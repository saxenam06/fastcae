"""The gate's regular route: gmsh meshes the production housing's CAD itself - its B-rep read by
OpenCASCADE, every surface and the volume held to the same size map as the field route (``sizes.npz``,
read by trilinear interpolation) - into linear tets that ``finish_mesh.py`` makes TET10 and labels as
it does every mesh.

    python gate_gmsh.py     # BENCH_CASE picks the case folder (gate3); writes gmsh_tets.npz, gmsh.json
"""

from __future__ import annotations

import json
import os
import time

os.environ.setdefault("BENCH_CASE", "gate3")

import gmsh  # noqa: E402
import numpy as np  # noqa: E402
from common import OUT  # noqa: E402
from gate_part import STEP  # noqa: E402

THREADS = 8


def size_map():
    s = np.load(OUT / "sizes.npz")
    size, origin, spacing = s["size"].astype(np.float64), s["origin"], float(s["spacing"])
    top = np.array(size.shape) - 2

    def at(x: float, y: float, z: float) -> float:
        u = (np.array([x, y, z]) - origin) / spacing
        i = np.clip(np.floor(u).astype(int), 0, top)
        a, b, c = np.clip(u - i, 0.0, 1.0)
        block = size[i[0] : i[0] + 2, i[1] : i[1] + 2, i[2] : i[2] + 2]
        yz = block[0] * (1 - a) + block[1] * a
        z_ = yz[0] * (1 - b) + yz[1] * b
        return float(z_[0] * (1 - c) + z_[1] * c)

    return at


def main() -> None:
    at = size_map()
    calls = [0]

    def size(dim, tag, x, y, z, lc):
        calls[0] += 1
        return at(x, y, z)

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 1)
    gmsh.option.setNumber("General.Verbosity", 3)
    gmsh.option.setNumber("General.NumThreads", THREADS)
    # gmsh's own repair of the B-rep - off by default: on this STEP it cannot fix a wire it sets out to.
    fix = int(os.environ.get("GATE_GMSH_FIX", "0"))
    for option in ("Geometry.OCCFixDegenerated", "Geometry.OCCFixSmallEdges", "Geometry.OCCFixSmallFaces"):
        gmsh.option.setNumber(option, fix)
    t0 = time.time()
    gmsh.model.occ.importShapes(str(STEP))
    if os.environ.get("GATE_GMSH_HEAL") == "1":
        gmsh.model.occ.healShapes()
    gmsh.model.occ.synchronize()
    volumes = gmsh.model.getEntities(3)
    print(f"imported {len(volumes)} volume(s), {len(gmsh.model.getEntities(2))} surfaces in {time.time() - t0:.0f} s",
          flush=True)
    gmsh.model.mesh.setSizeCallback(size)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
    gmsh.option.setNumber("Mesh.Algorithm", int(os.environ.get("GATE_GMSH_ALGORITHM", "6")))
    gmsh.option.setNumber("Mesh.Algorithm3D", 10)
    t0 = time.time()
    gmsh.model.mesh.generate(2)
    surface_s = time.time() - t0
    t0 = time.time()
    gmsh.model.mesh.generate(3)
    volume_s = time.time() - t0

    tags, coords, _ = gmsh.model.mesh.getNodes()
    nodes = coords.reshape(-1, 3)
    _, element_nodes = gmsh.model.mesh.getElementsByType(4)
    index = np.full(int(tags.max()) + 1, -1, np.int64)
    index[tags.astype(np.int64)] = np.arange(len(tags))
    tets = index[element_nodes.astype(np.int64)].reshape(-1, 4)
    gmsh.finalize()
    np.savez_compressed(OUT / "gmsh_tets.npz", nodes=nodes, tets=tets)
    info = {
        "mesher": "gmsh on the CAD (OpenCASCADE), sizes from sizes.npz",
        "surface_s": surface_s,
        "volume_s": volume_s,
        "size_calls": calls[0],
        "nodes": int(len(nodes)),
        "tets": int(len(tets)),
    }
    (OUT / "gmsh.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
