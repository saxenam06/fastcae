"""Checks: every design comes out pass, warn or reject, with a reason and a place.

A blended shape always builds; it can still be quietly wrong. These are the ways it can be, each
measured on the design as composed and contoured, never on what was asked for. Every finding names
the rule it used and whether that rule is assumed, so a threshold nobody has confirmed is never
presented as one somebody has.

**The fillet that was actually made.** On a fillet surface the distances to the part and to the rib,
``a`` and ``b``, satisfy ``(k - a)^2 + (k - b)^2 = k^2`` - so every contoured vertex on a fillet
says what ``k``, and so what radius, it was built to: ``k = a + b + sqrt(2ab)``, and
``R = k / (1 - n_a . n_b)``. Read off the surface, that is the radius a person would measure, grid
error and all.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy import ndimage

from .compose import Composition, Window
from .field import Field
from .ribs import ArcRib
from .surface import Surface


@dataclass(frozen=True)
class Rules:
    """The rules a design is held to. Values and where each comes from.

    What belongs to the part - the rib section, its fillet and edge round, the smallest radius the
    drawing allows - has no default: the engineer sets it, or the agent proposes it and says so.
    What is left are general rules of thumb, each labelled assumed until a project replaces it.
    """

    thickness_mm: tuple[float, float] | None = None
    edge_round_mm: float | None = None
    root_fillet_mm: float | None = None
    fillet_floor_mm: float | None = None
    draft_deg: tuple[float, float] = (0.0, 2.0)
    draft_used_deg: float = 1.0
    fillet_tolerance: float = 0.2
    rib_to_wall: float = 0.8
    root_gap: float = 2.0
    thick_spot: float = 2.0
    per_block: dict[str, dict[str, Any]] = field(default_factory=dict, compare=False)
    """For a design of several blocks, each block's own - ``thickness_mm`` and ``draft_deg`` as
    (low, high), ``root_fillet_mm`` - which a rib of that block is held to instead of what is
    shared: the thickness and draft its design space allows, and the fillet it was made with."""
    basis: tuple[tuple[str, str, bool], ...] = (
        ("draft_deg", "castable window", True),
        ("rib_to_wall", "foundry rule of thumb", True),
        ("root_gap", "clear gap between rib roots", True),
        ("thick_spot", "section at a junction against the wall beside it", True),
    )

    # Set per part, never defaulted.
    PART_RULES = ("thickness_mm", "edge_round_mm", "root_fillet_mm", "fillet_floor_mm")

    def missing(self) -> list[str]:
        """The part's own rules nobody has set yet."""
        return [name for name in self.PART_RULES if getattr(self, name) is None]

    def source(self, name: str) -> tuple[str, bool]:
        for key, text, assumed in self.basis:
            if key == name:
                return text, assumed
        return "", True

    def of(self, name: str, block: str | None) -> Any:
        """A rule for the ribs of one block: the block's own when it has one, else the shared."""
        own = self.per_block.get(block, {}).get(name) if block is not None else None
        return getattr(self, name) if own is None else own

    def own(self, name: str) -> bool:
        """Whether any block has its own of this rule."""
        return any(name in rules for rules in self.per_block.values())


@dataclass(frozen=True)
class Finding:
    check: str
    outcome: str
    reason: str
    rule: str
    assumed: bool = True
    where: tuple[float, float, float] | None = None
    value: float | None = None
    section: str = "check"
    """``check``: what the platform holds every rib to. ``constraint``: what the engineer asked."""
    cites: tuple[str, ...] = ()
    """For a constraint, the engineer's words it answers to."""


def check(
    base: Field,
    window: Window,
    design: Composition,
    ribs: list,
    surface: Surface,
    rules: Rules,
    owners: dict | None = None,
    shift=None,
) -> list[Finding]:
    """Every check, on one design. ``owners`` says which block each rib is of, for the rules each
    block has of its own; ``shift``, how far the design moved the part's surface at any points - the
    faces a rib is filleted to where they now are."""
    owners = owners or {}
    radii = {r: float(rules.of("root_fillet_mm", owners.get(r))) for r in ribs}
    return [
        _protected(base, window, design),
        _grid_edge(window, design),
        _floating(base, design),
        _thickness(ribs, base.grid.spacing_mm, rules, owners),
        _gaps(base, ribs, rules, radii),
        _fillet(window, design, ribs, surface, rules, radii, shift),
        _bridging(window, design, rules),
        _clipped(window, design),
        _release(base, design, ribs, rules, owners),
        _ends(base, design, ribs, rules),
        *_sections(base, window, design, ribs, rules),
        _surface(surface),
    ]


