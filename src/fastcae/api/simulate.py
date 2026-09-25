"""The deck over HTTP: its mesh, setup and results, solved again by cuDSS - and the runner's jobs.

Routes unpack, call the engine, pack. Meshes travel as binary: the outside of the mesh - its
boundary triangles and the nodes on them - with each triangle's group, and fields as one value per
node of that outside, so a result redraws without the mesh being sent again.
"""

from __future__ import annotations

import json
import struct

import numpy as np
from fastapi import APIRouter, HTTPException, Response

from .. import runner
from ..simulate import baseline, section, signals
from ..simulate.fem import FEMesh
from ..simulate.setup import FORCES, MOMENTS

router = APIRouter()

SKIN_MAGIC = b"FCSKIN01"
VALUES_MAGIC = b"FCVALS01"
NO_GROUP = 0xFFFF


def _open():  # type: ignore[no-untyped-def]
    from .app import _resume, _state

    if _state.project is None or _state.extraction is None:
        _resume()  # the server restarts on a source change; pick the session back up
    if _state.project is None or _state.extraction is None:
        raise HTTPException(409, "no project is open")
    return _state.project, _state.extraction


def _deck():  # type: ignore[no-untyped-def]
    project, result = _open()
    deck = baseline.read_deck(project)
    if deck is None:
        raise HTTPException(404, "this project has no solver deck")
    return project, result, deck


def _patch_groups(mesh: FEMesh, names: list[str]) -> np.ndarray:
    """Each boundary triangle's group: the first of ``names`` holding all three of its corners."""
    skin = mesh.skin
    out = np.full(len(skin.corners), NO_GROUP, np.uint16)
    for index, name in enumerate(names):
        try:
            members = mesh.group_nodes(name)
        except KeyError:
            continue
        inside = np.zeros(mesh.n_nodes, bool)
        inside[members] = True
        hit = inside[skin.corners].all(axis=1) & (out == NO_GROUP)
        out[hit] = index
    return out


def _patch_names(setup) -> list[str]:  # type: ignore[no-untyped-def]
    """The surface groups the setup acts on, those loads go in through first."""
    names: list[str] = []
    for d in setup.distributing:
        names.append(d.group)
    for r in setup.rigid:
        names += [g for g in r.groups if g != r.reference]
    for h in setup.held:
        names += h.groups
    for n in setup.nodal_loads:
        names.append(n.group)
    for s in setup.surface_loads:
        names.append(s.group)
    return list(dict.fromkeys(names))


def skin_blob(mesh: FEMesh, names: list[str]) -> bytes:
    skin = mesh.skin
    nodes, inverse = np.unique(skin.corners, return_inverse=True)
    triangles = inverse.reshape(-1, 3).astype(np.uint32)
    groups = _patch_groups(mesh, names)
    header = json.dumps(
        {"groups": names, "vertices": int(len(nodes)), "triangles": int(len(triangles))}
    ).encode()
    pad = (-len(header)) % 4
    parts = [
        SKIN_MAGIC,
        struct.pack("<III", len(header) + pad, len(nodes), len(triangles)),
        header + b" " * pad,
        mesh.nodes[nodes].astype(np.float32).tobytes(),
        triangles.tobytes(),
        groups.tobytes(),
        b"\0\0" * (len(groups) % 2),
        nodes.astype(np.uint32).tobytes(),
    ]
    return b"".join(parts)


def values_blob(values: np.ndarray, vectors: np.ndarray | None = None) -> bytes:
    values = np.asarray(values, np.float32)
    parts = [
        VALUES_MAGIC,
        struct.pack("<II", len(values), 0 if vectors is None else 3),
        values.tobytes(),
    ]
    if vectors is not None:
        parts.append(np.asarray(vectors, np.float32).tobytes())
    return b"".join(parts)


def _skin_nodes(mesh: FEMesh) -> np.ndarray:
    return np.unique(mesh.skin.corners)


def node_values(u: np.ndarray, von_mises: np.ndarray | None, name: str) -> np.ndarray:
    """One field of an answer at every node of its mesh."""
    if name == "displacement":
        return np.linalg.norm(u[:, :3], axis=1)
    if name in ("DX", "DY", "DZ"):
        return u[:, ("DX", "DY", "DZ").index(name)]
    if name == "von Mises":
        if von_mises is None:
            raise HTTPException(404, "this answer has no von Mises stress")
        return von_mises
    raise HTTPException(404, f"no field {name!r}")


def _field_values(mesh: FEMesh, answer: signals.Answer, name: str) -> np.ndarray:
    return node_values(answer.u, answer.von_mises, name)[_skin_nodes(mesh)]


def section_blob(
    mesh: FEMesh,
    nx: float,
    ny: float,
    nz: float,
    d: float,
    values: np.ndarray | None,
    vectors: np.ndarray | None,
) -> bytes:
    """Where the plane ``(nx, ny, nz) . x = d`` cuts the mesh: its triangles, with the field and
    the displacement on them when given."""
    if not np.isfinite([nx, ny, nz, d]).all() or np.hypot(np.hypot(nx, ny), nz) < 1e-12:
        raise HTTPException(422, "the plane needs a normal and an offset")
    tets = mesh.tet10 if mesh.tet10 is not None else mesh.cells.get("TETRA4")
    if tets is None:
        raise HTTPException(409, "the mesh has no tets to cut")
    cut = section.cut(mesh.nodes, tets, (nx, ny, nz), d, values, vectors)
    return section.encode(cut)


