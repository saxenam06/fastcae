"""Ribs composed into a part's field.

**Inside a window.** Everything about where ribs can go that does not depend on the design - the
part's exact distance out past the band, which way its surface faces, where rib material is allowed
and which cells are protected - is worked out once for a window of the grid and kept. A design then
only evaluates its own ribs, and only near them. Every other cell is the base, untouched, which is
what lets the design be contoured by splicing its windows into the base's contour.

**The part's distance, exactly, past the band.** The base field stores distance only a few voxels
out; a fillet of radius R needs it out to 2R. Inside a window it is computed again from the
tessellation by the same exact point-to-triangle scan the base was built with, so where a rib
changes nothing, the value is bit-for-bit the base's.

**Ribs are trimmed to where they may be.** A formation's lines run past a zone's walls on purpose;
the window says which cells are the zone's own air, and a rib exists only there and a voxel into the
metal around it, so the join has no gap and nothing pokes out the far side of a wall. Where a zone's
arc ends in open air, ribs are cut there by the arc's own planes rather than by voxels.

**Protected cells come back.** After blending, every protected cell is given its base value again,
so a protected surface is exactly the baseline's and a check can prove it by comparing cells.

**The edge of the grid is always outside.** Nothing is ever made solid on the grid's outermost
layer, so every design's surface closes - a surface that reached the edge would end there, open. A
rib that gets that far has left the part or outgrown the grid; the cells it was held back from are
kept, and a check rejects the design with where.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from ..geometry.brep import Tessellation
from .field import CODE as FIELD_CODE
from .field import Field, Grid, _unsigned_distance
from .formations import Region
from .ribs import round_union

# What a stored window depends on besides its inputs.
CODE_COMPOSE = (*FIELD_CODE, "generate/compose.py", "generate/formations.py", "generate/ribs.py")


@dataclass
class Window:
    """Everything about a stretch of the grid that a design does not change.

    Arrays are over the window's own cells, in its grid's order. ``part`` is the signed distance to
    the part, exact out to ``margin_mm`` and clamped there. Which base cell a window cell is, and
    the part's normal there, follow from that and are worked out for the cells asked about only -
    over a whole window on the part in ``assets/`` they would be four hundred megabytes a zone.
    """

    grid: Grid
    first: tuple[int, int, int]
    base_shape: tuple[int, int, int]
    part: np.ndarray
    allowed: np.ndarray
    protected: np.ndarray
    margin_mm: float
    region: Region | None = None

    def samples_of(self, cells: np.ndarray) -> np.ndarray:
        """The flat base-grid index of each of the given window cells."""
        i, j, k = np.unravel_index(np.asarray(cells, dtype=np.int64), self.grid.shape)
        return np.ravel_multi_index(
            (i + self.first[0], j + self.first[1], k + self.first[2]), self.base_shape
        ).astype(np.int64)

    def normal_at(self, cells: np.ndarray) -> np.ndarray:
        """The part's unit normal at each of the given window cells, by central differences."""
        shape = np.asarray(self.grid.shape)
        index = np.stack(
            np.unravel_index(np.asarray(cells, dtype=np.int64), self.grid.shape), axis=1
        )
        part = self.part.reshape(self.grid.shape)
        grad = np.empty((index.shape[0], 3))
        for axis in range(3):
            up, down = index.copy(), index.copy()
            up[:, axis] = np.minimum(up[:, axis] + 1, shape[axis] - 1)
            down[:, axis] = np.maximum(down[:, axis] - 1, 0)
            span = (up[:, axis] - down[:, axis]).clip(min=1) * self.grid.spacing_mm
            grad[:, axis] = (
                part[tuple(up.T)].astype(np.float64) - part[tuple(down.T)].astype(np.float64)
            ) / span
        length = np.linalg.norm(grad, axis=1, keepdims=True)
        return np.divide(grad, length, out=np.zeros_like(grad), where=length > 1e-12)

    def __getstate__(self) -> dict:
        state = dict(self.__dict__)
        state["allowed"] = np.packbits(self.allowed)
        state["protected"] = np.packbits(self.protected)
        return state

    def __setstate__(self, state: dict) -> None:
        count = state["grid"].n_cells
        state["allowed"] = np.unpackbits(state["allowed"], count=count).astype(bool)
        state["protected"] = np.unpackbits(state["protected"], count=count).astype(bool)
        self.__dict__.update(state)


