"""What every solver in the comparison shares: where things are, the load case and supports carried
over from agenticCAE, and the metrics every result is judged by - computed the same way for all.

The load case is agenticCAE's DLC 1.3 extreme (low-speed shaft 401 kN·m): a force on each of the six
bearing seats, in N, in the part's own frame (+Z down the main axis toward the generator, the main
axis through (0, 0)). The CAD is byte-identical to agenticCAE's, but its face numbers are not - it
read the STEP into more faces - so seats and bolt holes are found here by geometry: diameter, axis
and height, as agenticCAE recorded them.

Supports and loads are applied the same way by every solver, so the comparison isolates the solvers:
- **Flange bolts:** every surface point of the 25 bolt holes on the 1120 mm pitch circle is held
  fixed. (agenticCAE tied each hole rigidly to a fixed point, which leaves the hole free to rotate
  about it; holding the hole's surface is a little stiffer, and every solver here can apply it.)
- **Bearing seats:** each seat's force is spread evenly over its cylindrical surface, as a traction
  of force over area. (agenticCAE used a distributing RBE3 coupling with equal node weights, which
  is the same thing on an even mesh.)

The metrics are agenticCAE's:
- **Bore tilt**, arc-minutes: each seat's best-fit rigid rotation about the two axes square to the
  bore - what an RBE3 reference node reads - from the displacement of the seat's surface points.
- **Gear-mesh misalignment**, µm over the face width: the difference between the two shafts' skews
  along the line of action, each shaft's skew from how differently its two seats move.
- **99.9th-percentile von Mises**, MPa, weighted by volume - the peak chases singularities.
- **Largest displacement**, mm, and the **sum of reactions**, N, which must balance the loads.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np

# Where the scratch project and the cases live, and agenticCAE's assets - both overridable.
SCRATCH = Path(
    os.environ.get(
        "BENCH_SCRATCH",
        r"C:\Users\saxen\AppData\Local\Temp\claude\c--Work-fastcae\746a05ff-0c04-4b6d-aed8-06d9692b9036\scratchpad",
    )
)
# The case solved: design #7 of the campaign by default; ``BENCH_CASE=e56235`` for agenticCAE's mesh.
OUT = SCRATCH / "solve" / os.environ.get("BENCH_CASE", "design7")
AGENTICCAE = Path(os.environ.get("AGENTICCAE_ASSETS", r"C:\Work\agenticCAE\assets"))

# Cast iron, as agenticCAE solved it: MPa and mm.
E_MPA = 169_000.0
NU = 0.275

# The six bearing seats and what each carries - agenticCAE's names, geometry and loads.
SEATS = {
    "BORE_AX1_S1": {"dia": 180.0, "xy": (0.0, 520.0), "z": (113.9, 170.1)},
    "BORE_AX1_S4": {"dia": 200.0, "xy": (0.0, 520.0), "z": (425.9, 469.6)},
    "BORE_AX2_S2": {"dia": 180.0, "xy": (246.3, 376.6), "z": (113.9, 170.1)},
    "BORE_AX2_S3": {"dia": 272.0, "xy": (246.3, 376.6), "z": (554.7, 670.3)},
    "BORE_MAIN_S2": {"dia": 541.0, "xy": (0.0, 0.0), "z": (70.2, 125.2)},
    "BORE_MAIN_S3": {"dia": 360.02, "xy": (0.0, 0.0), "z": (554.7, 659.6)},
}
# The flange's bolt holes: 25 on a 1120 mm pitch circle round the main axis.
BOLT_PCD_MM = 1120.0

ARCMIN = 180.0 / math.pi * 60.0


def loads() -> dict[str, np.ndarray]:
    """Each seat's force, N, from agenticCAE's load case."""
    raw = json.loads((AGENTICCAE / "loads.json").read_text(encoding="utf-8"))
    return {name: np.array([raw[name][c] for c in ("FX", "FY", "FZ")], float) for name in SEATS}


def gear_meshes() -> dict:
    """The gear meshes and the shafts they join, from agenticCAE."""
    return json.loads((AGENTICCAE / "gearmesh.json").read_text(encoding="utf-8"))


def seat_fit(points: np.ndarray, u: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """A seat's best-fit rigid motion - translation of its centre and rotation - from its surface
    points' displacements, weighted: what a distributing coupling's reference node reads."""
    w = weights / weights.sum()
    centre = w @ points
    r = points - centre
    t = w @ u
    d = u - t
    # u - t ≈ θ × r, and θ × r = R θ with R the rows below: least squares for θ.
    zero = np.zeros(len(r))
    rows = np.stack(
        [
            np.stack([zero, r[:, 2], -r[:, 1]], axis=1),
            np.stack([-r[:, 2], zero, r[:, 0]], axis=1),
            np.stack([r[:, 1], -r[:, 0], zero], axis=1),
        ],
        axis=1,
    )  # (n, 3, 3): rows[i] @ θ = θ × r_i
    a = np.einsum("n,nji,njk->ik", w, rows, rows)
    b = np.einsum("n,nji,nj->i", w, rows, d)
    theta = np.linalg.solve(a, b)
    return t, theta


def metrics(
    seat_points: dict[str, np.ndarray],
    seat_u: dict[str, np.ndarray],
    seat_w: dict[str, np.ndarray],
    vm: np.ndarray,
    vm_volume: np.ndarray,
    u_all: np.ndarray,
    reactions: np.ndarray | None = None,
) -> dict:
    """agenticCAE's metrics from one solver's result: per seat tilt, gear-mesh misalignment,
    volume-weighted p99.9 and p99 von Mises, the peak, the largest displacement, the reactions."""
    per = {}
    centres = {}
    for name in SEATS:
        t, theta = seat_fit(seat_points[name], seat_u[name], seat_w[name])
        tilt = float(np.hypot(theta[0], theta[1]))
        per[name] = {
            "tilt_arcmin": round(tilt * ARCMIN, 5),
            "rx": float(theta[0]),
            "ry": float(theta[1]),
            "spin_rz": float(theta[2]),
            "u_mm": [float(x) for x in t],
        }
        centres[name] = t
    cfg = gear_meshes()
    mesh_out = {}
    for mname, m in cfg["meshes"].items():
        p0, p1 = (np.asarray(x, float) for x in m["axes_xy"])
        n = (p1 - p0) / np.linalg.norm(p1 - p0)
        tdir = np.array([-n[1], n[0]])

        def skew(shaft):
            a, b = cfg["shafts"][shaft]["bores"]
            z1, z2 = cfg["shafts"][shaft]["z_mm"]
            if a not in centres or b not in centres:
                return None
            return (centres[b][:2] - centres[a][:2]) / (z2 - z1)

        sa, sc = skew(m["shafts"][0]), skew(m["shafts"][1])
        if sa is None or sc is None:
            continue
        rel = sa - sc
        lead = float(rel @ tdir)
        rec = {"lead_mrad": lead * 1e3, "cdist_mrad": float(rel @ n) * 1e3}
        if m.get("face_width_mm"):
            rec["lead_um_over_face"] = abs(lead) * m["face_width_mm"] * 1e3
        mesh_out[mname] = rec
    order = np.argsort(vm)
    cum = np.cumsum(vm_volume[order]) / vm_volume.sum()

    def pct(f):
        return float(vm[order][min(int(np.searchsorted(cum, f)), len(order) - 1)])

    out = {
        "tilt_max_arcmin": max(p["tilt_arcmin"] for p in per.values()),
        "tilt_max_at": max(per, key=lambda k: per[k]["tilt_arcmin"]),
        "per_seat": per,
        "gear_mesh": mesh_out,
        "vm_p999_mpa": pct(0.999),
        "vm_p99_mpa": pct(0.99),
        "vm_peak_mpa": float(vm.max()),
        "umax_mm": float(np.linalg.norm(u_all, axis=1).max()),
    }
    if reactions is not None:
        out["reactions_N"] = [float(x) for x in reactions]
    return out


def von_mises(stress: np.ndarray) -> np.ndarray:
    """Von Mises of stresses given as (n, 6) xx, yy, zz, xy, yz, zx - or (n, 3, 3)."""
    s = np.asarray(stress)
    if s.ndim == 3:
        xx, yy, zz = s[:, 0, 0], s[:, 1, 1], s[:, 2, 2]
        xy, yz, zx = s[:, 0, 1], s[:, 1, 2], s[:, 2, 0]
    else:
        xx, yy, zz, xy, yz, zx = s.T
    return np.sqrt(0.5 * ((xx - yy) ** 2 + (yy - zz) ** 2 + (zz - xx) ** 2) + 3.0 * (xy**2 + yz**2 + zx**2))


def stress_from_strain(eps: np.ndarray) -> np.ndarray:
    """Linear-elastic stress (n, 3, 3) from strain (n, 3, 3), cast iron."""
    lam = E_MPA * NU / ((1 + NU) * (1 - 2 * NU))
    mu = E_MPA / (2 * (1 + NU))
    tr = np.trace(eps, axis1=1, axis2=2)
    return 2 * mu * eps + lam * tr[:, None, None] * np.eye(3)[None]
