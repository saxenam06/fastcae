"""A size map read off a mesh: the mean edge of the tets nearest each point of a grid twice the field's
spacing - so another mesher can be held to the same element sizes as this mesh, point by point. Used to
hold the gate's field and CAD-surface routes to the sizes of agenticCAE's own mesh of the part.

    python sizes_from_mesh.py <mesh case dir> <target case dir>
        # reads cgal_tets.npz from the first, field.npz from the second; writes sizes.npz, sizes.json there
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
from sizes import STRIDE

EDGES = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
NEAREST = 4  # tets averaged at each point


def main() -> None:
    source, target = Path(sys.argv[1]), Path(sys.argv[2])
    made = np.load(source / "cgal_tets.npz")
    nodes, tets = made["nodes"], made["tets"]
    p = nodes[tets]
    edge = np.mean([np.linalg.norm(p[:, a] - p[:, b], axis=1) for a, b in EDGES], axis=0)
    centres = p.mean(axis=1)
    f = np.load(target / "field.npz")
    shape = -(-np.asarray(f["shape"]) // STRIDE)
    origin, spacing = np.asarray(f["origin"], float), STRIDE * float(f["spacing"])
    grid = origin + np.stack(np.meshgrid(*[np.arange(n) for n in shape], indexing="ij"), -1).reshape(-1, 3) * spacing
    _, near = cKDTree(centres).query(grid, k=NEAREST)
    size = edge[near].mean(axis=1).reshape(tuple(shape)).astype(np.float32)
    faces = np.sort(np.concatenate([tets[:, [0, 1, 2]], tets[:, [0, 1, 3]], tets[:, [0, 2, 3]], tets[:, [1, 2, 3]]]), 1)
    unique, count = np.unique(faces, axis=0, return_counts=True)
    boundary = nodes[unique[count == 1]]
    surface = boundary.mean(axis=1)
    asked = np.mean([np.linalg.norm(boundary[:, a] - boundary[:, b], axis=1) for a, b in ((0, 1), (1, 2), (2, 0))], 0)
    np.savez_compressed(
        target / "sizes.npz",
        size=size,
        origin=origin,
        spacing=spacing,
        surface=surface,
        thickness=np.full(len(surface), np.inf),
        radius=np.full(len(surface), np.inf),
        target=asked,
        rule=np.full(len(surface), "mesh"),
    )
    info = {
        "rules": {"through": 0, "around": 0, "panel_mm": float(edge.max()), "from_mesh": str(source)},
        "size_grid": {"shape": [int(n) for n in shape], "spacing_mm": spacing},
        "mesh_tets": int(len(tets)),
        "tet_edge_mm": {q: float(np.percentile(edge, v)) for q, v in (("p5", 5), ("median", 50), ("p95", 95))},
    }
    (target / "sizes.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
