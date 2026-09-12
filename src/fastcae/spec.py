"""The spec: what an engineer asked for, in their words, and the only thing designs are made from.

**Written only through :func:`write`** - by the rib card when a design is made from it, or by a
model's tools - never by hand. It refuses what it cannot stand behind:

- a quote the engineer never said - their words are kept verbatim, never paraphrased
- faces the engineer never selected
- a feature the part does not have
- a placement or lever that cites no words, so every rule can be traced to what was said

**Every change is a new version**, kept beside the old ones in ``<project>/specs/<name>.json``,
with the lines that changed. ``project.json`` names the active spec.

**Features are named by id and fingerprint** - kind, size, position - so a spec can say plainly
when the part it was written against is not the part it is being read against.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from .features import FeatureSet
from .project import Project

SPEC_DIR = "specs"


class SpecError(ValueError):
    """A spec that cannot be written, and why."""


# --- the schema ---------------------------------------------------------------------------------


class Words(BaseModel):
    """Something the engineer said, verbatim - or faces they selected on the part, which is intent
    too. Said words are ``w1, w2, ...``; selections are ``s1, s2, ...`` and carry their faces."""

    id: str
    text: str
    faces: list[int] = Field(default_factory=list)


class KeepOut(BaseModel):
    """What ribs stay clear of: named features, or every feature of some kinds on the host."""

    features: list[str] = Field(default_factory=list)
    kinds: list[str] = Field(default_factory=list)
    clearance_mm: float = Field(default=0.0, ge=0.0)
    cites: list[str] = Field(default_factory=list)


class Family(BaseModel):
    """Straight paths across the host, all at one angle."""

    angle_deg: float = 0.0
    spacing_mm: float | None = Field(default=None, gt=0.0)
    count: int | None = Field(default=None, ge=1)
    offset: float = Field(default=0.5, ge=0.0, le=1.0)


class Layout(BaseModel):
    """How rib paths are drawn on the host.

    ``parallel`` and ``grid`` are families of straight paths - one family, or several at angles
    to each other. ``radial`` is paths out from the axis of a feature, like spokes.
    """

    kind: Literal["parallel", "grid", "radial"]
    families: list[Family] = Field(default_factory=list)
    centre: str | None = None
    count: int | None = Field(default=None, ge=1)
    phase_deg: float = 0.0
    spread: Literal["round", "across"] = "round"
    """Spokes all the way round from ``phase_deg``, or fanned evenly across where ribs stand."""


class Height(BaseModel):
    """How tall ribs may stand above the host. Each end never taller than what it meets there;
    ``top`` says whether the top slopes between the two ends or is held level at the lower."""

    max_mm: float | None = Field(default=None, gt=0.0)
    not_above: list[str] = Field(default_factory=list)
    fraction: float = Field(default=1.0, gt=0.0, le=1.0)
    top: Literal["slope", "level"] = "slope"
    cites: list[str] = Field(default_factory=list)


class Section(BaseModel):
    """The rib's cross-section: a plain web, or a T - the web with a flange along its top."""

    thickness_mm: float = Field(gt=0.0)
    root_fillet_mm: float = Field(gt=0.0)
    draft_deg: float = Field(default=0.0, ge=0.0, lt=30.0)
    edge_round_mm: float = Field(default=0.0, ge=0.0)
    shape: Literal["flat", "T"] = "flat"
    flange_width_mm: float = Field(default=0.0, ge=0.0)
    flange_thickness_mm: float = Field(default=0.0, ge=0.0)
    cites: list[str] = Field(default_factory=list)


class Placement(BaseModel):
    """One group of ribs: what they stand on, what they run between, what they avoid.

    ``host`` is where they stand: a flat feature, or faces that lie in one plane - or nothing, for
    webs that hang between their ``supports`` with nothing under them. ``pull`` is the way the part
    leaves its mould, which such webs stand along when what they join allows it.
    """

    id: str
    host: list[str] = Field(default_factory=list)
    supports: list[str] = Field(default_factory=list)
    pull: list[float] | None = None
    keep_out: list[KeepOut] = Field(default_factory=list)
    layout: Layout
    height: Height = Field(default_factory=Height)
    section: Section
    connection: Literal["supports", "free"] = "supports"
    clear_of: list[str] = Field(default_factory=list)
    """Other placements whose ribs these keep clear of - placed first, their ribs keep-outs."""
    clear_of_mm: float = Field(default=0.0, ge=0.0)
    cites: list[str] = Field(default_factory=list)

    @field_validator("host", mode="before")
    @classmethod
    def _one_or_many(cls, value: Any) -> Any:
        return [value] if isinstance(value, str) else value


class Lever(BaseModel):
    """A value designs vary over: where it is in the spec, its range, and why that range."""

    path: str
    low: float
    high: float
    step: float = Field(gt=0.0)
    basis: str = ""
    cites: list[str] = Field(default_factory=list)


class Measured(BaseModel):
    """A number the spec rests on, what it was measured on, and whether it was confirmed."""

    what: str
    value: float
    on: str
    confirmed: bool = False


