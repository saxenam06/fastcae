"""Checks: every design comes out pass, warn or reject, with a reason and a place.

A blended shape always builds; it can still be quietly wrong. These are the ways it can be, each
measured on the design as built - its field, and its surface where one is drawn - never on what was
asked for. Every finding names the rule it used and whether that rule is assumed, so a threshold
nobody has confirmed is never presented as one somebody has, and says how long it took.

**The fillet that was actually made.** On a fillet surface the distances to the part and to the rib,
``a`` and ``b``, satisfy ``(k - a)^2 + (k - b)^2 = k^2`` - so every point of the design's surface on
a fillet says what ``k``, and so what radius, it was built to: ``k = a + b + sqrt(2ab)``, and
``R = k / (1 - n_a . n_b)``. The points are read off the field - where its sign changes between two
neighbouring cells - so the radius is the one the field holds, grid error and all, whether or not
a surface is ever drawn.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
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
    seconds: float | None = None
    """How long the check took, when it was timed - two findings of one check share its time."""


def timed(run: Callable[..., Finding | list[Finding]], *args: Any) -> list[Finding]:
    """A check run, its findings each saying how long it took."""
    started = time.perf_counter()
    found = run(*args)
    seconds = round(time.perf_counter() - started, 3)
    return [replace(f, seconds=seconds) for f in (found if isinstance(found, list) else [found])]


def check(
    base: Field,
    window: Window,
    design: Composition,
    ribs: list,
    surface: Surface | None,
    rules: Rules,
    owners: dict | None = None,
) -> list[Finding]:
    """Every check of ribs, on one design, each timed. ``owners`` says which block each rib is of,
    for the rules each block has of its own. ``surface`` is the design's surface where one was
    drawn - checked for closure - or None: every other check reads the field, and the composition
    carries how far the design moved the part's faces, so a fillet is read where they now are."""
    owners = owners or {}
    radii = {r: float(rules.of("root_fillet_mm", owners.get(r))) for r in ribs}
    ratios = {r: float(rules.of("root_gap", owners.get(r))) for r in ribs}
    # Mould release waits for the pull: with no direction the part leaves its mould along, and no
    # cores forming the pockets inside, it has nothing true to say.
    out = [
        *timed(_protected, base, window, design),
        *timed(_grid_edge, window, design),
        *timed(_floating, base, design),
        *timed(_thickness, ribs, base.grid.spacing_mm, rules, owners),
        *timed(_gaps, base, ribs, rules, radii, ratios),
        *timed(_fillet, window, design, ribs, rules, radii),
        *timed(_bridging, window, design, rules),
        *timed(_clipped, window, design),
        *timed(_ends, base, design, ribs, rules),
        *timed(_sections, base, window, design, ribs, rules),
    ]
    if surface is not None:
        out += timed(_surface, surface)
    return out


def described(rules: Rules | None = None) -> list[dict[str, str]]:
    """Every check a built design goes through and what it holds the design to, in words - as the
    pipeline shows them."""
    r = rules or Rules()
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
            "rule": f"a clear gap of {r.root_gap:g} x the thinner rib between rib footprints in "
            "the open - each variant's own where it says - and no wedge of sand where two meet",
        },
        {
            "name": "root fillet",
            "rule": "no smaller than the smallest radius the study allows, and within "
            f"{r.fillet_tolerance:.0%} of the radius its block asks for - read off the field",
        },
        {
            "name": "rib ends",
            "rule": "each rib's end meets the metal ahead of it, or stops at least "
            f"{r.root_gap:g} x its thickness short of it - no finger of sand between",
        },
        {"name": "blend bridging", "rule": "fillet material only where a rib meets the part"},
        {"name": "blend clipped", "rule": "no fillet cut short by a protected area"},
        {
            "name": "thick spots",
            "rule": f"the section at a junction at most {r.thick_spot:g} x the wall beside it",
        },
        {
            "name": "rib against wall",
            "rule": f"a rib at most {r.rib_to_wall:g} x the wall it joins",
        },
        {
            "name": "holes through",
            "rule": "every hole open from one side of its plate to the other",
        },
        {
            "name": "surface",
            "rule": "the design's surface closed, with no stray edges - where a surface is drawn",
        },
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
    # Every piece at once: which touch the part, and how big each is.
    attached = set(np.unique(labels[touching & (labels > 0)]).tolist())
    loose = [n for n in range(1, count + 1) if n not in attached]
    if loose:
        counted = np.bincount(labels.ravel(), minlength=count + 1)
        sizes = [int(counted[n]) for n in loose]
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


