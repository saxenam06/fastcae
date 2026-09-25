"""Designs over HTTP: the campaigns kept for the open project, what a new one would make, and every
stage of every design as the interface draws it.

A design is read from its folder as each stage left it, so a campaign the runner is making shows
each design's stages as they finish. Cells travel in the field's format, surfaces in the part's,
the design's mesh and its answer in the deck's.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import numpy as np
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse

from .. import runner
from ..designs import campaign
from ..geometry.cells import exposed_faces
from ..geometry.field import Grid
from ..ribs import networks
from ..simulate.fem import FEMesh

router = APIRouter()


def _open():  # type: ignore[no-untyped-def]
    from .app import _resume, _state

    if _state.project is None or _state.extraction is None:
        _resume()  # the server restarts whenever a source file is saved; pick the session back up
    if _state.project is None or _state.extraction is None:
        raise HTTPException(409, "no project is open")
    return _state.project, _state.extraction


def _folder(cid: str, nn: str) -> Path:
    project, _ = _open()
    try:
        return campaign.design_folder(project, f"{cid}/{nn}")
    except KeyError:
        raise HTTPException(404, f"there is no design {cid}/{nn}") from None


def _binary(content: bytes) -> Response:
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/api/campaigns")
def get_campaigns() -> dict[str, Any]:
    """Every campaign kept for the open project, newest first, each design with where each of its
    stages is - and the runner's job making one, if any."""
    project, _ = _open()
    jobs = [
        *runner.jobs(project=project.name, kind="ribs.", limit=5),
    ]
    live = next((j for j in jobs if j.get("state") in ("queued", "running")), None)
    from ..designs import target

    held = target.load(project)
    goal = (held or {}).get("headline") or {}
    # What the target reads on the objective itself: a design is judged on this, not on how much of
    # the bare part's strain energy is left.
    t_obj = (held or {}).get("objective") or {}
    t_ranked = (t_obj.get("ranked") or [None])[0]
    t_mesh = ((t_obj.get("meshes") or {}).get(t_ranked) or {}) if t_ranked else {}
    t_lead = t_mesh.get("robust_um")
    t_j = t_obj.get("j_robust")
    kept = campaign.campaigns(project)
    labels = dict(campaign.STAGES) | dict(networks.STAGES)
    for c in kept:
        # a campaign's own stages, in its own order: a network design has nine, a library design
        # five, and a grid shows a campaign in the stages it was made in
        c["stages"] = [{"id": s, "label": labels.get(s, s)} for s in c.get("stages") or []]
        for d in c["designs"]:
            mine = (d.get("metrics") or {}).get("headline") or {}
            d["vs_target"] = {
                k: mine[k] / goal[k]
                for k in ("work_Nmm", "largest_displacement_mm", "added_kg")
                if isinstance(mine.get(k), (int, float)) and goal.get(k)
            } or None
            o = d.get("objective")
            if o:
                if t_j:
                    o["j_share"] = o["j_robust"] / t_j
                if t_lead and o.get("lead_um") is not None:
                    o["lead_share"] = o["lead_um"] / t_lead
    return {
        "stages": [{"id": s, "label": label} for s, label in campaign.STAGES],
        "campaigns": kept,
        "job": live,
        "target": {
            "name": held.get("name", "target"),
            "metal_L": held.get("metal_L"),
            "headline": goal,
            "words": held.get("words"),
            "objective": {"j_robust": t_j, "lead_um": t_lead, "ranked": t_ranked},
        }
        if held
        else None,
    }


