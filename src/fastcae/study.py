"""The study: what the engineer wants, as a design space in the part's named entities.

A study says, for each group of features to add, where they may go and what may vary - and for the
whole part, what every design must satisfy, what makes one better, what "better" means, and how many
designs to make from which seed. A design is a point in it: a version of the study and one value
for each free setting. Generation reads nothing else, so a version and a seed always give the same
designs.

**Written only through :func:`write`** - by the rib card or by a model's tools, never by hand. It
refuses what it cannot stand behind: words the engineer never said, faces they never selected,
entities the part does not have, a hard rule that cites nothing, a range that holds no value, a
known rule without what it needs.

**Every constraint has a strength and a source.** *Hard*: the engineer said it, or the drawing or
the part shows it - and it cites the words or says where it came from. *Assumed*: a default the
system took, the only kind it may offer to relax. *Learned*: from a rejection the engineer
confirmed, citing their words.

**Nothing is dropped.** A rule of a kind nothing checks, or one whose stage is not built yet, a free
setting nothing uses, a feature nothing can add - each is kept and listed by :func:`open_items`.
Everything nobody confirmed is listed by :func:`assumed`.

**Entities are bound by fingerprint.** ``face:1201`` is a name to show; :func:`resolve` finds each
entity on the part again by kind, size and position, or says it is gone.

**Every change is a new version**, kept beside the old ones in ``<project>/studies/<name>.json``,
with what changed. ``project.json`` names the active study.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from .features import FeatureKind, FeatureSet
from .project import Project
from .spec import Measured, SpecError, Words, changes, fingerprint, gather_words

STUDY_DIR = "studies"

# Who set a free setting, or a direction. The first two mean the engineer asked for it.
Source = Literal["you", "selected", "drawing", "measured", "default"]
ASKED = ("you", "selected")

# Where a constraint came from.
Origin = Literal["you", "selected", "drawing", "cad", "default", "rejection"]

# What the engine can add. A block asking for anything else is kept, and listed as open.
ADDS = ("ribs",)

# The free settings a block of ribs is made from. Any other is kept, and listed as open.
USED = (
    "generator",
    "centre",
    "spread",
    "angle_deg",
    "count",
    "spacing_mm",
    "thickness_mm",
    "height_fraction",
    "top",
    "root_fillet_mm",
    "edge_round_mm",
    "draft_deg",
)

# Quantities known without physics. Anything else an objective names waits for simulation.
GEOMETRIC = ("added_mass", "rib_volume", "rib_count", "rib_length", "coverage")

# How far holes and bores are kept clear of when nobody says otherwise.
INTERFACE_CLEARANCE_MM = 5.0

_REF = re.compile(r"^[a-z_]+:\d+$")


class StudyError(ValueError):
    """A study that cannot be written, and why."""


# --- the schema ---------------------------------------------------------------------------------


class Domain(BaseModel):
    """What one free setting may take - a range with a step, or a list of choices with a weight
    each - and the value a single design takes when the setting is not sampled."""

    low: float | None = None
    high: float | None = None
    step: float | None = Field(default=None, gt=0.0)
    options: list[str | float] | None = None
    weights: list[float] | None = None
    """How likely each choice is when designs are sampled - a prior, never a limit."""
    unit: str = ""
    suggested: str | float | None = None
    source: Source = "default"
    basis: str = ""
    """Why this range: what it was measured on or taken from, in words."""
    cites: list[str] = Field(default_factory=list)
    confirmed: bool = False

    @model_validator(mode="after")
    def _holds_something(self) -> Domain:
        ranged = self.low is not None or self.high is not None or self.step is not None
        if ranged and self.options is not None:
            raise ValueError("a setting is a range or a list of choices, not both")
        if self.options is not None:
            if not self.options:
                raise ValueError("a list of choices holds no choices")
            if self.weights is not None:
                if len(self.weights) != len(self.options):
                    raise ValueError("a list of choices needs a weight for each choice")
                if any(w < 0.0 for w in self.weights):
                    raise ValueError("a weight cannot be negative")
                if not any(w > 0.0 for w in self.weights):
                    raise ValueError("every weight is zero: nothing could be chosen")
        else:
            if self.low is None or self.high is None or self.step is None:
                raise ValueError("a range needs a low, a high and a step")
            if self.low > self.high:
                raise ValueError("low is above high")
            if self.weights is not None:
                raise ValueError("weights belong to a list of choices, not a range")
        if self.suggested is not None and not self.holds(self.suggested):
            raise ValueError(f"the suggested {self.suggested} is outside what it may take")
        return self

    def holds(self, value: Any) -> bool:
        if self.options is not None:
            return value in self.options
        try:
            number = float(value)
        except (TypeError, ValueError):
            return False
        assert self.low is not None and self.high is not None
        return self.low - 1e-9 <= number <= self.high + 1e-9

    @property
    def fixed(self) -> bool:
        return len(self.options) == 1 if self.options is not None else self.low == self.high

    def says(self) -> str:
        """What it may take, in words: '9 to 15 mm, 12 suggested', 'radial or grid'."""
        unit = self.unit if self.unit == "°" else (f" {self.unit}" if self.unit else "")
        if self.options is not None:
            shown = [_shown(o) for o in self.options]
            what = shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " or " + shown[-1]
            what += unit
        elif self.low == self.high:
            what = f"{_shown(self.low)}{unit}"
        else:
            what = f"{_shown(self.low)} to {_shown(self.high)}{unit}"
        if self.suggested is not None and not self.fixed:
            what += f", {_shown(self.suggested)} suggested"
        return what


class Where(BaseModel):
    """Where a group of features may go: what they may stand on - none, for ribs that hang between
    what they join - what they may run between or attach to, and whether they may span several of
    the faces they stand on, stay within one, or must bridge them."""

    support: list[str] = Field(default_factory=list)
    anchors: list[str] = Field(default_factory=list)
    span: Literal["union", "within_one", "must_bridge"] = "union"


class Block(BaseModel):
    """One group of features to add: what kind, where, and the settings designs vary over."""

    id: str = ""
    add: str
    where: Where = Field(default_factory=Where)
    free: dict[str, Domain] = Field(default_factory=dict)
    cites: list[str] = Field(default_factory=list)


class Constraint(BaseModel):
    """Something every design must satisfy, how firmly, and where it came from."""

    id: str = ""
    kind: str
    refs: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    block: str | None = None
    """The block it applies to; None: every block."""
    strength: Literal["hard", "assumed", "learned"] = "hard"
    source: Origin | None = None
    basis: str = ""
    """For a rule from the drawing or the part: the callout or the measurement, in words."""
    text: str = ""
    cites: list[str] = Field(default_factory=list)
    confirmed: bool = False

    @model_validator(mode="after")
    def _source_follows_strength(self) -> Constraint:
        if self.source is None:
            self.source = {"hard": "you", "assumed": "default", "learned": "rejection"}[
                self.strength
            ]
        return self


class Preference(BaseModel):
    """What makes a design better, not required - a weight when designs are chosen."""

    id: str = ""
    text: str
    kind: str = ""
    refs: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    block: str | None = None
    weight: float = Field(default=1.0, gt=0.0)
    source: Literal["you", "selected", "default"] = "you"
    cites: list[str] = Field(default_factory=list)


class Objective(BaseModel):
    """What "better" means: a quantity to make small or large, kept apart from every other."""

    id: str = ""
    quantity: str
    sense: Literal["min", "max"]
    refs: list[str] = Field(default_factory=list)
    text: str = ""
    source: Literal["you", "selected", "default"] = "you"
    cites: list[str] = Field(default_factory=list)

    @property
    def physical(self) -> bool:
        """Whether it waits for simulation."""
        return self.quantity not in GEOMETRIC


class Pull(BaseModel):
    """Which way the part leaves its mould: a direction, or the one a face gives - its normal or its
    axis."""

    direction: list[float] | None = None
    along: str | None = None
    source: Source = "default"
    basis: str = ""
    cites: list[str] = Field(default_factory=list)
    confirmed: bool = False

    @model_validator(mode="after")
    def _one_way(self) -> Pull:
        if (self.direction is None) == (self.along is None):
            raise ValueError("a pull is a direction or a face to take it from, one of the two")
        if self.direction is not None and (
            len(self.direction) != 3 or math.hypot(*self.direction) < 1e-9
        ):
            raise ValueError("a pull direction is three numbers, not all zero")
        return self


class Target(BaseModel):
    """How many designs, spread how, how different each must be from the rest, and the seed."""

    n: int = Field(default=4000, ge=1)
    stratify: Literal["topology"] = "topology"
    differ_by: int = Field(default=2, ge=1)
    """Two designs count as different when they differ by at least this many ribs."""
    seed: int = 0


class StudyVersion(BaseModel):
    version: int
    created: str
    words: list[Words]
    blocks: list[Block]
    constraints: list[Constraint] = Field(default_factory=list)
    prefer: list[Preference] = Field(default_factory=list)
    objectives: list[Objective] = Field(default_factory=list)
    pull: Pull | None = None
    target: Target = Field(default_factory=Target)
    measured: list[Measured] = Field(default_factory=list)
    fingerprints: dict[str, dict[str, Any]] = Field(default_factory=dict)
    note: str = ""
    changes: list[str] = Field(default_factory=list)


class Study(BaseModel):
    name: str
    versions: list[StudyVersion] = Field(default_factory=list)

    @property
    def current(self) -> StudyVersion:
        return self.versions[-1]


# --- the kinds of rule ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Kind:
    """A kind of rule the engine knows: how it reads, what it needs, and which stage enforces it -
    one rib at a time, combinations of ribs, their sizes, or the built design."""

    says: str
    needs: tuple[str, ...] = ()
    names: bool = False
    """Whether it names entities of the part, and is nothing without them."""
    stage: Literal["one rib", "combinations", "sizes", "built"] = "one rib"
    enforced: bool = True
    """Whether that stage enforces it today."""


KINDS: dict[str, Kind] = {
    "keep_clear_of": Kind("{clearance_mm:g} mm clear of {refs}", ("clearance_mm",), names=True),
    # Kept clear anywhere on the part, not only where ribs stand: that needs candidate ribs tested
    # in three dimensions. Until then the holes where ribs stand are kept clear of by keep_clear_of.
    "interface": Kind("{refs} left as they are", names=True, enforced=False),
    # A datum the drawing names: an interface whose face is not known until someone points at it.
    "datum": Kind("datum {letter} left as it is", ("letter",), enforced=False),
    "not_above": Kind("no taller than {refs}", names=True),
    "height_at_most": Kind("at most {mm:g} mm tall", ("mm",)),
    "within_what_it_meets": Kind("each end no taller than what it meets"),
    "ends_on": Kind("every rib ends on what it runs between"),
    "along": Kind("along {refs}", names=True),
    "square_to": Kind("square to {refs}", names=True),
    "not_ends_on": Kind("no rib ends on {refs}", names=True, enforced=False),
    "parallel_to_plane": Kind("parallel to the {plane} plane", ("plane",), enforced=False),
    "plane_contains_pull": Kind("each rib's plane contains the pull direction", enforced=False),
    "min_length": Kind(
        "at least {thicknesses:g} thicknesses long", ("thicknesses",), enforced=False
    ),
    "count_between": Kind(
        "{low:g} to {high:g} ribs", ("low", "high"), stage="combinations", enforced=False
    ),
    "at_least_at": Kind(
        "at least {n:g} ribs at {refs}", ("n",), names=True, stage="combinations", enforced=False
    ),
    "at_most_meeting": Kind(
        "at most {n:g} ribs meeting at one point", ("n",), stage="combinations", enforced=False
    ),
    "spacing_at_least": Kind(
        "at least {mm:g} mm apart", ("mm",), stage="combinations", enforced=False
    ),
    "no_x_junctions": Kind("no X-crossings", stage="combinations", enforced=False),
    "junction_angle_at_least": Kind(
        "ribs meeting at least {deg:g}° apart", ("deg",), stage="combinations", enforced=False
    ),
    "tie": Kind("{refs} tied together by ribs", names=True, stage="combinations", enforced=False),
    "symmetric_about": Kind(
        "symmetric about {refs}", names=True, stage="combinations", enforced=False
    ),
    "smallest_radius": Kind("no radius under {radius_mm:g} mm", ("radius_mm",), stage="sizes"),
    "draft_at_least": Kind("at least {deg:g}° of draft", ("deg",), stage="sizes"),
    "thickness_to_wall": Kind(
        "{low:g} to {high:g} of the wall met", ("low", "high"), stage="sizes"
    ),
}

# Which step of the build enforces each stage, for a rule whose stage is not built yet.
UNTIL = {
    "one rib": "candidate ribs are built (step 2)",
    "combinations": "the solver chooses combinations (step 3)",
    "sizes": "sizes are sampled (step 3)",
    "built": "designs are built and checked",
}


def said(constraint: Constraint) -> str:
    """The rule in words: as written, or as its kind reads it."""
    if constraint.text:
        return constraint.text
    kind = KINDS.get(constraint.kind)
    if kind is None:
        return constraint.kind.replace("_", " ")
    try:
        return kind.says.format(refs=", ".join(constraint.refs), **constraint.params)
    except (KeyError, ValueError, TypeError):
        return constraint.kind.replace("_", " ")


# --- reading and writing ------------------------------------------------------------------------


def path_of(project: Project, name: str):
    return project.root / STUDY_DIR / f"{name}.json"


def load(project: Project, name: str) -> Study | None:
    path = path_of(project, name)
    if not path.is_file():
        return None
    return Study.model_validate_json(path.read_text(encoding="utf-8"))


def active(project: Project) -> Study | None:
    """The study ``project.json`` names, if any."""
    name = project.data().get("study")
    return load(project, name) if name else None


def write(
    project: Project,
    name: str,
    *,
    quotes: list[str],
    said: list[str],
    blocks: list[dict[str, Any]],
    features: FeatureSet,
    constraints: list[dict[str, Any]] | None = None,
    prefer: list[dict[str, Any]] | None = None,
    objectives: list[dict[str, Any]] | None = None,
    pull: dict[str, Any] | None = None,
    target: dict[str, Any] | None = None,
    measured: list[dict[str, Any]] | None = None,
    note: str = "",
    selected: list[int] | None = None,
    selections: list[list[int]] | None = None,
) -> StudyVersion:
    """A new version of the study, checked, written, and made active.

    ``quotes`` are the engineer's words this version adds, each exactly as it appears in ``said``;
    ``selected`` is a set of faces they selected, among the ``selections`` they made. Cites of
    ``new`` stand for every word and selection this version adds, ``these`` for every one it rests
    on. Entries without an id are numbered: blocks ``b1``, constraints ``c1``, preferences ``p1``,
    objectives ``o1``.
    """
    if not name or any(c in name for c in "/\\:"):
        raise StudyError(f"{name!r} is not a study name")
    study = load(project, name) or Study(name=name)
    previous = study.versions[-1] if study.versions else None
    kept = previous.words if previous else []
    try:
        words, these = gather_words(kept, quotes, said, selected, selections)
    except SpecError as error:
        raise StudyError(str(error)) from error
    added = [w.id for w in words if w.id not in {k.id for k in kept}]
    stands_for = {"new": added, "these": these}

    problems: list[str] = []
    parsed: dict[str, list[Any]] = {}
    for key, model, items, prefix in (
        ("blocks", Block, blocks, "b"),
        ("constraints", Constraint, constraints or [], "c"),
        ("prefer", Preference, prefer or [], "p"),
        ("objectives", Objective, objectives or [], "o"),
    ):
        out = []
        for index, item in enumerate(items):
            label = item.get("id") or f"{prefix}{index + 1}"
            try:
                out.append(model.model_validate(_cited(item, stands_for)))
            except ValidationError as error:
                problems.append(f"{label}: {_plain(error)}")
        parsed[key] = _numbered(out, prefix)
    extras: dict[str, Any] = {}
    for key, model, value in (("pull", Pull, pull), ("target", Target, target)):
        if value is None:
            continue
        try:
            extras[key] = model.model_validate(_cited(value, stands_for))
        except ValidationError as error:
            problems.append(f"{key}: {_plain(error)}")
    try:
        numbers = [Measured.model_validate(m) for m in measured or []]
    except ValidationError as error:
        problems.append(f"measured: {_plain(error)}")
        numbers = []
    if problems:
        raise StudyError("; ".join(problems))

    version = StudyVersion(
        version=(previous.version + 1) if previous else 1,
        created=datetime.now(UTC).isoformat(timespec="seconds"),
        words=words,
        blocks=parsed["blocks"],
        constraints=parsed["constraints"],
        prefer=parsed["prefer"],
        objectives=parsed["objectives"],
        measured=numbers,
        note=note,
        **extras,
    )
    problems = _problems(version, {w.id for w in words}, features)
    if problems:
        raise StudyError("; ".join(problems))

    version.fingerprints = {ref: fingerprint(features, ref) for ref in sorted(_refs(version))}
    version.changes = changes(previous, version)
    study.versions.append(version)
    path = path_of(project, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(study.model_dump_json(indent=2) + "\n", encoding="utf-8")
    project.write_data("study", name)
    return version


def _cited(item: dict[str, Any], stands_for: dict[str, list[str]]) -> dict[str, Any]:
    """The item with every ``cites`` in it - its own and its settings' - expanded."""

    def expand(value: Any) -> Any:
        if isinstance(value, dict):
            out = {}
            for key, inner in value.items():
                if key == "cites" and isinstance(inner, list):
                    cites: list[str] = []
                    for cite in inner:
                        for one in stands_for.get(cite, [cite]):
                            if one not in cites:
                                cites.append(one)
                    out[key] = cites
                else:
                    out[key] = expand(inner)
            return out
        if isinstance(value, list):
            return [expand(v) for v in value]
        return value

    return expand(dict(item))


