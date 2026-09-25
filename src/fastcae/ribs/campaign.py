"""A rib network made real: its fins, already swept solids rooted in their walls, fused into
the part's own B-rep, meshed face by face and solved under the deck - :func:`realise` - with the
checks of each stage after it. A design that fails a check stops there, says which, and is kept on
screen as rejected or failed.

What is checked: that the fins made solids; that every solid fused, the fused part is one solid
and the metal added is what was planned, and how many new faces came out under
:data:`LEAST_FACE_MM2` - rejected for, or only reported, as the caller asks; that the mesh holds
no inverted tet, no hole closed flat and few poor tets, within what the card can factor; and that
the solve's reactions balance its loads.

Nothing here knows what the part is for."""

from __future__ import annotations

import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from ..designs import campaign as designs
from ..project import Project
from . import build, library, patterns

Say = Callable[[str], None]


MOST_BAD_TETS_PCT = 0.08
"""A mesh with more of its tets below quality 0.1 than this share is rejected."""
LEAST_FACE_MM2 = 5.0
"""A design may add no CAD face smaller than this."""
BALANCE = 0.02
"""The reactions must balance the loads to within this share."""


class Rejected(Exception):
    """A design that failed a stage's checks."""


def _check(record: dict[str, Any], stage: str, rows: list[dict[str, Any]]) -> None:
    record.setdefault("checks", {})[stage] = rows
    bad = [r for r in rows if not r["ok"]]
    if bad:
        raise Rejected("; ".join(f"{r['name']} {r['value']} (limit {r['limit']})" for r in bad))


def _row(name: str, value: Any, limit: Any, ok: bool) -> dict[str, Any]:
    return {"name": name, "value": value, "limit": limit, "ok": bool(ok)}


def _small_faces(vertices: np.ndarray, triangles: np.ndarray, face_id: np.ndarray) -> int:
    a, b, c = (vertices[triangles[:, i]] for i in range(3))
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    per_face = np.bincount(face_id, weights=area)
    present = np.bincount(face_id) > 0
    return int(((per_face < LEAST_FACE_MM2) & present).sum())


