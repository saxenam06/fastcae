"""Linear tetrahedra finished as second-order ones: what a mesher gives, as the solvers take it.

The mesh itself comes from :mod:`.face_mesh` - the part's CAD, or a design's, meshed face by face.
"""

from __future__ import annotations

import numpy as np

from .fem import FEMesh, oriented, quadratic


def finish(nodes: np.ndarray, tets: np.ndarray) -> FEMesh:
    """Linear tets as TET10 with straight mid-side nodes, the unused nodes dropped, every tet
    positively oriented; the volume as the cell group ``BULK``."""
    used, compact = np.unique(tets, return_inverse=True)
    nodes, tets = np.asarray(nodes, np.float64)[used], compact.reshape(tets.shape)
    tets = oriented(nodes, tets)
    nodes10, tets10 = quadratic(nodes, tets)
    return FEMesh(
        nodes=nodes10,
        cells={"TETRA10": tets10},
        cell_groups={"BULK": {"TETRA10": np.arange(len(tets10))}},
    )
