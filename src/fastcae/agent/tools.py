"""The agent's tools: a few general ones, each doing one job, for the agent to compose.

- **find** entities: features by kind, by what they touch, by which way they face, by the axis
  they turn about - or the axes themselves.
- **describe** entities: what each is, and - for several - how they stand to each other.
- **relate** an entity to the part: what it stands on, what rises round it, what is round it, what
  shares its axis, what lies across the open space in front of it - or several together: what lies
  between them, under and over.
- **measure** an entity: how far it reaches along a direction, or how thick the metal is under it.
- **search_drawing** for its words.
- **read_study** and **edit_study**: the study's draft, read, and changed - the only way to change
  it. An edit comes back with where the ribs would go, counted, so the agent can see its reading
  makes ribs before the engineer does.
- **skill**: how to compose these for a kind of request, read when needed.

Each calls the engine functions the routes call; nothing here computes geometry of its own, and
nothing an agent does is out of reach of the interface. Results are compact JSON - enough to reason
from, never whole meshes. What the agent changes is checked as any study version is - words quoted
exactly, entities on the part, hard rules citing words - the part's interfaces are closed on it
whatever it sends, and nothing is written until the engineer accepts it. Designs are the
engineer's to make.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

import numpy as np
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from .. import study as studies
from ..features import Feature, FeatureKind, extent, neighbours
from ..generate import reading
from ..generate import session as sessions
from ..generate.session import ATTENTION, Session
from ..generate.slots import CLOSED
from ..study import Constraint, Objective, Preference, Pull, Target
from . import skills as skillbook

LIMIT = 40
_REF = re.compile(r"\b[a-z_]+:\d+\b")
# How many questions of the part, since the study was last changed, before every answer reminds
# the agent that the engineer can be asked instead.
QUESTIONS = 8

# What the tools work on: the open project's rib work, and the conversation.
Context = Session


def _kinds() -> str:
    """The kinds of rule the platform knows, as a rule of each reads - what it needs in angle
    brackets - for the agent to pick from."""
    known = []
    for name, kind in studies.KINDS.items():
        if name in CLOSED:
            continue
        says = re.sub(r"\{(\w+)(:[^}]*)?\}", r"<\1>", kind.says)
        known.append(f"{name}: {says}")
    return "; ".join(known)


class Setting(BaseModel):
    """One setting of a block, as the words give it: a value, a low and a high, or the choices."""

    value: float | str | None = None
    low: float | None = None
    high: float | None = None
    step: float | None = None
    options: list[str | float] | None = None


SETTINGS = (
    "generator (parallel, grid, triangle, radial), centre (what spokes turn about), spread "
    "(across, round), angle_deg, count, spacing_mm, thickness_mm, root_fillet_mm, edge_round_mm, "
    "draft_deg, top (slope, level), height_thicknesses, section (flat, T), flange_width_mm, "
    "flange_thickness_mm"
)


class BlockEdit(BaseModel):
    """One block of ribs added, changed or taken out."""

    id: str | None = Field(
        default=None,
        description="The block to change, as read_study names it; left out, a new one.",
    )
    add: str | None = Field(
        default=None,
        description="What the block adds: ribs; thicken - the faces in stand_on moved along their "
        "normal, thicker or thinner; holes - through the plate in stand_on; material - what the "
        "part is cast in.",
    )
    stand_on: list[str] | None = Field(
        default=None,
        description="What its ribs stand on: the floor, as faces or features in one plane. An "
        "empty list: nothing under them - webs between what end_on names, standing along the "
        "way all of it runs. For thicken, the faces moved; for holes, the plate.",
    )
    end_on: list[str] | None = Field(
        default=None,
        description="What its ribs must end on: faces or features. An empty list: whatever rises "
        "round the floor, read off the part.",
    )
    span: Literal["union", "within_one", "must_bridge"] | None = None
    settings: dict[str, Setting | float | str | list[float | str] | None] = Field(
        default_factory=dict,
        description="Settings the words give, by name - "
        + SETTINGS
        + ". A value fixes one - given bare or as value; a low and high, or options - or a bare "
        "list - limit it; null hands it back to the part. What the words leave out is read off "
        "the part.",
    )
    rules: list[Constraint] = Field(
        default_factory=list,
        description="Rules for this block alone - what its ribs keep clear of, how tall they "
        "stand - of the kinds the edit's rules take.",
    )
    remove: bool = False


class EditStudy(BaseModel):
    """The study's draft changed from the engineer's words: blocks, rules and the rest."""

    quotes: list[str] = Field(
        description="The engineer's words this rests on, each copied exactly from what they typed."
    )
    blocks: list[BlockEdit] = Field(default_factory=list)
    rules: list[Constraint] = Field(
        default_factory=list,
        description="Rules for the whole study - every block, now and to come - each of a kind "
        "the platform knows - "
        + _kinds()
        + " - with the entities it names in refs: any face or feature, the holes found, or the "
        "ribs of another block as ribs:b1. A rule for one block goes in that block's rules, or "
        "names it in block. When no kind fits, a new kind with the engineer's words as its text "
        "is kept and listed as not enforced. Hard only for what the engineer said; cites may be "
        "left out.",
    )
    drop: list[str] = Field(
        default_factory=list,
        description="Ids of rules to take out, as read_study shows them: one the words put in, or "
        "one the part suggested for a block. Preferences and objectives by id too.",
    )
    confirm: list[str] = Field(
        default_factory=list,
        description="Ids of rules the part suggested that the engineer's words make theirs.",
    )
    prefer: list[Preference] = Field(default_factory=list)
    objectives: list[Objective] = Field(default_factory=list)
    pull: Pull | None = None
    target: Target | None = None
    attention: list[str] | None = Field(
        default=None,
        max_length=ATTENTION,
        description="At most three short lines for the engineer to look at before accepting the "
        "draft as it will stand: a question only they can answer that would change every design, "
        "an assumption that matters, a rule nothing enforces yet - naming entities by id. Never "
        "what the variant card already shows. Left out, the lines already there stay; an empty "
        "list clears them.",
    )


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
        """An answer about the part - past a few since the study was last changed, with a reminder
        that the engineer can be asked instead."""
        ctx.questions += 1
        if ctx.questions > QUESTIONS:
            note = (
                f"{ctx.questions} questions of the part since the study was last changed. Write "
                "what is clear, and ask the engineer the rest in the attention lines, naming the "
                "candidates by id."
            )
            out = {**out, "note": note} if isinstance(out, dict) else {"answer": out, "note": note}
        return json.dumps(out)

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

    @tool
    def read_study() -> str:
        """The study's draft as the engineer sees it on the variant card: each block - what its ribs
        stand on, end on and keep clear of, its settings, fixed or what they may take and who said
        so, its rules with their ids - the rules for the whole study, what is needed and what
        cannot be built yet, whether it differs from the study as last accepted, and the words it
        rests on."""
        card = sessions.view(ctx)
        study = studies.active(ctx.project)
        out = _compact(card)
        out["words"] = [w.text for w in study.current.words] if study else []
        return json.dumps(out)

    @tool(args_schema=EditStudy)
    def edit_study(
        quotes: list[str],
        blocks: list[BlockEdit] | None = None,
        rules: list[Constraint] | None = None,
        drop: list[str] | None = None,
        confirm: list[str] | None = None,
        prefer: list[Preference] | None = None,
        objectives: list[Objective] | None = None,
        pull: Pull | None = None,
        target: Target | None = None,
        attention: list[str] | None = None,
    ) -> str:
        """Change the study's draft from the engineer's words - the only way to change the study.
        What a block needs that the words leave open is read off the part, as a range. Checked as
        a study version is: refused, with the reason and nothing changed, if a quote is not their
        exact words, an entity is not on the part or a rule is incomplete. The part's interfaces
        are closed on it. What comes back is the draft as it now reads, and where each block's
        ribs would go at its suggested point, counted."""
        changes = []
        for change in blocks or []:
            data = change.model_dump(exclude_unset=True)
            if "settings" in data:
                data["settings"] = {name: _setting(s) for name, s in data["settings"].items()}
            changes.append(data)
        card = sessions.edit(
            ctx,
            quotes=list(quotes),
            blocks=changes,
            rules=[_plain(r) for r in rules or []],
            drop=list(drop or []),
            confirm=list(confirm or []),
            prefer=[_plain(p) for p in prefer or []],
            objectives=[_plain(o) for o in objectives or []],
            pull=_plain(pull) if pull is not None else None,
            target=_plain(target) if target is not None else None,
            attention=attention,
        )
        if isinstance(card.get("refused"), str):
            return json.dumps({"refused": card["refused"]})
        ctx.questions = 0
        out = _compact(card)
        drawn = sessions.paths(ctx)
        out["where_ribs_go"] = drawn.get("blocks") or drawn.get("cannot")
        if drawn.get("waiting"):
            out["waiting"] = drawn["waiting"]
        out["next"] = (
            "The variant card now shows all this to the engineer, with the attention lines above. "
            "If a line no longer holds for the draft as it now is, send attention again - an empty "
            "list clears it. End the turn with no text, unless a block makes no ribs or reads the "
            "words wrongly - then edit again, or ask in the attention lines."
        )
        out["attention"] = list(ctx.attention)
        return json.dumps(out)

    @tool
    def skill(name: str) -> str:
        """How to compose these tools for a kind of request. The skills there are, and when each
        is worth reading, are listed in the instructions."""
        text = skillbook.read(name)
        if text is None:
            return json.dumps({"error": f"no skill {name!r}", "skills": sorted(skillbook.index())})
        return text

    return [
        read_study,
        edit_study,
        find,
        describe,
        relate,
        measure,
        search_drawing,
        skill,
    ]


def _compact(card: dict) -> dict:
    """The draft as the agent reads it, in words: each block by what it stands on, ends on and
    keeps clear of; its settings; every rule by id; and the draft against the study."""
    out: dict[str, Any] = {"accepted_version": card["accepted"], "differs": card["differs"]}
    if card.get("cannot"):
        out["cannot"] = card["cannot"]
        return out
    blocks = []
    for block in card["blocks"]:
        ends = block["end_on"]["refs"]
        item: dict[str, Any] = {
            "id": block["id"],
            "add": block["add"],
            "stands_on": block["stand_on"]["refs"],
            "ends_on": ends[:12] + ([f"and {len(ends) - 12} more"] if len(ends) > 12 else []),
        }
        if block["end_on"]["read_off"]:
            item["ends_on_read_off_the_part"] = True
        item["keeps_clear_of"] = [_said(r) for r in block["keep_clear"]]
        item["settings"] = {s["name"]: f"{s['says']} ({s['source']})" for s in block["settings"]}
        item["rules"] = [_said(r) for r in block["rules"]]
        for key in ("needed", "problems"):
            if block[key]:
                item[key] = block[key]
        if block["cannot"]:
            item["cannot_build"] = block["cannot"]
        if block["note"]:
            item["read_off_the_part"] = block["note"]
        blocks.append(item)
    out["blocks"] = blocks
    out["rules"] = [_said(r) for r in card["rules"]]
    out["interfaces_closed"] = len(card["interfaces"])
    rest = card["rest"] or {}
    for key in ("prefer", "objectives"):
        if rest.get(key):
            out[key] = [f"{item['id']}: {item['says']}" for item in rest[key]]
    out["pull"] = rest["pull"]["says"] if rest.get("pull") else None
    if rest.get("target"):
        out["target"] = rest["target"]["says"]
    named = sorted({ref for ref in _REF.findall(json.dumps(blocks)) if ref in card["names"]})
    if named:
        out["names"] = {ref: card["names"][ref] for ref in named[:LIMIT]}
    if card["changes"]:
        out["changes"] = card["changes"][:LIMIT]
    if card["attention"]:
        out["attention"] = card["attention"]
    return out


def _said(rule: dict) -> dict:
    out = {"id": rule["id"], "says": rule["says"], "strength": rule["strength"], "by": rule["by"]}
    if rule["until"]:
        out["not_enforced"] = rule["until"]
    return out


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


def _plain(value: Any) -> Any:
    return value.model_dump() if isinstance(value, BaseModel) else value


def _setting(given: Any) -> dict | None:
    """A setting as the draft holds it: a bare value is the value, a bare list the options."""
    if given is None:
        return None
    if isinstance(given, list):
        return {"options": given}
    if not isinstance(given, dict):
        return {"value": given}
    return {k: v for k, v in given.items() if v is not None}