def _numbered(items: list[Any], prefix: str) -> list[Any]:
    """Ids for entries without one: the next free numbers after those given."""
    taken = {int(i.id[len(prefix) :]) for i in items if re.fullmatch(rf"{prefix}\d+", i.id)}
    counter = max(taken, default=0)
    for item in items:
        if not item.id:
            counter += 1
            item.id = f"{prefix}{counter}"
    return items


def _plain(error: ValidationError) -> str:
    lines = []
    for e in error.errors():
        where = ".".join(str(p) for p in e["loc"])
        message = str(e["msg"]).removeprefix("Value error, ")
        lines.append(f"{where}: {message}" if where else message)
    return "; ".join(lines)


def _refs(version: StudyVersion) -> set[str]:
    """Every entity of the part the version names."""
    refs: set[str] = set()
    for b in version.blocks:
        refs |= {*b.where.support, *b.where.anchors}
        for domain in b.free.values():
            values = [*(domain.options or []), domain.suggested]
            refs |= {v for v in values if isinstance(v, str) and _REF.match(v)}
    for item in (*version.constraints, *version.prefer, *version.objectives):
        refs |= set(item.refs)
    if version.pull is not None and version.pull.along:
        refs.add(version.pull.along)
    refs |= {m.on for m in version.measured}
    return refs


