"""The extract pipeline: deterministic steps, each reporting what it could and could not do.

Every step declares which artifact kinds it needs. A project with no drawing does not fail - the
drawing steps report ``skipped`` with the reason, and everything derivable from CAD alone still
runs. That is the whole test of whether this is a platform: drop a folder containing one STEP file
and no drawing, and the pipeline must produce a smaller but honest result rather than an error.

**Where controlled geometry comes from.** Not from a person's judgement typed into a manifest. A
drawing that puts a tolerance band on a dimension is *stating* that the feature is controlled, and
a detected feature whose size matches that band is the feature it is stating it about. So control
is derived from two artifacts agreeing, and every instance of it cites a page and the literal text
it was read from.

Nothing here is asserted that cannot be traced to a file in the project folder, to a page within
it, and to the literal text on that page.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np

from . import cache
from . import drawing as drawing_reader
from .drawing import CalloutKind, DrawingRead
from .features import FeatureKind, FeatureSet
from .features import detect as detect_features
from .geometry import (
    ExactProperties,
    HealthReport,
    Tessellation,
    check,
    declared_unit,
    exact_properties,
    tessellate,
)
from .geometry.atlas import Atlas
from .geometry.atlas import build as build_atlas
from .geometry.brep import INTERNAL_UNIT, load_cad
from .project import Artifact, ArtifactKind, Project
from .provenance import Conflict, Evidence, Fact, ProvenanceLog, SourceKind

# How closely a drawing dimension must match a modelled size to be the same feature.
#
# Wider than a tolerance band, because a drawing states a *controlled* size while a model carries a
# nominal and the two part company by design - a bore drawn at a mid-limit is routinely modelled at
# its round nominal. Matching at the drawing's own band would report ordinary practice as
# disagreement and teach everyone to ignore disagreements.
#
# But narrow relative to the part, because this decides *identity*. At 1 mm a 20.0 callout reached
# a O21.00 pattern, and a wrong association manufactures a conflict between two features that were
# never the same thing. Derived from the model's size so a small part does not inherit a tolerance
# spanning several of its own features, and capped so a large one does not get a loose band.
MATCH_TOL_FRACTION = 2.5e-4
MAX_MATCH_TOL_MM = 0.5

# How much better the best candidate must be than the runner-up, as a fraction of the matching
# tolerance.
#
# Text extraction gives no coordinates, so there is no leader line, no view and no position tying a
# callout to the geometry it points at. Size is all that remains, and a size can belong to several
# features - so separation from the next-best candidate is the only evidence that a match
# identifies one feature rather than picking arbitrarily among several.
DISCRIMINATION_MARGIN = 0.5

# The modules a stored extraction depends on. Naming them keeps a change to the interface, a route
# or the field from throwing away a result none of them could have affected.
CODE = (
    "extract.py",
    "project.py",
    "drawing.py",
    "features.py",
    "provenance.py",
    "geometry/brep.py",
    "geometry/health.py",
    "geometry/atlas.py",
    "simulate/aster.py",
    "simulate/med.py",
    "simulate/fem.py",
    "simulate/setup.py",
    "simulate/carry.py",
    "simulate/baseline.py",
)


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class Step:
    """One deterministic stage of extraction, and what it produced."""

    id: str
    label: str
    needs: tuple[ArtifactKind, ...] = ()
    status: StepStatus = StepStatus.PENDING
    detail: str = ""
    produced: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    seconds: float = 0.0

    def render(self) -> str:
        marks = {
            StepStatus.DONE: "ok",
            StepStatus.SKIPPED: "--",
            StepStatus.FAILED: "!!",
            StepStatus.PENDING: "..",
            StepStatus.RUNNING: ">>",
        }
        return f"  {marks[self.status]}  {self.label:34s} {self.detail}"


@dataclass
class Extraction:
    """The result of running the pipeline over one project."""

    project: Project
    artifacts: list[Artifact] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    log: ProvenanceLog = field(default_factory=ProvenanceLog)

    def first(self, kind: ArtifactKind) -> Artifact | None:
        return next((a for a in self.artifacts if a.kind is kind), None)

    def baseline(self) -> Artifact | None:
        """The CAD this extraction reads: the one the project names as baseline, if it was offered,
        otherwise the first CAD offered."""
        named = self.project.roles().get("baseline")
        cad = [a for a in self.artifacts if a.kind is ArtifactKind.CAD]
        return next((a for a in cad if a.name == named), cad[0] if cad else None)

    # Products, present only if the step that makes them ran.
    shape: Any | None = None
    """The loaded B-rep. Held so later steps can measure it without re-reading the file."""

    cad_digest: str = ""
    """Content hash of the CAD that was read. Everything measured from it is bound to this."""

    from_cache: bool = False
    """Whether this came back from disk rather than being computed. Reported, never acted on."""

    exact: ExactProperties | None = None
    tess: Tessellation | None = None
    health: HealthReport | None = None
    atlas: Atlas | None = None
    features: FeatureSet | None = None
    drawing: DrawingRead | None = None
    controlled: dict[str, Fact[bool]] = field(default_factory=dict)
    deck: dict[str, Any] | None = None
    """What the solver deck asks for, in words that do not depend on the solver, and its files."""
    anchoring: dict[str, Any] | None = None
    """Which CAD faces each group the deck acts on lies on, and where its reference points are."""

    @property
    def ok(self) -> bool:
        """Whether the part can be opened. A solver deck that cannot be read is reported on its own
        steps and leaves the part itself open - the deck is context, the CAD is the part."""
        return not any(
            s.status is StepStatus.FAILED and not s.id.startswith("deck.") for s in self.steps
        )

    @property
    def seconds(self) -> float:
        return sum(s.seconds for s in self.steps)

    def step(self, step_id: str) -> Step | None:
        return next((s for s in self.steps if s.id == step_id), None)

    def controlled_face_ids(self) -> set[int]:
        """Faces no design parameter may move.

        Only where the evidence is trustworthy. A match that disagrees, or a claim with only one
        source behind it, is surfaced for a human rather than silently acted on: freezing on weak
        evidence removes design freedom exactly as quietly as failing to freeze removes
        correctness.
        """
        if self.features is None:
            return set()
        return {
            face_id
            for feature_id, fact in self.controlled.items()
            if fact.value and fact.trustworthy
            for face_id in self.features.features[feature_id].face_ids
        }

    def render(self) -> str:
        lines = [f"{self.project.title}  ({self.seconds:.1f}s)"]
        lines += [s.render() for s in self.steps]
        if self.log.conflicts:
            lines += ["", f"  {len(self.log.conflicts)} unresolved pairings:"]
            lines += [
                f"    - {c.subject}: {c.left_value} vs {c.right_value}" for c in self.log.conflicts
            ]
        return "\n".join(lines)


def run(
    project: Project,
    artifacts: list[Artifact] | None = None,
    reuse: bool = True,
) -> Extraction:
    """Extract what a project's artifacts state. Never raises for a missing artifact, only a
    broken one.

    ``artifacts`` overrides what the folder contains, so a caller can point at files elsewhere or
    substitute one of them. Discovery is the default rather than the only option: a person editing
    a path in the interface is choosing what to extract, and that choice has to reach here.

    ``reuse`` returns a cached result when the same files have already been read by the same code.
    Set it False to read the files again, which is what a *re-extract* means.
    """
    chosen = artifacts or project.artifacts()
    # The roles decide which CAD is read, so they are part of what the result depends on.
    roles = ",".join(f"{role}={name}" for role, name in sorted(project.roles().items()))
    key = cache.key_for(*_fingerprint(chosen), f"roles:{roles}", code=CODE)
    item = cache.entry(project.root, "extract", key)

    result, hit = cache.memoise(item, lambda: _run(project, chosen), reuse=reuse)
    result.from_cache = hit
    return result


def _fingerprint(artifacts: list[Artifact]) -> list[str]:
    """What the result depends on: which files, and exactly what is in them."""
    return [f"{a.path}:{a.kind}:{a.digest()}" for a in artifacts]


def _run(project: Project, artifacts: list[Artifact]) -> Extraction:
    result = Extraction(project=project, artifacts=artifacts)

    discovered = _step(result, "discover", "Discover artifacts", _discover)
    cad = result.baseline()
    dwg = result.first(ArtifactKind.DRAWING)

    if discovered.status is StepStatus.FAILED:
        return result

    _step(
        result,
        "cad.load",
        "Read CAD",
        lambda r: _load_cad(r, cad),
        needs=(ArtifactKind.CAD,),
        available=cad is not None,
    )
    _step(
        result,
        "cad.health",
        "Check geometry health",
        _check_health,
        needs=(ArtifactKind.CAD,),
        available=result.exact is not None,
    )
    _step(
        result,
        "cad.atlas",
        "Measure every face",
        _build_atlas,
        needs=(ArtifactKind.CAD,),
        available=result.tess is not None,
    )
    _step(
        result,
        "cad.features",
        "Detect features",
        _detect,
        needs=(ArtifactKind.CAD,),
        available=result.atlas is not None,
    )
    _step(
        result,
        "drawing.read",
        "Read drawing",
        lambda r: _read_drawing(r, dwg),
        needs=(ArtifactKind.DRAWING,),
        available=dwg is not None,
    )
    _step(
        result,
        "crosscheck",
        "Cross-check drawing against CAD",
        _crosscheck,
        needs=(ArtifactKind.CAD, ArtifactKind.DRAWING),
        available=result.features is not None and result.drawing is not None,
    )

    from .simulate import baseline as solver_deck

    files = solver_deck.deck_files(project)
    _step(
        result,
        "deck.read",
        "Read the solver deck",
        _read_deck,
        needs=(ArtifactKind.FEM,),
        available=files.complete,
    )
    _step(
        result,
        "deck.results",
        "Read the solver's results",
        _read_results,
        needs=(ArtifactKind.RESULTS,),
        available=result.deck is not None and files.results is not None,
    )
    _step(
        result,
        "deck.anchor",
        "Tie the deck's groups to the CAD",
        _anchor_deck,
        needs=(ArtifactKind.CAD, ArtifactKind.FEM),
        available=result.deck is not None and result.tess is not None,
    )

    # The B-rep does not survive being stored, and nothing after this point asks for it: health and
    # the atlas are the only two steps that read it, and both have run. Dropping it here rather
    # than at the cache boundary keeps a restored result identical to a fresh one.
    result.shape = None
    return result


def _step(
    result: Extraction,
    step_id: str,
    label: str,
    action,
    needs: tuple[ArtifactKind, ...] = (),
    available: bool = True,
) -> Step:
    """Run one step, or record precisely why it did not run.

    A skipped step is a first-class outcome with a stated reason, not an absence. That is what
    lets a project with only CAD produce a report a person can read and act on.

    The reason names only the kinds actually missing. Listing everything a step needs would have
    said "no CAD, Drawing in this project" for a project that has CAD and no drawing, which is
    both wrong and the kind of message that teaches people to stop reading messages.
    """
    step = Step(id=step_id, label=label, needs=needs)
    result.steps.append(step)

    if not available:
        present = {a.kind for a in result.artifacts}
        missing = [k.label for k in needs if k not in present]
        step.status = StepStatus.SKIPPED
        step.detail = (
            f"no {' or '.join(missing)} in this project"
            if missing
            else "an earlier step did not produce what this one needs"
        )
        return step

    started = time.perf_counter()
    step.status = StepStatus.RUNNING
    try:
        detail = action(result) or ""
        step.status = StepStatus.DONE
        step.detail = detail
    except Exception as error:
        step.status = StepStatus.FAILED
        step.detail = f"{type(error).__name__}: {error}"
    step.seconds = time.perf_counter() - started
    return step


# --- steps --------------------------------------------------------------------------------------


def _discover(result: Extraction) -> str:
    artifacts = result.artifacts
    by_kind: dict[str, list[str]] = {}
    for artifact in artifacts:
        by_kind.setdefault(artifact.label, []).append(artifact.name)

    step = result.steps[-1]
    step.produced = {
        "artifacts": [
            {
                "name": a.name,
                "kind": str(a.kind),
                "label": a.label,
                "path": str(a.path),
                "size_bytes": a.size_bytes,
            }
            for a in artifacts
        ],
        "by_kind": {k: len(v) for k, v in by_kind.items()},
        "roles": result.project.roles(),
    }
    cad = [a.name for a in artifacts if a.kind is ArtifactKind.CAD]
    if not cad:
        step.warnings.append("no CAD in this project - nothing downstream can run")
    named = result.project.roles().get("baseline")
    if named is not None and named not in cad:
        step.warnings.append(f"the baseline is named as {named}, which is not among the files read")
    if len(cad) > 1 and named not in cad:
        chosen = result.baseline()
        step.warnings.append(
            f"{len(cad)} CAD files and none named as baseline; reading "
            f"{chosen.name if chosen else cad[0]} because its name sorts first"
        )
    if not any(a.kind is ArtifactKind.DRAWING for a in artifacts):
        step.warnings.append(
            "no drawing - sizes will be as modelled, with nothing stating which are controlled"
        )
    unknown = [a.name for a in artifacts if a.kind is ArtifactKind.UNKNOWN]
    if unknown:
        step.warnings.append(f"unrecognised file types: {', '.join(unknown)}")

    return ", ".join(f"{count} {kind}" for kind, count in step.produced["by_kind"].items())


def _load_cad(result: Extraction, artifact: Artifact | None) -> str:
    assert artifact is not None
    shape, notes = load_cad(artifact.path)
    result.exact = exact_properties(shape)
    result.shape = shape
    result.cad_digest = artifact.digest()

    unit = declared_unit(artifact.path) if artifact.path.suffix.lower() != ".brep" else "unstated"
    step = result.steps[-1]
    step.warnings.extend(notes)
    step.produced = {
        "file": artifact.name,
        "digest": result.cad_digest,
        "declared_unit": unit,
        "read_as": INTERNAL_UNIT.lower(),
        "solids": result.exact.n_solids,
        "faces": result.exact.n_faces,
        "volume_cm3": round(result.exact.volume_cm3, 1),
        "area_m2": round(result.exact.area_mm2 / 1e6, 4),
        "bbox_mm": [round(v, 1) for v in result.exact.bbox_mm],
    }
    if result.exact.n_solids != 1:
        step.warnings.append(f"{result.exact.n_solids} solids; downstream assumes one body")
    if unit == "unstated":
        step.warnings.append(
            f"the file declares no length unit; it was read as {INTERNAL_UNIT.lower()}"
        )
    elif unit not in ("millimetre",):
        step.warnings.append(
            f"the file declares {unit}; it was rescaled to {INTERNAL_UNIT.lower()} on read"
        )
    return (
        f"{result.exact.n_solids} solid, {result.exact.n_faces} faces, "
        f"{result.exact.volume_cm3:,.0f} cm3"
    )


def _check_health(result: Extraction) -> str:
    result.tess = tessellate(result.shape)
    assert result.exact is not None
    result.health = check(result.tess, result.exact)

    step = result.steps[-1]
    step.produced = {
        "triangles": result.tess.n_triangles,
        "watertight": result.health.watertight,
        "boundary_edges": result.health.boundary_edges,
        "non_manifold_edges": result.health.non_manifold_edges,
        "inconsistent_edges": result.health.inconsistent_edges,
        "shells": result.health.n_components,
        "volume_error_pct": round(result.health.volume_error * 100, 4),
    }
    step.warnings.extend(result.health.failures)
    if not result.health.watertight:
        raise ValueError(
            "the surface is not closed, so inside and outside are undefined and nothing "
            "downstream can be trusted"
        )
    return f"watertight, {result.tess.n_triangles:,} triangles"


def _build_atlas(result: Extraction) -> str:
    assert result.tess is not None
    result.atlas = build_atlas(result.shape, result.tess, result.cad_digest)
    exterior = len(result.atlas.exterior_faces())
    result.steps[-1].produced = {"faces": len(result.atlas), "exterior_faces": exterior}
    return f"{len(result.atlas)} faces, {exterior} reachable from outside"


def _detect(result: Extraction) -> str:
    assert result.atlas is not None and result.exact is not None
    result.features = detect_features(result.atlas, result.exact.bbox_mm)
    counts = result.features.counts()
    result.steps[-1].produced = {
        "features": len(result.features.features),
        "axes": len(result.features.axes),
        "significant_axes": len(result.features.significant_axes()),
        "by_kind": counts,
    }
    return ", ".join(f"{count} {kind}" for kind, count in counts.items())


def _read_drawing(result: Extraction, artifact: Artifact | None) -> str:
    assert artifact is not None
    result.drawing = drawing_reader.read(artifact.path)
    summary = drawing_reader.summarise(result.drawing)
    result.steps[-1].produced = summary
    result.steps[-1].warnings.extend(result.drawing.warnings)
    if not result.drawing.has_text:
        return f"{result.drawing.pages} pages, no text layer"
    return (
        f"{result.drawing.pages} pages, {len(result.drawing.callouts)} callouts, "
        f"{summary['toleranced_dimensions']} toleranced"
    )


def _crosscheck(result: Extraction) -> str:
    """Match what the drawing states against what the model contains.

    **The association is a hypothesis, not a measurement.** Text extraction yields no coordinates,
    so there is no leader line and no view tying a callout to the geometry it points at. Size is
    all that remains, and a size can belong to several features. So a match is asserted only when
    it is *decisive* - the best candidate clearly better than the runner-up - and it counts as an
    association only when a second, independent quantity agrees.

    Where size agrees and count does not, that is not a conflict about the count. It is doubt about
    the pairing: either the count is wrong, or these were never the same feature. The doubt is
    recorded as such rather than one reading being chosen.
    """
    assert result.features is not None and result.drawing is not None
    features = result.features
    tolerance = min(features.diagonal_mm * MATCH_TOL_FRACTION, MAX_MATCH_TOL_MM)
    matched = 0
    unmatched: list[str] = []
    ambiguous: list[str] = []

    # A toleranced dimension is the drawing asserting control over a size. Matching it to a
    # detected feature is what turns that assertion into a set of faces nothing may move.
    for callout in result.drawing.callouts:
        if callout.tolerance is None or callout.nominal is None:
            continue
        feature, rival = _best_and_rival(
            features, callout.nominal, (FeatureKind.BORE, FeatureKind.BOSS), tolerance
        )
        if feature is None:
            unmatched.append(
                f"p{callout.page} {callout.raw!r} - no bore or boss within "
                f"{tolerance:.3g} mm of {callout.nominal:g}"
            )
            continue
        if not _decisive(feature, rival, callout.nominal, tolerance):
            ambiguous.append(
                f"p{callout.page} {callout.raw!r} - {feature.id} at "
                f"{feature.diameter_mm:.2f} and {rival.id} at {rival.diameter_mm:.2f} "
                f"match equally well"
            )
            continue

        matched += 1
        from_drawing = _drawing_evidence(
            result,
            callout.page,
            callout.raw,
            f"{callout.nominal:.3f} +/-{callout.tolerance:.3f}",
        )
        from_cad = _cad_evidence(result, feature.id, feature.describe())

        # A tolerance band states that a size is controlled. It does not state that the size is a
        # diameter, and the symbol that would say so does not survive extraction. Matching it to a
        # bore is therefore an inference, cited as one, and its confidence caps the fact's.
        inferred = Evidence(
            kind=SourceKind.DERIVED,
            locator=f"{callout.raw!r} matched to {feature.id}",
            method="matched on nearest diameter; the drawing does not state this is a diameter",
            detail=(
                f"drawing {callout.nominal:.3f} mm against modelled {feature.diameter_mm:.3f} mm"
            ),
            confidence=1.0 if callout.is_diameter else 0.7,
        )
        gap = abs((feature.diameter_mm or 0.0) - callout.nominal)
        note = (
            f"drawing {callout.nominal:.3f}, modelled {feature.diameter_mm:.3f}"
            if gap > 1e-3
            else ""
        )
        result.controlled[feature.id] = Fact(True, (from_drawing, from_cad, inferred), False, note)
        result.log.record(f"{feature.id} controlled", from_drawing)
        result.log.record(f"{feature.id} controlled", from_cad)

    # A counted callout states how many of something there are. Comparing it to a detected pattern
    # tests both accounts against each other on a number neither can fudge.
    for callout in result.drawing.of_kind(CalloutKind.COUNTED):
        if callout.value is None or callout.count is None:
            continue

        # A counted number is only comparable with a hole diameter if something says it is one.
        # Without this guard a spacing between two features - `2X 150` - competes to match a
        # 150 mm hole pattern, and nothing in the extracted text tells the two apart.
        if not callout.reads_as_hole:
            unmatched.append(f"p{callout.page} {callout.raw!r} - not identifiable as a hole")
            continue

        pattern, rival = _best_and_rival(
            features, callout.value, (FeatureKind.HOLE_PATTERN,), tolerance
        )
        if pattern is None:
            unmatched.append(
                f"p{callout.page} {callout.raw!r} - no pattern within "
                f"{tolerance:.3g} mm of {callout.value:g}"
            )
            continue
        if not _decisive(pattern, rival, callout.value, tolerance):
            ambiguous.append(
                f"p{callout.page} {callout.raw!r} - {pattern.id} at "
                f"{pattern.diameter_mm:.2f} and {rival.id} at {rival.diameter_mm:.2f} "
                f"match equally well"
            )
            continue

        matched += 1
        from_drawing = _drawing_evidence(
            result,
            callout.page,
            callout.raw,
            f"{callout.count} features of {callout.value:g} mm",
        )
        from_cad = _cad_evidence(result, pattern.id, pattern.describe())

        # The association rests on an inference, so it is cited as one. Its confidence caps the
        # fact's, which is what stops a conflict built on a reading from looking as firm as one
        # built on two measurements.
        inferred = Evidence(
            kind=SourceKind.DERIVED,
            locator=f"{callout.raw!r} matched to {pattern.id}",
            method=f"read as a hole because of {callout.hole_basis}; matched on nearest diameter",
            detail=(f"drawing {callout.value:g} mm against modelled {pattern.diameter_mm:.2f} mm"),
            confidence=1.0 if callout.is_diameter else 0.7,
        )

        # Count is the corroborating quantity, and it decides what this match is worth.
        #
        # Size and count agreeing is two independent quantities agreeing about one feature, which
        # is an association. Size agreeing while count does not is one agreeing and one dissenting,
        # and from here there is no way to tell whether the count is wrong or whether these were
        # never the same feature - so the doubt goes against the pairing, not the number.
        if pattern.count == callout.count:
            result.controlled[pattern.id] = Fact(
                True, (from_drawing, from_cad, inferred), False, "size and count both agree"
            )
        else:
            result.log.conflict(
                Conflict(
                    subject=f"{pattern.id}: size agrees, count does not",
                    left=from_drawing,
                    right=from_cad,
                    left_value=f"{callout.count} at {callout.value:g}",
                    right_value=f"{pattern.count} at {pattern.diameter_mm:.2f}",
                    tolerance=(
                        "either the count differs, or the callout describes different features "
                        "of the same size - size alone cannot tell them apart"
                    ),
                )
            )

    result.steps[-1].produced = {
        "matched": matched,
        "ambiguous": len(ambiguous),
        "unmatched_callouts": len(unmatched),
        "controlled_features": len(result.controlled),
        "controlled_faces": len(result.controlled_face_ids()),
        "unresolved_pairings": len(result.log.conflicts),
    }
    # A callout with nothing to match is worth saying out loud: either the drawing describes
    # something this model does not contain, or detection missed it.
    result.steps[-1].warnings.extend(ambiguous[:6] + unmatched[:8])
    return (
        f"{matched} of {matched + len(ambiguous) + len(unmatched)} callouts associated, "
        f"{len(ambiguous)} ambiguous, {len(result.controlled_face_ids())} controlled faces, "
        f"{len(result.log.conflicts)} unresolved"
    )


def _read_deck(result: Extraction) -> str:
    """The deck's commands read - never run - its mesh and groups, and what it asks for."""
    from .simulate import baseline as solver_deck

    deck = solver_deck.read_deck(result.project)
    assert deck is not None
    summary = solver_deck.summary(deck)
    kept = ("files", "mesh", "groups", "setup", "io", "skipped", "warnings", "digest")
    result.deck = {k: summary[k] for k in kept}
    setup = deck.setup
    step = result.steps[-1]
    step.produced = {
        "commands": deck.files.comm.name if deck.files.comm else None,
        "mesh": deck.files.mesh.name if deck.files.mesh else None,
        "nodes": summary["mesh"]["nodes"],
        "cells": summary["mesh"]["cells"],
        "groups": len(summary["groups"]),
        "held": len(setup.held),
        "rigid_couplings": len(setup.rigid),
        "distributing_couplings": len(setup.distributing),
        "loads": len(setup.nodal_loads) + len(setup.surface_loads),
        "signals": len(setup.outputs),
    }
    step.warnings.extend(f"not read: {line}" for line in deck.skipped[:10])
    step.warnings.extend(f"not interpreted: {line}" for line in setup.not_read[:10])
    step.warnings.extend(summary["warnings"][:10])
    if deck.mesh.tet10 is None:
        step.warnings.append(
            "the mesh's volume is not quadratic tetrahedra alone; fastcae solves TET10 only"
        )
    return (
        f"{summary['mesh']['nodes']:,} nodes, {len(summary['groups'])} groups; "
        f"{len(setup.held)} held, {len(setup.rigid)} rigid and "
        f"{len(setup.distributing)} distributing couplings, "
        f"{len(setup.nodal_loads) + len(setup.surface_loads)} loads, {len(setup.outputs)} signals"
    )


