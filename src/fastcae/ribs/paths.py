"""Load paths: where the metal wants to go when nothing says what shape it must take.

The rib library only offers shapes someone thought of - planes through or tangent to an axis - so a
sizing over it can only rank them. Here every cube of the design volumes has a density of its own
and the loads place the metal: a free density optimisation on the voxel model, with nothing but
the part, the volumes, the deck and the objective. What it grows is the load path; ribs are laid
along it afterwards, under the production rules.

**The model** is the part and the design volumes as cubes (8 mm): the part's cubes are metal, each
design cube as stiff as its density says, ``E_MIN + (1 - E_MIN) x^p``, the density smoothed over a
cube and a half so a path grows as members rather than specks. The deck holds what it holds; each
non-zero component of each bearing load is spread over its seat's nodes.

**The objective** is the design's own - J, as smooth as a gradient needs it:

- the gear mesh's **robust lead** in µm over 10 µm: ``fw sqrt(L² + (b |p|)²)``, where ``p`` is
  each load part's lead, ``L`` their sum (the deck's), ``b`` the load band - agenticCAE's measured
  form of the median over the band;
- the **largest displacement** as a smooth maximum (the P-norm of the nodes' displacements), over
  the target's on the same model.

Stress is left to the solve of the design's own CAD.

**The solve**: cuDSS, every load part as a right-hand side on one factorisation, and the two
adjoints. **The step**: MMA, the metal held to the budget. **Deflation**: a run may be pushed away
from runs before it - a penalty on the metal it puts where they put theirs - so each finds a
different load path; the penalty's weight is the run's own setting, and what the push cost is
measured.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import scipy.sparse as sp
from scipy.spatial import cKDTree

from ..designs import objective
from ..gpu import release
from ..space.physics import E_DEFAULT, NU_DEFAULT, _surface_points
from ..space.physics import _solve as _cg_solve
from . import sizing

if TYPE_CHECKING:
    from ..extract import Extraction
    from ..project import Project
    from ..volumes.volume import Volume

Say = Callable[[str], None]

E_MIN = 1e-3
FILTER_CELLS = 1.6
"""The density is smoothed over this many cubes' radius."""
P_NORM = 8
"""The smooth maximum of the displacements: their P-norm."""
WORST_NORM = 12
"""The smooth maximum over the load cases a design must hold up under (:meth:`Model.hold_across`):
their P-norm. Higher than the displacements' because there are a dozen cases rather than a hundred
thousand nodes, and a design sized against a hard worst case chatters between whichever case is
worst this step."""
CG_TOL = 1e-7
MULTIGRID_TOL = 1e-6
"""The multigrid solve stops at this residual, relative: the card's single precision holds little
more."""
DEVICE_LIMIT = "3GiB"
"""The card memory the voxel model's factor may take; the rest waits in host memory."""


