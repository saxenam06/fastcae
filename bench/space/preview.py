"""The physics preview of a derived design space: one solve, the benefit of metal at every allowed
cell.

    python preview.py GRC_Gearbox_Housing <space.npz>

Writes ``<space>_benefit.npz`` and ``<space>_benefit.json`` beside the space.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from fastcae import extract
from fastcae.generate.field import Grid
from fastcae.project import open_project
from fastcae.simulate import baseline as solver_deck
from fastcae.space.physics import preview


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("space", type=Path)
    parser.add_argument("--factor", type=int, default=2)
    args = parser.parse_args()

    project = open_project(args.project)
    extraction = extract.run(project)
    deck = solver_deck.read_deck(project)
    data = np.load(args.space)
    grid = Grid(
        origin=tuple(float(v) for v in data["origin"]),
        spacing_mm=float(data["spacing"]),
        shape=tuple(int(v) for v in data["shape"]),
    )
    result = preview(grid, data["labels"], extraction.tess, extraction.anchoring, deck.setup, args.factor)
    out = args.space.with_name(args.space.stem + "_benefit")
    np.savez_compressed(out.with_suffix(".npz"), benefit=result["benefit"])
    b = result["benefit"]
    allowed = b[data["labels"] == 9]
    result["stats"]["benefit_percentiles"] = (
        {q: float(np.percentile(allowed, q)) for q in (25, 50, 75, 95, 99)} if len(allowed) else {}
    )
    out.with_suffix(".json").write_text(json.dumps(result["stats"], indent=1), encoding="utf-8")
    print(json.dumps(result["stats"], indent=1))


if __name__ == "__main__":
    main()