def _read_results(result: Extraction) -> str:
    """Which fields and tables the solver wrote back."""
    from .simulate import baseline as solver_deck

    deck = solver_deck.read_deck(result.project)
    assert deck is not None
    fields = {name: f.components for name, f in deck.fields.items()}
    tables = deck.tables()
    assert result.deck is not None
    result.deck["fields"] = [{"name": n, "components": c} for n, c in fields.items()]
    result.deck["tables"] = [{"columns": t.columns, "rows": len(t.rows)} for t in tables]
    result.steps[-1].produced = {
        "results": deck.files.results.name if deck.files.results else None,
        "fields": list(fields),
        "tables": len(tables),
        "rows": sum(len(t.rows) for t in tables),
    }
    return f"{len(fields)} fields ({', '.join(fields)}), {len(tables)} tables"


def _anchor_deck(result: Extraction) -> str:
    """Each group the deck acts on, as the CAD faces it lies on."""
    from .simulate import baseline as solver_deck
    from .simulate.carry import anchor

    deck = solver_deck.read_deck(result.project)
    assert deck is not None and result.tess is not None
    tess = result.tess
    anchored = anchor(deck.mesh, deck.setup, tess.vertices, tess.triangles, tess.face_id)
    result.anchoring = anchored.to_json()
    step = result.steps[-1]
    gaps = [a.gap for a in anchored.groups.values() if np.isfinite(a.gap)]
    step.produced = {
        "groups": len(anchored.groups),
        "reference_points": len(anchored.references),
        "largest_gap_mm": round(max(gaps), 3) if gaps else None,
        "not_anchored": anchored.not_anchored,
    }
    if anchored.not_anchored:
        step.warnings.append(f"not on the CAD's surface: {', '.join(anchored.not_anchored)}")
    return (
        f"{len(anchored.groups)} groups on CAD faces, {len(anchored.references)} reference points; "
        f"the mesh's patches lie within {max(gaps) if gaps else 0:.2f} mm of the CAD"
    )


