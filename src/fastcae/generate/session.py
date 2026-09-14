"""The rib work on one open project: the draft of the study's next version, the study it is
accepted as, and the designs made from that.

What the routes hold between requests, and what the agent's tools work on; nothing here needs an
agent. **Design a variant is the one structured view of the study**, and this is what it shows: the
draft, read back from the study's current version when the project opens, changed by the agent
from the engineer's words, compiled on every change into the version it would write - checked as
any version is, with the part's interfaces closed - and written only when the engineer accepts it.
Undo reads it back again.

**The draft holds what was said, never what was read.** Each block keeps the entities its ribs
stand on and end on - or none, to read them off the part - the settings the words gave, and the
part's suggestions the engineer took out. Everything else a block needs is read off the part again
on every change (:func:`.blocks.fill`), so a draft never carries a stale reading. Beside the blocks:
the rules from the words, preferences, objectives, the pull and the target.

Designs are made from the study, never from the draft: the study is the record of what was asked
for. **Go** makes many at once - as many as the study's target asks for, thousands - points spread
over what the study leaves free, every block of each placed together and screened in a fraction of
a second, the ones worth building kept and written to the project's ``designs`` folder, for the
engineer to look through and build.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
import re
import shutil
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import ValidationError

from .. import knowledge, variants
from .. import study as studies
from ..extract import Extraction
from ..features import FeatureKind
from ..project import Project
from ..spec import (
    HoleSet,
    MaterialChoice,
    Offset,
    Placement,
    SpecError,
    Version,
    Words,
    gather_words,
)
from .blocks import WEBS_JOIN, fill, start
from .intent import IntentError, Made, Opened, make
from .placement import Drilled, Placed, _Faces, axis_of, host_of, place_all
from .repair import repair
from .screen import Screened, face_offsets, measure_walls, screen
from .slots import CLOSED, SETTING_LABELS, names
from .variety import most_varied, outlines, plane_of, planned

STUDY_NAME = "ribs"
REF = re.compile(r"\b[a-z_]+:\d+\b")
# The most the agent may ask the engineer to look at, in lines.
ATTENTION = 3
# Rules that hold for the whole study, whichever block suggested them.
STUDY_WIDE = ("smallest_radius", "draft_at_least")
# How many designs Go makes when neither it nor the study's target is told.
GO = 24
# How many points Go tries, at most, for every design it is asked for: the rest are screened out.
TRIES_PER_DESIGN = 4
# How many points of each block, alone, Go keeps to make designs from - a quarter as many as the
# designs asked for, within these - and how many it tries for each it keeps, at most.
POOL = (32, 1024)
POOL_TRIES = 4
# How many other points of a block Go tries in a design screened out by that block alone.
REPAIRS = 3
# The root fillet a part is opened at when nothing in the study sets one: no ribs, only holes and
# faces moved.
OPEN_AT_MM = 6.0
# Where Go keeps the designs it made: beside the folder projects live in - the repository's, for a
# project in ``assets/`` - a folder per project, then one per run.
ARCHIVE_DIR = "_archived_designs"


def _nothing() -> dict[str, Any]:
    return {"blocks": [], "rules": [], "prefer": [], "objectives": [], "pull": None, "target": None}


@dataclass
class Session:
    """What the rib work on one open project holds."""

    project: Project
    extraction: Extraction
    said: list[str] = field(default_factory=list)
    """Words the engineer wrote to the agent, in order."""
    selections: list[list[int]] = field(default_factory=list)
    """Every set of faces the engineer had selected when they wrote, in order."""
    draft: dict[str, Any] = field(default_factory=_nothing)
    """The study's next version as it is being edited: ``blocks`` - each with ``id``, ``add``,
    ``support``, ``anchors``, ``span``, ``settings`` the words gave, the part's suggestions
    ``relaxed`` and ``cites`` - and ``rules``, ``prefer``, ``objectives``, ``pull``, ``target``."""
    heard: list[str] = field(default_factory=list)
    """The engineer's words the draft rests on, since the study was last written."""
    attention: list[str] = field(default_factory=list)
    """What the agent asked the engineer to look at before accepting - a few lines at most."""
    questions: int = 0
    """Questions the agent has asked of the part since the engineer last wrote, or it last changed
    the study."""
    measure: _Faces | None = None
    opened: dict[tuple[str, float], Opened] = field(default_factory=dict)
    opening: dict[tuple[str, float], threading.Lock] = field(default_factory=dict)
    """One lock a grid: a second request for the part on a grid waits for the first to open it."""
    memo: dict = field(default_factory=dict)
    """What each block reads off the part once, for every design placed after: where it stands,
    what it keeps clear of, what it ends on."""
    made: Made | None = None
    designs: list[dict] = field(default_factory=list)
    """What Go made: each design's values, and what became of every block's paths."""
    archive: Path | None = None
    """Where Go wrote the designs it kept."""
    loaded: dict[str, tuple[Any, list[dict]]] = field(default_factory=dict)
    """Runs of Go read back from where they are kept: the study version each was made from, and
    its designs - the last few looked at."""
    changed: set[str] = field(default_factory=set)
    """What changed since the interface last asked - ``draft``, ``study``, ``design``."""
    variant: str | None = None
    """The variant being authored on Design a variant - its id, new or kept in the library - whose
    one block the draft is; or None, and the draft is the study's next version, as the agent
    writes it."""

    def __post_init__(self) -> None:
        load(self)


# --- the draft, read and written -----------------------------------------------------------------


def _name(session: Session) -> str:
    """What the draft is written as: the variant being authored, or the study."""
    return session.variant or STUDY_NAME


def _folder(session: Session) -> str:
    return variants.FOLDER if session.variant else studies.STUDY_DIR


def _saved(session: Session) -> studies.StudyVersion | None:
    """What the draft is read back from: the variant as kept, or the study as accepted."""
    if session.variant:
        kept_variant = variants.load(session.project, session.variant)
        return kept_variant.current if kept_variant is not None else None
    study = studies.active(session.project)
    return study.current if study is not None else None


def _build(session: Session, entries: dict[str, Any]) -> studies.StudyVersion:
    """The version the draft would write, checked - a variant's rules may name the ribs and holes
    of any other in the library."""
    known = variants.kinds(session.project, but=session.variant) if session.variant else None
    return studies.build(
        session.project, _name(session), folder=_folder(session), known_blocks=known, **entries
    )


def load(session: Session) -> None:
    """Read the draft back from the study's current version - or the variant's, when one is being
    authored - forgetting what was not accepted."""
    session.draft, session.heard, session.attention = _nothing(), [], []
    version = _saved(session)
    if version is not None:
        draft = session.draft
        for block in version.blocks:
            where = block.where
            draft["blocks"].append(
                {
                    "id": block.id,
                    "add": block.add,
                    "support": [] if "support" in where.read_off else list(where.support),
                    "anchors": [] if "anchors" in where.read_off else list(where.anchors),
                    "other_side": list(where.other_side),
                    "span": where.span,
                    "settings": {
                        name: _as_setting(domain)
                        for name, domain in block.free.items()
                        if domain.source in studies.ASKED
                    },
                    "relaxed": list(block.relaxed),
                    "cites": list(block.cites),
                }
            )
        draft["rules"] = [
            _kept(c)
            for c in version.constraints
            if c.by == "words" or (c.by == "" and c.source in studies.ASKED)
        ]
        draft["prefer"] = [_kept(p) for p in version.prefer]
        draft["objectives"] = [_kept(o) for o in version.objectives]
        if version.pull is not None and version.pull.source in studies.ASKED:
            draft["pull"] = version.pull.model_dump()
        draft["target"] = version.target.model_dump()
    session.changed.add("draft")


def view(session: Session) -> dict:
    """The draft as Design a variant shows it: every block - what its ribs stand on, end on and keep
    clear of, each entity by name; its settings, fixed or what they may take and who said so; its
    rules; what is needed and what cannot be built yet - each marked where it differs from the
    study as accepted; then the rules for the whole study, the part's interfaces and the rest."""
    try:
        entries, reports = _entries(session)
        version = _build(session, entries)
    except (studies.StudyError, ValueError) as error:
        return _refused(session, str(error))
    return _read(session, version, reports)


def edit(
    session: Session,
    quotes: list[str],
    blocks: list[dict[str, Any]] | None = None,
    rules: list[dict[str, Any]] | None = None,
    drop: list[str] | None = None,
    confirm: list[str] | None = None,
    prefer: list[dict[str, Any]] | None = None,
    objectives: list[dict[str, Any]] | None = None,
    pull: dict[str, Any] | None = None,
    target: dict[str, Any] | None = None,
    attention: list[str] | None = None,
    by: str = "words",
) -> dict:
    """The draft changed from the engineer's words - their ``quotes``, exactly - or, ``by`` "you",
    by their hand on Design a variant, the quote saying what they did there.

    ``blocks`` add or change blocks: each with an ``id`` to change one, or none for a new one;
    ``add``; ``stand_on`` - entities, or none for webs with nothing under them - and ``end_on`` -
    entities, or none to read them off the part; ``span``; ``settings`` by name, each a
    ``value``, a ``low`` and ``high``, or ``options``, or None to hand it back to the part;
    ``rules`` that hold for that block alone; ``remove`` to take the block out. ``rules`` - for
    one block when they name it, else for every block, now and to come - ``prefer`` and
    ``objectives`` are added; ``drop`` takes out, by id, rules the words put in - or a rule the
    part suggested; ``confirm`` makes rules the part suggested the engineer's own, as they stand.
    The part's interfaces are closed by the platform whatever is sent. Checked as a version is;
    refused, nothing moves. The card as :func:`view` gives it, or ``{"refused": why}``."""
    quotes = [q.strip() for q in quotes if q and q.strip()]
    if not quotes:
        return {"refused": "quote the engineer's words this rests on, exactly as they wrote them"}
    saved = _saved(session)
    kept_words = saved.words if saved else []
    try:
        gather_words(kept_words, quotes, list(session.said), None, None)
    except SpecError as error:
        return {"refused": str(error)}
    known = {w.id for w in kept_words} | {"these", "new"}

    before = (copy.deepcopy(session.draft), list(session.heard), list(session.attention))
    try:
        if drop or confirm:
            _drop_and_confirm(session, list(drop or []), list(confirm or []), known)
        draft = session.draft
        for change in blocks or []:
            block_id = _change_block(draft, change, by)
            for rule in change.get("rules") or []:
                if rule.get("kind") not in CLOSED:
                    _add_rule(draft, _from_words({**rule, "block": block_id}, known, by))
        for rule in rules or []:
            if rule.get("kind") not in CLOSED:
                _add_rule(draft, _from_words(rule, known, by))
        draft["prefer"] += [_from_words(p, known, by) for p in prefer or []]
        draft["objectives"] += [_from_words(o, known, by) for o in objectives or []]
        if pull is not None:
            given = _from_words(pull, known, by)
            if given.get("source") in ("default", "words"):
                given["source"] = by
            draft["pull"] = given
        if target is not None:
            draft["target"] = {**(draft["target"] or {}), **target}
        # What the engineer should look at stays until an edit gives it again - or clears it with
        # none; the agent is shown it after every edit, to check it still holds.
        if attention is not None:
            session.attention = [line.strip() for line in attention if line.strip()][:ATTENTION]
        session.heard = list(dict.fromkeys([*session.heard, *quotes]))
        card = view(session)
    except (ValueError, ValidationError) as error:
        session.draft, session.heard, session.attention = before
        return {"refused": str(error)}
    if card.get("refused"):
        session.draft, session.heard, session.attention = before
        return {"refused": card["cannot"]}
    session.changed.add("draft")
    return card


def drop_rule(session: Session, ref: str) -> None:
    """Take out, by hand, a rule the words put in, or one the part suggested for a block - or a
    preference or objective. Raises ValueError for one that cannot be taken out here."""
    _drop_and_confirm(session, [ref], [], set())
    session.changed.add("draft")


# What a block added by hand adds, by what the card calls it: webs are ribs with nothing under them.
BY_HAND = {"ribs": "ribs", "webs": "ribs", "thicken": "thicken", "holes": "holes", "material": ""}
CARD = "By hand:"


def _no_floor(session: Session, refs: list[str]) -> str | None:
    """Why faces are no floor for ribs to stand on - curved, or flat but not in one plane - in
    words the engineer can act on; None when they are one."""
    features = session.extraction.features
    assert features is not None
    host, _ = host_of(features, refs)
    if host is not None:
        return None
    curved = [
        ref
        for ref in refs
        if (f := features.get(ref)) is not None
        and f.kind != FeatureKind.PLANAR_GROUP
        and not (f.kind == FeatureKind.FACE and f.metrics.get("flat") == 1.0)
    ]
    if curved:
        named = ", ".join(curved[:3]) + (f" and {len(curved) - 3} more" if len(curved) > 3 else "")
        which = "the face selected" if len(refs) == 1 else f"{len(curved)} of the {len(refs)}"
        said = f"{which} {'is' if len(curved) == 1 else 'are'} curved ({named})"
    else:
        said = "the faces selected are flat, but not in one plane"
    return (
        f"ribs stand on flat faces in one plane for now, and {said}. Select a floor or a plate - "
        "one flat face, or flat faces in one plane - to stand them on; or choose webs between, "
        "to join faces with nothing under them"
    )


