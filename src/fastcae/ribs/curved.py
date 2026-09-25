"""Curved plates: the plate library's own rules, on a rib's own sheet.

A library plate never guessed where the metal was. Its outline was the part's section in the plate's
plane - the band, less the metal and what the volume keeps clear, the piece in the pocket, opened to
the narrowest, sunk into the walls with the skin rule - so it traced a bore's flange step for step,
and neither stood proud of it nor came out beyond it. What it could not do was bend, or taper
except as the metal made it.

A rib standing along the mould's pull on a curve lies on a **vertical sheet**, and a vertical sheet
unrolls flat without stretching: distance along the curve and height are true lengths on it, as
``u`` and ``v`` are in a plate's plane. So the part is sectioned on the rib's own sheet - station by
station, square to the run, reading the metal on the rib's middle and on both its faces - and the
plate rules run on that section unchanged. ``h(s)`` then lowers the top inside the outline they
make, and never raises it. For a straight rib the sheet is a plane and this is the plate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import shapely
from shapely.geometry import LineString

from ..volumes import slices
from . import library

EXACT_END_MM = 3.0
"""How far in from each end a rib's section is read off the exact plane there rather than
station by station: the rib is straight so near its ends."""
STEP_MM = 2.0
"""How far apart along the run the part is sectioned in its middle. The section between two
stations is joined straight, so this is how closely the outline follows the floor."""
FINE_MM = 0.5
"""How far apart it is sectioned near the two ends, where the walls are. A wall crossing the sheet
at a slant is only placed to within a station, and the plate rules push the outline
:data:`.library.OVERLAP_MM` into the metal: at 2 mm the rib's edge ran all but flush with the wall,
and the fuse left a face under 5 mm2 there - eight of them on one rib."""
FINE_REACH_MM = 40.0
"""How far in from each end the fine stations run."""
BURY_OBLIQUE_MM = library.BURY_MM + 0.5 * library.THICKEST_MM / math.tan(math.radians(30.0))
"""How deep a member is sunk: an end meeting a wall at 30° reaches it across its whole thickness."""
MARGIN_MM = BURY_OBLIQUE_MM + library.SKIN_MM + 15.0
"""How far past each end the sheet is sectioned: enough for the ends to be sunk into the wall, and
for the skin rule to see the air beyond it."""


@dataclass
class Sheet:
    """A rib's sheet, unrolled: along the run ``s`` from its first end, up ``z`` from the volume's
    own zero as its band is."""

    s: np.ndarray
    """The stations, mm along the run; 0 and ``length`` are the rib's two ends."""
    base: np.ndarray = field(repr=False)
    """Each station's point on the run, at the volume's zero height, (n, 3)."""
    across: np.ndarray = field(repr=False)
    """Each station's horizontal square to the run, (n, 3)."""
    axis: np.ndarray = field(repr=False)
    length: float = 0.0

    def to3d(self, sz: np.ndarray, offset: float = 0.0) -> np.ndarray:
        """Points of the sheet - ``offset`` to one side of the middle - in the part's frame."""
        sz = np.atleast_2d(np.asarray(sz, float))
        at = np.column_stack(
            [np.interp(sz[:, 0], self.s, self.base[:, k]) for k in range(3)]
        ) + np.outer(sz[:, 1], self.axis)
        if offset:
            side = np.column_stack(
                [np.interp(sz[:, 0], self.s, self.across[:, k]) for k in range(3)]
            )
            at = at + offset * side / np.linalg.norm(side, axis=1, keepdims=True)
        return at


def sheet(run: np.ndarray, axis: np.ndarray, zero: np.ndarray) -> Sheet:
    """The sheet of a run ``run`` (n, 3) - a curve at any height - carried :data:`MARGIN_MM` on
    past both ends along the way it arrives, and resampled every :data:`STEP_MM`."""
    axis = np.asarray(axis, float) / np.linalg.norm(axis)
    flat = run - np.outer((run - zero) @ axis, axis)
    ds = np.linalg.norm(np.diff(flat, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(ds)])
    length = float(s[-1])
    head = flat[0] - flat[1]
    head /= np.linalg.norm(head)
    tail = flat[-1] - flat[-2]
    tail /= np.linalg.norm(tail)
    ends = min(FINE_REACH_MM, 0.5 * length)
    want = np.unique(
        np.round(
            np.concatenate(
                [
                    np.arange(-MARGIN_MM, ends, FINE_MM),
                    np.arange(ends, length - ends, STEP_MM),
                    np.arange(length - ends, length + MARGIN_MM + FINE_MM, FINE_MM),
                ]
            ),
            6,
        )
    )
    base = np.empty((len(want), 3))
    inside = (want >= 0.0) & (want <= length)
    for k in range(3):
        base[inside, k] = np.interp(want[inside], s, flat[:, k])
    before, after = want < 0.0, want > length
    base[before] = flat[0] + np.outer(-want[before], head)
    base[after] = flat[-1] + np.outer(want[after] - length, tail)
    runs = np.gradient(base, axis=0)
    runs /= np.linalg.norm(runs, axis=1, keepdims=True)
    across = np.cross(runs, axis)
    across /= np.linalg.norm(across, axis=1, keepdims=True)
    return Sheet(want, base, across, axis, length)


