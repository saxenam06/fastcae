"""Placement: where one of an engineer's placements puts ribs on a part.

A placement names a **host** the ribs stand on, the **supports** they run between, and what they
**keep out** of. This turns that into ribs, and says what happened to every path it tried.

**Paths are drawn on the host's plane** by the layout - families of straight paths, or spokes out
from a feature's axis - laid only across where the host is, and walked in short steps. A rib can
only be where the path is over the host and clear of every keep-out, grown by half the rib's
thickness and the clearance asked for; keep-outs and gaps in the host cut a path into pieces.

**Each rib is a span.** Where a stretch of path ends, the walk carries on a little way, a few
millimetres above the host, to see what is there: metal belonging to a support, metal belonging to
something else, a keep-out, or nothing. A rib runs only between two supports - unless the placement
allows free ends - and is carried into each support so its end is a filleted junction, not a cut.
Nothing is trimmed on the grid, so nothing can pass through a wall.

**Height follows what a rib spans, end by end.** Each end is buried in what it meets, as deep as it
must be for its last few millimetres to stay inside the metal all the way up - a wall with draft
leans away from a rib as it rises, so the deeper the end, the taller the rib can stand there. Each
end is no taller than that, nor than any feature named as a cap, nor than a height given outright -
whichever is least - times the fraction asked for; the top runs straight from one end's height to
the other's, or is held level at the lower when the placement asks for that. Nor is it taller than
the open space over it: something standing over the path caps it too.

**With nothing under them, ribs are webs between what they join.** Webs that run from something
round - a bearing, a boss - stand along its axis; others along the direction the most of what they
join runs along, the pull first among equals. The paths are drawn on the plane square to that,
across the open space between what they join: where the part is not, in the pieces of open space
that reach two or more of them. **Each web hangs from the height of its own two ends**: every
height where what they join begins - one of each side, when there are two - is tried, lowest
first, and each path takes the first where it makes a web; a part whose walls step up and down is
joined all round. Each web runs from one of them to another, never from one to itself, and is
carried into both as any rib is.

**A rib is no thicker than the wall it meets allows.** Where a rib ends on a wall, the wall is
measured square through it, where the rib meets it - with whatever a design moves its faces by. A
wall thinner than the rib may meet is thickened round the rib's end by a pad, when the placement
allows pads - never to more than twice what it was - or the rib is not placed. **Nor thicker than
its floor allows**: the floor under a rib is measured under it, as the design leaves the floor, and
is never thickened for it - a rib too thick for its floor is left out, and says the rule it broke.

**Holes go through a plate on a lattice**, square or staggered, each a whole ligament of metal from
the next, from the plate's edges, from what they keep clear of, and from the ribs of blocks placed
before them - in three dimensions: a rib under the plate is as much in the way as one on it. A hole
over something standing under the plate, where it would cut into more than the plate, is not
placed.

**What a block reads off the part is read once.** Where a block's ribs stand, what they keep clear
of and what they end on do not change from one design to the next; a ``memo`` kept by the caller
holds them, so many designs of one study each pay only for their own paths.
"""

from __future__ import annotations

import copy
import json
import math
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .. import knowledge
from ..features import Feature, FeatureKind, FeatureSet, extent
from ..geometry.atlas import Atlas
from ..geometry.brep import Tessellation
from ..spec import HoleSet, Placement
from .field import Field
from .holes import Hole
from .ribs import Rib

# How far past the end of a stretch of path the walk looks for what the rib would meet, as a
# multiple of the root fillet: a wall stands where the fillet at its foot ends. And never less than
# room for the sand between metal - the root gap - so a rib ends on what is that near, or clear of
# it.
LOOK_PAST = 3.0

# A stretch shorter than this many rib thicknesses is a stub, not a rib.
SHORTEST = 2.0

# How deep a rib's end may go into what it meets, as a multiple of how deep it is buried at least:
# far enough to stay inside a wall with draft to the wall's top.
DEEPEST = 10.0

# The most a pad may thicken a wall, as a multiple of the wall: past that the rib is too thick for
# it, and a lump that size is a hot spot in the casting.
PAD_MOST = 1.0

# How much thicker than its floor allows a rib may be, in millimetres, and still stand on it: what
# measuring the floor through its facets can be off by - the margin screening allows too.
FLOOR_SLACK = 0.5

# A hole is over plain plate when the metal under its rim runs no deeper than this much of the
# metal under its middle - and a grid cell more.
UNDER_PLATE = 1.3

# Where a free line may cross the host: on a lattice this far apart, square to it.
FREE_STEP_MM = 5.0


@dataclass(frozen=True)
class HostFrame:
    """The host's plane: an origin on it, its outward normal, and two axes in it."""

    origin: np.ndarray
    normal: np.ndarray
    e1: np.ndarray
    e2: np.ndarray

    def to_plane(self, points: np.ndarray) -> np.ndarray:
        p = np.asarray(points, dtype=float) - self.origin
        return np.stack([p @ self.e1, p @ self.e2], axis=-1)

    def to_world(self, uv: np.ndarray, height: float | np.ndarray = 0.0) -> np.ndarray:
        uv = np.atleast_2d(uv)
        h = np.asarray(height, dtype=float).reshape(-1, 1) if np.ndim(height) else height
        return self.origin + uv[:, :1] * self.e1 + uv[:, 1:2] * self.e2 + h * self.normal


@dataclass
class Placed:
    """The ribs a placement made, and what happened to every path it tried."""

    ribs: list[Rib]
    spans: list[dict] = field(default_factory=list)
    paths: int = 0
    """How many paths the layout drew. Each becomes ribs, or is counted in ``dropped`` with why."""
    tried: list[dict] = field(default_factory=list)
    """Every stretch of path tried, as a line just off the host - ``a``, ``b`` - and what became
    of it: ``rib``, or why not. What the layout will do, to see before anything is made."""
    dropped: dict[str, int] = field(default_factory=dict)
    keep_outs: list[dict] = field(default_factory=list)
    caps: dict = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    ended_on: dict[str, int] = field(default_factory=dict)
    """What pieces that ended on something not named to run between ended on, by feature - what
    could be named to make ribs of them."""
    closed: dict[str, int] = field(default_factory=dict)
    """What the part keeps closed that pieces would have reached, by feature."""
    pads: list[Rib] = field(default_factory=list)
    """Walls thickened round the ends of ribs that met them thinner than they may be."""
    left_out: list[dict] = field(default_factory=list)
    """Ribs left out for a rule of their own - too thick for the floor they would stand on - each
    with ``what`` and ``why``, the rule it broke: said with what repair leaves out."""

    def made(self) -> list[Rib]:
        """The metal it adds: its ribs and their pads - what a later block keeps clear of."""
        return [*self.ribs, *self.pads]

    def tally(self) -> str:
        """What became of every path, in counts that add up. Keep-outs and gaps cut a path into
        pieces, so ribs can outnumber paths: this counts the lines that cross where ribs stand,
        the pieces they are cut into and what each piece became - then the lines that miss."""
        missed = self.dropped.get("missed", 0)
        crossed = self.paths - missed
        if not self.paths:
            return "the layout lays no lines"
        if not crossed:
            if missed == 1:
                return "the line misses where ribs stand"
            return f"all {missed} lines miss where ribs stand"
        rest = sorted((why, n) for why, n in self.dropped.items() if why != "missed")
        pieces = len(self.ribs) + sum(n for _, n in rest)
        cross = "crosses" if crossed == 1 else "cross"
        words = f"{_many(crossed, 'line')} {cross} where ribs stand"
        if pieces != crossed:
            words += f", cut into {pieces} pieces"
        became = [_many(len(self.ribs), "rib")]
        for why, n in rest:
            said = f"{n} {NOT_PLACED.get(why, why.replace('_', ' '))}"
            which = {"ended_elsewhere": self.ended_on, "closed": self.closed}.get(why)
            if which:
                named = sorted(which, key=lambda name: (-which[name], name))
                more = f" and {len(named) - 3} more" if len(named) > 3 else ""
                said += f" ({', '.join(named[:3])}{more})"
            became.append(said)
        words += ": " + ", ".join(became)
        if self.pads:
            words += f" ({_many(len(self.pads), 'wall')} padded)"
        if missed:
            miss = "line misses" if missed == 1 else "lines miss"
            words += f"; {missed} more {miss} where ribs stand"
        return words


# Why a piece of a path did not become a rib, in the words the verdict uses.
NOT_PLACED = {
    "keep_out": "stopped by something to keep clear of",
    "open_end": "ending at an edge with nothing to meet",
    "ended_elsewhere": "ending on something not named to run between",
    "too_short": "too short to be a rib",
    "no_height": "with no room for a rib's height",
    "one_thing": "ending on one thing at both ends",
    "one_side": "running within one side, not from one side to the other",
    "crowded": "too close to another of its spokes",
    "thin_wall": "ending on a wall too thin for it",
    "thin_floor": "left out, too thick for the floor under it",
    "closed": "reaching a hole or bore the part keeps closed",
    "left_out": "left out so the rest hold together",
}

# The rule a rib too thick for its floor breaks, in the words screening and the verdict use.
ON_FLOOR = "rib on floor"


@dataclass
class Drilled:
    """The holes a set of holes made, and what became of every place the lattice offered."""

    holes: list[Hole]
    diameter_mm: float = 0.0
    pitch_mm: float = 0.0
    plate_mm: float | None = None
    offered: int = 0
    """How many points of the lattice fell on the plate. Each became a hole, or is counted in
    ``dropped`` with why."""
    dropped: dict[str, int] = field(default_factory=dict)
    tried: list[dict] = field(default_factory=list)
    """Each hole made, as a ring of short lines just off the plate - ``a``, ``b`` - to see before
    anything is made."""
    problems: list[str] = field(default_factory=list)
    frame: HostFrame | None = None
    """The plate's plane, and how far along its normal the holes run: from and to."""
    band: tuple[float, float] = (0.0, 0.0)

    def made(self) -> list[Hole]:
        return list(self.holes)

    def clear_of(self, ribs: list[Rib]) -> float | None:
        """The least metal between a hole's edge and the side of any of ``ribs`` beside it - over
        or under the plate, where the holes run. None when no rib is beside a hole."""
        if self.frame is None or not self.holes:
            return None
        keeps = [_RibKeep.of(rib, self.frame, 0.0, far_side=True) for rib in ribs]
        least = None
        for hole in self.holes:
            centre = self.frame.to_plane(np.asarray(hole.centre, dtype=float).reshape(1, 3))[0]
            for keep in keeps:
                if keep is None or keep.low > self.band[1] or keep.high < self.band[0]:
                    continue
                gap = keep.gap(centre, centre, hole.radius_mm)
                least = gap if least is None else min(least, gap)
        return least

    def tally(self) -> str:
        """What became of every point of the lattice, in counts that add up."""
        if self.problems:
            return self.problems[0]
        if not self.offered:
            return "the lattice lays no point on the plate"
        size = f"Ø{self.diameter_mm:g} at {self.pitch_mm:g} mm pitch"
        words = f"{_many(len(self.holes), 'hole')} {size}"
        rest = sorted(self.dropped.items())
        if rest:
            words += " - " + ", ".join(f"{n} {NOT_DRILLED.get(why, why)}" for why, n in rest)
        return words


# Why a point of the lattice did not become a hole.
NOT_DRILLED = {
    "edge": "too near the plate's edge",
    "keep_out": "on something to keep clear of",
    "made": "on the ribs or holes of another block",
    "under": "over something standing under the plate",
    "left_out": "left out so the ribs hold",
}

# The lines a hole is drawn with: a ring of this many.
HOLE_LINES = 10


def _many(n: int, thing: str) -> str:
    return f"no {thing}s" if n == 0 else f"{n} {thing}" + ("" if n == 1 else "s")


def _memo(memo: dict | None, key: tuple, make: Callable[[], Any]) -> Any:
    """What ``make`` gives, kept in ``memo`` under ``key`` - once for every design that asks."""
    if memo is None:
        return make()
    if key not in memo:
        memo[key] = make()
    return memo[key]


def _base_key(base: Field) -> Any:
    """What tells one part's field from another's, for the memo."""
    return base.key or id(base)


def place_all(
    base: Field,
    features: FeatureSet,
    atlas: Atlas,
    tess: Tessellation,
    placements: list[Placement],
    holes: list[HoleSet] | tuple = (),
    *,
    offsets: dict[int, float] | None = None,
    finder: _Faces | None = None,
    memo: dict | None = None,
) -> dict[str, Placed | Drilled]:
    """Ribs for every placement and holes for every set of holes, each placed after the blocks it
    keeps clear of - their ribs and holes its keep-outs. ``offsets`` moves faces of the part, by
    face, as the design moves them. Returned in the order given, ribs first."""
    items: list[Placement | HoleSet] = [*placements, *holes]
    ids = {item.id for item in items}
    finder = finder or _Faces(tess)
    offsets = dict(offsets or {})
    pending = list(items)
    done: dict[str, Placed | Drilled] = {}
    # Where each rib stands in the open past its junctions - kept for every design placing it alike.
    known: dict[tuple, list[np.ndarray]] = memo.setdefault("runs", {}) if memo is not None else {}
    if len(known) > PLACED_KEPT * 16:
        known.clear()
    runs: dict[Rib, list[np.ndarray]] = {}
    # The root gap each rib placed keeps, by its placement's rule.
    ratios: dict[Rib, float] = {}
    while pending:
        ready = [p for p in pending if all(o in done or o not in ids for o in p.clear_of)]
        chosen = ready[0] if ready else pending[0]
        pending.remove(chosen)
        avoid = [made for other in chosen.clear_of if other in done for made in done[other].made()]
        # A block placed alike before - the same block, clear of the same things, on faces the
        # design moves alike where it looked - is what it was.
        kept = _placed_memo(memo)
        key = (type(chosen).__name__, chosen.model_dump_json(), tuple(avoid))
        seen = kept.setdefault(key, [])
        kept.move_to_end(key)
        result = next(
            (
                earlier
                for asked, moved, earlier in seen
                if all(offsets.get(f, 0.0) == v for f, v in zip(asked, moved, strict=True))
            ),
            None,
        )
        if result is None:
            watched = _Watched(offsets)
            if isinstance(chosen, HoleSet):
                result = drill(
                    base, features, atlas, tess, chosen, avoid,
                    finder=finder, offsets=watched, memo=memo,
                )  # fmt: skip
            else:
                result = place(
                    base, features, atlas, tess, chosen, avoid,
                    finder=finder, offsets=watched, memo=memo,
                )  # fmt: skip
            asked = tuple(sorted(f for f in watched.asked if isinstance(f, int)))
            seen.append((asked, tuple(offsets.get(f, 0.0) for f in asked), result))
            del seen[:-PLACED_ALIKE]
            while len(kept) > PLACED_KEPT:
                kept.popitem(last=False)
        if isinstance(result, Placed):
            # Ribs of blocks placed before stand where they stand: a rib that would pass one closer
            # than room for the mould between them is left out, whichever blocks they belong to.
            assert isinstance(chosen, Placement)
            junction = chosen.section.root_fillet_mm
            earlier = [r for p in done.values() if isinstance(p, Placed) for r in p.ribs]
            for rib in result.ribs:
                trim = junction + rib.thickness_mm
                if (rib, trim) not in known:
                    known[(rib, trim)] = _exposed_runs(base, rib, trim)
                runs[rib] = known[(rib, trim)]
            ratio = root_gap_of(chosen)
            crowded = _crowding(result.ribs, earlier, runs, ratios, ratio)
            result = _without(result, crowded, "crowded")
            ratios.update({rib: ratio for rib in result.ribs})
        done[chosen.id] = result
    return {item.id: done[item.id] for item in items}