def hand(session: Session, action: dict[str, Any], selected: list[int] | None = None) -> dict:
    """The draft changed by the engineer's hand on Design a variant, as :func:`edit` changes it from
    their words: what was done is said in words - "By hand: ..." - kept among the
    study's words, and everything it sets is theirs. ``selected`` is the faces selected on the
    part, which an action takes when it names nothing.

    ``action`` is one of: ``add`` a block - ``ribs`` standing on what is selected, ``webs``
    between it, faces to ``thicken``, a plate to cut ``holes`` in, or the ``material``;
    ``stand_on`` or ``end_on`` - a block's entities, or none to read them off the part;
    ``other_side`` - what webs run to from what they end on, never within either side;
    ``setting`` - a ``value``, a ``low`` and ``high`` with a ``step``, some ``options``, or none
    to hand it back to the part; ``keep_clear`` - of entities, or of other blocks' ``ribs:b1`` and
    ``holes:b2``, by ``clearance_mm``; ``remove`` a block; ``confirm`` a rule the part suggested,
    by id; ``designs`` - how many, from which ``seed``. The card, or ``{"refused": why}``."""
    kind = action.get("action")
    faces = [f"face:{f}" for f in sorted({int(f) for f in selected or []})]
    refs = [str(r) for r in action["refs"]] if action.get("refs") is not None else faces
    block = action.get("block")
    ids = [b["id"] for b in session.draft["blocks"]]
    if kind != "add" and kind not in ("confirm", "designs", "drop") and block not in ids:
        return {"refused": f"there is no block {block} - blocks: {', '.join(ids) or 'none yet'}"}
    change: dict[str, Any] = {}
    if kind == "add":
        what = str(action.get("add") or "")
        if what not in BY_HAND:
            return {"refused": f"a block adds {', '.join(BY_HAND)} - not {what!r}"}
        if session.variant and what == "material":
            return {"refused": "a part is cast in one material, which no variant changes"}
        if session.variant and ids:
            return {
                "refused": "a variant is one change in one place: create this one, then start "
                "another for the next"
            }
        if what != "material" and not refs:
            return {"refused": "select the faces on the part first, or name them"}
        floor = _no_floor(session, refs) if what == "ribs" else None
        if floor:
            return {"refused": floor}
        casting = [b["id"] for b in session.draft["blocks"] if b.get("add") == "material"]
        if what == "material" and casting:
            return {
                "refused": f"{casting[0]} already says what the part is cast in - a part is cast "
                "in one material: narrow its choices there"
            }
        number = 1
        while f"b{number}" in ids:
            number += 1
        new = session.variant or f"b{number}"
        said = {
            "ribs": f"add {new}, ribs standing on {_and(refs)}",
            "webs": f"add {new}, webs between {_and(refs)} with nothing under them",
            "thicken": f"add {new}, {_and(refs)} made thicker or thinner",
            "holes": f"add {new}, holes through {_and(refs)}",
            "material": f"add {new}, what the part is cast in",
        }[what]
        added: dict[str, Any] = {"id": new, "add": BY_HAND[what] or "material"}
        if what == "webs":
            added.update(stand_on=[], end_on=refs)
        elif what != "material":
            added["stand_on"] = refs
        change["blocks"] = [added]
    elif kind in ("stand_on", "end_on"):
        where = "stands on" if kind == "stand_on" else "ends on"
        said = f"{block} {where} {_and(refs) if refs else 'what is read off the part'}"
        change["blocks"] = [{"id": block, kind: refs}]
    elif kind == "other_side":
        # What the webs run to, from what they end on: from one side to the other.
        refs = [str(r) for r in action.get("refs") or []]
        said = f"{block} runs to {_and(refs)}" if refs else f"{block} runs between any of its ends"
        change["blocks"] = [{"id": block, "other_side": refs}]
    elif kind == "setting":
        name = str(action.get("name") or "")
        if not name:
            return {"refused": "which setting?"}
        told = {k: action[k] for k in ("value", "low", "high", "step", "options") if k in action}
        told = {k: v for k, v in told.items() if v is not None}
        if name == "centre":
            # Spokes turn about an axis: a thing with none has no middle for them to fan from.
            features = session.extraction.features
            assert features is not None
            asked = [str(o) for o in told.get("options") or [told.get("value")] if o is not None]
            flat = [
                ref
                for ref in asked
                if (feature := features.get(ref)) is None or axis_of(features, feature) is None
            ]
            if flat:
                return {
                    "refused": f"{_and(flat)} {'has' if len(flat) == 1 else 'have'} no axis: "
                    "spokes turn only about round things - a boss, a bore, a ring's round faces"
                }
        label = SETTING_LABELS.get(name, name.replace("_", " "))
        said = f"{block} {label} {_told(told)}"
        change["blocks"] = [{"id": block, "settings": {name: told or None}}]
    elif kind == "keep_clear":
        if not refs:
            return {"refused": "keep clear of what? Select it on the part, or name it"}
        clearance = float(action.get("clearance_mm") or 0.0)
        said = f"{block} keeps {clearance:g} mm clear of {_and(refs)}"
        rule = {"kind": "keep_clear_of", "refs": refs, "params": {"clearance_mm": clearance}}
        change["blocks"] = [{"id": block, "rules": [rule]}]
    elif kind == "rule":
        rule_kind = str(action.get("kind") or "")
        if rule_kind not in studies.OFFERED:
            return {"refused": f"a variant holds {', '.join(studies.OFFERED)} - not {rule_kind!r}"}
        needs = studies.KINDS[rule_kind]
        params = {k: v for k, v in (action.get("params") or {}).items() if v is not None}
        named = refs if needs.names else []
        if needs.names and not named:
            return {"refused": "which faces? Select them on the part, or name them"}
        lacking = [p for p in needs.needs if p not in params]
        if lacking:
            return {"refused": f"{rule_kind.replace('_', ' ')} needs {', '.join(lacking)}"}
        rule = {"kind": rule_kind, "refs": named, "params": params}
        said = f"{block} holds: {studies.said(studies.Constraint(**rule))}"
        change["blocks"] = [{"id": block, "rules": [rule]}]
    elif kind == "drop":
        said = f"take out {action.get('rule')}"
        change["drop"] = [str(action.get("rule"))]
    elif kind == "remove":
        said = f"take out {block}"
        change["blocks"] = [{"id": block, "remove": True}]
    elif kind == "confirm":
        said = f"keep {action.get('rule')} as mine"
        change["confirm"] = [str(action.get("rule"))]
    elif kind == "designs":
        target = {k: int(action[k]) for k in ("n", "seed") if action.get(k) is not None}
        if not target:
            return {"refused": "how many designs, or from which seed?"}
        said = ", ".join(f"{k} {v}" for k, v in target.items()).replace("n ", "designs ", 1)
        change["target"] = target
    else:
        return {"refused": f"nothing is done by hand as {kind!r}"}
    words = f"{CARD} {said}"
    session.said.append(words)
    named = {int(r.split(":", 1)[1]) for r in refs if r.startswith("face:")}
    if named:
        session.selections.append(sorted(named))
    card = edit(session, [words], by="you", **change)
    if card.get("refused"):
        session.said.pop()
        if named:
            session.selections.pop()
    return card


def _and(refs: list[str]) -> str:
    if len(refs) < 2:
        return refs[0] if refs else "nothing"
    return ", ".join(refs[:-1]) + " and " + refs[-1]


def _told(setting: dict[str, Any]) -> str:
    """A setting given by hand, in words."""
    if not setting:
        return "handed back to the part"
    if setting.get("value") is not None:
        return f"fixed at {_value(setting['value'])}"
    if setting.get("options") is not None:
        return "one of " + ", ".join(_value(o) for o in setting["options"])
    low, high = setting.get("low"), setting.get("high")
    step = f" in steps of {_value(setting['step'])}" if setting.get("step") else ""
    return f"from {_value(low)} to {_value(high)}{step}"


def accept(session: Session) -> dict:
    """Write the draft as the study's next version - checked again - and read the draft back from
    it. ``{"version": n}``, or ``{"cannot": why}``."""
    try:
        entries, reports = _entries(session)
        version = _build(session, entries)
        note = "; ".join(_read(session, version, reports)["changes"])
        written = studies.write(session.project, STUDY_NAME, **entries, note=note[:400])
    except (studies.StudyError, ValueError) as error:
        return {"cannot": str(error)}
    load(session)
    session.changed.add("study")
    return {"version": written.version}


def undo(session: Session) -> dict:
    """Forget what was not accepted: the draft as the study has it."""
    load(session)
    return view(session)


def closed_interfaces(extraction: Extraction) -> list[dict]:
    """The part's interfaces, closed: its holes and bores, what the drawing controls - with the
    evidence it controls them by - and the datums the drawing names."""
    assert extraction.features is not None
    controlled = {
        ref: "; ".join(e.render() for e in fact.evidence) or "a toleranced dimension"
        for ref, fact in extraction.controlled.items()
        if fact.value
    }
    datums = extraction.drawing.datums() if extraction.drawing is not None else []
    return studies.interfaces(extraction.features, controlled, datums)


# --- compiling the draft -------------------------------------------------------------------------


def _measure(session: Session) -> _Faces:
    if session.measure is None:
        assert session.extraction.tess is not None
        session.measure = _Faces(session.extraction.tess)
    return session.measure


def _entries(session: Session) -> tuple[dict[str, Any], dict[str, dict]]:
    """The version the draft would write - every block filled from the part round what the words
    gave, the rules from the words, those the part suggests for each block less what the engineer
    took out, the part's interfaces closed - and, by block, what is needed or cannot be built."""
    draft = session.draft
    floor = next(
        (float(r["params"]["radius_mm"]) for r in draft["rules"] if r["kind"] == "smallest_radius"),
        None,
    )
    exit_along = _measure(session).exit_along
    blocks: list[dict] = []
    suggested: list[dict] = []
    measured: list[dict] = []
    pull = None
    reports: dict[str, dict] = {}
    for block in draft["blocks"]:
        fixed = {n: s for n, s in block["settings"].items() if _single(s) is not None}
        # Both sides of what webs run between are read off the part together: it is all of them
        # they stand among.
        other = list(block.get("other_side") or [])
        ends = list(dict.fromkeys([*block["anchors"], *other]))
        filled = fill(
            session.extraction,
            exit_along,
            {
                "add": block.get("add", "ribs"),
                "support": block["support"],
                "anchors": ends,
                "other_side": other,
                "given": {
                    **{n: _fixed_domain(s) for n, s in fixed.items()},
                    **{n: _provisional(s) for n, s in block["settings"].items() if n not in fixed},
                },
            },
            floor,
        )
        free = filled["free"]
        if session.variant and free is not None:
            # A variant authored on the card starts simple, where nothing was set by hand.
            start(free, block.get("add", "ribs"), block["settings"])
        for name, setting in block["settings"].items():
            free[name] = {"unit": _unit(name), **_domain(setting, free.get(name, {}))}
        # Every choice the part offers for what the engineer narrowed, so the card can offer them
        # still: the part read again without those choices.
        narrowed = [n for n, s in block["settings"].items() if _choices_given(s)]
        choices: dict[str, list] = {}
        if narrowed:
            offered = fill(
                session.extraction,
                exit_along,
                {
                    "add": block.get("add", "ribs"),
                    "support": block["support"],
                    "anchors": ends,
                    "other_side": other,
                    "given": {
                        n: _fixed_domain(s) if n in fixed else _provisional(s)
                        for n, s in block["settings"].items()
                        if n not in narrowed
                    },
                },
                floor,
            )
            if session.variant and offered.get("free") is not None:
                start(offered["free"], block.get("add", "ribs"), {})
            choices = {
                n: list(offered["free"][n]["options"])
                for n in narrowed
                if (offered.get("free") or {}).get(n, {}).get("options")
            }
        where = {**filled["where"], "span": block.get("span") or "union", "other_side": other}
        where["anchors"] = [a for a in where.get("anchors", []) if a not in other]
        blocks.append(
            {
                "id": block["id"],
                "add": block.get("add", "ribs"),
                "where": where,
                "free": free,
                "cites": block.get("cites") or ["these"],
                "relaxed": list(block.get("relaxed", [])),
            }
        )
        relaxed = [_signature(r) for r in block.get("relaxed", [])]
        for rule in filled["rules"]:
            scoped = dict(rule)
            if rule["kind"] not in STUDY_WIDE:
                scoped["block"] = block["id"]
            # The same rule suggested for another block is that block's; only a rule for the
            # whole study is said once.
            if _signature(scoped) in relaxed or any(
                _signature(scoped) == _signature(s) and scoped.get("block") == s.get("block")
                for s in suggested
            ):
                continue
            if any(_same(scoped, words) for words in draft["rules"]):
                continue
            suggested.append(scoped)
        measured += filled["measured"]
        pull = pull or filled["pull"]
        reports[block["id"]] = {
            **{k: filled[k] for k in ("needed", "problems", "cannot", "note")},
            "choices": choices,
        }
        webs = block.get("add", "ribs") == "ribs" and not block["support"]
        if session.variant and webs and not other:
            # Webs on the card run from one side to another, never within the faces of one: what
            # they join is both sides - the other still to add, which is all they need said.
            reports[block["id"]]["needed"] = [
                *(n for n in reports[block["id"]]["needed"] if n != WEBS_JOIN),
                "what the webs run to - select those faces and add them as the other side",
            ]
    suggested += _holes_clear_of_ribs(draft, blocks)
    entries = {
        "quotes": list(session.heard),
        "said": list(session.said),
        "selected": _selected(session) or None,
        "selections": [list(s) for s in session.selections],
        "features": session.extraction.features,
        "blocks": blocks,
        "constraints": [
            *({**r, "by": "words"} for r in draft["rules"]),
            *suggested,
            *closed_interfaces(session.extraction),
        ],
        # A variant is one change and every rule it holds - no pull while mould release waits for
        # one, nothing preferred, no target: how many designs is the campaign's to say.
        "prefer": [] if session.variant else list(draft["prefer"]),
        "objectives": [] if session.variant else list(draft["objectives"]),
        "pull": None if session.variant else (draft["pull"] or pull),
        "target": None if session.variant else draft["target"],
        "measured": measured,
    }
    return entries, reports


