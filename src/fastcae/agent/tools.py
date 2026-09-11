"""The agent's tools: questions about the part, the spec, and designs made from it.

Each tool calls the same engine functions the routes call; nothing here computes geometry of its
own, and nothing an agent does is out of reach of the interface. Results are compact JSON - enough
to reason from, never whole meshes.
"""

from __future__ import annotations

import json
from typing import Any, Literal

import numpy as np
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from .. import spec as specs
from ..features import Feature, FeatureKind, extent, neighbours
from ..generate.session import Session, design_from_spec, refill, write_from_card
from ..generate.slots import Given
from ..spec import Lever, Measured, Placement

LIMIT = 40

# What the tools work on: the open project's rib work, and the conversation.
Context = Session


class WriteSpec(BaseModel):
    """A new version of the spec."""

    name: str = Field(
        description="The spec's name, e.g. what the study is about. Keep it across versions."
    )
    quotes: list[str] = Field(
        description="The engineer's words this version adds, each copied exactly from what they "
        "typed. Words from earlier versions are kept and keep their ids (w1, w2, ...); new ones "
        "get the next ids in the order given."
    )
    placements: list[Placement] = Field(description="Every placement, in full.")
    rules: dict[str, Any] = Field(
        default_factory=dict,
        description="Check thresholds the engineer set or you proposed: fillet_floor_mm (the "
        "smallest radius allowed), thickness_mm [low, high], rib_to_wall, root_gap, thick_spot.",
    )
    levers: list[Lever] = Field(default_factory=list)
    measured: list[Measured] = Field(default_factory=list)
    note: str = Field(default="", description="One line: what this version changes and why.")
    selected: list[int] = Field(
        default_factory=list,
        description="Faces the engineer selected on the part that this version rests on, exactly "
        "as selected. Recorded as s1, s2, ... for placements to cite, like words.",
    )


class ProposalField(BaseModel):
    """One thing the placement needs, as the card shows it."""

    name: str = Field(description="What it is: host, supports, keep out, layout, thickness, ...")
    value: str = Field(description="Its value, short. Empty when it is needed from the engineer.")
    source: Literal["you", "measured", "default", "needed"] = Field(
        description="you: the engineer said or selected it. measured: from a tool. default: your "
        "choice, not confirmed. needed: only the engineer can say."
    )
    refs: list[str] = Field(
        default_factory=list,
        description="Feature or face ids this field is about, e.g. planar_group:114, face:1453.",
    )
    note: str = Field(default="", description="Why, in a few words. Optional.")


class Proposal(BaseModel):
    """What you have understood, as a card the engineer can check at a glance."""

    title: str = Field(description="A few words: what these ribs are.")
    fields: list[ProposalField]
    ask: str = Field(default="", description="The one question you most need answered, if any.")


