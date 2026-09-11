"""The rib card: everything a group of ribs needs, set by the engineer or filled from the part.

A group of ribs is a fixed list of slots - where they stand, what they run between, what they keep
clear of, their pattern, how dense, how tall, their section. The engineer starts a card from faces
selected on the part and sets any slot: a value, faces, or words. Everything else is filled in one
pass, from the geometry and the drawing, or with a default that says it is one. What nothing can
settle is marked needed, and what cannot be right is marked as a problem; the card is ready when
it has neither.

Every slot says where its value came from:

- ``you`` - the engineer set it: a value, or words
- ``selected`` - the engineer selected it on the part
- ``drawing`` - the drawing states it, with the page and the literal text
- ``measured`` - measured on the part
- ``default`` - a conventional starting value, not confirmed
- ``needed`` - only the engineer can say

Words are read here, deterministically: ids of faces and features, numbers and their units, and a
small vocabulary per slot. Words it cannot read are kept as typed and flagged, never guessed at.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, Field, ValidationError

from ..extract import Extraction
from ..features import (
    AXIS_DISTANCE_TOL_FRACTION,
    HOLE_WRAP_DEG,
    Feature,
    FeatureKind,
    FeatureSet,
    extent,
    turning_with,
    wrap_deg,
)
from .placement import _frame, host_of

Pattern = Literal["parallel", "grid", "triangle", "radial"]

# Defaults, each a conventional starting point and labelled as one wherever it is shown.
DEFAULT_CLEARANCE_MM = 5.0
DEFAULT_DRAFT_DEG = 1.0
RIB_TO_PLATE = 0.8
PITCH_IN_THICKNESSES = 8.0
DEFAULT_SPOKES = 8

# Values offered in the card's lists. Anything else can still be typed.
RADII_MM = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 16.0, 20.0, 25.0)
DRAFTS_DEG = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0)
PATTERN_NAMES = {
    "parallel": "parallel",
    "grid": "square grid",
    "triangle": "triangle grid",
    "radial": "spokes",
}
TOPS = {"slope": "sloping, each end to what it meets", "level": "level, at the lower end"}
SPREADS = {"across": "fanned across where ribs stand", "round": "all the way round"}

# Offered as what spokes turn about: round things going at least this far round their axis, with
# the rest of them - a boss or a bore, even one the CAD split in two.
ROUND_ENOUGH_DEG = 120.0

# What rises from where ribs stand is found by walking out across blends - fillets of any shape,
# chamfers - to the first faces that stand up. A face stands up when it is at least this steep.
STANDS_UP = math.cos(math.radians(45.0))
BLEND_DEPTH = 3


class Given(BaseModel):
    """What the engineer set. Anything left out is filled from the part or defaulted."""

    host: list[str] = Field(default_factory=list, description="Where ribs stand: face/feature ids.")
    supports: list[str] = Field(
        default_factory=list, description="What ribs run between: face/feature ids."
    )
    holes_on: list[str] = Field(
        default_factory=list,
        description="Faces whose holes ribs keep clear of; a face with no holes is kept clear of "
        "itself. Left out: the holes where ribs stand.",
    )
    avoid_holes: bool | None = Field(
        default=None, description="False if the engineer allows ribs over holes."
    )
    clearance_mm: float | None = Field(default=None, ge=0.0)
    pattern: Pattern | None = None
    centre: str | None = Field(default=None, description="For spokes: what they turn about.")
    spread: Literal["across", "round"] | None = Field(
        default=None,
        description="For spokes: fanned across where ribs stand (across), or all the way round.",
    )
    angle_deg: float | None = None
    angle_from: str | None = Field(
        default=None,
        description="Orientation from the part instead of a number: straight ribs along this "
        "face (or square to it), the first spoke toward it.",
    )
    angle_across: bool | None = Field(default=None, description="Square to angle_from, not along.")
    count: int | None = Field(default=None, ge=1)
    spacing_mm: float | None = Field(default=None, gt=0.0)
    height_mm: float | None = Field(default=None, gt=0.0)
    not_above: list[str] = Field(default_factory=list)
    height_top: Literal["slope", "level"] | None = Field(
        default=None,
        description="slope: each end as tall as what it meets, the top straight between; level: "
        "held to the lower end all along.",
    )
    thickness_mm: float | None = Field(default=None, gt=0.0)
    root_fillet_mm: float | None = Field(default=None, gt=0.0)
    edge_round_mm: float | None = Field(default=None, ge=0.0)
    draft_deg: float | None = Field(default=None, ge=0.0, lt=30.0)
    fillet_floor_mm: float | None = Field(default=None, gt=0.0)


# Every slot: its label, and the fields of ``Given`` it holds - the first is the one a bare value
# sets.
SLOTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "host": ("where ribs stand", ("host",)),
    "supports": ("what they run between", ("supports",)),
    "keep_out": ("keep clear of", ("clearance_mm", "holes_on", "avoid_holes")),
    "pattern": ("pattern", ("pattern", "centre", "spread")),
    "orientation": ("orientation", ("angle_deg", "angle_from", "angle_across")),
    "density": ("how many", ("count", "spacing_mm")),
    "height": ("how tall", ("height_mm", "not_above", "height_top")),
    "thickness": ("thickness", ("thickness_mm",)),
    "root_fillet": ("root fillet", ("root_fillet_mm",)),
    "edge_round": ("edge round", ("edge_round_mm",)),
    "draft": ("draft", ("draft_deg",)),
    "fillet_floor": ("smallest radius", ("fillet_floor_mm",)),
}
FACE_FIELDS = ("host", "supports", "holes_on", "not_above", "centre", "angle_from")
# Face fields that hold one face, not a list.
ONE_FACE = ("centre", "angle_from")


# --- the slots, filled ---------------------------------------------------------------------------


@dataclass
class Slot:
    name: str
    label: str
    value: Any
    shown: str
    source: str
    refs: list[str] = field(default_factory=list)
    """What the slot holds, to show on the part."""
    note: str = ""
    parts: list[dict] = field(default_factory=list)
    """The controls the card draws for it: faces, numbers, choices."""
    problems: list[str] = field(default_factory=list)
    words: str | None = None
    """Its value, written as words the card reads back - where typing over it starts from. None:
    as shown."""

    def row(self) -> dict:
        return {
            "key": self.name,
            "label": self.label,
            "shown": self.shown,
            "source": self.source,
            "refs": self.refs,
            "note": self.note,
            "parts": self.parts,
            "problems": self.problems,
            "words": self.shown if self.words is None else self.words,
        }


@dataclass
class Slots:
    slots: list[Slot]

    def get(self, name: str) -> Slot:
        return next(s for s in self.slots if s.name == name)

    def needed(self) -> list[str]:
        return [s.label for s in self.slots if s.source == "needed"]

    def problems(self) -> list[str]:
        return [f"{s.label}: {p}" for s in self.slots for p in s.problems]

    def ready(self) -> bool:
        return not self.needed() and not self.problems()

    def placement(self, cites: list[str]) -> dict:
        """The spec placement these slots describe. Refused while anything is needed or wrong."""
        if not self.ready():
            raise ValueError("the card is not ready: " + "; ".join(self.needed() + self.problems()))
        pattern = self.get("pattern").value
        angle = float(self.get("orientation").value or 0.0)
        density = self.get("density").value
        if pattern == "radial":
            spread = next(
                (p["value"] for p in self.get("pattern").parts if p.get("field") == "spread"),
                "across",
            )
            layout = {
                "kind": "radial",
                "centre": self.get("pattern").refs[0],
                "count": int(density["count"]),
                "phase_deg": angle,
                "spread": spread,
            }
        else:
            # Each family's angle and where its lines sit between lattice points. A triangle grid's
            # middle family sits on them where the outer two sit halfway, so all three meet.
            families = {
                "parallel": [(0.0, 0.5)],
                "grid": [(0.0, 0.5), (90.0, 0.5)],
                "triangle": [(0.0, 0.5), (60.0, 0.0), (120.0, 0.5)],
            }
            key = "count" if "count" in density else "spacing_mm"
            layout = {
                "kind": "parallel" if pattern == "parallel" else "grid",
                "families": [
                    {"angle_deg": angle + a, key: density[key], "offset": offset}
                    for a, offset in families[pattern]
                ],
            }
        supports = self.get("supports").refs
        return {
            "id": "p1",
            "host": self.get("host").refs,
            "supports": supports,
            "keep_out": self.get("keep_out").value,
            "layout": layout,
            "height": self.get("height").value,
            "section": {
                "thickness_mm": self.get("thickness").value,
                "root_fillet_mm": self.get("root_fillet").value,
                "edge_round_mm": self.get("edge_round").value,
                "draft_deg": self.get("draft").value,
            },
            "connection": "supports" if supports else "free",
            "cites": cites,
        }

    def rules(self) -> dict:
        return {"fillet_floor_mm": self.get("fillet_floor").value}

    def measured(self) -> list[dict]:
        """The numbers the part, the drawing or a default settled - not the engineer - each marked
        unconfirmed, so a spec says which of its values nobody set."""
        on = self.get("host").refs[0] if self.get("host").refs else None
        out = []
        for slot in self.slots:
            if slot.source not in ("measured", "default", "drawing") or on is None:
                continue
            value = slot.value
            if isinstance(value, dict):
                value = next((v for v in value.values() if isinstance(v, int | float)), None)
            if isinstance(value, int | float) and not isinstance(value, bool):
                what = f"{slot.label}, {slot.source}" + (f": {slot.note}" if slot.note else "")
                out.append({"what": what, "value": float(value), "on": on, "confirmed": False})
        return out


def infer(
    extraction: Extraction,
    given: Given,
    start: list[int] | None = None,
    exit_along=None,
    via: dict[str, str] | None = None,
) -> Slots:
    """Every slot, filled. ``start`` is the faces the card began from, sorted here into where ribs
    stand and what they run between. ``exit_along(point, direction)`` measures through the metal.
    ``via`` says which face fields the engineer filled by selecting rather than by typing."""
    features = extraction.features
    atlas = extraction.atlas
    assert features is not None and atlas is not None
    faces = atlas.faces
    start = [f for f in start or [] if f in faces]
    via = via or {}
    hole_faces = {f for h in features.of_kind(FeatureKind.HOLE) for f in h.face_ids}
    slots: list[Slot] = []

    def said(name: str) -> str:
        return via.get(name, "you")

    # --- where the ribs stand ------------------------------------------------------------------
    host_refs: list[str] = []
    host_source, host_note, host_problems = "needed", "", []
    if given.host:
        host_refs, host_source = list(given.host), said("host")
    else:
        flat = [f for f in start if faces[f].surface_type == "plane"]
        if flat:
            group = _host_among(features, flat, start)
            host_refs = [f"face:{f}" for f in group.face_ids]
            host_source = "selected"
            host_note = "the flat area the rest of your selection rises from"
    host: Feature | None = None
    if host_refs:
        host, why = host_of(features, host_refs)
        if host is None:
            host_problems.append(why)
    slots.append(
        Slot(
            "host",
            SLOTS["host"][0],
            host_refs,
            _faces_shown(host_refs, host),
            host_source,
            host_refs,
            host_note if host_refs else "select the flat faces ribs stand on",
            [_faces_part("host", "", host_refs)],
            host_problems,
            ", ".join(host_refs),
        )
    )
    normal = np.asarray(host.normal, dtype=float) if host is not None else None
    host_faces = set(host.face_ids) if host is not None else set()

    # --- what they run between -----------------------------------------------------------------
    note, problems = "", []
    if given.supports:
        support_refs, source = list(given.supports), said("supports")
    else:
        rest = [f for f in start if f not in host_faces and f not in hole_faces]
        if rest:
            support_refs, source = [f"face:{f}" for f in rest], "selected"
        elif host is not None and normal is not None:
            support_refs = [
                f"face:{f}"
                for f in _walls_around(
                    atlas, host_faces, normal, hole_faces, float(np.dot(host.centroid, normal))
                )
            ]
            source = "measured" if support_refs else "default"
            note = "what rises round where ribs stand, past any fillet or chamfer at its foot"
        else:
            support_refs, source = [], "default"
    unknown = [r for r in support_refs if features.get(r) is None]
    if unknown:
        problems.append(f"the part has no {', '.join(unknown)}")
    crossing = [
        r
        for r in support_refs
        if features.get(r) is not None and host_faces & set(features.get(r).face_ids)
    ]
    if crossing:
        problems.append(f"{', '.join(crossing)} is where ribs stand, not what they run between")
    slots.append(
        Slot(
            "supports",
            SLOTS["supports"][0],
            support_refs,
            f"{len(support_refs)} faces" if support_refs else "the edges of where ribs stand",
            source,
            support_refs,
            note if support_refs else "ribs end at the edges of where they stand",
            [_faces_part("supports", "", support_refs)],
            problems,
            ", ".join(support_refs),
        )
    )

    # --- what they keep clear of ---------------------------------------------------------------
    clearance = given.clearance_mm if given.clearance_mm is not None else DEFAULT_CLEARANCE_MM
    on = list(given.holes_on) or list(host_refs)
    keep: list[dict] = []
    keep_refs: list[str] = []
    problems = []
    if given.avoid_holes is False:
        keep_shown, keep_source, keep_note = "nothing - ribs may cross holes", "you", ""
    else:
        unknown = [r for r in on if features.get(r) is None]
        if unknown:
            problems.append(f"the part has no {', '.join(unknown)}")
        holes, themselves = _holes_on(features, [r for r in on if r not in unknown])
        keep_refs = [*holes, *(themselves if given.holes_on else [])]
        if keep_refs:
            keep.append({"features": keep_refs, "clearance_mm": clearance, "cites": []})
        where = ", ".join(given.holes_on) if given.holes_on else "where ribs stand"
        keep_shown = f"{len(holes)} holes on {where}, {clearance:g} mm clear"
        if themselves and given.holes_on:
            keep_shown += f"; {', '.join(themselves)} itself"
        set_by_you = given.holes_on or given.clearance_mm is not None or given.avoid_holes
        keep_source = said("holes_on") if given.holes_on else ("you" if set_by_you else "default")
        keep_note = "" if given.holes_on else "the holes through where ribs stand"
    slots.append(
        Slot(
            "keep_out",
            SLOTS["keep_out"][0],
            keep,
            keep_shown,
            keep_source,
            keep_refs,
            keep_note,
            [
                {
                    "type": "toggle",
                    "field": "avoid_holes",
                    "label": "keep clear of holes",
                    "value": given.avoid_holes is not False,
                },
                _faces_part("holes_on", "holes on", list(given.holes_on), shown=on),
                {"type": "list", "label": "holds", "refs": keep_refs},
                _number("clearance_mm", "clear by", clearance, "mm", 1.0, 0.0),
            ],
            problems,
            "none"
            if given.avoid_holes is False
            else (f"holes on {', '.join(on)}, " if on else "") + f"{clearance:g} mm clear",
        )
    )

    # --- the section: thickness first, the rest follow from it ------------------------------
    floor, floor_source, floor_note = _fillet_floor(extraction, given)
    thickness, thickness_source, thickness_note = _thickness(
        extraction, host, normal, given, exit_along
    )
    root = given.root_fillet_mm or (
        None if thickness is None else max(floor or 0.0, round(thickness / 2.0))
    )
    edge = (
        given.edge_round_mm
        if given.edge_round_mm is not None
        else (floor if floor is not None else (None if thickness is None else thickness / 4.0))
    )
    draft = given.draft_deg if given.draft_deg is not None else DEFAULT_DRAFT_DEG

    # --- the pattern ---------------------------------------------------------------------------
    problems = []
    offered = _centres(features, support_refs, normal, hole_faces) if normal is not None else []
    if given.pattern is not None:
        pattern, pattern_source, pattern_note = given.pattern, "you", ""
        centre = given.centre
        if pattern == "radial" and centre is None:
            centre = _round_centre(extraction, host, normal, support_refs, hole_faces)
            pattern_note = "" if centre is None else "what where ribs stand surrounds"
            if centre is None and offered:
                # Asked for spokes: the largest round thing there is, rather than nothing.
                centre = offered[0][0]
                pattern_note = "the largest round thing standing in where ribs stand"
    else:
        centre = _round_centre(extraction, host, normal, support_refs, hole_faces)
        if centre is not None:
            pattern, pattern_source = "radial", "default"
            pattern_note = "something round stands where ribs stand, and they surround it"
        else:
            pattern, pattern_source, pattern_note = "grid", "default", ""
    if pattern == "radial" and centre is None:
        pattern_source, pattern_note = "needed", "spokes need something to turn about: pick one"
    elif pattern == "radial" and features.get(centre) is None:
        problems.append(f"the part has no {centre}")
    elif pattern == "radial" and centre in given.host + host_refs:
        problems.append("spokes turn about something standing in where ribs stand, not the floor")
    if pattern != "radial":
        centre = None
    pattern_parts = [_choice("pattern", "", pattern, PATTERN_NAMES)]
    if pattern == "radial":
        about = _faces_part("centre", "about", [centre] if centre else [], single=True)
        if centre and centre not in dict(offered):
            offered.insert(0, (centre, centre))
        about["options"] = [{"value": ref, "label": label} for ref, label in offered]
        pattern_parts.append(about)
    # Spokes fan across where ribs stand - unless the engineer turned them, an angle or a face to
    # point at: a fan cannot be turned, so those go all the way round.
    turned = given.angle_deg is not None or given.angle_from is not None
    spread = given.spread or ("round" if turned else "across")
    if pattern == "radial":
        pattern_parts.append(_choice("spread", "", spread, SPREADS))
    fanned = pattern == "radial" and spread == "across"
    described = PATTERN_NAMES[pattern] + (f" about {centre}" if centre else "")
    described += ", fanned across where ribs stand" if fanned else ""
    slots.append(
        Slot(
            "pattern",
            SLOTS["pattern"][0],
            pattern,
            described,
            pattern_source,
            [centre] if centre else [],
            pattern_note,
            pattern_parts,
            problems,
            described,
        )
    )

    # --- which way: from a wall, unless the engineer says otherwise ---------------------------
    spokes = pattern == "radial"
    # Straight ribs are set out from the longest wall round where they stand, unless the engineer
    # gave an angle or a face: a grid lines up with it, parallel ribs run out from it.
    wall = None
    if not spokes and not given.angle_from and given.angle_deg is None and host is not None:
        wall = _main_wall(extraction, host, support_refs)
    reference = given.angle_from or wall
    across = given.angle_across if given.angle_across is not None else pattern == "parallel"
    relation = "toward" if spokes else ("square to" if across else "along")
    angle = given.angle_deg
    angle_source, angle_note, problems = "you", "", []
    angle_words = None
    if reference and host is not None:
        found = _angle_from(extraction, host, reference, centre if spokes else None)
        if found is None:
            problems.append(f"no direction can be taken from {reference}")
            angle = 0.0
        else:
            angle = found + (90.0 if across and not spokes else 0.0)
        angle_words = f"{relation} {reference}"
        angle_note = angle_words + (", the longest wall round where ribs stand" if wall else "")
        angle_source = "measured" if wall else "you"
    elif angle is None:
        angle = _long_axis_deg(extraction, host) if host is not None else 0.0
        angle_source = "measured" if host is not None else "default"
        angle_note = (
            "the first spoke along the longest direction of where ribs stand"
            if spokes
            else "along the longest direction of where ribs stand"
        )
    if host is not None and not reference:
        frame = _frame(host)
        axes = f"0° points along {_axis_word(frame.e1)}, 90° along {_axis_word(frame.e2)}"
        angle_note = f"{angle_note} - {axes}" if angle_note else axes
    if fanned:
        angle_note = (
            "a fan spreads its spokes evenly across where ribs stand; this turns spokes that "
            "go all the way round"
        )
    if not spokes and given.angle_deg is None:
        angle %= 180.0  # a straight rib runs both ways: 225° is 45°
    orientation_parts = [
        _number("angle_deg", "", round(angle, 1), "°", 5.0, None),
        _faces_part(
            "angle_from",
            "or toward" if spokes else "or along",
            [given.angle_from] if given.angle_from else [],
            shown=[wall] if wall else None,
            single=True,
        ),
    ]
    if reference and not spokes:
        orientation_parts.append(
            _choice("angle_across", "", across, {False: "along it", True: "square to it"})
        )
    slots.append(
        Slot(
            "orientation",
            SLOTS["orientation"][0],
            round(angle, 1),
            angle_words or f"{angle:.0f}°",
            angle_source,
            [reference] if reference else [],
            angle_note,
            orientation_parts,
            problems,
            words=angle_words or f"{round(angle, 1):g}°",
        )
    )

    density: dict[str, float]
    problems = []
    if given.count is not None:
        density, shown, source, note = {"count": given.count}, f"{given.count}", "you", ""
    elif given.spacing_mm is not None and pattern != "radial":
        density = {"spacing_mm": given.spacing_mm}
        shown, source, note = f"every {given.spacing_mm:g} mm", "you", ""
    elif pattern == "radial":
        density, shown, source, note = {"count": DEFAULT_SPOKES}, f"{DEFAULT_SPOKES}", "default", ""
    elif thickness is not None:
        pitch = round(PITCH_IN_THICKNESSES * thickness / 10.0) * 10.0 or 10.0
        density, shown, source = {"spacing_mm": pitch}, f"every {pitch:g} mm", "default"
        note = f"{PITCH_IN_THICKNESSES:g} × the thickness"
    else:
        density, shown, source, note = {}, "", "needed", "how many, or how far apart"
    pitch_now = density.get("spacing_mm")
    if pitch_now is not None and thickness is not None and pitch_now <= thickness:
        problems.append(f"every {pitch_now:g} mm is closer than the ribs are thick")
    density_parts = [
        _number("count", "count", density.get("count"), "", 1.0, 1.0, active="count" in density)
    ]
    if pattern != "radial":
        density_parts.append(
            _number(
                "spacing_mm", "or every", pitch_now, "mm", 5.0, 1.0, active=pitch_now is not None
            )
        )
    slots.append(
        Slot(
            "density",
            SLOTS["density"][0],
            density,
            shown,
            source,
            [],
            note,
            density_parts,
            problems,
        )
    )

    top_kind = given.height_top or "slope"
    height: dict[str, Any] = {"top": top_kind, "cites": []}
    if given.height_mm is not None:
        height["max_mm"] = given.height_mm
    if given.not_above:
        height["not_above"] = list(given.not_above)
    unknown = [r for r in given.not_above if features.get(r) is None]
    problems = [f"the part has no {', '.join(unknown)}"] if unknown else []
    # A rib is at least as tall as its root fillet: a limit lower than that leaves no rib at all.
    least = root if root is not None else 0.0
    if given.height_mm is not None and given.height_mm <= least:
        problems.append(f"at most {given.height_mm:g} mm is no taller than the R{least:g} root")
    if host is not None and normal is not None:
        level = float(np.dot(host.centroid, normal))
        for ref in given.not_above:
            if ref in unknown:
                continue
            _, top = extent(extraction.tess, features.get(ref).face_ids, tuple(normal))
            room = top - level
            if room <= 0.0:
                problems.append(f"{ref} is on the other side of where ribs stand")
            elif room <= least:
                problems.append(
                    f"{ref} reaches {room:.1f} mm past where ribs stand - no room for a rib "
                    f"under it"
                )
    bits = [f"at most {given.height_mm:g} mm"] if given.height_mm else []
    bits += [f"no taller than {', '.join(given.not_above)}"] if given.not_above else []
    bits += ["level top"] if given.height_top == "level" else []
    slots.append(
        Slot(
            "height",
            SLOTS["height"][0],
            height,
            " and ".join(bits) or "each end up to what it meets, the top sloping between",
            "you" if bits or given.height_top else "default",
            list(given.not_above),
            ""
            if bits or given.height_top
            else "each end of a rib as tall as the support it meets there",
            [
                _number("height_mm", "at most", given.height_mm, "mm", 1.0, 1.0),
                _faces_part("not_above", "no taller than", list(given.not_above)),
                _choice("height_top", "top", top_kind, TOPS),
            ],
            problems,
            " and ".join(bits),
        )
    )

    slots.append(
        Slot(
            "thickness",
            SLOTS["thickness"][0],
            thickness,
            "" if thickness is None else f"{thickness:g} mm",
            thickness_source,
            [],
            thickness_note,
            [_number("thickness_mm", "", thickness, "mm", 0.5, 0.5)],
        )
    )
    problems = []
    if root is not None and floor is not None and root < floor - 1e-9:
        problems.append(f"R{root:g} is below the smallest radius the part allows, R{floor:g}")
    slots.append(
        Slot(
            "root_fillet",
            SLOTS["root_fillet"][0],
            root,
            "" if root is None else f"R{root:g}",
            "you" if given.root_fillet_mm else ("default" if root is not None else "needed"),
            [],
            "" if given.root_fillet_mm else "half the thickness, not below the smallest radius",
            [_radius("root_fillet_mm", root)],
            problems,
        )
    )
    problems = []
    if edge and floor is not None and edge < floor - 1e-9:
        problems.append(f"R{edge:g} is below the smallest radius the part allows, R{floor:g}")
    if edge and thickness is not None and edge > thickness / 2.0 + 1e-9:
        problems.append(f"R{edge:g} is more than half of a {thickness:g} mm rib")
    slots.append(
        Slot(
            "edge_round",
            SLOTS["edge_round"][0],
            edge,
            "" if edge is None else ("none" if edge == 0 else f"R{edge:g}"),
            "you"
            if given.edge_round_mm is not None
            else ("drawing" if floor_source == "drawing" and edge == floor else "default"),
            [],
            "" if given.edge_round_mm is not None else "the smallest radius the part allows",
            [_radius("edge_round_mm", edge, none=True)],
            problems,
        )
    )
    slots.append(
        Slot(
            "draft",
            SLOTS["draft"][0],
            draft,
            f"{draft:g}°",
            "you" if given.draft_deg is not None else "default",
            [],
            "" if given.draft_deg is not None else "a cast part releases with a degree or so",
            [
                _choice(
                    "draft_deg",
                    "",
                    draft,
                    {v: f"{v:g}°" for v in sorted({*DRAFTS_DEG, draft})},
                )
            ],
        )
    )
    slots.append(
        Slot(
            "fillet_floor",
            SLOTS["fillet_floor"][0],
            floor,
            "" if floor is None else f"R{floor:g}",
            floor_source,
            [],
            floor_note,
            [_radius("fillet_floor_mm", floor)],
        )
    )
    return Slots(slots)


# --- the card, edited ---------------------------------------------------------------------------


class CardError(ValueError):
    """An edit the card cannot take, and why."""


class Edit(BaseModel):
    """One change to one slot: a value, faces, words, or back to what the part says."""

    slot: str
    field: str | None = None
    """Which of the slot's fields; its first when left out."""
    value: float | str | bool | None = None
    add: list[str] = Field(default_factory=list)
    remove: list[str] = Field(default_factory=list)
    replace: list[str] | None = None
    words: str | None = None
    reset: bool = False
    selected: bool = False
    """The faces came from a selection on the part."""


