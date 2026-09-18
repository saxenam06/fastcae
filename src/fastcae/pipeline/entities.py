"""The typed entities a pipeline produces, and the record of the steps that produced them.

One vocabulary for everyone who reads a part: the rail that shows the pipeline, the canvases that
draw what a step produced, and the agent that reasons about it. An entity says what it is (its kind
and typed fields), where it came from (the step, its origin, its evidence), what it is tied to
(links to other entities), and where it can be seen (a canvas and what to highlight there).

Origins stay distinguishable - imported, derived, inferred, confirmed, generated - because a face
the deck loads and a face that merely looks machined are different kinds of knowledge, and whoever
acts on them has to be able to tell.

Nothing here names what a part is for. A bore is a bore on a housing and on a bracket.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class Origin(StrEnum):
    IMPORTED = "imported"
    """Read from a file the engineer brought: a face of the CAD, a group of the deck."""
    DERIVED = "derived"
    """Computed from imported entities by a deterministic rule: a volume, a thickness."""
    INFERRED = "inferred"
    """A reading that could be wrong: a callout matched to a feature, a face that looks machined."""
    CONFIRMED = "confirmed"
    """Settled by the engineer's answer."""
    GENERATED = "generated"
    """Made by fastcae as a proposal: a design, a question."""


class Canvas(StrEnum):
    DRAWING = "drawing"
    CAD = "cad"
    MESH = "mesh"
    SPACE = "space"
    """The CAD in its design-space view: volumes drawn as cells, faces painted by value."""
    NONE = "none"


class Show(BaseModel):
    """Where an entity can be seen, and what to highlight there."""

    canvas: Canvas
    faces: list[int] = Field(default_factory=list)
    """CAD faces to select."""
    page: int | None = None
    """A drawing page."""
    text: str | None = None
    """The literal text to find on that page."""
    group: str | None = None
    """A solver-deck group, as the deck names it."""
    layers: list[str] = Field(default_factory=list)
    """Design-space layers of cells to draw."""
    paint: str | None = None
    """A per-face value to paint the part with: ``thickness``, ``cap``, ``interface`` or
    ``sealing``."""
    point: tuple[float, float, float] | None = None


class Link(BaseModel):
    """A tie to another entity, and what the tie means."""

    to: str
    role: str
    """``on`` (lies on), ``evidenced_by``, ``from`` (made from), ``about``, ``of`` ..."""


class Proof(BaseModel):
    """One piece of evidence: where it came from, where to look, what it said."""

    source: str
    """``cad``, ``drawing``, ``deck``, ``rule``, ``engineer``."""
    locator: str = ""
    detail: str = ""
    confidence: float | None = None


class Entity(BaseModel):
    id: str
    """Readable and stable while the files do not change: ``face:196``, ``group:BORE_MAIN_S2``."""
    kind: str
    label: str
    """A few words, as a list shows it."""
    step: str
    """The step that produced it."""
    origin: Origin
    show: Show = Field(default_factory=lambda: Show(canvas=Canvas.NONE))
    links: list[Link] = Field(default_factory=list)
    evidence: list[Proof] = Field(default_factory=list)
    status: str = "ok"
    """``ok``, or what needs attention: ``asked``, ``conflict``, ``failed``, ``waiting``."""


# --- read: the engineer's files -------------------------------------------------------------------


class Artifact(Entity):
    kind: Literal["artifact"] = "artifact"
    file: str
    artifact_kind: str
    size_bytes: int = 0


class Part(Entity):
    kind: Literal["part"] = "part"
    solids: int
    faces: int
    volume_cm3: float
    area_m2: float
    bbox_mm: list[float]
    unit: str = ""


class Health(Entity):
    kind: Literal["health"] = "health"
    watertight: bool
    triangles: int
    boundary_edges: int = 0
    non_manifold_edges: int = 0
    volume_error_pct: float = 0.0


class Face(Entity):
    kind: Literal["face"] = "face"
    surface: str
    area_mm2: float
    centroid: list[float]
    normal: list[float] | None = None
    axis: list[float] | None = None
    radius_mm: float | None = None
    concave: bool | None = None
    exterior: bool = False
    neighbours: int = 0


class Axis(Entity):
    kind: Literal["axis"] = "axis"
    direction: list[float]
    point: list[float]
    faces: int


class Feature(Entity):
    kind: Literal["feature"] = "feature"
    feature_kind: str
    """``bore``, ``boss``, ``hole``, ``hole_pattern``, ``planar_group``, ``fillet``."""
    faces: list[int]
    diameter_mm: float | None = None
    count: int = 1
    area_mm2: float = 0.0


class Callout(Entity):
    kind: Literal["callout"] = "callout"
    callout_kind: str
    page: int
    text: str
    value: float | None = None
    upper: float | None = None
    lower: float | None = None
    count: int | None = None


class Control(Entity):
    kind: Literal["control"] = "control"
    feature: str
    note: str = ""
    trustworthy: bool = True


class Conflict(Entity):
    kind: Literal["conflict"] = "conflict"
    subject: str
    left: str
    right: str
    tolerance: str = ""


