"""HTTP surface.

Routes contain no logic. Each unpacks a request, calls one function from the engine, and packs the
result. Anything a route could do that the engine cannot is something the agent would not be able
to do.

**Nothing is loaded at startup.** The server begins with no project open, because the first thing
a person does is choose what to extract. A server that pre-loads one part is a server built around
that part.
"""

from __future__ import annotations

import struct
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..extract import Extraction
from ..extract import run as run_extract
from ..project import ASSETS_ROOT, ArtifactKind, Project, classify, discover, open_project
from ..provenance import Evidence, Fact

MESH_MAGIC = b"FCMESH02"


@dataclass
class State:
    """Everything the server is holding. One project at a time, and none to begin with."""

    project: Project | None = None
    extraction: Extraction | None = None
    mesh_blob: bytes | None = None

    @property
    def stage(self) -> str:
        """Which stage of the product the session has reached.

        The ground truth behind the state strip in the UI, and later behind routing a question to
        the right node: a query about geometry belongs somewhere different from a query about a
        campaign, and the session has to know which it is in.
        """
        if self.extraction is None:
            return "upload"
        if not self.extraction.ok:
            return "extract_failed"
        return "model"


_state = State()


def extracted() -> Extraction:
    if _state.extraction is None:
        raise HTTPException(409, "nothing has been extracted yet")
    return _state.extraction


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


# --- session -----------------------------------------------------------------------------------


@app.get("/api/state")
def get_state() -> dict:
    """Where the session is. Polled by the UI, and the seed of the agent state view."""
    done = _state.extraction
    return {
        "stage": _state.stage,
        "project": None if _state.project is None else _project_row(_state.project),
        "extracted": done is not None,
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
    _state.extraction = run_extract(project, artifacts=artifacts)
    _state.mesh_blob = None
    return get_state()


@app.post("/api/reset")
def post_reset() -> dict:
    """Close the project and go back to a blank slate."""
    _state.project = None
    _state.extraction = None
    _state.mesh_blob = None
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


# --- selection ---------------------------------------------------------------------------------


class GrowRequest(BaseModel):
    seed: list[int] = Field(min_length=1)
    max_dihedral_deg: float = Field(default=40.0, gt=0.0, le=180.0)


class SimilarRequest(BaseModel):
    face_id: int


class FacesRequest(BaseModel):
    face_ids: list[int] = Field(min_length=1)


@app.post("/api/select/faces")
def post_select_faces(request: FacesRequest) -> dict:
    """Measure an arbitrary set of faces.

    A selection built by clicking needs its area and its overlap with what is controlled
    *measured*, not assumed. Filling those in client-side produced a panel that reported 0 mm2 and
    nothing controlled beside a face whose area and controlled state it had already shown.
    """
    result = extracted()
    if result.atlas is None:
        raise HTTPException(409, "no geometry")
    unknown = [i for i in request.face_ids if i not in result.atlas.faces]
    if unknown:
        raise HTTPException(404, f"no face {unknown[0]}")
    ids = set(request.face_ids)
    plural = "" if len(ids) == 1 else "s"
    return _selection(result, ids, f"{len(ids)} face{plural} picked directly")


@app.post("/api/select/grow")
def post_grow(request: GrowRequest) -> dict:
    result = extracted()
    if result.atlas is None:
        raise HTTPException(409, "no geometry")
    ids = result.atlas.grow(request.seed, max_dihedral_deg=request.max_dihedral_deg)
    return _selection(
        result,
        ids,
        f"grown from {sorted(request.seed)} across edges shallower than "
        f"{request.max_dihedral_deg:g} deg",
    )


@app.post("/api/select/similar")
def post_similar(request: SimilarRequest) -> dict:
    result = extracted()
    if result.atlas is None or request.face_id not in result.atlas.faces:
        raise HTTPException(404, f"no face {request.face_id}")
    seed = result.atlas[request.face_id]
    what = (
        f"O{seed.diameter_mm:.2f} {seed.surface_type}s"
        if seed.diameter_mm is not None
        else f"{seed.surface_type}s of about {seed.area:.0f} mm2"
    )
    return _selection(
        result, result.atlas.similar(request.face_id), f"all {what} matching face {request.face_id}"
    )


@app.get("/api/select/feature/{feature_id:path}")
def get_select_feature(feature_id: str) -> dict:
    result = extracted()
    if result.features is None or feature_id not in result.features.features:
        raise HTTPException(404, f"no feature {feature_id!r}")
    feature = result.features.features[feature_id]
    return _selection(result, set(feature.face_ids), feature.describe())


# --- rows --------------------------------------------------------------------------------------


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


def _selection(result: Extraction, face_ids, reason: str) -> dict:
    ids = sorted(int(i) for i in face_ids)
    controlled = result.controlled_face_ids()
    assert result.atlas is not None
    return {
        "face_ids": ids,
        "count": len(ids),
        "area_mm2": round(sum(result.atlas[i].area for i in ids), 1),
        "controlled_face_ids": sorted(set(ids) & controlled),
        "touches_controlled": bool(set(ids) & controlled),
        "reason": reason,
    }


# --- mesh --------------------------------------------------------------------------------------


def _encode_mesh(tess) -> bytes:
    """Positions, per-face-smoothed normals and face ids, little-endian.

    Un-welded, because WebGL2 has no primitive id in the fragment shader, so the CAD face id has
    to be a vertex attribute. That also lets normals be averaged per face rather than per vertex,
    which keeps machined edges sharp instead of rounding every one of them off.
    """
    tris, verts, face_id = tess.triangles, tess.vertices, tess.face_id
    corners = verts[tris.ravel()]

    a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    tri_normals = np.cross(b - a, c - a)
    keys = np.stack([tris.ravel(), np.repeat(face_id, 3)], axis=1)
    _, group, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    accumulated = np.zeros((counts.size, 3), dtype=np.float64)
    np.add.at(accumulated, group, np.repeat(tri_normals, 3, axis=0))
    lengths = np.linalg.norm(accumulated, axis=1, keepdims=True)
    normals = np.divide(
        accumulated, lengths, out=np.zeros_like(accumulated), where=lengths > 1e-12
    )[group]

    return (
        MESH_MAGIC
        + struct.pack("<I", corners.shape[0])
        + corners.astype("<f4").tobytes()
        + normals.astype("<f4").tobytes()
        + np.repeat(face_id.astype(np.uint32), 3).astype("<u4").tobytes()
    )
