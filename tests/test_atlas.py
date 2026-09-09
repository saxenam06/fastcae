"""The face atlas and the selection tools built on it.

These are the tools a design parameter will be authored with, so they are tested on *properties*
rather than on a part. Growing a selection must be monotone in its angle; similarity must never
cross a surface type; every measured dihedral must be a real angle. Those hold for a casting, a
bracket or a shaft.

An earlier ``grow`` compared face-average normals and returned only its seed, and the test of the
day passed because it asserted only that the seed was included and that the result was not the
whole part. The assertions here are the ones that would have failed.
"""

from __future__ import annotations

import pytest

from fastcae import extract
from fastcae.project import ArtifactKind, discover


@pytest.fixture(scope="module")
def result():
    for project in discover():
        if project.first(ArtifactKind.CAD):
            return extract.run(project)
    pytest.skip("no project with CAD under assets/")


@pytest.fixture(scope="module")
def atlas(result):
    if result.atlas is None:
        pytest.skip("no atlas was built")
    return result.atlas


@pytest.fixture(scope="module")
def seed(atlas):
    """The largest face that has neighbours. Deterministic, and defined for any part."""
    candidates = [f for f in atlas.faces.values() if f.neighbours]
    if not candidates:
        pytest.skip("no face has neighbours")
    return max(candidates, key=lambda f: f.area).face_id


# --- the atlas knows what it was built from ------------------------------------------------------


def test_the_atlas_is_bound_to_the_cad_it_was_built_from(result, atlas):
    """Face ids are positions in explorer order and do not survive a re-export.

    An atlas that cannot say which file it measured cannot detect that a selection has been carried
    onto different geometry, which is the failure it exists to make visible.
    """
    assert atlas.geometry_hash, "the atlas does not know which geometry it describes"
    assert atlas.geometry_hash == result.cad_digest


def test_every_face_is_measured(atlas, result):
    assert result.exact is not None
    assert len(atlas) == result.exact.n_faces
    for face in atlas.faces.values():
        assert face.surface_type
        assert face.area > 0.0, f"face {face.face_id} has no usable area"


def test_the_diagonal_is_measured_not_assumed(atlas):
    """Every scale-dependent tolerance is derived from it, so a zero would silently disable them."""
    assert atlas.diagonal_mm > 0.0


# --- measured dihedrals --------------------------------------------------------------------------


def test_dihedrals_are_real_angles_and_symmetric(atlas):
    for face in atlas.faces.values():
        for neighbour_id, angle in face.dihedral.items():
            assert 0.0 <= angle <= 180.0, f"{face.face_id}->{neighbour_id} is {angle}"
            assert neighbour_id in atlas.faces
            back = atlas[neighbour_id].dihedral.get(face.face_id)
            assert back == pytest.approx(angle), "an angle across an edge has to read the same way"


def test_most_faces_can_be_walked(atlas):
    """Growing walks measured dihedrals, so a face without any is unreachable.

    The implementation that compared analytic normals left every torus, cone, sphere and b-spline
    with nothing to compare, which silently made half the part unselectable.
    """
    with_edges = sum(1 for f in atlas.faces.values() if f.dihedral)
    assert with_edges > len(atlas) * 0.9, f"only {with_edges} of {len(atlas)} faces have dihedrals"


# --- growing a selection -------------------------------------------------------------------------


def test_growing_includes_the_seed(atlas, seed):
    assert seed in atlas.grow([seed], max_dihedral_deg=1.0)


def test_growing_returns_only_real_faces(atlas, seed):
    for face_id in atlas.grow([seed], max_dihedral_deg=90.0):
        assert face_id in atlas.faces


def test_growing_is_monotone_in_the_angle(atlas, seed):
    """A wider crease can only ever admit more. If it does not, the walk is not using the angle."""
    previous: set[int] = set()
    sizes = []
    for angle in (1.0, 15.0, 40.0, 90.0, 179.0):
        grown = atlas.grow([seed], max_dihedral_deg=angle)
        assert previous <= grown, f"{angle} deg admitted fewer faces than the step before it"
        previous = grown
        sizes.append(len(grown))
    assert sizes[-1] > sizes[0], "the angle changes nothing, so nothing is being walked"


def test_growing_far_enough_leaves_the_seed_behind(atlas, seed):
    """At a wide angle a selection has to spread. Returning the seed alone is the old failure."""
    assert len(atlas.grow([seed], max_dihedral_deg=90.0)) > 1


def test_growing_respects_its_ceiling(atlas, seed):
    assert len(atlas.grow([seed], max_dihedral_deg=179.0, max_faces=5)) <= 5 + len(
        atlas[seed].dihedral
    )


# --- similarity --------------------------------------------------------------------------------


def test_similar_never_crosses_a_surface_type(atlas):
    """Matching on size alone would sweep up every unrelated patch of the same area."""
    for face in list(atlas.faces.values())[:200]:
        for other_id in atlas.similar(face.face_id):
            assert atlas[other_id].surface_type == face.surface_type


def test_similar_holds_its_radius_tolerance(atlas):
    """A band wide enough to span two hole families merges patterns that are not the same."""
    tolerance = max(atlas.diagonal_mm * 5e-5, 1e-3)
    rounds = [f for f in atlas.faces.values() if f.radius_mm is not None][:200]
    if not rounds:
        pytest.skip("this part has no round faces")
    for face in rounds:
        for other_id in atlas.similar(face.face_id):
            other = atlas[other_id]
            assert other.radius_mm is not None
            assert abs(other.radius_mm - face.radius_mm) <= tolerance + 1e-9


def test_similar_includes_the_face_asked_about(atlas, seed):
    assert seed in atlas.similar(seed)


# --- visibility ----------------------------------------------------------------------------------


def test_something_is_visible_from_outside(atlas):
    """A closed solid seen from outside has an outside. None would mean every ray was blocked."""
    exterior = atlas.exterior_faces()
    assert exterior, "no face is reachable from outside, so the ray cast is not working"
    assert len(exterior) < len(atlas), "every face exterior means nothing was occluded"
