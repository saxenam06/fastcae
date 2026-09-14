"""The TET10 mesh's system (``system_tet10.py``) solved on the RTX 5060, three ways:

- ``amg_gpu`` - conjugate gradient on the GPU (CuPy), preconditioned by smoothed-aggregation
  algebraic multigrid: its levels built by PyAMG on the CPU from the six rigid-body modes, then run
  as V-cycles on the GPU with Chebyshev smoothing - PETSc GAMG's default recipe, on CuPy.
- ``cudss`` - NVIDIA cuDSS, the sparse direct solver on the GPU (Cholesky; its factors spill to
  host memory when the card's 8 GB is not enough).
- ``jacobi_gpu`` - the same conjugate gradient with only the diagonal, for scale.
- ``amg_cpu`` - PyAMG's own solver on the CPU, for scale.

    python solve_gpu_tet10.py [methods...]      # default: amg_gpu cudss
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import system_tet10
from common import OUT
from tet10_post import tet10_metrics

RTOL = 1e-8


def rigid_modes(points: np.ndarray) -> np.ndarray:
    """The six rigid-body modes at the free nodes, three dofs a node."""
    b = np.zeros((3 * len(points), 6))
    x, y, z = (points - points.mean(axis=0)).T
    b[0::3, 0] = 1.0
    b[1::3, 1] = 1.0
    b[2::3, 2] = 1.0
    b[0::3, 3], b[1::3, 3] = -y, x
    b[1::3, 4], b[2::3, 4] = -z, y
    b[0::3, 5], b[2::3, 5] = z, -x
    return b


def hierarchy(k, points):
    import pyamg

    return pyamg.smoothed_aggregation_solver(
        k.tobsr(blocksize=(3, 3)),
        B=rigid_modes(points),
        symmetry="hermitian",
        strength=("symmetric", {"theta": 0.0}),
        smooth=("jacobi", {"omega": 4.0 / 3.0}),
        improve_candidates=None,
        max_coarse=1000,
    )


class GpuAMG:
    """A PyAMG hierarchy applied as a V-cycle on the GPU: Chebyshev smoothing of degree 2 on the
    Jacobi-scaled operator over [0.1, 1.1] of its largest eigenvalue on every level, the coarsest
    solved by a pseudo-inverse. Rows with no diagonal - candidates an aggregate too small to carry
    all six rigid modes leaves empty - are left alone, as PyAMG leaves them."""

    def __init__(self, ml, degree: int = 2):
        import cupy as cp
        import cupyx.scipy.sparse as csp

        self.cp = cp
        self.degree = degree
        self.levels = []
        for level in ml.levels[:-1]:
            a = level.A.tocsr()
            d = a.diagonal()
            live = np.abs(d) > 1e-12 * np.abs(d).max()
            dinv = np.where(live, 1.0 / np.where(live, d, 1.0), 0.0)
            v = np.random.default_rng(0).standard_normal(a.shape[0]) * live
            for _ in range(20):
                v = dinv * (a @ v)
                v /= np.linalg.norm(v)
            lmax = 1.1 * float(np.linalg.norm(dinv * (a @ v)))
            self.levels.append(
                {
                    "A": csp.csr_matrix(a),
                    "P": csp.csr_matrix(level.P.tocsr()),
                    "R": csp.csr_matrix(level.R.tocsr()),
                    "Dinv": cp.asarray(dinv),
                    "bounds": (0.1 * lmax, lmax),
                }
            )
        self.coarse = cp.linalg.pinv(cp.asarray(ml.levels[-1].A.toarray()))

    def smooth(self, lv, x, b):
        """Chebyshev on D⁻¹A: x moved toward A⁻¹b by a polynomial of the given degree."""
        lo, hi = lv["bounds"]
        theta, delta = (hi + lo) / 2.0, (hi - lo) / 2.0
        sigma = theta / delta
        rho = 1.0 / sigma
        r = lv["Dinv"] * (b - lv["A"] @ x)
        d = r / theta
        x = x + d
        for _ in range(1, self.degree):
            r = r - lv["Dinv"] * (lv["A"] @ d)
            rho_next = 1.0 / (2.0 * sigma - rho)
            d = rho_next * rho * d + (2.0 * rho_next / delta) * r
            rho = rho_next
            x = x + d
        return x

    def cycle(self, b, level: int = 0):
        if level == len(self.levels):
            return self.coarse @ b
        lv = self.levels[level]
        x = self.smooth(lv, self.cp.zeros_like(b), b)
        x = x + lv["P"] @ self.cycle(lv["R"] @ (b - lv["A"] @ x), level + 1)
        return self.smooth(lv, x, b)


def pcg(a, b, apply, rtol: float, maxiter: int, xp):
    """Preconditioned conjugate gradient; the solution, its iterations, the relative residual."""
    x = xp.zeros_like(b)
    r = b.copy()
    z = apply(r)
    p = z.copy()
    rz = float(r @ z)
    norm_b = float(xp.linalg.norm(b))
    res = 1.0
    for k in range(1, maxiter + 1):
        ap = a @ p
        alpha = rz / float(p @ ap)
        x += alpha * p
        r -= alpha * ap
        res = float(xp.linalg.norm(r)) / norm_b
        if res < rtol or not np.isfinite(res):
            return x, k, res
        z = apply(r)
        rz_next = float(r @ z)
        p = z + (rz_next / rz) * p
        rz = rz_next
    return x, maxiter, res


def mtlayer() -> str | None:
    """cuDSS's threading layer, shipped beside it: without it, its reordering runs on one core."""
    import nvidia

    for base in nvidia.__path__:
        for found in Path(base).rglob("cudss_mtlayer*.dll"):
            return str(found)
        for found in Path(base).rglob("libcudss_mtlayer_gomp.so*"):
            return str(found)
    return None


