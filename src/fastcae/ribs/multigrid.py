"""Multigrid for the voxel model: conjugate gradients preconditioned by a V-cycle over coarser
lattices, on the card.

Every node of the voxel model sits on a corner of one lattice. A lattice twice as coarse
carries a fine node's motion as the trilinear blend of the coarse corners round it (``P``), and its
stiffness is ``Pᵀ K P`` - Galerkin's, so the coarse lattice feels a void as the fine one does. The
V-cycle - smooth, carry the residual down, solve the coarsest outright, carry the correction up,
smooth - is the preconditioner; conjugate gradients then converge in tens of steps where the
diagonal alone takes thousands.

The lattices and their blends depend only on where the nodes are and which the deck holds, so they
are made once; each new stiffness makes only the coarse matrices again (:meth:`Hierarchy.setup`).
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

COARSEST_DOFS = 6000
"""Below this many unknowns a lattice is solved outright."""
DEGREE = 2
"""The smoother: a Chebyshev polynomial of this degree in the diagonal-scaled matrix."""
LOW, HIGH = 0.3, 1.1
"""The share of the largest eigenvalue the smoother damps from and to."""


def _parents(index: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Each node's coarse corners and their trilinear weights: (rows, coarse index (k, 3),
    weight)."""
    rows, parents, weights = [], [], []
    per_axis = []
    for d in range(3):
        c = index[:, d]
        odd = (c % 2).astype(bool)
        lo = np.where(odd, (c - 1) // 2, c // 2)
        hi = np.where(odd, (c + 1) // 2, c // 2)
        w = np.where(odd, 0.5, 1.0)
        per_axis.append(((lo, w), (hi, np.where(odd, 0.5, 0.0))))
    for a in range(2):
        for b in range(2):
            for c in range(2):
                (px, wx), (py, wy), (pz, wz) = per_axis[0][a], per_axis[1][b], per_axis[2][c]
                w = wx * wy * wz
                keep = w > 0.0
                rows.append(np.flatnonzero(keep))
                parents.append(np.stack([px[keep], py[keep], pz[keep]], axis=1))
                weights.append(w[keep])
    return np.concatenate(rows), np.concatenate(parents), np.concatenate(weights)


def _blend(index: np.ndarray, held: np.ndarray) -> tuple[Any, np.ndarray, np.ndarray]:
    """The trilinear blend from the coarse lattice's nodes to these, per unknown (3n x 3m, on the
    card), with the held nodes' rows empty; and the coarse nodes' lattice index."""
    import cupy as cp
    import cupyx.scipy.sparse as csp

    rows, parents, weights = _parents(index)
    free = ~held[rows]
    rows, parents, weights = rows[free], parents[free], weights[free]
    coarse, column = np.unique(parents, axis=0, return_inverse=True)
    column = column.ravel()
    r = np.concatenate([3 * rows + d for d in range(3)])
    c = np.concatenate([3 * column + d for d in range(3)])
    w = np.concatenate([weights] * 3)
    p = csp.coo_matrix(
        (cp.asarray(w, cp.float32), (cp.asarray(r), cp.asarray(c))),
        shape=(3 * len(index), 3 * len(coarse)),
    ).tocsr()
    p.sum_duplicates()
    return p, coarse, column


def csr_of(k: Any, held_dofs: Any) -> Any:
    """Warp's 3x3-block matrix as the card's CSR, without leaving the card - the held unknowns'
    rows and columns cleared and a one on their diagonal, as Warp's own projection leaves them."""
    import cupy as cp
    import cupyx.scipy.sparse as csp

    nnz = int(k.nnz_sync()) if hasattr(k, "nnz_sync") else int(k.nnz)
    nrow = int(k.nrow)
    offsets = cp.asarray(k.offsets)[: nrow + 1].astype(cp.int32)
    columns = cp.asarray(k.columns)[:nnz].astype(cp.int32)
    counts = offsets[1:] - offsets[:-1]
    # Block b of block row r lands, for its row i and column j, at
    # 9 offsets[r] + 3 i counts[r] + 3 (b - offsets[r]) + j.
    block_row = cp.searchsorted(offsets[1:], cp.arange(nnz, dtype=cp.int32), side="right")
    block_row = block_row.astype(cp.int32)
    base = 9 * offsets[block_row] + 3 * (cp.arange(nnz, dtype=cp.int32) - offsets[block_row])
    step = 3 * counts[block_row]
    data = cp.empty(9 * nnz, cp.float32)
    indices = cp.empty(9 * nnz, cp.int32)
    values = cp.asarray(k.values)[:nnz].reshape(nnz, 3, 3)
    held_block = held_dofs.reshape(-1, 3)[:, 0]
    cut = held_block[block_row] | held_block[columns]
    diagonal = block_row == columns
    for i in range(3):
        for j in range(3):
            at = base + i * step + j
            v = cp.where(cut, cp.float32(0.0), values[:, i, j].astype(cp.float32))
            if i == j:
                v = cp.where(cut & diagonal, cp.float32(1.0), v)
            data[at] = v
            indices[at] = 3 * columns + j
    del base, step, block_row, cut, diagonal
    rows3 = cp.arange(3 * nrow, dtype=cp.int32)
    indptr = cp.empty(3 * nrow + 1, cp.int32)
    indptr[:-1] = 9 * offsets[rows3 // 3] + (rows3 % 3) * 3 * counts[rows3 // 3]
    indptr[-1] = 9 * nnz
    out = csp.csr_matrix((data, indices, indptr), shape=(3 * nrow, 3 * nrow))
    out.has_sorted_indices = False
    out.sort_indices()
    return out


class Level:
    def __init__(self, a: Any, p: Any | None) -> None:
        import cupy as cp

        self.a = a
        self.p = p
        self.r = p.T.tocsr() if p is not None else None
        diag = a.diagonal()
        diag = cp.where(cp.abs(diag) > 0, diag, 1.0).astype(cp.float32)
        self.dinv = (1.0 / diag).astype(cp.float32)
        self.top = self._largest()

    def _largest(self, steps: int = 12) -> float:
        import cupy as cp

        x = cp.random.default_rng(7).standard_normal(self.a.shape[0], dtype=cp.float32)
        top = 1.0
        for _ in range(steps):
            y = self.dinv * (self.a @ x)
            top = float(cp.linalg.norm(y) / max(float(cp.linalg.norm(x)), 1e-30))
            x = y / max(top, 1e-30)
        return top

    def smooth(self, x: Any, b: Any) -> Any:
        """``DEGREE`` steps of Chebyshev on ``a x = b`` from ``x``."""
        lo, hi = LOW * self.top, HIGH * self.top
        theta, delta = 0.5 * (hi + lo), 0.5 * (hi - lo)
        sigma = theta / delta
        rho = 1.0 / sigma
        r = b - self.a @ x
        d = self.dinv * r / theta
        x = x + d
        for _ in range(DEGREE - 1):
            r = r - self.a @ d
            rho_new = 1.0 / (2.0 * sigma - rho)
            d = rho_new * rho * d + (2.0 * rho_new / delta) * (self.dinv * r)
            x = x + d
            rho = rho_new
        return x


class Hierarchy:
    """The lattices from the voxel model's nodes down to one small enough to solve outright."""

    def __init__(self, nodes: np.ndarray, corner0: np.ndarray, spacing: float, held: np.ndarray):
        index = np.rint((nodes - corner0) / spacing).astype(np.int64)
        self.n = len(nodes)
        self.held_nodes = held.astype(bool)
        self.blends: list[Any] = []
        held_now = self.held_nodes
        while 3 * len(index) > COARSEST_DOFS and len(self.blends) < 8:
            p, coarse, _ = _blend(index, held_now)
            self.blends.append(p)
            index = coarse
            held_now = np.zeros(len(index), bool)
        self.levels: list[Level] = []
        self.chol = None
        self.seconds = 0.0
        self.trace = False

    def setup(self, k: Any) -> None:
        """The coarse matrices for a new stiffness (Warp's matrix, the held rows not yet
        cleared)."""
        import cupy as cp

        t0 = time.perf_counter()
        pool = cp.get_default_memory_pool()
        # The last stiffness's matrices go first, and every block the card lent is handed
        # back after: Warp shares the card, and a card that runs out pages to the host - ten times
        # slower.
        self.levels, self.chol, self.last = [], None, None
        pool.free_all_blocks()
        held = cp.asarray(np.repeat(self.held_nodes, 3))
        a = csr_of(k, held)
        for p in self.blends:
            level = Level(a, p)
            self.levels.append(level)
            ap = a @ p
            a = (level.r @ ap).tocsr()
            del ap
            a.sum_duplicates()
            pool.free_all_blocks()
        dense = a.toarray().astype(cp.float64)
        empty = cp.abs(cp.diag(dense)) < 1e-30
        dense[empty, empty] = 1.0
        self.chol = cp.linalg.cholesky(dense)
        del dense
        self.last = Level(a, None)
        pool.free_all_blocks()
        cp.cuda.Device().synchronize()
        self.seconds = time.perf_counter() - t0

    def _coarsest(self, b: Any) -> Any:
        import cupy as cp
        from cupyx.scipy.linalg import solve_triangular

        y = solve_triangular(self.chol, b.astype(cp.float64), lower=True)
        return solve_triangular(self.chol.T, y, lower=False).astype(cp.float32)

    def cycle(self, b: Any, depth: int = 0) -> Any:
        import cupy as cp

        if depth == len(self.levels):
            return self._coarsest(b)
        level = self.levels[depth]
        x = level.smooth(cp.zeros_like(b), b)
        r = b - level.a @ x
        x = x + level.p @ self.cycle(level.r @ r, depth + 1)
        return level.smooth(x, b)

    def solve(
        self, rhs: np.ndarray, start: np.ndarray | None = None, tol: float = 1e-6, most: int = 400
    ) -> tuple[np.ndarray, int, float]:
        """``K x = rhs`` with the held unknowns at zero: (x, iterations, relative residual)."""
        import cupy as cp

        held = cp.asarray(np.repeat(self.held_nodes, 3))
        a = self.levels[0].a if self.levels else self.last.a
        b = cp.asarray(rhs, cp.float32)
        b[held] = 0.0
        x = cp.zeros_like(b) if start is None else cp.asarray(start, cp.float32)
        x[held] = 0.0
        r = b - a @ x
        norm_b = max(float(cp.linalg.norm(b)), 1e-30)
        z = self.cycle(r)
        p = z.copy()
        rz = float(cp.dot(r.astype(cp.float64), z.astype(cp.float64)))
        its = 0
        res = float(cp.linalg.norm(r)) / norm_b
        while res > tol and its < most:
            q = a @ p
            alpha = rz / float(cp.dot(p.astype(cp.float64), q.astype(cp.float64)))
            x += np.float32(alpha) * p
            r -= np.float32(alpha) * q
            its += 1
            res = float(cp.linalg.norm(r)) / norm_b
            if self.trace and its % 10 == 0:
                print(f"    mg it {its}: residual {res:.2e}", flush=True)
            if res <= tol:
                break
            z = self.cycle(r)
            rz_new = float(cp.dot(r.astype(cp.float64), z.astype(cp.float64)))
            p = z + np.float32(rz_new / rz) * p
            rz = rz_new
        return cp.asnumpy(x).astype(np.float64), its, res