def _gaps(
    base: Field,
    ribs: list,
    rules: Rules,
    radii: dict | None = None,
    ratios: dict | None = None,
) -> Finding:
    """Room for the sand between ribs, measured between their footprints, and no narrow wedge of
    it where two meet. ``radii``, when given, is each rib's own root fillet; ``ratios`` each rib's
    own root gap; else the rules'."""
    ribs = _ribs_only(ribs)
    text, assumed = rules.source("root_gap")
    rule = (
        f"clear gap between rib footprints >= {rules.root_gap:g} x the thinner rib, and no wedge "
        f"of sand longer than that where two meet ({text})"
    )
    if len(ribs) < 2:
        return Finding("root gap", "pass", "one rib", rule, assumed)
    meetings, _ = meetings_of(base, ribs, rules, radii, ratios)
    wedges = [m for m in meetings if m.kind == "wedge"]
    if wedges:
        worst = min(wedges, key=lambda m: m.value)
        return Finding(
            "root gap",
            "reject",
            f"two ribs meet {worst.value:.0f}° apart - a wedge of sand too narrow to cast",
            rule,
            assumed,
            tuple(worst.where),
            worst.value,
        )
    gaps = [m for m in meetings if m.kind == "gap"]
    if gaps:
        worst = min(gaps, key=lambda m: m.value)
        return Finding(
            "root gap",
            "reject",
            f"a {worst.value:.1f} mm gap between rib footprints",
            rule,
            assumed,
            tuple(worst.where),
            worst.value,
        )
    return Finding("root gap", "pass", "every pair of ribs leaves room for the sand", rule, assumed)


@dataclass(frozen=True)
class Meeting:
    """Two ribs, by their place among the ribs, that break the root gap between them: too close
    side by side (``gap``, the gap in mm), or meeting at an angle too shallow for the sand between
    them (``wedge``, the angle in degrees)."""

    i: int
    j: int
    kind: str
    value: float
    where: np.ndarray = field(compare=False, default_factory=lambda: np.zeros(3))


@dataclass
class Junction:
    """Where ribs meet or cross, and how many arms each rib gives there: two for one passing
    through, one for one ending there."""

    where: np.ndarray
    arms: dict[int, int] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return sum(self.arms.values())


def meetings_of(
    base: Field,
    ribs: list,
    rules: Rules,
    radii: dict | None = None,
    ratios: dict | None = None,
) -> tuple[list[Meeting], list[Junction]]:
    """Every pair of ribs that breaks the root gap, and every point where ribs meet.

    Only where a rib stands in the open: the stretch that runs into a wall or boss is trimmed away,
    and spokes converging inside a boss are not a gap anybody casts - nor are they in the junction
    at either end, a fillet and a thickness long, where ribs meet what they end on.

    Two ribs whose footprints do not touch need the root gap between them. Two whose footprints
    touch meet: the sand between two of their arms is a wedge, rounded at its tip by the fillet,
    widening from there; where it is narrower than the root gap for longer than the root gap is
    wide, it is a finger of sand too thin to stand - the pair is a wedge.
    """
    pieces = [_exposed(base, r, _junction(r, rules, (radii or {}).get(r))) for r in ribs]
    plans = [_plan(r) for r in ribs]
    meetings: list[Meeting] = []
    junctions: list[Junction] = []
    for i in range(len(ribs)):
        for j in range(i + 1, len(ribs)):
            # Where their bodies cross or touch - sides, not fillets - they meet; where only their
            # fillets overlap, the sand between them is a slot, and it is a gap like any other.
            sides = (ribs[i].thickness_mm + ribs[j].thickness_mm) / 2.0
            reach = _half(ribs[i]) + _half(ribs[j])
            ratio = max(
                (ratios or {}).get(ribs[i], rules.root_gap),
                (ratios or {}).get(ribs[j], rules.root_gap),
            )
            room = ratio * min(ribs[i].thickness_mm, ribs[j].thickness_mm)
            whole, _ = _polyline_distance(plans[i], plans[j])
            met = _met(plans[i], plans[j], reach) if whole <= sides else None
            fillet = min(_fillet_of(ribs[i], radii), _fillet_of(ribs[j], radii))
            # Meeting in the open only: spokes whose lines cross inside the boss they turn about
            # meet in metal, and are held apart where they stand in the open.
            if met is not None and _in_open(base, met[0], ribs[i], ribs[j]):
                apex, arms_i, arms_j, angle = met
                _join(junctions, apex, i, len(arms_i), reach)
                _join(junctions, apex, j, len(arms_j), reach)
                if _wedged(angle, room, fillet):
                    meetings.append(Meeting(i, j, "wedge", angle, apex))
                continue
            touching = None
            for line_i in pieces[i]:
                for line_j in pieces[j]:
                    distance, point = _polyline_distance(line_i, line_j)
                    if distance <= sides:
                        touching = touching or (line_i, line_j, point)
                        continue
                    if distance - reach < room:
                        meetings.append(Meeting(i, j, "gap", distance - reach, point))
            if touching is not None:
                # Their bodies touch in the open, though their lines cross in metal - or not at
                # all: they meet there, at the angle between them.
                line_i, line_j, point = touching
                angle = _angle_between(line_i, line_j, point)
                if _wedged(angle, room, fillet):
                    meetings.append(Meeting(i, j, "wedge", angle, point))
    return meetings, junctions


