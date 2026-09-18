"""Derive a part's design space from its CAD and its solver deck.

The steps, each a rule that holds for any part, and each reporting what it produced as it finishes:

1. **Grid.** The part sampled on one grid; inside and outside are exact on a watertight surface.
2. **Wall thickness** at points spread over the whole surface: twice the deepest point straight
   behind the point - a plate reads as its thickness, a solid boss as its width, not its depth.
3. **Interfaces** (:mod:`.interfaces`): faces the deck loads or holds, the drawing tolerances, a
   held hole opens onto - frozen; faces that only look machined, planes an unmentioned hole
   pattern opens onto, bores the deck does not mention - asked about.
4. **What occupies the space round them** (:mod:`.sweeps`): what sits in a bore, what mates against
   a plane, a fastener and its tool in and beyond a hole, what fits over a boss, and a buffer round
   every frozen face. Frozen interfaces forbid it; doubtful ones mark it as waiting.
5. **The inside.** Openings capped by those sweeps, the air flooded from the grid's edge: what the
   flood cannot reach is inside, and every swept cell takes the side of the free air nearest it.
   Probed again with every wall thickened by a cell or more: if the inside grows, it leaks through
   narrow openings, and the air behind them waits for an answer.
6. **Beyond each bore**: toward the outside what sits in it carries on at full radius; toward the
   inside a shaft carries on through it, unless the bore is a register.
7. **Sealing walls**: walls with the inside behind them. No through-holes, later.
8. **The candidate band**: a layer over the free wall, ``k`` local wall thicknesses deep, and the
   pockets between features a ball of radius ``c`` local wall thicknesses cannot enter.
9. **Labels**: the band minus everything forbidden is allowed; every cell keeps every reason.
10. **Columns**: from points over the free wall, straight out along the normal, how far metal may
    go before it leaves the allowed space - the height map's cap.
11. **Checks**: symmetry candidates with how well each matches, and questions for everything unsure.
12. **Where metal helps** (:mod:`.physics`), when the deck can be solved: the part under its loads,
    then the allowed space pinned to how it moved.
"""

from __future__ import annotations

import json
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
from .model import EVIDENCE_WORDS, Evidence, Interface, Label, Params, Question, Reason, Space

LEAK_PROBE_CELLS = (1, 2, 3)
"""How much every wall is thickened, in cells, to find narrow openings from the inside out."""

LEAK_GROWTH = 1.05
"""The inside leaks if thickening the walls lets it grow by more than this."""

LID_CELLS = 2
"""How deep, in cells, what mates against a plane closes an opening when the inside is flooded. A
cover closes the opening its flange rims; the space in front of a face is not a lid, or a box whose
every face might mate would have no inside and no outside at all."""

NEAR_MM = 150.0
"""Keep-outs run on to the grid's edge; their volumes are counted, as they are drawn, this close to
the part."""

CODE = ("generate/field.py", "geometry/brep.py")

STEPS: list[tuple[str, str]] = [
    ("grid", "Grid"),
    ("thickness", "Wall thickness"),
    ("interfaces", "Interfaces"),
    ("sweeps", "What sits round them"),
    ("inside", "The inside"),
    ("beyond", "Beyond each bore"),
    ("sealing", "Sealing walls"),
    ("band", "Where metal could go"),
    ("labels", "Allowed, forbidden, waiting"),
    ("columns", "Height straight out"),
    ("checks", "Symmetry and questions"),
    ("physics", "Where metal helps"),
]
"""The pipeline's steps, in order: an id and the few words a screen shows for it."""

GROUP_WORDS = {
    "confirmed": "Confirmed by you",
    "released": "Released by you",
    "deck_load": "Loaded by the deck",
    "deck_support": "Held by the deck",
    "drawing": "Toleranced on the drawing",
    "deck_hole_plane": "Clamped by a held bolt",
    "asked": "Asked about",
}

Report = Callable[[dict[str, Any]], None]

Publish = Callable[[Any, str, np.ndarray], None]
"""Hears each layer of cells as soon as a step has made it: the grid, its name, its cells."""