def described(rules: Rules | None = None) -> list[dict[str, str]]:
    """Every check a built design goes through and what it holds the design to, in words - as the
    pipeline shows them."""
    r = rules or Rules()
    low, high = r.draft_deg
    return [
        {"name": "protected areas unchanged", "rule": "every protected cell exactly as it was"},
        {"name": "within the grid", "rule": "no rib runs off the grid the part was sampled on"},
        {"name": "nothing floating", "rule": "every piece of new metal touches the part"},
        {
            "name": "rib thickness",
            "rule": "each rib within the thickness its block allows, and at least 4 voxels",
        },
        {
            "name": "root gap",
            "rule": f"a clear gap of {r.root_gap:g} x the thinner rib between ribs in the open",
        },
        {
            "name": "root fillet",
            "rule": "no smaller than the smallest radius the study allows, and within "
            f"{r.fillet_tolerance:.0%} of the radius its block asks for",
        },
        {
            "name": "rib ends",
            "rule": "each rib's end meets the metal ahead of it, or stops at least "
            f"{r.root_gap:g} x its thickness short of it - no finger of sand between",
        },
        {"name": "blend bridging", "rule": "fillet material only where a rib meets the part"},
        {"name": "blend clipped", "rule": "no fillet cut short by a protected area"},
        {
            "name": "mould release",
            "rule": f"each rib's draft within what its block allows - {low:g}-{high:g} deg where "
            "it says nothing - and every rib tip open along the pull",
        },
        {
            "name": "thick spots",
            "rule": f"the section at a junction at most {r.thick_spot:g} x the wall beside it",
        },
        {
            "name": "rib against wall",
            "rule": f"a rib at most {r.rib_to_wall:g} x the wall it joins",
        },
        {"name": "surface", "rule": "the design's surface closed, with no stray edges"},
    ]


# --- the checks ---------------------------------------------------------------------------------


def _protected(base: Field, window: Window, design: Composition) -> Finding:
    rule = "every protected cell equals the baseline"
    cells = window.samples_of(np.flatnonzero(window.protected))
    if not cells.size:
        return Finding(
            "protected areas unchanged", "pass", "no protected area near the ribs", rule, False
        )
    differs = (design.field.at(cells) != base.at(cells)) | (
        design.field.inside.ravel()[cells] != base.inside.ravel()[cells]
    )
    if differs.any():
        where = tuple(base.grid.centres(cells[differs][:1])[0])
        return Finding(
            "protected areas unchanged",
            "reject",
            f"{int(differs.sum())} protected cells changed",
            rule,
            False,
            where,
        )
    return Finding(
        "protected areas unchanged",
        "pass",
        f"{cells.size:,} protected cells unchanged",
        rule,
        False,
    )


def _grid_edge(window: Window, design: Composition) -> Finding:
    rule = "no rib reaches the edge of the grid"
    held = design.off_grid if design.off_grid is not None else np.empty(0, dtype=np.int64)
    if held.size:
        return Finding(
            "within the grid",
            "reject",
            f"a rib runs off the grid ({held.size:,} cells held back): it has left the part, "
            "or needs more room than the grid was built with",
            rule,
            False,
            _centre_of(window, held),
        )
    return Finding("within the grid", "pass", "every rib inside the grid", rule, False)


def _floating(base: Field, design: Composition) -> Finding:
    rule = "every piece of rib touches the part, directly or through other ribs"
    added = design.changed[
        design.field.inside.ravel()[design.changed] & ~base.inside.ravel()[design.changed]
    ]
    if not added.size:
        return Finding("nothing floating", "pass", "nothing was added", rule, False)
    box, lo = _box_around(base.grid.shape, added, 2)
    new = design.field.inside[box] & ~base.inside[box]
    labels, count = ndimage.label(new, structure=np.ones((3, 3, 3), dtype=bool))
    touching = ndimage.binary_dilation(base.inside[box], structure=np.ones((3, 3, 3), dtype=bool))
    loose = [n for n in range(1, count + 1) if not np.any(touching[labels == n])]
    if loose:
        sizes = [int((labels == n).sum()) for n in loose]
        biggest = loose[int(np.argmax(sizes))]
        where = _centre(base, np.argwhere(labels == biggest) + lo)
        volume = sum(sizes) * base.grid.spacing_mm**3 / 1e3
        return Finding(
            "nothing floating",
            "reject",
            f"{len(loose)} piece(s) of rib, {volume:.1f} cm3, touch nothing",
            rule,
            False,
            where,
        )
    return Finding("nothing floating", "pass", f"{count} piece(s), all attached", rule, False)


