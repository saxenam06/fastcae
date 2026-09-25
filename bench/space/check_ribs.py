"""Measure a derived design space against the production part's real ribs.

    python check_ribs.py <space.npz> <finished.step> [--benefit benefit.npz]

Writes ``<space>_ribs.json`` and ``<space>_ribs.npz`` (the rib cells, by piece) beside the space.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from fastcae.geometry import check, exact_properties, load_cad, tessellate
from fastcae.geometry.field import Grid
from fastcae.space.check import compare


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("space", type=Path)
    parser.add_argument("finished", type=Path)
    parser.add_argument("--benefit", type=Path)
    args = parser.parse_args()

    data = np.load(args.space)
    grid = Grid(
        origin=tuple(float(v) for v in data["origin"]),
        spacing_mm=float(data["spacing"]),
        shape=tuple(int(v) for v in data["shape"]),
    )
    labels = data["labels"]
    t0 = time.perf_counter()
    shape, notes = load_cad(args.finished)
    tess = tessellate(shape)
    health = check(tess, exact_properties(shape))
    print(
        f"finished part: {tess.n_triangles:,} triangles, watertight {health.watertight} "
        f"({time.perf_counter() - t0:.0f} s); {notes[:3]}"
    )
    benefit = None
    if args.benefit:
        benefit = np.load(args.benefit)["benefit"]
    report, pieces = compare(grid, labels, tess, benefit)
    report["seconds"] = round(time.perf_counter() - t0, 1)
    out = args.space.with_name(args.space.stem + "_ribs")
    out.with_suffix(".json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    np.savez_compressed(out.with_suffix(".npz"), pieces=pieces)
    print(json.dumps({k: v for k, v in report.items() if k != "pieces"}, indent=1))
    for p in report["pieces"][:25]:
        print(
            f"  piece {p['piece']:3d}: {p['cm3']:8.1f} cm3  covered {p['covered']:.0%}  "
            f"blocked by {p['mostly_blocked_by']}  at {p['centre_mm']}"
        )


if __name__ == "__main__":
    main()