@dataclass
class Card:
    """One card as the engineer is editing it: what they set, how, and in which words."""

    given: Given = field(default_factory=Given)
    start: list[int] = field(default_factory=list)
    """The faces the card began from."""
    lines: dict[str, str] = field(default_factory=dict)
    """What the engineer set in each slot, as they said it - what a spec quotes."""
    unread: dict[str, str] = field(default_factory=dict)
    """Words typed into a slot that could not be read."""
    typed: set[str] = field(default_factory=set)
    """The slots whose line is words the engineer typed, not a value they picked."""
    via: dict[str, str] = field(default_factory=dict)
    """For each face field the engineer filled: ``selected`` or ``you``."""
    said: list[str] = field(default_factory=list)
    """Every line, in the order it was set."""
    selections: list[list[int]] = field(default_factory=list)
    """Every set of faces put into the card from the part."""
    last: Slots | None = None

    def begin(self, faces: list[int]) -> None:
        """Start again from faces selected on the part."""
        self.given, self.lines, self.unread, self.via, self.last = Given(), {}, {}, {}, None
        self.typed = set()
        self.start = sorted({int(f) for f in faces})
        if self.start:
            self.selections.append(self.start)

    def use(self, faces: list[int], role: str = "auto") -> None:
        """Faces selected on the part, for one role - where ribs stand, what they run between,
        whose holes they keep clear of - or, for ``auto``, as the faces the card starts from,
        keeping everything already set."""
        chosen = sorted({int(f) for f in faces})
        if role == "auto":
            self.start = chosen
            self.selections.append(chosen)
            return
        slot, name = {
            "host": ("host", "host"),
            "supports": ("supports", "supports"),
            "keep_out": ("keep_out", "holes_on"),
        }[role]
        self.edit(Edit(slot=slot, field=name, replace=[f"face:{f}" for f in chosen], selected=True))

    def view(self, slots: Slots, features: FeatureSet) -> dict:
        """The card as the interface draws it: every slot, what the engineer said in it, and
        whether it is ready to make ribs from."""
        rows = []
        for slot in slots.slots:
            row = slot.row()
            row["line"] = self.lines.get(slot.name, "")
            row["typed"] = slot.name in self.typed
            row["unread"] = self.unread.get(slot.name)
            rows.append(row)
        refs = {
            r
            for slot in slots.slots
            for r in [
                *slot.refs,
                *(ref for p in slot.parts for ref in (*p.get("refs", ()), *p.get("shown", ()))),
            ]
        }
        return {
            "started": bool(self.start or self.lines),
            "slots": rows,
            "needed": slots.needed(),
            "problems": slots.problems(),
            "ready": slots.ready(),
            "names": names(features, sorted(refs)),
        }

    def fill(self, extraction: Extraction, exit_along=None) -> Slots:
        slots = infer(extraction, self.given, self.start, exit_along, self.via)
        for key, words in self.unread.items():
            slots.get(key).problems.append(
                f"could not read {words!r} - set it with the controls, or clear the words"
            )
        self.last = slots
        return slots

    def quotes(self) -> list[str]:
        return list(self.lines.values())

    def selected(self) -> list[int]:
        """The faces selected on the part that the card rests on."""
        chosen = set(self.start)
        for name in FACE_FIELDS:
            if self.via.get(name) == "selected":
                refs = getattr(self.given, name)
                for ref in [refs] if isinstance(refs, str) else refs or []:
                    if ref.startswith("face:"):
                        chosen.add(int(ref.split(":", 1)[1]))
        return sorted(chosen)

    def edit(self, edit: Edit) -> None:
        if edit.slot not in SLOTS:
            raise CardError(f"there is no slot {edit.slot!r}")
        label, fields = SLOTS[edit.slot]
        values = self.given.model_dump()

        if edit.reset or (edit.words is not None and not edit.words.strip()):
            for name in fields:
                values[name] = [] if isinstance(values[name], list) else None
                self.via.pop(name, None)
            self.lines.pop(edit.slot, None)
            self.unread.pop(edit.slot, None)
            self.typed.discard(edit.slot)
            self.given = Given.model_validate(values)
            return

        if edit.words is not None:
            words = edit.words.strip()
            read = read_words(edit.slot, words)
            self._say(edit.slot, words)
            self.typed.add(edit.slot)
            if read is None:
                self.unread[edit.slot] = words
                return
            self.unread.pop(edit.slot, None)
            values.update(read)
            for name in read:
                if name in FACE_FIELDS:
                    self.via[name] = "you"
            self.given = _validated(values)
            return

        name = edit.field or fields[0]
        if name not in fields:
            raise CardError(f"{label} has no {name}")
        if name in FACE_FIELDS:
            shown = self._shown(name)
            if edit.replace is not None:
                refs = list(dict.fromkeys(edit.replace))
            else:
                refs = shown + [r for r in edit.add if r not in shown]
                refs = [r for r in refs if r not in edit.remove]
            if name in ONE_FACE:
                values[name] = refs[-1] if refs else None
            else:
                values[name] = refs
            if name == "angle_from":
                # Pointing at the part replaces a number, as a number replaces pointing.
                values["angle_deg"] = None
            self.via[name] = "selected" if edit.selected else "you"
            if edit.selected:
                faces = sorted(
                    {int(r.split(":", 1)[1]) for r in edit.replace or edit.add if _is_face(r)}
                )
                if faces:
                    self.selections.append(faces)
        elif name in ("avoid_holes", "angle_across"):
            values[name] = bool(edit.value)
        elif name == "pattern":
            if edit.value not in PATTERN_NAMES:
                raise CardError(f"a pattern is one of {', '.join(PATTERN_NAMES)}")
            values[name] = edit.value
        elif name == "height_top":
            if edit.value not in TOPS:
                raise CardError(f"a rib's top is one of {', '.join(TOPS)}")
            values[name] = edit.value
        elif name == "spread":
            if edit.value not in SPREADS:
                raise CardError(f"spokes spread one of {', '.join(SPREADS)}")
            values[name] = edit.value
        elif name == "count":
            values["count"] = None if edit.value is None else int(round(float(edit.value)))
            values["spacing_mm"] = None
        elif name == "spacing_mm":
            values["spacing_mm"] = None if edit.value is None else float(edit.value)
            values["count"] = None
        else:
            values[name] = None if edit.value is None else float(edit.value)
            if name == "angle_deg":
                values["angle_from"], values["angle_across"] = None, None
        self.unread.pop(edit.slot, None)
        self.given = _validated(values)
        self._say(edit.slot, _line(edit.slot, self.given))
        self.typed.discard(edit.slot)

    def _shown(self, name: str) -> list[str]:
        """A face field as the card shows it now: what was set, or else what the part gave."""
        value = getattr(self.given, name)
        if value:
            return [value] if isinstance(value, str) else list(value)
        if self.last is None:
            return []
        slot = {
            "host": "host",
            "supports": "supports",
            "holes_on": "keep_out",
            "not_above": "height",
            "centre": "pattern",
            "angle_from": "orientation",
        }[name]
        for part in self.last.get(slot).parts:
            if part.get("field") == name:
                return list(part.get("shown", part["refs"]))
        return []

    def _say(self, slot: str, text: str) -> None:
        line = f"{SLOTS[slot][0]}: {text}"
        self.lines[slot] = line
        if not self.said or self.said[-1] != line:
            self.said.append(line)


