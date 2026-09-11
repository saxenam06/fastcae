"""Zones: where ribs may go, proposed from the material a person removed.

When a project names a reference, ``reference - baseline`` is the material deleted to make the
baseline. Where it was is where ribs are known to fit. Each connected piece of it is placed about
the nearest detected axis, pieces on one axis at overlapping levels are grouped, and each group is
proposed as a zone: the arc of an annulus the pieces cover, their radial band, their levels, and
which way ribs attach.

**Which way ribs attach** is read off the part, not assumed. Just past the pieces' top level and
just below their bottom, the baseline is either metal or air over the pieces' own footprint.
Metal above means ribs hang from a ceiling; metal below, they stand on a floor; neither, they span
between the walls either side.

A proposal is only that: a person approves a zone before any lever for it exists.

**A zone's window** holds what composing ribs into it needs and a design never changes: the part's
exact distance and normals out to the widest fillet, the protected cells, and the zone's own air.
The air is found by flooding through empty cells from the zone's core, so a rib drawn across the
zone reaches into the walls either side and never through one to the outside.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
from scipy import ndimage

from ..geometry.brep import Tessellation
from .compose import Window, margin_for, window_between
from .field import Field
from .formations import REACH_PAST_MM, Region

# Pieces of removed material smaller than this are left out: the sliver where a patched surface
# met a fillet is not a place a rib was.
SMALLEST_PIECE_MM3 = 20_000.0

# Angular slack past the outermost removed piece, as a fraction of the arc it covers.
ARC_SLACK = 0.05


@dataclass(frozen=True)
class Zone:
    """Where ribs may go, and how they attach there."""

    id: str
    label: str
    region: Region
    host: str
    """``below`` - ribs stand on a floor; ``above`` - they hang from a ceiling; ``between`` - they
    span the gap between walls, free at both ends of the pull."""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "host": self.host,
            "region": asdict(self.region),
        }

    @staticmethod
    def from_dict(data: dict) -> Zone:
        region = {k: tuple(v) if isinstance(v, list) else v for k, v in data["region"].items()}
        return Zone(id=data["id"], label=data["label"], host=data["host"], region=Region(**region))


def propose(
    baseline: Field,
    reference: Field,
    axes: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
) -> list[Zone]:
    """Zones for the material ``reference`` has and ``baseline`` does not, about the given axes."""
    if baseline.grid != reference.grid:
        raise ValueError("the baseline and the reference were not sampled on the same grid")
    spacing = baseline.grid.spacing_mm
    removed = reference.inside & ~baseline.inside
    labels, count = ndimage.label(removed, structure=np.ones((3, 3, 3), dtype=bool))
    if not count:
        return []
    sizes = np.bincount(labels.ravel(), minlength=count + 1)
    smallest = SMALLEST_PIECE_MM3 / spacing**3

    pieces = []
    for label in range(1, count + 1):
        if sizes[label] < smallest:
            continue
        cells = np.flatnonzero(labels.ravel() == label)
        points = baseline.grid.centres(cells)
        axis = _axis_of(points, axes)
        t = (points - np.asarray(axes[axis][0])) @ _unit(axes[axis][1])
        pieces.append({"axis": axis, "points": points, "lo": float(t.min()), "hi": float(t.max())})

    groups: list[list[dict]] = []
    for piece in sorted(pieces, key=lambda p: (p["axis"], p["lo"])):
        last = groups[-1] if groups else None
        if last and last[0]["axis"] == piece["axis"] and piece["lo"] <= max(p["hi"] for p in last):
            last.append(piece)
        else:
            groups.append([piece])
    groups = _merge_strays(groups, axes)

    zones = []
    for number, group in enumerate(groups, 1):
        point, direction = axes[group[0]["axis"]]
        region, host = _region(
            baseline, np.concatenate([p["points"] for p in group]), point, direction
        )
        zones.append(Zone(id=f"zone-{number}", label=f"Zone {number}", region=region, host=host))
    return zones


def major_axes(axes: list, fraction: float = 0.1) -> list[tuple[tuple, tuple]]:
    """The axes worth proposing zones about: those carrying at least ``fraction`` of the surface
    the largest one carries.

    Feature detection finds an axis for every hole, and a rib's mid-plane contains any number of
    them by accident. The axes a part is built around - its shafts, its main bores - carry far more
    surface than a bolt hole does; on the part in ``assets/`` the three shaft axes carry 100%, 59%
    and 24% of the largest, and the next carries 3%. Relative, so it holds at any part's scale.
    """
    if not axes:
        return []
    largest = max(a.area_mm2 for a in axes)
    ranked = sorted(axes, key=lambda a: -a.area_mm2)
    return [
        (tuple(float(v) for v in a.point), tuple(float(v) for v in a.direction))
        for a in ranked
        if a.area_mm2 >= fraction * largest
    ]


def _merge_strays(groups: list[list[dict]], axes: list) -> list[list[dict]]:
    """A lone piece whose levels a larger group shares joins that group.

    A piece that is no plain plate - a rib that branches, a pad - can only have its axis guessed by
    distance, and a neighbouring axis may be nearer. Standing at the same levels as a group of
    ribs round another axis, it is one of them.
    """
    groups = sorted(groups, key=len, reverse=True)
    kept: list[list[dict]] = []
    for group in groups:
        if len(group) == 1 and kept:
            piece = group[0]
            for host in kept:
                point, direction = axes[host[0]["axis"]]
                t = (piece["points"] - np.asarray(point)) @ _unit(direction)
                lo = min(p["lo"] for p in host)
                hi = max(p["hi"] for p in host)
                if t.min() <= hi and t.max() >= lo:
                    host.append(
                        {
                            **piece,
                            "axis": host[0]["axis"],
                            "lo": float(t.min()),
                            "hi": float(t.max()),
                        }
                    )
                    break
            else:
                kept.append(group)
        else:
            kept.append(group)
    return sorted(kept, key=lambda g: min(p["lo"] for p in g))


def window_for(
    base: Field,
    tess: Tessellation,
    zone: Zone,
    radius_mm: float,
    protected_faces: set[int] | None = None,
    clearance_mm: float = 5.0,
) -> Window:
    """What composing ribs into ``zone`` needs that no design changes. See the module note."""
    region = zone.region
    margin = margin_for(base, radius_mm)
    origin, e1, e2, axis = region.frame()
    up = np.asarray(region.pull, dtype=float)

    # The box: the band grown by how far ribs reach past it, over the arc, base to full depth.
    angles = np.radians(region.theta_from_deg + np.linspace(0.0, region.span_deg, 181))
    reach = region.r_outer_mm + REACH_PAST_MM
    ring = [0.0, max(region.r_inner_mm - REACH_PAST_MM, 0.0), reach]
    corners = [
        origin + r * (math.cos(a) * e1 + math.sin(a) * e2) + h * up
        for a in angles
        for r in ring
        for h in (0.0, region.depth_mm)
    ]
    corners = np.asarray(corners)
    window = window_between(
        base,
        tess,
        corners.min(axis=0),
        corners.max(axis=0),
        margin,
        protected_faces=protected_faces,
        clearance_mm=clearance_mm,
        region=region,
    )
    window.allowed = _zone_air(base, window, region)
    return window


def _zone_air(base: Field, window: Window, region: Region) -> np.ndarray:
    """The zone's own air, and one voxel of the metal around it.

    Flooded through empty cells from the zone's core - its arc, band and levels - staying inside the
    band grown by how far ribs reach past it. Air on the far side of a wall is never reached.
    """
    origin, e1, e2, axis = region.frame()
    up = np.asarray(region.pull, dtype=float)
    points = window.grid.centres(np.arange(window.grid.n_cells)) - origin
    x, y = points @ e1, points @ e2
    h = points @ up
    level = (h >= -window.grid.spacing_mm) & (h <= region.depth_mm + window.grid.spacing_mm)
    solid = base.inside.ravel()[window.samples_of(np.arange(window.grid.n_cells))]

    candidate = ~solid & level & region.contains(x, y, REACH_PAST_MM)
    core = candidate & region.contains(x, y, 0.0)
    labels, _ = ndimage.label(candidate.reshape(window.grid.shape))
    keep = np.unique(labels.ravel()[core])
    air = np.isin(labels.ravel(), keep[keep > 0])

    grown = ndimage.binary_dilation(air.reshape(window.grid.shape)).ravel()
    return air | (grown & solid)


def _region(
    baseline: Field, points: np.ndarray, point: tuple, direction: tuple
) -> tuple[Region, str]:
    """The arc, band and levels a group of removed pieces covers, and which way ribs attach."""
    spacing = baseline.grid.spacing_mm
    axis = _unit(direction)
    probe = Region(point, tuple(axis), 0.0, 360.0, 0.0, 1.0, 0.0, 1.0, tuple(axis))
    origin, e1, e2, _ = probe.frame()
    p = points - np.asarray(point, dtype=float)
    t = p @ axis
    x, y = p @ e1, p @ e2
    r = np.hypot(x, y)
    r_in, r_out = float(r.min()), float(r.max())

    # The arc is measured where the pieces are widest apart in angle for the least reason to be -
    # across the middle of the band, not at the inner edge where a thin rib subtends many degrees.
    middle = (r > r_in + 0.25 * (r_out - r_in)) & (r < r_out - 0.25 * (r_out - r_in))
    theta = np.sort(np.degrees(np.arctan2(y[middle], x[middle])) % 360.0)
    gaps = np.diff(np.concatenate([theta, [theta[0] + 360.0]]))
    widest = int(np.argmax(gaps))
    start = theta[(widest + 1) % theta.size]
    span = 360.0 - gaps[widest]
    if gaps[widest] < 30.0:
        start, span = 0.0, 360.0
    else:
        slack = ARC_SLACK * span
        start, span = start - slack, min(span + 2 * slack, 360.0)

    lo, hi = float(t.min()), float(t.max())
    above = _solid_fraction(baseline, point, axis, x, y, e1, e2, hi + 1.5 * spacing)
    below = _solid_fraction(baseline, point, axis, x, y, e1, e2, lo - 1.5 * spacing)
    embed = spacing
    if above > 0.5 and above >= below:
        host, base, pull, depth = "above", hi + embed, -axis, hi - lo + embed
    elif below > 0.5:
        host, base, pull, depth = "below", lo - embed, axis, hi - lo + embed
    else:
        host, base, pull, depth = "between", lo, axis, hi - lo

    region = Region(
        centre=tuple(float(v) for v in point),
        axis=tuple(float(v) for v in axis),
        theta_from_deg=float(start % 360.0),
        theta_to_deg=float((start + span) % 360.0) if span < 360.0 else float(start % 360.0),
        r_inner_mm=r_in,
        r_outer_mm=r_out,
        base_mm=float(base),
        depth_mm=float(depth),
        pull=tuple(float(v) for v in pull),
    )
    return region, host


def _solid_fraction(baseline, point, axis, x, y, e1, e2, level) -> float:
    """How much of the pieces' footprint is metal at one level along the axis."""
    points = np.asarray(point) + level * axis + np.outer(x, e1) + np.outer(y, e2)
    return float((baseline.sample(points) < 0.0).mean())


def _axis_of(points: np.ndarray, axes: list) -> int:
    """The axis a removed piece belongs to.

    Not the nearest one: a rib runs out from its axis, so its middle is far from it by design, and
    a neighbouring axis can easily be closer. A rib is a plate, and a radial rib's plate *contains*
    its axis - so for a plate-shaped piece, the axis is the one lying in its mid-plane. Anything
    else falls back to the axis nearest its middle.
    """
    centre = points.mean(axis=0)
    values, vectors = np.linalg.eigh(np.cov((points - centre).T))
    plate = values[0] < 0.25 * values[1]
    normal = vectors[:, 0]

    best, best_score = 0, math.inf
    for index, (point, direction) in enumerate(axes):
        d = _unit(direction)
        offset = np.asarray(point, dtype=float) - centre
        if plate:
            # Off the plane in angle (weighted by the piece's size) and in position.
            score = abs(normal @ d) * math.sqrt(values[-1]) + abs(normal @ offset)
        else:
            score = float(np.linalg.norm(offset - (offset @ d) * d))
        if score < best_score:
            best, best_score = index, score
    return best


def _unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)
