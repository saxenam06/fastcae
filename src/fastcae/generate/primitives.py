"""Shapes a design adds, as distance functions.

A parameter does not modify geometry. It contributes a **distance** at every point, and the design
is what you get when those are combined with the base field. That is what makes topology free: a
rib that grows until it meets a boss merges with it, and nothing had to notice.

**The fillet is not a feature.** A smooth minimum joins two solids with a blend of radius ``k``, so
the fillet where a rib meets a wall falls out of the combine rather than being constructed. One
global ``k`` is therefore one global fillet size, which is the control that was wanted and not a
simplification of it.

Nothing here knows what a rib is *for*, and nothing here touches a field. These are functions of a
point in space, which is what makes them testable against closed forms rather than against a
picture.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Slab:
    """A rectangular block with rounded edges, in its own frame.

    A rib, in other words, before anything calls it one. It sits **on** a surface rather than
    centred on one: ``origin`` is the middle of its footprint and it rises from there along ``up``,
    because that is how it is authored - pick a face, and the rib grows out of it.

    ``along`` runs the length of the rib and ``up`` is the host's outward normal; the third axis
    follows from them, so a caller supplies two directions and cannot supply an inconsistent frame.
    """

    origin: tuple[float, float, float]
    along: tuple[float, float, float]
    up: tuple[float, float, float]

    length_mm: float
    thickness_mm: float
    height_mm: float

    round_mm: float = 0.0
    """Radius of the block's own edges. A cast rib has no sharp arris, and rounding it here costs
    one subtraction; the blend where it *meets* the wall is a separate thing and comes from
    :func:`smooth_min`."""

    def frame(self) -> np.ndarray:
        """The three axes as rows: along, across, up. Orthonormal by construction."""
        up = _unit(np.asarray(self.up, dtype=float))
        along = np.asarray(self.along, dtype=float)
        # Only the part of ``along`` that lies in the host surface. A caller pointing slightly out
        # of the plane means the rib to run along it, not to lean.
        along = _unit(along - np.dot(along, up) * up)
        return np.stack([along, np.cross(up, along), up])

    def half_extents(self) -> np.ndarray:
        return np.array(
            [self.length_mm / 2.0, self.thickness_mm / 2.0, self.height_mm / 2.0], dtype=float
        )

    def centre(self) -> np.ndarray:
        """The block's middle. Half its height above the footprint it was placed on."""
        return np.asarray(self.origin, dtype=float) + self.frame()[2] * (self.height_mm / 2.0)

    def distance(self, points: np.ndarray) -> np.ndarray:
        """Signed distance to the block. Negative inside, and exact.

        Exact matters: the blend radius, the wall thickness a design is checked against and the
        surface the contour finds are all read off these numbers, and an approximation here would
        be an approximation in all three.
        """
        local = (np.asarray(points, dtype=float) - self.centre()) @ self.frame().T
        radius = min(self.round_mm, float(self.half_extents().min()))
        gap = np.abs(local) - (self.half_extents() - radius)

        # Outside, the distance is to the nearest corner, edge or face - which is the length of the
        # positive part. Inside, every component is negative and the nearest way out is the least
        # negative one.
        outside = np.linalg.norm(np.maximum(gap, 0.0), axis=1)
        inside = np.minimum(gap.max(axis=1), 0.0)
        return outside + inside - radius

    def bounds(self, margin_mm: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
        """A world-space box holding the block, grown by ``margin_mm``.

        What decides how much of the field a parameter can reach. The margin has to cover the blend
        radius and the band, because a rib changes the distance in cells it does not occupy.
        """
        signs = np.array(np.meshgrid([-1, 1], [-1, 1], [-1, 1])).reshape(3, -1).T
        corners = self.centre() + (signs * self.half_extents()) @ self.frame()
        return corners.min(axis=0) - margin_mm, corners.max(axis=0) + margin_mm


def smooth_min(a: np.ndarray, b: np.ndarray, k_mm: float) -> np.ndarray:
    """Union of two solids, blended over ``k_mm``.

    Negative is inside, so a union is the smaller of the two distances. Taking the plain minimum
    leaves a crease where they meet; easing between them over ``k`` leaves a fillet of about that
    radius instead - which is where the design's fillets come from, rather than from anything
    modelling one.

    At ``k = 0`` this is exactly ``minimum``, so a design with no blend is not a special case.
    """
    if k_mm <= 0.0:
        return np.minimum(a, b)
    weight = np.clip(0.5 + 0.5 * (b - a) / k_mm, 0.0, 1.0)
    return b * (1.0 - weight) + a * weight - k_mm * weight * (1.0 - weight)


def _unit(vector: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(vector))
    if length < 1e-12:
        raise ValueError("a direction of zero length does not describe a direction")
    return vector / length