def _intervals(shape: Any, u: float, lo: float, hi: float) -> list[tuple[float, float]]:
    """Where the upright line ``u`` crosses ``shape`` in a station's plane, as (low, high)."""
    if shape.is_empty:
        return []
    cut = LineString([(u, lo), (u, hi)]).intersection(shape)
    out = []
    for g in getattr(cut, "geoms", [cut]):
        if g.geom_type == "LineString" and g.length > 0.05:
            z = [c[1] for c in g.coords]
            out.append((min(z), max(z)))
    return sorted(out)


def _strips(s: np.ndarray, columns: list[list[tuple[float, float]]]) -> Any:
    """The section on the sheet from what each station reads: consecutive stations' stretches that
    overlap are joined by straight quads, and a stretch with no partner reaches half way to each
    neighbouring station."""
    parts = []
    gaps = np.diff(s)
    for k in range(len(s)):
        before = 0.5 * (gaps[k - 1] if k > 0 else gaps[0])
        after = 0.5 * (gaps[k] if k < len(gaps) else gaps[-1])
        for lo, hi in columns[k]:
            parts.append(shapely.box(s[k] - before, lo, s[k] + after, hi))
        if k + 1 == len(s):
            continue
        for lo, hi in columns[k]:
            for lo2, hi2 in columns[k + 1]:
                if min(hi, hi2) > max(lo, lo2) - 1.0:
                    parts.append(
                        shapely.Polygon([(s[k], lo), (s[k + 1], lo2), (s[k + 1], hi2), (s[k], hi)])
                    )
    parts = [p.buffer(0) for p in parts if p.area > 0.0]
    return shapely.union_all(parts) if parts else shapely.Polygon()


@dataclass
class Section:
    """The part and what the volume keeps clear, on a rib's sheet: on its middle and on both of the
    thickest rib's faces, as a plate reads them in its plane and the two planes beside it."""

    metal: Any
    metals: list[Any]
    blocked: list[Any]


def section(extraction: Any, found: Any, at: Sheet, band: tuple[float, float]) -> Section:
    """The part sectioned on the sheet, station by station, square to the run."""
    tess = extraction.tess
    assert tess is not None
    active = [k for k in found.kept_clear if k.key not in found.recipe.off]
    offsets = (0.0, -0.5 * library.THICKEST_MM, 0.5 * library.THICKEST_MM)
    lo, hi = band[0] - 50.0, band[1] + 50.0
    metal_cols: list[list[list[tuple[float, float]]]] = [[] for _ in offsets]
    kept_cols: list[list[list[tuple[float, float]]]] = [[] for _ in offsets]
    for k in range(len(at.s)):
        runs = np.cross(at.axis, at.across[k])
        station = slices.Plane(at.base[k], runs, at.across[k], at.axis)
        metal = library._metal(extraction, station)
        blocked = [slices.section(q.vertices, q.triangles, None, station).inside for q in active]
        blocked = shapely.union_all([b for b in blocked if not b.is_empty]) if blocked else None
        for w, u in enumerate(offsets):
            metal_cols[w].append(_intervals(metal, u, lo, hi))
            kept_cols[w].append(_intervals(blocked, u, lo, hi) if blocked is not None else [])
    metals = [_strips(at.s, cols) for cols in metal_cols]
    kept = [_strips(at.s, cols) for cols in kept_cols]
    # **the ends read exactly, as a plate reads its plane.** A rib leaves its walls square and is
    # carried on straight past them, so near each end its sheet is a plane - and there the part is
    # sectioned once, exactly, instead of station by station. Sampled every half millimetre and
    # joined straight, a wall's face was placed a fraction of a millimetre off, the plate rules sank
    # the end to that, and every face under 5 mm2 left on the curved ribs sat exactly at a wall's
    # face; the flat plates, read exactly, had none.
    middle = shapely.box(EXACT_END_MM, lo - 10.0, at.length - EXACT_END_MM, hi + 10.0)
    ends = []
    for origin_s, outward_s in ((0.0, -1.0), (at.length, 1.0)):
        origin = at.to3d(np.array([[origin_s, 0.0]]))[0]
        ahead = at.to3d(np.array([[origin_s + outward_s * 5.0, 0.0]]))[0] - origin
        ahead /= np.linalg.norm(ahead)
        across = np.cross(ahead, at.axis)
        # the sheet's own across at this end, so the three planes are the three sheets there
        k = int(np.argmin(np.abs(at.s - origin_s)))
        if float(across @ at.across[k]) < 0.0:
            across = -across
        plane = slices.Plane(origin, across, ahead, at.axis)
        window = shapely.box(-EXACT_END_MM, lo - 10.0, MARGIN_MM, hi + 10.0)
        ends.append((plane, outward_s, origin_s, window))

    def on_sheet(shape: Any, outward_s: float, origin_s: float) -> Any:
        from shapely import affinity

        if shape.is_empty:
            return shape
        if outward_s < 0.0:
            shape = affinity.scale(shape, xfact=-1.0, yfact=1.0, origin=(0.0, 0.0))
        return affinity.translate(shape, xoff=origin_s)

    for w, u in enumerate(offsets):
        parts_m = [metals[w].intersection(middle)]
        parts_k = [kept[w].intersection(middle)]
        for plane, outward_s, origin_s, window in ends:
            at_w = plane.shifted(u)
            m = library._metal(extraction, at_w).intersection(window)
            parts_m.append(on_sheet(m, outward_s, origin_s))
            blocked = [slices.section(q.vertices, q.triangles, None, at_w).inside for q in active]
            blocked = [b.intersection(window) for b in blocked if not b.is_empty]
            if blocked:
                parts_k.append(on_sheet(shapely.union_all(blocked), outward_s, origin_s))
        metals[w] = shapely.union_all([g for g in parts_m if not g.is_empty]).buffer(0)
        got_k = [g for g in parts_k if not g.is_empty]
        kept[w] = shapely.union_all(got_k).buffer(0) if got_k else shapely.Polygon()
    return Section(metals[0], metals, kept)


