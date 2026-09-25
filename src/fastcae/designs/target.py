"""The target: the design the engineer holds up as the one to beat - for a housing, the production
casting - kept beside the part and measured exactly as every design is measured.

It is an input, like the CAD and the deck: the engineer hands over its CAD, and it is meshed face
by face as C3D10, the deck's own groups carried onto it by the CAD faces it shares with the part,
the deck's loads and supports unchanged, and solved by cuDSS - the route every design takes, so a
design read beside it is read like for like. What it adds to the part (its metal) is the budget a
design is held to when the comparison is to be fair.

Kept in ``<project>/target/``: the CAD as given, as STEP and BREP, and ``summary.json`` - the
answer as :func:`fastcae.designs.solve.summary` reads it, with the metal it adds and the mesh's
quality.
"""

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..extract import Extraction
    from ..project import Project

FOLDER = "target"


def folder(project: Project) -> Path:
    return project.root / FOLDER


def load(project: Project) -> dict[str, Any] | None:
    """The target's answer, or None when the project has no target solved."""
    path = folder(project) / "summary.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def solve(
    project: Project,
    extraction: Extraction,
    deck: Any,
    cad_file: Path,
    name: str = "production",
    say: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Keep ``cad_file`` as the project's target and solve it as a design is solved."""
    from . import cad
    from . import campaign as designs
    from . import solve as solving

    here = folder(project)
    here.mkdir(parents=True, exist_ok=True)
    kept = here / f"target{Path(cad_file).suffix.lower()}"
    if Path(cad_file).resolve() != kept.resolve():
        shutil.copy2(cad_file, kept)
    t0 = time.time()
    shape = cad.load(kept)
    cad.write(shape, here / "target.step", here / "target.brep")
    part = cad.load(designs._baseline(project))
    metal_L = (cad._volume(shape) - cad._volume(part)) / 1e6
    say(f"target CAD kept: {metal_L:.2f} L more metal than the part")
    stats: dict[str, Any] = {}
    mesh = solving.mesh_cad(here / "target.brep", here / "mesh-work", stats)
    say(f"target meshed: {len(mesh.cells['TETRA10']):,} second-order tets")
    carried = solving.carried(project, extraction, mesh)
    solution = solving.solve_design(carried, log=say)
    summary = solving.summary(solution, carried, deck)
    from . import objective

    summary["objective"] = objective.score(project, summary)
    summary.update(
        {
            "name": name,
            "cad": kept.name,
            "metal_L": round(metal_L, 3),
            "mesh_stats": {k: v for k, v in stats.items() if not isinstance(v, list)},
            "seconds": round(time.time() - t0, 1),
        }
    )
    (here / "summary.json").write_text(json.dumps(summary, indent=1, default=float), "utf-8")
    designs._save_solution(here, carried, solution)
    say(f"target solved: {summary.get('words')}")
    return summary
