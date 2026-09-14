"""The design's surface meshed with quadratic tetrahedra (TET10, C3D10), as agenticCAE solved this
housing: linear tets from fTetWild, then a mid-side node on every edge - straight edges, as
agenticCAE's conversion left them. Every boundary triangle is labelled with the CAD face it lies on,
so the six bearing seats and the flange's bolt holes become groups every solver applies the same way.

    python mesh_tet10.py [edge_mm] [triangles]   # 20 mm, 400,000 triangles by default

The design's surface - millions of triangles at the field's 3 mm - is first decimated by quadric
error to a few hundred thousand, which fTetWild meshes in minutes rather than an hour; its envelope
then holds the tets' boundary within 0.95 mm of that. Labels still come from the full surface.
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
from common import OUT, SEATS
from scipy.spatial import cKDTree

# The six edges of a tetrahedron, in TET10's order: (0,1) (1,2) (2,0) (0,3) (1,3) (2,3) - the same
# for VTK, MED and Code_Aster.
EDGES = np.array([[0, 1], [1, 2], [2, 0], [0, 3], [1, 3], [2, 3]])
# A tetrahedron's four faces, each seen from outside when the tet is positively oriented.
FACES = np.array([[0, 2, 1], [0, 1, 3], [1, 2, 3], [0, 3, 2]])


def quadratic(nodes: np.ndarray, tets: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    """TET10 from TET4: one node at the middle of every edge, shared by the tets round it."""
    edges = np.sort(tets[:, EDGES].reshape(-1, 2), axis=1)
    unique, inverse = np.unique(edges, axis=0, return_inverse=True)
    middle = 0.5 * (nodes[unique[:, 0]] + nodes[unique[:, 1]])
    nodes10 = np.vstack([nodes, middle])
    tets10 = np.hstack([tets, len(nodes) + inverse.reshape(-1, 6)])
    edge_node = {tuple(e): len(nodes) + i for i, e in enumerate(unique)}
    return nodes10, tets10, edge_node


def midside(tris: np.ndarray, edge_node: dict) -> np.ndarray:
    """Each boundary triangle's three mid-side nodes, in TRIA6 order: (0,1) (1,2) (2,0)."""
    return np.array(
        [[edge_node[tuple(sorted((a, b)))] for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0]))] for t in tris]
    )


def boundary(tets: np.ndarray) -> np.ndarray:
    """The triangles on the outside: faces that belong to one tet only, outward-oriented."""
    faces = tets[:, FACES].reshape(-1, 3)
    key = np.sort(faces, axis=1)
    _, first, counts = np.unique(key, axis=0, return_index=True, return_counts=True)
    return faces[first[counts == 1]]


def main() -> None:
    edge = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    target = int(sys.argv[2]) if len(sys.argv) > 2 else 400_000
    import fast_simplification
    import pytetwild

    started = time.time()
    surface = np.load(OUT / "surface.npz")
    setup = json.loads((OUT / "setup.json").read_text(encoding="utf-8"))
    vertices, triangles, face_id = surface["vertices"], surface["triangles"], surface["face_id"]
    reduction = max(0.0, 1.0 - target / len(triangles))
    light_v, light_t = fast_simplification.simplify(vertices, triangles.astype(np.int32), target_reduction=reduction)
    decimated = time.time() - started
    print(
        f"decimated {len(triangles):,} -> {len(light_t):,} triangles in {decimated:.0f} s",
        flush=True,
    )
    # The envelope, relative to the bounding box's diagonal, and how hard fTetWild optimises: the
    # defaults here are tight; MESH_EPSILON=1e-3 MESH_STOP_ENERGY=20 MESH_OPT_ITERS=40 is quicker.
    settings = {
        "epsilon": float(os.environ.get("MESH_EPSILON", 5e-4)),
        "stop_energy": float(os.environ.get("MESH_STOP_ENERGY", 10.0)),
        "num_opt_iter": int(os.environ.get("MESH_OPT_ITERS", 80)),
    }
    nodes, tets = pytetwild.tetrahedralize(
        light_v.astype(np.float64),
        light_t.astype(np.int32),
        edge_length_abs=edge,
        optimize=True,
        coarsen=True,
        **settings,
    )
    tets = tets.astype(np.int64)
    # Positive orientation throughout.
    p = nodes[tets]
    volume = np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))
    flip = volume < 0
    tets[flip] = tets[flip][:, [0, 2, 1, 3]]
    print(f"fTetWild: {len(nodes):,} nodes, {len(tets):,} tets in {time.time() - started:.0f} s")

    nodes10, tets10, edge_node = quadratic(nodes, tets)
    tris = boundary(tets)
    tris6 = np.hstack([tris, midside(tris, edge_node)])

    # Each boundary triangle takes the CAD face of the design-surface triangle nearest its middle.
    centres = vertices[triangles].mean(axis=1)
    tree = cKDTree(centres)
    distance, nearest = tree.query(nodes[tris].mean(axis=1))
    tri_face = face_id[nearest]
    group = np.full(len(tris), -1, np.int64)
    names = list(SEATS)
    for k, name in enumerate(names):
        group[np.isin(tri_face, setup["seats"][name]["faces"])] = k
    group[np.isin(tri_face, setup["bolt_faces"])] = len(names)
    counts = {name: int((group == k).sum()) for k, name in enumerate(names)}
    counts["BOLTS"] = int((group == len(names)).sum())

    quality = volume_quality(nodes, tets)
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
        "edge_mm": edge,
        "envelope_mm": settings["epsilon"] * float(np.linalg.norm(vertices.max(axis=0) - vertices.min(axis=0))),
        "ftetwild": settings,
        "surface_triangles": {
            "design": int(len(triangles)),
            "meshed": int(len(light_t)),
            "decimate_s": round(decimated, 1),
        },
        "linear_nodes": int(len(nodes)),
        "nodes": int(len(nodes10)),
        "dof": int(3 * len(nodes10)),
        "tets": int(len(tets10)),
        "boundary_triangles": int(len(tris)),
        "groups": counts,
        "boundary_gap_mm": {"median": float(np.median(distance)), "max": float(distance.max())},
        "quality": quality,
        "volume_mm3": float(np.abs(volume).sum() / 6.0),
        "seconds": round(time.time() - started, 1),
    }
    (OUT / "tet10.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(json.dumps(info, indent=1))


def volume_quality(nodes: np.ndarray, tets: np.ndarray) -> dict:
    """Mean-ratio quality of the linear tets: 1 for a regular tet, 0 for a flat one."""
    p = nodes[tets]
    v = np.abs(np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))) / 6.0
    l2 = sum(np.sum((p[:, a] - p[:, b]) ** 2, axis=1) for a, b in EDGES)
    q = 12.0 * (3.0 * v) ** (2.0 / 3.0) / l2
    return {
        "min": float(q.min()),
        "p1": float(np.percentile(q, 1)),
        "below_0.1": int((q < 0.1).sum()),
    }


if __name__ == "__main__":
    main()
