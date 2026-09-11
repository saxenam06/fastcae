"""A design: a parameter vector against a base geometry, and the field it produces.

**Nothing here stores geometry.** A design is a content digest and a few numbers, and the field is
regenerated from them. Identical numbers give an identical field, which is the property the whole
campaign rests on - two runs that differ have to differ because the design differs, not because
something was rebuilt slightly differently in between.

**A parameter is evaluated where it can reach, and nowhere else.** A rib touches the cells inside
its own bounding box grown by the blend radius and the band; on the part in ``assets/`` that is
tens of thousands of cells against nine million. Moving a dial therefore costs what the rib costs,
not what the part costs, which is what makes apply-and-see possible at all.

**The blend cannot outreach the band.** Beyond the band a cell knows only which side of the surface
it is on, so a blend radius larger than the band's reach would be blending against a clamped
number. It is capped rather than trusted.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from .field import Field, Grid
from .offset import Patch, weight
from .primitives import Slab, smooth_min

COHERENT = 0.75
"""How much of one direction a face selection needs before a rib may stand on it.

The area-weighted mean normal divided by the total area: one for a flat selection, falling towards
zero as it wraps. Three quarters admits a shallow panel with its root fillets - the ordinary case -
and rejects a selection that has gone round a corner, where "out of the face" is no longer a single
direction and a rib would be placed somewhere nobody pointed at.
"""


@dataclass(frozen=True)
class Parameter:
    """One lever on the geometry, and the range it may move over.

    A rib for now. The *placement* is authored once - which face it sits on, which way it runs, how
    thick it is - and the **height is the dial**, because that is the quantity a campaign sweeps and
    everything else is a decision about what the rib is rather than how much of it there is.
    """

    id: str
    name: str
    """What a person called it. Domain vocabulary, and the only place it is allowed to enter."""

    slab: Slab
    """The rib at zero height. Its own height is ignored; :meth:`at` supplies it."""

    low_mm: float
    high_mm: float
    default_mm: float

    host_face_ids: tuple[int, ...] = ()
    """The faces this was authored on. Kept so a person can see what a parameter is attached to."""

    def at(self, value_mm: float) -> Slab:
        return replace(self.slab, height_mm=float(np.clip(value_mm, self.low_mm, self.high_mm)))

    def clamp(self, value_mm: float) -> float:
        return float(np.clip(value_mm, self.low_mm, self.high_mm))


@dataclass(frozen=True)
class Design:
    """A point in the design space. Two numbers and a digest, never a mesh."""

    base_digest: str
    values: tuple[float, ...]

    def key(self) -> str:
        """A short stable name. Same design, same name, on any machine."""
        return "-".join(f"{value:.4f}" for value in self.values) or "base"


def apply(
    base: Field,
    parameters: list[Parameter],
    values: list[float] | tuple[float, ...],
    blend_mm: float,
) -> Field:
    """The base field with every parameter unioned into it.

    Returns a field of the same grid - that is the point of the grid being fixed - so anything that
    reads one reads the other, and two designs are comparable cell for cell.
    """
    if not parameters:
        return base
    if len(values) != len(parameters):
        raise ValueError(f"{len(parameters)} parameters but {len(values)} values")

    blend = min(float(blend_mm), base.reach_mm)
    slabs = [parameter.at(value) for parameter, value in zip(parameters, values, strict=True)]
    slabs = [slab for slab in slabs if slab.height_mm > 0.0]
    if not slabs:
        return base

    _refuse_to_clip(base, slabs)

    # The evaluation margin may run off the edge of the grid and it does not matter - out there the
    # band simply does not extend, and it is nowhere near the part. The *shape* running off the
    # edge is what matters, and that is what was checked.
    cells = _cells_within(base.grid, slabs, margin_mm=blend + base.reach_mm)
    if cells.size == 0:
        return base

    points = base.grid.centres(cells)
    distance = base.at(cells).astype(np.float64)
    for slab in slabs:
        distance = smooth_min(distance, slab.distance(points), blend)

    inside = base.inside.copy()
    # The sign *bit*, not "less than zero". A cell landing exactly on the surface is stored as
    # negative zero by the base field, and `-0.0 < 0` is False - so testing the value would flip
    # such a cell from solid to hollow and report a rib as having removed material.
    inside.ravel()[cells] = np.signbit(distance)

    index, band = _splice(base, cells, distance)
    return Field(
        grid=base.grid,
        band_index=index,
        band_mm=band,
        inside=inside,
        reach_mm=base.reach_mm,
        headroom_mm=base.headroom_mm,
        source_digest=base.source_digest,
        key="",
    )


def _refuse_to_clip(base: Field, slabs: list[Slab]) -> None:
    """Raise rather than let the edge of the grid trim a design.

    The grid is fixed, so a rib taller than the space above the part simply stops at the lattice
    boundary - and what that looks like from outside is a dial that works up to a point and then
    does nothing. It cost an afternoon to find that way, so it is an error now: the field carries
    how much headroom it was built with, and a parameter either fits or says it does not.
    """
    origin = np.asarray(base.grid.origin)
    far = origin + (np.asarray(base.grid.shape) - 1) * base.grid.spacing_mm

    for slab in slabs:
        low, high = slab.bounds()
        if (low < origin).any() or (high > far).any():
            raise ValueError(
                f"a {slab.height_mm:.1f} mm parameter reaches outside the field, which was built "
                f"with {base.headroom_mm:.1f} mm of headroom. Rebuild the field with more, or ask "
                f"for less."
            )


def _cells_within(grid: Grid, slabs: list[Slab], margin_mm: float) -> np.ndarray:
    """Flat indices of every cell any of these shapes can reach, ascending and without repeats."""
    shape = np.asarray(grid.shape)
    origin = np.asarray(grid.origin)
    blocks: list[np.ndarray] = []

    for slab in slabs:
        low, high = slab.bounds(margin_mm)
        first = np.clip(np.floor((low - origin) / grid.spacing_mm).astype(np.int64), 0, shape - 1)
        last = np.clip(np.ceil((high - origin) / grid.spacing_mm).astype(np.int64), 0, shape - 1)
        if (last < first).any():
            continue
        i, j, k = (np.arange(first[axis], last[axis] + 1) for axis in range(3))
        blocks.append(
            np.ravel_multi_index(
                tuple(axis.ravel() for axis in np.meshgrid(i, j, k, indexing="ij")), grid.shape
            )
        )

    if not blocks:
        return np.zeros(0, dtype=np.int64)
    # Unique because two parameters can overlap, and a cell listed twice would be spliced into the
    # band twice - which breaks the sorted-and-unique invariant everything downstream assumes.
    return np.unique(np.concatenate(blocks))


def _splice(base: Field, cells: np.ndarray, distance: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The base band with the re-evaluated cells swapped in.

    Cells join and leave the band as material moves: a cell that was well outside is now beside a
    rib, and one that was beside the surface is now buried. So the old entries in the region go and
    the new ones take their place, rather than being written over in situ.
    """
    replaced = np.isin(base.band_index, cells.astype(base.band_index.dtype))
    kept_index = base.band_index[~replaced]
    kept_mm = base.band_mm[~replaced]

    near = np.abs(distance) <= base.reach_mm
    fresh_index = cells[near].astype(base.band_index.dtype)
    fresh_mm = distance[near].astype(np.float32)

    index = np.concatenate([kept_index, fresh_index])
    band = np.concatenate([kept_mm, fresh_mm])
    order = np.argsort(index, kind="stable")
    return index[order], band[order]


