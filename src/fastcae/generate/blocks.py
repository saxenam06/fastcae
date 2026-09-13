"""A block of ribs, read off the part: what the engineer's words leave open, filled as ranges.

The agent writes a block's entities - what its ribs stand on, what they end on - and whatever
settings the engineer gave. Everything else a block needs to make ribs is read off the part here,
for any floor: what rises round it to end on, the holes through it to keep clear of, what spokes
could turn about, the plate under it for the thickness, the drawing's smallest radius. Each
setting comes back as a range or a list of choices round a suggested value, marked as nobody's
choice; each rule the part suggests is marked as the part's, and assumed unless the drawing
states it. What the words gave always wins, and what follows from it - a root fillet from a
thickness given - follows from it. Nothing is written here.

Ribs with nothing under them are webs between what they join, read off what they join: the way
they stand - the one direction all of it runs along - and the open space they cross; spokes about
the round thing among them, or straight webs square to the flat one; as thick as the thinnest of
them allows; their tops level with the lower end.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from pydantic import ValidationError

from .. import knowledge
from ..extract import Extraction
from ..features import FeatureKind
from .placement import _way, hang_frame
from .reading import TELLING, _owner
from .slots import (
    DEFAULT_DRAFT_DEG,
    DEFAULT_SPOKES,
    RADII_MM,
    RIB_TO_PLATE,
    WALLS,
    Given,
    _fillet_floor,
    _through,
    infer,
)

# The fields of the engineer's settings a floor's reading takes as given: a setting's name, and the
# field of ``Given`` it sets when the words fix it.
FIELD_OF = {
    "generator": "pattern",
    "centre": "centre",
    "spread": "spread",
    "angle_deg": "angle_deg",
    "count": "count",
    "spacing_mm": "spacing_mm",
    "thickness_mm": "thickness_mm",
    "root_fillet_mm": "root_fillet_mm",
    "edge_round_mm": "edge_round_mm",
    "draft_deg": "draft_deg",
    "top": "height_top",
}

# A T's flange, in thicknesses of its web: how wide, and how thick.
FLANGE_WIDTH = (2.0, 3.0, 4.0)
FLANGE_THICKNESS = (0.5, 0.75, 1.0)

# How far faces may move when nothing says: thinned by at most this much - and never below the
# least a wall may be - or thickened by up to this much.
THIN_MOST = 4.0
THICK_MOST = 10.0


def described() -> list[dict]:
    """What a block is read off the part as when nothing says, in words - as the pipeline shows."""
    return [
        {
            "name": "faces moved",
            "value": None,
            "says": f"thinned by at most {THIN_MOST:g} mm - never below the least a wall may be "
            f"- or thickened by up to {THICK_MOST:g} mm",
        },
        {
            "name": "T-section ribs",
            "value": None,
            "says": "a flange "
            + ", ".join(f"{w:g}" for w in FLANGE_WIDTH)
            + " times the web wide and "
            + ", ".join(f"{t:g}" for t in FLANGE_THICKNESS)
            + " times it thick",
        },
    ]


def fill(
    extraction: Extraction,
    exit_along,
    block: dict[str, Any],
    floor_radius: float | None = None,
) -> dict[str, Any]:
    """Everything ``block`` needs to make ribs, read off the part round what the words gave.

    ``block`` holds ``support`` - what the ribs stand on - ``anchors`` - what they end on, or none
    to read it off the part - and ``given``, the settings the words gave, as domains.
    ``floor_radius`` is the smallest radius the part allows when the words said it. Returns the
    block's ``where``, its ``free`` settings, the ``rules`` the part suggests for it, ``measured``
    values, the ``pull``, what is ``needed`` and wrong (``problems``), and why nothing can build
    it yet (``cannot``) - with a ``note`` on where each reading came from."""
    support = list(block.get("support") or [])
    anchors = list(block.get("anchors") or [])
    given: dict[str, dict] = dict(block.get("given") or {})
    kind = block.get("add") or "ribs"
    if kind == "thicken":
        return _thicken(extraction, exit_along, support, given)
    if kind == "holes":
        return _holes(extraction, exit_along, support, given)
    if kind == "material":
        return _material(given)
    if not support:
        return _pads(_hanging(extraction, exit_along, anchors, given, floor_radius), given)

    values: dict[str, Any] = {"host": support}
    if anchors:
        values["supports"] = anchors
    for name, domain in given.items():
        field = FIELD_OF.get(name)
        value = _one(domain)
        if field is not None and value is not None:
            values[field] = value
    if floor_radius is not None:
        values["fillet_floor_mm"] = floor_radius
    try:
        told = Given.model_validate(values)
    except ValidationError as error:
        problem = error.errors()[0]
        return _unfilled(support, anchors, given, [f"{problem['loc'][0]}: {problem['msg']}"])
    via = {"host": "words", "supports": "words", "centre": "words"}
    slots = infer(extraction, told, [], exit_along, via, "words")
    notes = {s.label: s.note for s in slots.slots if s.note and s.source not in ("you", "words")}
    if not slots.ready():
        filled = _unfilled(support, anchors, given, slots.problems(), slots.needed())
        filled["note"] = notes
        return filled

    entries = slots.study(cites=["these"])
    (read,) = entries["blocks"]
    free: dict[str, dict] = read["free"]
    free.update(given)
    section = given.get("section")
    if section is not None and "T" in (section.get("options") or []):
        _flange(free, given)
    rules = [
        {**rule, "by": "part"}
        for rule in entries["constraints"]
        if not (floor_radius is not None and rule["kind"] == "smallest_radius")
    ]
    measured_anchors = [] if anchors else _grouped(extraction, read["where"]["anchors"])
    return _pads(
        {
            "where": {
                "support": support,
                "anchors": anchors or measured_anchors,
                "read_off": [] if anchors else ["anchors"],
            },
            "free": free,
            "rules": rules,
            "measured": entries["measured"],
            "pull": entries["pull"],
            "needed": [],
            "problems": [],
            "cannot": None,
            "note": notes,
        },
        given,
    )


def _pads(filled: dict[str, Any], given: dict[str, dict]) -> dict[str, Any]:
    """A block of ribs is held to the wall it meets - no rib thicker than the foundry's rule of
    thumb allows of it - and may thicken a wall round a rib's end, where the wall is thinner than
    that, rather than lose the rib: pads on, unless the words say otherwise."""
    if filled.get("free") is None or filled.get("needed"):
        return filled
    ratio, source = knowledge.rule("rib_to_wall")
    if not any(rule["kind"] == "rib_to_wall" for rule in filled.get("rules", [])):
        filled["rules"] = [
            *filled.get("rules", []),
            {
                "kind": "rib_to_wall",
                "params": {"ratio": ratio},
                "strength": "assumed",
                "by": "part",
                "basis": source,
            },
        ]
    if "pads" not in given:
        filled["free"]["pads"] = {
            "options": ["on", "off"],
            "suggested": "on",
            "source": "default",
            "basis": f"a wall thickened round a rib's end where the rib is thicker than {ratio:g} "
            "of it, rather than the rib left out",
        }
    return filled


def _thicken(
    extraction: Extraction, exit_along, faces: list[str], given: dict[str, dict]
) -> dict[str, Any]:
    """Faces moved along their own normal - a wall, a plate or a boss made thicker or thinner:
    thinned no further than the least a wall may be, measured through the faces, or thickened by
    up to a plate's worth; blended into what is round them."""
    if not faces:
        return _unfilled([], [], given, [], ["the faces to move"])
    least, least_source = knowledge.rule("min_wall_mm")
    walls = [w for w in (_through(extraction, exit_along, ref) for ref in faces) if w]
    wall = min(walls) if walls else None
    thinnest = -float(min(THIN_MOST, max(0, math.floor(wall - least)))) if wall else 0.0
    notes = {}
    if wall is not None:
        notes["wall"] = f"{wall:.1f} mm of metal under them, measured through them"
    free: dict[str, dict] = {
        "offset_mm": {
            "low": thinnest,
            "high": THICK_MOST,
            "step": 1.0,
            "unit": "mm",
            "suggested": 0.0,
            "source": "measured" if wall is not None else "default",
            "basis": (
                f"thinned to no less than {least:g} mm from the {wall:.1f} mm under them, or "
                f"thickened by up to {THICK_MOST:g} mm"
                if wall is not None
                else f"thickened by up to {THICK_MOST:g} mm; the wall under them was not measured"
            ),
        },
        "blend_mm": {
            "options": [10.0, 20.0, 30.0],
            "suggested": 20.0,
            "unit": "mm",
            "source": "default",
            "basis": "how wide the join to the faces round them ramps",
        },
        "min_wall_mm": {
            "low": least,
            "high": least,
            "step": 1.0,
            "unit": "mm",
            "suggested": least,
            "source": "default",
            "basis": least_source,
        },
    }
    free.update(given)
    rules = [
        {
            "kind": "wall_at_least",
            "params": {"mm": least},
            "strength": "assumed",
            "by": "part",
            "basis": least_source,
        }
    ]
    measured = []
    if wall is not None:
        measured.append(
            {
                "what": "wall under the faces moved, measured",
                "value": round(wall, 1),
                "on": faces[0],
                "confirmed": False,
            }
        )
    return {
        "where": {"support": faces, "anchors": [], "read_off": []},
        "free": free,
        "rules": rules,
        "measured": measured,
        "pull": None,
        "needed": [],
        "problems": [],
        "cannot": None,
        "note": notes,
    }


