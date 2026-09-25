"""Flat sections of a closed triangle surface: the metal a plane cuts, as exact 2D polygons.

Design volumes and rib outlines are all asked the same question - where, in this plane, is the
part's metal, and which of its faces bounds it there? - and answering it in 2D keeps every answer
robust: no solid booleans on the whole part, whose failures depend on how its surfaces meet.

**Exact to the triangulation.** A plane meets the surface's triangles along segments; a segment's
ends lie on mesh edges, and two triangles sharing an edge share that end exactly - it is named by
the edge, not found by a tolerance - so the segments chain into closed loops by topology alone. The
metal is every loop filled by the even-odd rule: an outer wall and the bore through it make a ring.
The triangulation is the display's, within a quarter of a millimetre of the CAD.

**Faces kept.** Every segment carries the CAD face its triangle came from, so a region can be asked
which faces bound it - "does this pocket of air meet the ring?" - in the plane.

Nothing here knows what the surface is: a part, a keep-out, a region, all are closed triangle
surfaces.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import shapely
from shapely.geometry import MultiLineString, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

# A vertex this close to the plane is moved off it, so every crossing is a clean one.
ON_PLANE = 1e-9


@dataclass(frozen=True)
class Plane:
    """A plane with axes in it: ``u`` and ``v`` span it, ``normal`` is square to both."""

    origin: np.ndarray
    normal: np.ndarray
    u: np.ndarray
    v: np.ndarray

    def to2d(self, points: np.ndarray) -> np.ndarray:
        offset = np.asarray(points, float) - self.origin
        return np.stack([offset @ self.u, offset @ self.v], axis=-1)

    def to3d(self, uv: np.ndarray) -> np.ndarray:
        uv = np.asarray(uv, float)
        return self.origin + uv[..., :1] * self.u + uv[..., 1:2] * self.v

    def shifted(self, distance: float) -> Plane:
        return Plane(self.origin + distance * self.normal, self.normal, self.u, self.v)


def plane(origin, normal, u=None) -> Plane:  # type: ignore[no-untyped-def]
    """A plane through ``origin`` square to ``normal``; ``u`` along the given direction projected
    into it, when given."""
    n = np.asarray(normal, float)
    n = n / np.linalg.norm(n)
    if u is None:
        u = np.cross(n, [1.0, 0.0, 0.0] if abs(n[0]) < 0.9 else [0.0, 1.0, 0.0])
    u = np.asarray(u, float) - np.dot(u, n) * n
    u = u / np.linalg.norm(u)
    return Plane(np.asarray(origin, float), n, u, np.cross(n, u))


@dataclass
class Section:
    """Where a plane cuts a closed surface: the inside as polygons, and the cut's segments with the
    face each came from, all in the plane's own coordinates."""

    inside: BaseGeometry
    segments: np.ndarray
    """(m, 2, 2) mm."""
    faces: np.ndarray
    """(m,) the face each segment came from."""

    def lines(self, faces) -> BaseGeometry:  # type: ignore[no-untyped-def]
        """The cut along ``faces``, as lines."""
        mine = np.isin(self.faces, np.asarray(list(faces), np.int64))
        return MultiLineString([tuple(map(tuple, s)) for s in self.segments[mine]])


EMPTY = MultiPolygon()