@dataclass
class Composition:
    """A design's field, and which of its samples differ from the base's.

    The rest is what the checks read: the window cells a rib reached, the part's and the ribs'
    distances there, which rib was nearest, and the protected cells where a fillet was cut short.
    """

    field: Field
    changed: np.ndarray
    touched: np.ndarray | None = None
    part: np.ndarray | None = None
    ribs: np.ndarray | None = None
    nearest: np.ndarray | None = None
    clipped: np.ndarray | None = None
    off_grid: np.ndarray | None = None


def margin_for(base: Field, radius_mm: float) -> float:
    """How far past a rib its fillet and the band can reach: twice the radius, where surfaces face
    each other, plus the band and a voxel."""
    return 2.0 * radius_mm + base.reach_mm + base.grid.spacing_mm


def window_between(
    base: Field,
    tess: Tessellation,
    lo: np.ndarray,
    hi: np.ndarray,
    margin_mm: float,
    allowed: np.ndarray | None = None,
    protected_faces: set[int] | dict[int, float] | None = None,
    clearance_mm: float = 0.0,
    region: Region | None = None,
    around: list[tuple[np.ndarray, np.ndarray]] | None = None,
) -> Window:
    """A window over the box ``lo`` to ``hi``, grown by the margin and snapped to the lattice.

    ``protected_faces`` are held as they are within a clearance of them: ``clearance_mm`` for every
    one, or each its own. A face held at none is only not crossed, and a rib may meet it.

    ``around``, when given, is the boxes of what will be composed in it - each rib's: the part's
    distance is exact within the margin of them, where a fillet reads it, and clamped elsewhere, so
    ribs spread over a whole part pay for the part near them, not for the box round them all."""
    grid = base.grid
    origin = np.asarray(grid.origin)
    last_index = np.asarray(grid.shape) - 1
    first = np.clip(
        np.floor((lo - margin_mm - origin) / grid.spacing_mm).astype(int), 0, last_index
    )
    last = np.clip(np.ceil((hi + margin_mm - origin) / grid.spacing_mm).astype(int), 0, last_index)
    window = Grid(
        origin=tuple(float(v) for v in origin + first * grid.spacing_mm),
        spacing_mm=grid.spacing_mm,
        shape=tuple(int(v) for v in last - first + 1),
    )
    protected = np.zeros(window.n_cells, dtype=bool)
    if protected_faces:
        clearance_of = (
            protected_faces
            if isinstance(protected_faces, dict)
            else dict.fromkeys(protected_faces, clearance_mm)
        )
        for clearance in sorted({c for c in clearance_of.values() if c > 0.0}):
            faces = {f for f, c in clearance_of.items() if c == clearance}
            # Strictly inside: a cell out of reach comes back clamped to exactly the clearance.
            near = _part_distance(tess, window, clearance, faces=faces)
            protected |= near < clearance
    if allowed is None:
        allowed = np.ones(window.n_cells, dtype=bool)
    out = Window(
        grid=window,
        first=tuple(int(v) for v in first),
        base_shape=tuple(int(v) for v in grid.shape),
        part=np.empty(0, dtype=np.float32),
        allowed=allowed,
        protected=protected,
        margin_mm=margin_mm,
        region=region,
    )
    unsigned = _part_distance(tess, window, margin_mm, around=around)
    solid = base.inside.ravel()[out.samples_of(np.arange(window.n_cells))]
    out.part = np.where(solid, -unsigned, unsigned).astype(np.float32)
    return out


