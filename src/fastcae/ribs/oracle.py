"""The feasibility oracle: every fin judged before any boolean runs, and every verdict carrying its
reason.

A fin that will not build is cheapest to refuse from its numbers, next cheapest from its outline on
its own sheet, and dearest of all at the fuse - which is where every earlier route found out. So
the oracle judges in stages, each on what is already known at that stage, and each stage's verdict
is recorded: a run's record then says, for every fin it seeded, why it was kept or dropped.

**On the numbers** (:func:`on_numbers`): a fin that has faded is said to be faded and not judged;
a fin whose middle runs alongside the metal with its face a hair from it is refused, because that
glancing contact is where the fuse leaves slivers; one mostly buried in the metal is not one rib;
one that turns tighter than its own section can be swept is refused, because its faces fold
through each other. Pairs closer than a section and the sand round it (:func:`pairs`) are not
verdicts but conflicts, for the chooser to settle.

**On the sheet** (:func:`on_sheet`): the floor under the run, read exactly on the section, must
be metal along nearly all of it, or the rib hangs over an opening; and (:func:`graze`) a rail of
the rib's outline - its top, its base, an end - that
runs **parallel** to an edge of the metal's section within a few millimetres of it, on either
side, or in a thin gap of air outside it. Measured on this housing: every face under 5 mm2 the fuse
left on the curved ribs sat where a top ran a millimetre or two under a wall's top edge, where a
base rose through the floor's face at a glance, or where a top ran just under a ceiling. Squarely
across an edge is fine; alongside it is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import shapely

from . import fins

BACKED_LEAST = 0.9
"""The least share of a fin's run that must have metal under it."""
TURN_LEAST_MM = 40.0
"""The tightest a run may turn, as a radius: twice its section. Tighter, the sheet offset to
either face folds through itself and no solid can be made of it."""
NEAR_MM = 2.0
"""A rail this near a parallel metal edge, on either side, is a graze: the faces all but coincide.
The plate library's own overlap rule - never on, or a hair from, a face of the part."""
FAR_MM = 6.0
"""A rail outside the metal, this near a parallel edge, is a graze: a thin gap of air the fuse
closes somewhere along it."""
PARALLEL = 0.85
"""How nearly parallel, as the cosine between the rail and the edge."""
SAMPLE_MM = 2.0
ALONGSIDE_MM = 10.0
"""The most of a rib's outline, in mm, that may run alongside the metal before it is refused."""
ENDS_MM = 3.0
"""How far in from each end of the run the outline is left unjudged: the root shoes there are the
attachment, drawn to be sunk, and are judged by their own rule."""
STRAY_MOST = 0.35
"""The most of a fin's middle that may lie inside the metal: past that it is not one rib but the
pieces of one. A rib through a boss is a rib; a run mostly buried is not."""


@dataclass
class Verdict:
    """One fin's verdict at one stage, with what was measured."""

    fin: str
    stage: str
    ok: bool
    reason: str = ""
    measured: dict[str, float] = field(default_factory=dict)

    def row(self) -> dict[str, Any]:
        return {
            "fin": self.fin,
            "stage": self.stage,
            "ok": self.ok,
            "reason": self.reason,
            "measured": {k: round(float(v), 4) for k, v in self.measured.items()},
        }


def turn(number: np.ndarray, rail: fins.Rail, other: fins.Rail) -> float:
    """The tightest radius the run turns at, in mm."""
    points, _ = fins.control(number, rail, other)
    s = np.linspace(0.0, 1.0, fins.PIECES + 1)
    t = 1.0 - s
    d1 = np.stack([-3 * t**2, 3 * t * (t - 2 * s), 3 * s * (2 * t - s), 3 * s**2], axis=-1)
    d2 = np.stack([6 * t, 6 * (s - 2 * t), 6 * (t - 2 * s), 6 * s], axis=-1)
    c1, c2 = d1 @ points, d2 @ points
    curve = (
        np.abs(c1[:, 0] * c2[:, 1] - c1[:, 1] * c2[:, 0])
        / np.maximum(np.linalg.norm(c1, axis=1), 1e-9) ** 3
    )
    return float(1.0 / max(float(curve.max()), 1e-9))


