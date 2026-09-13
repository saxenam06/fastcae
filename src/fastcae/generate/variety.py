"""Which of many designs differ most, and each drawn as a plan - to look through a few dozen of the
thousands Go kept, as paths rather than as geometry.

**What a design is, to compare it.** Every design is described by what it is made of, block by
block: for ribs, how many, how long in all, which way they run, where they lie, how thick and how
tall, how many pads, how far the floor was thickened for them; for holes, how many, how big, how far
apart, where; for faces moved, how far; the material; and the mass. Each property is scaled to the
spread the designs cover, and each block counts as much as any other - so a block with many
properties does not outweigh one with a single offset.

**The most varied** are chosen by farthest-point selection: the design farthest from the middle of
them all first, then each next the one farthest from every one chosen so far. Deterministic: the
same designs give the same choice.

**A plan** is a design seen along the pull - or along the part's own axis nearest it - on the plane
square to it: each rib and pad as a line, each hole as a circle, over the outlines of the faces the
study names and of the part's bores, so each design is seen where it is on the part.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .. import knowledge
from ..features import FeatureKind, FeatureSet
from ..geometry.brep import Tessellation


def most_varied(
    designs: list[dict], k: int, axes: tuple[np.ndarray, np.ndarray] | None = None
) -> list[int]:
    """The positions in ``designs`` of the ``k`` that differ most from each other - which way ribs
    run and where they lie measured on the plane of ``axes``, else x and y."""
    if len(designs) <= k:
        return list(range(len(designs)))
    points = properties(designs, axes)
    middle = points.mean(axis=0)
    chosen = [int(np.argmax(np.linalg.norm(points - middle, axis=1)))]
    nearest = np.linalg.norm(points - points[chosen[0]], axis=1)
    while len(chosen) < k:
        far = int(np.argmax(nearest))
        if nearest[far] <= 0.0:
            break
        chosen.append(far)
        nearest = np.minimum(nearest, np.linalg.norm(points - points[far], axis=1))
    return chosen


def properties(
    designs: list[dict], axes: tuple[np.ndarray, np.ndarray] | None = None
) -> np.ndarray:
    """Every design as a row of properties, each scaled to the spread the designs cover, each block
    weighed alike."""
    if axes is None:
        axes = (np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]))
    groups: dict[str, list[list[float]]] = {}
    for design in designs:
        for block, row in _described(design, axes).items():
            groups.setdefault(block, []).append(row)
    blocks = [b for b, rows in groups.items() if len(rows) == len(designs)]
    columns = []
    for block in sorted(blocks):
        table = np.asarray(groups[block], dtype=float)
        spread = table.max(axis=0) - table.min(axis=0)
        varied = spread > 1e-9
        if not varied.any():
            continue
        scaled = (table[:, varied] - table[:, varied].min(axis=0)) / spread[varied]
        columns.append(scaled / math.sqrt(varied.sum()))
    if not columns:
        return np.zeros((len(designs), 1))
    return np.concatenate(columns, axis=1)


def _described(design: dict, axes: tuple[np.ndarray, np.ndarray]) -> dict[str, list[float]]:
    """A design's properties, by block - and the design's own mass."""
    out: dict[str, list[float]] = {}
    for block, made in design.get("made_of", {}).items():
        kind = made.get("kind")
        if kind == "ribs":
            out[block] = _ribs(_on(made, axes, ("ribs", "pads")))
        elif kind == "holes":
            out[block] = _holes(_on(made, axes, ("holes",)))
        elif kind == "thicken":
            out[block] = [float(made.get("offset_mm", 0.0)), float(made.get("blend_mm", 0.0))]
        elif kind == "material":
            # One of the catalogue's, each as far from every other.
            out[block] = [float(made.get("material") == m["id"]) for m in knowledge.materials()]
    out["mass"] = [float(design.get("mass_kg") or 0.0)]
    return out


def _on(made: dict, axes: tuple[np.ndarray, np.ndarray], keys: tuple[str, ...]) -> dict:
    """What a block made, its points on the plane of ``axes``."""
    e1, e2 = axes

    def at(point) -> list[float]:
        p = np.asarray(point, dtype=float)
        return [float(p @ e1), float(p @ e2), 0.0]

    out = dict(made)
    for key in keys:
        out[key] = [
            {
                **item,
                **{name: at(item[name]) for name in ("start", "end", "centre") if name in item},
            }
            for item in made.get(key, [])
        ]
    return out


def _ribs(made: dict) -> list[float]:
    """How many ribs, how long in all, which way they run - as the doubled angle's mean, so a line
    and its reverse agree - where their middle lies, how thick and how tall, pads, the floor."""
    ribs = made.get("ribs", [])
    if not ribs:
        return [0.0] * 9 + [float(made.get("floor_raised_mm", 0.0))]
    start = np.array([r["start"] for r in ribs], dtype=float)
    end = np.array([r["end"] for r in ribs], dtype=float)
    line = end - start
    length = np.linalg.norm(line[:, :2], axis=1)
    angle = 2.0 * np.arctan2(line[:, 1], line[:, 0])
    weights = length / max(float(length.sum()), 1e-9)
    middle = ((start + end) / 2.0)[:, :2].T @ weights
    return [
        float(len(ribs)),
        float(length.sum()),
        float(np.cos(angle) @ weights),
        float(np.sin(angle) @ weights),
        float(middle[0]),
        float(middle[1]),
        float(np.mean([r["thickness_mm"] for r in ribs])),
        float(np.mean([max(r["heights_mm"]) for r in ribs])),
        float(len(made.get("pads", []))),
        float(made.get("floor_raised_mm", 0.0)),
    ]


def _holes(made: dict) -> list[float]:
    holes = made.get("holes", [])
    if not holes:
        return [0.0] * 5
    centres = np.array([h["centre"] for h in holes], dtype=float)[:, :2]
    gaps = np.linalg.norm(centres[:, None, :] - centres[None, :, :], axis=2)
    gaps[np.diag_indices(len(holes))] = np.inf
    pitch = float(np.min(gaps)) if len(holes) > 1 else 0.0
    middle = centres.mean(axis=0)
    return [
        float(len(holes)),
        float(holes[0]["diameter_mm"]),
        pitch,
        float(middle[0]),
        float(middle[1]),
    ]


# --- plans ---------------------------------------------------------------------------------------


def plane_of(direction: np.ndarray | None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The plane a plan is drawn on: square to ``direction`` - the pull - looked at from the side
    it mostly points to, so a plan along z is a view from above. Its normal and two axes."""
    n = np.array([0.0, 0.0, 1.0]) if direction is None else np.asarray(direction, dtype=float)
    n = n / np.linalg.norm(n)
    if n[int(np.argmax(np.abs(n)))] < 0.0:
        n = -n
    reference = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = reference - (reference @ n) * n
    e1 = e1 / np.linalg.norm(e1)
    return n, e1, np.cross(n, e1)


