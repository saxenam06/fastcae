"""The design space as the pipeline shows it: one step, the last of the Read stage, and one entity -
the volume where metal may be added, read from the project's folder or defined there by the rules
when the engineer brought none.
"""

from __future__ import annotations

import time
from collections import defaultdict

from ..space.model import KEPT_CLEAR, LABEL_WORDS, Label, Space
from ..space.store import FILES
from .entities import Canvas, DesignSpace, Entity, Group, Link, Origin, Proof, Show, StepRun

STEP = "space"
LABEL = "Design space"

INPUTS: list[tuple[str, str, str, str]] = [
    # (key, few words, producing step, kind)
    ("part", "the part", "cad.load", "part"),
    ("features", "features", "cad.features", "feature"),
    ("anchors", "deck groups on CAD faces", "deck.anchor", "anchor"),
    ("controls", "drawing controls", "crosscheck", "control"),
]

RULE_WORDS = "defined by fastcae's rules from the CAD, the deck and the drawing, in place of yours"


def entity(space: Space) -> DesignSpace:
    stats = space.stats
    by_rules = space.defined_by == "rules"
    litres = {LABEL_WORDS[label]: space.litres(label) for label in KEPT_CLEAR}
    volume = float(stats.get("design_L", space.litres(Label.DESIGN)))
    return DesignSpace(
        id="design_space",
        label=f"Design space, {volume:.0f} L",
        step=STEP,
        origin=Origin.DERIVED if by_rules else Origin.IMPORTED,
        volume_L=volume,
        outside_L=float(stats.get("outside_L", 0.0)),
        inside_L=float(stats.get("inside_L", 0.0)),
        spacing_mm=space.grid.spacing_mm,
        cells=int(space.grid.n_cells),
        defined_by="rules" if by_rules else "engineer",
        file=FILES[0],
        kept_clear={
            "litres": litres,
            "bores": stats.get("bores"),
            "held_faces": stats.get("held_faces"),
            "holes": stats.get("holes"),
        },
        rules={
            k: v
            for k, v in space.params.to_json().items()
            if k
            in (
                "spacing_mm",
                "panel_layer",
                "inside_layer",
                "pocket_reach",
                "buffer",
                "hole_access_radius",
                "hole_access_length",
            )
        },
        benefit=stats.get("benefit", {}),
        links=[Link(to="part", role="round")],
        evidence=[
            Proof(
                source="rule" if by_rules else "engineer",
                locator=FILES[0],
                detail=RULE_WORDS if by_rules else "brought by the engineer",
            )
        ],
        show=Show(canvas=Canvas.SPACE, layers=["design"]),
    )


def space_step(
    space: Space | None,
    read: list[Entity],
    cached: bool = False,
    running: bool = False,
    said: str = "",
    since: float | None = None,
) -> tuple[StepRun, list[Entity]]:
    """The design space's step - read back, defined, being defined or still to come - and its
    entity. While it is being defined, what the rules last said and how long they have taken."""
    pool: dict[str, list[Entity]] = defaultdict(list)
    for e in read:
        pool[e.kind].append(e)
    inputs = [
        Group(key=key, label=words, count=len(pool.get(kind, [])), kind=kind, step=source)
        for key, words, source, kind in INPUTS
    ]
    shown = None if running else space
    entities: list[Entity] = [entity(shown)] if shown is not None else []
    outputs = (
        [
            Group(
                key="design_space",
                label="The design space",
                count=1,
                kind="design_space",
                ids=["design_space"],
            )
        ]
        if entities
        else []
    )
    if running:
        status, seconds = "running", (time.time() - since if since else None)
        detail = said or ("defining it by the rules" if space is None else "reading it")
    elif shown is None:
        status, seconds, detail = "pending", None, ""
    else:
        stats = shown.stats
        where = (
            f"{stats.get('outside_L', 0):.0f} L outside, {stats.get('inside_L', 0):.0f} L inside"
        )
        status = "cached" if cached else "done"
        seconds = None if cached else round(shown.seconds, 1)
        detail = f"{stats.get('design_L', 0):.0f} L: {where}" + (
            "" if shown.defined_by != "rules" else " · defined by the rules"
        )
    return (
        StepRun(
            id=STEP,
            stage="read",
            label=LABEL,
            status=status,  # type: ignore[arg-type]
            seconds=seconds,
            detail=detail,
            inputs=inputs,
            outputs=outputs,
        ),
        entities,
    )