def side(
    number: np.ndarray, rail: fins.Rail, other: fins.Rail, inside: fins.Inside
) -> tuple[float, float]:
    """How far, in mm, a fin's middle runs **alongside** the metal with its face a hair from it -
    the gap between its face and the metal inside (-:data:`NEAR_MM`, :data:`FAR_MM`) while the run
    heads along the boundary rather than across it - and the share of its middle that lies inside
    the metal outright. Squarely across a wall the fuse merges cleanly; alongside it scallops."""
    pts, _ = fins.run(number, rail, other)
    edge = max(int(fins.ENDS_SHARE * len(pts)), 1)
    middle = slice(edge, len(pts) - edge)
    deep, slope = inside.deep(pts)
    step = np.gradient(pts, axis=0)
    step /= np.maximum(np.linalg.norm(step, axis=1, keepdims=True), 1e-9)
    normal = slope / np.maximum(np.linalg.norm(slope, axis=1, keepdims=True), 1e-9)
    across = np.abs(np.einsum("ij,ij->i", step, normal))
    gap = deep - 0.5 * fins.THICKNESS_MM
    alongside = (gap > -NEAR_MM) & (gap < FAR_MM) & (across < np.sqrt(1.0 - PARALLEL**2))
    spacing = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).mean())
    along_mm = float(alongside[middle].sum()) * spacing
    stray = float(np.mean(deep[middle] < 0.0))
    return along_mm, stray


def on_numbers(
    layout: fins.Layout, numbers: np.ndarray, fields_: dict[str, fins.Field], least: float = 0.5
) -> list[Verdict]:
    """Every fin's verdict from its numbers alone."""
    out: list[Verdict] = []
    for k, (name, (ia, ib), number) in enumerate(
        zip(layout.where, layout.ends, numbers, strict=True)
    ):
        fin = f"{name}:fin:{k}"
        presence = float(number[9])
        if presence < least:
            out.append(Verdict(fin, "numbers", False, f"faded out (presence {presence:.2f})"))
            continue
        f = fields_[name]
        rail, other = f.rails[ia], f.rails[ib]
        along, stray = side(number, rail, other, f.bare)
        radius = turn(number, rail, other)
        measured = {
            "alongside_mm": along,
            "stray": stray,
            "radius_mm": radius,
            "presence": presence,
        }
        if along > ALONGSIDE_MM:
            out.append(
                Verdict(
                    fin,
                    "numbers",
                    False,
                    f"runs alongside the metal for {along:.0f} mm of its middle, its face a "
                    f"hair from the wall",
                    measured,
                )
            )
            continue
        if stray > STRAY_MOST:
            out.append(
                Verdict(
                    fin,
                    "numbers",
                    False,
                    f"{stray:.0%} of its middle lies inside the metal: not one rib",
                    measured,
                )
            )
            continue
        if radius < TURN_LEAST_MM:
            out.append(
                Verdict(
                    fin,
                    "numbers",
                    False,
                    f"turns as tight as {radius:.0f} mm: its faces would fold",
                    measured,
                )
            )
            continue
        out.append(Verdict(fin, "numbers", True, "", measured))
    return out


def pairs(
    layout: fins.Layout,
    numbers: np.ndarray,
    fields_: dict[str, fins.Field],
    root_free: float = 0.0,
) -> set[tuple[int, int]]:
    """Pairs of fins that leave no room for sand between them - closer than a section plus twice
    :data:`.fins.SAND_MM` - whatever their presence. Conflicts, not verdicts: the chooser keeps
    one of each pair."""
    whole = np.array(numbers, float)
    whole[:, 9] = 1.0
    return {
        (i, j)
        for i, j, value, _ in fins.spacing(layout, whole, fields_, root_free=root_free)
        if value > fins.SPACING_MM
    }