def _holes(
    extraction: Extraction, exit_along, host_refs: list[str], given: dict[str, dict]
) -> dict[str, Any]:
    """Holes through a plate, read off the plate: across from one to four plate thicknesses,
    a lattice square or staggered, set out along the plate's longest direction, kept a plate
    thickness of metal from each other, from what the plate holds already and from its edges."""
    from .placement import host_of
    from .slots import _holes_on, _long_axis_deg, _plate

    if not host_refs:
        return _unfilled([], [], given, [], ["the plate to cut holes in"])
    features = extraction.features
    host, why = host_of(features, host_refs)
    if host is None:
        return _unfilled(host_refs, [], given, [why])
    normal = np.asarray(host.normal, dtype=float)
    plate = _plate(extraction, host, normal, exit_along)
    if not plate:
        return _unfilled(host_refs, [], given, [], ["how thick the plate is - it was not measured"])
    factor, ligament_source = knowledge.rule("hole_ligament")
    ligament = round(factor * plate)
    smallest = max(10.0, 5.0 * math.ceil(plate / 5.0))
    largest = max(smallest + 10.0, 5.0 * math.floor(4.0 * plate / 5.0))
    suggested = min(largest, max(smallest, 5.0 * round(2.0 * plate / 5.0)))
    angle = round(_long_axis_deg(extraction, host) / 15.0) * 15.0 % 180.0
    free: dict[str, dict] = {
        "pattern": {
            "options": ["grid", "staggered"],
            "suggested": "staggered",
            "source": "default",
            "basis": "a square lattice, or every other row shifted by half",
        },
        "diameter_mm": {
            "low": smallest,
            "high": largest,
            "step": 5.0,
            "unit": "mm",
            "suggested": suggested,
            "source": "measured",
            "basis": f"one to four times the {plate:.1f} mm plate",
        },
        "pitch_mm": {
            "low": 2.0 * smallest,
            "high": 5.0 * largest,
            "step": 10.0,
            "unit": "mm",
            "suggested": 10.0 * round(3.0 * suggested / 10.0),
            "source": "default",
            "basis": "two to five diameters between centres",
        },
        "angle_deg": {
            "low": 0.0,
            "high": 165.0,
            "step": 15.0,
            "unit": "°",
            "suggested": angle,
            "source": "measured",
            "basis": "the plate's longest direction",
        },
        "edge_mm": {
            "low": float(ligament),
            "high": float(3 * ligament),
            "step": 5.0,
            "unit": "mm",
            "suggested": float(2 * ligament),
            "source": "default",
            "basis": "one to three plate thicknesses from the plate's edges and the walls round it",
        },
        "ligament_mm": {
            "low": float(ligament),
            "high": float(ligament),
            "step": 1.0,
            "unit": "mm",
            "suggested": float(ligament),
            "source": "default",
            "basis": ligament_source,
        },
    }
    free.update(given)
    rules: list[dict[str, Any]] = []
    holes, _ = _holes_on(features, host_refs)
    if holes:
        rules.append(
            {
                "kind": "keep_clear_of",
                "refs": holes,
                "params": {"clearance_mm": float(ligament)},
                "strength": "assumed",
                "by": "part",
                "text": f"{len(holes)} holes the plate has already, {ligament} mm clear",
                "basis": ligament_source,
            }
        )
    return {
        "where": {"support": host_refs, "anchors": [], "read_off": []},
        "free": free,
        "rules": rules,
        "measured": [
            {
                "what": "plate the holes go through, measured",
                "value": round(plate, 1),
                "on": host_refs[0],
                "confirmed": False,
            }
        ],
        "pull": None,
        "needed": [],
        "problems": [],
        "cannot": None,
        "note": {"plate": f"{plate:.1f} mm thick, measured through it"},
    }


