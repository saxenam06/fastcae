"""Formations: a few levers in, a set of ribs out.

A formation is drawn in the plane square to a zone's pull, across the zone's arc and radial band.
Every line it draws becomes a rib standing on the zone's base and rising along the pull; spokes and
grids draw straight lines, a web adds circular hoops. The ribs run a little past the band so they
reach into the walls either side; the composer trims them to the zone's own air, which is what
makes any pattern safe to draw.

Nothing here knows about a part. A formation sees a :class:`Region` - an axis, an arc, a band, a
base and a depth - and the same four formations draw on a gearbox ring, a flange or a bracket's web.

**Every lever has a step, and values snap to it.** A design's digest then stays stable, and a
sample cannot fill a campaign with designs that differ by a hundredth of a degree.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from .ribs import ArcRib, Rib

__all__ = ["FORMATIONS", "ArcRib", "Formation", "Lever", "Made", "Region", "build"]

# How far past the band a line runs, so its rib ends inside the wall rather than short of it.
REACH_PAST_MM = 20.0

# The step along a line when cutting it to the region. Fine enough that a rib's end lands within a
# millimetre of where the region's edge is.
_CUT_STEP_MM = 1.0


@dataclass(frozen=True)
class Region:
    """Where a formation is drawn: an arc of an annulus about an axis, and how ribs stand in it.

    ``base_mm`` is the level along ``axis`` from ``centre`` that ribs stand on; they rise along
    ``pull`` - which is the axis, or its reverse for ribs hanging from a ceiling - by up to
    ``depth_mm``. Angles are measured about the axis from the direction of world x projected onto
    the plane (world y where x is the axis).
    """

    centre: tuple[float, float, float]
    axis: tuple[float, float, float]
    theta_from_deg: float
    theta_to_deg: float
    r_inner_mm: float
    r_outer_mm: float
    base_mm: float
    depth_mm: float
    pull: tuple[float, float, float]

    def frame(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """The point on the axis at the base, and the plane's two directions and its normal."""
        axis = np.asarray(self.axis, dtype=float)
        axis = axis / np.linalg.norm(axis)
        seed = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        e1 = seed - (seed @ axis) * axis
        e1 = e1 / np.linalg.norm(e1)
        e2 = np.cross(axis, e1)
        origin = np.asarray(self.centre, dtype=float) + self.base_mm * axis
        return origin, e1, e2, axis

    @property
    def span_deg(self) -> float:
        return (self.theta_to_deg - self.theta_from_deg) % 360.0 or 360.0

    def contains(self, x: np.ndarray, y: np.ndarray, reach: float) -> np.ndarray:
        """Whether plane points lie in the arc, and in the band grown by ``reach`` either side."""
        r = np.hypot(x, y)
        theta = (np.degrees(np.arctan2(y, x)) - self.theta_from_deg) % 360.0
        return (
            (r >= self.r_inner_mm - reach)
            & (r <= self.r_outer_mm + reach)
            & (theta <= self.span_deg)
        )


@dataclass(frozen=True)
class Lever:
    """One number a person or a sampler sets."""

    name: str
    label: str
    low: float
    high: float
    step: float
    unit: str = ""
    integer: bool = False

    def snap(self, value: float) -> float:
        snapped = round(math.floor(value / self.step + 0.5) * self.step, 6)
        return int(snapped) if self.integer else snapped


SHARED_LEVERS = (
    Lever("thickness_mm", "Thickness", 15.0, 25.0, 0.5, "mm"),
    Lever("height", "Height", 0.5, 1.0, 0.02, "of the zone's depth"),
)


@dataclass(frozen=True)
class Made:
    """What a formation produced: its ribs, and how many pieces were too short to be ribs."""

    ribs: tuple
    dropped: int = 0


