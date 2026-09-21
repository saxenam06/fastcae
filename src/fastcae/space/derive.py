"""Define a part's design space - where metal may be added - from its CAD, its solver deck and its
drawing.

A design space is taken as defined: an input, like the CAD, kept in the project's folder
(:mod:`.store`). Where the engineer has brought none, these rules define it in their place - one
volume, the same rules on any part.

**Where metal could go**: a layer over the walls, ``k`` local wall thicknesses deep, outside and
inside alike, and the pockets between features a ball of ``c`` walls cannot enter. The inside is the
air the grid's edge cannot reach once every opening is capped by what sits in it - with the air
behind narrow openings, found by thickening every wall a cell or more.

**Kept clear**:

- every bore, whatever the evidence: what sits in it over its own length - a bearing - and past its
  ends what carries on - outward at its full radius, inward a shaft at 60 % of it, nothing past a
  register - and a collar one wall wide round its openings, outside the bore;
- round a face the deck or the drawing holds: what mates against it or fits over it, and a buffer
  one wall deep;
- in every hole the fastener, and beyond each open end its tool.

A face with only weak evidence - one that looks machined, one an unmentioned hole pattern opens
onto - keeps nothing clear: metal may go up to it.

What turns inside - gears, a planet carrier - is in neither the part's CAD nor its deck. The layer
over the inner walls stops ``k`` walls deep, which leaves the middle of the inside to it; the room
it really needs comes with the whole assembly in context.

**Where metal helps** (:mod:`.physics`), when the deck can be solved: the part under its loads, then
the design space pinned to how it moved - a value on every cell of it.
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage

from .. import cache
from ..features import FeatureKind
from . import interfaces as interface_rules
from . import sweeps
from .grid import (
    Samples,
    box_of,
    cell_of,
    distance_to,
    mask_of,
    part_field,
    sample_surface,
    signed_depth,
    thickness_behind,
)
from .model import KEPT_CLEAR, LABEL_WORDS, Label, Params, Space

LEAK_PROBE_CELLS = (1, 2, 3)
"""How much every wall is thickened, in cells, to find narrow openings from the inside out."""

LEAK_GROWTH = 1.05
"""The inside leaks if thickening the walls lets it grow by more than this."""

LID_CELLS = 2
"""How deep, in cells, what mates against a plane closes an opening when the inside is flooded. A
cover closes the opening its flange rims; the space in front of a face is not a lid, or a box whose
every face might mate would have no inside and no outside at all."""

CODE = ("geometry/field.py", "geometry/brep.py")

Say = Callable[[str], None] | None


class _Clock:
    """How long each stage took, said as it finishes."""

    def __init__(self, say: Say) -> None:
        self.say = say
        self.last = time.perf_counter()
        self.seconds: dict[str, float] = {}

    def lap(self, what: str, detail: str) -> None:
        now = time.perf_counter()
        self.seconds[what] = round(now - self.last, 1)
        self.last = now
        if self.say:
            self.say(f"{what}: {detail}")


def _exterior_air(free: np.ndarray) -> np.ndarray:
    """The air connected to the grid's edge."""
    labels, count = ndimage.label(free)
    if count == 0:
        return np.zeros(free.shape, bool)
    edge = np.zeros(count + 1, bool)
    for axis in range(free.ndim):
        for side in (0, -1):
            edge[np.unique(np.take(labels, side, axis=axis))] = True
    edge[0] = False
    out = edge[labels]
    del labels
    return out


def _buffer(
    grid, part: np.ndarray, samples: Samples, faces: list[int], radius_mm: float
) -> np.ndarray:  # type: ignore[no-untyped-def]
    """Air within ``radius_mm`` of the given faces."""
    on = np.isin(samples.face, np.asarray(faces))
    if not on.any() or radius_mm <= 0:
        return np.empty(0, np.int64)
    pts = samples.points[on]
    margin = radius_mm + 2 * grid.spacing_mm
    box = box_of(grid, pts.min(axis=0) - margin, pts.max(axis=0) + margin)
    shape = tuple(s.stop - s.start for s in box)
    seed = np.zeros(shape, bool)
    local = np.rint((pts - np.asarray(grid.origin)) / grid.spacing_mm).astype(int) - np.array(
        [s.start for s in box]
    )
    local = local[np.all((local >= 0) & (local < np.asarray(shape)), axis=1)]
    seed[local[:, 0], local[:, 1], local[:, 2]] = True
    if seed.size < 4_000_000:
        dist = ndimage.distance_transform_edt(~seed, sampling=grid.spacing_mm)
    else:
        dist = distance_to(seed, grid.spacing_mm)
    near = (dist <= radius_mm) & ~part[box]
    ii, jj, kk = np.nonzero(near)
    return np.ravel_multi_index(
        (ii + box[0].start, jj + box[1].start, kk + box[2].start), grid.shape
    )


