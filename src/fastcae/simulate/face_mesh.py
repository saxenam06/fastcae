"""A part's CAD meshed face by face - the recipe the baseline's deck mesh was made with, and every
design's after it.

gmsh triangulates every face of the B-rep on its own, elements 20 mm at most and 4 mm at least, the
sizes left to grade between; agenticCAE's own repair and tetrahedraliser finish it, as agenticCAE
meshed its designs: nodes closer than half a millimetre welded, edges shorter than 3 mm collapsed,
MeshFix, and gmsh filling the closed surface with tetrahedra. Two things are added to that route:

- **A face gmsh cannot parametrise** ("impossible to mesh periodic surface"; 4 of the baseline's
  1,753) is meshed in its own unrolled (u, v) plane, scaled to millimetres, on the rim nodes its
  neighbours already use, and its inner nodes are put back on the CAD surface. agenticCAE left those
  faces empty and MeshFix lidded them flat - over a hole, a lid.
- **Every curved edge** is divided at least 12 times a full turn at its tightest bend (never below
  1 mm), so a hole's rim is round rather than a hexagon; the faces grade out from it.

A face whose own triangles fold back over one another - a narrow land a fuse leaves where a rib
meets a wall, its rim spaced wider than it is across - is meshed again on a finer rim, and if it
still folds, by gmsh's other surface algorithm (``refolded_faces``). A fold left after the repair -
two triangles lying on each other, across two faces - is collapsed: the edge they share becomes one
node, the flap goes and its neighbours close up (``folds_collapsed``). Either way the fold must go:
gmsh fills nothing at all while two facets overlap.

A face left without triangles even so leaves a hole that MeshFix closes flat. :func:`mesh` counts
those holes (``patched_holes``) and says where they are, so a caller can refuse such a mesh.

agenticCAE's module is read from its own repository - the file ``FASTCAE_AGENTICCAE_SURFACE`` names,
else :data:`AGENTICCAE_SURFACE` - and needs gmsh and pymeshfix installed beside this package.
"""

from __future__ import annotations

import contextlib
import importlib.util
import math
import os
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

AGENTICCAE_SURFACE = r"C:\Work\agenticCAE\src\fastcae\mesh\surface.py"
SIZE_MM, SMALLEST_MM = 25.0, 4.0
PER_TURN = 12
NEAR_MM = 0.05  # rim nodes closer than this are one node in the unrolled plane; the weld joins them

# One loop of a face's rim in the face's unrolled plane: gmsh's node tags round it, their (u, v),
# and the scale that turns (u, v) into millimetres.
Rim = tuple[list[int], np.ndarray, np.ndarray]


def agenticcae() -> ModuleType:
    """agenticCAE's surface module - its repair and its tetrahedraliser - from its repository."""
    path = Path(os.environ.get("FASTCAE_AGENTICCAE_SURFACE", AGENTICCAE_SURFACE))
    if not path.is_file():
        raise FileNotFoundError(
            f"agenticCAE's surface mesher is not at {path}; name it in FASTCAE_AGENTICCAE_SURFACE"
        )
    spec = importlib.util.spec_from_file_location("agenticcae_surface", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"{path} cannot be read as a Python module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _start(gmsh: ModuleType, brep: Path, size: float, smallest: float) -> None:
    """The B-rep in a fresh gmsh session: element sizes bounded, none taken from curvature."""
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.option.setNumber("General.AbortOnError", 0)
    gmsh.option.setNumber("Geometry.Tolerance", 1e-3)
    gmsh.model.add("cad")
    gmsh.model.occ.importShapes(str(brep))
    gmsh.model.occ.synchronize()
    gmsh.option.setNumber("Mesh.MeshSizeMax", size)
    gmsh.option.setNumber("Mesh.MeshSizeMin", smallest)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)


def _generate(gmsh: ModuleType) -> list[int]:
    """Mesh the faces; the ones left without a triangle."""
    with contextlib.suppress(Exception):  # gmsh raises on the faces it skips; the rest are meshed
        gmsh.model.mesh.generate(2)
    return [
        t
        for _, t in gmsh.model.getEntities(2)
        if 2 not in list(gmsh.model.mesh.getElements(2, t)[0])
    ]


