"""Faces moved along their own normal - a wall, a plate or a boss made thicker or thinner - exactly,
in a window round them.

The field stores distance only a few cells out from the surface, so moving a face further than
that from the stored field would drag a clamped number. Here the part's distance is computed again,
exactly, from the tessellation, in a window round the faces moved - out as far as they move, their
blend and the band reach - and the move is one subtraction there::

    phi = part - offset * weight

``weight`` is one on the faces moved and nothing on the rest of the part, ramped between over the
block's blend (:func:`.offset.ramped`): a cell belongs to the faces moved by how much nearer it is
to them than to any other face, never through a wall to its far side. Both distances are exact -
to the triangles of the faces moved, and to those of every other face - and come from
:mod:`.distance`, on the GPU when there is one: the nearest-face question is asked of every cell in
the window, and the CPU and the GPU give it the same answer. Blocks that move faces near each other
move them together - the window of each sees every block's weight - so where a thickened floor
meets a thickened wall both move.

**The part's interfaces stay as they are.** Every cell within the clearance of a face the study
keeps closed - a bore, a hole - and nearer it than any face moved is given its base value back, so
a blend that would reach a bearing seat leaves it where it is, a check can prove it by comparing
cells, and a boss thickened round a bore meets the bore, which runs on through what was added.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field

import numpy as np

from ..features import FeatureSet
from ..geometry.brep import Tessellation
from ..spec import Offset
from .compose import Composition, _splice
from .distance import part_distance
from .field import Field, Grid
from .offset import ramped

# How many blocks of faces moved are kept, read off the part, for the designs that move them alike.
KEPT = 2


@dataclass
class Reach:
    """What one block of faces moved reads off the part, round its faces: the cells it moves -
    within the offset and the band of the surface - with their signed distance to the part; and the
    cells that belong to its faces at all, with how much, and how far each is from them. Cells as
    base-grid samples, ascending."""

    window: Grid
    moves: np.ndarray
    moves_local: np.ndarray
    """The same cells as ``moves``, as cells of ``window``."""
    part: np.ndarray
    owned: np.ndarray
    weight: np.ndarray
    near: np.ndarray


@dataclass
class Moved:
    """A design's faces moved: the field it leaves, which cells changed, and how far the surface
    was pushed out anywhere - for ribs filleted to it where it now is."""

    field: Field
    changed: np.ndarray
    blocks: list[tuple[Reach, float]] = field(default_factory=list)

    def shift(self, points: np.ndarray) -> np.ndarray:
        """How far the moved faces push the surface out at each point: every block's offset times
        how much the grid cell nearest the point belongs to its faces."""
        grid = self.field.grid
        index = np.rint(
            (np.asarray(points, dtype=float) - np.asarray(grid.origin)) / grid.spacing_mm
        )
        index = np.clip(index.astype(np.int64), 0, np.asarray(grid.shape) - 1)
        return self.shift_at(np.ravel_multi_index(tuple(index.T), grid.shape))

    def shift_at(self, samples: np.ndarray) -> np.ndarray:
        """The same, at samples of the grid."""
        total = np.zeros(len(samples))
        for reach, offset in self.blocks:
            total += offset * _looked_up(reach.owned, reach.weight, samples, 0.0)
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
    ``clearance_mm`` of ``protected_faces`` left as they were. ``patches`` keeps what each block
    reads off the part for the next design that moves the same faces as far."""
    spacing, reach = base.grid.spacing_mm, base.reach_mm
    kept: dict = patches if patches is not None else OrderedDict()
    every = {int(f) for f in np.unique(tess.face_id)}
    chosen: list[tuple[Reach, float]] = []
    for offset in offsets:
        if offset.offset_mm == 0.0:
            continue
        faces = tuple(sorted(moved_faces(features, [offset])))
        # Out from the surface, the distance is needed as far as a cell can move into the band -
        # the offset and the band's reach; across, as far again as the blend ramps.
        deep = abs(offset.offset_mm) + reach + spacing
        key = ("moved", base.key or id(base), faces, round(deep, 6), float(offset.blend_mm))
        if key not in kept:
            kept[key] = _reach_of(base, tess, set(faces), every, deep, offset.blend_mm)
            _trim(kept)
        chosen.append((kept[key], offset.offset_mm))
    moved = Moved(field=base, changed=np.empty(0, dtype=np.int64), blocks=chosen)
    if not chosen:
        return moved

    samples_all: list[np.ndarray] = []
    values_all: list[np.ndarray] = []
    for block, _ in chosen:
        samples = block.moves
        if not samples.size:
            continue
        shift = moved.shift_at(samples)
        value = block.part.astype(np.float64) - shift
        # Where nothing moves, the part is as the field holds it, bit for bit - not a cell changed.
        still = shift == 0.0
        value[still] = base.at(samples[still])
        if protected_faces:
            # Held as it was where a face kept closed is nearer than any face moved: the closed
            # face stays exactly where it is, and what is added beside it meets it, no groove.
            guard = part_distance(tess, block.window, clearance_mm, faces=protected_faces)
            guard = guard[block.moves_local]
            to_moved = np.full(len(samples), np.inf)
            for other, _ in chosen:
                to_moved = np.minimum(
                    to_moved, _looked_up(other.owned, other.near, samples, np.inf)
                )
            held = (guard < clearance_mm) & (guard < to_moved)
            value[held] = base.at(samples[held])
        samples_all.append(samples)
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