def described() -> list[dict]:
    """The rules ribs, pads and holes are placed to, in words - as the pipeline shows them."""
    return [
        {
            "name": "what a rib ends on",
            "value": LOOK_PAST,
            "says": "a rib's end looks this many root fillets past its path for what it meets - "
            "or as far as room for the sand needs, the root gap, when that is further - and ends "
            "on it",
        },
        {
            "name": "stubs",
            "value": SHORTEST,
            "says": "a stretch of path shorter than this many rib thicknesses is a stub, left out",
        },
        {
            "name": "into what it meets",
            "value": DEEPEST,
            "says": "a rib's end goes into a wall at most this many times as deep as it must",
        },
        {
            "name": "pads",
            "value": PAD_MOST,
            "says": "a wall too thin for a rib is thickened round its end by at most this many "
            "times itself; past that the rib is left out as meeting a thin wall",
        },
        {
            "name": "floors",
            "value": None,
            "says": "a floor is never thickened for its ribs: a rib too thick for the floor under "
            "it is left out, saying so",
        },
        {
            "name": "holes over plate",
            "value": UNDER_PLATE,
            "says": "a hole goes only over plain plate: the metal under its rim no deeper than "
            "this many times that under its middle",
        },
        {
            "name": "ribs of other blocks",
            "value": None,
            "says": "a rib closer to a rib placed before it than the root gap is left out, "
            "blocks placed in the order they keep clear of each other",
        },
    ]


# How many blocks placed are kept for designs that place them again alike, and how many ways of
# moving faces each is kept for.
PLACED_KEPT = 4096
PLACED_ALIKE = 32


def _placed_memo(memo: dict | None) -> OrderedDict:
    if memo is None:
        return OrderedDict()
    return memo.setdefault("placed", OrderedDict())


class _Watched(dict):
    """A design's faces moved, that remembers which faces placing a block asked about - so a block
    placed again where the design moves those alike is known to come out the same."""

    def __init__(self, moved: dict[int, float]):
        super().__init__(moved)
        self.asked: set[int] = set()

    def get(self, key, default=None):  # type: ignore[override]
        self.asked.add(key)
        return super().get(key, default)

    def __contains__(self, key) -> bool:
        self.asked.add(key)
        return super().__contains__(key)

    def __getitem__(self, key):
        self.asked.add(key)
        return super().__getitem__(key)


def root_gap_of(placement: Placement) -> float:
    """Room for the sand a placement's ribs keep from any other, in thicknesses of the thinner:
    its own rule's, or the rule of thumb when it has none."""
    if placement.root_gap is not None:
        return float(placement.root_gap)
    return float(knowledge.rule("root_gap")[0])


def _exposed_runs(base: Field, rib: Rib, trim: float) -> list[np.ndarray]:
    from .checks import _exposed

    return _exposed(base, rib, trim)


def _crowding(
    ribs: list[Rib],
    earlier: list[Rib],
    runs: dict[Rib, list[np.ndarray]],
    ratios: dict[Rib, float] | None = None,
    ratio: float | None = None,
) -> set[int]:
    """Which of ``ribs`` pass one of ``earlier`` closer than the root gap - room for the sand
    between their footprints - where both stand in the open past their junctions, and do not
    cross. ``ratio`` is the root gap these ribs keep, ``ratios`` each earlier rib's; the larger
    holds between two."""
    from .checks import _plan, _polyline_distance

    if not ribs or not earlier:
        return set()
    if ratio is None:
        ratio = float(knowledge.rule("root_gap")[0])
    crowded = set()
    for index, rib in enumerate(ribs):
        for other in earlier:
            # Ribs whose bodies cross meet in a junction - repair holds those to their angles and
            # arms. Only the sides, not the fillets: fillets overlapping over a slot of sand is a
            # gap too narrow, not a junction.
            sides = (rib.thickness_mm + other.thickness_mm) / 2.0
            whole, _ = _polyline_distance(_plan(rib), _plan(other))
            if whole <= sides:
                continue
            reach = _footprint(rib) + _footprint(other)
            gap = max(ratio, (ratios or {}).get(other, ratio))
            least = gap * min(rib.thickness_mm, other.thickness_mm)
            for mine in runs.get(rib, []):
                for theirs in runs.get(other, []):
                    distance, _ = _polyline_distance(mine, theirs)
                    if sides < distance < reach + least:
                        crowded.add(index)
                        break
                if index in crowded:
                    break
            if index in crowded:
                break
    return crowded


def _footprint(rib) -> float:
    """Half a rib's footprint - its metal where it stands, fillet and all."""
    return float(getattr(rib, "footprint_mm", rib.thickness_mm / 2.0))


def _without(placed: Placed, drop: set[int], why: str) -> Placed:
    """What a block placed, less the ribs at ``drop`` - their pads and lines with them - counted as
    left out ``why``."""
    if not drop:
        return placed
    out = copy.copy(placed)
    out.ribs = [r for i, r in enumerate(placed.ribs) if i not in drop]
    out.spans = [s for i, s in enumerate(placed.spans) if i not in drop]
    out.pads, cursor = [], 0
    out.tried = [dict(line) for line in placed.tried]
    for index, span in enumerate(placed.spans):
        count = len(span.get("pads_mm", []))
        if index in drop:
            first = span.get("line")
            if first is not None:
                for line in out.tried[first : first + 1 + count]:
                    line["outcome"] = why
        else:
            out.pads += placed.pads[cursor : cursor + count]
        cursor += count
    out.dropped = {**placed.dropped, why: placed.dropped.get(why, 0) + len(drop)}
    return out


def _without_holes(drilled: Drilled, drop: set[int], why: str) -> Drilled:
    """What a set of holes made, less the holes at ``drop`` - their rings drawn as left out -
    counted as left out ``why``."""
    if not drop:
        return drilled
    out = copy.copy(drilled)
    out.holes = [h for i, h in enumerate(drilled.holes) if i not in drop]
    out.tried = [dict(line) for line in drilled.tried]
    for index in drop:
        for line in out.tried[index * HOLE_LINES : (index + 1) * HOLE_LINES]:
            line["outcome"] = why
    out.dropped = {**drilled.dropped, why: drilled.dropped.get(why, 0) + len(drop)}
    return out


@dataclass
class _Height:
    """One height a block's paths are drawn at: the plane there, where ribs may go on it - for
    webs, where each thing they join is on it - and how far over it the walk looks."""

    frame: HostFrame
    footprint: _Footprint
    between: dict[str, np.ndarray] | None
    probe_height: float


@dataclass
class _Cells:
    """The footprints of several heights on one plane, as one: where paths are laid across."""

    parts: list[_Footprint]

    @property
    def step(self) -> float:
        return min(part.step for part in self.parts)

    def cells(self) -> np.ndarray:
        return np.concatenate([part.cells() for part in self.parts])


@dataclass
class _Ground:
    """What a block of ribs reads off the part before any path is drawn: the heights its paths are
    drawn at - the floor, for ribs standing on one; for webs, every height both what they run from
    and what they run to begin at, lowest first, all on one plane seen square - and the one most
    of what they join is at. Or why nothing can."""

    heights: list[_Height] = field(default_factory=list)
    main: int = 0
    host_faces: frozenset[int] = frozenset()
    problem: str = ""

    def cells(self) -> _Footprint | _Cells:
        """Where ribs may go at any of its heights."""
        if len(self.heights) == 1:
            return self.heights[0].footprint
        return _Cells([height.footprint for height in self.heights])

    def between(self) -> dict[str, np.ndarray] | None:
        """Where each thing webs join is, at any of its heights."""
        seen = [height.between for height in self.heights if height.between is not None]
        if not seen:
            return None
        if len(seen) == 1:
            return seen[0]
        refs = dict.fromkeys(ref for points in seen for ref in points)
        return {
            ref: np.concatenate(
                [points[ref] for points in seen if ref in points] or [np.zeros((0, 2))]
            )
            for ref in refs
        }


def _ground(
    base: Field,
    features: FeatureSet,
    tess: Tessellation,
    placement: Placement,
    step: float,
    probe_height: float,
    reach: float,
) -> _Ground:
    if not placement.host:
        hang, problem = hang_frame(
            features, tess, placement.supports, placement.pull, placement.other_side
        )
        if hang is None:
            return _Ground(problem=problem)
        n = hang.frame.normal
        at = float(hang.frame.origin @ n)
        heights = []
        for level in hang.levels or (Level(at, hang.band, hang.joins),):
            # Every height on the one plane, seen square: a path is the same path at each.
            frame = _frame_at(hang.frame.origin + (level.at - at) * n, n)
            probe = min(probe_height, level.band / 2.0)
            footprint, between = _gap(
                base, features, tess, list(level.joins), frame, level.band, step, probe, reach
            )
            heights.append(_Height(frame, footprint, between, probe))
        main = min(range(len(heights)), key=lambda k: abs(float(heights[k].frame.origin @ n) - at))
        return _Ground(heights, main)
    host, problem = host_of(features, placement.host)
    if host is None:
        return _Ground(problem=problem)
    frame = _frame(host)
    footprint = _Footprint.of(tess, host.face_ids, frame, step)
    return _Ground([_Height(frame, footprint, None, probe_height)], 0, frozenset(host.face_ids))


