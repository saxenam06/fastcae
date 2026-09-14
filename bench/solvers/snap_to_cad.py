"""A TET10 mesh's boundary moved onto the part's own CAD surface wherever the design leaves the part as it
is: each boundary corner to its nearest point on the CAD's triangulation, each boundary mid-side node to
the point nearest its edge's middle - so quadratic edges curve with the CAD, bores come out round and
fillets full - and every other mid-side node back to its edge's middle. A tet the move turns inside
out, or leaves with too little of its volume, takes its nodes back halfway until none does.

A design's field is exact where it differs from the part - its ribs are analytic; where it is the
part's, the CAD is more exact than any grid. So the boundary follows the CAD there, and nodes within
``--keep`` of a sample the design changed stay on the field. Any mesh can be given the same curved
mid-side nodes, so meshes of the part are compared alike.

    python snap_to_cad.py <case dir> [--surface cad_surface.npz] [--limit 3] [--keep 6]
        # rewrites the case's tet10.npz; writes snap.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import igl
import numpy as np
from scipy.spatial import cKDTree

EDGE = np.array([[0, 1], [1, 2], [2, 0], [0, 3], [1, 3], [2, 3]])
# Where the TET10 Jacobian is checked: the 4-point rule's points, the centroid and the corners.
QA, QB = 0.5854101966249685, 0.1381966011250105
POINTS = np.vstack([np.full((4, 4), QB) + np.eye(4) * (QA - QB), np.full((1, 4), 0.25), np.eye(4)])
# dL_i / d(xi, eta, zeta), with L1 = 1 - xi - eta - zeta.
DL = np.array([[-1.0, -1.0, -1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
SMALLEST = 0.05  # no point may keep less than this share of the straight tet's Jacobian


def gradients(l: np.ndarray) -> np.ndarray:
    """The ten shape functions' gradients in the reference, (10, 3), at barycentric point ``l``."""
    g = np.empty((10, 3))
    g[:4] = (4 * l[:, None] - 1) * DL
    for k, (a, b) in enumerate(EDGE):
        g[4 + k] = 4 * (l[b] * DL[a] + l[a] * DL[b])
    return g


GRADIENTS = np.stack([gradients(l) for l in POINTS])  # (points, 10, 3)


def worst_jacobian(nodes: np.ndarray, tets: np.ndarray) -> np.ndarray:
    """Each tet's smallest Jacobian over the check points, as a share of its straight corners' own."""
    x = nodes[tets]  # (m, 10, 3)
    j = np.einsum("mnc,pnd->mpcd", x, GRADIENTS)  # (m, points, 3, 3): column d is dX/d(reference d)
    det = np.linalg.det(j)
    straight = np.linalg.det(np.stack([x[:, 1] - x[:, 0], x[:, 2] - x[:, 0], x[:, 3] - x[:, 0]], axis=2))
    return det.min(axis=1) / straight


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("--surface", default="cad_surface.npz")
    parser.add_argument("--limit", type=float, default=3.0, help="a node further than this from the CAD stays, mm")
    parser.add_argument("--keep", type=float, default=6.0, help="nodes this near a changed sample stay, mm")
    args = parser.parse_args()

    mesh = dict(np.load(args.case / "tet10.npz"))
    nodes, tets, tris = mesh["nodes"].copy(), mesh["tets"], mesh["tris"]
    cad = np.load(args.case / args.surface)
    cv, ct = cad["vertices"], cad["triangles"].astype(np.int64)
    corners = np.unique(tris[:, :3])
    sides = np.unique(tris[:, 3:6])

    eligible = np.ones(len(nodes), bool)
    field = np.load(args.case / "field.npz")
    changed = field["changed"] if "changed" in field.files else np.empty(0, np.int64)
    if len(changed):
        where = np.asarray(field["origin"], float) + np.column_stack(
            np.unravel_index(changed, tuple(int(n) for n in field["shape"]))) * float(field["spacing"])
        near, _ = cKDTree(where).query(nodes, distance_upper_bound=args.keep)
        eligible = ~np.isfinite(near)

    def onto_cad(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        squared, _, closest = igl.point_mesh_squared_distance(points, cv, ct)
        return closest, np.sqrt(squared)

    start = nodes.copy()
    corner_to, corner_gap = onto_cad(nodes[corners])
    corner_ok = eligible[corners] & (corner_gap <= args.limit)
    share = np.zeros(len(nodes))  # how far along its move each node goes
    share[corners[corner_ok]] = 1.0
    share[sides[eligible[sides]]] = 1.0
    target = start.copy()
    target[corners[corner_ok]] = corner_to[corner_ok]

    def place(share: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        p = start.copy()
        p[corners] = start[corners] + share[corners, None] * (target[corners] - start[corners])
        for k, (a, b) in enumerate(EDGE):
            p[tets[:, 4 + k]] = 0.5 * (p[tets[:, a]] + p[tets[:, b]])
        middle = p[sides]
        to, gap = onto_cad(middle)
        s = np.where(gap <= args.limit, share[sides], 0.0)
        p[sides] = middle + s[:, None] * (to - middle)
        return p, gap

    before = float(worst_jacobian(start, tets).min())
    for rounds in range(8):
        placed, _ = place(share)
        worst = worst_jacobian(placed, tets)
        bad = worst < SMALLEST
        if not bad.any():
            break
        share[np.unique(tets[bad])] *= 0.5
    else:
        share[np.unique(tets[worst_jacobian(placed, tets) < SMALLEST])] = 0.0
        placed, _ = place(share)
    moved = np.linalg.norm(placed - start, axis=1)
    mesh["nodes"] = placed
    np.savez_compressed(args.case / "tet10.npz", **mesh)
    info = {
        "boundary_corners": int(len(corners)),
        "corners_snapped": int(corner_ok.sum()),
        "corners_too_far": int((eligible[corners] & ~corner_ok).sum()),
        "kept_on_field": int((~eligible[corners]).sum()),
        "move_mm": {"p50": float(np.median(moved[share > 0])) if (share > 0).any() else 0.0,
                    "p99": float(np.percentile(moved[share > 0], 99)) if (share > 0).any() else 0.0,
                    "max": float(moved.max())},
        "nodes_held_back": int((share[np.concatenate([corners, sides])] < 1).sum() - (~eligible[corners]).sum()),
        "rounds": rounds + 1,
        "worst_jacobian_share": {"before": before, "after": float(worst_jacobian(placed, tets).min())},
    }
    (args.case / "snap.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