@router.get("/api/designs/{cid}/{nn}")
def get_design(cid: str, nn: str) -> dict[str, Any]:
    """One design in full: what it was made for, every stage's numbers, its plates."""
    folder = _folder(cid, nn)
    record = campaign._read(folder / "design.json") or {}
    record.pop("trace", None)
    plates = campaign._read(folder / "plates.json")
    if plates:
        record["plates"] = plates
    record["files"] = {
        name: (folder / name).is_file()
        for name in (
            "optimise.npz",
            "fine.npz",
            "design.step",
            "cad.npz",
            "mesh.npz",
            "result.npz",
            networks.RUNS,
        )
    }
    head = campaign._read(folder.parent / "campaign.json") or {}
    labels = dict(campaign.STAGES) | dict(networks.STAGES)
    order = head.get("stages") or [s for s, _ in campaign.STAGES]
    record["stage_order"] = [{"id": s, "label": labels.get(s, s)} for s in order]
    if record.get("fins"):
        record["counts"] = networks.counts(record)
    # the pass's and the polish's histories as the screen's chart reads a history: the objective
    # and the metal by iteration, whatever the optimiser called them
    for key in ("pass", "polish"):
        history = (record.get(key) or {}).get("history")
        if history:
            record[key] = {**record[key], "history": [_as_iteration(h) for h in history]}
    _beside_target(record)
    return record


def _as_iteration(h: dict[str, Any]) -> dict[str, Any]:
    if "volume_L" in h and "objective" in h:
        return h
    return {
        "iteration": h.get("iteration"),
        "cells": None,
        "volume_L": h.get("metal_L", h.get("volume_L")),
        "objective": h.get("j", h.get("objective")),
        "seconds": h.get("seconds"),
        "present": h.get("present"),
        "accepted": h.get("accepted"),
    }


@router.get("/api/designs/{cid}/{nn}/fins")
def get_fins(cid: str, nn: str, stage: str = "seed") -> dict[str, Any]:
    """A network design's fins at one of its stages: each fin's run in the part's frame - its base
    and its top - with its state at that stage and the reason when it was refused or dropped."""
    if stage not in networks.STEP_OF:
        raise HTTPException(404, f"no fins to show at the {stage} stage")
    folder = _folder(cid, nn)
    record = campaign._read(folder / "design.json") or {}
    runs = networks.load_runs(folder)
    step = networks.STEP_OF[stage]
    if step not in runs:
        raise HTTPException(409, "the design keeps no runs for this stage")
    states = {f["id"]: f for f in networks.fin_states(record, stage)}
    got = runs[step]
    fins_out = []
    for k, fin_id in enumerate(got["ids"]):
        state = states.get(fin_id) or {"id": fin_id, "state": "seeded", "reason": ""}
        fins_out.append(
            {
                **state,
                "base": np.round(got["base"][k], 2).tolist(),
                "top": np.round(got["top"][k], 2).tolist(),
            }
        )
    return {"stage": stage, "fins": fins_out, "counts": networks.counts(record)}


def _beside_target(record: dict[str, Any]) -> None:
    """Each of the design's signals with the target's beside it, and the headline as shares of the
    target's: the design is read against what it is to beat, not only the bare part."""
    from ..designs import target

    project, _ = _open()
    held = target.load(project)
    said = record.get("solve")
    if not held or not isinstance(said, dict):
        return
    theirs = {(r["name"], r["component"]): r.get("design") for r in held.get("signals", [])}
    for row in said.get("signals", []):
        row["target"] = theirs.get((row["name"], row["component"]))
    mine, goal = said.get("headline") or {}, held.get("headline") or {}
    record["target"] = {
        "name": held.get("name", "target"),
        "metal_L": held.get("metal_L"),
        "shares": {
            k: mine[k] / goal[k]
            for k in ("work_Nmm", "largest_displacement_mm", "added_kg")
            if isinstance(mine.get(k), (int, float)) and goal.get(k)
        },
    }


def _coarse(folder: Path) -> tuple[Grid, dict[str, np.ndarray]]:
    path = folder / "optimise.npz"
    if not path.is_file():
        raise HTTPException(409, "not optimised yet")
    with np.load(path) as data:
        arrays = {k: data[k] for k in data.files}
    grid = Grid(
        origin=tuple(float(v) for v in arrays["origin"]),
        spacing_mm=float(arrays["spacing"]),
        shape=tuple(int(v) for v in arrays["shape"]),
    )
    return grid, arrays


