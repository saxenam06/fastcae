"""HTTP surface.

Routes contain no logic. Each unpacks a request, calls one function from the engine, and packs the
result. Anything a route could do that the engine cannot is something nothing else driving the
engine would be able to do.

**Nothing is loaded at startup.** The server begins with no project open, because the first thing
a person does is choose what to extract. A server that pre-loads one part is a server built around
that part.

This module holds the session - which project is open, and what was read from it - and the routes
that serve what was read: the part's surface, its faces, features and callouts, and the agent. The
pipeline, the design space, the deck and the designs have routers of their own, included at the end.
"""

from __future__ import annotations

import json
import struct
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..extract import Extraction
from ..extract import run as run_extract
from ..features import extent as feature_extent
from ..features import neighbours as feature_neighbours
from ..project import ASSETS_ROOT, ArtifactKind, Project, classify, discover, open_project
from ..provenance import Evidence, Fact
from . import mesh as mesh_format

VOXEL_MAGIC = b"FCVOXL02"


@dataclass
class State:
    """Everything the server is holding. One project at a time, and none to begin with."""

    project: Project | None = None
    extraction: Extraction | None = None
    mesh_blob: bytes | None = None
    agent: Any = None

    @property
    def stage(self) -> str:
        """Which stage of the product the session has reached."""
        if self.extraction is None:
            return "upload"
        if not self.extraction.ok:
            return "extract_failed"
        return "model"


_state = State()

LAST_OPEN = Path(".fastcae-open")
"""Where the server notes which project it has open, so a restart can pick it up again."""


def _remember(project: Project | None) -> None:
    """Note which project is open, or that none is."""
    try:
        if project is None:
            LAST_OPEN.unlink(missing_ok=True)
        else:
            LAST_OPEN.write_text(str(project.root.resolve()), encoding="utf-8")
    except OSError:
        pass  # a session that cannot be noted still works; it just will not survive a restart


def _resume() -> bool:
    """Open again what this server had open before it restarted.

    In development the server restarts whenever a source file is saved, which empties this module's
    state. Without this, every edit silently logs the engineer out: the page they are looking at
    keeps its data, and the next thing they click answers "no project is open". The extraction is
    reused from the project's own cache, so resuming costs nothing the project has not already done.
    """
    if _state.project is not None:
        return True
    try:
        where = LAST_OPEN.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if not where or not Path(where).is_dir():
        return False
    try:
        project = open_project(where)
        _state.extraction = run_extract(project, reuse=True)
        _state.project = project
    except Exception:  # a project that will not open is not worth failing the request for
        return False
    return True


def extracted() -> Extraction:
    if _state.extraction is None:
        _resume()
    if _state.extraction is None:
        raise HTTPException(409, "nothing has been extracted yet")
    return _state.extraction


def _project() -> Project:
    if _state.project is None:
        _resume()
    if _state.project is None:
        raise HTTPException(409, "no project is open")
    return _state.project


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"fastcae ready. {len(discover())} project(s) under {ASSETS_ROOT}/. Nothing loaded.")
    yield


