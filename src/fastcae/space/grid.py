"""The grid every region is a mask on, and the few operations every step needs: which cells are the
part, how far each cell is from something, points spread evenly over faces, and rays marched
through cells until they meet metal.

One grid for everything, so every region can be combined with every other cell by cell.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..generate.field import Field, Grid, build_field
from ..geometry.brep import Tessellation

# Rays marched per pass. Bounds peak memory: a pass holds one cell index per ray per step.
RAY_CHUNK = 60_000


def part_field(
    tess: Tessellation, spacing_mm: float, headroom_mm: float, digest: str = ""
) -> Field:
    """The part sampled on a grid with room around it for everything the design space holds.

    The field's own classification is exact on a watertight surface - ray parity, with the
    extraction's health gate behind it - so a cell is part or air with no threshold to choose.
    """
    return build_field(tess, spacing_mm=spacing_mm, source_digest=digest, headroom_mm=headroom_mm)


def cell_of(grid: Grid, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The flat index of the cell holding each point, and whether the point is on the grid."""
    ijk = np.rint((np.asarray(points, float) - np.asarray(grid.origin)) / grid.spacing_mm).astype(
        np.int64
    )
    shape = np.asarray(grid.shape)
    on = np.all((ijk >= 0) & (ijk < shape), axis=1)
    ijk = np.clip(ijk, 0, shape - 1)
    return np.ravel_multi_index((ijk[:, 0], ijk[:, 1], ijk[:, 2]), grid.shape), on


def distance_to(target: np.ndarray, spacing_mm: float, indices: bool = False):  # type: ignore[no-untyped-def]
    """Distance in mm from every cell to the nearest ``True`` cell of ``target`` - and, asked for,
    that cell's flat index. On the GPU when CuPy can, the same answer either way.

    The distance is between cell centres, so it is exact to half a cell: what a grid can know.
    """
    try:
        import cupy as cp
        from cupyx.scipy import ndimage as gnd

        image = cp.asarray(~target)
        if indices:
            dist, idx = gnd.distance_transform_edt(
                image, sampling=spacing_mm, return_indices=True, float64_distances=False
            )
            flat = cp.ravel_multi_index(tuple(idx), target.shape)
            del idx
            out = cp.asnumpy(dist), cp.asnumpy(flat).astype(np.int64)
        else:
            dist = gnd.distance_transform_edt(image, sampling=spacing_mm, float64_distances=False)
            out = cp.asnumpy(dist)
        del image, dist
        cp.get_default_memory_pool().free_all_blocks()
        return out
    except Exception:  # noqa: BLE001 - no GPU, or not enough of one: the CPU gives the same answer
        from scipy import ndimage

        if indices:
            dist, idx = ndimage.distance_transform_edt(
                ~target, sampling=spacing_mm, return_indices=True
            )
            return dist.astype(np.float32), np.ravel_multi_index(tuple(idx), target.shape).astype(
                np.int64
            )
        return ndimage.distance_transform_edt(~target, sampling=spacing_mm).astype(np.float32)


@dataclass
class Samples:
    """Points spread evenly over a surface, each with its outward normal and CAD face."""

    points: np.ndarray
    normals: np.ndarray
    face: np.ndarray
    triangle: np.ndarray

    def __len__(self) -> int:
        return int(len(self.points))

    def subset(self, keep: np.ndarray) -> Samples:
        return Samples(self.points[keep], self.normals[keep], self.face[keep], self.triangle[keep])


def sample_surface(
    tess: Tessellation,
    spacing_mm: float,
    seed: int = 0,
    triangles: np.ndarray | None = None,
    per_cell: float = 0.5,
) -> Samples:
    """About ``per_cell`` points per cell face's worth of area, never fewer than one a triangle, so
    a small face is never missed and a large one is covered evenly."""
    tri = tess.triangles if triangles is None else tess.triangles[triangles]
    index = np.arange(len(tess.triangles)) if triangles is None else np.asarray(triangles)
    a, b, c = (tess.vertices[tri[:, k]] for k in range(3))
    cross = np.cross(b - a, c - a)
    area = 0.5 * np.linalg.norm(cross, axis=1)
    normal = cross / np.maximum(2.0 * area, 1e-12)[:, None]
    count = np.maximum(1, np.ceil(area / (spacing_mm * spacing_mm) * per_cell)).astype(np.int64)
    owner = np.repeat(np.arange(len(tri)), count)
    rng = np.random.default_rng(seed)
    r1 = np.sqrt(rng.random(len(owner)))
    r2 = rng.random(len(owner))
    points = (
        (1 - r1)[:, None] * a[owner]
        + (r1 * (1 - r2))[:, None] * b[owner]
        + (r1 * r2)[:, None] * c[owner]
    )
    return Samples(points, normal[owner], tess.face_id[index[owner]].astype(np.int64), index[owner])


