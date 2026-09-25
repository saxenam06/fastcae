"""The load mixes a deck offers (:func:`mixes`): its own case; each line of shafting the part
carries, alone; and every line as a case of its own, carried together - what a design is loaded
with on the voxel model."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class LoadCase:
    """Loads on some of the deck's loaded groups, as the deck gives them."""

    name: str
    forces: dict[str, list[float]]
    """Per loaded surface group: the force (N) the deck puts through it."""
    weight: float = 1.0


@dataclass
class Mix:
    """What a design is optimised for: one or more load cases carried together."""

    name: str
    cases: list[LoadCase]
    words: str = ""


def _lines(extraction, groups: list[str]) -> list[list[str]]:  # type: ignore[no-untyped-def]
    """The loaded groups on one axis together: each line of shafting the part carries."""
    faces = extraction.features.faces if extraction.features is not None else {}
    anchored = (extraction.anchoring or {}).get("groups", {})
    axes: dict[str, tuple[np.ndarray, np.ndarray] | None] = {}
    for g in groups:
        found = None
        for f in anchored.get(g, {}).get("faces", []):
            face = faces.get(int(f))
            if face is None or face.surface_type != "cylinder" or face.axis is None:
                continue
            if getattr(face, "axis_point", None) is None:
                continue
            found = (np.asarray(face.axis, float), np.asarray(face.axis_point, float))
            break
        axes[g] = found
    lines: list[list[str]] = []
    for g in groups:
        here = axes[g]
        for line in lines:
            there = axes[line[0]]
            if here is None or there is None:
                continue
            a, p = there
            b, q = here
            if abs(float(a @ b)) < 0.999:
                continue
            off = (q - p) - ((q - p) @ a) * a
            if float(np.linalg.norm(off)) < 2.0:
                line.append(g)
                break
        else:
            lines.append([g])
    return lines


def mixes(extraction, setup) -> list[Mix]:  # type: ignore[no-untyped-def]
    """The load mixes the deck offers: its own case; each line of shafting alone; and every line as
    a case of its own, carried together."""
    loads = {n.group: n.values for n in setup.nodal_loads}
    forces: dict[str, list[float]] = {}
    for d in setup.distributing:
        if d.reference in loads:
            forces[d.group] = [float(loads[d.reference].get(c, 0.0)) for c in ("FX", "FY", "FZ")]
    for r in setup.rigid:
        if r.reference in loads:
            for g in r.groups:
                if g != r.reference:
                    forces[g] = [float(loads[r.reference].get(c, 0.0)) for c in ("FX", "FY", "FZ")]
    for s in setup.surface_loads:
        if s.group not in forces and all(c in s.values for c in ("FX", "FY", "FZ")):
            forces[s.group] = [float(s.values[c]) for c in ("FX", "FY", "FZ")]
    if not forces:
        return []
    out = [Mix("deck", [LoadCase("deck", forces)], "the deck's own load case")]
    lines = _lines(extraction, sorted(forces))
    if len(lines) > 1:
        size = {tuple(line): sum(np.linalg.norm(forces[g]) for g in line) for line in lines}
        lines.sort(key=lambda line: -size[tuple(line)])
        cases = [
            LoadCase(f"line {i + 1}", {g: forces[g] for g in line}) for i, line in enumerate(lines)
        ]
        for i, case in enumerate(cases):
            out.append(
                Mix(
                    f"line {i + 1}",
                    [case],
                    f"the loads on one line of shafting alone: {', '.join(case.forces)}",
                )
            )
        out.append(
            Mix("lines", cases, f"each of the {len(cases)} lines of shafting as its own case")
        )
    return out
