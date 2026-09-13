"""Screening: whether a design placed from a study is worth building, in milliseconds.

Go places thousands of designs; building one - composing its field and contouring it - takes a
minute. So every design is screened on what placing it already knows, and only one that passes is
kept. What screening holds a design to, each a rule with where it comes from:

- **every block made something** - ribs where the study asks for ribs, holes where it asks for
  holes. A design without them is not a design of the study.
- **a rib is no thicker than the floor it stands on allows** - the wall it ends on is held to that
  as it is placed, padded or not; the floor under it is held to it here, as the design leaves it
  after moving its faces. Thicken the floor, or thin the ribs.
- **ribs leave room for the mould between them** - the clear gap between two ribs standing in the
  open, at least twice the thinner, as the built design is checked.
- **no wall thinned below the least it may be** - the study's, or the material's when that is more.
- **holes a ligament of metal from the ribs** they keep clear of, measured on what was placed - and
  through no rib at all.

**What it weighs.** Each rib as the plate it is, each pad, each hole, each face moved by its area:
an estimate to compare designs by, the base part weighed exactly. Mass is the material's density
times that - the design's own, or the default the catalogue names.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .. import knowledge
from ..features import FeatureSet
from ..spec import HoleSet, MaterialChoice, Offset, Placement
from .checks import Rules, _gaps
from .field import Field
from .placement import Drilled, Placed
from .ribs import Rib

# Every check screening makes, what it holds a design to, and where the rule comes from - for the
# campaign to show, and to switch off for one campaign.
CHECKS = (
    ("ribs placed", "ribs where the study asks for ribs", "the study"),
    ("holes placed", "holes where the study asks for holes", "the study"),
    (
        "rib on floor",
        "a rib no thicker than 0.8 of the floor it stands on, as the design leaves it",
        "foundry rule of thumb (assumed)",
    ),
    (
        "holes clear of ribs",
        "a plate thickness of metal between each hole and the ribs it keeps clear of",
        "assumed",
    ),
    (
        "root gap",
        "a clear gap of twice the thinner rib between ribs in the open, within a block and between",
        "room for the sand between them (assumed)",
    ),
    (
        "wall kept",
        "no wall thinned below its least - the block's, or its material's",
        "the material's standard, or 8 mm (assumed)",
    ),
)


@dataclass
class Screened:
    """A design's screening: pass, warn or reject, what said so, and what it weighs."""

    outcome: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def rejected(self) -> list[dict[str, Any]]:
        return [f for f in self.findings if f["outcome"] == "reject"]


def measure_walls(
    extraction: Any, exit_along: Any, offsets: list[Offset]
) -> dict[str, float | None]:
    """The metal under each block of faces moved, measured through the thinnest of its faces on
    the part as it is - what thinning it takes from."""
    from .slots import _through

    out: dict[str, float | None] = {}
    for offset in offsets:
        walls = [w for w in (_through(extraction, exit_along, ref) for ref in offset.faces) if w]
        out[offset.id] = min(walls) if walls else None
    return out


def raised_floors(features: FeatureSet, placed: dict) -> list[Offset]:
    """The floors a design thickens for ribs too thick for them, as faces moved: each block's
    floor by what it asked, on top of what blocks placed before it asked of the same floor."""
    return [
        Offset(
            id=f"{block}-floor",
            faces=[f"face:{face}" for face in result.raised_faces],
            offset_mm=result.raised_mm,
            blend_mm=20.0,
        )
        for block, result in placed.items()
        if isinstance(result, Placed) and result.raised_mm
    ]


def face_offsets(features: FeatureSet, offsets: list[Offset]) -> dict[int, float]:
    """How far each face of the part moves, by face: every block that moves it, added up."""
    moved: dict[int, float] = {}
    for offset in offsets:
        for ref in offset.faces:
            feature = features.get(ref)
            if feature is None:
                continue
            for face in feature.face_ids:
                moved[face] = moved.get(face, 0.0) + offset.offset_mm
    return moved


