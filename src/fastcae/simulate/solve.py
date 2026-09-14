"""A deck solved again here: quadratic tetrahedra, linear elastic, on the GPU with cuDSS.

What the deck asks for is applied as it says, from :class:`~.setup.Setup`:

- **Held** degrees of freedom are taken out of the unknowns at the values given.
- **A rigid coupling** makes its nodes one rigid body moving with its reference node: each node's
  displacement is the reference's translation plus its rotation crossed with the arm from it. The
  reference's six motions are unknowns, less those the deck holds.
- **A distributing coupling** adds no stiffness. A load on its reference node is spread over the
  group's nodes, weighted, so that the force and its moment about the reference balance; the
  reference's motion is read afterwards as the weighted best fit of the group's motion.
- **Nodal loads** act at each node of their group; **surface loads** as consistent nodal forces
  on six-node triangles - on a straight one nothing at the corners and a third of the load on each
  mid-side node.

The unknowns are ``q`` with ``u = T q + u0``; the stiffness solved is ``T' K T``, factorised by
cuDSS on the GPU, part of its factor in host memory when the card is short. Stress is taken at every
node of every element - exact on a straight-edged TET10, whose strain is linear - and averaged over
the elements round each node, as Code_Aster's ``SIGM_NOEU`` is.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import scipy.sparse as sp

from .fem import EDGES, FEMesh, triangle_areas
from .setup import FORCES, MOMENTS, ROTATIONS, TRANSLATIONS, Setup

# The 4-point rule, exact for a straight TET10's stiffness.
QA, QB = 0.5854101966249685, 0.1381966011250105
QUAD = np.array([[QA, QB, QB, QB], [QB, QA, QB, QB], [QB, QB, QA, QB], [QB, QB, QB, QA]])
# The barycentric coordinates of a TET10's ten nodes.
NODE_L = np.vstack([np.eye(4), 0.5 * (np.eye(4)[EDGES[:, 0]] + np.eye(4)[EDGES[:, 1]])])
# Past this many unknowns the running sum of element matrices is kept in host memory.
ON_HOST_DOF = 1_600_000


class Unsupported(ValueError):
    """The deck asks for something this solver does not do; the message says what."""


@dataclass
class Solution:
    """The answer at every node of the mesh, and how it was reached."""

    u: np.ndarray
    rotation: np.ndarray
    stress: np.ndarray
    von_mises: np.ndarray
    reactions: dict[str, list[float]]
    unknowns: int
    times: dict[str, float] = field(default_factory=dict)
    info: dict[str, object] = field(default_factory=dict)


def _cross(r: np.ndarray) -> np.ndarray:
    """[r]x for each row of r: [r]x v = r x v."""
    m = np.zeros((len(r), 3, 3))
    m[:, 0, 1], m[:, 0, 2] = -r[:, 2], r[:, 1]
    m[:, 1, 0], m[:, 1, 2] = r[:, 2], -r[:, 0]
    m[:, 2, 0], m[:, 2, 1] = -r[:, 1], r[:, 0]
    return m


def _gradients(xp, x):  # type: ignore[no-untyped-def]
    """∇L0..∇L3 of each tetrahedron (m, 4, 3), and its volume."""
    jac = xp.stack([x[:, 1] - x[:, 0], x[:, 2] - x[:, 0], x[:, 3] - x[:, 0]], axis=2)
    inv = xp.linalg.inv(jac)
    g = xp.empty((len(x), 4, 3))
    g[:, 1:] = inv
    g[:, 0] = -inv.sum(axis=1)
    return g, xp.abs(xp.linalg.det(jac)) / 6.0


def _shape_gradients(xp, g, lam):  # type: ignore[no-untyped-def]
    """∇N of the ten nodes at points of barycentric coordinates ``lam`` (p, 4): (m, p, 10, 3)."""
    lam = xp.asarray(lam)
    gn = xp.empty((g.shape[0], lam.shape[0], 10, 3))
    gn[:, :, :4] = (4.0 * lam[None, :, :, None] - 1.0) * g[:, None, :, :]
    for k, (a, b) in enumerate(EDGES):
        gn[:, :, 4 + k] = 4.0 * (
            lam[None, :, b, None] * g[:, None, a] + lam[None, :, a, None] * g[:, None, b]
        )
    return gn


def _elasticity(xp, young, poisson):  # type: ignore[no-untyped-def]
    """The 6x6 isotropic elasticity matrix per element (m, 6, 6), engineering shears xy yz zx."""
    young, poisson = xp.asarray(young), xp.asarray(poisson)
    lam = young * poisson / ((1 + poisson) * (1 - 2 * poisson))
    mu = young / (2 * (1 + poisson))
    d = xp.zeros((len(young), 6, 6))
    d[:, :3, :3] = lam[:, None, None]
    for i in range(3):
        d[:, i, i] += 2 * mu
        d[:, 3 + i, 3 + i] = mu
    return d


def _b_matrix(xp, gn):  # type: ignore[no-untyped-def]
    """B (m, p, 6, 30) from shape gradients: xx yy zz, then xy yz zx."""
    m, p = gn.shape[:2]
    bm = xp.zeros((m, p, 6, 30))
    gx, gy, gz = gn[..., 0], gn[..., 1], gn[..., 2]
    bm[:, :, 0, 0::3] = gx
    bm[:, :, 1, 1::3] = gy
    bm[:, :, 2, 2::3] = gz
    bm[:, :, 3, 0::3], bm[:, :, 3, 1::3] = gy, gx
    bm[:, :, 4, 1::3], bm[:, :, 4, 2::3] = gz, gy
    bm[:, :, 5, 0::3], bm[:, :, 5, 2::3] = gz, gx
    return bm


def _materials(mesh: FEMesh, setup: Setup, tets: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Young's modulus and Poisson's ratio of each tetrahedron, from the deck's assignments."""
    if not setup.materials:
        raise Unsupported("the deck defines no elastic material")
    young = np.full(len(tets), np.nan)
    poisson = np.full(len(tets), np.nan)
    for m in setup.materials:
        if not m.groups:
            young[:], poisson[:] = m.young, m.poisson
            continue
        for g in m.groups:
            rows = mesh.cell_groups.get(g, {}).get("TETRA10")
            if rows is not None:
                young[rows], poisson[rows] = m.young, m.poisson
    if np.isnan(young).any():
        raise Unsupported(f"{int(np.isnan(young).sum())} elements have no material")
    return young, poisson


