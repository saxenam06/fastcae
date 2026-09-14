"""HTTP surface.

Routes contain no logic. Each unpacks a request, calls one function from the engine, and packs the
result. Anything a route could do that the engine cannot is something nothing else driving the
engine would be able to do.

**Nothing is loaded at startup.** The server begins with no project open, because the first thing
a person does is choose what to extract. A server that pre-loads one part is a server built around
that part.
"""

from __future__ import annotations

import json
import struct
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Any, Literal

import numpy as np
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .. import cache
from .. import spec as specs
from .. import study as studies
from .. import variants as variants_lib
from ..extract import Extraction
from ..extract import run as run_extract
from ..features import extent as feature_extent
from ..features import neighbours as feature_neighbours
from ..generate import Field as DistanceField
from ..generate import designs as design_space
from ..generate import field_for
from ..generate.campaigns import Card as CampaignCard
from ..generate.campaigns import campaigns as campaigns_of
from ..generate.campaigns import estimate as campaign_estimate
from ..generate.campaigns import go as launch_campaign
from ..generate.campaigns import screen_sample
from ..generate.cells import exposed_faces
from ..generate.design import Design, Parameter, apply, host_from, rib_on
from ..generate.field import field_key as key_of_field
from ..generate.formations import FORMATIONS
from ..generate.primitives import Slab
from ..generate.session import (
    Session,
    _present,
    accept,
    built_blob,
    campaign_pipeline,
    design_from_spec,
    design_from_study,
    design_paths,
    discard_variant,
    drop_rule,
    go,
    hand,
    keep_built,
    kept_of,
    new_variant,
    open_variant,
    paths,
    run_design,
    run_designs,
    runs,
    save_variant,
    undo,
    variant_sample,
    variant_shown,
    varied,
    verdict,
    view,
)
from ..generate.shading import corner_normals
from ..generate.surface import CODE as SURFACE_CODE
from ..generate.surface import Surface, contour, surface_for
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
    field: DistanceField | None = None
    surface: Surface | None = None
    surface_blob: bytes | None = None

    # Generate. Parameters are somebody's choices and live only for the session: until there is a
    # place to confirm and keep them, writing them down would be inventing provenance.
    parameters: list[Parameter] = dataclass_field(default_factory=list)
    next_parameter: int = 0
    design: DistanceField | None = None
    design_surface: Surface | None = None
    design_blob: bytes | None = None

    # Formations. The design space is opened once and every design is made in it.
    space: design_space.DesignSpace | None = None
    made: design_space.Design | None = None
    made_blob: bytes | None = None

    # The rib work: the card - the draft of the study - the study and designs made from it; one
    # session, shared with the agent when there is one, so the card the agent fills is the one
    # the engineer sees, and a design made anywhere is the one the Generate tab shows.
    intent: Any = None
    agent: Any = None
    made_verdict: dict | None = None

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

    reuse: bool = True
    """Whether a result already read from these files may be returned instead of reading again.

    False is what *re-extract* means. Not a cache repair - the cache is keyed on the content of the
    files and on the code that read them, so it cannot go stale on its own - but a way to say "read
    it again" when the reason sits outside both.
    """


class FieldRequest(BaseModel):
    spacing_mm: float | None = Field(default=None, gt=0.0)
    """Voxel size. Absent means the one derived from the model's own diagonal."""

    headroom_mm: float | None = Field(default=None, gt=0.0)
    """How far past the part the grid reaches, and so how tall a rib may be.

    The grid is fixed, so this is a hard ceiling on every design built on the field - and it is
    paid for in cells, which is why it is asked for rather than assumed generous.
    """

    reuse: bool = True


class RolesRequest(BaseModel):
    """Which CAD file designs grow from."""

    baseline: str = Field(min_length=1)


class SpaceRequest(BaseModel):
    """Which grid designs are made on. Unset: a quarter of the root fillet."""

    spacing_mm: float | None = Field(default=None, gt=0.0)


class ApprovalRequest(BaseModel):
    approved: bool
    clearance_mm: float | None = Field(default=None, ge=0.0)


class DesignSettings(BaseModel):
    """For each zone, a formation and its lever values."""

    zones: dict[str, dict]


# --- session -----------------------------------------------------------------------------------


@app.get("/api/state")
def get_state() -> dict:
    """Where the session is. Polled by the UI, and the seed of the agent state view."""
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
    _state.field = None
    _forget_parameters()
    _forget_space()
    return get_state()


@app.post("/api/field")
def post_field(request: FieldRequest) -> dict:
    """Build the distance field for what is open, or return the one already built.

    Separate from extraction because it belongs to Generate rather than to reading the files, and
    because it is the expensive one: minutes on a large part at a fine voxel, against seconds for
    everything else. Both are kept, so neither is paid twice for the same inputs.
    """
    result = extracted()
    if result.tess is None or _state.project is None:
        raise HTTPException(409, "no geometry was read")

    field, hit = field_for(
        _state.project.root,
        result.tess,
        result.cad_digest,
        spacing_mm=request.spacing_mm,
        reuse=request.reuse,
        headroom_mm=request.headroom_mm,
    )
    _state.field = field
    _state.surface = None
    _state.surface_blob = None
    _forget_parameters()
    return _field_row(field, hit)


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


# Voxel sizes the interface offers. Round numbers rather than one derived from the part, because
# a size nobody can name is a size nothing is ever cached for - and the derived 2.37 mm on the part
# in assets/ was five minutes of work behind a button that looked like the others.
OFFERED_SPACINGS_MM = (20.0, 10.0, 5.0, 2.5)