def _problems(version: StudyVersion, word_ids: set[str], features: FeatureSet) -> list[str]:
    problems = []
    missing = sorted(r for r in _refs(version) if features.get(r) is None)
    if missing:
        problems.append(
            f"the part has no {', '.join(missing)} - ids look like planar_group:114, hole:3, "
            "bore:196 or face:1453"
        )

    def unknown_cites(label: str, cites: list[str]) -> None:
        unknown = sorted({c for c in cites if c not in word_ids})
        if unknown:
            problems.append(f"{label} cites {', '.join(unknown)}, which are not words")

    for group in (version.blocks, version.constraints, version.prefer, version.objectives):
        ids = [item.id for item in group]
        doubled = sorted({i for i in ids if ids.count(i) > 1})
        if doubled:
            problems.append(f"{', '.join(doubled)} is used twice")
    block_ids = {b.id for b in version.blocks}
    for b in version.blocks:
        if not b.cites:
            problems.append(f"{b.id} cites no words")
        unknown_cites(b.id, b.cites)
        for name, domain in b.free.items():
            if domain.source in ASKED and not domain.cites:
                problems.append(f"{b.id} {name} was set by the engineer and cites no words")
            unknown_cites(f"{b.id} {name}", domain.cites)
    for c in version.constraints:
        if c.strength == "hard" and c.source in ASKED and not c.cites:
            problems.append(f"{c.id} is hard and cites no words")
        if c.strength == "hard" and c.source in ("drawing", "cad") and not c.basis:
            problems.append(
                f"{c.id} comes from the {c.source} but does not say where: give the callout or "
                "the measurement"
            )
        if c.strength == "learned" and not c.cites:
            problems.append(f"{c.id} is learned and cites no words")
        unknown_cites(c.id, c.cites)
        if c.block is not None and c.block not in block_ids:
            problems.append(f"{c.id} applies to {c.block}, which is not a block")
        kind = KINDS.get(c.kind)
        if kind is not None:
            lacking = [p for p in kind.needs if p not in c.params]
            if lacking:
                problems.append(f"{c.id}: {c.kind} needs {', '.join(lacking)}")
            if kind.names and not c.refs:
                problems.append(f"{c.id}: {c.kind} needs what it names")
    for item in (*version.prefer, *version.objectives):
        if item.source in ASKED and not item.cites:
            problems.append(f"{item.id} cites no words")
        unknown_cites(item.id, item.cites)
    if version.pull is not None:
        if version.pull.source in ASKED and not version.pull.cites:
            problems.append("the pull direction was set by the engineer and cites no words")
        unknown_cites("the pull direction", version.pull.cites)
    return problems