def _reach_of(
    base: Field, tess: Tessellation, faces: set[int], every: set[int], deep: float, blend: float
) -> Reach:
    """What a block of faces moved reads off the part: see :class:`Reach`. Both distances - to the
    faces moved and to the rest - are exact as far as a cell ``deep`` into the band can have its
    weight ramped: past that, both clamped, the cell belongs to nothing."""
    spacing = base.grid.spacing_mm
    reach = deep + max(blend, 0.0)
    mine = np.isin(tess.face_id, np.fromiter(faces, dtype=np.int64, count=len(faces)))
    corners = tess.vertices[np.unique(tess.triangles[mine])]
    grow = max(blend, 0.0) + deep + spacing
    window, first = _window(base.grid, corners.min(axis=0) - grow, corners.max(axis=0) + grow)
    near = part_distance(tess, window, reach, faces=faces)
    others = every - faces
    far = (
        part_distance(tess, window, reach, faces=others)
        if others
        else np.full(window.n_cells, reach, dtype=np.float32)
    )
    unsigned = np.minimum(near, far)
    within = np.flatnonzero(unsigned < reach)
    samples = _samples(window, first, base.grid, within)
    solid = base.inside.ravel()[samples]
    part = np.where(solid, -unsigned[within], unsigned[within]).astype(np.float32)
    moves = np.abs(part) < deep
    weight = ramped(near[within], far[within], blend).astype(np.float32)
    owned = weight > 0.0
    return Reach(
        window=window,
        moves=samples[moves],
        moves_local=within[moves],
        part=part[moves],
        owned=samples[owned],
        weight=weight[owned],
        near=near[within][owned].astype(np.float32),
    )


def _trim(kept: dict) -> None:
    """At most :data:`KEPT` blocks of faces moved kept: the oldest go first."""
    moved = [key for key in kept if isinstance(key, tuple) and key[:1] == ("moved",)]
    for key in moved[: max(0, len(moved) - KEPT)]:
        del kept[key]


def _looked_up(keys: np.ndarray, values: np.ndarray, wanted: np.ndarray, missing: float):
    """``values`` at ``wanted`` among the ascending ``keys``, ``missing`` where one is not there."""
    out = np.full(len(wanted), missing, dtype=np.float64)
    if not keys.size or not len(wanted):
        return out
    position = np.clip(np.searchsorted(keys, wanted), 0, keys.size - 1)
    found = keys[position] == wanted
    out[found] = values[position[found]]
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


def _samples(window: Grid, first: np.ndarray, grid: Grid, cells: np.ndarray) -> np.ndarray:
    """The flat index in ``grid`` of the given cells of ``window`` - ascending, as they are."""
    i, j, k = np.unravel_index(np.asarray(cells, dtype=np.int64), window.shape)
    return np.ravel_multi_index((i + first[0], j + first[1], k + first[2]), grid.shape).astype(
        np.int64
    )