@dataclass(frozen=True)
class Formation:
    name: str
    label: str
    own: tuple[Lever, ...]
    draw: Callable[[Region, dict], tuple[list, int]] = field(compare=False)

    @property
    def levers(self) -> tuple[Lever, ...]:
        return (*self.own, *SHARED_LEVERS)

    def snap(self, values: dict) -> dict:
        by_name = {lever.name: lever for lever in self.levers}
        return {
            name: by_name[name].snap(value) for name, value in values.items() if name in by_name
        }


def build(name: str, region: Region, values: dict, **rib_options) -> Made:
    """The ribs a formation draws in a region, from lever values. Values snap to their steps first.

    ``rib_options`` - draft and edge round - are the same for every rib, from the casting rules.
    """
    formation = FORMATIONS[name]
    snapped = formation.snap(values)
    for lever in formation.levers:
        if lever.name not in snapped:
            raise ValueError(f"{lever.name} was not given")
        if not lever.low <= snapped[lever.name] <= lever.high:
            raise ValueError(
                f"{lever.name} = {snapped[lever.name]} is outside {lever.low} to {lever.high}"
            )
    lines, dropped = formation.draw(region, snapped)
    ribs = tuple(_rib(region, line, snapped, rib_options) for line in lines)
    return Made(ribs=ribs, dropped=dropped)


# --- drawing ------------------------------------------------------------------------------------


def _spokes(region: Region, v: dict) -> tuple[list, int]:
    return [_spoke(region, a, v["skew_deg"]) for a in _spoke_angles(region, v)], 0


def _web(region: Region, v: dict) -> tuple[list, int]:
    lines = [_spoke(region, a, 0.0) for a in _spoke_angles(region, v)]
    band = region.r_outer_mm - region.r_inner_mm
    hoops = int(v["hoops"])
    lines += [("arc", region.r_inner_mm + k * band / (hoops + 1)) for k in range(1, hoops + 1)]
    return lines, 0


def _square_grid(region: Region, v: dict) -> tuple[list, int]:
    alpha = math.radians(v["angle_deg"])
    shift = v["offset"] * v["spacing_mm"] * math.sqrt(2.0)
    centre = shift * np.array([math.cos(alpha + math.pi / 4), math.sin(alpha + math.pi / 4)])
    return _families(region, centre, v["spacing_mm"], [alpha, alpha + math.pi / 2], v)


def _triangle_grid(region: Region, v: dict) -> tuple[list, int]:
    alpha = math.radians(v["angle_deg"])
    centre = v["offset"] * v["spacing_mm"] * np.array([math.cos(alpha), math.sin(alpha)])
    # Normals 120 degrees apart sum to zero, so every crossing is a crossing of all three families
    # and the cells are triangles, not the triangles-and-hexagons a free offset per family gives.
    directions = [alpha, alpha + 2 * math.pi / 3, alpha + 4 * math.pi / 3]
    return _families(region, centre, v["spacing_mm"], directions, v)


def _spoke_angles(region: Region, v: dict) -> list[float]:
    n = int(v["count"])
    step = region.span_deg / n
    return [region.theta_from_deg + (i + v["phase"]) * step for i in range(n)]


def _spoke(region: Region, angle_deg: float, skew_deg: float) -> tuple:
    theta, psi = math.radians(angle_deg), math.radians(skew_deg)
    middle = (region.r_inner_mm + region.r_outer_mm) / 2.0
    point = middle * np.array([math.cos(theta), math.sin(theta)])
    direction = np.array([math.cos(theta + psi), math.sin(theta + psi)])
    half = (region.r_outer_mm - region.r_inner_mm) / 2.0 / math.cos(psi) + REACH_PAST_MM
    return ("line", point - half * direction, point + half * direction)