def _wedged(angle_deg: float, room: float, fillet: float) -> bool:
    """Whether two ribs meeting ``angle_deg`` apart are too close for too long: a finger of sand
    narrower than the root gap for longer than the root gap is wide - or, where the fillets round
    their corner fill it, a lump of metal that long, two ribs run into one."""
    return _finger(angle_deg, room, fillet) > room or _merged(angle_deg, fillet) > room


def _merged(angle_deg: float, fillet: float) -> float:
    """How far from where two arms meet ``angle_deg`` apart the fillet rounding their corner fills
    between them: the further, the shallower the angle."""
    half = math.radians(max(angle_deg, 0.0) / 2.0)
    if half < 1e-6:
        return math.inf
    return fillet / math.tan(half)


def _angle_between(p: np.ndarray, q: np.ndarray, near: np.ndarray) -> float:
    """The least angle between two stretches of rib, by their pieces nearest ``near``."""

    def way(line: np.ndarray) -> np.ndarray:
        if len(line) < 2:
            return np.array([1.0, 0.0])
        middles = (line[:-1] + line[1:]) / 2.0
        k = int(np.argmin(np.linalg.norm(middles - np.asarray(near)[: line.shape[1]], axis=1)))
        step = line[k + 1] - line[k]
        return step / max(float(np.linalg.norm(step)), 1e-12)

    cosine = abs(float(np.clip(way(p) @ way(q), -1.0, 1.0)))
    return math.degrees(math.acos(cosine))


def _in_open(base: Field, apex: np.ndarray, a, b) -> bool:
    """Whether two ribs meeting at ``apex`` meet in open air - halfway up the lower of them - not
    inside the part."""
    up = np.asarray(a.pull, dtype=float)
    up = up / np.linalg.norm(up)
    height = 0.5 * min(
        max(a.height_at(np.array([0.0, 1.0]))), max(b.height_at(np.array([0.0, 1.0])))
    )
    return bool(base.sample((np.asarray(apex, dtype=float) + height * up).reshape(1, 3))[0] > 0.0)


def _half(rib) -> float:
    """Half a rib's footprint: its metal where it stands, fillet and all."""
    return float(getattr(rib, "footprint_mm", rib.thickness_mm / 2.0))


def _fillet_of(rib, radii: dict | None) -> float:
    own = (radii or {}).get(rib)
    return float(own if own is not None else getattr(rib, "root_fillet_mm", 0.0))


def _met(p: np.ndarray, q: np.ndarray, reach: float):
    """Where two straight stretches of rib meet - the point their lines cross - the directions of
    each one's arms from there, and the least angle between an arm of one and an arm of the other.
    None for curved stretches, or lines that run side by side without crossing."""
    if len(p) != 2 or len(q) != 2:
        return None
    u, v = p[1] - p[0], q[1] - q[0]
    lu, lv = float(np.linalg.norm(u)), float(np.linalg.norm(v))
    if lu < 1e-9 or lv < 1e-9:
        return None
    u, v = u / lu, v / lv
    # Solve p0 + s u = q0 + t v in the plane the two span.
    a = np.stack([u, -v], axis=1)
    solution, *_ = np.linalg.lstsq(a, q[0] - p[0], rcond=None)
    if abs(float(u @ v)) > math.cos(math.radians(1.0)):
        # Side by side, overlapping: one wedge of no angle at all.
        apex = (p[0] + p[1] + q[0] + q[1]) / 4.0
        return apex, [u], [v], 0.0
    apex = p[0] + float(solution[0]) * u

    def arms(line: np.ndarray) -> list[np.ndarray]:
        out = []
        for end in line:
            away = end - apex
            if float(np.linalg.norm(away)) > reach:
                out.append(away / float(np.linalg.norm(away)))
        return out

    arms_p, arms_q = arms(p), arms(q)
    if not arms_p or not arms_q:
        return None
    angle = min(
        math.degrees(math.acos(float(np.clip(a_ @ b_, -1.0, 1.0))))
        for a_ in arms_p
        for b_ in arms_q
    )
    return apex, arms_p, arms_q, angle