def _holes_clear_of_ribs(draft: dict[str, Any], blocks: list[dict]) -> list[dict]:
    """Holes keep a ligament of metal from the ribs of every block of ribs - placed after them, so
    holes go where ribs leave room - unless the words have those ribs keep clear of the holes
    instead, or the engineer took the rule out."""
    ribs = [b["id"] for b in blocks if b["add"] == "ribs"]
    out = []
    for block in blocks:
        if block["add"] != "holes" or not ribs:
            continue
        mine = f"{studies.HOLES}{block['id']}"
        others = [
            r
            for r in ribs
            if not any(w.get("block") == r and mine in w.get("refs", []) for w in draft["rules"])
        ]
        ligament = block["free"].get("ligament_mm") or {}
        clearance = ligament.get("suggested", ligament.get("low"))
        if not others or clearance is None:
            continue
        rule = {
            "kind": "keep_clear_of",
            "refs": [f"{studies.RIBS}{r}" for r in others],
            "params": {"clearance_mm": float(clearance)},
            "block": block["id"],
            "strength": "assumed",
            "by": "part",
            "basis": "a hole keeps a ligament of metal from any rib, as from another hole",
        }
        relaxed = [_signature(r) for r in block.get("relaxed", [])]
        if _signature(rule) in relaxed or any(_same(rule, w) for w in draft["rules"]):
            continue
        out.append(rule)
    return out


def _selected(session: Session) -> list[int]:
    """The faces the blocks name that the engineer selected on the part."""
    made = {int(f) for s in session.selections for f in s}
    named = {
        int(ref.split(":", 1)[1])
        for block in session.draft["blocks"]
        for ref in [*block["support"], *block["anchors"]]
        if ref.startswith("face:")
    }
    return sorted(named & made)


def _change_block(draft: dict[str, Any], change: dict[str, Any], by: str = "words") -> str:
    """One block added, changed or taken out, as the words - or the engineer's hand - ask. Its
    id."""
    ids = [b["id"] for b in draft["blocks"]]
    wanted = change.get("id")
    if change.get("remove"):
        if wanted not in ids:
            raise ValueError(f"there is no block {wanted} to take out - blocks: {', '.join(ids)}")
        draft["blocks"] = [b for b in draft["blocks"] if b["id"] != wanted]
        kept = []
        for rule in draft["rules"]:
            if rule.get("block") == wanted:
                continue
            refs = [r for r in rule.get("refs", []) if studies.ribs_of(r) != wanted]
            if rule.get("refs") and not refs:
                continue
            kept.append({**rule, "refs": refs})
        draft["rules"] = kept
        return wanted
    if wanted is None or wanted not in ids:
        number = 1
        while f"b{number}" in ids:
            number += 1
        block = {
            "id": wanted or f"b{number}",
            "add": change.get("add") or "ribs",
            "support": [],
            "anchors": [],
            "span": "union",
            "settings": {},
            "relaxed": [],
            "cites": ["these"],
        }
        draft["blocks"].append(block)
    else:
        block = next(b for b in draft["blocks"] if b["id"] == wanted)
        block["cites"] = list(dict.fromkeys([*block.get("cites", []), "these"]))
    if change.get("add"):
        block["add"] = change["add"]
    if change.get("stand_on") is not None:
        block["support"] = list(change["stand_on"])
    if change.get("end_on") is not None:
        block["anchors"] = list(change["end_on"])
    if change.get("other_side") is not None:
        block["other_side"] = list(change["other_side"])
    if change.get("span"):
        block["span"] = change["span"]
    for name, setting in (change.get("settings") or {}).items():
        if setting is None:
            block["settings"].pop(name, None)
            continue
        given = {k: v for k, v in setting.items() if v is not None and k not in ("cites", "source")}
        if not given:
            block["settings"].pop(name, None)
            continue
        block["settings"][name] = {**given, "source": by, "cites": ["these"]}
    return block["id"]


def _drop_and_confirm(session: Session, drop: list[str], confirm: list[str], known) -> None:
    """Rules taken out, and suggested rules made the engineer's, by the ids the draft shows them
    under. A rule the words put in is taken out of the draft; one the part suggested for a block
    is kept out of that block from now on; the part's interfaces stay closed."""
    entries, _ = _entries(session)
    version = _build(session, entries)
    by_id = {c.id: c for c in version.constraints}
    draft = session.draft
    words = [c for c in version.constraints if c.by == "words"]
    lists = {"p": draft["prefer"], "o": draft["objectives"]}
    gone: dict[str, set[int]] = {"p": set(), "o": set()}
    dropped_words: set[int] = set()
    for ref in [*drop, *confirm]:
        key, number = ref[:1], ref[1:]
        if key in lists and number.isdigit() and 1 <= int(number) <= len(lists[key]):
            if ref in confirm:
                raise ValueError(f"{ref} is the engineer's already")
            gone[key].add(int(number) - 1)
            continue
        rule = by_id.get(ref)
        if rule is None:
            raise ValueError(f"there is no {ref} - rules are c1 onwards, as Design a variant shows")
        if rule.by == "platform":
            raise ValueError(f"{ref} closes one of the part's interfaces, which stay closed")
        if rule.by == "words":
            if ref in confirm:
                raise ValueError(f"{ref} is the engineer's already")
            dropped_words.add(words.index(rule))
            continue
        _relax(draft, rule)
        if ref in confirm:
            mine = _kept(rule)
            mine.update(strength="hard", source="words", cites=["these"])
            draft["rules"].append(_from_words(mine, known))
    draft["rules"] = [r for i, r in enumerate(draft["rules"]) if i not in dropped_words]
    for key, items in lists.items():
        items[:] = [item for index, item in enumerate(items) if index not in gone[key]]


def _relax(draft: dict[str, Any], rule: studies.Constraint) -> None:
    """A rule the part suggested, kept out of its block - of every block, for one that holds for
    the whole study."""
    mark = {"kind": rule.kind, "refs": sorted(rule.refs)}
    for block in draft["blocks"]:
        if rule.block in (None, block["id"]) and mark not in block["relaxed"]:
            block["relaxed"].append(mark)


def _signature(rule: dict[str, Any]) -> tuple:
    return (rule["kind"], tuple(sorted(rule.get("refs", []))))


def _same(suggested: dict[str, Any], words: dict[str, Any]) -> bool:
    """Whether a rule the words put in says what a suggested one does - the words' then stands."""
    return _signature(suggested) == _signature(words) and words.get("block") in (
        None,
        suggested.get("block"),
    )


def _unit(name: str) -> str:
    """A setting's unit, as its name carries it."""
    return "mm" if name.endswith("_mm") else "°" if name.endswith("_deg") else ""


def _single(setting: dict[str, Any]) -> Any:
    if setting.get("value") is not None:
        return setting["value"]
    options = setting.get("options")
    if options is not None and len(options) == 1:
        return options[0]
    return None


def _choices_given(setting: dict[str, Any]) -> bool:
    """Whether a setting given by hand is some of its choices - or one of them - not a number."""
    return setting.get("options") is not None or isinstance(setting.get("value"), str)


def _fixed_domain(setting: dict[str, Any]) -> dict[str, Any]:
    value = _single(setting)
    said = {"source": _by(setting), "cites": list(setting.get("cites") or ["these"])}
    if isinstance(value, str):
        return {"options": [value], "suggested": value, **said}
    number = float(value)
    return {"low": number, "high": number, "step": 1.0, "suggested": number, **said}


def _provisional(setting: dict[str, Any]) -> dict[str, Any]:
    """A range or choices the words gave, as the part's reading first sees it."""
    if setting.get("options") is not None:
        return {"options": list(setting["options"]), "source": _by(setting), "cites": ["these"]}
    return {
        "low": setting.get("low"),
        "high": setting.get("high"),
        "step": setting.get("step") or 1.0,
        "source": _by(setting),
        "cites": ["these"],
    }


def _domain(setting: dict[str, Any], read: dict[str, Any]) -> dict[str, Any]:
    """A setting as the words gave it, over what the part read for it: a value fixed, the choices
    left, or a range - keeping the part's suggestion and step where they still fit."""
    said = {"source": _by(setting), "cites": list(setting.get("cites") or ["these"])}
    unit = {"unit": read["unit"]} if read.get("unit") else {}
    if _single(setting) is not None:
        return {**_fixed_domain(setting), **unit, **said}
    if setting.get("options") is not None:
        options = list(setting["options"])
        suggested = read.get("suggested") if read.get("suggested") in options else options[0]
        return {"options": options, "suggested": suggested, **unit, **said}
    low = setting.get("low", read.get("low"))
    high = setting.get("high", read.get("high"))
    if low is None or high is None:
        raise ValueError("a range needs its low and its high")
    step = setting.get("step") or read.get("step") or 1.0
    suggested = read.get("suggested")
    if not isinstance(suggested, int | float) or not float(low) <= suggested <= float(high):
        suggested = float(low)
    return {
        "low": float(low),
        "high": float(high),
        "step": float(step),
        "suggested": suggested,
        **unit,
        **said,
    }


def _by(setting: dict[str, Any]) -> str:
    """Who gave a setting: the engineer's words, unless their hand on the card."""
    return "you" if setting.get("source") == "you" else "words"


def _as_setting(domain: studies.Domain) -> dict[str, Any]:
    """A setting kept in a study, as the draft holds what the words - or the hand - gave."""
    said = {"source": domain.source, "cites": list(domain.cites)}
    if domain.fixed:
        value = domain.options[0] if domain.options is not None else domain.low
        return {"value": value, **said}
    if domain.options is not None:
        return {"options": list(domain.options), **said}
    return {"low": domain.low, "high": domain.high, "step": domain.step, **said}


def _from_words(item: dict[str, Any], known: set[str], by: str = "words") -> dict[str, Any]:
    """An entry the engineer's words - or their hand, ``by`` "you" - asked for: theirs, and - when
    it is firm and cites no word the study holds - citing the words the draft rests on. A cite
    that is not the id of a word is dropped rather than refused: quoting is checked where the
    words come in."""
    out = {k: v for k, v in item.items() if v is not None and k != "id"}
    out["cites"] = [c for c in out.get("cites", []) if c in known]
    strength = out.get("strength", "hard")
    if strength == "hard" and out.get("source") in (None, "you", "words"):
        out["source"] = by
    if strength in ("hard", "learned") and not out["cites"]:
        out["cites"] = ["these"]
    return out


def _add_rule(draft: dict[str, Any], rule: dict[str, Any]) -> None:
    """A rule from the words, added to the draft - once: the same rule given again, as an edit that
    restates a block does, is the rule the draft holds."""

    def said(r: dict[str, Any]) -> tuple:
        return (
            r["kind"],
            tuple(sorted(r.get("refs") or [])),
            json.dumps(r.get("params") or {}, sort_keys=True),
            r.get("block"),
        )

    if all(said(kept) != said(rule) for kept in draft["rules"]):
        draft["rules"].append(rule)


def _kept(item: Any) -> dict[str, Any]:
    out = item.model_dump()
    out.pop("id", None)
    return out


# --- the draft, as the card shows it -------------------------------------------------------------


def _read(session: Session, version: studies.StudyVersion, reports: dict[str, dict]) -> dict:
    accepted = _saved(session)
    now = _shown(version, reports)
    before = _shown(accepted, {}) if accepted is not None else None
    differs = accepted is None or studies.meaning(version) != studies.meaning(accepted)
    changes = _marked(now, before) if differs else []
    if differs and before is None:
        changes = ["first version"]
    refs = set()
    for block in now["blocks"]:
        refs |= {*block["stand_on"]["refs"], *block["end_on"]["refs"]}
        for rule in [*block["keep_clear"], *block["rules"]]:
            refs |= set(rule["refs"])
        for setting in block["settings"]:
            refs |= set(REF.findall(setting["says"]))
    for rule in [*now["rules"], *now["interfaces"]]:
        refs |= set(rule["refs"])
    features = session.extraction.features
    assert features is not None
    real = sorted(r for r in refs if features.get(r) is not None)
    return {
        "accepted": accepted.version if accepted is not None else None,
        "differs": differs,
        "changes": changes,
        "cannot": None,
        "refused": False,
        **now,
        "open": [line for line in studies.open_items(version) if not _about_pull(line, session)],
        "assumed": studies.assumed(version),
        "attention": list(session.attention),
        "names": names(features, real),
        "runs": runs(session),
        "variant": _variant_said(session, version),
        "offered": _offered(),
    }


def _about_pull(line: str, session: Session) -> bool:
    """Whether an open item asks for the pull - which a variant does not hold."""
    return bool(session.variant) and line.startswith("the pull direction")


def _variant_said(session: Session, version: studies.StudyVersion) -> dict | None:
    """The variant being authored: its code, its name - as kept, or suggested from what it adds
    and where - whether it is kept yet, and how many combinations it allows."""
    if not session.variant:
        return None
    kept = variants.load(session.project, session.variant)
    block = version.blocks[0] if version.blocks else None
    label = kept.label if kept is not None and kept.label else None
    return {
        "id": session.variant,
        "label": label or (variants.suggested_label(block) if block is not None else ""),
        "kept": kept is not None,
        "kind": variants.kind_of(block) if block is not None else None,
        "combinations": studies.combinations(block) if block is not None else 0,
        "others": [
            {"id": v["id"], "label": v["label"], "kind": v["kind"]}
            for v in (variants.listed(o) for o in variants.library(session.project))
            if v["id"] != session.variant
        ],
    }


def _offered() -> list[dict[str, Any]]:
    """The rules a variant may hold, as the card offers them: each kind, what it reads as, and
    what it needs."""
    return [
        {
            "kind": kind,
            "says": studies.KINDS[kind].says,
            "needs": list(studies.KINDS[kind].needs),
            "names": studies.KINDS[kind].names,
        }
        for kind in studies.OFFERED
    ]


def _refused(session: Session, why: str) -> dict:
    saved = _saved(session)
    return {
        "accepted": saved.version if saved is not None else None,
        "differs": None,
        "changes": [],
        "cannot": why,
        "refused": True,
        "blocks": [],
        "rules": [],
        "interfaces": [],
        "rest": None,
        "open": [],
        "assumed": [],
        "attention": list(session.attention),
        "names": {},
        "variant": _variant_said(session, _nothing_version()) if session.variant else None,
        "offered": _offered(),
    }


def _nothing_version() -> studies.StudyVersion:
    return studies.StudyVersion(version=0, created="", words=[], blocks=[])