@dataclass(frozen=True)
class Displacement:
    """Which cells a face selection moves, and how much each of them belongs to it.

    Separated from the height on purpose, because the mask is the expensive half and the height is
    the half that moves. Two nearest-point queries over a few hundred thousand cells cost about a
    second; once they are done, every value of the dial is one multiply and one subtract over the
    same cells. That is the difference between a control you drag and a control you wait for.
    """

    cells: np.ndarray
    weight: np.ndarray
    ramp_mm: float
    at: np.ndarray
    """Where each cell already sits in the base field's band.

    The offset only ever touches cells that are in the band, so the band's *membership* never
    changes - only its values do. Knowing the positions turns the splice a rib needs, which merges
    two sorted index sets, into a write into a copy. It is the difference between seconds and
    milliseconds on a selection covering half a square metre.
    """


def plan_offset(base: Field, patch: Patch, ramp_mm: float) -> Displacement:
    """Work out the mask once, for a selection that is about to be put on a dial.

    Only cells **in the band** are candidates. Everything else is either deep inside the part or
    well outside it, and cannot change sides: the field stores a clamped reach out there, and the
    displacement is capped at that same reach, so the sign it already has is the sign it keeps.
    The band is a thin shell, so this is the difference between a few hundred thousand cells and
    the tens of millions in the selection's bounding box.
    """
    reach = base.reach_mm
    ramp = min(max(float(ramp_mm), 0.0), reach)

    low, high = patch.bounds(reach + ramp + reach)
    coordinates = np.unravel_index(base.band_index, base.grid.shape)
    origin, spacing = np.asarray(base.grid.origin), base.grid.spacing_mm

    keep = np.ones(base.band_index.size, dtype=bool)
    for axis in range(3):
        centre = origin[axis] + coordinates[axis] * spacing
        keep &= (centre >= low[axis]) & (centre <= high[axis])

    where = np.flatnonzero(keep)
    cells = base.band_index[where]
    if cells.size == 0:
        return Displacement(cells=cells, weight=np.zeros(0), ramp_mm=ramp, at=where)
    mask = weight(patch, base.grid.centres(cells), ramp)
    return Displacement(cells=cells, weight=mask, ramp_mm=ramp, at=where)