def _ribs_only(ribs: list) -> list:
    """The ribs among what was composed: pads thicken walls, and are held to nothing a rib is."""
    return [r for r in ribs if not getattr(r, "pad", False)]


def _thickness(ribs: list, spacing: float, rules: Rules, owners: dict | None = None) -> Finding:
    ribs = _ribs_only(ribs)
    owners = owners or {}
    text, assumed = rules.source("thickness_mm")
    if rules.own("thickness_mm"):
        rule = "each rib within the thickness its block allows (the study); at least 4 voxels"
    else:
        low, high = rules.thickness_mm
        rule = f"{low:g}-{high:g} mm ({text}); at least 4 voxels"
    for rib in ribs:
        low, high = rules.of("thickness_mm", owners.get(rib))
        if not low <= rib.thickness_mm <= high:
            why = f"{rib.thickness_mm:g} mm is outside {low:g}-{high:g} mm"
        elif rib.thickness_mm < 4 * spacing:
            why = f"{rib.thickness_mm:g} mm is under 4 voxels of {spacing:g} mm"
        else:
            continue
        return Finding("rib thickness", "reject", why, rule, assumed, value=rib.thickness_mm)
    return Finding("rib thickness", "pass", f"{len(ribs)} ribs inside the window", rule, assumed)


def _gaps(base: Field, ribs: list, rules: Rules, radii: dict | None = None) -> Finding:
    """``radii``, when given, is each rib's own root fillet; else the rules'."""
    ribs = _ribs_only(ribs)
    text, assumed = rules.source("root_gap")
    rule = f"clear gap between ribs >= {rules.root_gap:g} x thickness ({text})"
    if len(ribs) < 2:
        return Finding("root gap", "pass", "one rib", rule, assumed)
    # Only where a rib stands in the open: the stretch that runs into a wall or boss is trimmed
    # away, and spokes converging inside a boss are not a gap anybody casts - nor are they in the
    # junction at either end, a fillet and a thickness long, where ribs meet what they end on.
    pieces = [_exposed(base, r, _junction(r, rules, (radii or {}).get(r))) for r in ribs]
    worst, where = math.inf, None
    for i in range(len(ribs)):
        for j in range(i + 1, len(ribs)):
            reach = (ribs[i].thickness_mm + ribs[j].thickness_mm) / 2.0
            for line_i in pieces[i]:
                for line_j in pieces[j]:
                    distance, point = _polyline_distance(line_i, line_j)
                    if distance <= reach:
                        continue  # they cross: a junction, filleted, not a gap
                    gap = distance - reach
                    if gap < worst:
                        worst, where = gap, point
    thinnest = min(r.thickness_mm for r in ribs)
    if worst < rules.root_gap * thinnest:
        return Finding(
            "root gap",
            "reject",
            f"a {worst:.1f} mm gap between ribs",
            rule,
            assumed,
            tuple(where),
            worst,
        )
    reason = "no ribs face each other" if math.isinf(worst) else f"narrowest gap {worst:.0f} mm"
    return Finding(
        "root gap", "pass", reason, rule, assumed, value=None if math.isinf(worst) else worst
    )


