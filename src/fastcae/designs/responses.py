"""What a solved design did under each of the deck's loads on its own.

A linear static analysis is linear in its loads, so one factorisation answers every load at once:
the solve already puts each component of every nodal load through as its own right-hand side
(:func:`..simulate.solve.solve` with ``components``). Keeping those answers whole - one field a
component, beside the design's own result - means a question the study never asked can be answered
later by adding them up, at no solver cost: another mix of the same loads, a bearing nobody scored,
a robustness band wider than the one the campaign used.

That is what makes a campaign's designs worth keeping as data. A surrogate trained on one
objective learns that objective; a surrogate trained on these learns the part's response, and the
objective becomes something read off it afterwards.

What is *not* here: the answer under a load the deck never applied. These are the deck's own load
components, each at the deck's own value, so a mix is written as a scale on each - 1.0 being the
deck as it stands.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

NAME = "components.npz"


@dataclass(frozen=True)
class Responses:
    """Every node's displacement under each load component of the deck, on its own."""

    u: np.ndarray
    """(nodes, 3, components), in the deck's length unit."""
    loads: list[str]
    """Each component as ``group:component``, for example ``REF_BORE_MAIN_S2:FX``."""
    values: np.ndarray
    """The deck's own value for each, the one its field was solved at."""

    @property
    def deck(self) -> np.ndarray:
        """The deck as it stands: every component at its own value, so their sum.

        This is the design's ``result.npz`` again, up to the solver's tolerance - unless the deck
        also presses on faces or holds a node away from where it lies, neither of which is a
        component here.
        """
        return self.u.sum(axis=2)

    def under(self, scales: dict[str, float] | np.ndarray) -> np.ndarray:
        """The answer under a mix of the deck's loads, each scaled: by name, or a scale each.

        A scale of 1 leaves a load as the deck applies it, 0 takes it away, 1.05 raises it by a
        twentieth - which is how a robustness band over the bearing loads is written.
        """
        if isinstance(scales, dict):
            unknown = set(scales) - set(self.loads)
            if unknown:
                raise KeyError(f"the deck has no load {sorted(unknown)}")
            w = np.array([scales.get(name, 1.0) for name in self.loads], np.float64)
        else:
            w = np.asarray(scales, np.float64)
            if w.shape != (len(self.loads),):
                raise ValueError(f"{len(self.loads)} scales wanted, {w.shape} given")
        return self.u @ w


def path(folder: Path | str) -> Path:
    """Where a solved design keeps its per-load answers."""
    return Path(folder) / NAME


def read(folder: Path | str) -> Responses | None:
    """A design's per-load answers, or None when it was solved before they were kept."""
    here = path(folder)
    if not here.exists():
        return None
    z = np.load(here)
    return Responses(u=z["u"], loads=[str(s) for s in z["loads"]], values=z["values"])