# --- what is open, and what is assumed -----------------------------------------------------------


def open_items(version: StudyVersion) -> list[str]:
    """What the study holds that nothing acts on yet - kept, never dropped, and said plainly."""
    items = []
    for b in version.blocks:
        if b.add not in ADDS:
            items.append(f"{b.id}: nothing can add {b.add} yet")
            continue
        for name in b.free:
            if name not in USED:
                items.append(f"{b.id} {name}: nothing uses this setting yet")
    for c in version.constraints:
        kind = KINDS.get(c.kind)
        if kind is None:
            items.append(f"{c.id}: {said(c)} - nothing checks this kind of rule yet")
        elif c.kind == "datum" and not c.refs:
            items.append(f"{c.id}: {said(c)} - which face is it? Point at it on the part")
        elif not kind.enforced:
            items.append(f"{c.id}: {said(c)} - not enforced until {UNTIL[kind.stage]}")
    if version.pull is None and version.blocks:
        items.append("the pull direction is not given: which way does the part leave its mould?")
    return items


def shown(version: StudyVersion) -> dict[str, Any]:
    """Every free setting and every constraint in words, by block and by id - as the engineer
    reads them."""
    return {
        "free": {b.id: {name: d.says() for name, d in b.free.items()} for b in version.blocks},
        "constraints": {c.id: said(c) for c in version.constraints},
    }


