"""The extract pipeline, on whatever project is in ``assets/``.

Nothing here hardcodes a part. The tests discover the projects present and assert **behaviours** -
that a closed surface is closed, that a missing artifact is reported rather than fatal, that every
claim carries a source. Those hold for a gearbox housing, a bracket or a shaft, which is the only
kind of test worth having on a platform that has to work on all three.

The one thing deliberately not tested is a value. There are no expected diameters or counts here,
because the system is not supposed to know any until it reads them.
"""

from __future__ import annotations

import shutil

import pytest

from fastcae import extract
from fastcae.extract import StepStatus
from fastcae.project import ArtifactKind, Project, discover
from fastcae.provenance import SourceKind


@pytest.fixture(scope="module")
def projects():
    found = discover()
    if not found:
        pytest.skip("no projects under assets/")
    return found


@pytest.fixture(scope="module")
def result(projects):
    with_cad = [p for p in projects if p.first(ArtifactKind.CAD)]
    if not with_cad:
        pytest.skip("no project with CAD")
    return extract.run(with_cad[0])


# --- projects are folders ------------------------------------------------------------------------


def test_a_project_is_named_after_its_folder(projects):
    """Rename the folder and the product renames itself. No manifest, nowhere else to look."""
    for project in projects:
        assert project.name == project.root.name
        assert "_" not in project.title


def test_artifacts_are_classified_by_extension(projects):
    """An unrecognised file is classified as unrecognised, never left out.

    Not an assertion that everything is recognised - a folder is allowed to contain a stray file,
    and ``Discover artifacts`` warns about it rather than failing.
    """
    for project in projects:
        for artifact in project.artifacts():
            assert artifact.kind in set(ArtifactKind)
            assert artifact.path.exists()
            assert artifact.label


def test_a_missing_kind_returns_none_rather_than_raising(projects):
    """The whole design. A project without a drawing is not broken; it has no drawing yet."""
    for project in projects:
        for kind in ArtifactKind:
            found = project.first(kind)
            if found is None:
                assert not project.of_kind(kind), f"{kind} exists but first() returned None"
            else:
                assert found.kind is kind
                assert found == project.of_kind(kind)[0]


# --- the pipeline ---------------------------------------------------------------------------------


def test_the_pipeline_runs_and_reports_every_step(result):
    assert result.ok, result.render()
    assert result.steps
    for step in result.steps:
        assert step.status in (StepStatus.DONE, StepStatus.SKIPPED)
        assert step.detail, f"{step.id} said nothing about what it did"


def test_geometry_is_closed_before_anything_is_built_on_it(result):
    """Every later stage assumes inside and outside are defined. They are not, on a leaking
    surface, and the failure is silent rather than loud - so the gate is here."""
    assert result.health is not None
    assert result.health.watertight, result.health.render()
    assert result.health.n_components >= 1


def test_features_are_detected_without_any_document(result):
    """Detection reads geometry alone. A part with no drawing still gets its features."""
    assert result.features is not None
    assert result.features.features
    assert result.features.axes


def test_a_project_without_a_drawing_still_extracts(result, tmp_path):
    """The case that decides whether this is a platform.

    Copy the CAD alone into a new folder and run. The drawing steps must report *skipped with a
    reason*, everything derivable from geometry must still run, and nothing may raise.
    """
    cad = result.project.first(ArtifactKind.CAD)
    assert cad is not None

    folder = tmp_path / "CAD_Only_Project"
    folder.mkdir()
    shutil.copy(cad.path, folder / cad.name)

    bare = extract.run(Project(root=folder))
    assert bare.ok, bare.render()
    assert bare.features is not None and bare.features.features
    assert bare.drawing is None

    skipped = [s for s in bare.steps if s.status is StepStatus.SKIPPED]
    assert skipped, "expected the drawing steps to be skipped"
    for step in skipped:
        assert "no Drawing" in step.detail, step.detail