app = FastAPI(title="fastcae", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5183", "http://127.0.0.1:5183"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExtractRequest(BaseModel):
    project: str = Field(min_length=1)
    paths: list[str] | None = None
    """Explicit artifact paths, overriding what the folder contains.

    Sent when someone has edited a path in the interface. Absent means "use the folder".
    """

    reuse: bool = True
    """Whether a result already read from these files may be returned instead of reading again.

    False is what *re-extract* means. Not a cache repair - the cache is keyed on the content of the
    files and on the code that read them, so it cannot go stale on its own - but a way to say "read
    it again" when the reason sits outside both.
    """


class RolesRequest(BaseModel):
    """Which CAD file designs grow from."""

    baseline: str = Field(min_length=1)


# --- session -----------------------------------------------------------------------------------


@app.get("/api/state")
def get_state() -> dict:
    """Where the session is. Polled by the UI, and the seed of the agent state view.

    The UI polls this, so resuming here is what makes a restart invisible: the page recovers on its
    own rather than waiting for the engineer to click something that fails."""
    if _state.project is None:
        _resume()
    done = _state.extraction
    return {
        "stage": _state.stage,
        "project": None if _state.project is None else _project_row(_state.project),
        "extracted": done is not None,
        "from_cache": None if done is None else done.from_cache,
        "seconds": None if done is None else round(done.seconds, 2),
        "steps": [] if done is None else [_step_row(s) for s in done.steps],
    }


@app.get("/api/projects")
def get_projects() -> list[dict]:
    """Every folder under assets/. The upload screen's contents."""
    return [_project_row(p) for p in discover()]


@app.get("/api/check")
def get_check(path: str) -> dict:
    """Whether a path exists, and what kind it would be read as.

    Lets the interface validate an edited path before committing to a pipeline run.
    """
    candidate = Path(path)
    if not candidate.is_file():
        return {"path": path, "exists": False, "kind": None, "label": None, "size_bytes": 0}
    artifact = classify(candidate)
    return {
        "path": path,
        "exists": True,
        "kind": str(artifact.kind),
        "label": artifact.label,
        "size_bytes": artifact.size_bytes,
    }


@app.post("/api/extract")
def post_extract(request: ExtractRequest) -> dict:
    """Run the deterministic pipeline over a project."""
    try:
        project = open_project(request.project)
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error

    artifacts = None
    if request.paths is not None:
        missing = [p for p in request.paths if not Path(p).is_file()]
        if missing:
            raise HTTPException(400, f"not a file: {', '.join(missing)}")
        artifacts = [classify(Path(p)) for p in request.paths]

    _state.project = project
    _state.extraction = run_extract(project, artifacts=artifacts, reuse=request.reuse)
    _state.mesh_blob = None
    _state.agent = None
    _remember(project)
    return get_state()


@app.put("/api/project/roles")
def put_roles(request: RolesRequest) -> dict:
    """Name the baseline, then read the project again.

    The baseline decides what is read, so everything read before this is about a different file.
    """
    if _state.project is None:
        raise HTTPException(409, "no project is open")
    try:
        _state.project.set_roles(baseline=request.baseline)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    return post_extract(ExtractRequest(project=str(_state.project.root)))


def _voxel_blob(grid, faces: np.ndarray) -> bytes:
    """Cells for the renderer: the grid, then one integer per visible cell face."""
    return (
        VOXEL_MAGIC
        + struct.pack(
            "<Ifiii fff",
            faces.size,
            grid.spacing_mm,
            grid.shape[0],
            grid.shape[1],
            grid.shape[2],
            *grid.origin,
        )
        + faces.astype("<u4").tobytes()
    )


@app.post("/api/reset")
def post_reset() -> dict:
    """Close the project and go back to a blank slate."""
    _state.project = None
    _state.extraction = None
    _state.mesh_blob = None
    _state.agent = None
    _remember(None)
    return get_state()


# --- results -----------------------------------------------------------------------------------


@app.get("/api/summary")
def get_summary() -> dict:
    result = extracted()
    exact = result.exact
    tess = result.tess
    return {
        "project": result.project.name,
        "title": result.project.title,
        "seconds": round(result.seconds, 2),
        "solids": None if exact is None else exact.n_solids,
        "faces": None if exact is None else exact.n_faces,
        "triangles": None if tess is None else tess.n_triangles,
        "volume_cm3": None if exact is None else round(exact.volume_cm3, 1),
        "area_m2": None if exact is None else round(exact.area_mm2 / 1e6, 4),
        "bbox_mm": None if exact is None else [round(v, 2) for v in exact.bbox_mm],
        "watertight": None if result.health is None else result.health.watertight,
        "features": None if result.features is None else len(result.features.features),
        "controlled_faces": len(result.controlled_face_ids()),
        "has_drawing": result.drawing is not None,
    }


@app.get("/api/steps")
def get_steps() -> list[dict]:
    return [_step_row(s) for s in extracted().steps]


@app.get("/api/mesh")
def get_mesh() -> Response:
    result = extracted()
    if result.tess is None:
        raise HTTPException(409, "no geometry was read")
    if _state.mesh_blob is None:
        _state.mesh_blob = _encode_mesh(result.tess)
    return Response(
        content=_state.mesh_blob,
        media_type="application/octet-stream",
        headers={"Content-Length": str(len(_state.mesh_blob)), "Cache-Control": "no-cache"},
    )


@app.get("/api/features")
def get_features(kind: str | None = None, limit: int = 300) -> list[dict]:
    result = extracted()
    if result.features is None:
        return []
    features = sorted(result.features.features.values(), key=lambda f: -f.area_mm2)
    if kind:
        features = [f for f in features if str(f.kind) == kind]
    return [_feature_row(result, f) for f in features[:limit]]


@app.get("/api/features/{feature_id}")
def get_feature(feature_id: str) -> dict:
    result = extracted()
    return _feature_row(result, _feature(result, feature_id))


@app.get("/api/features/{feature_id}/extent")
def get_feature_extent(feature_id: str, direction: str | None = None) -> dict:
    """How far a feature reaches along a direction: its lowest and highest point.

    ``direction`` is three numbers, ``x,y,z``. Left out, it is the feature's own: the way a planar
    group faces, or the axis a hole, bore or boss turns about.
    """
    result = extracted()
    feature = _feature(result, feature_id)
    if direction is not None:
        try:
            unit = [float(v) for v in direction.split(",")]
        except ValueError as error:
            raise HTTPException(400, "direction is three numbers, x,y,z") from error
    elif feature.normal is not None:
        unit = list(feature.normal)
    elif feature.axis_id is not None and result.features is not None:
        unit = list(result.features.axes[feature.axis_id].direction)
    else:
        raise HTTPException(400, f"{feature_id} has no direction of its own; give one")
    if len(unit) != 3 or not any(unit):
        raise HTTPException(400, "direction is three numbers, x,y,z, not all zero")
    assert result.tess is not None
    low, high = feature_extent(result.tess, feature.face_ids, tuple(unit))
    length = sum(v * v for v in unit) ** 0.5
    return {
        "feature": feature_id,
        "direction": [v / length for v in unit],
        "low_mm": round(low, 3),
        "high_mm": round(high, 3),
    }


@app.get("/api/features/{feature_id}/neighbours")
def get_feature_neighbours(feature_id: str) -> list[dict]:
    """Every feature touching this one along an edge."""
    result = extracted()
    _feature(result, feature_id)
    assert result.features is not None and result.atlas is not None
    return [
        _feature_row(result, result.features.features[other])
        for other in feature_neighbours(result.features, result.atlas, feature_id)
    ]


def _feature(result: Extraction, feature_id: str):
    found = None if result.features is None else result.features.get(feature_id)
    if found is None:
        raise HTTPException(404, f"no feature {feature_id}")
    return found


@app.get("/api/feature-kinds")
def get_feature_kinds() -> list[dict]:
    result = extracted()
    if result.features is None:
        return []
    return [
        {
            "kind": kind,
            "count": count,
            "controlled": sum(
                1
                for f in result.features.features.values()
                if str(f.kind) == kind and f.id in result.controlled
            ),
        }
        for kind, count in result.features.counts().items()
    ]


@app.get("/api/axes")
def get_axes() -> list[dict]:
    result = extracted()
    if result.features is None:
        return []
    return [
        {
            "id": axis.id,
            "point": [round(v, 2) for v in axis.point],
            "direction": [round(v, 4) for v in axis.direction],
            "face_count": len(axis.face_ids),
            "area_mm2": round(axis.area_mm2, 1),
            "feature_count": len(result.features.on_axis(axis.id)),
        }
        for axis in result.features.significant_axes()
    ]


@app.get("/api/callouts")
def get_callouts(kind: str | None = None) -> list[dict]:
    """What the drawing says. Empty when there is no drawing, which is not an error."""
    result = extracted()
    if result.drawing is None:
        return []
    callouts = result.drawing.callouts
    if kind:
        callouts = [c for c in callouts if str(c.kind) == kind]
    return [
        {
            "kind": str(c.kind),
            "page": c.page,
            "raw": c.raw,
            "nominal": c.nominal,
            "tolerance": c.tolerance,
            "count": c.count,
            "is_diameter": c.is_diameter,
            "through": c.through,
            "text": c.text,
        }
        for c in callouts
    ]


@app.get("/api/controlled")
def get_controlled() -> dict:
    result = extracted()
    face_ids = result.controlled_face_ids()
    return {
        "face_ids": sorted(face_ids),
        "count": len(face_ids),
        "by_feature": {
            feature_id: _fact_row(fact) for feature_id, fact in result.controlled.items()
        },
    }


@app.get("/api/faces/{face_id}")
def get_face(face_id: int) -> dict:
    result = extracted()
    if result.atlas is None or face_id not in result.atlas.faces:
        raise HTTPException(404, f"no face {face_id}")
    face = result.atlas[face_id]
    controlled = result.controlled_face_ids()
    features = [] if result.features is None else result.features.containing(face_id)
    return {
        "face_id": face.face_id,
        "surface_type": face.surface_type,
        "area_mm2": round(face.area, 2),
        "analytic_area_mm2": round(face.area_mm2, 2),
        "analytic_area_is_valid": face.area_mm2 > 0,
        "centroid_mm": [round(v, 2) for v in face.centroid],
        "bbox_mm": _face_box(result, face_id),
        "normal": None if face.normal is None else [round(v, 6) for v in face.normal],
        "axis": None if face.axis is None else [round(v, 6) for v in face.axis],
        "diameter_mm": None if face.diameter_mm is None else round(face.diameter_mm, 3),
        "minor_radius_mm": (
            None if face.minor_radius_mm is None else round(face.minor_radius_mm, 3)
        ),
        "half_angle_deg": (None if face.half_angle_deg is None else round(face.half_angle_deg, 2)),
        "concave": face.concave,
        "exterior": face.exterior,
        "z_mm": round(face.z_mm, 2),
        "neighbours": list(face.neighbours),
        "controlled": face_id in controlled,
        "features": [_feature_row(result, f) for f in features],
    }


def _face_box(result: Extraction, face_id: int) -> list[float] | None:
    """Where a face reaches, from its own triangles: OCC's box is padded by the face's tolerance."""
    if result.tess is None:
        return None
    mine = result.tess.face_id == face_id
    if not mine.any():
        return None
    points = result.tess.vertices[np.unique(result.tess.triangles[mine])]
    return [round(float(v), 2) for v in (*points.min(axis=0), *points.max(axis=0))]


def _project_row(project: Project) -> dict:
    artifacts = project.artifacts()
    return {
        "name": project.name,
        "title": project.title,
        "path": str(project.root),
        "artifacts": [
            {
                "name": a.name,
                "kind": str(a.kind),
                "label": a.label,
                "path": str(a.path),
                "size_bytes": a.size_bytes,
            }
            for a in artifacts
        ],
        "has_cad": any(a.kind is ArtifactKind.CAD for a in artifacts),
        "has_drawing": any(a.kind is ArtifactKind.DRAWING for a in artifacts),
        "roles": project.roles(),
    }


def _step_row(step) -> dict:
    return {
        "id": step.id,
        "label": step.label,
        "status": str(step.status),
        "detail": step.detail,
        "needs": [str(k) for k in step.needs],
        "produced": step.produced,
        "warnings": step.warnings,
        "seconds": round(step.seconds, 2),
    }


def _feature_row(result: Extraction, feature) -> dict:
    fact = result.controlled.get(feature.id)
    return {
        "id": feature.id,
        "kind": str(feature.kind),
        "face_ids": list(feature.face_ids),
        "area_mm2": round(feature.area_mm2, 1),
        "axis_id": feature.axis_id,
        "diameter_mm": None if feature.diameter_mm is None else round(feature.diameter_mm, 3),
        "station_mm": None if feature.station_mm is None else round(feature.station_mm, 2),
        "count": feature.count,
        "metrics": {k: (None if v != v else round(v, 3)) for k, v in feature.metrics.items()},
        "centroid_mm": [round(v, 2) for v in feature.centroid],
        "normal": None if feature.normal is None else [round(v, 6) for v in feature.normal],
        "opens_onto": list(feature.opens_onto),
        "controlled": None if fact is None else _fact_row(fact),
    }


def _fact_row(fact: Fact) -> dict:
    return {
        "value": fact.value,
        "state": str(fact.state),
        "confidence": round(fact.confidence, 2),
        "note": fact.note,
        "evidence": [_evidence_row(e) for e in fact.evidence],
    }


def _evidence_row(evidence: Evidence) -> dict:
    return {
        "kind": str(evidence.kind),
        "locator": evidence.locator,
        "method": evidence.method,
        "detail": evidence.detail,
        "confidence": round(evidence.confidence, 2),
    }


# --- mesh --------------------------------------------------------------------------------------


def _encode_mesh(
    tess, normals: np.ndarray | None = None, standing: np.ndarray | None = None
) -> bytes:
    """Pack a surface for the renderer. The format, and why it is that format, is in
    :mod:`fastcae.api.mesh`."""
    return mesh_format.encode(tess.vertices, tess.triangles, tess.face_id, normals, standing)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    focus: list[str] = Field(default_factory=list)
    """The entities in focus on the engineer's screen when they wrote."""


# --- the agent ------------------------------------------------------------------------------------


def _agent():
    """The agent for the open project: one conversation, kept with the project."""
    from ..agent.runtime import Runtime

    project, result = _project(), extracted()
    held = _state.agent
    if held is None or held.project.root != project.root or held.context.extraction is not result:
        _state.agent = Runtime(project, result)
    return _state.agent


def _agent_context():
    """What the agent's tools work on, for the open project, without the model behind them."""
    from ..agent import tools as agent_tools

    return agent_tools.Context(_project(), extracted(), said=[])


@app.get("/api/agent/status")
def get_agent_status() -> dict:
    """Which model the agent runs on, whether its key is present, whether tracing is on."""
    from ..agent.runtime import status

    return status()


@app.get("/api/agent/history")
def get_agent_history() -> dict:
    agent = _agent()
    return {"thread": agent.thread, "messages": agent.history()}


@app.post("/api/agent/new")
def post_agent_new() -> dict:
    """Start a new conversation. The old one is kept."""
    agent = _agent()
    agent.new_thread()
    return {"thread": agent.thread, "messages": []}


@app.post("/api/agent/chat")
def post_agent_chat(request: ChatRequest) -> StreamingResponse:
    """One message to the agent, answered as a stream of events: text, tools, what changed."""
    try:
        agent = _agent()
    except Exception as error:  # noqa: BLE001 - a missing key or model has to reach the pane
        raise HTTPException(503, f"the agent could not start: {error}") from error

    def events():
        for event in agent.turn(request.message, request.focus):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# The pipeline: its steps and the typed entities they produced.
from . import pipeline as pipeline_routes  # noqa: E402 - after the state it reads

app.include_router(pipeline_routes.router)

# The design space: read from the project, or defined there by the rules.
from . import designspace as designspace_routes  # noqa: E402 - after the state it reads

app.include_router(designspace_routes.router)

# The deck: its mesh, setup and results, solved again by cuDSS; the runner's jobs.
from . import simulate as simulate_routes  # noqa: E402 - after the state it reads

app.include_router(simulate_routes.router)

# Designs made in the design space: campaigns, and every stage of every design.
from . import designs as design_routes  # noqa: E402 - after the state it reads

app.include_router(design_routes.router)

# Design volumes: what the engineer's picks bound, and the volumes the project keeps.
from . import volumes as volume_routes  # noqa: E402 - after the state it reads

app.include_router(volume_routes.router)

# Rib campaigns: the kept volumes' candidate ribs sized by the loads, kept as patterns, built.
from . import ribs as rib_routes  # noqa: E402 - after the state it reads

app.include_router(rib_routes.router)