def assumed(version: StudyVersion) -> list[str]:
    """Everything nobody confirmed: free settings the part, the drawing or a default suggested,
    rules the system took, a pull direction nobody gave - to confirm, lock or narrow."""
    lines = []
    for b in version.blocks:
        for name, domain in b.free.items():
            if domain.source in ASKED or domain.confirmed:
                continue
            why = f": {domain.basis}" if domain.basis else ""
            lines.append(f"{b.id} {name}: {domain.says()} ({domain.source}{why})")
    for c in version.constraints:
        if c.strength == "assumed" and not c.confirmed:
            why = f": {c.basis}" if c.basis else ""
            lines.append(f"{c.id}: {said(c)} (assumed{why})")
    pull = version.pull
    if pull is not None and pull.source not in ASKED and not pull.confirmed:
        way = pull.along or ", ".join(f"{v:g}" for v in pull.direction or [])
        lines.append(f"pull: along {way} ({pull.source})")
    return lines


# --- one design ---------------------------------------------------------------------------------

# Each straight pattern's families: their angle to the first, and where their lines sit between
# lattice points. A triangle grid's middle family sits on them where the outer two sit halfway, so
# all three meet.
FAMILIES = {
    "parallel": [(0.0, 0.5)],
    "grid": [(0.0, 0.5), (90.0, 0.5)],
    "triangle": [(0.0, 0.5), (60.0, 0.0), (120.0, 0.5)],
}