REACH_PAST_MM = 30.0
FLUSH_MM = 3.0
"""How far a rib's top keeps from level with a top of the metal it meets - a bore's at an end, a
lip's it passes over. Level with it, the two faces meet flush and the fuse leaves slivers: seven of
eight faces under 5 mm2 on one design sat exactly there."""
"""How far past each end the rib is offered to the wall before the wall's own profile cuts it."""


@dataclass
class Profile:
    """A rib's heights on its sheet, read off the part's section: along the run ``s``, the floor
    it stands on, the straight line between the ends' floors, and its top."""

    s: np.ndarray
    floor: np.ndarray
    line: np.ndarray
    top: np.ndarray
    tops: list[float]
    """The metal's top at each end, read just inside the wall."""
    air: Any
    cut: Section
    band: tuple[float, float]
    roof: np.ndarray = field(default_factory=lambda: np.zeros(0))
    """The top of the rib's own stretch of air at each station - the volume's roof over it."""
    ground: np.ndarray = field(default_factory=lambda: np.zeros(0))
    """The floor as read, before it was held to the line between the ends' floors."""
    clear: np.ndarray = field(default_factory=lambda: np.zeros(0))
    """How high the rib may reach at each station before space the volume keeps clear - or the
    band's top. Metal above the rib does not limit it: the fuse makes the two one."""


