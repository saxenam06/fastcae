"""A solved design as a training record: a Zarr store of its answer, a JSON record of how it was
made, and a row of the run's Parquet table of metrics.

**The Zarr store** follows the layout agenticCAE curated its 490 designs in - PhysicsNeMo's, so its
datapipes need no adapter - one chunk an array, float32:

- the surface, at every node of the six-node boundary triangles, mid-sides included (the peak
  stress sits on a mid-side node as often as not): ``coords``, ``normals``, ``area``, and the answer
  there - ``vm`` (N, 1), ``disp`` (N, 1, 3), ``stress`` (N, 1, 6: xx yy zz xy xz yz);
- the volume, for a model of the answer anywhere in the part: ``volume_coords``, ``tets`` (TET10),
  ``volume_disp`` (N, 1, 3), ``volume_vm`` (N, 1), and ``surface_index`` into them;
- ``groups/<name>``, the nodes of every group a support, coupling or load acts on;
- attributes: which design, of which run, and the checks the store itself passed.

The second axis is the load case - one today, kept so a later campaign can widen it without a new
schema.

**The JSON record** says how the design was made and solved: its recipe and values, its build's
checks, the mesh and the sizes it was held to, the setup carried to it, the solver and its version,
every stage's time, its signals, and whether it was solved or set aside and why.

**The Parquet table** is one row a design, rebuilt from the records: the metrics a model is judged
on side by side, under the deck's names.
"""

from __future__ import annotations

import json
from importlib import metadata
from pathlib import Path

import numpy as np

from .fem import FEMesh, tet_volumes
from .signals import Answer, Signal

DTYPE = np.float32
LOAD_CASES = ("service",)
SOLVED = "solved"


def versions() -> dict[str, str]:
    """The versions of what solved it."""
    out = {}
    for name in ("nvidia-cudss-cu12", "nvmath-python", "cupy-cuda12x", "numpy", "scipy"):
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    return out


