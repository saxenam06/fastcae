"""The cut-cell route: the finite cell method on the GPU with NVIDIA Warp - no mesh that follows the
part. A fixed lattice of hexahedral cells covers it; cells wholly inside are integrated as usual,
cells the surface cuts are integrated at sub-cell points - inside at full stiffness, outside at a
millionth of it - so the part's true shape enters through the quadrature, not the mesh. Seat loads
are integrated over the seat surfaces and the bolt holes held by a penalty over theirs, both at
points on the real surface.

The surface here is the TET10 mesh's own boundary, labelled as every solver's is, so this differs
from Code_Aster in how it discretises and in nothing else. Solved by cuDSS on the GPU - direct,
because cut cells with a millionth of a stiffness defeat simple iterative preconditioners.

    python solve_fcm_warp.py [cell_mm ...] [--degree 2] [--sub 4]
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np
import warp as wp
import warp.fem as fem
from common import E_MPA, NU, OUT, SEATS, metrics

wp.config.quiet = True

ALPHA = 1e-6  # the stiffness left in a cut cell's outside, relative to the part's


@wp.kernel
def classify(
    mesh: wp.uint64,
    points: wp.array(dtype=wp.vec3),
    max_dist: float,
    sign: wp.array(dtype=float),
    distance: wp.array(dtype=float),
):
    i = wp.tid()
    q = wp.mesh_query_point_sign_normal(mesh, points[i], max_dist)
    if q.result:
        closest = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
        sign[i] = q.sign
        distance[i] = wp.length(points[i] - closest)
    else:
        sign[i] = 1.0
        distance[i] = max_dist


def query(mesh: wp.Mesh, points: np.ndarray, max_dist: float) -> tuple[np.ndarray, np.ndarray]:
    """Inside (sign < 0) and distance to the surface of each point, on the GPU."""
    p = wp.array(points.astype(np.float32), dtype=wp.vec3)
    sign = wp.zeros(len(points), dtype=float)
    distance = wp.zeros(len(points), dtype=float)
    wp.launch(classify, dim=len(points), inputs=[mesh.id, p, max_dist, sign, distance])
    return sign.numpy() < 0.0, distance.numpy()


@fem.integrand
def stiffness_cells(s: fem.Sample, u: fem.Field, v: fem.Field, lame: wp.vec2, weight: wp.array(dtype=float)):
    strain = fem.D(u, s)
    stress = 2.0 * lame[1] * strain + lame[0] * wp.trace(strain) * wp.identity(n=3, dtype=float)
    return weight[s.element_index] * wp.ddot(fem.D(v, s), stress)


@fem.integrand
def stiffness_points(s: fem.Sample, u: fem.Field, v: fem.Field, lame: wp.vec2):
    strain = fem.D(u, s)
    stress = 2.0 * lame[1] * strain + lame[0] * wp.trace(strain) * wp.identity(n=3, dtype=float)
    return wp.ddot(fem.D(v, s), stress)


@fem.integrand
def penalty(s: fem.Sample, u: fem.Field, v: fem.Field, beta: float):
    return beta * wp.dot(u(s), v(s))


@fem.integrand
def traction(s: fem.Sample, v: fem.Field, t: wp.vec3):
    return wp.dot(t, v(s))


@fem.integrand
def value_at(s: fem.Sample, u: fem.Field):
    return u(s)


@fem.integrand
def von_mises_at(s: fem.Sample, u: fem.Field, lame: wp.vec2):
    e = fem.D(u, s)
    sig = 2.0 * lame[1] * e + lame[0] * wp.trace(e) * wp.identity(n=3, dtype=float)
    dev = sig - (wp.trace(sig) / 3.0) * wp.identity(n=3, dtype=float)
    return wp.sqrt(1.5 * wp.ddot(dev, dev))


def surface_points(nodes, tris, spacing: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Points spread over the given triangles no further apart than ``spacing``, each with its share
    of area and the triangle it came from: every triangle split into n x n by its longest edge."""
    p = nodes[tris[:, :3]]
    longest = np.max(np.linalg.norm(p[:, [1, 2, 0]] - p, axis=2), axis=1)
    n_split = np.maximum(1, np.ceil(longest / spacing)).astype(int)
    area = 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
    points, weights, owner = [], [], []
    for n in np.unique(n_split):
        rows = np.flatnonzero(n_split == n)
        # Centroids of the n² sub-triangles, in barycentric coordinates.
        bary = []
        for i in range(n):
            for j in range(n - i):
                bary.append(((i + 1 / 3) / n, (j + 1 / 3) / n))
                if i + j < n - 1:
                    bary.append(((i + 2 / 3) / n, (j + 2 / 3) / n))
        b = np.asarray(bary)
        a, c1, c2 = p[rows, 0], p[rows, 1], p[rows, 2]
        pts = a[:, None] + b[None, :, 0, None] * (c1 - a)[:, None] + b[None, :, 1, None] * (c2 - a)[:, None]
        points.append(pts.reshape(-1, 3))
        weights.append(np.repeat(area[rows] / (n * n), len(b)))
        owner.append(np.repeat(rows, len(b)))
    return np.concatenate(points), np.concatenate(weights), np.concatenate(owner)


