"""Variants: one change in one place, kept in the project's library.

A variant is ribs on a floor, webs between two faces, faces made thicker or thinner, or holes
through a plate - with what it may vary and every rule it holds. It is a study of one block: the
same schema, checked by the same function, versioned the same way - except that its versions are
never shown, and it is called by a name that says what it changes and where.

**Kept in** ``<project>/variants/<id>.json``. Its id is five characters - a letter, then letters
and digits - unique in the project; its block's id is the same, so another variant names its ribs
``ribs:<id>`` and its holes ``holes:<id>``. The library is read here, never written: campaigns are
made from the variants in it, and each campaign keeps its own copy of those it used.
"""

from __future__ import annotations

import string
from typing import Any

from . import study as studies
from .project import Project

FOLDER = "variants"

_FIRST = string.ascii_lowercase
_REST = string.ascii_lowercase + string.digits


def load(project: Project, vid: str) -> studies.Study | None:
    """A variant of the library, or None."""
    if not _safe(vid):
        return None
    found = studies.load(project, vid, FOLDER)
    return found if found is not None and found.versions else None


def library(project: Project) -> list[studies.Study]:
    """Every variant kept, oldest first."""
    found = [load(project, path.stem) for path in _files(project)]
    kept = [variant for variant in found if variant is not None]
    return sorted(kept, key=lambda v: (v.versions[0].created, v.name))


def kind_of(block: studies.Block) -> str:
    """What a variant adds, as the card calls it."""
    if block.add == "ribs" and not block.where.support:
        return "webs"
    return block.add


def suggested_label(block: studies.Block) -> str:
    """A name that says what a variant changes and where."""
    kind = kind_of(block)
    if kind == "webs":
        return f"Webs between {_listed(block.where.anchors)}"
    if kind == "thicken":
        return f"{_listed(block.where.support)} thicker or thinner"
    if kind == "holes":
        return f"Holes in {_listed(block.where.support)}"
    return f"Ribs on {_listed(block.where.support)}"


def listed(variant: studies.Study, used_in: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """A variant as the library shows it: code, name, kind, where, how many combinations it
    allows, and which campaigns used it - and whether it changed since each did."""
    version = variant.current
    block = version.blocks[0]
    count = studies.combinations(block)
    return {
        "id": variant.name,
        "label": variant.label or suggested_label(block),
        "kind": kind_of(block),
        "stand_on": list(block.where.support),
        "end_on": list(block.where.anchors),
        "combinations": count,
        "version": version.version,
        "created": variant.versions[0].created,
        "changed": version.created,
        "used_in": [
            {**use, "changed_since": use.get("version", version.version) != version.version}
            for use in used_in or []
        ],
    }


def _files(project: Project):
    folder = project.root / FOLDER
    return sorted(folder.glob("*.json")) if folder.is_dir() else []


def _safe(vid: str) -> bool:
    return len(vid) == 5 and vid[0] in _FIRST and all(c in _REST for c in vid[1:])


def _listed(refs: list[str]) -> str:
    if not refs:
        return "what is read off the part"
    if len(refs) == 1:
        return refs[0]
    if len(refs) == 2:
        return f"{refs[0]} and {refs[1]}"
    return f"{refs[0]} and {len(refs) - 1} more"