@router.get("/api/designs/{cid}/{nn}/voxels")
def get_voxels(cid: str, nn: str, iteration: int = -1) -> Response:
    """The metal a design's optimisation had added at an iteration (the last, by default), as cells
    of the grid it was found on."""
    from .app import _voxel_blob

    grid, arrays = _coarse(_folder(cid, nn))
    offsets = arrays["offsets"]
    steps = len(offsets) - 1
    if steps <= 0 or iteration < 0 or iteration >= steps:
        cells = arrays["added"]
    else:
        cells = arrays["snapshots"][offsets[iteration] : offsets[iteration + 1]]
    mask = np.zeros(grid.shape, bool)
    mask.ravel()[cells.astype(np.int64)] = True
    return _binary(_voxel_blob(grid, exposed_faces(mask)))


@router.get("/api/designs/{cid}/{nn}/domain")
def get_domain(cid: str, nn: str, iteration: int = -1) -> Response:
    """Where the optimisation could put metal - the design space on the rib planes - less what it
    had put there at an iteration (the last, by default)."""
    from .app import _voxel_blob

    grid, arrays = _coarse(_folder(cid, nn))
    if "domain" not in arrays or not len(arrays["domain"]):
        raise HTTPException(409, "optimised before rib planes")
    offsets = arrays["offsets"]
    steps = len(offsets) - 1
    if steps <= 0 or iteration < 0 or iteration >= steps:
        cells = arrays["added"]
    else:
        cells = arrays["snapshots"][offsets[iteration] : offsets[iteration + 1]]
    mask = np.zeros(grid.shape, bool)
    mask.ravel()[arrays["domain"].astype(np.int64)] = True
    mask.ravel()[cells.astype(np.int64)] = False
    return _binary(_voxel_blob(grid, exposed_faces(mask)))


@router.get("/api/designs/{cid}/{nn}/fine")
def get_fine(cid: str, nn: str) -> Response:
    """The metal added, on the design space's own grid, within the design space: what the plates
    were read from."""
    from . import designspace
    from .app import _voxel_blob

    folder = _folder(cid, nn)
    space = designspace.held.space
    if space is None:
        raise HTTPException(409, "the design space has not been read")
    path = folder / "fine.npz"
    if not path.is_file():
        raise HTTPException(409, "not read as plates yet")
    with np.load(path) as data:
        cells = data["cells"].astype(np.int64)
    mask = np.zeros(space.grid.shape, bool)
    mask.ravel()[cells] = True
    return _binary(_voxel_blob(space.grid, exposed_faces(mask)))


@router.get("/api/designs/{cid}/{nn}/cad")
def get_cad(cid: str, nn: str, show: Literal["new", "all"] = "new") -> Response:
    """The design's CAD as the renderer draws a part: its new faces - the ribs - only, to draw over
    the part, or all of it."""
    from ..geometry.shading import corner_normals
    from . import mesh as mesh_format

    project, extraction = _open()
    folder = _folder(cid, nn)
    path = folder / "cad.npz"
    if not path.is_file():
        raise HTTPException(409, "no CAD yet")
    with np.load(path) as data:
        vertices = data["vertices"].astype(np.float64)
        triangles = data["triangles"].astype(np.int64)
        face_id = data["face_id"].astype(np.int64)
    if show == "new":
        new = _new_faces(folder, extraction, vertices, triangles, face_id)
        keep = np.isin(face_id, new)
        triangles, face_id = triangles[keep], face_id[keep]
    used, inverse = np.unique(triangles, return_inverse=True)
    vertices = vertices[used]
    triangles = inverse.reshape(-1, 3)
    return _binary(
        mesh_format.encode(vertices, triangles, face_id, corner_normals(vertices, triangles), None)
    )