def _validated(values: dict) -> Given:
    try:
        return Given.model_validate(values)
    except ValidationError as error:
        problem = error.errors()[0]
        raise CardError(f"{problem['loc'][0]}: {problem['msg']}") from error


def _line(slot: str, given: Given) -> str:
    """What a slot now says, as a line the engineer would have written."""
    if slot in ("host", "supports"):
        return ", ".join(getattr(given, slot)) or "nothing"
    if slot == "keep_out":
        if given.avoid_holes is False:
            return "nothing - ribs may cross holes"
        where = ", ".join(given.holes_on) or "where ribs stand"
        clearance = given.clearance_mm if given.clearance_mm is not None else DEFAULT_CLEARANCE_MM
        return f"holes on {where}, {clearance:g} mm clear"
    if slot == "pattern":
        name = PATTERN_NAMES.get(given.pattern or "", "")
        spokes = given.pattern == "radial"
        return (
            name
            + (f" about {given.centre}" if spokes and given.centre else "")
            + (f", {SPREADS[given.spread]}" if spokes and given.spread else "")
        )
    if slot == "orientation":
        if given.angle_from:
            if given.pattern == "radial":
                return f"toward {given.angle_from}"
            return f"{'square to' if given.angle_across else 'along'} {given.angle_from}"
        return f"{given.angle_deg:g}°" if given.angle_deg is not None else ""
    if slot == "density":
        if given.count is not None:
            return f"{given.count}"
        return f"every {given.spacing_mm:g} mm" if given.spacing_mm is not None else ""
    if slot == "height":
        bits = [f"at most {given.height_mm:g} mm"] if given.height_mm else []
        bits += [f"no taller than {', '.join(given.not_above)}"] if given.not_above else []
        bits += [f"{given.height_top} top"] if given.height_top else []
        return " and ".join(bits) or "up to what they span"
    value = getattr(given, SLOTS[slot][1][0])
    if value is None:
        return ""
    if slot == "thickness":
        return f"{value:g} mm"
    if slot == "draft":
        return f"{value:g}°"
    return "none" if value == 0 else f"R{value:g}"


