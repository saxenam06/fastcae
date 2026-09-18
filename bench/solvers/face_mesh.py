"""A B-rep meshed face by face, as agenticCAE meshed its designs - gmsh on every CAD face (20 mm most,
4 mm least), weld, collapse, MeshFix, gmsh tets - with two changes:

- a face gmsh cannot parametrise ("impossible to mesh periodic surface"; 4 of the baseline's 1,753)
  is meshed in its own unrolled (u, v) plane, scaled to millimetres, on the rim nodes its neighbours
  already use, and its inner nodes are put back on the CAD surface. agenticCAE left those faces
  empty and MeshFix lidded them flat - over a hole, a lid.
- every curved edge is divided at least `per_turn` times a full turn at its tightest bend (never
  below 1 mm), so a hole's rim is round rather than a hexagon; the faces grade out from it.

Study code, as the rest of bench/: the deck script uses it for the baseline.
"""

from __future__ import annotations

import contextlib
import importlib.util
import math
import time
from pathlib import Path

import numpy as np

AGENTICCAE_SURFACE = r"C:\Work\agenticCAE\src\fastcae\mesh\surface.py"
SIZE_MM, SMALLEST_MM = 20.0, 4.0
PER_TURN = 12
NEAR_MM = 0.05  # rim nodes closer than this are one node in the unrolled plane; the weld joins them


def agenticcae():
    spec = importlib.util.spec_from_file_location("agenticcae_surface", AGENTICCAE_SURFACE)
    ag = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ag)
    return ag


def _start(gmsh, brep: Path, size: float, smallest: float) -> None:
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


def _generate(gmsh) -> list[int]:
    """Mesh the faces; the ones left without a triangle."""
    with contextlib.suppress(Exception):  # gmsh raises on the faces it skips; the rest are meshed
        gmsh.model.mesh.generate(2)
    return [t for _, t in gmsh.model.getEntities(2) if 2 not in list(gmsh.model.mesh.getElements(2, t)[0])]


def _curve_sizes(gmsh, per_turn: float, size: float) -> dict[int, float]:
    sizes = {}
    for _, c in gmsh.model.getEntities(1):
        lo, hi = gmsh.model.getParametrizationBounds(1, c)
        bend = float(np.max(gmsh.model.getCurvature(1, c, np.linspace(lo[0], hi[0], 9))))
        if bend > 1e-6:
            sizes[c] = min(size, max(1.0, 2 * math.pi / (per_turn * bend)))
    return sizes


def _loops(gmsh, face: int) -> list[list[int]]:
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


def _unrolled(gmsh, face: int, xyz: dict[int, np.ndarray]):
    """Each rim loop in the face's (u, v) plane, scaled to millimetres."""
    out = []
    for loop in _loops(gmsh, face):
        p = np.array([xyz[t] for t in loop])
        uv = np.asarray(gmsh.model.getParametrization(2, face, p.ravel())).reshape(-1, 2)
        d = np.asarray(gmsh.model.getDerivative(2, face, uv.ravel())).reshape(-1, 6)
        scale = np.array([np.median(np.linalg.norm(d[:, :3], axis=1)), np.median(np.linalg.norm(d[:, 3:], axis=1))])
        keep = [0]
        for i in range(1, len(loop)):
            if np.linalg.norm(p[i] - p[keep[-1]]) > NEAR_MM:
                keep.append(i)
        if np.linalg.norm(p[keep[-1]] - p[keep[0]]) <= NEAR_MM:
            keep.pop()
        out.append(([loop[i] for i in keep], uv[keep], scale))
    return out


