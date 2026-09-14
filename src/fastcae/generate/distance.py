"""The part's exact distance from the cells of a window: on the GPU when there is one, the same
answer either way.

A design needs the part's distance further out than the band the base field stores: round its ribs,
where a fillet reads it, and round the faces it moves, as far as they move. :func:`part_distance` is
that one question - every cell of a window, its distance to the nearest of the part's triangles, or
of some of its faces, exactly out to a reach and clamped there - and it is the slowest step of a
build on the CPU, point against triangle, about seventy thousand cells a second.

**On the GPU**, when NVIDIA Warp is installed and a CUDA device is there: the triangles in a
bounding-volume hierarchy, one nearest-point query a cell - millions a second. **On the CPU**
otherwise: the exact scan conversion the base field is built with. ``FASTCAE_DISTANCE`` set to
``cpu`` or ``gpu`` chooses; unset, the GPU is used when it can be.

**Long triangles are split first, for the GPU.** OCC tessellates big faces with slivers - triangles
hundreds of millimetres long and a millimetre high - and in single precision the nearest point on
one comes out wrong by up to half a millimetre, always at the surface, where the fillets and the
contour read the field. Every triangle with an edge longer than :data:`LONGEST_MM` is halved across
it, again and again: the same surface in better-shaped pieces, done once for the part. Then no cell
differs from the exact answer by more than a few thousandths of a millimetre.

**The same triangles on both.** A window asks only about the triangles that can matter to it - those
within reach of it, of the faces asked about, near what will be composed in it - and both paths
answer over exactly those, so a cell the CPU clamps the GPU clamps too.
"""

from __future__ import annotations

import os
import threading
from typing import Any

import numpy as np

from ..geometry.brep import Tessellation
from .field import Grid, _unsigned_distance

# The longest edge a triangle keeps before it is halved, for the GPU's single precision.
LONGEST_MM = 16.0

_ENV = "FASTCAE_DISTANCE"
_state: dict[str, Any] = {}
# One question on the card at a time, and one part split at a time, whatever threads ask.
_lock = threading.Lock()


def backend() -> str:
    """Where the part's distance is computed: ``gpu`` or ``cpu``."""
    wanted = os.environ.get(_ENV, "").strip().lower()
    if wanted == "cpu":
        return "cpu"
    available = _gpu() is not None
    if wanted == "gpu" and not available:
        raise RuntimeError(f"{_ENV}=gpu, but NVIDIA Warp or a CUDA device is not there")
    return "gpu" if available else "cpu"


def _gpu():
    """The GPU module, once: None when Warp is not installed or finds no CUDA device."""
    if "gpu" not in _state:
        try:
            from . import _warp

            _state["gpu"] = _warp if _warp.ready() else None
        except Exception:  # noqa: BLE001 - no Warp, no driver, no device: the CPU answers
            _state["gpu"] = None
    return _state["gpu"]


def selected(
    tess: Tessellation,
    window: Grid,
    reach: float,
    faces: set[int] | None = None,
    around: list[tuple[np.ndarray, np.ndarray]] | None = None,
) -> np.ndarray:
    """Which of the part's triangles can matter to a window: within ``reach`` of it, of the
    ``faces`` asked about, and - given the boxes ``around`` - within twice the reach of one of
    them, where a cell within reach of a box has its nearest triangle."""
    lo = np.asarray(window.origin) - reach
    hi = np.asarray(window.origin) + (np.asarray(window.shape) - 1) * window.spacing_mm + reach
    corners = tess.vertices[tess.triangles]
    top, bottom = corners.max(axis=1), corners.min(axis=1)
    keep = np.all(top >= lo, axis=1) & np.all(bottom <= hi, axis=1)
    if faces is not None:
        keep &= np.isin(tess.face_id, np.fromiter(faces, dtype=np.int64, count=len(faces)))
    if around:
        near = np.zeros(len(keep), dtype=bool)
        for box_lo, box_hi in around:
            near |= np.all(top >= np.asarray(box_lo) - 2.0 * reach, axis=1) & np.all(
                bottom <= np.asarray(box_hi) + 2.0 * reach, axis=1
            )
        keep &= near
    return keep


def part_distance(
    tess: Tessellation,
    window: Grid,
    reach: float,
    faces: set[int] | None = None,
    around: list[tuple[np.ndarray, np.ndarray]] | None = None,
    *,
    on: str | None = None,
) -> np.ndarray:
    """Unsigned distance from each cell of ``window`` to the part - or to some of its ``faces`` -
    exactly out to ``reach`` and clamped there; given the boxes ``around``, exactly within
    ``reach`` of them and clamped beyond. Flat, in the window's order, in single precision - what
    the field stores.

    ``on`` is ``gpu`` or ``cpu``, or None for :func:`backend`'s choice."""
    keep = selected(tess, window, reach, faces, around)
    if not keep.any():
        return np.full(window.n_cells, reach, dtype=np.float32)
    where = on or backend()
    if where == "gpu":
        gpu = _gpu()
        if gpu is None:
            raise RuntimeError(
                "the GPU was asked for, and NVIDIA Warp or a CUDA device is not there"
            )
        with _lock:
            vertices, triangles, parent = split(tess)
            distance = gpu.nearest(vertices, triangles[keep[parent]], window, reach)
        return np.minimum(distance, np.float32(reach))
    local = Tessellation(
        vertices=tess.vertices,
        triangles=tess.triangles[keep],
        face_id=tess.face_id[keep],
        face_ids=tess.face_ids,
        deflection_mm=tess.deflection_mm,
        angle_deg=tess.angle_deg,
        faces_without_triangles=[],
    )
    return np.minimum(_unsigned_distance(local, window, reach).ravel(), np.float32(reach))


def split(tess: Tessellation) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The part's triangles with none longer than :data:`LONGEST_MM`, and each piece's original
    triangle - worked out once for the part."""
    held = _state.get("split")
    if held is not None and held[0] is tess:
        return held[1]
    made = split_long(tess.vertices, tess.triangles, LONGEST_MM)
    _state["split"] = (tess, made)
    return made


def split_long(
    vertices: np.ndarray, triangles: np.ndarray, longest: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Every triangle with an edge over ``longest`` halved across that edge, again and again - the
    same surface in better-shaped pieces - with each piece's original triangle. The midpoint of an
    edge is shared by the two triangles on it, so the surface stays closed."""
    parts = [np.asarray(vertices, dtype=np.float64)]
    count = len(vertices)
    t = np.asarray(triangles, dtype=np.int64)
    parent = np.arange(len(t))
    while True:
        verts = np.concatenate(parts)
        # Edge k runs from corner k to corner k + 1.
        edge = np.linalg.norm(verts[t[:, [1, 2, 0]]] - verts[t], axis=2)
        k = edge.argmax(axis=1)
        long = edge[np.arange(len(t)), k] > longest
        if not long.any():
            return verts, t, parent
        rows = np.flatnonzero(long)
        kk = k[rows]
        a, b, c = t[rows, kk], t[rows, (kk + 1) % 3], t[rows, (kk + 2) % 3]
        unique, inverse = np.unique(
            np.sort(np.stack([a, b], axis=1), axis=1), axis=0, return_inverse=True
        )
        parts.append(0.5 * (verts[unique[:, 0]] + verts[unique[:, 1]]))
        m = count + inverse.ravel()
        count += len(unique)
        t = np.concatenate([t[~long], np.stack([a, m, c], axis=1), np.stack([m, b, c], axis=1)])
        parent = np.concatenate([parent[~long], parent[rows], parent[rows]])
