"""The part on a grid of cubes: which cubes are metal (:func:`part_grid`), and the structure
the voxel model assembles its stiffness on (:class:`_Structure`) - hexahedra on the grid's nodes,
each cube as stiff as it is told, the deck's held nodes taken out."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import warp as wp
import warp.fem as fem
from scipy.spatial import cKDTree

from ..designs.optimise import Mix
from ..geometry.field import Grid
from ..space.interfaces import deck_roles
from ..space.model import Evidence
from ..space.physics import _surface_points, _Voxels

if TYPE_CHECKING:
    from ..extract import Extraction


CELL_MM = 8.0


@fem.integrand
def _scaled(s: fem.Sample, u: fem.Field, v: fem.Field, rho: fem.Field, lame: wp.vec2):
    strain = fem.D(u, s)
    stress = rho(s) * (
        2.0 * lame[1] * strain + lame[0] * wp.trace(strain) * wp.identity(n=3, dtype=float)
    )
    return wp.ddot(fem.D(v, s), stress)


def part_grid(extraction: Extraction, cell_mm: float = CELL_MM) -> tuple[Grid, np.ndarray]:
    """The part as cubes: a grid over it, and which cubes are metal - a ray up each column, filled
    between where it enters and leaves the surface."""
    from trimesh import Trimesh
    from trimesh.ray.ray_pyembree import RayMeshIntersector

    tess = extraction.tess
    assert tess is not None
    lo = tess.vertices.min(axis=0) - cell_mm
    hi = tess.vertices.max(axis=0) + cell_mm
    shape = tuple(int(np.ceil((hi[i] - lo[i]) / cell_mm)) + 1 for i in range(3))
    grid = Grid(origin=tuple(float(v) for v in lo), spacing_mm=cell_mm, shape=shape)
    mesh = Trimesh(vertices=tess.vertices, faces=tess.triangles, process=False, validate=False)
    rays = RayMeshIntersector(mesh)
    # Columns a hair off the lattice, so no ray runs exactly along an edge of the surface.
    ii, jj = np.meshgrid(np.arange(shape[0]), np.arange(shape[1]), indexing="ij")
    x = lo[0] + ii.ravel() * cell_mm + 0.0137 * cell_mm
    y = lo[1] + jj.ravel() * cell_mm + 0.0291 * cell_mm
    origins = np.stack([x, y, np.full(x.shape, lo[2] - cell_mm)], axis=1)
    directions = np.tile([0.0, 0.0, 1.0], (len(origins), 1))
    where, ray, _ = rays.intersects_location(origins, directions, multiple_hits=True)
    solid = np.zeros(shape, bool)
    order = np.lexsort((where[:, 2], ray))
    ray, z = ray[order], where[order, 2]
    starts = np.flatnonzero(np.r_[True, ray[1:] != ray[:-1]])
    ends = np.r_[starts[1:], len(ray)]
    centres_z = lo[2] + np.arange(shape[2]) * cell_mm
    for a, b in zip(starts, ends, strict=True):
        hits = z[a:b]
        if len(hits) % 2:
            hits = hits[:-1]  # a ray that grazed: its last crossing has no partner
        i, j = divmod(int(ray[a]), shape[1])
        for enter, leave in hits.reshape(-1, 2):
            solid[i, j, (centres_z >= enter) & (centres_z <= leave)] = True
    return grid, solid


class _Structure(_Voxels):
    """The part and every candidate as cubes, each cube's stiffness scaled on its own."""

    def __init__(self, cells: np.ndarray, grid: Grid, lame: tuple[float, float]) -> None:
        super().__init__(cells, np.asarray(grid.origin), grid.spacing_mm, lame)
        self.lame = lame
        self.rho_space = fem.make_polynomial_space(self.geo, degree=0, dtype=float)
        centres = self.rho_space.node_positions().numpy().astype(np.float64)
        at = np.rint((centres - np.asarray(grid.origin)) / grid.spacing_mm).astype(np.int64)
        # Which of our cells each of Warp's cell values belongs to.
        ours = {tuple(c): n for n, c in enumerate(cells.tolist())}
        self.value_of = np.array([ours[tuple(c)] for c in at.tolist()], np.int64)

    def assemble(self, stiffness: np.ndarray):  # type: ignore[no-untyped-def]
        """The stiffness matrix with each cell as stiff as ``stiffness`` says (1 is the metal)."""
        rho = self.rho_space.make_field()
        rho.dof_values = wp.array(stiffness[self.value_of].astype(np.float32), dtype=float)
        return fem.integrate(
            _scaled,
            fields={"u": fem.make_trial(self.space), "v": fem.make_test(self.space), "rho": rho},
            values={"lame": wp.vec2(*self.lame)},
            output_dtype=float,
        )


def boundary(
    extraction: Extraction, setup: Any, mix: Mix, structure: _Voxels
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """The nodes the deck holds, and each load case's forces on the nodes: the deck's held and
    loaded groups found on the grid by the CAD faces they lie on."""
    tess = extraction.tess
    assert tess is not None
    tree = cKDTree(structure.nodes)

    def near(points: np.ndarray) -> np.ndarray:
        if not len(points):
            return np.empty(0, np.int64)
        found = [np.asarray(i, np.int64) for i in tree.query_ball_point(points, 0.9 * CELL_MM)]
        ids = np.unique(np.concatenate([*found, np.empty(0, np.int64)]))
        return ids if len(ids) else np.unique(tree.query(points)[1])

    groups = (extraction.anchoring or {}).get("groups", {})
    roles = deck_roles(setup)
    held_faces = sorted(
        {
            f
            for g, a in groups.items()
            if roles.get(g, (None,))[0] is Evidence.DECK_SUPPORT
            for f in a["faces"]
        }
    )
    fixed = near(_surface_points(tess, held_faces))
    forces = {}
    for case in mix.cases:
        force = np.zeros((len(structure.nodes), 3))
        for g, vector in case.forces.items():
            if g not in groups:
                continue
            ids = near(_surface_points(tess, groups[g]["faces"]))
            if len(ids):
                force[ids] += np.asarray(vector) / len(ids)
        forces[case.name] = force
    return fixed, forces
