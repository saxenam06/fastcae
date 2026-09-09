"""The signed distance field.

Tested against shapes whose answer is known in closed form rather than against the part in
``assets/``, because "is this the right distance" is a question a sphere can answer exactly and a
casting cannot.

Two defects were found this way and both are guarded below. Resolving the cells straddling the
surface by growing the outside into them biased every surface outward by a third of a voxel. And
calling any region that does not reach the edge of the grid solid filled in sealed voids, because
connectivity cannot tell the material inside a wall from the air inside a cavity.
"""

from __future__ import annotations

import numpy as np
import pytest
import trimesh

from fastcae.generate.field import (
    MAX_SPACING_MM,
    MIN_SPACING_MM,
    _inside_by_parity,
    _inside_by_winding,
    _point_triangle_distance,
    build_field,
    scale_spacing,
)
from fastcae.geometry.brep import Tessellation

RADIUS = 100.0


def as_tessellation(mesh) -> Tessellation:
    return Tessellation(
        vertices=np.asarray(mesh.vertices, dtype=np.float64),
        triangles=np.asarray(mesh.faces, dtype=np.int32),
        face_id=np.zeros(len(mesh.faces), dtype=np.int32),
        face_ids=[0],
        deflection_mm=0.0,
        angle_deg=0.0,
        faces_without_triangles=[],
    )


@pytest.fixture(scope="module")
def sphere():
    return build_field(
        as_tessellation(trimesh.creation.icosphere(subdivisions=4, radius=RADIUS)),
        spacing_mm=8.0,
    )


# --- distance ------------------------------------------------------------------------------------


def test_point_triangle_distance_is_exact():
    """A dense sampling of the triangle is an upper bound on the true distance and converges to
    it, so a correct answer sits just below the sampling and the gap closes as it refines."""
    rng = np.random.default_rng(0)
    a, b, c = (rng.normal(size=(300, 3)) for _ in range(3))
    p = rng.normal(size=(300, 3)) * 2
    mine = _point_triangle_distance(p, a, b, c)

    longest = np.maximum.reduce(
        [
            np.linalg.norm(b - a, axis=1),
            np.linalg.norm(c - b, axis=1),
            np.linalg.norm(a - c, axis=1),
        ]
    )

    previous = None
    for steps in (30, 60, 120):
        u = np.linspace(0.0, 1.0, steps)
        bary = np.array([(x, y, 1 - x - y) for x in u for y in u if x + y <= 1.0])
        sampled = np.array(
            [
                np.linalg.norm(bary @ np.stack([a[i], b[i], c[i]]) - p[i], axis=1).min()
                for i in range(len(p))
            ]
        )
        assert (mine <= sampled + 1e-12).all(), "further than a point that is on the triangle"
        gap = float(((sampled - mine) / longest).max())
        assert gap < 3.0 / steps, "gap is wider than the sampling can explain"
        if previous is not None:
            assert gap < previous, "the gap does not close as the sampling refines"
        previous = gap


def test_a_sphere_reproduces_its_own_distance_function(sphere):
    """The one shape where every band value has an exact answer to be compared against."""
    truth = np.linalg.norm(sphere.grid.centres(sphere.band_index), axis=1) - RADIUS
    error = np.abs(sphere.band_mm - truth)

    # A faceted icosphere sits inside the ideal sphere by its own sagitta, and that - not the voxel
    # size - is the accuracy floor. The distance itself is computed exactly.
    assert error.max() < 0.2, f"max error {error.max():.3f} mm on an 8 mm voxel"
    assert (np.sign(sphere.band_mm) == np.sign(truth)).mean() > 0.99


def test_a_sphere_reproduces_its_volume(sphere):
    exact = 4.0 / 3.0 * np.pi * RADIUS**3
    assert abs(sphere.volume_mm3() - exact) / exact < 0.02


