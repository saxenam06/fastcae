"""Designs made from a spec: the engineer's placements turned into ribs, composed, checked.

**Opened once per fidelity.** A part is opened for designing at a grid: *full* is a quarter of the
smallest root fillet the spec asks for, *preview* twice that. Nothing else differs between them -
the same placement, the same constraints, the same checks - and every design says which it is.

**A design is a spec version and lever values.** Levers are paths into the spec
(``placements.p1.layout.count``); a design applies them to a copy of the version and makes that.

**The verdict has two parts.** *Your constraints*: each placement's keep-outs, heights and
supports, verified on the ribs actually placed and citing the words they came from. *Checks*: what
the platform holds every rib to, whether or not anyone asked.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import dataclass, field

import numpy as np

from .. import cache
from ..extract import Extraction
from ..project import Project
from ..spec import Placement, Version
from .checks import Finding, Rules, check
from .compose import CODE_COMPOSE, Composition, compose, margin_for, window_between
from .designs import Design, _worst
from .field import Field, field_for
from .placement import Placed, place_all
from .surface import Surface, recontour, surface_for

FIDELITIES = ("preview", "full")
CODE = (
    *CODE_COMPOSE,
    "generate/placement.py",
    "generate/intent.py",
    "generate/checks.py",
    "spec.py",
)


class IntentError(ValueError):
    """A design that cannot be made from this spec, and why."""


@dataclass
class Opened:
    """A part opened for designing at one fidelity."""

    project: Project
    extraction: Extraction
    fidelity: str
    base: Field
    surface: Surface

    @staticmethod
    def open(
        project: Project,
        extraction: Extraction,
        version: Version,
        fidelity: str,
        radius: float | None = None,
    ) -> Opened:
        """The part opened at the grid ``fidelity`` asks for: set by the smallest root fillet the
        placements have - or by ``radius``, to open it once for many designs of one study."""
        if fidelity not in FIDELITIES:
            raise IntentError(f"fidelity is one of {', '.join(FIDELITIES)}")
        if extraction.tess is None:
            raise IntentError("no geometry was read")
        smallest = min(p.section.root_fillet_mm for p in version.placements)
        full = (radius or smallest) / 4.0
        spacing = full if fidelity == "full" else 2.0 * full
        base, _ = field_for(
            project.root, extraction.tess, extraction.cad_digest, spacing_mm=spacing
        )
        surface, _ = surface_for(project.root, base, base.key, face_ids_from=extraction.tess)
        return Opened(project, extraction, fidelity, base, surface)


@dataclass
class Made:
    """A design made from a spec, with everything the verdict and the viewer need."""

    design: Design
    placed: dict[str, Placed] = field(default_factory=dict)
    version: int = 0
    levers: dict[str, float] = field(default_factory=dict)
    fidelity: str = "preview"


def make(opened: Opened, version: Version, levers: dict[str, float] | None = None) -> Made:
    """The design ``version`` describes with ``levers`` applied. See the module note."""
    started = time.perf_counter()
    levers = dict(levers or {})
    placements = _apply(version, levers)
    extraction = opened.extraction
    assert extraction.features is not None and extraction.atlas is not None
    assert extraction.tess is not None
    rules = _rules(version)

    # Each placement after those whose ribs it keeps clear of.
    placed = place_all(
        opened.base, extraction.features, extraction.atlas, extraction.tess, placements
    )
    ribs = [rib for result in placed.values() for rib in result.ribs]
    radius = min(p.section.root_fillet_mm for p in placements)

    constraints = [f for p in placements for f in _constraints(p, placed[p.id])]
    if not ribs:
        reasons = "; ".join(_why_none(placed[p.id]) for p in placements)
        composition = Composition(field=opened.base, changed=np.empty(0, dtype=np.int64))
        findings = [
            *constraints,
            Finding("ribs placed", "reject", f"no rib could be placed: {reasons}", "", False),
        ]
        surface = opened.surface
    else:
        window = _window(opened, placements, placed, ribs, radius)
        composition = compose(opened.base, window, ribs, radius)
        surface = recontour(
            opened.surface, composition.field, composition.changed, face_ids_from=extraction.tess
        )
        findings = [*constraints, *check(opened.base, window, composition, ribs, surface, rules)]

    settings = {"spec_version": version.version, "levers": levers, "fidelity": opened.fidelity}
    design = Design(
        settings=settings,
        digest=_digest(opened, version, levers),
        base=opened.base,
        composition=composition,
        surface=surface,
        findings=_worst([findings]),
        stats={
            "ribs": len(ribs),
            "fidelity": opened.fidelity,
            "spacing_mm": opened.base.grid.spacing_mm,
            "volume_cm3": surface.volume_mm3 / 1e3,
            "base_volume_cm3": opened.surface.volume_mm3 / 1e3,
            "added_cm3": (surface.volume_mm3 - opened.surface.volume_mm3) / 1e3,
            "seconds": round(time.perf_counter() - started, 1),
        },
        ribs=ribs,
    )
    return Made(design, placed, version.version, levers, opened.fidelity)


# --- levers ------------------------------------------------------------------------------------


def _apply(version: Version, levers: dict[str, float]) -> list[Placement]:
    """The version's placements with lever values put in at their paths."""
    known = {lever.path: lever for lever in version.levers}
    data = {"placements": {p.id: p.model_dump() for p in version.placements}}
    for path, value in levers.items():
        lever = known.get(path)
        if lever is None:
            raise IntentError(f"{path} is not a lever of this spec")
        if not lever.low <= value <= lever.high:
            raise IntentError(f"{path} = {value} is outside {lever.low} to {lever.high}")
        _set(data, path, value)
    return [Placement.model_validate(p) for p in data["placements"].values()]


