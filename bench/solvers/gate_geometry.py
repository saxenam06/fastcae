"""Where each of the gate's meshes leaves the CAD, both ways: mesh surface further than TOLERANCE from
the CAD's (metal a route invented - a lid, a gap closed) and CAD surface further than that from the
mesh's (a feature a route lost), gathered into places by a coarse grid, largest first; and each
mesh's volume against the CAD's.

    python gate_geometry.py [case ...]     # gate3reg gate3 by default; reads the gate part's surface.npz
"""

from __future__ import annotations

import sys

import igl
import numpy as np
from common import SCRATCH

TOLERANCE, CELL, SHOWN = 1.5, 40.0, 8


def boundary(tets: np.ndarray) -> np.ndarray:
    faces = np.sort(np.concatenate([tets[:, [0, 1, 2]], tets[:, [0, 1, 3]], tets[:, [0, 2, 3]], tets[:, [1, 2, 3]]]), 1)
    unique, count = np.unique(faces, axis=0, return_counts=True)
    return unique[count == 1]


def places(points: np.ndarray, gap: np.ndarray) -> list[str]:
    far = gap > TOLERANCE
    if not far.any():
        return []
    cells = np.floor(points[far] / CELL).astype(np.int64)
    _, which, count = np.unique(cells, axis=0, return_inverse=True, return_counts=True)
    order = np.argsort(-count)[:SHOWN]
    out = []
    for c in order:
        here = which.ravel() == c
        centre = points[far][here].mean(axis=0)
        out.append(f"{count[c]:5d} points, up to {gap[far][here].max():5.1f} mm, near ({centre[0]:.0f}, {centre[1]:.0f}, {centre[2]:.0f})")
    return out


def volume(nodes: np.ndarray, tets: np.ndarray) -> float:
    p = nodes[tets[:, :4]]
    return float(np.abs(np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))).sum() / 6)


def main() -> None:
    cad = np.load(SCRATCH / "solve" / "gate3" / "surface.npz")
    cv, ct = cad["vertices"], cad["triangles"].astype(np.int64)
    p = cv[ct]
    cad_volume = float(np.einsum("ij,ij->i", p[:, 0], np.cross(p[:, 1], p[:, 2])).sum() / 6)
    print(f"CAD volume {abs(cad_volume) / 1e3:.1f} cm3")
    for case in sys.argv[1:] or ["gate3reg", "gate3"]:
        made = np.load(SCRATCH / "solve" / case / "cgal_tets.npz")
        nodes, tets = made["nodes"], made["tets"]
        tris = boundary(tets)
        mesh_points = nodes[np.unique(tris)]
        invented, _, _ = igl.point_mesh_squared_distance(mesh_points, cv, ct)
        lost, _, _ = igl.point_mesh_squared_distance(cv, nodes, tris.astype(np.int64))
        print(f"\n{case}: volume {volume(nodes, tets) / 1e3:.1f} cm3")
        print(f"  mesh surface off the CAD by more than {TOLERANCE} mm:")
        for line in places(mesh_points, np.sqrt(invented)):
            print("   ", line)
        print(f"  CAD surface off the mesh by more than {TOLERANCE} mm:")
        for line in places(cv, np.sqrt(lost)):
            print("   ", line)


if __name__ == "__main__":
    main()
