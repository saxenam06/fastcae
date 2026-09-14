"""The runner's jobs for the baseline: its deck solved again here, and the route every variant will
take, walked on the baseline itself - field, mesh, the deck's setup carried over, solve - so the two
answers can be set side by side before a single design is trusted to it.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from .. import cache
from ..project import Project, open_project
from . import baseline, carry, fem, signals, solve, tetmesh

# The variant route's settings: the design grid a campaign previews on, and the mesher's. Cells and
# facets are held to the deck mesh's own element sizes; the bounds here only cap them.
ROUTE = {
    "spacing_mm": 3.0,
    "cell": 40.0,
    "facet": 30.0,
    "distance": 2.0,
    "edge": 8.0,
    "threads": 4,
    "seed": 0,
}


def _project(spec: dict) -> Project:
    return open_project(spec["project"])


def _extraction(project: Project):  # type: ignore[no-untyped-def]
    from ..extract import run as run_extract

    result = run_extract(project)
    if result.tess is None:
        raise RuntimeError("the CAD was not read")
    return result


def _deck(project: Project) -> baseline.Deck:
    deck = baseline.read_deck(project)
    if deck is None:
        raise RuntimeError("the project has no solver deck")
    return deck


def solve_deck(job, spec: dict) -> dict:  # type: ignore[no-untyped-def]
    """The deck's own mesh and setup, solved by cuDSS on the GPU."""
    from ..runner import GPU

    project = _project(spec)
    deck = _deck(project)
    job.update(stage="solve", progress=0.1, message="waiting for the GPU")
    with GPU:
        job.update(message="assembling and solving on the GPU")
        solution = solve.solve(deck.mesh, deck.setup, gpu=True, log=lambda m: job.event(m))
    answer = signals.from_solution(solution, "cuDSS")
    meta: dict = {
        "solver": "cuDSS",
        "mesh": "the deck's own",
        "unknowns": solution.unknowns,
        "times": solution.times,
        "residual": solution.info.get("residual"),
        "made": time.time(),
    }
    reference = deck.answer()
    if reference is not None:
        meta["agreement"] = signals.field_agreement(deck.mesh, reference, answer)
    baseline.store_answer(project, "cudss", deck.digest, answer, meta)
    return meta


# --- the variant route on the baseline ---------------------------------------------------------


def route_key(project: Project, deck: baseline.Deck, cad_digest: str) -> str:
    return cache.key_for(
        deck.digest,
        cad_digest,
        json.dumps(ROUTE, sort_keys=True),
        code=(
            "simulate/tetmesh.py",
            "simulate/carry.py",
            "simulate/fem.py",
            "simulate/wsl_mesher.py",
        ),
    )


def route_paths(project: Project, key: str) -> dict[str, Path]:
    folder = project.root / baseline.SOLVE_DIR
    return {
        "mesh": folder / f"route-mesh-{key}.npz",
        "carried": folder / f"route-carried-{key}.npz",
        "meta": folder / f"route-{key}.json",
    }


def route_meta(project: Project, key: str) -> dict:
    path = route_paths(project, key)["meta"]
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _save_meta(project: Project, key: str, step: str, value: dict) -> dict:
    meta = route_meta(project, key)
    meta[step] = value
    path = route_paths(project, key)["meta"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=1, default=float), encoding="utf-8")
    return meta


def _field(project: Project, result):  # type: ignore[no-untyped-def]
    from ..generate.field import field_for

    return field_for(project.root, result.tess, result.cad_digest, spacing_mm=ROUTE["spacing_mm"])


def route_field(job, spec: dict) -> dict:  # type: ignore[no-untyped-def]
    """The baseline as a distance field, on the grid its designs are built on."""
    project = _project(spec)
    result = _extraction(project)
    deck = _deck(project)
    key = route_key(project, deck, result.cad_digest)
    job.update(stage="field", progress=0.1, message="building the baseline's distance field")
    t0 = time.time()
    field, hit = _field(project, result)
    value = {
        "spacing_mm": field.grid.spacing_mm,
        "shape": list(field.grid.shape),
        "points": int(np.prod(field.grid.shape)),
        "band_points": int(len(field.band_index)),
        "seconds": time.time() - t0,
        "kept": hit,
    }
    _save_meta(project, key, "field", value)
    return value


