"""The design's surface meshed by gmsh instead of fTetWild - to see whether meshing, now the slow
step, can take minutes: the surface decimated as for fTetWild, gmsh splits it into patches at sharp
edges and re-parametrises each (``classifySurfaces``, ``createGeometry``), remeshes it at up to
20 mm - finer where curvature asks - and fills it with its parallel Delaunay mesher (HXT). TET10 and
labels as ``mesh_tet10.py`` makes them, into ``<case>/tet10.npz``.

    python mesh_gmsh.py [edge_mm] [triangles]   # BENCH_CASE=design7g, 20 mm, 200,000 triangles
"""

from __future__ import annotations

import json
import math
import sys
import time

import numpy as np
from common import OUT, SEATS
from mesh_tet10 import boundary, midside, quadratic, volume_quality
from scipy.spatial import cKDTree


def write_stl(path, vertices: np.ndarray, triangles: np.ndarray) -> None:
    """A binary STL of the triangles."""
    p = vertices[triangles].astype(np.float32)
    normal = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-30)
    record = np.zeros(len(triangles), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    record["n"], record["v"] = normal, p
    with open(path, "wb") as out:
        out.write(b"\0" * 80)
        out.write(np.uint32(len(triangles)).tobytes())
        out.write(record.tobytes())


def main() -> None:
    edge = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    target = int(sys.argv[2]) if len(sys.argv) > 2 else 200_000
    import fast_simplification
    import gmsh

    started = time.time()
    surface = np.load(OUT / "surface.npz")
    setup = json.loads((OUT / "setup.json").read_text(encoding="utf-8"))
    vertices, triangles, face_id = surface["vertices"], surface["triangles"], surface["face_id"]
    light_v, light_t = fast_simplification.simplify(
        vertices, triangles.astype(np.int32), target_reduction=max(0.0, 1.0 - target / len(triangles))
    )
    stl = OUT / "decimated.stl"
    write_stl(stl, light_v, light_t)
    decimated = time.time() - started
    print(f"decimated to {len(light_t):,} triangles in {decimated:.0f} s", flush=True)

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.option.setNumber("General.NumThreads", 16)
    t0 = time.time()
    gmsh.merge(str(stl))
    gmsh.model.mesh.classifySurfaces(40 * math.pi / 180, True, True, math.pi)
    gmsh.model.mesh.createGeometry()
    surfaces = gmsh.model.getEntities(2)
    loop = gmsh.model.geo.addSurfaceLoop([s[1] for s in surfaces])
    gmsh.model.geo.addVolume([loop])
    gmsh.model.geo.synchronize()
    geometry_s = time.time() - t0
    print(f"{len(surfaces)} patches in {geometry_s:.0f} s", flush=True)
    gmsh.option.setNumber("Mesh.MeshSizeMax", edge)
    gmsh.option.setNumber("Mesh.MeshSizeMin", 2.0)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 12)
    gmsh.option.setNumber("Mesh.Algorithm", 6)
    gmsh.option.setNumber("Mesh.Algorithm3D", 10)
    t0 = time.time()
    gmsh.model.mesh.generate(2)
    surface_s = time.time() - t0
    t0 = time.time()
    gmsh.model.mesh.generate(3)
    volume_s = time.time() - t0
    tags, coords, _ = gmsh.model.mesh.getNodes()
    types, _, cell_nodes = gmsh.model.mesh.getElements(3)
    gmsh.finalize()
    order = np.zeros(int(tags.max()) + 1, np.int64)
    order[tags.astype(np.int64)] = np.arange(len(tags))
    nodes = coords.reshape(-1, 3)
    tets = order[np.asarray(cell_nodes[list(types).index(4)], np.int64).reshape(-1, 4)]
    used = np.unique(tets)
    remap = np.full(len(nodes), -1, np.int64)
    remap[used] = np.arange(len(used))
    nodes, tets = nodes[used], remap[tets]
    p = nodes[tets]
    volume = np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))
    tets[volume < 0] = tets[volume < 0][:, [0, 2, 1, 3]]
    print(
        f"gmsh: {len(nodes):,} nodes, {len(tets):,} tets - surface {surface_s:.0f} s, volume {volume_s:.0f} s",
        flush=True,
    )

    nodes10, tets10, edge_node = quadratic(nodes, tets)
    tris = boundary(tets)
    tris6 = np.hstack([tris, midside(tris, edge_node)])
    tree = cKDTree(vertices[triangles].mean(axis=1))
    distance, nearest = tree.query(nodes[tris].mean(axis=1))
    tri_face = face_id[nearest]
    group = np.full(len(tris), -1, np.int64)
    names = list(SEATS)
    for k, name in enumerate(names):
        group[np.isin(tri_face, setup["seats"][name]["faces"])] = k
    group[np.isin(tri_face, setup["bolt_faces"])] = len(names)
    np.savez_compressed(
        OUT / "tet10.npz",
        nodes=nodes10,
        tets=tets10,
        tris=tris6,
        group=group,
        names=np.array([*names, "BOLTS"]),
        linear_nodes=len(nodes),
    )
    info = {
        "mesher": "gmsh 4.15 HXT on the decimated surface, reparametrised",
        "edge_mm": edge,
        "surface_triangles": {"design": int(len(triangles)), "meshed": int(len(light_t))},
        "seconds": {
            "decimate": round(decimated, 1),
            "geometry": round(geometry_s, 1),
            "surface": round(surface_s, 1),
            "volume": round(volume_s, 1),
            "total": round(time.time() - started, 1),
        },
        "linear_nodes": int(len(nodes)),
        "nodes": int(len(nodes10)),
        "dof": int(3 * len(nodes10)),
        "tets": int(len(tets10)),
        "boundary_triangles": int(len(tris)),
        "boundary_gap_mm": {"median": float(np.median(distance)), "max": float(distance.max())},
        "quality": volume_quality(nodes, tets),
        "volume_mm3": float(np.abs(volume).sum() / 6.0),
    }
    (OUT / "tet10.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