def window_around(
    base: Field,
    tess: Tessellation,
    ribs: list,
    radius_mm: float,
    protected: np.ndarray | None = None,
) -> Window:
    """A window just big enough for ``ribs``, allowing them anywhere. For ribs outside any zone."""
    margin = margin_for(base, radius_mm)
    lo = np.min([rib.bounds()[0] for rib in ribs], axis=0)
    hi = np.max([rib.bounds()[1] for rib in ribs], axis=0)
    window = window_between(base, tess, lo, hi, margin)
    if protected is not None:
        window.protected = np.isin(window.samples_of(np.arange(window.grid.n_cells)), protected)
    return window


def compose(
    base: Field, window: Window, ribs: list, radius_mm: float | Sequence[float], shift=None
) -> Composition:
    """``base`` with ``ribs`` joined to it by root fillets of ``radius_mm``, inside ``window`` - one
    radius for every rib, or each rib's own: ribs of different blocks ask for different radii.

    ``shift``, when given, says how far the design has moved the part's surface out at any points
    - faces thickened or thinned - so ribs are filleted to the surface where it now is."""
    if not ribs:
        return Composition(field=base, changed=np.empty(0, dtype=np.int64))

    margin = window.margin_mm
    points_of = window.grid.centres
    radii = np.broadcast_to(np.asarray(radius_mm, dtype=np.float64), (len(ribs),))

    # The ribs, as one solid: joined to each other where they cross, rounded to the smaller of
    # their radii. Which rib is nearest is kept, because the fillet against the part is that rib's
    # own - its normal, and its radius.
    ribs_distance = np.full(window.grid.n_cells, np.inf)
    nearest = np.full(window.grid.n_cells, -1, dtype=np.int32)
    for index, rib in enumerate(ribs):
        cells = _cells_near(window, rib, margin)
        cells = cells[window.allowed[cells]]
        if not cells.size:
            continue
        d = rib.distance(points_of(cells))
        current = ribs_distance[cells]
        before = nearest[cells]
        pair = np.minimum(radii[index], radii[np.maximum(before, 0)])
        nearest[cells] = np.where(d < current, index, before)
        ribs_distance[cells] = np.where(np.isinf(current), d, _crossing(current, d, pair))

    reached = np.flatnonzero(np.isfinite(ribs_distance))
    if window.region is not None and reached.size:
        cut = _arc_distance(window.region, points_of(reached))
        ribs_distance[reached] = np.maximum(ribs_distance[reached], cut)

    touched = np.flatnonzero(ribs_distance < margin)
    a = window.part[touched].astype(np.float64)
    if shift is not None and touched.size:
        a = a - shift(points_of(touched))
    b = ribs_distance[touched]

    # The blend acts only within 2R of both; everywhere else it is the plain union and needs no
    # normal. Inside that strip the rib's normal is its own, exact - a finite difference across the
    # grid would reach past the rib's root into the part and tilt it. R is the nearest rib's.
    radius_at = radii[nearest[touched]]
    ribs_normal = np.zeros((touched.size, 3))
    strip = np.flatnonzero((a < 2.0 * radius_at) & (b < 2.0 * radius_at))
    owner = nearest[touched[strip]]
    for index in np.unique(owner):
        rows = strip[owner == index]
        ribs_normal[rows] = ribs[index].normal(points_of(touched[rows]))

    value = round_union(a, window.normal_at(touched), b, ribs_normal, radius_at)
    solid = value < 0.0
    held = window.protected[touched]
    clipped = np.empty(0, dtype=np.int64)
    if held.any():
        samples = window.samples_of(touched[held])
        was_solid = base.inside.ravel()[samples]
        clipped = touched[held][solid[held] & ~was_solid]
        value[held] = base.at(samples)
        solid[held] = was_solid

    samples = window.samples_of(touched)
    edge = _on_grid_edge(samples, base.grid.shape)
    off_grid = np.empty(0, dtype=np.int64)
    if edge.any():
        was_solid = base.inside.ravel()[samples[edge]]
        off_grid = touched[edge][solid[edge] & ~was_solid]
        value[edge] = base.at(samples[edge])
        solid[edge] = was_solid

    composition = _splice(base, samples, value.astype(np.float32), solid)
    composition.touched = touched
    composition.part = a
    composition.ribs = b
    composition.nearest = nearest[touched]
    composition.clipped = clipped
    composition.off_grid = off_grid
    return composition


