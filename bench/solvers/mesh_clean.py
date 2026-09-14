"""The design meshed from its own field's surface, cleaned rather than decimated: the surface dual
contouring made from the field - millions of triangles no finer than the 3 mm grid holds - remeshed
into even triangles of a chosen size, finer where it curves, its sharp edges kept (MeshLab's
isotropic explicit remeshing); then repaired where it crosses itself (MeshFix: the crossing
triangles removed, the gap patched - dual contouring leaves a few thousand crossing faces where two
sheets pass closer than the grid); then filled with tets by TetGen, which keeps that surface as the
boundary. TET10 and labels as ``mesh_tet10.py`` makes them.

    python mesh_clean.py [edge_mm] [surface_mm] [tolerance_mm] [--keep-surface]
        # interior 20 mm, surface 10 mm, held within 0.5 mm of the design's surface; TetGen may
        # split the surface where quality asks, unless told to keep it
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np
from common import OUT, SEATS
from mesh_tet10 import boundary, midside, quadratic, volume_quality
from scipy.spatial import cKDTree


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    edge = float(args[0]) if len(args) > 0 else 20.0
    target = float(args[1]) if len(args) > 1 else 10.0
    tolerance = float(args[2]) if len(args) > 2 else 0.5
    keep_surface = "--keep-surface" in sys.argv
    import pymeshlab
    import tetgen

    started = time.time()
    surface = np.load(OUT / "surface.npz")
    setup = json.loads((OUT / "setup.json").read_text(encoding="utf-8"))
    vertices, triangles, face_id = surface["vertices"], surface["triangles"], surface["face_id"]
    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=vertices, face_matrix=triangles.astype(np.int32)))
    ms.meshing_isotropic_explicit_remeshing(
        iterations=6,
        adaptive=True,
        targetlen=pymeshlab.PureValue(target),
        featuredeg=30.0,
        checksurfdist=True,
        maxsurfdist=pymeshlab.PureValue(tolerance),
    )
    remesh_s = time.time() - started
    topology = ms.get_topological_measures()
    ms.compute_selection_by_self_intersections_per_face()
    crossing = int(ms.current_mesh().selected_face_number())
    clean = ms.current_mesh()
    sv, st = clean.vertex_matrix().astype(np.float64), clean.face_matrix().astype(np.int64)
    print(
        f"remeshed {len(triangles):,} -> {len(st):,} triangles in {remesh_s:.0f} s; boundary edges "
        f"{topology['boundary_edges']}, non-manifold edges {topology['non_two_manifold_edges']}, "
        f"self-intersecting faces {crossing}",
        flush=True,
    )
    import pymeshfix

    t0 = time.time()
    fixer = pymeshfix.MeshFix(sv, st.astype(np.int32))
    fixer.repair()
    fixed_v, fixed_t = np.asarray(fixer.points, np.float64), np.asarray(fixer.faces, np.int64)
    repair_s = time.time() - t0
    moved, _ = cKDTree(vertices).query(fixed_v)
    ms2 = pymeshlab.MeshSet()
    ms2.add_mesh(pymeshlab.Mesh(vertex_matrix=fixed_v, face_matrix=fixed_t.astype(np.int32)))
    ms2.compute_selection_by_self_intersections_per_face()
    still = int(ms2.current_mesh().selected_face_number())
    print(
        f"repaired in {repair_s:.1f} s: {len(st):,} -> {len(fixed_t):,} triangles, {still} still crossing; "
        f"its vertices within {moved.max():.2f} mm of the design's surface",
        flush=True,
    )
    sv, st = fixed_v, fixed_t
    np.savez_compressed(OUT / "clean_surface.npz", vertices=sv, triangles=st)

    t0 = time.time()
    if "--gmsh" in sys.argv:
        nodes, tets = gmsh_fill(sv, st, edge)
    else:
        maxvolume = edge**3 / (6.0 * np.sqrt(2.0))  # a regular tet with edges this long
        tet = tetgen.TetGen(sv, st.astype(np.int32))
        made = tet.tetrahedralize(
            order=1,
            quality=True,
            minratio=1.5,
            mindihedral=12.0,
            maxvolume=maxvolume,
            nobisect=keep_surface,
            verbose=0,
        )
        nodes, tets = made[0], made[1]
    tet_s = time.time() - t0
    nodes, tets = np.asarray(nodes, np.float64), np.asarray(tets, np.int64)
    p = nodes[tets]
    volume = np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))
    tets[volume < 0] = tets[volume < 0][:, [0, 2, 1, 3]]
    print(f"TetGen: {len(nodes):,} nodes, {len(tets):,} tets in {tet_s:.1f} s", flush=True)

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
    info = {
        "mesher": "MeshLab isotropic remeshing of the field's surface, then TetGen",
        "edge_mm": edge,
        "surface_mm": target,
        "surface_tolerance_mm": tolerance,
        "surface_kept": keep_surface,
        "surface_triangles": {"design": int(len(triangles)), "remeshed": int(len(st))},
        "surface_checks": {
            "boundary_edges": int(topology["boundary_edges"]),
            "non_manifold_edges": int(topology["non_two_manifold_edges"]),
            "self_intersecting_faces": crossing,
            "after_repair": still,
            "repaired_within_mm": float(moved.max()),
        },
        "seconds": {
            "remesh": round(remesh_s, 1),
            "repair": round(repair_s, 1),
            "tetgen": round(tet_s, 1),
            "total": round(time.time() - started, 1),
        },
        "linear_nodes": int(len(nodes)),
        "nodes": int(len(nodes10)),
        "dof": int(3 * len(nodes10)),
        "tets": int(len(tets10)),
        "boundary_triangles": int(len(tris)),
        "boundary_gap_mm": {"median": float(np.median(distance)), "max": float(distance.max())},
        "quality": volume_quality(nodes, tets),
        "volume_mm3": float(np.abs(volume).sum() / 6.0),
    }
    (OUT / "tet10.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(json.dumps(info, indent=1))


def gmsh_fill(vertices: np.ndarray, triangles: np.ndarray, edge: float) -> tuple[np.ndarray, np.ndarray]:
    """Tets inside the given closed surface by gmsh's parallel Delaunay mesher (HXT), the surface
    kept exactly as given - a discrete surface, nothing re-parametrised - and the result optimised."""
    import gmsh

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.NumThreads", 16)
        gmsh.logger.start()
        gmsh.model.add("design")
        surface = gmsh.model.addDiscreteEntity(2)
        tags = np.arange(1, len(vertices) + 1)
        gmsh.model.mesh.addNodes(2, surface, tags, vertices.ravel())
        gmsh.model.mesh.addElementsByType(surface, 2, [], (triangles + 1).ravel())
        loop = gmsh.model.geo.addSurfaceLoop([surface])
        gmsh.model.geo.addVolume([loop])
        gmsh.model.geo.synchronize()
        gmsh.option.setNumber("Mesh.MeshSizeMax", edge)
        gmsh.option.setNumber("Mesh.Algorithm3D", 10)
        gmsh.option.setNumber("Mesh.Optimize", 1)
        gmsh.model.mesh.generate(3)
        node_tags, coords, _ = gmsh.model.mesh.getNodes()
        types = gmsh.model.mesh.getElementTypes(3)
        if 4 not in types:
            raise RuntimeError("gmsh made no tets: " + " | ".join(gmsh.logger.get()[-12:]))
        _, element_nodes = gmsh.model.mesh.getElementsByType(4)
    finally:
        gmsh.finalize()
    index = np.zeros(int(node_tags.max()) + 1, np.int64)
    index[node_tags.astype(np.int64)] = np.arange(len(node_tags))
    tets = index[np.asarray(element_nodes, np.int64).reshape(-1, 4)]
    nodes = coords.reshape(-1, 3)
    used = np.unique(tets)
    remap = np.full(len(nodes), -1, np.int64)
    remap[used] = np.arange(len(used))
    return nodes[used], remap[tets]


if __name__ == "__main__":
    main()
