"""The deck's groups tied to the CAD, and carried to any other mesh of the part or of a design.

**Anchoring.** Every group a support, coupling or load acts on is a patch of the deck mesh's
surface.
Its triangles - the skin triangles whose corners all belong to the group - are matched to the CAD
face each lies on, by the CAD's own triangulation, so the group becomes a set of CAD faces. Single-
node groups - the reference points couplings are held or loaded through - keep their coordinates.

**Carrying.** A new mesh is labelled face by face: a boundary triangle joins a group when its middle
is nearest one of the group's faces and every corner lies within a tolerance of them - so a triangle
straddling a face's edge, half on the shoulder beside it, is not counted in. The reference points
are added where the deck put them, and the setup is copied unchanged, names and all.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

import numpy as np

from .fem import FEMesh, triangle_areas
from .setup import Setup


@dataclass
class Anchor:
    """A group as CAD faces: which faces, how much of the group lies on them, and how far off."""

    faces: list[int]
    area: float
    face_area: float
    gap: float
    triangles: int


@dataclass
class Anchoring:
    groups: dict[str, Anchor] = field(default_factory=dict)
    references: dict[str, list[float]] = field(default_factory=dict)
    volume_groups: list[str] = field(default_factory=list)
    point_groups: list[str] = field(default_factory=list)
    not_anchored: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "groups": {g: a.__dict__ for g, a in self.groups.items()},
            "references": self.references,
            "volume_groups": self.volume_groups,
            "point_groups": self.point_groups,
            "not_anchored": self.not_anchored,
        }


def _nearest(
    points: np.ndarray, vertices: np.ndarray, triangles: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    import igl

    squared, index, _ = igl.point_mesh_squared_distance(
        np.ascontiguousarray(points, np.float64),
        np.ascontiguousarray(vertices, np.float64),
        np.ascontiguousarray(triangles, np.int64),
    )
    return np.sqrt(squared), index


def acted_on(setup: Setup) -> set[str]:
    """Every group a support, coupling or load of the setup names."""
    names: set[str] = set()
    for h in setup.held:
        names.update(h.groups)
    for r in setup.rigid:
        names.update(r.groups)
    for d in setup.distributing:
        names.update({d.reference, d.group})
    for n in setup.nodal_loads:
        names.add(n.group)
    for s in setup.surface_loads:
        names.add(s.group)
    for o in setup.outputs:
        names.add(o.group)
    return names


def anchor(
    mesh: FEMesh,
    setup: Setup,
    vertices: np.ndarray,
    triangles: np.ndarray,
    face_id: np.ndarray,
    min_share: float = 0.01,
) -> Anchoring:
    """Tie the deck's groups to CAD faces."""
    out = Anchoring()
    skin = mesh.skin
    in_volume = np.zeros(mesh.n_nodes, bool)
    in_volume[np.unique(skin.corners)] = True
    for name, parts in mesh.cell_groups.items():
        if any(k in parts for k in ("TETRA10", "TETRA4")):
            out.volume_groups.append(name)
        elif set(parts) == {"POI1"}:
            out.point_groups.append(name)
    areas = triangle_areas(mesh.nodes, skin.corners)
    face_area = np.bincount(face_id, weights=triangle_areas(vertices, triangles))
    for name in sorted(acted_on(setup)):
        try:
            members = mesh.group_nodes(name)
        except KeyError:
            out.not_anchored.append(name)
            continue
        if len(members) == 1 and not in_volume[members[0]]:
            out.references[name] = mesh.nodes[members[0]].tolist()
            continue
        member = np.zeros(mesh.n_nodes, bool)
        member[members] = True
        patch = np.flatnonzero(member[skin.corners].all(axis=1))
        if not len(patch):
            out.not_anchored.append(name)
            continue
        gap, nearest = _nearest(mesh.nodes[skin.corners[patch]].mean(axis=1), vertices, triangles)
        faces = face_id[nearest]
        weight = np.bincount(faces, weights=areas[patch], minlength=len(face_area))
        chosen = np.flatnonzero(weight >= min_share * weight.sum())
        on = np.isin(faces, chosen)
        out.groups[name] = Anchor(
            faces=[int(f) for f in chosen],
            area=float(areas[patch].sum()),
            face_area=float(face_area[chosen].sum()),
            gap=float(gap[on].max()) if on.any() else float("nan"),
            triangles=int(len(patch)),
        )
    return out


@dataclass
class Carried:
    mesh: FEMesh
    setup: Setup
    groups: dict[str, dict] = field(default_factory=dict)


def carry(
    setup: Setup,
    anchoring: Anchoring,
    target: FEMesh,
    vertices: np.ndarray,
    triangles: np.ndarray,
    face_id: np.ndarray,
    tolerance: float = 2.0,
) -> Carried:
    """Label ``target``'s boundary with the deck's groups, add its reference points, copy its
    setup."""
    skin = target.skin
    corners = target.nodes[skin.corners]
    _, nearest = _nearest(corners.mean(axis=1), vertices, triangles)
    tri_face = face_id[nearest]
    areas = triangle_areas(target.nodes, skin.corners)
    node_groups = dict(target.node_groups)
    report: dict[str, dict] = {}
    six = skin.six if skin.six is not None else skin.corners
    for name, anchor_ in anchoring.groups.items():
        candidates = np.flatnonzero(np.isin(tri_face, anchor_.faces))
        if len(candidates):
            on_faces = np.isin(face_id, anchor_.faces)
            gap, _ = _nearest(corners[candidates].reshape(-1, 3), vertices, triangles[on_faces])
            candidates = candidates[(gap.reshape(-1, 3) < tolerance).all(axis=1)]
        node_groups[name] = np.unique(six[candidates])
        report[name] = {
            "triangles": int(len(candidates)),
            "area": float(areas[candidates].sum()),
            "deck_area": anchor_.area,
        }
    nodes = target.nodes
    cells = dict(target.cells)
    cell_groups = {k: dict(v) for k, v in target.cell_groups.items()}
    if anchoring.references:
        names = list(anchoring.references)
        first = len(nodes)
        nodes = np.vstack([nodes, np.array([anchoring.references[n] for n in names])])
        for i, name in enumerate(names):
            node_groups[name] = np.array([first + i])
        cells["POI1"] = np.arange(first, first + len(names))[:, None]
        for group in anchoring.point_groups:
            cell_groups[group] = {"POI1": np.arange(len(names))}
    volume = [k for k in ("TETRA10", "TETRA4") if k in cells]
    for group in anchoring.volume_groups:
        cell_groups[group] = {volume[0]: np.arange(len(cells[volume[0]]))}
    mesh = FEMesh(
        nodes=nodes, cells=cells, node_groups=node_groups, cell_groups=cell_groups, name=target.name
    )
    carried = copy.deepcopy(setup)
    carried.resolve({g for g, m in node_groups.items() if len(m) == 1})
    return Carried(mesh=mesh, setup=carried, groups=report)
