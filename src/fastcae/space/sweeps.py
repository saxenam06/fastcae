"""The space round an interface that something else occupies, swept from the interface itself.

Nothing needs to know what the neighbouring part is. A plane that mates has something in front of
it over its whole outline; a bore has something passing along it; a hole has a fastener in it and a
tool beyond each open end; a boss that fits has something round it. Each sweep runs outward until
it meets the part's own metal - past that, nothing that came from this interface can reach.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from ..generate.field import Grid
from ..geometry.brep import Tessellation
from .grid import box_of, centres_of_box, march, orthonormal, sample_surface
from .model import Interface

# Long sweeps are marched with rays 0.7 cells apart and steps of 0.9 cells: every cell a sweep
# crosses still holds a ray point, at a fifth of the cost of half-cell spacing.
RAY_SPACING = 0.7
RAY_STEP = 0.9


def _triangles_of(tess: Tessellation, faces: list[int]) -> np.ndarray:
    return np.flatnonzero(np.isin(tess.face_id, np.asarray(faces)))


def _disc(centre: np.ndarray, axis: np.ndarray, radius: float, spacing: float) -> np.ndarray:
    """Points filling a disc square to ``axis``, at most ``spacing`` apart."""
    u, v = orthonormal(axis)
    n = max(1, int(np.ceil(radius / spacing)))
    x = np.arange(-n, n + 1) * spacing
    gx, gy = np.meshgrid(x, x, indexing="ij")
    keep = gx**2 + gy**2 <= radius**2
    if not keep.any():
        return centre[None, :]
    return centre[None, :] + gx[keep][:, None] * u[None, :] + gy[keep][:, None] * v[None, :]


def _stations(
    tess: Tessellation, faces: list[int], point: np.ndarray, axis: np.ndarray
) -> tuple[float, float]:
    """Where along an axis a set of faces begins and ends."""
    tri = tess.triangles[_triangles_of(tess, faces)]
    vertices = tess.vertices[np.unique(tri)]
    s = (vertices - point) @ axis
    return float(s.min()), float(s.max())


def plane_neighbour(
    grid: Grid,
    solid: np.ndarray,
    tess: Tessellation,
    interface: Interface,
    depth_mm: float | None = None,
) -> np.ndarray:
    """Everything in front of a plane over its whole outline - openings in it included, because
    whatever mates against the plane covers them - out to the first metal, or only ``depth_mm``
    deep: the lid a cover makes over the opening its flange rims."""
    if interface.normal is None:
        return np.empty(0, np.int64)
    n = np.asarray(interface.normal, float)
    u, v = orthonormal(n)
    tri = _triangles_of(tess, interface.faces)
    pixel = RAY_SPACING * grid.spacing_mm
    samples = sample_surface(tess, 0.5 * pixel, triangles=tri)
    origin = samples.points.mean(axis=0)
    xy = np.stack([(samples.points - origin) @ u, (samples.points - origin) @ v], axis=1)
    lo = xy.min(axis=0) - 2 * pixel
    ij = np.floor((xy - lo) / pixel).astype(int)
    shape = tuple(ij.max(axis=0) + 3)
    image = np.zeros(shape, bool)
    image[ij[:, 0], ij[:, 1]] = True
    image = ndimage.binary_closing(image, structure=np.ones((3, 3)), iterations=2)
    image = ndimage.binary_fill_holes(image)
    pi, pj = np.nonzero(image)
    offset = float(np.median((samples.points - origin) @ n))
    starts = (
        origin[None, :]
        + ((pi + 0.5) * pixel + lo[0])[:, None] * u[None, :]
        + ((pj + 0.5) * pixel + lo[1])[:, None] * v[None, :]
        + (offset + 0.75 * grid.spacing_mm) * n[None, :]
    )
    length = (
        float(depth_mm)
        if depth_mm is not None
        else float(np.linalg.norm(np.asarray(grid.shape) * grid.spacing_mm))
    )
    cells, _ = march(grid, solid, starts, n, length, step_mm=RAY_STEP * grid.spacing_mm)
    return cells


REGISTER_DEPTH = 0.1
"""A bore shallower than this many diameters is a register - a mating part sits in it - not a
passage something runs through."""

SHAFT_SHARE = 0.6
"""What passes on through a bore, as a share of its radius: a bearing's inner ring leaves about
this much for the shaft."""


def bore_ends(tess: Tessellation, interface: Interface) -> dict:
    """A bore's axis, radius, where it begins and ends, and whether it is a register."""
    a = np.asarray(interface.axis, float)
    p0 = np.asarray(interface.axis_point, float)
    s0, s1 = _stations(tess, interface.faces, p0, a)
    r = float(interface.radius_mm)
    return {
        "axis": a,
        "point": p0,
        "radius": r,
        "stations": (s0, s1),
        "register": (s1 - s0) < REGISTER_DEPTH * 2.0 * r,
    }