class _Steps:
    """Times each step, and hands what it produced to whoever is listening."""

    def __init__(self, say, report: Report | None) -> None:  # type: ignore[no-untyped-def]
        self.say = say
        self.report = report
        self.last = time.perf_counter()
        self.records: list[dict[str, Any]] = []
        self.labels = dict(STEPS)

    def start(self, step: str) -> None:
        self.last = time.perf_counter()
        if self.report:
            self.report({"id": step, "label": self.labels[step], "status": "running"})

    def done(
        self, step: str, detail: str, produced: dict[str, Any] | None = None, status: str = "done"
    ) -> None:
        now = time.perf_counter()
        record = {
            "id": step,
            "label": self.labels[step],
            "status": status,
            "seconds": round(now - self.last, 2),
            "detail": detail,
            "produced": produced or {},
        }
        self.records.append(record)
        self.last = now
        if self.say:
            self.say(f"  {self.labels[step]}: {record['seconds']:.1f} s - {detail}")
        if self.report:
            self.report(record)


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


def _size_of(i: Interface) -> str:
    if i.radius_mm:
        return f"O{2 * i.radius_mm:.0f}"
    return f"{i.area_mm2 / 100:.0f} cm2"


def _group_of(i: Interface) -> str:
    kinds = {e["kind"] for e in i.evidence}
    if not i.frozen:
        return "asked"
    return next(
        k
        for k in ("deck_load", "deck_support", "drawing", "deck_hole_plane", "confirmed")
        if k in kinds
    )


def _median_by_face(faces: np.ndarray, values: np.ndarray) -> dict[int, float]:
    out: dict[int, float] = {}
    if not len(faces):
        return out
    order = np.argsort(faces, kind="stable")
    faces, values = faces[order], values[order]
    unique, first = np.unique(faces, return_index=True)
    for face, chunk in zip(unique, np.split(values, first[1:]), strict=True):
        out[int(face)] = round(float(np.median(chunk)), 1)
    return out


