"""The TET10 mesh solved by JAX-FEM 0.0.12 - differentiable finite elements in JAX: the stiffness
assembled on the GPU by automatic differentiation of the weak form, the same supports and loads,
the linear system handed to cuDSS on the GPU (JAX-FEM's own choices are SciPy, PETSc on the CPU, or
JAX's BiCGSTAB with a diagonal preconditioner). Runs inside WSL, in the ``jaxfem`` environment:

    XLA_PYTHON_CLIENT_PREALLOCATE=false micromamba run -n jaxfem python solve_jaxfem.py /mnt/c/.../<case>

JAX-FEM eliminates its Dirichlet rows in place, which leaves the matrix unsymmetric; the held values
are zero, so their columns are zeroed too - exactly - and cuDSS factors the symmetric matrix by
Cholesky, in half the memory of LU. JAX-FEM's sign for a surface load is read off against the
reference, not assumed. Writes ``jaxfem.npz`` - displacement at every TET10 node - and ``jaxfem.json``.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as onp

HERE = Path(sys.argv[1])
E_MPA, NU = 169_000.0, 0.275
TIMES: dict = {}
HELD: onp.ndarray = onp.empty(0, onp.int64)  # the held degrees of freedom, set before solving


def cudss_solve(a, b, x0, options):
    """JAX-FEM's custom linear solver: its PETSc matrix symmetrised, to the GPU, factored and solved
    by cuDSS."""
    import cupy as cp
    import cupyx.scipy.sparse as csp
    import jax.numpy as jnp
    import scipy.sparse as sp
    from nvmath.sparse.advanced import (
        DirectSolver,
        DirectSolverMatrixType,
        ExecutionCUDA,
        HybridMemoryModeOptions,
    )

    t0 = time.time()
    indptr, indices, data = a.getValuesCSR()
    n = a.getSize()[0]
    host = sp.csr_matrix((data, indices, indptr), shape=(n, n))
    keep = onp.ones(n)
    keep[HELD] = 0.0
    host = (sp.diags(keep) @ host @ sp.diags(keep) + sp.diags(1.0 - keep)).tocsr()
    host.sort_indices()
    m = csp.csr_matrix(host)
    rhs = cp.asarray(onp.asarray(b)).reshape(-1, 1)
    TIMES["to_gpu_s"] = time.time() - t0
    execution = ExecutionCUDA(hybrid_memory_mode_options=HybridMemoryModeOptions(hybrid_memory_mode=True))
    with DirectSolver(m, rhs, options={"sparse_system_type": DirectSolverMatrixType.SPD}, execution=execution) as s:
        t0 = time.time()
        s.plan()
        s.factorize()
        cp.cuda.Device().synchronize()
        TIMES["factor_s"] = time.time() - t0
        t0 = time.time()
        x = cp.asnumpy(s.solve()).ravel()
        TIMES["solve_s"] = time.time() - t0
    return jnp.asarray(x)


def main() -> None:
    import jax
    import jax.numpy as np
    from jax_fem.generate_mesh import Mesh
    from jax_fem.problem import Problem
    from jax_fem.solver import solver

    data = onp.load(HERE / "tet10.npz")
    setup = json.loads((HERE / "setup.json").read_text())
    nodes, tets, tris, group = data["nodes"], data["tets"], data["tris"], data["group"]
    names = [str(n) for n in data["names"]]
    seats = names[:-1]
    n = len(nodes)
    bolt_mask = onp.zeros(n, bool)
    bolt_mask[onp.unique(tris[group == len(seats)])] = True
    global HELD
    HELD = (3 * onp.flatnonzero(bolt_mask)[:, None] + onp.arange(3)).ravel()
    seat_masks, tractions = [], []
    for k, name in enumerate(seats):
        chosen = tris[group == k]
        mask = onp.zeros(n, bool)
        mask[onp.unique(chosen)] = True
        seat_masks.append(np.asarray(mask))
        p = nodes[chosen[:, :3]]
        area = 0.5 * onp.linalg.norm(onp.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1).sum()
        tractions.append(onp.asarray(setup["seats"][name]["force_N"], float) / area)
    lam = E_MPA * NU / ((1 + NU) * (1 - 2 * NU))
    mu = E_MPA / (2 * (1 + NU))

    class Elasticity(Problem):
        def get_tensor_map(self):
            def stress(u_grad):
                eps = 0.5 * (u_grad + u_grad.T)
                return lam * np.trace(eps) * np.eye(3) + 2.0 * mu * eps

            return stress

        def get_surface_maps(self):
            def pushing(t):
                def surface_map(u, x):
                    return t

                return surface_map

            return [pushing(np.asarray(t)) for t in tractions]

    # JAX-FEM finds a surface's faces by testing every face of every cell, and loads interior faces
    # and neighbours whose nodes all lie on a seat - 30% more area on one seat here. It is handed the
    # labelled triangles' own faces instead: each matched to its cell and local face by its corners.
    from jax_fem import fe

    seat_corners = [tris[group == k][:, :3] for k in range(len(seats))]

    def exact_faces(element, location_fns):
        cells = onp.asarray(element.cells)
        face_inds = onp.asarray(element.face_inds)
        size = onp.int64(len(nodes))
        key = lambda c: (c[:, 0] * size + c[:, 1]) * size + c[:, 2]  # noqa: E731
        keys, where = [], []
        for f, local in enumerate(face_inds):
            corners = [i for i in local if i < 4]
            keys.append(key(onp.sort(cells[:, corners], axis=1).astype(onp.int64)))
            where.append(onp.stack([onp.arange(len(cells)), onp.full(len(cells), f)], axis=1))
        keys, where = onp.concatenate(keys), onp.concatenate(where)
        order = onp.argsort(keys)
        out = []
        for corners in seat_corners:
            k = key(onp.sort(corners, axis=1).astype(onp.int64))
            out.append(np.asarray(where[order[onp.searchsorted(keys[order], k)]]))
        return out

    fe.FiniteElement.get_boundary_conditions_inds = exact_faces

    t0 = time.time()
    mesh = Mesh(nodes, tets.astype(onp.int32), ele_type="TET10")
    held = np.asarray(bolt_mask)

    def on_bolts(point, ind):
        return held[ind]

    def zero(point):
        return 0.0

    def on(mask):
        """A location function over node indices: JAX-FEM counts its arguments, so no defaults."""

        def location(point, ind):
            return mask[ind]

        return location

    locations = [on(m) for m in seat_masks]
    problem = Elasticity(
        mesh,
        vec=3,
        dim=3,
        ele_type="TET10",
        dirichlet_bc_info=[[on_bolts] * 3, [0, 1, 2], [zero] * 3],
        location_fns=locations,
    )
    TIMES["problem_s"] = time.time() - t0
    # The faces JAX-FEM loads, against the labelled seat triangles: it tests every face of every
    # cell, so an interior face with all its nodes on a seat is loaded too.
    TIMES["seat_faces"] = {
        name: {
            "jaxfem": int(len(problem.boundary_inds_list[k])),
            "labelled": int((group == k).sum()),
        }
        for k, name in enumerate(seats)
    }
    print(json.dumps(TIMES["seat_faces"]), flush=True)
    if "--faces" in sys.argv:
        return
    t0 = time.time()
    sol = solver(problem, solver_options={"newton": {"linear": {"custom_solver": cudss_solve}}, "tol": 1e-6})
    TIMES["solver_total_s"] = time.time() - t0
    u = onp.asarray(sol[0]).reshape(-1, 3)
    # JAX-FEM's sign for a surface map, read off against the reference when one is there.
    sign = 1.0
    ref = HERE / "cudss.npz"
    if ref.exists():
        u_ref = onp.load(ref)["u"]
        if onp.linalg.norm(u + u_ref) < onp.linalg.norm(u - u_ref):
            sign = -1.0
    u = sign * u
    onp.savez_compressed(HERE / "jaxfem.npz", u=u)
    TIMES.update(
        {
            "dof": int(3 * n),
            "surface_map_sign": sign,
            "devices": [str(d) for d in jax.devices()],
            "setup_s": TIMES.get("factor_s", 0.0),
            "umax": float(onp.linalg.norm(u, axis=1).max()),
        }
    )
    (HERE / "jaxfem.json").write_text(json.dumps(TIMES, indent=1))
    print(json.dumps(TIMES, indent=1))


if __name__ == "__main__":
    main()