def _finger(angle_deg: float, room: float, fillet: float) -> float:
    """How long the sand between two arms meeting at ``angle_deg`` stays narrower than ``room``:
    from where the fillet rounding their corner ends, two fillets wide, to where it is ``room``
    wide. Nothing when a fillet that big already fills it."""
    if room <= 2.0 * fillet:
        return 0.0
    half = math.radians(max(angle_deg, 0.0) / 2.0)
    if half < 1e-6:
        return math.inf
    return (room - 2.0 * fillet) / (2.0 * math.tan(half))


def _join(junctions: list[Junction], where: np.ndarray, rib: int, arms: int, reach: float) -> None:
    """A rib's arms at a point where ribs meet - the junction already there, or a new one."""
    for junction in junctions:
        if float(np.linalg.norm(junction.where - where)) <= reach:
            junction.arms[rib] = max(junction.arms.get(rib, 0), arms)
            return
    junctions.append(Junction(where=np.asarray(where, dtype=float), arms={rib: arms}))


def _fillet(
    window: Window,
    design: Composition,
    ribs: list,
    rules: Rules,
    radii: dict | None = None,
) -> Finding:
    """``radii``, when given, is the root fillet each rib was made with; else the rules'. The part's
    distance is the composition's own - with whatever the design moved its faces by taken off, so a
    fillet is read against the face where it now is."""
    targets = np.array([(radii or {}).get(r, rules.root_fillet_mm) for r in ribs], dtype=float)
    floor = rules.fillet_floor_mm
    text, assumed = rules.source("fillet_floor_mm")
    aim = f"R{targets[0]:g}" if np.allclose(targets, targets[0]) else "each rib's own radius"
    rule = f"achieved radius >= R{floor:g} ({text}); within {rules.fillet_tolerance:.0%} of {aim}"

    v, a, n_a, owner = _on_fillets(window, design, 2.0 * float(targets.max()))
    if not v.size:
        return Finding("root fillet", "warn", "no fillet found to measure", rule, assumed)
    b = np.empty(len(v))
    n_b = np.zeros_like(v)
    for index in np.unique(owner):
        rows = owner == index
        b[rows] = ribs[index].distance(v[rows])
        n_b[rows] = ribs[index].normal(v[rows])
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


