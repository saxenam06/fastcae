"""A derived design space measured against a finished design of the same part.

When a part exists both without and with its ribs - a baseline and the design that went into
production - the ribs are the one piece of evidence about the design space that no rule wrote. Every
rib cell of the finished part should fall where the space allows metal. How much does, where the
rest falls and why, and how big the space is beside the ribs, are the numbers this reports.

The grid's own resolution is part of the answer: a rib's outermost layer of cells is half in, half
out wherever its faces fall between cell centres, so coverage is also given without that layer.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import ndimage

from ..generate.field import Grid, build_field
from ..geometry.brep import Tessellation
from .model import LABEL_WORDS, Label

NOISE_CELLS = 30
"""Pieces of difference smaller than this are two exports of one surface disagreeing, not ribs."""


def compare(
    grid: Grid, labels: np.ndarray, finished: Tessellation, benefit: np.ndarray | None = None
) -> tuple[dict[str, Any], np.ndarray]:
    """Where the finished design's added metal falls in the space. Returns the report and the rib
    cells, labelled by piece (0 = not a rib)."""
    other = build_field(finished, grid=grid).inside
    part = labels == Label.PART
    added = other & ~part
    removed = part & ~other
    pieces, count = ndimage.label(added)
    sizes = np.bincount(pieces.ravel(), minlength=count + 1)
    keep = sizes >= NOISE_CELLS
    keep[0] = False
    pieces = np.where(keep[pieces], pieces, 0)
    rib = pieces > 0
    h = grid.spacing_mm
    cell_cm3 = h**3 / 1000.0

    # The outermost layer of each rib: cells with a neighbour that is neither rib nor part.
    solid = rib | part
    skin = rib & ~ndimage.binary_erosion(
        solid, structure=ndimage.generate_binary_structure(3, 1), border_value=0
    )
    core = rib & ~skin

    def shares(mask: np.ndarray) -> dict[str, float]:
        counts = np.bincount(labels[mask], minlength=len(Label))
        total = max(int(mask.sum()), 1)
        return {
            LABEL_WORDS[Label(i)]: round(float(c) / total, 4) for i, c in enumerate(counts) if c
        }

    admissible = labels == Label.ADMISSIBLE
    report: dict[str, Any] = {
        "rib_cm3": round(float(rib.sum()) * cell_cm3, 1),
        "rib_pieces": int(len(np.unique(pieces)) - 1),
        "noise_cm3": round(float((added & ~rib).sum()) * cell_cm3, 1),
        "baseline_not_in_finished_cm3": round(float(removed.sum()) * cell_cm3, 1),
        "skin_share": round(float(skin.sum()) / max(float(rib.sum()), 1.0), 3),
        "rib_by_label": shares(rib),
        "core_by_label": shares(core),
        "covered": round(float((rib & admissible).sum()) / max(float(rib.sum()), 1.0), 4),
        "covered_core": round(float((core & admissible).sum()) / max(float(core.sum()), 1.0), 4),
        "covered_or_unknown": round(
            float((rib & (admissible | (labels == Label.UNKNOWN))).sum())
            / max(float(rib.sum()), 1.0),
            4,
        ),
        "space_to_rib": round(float(admissible.sum()) / max(float(rib.sum()), 1.0), 2),
    }
    if benefit is not None:
        high = (
            benefit >= np.percentile(benefit[admissible], 75)
            if admissible.any()
            else np.zeros_like(admissible)
        )
        report["rib_in_top_quarter_benefit"] = round(
            float((rib & high).sum()) / max(float(rib.sum()), 1.0), 4
        )

    per_piece = []
    index = np.arange(1, pieces.max() + 1)
    counts = ndimage.sum_labels(np.ones_like(pieces), pieces, index)
    covered = ndimage.sum_labels(admissible, pieces, index)
    centres = ndimage.center_of_mass(rib, pieces, index)
    for label_id, n, c, centre in zip(index, counts, covered, centres, strict=True):
        if n == 0:
            continue
        cells = labels[pieces == label_id]
        blocking = np.bincount(cells[cells != Label.ADMISSIBLE], minlength=len(Label))
        top = int(np.argmax(blocking)) if blocking.any() else None
        per_piece.append(
            {
                "piece": int(label_id),
                "cm3": round(float(n) * cell_cm3, 1),
                "covered": round(float(c) / float(n), 3),
                "mostly_blocked_by": LABEL_WORDS[Label(top)] if top is not None else None,
                "centre_mm": [
                    round(float(v) * h + o, 1) for v, o in zip(centre, grid.origin, strict=True)
                ],
            }
        )
    per_piece.sort(key=lambda p: -p["cm3"])
    report["pieces"] = per_piece
    return report, pieces.astype(np.int32)
