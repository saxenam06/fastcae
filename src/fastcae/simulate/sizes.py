"""Element sizes for a design's mesh: the deck mesh's own wherever the design leaves the part as it
was, and at least two elements through every rib the design adds.

The rules are the ones measured on design #7 (``bench/solvers/sizes.py``, ``RESULTS.md``): through a
rib or thin wall - metal thinner than :data:`RIB_MAX` along the inward normal - at least
:data:`THROUGH` elements; applied only within :data:`NEAR_CHANGE` of the cells the design changed;
no rule asks for less than :data:`SMALLEST`; a size grows by at most :data:`GROWTH` mm for every mm
away from where a rule sets it. Elsewhere the deck mesh's own sizes hold - the sizes the gate
showed the field route meets the CAD's answer at.

The field is read where it is asked about and nowhere else: it is a band over a sign, and a design's
changes spread over most of the part's box - a dense copy would cost a gigabyte to answer questions
about its ribs.
"""

from __future__ import annotations

import time

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from .tetmesh import SizeGrid

THROUGH = 2  # elements through a rib's thickness
RIB_MAX = 25.0  # mm: thinner metal is a rib or thin wall
PANEL = 40.0  # mm: the largest element any rule leaves
SMALLEST = 3.0  # mm: the smallest element any rule asks for
GROWTH = 1.0  # mm of size per mm of distance
NEAR_CHANGE = 6.0  # mm: the rules apply this close to a changed cell
REACH = 60.0  # mm: thickness is measured up to this; thicker metal is a panel
STRIDE = 2  # the size grid takes every STRIDE-th point of the field's grid


def _values(field, ijk: np.ndarray) -> np.ndarray:  # type: ignore[no-untyped-def]
    """The field at whole cells (n, 3), clamped to the grid."""
    shape = np.asarray(field.grid.shape)
    ijk = np.clip(ijk, 0, shape - 1)
    return field.at(np.ravel_multi_index(tuple(ijk.T), tuple(shape))).astype(np.float64)


def _sample(field, p: np.ndarray) -> np.ndarray:  # type: ignore[no-untyped-def]
    """The field at points, by trilinear interpolation between cells."""
    grid = field.grid
    u = (p - np.asarray(grid.origin)) / grid.spacing_mm
    i = np.clip(np.floor(u).astype(np.int64), 0, np.asarray(grid.shape) - 2)
    t = np.clip(u - i, 0.0, 1.0)
    out = np.zeros(len(p))
    for di in (0, 1):
        for dj in (0, 1):
            for dk in (0, 1):
                w = (t[:, 0] if di else 1 - t[:, 0]) * (t[:, 1] if dj else 1 - t[:, 1])
                w = w * (t[:, 2] if dk else 1 - t[:, 2])
                out += w * _values(field, i + np.array([di, dj, dk]))
    return out


def _surface_nodes(field) -> tuple[np.ndarray, np.ndarray]:  # type: ignore[no-untyped-def]
    """The size grid's nodes within one size-grid spacing of the surface - as field cells, with
    the field there - read off the band: nearer than the band's reach is always on it."""
    shape = tuple(int(n) for n in field.grid.shape)
    near = np.abs(field.band_mm) <= STRIDE * field.grid.spacing_mm
    ijk = np.column_stack(np.unravel_index(field.band_index[near], shape))
    on_grid = np.all(ijk % STRIDE == 0, axis=1) & np.all(
        (ijk >= 1) & (ijk <= np.asarray(shape) - 2), axis=1
    )
    return ijk[on_grid], field.band_mm[near][on_grid].astype(np.float64)


def _normals(field, ijk: np.ndarray) -> np.ndarray:  # type: ignore[no-untyped-def]
    """The field's unit gradient at cells, from central differences."""
    g = np.column_stack(
        [
            _values(field, ijk + e) - _values(field, ijk - e)
            for e in (np.array([1, 0, 0]), np.array([0, 1, 0]), np.array([0, 0, 1]))
        ]
    )
    return g / np.maximum(np.linalg.norm(g, axis=1), 1e-9)[:, None]


