"""A design volume: kept as the recipe the engineer's picks make, and found as a stack of flat
sections bounded by the part's own faces.

**The recipe** is what is kept: the faces picked, the axis, the band along it, the reach out from
it, the anchor the ribs grow from, and the keep-outs switched off. It is a handful of numbers and
names, the same on any machine, and re-found in about a second.

**Found in flat sections.** Square to the axis, every few millimetres across the band, a slice is
the region's disc less the part's metal (:mod:`fastcae.volumes.slices` - the part's real faces, in
2D) less what is kept clear. The air in a slice falls into pieces; a piece joins the pieces in the
slices on either side that it overlaps, so pockets form through the stack. The volume is every
pocket that touches the anchor and, when a floor was picked, the floor: air past a wall, in another
cavity, or under a face that runs on outside the part is a pocket of its own and is left out. Each
slice is exact in its plane, and the stack is exact to the slice spacing along the axis.

No solid boolean runs on the part: everything is 2D polygons, which never fail on how the part's
surfaces happen to meet.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import shapely
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from . import keepouts, reading, slices

if TYPE_CHECKING:
    from ..extract import Extraction

STEP_MM = 3.0
"""Slice spacing along the axis: how finely the volume follows a wall that leans."""

TOUCH_MM = 0.5
"""A pocket touches a face when its outline comes this close to the face's cut."""

OVERLAP_MM2 = 1.0
"""Pieces in neighbouring slices join when they share this much area."""

SHOWN_MM = 0.3
"""How far a drawn outline may stray from the slice's own."""

CRUMB_MM2 = 4.0
"""Pieces smaller than this in a slice are slivers between faces, not air ribs could use."""


@dataclass
class Recipe:
    """What a design volume is: the picks and the numbers read off them."""

    faces: list[int]
    kind: str
    """``floor`` - from a floor towards the side it faces - or ``between``."""
    axis: list[float]
    point: list[float]
    band: list[float]
    """Along the axis from ``point``, mm."""
    radius_mm: float
    anchors: list[int]
    floors: list[int]
    off: list[str] = field(default_factory=list)
    """Keep-outs switched off, by key."""
    band_default: list[float] = field(default_factory=list)
    band_limits: list[float] = field(default_factory=list)
    step_mm: float = STEP_MM

    @property
    def frame(self) -> reading.Frame:
        return reading.Frame(np.asarray(self.axis, float), np.asarray(self.point, float))

    def key(self) -> str:
        """The same recipe, the same key: what the volume found from it is kept under."""
        data = json.dumps(
            {k: v for k, v in asdict(self).items() if k not in ("band_default", "band_limits")},
            sort_keys=True,
        )
        return hashlib.sha1(data.encode()).hexdigest()[:12]


def recipe(
    extraction: Extraction,
    faces: list[int],
    band: tuple[float, float] | None = None,
    off: list[str] | None = None,
) -> Recipe:
    """The recipe the picks make: the axis, the band - the default, or the one given - the anchor,
    the floors, and the reach."""
    atlas = extraction.atlas
    tess = extraction.tess
    assert atlas is not None and tess is not None
    faces = list(dict.fromkeys(int(f) for f in faces))
    if not faces:
        raise ValueError("pick at least one face")
    frame, kind = reading.frame_of(extraction, faces)
    along = frame.along(tess.vertices)
    limits = (float(along.min()), float(along.max()))
    default = reading.default_band(extraction, faces, frame, kind)
    lo, hi = band if band is not None else default
    lo, hi = max(min(lo, hi), limits[0]), min(max(lo, hi), limits[1])
    if hi - lo < 1.0:
        raise ValueError("the band along the axis is empty")
    anchors = reading.anchors_of(extraction, faces, frame, (lo, hi), kind)
    floors = [
        f
        for f in faces
        if atlas.faces[f].surface_type == "plane"
        and atlas.faces[f].normal is not None
        and abs(float(reading.unit(atlas.faces[f].normal) @ frame.axis)) > reading.SQUARE
    ]
    radius = reading.reach(extraction, faces, frame, (lo, hi), anchors)
    return Recipe(
        faces=faces,
        kind=kind,
        axis=[float(v) for v in frame.axis],
        point=[float(v) for v in frame.point],
        band=[float(lo), float(hi)],
        radius_mm=float(radius),
        anchors=anchors,
        floors=floors,
        off=sorted(off or []),
        band_default=[float(default[0]), float(default[1])],
        band_limits=[float(limits[0]), float(limits[1])],
    )