def layout_of(
    generator: str,
    angle: float,
    *,
    count: int | None = None,
    spacing: float | None = None,
    centre: str | None = None,
    spread: str = "across",
) -> dict[str, Any]:
    """The layout a generator draws: spokes about ``centre``, or straight families at ``angle``,
    a count or a spacing apart."""
    if generator == "radial":
        return {
            "kind": "radial",
            "centre": centre,
            "count": int(count or 0),
            "phase_deg": angle,
            "spread": spread,
        }
    key, value = ("count", int(count or 0)) if spacing is None else ("spacing_mm", spacing)
    return {
        "kind": "parallel" if generator == "parallel" else "grid",
        "families": [
            {"angle_deg": angle + a, key: value, "offset": offset}
            for a, offset in FAMILIES[generator]
        ],
    }


def point(
    version: StudyVersion, block: str, values: dict[str, Any] | None = None
) -> dict[str, Any]:
    """The placement one design of a block is made from: each free setting at the value given, or
    at its suggested value, and the constraints enforced today as the placement holds them. A
    straight pattern takes its spacing when the block has one, and its count otherwise."""
    found = next((b for b in version.blocks if b.id == block), None)
    if found is None:
        raise StudyError(f"there is no block {block}")
    if found.add not in ADDS:
        raise StudyError(f"nothing can add {found.add} yet")
    chosen: dict[str, Any] = {name: d.suggested for name, d in found.free.items()}
    chosen.update(values or {})
    lacking = [n for n in ("generator", "thickness_mm", "root_fillet_mm") if chosen.get(n) is None]
    if lacking:
        raise StudyError(f"{block} has no value for {', '.join(lacking)}")
    rules = [
        c
        for c in version.constraints
        if c.block in (None, found.id) and c.kind in KINDS and KINDS[c.kind].enforced
    ]

    generator = str(chosen["generator"])
    angle = float(chosen.get("angle_deg") or 0.0)
    if generator == "radial":
        layout = layout_of(
            "radial",
            angle,
            count=chosen.get("count"),
            centre=chosen.get("centre"),
            spread=str(chosen.get("spread") or "across"),
        )
    elif "spacing_mm" in found.free or "spacing_mm" in (values or {}):
        layout = layout_of(generator, angle, spacing=float(chosen["spacing_mm"]))
    else:
        layout = layout_of(generator, angle, count=chosen.get("count"))

    # What ribs keep clear of: every feature at the largest clearance any rule asks for it.
    widest: dict[str, float] = {}
    cited: dict[float, list[str]] = {}
    for c in (c for c in rules if c.kind == "keep_clear_of"):
        clearance = float(c.params["clearance_mm"])
        for ref in c.refs:
            widest[ref] = max(widest.get(ref, clearance), clearance)
        cited.setdefault(clearance, [])
        cited[clearance] += [x for x in c.cites if x not in cited[clearance]]
    keep_out = []
    for clearance in sorted({*widest.values()}, reverse=True):
        keep_out.append(
            {
                "features": [ref for ref, w in widest.items() if w == clearance],
                "clearance_mm": clearance,
                "cites": cited.get(clearance, []),
            }
        )

    height: dict[str, Any] = {
        "top": str(chosen.get("top") or "slope"),
        "fraction": float(chosen.get("height_fraction") or 1.0),
        "cites": [],
    }
    not_above = list(dict.fromkeys(r for c in rules if c.kind == "not_above" for r in c.refs))
    if not_above:
        height["not_above"] = not_above
    caps = [float(c.params["mm"]) for c in rules if c.kind == "height_at_most"]
    if caps:
        height["max_mm"] = min(caps)
    return {
        "id": found.id,
        "host": list(found.where.support),
        "supports": list(found.where.anchors),
        "keep_out": keep_out,
        "layout": layout,
        "height": height,
        "section": {
            "thickness_mm": float(chosen["thickness_mm"]),
            "root_fillet_mm": float(chosen["root_fillet_mm"]),
            "edge_round_mm": float(chosen.get("edge_round_mm") or 0.0),
            "draft_deg": float(chosen.get("draft_deg") or 0.0),
        },
        "connection": "supports" if any(c.kind == "ends_on" for c in rules) else "free",
        "cites": list(found.cites),
    }