# --- the deck ---------------------------------------------------------------------------------


@router.get("/api/deck")
def get_deck() -> dict:
    """What the deck says, what came back from its run, what fastcae has made of it since."""
    project, result = _open()
    files = baseline.deck_files(project)
    if not files.complete:
        return {"present": False, **files.to_json()}
    deck = baseline.read_deck(project)
    assert deck is not None
    out = {"present": True, **baseline.summary(deck)}
    out["anchoring"] = result.anchoring
    out["patches"] = _patch_names(deck.setup)
    out["answers"] = _answers(project, deck)
    return out


def _answers(project, deck) -> list[dict]:  # type: ignore[no-untyped-def]
    """The deck's own answer, as it came back from its run, and fastcae's reproduction of it."""
    rows = [
        {
            "id": "aster",
            "label": "Code_Aster",
            "provenance": "imported",
            "available": deck.files.results is not None,
            "detail": deck.files.results.name if deck.files.results else "no results file",
        }
    ]
    stored = baseline.load_answer(project, "cudss", deck.digest)
    rows.append(
        {
            "id": "cudss",
            "label": "cuDSS · same mesh",
            "provenance": "generated",
            "available": stored is not None,
            "meta": stored[1] if stored else None,
        }
    )
    return rows


@router.get("/api/deck/mesh")
def get_deck_mesh() -> Response:
    """The deck mesh's outside, each triangle with the group it lies in."""
    _, _, deck = _deck()
    return Response(
        skin_blob(deck.mesh, _patch_names(deck.setup)), media_type="application/octet-stream"
    )


@router.get("/api/deck/glyphs")
def get_deck_glyphs() -> dict:
    _, _, deck = _deck()
    return glyphs(deck.mesh, deck.setup)


def glyphs(mesh: FEMesh, setup) -> dict:  # type: ignore[no-untyped-def]
    """What to draw for each support, coupling and load: points, spokes, arrows - with its name."""
    rng = np.random.default_rng(0)

    def sample(members: np.ndarray, n: int) -> list[list[float]]:
        chosen = members if len(members) <= n else rng.choice(members, n, replace=False)
        return mesh.nodes[chosen].round(3).tolist()

    def point(group: str) -> list[float]:
        return mesh.nodes[mesh.group_nodes(group)].mean(axis=0).round(3).tolist()

    active = setup.active()
    out: dict = {"held": [], "rigid": [], "distributing": [], "loads": [], "surface": []}
    for h in setup.held:
        for g in h.groups:
            members = mesh.group_nodes(g)
            out["held"].append(
                {
                    "group": g,
                    "points": sample(members, 64),
                    "count": int(len(members)),
                    "dofs": h.dofs,
                    "load_set": h.load_set,
                    "active": h.load_set in active,
                }
            )
    for r in setup.rigid:
        slaves = np.unique(
            np.concatenate([mesh.group_nodes(g) for g in r.groups if g != r.reference])
        )
        out["rigid"].append(
            {
                "groups": r.groups,
                "reference": r.reference,
                "point": point(r.reference) if r.reference else None,
                "spokes": sample(slaves, 16),
                "count": int(len(slaves)),
                "load_set": r.load_set,
            }
        )
    for d in setup.distributing:
        members = mesh.group_nodes(d.group)
        out["distributing"].append(
            {
                "group": d.group,
                "reference": d.reference,
                "point": point(d.reference),
                "spokes": sample(members, 48),
                "count": int(len(members)),
                "load_set": d.load_set,
            }
        )
    for n in setup.nodal_loads:
        out["loads"].append(
            {
                "group": n.group,
                "point": point(n.group),
                "force": [n.values.get(c, 0.0) for c in FORCES],
                "moment": [n.values.get(c, 0.0) for c in MOMENTS],
                "nodes": int(len(mesh.group_nodes(n.group))),
                "load_set": n.load_set,
            }
        )
    for s in setup.surface_loads:
        out["surface"].append(
            {"group": s.group, "kind": s.kind, "values": s.values, "load_set": s.load_set}
        )
    lo, hi = mesh.nodes.min(axis=0), mesh.nodes.max(axis=0)
    forces = [np.linalg.norm(x["force"]) for x in out["loads"]] or [0.0]
    moments = [np.linalg.norm(x["moment"]) for x in out["loads"]] or [0.0]
    out["scale"] = {
        "span": float(np.linalg.norm(hi - lo)),
        "force_max": float(max(forces)),
        "moment_max": float(max(moments)),
    }
    return out


# --- answers ------------------------------------------------------------------------------------