def _add(mask: np.ndarray, flat: np.ndarray) -> None:
    if len(flat):
        mask.ravel()[flat] = True


def _field(extraction, params: Params, root: Path | None):  # type: ignore[no-untyped-def]
    tess = extraction.tess
    build = lambda: part_field(tess, params.spacing_mm, params.headroom_mm, extraction.cad_digest)  # noqa: E731
    if root is None:
        return build()
    key = cache.key_for(
        extraction.cad_digest, f"{params.spacing_mm:.6f}", f"{params.headroom_mm:.6f}", code=CODE
    )
    found, _ = cache.memoise(cache.entry(root, "space-field", key), build)
    return found


def _litres(mask: np.ndarray, h: float) -> float:
    return round(float(mask.sum()) * h**3 / 1e6, 1)


def derive(  # noqa: C901 - one pass through the rules reads better than a dozen indirections
    extraction,  # type: ignore[no-untyped-def]
    setup: Any = None,
    params: Params | None = None,
    root: Path | None = None,
    say: Say = print,
    physics: bool = True,
) -> Space:
    """The design space of an extracted part, by the rules. ``setup`` is the solver deck's setup,
    when the part has one: without it the rules run on the CAD and the drawing alone, and where
    metal helps is not found. ``root`` keeps the part's grid in that project's cache; ``say`` hears
    each stage as it finishes."""
    started = time.perf_counter()
    params = params or Params()
    clock = _Clock(say)
    tess, atlas, features = extraction.tess, extraction.atlas, extraction.features

    # The grid.
    field = _field(extraction, params, root)
    grid, part = field.grid, field.inside
    h = grid.spacing_mm
    air = ~part
    shape = grid.shape
    d_part = distance_to(part, h)
    clock.lap("the grid", f"{h:g} mm cells, {grid.n_cells / 1e6:.1f} M")

    # Wall thickness: twice the deepest point straight behind each point of the surface - a plate
    # reads as its thickness, a solid boss as its width, not its depth.
    samples = sample_surface(tess, h)
    depth = signed_depth(field)
    thickness = np.maximum(
        thickness_behind(grid, depth, samples.points, samples.normals, params.thickness_reach_mm),
        0.5 * h,
    )
    del depth
    typical = float(np.median(thickness))
    clock.lap("wall thickness", f"typical wall {typical:.0f} mm")

    # Interfaces: faces the deck loads or holds, the drawing tolerances or a held bolt clamps, every
    # bore, and faces with weak evidence only.
    found, counted = interface_rules.find(
        atlas,
        features,
        params,
        anchoring=extraction.anchoring if params.use_deck else None,
        setup=setup if params.use_deck else None,
        controlled=extraction.controlled,
    )
    out_cell, _ = cell_of(grid, samples.points + samples.normals * (0.75 * h))
    by_face: dict[int, list[int]] = defaultdict(list)
    for index, face in enumerate(samples.face):
        by_face[int(face)].append(index)
    for i in found:
        idx = [k for f in i.faces for k in by_face.get(f, [])]
        i.thickness_mm = round(float(np.median(thickness[idx])), 1) if idx else None
    bores = [i for i in found if i.kind == "bore"]
    held = [i for i in found if i.held]
    weak = sum(not i.kept_clear for i in found)
    clock.lap("interfaces", f"{len(held)} held, {len(bores)} bores, {weak} with weak evidence")

    # What sits round them. Kept clear: every bore's plug and collar, and round a held face what
    # mates against it, what fits over it and a buffer. What closes an opening when the inside is
    # flooded: what sits in a bore or fits over a boss, whole; what mates against any plane, as deep
    # as a cover; round a face with weak evidence, its buffer.
    bore = np.zeros(shape, bool)
    plane = np.zeros(shape, bool)
    ring = np.zeros(shape, bool)
    hole = np.zeros(shape, bool)
    buffer = np.zeros(shape, bool)
    lids = np.zeros(shape, bool)
    lo_t, hi_t = params.wall_range[0] * typical, params.wall_range[1] * typical
    for i in found:
        width = params.buffer * float(np.clip(i.thickness_mm or 2.0 * h, lo_t, hi_t))
        if i.kind == "bore":
            cells = sweeps.bore_plug(grid, part, tess, i)
            _add(bore, cells)
            _add(lids, cells)
            _add(bore, sweeps.bore_collar(grid, part, tess, i, width))
        elif i.kind == "plane":
            if i.held:
                _add(plane, sweeps.plane_neighbour(grid, part, tess, i))
            _add(lids, sweeps.plane_neighbour(grid, part, tess, i, depth_mm=LID_CELLS * h))
        elif i.kind == "boss":
            cells = sweeps.ring_neighbour(grid, part, tess, i)
            if i.held:
                _add(ring, cells)
            _add(lids, cells)
        around = _buffer(grid, part, samples, i.faces, width)
        if not i.held:
            _add(lids, around)
        elif i.kind != "bore":
            _add(buffer, around)
    holes = features.of_kind(FeatureKind.HOLE)
    for feature in holes:
        axis = np.asarray(feature.normal if feature.normal is not None else (0.0, 0.0, 1.0), float)
        radius = float(feature.metrics.get("radius_mm", 0.5 * (feature.diameter_mm or 0.0)))
        if radius <= 0:
            continue
        cells, _ = sweeps.hole_access(
            grid,
            part,
            tess,
            list(feature.face_ids),
            axis,
            np.asarray(feature.centroid, float),
            radius,
            params.hole_access_radius,
            params.hole_access_length,
        )
        _add(hole, cells)
    clock.lap(
        "what sits round them", f"{len(bores)} bores, {len(held)} held faces, {len(holes)} holes"
    )

    # The inside: flooded with the lids - and every swept cell takes the side of the air nearest it.
    caps = (lids | hole) & air
    del lids
    free = air & ~caps
    exterior = _exterior_air(free)
    enclosed = free & ~exterior
    _, nearest = distance_to(free, h, indices=True)
    cavity = enclosed | (caps & enclosed.ravel()[nearest.ravel()].reshape(shape))
    del nearest
    enclosed_cells = int(enclosed.sum())
    probes = []
    leak = np.zeros(shape, bool)
    for cells in LEAK_PROBE_CELLS:
        thick = ndimage.binary_dilation(part | caps, iterations=cells)
        inner = air & ~thick
        inner &= ~_exterior_air(inner)
        grown = ndimage.binary_dilation(inner, iterations=cells) & free
        probes.append({"mm": cells * h, "inside_L": round(float(grown.sum()) * h**3 / 1e6, 1)})
        if grown.sum() > LEAK_GROWTH * enclosed_cells:
            leak |= grown & ~enclosed
        del thick, inner, grown
    del caps, enclosed
    inside_air = cavity | leak
    outside_air = air & ~inside_air
    closed = "none" if not inside_air.any() else ("leaks" if leak.any() else "closed")
    clock.lap(
        "the inside",
        {
            "none": "no inside",
            "closed": f"closed, {_litres(cavity, h):.0f} L",
            "leaks": f"{_litres(cavity, h):.0f} L, {_litres(leak, h):.0f} L more behind narrow "
            "openings",
        }[closed],
    )

    # Beyond each bore: toward the outside what sits in it carries on at full radius; toward the
    # inside a shaft carries on through it, unless the bore is a register.
    flat_part = part.ravel()
    flat_free, flat_exterior = free.ravel(), exterior.ravel()
    carried = 0
    for i in bores:
        if i.axis is None or i.radius_mm is None or i.axis_point is None:
            continue
        ends = sweeps.bore_ends(tess, i)
        went = False
        for side, station in ((1, ends["stations"][1]), (-1, ends["stations"][0])):
            # Along the axis past the end, to the first air no sweep covers: which side is it on?
            reach = np.arange(1, int(max(3.0 * ends["radius"], 20 * h) / h) + 1) * h
            probe = (
                ends["point"][None, :] + ends["axis"][None, :] * (station + side * reach)[:, None]
            )
            cell, on = cell_of(grid, probe)
            cell = cell[on]
            hit_part = np.flatnonzero(flat_part[cell])
            open_air = np.flatnonzero(flat_free[cell])
            if not len(open_air) or (len(hit_part) and hit_part[0] < open_air[0]):
                continue
            if flat_exterior[cell[open_air[0]]]:
                share = 1.0
            elif ends["register"]:
                continue
            else:
                share = sweeps.SHAFT_SHARE
            _add(bore, sweeps.bore_beyond(grid, part, tess, i, side, share))
            went = True
        carried += went
    del free, exterior
    clock.lap("beyond each bore", f"{carried} of {len(bores)} carry on")

    # Where metal could go: a layer over every wall but a kept-clear interface's, outside and
    # inside, each as deep as its own number of local walls, and pockets between features.
    kept_faces = np.asarray(sorted({f for i in found if i.kept_clear for f in i.faces}), np.int64)
    free_wall = ~np.isin(samples.face, kept_faces)
    facing_out = outside_air.ravel()[out_cell] & free_wall
    facing_in = inside_air.ravel()[out_cell] & free_wall
    walls = facing_out | facing_in
    nominal = float(np.median(thickness[walls])) if walls.any() else typical
    lo_t, hi_t = params.wall_range[0] * nominal, params.wall_range[1] * nominal
    t_local = np.full(shape, nominal, np.float32)

    def layer(seeded: np.ndarray, k: float, side: np.ndarray, t_local: np.ndarray) -> np.ndarray:
        """The layer grown from the seeded samples, ``k`` local walls deep, on one side of the
        walls; each cell of that side takes the wall thickness of the wall nearest it."""
        seed_cells = out_cell[seeded]
        seed_t = np.clip(thickness[seeded], lo_t, hi_t)
        order = np.argsort(seed_cells, kind="stable")
        seed_cells, seed_t = seed_cells[order], seed_t[order]
        unique_cells, first, per_cell = np.unique(seed_cells, return_index=True, return_counts=True)
        if not len(unique_cells):
            return np.zeros(shape, bool)
        t_of_seed = np.add.reduceat(seed_t, first) / per_cell
        d_wall, nearest = distance_to(mask_of(grid, unique_cells), h, indices=True)
        t_near = (
            t_of_seed[np.searchsorted(unique_cells, nearest.ravel())]
            .reshape(shape)
            .astype(np.float32)
        )
        del nearest
        t_local[side] = t_near[side]
        out = side & (d_wall <= k * t_near)
        del d_wall, t_near
        return out

    panel = layer(facing_out, params.panel_layer, outside_air, t_local)
    panel |= layer(facing_in, params.inside_layer, inside_air, t_local)
    r_cap = params.headroom_mm - 2 * h
    r_local = np.minimum(params.pocket_reach * t_local, r_cap)
    del t_local
    pocket = np.zeros(shape, bool)
    for radius in sorted(r for r in params.pocket_ladder_mm if r <= r_cap):
        dilated = d_part <= radius
        closing = dilated & (distance_to(~dilated, h) > radius)
        pocket |= closing & air & (r_local >= radius)
        del dilated, closing
    del r_local, d_part
    candidate = panel | pocket
    clock.lap(
        "where metal could go",
        f"{_litres(panel, h):.0f} L layer, {_litres(pocket, h):.0f} L pockets",
    )

    # The design space: where metal could go, less what is kept clear.
    kept_clear = bore | plane | ring | hole | buffer
    design = candidate & ~kept_clear
    labels = np.full(shape, int(Label.OPEN_AIR), np.uint8)
    labels[inside_air] = int(Label.INSIDE)
    labels[design] = int(Label.DESIGN)
    taken = candidate & kept_clear
    for mask, label in (
        (buffer, Label.BUFFER),
        (hole, Label.HOLE_ACCESS),
        (ring, Label.RING),
        (plane, Label.MATING),
        (bore, Label.BORE),
    ):
        labels[taken & mask] = int(label)
    labels[part] = int(Label.PART)
    del bore, plane, ring, hole, buffer, kept_clear, taken, panel, pocket
    stats = {
        "design_L": _litres(design, h),
        "outside_L": _litres(design & outside_air, h),
        "inside_L": _litres(design & inside_air, h),
        "part_L": _litres(part, h),
        "the_inside": {
            "state": closed,
            "L": _litres(inside_air, h),
            "behind_narrow_openings_L": _litres(leak, h),
            "probes": probes,
        },
        "candidate_L": _litres(candidate, h),
        "kept_clear_L": {LABEL_WORDS[label]: _litres(labels == label, h) for label in KEPT_CLEAR},
        "wall_mm": round(nominal, 1),
        "wall_range_mm": [round(lo_t, 1), round(hi_t, 1)],
        "bores": len(bores),
        "bores_carried_on": carried,
        "held_faces": len(held),
        "weak_faces": weak,
        "holes": len(holes),
        "cells": int(grid.n_cells),
        "counted": counted,
    }
    del candidate, cavity, leak, inside_air, outside_air
    clock.lap("the design space", f"{stats['design_L']:.0f} L")
    space = Space(
        grid=grid,
        params=params,
        labels=labels,
        interfaces=found,
        stats=stats,
        source_digest=extraction.cad_digest,
    )

    # Where metal helps.
    if physics and setup is not None and extraction.anchoring and params.use_deck:
        from .physics import preview

        try:
            result = preview(grid, labels, tess, extraction.anchoring, setup, say=None)
            space.benefit = result["benefit"]
            values = space.benefit[design]
            space.stats["benefit"] = {
                **{k: v for k, v in result["stats"].items() if k != "loads"},
                "top_quarter": float(np.percentile(values, 75)) if len(values) else 0.0,
            }
            clock.lap(
                "where metal helps",
                f"largest movement {result['stats']['largest_displacement_mm']:.1f} mm",
            )
        except Exception as error:  # noqa: BLE001 - a preview that fails leaves the space standing
            space.stats["benefit"] = {"failed": f"{type(error).__name__}: {error}"}
            clock.lap("where metal helps", f"failed: {type(error).__name__}")
    space.stats["seconds"] = clock.seconds
    space.seconds = time.perf_counter() - started
    return space
