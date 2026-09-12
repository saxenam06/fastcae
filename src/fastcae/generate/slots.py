"""Reading ribs that stand on a floor off the part: everything such a group needs, filled round
what was given.

Given what the ribs stand on, and whatever else the engineer's words fixed, :func:`infer` fills
every slot a group of ribs on a floor needs in one pass - what rises round the floor to end on, the
holes through it to keep clear of, what spokes could turn about, the wall straight ribs are set out
from, the plate under them for the thickness, the drawing's smallest radius - from the geometry and
the drawing, or with a default that says it is one. What nothing can settle is marked needed, what
cannot be right is marked as a problem. :meth:`Slots.study` turns the slots into a block of the
study: what was given fixed, the rest ranges round what was read.

Every slot says where its value came from:

- ``you``, ``selected`` or ``words`` - given: by hand, by selecting, in words the agent read
- ``drawing`` - the drawing states it, with the page and the literal text
- ``measured`` - measured on the part
- ``default`` - a conventional starting value, not confirmed
- ``needed`` - only the engineer can say
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, Field

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
from ..study import layout_of
from .placement import _frame, host_of

Pattern = Literal["parallel", "grid", "triangle", "radial"]

# Defaults, each a conventional starting point and labelled as one wherever it is shown.
DEFAULT_CLEARANCE_MM = 5.0
DEFAULT_DRAFT_DEG = 1.0
RIB_TO_PLATE = 0.8
# How many of the largest things ribs end on count as the walls a rib is sized by.
WALLS = 6
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
# Where a slot's value can come from when somebody said it: set on the card, selected on the part,
# or read from the engineer's words by the agent.
ASKED = ("you", "selected", "words")

# The free settings as the engineer would name them.
SETTING_LABELS = {
    "generator": "patterns",
    "centre": "spokes about",
    "spread": "spokes",
    "angle_deg": "angle",
    "count": "count",
    "spacing_mm": "spacing",
    "thickness_mm": "thickness",
    "root_fillet_mm": "root fillet",
    "edge_round_mm": "edge round",
    "draft_deg": "draft",
    "top": "top",
    "height_fraction": "height",
    "section": "section",
    "flange_width_mm": "flange width",
    "flange_thickness_mm": "flange thickness",
}
# The part's interfaces, which the platform closes on every study.
CLOSED = ("interface", "datum")


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
    basis: dict[str, Any] = field(default_factory=dict)
    """What the slot was filled from that a study needs besides the value: the plate measured
    under a thickness, what spokes could turn about, which of its fields the engineer set."""

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
            layout = layout_of(
                "radial",
                angle,
                count=int(density["count"]),
                centre=self.get("pattern").refs[0],
                spread=self._spread(),
            )
        elif "count" in density:
            layout = layout_of(pattern, angle, count=int(density["count"]))
        else:
            layout = layout_of(pattern, angle, spacing=density["spacing_mm"])
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

    def _spread(self) -> str:
        return next(
            (p["value"] for p in self.get("pattern").parts if p.get("field") == "spread"),
            "across",
        )

    def study(self, cites: list[str]) -> dict[str, Any]:
        """These slots as a study's entries: one block of ribs whose suggested point is the card, so
        the block at that point is the placement the card makes. What the engineer set is fixed;
        what they left open varies over a range read from the part, marked as nobody's choice; the
        card's rules become constraints with their strength and source. ``cites`` is what the
        engineer's settings rest on. Refused while anything is needed or wrong."""
        if not self.ready():
            raise ValueError("the card is not ready: " + "; ".join(self.needed() + self.problems()))

        def asked(name: str) -> bool:
            return self.get(name).source in ASKED

        def locked(name: str, value: Any, unit: str = "") -> dict[str, Any]:
            source = self.get(name).source if asked(name) else "you"
            if isinstance(value, str):
                return {"options": [value], "suggested": value, "source": source, "cites": cites}
            return {
                "low": value,
                "high": value,
                "step": 1.0,
                "unit": unit,
                "suggested": value,
                "source": source,
                "cites": cites,
            }

        pattern_slot = self.get("pattern")
        pattern, density = pattern_slot.value, self.get("density").value
        thickness = float(self.get("thickness").value)
        floor = self.get("fillet_floor").value or 0.0
        offered = list(pattern_slot.basis.get("offered", []))
        free: dict[str, dict[str, Any]] = {}

        # Which patterns - every one the floor allows, unless the engineer chose one.
        if asked("pattern"):
            free["generator"] = locked("pattern", pattern)
        else:
            kinds = ["parallel", "grid", "triangle", *(["radial"] if offered else [])]
            if pattern not in kinds:
                kinds.append(pattern)
            free["generator"] = {
                "options": kinds,
                "weights": [1.0] * len(kinds),
                "suggested": pattern,
                "basis": "every pattern this floor allows; the card's first",
            }
        spokes_possible = "radial" in free["generator"]["options"]
        if spokes_possible:
            centre = pattern_slot.refs[0] if pattern_slot.refs else offered[0]
            if pattern_slot.basis.get("centre_set"):
                free["centre"] = locked("pattern", centre)
            else:
                free["centre"] = {
                    "options": list(dict.fromkeys([centre, *offered])),
                    "suggested": centre,
                    "source": "measured",
                    "basis": pattern_slot.note or "round things standing round where ribs stand",
                }
            spread = self._spread() if pattern == "radial" else "across"
            if pattern_slot.basis.get("spread_set"):
                free["spread"] = locked("pattern", spread)
            else:
                free["spread"] = {"options": ["across", "round"], "suggested": spread}

        # Which way, and how many.
        orientation = self.get("orientation")
        angle = float(orientation.value or 0.0)
        if asked("orientation"):
            free["angle_deg"] = locked("orientation", angle, "°")
        else:
            top = 359.0 if pattern == "radial" else 179.0
            free["angle_deg"] = {
                "low": min(0.0, angle),
                "high": max(top, angle),
                "step": 15.0,
                "unit": "°",
                "suggested": angle,
                "source": "measured" if orientation.source == "measured" else "default",
                "basis": orientation.note,
            }
        pitch = round(8.0 * thickness / 10.0) * 10.0 or 10.0
        spacing_range = {
            "low": max(10.0, math.floor(5.0 * thickness / 10.0) * 10.0),
            "high": math.ceil(16.0 * thickness / 10.0) * 10.0,
            "step": 10.0,
            "unit": "mm",
            "basis": "5 to 16 thicknesses apart",
        }
        count_range = {"low": 4, "high": 16, "step": 1, "basis": "4 to 16 ribs"}
        if "count" in density:
            count = int(density["count"])
            if asked("density"):
                free["count"] = locked("density", count)
            else:
                free["count"] = {**count_range, "suggested": count}
                free["spacing_mm"] = {**spacing_range, "suggested": pitch}
        else:
            spacing = float(density["spacing_mm"])
            if asked("density"):
                free["spacing_mm"] = locked("density", spacing, "mm")
            else:
                free["spacing_mm"] = {**spacing_range, "suggested": spacing}
            if spokes_possible:
                free["count"] = {**count_range, "suggested": DEFAULT_SPOKES}

        # The section, and how tall.
        plate = self.get("thickness").basis.get("plate_mm")
        sized_by = self.get("thickness").basis.get("sized_by", "plate it stands on")
        if asked("thickness"):
            free["thickness_mm"] = locked("thickness", thickness, "mm")
        elif plate:
            free["thickness_mm"] = {
                "low": min(thickness, round(0.6 * plate * 2.0) / 2.0),
                "high": max(thickness, round(1.0 * plate * 2.0) / 2.0),
                "step": 1.0,
                "unit": "mm",
                "suggested": thickness,
                "source": "measured",
                "basis": f"0.6 to 1.0 of the {plate:.1f} mm {sized_by}",
            }
        else:
            free["thickness_mm"] = {
                "low": 0.5 * thickness,
                "high": 1.25 * thickness,
                "step": 0.5,
                "unit": "mm",
                "suggested": thickness,
            }
        for name, slot, most in (
            ("root_fillet_mm", "root_fillet", thickness),
            ("edge_round_mm", "edge_round", thickness / 2.0),
        ):
            value = float(self.get(slot).value)
            if asked(slot):
                free[name] = locked(slot, value, "mm")
                continue
            radii = sorted({*(r for r in RADII_MM if floor <= r <= most), value})
            free[name] = {
                "options": radii,
                "suggested": value,
                "unit": "mm",
                "source": "drawing" if self.get(slot).source == "drawing" else "default",
                "basis": f"from the smallest radius the part allows to {most:g} mm",
            }
        draft = float(self.get("draft").value)
        free["draft_deg"] = (
            locked("draft", draft, "°")
            if asked("draft")
            else {
                "options": sorted({0.5, 1.0, 1.5, 2.0, 3.0, draft}),
                "suggested": draft,
                "unit": "°",
                "basis": self.get("draft").note,
            }
        )
        height = self.get("height")
        top_kind = height.value.get("top", "slope")
        free["top"] = (
            locked("height", top_kind)
            if height.basis.get("top_set")
            else {"options": ["slope", "level"], "suggested": top_kind}
        )
        free["height_fraction"] = {
            "low": 0.5,
            "high": 1.0,
            "step": 0.1,
            "suggested": 1.0,
            "basis": "from half to all of what each end meets",
        }

        constraints: list[dict[str, Any]] = []
        keep = self.get("keep_out")
        for kept in keep.value or []:
            chosen = asked("keep_out")
            constraints.append(
                {
                    "kind": "keep_clear_of",
                    "refs": list(kept["features"]),
                    "params": {"clearance_mm": kept["clearance_mm"]},
                    "strength": "hard" if chosen else "assumed",
                    "source": keep.source if chosen else "default",
                    "text": keep.shown,
                    "basis": keep.note,
                    "cites": cites if chosen else [],
                }
            )
        said_by = height.source if asked("height") else "you"
        if height.value.get("not_above"):
            constraints.append(
                {
                    "kind": "not_above",
                    "refs": list(height.value["not_above"]),
                    "source": said_by,
                    "cites": cites,
                }
            )
        if height.value.get("max_mm"):
            constraints.append(
                {
                    "kind": "height_at_most",
                    "params": {"mm": height.value["max_mm"]},
                    "source": said_by,
                    "cites": cites,
                }
            )
        constraints.append({"kind": "within_what_it_meets", "strength": "assumed"})
        if self.get("supports").refs:
            constraints.append({"kind": "ends_on", "strength": "assumed"})
        reference = orientation.basis.get("from")
        if reference and not orientation.basis.get("spokes"):
            constraints.append(
                {
                    "kind": "square_to" if orientation.basis.get("across") else "along",
                    "refs": [reference],
                    "source": orientation.source if asked("orientation") else "you",
                    "cites": cites,
                }
            )
        smallest = self.get("fillet_floor")
        if smallest.value is not None:
            from_drawing = smallest.source == "drawing"
            constraints.append(
                {
                    "kind": "smallest_radius",
                    "params": {"radius_mm": smallest.value},
                    "source": "drawing" if from_drawing else "you",
                    "basis": smallest.note if from_drawing else "",
                    "cites": [] if from_drawing else cites,
                }
            )
        for constraint in constraints:
            constraint["by"] = "part"
        host = self.get("host").refs
        return {
            "blocks": [
                {
                    "id": "b1",
                    "add": "ribs",
                    "where": {"support": list(host), "anchors": list(self.get("supports").refs)},
                    "free": free,
                    "cites": cites,
                }
            ],
            "constraints": constraints,
            "pull": {
                "along": host[0],
                "basis": "the normal of where ribs stand, which the card stands them along",
            },
            "measured": self.measured(),
        }

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
    start_via: str = "selected",
) -> Slots:
    """Every slot, filled. ``start`` is the faces the card began from, sorted here into where ribs
    stand and what they run between; ``start_via`` says whether they were selected or named in
    words. ``exit_along(point, direction)`` measures through the metal. ``via`` says how the
    engineer filled each face field: by selecting, by typing, or in words the agent read."""
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
            chosen = list(group.face_ids)
            # Other flat faces selected in the same plane are where ribs stand too: two halves
            # of a floor, not a floor and something to run to.
            normal_of = np.asarray(group.normal, dtype=float)
            level_of = float(np.dot(group.centroid, normal_of))
            tolerance = max(features.diagonal_mm * 1e-4, 1e-3)
            for f in flat:
                face = faces[f]
                if f in chosen or face.normal is None:
                    continue
                if float(np.dot(face.normal, normal_of)) > math.cos(math.radians(1.0)) and (
                    abs(float(np.dot(face.centroid, normal_of)) - level_of) < tolerance
                ):
                    chosen.append(f)
            host_refs = [f"face:{f}" for f in chosen]
            host_source = start_via
            host_note = "the flat area the rest of the faces rise from"
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
    # What stands up round where ribs stand, past any blend at its foot: what they run between
    # unless the engineer says, and where anything else round - a centre for spokes - is looked for.
    standing: list[str] = []
    if host is not None and normal is not None:
        standing = [
            f"face:{f}"
            for f in _walls_around(
                atlas, host_faces, normal, hole_faces, float(np.dot(host.centroid, normal))
            )
        ]
    if given.supports:
        support_refs, source = list(given.supports), said("supports")
    else:
        # The rest of the selection, less any flat face that does not stand up from where ribs
        # stand: a rib has nothing to meet there.
        rest = [
            f
            for f in start
            if f not in host_faces
            and f not in hole_faces
            and not (
                normal is not None
                and faces[f].surface_type == "plane"
                and not _rises(faces[f], normal)
            )
        ]
        if rest:
            support_refs, source = [f"face:{f}" for f in rest], start_via
        elif standing:
            support_refs, source = list(standing), "measured"
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
    elif host is not None and normal is not None:
        # A rib ends against something standing up from where it stands. A face level with the
        # floor, or below it, has nothing for a rib to meet.
        level = float(np.dot(host.centroid, normal))
        tolerance = max(features.diagonal_mm * 1e-4, 0.5)
        flat_out = [
            r
            for r in support_refs
            if r not in unknown
            and extent(extraction.tess, features.get(r).face_ids, tuple(normal))[1] - level
            <= tolerance
        ]
        if flat_out:
            problems.append(
                f"{', '.join(flat_out)} does not stand up from where ribs stand - a rib cannot "
                "end on it"
            )
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
        plural = "hole" if len(holes) == 1 else "holes"
        keep_shown = f"{len(holes)} {plural} on {where}, {clearance:g} mm clear"
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
    thickness, thickness_source, thickness_note, sized = _thickness(
        extraction, host, normal, given, exit_along, support_refs
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
    # What spokes could turn about: round things standing round where ribs stand, whether or not
    # they were named to run between.
    offered = (
        _centres(features, list(dict.fromkeys([*support_refs, *standing])), normal, hole_faces)
        if normal is not None
        else []
    )
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
            basis={
                "offered": [ref for ref, _ in offered],
                "centre_set": given.centre is not None,
                "spread_set": given.spread is not None,
            },
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
            basis={"from": given.angle_from, "across": bool(across), "spokes": spokes},
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
            basis={"top_set": given.height_top is not None},
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
            basis={"plate_mm": sized[0], "sized_by": sized[1]} if sized and sized[0] else {},
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


def _thickness(extraction, host, normal, given, exit_along, supports=()):
    """The rib's thickness, where it came from, why - and the metal it is sized by, if any: the
    plate under it, or - thinner, as under a bearing's thick housing - the thinnest of the walls it
    meets: a rib is no thicker than a wall it joins. Only the largest of what it ends on count as
    walls, not every sliver of a fillet."""
    through = _plate(extraction, host, normal, exit_along)
    features = extraction.features
    largest = sorted(
        (ref for ref in supports if features.get(ref) is not None),
        key=lambda ref: -features.get(ref).area_mm2,
    )[:WALLS]
    walls = [w for w in (_through(extraction, exit_along, ref) for ref in largest) if w]
    wall = min(walls) if walls else None
    sized, by = through, "plate it stands on"
    if wall is not None and (through is None or wall < through):
        sized, by = wall, "walls it meets"
    if given.thickness_mm is not None:
        return given.thickness_mm, "you", "", (sized, by)
    if host is None or normal is None or exit_along is None:
        return None, "needed", "how thick", None
    if sized is None:
        return None, "needed", "how thick - the plate under it could not be measured", None
    rib = round(RIB_TO_PLATE * sized * 2.0) / 2.0
    return rib, "default", f"{RIB_TO_PLATE:g} × the {sized:.1f} mm {by}", (sized, by)


def _through(extraction, exit_along, ref: str) -> float | None:
    """How thick the metal is under a face or a feature: a ray into the metal from the middle of
    its largest facet, square to it - through a plate, a wall, the rim of a boss or a bore."""
    features, tess = extraction.features, extraction.tess
    feature = features.get(ref) if features is not None else None
    if feature is None or exit_along is None:
        return None
    mine = np.flatnonzero(np.isin(tess.face_id, list(feature.face_ids)))
    if not mine.size:
        return None
    corners = tess.vertices[tess.triangles[mine]]
    cross = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    largest = int(np.argmax(np.linalg.norm(cross, axis=1)))
    centre = corners[largest].mean(axis=0)
    face = features.faces[int(tess.face_id[mine[largest]])]
    if face.surface_type == "plane" and face.normal is not None:
        inward = -np.asarray(face.normal, dtype=float)
    elif face.axis is not None and face.axis_point is not None:
        direction = np.asarray(face.axis, dtype=float)
        offset = centre - np.asarray(face.axis_point, dtype=float)
        radial = offset - (offset @ direction) * direction
        radial = radial / max(float(np.linalg.norm(radial)), 1e-12)
        inward = radial if face.concave else -radial
    else:
        inward = -cross[largest] / max(float(np.linalg.norm(cross[largest])), 1e-12)
    found = exit_along(centre + inward * 0.05, inward)
    return round(float(found), 2) if found else None


def _plate(extraction, host, normal, exit_along) -> float | None:
    """How thick the plate where ribs stand is, by a ray through it from its largest facet."""
    if host is None or normal is None or exit_along is None:
        return None
    tess = extraction.tess
    mine = np.flatnonzero(np.isin(tess.face_id, list(host.face_ids)))
    corners = tess.vertices[tess.triangles[mine]]
    areas = np.linalg.norm(
        np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1
    )
    # On the face, not at its centroid: the middle of an annulus is its hole.
    start = corners[int(np.argmax(areas))].mean(axis=0) - normal * 0.05
    through = exit_along(start, -normal)
    return float(through) if through else None


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