def _set(data: dict, path: str, value: float) -> None:
    """Put ``value`` at a dotted path; ``[n]`` indexes a list."""
    keys = []
    for part in path.split("."):
        while "[" in part:
            head, rest = part.split("[", 1)
            if head:
                keys.append(head)
            index, part = rest.split("]", 1)
            keys.append(int(index))
        if part:
            keys.append(part)
    target = data
    for key in keys[:-1]:
        target = target[key]
    last = keys[-1]
    if isinstance(target, dict) and last not in target:
        raise IntentError(f"{path} names nothing in the spec")
    current = target[last]
    target[last] = int(round(value)) if isinstance(current, int) else float(value)


# --- rules and the window ----------------------------------------------------------------------


def _rules(version: Version) -> Rules:
    """The checks' thresholds: the part's own from the spec, the rest general and marked so."""
    first = version.placements[0].section
    given = dict(version.rules)
    thickness = given.get("thickness_mm", [first.thickness_mm, first.thickness_mm])
    rules = Rules(
        thickness_mm=(float(thickness[0]), float(thickness[1])),
        edge_round_mm=first.edge_round_mm,
        root_fillet_mm=first.root_fillet_mm,
        fillet_floor_mm=given.get("fillet_floor_mm"),
        draft_used_deg=first.draft_deg,
        **{k: given[k] for k in ("rib_to_wall", "root_gap", "thick_spot") if k in given},
    )
    if rules.missing():
        raise IntentError(
            "the spec does not set " + ", ".join(rules.missing()) + " - ask the engineer"
        )
    return rules