def _families(
    region: Region, centre: np.ndarray, spacing: float, directions: list[float], v: dict
) -> tuple[list, int]:
    """Parallel lines at ``spacing`` in each direction through the lattice about ``centre``, cut to
    the region. Pieces shorter than twice the rib's thickness are dropped and counted."""
    reach = region.r_outer_mm + REACH_PAST_MM
    shortest = 2.0 * v["thickness_mm"]
    lines, dropped = [], 0
    for angle in directions:
        d = np.array([math.cos(angle), math.sin(angle)])
        n = np.array([-d[1], d[0]])
        base = centre @ n
        first = math.floor((-reach - base) / spacing)
        last = math.ceil((reach - base) / spacing)
        for j in range(first, last + 1):
            offset = base + j * spacing
            if abs(offset) >= reach:
                continue
            half = math.sqrt(reach * reach - offset * offset)
            for a, b in _runs(region, offset * n, d, half):
                if np.linalg.norm(b - a) < shortest:
                    dropped += 1
                else:
                    lines.append(("line", a, b))
    return lines, dropped


def _runs(region: Region, foot: np.ndarray, d: np.ndarray, half: float) -> list:
    """The stretches of the line ``foot + t d``, ``|t| <= half``, that lie in the region."""
    t = np.arange(-half, half + _CUT_STEP_MM, _CUT_STEP_MM)
    points = foot[None, :] + t[:, None] * d[None, :]
    inside = region.contains(points[:, 0], points[:, 1], REACH_PAST_MM)
    runs = []
    edges = np.flatnonzero(np.diff(np.concatenate([[0], inside.astype(int), [0]])))
    for start, stop in zip(edges[0::2], edges[1::2], strict=True):
        runs.append((points[start], points[stop - 1]))
    return runs


def _rib(region: Region, line: tuple, v: dict, options: dict):
    origin, e1, e2, axis = region.frame()
    height = v["height"] * region.depth_mm
    common = {
        "thickness_mm": v["thickness_mm"],
        "height_mm": height,
        "pull": tuple(float(c) for c in region.pull),
        **options,
    }
    if line[0] == "arc":
        return ArcRib(
            centre=tuple(float(c) for c in origin),
            axis=tuple(float(c) for c in axis),
            reference=tuple(float(c) for c in e1),
            radius_mm=float(line[1]),
            theta_from_deg=region.theta_from_deg,
            theta_to_deg=region.theta_to_deg,
            **common,
        )
    _, a, b = line
    start = origin + a[0] * e1 + a[1] * e2
    end = origin + b[0] * e1 + b[1] * e2
    return Rib(start=tuple(float(c) for c in start), end=tuple(float(c) for c in end), **common)


FORMATIONS: dict[str, Formation] = {
    f.name: f
    for f in (
        Formation(
            "spokes",
            "Spokes",
            (
                Lever("count", "Count", 3, 12, 1, "", integer=True),
                Lever("phase", "Rotation", 0.0, 1.0, 0.02, "of a pitch"),
                Lever("skew_deg", "Skew", -30.0, 30.0, 1.0, "deg"),
            ),
            _spokes,
        ),
        Formation(
            "web",
            "Web",
            (
                Lever("count", "Spokes", 3, 10, 1, "", integer=True),
                Lever("phase", "Rotation", 0.0, 1.0, 0.02, "of a pitch"),
                Lever("hoops", "Hoops", 1, 3, 1, "", integer=True),
            ),
            _web,
        ),
        Formation(
            "square_grid",
            "Square grid",
            (
                Lever("spacing_mm", "Spacing", 80.0, 240.0, 5.0, "mm"),
                Lever("angle_deg", "Angle", 0.0, 90.0, 1.0, "deg"),
                Lever("offset", "Offset", 0.0, 1.0, 0.02, "of a spacing"),
            ),
            _square_grid,
        ),
        Formation(
            "triangle_grid",
            "Triangle grid",
            (
                Lever("spacing_mm", "Spacing", 100.0, 300.0, 5.0, "mm"),
                Lever("angle_deg", "Angle", 0.0, 60.0, 1.0, "deg"),
                Lever("offset", "Offset", 0.0, 1.0, 0.02, "of a spacing"),
            ),
            _triangle_grid,
        ),
    )
}