# --- words ----------------------------------------------------------------------------------------

REFERENCE = re.compile(r"\b[a-z_]+:\d+\b")
NUMBER = re.compile(r"\d+(?:\.\d+)?")
FILLER = {"the", "a", "an", "and", "of", "to", "at", "is", "be", "it", "them", "these", "this"}
FILLER |= {"those", "with", "for", "please", "should", "must", "ribs", "rib", "face", "faces"}
PATTERN_WORDS = {
    "parallel": "parallel",
    "straight": "parallel",
    "lines": "parallel",
    "grid": "grid",
    "square": "grid",
    "squares": "grid",
    "triangle": "triangle",
    "triangles": "triangle",
    "triangular": "triangle",
    "spokes": "radial",
    "spoke": "radial",
    "radial": "radial",
    "radially": "radial",
    "fan": "radial",
}
VOCABULARY = {
    "host": {"on", "where", "stand", "standing", "flat", "floor"},
    "supports": {"between", "from", "run", "runs", "running", "join", "joining", "connect"},
    "keep_out": {
        "keep",
        "clear",
        "holes",
        "hole",
        "on",
        "in",
        "through",
        "by",
        "mm",
        "least",
        "away",
        "from",
        "clearance",
        "gap",
        "margin",
        "any",
        "all",
        "every",
        "none",
        "nothing",
        "may",
        "can",
        "cross",
        "over",
        "allowed",
        "where",
        "stand",
        "no",
    },
    "pattern": {
        *PATTERN_WORDS,
        "about",
        "around",
        "round",
        "from",
        "centred",
        "centered",
        "on",
        "deg",
        "degrees",
        "°",
        "pattern",
        "in",
        "turned",
        "fanned",
        "across",
        "all",
        "way",
        "where",
        "stand",
    },
    "orientation": {
        "deg",
        "degrees",
        "°",
        "angle",
        "turned",
        "rotated",
        "by",
        "along",
        "parallel",
        "square",
        "across",
        "perpendicular",
        "toward",
        "towards",
        "first",
        "spoke",
        "point",
        "points",
        "pointing",
        "running",
        "runs",
        "run",
    },
    "density": {
        "every",
        "apart",
        "mm",
        "pitch",
        "spacing",
        "spaced",
        "spokes",
        "count",
        "on",
        "centres",
        "centers",
    },
    "height": {
        "most",
        "mm",
        "high",
        "tall",
        "max",
        "maximum",
        "up",
        "no",
        "not",
        "taller",
        "higher",
        "than",
        "above",
        "below",
        "under",
        "top",
        "height",
        "or",
        "level",
        "flat",
        "slope",
        "sloped",
        "sloping",
        "each",
        "end",
        "ends",
        "side",
        "sides",
        "follows",
        "follow",
        "on",
    },
    "thickness": {"mm", "thick", "wide", "thickness"},
    "root_fillet": {"r", "mm", "radius", "fillet"},
    "edge_round": {"r", "mm", "radius", "round", "none", "sharp"},
    "draft": {"deg", "degrees", "°", "draft"},
    "fillet_floor": {"r", "mm", "radius", "smallest"},
}


