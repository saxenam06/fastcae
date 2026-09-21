"""Design volumes over HTTP: what the faces an engineer picks bound, as a see-through volume to
accept or change, and the volumes the project keeps.

A proposal is found from the picks - a second or two - and kept in memory under its recipe's key,
with its surface; accepting it writes the recipe with the project. Every surface travels in the
part's own mesh format.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from ..volumes import store
from ..volumes import volume as volumes

router = APIRouter()

KEEP = 12
"""Volumes found and kept in memory - proposals and accepted ones alike, the most recent first."""

_found: OrderedDict[str, volumes.Volume] = OrderedDict()


def _open():  # type: ignore[no-untyped-def]
    from .app import _resume, _state

    if _state.project is None or _state.extraction is None:
        _resume()  # the server restarts on a source change; pick the session back up
    if _state.project is None or _state.extraction is None:
        raise HTTPException(409, "no project is open")
    return _state.project, _state.extraction


def _setup(project):  # type: ignore[no-untyped-def]
    from ..simulate import baseline

    deck = baseline.read_deck(project)
    return deck.setup if deck is not None else None


def _find(recipe: volumes.Recipe) -> volumes.Volume:
    key = recipe.key()
    if key in _found:
        _found.move_to_end(key)
        return _found[key]
    project, extraction = _open()
    found = volumes.find(extraction, recipe, _setup(project))
    _found[key] = found
    while len(_found) > KEEP:
        _found.popitem(last=False)
    return found


class Picks(BaseModel):
    faces: list[int]
    band: list[float] | None = None
    off: list[str] | None = None


@router.post("/api/volumes/propose")
def propose(picks: Picks) -> dict[str, Any]:
    """The volume the picks bound: found, kept under its key, and described."""
    _, extraction = _open()
    band = tuple(picks.band) if picks.band and len(picks.band) == 2 else None
    try:
        recipe = volumes.recipe(extraction, picks.faces, band, picks.off)  # type: ignore[arg-type]
        found = _find(recipe)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {**found.summary(), "mesh": f"/api/volumes/mesh/{recipe.key()}"}


@router.get("/api/volumes/mesh/{key}")
def mesh(key: str) -> Response:
    """A volume's closed surface, see-through on the part."""
    from .mesh import encode

    found = _found.get(key)
    if found is None:
        # An accepted volume not in memory: found again from its recipe.
        project, extraction = _open()
        for entry in store.load(project.root, extraction.cad_digest):
            recipe = store.recipe_of(entry)
            if recipe.key() == key:
                found = _find(recipe)
                break
    if found is None:
        raise HTTPException(404, f"no volume {key} is known; propose it again")
    corners, triangles, normals = found.surface()
    if not len(triangles):
        raise HTTPException(404, "the volume is empty")
    body = encode(
        corners,
        triangles,
        np.zeros(len(triangles), np.uint32),
        normals=normals[triangles.ravel()],
    )
    return Response(content=body, media_type="application/octet-stream")


@router.get("/api/volumes")
def listed() -> dict[str, Any]:
    """The volumes the project keeps, each with its surface."""
    project, extraction = _open()
    out = []
    for entry in store.load(project.root, extraction.cad_digest):
        key = store.recipe_of(entry).key()
        out.append({**entry, "key": key, "mesh": f"/api/volumes/mesh/{key}"})
    return {"volumes": out}


class Accept(BaseModel):
    faces: list[int]
    band: list[float] | None = None
    off: list[str] | None = None
    name: str | None = None


@router.post("/api/volumes")
def accept(body: Accept) -> dict[str, Any]:
    """Keep the volume these picks bound, under a name."""
    project, extraction = _open()
    band = tuple(body.band) if body.band and len(body.band) == 2 else None
    try:
        recipe = volumes.recipe(extraction, body.faces, band, body.off)  # type: ignore[arg-type]
        found = _find(recipe)
        entry = store.add(project.root, extraction.cad_digest, recipe, found.summary(), body.name)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {**entry, "key": recipe.key(), "mesh": f"/api/volumes/mesh/{recipe.key()}"}


@router.delete("/api/volumes/{name}")
def delete(name: str) -> dict[str, Any]:
    project, extraction = _open()
    if not store.remove(project.root, extraction.cad_digest, name):
        raise HTTPException(404, f"there is no volume {name}")
    return listed()
