"""The TET10 mesh solved by FEniCSx (dolfinx 0.11): quadratic displacement on the mesh's straight
tets - the same field as a straight-edged TET10 - bolts held, each seat's traction on its faces.
Solved by conjugate gradient with PETSc's algebraic multigrid (GAMG, the rigid-body modes as its
near-nullspace), and by MUMPS directly. Runs inside WSL, in the ``fenicsx`` environment:

    micromamba run -n fenicsx python solve_fenicsx.py /mnt/c/.../design7 [gamg] [mumps]

Writes ``fenicsx_<method>.npz``: displacement at every TET10 node, in the mesh's own order.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(sys.argv[1])
METHODS = sys.argv[2:] or ["gamg", "mumps"]
E_MPA, NU = 169_000.0, 0.275


def main() -> None:
    import basix.ufl
    import dolfinx
    import ufl
    from dolfinx import fem
    from dolfinx import mesh as dmesh
    from dolfinx.fem.petsc import apply_lifting, assemble_matrix, assemble_vector, set_bc
    from mpi4py import MPI
    from petsc4py import PETSc
    from scipy.spatial import cKDTree

    data = np.load(HERE / "tet10.npz")
    setup = json.loads((HERE / "setup.json").read_text())
    nodes10, tets10, tris, group = data["nodes"], data["tets"], data["tris"], data["group"]
    names = [str(n) for n in data["names"]]
    linear = int(data["linear_nodes"])
    report = {}

    t0 = time.time()
    element = basix.ufl.element("Lagrange", "tetrahedron", 1, shape=(3,))
    domain = dmesh.create_mesh(MPI.COMM_SELF, tets10[:, :4].astype(np.int64), element, nodes10[:linear])
    tdim = domain.topology.dim
    domain.topology.create_connectivity(tdim - 1, tdim)
    # The labelled boundary triangles, in the mesh's own numbering.
    keep = group >= 0
    entities, values = dolfinx.io.distribute_entity_data(
        domain, tdim - 1, tris[keep][:, :3].astype(np.int64), group[keep].astype(np.int32)
    )
    tags = dmesh.meshtags_from_entities(
        domain, tdim - 1, dolfinx.graph.adjacencylist(entities), values.astype(np.int32)
    )
    report["mesh_s"] = time.time() - t0

    V = fem.functionspace(domain, ("Lagrange", 2, (3,)))
    lam = E_MPA * NU / ((1 + NU) * (1 - 2 * NU))
    mu = E_MPA / (2 * (1 + NU))
    u, v = ufl.TrialFunction(V), ufl.TestFunction(V)

    def sigma(w):
        e = ufl.sym(ufl.grad(w))
        return 2 * mu * e + lam * ufl.tr(e) * ufl.Identity(3)

    ds = ufl.Measure("ds", domain=domain, subdomain_data=tags)
    a = ufl.inner(sigma(u), ufl.sym(ufl.grad(v))) * ufl.dx
    L = 0
    for k, name in enumerate(names[:-1]):
        area = fem.assemble_scalar(fem.form(1.0 * ds(k)))
        traction = np.asarray(setup["seats"][name]["force_N"], float) / area
        L = L + ufl.inner(fem.Constant(domain, traction), v) * ds(k)
    bolts = tags.find(len(names) - 1)
    dofs = fem.locate_dofs_topological(V, tdim - 1, bolts)
    bc = fem.dirichletbc(np.zeros(3), dofs, V)

    t0 = time.time()
    A = assemble_matrix(fem.form(a), bcs=[bc])
    A.assemble()
    b = assemble_vector(fem.form(L))
    apply_lifting(b, [fem.form(a)], bcs=[[bc]])
    b.ghostUpdate(addv=PETSc.InsertMode.ADD, mode=PETSc.ScatterMode.REVERSE)
    set_bc(b, [bc])
    report["assemble_s"] = time.time() - t0
    report["dof"] = int(V.dofmap.index_map.size_global * 3)

    # Rigid-body modes, for the multigrid's coarse spaces.
    x = V.tabulate_dof_coordinates()
    modes = []
    for m in range(6):
        vec = np.zeros((len(x), 3))
        if m < 3:
            vec[:, m] = 1.0
        else:
            i, j = {3: (0, 1), 4: (1, 2), 5: (2, 0)}[m]
            vec[:, i], vec[:, j] = -x[:, j], x[:, i]
        pv = A.createVecLeft()
        pv.setArray(vec.ravel())
        modes.append(pv)
    nullspace = PETSc.NullSpace().create(vectors=modes)

    tree = cKDTree(x)
    distance, where = tree.query(nodes10)
    report["dof_match_mm"] = float(distance.max())
    for method in METHODS:
        ksp = PETSc.KSP().create(MPI.COMM_SELF)
        ksp.setOperators(A)
        opts = PETSc.Options()
        prefix = f"{method}_"
        ksp.setOptionsPrefix(prefix)
        if method == "gamg":
            A.setNearNullSpace(nullspace)
            opts[prefix + "ksp_type"] = "cg"
            opts[prefix + "ksp_rtol"] = 1e-8
            opts[prefix + "pc_type"] = "gamg"
            opts[prefix + "pc_gamg_type"] = "agg"
            opts[prefix + "mg_levels_ksp_type"] = "chebyshev"
            opts[prefix + "mg_levels_pc_type"] = "jacobi"
        else:
            opts[prefix + "ksp_type"] = "preonly"
            opts[prefix + "pc_type"] = "lu"
            opts[prefix + "pc_factor_mat_solver_type"] = "mumps"
        ksp.setFromOptions()
        sol = A.createVecRight()
        t0 = time.time()
        ksp.solve(b, sol)
        took = time.time() - t0
        values = sol.getArray().reshape(-1, 3)
        np.savez_compressed(HERE / f"fenicsx_{method}.npz", u=values[where])
        report[method] = {
            "solve_s": took,
            "iterations": ksp.getIterationNumber(),
            "reason": ksp.getConvergedReason(),
        }
        print(method, report[method], flush=True)
    (HERE / "fenicsx.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
