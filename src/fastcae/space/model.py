"""What a derived design space is made of: the label every cell carries, the reasons behind it, the
evidence behind every interface, and the settings the rules were run with.

Every name is a geometric kind - a bore corridor, a plane's neighbour, a hole's access - never what
the part is for. The same labels describe a gearbox housing, a bracket and a pump casing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import IntEnum, IntFlag, StrEnum
from typing import Any

import numpy as np

from ..generate.field import Grid


class Label(IntEnum):
    """One answer per cell: the first reason in this order that applies.

    The order is precedence: a cell inside the part is ``PART`` whatever else is true of it, and a
    cell is ``ADMISSIBLE`` only when nothing forbids it and it lies in the candidate band.
    """

    OPEN_AIR = 0
    """Air too far from any wall to be considered."""
    PART = 1
    CAVITY = 2
    """Enclosed air: what the part holds inside it."""
    BORE_CORRIDOR = 3
    """Along a bore's axis, out to the first metal: whatever passes through the bore."""
    PLANE_NEIGHBOUR = 4
    """In front of a frozen plane, over its whole outline: what mates against it."""
    RING_NEIGHBOUR = 5
    """Round a frozen convex cylinder: what fits over it."""
    HOLE_ACCESS = 6
    """Inside a hole, and beyond each open end of it: the fastener and the tool."""
    INTERFACE_BUFFER = 7
    """Close to a frozen face."""
    UNKNOWN = 8
    """Would be forbidden if a doubtful interface is confirmed: waiting for an answer."""
    ADMISSIBLE = 9
    """Metal may be added here."""


LABEL_WORDS = {
    Label.OPEN_AIR: "open air",
    Label.PART: "part",
    Label.CAVITY: "cavity",
    Label.BORE_CORRIDOR: "bore corridor",
    Label.PLANE_NEIGHBOUR: "mating space",
    Label.RING_NEIGHBOUR: "ring round a boss",
    Label.HOLE_ACCESS: "hole access",
    Label.INTERFACE_BUFFER: "interface buffer",
    Label.UNKNOWN: "needs an answer",
    Label.ADMISSIBLE: "allowed",
}


class Reason(IntFlag):
    """Every reason that applies to a cell, not just the one its label shows. Overlaps stay visible:
    a cell can be in a hole's access and a plane's neighbour at once."""

    PART = 1 << 0
    CAVITY = 1 << 1
    BORE_CORRIDOR = 1 << 2
    PLANE_NEIGHBOUR = 1 << 3
    RING_NEIGHBOUR = 1 << 4
    HOLE_ACCESS = 1 << 5
    INTERFACE_BUFFER = 1 << 6
    UNKNOWN = 1 << 7
    PANEL_LAYER = 1 << 8
    """Within the layer grown over the free outer wall."""
    POCKET = 1 << 9
    """Within a pocket between features: space a gusset may fill up to the feature it braces."""
    BEYOND = 1 << 10
    """Past a bore's ends: what sits in it carried on outward, or a shaft carried on inward."""
    LEAK = 1 << 11
    """Air the inside reaches only through a narrow opening."""


class Evidence(StrEnum):
    """Why a face is taken to meet something else. The first four freeze; the rest ask."""

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
    CONFIRMED = "confirmed"
    """The engineer said something meets it."""

    @property
    def freezes(self) -> bool:
        return self in (
            Evidence.DECK_LOAD,
            Evidence.DECK_SUPPORT,
            Evidence.DRAWING,
            Evidence.DECK_HOLE_PLANE,
            Evidence.CONFIRMED,
        )


EVIDENCE_WORDS = {
    Evidence.DECK_LOAD: "the deck loads it",
    Evidence.DECK_SUPPORT: "the deck holds it",
    Evidence.DRAWING: "the drawing tolerances it",
    Evidence.DECK_HOLE_PLANE: "a hole the deck holds opens onto it",
    Evidence.MACHINED: "looks machined: exact shape, sharp edges",
    Evidence.HOLE_PATTERN_PLANE: "a hole pattern opens onto it",
    Evidence.BORE_GEOMETRY: "a bore the deck does not mention",
    Evidence.CONFIRMED: "the engineer said something meets it",
}


