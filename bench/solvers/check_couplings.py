"""agenticCAE's supports - an RBE2 per bolt position, an RBE3 per seat - solved on the GPU against
Code_Aster's own couplings, on one case: the displacement field, and each seat's tilt read the way
agenticCAE read it (the RBE3 reference node's rotation; for the GPU, the same equal-weight fit).

    python check_couplings.py e56235
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

if len(sys.argv) > 1:
    os.environ["BENCH_CASE"] = sys.argv[1]

from common import ARCMIN, OUT, SEATS, seat_fit  # noqa: E402


def main() -> None:
    mesh = np.load(OUT / "tet10.npz")
    nodes, tris, group = mesh["nodes"], mesh["tris"], mesh["group"]
    aster = np.load(OUT / "aster_couplings.npz")
    gpu = np.load(OUT / "cudss_couplings.npz")["u"]
    ref = aster["u"]
    out = {
        "field_error": float(np.linalg.norm(gpu - ref) / np.linalg.norm(ref)),
        "umax_mm": {
            "aster": float(np.linalg.norm(ref, axis=1).max()),
            "gpu": float(np.linalg.norm(gpu, axis=1).max()),
        },
        "tilt_arcmin": {},
    }
    setup = json.loads((OUT / "setup.json").read_text(encoding="utf-8"))
    for k, name in enumerate(SEATS):
        members = np.unique(tris[group == k])
        w = np.ones(len(members))
        rbe3 = float(np.hypot(*aster["seat_rotation"][k, :2]) * ARCMIN)
        _, theta = seat_fit(nodes[members], gpu[members], w)
        row = {"aster_rbe3": rbe3, "gpu": float(np.hypot(theta[0], theta[1]) * ARCMIN)}
        if "reference" in setup:
            row["agenticcae"] = setup["reference"]["tilt_arcmin"][name]
        out["tilt_arcmin"][name] = row
    (OUT / "couplings.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
