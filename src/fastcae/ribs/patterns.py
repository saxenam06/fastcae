"""A pattern: the ribs a design is made of, each with its thickness, what the optimiser scored
it and the metal it adds - what :func:`.campaign.realise` is handed, and what the design's record
keeps."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


@dataclass
class Pattern:
    """One pattern: the ribs kept, each with its thickness."""

    ribs: list[tuple[str, float]]
    score: float
    metal_L: float
    mirrors: dict[str, float | None] = field(default_factory=dict)
    """Each volume's mirror plane, as its angle about the axis, where one was held."""

    def summary(self) -> dict[str, Any]:
        return {
            "ribs": [{"id": i, "thickness_mm": t} for i, t in self.ribs],
            "count": len(self.ribs),
            "score": round(self.score, 4),
            "metal_L": round(self.metal_L, 3),
            "mirrors": self.mirrors,
        }
