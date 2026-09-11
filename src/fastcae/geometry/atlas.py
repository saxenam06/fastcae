"""The face atlas: what every CAD face is, measured from the B-rep.

This is what makes the part addressable. A triangle on screen carries a face id; the atlas turns
that id into "a concave cylinder of this diameter on this axis, at this station, adjacent to these
six faces". Without it a click is a triangle and nothing more, and "select the smooth region
between those two openings" is not a question anyone can answer.

Everything here is measured, never inferred from a document, and nothing here knows what any of it
is *for*. Geometric kinds and sizes only; roles and names arrive later, in :mod:`fastcae.extract`,
from whatever documents the project contains. Keeping the two apart is what makes a cross-check
possible - two independent accounts, compared, rather than one overwriting the other - and it is
what lets the same code read a bracket tomorrow.

Face ids are positions in ``TopExp_Explorer`` order over the STEP, and are stable for a given
file. They are **not** stable across a healed or re-exported B-rep, because healing splits faces
and renumbers everything after them. An atlas is therefore bound to one geometry hash and says so;
carrying face ids between two exports of "the same" part is how a selection silently moves.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import GeomAbs_SurfaceType
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape
from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape

from .brep import WELD_TOL_MM, Tessellation, faces_of

# OCC's surface-type enum as readable names. Anything OCC does not classify becomes "other"
# rather than a number, because these strings reach the UI and the agent.
_SURFACE_NAMES = {
    GeomAbs_SurfaceType.GeomAbs_Plane: "plane",
    GeomAbs_SurfaceType.GeomAbs_Cylinder: "cylinder",
    GeomAbs_SurfaceType.GeomAbs_Cone: "cone",
    GeomAbs_SurfaceType.GeomAbs_Sphere: "sphere",
    GeomAbs_SurfaceType.GeomAbs_Torus: "torus",
    GeomAbs_SurfaceType.GeomAbs_BezierSurface: "bezier",
    GeomAbs_SurfaceType.GeomAbs_BSplineSurface: "bspline",
    GeomAbs_SurfaceType.GeomAbs_SurfaceOfRevolution: "revolution",
    GeomAbs_SurfaceType.GeomAbs_SurfaceOfExtrusion: "extrusion",
    GeomAbs_SurfaceType.GeomAbs_OffsetSurface: "offset",
    GeomAbs_SurfaceType.GeomAbs_OtherSurface: "other",
}


@dataclass
class FaceRecord:
    """One CAD face, as the B-rep describes it.

    Fields are ``None`` where they do not apply: a plane has no radius, a b-spline has no axis.
    That is preferable to a sentinel, because a caller asking a cylinder question of a plane
    should get nothing rather than a plausible zero.
    """

    face_id: int
    surface_type: str

    area_mm2: float
    """Analytic area from OCC. Negative on some faces of real CAD, which is why the tessellated
    area is kept beside it and :attr:`area` prefers whichever is usable."""

    tess_area_mm2: float
    """Area of this face's triangles. The honest area when the analytic one is malformed."""

    centroid: tuple[float, float, float]
    bbox_mm: tuple[float, float, float, float, float, float]

    normal: tuple[float, float, float] | None = None
    """Outward normal at the face centre, orientation applied. Planes and simple surfaces."""

    axis: tuple[float, float, float] | None = None
    axis_point: tuple[float, float, float] | None = None
    radius_mm: float | None = None
    minor_radius_mm: float | None = None
    half_angle_deg: float | None = None

    concave: bool | None = None
    """True when material lies outside the surface - a bore or a fillet root, not a boss."""

    exterior: bool = False
    """Whether this face can be seen from outside the casting.

    A bore wall and an outer skin panel are both perfectly ordinary faces with outward normals;
    what separates them is whether anything blocks the view. This is the property behind "select
    the outer skin", so it is measured by ray casting rather than guessed from curvature.
    """

    neighbours: tuple[int, ...] = ()
    """Faces sharing at least one edge, from OCC topology rather than from shared vertices."""

    dihedral: dict[int, float] = field(default_factory=dict)
    """Measured angle in degrees to each neighbour, across their shared edge.

    Zero means tangent - the two surfaces flow into one another, as a fillet does into the wall it
    blends. Ninety means a square corner. This is what selection growing walks, and it is measured
    from the tessellation rather than derived from surface types, so it is defined for every face
    including the tori, cones, spheres and b-splines that have no analytic normal at all.
    """

    facing: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """The way the face points overall: its area-weighted mean triangle normal, unit length.

    Measured from the tessellation, so it exists for every surface type. It is the direction a rib
    placed on this face would rise in, and the direction selection growing measures against.
    """

    flatness: float = 0.0
    """How much of a single direction this face has. One on a plane, zero on a full cylinder.

    The length of the mean normal before it was normalised. A face that wraps around cancels itself
    out, and :attr:`facing` becomes meaningless - this is what says so, rather than a caller having
    to know which surface types curve.
    """

    @property
    def area(self) -> float:
        """The area to actually use. Falls back to the tessellation where OCC returns nonsense."""
        return self.area_mm2 if self.area_mm2 > 0 else self.tess_area_mm2

    @property
    def diameter_mm(self) -> float | None:
        return None if self.radius_mm is None else 2.0 * self.radius_mm

    @property
    def z_mm(self) -> float:
        return self.centroid[2]

    def describe(self) -> str:
        bits = [f"face {self.face_id}", self.surface_type]
        if self.diameter_mm is not None:
            bits.append(f"O{self.diameter_mm:.1f}")
        bits.append(f"{self.area:.0f} mm2")
        bits.append(f"z {self.z_mm:.1f}")
        if self.concave is not None:
            bits.append("concave" if self.concave else "convex")
        bits.append("exterior" if self.exterior else "internal")
        return "  ".join(bits)