def screen(
    features: FeatureSet,
    base: Field,
    placements: list[Placement],
    holes: list[HoleSet],
    offsets: list[Offset],
    material: MaterialChoice | None,
    placed: dict[str, Placed | Drilled],
    walls: dict[str, float | None],
    base_volume_mm3: float,
    off: frozenset[str] | set[str] = frozenset(),
) -> Screened:
    """A design screened: ``placed`` is what placing it made, block by block; ``walls`` the metal
    under each block of faces moved, as measured on the part; ``off`` the checks a campaign
    switched off, by name, which neither pass nor fail it."""
    findings: list[dict[str, Any]] = []
    moved = face_offsets(features, offsets)
    chosen = knowledge.material(material.material) if material is not None else None
    least_of_material = float(chosen["min_wall_mm"]) if chosen else 0.0

    def say(check: str, outcome: str, reason: str, rule: str, block: str | None = None) -> None:
        findings.append(
            {"check": check, "outcome": outcome, "reason": reason, "rule": rule, "block": block}
        )

    # Every block made something.
    for placement in placements:
        result = placed[placement.id]
        assert isinstance(result, Placed)
        if not result.ribs:
            why = result.problems[0] if result.problems else result.tally()
            say("ribs placed", "reject", f"{placement.id} placed no rib: {why}", "ribs where the "
                "study asks for ribs", placement.id)  # fmt: skip
    for hole_set in holes:
        result = placed[hole_set.id]
        assert isinstance(result, Drilled)
        if not result.holes:
            say("holes placed", "reject", f"{hole_set.id} cut no hole: {result.tally()}",
                "holes where the study asks for holes", hole_set.id)  # fmt: skip

    # A rib no thicker than the floor under it allows, as the design leaves the floor.
    for placement in placements:
        result = placed[placement.id]
        assert isinstance(result, Placed)
        if not placement.host or not placement.rib_to_wall or not result.ribs:
            continue
        host = [features.get(ref) for ref in placement.host]
        faces = {f for h in host if h is not None for f in h.face_ids}
        lift = min((moved[f] for f in faces if f in moved), default=0.0)
        floors = [s["floor_mm"] for s in result.spans if s.get("floor_mm")]
        if not floors:
            continue
        # Thickened for these ribs, and for ribs of other blocks on the same floor.
        raised = sum(
            r.raised_mm
            for r in placed.values()
            if isinstance(r, Placed) and set(r.raised_faces) & faces
        )
        floor = min(floors) + lift + raised
        most = placement.rib_to_wall * floor
        thickness = placement.section.thickness_mm
        rule = f"a rib no thicker than {placement.rib_to_wall:g} of the floor it stands on"
        if thickness > most + 0.5:
            say("rib on floor", "reject", f"{placement.id}: {thickness:g} mm ribs on a "
                f"{floor:.0f} mm floor - at most {most:.1f} mm there; thicken the floor or thin "
                "the ribs", rule, placement.id)  # fmt: skip
        else:
            say("rib on floor", "pass", f"{placement.id}: {thickness:g} mm ribs on a "
                f"{floor:.0f} mm floor", rule, placement.id)  # fmt: skip

    # Holes a ligament of metal from the ribs they keep clear of - measured on what was placed -
    # and through no rib of any block.
    for hole_set in holes:
        result = placed[hole_set.id]
        assert isinstance(result, Drilled)
        if not result.holes:
            continue
        named = [
            rib
            for other in hole_set.clear_of
            if isinstance(placed.get(other), Placed)
            for rib in placed[other].made()
        ]
        rest = [
            rib
            for other, r in placed.items()
            if isinstance(r, Placed) and other not in hole_set.clear_of
            for rib in r.made()
        ]
        ligament = max(hole_set.ligament_mm, hole_set.clear_of_mm)
        rule = f"{ligament:g} mm of metal between a hole and a rib"
        nearest = result.clear_of(named)
        if nearest is not None and nearest < ligament - 0.5:
            say("holes clear of ribs", "reject", f"{hole_set.id}: a hole {nearest:.1f} mm from a "
                "rib", rule, hole_set.id)  # fmt: skip
        else:
            shown = "no rib beside a hole" if nearest is None else f"nearest rib {nearest:.0f} mm"
            say("holes clear of ribs", "pass", f"{hole_set.id}: {shown}", rule, hole_set.id)
        through = result.clear_of(rest)
        if through is not None and through < 0.0:
            say("holes clear of ribs", "warn", f"{hole_set.id}: a hole cuts into a rib no rule "
                "keeps it clear of", rule, hole_set.id)  # fmt: skip

    # Room for the mould between ribs: within each block - its own spacing against its own
    # thickness, which the block alone decides - then between blocks, which only together do.
    radii = {
        rib: placement.section.root_fillet_mm
        for placement in placements
        for rib in placed[placement.id].ribs
    }
    failed = False
    for placement in placements:
        own = placed[placement.id].ribs
        if len(own) > 1:
            gap = _gaps(base, list(own), Rules(), radii)
            say("root gap", gap.outcome, f"{placement.id}: {gap.reason}", gap.rule, placement.id)
            failed |= gap.outcome == "reject"
    if not failed and len({p.id for p in placements if placed[p.id].ribs}) > 1:
        gap = _gaps(base, list(radii), Rules(), radii)
        say("root gap", gap.outcome, f"between blocks: {gap.reason}", gap.rule)

    # No wall thinned below the least it may be.
    for offset in offsets:
        wall = walls.get(offset.id)
        if offset.offset_mm >= 0.0 or wall is None:
            continue
        least = max(offset.min_wall_mm, least_of_material)
        left = wall + offset.offset_mm
        rule = f"no wall thinned below {least:g} mm"
        if left < least - 1e-6:
            say("wall kept", "reject", f"{offset.id} leaves {left:.1f} mm of the {wall:.1f} mm "
                "wall", rule, offset.id)  # fmt: skip
        else:
            say("wall kept", "pass", f"{offset.id} leaves {left:.1f} mm", rule, offset.id)

    findings = [f for f in findings if f["check"] not in off]
    stats = _weighed(features, placed, offsets, chosen, base_volume_mm3)
    order = {"reject": 0, "warn": 1, "pass": 2}
    worst = min((f["outcome"] for f in findings), key=order.get, default="pass")
    return Screened(outcome=worst, findings=findings, stats=stats)