def _curve_sizes(gmsh: ModuleType, per_turn: float, size: float) -> dict[int, float]:
    """Each curved edge's element size: a full turn at its tightest bend over ``per_turn``, never
    below 1 mm nor above ``size``."""
    sizes = {}
    for _, c in gmsh.model.getEntities(1):
        lo, hi = gmsh.model.getParametrizationBounds(1, c)
        bend = float(np.max(gmsh.model.getCurvature(1, c, np.linspace(lo[0], hi[0], 9))))
        if bend > 1e-6:
            sizes[c] = min(size, max(1.0, 2 * math.pi / (per_turn * bend)))
    return sizes


FOLD_DOT = -0.5
"""Two neighbouring triangles of one face whose normals point further apart than this, folded."""
FOLD_ROUNDS = 3
"""How many times a folded face is meshed again, each time finer."""
FOLD_FLAT = -0.999
"""Two triangles whose normals are this far past opposite lie on each other."""
COLLAPSE_ROUNDS = 4
"""How many times the folds left after the repair are collapsed away."""


def _folded(gmsh: ModuleType, skip: list[int]) -> list[int]:
    """The faces (not in ``skip``) whose own triangles fold: two neighbours facing apart."""
    ntags, coords, _ = gmsh.model.mesh.getNodes()
    order = np.argsort(ntags)
    tags, points = np.asarray(ntags)[order], np.asarray(coords).reshape(-1, 3)[order]
    out = []
    for _, f in gmsh.model.getEntities(2):
        if f in skip:
            continue
        types, _, nodes = gmsh.model.mesh.getElements(2, f)
        tri = [
            np.asarray(n, np.int64).reshape(-1, 3)
            for t, n in zip(types, nodes, strict=True)
            if t == 2
        ]
        if not tri:
            continue
        tri = np.vstack(tri)
        p = points[np.searchsorted(tags, tri)]
        n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1), 1e-30)[:, None]
        e = np.sort(np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]]), axis=1)
        owner = np.tile(np.arange(len(tri)), 3)
        o = np.lexsort((e[:, 1], e[:, 0]))
        e, owner = e[o], owner[o]
        pair = np.flatnonzero(np.all(e[1:] == e[:-1], axis=1))
        if (
            len(pair)
            and float(np.min(np.einsum("ij,ij->i", n[owner[pair]], n[owner[pair + 1]]))) < FOLD_DOT
        ):
            out.append(f)
    return out


NARROW = 3.0
"""A narrow face's rim is divided no coarser than this many times the face's width..."""
NARROW_LEAST_MM = 8.0
"""...nor finer than this: a strip's triangles stay stout without the whole part growing finer."""


def _narrow_sizes(gmsh: ModuleType, size: float, smallest: float) -> dict[int, float]:
    """The rim of every face narrower than its elements - a fillet strip, a land - divided to its
    width, so it is not spanned by needles: width as twice the area over the perimeter, which is a
    strip's own width."""
    sizes: dict[int, float] = {}
    for _, f in gmsh.model.getEntities(2):
        rim = [abs(c) for _, c in gmsh.model.getBoundary([(2, f)], oriented=False)]
        perimeter = sum(gmsh.model.occ.getMass(1, c) for c in rim)
        if perimeter <= 0:
            continue
        width = 2.0 * gmsh.model.occ.getMass(2, f) / perimeter
        h = max(smallest, NARROW_LEAST_MM, NARROW * width)
        if h < size:
            for c in rim:
                sizes[c] = min(sizes.get(c, size), h)
    return sizes


def _folded_edges(vertices: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    """The edges whose two triangles lie on each other, (n, 2) node numbers."""
    n = np.cross(
        vertices[triangles[:, 1]] - vertices[triangles[:, 0]],
        vertices[triangles[:, 2]] - vertices[triangles[:, 0]],
    )
    n /= np.maximum(np.linalg.norm(n, axis=1), 1e-30)[:, None]
    e = np.sort(
        np.concatenate([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]]), axis=1
    )
    owner = np.tile(np.arange(len(triangles)), 3)
    order = np.lexsort((e[:, 1], e[:, 0]))
    e, owner = e[order], owner[order]
    same = np.flatnonzero(np.all(e[1:] == e[:-1], axis=1))
    dots = np.einsum("ij,ij->i", n[owner[same]], n[owner[same + 1]])
    return e[same][dots < FOLD_FLAT]


def _collapse(
    vertices: np.ndarray, triangles: np.ndarray, edges: np.ndarray
) -> tuple[np.ndarray, np.ndarray, int]:
    """Each edge's two nodes made one, at their middle; the triangles left without three nodes
    go."""
    into = np.arange(len(vertices))
    for a, b in edges:
        a, b = int(into[a]), int(into[b])
        if a == b:
            continue
        vertices[a] = 0.5 * (vertices[a] + vertices[b])
        into[into == b] = a
    moved = into[triangles]
    keep = (
        (moved[:, 0] != moved[:, 1]) & (moved[:, 1] != moved[:, 2]) & (moved[:, 2] != moved[:, 0])
    )
    return vertices, moved[keep], int((~keep).sum())