@dataclass
class Atlas:
    """Every face of one geometry, plus the adjacency needed to grow a selection."""

    geometry_hash: str
    faces: dict[int, FaceRecord] = field(default_factory=dict)
    diagonal_mm: float = 0.0
    """The model's bounding diagonal. Every size-dependent tolerance is derived from it."""

    def __len__(self) -> int:
        return len(self.faces)

    def __getitem__(self, face_id: int) -> FaceRecord:
        return self.faces[face_id]

    def of_type(self, surface_type: str) -> list[FaceRecord]:
        return [f for f in self.faces.values() if f.surface_type == surface_type]

    def exterior_faces(self) -> list[FaceRecord]:
        return [f for f in self.faces.values() if f.exterior]

    def type_counts(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for f in self.faces.values():
            counts[f.surface_type] += 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    def grow(
        self,
        seed: set[int] | list[int],
        max_dihedral_deg: float = 40.0,
        max_faces: int = 5000,
    ) -> set[int]:
        """Flood a selection outward while the surface keeps facing the way the seed faces.

        This is what turns one click into the region a rib can stand on, and the angle is the one
        control: **no face may point more than this far from the face you started on.**

        Two gates, and the second is the one that matters. The first is the measured dihedral at
        the shared edge, which stops the walk at a crease. The second compares each candidate's
        :attr:`FaceRecord.facing` against the seed's.

        The dihedral gate alone is not enough, and on real CAD it is not even close. A cast housing
        is tangent-continuous nearly everywhere - on the part in ``assets/``, 60% of all face
        boundaries bend by less than five degrees, because every corner is a fillet that flows into
        both surfaces it joins. A per-edge test has no memory, so a walk turns through ninety
        degrees in ten nine-degree steps while every single step passes a forty-degree gate, and
        one click takes the whole shell. Measuring against the seed instead of against the previous
        face is what gives the threshold something to hold on to.

        Where the seed has no direction of its own - a full cylinder cancels itself out, and
        :attr:`FaceRecord.flatness` says so - nothing passes the second gate and the selection
        stays as it was. Refusing to spread is the honest answer there: a bore faces every way at
        once, so "faces pointing the same way as this one" has no meaning to compute.
        """
        selected = {int(s) for s in seed}
        aim = self._facing_of(selected)
        if aim is None:
            return selected

        limit = math.cos(math.radians(max_dihedral_deg))
        frontier = list(selected)

        while frontier and len(selected) < max_faces:
            current = self.faces.get(frontier.pop())
            if current is None:
                continue
            for neighbour_id, angle in current.dihedral.items():
                if neighbour_id in selected or angle > max_dihedral_deg:
                    continue
                neighbour = self.faces.get(neighbour_id)
                if neighbour is None or _dot(neighbour.facing, aim) < limit:
                    continue
                selected.add(neighbour_id)
                frontier.append(neighbour_id)

        return selected

    def _facing_of(self, seed: set[int]) -> tuple[float, float, float] | None:
        """The direction a seed selection points, area-weighted. ``None`` if it has none."""
        total = [0.0, 0.0, 0.0]
        for face_id in seed:
            face = self.faces.get(face_id)
            if face is None:
                continue
            weight = face.area * face.flatness
            for axis in range(3):
                total[axis] += face.facing[axis] * weight

        length = math.sqrt(sum(v * v for v in total))
        if length < 1e-9:
            return None
        return (total[0] / length, total[1] / length, total[2] / length)

    def similar(
        self,
        face_id: int,
        radius_tol_mm: float | None = None,
        area_tol: float = 0.05,
    ) -> set[int]:
        """Faces of the same type and size anywhere on the part.

        One click on a hole should offer the family it belongs to. Matching is on radius where the
        surface has one and on area otherwise, because area alone would sweep up every unrelated
        patch that happens to be the same size.

        The radius tolerance is tight, and derived from the model's size rather than fixed: parts
        routinely carry several hole families whose diameters differ by a fraction, and too wide a
        band spans all of them at once, silently merging distinct patterns into one selection. CAD
        nominals are exact numbers, so a loose tolerance buys nothing.
        """
        if radius_tol_mm is None:
            radius_tol_mm = max(self.diagonal_mm * 5e-5, 1e-3)
        seed = self.faces[face_id]
        out = {face_id}
        for other in self.faces.values():
            if other.face_id == face_id or other.surface_type != seed.surface_type:
                continue
            if seed.radius_mm is not None and other.radius_mm is not None:
                if abs(seed.radius_mm - other.radius_mm) <= radius_tol_mm:
                    out.add(other.face_id)
            elif (
                seed.radius_mm is None
                and other.radius_mm is None
                and abs(other.area - seed.area) <= area_tol * max(seed.area, 1e-9)
            ):
                out.add(other.face_id)
        return out


def build(shape: TopoDS_Shape, tess: Tessellation, geometry_hash: str) -> Atlas:  # noqa: C901
    """Measure every face of the shape.

    ``tess`` is needed for two things the B-rep cannot supply on its own: an area for the faces
    whose analytic area is negative, and the ray casting that decides what is exterior.
    """
    faces = faces_of(shape)
    tess_areas = tess.face_areas()
    adjacency = _adjacency(shape, faces)

    lo = tess.vertices.min(axis=0)
    hi = tess.vertices.max(axis=0)
    diagonal = float(np.linalg.norm(hi - lo))
    exterior = _exterior_faces(tess, diagonal)

    dihedrals = _edge_dihedrals(tess)
    facing, flatness = _face_directions(tess, len(faces))

    atlas = Atlas(geometry_hash=geometry_hash, diagonal_mm=diagonal)
    for face_id, face in enumerate(faces):
        record = _measure(face_id, face)
        record.tess_area_mm2 = tess_areas.get(face_id, 0.0)
        record.neighbours = tuple(sorted(adjacency.get(face_id, set())))
        record.dihedral = dihedrals.get(face_id, {})
        record.exterior = face_id in exterior
        record.facing = tuple(float(v) for v in facing[face_id])  # type: ignore[assignment]
        record.flatness = float(flatness[face_id])
        atlas.faces[face_id] = record

    return atlas


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _face_directions(tess: Tessellation, n_faces: int) -> tuple[np.ndarray, np.ndarray]:
    """The way each face points, and how much of a single direction it has.

    Area-weighted, so a large panel decides its own direction rather than a sliver at its edge, and
    taken from the tessellation so that it exists for the tori, cones and b-splines that carry no
    analytic normal. The weight is deliberately the unnormalised cross product: its length is twice
    the triangle's area.

    ``flatness`` is the length of the mean direction before normalising. It is one on a plane and
    falls towards zero as a face wraps, so it is also the test for whether ``facing`` means
    anything at all - a full cylinder cancels itself out and has no direction to report.
    """
    corners = tess.triangles
    a = tess.vertices[corners[:, 0]]
    b = tess.vertices[corners[:, 1]]
    c = tess.vertices[corners[:, 2]]

    weighted = np.cross(b - a, c - a)
    areas = np.linalg.norm(weighted, axis=1)

    total = np.zeros((n_faces, 3))
    weight = np.zeros(n_faces)
    np.add.at(total, tess.face_id, weighted)
    np.add.at(weight, tess.face_id, areas)

    length = np.linalg.norm(total, axis=1)
    safe = length[:, None] > 1e-12
    facing = np.divide(total, length[:, None], out=np.zeros_like(total), where=safe)
    flatness = np.divide(length, weight, out=np.zeros(n_faces), where=weight > 1e-12)
    return facing, flatness


def _edge_dihedrals(tess: Tessellation) -> dict[int, dict[int, float]]:
    """Measure the angle between every pair of faces that meet, at the edge where they meet.

    Walks the tessellation once. Every undirected edge used by exactly two triangles belonging to
    different CAD faces is a piece of the boundary between those faces, and the angle between the
    two triangle normals there is the dihedral. A face pair usually shares many such edges, so the
    **median** is taken: a couple of sliver triangles at the ends of an edge can be wildly
    misoriented, and a mean would let them drag the whole boundary open or shut.

    Measuring rather than deriving is what makes this work at all. Tori, cones, spheres and
    b-splines carry no analytic normal, and a curved face has no single normal to compare even
    when one exists.
    """
    verts, tris, face_id = tess.vertices, tess.triangles, tess.face_id

    a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    normals = np.cross(b - a, c - a)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 1e-12)

    directed = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]], axis=0)
    owner = np.tile(np.arange(tris.shape[0]), 3)

    undirected = np.sort(directed, axis=1)
    order = np.lexsort((undirected[:, 1], undirected[:, 0]))
    sorted_edges = undirected[order]
    sorted_owner = owner[order]

    # Adjacent rows sharing an edge are the two triangles that meet along it. On a watertight
    # surface every interior edge appears exactly twice, so pairing neighbours is enough.
    same = np.all(sorted_edges[:-1] == sorted_edges[1:], axis=1)
    left = sorted_owner[:-1][same]
    right = sorted_owner[1:][same]

    face_left = face_id[left]
    face_right = face_id[right]
    across = face_left != face_right
    if not across.any():
        return {}

    left, right = left[across], right[across]
    face_left, face_right = face_left[across], face_right[across]

    cosine = np.clip(np.einsum("ij,ij->i", normals[left], normals[right]), -1.0, 1.0)
    angle = np.degrees(np.arccos(cosine))

    samples: dict[tuple[int, int], list[float]] = defaultdict(list)
    for fl, fr, deg in zip(face_left, face_right, angle, strict=True):
        samples[(int(fl), int(fr))].append(float(deg))

    out: dict[int, dict[int, float]] = defaultdict(dict)
    for (fl, fr), values in samples.items():
        median = float(np.median(values))
        out[fl][fr] = median
        out[fr][fl] = median
    return dict(out)