@app.get("/api/field/options")
def get_field_options() -> list[dict]:
    """The voxel sizes on offer, and which of them are already built.

    A button that costs five minutes and a button that costs nothing should not look alike.
    """
    result = extracted()
    if result.tess is None or _state.project is None:
        raise HTTPException(409, "no geometry was read")

    root = _state.project.root
    out = []
    for spacing in OFFERED_SPACINGS_MM:
        field_key = key_of_field(result.tess, result.cad_digest, spacing_mm=spacing)
        surface_key = cache.key_for(field_key, code=SURFACE_CODE)
        out.append(
            {
                "spacing_mm": spacing,
                "field_ready": cache.entry(root, "field", field_key).exists,
                "surface_ready": cache.entry(root, "surface", surface_key).exists,
            }
        )
    return out


@app.get("/api/field")
def get_field() -> dict:
    """What the field holds, or 409 if none has been built. Never builds one."""
    if _state.field is None:
        raise HTTPException(409, "no field has been built")
    return _field_row(_state.field, True)


@app.get("/api/field/surface")
def get_field_surface() -> dict:
    """Contour the field, and say what came out.

    Reported beside the same measurements taken on the B-rep surface, because the only useful
    question about a reconstruction is how it differs from the thing it reconstructs.
    """
    result = extracted()
    if _state.field is None:
        raise HTTPException(409, "no field has been built")
    if _state.surface is None:
        _state.surface, _ = surface_for(
            _state.project.root if _state.project else Path("."),
            _state.field,
            _state.field.key,
            face_ids_from=result.tess,
        )
        _state.surface_blob = None

    surface = _state.surface
    boundary, non_manifold, winding = surface.faults
    exact = result.exact
    volume = surface.volume_mm3
    return {
        "spacing_mm": surface.spacing_mm,
        "vertices": surface.n_vertices,
        "triangles": surface.n_triangles,
        "volume_cm3": round(volume / 1e3, 1),
        "area_m2": round(surface.area_mm2 / 1e6, 4),
        "watertight": surface.watertight,
        "boundary_edges": boundary,
        "non_manifold_edges": non_manifold,
        "inconsistent_edges": winding,
        "brep_volume_cm3": None if exact is None else round(exact.volume_cm3, 1),
        "volume_error_pct": (
            None
            if exact is None
            else round(abs(volume / 1e3 - exact.volume_cm3) / exact.volume_cm3 * 100, 3)
        ),
        "brep_triangles": None if result.tess is None else result.tess.n_triangles,
        "shell_cells": int(_state.field.shell().size),
        "exposed_faces": int(exposed_faces(_state.field.inside).size),
        "solid_cells": _state.field.n_inside,
        "band_cells": _state.field.n_band,
    }


@app.get("/api/field/voxels")
def get_field_voxels() -> Response:
    """The field's own cells, as one integer per visible face.

    The field drawn as itself rather than as a reconstruction of itself. A contour is a fit - one
    vertex per cell placed by least squares - and it can be wrong where the field is not. These are
    the cells as stored.

    Only the faces that show, and one integer each: a cell has six faces and you see at most three,
    so drawing whole cubes is six times the work for the same picture - forty-eight million vertices
    a frame at 2.5 mm against ten point eight.
    """
    if _state.field is None:
        raise HTTPException(409, "no field has been built")

    return Response(
        content=_voxel_blob(_state.field.grid, exposed_faces(_state.field.inside)),
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-cache"},
    )


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


@app.get("/api/field/mesh")
def get_field_mesh() -> Response:
    """The contoured surface, in the same format the B-rep tessellation is served in.

    Identical format on purpose: the interface draws both at once to compare them, and a second
    format would mean a second path through the renderer that could differ for its own reasons.
    """
    if _state.surface is None:
        get_field_surface()
    assert _state.surface is not None
    if _state.surface_blob is None:
        surface = _state.surface
        # Shaded as one surface rather than by the CAD face ids it borrowed for picking. Those ids
        # fragment a contour into thousands of patches, and a smooth casting comes back crazed.
        _state.surface_blob = _encode_mesh(
            surface, normals=corner_normals(surface.vertices, surface.triangles)
        )
    return Response(
        content=_state.surface_blob,
        media_type="application/octet-stream",
        headers={
            "Content-Length": str(len(_state.surface_blob)),
            "Cache-Control": "no-cache",
        },
    )


@app.post("/api/reset")
def post_reset() -> dict:
    """Close the project and go back to a blank slate."""
    _state.project = None
    _state.extraction = None
    _state.mesh_blob = None
    _state.field = None
    _state.surface = None
    _state.surface_blob = None
    _forget_parameters()
    _forget_space()
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


class Seed(BaseModel):
    face_id: int
    grow_deg: float = Field(default=0.0, ge=0.0, le=180.0)
    """Grow from this face across every edge shallower than this; zero is the face alone."""


class SeedsRequest(BaseModel):
    seeds: list[Seed] = Field(min_length=1)


@app.post("/api/select/seeds")
def post_select_seeds(request: SeedsRequest) -> dict:
    """A selection made click by click: each face clicked, grown by its own angle or not at all.

    One angle over every click grew faces clicked later as far as the first - the angle belongs to
    the click, not to the selection.
    """
    result = extracted()
    if result.atlas is None:
        raise HTTPException(409, "no geometry")
    unknown = [s.face_id for s in request.seeds if s.face_id not in result.atlas.faces]
    if unknown:
        raise HTTPException(404, f"no face {unknown[0]}")
    ids: set[int] = set()
    for seed in request.seeds:
        if seed.grow_deg > 0:
            ids |= result.atlas.grow([seed.face_id], max_dihedral_deg=seed.grow_deg)
        else:
            ids.add(seed.face_id)
    grown = sum(1 for s in request.seeds if s.grow_deg > 0)
    return _selection(result, ids, f"{len(request.seeds)} faces clicked, {grown} of them grown")


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
    feature = _feature(result, feature_id)
    return _selection(result, set(feature.face_ids), feature.describe())


