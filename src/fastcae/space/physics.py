"""Where added metal would help: the part solved under the deck's own loads and supports, then its
design space filled with a material that follows the part as it deflects.

Two solves, not one. A single model with the design space as a very soft material is the textbook
way, and it is badly conditioned: a large soft region makes the iterative solver crawl, and a soft
region large enough still stiffens the part. Its limit as the material gets softer is exactly two
separate problems - the part alone, then the design space alone with its surface pinned to wherever
the part moved - and each of those is well conditioned.

How much strain energy the filler would carry at full stiffness, cell by cell, is the classic first
measure of what adding material there is worth - the first step of the optimisation that comes
later, and nothing more. The grid is coarse (a voxel model reads the seats' tilt about a seventh
off), which is fine for ranking where metal helps; no number from here becomes a record.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import warp as wp
import warp.examples.fem.utils as fem_utils
import warp.fem as fem
from scipy.spatial import cKDTree
from warp.sparse import bsr_diag

from ..geometry.brep import Tessellation
from ..geometry.field import Grid
from .interfaces import deck_roles
from .model import Evidence, Label

E_DEFAULT = 169_000.0
NU_DEFAULT = 0.275

wp.config.log_level = wp.LOG_WARNING


@fem.integrand
def _elasticity(s: fem.Sample, u: fem.Field, v: fem.Field, lame: wp.vec2):
    strain = fem.D(u, s)
    stress = 2.0 * lame[1] * strain + lame[0] * wp.trace(strain) * wp.identity(n=3, dtype=float)
    return wp.ddot(fem.D(v, s), stress)


def _block_mean(mask: np.ndarray, f: int) -> np.ndarray:
    nx, ny, nz = (s // f for s in mask.shape)
    m = mask[: nx * f, : ny * f, : nz * f].reshape(nx, f, ny, f, nz, f)
    return m.mean(axis=(1, 3, 5), dtype=np.float32)


def _surface_points(tess: Tessellation, faces: list[int]) -> np.ndarray:
    tri = tess.triangles[np.isin(tess.face_id, np.asarray(faces))]
    if not len(tri):
        return np.empty((0, 3))
    return np.concatenate([tess.vertices[np.unique(tri)], tess.vertices[tri].mean(axis=1)])


class _Voxels:
    """Hexahedral cells on a lattice, their nodes, and their stiffness matrix."""

    def __init__(
        self, cells: np.ndarray, centre0: np.ndarray, big: float, lame: tuple[float, float]
    ) -> None:
        self.cells = cells
        self.big = big
        self.corner0 = centre0 - 0.5 * big
        for translation in (self.corner0, centre0):
            volume = wp.Volume.allocate_by_voxels(
                voxel_points=wp.array(cells, dtype=wp.vec3i),
                voxel_size=big,
                translation=wp.vec3(*translation),
            )
            geo = fem.Nanogrid(volume)
            space = fem.make_polynomial_space(geo, degree=1, dtype=wp.vec3)
            nodes = space.node_positions().numpy().astype(np.float64)
            # Nodes must sit on the cells' corners; Warp versions differ on where a voxel starts.
            if np.median(np.abs(((nodes[:200] - self.corner0) / big) % 1.0 - 0.5)) > 0.25:
                break
        else:
            raise RuntimeError("the voxel nodes do not line up with the cells")
        self.volume, self.geo, self.space, self.nodes = volume, geo, space, nodes
        self.k = fem.integrate(
            _elasticity,
            fields={"u": fem.make_trial(space), "v": fem.make_test(space)},
            values={"lame": wp.vec2(*lame)},
            output_dtype=float,
        )
        index = np.rint((nodes - self.corner0) / big).astype(np.int64)
        self.dims = index.max(axis=0) + 2
        self.key = self._key(index)
        self.order = np.argsort(self.key)

    def _key(self, index: np.ndarray) -> np.ndarray:
        return (index[:, 0] * self.dims[1] + index[:, 1]) * self.dims[2] + index[:, 2]

    def find(self, positions: np.ndarray) -> np.ndarray:
        """Which node sits at each position, -1 where none does."""
        index = np.rint((positions - self.corner0) / self.big).astype(np.int64)
        inside = np.all((index >= 0) & (index < self.dims), axis=1)
        key = self._key(np.clip(index, 0, self.dims - 1))
        sorted_key = self.key[self.order]
        pos = np.clip(np.searchsorted(sorted_key, key), 0, len(self.order) - 1)
        hit = inside & (sorted_key[pos] == key)
        return np.where(hit, self.order[pos], -1)

    def energy(self, u: np.ndarray, lame: tuple[float, float]) -> np.ndarray:
        """Strain energy density of each cell at full stiffness, from its eight corners."""
        corner = np.zeros((len(self.cells), 2, 2, 2), np.int64)
        valid = np.ones(len(self.cells), bool)
        for a in (0, 1):
            for b in (0, 1):
                for c in (0, 1):
                    at = self.corner0 + (self.cells + np.array([a, b, c])) * self.big
                    found = self.find(at)
                    valid &= found >= 0
                    corner[:, a, b, c] = np.maximum(found, 0)
        uc = u[corner]
        grad = (
            np.stack(
                [
                    (uc[:, 1] - uc[:, 0]).mean(axis=(1, 2)),
                    (uc[:, :, 1] - uc[:, :, 0]).mean(axis=(1, 2)),
                    (uc[:, :, :, 1] - uc[:, :, :, 0]).mean(axis=(1, 2)),
                ],
                axis=2,
            )
            / self.big
        )
        eps = 0.5 * (grad + grad.transpose(0, 2, 1))
        lam, mu = lame
        trace = np.trace(eps, axis1=1, axis2=2)
        out = 0.5 * (lam * trace**2 + 2.0 * mu * np.einsum("nij,nij->n", eps, eps))
        out[~valid] = 0.0
        return out


def _solve(
    k,
    rhs: np.ndarray,
    fixed: np.ndarray,
    values: np.ndarray | None,
    start: np.ndarray | None,
    tol: float = 1e-6,
):  # type: ignore[no-untyped-def]
    """Conjugate gradients with the ``fixed`` nodes held - at zero, or at ``values``."""
    n = len(rhs)
    blocks = np.zeros((n, 3, 3), np.float32)
    blocks[fixed] = np.eye(3)
    b = wp.array(rhs.astype(np.float32), dtype=wp.vec3)
    pinned = None if values is None else wp.array(values.astype(np.float32), dtype=wp.vec3)
    fem.project_linear_system(k, b, bsr_diag(wp.array(blocks, dtype=wp.mat33)), pinned)
    x = wp.array(
        (start if start is not None else np.zeros((n, 3))).astype(np.float32), dtype=wp.vec3
    )
    t0 = time.perf_counter()
    err, its = fem_utils.bsr_cg(k, x=x, b=b, tol=tol, max_iters=30_000, quiet=True)
    wp.synchronize()
    return x.numpy().astype(np.float64), int(its), float(err), time.perf_counter() - t0


def preview(  # noqa: C901
    grid: Grid,
    labels: np.ndarray,
    tess: Tessellation,
    anchoring: dict[str, Any],
    setup: Any,
    factor: int = 2,
    say=print,  # type: ignore[no-untyped-def]
    metal_share: float = 0.25,
) -> dict[str, Any]:
    """Benefit of adding metal at each cell of the design space, on its own grid (0 outside it),
    and what the two solves took."""
    h = grid.spacing_mm
    big = factor * h
    part = _block_mean(labels == Label.PART, factor) >= metal_share
    band = ~part & (_block_mean(labels == Label.DESIGN, factor) >= 0.25)
    centre0 = np.asarray(grid.origin) + 0.5 * (factor - 1) * h
    material = next(iter(setup.materials), None) if setup is not None else None
    young = float(material.young) if material else E_DEFAULT
    poisson = float(material.poisson) if material else NU_DEFAULT
    lame = (young * poisson / ((1 + poisson) * (1 - 2 * poisson)), young / (2 * (1 + poisson)))

    # 1. The part alone, under the deck's loads and supports.
    t0 = time.perf_counter()
    metal = _Voxels(np.argwhere(part).astype(np.int32), centre0, big, lame)
    roles = deck_roles(setup)
    groups = anchoring.get("groups", {})
    tree = cKDTree(metal.nodes)

    def near(points: np.ndarray) -> np.ndarray:
        if not len(points):
            return np.empty(0, np.int64)
        found = [
            np.asarray(ids, dtype=np.int64) for ids in tree.query_ball_point(points, 0.9 * big)
        ]
        ids = np.unique(np.concatenate([*found, np.empty(0, np.int64)]))
        return ids if len(ids) else np.unique(tree.query(points)[1])

    held = sorted(
        {
            f
            for g, a in groups.items()
            if roles.get(g, (None,))[0] is Evidence.DECK_SUPPORT
            for f in a["faces"]
        }
    )
    fixed = near(_surface_points(tess, held))
    force = np.zeros((len(metal.nodes), 3))
    loads = {n.group: n.values for n in setup.nodal_loads}
    applied = []
    for d in setup.distributing:
        values = loads.get(d.reference)
        if values is None or d.group not in groups:
            continue
        ids = near(_surface_points(tess, groups[d.group]["faces"]))
        vector = np.array([values.get(c, 0.0) for c in ("FX", "FY", "FZ")], float)
        if len(ids):
            force[ids] += vector / len(ids)
            applied.append({"group": d.group, "nodes": int(len(ids)), "force_N": vector.tolist()})
    u_metal, its1, err1, s1 = _solve(metal.k, force, fixed, None, None)
    magnitude = np.linalg.norm(u_metal, axis=1)
    if say:
        say(
            f"  part: {len(metal.cells):,} cells, {3 * len(metal.nodes):,} unknowns, "
            f"CG {its1} its in {s1:.0f} s"
        )

    # 2. The design space alone, its surface pinned where the part moved it.
    filler = _Voxels(np.argwhere(band).astype(np.int32), centre0, big, lame)
    shared = metal.find(filler.nodes)
    pinned = np.flatnonzero(shared >= 0)
    values = np.zeros((len(filler.nodes), 3))
    values[pinned] = u_metal[shared[pinned]]
    u_filler, its2, err2, s2 = _solve(
        filler.k, np.zeros((len(filler.nodes), 3)), pinned, values, values
    )
    if say:
        say(
            f"  filler: {len(filler.cells):,} cells, {len(pinned):,} nodes on the part, "
            f"CG {its2} its in {s2:.0f} s"
        )

    energy = filler.energy(u_filler, lame)
    coarse = np.zeros(part.shape, np.float32)
    coarse[filler.cells[:, 0], filler.cells[:, 1], filler.cells[:, 2]] = energy
    fine = np.repeat(np.repeat(np.repeat(coarse, factor, 0), factor, 1), factor, 2)
    benefit = np.zeros(labels.shape, np.float32)
    nx, ny, nz = fine.shape
    benefit[:nx, :ny, :nz] = fine
    benefit[labels != Label.DESIGN] = 0.0
    loaded = np.abs(force).sum(axis=1) > 0
    return {
        "benefit": benefit,
        "stats": {
            "cell_mm": big,
            "part_cells": int(len(metal.cells)),
            "filler_cells": int(len(filler.cells)),
            "part_unknowns": int(3 * len(metal.nodes)),
            "filler_unknowns": int(3 * len(filler.nodes)),
            "filler_nodes_on_part": int(len(pinned)),
            "fixed_nodes": int(len(fixed)),
            "loads": applied,
            "part_cg": {"iterations": its1, "residual": err1, "seconds": round(s1, 1)},
            "filler_cg": {"iterations": its2, "residual": err2, "seconds": round(s2, 1)},
            "seconds": round(time.perf_counter() - t0, 1),
            "largest_displacement_mm": round(float(magnitude.max()), 4),
            "loaded_node_displacement_mm": round(float(magnitude[loaded].mean()), 4)
            if loaded.any()
            else None,
            "compliance_Nmm": round(float((force * u_metal).sum()), 1),
        },
    }