def place(
    base: Field,
    features: FeatureSet,
    atlas: Atlas,
    tess: Tessellation,
    placement: Placement,
    avoid: list[Rib | Hole] | tuple = (),
    *,
    finder: _Faces | None = None,
    offsets: dict[int, float] | None = None,
    memo: dict | None = None,
) -> Placed:
    """Ribs for ``placement`` on the part ``base`` samples, clear of the ribs and holes in
    ``avoid``, on the part with its faces moved by ``offsets``. See the module note."""
    section = placement.section
    thickness = section.thickness_mm
    tee = section.shape == "T" and section.flange_width_mm > thickness
    # Half the rib at its widest - the flange, for a T.
    side = (section.flange_width_mm if tee else thickness) / 2.0
    # Half its footprint: its metal where it stands, the root fillet besides - what keeps clear of
    # anything, so a clearance is measured from real metal and not from the rib's middle.
    half = max(thickness / 2.0 + section.root_fillet_mm, side)
    spacing = base.grid.spacing_mm
    step = max(min(spacing / 2.0, 1.0), features.diagonal_mm * 2e-4)
    probe_height = max(2.0 * spacing, 0.5 * section.root_fillet_mm)
    # Whatever is nearer a rib's end than room for the sand is what it ends on.
    ratio = root_gap_of(placement)
    room = ratio * section.thickness_mm
    reach = max(LOOK_PAST * section.root_fillet_mm, room) + spacing
    offsets = offsets or {}
    finder = finder or _Faces(tess)
    site = (
        _base_key(base),
        tuple(placement.host),
        tuple(placement.supports),
        tuple(placement.other_side),
    )

    hanging = not placement.host
    pull = tuple(placement.pull) if placement.pull is not None else None
    ground = _memo(
        memo,
        ("ground", *site, pull, step, probe_height, reach),
        lambda: _ground(base, features, tess, placement, step, probe_height, reach),
    )
    if ground.problem:
        return Placed(ribs=[], problems=[ground.problem])
    if placement.layout.kind == "radial":
        # Spokes turn about an axis: a thing with none - a freeform face alone - has no middle
        # they could fan from.
        about = features.get(placement.layout.centre or "")
        if about is None:
            return Placed(ribs=[], problems=[f"the part has no {placement.layout.centre}"])
        if axis_of(features, about) is None:
            return Placed(
                ribs=[],
                problems=[
                    f"{about.id} has no axis: spokes turn only about round things - a boss, a "
                    "bore, a ring's round faces"
                ],
            )
    main = ground.heights[ground.main]
    host_faces = set(ground.host_faces)
    keep: list = _memo(
        memo,
        ("keep", *site, pull, step, json.dumps([k.model_dump() for k in placement.keep_out])),
        lambda: _keep_outs(features, atlas, tess, placement, main.frame, host_faces, step),
    )
    rows = [{**k.row(), "rule": k.rule} for k in keep]
    # What the part keeps closed, in three dimensions - a hole in a boss a rib ends on is as much
    # in the way as one in the floor - all but what the ribs run between, which is theirs to meet.
    shut = [ref for ref in placement.closed if ref not in set(placement.supports)]
    # Points over a rib a little apart, the part's size considered: a millimetre or two on a
    # housing.
    spread = max(step, features.diagonal_mm * 7.5e-4)
    closed = (
        _memo(
            memo,
            ("closed", tuple(sorted(shut)), placement.closed_mm, spread),
            lambda: _Closed.of(features, tess, shut, placement.closed_mm, spread),
        )
        if shut
        else None
    )
    # Other blocks' ribs and holes are kept clear of in three dimensions, one by one, once each
    # rib's height is known: one standing over or under another is no obstacle to it. Seen from
    # each height paths are drawn at.
    others = [
        [
            kept
            for kept in (_kept_clear(thing, h.frame, placement.clear_of_mm) for thing in avoid)
            if kept is not None
        ]
        for h in ground.heights
    ]
    # How far a rib's end is buried in what it meets: set by the rib, not by the grid, so a
    # preview and a full design end in the same place.
    bury = max(section.root_fillet_mm, 2.0 * spacing)
    support_of = _memo(
        memo,
        ("supports", tuple(placement.supports)),
        lambda: _supports_by_face(features, atlas, placement.supports),
    )
    # A floor the design moves: ribs on it start where it now is. Thinned, they reach down to it.
    host_offset = min((offsets[f] for f in host_faces if f in offsets), default=0.0)
    sink = 0.0 if hanging else spacing + max(0.0, -host_offset)
    # How far a wall measured through its facets may fall short of what a rib needs and still be
    # enough: what the tessellation can be off by, both faces.
    slack = max(0.5, 2.0 * tess.deflection_mm)

    def thing(face: int, ref: str | None) -> np.ndarray:
        """Points over what a rib's end meets: the support the face met belongs to, or else what
        the face is part of - the face with it either way - read once for every design."""
        faces = _memo(memo, ("thing faces", face, ref), lambda: _thing_faces(features, face, ref))
        return _memo(memo, ("thing", faces, spacing), lambda: _on_faces(tess, faces, spacing))

    placed = Placed(ribs=[], keep_outs=rows)
    # How tall named features let ribs stand, over each height.
    caps = [
        _memo(
            memo,
            (
                "caps",
                *site,
                pull,
                float(h.frame.origin @ h.frame.normal),
                tuple(placement.height.not_above),
                placement.height.max_mm,
            ),
            lambda h=h: _caps(features, tess, placement, h.frame),
        )
        for h in ground.heights
    ]
    placed.caps = caps[ground.main]
    # Why stretches had no room for a rib. A problem only if no rib had room at all; otherwise
    # they are counted among what was not placed, like any other stretch dropped.
    no_room: list[str] = []
    spokes: list[_RibKeep] = []
    # Lines are drawn a little off the host, so they show over it rather than in it.
    lift = max(spacing / 2.0, 0.5)

    # Spokes close in on each other toward what they turn about, where their roots may meet; past
    # that they leave room for the mould between them.
    root_zone = section.root_fillet_mm + thickness
    crowd = ratio * thickness
    # The wall a rib meets must be this thick, when a rule holds ribs to it.
    need = thickness / placement.rib_to_wall if placement.rib_to_wall else 0.0

    def attempt(
        k: int, path_id: int, start: np.ndarray, direction: np.ndarray, length: float
    ) -> _Attempt:
        """What one path becomes at the ``k``-th height: each piece as a line, why each that is
        no rib is not, and the ribs, pads and spokes it makes."""
        height = ground.heights[k]
        frame, footprint, probe_height = height.frame, height.footprint, height.probe_height
        out = _Attempt()

        def tried(p: np.ndarray, q: np.ndarray, outcome: str, width: float | None = None):
            a, b = frame.to_world(np.array([p, q]), lift)
            line: dict[str, Any] = {
                "a": [round(float(v), 2) for v in a],
                "b": [round(float(v), 2) for v in b],
                "outcome": outcome,
            }
            if width:
                # What is made is drawn as wide as it is, square to the way it stands.
                line["mm"] = round(float(width), 2)
                line["up"] = [round(float(v), 4) for v in frame.normal]
            out.lines.append(line)

        s = np.arange(0.0, length + step, step)
        uv = start + np.outer(s, direction)
        over = footprint.covers(uv)
        if not over.any():
            _count(out, "missed")
            tried(uv[0], uv[-1], "missed")
            return out
        blocked = np.zeros(s.size, dtype=bool)
        for keep_out in keep:
            blocked |= keep_out.blocks(uv, half)
        usable = over & ~blocked
        if not usable.any():
            _count(out, "keep_out")
            where = np.flatnonzero(over)
            tried(uv[where[0]], uv[where[-1]], "keep_out")
            return out
        for first, last in _runs(usable):
            if (s[last] - s[first]) < SHORTEST * thickness:
                _count(out, "too_short")
                tried(uv[first], uv[last], "too_short")
                continue
            mets = [
                _end(
                    base,
                    frame,
                    finder,
                    support_of,
                    uv[index],
                    sense * direction,
                    reach,
                    step,
                    probe_height,
                    blocked,
                    index,
                    int(sense),
                    bury,
                    thing,
                    thickness / 2.0,
                )
                for index, sense in ((first, -1.0), (last, 1.0))
            ]
            ends = [met.kind for met in mets]
            if hanging and ends == ["support", "support"] and mets[0].ref == mets[1].ref:
                _count(out, "one_thing")
                tried(uv[first], uv[last], "one_thing")
                continue
            if placement.other_side and ends == ["support", "support"]:
                # Two sides named: from one to the other, never within either.
                far = set(placement.other_side)
                if (mets[0].ref in far) == (mets[1].ref in far):
                    _count(out, "one_side")
                    tried(uv[first], uv[last], "one_side")
                    continue
            if (placement.connection == "supports" or hanging) and ends != ["support", "support"]:
                # What stops it most: a keep-out, then an edge with nothing past it - naming a
                # face would not help either - then something that could be named to run between.
                reason = next(
                    why
                    for kind, why in (
                        ("keep_out", "keep_out"),
                        ("edge", "open_end"),
                        ("elsewhere", "ended_elsewhere"),
                    )
                    if kind in ends
                )
                _count(out, reason)
                tried(uv[first], uv[last], reason)
                for met in mets:
                    if reason != "ended_elsewhere" or met.kind != "elsewhere" or met.face is None:
                        continue
                    for feature in features.containing(met.face) or [None]:
                        name = feature.id if feature else f"face:{met.face}"
                        out.ended_on[name] = out.ended_on.get(name, 0) + 1
                continue
            tops = [met.top for met in mets]
            if hanging and None not in tops:
                # A web stands only where both its ends do: no taller than the lower of the two
                # things it joins, whichever way its top runs.
                tops = [min(t for t in tops if t is not None)] * 2
            heights, why = _height(caps[k], tops, placement)
            room = _headroom(
                finder, frame, uv[first], uv[last], probe_height, section.root_fillet_mm + side
            )
            if heights is not None and room is not None and max(heights) > room:
                heights = [min(h, room) for h in heights]
                why = f"{why}, what stands over it" if why else "what stands over it"
            if heights is None or min(heights) <= section.root_fillet_mm:
                # No room for a rib: taller than its own root fillet is the least a rib is.
                reason = (
                    why
                    if heights is None
                    else f"{why} leaves {min(heights):.1f} mm above the host - no taller than "
                    f"the R{section.root_fillet_mm:g} root fillet, so no rib"
                )
                if reason not in out.no_room:
                    out.no_room.append(reason)
                _count(out, "no_height")
                tried(uv[first], uv[last], "no_height")
                continue
            if any(o.clashes(uv[first], uv[last], half, max(heights)) for o in others[k]):
                _count(out, "keep_out")
                tried(uv[first], uv[last], "keep_out")
                continue
            # A spoke that would come closer to another past their roots than room for the mould
            # between them is left out. Straight families cross by design.
            spoke = None
            if placement.layout.kind == "radial":
                p, q = _inset(uv[first], uv[last], root_zone)
                if any(other.gap(p, q, half) < crowd for other in (*spokes, *out.spokes)):
                    _count(out, "crowded")
                    tried(uv[first], uv[last], "crowded")
                    continue
                spoke = _RibKeep(a=p, b=q, half=half, clearance=0.0)
            # Each end on a wall no thinner than the rib may meet: padded where the placement allows
            # it, never to more than twice the wall - else the rib is not placed.
            pads: list[Rib] = []
            thin = False
            for met, height, sense in ((mets[0], heights[0], -1.0), (mets[1], heights[1], 1.0)):
                if not need:
                    break
                measured = _wall(finder, features, frame, met, sense * direction, offsets)
                if measured is None or measured[0] >= need - slack:
                    continue
                wall, inward = measured
                depth = float(math.ceil(need - wall))
                if not placement.pads or depth > PAD_MOST * wall:
                    thin = True
                    break
                assert met.surface is not None
                pads.append(_pad(frame, met.surface, inward, depth, thickness, height + sink, sink))
            if thin:
                _count(out, "thin_wall")
                tried(uv[first], uv[last], "thin_wall")
                continue
            a = mets[0].end_for(heights[0]) if mets[0].ends is not None else uv[first]
            b = mets[1].end_for(heights[1]) if mets[1].ends is not None else uv[last]
            # A wall the design thins stands back from the rib's end, which reaches it still.
            a = a - direction * max(0.0, -offsets.get(mets[0].face, 0.0))
            b = b + direction * max(0.0, -offsets.get(mets[1].face, 0.0))
            # Sunk into the floor, so the two are one; a web with nothing under it starts where it
            # starts.
            rib = Rib(
                start=tuple(float(v) for v in frame.to_world(a, -sink)[0]),
                end=tuple(float(v) for v in frame.to_world(b, -sink)[0]),
                thickness_mm=thickness,
                height_mm=heights[0] + sink,
                end_height_mm=heights[1] + sink,
                pull=tuple(float(v) for v in frame.normal),
                draft_deg=section.draft_deg,
                edge_round_mm=section.edge_round_mm,
                flange_width_mm=section.flange_width_mm if tee else 0.0,
                flange_thickness_mm=section.flange_thickness_mm if tee else 0.0,
                root_fillet_mm=section.root_fillet_mm,
            )
            # Its metal, and its pads', clear of what the part keeps closed - ends buried in what
            # they meet and all.
            reached = None
            if closed is not None:
                reached = next(filter(None, (closed.reached(frame, r) for r in (rib, *pads))), None)
            if reached is not None:
                _count(out, "closed")
                out.closed[reached] = out.closed.get(reached, 0) + 1
                tried(uv[first], uv[last], "closed")
                continue
            # The floor under it, as the design leaves it - never thickened for it: a rib too
            # thick for its floor is left out, and says the rule it broke.
            floor = None if hanging else _floor(finder, frame, uv[first], uv[last])
            if (
                floor is not None
                and placement.rib_to_wall
                and thickness > placement.rib_to_wall * (floor + host_offset) + FLOOR_SLACK
            ):
                _count(out, "thin_floor")
                tried(a, b, "thin_floor", thickness)
                out.left_out.append({"what": "rib", "why": ON_FLOOR})
                continue
            if spoke is not None:
                out.spokes.append(spoke)
            line_index = len(out.lines)
            tried(a, b, "rib", thickness)
            for pad in pads:
                line = frame.to_plane(np.array([pad.start, pad.end]))
                tried(line[0], line[1], "pad", pad.thickness_mm)
            out.ribs.append(rib)
            out.pads.extend(pads)
            out.spans.append(
                {
                    "path": path_id,
                    "ends": ends,
                    "length_mm": round(float(np.linalg.norm(b - a)), 1),
                    "height_mm": round(max(heights), 1),
                    "heights_mm": [round(h, 1) for h in heights],
                    "limited_by": why,
                    "clearance_mm": _clearance(keep, a, b, half),
                    # Each rule's keep-outs, from the rib in the open - not its ends, buried in
                    # what they meet.
                    "clear_by_rule": _clearances(
                        keep, uv[first], uv[last], half, len(placement.keep_out)
                    ),
                    "pads_mm": [pad.thickness_mm / 2.0 for pad in pads],
                    # The floor it stands on, measured under it - before the design moves it.
                    "floor_mm": floor,
                    "line": line_index,
                }
            )
        return out

    for path_id, (start, direction, length) in enumerate(
        _paths(placement, main.frame, ground.cells(), features, ground.between())
    ):
        placed.paths += 1
        # Lowest first, the first height the path makes a rib at; making none at any, it is
        # drawn where most of what the webs join is.
        tries: list[_Attempt] = []
        for k in range(len(ground.heights)):
            tries.append(attempt(k, path_id, start, direction, length))
            if tries[-1].ribs:
                break
        chosen = tries[-1] if tries[-1].ribs else tries[ground.main]
        _merge(placed, chosen)
        spokes.extend(chosen.spokes)
        no_room.extend(reason for reason in chosen.no_room if reason not in no_room)
    if not placed.ribs:
        placed.problems.extend(no_room)
    return placed


def _floor(finder: _Faces, frame: HostFrame, a: np.ndarray, b: np.ndarray) -> float | None:
    """How thick the floor under a rib is: the least metal under three points along it."""
    points = a + np.outer([0.25, 0.5, 0.75], b - a)
    depth = finder.exits_along(frame.to_world(points, -0.05), -frame.normal)
    depth = depth[np.isfinite(depth)]
    return round(float(depth.min()) + 0.05, 1) if depth.size else None


def _wall(
    finder: _Faces,
    features: FeatureSet,
    frame: HostFrame,
    met: _Met,
    toward: np.ndarray,
    offsets: dict[int, float],
) -> tuple[float, np.ndarray] | None:
    """How thick the wall a rib's end meets is - square through it from where the rib meets it,
    with what the design moves its two faces by - and which way is into it. None where the end
    meets no wall, or where it cannot be told."""
    if met.kind != "support" or met.surface is None or met.face is None:
        return None
    way = toward[0] * frame.e1 + toward[1] * frame.e2
    inward = _inward(features, met.face, met.surface, way)
    distance, far = finder.through((met.surface + 0.05 * inward).reshape(1, 3), inward)
    if not np.isfinite(distance[0]):
        return None
    moved = offsets.get(met.face, 0.0) + (offsets.get(int(far[0]), 0.0) if far[0] >= 0 else 0.0)
    return float(distance[0]) + 0.05 + moved, inward


