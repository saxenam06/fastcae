"""The design space over HTTP: the pipeline's second stage run live, and what each step produced.

``POST /api/designspace/run`` streams the steps as they start and finish - or, when nothing the
space depends on has changed, replays the record of the run that made it. The engineer's answers,
kept in the project's data, are applied on every run. Everything a step produced can then be asked
for: its volumes as cells for the stage, its per-face values, the benefit of metal on the allowed
space.
"""

from __future__ import annotations

import json
import queue
import struct
import threading
from collections.abc import Callable
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..generate.cells import exposed_faces
from ..pipeline import answers as answer_store
from ..space.grid import distance_to
from ..space.model import Label, Params, Reason, Space
from ..space.store import derived

router = APIRouter()

NEAR_MM = 150.0
"""Keep-outs run on to the grid's edge; the stage shows them only this close to the part."""


class _Held:
    """The space for the open project, and the run making one."""

    def __init__(self) -> None:
        self.project: str | None = None
        self.space: Space | None = None
        self.cached = False
        self.running = False
        self.live: dict[str, dict[str, Any]] = {}
        self.near: np.ndarray | None = None
        self.masks: dict[str, np.ndarray] = {}
        self.lock = threading.Lock()
        self.version = 0
        # While a run derives: each layer's visible cell faces as its step made it, and the grid.
        self.live_faces: dict[str, tuple[Any, Future]] = {}

    def forget(self) -> None:
        self.space = None
        self.near = None
        self.masks = {}
        self.live = {}
        self.version += 1


held = _Held()


def opened():  # type: ignore[no-untyped-def]
    """The open project and its extraction; a new project forgets the last one's space."""
    from .app import _state

    if _state.project is None or _state.extraction is None:
        raise HTTPException(409, "no project has been extracted")
    if held.project != _state.project.name:
        held.forget()
        held.project = _state.project.name
    return _state.project, _state.extraction


def _space() -> Space:
    opened()
    if held.space is None:
        raise HTTPException(409, "the design space has not been derived yet")
    return held.space


class RunRequest(BaseModel):
    reuse: bool = True
    inside: bool | None = None
    panel_layer: float | None = None
    pocket_reach: float | None = None


def params_for(project, request: RunRequest | None) -> Params:  # type: ignore[no-untyped-def]
    """The rules' settings: the defaults, then what the engineer's answers settle, then what this
    request asks for."""
    params = Params()
    for name, value in answer_store.settings(answer_store.load(project)).items():
        setattr(params, name, value)
    if request is not None:
        for name in ("inside", "panel_layer", "pocket_reach"):
            value = getattr(request, name)
            if value is not None:
                setattr(params, name, value)
        if request.panel_layer is not None:
            params.inside_layer = request.panel_layer
    return params


def start(request: RunRequest, on_event: Callable[[dict[str, Any] | None], None]) -> None:
    """Derive - or read back - the open project's design space in the background, telling
    ``on_event`` each step as it starts and finishes, then ``done`` (or ``error``), then None."""
    project, extraction = opened()
    with held.lock:
        if held.running:
            raise HTTPException(409, "the design space is already being derived")
        held.running = True
        held.live = {}
        held.live_faces = {}
    params = params_for(project, request)
    answers = answer_store.load(project)

    def report(step: dict[str, Any]) -> None:
        held.live[step["id"]] = step
        held.version += 1
        on_event({"type": "step", **step})

    # A layer's visible faces are found beside the run rather than in it: the derivation goes on
    # while they are, and a request for the layer waits for its own.
    faces = ThreadPoolExecutor(max_workers=1, thread_name_prefix="layer-faces")

    def publish(grid, layer: str, cells: np.ndarray) -> None:  # type: ignore[no-untyped-def]
        """A layer as soon as it is made, so the stage can show it while the rest is derived."""
        held.live_faces[layer] = (grid, faces.submit(exposed_faces, cells))

    def work() -> None:
        from ..simulate import baseline as solver_deck

        try:
            deck = solver_deck.read_deck(project)
            space, hit = derived(
                extraction,
                deck.setup if deck else None,
                params,
                project.root,
                reuse=request.reuse,
                report=report,
                say=None,
                answers=answer_store.for_interfaces(answers),
                publish=publish,
            )
            held.forget()
            held.space = space
            held.cached = hit
            on_event({"type": "done", "cached": hit})
        except Exception as error:  # noqa: BLE001 - reported on the stream, not swallowed
            on_event({"type": "error", "message": f"{type(error).__name__}: {error}"})
        finally:
            held.running = False
            held.live = {}
            held.live_faces = {}
            faces.shutdown(wait=False, cancel_futures=True)
            held.version += 1
            on_event(None)

    threading.Thread(target=work, daemon=True).start()


def stream_of(
    request: RunRequest, shape: Callable[[dict[str, Any]], dict[str, Any]] = lambda e: e
) -> StreamingResponse:
    events: queue.Queue = queue.Queue()
    start(request, events.put)

    def stream():
        while True:
            event = events.get()
            if event is None:
                return
            yield f"data: {json.dumps(shape(event), default=str)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/designspace/run")
