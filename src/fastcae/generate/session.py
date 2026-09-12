"""The rib work on one open project: the draft of the study's next version, the study it is
accepted as, and the designs made from that.

What the routes hold between requests, and what the agent's tools work on; nothing here needs an
agent. **The Study card is the one structured view of the study**, and this is what it shows: the
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
for. **Go** makes many at once: points spread over what the study leaves free, each placed and
counted in seconds, for the engineer to look through.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from .. import study as studies
from ..extract import Extraction
from ..project import Project
from ..spec import Placement, SpecError, Version, Words, gather_words
from .blocks import fill
from .intent import IntentError, Made, Opened, make
from .placement import _Faces, place_all
from .slots import CLOSED, SETTING_LABELS, names

STUDY_NAME = "ribs"
REF = re.compile(r"\b[a-z_]+:\d+\b")
# The most the agent may ask the engineer to look at, in lines.
ATTENTION = 3
# Rules that hold for the whole study, whichever block suggested them.
STUDY_WIDE = ("smallest_radius", "draft_at_least")
# How many designs Go makes when it is not told.
GO = 24


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
    made: Made | None = None
    designs: list[dict] = field(default_factory=list)
    """What Go made: each design's values, and what became of every block's paths."""
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
    """The draft as the Study card shows it: every block - what its ribs stand on, end on and keep
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
) -> dict:
    """The draft changed from the engineer's words - their ``quotes``, exactly.

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
            block_id = _change_block(draft, change)
            for rule in change.get("rules") or []:
                if rule.get("kind") not in CLOSED:
                    _add_rule(draft, _from_words({**rule, "block": block_id}, known))
        for rule in rules or []:
            if rule.get("kind") not in CLOSED:
                _add_rule(draft, _from_words(rule, known))
        draft["prefer"] += [_from_words(p, known) for p in prefer or []]
        draft["objectives"] += [_from_words(o, known) for o in objectives or []]
        if pull is not None:
            given = _from_words(pull, known)
            if given.get("source") in ("default", "words"):
                given["source"] = "words"
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


def _change_block(draft: dict[str, Any], change: dict[str, Any]) -> str:
    """One block added, changed or taken out, as the words ask. Its id."""
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
        given = {k: v for k, v in setting.items() if v is not None and k != "cites"}
        if not given:
            block["settings"].pop(name, None)
            continue
        block["settings"][name] = {**given, "cites": ["these"]}
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
            raise ValueError(f"there is no {ref} - rules are c1 onwards, as the study card shows")
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
    said = {"source": "words", "cites": list(setting.get("cites") or ["these"])}
    if isinstance(value, str):
        return {"options": [value], "suggested": value, **said}
    number = float(value)
    return {"low": number, "high": number, "step": 1.0, "suggested": number, **said}


def _provisional(setting: dict[str, Any]) -> dict[str, Any]:
    """A range or choices the words gave, as the part's reading first sees it."""
    if setting.get("options") is not None:
        return {"options": list(setting["options"]), "source": "words", "cites": ["these"]}
    return {
        "low": setting.get("low"),
        "high": setting.get("high"),
        "step": setting.get("step") or 1.0,
        "source": "words",
        "cites": ["these"],
    }


def _domain(setting: dict[str, Any], read: dict[str, Any]) -> dict[str, Any]:
    """A setting as the words gave it, over what the part read for it: a value fixed, the choices
    left, or a range - keeping the part's suggestion and step where they still fit."""
    said = {"source": "words", "cites": list(setting.get("cites") or ["these"])}
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


def _as_setting(domain: studies.Domain) -> dict[str, Any]:
    """A setting kept in a study, as the draft holds what the words gave."""
    cites = list(domain.cites)
    if domain.fixed:
        value = domain.options[0] if domain.options is not None else domain.low
        return {"value": value, "cites": cites}
    if domain.options is not None:
        return {"options": list(domain.options), "cites": cites}
    return {"low": domain.low, "high": domain.high, "step": domain.step, "cites": cites}