def _inward(features: FeatureSet, face_id: int, point: np.ndarray, toward: np.ndarray):
    """Square into the metal at a point on a face: against a flat face's normal, toward or away
    from a round face's axis - or the way a rib runs into it, for a face that says neither or does
    not face the rib."""
    face = features.faces.get(face_id)
    inward = None
    if face is not None and face.surface_type == "plane" and face.normal is not None:
        inward = -np.asarray(face.normal, dtype=float)
    elif face is not None and face.axis is not None and face.axis_point is not None:
        axis = np.asarray(face.axis, dtype=float)
        offset = np.asarray(point, dtype=float) - np.asarray(face.axis_point, dtype=float)
        radial = offset - (offset @ axis) * axis
        length = float(np.linalg.norm(radial))
        if length > 1e-9:
            inward = radial / length if face.concave else -radial / length
    if inward is None or float(inward @ toward) < 0.2:
        inward = np.asarray(toward, dtype=float)
    return inward / np.linalg.norm(inward)


def _pad(
    frame: HostFrame,
    surface: np.ndarray,
    inward: np.ndarray,
    depth: float,
    thickness: float,
    height: float,
    sink: float,
) -> Rib:
    """A pad where a rib meets a wall too thin for it: a plate along the wall, half in it, standing
    ``depth`` out of it, as tall as the rib there and as wide as two ribs and itself twice over."""
    along = np.cross(-inward, frame.normal)
    if float(np.linalg.norm(along)) < 1e-6:
        along = frame.e1
    across = frame.to_plane((surface + along).reshape(1, 3))[0]
    across = across - frame.to_plane(surface.reshape(1, 3))[0]
    across = across / max(float(np.linalg.norm(across)), 1e-12)
    centre = frame.to_plane(surface.reshape(1, 3))[0]
    half = thickness + depth
    a, b = centre - half * across, centre + half * across
    return Rib(
        start=tuple(float(v) for v in frame.to_world(a, -sink)[0]),
        end=tuple(float(v) for v in frame.to_world(b, -sink)[0]),
        thickness_mm=2.0 * depth,
        height_mm=height,
        pull=tuple(float(v) for v in frame.normal),
        pad=True,
    )


# --- holes ---------------------------------------------------------------------------------------


@dataclass
class _Plate:
    """What a set of holes reads off the part before any is placed: the plate's plane, where it
    is, how far each point on it is from its edge, and how thick it is. Or why nothing can."""

    frame: HostFrame | None = None
    footprint: _Footprint | None = None
    edge: np.ndarray | None = None
    host_faces: frozenset[int] = frozenset()
    thickness: float | None = None
    problem: str = ""

    def edge_at(self, uv: np.ndarray) -> np.ndarray:
        """How far points on the plate are from its edge - nothing, off it."""
        assert self.footprint is not None and self.edge is not None
        index = np.round((np.atleast_2d(uv) - self.footprint.lo) / self.footprint.step).astype(int)
        ok = np.all((index >= 0) & (index < np.asarray(self.edge.shape)), axis=1)
        out = np.zeros(index.shape[0])
        out[ok] = self.edge[index[ok, 0], index[ok, 1]]
        return out


def _plate_of(
    features: FeatureSet, tess: Tessellation, finder: _Faces, refs: list[str], step: float
) -> _Plate:
    from scipy import ndimage

    host, problem = host_of(features, refs)
    if host is None:
        return _Plate(problem=problem)
    frame = _frame(host)
    footprint = _Footprint.of(tess, host.face_ids, frame, step)
    # How far each cell of the plate is from the nearest cell off it: from its edge, the foot of a
    # wall standing on it, a hole it has already.
    edge = ndimage.distance_transform_edt(footprint.mask) * step
    mine = np.flatnonzero(np.isin(tess.face_id, list(host.face_ids)))
    corners = tess.vertices[tess.triangles[mine]]
    areas = np.linalg.norm(
        np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1
    )
    # Through the plate from its largest facet - on the face, not at its centroid, which may be in
    # a hole.
    start = corners[int(np.argmax(areas))].mean(axis=0) - frame.normal * 0.05
    through = finder.exit_along(start, -frame.normal)
    thickness = None if through is None else through + 0.05
    return _Plate(frame, footprint, edge, frozenset(host.face_ids), thickness)


def drill(
    base: Field,
    features: FeatureSet,
    atlas: Atlas,
    tess: Tessellation,
    holes: HoleSet,
    avoid: list[Rib | Hole] | tuple = (),
    *,
    finder: _Faces | None = None,
    offsets: dict[int, float] | None = None,
    memo: dict | None = None,
) -> Drilled:
    """Holes for ``holes`` through the plate it names - clear of its edges, of what it keeps clear
    of and of the ribs and holes in ``avoid`` - on the part with its faces moved by ``offsets``.
    See the module note."""
    spacing = base.grid.spacing_mm
    step = max(spacing / 2.0, 1.0)
    finder = finder or _Faces(tess)
    offsets = offsets or {}
    radius = holes.diameter_mm / 2.0
    ligament = holes.ligament_mm
    drilled = Drilled(holes=[], diameter_mm=holes.diameter_mm, pitch_mm=holes.pitch_mm)
    plate = _memo(
        memo,
        ("plate", _base_key(base), tuple(holes.host), step),
        lambda: _plate_of(features, tess, finder, holes.host, step),
    )
    if plate.problem:
        drilled.problems.append(plate.problem)
        return drilled
    if plate.thickness is None:
        drilled.problems.append(f"how thick {', '.join(holes.host)} is could not be measured")
        return drilled
    drilled.plate_mm = round(plate.thickness, 1)
    between = holes.pitch_mm - holes.diameter_mm
    if between < ligament - 1e-9:
        drilled.problems.append(
            f"holes Ø{holes.diameter_mm:g} mm at {holes.pitch_mm:g} mm pitch leave {between:g} mm "
            f"of metal between them - less than the {ligament:g} mm each needs"
        )
        return drilled
    frame = plate.frame
    footprint = plate.footprint
    assert frame is not None and footprint is not None
    host_faces = set(plate.host_faces)
    keep: list = _memo(
        memo,
        ("keep", _base_key(base), tuple(holes.host), step, "holes")
        + (json.dumps([k.model_dump() for k in holes.keep_out]),),
        lambda: _keep_outs(features, atlas, tess, holes, frame, host_faces, step),
    )
    clearance = max(holes.clear_of_mm, ligament)
    others = [
        kept
        for kept in (_kept_clear(thing, frame, clearance, far_side=True) for thing in avoid)
        if kept is not None
    ]
    # The plate as the design has it: its face moved, and so what a hole runs through.
    host_offset = min((offsets[f] for f in host_faces if f in offsets), default=0.0)
    low, high = -(plate.thickness + spacing), max(0.0, host_offset) + spacing
    drilled.frame, drilled.band = frame, (low, high)

    # The lattice, from the middle of the plate: rows a pitch apart - or, staggered, every other
    # row shifted by half a pitch, the rows closer so every hole is a pitch from the next.
    cells = footprint.cells()
    centre = cells.mean(axis=0)
    angle = math.radians(holes.angle_deg)
    d = np.array([math.cos(angle), math.sin(angle)])
    m = np.array([-d[1], d[0]])
    along, across = (cells - centre) @ d, (cells - centre) @ m
    pitch = holes.pitch_mm
    staggered = holes.pattern == "staggered"
    row = pitch * (math.sqrt(3.0) / 2.0 if staggered else 1.0)
    lattice = []
    for j in range(math.floor(float(across.min()) / row), math.ceil(float(across.max()) / row) + 1):
        shift = pitch / 2.0 if staggered and j % 2 else 0.0
        first = math.floor((float(along.min()) - shift) / pitch)
        last = math.ceil((float(along.max()) - shift) / pitch)
        for i in range(first, last + 1):
            lattice.append(centre + (i * pitch + shift) * d + j * row * m)
    points = np.array(lattice).reshape(-1, 2)
    points = points[footprint.covers(points)]
    drilled.offered = len(points)

    def drop(bad: np.ndarray, why: str) -> np.ndarray:
        if bad.any():
            drilled.dropped[why] = drilled.dropped.get(why, 0) + int(bad.sum())
        return points[~bad]

    # A whole edge distance from the plate's edge - the raster overstates the plate by a cell.
    points = drop(plate.edge_at(points) - step < radius + holes.edge_mm, "edge")
    blocked = np.zeros(len(points), dtype=bool)
    for k in keep:
        blocked |= k.blocks(points, radius)
    points = drop(blocked, "keep_out")
    if others and len(points):
        clash = np.array([any(o.near(p, p, radius, low, high) for o in others) for p in points])
        points = drop(clash, "made")
    if not len(points):
        return drilled

    # Over plain plate: the metal under its rim runs no deeper than under its middle - else
    # something stands under the plate there, and the hole would cut into it.
    turns = np.linspace(0.0, 2.0 * math.pi, 8, endpoint=False)
    ring = np.concatenate(
        [np.zeros((1, 2)), np.stack([np.cos(turns), np.sin(turns)], axis=1) * (radius + ligament)]
    )
    samples = (points[:, None, :] + ring[None, :, :]).reshape(-1, 2)
    depth, far = finder.through(frame.to_world(samples, -0.05), -frame.normal)
    depth = (depth + 0.05).reshape(len(points), len(ring))
    far = far.reshape(len(points), len(ring))
    known = np.isfinite(depth).all(axis=1)
    safe = np.where(np.isfinite(depth), depth, 0.0)
    middle = safe[:, 0]
    plain = (
        known
        & (safe.max(axis=1) <= UNDER_PLATE * middle + spacing)
        & (safe.min(axis=1) >= middle / UNDER_PLATE - spacing)
    )
    kept = np.flatnonzero(plain)
    points = drop(~plain, "under")
    lift = max(spacing / 2.0, 0.5)
    circle = np.linspace(0.0, 2.0 * math.pi, HOLE_LINES + 1)
    for point, index in zip(points, kept, strict=True):
        # Through the plate and a little past its far side, however far the design moves it.
        pushed = max((offsets.get(int(f), 0.0) for f in far[index] if f >= 0), default=0.0)
        hole = Hole(
            centre=tuple(float(v) for v in frame.to_world(point, 0.0)[0]),
            axis=tuple(float(v) for v in frame.normal),
            radius_mm=radius,
            depth_mm=float(safe[index].max()) + max(0.0, pushed) + 2.0 * spacing,
            above_mm=max(0.0, host_offset) + 2.0 * spacing,
        )
        drilled.holes.append(hole)
        rim = point + radius * np.stack([np.cos(circle), np.sin(circle)], axis=1)
        world = frame.to_world(rim, lift)
        for a, b in zip(world[:-1], world[1:], strict=True):
            drilled.tried.append(
                {
                    "a": [round(float(v), 2) for v in a],
                    "b": [round(float(v), 2) for v in b],
                    "outcome": "hole",
                }
            )
    return drilled


# --- the host -------------------------------------------------------------------------------------


def host_of(features: FeatureSet, refs: list[str]) -> tuple[Feature | None, str]:
    """Where ribs stand, as one flat area: every face of every ref, which must lie in one plane.
    None, and why, when they do not - or when the part has no such feature."""
    found = [features.get(ref) for ref in refs]
    missing = [ref for ref, feature in zip(refs, found, strict=True) if feature is None]
    if missing or not found:
        return None, f"the part has no {', '.join(missing) or 'place for ribs to stand'}"
    curved = [
        f.id
        for f in found
        if f.normal is None
        or not (
            f.kind == FeatureKind.PLANAR_GROUP
            or (f.kind == FeatureKind.FACE and f.metrics.get("flat") == 1.0)
        )
    ]
    if curved:
        return None, f"{', '.join(curved)} is not flat; ribs stand only on flat faces yet"
    if len(found) == 1:
        return found[0], ""
    normal = np.asarray(found[0].normal, dtype=float)
    level = float(np.asarray(found[0].centroid) @ normal)
    tolerance = max(features.diagonal_mm * 1e-4, 1e-3)
    for f in found[1:]:
        parallel = float(np.asarray(f.normal) @ normal) > math.cos(math.radians(1.0))
        if not parallel or abs(float(np.asarray(f.centroid) @ normal) - level) > tolerance:
            return None, f"{', '.join(refs)} are not one plane; ribs stand on one flat area"
    faces = tuple(sorted({face for f in found for face in f.face_ids}))
    areas = np.array([f.area_mm2 for f in found])
    centre = np.average(np.array([f.centroid for f in found]), axis=0, weights=areas)
    return (
        Feature(
            id=" + ".join(refs),
            kind=FeatureKind.FACE,
            face_ids=faces,
            area_mm2=float(areas.sum()),
            centroid=tuple(float(v) for v in centre),
            metrics={"flat": 1.0},
            normal=tuple(float(v) for v in normal),
        ),
        "",
    )


def _frame(host: Feature) -> HostFrame:
    return _frame_at(np.asarray(host.centroid, dtype=float), np.asarray(host.normal, dtype=float))


def _frame_at(origin: np.ndarray, normal: np.ndarray) -> HostFrame:
    n = normal / np.linalg.norm(normal)
    reference = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = reference - (reference @ n) * n
    e1 = e1 / np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    return HostFrame(origin=origin, normal=n, e1=e1, e2=e2)


# --- webs with nothing under them -----------------------------------------------------------------

# A round face runs along a direction within this of its axis; a flat one, when its normal is within
# this of square to the direction.
ALONG = math.cos(math.radians(10.0))
SQUARE_TO = math.sin(math.radians(10.0))


@dataclass(frozen=True)
class Level:
    """A height webs may hang from, along the way they stand: how far past it they may reach, and
    which of the things named they join there."""

    at: float
    band: float
    joins: tuple[str, ...]


@dataclass(frozen=True)
class Hang:
    """Where webs with nothing under them stand: the plane their paths are drawn on, how far along
    its normal they may reach past it, and which of the things named they join there - and every
    height a web may hang from, lowest first, that one among them."""

    frame: HostFrame
    band: float
    joins: tuple[str, ...]
    levels: tuple[Level, ...] = ()


# Heights webs may hang from closer than this are one: the highest of them, where all are.
LEVELS_APART_MM = 5.0
# The most heights a web is looked for at.
MOST_LEVELS = 8