def _fillet(
    window: Window,
    design: Composition,
    ribs: list,
    surface: Surface,
    rules: Rules,
    radii: dict | None = None,
    shift=None,
) -> Finding:
    """``radii``, when given, is the root fillet each rib was made with; else the rules'. ``shift``,
    how far the design moved the part's surface: a fillet is read against the face where it is."""
    targets = np.array([(radii or {}).get(r, rules.root_fillet_mm) for r in ribs], dtype=float)
    floor = rules.fillet_floor_mm
    text, assumed = rules.source("fillet_floor_mm")
    aim = f"R{targets[0]:g}" if np.allclose(targets, targets[0]) else "each rib's own radius"
    rule = f"achieved radius >= R{floor:g} ({text}); within {rules.fillet_tolerance:.0%} of {aim}"

    grid = window.grid
    lo = np.asarray(grid.origin)
    hi = lo + (np.asarray(grid.shape) - 1) * grid.spacing_mm
    v = surface.vertices
    inside = np.all((v >= lo) & (v <= hi), axis=1)
    v = v[inside]
    a = _trilinear(window, window.part, v)
    if shift is not None and v.size:
        a = a - shift(v)
    near = a < 2.0 * targets.max()
    v, a = v[near], a[near]
    if not v.size:
        return Finding("root fillet", "warn", "no fillet found to measure", rule, assumed)
    n_a = window.normal_at(_nearest_cell(window, v))

    distances = np.stack([r.distance(v) for r in ribs], axis=1)
    owner = np.argmin(distances, axis=1)
    b = distances[np.arange(v.shape[0]), owner]
    n_b = np.zeros_like(v)
    for index in np.unique(owner):
        n_b[owner == index] = ribs[index].normal(v[owner == index])
    cosine = np.einsum("ij,ij->i", n_a, n_b)
    k = targets[owner] * (1.0 - cosine)
    on = (a > 0.05 * k) & (b > 0.05 * k) & (a < 0.95 * k) & (b < 0.95 * k) & (cosine < 0.9)
    if on.sum() < 10:
        return Finding("root fillet", "warn", "too little fillet surface to measure", rule, assumed)
    radius = (a[on] + b[on] + np.sqrt(2.0 * a[on] * b[on])) / (1.0 - cosine[on])
    # Each rib against its own radius, the one furthest from it said. A pad's edge against the wall
    # it lies on is no rib's root: the surface there is only kept from being read as a rib's.
    per_rib = [
        (float(np.median(radius[owner[on] == i])), float(targets[i]))
        for i in np.unique(owner[on])
        if (owner[on] == i).sum() >= 10 and not getattr(ribs[i], "pad", False)
    ]
    if per_rib:
        achieved, target = max(per_rib, key=lambda p: abs(p[0] / p[1] - 1.0))
    else:
        achieved, target = float(np.median(radius)), float(np.median(targets[owner[on]]))
    where = tuple(v[on][int(np.argmin(np.abs(radius - achieved)))])
    if achieved < floor:
        return Finding(
            "root fillet",
            "reject",
            f"R{achieved:.1f} achieved, below R{floor:g}",
            rule,
            assumed,
            where,
            achieved,
        )
    if abs(achieved - target) > rules.fillet_tolerance * target:
        return Finding(
            "root fillet",
            "warn",
            f"R{achieved:.1f} achieved against R{target:g}",
            rule,
            assumed,
            where,
            achieved,
        )
    return Finding(
        "root fillet",
        "pass",
        f"R{achieved:.1f} achieved against R{target:g}",
        rule,
        assumed,
        where,
        achieved,
    )


def _bridging(window: Window, design: Composition, rules: Rules) -> Finding:
    rule = "fillet material only where a rib meets the part"
    touched, a, b = design.touched, design.part, design.ribs
    if touched is None or not touched.size:
        return Finding("blend bridging", "pass", "nothing blended", rule, False)
    value = design.field.at(window.samples_of(touched))
    fillet = (value < 0.0) & (a > 0.0) & (b > 0.0)
    overlap = (a < 0.0) & (b < 0.0)
    if not fillet.any():
        return Finding("blend bridging", "pass", "no fillet material", rule, False)

    box, lo = _box_around(window.grid.shape, touched, 2)
    marks = np.zeros(window.grid.shape, dtype=bool)
    marks.ravel()[touched[overlap]] = True
    away = ndimage.distance_transform_edt(~marks[box]) * window.grid.spacing_mm
    cells = np.stack(np.unravel_index(touched[fillet], window.grid.shape), axis=1) - lo
    far = away[tuple(cells.T)] > 2.0 * rules.root_fillet_mm + window.grid.spacing_mm
    if far.any():
        where = _centre_of(window, touched[fillet][far])
        volume = far.sum() * window.grid.spacing_mm**3 / 1e3
        return Finding(
            "blend bridging",
            "warn",
            f"{volume:.1f} cm3 of fillet fills a gap to something the rib does not touch",
            rule,
            False,
            where,
        )
    return Finding("blend bridging", "pass", "every fillet sits on a rib's root", rule, False)


def _clipped(window: Window, design: Composition) -> Finding:
    rule = "fillets are not cut short by protected areas"
    if design.clipped is None or not design.clipped.size:
        return Finding("blend clipped", "pass", "no fillet reaches a protected area", rule, False)
    return Finding(
        "blend clipped",
        "warn",
        f"{design.clipped.size} cells of rib or fillet cut back by a protected area",
        rule,
        False,
        _centre_of(window, design.clipped),
    )