@dataclass
class Params:
    """The rules' settings. Every one is shown with the result and can be changed."""

    spacing_mm: float = 4.0
    """The grid's cell size."""
    headroom_mm: float = 170.0
    """How far past the part's box the grid reaches. The band cannot grow further than this."""
    panel_layer: float = 3.0
    """The layer over free walls, in local wall thicknesses (k)."""
    pocket_reach: float = 4.0
    """The radius that bridges gaps between features, in local wall thicknesses (c)."""
    pocket_ladder_mm: tuple[float, ...] = (15.0, 30.0, 45.0, 60.0, 90.0, 120.0, 150.0)
    """The fixed radii the local one is picked from, and the sensitivity display."""
    wall_range: tuple[float, float] = (0.5, 1.5)
    """Local wall thickness is held within these multiples of the part's typical wall, so a solid
    boss does not count as a wall three times as thick."""
    buffer: float = 1.0
    """The buffer round a frozen face, in local wall thicknesses."""
    hole_access_radius: float = 1.8
    """A hole's access cylinder, in the hole's radii."""
    hole_access_length: float = 3.0
    """A hole's access cylinder, in the hole's diameters."""
    sharp_deg: float = 20.0
    """An edge is sharp above this dihedral. A hint towards "machined", never a freeze."""
    thickness_reach_mm: float = 200.0
    """Wall thickness is measured up to this."""
    min_question_area_mm2: float = 1600.0
    """Machined-looking features smaller than this are counted, not asked about: nothing lands on
    them. (40 x 40 mm.)"""
    inside: bool = False
    """Whether metal may be added on the inner walls too, clear of what sits in and passes through
    the bores. Off by default: what moves inside is in neither the CAD nor the deck."""
    inside_layer: float = 3.0
    """The layer over inner walls, in local wall thicknesses, when ``inside`` is on: the same rule
    as outside."""
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
    def frozen(self) -> bool:
        return any(Evidence(e["kind"]).freezes for e in self.evidence)

    @property
    def status(self) -> str:
        return "frozen" if self.frozen else "question"

    def to_json(self) -> dict[str, Any]:
        out = asdict(self)
        out["status"] = self.status
        return out


@dataclass
class Question:
    """Something the rules cannot decide. Asked, never assumed."""

    id: str
    kind: str
    text: str
    """A few words, as the confirm screen shows it."""
    detail: str = ""
    faces: list[int] = field(default_factory=list)
    where: tuple[float, float, float] | None = None
    options: tuple[str, ...] = ()
    meanwhile: str = ""
    """What the cells it concerns are labelled until it is answered."""

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Space:
    """A derived design space. Arrays live on the grid; everything else is plain data."""

    grid: Grid
    params: Params
    labels: np.ndarray
    """uint8, one :class:`Label` per cell."""
    reasons: np.ndarray
    """uint16, the :class:`Reason` bits of every cell."""
    interfaces: list[Interface]
    questions: list[Question]
    columns: dict[str, np.ndarray]
    """The free outer wall, sampled: ``points``, ``normals``, ``face`` (CAD face id), ``thickness``,
    ``cap`` (mm of allowed metal straight out from the wall), ``reenters`` (the column leaves the
    allowed space and comes back into it further out)."""
    sealing_faces: list[int]
    symmetry: list[dict[str, Any]]
    stats: dict[str, Any]
    source_digest: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    """The pipeline as it ran: each step's id, label, seconds, a few words, and what it produced."""
    faces: dict[str, dict[int, Any]] = field(default_factory=dict)
    """Per CAD face: ``thickness`` (median mm), ``cap`` (median mm of allowed metal straight out),
    ``interface`` (the group that froze or asked about it)."""
    benefit: np.ndarray | None = None
    """float32 per cell: strain energy filler would carry there at full stiffness; 0 where not
    allowed. None until the physics step has run."""

    def volume_mm3(self, label: Label) -> float:
        return float((self.labels == label).sum()) * self.grid.spacing_mm**3

    def summary(self) -> dict[str, Any]:
        return {
            "params": self.params.to_json(),
            "grid": {
                "origin": self.grid.origin,
                "spacing_mm": self.grid.spacing_mm,
                "shape": self.grid.shape,
            },
            "volumes_cm3": {
                LABEL_WORDS[label]: round(self.volume_mm3(label) / 1000.0, 1) for label in Label
            },
            "interfaces": [i.to_json() for i in self.interfaces],
            "questions": [q.to_json() for q in self.questions],
            "sealing_faces": self.sealing_faces,
            "symmetry": self.symmetry,
            "stats": self.stats,
            "steps": self.steps,
            "faces": {k: {str(f): v for f, v in d.items()} for k, d in self.faces.items()},
            "has_benefit": self.benefit is not None,
        }