def _measure(face_id: int, face: TopoDS_Face) -> FaceRecord:
    """Read one face's surface definition through OCC's adaptor."""
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    com = props.CentreOfMass()

    box = Bnd_Box()
    BRepBndLib.Add_s(face, box)
    x0, y0, z0, x1, y1, z1 = box.Get()

    adaptor = BRepAdaptor_Surface(face)
    kind = _SURFACE_NAMES.get(adaptor.GetType(), "other")
    reversed_face = face.Orientation() == TopAbs_REVERSED

    record = FaceRecord(
        face_id=face_id,
        surface_type=kind,
        area_mm2=float(props.Mass()),
        tess_area_mm2=0.0,
        centroid=(com.X(), com.Y(), com.Z()),
        bbox_mm=(float(x0), float(y0), float(z0), float(x1), float(y1), float(z1)),
    )

    if kind == "plane":
        pln = adaptor.Plane()
        n = pln.Axis().Direction()
        vec = np.array([n.X(), n.Y(), n.Z()], dtype=float)
        if reversed_face:
            vec = -vec
        record.normal = tuple(vec)
    elif kind == "cylinder":
        cyl = adaptor.Cylinder()
        ax, loc = cyl.Axis().Direction(), cyl.Location()
        record.axis = (ax.X(), ax.Y(), ax.Z())
        record.axis_point = (loc.X(), loc.Y(), loc.Z())
        record.radius_mm = float(cyl.Radius())
        record.concave = reversed_face
        record.normal = _radial_normal(record, reversed_face)
    elif kind == "cone":
        cone = adaptor.Cone()
        ax, loc = cone.Axis().Direction(), cone.Location()
        record.axis = (ax.X(), ax.Y(), ax.Z())
        record.axis_point = (loc.X(), loc.Y(), loc.Z())
        record.radius_mm = float(cone.RefRadius())
        record.half_angle_deg = math.degrees(float(cone.SemiAngle()))
        record.concave = reversed_face
    elif kind == "sphere":
        sph = adaptor.Sphere()
        loc = sph.Location()
        record.axis_point = (loc.X(), loc.Y(), loc.Z())
        record.radius_mm = float(sph.Radius())
        record.concave = reversed_face
    elif kind == "torus":
        tor = adaptor.Torus()
        ax, loc = tor.Axis().Direction(), tor.Location()
        record.axis = (ax.X(), ax.Y(), ax.Z())
        record.axis_point = (loc.X(), loc.Y(), loc.Z())
        record.radius_mm = float(tor.MajorRadius())
        record.minor_radius_mm = float(tor.MinorRadius())
        record.concave = reversed_face

    return record


