"""The chooser: which of the fins the physics has placed and valued make the network - decided by
CP-SAT, for value, under every rule that is a decision rather than a number.

A gradient optimiser moves numbers; it cannot decide. Whether a fin exists, which of two ribs that
cannot both stand survives, whether a hoop's spokes are there to carry it, whether a branch has its
spine, that a mirror pair stands or falls together - these are yes-or-no choices, and left to a
continuous solver they are settled by fading, not choosing: from twenty-four seeded fins crowding
one another, a run under the spacing rule kept two. Here they are settled as choices, in seconds.

The chooser sees a **table**, never geometry: each fin's value (what the objective loses without
it), its metal, its volume, and its relations to the others. It keeps the most value the rules
allow, and says of every fin it left out which rule removed it. It never moves a fin and never
adds one - the seeding must be rich enough, and the continuous pass before it must have done the
placing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import shapely
from ortools.sat.python import cp_model

from . import fins, oracle

SCALE = 1000.0
CROSS_DEG = 60.0
"""A crossing this steep or steeper is a junction the foundry casts; shallower, the two ribs
crowd each other and one must go."""
"""Values and litres are held as integers this many to one."""
NEEDS = 3
"""How many of the fins it needs a fin must have - a hoop, this many of its spokes."""


@dataclass
class Table:
    """The fins as the chooser sees them."""

    ids: list[str]
    volume: list[str]
    value: np.ndarray
    """What the objective loses without each fin: positive is worth keeping."""
    metal_L: np.ndarray
    conflicts: set[tuple[int, int]] = field(default_factory=set)
    """Pairs that cannot both stand: crowding, or crossing too shallow."""
    junctions: set[tuple[int, int]] = field(default_factory=set)
    """Pairs that may both stand and meet - a crossing steep enough, a tee."""
    needs: dict[int, list[int]] = field(default_factory=dict)
    """A fin and the fins it needs :data:`NEEDS` of - a hoop and its spokes."""
    spine: dict[int, int] = field(default_factory=dict)
    """A branch and the fin it leaves from."""
    mirror: dict[int, int] = field(default_factory=dict)
    """A fin and its mirror: together or not at all."""
    covers: dict[str, list[int]] = field(default_factory=dict)
    """A region that must keep at least one of these fins."""
    nodes: list[list[int]] = field(default_factory=list)
    """Fins meeting at one node, at most so many of them (``valence``)."""


@dataclass
class Choice:
    """One network: the fins kept, and why every other was not."""

    kept: list[int]
    score: float
    metal_L: float
    why: dict[str, str] = field(default_factory=dict)

    def summary(self, table: Table) -> dict[str, Any]:
        return {
            "kept": [table.ids[i] for i in self.kept],
            "score": round(self.score, 4),
            "metal_L": round(self.metal_L, 3),
            "why": dict(self.why),
        }


def choose(
    table: Table,
    budget_L: float,
    most: int = 12,
    least_L: float = 0.0,
    alternatives: int = 1,
    differ_by: int = 2,
    valence: int = 4,
) -> list[Choice]:
    """The best networks the rules allow, each differing from every one before by at least
    ``differ_by`` fins."""
    n = len(table.ids)
    model = cp_model.CpModel()
    keep = [model.NewBoolVar(f"keep{i}") for i in range(n)]
    value = [int(round(SCALE * float(v))) for v in table.value]
    metal = [int(round(SCALE * float(m))) for m in table.metal_L]
    model.Add(sum(m * k for m, k in zip(metal, keep, strict=True)) <= int(round(SCALE * budget_L)))
    if least_L > 0.0:
        model.Add(
            sum(m * k for m, k in zip(metal, keep, strict=True)) >= int(round(SCALE * least_L))
        )
    for i, j in table.conflicts:
        model.Add(keep[i] + keep[j] <= 1)
    for i, them in table.needs.items():
        want = min(NEEDS, len(them))
        if want:
            model.Add(want * keep[i] <= sum(keep[j] for j in them))
        else:
            model.Add(keep[i] == 0)
    for i, j in table.spine.items():
        model.Add(keep[i] <= keep[j])
    for i, j in table.mirror.items():
        model.Add(keep[i] == keep[j])
    for _, them in table.covers.items():
        if them:
            model.Add(sum(keep[j] for j in them) >= 1)
    for them in table.nodes:
        model.Add(sum(keep[j] for j in them) <= valence)
    for name in sorted(set(table.volume)):
        mine = [i for i in range(n) if table.volume[i] == name]
        model.Add(sum(keep[i] for i in mine) <= most)
    model.Maximize(sum(v * k for v, k in zip(value, keep, strict=True)))

    found: list[Choice] = []
    for _ in range(max(1, alternatives)):
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 20.0
        solver.parameters.num_workers = 8
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break
        kept = [i for i in range(n) if solver.Value(keep[i])]
        found.append(
            Choice(
                kept,
                solver.ObjectiveValue() / SCALE,
                float(table.metal_L[kept].sum()) if kept else 0.0,
                _why(table, kept, budget_L, most, valence),
            )
        )
        # the next differs from this one by at least so many fins
        chosen = set(kept)
        model.Add(
            sum(1 - keep[i] for i in chosen) + sum(keep[i] for i in range(n) if i not in chosen)
            >= differ_by
        )
    return found


def relations(
    layout: fins.Layout,
    numbers: np.ndarray,
    fields_: dict[str, fins.Field],
    cross_deg: float = CROSS_DEG,
    root_free: float = 0.0,
) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    """Which pairs of fins conflict and which may meet: two runs that **cross** at ``cross_deg``
    or steeper are a junction; ones that cross shallower, or come within a section and the sand
    round it without crossing (:func:`.oracle.pairs`), are a conflict."""
    runs = []
    for name, (ia, ib), number in zip(layout.where, layout.ends, numbers, strict=True):
        f = fields_[name]
        pts, _ = fins.run(number, f.rails[ia], f.rails[ib])
        runs.append(pts)
    crowded = oracle.pairs(layout, numbers, fields_, root_free=root_free)
    conflicts: set[tuple[int, int]] = set()
    junctions: set[tuple[int, int]] = set()
    for i, here in enumerate(runs):
        for j in range(i + 1, len(runs)):
            if layout.where[i] != layout.where[j]:
                continue
            there = runs[j]
            met = shapely.LineString(here).intersection(shapely.LineString(there))
            if met.is_empty:
                if (i, j) in crowded:
                    conflicts.add((i, j))
                continue
            point = met.geoms[0] if hasattr(met, "geoms") else met
            if point.geom_type != "Point":
                conflicts.add((i, j))
                continue
            at = np.array([point.x, point.y])
            ta = _tangent(here, at)
            tb = _tangent(there, at)
            angle = np.degrees(np.arccos(np.clip(abs(float(ta @ tb)), 0.0, 1.0)))
            (junctions if angle >= cross_deg else conflicts).add((i, j))
    return conflicts, junctions


def _tangent(run: np.ndarray, at: np.ndarray) -> np.ndarray:
    """The run's direction where it passes nearest ``at``."""
    k = int(np.argmin(np.linalg.norm(run - at, axis=1)))
    a, b = run[max(k - 1, 0)], run[min(k + 1, len(run) - 1)]
    t = b - a
    return t / max(float(np.linalg.norm(t)), 1e-9)


