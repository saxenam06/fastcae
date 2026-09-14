"""The design solved directly on its voxel grid, on the GPU, with NVIDIA Warp - no mesh. Its solid
cells, resampled from the 3 mm field it was built on to a chosen cell size, become trilinear hex
elements (a sparse NanoVDB grid); the stiffness is assembled on the GPU and solved by conjugate
gradient with a diagonal preconditioner. Nodes within a cell of the bolt holes are held; each seat's
force is shared equally by the nodes within a cell of its surface. The same metrics as every solver.

    python solve_warp_voxel.py 6 5 4        # cell sizes, mm
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np
import warp as wp
import warp.examples.fem.utils as fem_utils
import warp.fem as fem
from common import E_MPA, NU, OUT, SEATS, metrics, stress_from_strain, von_mises
from scipy.spatial import cKDTree
from warp.sparse import bsr_diag

wp.config.log_level = wp.LOG_WARNING


@fem.integrand
def elasticity_form(s: fem.Sample, u: fem.Field, v: fem.Field, lame: wp.vec2):
    strain = fem.D(u, s)
    stress = 2.0 * lame[1] * strain + lame[0] * wp.trace(strain) * wp.identity(n=3, dtype=float)
    return wp.ddot(fem.D(v, s), stress)


def solid_cells(h: float) -> tuple[np.ndarray, np.ndarray]:
    """The integer coordinates and centres of the solid cells of a lattice of spacing ``h`` over the
    design's 3 mm field - solid where the field's nearest cell is."""
    f = np.load(OUT / "field.npz")
    origin, spacing, shape = f["origin"], float(f["spacing"]), tuple(int(x) for x in f["shape"])
    inside = np.unpackbits(f["inside"], count=int(np.prod(shape))).astype(bool).reshape(shape)
    extent = np.asarray(shape) * spacing
    count = np.ceil(extent / h).astype(int)
    gi, gj = np.meshgrid(np.arange(count[0]), np.arange(count[1]), indexing="ij")
    ijk_all = []
    for k in range(count[2]):
        centre = origin + np.stack([gi, gj, np.full_like(gi, k)], axis=-1) * h
        idx = np.clip(np.rint((centre - origin) / spacing).astype(int), 0, np.asarray(shape) - 1)
        solid = inside[idx[..., 0], idx[..., 1], idx[..., 2]]
        if solid.any():
            ii, jj = np.nonzero(solid)
            ijk_all.append(np.stack([ii, jj, np.full_like(ii, k)], axis=1))
    ijk = np.concatenate(ijk_all)
    return ijk, origin


def surface_points(setup: dict) -> dict[str, np.ndarray]:
    """Points on each seat's surface and on the bolt holes, from the design's own surface."""
    s = np.load(OUT / "surface.npz")
    v, t, fid = s["vertices"], s["triangles"], s["face_id"]
    out = {}
    for name in SEATS:
        chosen = t[np.isin(fid, setup["seats"][name]["faces"])]
        out[name] = np.concatenate([v[np.unique(chosen)], v[chosen].mean(axis=1)])
    chosen = t[np.isin(fid, setup["bolt_faces"])]
    out["BOLTS"] = np.concatenate([v[np.unique(chosen)], v[chosen].mean(axis=1)])
    return out


def solve(h: float, setup: dict, points: dict) -> dict:
    started = time.time()
    ijk, origin = solid_cells(h)
    volume = wp.Volume.allocate_by_voxels(
        voxel_points=wp.array(ijk.astype(np.int32), dtype=wp.vec3i),
        voxel_size=h,
        translation=wp.vec3(*origin),
    )
    geo = fem.Nanogrid(volume)
    space = fem.make_polynomial_space(geo, degree=1, dtype=wp.vec3)
    nodes = space.node_positions().numpy().astype(np.float64)
    n = len(nodes)
    built = time.time() - started

    lam = E_MPA * NU / ((1 + NU) * (1 - 2 * NU))
    mu = E_MPA / (2 * (1 + NU))
    t0 = time.time()
    k = fem.integrate(
        elasticity_form,
        fields={"u": fem.make_trial(space), "v": fem.make_test(space)},
        values={"lame": wp.vec2(lam, mu)},
        output_dtype=float,
    )
    wp.synchronize()
    assemble = time.time() - t0

    tree = cKDTree(nodes)
    reach = 0.9 * h

    def near(pts: np.ndarray) -> np.ndarray:
        """The grid nodes within a cell of the given surface points - or, where the grid has none
        that close, each point's nearest node."""
        found = [np.asarray(ids, dtype=np.int64) for ids in tree.query_ball_point(pts, reach)]
        ids = np.unique(np.concatenate([*found, np.empty(0, np.int64)]))
        return ids if len(ids) else np.unique(tree.query(pts)[1])

    fixed = near(points["BOLTS"])
    seat_ids = {name: near(points[name]) for name in SEATS}
    force = np.zeros((n, 3), np.float32)
    for name, ids in seat_ids.items():
        force[ids] += np.asarray(setup["seats"][name]["force_N"], float) / len(ids)
    blocks = np.zeros((n, 3, 3), np.float32)
    blocks[fixed] = np.eye(3)
    projector = bsr_diag(wp.array(blocks, dtype=wp.mat33))
    rhs = wp.array(force, dtype=wp.vec3)
    fem.project_linear_system(k, rhs, projector)
    u = wp.zeros(n, dtype=wp.vec3)
    t0 = time.time()
    err, its = fem_utils.bsr_cg(k, x=u, b=rhs, tol=1e-6, max_iters=40_000, quiet=True)
    wp.synchronize()
    solve_s = time.time() - t0
    un = u.numpy().astype(np.float64)

    # Von Mises at each cell's centre from its eight corners: nodes hashed on the doubled lattice.
    def key_of(p):
        return np.rint(2.0 * (p - origin) / h).astype(np.int64)

    node_key = key_of(nodes)
    base = node_key.min(axis=0)
    dims = node_key.max(axis=0) - base + 3

    def flat(q):
        return ((q[:, 0] - base[0]) * dims[1] + (q[:, 1] - base[1])) * dims[2] + (q[:, 2] - base[2])

    order = np.argsort(flat(node_key))
    sorted_keys = flat(node_key)[order]
    centres = origin + ijk * h
    # Corners at centre ± h/2 on this lattice; if Warp's voxels span [ijk, ijk+1] instead, shift.
    probe = key_of(centres[:1] + 0.5 * h)
    shift = 0.0 if np.isin(flat(probe), sorted_keys).all() else 0.5 * h
    centres = centres + shift
    corner = np.zeros((len(ijk), 2, 2, 2), np.int64)
    for a in (0, 1):
        for b in (0, 1):
            for c in (0, 1):
                q = key_of(centres + h * (np.array([a, b, c]) - 0.5))
                pos = np.searchsorted(sorted_keys, flat(q))
                corner[:, a, b, c] = order[np.clip(pos, 0, len(order) - 1)]
    uc = un[corner]  # (m, 2, 2, 2, 3)
    grad = (
        np.stack(
            [
                (uc[:, 1] - uc[:, 0]).mean(axis=(1, 2)),
                (uc[:, :, 1] - uc[:, :, 0]).mean(axis=(1, 2)),
                (uc[:, :, :, 1] - uc[:, :, :, 0]).mean(axis=(1, 2)),
            ],
            axis=2,
        )
        / h
    )  # (m, 3 components, 3 directions)
    eps = 0.5 * (grad + grad.transpose(0, 2, 1))
    vm = von_mises(stress_from_strain(eps))
    weights = {name: np.ones(len(ids)) for name, ids in seat_ids.items()}
    result = metrics(
        {name: nodes[ids] for name, ids in seat_ids.items()},
        {name: un[ids] for name, ids in seat_ids.items()},
        weights,
        vm,
        np.full(len(vm), h**3),
        un,
    )
    np.savez_compressed(OUT / f"warp_{h:g}mm.npz", nodes=nodes, u=un)
    return {
        "cell_mm": h,
        "cells": int(len(ijk)),
        "nodes": int(n),
        "dof": int(3 * n),
        "fixed_nodes": int(len(fixed)),
        "seat_nodes": {name: int(len(ids)) for name, ids in seat_ids.items()},
        "grid_s": built,
        "assemble_s": assemble,
        "solve_s": solve_s,
        "iterations": int(its),
        "residual": float(err),
        "volume_mm3": float(len(ijk) * h**3),
        "metrics": result,
    }


def main() -> None:
    sizes = [float(a) for a in sys.argv[1:]] or [6.0, 5.0, 4.0]
    setup = json.loads((OUT / "setup.json").read_text(encoding="utf-8"))
    points = surface_points(setup)
    path = OUT / "warp_voxel.json"
    report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for h in sizes:
        try:
            report[f"{h:g}mm"] = solve(h, setup, points)
            r = report[f"{h:g}mm"]
            print(
                f"{h:g} mm: {r['dof']:,} dof, assemble {r['assemble_s']:.1f} s, solve {r['solve_s']:.1f} s "
                f"({r['iterations']} its), tilt max {r['metrics']['tilt_max_arcmin']:.3f}'",
                flush=True,
            )
        except Exception as error:  # noqa: BLE001 - one size failing must not lose the others
            report[f"{h:g}mm"] = {"error": repr(error)}
            print(f"{h:g} mm failed: {error!r}", flush=True)
        (OUT / "warp_voxel.json").write_text(json.dumps(report, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