class Version(BaseModel):
    version: int
    created: str
    words: list[Words]
    placements: list[Placement]
    rules: dict[str, Any] = Field(default_factory=dict)
    levers: list[Lever] = Field(default_factory=list)
    measured: list[Measured] = Field(default_factory=list)
    fingerprints: dict[str, dict[str, Any]] = Field(default_factory=dict)
    note: str = ""
    changes: list[str] = Field(default_factory=list)


class Spec(BaseModel):
    name: str
    versions: list[Version] = Field(default_factory=list)

    @property
    def current(self) -> Version:
        return self.versions[-1]


# --- reading and writing ------------------------------------------------------------------------


def path_of(project: Project, name: str):
    return project.root / SPEC_DIR / f"{name}.json"


def load(project: Project, name: str) -> Spec | None:
    path = path_of(project, name)
    if not path.is_file():
        return None
    return Spec.model_validate_json(path.read_text(encoding="utf-8"))


def active(project: Project) -> Spec | None:
    """The spec ``project.json`` names, if any."""
    name = project.data().get("spec")
    return load(project, name) if name else None


def write(
    project: Project,
    name: str,
    *,
    quotes: list[str],
    said: list[str],
    placements: list[dict[str, Any]],
    features: FeatureSet,
    rules: dict[str, Any] | None = None,
    levers: list[dict[str, Any]] | None = None,
    measured: list[dict[str, Any]] | None = None,
    note: str = "",
    selected: list[int] | None = None,
    selections: list[list[int]] | None = None,
) -> Version:
    """A new version of the spec, checked, written, and made active.

    ``quotes`` are the engineer's words this version adds, each exactly as it appears in ``said``
    - what the engineer typed in this conversation. Words from earlier versions are kept.
    ``selected`` is a set of faces the engineer selected on the part, which must be among the
    ``selections`` they actually made in this conversation.
    """
    if not name or any(c in name for c in "/\\:"):
        raise SpecError(f"{name!r} is not a spec name")
    spec = load(project, name) or Spec(name=name)
    previous = spec.versions[-1] if spec.versions else None

    words, these = gather_words(
        previous.words if previous else [], quotes, said, selected, selections
    )
    word_ids = {w.id for w in words}
    added = [
        w.id for w in words if w.id not in {x.id for x in (previous.words if previous else [])}
    ]
    placements = [_expand(p, {"new": added, "these": these}) for p in placements]

    try:
        version = Version(
            version=(previous.version + 1) if previous else 1,
            created=datetime.now(UTC).isoformat(timespec="seconds"),
            words=words,
            placements=[Placement.model_validate(p) for p in placements],
            rules=dict(rules or {}),
            levers=[Lever.model_validate(v) for v in levers or []],
            measured=[Measured.model_validate(m) for m in measured or []],
            note=note,
        )
    except ValidationError as error:
        raise SpecError(str(error)) from error

    problems = _problems(version, word_ids, features)
    if problems:
        raise SpecError("; ".join(problems))

    version.fingerprints = {ref: fingerprint(features, ref) for ref in sorted(_refs(version))}
    version.changes = changes(previous, version)
    spec.versions.append(version)

    path = path_of(project, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(spec.model_dump_json(indent=2) + "\n", encoding="utf-8")
    project.write_data("spec", name)
    return version


def gather_words(
    kept: list[Words],
    quotes: list[str],
    said: list[str],
    selected: list[int] | None,
    selections: list[list[int]] | None,
) -> tuple[list[Words], list[str]]:
    """The words a new version holds - those ``kept`` from the last, and the ``quotes`` and the
    ``selected`` faces it adds - and the ids of the ones it is written from.

    A quote must appear exactly in ``said``, what the engineer typed, or be words already kept -
    checked when they were first written. Selected faces must be among the ``selections`` they
    made. Anything else is refused: a spec never puts words in their mouth.
    """
    words = list(kept)
    known = {w.text for w in words if not w.faces}
    these: list[str] = []
    for quote in quotes:
        quote = quote.strip()
        if not quote:
            continue
        if quote not in known and not any(quote in text for text in said):
            raise SpecError(f"the engineer never said {quote!r}; quote their words exactly")
        if quote not in known:
            said_so_far = sum(1 for w in words if not w.faces)
            words.append(Words(id=f"w{said_so_far + 1}", text=quote))
            known.add(quote)
        these.append(next(w.id for w in words if w.text == quote and not w.faces))
    if selected:
        chosen = sorted({int(f) for f in selected})
        made = {int(f) for selection in selections or [] for f in selection}
        missing = [f for f in chosen if f not in made]
        if missing:
            raise SpecError(
                f"the engineer never selected {', '.join(f'face:{f}' for f in missing)}"
            )
        if not any(w.faces == chosen for w in words):
            count = sum(1 for w in words if w.faces) + 1
            words.append(
                Words(
                    id=f"s{count}",
                    text="selected " + ", ".join(f"face:{f}" for f in chosen),
                    faces=chosen,
                )
            )
        these.append(next(w.id for w in words if w.faces == chosen))
    return words, these


def _expand(placement: dict[str, Any], stands_for: dict[str, list[str]]) -> dict[str, Any]:
    """A cite of ``new`` stands for every word and selection this version adds; ``these`` for
    every one it was written from, new or kept."""

    def expand(cites: list[str]) -> list[str]:
        out: list[str] = []
        for cite in cites:
            for one in stands_for.get(cite, [cite]):
                if one not in out:
                    out.append(one)
        return out

    placement = dict(placement)
    if "cites" in placement:
        placement["cites"] = expand(list(placement["cites"]))
    for key in ("height", "section"):
        if isinstance(placement.get(key), dict) and "cites" in placement[key]:
            placement[key] = {**placement[key], "cites": expand(list(placement[key]["cites"]))}
    if isinstance(placement.get("keep_out"), list):
        placement["keep_out"] = [
            {**k, "cites": expand(list(k.get("cites", [])))} for k in placement["keep_out"]
        ]
    return placement


def _refs(version: Version) -> set[str]:
    refs: set[str] = set()
    for p in version.placements:
        refs |= {*p.host, *p.supports, *p.height.not_above}
        refs |= {f for k in p.keep_out for f in k.features}
        if p.layout.centre:
            refs.add(p.layout.centre)
    for m in version.measured:
        refs.add(m.on)
    return refs


def _problems(version: Version, word_ids: set[str], features: FeatureSet) -> list[str]:
    problems = []
    missing = sorted(r for r in _refs(version) if features.get(r) is None)
    if missing:
        problems.append(
            f"the part has no {', '.join(missing)} - ids look like planar_group:114, hole:3, "
            "bore:196 or face:1453"
        )
    for p in version.placements:
        if not p.cites:
            problems.append(f"placement {p.id} cites no words")
        cited = [
            *p.cites,
            *p.height.cites,
            *p.section.cites,
            *(c for k in p.keep_out for c in k.cites),
        ]
        unknown = sorted({c for c in cited if c not in word_ids})
        if unknown:
            problems.append(f"placement {p.id} cites {', '.join(unknown)}, which are not words")
        if p.layout.kind == "radial" and (p.layout.centre is None or p.layout.count is None):
            problems.append(f"placement {p.id}: a radial layout needs a centre and a count")
        if p.layout.kind in ("parallel", "grid"):
            if not p.layout.families:
                problems.append(f"placement {p.id}: a {p.layout.kind} layout needs its families")
            for family in p.layout.families:
                if (family.spacing_mm is None) == (family.count is None):
                    problems.append(
                        f"placement {p.id}: each family takes a spacing or a count, not both"
                    )
    for lever in version.levers:
        if not lever.cites:
            problems.append(f"lever {lever.path} cites no words")
        if lever.low > lever.high:
            problems.append(f"lever {lever.path}: low is above high")
    return problems


# --- fingerprints -------------------------------------------------------------------------------


def fingerprint(features: FeatureSet, feature_id: str) -> dict[str, Any]:
    """What identifies a feature besides its number: kind, size, where it is."""
    f = features.get(feature_id)
    assert f is not None
    return {
        "kind": str(f.kind),
        "area_mm2": round(f.area_mm2, 1),
        "diameter_mm": None if f.diameter_mm is None else round(f.diameter_mm, 3),
        "centroid": [round(v, 2) for v in f.centroid],
    }


def rebind(version: Any, features: FeatureSet) -> list[str]:
    """Where the features a version names - by ``version.fingerprints`` - no longer match the part
    it is read against. Empty: all match."""
    problems = []
    tolerance = max(features.diagonal_mm * 1e-4, 1e-3)
    for ref, expected in version.fingerprints.items():
        if features.get(ref) is None:
            problems.append(f"{ref} is no longer on the part")
            continue
        now = fingerprint(features, ref)
        if now["kind"] != expected["kind"]:
            problems.append(f"{ref} was a {expected['kind']}, now a {now['kind']}")
        elif math.dist(now["centroid"], expected["centroid"]) > tolerance:
            problems.append(f"{ref} has moved")
        elif abs(now["area_mm2"] - expected["area_mm2"]) > max(0.001 * expected["area_mm2"], 1.0):
            problems.append(f"{ref} has changed size")
    return problems


# --- what changed -------------------------------------------------------------------------------


def changes(previous: BaseModel | None, version: BaseModel) -> list[str]:
    """What this version changes, one line each, as ``path: old -> new``."""
    if previous is None:
        return ["first version"]
    old = _flat(previous.model_dump(exclude={"version", "created", "fingerprints", "changes"}))
    new = _flat(version.model_dump(exclude={"version", "created", "fingerprints", "changes"}))
    lines = []
    for key in sorted(set(old) | set(new)):
        if old.get(key) != new.get(key):
            lines.append(f"{key}: {json.dumps(old.get(key))} -> {json.dumps(new.get(key))}")
    return lines


def _flat(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            out.update(_flat(v, f"{prefix}.{k}" if prefix else str(k)))
        return out
    if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
        out = {}
        for i, v in enumerate(value):
            label = v.get("id", i) if isinstance(v, dict) else i
            out.update(_flat(v, f"{prefix}[{label}]"))
        return out
    return {prefix: value}