def _release(
    base: Field, design: Composition, ribs: list, rules: Rules, owners: dict | None = None
) -> Finding:
    owners = owners or {}
    text, assumed = rules.source("draft_deg")
    if rules.own("draft_deg"):
        rule = "each rib's draft within what its block allows (the study); every rib face"
        rule += " visible along the pull"
    else:
        low, high = rules.draft_deg
        rule = f"draft {low:g}-{high:g} deg ({text}); every rib face visible along the pull"
    # A pad lies along the wall it thickens, and has no draft of its own.
    for rib in _ribs_only(ribs):
        low, high = rules.of("draft_deg", owners.get(rib))
        if not low <= rib.draft_deg <= high:
            why = f"draft {rib.draft_deg:g} deg, outside {low:g}-{high:g}"
            return Finding("mould release", "reject", why, rule, assumed)

    spacing = base.grid.spacing_mm
    lo = np.asarray(base.grid.origin)
    hi = lo + (np.asarray(base.grid.shape) - 1) * spacing
    blocked, where = 0, None
    for rib in ribs:
        tips, up = _tips(rib, spacing)
        # Rib material, not the part's own: a tip drawn into a boss is the boss.
        below = tips - 0.5 * spacing * up
        exists = (design.field.sample(below) < 0.0) & (base.sample(below) > 0.0)
        tips = tips[exists]
        if not tips.size:
            continue
        steps = np.arange(1.0, np.linalg.norm(hi - lo) / spacing) * spacing
        for tip in tips:
            ray = tip + steps[:, None] * up
            ray = ray[np.all((ray >= lo) & (ray <= hi), axis=1)]
            if ray.size and np.any(base.sample(ray) < 0.0):
                blocked += 1
                where = where or tuple(tip)
    if blocked:
        return Finding(
            "mould release",
            "reject",
            f"{blocked} points on rib tips sit under the part along the pull",
            rule,
            assumed,
            where,
        )
    return Finding("mould release", "pass", "every rib tip is open along the pull", rule, assumed)


def _ends(base: Field, design: Composition, ribs: list, rules: Rules) -> Finding:
    """No finger of sand between a rib's end and the metal ahead of it: along each rib, out past
    each end, at a quarter, half and three quarters of its height there, the design is metal all the
    way into what is ahead, or air for at least the root gap. An end in the part's own metal is
    joined to it, whatever the part holds past it."""
    text, assumed = rules.source("root_gap")
    rule = (
        f"a rib's end meets the metal ahead of it, or stops >= {rules.root_gap:g} x its thickness "
        f"short ({text})"
    )
    field = design.field
    step = field.grid.spacing_mm / 2.0
    worst, where = 0.0, None
    # Straight ribs: an arc's ends run on round what it follows, and are not looked at here.
    for rib in (r for r in _ribs_only(ribs) if hasattr(r, "start")):
        start, end = np.asarray(rib.start, float), np.asarray(rib.end, float)
        length = float(np.linalg.norm(end - start))
        if length < 1e-6:
            continue
        along = (end - start) / length
        up = np.asarray(rib.pull, float) / np.linalg.norm(rib.pull)
        room = rules.root_gap * rib.thickness_mm
        s = np.arange(-step, room + step, step)
        # The first sample past the end face: metal there, and the end is buried in what it meets -
        # air further on is the part's own, a hole or a pocket, not sand between the two.
        past = int(np.searchsorted(s, 0.5 * step))
        ends = ((start, -along, rib.height_mm), (end, along, rib.end_height_mm or rib.height_mm))
        for tip, outward, height in ends:
            for fraction in (0.25, 0.5, 0.75):
                points = tip + fraction * height * up + s[:, None] * outward
                metal = field.sample(points) < 0.0
                if not metal[0] or metal[past] or base.sample(points[:1])[0] < 0.0:
                    continue
                air = past
                if not metal[air:].any():
                    continue
                gap = float(np.argmax(metal[air:])) * step
                if gap > worst:
                    worst, where = gap, tuple(points[air])
    if where is not None:
        return Finding(
            "rib ends",
            "reject",
            f"a {worst:.0f} mm finger of sand between a rib's end and the metal ahead of it",
            rule,
            assumed,
            where,
            worst,
        )
    return Finding(
        "rib ends", "pass", "every rib end meets what is ahead of it or stands clear", rule, assumed
    )


