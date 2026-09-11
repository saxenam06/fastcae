"""A design space, and the designs made in it.

**Opened once.** The corrected baseline, its contour, and a window for every approved zone are what
every design is made from, and none of them depends on the design - so they are built once, kept on
disk, and a design only pays for its own ribs.

**A design is its settings.** For each zone, a formation and its lever values. Its digest is those
settings, the baseline's key, the rules and the code, so the same settings on the same part give the
same bytes - and a test holds it to that.

**Zones and protected areas are decisions.** They are proposed by the system and approved by a
person, and both are written in ``project.json``; a zone nobody approved has no levers and cannot be
designed in.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field

import numpy as np

from .. import cache
from ..extract import Extraction
from ..project import Project
from .checks import Finding, Rules, check
from .compose import CODE_COMPOSE, Composition, compose
from .corrections import corrected
from .field import Field, field_for
from .formations import FORMATIONS, build
from .surface import Surface, recontour, surface_for
from .zones import Zone, window_for

CODE = (
    "generate/designs.py",
    "generate/zones.py",
    "generate/formations.py",
    "generate/ribs.py",
    "generate/checks.py",
    *CODE_COMPOSE,
)

# What a stored window depends on: the code that builds one, and nothing that merely reads it. A
# change to a check must not throw away minutes of distance computation.
WINDOW_CODE = (*CODE_COMPOSE, "generate/zones.py")

# How a design's outcome is read off its findings: the worst of them.
_RANK = {"pass": 0, "warn": 1, "reject": 2}

# Which detected features are protected when a person approves protection without naming others.
PROTECTED_KINDS = ("bore", "hole_pattern", "controlled")


# --- decisions in project.json -----------------------------------------------------------------


def save_proposals(project: Project, zones: list[Zone]) -> None:
    """Write proposed zones, keeping any approval already given to a zone with the same id."""
    was = {z["id"]: z.get("status") for z in project.data().get("zones", [])}
    project.write_data(
        "zones",
        [{**z.to_dict(), "status": was.get(z.id, "proposed") or "proposed"} for z in zones],
    )


def approve_zone(project: Project, zone_id: str, approved: bool) -> None:
    zones = project.data().get("zones", [])
    if not any(z["id"] == zone_id for z in zones):
        raise ValueError(f"no zone {zone_id!r} has been proposed")
    for zone in zones:
        if zone["id"] == zone_id:
            zone["status"] = "approved" if approved else "proposed"
    project.write_data("zones", zones)


def zones_of(project: Project, status: str | None = None) -> list[Zone]:
    return [
        Zone.from_dict(z)
        for z in project.data().get("zones", [])
        if status is None or z.get("status") == status
    ]


def protection(project: Project) -> dict:
    """What is protected, and whether a person has approved it. Proposed until they have."""
    return {
        "kinds": list(PROTECTED_KINDS),
        "clearance_mm": 5.0,
        "status": "proposed",
        **project.data().get("protected", {}),
    }


def approve_protection(project: Project, approved: bool, clearance_mm: float | None = None) -> None:
    current = protection(project)
    if clearance_mm is not None:
        current["clearance_mm"] = float(clearance_mm)
    current["status"] = "approved" if approved else "proposed"
    project.write_data("protected", current)


def protected_faces(extraction: Extraction, kinds: list[str]) -> set[int]:
    faces: set[int] = set()
    if extraction.features is not None:
        for feature in extraction.features.features.values():
            if str(feature.kind) in kinds:
                faces |= set(feature.face_ids)
    if "controlled" in kinds:
        faces |= extraction.controlled_face_ids()
    return faces


# --- the design space --------------------------------------------------------------------------


@dataclass
class Design:
    """One design: its settings, its geometry, what the checks found, and what it measures."""

    settings: dict
    digest: str
    base: Field
    composition: Composition
    surface: Surface
    findings: list[Finding]
    stats: dict
    ribs: list = field(default_factory=list)

    @property
    def outcome(self) -> str:
        return max((f.outcome for f in self.findings), key=_RANK.__getitem__, default="pass")

    def added_surface(self) -> Surface:
        """Only the surfaces that are new: ribs and their fillets, not the part they stand on.

        What the viewer draws over the part it already has. A triangle is new when its middle
        stands off the baseline's surface; the part's own surface near a rib is re-contoured too,
        but it lies where it always did.
        """
        surface = self.surface
        changed = self.composition.changed
        if not changed.size:
            return _subset(surface, np.zeros(surface.n_triangles, dtype=bool))
        centres = self.base.grid.centres(changed)
        lo, hi = centres.min(axis=0), centres.max(axis=0)
        middle = surface.vertices[surface.triangles].mean(axis=1)
        near = np.all((middle >= lo) & (middle <= hi), axis=1)
        off = np.zeros(surface.n_triangles, dtype=bool)
        off[near] = np.abs(self.base.sample(middle[near])) > 0.75 * self.base.grid.spacing_mm
        return _subset(surface, off)


@dataclass
class DesignSpace:
    """A project opened for designing. See the module note."""

    project: Project
    extraction: Extraction
    base: Field
    surface: Surface
    zones: list[Zone]
    windows: dict
    rules: Rules
    radius_mm: float
    corrections: list = field(default_factory=list)
    density: dict = field(default_factory=dict)

    @staticmethod
    def open(
        project: Project,
        extraction: Extraction,
        spacing_mm: float = 2.5,
        radius_mm: float | None = None,
    ) -> DesignSpace:
        rules = Rules(**project.data().get("rules", {}))
        radius = rules.root_fillet_mm if radius_mm is None else radius_mm
        tess = extraction.tess
        if tess is None:
            raise ValueError("no geometry was read")

        raw, _ = field_for(project.root, tess, extraction.cad_digest, spacing_mm=spacing_mm)
        base, applied = corrected(project, raw)
        surface, _ = surface_for(project.root, base, base.key, face_ids_from=tess)

        zones = zones_of(project, "approved")
        guard = protection(project)
        faces = (
            protected_faces(extraction, guard["kinds"]) if guard["status"] == "approved" else set()
        )
        windows = {}
        for zone in zones:
            key = cache.key_for(
                base.key,
                json.dumps(zone.to_dict(), sort_keys=True),
                f"{radius:.6f}",
                f"{guard['clearance_mm']:.6f}",
                ",".join(map(str, sorted(faces))),
                code=WINDOW_CODE,
            )
            windows[zone.id], _ = cache.memoise(
                cache.entry(project.root, "window", key),
                lambda zone=zone: window_for(
                    base,
                    tess,
                    zone,
                    radius,
                    protected_faces=faces,
                    clearance_mm=guard["clearance_mm"],
                ),
            )
        return DesignSpace(
            project=project,
            extraction=extraction,
            base=base,
            surface=surface,
            zones=zones,
            windows=windows,
            rules=rules,
            radius_mm=radius,
            corrections=applied,
            density=project.data().get("density", {}),
        )

    def generate(self, settings: dict) -> Design:
        """The design these settings describe: ribs composed, contoured, checked and measured."""
        started = time.perf_counter()
        by_id = {z.id: z for z in self.zones}
        unknown = [zone_id for zone_id in settings if zone_id not in by_id]
        if unknown:
            raise ValueError(f"{', '.join(unknown)}: not an approved zone")

        field_now = self.base
        changed = []
        parts = []
        all_ribs = []
        dropped = 0
        for zone_id in sorted(settings):
            chosen = dict(settings[zone_id])
            name = chosen.pop("formation", None)
            if name not in FORMATIONS:
                raise ValueError(f"{zone_id}: {name!r} is not a formation")
            made = build(
                name,
                by_id[zone_id].region,
                chosen,
                draft_deg=self.rules.draft_used_deg,
                edge_round_mm=self.rules.edge_round_mm,
            )
            ribs = list(made.ribs)
            dropped += made.dropped
            composition = compose(field_now, self.windows[zone_id], ribs, self.radius_mm)
            field_now = composition.field
            changed.append(composition.changed)
            parts.append((zone_id, composition, ribs))
            all_ribs += ribs
        composed_at = time.perf_counter()

        every = np.unique(np.concatenate(changed)) if changed else np.empty(0, dtype=np.int64)
        whole = Composition(field=field_now, changed=every)
        surface = recontour(self.surface, field_now, every, face_ids_from=self.extraction.tess)
        contoured_at = time.perf_counter()

        findings = _worst(
            [
                check(self.base, self.windows[zone_id], composition, ribs, surface, self.rules)
                for zone_id, composition, ribs in parts
            ]
        )
        checked_at = time.perf_counter()

        density = float(self.density.get("g_cm3", 0.0)) or None
        fillet = next((f.value for f in findings if f.check == "root fillet"), None)
        stats = {
            "ribs": len(all_ribs),
            "dropped": dropped,
            "volume_cm3": surface.volume_mm3 / 1e3,
            "base_volume_cm3": self.surface.volume_mm3 / 1e3,
            "added_cm3": (surface.volume_mm3 - self.surface.volume_mm3) / 1e3,
            "mass_kg": None if density is None else surface.volume_mm3 / 1e3 * density / 1e3,
            "base_mass_kg": None
            if density is None
            else self.surface.volume_mm3 / 1e3 * density / 1e3,
            "density": self.density,
            "smallest_fillet_mm": fillet,
            "seconds": {
                "compose": composed_at - started,
                "contour": contoured_at - composed_at,
                "check": checked_at - contoured_at,
            },
        }
        return Design(
            settings=settings,
            digest=self.digest(settings),
            base=self.base,
            composition=whole,
            surface=surface,
            findings=findings,
            stats=stats,
            ribs=all_ribs,
        )

    def digest(self, settings: dict) -> str:
        """What a design is: its settings, the baseline, the rules and the code."""
        snapped = {
            zone_id: {"formation": s["formation"], **FORMATIONS[s["formation"]].snap(s)}
            for zone_id, s in settings.items()
            if s.get("formation") in FORMATIONS
        }
        text = json.dumps(
            {
                "settings": snapped,
                "base": self.base.key,
                "rules": repr(self.rules),
                "radius": self.radius_mm,
            },
            sort_keys=True,
        )
        return "sha256:" + hashlib.sha256((text + cache.code_digest(CODE)).encode()).hexdigest()


def _worst(per_zone: list[list[Finding]]) -> list[Finding]:
    """One finding per check across zones: the worst, and where it was."""
    out: dict[str, Finding] = {}
    for findings in per_zone:
        for finding in findings:
            held = out.get(finding.check)
            if held is None or _RANK[finding.outcome] > _RANK[held.outcome]:
                out[finding.check] = finding
    return list(out.values())


def _subset(surface: Surface, keep: np.ndarray) -> Surface:
    triangles = surface.triangles[keep]
    used, index = np.unique(triangles, return_inverse=True)
    return Surface(
        vertices=surface.vertices[used],
        triangles=index.reshape(-1, 3).astype(np.int32),
        face_id=surface.face_id[keep],
        spacing_mm=surface.spacing_mm,
    )
