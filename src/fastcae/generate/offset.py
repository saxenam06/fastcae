"""Which part of the surface a face selection is asking to move.

This is the piece that makes a design edit *B-rep based and still fully implicit*. The selection is
made on the CAD - real faces, picked by a person or grown from one - and it arrives here as a set of
face ids. What leaves is a number per cell saying how much that cell belongs to the selection. The
edit itself is then a field operation, so nothing is ever cut, healed or re-meshed.

The alternative, and what the first rib did, is to infer a *shape* from the selection - a footprint,
a longest direction, a slab - and union that in. That guesses. Pick a panel and it stands a thin
wall on one edge of it, because a slab is what it knows how to build. A mask does not guess: the
faces you picked are the faces that move.

The weight is smooth on purpose. Where it falls from one to zero the surface ramps between offset
and untouched, and that ramp *is* the blend at the edge of the patch - not a fillet anybody
constructs, just what a smooth transition leaves behind.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .surface import scatter


@dataclass(frozen=True)
class Patch:
    """A face selection, sampled densely enough that distance to it can be measured.

    Two point sets rather than one: the faces that were picked, and the whole rest of the surface.
    A cell belongs to the selection when it is nearer the first than the second, which is a question
    that stays answerable on a curved face, around a corner, and across a selection in several
    pieces - none of which a footprint-and-direction description survives.
    """

    face_ids: tuple[int, ...]
    inside: object
    """kd-tree over sample points on the selected faces."""
    outside: object
    """kd-tree over sample points on every other face. Empty only if the whole part was selected."""
    low: np.ndarray
    high: np.ndarray
    """Bounds of the selected faces, before any offset."""

    def bounds(self, margin_mm: float) -> tuple[np.ndarray, np.ndarray]:
        return self.low - margin_mm, self.high + margin_mm


def patch_from(source: object, face_ids: set[int] | tuple[int, ...], spacing_mm: float) -> Patch:
    """Sample a tessellation and split it into the faces that were picked and the rest.

    Sampled rather than taken at the triangles: a CAD tessellation is adaptive, so a large flat face
    may be two enormous triangles, and asking "which face is nearest" against triangle centroids
    answers with whichever neighbour happens to be finely divided. Sampling evens that out.
    """
    from scipy.spatial import cKDTree

    wanted = {int(f) for f in face_ids}
    if not wanted:
        raise ValueError("a face offset needs at least one face")

    vertices = np.asarray(source.vertices)  # type: ignore[attr-defined]
    triangles = np.asarray(source.triangles)  # type: ignore[attr-defined]
    face_id = np.asarray(source.face_id)  # type: ignore[attr-defined]

    points, owner = scatter(vertices, triangles, face_id, spacing_mm)
    mine = np.isin(owner, np.fromiter(wanted, dtype=owner.dtype, count=len(wanted)))
    if not mine.any():
        raise ValueError("that selection has no surface on it")
    if mine.all():
        raise ValueError("the whole part was selected - an offset needs something to blend into")

    chosen = points[mine]
    return Patch(
        face_ids=tuple(sorted(wanted)),
        inside=cKDTree(chosen),
        outside=cKDTree(points[~mine]),
        low=chosen.min(axis=0),
        high=chosen.max(axis=0),
    )


def weight(patch: Patch, points: np.ndarray, ramp_mm: float) -> np.ndarray:
    """How much each point belongs to the selection: one on it, zero off it, ramped between.

    The comparison is between two distances - to the selection and to everything else - rather than
    against a fixed radius. A fixed radius would reach across a thin wall and move the far side of
    it too; nearer-of-the-two cannot, because the far side has its own surface closer to it.

    ``ramp_mm`` is the width of the transition, and so the radius of the blend where the offset
    region meets the untouched one. At zero the mask is a step and the join is a sharp edge.
    """
    near, _ = patch.inside.query(points, k=1, workers=-1)  # type: ignore[attr-defined]
    far, _ = patch.outside.query(points, k=1, workers=-1)  # type: ignore[attr-defined]
    return ramped(near, far, ramp_mm)


def ramped(near: np.ndarray, far: np.ndarray, ramp_mm: float) -> np.ndarray:
    """How much points belong to a selection, from their distance to it and to everything else."""
    near = np.asarray(near, dtype=np.float64)
    far = np.asarray(far, dtype=np.float64)
    if ramp_mm <= 0.0:
        return (near <= far).astype(np.float64)

    # Smoothstep on the signed difference, so the mask is flat at both ends and has no crease where
    # it arrives at one or leaves zero - a kink there would print itself onto the surface.
    t = np.clip(0.5 + 0.5 * (far - near) / ramp_mm, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)