def hang_frame(
    features: FeatureSet,
    tess: Tessellation,
    supports: list[str],
    pull=None,
    other_side: list[str] | tuple[str, ...] = (),
) -> tuple[Hang | None, str]:
    """For webs with nothing under them: where they stand, or None and why.

    Webs that run from something round - ``other_side`` names what they run to, the rest of
    ``supports`` what they run from - stand along its axis: the webs of a bearing stand along the
    bearing, whatever else is named. Otherwise they stand along the direction the most of the
    things named run along - the axis of a round one, the line two flat ones meet along, else one
    of the part's own axes - the pull first among equals, then the axis of a round thing: a thing
    runs along a direction when most of its faces do.

    They join those things, from the level where the most of them are present - of both sides,
    when there are two - as far up as all of those go, so a web standing there meets every one.
    Each web may hang from any height where both of its ends can begin: every height one of the
    things named begins at, where two of them are present - one of each side - is among
    ``levels``. Things that run along some other way, or are elsewhere, take no part."""
    found = [features.get(ref) for ref in supports]
    missing = [ref for ref, f in zip(supports, found, strict=True) if f is None]
    if missing:
        return None, f"the part has no {', '.join(missing)}"
    if len(found) < 2:
        return None, "a web with nothing under it joins two things or more: name what it joins"
    far = set(other_side)

    def sided(refs: list[str]) -> bool:
        """Both sides among them, when there are two; else two things or more."""
        if not far:
            return len(refs) >= 2
        return any(r in far for r in refs) and any(r not in far for r in refs)

    n = None
    if far:
        axis = _round_axis(
            features, [f for ref, f in zip(supports, found, strict=True) if ref not in far]
        )
        if axis is not None:
            ran = [
                ref
                for ref, f in zip(supports, found, strict=True)
                if _runs_along(features, f, axis)
            ]
            n = axis if sided(ran) else None
    if n is None:
        n, problem = _most_along(features, supports, found, pull)
        if n is None:
            return None, problem
    # Up is the pull's way, or - with none - the way the direction's largest part points.
    sign = float(n @ np.asarray(pull, dtype=float)) if pull is not None else n[np.abs(n).argmax()]
    if sign < 0.0:
        n = -n
    along = [ref for ref, f in zip(supports, found, strict=True) if _runs_along(features, f, n)]
    spans = {ref: extent(tess, features.get(ref).face_ids, tuple(n)) for ref in along}

    def present(level: float) -> list[str]:
        return [r for r, (lo, hi) in spans.items() if lo <= level + 1e-6 and hi >= level + 1.0]

    # Heights where things begin, those within a few millimetres of each other one - the highest
    # of them, where every one of them is - where webs can join something on each side.
    heights: list[float] = []
    first = -math.inf
    for z in sorted({lo for lo, _ in spans.values()}):
        if z - first < LEVELS_APART_MM:
            heights[-1] = z
        else:
            heights.append(z)
            first = z
    heights = [z for z in heights if sided(present(z))]
    if not heights:
        said = ", ".join(f"{ref} {lo:.0f} to {hi:.0f}" for ref, (lo, hi) in spans.items())
        joined = "join them" if not far else "run from one side to the other"
        return None, (
            f"{', '.join(supports)} do not overlap along {_way(n)} ({said} mm), so no web can "
            f"{joined}"
        )
    level = max(heights, key=lambda z: len(present(z)))
    if len(heights) > MOST_LEVELS:
        # As many as that, spread evenly from the lowest to the highest - the main one kept.
        picks = {
            heights[round(k * (len(heights) - 1) / (MOST_LEVELS - 1))] for k in range(MOST_LEVELS)
        }
        heights = sorted({*picks, level})
    joins = present(level)
    top = min(spans[ref][1] for ref in joins)
    centre = np.mean([np.asarray(features.get(r).centroid, dtype=float) for r in joins], axis=0)
    frame = _frame_at(centre + (level - float(centre @ n)) * n, n)
    levels = tuple(
        Level(at=z, band=min(spans[r][1] for r in present(z)) - z, joins=tuple(present(z)))
        for z in heights
    )
    return Hang(frame=frame, band=top - level, joins=tuple(joins), levels=levels), ""


def _round_axis(features: FeatureSet, found: list[Feature]) -> np.ndarray | None:
    """The axis of what webs run from, when it is round - most of its faces, by area, turn about
    an axis, as a bearing's do: the largest of those faces' axis. None for anything else."""
    faces = [features.faces[i] for f in found for i in f.face_ids]
    turning = [f for f in faces if f.surface_type in ("cylinder", "cone") and f.axis is not None]
    flat = [f for f in faces if f.surface_type == "plane" and f.normal is not None]
    if not turning or sum(f.area for f in turning) < sum(f.area for f in flat):
        return None
    axis = np.asarray(max(turning, key=lambda f: f.area).axis, dtype=float)
    return axis / np.linalg.norm(axis)


def _most_along(
    features: FeatureSet, supports: list[str], found: list[Feature], pull
) -> tuple[np.ndarray | None, str]:
    """The direction the most of the things named run along - the pull first among equals, then
    the axis of a round thing, the line two flat ones meet along, else one of the part's own axes.
    Or None and why."""
    faces = [features.faces[i] for f in found for i in f.face_ids]
    axes = sorted(
        (face for face in faces if face.surface_type in ("cylinder", "cone") and face.axis),
        key=lambda face: -face.area_mm2,
    )
    flats = sorted(
        (face for face in faces if face.surface_type == "plane" and face.normal is not None),
        key=lambda face: -face.area_mm2,
    )
    candidates = [] if pull is None else [np.asarray(pull, dtype=float)]
    candidates += [np.asarray(face.axis, dtype=float) for face in axes[:3]]
    for i, first in enumerate(flats[:4]):
        for second in flats[i + 1 : 4]:
            across = np.cross(np.asarray(first.normal), np.asarray(second.normal))
            if np.linalg.norm(across) > 0.2:
                candidates.append(across)
    # With nothing else to go by - flat faces all facing one way or the other - the part's own axes.
    candidates += [np.eye(3)[2], np.eye(3)[1], np.eye(3)[0]]
    candidates = [c / np.linalg.norm(c) for c in candidates if np.linalg.norm(c) > 1e-9]
    # Which of the things named run along each candidate; the first with the most wins.
    along = [
        [ref for ref, f in zip(supports, found, strict=True) if _runs_along(features, f, c)]
        for c in candidates
    ]
    best = max(range(len(candidates)), key=lambda k: (len(along[k]), -k), default=None)
    if best is None or len(along[best]) < 2:
        return None, (
            f"{', '.join(supports)} share no direction a web could stand along - name it, or "
            "something for the webs to stand on"
        )
    return candidates[best], ""


def _runs_along(features: FeatureSet, feature: Feature, d: np.ndarray) -> bool:
    """Whether a thing runs along a direction: most of its round faces turn about it, and its flat
    ones stand square to it - by area, blends aside."""
    counted = ran = 0.0
    for face in (features.faces[i] for i in feature.face_ids):
        if face.surface_type in ("cylinder", "cone") and face.axis is not None:
            counted += face.area_mm2
            ran += face.area_mm2 * (abs(float(np.asarray(face.axis) @ d)) > ALONG)
        elif face.surface_type == "plane" and face.normal is not None:
            counted += face.area_mm2
            ran += face.area_mm2 * (abs(float(np.asarray(face.normal) @ d)) < SQUARE_TO)
    return counted > 0.0 and ran >= 0.5 * counted


def _way(n: np.ndarray) -> str:
    """A direction in words: the axis it is, or its parts."""
    for i, name in enumerate("xyz"):
        if abs(n[i]) > 0.999:
            return name
    return "(" + ", ".join(f"{v:.2f}" for v in n) + ")"


def _gap(
    base: Field,
    features: FeatureSet,
    tess: Tessellation,
    joins: list[str],
    frame: HostFrame,
    band: float,
    step: float,
    probe_height: float,
    pad: float,
) -> tuple[_Footprint, dict[str, np.ndarray]]:
    """Where webs with nothing under them may go, on the plane their paths are drawn on: where the
    part is not - just above the plane and halfway up what they join - in the pieces of that open
    space that reach two or more of them. And where each thing they join is, on the plane, at the
    heights the webs stand through."""
    from scipy import ndimage

    heights = (probe_height, band / 2.0, band - probe_height)
    seen = {ref: _sliced(tess, features.get(ref).face_ids, frame, heights, step) for ref in joins}
    every = np.concatenate([p for p in seen.values() if len(p)])
    lo, hi = every.min(axis=0) - pad, every.max(axis=0) + pad
    cell = max(step, math.sqrt(float(np.prod(hi - lo)) / 1.5e6))
    shape = tuple(np.ceil((hi - lo) / cell).astype(int) + 1)
    gu, gv = np.meshgrid(np.arange(shape[0]), np.arange(shape[1]), indexing="ij")
    uv = lo + np.stack([gu.ravel(), gv.ravel()], axis=1) * cell
    air = np.ones(len(uv), dtype=bool)
    for height in (probe_height, band / 2.0):
        air &= base.sample(frame.to_world(uv, height)) > 0.0
    air = air.reshape(shape)
    pieces, count = ndimage.label(air)
    # Open space reaches a thing when it comes within a grid cell or two of the thing's faces.
    near = int(math.ceil((base.grid.spacing_mm + cell) / cell))
    reaches: list[set[int]] = []
    for points in seen.values():
        marks = np.zeros(shape, dtype=bool)
        index = np.clip(np.round((points - lo) / cell).astype(int), 0, np.asarray(shape) - 1)
        marks[index[:, 0], index[:, 1]] = True
        marks = ndimage.binary_dilation(marks, iterations=near)
        reaches.append(set(np.unique(pieces[marks & air]).tolist()) - {0})
    kept = [k for k in range(1, count + 1) if sum(k in r for r in reaches) >= 2]
    return _Footprint(lo=lo, step=cell, mask=np.isin(pieces, kept)), seen


def _inset(a: np.ndarray, b: np.ndarray, by: float) -> tuple[np.ndarray, np.ndarray]:
    """The stretch ``a``-``b`` less ``by`` at each end: its middle, if it is no longer than that."""
    length = float(np.linalg.norm(b - a))
    if length <= 2.0 * by:
        middle = (a + b) / 2.0
        return middle, middle
    step = (b - a) * (by / length)
    return a + step, b - step


def _facing(between: dict[str, np.ndarray], across: np.ndarray) -> tuple[float, float] | None:
    """Where two of the things webs join face each other along a direction: of every two, the
    stretch across the direction both reach - from the lowest to the highest of these. None when
    no two do."""
    reach = [
        (float((p @ across).min()), float((p @ across).max())) for p in between.values() if len(p)
    ]
    shared = [
        (max(a[0], b[0]), min(a[1], b[1]))
        for i, a in enumerate(reach)
        for b in reach[i + 1 :]
        if min(a[1], b[1]) > max(a[0], b[0])
    ]
    if not shared:
        return None
    return min(s[0] for s in shared), max(s[1] for s in shared)


def _sliced(tess: Tessellation, face_ids, frame: HostFrame, heights, step: float) -> np.ndarray:
    """Where faces cross the planes ``heights`` above the frame's, as points on its plane about a
    ``step`` apart - what a big face with few corners is at those heights - with the corners of its
    facets that lie between the lowest and highest."""
    mine = np.isin(tess.face_id, list(face_ids))
    corners = tess.vertices[tess.triangles[mine]]
    along = corners @ frame.normal - float(frame.origin @ frame.normal)
    out = [corners[(along >= min(heights)) & (along <= max(heights))]]
    for height in heights:
        d = along - height
        crossing = (d.min(axis=1) < 0.0) & (d.max(axis=1) > 0.0)
        ends = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            di, dj = d[crossing, i], d[crossing, j]
            t = np.where((di < 0.0) != (dj < 0.0), di / np.where(di == dj, 1.0, di - dj), np.nan)
            ends.append(
                corners[crossing, i] + t[:, None] * (corners[crossing, j] - corners[crossing, i])
            )
        ends = np.stack(ends, axis=1)
        found = ~np.isnan(ends[:, :, 0])
        pairs = [row[ok][:2] for row, ok in zip(ends, found, strict=True) if ok.sum() >= 2]
        for p, q in pairs:
            n = int(math.ceil(float(np.linalg.norm(q - p)) / step)) + 1
            out.append(p + np.outer(np.linspace(0.0, 1.0, n), q - p))
    points = np.concatenate([o.reshape(-1, 3) for o in out]) if out else np.zeros((0, 3))
    return frame.to_plane(points) if len(points) else np.zeros((0, 2))


def _headroom(
    finder: _Faces,
    frame: HostFrame,
    a: np.ndarray,
    b: np.ndarray,
    probe_height: float,
    margin: float,
) -> float | None:
    """How tall a rib along ``a``-``b`` can stand before it meets something over it: the open
    space above its middle, clear of its ends by ``margin`` - where it meets what it runs into.
    None when nothing stands over it."""
    length = float(np.linalg.norm(b - a))
    ts = [0.5] if length <= 2.0 * margin else np.linspace(margin / length, 1 - margin / length, 7)
    points = frame.to_world(a + np.outer(ts, b - a), probe_height)
    above = finder.exits_along(points, frame.normal)
    above = above[~np.isnan(above)]
    return None if not len(above) else probe_height + float(above.min())