def _sections(
    base: Field, window: Window, design: Composition, ribs: list, rules: Rules
) -> list[Finding]:
    """The thickest section at each junction against the wall it joins, and each rib against that
    wall. By distance transform, so to the nearest voxel."""
    spot_text, spot_assumed = rules.source("thick_spot")
    wall_text, wall_assumed = rules.source("rib_to_wall")
    spot_rule = f"junction section <= {rules.thick_spot:g} x the wall ({spot_text})"
    wall_rule = f"rib thickness <= {rules.rib_to_wall:g} x the wall ({wall_text})"
    touched, a, b = design.touched, design.part, design.ribs
    if touched is None or not touched.size:
        return [
            Finding("thick spots", "pass", "no junctions", spot_rule, spot_assumed),
            Finding("rib against wall", "pass", "no junctions", wall_rule, wall_assumed),
        ]
    spacing = window.grid.spacing_mm
    root = (np.abs(a) < rules.root_fillet_mm) & (np.abs(b) < rules.root_fillet_mm)
    if not root.any():
        return [
            Finding("thick spots", "pass", "no rib meets the part", spot_rule, spot_assumed),
            Finding("rib against wall", "pass", "no rib meets the part", wall_rule, wall_assumed),
        ]
    grown = int(math.ceil(3 * max(r.thickness_mm for r in ribs) / spacing))
    box, lo = _box_around(window.grid.shape, touched[root], grown)
    box_cells = np.ravel_multi_index(
        tuple(
            g.ravel()
            for g in np.meshgrid(*[np.arange(s.start, s.stop) for s in box], indexing="ij")
        ),
        window.grid.shape,
    )
    sub = np.stack(np.unravel_index(window.samples_of(box_cells), base.grid.shape), axis=1)
    shape = window.grid.shape
    shape_box = tuple(s.stop - s.start for s in box)
    design_solid = design.field.inside[tuple(sub.T)].reshape(shape_box)
    base_solid = base.inside[tuple(sub.T)].reshape(shape_box)
    # A pad is the wall made thicker where a rib meets it: measured as the wall.
    for pad in (r for r in ribs if getattr(r, "pad", False)):
        _mark(window, box, base_solid, pad)
    design_depth = ndimage.distance_transform_edt(design_solid) * spacing
    base_depth = ndimage.distance_transform_edt(base_solid) * spacing
    cells = np.stack(np.unravel_index(touched[root], shape), axis=1) - lo
    owner = design.nearest[root]

    # The wall a rib stands on is measured through the part beneath its root - every part cell
    # within one and a half rib thicknesses of the root, each credited to the nearest root cell's
    # rib. A rib only reaches a voxel into the metal, so its own cells cannot see the wall's depth.
    roots = np.zeros(shape_box, dtype=bool)
    roots[tuple(cells.T)] = True
    labels = np.full(shape_box, -1, dtype=np.int64)
    labels[tuple(cells.T)] = owner
    away, nearest_root = ndimage.distance_transform_edt(~roots, return_indices=True)
    reach = 1.5 * max(r.thickness_mm for r in ribs) / spacing
    beneath_mask = base_solid & (away <= reach)
    beneath_owner = labels[tuple(nearest_root[:, beneath_mask])]
    beneath_depth = base_depth[beneath_mask]

    worst_spot, worst_wall = (0.0, None), (math.inf, None, None)
    for index in np.unique(owner):
        if getattr(ribs[index], "pad", False):
            continue
        mine = cells[owner == index]
        depth = beneath_depth[beneath_owner == index]
        # The wall: the deepest the part goes under where this rib joins it.
        wall = 2.0 * float(depth.max()) if depth.size else 0.0
        section = 2.0 * float(design_depth[tuple(mine.T)].max()) if mine.size else 0.0
        if wall > 0.0:
            ratio = section / wall
            if ratio > worst_spot[0]:
                worst_spot = (
                    ratio,
                    _centre_of(window, np.ravel_multi_index((mine + lo).T, shape)[:1]),
                )
            margin = rules.rib_to_wall * wall - ribs[index].thickness_mm
            if margin < worst_wall[0]:
                worst_wall = (margin, wall, ribs[index].thickness_mm)

    ratio, where = worst_spot
    spot = (
        Finding(
            "thick spots",
            "warn",
            f"a junction {ratio:.1f}x the wall beside it",
            spot_rule,
            spot_assumed,
            where,
            ratio,
        )
        if ratio > rules.thick_spot
        else Finding(
            "thick spots",
            "pass",
            f"thickest junction {ratio:.1f}x its wall",
            spot_rule,
            spot_assumed,
            value=ratio,
        )
    )
    margin, wall, thickness = worst_wall
    against = (
        Finding(
            "rib against wall",
            "warn",
            f"a {thickness:g} mm rib on a {wall:.0f} mm wall",
            wall_rule,
            wall_assumed,
            value=wall,
        )
        if wall is not None and margin < 0.0
        else Finding(
            "rib against wall",
            "pass",
            "every rib thinner than its wall allows",
            wall_rule,
            wall_assumed,
        )
    )
    return [spot, against]