def rules_of(version: StudyVersion) -> dict[str, Any]:
    """The check thresholds a design of this version is held to: the smallest radius allowed, when
    the study names one."""
    radii = [
        float(c.params["radius_mm"]) for c in version.constraints if c.kind == "smallest_radius"
    ]
    return {"fillet_floor_mm": max(radii)} if radii else {}


# --- finding entities again ----------------------------------------------------------------------


def resolve(version: StudyVersion, features: FeatureSet) -> tuple[dict[str, str], list[str]]:
    """Each entity the version names, found on the part by what it is: the same id if it still
    matches its fingerprint, else the one entity of its kind that does. What is found, as
    ``{name in the study: id on the part}``, and what is not, in words."""
    tolerance = max(features.diagonal_mm * 1e-4, 1e-3)
    found: dict[str, str] = {}
    lost: list[str] = []
    for ref, expected in version.fingerprints.items():
        still = features.get(ref) is not None
        if still and _matches(fingerprint(features, ref), expected, tolerance):
            found[ref] = ref
            continue
        if expected["kind"] == "face":
            pool = [f"face:{face_id}" for face_id in features.faces]
        else:
            pool = [f.id for f in features.features.values() if str(f.kind) == expected["kind"]]
        same = [r for r in pool if _matches(fingerprint(features, r), expected, tolerance)]
        if len(same) == 1:
            found[ref] = same[0]
        elif same:
            lost.append(f"{ref} matches {len(same)} entities on the part: {', '.join(same[:5])}")
        else:
            lost.append(f"{ref} is no longer on the part")
    return found, lost