@dataclass
class _Footprint:
    """Where the host is, seen square to its plane, as a raster of small cells."""

    lo: np.ndarray
    step: float
    mask: np.ndarray

    @staticmethod
    def of(tess: Tessellation, face_ids, frame: HostFrame, step: float) -> _Footprint:
        mine = np.isin(tess.face_id, list(face_ids))
        corners = frame.to_plane(tess.vertices[tess.triangles[mine]].reshape(-1, 3)).reshape(
            -1, 3, 2
        )
        lo = corners.reshape(-1, 2).min(axis=0) - step
        hi = corners.reshape(-1, 2).max(axis=0) + step
        shape = np.ceil((hi - lo) / step).astype(int) + 1
        mask = np.zeros(tuple(shape), dtype=bool)
        for tri in corners:
            a, b, c = tri
            t_lo = np.floor((tri.min(axis=0) - lo) / step).astype(int)
            t_hi = np.ceil((tri.max(axis=0) - lo) / step).astype(int)
            iu = np.arange(t_lo[0], t_hi[0] + 1)
            iv = np.arange(t_lo[1], t_hi[1] + 1)
            gu, gv = np.meshgrid(iu, iv, indexing="ij")
            p = np.stack([lo[0] + gu * step, lo[1] + gv * step], axis=-1)
            inside = _in_triangle(p, a, b, c, step * 0.5)
            mask[gu[inside], gv[inside]] = True
        return _Footprint(lo=lo, step=step, mask=mask)

    def covers(self, uv: np.ndarray) -> np.ndarray:
        index = np.round((uv - self.lo) / self.step).astype(int)
        ok = np.all((index >= 0) & (index < np.asarray(self.mask.shape)), axis=1)
        out = np.zeros(uv.shape[0], dtype=bool)
        out[ok] = self.mask[index[ok, 0], index[ok, 1]]
        return out

    def cells(self) -> np.ndarray:
        """Every cell where the host is, as a point on its plane."""
        return self.lo + np.argwhere(self.mask) * self.step


def _in_triangle(p: np.ndarray, a, b, c, pad: float) -> np.ndarray:
    """Whether points lie in a triangle, or within ``pad`` of it - so no cell falls between two. A
    triangle seen edge on - of a face square to the plane - is the line it collapses to."""

    def side(p0, p1):
        edge = p1 - p0
        length = max(float(np.hypot(*edge)), 1e-12)
        cross = edge[0] * (p[..., 1] - p0[1]) - edge[1] * (p[..., 0] - p0[0])
        return cross / length

    area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if abs(area) < 1e-12:
        p0, p1 = max(((a, b), (b, c), (c, a)), key=lambda e: float(np.hypot(*(e[1] - e[0]))))
        edge = p1 - p0
        t = np.clip(((p - p0) @ edge) / max(float(edge @ edge), 1e-24), 0.0, 1.0)
        return np.linalg.norm(p - (p0 + t[..., None] * edge), axis=-1) <= pad
    sign = 1.0 if area > 0 else -1.0
    return (sign * side(a, b) >= -pad) & (sign * side(b, c) >= -pad) & (sign * side(c, a) >= -pad)


# --- paths ----------------------------------------------------------------------------------------


def _paths(
    placement: Placement,
    frame: HostFrame,
    footprint: _Footprint,
    features: FeatureSet,
    between: dict[str, np.ndarray] | None = None,
):
    """Every path the layout draws: (start, unit direction, length), on the host's plane. Each is
    laid only across where the host is - never through the empty corners of a rectangle round a
    host that is not one, where it could only miss.

    Webs with nothing under them are laid by where the things they join are - ``between``, each
    on the plane: spokes fanned across the others than what they turn about, straight paths across
    where two of them face each other."""
    layout = placement.layout
    cells = footprint.cells()
    if not len(cells):
        return
    if layout.kind == "lines":
        # Free lines: each at its own angle, crossing where its share of the way across the host
        # puts it - on a lattice from the host's edge, the spacing apart - 5 mm when none is said -
        # so a place is a place a person would draw, and the same share the same line. Two lines
        # at one angle and one place are one line.
        step = float(layout.spacing_mm or FREE_STEP_MM)
        seen: set[tuple[float, float]] = set()
        for line in layout.lines:
            angle = math.radians(line.angle_deg)
            d = np.array([math.cos(angle), math.sin(angle)])
            m = np.array([-d[1], d[0]])
            across, along = cells @ m, cells @ d
            low, high = float(across.min()), float(across.max())
            c = low + step * round(line.at * (high - low) / step)
            if (round(line.angle_deg, 6), round(c, 6)) in seen:
                continue
            seen.add((round(line.angle_deg, 6), round(c, 6)))
            yield c * m + float(along.min()) * d, d, float(along.max() - along.min())
        return
    if layout.kind == "radial":
        centre_feature = features.get(layout.centre)
        assert centre_feature is not None
        point = _axis_point(features, centre_feature)
        if point is None:
            return
        centre = frame.to_plane(np.asarray(point).reshape(1, 3))[0]
        reach = float(np.max(np.linalg.norm(cells - centre, axis=1))) + footprint.step
        count = int(layout.count or 0)
        first, arc = math.radians(layout.phase_deg), 2.0 * math.pi
        if layout.spread == "across":
            towards = cells
            if between is not None:
                others = [p for ref, p in between.items() if ref != layout.centre and len(p)]
                towards = np.concatenate(others) if others else cells
            fan = _arc_of(towards, centre)
            if fan is not None:
                first, arc = fan
        whole = arc > 2.0 * math.pi - 1e-9
        if layout.spacing_mm:
            # Spokes the spacing apart where they end, round the far part of the floor: no more
            # of them than that leaves room for.
            rim = float(np.percentile(np.linalg.norm(cells - centre, axis=1), 90.0))
            room = max(1, int(math.floor(arc * rim / float(layout.spacing_mm))))
            count = min(count, room) if count else room
        for k in range(count):
            # All the way round, the first spoke at the phase; across a fan, each in the middle
            # of its share, so none lies on the fan's edge.
            angle = first + arc * (k if whole else k + 0.5) / count
            yield centre, np.array([math.cos(angle), math.sin(angle)]), reach
        return
    # A grid is one lattice: every family at the first family's spacing, laid from one origin -
    # the host's middle - so families cross at common points. Three families 60 degrees apart
    # whose offsets add up then make triangles, not three unrelated sets of lines.
    lattice = None
    if layout.kind == "grid" and layout.families:
        first = layout.families[0]
        if first.spacing_mm is not None:
            lattice = float(first.spacing_mm)
        elif first.count is not None:
            angle = math.radians(first.angle_deg)
            m = np.array([-math.sin(angle), math.cos(angle)])
            across = cells @ m
            lattice = float(across.max() - across.min()) / first.count
    for family in layout.families:
        angle = math.radians(family.angle_deg)
        d = np.array([math.cos(angle), math.sin(angle)])
        m = np.array([-d[1], d[0]])
        across = cells @ m
        along = cells @ d
        low, high = float(across.min()), float(across.max())
        facing = None if between is None else _facing(between, m)
        if facing is not None:
            low, high = facing
        if lattice is not None:
            n = np.arange(math.floor(low / lattice) - 1, math.ceil(high / lattice) + 1)
            offsets = [c for c in (n + family.offset) * lattice if low <= c <= high]
        elif family.spacing_mm is not None:
            gap = float(family.spacing_mm)
            offsets = list(np.arange(low + family.offset * gap, high, gap))
        else:
            count = int(family.count or 1)
            gap = (high - low) / count
            offsets = [low + (k + family.offset) * gap for k in range(count)]
        if family.count is not None and len(offsets) > family.count:
            # A count as well as a spacing: that many of them, round the middle of the floor.
            middle = (low + high) / 2.0
            offsets = sorted(sorted(offsets, key=lambda c: abs(c - middle))[: family.count])
        for c in offsets:
            yield c * m + float(along.min()) * d, d, float(along.max() - along.min())


def _arc_of(points: np.ndarray, centre: np.ndarray) -> tuple[float, float] | None:
    """The arc round ``centre`` that ``points`` fill: where it starts, in radians, and how wide it
    is. None when they fill nearly all the way round - spokes then go all the way."""
    points = np.asarray(points, dtype=float) - centre
    if not len(points):
        return None
    angles = np.sort(np.arctan2(points[:, 1], points[:, 0]) % (2.0 * math.pi))
    gaps = np.diff(np.concatenate([angles, [angles[0] + 2.0 * math.pi]]))
    widest = int(np.argmax(gaps))
    if gaps[widest] < math.radians(30.0):
        return None
    start = float(angles[(widest + 1) % len(angles)])
    return start, 2.0 * math.pi - float(gaps[widest])


def _axis_point(features: FeatureSet, feature: Feature) -> tuple[float, float, float] | None:
    """A point on the axis spokes turn about: see :func:`axis_of`. None for a thing with none."""
    found = axis_of(features, feature)
    return None if found is None else found[0]


def axis_of(
    features: FeatureSet, feature: Feature
) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    """The axis a round thing turns about, as a point on it and its direction: its own - a boss, a
    bore, a round face - or, for a ring the CAD made of several faces, the axis its round faces
    share, the largest of them first; a face of a ring that is not round itself - a blend between
    its bands, a flat face across it - turns about the axis of the round faces round it, a flat one
    only about an axis square to it: a fillet along a wall's edge is no axis of the wall's. None
    for a thing with no axis: spokes turn only about round things."""
    if feature.axis_id and feature.axis_id in features.axes:
        axis = features.axes[feature.axis_id]
        return axis.point, axis.direction
    faces = [features.faces[f] for f in feature.face_ids if f in features.faces]
    round_ = [f for f in faces if _turns(f)]
    if not round_:
        near = {n for f in faces for n in getattr(f, "neighbours", ()) if n in features.faces}
        round_ = [features.faces[n] for n in near if _turns(features.faces[n])]
        flat = [f for f in faces if f.surface_type == "plane" and f.normal is not None]
        if flat:
            normal = np.asarray(flat[0].normal, dtype=float)
            round_ = [f for f in round_ if abs(float(np.asarray(f.axis) @ normal)) > ALONG]
    if not round_:
        return None
    # The axis most of their area turns about.
    area: dict[str, float] = {}
    for face in round_:
        key = next(
            (a.id for a in features.axes.values() if face.face_id in a.face_ids),
            f"face:{face.face_id}",
        )
        area[key] = area.get(key, 0.0) + face.area
    best = max(area, key=lambda k: (area[k], k))
    if best in features.axes:
        axis = features.axes[best]
        return axis.point, axis.direction
    face = features.faces[int(best.split(":", 1)[1])]
    return tuple(face.axis_point), tuple(face.axis)


def _turns(face) -> bool:
    """Whether a face turns about an axis: a cylinder, a cone or a torus that says where its axis
    is."""
    return (
        face.surface_type in ("cylinder", "cone", "torus")
        and face.axis is not None
        and face.axis_point is not None
    )


def _runs(usable: np.ndarray) -> list[tuple[int, int]]:
    """Index ranges where ``usable`` is true throughout, inclusive."""
    padded = np.concatenate([[False], usable, [False]])
    edges = np.flatnonzero(np.diff(padded.astype(int)))
    return [(int(a), int(b) - 1) for a, b in zip(edges[0::2], edges[1::2], strict=True)]


# --- what a path meets at its ends ----------------------------------------------------------------


