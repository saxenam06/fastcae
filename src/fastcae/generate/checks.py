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
from dataclasses import dataclass

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
) -> list[Finding]:
    """Every check, on one design."""
    return [
        _protected(base, window, design),
        _grid_edge(window, design),
        _floating(base, design),
        _thickness(ribs, base.grid.spacing_mm, rules),
        _gaps(base, ribs, rules),
        _fillet(window, design, ribs, surface, rules),
        _bridging(window, design, rules),
        _clipped(window, design),
        _release(base, design, ribs, rules),
        *_sections(base, window, design, ribs, rules),
        _surface(surface),
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


def _thickness(ribs: list, spacing: float, rules: Rules) -> Finding:
    low, high = rules.thickness_mm
    text, assumed = rules.source("thickness_mm")
    rule = f"{low:g}-{high:g} mm ({text}); at least 4 voxels"
    bad = [r for r in ribs if not low <= r.thickness_mm <= high or r.thickness_mm < 4 * spacing]
    if bad:
        return Finding(
            "rib thickness",
            "reject",
            f"{bad[0].thickness_mm:g} mm is outside the rule",
            rule,
            assumed,
            value=bad[0].thickness_mm,
        )
    return Finding("rib thickness", "pass", f"{len(ribs)} ribs inside the window", rule, assumed)


def _gaps(base: Field, ribs: list, rules: Rules) -> Finding:
    text, assumed = rules.source("root_gap")
    rule = f"clear gap between ribs >= {rules.root_gap:g} x thickness ({text})"
    if len(ribs) < 2:
        return Finding("root gap", "pass", "one rib", rule, assumed)
    # Only where a rib stands in the open: the stretch that runs into a wall or boss is trimmed
    # away, and spokes converging inside a boss are not a gap anybody casts.
    pieces = [_exposed(base, r) for r in ribs]
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
    window: Window, design: Composition, ribs: list, surface: Surface, rules: Rules
) -> Finding:
    target, floor = rules.root_fillet_mm, rules.fillet_floor_mm
    text, assumed = rules.source("fillet_floor_mm")
    rule = (
        f"achieved radius >= R{floor:g} ({text}); "
        f"within {rules.fillet_tolerance:.0%} of R{target:g}"
    )

    grid = window.grid
    lo = np.asarray(grid.origin)
    hi = lo + (np.asarray(grid.shape) - 1) * grid.spacing_mm
    v = surface.vertices
    inside = np.all((v >= lo) & (v <= hi), axis=1)
    v = v[inside]
    a = _trilinear(window, window.part, v)
    near = a < 2.0 * target
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
    k = target * (1.0 - cosine)
    on = (a > 0.05 * k) & (b > 0.05 * k) & (a < 0.95 * k) & (b < 0.95 * k) & (cosine < 0.9)
    if on.sum() < 10:
        return Finding("root fillet", "warn", "too little fillet surface to measure", rule, assumed)
    radius = (a[on] + b[on] + np.sqrt(2.0 * a[on] * b[on])) / (1.0 - cosine[on])
    per_rib = [
        np.median(radius[owner[on] == i])
        for i in np.unique(owner[on])
        if (owner[on] == i).sum() >= 10
    ]
    achieved = float(min(per_rib)) if per_rib else float(np.median(radius))
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


def _release(base: Field, design: Composition, ribs: list, rules: Rules) -> Finding:
    low, high = rules.draft_deg
    text, assumed = rules.source("draft_deg")
    rule = f"draft {low:g}-{high:g} deg ({text}); every rib face visible along the pull"
    for rib in ribs:
        if not low <= rib.draft_deg <= high:
            return Finding("mould release", "reject", f"draft {rib.draft_deg:g} deg", rule, assumed)

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


def _exposed(base: Field, rib) -> list[np.ndarray]:
    """The stretches of a rib's line whose mid-height stands in open air, as polylines."""
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
    return [
        points[start:stop]
        for start, stop in zip(edges[0::2], edges[1::2], strict=True)
        if stop - start >= 2
    ]


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