def _shown(version: studies.StudyVersion, reports: dict[str, dict]) -> dict:
    """A version as the card shows it, block by block, then the rest."""
    blocks = []
    for block in version.blocks:
        report = reports.get(block.id, {})
        mine = [c for c in version.constraints if c.block == block.id and c.by != "platform"]
        blocks.append(
            {
                "id": block.id,
                "add": block.add,
                "stand_on": {
                    "refs": list(block.where.support),
                    "read_off": "support" in block.where.read_off,
                },
                "end_on": {
                    "refs": list(block.where.anchors),
                    "read_off": "anchors" in block.where.read_off,
                },
                "other_side": {"refs": list(block.where.other_side), "read_off": False},
                "keep_clear": [_rule(c) for c in mine if c.kind == "keep_clear_of"],
                "settings": [
                    {
                        "name": name,
                        "label": SETTING_LABELS.get(name, name.replace("_", " ")),
                        "says": _says(name, d),
                        "source": d.source,
                        "fixed": d.fixed,
                        "basis": d.basis,
                        # A free layout's seed is how designs differ, never what anyone sets.
                        "hidden": name in HIDDEN,
                        # A height is a share of what each end meets, shown as a percentage.
                        "percent": name == "height_fraction",
                        # What it may take, to change by hand on the card.
                        "domain": {
                            "low": d.low,
                            "high": d.high,
                            "step": d.step,
                            "options": d.options,
                            # Every choice the part offers, some of which the engineer may have
                            # left out.
                            "choices": (report.get("choices") or {}).get(name, d.options),
                            "suggested": d.suggested,
                            "unit": d.unit,
                            # What the part may be cast in, to choose the one it is.
                            **(
                                {"catalogue": [m["id"] for m in knowledge.materials()]}
                                if name == "material"
                                else {}
                            ),
                        },
                    }
                    for name, d in block.free.items()
                ],
                "rules": [_rule(c) for c in mine if c.kind != "keep_clear_of"],
                "needed": list(report.get("needed", [])),
                "problems": list(report.get("problems", [])),
                "cannot": report.get("cannot"),
                "note": dict(report.get("note", {})),
                "changed": False,
            }
        )
    pull, target = version.pull, version.target
    way = None
    if pull is not None:
        way = pull.along or ", ".join(f"{v:g}" for v in pull.direction or [])
    return {
        "blocks": blocks,
        "rules": [
            _rule(c)
            for c in version.constraints
            if c.block is None and c.by != "platform" and c.kind not in CLOSED
        ],
        "interfaces": [
            _rule(c) for c in version.constraints if c.by == "platform" or c.kind in CLOSED
        ],
        "rest": {
            "prefer": [{"id": p.id, "says": p.text, "weight": p.weight} for p in version.prefer],
            "objectives": [
                {
                    "id": o.id,
                    "says": o.text
                    or f"{o.sense} {o.quantity}" + (f" of {', '.join(o.refs)}" if o.refs else ""),
                    "physical": o.physical,
                }
                for o in version.objectives
            ],
            "pull": None
            if pull is None
            else {"says": f"along {way}", "source": pull.source, "basis": pull.basis},
            "target": {
                "says": f"{target.n} designs, each at least {target.differ_by} ribs from the "
                f"rest, seed {target.seed}"
            },
        },
    }


# Settings a variant varies over that nobody sets: which free layout a design takes.
HIDDEN = ("layout",)


def _says(name: str, domain: studies.Domain) -> str:
    """What a setting may take, in words - a height as a percentage of what each end meets."""
    if name != "height_fraction" or domain.options is not None:
        return domain.says()

    def percent(value: Any) -> str:
        return f"{float(value) * 100:g}"

    if domain.low == domain.high:
        return f"{percent(domain.low)} %"
    said = f"{percent(domain.low)} to {percent(domain.high)} %"
    if domain.suggested is not None:
        said += f", {percent(domain.suggested)} suggested"
    return said


def _rule(constraint: studies.Constraint) -> dict[str, Any]:
    kind = studies.KINDS.get(constraint.kind)
    if kind is None:
        until = "nothing checks this kind of rule yet"
    elif constraint.kind == "datum" and not constraint.refs:
        until = "which face is it? Point at it on the part"
    elif not kind.enforced:
        until = studies.UNTIL[kind.stage]
    else:
        until = ""
    return {
        "id": constraint.id,
        "kind": constraint.kind,
        "says": studies.said(constraint),
        "strength": constraint.strength,
        "source": constraint.source,
        "by": constraint.by,
        "refs": list(constraint.refs),
        "params": dict(constraint.params),
        "basis": constraint.basis,
        "enforced": not until,
        "until": until,
        "changed": False,
    }


def _marked(now: dict, before: dict | None) -> list[str]:
    """Each item of ``now`` marked where it differs from ``before``; the differences, in lines."""
    lines: list[str] = []
    old = {b["id"]: b for b in (before or {}).get("blocks", [])}
    for block in now["blocks"]:
        was = old.get(block["id"])
        if was is None:
            block["changed"] = True
            for group in ("keep_clear", "rules"):
                for rule in block[group]:
                    rule["changed"] = True
            for setting in block["settings"]:
                setting["changed"] = True
            block["stand_on"]["changed"] = block["end_on"]["changed"] = True
            lines.append(f"{block['id']} added: {block['add']}")
            continue
        for key, label in (("stand_on", "stands on"), ("end_on", "ends on")):
            moved = block[key]["refs"] != was[key]["refs"]
            block[key]["changed"] = moved
            if moved:
                lines.append(f"{block['id']} {label}: {', '.join(block[key]['refs']) or 'nothing'}")
        settings = {s["name"]: (s["says"], s["source"]) for s in was["settings"]}
        for setting in block["settings"]:
            setting["changed"] = settings.get(setting["name"]) != (
                setting["says"],
                setting["source"],
            )
            if setting["changed"]:
                lines.append(f"{block['id']} {setting['label']}: {setting['says']}")
        for group in ("keep_clear", "rules"):
            said = {r["says"] for r in was[group]}
            for rule in block[group]:
                rule["changed"] = rule["says"] not in said
                if rule["changed"]:
                    lines.append(f"{block['id']}: {rule['says']}")
            gone = said - {r["says"] for r in block[group]}
            lines.extend(f"{block['id']} no longer: {text}" for text in sorted(gone))
        block["changed"] = any(
            [
                block["stand_on"]["changed"],
                block["end_on"]["changed"],
                *(s["changed"] for s in block["settings"]),
                *(r["changed"] for g in ("keep_clear", "rules") for r in block[g]),
            ]
        )
    for gone in sorted(set(old) - {b["id"] for b in now["blocks"]}):
        lines.append(f"{gone} taken out")
    said = {r["says"] for r in (before or {}).get("rules", [])}
    for rule in now["rules"]:
        rule["changed"] = rule["says"] not in said
        if rule["changed"]:
            lines.append(f"rule added: {rule['says']}")
    lines.extend(
        f"rule taken out: {text}" for text in sorted(said - {r["says"] for r in now["rules"]})
    )
    rest, was_rest = now["rest"], (before or {}).get("rest")
    if was_rest is not None:
        for key, label in (("prefer", "preference"), ("objectives", "objective")):
            new = [p["says"] for p in rest[key]]
            old_says = [p["says"] for p in was_rest[key]]
            lines.extend(f"{label} added: {t}" for t in new if t not in old_says)
            lines.extend(f"{label} taken out: {t}" for t in old_says if t not in new)
        for key, label in (("pull", "pull direction"), ("target", "designs")):
            if rest[key] != was_rest[key]:
                lines.append(f"{label}: {(rest[key] or {}).get('says', 'not given')}")
    return lines or ["how settings are ranged"]


# --- where ribs would go, and designs -------------------------------------------------------------


@dataclass
class Pieces:
    """What one design of a study is made from, block by block: ribs to place, holes to cut, faces
    to move, what it is cast in - and why each block that cannot be built cannot."""

    placements: list[Placement] = field(default_factory=list)
    holes: list[HoleSet] = field(default_factory=list)
    offsets: list[Offset] = field(default_factory=list)
    material: MaterialChoice | None = None
    cannot: list[str] = field(default_factory=list)

    def any(self) -> bool:
        return bool(self.placements or self.holes or self.offsets or self.material)

    def radius(self) -> float:
        """The root fillet the part is opened at for these: the smallest of their ribs'."""
        return min((p.section.root_fillet_mm for p in self.placements), default=OPEN_AT_MM)


def _pieces(
    version: studies.StudyVersion,
    values: dict[str, dict[str, Any]] | None = None,
    present: set[str] | None = None,
) -> Pieces:
    """Every block that can be built, at the values given for it - or at its suggested point - as
    what it is made from, and why each other block cannot; only the blocks ``present``, when a
    design holds some of them. Webs with nothing under them stand along the pull when it is a
    direction and what they join runs along it."""
    pieces = Pieces()
    pull = version.pull.direction if version.pull is not None else None
    for block in version.blocks:
        if present is not None and block.id not in present:
            continue
        if block.add not in studies.ADDS:
            pieces.cannot.append(f"{block.id}: nothing can add {block.add} yet")
            continue
        try:
            point = studies.point(version, block.id, (values or {}).get(block.id))
            kind = point.get("kind")
            if kind == "thicken":
                pieces.offsets.append(Offset.model_validate(point))
            elif kind == "holes":
                pieces.holes.append(HoleSet.model_validate(point))
            elif kind == "material":
                pieces.material = MaterialChoice.model_validate(point)
            else:
                if not block.where.support and pull:
                    point["pull"] = list(pull)
                pieces.placements.append(Placement.model_validate(point))
        except (studies.StudyError, ValueError) as error:
            pieces.cannot.append(f"{block.id}: {error}")
    return pieces


def _spec_of(version: studies.StudyVersion, pieces: Pieces) -> Version:
    """One design of a study, as the spec a design is made from."""
    return Version(
        version=version.version,
        created=version.created,
        words=version.words or [Words(id="card", text="not yet written")],
        placements=pieces.placements,
        offsets=pieces.offsets,
        holes=pieces.holes,
        material=pieces.material,
        rules=studies.rules_of(version),
        measured=version.measured,
    )


def _opened(session: Session, version: Version, fidelity: str, radius: float) -> Opened:
    """The part opened at a fidelity, once per grid - the grid ``radius``, a root fillet, asks
    for - so many designs are placed on one."""
    key = (fidelity, radius)
    with session.opening.setdefault(key, threading.Lock()):
        if key not in session.opened:
            session.opened[key] = Opened.open(
                session.project, session.extraction, version, fidelity, radius
            )
    return session.opened[key]


def _place(
    session: Session,
    version: studies.StudyVersion,
    pieces: Pieces,
    radius: float | None = None,
) -> dict:
    """The pieces placed on the part at the preview grid - that of ``radius``, when many designs
    share one - each block after those it keeps clear of, on the part with its faces moved as the
    design moves them."""
    extraction = session.extraction
    try:
        opened = _opened(session, _spec_of(version, pieces), "preview", radius or pieces.radius())
    except IntentError as error:
        return {"cannot": str(error)}
    features = extraction.features
    assert features is not None and extraction.atlas is not None and extraction.tess is not None
    return place_all(
        opened.base,
        features,
        extraction.atlas,
        extraction.tess,
        pieces.placements,
        pieces.holes,
        offsets=face_offsets(features, pieces.offsets),
        finder=_measure(session),
        memo=session.memo,
    )


def _rows(pieces: Pieces, placed: dict) -> dict[str, dict[str, Any]]:
    """What every block of a design made, in a few words each, block by block."""
    rows: dict[str, dict[str, Any]] = {}
    for placement in pieces.placements:
        result = placed[placement.id]
        rows[placement.id] = {
            "ribs": len(result.ribs),
            "pads": len(result.pads),
            "says": result.tally(),
        }
    for hole_set in pieces.holes:
        result = placed[hole_set.id]
        rows[hole_set.id] = {"holes": len(result.holes), "says": result.tally()}
    for offset in pieces.offsets:
        way = "thickened" if offset.offset_mm > 0 else "thinned" if offset.offset_mm < 0 else "kept"
        # A few faces by name; more, how many - every face named says nothing a design changes.
        faces = _and(offset.faces) if len(offset.faces) <= 3 else f"{len(offset.faces)} faces"
        rows[offset.id] = {
            "moved_mm": offset.offset_mm,
            "says": f"{faces} {way}"
            + (f" by {abs(offset.offset_mm):g} mm" if offset.offset_mm else " as they are"),
        }
    if pieces.material is not None:
        rows[pieces.material.id] = {"says": f"cast in {pieces.material.material}"}
    return rows


def _counted(placed: dict) -> dict[str, int]:
    return {
        "ribs": sum(len(r.ribs) for r in placed.values() if isinstance(r, Placed)),
        "pads": sum(len(r.pads) for r in placed.values() if isinstance(r, Placed)),
        "holes": sum(len(r.holes) for r in placed.values() if isinstance(r, Drilled)),
        "paths": sum(r.paths for r in placed.values() if isinstance(r, Placed)),
    }


def paths(session: Session, draft: bool = True, values: dict | None = None) -> dict:
    """Where the draft's - or the study's - suggested design would put ribs and holes, or the
    design at the values given: every line each block's layout tries, and what became of it, before
    anything is made. Only placing, nothing composed or checked: seconds once the part is open at
    the preview grid."""
    if draft:
        try:
            entries, _ = _entries(session)
            version = _build(session, entries)
        except (studies.StudyError, ValueError) as error:
            return {"cannot": str(error)}
    else:
        study = studies.active(session.project)
        if study is None:
            return {"cannot": "there is no study yet"}
        version = study.current
    pieces = _pieces(version, values)
    if not pieces.any():
        why = "; ".join(pieces.cannot) or "nothing the study asks for can be placed yet"
        return {"cannot": why}
    placed = _place(session, version, pieces)
    if "cannot" in placed:
        return placed
    rows = _rows(pieces, placed)
    return {
        "lines": [line for result in placed.values() for line in result.tried],
        **_counted(placed),
        "summary": "; ".join(f"{bid}: {row['says']}" for bid, row in rows.items()),
        "blocks": rows,
        "waiting": pieces.cannot,
    }