def read_words(slot: str, words: str) -> dict | None:
    """What some words typed into one slot set, as fields of ``Given`` - or None when they say
    something this cannot read: a word outside the slot's vocabulary, or too few or too many
    values. Ids of faces and features are kept exactly as typed."""
    text = re.sub(r"\br(?=\d)", "r ", words.lower())
    refs = REFERENCE.findall(text)
    rest = REFERENCE.sub(" ", text)
    numbers = [float(n) for n in NUMBER.findall(rest)]
    tokens = re.findall(r"[a-z]+|°", NUMBER.sub(" ", rest))
    if any(t not in FILLER and t not in VOCABULARY[slot] for t in tokens):
        return None
    words_used = set(tokens)

    if slot in ("host", "supports"):
        return {slot: refs} if refs and not numbers else None
    if slot == "keep_out":
        if words_used & {"none", "nothing"} or (
            "cross" in words_used and words_used & {"may", "can", "allowed"}
        ):
            return {"avoid_holes": False} if not refs and not numbers else None
        if len(numbers) > 1 or not (refs or numbers):
            return None
        read: dict[str, Any] = {"avoid_holes": True}
        if refs:
            read["holes_on"] = refs
        if numbers:
            read["clearance_mm"] = numbers[0]
        return read
    if slot == "pattern":
        kinds = {PATTERN_WORDS[t] for t in tokens if t in PATTERN_WORDS}
        if len(kinds) > 1:
            kinds.discard("grid")  # "triangle grid" is a triangle grid
        if len(kinds) != 1 or len(refs) > 1 or len(numbers) > 1:
            return None
        (kind,) = kinds
        read = {"pattern": kind}
        if refs:
            if kind != "radial":
                return None
            read["centre"] = refs[0]
        if numbers:
            read["angle_deg"] = numbers[0]
        if kind == "radial" and words_used & {"fan", "fanned", "across"}:
            read["spread"] = "across"
        elif kind == "radial" and "all" in words_used and words_used & {"round", "around"}:
            read["spread"] = "round"
        return read
    if slot == "orientation":
        if refs:
            if len(refs) > 1 or numbers:
                return None
            across = bool(words_used & {"square", "across", "perpendicular"})
            return {"angle_from": refs[0], "angle_across": across, "angle_deg": None}
        if len(numbers) != 1:
            return None
        return {"angle_deg": numbers[0], "angle_from": None, "angle_across": None}
    if slot == "density":
        if len(numbers) != 1 or refs:
            return None
        if words_used & {"every", "apart", "mm", "pitch", "spacing", "spaced", "centres"}:
            return {"spacing_mm": numbers[0], "count": None}
        if numbers[0].is_integer():
            return {"count": int(numbers[0]), "spacing_mm": None}
        return None
    if slot == "height":
        level = bool(words_used & {"level", "flat"})
        slope = bool(words_used & {"slope", "sloped", "sloping", "each", "follows", "follow"})
        if len(numbers) > 1 or (level and slope) or not (refs or numbers or level or slope):
            return None
        read = {}
        if numbers:
            read["height_mm"] = numbers[0]
        if refs:
            read["not_above"] = refs
        if level or slope:
            read["height_top"] = "level" if level else "slope"
        return read
    if refs:
        return None
    name = SLOTS[slot][1][0]
    if slot == "edge_round" and not numbers and words_used & {"none", "sharp"}:
        return {name: 0.0}
    return {name: numbers[0]} if len(numbers) == 1 else None


