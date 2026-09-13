"""Repair: a design whose pieces break a rule between them, mended by leaving out the fewest.

Placing puts each variant's ribs and holes where its own rules allow. What no variant sees alone is
what the pieces do together - and a pattern can crowd itself: two ribs with no room for the sand
between them, two meeting at an angle too shallow to cast, a hole on a rib's fillet, four arms
crossing where a variant forbids it. Each is a conflict between pieces, and one choice of pieces to
leave out settles them all at once.

**CP-SAT makes that choice**: the fewest pieces left out; a rib takes its pads with it; where two
choices leave out as many, holes go before ribs. One worker and a fixed seed, so the same design is
always mended the same way. What a design has left out is said, piece by piece, with the rule it
broke - and its lines are drawn as left out, not as ribs.

What leaving pieces out cannot mend - a variant that made nothing, a rib too thick for its floor, a
wall thinned too far - is left to the screening that follows, and such a design is drawn again.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..spec import HoleSet, Placement
from .checks import Rules, meetings_of
from .field import Field
from .placement import Drilled, Placed, _kept_clear, _without, _without_holes, root_gap_of

# Why a piece was left out, in the words the verdict uses.
BROKE = {
    "gap": "root gap",
    "wedge": "a wedge of sand",
    "x": "an X crossing",
    "hole": "holes clear of ribs",
}

# How long the solver may think about one design, in seconds. A design is a few dozen pieces;
# it answers in milliseconds.
SECONDS = 5.0


@dataclass
class Repair:
    """A design mended: what it places now, and what was left out - each piece by its block,
    whether a rib or a hole, its place among them, and the rule it broke."""

    placed: dict[str, Placed | Drilled]
    left_out: list[dict[str, Any]] = field(default_factory=list)


def repair(
    base: Field,
    placements: list[Placement],
    holes: list[HoleSet],
    placed: dict[str, Placed | Drilled],
) -> Repair:
    """The design ``placed`` with the fewest pieces left out so no rule between them breaks - as
    it is, when none does."""
    ribs: list[tuple[str, int]] = []
    shapes = []
    radii: dict = {}
    ratios: dict = {}
    forbids: set[int] = set()
    for placement in placements:
        result = placed.get(placement.id)
        if not isinstance(result, Placed):
            continue
        for index, rib in enumerate(result.ribs):
            if placement.no_x:
                forbids.add(len(ribs))
            ribs.append((placement.id, index))
            shapes.append(rib)
            radii[rib] = placement.section.root_fillet_mm
            ratios[rib] = root_gap_of(placement)

    pairs: list[tuple[tuple, tuple, str]] = []
    crossings: list[list[tuple[tuple, int]]] = []
    if len(shapes) > 1:
        meetings, junctions = meetings_of(base, shapes, Rules(), radii, ratios)
        for meeting in meetings:
            pairs.append((("rib", meeting.i), ("rib", meeting.j), meeting.kind))
        for junction in junctions:
            if junction.count > 3 and forbids.intersection(junction.arms):
                crossings.append([(("rib", r), arms) for r, arms in junction.arms.items()])
    at = {rib: position for position, rib in enumerate(ribs)}
    for hole_set in holes:
        result = placed.get(hole_set.id)
        if not isinstance(result, Drilled) or not result.holes or result.frame is None:
            continue
        ligament = max(hole_set.ligament_mm, hole_set.clear_of_mm)
        for other in hole_set.clear_of:
            near = placed.get(other)
            if not isinstance(near, Placed):
                continue
            for index, rib in enumerate(near.ribs):
                keep = _kept_clear(rib, result.frame, 0.0, far_side=True)
                if keep is None or keep.low > result.band[1] or keep.high < result.band[0]:
                    continue
                for number, hole in enumerate(result.holes):
                    centre = result.frame.to_plane([hole.centre])[0]
                    if keep.gap(centre, centre, hole.radius_mm) < ligament - 0.5:
                        pairs.append(
                            (("hole", hole_set.id, number), ("rib", at[(other, index)]), "hole")
                        )
    if not pairs and not crossings:
        return Repair(placed=placed)

    kept = _choose(pairs, crossings)
    left_out: list[dict[str, Any]] = []
    why_of: dict[tuple, str] = {}
    for a, b, kind in pairs:
        for piece in (a, b):
            why_of.setdefault(piece, BROKE[kind])
    for crossing in crossings:
        for piece, _ in crossing:
            why_of.setdefault(piece, BROKE["x"])
    gone_ribs: dict[str, set[int]] = {}
    gone_holes: dict[str, set[int]] = {}
    for piece, keep in sorted(kept.items(), key=lambda item: str(item[0])):
        if keep:
            continue
        if piece[0] == "rib":
            block, index = ribs[piece[1]]
            gone_ribs.setdefault(block, set()).add(index)
            left_out.append({"block": block, "what": "rib", "index": index, "why": why_of[piece]})
        else:
            _, block, index = piece
            gone_holes.setdefault(block, set()).add(index)
            left_out.append({"block": block, "what": "hole", "index": index, "why": why_of[piece]})
    mended = dict(placed)
    for block, gone in gone_ribs.items():
        result = mended[block]
        assert isinstance(result, Placed)
        mended[block] = _without(result, gone, "left_out")
    for block, gone in gone_holes.items():
        result = mended[block]
        assert isinstance(result, Drilled)
        mended[block] = _without_holes(result, gone, "left_out")
    return Repair(placed=mended, left_out=left_out)


def _choose(
    pairs: list[tuple[tuple, tuple, str]], crossings: list[list[tuple[tuple, int]]]
) -> dict[tuple, bool]:
    """Which pieces to keep: every pair in conflict loses one, every crossing keeps at most three
    arms, the fewest pieces are left out - holes before ribs, where it is a tie."""
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    pieces = sorted({p for a, b, _ in pairs for p in (a, b)} | {p for c in crossings for p, _ in c})
    keep = {piece: model.NewBoolVar(f"keep{n}") for n, piece in enumerate(pieces)}
    for a, b, _ in pairs:
        model.Add(keep[a] + keep[b] <= 1)
    for crossing in crossings:
        model.Add(sum(arms * keep[piece] for piece, arms in crossing) <= 3)
    # Left out: a thousand a piece, and one more for a rib - so the fewest go, and of as many,
    # holes rather than ribs.
    model.Minimize(
        sum((1000 + (1 if piece[0] == "rib" else 0)) * (1 - keep[piece]) for piece in pieces)
    )
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = SECONDS
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # Leaving every piece in conflict out always settles them: never reached, but never wrong.
        return {piece: False for piece in pieces}
    return {piece: bool(solver.Value(keep[piece])) for piece in pieces}
