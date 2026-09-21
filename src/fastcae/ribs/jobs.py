"""The runner's job for ribs: one rib network in the kept design volumes, held to the project's
target - seeded, optimised, chosen, built, meshed and solved (:mod:`.workflow`)."""

from __future__ import annotations

from .. import extract
from ..designs import target
from ..project import open_project
from ..simulate import baseline
from ..volumes import store, volume
from . import workflow


def run_network(job, spec: dict) -> dict:  # type: ignore[no-untyped-def]
    """One network campaign, from what the job asks."""
    from ..runner import GPU

    project = open_project(spec["project"])
    asked = workflow.Asked.of(spec.get("args", {}))
    job.update(stage="ribs", message="opening the part, its deck and its design volumes")
    extraction = extract.run(project)
    deck = baseline.read_deck(project)
    if deck is None:
        raise RuntimeError("the project has no solver deck")
    held = target.load(project)
    if held is None:
        raise RuntimeError("the project has no target solved to hold designs to")
    kept = store.load(project.root, extraction.cad_digest)
    chosen = [v for v in kept if not asked.volumes or v["name"] in asked.volumes]
    if not chosen:
        raise RuntimeError("no design volume is kept: pick faces on the CAD's Design volumes view")
    found = [(v["name"], volume.find(extraction, store.recipe_of(v), deck.setup)) for v in chosen]

    def say(line: str) -> None:
        job.event(line)
        job.update(message=line)

    folder = workflow.run(
        project, extraction, deck, found, held, asked, say=say, lock=GPU, cancelled=job.cancelled
    )
    return {"campaign": folder.name}