# --- the controls a slot is drawn with -----------------------------------------------------------


def _faces_part(
    name: str, label: str, refs: list[str], shown: list[str] | None = None, single: bool = False
) -> dict:
    part: dict[str, Any] = {"type": "faces", "field": name, "label": label, "refs": refs}
    if shown is not None and shown != refs:
        part["shown"] = shown
    if single:
        part["single"] = True
    return part


def _number(name, label, value, unit, step, least, active: bool = True) -> dict:
    return {
        "type": "number",
        "field": name,
        "label": label,
        "value": value,
        "unit": unit,
        "step": step,
        "min": least,
        "active": active,
    }


def _choice(name: str, label: str, value, options: dict) -> dict:
    return {
        "type": "choice",
        "field": name,
        "label": label,
        "value": value,
        "options": [{"value": v, "label": text} for v, text in options.items()],
    }


def _radius(name: str, value: float | None, none: bool = False) -> dict:
    offered = sorted({*RADII_MM, *([value] if value else []), *([0.0] if none else [])})
    return _choice(name, "", value, {v: "none" if v == 0 else f"R{v:g}" for v in offered})


def _faces_shown(refs: list[str], merged: Feature | None) -> str:
    if not refs:
        return ""
    if merged is not None:
        return f"{', '.join(refs[:3])}{'…' if len(refs) > 3 else ''} ({merged.area_mm2:,.0f} mm²)"
    return ", ".join(refs)


