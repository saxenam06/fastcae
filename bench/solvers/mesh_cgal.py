"""The design meshed straight from its distance field by CGAL's mesher (Mesh_3) - no surface is made at
all. CGAL asks the field, point by point, whether it is inside the part and where a segment crosses its
surface: trilinear across the field's 3 mm grid, exact within its band. It builds tets whose boundary
facets lie within a set distance of where the field is zero, holds the cells to a size, and removes
slivers.

By default the field is answered in C++ by ``cgal_field`` (``cgal_field.cpp``, built by
``build_cgal_field.sh`` into the WSL micromamba environment ``fieldmesh``), surface points found to
5e-6 of the grid's diagonal. ``--python`` answers it in Python through pygalmesh instead, in the
``galmesh`` environment, where CGAL keeps its default of 1e-3 of a sphere about the origin:

    micromamba run -n fieldmesh python mesh_cgal.py /mnt/c/.../<case> [cell_mm] [facet_mm] [distance_mm]
        [--threads N] [--no-perturb] [--no-exude] [--sliver-bound DEG] [--time-limit S]
        [--sizes sizes.npz] [--lines lines.npz] [--python]

``--sizes`` reads an element-size grid (``size`` in mm, ``origin``, ``spacing``): cells and facets are
then held to that size, the facet distance stays a constant. ``--lines`` reads polylines the mesh must
follow - the edges of the faces loads and supports go on, which the grid alone would round - so those
faces come out exactly. Writes ``cgal_tets.npz`` - linear tets - for ``finish_mesh.py`` to make TET10
and label.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

# A regular tet's circumradius is 0.61 of its edge, an equilateral triangle's 0.58; held to those, CGAL's
# tets came out at 0.81 and its boundary triangles at 0.75 of the size asked on design #7, so the bounds
# are set that much looser to get the size asked.
CELL_OF_EDGE, FACET_OF_EDGE = 0.61 / 0.81, 0.58 / 0.75


def load_sdf(here: Path, dtype) -> tuple[np.ndarray, np.ndarray, float, float]:
    f = np.load(here / "field.npz")
    shape = tuple(int(x) for x in f["shape"])
    reach = float(f["reach_mm"])
    inside = np.unpackbits(f["inside"], count=int(np.prod(shape))).astype(bool)
    sdf = np.where(inside, -reach, reach).astype(dtype)
    sdf[f["band_index"]] = f["band_mm"]
    return sdf.reshape(shape), np.asarray(f["origin"], float), float(f["spacing"]), reach


def compiled(here: Path, args: argparse.Namespace) -> dict:
    import cgal_field

    sdf, origin, spacing, reach = load_sdf(here, np.float32)
    sized = {}
    if args.sizes:
        s = np.load(args.sizes)
        sized = dict(
            sizes=np.ascontiguousarray(s["size"], np.float32),
            size_origin=tuple(float(x) for x in s["origin"]),
            size_spacing=float(s["spacing"]),
            cell_factor=CELL_OF_EDGE,
            facet_factor=FACET_OF_EDGE,
        )
    lines = []
    if args.lines:
        held = np.load(args.lines)
        lines = [np.ascontiguousarray(held[k], np.float64) for k in sorted(held.files, key=lambda k: int(k[4:]))]
    out = cgal_field.mesh(
        sdf,
        tuple(origin),
        spacing,
        reach,
        cell_size=args.cell,
        facet_size=args.facet,
        facet_distance=args.distance,
        error_bound=args.error,
        perturb=not args.no_perturb,
        exude=not args.no_exude,
        sliver_bound=args.sliver_bound,
        time_limit=args.time_limit,
        threads=args.threads,
        seed=args.seed,
        lines=lines,
        edge_size=args.edge,
        **sized,
    )
    return out


def python(here: Path, args: argparse.Namespace) -> dict:
    import pygalmesh

    sdf, origin, spacing, reach = load_sdf(here, np.float64)
    nx, ny, nz = sdf.shape
    values = memoryview(sdf.ravel())
    ox, oy, oz = origin
    far = max(np.linalg.norm(origin), np.linalg.norm(origin + np.asarray(sdf.shape) * spacing)) + 10.0
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

    mesh = pygalmesh.generate_mesh(
        Field(),
        max_cell_circumradius=args.cell,
        max_radius_surface_delaunay_ball=args.facet,
        max_facet_distance=args.distance,
        min_facet_angle=25.0,
        max_circumradius_edge_ratio=2.0,
        perturb=not args.no_perturb,
        exude=not args.no_exude,
        seed=0,
        verbose=False,
    )
    return {
        "nodes": np.asarray(mesh.points, np.float64),
        "tets": np.asarray(mesh.cells_dict["tetra"], np.int64),
        "field_queries": calls[0],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("cell", type=float, nargs="?", default=12.5, help="largest cell circumradius, mm")
    parser.add_argument("facet", type=float, nargs="?", default=10.0, help="largest surface facet circumradius, mm")
    parser.add_argument("distance", type=float, nargs="?", default=0.5, help="facets within this of the surface, mm")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0, help="where CGAL starts - another seed, another mesh of the same")
    parser.add_argument("--no-perturb", action="store_true")
    parser.add_argument("--no-exude", action="store_true")
    parser.add_argument("--sliver-bound", type=float, default=0.0, help="stop removing slivers above this angle, deg")
    parser.add_argument("--time-limit", type=float, default=0.0, help="each sliver pass at most this long, s")
    parser.add_argument("--error", type=float, default=5e-6, help="surface points to this share of the diagonal")
    parser.add_argument("--sizes", type=Path, help="element-size grid, npz with size, origin, spacing")
    parser.add_argument("--lines", type=Path, help="polylines the mesh follows, npz with line0, line1, ...")
    # Along a line CGAL keeps other vertices out of a ball round each of its own, so a coarse spacing
    # there cuts off whatever small the line runs beside - a shoulder under a seat, measured.
    parser.add_argument("--edge", type=float, default=3.0, help="vertices along the lines at most this apart, mm")
    parser.add_argument("--python", action="store_true", help="answer the field in Python, through pygalmesh")
    args = parser.parse_args()

    t0 = time.time()
    out = python(args.case, args) if args.python else compiled(args.case, args)
    took = time.time() - t0
    nodes, tets = out["nodes"], out["tets"]
    np.savez_compressed(args.case / "cgal_tets.npz", nodes=nodes, tets=tets)
    info = {
        "mesher": "CGAL Mesh_3 on the distance field, " + ("pygalmesh" if args.python else "compiled"),
        "cell_circumradius_mm": args.cell,
        "facet_circumradius_mm": args.facet,
        "facet_distance_mm": args.distance,
        "sizes": str(args.sizes) if args.sizes else None,
        "lines": str(args.lines) if args.lines else None,
        "edge_mm": args.edge if args.lines else None,
        "error_bound": None if args.python else args.error,
        "threads": args.threads,
        "seed": args.seed,
        "perturb": not args.no_perturb,
        "exude": not args.no_exude,
        "sliver_bound_deg": args.sliver_bound,
        "time_limit_s": args.time_limit,
        "seconds": took,
        **{k: float(out[k]) for k in ("refine_s", "perturb_s", "exude_s") if k in out},
        "field_queries": int(out["field_queries"]),
        "nodes": int(len(nodes)),
        "tets": int(len(tets)),
    }
    (args.case / "cgal.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