def _from_words(item: dict[str, Any], known: set[str]) -> dict[str, Any]:
    """An entry the engineer's words asked for: from their words, and - when it is firm and cites
    no word the study holds - citing the words the draft rests on. A cite that is not the id of a
    word is dropped rather than refused: quoting is checked where the words come in."""
    out = {k: v for k, v in item.items() if v is not None and k != "id"}
    out["cites"] = [c for c in out.get("cites", []) if c in known]
    strength = out.get("strength", "hard")
    if strength == "hard" and out.get("source") in (None, "you"):
        out["source"] = "words"
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


def _placements(
    version: studies.StudyVersion, values: dict[str, dict[str, Any]] | None = None
) -> tuple[list[Placement], list[str]]:
    """Every block that can be built, at the values given for it - or at its suggested point - and
    why each other block cannot. Webs with nothing under them stand along the pull when it is a
    direction and what they join runs along it."""
    placements, cannot = [], []
    pull = version.pull.direction if version.pull is not None else None
    for block in version.blocks:
        if block.add not in studies.ADDS:
            cannot.append(f"{block.id}: nothing can add {block.add} yet")
            continue
        try:
            point = studies.point(version, block.id, (values or {}).get(block.id))
            if not block.where.support and pull:
                point["pull"] = list(pull)
            placements.append(Placement.model_validate(point))
        except (studies.StudyError, ValueError) as error:
            cannot.append(f"{block.id}: {error}")
    return placements, cannot


def _opened(
    session: Session,
    placements: list[Placement],
    version: Version,
    fidelity: str,
    radius: float | None = None,
):
    """The part opened at a fidelity, once per grid: the grid the placements' smallest root fillet
    asks for, or the one ``radius`` does - so many designs are placed on one."""
    radius = radius or min(p.section.root_fillet_mm for p in placements)
    key = (fidelity, radius)
    if key not in session.opened:
        session.opened[key] = Opened.open(
            session.project, session.extraction, version, fidelity, radius
        )
    return session.opened[key]


def paths(session: Session, draft: bool = True, values: dict | None = None) -> dict:
    """Where the draft's - or the study's - suggested design would put ribs, or the design at the
    values given: every line each block's layout tries, and what became of it, before anything is
    made. Only placing, nothing composed or checked: seconds once the part is open at the preview
    grid."""
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
    placements, cannot = _placements(version, values)
    if not placements:
        return {"cannot": "; ".join(cannot) or "nothing the study asks for can be placed yet"}
    placed = _place(session, version, placements)
    if "cannot" in placed:
        return placed
    lines = [line for result in placed.values() for line in result.tried]
    return {
        "lines": lines,
        "ribs": sum(len(result.ribs) for result in placed.values()),
        "paths": sum(result.paths for result in placed.values()),
        "summary": "; ".join(f"{bid}: {result.tally()}" for bid, result in placed.items()),
        "blocks": {bid: {"ribs": len(r.ribs), "says": r.tally()} for bid, r in placed.items()},
        "waiting": cannot,
    }


def _place(
    session: Session,
    version: studies.StudyVersion,
    placements: list[Placement],
    radius: float | None = None,
):
    """The placements placed on the part at the preview grid - that of ``radius``, when many
    designs share one - each block after those whose ribs it keeps clear of."""
    extraction = session.extraction
    point = Version(
        version=version.version,
        created="",
        words=[Words(id="card", text="not yet written")],
        placements=placements,
        rules=studies.rules_of(version),
    )
    try:
        opened = _opened(session, placements, point, "preview", radius)
    except IntentError as error:
        return {"cannot": str(error)}
    assert extraction.features is not None and extraction.atlas is not None
    return place_all(
        opened.base, extraction.features, extraction.atlas, extraction.tess, placements
    )


