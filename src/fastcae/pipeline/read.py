"""The Read stage as typed entities: what extraction found in the engineer's files.

Every extraction step becomes a step of the pipeline, and everything it found becomes an entity -
a face of the CAD, a callout of the drawing, a group of the deck - with where it can be seen and
what it is tied to. Nothing is recomputed: this reads the extraction as it stands.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from typing import Any

from .entities import (
    Anchor,
    Artifact,
    Axis,
    Callout,
    Canvas,
    Conflict,
    Control,
    Coupling,
    DeckGroup,
    Entity,
    Face,
    Feature,
    Group,
    Health,
    Link,
    Load,
    Material,
    Origin,
    Part,
    Proof,
    ResultField,
    Show,
    Signal,
    StepRun,
    Support,
)

CANVAS_OF_ARTIFACT = {
    "cad": Canvas.CAD,
    "drawing": Canvas.DRAWING,
    "fem": Canvas.MESH,
    "results": Canvas.MESH,
}

INPUTS: dict[str, list[tuple[str, str, str]]] = {
    # step: (input key, few words, producing step)
    "cad.load": [("cad", "the CAD file", "discover")],
    "cad.health": [("part", "the part", "cad.load")],
    "cad.atlas": [("part", "the part", "cad.load")],
    "cad.features": [("faces", "faces", "cad.atlas")],
    "drawing.read": [("drawing", "the drawing", "discover")],
    "crosscheck": [
        ("callouts", "callouts", "drawing.read"),
        ("features", "features", "cad.features"),
    ],
    "deck.read": [("deck", "the deck's files", "discover")],
    "deck.results": [("results", "the deck's answer", "discover")],
    "deck.anchor": [("groups", "deck groups", "deck.read"), ("faces", "faces", "cad.atlas")],
}

FEATURE_WORDS = {
    "bore": "Bores",
    "boss": "Bosses",
    "hole": "Holes",
    "hole_pattern": "Hole patterns",
    "planar_group": "Flat groups",
    "fillet": "Fillets",
}

SURFACE_WORDS = {
    "plane": "Planes",
    "cylinder": "Cylinders",
    "cone": "Cones",
    "sphere": "Spheres",
    "torus": "Tori",
    "bspline": "Free-form",
    "bezier": "Free-form",
    "revolution": "Revolved",
    "extrusion": "Extruded",
    "offset": "Offset",
}


def _size(radius: float | None, area: float) -> str:
    return f"O{2 * radius:.0f}" if radius else f"{area / 100:.0f} cm2"


def _vec(v: Any) -> list[float] | None:
    return None if v is None else [round(float(x), 4) for x in v]


def _faces_of(step: str, ids: list[int]) -> Show:
    return Show(canvas=Canvas.CAD, faces=[int(f) for f in ids])


def read_stage(extraction) -> tuple[list[StepRun], list[Entity]]:  # type: ignore[no-untyped-def]  # noqa: C901
    out: list[Entity] = []
    groups: dict[str, list[Group]] = defaultdict(list)

    def add_group(step: str, key: str, label: str, members: list[Entity], kind: str = "") -> None:
        if members:
            groups[step].append(
                Group(
                    key=key, label=label, count=len(members), kind=kind, ids=[m.id for m in members]
                )
            )

    # Artifacts.
    artifacts = []
    for a in extraction.artifacts:
        kind = str(a.kind)
        artifacts.append(
            Artifact(
                id=f"artifact:{a.name}",
                label=a.name,
                step="discover",
                origin=Origin.IMPORTED,
                file=a.name,
                artifact_kind=a.label,
                size_bytes=int(a.size_bytes or 0),
                show=Show(canvas=CANVAS_OF_ARTIFACT.get(kind, Canvas.NONE)),
            )
        )
    out += artifacts
    add_group("discover", "artifacts", "Files", artifacts, "artifact")

    # The part.
    if extraction.exact is not None:
        e = extraction.exact
        part = Part(
            id="part",
            label=f"{e.n_solids} solid, {e.n_faces} faces",
            step="cad.load",
            origin=Origin.IMPORTED,
            solids=e.n_solids,
            faces=e.n_faces,
            volume_cm3=round(e.volume_cm3, 1),
            area_m2=round(e.area_mm2 / 1e6, 4),
            bbox_mm=[round(v, 1) for v in e.bbox_mm],
            show=Show(canvas=Canvas.CAD),
        )
        out.append(part)
        add_group("cad.load", "part", "The part", [part], "part")
    if extraction.health is not None:
        hr = extraction.health
        health = Health(
            id="health",
            label="watertight" if hr.watertight else "not watertight",
            step="cad.health",
            origin=Origin.DERIVED,
            status="ok" if hr.watertight else "failed",
            watertight=hr.watertight,
            triangles=extraction.tess.n_triangles if extraction.tess else 0,
            boundary_edges=hr.boundary_edges,
            non_manifold_edges=hr.non_manifold_edges,
            volume_error_pct=round(hr.volume_error * 100, 4),
            show=Show(canvas=Canvas.CAD),
        )
        out.append(health)
        add_group("cad.health", "health", "Health", [health], "health")

    # Faces.
    if extraction.atlas is not None:
        by_type: dict[str, list[Entity]] = defaultdict(list)
        for f in extraction.atlas.faces.values():
            face = Face(
                id=f"face:{f.face_id}",
                label=f"{f.surface_type} {_size(f.radius_mm, f.area)}",
                step="cad.atlas",
                origin=Origin.IMPORTED,
                surface=f.surface_type,
                area_mm2=round(f.area, 1),
                centroid=_vec(f.centroid) or [],
                normal=_vec(f.normal),
                axis=_vec(f.axis),
                radius_mm=f.radius_mm,
                concave=f.concave,
                exterior=f.exterior,
                neighbours=len(f.neighbours),
                show=_faces_of("cad.atlas", [f.face_id]),
            )
            by_type[f.surface_type].append(face)
            out.append(face)
        for surface, members in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
            add_group(
                "cad.atlas",
                surface,
                SURFACE_WORDS.get(surface, f"{surface} faces"),
                members,
                "face",
            )

    # Features and axes.
    if extraction.features is not None:
        fs = extraction.features
        by_kind: dict[str, list[Entity]] = defaultdict(list)
        for feature in fs.features.values():
            kind = str(feature.kind)
            size = (
                f"O{feature.diameter_mm:.0f}"
                if feature.diameter_mm
                else f"{feature.area_mm2 / 100:.0f} cm2"
            )
            count = feature.count
            entity = Feature(
                id=feature.id,
                label=f"{kind.replace('_', ' ')} {size}"
                + (f" x{count}" if count > 1 and kind == "hole_pattern" else ""),
                step="cad.features",
                origin=Origin.DERIVED,
                feature_kind=kind,
                faces=list(feature.face_ids),
                diameter_mm=feature.diameter_mm,
                count=count,
                area_mm2=round(feature.area_mm2, 1),
                links=[Link(to=f"face:{f}", role="on") for f in feature.face_ids]
                + ([Link(to=f"axis:{feature.axis_id}", role="about")] if feature.axis_id else []),
                show=_faces_of("cad.features", list(feature.face_ids)),
            )
            by_kind[kind].append(entity)
            out.append(entity)
        for kind in ("bore", "boss", "hole", "hole_pattern", "planar_group", "fillet"):
            add_group(
                "cad.features",
                kind,
                FEATURE_WORDS.get(kind, kind),
                by_kind.get(kind, []),
                "feature",
            )
        axes = []
        for axis in fs.significant_axes():
            axes.append(
                Axis(
                    id=f"axis:{axis.id}",
                    label=f"axis {axis.id}, {len(axis.face_ids)} faces",
                    step="cad.features",
                    origin=Origin.DERIVED,
                    direction=_vec(axis.direction) or [],
                    point=_vec(axis.point) or [],
                    faces=len(axis.face_ids),
                    show=_faces_of("cad.features", list(axis.face_ids)),
                )
            )
        out += axes
        add_group("cad.features", "axes", "Axes that organise the part", axes, "axis")

    # The drawing.
    callout_by_text: dict[tuple[int, str], str] = {}
    if extraction.drawing is not None:
        by_kind = defaultdict(list)
        for index, c in enumerate(extraction.drawing.callouts):
            entity = Callout(
                id=f"callout:p{c.page}:{index}",
                label=c.raw,
                step="drawing.read",
                origin=Origin.IMPORTED,
                callout_kind=str(c.kind),
                page=c.page,
                text=c.raw,
                value=c.value,
                upper=c.upper,
                lower=c.lower,
                count=c.count,
                show=Show(canvas=Canvas.DRAWING, page=c.page, text=c.raw),
            )
            callout_by_text.setdefault((c.page, c.raw), entity.id)
            by_kind[str(c.kind)].append(entity)
            out.append(entity)
        for kind, members in sorted(by_kind.items(), key=lambda kv: -len(kv[1])):
            add_group("drawing.read", kind, kind.replace("_", " ").capitalize(), members, "callout")

    # Cross-check.
    controls = []
    for feature_id, fact in (extraction.controlled or {}).items():
        feature = extraction.features.features.get(feature_id) if extraction.features else None
        links = [Link(to=feature_id, role="of")]
        proofs = []
        for ev in fact.evidence:
            proofs.append(
                Proof(
                    source=str(ev.kind),
                    locator=ev.locator,
                    detail=ev.detail,
                    confidence=ev.confidence,
                )
            )
            found = _callout_of(ev.locator, callout_by_text)
            if found:
                links.append(Link(to=found, role="evidenced_by"))
        controls.append(
            Control(
                id=f"control:{feature_id}",
                label=f"{feature_id} controlled",
                step="crosscheck",
                origin=Origin.INFERRED,
                feature=feature_id,
                note=fact.note,
                trustworthy=bool(getattr(fact, "trustworthy", True)),
                links=links,
                evidence=proofs,
                show=_faces_of("crosscheck", list(feature.face_ids) if feature else []),
            )
        )
    out += controls
    add_group("crosscheck", "controls", "Controlled by the drawing", controls, "control")
    conflicts = []
    for n, c in enumerate(extraction.log.conflicts):
        match = re.match(r"^([a-z_]+:\d+)", c.subject)
        feature = (
            extraction.features.features.get(match.group(1))
            if match and extraction.features
            else None
        )
        conflicts.append(
            Conflict(
                id=f"conflict:{n}",
                label=c.subject,
                step="crosscheck",
                origin=Origin.DERIVED,
                status="conflict",
                subject=c.subject,
                left=str(c.left_value),
                right=str(c.right_value),
                tolerance=c.tolerance,
                links=[Link(to=match.group(1), role="about")] if match else [],
                show=_faces_of("crosscheck", list(feature.face_ids) if feature else []),
            )
        )
    out += conflicts
    add_group("crosscheck", "conflicts", "Unresolved", conflicts, "conflict")

    # The deck.
    deck = extraction.deck or {}
    deck_groups = []
    for g in deck.get("groups", []):
        roles = ", ".join(g.get("roles", [])) or "named"
        deck_groups.append(
            DeckGroup(
                id=f"group:{g['name']}",
                label=f"{g['name']}: {roles}",
                step="deck.read",
                origin=Origin.IMPORTED,
                name=g["name"],
                nodes=int(g.get("count", 0)),
                cells={k: int(v) for k, v in (g.get("cells") or {}).items()},
                show=Show(canvas=Canvas.MESH, group=g["name"]),
            )
        )
    out += deck_groups
    add_group("deck.read", "groups", "Groups", deck_groups, "deck_group")
    setup = deck.get("setup") or {}
    supports = []
    for n, h in enumerate(setup.get("held", [])):
        supports.append(
            Support(
                id=f"support:{n}",
                label=f"held: {len(h['groups'])} group{'s' if len(h['groups']) != 1 else ''}",
                step="deck.read",
                origin=Origin.IMPORTED,
                groups=list(h["groups"]),
                dofs={k: float(v) for k, v in h.get("dofs", {}).items()},
                links=[Link(to=f"group:{g}", role="holds") for g in h["groups"]],
                show=Show(canvas=Canvas.MESH, group=h["groups"][0] if h["groups"] else None),
            )
        )
    out += supports
    add_group("deck.read", "supports", "Supports", supports, "support")
    couplings = []
    for r in setup.get("rigid", []):
        surface = next((g for g in r["groups"] if g != r.get("reference")), r["groups"][0])
        couplings.append(
            Coupling(
                id=f"coupling:{surface}",
                label=f"rigid: {surface} to {r.get('reference')}",
                step="deck.read",
                origin=Origin.IMPORTED,
                coupling_kind="rigid",
                groups=list(r["groups"]),
                reference=r.get("reference"),
                links=[Link(to=f"group:{g}", role="ties") for g in r["groups"]],
                show=Show(canvas=Canvas.MESH, group=surface),
            )
        )
    for d in setup.get("distributing", []):
        couplings.append(
            Coupling(
                id=f"coupling:{d['group']}",
                label=f"distributing: {d['group']} to {d['reference']}",
                step="deck.read",
                origin=Origin.IMPORTED,
                coupling_kind="distributing",
                groups=[d["group"], d["reference"]],
                reference=d["reference"],
                links=[
                    Link(to=f"group:{d['group']}", role="ties"),
                    Link(to=f"group:{d['reference']}", role="ties"),
                ],
                show=Show(canvas=Canvas.MESH, group=d["group"]),
            )
        )
    out += couplings
    add_group("deck.read", "couplings", "Couplings", couplings, "coupling")
    loads = []
    for kind, key in (("nodal", "nodal_loads"), ("surface", "surface_loads")):
        for n, ld in enumerate(setup.get(key, [])):
            values = {k: float(v) for k, v in ld.get("values", {}).items()}
            words = ", ".join(f"{k} {v / 1000:+.0f} kN" for k, v in values.items() if abs(v) > 0)
            loads.append(
                Load(
                    id=f"load:{ld['group']}" if kind == "nodal" else f"load:{ld['group']}:{n}",
                    label=f"{ld['group']}: {words}" if words else ld["group"],
                    step="deck.read",
                    origin=Origin.IMPORTED,
                    load_kind=kind,  # type: ignore[arg-type]
                    group=ld["group"],
                    values=values,
                    links=[Link(to=f"group:{ld['group']}", role="on")],
                    show=Show(canvas=Canvas.MESH, group=ld["group"]),
                )
            )
    out += loads
    add_group("deck.read", "loads", "Loads", loads, "load")
    materials = [
        Material(
            id=f"material:{m['name']}",
            label=f"{m['name']}: E {m['young']:,.0f} MPa, nu {m['poisson']}",
            step="deck.read",
            origin=Origin.IMPORTED,
            name=m["name"],
            young=float(m["young"]),
            poisson=float(m["poisson"]),
            density=m.get("density"),
            show=Show(canvas=Canvas.MESH),
        )
        for m in setup.get("materials", [])
    ]
    out += materials
    add_group("deck.read", "materials", "Material", materials, "material")
    signals = [
        Signal(
            id=f"signal:{o['name']}",
            label=f"{o['name']}: {o.get('field', '')} on {o.get('group', '')}",
            step="deck.read",
            origin=Origin.IMPORTED,
            name=o["name"],
            group=o.get("group", ""),
            field=o.get("field", ""),
            components=list(o.get("components") or []),
            links=[Link(to=f"group:{o.get('group')}", role="reads")] if o.get("group") else [],
            show=Show(canvas=Canvas.MESH, group=o.get("group")),
        )
        for o in setup.get("outputs", [])
    ]
    out += signals
    add_group("deck.read", "signals", "Signals it asks for", signals, "signal")
    fields = [
        ResultField(
            id=f"result:{f['name']}",
            label=f"{f['name']} ({len(f.get('components', []))} components)",
            step="deck.results",
            origin=Origin.IMPORTED,
            name=f["name"],
            components=list(f.get("components", [])),
            show=Show(canvas=Canvas.MESH),
        )
        for f in deck.get("fields", [])
    ]
    out += fields
    add_group("deck.results", "fields", "Fields", fields, "result_field")

    # The deck tied to the CAD.
    anchors = []
    for g, a in ((extraction.anchoring or {}).get("groups") or {}).items():
        gap = a.get("gap")
        anchors.append(
            Anchor(
                id=f"anchor:{g}",
                label=f"{g} on {len(a['faces'])} face{'s' if len(a['faces']) != 1 else ''}",
                step="deck.anchor",
                origin=Origin.DERIVED,
                group=g,
                faces=[int(f) for f in a["faces"]],
                gap_mm=round(float(gap), 3) if gap is not None and gap == gap else None,
                links=[Link(to=f"group:{g}", role="of")]
                + [Link(to=f"face:{f}", role="on") for f in a["faces"]],
                show=_faces_of("deck.anchor", a["faces"]),
            )
        )
    out += anchors
    add_group("deck.anchor", "anchors", "Groups on CAD faces", anchors, "anchor")

    counts = {g.key: g for gs in groups.values() for g in gs}
    steps: list[StepRun] = []
    for s in extraction.steps:
        inputs = []
        for key, words, source in INPUTS.get(s.id, []):
            if key in ("cad", "drawing", "deck", "results"):
                kinds = {
                    "cad": "CAD",
                    "drawing": "Drawing",
                    "deck": "Solver deck",
                    "results": "Solver results",
                }
                members = [a for a in artifacts if a.artifact_kind == kinds[key]]
                inputs.append(
                    Group(
                        key=key,
                        label=words,
                        count=len(members),
                        kind="artifact",
                        ids=[m.id for m in members],
                        step=source,
                    )
                )
            elif key == "faces":
                total = sum(g.count for g in groups.get("cad.atlas", []))
                inputs.append(Group(key=key, label=words, count=total, kind="face", step=source))
            elif key == "features":
                total = sum(g.count for g in groups.get("cad.features", []) if g.kind == "feature")
                inputs.append(Group(key=key, label=words, count=total, kind="feature", step=source))
            elif key == "callouts":
                total = sum(g.count for g in groups.get("drawing.read", []))
                inputs.append(Group(key=key, label=words, count=total, kind="callout", step=source))
            elif key in counts:
                g = counts[key]
                inputs.append(Group(key=key, label=words, count=g.count, kind=g.kind, step=source))
        status = str(s.status)
        steps.append(
            StepRun(
                id=s.id,
                stage="read",
                label=s.label,
                status=status
                if status in ("pending", "running", "done", "skipped", "failed")
                else "done",  # type: ignore[arg-type]
                seconds=round(s.seconds, 2),
                detail=s.detail,
                inputs=inputs,
                outputs=groups.get(s.id, []),
                warnings=list(s.warnings)[:12],
            )
        )
    return steps, out


def _callout_of(locator: str, callouts: dict[tuple[int, str], str]) -> str | None:
    """The callout a drawing citation names: ``<file> page <n>: '<literal text>'``."""
    match = re.search(r"page (\d+): (.+)$", locator)
    if not match:
        return None
    try:
        text = ast.literal_eval(match.group(2))
    except (ValueError, SyntaxError):
        return None
    return callouts.get((int(match.group(1)), str(text)))