def route_mesh(job, spec: dict) -> dict:  # type: ignore[no-untyped-def]
    """The field meshed by CGAL in WSL: held to the deck mesh's element sizes point by point, the
    edges of every face a distributing coupling acts on followed as lines."""
    project = _project(spec)
    result = _extraction(project)
    deck = _deck(project)
    key = route_key(project, deck, result.cad_digest)
    job.update(stage="mesh", progress=0.1, message="building or reading the field")
    field, _ = _field(project, result)
    tets = deck.mesh.tet10 if deck.mesh.tet10 is not None else deck.mesh.cells["TETRA4"]
    sizes = tetmesh.sizes_from_mesh(
        deck.mesh.nodes,
        tets[:, :4],
        np.asarray(field.grid.origin),
        tuple(field.grid.shape),
        field.grid.spacing_mm,
    )
    anchoring = carry.anchor(
        deck.mesh, deck.setup, result.tess.vertices, result.tess.triangles, result.tess.face_id
    )
    faces = sorted(
        {
            f
            for d in deck.setup.distributing
            if d.group in anchoring.groups
            for f in anchoring.groups[d.group].faces
        }
    )
    lines = tetmesh.face_edges(
        result.tess.vertices, result.tess.triangles, result.tess.face_id, set(faces)
    )
    job.update(progress=0.3, message=f"meshing the field in WSL, {len(lines)} edge lines")
    work = tetmesh.workspace(project.root / baseline.SOLVE_DIR / "work")
    t0 = time.time()
    try:
        nodes, lin, info = tetmesh.mesh_field(
            field,
            work,
            sizes=sizes,
            lines=lines,
            **{k: ROUTE[k] for k in ("cell", "facet", "distance", "edge", "threads", "seed")},
        )
    finally:
        tetmesh.clean(work)
    mesh = tetmesh.finish(nodes, lin)
    fem.save(mesh, route_paths(project, key)["mesh"])
    quality = fem.quality(mesh.nodes, mesh.cells["TETRA10"])
    value = {
        "tets": int(len(mesh.cells["TETRA10"])),
        "nodes": int(mesh.n_nodes),
        "unknowns": int(3 * mesh.n_nodes),
        "lines": len(lines),
        "mesh_s": info.get("seconds"),
        "seconds": time.time() - t0,
        "quality_min": float(quality.min()),
        "quality_below_0.1": int((quality < 0.1).sum()),
        "deck_unknowns": int(3 * len(np.unique(tets))),
    }
    _save_meta(project, key, "mesh", value)
    return value


def route_setup(job, spec: dict) -> dict:  # type: ignore[no-untyped-def]
    """The deck's setup carried to the field's mesh: every group by the CAD faces it lies on."""
    project = _project(spec)
    result = _extraction(project)
    deck = _deck(project)
    key = route_key(project, deck, result.cad_digest)
    paths = route_paths(project, key)
    if not paths["mesh"].exists():
        raise RuntimeError("mesh the field first")
    mesh = fem.load(paths["mesh"])
    job.update(stage="setup", progress=0.3, message="labelling the mesh's boundary by CAD face")
    anchoring = carry.anchor(
        deck.mesh, deck.setup, result.tess.vertices, result.tess.triangles, result.tess.face_id
    )
    carried = carry.carry(
        deck.setup,
        anchoring,
        mesh,
        result.tess.vertices,
        result.tess.triangles,
        result.tess.face_id,
    )
    fem.save(carried.mesh, paths["carried"])
    value = {"groups": carried.groups, "references": len(anchoring.references)}
    _save_meta(project, key, "setup", value)
    return value


def route_solve(job, spec: dict) -> dict:  # type: ignore[no-untyped-def]
    """The carried mesh and setup solved by cuDSS."""
    from ..runner import GPU

    project = _project(spec)
    result = _extraction(project)
    deck = _deck(project)
    key = route_key(project, deck, result.cad_digest)
    paths = route_paths(project, key)
    if not paths["carried"].exists():
        raise RuntimeError("carry the setup first")
    mesh = fem.load(paths["carried"])
    setup = _carried_setup(deck, mesh)
    job.update(stage="solve", progress=0.2, message="waiting for the GPU")
    with GPU:
        job.update(message="assembling and solving on the GPU")
        solution = solve.solve(mesh, setup, gpu=True, log=lambda m: job.event(m))
    answer = signals.from_solution(solution, "cuDSS · field route")
    meta = {
        "solver": "cuDSS",
        "mesh": "the field's",
        "unknowns": solution.unknowns,
        "times": solution.times,
        "residual": solution.info.get("residual"),
        "made": time.time(),
    }
    baseline.store_answer(project, "route", key, answer, meta)
    _save_meta(project, key, "solve", meta)
    return meta


def _carried_setup(deck: baseline.Deck, mesh: fem.FEMesh):  # type: ignore[no-untyped-def]
    import copy

    setup = copy.deepcopy(deck.setup)
    setup.resolve({g for g, m in mesh.node_groups.items() if len(m) == 1})
    return setup


def route_all(job, spec: dict) -> dict:  # type: ignore[no-untyped-def]
    out = {}
    for name, step in (
        ("field", route_field),
        ("mesh", route_mesh),
        ("setup", route_setup),
        ("solve", route_solve),
    ):
        if job.cancelled():
            break
        job.event(f"route: {name}")
        out[name] = step(job, spec)
    return out
