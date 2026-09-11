"""Zones: where ribs may go, and how they attach there.

A zone is a region - an arc of an annulus about an axis, a band of radii, a range of levels - and
which way ribs attach inside it. Nothing here decides where a zone is; that is the engineer's
intent, written into the project. What is here is what composing ribs into a zone needs.

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
