"""The TET10 mesh's linear system, assembled once on the GPU and kept for every linear solver: the
stiffness over the free degrees of freedom, the seats' loads, and the rows of the held ones for the
reactions. Code_Aster and FEniCSx assemble their own; every other solver here reads this one, so
they differ only in how they solve it.

Straight-edged TET10 with a 4-point rule, exact for their stiffness; each seat's uniform traction
as consistent nodal forces - nothing on a six-node triangle's corners, a third of its area on each
mid-side node. Every node of the bolt holes' triangles is held.

    python system_tet10.py          # writes system.npz beside tet10.npz
"""

from __future__ import annotations

import json
import time

import numpy as np
import scipy.sparse as sp
from common import E_MPA, NU, OUT, SEATS
from tet10_post import EDGE

# The 4-point rule, exact for the quadratic integrand of a straight TET10's stiffness.
QA, QB = 0.5854101966249685, 0.1381966011250105
QUAD = np.array([[QA, QB, QB, QB], [QB, QA, QB, QB], [QB, QB, QA, QB], [QB, QB, QB, QA]])


def stiffness_gpu(nodes: np.ndarray, tets: np.ndarray, chunk: int = 20_000) -> sp.csr_matrix:
    """The global stiffness, element matrices B^T D B computed on the GPU a chunk at a time and
    summed into one CSR there."""
    import cupy as cp
    import cupyx.scipy.sparse as csp

    lam = E_MPA * NU / ((1 + NU) * (1 - 2 * NU))
    mu = E_MPA / (2 * (1 + NU))
    d = cp.zeros((6, 6))
    d[:3, :3] = lam
    d[cp.arange(3), cp.arange(3)] += 2 * mu
    d[cp.arange(3, 6), cp.arange(3, 6)] = mu
    quad = cp.asarray(QUAD)
    xyz = cp.asarray(nodes)
    n = 3 * len(nodes)
    total = None
    for start in range(0, len(tets), chunk):
        t = cp.asarray(tets[start : start + chunk])
        m = len(t)
        x = xyz[t[:, :4]]
        jac = cp.stack([x[:, 1] - x[:, 0], x[:, 2] - x[:, 0], x[:, 3] - x[:, 0]], axis=2)
        inv = cp.linalg.inv(jac)  # rows: ∇L1, ∇L2, ∇L3
        g = cp.empty((m, 4, 3))
        g[:, 1:] = inv
        g[:, 0] = -inv.sum(axis=1)
        volume = cp.abs(cp.linalg.det(jac)) / 6.0
        # ∇N of the ten nodes at each quadrature point: (m, q, 10, 3).
        gn = cp.empty((m, 4, 10, 3))
        gn[:, :, :4] = (4.0 * quad[None, :, :, None] - 1.0) * g[:, None, :, :]
        for k, (a, b) in enumerate(EDGE):
            gn[:, :, 4 + k] = 4.0 * (quad[None, :, b, None] * g[:, None, a] + quad[None, :, a, None] * g[:, None, b])
        # B (m, q, 6, 30): xx yy zz, then engineering shears xy yz zx.
        bm = cp.zeros((m, 4, 6, 30))
        gx, gy, gz = gn[..., 0], gn[..., 1], gn[..., 2]
        bm[:, :, 0, 0::3] = gx
        bm[:, :, 1, 1::3] = gy
        bm[:, :, 2, 2::3] = gz
        bm[:, :, 3, 0::3], bm[:, :, 3, 1::3] = gy, gx
        bm[:, :, 4, 1::3], bm[:, :, 4, 2::3] = gz, gy
        bm[:, :, 5, 0::3], bm[:, :, 5, 2::3] = gz, gx
        bm = bm.reshape(m * 4, 6, 30)
        ke = cp.matmul(bm.transpose(0, 2, 1), cp.matmul(d, bm)).reshape(m, 4, 30, 30)
        ke = (ke * (volume / 4.0)[:, None, None, None]).sum(axis=1)
        dof = (3 * t[:, :, None] + cp.arange(3)[None, None, :]).reshape(m, 30)
        rows = cp.repeat(dof, 30, axis=1).ravel()
        cols = cp.tile(dof, (1, 30)).ravel()
        block = csp.coo_matrix((ke.ravel(), (rows, cols)), shape=(n, n)).tocsr()
        total = block if total is None else total + block
        del ke, bm, gn, block
    cp.cuda.Device().synchronize()
    return total.get()


