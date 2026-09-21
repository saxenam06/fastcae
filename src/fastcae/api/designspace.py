"""The design space over HTTP: read from the project's folder - or defined there by the rules when
the engineer brought none - and the volume itself.

``POST /api/designspace/run`` streams the step: what the rules say as they go when they define it,
then ``done``. The volume can then be asked for as cells for the stage, with where metal helps on
each of them.
"""

from __future__ import annotations

import json
import queue
import struct
import threading
import time
from collections.abc import Callable
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..geometry.cells import exposed_faces
from ..space.model import Label, Space
from ..space.store import defined

router = APIRouter()


class _Held:
    """The design space of the open project, and the run reading or defining it."""

    def __init__(self) -> None:
        self.project: str | None = None
        self.space: Space | None = None
        self.cached = False
        self.running = False
        self.said = ""
        self.since: float | None = None
        self.faces: np.ndarray | None = None
        self.lock = threading.Lock()
        self.version = 0

    def forget(self) -> None:
        self.space = None
        self.faces = None
        self.version += 1


held = _Held()


def opened():  # type: ignore[no-untyped-def]
    """The open project and its extraction; a new project forgets the last one's space."""
    from .app import _resume, _state

    if _state.project is None or _state.extraction is None:
        _resume()  # the server restarts on a source change; pick the session back up
    if _state.project is None or _state.extraction is None:
        raise HTTPException(409, "no project has been extracted")
    if held.project != _state.project.name:
        held.forget()
        held.project = _state.project.name
    return _state.project, _state.extraction


def _space() -> Space:
    opened()
    if held.space is None:
        raise HTTPException(409, "the design space has not been read yet")
    return held.space


class RunRequest(BaseModel):
    again: bool = False
    """Define it again by the rules - never over one the engineer brought."""


def start(request: RunRequest, on_event: Callable[[dict[str, Any] | None], None]) -> None:
    """Read - or define - the open project's design space in the background, telling ``on_event``
    what the rules say as they go, then ``done`` (or ``error``), then None."""
    project, extraction = opened()
    with held.lock:
        if held.running:
            raise HTTPException(409, "the design space is already being read")
        held.running = True
        held.said = ""
        held.since = time.time()
        held.version += 1

    def say(line: str) -> None:
        held.said = line
        held.version += 1
        on_event({"type": "say", "detail": line})

    def setup():  # type: ignore[no-untyped-def]
        from ..simulate import baseline as solver_deck

        deck = solver_deck.read_deck(project)
        return deck.setup if deck else None

    def work() -> None:
        try:
            space, read = defined(extraction, setup, project.root, again=request.again, say=say)
            held.forget()
            held.space = space
            held.cached = read
            on_event({"type": "done", "cached": read})
        except Exception as error:  # noqa: BLE001 - reported on the stream, not swallowed
            on_event({"type": "error", "message": f"{type(error).__name__}: {error}"})
        finally:
            held.running = False
            held.said = ""
            held.version += 1
            on_event(None)

    threading.Thread(target=work, daemon=True).start()


def stream_of(request: RunRequest) -> StreamingResponse:
    events: queue.Queue = queue.Queue()
    start(request, events.put)

    def stream():
        while True:
            event = events.get()
            if event is None:
                return
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/designspace/run")
def post_run(request: RunRequest) -> StreamingResponse:
    """Read the design space - or define it - as a stream."""
    return stream_of(request)


@router.get("/api/designspace")
def get_designspace() -> dict[str, Any]:
    """What the design space holds and how it was defined, or 409 before it has been read."""
    out = _space().summary()
    out["cached"] = held.cached
    return out


def _faces(space: Space) -> np.ndarray:
    if held.faces is None:
        held.faces = exposed_faces(space.labels == Label.DESIGN)
    return held.faces


@router.get("/api/designspace/cells/{layer}")
def get_cells(layer: str) -> Response:
    """The design space's cells, one integer a visible face - the same format as the field's."""
    from .app import _voxel_blob

    if layer != "design":
        raise HTTPException(404, f"no layer {layer!r}; there is design")
    if held.running:
        raise HTTPException(409, "the design space is being read")
    space = _space()
    return Response(
        content=_voxel_blob(space.grid, _faces(space)),
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/api/designspace/values/benefit")
def get_benefit_values() -> Response:
    """Where metal helps at each visible face of the design space, in the order the cells route
    gives those faces: the range first (two floats, 5th and 99.5th percentile), then one a face."""
    if held.running:
        raise HTTPException(409, "the design space is being read")
    space = _space()
    if space.benefit is None:
        raise HTTPException(409, "where metal helps was not found: the deck could not be solved")
    faces = _faces(space)
    values = space.benefit.ravel()[(faces >> 3).astype(np.int64)].astype("<f4")
    inside = space.benefit[space.labels == Label.DESIGN]
    positive = inside[inside > 0]
    lo = float(np.percentile(positive, 5)) if len(positive) else 0.0
    hi = float(np.percentile(inside, 99.5)) if len(inside) else 1.0
    return Response(
        content=struct.pack("<ff", lo, hi) + values.tobytes(),
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-cache"},
    )
