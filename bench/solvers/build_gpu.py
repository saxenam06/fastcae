"""Design #7 rebuilt with the build's slowest step on the GPU - a trial, not a change to the product:
``compose._part_distance``, each window cell's exact distance to the part, is swapped at run time
for nearest-point queries against a bounding-volume hierarchy on the GPU (NVIDIA Warp), and every
step of the build is timed.

The part's tessellation has triangles 570 mm long and a millimetre high - OCC's chords across big
faces - and in single precision the nearest point on such a sliver comes out wrong by up to half a
millimetre. Split into pieces no longer than 16 mm - the same surface, better-shaped triangles -
the GPU agrees with the exact CPU answer to 0.004 mm on every cell of the band. The split is done
once for the part; each window selects its triangles exactly as the product code does.

The window cached by the earlier, CPU build is set aside first, so the build computes it again.
Writes the design as ``export_design.py`` does, to ``solve/<BENCH_CASE>/`` (design7gpu by default),
and the step times to ``build_gpu.json``.

    python build_gpu.py
"""

from __future__ import annotations

import json
import os
import shutil
import time

os.environ.setdefault("BENCH_CASE", "design7gpu")

import numpy as np  # noqa: E402
import warp as wp  # noqa: E402
from common import OUT, SCRATCH  # noqa: E402

from fastcae.generate import compose, intent, thicken  # noqa: E402

wp.config.quiet = True
LONGEST_MM = 16.0
TIMES: dict[str, float] = {}
COUNTS: dict[str, int] = {}
_split: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}


def split_long(vertices: np.ndarray, triangles: np.ndarray, longest: float):
    """Every triangle with an edge over ``longest`` halved across that edge, again and again - the
    same surface in better-shaped pieces - with each piece's original triangle."""
    parts = [vertices.astype(np.float64)]
    count = len(vertices)
    t = triangles.astype(np.int64)
    parent = np.arange(len(t))
    while True:
        verts = np.concatenate(parts)
        edge = np.linalg.norm(verts[t[:, [1, 2, 0]]] - verts[t], axis=2)  # edge k runs t[k] -> t[k+1]
        k = edge.argmax(axis=1)
        long = edge[np.arange(len(t)), k] > longest
        if not long.any():
            return verts, t, parent
        rows = np.flatnonzero(long)
        kk = k[rows]
        a, b, c = t[rows, kk], t[rows, (kk + 1) % 3], t[rows, (kk + 2) % 3]
        # One midpoint per edge, shared by the two triangles on it, so the surface stays closed.
        unique, inverse = np.unique(np.sort(np.stack([a, b], axis=1), axis=1), axis=0, return_inverse=True)
        parts.append(0.5 * (verts[unique[:, 0]] + verts[unique[:, 1]]))
        m = count + inverse.ravel()
        count += len(unique)
        t = np.concatenate([t[~long], np.stack([a, m, c], axis=1), np.stack([m, b, c], axis=1)])
        parent = np.concatenate([parent[~long], parent[rows], parent[rows]])


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


def gpu_part_distance(tess, window, reach, faces=None, around=None):
    """``compose._part_distance`` on the GPU: the same triangles, the same answer."""
    started = time.perf_counter()
    lo = np.asarray(window.origin) - reach
    hi = np.asarray(window.origin) + (np.asarray(window.shape) - 1) * window.spacing_mm + reach
    corners = tess.vertices[tess.triangles]
    top, bottom = corners.max(axis=1), corners.min(axis=1)
    keep = np.all(top >= lo, axis=1) & np.all(bottom <= hi, axis=1)
    if faces is not None:
        keep &= np.isin(tess.face_id, list(faces))
    if around:
        near = np.zeros(len(keep), dtype=bool)
        for box_lo, box_hi in around:
            near |= np.all(top >= np.asarray(box_lo) - 2.0 * reach, axis=1) & np.all(
                bottom <= np.asarray(box_hi) + 2.0 * reach, axis=1
            )
        keep &= near
    if not keep.any():
        return np.full(window.n_cells, reach)
    key = id(tess)
    if key not in _split:
        t0 = time.perf_counter()
        _split[key] = split_long(tess.vertices, tess.triangles, LONGEST_MM)
        TIMES["split_triangles"] = TIMES.get("split_triangles", 0.0) + time.perf_counter() - t0
    vertices, triangles, parent = _split[key]
    chosen = triangles[keep[parent]]
    mesh = wp.Mesh(
        points=wp.array(vertices.astype(np.float32), dtype=wp.vec3),
        indices=wp.array(chosen.astype(np.int32).ravel(), dtype=int),
    )
    out = np.empty(window.n_cells, dtype=np.float64)
    chunk = 1 << 24
    buffer = wp.empty(chunk, dtype=float)
    _, ny, nz = window.shape
    for first in range(0, window.n_cells, chunk):
        n = min(chunk, window.n_cells - first)
        wp.launch(
            _nearest,
            dim=n,
            inputs=[mesh.id, wp.vec3(*window.origin), float(window.spacing_mm), ny, nz, first, float(reach), buffer],
        )
        out[first : first + n] = buffer.numpy()[:n]
    TIMES["gpu_distance"] = TIMES.get("gpu_distance", 0.0) + time.perf_counter() - started
    COUNTS["cells"] = COUNTS.get("cells", 0) + window.n_cells
    COUNTS["calls"] = COUNTS.get("calls", 0) + 1
    return out


def timed(module, name: str) -> None:
    """Wrap ``module.name`` to add its time to the step's total."""
    original = getattr(module, name)

    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            TIMES[name] = TIMES.get(name, 0.0) + time.perf_counter() - t0

    setattr(module, name, wrapper)


def main() -> None:
    project = SCRATCH / "e2e" / "projects" / "GRC_Gearbox_Housing"
    aside = project / ".fastcae-windows-set-aside"
    aside.mkdir(exist_ok=True)
    for cached in (project / ".fastcae").glob("window-*.pickle"):
        shutil.move(str(cached), aside / cached.name)

    compose._part_distance = gpu_part_distance
    thicken._part_distance = gpu_part_distance
    for name in ("window_between", "compose", "recontour", "check", "move_faces", "screen", "cut"):
        if hasattr(intent, name):
            timed(intent, name)

    import export_design

    started = time.perf_counter()
    export_design.main()
    total = time.perf_counter() - started
    report = {"total_s": total, "steps_s": TIMES, "counts": COUNTS, "split_longest_mm": LONGEST_MM}
    (OUT / "build_gpu.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
