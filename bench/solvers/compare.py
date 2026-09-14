"""Every solver's answer on one case against Code_Aster's, and what each cost - one table.

Results on the TET10 mesh (Code_Aster, the GPU solvers, PETSc, FEniCSx, JAX-FEM) are read the same
way: agenticCAE's metrics from each displacement, and the displacement field itself against the
reference, node by node. Results on their own grids (Warp's voxels, the cut-cell method) are
compared by their metrics only - they have no nodes in common with the mesh.

    python compare.py [case]        # design7 by default; writes <case>/results.md and results.json
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

if len(sys.argv) > 1:
    os.environ["BENCH_CASE"] = sys.argv[1]

from common import OUT, SEATS  # noqa: E402
from tet10_post import tet10_metrics  # noqa: E402

LABELS = {
    "aster_clamped": "Code_Aster 18, MUMPS (block low-rank), CPU - WSL",
    "cudss": "cuDSS direct (Cholesky), GPU",
    "amg_gpu": "CG + smoothed-aggregation AMG (PyAMG levels, CuPy V-cycle), GPU",
    "jacobi_gpu": "CG + Jacobi, GPU",
    "amg_cpu": "CG + PyAMG, CPU",
    "petsc_gamg_gpu": "PETSc CG + GAMG, cuSPARSE, GPU - WSL",
    "petsc_gamg_cpu": "PETSc CG + GAMG, CPU - WSL",
    "petsc_cholmod": "PETSc + CHOLMOD Cholesky, CPU - WSL",
    "fenicsx_gamg": "FEniCSx P2, PETSc CG + GAMG, CPU - WSL",
    "fenicsx_mumps": "FEniCSx P2, MUMPS, CPU - WSL",
    "jaxfem": "JAX-FEM TET10, GPU - WSL",
}


def times(name: str) -> dict:
    """What a result cost, from wherever its solver wrote it."""
    if name.startswith("aster"):
        z = np.load(OUT / f"{name}.npz")
        return {
            "setup_s": float(z["setup_s"]),
            "solve_s": float(z["solve_s"]),
            "total_s": float(z["total_s"]),
        }
    if name in ("cudss", "amg_gpu", "jacobi_gpu", "amg_cpu"):
        r = json.loads((OUT / "gpu_tet10.json").read_text(encoding="utf-8")).get(name, {})
        return {k: r[k] for k in ("setup_s", "solve_s", "iterations", "residual") if k in r}
    if name.startswith("petsc_"):
        return json.loads((OUT / "petsc.json").read_text(encoding="utf-8")).get(name[6:], {})
    if name.startswith("fenicsx_"):
        # Its own mesh and assembly count as setup; its solve includes the multigrid's setup.
        data = json.loads((OUT / "fenicsx.json").read_text(encoding="utf-8"))
        return {
            **data.get(name[8:], {}),
            "setup_s": data.get("mesh_s", 0.0) + data.get("assemble_s", 0.0),
        }
    if name == "jaxfem":
        # Setup: the problem and JAX's assembly (with its compilation) and the factorisation.
        data = json.loads((OUT / "jaxfem.json").read_text(encoding="utf-8"))
        return {**data, "setup_s": data["problem_s"] + data["solver_total_s"] - data["solve_s"]}
    return {}


def main() -> None:
    mesh = dict(np.load(OUT / "tet10.npz"))
    info = json.loads((OUT / "tet10.json").read_text(encoding="utf-8"))
    system = None
    if (OUT / "system.npz").exists():
        import system_tet10

        system = system_tet10.load()

    ref_file = OUT / "aster_clamped.npz"
    ref = np.load(ref_file)["u"] if ref_file.exists() else None
    rows = {}
    for name in LABELS:
        path = OUT / f"{name}.npz"
        if not path.exists():
            continue
        u = np.load(path)["u"]
        reactions = None
        if system is not None:
            reactions = system_tet10.result(system, u[system["free_nodes"]], len(u))[1]
        m = tet10_metrics(mesh, u, reactions)
        row = {"label": LABELS[name], "metrics": m, "times": times(name)}
        if ref is not None:
            row["field_error"] = float(np.linalg.norm(u - ref) / np.linalg.norm(ref))
        rows[name] = row

    grids = {}
    for file, key in (("warp_voxel.json", "warp"), ("fcm.json", "fcm")):
        if (OUT / file).exists():
            for size, r in json.loads((OUT / file).read_text(encoding="utf-8")).items():
                if "metrics" in r:
                    grids[f"{key}_{size}"] = r

    base = rows.get("aster_clamped", {}).get("metrics")
    out = {"case": OUT.name, "mesh": info, "results": rows, "grids": grids}
    (OUT / "results.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    text = table(rows, grids, base, info)
    (OUT / "results.md").write_text(text, encoding="utf-8")
    print(text)


def err(value: float, ref: float) -> str:
    return f"{100.0 * (value - ref) / ref:+.2f} %" if ref else "-"


def table(rows: dict, grids: dict, base: dict | None, info: dict) -> str:
    lines = [f"# {OUT.name}: {info['dof']:,} DOF TET10 ({info['tets']:,} elements)", ""]
    lines += [
        "| solver | setup s | solve s | its | field error | worst tilt ′ | IMS lead µm | p99.9 MPa | umax mm |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows.values():
        m, t = r["metrics"], r["times"]
        lead = m["gear_mesh"].get("IMS_82_23", {}).get("lead_um_over_face", float("nan"))
        cells = [
            r["label"],
            f"{t.get('setup_s', float('nan')):.1f}",
            f"{t.get('solve_s', float('nan')):.1f}",
            str(t.get("iterations", "")),
            f"{r.get('field_error', float('nan')):.1e}",
            f"{m['tilt_max_arcmin']:.4f}",
            f"{lead:.3f}",
            f"{m['vm_p999_mpa']:.2f}",
            f"{m['umax_mm']:.4f}",
        ]
        lines.append("| " + " | ".join(cells) + " |")
    if base is not None:
        lines += ["", "Tilt per seat, arc-minutes, and the error of each against Code_Aster:", ""]
        lines += ["| solver | " + " | ".join(SEATS) + " |", "|---|" + "---:|" * len(SEATS)]
        for name, r in rows.items():
            per = r["metrics"]["per_seat"]
            cells = [
                f"{per[s]['tilt_arcmin']:.4f} ({err(per[s]['tilt_arcmin'], base['per_seat'][s]['tilt_arcmin'])})"
                for s in SEATS
            ]
            lines.append(f"| {name} | " + " | ".join(cells) + " |")
    if grids:
        lines += [
            "",
            "On their own grids - no mesh:",
            "",
            "| method | DOF | setup s | solve s | its | worst tilt ′ | IMS lead µm | p99.9 MPa | umax mm |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for name, r in grids.items():
            m = r["metrics"]
            lead = m["gear_mesh"].get("IMS_82_23", {}).get("lead_um_over_face", float("nan"))
            # The grid, its assembly and - for the cut cells - the factorisation.
            setup = r.get("grid_s", 0.0) + r.get("assemble_s", 0.0) + r.get("setup_s", 0.0)
            lines.append(
                f"| {name} | {r['dof']:,} | {setup:.1f} | {r['solve_s']:.1f} | {r.get('iterations', '')} | "
                f"{m['tilt_max_arcmin']:.4f} | {lead:.3f} | {m['vm_p999_mpa']:.2f} | {m['umax_mm']:.4f} |"
            )
            if base is not None:
                per = m["per_seat"]
                lines.append(
                    "|  vs Code_Aster | | | | | "
                    + ", ".join(
                        f"{s.split('_', 1)[1]} {err(per[s]['tilt_arcmin'], base['per_seat'][s]['tilt_arcmin'])}"
                        for s in SEATS
                    )
                    + f" | {err(lead, base['gear_mesh']['IMS_82_23']['lead_um_over_face'])} | "
                    f"{err(m['vm_p999_mpa'], base['vm_p999_mpa'])} | {err(m['umax_mm'], base['umax_mm'])} |"
                )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