def _radial_normal(record: FaceRecord, reversed_face: bool) -> tuple[float, float, float] | None:
    """Outward normal of a cylinder at its centroid.

    Radially away from the axis, or towards it when the face is concave and the material lies
    outside the surface.
    """
    if record.axis is None or record.axis_point is None:
        return None
    axis = np.asarray(record.axis, dtype=float)
    to_com = np.asarray(record.centroid, dtype=float) - np.asarray(record.axis_point, dtype=float)
    radial = to_com - np.dot(to_com, axis) * axis
    norm = float(np.linalg.norm(radial))
    if norm < 1e-9:
        return None
    radial = radial / norm
    return tuple(-radial if reversed_face else radial)


def _adjacency(shape: TopoDS_Shape, faces: list[TopoDS_Face]) -> dict[int, set[int]]:
    """Which faces share an edge, from OCC's own topology map.

    Topology rather than shared tessellation vertices, deliberately. Two faces can share vertices
    without sharing an edge - a rib flank and a wall meet at a corner point - and a selection that
    leaked through such a point would jump to an unrelated face and look like a bug in the angle
    threshold rather than a bug here.
    """
    index = {face.TShape(): i for i, face in enumerate(faces)}
    edge_to_faces = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, edge_to_faces)

    adjacency: dict[int, set[int]] = defaultdict(set)
    for i in range(1, edge_to_faces.Extent() + 1):
        touching = [
            index[TopoDS.Face_s(f).TShape()]
            for f in edge_to_faces.FindFromIndex(i)
            if TopoDS.Face_s(f).TShape() in index
        ]
        for a in touching:
            for b in touching:
                if a != b:
                    adjacency[a].add(b)
    return adjacency


