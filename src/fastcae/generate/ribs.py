"""A rib, as an exact distance function, and the blend that joins it to a part with a root fillet.

**A rib is a plate on a line.** Its line lies in the plane its formation is drawn in; it is extruded
along the pull direction - the way the mould opens - to its height, and it is ``thickness`` across.
Its top may slope, straight from one end's height to the other's.
Draft closes the flanks in with height, as a casting needs to leave its mould; the free edges are
rounded. The ends are flat, because a rib ends inside a wall or boss and is trimmed there; nothing
of an end is ever seen.

**The root fillet comes from the union, not from a feature.** A rolling ball of radius R wedged
between two surfaces touches each of them where the other is ``R * (1 - n_a . n_b)`` away - exactly
``R`` when they meet square. The round blend

    k = R * (1 - n_a . n_b)
    d = max(k, min(a, b)) - |(max(k - a, 0), max(k - b, 0))|

touches both surfaces at exactly those points, and is a circle of radius R where they meet square.
Where they meet at another angle the curve between the two touch points is not quite circular, and
how far that matters is measured rather than assumed. It changes the field only where both ``a`` and
``b`` are below ``k``, which is at a junction and nowhere else: a part's own edges are never
rounded.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


def _section(
    t: np.ndarray,
    h: np.ndarray,
    thickness: float,
    height: float | np.ndarray,
    draft_deg: float,
    rho: float,
    top_scale: float = 1.0,
) -> np.ndarray:
    """Signed distance in a rib's cross-section: a drafted rectangle, its top corners rounded.

    ``t`` is the offset across the rib from its mid-plane, ``h`` the height up the pull from its
    root. Shared by every rib, straight or curved, so they all have one section. ``height`` may
    vary point by point, for a top that slopes along the rib; ``top_scale`` turns a height above
    that top into a distance to it.
    """
    slope = math.tan(math.radians(draft_deg))
    cos = math.cos(math.radians(draft_deg))
    half = thickness / 2.0
    rho = min(rho, half * 0.999, float(np.min(height)) / 2.0)

    flank = (np.abs(t) - (half - h * slope)) * cos
    top = (h - height) * top_scale
    bottom = -h
    vertical = np.maximum(top, bottom)
    if rho > 0.0:
        qx, qy = flank + rho, top + rho
        rounded = (
            np.hypot(np.maximum(qx, 0.0), np.maximum(qy, 0.0))
            + np.minimum(np.maximum(qx, qy), 0.0)
            - rho
        )
        section = np.where(h > height - rho, rounded, np.maximum(flank, vertical))
        return np.maximum(section, bottom)
    section = np.maximum(flank, vertical)
    outside = np.hypot(np.maximum(flank, 0.0), np.maximum(vertical, 0.0))
    return np.where((flank > 0.0) & (vertical > 0.0), outside, section)


def _extruded(section: np.ndarray, ends: np.ndarray) -> np.ndarray:
    """A section swept along a path, with flat ends: ``ends`` is the distance past either end."""
    inner = np.minimum(np.maximum(section, ends), 0.0)
    outer = np.hypot(np.maximum(section, 0.0), np.maximum(ends, 0.0))
    return inner + outer


class _Shape:
    """What every rib offers the composer: a distance, its normal, and a box it fits in."""

    def distance(self, points: np.ndarray) -> np.ndarray:  # pragma: no cover - overridden
        raise NotImplementedError

    def normal(self, points: np.ndarray, step_mm: float = 1e-3) -> np.ndarray:
        """Unit gradient of the distance, by central differences."""
        points = np.asarray(points, dtype=float)
        grad = np.empty_like(points)
        for axis in range(3):
            offset = np.zeros(3)
            offset[axis] = step_mm
            grad[:, axis] = self.distance(points + offset) - self.distance(points - offset)
        length = np.linalg.norm(grad, axis=1, keepdims=True)
        return np.divide(grad, length, out=np.zeros_like(grad), where=length > 0.0)


def _flange(t: np.ndarray, h: np.ndarray, width: float, thickness: float, height, rho: float):
    """Signed distance in a flange's cross-section: a bar ``width`` across and ``thickness`` deep,
    its top at ``height``, its corners rounded by ``rho``."""
    rho = min(rho, width / 2.0 * 0.999, thickness / 2.0 * 0.999)
    qx = np.abs(t) - width / 2.0 + rho
    qy = np.abs(h - (height - thickness / 2.0)) - thickness / 2.0 + rho
    outside = np.hypot(np.maximum(qx, 0.0), np.maximum(qy, 0.0))
    return outside + np.minimum(np.maximum(qx, qy), 0.0) - rho


@dataclass(frozen=True)
class Rib(_Shape):
    """A drafted plate standing on a line - or, with a flange, a T.

    ``start`` and ``end`` are the line's two ends, on the face or level the rib stands on. The rib
    rises from there along ``pull`` by ``height_mm``, ``thickness_mm`` across at its root. With
    ``end_height_mm`` its top slopes, straight, from ``height_mm`` at its start to that at its end.
    With ``flange_width_mm`` wider than the web, a flange ``flange_thickness_mm`` deep runs along
    its top, following the slope: the rib is a T.
    """

    start: tuple[float, float, float]
    end: tuple[float, float, float]
    thickness_mm: float
    height_mm: float
    pull: tuple[float, float, float] = (0.0, 0.0, 1.0)
    draft_deg: float = 0.0
    edge_round_mm: float = 0.0
    end_height_mm: float | None = None
    flange_width_mm: float = 0.0
    flange_thickness_mm: float = 0.0

    @property
    def tee(self) -> bool:
        return self.flange_width_mm > self.thickness_mm and self.flange_thickness_mm > 0.0

    @property
    def width_mm(self) -> float:
        """How wide it is at its widest: the flange, for a T."""
        return self.flange_width_mm if self.tee else self.thickness_mm

    @property
    def heights(self) -> tuple[float, float]:
        """How tall it is at its start and at its end."""
        end = self.height_mm if self.end_height_mm is None else self.end_height_mm
        return self.height_mm, end

    def height_at(self, fraction: np.ndarray) -> np.ndarray:
        """How tall it is a fraction of the way along its line, from its start."""
        low, high = self.heights
        return low + (high - low) * np.clip(np.asarray(fraction, dtype=float), 0.0, 1.0)

    def frame(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
        """Origin; unit axes along the line, across it and up the pull; and the line's length."""
        up = np.asarray(self.pull, dtype=float)
        up = up / np.linalg.norm(up)
        origin = np.asarray(self.start, dtype=float)
        line = np.asarray(self.end, dtype=float) - origin
        line = line - (line @ up) * up
        length = float(np.linalg.norm(line))
        if length <= 0.0:
            raise ValueError("a rib's line has no length across the pull direction")
        along = line / length
        across = np.cross(up, along)
        return origin, along, across, up, length

    def distance(self, points: np.ndarray) -> np.ndarray:
        """Signed distance from each point, negative inside."""
        origin, along, across, up, length = self.frame()
        p = np.asarray(points, dtype=float) - origin
        s, t, h = p @ along, p @ across, p @ up
        low, high = self.heights
        rise = (high - low) / length
        height = self.height_at(s / length) if rise else self.height_mm
        section = _section(
            t,
            h,
            self.thickness_mm,
            height,
            self.draft_deg,
            self.edge_round_mm,
            top_scale=1.0 / math.sqrt(1.0 + rise * rise),
        )
        if self.tee:
            flange = _flange(
                t,
                h,
                self.flange_width_mm,
                min(self.flange_thickness_mm, float(np.min(height))),
                height,
                self.edge_round_mm,
            )
            section = np.minimum(section, flange)
        return _extruded(section, np.abs(s - length / 2.0) - length / 2.0)

    def plan_near(self, points: np.ndarray, margin_mm: float) -> np.ndarray:
        """Whether points are within ``margin_mm`` of the rib seen along its pull."""
        origin, along, across, _, length = self.frame()
        p = np.asarray(points, dtype=float) - origin
        s, t = p @ along, p @ across
        return (
            (s >= -margin_mm)
            & (s <= length + margin_mm)
            & (np.abs(t) <= self.width_mm / 2.0 + margin_mm)
        )

    def bounds(self, margin_mm: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
        """The axis-aligned box holding the rib, grown by ``margin_mm``."""
        origin, along, across, up, length = self.frame()
        half = self.width_mm / 2.0
        heights = self.heights
        corners = np.array(
            [
                origin + a * along * length + b * across * half + c * up * heights[a]
                for a in (0, 1)
                for b in (-1, 1)
                for c in (0, 1)
            ]
        )
        return corners.min(axis=0) - margin_mm, corners.max(axis=0) + margin_mm


@dataclass(frozen=True)
class ArcRib(_Shape):
    """A drafted plate standing on a circular arc: the hoop of a web.

    ``centre`` is on the arc's axis, at the level the rib stands on. Angles are measured about
    ``axis`` from ``reference``, the direction of zero.
    """

    centre: tuple[float, float, float]
    axis: tuple[float, float, float]
    reference: tuple[float, float, float]
    radius_mm: float
    theta_from_deg: float
    theta_to_deg: float
    thickness_mm: float
    height_mm: float
    pull: tuple[float, float, float] = (0.0, 0.0, 1.0)
    draft_deg: float = 0.0
    edge_round_mm: float = 0.0

    def height_at(self, fraction: np.ndarray) -> np.ndarray:
        """How tall it is a fraction of the way along its arc: the same everywhere."""
        return np.full(np.shape(fraction), self.height_mm, dtype=float)

    def _frame(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        axis = np.asarray(self.axis, dtype=float)
        axis = axis / np.linalg.norm(axis)
        e1 = np.asarray(self.reference, dtype=float)
        e1 = e1 - (e1 @ axis) * axis
        e1 = e1 / np.linalg.norm(e1)
        e2 = np.cross(axis, e1)
        up = np.asarray(self.pull, dtype=float)
        return np.asarray(self.centre, dtype=float), axis, e1, e2, up / np.linalg.norm(up)

    def distance(self, points: np.ndarray) -> np.ndarray:
        centre, axis, e1, e2, up = self._frame()
        p = np.asarray(points, dtype=float) - centre
        h = p @ up
        x, y = p @ e1, p @ e2
        r = np.hypot(x, y)
        section = _section(
            r - self.radius_mm,
            h,
            self.thickness_mm,
            self.height_mm,
            self.draft_deg,
            self.edge_round_mm,
        )
        span = (self.theta_to_deg - self.theta_from_deg) % 360.0 or 360.0
        middle = math.radians(self.theta_from_deg + span / 2.0)
        off = np.abs((np.arctan2(y, x) - middle + math.pi) % (2.0 * math.pi) - math.pi)
        ends = self.radius_mm * (off - math.radians(span / 2.0))
        return _extruded(section, ends)

    def plan_near(self, points: np.ndarray, margin_mm: float) -> np.ndarray:
        """Whether points are within ``margin_mm`` of the arc seen along its pull."""
        centre, _, e1, e2, _ = self._frame()
        p = np.asarray(points, dtype=float) - centre
        x, y = p @ e1, p @ e2
        r = np.hypot(x, y)
        span = (self.theta_to_deg - self.theta_from_deg) % 360.0 or 360.0
        middle = math.radians(self.theta_from_deg + span / 2.0)
        off = np.abs((np.arctan2(y, x) - middle + math.pi) % (2.0 * math.pi) - math.pi)
        slack = margin_mm / max(self.radius_mm, 1e-9)
        return (np.abs(r - self.radius_mm) <= self.thickness_mm / 2.0 + margin_mm) & (
            off <= math.radians(span / 2.0) + slack
        )

    def bounds(self, margin_mm: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
        centre, axis, e1, e2, up = self._frame()
        span = (self.theta_to_deg - self.theta_from_deg) % 360.0 or 360.0
        angles = np.radians(self.theta_from_deg + np.linspace(0.0, span, 73))
        half = self.thickness_mm / 2.0
        points = [
            centre + (self.radius_mm + dr) * (np.cos(a) * e1 + np.sin(a) * e2) + dh * up
            for a in angles
            for dr in (-half, half)
            for dh in (0.0, self.height_mm)
        ]
        points = np.asarray(points)
        return points.min(axis=0) - margin_mm, points.max(axis=0) + margin_mm


def round_union(
    a: np.ndarray, n_a: np.ndarray, b: np.ndarray, n_b: np.ndarray, radius_mm: float
) -> np.ndarray:
    """The union of two solids, rounded where they meet as a ball of ``radius_mm`` would round it.

    ``a`` and ``b`` are signed distances to the two solids at the same points, ``n_a`` and ``n_b``
    their unit normals there. See the module note for where it touches and where it changes nothing.
    """
    cosine = np.clip(np.einsum("ij,ij->i", n_a, n_b), -1.0, 1.0)
    k = radius_mm * (1.0 - cosine)
    u = np.maximum(k - a, 0.0)
    w = np.maximum(k - b, 0.0)
    blended = np.maximum(k, np.minimum(a, b)) - np.hypot(u, w)
    # Where either surface is out of reach the blend *is* the plain union, and saying so exactly
    # rather than as k - (k - a) keeps every untouched cell bit-for-bit what it was - which is what
    # lets a design be spliced into its base without everything near the part counting as changed.
    return np.where((a >= k) | (b >= k), np.minimum(a, b), blended)
