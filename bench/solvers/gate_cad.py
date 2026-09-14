"""The gate's CAD-surface route: the production housing meshed from its CAD's own triangulated surface -
the one its field is built from (``cad_surface.npz``), its sharp edges kept - by the same compiled CGAL
mesher as the field route, held to the same size map (``sizes.npz``) with the same factors, facet
distance and sliver passes; so the one difference from the field route is the 3 mm grid. Runs in the
WSL environment ``fieldmesh``:

    python gate_cad.py /mnt/c/.../<case> [--threads N] [--surface cad_surface.npz]
        # reads the surface and sizes.npz; writes cgal_tets.npz
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from mesh_cgal import CELL_OF_EDGE, FACET_OF_EDGE

FEATURE_ANGLE = 60.0  # degrees: an edge sharper than this is kept as an edge
FACET_DISTANCE = 2.0  # mm, as the field route


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--surface", default="cad_surface.npz")
    parser.add_argument("--feature-angle", type=float, default=FEATURE_ANGLE, help="0: no edges found, lines only")
    parser.add_argument("--lines", type=Path, help="polylines to follow, as for mesh_cgal.py")
    parser.add_argument("--edge", type=float, default=8.0, help="vertices along the lines at most this apart, mm")
    args = parser.parse_args()
    import cgal_field

    surface = np.load(args.case / args.surface)
    s = np.load(args.case / "sizes.npz")
    lines = []
    if args.lines:
        held = np.load(args.lines)
        lines = [np.ascontiguousarray(held[k], np.float64) for k in sorted(held.files, key=lambda k: int(k[4:]))]
    t0 = time.time()
    out = cgal_field.mesh_surface(
        np.ascontiguousarray(surface["vertices"], np.float64),
        np.ascontiguousarray(surface["triangles"], np.int64),
        feature_angle=args.feature_angle,
        edge_size=args.edge,
        facet_distance=FACET_DISTANCE,
        sizes=np.ascontiguousarray(s["size"], np.float32),
        size_origin=tuple(float(x) for x in s["origin"]),
        size_spacing=float(s["spacing"]),
        cell_factor=CELL_OF_EDGE,
        facet_factor=FACET_OF_EDGE,
        threads=args.threads,
        seed=0,
        lines=lines,
    )
    took = time.time() - t0
    nodes, tets = out["nodes"], out["tets"]
    np.savez_compressed(args.case / "cgal_tets.npz", nodes=nodes, tets=tets)
    info = {
        "mesher": f"CGAL Mesh_3 on the CAD's own triangulated surface ({args.surface})",
        "feature_angle_deg": args.feature_angle,
        "lines": str(args.lines) if args.lines else None,
        "edge_mm": args.edge,
        "facet_distance_mm": FACET_DISTANCE,
        "threads": args.threads,
        "seconds": took,
        **{k: float(out[k]) for k in ("refine_s", "perturb_s", "exude_s")},
        "nodes": int(len(nodes)),
        "tets": int(len(tets)),
    }
    (args.case / "cgal.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
