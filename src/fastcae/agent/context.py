"""What the agent works on: the open project, what was read from it, and one conversation.

The conversation keeps what the engineer wrote, in order; how many questions the agent has asked of
the part since they last wrote, so that past a few it is reminded the engineer can be asked instead;
and what changed in a turn, for the interface to read again. **The part's surface is opened once**,
the first time a question needs a ray cast through it - how thick the metal is, what lies across or
between things - and kept for the rest of the conversation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..extract import Extraction
from ..geometry.brep import Tessellation
from ..project import Project


@dataclass
class Context:
    """One conversation with the agent, over one open project."""

    project: Project
    extraction: Extraction
    said: list[str] = field(default_factory=list)
    """What the engineer wrote to the agent, in order."""
    questions: int = 0
    """Questions the agent has asked of the part since the engineer last wrote."""
    changed: set[str] = field(default_factory=set)
    """What the agent changed in a turn, for the interface to read again."""
    measure: _Faces | None = None
    """The part's surface, for casting rays through: opened the first time it is needed."""


def measure(ctx: Context) -> _Faces:
    """The part's surface, for casting rays through - opened the first time it is asked for, then
    kept with the conversation."""
    if ctx.measure is None:
        assert ctx.extraction.tess is not None
        ctx.measure = _Faces(ctx.extraction.tess)
    return ctx.measure


class _Faces:
    """The part's tessellated surface, for casting rays through: how far the metal goes from a
    point inside it - and, on ``mesh``, what a ray meets first and what lies inside the part."""

    def __init__(self, tess: Tessellation):
        import trimesh

        self.tess = tess
        self.mesh = trimesh.Trimesh(tess.vertices, tess.triangles, process=False)

    def exit_along(self, inside: np.ndarray, direction: np.ndarray) -> float | None:
        """How far from a point inside the metal, along ``direction``, the metal ends."""
        distance = self.exits_along(np.asarray(inside, dtype=float).reshape(1, 3), direction)[0]
        return None if np.isnan(distance) else float(distance)

    def exits_along(self, inside: np.ndarray, direction: np.ndarray) -> np.ndarray:
        """The same for many points at once, in one cast: NaN where nothing is met."""
        return self.through(inside, direction)[0]

    def through(self, inside: np.ndarray, direction: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """How far from points inside the metal, along ``direction`` - one for all, or one each -
        the metal ends, and the face it ends at: NaN and -1 where nothing is met."""
        origins = np.asarray(inside, dtype=float).reshape(-1, 3)
        out = np.full(len(origins), np.nan)
        faces = np.full(len(origins), -1, dtype=np.int64)
        if not len(origins):
            return out, faces
        directions = np.asarray(direction, dtype=float)
        if directions.ndim == 1:
            directions = np.tile(directions, (len(origins), 1))
        hits, rays, triangles = self.mesh.ray.intersects_location(
            origins, directions, multiple_hits=False
        )
        if len(hits):
            out[rays] = np.linalg.norm(hits - origins[rays], axis=1)
            faces[rays] = self.tess.face_id[triangles]
        return out, faces
