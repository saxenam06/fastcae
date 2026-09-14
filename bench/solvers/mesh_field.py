"""The design meshed straight from its distance field - no surface is made at all. The field's own
grid, taken at every ``stride``-th point, is cut into tets: six to a cube, split along its long
diagonal the same way in every cube, so neighbours share their faces. Only cubes with a corner inside
the part are kept. Each corner carries the field's signed distance; MMG cuts the tets where that
distance is zero - the part's surface - and remeshes what lies inside to the chosen size with good
elements. The surface exists only as MMG's cut. TET10 and labels as the other meshers make them.

    python mesh_field.py [edge_mm] [stride] [hausd_mm]    # 20 mm, every 2nd point (6 mm), 0.5 mm
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np
from common import OUT, SEATS
from mesh_tet10 import boundary, midside, quadratic, volume_quality
from scipy.spatial import cKDTree

# The six tets of a cube, each a path from its corner (0,0,0) to (1,1,1) along the three axes in
# one order - the Kuhn split, which every cube makes alike, so the tets of neighbours meet face to face.
KUHN = []
for first in range(3):
    for second in range(3):
        if second == first:
            continue
        a = [0, 0, 0]
        a[first] = 1
        b = list(a)
        b[second] = 1
        KUHN.append([(0, 0, 0), tuple(a), tuple(b), (1, 1, 1)])


def signed_distance() -> tuple[np.ndarray, np.ndarray, float, float]:
    """The field's signed distance at every grid point - exact within its band, its reach beyond,
    negative inside - with the grid's origin and spacing, and the reach."""
    f = np.load(OUT / "field.npz")
    shape = tuple(int(x) for x in f["shape"])
    reach = float(f["reach_mm"])
    inside = np.unpackbits(f["inside"], count=int(np.prod(shape))).astype(bool)
    sdf = np.where(inside, -reach, reach).astype(np.float32)
    sdf[f["band_index"]] = f["band_mm"]
    return sdf.reshape(shape), np.asarray(f["origin"], float), float(f["spacing"]), reach


def background(sdf: np.ndarray, origin: np.ndarray, spacing: float, stride: int):
    """Tets over every cube of the coarser lattice with a corner inside the part, and the signed
    distance at their corners."""
    sub = sdf[::stride, ::stride, ::stride]
    h = spacing * stride
    nx, ny, nz = sub.shape
    ii = np.stack(np.meshgrid(np.arange(nx - 1), np.arange(ny - 1), np.arange(nz - 1), indexing="ij"), -1)
    ii = ii.reshape(-1, 3)
    corners = np.array([(a, b, c) for a in (0, 1) for b in (0, 1) for c in (0, 1)])
    values = np.stack([sub[ii[:, 0] + a, ii[:, 1] + b, ii[:, 2] + c] for a, b, c in corners], axis=1)
    cubes = ii[values.min(axis=1) < 0.0]
    flat = lambda p: (p[..., 0] * ny + p[..., 1]) * nz + p[..., 2]  # noqa: E731
    tets = np.concatenate([np.stack([flat(cubes + np.array(v)) for v in path], axis=1) for path in KUHN])
    used, compact = np.unique(tets, return_inverse=True)
    tets = compact.reshape(tets.shape)
    ijk = np.stack(np.unravel_index(used, sub.shape), axis=1)
    points = origin + ijk * h
    level = sub.ravel()[used].astype(np.float64)
    p = points[tets]
    volume = np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))
    tets[volume < 0] = tets[volume < 0][:, [0, 2, 1, 3]]
    return points, tets, level, len(cubes)


def main() -> None:
    edge = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    stride = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    hausd = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
    import mmgpy

    started = time.time()
    surface = np.load(OUT / "surface.npz")
    setup = json.loads((OUT / "setup.json").read_text(encoding="utf-8"))
    vertices, triangles, face_id = surface["vertices"], surface["triangles"], surface["face_id"]
    sdf, origin, spacing, reach = signed_distance()
    points, tets, level, cubes = background(sdf, origin, spacing, stride)
    background_s = time.time() - started
    print(
        f"background: {cubes:,} cubes of {spacing * stride:g} mm, {len(points):,} points, {len(tets):,} tets "
        f"in {background_s:.0f} s",
        flush=True,
    )

    t0 = time.time()
    mesh = mmgpy.MmgMesh3D(points, tets.astype(np.int32))
    result = mesh.remesh_levelset(level.reshape(-1, 1), hmax=edge, hausd=hausd, hgrad=1.3, verbose=-1)
    mmg_s = time.time() - t0
    all_tets, refs = mesh.get_tetrahedra_with_refs()
    all_nodes = np.asarray(mesh.get_vertices(), np.float64)
    inner = np.asarray(all_tets, np.int64)[np.asarray(refs) == 3]
    used, compact = np.unique(inner, return_inverse=True)
    nodes, tets = all_nodes[used], compact.reshape(inner.shape)
    p = nodes[tets]
    volume = np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))
    tets[volume < 0] = tets[volume < 0][:, [0, 2, 1, 3]]
    print(f"MMG: {len(nodes):,} nodes, {len(tets):,} tets inside in {mmg_s:.0f} s ({result})", flush=True)

    nodes10, tets10, edge_node = quadratic(nodes, tets)
    tris = boundary(tets)
    tris6 = np.hstack([tris, midside(tris, edge_node)])
    tree = cKDTree(vertices[triangles].mean(axis=1))
    distance, nearest = tree.query(nodes[tris].mean(axis=1))
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
    import igl

    squared, _, _ = igl.point_mesh_squared_distance(nodes[np.unique(tris)], vertices, triangles.astype(np.int64))
    surface_gap = np.sqrt(squared)
    info = {
        "mesher": "MMG level-set remeshing of the field's own grid - no surface",
        "edge_mm": edge,
        "grid_mm": spacing * stride,
        "hausd_mm": hausd,
        "background": {"cubes": int(cubes), "points": int(len(points)), "tets": int(len(all_tets))},
        "seconds": {
            "background": round(background_s, 1),
            "mmg": round(mmg_s, 1),
            "total": round(time.time() - started, 1),
        },
        "linear_nodes": int(len(nodes)),
        "nodes": int(len(nodes10)),
        "dof": int(3 * len(nodes10)),
        "tets": int(len(tets10)),
        "boundary_triangles": int(len(tris)),
        "boundary_from_design_mm": {
            "median": float(np.median(surface_gap)),
            "p99": float(np.percentile(surface_gap, 99)),
            "max": float(surface_gap.max()),
        },
        "quality": volume_quality(nodes, tets),
        "volume_mm3": float(np.abs(volume).sum() / 6.0),
    }
    (OUT / "tet10.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