def _mark(window: Window, box: tuple[slice, ...], solid: np.ndarray, shape) -> None:
    """Mark in ``solid`` - a box of the window's cells - every cell inside ``shape``."""
    lo, hi = shape.bounds()
    origin = np.asarray(window.grid.origin)
    spacing = window.grid.spacing_mm
    first = [max(int(np.floor((lo[a] - origin[a]) / spacing)), box[a].start) for a in range(3)]
    last = [min(int(np.ceil((hi[a] - origin[a]) / spacing)) + 1, box[a].stop) for a in range(3)]
    if any(f >= t for f, t in zip(first, last, strict=True)):
        return
    axes = [np.arange(f, t) for f, t in zip(first, last, strict=True)]
    index = np.stack([g.ravel() for g in np.meshgrid(*axes, indexing="ij")], axis=1)
    inside = shape.distance(window.grid.centres(np.ravel_multi_index(index.T, window.grid.shape)))
    local = index[inside < 0.0] - np.array([b.start for b in box])
    solid[tuple(local.T)] = True


def _surface(surface: Surface) -> Finding:
    rule = "closed and oriented, every edge in exactly two triangles"
    boundary, non_manifold, winding = surface.faults
    if surface.faults != (0, 0, 0):
        return Finding(
            "surface",
            "reject",
            f"{boundary} open, {non_manifold} non-manifold, {winding} mis-wound edges",
            rule,
            False,
        )
    return Finding("surface", "pass", f"closed, {surface.n_triangles:,} triangles", rule, False)


# --- helpers ------------------------------------------------------------------------------------


def _plan(rib) -> np.ndarray:
    """A rib's line in the plane square to its pull, as a polyline of 3D points on its root."""
    if isinstance(rib, ArcRib):
        centre, _, e1, e2, _ = rib._frame()
        span = (rib.theta_to_deg - rib.theta_from_deg) % 360.0 or 360.0
        angles = np.radians(rib.theta_from_deg + np.linspace(0.0, span, 65))
        return centre + rib.radius_mm * (
            np.cos(angles)[:, None] * e1 + np.sin(angles)[:, None] * e2
        )
    return np.asarray([rib.start, rib.end], dtype=float)


def _junction(rib, rules: Rules, radius: float | None = None) -> float:
    """How far from where a rib meets what it ends on its junction reaches: a root fillet and a
    thickness - where spokes about one boss close in on each other, as they may."""
    if radius is None:
        radius = rules.root_fillet_mm
    if radius is None:
        radius = rib.thickness_mm / 2.0
    return radius + rib.thickness_mm


def _exposed(base: Field, rib, trim: float = 0.0) -> list[np.ndarray]:
    """The stretches of a rib's line whose mid-height stands in open air, as polylines - each less
    ``trim`` at both ends, and none shorter than that."""
    line = _plan(rib)
    step = base.grid.spacing_mm
    points = []
    for a, b in zip(line[:-1], line[1:], strict=True):
        count = max(int(np.linalg.norm(b - a) / step), 1)
        points.append(a + np.linspace(0.0, 1.0, count, endpoint=False)[:, None] * (b - a))
    points.append(line[-1:])
    points = np.concatenate(points)
    up = np.asarray(rib.pull, dtype=float)
    up = up / np.linalg.norm(up)
    along = np.linspace(0.0, 1.0, len(points))
    open_air = base.sample(points + 0.5 * rib.height_at(along)[:, None] * up) > 0.0
    edges = np.flatnonzero(np.diff(np.concatenate([[0], open_air.astype(int), [0]])))
    runs = [
        points[start:stop]
        for start, stop in zip(edges[0::2], edges[1::2], strict=True)
        if stop - start >= 2
    ]
    if isinstance(rib, ArcRib):
        return runs
    # A straight rib's stretch in the open is one straight line: its two ends say all of it.
    out = []
    for run in runs:
        a, b = run[0], run[-1]
        length = float(np.linalg.norm(b - a))
        if length <= 2.0 * trim:
            continue
        step = (b - a) * (trim / length) if length else 0.0
        out.append(np.array([a + step, b - step]))
    return out