def on_sheet(
    extraction: Any,
    found: Any,
    at: Any,
    tall: np.ndarray,
    fin: str,
    floor_required: bool = True,
    edges: Any = None,
) -> tuple[Verdict, Any]:
    """A fin's verdict from its outline on its own sheet, and that outline (a
    :class:`.curved.Offered`) when it has one: refused where no outline can be drawn - no room to
    stand, no wall to root in, space kept clear in the way - and where the outline it would have
    runs alongside the metal on any of its three sheets (:func:`graze`)."""
    from . import curved

    reasons: list[str] = []
    offered = curved.outline_on_sheet(extraction, found, at, tall, why=reasons, edges=edges)
    if offered is None:
        return Verdict(fin, "sheet", False, "; ".join(reasons) or "no outline"), None
    backed = float(offered.backed.mean()) if len(offered.backed) else 1.0
    # a volume picked from a floor stands its ribs on that floor; one picked between faces spans
    # them, and its ribs are held by their ends alone by design
    if floor_required and backed < BACKED_LEAST:
        return (
            Verdict(
                fin,
                "sheet",
                False,
                f"the floor under {1.0 - backed:.0%} of its run is open",
                {"backed": backed, "length_mm": float(at.length)},
            ),
            offered,
        )
    ends = (0.0, float(at.length))
    by_sheet = [graze(offered.ring, [m], ends=ends) for m in offered.profile.cut.metals]
    hits = [g for got in by_sheet for g in got]
    # the three sheets each see the same outline: the length is the worst sheet's, not the sum
    worst = max((alongside_mm(got) for got in by_sheet), default=0.0)
    measured = {
        "alongside_mm": worst,
        "graze_gap_mm": min((g["gap_mm"] for g in hits), default=float("inf")),
        "backed": backed,
        "length_mm": float(at.length),
    }
    if worst > ALONGSIDE_MM:
        where = sorted({round(g["s"] / max(at.length, 1e-9), 1) for g in hits})
        return (
            Verdict(
                fin,
                "sheet",
                False,
                f"runs alongside the metal for {worst:.0f} mm, nearest "
                f"{measured['graze_gap_mm']:.1f} mm, along its run at "
                f"{', '.join(f'{w:.0%}' for w in where)}",
                measured,
            ),
            offered,
        )
    return Verdict(fin, "sheet", True, "", measured), offered


def _samples(ring: Any, step: float) -> tuple[np.ndarray, np.ndarray]:
    """Points every ``step`` along a closed ring, and the unit tangent at each."""
    line = shapely.LineString(np.asarray(ring.coords))
    n = max(int(line.length / step), 8)
    at = np.linspace(0.0, line.length, n, endpoint=False)
    pts = np.asarray([[p.x, p.y] for p in (line.interpolate(float(a)) for a in at)])
    ahead = np.asarray([[p.x, p.y] for p in (line.interpolate(float(a + 0.5 * step)) for a in at)])
    behind = np.asarray(
        [[p.x, p.y] for p in (line.interpolate(float(max(a - 0.5 * step, 0.0))) for a in at)]
    )
    t = ahead - behind
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
    return pts, t


def alongside_mm(hits: list[dict[str, float]], step_mm: float = SAMPLE_MM) -> float:
    """How far, in mm, an outline runs alongside the metal: its flagged samples, by their step."""
    return float(len(hits)) * step_mm


def graze(
    ring: Any,
    metals: list[Any],
    near_mm: float = NEAR_MM,
    far_mm: float = FAR_MM,
    parallel: float = PARALLEL,
    step_mm: float = SAMPLE_MM,
    ends: tuple[float, float] | None = None,
) -> list[dict[str, float]]:
    """Where the outline ``ring`` runs alongside an edge of the metal: each sample of its boundary
    within ``near_mm`` of a parallel metal edge on either side, or within ``far_mm`` outside the
    metal. Each is ``{"s", "z", "gap_mm", "cos", "inside"}``. With ``ends`` - the run's two ends
    along the sheet - samples within :data:`ENDS_MM` of either, and beyond them, are the root
    shoes' and are not judged."""
    solids = [m for m in metals if m is not None and not m.is_empty]
    if not solids:
        return []
    metal = shapely.union_all(solids)
    edges = [
        shapely.LineString(np.asarray(r.coords))
        for poly in getattr(metal, "geoms", [metal])
        if poly.geom_type == "Polygon"
        for r in [poly.exterior, *poly.interiors]
    ]
    if not edges:
        return []
    pts, tangents = _samples(ring.exterior, step_mm)
    if ends is not None:
        judged = (pts[:, 0] > ends[0] + ENDS_MM) & (pts[:, 0] < ends[1] - ENDS_MM)
        pts, tangents = pts[judged], tangents[judged]
    inside = shapely.contains_xy(metal, pts[:, 0], pts[:, 1])
    out: list[dict[str, float]] = []
    for p, t, within in zip(pts, tangents, inside, strict=True):
        point = shapely.Point(p)
        edge = min(edges, key=lambda e: e.distance(point))
        gap = float(edge.distance(point))
        limit = near_mm if within else far_mm
        if gap > limit:
            continue
        along = float(edge.project(point))
        a = edge.interpolate(max(along - 1.0, 0.0))
        b = edge.interpolate(min(along + 1.0, edge.length))
        tb = np.array([b.x - a.x, b.y - a.y])
        tb /= max(float(np.linalg.norm(tb)), 1e-9)
        cos = abs(float(t @ tb))
        if cos < parallel:
            continue
        out.append(
            {
                "s": float(p[0]),
                "z": float(p[1]),
                "gap_mm": gap,
                "cos": cos,
                "inside": float(within),
            }
        )
    return out