def offset_faces(base: Field, plan: Displacement, height_mm: float) -> Field:
    """Move a set of CAD faces along their own normal, as a field operation.

    The whole operator is one subtraction. What the field stores *is* signed distance, so taking a
    constant off it moves the surface by that constant along its own gradient - which is the surface
    normal, at every point, without anybody computing one. Make the constant a mask and only the
    selected faces move::

        phi_new = phi_base - height * weight

    Positive height adds material, negative removes it, and both are the same line of code. On a
    curved face the offset follows the curvature; where the mask ramps, the surface ramps with it,
    and the join blends itself.

    This is what the first rib could not do. A slab has to guess a footprint and a direction from
    the selection, so picking a panel stood a thin wall along one edge of it. Here the faces that
    were picked are exactly the faces that move.

    **Bounded by the band.** Outside the band a cell knows only its side, not its distance, so
    subtracting from a clamped value would drag material out of a region that has no measurement in
    it. The height is capped at the band's reach and the cap is the caller's to report.
    """
    reach = base.reach_mm
    height = float(np.clip(height_mm, -reach, reach))
    if height == 0.0 or plan.cells.size == 0:
        return base

    distance = np.clip(
        base.band_mm[plan.at].astype(np.float64) - height * plan.weight, -reach, reach
    )

    inside = base.inside.copy()
    inside.ravel()[plan.cells] = np.signbit(distance)

    band = base.band_mm.copy()
    band[plan.at] = distance
    return Field(
        grid=base.grid,
        band_index=base.band_index,
        band_mm=band,
        inside=inside,
        reach_mm=reach,
        headroom_mm=base.headroom_mm,
        source_digest=base.source_digest,
        key="",
    )


def host_from(
    vertices: np.ndarray,
    triangles: np.ndarray,
    face_id: np.ndarray,
    wanted: set[int],
) -> tuple[np.ndarray, np.ndarray]:
    """The points of a face selection, and the way it faces.

    The direction comes from the **triangles**, not from the CAD face's analytic normal: the
    tessellation is wound coherently outward, so an area-weighted sum of its triangle normals
    points out of the material for any surface at all - including the tori, cones and b-splines
    that have no analytic normal to ask.
    """
    mine = np.isin(face_id, np.fromiter(wanted, dtype=face_id.dtype, count=len(wanted)))
    if not mine.any():
        raise ValueError("that selection has no triangles on it")

    corners = triangles[mine]
    a, b, c = vertices[corners[:, 0]], vertices[corners[:, 1]], vertices[corners[:, 2]]

    # Unnormalised, so the sum is area-weighted: a large face should decide the direction, not a
    # sliver that happens to sit at an angle.
    weighted = np.cross(b - a, c - a)
    facing = weighted.sum(axis=0)
    length = float(np.linalg.norm(facing))

    # How much of a single direction the selection has: one if it is flat, falling to zero as it
    # wraps. A selection that wraps has no "out", and averaging it anyway produces a direction that
    # points into the part as readily as out of it - which is how a rib ends up lying along a wall
    # instead of standing on it. Refusing is the only honest answer.
    total_area = float(np.linalg.norm(weighted, axis=1).sum())
    coherence = length / total_area if total_area > 1e-12 else 0.0
    if coherence < COHERENT:
        raise ValueError(
            "those faces point too many different ways for a rib to stand on them - "
            "material is added straight out of the face, so the selection needs one direction"
        )

    return vertices[np.unique(corners)], facing / length


def rib_on(
    field: Field,
    vertices: np.ndarray,
    normal: np.ndarray,
    thickness_mm: float,
    span: float = 0.9,
) -> Slab:
    """A rib laid along the longest direction of a set of faces, standing on them.

    The first way to author one, and the least a person has to say: pick a face, and the rib runs
    the way that face runs. Its length is a fraction of the host rather than all of it, because a
    rib that reaches exactly to the edge of its host is a rib whose end is a guess.

    ``normal`` points out of the material, so the rib rises the way the surface faces.
    """
    if vertices.shape[0] < 3:
        raise ValueError("a rib needs a host with some area to stand on")

    centre = vertices.mean(axis=0)
    up = normal / np.linalg.norm(normal)

    # The longest direction *in the surface*: the leading axis of the host once its normal is
    # projected out. On a long flat land that is along the land, which is where a rib goes.
    flat = vertices - centre
    flat = flat - np.outer(flat @ up, up)
    _, _, directions = np.linalg.svd(flat, full_matrices=False)
    along = directions[0]

    reach = float(np.abs(flat @ along).max())
    return Slab(
        origin=tuple(float(v) for v in centre),
        along=tuple(float(v) for v in along),
        up=tuple(float(v) for v in up),
        length_mm=2.0 * reach * span,
        thickness_mm=float(thickness_mm),
        height_mm=0.0,
        round_mm=min(float(thickness_mm) / 4.0, field.grid.spacing_mm),
    )
