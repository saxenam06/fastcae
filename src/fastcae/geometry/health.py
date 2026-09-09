"""Watertightness and fidelity checks on a tessellation.

This is the S0 gate. Everything after it - inside/outside classification, the distance field,
cell fractions, mass, wall thickness - assumes a closed, consistently oriented surface. If that
assumption is false the failures are silent: rays pass through a hole, parity flips, and a
region of the casting reads as air with no error anywhere.

So the checks are structural rather than statistical. An edge in a closed surface is used by
exactly two triangles, once in each direction. Counting is cheap and the answer is not a matter
of opinion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .brep import ExactProperties, Tessellation


@dataclass
class HealthReport:
    n_vertices: int
    n_triangles: int
    n_faces_tessellated: int
    n_faces_expected: int

    boundary_edges: int
    non_manifold_edges: int
    inconsistent_edges: int
    unreferenced_vertices: int
    n_components: int

    tess_volume_mm3: float
    tess_area_mm2: float
    exact_volume_mm3: float
    exact_area_mm2: float

    failures: list[str] = field(default_factory=list)

    @property
    def volume_error(self) -> float:
        return abs(self.tess_volume_mm3 - self.exact_volume_mm3) / abs(self.exact_volume_mm3)

    @property
    def area_error(self) -> float:
        return abs(self.tess_area_mm2 - self.exact_area_mm2) / abs(self.exact_area_mm2)

    @property
    def watertight(self) -> bool:
        return (
            self.boundary_edges == 0
            and self.non_manifold_edges == 0
            and self.inconsistent_edges == 0
        )

    @property
    def passed(self) -> bool:
        return not self.failures

    def render(self) -> str:
        ok = "PASS" if self.passed else "FAIL"
        lines = [
            f"S0 geometry health: {ok}",
            "",
            f"  vertices              {self.n_vertices:,}",
            f"  triangles             {self.n_triangles:,}",
            f"  faces tessellated     {self.n_faces_tessellated:,} of {self.n_faces_expected:,}",
            "",
            f"  boundary edges        {self.boundary_edges:,}   (want 0 - holes)",
            f"  non-manifold edges    {self.non_manifold_edges:,}   (want 0 - >2 triangles)",
            f"  inconsistent edges    {self.inconsistent_edges:,}   (want 0 - winding)",
            f"  unreferenced vertices {self.unreferenced_vertices:,}",
            f"  shells                {self.n_components:,}",
            "",
            f"  volume  tessellated   {self.tess_volume_mm3 / 1e3:12,.1f} cm3",
            f"          exact (B-rep) {self.exact_volume_mm3 / 1e3:12,.1f} cm3",
            f"          error         {self.volume_error * 100:12.4f} %",
            f"  area    tessellated   {self.tess_area_mm2 / 1e6:12.4f} m2",
            f"          exact (B-rep) {self.exact_area_mm2 / 1e6:12.4f} m2",
            f"          error         {self.area_error * 100:12.4f} %",
        ]
        if self.failures:
            lines += ["", "  failures:"] + [f"    - {f}" for f in self.failures]
        return "\n".join(lines)


def check(
    tess: Tessellation,
    exact: ExactProperties,
    max_volume_error: float = 0.002,
    max_area_error: float = 0.01,
) -> HealthReport:
    """Run the S0 gate.

    ``max_volume_error`` defaults to 0.2%. Volume is the strict one because it is what the
    distance field reproduces and what mass is read from. Area is looser by nature: a chord
    tessellation always under-reports curved area, and that bias is expected rather than a
    defect.
    """
    edges = _edge_table(tess.triangles)
    boundary, non_manifold, inconsistent = _edge_faults(edges)

    used = np.zeros(tess.n_vertices, dtype=bool)
    used[tess.triangles.ravel()] = True

    report = HealthReport(
        n_vertices=tess.n_vertices,
        n_triangles=tess.n_triangles,
        n_faces_tessellated=len(tess.face_ids),
        n_faces_expected=exact.n_faces,
        boundary_edges=boundary,
        non_manifold_edges=non_manifold,
        inconsistent_edges=inconsistent,
        unreferenced_vertices=int((~used).sum()),
        n_components=_count_components(tess),
        tess_volume_mm3=tess.volume_mm3(),
        tess_area_mm2=tess.area_mm2(),
        exact_volume_mm3=exact.volume_mm3,
        exact_area_mm2=exact.area_mm2,
    )

    if boundary:
        report.failures.append(
            f"{boundary} boundary edges - the surface has holes, so inside/outside is undefined"
        )
    if non_manifold:
        report.failures.append(
            f"{non_manifold} non-manifold edges - more than two triangles meet along an edge"
        )
    if inconsistent:
        report.failures.append(
            f"{inconsistent} inconsistently wound edges - outward normals are not coherent"
        )
    if report.n_faces_tessellated < exact.n_faces:
        report.failures.append(
            f"{exact.n_faces - report.n_faces_tessellated} CAD faces produced no triangles"
        )
    if report.tess_volume_mm3 <= 0:
        report.failures.append("tessellated volume is not positive - winding points inward")
    if report.volume_error > max_volume_error:
        report.failures.append(
            f"volume error {report.volume_error * 100:.4f}% exceeds {max_volume_error * 100:.2f}%"
        )
    if report.area_error > max_area_error:
        report.failures.append(
            f"area error {report.area_error * 100:.4f}% exceeds {max_area_error * 100:.2f}%"
        )

    return report


def _edge_table(triangles: np.ndarray) -> np.ndarray:
    """Every directed edge of every triangle, as (n*3, 2)."""
    return np.concatenate(
        [triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]], axis=0
    )


def _edge_faults(directed: np.ndarray) -> tuple[int, int, int]:
    """Count holes, non-manifold edges and winding faults from the directed edge list.

    On a closed, coherently oriented surface every undirected edge appears exactly twice, once
    in each direction. Anything else is one of three faults, and which one it is tells you what
    went wrong: a count of one is a hole, more than two is a non-manifold junction, and two in
    the same direction is a flipped triangle.
    """
    undirected = np.sort(directed, axis=1)
    _, inverse, counts = np.unique(undirected, axis=0, return_inverse=True, return_counts=True)

    boundary = int((counts == 1).sum())
    non_manifold = int((counts > 2).sum())

    # Winding: for edges used exactly twice, the two uses must have opposite direction.
    forward = directed[:, 0] < directed[:, 1]
    pair_ids = np.nonzero(counts == 2)[0]
    if pair_ids.size:
        net = np.zeros(counts.size, dtype=np.int64)
        np.add.at(net, inverse, np.where(forward, 1, -1))
        inconsistent = int((net[pair_ids] != 0).sum())
    else:
        inconsistent = 0

    return boundary, non_manifold, inconsistent


def _count_components(tess: Tessellation) -> int:
    """Connected shells, by union-find over triangle adjacency through shared vertices."""
    parent = np.arange(tess.n_vertices, dtype=np.int64)

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = int(parent[x])
        return x

    for a, b in (
        (tess.triangles[:, 0], tess.triangles[:, 1]),
        (tess.triangles[:, 1], tess.triangles[:, 2]),
    ):
        for x, y in zip(a, b, strict=True):
            rx, ry = find(int(x)), find(int(y))
            if rx != ry:
                parent[ry] = rx

    used = np.zeros(tess.n_vertices, dtype=bool)
    used[tess.triangles.ravel()] = True
    roots = {find(int(i)) for i in np.nonzero(used)[0]}
    return len(roots)