def _profile(
    extraction: Any, found: Any, at: Sheet, tall: np.ndarray, no: Any, flush_middle: bool
) -> Profile | None:
    """The heights a rib on ``at`` stands at - shared by the traced and the swept build, so both
    read the part the same way."""
    r = found.recipe
    band = (float(r.band[0]), float(r.band[1]))
    cut = section(extraction, found, at, band)
    region = shapely.box(-REACH_PAST_MM, band[0], at.length + REACH_PAST_MM, band[1])
    air = region
    for metal, blocked in zip(cut.metals, cut.blocked, strict=True):
        here = region.difference(metal) if not metal.is_empty else region
        if not blocked.is_empty:
            here = here.difference(blocked)
        air = air.intersection(here)
    inside = (at.s >= 0.0) & (at.s <= at.length)
    s_in = at.s[inside]
    tall = np.asarray(tall, float)
    # the floor under the run: the bottom of the rib's own stretch of air - the tallest one at the
    # middle, then, station by station outward, the one overlapping it most. The tallest stretch
    # at every station, as this first read, jumped beside a wall to the pocket under a lip there
    # and put the S3 ceiling's floor at the bottom of its band, 55 mm below the real one.
    columns = [_intervals(air, float(x), band[0] - 1.0, band[1] + 1.0) for x in s_in]
    floor = np.full(len(s_in), np.nan)
    roof = np.full(len(s_in), np.nan)
    mid = len(s_in) // 2
    if columns[mid]:
        own = {mid: max(columns[mid], key=lambda a: a[1] - a[0])}
        for order in (range(mid + 1, len(s_in)), range(mid - 1, -1, -1)):
            last = own[mid]
            for i in order:
                touching = [a for a in columns[i] if min(a[1], last[1]) - max(a[0], last[0]) > 0.0]
                if touching:
                    last = max(touching, key=lambda a: min(a[1], last[1]) - max(a[0], last[0]))
                    own[i] = last
        for i, a in own.items():
            floor[i] = a[0]
            roof[i] = a[1]
    ok = np.isfinite(floor)
    if ok.sum() < 4:
        no("no air along its run")
        return None
    floor = np.interp(s_in, s_in[ok], floor[ok])
    # each end's floor over its first 20 mm, high side: beside a wall the floor can drop into a
    # groove - 55 mm deep by the S3 ceiling's walls - which is not what the rib stands on
    # read from 15 to 50 mm in from each end: at the end itself the column stands inside the
    # boss's flank or the wall's foot, and reads the metal's top as a floor 30 mm up
    near_a = (s_in >= 15.0) & (s_in <= 50.0)
    near_b = (s_in >= at.length - 50.0) & (s_in <= at.length - 15.0)
    if not near_a.any():
        near_a = s_in <= 20.0
    if not near_b.any():
        near_b = s_in >= at.length - 20.0
    floor_a = float(np.percentile(floor[near_a], 50)) if near_a.any() else float(floor[0])
    floor_b = float(np.percentile(floor[near_b], 50)) if near_b.any() else float(floor[-1])
    # and within those 15 mm the floor is the end's, not the column's: the base runs into the
    # metal the end is sunk in
    floor = np.where(s_in < 15.0, np.minimum(floor, floor_a), floor)
    floor = np.where(s_in > at.length - 15.0, np.minimum(floor, floor_b), floor)
    # the metal's top at each end, read just inside the wall there
    tops = []
    for x, near in ((-3.0, floor_a), (at.length + 3.0, floor_b)):
        spans = _intervals(cut.metal, x, band[0] - 50.0, band[1] + 50.0)
        # the highest metal in that column within the band: a bore's flange can be a U in
        # section, and the first metal met above the floor was the lip of its slot, half its height
        above = [b for a, b in spans if b > near + 1.0]
        tops.append(min(max(above), band[1]) if above else band[1])
    line = floor_a + (floor_b - floor_a) * s_in / max(at.length, 1e-9)
    proud = tops[0] + (tops[1] - tops[0]) * s_in / max(at.length, 1e-9) - FLUSH_MM
    top = np.minimum(line + tall, proud)
    if flush_middle:
        # never flush with a top the rib passes over, either: where metal comes into the run
        # and its top is within FLUSH_MM of the rib's, the rib stands that much clear of it
        for i, x in enumerate(s_in):
            for a, b in _intervals(cut.metal, float(x), band[0] - 50.0, band[1] + 50.0):
                if a < top[i] and abs(b - top[i]) < FLUSH_MM and b > floor[i] + 1.0:
                    top[i] = b - FLUSH_MM if b - FLUSH_MM > floor[i] + 8.0 else b + FLUSH_MM
    # never below the line between the ends' floors either: over a groove the rib bridges, and on
    # a bump it sits into the metal, which the fuse makes one with it
    ground = floor.copy()
    floor = np.maximum(floor, line)
    if np.any(top - floor < 8.0):
        worst = int(np.argmin(top - floor))
        no(
            f"no room to stand 8 mm at {s_in[worst]:.0f} of {at.length:.0f} mm: "
            f"floor {floor[worst]:.0f}, "
            f"ends' floors {floor_a:.0f}/{floor_b:.0f}, h {tall[worst]:.0f}, ends' metal tops "
            f"{tops[0]:.0f}/{tops[1]:.0f}"
        )
        return None
    ok_roof = np.isfinite(roof)
    roof = (
        np.interp(s_in, s_in[ok_roof], roof[ok_roof])
        if ok_roof.any()
        else np.full_like(floor, band[1])
    )
    kept = [b for b in cut.blocked if not b.is_empty]
    kept_all = shapely.union_all(kept) if kept else None
    clear = np.full(len(s_in), band[1])
    if kept_all is not None:
        for i, x in enumerate(s_in):
            above = [a for a, _ in _intervals(kept_all, float(x), band[0] - 1.0, band[1] + 1.0)]
            above = [a for a in above if a > ground[i]]
            if above:
                clear[i] = min(min(above), band[1])
    return Profile(s_in, floor, line, top, tops, air, cut, band, roof, ground, clear)


"""How far into the floor a swept rib's bottom is carried, for the housing to cut it off exactly."""


SMOOTH_RAIL_MM = 10.0
"""Over how far a swept rib's base and top are smoothed before its slab is made."""


def _smooth(s: np.ndarray, values: np.ndarray, sigma: float = SMOOTH_RAIL_MM) -> np.ndarray:
    """``values`` along ``s`` smoothed with a Gaussian ``sigma`` mm wide - stations need not be
    evenly spaced."""
    s = np.asarray(s, float)
    w = np.exp(-0.5 * ((s[:, None] - s[None, :]) / sigma) ** 2)
    return (w @ np.asarray(values, float)) / w.sum(axis=1)