@dataclass
class Volume:
    """A design volume found from its recipe: its air, slice by slice."""

    recipe: Recipe
    heights: np.ndarray
    """Each slice's middle along the axis, mm."""
    step: float
    """Slice spacing: the recipe's, fitted to the band."""
    air: list[BaseGeometry]
    """Each slice's air in the volume, in that slice's own coordinates."""
    kept_clear: list[keepouts.Keepout]
    """The keep-outs that reach into the region, switched off or not."""
    pockets: int
    left_out: int
    touches: dict[int, bool]
    seconds: float

    @property
    def planes(self) -> list[slices.Plane]:
        return [_slice_plane(self.recipe, s) for s in self.heights]

    @property
    def volume_mm3(self) -> float:
        return float(sum(a.area for a in self.air) * self.step)

    def contains(self, points: np.ndarray) -> np.ndarray:
        """Which of the points lie in the volume."""
        points = np.atleast_2d(np.asarray(points, float))
        frame = self.recipe.frame
        s = frame.along(points)
        k = np.floor((s - self.recipe.band[0]) / self.step).astype(int)
        out = np.zeros(len(points), bool)
        planes = self.planes
        for index in np.unique(k):
            if index < 0 or index >= len(self.air) or self.air[index].is_empty:
                continue
            mine = k == index
            uv = planes[index].to2d(points[mine])
            out[mine] = shapely.contains_xy(self.air[index], uv[:, 0], uv[:, 1])
        return out

    def surface(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """The volume's closed surface for display: the walls of each slice and the steps between
        slices. Vertices (n, 3), triangles (m, 3), and one outward normal per corner (3m, 3)."""
        frame = self.recipe.frame
        step = self.step
        planes = self.planes
        vertices: list[np.ndarray] = []
        normals: list[np.ndarray] = []

        def add(corners: np.ndarray, normal: np.ndarray) -> None:
            vertices.append(corners.reshape(-1, 3))
            normals.append(np.repeat(normal.reshape(-1, 1, 3), 3, axis=1).reshape(-1, 3))

        # Drawn from outlines simplified to a third of a millimetre: a tenth of the triangles, the
        # same picture. Only the drawing; what the volume holds is the slices as found.
        shown = [a if a.is_empty else a.simplify(SHOWN_MM) for a in self.air]
        for k, region in enumerate(shown):
            if region.is_empty:
                continue
            at = planes[k]
            low, high = -0.5 * step * frame.axis, 0.5 * step * frame.axis
            for polygon in getattr(region, "geoms", [region]):
                polygon = shapely.geometry.polygon.orient(polygon, 1.0)
                for ring in [polygon.exterior, *polygon.interiors]:
                    xy = np.asarray(ring.coords)
                    a3 = at.to3d(xy[:-1])
                    b3 = at.to3d(xy[1:])
                    edge = b3 - a3
                    out = np.cross(edge, frame.axis)
                    out /= np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-12)
                    quad1 = np.stack([a3 + low, b3 + low, b3 + high], axis=1)
                    quad2 = np.stack([a3 + low, b3 + high, a3 + high], axis=1)
                    add(np.concatenate([quad1, quad2]), np.concatenate([out, out]))
            # The step up to the next slice and down from the last: what one has and the other
            # does not.
            above = shown[k + 1] if k + 1 < len(shown) else None
            below = shown[k - 1] if k > 0 else None
            for other, sign in ((above, 1.0), (below, -1.0)):
                bare = region if other is None or other.is_empty else region.difference(other)
                if bare.is_empty:
                    continue
                flat = slices.triangles_of(bare)
                if not len(flat):
                    continue
                corners = at.to3d(flat) + sign * 0.5 * step * frame.axis
                add(corners, np.repeat((sign * frame.axis)[None, :], len(flat), axis=0))
        if not vertices:
            return np.empty((0, 3)), np.empty((0, 3), np.int64), np.empty((0, 3))
        corners = np.concatenate(vertices)
        normal = np.concatenate(normals)
        triangles = np.arange(len(corners)).reshape(-1, 3)
        # Wound to face the way their normal says.
        a, b, c = corners[triangles[:, 0]], corners[triangles[:, 1]], corners[triangles[:, 2]]
        wrong = np.einsum("ij,ij->i", np.cross(b - a, c - a), normal[triangles[:, 0]]) < 0
        triangles[wrong] = triangles[wrong][:, ::-1]
        return corners, triangles, normal

    def summary(self) -> dict[str, Any]:
        r = self.recipe
        lo, hi = r.band
        what = "over the floor" if r.kind == "floor" else "round the anchor"
        return {
            **asdict(r),
            "key": r.key(),
            "volume_L": round(self.volume_mm3 / 1e6, 2),
            "pockets": self.pockets,
            "left_out": self.left_out,
            "touches": {str(k): v for k, v in self.touches.items()},
            "keepouts": [{**k.summary(), "off": k.key in r.off} for k in self.kept_clear],
            "slices": len(self.air),
            "seconds": round(self.seconds, 2),
            "words": (
                f"{self.volume_mm3 / 1e6:.1f} L {what}, {hi - lo:.0f} mm along the axis, reaching "
                f"{r.radius_mm:.0f} mm from it; {len(self.kept_clear) - len(r.off)} kept clear"
            ),
        }