def _matches(now: dict[str, Any], expected: dict[str, Any], tolerance: float) -> bool:
    if now["kind"] != expected["kind"]:
        return False
    if math.dist(now["centroid"], expected["centroid"]) > tolerance:
        return False
    if abs(now["area_mm2"] - expected["area_mm2"]) > max(0.001 * expected["area_mm2"], 1.0):
        return False
    a, b = now.get("diameter_mm"), expected.get("diameter_mm")
    return (a is None) == (b is None) and (a is None or abs(a - b) <= 1e-3)


# --- interfaces ---------------------------------------------------------------------------------


def interfaces(
    features: FeatureSet,
    controlled: dict[str, str] | None = None,
    datums: list[str] | None = None,
) -> list[dict]:
    """The constraints that close the part's interfaces unless the engineer opens them: every hole
    and every bore the part has, kept clear; every feature the drawing controls, citing the callout
    that controls it - ``controlled`` maps a feature to that callout's text; and every datum the
    drawing names, waiting for someone to point at its face."""
    out: list[dict] = []
    clearance = INTERFACE_CLEARANCE_MM
    for kind, what in ((FeatureKind.HOLE, "hole"), (FeatureKind.BORE, "bore")):
        refs = [f.id for f in features.of_kind(kind)]
        if refs:
            out.append(
                {
                    "kind": "interface",
                    "refs": refs,
                    "params": {"clearance_mm": clearance},
                    "strength": "hard",
                    "source": "cad",
                    "basis": f"every {what} found on the part ({len(refs)})",
                    "text": f"the {len(refs)} {what}s left as they are, {clearance:g} mm clear",
                }
            )
    for ref, callout in sorted((controlled or {}).items()):
        if features.get(ref) is None:
            continue
        out.append(
            {
                "kind": "interface",
                "refs": [ref],
                "params": {"clearance_mm": clearance},
                "strength": "hard",
                "source": "drawing",
                "basis": f"controlled on the drawing: {callout}",
                "text": f"{ref} left as it is - the drawing controls it",
            }
        )
    for letter in datums or []:
        out.append(
            {
                "kind": "datum",
                "params": {"letter": letter},
                "strength": "hard",
                "source": "drawing",
                "basis": f"the drawing names datum {letter}",
            }
        )
    return out


def _shown(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)
