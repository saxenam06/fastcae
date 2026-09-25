"""A rib network's stages as a design records them - so every stage's result can be seen.

A network is made in stages, each with a result of its own: the **seed** laid down, the **pass**
that moves every fin, the **oracle** that judges each, the **chooser** that keeps a network, the
**polish** with the topology fixed, then the ribs built, the CAD, the mesh and the solve. A design
made this way keeps, beside its record, the fins' runs at each step in the part's frame
(:func:`save_runs`), and its record's ledger says what happened to every fin. From those two the
product draws each stage on the part and says why each fin went as far as it did.

Nothing here knows what a part is for: a fin is named by its volume and its index, a state by
what happened to it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from . import fins

STAGES: list[tuple[str, str]] = [
    ("seed", "Seed"),
    ("pass", "Pass"),
    ("oracle", "Oracle"),
    ("chooser", "Chooser"),
    ("polish", "Polish"),
    ("ribs", "Path"),
    ("cad", "CAD"),
    ("mesh", "Mesh"),
    ("solve", "Solve"),
]
"""A network design's stages, in order: an id and the word a screen shows for it."""

RUNS = "fins.npz"
"""Where a design keeps its fins' runs at each step, beside its record."""

STEP_OF = {
    "seed": "seed",
    "pass": "pass",
    "oracle": "pass",
    "chooser": "pass",
    "polish": "polished",
}
"""Which stored step each stage draws: the oracle and the chooser judge the fins where the pass
left them."""


def ribbons(
    fields_: dict[str, fins.Field], layout: fins.Layout, numbers: np.ndarray, stations: int = 24
) -> tuple[np.ndarray, np.ndarray]:
    """Every fin's run in the part's frame: its base along the floor it stands on and its top
    ``h(s)`` above, each (fins, stations + 1, 3)."""
    base_all, top_all = [], []
    for name, (ia, ib), number in zip(layout.where, layout.ends, numbers, strict=True):
        f = fields_[name]
        pts, _ = fins.run(number, f.rails[ia], f.rails[ib], pieces=stations)
        s = np.linspace(0.0, 1.0, len(pts))
        tall = fins._bernstein2(s) @ np.asarray(number[6:9], float)
        axis = np.asarray(f.plane.normal, float)
        floor = f.floor.under(pts)
        base = f.plane.to3d(pts) + np.outer(floor, axis)
        base_all.append(base)
        top_all.append(base + np.outer(tall, axis))
    if not base_all:
        return np.zeros((0, stations + 1, 3)), np.zeros((0, stations + 1, 3))
    return np.stack(base_all), np.stack(top_all)


def save_runs(
    folder: Path,
    runs: dict[str, tuple[fins.Layout, np.ndarray, list[str]]],
    fields_: dict[str, fins.Field],
) -> Path:
    """The fins' runs at each step - ``{step: (layout, numbers, ids)}`` - written beside the
    design as :data:`RUNS`."""
    arrays: dict[str, np.ndarray] = {}
    for step, (layout, numbers, ids) in runs.items():
        base, top = ribbons(fields_, layout, numbers)
        arrays[f"base_{step}"] = base.astype(np.float32)
        arrays[f"top_{step}"] = top.astype(np.float32)
        arrays[f"ids_{step}"] = np.asarray(ids, dtype=str)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / RUNS
    np.savez_compressed(path, **arrays)
    return path


def load_runs(folder: Path) -> dict[str, dict[str, Any]]:
    """The runs a design keeps, by step: ``{step: {"base", "top", "ids"}}``."""
    path = folder / RUNS
    if not path.is_file():
        return {}
    out: dict[str, dict[str, Any]] = {}
    with np.load(path) as data:
        for key in data.files:
            kind, _, step = key.partition("_")
            out.setdefault(step, {})[kind] = data[key]
    return {
        step: {"base": v["base"], "top": v["top"], "ids": [str(i) for i in v["ids"]]}
        for step, v in out.items()
        if {"base", "top", "ids"} <= set(v)
    }


def _verdict(fin: dict[str, Any], stage: str) -> dict[str, Any] | None:
    for v in fin.get("verdicts", []):
        if v.get("stage") == stage:
            return v
    return None


