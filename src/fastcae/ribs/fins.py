"""Fins: a rib as a curve on the metal, a height along it, and one cast section.

A fin here is not a form picked from a list. It is:

* **a curve** across the volume's plan, four control points - its two **ends on the rail** (the line
  where the volume's air meets metal), one number each, and two **interior points**, free. Bow one
  and it is an arc; pull them apart and it is a chevron.
* **a height** ``h(s)`` along the run, three stations, quadratic - so it cannot go negative. Full
  everywhere is a web; falling to zero at one end is a run-out, at both an island.
* **a section**, fixed at :data:`THICKNESS_MM`. Production casts one, and a fixed one is what lets a
  fin fuse into a wall without leaving a wedge.
* **a presence** ``α``, 0 to 1, that fades it out.

Ten numbers a fin (:data:`NUMBERS`); the flange ``w(s)``, the root ``r(s)`` and the holes come
after the go/no-go, and slot into the same chain.

**The base is read, not chosen** (:class:`Floor`): the fin stands from whatever lies under it at
that point to that plus ``h``. There is no number that would lift it off, so it cannot hang in air.

**Drawn on the cubes** exactly as :mod:`.plates` draws a plate - a smooth step about a cube wide,
times the presence - so :mod:`.paths` solves any set of numbers and the objective's gradient on the
cubes flows back to every number. Two differences from a plate, both deliberate:

* the distance to the run is **blended smoothly across the curve's pieces**, never taken from the
  nearest one: a hard nearest-piece switch puts a step in the gradient wherever that nearest piece
  changes;
* the run carries a height, so a cube above the fin's top is empty and the gradient says by how
  much raising the fin would fill it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .library import FREE_MM
from .mma import _step

NUMBERS = ("a", "b", "cu", "cv", "du", "dv", "h0", "h1", "h2", "presence")
"""A fin's numbers: its two ends along the rail, its two interior control points, its three height
stations, and its presence."""

THICKNESS_MM = 20.0
"""The one section the production housing casts. Not a variable."""
ROUND_MM = 1.0
"""The distance to the run is rounded off within this of it, so it has a slope on the run itself."""
PIECES = 24
"""How many pieces the curve is read as. The blend below is smooth across them, so this sets
accuracy, not smoothness."""
BLEND_MM = 6.0
"""How softly the pieces blend: a piece this much further away than the nearest counts about a
third as much. Smaller is sharper and noisier; about a cube is right."""
RAIL_SMOOTH = 5
"""How many rail samples either side are averaged. A rail off a voxelled wall is a staircase, and
an end sliding along a staircase gives a stepped gradient - so the rail is smoothed, not the fin."""
ROOTED_MM = FREE_MM + 1.0
"""How near the metal a stretch of boundary counts as rooted, allowing for the resampling."""
HOLE_CLEAR_MM = 10.0
"""How far a run must keep from a hole in the volume's air - half a rib's section, so a rib's own
face clears it. Holes and keep-outs are already cut out of the air (:mod:`fastcae.volumes.volume`),
so a run over one is charged like any other stray; this is the margin on top. A placeholder until
it is measured off the production casting."""
GRAZE_MM = 18.0
"""How far clear of the metal a rib's **middle** must run.

A rib should be plainly in the air along its length and meet the metal only at its ends. One that
runs alongside a wall at a glancing angle is neither in nor out: the fuse carves shallow scallops
where the two surfaces graze, and every scallop leaves faces of a few square millimetres. Half a
rib's section, the gap inside which the oracle calls a face alongside the metal
(:data:`fastcae.ribs.oracle.FAR_MM`), and a little: **the optimiser's margin must clear the
oracle's**, or a fin can keep every rule it was given and still be refused afterwards. At 14 mm a
face stood 4 mm off the wall, inside the oracle's 6.
"""
ENDS_SHARE = 0.15
"""The share of the run at each end that is exempt: an end *must* reach the metal to be buried."""
CLEAR_MM = 0.1
"""**A rule, not a charge:** the most a fin's middle may come inside :data:`GRAZE_MM` of the metal,
in mm averaged over its run - see :func:`clearance`. A rib meets the metal at its two ends and its
floor and nowhere else; one that touches a bore or wall along its side is not a rib a foundry
makes, and its glancing contact is where the fuse leaves slivers. As a charge it only discouraged
that, and a fin could buy its way past it; here it is one rule per fin in
:func:`.mma._mma_many`. Nearly zero - the soft hinge never reads exactly zero."""
CLEAR_SOFT_MM = 1.0
"""How soft that hinge is, in mm. The rule is about the curve, not the cubes, so it stays sharp from
the first step rather than following the drawing's continuation."""


def _bernstein3(s: np.ndarray) -> np.ndarray:
    """The four cubic weights at each ``s``, (n, 4)."""
    t = 1.0 - s
    return np.stack([t**3, 3.0 * t**2 * s, 3.0 * t * s**2, s**3], axis=-1)


def _bernstein2(s: np.ndarray) -> np.ndarray:
    """The three quadratic weights at each ``s``, (n, 3)."""
    t = 1.0 - s
    return np.stack([t**2, 2.0 * t * s, s**2], axis=-1)


def _dbernstein2(s: np.ndarray) -> np.ndarray:
    """Their slopes by ``s``, (n, 3)."""
    t = 1.0 - s
    return np.stack([-2.0 * t, 2.0 * (t - s), 2.0 * s], axis=-1)


@dataclass
class Rail:
    """Where a fin's ends may sit: a **rooted stretch** of a volume's plan - a run of its air's
    boundary that is backed by metal all the way along.

    An end is **one** number, how far along in mm, between 0 and :attr:`length_mm`. Inside a stretch
    there are no jumps, so an end's gradient is clean; and since the whole stretch is metal, there
    is no number that puts an end in air. About a fifth of a volume's boundary is free, and that is
    why the boundary is cut into stretches rather than taken whole.
    """

    points: np.ndarray = field(repr=False)
    """The rail, resampled evenly, (n, 2)."""
    step_mm: float = 1.0
    closed: bool = False
    """Whether the stretch is the whole boundary, so the number wraps rather than stopping."""

    @property
    def length_mm(self) -> float:
        n = len(self.points) if self.closed else len(self.points) - 1
        return float(n * self.step_mm)

    @classmethod
    def of(
        cls,
        line: np.ndarray,
        step_mm: float = 2.0,
        smooth: int = RAIL_SMOOTH,
        closed: bool | None = None,
    ) -> Rail:
        """A rail from a line of the plan, resampled every ``step_mm`` and smoothed."""
        line = np.asarray(line, float)
        shut = bool(len(line) > 2 and np.allclose(line[0], line[-1])) if closed is None else closed
        if shut and len(line) > 1 and np.allclose(line[0], line[-1]):
            line = line[:-1]
        whole = np.vstack([line, line[:1]]) if shut else line
        run = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(whole, axis=0), axis=1))])
        n = max(int(round(float(run[-1]) / step_mm)), 8)
        want = np.linspace(0.0, float(run[-1]), n, endpoint=shut is False)
        out = np.stack([np.interp(want, run, whole[:, i]) for i in (0, 1)], axis=1)
        if smooth > 0:
            k = np.ones(2 * smooth + 1) / (2 * smooth + 1)
            wide = (
                np.vstack([out[-smooth:], out, out[:smooth]])
                if shut
                else np.vstack([np.repeat(out[:1], smooth, 0), out, np.repeat(out[-1:], smooth, 0)])
            )
            out = np.stack([np.convolve(wide[:, i], k, "valid") for i in (0, 1)], axis=1)
        step = float(run[-1]) / (n if shut else n - 1)
        return cls(out, step, shut)

    def at(self, u: float) -> tuple[np.ndarray, np.ndarray]:
        """Where ``u`` mm along the rail is, and which way the rail runs there - the point's
        derivative by ``u``. Read between samples, so a sliding end moves smoothly."""
        n = len(self.points)
        if self.closed:
            x = (float(u) / self.step_mm) % n
            i = int(np.floor(x))
            a, b = self.points[i % n], self.points[(i + 1) % n]
        else:
            x = float(np.clip(u / self.step_mm, 0.0, n - 1 - 1e-9))
            i = int(np.floor(x))
            a, b = self.points[i], self.points[i + 1]
        return a + (x - i) * (b - a), (b - a) / self.step_mm


def rails(
    rings: list[np.ndarray], metal: Any, step_mm: float = 4.0, least_mm: float = 60.0
) -> list[Rail]:
    """A volume's rooted stretches: its air's boundary cut wherever it leaves the metal, each run
    of at least ``least_mm`` kept as a rail of its own. A boundary entirely backed stays closed."""
    from shapely.geometry import Point

    out: list[Rail] = []
    for ring in rings:
        whole = Rail.of(np.asarray(ring, float), step_mm, smooth=0)
        pts = whole.points
        on = (
            np.ones(len(pts), bool)
            if metal is None or metal.is_empty
            else np.array([metal.distance(Point(*p)) <= ROOTED_MM for p in pts])
        )
        if on.all():
            out.append(Rail.of(pts, step_mm, closed=True))
            continue
        if not on.any():
            continue
        order = np.roll(np.arange(len(pts)), -int(np.flatnonzero(~on)[0]))
        run: list[int] = []
        for i in order:
            if on[i]:
                run.append(int(i))
                continue
            if len(run) * step_mm >= least_mm:
                out.append(Rail.of(pts[run], step_mm, closed=False))
            run = []
        if len(run) * step_mm >= least_mm:
            out.append(Rail.of(pts[run], step_mm, closed=False))
    return out


@dataclass
class Floor:
    """What lies under each point of a volume's plan: the top of the metal below, or the bottom of
    the band where there is none. Read from the cubes themselves, then smoothed - a floor that
    starts within one cube is a step in the field, and a step is a cliff in the gradient."""

    lo: np.ndarray = field(default_factory=lambda: np.zeros(2), repr=False)
    """The plan's corner, (2,)."""
    spacing_mm: float = 5.0
    height: np.ndarray = field(default_factory=lambda: np.zeros((1, 1)), repr=False)
    """The floor over the plan, (nu, nv)."""

    @classmethod
    def of(
        cls,
        at: np.ndarray,
        spacing_mm: float = 5.0,
        smooth: int = 3,
        top: bool = False,
        over: np.ndarray | None = None,
    ) -> Floor:
        """The floor under cubes at ``at`` - (n, 3), the plan's two axes then the draw.

        With ``top`` it reads the other end of each column instead - the **crest**, how high the
        metal there reaches - which is what caps a rib's height. ``over`` gives the plan to lay the
        field on when the cubes read are not the ones it will be asked about, as the part's metal is
        not the volume's air.
        """
        at = np.asarray(at, float)
        plan = at[:, :2] if over is None else np.asarray(over, float)[:, :2]
        lo = np.minimum(at[:, :2].min(axis=0), plan.min(axis=0)) - spacing_mm
        wide = np.maximum(at[:, :2].max(axis=0), plan.max(axis=0))
        idx = np.floor((at[:, :2] - lo) / spacing_mm).astype(int)
        shape = tuple(np.floor((wide - lo) / spacing_mm).astype(int) + 3)
        floor = np.full(shape, -np.inf if top else np.inf)
        (np.maximum if top else np.minimum).at(floor, (idx[:, 0], idx[:, 1]), at[:, 2])
        far = np.isinf(floor)
        fill = float(at[:, 2].max() if top else at[:, 2].min())
        floor[far] = fill if far.all() else float(floor[~far].mean())
        for _ in range(smooth):
            pad = np.pad(floor, 1, mode="edge")
            floor = 0.5 * floor + 0.125 * (
                pad[:-2, 1:-1] + pad[2:, 1:-1] + pad[1:-1, :-2] + pad[1:-1, 2:]
            )
        return cls(lo, spacing_mm, floor)

    def under(self, uv: np.ndarray) -> np.ndarray:
        """The floor under each point, read between samples."""
        x = np.clip((np.asarray(uv, float) - self.lo) / self.spacing_mm, 0.0, None)
        i = np.minimum(np.floor(x).astype(int), np.asarray(self.height.shape) - 2)
        f = x - i
        h = self.height
        near = h[i[:, 0], i[:, 1]] * (1 - f[:, 1]) + h[i[:, 0], i[:, 1] + 1] * f[:, 1]
        far = h[i[:, 0] + 1, i[:, 1]] * (1 - f[:, 1]) + h[i[:, 0] + 1, i[:, 1] + 1] * f[:, 1]
        return np.asarray(near * (1 - f[:, 0]) + far * f[:, 0], float)


