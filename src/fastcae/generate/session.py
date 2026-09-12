"""The rib work on one open project: its card, the study written from it, designs made from that.

What the routes hold between requests - and what the agent's tools work on, when there is an agent;
nothing here needs one. A card is filled, written as a new version of the study when the engineer
asks for a design - its block of ribs, its rules, and the part's interfaces closed - and the design
is made from the study at its suggested point, never from the card: the study is the record of what
was asked for. Specs, the study's first form, are still read and written for the agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import spec as specs
from .. import study as studies
from ..extract import Extraction
from ..project import Project
from ..spec import Placement, Version, Words
from .intent import IntentError, Made, Opened, make
from .placement import _Faces, place
from .slots import Card, Slots

SPEC_NAME = "ribs"
STUDY_NAME = "ribs"


@dataclass
class Session:
    """What the rib work on one open project holds."""

    project: Project
    extraction: Extraction
    said: list[str] = field(default_factory=list)
    """Words the engineer wrote outside the card - to an agent - in order."""
    selections: list[list[int]] = field(default_factory=list)
    """Every set of faces the engineer had selected when they wrote, in order."""
    card: Card = field(default_factory=Card)
    """The rib card: what the engineer set, by value, selection or words."""
    slots: Slots | None = None
    measure: _Faces | None = None
    opened: dict[tuple[str, float], Opened] = field(default_factory=dict)
    made: Made | None = None
    changed: set[str] = field(default_factory=set)
    """What changed since the interface last asked - ``slots``, ``spec``, ``design``."""


def refill(session: Session) -> dict:
    """Fill every slot again from what the engineer has set and selected, and the card for it."""
    if session.measure is None:
        assert session.extraction.tess is not None
        session.measure = _Faces(session.extraction.tess)
    session.slots = session.card.fill(session.extraction, session.measure.exit_along)
    session.changed.add("slots")
    assert session.extraction.features is not None
    return {"card": session.card.view(session.slots, session.extraction.features)}


def write_from_card(session: Session, name: str = SPEC_NAME, quotes: list[str] | None = None):
    """A new version of the spec from the card as it stands: its placement, the engineer's lines
    from it and any other words quoted, the faces it rests on, and the values nobody set, marked
    so. ``{"version": n}``, or ``{"cannot": why}``."""
    if session.slots is None:
        refill(session)
    assert session.slots is not None
    try:
        placement = session.slots.placement(cites=["these"])
    except ValueError as error:
        return {"cannot": str(error)}
    try:
        version = specs.write(
            session.project,
            name,
            quotes=[*(quotes or []), *session.card.quotes()],
            said=[*session.said, *session.card.said],
            selected=session.card.selected() or None,
            selections=[*session.selections, *session.card.selections],
            placements=[placement],
            rules=session.slots.rules(),
            measured=session.slots.measured(),
            features=session.extraction.features,
        )
    except specs.SpecError as error:
        return {"cannot": str(error)}
    session.changed.add("spec")
    return {"version": version.version}


def write_study_from_card(
    session: Session, name: str = STUDY_NAME, quotes: list[str] | None = None
) -> dict:
    """A new version of the study from the card as it stands: its block of ribs - the card as the
    suggested point, ranges from the part round it - its rules, and the part's interfaces closed,
    resting on the engineer's lines from the card, any other words quoted and the faces they
    selected. ``{"version": n}``, or ``{"cannot": why}``. The card writes the whole study; it is
    the study's only writer until a model edits studies too."""
    if session.slots is None:
        refill(session)
    assert session.slots is not None
    try:
        entries = session.slots.study(cites=["these"])
    except ValueError as error:
        return {"cannot": str(error)}
    entries["constraints"] = [*entries["constraints"], *closed_interfaces(session.extraction)]
    try:
        version = studies.write(
            session.project,
            name,
            quotes=[*(quotes or []), *session.card.quotes()],
            said=[*session.said, *session.card.said],
            selected=session.card.selected() or None,
            selections=[*session.selections, *session.card.selections],
            features=session.extraction.features,
            **entries,
        )
    except studies.StudyError as error:
        return {"cannot": str(error)}
    session.changed.add("study")
    return {"version": version.version}


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


def design_from_study(
    session: Session, fidelity: str, values: dict[str, Any] | None = None
) -> dict:
    """A design from the active study's current version - every free setting at the value given,
    or at its suggested value - and its verdict, with what the study holds that nothing enforces
    yet and what nobody confirmed. Or why there is none."""
    study = studies.active(session.project)
    if study is None:
        return {"cannot": "there is no study yet"}
    version = study.current
    assert session.extraction.features is not None
    _, lost = studies.resolve(version, session.extraction.features)
    if lost:
        return {"cannot": "the part is not the one the study names: " + "; ".join(lost[:3])}
    try:
        placements = [
            Placement.model_validate(studies.point(version, block.id, values))
            for block in version.blocks
            if block.add in studies.ADDS
        ]
    except (studies.StudyError, ValueError) as error:
        return {"cannot": str(error)}
    if not placements:
        return {"cannot": "nothing the study asks for can be made yet"}
    point = Version(
        version=version.version,
        created=version.created,
        words=version.words,
        placements=placements,
        rules=studies.rules_of(version),
        measured=version.measured,
    )
    try:
        key = (fidelity, min(p.section.root_fillet_mm for p in placements))
        if key not in session.opened:
            session.opened[key] = Opened.open(session.project, session.extraction, point, fidelity)
        made = make(session.opened[key], point, {})
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
    }


def paths_for_card(session: Session) -> dict:
    """Where the card would put ribs, before anything is made: every line its layout tries, and
    what becomes of each - a rib, or why not. Only placing, nothing composed or checked, so it
    takes seconds once the part is open at the preview grid; nothing is written to the spec."""
    if session.slots is None:
        refill(session)
    assert session.slots is not None
    extraction = session.extraction
    try:
        placement = Placement.model_validate(session.slots.placement(cites=["card"]))
    except ValueError as error:
        return {"cannot": str(error)}
    version = Version(
        version=0,
        created="",
        words=[Words(id="card", text="the card, not yet written")],
        placements=[placement],
        rules=session.slots.rules(),
    )
    key = ("preview", placement.section.root_fillet_mm)
    try:
        if key not in session.opened:
            session.opened[key] = Opened.open(session.project, extraction, version, "preview")
    except IntentError as error:
        return {"cannot": str(error)}
    assert extraction.features is not None and extraction.atlas is not None
    placed = place(
        session.opened[key].base, extraction.features, extraction.atlas, extraction.tess, placement
    )
    return {
        "lines": placed.tried,
        "ribs": len(placed.ribs),
        "paths": placed.paths,
        "summary": placed.tally(),
    }


def design_from_spec(session: Session, fidelity: str, levers: dict[str, float]) -> dict:
    """A design from the active spec's current version, and its verdict - or why there is none."""
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