def fin_states(record: dict[str, Any], stage: str) -> list[dict[str, Any]]:
    """Every fin's state at ``stage``, read off the record's ledger: its id, kind, value, metal,
    a state word and the reason when it was refused or dropped. At the polish only the kept fins
    are there, as only they were polished."""
    out: list[dict[str, Any]] = []
    for fin in record.get("fins", []):
        head = {
            "id": fin.get("id"),
            "kind": fin.get("kind"),
            "value": fin.get("value"),
            "metal_L": fin.get("metal_L"),
        }
        chooser = fin.get("chooser") or ""
        numbers = _verdict(fin, "numbers")
        if stage == "seed":
            out.append({**head, "state": "seeded", "reason": ""})
        elif stage == "pass":
            out.append({**head, "state": "moved", "reason": ""})
        elif stage == "oracle":
            if numbers is None or numbers.get("ok"):
                out.append({**head, "state": "passed", "reason": ""})
            else:
                out.append({**head, "state": "refused", "reason": numbers.get("reason", "")})
        elif stage == "chooser":
            if chooser.startswith("kept"):
                # "kept", or "kept: measured …" - dropped on its value, then measured back in
                out.append({**head, "state": "kept", "reason": chooser.partition(": ")[2]})
            elif chooser.startswith("refused by the oracle"):
                out.append({**head, "state": "refused", "reason": chooser.partition(": ")[2]})
            else:
                out.append({**head, "state": "dropped", "reason": chooser})
        elif stage == "polish":
            if not chooser.startswith("kept"):
                continue
            later = [
                v
                for v in fin.get("verdicts", [])
                if str(v.get("stage", "")).startswith(("numbers after polish", "sheet", "solid"))
            ]
            if not later:
                # kept, but not yet polished and judged: nothing is built until it is
                out.append({**head, "state": "kept", "reason": ""})
                continue
            # a fin is tried as polished and then as it was seeded; it is built if either shape
            # has its sheet and no solid refused
            built = None
            for shape in ("", ", as seeded"):
                sheet = next((v for v in later if v.get("stage") == "sheet" + shape), None)
                solid = next((v for v in later if v.get("stage") == "solid" + shape), None)
                if sheet is not None and sheet.get("ok") and (solid is None or solid.get("ok")):
                    built = shape
                    break
            numbers_ok = all(v.get("ok") for v in later if v.get("stage") == "numbers after polish")
            if built is not None and numbers_ok:
                out.append(
                    {**head, "state": "built", "reason": "built as it was seeded" if built else ""}
                )
            else:
                bad = [v for v in later if not v.get("ok")]
                why = bad[-1].get("reason", "") if bad else ""
                out.append({**head, "state": "refused", "reason": why})
    return out


def counts(record: dict[str, Any]) -> dict[str, int]:
    """How many fins went how far: seeded, passed the oracle, chosen, built."""
    return {
        "seeded": len(record.get("fins", [])),
        "passed": sum(1 for f in fin_states(record, "oracle") if f["state"] == "passed"),
        "chosen": sum(1 for f in fin_states(record, "chooser") if f["state"] == "kept"),
        "built": sum(1 for f in fin_states(record, "polish") if f["state"] == "built"),
    }


def stage_details(record: dict[str, Any]) -> dict[str, str]:
    """A few words for each of the network's own stages, from the ledger and the run's history."""
    c = counts(record)
    refused = [f for f in fin_states(record, "oracle") if f["state"] == "refused"]
    reasons: dict[str, int] = {}
    for f in refused:
        key = f["reason"].split(":")[0].split(" for ")[0][:32]
        reasons[key] = reasons.get(key, 0) + 1
    worst = ", ".join(f"{n} {k}" for k, n in sorted(reasons.items(), key=lambda kv: -kv[1])[:3])
    net = record.get("network") or {}
    return {
        "seed": f"{c['seeded']} fins seeded",
        "pass": "every fin moved by the loads",
        "oracle": f"{c['passed']} of {c['seeded']} pass" + (f"; {worst}" if worst else ""),
        "chooser": f"{c['chosen']} kept"
        + (
            f", {float(net['metal_L']):.2f} L"
            if isinstance(net.get("metal_L"), (int, float))
            else ""
        ),
        "polish": f"{c['built']} of {c['chosen']} build",
    }
