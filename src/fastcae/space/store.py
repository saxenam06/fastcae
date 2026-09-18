"""A derived design space kept with its project, derived once and read back while nothing changed.

The key is everything the result depends on: the project's files, byte for byte, the settings the
rules ran with, and the code that ran them. Change any of them and the space is derived again;
change none and it is read back - with the pipeline's own record, so the steps it went through can
still be shown, each with what it produced.

Two files an entry: the arrays (compressed, about ten megabytes on a large housing at 4 mm) and the
summary as JSON.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from .. import cache
from ..generate.field import Grid
from .model import Interface, Params, Question, Space

KIND = "designspace"
KEEP = 4

CODE = (
    "space/model.py",
    "space/grid.py",
    "space/interfaces.py",
    "space/sweeps.py",
    "space/derive.py",
    "space/physics.py",
    "features.py",
    "geometry/atlas.py",
    "geometry/brep.py",
    "generate/field.py",
    "simulate/carry.py",
)


def key_for(extraction, params: Params, answers: dict[str, str] | None = None) -> str:  # type: ignore[no-untyped-def]
    files = [f"{a.path.name}:{a.kind}:{a.digest()}" for a in extraction.artifacts]
    return cache.key_for(
        *sorted(files),
        json.dumps(params.to_json(), sort_keys=True),
        json.dumps(answers or {}, sort_keys=True),
        code=CODE,
    )


def _paths(root: Path, key: str) -> tuple[Path, Path]:
    base = root / cache.CACHE_DIR_NAME / f"{KIND}-{key}"
    return base.with_suffix(".npz"), base.with_suffix(".json")


def load(root: Path, key: str) -> Space | None:
    """The space kept under ``key``, or None. A broken entry is a miss, never an error."""
    arrays_path, summary_path = _paths(root, key)
    if not arrays_path.is_file() or not summary_path.is_file():
        return None
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        with np.load(arrays_path) as data:
            arrays = {k: data[k] for k in data.files}
    except Exception:  # noqa: BLE001
        return None
    grid = Grid(
        origin=tuple(float(v) for v in arrays["origin"]),
        spacing_mm=float(arrays["spacing"]),
        shape=tuple(int(v) for v in arrays["shape"]),
    )
    params_json = summary["params"]
    params = Params(**{k: tuple(v) if isinstance(v, list) else v for k, v in params_json.items()})
    interfaces = [
        Interface(**{k: v for k, v in i.items() if k != "status"}) for i in summary["interfaces"]
    ]
    questions = [
        Question(
            **{
                k: tuple(v) if k in ("options", "where") and v is not None else v
                for k, v in q.items()
            }
        )
        for q in summary["questions"]
    ]
    for path in (arrays_path, summary_path):
        path.touch()
    return Space(
        grid=grid,
        params=params,
        labels=arrays["labels"],
        reasons=arrays["reasons"],
        interfaces=interfaces,
        questions=questions,
        columns={k[len("column_") :]: v for k, v in arrays.items() if k.startswith("column_")},
        sealing_faces=summary["sealing_faces"],
        symmetry=summary["symmetry"],
        stats=summary["stats"],
        steps=summary.get("steps", []),
        faces={k: {int(f): v for f, v in d.items()} for k, d in summary.get("faces", {}).items()},
        benefit=arrays.get("benefit"),
    )


def save(root: Path, key: str, space: Space) -> None:
    """Keep a space, atomically, and let the oldest entries go."""
    arrays_path, summary_path = _paths(root, key)
    arrays_path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {
        "labels": space.labels,
        "reasons": space.reasons,
        "origin": np.asarray(space.grid.origin),
        "spacing": np.asarray(space.grid.spacing_mm),
        "shape": np.asarray(space.grid.shape),
        **{f"column_{k}": v for k, v in space.columns.items()},
    }
    if space.benefit is not None:
        arrays["benefit"] = space.benefit
    partial = arrays_path.with_name(arrays_path.stem + ".partial.npz")
    np.savez_compressed(partial, **arrays)
    partial.replace(arrays_path)
    text = json.dumps(space.summary(), default=str)
    partial_json = summary_path.with_suffix(".json.partial")
    partial_json.write_text(text, encoding="utf-8")
    partial_json.replace(summary_path)
    kept = sorted(
        arrays_path.parent.glob(f"{KIND}-*.npz"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    for old in kept[KEEP:]:
        old.unlink(missing_ok=True)
        old.with_suffix(".json").unlink(missing_ok=True)


def derived(  # type: ignore[no-untyped-def]
    extraction,
    setup: Any,
    params: Params,
    root: Path,
    reuse: bool = True,
    report: Callable[[dict[str, Any]], None] | None = None,
    say=None,  # type: ignore[no-untyped-def]
    answers: dict[str, str] | None = None,
    publish: Callable[[Any, str, Any], None] | None = None,
) -> tuple[Space, bool]:
    """The project's design space: read back when nothing it depends on has changed, derived and
    kept otherwise. A space read back replays its steps to ``report``, marked as read back."""
    from .derive import derive

    key = key_for(extraction, params, answers)
    if reuse:
        found = load(root, key)
        if found is not None:
            if report:
                for step in found.steps:
                    report(
                        {**step, "status": "cached" if step["status"] == "done" else step["status"]}
                    )
            return found, True
    space = derive(
        extraction,
        setup=setup,
        params=params,
        root=root,
        say=say,
        report=report,
        answers=answers,
        publish=publish,
    )
    save(root, key, space)
    return space, False