# --- helpers ------------------------------------------------------------------------------------


def _best_and_rival(
    features: FeatureSet, diameter: float, kinds: tuple[FeatureKind, ...], tolerance: float
):
    """The nearest feature in diameter and the next nearest. Either may be None.

    Both are returned because the runner-up is what says whether the winner means anything.
    Ranking by area first - as an earlier version did - let a 20.0 callout match a 21.00 pattern
    of five holes while a 20.00 pattern of four sat within reach, because the wrong one was
    larger. Diameter is what is being matched on, so diameter decides.
    """
    ranked = sorted(
        (f for f in features.features.values() if f.kind in kinds and f.diameter_mm is not None),
        key=lambda f: (abs(f.diameter_mm - diameter), -f.area_mm2),
    )
    within = [f for f in ranked if abs(f.diameter_mm - diameter) <= tolerance]
    best = within[0] if within else None
    rival = ranked[1] if best is not None and len(ranked) > 1 else None
    return best, rival


def _decisive(best, rival, target: float, tolerance: float) -> bool:
    """Whether the best match is clearly better than the next, or merely first past the post.

    Separation, not proximity. On the part in ``assets/`` a 26.00 callout beat a 26.50 pattern by
    0.026 mm of tolerance margin: under a proximity test that is a match, and it is luck. Under a
    separation test it is decisive, because 26.00 sits exactly on one candidate and half a
    millimetre from the other - and where two candidates really are equally good, nothing is
    asserted at all.
    """
    if rival is None:
        return True
    return (
        abs(rival.diameter_mm - target) - abs(best.diameter_mm - target)
        > DISCRIMINATION_MARGIN * tolerance
    )


def _drawing_evidence(result: Extraction, page: int, raw: str, detail: str) -> Evidence:
    assert result.drawing is not None
    return Evidence(
        kind=SourceKind.DRAWING,
        locator=f"{result.drawing.path.name} page {page}: {raw!r}",
        method="text extracted from the PDF and parsed",
        detail=detail,
    )


def _cad_evidence(result: Extraction, feature_id: str, detail: str) -> Evidence:
    artifact = result.baseline()
    name = artifact.name if artifact else "the CAD"
    return Evidence(
        kind=SourceKind.CAD,
        locator=f"{name}: feature {feature_id}",
        method="geometric detection from the B-rep",
        detail=detail,
    )
