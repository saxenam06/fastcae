"""How a mesh made from a design's field holds the meshing rules - read on its boundary triangles,
each against the nearest surface point ``sizes.py`` measured:

- through a rib or thin wall: its thickness over the triangle's size - its mean edge - at least 2;
- round a concave curve: 2 pi R over its size, at least 16;
- everywhere: its size against the size asked for, and its longest edge against the panel size;

with the elements' quality (mean ratio, smallest dihedral angle), the unknowns as TET10, and how far
boundary nodes sit from where the field is zero.

    python mesh_report.py <case dir>     # reads cgal_tets.npz, sizes.npz, field.npz; writes mesh_report.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from mesh_cgal import load_sdf
from scipy.spatial import cKDTree
from sizes import sample

EDGES = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
MARGIN = 0.9  # a rule counts as held within 10 % of its number


def smallest_dihedral(p: np.ndarray) -> np.ndarray:
    normals = []
    for a, b, c in ((1, 2, 3), (0, 2, 3), (0, 1, 3), (0, 1, 2)):
        n = np.cross(p[:, b] - p[:, a], p[:, c] - p[:, a])
        normals.append(n / np.linalg.norm(n, axis=1, keepdims=True))
    worst = np.full(len(p), 180.0)
    for x in range(4):
        for y in range(x + 1, 4):
            cos = -np.einsum("ij,ij->i", normals[x], normals[y])
            worst = np.minimum(worst, np.degrees(np.arccos(np.clip(cos, -1, 1))))
    return worst


def share(x: np.ndarray) -> float:
    return float(x.mean()) if len(x) else 1.0


def main() -> None:
    here = Path(sys.argv[1])
    rules = json.loads((here / "sizes.json").read_text())["rules"]
    through_min, around_min, panel = rules["through"], rules["around"], rules["panel_mm"]
    made = np.load(here / "cgal_tets.npz")
    nodes, tets = made["nodes"], made["tets"]
    sizes = np.load(here / "sizes.npz")
    p = nodes[tets]
    volume = np.abs(np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))) / 6
    l2 = sum(np.sum((p[:, a] - p[:, b]) ** 2, axis=1) for a, b in EDGES)
    quality = 12 * (3 * volume) ** (2 / 3) / l2
    dihedral = smallest_dihedral(p)
    edges = np.unique(np.sort(np.concatenate([tets[:, list(e)] for e in EDGES]), 1), axis=0)

    faces = np.sort(np.concatenate([tets[:, [0, 1, 2]], tets[:, [0, 1, 3]], tets[:, [0, 2, 3]], tets[:, [1, 2, 3]]]), 1)
    unique, count = np.unique(faces, axis=0, return_counts=True)
    tris = unique[count == 1]
    q = nodes[tris]
    lengths = np.array([np.linalg.norm(q[:, a] - q[:, b], axis=1) for a, b in ((0, 1), (1, 2), (2, 0))])
    longest, size = lengths.max(axis=0), lengths.mean(axis=0)
    _, near = cKDTree(sizes["surface"]).query(q.mean(axis=1))
    rule, thick, radius, target = sizes["rule"][near], sizes["thickness"][near], sizes["radius"][near], sizes["target"][near]
    thin, curve = rule == "thickness", rule == "curve"
    through = thick[thin] / size[thin]
    around = 2 * np.pi * radius[curve] / size[curve]
    ratio = size / target

    sdf, origin, spacing, _ = load_sdf(here, np.float32)
    gap = np.abs(sample(sdf, origin, spacing, nodes[np.unique(tris)]))
    info = {
        "tets": int(len(tets)),
        "dof_tet10": int(3 * (len(nodes) + len(edges))),
        "quality": {"mean_ratio_min": float(quality.min()), "below_0.1": int((quality < 0.1).sum()),
                    "dihedral_min_deg": float(dihedral.min()), "dihedral_below_10": int((dihedral < 10).sum())},
        "boundary_gap_mm": {"median": float(np.median(gap)), "p99": float(np.percentile(gap, 99)),
                            "max": float(gap.max())},
        "through_thin": {"triangles": int(thin.sum()), "held": share(through >= through_min * MARGIN),
                         "p5": float(np.percentile(through, 5)) if len(through) else None},
        "round_curves": {"triangles": int(curve.sum()), "held": share(around >= around_min * MARGIN),
                         "p5": float(np.percentile(around, 5)) if len(around) else None},
        "panels": {"longest_edge_mm": float(longest.max()), "held": share(longest <= panel / MARGIN)},
        "edge_over_asked": {"median": float(np.median(ratio)), "p95": float(np.percentile(ratio, 95)),
                            "held": share(ratio <= 1 / MARGIN)},
    }
    (here / "mesh_report.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
