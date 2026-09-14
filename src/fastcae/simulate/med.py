"""MED: the HDF5 files Code_Aster reads its mesh from and writes its results to.

Read with h5py alone. What a MED file holds, as far as a deck needs it:

- ``/ENS_MAA/<mesh>/<step>/NOE/COO`` - node coordinates, all x then all y then all z; ``NOE/FAM``
  each node's family.
- ``/ENS_MAA/<mesh>/<step>/MAI/<type>/NOD`` - each cell type's connectivity, 1-based, all first
  nodes then all second nodes and so on; ``FAM`` each cell's family.
- ``/FAS/<mesh>/{NOEUD,ELEME}/<family>/GRO/NOM`` - the groups a family belongs to. A node or cell
  is in a group when its family is. Families of nodes are numbered from 1, of cells from -1.
- ``/CHA/<result><field>/<step>/NOE/<profile>/CO`` - a nodal field's values, all of the first
  component then all of the second; ``/PROFILS/<profile>/PFL`` which nodes a profile covers.

MED numbers the nodes of a volume cell the other way round from Code_Aster's own format: a
tetrahedron's second and third corners are swapped, and its mid-side nodes with them. Cells are
permuted into :mod:`fem`'s order as they are read.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .fem import NODES_PER_CELL, FEMesh

# MED's three-letter cell types and the names every deck uses.
MED_TYPES = {
    "PO1": "POI1",
    "SE2": "SEG2",
    "SE3": "SEG3",
    "TR3": "TRIA3",
    "TR6": "TRIA6",
    "QU4": "QUAD4",
    "QU8": "QUAD8",
    "TE4": "TETRA4",
    "T10": "TETRA10",
    "PE6": "PENTA6",
    "P15": "PENTA15",
    "PY5": "PYRAM5",
    "HE8": "HEXA8",
    "H20": "HEXA20",
}
# MED order to Code_Aster's, per type: aster = med[:, permutation]. Each is its own inverse.
# Checked against Code_Aster's own conversion of a mesh it was given in its own format. Other
# volume types are read as MED stores them; nothing here solves them.
PERMUTATION = {
    "TETRA4": [0, 2, 1, 3],
    "TETRA10": [0, 2, 1, 3, 6, 5, 4, 7, 9, 8],
}


@dataclass
class NodalField:
    """One field's values at nodes: its components' names, which nodes, and the values there."""

    name: str
    components: list[str]
    nodes: np.ndarray
    values: np.ndarray
    units: list[str]

    def component(self, name: str, n_nodes: int, missing: float = np.nan) -> np.ndarray:
        """One component at every node of the mesh; ``missing`` where the field has none."""
        out = np.full(n_nodes, missing)
        out[self.nodes] = self.values[:, self.components.index(name)]
        return out


def _text(raw: np.ndarray | bytes) -> str:
    if isinstance(raw, bytes | np.bytes_):
        return bytes(raw).decode("latin-1").strip()
    return bytes(np.asarray(raw).astype(np.uint8)).decode("latin-1").strip()


def _names(dataset) -> list[str]:  # type: ignore[no-untyped-def]
    """Group names: fixed-width rows of characters, blank-padded."""
    return [_text(row) for row in dataset[()]]


def _split(packed: str, width: int, count: int) -> list[str]:
    return [packed[i * width : (i + 1) * width].strip() for i in range(count)]


def read_mesh(path: Path, name: str | None = None) -> FEMesh:
    """The mesh in a MED file - the first one, unless ``name`` picks another."""
    import h5py

    with h5py.File(path, "r") as f:
        meshes = list(f["ENS_MAA"].keys())
        if not meshes:
            raise ValueError(f"{path.name} holds no mesh")
        chosen = name if name in meshes else meshes[0]
        steps = f["ENS_MAA"][chosen]
        step = steps[sorted(steps.keys())[0]]
        coo = step["NOE/COO"][()]
        dim = int(steps.attrs.get("ESP", steps.attrs.get("DIM", 3)))
        n = len(coo) // dim
        nodes = np.zeros((n, 3))
        nodes[:, :dim] = coo.reshape(dim, n).T
        node_family = step["NOE/FAM"][()] if "FAM" in step["NOE"] else np.zeros(n, np.int64)

        cells: dict[str, np.ndarray] = {}
        cell_family: dict[str, np.ndarray] = {}
        if "MAI" in step:
            for code, group in step["MAI"].items():
                kind = MED_TYPES.get(code)
                if kind is None:
                    continue
                k = NODES_PER_CELL[kind]
                raw = group["NOD"][()]
                conn = raw.reshape(k, len(raw) // k).T.astype(np.int64) - 1
                if kind in PERMUTATION:
                    conn = conn[:, PERMUTATION[kind]]
                cells[kind] = conn
                cell_family[kind] = (
                    group["FAM"][()] if "FAM" in group else np.zeros(len(conn), np.int64)
                )

        node_groups: dict[str, list[int]] = {}
        cell_groups: dict[str, dict[str, np.ndarray]] = {}
        families = f.get(f"FAS/{chosen}")
        node_fams: dict[int, list[str]] = {}
        cell_fams: dict[int, list[str]] = {}
        if families is not None:
            for kind_name, target in (("NOEUD", node_fams), ("ELEME", cell_fams)):
                if kind_name not in families:
                    continue
                for family in families[kind_name].values():
                    if "GRO" in family:
                        target[int(family.attrs["NUM"])] = _names(family["GRO/NOM"])
        for number, groups in node_fams.items():
            members = np.flatnonzero(node_family == number)
            for g in groups:
                node_groups.setdefault(g, []).extend(members.tolist())
        for kind, fam in cell_family.items():
            for number, groups in cell_fams.items():
                rows = np.flatnonzero(fam == number)
                if not len(rows):
                    continue
                for g in groups:
                    have = cell_groups.setdefault(g, {})
                    have[kind] = np.concatenate([have[kind], rows]) if kind in have else rows
    return FEMesh(
        nodes=nodes,
        cells=cells,
        node_groups={g: np.unique(np.asarray(v, np.int64)) for g, v in node_groups.items()},
        cell_groups={
            g: {k: np.sort(v) for k, v in parts.items()} for g, parts in cell_groups.items()
        },
        name=chosen,
    )


def field_name(stored: str) -> str:
    """A field's own name from the name it is stored under: Code_Aster prefixes each with its
    result's name, padded to eight characters with underscores."""
    return stored[8:] if len(stored) > 8 else stored


