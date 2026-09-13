"""Faces moved along their own normal - a wall, a plate or a boss made thicker or thinner - exactly,
in a window round them.

The field stores distance only a few cells out from the surface, so moving a face further than
that from the stored field would drag a clamped number. Here the part's distance is computed again,
exactly, from the tessellation, in a window round the faces moved - out as far as they move, their
blend and the band reach - and the move is one subtraction there::

    phi = part - offset * weight

``weight`` is one on the faces moved and nothing on the rest of the part, ramped between over the
block's blend (:func:`.offset.weight`): nearer the faces moved than any other face, never through a
wall to its far side. Blocks that move faces near each other move them together - the window of
each sees every block's weight - so where a thickened floor meets a thickened wall both move.

**The part's interfaces stay as they are.** Every cell within the clearance of a face the study
keeps closed - a bore, a hole - and nearer it than any face moved is given its base value back, so
a blend that would reach a bearing seat leaves it where it is, a check can prove it by comparing
cells, and a boss thickened round a bore meets the bore, which runs on through what was added.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..features import FeatureSet
from ..geometry.brep import Tessellation
from ..spec import Offset
from .compose import Composition, _part_distance, _splice
from .field import Field, Grid
from .offset import Patch, patch_from, weight


@dataclass
class Moved:
    """A design's faces moved: the field it leaves, which cells changed, and how far the surface
    was pushed out anywhere - for ribs filleted to it where it now is."""

    field: Field
    changed: np.ndarray
    patches: list[tuple[Patch, float, float]] = field(default_factory=list)

    def shift(self, points: np.ndarray) -> np.ndarray:
        """How far the moved faces push the surface out at each point: every block's offset times
        how much the point belongs to its faces."""
        total = np.zeros(len(points))
        for patch, offset, blend in self.patches:
            lo, hi = patch.bounds(abs(offset) + blend + 1.0)
            near = np.all((points >= lo) & (points <= hi), axis=1)
            if near.any():
                total[near] += offset * weight(patch, points[near], blend)
        return total


def move_faces(
    base: Field,
    tess: Tessellation,
    features: FeatureSet,
    offsets: list[Offset],
    protected_faces: set[int] | None = None,
    clearance_mm: float = 0.0,
    patches: dict | None = None,
) -> Moved:
    """``base`` with every block of ``offsets`` moving its faces, exactly, and the cells within
    ``clearance_mm`` of ``protected_faces`` left as they were. ``patches`` keeps each block's
    sampled faces for the next design that moves the same ones."""
    spacing, reach = base.grid.spacing_mm, base.reach_mm
    kept = patches if patches is not None else {}
    chosen: list[tuple[Patch, float, float]] = []
    for offset in offsets:
        if offset.offset_mm == 0.0:
            continue
        faces = tuple(sorted(moved_faces(features, [offset])))
        key = (faces, spacing)
        if key not in kept:
            kept[key] = patch_from(tess, set(faces), spacing / 2.0)
        chosen.append((kept[key], offset.offset_mm, offset.blend_mm))
    moved = Moved(field=base, changed=np.empty(0, dtype=np.int64), patches=chosen)
    if not chosen:
        return moved

    samples_all: list[np.ndarray] = []
    values_all: list[np.ndarray] = []
    for patch, offset, blend in chosen:
        # Across, the window reaches past the faces as far as their blend; out from the surface,
        # the distance is needed only as far as a cell can move into the band - the offset and the
        # band's reach - which is what the exact scan costs by.
        deep = abs(offset) + reach + spacing
        lo, hi = patch.bounds(blend + deep + spacing)
        window, first = _window(base.grid, lo, hi)
        unsigned = _part_distance(tess, window, deep)
        samples = _samples(window, first, base.grid)
        solid = base.inside.ravel()[samples]
        part = np.where(solid, -unsigned, unsigned)
        # Only cells the move can reach: within the offset and the band of the surface.
        near = np.flatnonzero(np.abs(part) < deep)
        if not near.size:
            continue
        points = window.centres(near)
        value = part[near] - moved.shift(points)
        if protected_faces:
            # Held as it was where a face kept closed is nearer than any face moved: the closed
            # face stays exactly where it is, and what is added beside it meets it, no groove.
            guard = _part_distance(tess, window, clearance_mm, faces=protected_faces)[near]
            to_moved = np.min(
                [p.inside.query(points, k=1, workers=-1)[0] for p, _, _ in chosen], axis=0
            )
            held = (guard < clearance_mm) & (guard < to_moved)
            value[held] = base.at(samples[near][held])
        samples_all.append(samples[near])
        values_all.append(value)
    if not samples_all:
        return moved
    samples = np.concatenate(samples_all)
    values = np.concatenate(values_all)
    # Windows that overlap see every block's weight, so a cell in two has one value: keep one.
    samples, first_seen = np.unique(samples, return_index=True)
    values = values[first_seen]
    spliced: Composition = _splice(base, samples, values.astype(np.float32), np.signbit(values))
    moved.field, moved.changed = spliced.field, spliced.changed
    return moved


def moved_faces(features: FeatureSet, offsets: list[Offset]) -> set[int]:
    """Every face the blocks move."""
    out: set[int] = set()
    for offset in offsets:
        for ref in offset.faces:
            feature = features.get(ref)
            if feature is not None:
                out |= set(feature.face_ids)
    return out


def _window(grid: Grid, lo: np.ndarray, hi: np.ndarray) -> tuple[Grid, np.ndarray]:
    """The stretch of ``grid`` over the box ``lo`` to ``hi``, snapped to its lattice, and where
    it starts in it."""
    origin = np.asarray(grid.origin)
    last_index = np.asarray(grid.shape) - 1
    first = np.clip(np.floor((lo - origin) / grid.spacing_mm).astype(int), 0, last_index)
    last = np.clip(np.ceil((hi - origin) / grid.spacing_mm).astype(int), 0, last_index)
    window = Grid(
        origin=tuple(float(v) for v in origin + first * grid.spacing_mm),
        spacing_mm=grid.spacing_mm,
        shape=tuple(int(v) for v in last - first + 1),
    )
    return window, first


def _samples(window: Grid, first: np.ndarray, grid: Grid) -> np.ndarray:
    """The flat index in ``grid`` of every cell of ``window``, in the window's order."""
    i, j, k = np.unravel_index(np.arange(window.n_cells, dtype=np.int64), window.shape)
    return np.ravel_multi_index((i + first[0], j + first[1], k + first[2]), grid.shape).astype(
        np.int64
    )