def _is_face(ref: str) -> bool:
    return ref.startswith("face:") and ref.split(":", 1)[1].isdigit()


def names(features: FeatureSet, refs: list[str]) -> dict[str, str]:
    """A few words for each ref, for the card to show beside it."""
    out = {}
    for ref in refs:
        feature = features.get(ref)
        if feature is None:
            out[ref] = "not on the part"
            continue
        if feature.kind == FeatureKind.FACE:
            face = features.faces[feature.face_ids[0]]
            text = f"{face.surface_type}, {face.area:,.0f} mm²"
            if face.diameter_mm is not None and face.surface_type in ("cylinder", "cone"):
                text += f", Ø{face.diameter_mm:.1f}"
        elif feature.kind == FeatureKind.HOLE:
            text = f"hole, Ø{feature.diameter_mm:.1f}" if feature.diameter_mm else "hole"
        else:
            text = f"{feature.kind}, {feature.area_mm2:,.0f} mm², {len(feature.face_ids)} faces"
        out[ref] = text
    return out


# --- reading the part ---------------------------------------------------------------------------


def _host_among(features: FeatureSet, flat: list[int], selected: list[int]) -> Feature:
    """Of the flat areas selected, the one the other selected faces rise from - walls standing on
    it, bosses square to it - and the larger when two are equal. Not simply the largest: a tall
    wall selected beside a floor can be the bigger face. Returned whole: every face of its
    connected flat area."""
    groups: dict[str, Feature] = {}
    for face in flat:
        group = next(
            (f for f in features.containing(face) if f.kind == FeatureKind.PLANAR_GROUP),
            None,
        ) or features.get(f"face:{face}")
        assert group is not None
        groups.setdefault(group.id, group)
    best, best_score = None, (-1, -1.0)
    for group in groups.values():
        normal = np.asarray(group.normal, dtype=float)
        others = [f for f in selected if f not in group.face_ids]
        rising = sum(1 for f in others if _rises(features.faces[f], normal))
        if (rising, group.area_mm2) > best_score:
            best, best_score = group, (rising, group.area_mm2)
    assert best is not None
    return best


def _walls_around(
    atlas, host_faces: set[int], normal: np.ndarray, hole_faces: set[int], level: float
) -> list[int]:
    """What stands up round where ribs stand - walls, bosses, bores - reached across whatever
    blends into it at its edge: a fillet of any shape, a chamfer. Only on the side ribs stand on:
    past a round on the outer edge of a floor is the outside of the part, falling away below it.
    Holes are not walls, and nothing is looked for past a hole."""
    tolerance = max(atlas.diagonal_mm * 1e-4, 1e-3)
    found: set[int] = set()
    seen = set(host_faces)
    frontier = [(n, 0) for f in sorted(host_faces) for n in atlas.faces[f].neighbours]
    while frontier:
        face_id, depth = frontier.pop(0)
        if face_id in seen:
            continue
        seen.add(face_id)
        face = atlas.faces[face_id]
        if face_id in hole_faces or float(np.dot(face.centroid, normal)) - level < tolerance:
            continue
        if _rises(face, normal):
            found.add(face_id)
        elif depth < BLEND_DEPTH and _blends(face, normal):
            frontier.extend((n, depth + 1) for n in face.neighbours)
    return sorted(found)


def _rises(face, normal: np.ndarray) -> bool:
    """Whether a face stands up from a surface facing ``normal``, as a wall or a boss does."""
    if face.surface_type == "plane" and face.normal is not None:
        return abs(float(np.dot(face.normal, normal))) < STANDS_UP
    if face.surface_type in ("cylinder", "cone") and face.axis is not None:
        return abs(float(np.dot(face.axis, normal))) > 0.7
    if face.surface_type == "bspline" and face.flatness > 0.9:
        return abs(float(np.dot(face.facing, normal))) < STANDS_UP
    return False


def _blends(face, normal: np.ndarray) -> bool:
    """Whether a face is a way across from where ribs stand to something else: a fillet, a round,
    a chamfer - not a step to another flat area."""
    if face.surface_type in ("torus", "sphere", "bspline"):
        return True
    if face.surface_type in ("cylinder", "cone"):
        return True
    if face.surface_type == "plane" and face.normal is not None:
        return abs(float(np.dot(face.normal, normal))) < 0.98
    return False


def _host_points(extraction: Extraction, host: Feature, most: int = 4000) -> np.ndarray:
    tess = extraction.tess
    mine = np.isin(tess.face_id, list(host.face_ids))
    points = tess.vertices[np.unique(tess.triangles[mine])]
    if len(points) > most:
        points = points[np.linspace(0, len(points) - 1, most).astype(int)]
    return points


def _centres(features, support_refs, normal, hole_faces, most: int = 8) -> list[tuple[str, str]]:
    """What spokes could turn about: the bosses and bores among what ribs run between, standing
    square to where they stand, largest first. A boss or bore goes a good way round its axis, with
    the rest of it if the CAD split it; a rounded wall corner or a fillet goes a quarter of the way,
    and is not offered."""
    tolerance = max(features.diagonal_mm * AXIS_DISTANCE_TOL_FRACTION, 1e-3)
    found: dict[str, tuple[float, str]] = {}
    for ref in support_refs:
        feature = features.get(ref)
        if feature is None:
            continue
        for face_id in feature.face_ids:
            face = features.faces[face_id]
            if face_id in hole_faces or face.axis is None or face.radius_mm is None:
                continue
            if face.surface_type not in ("cylinder", "cone"):
                continue
            if abs(float(np.dot(face.axis, normal))) < 0.9:
                continue
            if wrap_deg(turning_with(features.faces, face_id, tolerance)) < ROUND_ENOUGH_DEG:
                continue
            kind = "bore" if face.concave else "boss"
            label = f"{ref} · {kind}, Ø{2.0 * face.radius_mm:.0f}"
            if ref not in found or face.radius_mm > found[ref][0]:
                found[ref] = (face.radius_mm, label)
    ranked = sorted(found.items(), key=lambda item: -item[1][0])
    return [(ref, label) for ref, (_, label) in ranked[:most]]