def solve(method: str, system: dict, points: np.ndarray) -> dict:
    k, f = system["k"], system["f"]
    if method == "amg_cpu":
        t0 = time.time()
        ml = hierarchy(k, points)
        setup = time.time() - t0
        residuals: list[float] = []
        t0 = time.time()
        x = ml.solve(f, tol=RTOL, accel="cg", maxiter=1000, residuals=residuals)
        return {
            "setup_s": setup,
            "solve_s": time.time() - t0,
            "iterations": len(residuals) - 1,
            "residual": residuals[-1] / residuals[0],
            "levels": [int(lv.A.shape[0]) for lv in ml.levels],
            "x": x,
        }

    import cupy as cp
    import cupyx.scipy.sparse as csp

    a = csp.csr_matrix(k)
    b = cp.asarray(f)
    if method == "amg_gpu":
        t0 = time.time()
        ml = hierarchy(k, points)
        cpu_setup = time.time() - t0
        t0 = time.time()
        amg = GpuAMG(ml)
        cp.cuda.Device().synchronize()
        upload = time.time() - t0
        t0 = time.time()
        x, its, res = pcg(a, b, amg.cycle, RTOL, 1000, cp)
        cp.cuda.Device().synchronize()
        return {
            "setup_s": cpu_setup + upload,
            "hierarchy_cpu_s": cpu_setup,
            "upload_s": upload,
            "solve_s": time.time() - t0,
            "iterations": its,
            "residual": res,
            "levels": [int(lv.A.shape[0]) for lv in ml.levels],
            "x": cp.asnumpy(x),
        }
    if method == "jacobi_gpu":
        dinv = 1.0 / a.diagonal()
        t0 = time.time()
        x, its, res = pcg(a, b, lambda r: dinv * r, RTOL, 40_000, cp)
        cp.cuda.Device().synchronize()
        return {
            "setup_s": 0.0,
            "solve_s": time.time() - t0,
            "iterations": its,
            "residual": res,
            "x": cp.asnumpy(x),
        }
    if method == "cudss":
        from nvmath.sparse.advanced import (
            DirectSolver,
            DirectSolverMatrixType,
            ExecutionCUDA,
            HybridMemoryModeOptions,
        )

        options = {
            "sparse_system_type": DirectSolverMatrixType.SPD,
            "multithreading_lib": mtlayer(),
        }
        execution = ExecutionCUDA(hybrid_memory_mode_options=HybridMemoryModeOptions(hybrid_memory_mode=True))
        with DirectSolver(a, b.reshape(-1, 1), options=options, execution=execution) as solver:
            t0 = time.time()
            solver.plan()
            cp.cuda.Device().synchronize()
            plan = time.time() - t0
            t0 = time.time()
            solver.factorize()
            cp.cuda.Device().synchronize()
            factor = time.time() - t0
            t0 = time.time()
            x = solver.solve()
            cp.cuda.Device().synchronize()
            solve_s = time.time() - t0
        x = cp.asnumpy(x).ravel()
        res = float(np.linalg.norm(k @ x - f) / np.linalg.norm(f))
        return {
            "setup_s": plan + factor,
            "plan_s": plan,
            "factor_s": factor,
            "solve_s": solve_s,
            "iterations": 1,
            "residual": res,
            "x": x,
        }
    raise ValueError(method)