def _slice_plane(r: Recipe, s: float) -> slices.Plane:
    axis = np.asarray(r.axis, float)
    point = np.asarray(r.point, float)
    u = np.cross(axis, [1.0, 0.0, 0.0] if abs(axis[0]) < 0.9 else [0.0, 1.0, 0.0])
    return slices.plane(point + s * axis, axis, u)


def _parts(geometry: BaseGeometry) -> list[BaseGeometry]:
    if geometry.is_empty:
        return []
    return [g for g in getattr(geometry, "geoms", [geometry]) if g.area > CRUMB_MM2]


def find(extraction: Extraction, r: Recipe, setup: Any = None) -> Volume:
    """The volume a recipe makes."""
    started = time.perf_counter()
    tess = extraction.tess
    atlas = extraction.atlas
    assert tess is not None and atlas is not None
    frame = r.frame
    lo, hi = r.band
    count = max(1, int(round((hi - lo) / r.step_mm)))
    step = (hi - lo) / count
    heights = lo + (np.arange(count) + 0.5) * step
    region_box = _region_box(r)
    near = [k for k in keepouts.every(extraction, setup) if _boxes_meet(k.box, region_box)]
    kept_clear = [k for k in near if _reaches(k, r)]
    active = [k for k in kept_clear if k.key not in r.off]
    # Each keep-out's own extent along the axis: a slice cuts only those that span its height.
    spans = [
        (float(frame.along(k.vertices).min()), float(frame.along(k.vertices).max())) for k in active
    ]

    # Only the part's triangles within the band can be cut by its slices.
    along = frame.along(tess.vertices)
    # Every triangle that spans any of the band, corners inside it or not: a long triangle can
    # cross the band with both corners outside it.
    span = along[tess.triangles]
    within = (span.max(axis=1) >= lo - step) & (span.min(axis=1) <= hi + step)
    triangles = tess.triangles[within]
    face_id = tess.face_id[within]
    touch_faces = set(r.anchors) if r.anchors else (set(r.faces) - set(r.floors))
    disc = Point(0.0, 0.0).buffer(r.radius_mm, quad_segs=32)

    pieces: list[list[BaseGeometry]] = []
    touching: list[list[bool]] = []
    for s in heights:
        at = _slice_plane(r, float(s))
        cut = slices.section(tess.vertices, triangles, face_id, at)
        # Within the part's own outline in this slice - its convex hull - never outside its walls.
        region = disc.intersection(cut.inside.convex_hull) if not cut.inside.is_empty else disc
        air = region.difference(cut.inside) if not cut.inside.is_empty else region
        blocked = [
            slices.section(k.vertices, k.triangles, None, at).inside
            for k, (a, b) in zip(active, spans, strict=True)
            if a <= s <= b
        ]
        blocked = [b for b in blocked if not b.is_empty]
        if blocked:
            air = air.difference(shapely.union_all(blocked))
        parts = _parts(air)
        pieces.append(parts)
        lines = cut.lines(touch_faces) if touch_faces else None
        touching.append(
            [
                bool(lines is not None and not lines.is_empty and p.distance(lines) <= TOUCH_MM)
                for p in parts
            ]
        )

    # The floor: the pieces in the slice next to it that lie over it.
    on_floor: set[tuple[int, int]] = set()
    if r.floors:
        levels = [float(frame.along(reading.face_points(extraction, f)).mean()) for f in r.floors]
        for level in levels:
            k = int(np.clip(np.floor((level - lo) / step), 0, count - 1))
            at = _slice_plane(r, float(heights[k]))
            footprint = shapely.union_all(
                [
                    shapely.Polygon(at.to2d(tri))
                    for f in r.floors
                    for tri in tess.vertices[tess.triangles[tess.face_id == f]]
                ]
            ).buffer(1.0)
            for i, p in enumerate(pieces[k]):
                if p.intersection(footprint).area > OVERLAP_MM2:
                    on_floor.add((k, i))

    # Pockets through the stack: pieces joined to those they overlap in the next slice.
    index = {}
    for k, parts in enumerate(pieces):
        for i in range(len(parts)):
            index[(k, i)] = len(index)
    parent = list(range(len(index)))

    def root(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for k in range(len(pieces) - 1):
        for i, p in enumerate(pieces[k]):
            for j, q in enumerate(pieces[k + 1]):
                if p.intersects(q) and p.intersection(q).area > OVERLAP_MM2:
                    parent[root(index[(k, i)])] = root(index[(k + 1, j)])
    pockets: dict[int, dict[str, bool]] = {}
    for (k, i), n in index.items():
        mark = pockets.setdefault(root(n), {"anchor": False, "floor": False})
        mark["anchor"] |= touching[k][i]
        mark["floor"] |= (k, i) in on_floor
    wanted = {
        p
        for p, mark in pockets.items()
        if (mark["anchor"] or not touch_faces) and (mark["floor"] or not r.floors)
    }
    if not wanted and r.floors:
        # No pocket meets both the floor and a boss on its axis - the boss stands elsewhere: the
        # air over the floor alone.
        wanted = {p for p, mark in pockets.items() if mark["floor"]}
    air = []
    for k, parts in enumerate(pieces):
        kept = [p for i, p in enumerate(parts) if root(index[(k, i)]) in wanted]
        air.append(shapely.union_all(kept) if kept else slices.EMPTY)
    touches = {f: False for f in dict.fromkeys([*r.faces, *r.anchors])}
    for f in touches:
        touches[f] = any(pockets[p]["anchor"] for p in wanted) if f in touch_faces else bool(wanted)
    return Volume(
        recipe=r,
        heights=heights,
        step=step,
        air=air,
        kept_clear=kept_clear,
        pockets=len(wanted),
        left_out=len(pockets) - len(wanted),
        touches=touches,
        seconds=time.perf_counter() - started,
    )


def _region_box(r: Recipe) -> np.ndarray:
    frame = r.frame
    lo, hi = r.band
    ends = np.array([frame.point + lo * frame.axis, frame.point + hi * frame.axis])
    pad = r.radius_mm
    return np.concatenate([ends.min(axis=0) - pad, ends.max(axis=0) + pad])


def _boxes_meet(a: np.ndarray, b: np.ndarray) -> bool:
    return bool(np.all(a[:3] <= b[3:]) and np.all(b[:3] <= a[3:]))


def _reaches(k: keepouts.Keepout, r: Recipe) -> bool:
    """Whether a keep-out can reach into the region's cylinder: its box taken as a ball round its
    middle."""
    frame = r.frame
    middle = 0.5 * (k.box[:3] + k.box[3:])
    half = 0.5 * float(np.linalg.norm(k.box[3:] - k.box[:3]))
    s = float(frame.along(middle[None, :])[0])
    off = float(frame.radial(middle[None, :])[0])
    return off - half <= r.radius_mm and r.band[0] - half <= s <= r.band[1] + half
