"""What a rib is measured by: the limits every rib keeps - how thick, how deeply sunk, how
sharp a corner, how near the metal counts as rooted - the part's metal on a plane, and the round a
volume grows from. :class:`Candidate` is a rib as the builder and the record know it: where it
stands, in which volume, and what it is called."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import shapely
from shapely.geometry.base import BaseGeometry

from ..volumes import reading, slices

if TYPE_CHECKING:
    from ..extract import Extraction
    from ..volumes.volume import Volume

THICKEST_MM = 25.0
"""The thickest a rib may be: its shape must be air across this."""
BURY_MM = 6.0
"""How far a rib is sunk into the metal it meets."""
SKIN_MM = 3.0
"""The least metal left between a sunk rib and the air beyond the wall it is sunk into."""
FREE_MM = 1.5
"""Outline further than this from the metal is free edge."""


@dataclass
class Candidate:
    """One rib a design may have: its placement, its form, and its plates."""

    id: str
    volume: str
    family: str
    form: str
    placement: str
    angle_deg: float
    hand: int
    plane: slices.Plane = field(repr=False)
    shape: BaseGeometry = field(repr=False)
    """The web's outline in its plane: the air it fills and the metal it is sunk into."""
    air_mm2: float
    """The area of the air the web fills."""
    flange: tuple[slices.Plane, BaseGeometry] | None = field(default=None, repr=False)
    flange_mm2: float = 0.0
    reach_mm: tuple[float, float] = (0.0, 0.0)
    """How far from the volume's axis the rib reaches, least and most."""
    taper: tuple[float, float, float] | None = None
    """A web thick ``t0`` where its run starts (its plane's origin) and ``t1`` a ``length`` along
    it, the faces straight between: (t0, t1, length) mm. None for a web of one thickness."""

    extra: list[tuple[slices.Plane, BaseGeometry]] = field(default_factory=list, repr=False)
    """Further plates of the same rib, each in its own plane: the chords a curved rib is made of.

    A rib that follows a bore round is not flat, so it is not one plate. It is a short chain of
    them, each square to the mould's pull as every rib must be, meeting end to end - which is how a
    foundry makes an arc and how the fuse reads one."""

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "volume": self.volume,
            "family": self.family,
            "form": self.form,
            "placement": self.placement,
            "angle_deg": round(self.angle_deg, 2),
            "hand": self.hand,
            "air_mm2": round(self.air_mm2),
            "flange_mm2": round(self.flange_mm2),
            "reach_mm": [round(self.reach_mm[0], 1), round(self.reach_mm[1], 1)],
            "normal": [round(float(v), 6) for v in self.plane.normal],
        }


def _anchor_radius(extraction: Extraction, found: Volume) -> float:
    """How far the metal the volume grows from lies from its axis: the median of its faces'."""
    r = found.recipe
    axis, point = np.asarray(r.axis, float), np.asarray(r.point, float)
    faces = list(r.anchors) or list(r.faces)
    pts = np.concatenate([reading.face_points(extraction, f) for f in faces])
    off = pts - point
    return float(np.median(np.linalg.norm(off - np.outer(off @ axis, axis), axis=1)))


def _metal(extraction: Extraction, at: slices.Plane) -> BaseGeometry:
    tess = extraction.tess
    assert tess is not None
    return slices.section(tess.vertices, tess.triangles, tess.face_id, at).inside


def _largest(shape: BaseGeometry) -> BaseGeometry:
    pieces = [
        g for g in getattr(shape, "geoms", [shape]) if g.geom_type == "Polygon" and not g.is_empty
    ]
    return max(pieces, key=lambda g: g.area) if pieces else shapely.Polygon()