def build(ctx: Context) -> list[BaseTool]:
    """The tools, bound to one open project and conversation."""
    features = ctx.extraction.features
    atlas = ctx.extraction.atlas
    tess = ctx.extraction.tess
    assert features is not None and atlas is not None and tess is not None

    def row(f: Feature) -> dict:
        out: dict[str, Any] = {"id": f.id, "kind": str(f.kind), "area_mm2": round(f.area_mm2)}
        out["centre"] = [round(v, 1) for v in f.centroid]
        if f.normal is not None:
            out["faces" if f.kind == FeatureKind.PLANAR_GROUP else "axis"] = [
                round(v, 3) for v in f.normal
            ]
        if f.diameter_mm is not None:
            out["diameter_mm"] = round(f.diameter_mm, 2)
        if f.kind in (FeatureKind.HOLE_PATTERN,):
            out["count"] = f.count
        if f.id in ctx.extraction.controlled:
            out["controlled_by_drawing"] = bool(ctx.extraction.controlled[f.id].value)
        return out

    def own_direction(f: Feature) -> tuple[float, float, float] | None:
        if f.normal is not None:
            return f.normal
        if f.axis_id and f.axis_id in features.axes:
            return features.axes[f.axis_id].direction
        return None

    @tool
    def find_features(
        kind: str | None = None,
        touching: str | None = None,
        facing: list[float] | None = None,
        limit: int = 30,
    ) -> str:
        """List detected features, largest first. Feature ids look like planar_group:114, hole:3,
        bore:196; any single CAD face can also be named as face:1453, wherever a feature id goes.

        kind: one of hole, bore, boss, planar_group, fillet, hole_pattern.
        touching: only features that share an edge with this feature id.
        facing: only planar groups facing within 25 degrees of this direction [x, y, z].
        """
        chosen = list(features.features.values())
        if kind:
            chosen = [f for f in chosen if str(f.kind) == kind]
        if touching:
            if features.get(touching) is None:
                return json.dumps({"error": _unknown(touching)})
            near = set(neighbours(features, atlas, touching))
            chosen = [f for f in chosen if f.id in near]
        if facing:
            d = np.asarray(facing, dtype=float)
            d = d / max(float(np.linalg.norm(d)), 1e-12)
            chosen = [
                f
                for f in chosen
                if f.kind == FeatureKind.PLANAR_GROUP
                and f.normal is not None
                and float(np.dot(f.normal, d)) > np.cos(np.radians(25.0))
            ]
        chosen.sort(key=lambda f: -f.area_mm2)
        limit = max(1, min(int(limit), LIMIT))
        return json.dumps({"total": len(chosen), "features": [row(f) for f in chosen[:limit]]})

    @tool
    def describe(feature_ids: list[str]) -> str:
        """Everything known about some features or faces (planar_group:114, face:1453): size,
        position, which way they face, how far they reach along their own direction, what they
        touch, and for a flat one the holes that pierce it."""
        out = []
        for ref in feature_ids[:LIMIT]:
            f = features.get(ref)
            if f is None:
                out.append({"id": ref, "error": _unknown(ref)})
                continue
            item = row(f)
            direction = own_direction(f)
            if direction is not None:
                low, high = extent(tess, f.face_ids, direction)
                item["reach_along_own_direction_mm"] = [round(low, 2), round(high, 2)]
            item["touches"] = [
                f"{n} ({features.features[n].kind})" for n in neighbours(features, atlas, ref)
            ][:LIMIT]
            if f.kind == FeatureKind.PLANAR_GROUP or f.metrics.get("flat") == 1.0:
                mine = set(f.face_ids)
                holes = [h for h in features.of_kind(FeatureKind.HOLE) if mine & set(h.opens_onto)]
                item["holes_through_it"] = [
                    {"id": h.id, "diameter_mm": round(h.diameter_mm or 0.0, 2)} for h in holes
                ][:LIMIT]
                item["hole_count"] = len(holes)
            item["face_ids"] = list(f.face_ids)[:LIMIT]
            out.append(item)
        return json.dumps(out)

    @tool
    def measure_extent(feature_id: str, direction: list[float]) -> str:
        """How far a feature reaches along a direction [x, y, z]: its lowest and highest point,
        projected onto that direction, in mm."""
        f = features.get(feature_id)
        if f is None:
            return json.dumps({"error": _unknown(feature_id)})
        low, high = extent(tess, f.face_ids, tuple(direction))
        return json.dumps(
            {
                "feature": feature_id,
                "direction": direction,
                "low_mm": round(low, 3),
                "high_mm": round(high, 3),
            }
        )

    @tool
    def faces(face_ids: list[int]) -> str:
        """What some CAD faces are: surface type, area, where, and which features they belong to."""
        out = []
        for face_id in face_ids[:LIMIT]:
            face = atlas.faces.get(int(face_id))
            if face is None:
                out.append({"face": face_id, "error": "no such face"})
                continue
            out.append(
                {
                    "face": face_id,
                    "type": face.surface_type,
                    "area_mm2": round(face.area),
                    "centre": [round(v, 1) for v in face.centroid],
                    "normal": None if face.normal is None else [round(v, 3) for v in face.normal],
                    "in": [f.id for f in features.containing(int(face_id))],
                }
            )
        return json.dumps(out)

    @tool(args_schema=Given)
    def fill_slots(**values: Any) -> str:
        """Fill every slot a group of ribs needs and show the engineer the card. Pass only what the
        engineer has just said, as values - it is added to what they said before. The faces they
        selected are already known here. Everything else is filled from the part, the drawing, or a
        labelled default; what nothing settles comes back as needed."""
        said_now = Given.model_validate(values)
        merged = ctx.card.given.model_dump()
        for key, value in said_now.model_dump().items():
            if value not in (None, [], ""):
                merged[key] = value
        ctx.card.given = Given.model_validate(merged)
        return json.dumps(refill(ctx))

    @tool
    def write_spec_from_slots(name: str, quotes: list[str]) -> str:
        """Write the spec from the filled slots - once the engineer has confirmed the card and
        nothing is needed - and make a preview design from it. ``quotes`` are the engineer's words
        this rests on, copied exactly."""
        if ctx.slots is None:
            return json.dumps({"cannot": "fill the slots first"})
        reply = write_from_card(ctx, name, quotes)
        if "version" in reply:
            reply["design"] = design_from_spec(ctx, "preview", {})
        return json.dumps(reply)

    @tool
    def look_at_faces(face_ids: list[int]) -> str:
        """What some faces are and how they relate: each face's type, size, position, which way it
        faces or the axis it turns about, what features it is in; and for each pair, whether they
        touch, the angle between them, whether they face each other and across what gap, and
        whether they turn about the same axis. For working out what selected faces are for."""
        chosen = [atlas.faces.get(int(f)) for f in face_ids[:LIMIT]]
        missing = [f for f, face in zip(face_ids, chosen, strict=False) if face is None]
        faces_out = []
        for face in (f for f in chosen if f is not None):
            item: dict[str, Any] = {
                "face": f"face:{face.face_id}",
                "type": face.surface_type,
                "area_mm2": round(face.area),
                "centre": [round(v, 1) for v in face.centroid],
                "in": [f.id for f in features.containing(face.face_id)],
            }
            if face.surface_type == "plane" and face.normal is not None:
                item["faces"] = [round(v, 3) for v in face.normal]
            elif face.axis is not None:
                item["axis"] = [round(v, 3) for v in face.axis]
                if face.radius_mm is not None:
                    item["radius_mm"] = round(face.radius_mm, 2)
                if face.concave is not None:
                    item["material"] = "outside (a bore)" if face.concave else "inside (a boss)"
            faces_out.append(item)
        pairs = []
        real = [f for f in chosen if f is not None]
        for i, a in enumerate(real):
            for b in real[i + 1 :]:
                pairs.append(_relation(a, b, features.diagonal_mm))
        return json.dumps({"faces": faces_out, "pairs": pairs, "not_on_the_part": missing})

    @tool
    def around(face_id: int) -> str:
        """The faces around one face: those sharing an edge with it, and past any fillet the faces
        beyond, each with the angle it makes and the features it is in. From a floor this finds
        the walls, bores and bosses rising from it."""
        face = atlas.faces.get(int(face_id))
        if face is None:
            return json.dumps({"error": _unknown(f"face:{face_id}")})
        rows, seen = [], {face.face_id}
        for n in face.neighbours:
            if n in seen:
                continue
            seen.add(n)
            other = atlas.faces[n]
            rows.append(_ring_row(face, other, features, via=None))
            if other.surface_type in ("torus", "sphere", "bspline"):
                for m in other.neighbours:
                    if m in seen:
                        continue
                    seen.add(m)
                    rows.append(_ring_row(face, atlas.faces[m], features, via=n))
        return json.dumps({"face": f"face:{face.face_id}", "around": rows[: LIMIT * 2]})

    @tool(args_schema=Proposal)
    def show_proposal(title: str, fields: list[ProposalField], ask: str = "") -> str:
        """Show the engineer what you have understood as a card - every field of the placement
        with its value and where it came from - instead of explaining it in prose. The card lets
        them check it at a glance and pick out the faces it names."""
        unknown = sorted({r for f in fields for r in (_field_refs(f)) if features.get(r) is None})
        if unknown:
            return json.dumps({"refused": _unknown(", ".join(unknown))})
        return json.dumps(
            {"shown": True, "needed": [f.name for f in fields if _source(f) == "needed"]}
        )

    @tool
    def search_drawing(text: str) -> str:
        """Lines of the drawing's text containing this (case-insensitive), with their pages - notes,
        title block and dimensions alike. Try the drawing's own wording: RADII, not radius."""
        drawing = ctx.extraction.drawing
        if drawing is None:
            return json.dumps({"error": "this project has no drawing"})
        hits = [{"page": page, "text": line} for page, line in drawing.search(text)]
        return json.dumps({"total": len(hits), "lines": hits[:LIMIT]})

    @tool
    def read_spec() -> str:
        """The active spec's current version, in full, and how many versions it has."""
        spec = specs.active(ctx.project)
        if spec is None:
            return json.dumps({"spec": None})
        return json.dumps(
            {
                "name": spec.name,
                "versions": len(spec.versions),
                "current": spec.current.model_dump(),
            }
        )

    @tool(args_schema=WriteSpec)
    def write_spec(
        name: str,
        quotes: list[str],
        placements: list[Placement],
        rules: dict[str, Any] | None = None,
        levers: list[Lever] | None = None,
        measured: list[Measured] | None = None,
        note: str = "",
        selected: list[int] | None = None,
    ) -> str:
        """Write a new version of the spec and make it active. Refused, with the reason, if a quote
        is not the engineer's exact words, a feature does not exist, or something cites nothing."""
        try:
            version = specs.write(
                ctx.project,
                name,
                quotes=quotes,
                said=ctx.said,
                selected=selected,
                selections=ctx.selections,
                placements=[_plain(p) for p in placements],
                features=features,
                rules=rules,
                levers=[_plain(v) for v in levers or []],
                measured=[_plain(m) for m in measured or []],
                note=note,
            )
        except specs.SpecError as error:
            return json.dumps({"refused": str(error)})
        ctx.changed.add("spec")
        return json.dumps(
            {
                "version": version.version,
                "words": [w.model_dump() for w in version.words],
                "changes": version.changes[:LIMIT],
            }
        )

    @tool
    def make_design(
        fidelity: Literal["preview", "full"] = "preview",
        levers: dict[str, float] | None = None,
    ) -> str:
        """Make a design from the active spec's current version, with lever values if given, and
        return its verdict: the engineer's constraints, then the checks. Preview is the same design
        on a coarser grid, for iterating; full is what a design is accepted at."""
        return json.dumps(design_from_spec(ctx, fidelity, levers or {}))

    return [
        fill_slots,
        write_spec_from_slots,
        find_features,
        describe,
        measure_extent,
        faces,
        look_at_faces,
        around,
        search_drawing,
        read_spec,
        write_spec,
        make_design,
    ]


