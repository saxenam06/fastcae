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

**With nothing under them, ribs are webs between what they join.** They stand along the direction
the most of what they join runs along - the pull first among equals - from the level where the most
of it is present. The paths are drawn on the plane square to it there, across the open space
between them: where the part is not, in the pieces of open space that reach two or more of them.
Each web runs from one of them to another, never from one to itself, and is carried into both as
any rib is.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..features import Feature, FeatureKind, FeatureSet, extent
from ..geometry.atlas import Atlas
from ..geometry.brep import Tessellation
from ..spec import Placement
from .field import Field
from .ribs import Rib

# How far past the end of a stretch of path the walk looks for what the rib would meet, as a
# multiple of the root fillet: a wall stands where the fillet at its foot ends.
LOOK_PAST = 3.0

# A stretch shorter than this many rib thicknesses is a stub, not a rib.
SHORTEST = 2.0

# How deep a rib's end may go into what it meets, as a multiple of how deep it is buried at least:
# far enough to stay inside a wall with draft to the wall's top.
DEEPEST = 10.0


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
            if why == "ended_elsewhere" and self.ended_on:
                named = sorted(self.ended_on, key=lambda name: (-self.ended_on[name], name))
                more = f" and {len(named) - 3} more" if len(named) > 3 else ""
                said += f" ({', '.join(named[:3])}{more})"
            became.append(said)
        words += ": " + ", ".join(became)
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
    "crowded": "too close to another of its spokes",
}


def _many(n: int, thing: str) -> str:
    return f"no {thing}s" if n == 0 else f"{n} {thing}" + ("" if n == 1 else "s")


def place_all(
    base: Field,
    features: FeatureSet,
    atlas: Atlas,
    tess: Tessellation,
    placements: list[Placement],
) -> dict[str, Placed]:
    """Ribs for every placement, each placed after those whose ribs it keeps clear of - their
    ribs its keep-outs. Returned in the order the placements were given."""
    ids = {p.id for p in placements}
    pending = list(placements)
    done: dict[str, Placed] = {}
    while pending:
        ready = [p for p in pending if all(o in done or o not in ids for o in p.clear_of)]
        chosen = ready[0] if ready else pending[0]
        pending.remove(chosen)
        avoid = [rib for other in chosen.clear_of if other in done for rib in done[other].ribs]
        done[chosen.id] = place(base, features, atlas, tess, chosen, avoid)
    return {p.id: done[p.id] for p in placements}