def _material(given: dict[str, dict]) -> dict[str, Any]:
    """What the part is cast in: one material, which its designs do not change - the one the words
    name, else the one assumed until someone says which."""
    default, why = knowledge.default_material()
    free: dict[str, dict] = {
        "material": {
            "options": [default],
            "suggested": default,
            "source": "default",
            "basis": "a part is cast in one material, which its designs do not change; "
            f"assumed until someone says which: {why}",
        }
    }
    free.update(given)
    return {
        "where": {"support": [], "anchors": [], "read_off": []},
        "free": free,
        "rules": [],
        "measured": [],
        "pull": None,
        "needed": [],
        "problems": [],
        "cannot": None,
        "note": {},
    }


def _one(domain: dict[str, Any]) -> Any:
    """A setting's one value, when the words fixed it; else None."""
    options = domain.get("options")
    if options is not None:
        return options[0] if len(options) == 1 else None
    low, high = domain.get("low"), domain.get("high")
    if low is not None and high is not None and low == high:
        return low
    return None


def _flange(free: dict[str, dict], given: dict[str, dict]) -> None:
    """A T's flange, in thicknesses of its web, unless the words gave it."""
    thickness = free["thickness_mm"]
    web = float(thickness.get("suggested") or thickness.get("low") or 0.0)
    widest_web = float(thickness.get("high") or web)
    if web <= 0.0:
        return
    if "flange_width_mm" not in given:
        low, mid, high = (math.ceil(k * web) for k in FLANGE_WIDTH)
        low = max(low, math.ceil(widest_web))
        free["flange_width_mm"] = {
            "low": float(low),
            "high": float(max(high, low)),
            "step": 1.0,
            "unit": "mm",
            "suggested": float(min(max(mid, low), max(high, low))),
            "source": "default",
            "basis": "2 to 4 times the web's thickness",
        }
    if "flange_thickness_mm" not in given:
        low, mid, high = (round(k * web * 2.0) / 2.0 for k in FLANGE_THICKNESS)
        free["flange_thickness_mm"] = {
            "low": max(low, 0.5),
            "high": max(high, 0.5),
            "step": 0.5,
            "unit": "mm",
            "suggested": max(mid, 0.5),
            "source": "default",
            "basis": "half to all of the web's thickness",
        }