def _relation(a, b, diagonal: float) -> dict:
    """How two faces stand to each other."""
    out: dict[str, Any] = {
        "faces": [f"face:{a.face_id}", f"face:{b.face_id}"],
        "touch": bool(b.face_id in a.neighbours),
    }
    na = np.asarray(a.normal) if a.surface_type == "plane" and a.normal is not None else None
    nb = np.asarray(b.normal) if b.surface_type == "plane" and b.normal is not None else None
    if na is not None and nb is not None:
        cosine = float(np.clip(na @ nb, -1.0, 1.0))
        out["angle_deg"] = round(float(np.degrees(np.arccos(cosine))), 1)
        if cosine < -0.95:
            out["facing_each_other_gap_mm"] = round(
                abs(float((np.asarray(b.centroid) - np.asarray(a.centroid)) @ na)), 1
            )
    if a.axis is not None and b.axis is not None and a.axis_point and b.axis_point:
        da, db = np.asarray(a.axis, dtype=float), np.asarray(b.axis, dtype=float)
        parallel = bool(abs(float(da @ db)) > float(np.cos(np.radians(1.0))))
        if parallel:
            offset = np.asarray(b.axis_point, dtype=float) - np.asarray(a.axis_point, dtype=float)
            off_axis = float(np.linalg.norm(offset - (offset @ da) * da))
            out["same_axis"] = bool(off_axis <= max(diagonal * 1e-3, 1e-3))
            if out["same_axis"] and a.radius_mm is not None and b.radius_mm is not None:
                out["radial_gap_mm"] = round(abs(a.radius_mm - b.radius_mm), 1)
    for flat, round_ in ((na, b), (nb, a)):
        if flat is not None and round_.axis is not None:
            along = abs(float(flat @ np.asarray(round_.axis, dtype=float)))
            out["axis_square_to_the_flat_face"] = bool(along > float(np.cos(np.radians(5.0))))
    return out