def _polyline_distance(p: np.ndarray, q: np.ndarray) -> tuple[float, np.ndarray]:
    """The least distance between two polylines, and the midpoint of where it is."""
    best, where = math.inf, None
    for i in range(len(p) - 1):
        for j in range(len(q) - 1):
            d, a, b = _segment_distance(p[i], p[i + 1], q[j], q[j + 1])
            if d < best:
                best, where = d, (a + b) / 2.0
    return best, where


def _segment_distance(p0, p1, q0, q1) -> tuple[float, np.ndarray, np.ndarray]:
    u, v, w = p1 - p0, q1 - q0, p0 - q0
    a, b, c, d, e = u @ u, u @ v, v @ v, u @ w, v @ w
    denominator = a * c - b * b
    s = 0.0 if denominator < 1e-12 else float(np.clip((b * e - c * d) / denominator, 0.0, 1.0))
    t = float(np.clip((b * s + e) / c, 0.0, 1.0)) if c > 1e-12 else 0.0
    s = float(np.clip((b * t - d) / a, 0.0, 1.0)) if a > 1e-12 else 0.0
    a_point, b_point = p0 + s * u, q0 + t * v
    return float(np.linalg.norm(a_point - b_point)), a_point, b_point


def _tips(rib, spacing: float) -> tuple[np.ndarray, np.ndarray]:
    """Points along a rib's free edge, a little inside it, and its pull direction."""
    if isinstance(rib, ArcRib):
        centre, _, e1, e2, up = rib._frame()
        span = (rib.theta_to_deg - rib.theta_from_deg) % 360.0 or 360.0
        count = max(int(math.radians(span) * rib.radius_mm / (2 * spacing)), 2)
        angles = np.radians(rib.theta_from_deg + np.linspace(0.0, span, count))
        line = centre + rib.radius_mm * (
            np.cos(angles)[:, None] * e1 + np.sin(angles)[:, None] * e2
        )
    else:
        origin, along, _, up, length = rib.frame()
        count = max(int(length / (2 * spacing)), 2)
        line = origin + np.linspace(0.0, length, count)[:, None] * along
    heights = rib.height_at(np.linspace(0.0, 1.0, len(line)))
    return line + (heights - 0.5 * spacing)[:, None] * up, up


def _trilinear(window: Window, values: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Values stored per window cell, interpolated at arbitrary points inside the window."""
    grid = window.grid
    shape = np.asarray(grid.shape)
    u = (points - np.asarray(grid.origin)) / grid.spacing_mm
    base = np.clip(np.floor(u).astype(np.int64), 0, shape - 2)
    f = np.clip(u - base, 0.0, 1.0)
    table = values.reshape(*grid.shape, -1)
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                weight = (
                    (f[:, 0] if dx else 1 - f[:, 0])
                    * (f[:, 1] if dy else 1 - f[:, 1])
                    * (f[:, 2] if dz else 1 - f[:, 2])
                )
                corner = table[base[:, 0] + dx, base[:, 1] + dy, base[:, 2] + dz]
                out = out + weight[:, None] * corner
    return out[:, 0] if out.shape[1] == 1 else out


def _nearest_cell(window: Window, points: np.ndarray) -> np.ndarray:
    """The window cell nearest each point."""
    index = np.rint((points - np.asarray(window.grid.origin)) / window.grid.spacing_mm).astype(
        np.int64
    )
    index = np.clip(index, 0, np.asarray(window.grid.shape) - 1)
    return np.ravel_multi_index(tuple(index.T), window.grid.shape)


def _unit(v: np.ndarray) -> np.ndarray:
    length = np.linalg.norm(v, axis=1, keepdims=True)
    return np.divide(v, length, out=np.zeros_like(v), where=length > 1e-12)


def _box_around(shape: tuple, flat: np.ndarray, grow: int) -> tuple[tuple[slice, ...], np.ndarray]:
    index = np.stack(np.unravel_index(flat, shape), axis=1)
    lo = np.maximum(index.min(axis=0) - grow, 0)
    hi = np.minimum(index.max(axis=0) + grow + 1, np.asarray(shape))
    return tuple(slice(int(a), int(b)) for a, b in zip(lo, hi, strict=True)), lo


def _centre(base: Field, index: np.ndarray) -> tuple[float, float, float]:
    flat = np.ravel_multi_index(index.T, base.grid.shape)
    return tuple(float(v) for v in base.grid.centres(flat).mean(axis=0))


def _centre_of(window: Window, cells: np.ndarray) -> tuple[float, float, float]:
    return tuple(float(v) for v in window.grid.centres(cells).mean(axis=0))