def solve(h: float, degree: int, sub: int, mesh_data: dict, setup: dict) -> dict:
    started = time.time()
    nodes, tris, group = mesh_data["nodes"], mesh_data["tris"], mesh_data["group"]
    boundary = wp.Mesh(
        points=wp.array(nodes.astype(np.float32), dtype=wp.vec3),
        indices=wp.array(tris[:, :3].astype(np.int32).ravel(), dtype=int),
    )
    lo, hi = nodes.min(axis=0) - h, nodes.max(axis=0) + h
    count = np.ceil((hi - lo) / h).astype(int) + 1
    # Cells centred on lo + ijk h, classified by their centres - wholly inside when further than
    # their half-diagonal from the surface, cut when nearer.
    ii = np.stack(np.meshgrid(*[np.arange(c) for c in count], indexing="ij"), axis=-1).reshape(-1, 3)
    centres = lo + ii * h
    inside, distance = query(boundary, centres, 1e5)
    reach = 0.5 * np.sqrt(3.0) * h + 1e-3
    interior = inside & (distance > reach)
    near = distance <= reach
    # Sub-cell points of the cells the surface may cut.
    offsets = (np.stack(np.meshgrid(*[np.arange(sub)] * 3, indexing="ij"), axis=-1).reshape(-1, 3) + 0.5) / sub - 0.5
    near_ijk = ii[near]
    sub_points = (lo + near_ijk * h)[:, None, :] + offsets[None] * h
    sub_inside, _ = query(boundary, sub_points.reshape(-1, 3), 2.0 * h)
    sub_inside = sub_inside.reshape(len(near_ijk), -1)
    cut = sub_inside.any(axis=1)
    cut_ijk = near_ijk[cut]
    active = np.concatenate([ii[interior], cut_ijk])
    classify_s = time.time() - started

    t0 = time.time()
    volume = wp.Volume.allocate_by_voxels(
        voxel_points=wp.array(active.astype(np.int32), dtype=wp.vec3i),
        voxel_size=h,
        translation=wp.vec3(*lo),
    )
    geo = fem.Nanogrid(volume)
    space = fem.make_polynomial_space(geo, degree=degree, dtype=wp.vec3)
    n_nodes = space.node_count()
    cells = fem.Cells(geo)
    weight = cell_weights(geo, lo, h, ii[interior])
    lam = E_MPA * NU / ((1 + NU) * (1 - 2 * NU))
    mu = E_MPA / (2 * (1 + NU))
    lame = wp.vec2(lam, mu)
    u_trial, v_test = fem.make_trial(space), fem.make_test(space)
    import scipy.sparse as sp
    import scipy.sparse.linalg  # noqa: F401 - sp.linalg.norm

    size = 3 * n_nodes

    def host(bsr) -> sp.csr_matrix:
        """A Warp block matrix on the host, as CSR - the pieces are added there: Warp adding one
        into another in place reserves room for both, which outgrows the card."""
        m = sp.bsr_matrix(
            (
                bsr.values.numpy()[: bsr.nnz].astype(np.float64),
                bsr.columns.numpy()[: bsr.nnz],
                bsr.offsets.numpy(),
            ),
            shape=(size, size),
        ).tocsr()
        del bsr
        return m

    # Row compression: the least temporary memory - the default triplets outgrow the card.
    lean = {"construction": "row_compress"}
    a_host = host(
        fem.integrate(
            stiffness_cells,
            fields={"u": u_trial, "v": v_test},
            quadrature=fem.RegularQuadrature(cells, order=2 * degree),
            values={"lame": lame, "weight": weight},
            output_dtype=wp.float64,
            bsr_options=lean,
        )
    )
    pts = sub_points[cut].reshape(-1, 3)
    measure = np.where(sub_inside[cut].ravel(), 1.0, ALPHA) * (h / sub) ** 3
    # A million points at a time: one quadrature over all of them runs the card out of memory.
    for rows in chunks(len(pts)):
        cut_quad = fem.PicQuadrature(
            cells,
            positions=wp.array(pts[rows].astype(np.float32), dtype=wp.vec3),
            measures=wp.array(measure[rows].astype(np.float32), dtype=float),
            max_dist=h,
        )
        a_host = a_host + host(
            fem.integrate(
                stiffness_points,
                fields={"u": u_trial, "v": v_test},
                quadrature=cut_quad,
                values={"lame": lame},
                output_dtype=wp.float64,
                bsr_options=lean,
            )
        )
        del cut_quad
    # Bolt holes held by a penalty over their surface; seats loaded over theirs.
    spacing = h / (2.0 * degree)
    names = list(SEATS)
    bolt_pts, bolt_w, _ = surface_points(nodes, tris[group == len(names)], spacing)
    beta = 1e3 * E_MPA / h
    bolt_quad = fem.PicQuadrature(
        cells,
        positions=wp.array(bolt_pts.astype(np.float32), dtype=wp.vec3),
        measures=wp.array(bolt_w.astype(np.float32), dtype=float),
        max_dist=h,
    )
    a_host = a_host + host(
        fem.integrate(
            penalty,
            fields={"u": u_trial, "v": v_test},
            quadrature=bolt_quad,
            values={"beta": beta},
            output_dtype=wp.float64,
            bsr_options=lean,
        )
    )
    rhs = None
    seat_quads = {}
    for kk, name in enumerate(names):
        chosen = tris[group == kk]
        sp_pts, sp_w, _ = surface_points(nodes, chosen, spacing)
        force = np.asarray(setup["seats"][name]["force_N"], float)
        t = force / sp_w.sum()
        quad = fem.PicQuadrature(
            cells,
            positions=wp.array(sp_pts.astype(np.float32), dtype=wp.vec3),
            measures=wp.array(sp_w.astype(np.float32), dtype=float),
            max_dist=h,
        )
        seat_quads[name] = (quad, sp_pts, sp_w)
        part = fem.integrate(
            traction,
            fields={"v": v_test},
            quadrature=quad,
            values={"t": wp.vec3(*t)},
            output_dtype=wp.float64,
        ).numpy()
        rhs = part if rhs is None else rhs + part
    wp.synchronize()
    assemble_s = time.time() - t0

    # cuDSS.
    import cupy as cp
    import cupyx.scipy.sparse as csp
    from nvmath.sparse.advanced import (
        DirectSolver,
        DirectSolverMatrixType,
        ExecutionCUDA,
        HybridMemoryModeOptions,
    )
    from solve_gpu_tet10 import mtlayer

    # cuDSS does not add duplicate entries up.
    a_host.sum_duplicates()
    a_host.sort_indices()
    f = rhs.astype(np.float64).ravel()
    diagonal = a_host.diagonal()
    asym = sp.linalg.norm(a_host - a_host.T) / sp.linalg.norm(a_host)
    load = f.reshape(-1, 3).sum(axis=0)
    print(
        f"  {h:g} mm: {n_nodes:,} nodes, {int((diagonal <= 0).sum())} without stiffness, "
        f"{int((~np.isfinite(a_host.data)).sum())} non-finite entries, asymmetry {asym:.1e}, interior weight "
        f"{float(weight.numpy().sum()):,.0f} of {int(interior.sum()):,} interior cells, load {load}",
        flush=True,
    )
    # LU, not Cholesky: the integrands run in single precision, whose round-off is as large as the
    # millionth of a stiffness left in cut cells, and Cholesky meets a negative pivot there.
    execution = ExecutionCUDA(hybrid_memory_mode_options=HybridMemoryModeOptions(hybrid_memory_mode=True))
    for kind in (DirectSolverMatrixType.GENERAL,):
        t0 = time.time()
        options = {"sparse_system_type": kind, "multithreading_lib": mtlayer()}
        with DirectSolver(
            csp.csr_matrix(a_host),
            cp.asarray(f).reshape(-1, 1),
            options=options,
            execution=execution,
        ) as solver:
            solver.plan()
            solver.factorize()
            cp.cuda.Device().synchronize()
            factor_s = time.time() - t0
            t1 = time.time()
            x = cp.asnumpy(solver.solve()).ravel()
            cp.cuda.Device().synchronize()
            solve_s = time.time() - t1
        residual = float(np.linalg.norm(a_host @ x - f) / np.linalg.norm(f))
        print(f"  cuDSS {kind.name}: residual {residual:.1e}", flush=True)
        if np.isfinite(residual) and residual < 1e-6:
            break
    # CuPy keeps what cuDSS used in its pool; Warp needs it back for reading the answer.
    cp.get_default_memory_pool().free_all_blocks()
    cp.get_default_pinned_memory_pool().free_all_blocks()

    # Read it back: displacement on the seats' points, stress at every inside quadrature point.
    u_field = space.make_field()
    u_field.dof_values = wp.array(x.reshape(-1, 3).astype(np.float32), dtype=wp.vec3)
    seat_points, seat_u, seat_w = {}, {}, {}
    for name, (quad, sp_pts, sp_w) in seat_quads.items():
        seat_points[name], seat_w[name] = sp_pts, sp_w
        seat_u[name] = interpolate_points(value_at, quad, sp_pts, {"u": u_field}, {})
    # Results come back in the points' own order - checked, since every metric depends on it.
    first = next(iter(seat_quads.values()))
    order_gap = float(np.abs(interpolate_points(_position, first[0], first[1], {}, {}) - first[1]).max())
    inside_pts = sub_points[cut].reshape(-1, 3)[sub_inside[cut].ravel()]
    vm_cut = evaluate(von_mises_at, cells, inside_pts, {"u": u_field}, {"lame": lame}, h, dtype=float)
    centre_pts = lo + ii[interior] * h
    vm_int = evaluate(von_mises_at, cells, centre_pts, {"u": u_field}, {"lame": lame}, h, dtype=float)
    vm = np.concatenate([vm_int, vm_cut])
    vol = np.concatenate([np.full(len(vm_int), h**3), np.full(len(vm_cut), (h / sub) ** 3)])
    all_pts, _, _ = surface_points(nodes, tris, spacing)
    u_surface = evaluate(value_at, cells, all_pts, {"u": u_field}, {}, h)
    u_bolt = interpolate_points(value_at, bolt_quad, bolt_pts, {"u": u_field}, {})
    reactions = -beta * (u_bolt * bolt_w[:, None]).sum(axis=0)
    result = metrics(seat_points, seat_u, seat_w, vm, vol, u_surface, reactions)
    np.savez_compressed(OUT / f"fcm_{h:g}mm_q{degree}.npz", points=all_pts, u=u_surface)
    return {
        "cell_mm": h,
        "degree": degree,
        "sub": sub,
        "alpha": ALPHA,
        "penalty": beta,
        "cells": int(len(active)),
        "cut_cells": int(len(cut_ijk)),
        "interior_cells": int(interior.sum()),
        "nodes": int(n_nodes),
        "dof": int(3 * n_nodes),
        "nnz": int(a_host.nnz),
        "grid_s": classify_s,
        "assemble_s": assemble_s,
        "setup_s": factor_s,
        "solve_s": solve_s,
        "iterations": 1,
        "residual": residual,
        "bolt_slip_mm": float(np.linalg.norm(u_bolt, axis=1).max()),
        "point_order_gap_mm": order_gap,
        "volume_mm3": float(len(ii[interior]) * h**3 + sub_inside[cut].sum() * (h / sub) ** 3),
        "metrics": result,
    }


