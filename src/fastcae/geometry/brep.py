"""STEP loading and face-tagged tessellation.

Everything downstream keys off the CAD face id. A triangle that does not know which face it came
from cannot be selected, cannot be frozen, and cannot carry a design parameter, so the face id
travels with the triangle from here to the browser.

**Tessellation, not meshing.** OCC's ``BRepMesh`` walks each face's own surface definition and is
indifferent to whether the face is parametrisable in the way a volume mesher needs. gmsh's 2D
algorithm is a mesher and cannot process the part in ``assets/`` at all: it stops on a periodic
cylindrical face, and with OCC healing enabled it stops on a wire it cannot repair instead. A
mesher that loses faces leaves holes, and a hole has to be bridged by geometry nobody modelled -
which is why this module tessellates instead.

**Version pin.** ``cadquery-ocp`` is held at 7.9.3.1.1. The 8.x wheel ships an unsigned binary
that Windows Smart App Control refuses to load, and Smart App Control offers no per-file exception
list. An environment constraint rather than a preference; expect this failure if the pin is raised.

Source is ASCII only. An earlier patch written through ``Path.write_text`` picked up the Windows
default codepage and corrupted every non-ASCII character in the file.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepTools import BRepTools
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS, TopoDS_Compound, TopoDS_Face, TopoDS_Shape
from scipy.spatial import cKDTree

# Welding tolerance in mm for joining per-face triangulations into one surface.
#
# One micron. Real CAD carries sub-micron mismatches where two faces were meant to meet and do not
# quite, and those are the cracks a weld exists to close; the smallest geometry anyone deliberately
# models is orders of magnitude larger. A tolerance between the two closes every crack while being
# unable to merge distinct geometry.
WELD_TOL_MM = 1e-3

# The unit every internal length is in.
#
# Declared rather than inherited. OCC rescales a STEP into whatever `xstep.cascade.unit` names, and
# that setting reads as empty by default - so the whole system was relying on an unstated default
# to be millimetres. Setting it makes the conversion a decision, and means a file drawn in inches
# or metres arrives at the same scale as one drawn in millimetres instead of being 25x or 1000x
# wrong with nothing to notice it.
INTERNAL_UNIT = "MM"

# Chord tolerance as a fraction of the model's bounding diagonal, and the range it is held within.
#
# Absolute tolerances hide an assumption about part size. Half a millimetre is a reasonable chord
# on a two-metre casting and a coarse one on a forty-millimetre bracket, so the default is derived
# from the model and only the *bounds* are absolute: below 10 um the tessellation stops being worth
# the triangles, and above 1 mm nothing small survives.
DEFLECTION_FRACTION = 2.5e-4
MIN_DEFLECTION_MM = 0.01
MAX_DEFLECTION_MM = 1.0

# Maximum turn between adjacent triangles.
#
# The angular tolerance usually governs, not the linear one: a chord subtending angle t on radius r
# sags r(1 - cos(t/2)) whatever chord limit is set, so on a part whose area is dominated by
# large-radius surfaces, tightening the deflection alone changes almost nothing.
#
# Refining without limit is not safer. Past a point the surface reopens, as slivers appear below
# the weld tolerance faster than fidelity improves. The health gate says where that point is for a
# given part; it is not a constant.
DISPLAY_ANGLE_DEG = 20.0


@dataclass(frozen=True)
class ExactProperties:
    """Volume and area from the B-rep itself, not from any discretisation.

    These are the reference values every tessellation is measured against, and the closest thing a
    part has to ground truth. Not exact, though: a face whose analytic area is malformed
    contributes a wrong amount to the analytic volume while its triangles contribute a right one,
    so on such a part the two disagree by more than discretisation explains. The health gate
    measures that residual rather than assuming a bound for it.

    There is no mass here. Volume is a property of geometry; mass needs a density, and a density is
    a claim some document has to make.
    """

    volume_mm3: float
    area_mm2: float
    n_faces: int
    n_solids: int
    bbox_mm: tuple[float, float, float, float, float, float]

    @property
    def volume_cm3(self) -> float:
        return self.volume_mm3 / 1e3

    @property
    def size_mm(self) -> tuple[float, float, float]:
        x0, y0, z0, x1, y1, z1 = self.bbox_mm
        return (x1 - x0, y1 - y0, z1 - z0)

    def mass_kg(self, density_g_cm3: float) -> float:
        """Mass, given a density.

        No default, deliberately. Nothing in a project folder states a material unless one of its
        documents does, and a density assumed here would be indistinguishable downstream from one
        that was read. A caller wanting a mass has to supply the density and say where it came
        from.
        """
        return self.volume_cm3 * density_g_cm3 / 1e3


@dataclass
class Tessellation:
    """A welded triangle surface that remembers where each triangle came from.

    ``vertices``   (n, 3) float64, mm, in the STEP's own frame.
    ``triangles``  (m, 3) int32, indices into ``vertices``, wound counter-clockwise seen from
                   outside the solid.
    ``face_id``    (m,) int32, the CAD face each triangle belongs to.
    ``face_ids``   the CAD face ids that produced triangles, in explorer order, which is the
                   definition of the id and is stable for a given STEP file.
    """

    vertices: np.ndarray
    triangles: np.ndarray
    face_id: np.ndarray
    face_ids: list[int]
    deflection_mm: float
    angle_deg: float
    faces_without_triangles: list[int]

    @property
    def n_vertices(self) -> int:
        return int(self.vertices.shape[0])

    @property
    def n_triangles(self) -> int:
        return int(self.triangles.shape[0])

    def volume_mm3(self) -> float:
        """Signed volume by the divergence theorem over the closed surface.

        Meaningful only on a watertight, coherently wound mesh, which is why this is the quantity
        the S0 gate compares against the B-rep volume. On a leaking surface it is quietly wrong,
        and that is the failure this stage exists to catch.
        """
        a = self.vertices[self.triangles[:, 0]]
        b = self.vertices[self.triangles[:, 1]]
        c = self.vertices[self.triangles[:, 2]]
        return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)

    def area_mm2(self) -> float:
        a = self.vertices[self.triangles[:, 0]]
        b = self.vertices[self.triangles[:, 1]]
        c = self.vertices[self.triangles[:, 2]]
        return float(np.linalg.norm(np.cross(b - a, c - a), axis=1).sum() / 2.0)

    def triangle_areas(self) -> np.ndarray:
        a = self.vertices[self.triangles[:, 0]]
        b = self.vertices[self.triangles[:, 1]]
        c = self.vertices[self.triangles[:, 2]]
        return np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2.0

    def face_areas(self) -> dict[int, float]:
        """Tessellated area per CAD face. Feeds the atlas and the selection tools."""
        area = self.triangle_areas()
        out: dict[int, float] = {}
        for fid in np.unique(self.face_id):
            out[int(fid)] = float(area[self.face_id == fid].sum())
        return out
def declared_unit(path: Path) -> str:
    """The length unit the STEP file declares, read from its header.

    Reported rather than acted on: OCC has already rescaled the geometry to
    :data:`INTERNAL_UNIT` by the time anything sees it. Knowing what the file said is still worth
    having, because a file that declares inches and a model that measures like millimetres is a
    discrepancy someone needs to look at.
    """
    # Streamed over the whole file rather than its header. A STEP declares its unit among the
    # entity records, which on a large part sit behind hundreds of thousands of coordinate lines -
    # reading only the opening of the file reported every part as declaring nothing.
    prefixes = ("MILLI", "CENTI", "DECI", "KILO", "MICRO", "NANO")
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if "SI_UNIT" in line and "METRE" in line:
                for name in prefixes:
                    if f".{name}." in line:
                        return f"{name.lower()}metre"
                return "metre"
            if "CONVERSION_BASED_UNIT" in line and "INCH" in line.upper():
                return "inch"
    return "unstated"


def scale_deflection(bbox_mm: tuple[float, float, float, float, float, float]) -> float:
    """A chord tolerance proportional to the model, clamped to a usable range."""
    x0, y0, z0, x1, y1, z1 = bbox_mm
    diagonal = math.dist((x0, y0, z0), (x1, y1, z1))
    return min(max(diagonal * DEFLECTION_FRACTION, MIN_DEFLECTION_MM), MAX_DEFLECTION_MM)


def load_step(path: Path) -> TopoDS_Shape:
    # Stated explicitly so the conversion is a decision rather than an inherited default.
    Interface_Static.SetCVal_s("xstep.cascade.unit", INTERNAL_UNIT)
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone:
        raise OSError(f"STEP read failed with status {status}: {path}")
    reader.TransferRoots()
    shape = reader.OneShape()
    if shape.IsNull():
        raise ValueError(f"STEP produced a null shape: {path}")
    return shape


def load_cad(path: Path) -> tuple[TopoDS_Shape, list[str]]:
    """Read a CAD file by its extension. Returns the solid geometry, and notes on anything else.

    A STEP file is read as it stands. A ``.brep`` is OCC's own dump of whatever a CAD session held,
    which is not the same thing as a part: the baseline in ``assets/`` carries 29 loose edges beside
    its one solid, left where features were deleted. Passing those on would count them as geometry
    and hand the atlas edges with no face; dropping them silently would hide that the file is not
    clean. So the solids are kept, and everything else is named in a note.
    """
    if path.suffix.lower() != ".brep":
        return load_step(path), []

    shape = TopoDS_Shape()
    if not BRepTools.Read_s(shape, str(path), BRep_Builder()) or shape.IsNull():
        raise OSError(f"BREP read failed: {path}")

    solids = []
    exp = TopExp_Explorer(shape, TopAbs_SOLID)
    while exp.More():
        solids.append(exp.Current())
        exp.Next()
    if not solids:
        raise ValueError(f"the file holds no solid: {path}")

    notes = []
    loose_faces = _count_outside(shape, TopAbs_FACE, TopAbs_SOLID)
    loose_edges = _count_outside(shape, TopAbs_EDGE, TopAbs_FACE)
    if loose_faces:
        notes.append(f"the file also holds {loose_faces} loose faces outside any solid; not read")
    if loose_edges:
        notes.append(f"the file also holds {loose_edges} loose edges outside any face; not read")

    if len(solids) == 1:
        return solids[0], notes
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for solid in solids:
        builder.Add(compound, solid)
    return compound, notes


def _count_outside(shape: TopoDS_Shape, kind: int, container: int) -> int:
    """How many sub-shapes of ``kind`` are not part of any ``container``."""
    n = 0
    exp = TopExp_Explorer(shape, kind, container)
    while exp.More():
        n += 1
        exp.Next()
    return n


def faces_of(shape: TopoDS_Shape) -> list[TopoDS_Face]:
    """CAD faces in explorer order. That order is the definition of the face id."""
    out: list[TopoDS_Face] = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        out.append(TopoDS.Face_s(exp.Current()))
        exp.Next()
    return out


def _count(shape: TopoDS_Shape, kind: int) -> int:
    n = 0
    exp = TopExp_Explorer(shape, kind)
    while exp.More():
        n += 1
        exp.Next()
    return n


def exact_properties(shape: TopoDS_Shape) -> ExactProperties:
    vol = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, vol)
    area = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape, area)

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    x0, y0, z0, x1, y1, z1 = box.Get()

    return ExactProperties(
        volume_mm3=float(vol.Mass()),
        area_mm2=float(area.Mass()),
        n_faces=_count(shape, TopAbs_FACE),
        n_solids=_count(shape, TopAbs_SOLID),
        bbox_mm=(float(x0), float(y0), float(z0), float(x1), float(y1), float(z1)),
    )


def tessellate(
    shape: TopoDS_Shape,
    deflection_mm: float | None = None,
    angle_deg: float = DISPLAY_ANGLE_DEG,
    weld_tol_mm: float = WELD_TOL_MM,
) -> Tessellation:
    """Tessellate every face and weld the per-face triangulations into one surface.

    ``deflection_mm`` bounds the distance between a triangle chord and the true surface;
    ``angle_deg`` bounds the turn between adjacent triangles. The angular one is usually binding,
    for the reasons set out with the constants above.

    ``deflection_mm`` defaults to a fraction of the model's own size rather than to a fixed
    number, so a small part is not tessellated as coarsely as a large one.

    The shape is cleaned first, and that is not optional. ``BRepMesh_IncrementalMesh`` *mutates*
    the shape it is given, storing a triangulation on each face, and on a later call it leaves
    alone any face whose stored triangulation is already at least as fine as requested. Tessellate
    the same shape twice at different tolerances and the second result silently inherits the
    first, so a tolerance sweep reports convergence that is an artefact of call order. Cleaning
    makes the result depend only on the arguments.
    """
    if deflection_mm is None:
        box = Bnd_Box()
        BRepBndLib.Add_s(shape, box)
        deflection_mm = scale_deflection(box.Get())

    BRepTools.Clean_s(shape)
    BRepMesh_IncrementalMesh(shape, deflection_mm, False, math.radians(angle_deg), True)

    faces = faces_of(shape)
    verts_parts: list[np.ndarray] = []
    tris_parts: list[np.ndarray] = []
    fid_parts: list[np.ndarray] = []
    face_ids: list[int] = []
    empty: list[int] = []
    offset = 0

    for fid, face in enumerate(faces):
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is None or tri.NbNodes() < 3 or tri.NbTriangles() < 1:
            # Recorded, never skipped silently: a face that produced no triangles is a hole in
            # the surface, and a hole makes every inside/outside answer downstream unreliable.
            empty.append(fid)
            continue

        n_nodes = tri.NbNodes()
        n_tris = tri.NbTriangles()
        trsf = loc.Transformation()

        pts = np.empty((n_nodes, 3), dtype=np.float64)
        for i in range(1, n_nodes + 1):
            p = tri.Node(i).Transformed(trsf)
            pts[i - 1] = (p.X(), p.Y(), p.Z())

        idx = np.empty((n_tris, 3), dtype=np.int64)
        for i in range(1, n_tris + 1):
            n1, n2, n3 = tri.Triangle(i).Get()
            idx[i - 1] = (n1 - 1, n2 - 1, n3 - 1)

        # A REVERSED face carries its triangulation in the surface's own sense, which points into
        # the solid. Flipping here is what makes the assembled surface coherently outward, which
        # in turn is what makes the divergence-theorem volume positive and ray parity well
        # defined.
        if face.Orientation() == TopAbs_REVERSED:
            idx = idx[:, [0, 2, 1]]

        verts_parts.append(pts)
        tris_parts.append(idx + offset)
        fid_parts.append(np.full(n_tris, fid, dtype=np.int32))
        face_ids.append(fid)
        offset += n_nodes

    if not verts_parts:
        raise ValueError("tessellation produced no triangles")

    vertices = np.concatenate(verts_parts, axis=0)
    triangles = np.concatenate(tris_parts, axis=0)
    face_id = np.concatenate(fid_parts, axis=0)

    vertices, triangles = _weld(vertices, triangles, weld_tol_mm)
    triangles, face_id = _drop_degenerate(triangles, face_id)

    return Tessellation(
        vertices=vertices,
        triangles=triangles.astype(np.int32),
        face_id=face_id,
        face_ids=face_ids,
        deflection_mm=deflection_mm,
        angle_deg=angle_deg,
        faces_without_triangles=empty,
    )


def _weld(vertices: np.ndarray, triangles: np.ndarray, tol: float) -> tuple[np.ndarray, np.ndarray]:
    """Merge coincident vertices so adjacent faces share edges rather than abutting them.

    Two passes, and the second is the point. Rounding coordinates onto a grid and taking uniques
    is fast, but it merges by *bin* rather than by *distance*: two points closer than the tolerance
    land in different bins whenever they straddle a boundary, and the crack stays open. Widening
    the bin until it happens to catch one particular pair is luck rather than a guarantee, and the
    next part straddles somewhere else.

    So the grid pass collapses only exact repeats, which is most of them since BRepMesh reuses a
    shared edge's discretisation, and a KD-tree pass then merges anything genuinely within
    ``tol``, transitively.
    """
    # Pass 1: exact repeats. Quarter-tolerance bins, so nothing merged here is anywhere near the
    # tolerance limit and this pass can only help the one that follows.
    keys = np.round(vertices / (tol / 4.0)).astype(np.int64)
    _, first, coarse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
    reduced = vertices[first]

    # Pass 2: distance-exact merge of whatever the grid split apart.
    pairs = cKDTree(reduced).query_pairs(tol, output_type="ndarray")
    if pairs.size:
        parent = np.arange(reduced.shape[0], dtype=np.int64)

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = int(parent[x])
            return x

        for i, j in pairs:
            ri, rj = find(int(i)), find(int(j))
            if ri != rj:
                parent[max(ri, rj)] = min(ri, rj)

        roots = np.array([find(int(i)) for i in range(reduced.shape[0])], dtype=np.int64)
        keep, fine = np.unique(roots, return_inverse=True)
        reduced = reduced[keep]
        coarse = fine[coarse]

    return reduced, coarse[triangles].reshape(-1, 3)


def _drop_degenerate(triangles: np.ndarray, face_id: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Remove triangles that welding collapsed to an edge or a point.

    BRepMesh emits them at cone apexes and sphere poles. They carry no area and no volume, but
    they do leave edges used an odd number of times, which would make a closed surface report as
    leaking. Dropping them cannot open a hole: a triangle with a repeated vertex contributes a
    self-loop plus a cancelling pair, so removing it takes two uses off a single undirected edge.
    """
    a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    keep = (a != b) & (b != c) & (a != c)
    return triangles[keep], face_id[keep]