def read_fields(path: Path, names: list[str] | None = None) -> dict[str, NodalField]:
    """The nodal fields in a MED results file, at their last step, by field name (DEPL, SIEQ_NOEU
    ...). Fields on elements or Gauss points are left out."""
    import h5py

    out: dict[str, NodalField] = {}
    with h5py.File(path, "r") as f:
        if "CHA" not in f:
            return out
        profiles = f.get("PROFILS")
        n_nodes = None
        if "ENS_MAA" in f:
            mesh = f["ENS_MAA"][list(f["ENS_MAA"].keys())[0]]
            step = mesh[sorted(mesh.keys())[0]]
            dim = int(mesh.attrs.get("ESP", mesh.attrs.get("DIM", 3)))
            n_nodes = len(step["NOE/COO"]) // dim
        for stored, group in f["CHA"].items():
            short = field_name(stored)
            if names is not None and short not in names:
                continue
            count = int(group.attrs["NCO"])
            components = _split(_text(group.attrs["NOM"]), 16, count)
            units = _split(_text(group.attrs.get("UNI", b"")), 16, count)
            steps = sorted(group.keys())
            if not steps:
                continue
            last = group[steps[-1]]
            if "NOE" not in last:
                continue
            entity = last["NOE"]
            profile = _text(entity.attrs.get("PFL", b""))
            data = entity[profile] if profile in entity else next(iter(entity.values()))
            values = data["CO"][()]
            if (
                profile
                and profile != "MED_NO_PROFILE_INTERNAL"
                and profiles is not None
                and profile in profiles
            ):
                nodes = profiles[profile]["PFL"][()].astype(np.int64) - 1
            else:
                nodes = np.arange(len(values) // count if n_nodes is None else n_nodes)
            k = len(values) // count
            out[short] = NodalField(
                name=short,
                components=components,
                nodes=nodes[:k],
                values=values.reshape(count, k).T,
                units=units,
            )
    return out
