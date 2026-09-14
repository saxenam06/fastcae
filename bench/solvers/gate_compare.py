"""The gate's verdict: the production housing meshed the regular way (agenticCAE's route) and through its
field (the compiled CGAL mesher), each solved by Code_Aster with agenticCAE's couplings - the metrics,
the displacement and stress maps point by point, and the highest stress peaks, against the pass marks
agreed. The field route's answer is read at the regular route's points: its displacement by linear
interpolation in the tet holding the point, its stress as the holding tet's.

    python gate_compare.py [reference_case] [test_case] [--out results/gate/<name>.json]
        # gate3reg gate3 by default; writes gate.json in the test case, or --out
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from common import ARCMIN, SCRATCH, SEATS
from scipy.spatial import cKDTree
from tet10_post import centroid_stress, tet10_metrics

# Pass marks, per cent: bearing tilts and gear-mesh misalignment, p99.9, the maps, the peaks.
PASS = {"tilt": 3.0, "lead": 3.0, "p999": 5.0, "displacement_map": 3.0, "stress_map": 10.0, "peaks": 10.0}
PEAKS, APART_MM, NEAR_MM = 10, 50.0, 10.0


def load(case: str) -> dict:
    here = SCRATCH / "solve" / case
    mesh = dict(np.load(here / "tet10.npz"))
    solved = np.load(here / "aster_couplings.npz")
    u = solved["u"]
    m = tet10_metrics(mesh, u)
    rotation = solved["seat_rotation"]
    m["reference_tilt_arcmin"] = {n: float(np.hypot(*rotation[k, :2]) * ARCMIN) for k, n in enumerate(SEATS)}
    vm, volume = centroid_stress(mesh["nodes"], mesh["tets"], u)
    setup = json.loads((here / "setup.json").read_text(encoding="utf-8"))
    return {"case": case, "mesh": mesh, "u": u, "metrics": m, "vm": vm, "volume": volume, "setup": setup,
            "dof": int(3 * len(mesh["nodes"])), "solve_s": float(solved["solve_s"])}


def locate(mesh: dict, points: np.ndarray, candidates: int = 24) -> tuple[np.ndarray, np.ndarray]:
    """For each point, the tet of ``mesh`` holding it - or, off the mesh, the nearest by barycentric
    reach - and its barycentric coordinates there, clamped into the tet."""
    nodes, corners = mesh["nodes"], mesh["tets"][:, :4]
    _, near = cKDTree(nodes[corners].mean(axis=1)).query(points, k=candidates)
    best = np.zeros(len(points), np.int64)
    best_bary = np.zeros((len(points), 4))
    best_reach = np.full(len(points), -np.inf)
    for j in range(candidates):
        t = near[:, j]
        x = nodes[corners[t]]
        m = np.stack([x[:, 1] - x[:, 0], x[:, 2] - x[:, 0], x[:, 3] - x[:, 0]], axis=2)
        lam = np.linalg.solve(m, (points - x[:, 0])[:, :, None])[:, :, 0]
        bary = np.column_stack([1 - lam.sum(axis=1), lam])
        reach = bary.min(axis=1)
        better = reach > best_reach
        best[better], best_bary[better], best_reach[better] = t[better], bary[better], reach[better]
    best_bary = np.clip(best_bary, 0, None)
    return best, best_bary / best_bary.sum(axis=1, keepdims=True)


def percent(a: float, b: float) -> float:
    return 100.0 * (a / b - 1.0) if b else float("nan")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out_path = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    args = [a for a in args if a != out_path]
    reg, fld = load(args[0] if args else "gate3reg"), load(args[1] if len(args) > 1 else "gate3")
    rm, fm = reg["metrics"], fld["metrics"]
    rows = []
    for name in SEATS:
        rows.append(("tilt", f"{name} tilt, seat fit (')", rm["per_seat"][name]["tilt_arcmin"],
                     fm["per_seat"][name]["tilt_arcmin"]))
        rows.append(("tilt", f"{name} tilt, reference node (')", rm["reference_tilt_arcmin"][name],
                     fm["reference_tilt_arcmin"][name]))
    for name in rm["gear_mesh"]:
        rows.append(("lead", f"{name} lead (mrad)", rm["gear_mesh"][name]["lead_mrad"], fm["gear_mesh"][name]["lead_mrad"]))
    rows += [("p999", "p99.9 von Mises (MPa)", rm["vm_p999_mpa"], fm["vm_p999_mpa"]),
             ("info", "p99 von Mises (MPa)", rm["vm_p99_mpa"], fm["vm_p99_mpa"]),
             ("info", "peak von Mises (MPa)", rm["vm_peak_mpa"], fm["vm_peak_mpa"]),
             ("info", "largest displacement (mm)", rm["umax_mm"], fm["umax_mm"])]

    # The displacement map at the regular mesh's corner nodes; the stress map at its tets' centroids.
    corner_nodes = np.unique(reg["mesh"]["tets"][:, :4])
    at = reg["mesh"]["nodes"][corner_nodes]
    tet, bary = locate(fld["mesh"], at)
    u_f = np.einsum("nk,nkc->nc", bary, fld["u"][fld["mesh"]["tets"][tet, :4]])
    u_r = reg["u"][corner_nodes]
    displacement_map = 100 * np.linalg.norm(u_f - u_r) / np.linalg.norm(u_r)
    centres = reg["mesh"]["nodes"][reg["mesh"]["tets"][:, :4]].mean(axis=1)
    held, _ = locate(fld["mesh"], centres)
    w = reg["volume"]
    stress_map = 100 * np.sqrt(np.sum(w * (fld["vm"][held] - reg["vm"]) ** 2) / np.sum(w * reg["vm"] ** 2))

    # The highest peaks of the regular route, at least APART_MM apart; the field's highest within NEAR_MM.
    bolts = np.array([[*p["xy"], 0.0] for p in reg["setup"]["bolt_positions"]])
    record = SCRATCH / "solve" / reg["case"] / "regular.json"
    patches = json.loads(record.read_text())["repair"]["patch_sites"] if record.exists() else []
    lids = np.array([p["centre"] for p in patches]) if patches else np.empty((0, 3))
    field_tree = cKDTree(fld["mesh"]["nodes"][fld["mesh"]["tets"][:, :4]].mean(axis=1))
    peaks, taken = [], []
    for t in np.argsort(-reg["vm"]):
        c = centres[t]
        if any(np.linalg.norm(c - q) < APART_MM for q in taken):
            continue
        taken.append(c)
        near = field_tree.query_ball_point(c, NEAR_MM)
        field_peak = float(fld["vm"][near].max()) if near else float("nan")
        at_bolt = bool(len(bolts) and np.min(np.hypot(*(bolts[:, :2] - c[:2]).T)) < 40.0 and c[2] < 120.0)
        on_lid = bool(len(lids) and np.min(np.linalg.norm(lids - c, axis=1)) < 150.0)
        peaks.append({"at_mm": [round(float(x), 1) for x in c], "regular_mpa": float(reg["vm"][t]),
                      "field_mpa": field_peak, "diff_pct": percent(field_peak, float(reg["vm"][t])),
                      "at_bolt_coupling": at_bolt, "near_meshfix_lid": on_lid})
        if len(peaks) == PEAKS:
            break

    table = [{"kind": k, "metric": name, "regular": a, "field": b, "diff_pct": percent(b, a)} for k, name, a, b in rows]
    judged = [p for p in peaks if not p["at_bolt_coupling"] and not p["near_meshfix_lid"]]
    verdict = {
        "tilts": bool(max(abs(r["diff_pct"]) for r in table if r["kind"] == "tilt") <= PASS["tilt"]),
        "leads": bool(max(abs(r["diff_pct"]) for r in table if r["kind"] == "lead") <= PASS["lead"]),
        "p999": bool(abs(table[[r["metric"] for r in table].index("p99.9 von Mises (MPa)")]["diff_pct"]) <= PASS["p999"]),
        "displacement_map": bool(displacement_map <= PASS["displacement_map"]),
        "stress_map": bool(stress_map <= PASS["stress_map"]),
        "peaks": bool(judged) and bool(max(abs(p["diff_pct"]) for p in judged) <= PASS["peaks"]),
    }
    out = {"pass_marks_pct": PASS, "verdict": verdict,
           "meshes": {r["case"]: {"dof": r["dof"], "tets": int(len(r["mesh"]["tets"])), "code_aster_solve_s": r["solve_s"]}
                      for r in (reg, fld)},
           "metrics": table, "displacement_map_pct": displacement_map, "stress_map_pct": stress_map, "peaks": peaks}
    out["reference"], out["test"] = reg["case"], fld["case"]
    target = Path(out_path) if out_path else SCRATCH / "solve" / fld["case"] / "gate.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=1, default=float))
    for r in table:
        print(f"{r['metric']:40s} {r['regular']:10.4f} {r['field']:10.4f} {r['diff_pct']:+7.2f} %")
    print(f"displacement map {displacement_map:.2f} %, stress map {stress_map:.2f} %")
    for p in peaks:
        print(f"peak at {p['at_mm']}: {p['regular_mpa']:.1f} vs {p['field_mpa']:.1f} MPa ({p['diff_pct']:+.1f} %)"
              f"{' bolt' if p['at_bolt_coupling'] else ''}{' lid' if p['near_meshfix_lid'] else ''}")
    print("verdict:", json.dumps(verdict))


if __name__ == "__main__":
    main()