def _answer(run: str):  # type: ignore[no-untyped-def]
    project, _, deck = _deck()
    if run == "aster":
        answer = deck.answer()
        if answer is None:
            raise HTTPException(404, "the deck came with no results")
        return deck.mesh, answer, deck
    if run == "cudss":
        stored = baseline.load_answer(project, "cudss", deck.digest)
        if stored is None:
            raise HTTPException(404, "not solved by cuDSS yet")
        return deck.mesh, stored[0], deck
    raise HTTPException(404, f"no answer {run!r}")


@router.get("/api/deck/field")
def get_field(run: str, name: str, vectors: bool = False) -> Response:
    """One field of one answer at every node of the mesh's outside, in the skin's vertex order."""
    mesh, answer, _ = _answer(run)
    nodes = _skin_nodes(mesh)
    values = _field_values(mesh, answer, name)
    return Response(
        values_blob(values, answer.u[nodes] if vectors else None),
        media_type="application/octet-stream",
    )


@router.get("/api/deck/section")
def get_section(
    nx: float, ny: float, nz: float, d: float, run: str | None = None, name: str | None = None
) -> Response:
    """Where a plane cuts the deck's mesh, as triangles in the plane - with one field of an answer
    and its displacement on them, when an answer is named."""
    if run:
        mesh, answer, _ = _answer(run)
        values = node_values(answer.u, answer.von_mises, name) if name else None
        vectors = answer.u[:, :3]
    else:
        _, _, deck = _deck()
        mesh, values, vectors = deck.mesh, None, None
    return Response(
        section_blob(mesh, nx, ny, nz, d, values, vectors), media_type="application/octet-stream"
    )


@router.get("/api/deck/signals")
def get_signals() -> dict:
    """Every signal of every answer there is, side by side."""
    _, _, deck = _deck()
    runs: dict[str, list[signals.Signal]] = {}
    labels = {}
    for run in ("aster", "cudss"):
        try:
            mesh, answer, _ = _answer(run)
        except HTTPException:
            continue
        runs[run] = signals.signals(mesh, deck.setup, answer)
        labels[run] = answer.source
    rows: dict[tuple[str, str], dict] = {}
    for run, found in runs.items():
        for s in found:
            row = rows.setdefault(
                (s.name, s.component),
                {
                    "name": s.name,
                    "component": s.component,
                    "unit": s.unit,
                    "kind": s.kind,
                    "group": s.group,
                    "values": {},
                },
            )
            row["values"][run] = s.value
    agreement = {}
    if "aster" in runs and "cudss" in runs:
        agreement["cudss"] = signals.field_agreement(
            deck.mesh, _answer("aster")[1], _answer("cudss")[1]
        )
    return {"runs": labels, "rows": list(rows.values()), "agreement": agreement}


@router.get("/api/deck/certificate")
def get_certificate(other: str = "cudss") -> dict:
    """How a reproduction compares with the engineer's own answer, quantity by quantity."""
    project, _, deck = _deck()
    ref_mesh, reference, _ = _answer("aster")
    mesh, answer, _ = _answer(other)
    rows = signals.certificate(
        (ref_mesh, deck.setup, reference), (mesh, deck.setup, answer), same_mesh=True
    )
    stored = baseline.load_answer(project, other, deck.digest)
    solver = {
        "reference": _aster_version(deck),
        "other": "cuDSS 0.8 (nvmath-python 1.0), linear static, TETRA10",
    }
    meta = stored[1] if stored else {}
    return {
        "other": other,
        "rows": rows,
        "solver": solver,
        "residual": meta.get("residual"),
        "holds": all(r["holds"] is not False for r in rows),
    }


def _aster_version(deck) -> str:  # type: ignore[no-untyped-def]
    """Which Code_Aster the engineer's run used, from its message log."""
    if deck.files.log is None:
        return "Code_Aster"
    head = deck.files.log.read_text(encoding="utf-8", errors="replace")[:20000]
    import re

    found = re.search(r"Version\s+([\d.]+)", head)
    mumps = re.search(r"MUMPS\s*:\s*([\d.]+)", head)
    return f"Code_Aster {found.group(1) if found else ''}".strip() + (
        f", MUMPS {mumps.group(1)}" if mumps else ""
    )


@router.post("/api/deck/solve")
def post_solve() -> dict:
    """Solve the deck's own mesh and setup with cuDSS, on the runner."""
    project, _, _ = _deck()
    return {"job": runner.submit("baseline.cudss", project.name).id}


# --- jobs ----------------------------------------------------------------------------------------


@router.get("/api/jobs")
def get_jobs(kind: str | None = None) -> dict:
    from .app import _state

    project = _state.project.name if _state.project else None
    return {"runner": runner.alive(), "jobs": runner.jobs(project=project, kind=kind)}


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str, since: int = 0) -> dict:
    job = runner.Job(job_id)
    if not job.folder.exists():
        raise HTTPException(404, f"no job {job_id}")
    return {"id": job_id, **job.spec(), **job.status(), "events": job.events(since)}


@router.post("/api/jobs/{job_id}/cancel")
def post_cancel(job_id: str) -> dict:
    job = runner.Job(job_id)
    if not job.folder.exists():
        raise HTTPException(404, f"no job {job_id}")
    job.cancel()
    return {"id": job_id, "cancelled": True}