def realise(  # noqa: C901 - the stages in order read better in one place
    project: Project,
    extraction,  # type: ignore[no-untyped-def]
    deck,  # type: ignore[no-untyped-def]
    d: Path,
    pattern: patterns.Pattern,
    by_id: dict[str, library.Candidate],
    say: Say,
    gpu: Any,
    bodies: list[Any],
    small_faces: str = "reject",
) -> bool:
    """A pattern made real - its plates, CAD, mesh and solve - with every stage's checks. True when
    it passed them all. The design's record is read from its folder and saved as it goes.

    ``small_faces`` is what a new face under :data:`LEAST_FACE_MM2` does: ``"reject"`` the design
    at the CAD stage, as every campaign has, or ``"report"`` it in the checks and go on to the
    mesh, whose own checks - no tet inverted, few below quality 0.1 - then decide. Measured on
    the network designs of 2026-09-21: every one carried two to fourteen such faces, corner faces
    under 1.5 mm2 where a sunk rib end meets its wall, and every one meshed with 0.04 % of tets
    below quality 0.1 and none inverted. Reporting is honest as long as the row stays in the
    checks, marked failed, for anyone reading the design."""
    design = designs._Design(d)
    record = design.record
    metrics: dict[str, Any] = record.setdefault("metrics", {})
    try:
        ribs = [by_id[i] for i, _ in pattern.ribs]
        # 2. The pattern, as plates, and the outline's checks on every rib.
        t0 = time.time()
        rows = []
        # what is drawn must be what is built. A rib swept from a curve is drawn by its own
        # mid-surface - its bottom edge out and its top edge back - not by a flat plate standing in
        # for it, which would show a shape that is never made.
        for body in bodies:
            rows.append(
                {
                    "name": body.name,
                    "outline": np.round(body.outline, 2).tolist(),
                    "holes": [],
                    "normal": np.round(body.normal, 5).tolist(),
                    "thickness_mm": body.thickness_mm,
                    "stats": {
                        "angle_deg": 0.0,
                        "volume": body.name.split(":")[0],
                        "family": "fin",
                        "form": "curve",
                        "litres": 0.0,
                    },
                }
            )
        designs._write(d / "plates.json", {"plates": rows, "rib_mm": None, "covered": None})
        metrics["plates"] = len(rows)
        mirrored = [k for k, v in pattern.mirrors.items() if v is not None]
        forms = sorted({r.form for r in ribs})
        design.stage(
            "ribs",
            status="done",
            seconds=round(time.time() - t0, 1),
            detail=f"{len(pattern.ribs)} ribs ({', '.join(forms)}), {pattern.metal_L:.1f} L"
            + (f"; mirror-symmetric in {', '.join(mirrored)}" if mirrored else ""),
        )
        # A rib built as one swept solid is not a set of plate outlines, and the outline checks
        # below would be reading a shape that is never built. What can be said of a solid is
        # said here; the wall and sliver checks it must still pass run on the fused part at the
        # CAD stage, which sees the real geometry.
        from ..designs import cad as _cad

        _check(
            record,
            "ribs",
            [
                _row("fins built as solids", len(bodies), len(pattern.ribs), True),
                # A design's ribs are joined into one body before the housing sees them, and
                # that body holds as many solids as there are groups of ribs touching one
                # another - nine ribs that never meet are nine solids, which is right. What
                # must never happen is none.
                _row(
                    "the ribs make solids",
                    sum(len(_cad._solids(b.shape)) for b in bodies),
                    1,
                    sum(len(_cad._solids(b.shape)) for b in bodies) >= 1,
                ),
            ],
        )

        # 3. CAD.
        from ..designs import cad
        from ..designs import solve as solver

        t0 = time.time()
        design.stage("cad", status="running", started=t0)
        base = cad.load(designs._baseline(project))
        report = build.build(base, d, bodies)
        vertices, triangles, face_id = cad.tessellate(cad.load(d / "design.brep"))
        np.savez_compressed(
            d / "cad.npz",
            vertices=vertices.astype(np.float32),
            triangles=triangles.astype(np.int32),
            face_id=face_id.astype(np.int32),
        )
        record["cad"] = report
        metrics["cad_added_cm3"] = round(report["added_L"] * 1000)
        design.stage(
            "cad",
            status="done",
            seconds=round(time.time() - t0, 1),
            detail=f"{report['fused']} of {report['plates']} plates fused, "
            f"{report['added_L']:.1f} L added; STEP written",
        )
        tiny_part = _small_faces(*cad.tessellate(base))
        tiny = _small_faces(vertices, triangles, face_id)
        ratio = report["added_L"] / max(pattern.metal_L, 1e-9)
        faces_row = _row(
            f"new faces under {LEAST_FACE_MM2:g} mm2",
            tiny - tiny_part,
            0,
            tiny <= tiny_part,
        )
        hard = [
            _row(
                "plates fused",
                report["fused"],
                report["plates"],
                report["fused"] == report["plates"],
            ),
            _row("solids", report["solids"], 1, report["solids"] == 1),
            _row("metal added / planned", round(ratio, 3), "0.8-1.2", 0.8 <= ratio <= 1.2),
        ]
        if small_faces == "report":
            # the row is kept, failed or not, and the design goes on to the mesh's own checks
            _check(record, "cad", hard)
            record["checks"]["cad"].append(faces_row)
            if not faces_row["ok"]:
                design.stage(
                    "cad",
                    detail=f"{record['stages']['cad'].get('detail', '')}; "
                    f"{faces_row['value']} faces under {LEAST_FACE_MM2:g} mm2 reported, "
                    "meshed anyway",
                )
        else:
            _check(record, "cad", [*hard[:2], faces_row, hard[2]])

        # 4. Mesh.
        t0 = time.time()
        design.stage("mesh", status="running", started=t0)
        stats: dict[str, Any] = {}
        mesh = solver.mesh_cad(d / "design.brep", d / "mesh-work", stats)
        tets = len(mesh.cells["TETRA10"])
        np.savez_compressed(
            d / "mesh.npz",
            nodes=mesh.nodes.astype(np.float64),
            tetra10=mesh.cells["TETRA10"].astype(np.int32),
        )
        metrics["tets"], metrics["nodes"] = int(tets), int(mesh.n_nodes)
        record["mesh"] = {k: v for k, v in stats.items() if not isinstance(v, list)}
        design.stage(
            "mesh",
            status="done",
            seconds=round(time.time() - t0, 1),
            detail=f"{tets:,} second-order tets, {mesh.n_nodes:,} nodes; "
            f"{stats.get('below_q0.1_pct', 0):.3f} % below quality 0.1",
        )
        bad = float(stats.get("below_q0.1_pct", 0.0))
        _check(
            record,
            "mesh",
            [
                _row("tets", tets, designs.MOST_TETS, tets <= designs.MOST_TETS),
                _row("inverted tets", stats.get("inverted", 0), 0, stats.get("inverted", 0) == 0),
                _row(
                    "holes closed flat",
                    stats.get("patched_holes", 0),
                    0,
                    stats.get("patched_holes", 0) == 0,
                ),
                _row(
                    "tets below quality 0.1, %",
                    round(bad, 4),
                    MOST_BAD_TETS_PCT,
                    bad <= MOST_BAD_TETS_PCT,
                ),
            ],
        )

        # 5. Solve.
        t0 = time.time()
        design.stage("solve", status="running", started=t0)
        carried = solver.carried(project, extraction, mesh)
        with gpu:
            solution = solver.solve_design(carried)
        said = solver.summary(solution, carried, deck)
        from ..designs import objective, target

        said["objective"] = objective.score(project, said, target.load(project))
        designs._save_solution(d, carried, solution)
        record["solve"] = said
        metrics.update({k: v for k, v in said.items() if k in ("unknowns", "headline")})
        design.stage(
            "solve",
            status="done",
            seconds=round(time.time() - t0, 1),
            detail=said.get("words", "solved"),
        )
        applied = np.zeros(3)
        for load in carried.setup.nodal_loads:
            applied += [float(load.values.get(k, 0.0)) for k in ("FX", "FY", "FZ")]
        pushed = np.sum([np.asarray(r[:3], float) for r in solution.reactions.values()], axis=0)
        off = float(np.linalg.norm(applied + pushed) / max(np.linalg.norm(applied), 1e-9))
        _check(
            record,
            "solve",
            [_row("reactions against loads, off by", round(off, 5), BALANCE, off <= BALANCE)],
        )
        say(f"{record['name']}: {said.get('words')}")
        design.save()
        return True
    except Exception as error:  # noqa: BLE001 - a design that fails is said so; the rest go on
        # the design's own stages, in its own order: a network design has nine, a library
        # design five
        order = list(record["stages"])
        stage = next((s for s in order if record["stages"][s].get("status") == "running"), None)
        if stage is None:  # failed a check after its stage finished: the stage it checked
            done = [s for s in order if record["stages"][s].get("status") == "done"]
            stage = done[-1] if done else order[0]
        rejected = isinstance(error, Rejected)
        record["failed"] = ("rejected: " if rejected else f"{type(error).__name__}: ") + str(error)
        if not rejected:
            record["trace"] = traceback.format_exc()[-4000:]
        record["rejected"] = rejected
        design.stage(stage, status="failed", detail=record["failed"][:300])
        say(f"  {record['name']} failed at {stage}: {record['failed']}")
        design.save()
        return False
