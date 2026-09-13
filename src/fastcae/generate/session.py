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
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import ValidationError

from .. import knowledge
from .. import study as studies
from ..extract import Extraction
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
from .blocks import fill
from .intent import IntentError, Made, Opened, make
from .placement import Drilled, Placed, _Faces, place_all
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

    def __post_init__(self) -> None:
        load(self)


# --- the draft, read and written -----------------------------------------------------------------


def load(session: Session) -> None:
    """Read the draft back from the study's current version - forgetting what was not accepted."""
    session.draft, session.heard, session.attention = _nothing(), [], []
    study = studies.active(session.project)
    if study is not None:
        version = study.current
        draft = session.draft
        for block in version.blocks:
            where = block.where
            draft["blocks"].append(
                {
                    "id": block.id,
                    "add": block.add,
                    "support": [] if "support" in where.read_off else list(where.support),
                    "anchors": [] if "anchors" in where.read_off else list(where.anchors),
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
        version = studies.build(session.project, STUDY_NAME, **entries)
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
    study = studies.active(session.project)
    kept_words = study.current.words if study else []
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


def hand(session: Session, action: dict[str, Any], selected: list[int] | None = None) -> dict:
    """The draft changed by the engineer's hand on Design a variant, as :func:`edit` changes it from
    their words: what was done is said in words - "By hand: ..." - kept among the
    study's words, and everything it sets is theirs. ``selected`` is the faces selected on the
    part, which an action takes when it names nothing.

    ``action`` is one of: ``add`` a block - ``ribs`` standing on what is selected, ``webs``
    between it, faces to ``thicken``, a plate to cut ``holes`` in, or the ``material``;
    ``stand_on`` or ``end_on`` - a block's entities, or none to read them off the part;
    ``setting`` - a ``value``, a ``low`` and ``high`` with a ``step``, some ``options``, or none
    to hand it back to the part; ``keep_clear`` - of entities, or of other blocks' ``ribs:b1`` and
    ``holes:b2``, by ``clearance_mm``; ``remove`` a block; ``confirm`` a rule the part suggested,
    by id; ``designs`` - how many, from which ``seed``. The card, or ``{"refused": why}``."""
    kind = action.get("action")
    faces = [f"face:{f}" for f in sorted({int(f) for f in selected or []})]
    refs = [str(r) for r in action["refs"]] if action.get("refs") is not None else faces
    block = action.get("block")
    ids = [b["id"] for b in session.draft["blocks"]]
    if kind != "add" and kind not in ("confirm", "designs") and block not in ids:
        return {"refused": f"there is no block {block} - blocks: {', '.join(ids) or 'none yet'}"}
    change: dict[str, Any] = {}
    if kind == "add":
        what = str(action.get("add") or "")
        if what not in BY_HAND:
            return {"refused": f"a block adds {', '.join(BY_HAND)} - not {what!r}"}
        if what != "material" and not refs:
            return {"refused": "select the faces on the part first, or name them"}
        casting = [b["id"] for b in session.draft["blocks"] if b.get("add") == "material"]
        if what == "material" and casting:
            return {
                "refused": f"{casting[0]} already says what the part is cast in - a part is cast "
                "in one material: narrow its choices there"
            }
        number = 1
        while f"b{number}" in ids:
            number += 1
        new = f"b{number}"
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
    elif kind == "setting":
        name = str(action.get("name") or "")
        if not name:
            return {"refused": "which setting?"}
        told = {k: action[k] for k in ("value", "low", "high", "step", "options") if k in action}
        told = {k: v for k, v in told.items() if v is not None}
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
        version = studies.build(session.project, STUDY_NAME, **entries)
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
        filled = fill(
            session.extraction,
            exit_along,
            {
                "add": block.get("add", "ribs"),
                "support": block["support"],
                "anchors": block["anchors"],
                "given": {
                    **{n: _fixed_domain(s) for n, s in fixed.items()},
                    **{n: _provisional(s) for n, s in block["settings"].items() if n not in fixed},
                },
            },
            floor,
        )
        free = filled["free"]
        for name, setting in block["settings"].items():
            free[name] = {"unit": _unit(name), **_domain(setting, free.get(name, {}))}
        blocks.append(
            {
                "id": block["id"],
                "add": block.get("add", "ribs"),
                "where": {**filled["where"], "span": block.get("span") or "union"},
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
        reports[block["id"]] = {k: filled[k] for k in ("needed", "problems", "cannot", "note")}
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
        "prefer": list(draft["prefer"]),
        "objectives": list(draft["objectives"]),
        "pull": draft["pull"] or pull,
        "target": draft["target"],
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
    version = studies.build(session.project, STUDY_NAME, **entries)
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
    study = studies.active(session.project)
    accepted = study.current if study is not None else None
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
        "open": studies.open_items(version),
        "assumed": studies.assumed(version),
        "attention": list(session.attention),
        "names": names(features, real),
        "runs": runs(session),
    }


def _refused(session: Session, why: str) -> dict:
    study = studies.active(session.project)
    return {
        "accepted": study.current.version if study is not None else None,
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
    }


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
                "keep_clear": [_rule(c) for c in mine if c.kind == "keep_clear_of"],
                "settings": [
                    {
                        "name": name,
                        "label": SETTING_LABELS.get(name, name.replace("_", " ")),
                        "says": d.says(),
                        "source": d.source,
                        "fixed": d.fixed,
                        "basis": d.basis,
                        # What it may take, to change by hand on the card.
                        "domain": {
                            "low": d.low,
                            "high": d.high,
                            "step": d.step,
                            "options": d.options,
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
    version: studies.StudyVersion, values: dict[str, dict[str, Any]] | None = None
) -> Pieces:
    """Every block that can be built, at the values given for it - or at its suggested point - as
    what it is made from, and why each other block cannot. Webs with nothing under them stand along
    the pull when it is a direction and what they join runs along it."""
    pieces = Pieces()
    pull = version.pull.direction if version.pull is not None else None
    for block in version.blocks:
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
        rows[offset.id] = {
            "moved_mm": offset.offset_mm,
            "says": f"{', '.join(offset.faces)} {way}"
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
            version = studies.build(session.project, STUDY_NAME, **entries)
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


def design_from_study(
    session: Session,
    fidelity: str,
    values: dict[str, dict[str, Any]] | None = None,
    run: str | None = None,
) -> dict:
    """A design from the active study's current version - or from the study version a kept
    ``run`` of Go was made from - every block at the values given for it, or at its suggested
    point, and its verdict, with what the study holds that nothing enforces yet and what nobody
    confirmed. Or why there is none."""
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
    assert session.extraction.features is not None
    _, lost = studies.resolve(version, session.extraction.features)
    if lost:
        return {"cannot": "the part is not the one the study names: " + "; ".join(lost[:3])}
    pieces = _pieces(version, values)
    if not pieces.any():
        return {"cannot": "; ".join(pieces.cannot) or "nothing the study asks for can be made yet"}
    point = _spec_of(version, pieces)
    radius = pieces.radius()
    if fidelity == "preview":
        # Every preview of a study on one grid - no finer than the one its designs were placed
        # on - built once: a design with a smaller fillet waits for full to be held to it.
        radius = max(radius, _pieces(version).radius())
    try:
        opened = _opened(session, point, fidelity, radius)
        made = make(opened, point, {}, finder=_measure(session), memo=session.memo)
    except IntentError as error:
        return {"cannot": str(error)}
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
        opened = _opened(session, _spec_of(version, first), "preview", radius)
    except IntentError as error:
        yield {"type": "error", "message": str(error)}
        return
    extraction = session.extraction
    features = extraction.features
    assert features is not None
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

    def tried_at(values: dict[str, dict[str, Any]]) -> tuple[Pieces, dict, Screened] | str:
        pieces = _pieces(version, values)
        placed = _place(session, version, pieces, radius)
        if "cannot" in placed:
            return str(placed["cannot"])
        screened = screen(
            features,
            opened.base,
            pieces.placements,
            pieces.holes,
            pieces.offsets,
            pieces.material,
            placed,
            walls,
            opened.surface.volume_mm3,
            set(off["checks"]),
        )
        return pieces, placed, screened

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
            pieces, placed, screened = outcome
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
                pieces, placed, screened = outcome
                if screened.outcome != "reject":
                    repaired += 1
            if screened.outcome == "reject":
                rejected.update(f["check"] for f in screened.rejected())
                if tried % 25 == 0:
                    yield progress()
                continue
            key = _key(pieces, placed)
            if key in seen:
                rejected["alike"] += 1
                continue
            seen.add(key)
            design = _design(len(session.designs), version, values, pieces, placed, screened)
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
        parts.append(("raised", placement.id, result.raised_mm))
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
            "floor_raised_mm": result.raised_mm,
            "floor_faces": list(result.raised_faces),
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
    """A design in a few words per block: what varies in it, at the value it takes."""
    out = {}
    for block in version.blocks:
        if block.id not in values:
            continue
        chosen = {n: d.suggested for n, d in block.free.items()}
        chosen.update(values[block.id])
        varied = [n for n, d in block.free.items() if not d.fixed]
        out[block.id] = ", ".join(
            f"{SETTING_LABELS.get(n, n)} {_value(chosen.get(n))}" for n in varied if n in chosen
        )
    return out


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
        pieces = _pieces(version, design["values"])
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


# Every design's paths, beside a run's designs: a line of JSON each, in the same order.
PATHS = "paths.jsonl"


def _compact(lines: list[dict]) -> list[list]:
    """A design's paths as they are kept: each line its two ends and what became of it."""
    return [[*line["a"], *line["b"], line["outcome"]] for line in lines]


def _expanded(rows: list[list]) -> list[dict]:
    """A design's paths as kept, as the lines drawn."""
    return [{"a": row[0:3], "b": row[3:6], "outcome": row[6]} for row in rows]


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
    ("M", "Mesh", False, "meshed for the solver"),
    ("S", "Setup", False, "loads, supports and the solver deck"),
    ("R", "Results", False, "solved: stresses, displacements, frequencies"),
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
        "interfaces_clear_mm": studies.INTERFACE_CLEARANCE_MM,
        "knowledge": rules,
        "materials": [
            {k: m[k] for k in ("id", "name", "density_kg_m3", "min_wall_mm", "source")}
            for m in knowledge.materials()
        ],
        "sampler": {
            "says": "each block's free settings spread alone by a scrambled Sobol sequence, the "
            "points that make something kept; then a Sobol spread over which of each block's "
            "points to combine; a design screened out by one block alone tries other points of "
            f"that block, {REPAIRS} times",
            "pool": {"least": POOL[0], "most": POOL[1], "tries": POOL_TRIES},
            "tries_per_design": TRIES_PER_DESIGN,
        },
        "stages": [
            {"key": k, "label": label, "built": built, "says": says}
            for k, label, built, says in STAGES
        ],
        "runs": runs(session),
    }


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


def _stages(design: dict, built: dict[str, str] | None) -> dict[str, str]:
    """Where one design is in its stages, and how each came out: its paths as screened - pass or
    warn, since a run keeps nothing screened out - and its field as checked, in full if it was
    built in full; ``none`` for a stage not reached."""
    field = "none"
    if built:
        field = built.get("full") or built.get("preview") or "none"
    return {
        "P": str(design.get("outcome", "pass")),
        "F": field,
        "M": "none",
        "S": "none",
        "R": "none",
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
) -> dict:
    """A run's designs, as the list shows them: the ``k`` that differ most, those built, or a page
    of all of them - each with its stages - and how many are at each stage."""
    found = _run(session, run)
    if isinstance(found, str):
        return {"cannot": found}
    version, designs = found
    built = _built(session, run)
    varied_order = _order(session, run, version, designs)
    rank = {index: position + 1 for position, index in enumerate(varied_order)}
    if show == "varied":
        order = varied_order[: max(1, min(int(k), MOST_VARIED))]
    elif show == "built":
        order = sorted(i for i in built if i < len(designs))
    else:
        order = list(range(max(0, offset), min(max(0, offset) + limit, len(designs))))
    rows = [
        {
            **{key: designs[i][key] for key in ("index", "ribs", "holes", "pads", "mass_kg")},
            "material": designs[i].get("material"),
            "rank": rank.get(i),
            "stages": _stages(designs[i], built.get(i)),
            "short": _short(version, designs[i]),
        }
        for i in order
    ]
    counts = {"P": len(designs), "F": len(built), "M": 0, "S": 0, "R": 0}
    return {
        "run": run,
        "version": version.version,
        "of": len(designs),
        "show": show,
        "rows": rows,
        "counts": counts,
        "built": [
            [i, _stages(designs[i], built[i])["F"]] for i in sorted(built) if i < len(designs)
        ],
        "blocks": {b.id: b.add for b in version.blocks},
    }


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
    return {
        **_listed(design),
        "run": run,
        "rank": rank.get(index),
        "short": _short(version, design),
        "stages": _stages(design, built.get(index)),
        "built": verdicts,
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
            if made.get("floor_raised_mm"):
                words += f", floor +{_value(made['floor_raised_mm'])}"
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
    """A design's verdict, as the engineer reads it: their constraints first, then the checks."""
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
        "seconds": stats["seconds"],
        "constraints": rows("constraint"),
        "checks": rows("check"),
    }