def _ring_row(face, other, features, via: int | None) -> dict:
    row: dict[str, Any] = {
        "face": f"face:{other.face_id}",
        "type": other.surface_type,
        "angle_deg": round(float(face.dihedral.get(other.face_id, float("nan"))), 1)
        if via is None
        else None,
        "in": [f.id for f in features.containing(other.face_id)],
    }
    if via is not None:
        row["past_fillet"] = f"face:{via}"
    if other.surface_type == "plane" and other.normal is not None:
        row["faces"] = [round(v, 3) for v in other.normal]
    elif other.axis is not None:
        row["axis"] = [round(v, 3) for v in other.axis]
        if other.radius_mm is not None:
            row["radius_mm"] = round(other.radius_mm, 2)
    return row


def _field_refs(field_: Any) -> list[str]:
    return list(field_.refs if isinstance(field_, BaseModel) else field_.get("refs", []))


def _source(field_: Any) -> str:
    return field_.source if isinstance(field_, BaseModel) else field_.get("source", "")


def _unknown(ref: str) -> str:
    return (
        f"no feature or face {ref!r} - ids look like planar_group:114, hole:3, bore:196, "
        "or face:1453 for a single face"
    )


def _plain(value: Any) -> Any:
    return value.model_dump() if isinstance(value, BaseModel) else value