def _on_grid_edge(samples: np.ndarray, shape: tuple[int, int, int]) -> np.ndarray:
    """Which of the given flat samples lie on the grid's outermost layer."""
    index = np.unravel_index(samples, shape)
    edge = np.zeros(samples.shape, dtype=bool)
    for axis in range(3):
        edge |= (index[axis] == 0) | (index[axis] == shape[axis] - 1)
    return edge


def _crossing(x: np.ndarray, y: np.ndarray, radius: float | np.ndarray) -> np.ndarray:
    """Where two ribs cross: their union, rounded to ``radius``; exact where either is far."""
    u = np.maximum(radius - x, 0.0)
    w = np.maximum(radius - y, 0.0)
    blended = np.maximum(radius, np.minimum(x, y)) - np.hypot(u, w)
    return np.where((x >= radius) | (y >= radius), np.minimum(x, y), blended)


def _cells_near(window: Window, rib, margin: float) -> np.ndarray:
    """Window cells within ``margin`` of a rib's box, as window-local flat indices."""
    lo, hi = rib.bounds(margin_mm=margin)
    origin = np.asarray(window.grid.origin)
    spacing = window.grid.spacing_mm
    shape = np.asarray(window.grid.shape)
    first = np.clip(np.floor((lo - origin) / spacing).astype(int), 0, shape - 1)
    last = np.clip(np.ceil((hi - origin) / spacing).astype(int), 0, shape - 1)
    if np.any(last < first):
        return np.empty(0, dtype=np.int64)
    axes = [np.arange(first[a], last[a] + 1) for a in range(3)]

    # A long rib at an angle has a box far bigger than itself. Its plan - the rib seen along its
    # pull - rules most of the box out in two dimensions, before any cell in three is looked at.
    up = np.abs(np.asarray(rib.pull, dtype=float))
    along = int(np.argmax(up))
    if up[along] > 0.999 and hasattr(rib, "plan_near"):
        other = [a for a in range(3) if a != along]
        grid2 = np.stack(np.meshgrid(axes[other[0]], axes[other[1]], indexing="ij"), axis=-1)
        grid2 = grid2.reshape(-1, 2)
        world = np.zeros((grid2.shape[0], 3))
        world[:, other[0]] = origin[other[0]] + grid2[:, 0] * spacing
        world[:, other[1]] = origin[other[1]] + grid2[:, 1] * spacing
        world[:, along] = (lo[along] + hi[along]) / 2.0
        keep = grid2[rib.plan_near(world, margin + spacing)]
        if not keep.size:
            return np.empty(0, dtype=np.int64)
        column = np.repeat(keep, axes[along].size, axis=0)
        level = np.tile(axes[along], keep.shape[0])
        index = np.zeros((column.shape[0], 3), dtype=np.int64)
        index[:, other[0]] = column[:, 0]
        index[:, other[1]] = column[:, 1]
        index[:, along] = level
        return np.ravel_multi_index(index.T, window.grid.shape).astype(np.int64)

    mesh = np.meshgrid(*axes, indexing="ij")
    return np.ravel_multi_index(tuple(m.ravel() for m in mesh), window.grid.shape).astype(np.int64)