def _loops(gmsh: ModuleType, face: int) -> list[list[int]]:
    """The face's rim as closed chains of node tags, from gmsh's own curve mesh."""
    adj: dict[int, list[int]] = {}
    for _, c in gmsh.model.getBoundary([(2, face)], oriented=False):
        types, _, nodes = gmsh.model.mesh.getElements(1, abs(c))
        for t, n in zip(types, nodes, strict=True):
            if t == 1:
                for a, b in np.asarray(n, np.int64).reshape(-1, 2):
                    adj.setdefault(int(a), []).append(int(b))
                    adj.setdefault(int(b), []).append(int(a))
    left, loops = set(adj), []
    while left:
        start = min(left)
        loop, prev, cur = [start], None, start
        left.discard(start)
        while True:
            step = [x for x in adj[cur] if x != prev and x in left]
            if not step:
                break
            prev, cur = cur, step[0]
            loop.append(cur)
            left.discard(cur)
        loops.append(loop)
    return loops


def _simple(poly: np.ndarray) -> bool:
    """No two non-adjacent edges of the closed polygon cross."""
    a, b = poly, np.roll(poly, -1, axis=0)
    n = len(poly)
    for i in range(n):
        p, r = a[i], b[i] - a[i]
        s = b - a
        den = r[0] * s[:, 1] - r[1] * s[:, 0]
        with np.errstate(divide="ignore", invalid="ignore"):
            t = ((a[:, 0] - p[0]) * s[:, 1] - (a[:, 1] - p[1]) * s[:, 0]) / den
            u = ((a[:, 0] - p[0]) * r[1] - (a[:, 1] - p[1]) * r[0]) / den
        hit = (np.abs(den) > 1e-12) & (t > 1e-9) & (t < 1 - 1e-9) & (u > 1e-9) & (u < 1 - 1e-9)
        hit[[i, (i - 1) % n, (i + 1) % n]] = False
        if hit.any():
            return False
    return True


def _unrolled(gmsh: ModuleType, face: int, xyz: dict[int, np.ndarray]) -> list[Rim]:
    """Each rim loop in the face's (u, v) plane, scaled to millimetres."""
    out = []
    for loop in _loops(gmsh, face):
        p = np.array([xyz[t] for t in loop])
        uv = np.asarray(gmsh.model.getParametrization(2, face, p.ravel())).reshape(-1, 2)
        d = np.asarray(gmsh.model.getDerivative(2, face, uv.ravel())).reshape(-1, 6)
        scale = np.array(
            [
                np.median(np.linalg.norm(d[:, :3], axis=1)),
                np.median(np.linalg.norm(d[:, 3:], axis=1)),
            ]
        )
        keep = [0]
        for i in range(1, len(loop)):
            if np.linalg.norm(p[i] - p[keep[-1]]) > NEAR_MM:
                keep.append(i)
        if np.linalg.norm(p[keep[-1]] - p[keep[0]]) <= NEAR_MM:
            keep.pop()
        out.append(([loop[i] for i in keep], uv[keep], scale))
    return out