def _thickness(field, surface: np.ndarray, normal: np.ndarray) -> np.ndarray:  # type: ignore[no-untyped-def]
    """Metal along the inward normal from each surface point, to where the field turns positive
    again; REACH where it does not within REACH, or where the normal does not enter the metal."""
    step = field.grid.spacing_mm / 2
    t = np.full(len(surface), REACH)
    open_ = np.ones(len(surface), bool)
    entered = np.zeros(len(surface), bool)
    before = np.zeros(len(surface))
    for s in np.arange(step, REACH + step / 2, step):
        if not open_.any():
            break
        v = before.copy()
        v[open_] = _sample(field, surface[open_] - s * normal[open_])
        out = open_ & entered & (v >= 0)
        t[out] = s - step * v[out] / np.maximum(v[out] - before[out], 1e-9)
        open_ &= ~out
        entered |= v < 0
        before = v
    return t


def design_sizes(field, changed: np.ndarray, base: SizeGrid | None = None) -> tuple[SizeGrid, dict]:  # type: ignore[no-untyped-def]
    """The size map a design is meshed to: ``base`` - the deck mesh's sizes on the field's grid,
    :func:`~.tetmesh.sizes_from_mesh` - held everywhere, finer through the ribs near ``changed``
    (flat indices of the cells the design changed), graded at :data:`GROWTH`."""
    t0 = time.time()
    grid = field.grid
    spacing = float(grid.spacing_mm)
    origin = np.asarray(grid.origin, float)
    coarse_shape = tuple(int(n) for n in -(-np.asarray(grid.shape) // STRIDE))
    size = np.full(coarse_shape, PANEL, np.float32)
    if base is not None:
        if base.size.shape != coarse_shape or not np.allclose(base.origin, origin):
            raise ValueError("the base sizes are not on this field's size grid")
        size = np.minimum(size, base.size.astype(np.float32))
    ruled = 0
    if len(changed):
        ijk, value = _surface_nodes(field)
        at = origin + ijk * spacing
        # First by cell, generously, so normals and thickness are found only where they count.
        tree = cKDTree(grid.centres(np.asarray(changed)))
        far, _ = tree.query(at, distance_upper_bound=NEAR_CHANGE + STRIDE * spacing)
        keep = np.isfinite(far)
        ijk, value, at = ijk[keep], value[keep], at[keep]
        normal = _normals(field, ijk)
        surface = at - value[:, None] * normal
        far, _ = tree.query(surface, distance_upper_bound=NEAR_CHANGE)
        keep = np.isfinite(far)
        thick = _thickness(field, surface[keep], normal[keep])
        rib = thick <= RIB_MAX
        target = np.clip(thick[rib] / THROUGH, SMALLEST, PANEL).astype(np.float32)
        cells = ijk[keep][rib] // STRIDE
        np.minimum.at(size, tuple(cells.T), target)
        ruled = int(rib.sum())
    offsets = np.indices((3, 3, 3)).reshape(3, -1).T - 1
    rise = (GROWTH * STRIDE * spacing * np.linalg.norm(offsets, axis=1)).reshape(3, 3, 3)
    for _ in range(int(np.ceil((PANEL - SMALLEST) / (GROWTH * STRIDE * spacing)))):
        size = ndimage.grey_erosion(size, structure=-rise)
    info = {
        "rules": {
            "through": THROUGH,
            "rib_max_mm": RIB_MAX,
            "panel_mm": PANEL,
            "smallest_mm": SMALLEST,
            "growth": GROWTH,
            "near_change_mm": NEAR_CHANGE,
        },
        "set_by_ribs": ruled,
        "changed_cells": int(len(changed)),
        "smallest_mm": float(size.min()),
        "seconds": time.time() - t0,
    }
    return SizeGrid(size=size, origin=origin, spacing=float(STRIDE * spacing)), info