def section(
    vertices: np.ndarray, triangles: np.ndarray, face_id: np.ndarray | None, at: Plane
) -> Section:
    """The plane's cut through a closed triangle surface."""
    vertices = np.asarray(vertices, float)
    d = (vertices - at.origin) @ at.normal
    d = np.where(np.abs(d) < ON_PLANE, ON_PLANE, d)
    sd = d[triangles]
    crossing = (sd.min(axis=1) < 0.0) & (sd.max(axis=1) > 0.0)
    tri = triangles[crossing]
    if not len(tri):
        return Section(EMPTY, np.empty((0, 2, 2)), np.empty(0, np.int64))
    faces = np.zeros(len(tri), np.int64) if face_id is None else np.asarray(face_id)[crossing]

    # Each crossing triangle has two edges that cross; each end is named by its mesh edge, low
    # vertex first, and computed from that order, so neighbours agree on it exactly.
    ends = []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        ia, ib = tri[:, a], tri[:, b]
        lo, hi = np.minimum(ia, ib), np.maximum(ia, ib)
        cross = (d[lo] < 0.0) != (d[hi] < 0.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            t = np.where(cross, d[lo] / np.where(cross, d[lo] - d[hi], 1.0), 0.0)
        point = vertices[lo] + t[:, None] * (vertices[hi] - vertices[lo])
        ends.append((cross, lo, hi, point))
    first_key = np.full(len(tri), -1, np.int64)
    second_key = np.full(len(tri), -1, np.int64)
    first_pt = np.zeros((len(tri), 3))
    second_pt = np.zeros((len(tri), 3))
    stride = np.int64(len(vertices))
    for cross, lo, hi, point in ends:
        key = lo.astype(np.int64) * stride + hi.astype(np.int64)
        take_first = cross & (first_key < 0)
        take_second = cross & ~take_first
        first_key[take_first], first_pt[take_first] = key[take_first], point[take_first]
        second_key[take_second], second_pt[take_second] = key[take_second], point[take_second]
    ok = (first_key >= 0) & (second_key >= 0)
    first_key, second_key = first_key[ok], second_key[ok]
    first_pt, second_pt, faces = first_pt[ok], second_pt[ok], faces[ok]
    segments = np.stack([at.to2d(first_pt), at.to2d(second_pt)], axis=1)
    return Section(_filled(first_key, second_key, segments), segments, faces)


def _filled(first: np.ndarray, second: np.ndarray, segments: np.ndarray) -> BaseGeometry:
    """The segments chained into loops by the mesh edges they end on, filled even-odd."""
    point_of: dict[int, np.ndarray] = {}
    links: dict[int, list[int]] = {}
    for k, (a, b) in enumerate(zip(first.tolist(), second.tolist(), strict=True)):
        point_of[a] = segments[k, 0]
        point_of[b] = segments[k, 1]
        links.setdefault(a, []).append(b)
        links.setdefault(b, []).append(a)
    seen: set[int] = set()
    rings = []
    for start in links:
        if start in seen or len(links[start]) != 2:
            continue
        ring = [start]
        seen.add(start)
        previous, current = start, links[start][0]
        closed = False
        while True:
            if current == start:
                closed = True
                break
            if current in seen or len(links.get(current, ())) != 2:
                break
            seen.add(current)
            ring.append(current)
            a, b = links[current]
            previous, current = current, (b if a == previous else a)
        if closed and len(ring) >= 3:
            rings.append(np.array([point_of[k] for k in ring]))
    return _even_odd([Polygon(r) for r in rings])


def _even_odd(loops: list[Polygon]) -> BaseGeometry:
    """Loops that never cross, filled even-odd: each one inside an even number of others is an
    outline of metal, each inside an odd number a hole in the one just outside it."""
    loops = [loop if loop.is_valid else loop.buffer(0) for loop in loops]
    loops = [loop for loop in loops if not loop.is_empty and loop.area > 0.0]
    if not loops:
        return EMPTY
    loops.sort(key=lambda loop: -loop.area)
    for loop in loops:
        shapely.prepare(loop)
    parent = [-1] * len(loops)
    depth = [0] * len(loops)
    for i, loop in enumerate(loops):
        probe = loop.representative_point()
        # The smallest larger loop holding it is the one just outside it.
        for j in range(i - 1, -1, -1):
            if loops[j].contains(probe) and loops[j].area > loop.area:
                parent[i] = j
                depth[i] = depth[j] + 1
                break
    shells = []
    for i, loop in enumerate(loops):
        if depth[i] % 2:
            continue
        holes = [loops[k] for k in range(len(loops)) if parent[k] == i]
        shell = loop
        for hole in holes:
            shell = shell.difference(hole)
        shells.append(shell)
    return shapely.union_all(shells)


def cylinder_mesh(
    point: np.ndarray, axis: np.ndarray, radius: float, lo: float, hi: float, segments: int = 96
) -> tuple[np.ndarray, np.ndarray]:
    """A closed cylinder about ``axis`` through ``point``, from ``lo`` to ``hi`` along it."""
    axis = np.asarray(axis, float) / np.linalg.norm(axis)
    u = np.cross(axis, [1.0, 0.0, 0.0] if abs(axis[0]) < 0.9 else [0.0, 1.0, 0.0])
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    angles = np.linspace(0.0, 2.0 * math.pi, segments, endpoint=False)
    ring = radius * (np.cos(angles)[:, None] * u + np.sin(angles)[:, None] * v)
    base = np.asarray(point, float)
    bottom = base + lo * axis + ring
    top = base + hi * axis + ring
    vertices = np.vstack([bottom, top, [base + lo * axis], [base + hi * axis]])
    n = segments
    i = np.arange(n)
    j = (i + 1) % n
    sides = np.concatenate([np.stack([i, j, n + j], 1), np.stack([i, n + j, n + i], 1)])
    caps = np.concatenate(
        [np.stack([np.full(n, 2 * n), j, i], 1), np.stack([np.full(n, 2 * n + 1), n + i, n + j], 1)]
    )
    return vertices, np.concatenate([sides, caps]).astype(np.int64)


def prism_mesh(
    vertices: np.ndarray, triangles: np.ndarray, direction: np.ndarray, back: float, depth: float
) -> tuple[np.ndarray, np.ndarray]:
    """A closed solid swept from an open patch of triangles along ``direction``: from ``back``
    behind it to ``depth`` in front of it."""
    direction = np.asarray(direction, float) / np.linalg.norm(direction)
    used, compact = np.unique(triangles, return_inverse=True)
    compact = compact.reshape(triangles.shape)
    patch = np.asarray(vertices, float)[used]
    n = len(patch)
    low = patch - back * direction
    high = patch + depth * direction
    # The patch's boundary: edges used by one triangle only.
    edges = np.concatenate([compact[:, [0, 1]], compact[:, [1, 2]], compact[:, [2, 0]]])
    key = np.sort(edges, axis=1)
    _, first, counts = np.unique(key, axis=0, return_index=True, return_counts=True)
    rim = edges[first[counts == 1]]
    a, b = rim[:, 0], rim[:, 1]
    sides = np.concatenate([np.stack([a, b, n + b], 1), np.stack([a, n + b, n + a], 1)])
    faces = np.concatenate([compact[:, ::-1], compact + n, sides])
    return np.vstack([low, high]), faces.astype(np.int64)


def triangles_of(region: BaseGeometry) -> np.ndarray:
    """A polygon, holes and all, as triangles in its plane: (t, 3, 2)."""
    if region.is_empty:
        return np.empty((0, 3, 2))
    out = []
    for polygon in getattr(region, "geoms", [region]):
        if polygon.is_empty or polygon.geom_type != "Polygon":
            continue
        mesh = shapely.constrained_delaunay_triangles(polygon)
        for triangle in mesh.geoms:
            out.append(np.asarray(triangle.exterior.coords)[:3])
    return np.asarray(out) if out else np.empty((0, 3, 2))