def _round_centre(extraction, host, normal, support_refs, hole_faces) -> str | None:
    """What spokes turn about: the largest round thing among the supports - a boss or a bore,
    going round its axis with the rest of it if the CAD split it - standing square to where ribs
    stand, with where they stand round more than half of it. Never the ring wall a floor is
    inside, never a fillet in a corner, never a hole."""
    if host is None or normal is None:
        return None
    features = extraction.features
    tolerance = max(features.diagonal_mm * AXIS_DISTANCE_TOL_FRACTION, 1e-3)
    points = _host_points(extraction, host)
    best, best_radius = None, 0.0
    for ref in support_refs:
        feature = features.get(ref)
        if feature is None:
            continue
        for face_id in feature.face_ids:
            face = features.faces[face_id]
            if face_id in hole_faces or face.axis is None or face.radius_mm is None:
                continue
            if face.surface_type not in ("cylinder", "cone") or face.radius_mm <= best_radius:
                continue
            if abs(float(np.dot(face.axis, normal))) < 0.9:
                continue
            whole = turning_with(features.faces, face_id, tolerance)
            if wrap_deg(whole) >= HOLE_WRAP_DEG and _surrounds(points, face):
                best, best_radius = ref, face.radius_mm
    return best


def _surrounds(points: np.ndarray, face) -> bool:
    """Whether points lie round more than half of a face of revolution, outside it: a floor round
    a boss standing in it, or beside a bore it fans out from - not a floor inside a ring wall."""
    axis = np.asarray(face.axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    offset = points - np.asarray(face.axis_point, dtype=float)
    radial = offset - np.outer(offset @ axis, axis)
    distance = np.linalg.norm(radial, axis=1)
    if len(points) < 3 or float(np.median(distance)) <= face.radius_mm:
        return False
    reference = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = reference - (reference @ axis) * axis
    u = u / np.linalg.norm(u)
    v = np.cross(axis, u)
    angles = np.sort(np.degrees(np.arctan2(radial @ v, radial @ u)) % 360.0)
    gaps = np.diff(np.concatenate([angles, [angles[0] + 360.0]]))
    return float(gaps.max()) < 180.0


def _holes_on(features: FeatureSet, refs: list[str]) -> tuple[list[str], list[str]]:
    """The holes through the faces of these refs, and the refs with no hole through them."""
    holes: list[str] = []
    themselves: list[str] = []
    for ref in refs:
        faces = set(features.get(ref).face_ids)
        through = [h.id for h in features.of_kind(FeatureKind.HOLE) if faces & set(h.opens_onto)]
        holes += [h for h in through if h not in holes]
        if not through:
            themselves.append(ref)
    return holes, themselves


def _angle_from(extraction: Extraction, host: Feature, ref: str, centre: str | None):
    """An angle on where ribs stand taken from something on the part: for spokes, toward it from
    what they turn about; for straight ribs, the way it runs - a wall's line along the floor, a
    fillet's axis, or else its longest direction. None when there is no such thing on the part."""
    from .placement import _axis_point

    features = extraction.features
    feature = features.get(ref)
    if feature is None:
        return None
    frame = _frame(host)
    if centre is not None:
        about = features.get(centre)
        if about is None:
            return None
        origin = frame.to_plane(np.asarray(_axis_point(features, about)).reshape(1, 3))[0]
        target = frame.to_plane(np.asarray(feature.centroid).reshape(1, 3))[0]
        towards = target - origin
        return float(math.degrees(math.atan2(towards[1], towards[0]))) % 360.0
    runs = None
    flat = feature.kind == FeatureKind.PLANAR_GROUP or feature.metrics.get("flat") == 1.0
    if flat and feature.normal is not None:
        runs = np.cross(np.asarray(feature.normal, dtype=float), frame.normal)
    elif feature.kind == FeatureKind.FACE and feature.normal is not None:
        runs = np.asarray(feature.normal, dtype=float)  # a face of revolution: its axis
    if runs is not None:
        seen = np.array([runs @ frame.e1, runs @ frame.e2])
        if float(np.linalg.norm(seen)) > 1e-6:
            return float(math.degrees(math.atan2(seen[1], seen[0]))) % 180.0
    return _long_axis_deg(extraction, feature)


def _main_wall(extraction: Extraction, host: Feature, support_refs: list[str]) -> str | None:
    """The wall straight ribs are set out from when nothing else says: of the flat faces standing
    round where ribs stand, the one that runs along it the furthest."""
    features = extraction.features
    frame = _frame(host)
    best, longest = None, 0.0
    for ref in support_refs:
        feature = features.get(ref)
        if feature is None or feature.normal is None:
            continue
        if not (feature.kind == FeatureKind.PLANAR_GROUP or feature.metrics.get("flat") == 1.0):
            continue
        runs = np.cross(np.asarray(feature.normal, dtype=float), frame.normal)
        if float(np.linalg.norm(runs)) < 0.5:
            continue  # nearly parallel to where ribs stand: a step, not a wall
        runs = runs / float(np.linalg.norm(runs))
        low, high = extent(extraction.tess, feature.face_ids, tuple(runs))
        if high - low > longest:
            best, longest = ref, high - low
    return best


def _axis_word(direction: np.ndarray) -> str:
    """A direction by the part's own axes - ``+X``, ``-Y`` - or its components if it has none."""
    direction = np.asarray(direction, dtype=float)
    biggest = int(np.argmax(np.abs(direction)))
    if abs(direction[biggest]) > 0.99:
        return f"{'+' if direction[biggest] > 0 else '-'}{'XYZ'[biggest]}"
    return "(" + ", ".join(f"{c:.2f}" for c in direction) + ")"


def _long_axis_deg(extraction: Extraction, host: Feature) -> float:
    """The angle of the host's longest direction, in the frame placement draws paths in."""
    frame = _frame(host)
    points = frame.to_plane(_host_points(extraction, host))
    if len(points) < 3:
        return 0.0
    centred = points - points.mean(axis=0)
    _, vectors = np.linalg.eigh(np.cov(centred.T))
    major = vectors[:, -1]
    return float(math.degrees(math.atan2(major[1], major[0]))) % 180.0


def _thickness(extraction, host, normal, given, exit_along):
    if given.thickness_mm is not None:
        return given.thickness_mm, "you", ""
    if host is None or normal is None or exit_along is None:
        return None, "needed", "how thick"
    tess = extraction.tess
    mine = np.flatnonzero(np.isin(tess.face_id, list(host.face_ids)))
    corners = tess.vertices[tess.triangles[mine]]
    areas = np.linalg.norm(
        np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1
    )
    # On the face, not at its centroid: the middle of an annulus is its hole.
    start = corners[int(np.argmax(areas))].mean(axis=0) - normal * 0.05
    through = exit_along(start, -normal)
    if not through:
        return None, "needed", "how thick - the plate under it could not be measured"
    rib = round(RIB_TO_PLATE * through * 2.0) / 2.0
    return rib, "default", f"{RIB_TO_PLATE:g} × the {through:.1f} mm plate it stands on"


RADII = re.compile(r"RADII\s*R\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


def _fillet_floor(extraction, given):
    if given.fillet_floor_mm is not None:
        return given.fillet_floor_mm, "you", ""
    drawing = extraction.drawing
    if drawing is not None:
        for page, line in getattr(drawing, "lines", []):
            match = RADII.search(line)
            if match:
                around = line[max(0, match.start() - 40) : match.end() + 20].strip()
                return float(match.group(1)), "drawing", f"page {page}: …{around}…"
    return None, "needed", "the smallest radius the part allows"
