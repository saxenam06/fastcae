"""A campaign's records: its folder beside the project's, a folder for each design, every stage
stamped on the design's record as it finishes (:class:`_Design`), the solved fields kept beside it
(:func:`_save_solution`), and what the screens read of them (:func:`campaigns`, :func:`summary`).

**Where campaigns are kept**: beside the folder projects live in, never in the project's own
folder, which holds only what the engineer brought and decided."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from ..project import Project

STAGES: list[tuple[str, str]] = [
    ("optimise", "Optimise"),
    ("ribs", "Path"),
    ("cad", "CAD"),
    ("mesh", "Mesh"),
    ("solve", "Solve"),
]
"""A design's stages, in order: an id and the word a screen shows for it."""


MOST_TETS = 305_000
"""The largest design mesh the card factors: past about 1.65 M unknowns cuDSS fails on an 8 GB card
even with part of its factor in host memory - the densest block of a mesh this size must still fit
on the card."""


def root(project: Project) -> Path:
    """Where a project's campaigns are kept: beside the folder projects live in, never in the
    project's own folder, which holds only what the engineer brought and decided."""
    return project.root.resolve().parent.parent / "_archived_designs" / project.name / "campaigns"


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    partial.write_text(json.dumps(value, indent=1, default=_plain), encoding="utf-8")
    partial.replace(path)


def _plain(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return str(value)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def create(project: Project, designs: list[dict[str, Any]], name: str | None = None) -> Path:
    """A new campaign's folder, with a folder for each of its designs, every stage still to do."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    folder = root(project) / stamp
    _write(
        folder / "campaign.json",
        {
            "id": stamp,
            "name": name or f"campaign {stamp}",
            "made": time.time(),
            "designs": len(designs),
            "stages": [s for s, _ in STAGES],
        },
    )
    for i, design in enumerate(designs, start=1):
        _write(
            folder / f"{i:02d}" / "design.json",
            {
                "id": f"{stamp}/{i:02d}",
                "index": i,
                **design,
                "stages": {s: {"status": "pending"} for s, _ in STAGES},
            },
        )
    return folder


def campaigns(project: Project) -> list[dict[str, Any]]:
    """Every campaign kept for a project, newest first, with its designs in a few words each."""
    out = []
    base = root(project)
    for folder in sorted(base.iterdir(), reverse=True) if base.is_dir() else []:
        head = _read(folder / "campaign.json")
        if not head:
            continue
        designs = []
        for d in sorted(folder.iterdir()):
            record = _read(d / "design.json") if d.is_dir() else None
            if record:
                designs.append(summary(record))
        out.append({**head, "designs": designs})
    return out


def _objective_of(record: dict[str, Any]) -> dict[str, Any] | None:
    """What a design was judged on, as a list shows it: the objective and the misalignment that is
    most of it. None until it is solved.

    A list that shows strain energy shows what the part does, not what the study asked for. The
    objective is the number the sizing moved and the number a design is kept or dropped on, so it
    is the one a list has to carry."""
    obj = (record.get("solve") or {}).get("objective") or {}
    if obj.get("j_robust") is None:
        return None
    ranked = (obj.get("ranked") or [None])[0]
    mesh = ((obj.get("meshes") or {}).get(ranked) or {}) if ranked else {}
    return {
        "j_robust": obj.get("j_robust"),
        "j_nominal": obj.get("j_nominal"),
        "lead_um": mesh.get("robust_um"),
        "ranked": ranked,
        "load_case": (record.get("load_case") or {}).get("name"),
    }


def summary(record: dict[str, Any]) -> dict[str, Any]:
    """A design as a list shows it."""
    counts = None
    if record.get("fins"):
        from ..ribs import networks

        counts = networks.counts(record)
    return (
        {"counts": counts}
        | {
            k: record.get(k)
            for k in (
                "id",
                "index",
                "name",
                "budget_L",
                "budget_share",
                "stages",
                "metrics",
                "failed",
                "why",
                "rejected",
            )
        }
        | {
            "mix": {"name": record["mix"]["name"], "words": record["mix"].get("words", "")},
            "objective": _objective_of(record),
        }
    )


def design_folder(project: Project, design_id: str) -> Path:
    """A design's folder from its id, ``<campaign>/<nn>`` - never outside the campaigns."""
    base = root(project).resolve()
    folder = (base / design_id).resolve()
    if base not in folder.parents or not (folder / "design.json").is_file():
        raise KeyError(design_id)
    return folder


class _Design:
    """One design's folder: its record, saved as each stage starts and ends."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.record = _read(folder / "design.json")

    def save(self) -> None:
        _write(self.folder / "design.json", self.record)

    def stage(self, stage: str, **changes: Any) -> None:
        self.record["stages"][stage] = {**self.record["stages"].get(stage, {}), **changes}
        self.save()


def _baseline(project: Project) -> Path:
    cad = project.roles().get("baseline")
    if cad:
        return project.root / cad
    from ..project import ArtifactKind

    first = project.first(ArtifactKind.CAD)
    if first is None:
        raise RuntimeError("the project has no CAD")
    return first.path


def _save_solution(folder: Path, carried, solution) -> None:  # type: ignore[no-untyped-def]
    from ..simulate import signals

    answer = signals.from_solution(solution, "cuDSS")
    np.savez_compressed(
        folder / "result.npz",
        u=np.asarray(answer.u, np.float32),
        von_mises=np.asarray(
            answer.von_mises if answer.von_mises is not None else np.zeros(len(answer.u)),
            np.float32,
        ),
    )
    # Every load component's own answer, kept whole: a study that asks a different question of
    # this design - another mix of the same loads, a measure nobody asked for yet - is a weighted
    # sum of these, not another solve. Uncompressed: it is dense, and the time costs more than the
    # bytes (a design's file is about 100 MB).
    if solution.component_u is not None:
        np.savez(
            folder / "components.npz",
            u=solution.component_u,
            loads=np.array(
                [f"{p['group']}:{p['component']}" for p in solution.info["components"]]  # type: ignore[index,union-attr]
            ),
            values=np.array(
                [p["value"] for p in solution.info["components"]],  # type: ignore[index,union-attr]
                np.float64,
            ),
        )
