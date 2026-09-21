"""Design volumes kept with the project: the recipes an engineer accepted, beside their own files.

``<project>/volumes/volumes.json`` holds each accepted volume's name, recipe and what it held when
it was accepted. The recipe is the volume: it is found again from the CAD whenever it is drawn or
used, so the file stays small and says exactly what was chosen. Volumes accepted on another CAD
are read back only while that CAD is the project's.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .volume import Recipe

FILE = "volumes.json"


def _path(root: Path) -> Path:
    return Path(root) / "volumes" / FILE


def load(root: Path, digest: str | None) -> list[dict[str, Any]]:
    """The volumes accepted on this CAD, oldest first."""
    path = _path(root)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if digest is not None and data.get("cad_digest") not in (None, digest):
        return []
    return list(data.get("volumes", []))


def _save(root: Path, digest: str | None, volumes: list[dict[str, Any]]) -> None:
    path = _path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"cad_digest": digest, "volumes": volumes}
    path.write_text(json.dumps(body, indent=1), encoding="utf-8")


def recipe_of(entry: dict[str, Any]) -> Recipe:
    return Recipe(**entry["recipe"])


def add(
    root: Path, digest: str | None, recipe: Recipe, summary: dict[str, Any], name: str | None
) -> dict[str, Any]:
    """Keep a volume under a name - the one given, or the next free ``V<n>``."""
    volumes = load(root, digest)
    taken = {v["name"] for v in volumes}
    if not name:
        n = 1
        while f"V{n}" in taken:
            n += 1
        name = f"V{n}"
    elif name in taken:
        raise ValueError(f"there is a volume called {name} already")
    entry = {
        "name": name,
        "accepted": time.strftime("%Y-%m-%d %H:%M"),
        "recipe": summary_recipe(recipe),
        "volume_L": summary.get("volume_L"),
        "words": summary.get("words"),
    }
    volumes.append(entry)
    _save(root, digest, volumes)
    return entry


def remove(root: Path, digest: str | None, name: str) -> bool:
    volumes = load(root, digest)
    kept = [v for v in volumes if v["name"] != name]
    if len(kept) == len(volumes):
        return False
    _save(root, digest, kept)
    return True


def summary_recipe(recipe: Recipe) -> dict[str, Any]:
    return asdict(recipe)