def surface(mesh: FEMesh) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The nodes of the boundary's six-node triangles, each with its outward normal and the share
    of the surface it stands for - each triangle split at its mid-sides into four."""
    six = mesh.skin.six
    if six is None:
        raise ValueError("the mesh has no six-node boundary")
    a, b, c, ab, bc, ca = six.T
    pieces = np.concatenate(
        [np.column_stack(t) for t in ((a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca))]
    )
    p = mesh.nodes[pieces]
    cross = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    normal = np.zeros((mesh.n_nodes, 3))
    area = np.zeros(mesh.n_nodes)
    for k in range(3):
        np.add.at(normal, pieces[:, k], cross)
        np.add.at(area, pieces[:, k], 0.5 * np.linalg.norm(cross, axis=1) / 3.0)
    points = np.unique(six)
    n = normal[points]
    return points, n / np.maximum(np.linalg.norm(n, axis=1), 1e-300)[:, None], area[points]


def mass_kg(mesh: FEMesh, density_t_mm3: float) -> float:
    """The mesh's metal, weighed: its volume at the deck's density (tonnes a cubic millimetre)."""
    tets = mesh.tet10 if mesh.tet10 is not None else mesh.cells["TETRA4"]
    return float(tet_volumes(mesh.nodes, tets).sum() * density_t_mm3 * 1000.0)


def write_store(path: Path, mesh: FEMesh, answer: Answer, groups: list[str], attrs: dict) -> dict:
    """One design's Zarr store; what it holds, and the checks the store itself passed."""
    import zarr

    points, normals, area = surface(mesh)
    volume = np.unique(mesh.tet10) if mesh.tet10 is not None else np.arange(mesh.n_nodes)
    vm = answer.von_mises if answer.von_mises is not None else np.full(mesh.n_nodes, np.nan)
    stress = answer.stress if answer.stress is not None else np.full((mesh.n_nodes, 6), np.nan)
    # Renumbered to the volume's own nodes: reference points carry no metal and are not in it.
    renumber = np.full(mesh.n_nodes, -1, np.int64)
    renumber[volume] = np.arange(len(volume))
    peak_ratio = float(np.nanmax(vm[points]) / np.nanmax(vm[volume]))
    arrays: dict[str, np.ndarray] = {
        "coords": mesh.nodes[points].astype(DTYPE),
        "normals": normals.astype(DTYPE),
        "area": area.astype(DTYPE),
        "vm": vm[points].astype(DTYPE)[:, None],
        "disp": answer.u[points].astype(DTYPE)[:, None, :],
        "stress": stress[points].astype(DTYPE)[:, None, :],
        "volume_coords": mesh.nodes[volume].astype(DTYPE),
        "tets": renumber[mesh.tet10].astype(np.int32)
        if mesh.tet10 is not None
        else np.zeros((0, 10), np.int32),
        "volume_disp": answer.u[volume].astype(DTYPE)[:, None, :],
        "volume_vm": vm[volume].astype(DTYPE)[:, None],
        "surface_index": renumber[points].astype(np.int32),
    }
    qa = {
        "points": int(len(points)),
        "volume_nodes": int(len(volume)),
        "surface_area_mm2": float(area.sum()),
        "peak_ratio": peak_ratio,
        "vm_max_MPa": float(np.nanmax(vm[volume])),
        "finite": bool(all(np.isfinite(v).all() for k, v in arrays.items() if k != "stress")),
        "load_cases": list(LOAD_CASES),
    }
    root = zarr.open_group(str(path), mode="w")
    for name, value in arrays.items():
        root.create_array(name, shape=value.shape, dtype=value.dtype, chunks=value.shape)[...] = (
            value
        )
    held = root.create_group("groups")
    for name in groups:
        members = renumber[mesh.group_nodes(name)]
        members = members[members >= 0].astype(np.int32)
        if len(members):
            held.create_array(name, shape=members.shape, dtype=members.dtype, chunks=members.shape)[
                ...
            ] = members
    root.attrs.update({**attrs, "qa": qa})
    return qa


def write_record(path: Path, record: dict) -> None:
    partial = path.with_suffix(".partial")
    partial.write_text(json.dumps(record, indent=1, default=_plain), encoding="utf-8")
    partial.replace(path)


def _plain(value):  # type: ignore[no-untyped-def]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return str(value)


def signal_columns(signals: list[Signal]) -> dict[str, float]:
    """A design's signals as columns: ``<name>.<component>``, the deck's names kept."""
    return {f"{s.name}.{s.component}": float(s.value) for s in signals}


def rebuild_table(folder: Path) -> Path | None:
    """The run's Parquet table of metrics, one row a design, from every record in ``folder``."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows = []
    for path in sorted(folder.glob("*.json"), key=lambda p: _index(p.stem)):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows.append(
            {
                "run": record.get("run"),
                "index": record.get("index"),
                "outcome": record.get("outcome"),
                "reason": record.get("reason", ""),
                "route": record.get("route", ""),
                "mass_kg": record.get("mass_kg"),
                "unknowns": record.get("mesh", {}).get("unknowns"),
                "tets": record.get("mesh", {}).get("tets"),
                "seconds": record.get("seconds"),
                **{f"seconds.{k}": v for k, v in (record.get("stages") or {}).items()},
                **(record.get("metrics") or {}),
                "values": json.dumps(record.get("values") or {}, sort_keys=True),
            }
        )
    if not rows:
        return None
    columns = sorted({k for r in rows for k in r})
    table = pa.table({k: [r.get(k) for r in rows] for k in columns})
    out = folder / "metrics.parquet"
    pq.write_table(table, out.with_suffix(".partial"))
    out.with_suffix(".partial").replace(out)
    return out


def _index(stem: str) -> int:
    try:
        return int(stem)
    except ValueError:
        return 1 << 30
