"""The gate's regular route, as agenticCAE meshed its 490 designs (``src/fastcae/mesh/surface.py`` in
the agenticCAE repository): gmsh triangulates the CAD's faces - carrying on past the few it cannot
parametrise - the triangles are welded at 0.5 mm, their short edges collapsed at 3 mm, the holes the
skipped faces leave closed by MeshFix, and gmsh fills the closed surface with tets. agenticCAE's own
weld, collapse and MeshFix run as they are, loaded from its repository; the two gmsh steps are its
own, held to the gate's size map (``sizes.npz``) - or, with ``GATE_REGULAR=agentic``, run as agenticCAE
ran them, sizes and all, so the other routes can be held to this mesh's own sizes
(``sizes_from_mesh.py``).

    python gate_regular.py     # BENCH_CASE picks the case folder (gate3reg); writes cgal_tets.npz, regular.json
"""

from __future__ import annotations

import importlib.util
import json
import os
import time

os.environ.setdefault("BENCH_CASE", "gate3reg")

import numpy as np  # noqa: E402
from common import OUT  # noqa: E402
from gate_gmsh import size_map  # noqa: E402
from gate_part import STEP  # noqa: E402

AGENTICCAE_SURFACE = r"C:\Work\agenticCAE\src\fastcae\mesh\surface.py"


def agenticcae():
    spec = importlib.util.spec_from_file_location("agenticcae_surface", AGENTICCAE_SURFACE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sized(gmsh, at) -> None:
    gmsh.model.mesh.setSizeCallback(lambda dim, tag, x, y, z, lc: at(x, y, z))
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)


def cad_surface(at) -> tuple[np.ndarray, np.ndarray, dict]:
    """agenticCAE's ``cad_surface``: gmsh triangulates the B-rep, not stopping at a face it cannot
    parametrise - with the size map for its sizes."""
    import gmsh

    t0 = time.perf_counter()
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.AbortOnError", 0)
        gmsh.option.setNumber("Geometry.Tolerance", 1e-3)
        gmsh.model.occ.importShapes(str(STEP))
        gmsh.model.occ.synchronize()
        sized(gmsh, at)
        try:
            gmsh.model.mesh.generate(2)
        except Exception:  # noqa: BLE001 - the faces gmsh could mesh are kept, as agenticCAE does
            pass
        tags, coords, _ = gmsh.model.mesh.getNodes()
        xyz = coords.reshape(-1, 3)
        row = {int(x): i for i, x in enumerate(tags)}
        tri, empty = [], 0
        for _, tag in gmsh.model.getEntities(2):
            types, _, nodes = gmsh.model.mesh.getElements(2, tag)
            got = False
            for kind, nn in zip(types, nodes):
                if kind == 2:
                    tri.append(np.array([row[int(x)] for x in nn]).reshape(-1, 3))
                    got = True
            empty += not got
        tris = np.vstack(tri)
    finally:
        gmsh.finalize()
    return xyz, tris, {"tris": int(len(tris)), "unparametrised_faces": int(empty),
                       "seconds": round(time.perf_counter() - t0, 2)}


def tetrahedralise(ag, verts, tris, at) -> tuple[np.ndarray, np.ndarray, dict]:
    """agenticCAE's ``tetrahedralise``: gmsh fills the closed surface - with the size map inside."""
    import gmsh

    stl = ag.write_stl(OUT / "_surface.stl", verts, tris)
    t0 = time.perf_counter()
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.AbortOnError", 0)
        gmsh.merge(str(stl))
        surfaces = [x[1] for x in gmsh.model.getEntities(2)]
        gmsh.model.geo.addVolume([gmsh.model.geo.addSurfaceLoop(surfaces)])
        gmsh.model.geo.synchronize()
        sized(gmsh, at)
        gmsh.option.setNumber("Mesh.AngleToleranceFacetOverlap", 0.01)
        gmsh.option.setNumber("Mesh.Optimize", 1)
        gmsh.model.mesh.generate(3)
        tags, coords, _ = gmsh.model.mesh.getNodes()
        points = coords.reshape(-1, 3)
        row = {int(x): i for i, x in enumerate(tags)}
        types, _, nodes = gmsh.model.mesh.getElements(3)
        blocks = [np.array([row[int(x)] for x in b]).reshape(-1, 4) for t, b in zip(types, nodes) if t == 4]
        if not blocks:
            raise RuntimeError("gmsh produced no tetrahedra from the repaired surface")
        tets = np.vstack(blocks)
    finally:
        gmsh.finalize()
        (OUT / "_surface.stl").unlink(missing_ok=True)
    used = np.unique(tets)
    remap = -np.ones(len(points), np.int64)
    remap[used] = np.arange(len(used))
    return points[used], remap[tets], {"nodes": int(len(used)), "tets": int(len(tets)),
                                       "seconds": round(time.perf_counter() - t0, 2)}


def main() -> None:
    ag = agenticcae()
    # ``GATE_REGULAR=agentic``: agenticCAE's sizes as well - its 20 mm most, 4 mm least, gmsh grading
    # the rest from the CAD's own faces and edges - its functions called as they are.
    agentic = os.environ.get("GATE_REGULAR") == "agentic"
    at = None if agentic else size_map()
    verts, tris, surface = ag.cad_surface(STEP, ag.SIZE_MM) if agentic else cad_surface(at)
    print("surface:", json.dumps(surface), flush=True)
    t0 = time.perf_counter()
    verts, tris, repaired = ag.repair(verts, tris)
    repaired["seconds"] = round(time.perf_counter() - t0, 2)
    print("repair:", json.dumps({k: v for k, v in repaired.items() if k != "patch_sites"}), flush=True)
    if agentic:
        nodes, tets, filled = ag.tetrahedralise(verts, tris, ag.SIZE_MM, OUT)
        (OUT / "_surface.stl").unlink(missing_ok=True)
    else:
        nodes, tets, filled = tetrahedralise(ag, verts, tris, at)
    print("tets:", json.dumps(filled), flush=True)
    np.savez_compressed(OUT / "cgal_tets.npz", nodes=nodes, tets=tets)
    info = {"mesher": "agenticCAE's route: gmsh on the CAD's faces, weld, collapse, MeshFix, gmsh tets",
            "sizes": "agenticCAE's own (20 mm most, 4 mm least)" if agentic else "sizes.npz",
            "surface": surface, "repair": repaired, "tets": filled,
            "seconds": surface["seconds"] + repaired["seconds"] + filled["seconds"]}
    (OUT / "regular.json").write_text(json.dumps(info, indent=1, default=float))


if __name__ == "__main__":
    main()