def _new_faces(folder: Path, extraction, vertices, triangles, face_id) -> np.ndarray:  # type: ignore[no-untyped-def]
    """The faces of a design's CAD that are not the part's: those lying off the part's surface."""
    cache = folder / "new_faces.npy"
    # Kept until the design's CAD is made again.
    if cache.is_file() and cache.stat().st_mtime >= (folder / "cad.npz").stat().st_mtime:
        return np.load(cache)
    import igl

    tess = extraction.tess
    centres = vertices[triangles].mean(axis=1)
    squared, _, _ = igl.point_mesh_squared_distance(
        centres, tess.vertices.astype(np.float64), tess.triangles.astype(np.int64)
    )
    off = np.sqrt(squared) > 0.2
    share = np.bincount(face_id, weights=off, minlength=face_id.max() + 1) / np.maximum(
        np.bincount(face_id, minlength=face_id.max() + 1), 1
    )
    new = np.flatnonzero(share > 0.5)
    np.save(cache, new)
    return new


def _fe(folder: Path) -> FEMesh:
    path = folder / "mesh.npz"
    if not path.is_file():
        raise HTTPException(409, "not meshed yet")
    with np.load(path) as data:
        nodes, tets = data["nodes"], data["tetra10"]
    return FEMesh(nodes=nodes, cells={"TETRA10": tets.astype(np.int64)}, name="DESIGN")


@router.get("/api/designs/{cid}/{nn}/fe/mesh")
def get_fe_mesh(cid: str, nn: str) -> Response:
    """The design's mesh: its outside, as the deck's mesh is served."""
    from .simulate import skin_blob

    return _binary(skin_blob(_fe(_folder(cid, nn)), []))


@router.get("/api/designs/{cid}/{nn}/fe/field")
def get_fe_field(cid: str, nn: str, name: str, vectors: bool = False) -> Response:
    """One field of the design's answer at every node of its mesh's outside."""
    from .simulate import values_blob

    folder = _folder(cid, nn)
    mesh = _fe(folder)
    path = folder / "result.npz"
    if not path.is_file():
        raise HTTPException(409, "not solved yet")
    with np.load(path) as data:
        u, vm = data["u"], data["von_mises"]
    nodes = np.unique(mesh.skin.corners)
    if name == "displacement":
        values = np.linalg.norm(u[nodes], axis=1)
    elif name in ("DX", "DY", "DZ"):
        values = u[nodes, ("DX", "DY", "DZ").index(name)]
    elif name == "von Mises":
        values = vm[nodes]
    else:
        raise HTTPException(404, f"no field {name!r}")
    return _binary(values_blob(values, u[nodes] if vectors else None))


@router.get("/api/designs/{cid}/{nn}/fe/section")
def get_fe_section(
    cid: str, nn: str, nx: float, ny: float, nz: float, d: float, name: str | None = None
) -> Response:
    """Where a plane cuts the design's mesh, as triangles in the plane - with one field of its
    answer and its displacement on them, once it is solved and a field is named."""
    from .simulate import node_values, section_blob

    folder = _folder(cid, nn)
    mesh = _fe(folder)
    values = vectors = None
    path = folder / "result.npz"
    if path.is_file():
        with np.load(path) as data:
            u, vm = data["u"], data["von_mises"]
        vectors = u[:, :3]
        values = node_values(u, vm, name) if name else None
    elif name:
        raise HTTPException(409, "not solved yet")
    return _binary(section_blob(mesh, nx, ny, nz, d, values, vectors))


@router.get("/api/designs/{cid}/{nn}/step")
def get_step(cid: str, nn: str) -> FileResponse:
    """The design's CAD, as STEP."""
    folder = _folder(cid, nn)
    path = folder / "design.step"
    if not path.is_file():
        raise HTTPException(409, "no CAD yet")
    return FileResponse(path, filename=f"design-{cid}-{nn}.step", media_type="application/step")