def _why(table: Table, kept: list[int], budget_L: float, most: int, valence: int) -> dict[str, str]:
    """For every fin left out, the rule that removed it - the first that applies, cheapest
    explanation first."""
    n = len(table.ids)
    inside = set(kept)
    out: dict[str, str] = {}
    metal_kept = float(table.metal_L[kept].sum()) if kept else 0.0
    for i in range(n):
        if i in inside:
            continue
        name = table.ids[i]
        if table.value[i] <= 0.0 and not any(i in them for them in table.needs.values()):
            out[name] = f"worth nothing to the objective ({table.value[i]:+.3f})"
            continue
        crowd = [
            j for a, b in table.conflicts for j in ((b,) if a == i else (a,) if b == i else ())
        ]
        crowd = [j for j in crowd if j in inside]
        if crowd:
            out[name] = "crowds " + ", ".join(table.ids[j] for j in crowd)
            continue
        if i in table.needs:
            have = sum(1 for j in table.needs[i] if j in inside)
            want = min(NEEDS, len(table.needs[i]))
            out[name] = f"needs {want} of its spokes standing, has {have}"
            continue
        if i in table.spine and table.spine[i] not in inside:
            out[name] = f"needs its spine {table.ids[table.spine[i]]}, which was dropped"
            continue
        if i in table.mirror and table.mirror[i] not in inside:
            out[name] = f"its mirror {table.ids[table.mirror[i]]} was dropped"
            continue
        full = (sum(1 for j in them if j in inside) >= valence for them in table.nodes if i in them)
        if any(full):
            out[name] = f"a node it meets already holds {valence} ribs"
            continue
        same = sum(1 for j in kept if table.volume[j] == table.volume[i])
        if same >= most:
            out[name] = f"the volume already holds {most} ribs"
            continue
        if metal_kept + float(table.metal_L[i]) > budget_L + 1e-9:
            out[name] = f"no room in the budget ({metal_kept:.2f} of {budget_L:.2f} L spent)"
            continue
        if table.value[i] <= 0.0:
            out[name] = f"worth nothing to the objective ({table.value[i]:+.3f})"
            continue
        out[name] = "a better set was found without it"
    return out