def post_run(request: RunRequest) -> StreamingResponse:
    """Derive the design space - or read it back - as a stream of its steps."""
    return stream_of(request)


def _summary(space: Space, cached: bool) -> dict[str, Any]:
    out = space.summary()
    out["cached"] = cached
    return out


@router.get("/api/designspace")
def get_designspace() -> dict[str, Any]:
    """The derived space's summary and its pipeline record, or 409 before the first run."""
    return _summary(_space(), held.cached)


def _mask(space: Space, layer: str) -> np.ndarray:
    """The cells a step's layer holds."""
    if layer in held.masks:
        return held.masks[layer]
    labels, reasons = space.labels, space.reasons
    part = labels == Label.PART
    air = ~part

    def bit(reason: Reason) -> np.ndarray:
        return (reasons & np.uint16(reason)) != 0

    if held.near is None:
        held.near = distance_to(part, space.grid.spacing_mm) <= NEAR_MM
    near = held.near
    masks = {
        "part": lambda: part,
        "plug": lambda: bit(Reason.BORE_CORRIDOR) & ~bit(Reason.BEYOND) & air & near,
        "beyond": lambda: bit(Reason.BEYOND) & air & near,
        "mating": lambda: bit(Reason.PLANE_NEIGHBOUR) & air & near,
        "ring": lambda: bit(Reason.RING_NEIGHBOUR) & air & near,
        "hole": lambda: bit(Reason.HOLE_ACCESS) & air & near,
        "buffer": lambda: bit(Reason.INTERFACE_BUFFER) & air & near,
        "waiting": lambda: bit(Reason.UNKNOWN) & ~bit(Reason.LEAK) & air & near,
        "cavity": lambda: labels == Label.CAVITY,
        "leak": lambda: bit(Reason.LEAK),
        "panel": lambda: bit(Reason.PANEL_LAYER),
        "pocket": lambda: bit(Reason.POCKET),
        "allowed": lambda: labels == Label.ADMISSIBLE,
        "unknown": lambda: labels == Label.UNKNOWN,
        "benefit": lambda: labels == Label.ADMISSIBLE,
    }
    if layer not in masks:
        raise HTTPException(404, f"no layer {layer!r}; there are {', '.join(masks)}")
    found = masks[layer]()
    held.masks[layer] = found
    return found


def _faces_of(space: Space, layer: str) -> np.ndarray:
    key = f"faces:{layer}"
    if key not in held.masks:
        held.masks[key] = exposed_faces(_mask(space, layer))
    return held.masks[key]


@router.get("/api/designspace/cells/{layer}")
def get_cells(layer: str) -> Response:
    """One layer's cells, as one integer per visible face - the same format as the field's. While a
    run is deriving, the layers its steps have made so far."""
    from .app import _voxel_blob

    opened()
    if held.running:
        if layer not in held.live_faces:
            raise HTTPException(409, f"the run has not made {layer!r} yet")
        grid, pending = held.live_faces[layer]
        try:
            faces = pending.result()
        except CancelledError:
            raise HTTPException(409, "the run has just ended: ask again") from None
    else:
        space = _space()
        grid, faces = space.grid, _faces_of(space, layer)
    return Response(
        content=_voxel_blob(grid, faces),
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/api/designspace/values/benefit")
def get_benefit_values() -> Response:
    """The benefit of metal at each visible face of the allowed space, in the order the cells route
    gives those faces: the range first (two floats, 5th and 99.5th percentile), then one a face."""
    space = _space()
    if held.running:
        raise HTTPException(409, "the design space is being derived again")
    if space.benefit is None:
        raise HTTPException(409, "the physics step has not run")
    faces = _faces_of(space, "benefit")
    values = space.benefit.ravel()[(faces >> 3).astype(np.int64)].astype("<f4")
    allowed = space.benefit[space.labels == Label.ADMISSIBLE]
    positive = allowed[allowed > 0]
    lo = float(np.percentile(positive, 5)) if len(positive) else 0.0
    hi = float(np.percentile(allowed, 99.5)) if len(allowed) else 1.0
    return Response(
        content=struct.pack("<ff", lo, hi) + values.tobytes(),
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/api/designspace/faces/{kind}")
def get_faces(kind: str) -> dict[str, Any]:
    """Per CAD face: ``thickness`` or ``cap`` (mm), ``interface`` (the group that froze or asked
    about it) or ``sealing`` (the faces that hold the inside)."""
    space = _space()
    if held.running:
        raise HTTPException(409, "the design space is being derived again")
    if kind == "sealing":
        return {"kind": kind, "faces": {str(f): 1 for f in space.sealing_faces}}
    if kind not in space.faces:
        raise HTTPException(404, f"no face values {kind!r}")
    return {"kind": kind, "faces": {str(f): v for f, v in space.faces[kind].items()}}