def test_the_band_is_a_band(sphere):
    """It has to hold both sides of the surface, and nothing beyond its reach."""
    assert (np.abs(sphere.band_mm) <= sphere.reach_mm + 1e-6).all()
    assert (sphere.band_mm < 0).any() and (sphere.band_mm > 0).any()
    assert sphere.n_band < sphere.grid.n_cells


# --- sign ----------------------------------------------------------------------------------------


def test_a_sealed_void_is_not_filled_in():
    """The failure connectivity alone cannot see.

    A cavity sealed inside a solid and the material of the solid are both regions that never reach
    the edge of the grid. Only the surface's own winding separates them.
    """
    outer = trimesh.creation.box(extents=(200, 200, 200))
    inner = trimesh.creation.box(extents=(80, 80, 80))
    inner.invert()
    hollow = trimesh.util.concatenate([outer, inner])

    field = build_field(as_tessellation(hollow), spacing_mm=5.0)
    assert field.sample(np.array([[0.0, 0.0, 0.0]]))[0] > 0, "the void reads as solid"

    expected = 200.0**3 - 80.0**3
    assert abs(field.volume_mm3() - expected) / expected < 0.02


def test_a_through_hole_is_open():
    tube = trimesh.creation.annulus(r_min=30.0, r_max=100.0, height=120.0, sections=64)
    field = build_field(as_tessellation(tube), spacing_mm=5.0)

    probe = np.array([[0.0, 0.0, 0.0], [65.0, 0.0, 0.0], [0.0, 0.0, 200.0]])
    bore, wall, above = field.sample(probe)
    assert bore > 0 and above > 0, "the bore or the space above it reads as solid"
    assert wall < 0, "the wall reads as empty"


def test_parity_and_winding_agree():
    """Two independent answers to the same question.

    Ray parity counts crossings; the winding number measures solid angle and has no ray to graze.
    They are used in that order only because one is faster.
    """
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=RADIUS)
    tess = as_tessellation(mesh)
    field = build_field(tess, spacing_mm=20.0)

    rng = np.random.default_rng(0)
    cells = rng.choice(field.grid.n_cells, size=400, replace=False)
    by_ray = _inside_by_parity(tess, field.grid, cells)
    by_angle = _inside_by_winding(tess, field.grid, cells)
    assert (by_ray == by_angle).all()


# --- the properties a campaign depends on --------------------------------------------------------


def test_the_same_input_gives_the_same_field():
    """Two variants must differ because the design differs, never because a rebuild wandered."""
    tess = as_tessellation(trimesh.creation.box(extents=(120, 90, 60)))
    first = build_field(tess, spacing_mm=10.0)
    second = build_field(tess, spacing_mm=10.0)

    assert first.grid == second.grid
    assert np.array_equal(first.band_index, second.band_index)
    assert np.array_equal(first.band_mm, second.band_mm)
    assert np.array_equal(first.inside, second.inside)


def test_sampling_agrees_with_the_band_it_was_built_from(sphere):
    points = sphere.grid.centres(sphere.band_index[::37])
    assert np.allclose(sphere.sample(points), sphere.band_mm[::37], atol=1e-4)


def test_the_grid_holds_the_whole_part_with_room_around_it():
    tess = as_tessellation(trimesh.creation.box(extents=(120, 90, 60)))
    field = build_field(tess, spacing_mm=10.0)

    origin = np.asarray(field.grid.origin)
    far = origin + (np.asarray(field.grid.shape) - 1) * field.grid.spacing_mm
    assert (origin < tess.vertices.min(axis=0)).all()
    assert (far > tess.vertices.max(axis=0)).all()
    # The outside has to be reachable, or there is nothing for a ray to escape into.
    assert not field.inside[0, 0, 0]
    assert not field.inside[-1, -1, -1]


def test_voxel_size_is_derived_from_the_model():
    """Absolute in millimetres would be an assumption about part size, as everywhere else here."""
    assert scale_spacing(2000.0) == pytest.approx(2.5)
    assert scale_spacing(1.0) == MIN_SPACING_MM
    assert scale_spacing(1e9) == MAX_SPACING_MM
