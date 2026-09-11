"""The wire format a surface reaches the browser in.

Its own module because it is neither a route nor engine work: nothing here decides anything about
the geometry, it only decides how many bytes saying so takes.

**Indexed, and welded by normal.** A surface contoured out of a field has one vertex per cell and
about two triangles using it, so sending three separate corners per triangle says everything three
times: 10.8 million vertices for the 1.8 million a 2.5 mm field actually has, and 303 MB for what
fits in 80. Vertices are therefore shared - but only where they can be, which means where they
agree about which way the surface faces. A machined edge has two normals at one point and needs two
vertices; a smooth wall needs one. Welding on position alone rounds every edge off, and not welding
at all costs four times the bytes for the same picture.

**Normals as bytes.** A unit vector in three signed bytes is accurate to about half a degree, which
is far below what shading shows and a third of what three floats cost.

Un-indexed corners were also load-bearing for one thing: WebGL2 has no primitive id in a fragment
shader, so the CAD face id has to arrive as a vertex attribute. Welding by normal keeps that
working, because two triangles that share a vertex and a normal are on the same surface and want
the same face id - and where they do not, the normal has already split them.
"""

from __future__ import annotations

import struct

import numpy as np

MAGIC = b"FCMESH03"

# Room for the vertex index in the packed weld key, leaving the low bits for the normal. Twenty-one
# bits would hold the 1.8 M vertices a 2.5 mm field of the part in assets/ contours to; forty is
# past any grid that fits in memory.
_INDEX_SHIFT = 24


def encode(
    vertices: np.ndarray,
    triangles: np.ndarray,
    face_id: np.ndarray,
    normals: np.ndarray | None = None,
) -> bytes:
    """Pack a triangle surface for the renderer.

    ``normals`` is one per triangle corner, in the order ``triangles.ravel()``. Given none, they
    are averaged **within a CAD face**, which is what keeps a machined edge on the B-rep sharp. A
    contour passes its own, because the face ids it carries are borrowed for picking and would
    shatter the shading into thousands of patches.
    """
    corners = triangles.ravel().astype(np.int64)
    if normals is None:
        normals = face_smoothed_normals(vertices, triangles, face_id)

    quantised = np.rint(np.clip(normals, -1.0, 1.0) * 127.0).astype(np.int8)
    packed = (corners << _INDEX_SHIFT) | (
        ((quantised[:, 0].astype(np.int64) + 128) << 16)
        | ((quantised[:, 1].astype(np.int64) + 128) << 8)
        | (quantised[:, 2].astype(np.int64) + 128)
    )

    _, first, index = np.unique(packed, return_index=True, return_inverse=True)
    index = index.reshape(-1).astype(np.uint32)

    positions = vertices[corners[first]].astype("<f4")
    shared_normals = np.zeros((first.size, 4), dtype=np.int8)
    shared_normals[:, :3] = quantised[first]
    ids = np.repeat(face_id, 3)[first].astype("<u4")

    return b"".join(
        [
            MAGIC,
            struct.pack("<II", first.size, triangles.shape[0]),
            positions.tobytes(),
            shared_normals.tobytes(),
            ids.tobytes(),
            index.astype("<u4").tobytes(),
        ]
    )


def face_smoothed_normals(
    vertices: np.ndarray, triangles: np.ndarray, face_id: np.ndarray
) -> np.ndarray:
    """A normal per corner, averaged within a CAD face.

    What keeps a bore shading smoothly while the chamfer beside it keeps its edge: the face
    boundary is the crease, and the B-rep already knows where those are, so nothing here has to
    guess at an angle.
    """
    a, b, c = vertices[triangles[:, 0]], vertices[triangles[:, 1]], vertices[triangles[:, 2]]
    face = np.cross(b - a, c - a)

    # Grouped through one integer rather than a pair of columns: grouping on two columns is a
    # lexsort, and eleven million rows of it is seconds rather than a fraction of one.
    stride = int(face_id.max()) + 1 if face_id.size else 1
    keys = triangles.ravel().astype(np.int64) * stride + np.repeat(face_id, 3).astype(np.int64)
    _, group, counts = np.unique(keys, return_inverse=True, return_counts=True)

    accumulated = np.zeros((counts.size, 3), dtype=np.float64)
    np.add.at(accumulated, group, np.repeat(face, 3, axis=0))
    length = np.linalg.norm(accumulated, axis=1, keepdims=True)
    return np.divide(accumulated, length, out=np.zeros_like(accumulated), where=length > 1e-12)[
        group
    ]
