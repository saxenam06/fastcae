"""Tetrahedra from CGAL's mesher in WSL - on a design's distance field, or on a closed triangulated
surface - held to an element-size map and made to follow edge lines, then finished as TET10.

**Sizes** come from a mesh the engineer already trusts: :func:`sizes_from_mesh` reads the mean tet
edge off it at every point of a grid, so another mesh of the same part - or of a design grown from
it - can be held to the same sizes point by point.

**Lines** are the edges of the CAD faces a load goes in through: :func:`face_edges` follows each
boundary loop of a set of faces on the CAD's own triangulation, so those faces come out exactly
where
a grid alone would round them. Vertices along them are kept about 8 mm apart: at the element size a
line keeps other vertices off whatever small runs beside it, and much closer makes the faces dense.
"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .. import wsl
from .fem import EDGES, FEMesh, oriented, quadratic

ENV = "fieldmesh"
SCRIPT = Path(__file__).with_name("wsl_mesher.py")


class MeshFailed(RuntimeError):
    pass


@dataclass
class SizeGrid:
    """An element edge length wanted at every point of a grid."""

    size: np.ndarray
    origin: np.ndarray
    spacing: float


def sizes_from_mesh(
    nodes: np.ndarray,
    tets: np.ndarray,
    origin: np.ndarray,
    shape: tuple[int, int, int],
    spacing: float,
    stride: int = 2,
    nearest: int = 4,
) -> SizeGrid:
    """The mean edge of the ``nearest`` tets round each point of a grid ``stride`` times coarser
    than
    the one given."""
    from scipy.spatial import cKDTree

    p = nodes[tets[:, :4]]
    edge = np.mean([np.linalg.norm(p[:, a] - p[:, b], axis=1) for a, b in EDGES], axis=0)
    coarse = -(-np.asarray(shape) // stride)
    step = stride * spacing
    axes = [np.arange(n) for n in coarse]
    grid = origin + np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3) * step
    _, near = cKDTree(p.mean(axis=1)).query(grid, k=nearest)
    size = edge[near].mean(axis=1).reshape(tuple(int(n) for n in coarse)).astype(np.float32)
    return SizeGrid(size=size, origin=np.asarray(origin, float), spacing=float(step))


def face_edges(
    vertices: np.ndarray, triangles: np.ndarray, face_id: np.ndarray, faces: set[int]
) -> list[np.ndarray]:
    """The boundary loops of a set of CAD faces on their triangulation, each a closed polyline."""
    chosen = triangles[np.isin(face_id, list(faces))]
    if not len(chosen):
        return []
    edges = np.concatenate([chosen[:, [0, 1]], chosen[:, [1, 2]], chosen[:, [2, 0]]])
    key = np.sort(edges, axis=1)
    _, inverse, count = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    boundary = edges[count[inverse.ravel()] == 1]
    following: dict[int, list[int]] = {}
    for a, b in boundary:
        following.setdefault(int(a), []).append(int(b))
        following.setdefault(int(b), []).append(int(a))
    seen: set[tuple[int, int]] = set()
    loops = []
    for start in list(following):
        for nxt in following[start]:
            if (start, nxt) in seen:
                continue
            path = [start, nxt]
            seen.update({(start, nxt), (nxt, start)})
            while path[-1] != start:
                here, before = path[-1], path[-2]
                options = [v for v in following[here] if v != before and (here, v) not in seen]
                if not options:
                    break
                path.append(options[0])
                seen.update({(here, options[0]), (options[0], here)})
            if path[-1] == start and len(path) > 3:
                loops.append(vertices[path].astype(np.float64))
    return loops


def _run(work: Path, params: dict, timeout: float | None) -> tuple[np.ndarray, np.ndarray, dict]:
    (work / "params.json").write_text(json.dumps(params), encoding="utf-8")
    limit = int(timeout or 900)
    # Stopped on Linux's side, where it runs; a Windows-side timeout alone would leave it running.
    command = (
        f"timeout --signal=TERM --kill-after=15 {limit} "
        f"python '{wsl.to_wsl(SCRIPT)}' '{wsl.to_wsl(work)}'"
    )
    ran = wsl.bash(wsl.in_env(ENV, command), timeout=limit + 60)
    if not ran.ok or not (work / "tets.npz").exists():
        raise MeshFailed((ran.err or ran.out)[-2000:] or "the mesher wrote nothing")
    made = np.load(work / "tets.npz")
    info = json.loads((work / "mesh.json").read_text(encoding="utf-8"))
    return made["nodes"], made["tets"], info


def _write_common(work: Path, sizes: SizeGrid | None, lines: list[np.ndarray]) -> None:
    if sizes is not None:
        np.savez(work / "sizes.npz", size=sizes.size, origin=sizes.origin, spacing=sizes.spacing)
    if lines:
        np.savez(work / "lines.npz", **{f"line{i}": line for i, line in enumerate(lines)})


def workspace(root: Path) -> Path:
    work = root / f"mesh-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    work.mkdir(parents=True)
    return work


def mesh_field(
    field,
    work: Path,
    sizes: SizeGrid | None = None,
    lines: list[np.ndarray] | None = None,  # type: ignore[no-untyped-def]
    timeout: float | None = 600,
    **params: float,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Linear tets from a distance field (the product's :class:`Field`): trilinear across its grid,
    exact within its band."""
    grid = field.grid
    np.savez(
        work / "field.npz",
        origin=np.asarray(grid.origin, float),
        spacing=float(grid.spacing_mm),
        shape=np.asarray(grid.shape, np.int64),
        inside=np.packbits(np.asarray(field.inside).ravel()),
        band_index=field.band_index,
        band_mm=field.band_mm,
        reach_mm=float(field.reach_mm),
    )
    _write_common(work, sizes, lines or [])
    return _run(work, {"mode": "field", **params}, timeout)


def mesh_surface(
    vertices: np.ndarray,
    triangles: np.ndarray,
    work: Path,
    sizes: SizeGrid | None = None,
    lines: list[np.ndarray] | None = None,
    timeout: float | None = 600,
    **params: float,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Linear tets filling a closed triangulated surface."""
    np.savez(
        work / "surface.npz",
        vertices=np.asarray(vertices, np.float64),
        triangles=np.asarray(triangles, np.int64),
    )
    _write_common(work, sizes, lines or [])
    return _run(work, {"mode": "surface", **params}, timeout)


def finish(nodes: np.ndarray, tets: np.ndarray) -> FEMesh:
    """Linear tets as TET10 with straight mid-side nodes, the unused nodes dropped, every tet
    positively oriented; the volume as the cell group ``BULK``."""
    used, compact = np.unique(tets, return_inverse=True)
    nodes, tets = np.asarray(nodes, np.float64)[used], compact.reshape(tets.shape)
    tets = oriented(nodes, tets)
    nodes10, tets10 = quadratic(nodes, tets)
    return FEMesh(
        nodes=nodes10,
        cells={"TETRA10": tets10},
        cell_groups={"BULK": {"TETRA10": np.arange(len(tets10))}},
    )


def clean(work: Path) -> None:
    shutil.rmtree(work, ignore_errors=True)