def _arc_distance(region: Region, points: np.ndarray) -> np.ndarray:
    """Signed distance to the wedge a zone's arc spans, measured in the plane square to its axis."""
    if region.span_deg >= 360.0:
        return np.full(points.shape[0], -np.inf)
    origin, e1, e2, axis = region.frame()
    p = points - origin
    x, y = p @ e1, p @ e2
    inside = region.contains(x, y, reach=math.inf)
    distance = np.full(points.shape[0], np.inf)
    for angle in (region.theta_from_deg, region.theta_from_deg + region.span_deg):
        u = np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])
        along = x * u[0] + y * u[1]
        across = np.abs(x * u[1] - y * u[0])
        distance = np.minimum(distance, np.where(along >= 0.0, across, np.hypot(x, y)))
    return np.where(inside, -distance, distance)


def _part_distance(
    tess: Tessellation,
    window: Grid,
    reach: float,
    faces: set[int] | None = None,
    around: list[tuple[np.ndarray, np.ndarray]] | None = None,
) -> np.ndarray:
    """Unsigned distance from each window sample to the part (or some of its faces), exactly, out
    to ``reach`` and clamped there - or, given the boxes ``around``, exactly within ``reach`` of
    them and clamped beyond: only the facets that near can matter there."""
    lo = np.asarray(window.origin) - reach
    hi = np.asarray(window.origin) + (np.asarray(window.shape) - 1) * window.spacing_mm + reach
    corners = tess.vertices[tess.triangles]
    top, bottom = corners.max(axis=1), corners.min(axis=1)
    keep = np.all(top >= lo, axis=1) & np.all(bottom <= hi, axis=1)
    if faces is not None:
        keep &= np.isin(tess.face_id, list(faces))
    if around:
        # A cell within reach of a box has its nearest facets within twice the reach of it.
        near = np.zeros(len(keep), dtype=bool)
        for box_lo, box_hi in around:
            near |= np.all(top >= np.asarray(box_lo) - 2.0 * reach, axis=1) & np.all(
                bottom <= np.asarray(box_hi) + 2.0 * reach, axis=1
            )
        keep &= near
    if not keep.any():
        return np.full(window.n_cells, reach)
    local = Tessellation(
        vertices=tess.vertices,
        triangles=tess.triangles[keep],
        face_id=tess.face_id[keep],
        face_ids=tess.face_ids,
        deflection_mm=tess.deflection_mm,
        angle_deg=tess.angle_deg,
        faces_without_triangles=[],
    )
    distance = _unsigned_distance(local, window, reach).ravel().astype(np.float64)
    return np.minimum(distance, reach)


def _unit_gradient(values: np.ndarray, spacing: float) -> np.ndarray:
    grad = np.stack(np.gradient(values, spacing), axis=-1).reshape(-1, 3)
    length = np.linalg.norm(grad, axis=1, keepdims=True)
    return np.divide(grad, length, out=np.zeros_like(grad), where=length > 1e-12)


def _splice(base: Field, samples: np.ndarray, value: np.ndarray, solid: np.ndarray) -> Composition:
    """The base with the given samples replaced, and which of them actually differ."""
    reach = base.reach_mm
    held = np.abs(value) <= reach
    stored = np.where(held, value, np.where(solid, -reach, reach)).astype(np.float32)
    was = base.at(samples)
    was_solid = base.inside.ravel()[samples]
    differs = (stored != was) | (solid != was_solid)
    changed = np.sort(samples[differs])

    samples, value, solid, held = samples[differs], value[differs], solid[differs], held[differs]
    inside = base.inside.copy()
    inside.ravel()[samples] = solid

    outside = ~np.isin(base.band_index, samples)
    band_index = np.concatenate([base.band_index[outside], samples[held].astype(np.int32)])
    band_mm = np.concatenate([base.band_mm[outside], value[held]])
    order = np.argsort(band_index, kind="stable")

    field = Field(
        grid=base.grid,
        band_index=band_index[order],
        band_mm=band_mm[order],
        inside=inside,
        reach_mm=reach,
        headroom_mm=base.headroom_mm,
        source_digest=base.source_digest,
    )
    return Composition(field=field, changed=changed)