def couplings(mesh: dict) -> None:
    """agenticCAE's supports (``system_tet10.build_couplings``), solved by cuDSS; u = T q."""
    if not (OUT / "system_couplings.npz").exists():
        print("assembled:", json.dumps(system_tet10.build_couplings(), default=float), flush=True)
    system = system_tet10.load_couplings()
    r = solve("cudss", {"k": system["k"], "f": system["f"]}, None)
    u = (system["t"] @ r.pop("x")).reshape(-1, 3)
    np.savez_compressed(OUT / "cudss_couplings.npz", u=u)
    path = OUT / "gpu_tet10.json"
    report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    report["cudss_couplings"] = r
    path.write_text(json.dumps(report, indent=1, default=float), encoding="utf-8")
    print(
        f"cudss_couplings: setup {r['setup_s']:.1f} s, solve {r['solve_s']:.1f} s, residual {r['residual']:.1e}; "
        f"umax {np.linalg.norm(u, axis=1).max():.4f} mm",
        flush=True,
    )


def main() -> None:
    methods = sys.argv[1:] or ["amg_gpu", "cudss"]
    mesh = dict(np.load(OUT / "tet10.npz"))
    if methods == ["couplings"]:
        couplings(mesh)
        return
    if not (OUT / "system.npz").exists():
        print("assembled:", json.dumps(system_tet10.build()), flush=True)
    system = system_tet10.load()
    points = mesh["nodes"][system["free_nodes"]]
    path = OUT / "gpu_tet10.json"
    report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    report["system"] = json.loads((OUT / "system.json").read_text(encoding="utf-8"))
    for method in methods:
        try:
            r = solve(method, system, points)
        except Exception as error:  # noqa: BLE001 - one method failing must not lose the others
            report[method] = {"error": repr(error)}
            print(f"{method} failed: {error!r}", flush=True)
            continue
        u, reactions = system_tet10.result(system, r.pop("x"), len(mesh["nodes"]))
        r["metrics"] = tet10_metrics(mesh, u, reactions)
        np.savez_compressed(OUT / f"{method}.npz", u=u)
        report[method] = r
        m = r["metrics"]
        print(
            f"{method}: setup {r['setup_s']:.1f} s, solve {r['solve_s']:.1f} s, {r['iterations']} its, "
            f"residual {r['residual']:.1e}; tilt max {m['tilt_max_arcmin']:.4f}' at {m['tilt_max_at']}, "
            f"p99.9 {m['vm_p999_mpa']:.2f} MPa, umax {m['umax_mm']:.4f} mm",
            flush=True,
        )
        path.write_text(json.dumps(report, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
