"""The command line: build a seeded list of designs and write down what came of each.

    fastcae designs GRC_Gearbox_Housing --per-formation 16 --seed 0

Every formation is sampled the same number of times, so a later comparison between formations is a
fair one. Within a formation the values come from a seeded Latin hypercube: each lever's range is
cut into as many equal bands as there are designs and each band is used exactly once, so no lever
is left unexplored. Values snap to their levers' steps; a duplicate that snapping makes is built
once. Each design uses the same formation and values in every approved zone.

Not a Sobol sequence, which the plan named: SciPy's quasi-random module sits behind a native library
that this machine's Windows Application Control policy refuses to load.

What is written is the settings - the only thing a design is - and a summary row per design. The
geometry is derived and rebuilds from the settings byte for byte.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

from . import extract
from .generate.designs import DesignSpace
from .generate.formations import FORMATIONS
from .project import open_project


def sample(per_formation: int, seed: int) -> list[dict]:
    """Lever values for every formation: ``per_formation`` each, seeded, snapped to their steps."""
    chosen = []
    for index, formation in enumerate(FORMATIONS.values()):
        levers = formation.levers
        points = _latin_hypercube(per_formation, len(levers), seed * 1000 + index)
        for point in points:
            values = {}
            for lever, u in zip(levers, point, strict=True):
                if lever.integer:
                    span = int(lever.high - lever.low) + 1
                    value = min(lever.low + int(np.floor(u * span)), lever.high)
                else:
                    value = lever.snap(lever.low + u * (lever.high - lever.low))
                    value = min(max(value, lever.low), lever.high)
                values[lever.name] = lever.snap(value)
            chosen.append({"formation": formation.name, **values})
    return chosen


def _latin_hypercube(count: int, dimensions: int, seed: int) -> np.ndarray:
    """``count`` points in the unit cube, one in each of ``count`` equal bands of every axis."""
    rng = np.random.default_rng(seed)
    bands = np.stack([rng.permutation(count) for _ in range(dimensions)], axis=1)
    return (bands + rng.random((count, dimensions))) / count


def run_batch(space: DesignSpace, per_formation: int, seed: int, out: Path) -> list[dict]:
    """Build every sampled design in ``space``, and write the settings and a summary table."""
    out.mkdir(parents=True, exist_ok=True)
    rows, listed, seen = [], [], set()
    for chosen in sample(per_formation, seed):
        settings = {zone.id: dict(chosen) for zone in space.zones}
        digest = space.digest(settings)
        if digest in seen:
            continue
        seen.add(digest)
        started = time.perf_counter()
        made = space.generate(settings)
        stats = made.stats
        failing = [f"{f.check}: {f.reason}" for f in made.findings if f.outcome != "pass"]
        rows.append(
            {
                "digest": made.digest,
                "formation": chosen["formation"],
                "levers": json.dumps({k: v for k, v in chosen.items() if k != "formation"}),
                "outcome": made.outcome,
                "ribs": stats["ribs"],
                "dropped": stats["dropped"],
                "added_cm3": round(stats["added_cm3"], 1),
                "mass_kg": None if stats["mass_kg"] is None else round(stats["mass_kg"], 2),
                "smallest_fillet_mm": stats["smallest_fillet_mm"],
                "seconds": round(time.perf_counter() - started, 2),
                "not_passing": " | ".join(failing),
            }
        )
        listed.append({"digest": made.digest, "settings": settings})

    with (out / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["digest"])
        writer.writeheader()
        writer.writerows(rows)
    (out / "settings.json").write_text(json.dumps(listed, indent=2), encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fastcae")
    commands = parser.add_subparsers(dest="command", required=True)
    batch = commands.add_parser("designs", help="build a seeded list of designs")
    batch.add_argument("project", help="project folder name under assets/, or a path")
    batch.add_argument("--per-formation", type=int, default=16)
    batch.add_argument("--seed", type=int, default=0)
    batch.add_argument(
        "--spacing", type=float, default=None, help="grid spacing, mm (default: root fillet / 4)"
    )
    batch.add_argument(
        "--out", type=Path, default=None, help="where to write; the project's designs/"
    )
    args = parser.parse_args(argv)

    project = open_project(args.project)
    result = extract.run(project)
    space = DesignSpace.open(project, result, spacing_mm=args.spacing)
    if not space.zones:
        parser.error("no zone is approved in this project; approve one in the Generate tab first")
    out = args.out or project.root / "designs" / f"seed-{args.seed}"
    rows = run_batch(space, args.per_formation, args.seed, out)
    outcomes = {o: sum(r["outcome"] == o for r in rows) for o in ("pass", "warn", "reject")}
    print(f"{len(rows)} designs written to {out}: {outcomes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