class RefsRequest(BaseModel):
    refs: list[str] = Field(min_length=1)
    """Features and faces by name: ``hole:3``, ``face:1453``."""


@app.post("/api/select/refs")
def post_select_refs(request: RefsRequest) -> dict:
    """Every face of some features and faces at once - to show on the part what a study names,
    two hundred holes as quickly as one."""
    result = extracted()
    assert result.features is not None
    faces: set[int] = set()
    missing = []
    for ref in request.refs:
        found = result.features.get(ref)
        if found is None:
            missing.append(ref)
        else:
            faces |= set(found.face_ids)
    if missing:
        raise HTTPException(404, f"no {', '.join(missing[:5])} on the part")
    return _selection(result, faces, f"{len(request.refs)} named")


# --- generate ----------------------------------------------------------------------------------


class RibRequest(BaseModel):
    """Author a rib from a face selection. The least a person has to say."""

    face_ids: list[int] = Field(min_length=1)
    name: str = Field(default="rib", min_length=1, max_length=60)
    thickness_mm: float = Field(gt=0.0)
    high_mm: float = Field(gt=0.0)
    span: float = Field(default=0.9, gt=0.0, le=1.0)


class DesignRequest(BaseModel):
    values_mm: list[float]
    blend_mm: float = Field(default=0.0, ge=0.0)


def _base_field() -> DistanceField:
    if _state.field is None:
        raise HTTPException(409, "no field has been built to put a parameter on")
    return _state.field


def _design_field() -> DistanceField:
    """The design if one has been evaluated, otherwise the part as it came."""
    return _state.design if _state.design is not None else _base_field()


@app.post("/api/parameters")
def post_parameter(request: RibRequest) -> dict:
    """Put a rib on a selection of faces.

    The placement is decided once, here: which faces it stands on, which way it runs and how thick
    it is. After that the **height is the dial**, because that is what a campaign sweeps and the
    rest is a decision about what the rib is rather than how much of it there is.
    """
    result = extracted()
    base = _base_field()
    if result.tess is None:
        raise HTTPException(409, "no geometry was read")

    try:
        vertices, normal = host_from(
            result.tess.vertices, result.tess.triangles, result.tess.face_id, set(request.face_ids)
        )
        slab = rib_on(base, vertices, normal, request.thickness_mm, span=request.span)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error

    # Capped by what the grid can hold rather than left to fail at the far end of a slider: a
    # slider whose top end raises an error is a slider that lies about its own range.
    ceiling = _headroom_for(base, slab)
    if ceiling <= base.grid.spacing_mm:
        raise HTTPException(400, "there is no room above that face for a rib")

    parameter = Parameter(
        id=f"rib:{_state.next_parameter}",
        name=request.name,
        slab=slab,
        low_mm=0.0,
        high_mm=min(request.high_mm, ceiling),
        default_mm=0.0,
        host_face_ids=tuple(sorted(set(request.face_ids))),
    )
    _state.parameters.append(parameter)
    _state.next_parameter += 1
    _forget_design()
    return _parameter_row(parameter, ceiling)


@app.get("/api/parameters")
def get_parameters() -> list[dict]:
    base = _base_field()
    return [_parameter_row(p, _headroom_for(base, p.slab)) for p in _state.parameters]


@app.delete("/api/parameters/{parameter_id}")
def delete_parameter(parameter_id: str) -> list[dict]:
    remaining = [p for p in _state.parameters if p.id != parameter_id]
    if len(remaining) == len(_state.parameters):
        raise HTTPException(404, f"no parameter {parameter_id!r}")
    _state.parameters = remaining
    _forget_design()
    return get_parameters()


@app.post("/api/design")
def post_design(request: DesignRequest) -> dict:
    """Evaluate one point in the design space.

    A design is a digest and these numbers. The field is regenerated from them rather than stored,
    so the same numbers give the same part on any machine and on any day - which is the property a
    campaign's data rests on.
    """
    base = _base_field()
    if len(request.values_mm) != len(_state.parameters):
        raise HTTPException(
            400, f"{len(_state.parameters)} parameters but {len(request.values_mm)} values"
        )

    started = time.perf_counter()
    try:
        field = apply(base, _state.parameters, request.values_mm, blend_mm=request.blend_mm)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    seconds = time.perf_counter() - started

    _state.design = field
    _state.design_surface = None
    _state.design_blob = None

    design = Design(base_digest=base.source_digest, values=tuple(request.values_mm))
    added = field.volume_mm3() - base.volume_mm3()
    return {
        "key": design.key(),
        "values_mm": list(request.values_mm),
        # What was asked for and what the band could carry. A fillet wider than the band would be
        # blending against a clamped distance rather than a real one, so it is capped - and the
        # ceiling is reported, because a slider that stops working partway along without saying so
        # is indistinguishable from a slider that does nothing.
        "blend_mm": min(request.blend_mm, base.reach_mm),
        "blend_ceiling_mm": round(base.reach_mm, 2),
        "volume_cm3": round(field.volume_mm3() / 1e3, 1),
        "added_cm3": round(added / 1e3, 1),
        "base_volume_cm3": round(base.volume_mm3() / 1e3, 1),
        "seconds": round(seconds, 3),
    }