def stiffness(
    nodes: np.ndarray,
    tets: np.ndarray,
    young: np.ndarray,
    poisson: np.ndarray,
    gpu: bool = True,
    chunk: int = 20_000,
) -> sp.csr_matrix:
    """The global stiffness over every node's three translations, element matrices B'DB computed a
    chunk at a time - on the GPU when there is one - and summed into one CSR."""
    if gpu:
        import cupy as xp
        import cupyx.scipy.sparse as xsp
    else:
        xp, xsp = np, sp
    n = 3 * len(nodes)
    on_host = not gpu or n > ON_HOST_DOF
    quad = QUAD
    xyz = xp.asarray(nodes)
    total = None
    for start in range(0, len(tets), chunk):
        t = xp.asarray(tets[start : start + chunk])
        g, volume = _gradients(xp, xyz[t[:, :4]])
        gn = _shape_gradients(xp, g, quad)
        bm = _b_matrix(xp, gn)
        d = _elasticity(xp, young[start : start + chunk], poisson[start : start + chunk])
        m = len(t)
        db = xp.einsum("mij,mqjk->mqik", d, bm)
        ke = xp.einsum("mqji,mqjk->mik", bm, db) * (volume / 4.0)[:, None, None]
        dof = (3 * t[:, :, None] + xp.arange(3)[None, None, :]).reshape(m, 30)
        rows = xp.repeat(dof, 30, axis=1).ravel()
        cols = xp.tile(dof, (1, 30)).ravel()
        block = xsp.coo_matrix((ke.ravel(), (rows, cols)), shape=(n, n)).tocsr()
        if gpu and on_host:
            block = block.get()
            xp.get_default_memory_pool().free_all_blocks()
        total = block if total is None else total + block
        del ke, bm, gn, db, block
    if gpu and not on_host:
        total = total.get()  # type: ignore[union-attr]
    if gpu:
        # CuPy keeps freed blocks for reuse; cuDSS allocates outside that pool and needs them back.
        xp.get_default_memory_pool().free_all_blocks()
    return total  # type: ignore[return-value]