def _full_ends(got: Profile, tall: np.ndarray, cap: np.ndarray | None = None) -> np.ndarray:
    """A swept rib's top: **the full height of the metal at both ends**, as a plate's end was - a
    bore's top at one, a wall's at the other, less :data:`FLUSH_MM` so the two tops never lie
    flush - and between them one smooth curve, a quadratic through the two ends whose middle is the
    height ``h`` asks there.

    The middle may rise above the line between the ends where the volume's roof allows, never
    above that roof (proud of the metal around it), and never dips below the lower end. The ends'
    heights are the section's, not free numbers: a rib that stopped short of a bore's top left the
    rest of the bore's face bare above it.
    """
    s = got.s / max(got.s[-1], 1e-9)
    # the height the optimiser gave each end, under the metal's top there less FLUSH_MM: the
    # optimiser caps its ends by the same metal (:func:`.fins.capped`), so the two agree, and a
    # rib drawn taller at its ends than it was valued at is no longer possible
    tall_ = np.asarray(tall, float)
    a = min(got.tops[0] - FLUSH_MM, float(got.line[0] + tall_[0]))
    b = min(got.tops[1] - FLUSH_MM, float(got.line[-1] + tall_[-1]))
    # capped by space kept clear and the band's top only; metal over the rib - a lip, a bore's
    # flange - is merged by the fuse, and capping at it left S2 ribs no room to stand
    roof = got.clear - FLUSH_MM if cap is None else np.asarray(cap, float)
    a, b = min(a, float(roof[0])), min(b, float(roof[-1]))
    want = float(np.interp(0.5, s, got.line + np.asarray(tall, float)))
    want = max(want, min(a, b))
    control = 2.0 * want - 0.5 * (a + b)
    # **one arc under every cap**, not clipped by them: the middle rises as far as it can while
    # the whole curve stays under the roof. Clipped instead, the top followed each cap in turn - a
    # keep-out over the bore, the band, a wall - and came out with shoulders: the notches.
    inner = (s > 0.01) & (s < 0.99)
    if inner.any():
        room = (roof[inner] - (1 - s[inner]) ** 2 * a - s[inner] ** 2 * b) / (
            2 * s[inner] * (1 - s[inner])
        )
        control = min(control, float(room.min()))
    return (1 - s) ** 2 * a + 2 * s * (1 - s) * control + s**2 * b


SINK_MM = 8.0
TAPER_MM = 25.0
"""Over how far from each end a rib's base and top are drawn into its root window."""
EDGE_CLEAR_MM = 3.0
"""How far a root window keeps from a housing edge crossing the wall's face at the end."""
ROOT_MARGIN_MM = 4.0
"""How far inside its root window a rib's end lies. At 1 mm the end's top corner still met the
wall where its surface rounds off, and the fuse left a face of a square millimetre or two there."""
ROOT_LEAST_MM = 4.0
"""The least a root shoe goes into its wall."""
ROOT_TALLEST_LEAST_MM = 10.0
"""The least height of wall a root shoe needs across the rib's whole thickness."""
"""How far a swept rib's base reaches into the floor where the floor is metal."""


def _lowest(s: np.ndarray, values: np.ndarray, reach: float) -> np.ndarray:
    """The least of ``values`` within ``reach`` mm along ``s`` either way of each station."""
    near = np.abs(s[:, None] - s[None, :]) <= reach
    return np.where(near, values[None, :], np.inf).min(axis=1)


def _through(metal: Any, z: float, start: float, way: float) -> float:
    """How far the metal runs from ``start`` along the sheet at height ``z``, going ``way`` (-1 or
    +1): the wall's thickness there, 0 where ``start`` is not in metal."""
    from shapely.geometry import LineString

    reach = MARGIN_MM
    line = LineString([(start, z), (start + way * reach, z)])
    cut = line.intersection(metal)
    best = 0.0
    for g in getattr(cut, "geoms", [cut]):
        if g.geom_type != "LineString" or g.is_empty:
            continue
        xs = [c[0] for c in g.coords]
        if min(xs) <= start + 1.0 and max(xs) >= start - 1.0:
            best = max(best, max(abs(x - start) for x in xs))
    return best


@dataclass
class Offered:
    """A swept rib's outline on its sheet, before any solid is made of it: what the oracle judges
    and what the solid is drawn from, so the two never differ."""

    ring: Any
    """The outline, a polygon on the sheet: along the run, and up."""
    s: np.ndarray
    base: np.ndarray
    top: np.ndarray
    shoes: tuple[tuple[float, float, float], tuple[float, float, float]]
    """Each end's root window and depth: the heights between which the wall holds the rib across
    its whole thickness, and how far into the wall the end is sunk."""
    profile: Profile
    backed: np.ndarray = field(default_factory=lambda: np.zeros(0, bool))
    """Whether the floor under each station is metal - read on the section, 2 mm under it."""


