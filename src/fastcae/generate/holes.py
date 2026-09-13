"""A hole through a plate, as an exact distance function, and holes cut into a design's field.

**A hole is a capped cylinder.** Its axis leaves the metal square to the plate it goes through; it
reaches ``above_mm`` out of the plate's face - past any thickening of the face - and ``depth_mm``
into the metal, through the plate and a little past its far side, measured at the hole. Nothing
beyond that is touched: a wall standing under the plate is never cut, because a hole over one is
not placed.

**Cutting is a maximum.** Metal stays where it was and the hole was not: ``max(part, -hole)``, the
exact distance to what is left wherever the hole's own surface is the nearest. The hole's edges
stay sharp - a round on them would be the plate's to ask for.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .compose import Composition, _splice
from .field import Field


@dataclass(frozen=True)
class Hole:
    """A round hole: ``centre`` on the face it opens onto, ``axis`` out of the metal there."""

    centre: tuple[float, float, float]
    axis: tuple[float, float, float]
    radius_mm: float
    depth_mm: float
    above_mm: float

    def _frame(self) -> tuple[np.ndarray, np.ndarray]:
        axis = np.asarray(self.axis, dtype=float)
        return np.asarray(self.centre, dtype=float), axis / np.linalg.norm(axis)

    def distance(self, points: np.ndarray) -> np.ndarray:
        """Signed distance from each point to the hole, negative inside it."""
        centre, axis = self._frame()
        p = np.asarray(points, dtype=float) - centre
        h = p @ axis
        radial = np.linalg.norm(p - np.outer(h, axis), axis=1) - self.radius_mm
        # Along the axis: from depth below the face to above_mm over it.
        middle = (self.above_mm - self.depth_mm) / 2.0
        half = (self.above_mm + self.depth_mm) / 2.0
        along = np.abs(h - middle) - half
        inner = np.minimum(np.maximum(radial, along), 0.0)
        outer = np.hypot(np.maximum(radial, 0.0), np.maximum(along, 0.0))
        return inner + outer

    def bounds(self, margin_mm: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
        """The axis-aligned box holding the hole, grown by ``margin_mm``."""
        centre, axis = self._frame()
        ends = np.array([centre + self.above_mm * axis, centre - self.depth_mm * axis])
        # A disc of the radius square to the axis reaches, along each world axis, the radius times
        # the sine of the angle between them.
        spread = self.radius_mm * np.sqrt(np.clip(1.0 - axis**2, 0.0, 1.0))
        return ends.min(axis=0) - spread - margin_mm, ends.max(axis=0) + spread + margin_mm


def cut(base: Field, holes: list[Hole]) -> Composition:
    """``base`` with ``holes`` cut out of it, and which cells that changed."""
    if not holes:
        return Composition(field=base, changed=np.empty(0, dtype=np.int64))
    grid = base.grid
    origin = np.asarray(grid.origin)
    shape = np.asarray(grid.shape)
    reach = base.reach_mm
    blocks = []
    for hole in holes:
        lo, hi = hole.bounds(reach + grid.spacing_mm)
        first = np.clip(np.floor((lo - origin) / grid.spacing_mm).astype(np.int64), 0, shape - 1)
        last = np.clip(np.ceil((hi - origin) / grid.spacing_mm).astype(np.int64), 0, shape - 1)
        axes = [np.arange(first[a], last[a] + 1) for a in range(3)]
        mesh = np.meshgrid(*axes, indexing="ij")
        blocks.append(np.ravel_multi_index(tuple(m.ravel() for m in mesh), grid.shape))
    cells = np.unique(np.concatenate(blocks)).astype(np.int64)
    points = grid.centres(cells)
    value = base.at(cells).astype(np.float64)
    for hole in holes:
        value = np.maximum(value, -hole.distance(points))
    # The sign bit, not "below zero": a cell exactly on the surface is stored as negative zero.
    return _splice(base, cells, value.astype(np.float32), np.signbit(value))
