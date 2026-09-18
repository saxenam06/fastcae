"""The pipeline over HTTP: its steps, the typed entities they produced, and the engineer's answers.

``GET /api/pipeline`` is the rail: two stages, each step with its status, what it read and what it
produced. ``GET /api/entities`` lists entities, ``GET /api/entities/{id}`` gives one in full with
everything linked to it both ways - the same JSON an agent reads. ``POST /api/answers`` records an
answer in the project's data; the next run applies it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..pipeline import answers as answer_store
from ..pipeline import graph as pipeline_graph
from . import designspace

router = APIRouter()

_cached: dict[str, Any] = {"key": None, "graph": None}


def current_graph() -> pipeline_graph.Graph:
    """The graph of what the server holds now, built again only when something in it changed."""
    project, extraction = designspace.opened()
    held = designspace.held
    answers = answer_store.load(project)
    key = (
        id(extraction),
        id(held.space),
        held.version,
        held.running,
        tuple(sorted(answers.items())),
    )
    if _cached["key"] != key:
        _cached["graph"] = pipeline_graph.build(
            extraction, held.space, answers, dict(held.live), held.running
        )
        _cached["key"] = key
    return _cached["graph"]


@router.get("/api/pipeline")
def get_pipeline() -> dict[str, Any]:
    out = current_graph().pipeline()
    out["running"] = designspace.held.running
    out["cached"] = designspace.held.cached
    return out


@router.post("/api/pipeline/run")
def post_pipeline_run(request: designspace.RunRequest) -> StreamingResponse:
    """Run the design-space stage - or read it back - as a stream: each step as it starts and
    finishes, then ``done``. The Read stage ran when the files were extracted."""
    return designspace.stream_of(request)


@router.get("/api/entities")
def get_entities(
    kind: str | None = None,
    step: str | None = None,
    ids: str | None = None,
    text: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> dict[str, Any]:
    """Entities in a few words each: all of them, or of one kind, one step, or the ids given
    (comma-separated), or whose label contains ``text``."""
    return current_graph().find(kind, step, ids.split(",") if ids else None, text, limit, offset)


@router.get("/api/entities/schema")
def get_schema() -> dict[str, Any]:
    """Every entity kind's fields, as JSON Schema."""
    return pipeline_graph.schema()


@router.get("/api/entities/{entity_id:path}")
def get_entity(entity_id: str) -> dict[str, Any]:
    """One entity in full: its typed fields, evidence, links, and what links to it."""
    found = current_graph().entity(entity_id)
    if found is None:
        raise HTTPException(404, f"no entity {entity_id!r}")
    return found


class AnswerRequest(BaseModel):
    question: str
    value: str | None = None
    """An option the question offers, or None to take the answer back."""


@router.post("/api/answers")
def post_answer(request: AnswerRequest) -> dict[str, Any]:
    """Record an answer in the project's data. The design space runs again to apply it."""
    try:
        return record_answer(request.question, request.value)
    except KeyError as error:
        raise HTTPException(404, str(error.args[0])) from None
    except ValueError as error:
        raise HTTPException(400, str(error)) from None


def record_answer(question: str, value: str | None) -> dict[str, Any]:
    """Keep an answer - one of the options the question offers, or None to take it back - with the
    part. KeyError for a question there is not, ValueError for an answer it does not offer."""
    project, _ = designspace.opened()
    entity = current_graph().entities.get(question)
    if entity is None or entity.kind != "question":
        raise KeyError(f"no question {question!r}")
    options = getattr(entity, "options", [])
    if value is not None and options and value not in options:
        raise ValueError(f"{value!r} is not one of {', '.join(options)}")
    answers = answer_store.save(project, question, value)
    return {"answers": answers, "rerun": "space"}
