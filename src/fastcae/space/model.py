"""What a design space is made of: the label every cell carries, the evidence behind every interface
it keeps clear round, and the settings the rules were run with.

Every name is a geometric kind - a bore, a plane that mates, a hole's access - never what the part
is for. The same labels describe a gearbox housing, a bracket and a pump casing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import IntEnum, StrEnum
from typing import Any

import numpy as np

from ..geometry.field import Grid


class Label(IntEnum):
    """One answer per cell. ``DESIGN`` is the design space; the kept-clear labels mark only the
    cells they took from it, so the grid says why metal may not go where it otherwise could."""

    OPEN_AIR = 0
    """Air beyond the layer over the outer walls."""
    PART = 1
    DESIGN = 2
    """The design space: metal may be added here."""
    BORE = 3
    """What sits in a bore and what carries on past its ends - a bearing, a shaft, a cover - and the
    collar round its openings."""
    MATING = 4
    """In front of a held face: what mates against it."""
    RING = 5
    """Round a held boss: what fits over it."""
    HOLE_ACCESS = 6
    """A fastener in a hole, and its tool beyond each open end."""
    BUFFER = 7
    """Close to a held face."""
    INSIDE = 8
    """The inside beyond the layer over its walls: room for what turns in it."""


LABEL_WORDS = {
    Label.OPEN_AIR: "open air",
    Label.PART: "part",
    Label.DESIGN: "design space",
    Label.BORE: "bearing, shaft and collar of a bore",
    Label.MATING: "mating space",
    Label.RING: "ring round a boss",
    Label.HOLE_ACCESS: "fastener and tool",
    Label.BUFFER: "buffer round a held face",
    Label.INSIDE: "inside, left to what turns there",
}


KEPT_CLEAR = (Label.BORE, Label.MATING, Label.RING, Label.HOLE_ACCESS, Label.BUFFER)


class Evidence(StrEnum):
    """Why a face is taken to meet something else. The first four hold it; the rest are weak."""

    DECK_LOAD = "deck_load"
    """The deck loads the face, or couples it to a loaded point."""
    DECK_SUPPORT = "deck_support"
    """The deck holds the face, or couples it to a held point."""
    DRAWING = "drawing"
    """The drawing tolerances the feature."""
    DECK_HOLE_PLANE = "deck_hole_plane"
    """A plane a hole the deck holds or loads opens onto: the joint's clamped faces."""
    MACHINED = "machined"
    """An exact plane or cylinder with sharp edges all round, where a casting leaves fillets."""
    HOLE_PATTERN_PLANE = "hole_pattern_plane"
    """A plane a pattern of holes opens onto, which the deck does not mention."""
    BORE_GEOMETRY = "bore_geometry"
    """A bore the deck does not mention."""

    @property
    def holds(self) -> bool:
        return self in (
            Evidence.DECK_LOAD,
            Evidence.DECK_SUPPORT,
            Evidence.DRAWING,
            Evidence.DECK_HOLE_PLANE,
        )


@dataclass
class Params:
    """The rules' settings. Every one is kept with the result."""

    spacing_mm: float = 4.0
    """The grid's cell size."""
    headroom_mm: float = 170.0
    """How far past the part's box the grid reaches. The layer cannot grow further than this."""
    panel_layer: float = 3.0
    """The layer over the outer walls, in local wall thicknesses (k)."""
    inside_layer: float = 3.0
    """The layer over the inner walls, in local wall thicknesses. What turns inside is in neither
    the CAD nor the deck: the middle of the inside is left to it."""
    pocket_reach: float = 4.0
    """The radius that bridges gaps between features, in local wall thicknesses (c)."""
    pocket_ladder_mm: tuple[float, ...] = (15.0, 30.0, 45.0, 60.0, 90.0, 120.0, 150.0)
    """The fixed radii the local one is picked from."""
    wall_range: tuple[float, float] = (0.5, 1.5)
    """Local wall thickness is held within these multiples of the part's typical wall, so a solid
    boss does not count as a wall three times as thick."""
    buffer: float = 1.0
    """The buffer round a held face, and the collar round a bore, in local wall thicknesses."""
    hole_access_radius: float = 1.8
    """A hole's access cylinder, in the hole's radii."""
    hole_access_length: float = 3.0
    """A hole's access cylinder, in the hole's diameters."""
    sharp_deg: float = 20.0
    """An edge is sharp above this dihedral: a hint that a face is machined."""
    thickness_reach_mm: float = 200.0
    """Wall thickness is measured up to this."""
    min_question_area_mm2: float = 1600.0
    """Machined-looking features smaller than this are only counted: nothing lands on them."""
    use_deck: bool = True
    use_drawing: bool = True

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Interface:
    """A set of faces taken to meet something else, and why."""

    id: str
    kind: str
    """``plane``, ``bore`` (concave cylinder), ``boss`` (convex cylinder), ``hole``, ``surface``."""
    faces: list[int]
    evidence: list[dict[str, Any]] = field(default_factory=list)
    """Each: ``{"kind": Evidence, "detail": str, "confidence": float}``."""
    area_mm2: float = 0.0
    normal: tuple[float, float, float] | None = None
    axis: tuple[float, float, float] | None = None
    axis_point: tuple[float, float, float] | None = None
    radius_mm: float | None = None
    thickness_mm: float | None = None
    """The wall's median thickness under these faces - what its buffer is measured in."""

    @property
    def held(self) -> bool:
        """The deck or the drawing says something meets it."""
        return any(Evidence(e["kind"]).holds for e in self.evidence)

    @property
    def kept_clear(self) -> bool:
        """Whether the design space keeps clear round it: a held face, and every bore - what sits
        in a bore and passes through it is there whatever the evidence says."""
        return self.held or self.kind == "bore"

    def to_json(self) -> dict[str, Any]:
        out = asdict(self)
        out["held"] = self.held
        out["kept_clear"] = self.kept_clear
        return out


@dataclass
class Space:
    """A design space. Arrays live on the grid; everything else is plain data."""

    grid: Grid
    params: Params
    labels: np.ndarray
    """uint8, one :class:`Label` per cell."""
    interfaces: list[Interface]
    stats: dict[str, Any]
    source_digest: str = ""
    """The CAD it was defined on."""
    defined_by: str = "rules"
    """``rules`` - defined by fastcae standing in for the engineer - or ``engineer``."""
    seconds: float = 0.0
    benefit: np.ndarray | None = None
    """float32 per cell: strain energy metal would carry there at full stiffness; 0 outside the
    design space. None when the deck could not be solved."""

    @property
    def design(self) -> np.ndarray:
        return self.labels == Label.DESIGN

    def litres(self, label: Label) -> float:
        return round(float((self.labels == label).sum()) * self.grid.spacing_mm**3 / 1e6, 1)

    def summary(self) -> dict[str, Any]:
        return {
            "defined_by": self.defined_by,
            "source_digest": self.source_digest,
            "seconds": round(self.seconds, 1),
            "params": self.params.to_json(),
            "grid": {
                "origin": self.grid.origin,
                "spacing_mm": self.grid.spacing_mm,
                "shape": self.grid.shape,
            },
            "litres": {LABEL_WORDS[label]: self.litres(label) for label in Label},
            "interfaces": [i.to_json() for i in self.interfaces],
            "stats": self.stats,
            "has_benefit": self.benefit is not None,
        }