def _plane_mesh(
    gmsh: ModuleType, face: int, rims: list[Rim]
) -> tuple[np.ndarray, dict[int, int], dict[int, np.ndarray]]:
    """gmsh meshes the unrolled polygon; its inner nodes go back onto the CAD face. Returns the
    triangles in the plane's node tags, the rim's tags in the CAD mesh, and each inner node's
    place on the face."""
    scale = rims[0][2]
    polys = [uv * scale for _, uv, _ in rims]
    area = [
        0.5 * np.sum(q[:, 0] * np.roll(q[:, 1], -1) - np.roll(q[:, 0], -1) * q[:, 1]) for q in polys
    ]
    gmsh.model.add(f"plane{face}")
    origin: dict[int, int] = {}
    curve_loops: list[int] = []
    for k in np.argsort(-np.abs(area)):  # the outer loop first, holes after
        q, tags = polys[k], rims[k][0]
        seg = np.linalg.norm(q - np.roll(q, 1, axis=0), axis=1)
        points = []
        for (x, y), t, h in zip(q, tags, 0.5 * (seg + np.roll(seg, -1)), strict=True):
            pt = gmsh.model.geo.addPoint(x, y, 0, max(h, 0.1))
            origin[pt] = t
            points.append(pt)
        lines = [
            gmsh.model.geo.addLine(points[i], points[(i + 1) % len(points)])
            for i in range(len(points))
        ]
        curve_loops.append(gmsh.model.geo.addCurveLoop(lines))
        for line in lines:
            gmsh.model.geo.mesh.setTransfiniteCurve(line, 2)
    gmsh.model.geo.addPlaneSurface(curve_loops)
    gmsh.model.geo.synchronize()
    gmsh.model.mesh.generate(2)
    rim = {int(gmsh.model.mesh.getNodes(0, pt)[0][0]): t for pt, t in origin.items()}
    ntags, coords, _ = gmsh.model.mesh.getNodes()
    row = {int(n): i for i, n in enumerate(ntags)}
    coords = coords.reshape(-1, 3)
    types, _, nodes = gmsh.model.mesh.getElements(2)
    tris = np.asarray(nodes[list(types).index(2)], np.int64).reshape(-1, 3)
    gmsh.model.remove()
    gmsh.model.setCurrent("cad")
    inside = [int(n) for n in ntags if int(n) not in rim]
    placed: dict[int, np.ndarray] = {}
    if inside:
        uv = np.array([coords[row[n], :2] for n in inside]) / scale
        on_face = np.asarray(gmsh.model.getValue(2, face, uv.ravel())).reshape(-1, 3)
        placed = dict(zip(inside, on_face, strict=True))
    return tris, rim, placed