@app.get("/api/design/voxels")
def get_design_voxels(only: str = "added") -> Response:
    """The design's cells, in the format the base field's arrive in.

    ``added`` by default: the cells this design has that the bare part does not. That is what a
    person authoring a parameter is looking at - a rib standing on a part they can still see and
    still click - where the whole design drawn as cells would bury the geometry under a blocky copy
    of itself and leave nothing to pick.
    """
    field = _design_field()
    grid = field.grid
    if only == "added":
        # Nothing placed yet means nothing added. Falling back to the whole part here would bury
        # the geometry under a blocky copy of itself before a person had asked for anything.
        base = _base_field()
        solid = field.inside & ~base.inside if _state.design is not None else _empty(base)
    elif only == "all":
        solid = field.inside
    else:
        raise HTTPException(400, f"{only!r} is not 'added' or 'all'")
    return Response(
        content=_voxel_blob(grid, exposed_faces(solid)),
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/api/design/surface")
def get_design_surface() -> dict:
    """Contour the design.

    Not cached, unlike the base field's: a design is one point of many and is rarely asked for
    twice, so keeping every one would fill a disk with results nothing will look at again.
    """
    result = extracted()
    if _state.design_surface is None:
        _state.design_surface = contour(_design_field(), face_ids_from=result.tess)
        _state.design_blob = None

    surface = _state.design_surface
    boundary, non_manifold, winding = surface.faults
    return {
        "spacing_mm": surface.spacing_mm,
        "vertices": surface.n_vertices,
        "triangles": surface.n_triangles,
        "volume_cm3": round(surface.volume_mm3 / 1e3, 1),
        "watertight": surface.watertight,
        "boundary_edges": boundary,
        "non_manifold_edges": non_manifold,
        "inconsistent_edges": winding,
    }


@app.get("/api/design/mesh")
def get_design_mesh() -> Response:
    if _state.design_surface is None:
        get_design_surface()
    assert _state.design_surface is not None
    if _state.design_blob is None:
        surface = _state.design_surface
        _state.design_blob = _encode_mesh(
            surface, normals=corner_normals(surface.vertices, surface.triangles)
        )
    return Response(
        content=_state.design_blob,
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-cache"},
    )


# --- formations ---------------------------------------------------------------------------------


def _project() -> Project:
    if _state.project is None:
        raise HTTPException(409, "no project is open")
    return _state.project


def _forget_space() -> None:
    _state.space = None
    _state.made = None
    _state.made_blob = None
    _state.made_verdict = None


@app.get("/api/zones")
def get_zones() -> dict:
    """The project's zones and whether each is approved, and what is protected."""
    project = _project()
    return {
        "zones": [{**z, "summary": _zone_summary(z)} for z in project.data().get("zones", [])],
        "protected": design_space.protection(project),
    }


@app.post("/api/zones/{zone_id}")
def post_zone(zone_id: str, request: ApprovalRequest) -> dict:
    try:
        design_space.approve_zone(_project(), zone_id, request.approved)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    _forget_space()
    return get_zones()


@app.post("/api/protected")
def post_protected(request: ApprovalRequest) -> dict:
    design_space.approve_protection(_project(), request.approved, request.clearance_mm)
    _forget_space()
    return get_zones()


@app.get("/api/formations")
def get_formations() -> dict:
    """Every formation and its levers, and the values every rib shares from the rules."""
    rules = design_space.Rules(**_project().data().get("rules", {}))
    return {
        "formations": [
            {
                "name": f.name,
                "label": f.label,
                "levers": [
                    {
                        "name": lever.name,
                        "label": lever.label,
                        "low": lever.low,
                        "high": lever.high,
                        "step": lever.step,
                        "unit": lever.unit,
                        "integer": lever.integer,
                    }
                    for lever in f.levers
                ],
            }
            for f in FORMATIONS.values()
        ],
        "fixed": {
            "root_fillet_mm": rules.root_fillet_mm,
            "edge_round_mm": rules.edge_round_mm,
            "draft_deg": rules.draft_used_deg,
        },
        "rules": [
            {"name": name, "basis": basis, "assumed": assumed}
            for name, basis, assumed in rules.basis
        ],
    }


@app.post("/api/designspace")
def post_design_space(request: SpaceRequest) -> dict:
    """Open the project for designing: the baseline, its contour, a window per zone.

    Minutes the first time on a large part, and kept on disk after.
    """
    result = extracted()
    project = _project()
    try:
        _state.space = design_space.DesignSpace.open(project, result, spacing_mm=request.spacing_mm)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    _state.made = None
    _state.made_blob = None
    return _space_row(_state.space)


@app.post("/api/designs")
def post_designs(request: DesignSettings) -> dict:
    """Make the design these settings describe, and say what it is and what the checks found."""
    if _state.space is None:
        raise HTTPException(409, "the design space is not open")
    try:
        made = _state.space.generate(request.zones)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    _state.made = made
    _state.made_blob = None
    return _design_row(made)


@app.get("/api/designs/current/mesh")
def get_current_design_mesh() -> Response:
    """The new surfaces of the current design - ribs and fillets - to draw over the part."""
    if _state.made is None:
        raise HTTPException(409, "no design has been made")
    if _state.made_blob is None:
        _state.made_blob = _changed_blob(_state.made)
    return Response(
        content=_state.made_blob,
        media_type="application/octet-stream",
        headers={"Content-Length": str(len(_state.made_blob)), "Cache-Control": "no-cache"},
    )


def _zone_summary(zone: dict) -> str:
    region = zone["region"]
    span = (region["theta_to_deg"] - region["theta_from_deg"]) % 360.0 or 360.0
    hosts = {
        "below": "standing on a floor",
        "above": "hanging from a ceiling",
        "between": "spanning between walls",
    }
    return (
        f"{region['theta_from_deg']:.0f}–{(region['theta_from_deg'] + span) % 360:.0f} deg, "
        f"r {region['r_inner_mm']:.0f}–{region['r_outer_mm']:.0f} mm, "
        f"{region['depth_mm']:.0f} mm deep, ribs {hosts.get(zone['host'], zone['host'])}"
    )


def _space_row(space: design_space.DesignSpace) -> dict:
    return {
        "zones": [{**z.to_dict(), "summary": _zone_summary(z.to_dict())} for z in space.zones],
        "spacing_mm": space.base.grid.spacing_mm,
        "base_volume_cm3": round(space.surface.volume_mm3 / 1e3, 1),
        "base_faults": list(space.surface.faults),
        "radius_mm": space.radius_mm,
        "density": space.density,
    }


def _design_row(made: design_space.Design) -> dict:
    stats = made.stats
    return {
        "digest": made.digest,
        "outcome": made.outcome,
        "settings": made.settings,
        "findings": [
            {
                "check": f.check,
                "outcome": f.outcome,
                "reason": f.reason,
                "rule": f.rule,
                "assumed": f.assumed,
                "where": None if f.where is None else [round(v, 1) for v in f.where],
                "value": None if f.value is None else round(f.value, 2),
            }
            for f in made.findings
        ],
        "stats": {
            **{
                k: (round(v, 3) if isinstance(v, float) else v)
                for k, v in stats.items()
                if k != "seconds"
            },
            "seconds": {k: round(v, 2) for k, v in stats["seconds"].items()},
        },
    }


def _empty(field: DistanceField) -> np.ndarray:
    return np.zeros(field.inside.shape, dtype=bool)


def _forget_design() -> None:
    _state.design = None
    _state.design_surface = None
    _state.design_blob = None


def _forget_parameters() -> None:
    """Levers belong to the part they were placed on.

    A parameter names faces of one geometry, so carrying it into another project would put a rib on
    whatever happened to share that face number. Numbering restarts too: an id that came back would
    make one value vector mean two different things.
    """
    _state.parameters = []
    _state.next_parameter = 0
    _forget_design()


def _headroom_for(base: DistanceField, slab: Slab) -> float:
    """The tallest this rib can be before it runs off the edge of the grid.

    Reported rather than discovered. The grid is fixed, so past its edge is not "smaller" but
    "absent" - and a slider that silently stops working partway along is how that was found the
    first time.

    A rib grows only along ``up``, so its footprint is fixed and the only corners that move are the
    four on top. The limit is whichever of them reaches a wall of the grid first.
    """
    origin = np.asarray(base.grid.origin)
    far = origin + (np.asarray(base.grid.shape) - 1) * base.grid.spacing_mm
    axes = slab.frame()
    up = axes[2]

    signs = np.array([[-1.0, -1.0], [-1.0, 1.0], [1.0, -1.0], [1.0, 1.0]])
    footprint = np.asarray(slab.origin) + signs @ np.stack(
        [axes[0] * slab.length_mm / 2.0, axes[1] * slab.thickness_mm / 2.0]
    )

    room = np.full(3, np.inf)
    for axis in range(3):
        if abs(up[axis]) < 1e-9:
            continue
        wall = far[axis] if up[axis] > 0 else origin[axis]
        room[axis] = float(((wall - footprint[:, axis]) / up[axis]).min())
    return float(max(room.min(), 0.0))


def _parameter_row(parameter: Parameter, ceiling_mm: float) -> dict:
    slab = parameter.slab
    return {
        "id": parameter.id,
        "name": parameter.name,
        "kind": "rib",
        "low_mm": round(parameter.low_mm, 2),
        "high_mm": round(parameter.high_mm, 2),
        "default_mm": round(parameter.default_mm, 2),
        "ceiling_mm": round(ceiling_mm, 2),
        "length_mm": round(slab.length_mm, 1),
        "thickness_mm": round(slab.thickness_mm, 1),
        "origin_mm": [round(v, 1) for v in slab.origin],
        "up": [round(float(v), 3) for v in slab.frame()[2]],
        "host_face_ids": list(parameter.host_face_ids),
    }


# --- rows --------------------------------------------------------------------------------------


def _field_row(field: DistanceField, from_cache: bool) -> dict:
    return {
        "spacing_mm": field.grid.spacing_mm,
        "shape": list(field.grid.shape),
        "cells": field.grid.n_cells,
        "band_cells": field.n_band,
        "solid_cells": field.n_inside,
        "reach_mm": round(field.reach_mm, 3),
        "headroom_mm": round(field.headroom_mm, 1),
        "volume_cm3": round(field.volume_mm3() / 1e3, 1),
        "from_cache": from_cache,
    }


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


def _encode_mesh(
    tess, normals: np.ndarray | None = None, standing: np.ndarray | None = None
) -> bytes:
    """Pack a surface for the renderer. The format, and why it is that format, is in
    :mod:`fastcae.api.mesh`."""
    return mesh_format.encode(tess.vertices, tess.triangles, tess.face_id, normals, standing)


def _changed_blob(design) -> bytes:
    """The surfaces a design changes, drawn down to the part, each vertex saying how far it stands
    off it - what the viewer draws over the part it already has."""
    changed, standing = design.changed_surface()
    return _encode_mesh(
        changed, normals=corner_normals(changed.vertices, changed.triangles), standing=standing
    )


# --- the spec, and designs made from it -----------------------------------------------------------


class SpecDesignRequest(BaseModel):
    fidelity: Literal["preview", "full"] = "preview"
    levers: dict[str, float] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    selection: list[int] = Field(default_factory=list)
    """The faces selected on the part when the engineer wrote."""
    role: Literal["auto", "host", "supports", "keep_out"] = "auto"
    """What the engineer said the selection is for; ``auto`` leaves it to the agent."""


def _intent() -> Session:
    """The rib work on the open project: the study's draft, read back from the study when the
    project opens, and designs made from the study."""
    project, result = _project(), extracted()
    held = _state.intent
    if held is None or held.project.root != project.root or held.extraction is not result:
        _state.intent = Session(project, result)
        _state.agent = None
    return _state.intent


@app.get("/api/spec")
def get_spec() -> dict:
    """The active spec: its versions, and the current one in full."""
    spec = specs.active(_project())
    if spec is None:
        return {"spec": None}
    return {
        "spec": spec.name,
        "versions": [
            {"version": v.version, "created": v.created, "note": v.note, "changes": v.changes}
            for v in spec.versions
        ],
        "current": spec.current.model_dump(),
    }


@app.post("/api/spec/design")
def post_spec_design(request: SpecDesignRequest) -> dict:
    """A design from the active spec, and its verdict."""
    context = _intent()
    reply = design_from_spec(context, request.fidelity, request.levers)
    if "cannot" in reply:
        raise HTTPException(409, reply["cannot"])
    _hold_design(context)
    return reply


@app.get("/api/study")
def get_study() -> dict:
    """The active study: its versions, the current one in full, what it holds that nothing
    enforces yet, and what nobody confirmed."""
    study = studies.active(_project())
    if study is None:
        return {"study": None}
    current = study.current
    return {
        "study": study.name,
        "versions": [
            {"version": v.version, "created": v.created, "note": v.note, "changes": v.changes}
            for v in study.versions
        ],
        "current": current.model_dump(),
        "shown": studies.shown(current),
        "open": studies.open_items(current),
        "assumed": studies.assumed(current),
    }


class StudyRule(BaseModel):
    id: str = Field(min_length=2)
    """A rule, preference or objective of the draft, by the id Design a variant shows."""


class StudyPaths(BaseModel):
    draft: bool = True
    """The draft's suggested design, rather than the study's as accepted."""
    design: int | None = None
    """One of the designs Go made, by its index, rather than a suggested one."""
    run: str | None = None
    """The kept run of Go the design is of; else the study as accepted."""


class StudyGo(BaseModel):
    n: int | None = Field(default=None, ge=1, le=20000)
    """How many designs to keep: the study's target when not given."""
    seed: int | None = None
    """Where the spread starts: the study's seed when not given."""
    off: dict[Literal["blocks", "rules", "checks"], list[str]] = Field(default_factory=dict)
    """What this campaign switches off for itself alone: blocks and rules by id, screening checks
    by name. The study is left as it is."""


@app.get("/api/study/draft")
def get_study_draft() -> dict:
    """Design a variant: the draft of the study's next version - every block by what its ribs stand
    on, end on and keep clear of, its settings and rules, what is needed and what cannot be built
    yet - each marked where it differs from the study as accepted."""
    return {"draft": view(_intent())}


@app.post("/api/study/accept")
def post_study_accept() -> dict:
    """Write the draft as the study's next version, and the draft as read back from it."""
    context = _intent()
    reply = accept(context)
    if "cannot" in reply:
        raise HTTPException(409, reply["cannot"])
    return {**reply, "draft": view(context)}


@app.post("/api/study/undo")
def post_study_undo() -> dict:
    """Forget what was not accepted: the draft as the study has it."""
    return {"draft": undo(_intent())}


@app.post("/api/study/rules/drop")
def post_study_rule_drop(request: StudyRule) -> dict:
    """Take out a rule the words put in or the part suggested - or a preference, an objective."""
    context = _intent()
    try:
        drop_rule(context, request.id)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    return {"draft": view(context)}


class StudyHand(BaseModel):
    """Something done by hand on Design a variant: ``action`` - add, stand_on, end_on, other_side,
    setting, keep_clear, remove, confirm, designs - and what it takes: ``block``, ``add``, ``refs``,
    ``name`` with a ``value``, ``low``/``high``/``step`` or ``options``, ``clearance_mm``,
    ``rule``, ``n``, ``seed``."""

    action: str
    block: str | None = None
    add: str | None = None
    refs: list[str] | None = None
    name: str | None = None
    value: float | str | None = None
    low: float | None = None
    high: float | None = None
    step: float | None = None
    options: list[float | str] | None = None
    clearance_mm: float | None = None
    rule: str | None = None
    kind: str | None = None
    """For ``rule``: the kind of rule a variant holds - one the pipeline checks."""
    params: dict[str, Any] | None = None
    """For ``rule``: what the rule needs, by name - ``mm``, ``ratio``, ``radius_mm``."""
    n: int | None = Field(default=None, ge=1, le=20000)
    seed: int | None = None
    selected: list[int] = Field(default_factory=list)
    """The faces selected on the part, which the action takes when it names nothing."""


@app.post("/api/study/hand")
def post_study_hand(request: StudyHand) -> dict:
    """The draft changed by hand on Design a variant - kept as the engineer's own, with what was
    done said in words - and the card as it now is."""
    context = _intent()
    action = request.model_dump(exclude={"selected"}, exclude_none=True)
    card = hand(context, action, request.selected)
    if isinstance(card.get("refused"), str):
        raise HTTPException(409, card["refused"])
    return {"draft": card}


@app.post("/api/study/paths")
def post_study_paths(request: StudyPaths) -> dict:
    """Where ribs would go, as lines on the part, before anything is made: the draft's suggested
    design, the study's, or one of the designs Go made."""
    context = _intent()
    if request.design is not None:
        reply = design_paths(context, request.design, request.run)
    else:
        reply = paths(context, draft=request.draft)
    if "cannot" in reply:
        raise HTTPException(409, reply["cannot"])
    return reply


class StudyDesign(BaseModel):
    fidelity: Literal["preview", "full"] = "preview"
    design: int | None = None
    """One of the designs Go made, by its index; else the study's suggested point."""
    values: dict[str, dict[str, Any]] = Field(default_factory=dict)
    """Free settings at other values than suggested, by block and name."""
    run: str | None = None
    """The kept run of Go the design is of, built from the study version it was made from."""


@app.post("/api/study/design")
def post_study_design(request: StudyDesign) -> dict:
    """A design from the study - the draft accepted first, if it differs - at its suggested point,
    at one of the designs Go made, or at the values given; or one of a kept run's designs, from the
    study version that run was made from; and its verdict."""
    context = _intent()
    if request.run is None:
        draft = view(context)
        if draft.get("refused"):
            raise HTTPException(409, draft["cannot"])
        if draft["differs"]:
            written = accept(context)
            if "cannot" in written:
                raise HTTPException(409, written["cannot"])
    values = request.values
    if request.design is not None:
        designs = kept_of(context, request.run)
        if isinstance(designs, str):
            raise HTTPException(404, designs)
        if not 0 <= request.design < len(designs):
            raise HTTPException(404, f"there is no design {request.design}")
        values = designs[request.design]["values"]
    reply = design_from_study(context, request.fidelity, values, request.run)
    if "cannot" in reply:
        raise HTTPException(409, reply["cannot"])
    _hold_design(context)
    return reply


@app.get("/api/study/varied")
def get_study_varied(k: int = 30, run: str | None = None) -> dict:
    """The designs Go kept that differ most from each other - ``k`` of them, 5 to 100, of the study
    as accepted or of a kept ``run`` - each as a plan of its ribs, pads and holes over the outlines
    of what the study names."""
    reply = varied(_intent(), max(5, min(int(k), 100)), run)
    if "cannot" in reply:
        raise HTTPException(409, reply["cannot"])
    return reply


@app.post("/api/study/go")
def post_study_go(request: StudyGo) -> StreamingResponse:
    """Many designs from the study at once - the draft accepted first, if it differs - each placed
    and counted as it is done, as a stream of events."""
    context = _intent()

    def events():
        for event in go(context, request.n, seed=request.seed, off=dict(request.off)):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- variants: authored on Design a variant, kept in the library ---------------------------------


def _library(context: Session) -> list[dict]:
    """Every variant kept, as the library lists it - with the campaigns that used each."""
    used: dict[str, list[dict]] = {}
    for launched in campaigns_of(context):
        for kept in launched["variants"]:
            used.setdefault(kept["id"], []).append(
                {"run": launched["run"], "name": launched["name"], "version": kept["version"]}
            )
    return [variants_lib.listed(v, used.get(v.name)) for v in variants_lib.library(context.project)]


@app.get("/api/variants")
def get_variants() -> dict:
    """The project's variants - code, name, kind, where, how many combinations each allows, which
    campaigns used it - and the one being authored."""
    context = _intent()
    return {"variants": _library(context), "authoring": context.variant}


@app.get("/api/variants/{vid}")
def get_variant(vid: str) -> dict:
    """A variant of the library, read only: what it adds and where, what it may vary, its rules."""
    shown = variant_shown(_intent(), vid)
    if shown is None:
        raise HTTPException(404, f"there is no variant {vid}")
    return shown


@app.post("/api/variants/new")
def post_variant_new() -> dict:
    """A new variant to author, with nothing in it yet."""
    return {"draft": new_variant(_intent())}


@app.post("/api/variants/{vid}/open")
def post_variant_open(vid: str) -> dict:
    """A variant of the library, read back to change."""
    card = open_variant(_intent(), vid)
    if isinstance(card.get("refused"), str):
        raise HTTPException(404, card["refused"])
    return {"draft": card}


@app.get("/api/variant/draft")
def get_variant_draft() -> dict:
    """The variant being authored - a new one when none is."""
    context = _intent()
    if context.variant is None:
        return {"draft": new_variant(context)}
    return {"draft": view(context)}


@app.post("/api/variant/hand")
def post_variant_hand(request: StudyHand) -> dict:
    """The variant being authored, changed by hand on the card."""
    context = _intent()
    if context.variant is None:
        new_variant(context)
    action = request.model_dump(exclude={"selected"}, exclude_none=True)
    card = hand(context, action, request.selected)
    if isinstance(card.get("refused"), str):
        raise HTTPException(409, card["refused"])
    return {"draft": card}


class VariantSample(BaseModel):
    another: bool = False
    """A point drawn at random from what the variant allows, rather than its suggested one."""
    seed: int | None = None


@app.post("/api/variant/sample")
def post_variant_sample(request: VariantSample) -> dict:
    """The variant being authored at a point that passes - placed alone, repaired and screened -
    as lines on the part; or why none of the points tried does."""
    reply = variant_sample(_intent(), request.another, request.seed)
    if "cannot" in reply:
        raise HTTPException(409, reply["cannot"])
    return reply


class VariantSave(BaseModel):
    label: str | None = None


@app.post("/api/variant/save")
def post_variant_save(request: VariantSave) -> dict:
    """The variant being authored, kept in the library - created, or its changes saved - once one
    of its points passes."""
    context = _intent()
    reply = save_variant(context, request.label)
    if "cannot" in reply:
        raise HTTPException(409, reply["cannot"])
    return {**reply, "draft": view(context), "variants": _library(context)}


@app.post("/api/variant/discard")
def post_variant_discard() -> dict:
    """Forget what was not saved: the variant as kept, or nothing in it."""
    return {"draft": discard_variant(_intent())}


@app.post("/api/variants/{vid}/duplicate")
def post_variant_duplicate(vid: str) -> dict:
    context = _intent()
    try:
        copy = variants_lib.duplicate(context.project, vid)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    return {"id": copy, "variants": _library(context)}


@app.delete("/api/variants/{vid}")
def delete_variant(vid: str) -> dict:
    """A variant taken out of the library - its file moved aside; campaigns keep their copies."""
    context = _intent()
    try:
        variants_lib.delete(context.project, vid)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    if context.variant == vid:
        new_variant(context)
    return {"variants": _library(context)}


# --- campaigns, and the designs of each run ------------------------------------------------------


@app.get("/api/campaign")
def get_campaign() -> dict:
    """What a campaign runs, in the open: the stages a design goes through with what each takes
    and gives, the checks every design is screened and built by and the rules of thumb behind them
    with their sources, how designs are placed and drawn, the materials - and the campaigns
    launched so far."""
    return campaign_pipeline(_intent())


@app.post("/api/campaign/estimate")
def post_campaign_estimate(card: CampaignCard) -> dict:
    """How many designs a card's variants allow, each variant's share, and whether every one of
    them can be asked for."""
    reply = campaign_estimate(_project(), card)
    if "cannot" in reply:
        raise HTTPException(409, reply["cannot"])
    return reply


@app.post("/api/campaign/screen")
def post_campaign_screen(card: CampaignCard) -> dict:
    """A hundred designs drawn as the card would draw them, placed, repaired and screened - nothing
    kept: how many pass, why the rest do not, and how long the launch will take."""
    reply = screen_sample(_intent(), card)
    if "cannot" in reply:
        raise HTTPException(409, reply["cannot"])
    return reply


@app.post("/api/campaign/go")
def post_campaign_go(card: CampaignCard) -> StreamingResponse:
    """A campaign launched from its card, as a stream of events: each variant pooled alone, each
    design kept, then what it came to."""
    context = _intent()

    def events():
        for event in launch_campaign(context, card):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/campaigns")
def get_campaigns() -> list[dict]:
    """Every campaign launched for the open project, newest first."""
    return campaigns_of(_intent())


@app.get("/api/runs")
def get_runs() -> list[dict]:
    """Every run kept for the open project, newest first."""
    return runs(_intent())


@app.get("/api/runs/{run}/designs")
def get_run_designs(
    run: str,
    show: Literal["varied", "built", "all"] = "varied",
    k: int = 30,
    offset: int = 0,
    limit: int = 200,
    variant: str | None = None,
) -> dict:
    """A run's designs as the list shows them - the ``k`` that differ most, those built, or a page
    of all; only those holding one ``variant``, when asked - each with where it is in its stages,
    and how many are at each."""
    reply = run_designs(_intent(), run, show, k, offset, max(1, min(int(limit), 1000)), variant)
    if "cannot" in reply:
        raise HTTPException(404, reply["cannot"])
    return reply


@app.get("/api/runs/{run}/designs/{index}")
def get_run_design(run: str, index: int) -> dict:
    """One design of a run in full, with its verdict at each fidelity it was built at."""
    reply = run_design(_intent(), run, index)
    if "cannot" in reply:
        raise HTTPException(404, reply["cannot"])
    return reply


class RunBuild(BaseModel):
    fidelity: Literal["preview", "full"] = "preview"


@app.post("/api/runs/{run}/designs/{index}/build")
def post_run_build(run: str, index: int, request: RunBuild) -> dict:
    """One design of a run built - its field, from the study version the run was made from - and
    checked; kept beside the run with the surfaces it changes and its new metal as cells, so its
    field stage is done for good."""
    context = _intent()
    designs = kept_of(context, run)
    if isinstance(designs, str):
        raise HTTPException(404, designs)
    if not 0 <= index < len(designs):
        raise HTTPException(404, f"there is no design {index} in {run}")
    design = designs[index]
    reply = design_from_study(context, request.fidelity, design["values"], run, _present(design))
    if "cannot" in reply:
        raise HTTPException(409, reply["cannot"])
    assert context.made is not None
    made = context.made.design
    surface = _changed_blob(made)
    new_metal = made.composition.field.inside & ~made.base.inside
    cells = _voxel_blob(made.base.grid, exposed_faces(new_metal))
    keep_built(context, run, index, request.fidelity, reply, {"mesh": surface, "cells": cells})
    _hold_design(context)
    _state.made_blob = surface
    return run_design(context, run, index)


@app.get("/api/runs/{run}/designs/{index}/{kind}")
def get_run_built(
    run: str, index: int, kind: Literal["mesh", "cells"], fidelity: str = "preview"
) -> Response:
    """What was kept of a built design: the surfaces it changes, in the format the part arrives
    in, or its new metal as cells, in the format the field's arrive in."""
    blob = built_blob(_intent(), run, index, fidelity, kind)
    if blob is None:
        raise HTTPException(404, f"design {index} of {run} has not been built at {fidelity}")
    return Response(
        content=blob,
        media_type="application/octet-stream",
        headers={"Content-Length": str(len(blob)), "Cache-Control": "no-cache"},
    )


@app.get("/api/designs/current")
def get_current_design() -> dict:
    """The verdict of the design last made from a spec, by the agent or the Generate tab."""
    if _state.made_verdict is None:
        raise HTTPException(404, "no design has been made from a spec")
    return _state.made_verdict


def _hold_design(context: Session) -> None:
    if context.made is not None:
        _state.made = context.made.design
        _state.made_blob = None
        _state.made_verdict = verdict(context.made)


# --- the agent ------------------------------------------------------------------------------------


def _agent():
    from ..agent.runtime import Runtime

    context = _intent()
    if _state.agent is None:
        _state.agent = Runtime(context.project, context.extraction, context=context)
    return _state.agent


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
        for event in agent.turn(request.message, request.selection, request.role):
            if event["type"] == "changed" and "design" in event["what"]:
                _hold_design(agent.context)
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Simulate: the baseline's deck and answers, the variant route, the runner's jobs.
from . import simulate as simulate_routes  # noqa: E402 - after the state it reads

app.include_router(simulate_routes.router)
