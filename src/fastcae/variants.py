"""Variants: one change in one place, kept in the project's library.

A variant is ribs on a floor, webs between two faces, faces made thicker or thinner, or holes
through a plate - with what it may vary and every rule it holds. It is a study of one block: the
same schema, checked by the same function, versioned the same way - except that its versions are
never shown, and it is called by a name that says what it changes and where.

**Kept in** ``<project>/variants/<id>.json``. Its id is five characters - a letter, then letters
and digits - random and unique in the project; its block's id is the same, so another variant
names its ribs ``ribs:<id>`` and its holes ``holes:<id>``. Deleting one moves its file aside, into
``variants/.deleted/``: a campaign that used it keeps its own copy anyway.

Campaigns are made from variants, never from the draft being authored.
"""

from __future__ import annotations

import secrets
import shutil
import string
from typing import Any

from . import study as studies
from .project import Project

FOLDER = "variants"
DELETED = ".deleted"

# What a variant adds, as the card calls it: webs are ribs with nothing under them.
KINDS = ("ribs", "webs", "thicken", "holes")

_FIRST = string.ascii_lowercase
_REST = string.ascii_lowercase + string.digits


def new_id(project: Project) -> str:
    """An id no variant of the project has had: a letter, then four letters or digits."""
    taken = {path.stem for path in _files(project)} | {
        path.stem for path in (project.root / FOLDER / DELETED).glob("*.json")
    }
    while True:
        vid = secrets.choice(_FIRST) + "".join(secrets.choice(_REST) for _ in range(4))
        if vid not in taken:
            return vid


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


def kinds(project: Project, but: str | None = None) -> dict[str, str]:
    """What each variant adds, by id - whose ribs or holes a rule of another may name."""
    return {
        variant.name: variant.current.blocks[0].add
        for variant in library(project)
        if variant.name != but and variant.current.blocks
    }


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


def rename(project: Project, vid: str, label: str) -> None:
    variant = load(project, vid)
    if variant is None:
        raise ValueError(f"there is no variant {vid}")
    variant.label = label.strip() or variant.label
    studies.save(project, variant, FOLDER)


def duplicate(project: Project, vid: str) -> str:
    """A copy of a variant under a new id - its block and every rule it holds renamed with it."""
    variant = load(project, vid)
    if variant is None:
        raise ValueError(f"there is no variant {vid}")
    new = new_id(project)
    copied = variant.model_copy(deep=True)
    copied.name = new
    copied.label = f"{variant.label} (copy)"
    for version in copied.versions:
        for block in version.blocks:
            if block.id == vid:
                block.id = new
        for constraint in version.constraints:
            if constraint.block == vid:
                constraint.block = new
    studies.save(project, copied, FOLDER)
    return new


def delete(project: Project, vid: str) -> None:
    """A variant taken out of the library - its file moved aside, never lost."""
    path = studies.path_of(project, vid, FOLDER)
    if not _safe(vid) or not path.is_file():
        raise ValueError(f"there is no variant {vid}")
    aside = project.root / FOLDER / DELETED
    aside.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(aside / path.name))


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
