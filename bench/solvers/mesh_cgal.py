"""The design meshed straight from its distance field by CGAL's mesher (Mesh_3, through pygalmesh) -
no surface is made at all. CGAL asks the field, point by point, whether it is inside the part and
how far from its surface: trilinear across the field's 3 mm grid, exact within its band. It builds
tets whose boundary facets lie within a set distance of where the field is zero, holds the cells to
a size, and removes slivers. Runs inside WSL, in the ``galmesh`` micromamba environment:

    micromamba run -n galmesh python mesh_cgal.py /mnt/c/.../<case> [cell_mm] [facet_mm] [distance_mm]

Writes ``cgal_tets.npz`` - linear tets - for ``finish_mesh.py`` to make TET10 and label.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(sys.argv[1])
CELL = float(sys.argv[2]) if len(sys.argv) > 2 else 12.5  # largest cell circumradius, mm
FACET = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0  # largest surface facet circumradius, mm
DISTANCE = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5  # facets within this of the surface, mm


def main() -> None:
    import pygalmesh

    f = np.load(HERE / "field.npz")
    shape = tuple(int(x) for x in f["shape"])
    reach = float(f["reach_mm"])
    origin = np.asarray(f["origin"], float)
    spacing = float(f["spacing"])
    inside = np.unpackbits(f["inside"], count=int(np.prod(shape))).astype(bool)
    sdf = np.where(inside, -reach, reach).astype(np.float64)
    sdf[f["band_index"]] = f["band_mm"]
    values = memoryview(sdf)
    nx, ny, nz = shape
    ox, oy, oz = origin
    far = max(np.linalg.norm(origin), np.linalg.norm(origin + np.asarray(shape) * spacing)) + 10.0
    calls = [0]

    class Field(pygalmesh.DomainBase):
        def __init__(self):
            super().__init__()

        def eval(self, x):
            calls[0] += 1
            u = (x[0] - ox) / spacing
            v = (x[1] - oy) / spacing
            w = (x[2] - oz) / spacing
            i, j, k = int(u // 1), int(v // 1), int(w // 1)
            if i < 0 or j < 0 or k < 0 or i >= nx - 1 or j >= ny - 1 or k >= nz - 1:
                return reach
            a, b, c = u - i, v - j, w - k
            base = (i * ny + j) * nz + k
            sy, sx = nz, ny * nz
            c00 = values[base] * (1 - c) + values[base + 1] * c
            c01 = values[base + sy] * (1 - c) + values[base + sy + 1] * c
            c10 = values[base + sx] * (1 - c) + values[base + sx + 1] * c
            c11 = values[base + sx + sy] * (1 - c) + values[base + sx + sy + 1] * c
            return (c00 * (1 - b) + c01 * b) * (1 - a) + (c10 * (1 - b) + c11 * b) * a

        def get_bounding_sphere_squared_radius(self):
            return far * far

    t0 = time.time()
    mesh = pygalmesh.generate_mesh(
        Field(),
        max_cell_circumradius=CELL,
        max_radius_surface_delaunay_ball=FACET,
        max_facet_distance=DISTANCE,
        min_facet_angle=25.0,
        max_circumradius_edge_ratio=2.0,
        perturb=True,
        exude=True,
        seed=0,
        verbose=False,
    )
    took = time.time() - t0
    nodes = np.asarray(mesh.points, np.float64)
    tets = np.asarray(mesh.cells_dict["tetra"], np.int64)
    np.savez_compressed(HERE / "cgal_tets.npz", nodes=nodes, tets=tets)
    info = {
        "mesher": "CGAL Mesh_3 on the distance field (pygalmesh)",
        "cell_circumradius_mm": CELL,
        "facet_circumradius_mm": FACET,
        "facet_distance_mm": DISTANCE,
        "seconds": took,
        "field_queries": calls[0],
        "nodes": int(len(nodes)),
        "tets": int(len(tets)),
    }
    (HERE / "cgal.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