def _grouped(extraction: Extraction, refs: list[str]) -> list[str]:
    """Faces read off the part, named by the features they belong to where they have one: a boss
    or a wall once, not every face of it."""
    features = extraction.features
    assert features is not None
    out: list[str] = []
    for ref in refs:
        named = ref
        if ref.startswith("face:"):
            named = _owner(features, int(ref.split(":", 1)[1]), TELLING)
        if named not in out:
            out.append(named)
    return out


def _unfilled(support, anchors, given, problems, needed=()) -> dict[str, Any]:
    return {
        "where": {"support": support, "anchors": anchors, "read_off": []},
        "free": dict(given),
        "rules": [],
        "measured": [],
        "pull": None,
        "needed": list(needed),
        "problems": list(problems),
        "cannot": None,
        "note": {},
    }


def _hanging(
    extraction: Extraction,
    exit_along,
    anchors: list[str],
    given: dict[str, dict],
    floor_radius: float | None,
) -> dict[str, Any]:
    """A block with nothing under it: webs between what it joins, filled round what the words gave.
    They stand along the one direction everything they join runs along, from where the last of it
    begins; spokes about the round thing among them, largest first, or straight webs square to the
    largest flat one; as thick as the thinnest of them allows; their tops level with the lower end
    unless the words say otherwise."""
    features, tess = extraction.features, extraction.tess
    assert features is not None and tess is not None
    if len(anchors) < 2:
        return _unfilled([], anchors, given, [], ["what the webs join: two things or more"])
    hang, problem = hang_frame(features, tess, anchors)
    if hang is None:
        return _unfilled([], anchors, given, [problem])
    frame, band = hang.frame, hang.band
    level = float(frame.origin @ frame.normal)
    # A boss before a bore, then the largest: spokes turn about what stands out.
    round_ = sorted(
        (ref for ref in anchors if _round_thing(features, ref)),
        key=lambda ref: (
            bool(features.faces[features.get(ref).face_ids[0]].concave),
            -features.get(ref).area_mm2,
        ),
    )
    flat = sorted(
        (ref for ref in anchors if features.get(ref).normal is not None and ref not in round_),
        key=lambda ref: -features.get(ref).area_mm2,
    )

    # As thick as the thinnest of the largest things it joins allows.
    largest = sorted(anchors, key=lambda ref: -features.get(ref).area_mm2)[:WALLS]
    walls = {ref: _through(extraction, exit_along, ref) for ref in largest}
    walls = {ref: w for ref, w in walls.items() if w}
    free: dict[str, dict] = {}
    joined = list(hang.joins)
    notes = {
        "webs": f"stand along {_way(frame.normal)}, from {level:.0f} to {level + band:.0f} mm - "
        f"where {_listed(joined)} all are",
    }
    if len(joined) < len(anchors):
        notes["webs"] += f"; {_listed([a for a in anchors if a not in joined])} take no part"
    measured: list[dict] = []
    thickness = None
    if walls:
        thinnest = min(walls, key=walls.get)
        wall = walls[thinnest]
        thickness = round(RIB_TO_PLATE * wall * 2.0) / 2.0
        basis = f"{RIB_TO_PLATE:g} × the {wall:.1f} mm of {thinnest}, the thinnest thing it joins"
        free["thickness_mm"] = {
            "low": min(thickness, round(0.6 * wall * 2.0) / 2.0),
            "high": max(thickness, round(wall * 2.0) / 2.0),
            "step": 0.5,
            "unit": "mm",
            "suggested": thickness,
            "source": "measured",
            "basis": f"0.6 to 1.0 of the {wall:.1f} mm of {thinnest}, the thinnest thing it joins",
        }
        notes["thickness"] = basis
        measured.append(
            {
                "what": f"thickness, measured: {basis}",
                "value": thickness,
                "on": thinnest,
                "confirmed": False,
            }
        )
    given_thickness = _one(given["thickness_mm"]) if "thickness_mm" in given else None
    thickness = float(given_thickness or thickness or 0.0)
    if not thickness:
        return _unfilled(
            [], anchors, given, [], ["how thick - what it joins could not be measured"]
        )

    # Spokes about the round thing among them, or straight webs across.
    kinds = ["radial", "parallel"] if round_ else ["parallel"]
    free["generator"] = {
        "options": kinds,
        "weights": [1.0] * len(kinds),
        "suggested": kinds[0],
        "basis": "spokes about " + round_[0] if round_ else "straight webs across",
    }
    if round_:
        free["centre"] = {
            "options": round_,
            "suggested": round_[0],
            "source": "measured",
            "basis": "the round things it joins, largest first",
        }
        free["spread"] = {"options": ["across", "round"], "suggested": "across"}
    angle = 0.0
    if flat:
        normal = np.asarray(features.get(flat[0]).normal, dtype=float)
        across = normal - (normal @ frame.normal) * frame.normal
        if np.linalg.norm(across) > 1e-6:
            angle = math.degrees(math.atan2(float(across @ frame.e2), float(across @ frame.e1)))
            angle = round(angle % 180.0)
            notes["angle"] = f"straight webs square to {flat[0]}"
    free["angle_deg"] = {
        "low": 0.0,
        "high": 359.0 if round_ else 179.0,
        "step": 15.0,
        "unit": "°",
        "suggested": angle,
        "source": "measured" if flat else "default",
        "basis": notes.get("angle", ""),
    }
    free["count"] = {
        "low": 2,
        "high": 12,
        "step": 1,
        "suggested": min(4, DEFAULT_SPOKES),
        "basis": "2 to 12 webs",
    }
    free["spacing_mm"] = {
        "low": max(10.0, math.floor(5.0 * thickness / 10.0) * 10.0),
        "high": math.ceil(16.0 * thickness / 10.0) * 10.0,
        "step": 10.0,
        "unit": "mm",
        "suggested": round(8.0 * thickness / 10.0) * 10.0 or 10.0,
        "basis": "5 to 16 thicknesses apart",
    }

    # Radii from the smallest the part allows, the draft, and how tall.
    told = Given(fillet_floor_mm=floor_radius) if floor_radius else Given()
    floor, floor_source, floor_note = _fillet_floor(extraction, told)
    least = floor or 0.0
    root = max(least, round(thickness / 2.0))
    edge = floor if floor is not None else thickness / 4.0
    for name, value, most in (
        ("root_fillet_mm", root, thickness),
        ("edge_round_mm", edge, thickness / 2.0),
    ):
        free[name] = {
            "options": sorted({*(r for r in RADII_MM if least <= r <= most), value}),
            "suggested": value,
            "unit": "mm",
            "source": "drawing" if floor_source == "drawing" and value == floor else "default",
            "basis": f"from the smallest radius the part allows to {most:g} mm",
        }
    free["draft_deg"] = {
        "options": [0.5, 1.0, 1.5, 2.0, 3.0],
        "suggested": DEFAULT_DRAFT_DEG,
        "unit": "°",
        "basis": "a conventional draft",
    }
    free["top"] = {"options": ["level", "slope"], "suggested": "level"}
    free["height_fraction"] = {
        "low": 0.5,
        "high": 1.0,
        "step": 0.1,
        "suggested": 1.0,
        "basis": "from half to all of what each end meets",
    }
    free.update(given)
    section = given.get("section")
    if section is not None and "T" in (section.get("options") or []):
        _flange(free, given)

    rules: list[dict[str, Any]] = [
        {"kind": "ends_on", "strength": "assumed", "by": "part"},
        {"kind": "within_what_it_meets", "strength": "assumed", "by": "part"},
    ]
    if floor is not None and floor_source == "drawing" and floor_radius is None:
        rules.append(
            {
                "kind": "smallest_radius",
                "params": {"radius_mm": floor},
                "source": "drawing",
                "basis": floor_note,
                "by": "part",
            }
        )
    return {
        "where": {"support": [], "anchors": anchors, "read_off": []},
        "free": free,
        "rules": rules,
        "measured": measured,
        "pull": None,
        "needed": [],
        "problems": [],
        "cannot": None,
        "note": notes,
    }


def _round_thing(features, ref: str) -> bool:
    """Whether spokes could turn about it: a boss, a bore, a face of one."""
    feature = features.get(ref)
    if feature.kind in (FeatureKind.BOSS, FeatureKind.BORE):
        return True
    faces = [features.faces[f] for f in feature.face_ids]
    return feature.kind != FeatureKind.HOLE and all(
        f.surface_type in ("cylinder", "cone") for f in faces
    )


def _listed(refs: list[str]) -> str:
    return refs[0] if len(refs) == 1 else ", ".join(refs[:-1]) + " and " + refs[-1]
