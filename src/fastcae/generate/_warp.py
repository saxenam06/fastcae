"""The part's distance on the GPU, with NVIDIA Warp: a bounding-volume hierarchy over the triangles
and one nearest-point query a cell. Imported only when Warp is installed; :mod:`.distance` says when
it is used and why its triangles are split first."""

from __future__ import annotations

import numpy as np
import warp as wp

from .field import Grid

wp.config.log_level = wp.LOG_WARNING

# Cells answered at once: bounds the buffer on the card, not the answer.
CHUNK = 1 << 24


def ready() -> bool:
    """Whether there is a CUDA device to answer on."""
    wp.init()
    return wp.get_cuda_device_count() > 0


@wp.kernel
def _nearest(
    mesh: wp.uint64,
    origin: wp.vec3,
    spacing: float,
    ny: int,
    nz: int,
    first: int,
    reach: float,
    out: wp.array(dtype=float),
):
    tid = wp.tid()
    flat = first + tid
    i = flat // (ny * nz)
    j = (flat // nz) % ny
    k = flat % nz
    p = origin + wp.vec3(float(i), float(j), float(k)) * spacing
    q = wp.mesh_query_point_no_sign(mesh, p, reach)
    if q.result:
        out[tid] = wp.min(wp.length(p - wp.mesh_eval_position(mesh, q.face, q.u, q.v)), reach)
    else:
        out[tid] = reach


@wp.kernel
def _nearest_points(
    mesh: wp.uint64,
    points: wp.array(dtype=wp.vec3),
    reach: float,
    out: wp.array(dtype=float),
):
    tid = wp.tid()
    p = points[tid]
    q = wp.mesh_query_point_no_sign(mesh, p, reach)
    if q.result:
        out[tid] = wp.min(wp.length(p - wp.mesh_eval_position(mesh, q.face, q.u, q.v)), reach)
    else:
        out[tid] = reach


def _mesh(vertices: np.ndarray, triangles: np.ndarray) -> wp.Mesh:
    return wp.Mesh(
        points=wp.array(vertices.astype(np.float32), dtype=wp.vec3, device="cuda"),
        indices=wp.array(triangles.astype(np.int32).ravel(), dtype=int, device="cuda"),
    )


def nearest(vertices: np.ndarray, triangles: np.ndarray, window: Grid, reach: float) -> np.ndarray:
    """Each cell of ``window``'s distance to the nearest of ``triangles``, out to ``reach``."""
    mesh = _mesh(vertices, triangles)
    out = np.empty(window.n_cells, dtype=np.float32)
    buffer = wp.empty(min(CHUNK, window.n_cells), dtype=float, device="cuda")
    _, ny, nz = window.shape
    origin = wp.vec3(*(float(v) for v in window.origin))
    for first in range(0, window.n_cells, CHUNK):
        n = min(CHUNK, window.n_cells - first)
        wp.launch(
            _nearest,
            dim=n,
            inputs=[mesh.id, origin, float(window.spacing_mm), ny, nz, first, float(reach), buffer],
            device="cuda",
        )
        out[first : first + n] = buffer.numpy()[:n]
    return out


def nearest_points(
    vertices: np.ndarray, triangles: np.ndarray, points: np.ndarray, reach: float
) -> np.ndarray:
    """Each point's distance to the nearest of ``triangles``, out to ``reach``."""
    mesh = _mesh(vertices, triangles)
    out = np.empty(len(points), dtype=np.float32)
    for first in range(0, len(points), CHUNK):
        chunk = np.ascontiguousarray(points[first : first + CHUNK], dtype=np.float32)
        where = wp.array(chunk, dtype=wp.vec3, device="cuda")
        buffer = wp.empty(len(chunk), dtype=float, device="cuda")
        wp.launch(
            _nearest_points, dim=len(chunk), inputs=[mesh.id, where, float(reach), buffer],
            device="cuda",
        )  # fmt: skip
        out[first : first + len(chunk)] = buffer.numpy()
    return out