@dataclass
class Inside:
    """How deep inside a volume's air each point of its plan is - positive in the air, negative in
    the metal, in mm. Read from the air itself, then smoothed, so the charge below has a slope
    everywhere rather than a cliff at the boundary."""

    lo: np.ndarray = field(default_factory=lambda: np.zeros(2), repr=False)
    spacing_mm: float = 5.0
    depth: np.ndarray = field(default_factory=lambda: np.zeros((1, 1)), repr=False)

    @classmethod
    def of(
        cls,
        air: Any,
        box: tuple[float, float, float, float],
        spacing_mm: float = 5.0,
        clear_mm: float = HOLE_CLEAR_MM,
    ) -> Inside:
        import shapely
        from scipy import ndimage

        # a hole inside the air gets a margin the run must keep off; the air's outer boundary does
        # not, because both of a fin's ends are pinned to it
        holes = [
            shapely.Polygon(ring).buffer(clear_mm)
            for poly in getattr(air, "geoms", [air])
            if poly.geom_type == "Polygon"
            for ring in poly.interiors
        ]
        if holes and clear_mm > 0.0:
            air = air.difference(shapely.union_all(holes))
        u0, v0, u1, v1 = box
        pad = 8.0 * spacing_mm
        lo = np.array([u0 - pad, v0 - pad])
        nu = int((u1 - u0 + 2 * pad) / spacing_mm) + 2
        nv = int((v1 - v0 + 2 * pad) / spacing_mm) + 2
        gu = lo[0] + np.arange(nu) * spacing_mm
        gv = lo[1] + np.arange(nv) * spacing_mm
        uu, vv = np.meshgrid(gu, gv, indexing="ij")
        air_here = shapely.contains_xy(air, uu.ravel(), vv.ravel()).reshape(nu, nv)
        near = ndimage.distance_transform_edt(air_here) * spacing_mm
        far = ndimage.distance_transform_edt(~air_here) * spacing_mm
        depth = ndimage.gaussian_filter(np.asarray(near - far, float), 1.0)
        return cls(lo, spacing_mm, depth)

    def deep(self, uv: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """How deep each point is, and that depth's slope - the analytic slope of the reading
        between samples, so finite differences of the same reading match it."""
        x = (np.asarray(uv, float) - self.lo) / self.spacing_mm
        top = np.asarray(self.depth.shape) - 2
        i = np.clip(np.floor(x).astype(int), 0, top)
        f = np.clip(x - i, 0.0, 1.0)
        d = self.depth
        d00 = d[i[:, 0], i[:, 1]]
        d10 = d[i[:, 0] + 1, i[:, 1]]
        d01 = d[i[:, 0], i[:, 1] + 1]
        d11 = d[i[:, 0] + 1, i[:, 1] + 1]
        fu, fv = f[:, 0], f[:, 1]
        value = (
            d00 * (1 - fu) * (1 - fv) + d10 * fu * (1 - fv) + d01 * (1 - fu) * fv + d11 * fu * fv
        )
        slope = np.stack(
            [
                ((d10 - d00) * (1 - fv) + (d11 - d01) * fv) / self.spacing_mm,
                ((d01 - d00) * (1 - fu) + (d11 - d10) * fu) / self.spacing_mm,
            ],
            axis=1,
        )
        return np.asarray(value, float), slope


CLEAR_OVER_MM = 100.0
"""The length of run the clearance rule is told for: a millimetre inside the margin along 10 mm of
run reads 0.1, :data:`CLEAR_MM` - about where the oracle starts to call a face alongside."""
ROOT_ZONE_MM = GRAZE_MM + HOLE_CLEAR_MM
"""How much of each end of a run is its root, whatever its length: within this of the metal it
roots in a rib is inside that metal's margin by right. By share alone (:data:`ENDS_SHARE`) a short
rib - 70 mm between two bosses - had 10 mm of root and could never keep the rule."""


def clearance(
    number: np.ndarray,
    rail: Rail,
    other: Rail,
    inside: Inside,
    pieces: int = PIECES,
) -> tuple[float, np.ndarray]:
    """How far a fin's **middle** comes inside :data:`GRAZE_MM` of the metal, in mm, summed along
    its run and told for each :data:`CLEAR_OVER_MM` of it - and that by the fin's ten numbers. The
    rule :data:`CLEAR_MM` holds it to.

    **Counted by the millimetre, not averaged over the run.** Averaged, a long fin could graze a
    wall for 30 mm and read as next to nothing, keep the rule, and be refused by the oracle, which
    counts how far a face runs alongside the metal (:data:`fastcae.ribs.oracle.ALONGSIDE_MM`). On
    2026-09-21 one fin lost that way took a network from 0.34 mm to 0.46 mm.

    A soft hinge, ``r log(1 + e^(v / r))`` of how much too close each point is, and not a step: a
    step reads a run already deep in the wall as flat - moving it a little changes nothing - so the
    only thing that lowered it was fading the fin out, and a first run under that rule deleted eight
    ribs of twelve. The hinge grows the further in a point is, so its slope always points out.

    The presence is left out on purpose: a fin keeps clear by moving, not by fading. The ends are
    exempt, as in :func:`strays` - an end must reach the metal.
    """
    pts, how = run(number, rail, other, pieces)
    deep, slope = inside.deep(pts)
    along = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    root = max(ENDS_SHARE * float(along[-1]), ROOT_ZONE_MM)
    middle = (along >= root) & (along <= along[-1] - root)
    if not middle.any():
        return 0.0, np.zeros(len(NUMBERS))
    v = (GRAZE_MM - deep[middle]) / CLEAR_SOFT_MM
    hinge = CLEAR_SOFT_MM * np.logaddexp(0.0, v)
    pull = 0.5 * (1.0 + np.tanh(0.5 * v))  # d hinge / d v, the logistic
    # each point stands for the stretch of run round it - half the piece before and half the one
    # after - in units of CLEAR_OVER_MM; the stretches move with the numbers too
    piece = np.diff(pts, axis=0)
    length = np.maximum(np.linalg.norm(piece, axis=1), 1e-12)
    by_piece = np.einsum("mk,mkj->mj", piece / length[:, None], how[1:] - how[:-1])
    stretch = np.concatenate([[length[0]], 0.5 * (length[1:] + length[:-1]), [length[-1]]])
    by_stretch = np.vstack([by_piece[:1], 0.5 * (by_piece[1:] + by_piece[:-1]), by_piece[-1:]])
    stretch, by_stretch = stretch / CLEAR_OVER_MM, by_stretch / CLEAR_OVER_MM
    by_point = -(pull * stretch[middle])[:, None] * slope[middle]
    grad = np.zeros(len(NUMBERS))
    grad[0:6] = np.einsum("mk,mkj->j", by_point, how[middle]) + hinge @ by_stretch[middle]
    return float(hinge @ stretch[middle]), grad


def capped(number: np.ndarray, f: Field, rail: Rail, other: Rail) -> np.ndarray:
    """``number`` with its three height stations held under the room the volume gives it.

    **The design volume already says how tall a rib may be.** It is the air the engineer approved,
    and it is bounded above by whatever is there - a bore, a wall, a ceiling - so its own roof is
    the answer, read station by station, with no need to go looking for metal and no way to be
    fooled by a bore's hole. It is far from level: on this housing one end of a volume stands tens
    of millimetres above the other, which is the taper a rib should follow.

    On top of that, :data:`TALLEST_MM` - the tallest a rib may stand at all, wherever the volume is
    deep enough to allow more.

    ``h(s)`` is a quadratic Bezier over the three stations, so the run never rises above them:
    capping the stations caps the rib.
    """
    out = np.array(number, float)
    out = _reach_capped(out, rail, other)
    pts, _ = run(out, rail, other)
    floor = f.floor.under(pts)
    room = under_roof(pts, floor, np.full(len(pts), TALLEST_MM), f)
    # **The ends are held to the metal they root in, the middle to the roof over it.** A rib's end
    # stands inside the boss or the wall it meets - sunk into it - so the air beside the rail there
    # is no measure of how tall it may be: read that way, the S2 ring's fins were held to the
    # 10 mm of air under a boss's flank and came out 30 mm tall against a boss of 60. The metal's
    # own height there is the cap, and it is what the build reads too (:mod:`.curved`).
    third = max(len(pts) // 3, 1)
    middle = room[third:-third] if len(pts) > 2 * third else room
    at = np.array(
        [
            min(TALLEST_MM, _wall(f, rail, float(out[0]), pts[0], pts[-1])),
            max(float(middle.min()), SHORTEST_MM),
            min(TALLEST_MM, _wall(f, other, float(out[1]), pts[-1], pts[0])),
        ]
    )
    # never proud of the metal around it: the middle's top under the line between the two ends'
    # tops, as the build holds it - not merely under the higher end
    ground = floor[[0, len(pts) // 2, -1]]
    line = 0.5 * ((ground[0] + at[0]) + (ground[2] + at[2])) - ground[1]
    at[1] = max(min(at[1], line), SHORTEST_MM)
    out[6:9] = np.minimum(out[6:9], at)
    # **a boss is covered.** A rib that meets a bearing's boss over a sliver of its height
    # stiffens nothing; the ribs that hold a bore run the boss's full height. So an end on the
    # anchor's round stands at least :data:`ROOT_SHARE` of the metal's height there. The
    # optimiser may raise it further; it may not lower it.
    if f.anchor is not None:
        centre, radius = f.anchor
        for k, p, cap in ((6, pts[0], at[0]), (8, pts[-1], at[2])):
            if float(np.linalg.norm(p - centre)) <= radius + ANCHOR_MARGIN_MM:
                out[k] = max(out[k], ROOT_SHARE * cap)
    # **no sag in the middle.** A top edge that runs from one wall to the other at a slope is an
    # ordinary rib, however steep. One that dips in between and climbs back is not: the run pulls
    # away from the metal either side of the dip and its end faces stand in the open. Holding the
    # middle station at or above the lower end leaves the profile's lowest point at an end - where
    # it may fall to nothing, which is a run-out, and is what a rib fading into a surface is.
    out[7] = max(out[7], min(out[6], out[8]))
    return out


ROOT_SHARE = 0.8
"""How much of a boss's height a rib ending on it must cover, at least."""
ANCHOR_MARGIN_MM = 25.0
"""How far outside the anchor's round an end still counts as on the boss: the rail runs on the
boss's face, a fillet or a flange out from its round."""
REACH_SHARE = 0.6
"""How far, as a share of the chord between its ends, an interior control point may stand out
from its end. Further, a cubic through four points loops back on itself, and the pass made
hairpins by the dozen - 38 of 60 fins refused for turning inside their own section - before this
held them. Within it a fin can still bow well round a bore; it cannot fold."""


def _reach_capped(number: np.ndarray, rail: Rail, other: Rail | None) -> np.ndarray:
    """``number`` with each interior control point's reach held to :data:`REACH_SHARE` of the
    chord, measured as :func:`control` reads it: square out from its end."""
    out = np.array(number, float)
    p0, t0 = rail.at(float(out[0]))
    p3, t3 = (other or rail).at(float(out[1]))
    chord = float(np.linalg.norm(p3 - p0))
    limit = max(REACH_SHARE * chord - SHORTEST_MM, SHORTEST_MM)
    for here, along, slot, far in ((p0, t0, 2, p3), (p3, t3, 4, p0)):
        square = np.array([-along[1], along[0]], float)
        square /= max(float(np.linalg.norm(square)), 1e-9)
        if float(square @ (far - here)) < 0.0:
            square = -square
        x = float((out[slot : slot + 2] - here) @ square)
        if x > limit:
            out[slot : slot + 2] = out[slot : slot + 2] - (x - limit) * square
    return out


def _wall(f: Field, spline: Rail, u: float, here: np.ndarray, away: np.ndarray) -> float:
    """How high the metal stands at a rib's end, above the floor the rib stands on.

    Read a little way **into** the metal, on whichever side of the rail the metal lies - at the face
    itself the reading is half air, and pushing simply away from the rib's other end walks into a
    bore's hole as often as into its wall.
    """
    at, along = spline.at(u)
    side = np.array([-along[1], along[0]])
    side /= max(float(np.linalg.norm(side)), 1e-9)
    if float(side @ (away - here)) > 0.0:
        side = -side
    # from just inside the face to a section in: a wall thinner than the rail's own smoothing
    # - 15 mm, with a low flange behind it - was overshot by every sample when they began at
    # 12 mm, and its ribs were capped at the flange's 50 mm against a wall of 180
    reach = np.stack(
        [f.crest.under(at[None] + x * side[None]) for x in (4.0, 8.0, 12.0, 18.0, 24.0)]
    )
    return float(max(reach.max() - f.floor.under(at[None])[0], SHORTEST_MM))


def under_roof(pts: np.ndarray, floor: np.ndarray, tall: np.ndarray, f: Field) -> np.ndarray:
    """``tall`` held under the volume's own ceiling at every station.

    The cubes stop at the ceiling, so the optimiser already sees nothing above it - but a solid
    built from the same numbers would stand right through it, into space the engineer did not
    approve. The ceiling is far from level, so this is read station by station and not once.
    """
    return np.minimum(tall, np.maximum(f.roof.under(pts) - floor, SHORTEST_MM))


def control(
    number: np.ndarray, rail: Rail, other: Rail | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """A fin's four control points, and how they move with its six curve numbers: (4, 2) and
    (4, 2, 6).

    Each end slides along its own rooted stretch. The interior point beside an end keeps only the
    part of itself **square to the rail there** - whatever ran along the wall is dropped - so the
    run always leaves the metal at right angles to it. A run leaving along a bore instead of out of
    it is tangent to that bore, and its end face then stands in the open however deep the end is
    buried; charging that was not enough, because a charge can be paid.

    What the optimiser still chooses is how far out each interior point sits, which is what makes
    the run straight, bowed, or an S. Only the direction of leaving is fixed.
    """
    p0, t0 = rail.at(float(number[0]))
    p3, t3 = (other or rail).at(float(number[1]))
    inner = []
    ways = []
    for here, along, free, far in (
        (p0, t0, number[2:4], p3),
        (p3, t3, number[4:6], p0),
    ):
        square = np.array([-along[1], along[0]], float)
        square /= max(float(np.linalg.norm(square)), 1e-9)
        # square to the rail, pointing at **this end's** far end: into the volume, not into the
        # wall behind it. Orienting both ends by the same direction sends the far one backwards,
        # its reach collapses to nothing, and a control polygon with two points on top of each
        # other has infinite curvature - which read as 7e36 before a test caught it.
        if float(square @ (far - here)) < 0.0:
            square = -square
        # how far out it sits, floored smoothly at nothing: a hard max() has a kink exactly where
        # the point sits on the wall, and a gradient either side of a kink is not one gradient
        x = float((np.asarray(free, float) - here) @ square)
        out = SHORTEST_MM + SQUARE_SOFT_MM * np.logaddexp(0.0, x / SQUARE_SOFT_MM)
        inner.append(here + out * square)
        ways.append(square * float(1.0 / (1.0 + np.exp(-x / SQUARE_SOFT_MM))))
    points = np.stack([p0, inner[0], inner[1], p3])
    how = np.zeros((4, 2, 6))
    how[0, :, 0] = t0
    how[3, :, 1] = t3
    # the interior point moves only along its square direction, so only that part of a move counts
    square0 = ways[0] / max(float(np.linalg.norm(ways[0])), 1e-12)
    square1 = ways[1] / max(float(np.linalg.norm(ways[1])), 1e-12)
    how[1, :, 2] = ways[0] * square0[0]
    how[1, :, 3] = ways[0] * square0[1]
    how[2, :, 4] = ways[1] * square1[0]
    how[2, :, 5] = ways[1] * square1[1]
    # and each interior point rides its own end as that end slides along the rail
    how[1, :, 0] = t0 - float(t0 @ square0) * ways[0]
    how[2, :, 1] = t3 - float(t3 @ square1) * ways[1]
    return points, how


def run(
    number: np.ndarray, rail: Rail, other: Rail | None = None, pieces: int = PIECES
) -> tuple[np.ndarray, np.ndarray]:
    """The curve read as ``pieces + 1`` points along it, and how each moves with the six curve
    numbers: (m, 2) and (m, 2, 6)."""
    points, how = control(number, rail, other)
    s = np.linspace(0.0, 1.0, pieces + 1)
    weight = _bernstein3(s)
    return weight @ points, np.einsum("ms,skj->mkj", weight, how)


def draw_one(
    at: np.ndarray,
    number: np.ndarray,
    rail: Rail,
    floor: Floor,
    radius: float,
    power: float,
    grow: float = 0.0,
    other: Rail | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """One fin on the cubes of its plan - ``at`` is (n, 3), the plan's two axes then the draw,
    grown by ``grow`` on each face for its halo.

    Returns which cubes it reaches, the share of each it fills, and that share's derivative by each
    of the fin's ten numbers, (m, 10).
    """
    presence = float(number[9])
    pts, how = run(number, rail, other)
    half = 0.5 * THICKNESS_MM + grow
    reach = half + radius
    lo, hi = pts.min(axis=0) - reach, pts.max(axis=0) + reach
    near = np.flatnonzero(np.all((at[:, :2] >= lo) & (at[:, :2] <= hi), axis=1))
    if not len(near):
        return near, np.zeros(0), np.zeros((0, len(NUMBERS)))
    p, z = at[near, :2], at[near, 2]
    base = floor.under(p)
    tall = float(np.max(number[6:9])) + grow + radius
    keep = (z >= base - grow - radius) & (z <= base + tall)
    near, p, z, base = near[keep], p[keep], z[keep], base[keep]
    if not len(near):
        return near, np.zeros(0), np.zeros((0, len(NUMBERS)))

    # --- how far to the run, blended across its pieces, and how far along it --------------------
    a, b = pts[:-1], pts[1:]
    e = b - a
    pieces = len(a)
    length2 = np.maximum(np.einsum("mk,mk->m", e, e), 1e-9)
    pa = p[:, None, :] - a[None, :, :]
    raw = np.einsum("nmk,mk->nm", pa, e) / length2
    inside = (raw > 0.0) & (raw < 1.0)
    t = np.clip(raw, 0.0, 1.0)
    off = pa - t[:, :, None] * e[None, :, :]
    root = np.sqrt(off[:, :, 0] ** 2 + off[:, :, 1] ** 2 + ROUND_MM**2)
    piece = root - ROUND_MM
    # a smooth least, so no cube switches from one piece to another with a jump in its slope
    weight = np.exp(-(piece - piece.min(axis=1, keepdims=True)) / BLEND_MM)
    weight /= weight.sum(axis=1, keepdims=True)
    d = np.einsum("nm,nm->n", weight, piece)
    along = (np.arange(pieces) + t) / pieces
    s = np.einsum("nm,nm->n", weight, along)

    # --- the fin there: across its section, and between the floor and its top -------------------
    rise = _bernstein2(s) @ np.asarray(number[6:9], float)
    across, dacross = _step(half - d, radius)
    up, _ = _step(z - base + grow, radius)
    down, ddown = _step(base + rise + grow - z, radius)
    whole = presence**power
    share = whole * across * up * down

    # --- back to the numbers --------------------------------------------------------------------
    by_d = -whole * dacross * up * down
    by_s = whole * across * up * ddown * (_dbernstein2(s) @ np.asarray(number[6:9], float))
    n = off / root[:, :, None]
    # the smooth least and the blended run each move with every piece's distance
    d_by_piece = weight * (1.0 - (piece - d[:, None]) / BLEND_MM)
    s_by_piece = -weight * (along - s[:, None]) / BLEND_MM
    # a piece's own distance and run move with its two ends. The run's turn under the cube cancels
    # at the foot of the perpendicular, and a clamped end does not move at all, so both terms in
    # d(distance)/d(end) but the first vanish.
    dd_da = -(1.0 - t)[:, :, None] * n
    dd_db = -t[:, :, None] * n
    dt_da = np.where(
        inside[:, :, None],
        (-e[None] - pa + 2.0 * t[:, :, None] * e[None]) / length2[None, :, None],
        0.0,
    )
    dt_db = np.where(
        inside[:, :, None], (pa - 2.0 * t[:, :, None] * e[None]) / length2[None, :, None], 0.0
    )
    on_piece = by_d[:, None] * d_by_piece + by_s[:, None] * s_by_piece
    on_t = by_s[:, None] * weight / pieces
    pull = np.zeros((len(near), len(pts), 2))
    pull[:, :-1] += on_piece[:, :, None] * dd_da + on_t[:, :, None] * dt_da
    pull[:, 1:] += on_piece[:, :, None] * dd_db + on_t[:, :, None] * dt_db

    grad = np.zeros((len(near), len(NUMBERS)))
    grad[:, 0:6] = np.einsum("nmk,mkj->nj", pull, how)
    grad[:, 6:9] = (whole * across * up * ddown)[:, None] * _bernstein2(s)
    grad[:, 9] = power * presence ** (power - 1.0) * across * up * down if presence > 0.0 else 0.0
    return near, share, grad


@dataclass
class Field:
    """A volume as a fin sees it: its plan, its cubes in it, the rooted stretches its fins' ends
    may sit on, and the floor they stand from."""

    name: str
    plane: Any = field(repr=False)
    cells: np.ndarray = field(repr=False)
    """The volume's cubes, by index among the design cubes."""
    at: np.ndarray = field(repr=False)
    """Where they are, (n, 3): the plan's two axes, then up along the draw."""
    rails: list[Rail] = field(default_factory=list, repr=False)
    floor: Floor = field(default_factory=Floor, repr=False)
    roof: Floor = field(default_factory=Floor, repr=False)
    """How high the volume's own air reaches over each point of its plan. The engineer approved the
    space below it and nothing above, and it is far from level - on this housing one end of a volume
    stands tens of millimetres above the other."""
    metals: list[tuple[float, Any]] = field(default_factory=list, repr=False)
    """The part's metal in the volume's plan, at several heights across the band: (height, shape).

    One plane is not enough. A wall leans and steps, so an end on the metal boundary at mid-height
    can stand in open air higher up - and then its end face shows, which is the one thing a rib
    running wall to wall must never have."""
    crest: Floor = field(default_factory=Floor, repr=False)
    """How high the part's metal reaches over each point of the plan - what caps a rib's height."""
    inside: Inside = field(default_factory=Inside, repr=False)
    bare: Inside = field(default_factory=Inside, repr=False)
    """The same depth without the margin round holes: the metal as it is, for judging a fin's
    outline against it (:mod:`.oracle`) rather than for keeping the run off it."""
    box: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    tallest_mm: float = 0.0
    """The most air there is over any column - the range a height station has."""
    anchor: tuple[np.ndarray, float] | None = None
    """The round the volume grows from - a boss, a bearing's ring - as its centre in the plan and
    its radius. A fin ending on it roots over most of its height (:data:`ROOT_SHARE`)."""


EXACT_MM = 1.0
"""How finely a column is read along the pull, for the fields' floor, roof and crest."""
EXACT_PLAN_MM = 5.0
"""How finely the fields' floor, roof and crest are laid over a volume's plan."""


def _lowest_span(inside: np.ndarray, zs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per row of ``inside`` (points, heights): where its lowest stretch starts and stops."""
    has = inside.any(axis=1)
    first = np.argmax(inside, axis=1)
    after = np.arange(inside.shape[1])[None, :] > first[:, None]
    gone = after & ~inside
    stop = np.where(gone.any(axis=1), np.argmax(gone, axis=1) - 1, inside.shape[1] - 1)
    lo = np.where(has, zs[first], np.nan)
    hi = np.where(has, zs[stop], np.nan)
    return lo, hi


def _filled(grid: np.ndarray) -> np.ndarray:
    """``grid`` with every nan taken from the nearest sample that has a value, so a map read off
    the edge of what was measured still has a slope."""
    from scipy import ndimage

    bad = ~np.isfinite(grid)
    if not bad.any() or bad.all():
        return np.where(bad, 0.0, grid)
    idx = ndimage.distance_transform_edt(bad, return_distances=False, return_indices=True)
    return grid[tuple(idx)]


def _smoothed(grid: np.ndarray, passes: int = 1) -> np.ndarray:
    for _ in range(passes):
        pad = np.pad(grid, 1, mode="edge")
        grid = 0.5 * grid + 0.125 * (
            pad[:-2, 1:-1] + pad[2:, 1:-1] + pad[1:-1, :-2] + pad[1:-1, 2:]
        )
    return grid


def _exact(
    found: Any, plane: Any, extraction: Any, at: np.ndarray, spacing_mm: float
) -> tuple[Floor, Floor, Floor]:
    """A volume's floor, roof and crest over its plan, read **exactly** - the floor and roof from
    the volume's own column at each point (its band, less the metal and what it keeps clear), the
    crest from the part's metal sectioned every :data:`EXACT_MM` along the pull.

    The build reads the same things (:func:`_room`, and the metal an end meets), so the optimiser
    now scores the rib that gets built. Read off 10 mm cubes, as these first were, the S2 ring's
    ribs were given twice the room the volume has by its bore, and the S3 ceiling's a floor 16 mm
    below where the volume starts.
    """
    import shapely

    from .library import _metal

    lo_uv = at[:, :2].min(axis=0) - 3.0 * spacing_mm
    hi_uv = at[:, :2].max(axis=0) + 3.0 * spacing_mm
    gu = np.arange(lo_uv[0], hi_uv[0] + spacing_mm, spacing_mm)
    gv = np.arange(lo_uv[1], hi_uv[1] + spacing_mm, spacing_mm)
    uu, vv = np.meshgrid(gu, gv, indexing="ij")
    uv = np.column_stack([uu.ravel(), vv.ravel()])
    zs = np.arange(at[:, 2].min() - 40.0, at[:, 2].max() + 40.0, EXACT_MM)
    axis = np.asarray(plane.normal, float)
    base = plane.to3d(uv)
    column = (base[:, None, :] + zs[None, :, None] * axis[None, None, :]).reshape(-1, 3)
    room = found.contains(column).reshape(len(uv), len(zs))
    lo, hi = _lowest_span(room, zs)
    floor = _filled(lo.reshape(uu.shape))
    roof = _filled(hi.reshape(uu.shape))
    # the metal's crest: of the stretches of metal over a point, the top of the one nearest the
    # middle of the volume's room there - a bore's flange beside the rib, not the housing's far wall
    solid = np.zeros((len(uv), len(zs)), bool)
    for k, z in enumerate(zs):
        metal = _metal(extraction, plane.shifted(float(z)))
        if not metal.is_empty:
            solid[:, k] = shapely.contains_xy(metal, uv[:, 0], uv[:, 1])
    middle = (0.5 * (floor + roof)).ravel()
    crest = np.full(len(uv), np.nan)
    for i in np.flatnonzero(solid.any(axis=1)):
        got = _nearest(_spans_on(solid[i], zs), float(middle[i]))
        if got is not None:
            crest[i] = got[1]
    crest = _filled(crest.reshape(uu.shape))
    lo_grid = np.array([gu[0], gv[0]])
    return (
        Floor(lo_grid, spacing_mm, _smoothed(floor)),
        Floor(lo_grid, spacing_mm, _smoothed(roof)),
        Floor(lo_grid, spacing_mm, _smoothed(crest)),
    )


def _mid(found: Any) -> tuple[Any, Any]:
    """The volume's section half way along its band: its plane and its air."""
    k = len(found.air) // 2
    return found.planes[k], found.air[k]


def fields(model: Any, volumes: list[tuple[str, Any]], extraction: Any) -> dict[str, Field]:
    """Each volume as a field, over the model's design cubes.

    **Up is the volume's own axis.** Measured on this housing: with it, the floor under every column
    is metal in both volumes; against it, 99 % of the S3 ceiling's columns floor at the band's own
    edge, which is not a floor at all.
    """
    from . import library

    centres = np.asarray(model.grid.origin) + model.cells[model.n_metal :] * model.grid.spacing_mm
    taken = np.zeros(model.n_design, bool)
    out: dict[str, Field] = {}
    for name, found in volumes:
        inside = found.contains(centres) & ~taken
        taken |= inside
        cells = np.flatnonzero(inside)
        plane, air = _mid(found)
        uv = plane.to2d(centres[cells])
        up = (centres[cells] - plane.origin) @ plane.normal
        at = np.column_stack([uv, up])
        rings = [
            np.asarray(r.coords)
            for poly in getattr(air, "geoms", [air])
            if poly.geom_type == "Polygon"
            for r in [poly.exterior, *poly.interiors]
        ]
        floor, roof, crest = _exact(found, plane, extraction, at, EXACT_PLAN_MM)
        heights = np.linspace(at[:, 2].min(), at[:, 2].max(), METAL_PLANES)
        metals = [(float(z), library._metal(extraction, plane.shifted(float(z)))) for z in heights]
        tallest = float((roof.height - floor.height).max()) if len(at) else 0.0
        lo_u, lo_v, hi_u, hi_v = air.bounds
        try:
            anchor: tuple[np.ndarray, float] | None = (
                plane.to2d(np.asarray(found.recipe.point, float)[None, :])[0],
                library._anchor_radius(extraction, found),
            )
        except Exception:  # a volume picked with no round to grow from
            anchor = None
        out[name] = Field(
            name=name,
            plane=plane,
            cells=cells,
            at=at,
            rails=rails(rings, library._metal(extraction, plane)),
            floor=floor,
            roof=roof,
            crest=crest,
            metals=metals,
            inside=Inside.of(air, (lo_u, lo_v, hi_u, hi_v), model.grid.spacing_mm),
            bare=Inside.of(air, (lo_u, lo_v, hi_u, hi_v), model.grid.spacing_mm, clear_mm=0.0),
            box=(lo_u, lo_v, hi_u, hi_v),
            tallest_mm=tallest,
            anchor=anchor,
        )
    return out


@dataclass
class Layout:
    """The fins as numbers: which volume each is in, which rooted stretch each of its ends is on,
    and every number's range."""

    where: list[str]
    ends: list[tuple[int, int]] = field(default_factory=list)
    lo: np.ndarray = field(default_factory=lambda: np.zeros((0, len(NUMBERS))), repr=False)
    hi: np.ndarray = field(default_factory=lambda: np.zeros((0, len(NUMBERS))), repr=False)

    @classmethod
    def of(cls, fields_: dict[str, Field], where: list[str], ends: list[tuple[int, int]]) -> Layout:
        lo, hi = [], []
        for name, (ia, ib) in zip(where, ends, strict=True):
            f = fields_[name]
            u0, v0, u1, v1 = f.box
            tall = max(f.tallest_mm, 1.0)
            lo.append([0.0, 0.0, u0, v0, u0, v0, 0.0, 0.0, 0.0, 0.0])
            hi.append(
                [
                    f.rails[ia].length_mm,
                    f.rails[ib].length_mm,
                    u1,
                    v1,
                    u1,
                    v1,
                    tall,
                    tall,
                    tall,
                    1.0,
                ]
            )
        return cls(where, ends, np.asarray(lo, float), np.asarray(hi, float))

    def narrow(
        self,
        numbers: np.ndarray,
        slide_mm: float | np.ndarray,
        band_mm: np.ndarray | None = None,
    ) -> Layout:
        """The same layout with each end allowed to slide only ``slide_mm`` either way of where
        ``numbers`` has it: a pass that refines a pattern rather than dissolving it. With
        ``band_mm`` - one for each fin, from :func:`bands` - its two interior control points are
        held as near their own places, so the run can neither fold nor leave the air it was seeded
        across: what the oracle would refuse afterwards becomes a bound the optimiser never
        crosses."""
        lo, hi = self.lo.copy(), self.hi.copy()
        slide = np.broadcast_to(np.asarray(slide_mm, float), (len(numbers),))  # one, or one a fin
        for k in (0, 1):
            lo[:, k] = np.maximum(self.lo[:, k], numbers[:, k] - slide)
            hi[:, k] = np.minimum(self.hi[:, k], numbers[:, k] + slide)
        if band_mm is not None:
            band = np.asarray(band_mm, float)[:, None]
            lo[:, 2:6] = np.maximum(self.lo[:, 2:6], numbers[:, 2:6] - band)
            hi[:, 2:6] = np.minimum(self.hi[:, 2:6], numbers[:, 2:6] + band)
        return Layout(self.where, self.ends, lo, hi)

    def numbers(self, x: np.ndarray) -> np.ndarray:
        """(fins, 10) from the shares, 0 to 1, that MMA moves."""
        return np.asarray(self.lo + x.reshape(-1, len(NUMBERS)) * (self.hi - self.lo), float)

    def shares(self, numbers: np.ndarray) -> np.ndarray:
        span = np.maximum(self.hi - self.lo, 1e-9)
        return np.asarray(np.clip((numbers - self.lo) / span, 0.0, 1.0).ravel(), float)


@dataclass
class Drawing:
    """The fins on the design cubes: the metal of each, and how to carry a derivative by the cubes'
    metal back to the fins' numbers."""

    metal: np.ndarray
    parts: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = field(repr=False)

    def back(self, by_cube: np.ndarray) -> np.ndarray:
        """``d/d numbers`` (fins, 10) of anything whose derivative by each cube's metal is
        ``by_cube``: the fins are ``1 - Π(1 - share)``, so a fin's share counts as much as the
        others leave room for."""
        room = np.log(np.maximum(1.0 - self.metal, 1e-12))
        out = np.zeros((len(self.parts), len(NUMBERS)))
        for i, (cubes, share, grad) in enumerate(self.parts):
            if not len(cubes):
                continue
            rest = np.exp(room[cubes] - np.log(np.maximum(1.0 - share, 1e-12)))
            out[i] = (by_cube[cubes] * rest) @ grad
        return out


def draw(
    fields_: dict[str, Field],
    layout: Layout,
    numbers: np.ndarray,
    n_design: int,
    radius: float,
    power: float,
) -> Drawing:
    """Every fin on the design cubes, drawn with the presence raised to ``power``."""
    room = np.zeros(n_design)
    parts = []
    for name, (ia, ib), number in zip(layout.where, layout.ends, numbers, strict=True):
        f = fields_[name]
        near, share, grad = draw_one(
            f.at, number, f.rails[ia], f.floor, radius, power, other=f.rails[ib]
        )
        cubes = f.cells[near]
        room[cubes] += np.log(np.maximum(1.0 - share, 1e-12))
        parts.append((cubes, share, grad))
    return Drawing(1.0 - np.exp(room), parts)


def weigh(
    fields_: dict[str, Field],
    layout: Layout,
    numbers: np.ndarray,
    n_design: int,
    radius: float,
) -> Drawing:
    """The same fins drawn for their **metal**: the presence counted as it is, not cubed.

    This is the whole of what makes a fin decide. Stiffness is charged at the presence cubed, so a
    fin half there gives an eighth of it; metal is charged at the presence itself, so that same fin
    still costs half. Half-present is then poor value and the fin goes to nothing or to whole.

    Charging both at the cube, as this first did, makes a half-present fin exactly as efficient as
    a whole one: nothing ever decides. Fifteen fins came out of such a run at 0.56 to 0.99, billed
    for 3.4 L and weighing 11.8 L when built - a design that cannot be made.
    """
    return draw(fields_, layout, numbers, n_design, radius, 1.0)


def nearest(fields_: dict[str, Field], name: str, point: np.ndarray) -> tuple[int, float]:
    """Which rooted stretch a point is nearest, and how far along it - how a seed's end becomes a
    number."""
    best, out = np.inf, (0, 0.0)
    for i, rail in enumerate(fields_[name].rails):
        gap = np.linalg.norm(rail.points - np.asarray(point, float), axis=1)
        k = int(np.argmin(gap))
        if float(gap[k]) < best:
            best, out = float(gap[k]), (i, k * rail.step_mm)
    return out


def values_carried(
    model: Any,
    fields_: dict[str, Field],
    layout: Layout,
    numbers: np.ndarray,
    reference: Any,
    radius: float,
    lead_weight: float = 0.0,
    least: float = 0.5,
) -> np.ndarray:
    """What each fin is worth **in the company of the rest**: how far J would rise, to first order,
    were the metal that fin alone accounts for taken away - by one evaluation of the objective's
    own derivative with every present fin standing. Positive is worth keeping.

    Standing alone on the bare part (:func:`values_alone`) a fin is read against whatever moves
    most there, and on a part with one dominant weakness that is the only thing any fin can be
    read against. Measured on the housing, 2026-09-21: the bare part's whole displacement was one
    face dishing, every fin on the other volume read as worth under 0.02 % of J and the chooser
    dropped all seventeen - though with the first face held the largest displacement moves to the
    second, where those fins are what holds it. In company each is read for the load it carries.

    Metal two fins share is credited to neither: take one away and the other still fills those
    cubes. So a junction costs its fins nothing, and of two fins laid on top of each other neither
    reads as the one to keep - the chooser's conflicts settle that."""
    from . import paths

    judged = np.array(numbers, float)
    present = judged[:, 9] >= least
    judged[:, 9] = np.where(present, 1.0, 0.0)
    drawing = draw(fields_, layout, judged, model.n_design, radius, 1.0)
    stiff = np.ones(len(model.cells))
    stiff[model.n_metal :] = paths.E_MIN + (1.0 - paths.E_MIN) * drawing.metal
    _, by_stiffness, _ = model.gradient(stiff, lead_weight, reference, {})
    by_metal = (1.0 - paths.E_MIN) * np.asarray(by_stiffness, float)[model.n_metal :]
    room = np.log(np.maximum(1.0 - drawing.metal, 1e-12))
    out = np.zeros(len(judged))
    for i, (cubes, share, _) in enumerate(drawing.parts):
        if not present[i] or not len(cubes):
            continue
        # the fins are 1 - Π(1 - share): without this one the cube keeps what the others fill
        without = 1.0 - np.exp(room[cubes] - np.log(np.maximum(1.0 - share, 1e-12)))
        mine = np.clip(drawing.metal[cubes] - without, 0.0, 1.0)
        out[i] = -float(by_metal[cubes] @ mine)
    return out


@dataclass
class Result:
    """One run: the fins' numbers, and how it got there."""

    layout: Layout
    numbers: np.ndarray
    metal: np.ndarray = field(repr=False)
    history: list[dict[str, Any]] = field(default_factory=list)
    frames: list[np.ndarray] = field(default_factory=list, repr=False)
    stats: dict[str, Any] = field(default_factory=dict)


def optimise(
    model: Any,
    fields_: dict[str, Field],
    layout: Layout,
    start: np.ndarray,
    budget_L: float,
    reference: Any,
    steps: int = 60,
    say: Any = print,
    move: float = 0.03,
    lead_weights: list[float] | None = None,
    hold: bool = False,
    stiffness_only: bool = False,
    skip: set[tuple[int, int]] | None = None,
    hold_apart: bool = True,
    root_free: float = 0.0,
    late: list[float] | None = None,
    hold_presence: bool = False,
) -> Result:
    """The fins' numbers bringing the objective lowest with ``budget_L`` of metal, from ``start``
    (fins, 10). Pairs in ``skip`` are junctions and are not held apart (:func:`spacing`). With
    ``hold_apart`` off no pair is: a seed laid down on purpose too rich crowds everywhere, and
    held apart it fades to a few fins before anything is learned - which fins to keep is the
    chooser's decision, made after this pass on what each fin is worth. ``late`` replaces
    :data:`LATE`, how much of the shape charges each step holds: a short pass wants them from the
    first step, or a fin has fourteen steps to curl into a hairpin before anything says no.
    ``hold_presence`` keeps every fin's presence where it started: in a pass that places fins for
    the chooser to decide on, whether a fin exists is not the pass's question, and left to it the
    shape charges - which scale with presence - are paid cheapest by fading rather than by
    straightening: 23 of 60 fins faded that way in one pass.

    The loop is :func:`.plates.optimise`'s - the same MMA, the same budget as one linear
    constraint, the same continuation of the smooth step's width, the presence's power and the
    lead's weight - with the fin of :func:`draw_one` in place of the plate. What changes is what
    the numbers mean: a curve that bends and a height that varies, not a plate of one thickness.

    ``hold`` makes it a **second pass** over a layout the first has settled. The objective is held
    still - sharp fins, the full presence power and the whole of the lead from the first step - and
    a step that makes it worse is taken back and tried again at half the move, while a step that
    gains lets the move grow again. The run's answer is then the best point it reached, not
    wherever its last try landed.

    Both halves of that matter, and both were learned by running it. Without the take-back the run
    oscillates: J swung between 1.48 and 2.49 over the last forty steps of the first run with the
    move stuck at its cap, because the gear mesh's lead is a difference of two skews that all but
    cancel, and a one per cent move of every number can swing it several fold. And without pinning
    the continuation the take-back is worse than useless - it compares values from an objective
    that is still changing, accepts a step that only looks better because the lead is not yet
    counted, and stops there, which is exactly what it did.
    """
    import time

    from . import mma, paths

    h3 = model.cell_volume
    budget = budget_L * 1e6
    x = layout.shares(start)
    low, upp = np.zeros_like(x), np.ones_like(x)
    old1 = old2 = None
    warm: dict[str, np.ndarray] = {}
    history: list[dict[str, Any]] = []
    frames: list[np.ndarray] = []
    started = time.perf_counter()
    drawing = None
    best: dict[str, Any] | None = None
    move_now = move
    unit: float | None = None
    for it in range(steps):
        t0 = time.perf_counter()
        if hold:
            # the objective held still: the lead's full weight, or the weight the caller's own
            # schedule ends on - a run answering for the deflection alone stays that way
            radius, power, lead_w = (
                mma.POLISH_RADIUS * model.grid.spacing_mm,
                mma.PRESENCE[-1],
                1.0 if lead_weights is None else float(lead_weights[-1]),
            )
        else:
            radius = mma.RADII[min(it, len(mma.RADII) - 1)] * model.grid.spacing_mm
            power = mma.PRESENCE[min(it, len(mma.PRESENCE) - 1)]
            schedule = lead_weights or mma.LEAD_WEIGHTS
            lead_w = schedule[min(it, len(schedule) - 1)]
        numbers = layout.numbers(x)
        if hold_presence:
            numbers[:, 9] = np.asarray(start, float)[:, 9]
        # a rib is held by the metal at its ends and may not stand above it
        for i, (name, (ia, ib)) in enumerate(zip(layout.where, layout.ends, strict=True)):
            f = fields_[name]
            numbers[i] = capped(numbers[i], f, f.rails[ia], f.rails[ib])
        x = layout.shares(numbers)
        drawing = draw(fields_, layout, numbers, model.n_design, radius, power)
        stiff = np.ones(len(model.cells))
        stiff[model.n_metal :] = paths.E_MIN + (1.0 - paths.E_MIN) * drawing.metal
        m, de, terms = model.gradient(stiff, lead_w, reference, warm, stiffness_only=stiffness_only)
        by_cube = de[model.n_metal :] * (1.0 - paths.E_MIN)
        span = layout.hi - layout.lo
        df = (drawing.back(by_cube) * span).ravel()
        # the metal is what would be cast, so the presence counts as it is - see weigh()
        weight = weigh(fields_, layout, numbers, model.n_design, radius)
        metal = float(weight.metal.sum()) * h3
        dg = (weight.back(np.full(model.n_design, h3 / budget)) * span).ravel()
        # the rules: the budget, and one per fin - its middle clear of the metal (see CLEAR_MM),
        # in mm, so a unit of either is about the same size
        rules, d_rules = [metal / budget - 1.0], [dg]
        stray = 0.0
        for i, (name, (ia, ib)) in enumerate(zip(layout.where, layout.ends, strict=True)):
            f = fields_[name]
            one, d_one = clearance(numbers[i], f.rails[ia], f.rails[ib], f.inside)
            stray = max(stray, one)
            row = np.zeros((len(layout.where), len(NUMBERS)))
            row[i] = d_one
            rules.append(one - CLEAR_MM)
            d_rules.append((row * span).ravel())
        # and one per pair of fins near each other: 100 mm between centres (see SPACING_MM)
        crowd = 0.0
        for _, _, one, d_one in spacing(layout, numbers, fields_, skip=skip, root_free=root_free):
            crowd = max(crowd, one)
            if not hold_apart:
                continue
            rules.append(one - SPACING_MM)
            d_rules.append((d_one * span).ravel())
        g, dg = np.asarray(rules), np.asarray(d_rules)
        charge = 0.0

        # the shape charges: a run may not turn inside its own section, and two runs - or one run
        # doubled back past itself - may not leave the mould without room for sand between them.
        # Both come later than the stray charge: a fin must be in one piece before its shape is
        # worth arguing about.
        schedule_late = late if late is not None else LATE
        late_now = 1.0 if hold else schedule_late[min(it, len(schedule_late) - 1)]
        bend = long_ = 0.0
        if late_now > 0.0:
            # every charge is a **mean over the fins**, so its weight means what its docstring says:
            # what one fin wholly offending would cost. Summed instead, as this first did, a modest
            # charge arrives once per fin - on twenty-four fins the shape charges came to 8.2 J
            # against a J of 3.6, and the cheapest answer was to delete ribs until almost nothing
            # was left: 16 present fell to 4, and 3.6 L to 0.48.
            each = max(len(layout.where), 1)
            d_shape = np.zeros((len(layout.where), len(NUMBERS)))
            for i, (name, (ia, ib)) in enumerate(zip(layout.where, layout.ends, strict=True)):
                f = fields_[name]
                one, d_one = bends(numbers[i], f.rails[ia], f.rails[ib], radius)
                bend += one / each
                d_shape[i] += BEND_WEIGHT * d_one / each
                far, d_far = lengths(numbers[i], f.rails[ia], f.rails[ib])
                long_ += far / each
                d_shape[i] += LONG_WEIGHT * d_far / each

            charge += late_now * (BEND_WEIGHT * bend + LONG_WEIGHT * long_)
            df = df + (late_now * d_shape * span).ravel()
        value = terms["value"] + charge
        # the objective in units of where it started: stiffness here runs from tens to thousands,
        # and unscaled, one unit of a broken rule (RELAX of them) weighed nothing beside it -
        # the rules
        # were trampled and the fins faded to keep what was left of them
        if unit is None:
            unit = max(abs(value), 1e-9)
        df = df / unit
        accepted = True
        if hold:
            accepted = best is None or (
                value <= best["value"] and float(g.max()) <= max(float(best["g"].max()), 0.01)
            )
            if accepted:
                if best is not None:
                    move_now = min(move_now * 1.5, move)
                best = {"value": value, "x": x.copy(), "df": df, "g": g, "dg": dg}
                frames.append(numbers.copy())
            else:
                # back to the best point, half the move, the asymptotes started afresh
                move_now = max(move_now * 0.5, 1e-4)
                old1 = old2 = None
            base = best
            assert base is not None
            x_new, low, upp = mma._mma_many(
                base["x"],
                base["df"],
                base["g"],
                base["dg"],
                low,
                upp,
                old1,
                old2,
                it if accepted else 0,
                move_now,
            )
            if accepted:
                old2, old1 = old1, base["x"].copy()
        else:
            frames.append(numbers.copy())
            x_new, low, upp = mma._mma_many(x, df, g, dg, low, upp, old1, old2, it, move)
            old2, old1 = old1, x.copy()
        change = float(np.abs(x_new - x).max())
        x = x_new
        present = int((numbers[:, 9] >= 0.5).sum())
        history.append(
            {
                "iteration": it,
                "objective": round(terms["value"], 5),
                "j": round(terms["j"], 5),
                "lead_weight": round(lead_w, 3),
                "robust_um": round(m["robust_um"], 4),
                "smooth_max_mm": round(m["smooth_max_mm"], 5),
                "largest_mm": round(m["largest_mm"], 5),
                "metal_L": round(metal / 1e6, 3),
                "stray": round(stray, 4),
                "bend": round(bend, 4),
                "crowd": round(crowd, 4),
                "long": round(long_, 4),
                "present": present,
                "accepted": bool(accepted),
                "move": round(move_now, 5),
                "change": round(change, 4),
                "seconds": round(time.perf_counter() - t0, 1),
            }
        )
        say(
            f"step {it}: J {terms['j']:.3f} (lead {m['robust_um']:.2f} um, max "
            f"{m['smooth_max_mm']:.3f} mm), {metal / 1e6:.2f} L, {present} fins present, "
            f"worst stray {stray:.3f}, bend {bend:.2f}, crowd {crowd:.2f}, long {long_:.2f}, "
            f"change {change:.3f}, {time.perf_counter() - t0:.0f} s"
            + ("" if accepted else " - taken back")
        )
        if hold and move_now < 2e-4:
            say(f"it stops at step {it}: nothing better within a move of {move_now:.1e}")
            break
    if hold and best is not None:
        # the run's answer is the best point it reached, not where its last try landed
        x = best["x"]
    numbers = layout.numbers(x)
    frames.append(numbers.copy())
    return Result(
        layout=layout,
        numbers=numbers,
        metal=drawing.metal if drawing is not None else np.zeros(model.n_design),
        history=history,
        frames=frames,
        stats={
            "seconds": round(time.perf_counter() - started, 1),
            "final": history[-1] if history else {},
        },
    )


CHORDS = 6
"""How many flat plates a fin is built from. A rib that follows a bore round is not flat, so it is
a short chain of plates meeting end to end, each square to the mould's pull - which is how a foundry
makes an arc and how the fuse reads one."""
REACH_MM = 12.0
"""How far an end may look for the metal before giving up. The rail is smoothed, so an end on it
sits a little out in the air rather than on the boundary; this is the slack that allows for."""
BURY_MM = 15.0
"""How far a fin's two outer ends are pushed into the metal they meet, at most - walked out only as
far as the metal really goes, stopping a skin short of any air on the far side.

The fin keeps its own clean outline and simply overlaps the wall; it is **never** trimmed against
the wall's silhouette first. That trimming is what made an outline follow 7-31 small steps of a wall
and leave a sliver face at every one - 25 of the 30 rejections that killed the plate route. The
overlap also settles the other failure: a fin that reaches into metal cannot end in mid-air."""
LAP_MM = 18.0
"""How far neighbouring plates of one fin overlap, so the joint is solid and not a seam."""


def _into(
    metal: Any,
    at: np.ndarray,
    away: np.ndarray,
    most: float = BURY_MM,
    across: list[Any] | None = None,
) -> float:
    """How far past ``at``, along ``away``, the metal goes - at most ``most``, and always leaving
    :data:`.library.SKIN_MM` between the end and whatever is on the far side.

    With ``across``, the metal is asked at **every height the rib stands**, not only at mid-height.
    A wall leans and steps, so an end buried at one height can stand in open air at another, and
    then its end face shows - which is the one thing a rib running wall to wall must never have.
    """
    from shapely.geometry import Point

    from .library import SKIN_MM

    asked = across if across else [metal]

    def inside(x: float) -> bool:
        here = at + away * x
        point = Point(float(here[0]), float(here[1]))
        return all(shape.contains(point) for shape in asked)

    # **Find the metal first.** The rail is smoothed - eleven samples averaged over forty
    # millimetres - so an end on it is no longer on the metal boundary; it sits a few millimetres
    # out in the air. Walking from there and stopping at the first point that is not metal gives up
    # instantly, and the end drives in nothing: measured on this housing, fifteen ends of eighteen.
    step = 1.0
    start = 0.0
    while start <= REACH_MM and not inside(start + SKIN_MM):
        start += step
    if start > REACH_MM:
        return 0.0
    # then bury from where the metal begins, leaving a skin on the far side
    out = 0.0
    while out + step <= most and inside(start + out + step + SKIN_MM):
        out += step
    return start + out


def ribs(
    layout: Layout,
    numbers: np.ndarray,
    fields_: dict[str, Field],
    metals: dict[str, Any],
    least: float = 0.5,
    chords: int = CHORDS,
) -> tuple[list[Any], dict[str, str]]:
    """Each fin present by ``least`` or more built as a chain of plates - the ribs, and why each
    fin not built was not.

    A plate's own plane holds the chord and the mould's pull, so its outline is the run across and
    the height up: the bottom edge follows the floor the fin stands on, the top edge that plus
    ``h(s)``. The chain's two outer ends are buried in the metal by :data:`BURY_MM` and its inner
    joints lap by :data:`LAP_MM`.
    """
    import shapely

    from ..volumes import slices
    from . import library

    out: list[Any] = []
    why: dict[str, str] = {}
    for k, (name, (ia, ib), number) in enumerate(
        zip(layout.where, layout.ends, numbers, strict=True)
    ):
        cid = f"{name}:fin:{k}"
        if number[9] < least:
            why[cid] = f"faded out (presence {number[9]:.2f})"
            continue
        f = fields_[name]
        pts, _ = run(number, f.rails[ia], f.rails[ib], pieces=chords)
        axis = np.asarray(f.plane.normal, float)
        metal = metals[name]
        first = _into(metal, pts[0], (pts[0] - pts[1]) / max(np.linalg.norm(pts[1] - pts[0]), 1e-9))
        last = _into(
            metal, pts[-1], (pts[-1] - pts[-2]) / max(np.linalg.norm(pts[-1] - pts[-2]), 1e-9)
        )
        made: list[tuple[Any, Any]] = []
        area = 0.0
        for j in range(len(pts) - 1):
            p0, p1 = pts[j], pts[j + 1]
            a3, b3 = f.plane.to3d(np.atleast_2d(p0))[0], f.plane.to3d(np.atleast_2d(p1))[0]
            along = b3 - a3
            length = float(np.linalg.norm(along))
            if length < 1.0:
                continue
            along = along / length
            at = slices.plane(a3, np.cross(along, axis), along)
            back = first if j == 0 else LAP_MM
            on = last if j == len(pts) - 2 else LAP_MM
            s = np.linspace(-back, length + on, 9)
            here = p0 + np.outer(np.clip(s, 0.0, length) / length, p1 - p0)
            floor = f.floor.under(here)
            share = np.clip(
                (np.arange(len(pts) - 1)[j] + s / max(length, 1e-9)) / (len(pts) - 1), 0, 1
            )
            tall = _bernstein2(share) @ np.asarray(number[6:9], float)
            if float(np.max(tall)) < 5.0:
                continue
            ring = np.vstack(
                [np.column_stack([s, floor]), np.column_stack([s, floor + tall])[::-1]]
            )
            shape = shapely.Polygon(ring).buffer(0)
            if shape.is_empty or not shape.is_valid:
                continue
            made.append((at, shape))
            # new metal is only the run in the air: the lap is the rib overlapping itself and the
            # bury is inside metal that is there already
            own = (s >= 0.0) & (s <= length)
            area += float(np.trapezoid(tall[own], s[own])) if own.sum() > 1 else 0.0
        if not made:
            why[cid] = "no plate of any height along its run"
            continue
        d = pts[-1] - pts[0]
        out.append(
            library.Candidate(
                id=cid,
                volume=name,
                family="fin",
                form="curve",
                placement=cid,
                angle_deg=float(np.degrees(np.arctan2(d[1], d[0])) % 360.0),
                hand=0,
                plane=made[0][0],
                shape=made[0][1],
                air_mm2=area,
                extra=made[1:],
            )
        )
    return out, why


STATIONS = 40
"""How many stations a fin's rails are sampled at. These set how faithfully the solid follows the
curve, not how many faces it has: the rails are fitted with one surface each either way."""
TALLEST_MM = 5.0 * THICKNESS_MM
"""The tallest a rib may stand anywhere, whatever room it is given - five times its own section.
Where the volume is deep enough to allow more, this is what stops it: a rib much taller than this
against its thickness is hard to fill and hard to draw, whatever the space above it says."""
METAL_PLANES = 5
"""How many heights across a volume's band the part's metal is read at. One plane says where the
metal is at mid-height and nothing about anywhere else."""
SHORTEST_MM = 8.0
"""The least a fin may stand anywhere along its run. Where ``h(s)`` falls below it the rib has run
out, and the solid ends there rather than closing to a knife edge."""


def _spans_on(inside: np.ndarray, zs: np.ndarray) -> list[tuple[float, float]]:
    """The stretches of ``zs`` where ``inside`` holds, as (lowest, highest)."""
    edges = np.flatnonzero(np.diff(np.concatenate([[0], inside.astype(np.int8), [0]])))
    return [(float(zs[a]), float(zs[b - 1])) for a, b in zip(edges[::2], edges[1::2], strict=True)]


def _nearest(spans: list[tuple[float, float]], near: float) -> tuple[float, float] | None:
    """Of ``spans``, the one holding ``near``, or else the closest to it."""
    if not spans:
        return None

    def gap(a: tuple[float, float]) -> float:
        return 0.0 if a[0] <= near <= a[1] else min(abs(a[0] - near), abs(a[1] - near))

    return min(spans, key=gap)


BEND_MM = 150.0
"""The tightest a fin's run may turn before it is charged, as a radius.

Not a casting limit - a rib can be poured round a far tighter bend than this. It is what a rib on a
housing **looks like**: production runs sweep through a few hundred millimetres of radius and never
wander. At one and a half times the section, which is where this started, a 20 mm rib could turn
inside a hairpin and pay nothing, and the runs showed it."""
BEND_WEIGHT = 1.0
"""What a fin turning everywhere tighter than :data:`BEND_MM` costs, in J."""
EVEN_WEIGHT = 1.0
"""What a fin whose curvature swings by a whole :data:`BEND_MM` along its run costs, in J.

Charging only the tightest turn says nothing about a run that is straight and then kinks once: it
and an even arc pay the same, and they look nothing alike. A circular arc has the **same curvature
all the way along**, so charging how much the curvature varies is what makes an even sweep the
cheapest curve there is, a straight run free, and a kink dear."""
SAND_MM = 40.0
"""Half the sand a mould needs between two rib faces: two runs closer than a section plus twice
this - 100 mm between centres - leave no room for it."""
LONGEST_MM = 250.0
"""The longest a rib may run before it is charged. A rib that wanders half way round a pocket is
neither what a foundry feeds nor what carries a load: the load wants the short way between two
anchors. Runs reached 811 mm before this was charged."""
LONG_WEIGHT = 1.0
"""What a rib twice :data:`LONGEST_MM` long would cost, in J."""
LATE = [0.0] * 14 + list(np.linspace(0.0, 1.0, 12)) + [1.0] * 200
"""How much of the shape charges the objective holds, step by step: none while the fins find their
places, then all of it. Later than the stray charge - a fin must be in one piece before its shape
is worth arguing about."""


def bends(number: np.ndarray, rail: Rail, other: Rail, radius: float) -> tuple[float, np.ndarray]:
    """How tightly a fin's run turns, beyond what it may - and that charge's derivative by its ten
    numbers.

    The run is a cubic through four control points, so its first and second derivatives are linear
    in them and the curvature is a smooth function of them throughout.
    """
    points, how = control(number, rail, other)
    s = np.linspace(0.0, 1.0, PIECES + 1)
    t = 1.0 - s
    d1 = np.stack([-3 * t**2, 3 * t * (t - 2 * s), 3 * s * (2 * t - s), 3 * s**2], axis=-1)
    d2 = np.stack([6 * t, 6 * (s - 2 * t), 6 * (t - 2 * s), 6 * s], axis=-1)
    c1, c2 = d1 @ points, d2 @ points
    turn = c1[:, 0] * c2[:, 1] - c1[:, 1] * c2[:, 0]
    speed = np.maximum(np.linalg.norm(c1, axis=1), 1e-9)
    curve = np.abs(turn) / speed**3
    over, dover = _step(curve - 1.0 / BEND_MM, 1.0 / (3.0 * BEND_MM))
    presence = float(number[9])
    # how tight it turns at its tightest, and how much that turning varies along the run
    mean = float(curve.mean())
    swing = (curve - mean) * BEND_MM
    charge = presence * (BEND_WEIGHT * float(over.mean()) + EVEN_WEIGHT * float((swing**2).mean()))

    sign = np.sign(turn)
    # d(curvature)/d(control point), through the turn and through the speed
    by_turn = sign / speed**3
    by_speed = -3.0 * np.abs(turn) / speed**4
    grad = np.zeros(len(NUMBERS))
    pull = np.zeros((len(s), 4, 2))
    pull[:, :, 0] = (
        by_turn[:, None] * (d1 * c2[:, 1, None] - d2 * c1[:, 1, None])
        + by_speed[:, None] * d1 * (c1[:, 0] / speed)[:, None]
    )
    pull[:, :, 1] = (
        by_turn[:, None] * (d2 * c1[:, 0, None] - d1 * c2[:, 0, None])
        + by_speed[:, None] * d1 * (c1[:, 1] / speed)[:, None]
    )
    weight = (
        presence
        # d(mean squared swing)/d(curvature at j) is 2 * swing_j * BEND_MM / n: the mean's own
        # move cancels, because the swings sum to nothing by construction
        * (BEND_WEIGHT * dover + EVEN_WEIGHT * 2.0 * swing * BEND_MM)
        / len(s)
    )
    grad[0:6] = np.einsum("m,mkc,kcj->j", weight, pull, how)
    grad[9] = charge / max(presence, 1e-9)
    return charge, grad


def lengths(number: np.ndarray, rail: Rail, other: Rail) -> tuple[float, np.ndarray]:
    """How far a fin runs beyond what it may, as a share of :data:`LONGEST_MM` - and that charge's
    derivative by its ten numbers.

    The run is sampled and its length summed, so the charge falls on every control point that made
    it long.
    """
    pts, how = run(number, rail, other)
    step = np.diff(pts, axis=0)
    span = np.maximum(np.linalg.norm(step, axis=1), 1e-9)
    total = float(span.sum())
    presence = float(number[9])
    over = max(total - LONGEST_MM, 0.0) / LONGEST_MM
    grad = np.zeros(len(NUMBERS))
    if over <= 0.0:
        return 0.0, grad
    way = step / span[:, None]
    pull = np.zeros_like(pts)
    pull[:-1] -= way
    pull[1:] += way
    grad[0:6] = presence * np.einsum("mk,mkj->j", pull, how) / LONGEST_MM
    grad[9] = over
    return presence * over, grad


SPACING_MM = 0.1
"""**A rule, not a charge:** the most two fins may come inside a section plus twice
:data:`SAND_MM` of each other - 100 mm between centres - in mm summed over one run's points and
divided by their count (see :func:`spacing`). As the charge :func:`crowds` it was traded away: the
first curved-plate design had two ribs lying across each other. Nearly zero - the soft hinge never
reads exactly zero."""


ROOT_FREE = 0.35
"""The share of a run, from a root it shares with another, over which the two are not held apart.
Spokes run into one boss and two ribs meet a wall in a V: at the shared root they are as close as
ribs get, by design, and what a mould needs between two faces is judged along the rest. Spokes
20 degrees apart on a boss of 270 mm stand 94 mm apart there and 134 mm a third of the way out.
A figure to be set off the production casting, as :data:`SAND_MM` is."""


def _judged(here: np.ndarray, there: np.ndarray, gap: float, root_free: float) -> np.ndarray:
    """Which pairs of points of two runs the spacing rule reads, (m, n): all of them, unless the
    runs **share a root** - an end of each within ``gap`` of the other - when the first
    ``root_free`` of each run from that end is left out."""
    keep_h = np.ones(len(here), bool)
    keep_t = np.ones(len(there), bool)
    if root_free > 0.0:
        nh = int(round(root_free * (len(here) - 1)))
        nt = int(round(root_free * (len(there) - 1)))
        for eh in (0, -1):
            for et in (0, -1):
                if float(np.linalg.norm(here[eh] - there[et])) >= gap:
                    continue
                if eh == 0:
                    keep_h[: nh + 1] = False
                else:
                    keep_h[len(here) - nh - 1 :] = False
                if et == 0:
                    keep_t[: nt + 1] = False
                else:
                    keep_t[len(there) - nt - 1 :] = False
    return keep_h[:, None] & keep_t[None, :]


def spacing(
    layout: Layout,
    numbers: np.ndarray,
    fields_: dict[str, Field],
    skip: set[tuple[int, int]] | None = None,
    root_free: float = 0.0,
) -> list[tuple[int, int, float, np.ndarray]]:
    """Each pair of fins in one volume near enough to matter, with how far inside 100 mm of each
    other they come and that by every fin's numbers: ``(i, j, value, (fins, 10))``, the rule
    :data:`SPACING_MM` holds each to. Pairs in ``skip`` are **junctions** - two ribs that cross
    steeply and are meant to meet - and are not held apart.

    **Two fins, never one against itself.** Points of one run are all within 100 mm of their
    neighbours along it, so a fin measured against itself broke the rule everywhere, and the first
    run under it faded every fin but one to keep it. A run cannot double back past itself anyway:
    it may not bend tighter than :data:`BEND_MM`.

    A soft hinge of how much too close each pair of points is, as :func:`clearance` uses: it grows
    the further two runs overlap, so its slope always parts them - a step read two ribs lying across
    each other as flat. Summed over the pairs and divided by one run's points, so a short touch
    counts as much as it should and is not lost among every far pair. Times both presences: a fin
    that has faded out is not built, and need not keep its distance.
    """
    gap = THICKNESS_MM + 2.0 * SAND_MM
    runs, hows = [], []
    for name, (ia, ib), number in zip(layout.where, layout.ends, numbers, strict=True):
        f = fields_[name]
        pts, how = run(number, f.rails[ia], f.rails[ib])
        runs.append(pts)
        hows.append(how)
    out = []
    for i, here in enumerate(runs):
        for j, there in enumerate(runs):
            if j <= i or layout.where[i] != layout.where[j]:
                continue
            if skip and (i, j) in skip:
                continue
            lo = np.maximum(here.min(axis=0), there.min(axis=0))
            hi = np.minimum(here.max(axis=0), there.max(axis=0))
            if np.any(lo - hi > gap + 20.0):
                continue  # boxes too far apart for any two points to come near
            apart = here[:, None, :] - there[None, :, :]
            far = np.linalg.norm(apart, axis=2)
            v = (gap - far) / CLEAR_SOFT_MM
            judged = _judged(here, there, gap, root_free)
            hinge = np.where(judged, CLEAR_SOFT_MM * np.logaddexp(0.0, v), 0.0)
            pull = np.where(judged & (far > 1e-6), 0.5 * (1.0 + np.tanh(0.5 * v)), 0.0)
            share = float(numbers[i, 9] * numbers[j, 9])
            n = float(len(here))
            raw = float(hinge.sum()) / n
            grad = np.zeros((len(runs), len(NUMBERS)))
            way = apart / np.maximum(far, 1e-9)[:, :, None]
            by_here = -share * np.einsum("mn,mnc->mc", pull, way) / n
            by_there = share * np.einsum("mn,mnc->nc", pull, way) / n
            grad[i, 0:6] += np.einsum("mc,mcj->j", by_here, hows[i])
            grad[j, 0:6] += np.einsum("nc,ncj->j", by_there, hows[j])
            grad[i, 9] += float(numbers[j, 9]) * raw
            grad[j, 9] += float(numbers[i, 9]) * raw
            out.append((i, j, share * raw, grad))
    return out


def _nearest_on(rail: Rail, point: np.ndarray) -> float:
    """How far along ``rail`` comes nearest ``point``."""
    return float(np.argmin(np.linalg.norm(rail.points - point, axis=1))) * rail.step_mm


ANCHOR_PATTERNS = ("spokes", "chords", "tangents", "wheel")
"""The patterns cast from a volume's anchor: spokes by angle from the boss to the wall, chords
from wall to wall that close a ring round the boss, tangents leaving the boss aslant, and a wheel -
spokes and chords together, whose crossings close its cells. They need no telling of which rail is
the bore and which the wall, so they hold on a volume whose bore and wall share one rail."""
RING_SIDES = 4
"""How many chords close the ring. A chord between two feet on the wall meets it at half the angle
it spans: between neighbouring feet that is a few degrees - a rib lying along the wall, which the
gate of placement refuses and the wheel of 2026-09-21 lost most of its fins to. Four sides span a
quarter of the wall each and meet it at 45 degrees; five meet it at 36, six at 30 - refused."""
TANGENT_DEG = 35.0
"""How far round the boss a tangent's wall end sits from the angle it leaves at."""


BAND_SHARE = 0.15
"""The most a fin's interior control points may move in a pass, as a share of its chord. A cubic's
middle moves three quarters as far as its control points, so a run of chord c bows at most
0.11 c and turns no tighter than about c - a 160 mm spoke keeps a radius over 150 mm, against the
40 mm under which the oracle calls a run folded (:data:`fastcae.ribs.oracle.TURN_LEAST_MM`)."""
BAND_LEAST_MM = 4.0
"""The band a fin keeps however little room it has: enough to move off a wall it was seeded near."""
BAND_MOST_MM = 40.0
"""The band a fin gets however much room it has - as far as its ends may slide."""


def bands(fields_: dict[str, Field], layout: Layout, numbers: np.ndarray) -> np.ndarray:
    """How far each fin's interior control points may move in a pass, either way of where
    ``numbers`` has them (mm): the room the middle half of its run has to the edge of its volume's
    air, less the margin a rib's middle keeps (:data:`GRAZE_MM`), and never more than
    :data:`BAND_SHARE` of its chord. Read over the middle half because there a run ought to be
    plainly in the air - its ends sit on the boundary by right - and a cubic's middle moves three
    quarters as far as the control points that steer it."""
    out = np.zeros(len(numbers))
    for n, (name, (ia, ib), number) in enumerate(
        zip(layout.where, layout.ends, numbers, strict=True)
    ):
        fld = fields_[name]
        pts, _ = run(number, fld.rails[ia], fld.rails[ib])
        chord = float(np.linalg.norm(pts[-1] - pts[0]))
        room = BAND_MOST_MM
        air = fld.inside if fld.inside.depth.size > 1 else fld.bare
        if air.depth.size > 1:
            m = len(pts)
            depth, _ = air.deep(pts[m // 4 : m - m // 4])
            room = (float(depth.min()) - GRAZE_MM) / 0.75
        out[n] = float(np.clip(min(room, BAND_SHARE * chord), BAND_LEAST_MM, BAND_MOST_MM))
    return out


PLACE_SQUARE_DEG = 35.0
"""The least angle a seeded fin's straight run may make with the wall it ends on. Below it the rib's
face meets the wall at a glance, the wedge between them is where the fuse leaves its slivers, and
a run forced to leave square (:func:`control`) has to turn so tightly to do it that it folds."""
PLACE_ROOT_MM = 25.0
"""The least the metal must stand at an end for a fin to be seeded there - a little over one
section, :data:`THICKNESS_MM`. The builder sinks a rib's end into the wall it meets; where the wall
stands lower than this there is nothing to sink it into across the rib's whole thickness, and the
height rule (:func:`capped`) tapers the rib to nothing at that end. Measured 2026-09-21: every fin
the builder refused for want of a root ended on metal 8 to 23 mm tall."""
PLACE_SKIP_MM = 15.0
"""How much of each end of a run the air test leaves unread: the end sits on the boundary, and a
hole's margin (:data:`HOLE_CLEAR_MM`) reaches this far round a boss a fin may rightly end on."""
PLACE_DEEP_MM = -2.0
"""How far outside the air a sample of the run may read before the run counts as leaving it - the
depth is smoothed and laid on a 5 mm plan, so the boundary itself reads a millimetre or two off."""
TOO_SHORT = "shorter than three sections"


def placeable(f: Field, a: tuple[int, float], b: tuple[int, float]) -> str | None:
    """Why a straight fin between two rail positions may not be seeded - ``None`` when it may.

    **The rules of placement, in one place, for every seeder** - spokes, chords, load-path members,
    a scatter: they differ in what they propose and never in what is allowed. Each rule is one the
    oracle or the builder would otherwise enforce later by refusing the fin, after an optimiser has
    spent its steps on it and a chooser has counted on it:

    - the run is at least three sections long;
    - it lies across the volume's own air, clear of every hole by the margin the pass holds - never
      over a bore, a keep-out or an island of metal;
    - it meets the wall at each end at :data:`PLACE_SQUARE_DEG` or steeper;
    - the metal at each end stands at least :data:`PLACE_ROOT_MM`, so the end can root;
    - its middle stands clear of the metal by the rule the pass itself holds
      (:func:`clearance`, :data:`CLEAR_MM`) - **the same measure, not a likeness of it**. A fin
      seeded inside that margin has only a narrow band to move in (:func:`bands`), ends the pass
      still breaking the rule, and is refused by the oracle afterwards: on 2026-09-21 one such
      fin, removed after the pass, took a network from 0.305 mm to 0.357 mm by itself.

    All five are read on the volume's plan and its height maps, in about a millisecond."""
    pa, ta = f.rails[a[0]].at(a[1])
    pb, tb = f.rails[b[0]].at(b[1])
    length = float(np.linalg.norm(pb - pa))
    if length < 3.0 * THICKNESS_MM:
        return TOO_SHORT
    way = (pb - pa) / length
    air = f.inside if f.inside.depth.size > 1 else f.bare
    if air.depth.size > 1 and length > 2.0 * PLACE_SKIP_MM:
        t = np.arange(PLACE_SKIP_MM, length - PLACE_SKIP_MM + 1e-9, 5.0)
        depth, _ = air.deep(pa + t[:, None] * way)
        if float(depth.min()) < PLACE_DEEP_MM:
            return "passes over a hole, a keep-out or the metal"
    for tangent in (ta, tb):
        along = tangent / max(float(np.linalg.norm(tangent)), 1e-9)
        angle = float(np.degrees(np.arccos(np.clip(abs(float(way @ along)), 0.0, 1.0))))
        if angle < PLACE_SQUARE_DEG:
            return f"meets its wall at {angle:.0f} degrees"
    if f.crest.height.size > 1:
        for (i, u), here, away in ((a, pa, pb), (b, pb, pa)):
            tall = _wall(f, f.rails[i], u, here, away)
            if tall < PLACE_ROOT_MM:
                return f"the metal at one end stands only {tall:.0f} mm"
    if f.inside.depth.size > 1:
        number = np.asarray(_straight(f, a, b, PLACE_ROOT_MM), float)
        near, _ = clearance(number, f.rails[a[0]], f.rails[b[0]], f.inside)
        if near > CLEAR_MM:
            return f"its middle does not stand {GRAZE_MM:.0f} mm clear of the metal"
    return None


def _ray_hits(f: Field, centre: np.ndarray, angle_deg: float) -> list[tuple[float, int, float]]:
    """Where a ray from the anchor's centre crosses the volume's rails: ``(distance, rail, u)``,
    nearest first."""
    from shapely.geometry import LineString

    theta = np.radians(angle_deg)
    way = np.array([np.cos(theta), np.sin(theta)])
    far = centre + 5000.0 * way
    ray = LineString([centre, far])
    out: list[tuple[float, int, float]] = []
    for i, rail in enumerate(f.rails):
        pts = rail.points if not rail.closed else np.vstack([rail.points, rail.points[:1]])
        crossing = ray.intersection(LineString(pts))
        for g in getattr(crossing, "geoms", [crossing]):
            if g.is_empty or g.geom_type != "Point":
                continue
            p = np.array([g.x, g.y])
            out.append((float(np.linalg.norm(p - centre)), i, _nearest_on(rail, p)))
    return sorted(out)


def _straight(
    f: Field, a: tuple[int, float], b: tuple[int, float], tall: float, bow: float = 0.0
) -> list[float]:
    """A fin's ten numbers between two rail positions, straight or bowed."""
    pa, _ = f.rails[a[0]].at(a[1])
    pb, _ = f.rails[b[0]].at(b[1])
    one, two = pa + (pb - pa) / 3.0, pa + 2.0 * (pb - pa) / 3.0
    if bow:
        square = np.array([-(pb - pa)[1], (pb - pa)[0]])
        square /= max(float(np.linalg.norm(square)), 1e-9)
        one, two = one + bow * square, two + bow * square
    return [a[1], b[1], *one, *two, tall, tall, tall, 1.0]


def sow_anchor(
    fields_: dict[str, Field],
    pattern: str,
    count: int = 36,
    bow: float = 0.0,
    refused: list[tuple[str, str]] | None = None,
    apart: bool = True,
    also: Any = None,
) -> tuple[Layout, np.ndarray]:
    """Fins laid out in one of :data:`ANCHOR_PATTERNS` round each volume's anchor, as a pass's
    starting point: ``count`` rays a volume, one every ``360 / count`` degrees, each a spoke from
    the boss's round to **the first rooted boundary it meets across the volume's own air** - the
    wall, or another boss standing between. Never the farthest: a ray that carries on past a second
    bore to the far wall lays a rib over that bore's shaft.

    Every fin of every pattern goes through :func:`placeable`, and with ``apart`` must also stand
    with those already placed (:func:`_against`): the spacing rule is kept by where fins are put,
    not by a chooser thinning them afterwards - rays cast closer than the rule allows seed every
    second or third spoke. What is refused is never seeded, and is told in ``refused`` as
    ``(volume, why)`` when a list is given.

    ``also`` is one more judge, the caller's: ``also(volume, field, a, b, numbers) -> why | None``,
    asked after the gate and before a fin takes its place among the others - so a fin it refuses
    leaves room for its neighbour. It is how the CAD's own sections judge a seed
    (:func:`fastcae.ribs.oracle.on_sheet`): they see what no plan or cube does - a wall 4 mm tall
    that the cubes read as 25, a leaning wall an end runs along - and cost seconds a fin, so they
    are not part of :func:`placeable`."""
    if pattern not in ANCHOR_PATTERNS:
        raise ValueError(f"no anchor pattern {pattern!r}: one of {ANCHOR_PATTERNS}")
    where: list[str] = []
    ends: list[tuple[int, int]] = []
    rows: list[list[float]] = []
    for name, f in fields_.items():
        if f.anchor is None or not f.rails:
            continue
        centre, radius = f.anchor
        tall = min(TALLEST_MM, max(f.tallest_mm, SHORTEST_MM))
        feet: list[tuple[tuple[int, float], tuple[int, float]]] = []
        angles: list[float] = []
        placed: list[np.ndarray] = []

        def stands(
            a: tuple[int, float],
            b: tuple[int, float],
            name: str = name,
            f: Field = f,
            tall: float = tall,
            placed: list[np.ndarray] = placed,
        ) -> str | None:
            """Why a fin the gate has passed may still not be placed in this volume - it crowds
            or crosses one already there, or the caller's own judge refuses it - and its run
            remembered when it may."""
            row = _straight(f, a, b, tall, bow)
            here, _ = run(np.asarray(row, float), f.rails[a[0]], f.rails[b[0]])
            why = _against(here, placed) if apart else None
            if why is None and also is not None:
                why = also(name, f, a, b, row)
            if why is None:
                placed.append(here)
            return why

        for k in range(count):
            angle = 360.0 * k / count
            hits = _ray_hits(f, np.asarray(centre, float), angle)
            near = [h for h in hits if h[0] >= 0.5 * radius]
            if len(near) < 2:
                continue
            # no boss face on this ray: the anchor's round is cut open here, as a keep-out cuts
            # a ring open
            if near[0][0] > 1.5 * radius:
                continue
            boss = (near[0][1], near[0][2])
            for _, rail, u in near[1:]:
                why = placeable(f, boss, (rail, u))
                if why is None and pattern in ("spokes", "wheel"):
                    why = stands(boss, (rail, u))
                if why is None:
                    feet.append((boss, (rail, u)))
                    angles.append(angle)
                if why != TOO_SHORT:
                    # placed - or stopped by something every boundary further out lies beyond too
                    if why is not None and refused is not None:
                        refused.append((name, why))
                    break
        if pattern in ("spokes", "wheel"):
            for boss, wall in feet:
                where.append(name)
                ends.append((boss[0], wall[0]))
                rows.append(_straight(f, boss, wall, tall, bow))
        if pattern in ("chords", "wheel") and feet:
            # the ring's corners: the foot nearest each of RING_SIDES angles round the boss
            corners = []
            for j in range(RING_SIDES):
                want = angles[0] + 360.0 * j / RING_SIDES
                off = [abs((g - want + 180.0) % 360.0 - 180.0) for g in angles]
                k = int(np.argmin(off))
                if off[k] <= 1.5 * 360.0 / count:
                    corners.append(feet[k][1])
                else:
                    corners.append(None)
            for a, b in zip(corners, corners[1:] + corners[:1], strict=True):
                if a is None or b is None or a == b:
                    continue
                why = placeable(f, a, b) or stands(a, b)
                if why is not None:
                    if refused is not None:
                        refused.append((name, why))
                    continue
                where.append(name)
                ends.append((a[0], b[0]))
                rows.append(_straight(f, a, b, tall, bow))
        if pattern == "tangents":
            shift = max(int(round(TANGENT_DEG * count / 360.0)), 1)
            for k, (boss, _) in enumerate(feet):
                wall = feet[(k + shift) % len(feet)][1]
                why = placeable(f, boss, wall) or stands(boss, wall)
                if why is not None:
                    if refused is not None:
                        refused.append((name, why))
                    continue
                where.append(name)
                ends.append((boss[0], wall[0]))
                rows.append(_straight(f, boss, wall, tall, bow))
    return Layout.of(fields_, where, ends), np.asarray(rows, float).reshape(-1, len(NUMBERS))


SCATTER_TRIES = 400
"""How many random pairs of wall positions are tried for each fin a scatter is asked for. Most are
not ribs - too short, over a bore, along a wall, across one already placed - and are refused."""
SCATTER_CROSS_DEG = 60.0
"""How steeply two scattered fins must cross to be a junction and not a conflict - the chooser's
own figure (:data:`fastcae.ribs.choose.CROSS_DEG`)."""


def sow_scatter(
    fields_: dict[str, Field],
    count: int = 30,
    seed: int = 0,
    refused: list[tuple[str, str]] | None = None,
    also: Any = None,
) -> tuple[Layout, np.ndarray]:
    """Up to ``count`` fins a volume, **scattered at random and placed by rule**: two positions
    drawn anywhere along the volume's rails, kept only if the straight fin between them passes the
    gate of placement (:func:`placeable`), runs no longer than twice :data:`LONGEST_MM`, and stands
    against every fin already kept either a section and its sand apart - but for a root the two
    share (:data:`ROOT_FREE`) - or across it at :data:`SCATTER_CROSS_DEG` or steeper, a junction.

    What order there is in the result is the rules' and not a pattern's: square to its walls,
    evenly apart, crossing steeply or not at all. The same ``seed`` scatters the same fins.
    ``also`` is the caller's own judge, asked last, as :func:`sow_anchor` asks it."""
    rng = np.random.default_rng(seed)
    where: list[str] = []
    ends: list[tuple[int, int]] = []
    rows: list[list[float]] = []
    for name, fld in fields_.items():
        if not fld.rails:
            continue
        tall = min(TALLEST_MM, max(fld.tallest_mm, SHORTEST_MM))
        lengths = np.array([len(r.points) * r.step_mm for r in fld.rails], float)
        share = lengths / lengths.sum()
        kept: list[np.ndarray] = []
        for _ in range(SCATTER_TRIES * count):
            if len(kept) >= count:
                break
            ia, ib = (int(k) for k in rng.choice(len(fld.rails), size=2, p=share))
            a = (ia, float(rng.uniform(0.0, lengths[ia])))
            b = (ib, float(rng.uniform(0.0, lengths[ib])))
            why = placeable(fld, a, b)
            pa, _ = fld.rails[ia].at(a[1])
            pb, _ = fld.rails[ib].at(b[1])
            if why is None and float(np.linalg.norm(pb - pa)) > 2.0 * LONGEST_MM:
                why = "longer than a rib runs"
            row = _straight(fld, a, b, tall)
            # the run as it will be drawn - it leaves its walls square, so it is not the chord -
            # judged against each fin already kept by the measures the chooser itself uses
            here, _ = run(np.asarray(row, float), fld.rails[ia], fld.rails[ib])
            if why is None:
                why = _against(here, kept)
            if why is None and also is not None:
                why = also(name, fld, a, b, row)
            if why is not None:
                if refused is not None:
                    refused.append((name, why))
                continue
            kept.append(here)
            where.append(name)
            ends.append((ia, ib))
            rows.append(row)
    return Layout.of(fields_, where, ends), np.asarray(rows, float).reshape(-1, len(NUMBERS))


def _against(here: np.ndarray, kept: list[np.ndarray]) -> str | None:
    """Why a run may not stand with the runs already placed in its volume - ``None`` when it may:
    it must cross each of them at :data:`SCATTER_CROSS_DEG` or steeper, a junction, or keep a
    section and its sand from it but for a root they share - the chooser's own two measures
    (:func:`fastcae.ribs.choose.relations`), so what is placed is never what it must thin."""
    import shapely

    gap = THICKNESS_MM + 2.0 * SAND_MM
    for there in kept:
        met = shapely.LineString(here).intersection(shapely.LineString(there))
        if not met.is_empty:
            point = met.geoms[0] if hasattr(met, "geoms") else met
            angle = 0.0
            if point.geom_type == "Point":
                angle = _crossing_deg(here, there, np.array([point.x, point.y]))
            if angle < SCATTER_CROSS_DEG:
                return f"crosses a fin already placed at {angle:.0f} degrees"
            continue
        far = np.linalg.norm(here[:, None, :] - there[None, :, :], axis=2)
        hinge = np.where(
            _judged(here, there, gap, ROOT_FREE),
            CLEAR_SOFT_MM * np.logaddexp(0.0, (gap - far) / CLEAR_SOFT_MM),
            0.0,
        )
        if float(hinge.sum()) / len(here) > SPACING_MM:
            return "crowds a fin already placed"
    return None


def _crossing_deg(here: np.ndarray, there: np.ndarray, at: np.ndarray) -> float:
    """The angle two runs cross at, each read where it passes nearest ``at``."""
    ways = []
    for pts in (here, there):
        k = int(np.argmin(np.linalg.norm(pts - at, axis=1)))
        t = pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]
        ways.append(t / max(float(np.linalg.norm(t)), 1e-9))
    return float(np.degrees(np.arccos(np.clip(abs(float(ways[0] @ ways[1])), 0.0, 1.0))))


SQUARE_SOFT_MM = 3.0
"""How softly an interior control point's reach is floored at nothing. A hard floor has a kink
exactly where the point sits on the wall, and a gradient either side of a kink is not one."""
