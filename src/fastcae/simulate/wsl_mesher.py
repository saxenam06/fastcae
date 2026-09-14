"""Runs in WSL's ``fieldmesh`` environment, where the compiled mesher is: CGAL's Mesh_3 on a
distance
field or on a closed triangulated surface. Standalone - numpy and ``cgal_field`` only - and driven
through files in one folder, so the Windows side needs nothing of Linux's but a path:

- ``params.json`` - the mode (``field`` or ``surface``) and the mesher's settings;
- ``field.npz`` - the grid's origin, spacing, shape, inside bits, band and reach; or
  ``surface.npz`` -
  vertices and triangles;
- ``sizes.npz`` (optional) - an element-size grid: ``size``, ``origin``, ``spacing``;
- ``lines.npz`` (optional) - polylines the mesh must follow, ``line0``, ``line1`` ...

Writes ``tets.npz`` (nodes, linear tets) and ``mesh.json`` (what it did, and how long it took).

    python wsl_mesher.py /mnt/c/.../work
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

# A regular tet's circumradius is 0.61 of its edge, an equilateral triangle's 0.58; held to those,
# CGAL's tets come out at 0.81 and its boundary triangles at 0.75 of the size asked, so the bounds
# are
# set that much looser to get the size asked.
CELL_OF_EDGE, FACET_OF_EDGE = 0.61 / 0.81, 0.58 / 0.75


def main(work: Path) -> None:
    import cgal_field

    params = json.loads((work / "params.json").read_text())
    sized = {}
    if (work / "sizes.npz").exists():
        s = np.load(work / "sizes.npz")
        sized = dict(
            sizes=np.ascontiguousarray(s["size"], np.float32),
            size_origin=tuple(float(x) for x in s["origin"]),
            size_spacing=float(s["spacing"]),
            cell_factor=CELL_OF_EDGE,
            facet_factor=FACET_OF_EDGE,
        )
    lines = []
    if (work / "lines.npz").exists():
        held = np.load(work / "lines.npz")
        lines = [
            np.ascontiguousarray(held[k], np.float64)
            for k in sorted(held.files, key=lambda k: int(k[4:]))
        ]
    t0 = time.time()
    if params["mode"] == "field":
        f = np.load(work / "field.npz")
        shape = tuple(int(x) for x in f["shape"])
        reach = float(f["reach_mm"])
        inside = np.unpackbits(f["inside"], count=int(np.prod(shape))).astype(bool)
        sdf = np.where(inside, -reach, reach).astype(np.float32)
        sdf[f["band_index"]] = f["band_mm"]
        out = cgal_field.mesh(
            sdf.reshape(shape),
            tuple(float(x) for x in f["origin"]),
            float(f["spacing"]),
            reach,
            cell_size=params.get("cell", 40.0),
            facet_size=params.get("facet", 30.0),
            facet_distance=params.get("distance", 2.0),
            error_bound=params.get("error", 5e-6),
            threads=params.get("threads", 4),
            seed=params.get("seed", 0),
            lines=lines,
            edge_size=params.get("edge", 8.0),
            **sized,
        )
    else:
        s = np.load(work / "surface.npz")
        out = cgal_field.mesh_surface(
            np.ascontiguousarray(s["vertices"], np.float64),
            np.ascontiguousarray(s["triangles"], np.int64),
            feature_angle=params.get("feature_angle", 0.0),
            edge_size=params.get("edge", 8.0),
            cell_size=params.get("cell", 40.0),
            facet_size=params.get("facet", 30.0),
            facet_distance=params.get("distance", 2.0),
            threads=params.get("threads", 4),
            seed=params.get("seed", 0),
            lines=lines,
            **sized,
        )
    took = time.time() - t0
    nodes, tets = np.asarray(out["nodes"], np.float64), np.asarray(out["tets"], np.int64)
    np.savez(work / "tets.npz", nodes=nodes, tets=tets)
    info = {
        "mode": params["mode"],
        "seconds": took,
        **{k: float(out[k]) for k in ("refine_s", "perturb_s", "exude_s") if k in out},
        "nodes": int(len(nodes)),
        "tets": int(len(tets)),
        "lines": len(lines),
        "sized": bool(sized),
        "params": params,
    }
    (work / "mesh.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
