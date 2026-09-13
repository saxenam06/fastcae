"""A design space, and the designs made in it.

**Opened once.** The baseline, its contour, and a window for every approved zone are what
every design is made from, and none of them depends on the design - so they are built once, kept on
disk, and a design only pays for its own ribs.

**A design is its settings.** For each zone, a formation and its lever values. Its digest is those
settings, the baseline's key, the rules and the code, so the same settings on the same part give the
same bytes - and a test holds it to that.

**Zones and protected areas are decisions.** Both are written in ``project.json``: a zone comes
from the engineer's intent, protected areas are proposed from detected features, and a person
approves each. A zone nobody approved has no levers and cannot be designed in.
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
from .field import Field, field_for
from .formations import FORMATIONS, build
from .surface import SLOTS, Surface, recontour, surface_for
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


def approve_zone(project: Project, zone_id: str, approved: bool) -> None:
    zones = project.data().get("zones", [])
    if not any(z["id"] == zone_id for z in zones):
        raise ValueError(f"no zone {zone_id!r} in this project")
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
    part_surface: Surface | None = None
    """The part's own surface, contoured from ``base``: what this design's is compared with."""

    @property
    def outcome(self) -> str:
        return max((f.outcome for f in self.findings), key=_RANK.__getitem__, default="pass")

    def changed_surface(self) -> tuple[Surface, np.ndarray]:
        """The surfaces this design changes, down to where they meet the part, and how far each of
        their vertices stands off it.

        What the viewer draws over the part it already has. A vertex has moved when the part's own
        surface has none like it - none with its key, or one somewhere else - and every triangle
        with a moved vertex is drawn. So what is drawn ends exactly on the part's own surface, and
        a rib's fillet runs all the way down to it instead of stopping short of it.

        ``standing`` is per vertex: 0 on the part, 1 half a cell or more off it. It is how far the
        field moved around the vertex, read between its cell's eight samples, so it is nothing
        where no sample changed and rises smoothly up a fillet; the viewer blends the part's colour
        into the design's by it, and the join reads as a join rather than as a jagged edge.
        """
        surface, part = self.surface, self.part_surface
        if part is None or part.vertex_key is None or surface.vertex_key is None:
            raise ValueError("this design carries no surface of the part to compare with")
        same = np.clip(np.searchsorted(part.vertex_key, surface.vertex_key), 0, part.n_vertices - 1)
        moved = (part.vertex_key[same] != surface.vertex_key) | np.any(
            part.vertices[same] != surface.vertices, axis=1
        )
        standing = np.zeros(surface.n_vertices)
        spacing = self.base.grid.spacing_mm
        standing[moved] = np.clip(np.abs(self._field_moved(moved)) / (0.5 * spacing), 0.0, 1.0)
        changed, used = _subset(surface, moved[surface.triangles].any(axis=1))
        return changed, standing[used]

    def _field_moved(self, which: np.ndarray) -> np.ndarray:
        """How far the field moved at these vertices of the design's surface: the change at the
        eight samples of the cell each belongs to, weighted by where in the cell it sits."""
        grid = self.base.grid
        shape = np.asarray(grid.shape)
        cell = np.stack(
            np.unravel_index(self.surface.vertex_key[which] // SLOTS, tuple(shape - 1)), axis=1
        )
        corner_zero = np.asarray(grid.origin) + cell * grid.spacing_mm
        across = np.clip((self.surface.vertices[which] - corner_zero) / grid.spacing_mm, 0.0, 1.0)
        out = np.zeros(cell.shape[0])
        for corner in np.ndindex(2, 2, 2):
            sample = np.ravel_multi_index((cell + corner).T, tuple(shape))
            weight = np.prod(np.where(np.asarray(corner) == 1, across, 1.0 - across), axis=1)
            out += weight * (self.composition.field.at(sample) - self.base.at(sample))
        return out


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
    density: dict = field(default_factory=dict)

    @staticmethod
    def open(
        project: Project,
        extraction: Extraction,
        spacing_mm: float | None = None,
        radius_mm: float | None = None,
    ) -> DesignSpace:
        rules = Rules(**project.data().get("rules", {}))
        if rules.missing():
            raise ValueError(
                "not set for this part: " + ", ".join(rules.missing()).replace("_mm", "")
            )
        radius = rules.root_fillet_mm if radius_mm is None else radius_mm
        # Four voxels across the smallest radius a design must hold, unless a grid is asked for.
        spacing_mm = radius / 4.0 if spacing_mm is None else spacing_mm
        tess = extraction.tess
        if tess is None:
            raise ValueError("no geometry was read")

        base, _ = field_for(project.root, tess, extraction.cad_digest, spacing_mm=spacing_mm)
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
            part_surface=self.surface,
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


def _subset(surface: Surface, keep: np.ndarray) -> tuple[Surface, np.ndarray]:
    """The kept triangles as a surface of their own, and which of the whole's vertices it uses."""
    triangles = surface.triangles[keep]
    used, index = np.unique(triangles, return_inverse=True)
    kept = Surface(
        vertices=surface.vertices[used],
        triangles=index.reshape(-1, 3).astype(np.int32),
        face_id=surface.face_id[keep],
        spacing_mm=surface.spacing_mm,
    )
    return kept, used