def _window(opened: Opened, placements, placed, ribs, radius: float):
    """The part's exact distance round the ribs, and the keep-outs to hold, kept for reuse."""
    base, tess = opened.base, opened.extraction.tess
    features = opened.extraction.features
    lo = np.min([rib.bounds()[0] for rib in ribs], axis=0)
    hi = np.max([rib.bounds()[1] for rib in ribs], axis=0)
    # Snapped outward so small changes to the ribs reuse one window.
    snap = 8.0 * base.grid.spacing_mm
    lo, hi = np.floor(lo / snap) * snap, np.ceil(hi / snap) * snap
    held = sorted({k["feature"] for result in placed.values() for k in result.keep_outs})
    faces = {f for ref in held for f in features.get(ref).face_ids}
    clearance = max((k.clearance_mm for p in placements for k in p.keep_out), default=0.0)
    key = cache.key_for(
        base.key,
        ",".join(f"{v:.3f}" for v in (*lo, *hi)),
        f"{radius:.6f}",
        f"{clearance:.6f}",
        ",".join(map(str, sorted(faces))),
        code=CODE_COMPOSE,
    )
    window, _ = cache.memoise(
        cache.entry(opened.project.root, "window", key),
        lambda: window_between(
            base,
            tess,
            lo,
            hi,
            margin_for(base, radius),
            protected_faces=faces,
            clearance_mm=clearance,
        ),
    )
    return window


# --- your constraints ----------------------------------------------------------------------------


def _constraints(placement: Placement, placed: Placed) -> list[Finding]:
    """Each constraint of a placement, verified on the ribs it actually made."""
    out = []
    spans = placed.spans
    label = f"placement {placement.id}"

    for index, keep in enumerate(placement.keep_out):
        what = ", ".join([*keep.features, *(f"every {k} on the host" for k in keep.kinds)])
        # Each rule against its own keep-outs: a rib near a face kept 0 mm clear of is not held to
        # the clearance the holes ask for.
        gaps = [
            s["clear_by_rule"][index]
            for s in spans
            if s.get("clear_by_rule") and s["clear_by_rule"][index] is not None
        ]
        rule = f"{keep.clearance_mm:g} mm clear of {what}"
        if not spans:
            outcome, reason = "pass", "no rib to check"
        elif not gaps:
            outcome, reason = "pass", "nothing to keep clear of on the host"
        else:
            nearest = min(gaps)
            ok = nearest >= keep.clearance_mm - 1e-6
            outcome = "pass" if ok else "reject"
            count = sum(1 for row in placed.keep_outs if row.get("rule", index) == index)
            reason = f"nearest {nearest:.1f} mm, {count} keep-outs on the host"
        # One finding per rule: the verdict keeps one finding per check name.
        name = "keep out" if index == 0 else f"keep out {index + 1}"
        out.append(
            Finding(
                f"{name} ({label})",
                outcome,
                reason,
                rule,
                False,
                section="constraint",
                cites=tuple(keep.cites or placement.cites),
            )
        )

    if spans:
        tallest = max(s["height_mm"] for s in spans)
        limits = sorted({s["limited_by"] for s in spans})
        out.append(
            Finding(
                f"height ({label})",
                "pass",
                f"tallest {tallest:.1f} mm above the host, each rib held to " + ", ".join(limits),
                "no taller than the supports it spans"
                + (
                    f" or {', '.join(placement.height.not_above)}"
                    if placement.height.not_above
                    else ""
                )
                + (f" or {placement.height.max_mm:g} mm" if placement.height.max_mm else ""),
                False,
                value=tallest,
                section="constraint",
                cites=tuple(placement.height.cites or placement.cites),
            )
        )

    count = len(placement.supports)
    ends = (
        f"between two of the {count} faces named to run between"
        if count > 1
        else (f"from {placement.supports[0]}" if count else "to the edges of where it stands")
    )
    out.append(
        Finding(
            f"supports ({label})",
            "pass" if spans else "reject",
            placed.tally(),
            f"every rib runs {ends}",
            False,
            section="constraint",
            cites=tuple(placement.cites),
        )
    )
    for problem in placed.problems:
        out.append(
            Finding(f"placement {placement.id}", "reject", problem, "", False, section="constraint")
        )
    return out


def _why_none(placed: Placed) -> str:
    return placed.problems[0] if placed.problems else placed.tally()


def _digest(opened: Opened, version: Version, levers: dict[str, float]) -> str:
    payload = json.dumps(
        {
            "base": opened.base.key,
            "version": version.model_dump(exclude={"created", "changes"}),
            "levers": levers,
            "fidelity": opened.fidelity,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def copy_version(version: Version) -> Version:
    return copy.deepcopy(version)