def _exterior_faces(tess: Tessellation, diagonal: float, samples_per_face: int = 6) -> set[int]:
    """Decide which faces are reachable from outside, by casting rays outward.

    The test is simply whether a ray leaving the surface along its own outward normal escapes
    without hitting the casting again. A skin panel escapes; a bore wall looks across the bore and
    hits the far side.

    Sampling several triangles per face and taking a majority matters. A single ray from one
    triangle of a large curved panel can graze a boss and report the whole panel internal, and
    that panel is exactly the sort of region a user wants to select.
    """
    verts = tess.vertices
    tris = tess.triangles
    a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    centres = (a + b + c) / 3.0
    normals = np.cross(b - a, c - a)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 1e-12)

    rng = np.random.default_rng(0)
    by_face: dict[int, list[int]] = defaultdict(list)
    for tri_index, face_id in enumerate(tess.face_id):
        by_face[int(face_id)].append(tri_index)

    chosen: list[int] = []
    owner: list[int] = []
    for face_id, indices in by_face.items():
        if len(indices) <= samples_per_face:
            picked = indices
        else:
            picked = rng.choice(indices, size=samples_per_face, replace=False).tolist()
        chosen.extend(picked)
        owner.extend([face_id] * len(picked))

    chosen_arr = np.asarray(chosen, dtype=np.int64)
    # Offset the origin off the surface, or a ray immediately re-hits the triangle it started from
    # and every face reports as internal. Scaled to the model but floored above the weld tolerance,
    # since below that the offset is inside the noise the weld was closing.
    offset = max(diagonal * 5e-6, WELD_TOL_MM * 10.0)
    origins = centres[chosen_arr] + normals[chosen_arr] * offset
    directions = normals[chosen_arr]
    escaped = _rays_escape(origins, directions, verts, tris)

    votes_yes: dict[int, int] = defaultdict(int)
    votes_all: dict[int, int] = defaultdict(int)
    for face_id, ok in zip(owner, escaped, strict=True):
        votes_all[face_id] += 1
        votes_yes[face_id] += int(ok)

    return {fid for fid, total in votes_all.items() if votes_yes[fid] * 2 > total}