class _Faces:
    """Which CAD face is nearest a point, exactly: the closest point on the tessellated surface."""

    def __init__(self, tess: Tessellation):
        import trimesh

        self.tess = tess
        self.mesh = trimesh.Trimesh(tess.vertices, tess.triangles, process=False)

    def nearest(self, point: np.ndarray) -> int:
        return self.nearest_point(point)[0]

    def nearest_point(self, point: np.ndarray) -> tuple[int, np.ndarray]:
        """The face nearest a point, and the nearest point on it."""
        closest, _, triangle = self.mesh.nearest.on_surface(
            np.asarray(point, dtype=float).reshape(1, 3)
        )
        return int(self.tess.face_id[int(triangle[0])]), np.asarray(closest[0], dtype=float)

    def facing(
        self, start: np.ndarray, direction: np.ndarray, within: float
    ) -> tuple[int, np.ndarray] | None:
        """The face a ray from ``start`` along ``direction`` meets first, within ``within``, and
        where it meets it - exactly, on the tessellation. None when it meets none so near."""
        origin = np.asarray(start, dtype=float).reshape(1, 3)
        way = np.asarray(direction, dtype=float).reshape(1, 3)
        hits, _, triangles = self.mesh.ray.intersects_location(origin, way, multiple_hits=False)
        if not len(hits) or float(np.linalg.norm(hits[0] - origin[0])) > within:
            return None
        return int(self.tess.face_id[int(triangles[0])]), np.asarray(hits[0], dtype=float)

    def exit_along(self, inside: np.ndarray, direction: np.ndarray) -> float | None:
        """How far from a point inside the metal, along ``direction``, the metal ends."""
        distance = self.exits_along(np.asarray(inside, dtype=float).reshape(1, 3), direction)[0]
        return None if np.isnan(distance) else float(distance)

    def exits_along(self, inside: np.ndarray, direction: np.ndarray) -> np.ndarray:
        """The same for many points at once, in one cast: NaN where nothing is met."""
        return self.through(inside, direction)[0]

    def through(self, inside: np.ndarray, direction: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """How far from points inside the metal, along ``direction`` - one for all, or one each -
        the metal ends, and the face it ends at: NaN and -1 where nothing is met."""
        origins = np.asarray(inside, dtype=float).reshape(-1, 3)
        out = np.full(len(origins), np.nan)
        faces = np.full(len(origins), -1, dtype=np.int64)
        if not len(origins):
            return out, faces
        directions = np.asarray(direction, dtype=float)
        if directions.ndim == 1:
            directions = np.tile(directions, (len(origins), 1))
        hits, rays, triangles = self.mesh.ray.intersects_location(
            origins, directions, multiple_hits=False
        )
        if len(hits):
            out[rays] = np.linalg.norm(hits - origins[rays], axis=1)
            faces[rays] = self.tess.face_id[triangles]
        return out, faces


# What a face met elsewhere is part of: the features that say what a thing is.
_TELLING = (FeatureKind.BORE, FeatureKind.BOSS, FeatureKind.HOLE, FeatureKind.PLANAR_GROUP)


def _thing_faces(features: FeatureSet, face: int, ref: str | None) -> tuple[int, ...]:
    """The faces of what a rib's end meets: the support ``ref`` - every face of it - or, met
    elsewhere, what the face is part of - the bore, boss, hole or flat area it belongs to - the
    face with them either way. Never what they touch: a wall behind a boss is not the boss."""
    faces = {int(face)}
    named = features.get(ref) if ref is not None else None
    if named is not None:
        faces |= set(named.face_ids)
    else:
        for feature in features.containing(int(face)):
            if feature.kind in _TELLING:
                faces |= set(feature.face_ids)
    return tuple(sorted(faces))


def _supports_by_face(features: FeatureSet, atlas: Atlas, supports: list[str]) -> dict[int, str]:
    """The faces that count as each support: its own, and those touching them - the fillet at its
    foot, a chamfer on its edge - a face of its own before one it touches. Nothing further: a wall
    that merely shares a boss's axis is not the boss, and when a path ends on something else the
    report says what, so it can be named."""
    owner: dict[int, str] = {}
    for ref in supports:
        for face in features.get(ref).face_ids:
            owner.setdefault(face, ref)
    for ref in supports:
        for face in features.get(ref).face_ids:
            for n in atlas.faces[face].neighbours:
                owner.setdefault(n, ref)
    return owner


@dataclass
class _Met:
    """What a stretch of path meets past one of its ends: ``support``, ``elsewhere``, ``keep_out``
    or ``edge``; the face it met, and the support that is; and where the rib's end could be buried
    in it, nearest first, with how tall a rib whose end is buried there can stand."""

    kind: str
    face: int | None = None
    ends: np.ndarray | None = None
    tops: np.ndarray | None = None
    ref: str | None = None
    surface: np.ndarray | None = None
    """Where the path meets it, on its face, in the part's coordinates."""

    @property
    def top(self) -> float | None:
        """The tallest a rib can stand at this end."""
        return None if self.tops is None else float(self.tops.max())

    def end_for(self, height: float) -> np.ndarray:
        """The nearest place to bury the end that keeps it inside all the way up to ``height``."""
        assert self.ends is not None and self.tops is not None
        enough = np.flatnonzero(self.tops >= height - 1e-6)
        return self.ends[int(enough[0]) if len(enough) else int(np.argmax(self.tops))]


def _end(
    base: Field,
    frame: HostFrame,
    finder: _Faces,
    support_of: dict[int, str],
    at: np.ndarray,
    outward: np.ndarray,
    reach: float,
    step: float,
    probe_height: float,
    blocked: np.ndarray,
    index: int,
    sense: int,
    bury: float,
    thing: Callable[[int, str | None], np.ndarray] | None = None,
    half_width: float = 0.0,
) -> _Met:
    """What a stretch of path meets past one end, and how tall a rib can stand where it ends.

    **An end is as tall as what it meets**, never the metal behind it: a boss stood against a tall
    wall is met as tall as the boss. ``thing`` gives points over the faces of what the end meets -
    the support its face belongs to, or the feature it is part of - and the end stands as tall as
    the highest of them within the rib's width, ``half_width`` either side, and as deep into it as
    the end may be buried.

    A rib's end is buried in what it meets, and its last ``bury`` millimetres must stay inside the
    metal all the way up - taller, and the end would hang in the air. How tall that is depends on
    how deep the end goes: a wall with draft leans away from the rib as it rises, so the metal just
    inside its face runs out within millimetres while deeper in it goes on to the wall's top. So
    every depth into the metal is weighed, as far as the metal goes - never through to the other
    side - and the rib takes the nearest that is deep enough for the height it ends up with.
    """
    beyond = index + sense
    if 0 <= beyond < blocked.size and blocked[beyond]:
        return _Met("keep_out")
    s = np.arange(step, reach + step, step)
    probes = at + np.outer(s, outward)
    metal = base.sample(frame.to_world(probes, probe_height)) < 0.0
    if not metal.any():
        return _Met("edge")
    first = int(np.argmax(metal))
    hit = probes[first]
    # The face the path runs into: a ray along the path from a grid cell back into the air - the
    # field finds the metal to within half a cell - exactly on the tessellation. Where the ray finds
    # none so near, the face nearest where the metal starts.
    spacing = base.grid.spacing_mm
    before = (probes[first - 1] if first else at) - spacing * outward
    way = outward[0] * frame.e1 + outward[1] * frame.e2
    met = finder.facing(frame.to_world(before, probe_height)[0], way, 2.0 * (step + spacing))
    if met is None:
        face, surface = finder.nearest_point(frame.to_world(hit, probe_height)[0])
    else:
        face, surface = met
    ref = support_of.get(face)
    kind = "support" if ref is not None else "elsewhere"

    # Into the metal from where the path meets it, for as long as it stays metal.
    depth = np.arange(0.0, DEEPEST * bury + step, step)
    into = hit + np.outer(depth, outward)
    world = frame.to_world(into, probe_height)
    inside = base.sample(world)
    run = len(inside) if (inside < 0.0).all() else max(int(np.argmin(inside < 0.0)), 1)
    # How far the metal goes up from each point - only where the field is sure it is metal: just
    # inside a face the field and the true surface can disagree, and a ray from air measures air.
    rises = np.zeros(run)
    sure = np.flatnonzero(inside[:run] < -0.25 * base.grid.spacing_mm)
    if len(sure):
        rises[sure] = np.nan_to_num(finder.exits_along(world[sure], frame.normal), nan=0.0)
    # No taller than what it meets: the metal found behind that, however tall, is something else's.
    top = math.inf
    if thing is not None:
        met_top = _local_top(
            thing(face, ref), frame, surface, way, half_width, float(depth[-1]), step
        )
        if met_top is None:
            met_top = _local_top(
                thing(face, None), frame, surface, way, half_width, float(depth[-1]), step
            )
        top = probe_height if met_top is None else max(met_top, probe_height)
    width = int(round(bury / step))
    if run <= width:
        # Thinner than the burial: as deep as it goes, as tall as all of it allows.
        tops = np.minimum(np.array([probe_height + rises.min()]), top)
        return _Met(kind, face, into[run - 1 : run], tops, ref, surface)
    # An end at a depth keeps the last ``bury`` of the rib at the depths behind it inside, so it
    # stands as tall as the lowest of those columns of metal.
    held = np.lib.stride_tricks.sliding_window_view(rises, width + 1).min(axis=1)
    return _Met(kind, face, into[width:run], np.minimum(probe_height + held, top), ref, surface)


def _local_top(
    points: np.ndarray,
    frame: HostFrame,
    surface: np.ndarray,
    way: np.ndarray,
    half_width: float,
    depth: float,
    step: float,
) -> float | None:
    """How far above the frame's plane what an end meets rises where the end meets it: the highest
    of ``points`` - over its faces - within the end's width either side of where the path meets it,
    and from a step before that to ``depth`` into it. None when none of them is there."""
    if not len(points):
        return None
    up = np.asarray(frame.normal, dtype=float)
    ahead = np.asarray(way, dtype=float) - (np.asarray(way, dtype=float) @ up) * up
    ahead = ahead / max(float(np.linalg.norm(ahead)), 1e-12)
    across = np.cross(up, ahead)
    offset = points - np.asarray(surface, dtype=float)
    lateral, into = offset @ across, offset @ ahead
    mine = (np.abs(lateral) <= half_width + step) & (into >= -(half_width + step)) & (into <= depth)
    if not mine.any():
        return None
    return float(((points[mine] - frame.origin) @ up).max())


# --- keep-outs ------------------------------------------------------------------------------------


@dataclass
class _Disc:
    """A keep-out seen square to the host: a disc, and the clearance around it - for something
    round, a hole, a boss, a bore."""

    feature: str
    centre: np.ndarray
    radius: float
    clearance: float
    rule: int = 0
    """Which of the placement's keep-out rules it is kept clear of by."""

    def blocks(self, uv: np.ndarray, half_width: float) -> np.ndarray:
        return np.linalg.norm(uv - self.centre, axis=1) < self.radius + self.clearance + half_width

    def gap(self, a: np.ndarray, b: np.ndarray, half_width: float) -> float:
        """The gap between a rib's side along ``a``-``b`` and the edge of this keep-out."""
        ab = b - a
        t = np.clip((self.centre - a) @ ab / max(ab @ ab, 1e-12), 0.0, 1.0)
        return float(np.linalg.norm(a + t * ab - self.centre)) - self.radius - half_width

    def row(self) -> dict:
        return {
            "feature": self.feature,
            "centre": [round(float(v), 2) for v in self.centre],
            "radius_mm": round(self.radius, 2),
            "clearance_mm": self.clearance,
        }


@dataclass
class _Outline:
    """A keep-out seen square to the host by its own outline - for a face or anything not round,
    which a disc would overstate by half its length - and the clearance around it: a raster of
    where it is, and how far every cell round it is from it."""

    feature: str
    lo: np.ndarray
    step: float
    distance: np.ndarray
    clearance: float
    rule: int = 0
    """Which of the placement's keep-out rules it is kept clear of by."""

    # How far round the outline the raster reaches beyond the clearance: past the widest rib.
    REACH = 40.0

    @staticmethod
    def of(
        feature: str, tess: Tessellation, face_ids, frame: HostFrame, step: float, clearance: float
    ) -> _Outline:
        from scipy import ndimage

        pad = clearance + _Outline.REACH
        inner = _Footprint.of(tess, face_ids, frame, step)
        border = int(math.ceil(pad / step))
        mask = np.pad(inner.mask, border)
        lo = inner.lo - border * step
        distance = ndimage.distance_transform_edt(~mask) * step
        return _Outline(feature=feature, lo=lo, step=step, distance=distance, clearance=clearance)

    def _at(self, uv: np.ndarray) -> np.ndarray:
        index = np.round((np.atleast_2d(uv) - self.lo) / self.step).astype(int)
        ok = np.all((index >= 0) & (index < np.asarray(self.distance.shape)), axis=1)
        out = np.full(index.shape[0], np.inf)
        out[ok] = self.distance[index[ok, 0], index[ok, 1]]
        return out

    def blocks(self, uv: np.ndarray, half_width: float) -> np.ndarray:
        return self._at(uv) < self.clearance + half_width

    def gap(self, a: np.ndarray, b: np.ndarray, half_width: float) -> float:
        count = max(2, int(math.ceil(float(np.linalg.norm(b - a)) / self.step)) + 1)
        points = a + np.outer(np.linspace(0.0, 1.0, count), b - a)
        return float(np.min(self._at(points))) - half_width

    def row(self) -> dict:
        return {"feature": self.feature, "outline": True, "clearance_mm": self.clearance}


@dataclass
class _RibKeep:
    """Another block's rib, kept clear of: its line seen square to the host, as wide as its
    footprint - fillet and all - and how far along the host's normal it reaches, from and to."""

    a: np.ndarray
    b: np.ndarray
    half: float
    clearance: float
    low: float = -math.inf
    high: float = math.inf

    @staticmethod
    def of(rib: Rib, frame: HostFrame, clearance: float, far_side: bool = False) -> _RibKeep | None:
        """None for a rib wholly on the far side of the host, where nothing standing here goes -
        unless ``far_side`` asks for those too, as a hole through the host does."""
        base = np.asarray([rib.start, rib.end], dtype=float)
        up = np.asarray(rib.pull, dtype=float)
        tops = base + np.outer(rib.heights, up)
        level = float(frame.origin @ frame.normal)
        along = np.concatenate([base @ frame.normal, tops @ frame.normal]) - level
        if float(along.max()) < -1.0 and not far_side:
            return None
        a, b = frame.to_plane(base)
        return _RibKeep(
            a=a,
            b=b,
            half=_footprint(rib),
            clearance=clearance,
            low=float(along.min()),
            high=float(along.max()),
        )

    @staticmethod
    def of_hole(hole: Hole, frame: HostFrame, clearance: float) -> _RibKeep:
        """A hole of another block, kept clear of like a rib: its run seen square to the host, as
        wide as it is, and how far along the host's normal it goes."""
        centre, axis = np.asarray(hole.centre, dtype=float), np.asarray(hole.axis, dtype=float)
        ends = np.array([centre + hole.above_mm * axis, centre - hole.depth_mm * axis])
        along = ends @ frame.normal - float(frame.origin @ frame.normal)
        a, b = frame.to_plane(ends)
        return _RibKeep(
            a=a,
            b=b,
            half=hole.radius_mm,
            clearance=clearance,
            low=float(along.min()),
            high=float(along.max()),
        )

    def clashes(self, a: np.ndarray, b: np.ndarray, half_width: float, top: float) -> bool:
        """Whether a rib along ``a``-``b`` standing ``top`` tall comes nearer this one than the
        clearance: beside it, and at a height it reaches too."""
        return self.near(a, b, half_width, 0.0, top)

    def near(self, a: np.ndarray, b: np.ndarray, half_width: float, low: float, high: float):
        """Whether something along ``a``-``b``, reaching from ``low`` to ``high`` along the
        host's normal, comes nearer this one than the clearance."""
        if self.low > high + self.clearance or self.high < low - self.clearance:
            return False
        return self.gap(a, b, half_width) < self.clearance

    def _distance(self, uv: np.ndarray) -> np.ndarray:
        ab = self.b - self.a
        t = np.clip((np.atleast_2d(uv) - self.a) @ ab / max(ab @ ab, 1e-12), 0.0, 1.0)
        return np.linalg.norm(np.atleast_2d(uv) - (self.a + np.outer(t, ab)), axis=1)

    def blocks(self, uv: np.ndarray, half_width: float) -> np.ndarray:
        return self._distance(uv) < self.half + self.clearance + half_width

    def gap(self, a: np.ndarray, b: np.ndarray, half_width: float) -> float:
        points = a + np.outer(np.linspace(0.0, 1.0, 101), b - a)
        return float(np.min(self._distance(points))) - self.half - half_width


def _kept_clear(
    thing: Rib | Hole, frame: HostFrame, clearance: float, far_side: bool = False
) -> _RibKeep | None:
    """Another block's rib, pad or hole, as a block placed after it keeps clear of it."""
    if isinstance(thing, Hole):
        return _RibKeep.of_hole(thing, frame, clearance)
    return _RibKeep.of(thing, frame, clearance, far_side)


def _keep_outs(
    features: FeatureSet,
    atlas: Atlas,
    tess: Tessellation,
    placement: Placement | HoleSet,
    frame: HostFrame,
    host_faces: set[int],
    step: float,
) -> list[_Disc | _Outline]:
    """What the placement keeps clear of, each as seen square to the host: something round as a
    disc, anything else by its own outline. Every feature of a kind named counts when it is on the
    host - none, for webs with nothing under them."""
    touching = {n for f in host_faces for n in atlas.faces[f].neighbours}
    keeps: list[_Disc | _Outline] = []
    for rule, keep in enumerate(placement.keep_out):
        chosen = [features.get(f) for f in keep.features]
        for kind in keep.kinds:
            for feature in features.features.values():
                if str(feature.kind) != kind:
                    continue
                on_host = host_faces.intersection(feature.opens_onto) or touching.intersection(
                    feature.face_ids
                )
                if on_host:
                    chosen.append(feature)
        for feature in chosen:
            if _round(features, feature):
                made = _disc(features, tess, frame, feature, keep.clearance_mm)
            else:
                made = _Outline.of(
                    feature.id, tess, feature.face_ids, frame, step, keep.clearance_mm
                )
            made.rule = rule
            keeps.append(made)
    return keeps


@dataclass
class _Shut:
    """One thing the part keeps closed. A hole or bore is the open space it holds: a cylinder from
    ``point`` along ``way``, ``low`` to ``high`` along it - as far as its faces go - and ``radius``
    out, as far as they go, counterbores and chamfers included. Anything else is points on its
    faces. ``box`` bounds it."""

    name: str
    box: np.ndarray
    point: np.ndarray | None = None
    way: np.ndarray | None = None
    low: float = 0.0
    high: float = 0.0
    radius: float = 0.0
    cloud: Any = None

    def distance(self, where: np.ndarray) -> np.ndarray:
        """How far each point is from it - nothing, inside the space a hole holds open."""
        if self.cloud is not None:
            found, _ = self.cloud.query(where)
            return np.asarray(found, dtype=float)
        assert self.point is not None and self.way is not None
        q = where - self.point
        along = q @ self.way
        out = np.linalg.norm(q - np.outer(along, self.way), axis=1)
        past = np.maximum(np.maximum(self.low - along, along - self.high), 0.0)
        return np.hypot(past, np.maximum(out - self.radius, 0.0))


@dataclass
class _Closed:
    """What the part keeps closed - its holes, its bores, what the drawing controls. A rib keeps
    its metal ``clearance`` clear of each - its sides and top, its ends buried in what it meets,
    the root fillet where it meets the host - measured from points over it no more than
    ``spacing`` apart."""

    shut: list[_Shut]
    boxes: np.ndarray
    clearance: float
    spacing: float

    @classmethod
    def of(
        cls,
        features: FeatureSet,
        tess: Tessellation,
        refs: list[str],
        clearance: float,
        spacing: float,
    ) -> _Closed | None:
        shut = [
            made
            for ref in refs
            if features.get(ref) is not None
            for part in _closed_parts(features, features.get(ref))
            if (made := _shut_of(features, tess, part, spacing)) is not None
        ]
        if not shut:
            return None
        return cls(shut, np.stack([s.box for s in shut]), clearance, spacing)

    def reached(self, frame: HostFrame, rib: Rib) -> str | None:
        """The nearest of what the part keeps closed that ``rib`` comes nearer than the clearance
        to, or None. Points over a rib may miss its nearest by a little under the spacing, so a
        rib is taken only when surely too near - never one the host's keep-outs let stand."""
        low, high = _bounds(rib)
        grow = self.clearance + self.spacing
        near = np.flatnonzero(
            np.all(self.boxes[:, 0] <= high + grow, axis=1)
            & np.all(self.boxes[:, 1] >= low - grow, axis=1)
        )
        if not len(near):
            return None
        skin = _skin(rib, frame, self.spacing)
        best: tuple[float, str] | None = None
        for k in near:
            shut = self.shut[k]
            mine = np.all(skin >= shut.box[0] - grow, axis=1) & np.all(
                skin <= shut.box[1] + grow, axis=1
            )
            if not mine.any():
                continue
            gap = float(shut.distance(skin[mine]).min())
            if gap < self.clearance - 0.75 * self.spacing and (best is None or gap < best[0]):
                best = (gap, shut.name)
        return None if best is None else best[1]


def _closed_parts(features: FeatureSet, feature: Feature) -> list[Feature]:
    """What a closed feature is made of, one by one: a pattern of holes is its holes."""
    if feature.kind == FeatureKind.HOLE_PATTERN:
        mine = set(feature.face_ids)
        holes = [h for h in features.of_kind(FeatureKind.HOLE) if set(h.face_ids) <= mine]
        if holes:
            return holes
    return [feature]


def _shut_of(
    features: FeatureSet, tess: Tessellation, feature: Feature, spacing: float
) -> _Shut | None:
    """A closed feature as a rib keeps clear of it: a hole or bore by the space it holds open,
    anything else by points over its faces."""
    from scipy.spatial import cKDTree

    mine = np.isin(tess.face_id, list(feature.face_ids))
    corners = tess.vertices[np.unique(tess.triangles[mine])]
    if not len(corners):
        return None
    box = np.stack([corners.min(axis=0), corners.max(axis=0)])
    axis = features.axes.get(feature.axis_id) if feature.axis_id else None
    if feature.kind in (FeatureKind.HOLE, FeatureKind.BORE) and axis is not None:
        point = np.asarray(axis.point, dtype=float)
        way = np.asarray(axis.direction, dtype=float)
        way = way / np.linalg.norm(way)
        along = (corners - point) @ way
        out = np.linalg.norm(corners - point - np.outer(along, way), axis=1)
        return _Shut(
            feature.id, box, point, way, float(along.min()), float(along.max()), float(out.max())
        )
    return _Shut(feature.id, box, cloud=cKDTree(_on_faces(tess, feature.face_ids, spacing)))


def _bounds(rib: Rib) -> tuple[np.ndarray, np.ndarray]:
    """A box round a rib's metal, root fillet and all."""
    start, end = np.asarray(rib.start, dtype=float), np.asarray(rib.end, dtype=float)
    up = np.asarray(rib.pull, dtype=float)
    up = up / np.linalg.norm(up)
    far = rib.height_mm if rib.end_height_mm is None else rib.end_height_mm
    wide = max(rib.thickness_mm, rib.flange_width_mm) / 2.0 + rib.root_fillet_mm
    corners = np.array([start, end, start + rib.height_mm * up, end + far * up])
    return corners.min(axis=0) - wide, corners.max(axis=0) + wide


def _skin(rib: Rib, frame: HostFrame, spacing: float) -> np.ndarray:
    """Points over a rib's metal no more than ``spacing`` or so apart: its two sides - as far out
    as its root fillet goes where it meets the host, and in it - its top and its two ends."""
    start, end = np.asarray(rib.start, dtype=float), np.asarray(rib.end, dtype=float)
    up = np.asarray(rib.pull, dtype=float)
    up = up / np.linalg.norm(up)
    along = end - start
    length = float(np.linalg.norm(along))
    ahead = along / length if length > 1e-9 else np.asarray(frame.e1, dtype=float)
    across = np.cross(up, ahead)
    across = across / max(float(np.linalg.norm(across)), 1e-12)
    first = rib.height_mm
    last = rib.height_mm if rib.end_height_mm is None else rib.end_height_mm
    side = max(rib.thickness_mm, rib.flange_width_mm) / 2.0
    fillet = rib.root_fillet_mm
    foot = float((start - frame.origin) @ frame.normal)
    rising = float(up @ frame.normal)

    t = np.linspace(0.0, 1.0, max(2, int(math.ceil(length / spacing)) + 1))
    u = np.linspace(0.0, 1.0, max(2, int(math.ceil(max(first, last) / spacing)) + 1))
    rise = np.outer(first + t * (last - first), u)
    middle = start + t[:, None, None] * along + rise[..., None] * up
    # How far out each side is: the rib, and its root fillet where it meets the host.
    half = side + np.clip(fillet - (foot + rise * rising), 0.0, fillet)
    sides = [middle + half[..., None] * across, middle - half[..., None] * across]
    s = np.linspace(-1.0, 1.0, max(2, int(math.ceil(2.0 * (side + fillet) / spacing)) + 1))
    top = middle[:, -1, None, :] + (side * s)[None, :, None] * across
    ends = [
        middle[i, :, None, :] + (half[i, :, None] * s[None, :])[..., None] * across for i in (0, -1)
    ]
    return np.concatenate([p.reshape(-1, 3) for p in (*sides, top, *ends)])


def _on_faces(tess: Tessellation, face_ids, step: float) -> np.ndarray:
    """Points over faces, none further than ``step`` or so from the next."""
    mine = np.isin(tess.face_id, list(face_ids))
    out = []
    for corner, a, b in tess.vertices[tess.triangles[mine]]:
        first, second = a - corner, b - corner
        n = max(1, int(math.ceil(float(np.linalg.norm(first)) / step)))
        m = max(1, int(math.ceil(float(np.linalg.norm(second)) / step)))
        i, j = np.meshgrid(np.arange(n + 1) / n, np.arange(m + 1) / m, indexing="ij")
        inside = (i + j) <= 1.0 + 1e-9
        out.append(corner + np.outer(i[inside], first) + np.outer(j[inside], second))
    return np.concatenate(out) if out else np.zeros((0, 3))


def _round(features: FeatureSet, feature: Feature) -> bool:
    """Whether a keep-out is round along its own axis: a hole, a boss, a bore, a face of one."""
    if feature.kind in (FeatureKind.HOLE, FeatureKind.BOSS, FeatureKind.BORE):
        return True
    faces = [features.faces[f] for f in feature.face_ids]
    return all(f.surface_type in ("cylinder", "cone") for f in faces)


def _disc(features, tess, frame, feature: Feature, clearance: float) -> _Disc:
    """A keep-out seen square to the host: centred on the feature itself, as wide as it reaches.

    Centred on the feature's own middle, never on its axis line - a hole running sideways through a
    wall at the host's edge has an axis whose nearest point to anything can be far away.
    """
    mine = np.isin(tess.face_id, list(feature.face_ids))
    points = frame.to_plane(tess.vertices[np.unique(tess.triangles[mine])])
    centre = frame.to_plane(np.asarray(feature.centroid, dtype=float).reshape(1, 3))[0]
    radius = float(np.max(np.linalg.norm(points - centre, axis=1)))
    return _Disc(feature=feature.id, centre=centre, radius=radius, clearance=clearance)


def _clearance(keep: list, a: np.ndarray, b: np.ndarray, half_width: float) -> float | None:
    """The smallest gap between the rib's side and any keep-out's edge, seen square to the host."""
    if not keep:
        return None
    return round(min(k.gap(a, b, half_width) for k in keep), 2)


def _clearances(
    keep: list, a: np.ndarray, b: np.ndarray, half_width: float, rules: int
) -> list[float | None]:
    """The smallest gap between the rib's side and the keep-outs of each rule, rule by rule - to
    verify each against its own clearance. None for a rule with nothing here to keep clear of."""
    out: list[float | None] = []
    for rule in range(rules):
        mine = [k for k in keep if k.rule == rule]
        out.append(round(min(k.gap(a, b, half_width) for k in mine), 2) if mine else None)
    return out


# --- height ---------------------------------------------------------------------------------------


def _caps(features: FeatureSet, tess: Tessellation, placement: Placement, frame: HostFrame) -> dict:
    """The heights above the host that named features and a given height allow."""
    caps = {}
    level = float(frame.origin @ frame.normal)
    for ref in placement.height.not_above:
        _, top = extent(tess, features.get(ref).face_ids, tuple(frame.normal))
        caps[ref] = round(top - level, 3)
    if placement.height.max_mm is not None:
        caps["given"] = placement.height.max_mm
    return caps


def _height(
    caps: dict, tops: list[float | None], placement: Placement
) -> tuple[list[float] | None, str]:
    """How tall a rib stands at each end: its height in thicknesses, but no taller than what that
    end meets, than any feature named as a cap, or than a height given - times the fraction asked
    for. An end that meets nothing takes the other's height; a level top is held to the lower end
    all the way along."""
    tall = placement.height.thicknesses
    if tall:
        caps = {**caps, f"{tall:g} thicknesses": tall * placement.section.thickness_mm}
    heights: list[float | None] = []
    whys: list[str] = []
    for side, top in zip(("first support", "second support"), tops, strict=True):
        limits = dict(caps)
        if top is not None:
            limits[side] = top
        why = min(limits, key=limits.get) if limits else ""
        heights.append(float(limits[why]) if limits else None)
        whys.append(why)
    if heights[0] is None and heights[1] is None:
        return None, "nothing limits the height: name a height, or a feature ribs stay below"
    for i in (0, 1):
        if heights[i] is None:
            heights[i], whys[i] = heights[1 - i], whys[1 - i]
    if placement.height.top == "level":
        low = 0 if heights[0] <= heights[1] else 1
        heights, whys = [heights[low]] * 2, [whys[low]] * 2
    fraction = placement.height.fraction
    why = whys[0] if whys[0] == whys[1] else f"{whys[0]}, {whys[1]}"
    return [float(h) * fraction for h in heights], why


def _count(placed: Placed | _Attempt, reason: str) -> None:
    placed.dropped[reason] = placed.dropped.get(reason, 0) + 1


@dataclass
class _Attempt:
    """What one path became at one height: each piece as a line, why each that is no rib is not,
    and the ribs, pads and spokes it made."""

    lines: list[dict] = field(default_factory=list)
    dropped: dict[str, int] = field(default_factory=dict)
    ended_on: dict[str, int] = field(default_factory=dict)
    closed: dict[str, int] = field(default_factory=dict)
    ribs: list[Rib] = field(default_factory=list)
    pads: list[Rib] = field(default_factory=list)
    spans: list[dict] = field(default_factory=list)
    spokes: list[_RibKeep] = field(default_factory=list)
    no_room: list[str] = field(default_factory=list)
    left_out: list[dict] = field(default_factory=list)


def _merge(placed: Placed, attempt: _Attempt) -> None:
    """A path's attempt, as part of what the block placed: its lines after the rest - each rib's
    line still followed by its pads' - and its counts added in."""
    offset = len(placed.tried)
    placed.tried.extend(attempt.lines)
    placed.left_out.extend(attempt.left_out)
    for mine, theirs in (
        (placed.dropped, attempt.dropped),
        (placed.ended_on, attempt.ended_on),
        (placed.closed, attempt.closed),
    ):
        for key, n in theirs.items():
            mine[key] = mine.get(key, 0) + n
    placed.ribs.extend(attempt.ribs)
    placed.pads.extend(attempt.pads)
    placed.spans.extend({**span, "line": span["line"] + offset} for span in attempt.spans)