def planned(made_of: dict, axes: tuple[np.ndarray, np.ndarray]) -> dict[str, Any]:
    """A design on the plan: its ribs and pads as lines, its holes as circles, each with its
    block."""
    e1, e2 = axes

    def at(point) -> list[float]:
        p = np.asarray(point, dtype=float)
        return [round(float(p @ e1), 1), round(float(p @ e2), 1)]

    ribs, pads, holes = [], [], []
    for block, made in made_of.items():
        if made.get("kind") == "ribs":
            ribs += [[*at(r["start"]), *at(r["end"]), block] for r in made.get("ribs", [])]
            pads += [[*at(p["start"]), *at(p["end"]), block] for p in made.get("pads", [])]
        elif made.get("kind") == "holes":
            holes += [
                [*at(h["centre"]), round(h["diameter_mm"] / 2.0, 1), block]
                for h in made.get("holes", [])
            ]
    return {"ribs": ribs, "pads": pads, "holes": holes}


def outlines(
    features: FeatureSet, tess: Tessellation, refs: list[str], axes: tuple[np.ndarray, np.ndarray]
) -> list[list[float]]:
    """The outlines of the faces of ``refs`` and of the part's bores, on the plan, as short lines:
    every edge of their facets that only one facet of them has."""
    faces = {f for ref in refs if features.get(ref) is not None for f in features.get(ref).face_ids}
    faces |= {f for bore in features.of_kind(FeatureKind.BORE) for f in bore.face_ids}
    if not faces:
        return []
    mine = np.isin(tess.face_id, list(faces))
    triangles = tess.triangles[mine]
    edges = np.sort(
        np.concatenate([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]]), axis=1
    )
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    boundary = unique[counts == 1]
    e1, e2 = axes
    ends = tess.vertices[boundary]  # (m, 2, 3)
    plan = np.stack([ends @ e1, ends @ e2], axis=-1)  # (m, 2, 2)
    plan = np.round(plan, 1)
    keep = np.linalg.norm(plan[:, 0] - plan[:, 1], axis=1) > 0.5
    lines = np.unique(plan[keep].reshape(-1, 4), axis=0)
    return lines.tolist()