class Model:
    """The part, the design volumes and the deck on the voxel model, ready to be solved for any
    densities of the design cubes."""

    def __init__(
        self,
        project: Project,
        extraction: Extraction,
        setup: Any,
        volumes: list[Volume],
        mix: Any,
        cell_mm: float = sizing.CELL_MM,
        say: Say = print,
        solid: np.ndarray | None = None,
        design_cells: np.ndarray | None = None,
    ) -> None:
        t0 = time.perf_counter()
        self.say = say
        grid, own = sizing.part_grid(extraction, cell_mm)
        # Another shape's metal on the same grid - the target's, to measure against - when given.
        solid = own if solid is None else solid
        self.grid, self.solid = grid, solid
        origin = np.asarray(grid.origin)
        if design_cells is not None:
            # The design cubes given - a rib network's, say - less any that are metal already.
            keep = ~solid[design_cells[:, 0], design_cells[:, 1], design_cells[:, 2]]
            design = np.unique(design_cells[keep], axis=0)
        else:
            # Design cubes: not metal, centre inside a design volume.
            free = np.argwhere(~solid)
            centres = origin + free * cell_mm
            inside = np.zeros(len(free), bool)
            for v in volumes:
                lo, hi = _box_of(v)
                near = np.all((centres >= lo - cell_mm) & (centres <= hi + cell_mm), axis=1)
                idx = np.flatnonzero(near)
                if len(idx):
                    inside[idx] |= v.contains(centres[idx])
            design = free[inside]
        metal = np.argwhere(solid)
        self.cells = np.concatenate([metal, design]).astype(np.int32)
        self.n_metal, self.n_design = len(metal), len(design)
        self.cell_volume = cell_mm**3
        material = next(iter(setup.materials), None)
        young = float(material.young) if material else E_DEFAULT
        poisson = float(material.poisson) if material else NU_DEFAULT
        self.lame = (
            young * poisson / ((1 + poisson) * (1 - 2 * poisson)),
            young / (2 * (1 + poisson)),
        )
        self.structure = sizing._Structure(self.cells, grid, self.lame)
        nodes = self.structure.nodes
        self.n_nodes = len(nodes)
        # The deck's supports; each non-zero component of each bearing load, spread over its seat.
        fixed, _ = sizing.boundary(extraction, setup, mix, self.structure)
        self.fixed = np.zeros(self.n_nodes, bool)
        self.fixed[fixed] = True
        groups = (extraction.anchoring or {}).get("groups", {})
        tess = extraction.tess
        # The part's own nodes - corners of its metal cubes. A seat's loads and the gear mesh's read
        # stand on these alone, and the largest displacement is read on them: a node only design
        # cubes hold floats in near-void wherever the design has no metal, and a load or a read
        # on it measures the void, not the part.
        self.metal_nodes = np.zeros(self.n_nodes, bool)
        st = self.structure
        for a in (0, 1):
            for b in (0, 1):
                for c in (0, 1):
                    at = st.find(st.corner0 + (metal + np.array([a, b, c])) * st.big)
                    self.metal_nodes[at[at >= 0]] = True
        on_metal = np.flatnonzero(self.metal_nodes)
        tree = cKDTree(nodes[on_metal])

        def seat(group: str) -> np.ndarray:
            pts = _surface_points(tess, groups[group]["faces"])
            ids = [np.asarray(i, np.int64) for i in tree.query_ball_point(pts, 0.9 * cell_mm)]
            found = np.unique(np.concatenate([*ids, np.empty(0, np.int64)]))
            return on_metal[found] if len(found) else on_metal[np.unique(tree.query(pts)[1])]

        self.parts: list[tuple[str, int, float]] = []
        self.rhs = []
        self.seats: dict[str, np.ndarray] = {}
        for case in mix.cases:
            for g, vector in case.forces.items():
                if g not in groups:
                    continue
                ids = seat(g)
                self.seats[g] = ids
                for c in range(3):
                    if abs(vector[c]) > 0.0:
                        f = np.zeros((self.n_nodes, 3))
                        f[ids, c] = vector[c] / len(ids)
                        self.parts.append((g, c, float(vector[c])))
                        self.rhs.append(f.ravel())
        # The gear mesh's lead as a linear read of the displacements, for every mesh ranked on.
        cfg = objective.config(project)
        if cfg is None:
            raise RuntimeError("the project has no gear mesh data: objective/gearmesh.json")
        for name in {b for s in cfg["shafts"].values() for b in s["bores"]}:
            if name not in self.seats and name in groups:
                self.seats[name] = seat(name)
        ranked = [n for n, m in cfg["meshes"].items() if m.get("face_width_mm")]
        if not ranked:
            raise RuntimeError("no gear mesh has a face width to rank on")
        self.mesh_name = ranked[0]
        mesh = cfg["meshes"][self.mesh_name]
        self.face_width = float(mesh["face_width_mm"])
        self.lead = self._lead_vector(cfg, mesh)
        # Every mesh's lead, to read beside the ranked one (a mesh without a face width is read in
        # radians only).
        self.leads_all = {
            name: self._lead_vector(cfg, m)
            for name, m in cfg["meshes"].items()
            if all(b in self.seats for s in m["shafts"] for b in cfg["shafts"][s]["bores"])
        }
        self.deck_rhs = np.sum(self.rhs, axis=0) if self.rhs else np.zeros(3 * self.n_nodes)
        self.bands: list[tuple[str, np.ndarray]] = []
        """Load cases the design must hold up under, each a scale on every load part - set by
        :meth:`hold_across`. Empty means the one case the mix gave."""
        # The density filter over the design cubes.
        design_centres = design.astype(float)
        h_tree = cKDTree(design_centres)
        pairs = h_tree.query_pairs(FILTER_CELLS, output_type="ndarray")
        i = np.concatenate([pairs[:, 0], pairs[:, 1], np.arange(self.n_design)])
        j = np.concatenate([pairs[:, 1], pairs[:, 0], np.arange(self.n_design)])
        dist = np.linalg.norm(design_centres[i] - design_centres[j], axis=1)
        w = np.maximum(FILTER_CELLS - dist, 0.0)
        h = sp.csr_matrix((w, (i, j)), shape=(self.n_design, self.n_design))
        self.filter = sp.diags(1.0 / np.asarray(h.sum(axis=1)).ravel()) @ h
        # Which of the structure's cells is which of ours: Warp orders its cells its own way.
        self.free_dofs = np.flatnonzero(~np.repeat(self.fixed, 3))
        # The coarser lattices for multigrid, made once: they depend on where the nodes are and
        # which the deck holds, not on the stiffness. Without CuPy, Warp's diagonal CG instead.
        self.hierarchy = None
        self._ready: Any = None
        self.iterations: list[int] = []
        try:
            from .multigrid import Hierarchy

            st = self.structure
            self.hierarchy = Hierarchy(st.nodes, st.corner0, st.big, self.fixed)
        except ImportError:
            pass
        say(
            f"voxel model: {self.n_metal:,} cubes of the part, {self.n_design:,} of the design "
            f"volumes ({self.n_design * self.cell_volume / 1e6:.1f} L), {len(self.parts)} load "
            f"parts, {3 * self.n_nodes:,} unknowns; ranked on {self.mesh_name} "
            f"({time.perf_counter() - t0:.0f} s)"
        )

    def _lead_vector(self, cfg: dict[str, Any], mesh: dict[str, Any]) -> np.ndarray:
        """The mesh's lead (radians) as ``g · u``, a bore's motion the mean of its seat's nodes."""
        g = np.zeros((self.n_nodes, 3))
        p0, p1 = (np.asarray(x, float) for x in mesh["axes_xy"])
        n = (p1 - p0) / np.linalg.norm(p1 - p0)
        t = np.array([-n[1], n[0], 0.0])
        for sign, shaft in zip((1.0, -1.0), mesh["shafts"], strict=True):
            a, b = cfg["shafts"][shaft]["bores"]
            z1, z2 = cfg["shafts"][shaft]["z_mm"]
            for bore, s_bore in ((b, 1.0), (a, -1.0)):
                ids = self.seats[bore]
                # skew = (d_b - d_a) / (z2 - z1); lead = t · (skew_A - skew_C)
                g[ids] += sign * s_bore * t / (z2 - z1) / len(ids)
        return g.ravel()

    # -- solving ------------------------------------------------------------------------------

    def stiffness(self, x_filtered: np.ndarray, p: float) -> np.ndarray:
        s = np.ones(len(self.cells))
        s[self.n_metal :] = E_MIN + (1.0 - E_MIN) * x_filtered**p
        return s

    def solve(
        self,
        stiffness: np.ndarray,
        rhs: np.ndarray,
        then: Callable[[np.ndarray], np.ndarray] | None = None,
    ) -> tuple[np.ndarray, np.ndarray | None]:
        """Every right-hand side on one factorisation: (3n, m) displacements - and, when ``then``
        is given, the right-hand sides it makes of them solved on the same factor."""
        import cupy as cp
        import cupyx.scipy.sparse as csp
        from nvmath.sparse.advanced import (
            DirectSolver,
            DirectSolverMatrixType,
            ExecutionCUDA,
            HybridMemoryModeOptions,
        )

        from ..gpu import release
        from ..simulate.solve import _mtlayer

        k = self.structure.assemble(stiffness)
        k_csr = _to_csr(k, 3 * self.n_nodes)
        free = self.free_dofs
        k_ff = k_csr[free][:, free].tocsr()
        k_ff.sort_indices()
        release()
        a = csp.csr_matrix(k_ff)
        b = cp.asfortranarray(cp.asarray(rhs[free]))
        options = {
            "sparse_system_type": DirectSolverMatrixType.SPD,
            "multithreading_lib": _mtlayer(),
        }
        execution = ExecutionCUDA(
            hybrid_memory_mode_options=HybridMemoryModeOptions(
                hybrid_memory_mode=True, hybrid_device_memory_limit=DEVICE_LIMIT
            )
        )
        second = None
        try:
            with DirectSolver(a, b, options=options, execution=execution) as solver:
                solver.plan()
                solver.factorize()
                x = cp.asnumpy(solver.solve()).reshape(len(free), -1)
                first = np.zeros((3 * self.n_nodes, rhs.shape[1]))
                first[free] = x
                if then is not None:
                    more = then(first)
                    # The factor keeps its right-hand sides' shape: the rest are zero columns.
                    padded = np.zeros((len(free), rhs.shape[1]))
                    padded[:, : more.shape[1]] = more[free]
                    solver.reset_operands(b=cp.asfortranarray(cp.asarray(padded)))
                    y = cp.asnumpy(solver.solve()).reshape(len(free), -1)[:, : more.shape[1]]
                    second = np.zeros((3 * self.n_nodes, more.shape[1]))
                    second[free] = y
        finally:
            a = b = None
            release()
        return first, second

    def cg(self, k: Any, rhs: np.ndarray, start: np.ndarray | None) -> np.ndarray:
        """``K x = rhs`` by conjugate gradients on the card, from ``start``: (3n,) displacements,
        the held nodes at zero - preconditioned by multigrid, its coarse matrices made again when
        ``k`` is a new stiffness. Memory is the matrices' own - nothing grows with the load's
        parts."""
        if self.hierarchy is not None:
            if self._ready is not k:
                self._ready = None
                self.hierarchy.setup(k)
                self._ready = k
            x, its, _ = self.hierarchy.solve(rhs, start, tol=MULTIGRID_TOL)
            self.iterations.append(its)
            return x
        x, _, _, _ = _cg_solve(
            k,
            rhs.reshape(-1, 3),
            np.flatnonzero(self.fixed),
            None,
            None if start is None else start.reshape(-1, 3),
            tol=CG_TOL,
        )
        return x.ravel()

    def evaluate(self, stiffness: np.ndarray) -> dict[str, Any]:
        """The objective's terms for a stiffness, by two solves: every part's lead from the lead's
        adjoint (``lead_i = λᵀ f_i``), and the deck's displacements."""
        k = self.structure.assemble(stiffness)
        lam = self.cg(k, self.lead, None)
        u = self.cg(k, self.deck_rhs, None)
        return self.terms(lam, u)

    def hold_across(self, cases: list[tuple[str, dict[str, list[float]]]]) -> None:
        """Ask for a design that holds up under every one of these load cases, not only the mix's.

        Each is a name and the force through every loaded group, as a study's load cases give
        them; they are lined up here against the parts this
        model was built with, because only the model knows what order it put them in. A load the
        model does not carry is ignored, and one the case leaves out is scaled away.

        The misalignment the objective reads becomes the worst of the cases, smoothly
        (:data:`WORST_NORM`). It costs **nothing**: every part's lead already comes from the one
        adjoint solve, so a case is a re-weighted sum of numbers the step has in hand, and the
        derivative of the worst is one vector however many cases there are. Only the deflection
        term stays on the mix's own case - that would need a solve a case, and it is the
        misalignment that a turned load ruins.
        """
        self.bands = [
            (
                name,
                np.array(
                    [
                        forces.get(g, [0.0, 0.0, 0.0])[c] / value if value else 0.0
                        for g, c, value in self.parts
                    ]
                ),
            )
            for name, forces in cases
        ]

    def _worst(self, leads: np.ndarray) -> tuple[float, np.ndarray, list[float]]:
        """The misalignment to answer for, and its derivative by each part's lead.

        With no band it is the deck's own robust misalignment. With one it is the smooth maximum
        over the cases, which is differentiable where a plain maximum is not - a design sized
        against a hard worst case chatters between whichever case is worst this step.
        """
        scale = self.face_width * 1e3
        bands = self.bands or [("deck", np.ones(len(leads)))]
        each, slopes = [], []
        for _, v in bands:
            scaled = v * leads
            total = float(scaled.sum())
            root = max(float(np.sqrt(total**2 + objective.BAND**2 * float(scaled @ scaled))), 1e-30)
            each.append(scale * root)
            slopes.append(scale * v * (total + objective.BAND**2 * scaled) / root)
        if len(each) == 1:
            return each[0], slopes[0], each
        got = np.array(each)
        worst = float(np.sum(got**WORST_NORM) ** (1.0 / WORST_NORM))
        share = (got / max(worst, 1e-30)) ** (WORST_NORM - 1)
        return worst, np.sum([s * g for s, g in zip(share, slopes, strict=True)], axis=0), each

    def terms(self, lam: np.ndarray, u: np.ndarray) -> dict[str, Any]:
        leads = np.array([float(lam @ f) for f in self.rhs])
        total = float(leads.sum())
        scale = self.face_width * 1e3
        robust, _, each = self._worst(leads)
        deck = u.reshape(-1, 3)
        size = np.linalg.norm(deck, axis=1) * self.metal_nodes
        return {
            "leads": leads,
            "total": total,
            "robust_um": robust,
            "per_case_um": each,
            "nominal_um": abs(total) * scale,
            "smooth_max_mm": float(np.sum(size**P_NORM) ** (1.0 / P_NORM)),
            "largest_mm": float(size.max()),
            "deck": deck,
            "size": size,
        }

    def gradient(
        self,
        stiffness: np.ndarray,
        lead_weight: float,
        reference: Reference,
        warm: dict[str, np.ndarray],
        stiffness_only: bool = False,
    ) -> tuple[dict[str, Any], np.ndarray, dict[str, float]]:
        """The objective at a stiffness, and its derivative by every cell's stiffness, by four
        solves, each from where ``warm`` says the last step left it: the lead's adjoint (every
        part's lead is λᵀ f_i), the deck's displacements, the parts weighted as the robust lead's
        gradient asks, and the smooth maximum's adjoint."""
        k = self.structure.assemble(stiffness)
        # Two of the four solves exist only for the gear mesh's lead. A run that does not answer for
        # the lead - one asking only how the housing bends - must not pay for them: they were being
        # solved and then multiplied by nothing, which is half the work of every step.
        wants_lead = lead_weight > 0.0 and not stiffness_only
        deck = self.cg(k, self.deck_rhs, warm.get("deck"))
        if stiffness_only:
            # **One solve a step.** Strain energy under the deck's own case is self-adjoint - its
            # derivative by a cell's stiffness is that cell's own energy - so there is no adjoint
            # to solve for. Everything else here needs a second solve because it asks about one
            # place in the housing rather than the whole of it.
            warm.update(deck=deck)
            energy = self.mutual(deck, deck)
            m = {
                "robust_um": float("nan"),
                "smooth_max_mm": float("nan"),
                "largest_mm": float(np.linalg.norm(deck.reshape(-1, 3), axis=1).max()),
                "compliance": float(energy.sum()),
            }
            del k
            release()
            j = m["compliance"] / max(reference.compliance, 1e-30)
            return (
                m,
                -energy / max(reference.compliance, 1e-30),
                {"value": j, "j": j, "j_misalign": 0.0, "j_deflection": j},
            )
        lam_g = self.cg(k, self.lead, warm.get("lam_g")) if wants_lead else np.zeros_like(deck)
        m = self.terms(lam_g, deck)
        if not wants_lead:
            # nothing was measured, so nothing is claimed: a lead of zero would read as perfect
            m["robust_um"] = float("nan")
        leads = m["leads"]
        # d(what we answer for)/d lead_i - one vector however many cases are held, so the solve
        # below is the same single solve whether the design answers for one case or twelve
        _, w, _ = self._worst(leads)
        weighted = (
            self.cg(k, np.stack(self.rhs, axis=1) @ w, warm.get("weighted"))
            if wants_lead
            else lam_g
        )
        smax = m["smooth_max_mm"]
        size = np.maximum(m["size"], 1e-30)
        dmax = (smax ** (1 - P_NORM)) * (size ** (P_NORM - 2))[:, None] * m["deck"]
        lam_h = self.cg(k, dmax.ravel(), warm.get("lam_h"))
        warm.update(lam_g=lam_g, deck=deck, weighted=weighted, lam_h=lam_h)
        del k
        release()
        j_mis = (m["robust_um"] / objective.UM_REF) if wants_lead else 0.0
        j_def = smax / reference.smooth_max_mm
        # dJ/dE_e = -(λ_gᵀ K_e Σ w_i u_i) / UM_REF - (λ_hᵀ K_e u_deck) / ref
        de = -self.mutual(lam_h, deck) / reference.smooth_max_mm
        if wants_lead:
            de = de - lead_weight * self.mutual(lam_g, weighted) / objective.UM_REF
        terms = {
            "value": lead_weight * j_mis + j_def,
            "j": j_mis + j_def,
            "j_misalign": j_mis,
            "j_deflection": j_def,
        }
        return m, de, terms

    def _gradients(self, u: np.ndarray) -> np.ndarray:
        """Each cell's displacement gradient from its eight corners, (cells, 3, 3)."""
        st = self.structure
        corner = np.zeros((len(st.cells), 2, 2, 2), np.int64)
        for a in (0, 1):
            for b in (0, 1):
                for c in (0, 1):
                    at = st.corner0 + (st.cells + np.array([a, b, c])) * st.big
                    corner[:, a, b, c] = np.maximum(st.find(at), 0)
        uc = u.reshape(-1, 3)[corner]
        return (
            np.stack(
                [
                    (uc[:, 1] - uc[:, 0]).mean(axis=(1, 2)),
                    (uc[:, :, 1] - uc[:, :, 0]).mean(axis=(1, 2)),
                    (uc[:, :, :, 1] - uc[:, :, :, 0]).mean(axis=(1, 2)),
                ],
                axis=2,
            )
            / st.big
        )

    def mutual(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """``aᵀ K_e b`` of every cell at full stiffness (one-point, as the sizing reads energy)."""
        ga, gb = self._gradients(a), self._gradients(b)
        ea, eb = 0.5 * (ga + ga.transpose(0, 2, 1)), 0.5 * (gb + gb.transpose(0, 2, 1))
        lam, mu = self.lame
        tr = np.trace(ea, axis1=1, axis2=2) * np.trace(eb, axis1=1, axis2=2)
        return (lam * tr + 2.0 * mu * np.einsum("nij,nij->n", ea, eb)) * self.cell_volume

    # -- measuring ----------------------------------------------------------------------------

    def measure(self, u_parts: np.ndarray) -> dict[str, Any]:
        """The robust lead (µm) and the smooth largest displacement of the parts' displacements.

        Read the same way the sizing reads them, band and all, so a set screened here is screened
        on what it was sized for."""
        leads = self.lead @ u_parts
        total = float(leads.sum())
        scale = self.face_width * 1e3
        robust, _, each = self._worst(leads)
        deck = u_parts.sum(axis=1).reshape(-1, 3)
        size = np.linalg.norm(deck, axis=1) * self.metal_nodes
        smooth_max = float(np.sum(size**P_NORM) ** (1.0 / P_NORM))
        return {
            "leads": leads,
            "total": total,
            "robust_um": robust,
            "per_case_um": each,
            "nominal_um": abs(total) * scale,
            "smooth_max_mm": smooth_max,
            "largest_mm": float(size.max()),
            "deck": deck,
            "size": size,
        }


def solid_of(
    extraction: Extraction, vertices: np.ndarray, triangles: np.ndarray, cell_mm: float
) -> np.ndarray:
    """Another closed surface's metal on the part's own grid."""

    class _Tess:
        pass

    class _Shape:
        pass

    grid, _ = sizing.part_grid(extraction, cell_mm)
    t = _Tess()
    t.vertices, t.triangles = vertices, triangles
    other = _Shape()
    other.tess = t
    other_grid, solid = sizing.part_grid(other, cell_mm)  # type: ignore[arg-type]
    if tuple(other_grid.shape) != tuple(grid.shape) or not np.allclose(
        other_grid.origin, grid.origin
    ):
        raise ValueError("the other shape does not share the part's grid")
    return solid


def _box_of(v: Volume) -> tuple[np.ndarray, np.ndarray]:
    corners, _, _ = v.surface()
    return corners.min(axis=0), corners.max(axis=0)


def _to_csr(k: Any, n: int) -> sp.csr_matrix:
    """Warp's block matrix as SciPy's."""
    nnz = int(k.nnz_sync()) if hasattr(k, "nnz_sync") else int(k.nnz)
    offsets = k.offsets.numpy()[: k.nrow + 1].astype(np.int64)
    columns = k.columns.numpy()[:nnz].astype(np.int64)
    values = k.values.numpy()[:nnz].astype(np.float64)
    return sp.bsr_matrix((values, columns, offsets), shape=(n, n)).tocsr()


@dataclass
class Reference:
    """What a run is measured against: the target's robust lead and smooth largest displacement on
    the same voxel model."""

    robust_um: float
    smooth_max_mm: float
    compliance: float = 1.0
    """The target's strain energy under the deck's own load case - what a run answering for
    stiffness alone is measured against."""
