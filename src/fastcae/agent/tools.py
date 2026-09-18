"""The agent's tools: a few general ones, each doing one job, for the agent to compose.

Over the pipeline - what fastcae read from the engineer's files and derived from them:

- **pipeline**: every step in order, whether it ran, what it said, what it made.
- **entities**: the typed entities a step made, of a kind, or holding some words.
- **entity**: one in full - its fields, the evidence behind it, what it is tied to both ways.
- **show** entities to the engineer, on the canvas each belongs to.
- **answer** one of the pipeline's questions, with the engineer's own words; **derive** the design
  space again to apply what was answered.

Over the part itself:

- **find** features by kind, by what they touch, which way they face, the axis they turn about.
- **describe** them, and - for several - how they stand to each other.
- **relate** them to the part: what they stand on, what rises round them, what lies across or
  between them.
- **measure** how far one reaches along a direction, or how thick the metal is under it.
- **search_drawing** for its words.

Each calls what the routes call; nothing here computes geometry of its own, and nothing an agent
does is out of reach of the interface. Results are compact JSON - enough to reason from, never
whole meshes. The agent records an answer only when the engineer's words give it, and never
changes what was read from the engineer's files.
"""

from __future__ import annotations

import json
import threading
from typing import Any, Literal

import numpy as np
from langchain_core.tools import BaseTool, tool

from ..features import Feature, FeatureKind, extent, neighbours
from ..generate import reading
from ..generate import session as sessions
from ..generate.session import Session

LIMIT = 40
# How many questions of the part, since the engineer last wrote, before every answer reminds the
# agent that the engineer can be asked instead.
QUESTIONS = 8
# How long a derivation may take before the agent is told it is still running.
DERIVE_WAIT_S = 600.0

# What the tools work on: the open project, and the conversation.
Context = Session


