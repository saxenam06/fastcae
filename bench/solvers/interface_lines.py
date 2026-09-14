"""The edges of the faces loads and supports go on - each bearing seat's and each flange bolt hole's
cylinder, a circle at either end - as polylines for the field mesher to follow (``mesh_cgal.py
--lines``), so those faces are meshed exactly where the grid alone would round their edges.

    python interface_lines.py <case dir> [--seats]     # reads the case's cylinders.json; writes lines.npz

``--seats`` keeps the seats' circles only: each of the many small bolt holes' circles makes the mesh
dense round it.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from common import SEATS

STEP_MM = 3.0  # between a circle's points


def circle(xy, radius: float, z: float) -> np.ndarray:
    n = max(24, math.ceil(2 * math.pi * radius / STEP_MM))
    t = np.linspace(0.0, 2 * math.pi, n + 1)
    t[-1] = 0.0  # closed: the first point again, exactly
    return np.column_stack([xy[0] + radius * np.cos(t), xy[1] + radius * np.sin(t), np.full(n + 1, z)])


def main() -> None:
    here = Path(sys.argv[1])
    data = json.loads((here / "cylinders.json").read_text(encoding="utf-8"))
    rings = set()
    for name, found in data["seats"].items():
        for c in found:
            for z in c["z"]:
                rings.add((round(SEATS[name]["xy"][0], 3), round(SEATS[name]["xy"][1], 3), round(c["radius_mm"], 3), round(z, 3)))
    for c in [] if "--seats" in sys.argv else data["bolts"]:
        for z in c["z"]:
            rings.add((round(c["xy"][0], 3), round(c["xy"][1], 3), round(c["radius_mm"], 3), round(z, 3)))
    lines = {f"line{i}": circle((x, y), r, z) for i, (x, y, r, z) in enumerate(sorted(rings))}
    np.savez_compressed(here / "lines.npz", **lines)
    print(f"{len(lines)} circles, {sum(len(v) for v in lines.values())} points")


if __name__ == "__main__":
    main()