def march(
    grid: Grid,
    solid: np.ndarray,
    starts: np.ndarray,
    directions: np.ndarray,
    length_mm: float | np.ndarray,
    step_mm: float | None = None,
    stop_at_solid: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Rays from ``starts`` along ``directions`` (unit), each until it meets a solid cell, leaves
    the grid or has run its length.

    Returns the flat indices of every cell a ray passed through before stopping (repeats removed),
    and how far each ray got in mm. The cell a ray stops in is not included.
    """
    step = step_mm or 0.5 * grid.spacing_mm
    starts = np.asarray(starts, float)
    shared = np.asarray(directions, float)
    if shared.ndim == 1 and stop_at_solid:
        axis = int(np.argmax(np.abs(shared)))
        if abs(abs(shared[axis]) - 1.0) < 1e-9:
            return _march_along_axis(
                grid, solid, starts, axis, int(np.sign(shared[axis])), length_mm
            )
    directions = np.broadcast_to(shared, starts.shape)
    lengths = np.broadcast_to(np.asarray(length_mm, float), (len(starts),))
    steps = int(math.ceil(float(lengths.max(initial=0.0)) / step)) + 1
    flat_solid = solid.ravel()
    visited: list[np.ndarray] = []
    reached = np.zeros(len(starts))
    per_chunk = max(1, RAY_CHUNK * 64 // max(steps, 1))
    distance = np.arange(steps) * step
    for lo in range(0, len(starts), per_chunk):
        hi = min(lo + per_chunk, len(starts))
        p = starts[lo:hi, None, :] + directions[lo:hi, None, :] * distance[None, :, None]
        cells, on = cell_of(grid, p.reshape(-1, 3))
        cells = cells.reshape(hi - lo, steps)
        on = on.reshape(hi - lo, steps) & (distance[None, :] <= lengths[lo:hi, None])
        blocked = ~on
        if stop_at_solid:
            blocked |= flat_solid[cells]
        # Everything from the first blocked step on is past the stop.
        first = np.where(blocked.any(axis=1), blocked.argmax(axis=1), steps)
        keep = np.arange(steps)[None, :] < first[:, None]
        visited.append(np.unique(cells[keep]))
        reached[lo:hi] = np.where(first > 0, distance[np.maximum(first - 1, 0)], 0.0)
    out = np.unique(np.concatenate(visited)) if visited else np.empty(0, np.int64)
    return out, reached


def _march_along_axis(
    grid: Grid,
    solid: np.ndarray,
    starts: np.ndarray,
    axis: int,
    sign: int,
    length_mm: float | np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """:func:`march` for rays along a grid axis: each ray is one column of cells, scanned whole."""
    h = grid.spacing_mm
    shape = np.asarray(grid.shape)
    ijk = np.rint((starts - np.asarray(grid.origin)) / h).astype(np.int64)
    on = np.all((ijk >= 0) & (ijk < shape), axis=1)
    lengths = np.broadcast_to(np.asarray(length_mm, float), (len(starts),))[on]
    ijk = ijk[on]
    if not len(ijk):
        return np.empty(0, np.int64), np.zeros(len(starts))
    others = [a for a in range(3) if a != axis]
    moved = np.moveaxis(solid, axis, -1)
    n = shape[axis]
    steps = np.arange(n)
    visited, reached = [], np.zeros(len(starts))
    reached_on = np.zeros(len(ijk))
    for lo in range(0, len(ijk), 20_000):
        block = ijk[lo : lo + 20_000]
        column = moved[block[:, others[0]], block[:, others[1]], :]
        k0 = block[:, axis]
        offset = (steps[None, :] - k0[:, None]) * sign
        to_edge = (n - 1 - k0) if sign > 0 else k0
        span = np.minimum(np.floor(lengths[lo : lo + 20_000] / h).astype(np.int64), to_edge)
        ahead = (offset >= 0) & (offset <= span[:, None])
        blocked = column & ahead
        # The first blocked cell in the direction of travel.
        far = np.where(blocked, offset, n + 1).min(axis=1)
        keep = ahead & (offset < far[:, None])
        rows, ks = np.nonzero(keep)
        cell = np.empty((len(rows), 3), np.int64)
        cell[:, others[0]] = block[rows, others[0]]
        cell[:, others[1]] = block[rows, others[1]]
        cell[:, axis] = ks
        visited.append(np.ravel_multi_index(tuple(cell.T), grid.shape))
        reached_on[lo : lo + 20_000] = np.maximum(np.minimum(far, span + 1) - 1, 0) * h
    reached[on] = reached_on
    return np.unique(np.concatenate(visited)), reached


def signed_depth(field: Field) -> np.ndarray:
    """How deep each cell lies in the metal, mm: positive inside, negative outside.

    Exact near the surface, where the field stores true distances; further in, the distance between
    cell centres less half a cell, which meets the exact band where it ends.
    """
    inside = field.inside
    h = field.grid.spacing_mm
    depth = distance_to(~inside, h) - 0.5 * h
    depth[~inside] = -h
    band = depth.ravel()
    band[field.band_index] = -field.band_mm
    return depth


def sample_linear(grid: Grid, values: np.ndarray, points: np.ndarray) -> np.ndarray:
    """``values`` at arbitrary points, by trilinear interpolation between cell centres."""
    u = (np.asarray(points, float) - np.asarray(grid.origin)) / grid.spacing_mm
    shape = np.asarray(grid.shape)
    i = np.clip(np.floor(u).astype(np.int64), 0, shape - 2)
    t = np.clip(u - i, 0.0, 1.0)
    flat = values.ravel()
    out = np.zeros(len(u), np.float32)
    for di in (0, 1):
        wi = t[:, 0] if di else 1 - t[:, 0]
        for dj in (0, 1):
            wj = wi * (t[:, 1] if dj else 1 - t[:, 1])
            for dk in (0, 1):
                w = wj * (t[:, 2] if dk else 1 - t[:, 2])
                index = ((i[:, 0] + di) * shape[1] + (i[:, 1] + dj)) * shape[2] + (i[:, 2] + dk)
                out += (w * flat[index]).astype(np.float32)
    return out


def thickness_behind(
    grid: Grid, depth: np.ndarray, points: np.ndarray, normals: np.ndarray, reach_mm: float
) -> np.ndarray:
    """Metal behind each surface point: twice the deepest point straight in along the normal,
    before the ray comes out of the metal. A plate reads as its thickness; a solid boss as its
    width, however deep it goes."""
    step = grid.spacing_mm / 3.0
    distance = np.arange(1, int(np.ceil(reach_mm / step)) + 1) * step
    out = np.zeros(len(points), np.float32)
    per_chunk = max(1, 4_000_000 // len(distance))
    for lo in range(0, len(points), per_chunk):
        hi = min(lo + per_chunk, len(points))
        p = points[lo:hi, None, :] - normals[lo:hi, None, :] * distance[None, :, None]
        d = sample_linear(grid, depth, p.reshape(-1, 3)).reshape(hi - lo, -1)
        out_of_metal = d < 0
        first = np.where(out_of_metal.any(axis=1), out_of_metal.argmax(axis=1), len(distance))
        before = np.arange(len(distance))[None, :] < first[:, None]
        out[lo:hi] = 2.0 * np.where(before, d, 0.0).max(axis=1)
    return out


def ray_max(
    grid: Grid,
    values: np.ndarray,
    stop: np.ndarray,
    starts: np.ndarray,
    directions: np.ndarray,
    length_mm: float,
) -> np.ndarray:
    """The largest of ``values`` each ray passes over before it reaches a ``stop`` cell or has run
    its length. Rays that stop at once give 0."""
    step = 0.5 * grid.spacing_mm
    distance = np.arange(int(math.ceil(length_mm / step)) + 1) * step
    flat_values, flat_stop = values.ravel(), stop.ravel()
    out = np.zeros(len(starts), np.float32)
    per_chunk = max(1, RAY_CHUNK * 64 // len(distance))
    for lo in range(0, len(starts), per_chunk):
        hi = min(lo + per_chunk, len(starts))
        p = starts[lo:hi, None, :] + directions[lo:hi, None, :] * distance[None, :, None]
        cells, on = cell_of(grid, p.reshape(-1, 3))
        cells = cells.reshape(hi - lo, -1)
        blocked = ~on.reshape(hi - lo, -1) | flat_stop[cells]
        first = np.where(blocked.any(axis=1), blocked.argmax(axis=1), len(distance))
        before = np.arange(len(distance))[None, :] < first[:, None]
        out[lo:hi] = np.where(before, flat_values[cells], 0.0).max(axis=1)
    return out


def mask_of(grid: Grid, flat: np.ndarray) -> np.ndarray:
    out = np.zeros(grid.shape, bool)
    out.ravel()[flat] = True
    return out


def box_of(grid: Grid, lo_mm: np.ndarray, hi_mm: np.ndarray) -> tuple[slice, slice, slice]:
    """The cells a world-space box covers, as slices."""
    lo = np.floor((np.asarray(lo_mm) - np.asarray(grid.origin)) / grid.spacing_mm).astype(int)
    hi = np.ceil((np.asarray(hi_mm) - np.asarray(grid.origin)) / grid.spacing_mm).astype(int) + 1
    lo = np.clip(lo, 0, np.asarray(grid.shape))
    hi = np.clip(hi, 0, np.asarray(grid.shape))
    return tuple(slice(int(a), int(b)) for a, b in zip(lo, hi, strict=True))  # type: ignore[return-value]


def centres_of_box(grid: Grid, box: tuple[slice, slice, slice]) -> np.ndarray:
    """World coordinates of every cell in a box, shape (*box, 3)."""
    axes = [
        np.asarray(grid.origin)[a] + np.arange(box[a].start, box[a].stop) * grid.spacing_mm
        for a in range(3)
    ]
    x, y, z = np.meshgrid(*axes, indexing="ij")
    return np.stack([x, y, z], axis=-1)


def orthonormal(n: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Two unit vectors square to ``n`` and to each other."""
    n = np.asarray(n, float) / np.linalg.norm(n)
    helper = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(n, helper)
    u /= np.linalg.norm(u)
    return u, np.cross(n, u)