def nodal_stress(
    nodes: np.ndarray,
    tets: np.ndarray,
    young: np.ndarray,
    poisson: np.ndarray,
    u: np.ndarray,
    n_nodes: int,
    chunk: int = 50_000,
) -> tuple[np.ndarray, np.ndarray]:
    """Stress at every node (SIXX SIYY SIZZ SIXY SIXZ SIYZ) averaged over the elements round it, and
    von Mises likewise averaged from each element's own value there."""
    total = np.zeros((n_nodes, 6))
    vm_total = np.zeros(n_nodes)
    count = np.zeros(n_nodes)
    for start in range(0, len(tets), chunk):
        t = tets[start : start + chunk]
        g, _ = _gradients(np, nodes[t[:, :4]])
        gn = _shape_gradients(np, g, NODE_L)  # (m, 10 points, 10 nodes, 3)
        ue = u[t]  # (m, 10, 3)
        grad = np.einsum("mpnj,mni->mpij", gn, ue)
        eps = 0.5 * (grad + grad.transpose(0, 1, 3, 2))
        e, nu = young[start : start + chunk, None], poisson[start : start + chunk, None]
        lam = e * nu / ((1 + nu) * (1 - 2 * nu))
        mu = e / (2 * (1 + nu))
        tr = eps[..., 0, 0] + eps[..., 1, 1] + eps[..., 2, 2]
        s = np.empty(eps.shape[:2] + (6,))
        for i in range(3):
            s[..., i] = 2 * mu * eps[..., i, i] + lam * tr
        s[..., 3] = 2 * mu * eps[..., 0, 1]
        s[..., 4] = 2 * mu * eps[..., 0, 2]
        s[..., 5] = 2 * mu * eps[..., 1, 2]
        vm = von_mises(s)
        np.add.at(total, t.ravel(), s.reshape(-1, 6))
        np.add.at(vm_total, t.ravel(), vm.ravel())
        np.add.at(count, t.ravel(), 1.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return total / count[:, None], vm_total / count


def von_mises(s: np.ndarray) -> np.ndarray:
    """Von Mises of stresses given as (..., 6): xx yy zz xy xz yz."""
    xx, yy, zz, xy, xz, yz = (s[..., i] for i in range(6))
    return np.sqrt(
        0.5 * ((xx - yy) ** 2 + (yy - zz) ** 2 + (zz - xx) ** 2) + 3.0 * (xy**2 + yz**2 + xz**2)
    )


def rigid_fit(
    points: np.ndarray, u: np.ndarray, weights: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The weighted best-fit rigid motion of points: the centre's translation, the rotation, and the
    centre itself."""
    w = weights / weights.sum()
    centre = w @ points
    r = points - centre
    t = w @ u
    arms = -_cross(r)  # arms[i] @ θ = θ x r_i
    a = np.einsum("n,nji,njk->ik", w, arms, arms)
    b = np.einsum("n,nji,nj->i", w, arms, u - t)
    return t, np.linalg.solve(a, b), centre


def _group_weights(mesh: FEMesh, members: np.ndarray, weights: list[float]) -> np.ndarray:
    return np.full(len(members), weights[0] if weights else 1.0)


def solve(mesh: FEMesh, setup: Setup, gpu: bool = True, log=print) -> Solution:  # type: ignore[no-untyped-def]
    """Solve the deck's linear static analysis on its mesh."""
    tets = mesh.tet10
    if tets is None:
        raise Unsupported("the mesh's volume is not quadratic tetrahedra alone")
    started = time.time()
    n = mesh.n_nodes
    nodes = mesh.nodes
    active = setup.active()
    young, poisson = _materials(mesh, setup, tets)
    volume_nodes = np.zeros(n, bool)
    volume_nodes[np.unique(tets)] = True

    t0 = time.time()
    k_full = stiffness(nodes, tets, young, poisson, gpu=gpu)
    times = {"assemble_s": time.time() - t0}
    log(f"assembled {3 * int(volume_nodes.sum()):,} unknowns in {times['assemble_s']:.1f} s")

    f = np.zeros(3 * n)
    u0 = np.zeros(3 * n)
    # Reference nodes of rigid couplings: their six motions, and which the deck holds.
    rigid = [r for r in setup.rigid if r.load_set in active]
    held = [h for h in setup.held if h.load_set in active]
    distributing = [d for d in setup.distributing if d.load_set in active]
    nodal = [x for x in setup.nodal_loads if x.load_set in active]
    surface = [x for x in setup.surface_loads if x.load_set in active]

    slave_of = np.full(n, -1)
    refs: list[dict] = []
    for i, tie in enumerate(rigid):
        if tie.reference is None:
            raise Unsupported(f"rigid coupling {tie.groups} has no single-node reference")
        ref_node = int(mesh.group_nodes(tie.reference)[0])
        members = np.unique(
            np.concatenate([mesh.group_nodes(g) for g in tie.groups if g != tie.reference])
        )
        members = members[members != ref_node]
        if (slave_of[members] >= 0).any():
            raise Unsupported(f"nodes of {tie.groups} are tied by two rigid couplings")
        slave_of[members] = i
        refs.append({"node": ref_node, "members": members, "held": {}, "group": tie.reference})
    ref_index = {r["node"]: i for i, r in enumerate(refs)}
    distributing_refs = {int(mesh.group_nodes(d.reference)[0]) for d in distributing}

    held_nodes = np.zeros(3 * n, bool)
    for h in held:
        for g in h.groups:
            for node in mesh.group_nodes(g):
                node = int(node)
                if node in ref_index:
                    refs[ref_index[node]]["held"].update(h.dofs)
                elif node in distributing_refs:
                    raise Unsupported(
                        f"{g}: holding a distributing coupling's reference is not solved here"
                    )
                elif volume_nodes[node]:
                    for c, name in enumerate(TRANSLATIONS):
                        if name in h.dofs:
                            held_nodes[3 * node + c] = True
                            u0[3 * node + c] = h.dofs[name]

    # Loads.
    for load in nodal:
        vec = np.array([load.values.get(c, 0.0) for c in FORCES])
        mom = np.array([load.values.get(c, 0.0) for c in MOMENTS])
        for node in mesh.group_nodes(load.group):
            node = int(node)
            if node in ref_index:
                refs[ref_index[node]].setdefault("load", np.zeros(6))
                refs[ref_index[node]]["load"] += np.concatenate([vec, mom])
            elif node in distributing_refs:
                continue  # spread below
            else:
                if np.any(mom):
                    raise Unsupported(f"{load.group}: a moment on a node without rotations")
                f[3 * node : 3 * node + 3] += vec
    for d in distributing:
        ref_node = int(mesh.group_nodes(d.reference)[0])
        vec = np.zeros(3)
        mom = np.zeros(3)
        for load in nodal:
            if ref_node in set(mesh.group_nodes(load.group).tolist()):
                vec += [load.values.get(c, 0.0) for c in FORCES]
                mom += [load.values.get(c, 0.0) for c in MOMENTS]
        if not np.any(vec) and not np.any(mom):
            continue
        members = mesh.group_nodes(d.group)
        w = _group_weights(mesh, members, d.weights)
        x = nodes[members]
        wn = w / w.sum()
        c = wn @ x
        r = x - c
        inertia = np.einsum("n,nk,nk->", w, r, r) * np.eye(3) - np.einsum("n,ni,nj->ij", w, r, r)
        a = np.linalg.solve(inertia, np.cross(nodes[ref_node] - c, vec) + mom)
        share = wn[:, None] * vec[None, :] + w[:, None] * np.cross(a[None, :], r)
        np.add.at(f, (3 * members[:, None] + np.arange(3)).ravel(), share.ravel())
    for load in surface:
        tris = mesh.cells.get("TRIA6")
        rows = mesh.cell_groups.get(load.group, {}).get("TRIA6")
        if tris is None or rows is None:
            raise Unsupported(f"{load.group}: surface loads need six-node triangles")
        chosen = tris[rows]
        area = triangle_areas(nodes, chosen)
        if load.kind == "PRES_REP":
            p = nodes[chosen[:, :3]]
            normal = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
            normal /= np.linalg.norm(normal, axis=1, keepdims=True)
            traction = -load.values.get("PRES", 0.0) * normal
        else:
            traction = np.tile([load.values.get(c, 0.0) for c in FORCES], (len(chosen), 1))
        for c in range(3):
            np.add.at(f, 3 * chosen[:, 3:].ravel() + c, np.repeat(area / 3.0 * traction[:, c], 3))

    # The map from unknowns to every node's displacement.
    t0 = time.time()
    free = np.flatnonzero(np.repeat(volume_nodes, 3) & ~held_nodes & (np.repeat(slave_of, 3) < 0))
    rows_list = [free]
    cols_list = [np.arange(len(free))]
    vals_list = [np.ones(len(free))]
    col = len(free)
    extra_load = []
    for r in refs:
        held_dofs = r["held"]
        free_dofs = [i for i, name in enumerate(TRANSLATIONS + ROTATIONS) if name not in held_dofs]
        value = np.array([held_dofs.get(name, 0.0) for name in TRANSLATIONS + ROTATIONS])
        members = r["members"]
        arm = nodes[members] - nodes[r["node"]]
        # u_i = u_R + θ x r_i = [I | -[r_i]x] [u_R; θ]
        block = np.concatenate(
            [np.broadcast_to(np.eye(3), (len(members), 3, 3)), -_cross(arm)], axis=2
        )
        u0[(3 * members[:, None] + np.arange(3)).ravel()] += (block @ value).ravel()
        r["columns"] = {}
        for j in free_dofs:
            rows_list.append((3 * members[:, None] + np.arange(3)).ravel())
            cols_list.append(np.full(3 * len(members), col))
            vals_list.append(block[:, :, j].ravel())
            r["columns"][j] = col
            extra_load.append((col, float(r.get("load", np.zeros(6))[j])))
            col += 1
        r["value"] = value
    tmat = sp.csr_matrix(
        (np.concatenate(vals_list), (np.concatenate(rows_list), np.concatenate(cols_list))),
        shape=(3 * n, col),
    )
    k_red = (tmat.T @ k_full @ tmat).tocsr()
    k_red.sort_indices()
    f_red = tmat.T @ (f - k_full @ u0)
    for j, value in extra_load:
        f_red[j] += value
    times["reduce_s"] = time.time() - t0
    log(f"{col:,} unknowns after supports and couplings, reduced in {times['reduce_s']:.1f} s")

    t0 = time.time()
    q, solver_info = _factor_and_solve(k_red, f_red, gpu)
    times["solve_s"] = time.time() - t0
    times.update({k: v for k, v in solver_info.items() if k.endswith("_s")})
    log(f"solved in {times['solve_s']:.1f} s")

    u_flat = tmat @ q + u0
    u = u_flat.reshape(-1, 3)
    rotation = np.full((n, 3), np.nan)
    for r in refs:
        motion = r["value"].copy()
        for j, c in r["columns"].items():
            motion[j] = q[c]
        u[r["node"]] = motion[:3]
        rotation[r["node"]] = motion[3:]
    for d in distributing:
        ref_node = int(mesh.group_nodes(d.reference)[0])
        members = mesh.group_nodes(d.group)
        t_c, theta, centre = rigid_fit(
            nodes[members], u[members], _group_weights(mesh, members, d.weights)
        )
        u[ref_node] = t_c + np.cross(theta, nodes[ref_node] - centre)
        rotation[ref_node] = theta

    # Reactions: what each held group's nodes push back with.
    residual = (k_full @ u_flat - f).reshape(-1, 3)
    reactions: dict[str, list[float]] = {}
    for h in held:
        for g in h.groups:
            members = mesh.group_nodes(g)
            force = np.zeros(3)
            for node in members:
                node = int(node)
                if node in ref_index:
                    force += residual[refs[ref_index[node]]["members"]].sum(axis=0)
                elif volume_nodes[node]:
                    force += residual[node]
            reactions[g] = force.tolist()

    t0 = time.time()
    stress, vm = nodal_stress(nodes, tets, young, poisson, u, n)
    times["stress_s"] = time.time() - t0
    times["total_s"] = time.time() - started
    return Solution(
        u=u,
        rotation=rotation,
        stress=stress,
        von_mises=vm,
        reactions=reactions,
        unknowns=col,
        times=times,
        info={"solver": solver_info.get("solver", "?"), "residual": solver_info.get("residual")},
    )


def _mtlayer() -> str | None:
    """cuDSS's threading layer, shipped beside it: without it, its reordering runs on one core."""
    try:
        import nvidia
    except ImportError:
        return None
    for base in nvidia.__path__:
        for pattern in ("cudss_mtlayer*.dll", "libcudss_mtlayer_gomp.so*"):
            for found in Path(base).rglob(pattern):
                return str(found)
    return None


def _factor_and_solve(k: sp.csr_matrix, f: np.ndarray, gpu: bool) -> tuple[np.ndarray, dict]:
    if not gpu:
        from scipy.sparse.linalg import spsolve

        x = spsolve(k.tocsc(), f)
        return x, {
            "solver": "scipy",
            "residual": float(np.linalg.norm(k @ x - f) / max(np.linalg.norm(f), 1e-300)),
        }
    import cupy as cp
    import cupyx.scipy.sparse as csp
    from nvmath.sparse.advanced import (
        DirectSolver,
        DirectSolverMatrixType,
        ExecutionCUDA,
        HybridMemoryModeOptions,
    )

    from ..gpu import release

    release()
    a = csp.csr_matrix(k)
    b = cp.asarray(f)
    options = {"sparse_system_type": DirectSolverMatrixType.SPD, "multithreading_lib": _mtlayer()}
    execution = ExecutionCUDA(
        hybrid_memory_mode_options=HybridMemoryModeOptions(hybrid_memory_mode=True)
    )
    try:
        with DirectSolver(a, b.reshape(-1, 1), options=options, execution=execution) as solver:
            t0 = time.time()
            solver.plan()
            cp.cuda.Device().synchronize()
            plan = time.time() - t0
            t0 = time.time()
            solver.factorize()
            cp.cuda.Device().synchronize()
            factor = time.time() - t0
            t0 = time.time()
            x = solver.solve()
            cp.cuda.Device().synchronize()
            solve_s = time.time() - t0
        x = cp.asnumpy(x).ravel()
    finally:
        # Whether it solved or ran out: the card handed back, for the next build or solve.
        a = b = None
        release()
    residual = float(np.linalg.norm(k @ x - f) / max(np.linalg.norm(f), 1e-300))
    return x, {
        "solver": "cuDSS",
        "plan_s": plan,
        "factor_s": factor,
        "backsolve_s": solve_s,
        "residual": residual,
    }
