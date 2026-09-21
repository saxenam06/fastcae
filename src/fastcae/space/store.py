"""The design space kept with its project: in the project's folder, beside the engineer's own files.

A design space is taken as defined - an input, like the CAD. It is kept as ``design_space.npz`` -
the grid, every cell's label, and where metal helps - beside ``design_space.json``, what it holds
and how it was defined. It is read back for as long as the CAD it was defined on is the project's
CAD.
Where there is none, the rules define one (:func:`.derive.derive`) and keep it there, standing in
for the engineer's; defining it again replaces only one the rules defined.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from ..geometry.field import Grid
from .model import Interface, Params, Space

NAME = "design_space"
FILES = (f"{NAME}.npz", f"{NAME}.json")
"""The two files a design space is kept as, in the project's folder."""


def paths(root: Path) -> tuple[Path, Path]:
    return root / FILES[0], root / FILES[1]


def exists(root: Path) -> bool:
    return all(p.is_file() for p in paths(root))


def load(root: Path, digest: str | None = None) -> Space | None:
    """The design space kept in a project's folder - or None when there is none, when it cannot be
    read, or when it was defined on another CAD than ``digest``."""
    arrays_path, summary_path = paths(root)
    if not exists(root):
        return None
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if digest and summary.get("source_digest") not in (None, "", digest):
            return None
        with np.load(arrays_path) as data:
            arrays = {k: data[k] for k in data.files}
        grid = Grid(
            origin=tuple(float(v) for v in arrays["origin"]),
            spacing_mm=float(arrays["spacing"]),
            shape=tuple(int(v) for v in arrays["shape"]),
        )
        params = Params(
            **{
                k: tuple(v) if isinstance(v, list) else v
                for k, v in summary["params"].items()
                if k in Params.__dataclass_fields__
            }
        )
        interfaces = [
            Interface(**{k: v for k, v in i.items() if k in Interface.__dataclass_fields__})
            for i in summary.get("interfaces", [])
        ]
    except Exception:  # noqa: BLE001 - a file that cannot be read is no design space, never an error
        return None
    return Space(
        grid=grid,
        params=params,
        labels=arrays["labels"],
        interfaces=interfaces,
        stats=summary.get("stats", {}),
        source_digest=summary.get("source_digest", ""),
        defined_by=summary.get("defined_by", "engineer"),
        seconds=float(summary.get("seconds", 0.0)),
        benefit=arrays.get("benefit"),
    )


def save(root: Path, space: Space) -> None:
    """Keep a design space in the project's folder, each file written whole or not at all."""
    arrays_path, summary_path = paths(root)
    arrays = {
        "labels": space.labels,
        "origin": np.asarray(space.grid.origin),
        "spacing": np.asarray(space.grid.spacing_mm),
        "shape": np.asarray(space.grid.shape),
    }
    if space.benefit is not None:
        arrays["benefit"] = space.benefit
    partial = arrays_path.with_name(f"{NAME}.partial.npz")
    np.savez_compressed(partial, **arrays)
    partial.replace(arrays_path)
    partial_json = summary_path.with_name(f"{NAME}.partial.json")
    partial_json.write_text(json.dumps(space.summary(), indent=1, default=str), encoding="utf-8")
    partial_json.replace(summary_path)


def defined(  # type: ignore[no-untyped-def]
    extraction,
    setup: Callable[[], Any],
    root: Path,
    again: bool = False,
    say: Callable[[str], None] | None = None,
) -> tuple[Space, bool]:
    """The project's design space, and whether it was read from its folder: read when it is there
    and was defined on this CAD, defined by the rules and kept there otherwise. ``setup`` gives the
    solver deck's setup, read only when the rules need it. ``again`` defines it anew - never over
    one the engineer brought."""
    from .derive import derive

    found = load(root, extraction.cad_digest)
    if found is not None and (not again or found.defined_by != "rules"):
        return found, True
    space = derive(extraction, setup=setup(), params=Params(), root=root, say=say)
    save(root, space)
    return space, False