def build(ctx: Context) -> list[BaseTool]:
    """The tools, bound to one open project and conversation."""
    extraction = ctx.extraction
    features, atlas, tess = extraction.features, extraction.atlas, extraction.tess
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
        if f.axis_id:
            out["on_axis"] = f.axis_id
        if f.kind in (FeatureKind.HOLE_PATTERN,):
            out["count"] = f.count
        if f.id in extraction.controlled:
            out["controlled_by_drawing"] = bool(extraction.controlled[f.id].value)
        return out

    def answered(out: Any) -> str:
        """An answer - past a few since the engineer last wrote, with a reminder that the engineer
        can be asked instead."""
        ctx.questions += 1
        if ctx.questions > QUESTIONS:
            note = (
                f"{ctx.questions} questions since the engineer last wrote. Say what is clear, "
                "and ask the engineer the rest, naming the candidates by id."
            )
            out = {**out, "note": note} if isinstance(out, dict) else {"answer": out, "note": note}
        return json.dumps(out)

    # --- the pipeline -------------------------------------------------------------------------

    def graph():  # type: ignore[no-untyped-def]
        from ..api import pipeline as pipeline_api

        return pipeline_api.current_graph()

    @tool
    def pipeline() -> str:
        """The pipeline that read the engineer's files - drawing, CAD, solver deck - and derived the
        design space from them: every step in order, whether it ran, what it said, and what it made,
        each group of entities by label, kind and count. Start here."""
        from ..api import designspace

        steps = []
        for stage in graph().stages:
            for step in stage.steps:
                item: dict[str, Any] = {
                    "step": step.id,
                    "stage": stage.id,
                    "label": step.label,
                    "status": step.status,
                    "said": step.detail,
                    "made": [f"{g.count} {g.label} ({g.kind})" for g in step.outputs],
                }
                if step.warnings:
                    item["warnings"] = step.warnings[:3]
                steps.append(item)
        return answered({"steps": steps, "deriving": designspace.held.running})

    @tool
    def entities(
        kind: str | None = None, step: str | None = None, text: str | None = None, limit: int = 30
    ) -> str:
        """Entities the pipeline made, in a few words each: of one kind, made by one step, or whose
        label or id holds some words. Kinds: artifact, part, face, feature, axis, callout, control,
        conflict, deck_group, support, coupling, load, material, signal, result_field, anchor,
        grid, face_map, interface, keep_out, inside, opening, continuation, band, region,
        question, mirror, benefit."""
        found = graph().find(kind, step, None, text, limit=max(1, min(int(limit), LIMIT)))
        rows = [
            {k: e[k] for k in ("id", "kind", "label", "status", "origin")}
            for e in found["entities"]
        ]
        return answered({"total": found["total"], "found": rows})

    @tool
    def entity(id: str) -> str:
        """One entity in full: its typed fields, the evidence behind it and where that was found,
        what it is tied to and what is tied to it - each named in a few words."""
        found = graph().entity(id)
        if found is None:
            return answered({"error": f"no entity {id!r}; entities finds them"})
        found.pop("show", None)
        for key in ("links", "backlinks"):
            rows = found.get(key, [])
            if len(rows) > LIMIT:
                found[key] = rows[:LIMIT] + [{"and_more": len(rows) - LIMIT}]
        return answered(found)

    @tool
    def show(ids: list[str]) -> str:
        """Show entities to the engineer: each on the canvas it belongs to - the drawing, the CAD,
        the deck's mesh, the design space - highlighted, with the first one's card open. Show what
        you talk about rather than describing where it is."""
        known = graph().entities
        out: dict[str, Any] = {"shown": [i for i in ids if i in known]}
        missing = [i for i in ids if i not in known]
        if missing:
            out["unknown"] = missing
        return json.dumps(out)

    @tool
    def answer(question: str, value: str | None, quotes: list[str]) -> str:
        """Record the engineer's answer to one of the pipeline's questions - only what their words
        give, quoted exactly. value: one of the options the question offers, or null to take an
        answer back. What is answered applies when the design space is derived again."""
        from ..api import pipeline as pipeline_api

        heard = " ".join(ctx.said)
        missing = [q for q in quotes if not q.strip() or q not in heard]
        if not quotes or missing:
            refused = "every answer rests on the engineer's words, quoted exactly"
            if missing:
                refused += f"; not said: {missing}"
            return json.dumps({"refused": refused})
        try:
            recorded = pipeline_api.record_answer(question, value)
        except (KeyError, ValueError) as error:
            return json.dumps({"refused": str(error.args[0] if error.args else error)})
        ctx.changed.add("answers")
        ctx.questions = 0
        return json.dumps(
            {"answers": recorded["answers"], "next": "derive applies them, once all are given"}
        )

    @tool
    def derive() -> str:
        """Derive the design space again, applying every answer recorded since it was last derived.
        About a minute on a large part; the engineer sees each step on the pipeline as it runs.
        What comes back is each step and what it said."""
        from ..api import designspace

        if designspace.held.running:
            return json.dumps({"refused": "the design space is being derived already"})
        records: list[dict[str, Any]] = []
        failed: list[str] = []
        ended = threading.Event()

        def heard(event: dict[str, Any] | None) -> None:
            if event is None:
                ended.set()
            elif event["type"] == "step" and event["status"] != "running":
                record = {"step": event["id"], "status": event["status"]}
                if event.get("detail"):
                    record["said"] = event["detail"]
                records.append(record)
            elif event["type"] == "error":
                failed.append(event["message"])

        designspace.start(designspace.RunRequest(reuse=True), heard)
        if not ended.wait(DERIVE_WAIT_S):
            return json.dumps({"still_running": "the pipeline shows it; ask pipeline later"})
        ctx.changed.add("space")
        out: dict[str, Any] = {"steps": records}
        if failed:
            out["failed"] = failed
        return json.dumps(out)

    # --- the part --------------------------------------------------------------------------------

    @tool
    def find(
        kind: str | None = None,
        touching: str | None = None,
        facing: list[float] | None = None,
        on_axis: str | None = None,
        limit: int = 30,
    ) -> str:
        """Entities of the part, largest first. Ids look like planar_group:114, hole:3, bore:196,
        boss:352; any single CAD face is face:1453, wherever an id goes.

        kind: hole, bore, boss, planar_group, fillet, hole_pattern - or axis, for the part's axes
          with the bores, bosses and holes on each.
        touching: only what shares an edge with this entity.
        facing: only flat groups facing within 25 degrees of this direction [x, y, z].
        on_axis: only what turns about this axis.
        """
        if kind == "axis":
            return answered({"axes": reading.axes(extraction, max(1, min(int(limit), 12)))})
        chosen = list(features.features.values())
        if kind:
            chosen = [f for f in chosen if str(f.kind) == kind]
        if touching:
            if features.get(touching) is None:
                return answered({"error": _unknown(touching)})
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
        if on_axis:
            chosen = [f for f in chosen if f.axis_id == on_axis]
        chosen.sort(key=lambda f: -f.area_mm2)
        limit = max(1, min(int(limit), LIMIT))
        return answered({"total": len(chosen), "found": [row(f) for f in chosen[:limit]]})

    @tool
    def describe(ids: list[str]) -> str:
        """What entities are (planar_group:114, face:1453, boss:352): size, position, which way
        they face or the axis they turn about, how far they reach along it, what they touch, the
        features a face belongs to, the holes through a flat one. For two or more, how each pair
        stands: touching, the angle between them, facing each other across what gap, on one axis."""
        out = []
        firsts = []
        for ref in ids[:LIMIT]:
            f = features.get(ref)
            if f is None:
                out.append({"id": ref, "error": _unknown(ref)})
                continue
            item = row(f)
            direction = f.normal
            if direction is None and f.axis_id and f.axis_id in features.axes:
                direction = features.axes[f.axis_id].direction
            if direction is not None:
                low, high = extent(tess, f.face_ids, direction)
                item["reach_along_own_direction_mm"] = [round(low, 2), round(high, 2)]
            face = atlas.faces[f.face_ids[0]]
            if face.concave is not None and face.axis is not None:
                item["material"] = "outside it (a bore)" if face.concave else "inside it (a boss)"
            item["in"] = [x.id for x in features.containing(f.face_ids[0]) if x.id != ref]
            item["touches"] = [
                f"{n} ({features.features[n].kind})" for n in neighbours(features, atlas, ref)
            ][:LIMIT]
            if f.kind == FeatureKind.PLANAR_GROUP or f.metrics.get("flat") == 1.0:
                mine = set(f.face_ids)
                holes = [h for h in features.of_kind(FeatureKind.HOLE) if mine & set(h.opens_onto)]
                item["holes_through_it"] = [h.id for h in holes][:LIMIT]
            out.append(item)
            firsts.append(face)
        pairs = [
            _relation(a, b, features.diagonal_mm)
            for i, a in enumerate(firsts)
            for b in firsts[i + 1 :]
        ]
        return answered({"entities": out, "pairs": pairs[:LIMIT]} if pairs else {"entities": out})

    @tool
    def relate(
        ids: list[str],
        relation: Literal["stands_on", "rises_round", "around", "on_axis", "across", "between"],
    ) -> str:
        """How entities stand to the rest of the part.

        stands_on: the flat faces an entity rises from - a boss, a bore, a wall - reached across
          the fillets at its foot, each with whether it goes all the way round it; also faces it
          opens onto or that top it.
        rises_round: what stands up round a floor - faces in one plane - past the blends at its
          edges: walls, bosses, bores, each with how far it stands above the floor. Floors not in
          one plane are answered each on its own.
        around: the faces sharing an edge with a face, and past any fillet the faces beyond.
        on_axis: what turns about the same axis as an entity: bores, bosses, holes.
        across: what lies across the open space in front of an entity, straight out of its metal:
          the things met first - the wall across a gap - each with the share of the entity that
          looks at it and the gap to it in mm, nearest, middle and farthest; and the share that
          looks out of the part.
        between: for two or more entities together - the way they run together, the heights they
          share, and what is under and over the open space between them, each with the share of
          that space and how far past where they begin or end it is. Something right where they
          begin or end, under or over most of the space, is a floor ribs between them stand on;
          open space there, and they are webs with nothing under them.
        """
        try:
            if relation == "between":
                return answered(reading.between(extraction, sessions._measure(ctx), list(ids)))
            if relation == "across":
                finder = sessions._measure(ctx)
                return answered({ref: reading.across(extraction, finder, ref) for ref in ids[:6]})
            if relation == "stands_on":
                return answered({ref: reading.stands_on(extraction, ref) for ref in ids[:6]})
            if relation == "rises_round":
                try:
                    return answered(reading.rises_round(extraction, list(ids)))
                except ValueError:
                    if len(ids) < 2:
                        raise
                # Floors not in one plane: what rises round each, one by one.
                each = {}
                for ref in ids[:6]:
                    try:
                        each[ref] = reading.rises_round(extraction, [ref], most=20)["round"]
                    except ValueError as error:
                        each[ref] = {"error": str(error)}
                return answered(each)
            if relation == "on_axis":
                out = {}
                for ref in ids[:6]:
                    f = features.get(ref)
                    if f is None:
                        out[ref] = {"error": _unknown(ref)}
                        continue
                    axis = f.axis_id
                    same = [
                        row(x) for x in features.features.values() if axis and x.axis_id == axis
                    ]
                    same.sort(key=lambda r: -(r.get("diameter_mm") or 0.0))
                    out[ref] = {"axis": axis, "on_it": same[:LIMIT]}
                return answered(out)
            out = {}
            for ref in ids[:4]:
                f = features.get(ref)
                if f is None:
                    out[ref] = {"error": _unknown(ref)}
                    continue
                face = atlas.faces[f.face_ids[0]]
                rows, seen = [], {face.face_id}
                for n in face.neighbours:
                    if n in seen:
                        continue
                    seen.add(n)
                    other = atlas.faces[n]
                    rows.append(_ring_row(face, other, features, via=None))
                    if other.surface_type in ("torus", "sphere", "bspline"):
                        for m in other.neighbours:
                            if m not in seen:
                                seen.add(m)
                                rows.append(_ring_row(face, atlas.faces[m], features, via=n))
                out[ref] = rows[: LIMIT * 2]
            return answered(out)
        except ValueError as error:
            return answered({"error": str(error)})

    @tool
    def measure(id: str, direction: list[float] | None = None) -> str:
        """How far an entity reaches along a direction [x, y, z] - its lowest and highest point
        along it, in mm - or, with no direction, how thick the metal is under it."""
        f = features.get(id)
        if f is None:
            return answered({"error": _unknown(id)})
        if direction is None:
            through = reading.thickness_at(extraction, sessions._measure(ctx).exit_along, id)
            return answered({"id": id, "metal_under_it_mm": through})
        low, high = extent(tess, f.face_ids, tuple(direction))
        return answered(
            {"id": id, "direction": direction, "low_mm": round(low, 3), "high_mm": round(high, 3)}
        )

    @tool
    def search_drawing(text: str) -> str:
        """Lines of the drawing's text containing this (case-insensitive), with their pages - notes,
        title block, labels and dimensions alike. Try the drawing's own wording."""
        drawing = extraction.drawing
        if drawing is None:
            return answered({"error": "this project has no drawing"})
        hits = [{"page": page, "text": line} for page, line in drawing.search(text)]
        return answered({"total": len(hits), "lines": hits[:LIMIT]})

    return [
        pipeline,
        entities,
        entity,
        show,
        answer,
        derive,
        find,
        describe,
        relate,
        measure,
        search_drawing,
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


def _unknown(ref: str) -> str:
    return (
        f"no feature or face {ref!r} - ids look like planar_group:114, hole:3, bore:196, "
        "or face:1453 for a single face"
    )