def design_from_study(
    session: Session, fidelity: str, values: dict[str, dict[str, Any]] | None = None
) -> dict:
    """A design from the active study's current version - every block at the values given for it,
    or at its suggested point - and its verdict, with what the study holds that nothing enforces
    yet and what nobody confirmed. Or why there is none."""
    study = studies.active(session.project)
    if study is None:
        return {"cannot": "there is no study yet"}
    version = study.current
    assert session.extraction.features is not None
    _, lost = studies.resolve(version, session.extraction.features)
    if lost:
        return {"cannot": "the part is not the one the study names: " + "; ".join(lost[:3])}
    placements, cannot = _placements(version, values)
    if not placements:
        return {"cannot": "; ".join(cannot) or "nothing the study asks for can be made yet"}
    point = Version(
        version=version.version,
        created=version.created,
        words=version.words,
        placements=placements,
        rules=studies.rules_of(version),
        measured=version.measured,
    )
    try:
        made = make(_opened(session, placements, point, fidelity), point, {})
    except IntentError as error:
        return {"cannot": str(error)}
    session.made = made
    session.changed.add("design")
    return {
        **verdict(made),
        "study": study.name,
        "study_version": version.version,
        "open": studies.open_items(version),
        "assumed": studies.assumed(version),
        "waiting": cannot,
    }


def go(session: Session, n: int = GO) -> Iterator[dict]:
    """Many designs at once: the draft accepted if it differs, then ``n`` points spread over what
    every block leaves free - the suggested point first - each placed, its ribs counted and what
    stopped the rest said, as each is done. Designs whose ribs all fall in the same places are
    made once. Nothing is composed or checked: that is for the one the engineer picks."""
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
    version = study.current
    buildable, cannot = _placements(version)
    if not buildable:
        yield {"type": "error", "message": "; ".join(cannot) or "nothing can be placed yet"}
        return
    ids = [p.id for p in buildable]
    spread = {bid: studies.sample(version, bid, n) for bid in ids}
    # Every design is placed on the grid the suggested one opens: placing needs no finer grid, and
    # a grid per root fillet sampled would build the part's field again and again.
    radius = min(p.section.root_fillet_mm for p in buildable)
    session.designs = []
    seen: set[tuple] = set()
    yield {"type": "started", "version": version.version, "n": n, "waiting": cannot}
    for index in range(n):
        values = {bid: spread[bid][index % len(spread[bid])] for bid in ids}
        placements, _ = _placements(version, values)
        placed = _place(session, version, placements, radius)
        if "cannot" in placed:
            yield {"type": "error", "message": placed["cannot"]}
            return
        ribs = [
            (round(r.start[0]), round(r.start[1]), round(r.end[0]), round(r.end[1]))
            for result in placed.values()
            for r in result.ribs
        ]
        key = tuple(sorted(ribs))
        if key in seen:
            continue
        seen.add(key)
        design = {
            "index": len(session.designs),
            "values": values,
            "ribs": sum(len(result.ribs) for result in placed.values()),
            "blocks": {bid: {"ribs": len(r.ribs), "says": r.tally()} for bid, r in placed.items()},
            "about": _about(version, values),
            "lines": [line for result in placed.values() for line in result.tried],
        }
        session.designs.append(design)
        yield {"type": "design", **{k: v for k, v in design.items() if k != "lines"}}
    session.changed.add("designs")
    yield {"type": "done", "made": len(session.designs)}


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


def design_paths(session: Session, index: int) -> dict:
    """The lines of one of the designs Go made, to draw on the part."""
    if not 0 <= index < len(session.designs):
        return {"cannot": f"there is no design {index}"}
    design = session.designs[index]
    return {
        "lines": design["lines"],
        "ribs": design["ribs"],
        "paths": len(design["lines"]),
        "summary": "; ".join(f"{b}: {r['says']}" for b, r in design["blocks"].items()),
    }


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

    return {
        "spec_version": made.version,
        "fidelity": made.fidelity,
        "outcome": design.outcome,
        "ribs": design.stats["ribs"],
        "added_cm3": round(design.stats["added_cm3"], 1),
        "seconds": design.stats["seconds"],
        "constraints": rows("constraint"),
        "checks": rows("check"),
    }