def surface(
    brep: Path, size: float = SIZE_MM, smallest: float = SMALLEST_MM, per_turn: float = PER_TURN
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Every CAD face triangulated, none left empty. Returns (vertices, triangles, stats)."""
    import gmsh

    t0 = time.time()
    _start(gmsh, brep, size, smallest)
    empty = _generate(gmsh)
    gmsh.finalize()
    _start(gmsh, brep, size, smallest)
    try:
        sizes = _curve_sizes(gmsh, per_turn, size) if per_turn else {}
        for c, h in _narrow_sizes(gmsh, size, smallest).items():
            sizes[c] = min(sizes.get(c, size), h)
        if sizes:
            gmsh.model.mesh.setSizeCallback(
                lambda dim, tag, x, y, z, lc: min(lc, sizes.get(tag, lc)) if dim == 1 else lc
            )
        rim_curves = {
            abs(c) for f in empty for _, c in gmsh.model.getBoundary([(2, f)], oriented=False)
        }
        # Rims as gmsh spaced them, finer only if the unrolled rim would cross itself.
        for h in (None, smallest, smallest / 2, smallest / 4):
            if h:
                for c in rim_curves:
                    divisions = max(3, math.ceil(gmsh.model.occ.getMass(1, c) / h) + 1)
                    gmsh.model.mesh.setTransfiniteCurve(c, divisions)
            still = _generate(gmsh)
            ntags, coords, _ = gmsh.model.mesh.getNodes()
            xyz = dict(zip((int(t) for t in ntags), coords.reshape(-1, 3), strict=True))
            rims = {f: _unrolled(gmsh, f, xyz) for f in still}
            if all(_simple(uv * sc) for f in rims for _, uv, sc in rims[f]):
                break
        # Faces whose own triangles fold: their rims finer each round, then the other algorithm.
        refolded: list[int] = []
        for round_ in range(FOLD_ROUNDS):
            folds = _folded(gmsh, still)
            if not folds:
                break
            refolded = sorted(set(refolded) | set(folds))
            for f in folds:
                rim = [abs(c) for _, c in gmsh.model.getBoundary([(2, f)], oriented=False)]
                perimeter = sum(gmsh.model.occ.getMass(1, c) for c in rim)
                width = 2.0 * gmsh.model.occ.getMass(2, f) / max(perimeter, 1e-9)
                h = max(0.25, min(smallest, width) / 2 ** (round_ + 1))
                for c in rim:
                    divisions = max(3, min(2000, math.ceil(gmsh.model.occ.getMass(1, c) / h) + 1))
                    gmsh.model.mesh.setTransfiniteCurve(c, divisions)
                if round_ > 0:
                    gmsh.model.mesh.setAlgorithm(2, f, 1)  # MeshAdapt
            still = _generate(gmsh)
            ntags, coords, _ = gmsh.model.mesh.getNodes()
            xyz = dict(zip((int(t) for t in ntags), coords.reshape(-1, 3), strict=True))
            rims = {f: _unrolled(gmsh, f, xyz) for f in still}
        tris: list[np.ndarray] = []
        for _, t in gmsh.model.getEntities(2):
            types, _, nodes = gmsh.model.mesh.getElements(2, t)
            tris += [
                np.asarray(nn, np.int64).reshape(-1, 3)
                for ty, nn in zip(types, nodes, strict=True)
                if ty == 2
            ]
        faces = len(gmsh.model.getEntities(2))
        fresh = max(xyz) + 1
        for f in still:
            ft, rim, placed = _plane_mesh(gmsh, f, rims[f])
            new = {}
            for n, p in placed.items():
                new[n], xyz[fresh] = fresh, p
                fresh += 1
            tris.append(
                np.vectorize(lambda n, rim=rim, new=new: rim.get(int(n), new.get(int(n))))(ft)
            )
    finally:
        gmsh.finalize()
    stacked = np.vstack(tris)
    ids = np.unique(stacked)
    row = {int(t): i for i, t in enumerate(ids)}
    vertices = np.array([xyz[int(t)] for t in ids])
    return (
        vertices,
        np.vectorize(row.get)(stacked),
        {
            "faces": faces,
            "unrolled_faces": still,
            "refolded_faces": refolded,
            "curves_sized": len(sizes),
            "seconds": round(time.time() - t0, 1),
        },
    )


def mesh(
    brep: Path,
    work: Path,
    size: float = SIZE_MM,
    smallest: float = SMALLEST_MM,
    per_turn: float = PER_TURN,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """The part as corner nodes and linear tets. Returns (nodes, tets, stats); the stats say what
    was patched - ``patched_holes`` the holes MeshFix closed flat, ``patch_sites`` where the widest
    of them are - and how long each step took."""
    missing = [name for name in ("gmsh", "pymeshfix") if importlib.util.find_spec(name) is None]
    if missing:
        raise ImportError(
            f"the face-by-face mesher needs {' and '.join(missing)} installed beside fastcae "
            "(gmsh 4.15.2 and pymeshfix 0.18.1 made the baseline's deck mesh)"
        )
    ag = agenticcae()
    t0 = time.time()
    vertices, triangles, made = surface(brep, size, smallest, per_turn)
    t1 = time.time()
    vertices, triangles, repaired = ag.repair(vertices, triangles)
    # MeshFix can hand the surface back turned inside out when it mends a defect; the volume mesher
    # then finds nothing inside it. Its enclosed volume says which way it faces.
    a, b, c = (vertices[triangles[:, i]] for i in range(3))
    inside_out = float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) < 0.0
    if inside_out:
        triangles = triangles[:, ::-1]
    collapsed = 0
    for _ in range(COLLAPSE_ROUNDS):
        edges = _folded_edges(vertices, triangles)
        if not len(edges):
            break
        vertices, triangles, gone = _collapse(vertices, triangles, edges)
        collapsed += gone
    repaired = {**repaired, "turned_outward": inside_out, "folds_collapsed": collapsed}
    t2 = time.time()
    nodes, tets, filled = ag.tetrahedralise(vertices, triangles, size, work)
    (Path(work) / "_surface.stl").unlink(missing_ok=True)
    return (
        np.asarray(nodes),
        np.asarray(tets),
        {
            **made,
            "patched_holes": repaired["patched_holes"],
            "turned_outward": repaired["turned_outward"],
            "folds_collapsed": repaired["folds_collapsed"],
            "patch_sites": repaired["patch_sites"],
            **filled,
            "surface_s": round(t1 - t0, 1),
            "repair_s": round(t2 - t1, 1),
            "tets_s": round(time.time() - t2, 1),
        },
    )


def _plain(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return str(value)


if __name__ == "__main__":
    # A CAD meshed in a process of its own, so whoever waits on it can stop it:
    # ``python -m fastcae.simulate.face_mesh <brep> <work>`` writes the nodes and tets to
    # ``face_mesh.npz`` and the stats to ``face_mesh.json``, both in ``work``.
    import json
    import sys

    brep_path, work_dir = Path(sys.argv[1]), Path(sys.argv[2])
    work_dir.mkdir(parents=True, exist_ok=True)
    found_nodes, found_tets, found_info = mesh(brep_path, work_dir)
    np.savez(work_dir / "face_mesh.npz", nodes=found_nodes, tets=found_tets)
    (work_dir / "face_mesh.json").write_text(
        json.dumps(found_info, default=_plain), encoding="utf-8"
    )
