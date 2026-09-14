"""agenticCAE's metrics from a displacement on the TET10 mesh - computed the same way whichever
solver produced it, so the solvers differ only in their answer, not in how it is read.

Stress is taken at each element's centroid, weighted by the element's volume. On a straight-edged
TET10 the corner shape functions have no gradient at the centroid and each mid-side one has the sum
of its two corners' barycentric gradients, so the strain there is exact and cheap.
"""

from __future__ import annotations

import numpy as np
from common import SEATS, metrics, stress_from_strain, von_mises


def barycentric_gradients(nodes: np.ndarray, tets: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """∇L0..∇L3 for every tet (n, 4, 3), and its volume."""
    x = nodes[tets[:, :4]]
    t = np.stack([x[:, 1] - x[:, 0], x[:, 2] - x[:, 0], x[:, 3] - x[:, 0]], axis=2)  # columns
    inv = np.linalg.inv(t)  # rows are ∇L1, ∇L2, ∇L3
    g = np.empty((len(tets), 4, 3))
    g[:, 1:] = inv
    g[:, 0] = -inv.sum(axis=1)
    volume = np.abs(np.linalg.det(t)) / 6.0
    return g, volume


# TET10 mid-side node k joins corners EDGE[k].
EDGE = np.array([[0, 1], [1, 2], [2, 0], [0, 3], [1, 3], [2, 3]])


def centroid_stress(nodes: np.ndarray, tets: np.ndarray, u: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Von Mises at each element's centroid, and the element's volume."""
    g, volume = barycentric_gradients(nodes, tets)
    grad = np.zeros((len(tets), 3, 3))
    for k, (a, b) in enumerate(EDGE):
        dn = g[:, a] + g[:, b]  # ∇N of mid-side node k at the centroid
        grad += u[tets[:, 4 + k]][:, :, None] * dn[:, None, :]
    eps = 0.5 * (grad + grad.transpose(0, 2, 1))
    return von_mises(stress_from_strain(eps)), volume


def seat_nodes(nodes: np.ndarray, tris: np.ndarray, group: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """A seat's nodes and each one's share of its area."""
    chosen = tris[group == k]
    p = nodes[chosen[:, :3]]
    area = 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
    ids = np.unique(chosen)
    w = np.zeros(len(nodes))
    np.add.at(w, chosen.ravel(), np.repeat(area / 6.0, 6))
    return ids, w[ids]


def tet10_metrics(mesh: dict, u: np.ndarray, reactions: np.ndarray | None = None) -> dict:
    nodes, tets, tris, group = mesh["nodes"], mesh["tets"], mesh["tris"], mesh["group"]
    names = list(SEATS)
    points, disp, weights = {}, {}, {}
    for k, name in enumerate(names):
        ids, w = seat_nodes(nodes, tris, group, k)
        points[name], disp[name], weights[name] = nodes[ids], u[ids], w
    vm, volume = centroid_stress(nodes, tets, u)
    return metrics(points, disp, weights, vm, volume, u, reactions)
