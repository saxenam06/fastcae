"""A design solved the way the baseline's deck is: its CAD meshed face by face by the recipe the
deck's own mesh was made with, the deck's groups carried onto that mesh by the CAD faces they lie
on, and the deck's analysis solved by cuDSS on the GPU.

- :func:`mesh_cad` - the CAD meshed face by face (:mod:`fastcae.simulate.face_mesh`) and finished
  as TET10. A face gmsh could not mesh leaves a hole MeshFix would lid flat; such a mesh is refused.
- :func:`carried` - each group the deck acts on tied to the faces of the baseline's CAD and carried
  onto the mesh: supports, couplings, loads and signals unchanged, reference points where the deck
  put them. A mesh holding less than half of a group's area in the deck has covered a face the deck
  acts on - its setup would not be the deck's - and is refused.
- :func:`solve_design` - the carried deck solved by cuDSS.
- :func:`summary` - the deck's signals read off the design's answer beside the part's own, and a
  headline in numbers and in words.

Nothing here knows the part. The deck says what is held, what is loaded and what is read off the
answer; the CAD's faces tie that to any mesh whose CAD keeps them.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from ..gpu import release
from ..simulate import baseline, carry, signals, solve, tetmesh
from ..simulate.fem import FEMesh, tet_volumes

if TYPE_CHECKING:
    from ..extract import Extraction
    from ..project import Project

# A mesh holding less than this share of a group's area in the deck has covered a face the deck
# acts on.
LEAST_SHARE = 0.5

MESH_MINUTES = 10
"""The longest a design's CAD may take to mesh; a design meshes in under a minute, and one gmsh
has not finished in ten it will not finish."""


class Unmeshed(RuntimeError):
    """gmsh left faces of the CAD without triangles: MeshFix would close the holes flat."""


class NotCarried(RuntimeError):
    """The deck's setup does not carry onto a mesh; ``carried`` holds what did, if anything."""

    def __init__(self, message: str, carried: carry.Carried | None = None) -> None:
        super().__init__(message)
        self.carried = carried


def mesh_cad(brep_path: Path, work: Path, stats: dict[str, Any] | None = None) -> FEMesh:
    """The CAD meshed face by face and finished as TET10, the volume as the cell group ``BULK``.

    ``work`` takes the mesher's scratch file. ``stats``, when given, is filled with what the mesher
    reports: faces, faces meshed unrolled, holes closed, element quality, volume, seconds."""
    brep_path, work = Path(brep_path), Path(work)
    work.mkdir(parents=True, exist_ok=True)
    nodes, tets, info = _mesh_apart(brep_path, work)
    if stats is not None:
        stats.update(info)
    if info["patched_holes"]:
        sites = "; ".join(
            f"{site['span_mm']} mm across at {site['centre']}" for site in info["patch_sites"][:3]
        )
        raise Unmeshed(
            f"{brep_path.name}: gmsh left faces unmeshed - {info['patched_holes']} holes MeshFix "
            f"would lid flat ({sites})"
        )
    return tetmesh.finish(nodes, tets)