# --- variants, authored on the card ---------------------------------------------------------------

# How many points of a variant Show paths tries, at most, to find one that passes.
SAMPLE_TRIES = 48


def new_variant(session: Session) -> dict:
    """A new variant to author: an id no variant has had, and nothing in it yet."""
    session.variant = variants.new_id(session.project)
    session.draft, session.heard, session.attention = _nothing(), [], []
    session.changed.add("draft")
    return view(session)


def open_variant(session: Session, vid: str) -> dict:
    """A variant of the library to change: the draft read back from it as kept."""
    if variants.load(session.project, vid) is None:
        return {"refused": f"there is no variant {vid}"}
    session.variant = vid
    load(session)
    return view(session)


def discard_variant(session: Session) -> dict:
    """Forget what was not saved: the variant as kept - or, never kept, nothing in it."""
    load(session)
    return view(session)


def save_variant(session: Session, label: str | None = None) -> dict:
    """The variant being authored, kept in the library once one of its points passes - created, or
    saved as changed, called ``label``. ``{"variant": id, "version": n, "label": ...}``, or
    ``{"cannot": why}``: nothing is kept that no design could be made of."""
    if not session.variant:
        return {"cannot": "no variant is being authored"}
    if not session.draft["blocks"]:
        return {"cannot": "add ribs, webs, a thickening or holes first: select faces on the part"}
    card = view(session)
    if card.get("refused"):
        return {"cannot": card["cannot"]}
    kept = variants.load(session.project, session.variant)
    name = (
        (label or "").strip()
        or (kept.label if kept is not None else "")
        or card["variant"]["label"]
    )
    if kept is not None and not card["differs"]:
        variants.rename(session.project, session.variant, name)
        session.changed.add("variants")
        return {"variant": session.variant, "version": kept.current.version, "label": name}
    sample = variant_sample(session)
    if "cannot" in sample:
        return {"cannot": sample["cannot"]}
    try:
        entries, _ = _entries(session)
        written = studies.write(
            session.project,
            session.variant,
            folder=variants.FOLDER,
            make_active=False,
            label=name,
            known_blocks=variants.kinds(session.project, but=session.variant),
            **entries,
            note="; ".join(card["changes"])[:400],
        )
    except (studies.StudyError, ValueError) as error:
        return {"cannot": str(error)}
    load(session)
    session.changed.add("variants")
    return {"variant": session.variant, "version": written.version, "label": name}


def variant_sample(session: Session, another: bool = False, seed: int | None = None) -> dict:
    """The variant being authored at a point that passes: its suggested point first - or, for
    another sample, points drawn at random from what it allows - each placed alone, repaired and
    screened, until one passes. Its lines, what repair left out, what it made; or why none of the
    points tried passes, the commonest reasons first."""
    try:
        entries, _ = _entries(session)
        version = _build(session, entries)
    except (studies.StudyError, ValueError) as error:
        return {"cannot": str(error)}
    if not version.blocks:
        return {"cannot": "add ribs, webs, a thickening or holes first: select faces on the part"}
    block = version.blocks[0]
    first = _pieces(version)
    if not first.any():
        return {"cannot": "; ".join(first.cannot) or "nothing it asks for can be placed yet"}
    draw = random.Random(seed)
    points: list[dict[str, Any]] = [] if another else [{}]
    while len(points) < SAMPLE_TRIES:
        points.append(random_point(block, draw))
    walls = measure_walls(session.extraction, _measure(session).exit_along, first.offsets)
    why: Counter[str] = Counter()
    for number, values in enumerate(points, start=1):
        outcome = _tried(session, version, {block.id: values}, first.radius(), walls)
        if isinstance(outcome, str):
            return {"cannot": outcome}
        pieces, mended, screened = outcome
        if screened.outcome == "reject":
            why.update(f["check"] for f in screened.rejected())
            continue
        rows = _rows(pieces, mended.placed)
        return {
            "lines": [line for result in mended.placed.values() for line in result.tried],
            **_counted(mended.placed),
            # A variant is one block: what it made, without its code.
            "summary": "; ".join(row["says"] for row in rows.values()),
            "blocks": rows,
            "values": values,
            "about": _about(version, {block.id: values}).get(block.id, ""),
            "left_out": mended.left_out,
            "left_out_said": left_out_said(mended.left_out),
            "findings": [f for f in screened.findings if f["outcome"] != "pass"],
            "tried": number,
            "drawn": _drawn(block, another, seed, number),
            "waiting": first.cannot,
        }
    reasons = ", ".join(f"{check} {n}" for check, n in why.most_common(3))
    return {
        "cannot": f"none of the {len(points)} points tried passes ({reasons}) - change where it "
        "stands or what it may take"
    }


def _drawn(block: studies.Block, another: bool, seed: int | None, number: int) -> str:
    """How a sample of a variant was drawn, in a sentence: its suggested point, or a point drawn at
    random - every choice and every step of a range as likely as the next - and on which try of how
    many it passed."""
    if not any(not domain.fixed for domain in block.free.values()):
        return "Nothing in it varies: every sample is its one design."
    if not another and number == 1:
        return "At its suggested point: every setting where it starts."
    random_ = "every choice, and every step of a range, as likely as the next"
    tries = f"passed on try {number} of up to {SAMPLE_TRIES}"
    if not another:
        return f"Its suggested point did not pass, so drawn at random: {random_}; {tries}."
    return f"Drawn at random (seed {seed}): {random_}; {tries}."


def variant_shown(session: Session, vid: str) -> dict | None:
    """A variant of the library as a campaign shows it, read only: what it adds and where, what it
    may vary, every rule it holds - never the one being authored, which stays as it is."""
    kept = variants.load(session.project, vid)
    if kept is None:
        return None
    shown = _shown(kept.current, {})
    features = session.extraction.features
    assert features is not None
    block = shown["blocks"][0]
    # A rule said for every block - the drawing's smallest radius - is the variant's own: it has
    # one block, and a campaign composes the rule onto it.
    block["rules"] = [*block["rules"], *shown["rules"]]
    refs = {*block["stand_on"]["refs"], *block["end_on"]["refs"], *block["other_side"]["refs"]}
    for rule in [*block["keep_clear"], *block["rules"]]:
        refs |= set(rule["refs"])
    real = sorted(r for r in refs if features.get(r) is not None)
    return {
        **variants.listed(kept),
        "block": block,
        "interfaces": len(shown["interfaces"]),
        "names": names(features, real),
    }


def random_point(block: studies.Block, draw: random.Random) -> dict[str, Any]:
    """A point of a block drawn at random: each setting that is not fixed at a value it may take,
    each value as likely as the next - choices by their weights, where a study weighs them; a
    variant weighs none."""
    return {
        name: studies._at(domain, draw.random())
        for name, domain in sorted(block.free.items())
        if not domain.fixed
    }


def left_out_said(left_out: list[dict[str, Any]]) -> str:
    """What was left out of a design, in a few words: how many ribs and holes, and the rule each
    broke."""
    if not left_out:
        return ""
    counted = Counter((x["what"], x["why"]) for x in left_out)
    parts = [
        f"{n} {what}{'s' if n != 1 else ''} ({why})" for (what, why), n in sorted(counted.items())
    ]
    return "left out: " + ", ".join(parts)


def _tried(
    session: Session,
    version: studies.StudyVersion,
    values: dict[str, dict[str, Any]],
    radius: float,
    walls: dict[str, float | None],
    off: frozenset[str] | set[str] = frozenset(),
):
    """One design at ``values`` - the blocks it holds, each at the point given - placed on the
    grid of ``radius``, repaired and screened; or why it cannot be placed."""
    pieces = _pieces(version, values, present=set(values))
    if not pieces.any():
        return "; ".join(pieces.cannot) or "nothing it asks for can be placed yet"
    placed = _place(session, version, pieces, radius)
    if "cannot" in placed:
        return str(placed["cannot"])
    opened = _opened(session, _spec_of(version, pieces), "preview", radius)
    features = session.extraction.features
    assert features is not None
    mended = repair(opened.base, pieces.placements, pieces.holes, placed)
    screened = screen(
        features,
        opened.base,
        pieces.placements,
        pieces.holes,
        pieces.offsets,
        pieces.material,
        mended.placed,
        walls,
        opened.surface.volume_mm3,
        set(off),
    )
    return pieces, mended, screened


def design_from_study(
    session: Session,
    fidelity: str,
    values: dict[str, dict[str, Any]] | None = None,
    run: str | None = None,
    present: set[str] | None = None,
) -> dict:
    """A design from the active study's current version - or from the study version a kept
    ``run`` of Go was made from - every block at the values given for it, or at its suggested
    point - only the variants ``present``, for a design of a campaign - and its verdict, with what
    the study holds that nothing enforces yet and what nobody confirmed. Or why there is none."""
    if run is not None:
        found = _run(session, run)
        if isinstance(found, str):
            return {"cannot": found}
        version, _ = found
        name = run
    else:
        study = studies.active(session.project)
        if study is None:
            return {"cannot": "there is no study yet"}
        version, name = study.current, study.name
    built = built_of(
        session.extraction,
        version,
        values,
        present,
        fidelity,
        opener=lambda point, level, radius: _opened(session, point, level, radius),
        finder=_measure(session),
        memo=session.memo,
    )
    if isinstance(built, str):
        return {"cannot": built}
    made, pieces = built
    session.made = made
    session.changed.add("design")
    return {
        **verdict(made),
        "study": name,
        "study_version": version.version,
        "open": studies.open_items(version),
        "assumed": studies.assumed(version),
        "waiting": pieces.cannot,
    }


def built_of(
    extraction: Extraction,
    version: studies.StudyVersion,
    values: dict[str, dict[str, Any]] | None,
    present: set[str] | None,
    fidelity: str,
    *,
    opener: Callable[[Version, str, float], Opened],
    finder: _Faces,
    memo: dict,
    surface: bool = True,
) -> tuple[Made, Pieces] | str:
    """One design of a study version built - every block at the values given, or its suggested
    point, only the variants ``present`` - on the part ``opener`` opens at a fidelity and a root
    fillet's grid; and what it was made from. Or why it cannot be. Whoever builds a design of a
    campaign builds it here, so the design built anywhere is the same design."""
    assert extraction.features is not None
    _, lost = studies.resolve(version, extraction.features)
    if lost:
        return "the part is not the one the study names: " + "; ".join(lost[:3])
    pieces = _pieces(version, values, present)
    if not pieces.any():
        return "; ".join(pieces.cannot) or "nothing the study asks for can be made yet"
    point = _spec_of(version, pieces)
    radius = pieces.radius()
    if fidelity == "preview":
        # Every preview of a study on one grid - no finer than the one its designs were placed
        # on - built once: a design with a smaller fillet waits for full to be held to it.
        radius = max(radius, _pieces(version).radius())
    try:
        opened = opener(point, fidelity, radius)
        made = make(opened, point, {}, finder=finder, memo=memo, surface=surface)
    except IntentError as error:
        return str(error)
    return made, pieces