def test_a_skip_names_only_what_is_actually_missing(result):
    """A step needing CAD and a drawing, in a project with CAD, must not claim CAD is missing."""
    present = {a.kind for a in result.project.artifacts()}
    for step in result.steps:
        if step.status is not StepStatus.SKIPPED:
            continue
        for kind in step.needs:
            if ArtifactKind(kind) in present:
                assert ArtifactKind(kind).label not in step.detail, step.detail


def test_an_empty_folder_fails_without_raising(tmp_path):
    folder = tmp_path / "Empty_Project"
    folder.mkdir()
    empty = extract.run(Project(root=folder))

    assert empty.steps[0].warnings, "an empty project should say what it is missing"
    assert all(s.status is not StepStatus.FAILED for s in empty.steps[1:])


# --- nothing is claimed without a source ----------------------------------------------------------


def test_every_controlled_claim_cites_both_the_drawing_and_the_cad(result):
    """Control is derived from two artifacts agreeing, never asserted by hand.

    A drawing that puts a tolerance on a size is stating the feature is controlled; a detected
    feature of that size is what it is stating it about. Either source alone proves nothing.
    """
    if result.drawing is None:
        pytest.skip("this project has no drawing")

    for feature_id, fact in result.controlled.items():
        kinds = {e.kind for e in fact.evidence}
        assert SourceKind.DRAWING in kinds, f"{feature_id} has no drawing citation"
        assert SourceKind.CAD in kinds, f"{feature_id} has no CAD measurement"


def test_every_drawing_citation_quotes_the_text_it_was_read_from(result):
    """The locator is what makes a reading checkable against the page."""
    if result.drawing is None:
        pytest.skip("this project has no drawing")

    for fact in result.controlled.values():
        for evidence in fact.evidence:
            if evidence.kind is SourceKind.DRAWING:
                assert "page" in evidence.locator
                assert "'" in evidence.locator or '"' in evidence.locator


def test_controlled_faces_come_only_from_trustworthy_evidence(result):
    controlled = result.controlled_face_ids()
    if not controlled:
        pytest.skip("nothing controlled in this project")
    assert result.features is not None
    for feature_id, fact in result.controlled.items():
        if set(result.features.features[feature_id].face_ids) & controlled:
            assert fact.trustworthy, f"{feature_id} controlled on {fact.state}"


def test_unresolved_pairings_are_kept_rather_than_resolved(result):
    """A disagreement is information. Each side must survive with its own source attached."""
    for conflict in result.log.conflicts:
        assert conflict.left_value != conflict.right_value
        assert conflict.left.locator and conflict.right.locator
        assert conflict.left.kind is not conflict.right.kind


def test_no_conflict_is_surfaced_anywhere(result):
    """A conflict is what two *confirmed* facts do when they disagree.

    Nothing is confirmed yet - no association has been checked by a person - so a size match whose
    count disagrees is an open question about the pairing, not a conflict about the number. It is
    recorded internally and must not reach the interface or the agent under that name.
    """
    from fastcae.api.app import app

    for route in app.routes:
        assert "conflict" not in getattr(route, "path", "").lower()

    for step in result.steps:
        for key in step.produced:
            assert "conflict" not in key.lower(), f"{step.id} publishes {key!r}"


def test_a_diameter_is_never_asserted_without_evidence(result):
    """The diameter symbol does not survive text extraction, so a bare value is not known to be
    one. Where an association depends on it being a diameter, that inference is cited."""
    if result.drawing is None:
        pytest.skip("this project has no drawing")

    for callout in result.drawing.callouts:
        if callout.is_diameter:
            assert any(mark in callout.raw for mark in "⌀øØ"), callout.raw

    for feature_id, fact in result.controlled.items():
        derived = [e for e in fact.evidence if e.kind is SourceKind.DERIVED]
        assert derived, f"{feature_id} was matched by size without citing the inference"


def test_no_mass_is_asserted_anywhere(result):
    """Volume is geometry; mass needs a density, and nothing in a folder states one.

    A density assumed in code would be indistinguishable, three stages later, from one that was
    read off a document.
    """
    assert result.exact is not None
    with pytest.raises(TypeError):
        result.exact.mass_kg()  # type: ignore[call-arg]
