"""A second case, with a reference answer: agenticCAE's own mesh of its production design e56235
(57,240 nodes, 202,496 linear tets from gmsh at 20 mm), made TET10 the way agenticCAE made it -
straight mid-side nodes - and labelled for the same supports and loads as every case here.

agenticCAE solved this design quadratic with Code_Aster: worst bore tilt 2.196 arcmin at
BORE_MAIN_S2, p99.9 von Mises 67.8 MPa, largest displacement 0.4285 mm (handbook 14-objective).
Its supports differ from the ones here - an RBE2 per bolt position tied to a fixed point, an RBE3
per seat - so its numbers are a sanity check on this setup, not a target for the solvers.

gmsh put every boundary node on the CAD, so a boundary triangle lies on a seat or a bolt hole when
all three of its corners do: at the cylinder's radius from its axis, within its height.

    python case_e56235.py          # writes scratchpad/solve/e56235/
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from common import SCRATCH, SEATS, loads
from mesh_tet10 import boundary, midside, quadratic, volume_quality

AGENTIC_MESH = Path(r"C:\Work\agenticCAE\results\v_e56235e636\mesh")
CASE = SCRATCH / "solve" / "e56235"


def on_cylinder(points: np.ndarray, xy, radius: float, z: tuple[float, float], tol: float) -> np.ndarray:
    rho = np.hypot(points[..., 0] - xy[0], points[..., 1] - xy[1])
    return (np.abs(rho - radius) < tol) & (points[..., 2] > z[0] - 0.5) & (points[..., 2] < z[1] + 0.5)


def main() -> None:
    started = time.time()
    CASE.mkdir(parents=True, exist_ok=True)
    cylinders = json.loads((SCRATCH / "solve" / "cylinders.json").read_text(encoding="utf-8"))
    nodes = np.load(AGENTIC_MESH / "nodes.npy").astype(np.float64)
    tets = np.load(AGENTIC_MESH / "tets.npy").astype(np.int64)
    p = nodes[tets]
    volume = np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))
    flip = volume < 0
    tets[flip] = tets[flip][:, [0, 2, 1, 3]]

    nodes10, tets10, edge_node = quadratic(nodes, tets)
    tris = boundary(tets)
    tris6 = np.hstack([tris, midside(tris, edge_node)])

    corners = nodes[tris]  # (m, 3, 3)
    normal = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    normal /= np.linalg.norm(normal, axis=1, keepdims=True)
    radial = np.abs(normal[:, 2]) < 0.5
    group = np.full(len(tris), -1, np.int64)
    names = list(SEATS)
    for k, name in enumerate(names):
        seat = SEATS[name]
        for c in cylinders["seats"][name]:
            hit = on_cylinder(corners, seat["xy"], c["radius_mm"], seat["z"], 0.3).all(axis=1) & radial
            group[hit] = k
    for b in cylinders["bolts"]:
        if b["radius_mm"] < 5.0:
            continue
        hit = on_cylinder(corners, b["xy"], b["radius_mm"], tuple(b["z"]), 0.3).all(axis=1) & radial
        group[hit & (group < 0)] = len(names)
    counts = {name: int((group == k).sum()) for k, name in enumerate(names)}
    counts["BOLTS"] = int((group == len(names)).sum())

    np.savez_compressed(
        CASE / "tet10.npz",
        nodes=nodes10,
        tets=tets10,
        tris=tris6,
        group=group,
        names=np.array([*names, "BOLTS"]),
        linear_nodes=len(nodes),
    )
    force = loads()
    (CASE / "setup.json").write_text(
        json.dumps(
            {
                "case": "agenticCAE e56235 production design, its own gmsh mesh",
                "seats": {n: {"force_N": force[n].tolist()} for n in names},
                "reference": {
                    "source": "agenticCAE handbook 14-objective, gcpv0032_e56235, TETRA10, Code_Aster 18.0.12",
                    "supports": "RBE2 per bolt position to a fixed point; RBE3 per seat",
                    "tilt_arcmin": {
                        "BORE_MAIN_S2": 2.1960,
                        "BORE_AX2_S3": 1.3490,
                        "BORE_AX1_S4": 1.1259,
                        "BORE_MAIN_S3": 0.5252,
                        "BORE_AX2_S2": 0.3131,
                        "BORE_AX1_S1": 0.3294,
                    },
                    "umax_mm": 0.4285,
                    "vm_p999_mpa": 67.8,
                    "vm_peak_mpa": 156.9,
                    "ims_lead_um": 19.04,
                    "solve_s": 560,
                },
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    info = {
        "edge_mm": 20.0,
        "linear_nodes": int(len(nodes)),
        "nodes": int(len(nodes10)),
        "dof": int(3 * len(nodes10)),
        "tets": int(len(tets10)),
        "boundary_triangles": int(len(tris)),
        "groups": counts,
        "quality": volume_quality(nodes, tets),
        "volume_mm3": float(np.abs(volume).sum() / 6.0),
        "seconds": round(time.time() - started, 1),
    }
    (CASE / "tet10.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
