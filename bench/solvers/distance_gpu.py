"""How fast the build's slowest step could be: exact unsigned distance from the design's grid cells
to the part's tessellation - what ``compose._part_distance`` computes, point against triangle, on
the CPU - as nearest-point queries against a bounding-volume hierarchy on the GPU (Warp), on the
cells of design #7's 3 mm field band. A measurement, not a change to the build.

    python distance_gpu.py
"""

from __future__ import annotations

import time

import numpy as np
import warp as wp
from common import OUT, SCRATCH

from fastcae import extract
from fastcae.generate.field import _unsigned_distance
from fastcae.project import Project

wp.config.quiet = True


@wp.kernel
def nearest(mesh: wp.uint64, points: wp.array(dtype=wp.vec3), reach: float, out: wp.array(dtype=float)):
    i = wp.tid()
    q = wp.mesh_query_point_no_sign(mesh, points[i], reach)
    if q.result:
        out[i] = wp.length(points[i] - wp.mesh_eval_position(mesh, q.face, q.u, q.v))
    else:
        out[i] = reach


def main() -> None:
    tess = extract.run(Project(root=SCRATCH / "e2e" / "projects" / "GRC_Gearbox_Housing")).tess
    f = np.load(OUT / "field.npz")
    origin, spacing, shape = f["origin"], float(f["spacing"]), tuple(int(x) for x in f["shape"])
    band = f["band_index"]
    reach = float(f["reach_mm"])
    ijk = np.stack(np.unravel_index(band, shape), axis=1)
    points = origin + ijk * spacing
    print(f"{len(tess.triangles):,} triangles; {len(points):,} band cells; reach {reach} mm", flush=True)

    t0 = time.time()
    mesh = wp.Mesh(
        points=wp.array(tess.vertices.astype(np.float32), dtype=wp.vec3),
        indices=wp.array(tess.triangles.astype(np.int32).ravel(), dtype=int),
    )
    wp.synchronize()
    bvh = time.time() - t0
    p = wp.array(points.astype(np.float32), dtype=wp.vec3)
    out = wp.zeros(len(points), dtype=float)
    wp.launch(nearest, dim=len(points), inputs=[mesh.id, p, reach, out])  # compile and warm up
    wp.synchronize()
    t0 = time.time()
    wp.launch(nearest, dim=len(points), inputs=[mesh.id, p, reach, out])
    wp.synchronize()
    gpu = time.time() - t0
    d_gpu = out.numpy()
    print(f"GPU: BVH {bvh:.2f} s, {len(points):,} queries {gpu:.2f} s", flush=True)

    # The CPU route on a slab of the same cells, for the rate and the agreement.
    from fastcae.generate.field import Grid

    k0 = int(np.median(ijk[:, 2]))
    slab = (ijk[:, 2] >= k0) & (ijk[:, 2] < k0 + 8)
    lo = ijk[slab].min(axis=0)
    hi = ijk[slab].max(axis=0)
    window = Grid(
        origin=tuple(float(v) for v in origin + lo * spacing),
        spacing_mm=spacing,
        shape=tuple(int(v) for v in hi - lo + 1),
    )
    t0 = time.time()
    d_cpu = _unsigned_distance(tess, window, reach)
    cpu = time.time() - t0
    local = ijk[slab] - lo
    d_cpu_band = np.minimum(d_cpu[local[:, 0], local[:, 1], local[:, 2]], reach)
    diff = np.abs(d_cpu_band - d_gpu[slab])
    gap = float(diff.max())
    worst = np.argsort(diff)[-3:]
    print(
        f"cells differing by over 0.01 mm: {int((diff > 0.01).sum())} of {len(diff):,}; worst at CPU "
        f"{d_cpu_band[worst].round(3)} GPU {d_gpu[slab][worst].round(3)}",
        flush=True,
    )
    print(
        f"CPU: a slab of {window.n_cells:,} cells ({slab.sum():,} in the band) in {cpu:.1f} s; "
        f"largest disagreement with the GPU {gap:.4f} mm",
        flush=True,
    )
    # A double-precision tree on the CPU (libigl's AABB): exact, and all 16 cores.
    import igl

    t0 = time.time()
    sq, _, _ = igl.point_mesh_squared_distance(
        points, tess.vertices.astype(np.float64), tess.triangles.astype(np.int64)
    )
    tree = time.time() - t0
    d_igl = np.minimum(np.sqrt(sq), reach)
    gap_igl = float(np.abs(d_igl[slab] - d_cpu_band).max())
    print(
        f"libigl: {len(points):,} queries in {tree:.1f} s; largest disagreement with the CPU route {gap_igl:.6f} mm",
        flush=True,
    )
    rate_cpu = window.n_cells / cpu
    rate_gpu = len(points) / gpu
    print(f"cells a second: CPU {rate_cpu:,.0f}, GPU {rate_gpu:,.0f} - {rate_gpu / rate_cpu:,.0f}x", flush=True)


if __name__ == "__main__":
    main()