def bore_plug(
    grid: Grid, solid: np.ndarray, tess: Tessellation, interface: Interface
) -> np.ndarray:
    """The bore itself, over its own length: what sits in it - a bearing, a mating spigot."""
    if interface.axis is None or interface.axis_point is None or interface.radius_mm is None:
        return np.empty(0, np.int64)
    e = bore_ends(tess, interface)
    s0, s1 = e["stations"]
    centre = e["point"] + e["axis"] * 0.5 * (s0 + s1)
    starts = _disc(centre, e["axis"], 0.98 * e["radius"], RAY_SPACING * grid.spacing_mm)
    half = 0.5 * (s1 - s0) + 0.5 * grid.spacing_mm
    forward, _ = march(grid, solid, starts, e["axis"], half)
    backward, _ = march(grid, solid, starts, -e["axis"], half)
    return np.union1d(forward, backward)


def bore_beyond(
    grid: Grid, solid: np.ndarray, tess: Tessellation, interface: Interface, side: int, share: float
) -> np.ndarray:
    """From one end of a bore (``side`` +1 or -1 along its axis) on along the axis, within ``share``
    of its radius, out to the first metal."""
    e = bore_ends(tess, interface)
    s0, s1 = e["stations"]
    station = s1 if side > 0 else s0
    tip = e["point"] + e["axis"] * (station + side * 0.5 * grid.spacing_mm)
    starts = _disc(tip, e["axis"], 0.98 * share * e["radius"], RAY_SPACING * grid.spacing_mm)
    length = float(np.linalg.norm(np.asarray(grid.shape) * grid.spacing_mm))
    cells, _ = march(
        grid, solid, starts, side * e["axis"], length, step_mm=RAY_STEP * grid.spacing_mm
    )
    return cells


def ring_neighbour(
    grid: Grid, solid: np.ndarray, tess: Tessellation, interface: Interface
) -> np.ndarray:
    """Round a convex cylinder over its length: whatever fits over it."""
    if interface.axis is None or interface.axis_point is None or interface.radius_mm is None:
        return np.empty(0, np.int64)
    a = np.asarray(interface.axis, float)
    p0 = np.asarray(interface.axis_point, float)
    r = interface.radius_mm
    width = max(2.0 * grid.spacing_mm, 0.25 * r)
    s0, s1 = _stations(tess, interface.faces, p0, a)
    ends = np.array([p0 + a * s0, p0 + a * s1])
    reach = r + width
    box = box_of(grid, ends.min(axis=0) - reach, ends.max(axis=0) + reach)
    centres = centres_of_box(grid, box)
    rel = centres - p0
    s = rel @ a
    radial = np.linalg.norm(rel - s[..., None] * a, axis=-1)
    inside = (s >= s0) & (s <= s1) & (radial >= r) & (radial <= r + width) & ~solid[box]
    ii, jj, kk = np.nonzero(inside)
    return np.ravel_multi_index(
        (ii + box[0].start, jj + box[1].start, kk + box[2].start), grid.shape
    ).astype(np.int64)


def hole_access(
    grid: Grid,
    solid: np.ndarray,
    tess: Tessellation,
    faces: list[int],
    axis: np.ndarray,
    point: np.ndarray,
    radius: float,
    access_radius: float,
    access_length: float,
) -> tuple[np.ndarray, list[dict]]:
    """A hole's own bore, and beyond each open end a cylinder for the fastener's head and the tool.

    Returns the cells and, for each open end, how far straight out a tool can go before it meets
    metal - short means the hole cannot be reached from that side.
    """
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    s0, s1 = _stations(tess, faces, point, a)
    step = 0.5 * grid.spacing_mm
    mid = point + a * 0.5 * (s0 + s1)
    plug = _disc(mid, a, 0.98 * radius, step)
    half = 0.5 * (s1 - s0) + grid.spacing_mm
    cells = [march(grid, solid, plug, a, half)[0], march(grid, solid, plug, -a, half)[0]]
    ends = []
    flat_solid = solid.ravel()
    for sign, station in ((1.0, s1), (-1.0, s0)):
        tip = point + a * (station + sign * 0.6 * grid.spacing_mm)
        index = np.rint((tip - np.asarray(grid.origin)) / grid.spacing_mm).astype(int)
        if np.any(index < 0) or np.any(index >= np.asarray(grid.shape)):
            continue
        if flat_solid[np.ravel_multi_index(tuple(index), grid.shape)]:
            continue
        disc = _disc(tip, a, access_radius * radius, step)
        found, reached = march(grid, solid, disc, sign * a, access_length * 2.0 * radius)
        cells.append(found)
        centre_rays = np.linalg.norm(disc - tip, axis=1) <= radius
        ends.append(
            {
                "direction": (sign * a).tolist(),
                "at": tip.tolist(),
                "clear_mm": float(np.median(reached[centre_rays])) if centre_rays.any() else 0.0,
            }
        )
    return np.unique(np.concatenate(cells)), ends