class DeckGroup(Entity):
    kind: Literal["deck_group"] = "deck_group"
    name: str
    nodes: int = 0
    cells: dict[str, int] = Field(default_factory=dict)


class Support(Entity):
    kind: Literal["support"] = "support"
    groups: list[str]
    dofs: dict[str, float]


class Coupling(Entity):
    kind: Literal["coupling"] = "coupling"
    coupling_kind: Literal["rigid", "distributing"]
    groups: list[str]
    reference: str | None = None


class Load(Entity):
    kind: Literal["load"] = "load"
    load_kind: Literal["nodal", "surface"]
    group: str
    values: dict[str, float]


class Material(Entity):
    kind: Literal["material"] = "material"
    name: str
    young: float
    poisson: float
    density: float | None = None


class Signal(Entity):
    kind: Literal["signal"] = "signal"
    name: str
    group: str
    field: str
    components: list[str] = Field(default_factory=list)


class ResultField(Entity):
    kind: Literal["result_field"] = "result_field"
    name: str
    components: list[str] = Field(default_factory=list)


class Anchor(Entity):
    kind: Literal["anchor"] = "anchor"
    group: str
    faces: list[int]
    gap_mm: float | None = None


# --- design space ---------------------------------------------------------------------------------


class Grid(Entity):
    kind: Literal["grid"] = "grid"
    spacing_mm: float
    cells: int
    part_L: float


class FaceMap(Entity):
    """A value on every face it covers, painted on the part."""

    kind: Literal["face_map"] = "face_map"
    what: Literal["thickness", "cap", "interface", "sealing"]
    unit: str = ""
    faces: int = 0
    summary: dict[str, Any] = Field(default_factory=dict)


class Interface(Entity):
    """Faces taken to meet something else: frozen on strong evidence, asked about on weak."""

    kind: Literal["interface"] = "interface"
    interface_kind: str
    """``plane``, ``bore``, ``boss``, ``hole``, ``surface``."""
    state: Literal["frozen", "asked", "released"]
    faces: list[int]
    radius_mm: float | None = None
    area_mm2: float = 0.0
    thickness_mm: float | None = None


class KeepOut(Entity):
    """Space something else occupies: forbidden, or waiting on an answer."""

    kind: Literal["keep_out"] = "keep_out"
    keep_out_kind: Literal["plug", "beyond", "mating", "ring", "hole", "buffer", "waiting"]
    volume_L: float


class Inside(Entity):
    kind: Literal["inside"] = "inside"
    state: Literal["closed", "leaks", "none"]
    volume_L: float
    probes: list[dict[str, float]] = Field(default_factory=list)


class Opening(Entity):
    kind: Literal["opening"] = "opening"
    volume_L: float


class Continuation(Entity):
    """What carries on past a bore's ends."""

    kind: Literal["continuation"] = "continuation"
    ends: list[str]


class Band(Entity):
    kind: Literal["band"] = "band"
    band_kind: Literal["layer", "pockets"]
    volume_L: float
    detail: dict[str, Any] = Field(default_factory=dict)


class Region(Entity):
    kind: Literal["region"] = "region"
    region_kind: Literal["allowed", "waiting"]
    volume_L: float


class Question(Entity):
    kind: Literal["question"] = "question"
    question_kind: str
    text: str
    detail: str = ""
    options: list[str] = Field(default_factory=list)
    meanwhile: str = ""
    answer: str | None = None


class Mirror(Entity):
    kind: Literal["mirror"] = "mirror"
    normal: list[float]
    through: list[float]
    match_share: float


class Benefit(Entity):
    """Where added metal would carry the most load, from one solve of the part under the deck."""

    kind: Literal["benefit"] = "benefit"
    stats: dict[str, Any] = Field(default_factory=dict)


AnyEntity = Annotated[
    Artifact
    | Part
    | Health
    | Face
    | Axis
    | Feature
    | Callout
    | Control
    | Conflict
    | DeckGroup
    | Support
    | Coupling
    | Load
    | Material
    | Signal
    | ResultField
    | Anchor
    | Grid
    | FaceMap
    | Interface
    | KeepOut
    | Inside
    | Opening
    | Continuation
    | Band
    | Region
    | Question
    | Mirror
    | Benefit,
    Field(discriminator="kind"),
]


# --- the pipeline ---------------------------------------------------------------------------------


class Group(BaseModel):
    """Some of a step's inputs or outputs, as the rail lists them: a few words, how many, which."""

    key: str
    label: str
    count: int
    kind: str = ""
    ids: list[str] = Field(default_factory=list)
    step: str = ""
    """For an input: the step that produced it."""


class StepRun(BaseModel):
    id: str
    stage: Literal["read", "space"]
    label: str
    status: Literal["pending", "running", "done", "cached", "skipped", "failed"] = "pending"
    seconds: float | None = None
    detail: str = ""
    inputs: list[Group] = Field(default_factory=list)
    outputs: list[Group] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Stage(BaseModel):
    id: Literal["read", "space"]
    label: str
    steps: list[StepRun]