def place(
    base: Field,
    features: FeatureSet,
    atlas: Atlas,
    tess: Tessellation,
    placement: Placement,
    avoid: list[Rib] | tuple = (),
) -> Placed:
    """Ribs for ``placement`` on the part ``base`` samples, clear of the ribs in ``avoid``. See the
    module note."""
    section = placement.section
    thickness = section.thickness_mm
    tee = section.shape == "T" and section.flange_width_mm > thickness
    # Half the rib at its widest - the flange, for a T: what keeps clear of anything.
    half = (section.flange_width_mm if tee else thickness) / 2.0
    spacing = base.grid.spacing_mm
    step = max(min(spacing / 2.0, 1.0), features.diagonal_mm * 2e-4)
    probe_height = max(2.0 * spacing, 0.5 * section.root_fillet_mm)
    reach = LOOK_PAST * section.root_fillet_mm + spacing

    hanging = not placement.host
    between = None
    if hanging:
        hang, problem = hang_frame(features, tess, placement.supports, placement.pull)
        if hang is None:
            return Placed(ribs=[], problems=[problem])
        frame, band = hang.frame, hang.band
        probe_height = min(probe_height, band / 2.0)
        footprint, between = _gap(
            base, features, tess, list(hang.joins), frame, band, step, probe_height, reach
        )
        host_faces: set[int] = set()
    else:
        host, problem = host_of(features, placement.host)
        if host is None:
            return Placed(ribs=[], problems=[problem])
        frame = _frame(host)
        footprint = _Footprint.of(tess, host.face_ids, frame, step)
        host_faces = set(host.face_ids)
    keep: list = _keep_outs(features, atlas, tess, placement, frame, host_faces, step)
    rows = [{**k.row(), "rule": k.rule} for k in keep]
    # Other blocks' ribs are kept clear of in three dimensions, rib by rib, once each rib's height
    # is known: one standing over or under another is no obstacle to it.
    others = [
        kept
        for kept in (_RibKeep.of(rib, frame, placement.clear_of_mm) for rib in avoid)
        if kept is not None
    ]
    # How far a rib's end is buried in what it meets: set by the rib, not by the grid, so a
    # preview and a full design end in the same place.
    bury = max(section.root_fillet_mm, 2.0 * spacing)
    finder = _Faces(tess)
    support_of = _supports_by_face(features, atlas, placement.supports)

    placed = Placed(ribs=[], keep_outs=rows)
    caps = _caps(features, tess, placement, frame)
    placed.caps = caps
    # Why stretches had no room for a rib. A problem only if no rib had room at all; otherwise
    # they are counted among what was not placed, like any other stretch dropped.
    no_room: list[str] = []
    spokes: list[_RibKeep] = []
    # Lines are drawn a little off the host, so they show over it rather than in it.
    lift = max(spacing / 2.0, 0.5)

    # Spokes close in on each other toward what they turn about, where their roots may meet; past
    # that they must not run into each other.
    root_zone = section.root_fillet_mm + thickness

    def tried(p: np.ndarray, q: np.ndarray, outcome: str) -> None:
        a, b = frame.to_world(np.array([p, q]), lift)
        placed.tried.append(
            {
                "a": [round(float(v), 2) for v in a],
                "b": [round(float(v), 2) for v in b],
                "outcome": outcome,
            }
        )

    for path_id, (start, direction, length) in enumerate(
        _paths(placement, frame, footprint, features, between)
    ):
        placed.paths += 1
        s = np.arange(0.0, length + step, step)
        uv = start + np.outer(s, direction)
        over = footprint.covers(uv)
        if not over.any():
            _count(placed, "missed")
            tried(uv[0], uv[-1], "missed")
            continue
        blocked = np.zeros(s.size, dtype=bool)
        for k in keep:
            blocked |= k.blocks(uv, half)
        usable = over & ~blocked
        if not usable.any():
            _count(placed, "keep_out")
            where = np.flatnonzero(over)
            tried(uv[where[0]], uv[where[-1]], "keep_out")
            continue
        for first, last in _runs(usable):
            if (s[last] - s[first]) < SHORTEST * thickness:
                _count(placed, "too_short")
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
                )
                for index, sense in ((first, -1.0), (last, 1.0))
            ]
            ends = [met.kind for met in mets]
            if hanging and ends == ["support", "support"] and mets[0].ref == mets[1].ref:
                _count(placed, "one_thing")
                tried(uv[first], uv[last], "one_thing")
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
                _count(placed, reason)
                tried(uv[first], uv[last], reason)
                for met in mets:
                    if reason != "ended_elsewhere" or met.kind != "elsewhere" or met.face is None:
                        continue
                    for feature in features.containing(met.face) or [None]:
                        name = feature.id if feature else f"face:{met.face}"
                        placed.ended_on[name] = placed.ended_on.get(name, 0) + 1
                continue
            heights, why = _height(caps, [met.top for met in mets], placement)
            room = _headroom(
                finder, frame, uv[first], uv[last], probe_height, section.root_fillet_mm + half
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
                if reason not in no_room:
                    no_room.append(reason)
                _count(placed, "no_height")
                tried(uv[first], uv[last], "no_height")
                continue
            if any(o.clashes(uv[first], uv[last], half, max(heights)) for o in others):
                _count(placed, "keep_out")
                tried(uv[first], uv[last], "keep_out")
                continue
            # A spoke that would run into another past their roots is left out. Straight families
            # cross by design.
            if placement.layout.kind == "radial":
                p, q = _inset(uv[first], uv[last], root_zone)
                if any(s.gap(p, q, half) < 0.0 for s in spokes):
                    _count(placed, "crowded")
                    tried(uv[first], uv[last], "crowded")
                    continue
                spokes.append(_RibKeep(a=p, b=q, half=half, clearance=0.0))
            a = mets[0].end_for(heights[0]) if mets[0].ends is not None else uv[first]
            b = mets[1].end_for(heights[1]) if mets[1].ends is not None else uv[last]
            tried(a, b, "rib")
            # Sunk into the floor, so the two are one; a web with nothing under it starts where it
            # starts.
            sink = 0.0 if hanging else spacing
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
            )
            placed.ribs.append(rib)
            placed.spans.append(
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
                }
            )
    if not placed.ribs:
        placed.problems.extend(no_room)
    return placed


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
class Hang:
    """Where webs with nothing under them stand: the plane their paths are drawn on, how far along
    its normal they may reach past it, and which of the things named they join there."""

    frame: HostFrame
    band: float
    joins: tuple[str, ...]


