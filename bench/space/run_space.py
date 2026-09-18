"""Derive a project's design space and keep the result beside the run.

    python run_space.py GRC_Gearbox_Housing --spacing 4 --out <dir> [--no-deck]

Run from a folder holding its own ``assets/<project>`` copy: the derivation builds a field of the
part, and the project's cache is written where the project is.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from fastcae import extract
from fastcae.project import open_project
from fastcae.simulate import baseline as solver_deck
from fastcae.space import Params, derive
from fastcae.space.derive import save


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("--spacing", type=float, default=4.0)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-deck", action="store_true")
    parser.add_argument("--no-drawing", action="store_true")
    parser.add_argument("--inside", action="store_true")
    parser.add_argument("--pocket-reach", type=float, default=4.0)
    parser.add_argument("--layer", type=float, default=3.0)
    args = parser.parse_args()

    project = open_project(args.project)
    extraction = extract.run(project)
    deck = solver_deck.read_deck(project) if not args.no_deck else None
    params = Params(
        spacing_mm=args.spacing,
        use_deck=not args.no_deck,
        use_drawing=not args.no_drawing,
        inside=args.inside,
        pocket_reach=args.pocket_reach,
        panel_layer=args.layer,
        inside_layer=args.layer,
    )
    started = time.perf_counter()
    space = derive(extraction, setup=deck.setup if deck else None, params=params, root=project.root)
    print(f"derived in {time.perf_counter() - started:.1f} s")
    args.out.mkdir(parents=True, exist_ok=True)
    name = (
        f"space_{args.spacing:g}mm"
        + ("_nodeck" if args.no_deck else "")
        + ("_inside" if args.inside else "")
        + (f"_c{args.pocket_reach:g}" if args.pocket_reach != 4.0 else "")
        + (f"_k{args.layer:g}" if args.layer != 3.0 else "")
    )
    save(space, args.out / name)
    summary = space.summary()
    print(json.dumps({k: summary[k] for k in ("volumes_cm3", "stats")}, indent=1, default=str)[:6000])
    for q in space.questions[:40]:
        print(f"  ? {q.text}  [{q.detail[:90]}]")
    frozen = [i for i in space.interfaces if i.frozen]
    print(f"{len(frozen)} frozen interfaces:")
    for i in frozen:
        kinds = sorted({e["kind"] for e in i.evidence})
        print(
            f"  {i.id:10s} faces {i.faces[:6]}{'...' if len(i.faces) > 6 else ''} "
            f"{', '.join(kinds)}  t={i.thickness_mm}"
        )


if __name__ == "__main__":
    main()
