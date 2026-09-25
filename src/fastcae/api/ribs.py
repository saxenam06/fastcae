"""Rib network campaigns over HTTP: what one can be asked for - the kept design volumes, the
target it is held to, the seeders it can start from - and launching one on the runner."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import runner
from ..volumes import store

router = APIRouter()


def _open():  # type: ignore[no-untyped-def]
    from .app import _resume, _state

    if _state.project is None or _state.extraction is None:
        _resume()  # the server restarts on a source change; pick the session back up
    if _state.project is None or _state.extraction is None:
        raise HTTPException(409, "no project is open")
    return _state.project, _state.extraction


@router.get("/api/ribs/plan")
def plan() -> dict[str, Any]:
    """The kept volumes, the target a network is held to, and the seeders it can start from."""
    from ..designs import target
    from ..ribs import workflow
    from ..simulate import baseline

    project, extraction = _open()
    volumes = [
        {"name": v["name"], "volume_L": v.get("volume_L"), "faces": v["recipe"]["faces"]}
        for v in store.load(project.root, extraction.cad_digest)
    ]
    held = target.load(project)
    asked = workflow.Asked()
    return {
        "volumes": volumes,
        "target": {
            "name": held.get("name", "target"),
            "metal_L": held.get("metal_L"),
            "words": held.get("words"),
        }
        if held
        else None,
        "seeders": [{"name": s, "words": workflow.SEEDER_WORDS[s]} for s in workflow.SEEDERS],
        "defaults": {
            "pattern": asked.pattern,
            "rays": asked.rays,
            "steps": asked.steps,
            "polish": asked.polish,
            "seed": asked.seed,
        },
        "limits": {"rays": workflow.RAYS, "steps": workflow.STEPS, "polish": workflow.POLISH},
        "deck": baseline.read_deck(project) is not None,
    }


class Launch(BaseModel):
    volumes: list[str] = []
    pattern: str = "spokes"
    rays: int = 36
    steps: int = 20
    polish: int = 30
    seed: int = 0
    name: str | None = None


@router.post("/api/ribs/campaigns")
def launch(request: Launch) -> dict[str, Any]:
    """A rib network made by the runner, in the background: one campaign, one network."""
    from ..designs import target
    from ..ribs import workflow

    project, extraction = _open()
    if request.pattern not in workflow.SEEDERS:
        raise HTTPException(400, f"no seeder {request.pattern!r}")
    kept = {v["name"] for v in store.load(project.root, extraction.cad_digest)}
    if not kept:
        raise HTTPException(409, "no design volume is kept: pick faces on the CAD's Design volumes")
    unknown = [v for v in request.volumes if v not in kept]
    if unknown:
        raise HTTPException(404, f"no volume {', '.join(unknown)}")
    if target.load(project) is None:
        raise HTTPException(409, "the project has no target solved to hold designs to")
    job = runner.submit("ribs.network", project.name, request.model_dump())
    return {"job": job.id}