def _on_fillets(
    window: Window, design: Composition, reach: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Points of the design's surface where a fillet may be - within ``reach`` of both the part and
    a rib - read off its field: where its sign changes between two neighbouring cells of the
    window, the change found between their values. With each, its distance to the part as the
    design leaves it, the part's normal there, and which rib is nearest."""
    empty = (np.zeros((0, 3)), np.zeros(0), np.zeros((0, 3)), np.zeros(0, dtype=np.int64))
    touched, a_all, b_all = design.touched, design.part, design.ribs
    if touched is None or a_all is None or b_all is None or design.nearest is None:
        return empty
    grid = window.grid
    spacing = grid.spacing_mm
    close = (a_all < reach + spacing) & (b_all < reach + spacing)
    cells = touched[close]
    if not cells.size:
        return empty
    a_of, owner_of = a_all[close], design.nearest[close]
    samples = window.samples_of(cells)
    solid = design.field.inside.ravel()[samples]
    value = design.field.at(samples).astype(np.float64)
    shape = np.asarray(grid.shape)
    index = np.stack(np.unravel_index(cells, grid.shape), axis=1)
    strides = (int(shape[1] * shape[2]), int(shape[2]), 1)
    points, a, n_a, owner = [], [], [], []
    for axis in range(3):
        ahead = np.flatnonzero(index[:, axis] < shape[axis] - 1)
        after = cells[ahead] + strides[axis]
        position = np.clip(np.searchsorted(cells, after), 0, cells.size - 1)
        found = cells[position] == after
        i, j = ahead[found], position[found]
        crossing = solid[i] != solid[j]
        i, j = i[crossing], j[crossing]
        if not i.size:
            continue
        gap = value[i] - value[j]
        t = np.clip(np.divide(value[i], gap, out=np.full(i.size, 0.5), where=gap != 0.0), 0, 1)
        step = np.zeros(3)
        step[axis] = spacing
        points.append(grid.centres(cells[i]) + t[:, None] * step)
        a.append(a_of[i] + t * (a_of[j] - a_of[i]))
        n_a.append(window.normal_at(cells[i]))
        owner.append(owner_of[i])
    if not points:
        return empty
    return (
        np.concatenate(points),
        np.concatenate(a),
        np.concatenate(n_a),
        np.concatenate(owner).astype(np.int64),
    )


def holes_through(base: Field, field: Field, holes: list) -> Finding:
    """Every hole open all the way through its plate: along its axis, from over the plate's face
    to past its far side - where the part's metal under the hole ends - the design is air; and
    the part had metal there to cut."""
    rule = "every hole open from one side of its plate to the other"
    if not holes:
        return Finding("holes through", "pass", "no holes", rule, False)
    spacing = field.grid.spacing_mm
    blind, nothing = [], []
    for hole in holes:
        centre = np.asarray(hole.centre, dtype=float)
        axis = np.asarray(hole.axis, dtype=float)
        axis = axis / np.linalg.norm(axis)
        # From over the plate's face down its axis, as far again as the hole was cut: where the
        # part's metal under it starts, and where it ends - the plate's far side.
        along = np.arange(hole.above_mm, -2.0 * hole.depth_mm - spacing, -spacing / 2.0)
        points = centre + along[:, None] * axis
        metal = base.sample(points) < 0.0
        if not metal.any():
            nothing.append(centre)
            continue
        start = int(np.argmax(metal))
        after = np.flatnonzero(~metal[start:])
        if not after.size:
            blind.append(centre)
            continue
        stop = start + int(after[0])
        # Air all the way: the plate's face to its far side, a sample past each.
        through = slice(max(start - 1, 0), stop + 1)
        if (field.sample(points[through]) < 0.0).any():
            blind.append(centre)
    if blind:
        return Finding(
            "holes through",
            "reject",
            f"{len(blind)} of {len(holes)} holes closed somewhere along their axis",
            rule,
            False,
            tuple(float(v) for v in blind[0]),
        )
    if nothing:
        return Finding(
            "holes through",
            "reject",
            f"{len(nothing)} of {len(holes)} holes cut through no metal",
            rule,
            False,
            tuple(float(v) for v in nothing[0]),
        )
    return Finding("holes through", "pass", f"all {len(holes)} holes through", rule, False)


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

    # How far each cell of fillet is from where a rib runs into the part, cell to cell: the
    # nearest such cell, by a tree over them - what a distance transform of the box round them
    # all would say, for the cells asked about only.
    spacing = window.grid.spacing_mm
    limit = 2.0 * rules.root_fillet_mm + spacing
    cells = np.stack(np.unravel_index(touched[fillet], window.grid.shape), axis=1)
    if overlap.any():
        from scipy.spatial import cKDTree

        roots = np.stack(np.unravel_index(touched[overlap], window.grid.shape), axis=1)
        away, _ = cKDTree(roots).query(cells, k=1, distance_upper_bound=limit / spacing + 1.0)
        far = away * spacing > limit
    else:
        far = np.ones(len(cells), dtype=bool)
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
    shape = window.grid.shape
    cells = np.stack(np.unravel_index(touched[root], shape), axis=1)
    owner = design.nearest[root]
    worst_spot: tuple[float, Any] = (0.0, None)
    worst_wall: tuple[float, Any, Any] = (math.inf, None, None)
    # Each rib's junctions in a box of their own, grown as far as a section or the wall beneath
    # can matter; boxes that overlap are one - ribs that meet or cross are measured together, and
    # ribs far apart pay for the part round them, not for the box round them all.
    for box, lo in _boxes(cells, owner, grown, shape):
        mine = np.all((cells >= lo) & (cells < [s.stop for s in box]), axis=1)
        for index, ratio, where, margin, wall in _box_sections(
            base, window, design, ribs, rules, box, cells[mine] - lo, owner[mine]
        ):
            if wall > 0.0:
                if ratio > worst_spot[0]:
                    worst_spot = (ratio, where)
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


def _boxes(
    cells: np.ndarray, owner: np.ndarray, grown: int, shape: tuple[int, ...]
) -> list[tuple[tuple[slice, ...], np.ndarray]]:
    """A box round each rib's junction cells, grown by ``grown`` cells and held to the window;
    boxes that overlap merged into one, until none do."""
    top = np.asarray(shape)
    boxes = []
    for index in np.unique(owner):
        mine = cells[owner == index]
        boxes.append(
            [np.maximum(mine.min(axis=0) - grown, 0), np.minimum(mine.max(axis=0) + grown + 1, top)]
        )
    merged = True
    while merged:
        merged = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                (a_lo, a_hi), (b_lo, b_hi) = boxes[i], boxes[j]
                if np.all(a_lo < b_hi) and np.all(b_lo < a_hi):
                    boxes[i] = [np.minimum(a_lo, b_lo), np.maximum(a_hi, b_hi)]
                    del boxes[j]
                    merged = True
                    break
            if merged:
                break
    return [
        (tuple(slice(int(a), int(b)) for a, b in zip(lo, hi, strict=True)), lo) for lo, hi in boxes
    ]


def _box_sections(
    base: Field,
    window: Window,
    design: Composition,
    ribs: list,
    rules: Rules,
    box: tuple[slice, ...],
    cells: np.ndarray,
    owner: np.ndarray,
):
    """In one box of the window, each rib's thickest junction against the wall it joins: the rib,
    the ratio of the two and where, how far the rib is inside what the wall allows, and the wall.
    By distance transform, so to the nearest voxel."""
    spacing = window.grid.spacing_mm
    lo = np.array([s.start for s in box])
    shape_box = tuple(s.stop - s.start for s in box)
    # The window is a block of the base grid: the box, where it lies in that.
    at = tuple(
        slice(s.start + first, s.stop + first) for s, first in zip(box, window.first, strict=True)
    )
    design_solid = design.field.inside[at]
    base_solid = base.inside[at].copy()
    # A pad is the wall made thicker where a rib meets it: measured as the wall.
    for pad in (r for r in ribs if getattr(r, "pad", False)):
        _mark(window, box, base_solid, pad)

    # The wall a rib stands on is measured through the part beneath its root - every part cell
    # within one and a half rib thicknesses of the root, each credited to the nearest root cell's
    # rib. A rib only reaches a voxel into the metal, so its own cells cannot see the wall's depth.
    from scipy.spatial import cKDTree

    reach = 1.5 * max(r.thickness_mm for r in ribs) / spacing
    near_lo = np.maximum(cells.min(axis=0) - int(math.ceil(reach)), 0)
    near_hi = np.minimum(cells.max(axis=0) + int(math.ceil(reach)) + 1, shape_box)
    near = tuple(slice(int(a), int(b)) for a, b in zip(near_lo, near_hi, strict=True))
    candidates = np.argwhere(base_solid[near]) + near_lo
    away, nearest_root = cKDTree(cells).query(candidates, k=1, distance_upper_bound=reach + 1e-9)
    beneath = np.isfinite(away) & (away <= reach)
    beneath_owner = owner[nearest_root[beneath]]
    beneath_depth = _depth(base_solid, candidates[beneath]) * spacing
    design_depth = _depth(design_solid, cells) * spacing

    for index in np.unique(owner):
        if getattr(ribs[index], "pad", False):
            continue
        rows = owner == index
        mine = cells[rows]
        depth = beneath_depth[beneath_owner == index]
        # The wall: the deepest the part goes under where this rib joins it.
        wall = 2.0 * float(depth.max()) if depth.size else 0.0
        section = 2.0 * float(design_depth[rows].max()) if mine.size else 0.0
        ratio = section / wall if wall > 0.0 else 0.0
        where = _centre_of(window, np.ravel_multi_index((mine[:1] + lo).T, window.grid.shape))
        yield int(index), ratio, where, rules.rib_to_wall * wall - ribs[index].thickness_mm, wall


def _depth(solid: np.ndarray, points: np.ndarray) -> np.ndarray:
    """How deep each of ``points`` - cells of the box ``solid`` - lies in it: the distance, in
    cells, to the nearest cell of the box that is not solid; nothing for a point not in it. What a
    distance transform of the box says, asked of these cells only: the nearest cell not solid
    always borders the solid, so only those are looked among."""
    from scipy.spatial import cKDTree

    out = np.zeros(len(points))
    if not len(points):
        return out
    inside = solid[tuple(points.T)]
    edge = np.argwhere(ndimage.binary_dilation(solid) & ~solid)
    if not len(edge):
        out[inside] = float(np.linalg.norm(solid.shape))
        return out
    found, _ = cKDTree(edge).query(points[inside], k=1)
    out[inside] = found
    return out


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