def cell_weights(geo, lo: np.ndarray, h: float, interior_ijk: np.ndarray) -> wp.array:
    """1 for the grid's cells wholly inside the part, 0 for the cut ones - in the grid's own order."""
    positions = cell_positions(geo)
    ijk = np.rint((positions - lo) / h).astype(np.int64)
    key = lambda a: (a[:, 0] * 100_003 + a[:, 1]) * 100_003 + a[:, 2]  # noqa: E731
    return wp.array(np.isin(key(ijk), key(interior_ijk)).astype(np.float32), dtype=float)


def cell_positions(geo) -> np.ndarray:
    """Each grid cell's centre, in the grid's order."""
    cells = fem.Cells(geo)
    quad = fem.RegularQuadrature(cells, order=0)
    out = wp.zeros(quad.total_point_count(), dtype=wp.vec3)
    fem.interpolate(_position, dest=out, at=quad, values={})
    return out.numpy().astype(np.float64)


@fem.integrand
def _position(s: fem.Sample, domain: fem.Domain):
    return fem.position(domain, s)


def interpolate_points(integrand, quad, points: np.ndarray, fields: dict, values: dict, dtype=wp.vec3) -> np.ndarray:
    """An integrand evaluated at a particle quadrature's points, back in the points' own order."""
    out = wp.zeros(len(points), dtype=dtype)
    fem.interpolate(integrand, dest=out, at=quad, fields=fields, values=values)
    return out.numpy().astype(np.float64)