def loads(nodes, tris, group, setup) -> np.ndarray:
    """Each seat's traction as consistent nodal forces on its six-node triangles."""
    f = np.zeros(3 * len(nodes))
    for k, name in enumerate(SEATS):
        chosen = tris[group == k]
        p = nodes[chosen[:, :3]]
        area = 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
        traction = np.asarray(setup["seats"][name]["force_N"], float) / area.sum()
        for c in range(3):
            np.add.at(f, 3 * chosen[:, 3:].ravel() + c, np.repeat(area / 3.0, 3) * traction[c])
    return f


def build() -> dict:
    mesh = np.load(OUT / "tet10.npz")
    setup = json.loads((OUT / "setup.json").read_text(encoding="utf-8"))
    nodes, tets, tris, group = mesh["nodes"], mesh["tets"], mesh["tris"], mesh["group"]
    t0 = time.time()
    k_full = stiffness_gpu(nodes, tets)
    assemble_s = time.time() - t0
    f_full = loads(nodes, tris, group, setup)
    fixed_nodes = np.unique(tris[group == len(SEATS)])
    free_nodes = np.setdiff1d(np.arange(len(nodes)), fixed_nodes)
    free = (3 * free_nodes[:, None] + np.arange(3)).ravel()
    fixed = (3 * fixed_nodes[:, None] + np.arange(3)).ravel()
    t0 = time.time()
    k = k_full[free][:, free].tocsr()
    k.sort_indices()
    k_fix = k_full[fixed].tocsr()
    reduce_s = time.time() - t0
    np.savez(
        OUT / "system.npz",
        data=k.data,
        indices=k.indices,
        indptr=k.indptr,
        shape=np.array(k.shape),
        f=f_full[free],
        f_full=f_full,
        free_nodes=free_nodes,
        fixed_nodes=fixed_nodes,
        fix_data=k_fix.data,
        fix_indices=k_fix.indices,
        fix_indptr=k_fix.indptr,
        fix_shape=np.array(k_fix.shape),
    )
    info = {
        "dof": int(3 * len(nodes)),
        "free_dof": int(len(free)),
        "nnz": int(k.nnz),
        "assemble_gpu_s": round(assemble_s, 2),
        "reduce_s": round(reduce_s, 2),
        "load_N": f_full.reshape(-1, 3).sum(axis=0).tolist(),
    }
    (OUT / "system.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    return info


def cross_matrix(r: np.ndarray) -> np.ndarray:
    """[r]x for each row of r: [r]x v = r x v."""
    m = np.zeros((len(r), 3, 3))
    m[:, 0, 1], m[:, 0, 2] = -r[:, 2], r[:, 1]
    m[:, 1, 0], m[:, 1, 2] = r[:, 2], -r[:, 0]
    m[:, 2, 0], m[:, 2, 1] = -r[:, 1], r[:, 0]
    return m


def build_couplings() -> dict:
    """agenticCAE's supports on the same stiffness: each bolt position an RBE2 - its hole's nodes a
    rigid body about a held point on its axis, free to turn - eliminated, so the unknowns are the
    other nodes' displacements and three rotations a bolt; each seat's force an RBE3 - spread over
    the seat's nodes with equal weights so that force and moment about the axis point balance.
    Writes ``system_couplings.npz``: the reduced stiffness and load, and T with u = T q."""
    mesh = np.load(OUT / "tet10.npz")
    setup = json.loads((OUT / "setup.json").read_text(encoding="utf-8"))
    nodes, tets, tris, group, bolt = (
        mesh["nodes"],
        mesh["tets"],
        mesh["tris"],
        mesh["group"],
        mesh["bolt"],
    )
    n = len(nodes)
    t0 = time.time()
    k_full = stiffness_gpu(nodes, tets)
    assemble_s = time.time() - t0

    f = np.zeros(3 * n)
    for k, name in enumerate(SEATS):
        members = np.unique(tris[group == k])
        x = nodes[members]
        c = x.mean(axis=0)
        ref = np.array([*SEATS[name]["xy"], x[:, 2].mean()])
        force = np.asarray(setup["seats"][name]["force_N"], float)
        r = x - c
        inertia = (r**2).sum() * np.eye(3) - r.T @ r
        a = np.linalg.solve(inertia, np.cross(ref - c, force))
        share = force / len(members) + np.cross(a, r)
        f[(3 * members[:, None] + np.arange(3)).ravel()] += share.ravel()

    positions = setup["bolt_positions"]
    held = np.unique(tris[bolt >= 0])
    free_nodes = np.setdiff1d(np.arange(n), held)
    rows, cols, vals = [], [], []
    free_rows = (3 * free_nodes[:, None] + np.arange(3)).ravel()
    rows.append(free_rows)
    cols.append(np.arange(len(free_rows)))
    vals.append(np.ones(len(free_rows)))
    base = len(free_rows)
    owner = np.full(n, -1)
    for p in range(len(positions)):
        owner[np.unique(tris[bolt == p])] = p
    for p, position in enumerate(positions):
        members = np.flatnonzero(owner == p)
        point = np.array([*position["xy"], nodes[members, 2].mean()])
        block = -cross_matrix(nodes[members] - point)  # u_i = θ x r_i = -[r_i]x θ
        rr = (3 * members[:, None, None] + np.arange(3)[None, :, None]).repeat(3, axis=2)
        cc = np.broadcast_to(base + 3 * p + np.arange(3)[None, None, :], rr.shape)
        rows.append(rr.ravel())
        cols.append(cc.ravel())
        vals.append(block.ravel())
    t = sp.csr_matrix(
        (np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
        shape=(3 * n, base + 3 * len(positions)),
    )
    t0 = time.time()
    k = (t.T @ k_full @ t).tocsr()
    k.sort_indices()
    reduce_s = time.time() - t0
    np.savez(
        OUT / "system_couplings.npz",
        data=k.data,
        indices=k.indices,
        indptr=k.indptr,
        shape=np.array(k.shape),
        f=t.T @ f,
        f_full=f,
        t_data=t.data,
        t_indices=t.indices,
        t_indptr=t.indptr,
        t_shape=np.array(t.shape),
        held=held,
    )
    return {
        "dof": int(3 * n),
        "reduced_dof": int(k.shape[0]),
        "nnz": int(k.nnz),
        "assemble_gpu_s": assemble_s,
        "reduce_s": reduce_s,
        "load_N": f.reshape(-1, 3).sum(axis=0).tolist(),
    }


def load_couplings() -> dict:
    s = np.load(OUT / "system_couplings.npz")
    k = sp.csr_matrix((s["data"], s["indices"], s["indptr"]), shape=tuple(s["shape"]))
    t = sp.csr_matrix((s["t_data"], s["t_indices"], s["t_indptr"]), shape=tuple(s["t_shape"]))
    return {"k": k, "f": s["f"], "f_full": s["f_full"], "t": t, "held": s["held"]}


def load() -> dict:
    """The system as saved: ``k`` (free x free), ``f``, the node sets, and ``k_fix`` (held rows x all)."""
    s = np.load(OUT / "system.npz")
    k = sp.csr_matrix((s["data"], s["indices"], s["indptr"]), shape=tuple(s["shape"]))
    k_fix = sp.csr_matrix((s["fix_data"], s["fix_indices"], s["fix_indptr"]), shape=tuple(s["fix_shape"]))
    return {
        "k": k,
        "f": s["f"],
        "f_full": s["f_full"],
        "free_nodes": s["free_nodes"],
        "fixed_nodes": s["fixed_nodes"],
        "k_fix": k_fix,
    }


def result(system: dict, x: np.ndarray, n_nodes: int) -> tuple[np.ndarray, np.ndarray]:
    """The displacement at every node from the free solution, and the sum of the reactions."""
    u = np.zeros((n_nodes, 3))
    u[system["free_nodes"]] = np.asarray(x).reshape(-1, 3)
    fixed = (3 * system["fixed_nodes"][:, None] + np.arange(3)).ravel()
    reactions = (system["k_fix"] @ u.ravel() - system["f_full"][fixed]).reshape(-1, 3).sum(axis=0)
    return u, reactions


if __name__ == "__main__":
    import sys

    print(json.dumps(build_couplings() if "couplings" in sys.argv else build(), indent=1))
