"""Normals for a contoured surface, so it can be looked at rather than merely measured.

A surface out of a field has no CAD faces of its own. The face ids it carries are borrowed from the
nearest face of the original, which is exactly right for picking and exactly wrong for shading:
neighbouring triangles land on different faces, every one of those boundaries becomes a shading
seam, and a smooth casting comes back looking crazed. That is a rendering artefact, and comparing
it against a B-rep tessellation shaded properly is comparing two different things.

So normals are averaged across the surface itself, and split only where the surface genuinely
creases. A machined edge stays an edge; a cast wall reads as smooth if it is smooth, and as bumpy
if the voxel size made it bumpy - which is the comparison worth being able to make.

Deliberately not part of what a stored contour depends on. How a surface is lit cannot change what
it is, so changing this must not throw away half an hour of contouring.
"""

from __future__ import annotations

import math

import numpy as np

# Below this angle between a triangle and its vertex's average, the two are the same surface.
#
# Forty degrees sits above the turn between adjacent facets on anything the voxel size resolves,
# and below the shallowest angle anyone would call a machined edge. The same threshold the
# selection tools grow across, for the same reason.
CREASE_DEG = 40.0


def corner_normals(
    vertices: np.ndarray,
    triangles: np.ndarray,
    crease_deg: float = CREASE_DEG,
) -> np.ndarray:
    """A normal per triangle corner: averaged where the surface is smooth, flat where it creases.

    Returns ``(3 * n_triangles, 3)``, in the order the corners are written to the wire - one per
    un-welded vertex, because WebGL has no primitive id and the face id has to travel per vertex
    anyway.
    """
    a = vertices[triangles[:, 0]]
    b = vertices[triangles[:, 1]]
    c = vertices[triangles[:, 2]]

    # Unnormalised, so the accumulation is area-weighted: a large triangle should have more say
    # about the shape of the surface than a sliver at the same vertex.
    face = np.cross(b - a, c - a)

    accumulated = np.zeros(vertices.shape, dtype=np.float64)
    for corner in range(3):
        for axis in range(3):
            accumulated[:, axis] += np.bincount(
                triangles[:, corner], weights=face[:, axis], minlength=vertices.shape[0]
            )
    smooth = _normalise(accumulated)
    flat = _normalise(face)

    # A corner takes the averaged normal unless its own triangle disagrees with it, which is what a
    # crease looks like from the inside: the average there is the mean of two surfaces and belongs
    # to neither.
    limit = math.cos(math.radians(crease_deg))
    at_corner = smooth[triangles]  # (m, 3, 3)
    agrees = np.einsum("mcj,mj->mc", at_corner, flat) >= limit
    chosen = np.where(agrees[:, :, None], at_corner, flat[:, None, :])
    return chosen.reshape(-1, 3)


def _normalise(vectors: np.ndarray) -> np.ndarray:
    length = np.linalg.norm(vectors, axis=1, keepdims=True)
    return np.divide(vectors, length, out=np.zeros_like(vectors), where=length > 1e-12)