def go(
    session: Session,
    n: int | None = None,
    budget: int | None = None,
    seed: int | None = None,
    off: dict[str, list[str]] | None = None,
) -> Iterator[dict]:
    """Many designs at once - a campaign: the draft accepted if it differs, then ``n`` kept - the
    study's target when not told - of at most ``budget`` tried. Nothing is composed or checked in
    full: that is for the one the engineer builds.

    **A campaign may switch parts of the study off** for itself alone - ``off`` names ``blocks``,
    ``rules`` by id and screening ``checks`` by name - and set the spread's ``seed``. The study is
    left as it is; the run keeps the study version it used and what was switched off beside its
    designs, and a different campaign of one version is a run of its own. The part's interfaces
    stay closed whatever is switched off.

    **Each block alone first.** Its free settings are spread over, the other blocks at their
    suggested points, and every point is placed and screened: the points at which the block makes
    something and holds to its own rules are kept - as many as :data:`POOL` says - and how many
    it took is said. A block that makes nothing wherever it is tried stops Go, with why.

    **Then together.** A spread over which of each block's points to take, every block of each
    design placed at once - each after those it keeps clear of - and screened for what one block
    alone cannot show: ribs of two blocks with no room between them, holes on ribs. Each design kept
    is said as it is kept and written to the project's ``designs`` folder with everything it is
    made of; designs alike in every rib, pad, hole and face moved are kept once."""
    card = view(session)
    if card.get("refused"):
        yield {"type": "error", "message": card["cannot"]}
        return
    if card["differs"]:
        written = accept(session)
        if "cannot" in written:
            yield {"type": "error", "message": written["cannot"]}
            return
        yield {"type": "accepted", "version": written["version"]}
    study = studies.active(session.project)
    assert study is not None
    accepted = study.current
    off = {key: sorted(set((off or {}).get(key) or [])) for key in ("blocks", "rules", "checks")}
    version = campaign_version(accepted, off, seed)
    first = _pieces(version)
    if not first.any():
        yield {"type": "error", "message": "; ".join(first.cannot) or "nothing can be placed yet"}
        return
    n = int(n or version.target.n or GO)
    budget = int(budget or TRIES_PER_DESIGN * n + 100)
    # Every design is placed on the grid the suggested one opens: placing needs no finer grid, and
    # a grid per root fillet sampled would build the part's field again and again.
    radius = first.radius()
    try:
        _opened(session, _spec_of(version, first), "preview", radius)
    except IntentError as error:
        yield {"type": "error", "message": str(error)}
        return
    extraction = session.extraction
    walls = measure_walls(extraction, _measure(session).exit_along, first.offsets)
    campaign = {
        "study": study.name,
        "version": accepted.version,
        "n": n,
        "budget": budget,
        "seed": version.target.seed,
        "off": off,
    }
    folder = archive_root(session.project) / _run_name(study.name, accepted, campaign)
    folder.mkdir(parents=True, exist_ok=True)
    # The study version the designs are made from, and the campaign, beside them: a run read back
    # needs nothing else.
    (folder / "study.json").write_text(version.model_dump_json(indent=1), encoding="utf-8")
    (folder / "campaign.json").write_text(json.dumps(campaign, indent=2), encoding="utf-8")
    shutil.rmtree(folder / "built", ignore_errors=True)
    session.designs, session.archive = [], folder / "designs.jsonl"
    where = f"{ARCHIVE_DIR}/{session.project.name}/{folder.name}"
    session.loaded = {}
    started = time.perf_counter()

    def tried_at(values: dict[str, dict[str, Any]]):
        # Placed, repaired and screened as a campaign's designs are - and as a design is built -
        # so the design listed is the design made.
        return _tried(session, version, values, radius, walls, off["checks"])

    yield {
        "type": "started",
        "version": version.version,
        "n": n,
        "budget": budget,
        "waiting": first.cannot,
        "archive": where,
        "run": folder.name,
        "off": off,
    }

    # Each block alone.
    waiting = _ids(first.cannot)
    pools: dict[str, list[dict[str, Any]]] = {}
    alone: dict[str, dict[str, Any]] = {}
    for block in version.blocks:
        if block.add not in studies.ADDS or block.id in waiting:
            continue
        if all(d.fixed for d in block.free.values()):
            pools[block.id] = [{}]
            continue
        pool: list[dict[str, Any]] = []
        pool_effective: list[dict[str, Any]] = []
        why: Counter[str] = Counter()
        count = 0
        most = min(max(POOL[0], n // 4), POOL[1])
        for values in studies.spread(version, blocks=[block.id]):
            if len(pool) >= most or count >= most * POOL_TRIES:
                break
            count += 1
            outcome = tried_at(values)
            if isinstance(outcome, str):
                yield {"type": "error", "message": outcome}
                return
            mine = [f for f in outcome[2].rejected() if f.get("block") == block.id]
            if mine:
                why.update(f["check"] for f in mine)
                continue
            # The suggested point, and the same values given, are one point.
            effective = {**{n: d.suggested for n, d in block.free.items()}, **values[block.id]}
            if effective in pool_effective:
                continue
            pool_effective.append(effective)
            pool.append(values[block.id])
        alone[block.id] = {"kept": len(pool), "tried": count, "rejected": dict(why)}
        yield {"type": "block", "block": block.id, **alone[block.id]}
        if not pool:
            reasons = ", ".join(f"{k} {v}" for k, v in why.most_common(3))
            yield {
                "type": "error",
                "message": f"{block.id} makes nothing at any of the {count} points tried: "
                f"{reasons} - change what it stands on or joins, or what it may take",
            }
            return
        pools[block.id] = pool

    # Together.
    seen: set[str] = set()
    rejected: Counter[str] = Counter()
    tried = repaired = 0
    other = random.Random(version.target.seed)

    def progress() -> dict:
        return {
            "type": "progress",
            "tried": tried,
            "made": len(session.designs),
            "repaired": repaired,
            "rejected": dict(rejected),
            "seconds": round(time.perf_counter() - started, 1),
        }

    # Every design's paths beside it, a line each in the same order: any design is drawn at once.
    with (
        session.archive.open("w", encoding="utf-8") as archive,
        (folder / PATHS).open("w", encoding="utf-8") as kept_paths,
    ):
        for values in _combined(version, pools):
            if len(session.designs) >= n or tried >= budget:
                break
            tried += 1
            outcome = tried_at(values)
            if isinstance(outcome, str):
                yield {"type": "error", "message": outcome}
                return
            pieces, mended, screened = outcome
            # A design screened out by one block alone - holes with no room left by these ribs -
            # takes another of that block's points, the rest as they are, a few times.
            for _ in range(REPAIRS):
                blamed = {f.get("block") for f in screened.rejected()}
                if (
                    not blamed
                    or None in blamed
                    or not blamed <= {b for b in pools if len(pools[b]) > 1}
                ):
                    break
                values = {**values, **{b: other.choice(pools[b]) for b in blamed}}
                outcome = tried_at(values)
                if isinstance(outcome, str):
                    yield {"type": "error", "message": outcome}
                    return
                pieces, mended, screened = outcome
                if screened.outcome != "reject":
                    repaired += 1
            if screened.outcome == "reject":
                rejected.update(f["check"] for f in screened.rejected())
                if tried % 25 == 0:
                    yield progress()
                continue
            placed = mended.placed
            key = _key(pieces, placed)
            if key in seen:
                rejected["alike"] += 1
                continue
            seen.add(key)
            design = _design(len(session.designs), version, values, pieces, placed, screened)
            design["left_out"] = mended.left_out
            archive.write(json.dumps(_archived(design)) + "\n")
            kept_paths.write(json.dumps(_compact(design["lines"])) + "\n")
            session.designs.append(design)
            yield {"type": "design", **_listed(design)}
            if len(session.designs) % 25 == 0:
                yield progress()
    summary = {
        "project": session.project.name,
        "run": folder.name,
        "study": study.name,
        "version": version.version,
        "asked": n,
        "made": len(session.designs),
        "tried": tried,
        "repaired": repaired,
        "rejected": dict(rejected),
        "alone": alone,
        "seconds": round(time.perf_counter() - started, 1),
        "archive": where,
        "spread": _spread_of(session.designs),
    }
    (folder / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    session.changed.add("designs")
    yield {"type": "done", **{k: v for k, v in summary.items() if k != "spread"}}


def campaign_version(
    version: studies.StudyVersion, off: dict[str, list[str]], seed: int | None = None
) -> studies.StudyVersion:
    """The study version a campaign makes its designs from: the blocks and rules it switches off
    left out - with every rule of a block left out, and every rule keeping clear of what a block
    left out would have made - and its seed; the part's interfaces kept."""
    used = version.model_copy(deep=True)
    gone = set(off.get("blocks") or [])
    rules = set(off.get("rules") or [])
    used.blocks = [b for b in used.blocks if b.id not in gone]

    def kept(c: studies.Constraint) -> bool:
        if c.by == "platform":
            return True
        made_by_gone = any(studies.made_by(r) in gone for r in c.refs)
        return c.id not in rules and c.block not in gone and not made_by_gone

    used.constraints = [c for c in used.constraints if kept(c)]
    if seed is not None:
        used.target = used.target.model_copy(update={"seed": int(seed)})
    return used


def _run_name(name: str, version: studies.StudyVersion, campaign: dict[str, Any]) -> str:
    """A run's name: its study and version - and, for a campaign that switches anything off or
    spreads from another seed, a few characters that tell it from the rest."""
    plain = not any(campaign["off"].values()) and campaign["seed"] == version.target.seed
    if plain:
        return f"{name}-v{version.version}"
    said = json.dumps({"seed": campaign["seed"], "off": campaign["off"]}, sort_keys=True)
    return f"{name}-v{version.version}-{hashlib.sha1(said.encode()).hexdigest()[:6]}"


def _ids(cannot: list[str]) -> set[str]:
    """The blocks named in lines saying why they cannot be built."""
    return {line.split(":", 1)[0] for line in cannot}


def _combined(
    version: studies.StudyVersion, pools: dict[str, list[dict[str, Any]]]
) -> Iterator[dict[str, dict[str, Any]]]:
    """Designs from each block's points: the first of each - its suggested point, when that made
    something - then a scrambled Sobol spread over which point of each block to take, so every
    point of every block is taken about as often, and no two blocks move in step."""
    from scipy.stats import qmc

    blocks = list(pools)
    yield {b: pools[b][0] for b in blocks}
    varied = [b for b in blocks if len(pools[b]) > 1]
    if not varied:
        return
    engine = qmc.Sobol(d=len(varied), scramble=True, seed=version.target.seed)
    while True:
        for row in engine.random(1024):
            values = {b: pools[b][0] for b in blocks}
            for block, u in zip(varied, row, strict=True):
                pool = pools[block]
                values[block] = pool[min(int(u * len(pool)), len(pool) - 1)]
            yield values


def _key(pieces: Pieces, placed: dict) -> str:
    """What makes two designs the same design: every rib and pad where it stands, as thick and as
    tall; every hole; every face moved; what it is cast in - to the millimetre."""
    parts: list[tuple] = []
    for placement in pieces.placements:
        result = placed[placement.id]
        parts.append(("fillet", placement.id, placement.section.root_fillet_mm))
        for rib in result.made():
            parts.append(
                (
                    "pad" if rib.pad else "rib",
                    *(round(v) for v in (*rib.start, *rib.end, *rib.heights)),
                    round(rib.thickness_mm, 1),
                    round(rib.flange_width_mm, 1),
                    round(rib.flange_thickness_mm, 1),
                    round(rib.draft_deg, 2),
                    round(rib.edge_round_mm, 1),
                )
            )
    for hole_set in pieces.holes:
        for hole in placed[hole_set.id].holes:
            parts.append(("hole", *(round(v) for v in hole.centre), round(hole.radius_mm, 1)))
    for offset in pieces.offsets:
        parts.append(("moved", offset.id, round(offset.offset_mm, 1), round(offset.blend_mm)))
    if pieces.material is not None:
        parts.append(("material", pieces.material.material))
    return json.dumps(sorted(parts, key=str))


def _design(
    index: int,
    version: studies.StudyVersion,
    values: dict[str, dict[str, Any]],
    pieces: Pieces,
    placed: dict,
    screened: Screened,
) -> dict:
    """One design Go kept: its values, what every block made, how it screened and what it weighs -
    and everything it is made of, to build it or hand it on."""
    stats = screened.stats
    return {
        "index": index,
        "values": values,
        "outcome": screened.outcome,
        "ribs": stats["ribs"],
        "pads": stats["pads"],
        "holes": stats["holes"],
        "mass_kg": stats["mass_kg"],
        "added_kg": stats["added_kg"],
        "material": stats["material"],
        "blocks": _rows(pieces, placed),
        "about": _about(version, values),
        "findings": [f for f in screened.findings if f["outcome"] != "pass"],
        "stats": stats,
        "made_of": _made_of(pieces, placed),
        "version": version.version,
        "lines": [line for result in placed.values() for line in result.tried],
    }


def _made_of(pieces: Pieces, placed: dict) -> dict[str, Any]:
    """Everything a design is made of, in the part's coordinates: each block's ribs and pads, its
    holes, the faces it moves and how far, what it is cast in."""

    def rib_of(rib) -> dict[str, Any]:
        return {
            "start": [round(v, 2) for v in rib.start],
            "end": [round(v, 2) for v in rib.end],
            "thickness_mm": rib.thickness_mm,
            "heights_mm": [round(h, 2) for h in rib.heights],
            "pull": [round(v, 4) for v in rib.pull],
            "draft_deg": rib.draft_deg,
            "edge_round_mm": rib.edge_round_mm,
            "flange_width_mm": rib.flange_width_mm,
            "flange_thickness_mm": rib.flange_thickness_mm,
        }

    out: dict[str, Any] = {}
    for placement in pieces.placements:
        result = placed[placement.id]
        out[placement.id] = {
            "kind": "ribs",
            "root_fillet_mm": placement.section.root_fillet_mm,
            "ribs": [rib_of(r) for r in result.ribs],
            "pads": [rib_of(r) for r in result.pads],
        }
    for hole_set in pieces.holes:
        out[hole_set.id] = {
            "kind": "holes",
            "holes": [
                {
                    "centre": [round(v, 2) for v in h.centre],
                    "axis": [round(v, 4) for v in h.axis],
                    "diameter_mm": 2.0 * h.radius_mm,
                    "depth_mm": round(h.depth_mm, 2),
                    "above_mm": round(h.above_mm, 2),
                }
                for h in placed[hole_set.id].holes
            ],
        }
    for offset in pieces.offsets:
        out[offset.id] = {
            "kind": "thicken",
            "faces": list(offset.faces),
            "offset_mm": offset.offset_mm,
            "blend_mm": offset.blend_mm,
        }
    if pieces.material is not None:
        out[pieces.material.id] = {"kind": "material", "material": pieces.material.material}
    return out


def _archived(design: dict) -> dict:
    """A design as Go writes it: all of it but the lines it is drawn with, which follow from it."""
    return {k: v for k, v in design.items() if k != "lines"}


def _listed(design: dict) -> dict:
    """A design as the list of designs shows it."""
    keep = ("index", "values", "outcome", "ribs", "pads", "holes", "mass_kg", "added_kg")
    return {
        **{k: design[k] for k in keep},
        "material": design["material"],
        "blocks": design["blocks"],
        "about": design["about"],
        "findings": design["findings"],
    }


def _spread_of(designs: list[dict]) -> dict[str, Any]:
    """How the designs kept spread over what they vary: each setting's values, counted, block by
    block; and their ribs, holes and mass, from least to most."""
    out: dict[str, Any] = {"settings": {}}
    for design in designs:
        for block, values in design["values"].items():
            for name, value in values.items():
                shown = f"{value:g}" if isinstance(value, float) else str(value)
                counts = out["settings"].setdefault(f"{block}.{name}", {})
                counts[shown] = counts.get(shown, 0) + 1
    for what in ("ribs", "holes", "pads", "mass_kg"):
        numbers = [d[what] for d in designs if d.get(what) is not None]
        if numbers:
            out[what] = {"least": min(numbers), "most": max(numbers)}
    return out


def _about(version: studies.StudyVersion, values: dict[str, dict[str, Any]]) -> dict[str, str]:
    """A design in a few words per block: what varies in it, at the value it takes - only what
    makes a difference to its pattern: no spokes for a grid, no free layout but for free lines."""
    out = {}
    for block in version.blocks:
        if block.id not in values:
            continue
        chosen = {n: d.suggested for n, d in block.free.items()}
        chosen.update(values[block.id])
        used = studies.effective(block, chosen)
        varied = [
            n
            for n, d in block.free.items()
            if not d.fixed and n in used and n in chosen and n not in HIDDEN
        ]
        said = [_said_value(n, chosen[n], block.free[n]) for n in varied]
        if chosen.get("generator") == "free":
            # Free lines are told apart by their layout, which nobody sets.
            lines = f"{PATTERNS_SAID['free']} (layout {int(chosen.get('layout') or 0)})"
            if "generator" in varied:
                said[varied.index("generator")] = lines
            else:
                said.insert(0, lines)
        out[block.id] = ", ".join(said)
    return out


# Patterns as the card names them.
PATTERNS_SAID = {
    "parallel": "parallel ribs",
    "grid": "square grid",
    "triangle": "triangle grid",
    "radial": "spokes",
    "free": "free lines",
}


def _said_value(name: str, value: Any, domain: studies.Domain) -> str:
    """One setting at a value, as a person says it: a pattern by name, a height in percent, a
    length in its unit."""
    if name == "generator":
        return PATTERNS_SAID.get(str(value), str(value))
    label = SETTING_LABELS.get(name, name.replace("_", " "))
    if name == "height_fraction" and isinstance(value, int | float):
        return f"{label} {float(value) * 100:g}%"
    unit = domain.unit or _unit(name)
    if isinstance(value, int | float) and unit:
        return f"{label} {_value(value)}{'' if unit == '°' else ' '}{unit}"
    return f"{label} {_value(value)}"


def _value(value: Any) -> str:
    return f"{value:g}" if isinstance(value, float) else str(value)


def design_paths(session: Session, index: int, run: str | None = None) -> dict:
    """The lines of one of the designs a campaign kept - in this session, or in a kept ``run`` - to
    draw on the part: as the run kept them beside its designs; or, for a run kept without them,
    placed again from its values on the grid the campaign placed every design on."""
    found = _run(session, run) if run is not None else None
    if isinstance(found, str):
        return {"cannot": found}
    version, designs = found if found is not None else (None, kept(session))
    if not 0 <= index < len(designs):
        return {"cannot": f"there is no design {index}"}
    design = designs[index]
    if "lines" not in design and run is not None:
        rows = _kept_paths(session, run)
        if rows is not None and index < len(rows):
            design["lines"] = _expanded(json.loads(rows[index]))
    if "lines" not in design:
        if version is None:
            study = studies.active(session.project)
            if study is None:
                return {"cannot": "there is no study yet"}
            version = study.current
        pieces = _pieces(version, design["values"], _present(design))
        placed = _place(session, version, pieces, _pieces(version).radius())
        if "cannot" in placed:
            return placed
        design["lines"] = [line for result in placed.values() for line in result.tried]
    return {
        "lines": design["lines"],
        "ribs": design["ribs"],
        "holes": design["holes"],
        "pads": design["pads"],
        "paths": len(design["lines"]),
        "summary": "; ".join(f"{b}: {r['says']}" for b, r in design["blocks"].items()),
    }


def _present(design: dict) -> set[str] | None:
    """The variants a design of a campaign holds; None for a design of a study, which holds every
    block."""
    held = design.get("variants")
    return set(held) if held is not None else None


# Every design's paths, beside a run's designs: a line of JSON each, in the same order.
PATHS = "paths.jsonl"


def _compact(lines: list[dict]) -> list[list]:
    """A design's paths as they are kept: each line its two ends and what became of it - and, for
    what was made, how wide it is and which way it stands."""
    return [
        [
            *line["a"],
            *line["b"],
            line["outcome"],
            *([line["mm"], *line["up"]] if "mm" in line else []),
        ]
        for line in lines
    ]


def _expanded(rows: list[list]) -> list[dict]:
    """A design's paths as kept, as the lines drawn."""
    out = []
    for row in rows:
        line = {"a": row[0:3], "b": row[3:6], "outcome": row[6]}
        if len(row) >= 11:
            line.update(mm=row[7], up=row[8:11])
        out.append(line)
    return out


def _kept_paths(session: Session, run: str) -> list[str] | None:
    """The paths a run kept beside its designs, a line of JSON a design, read once - or None for a
    run kept without them."""
    path = archive_root(session.project) / run / PATHS
    if not _safe(run) or not path.is_file():
        return None
    key = ("paths", run, path.stat().st_mtime_ns)
    if key not in session.memo:
        session.memo[key] = path.read_text(encoding="utf-8").splitlines()
    return session.memo[key]


def archive_root(project: Project) -> Path:
    """Where Go keeps the designs it made for a project: ``_archived_designs`` beside the folder
    projects live in - the repository's, for a project in ``assets/`` - then the project's name. A
    project's own folder holds only what the engineer brought and decided."""
    return project.root.resolve().parent.parent / ARCHIVE_DIR / project.name


def runs(session: Session) -> list[dict]:
    """Every run of Go kept for the open project, newest first: its study and version, how many
    designs it kept of how many tried, and how long it took - from what Go wrote beside them."""
    root = archive_root(session.project)
    out = []
    for folder in root.iterdir() if root.is_dir() else []:
        summary = folder / "summary.json"
        if not (summary.is_file() and (folder / "designs.jsonl").is_file()):
            continue
        if not (folder / "study.json").is_file():
            continue
        said = json.loads(summary.read_text(encoding="utf-8"))
        campaign = folder / "campaign.json"
        chosen = json.loads(campaign.read_text(encoding="utf-8")) if campaign.is_file() else {}
        out.append(
            {
                "run": folder.name,
                "name": chosen.get("name") or folder.name,
                "study": said.get("study"),
                "version": said.get("version"),
                "made": said.get("made"),
                "tried": said.get("tried"),
                "seconds": said.get("seconds"),
                "seed": chosen.get("seed"),
                "off": chosen.get("off") or {},
                "built": len(_built(session, folder.name)),
                "where": f"{ARCHIVE_DIR}/{session.project.name}/{folder.name}",
                "when": summary.stat().st_mtime,
            }
        )
    return sorted(out, key=lambda r: -r["when"])


def _run(session: Session, run: str) -> tuple[studies.StudyVersion, list[dict]] | str:
    """A kept run of Go read back - the study version it was made from, and its designs - or why
    it cannot be. The last few read are kept in hand."""
    if run in session.loaded:
        return session.loaded[run]
    folder = archive_root(session.project) / run
    if not _safe(run) or not (folder / "designs.jsonl").is_file():
        return f"there is no run {run} kept for {session.project.name}"
    version = studies.StudyVersion.model_validate_json(
        (folder / "study.json").read_text(encoding="utf-8")
    )
    assert session.extraction.features is not None
    _, lost = studies.resolve(version, session.extraction.features)
    if lost:
        return f"run {run} names what the part does not have: " + "; ".join(lost[:3])
    with (folder / "designs.jsonl").open(encoding="utf-8") as lines:
        designs = [json.loads(line) for line in lines if line.strip()]
    while len(session.loaded) >= 2:
        session.loaded.pop(next(iter(session.loaded)))
    session.loaded[run] = (version, designs)
    return version, designs


def kept_of(session: Session, run: str | None) -> list[dict] | str:
    """The designs of a kept ``run`` of Go, or - with none - of the study as accepted; or why
    there are none."""
    if run is None:
        return kept(session)
    found = _run(session, run)
    return found if isinstance(found, str) else found[1]


def kept(session: Session) -> list[dict]:
    """The designs Go kept of the active study's current version: those in hand, or read back from
    where Go keeps them - the newest campaign of that version."""
    study = studies.active(session.project)
    if study is None:
        return []
    version = study.current.version
    if session.designs and session.designs[0].get("version") == version:
        return session.designs
    mine = [r for r in runs(session) if r["study"] == study.name and r["version"] == version]
    if not mine:
        return session.designs
    found = _run(session, mine[0]["run"])
    return session.designs if isinstance(found, str) else found[1]


# The stages a design goes through, in order, and whether each is built yet: placed and screened,
# its field built, meshed, its solver set up, its results.
STAGES = (
    ("P", "Paths", True, "placed and screened: where its ribs, pads and holes go"),
    ("F", "Field", True, "its field built and checked: the geometry, as voxels and a surface"),
    ("M", "Mesh", True, "meshed for the solver, by CGAL from its field"),
    ("S", "Setup", True, "the solver deck's supports, couplings and loads, carried by CAD face"),
    ("R", "Results", True, "solved: displacement and stress everywhere, the deck's signals"),
)

# What each stage takes, and what it gives - the pipeline in the open.
STAGE_FLOW = {
    "P": (
        "the variants a design holds, each at a point of what it allows; the part's faces and "
        "features; each variant's rules",
        "where every rib, pad and hole goes, with what repair left out; how it screened; what it "
        "weighs; its paths, drawn at once - seconds a thousand designs",
    ),
    "F": (
        "a design's paths; the part's distance field at the preview or full grid",
        "the design's field - ribs joined with their fillets, faces moved, holes cut - its "
        "surfaces, its new metal as cells, and every field check - minutes a design",
    ),
    "M": (
        "a design's field; the solver deck mesh's element sizes",
        "quadratic tetrahedra, two through every rib the design adds - seconds a design",
    ),
    "S": (
        "the mesh; the deck's supports, couplings and loads, tied to the CAD's faces",
        "the deck's setup on the design's mesh, every group where the deck put it",
    ),
    "R": (
        "the mesh and its setup",
        "displacement and stress at every node, the deck's signals, and the design's record - "
        "seconds a design on the GPU",
    ),
}

# How designs may be drawn, as the campaign card offers them.
METHODS = (
    (
        "even",
        "Spread evenly",
        "a scrambled Sobol sequence: every point of every variant taken "
        "about as often, choices balanced - the widest spread for the fewest designs",
    ),  # fmt: skip
    (
        "random",
        "Random",
        "each design drawn at random from what the variants allow - every "
        "choice, and every step of a range, as likely as the next",
    ),  # fmt: skip
    (
        "every",
        "Every combination",
        "every set of the variants at every point of each - when that "
        "is no more than the designs asked for",
    ),  # fmt: skip
)


def campaign_pipeline(session: Session) -> dict:
    """What a campaign runs, all of it: the checks every design is screened by, the rules of thumb
    they rest on with their sources, how designs are spread, the stages each design goes through
    and which are built - and the runs kept so far. The study's blocks and rules are the card's."""
    from . import blocks as filled
    from . import checks, placement
    from .screen import CHECKS

    rules = []
    for name in ("rib_to_wall", "root_gap", "hole_ligament", "min_wall_mm"):
        value, source = knowledge.rule(name)
        rules.append({"name": name, "value": value, "source": source})
    return {
        "checks": [{"name": n, "rule": r, "source": s} for n, r, s in CHECKS],
        "placement": [*placement.described(), *filled.described()],
        "full_checks": checks.described(),
        "repair": {
            "says": "a design whose pieces break a rule between them is mended by CP-SAT, which "
            "leaves out the fewest ribs, pads or holes - holes before ribs where it is a tie - so "
            "every rule holds; a design repair cannot save is drawn again",
            "rules": list(REPAIRED),
        },
        "interfaces_clear_mm": studies.INTERFACE_CLEARANCE_MM,
        "knowledge": rules,
        "materials": [
            {k: m[k] for k in ("id", "name", "density_kg_m3", "min_wall_mm", "source")}
            for m in knowledge.materials()
        ],
        "methods": [{"key": k, "label": label, "says": says} for k, label, says in METHODS],
        "sampler": {
            "says": "each variant alone first: points of what it allows placed, repaired and "
            "screened, those that pass its pool; then designs - a set of the variants, as many "
            "with one as with two or all, and a pool point of each - placed together, repaired, "
            "screened; alike designs kept once",
            "pool": {"least": POOL[0], "most": POOL[1], "tries": POOL_TRIES},
            "tries_per_design": TRIES_PER_DESIGN,
        },
        "stages": [
            {
                "key": k,
                "label": label,
                "built": built,
                "says": says,
                "takes": STAGE_FLOW[k][0],
                "gives": STAGE_FLOW[k][1],
            }
            for k, label, built, says in STAGES
        ],
        "runs": runs(session),
    }


# The rules repair mends by leaving pieces out, in the words the verdict uses.
REPAIRED = ("root gap", "a wedge of sand", "holes clear of ribs", "an X crossing")


BUILT = re.compile(r"(\d+)-(preview|full)\.json")
# What is kept of a design built: the surfaces it changes, and its new metal as cells.
KEPT_BUILT = ("mesh", "cells")
# The most designs the list shows as those that differ most.
MOST_VARIED = 100


def _built(session: Session, run: str) -> dict[int, dict[str, str]]:
    """The designs of a run built so far: at which fidelities, and what each came out as. Read
    once for as long as the folder is unchanged."""
    folder = archive_root(session.project) / run / "built"
    if not folder.is_dir():
        return {}
    verdicts = [p for p in folder.iterdir() if BUILT.fullmatch(p.name)]
    key = ("built", run, tuple(sorted((p.name, p.stat().st_mtime_ns) for p in verdicts)))
    if key not in session.memo:
        out: dict[int, dict[str, str]] = {}
        for path in verdicts:
            found = BUILT.fullmatch(path.name)
            if found:
                said = json.loads(path.read_text(encoding="utf-8"))
                out.setdefault(int(found[1]), {})[found[2]] = str(said.get("outcome", "pass"))
        session.memo[key] = out
    return session.memo[key]


SOLVED_RECORD = re.compile(r"(\d+)\.json")


def _solved(session: Session, run: str) -> dict[int, dict[str, str]]:
    """The designs of a run the runner took on: how far each got - built, meshed, set up, solved -
    and how each stage came out, from the records it left. Read once for as long as the folder is
    unchanged."""
    folder = archive_root(session.project) / run / "solved"
    if not folder.is_dir():
        return {}
    paths = [p for p in folder.iterdir() if SOLVED_RECORD.fullmatch(p.name)]
    key = ("solved", run, tuple(sorted((p.name, p.stat().st_mtime_ns) for p in paths)))
    if key not in session.memo:
        out: dict[int, dict[str, str]] = {}
        for path in paths:
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            done = record.get("stages") or {}
            state: dict[str, str] = {}
            for letter, stage in (("F", "build"), ("M", "mesh"), ("S", "setup"), ("R", "solve")):
                if stage in done:
                    verdict = (record.get("build") or {}).get("outcome") if letter == "F" else None
                    state[letter] = str(verdict or "pass")
                elif record.get("outcome") != "solved":
                    state[letter] = "reject"  # where it was set aside
                    break
            out[int(path.stem)] = state
        session.memo[key] = out
    return session.memo[key]


def _solved_brief(session: Session, run: str, index: int) -> dict | None:
    """How the runner made and solved one design, briefly - or None when it has not taken it on:
    solved or set aside and why, the route and its times, the mesh, and the deck's signals."""
    if not _safe(run):
        return None
    path = archive_root(session.project) / run / "solved" / f"{int(index)}.json"
    if not path.is_file():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    mesh = record.get("mesh") or {}
    return {
        "outcome": record.get("outcome"),
        "reason": record.get("reason", ""),
        "route": record.get("route", ""),
        "seconds": record.get("seconds"),
        "stages": record.get("stages") or {},
        "mesh": {k: mesh.get(k) for k in ("tets", "unknowns", "quality_min")},
        "mass_kg": record.get("mass_kg"),
        "signals": [s for s in record.get("signals") or [] if s.get("kind") == "derived"],
        "solver": {k: (record.get("solver") or {}).get(k) for k in ("name", "residual")},
    }


def _stages(
    design: dict, built: dict[str, str] | None, solved: dict[str, str] | None = None
) -> dict[str, str]:
    """Where one design is in its stages, and how each came out: its paths as screened - pass or
    warn, since a run keeps nothing screened out - its field as checked, in full if it was built
    in full, and its mesh, setup and results as the runner left them; ``none`` for a stage not
    reached."""
    field = "none"
    if built:
        field = built.get("full") or built.get("preview") or "none"
    solved = solved or {}
    return {
        "P": str(design.get("outcome", "pass")),
        "F": field if field != "none" else solved.get("F", "none"),
        "M": solved.get("M", "none"),
        "S": solved.get("S", "none"),
        "R": solved.get("R", "none"),
    }


def _order(session: Session, run: str, version: studies.StudyVersion, designs: list[dict]):
    """The designs of a run that differ most, most different first: each further from those before
    it than any other - so the first 20 of them are the 20 that differ most."""
    key = ("varied", run, len(designs))
    if key not in session.memo:
        features = session.extraction.features
        assert features is not None
        _, e1, e2 = plane_of(_pull_of(version, features))
        session.memo[key] = most_varied(designs, MOST_VARIED, (e1, e2))
    return session.memo[key]


def run_designs(
    session: Session,
    run: str,
    show: str = "varied",
    k: int = 30,
    offset: int = 0,
    limit: int = 200,
    variant: str | None = None,
) -> dict:
    """A run's designs, as the list shows them: the ``k`` that differ most, those built, or a page
    of all of them - only those holding ``variant``, when asked - each with its stages, the
    variants it holds and what repair left out of it; and how many are at each stage."""
    found = _run(session, run)
    if isinstance(found, str):
        return {"cannot": found}
    version, designs = found
    built = _built(session, run)
    solved = _solved(session, run)
    varied_order = _order(session, run, version, designs)
    rank = {index: position + 1 for position, index in enumerate(varied_order)}
    everyone = [b.id for b in version.blocks]

    def holds(i: int) -> bool:
        return variant is None or variant in (designs[i].get("variants") or everyone)

    if show == "varied":
        order = [i for i in varied_order if holds(i)][: max(1, min(int(k), MOST_VARIED))]
    elif show == "built":
        order = sorted(i for i in set(built) | set(solved) if i < len(designs) and holds(i))
    else:
        matching = [i for i in range(len(designs)) if holds(i)]
        order = matching[max(0, offset) : max(0, offset) + limit]
    rows = [
        {
            **{key: designs[i][key] for key in ("index", "ribs", "holes", "pads", "mass_kg")},
            "material": designs[i].get("material"),
            "rank": rank.get(i),
            "stages": _stages(designs[i], built.get(i), solved.get(i)),
            "short": _short(version, designs[i]),
            "variants": designs[i].get("variants") or everyone,
            "left_out": len(designs[i].get("left_out") or []),
        }
        for i in order
    ]
    reached = {
        letter: sum(s.get(letter) in ("pass", "warn") for s in solved.values())
        for letter in ("F", "M", "S", "R")
    }
    fields = set(built) | {i for i, s in solved.items() if s.get("F") in ("pass", "warn")}
    counts = {"P": len(designs), "F": len(fields), **{k: reached[k] for k in ("M", "S", "R")}}
    return {
        "run": run,
        "version": version.version,
        "of": len(designs),
        "holding": sum(holds(i) for i in range(len(designs))),
        "variant": variant,
        "show": show,
        "rows": rows,
        "counts": counts,
        "built": [
            [i, _stages(designs[i], built.get(i), solved.get(i))["F"]]
            for i in sorted(fields)
            if i < len(designs)
        ],
        "blocks": {b.id: b.add for b in version.blocks},
        "labels": _labels(session, run),
    }


def _labels(session: Session, run: str) -> dict[str, str]:
    """What a campaign calls each of its variants, by code; nothing for a run of a study."""
    manifest = archive_root(session.project) / run / "campaign.json"
    if not _safe(run) or not manifest.is_file():
        return {}
    said = json.loads(manifest.read_text(encoding="utf-8"))
    return {v["id"]: v.get("label", v["id"]) for v in said.get("variants", [])}


def run_design(session: Session, run: str, index: int) -> dict:
    """One design of a run in full: what each block made, how it screened, what it weighs, where
    it is in its stages, and its verdict at each fidelity it was built at."""
    found = _run(session, run)
    if isinstance(found, str):
        return {"cannot": found}
    version, designs = found
    if not 0 <= index < len(designs):
        return {"cannot": f"there is no design {index} in {run}"}
    design = designs[index]
    built = _built(session, run)
    verdicts = {}
    for fidelity in built.get(index, {}):
        path = archive_root(session.project) / run / "built" / f"{index}-{fidelity}.json"
        verdicts[fidelity] = json.loads(path.read_text(encoding="utf-8"))
    rank = {i: p + 1 for p, i in enumerate(_order(session, run, version, designs))}
    everyone = [b.id for b in version.blocks]
    held = design.get("variants") or everyone
    return {
        **_listed(design),
        "run": run,
        "rank": rank.get(index),
        "short": _short(version, design),
        "stages": _stages(design, built.get(index), _solved(session, run).get(index)),
        "built": verdicts,
        "solved": _solved_brief(session, run, index),
        "variants": held,
        "absent": [b for b in everyone if b not in held],
        "labels": _labels(session, run),
        "left_out": design.get("left_out") or [],
        "left_out_said": left_out_said(design.get("left_out") or []),
        "recipe": design.get("recipe"),
        "seed": design.get("seed"),
    }


def keep_built(
    session: Session,
    run: str,
    index: int,
    fidelity: str,
    reply: dict,
    blobs: dict[str, bytes],
) -> None:
    """A design of a run, built: its verdict, the surfaces it changes and its new metal as cells,
    kept beside the run - its field stage done."""
    folder = archive_root(session.project) / run / "built"
    folder.mkdir(parents=True, exist_ok=True)
    for kind, blob in blobs.items():
        assert kind in KEPT_BUILT, kind
        (folder / f"{index}-{fidelity}.{kind}").write_bytes(blob)
    # The verdict last: a design counts as built once it is there.
    (folder / f"{index}-{fidelity}.json").write_text(json.dumps(reply, indent=1), encoding="utf-8")


def built_blob(session: Session, run: str, index: int, fidelity: str, kind: str) -> bytes | None:
    """What was kept of a built design - its surfaces, or its cells - or None if it was not
    built."""
    if not _safe(run) or kind not in KEPT_BUILT or fidelity not in ("preview", "full"):
        return None
    path = archive_root(session.project) / run / "built" / f"{index}-{fidelity}.{kind}"
    return path.read_bytes() if path.is_file() else None


def _safe(run: str) -> bool:
    """A run's name as Go writes it: one folder, nothing that climbs out of it."""
    return bool(re.fullmatch(r"[\w][\w.\- ]*", run)) and ".." not in run


def varied(session: Session, k: int = 30, run: str | None = None) -> dict:
    """The ``k`` designs Go kept that differ most from each other - of the study as accepted, or of
    a kept ``run`` - each as a plan: its ribs and pads as lines, its holes as circles, seen along
    the pull over the outlines of what the study names and of the part's bores; with a few words a
    block, and what the list shows."""
    if run is not None:
        found = _run(session, run)
        if isinstance(found, str):
            return {"cannot": found}
        version, designs = found
    else:
        study = studies.active(session.project)
        designs = kept(session)
        if study is None or not designs:
            return {"cannot": "Go has kept no designs of the study as accepted yet"}
        version = study.current
    features, tess = session.extraction.features, session.extraction.tess
    assert features is not None and tess is not None
    _, e1, e2 = plane_of(_pull_of(version, features))
    picked = _order(session, run or "", version, designs)[:k]
    refs = sorted({r for b in version.blocks for r in (*b.where.support, *b.where.anchors)})
    outlined = _memo_outlines(session, features, tess, refs, (e1, e2))
    rows = []
    for position in picked:
        design = designs[position]
        rows.append(
            {
                **_listed(design),
                "plan": planned(design["made_of"], (e1, e2)),
                "short": _short(version, design),
            }
        )
    points = [p for line in outlined for p in (line[:2], line[2:])]
    for row in rows:
        plan = row["plan"]
        points += [p for line in [*plan["ribs"], *plan["pads"]] for p in (line[:2], line[2:4])]
        points += [h[:2] for h in plan["holes"]]
    xy = np.array(points, dtype=float) if points else np.zeros((1, 2))
    lo, hi = xy.min(axis=0), xy.max(axis=0)
    pad = 0.03 * float(max(hi - lo))
    return {
        "of": len(designs),
        "run": run,
        "designs": rows,
        "outlines": outlined,
        "bounds": [*(lo - pad).round(1).tolist(), *(hi + pad).round(1).tolist()],
        "blocks": {b.id: b.add for b in version.blocks},
    }


def _memo_outlines(session: Session, features, tess, refs: list[str], axes) -> list[list[float]]:
    key = ("outlines", tuple(refs), tuple(np.round(np.concatenate(axes), 6)))
    if key not in session.memo:
        session.memo[key] = outlines(features, tess, refs, axes)
    return session.memo[key]


def _pull_of(version: studies.StudyVersion, features) -> np.ndarray | None:
    """Which way the study's designs are looked at in plan: along its pull - a direction, or the
    way a face named for it faces."""
    pull = version.pull
    if pull is None:
        return None
    if pull.direction is not None:
        return np.asarray(pull.direction, dtype=float)
    feature = features.get(pull.along) if pull.along else None
    return None if feature is None or feature.normal is None else np.asarray(feature.normal)


def _short(version: studies.StudyVersion, design: dict) -> list[list[str]]:
    """A design in a few words a block: the pattern and how many ribs, and how thick; the holes;
    how far faces moved; the material."""
    out = []
    for block in version.blocks:
        made = design.get("made_of", {}).get(block.id)
        if made is None:
            continue
        chosen = {n: d.suggested for n, d in block.free.items()}
        chosen.update(design["values"].get(block.id, {}))
        kind = made.get("kind")
        if kind == "ribs":
            ribs = made.get("ribs", [])
            thick = f", {_value(ribs[0]['thickness_mm'])} mm" if ribs else ""
            words = f"{chosen.get('generator', 'ribs')} ×{len(ribs)}{thick}"
            if made.get("pads"):
                words += f", {len(made['pads'])} pads"
        elif kind == "holes":
            holes = made.get("holes", [])
            size = f" Ø{_value(holes[0]['diameter_mm'])}" if holes else ""
            words = f"{chosen.get('pattern', '')}{size} ×{len(holes)}"
        elif kind == "thicken":
            words = f"{float(made.get('offset_mm', 0.0)):+g} mm"
        else:
            words = str(made.get("material", ""))
        out.append([block.id, words])
    return out


def design_from_spec(session: Session, fidelity: str, levers: dict[str, float]) -> dict:
    """A design from the active spec's current version, and its verdict - or why there is none."""
    from .. import spec as specs

    spec = specs.active(session.project)
    if spec is None:
        return {"cannot": "there is no spec yet"}
    version = spec.current
    try:
        key = (fidelity, min(p.section.root_fillet_mm for p in version.placements))
        if key not in session.opened:
            session.opened[key] = Opened.open(
                session.project, session.extraction, version, fidelity
            )
        made = make(session.opened[key], version, levers)
    except IntentError as error:
        return {"cannot": str(error)}
    session.made = made
    session.changed.add("design")
    return verdict(made)


def verdict(made: Made) -> dict:
    """A design's verdict, as the engineer reads it: their constraints first, then the checks -
    each check with how long it took - how long each step of the build took, and the part's faces
    the design cuts, which the viewer shows as the design's own surface."""
    design = made.design
    order = {"reject": 0, "warn": 1, "pass": 2}

    def rows(section: str) -> list[dict]:
        chosen = [f for f in design.findings if f.section == section]
        chosen.sort(key=lambda f: order[f.outcome])
        return [
            {
                "check": f.check,
                "outcome": f.outcome,
                "reason": f.reason,
                "rule": f.rule,
                **({"assumed": True} if f.assumed and section == "check" else {}),
                **({"cites": list(f.cites)} if f.cites else {}),
                **({"seconds": f.seconds} if f.seconds is not None else {}),
            }
            for f in chosen
        ]

    stats = design.stats
    return {
        "spec_version": made.version,
        "fidelity": made.fidelity,
        "outcome": design.outcome,
        "ribs": stats["ribs"],
        "pads": stats.get("pads", 0),
        "holes": stats.get("holes", 0),
        "added_cm3": round(stats["added_cm3"], 1),
        "mass_kg": stats.get("mass_kg"),
        "material": stats.get("material"),
        "weighed_from": stats.get("weighed_from", "surface"),
        "seconds": stats["seconds"],
        "steps": dict(stats.get("steps") or {}),
        "distance": stats.get("distance"),
        "surface": design.surface is not None,
        "cut_faces": list(stats.get("cut_faces") or []),
        "constraints": rows("constraint"),
        "checks": rows("check"),
    }
