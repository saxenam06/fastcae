"""The runner's job for the baseline: its deck's own mesh and setup solved again here, by cuDSS on
the GPU, so fastcae's answer can be set beside the engineer's own - and the mesher's settings every
design of a campaign is meshed with.
"""

from __future__ import annotations

import time

from ..project import Project, open_project
from . import baseline, signals, solve

# The route every design of a campaign takes: the design grid a campaign previews on, and the
# mesher's settings. Cells and facets are held to the deck mesh's own element sizes; the bounds
# here only cap them.
ROUTE = {
    "spacing_mm": 3.0,
    "cell": 40.0,
    "facet": 30.0,
    "distance": 2.0,
    "edge": 8.0,
    "threads": 4,
    "seed": 0,
}


def _project(spec: dict) -> Project:
    return open_project(spec["project"])


def _deck(project: Project) -> baseline.Deck:
    deck = baseline.read_deck(project)
    if deck is None:
        raise RuntimeError("the project has no solver deck")
    return deck


def solve_deck(job, spec: dict) -> dict:  # type: ignore[no-untyped-def]
    """The deck's own mesh and setup, solved by cuDSS on the GPU."""
    from ..runner import GPU

    project = _project(spec)
    deck = _deck(project)
    job.update(stage="solve", progress=0.1, message="waiting for the GPU")
    with GPU:
        job.update(message="assembling and solving on the GPU")
        solution = solve.solve(deck.mesh, deck.setup, gpu=True, log=lambda m: job.event(m))
    answer = signals.from_solution(solution, "cuDSS")
    meta: dict = {
        "solver": "cuDSS",
        "mesh": "the deck's own",
        "unknowns": solution.unknowns,
        "times": solution.times,
        "residual": solution.info.get("residual"),
        "made": time.time(),
    }
    reference = deck.answer()
    if reference is not None:
        meta["agreement"] = signals.field_agreement(deck.mesh, reference, answer)
    baseline.store_answer(project, "cudss", deck.digest, answer, meta)
    return meta
