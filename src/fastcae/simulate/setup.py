"""What a deck asks for, in words that do not depend on the solver.

Every item keeps the deck's own names - the group it acts on, and the load set (the deck's
variable) it belongs to - so what is shown and solved here is what the engineer wrote, and a design
solved later is asked for exactly the same things.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

# Degrees of freedom: translations and rotations.
TRANSLATIONS = ("DX", "DY", "DZ")
ROTATIONS = ("DRX", "DRY", "DRZ")
FORCES = ("FX", "FY", "FZ")
MOMENTS = ("MX", "MY", "MZ")


@dataclass
class Material:
    """A linear-elastic material and the cell groups it fills (none named: all of them)."""

    name: str
    young: float
    poisson: float
    density: float | None = None
    groups: list[str] = field(default_factory=list)


@dataclass
class Held:
    """Degrees of freedom held at the values given, on the nodes of each group."""

    load_set: str
    groups: list[str]
    dofs: dict[str, float]


@dataclass
class Rigid:
    """Nodes tied to move as one rigid body - a kinematic coupling. ``reference`` is the single-node
    group among ``groups``, when there is one: the point the body is held or loaded through."""

    load_set: str
    groups: list[str]
    reference: str | None = None


@dataclass
class Distributing:
    """A distributing coupling: the reference node's load spread over the group's nodes with the
    weights given, and its motion the weighted average of theirs. It adds no stiffness."""

    load_set: str
    reference: str
    group: str
    reference_dofs: list[str]
    group_dofs: list[str]
    weights: list[float]


@dataclass
class NodalLoad:
    """Forces and moments applied at the nodes of a group."""

    load_set: str
    group: str
    values: dict[str, float]


@dataclass
class SurfaceLoad:
    """A traction (force per area) or a pressure on the cells of a group."""

    load_set: str
    kind: str
    group: str
    values: dict[str, float]


@dataclass
class Output:
    """A signal the deck reads off the answer: a field's components at the nodes of a group,
    under the name the deck gives it."""

    name: str
    group: str
    field: str
    components: list[str] | None
    operation: str
    table: str


@dataclass
class Analysis:
    """How the deck solves: the kind of analysis, the load sets it applies, the fields it computes
    and where it writes them."""

    kind: str
    load_sets: list[str]
    solver: dict[str, Any] = field(default_factory=dict)
    fields: list[str] = field(default_factory=list)
    written: list[str] = field(default_factory=list)


@dataclass
class Setup:
    """Everything a deck asks for, with what could not be read said plainly."""

    materials: list[Material] = field(default_factory=list)
    held: list[Held] = field(default_factory=list)
    rigid: list[Rigid] = field(default_factory=list)
    distributing: list[Distributing] = field(default_factory=list)
    nodal_loads: list[NodalLoad] = field(default_factory=list)
    surface_loads: list[SurfaceLoad] = field(default_factory=list)
    outputs: list[Output] = field(default_factory=list)
    analysis: Analysis | None = None
    model: list[dict[str, Any]] = field(default_factory=list)
    discrete: list[dict[str, Any]] = field(default_factory=list)
    not_read: list[str] = field(default_factory=list)

    def active(self) -> set[str]:
        """The load sets the analysis applies - every one, when the deck names none."""
        if self.analysis is None or not self.analysis.load_sets:
            return {
                item.load_set
                for item in [
                    *self.held,
                    *self.rigid,
                    *self.distributing,
                    *self.nodal_loads,
                    *self.surface_loads,
                ]
            }
        return set(self.analysis.load_sets)

    def resolve(self, single_node: set[str]) -> None:
        """Name each rigid coupling's reference: the one group among its groups holding one node."""
        for tie in self.rigid:
            if tie.reference is None:
                refs = [g for g in tie.groups if g in single_node]
                tie.reference = refs[0] if len(refs) == 1 else None

    def to_json(self) -> dict[str, Any]:
        return _plain(asdict(self))


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    return value