def chunks(count: int, size: int = 1_000_000) -> list[slice]:
    return [slice(start, min(start + size, count)) for start in range(0, count, size)]


def evaluate(integrand, cells, points: np.ndarray, fields: dict, values: dict, h: float, dtype=wp.vec3) -> np.ndarray:
    """An integrand at arbitrary points, a few million at a time."""
    parts = []
    for rows in chunks(len(points)):
        quad = fem.PicQuadrature(
            cells,
            positions=wp.array(points[rows].astype(np.float32), dtype=wp.vec3),
            measures=wp.array(np.ones(rows.stop - rows.start, np.float32), dtype=float),
            max_dist=h,
        )
        parts.append(interpolate_points(integrand, quad, points[rows], fields, values, dtype))
        del quad
    return np.concatenate(parts)


def main() -> None:
    args, flags = [], {"--degree": "1", "--sub": "4"}
    rest = iter(sys.argv[1:])
    for a in rest:
        if a in flags:
            flags[a] = next(rest)
        else:
            args.append(a)
    degree, sub = int(flags["--degree"]), int(flags["--sub"])
    sizes = [float(a) for a in args] or [10.0, 8.0]
    mesh_data = dict(np.load(OUT / "tet10.npz"))
    setup = json.loads((OUT / "setup.json").read_text(encoding="utf-8"))
    path = OUT / "fcm.json"
    report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for h in sizes:
        key = f"{h:g}mm_q{degree}"
        try:
            r = solve(h, degree, sub, mesh_data, setup)
            report[key] = r
            m = r["metrics"]
            print(
                f"{key}: {r['dof']:,} dof ({r['cut_cells']:,} cut cells), grid {r['grid_s']:.1f} s, assemble "
                f"{r['assemble_s']:.1f} s, factor {r['setup_s']:.1f} s, solve {r['solve_s']:.2f} s; tilt max "
                f"{m['tilt_max_arcmin']:.4f}' at {m['tilt_max_at']}, p99.9 {m['vm_p999_mpa']:.2f}, "
                f"umax {m['umax_mm']:.4f}",
                flush=True,
            )
        except Exception as error:  # noqa: BLE001 - one size failing must not lose the others
            import traceback

            traceback.print_exc()
            report[key] = {"error": repr(error)}
        path.write_text(json.dumps(report, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
