"""The TET10 system (``system_tet10.py``) solved by PETSc 3.25, built with CUDA - inside WSL, in the
``petscgpu`` micromamba environment:

- ``gamg_gpu`` - conjugate gradient with PETSc's smoothed-aggregation multigrid, the matrix and
  vectors on the GPU (cuSPARSE): the Galerkin products, the Chebyshev smoothing and the Krylov
  iteration run there, the aggregation on the CPU. The six rigid-body modes as near-nullspace.
- ``gamg_cpu`` - the same on the CPU, one core.
- ``cholmod`` - SuiteSparse's supernodal Cholesky on the CPU, a direct solve to compare with MUMPS.

    PETSC_OPTIONS=-use_gpu_aware_mpi\\ 0 micromamba run -n petscgpu python solve_petsc.py /mnt/c/.../<case> [methods]

Writes ``petsc_<method>.npz`` - displacement at every TET10 node - and ``petsc.json`` with the times.
With ``couplings`` among the arguments it solves agenticCAE's supports instead
(``system_couplings.npz``: the free nodes' displacements and three rotations a bolt, u = T q) and
writes ``petsc_couplings_<method>.npz`` holding q.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(sys.argv[1])
COUPLINGS = "couplings" in sys.argv[2:]
METHODS = [m for m in sys.argv[2:] if m != "couplings"] or ["gamg_gpu", "gamg_cpu", "cholmod"]


def rigid_modes(points: np.ndarray) -> np.ndarray:
    b = np.zeros((3 * len(points), 6))
    x, y, z = (points - points.mean(axis=0)).T
    b[0::3, 0] = 1.0
    b[1::3, 1] = 1.0
    b[2::3, 2] = 1.0
    b[0::3, 3], b[1::3, 3] = -y, x
    b[1::3, 4], b[2::3, 4] = -z, y
    b[0::3, 5], b[2::3, 5] = z, -x
    return b


def main() -> None:
    from petsc4py import PETSc

    s = np.load(HERE / ("system_couplings.npz" if COUPLINGS else "system.npz"))
    nodes = np.load(HERE / "tet10.npz")["nodes"]
    indptr, indices, data = (
        s["indptr"].astype(PETSc.IntType),
        s["indices"].astype(PETSc.IntType),
        s["data"],
    )
    n = int(s["shape"][0])
    f = s["f"]
    if COUPLINGS:
        # The unknowns: the free nodes' displacements, then three rotations a bolt. A rigid rotation
        # about x, y or z turns every bolt by the same; the translations leave them alone.
        free_nodes = np.setdiff1d(np.arange(len(nodes)), s["held"])
        bolts = (n - 3 * len(free_nodes)) // 3
        modes = np.zeros((n, 6))
        modes[: 3 * len(free_nodes)] = rigid_modes(nodes[free_nodes])
        turn = np.zeros((3 * bolts, 6))
        turn[2::3, 3] = turn[0::3, 4] = turn[1::3, 5] = 1.0  # modes 3, 4, 5 turn about z, x, y
        modes[3 * len(free_nodes) :] = turn
    else:
        free_nodes = s["free_nodes"]
        modes = rigid_modes(nodes[free_nodes])
    name = "petsc_couplings.json" if COUPLINGS else "petsc.json"
    report = json.loads((HERE / name).read_text()) if (HERE / name).exists() else {}
    for method in METHODS:
        try:
            report[method] = run(method, indptr, indices, data, n, f, modes, nodes, None if COUPLINGS else free_nodes)
        except Exception as error:  # noqa: BLE001 - one method failing must not lose the others
            report[method] = {"error": str(error).splitlines()[0][:300]}
        print(method, json.dumps(report[method]), flush=True)
        (HERE / name).write_text(json.dumps(report, indent=1))


def run(method, indptr, indices, data, n, f, modes, nodes, free_nodes) -> dict:
    """One method's solve: its times, iterations and residual; the displacement written beside."""
    from petsc4py import PETSc

    gpu = method.endswith("_gpu")
    opts = PETSc.Options()
    if gpu:
        # The multigrid setup's sparse products on the CPU - cuSPARSE's want more than the card's
        # 8 GB here - the iteration on the GPU. PETSc names the switch by how the product is called.
        for name in (
            "matmatmult_backend_cpu",
            "matptap_backend_cpu",
            "mat_product_algorithm_backend_cpu",
        ):
            opts[name] = True
    t0 = time.time()
    a = PETSc.Mat().createAIJ(size=(n, n), csr=(indptr, indices, data), bsize=3, comm=PETSc.COMM_SELF)
    a.assemble()
    if gpu:
        a = a.convert("aijcusparse")
    vectors = []
    for m in range(6):
        v = a.createVecLeft()
        v.setArray(modes[:, m])
        vectors.append(v)
    a.setNearNullSpace(PETSc.NullSpace().create(vectors=vectors))
    b = a.createVecLeft()
    b.setArray(f)
    x = a.createVecRight()
    ksp = PETSc.KSP().create(PETSc.COMM_SELF)
    ksp.setOperators(a)
    prefix = f"{method}_"
    ksp.setOptionsPrefix(prefix)
    if method.startswith("gamg"):
        opts[prefix + "ksp_type"] = "cg"
        opts[prefix + "ksp_rtol"] = 1e-8
        opts[prefix + "ksp_norm_type"] = "unpreconditioned"
        opts[prefix + "pc_type"] = "gamg"
        opts[prefix + "pc_gamg_type"] = "agg"
        opts[prefix + "pc_gamg_threshold"] = 0.01
        opts[prefix + "pc_gamg_agg_nsmooths"] = 1
        opts[prefix + "mg_levels_ksp_type"] = "chebyshev"
        opts[prefix + "mg_levels_pc_type"] = "jacobi"
        opts[prefix + "mg_levels_ksp_max_it"] = 2
    else:
        opts[prefix + "ksp_type"] = "preonly"
        opts[prefix + "pc_type"] = "cholesky"
        opts[prefix + "pc_factor_mat_solver_type"] = method
    ksp.setFromOptions()
    made = time.time() - t0
    t0 = time.time()
    ksp.setUp()
    setup = time.time() - t0
    t0 = time.time()
    ksp.solve(b, x)
    solve = time.time() - t0
    values = x.getArray().copy()
    r = b.duplicate()
    a.mult(x, r)
    r.aypx(-1.0, b)
    if free_nodes is None:
        np.savez_compressed(HERE / f"petsc_couplings_{method}.npz", q=values)
    else:
        u = np.zeros((len(nodes), 3))
        u[free_nodes] = values.reshape(-1, 3)
        np.savez_compressed(HERE / f"petsc_{method}.npz", u=u)
    out = {
        "matrix_s": made,
        "setup_s": setup,
        "solve_s": solve,
        "iterations": ksp.getIterationNumber(),
        "reason": int(ksp.getConvergedReason()),
        "residual": float(r.norm() / b.norm()),
    }
    ksp.destroy()
    a.destroy()
    return out


if __name__ == "__main__":
    main()
