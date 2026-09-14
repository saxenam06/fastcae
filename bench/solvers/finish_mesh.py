"""Linear tets made elsewhere - CGAL in WSL, gmsh on the CAD - finished as every mesher here finishes
them: TET10 with straight mid-side nodes, each boundary triangle labelled by the CAD face of the
surface triangle nearest it (the design's surface, or the part's own), the mesh's distance from that
surface measured.

    python finish_mesh.py cgal_tets.npz     # BENCH_CASE picks the case folder
"""

from __future__ import annotations

import json
import sys

import numpy as np
from common import OUT, SEATS
from mesh_tet10 import boundary, midside, quadratic, volume_quality


def main() -> None:
    made = np.load(OUT / sys.argv[1])
    nodes, tets = np.asarray(made["nodes"], np.float64), np.asarray(made["tets"], np.int64)
    used, compact = np.unique(tets, return_inverse=True)
    nodes, tets = nodes[used], compact.reshape(tets.shape)
    p = nodes[tets]
    volume = np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))
    tets[volume < 0] = tets[volume < 0][:, [0, 2, 1, 3]]
    surface = np.load(OUT / "surface.npz")
    setup = json.loads((OUT / "setup.json").read_text(encoding="utf-8"))
    vertices, triangles, face_id = surface["vertices"], surface["triangles"], surface["face_id"]

    import igl

    nodes10, tets10, edge_node = quadratic(nodes, tets)
    tris = boundary(tets)
    tris6 = np.hstack([tris, midside(tris, edge_node)])
    # The surface triangle truly nearest each boundary triangle's centre: a CAD triangulation has
    # triangles hundreds of millimetres long, whose centres say nothing about what lies near them.
    _, nearest, _ = igl.point_mesh_squared_distance(nodes[tris].mean(axis=1), vertices, triangles.astype(np.int64))
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
    squared, _, _ = igl.point_mesh_squared_distance(nodes[np.unique(tris)], vertices, triangles.astype(np.int64))
    gap = np.sqrt(squared)
    info = {
        "from": sys.argv[1],
        "linear_nodes": int(len(nodes)),
        "nodes": int(len(nodes10)),
        "dof": int(3 * len(nodes10)),
        "tets": int(len(tets10)),
        "boundary_triangles": int(len(tris)),
        "boundary_from_design_mm": {
            "median": float(np.median(gap)),
            "p99": float(np.percentile(gap, 99)),
            "max": float(gap.max()),
        },
        "quality": volume_quality(nodes, tets),
        "volume_mm3": float(np.abs(volume).sum() / 6.0),
    }
    extra = OUT / (sys.argv[1].replace("_tets.npz", ".json"))
    if extra.exists():
        info["mesher"] = json.loads(extra.read_text(encoding="utf-8"))
    (OUT / "tet10.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
