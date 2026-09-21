"""The pipeline over HTTP: its steps and the typed entities they produced.

``GET /api/pipeline`` is the rail: every step with its status, what it read and what it produced,
the design space last. ``GET /api/entities`` lists entities, ``GET /api/entities/{id}`` gives one in
full with everything linked to it both ways - the same JSON an agent reads.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..pipeline import graph as pipeline_graph
from . import designspace

router = APIRouter()

_cached: dict[str, Any] = {"key": None, "graph": None}


def current_graph() -> pipeline_graph.Graph:
    """The graph of what the server holds now, built again only when something in it changed."""
    _, extraction = designspace.opened()
    held = designspace.held
    key = (id(extraction), id(held.space), held.version, held.running, held.cached)
    if _cached["key"] != key:
        _cached["graph"] = pipeline_graph.build(
            extraction, held.space, held.cached, held.running, held.said, held.since
        )
        _cached["key"] = key
    return _cached["graph"]


@router.get("/api/pipeline")
def get_pipeline() -> dict[str, Any]:
    out = current_graph().pipeline()
    out["running"] = designspace.held.running
    return out


@router.post("/api/pipeline/run")
def post_pipeline_run(request: designspace.RunRequest) -> StreamingResponse:
    """Read the design space - or define it - as a stream. The engineer's files were read when the
    project was extracted."""
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