def _weighed(
    features: FeatureSet,
    placed: dict[str, Placed | Drilled],
    offsets: list[Offset],
    material: dict[str, Any] | None,
    base_volume_mm3: float,
) -> dict[str, Any]:
    """What a design adds and takes away, by what does it, and what it weighs."""
    ribs = [rib for r in placed.values() if isinstance(r, Placed) for rib in r.ribs]
    pads = [pad for r in placed.values() if isinstance(r, Placed) for pad in r.pads]
    drilled = [r for r in placed.values() if isinstance(r, Drilled)]
    rib_mm3 = sum(_plate_volume(rib) for rib in ribs)
    # A pad stands half in the wall it thickens.
    pad_mm3 = sum(_plate_volume(pad) / 2.0 for pad in pads)
    hole_mm3 = sum(
        math.pi * hole.radius_mm**2 * (result.plate_mm or 0.0)
        for result in drilled
        for hole in result.holes
    )
    moved_mm3 = 0.0
    for offset in [*offsets, *raised_floors(features, placed)]:
        area = sum(
            features.get(ref).area_mm2 for ref in offset.faces if features.get(ref) is not None
        )
        moved_mm3 += area * offset.offset_mm
    added = rib_mm3 + pad_mm3 + moved_mm3 - hole_mm3
    if material is None:
        material = knowledge.material(knowledge.default_material()[0])
    density = float((material or {}).get("density_kg_m3", 0.0))
    return {
        "ribs": len(ribs),
        "pads": len(pads),
        "holes": sum(len(r.holes) for r in drilled),
        "rib_cm3": round(rib_mm3 / 1e3, 1),
        "pad_cm3": round(pad_mm3 / 1e3, 1),
        "hole_cm3": round(hole_mm3 / 1e3, 1),
        "moved_cm3": round(moved_mm3 / 1e3, 1),
        "added_cm3": round(added / 1e3, 1),
        "material": (material or {}).get("id"),
        "mass_kg": round((base_volume_mm3 + added) * density * 1e-9, 1),
        "added_kg": round(added * density * 1e-9, 2),
    }


def _plate_volume(rib: Rib) -> float:
    """A rib as the plate it is: its line's length, times its mean height, times its thickness - a
    T's flange besides. Fillets and draft aside: an estimate to compare designs by."""
    line = np.asarray(rib.end, dtype=float) - np.asarray(rib.start, dtype=float)
    up = np.asarray(rib.pull, dtype=float)
    up = up / np.linalg.norm(up)
    length = float(np.linalg.norm(line - (line @ up) * up))
    height = sum(rib.heights) / 2.0
    volume = length * height * rib.thickness_mm
    if rib.tee:
        volume += length * (rib.flange_width_mm - rib.thickness_mm) * rib.flange_thickness_mm
    return volume