def hang_frame(
    features: FeatureSet, tess: Tessellation, supports: list[str], pull=None
) -> tuple[Hang | None, str]:
    """For webs with nothing under them: where they stand, or None and why.

    They stand along the direction the most of the things named run along - the axis of a round
    one, the line two flat ones meet along, else one of the part's own axes - the pull first among
    equals, then the axis of a round thing: a thing runs along a direction when most of its faces
    do. They join those things, from
    the level where the most of them are present, as far up as all of those go - so a web standing
    there meets every one. Things that run along some other way, or are elsewhere, take no part."""
    found = [features.get(ref) for ref in supports]
    missing = [ref for ref, f in zip(supports, found, strict=True) if f is None]
    if missing:
        return None, f"the part has no {', '.join(missing)}"
    if len(found) < 2:
        return None, "a web with nothing under it joins two things or more: name what it joins"
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
    n = candidates[best]
    # Up is the pull's way, or - with none - the way the direction's largest part points.
    sign = float(n @ np.asarray(pull, dtype=float)) if pull is not None else n[np.abs(n).argmax()]
    if sign < 0.0:
        n = -n
    spans = {ref: extent(tess, features.get(ref).face_ids, tuple(n)) for ref in along[best]}

    def present(level: float) -> list[str]:
        return [r for r, (lo, hi) in spans.items() if lo <= level + 1e-6 and hi >= level + 1.0]

    level = max(sorted({lo for lo, _ in spans.values()}), key=lambda z: len(present(z)))
    joins = present(level)
    if len(joins) < 2:
        said = ", ".join(f"{ref} {lo:.0f} to {hi:.0f}" for ref, (lo, hi) in spans.items())
        return None, (
            f"{', '.join(supports)} do not overlap along {_way(n)} ({said} mm), so no web can "
            "join them"
        )
    top = min(spans[ref][1] for ref in joins)
    centre = np.mean([np.asarray(features.get(r).centroid, dtype=float) for r in joins], axis=0)
    frame = _frame_at(centre + (level - float(centre @ n)) * n, n)
    return Hang(frame=frame, band=top - level, joins=tuple(joins)), ""


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
    if layout.kind == "radial":
        centre_feature = features.get(layout.centre)
        assert centre_feature is not None
        centre = frame.to_plane(np.asarray(_axis_point(features, centre_feature)).reshape(1, 3))[0]
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
        if first.count is not None:
            angle = math.radians(first.angle_deg)
            m = np.array([-math.sin(angle), math.cos(angle)])
            across = cells @ m
            lattice = float(across.max() - across.min()) / first.count
        else:
            lattice = float(first.spacing_mm)
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
        elif family.count is not None:
            gap = (high - low) / family.count
            offsets = [low + (k + family.offset) * gap for k in range(family.count)]
        else:
            gap = float(family.spacing_mm)
            offsets = list(np.arange(low + family.offset * gap, high, gap))
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


