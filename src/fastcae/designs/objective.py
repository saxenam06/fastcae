"""What a design is judged on: **J** - the gear mesh's misalignment, the housing's largest
displacement and its stress, each against a reference - and **J robust**, the same with the
misalignment taken over a band of loads rather than the one case.

**Gear mesh misalignment** is the relative skew of two meshing shafts, not the tilt of any one
bore: two shafts that lean together mesh well, two that lean apart do not. Each shaft is taken as
rigid between its two bearing seats, its axis set by how differently its two seats move; the lead
is the part of the relative skew about the line of centres - it opens the mesh across the face -
and in micrometres it is that skew times the face width. Which shafts mesh, their line of centres
and face width are the gearbox's own data, kept with the project in ``objective/gearmesh.json``;
only a mesh with a face width is ranked on.

**Robust**: the deck's load is the sum of its parts (each non-zero component of each bearing load),
so each part is solved alone and the misalignment under the deck's load scaled part by part by
``1 + e``, ``e ~ N(0, 5 %²)``, is a re-weighted sum; the robust figure is the median of its size
over 4,000 seeded draws. A design that meets the one case by cancelling luckily scores badly here.

``J = |lead| / 10 µm + largest displacement / the target's + p99.9 von Mises / 250 MPa``. Lower is
better. The target's own J uses its own largest displacement, so its deflection term is 1.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from ..project import Project

GEARMESH = Path("objective") / "gearmesh.json"
UM_REF = 10.0
"""The misalignment that counts as one unit of J, µm."""
STRESS_LIMIT_MPA = 250.0
BAND = 0.05
DRAWS = 4000
SEED = 7


def config(project: Project) -> dict[str, Any] | None:
    """The gearbox's shafts and meshes, when the project holds them."""
    path = project.root / GEARMESH
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _skew(cfg: dict[str, Any], motions: dict[str, np.ndarray], shaft: str) -> np.ndarray | None:
    a, b = cfg["shafts"][shaft]["bores"]
    z1, z2 = cfg["shafts"][shaft]["z_mm"]
    if a not in motions or b not in motions:
        return None
    return (motions[b][:2] - motions[a][:2]) / (z2 - z1)


def leads(cfg: dict[str, Any], motions: dict[str, np.ndarray]) -> dict[str, float]:
    """Each mesh's lead - relative skew about its line of centres - in radians, from each bore's
    motion (x, y, z) keyed by the bore's name."""
    out = {}
    for name, m in cfg["meshes"].items():
        p0, p1 = (np.asarray(x, float) for x in m["axes_xy"])
        n = (p1 - p0) / np.linalg.norm(p1 - p0)
        t = np.array([-n[1], n[0]])
        sa, sc = (_skew(cfg, motions, s) for s in m["shafts"])
        if sa is None or sc is None:
            continue
        out[name] = float((sa - sc) @ t)
    return out


def _bores_of(said: dict[str, Any]) -> dict[str, np.ndarray]:
    """Each bore's motion under the deck, from a solve's signals."""
    got: dict[str, dict[str, float]] = {}
    for r in said.get("signals", []):
        if r.get("component") in ("DX", "DY", "DZ") and r.get("design") is not None:
            got.setdefault(r["name"], {})[r["component"]] = float(r["design"])
    return {
        k: np.array([v.get("DX", 0.0), v.get("DY", 0.0), v.get("DZ", 0.0)]) for k, v in got.items()
    }


def _signal(said: dict[str, Any], name: str, component: str) -> float | None:
    for r in said.get("signals", []):
        if (r.get("name"), r.get("component")) == (name, component) and r.get("design") is not None:
            return float(r["design"])
    return None


def robust_um(parts_um: np.ndarray) -> float:
    """The median size of the re-weighted sum of the parts' misalignment over the load band."""
    rng = np.random.default_rng(SEED)
    e = rng.normal(0.0, BAND, size=(DRAWS, len(parts_um)))
    return float(np.median(np.abs((1.0 + e) @ parts_um)))


def score(
    project: Project, said: dict[str, Any], target: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """J and J robust of a solve's summary - its signals and, for the robust figure, its parts -
    against ``target``'s largest displacement (its own, when no target is given)."""
    cfg = config(project)
    if cfg is None:
        return None
    ref = {k.removeprefix("REF_"): v for k, v in _bores_of(said).items()}
    nominal = leads(cfg, {k: v for k, v in ref.items()})
    parts: dict[str, list[float]] = {}
    for part in said.get("components") or []:
        motions = {k.removeprefix("REF_"): np.asarray(v, float) for k, v in part["refs"].items()}
        for mesh, lead in leads(cfg, motions).items():
            parts.setdefault(mesh, []).append(lead)
    meshes = {}
    for name, m in cfg["meshes"].items():
        if name not in nominal:
            continue
        fw = m.get("face_width_mm")
        row: dict[str, Any] = {"lead_mrad": nominal[name] * 1e3, "face_width_mm": fw}
        if fw:
            row["nominal_um"] = abs(nominal[name]) * fw * 1e3
            if name in parts:
                p_um = np.asarray(parts[name]) * fw * 1e3
                row["robust_um"] = robust_um(p_um)
                row["parts_norm_um"] = float(np.linalg.norm(p_um))
                row["parts_sum_um"] = float(p_um.sum())
        meshes[name] = row
    ranked = [n for n, r in meshes.items() if r.get("face_width_mm")]
    largest = _signal(said, "displacement", "largest")
    stress = _signal(said, "von Mises", "p99.9")
    goal = _signal(target, "displacement", "largest") if target else largest
    defl = largest / goal if largest is not None and goal else None
    stress_term = stress / STRESS_LIMIT_MPA if stress is not None else None
    out: dict[str, Any] = {"meshes": meshes, "ranked": ranked, "terms": {}}
    for mode, key in (("nominal", "nominal_um"), ("robust", "robust_um")):
        values = [meshes[n][key] for n in ranked if key in meshes[n]]
        if not values or defl is None or stress_term is None:
            continue
        mis = max(values) / UM_REF
        out[f"j_{mode}"] = mis + defl + stress_term
        out["terms"][mode] = {"misalign": mis, "deflection": defl, "stress": stress_term}
    return out
