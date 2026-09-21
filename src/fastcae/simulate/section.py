"""Where a plane cuts a mesh of tets: the section, as triangles lying in the plane.

Each tet the plane crosses is cut along the edges running from one side of it to the other: a
corner alone on its side makes a triangle, two corners on each side a quadrilateral, drawn as two
triangles. What the nodes carry - a field of an answer, a displacement - is interpolated linearly
along the edges cut, so a section shows the answer inside the part, not only on its outside. Each
triangle says which of its edges are element edges, so a quadrilateral's diagonal is never drawn as
one.

Only the corner nodes are used: a second-order tet is cut as the straight-sided tet its corners
make, which is what a picture of the section needs.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

import numpy as np

MAGIC = b"FCSECT01"


@dataclass
class Section:
    """The section's triangles, three corners each."""

    positions: np.ndarray
    """(3t, 3) float32, mm."""
    values: np.ndarray | None
    """(3t,) float32: the field at each corner, when one was given."""
    vectors: np.ndarray | None
    """(3t, 3) float32: the displacement at each corner, when one was given."""
    edges: np.ndarray
    """(t,) uint8: bit k set when the edge opposite corner k is an element's edge."""

    @property
    def triangles(self) -> int:
        return len(self.edges)


def _polygons() -> dict[int, list[tuple[int, int]]]:
    """For each set of corners on the far side of the plane (a 4-bit mask, corner k as bit k), the
    tet edges the section crosses, in order round it."""
    out: dict[int, list[tuple[int, int]]] = {}
    for mask in range(1, 15):
        far = [c for c in range(4) if mask >> c & 1]
        near = [c for c in range(4) if not mask >> c & 1]
        if len(far) == 1 or len(near) == 1:
            lone, others = (far[0], near) if len(far) == 1 else (near[0], far)
            out[mask] = [(lone, o) for o in others]
        else:
            # Two a side: each crossing shares a face of the tet with the next, so this order runs
            # round the quadrilateral rather than across it.
            (a, b), (c, d) = far, near
            out[mask] = [(a, c), (a, d), (b, d), (b, c)]
    return out


POLYGONS = _polygons()

# Which edges of the two triangles a quadrilateral is drawn as are element edges: all but the
# diagonal they share. Bit k is the edge opposite the triangle's corner k.
TRIANGLE_EDGES = 0b111
FIRST_HALF_EDGES = 0b101
SECOND_HALF_EDGES = 0b011


def cut(
    nodes: np.ndarray,
    tets: np.ndarray,
    normal: np.ndarray | tuple[float, float, float],
    d: float,
    values: np.ndarray | None = None,
    vectors: np.ndarray | None = None,
) -> Section:
    """The section of ``tets`` (rows of node indices, corners first as TETRA4 and TETRA10 list them)
    by the plane ``normal . x = d``, with ``values`` (one per node) and ``vectors`` (three per node)
    interpolated onto it."""
    n = np.asarray(normal, float)
    n = n / np.linalg.norm(n)
    corners = np.asarray(tets)[:, :4]
    side = np.asarray(nodes, float) @ n - float(d)
    far = side[corners] > 0.0
    mask = far[:, 0] | far[:, 1] << 1 | far[:, 2] << 2 | far[:, 3] << 3

    positions, field, moved, edges = [], [], [], []
    for pattern, polygon in POLYGONS.items():
        which = np.flatnonzero(mask == pattern)
        if not len(which):
            continue
        points, point_values, point_vectors = [], [], []
        for i, j in polygon:
            a, b = corners[which, i], corners[which, j]
            t = (side[a] / (side[a] - side[b]))[:, None]
            points.append(nodes[a] + t * (nodes[b] - nodes[a]))
            if values is not None:
                point_values.append(values[a] + t[:, 0] * (values[b] - values[a]))
            if vectors is not None:
                point_vectors.append(vectors[a] + t * (vectors[b] - vectors[a]))
        halves = (
            [((0, 1, 2), TRIANGLE_EDGES)]
            if len(polygon) == 3
            else [((0, 1, 2), FIRST_HALF_EDGES), ((0, 2, 3), SECOND_HALF_EDGES)]
        )
        for triangle, mask_bits in halves:
            positions.append(np.stack([points[k] for k in triangle], axis=1))
            if values is not None:
                field.append(np.stack([point_values[k] for k in triangle], axis=1))
            if vectors is not None:
                moved.append(np.stack([point_vectors[k] for k in triangle], axis=1))
            edges.append(np.full(len(which), mask_bits, np.uint8))

    if not positions:
        return Section(
            positions=np.empty((0, 3), np.float32),
            values=None if values is None else np.empty(0, np.float32),
            vectors=None if vectors is None else np.empty((0, 3), np.float32),
            edges=np.empty(0, np.uint8),
        )
    return Section(
        positions=np.concatenate(positions).reshape(-1, 3).astype(np.float32),
        values=None if values is None else np.concatenate(field).reshape(-1).astype(np.float32),
        vectors=None
        if vectors is None
        else np.concatenate(moved).reshape(-1, 3).astype(np.float32),
        edges=np.concatenate(edges),
    )


def encode(section: Section) -> bytes:
    """The section as the interface reads it: a header, then the corners, the field and the
    displacement where there are any, and each triangle's element edges."""
    flags = (1 if section.values is not None else 0) | (2 if section.vectors is not None else 0)
    parts = [MAGIC, struct.pack("<II", section.triangles, flags), section.positions.tobytes()]
    if section.values is not None:
        parts.append(section.values.tobytes())
    if section.vectors is not None:
        parts.append(section.vectors.tobytes())
    parts.append(section.edges.tobytes())
    parts.append(b"\0" * (-section.triangles % 4))
    return b"".join(parts)
