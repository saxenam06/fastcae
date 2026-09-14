"""A finite-element mesh as a solver deck carries it: nodes, cells by type, and named groups.

Cells are kept by type because that is how every deck format stores them and how every solver
reads them; node numbers are 0-based rows of ``nodes``, and each type's nodes are in one order
throughout - Code_Aster's ASTER-format order, which is also VTK's for the types used here. A
reader of another format permutes into it once, on the way in.

Quadratic tetrahedra (TET10) are numbered corners first, then the middles of edges (0,1) (1,2)
(2,0) (0,3) (1,3) (2,3); six-node triangles corners first, then (0,1) (1,2) (2,0).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

import numpy as np

# A tetrahedron's six edges, in TET10's order of mid-side nodes.
EDGES = np.array([[0, 1], [1, 2], [2, 0], [0, 3], [1, 3], [2, 3]])
# Its four faces, each wound to face outward when the tetrahedron is positively oriented, and the
# same faces as six-node triangles in TET10's own numbering.
FACES = np.array([[0, 2, 1], [0, 1, 3], [1, 2, 3], [0, 3, 2]])
FACES6 = np.array([[0, 2, 1, 6, 5, 4], [0, 1, 3, 4, 8, 7], [1, 2, 3, 5, 9, 8], [0, 3, 2, 7, 9, 6]])

# How many nodes each cell type has.
NODES_PER_CELL = {
    "POI1": 1,
    "SEG2": 2,
    "SEG3": 3,
    "TRIA3": 3,
    "TRIA6": 6,
    "QUAD4": 4,
    "QUAD8": 8,
    "TETRA4": 4,
    "TETRA10": 10,
    "PENTA6": 6,
    "PENTA15": 15,
    "PYRAM5": 5,
    "HEXA8": 8,
    "HEXA20": 20,
}
VOLUME_TYPES = ("TETRA4", "TETRA10", "PENTA6", "PENTA15", "PYRAM5", "HEXA8", "HEXA20")


@dataclass
class Skin:
    """The outside of a mesh's volume: its boundary triangles, wound outward.

    ``corners`` are the triangles' three corner nodes; ``six`` the six-node triangles when the
    cells are quadratic, else None; ``cell`` which volume cell each came from.
    """

    corners: np.ndarray
    six: np.ndarray | None
    cell: np.ndarray


@dataclass
class FEMesh:
    """Nodes, cells by type, and the groups a deck names."""

    nodes: np.ndarray
    cells: dict[str, np.ndarray]
    node_groups: dict[str, np.ndarray] = field(default_factory=dict)
    cell_groups: dict[str, dict[str, np.ndarray]] = field(default_factory=dict)
    name: str = "mesh"

    @property
    def n_nodes(self) -> int:
        return len(self.nodes)

    def count(self, kind: str) -> int:
        cells = self.cells.get(kind)
        return 0 if cells is None else len(cells)

    def group_nodes(self, name: str) -> np.ndarray:
        """Every node a group holds, whichever way the deck defined it: listed as nodes, or as the
        nodes of its cells."""
        if name in self.node_groups:
            return self.node_groups[name]
        if name in self.cell_groups:
            parts = [
                self.cells[kind][rows].ravel() for kind, rows in self.cell_groups[name].items()
            ]
            return np.unique(np.concatenate(parts)) if parts else np.empty(0, np.int64)
        raise KeyError(name)

    def groups(self) -> list[str]:
        """Every group name, node groups and cell groups alike, in the order they were read."""
        return list(dict.fromkeys([*self.node_groups, *self.cell_groups]))

    @cached_property
    def tet10(self) -> np.ndarray | None:
        """The quadratic tetrahedra, when the volume is made of them alone."""
        volume = [kind for kind in VOLUME_TYPES if self.count(kind)]
        return self.cells["TETRA10"] if volume == ["TETRA10"] else None

    @cached_property
    def skin(self) -> Skin:
        """The boundary of the volume cells, from tetrahedra (quadratic or linear)."""
        if self.count("TETRA10"):
            tets = self.cells["TETRA10"]
            faces6 = tets[:, FACES6].reshape(-1, 6)
            key = np.sort(faces6[:, :3], axis=1)
            _, first, counts = np.unique(key, axis=0, return_index=True, return_counts=True)
            keep = first[counts == 1]
            return Skin(corners=faces6[keep, :3], six=faces6[keep], cell=keep // 4)
        if self.count("TETRA4"):
            tets = self.cells["TETRA4"]
            faces = tets[:, FACES].reshape(-1, 3)
            key = np.sort(faces, axis=1)
            _, first, counts = np.unique(key, axis=0, return_index=True, return_counts=True)
            keep = first[counts == 1]
            return Skin(corners=faces[keep], six=None, cell=keep // 4)
        raise ValueError("the mesh has no tetrahedra")


def save(mesh: FEMesh, path) -> None:  # type: ignore[no-untyped-def]
    """A mesh with its groups, in one ``.npz``."""
    arrays: dict[str, np.ndarray] = {"nodes": mesh.nodes, "name": np.array(mesh.name)}
    for kind, cells in mesh.cells.items():
        arrays[f"cells/{kind}"] = cells
    for name, members in mesh.node_groups.items():
        arrays[f"nodes@{name}"] = members
    for name, parts in mesh.cell_groups.items():
        for kind, rows in parts.items():
            arrays[f"cellgroup@{name}@{kind}"] = rows
    partial = str(path) + ".partial.npz"
    np.savez_compressed(partial, **arrays)
    import os

    os.replace(partial, path)


def load(path) -> FEMesh:  # type: ignore[no-untyped-def]
    data = np.load(path)
    cells, node_groups, cell_groups = {}, {}, {}
    for key in data.files:
        if key.startswith("cells/"):
            cells[key[6:]] = data[key]
        elif key.startswith("nodes@"):
            node_groups[key[6:]] = data[key]
        elif key.startswith("cellgroup@"):
            _, name, kind = key.split("@")
            cell_groups.setdefault(name, {})[kind] = data[key]
    return FEMesh(
        nodes=data["nodes"],
        cells=cells,
        node_groups=node_groups,
        cell_groups=cell_groups,
        name=str(data["name"]),
    )


def quadratic(nodes: np.ndarray, tets: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """TET10 from TET4: a node at the middle of every edge, shared by the tets round it - straight
    edges."""
    edges = np.sort(tets[:, EDGES].reshape(-1, 2), axis=1)
    unique, inverse = np.unique(edges, axis=0, return_inverse=True)
    middle = 0.5 * (nodes[unique[:, 0]] + nodes[unique[:, 1]])
    return np.vstack([nodes, middle]), np.hstack([tets, len(nodes) + inverse.reshape(-1, 6)])


def oriented(nodes: np.ndarray, tets: np.ndarray) -> np.ndarray:
    """Linear tetrahedra with every one positively oriented."""
    tets = np.array(tets, dtype=np.int64)
    p = nodes[tets]
    volume = np.einsum(
        "ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0])
    )
    tets[volume < 0] = tets[volume < 0][:, [0, 2, 1, 3]]
    return tets


def tet_volumes(nodes: np.ndarray, tets: np.ndarray) -> np.ndarray:
    """Each tetrahedron's volume, from its corners."""
    p = nodes[tets[:, :4]]
    return (
        np.abs(
            np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))
        )
        / 6.0
    )


def quality(nodes: np.ndarray, tets: np.ndarray) -> np.ndarray:
    """Mean-ratio quality of each tetrahedron's corners: 1 for a regular one, 0 for a flat one."""
    p = nodes[tets[:, :4]]
    v = tet_volumes(nodes, tets)
    l2 = sum(np.sum((p[:, a] - p[:, b]) ** 2, axis=1) for a, b in EDGES)
    return 12.0 * (3.0 * v) ** (2.0 / 3.0) / l2


def triangle_areas(nodes: np.ndarray, tris: np.ndarray) -> np.ndarray:
    p = nodes[tris[:, :3]]
    return 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