def outline_on_sheet(
    extraction: Any,
    found: Any,
    at: Sheet,
    tall: np.ndarray,
    why: list[str] | None = None,
    edges: Any = None,
) -> Offered | None:
    """The smooth parameterised rib's outline on its sheet - the curve, a smooth base, ``h(s)``
    for its top, a root shoe at each end - **drawn to be sunk into the metal around it and fused,
    as a plate was.**

    A plate never touched the metal exactly: it was carried into the walls and floor and the fuse
    made the overlap one. Cut to the housing's own faces instead, a rib's faces lay exactly on the
    wall's and the floor's, and that is where OCC left slivers, folded slabs and gaps at a sloping
    wall's foot. So:

    - its heights come off the part's section on its own sheet (:func:`_profile`), not cubes;
    - its **base** runs :data:`SINK_MM` into the floor wherever the floor is metal - up into a
      recess, down a groove, smoothed - and stops at the floor where the floor is only the edge of
      space kept clear;
    - its **top** is the full height of the metal at each end and one smooth curve between, under
      space kept clear (smoothed first: read station by station it made the edge wavy);
    - each **end** is sunk into its wall as deep as the plates' rule allows -
      :data:`.BURY_OBLIQUE_MM`, less a skin short of the wall's far side at every height,
      so it never comes through - and within the height of the wall's metal;
    - what the volume keeps clear is refused.

    Nothing here touches OCC: the outline is judged by the oracle first (:mod:`.oracle`), and only
    an outline that passes becomes a solid (:func:`swept`).
    """

    def no(reason: str) -> None:
        if why is not None:
            why.append(reason)

    got = _profile(extraction, found, at, tall, no, flush_middle=False)
    if got is None:
        return None
    band = got.band
    metal = got.cut.metal
    x = got.s

    def in_metal(xx: float, z: float) -> bool:
        return any(
            a <= z <= b for a, b in _intervals(metal, float(xx), band[0] - 80.0, band[1] + 80.0)
        )

    backed = np.array([in_metal(xx, f - 2.0) for xx, f in zip(x, got.ground, strict=True)])
    # the base: into the floor where it is metal, at it where not; the lowest within 8 mm either
    # way, so a step is met inside the metal, then smoothed
    base = np.where(backed, got.ground - SINK_MM, got.ground)
    base = _smooth(x, _lowest(x, base, 8.0), 4.0)
    base = np.where(backed, np.minimum(base, got.ground - 1.0), np.maximum(base, got.ground))
    base = _smooth(x, base, 2.0)
    # the top: the keep-out ceiling smoothed from below first, then the full-height curve under it
    got.clear = _smooth(x, _lowest(x, got.clear, 10.0), 5.0)
    top = _full_ends(got, tall)
    top = np.minimum(_smooth(x, top, 4.0), got.clear - FLUSH_MM)
    if np.any(top - got.ground < 8.0):
        no("no room to stand 8 mm under space kept clear somewhere along its run")
        return None
    # nothing into what the volume keeps clear
    blocked = [b for b in got.cut.blocked if not b.is_empty]
    if blocked:
        offered = shapely.Polygon(
            [*zip(x, got.ground, strict=True), *zip(x[::-1], top[::-1], strict=True)]
        ).buffer(0)
        if offered.intersection(shapely.union_all(blocked)).area > 50.0:
            no("runs into space the volume keeps clear")
            return None

    # each end a **root shoe**: the attachment is designed, not found by trimming. At each end,
    # the longest run of heights where the wall is metal across the rib's whole thickness - its
    # middle and both faces - and deep enough; and one depth into it, the shallowest wall there
    # less a skin. A depth read height by height was a sawtooth, and every tooth met the wall in a
    # sliver; under a flange standing clear of the floor there is no wall, and the end simply stops
    # at the wall's face there.
    def shoe(i: int, start: float, way: float) -> list[tuple[float, float]]:
        heights = np.linspace(base[i], top[i], 41)
        walls = np.array(
            [
                min(_through(m, float(z), start + way * 0.5, way) for m in got.cut.metals)
                for z in heights
            ]
        )
        least = library.SKIN_MM + ROOT_LEAST_MM
        ok = walls >= least
        # **clear of the wall's own edges.** Where a housing edge crosses the wall's face at the
        # end - a fillet's rim, a chamfer, the foot of a boss - an end drawn to that height lands
        # its own edge on the housing's, and the fuse leaves a face of a square millimetre there.
        # The edges are the B-rep's, sampled once (:func:`edge_tree`); the section's own corners
        # are no guide, a curved face being all corners once sectioned. No height within
        # EDGE_CLEAR_MM of an edge on any of the three sheets holds a root.
        if edges is not None:
            for offset in (0.0, -0.5 * library.THICKEST_MM, 0.5 * library.THICKEST_MM):
                line = at.to3d(np.column_stack([np.full(len(heights), start), heights]), offset)
                near, _ = edges.query(line)
                ok &= near > EDGE_CLEAR_MM
        # the longest run of supported heights
        best, run_start = (0, -1), None
        for k, good in enumerate([*ok, False]):
            if good and run_start is None:
                run_start = k
            if not good and run_start is not None:
                if k - run_start > best[1] - best[0] + 1:
                    best = (run_start, k - 1)
                run_start = None
        lo_k, hi_k = best
        if hi_k < lo_k or heights[hi_k] - heights[lo_k] < ROOT_TALLEST_LEAST_MM:
            return []
        depth = min(BURY_OBLIQUE_MM, float(walls[lo_k : hi_k + 1].min()) - library.SKIN_MM)
        return [(float(heights[lo_k]), float(heights[hi_k]), depth)]

    first = shoe(0, 0.0, -1.0)
    second = shoe(-1, at.length, 1.0)
    if not first or not second:
        no("no wall at one end holds a root across the rib's whole thickness")
        return None
    # **the whole end sunk.** An end drawn taller than its window stopped on the wall's face above
    # and below it, and a face that stops on another face is where the fuse leaves its slivers -
    # every small face on the ring's ribs sat there. So over the last :data:`TAPER_MM` the base
    # rises and the top falls into the window, and the end is one rectangle sunk into the wall.
    (z0a, z1a, depth_a), (z0b, z1b, depth_b) = first[0], second[0]
    base, top = base.copy(), top.copy()
    for z0, z1, end_s in ((z0a, z1a, 0.0), (z0b, z1b, at.length)):
        w = np.clip(1.0 - np.abs(x - end_s) / TAPER_MM, 0.0, 1.0)
        base = base + w * np.maximum(z0 + ROOT_MARGIN_MM - base, 0.0)
        top = top - w * np.maximum(top - (z1 - ROOT_MARGIN_MM), 0.0)
    if float(top[0] - base[0]) < 8.0 or float(top[-1] - base[-1]) < 8.0:
        no("its root window at an end is too short to stand 8 mm in")
        return None
    # the outline on the rib's own sheet: base along the run, the second end sunk, the top back,
    # the first end sunk - drawn exactly on the sheet, nothing fitted
    ring = [
        *zip(x, base, strict=True),
        (at.length + depth_b, float(base[-1])),
        (at.length + depth_b, float(top[-1])),
        *zip(x[::-1], top[::-1], strict=True),
        (-depth_a, float(top[0])),
        (-depth_a, float(base[0])),
    ]
    outline_2d = shapely.Polygon(ring).buffer(0)
    if outline_2d.geom_type != "Polygon" or outline_2d.is_empty:
        outline_2d = library._largest(outline_2d)
    if outline_2d.is_empty:
        no("its outline does not close")
        return None
    return Offered(outline_2d, x, base, top, (first[0], second[0]), got, backed)