def _mesh_apart(brep_path: Path, work: Path) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """:func:`fastcae.simulate.face_mesh.mesh` in a process of its own, stopped past
    :data:`MESH_MINUTES`: a face gmsh cannot finish would otherwise hold everything after it for
    ever."""
    for name in ("face_mesh.npz", "face_mesh.json"):
        (work / name).unlink(missing_ok=True)
    log = work / "face_mesh.log"
    with open(log, "w", encoding="utf-8") as out:
        try:
            subprocess.run(
                [sys.executable, "-m", "fastcae.simulate.face_mesh", str(brep_path), str(work)],
                stdout=out,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=MESH_MINUTES * 60,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"the mesher had not finished in {MESH_MINUTES} min") from error
        except subprocess.CalledProcessError as error:
            said = [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
            raise RuntimeError(said[-1] if said else "the mesher failed") from error
    with np.load(work / "face_mesh.npz") as found:
        nodes, tets = found["nodes"], found["tets"]
    return nodes, tets, json.loads((work / "face_mesh.json").read_text(encoding="utf-8"))


def _closed(
    vertices: np.ndarray, triangles: np.ndarray, face_id: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The CAD's triangulation without the odd pair of identical, oppositely wound triangles."""
    _, inverse, count = np.unique(
        np.sort(triangles, 1), axis=0, return_inverse=True, return_counts=True
    )
    keep = count[inverse.ravel()] == 1
    triangles, face_id = triangles[keep], face_id[keep]
    used, compact = np.unique(triangles, return_inverse=True)
    return vertices[used], compact.reshape(triangles.shape), face_id


def _deck(project: Project) -> baseline.Deck:
    deck = baseline.read_deck(project)
    if deck is None:
        raise NotCarried("the project has no solver deck: nothing says how a design is held")
    return deck


def carried(project: Project, extraction: Extraction, mesh: FEMesh) -> carry.Carried:
    """The baseline deck's setup on ``mesh``: each group it acts on tied to the CAD faces it lies on
    - on the baseline CAD's triangulation, closed - and carried onto the mesh by those faces."""
    deck = _deck(project)
    tess = extraction.tess
    if tess is None:
        raise NotCarried("the extraction holds no triangulation of the CAD to tie the deck to")
    vertices, triangles, face_id = _closed(tess.vertices, tess.triangles, tess.face_id)
    anchoring = carry.anchor(deck.mesh, deck.setup, vertices, triangles, face_id)
    moved = carry.carry(deck.setup, anchoring, mesh, vertices, triangles, face_id)
    lost = [f"{name} (not on the CAD's surface)" for name in anchoring.not_anchored]
    lost += [
        f"{name} ({group['area'] / max(group['deck_area'], 1e-9):.0%} of its area)"
        for name, group in moved.groups.items()
        if group["area"] < LEAST_SHARE * group["deck_area"]
    ]
    if lost:
        raise NotCarried("groups the deck acts on are lost: " + ", ".join(lost), moved)
    return moved


def solve_design(
    carried: carry.Carried, log: Callable[[str], None] | None = None
) -> solve.Solution:
    """The carried deck solved by cuDSS on the GPU; the card is handed back afterwards, whatever
    happened. The card takes one user at a time: the caller holds it (the runner's GPU lock)."""
    release()
    try:
        return solve.solve(
            carried.mesh, carried.setup, gpu=True, log=log or (lambda _: None), components=True
        )
    finally:
        release()


def _mass_kg(mesh: FEMesh, density: float) -> float:
    """The mesh's metal at the deck's density (tonnes a cubic millimetre)."""
    tets = mesh.tet10 if mesh.tet10 is not None else mesh.cells["TETRA4"]
    return float(tet_volumes(mesh.nodes, tets).sum() * density * 1000.0)


def summary(
    solution: solve.Solution, carried: carry.Carried, deck: baseline.Deck
) -> dict[str, Any]:
    """The design's answer read as the deck reads it, beside the part's own - the deck's results.

    - ``signals``: every signal the deck asks for and every derived one, a row each - the part's
      value, the design's, and the change as a share of the part's; a signal only one side has
      is listed with the other side None.
    - ``headline``: the few numbers a list shows - the work of the loads (the strain energy) and
      the largest displacement, the design's and as shares of the part's, and the metal added.
    - ``words``: the headline in a line.
    - ``unknowns``, ``mesh``, ``groups`` (how much of each group's area the mesh carried),
      ``solver``, ``mass_kg`` (at the deck's density, when it gives one)."""
    reference = deck.answer()
    theirs = {
        (s.name, s.component): s
        for s in (signals.signals(deck.mesh, deck.setup, reference) if reference else [])
    }
    answer = signals.from_solution(solution, "cuDSS")
    mine = {(s.name, s.component): s for s in signals.signals(carried.mesh, carried.setup, answer)}
    rows = []
    for key in dict.fromkeys([*theirs, *mine]):
        before, after = theirs.get(key), mine.get(key)
        either = after or before
        assert either is not None
        rows.append(
            {
                "name": either.name,
                "component": either.component,
                "unit": either.unit,
                "kind": either.kind,
                "group": either.group,
                "baseline": before.value if before else None,
                "design": after.value if after else None,
                "change": (after.value - before.value) / abs(before.value)
                if before and after and before.value != 0
                else None,
            }
        )
    materials = deck.setup.materials
    density = materials[0].density if len(materials) == 1 else None
    mass = (
        {"baseline": _mass_kg(deck.mesh, density), "design": _mass_kg(carried.mesh, density)}
        if density
        else None
    )
    work = signals.work(carried.mesh, carried.setup, answer)
    work_part = signals.work(deck.mesh, deck.setup, reference) if reference else None
    work_share = work / work_part if work_part else None
    largest = mine[("displacement", "largest")].value
    part = theirs.get(("displacement", "largest"))
    largest_share = largest / part.value if part and part.value else None
    added = mass["design"] - mass["baseline"] if mass else None
    words = f"largest displacement {largest:.3g} mm"
    if largest_share is not None:
        words += f", {largest_share:.0%} of the part's"
    if work_share is not None:
        words += f"; strain energy {work_share:.0%} of the part's"
    if added is not None:
        words += f"; {round(added, 1) or 0.0:+.1f} kg"  # never "-0.0"
    return {
        "unknowns": solution.unknowns,
        "headline": {
            "work_Nmm": work,
            "work_share": work_share,
            "largest_displacement_mm": largest,
            "largest_displacement_share": largest_share,
            "added_kg": added,
        },
        "words": words,
        # Each load part's bearing motions: what a measure over a band of loads is read from.
        # Both how a seat moved and how it turned - a gear mesh is read from the first, a bearing's
        # misalignment from the second, and a study that keeps only one cannot ask the other later.
        "components": [
            {
                "group": part["group"],
                "component": part["component"],
                "value": part["value"],
                "refs": {k: v["u"] for k, v in part["refs"].items() if "BOLT" not in k},
                "turns": {k: v["rotation"] for k, v in part["refs"].items() if "BOLT" not in k},
            }
            for part in solution.info.get("components", [])
        ],
        "mesh": {"tets": carried.mesh.count("TETRA10"), "nodes": carried.mesh.n_nodes},
        "groups": {
            name: {**group, "share": group["area"] / max(group["deck_area"], 1e-9)}
            for name, group in carried.groups.items()
        },
        "solver": {
            "name": "cuDSS",
            "residual": solution.info.get("residual"),
            "times": solution.times,
        },
        "baseline": {
            "source": reference.source if reference else None,
            "tets": deck.mesh.count("TETRA10"),
            "nodes": deck.mesh.n_nodes,
            "work_Nmm": work_part,
        },
        "mass_kg": mass,
        "signals": rows,
    }
