"""The design-space stage as typed entities: what the derivation found, tied back to what it read.

An interface links to the deck groups, drawing controls and features that are its evidence; a
keep-out to the interfaces it was swept from; a question to what it asks about. Volumes show on the
CAD's design-space view as layers of cells, per-face values as paint.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..space.derive import GROUP_WORDS, STEPS
from ..space.model import EVIDENCE_WORDS, Evidence, Space
from .entities import (
    Band,
    Benefit,
    Canvas,
    Continuation,
    Entity,
    FaceMap,
    Grid,
    Group,
    Inside,
    Interface,
    KeepOut,
    Link,
    Mirror,
    Opening,
    Origin,
    Proof,
    Question,
    Region,
    Show,
    StepRun,
)

Only = dict[str, set[str]]

THICKNESS: Only = {"what": {"thickness"}}

INPUTS: dict[str, list[tuple[str, str, str, str, Only | None]]] = {
    # step: (key, few words, producing step, kind, only those whose fields hold these values)
    "grid": [("part", "the part", "cad.load", "part", None)],
    "thickness": [("faces", "faces", "cad.atlas", "face", None)],
    "interfaces": [
        ("anchors", "deck groups on CAD faces", "deck.anchor", "anchor", None),
        ("couplings", "couplings", "deck.read", "coupling", None),
        ("loads", "loads", "deck.read", "load", None),
        ("supports", "supports", "deck.read", "support", None),
        ("controls", "drawing controls", "crosscheck", "control", None),
        ("features", "features", "cad.features", "feature", None),
        ("thickness", "wall thickness", "thickness", "face_map", THICKNESS),
    ],
    "sweeps": [
        ("interfaces", "interfaces", "interfaces", "interface", None),
        ("holes", "holes", "cad.features", "feature", {"feature_kind": {"hole"}}),
    ],
    "inside": [("keep_outs", "what sits round them", "sweeps", "keep_out", None)],
    "beyond": [
        ("bores", "bores", "interfaces", "interface", {"interface_kind": {"bore"}}),
        ("inside", "the inside", "inside", "inside", None),
    ],
    "sealing": [
        ("inside", "the inside", "inside", "inside", None),
        ("thickness", "wall thickness", "thickness", "face_map", THICKNESS),
    ],
    "band": [
        ("thickness", "wall thickness", "thickness", "face_map", THICKNESS),
        ("inside", "the inside", "inside", "inside", None),
    ],
    "labels": [
        ("band", "where metal could go", "band", "band", None),
        ("keep_outs", "what sits round them", "sweeps", "keep_out", None),
        ("beyond", "beyond the bores", "beyond", "continuation", None),
        ("inside", "the inside", "inside", "inside", None),
    ],
    "columns": [
        ("allowed", "allowed space", "labels", "region", {"region_kind": {"allowed"}}),
        ("frozen", "frozen interfaces", "interfaces", "interface", {"state": {"frozen"}}),
    ],
    "checks": [
        ("asked", "interfaces in doubt", "interfaces", "interface", {"state": {"asked"}}),
        ("inside", "the inside", "inside", "inside", None),
        ("part", "the part", "cad.load", "part", None),
    ],
    "physics": [
        ("allowed", "allowed space", "labels", "region", {"region_kind": {"allowed"}}),
        ("anchors", "deck groups on CAD faces", "deck.anchor", "anchor", None),
        ("loads", "loads", "deck.read", "load", None),
        ("supports", "supports", "deck.read", "support", None),
        ("couplings", "couplings", "deck.read", "coupling", None),
        ("materials", "material", "deck.read", "material", None),
    ],
}


def _inputs(step: str, pool: dict[str, list[Entity]]) -> list[Group]:
    """What a step read, counted from the entities there are: all of a kind - found by kind and
    producing step - or, where only some are read, those some by id."""
    out = []
    for key, words, source, kind, only in INPUTS.get(step, []):
        members = pool.get(kind, [])
        if only:
            members = [
                e
                for e in members
                if all(str(getattr(e, f, None)) in allowed for f, allowed in only.items())
            ]
        ids = [e.id for e in members] if only else []
        out.append(Group(key=key, label=words, count=len(members), kind=kind, step=source, ids=ids))
    return out


KIND_WORDS = {
    "plane": "Flat face",
    "bore": "Bore",
    "boss": "Boss",
    "hole": "Hole",
    "surface": "Face",
}

SOURCE_OF = {
    "deck_load": "deck",
    "deck_support": "deck",
    "deck_hole_plane": "deck",
    "drawing": "drawing",
    "confirmed": "engineer",
    "machined": "rule",
    "hole_pattern_plane": "rule",
    "bore_geometry": "rule",
}


def _layer_show(*layers: str, faces: list[int] | None = None) -> Show:
    return Show(canvas=Canvas.SPACE, layers=list(layers), faces=faces or [])


def _group_key(i) -> str:  # type: ignore[no-untyped-def]
    kinds = {e["kind"] for e in i.evidence}
    if not i.frozen:
        return "asked"
    return next(
        k
        for k in ("deck_load", "deck_support", "drawing", "deck_hole_plane", "confirmed")
        if k in kinds
    )


def space_entities(
    space: Space, answers: dict[str, str] | None = None
) -> tuple[dict[str, list[Group]], list[Entity]]:  # noqa: C901
    """Every entity the design space produced, and each step's outputs grouped as the rail lists
    them."""
    answers = answers or {}
    records = {s["id"]: s for s in space.steps}
    produced = {k: v.get("produced", {}) for k, v in records.items()}
    out: list[Entity] = []
    groups: dict[str, list[Group]] = defaultdict(list)

    def add(step: str, key: str, label: str, members: list[Entity], kind: str) -> None:
        out.extend(members)
        if members:
            groups[step].append(
                Group(
                    key=key, label=label, count=len(members), kind=kind, ids=[m.id for m in members]
                )
            )

    h = space.grid.spacing_mm
    add(
        "grid",
        "grid",
        "The grid",
        [
            Grid(
                id="grid",
                label=f"{h:g} mm cells",
                step="grid",
                origin=Origin.DERIVED,
                spacing_mm=h,
                cells=space.grid.n_cells,
                part_L=float(produced.get("grid", {}).get("part_L", 0.0)),
                show=_layer_show("part"),
            )
        ],
        "grid",
    )
    thickness = produced.get("thickness", {})
    add(
        "thickness",
        "map",
        "Wall thickness on every face",
        [
            FaceMap(
                id="map:thickness",
                label=f"typical wall {thickness.get('typical_mm', 0):.0f} mm",
                step="thickness",
                origin=Origin.DERIVED,
                what="thickness",
                unit="mm",
                faces=len(space.faces.get("thickness", {})),
                summary=thickness,
                show=Show(canvas=Canvas.SPACE, paint="thickness"),
            )
        ],
        "face_map",
    )

    # Interfaces, each tied to its evidence.
    by_group: dict[str, list[Entity]] = defaultdict(list)
    interface_ids: dict[str, list[str]] = defaultdict(list)
    for i in space.interfaces:
        links = [Link(to=f"face:{f}", role="on") for f in i.faces]
        proofs = []
        for e in i.evidence:
            ref = e.get("ref")
            proofs.append(
                Proof(
                    source=SOURCE_OF.get(e["kind"], "rule"),
                    locator=ref or "",
                    detail=f"{EVIDENCE_WORDS[Evidence(e['kind'])]}: {e['detail']}",
                    confidence=e.get("confidence"),
                )
            )
            if ref and ref != "engineer":
                links.append(Link(to=ref, role="evidenced_by"))
                if ref.startswith("group:"):
                    links.append(Link(to="anchor:" + ref[len("group:") :], role="evidenced_by"))
        size = f"O{2 * i.radius_mm:.0f}" if i.radius_mm else f"{i.area_mm2 / 100:.0f} cm2"
        entity = Interface(
            id=f"interface:{i.id}",
            label=f"{KIND_WORDS.get(i.kind, 'Face')} {size}",
            step="interfaces",
            origin=Origin.CONFIRMED
            if any(e["kind"] == "confirmed" for e in i.evidence)
            else (Origin.DERIVED if i.frozen else Origin.INFERRED),
            status="ok" if i.frozen else "asked",
            interface_kind=i.kind,
            state="frozen" if i.frozen else "asked",
            faces=list(i.faces),
            radius_mm=i.radius_mm,
            area_mm2=round(i.area_mm2, 1),
            thickness_mm=i.thickness_mm,
            links=links,
            evidence=proofs,
            show=Show(canvas=Canvas.CAD, faces=list(i.faces)),
        )
        key = _group_key(i)
        by_group[key].append(entity)
        interface_ids[f"{'frozen' if i.frozen else 'asked'}:{i.kind}"].append(entity.id)
        interface_ids["frozen" if i.frozen else "asked"].append(entity.id)
    # Released by an answer: no interface now, kept in view so the answer can be taken back.
    for r in produced.get("interfaces", {}).get("released", []):
        by_group["released"].append(
            Interface(
                id=f"interface:{r['id']}",
                label=f"{KIND_WORDS.get(r['kind'], 'Face')} {r['size']}",
                step="interfaces",
                origin=Origin.CONFIRMED,
                interface_kind=r["kind"],
                state="released",
                faces=list(r["faces"]),
                links=[Link(to=f"face:{f}", role="on") for f in r["faces"]],
                evidence=[
                    Proof(source="engineer", locator="engineer", detail="you said nothing meets it")
                ],
                show=Show(canvas=Canvas.CAD, faces=list(r["faces"])),
            )
        )
    for key in (
        "deck_load",
        "deck_support",
        "deck_hole_plane",
        "drawing",
        "confirmed",
        "asked",
        "released",
    ):
        add("interfaces", key, GROUP_WORDS[key], by_group.get(key, []), "interface")
    add(
        "interfaces",
        "map",
        "Interfaces painted on the part",
        [
            FaceMap(
                id="map:interface",
                label="each face by what froze or asked about it",
                step="interfaces",
                origin=Origin.DERIVED,
                what="interface",
                faces=len(space.faces.get("interface", {})),
                show=Show(canvas=Canvas.SPACE, paint="interface"),
            )
        ],
        "face_map",
    )

    # What sits round them.
    swept_from = {
        "plug": interface_ids["frozen:bore"],
        "mating": interface_ids["frozen:plane"],
        "ring": interface_ids["frozen:boss"],
        "hole": interface_ids["frozen:hole"],
        "buffer": interface_ids["frozen"],
        "waiting": interface_ids["asked"],
    }
    keep_outs = []
    for layer in produced.get("sweeps", {}).get("layers", []):
        keep_outs.append(
            KeepOut(
                id=f"keep_out:{layer['key']}",
                label=f"{layer['label']}: {layer['L']:.0f} L",
                step="sweeps",
                origin=Origin.DERIVED,
                status="waiting" if layer["key"] == "waiting" else "ok",
                keep_out_kind=layer["key"],
                volume_L=float(layer["L"]),
                links=[Link(to=x, role="from") for x in swept_from.get(layer["key"], [])],
                show=_layer_show(layer["key"]),
            )
        )
    add("sweeps", "keep_outs", "Kept clear", keep_outs, "keep_out")

    # The inside.
    inside = produced.get("inside", {})
    if inside:
        add(
            "inside",
            "inside",
            "The inside",
            [
                Inside(
                    id="inside",
                    label={
                        "closed": f"closed, {inside.get('inside_L', 0):.0f} L",
                        "leaks": "leaks",
                        "none": "no inside",
                    }[inside.get("status", "none")],
                    step="inside",
                    origin=Origin.DERIVED,
                    state=inside.get("status", "none"),
                    volume_L=float(inside.get("inside_L", 0.0)),
                    probes=inside.get("probes", []),
                    show=_layer_show("cavity"),
                )
            ],
            "inside",
        )
        if inside.get("leak_L", 0) > 0:
            add(
                "inside",
                "openings",
                "Narrow openings",
                [
                    Opening(
                        id="opening",
                        label=f"{inside['leak_L']:.0f} L behind narrow openings",
                        step="inside",
                        origin=Origin.DERIVED,
                        status="asked",
                        volume_L=float(inside["leak_L"]),
                        show=_layer_show("leak"),
                    )
                ],
                "opening",
            )

    # Beyond each bore.
    continuations = []
    for b in produced.get("beyond", {}).get("bores", []):
        continuations.append(
            Continuation(
                id=f"continuation:{b['id']}",
                label=f"{b['size']}: " + "; ".join(b["ends"])
                if b["ends"]
                else f"{b['size']}: closed both ends",
                step="beyond",
                origin=Origin.DERIVED,
                ends=list(b["ends"]),
                links=[Link(to=f"interface:{b['id']}", role="from")],
                show=_layer_show("beyond", faces=b.get("faces", [])),
            )
        )
    add("beyond", "bores", "Bores", continuations, "continuation")

    # Sealing walls.
    add(
        "sealing",
        "map",
        "Faces that hold the inside",
        [
            FaceMap(
                id="map:sealing",
                label=f"{len(space.sealing_faces)} faces",
                step="sealing",
                origin=Origin.DERIVED,
                what="sealing",
                faces=len(space.sealing_faces),
                show=Show(canvas=Canvas.SPACE, paint="sealing", faces=list(space.sealing_faces)),
            )
        ],
        "face_map",
    )

    # Where metal could go.
    band = produced.get("band", {})
    bands = []
    for layer in band.get("layers", []):
        kind = "layer" if layer["key"] == "panel" else "pockets"
        bands.append(
            Band(
                id=f"band:{kind}",
                label=f"{layer['label']}: {layer['L']:.0f} L",
                step="band",
                origin=Origin.DERIVED,
                band_kind=kind,  # type: ignore[arg-type]
                volume_L=float(layer["L"]),
                detail={
                    k: band[k]
                    for k in ("wall_mm", "wall_range_mm", "ladder", "inside")
                    if k in band
                },
                show=_layer_show(layer["key"]),
            )
        )
    add("band", "band", "Candidate space", bands, "band")

    # Allowed and waiting.
    regions = []
    for layer in produced.get("labels", {}).get("layers", []):
        kind = "allowed" if layer["key"] == "allowed" else "waiting"
        regions.append(
            Region(
                id=f"region:{kind}",
                label=f"{layer['label']}: {layer['L']:.0f} L",
                step="labels",
                origin=Origin.DERIVED,
                status="waiting" if kind == "waiting" else "ok",
                region_kind=kind,  # type: ignore[arg-type]
                volume_L=float(layer["L"]),
                links=[Link(to="band:layer", role="from"), Link(to="band:pockets", role="from")]
                + [Link(to=k.id, role="minus") for k in keep_outs],
                show=_layer_show(layer["key"]),
            )
        )
    add("labels", "regions", "The design space", regions, "region")

    # Height straight out.
    columns = produced.get("columns", {})
    add(
        "columns",
        "map",
        "Height allowed straight out, on every face",
        [
            FaceMap(
                id="map:cap",
                label=f"median {columns.get('cap_mm', {}).get('50', 0):.0f} mm",
                step="columns",
                origin=Origin.DERIVED,
                what="cap",
                unit="mm",
                faces=len(space.faces.get("cap", {})),
                summary=columns,
                show=Show(canvas=Canvas.SPACE, paint="cap", layers=["allowed"]),
            )
        ],
        "face_map",
    )

    # Symmetry and questions.
    mirrors = [
        Mirror(
            id=f"mirror:{n}",
            label=f"mirror plane, {m['match_share']:.0%} match",
            step="checks",
            origin=Origin.INFERRED,
            normal=list(m["normal"]),
            through=list(m["through"]),
            match_share=float(m["match_share"]),
            show=Show(canvas=Canvas.CAD, point=tuple(m["through"])),
        )
        for n, m in enumerate(space.symmetry[:3])
    ]
    add("checks", "mirrors", "Mirror planes", mirrors, "mirror")
    questions_by: dict[str, list[Entity]] = defaultdict(list)
    for q in space.questions:
        qid = "question:" + q.id.removeprefix("q:")
        about = []
        if q.kind == "interface":
            about = [Link(to="interface:" + q.id.removeprefix("q:"), role="about")]
        elif q.kind == "cavity":
            about = [Link(to="inside", role="about")]
        elif q.kind == "symmetry":
            about = [Link(to="mirror:0", role="about")]
        answer = answers.get(qid)
        questions_by[q.kind].append(
            Question(
                id=qid,
                label=q.text,
                step="checks",
                origin=Origin.GENERATED,
                status="ok" if answer else "asked",
                question_kind=q.kind,
                text=q.text,
                detail=q.detail,
                options=list(q.options),
                meanwhile=q.meanwhile,
                answer=answer,
                links=about,
                show=Show(canvas=Canvas.CAD, faces=list(q.faces))
                if q.faces
                else _layer_show("cavity", "leak")
                if q.kind in ("cavity", "inside")
                else Show(canvas=Canvas.SPACE),
            )
        )
    words = {
        "interface": "About faces",
        "cavity": "About the inside",
        "inside": "About inner walls",
        "symmetry": "About symmetry",
        "resolution": "About the grid",
        "access": "About hole access",
    }
    for kind in ("interface", "cavity", "inside", "symmetry", "access", "resolution"):
        add("checks", f"questions:{kind}", words[kind], questions_by.get(kind, []), "question")

    # Where metal helps.
    physics = records.get("physics", {})
    if space.benefit is not None:
        add(
            "physics",
            "benefit",
            "Where metal helps",
            [
                Benefit(
                    id="benefit",
                    label=physics.get("detail", "benefit of metal"),
                    step="physics",
                    origin=Origin.DERIVED,
                    stats=produced.get("physics", {}),
                    links=[Link(to="region:allowed", role="on")],
                    show=_layer_show("benefit"),
                )
            ],
            "benefit",
        )
    return groups, out


def space_stage(
    space: Space | None,
    read: list[Entity],
    answers: dict[str, str] | None = None,
    live: dict[str, dict[str, Any]] | None = None,
    running: bool = False,
) -> tuple[list[StepRun], list[Entity]]:
    """The design-space steps - done, read back, running or still to run - and their entities.

    ``read`` is what the Read stage made, for the steps' inputs; ``live`` holds the records a run
    in progress has reported so far. While one is ``running`` the last space is on its way out:
    its steps and entities are not shown, only what the run has reported."""
    shown = None if running else space
    groups, entities = space_entities(shown, answers) if shown is not None else ({}, [])
    records = {s["id"]: s for s in shown.steps} if shown is not None else {}
    for sid, record in (live or {}).items():
        records[sid] = record
    pool: dict[str, list[Entity]] = defaultdict(list)
    for e in read + entities:
        pool[e.kind].append(e)
    steps = []
    for sid, label in STEPS:
        record = records.get(sid, {})
        inputs = _inputs(sid, pool)
        steps.append(
            StepRun(
                id=sid,
                stage="space",
                label=label,
                status=record.get("status", "pending"),
                seconds=record.get("seconds"),
                detail=record.get("detail", ""),
                inputs=inputs,
                outputs=groups.get(sid, []),
            )
        )
    return steps, entities