def _rays_escape(
    origins: np.ndarray,
    directions: np.ndarray,
    verts: np.ndarray,
    tris: np.ndarray,
) -> np.ndarray:
    """Does each ray reach infinity without hitting the surface again?

    Through Embree, because the brute-force alternative is not merely slower but a different
    order of work: 13,000 rays against 153,000 triangles is two billion ray-triangle tests, which
    took 180 seconds in numpy and would take minutes on the field tessellation's 1.34 million
    triangles. Embree does the same job in about a second by building a BVH first.

    ``embreex`` is an ordinary dependency, but the fallback below is kept for the case where its
    wheel is unavailable rather than letting the atlas fail to build at all.
    """
    try:
        from trimesh import Trimesh
        from trimesh.ray.ray_pyembree import RayMeshIntersector

        mesh = Trimesh(vertices=verts, faces=tris, process=False, validate=False)
        return ~RayMeshIntersector(mesh).intersects_any(origins, directions)
    except ImportError:
        return _rays_escape_bruteforce(origins, directions, verts, tris)


def _rays_escape_bruteforce(
    origins: np.ndarray,
    directions: np.ndarray,
    verts: np.ndarray,
    tris: np.ndarray,
    chunk: int = 256,
) -> np.ndarray:
    """Vectorised Moller-Trumbore against every triangle. Correct, and far too slow to rely on."""
    v0 = verts[tris[:, 0]]
    edge1 = verts[tris[:, 1]] - v0
    edge2 = verts[tris[:, 2]] - v0

    escaped = np.ones(origins.shape[0], dtype=bool)
    for start in range(0, origins.shape[0], chunk):
        stop = min(start + chunk, origins.shape[0])
        o = origins[start:stop, None, :]
        d = directions[start:stop, None, :]

        h = np.cross(d, edge2[None, :, :])
        det = np.einsum("ijk,jk->ij", h, edge1)
        parallel = np.abs(det) < 1e-12
        inv_det = np.divide(1.0, det, out=np.zeros_like(det), where=~parallel)

        s = o - v0[None, :, :]
        u = np.einsum("ijk,ijk->ij", s, h) * inv_det
        q = np.cross(s, edge1[None, :, :])
        v = np.einsum("ijk,ijk->ij", d, q) * inv_det
        t = np.einsum("ijk,jk->ij", q, edge2) * inv_det

        hit = (~parallel) & (u >= 0.0) & (u <= 1.0) & (v >= 0.0) & (u + v <= 1.0) & (t > 1e-6)
        escaped[start:stop] = ~hit.any(axis=1)

    return escaped