def _plane_mesh(gmsh, face: int, rims):
    """gmsh meshes the unrolled polygon; its inner nodes go back onto the CAD face."""
    scale = rims[0][2]
    polys = [uv * scale for _, uv, _ in rims]
    area = [0.5 * np.sum(q[:, 0] * np.roll(q[:, 1], -1) - np.roll(q[:, 0], -1) * q[:, 1]) for q in polys]
    gmsh.model.add(f"plane{face}")
    origin, curve_loops = {}, []
    for k in np.argsort(-np.abs(area)):  # the outer loop first, holes after
        q, tags = polys[k], rims[k][0]
        seg = np.linalg.norm(q - np.roll(q, 1, axis=0), axis=1)
        points = []
        for (x, y), t, h in zip(q, tags, 0.5 * (seg + np.roll(seg, -1)), strict=True):
            pt = gmsh.model.geo.addPoint(x, y, 0, max(h, 0.1))
            origin[pt] = t
            points.append(pt)
        lines = [gmsh.model.geo.addLine(points[i], points[(i + 1) % len(points)]) for i in range(len(points))]
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
    placed = {}
    if inside:
        uv = np.array([coords[row[n], :2] for n in inside]) / scale
        placed = dict(zip(inside, np.asarray(gmsh.model.getValue(2, face, uv.ravel())).reshape(-1, 3), strict=True))
    return tris, rim, placed


def surface(brep: Path, size: float = SIZE_MM, smallest: float = SMALLEST_MM, per_turn: float = PER_TURN):
    """Every CAD face triangulated, none left empty. Returns (vertices, triangles, stats)."""
    import gmsh

    t0 = time.time()
    _start(gmsh, brep, size, smallest)
    empty = _generate(gmsh)
    gmsh.finalize()
    _start(gmsh, brep, size, smallest)
    try:
        sizes = _curve_sizes(gmsh, per_turn, size) if per_turn else {}
        if sizes:
            gmsh.model.mesh.setSizeCallback(
                lambda dim, tag, x, y, z, lc: min(lc, sizes.get(tag, lc)) if dim == 1 else lc
            )
        rim_curves = {abs(c) for f in empty for _, c in gmsh.model.getBoundary([(2, f)], oriented=False)}
        # Rims as gmsh spaced them, finer only if the unrolled rim would cross itself.
        for h in (None, smallest, smallest / 2, smallest / 4):
            if h:
                for c in rim_curves:
                    gmsh.model.mesh.setTransfiniteCurve(c, max(3, math.ceil(gmsh.model.occ.getMass(1, c) / h) + 1))
            still = _generate(gmsh)
            ntags, coords, _ = gmsh.model.mesh.getNodes()
            xyz = dict(zip((int(t) for t in ntags), coords.reshape(-1, 3), strict=True))
            rims = {f: _unrolled(gmsh, f, xyz) for f in still}
            if all(_simple(uv * sc) for f in rims for _, uv, sc in rims[f]):
                break
        tris = []
        for _, t in gmsh.model.getEntities(2):
            types, _, nodes = gmsh.model.mesh.getElements(2, t)
            tris += [np.asarray(nn, np.int64).reshape(-1, 3) for ty, nn in zip(types, nodes, strict=True) if ty == 2]
        faces = len(gmsh.model.getEntities(2))
        fresh = max(xyz) + 1
        for f in still:
            ft, rim, placed = _plane_mesh(gmsh, f, rims[f])
            new = {}
            for n, p in placed.items():
                new[n], xyz[fresh] = fresh, p
                fresh += 1
            tris.append(np.vectorize(lambda n, rim=rim, new=new: rim.get(int(n), new.get(int(n))))(ft))
    finally:
        gmsh.finalize()
    tris = np.vstack(tris)
    ids = np.unique(tris)
    row = {int(t): i for i, t in enumerate(ids)}
    vertices = np.array([xyz[int(t)] for t in ids])
    return vertices, np.vectorize(row.get)(tris), {
        "faces": faces, "unrolled_faces": still, "curves_sized": len(sizes), "seconds": round(time.time() - t0, 1)
    }


def mesh(brep: Path, work: Path, size: float = SIZE_MM, smallest: float = SMALLEST_MM, per_turn: float = PER_TURN):
    """The part as corner nodes and tets. Returns (nodes, tets, stats); stats say what was patched."""
    ag = agenticcae()
    vertices, triangles, made = surface(brep, size, smallest, per_turn)
    vertices, triangles, repaired = ag.repair(vertices, triangles)
    nodes, tets, filled = ag.tetrahedralise(vertices, triangles, size, work)
    (Path(work) / "_surface.stl").unlink(missing_ok=True)
    return np.asarray(nodes), np.asarray(tets), {**made, "patched_holes": repaired["patched_holes"], **filled}