def swept(
    extraction: Any,
    found: Any,
    at: Sheet,
    tall: np.ndarray,
    housing: Any,
    thickness_mm: float,
    why: list[str] | None = None,
    stash: dict[str, Any] | None = None,
    offered: Offered | None = None,
    edges: Any = None,
) -> tuple[Any, np.ndarray] | None:
    """The smooth parameterised rib as one solid: its outline (:func:`outline_on_sheet`, or
    ``offered`` when the oracle has already drawn and judged it) given its section on its own
    sheet. A slab OCC finds folded through itself is refused."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Check

    def no(reason: str) -> None:
        if why is not None:
            why.append(reason)

    got = (
        offered
        if offered is not None
        else outline_on_sheet(extraction, found, at, tall, why, edges=edges)
    )
    if got is None:
        return None
    try:
        slab = solid(at, got.ring, thickness_mm)
    except Exception as exc:  # OCC's own failures arrive as Python exceptions too
        no(f"no solid: {exc}")
        return None
    if stash is not None:
        stash["slab"] = slab
    if not BRepAlgoAPI_Check(slab, True, True).IsValid():
        no("its solid intersects itself")
        return None
    # the rib's side as the design screen draws it - exactly the outline that is built
    ring_2d = np.asarray(got.ring.exterior.coords)[:-1]
    return slab, at.to3d(ring_2d)


def solid(at: Sheet, shape: Any, thickness_mm: float) -> Any:
    """The outline as a solid ``thickness_mm`` thick, centred on the sheet - **the plate's own
    solid, bent**: a flat outline given its thickness has two faces cut to the outline and one
    narrow face along each of its edges, and so has this.

    Each face of the rib is a sheet of its own - the run's curve carried ``thickness_mm / 2`` to
    one side, then straight up the pull - and on it the outline is drawn exactly, in the sheet's
    own two coordinates: along the run, and up. Each edge of the outline then becomes a narrow face
    ruled between its two drawings, one on either side. Nothing is fitted to the outline, so a step
    where it traces a flange stays a step; two rails fitted through it overshot every step, and ten
    ribs of thirteen would not fuse.
    """
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakeVertex,
        BRepBuilderAPI_MakeWire,
    )
    from OCP.BRepFill import BRepFill
    from OCP.BRepLib import BRepLib
    from OCP.Geom import Geom_SurfaceOfLinearExtrusion
    from OCP.Geom2d import Geom2d_Line
    from OCP.GeomAbs import GeomAbs_C2
    from OCP.GeomAPI import GeomAPI_PointsToBSpline
    from OCP.gp import gp_Dir, gp_Dir2d, gp_Pnt, gp_Pnt2d
    from OCP.TColgp import TColgp_Array1OfPnt
    from OCP.TColStd import TColStd_Array1OfReal
    from OCP.TopoDS import TopoDS
    from shapely.geometry.polygon import orient

    from ..designs import sweep

    shape = orient(shape.simplify(0.5, preserve_topology=True), 1.0)
    rings = [np.asarray(shape.exterior.coords)[:-1]] + [
        np.asarray(r.coords)[:-1] for r in shape.interiors
    ]
    rings = [_without_short(r) for r in rings]
    up = gp_Dir(*map(float, at.axis))

    def face_sheet(offset: float) -> Any:
        points = at.base + offset * at.across
        row = TColgp_Array1OfPnt(1, len(points))
        ts = TColStd_Array1OfReal(1, len(points))
        for i, (q, s) in enumerate(zip(points, at.s, strict=True), start=1):
            row.SetValue(i, gp_Pnt(*map(float, q)))
            ts.SetValue(i, float(s))
        fit = GeomAPI_PointsToBSpline(row, ts, 3, 8, GeomAbs_C2, 1e-3)
        if not fit.IsDone():
            raise ValueError("a face's run does not fit a curve")
        return Geom_SurfaceOfLinearExtrusion(fit.Curve(), up)

    def drawn(surface: Any, offset: float) -> tuple[Any, list[list[Any]]]:
        """The outline drawn on one face's sheet: the face, and its edges ring by ring."""
        wires, edges = [], []
        for ring in rings:
            # each corner taken off the face's own surface, so the edges drawn on it end on it
            corners = [
                BRepBuilderAPI_MakeVertex(surface.Value(float(c[0]), float(c[1]))).Vertex()
                for c in ring
            ]
            ring_edges = []
            wire = BRepBuilderAPI_MakeWire()
            for i in range(len(ring)):
                a, b = ring[i], ring[(i + 1) % len(ring)]
                length = float(np.linalg.norm(b - a))
                line = Geom2d_Line(
                    gp_Pnt2d(*map(float, a)), gp_Dir2d(*map(float, (b - a) / length))
                )
                edge = BRepBuilderAPI_MakeEdge(
                    line, surface, corners[i], corners[(i + 1) % len(ring)], 0.0, length
                ).Edge()
                ring_edges.append(edge)
                wire.Add(edge)
            if not wire.IsDone():
                raise ValueError("the outline does not close on a face's sheet")
            wires.append(wire.Wire())
            edges.append(ring_edges)
        make = BRepBuilderAPI_MakeFace(surface, wires[0], True)
        for w in wires[1:]:
            make.Add(w)
        if not make.IsDone():
            raise ValueError("the outline does not make a face on its sheet")
        face = make.Face()
        BRepLib.BuildCurves3d_s(face)
        return face, edges

    half = 0.5 * thickness_mm
    one, one_edges = drawn(face_sheet(half), half)
    two, two_edges = drawn(face_sheet(-half), -half)
    faces = [one, two]
    for ring_one, ring_two in zip(one_edges, two_edges, strict=True):
        for a, b in zip(ring_one, ring_two, strict=True):
            faces.append(BRepFill.Face_s(TopoDS.Edge_s(a), TopoDS.Edge_s(b)))
    return sweep.close(faces)


def _without_short(ring: np.ndarray, least: float = 0.5) -> np.ndarray:
    """A ring with any corner nearer than ``least`` to the one before it dropped: an edge that
    short makes a face under a square millimetre along the rim."""
    keep = [ring[0]]
    for c in ring[1:]:
        if np.linalg.norm(c - keep[-1]) >= least:
            keep.append(c)
    if len(keep) > 3 and np.linalg.norm(keep[-1] - keep[0]) < least:
        keep.pop()
    return np.asarray(keep)