def derive(  # noqa: C901 - one pass through the steps reads better than a dozen indirections
    extraction,  # type: ignore[no-untyped-def]
    setup: Any = None,
    params: Params | None = None,
    root: Path | None = None,
    say=print,  # type: ignore[no-untyped-def]
    report: Report | None = None,
    physics: bool = True,
    answers: dict[str, str] | None = None,
    publish: Publish | None = None,
) -> Space:
    """The design space of an extracted part. ``setup`` is the solver deck's setup, when the part
    has one; without it the derivation runs on geometry and the drawing alone, and the physics step
    is skipped. ``root`` keeps the part's grid in that project's cache. ``report`` hears each step
    start and finish, with what it produced; ``publish`` gets each layer of cells as it is made,
    just before the step that made it reports it finished."""
    params = params or Params()
    steps = _Steps(say, report)

    def show(layers: dict[str, np.ndarray]) -> None:
        if publish is not None:
            for name, cells in layers.items():
                publish(grid, name, cells)

    tess, atlas, features = extraction.tess, extraction.atlas, extraction.features

    # 1. Grid.
    steps.start("grid")
    field = _field(extraction, params, root)
    grid, part = field.grid, field.inside
    h = grid.spacing_mm
    air = ~part
    shape = grid.shape
    d_part = distance_to(part, h)
    near = d_part <= NEAR_MM
    show({"part": part})
    steps.done(
        "grid",
        f"{h:g} mm cells, {grid.n_cells / 1e6:.1f} M",
        {"spacing_mm": h, "cells": grid.n_cells, "part_L": _litres(part, h), "layers": ["part"]},
    )

    # 2. Wall thickness: twice the deepest point straight behind each point.
    steps.start("thickness")
    samples = sample_surface(tess, h)
    depth = signed_depth(field)
    thickness = np.maximum(
        thickness_behind(grid, depth, samples.points, samples.normals, params.thickness_reach_mm),
        0.5 * h,
    )
    del depth
    typical = float(np.median(thickness))
    thickness_by_face = _median_by_face(samples.face, thickness)
    steps.done(
        "thickness",
        f"typical wall {typical:.0f} mm",
        {
            "typical_mm": round(typical, 1),
            "percentiles_mm": {
                q: round(float(np.percentile(thickness, q)), 1) for q in (5, 25, 50, 75, 95)
            },
            "faces": "thickness",
        },
    )

    # 3. Interfaces.
    steps.start("interfaces")
    anchoring = extraction.anchoring if params.use_deck else None
    found, counted = interface_rules.find(
        atlas,
        features,
        params,
        anchoring=anchoring,
        setup=setup if params.use_deck else None,
        controlled=extraction.controlled,
        answers=answers,
    )
    # Released by the engineer's answer: no longer an interface, but shown, so it can be taken back.
    released: list[Interface] = counted.pop("released")
    frozen_faces = {f for i in found if i.frozen for f in i.faces}
    out_cell, _ = cell_of(grid, samples.points + samples.normals * (0.75 * h))
    by_face: dict[int, list[int]] = defaultdict(list)
    for index, face in enumerate(samples.face):
        by_face[int(face)].append(index)
    for i in found:
        idx = [k for f in i.faces for k in by_face.get(f, [])]
        i.thickness_mm = round(float(np.median(thickness[idx])), 1) if idx else None
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    interface_by_face: dict[int, str] = {}
    for i in found:
        group = _group_of(i)
        groups[group].append(
            {
                "id": i.id,
                "kind": i.kind,
                "faces": i.faces,
                "size": _size_of(i),
                "detail": "; ".join(
                    sorted({EVIDENCE_WORDS[Evidence(e["kind"])] for e in i.evidence})
                ),
            }
        )
        for f in i.faces:
            interface_by_face[f] = group
    frozen_n = sum(i.frozen for i in found)
    steps.done(
        "interfaces",
        f"{frozen_n} frozen, {len(found) - frozen_n} asked",
        {
            "groups": [
                {"key": k, "label": GROUP_WORDS[k], "count": len(groups[k]), "items": groups[k]}
                for k in (
                    "deck_load",
                    "deck_support",
                    "deck_hole_plane",
                    "drawing",
                    "confirmed",
                    "asked",
                )
                if groups.get(k)
            ],
            "counted_not_asked": counted,
            "released": [
                {"id": i.id, "kind": i.kind, "faces": i.faces, "size": _size_of(i)}
                for i in released
            ],
            "faces": "interface",
        },
    )

    # 4. Sweeps.
    steps.start("sweeps")
    corridor = np.zeros(shape, bool)
    plane = np.zeros(shape, bool)
    ring = np.zeros(shape, bool)
    hole = np.zeros(shape, bool)
    buffer = np.zeros(shape, bool)
    doubtful = np.zeros(shape, bool)
    # What closes an opening when the inside is flooded: what sits in a bore or fits over a boss,
    # whole; what mates against a plane, as deep as a cover; round a face in doubt, its buffer.
    lids = np.zeros(shape, bool)
    swept: dict[str, int] = {}
    lo_t, hi_t = params.wall_range[0] * typical, params.wall_range[1] * typical
    for i in found:
        if i.kind == "bore":
            cells = sweeps.bore_plug(grid, part, tess, i)
            _add(corridor if i.frozen else doubtful, cells)
            _add(lids, cells)
        elif i.kind == "plane":
            cells = sweeps.plane_neighbour(grid, part, tess, i)
            _add(plane if i.frozen else doubtful, cells)
            _add(lids, sweeps.plane_neighbour(grid, part, tess, i, depth_mm=LID_CELLS * h))
        elif i.kind == "boss":
            cells = sweeps.ring_neighbour(grid, part, tess, i)
            _add(ring if i.frozen else doubtful, cells)
            _add(lids, cells)
        else:
            cells = np.empty(0, np.int64)
        swept[i.id] = int(len(cells))
        radius = params.buffer * float(np.clip(i.thickness_mm or 2.0 * h, lo_t, hi_t))
        around = _buffer(grid, part, samples, i.faces, radius)
        _add(buffer if i.frozen else doubtful, around)
        if not i.frozen:
            _add(lids, around)
    frozen_holes = {f for i in found if i.kind == "hole" and i.frozen for f in i.faces}
    blocked: list[dict[str, Any]] = []
    for feature in features.of_kind(FeatureKind.HOLE):
        axis = np.asarray(feature.normal if feature.normal is not None else (0.0, 0.0, 1.0), float)
        radius = float(feature.metrics.get("radius_mm", 0.5 * (feature.diameter_mm or 0.0)))
        if radius <= 0:
            continue
        cells, ends = sweeps.hole_access(
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
        if set(feature.face_ids) & frozen_holes:
            for end in ends:
                if end["clear_mm"] < 2.0 * radius:
                    blocked.append({"hole": feature.id, **end, "diameter_mm": 2.0 * radius})
    shown = air & near
    show(
        {
            "plug": corridor & shown,
            "mating": plane & shown,
            "ring": ring & shown,
            "hole": hole & shown,
            "buffer": buffer & shown,
            "waiting": doubtful & shown,
        }
    )
    steps.done(
        "sweeps",
        f"{_litres((corridor | plane | ring | hole | buffer) & shown, h):.0f} L kept clear, "
        f"{_litres(doubtful & shown, h):.0f} L waiting, near the part",
        {
            "layers": [
                {"key": "plug", "label": "What sits in a bore", "L": _litres(corridor & shown, h)},
                {
                    "key": "mating",
                    "label": "What mates against a plane",
                    "L": _litres(plane & shown, h),
                },
                {"key": "ring", "label": "What fits over a boss", "L": _litres(ring & shown, h)},
                {"key": "hole", "label": "Fastener and tool", "L": _litres(hole & shown, h)},
                {
                    "key": "buffer",
                    "label": "Buffer round frozen faces",
                    "L": _litres(buffer & shown, h),
                },
                {
                    "key": "waiting",
                    "label": "Waiting on an answer",
                    "L": _litres(doubtful & shown, h),
                },
            ],
            "holes": len(features.of_kind(FeatureKind.HOLE)),
            "near_mm": NEAR_MM,
        },
    )

    # 5. The inside: flooded with the sweeps as lids - what sits in a bore or a hole whole, what
    # mates against a plane as deep as a cover - and every swept cell takes the side of the air
    # nearest it.
    steps.start("inside")
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
    # The inside as it is kept: the free air enclosed, and the lids and sweeps on its side.
    enclosed_l = _litres(cavity, h)
    leak_l = _litres(leak, h)
    status = (
        "none" if enclosed_cells == 0 and not leak.any() else ("leaks" if leak.any() else "closed")
    )
    show({"cavity": cavity, "leak": leak})
    steps.done(
        "inside",
        {
            "none": "no inside",
            "closed": f"closed, {enclosed_l:.0f} L",
            "leaks": f"leaks: {leak_l:.0f} L behind narrow openings",
        }[status],
        {
            "status": status,
            "inside_L": enclosed_l,
            "leak_L": leak_l,
            "probes": probes,
            "layers": ["cavity", "leak"],
        },
    )

    # 6. Beyond each bore.
    steps.start("beyond")
    beyond_mask = np.zeros(shape, bool)
    bores: list[dict[str, Any]] = []
    flat_part = part.ravel()
    flat_free, flat_exterior = free.ravel(), exterior.ravel()
    for i in found:
        if i.kind != "bore" or i.axis is None or i.radius_mm is None or i.axis_point is None:
            continue
        ends = sweeps.bore_ends(tess, i)
        went = []
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
                went.append("closed")
                continue
            if flat_exterior[cell[open_air[0]]]:
                share, where = 1.0, "outside: carried on"
            elif ends["register"]:
                went.append("inside: a register, nothing passes")
                continue
            else:
                share, where = sweeps.SHAFT_SHARE, f"inside: a shaft at {sweeps.SHAFT_SHARE:.0%}"
            cells = sweeps.bore_beyond(grid, part, tess, i, side, share)
            _add(corridor if i.frozen else doubtful, cells)
            _add(beyond_mask, cells)
            went.append(where)
        bores.append(
            {"id": i.id, "size": _size_of(i), "faces": i.faces, "frozen": i.frozen, "ends": went}
        )
    outside_air = air & ~cavity & ~leak
    inside_air = cavity & ~leak if params.inside else np.zeros(shape, bool)
    went_on = ("outside", "inside: a shaft")
    carried = sum(any(e.startswith(went_on) for e in b["ends"]) for b in bores)
    show({"beyond": beyond_mask & air & near})
    steps.done(
        "beyond",
        f"{carried} of {len(bores)} bores carried on",
        {"bores": bores, "layers": ["beyond"], "beyond_L": _litres(beyond_mask & air & near, h)},
    )

    # 7. Sealing walls: every point of the surface that faces the outside - lids and all - with the
    # inside behind it.
    steps.start("sealing")
    in_cell, _ = cell_of(grid, samples.points - samples.normals * (thickness[:, None] + 0.75 * h))
    wall = outside_air.ravel()[out_cell]
    sealing_sample = wall & (cavity | leak).ravel()[in_cell]
    share_of: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for face, seal, ext in zip(samples.face, sealing_sample, wall, strict=True):
        if ext:
            share_of[int(face)][0] += int(seal)
            share_of[int(face)][1] += 1
    sealing_faces = sorted(f for f, (s, n) in share_of.items() if n and s / n >= 0.5)
    free_wall = wall & ~np.isin(samples.face, np.asarray(sorted(frozen_faces), dtype=np.int64))
    nominal = float(np.median(thickness[free_wall])) if free_wall.any() else typical
    lo_t, hi_t = params.wall_range[0] * nominal, params.wall_range[1] * nominal
    steps.done(
        "sealing",
        f"{len(sealing_faces)} faces hold the inside",
        {"faces": "sealing", "count": len(sealing_faces)},
    )

    # 8. The candidate band: a layer over every wall but a frozen one - over a face in doubt it
    # waits with the face - and pockets between features.
    steps.start("band")
    seeded = free_wall
    seed_cells = out_cell[seeded]
    seed_t = np.clip(thickness[seeded], lo_t, hi_t)
    order = np.argsort(seed_cells, kind="stable")
    seed_cells, seed_t = seed_cells[order], seed_t[order]
    unique_cells, first, per_cell = np.unique(seed_cells, return_index=True, return_counts=True)
    if len(unique_cells):
        t_of_seed = np.add.reduceat(seed_t, first) / per_cell
        d_wall, nearest = distance_to(mask_of(grid, unique_cells), h, indices=True)
        t_near = (
            t_of_seed[np.searchsorted(unique_cells, nearest.ravel())]
            .reshape(shape)
            .astype(np.float32)
        )
        del nearest
        panel = outside_air & (d_wall <= params.panel_layer * t_near)
        del d_wall
    else:
        # No wall free to grow from: every face is an interface. Pockets between features stay.
        t_near = np.full(shape, nominal, np.float32)
        panel = np.zeros(shape, bool)
    if params.inside:
        inner = cavity.ravel()[out_cell]
        inner_cells = np.unique(out_cell[inner])
        inner_t = np.clip(thickness[inner], lo_t, hi_t)
        d_inner = distance_to(mask_of(grid, inner_cells), h)
        panel |= inside_air & (
            d_inner <= params.inside_layer * float(np.median(inner_t) if len(inner_t) else nominal)
        )
        del d_inner
    r_cap = params.headroom_mm - 2 * h
    r_local = np.minimum(params.pocket_reach * t_near, r_cap)
    pocket = np.zeros(shape, bool)
    ladder = []
    for radius in sorted(r for r in params.pocket_ladder_mm if r <= r_cap):
        dilated = d_part <= radius
        closing = dilated & (distance_to(~dilated, h) > radius)
        rung = closing & (outside_air | inside_air)
        ladder.append({"radius_mm": radius, "pocket_L": _litres(rung, h)})
        pocket |= rung & (r_local >= radius)
        del dilated, closing, rung
    del r_local
    candidate = (panel | pocket) & (outside_air | inside_air)
    show({"panel": panel, "pocket": pocket})
    steps.done(
        "band",
        f"{_litres(panel, h):.0f} L layer, {_litres(pocket, h):.0f} L pockets",
        {
            "layers": [
                {
                    "key": "panel",
                    "label": f"Layer, {params.panel_layer:g} walls deep",
                    "L": _litres(panel, h),
                },
                {"key": "pocket", "label": "Pockets between features", "L": _litres(pocket, h)},
            ],
            "wall_mm": round(nominal, 1),
            "wall_range_mm": [round(lo_t, 1), round(hi_t, 1)],
            "ladder": ladder,
            "inside": params.inside,
        },
    )

    # 9. Labels and reasons.
    steps.start("labels")
    labels = np.full(shape, int(Label.OPEN_AIR), np.uint8)
    reasons = np.zeros(shape, np.uint16)
    unknown = (doubtful | leak) & (candidate | leak)
    for mask, reason in (
        (part, Reason.PART),
        (cavity, Reason.CAVITY),
        (corridor, Reason.BORE_CORRIDOR),
        (plane, Reason.PLANE_NEIGHBOUR),
        (ring, Reason.RING_NEIGHBOUR),
        (hole, Reason.HOLE_ACCESS),
        (buffer, Reason.INTERFACE_BUFFER),
        (doubtful | leak, Reason.UNKNOWN),
        (panel, Reason.PANEL_LAYER),
        (pocket, Reason.POCKET),
        (beyond_mask, Reason.BEYOND),
        (leak, Reason.LEAK),
    ):
        reasons[mask] |= np.uint16(reason)
    for mask, label in (
        (cavity, Label.CAVITY),
        (candidate, Label.ADMISSIBLE),
        (unknown, Label.UNKNOWN),
        (buffer & air, Label.INTERFACE_BUFFER),
        (hole & air, Label.HOLE_ACCESS),
        (ring & air, Label.RING_NEIGHBOUR),
        (plane & air, Label.PLANE_NEIGHBOUR),
        (corridor & air, Label.BORE_CORRIDOR),
        (part, Label.PART),
    ):
        labels[mask] = int(label)
    admissible = labels == Label.ADMISSIBLE
    forbidden = candidate & ~admissible & (labels != Label.UNKNOWN)
    show({"allowed": admissible, "unknown": labels == Label.UNKNOWN})
    steps.done(
        "labels",
        f"{_litres(admissible, h):.0f} L allowed, "
        f"{_litres(labels == Label.UNKNOWN, h):.0f} L waiting",
        {
            "layers": [
                {"key": "allowed", "label": "Allowed", "L": _litres(admissible, h)},
                {
                    "key": "unknown",
                    "label": "Waiting on an answer",
                    "L": _litres(labels == Label.UNKNOWN, h),
                },
            ],
            "taken_from_band_L": _litres(forbidden, h),
        },
    )

    # 10. Columns from the free wall, two per cell of wall.
    steps.start("columns")
    dense = sample_surface(tess, h, seed=2, per_cell=2.0)
    dense_out, _ = cell_of(grid, dense.points + dense.normals * (0.75 * h))
    facing_space = outside_air.ravel()[dense_out] | (
        inside_air.ravel()[dense_out] if params.inside else False
    )
    # From the free wall alone: a face in doubt has no height until it is answered.
    interface_faces = np.asarray(sorted({f for i in found for f in i.faces}), dtype=np.int64)
    keep = facing_space & ~np.isin(dense.face, interface_faces)
    cols = dense.subset(keep)
    longest = float(params.panel_layer * hi_t + r_cap)
    step = 0.5 * h
    distances = np.arange(0.5 * h, longest + step, step)
    cap = np.zeros(len(cols))
    reenters = np.zeros(len(cols), bool)
    reachable = np.zeros(admissible.size, bool)
    flat_admissible = admissible.ravel()
    for lo in range(0, len(cols), 20_000):
        hi = min(lo + 20_000, len(cols))
        p = cols.points[lo:hi, None, :] + cols.normals[lo:hi, None, :] * distances[None, :, None]
        cells, on = cell_of(grid, p.reshape(-1, 3))
        ok = (flat_admissible[cells] & on).reshape(hi - lo, len(distances))
        first_out = np.where((~ok).any(axis=1), (~ok).argmax(axis=1), len(distances))
        cap[lo:hi] = np.where(
            first_out > 0, distances[np.maximum(first_out - 1, 0)] + 0.5 * step, 0.0
        )
        after = np.arange(len(distances))[None, :] > first_out[:, None]
        reenters[lo:hi] = (ok & after).any(axis=1)
        inside_run = np.arange(len(distances))[None, :] < first_out[:, None]
        reachable[cells.reshape(hi - lo, -1)[inside_run]] = True
    unreachable = flat_admissible & ~reachable
    columns = {
        "points": cols.points.astype(np.float32),
        "normals": cols.normals.astype(np.float32),
        "face": cols.face.astype(np.int32),
        "cap": cap.astype(np.float32),
        "reenters": reenters,
    }
    cap_by_face = _median_by_face(cols.face, cap)
    steps.done(
        "columns",
        f"median {float(np.median(cap)) if len(cap) else 0:.0f} mm straight out",
        {
            "count": int(len(cols)),
            "cap_mm": {q: round(float(np.percentile(cap, q)), 1) for q in (10, 50, 90)}
            if len(cap)
            else {},
            "zero_share": round(float((cap == 0).mean()), 3) if len(cap) else None,
            "reentry_share": round(float(reenters.mean()), 3) if len(cap) else None,
            "unreachable_L": round(float(unreachable.sum()) * h**3 / 1e6, 1),
            "faces": "cap",
        },
    )

    # 11. Symmetry and questions.
    steps.start("checks")
    symmetry = _symmetry(grid, part, samples, h)
    questions = _questions(
        found + released, probes, enclosed_cells, leak, h, thickness, blocked, symmetry, grid
    )
    questions.append(
        Question(
            id="q:inside",
            kind="inside",
            text="Ribs on the inner walls too?"
            if not params.inside
            else "Ribs on the inner walls: allowed. Keep?",
            detail="what moves inside is in neither the CAD nor the deck; allowed inside means "
            f"clear of each bore's own volume and a shaft of {sweeps.SHAFT_SHARE:.0%} of its "
            "radius through it",
            options=("outside only", "inside too"),
            meanwhile="outside only" if not params.inside else "inside too",
        )
    )
    best = symmetry[0]["match_share"] if symmetry else 0.0
    steps.done(
        "checks",
        f"{len(questions)} questions; best mirror matches {best:.0%}",
        {"symmetry": symmetry, "questions": [q.to_json() for q in questions]},
    )

    space = Space(
        grid=grid,
        params=params,
        labels=labels,
        reasons=reasons,
        interfaces=found,
        questions=questions,
        columns=columns,
        sealing_faces=sealing_faces,
        symmetry=symmetry,
        stats={
            "cells": int(labels.size),
            "samples": int(len(samples)),
            "nominal_wall_mm": round(nominal, 1),
            "wall_range_mm": [round(lo_t, 1), round(hi_t, 1)],
            "swept_cells": swept,
            "blocked_hole_ends": len(blocked),
            "thin_wall_share": round(float((thickness < 2 * h).mean()), 3),
        },
        source_digest=extraction.cad_digest,
        faces={"thickness": thickness_by_face, "cap": cap_by_face, "interface": interface_by_face},
    )

    # 12. Where metal helps.
    steps.start("physics")
    if not physics:
        steps.done("physics", "not asked for", status="skipped")
    elif setup is None or not extraction.anchoring or not params.use_deck:
        steps.done("physics", "no solver deck to load the part with", status="skipped")
    else:
        from .physics import preview

        try:
            result = preview(grid, labels, tess, extraction.anchoring, setup, say=say)
            space.benefit = result["benefit"]
            stats = result["stats"]
            allowed_values = space.benefit[admissible]
            steps.done(
                "physics",
                f"part {stats['part_cg']['seconds']:.0f} s, "
                f"filler {stats['filler_cg']['seconds']:.0f} s; "
                f"largest movement {stats['largest_displacement_mm']:.1f} mm",
                {
                    **{k: v for k, v in stats.items() if k != "loads"},
                    "benefit_top_quarter": float(np.percentile(allowed_values, 75))
                    if len(allowed_values)
                    else 0.0,
                    "layers": ["benefit"],
                },
            )
        except Exception as error:  # noqa: BLE001 - a preview that fails leaves the space standing
            steps.done("physics", f"failed: {type(error).__name__}: {error}", status="failed")
    space.steps = steps.records
    return space


def _symmetry(grid, part: np.ndarray, samples: Samples, h: float) -> list[dict[str, Any]]:  # type: ignore[no-untyped-def]
    """Candidate mirror planes and how much of the surface each maps onto the surface."""
    ijk = np.argwhere(part)
    if len(ijk) > 400_000:
        ijk = ijk[:: len(ijk) // 400_000]
    pts = ijk * h + np.asarray(grid.origin)
    centre = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - centre, full_matrices=False)
    unique: list[np.ndarray] = []
    for n in [*vt, *np.eye(3)]:
        n = n / np.linalg.norm(n)
        if all(abs(float(n @ m)) < 0.99 for m in unique):
            unique.append(n)
    surface_cells = np.unique(cell_of(grid, samples.points)[0])
    to_surface = distance_to(mask_of(grid, surface_cells), h)
    rng = np.random.default_rng(1)
    probe = samples.points[rng.choice(len(samples), size=min(40_000, len(samples)), replace=False)]
    out = []
    for n in unique:
        mirrored = probe - 2.0 * ((probe - centre) @ n)[:, None] * n[None, :]
        cells, on = cell_of(grid, mirrored)
        d = np.where(on, to_surface.ravel()[cells], np.inf)
        finite = d[np.isfinite(d)]
        out.append(
            {
                "normal": [round(float(v), 4) for v in n],
                "through": [round(float(v), 1) for v in centre],
                "match_share": round(float((d <= 2.0 * h).mean()), 3),
                "median_miss_mm": round(float(np.median(finite)), 1) if len(finite) else None,
            }
        )
    out.sort(key=lambda s: -s["match_share"])
    return out


def _questions(  # type: ignore[no-untyped-def]
    found: list[Interface], probes, enclosed_cells, leak, h, thickness, blocked, symmetry, grid
) -> list[Question]:
    questions: list[Question] = []
    for i in found:
        if i.frozen:
            continue
        kinds = {Evidence(e["kind"]) for e in i.evidence}
        words = "; ".join(EVIDENCE_WORDS[k] for k in kinds)
        what = {"plane": "Flat face", "bore": "Bore", "boss": "Boss", "hole": "Hole"}.get(
            i.kind, "Face"
        )
        questions.append(
            Question(
                id=f"q:{i.id}",
                kind="interface",
                text=f"{what} {_size_of(i)}: does something meet it?",
                detail=words,
                faces=i.faces,
                options=("freeze", "free"),
                meanwhile="the space in front of it and round it waits",
            )
        )
    enclosed_l = enclosed_cells * h**3 / 1e6
    leak_l = float(leak.sum()) * h**3 / 1e6
    growth = ", ".join(f"{p['mm']:.0f} mm -> {p['inside_L']:.1f} L" for p in probes)
    if leak_l > 0:
        ijk = np.argwhere(leak)
        where = tuple(float(v) for v in (ijk.mean(axis=0) * h + np.asarray(grid.origin)))
        questions.append(
            Question(
                id="q:inside-closed",
                kind="cavity",
                text=f"Inside: {enclosed_l:.1f} L closed, "
                f"{leak_l:.1f} L more behind narrow openings",
                detail=f"walls thickened by {growth}",
                where=where,
                options=("inside", "outside"),
                meanwhile="the air behind the narrow openings waits",
            )
        )
    elif enclosed_l > 0:
        questions.append(
            Question(
                id="q:inside-closed",
                kind="cavity",
                text=f"Inside is closed: {enclosed_l:.1f} L of free air. Confirm?",
                detail=f"walls thickened by {growth}: the inside does not grow",
                options=("confirm", "reopen"),
                meanwhile="treated as inside",
            )
        )
    thin = float((thickness < 2 * h).mean())
    if thin > 0.01:
        questions.append(
            Question(
                id="q:thin-walls",
                kind="resolution",
                text=f"{thin:.0%} of the surface is thinner than two cells ({2 * h:.0f} mm)",
                detail="the grid may see openings through them that are not there",
                meanwhile="reported only",
            )
        )
    for b in blocked:
        questions.append(
            Question(
                id=f"q:access:{b['hole']}",
                kind="access",
                text=f"Hole O{b['diameter_mm']:.0f}: "
                f"only {b['clear_mm']:.0f} mm clear straight out",
                detail="a tool along the hole's axis meets the part",
                where=tuple(b["at"]),
                meanwhile="reported only",
            )
        )
    if symmetry and symmetry[0]["match_share"] >= 0.6:
        s = symmetry[0]
        questions.append(
            Question(
                id="q:mirror",
                kind="symmetry",
                text=f"Mirror plane matches {s['match_share']:.0%} of the surface: "
                "keep designs mirrored?",
                detail=f"normal {s['normal']} through {s['through']}",
                options=("mirror", "no"),
                meanwhile="not enforced",
            )
        )
    return questions


def save(space: Space, path) -> None:  # type: ignore[no-untyped-def]
    """The arrays in one file, beside the summary as JSON."""
    path = Path(path)
    arrays = {
        "labels": space.labels,
        "reasons": space.reasons,
        "origin": np.asarray(space.grid.origin),
        "spacing": np.asarray(space.grid.spacing_mm),
        "shape": np.asarray(space.grid.shape),
        **{f"column_{k}": v for k, v in space.columns.items()},
    }
    if space.benefit is not None:
        arrays["benefit"] = space.benefit
    np.savez_compressed(path.with_suffix(".npz"), **arrays)
    path.with_suffix(".json").write_text(
        json.dumps(space.summary(), indent=1, default=str), encoding="utf-8"
    )
