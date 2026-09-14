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
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

import numpy as np

from .. import cache, knowledge
from ..extract import Extraction
from ..project import Project
from ..spec import HoleSet, Placement, Version
from ..study import INTERFACE_CLEARANCE_MM
from .checks import Finding, Rules, check, holes_through, timed
from .compose import CODE_COMPOSE, Composition, compose, margin_for, window_between
from .designs import Design, _worst
from .distance import backend
from .field import Field, field_for
from .holes import cut
from .placement import Drilled, Placed, _Faces, place_all, root_gap_of
from .repair import repair
from .screen import face_offsets, measure_walls, screen
from .surface import Surface, recontour, surface_for
from .thicken import move_faces, moved_faces

FIDELITIES = ("preview", "full")
CODE = (
    *CODE_COMPOSE,
    "generate/placement.py",
    "generate/intent.py",
    "generate/checks.py",
    "generate/holes.py",
    "generate/thicken.py",
    "generate/screen.py",
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
    patches: dict = field(default_factory=dict)
    """The faces each block of faces moved samples, kept for every design that moves them."""

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
        if radius is None:
            if not version.placements:
                raise IntentError("nothing in the spec says how finely to open the part")
            radius = min(p.section.root_fillet_mm for p in version.placements)
        full = radius / 4.0
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


class Clock:
    """How long each step of a build takes, in seconds, by name - added up when a step runs
    twice."""

    def __init__(self) -> None:
        self.times: dict[str, float] = {}

    @contextmanager
    def __call__(self, name: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            self.times[name] = self.times.get(name, 0.0) + time.perf_counter() - started

    def said(self) -> dict[str, float]:
        """Each step's time, to the millisecond."""
        return {name: round(seconds, 3) for name, seconds in self.times.items()}


def make(
    opened: Opened,
    version: Version,
    levers: dict[str, float] | None = None,
    *,
    finder: _Faces | None = None,
    memo: dict | None = None,
    surface: bool = True,
) -> Made:
    """The design ``version`` describes with ``levers`` applied. See the module note.

    In order: the faces it moves, exactly; its ribs and their pads, filleted to the part where it
    now is; its holes, cut; its surface drawn - re-contoured where it changed. Then the checks - on
    the part as moved, what ribs stand on and end on - and what screening found besides. Every step
    and every check is timed: ``stats["steps"]``, and each finding's ``seconds``.

    ``surface`` False leaves the surface undrawn, and the one check that reads it: the field is
    built and checked all the same, and weighed from the field - what a design built for a dataset
    needs, whose surface is drawn only when someone opens it."""
    started = time.perf_counter()
    clock = Clock()
    levers = dict(levers or {})
    placements = _apply(version, levers)
    extraction = opened.extraction
    features, tess = extraction.features, extraction.tess
    assert features is not None and extraction.atlas is not None and tess is not None
    rules = _rules(version) if placements else None
    finder = finder or _Faces(tess)

    # Each block after those it keeps clear of, on the part with its faces moved - then mended as
    # a campaign mended it, the fewest pieces left out so no rule between them breaks: the design
    # built is the design screened.
    with clock("place"):
        placed = place_all(
            opened.base,
            features,
            extraction.atlas,
            tess,
            placements,
            version.holes,
            offsets=face_offsets(features, version.offsets),
            finder=finder,
            memo=memo,
        )
    with clock("repair"):
        mended = repair(opened.base, placements, version.holes, placed)
    placed = mended.placed
    ribs = [rib for p in placements for rib in placed[p.id].ribs]
    pads = [pad for p in placements for pad in placed[p.id].pads]
    holes = [hole for hs in version.holes for hole in placed[hs.id].holes]
    solids = [*ribs, *pads]
    # Which block each rib and pad is of: it is joined to the part with that block's fillet, and
    # held to that block's rules.
    owner_of = [p.id for p in placements for _ in placed[p.id].ribs]
    owner_of += [p.id for p in placements for _ in placed[p.id].pads]
    fillet_of = {p.id: p.section.root_fillet_mm for p in placements}
    radii = [fillet_of[owner] for owner in owner_of]
    radius = max(radii, default=0.0)

    with clock("screen"):
        constraints = [f for p in placements for f in _constraints(p, placed[p.id])]
        constraints += [f for hs in version.holes for f in _hole_constraints(hs, placed[hs.id])]
        screened = screen(
            features,
            opened.base,
            placements,
            version.holes,
            version.offsets,
            version.material,
            placed,
            measure_walls(extraction, finder.exit_along, version.offsets),
            opened.surface.volume_mm3,
        )
    # What screening holds a design to that the checks do not: the rest the checks say again.
    constraints += [
        Finding(
            f["check"],
            f["outcome"],
            f["reason"],
            f["rule"],
            True,
            section="check",
            seconds=screened.seconds.get(f["check"], 0.0),
        )
        for f in screened.findings
        if f["check"] in SCREENED_ONLY
    ]

    field = opened.base
    changed: list[np.ndarray] = []
    shift = None
    # The faces the design moves - its variants' own; a floor is never moved for its ribs.
    if version.offsets:
        with clock("move faces"):
            kept_closed = _interface_faces(features) - moved_faces(features, version.offsets)
            moved = move_faces(
                opened.base,
                tess,
                features,
                version.offsets,
                kept_closed,
                INTERFACE_CLEARANCE_MM,
                opened.patches,
            )
        field, shift = moved.field, moved.shift
        changed.append(moved.changed)
    composition = Composition(field=field, changed=np.empty(0, dtype=np.int64))
    findings: list[Finding] = [*constraints]
    if placements and not ribs:
        reasons = "; ".join(_why_none(placed[p.id]) for p in placements)
        findings.append(
            Finding(
                "ribs placed",
                "reject",
                f"no rib could be placed: {reasons}",
                "",
                False,
                seconds=screened.seconds.get("ribs placed", 0.0),
            )
        )
    window = None
    if solids:
        with clock("window"):
            window = _window(opened, placements, placed, solids, radius)
        with clock("compose"):
            composition = compose(field, window, solids, radii, shift=shift)
        changed.append(composition.changed)
    if holes:
        with clock("cut holes"):
            cutting = cut(composition.field, holes)
        composition.field = cutting.field
        changed.append(cutting.changed)
    every = np.unique(np.concatenate(changed)) if changed else np.empty(0, dtype=np.int64)
    composition.changed = every
    drawn: Surface | None = None
    if surface:
        drawn = opened.surface
        if every.size:
            with clock("recontour"):
                drawn = recontour(opened.surface, composition.field, every, face_ids_from=tess)
    with clock("checks"):
        if solids and window is not None and rules is not None:
            owners = dict(zip(solids, owner_of, strict=True))
            findings += check(field, window, composition, solids, drawn, rules, owners)
        elif drawn is not None:
            findings += timed(_surface_check, drawn)
        if holes:
            findings += timed(holes_through, field, composition.field, holes)
    with clock("weigh"):
        taken = cut_faces(opened.base, composition.field, every, tess)
        if drawn is not None:
            volume, weighed = drawn.volume_mm3, "surface"
        else:
            added = volume_change(opened.base, composition.field, every)
            volume, weighed = opened.surface.volume_mm3 + added, "field"

    chosen = knowledge.material(
        version.material.material if version.material else knowledge.default_material()[0]
    )
    density = float((chosen or {}).get("density_kg_m3", 0.0))
    settings = {"spec_version": version.version, "levers": levers, "fidelity": opened.fidelity}
    design = Design(
        settings=settings,
        digest=_digest(opened, version, levers),
        base=opened.base,
        composition=composition,
        surface=drawn,
        findings=_worst([findings]),
        stats={
            "ribs": len(ribs),
            "pads": len(pads),
            "holes": len(holes),
            "fidelity": opened.fidelity,
            "spacing_mm": opened.base.grid.spacing_mm,
            "volume_cm3": volume / 1e3,
            "base_volume_cm3": opened.surface.volume_mm3 / 1e3,
            "added_cm3": (volume - opened.surface.volume_mm3) / 1e3,
            "weighed_from": weighed,
            "material": (chosen or {}).get("id"),
            "mass_kg": round(volume * density * 1e-9, 1),
            "seconds": round(time.perf_counter() - started, 1),
            "steps": clock.said(),
            "distance": backend(),
            "left_out": len(mended.left_out),
            "cut_faces": taken,
        },
        ribs=ribs,
        part_surface=opened.surface,
    )
    return Made(design, placed, version.version, levers, opened.fidelity)


def cut_faces(base: Field, field: Field, changed: np.ndarray, tess) -> list[int]:
    """The part's faces a design takes metal away from - holes cut through them, faces thinned:
    the faces nearest the cells that were metal and are not. Where the viewer shows the design's
    own surface instead of the part's."""
    changed = np.asarray(changed, dtype=np.int64)
    if not changed.size:
        return []
    removed = changed[base.inside.ravel()[changed] & ~field.inside.ravel()[changed]]
    if not removed.size:
        return []
    from .surface import _lookup

    tree, owner = _lookup(tess.vertices, tess.triangles, tess.face_id, base.grid.spacing_mm)
    _, nearest = tree.query(base.grid.centres(removed), k=1, workers=-1)
    return sorted({int(face) for face in owner[nearest]})


def volume_change(base: Field, field: Field, changed: np.ndarray) -> float:
    """How much metal a design adds, less what it takes away, in cubic millimetres - read off the
    field where it changed: each cell counted as full as its distance says, a cell on the surface
    half full, one a half cell inside wholly."""
    changed = np.asarray(changed, dtype=np.int64)
    if not changed.size:
        return 0.0
    spacing = base.grid.spacing_mm

    def full(values: np.ndarray) -> np.ndarray:
        return np.clip(0.5 - values.astype(np.float64) / spacing, 0.0, 1.0)

    return float((full(field.at(changed)) - full(base.at(changed))).sum() * spacing**3)


# What screening finds that the checks of a built design do not look at.
SCREENED_ONLY = ("rib on floor", "wall kept", "holes placed", "holes clear of ribs")


def _interface_faces(features) -> set[int]:
    """The faces of every hole and bore on the part - its interfaces, kept as they are."""
    from ..features import FeatureKind

    return {
        face
        for kind in (FeatureKind.HOLE, FeatureKind.BORE)
        for feature in features.of_kind(kind)
        for face in feature.face_ids
    }


def _surface_check(surface: Surface) -> list[Finding]:
    from .checks import _surface

    return [_surface(surface)]


def _hole_constraints(holes: HoleSet, drilled: Drilled) -> list[Finding]:
    """A set of holes, verified on the holes it actually cut."""
    rule = (
        f"Ø{holes.diameter_mm:g} at {holes.pitch_mm:g} mm pitch, {holes.edge_mm:g} mm from the "
        f"plate's edges, {holes.ligament_mm:g} mm of metal from anything else"
    )
    outcome = "pass" if drilled.holes else "reject"
    return [
        Finding(
            f"holes ({holes.id})",
            outcome,
            drilled.tally(),
            rule,
            False,
            section="constraint",
            cites=tuple(holes.cites),
        )
    ]


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
    """The checks' thresholds: the part's own from the spec - each block's own where it has them,
    and the fillet each was made with - the rest general and marked so."""
    first = version.placements[0].section
    given = dict(version.rules)
    thickness = given.get("thickness_mm", [first.thickness_mm, first.thickness_mm])
    windows = given.get("per_block") or {}
    per_block = {}
    for placement in version.placements:
        spans = windows.get(placement.id, {})
        own = {
            name: tuple(map(float, span)) if isinstance(span, list | tuple) else float(span)
            for name, span in spans.items()
        }
        per_block[placement.id] = {
            **own,
            "root_fillet_mm": placement.section.root_fillet_mm,
            "root_gap": root_gap_of(placement),
        }
    rules = Rules(
        thickness_mm=(float(thickness[0]), float(thickness[1])),
        edge_round_mm=first.edge_round_mm,
        # How far a fillet reaches, for the checks that look round a rib's root: the largest.
        root_fillet_mm=max(p.section.root_fillet_mm for p in version.placements),
        fillet_floor_mm=given.get("fillet_floor_mm"),
        draft_used_deg=first.draft_deg,
        per_block=per_block,
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
    # Each face kept clear of is held as far as the clearance kept from it - the widest, when
    # several blocks keep clear of it - not as far as the widest any keep-out asks for anywhere.
    clearance_of: dict[int, float] = {}
    for placement in placements:
        result = placed.get(placement.id)
        if not isinstance(result, Placed):
            continue
        for row in result.keep_outs:
            clearance = placement.keep_out[row["rule"]].clearance_mm
            for face in features.get(row["feature"]).face_ids:
                clearance_of[face] = max(clearance_of.get(face, 0.0), clearance)
    # The part's distance is exact near each rib - where its fillet reads it - and nowhere else.
    around = [
        (np.floor(box[0] / snap) * snap, np.ceil(box[1] / snap) * snap)
        for box in (rib.bounds() for rib in ribs)
    ]
    key = cache.key_for(
        base.key,
        ",".join(f"{v:.3f}" for v in (*lo, *hi)),
        f"{radius:.6f}",
        ",".join(f"{face}:{clearance:g}" for face, clearance in sorted(clearance_of.items())),
        ";".join(",".join(f"{v:.0f}" for v in (*a, *b)) for a, b in sorted(map(_listed, around))),
        # Where the distance was computed: the GPU's and the CPU's agree to thousandths of a
        # millimetre, not to the bit, and a design is built from one or the other throughout.
        backend(),
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
            protected_faces=clearance_of,
            around=around,
        ),
    )
    return window


def _listed(box: tuple[np.ndarray, np.ndarray]) -> tuple[tuple[float, ...], tuple[float, ...]]:
    return tuple(float(v) for v in box[0]), tuple(float(v) for v in box[1])


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
        tall = placement.height.thicknesses
        out.append(
            Finding(
                f"height ({label})",
                "pass",
                f"tallest {tallest:.1f} mm above the host, each rib held to " + ", ".join(limits),
                (f"{tall:g} thicknesses tall, " if tall else "")
                + "no taller than what each end meets"
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