def _axis_point(features: FeatureSet, feature: Feature) -> tuple[float, float, float]:
    if feature.axis_id and feature.axis_id in features.axes:
        return features.axes[feature.axis_id].point
    return feature.centroid


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
        _, _, triangle = self.mesh.nearest.on_surface(np.asarray(point, dtype=float).reshape(1, 3))
        return int(self.tess.face_id[int(triangle[0])])

    def exit_along(self, inside: np.ndarray, direction: np.ndarray) -> float | None:
        """How far from a point inside the metal, along ``direction``, the metal ends."""
        distance = self.exits_along(np.asarray(inside, dtype=float).reshape(1, 3), direction)[0]
        return None if np.isnan(distance) else float(distance)

    def exits_along(self, inside: np.ndarray, direction: np.ndarray) -> np.ndarray:
        """The same for many points at once, in one cast: NaN where nothing is met."""
        origins = np.asarray(inside, dtype=float).reshape(-1, 3)
        out = np.full(len(origins), np.nan)
        if not len(origins):
            return out
        directions = np.tile(np.asarray(direction, dtype=float), (len(origins), 1))
        hits, rays, _ = self.mesh.ray.intersects_location(origins, directions, multiple_hits=False)
        if len(hits):
            out[rays] = np.linalg.norm(hits - origins[rays], axis=1)
        return out


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
) -> _Met:
    """What a stretch of path meets past one end, and how tall a rib can stand where it ends.

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
    hit = probes[int(np.argmax(metal))]
    face = finder.nearest(frame.to_world(hit, probe_height)[0])
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
    width = int(round(bury / step))
    if run <= width:
        # Thinner than the burial: as deep as it goes, as tall as all of it allows.
        return _Met(kind, face, into[run - 1 : run], np.array([probe_height + rises.min()]), ref)
    # An end at a depth keeps the last ``bury`` of the rib at the depths behind it inside, so it
    # stands as tall as the lowest of those columns of metal.
    held = np.lib.stride_tricks.sliding_window_view(rises, width + 1).min(axis=1)
    return _Met(kind, face, into[width:run], probe_height + held, ref)


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
    """Another block's rib, kept clear of: its line seen square to the host, as wide as it is, and
    how far along the host's normal it reaches, from and to."""

    a: np.ndarray
    b: np.ndarray
    half: float
    clearance: float
    low: float = -math.inf
    high: float = math.inf

    @staticmethod
    def of(rib: Rib, frame: HostFrame, clearance: float) -> _RibKeep | None:
        """None for a rib wholly on the far side of the host, where nothing standing here goes."""
        base = np.asarray([rib.start, rib.end], dtype=float)
        up = np.asarray(rib.pull, dtype=float)
        tops = base + np.outer(rib.heights, up)
        level = float(frame.origin @ frame.normal)
        along = np.concatenate([base @ frame.normal, tops @ frame.normal]) - level
        if float(along.max()) < -1.0:
            return None
        a, b = frame.to_plane(base)
        return _RibKeep(
            a=a,
            b=b,
            half=rib.width_mm / 2.0,
            clearance=clearance,
            low=float(along.min()),
            high=float(along.max()),
        )

    def clashes(self, a: np.ndarray, b: np.ndarray, half_width: float, top: float) -> bool:
        """Whether a rib along ``a``-``b`` standing ``top`` tall comes nearer this one than the
        clearance: beside it, and at a height it reaches too."""
        if self.low > top + self.clearance or self.high < -self.clearance:
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


def _keep_outs(
    features: FeatureSet,
    atlas: Atlas,
    tess: Tessellation,
    placement: Placement,
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
    """How tall a rib stands at each end: no taller than what that end meets, than any feature
    named as a cap, or than a height given - times the fraction asked for. An end that meets
    nothing takes the other's height; a level top is held to the lower end all the way along."""
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


def _count(placed: Placed, reason: str) -> None:
    placed.dropped[reason] = placed.dropped.get(reason, 0) + 1
