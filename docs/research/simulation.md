# Solving thousands of designs

How a generated design becomes solved stress and displacement, fast enough for thousands of designs:
meshing, solvers, GPU solvers, voxel and cut-cell (immersed) methods, what they cost on this
housing, and what speeds each route up. September 2026. No published open-source work does the whole
of it - rule-driven variants of one cast part feeding an open structural surrogate; every piece
exists separately. Runtimes marked *(est.)* are estimates, not published benchmarks.

## Two routes from a design to a solution

Every fastcae design exists as a signed distance field on a regular grid (3 mm at preview, 1.5 mm
at full) and a contoured triangle surface. From there:

| | A. Mesh, then solve | C. Solve directly on the grid, on a GPU |
|---|---|---|
| What happens | grid → surface → solid elements (quadratic tets, TET10/C3D10) → solver | each cell of the design's grid becomes an element; no mesh |
| Can it fail? | meshing sometimes (fTetWild succeeds on about 98.7% of a hard test set) | no |
| Time per design, measured here | mesh 8-14 s straight from the field (compiled CGAL), solve 10-13 s (cuDSS on the GPU); fTetWild took 26-103 min, Code_Aster 57 s | 9-109 s on the laptop GPU (voxels, cut cells) |
| Bearing tilt, misalignment, deflection | accurate - every TET10 solver agrees to 10⁻⁸ | measured 6-17 % off on the worst tilt, up to 36 % on the gear-mesh lead |
| Natural frequencies | accurate | close |
| Stress at fillets and rib roots | accurate with a fine TET10 mesh | unreliable: the grid's stair-step boundary distorts surface stress. A 99.9th-percentile stress fares better than the peak - cut cells measured within 0.4 % - but is still biased |
| Memory, measured here | cuDSS 5.2 GB of the 8 GB card at 1.06 M unknowns | 7 M voxel unknowns (4 mm) and quadratic cut cells ran out of the card |
| Libraries | meshing: CGAL (from the field), gmsh, fTetWild (pytetwild), MMG, TetGen; solvers: cuDSS, PETSc, Code_Aster, FEniCSx, CalculiX | NVIDIA Warp fem (Windows), JAX-FEM (Linux/WSL), torch-fem; commercial: Ansys Discovery, Intact in nTop |

A middle route keeps the grid but computes the cells the surface cuts properly - **cut-cell
(immersed) methods**, below. It restores most of the stress accuracy at surfaces without meshing,
and is research-grade.

## Measured on this housing (agenticCAE)

The earlier agenticCAE project solved this housing ([agenticcae.md](agenticcae.md)); its
`handbook/research/16-implicit-rib-variants.md` measures both routes:

| | Unknowns (DOF) | Solve: Code_Aster `MACRO_ELAS_MULT`, 55 unit load cases, one core | Stress quality |
|---|---|---|---|
| Linear tets (C3D4): 57,240 nodes, 202,496 tets | 0.19 M | 138 s (55 × `MECA_STATIQUE`: 385 s; CalculiX 55 × `*STEP`: 915 s) | linear tets are 25-35% too stiff on this housing - not usable |
| **Quadratic tets (C3D10)** | **1.27 M** | **1,139 s** (CalculiX exhausts 7.8 GB) | good |
| Grid, 20 mm (29,013 active cells, 83% cut) | 0.13 M | not measured | too coarse |
| Grid, 10 mm (182,504 active cells, 61% cut) | 0.72 M | not measured | too coarse |
| Grid, 5 mm (1,239,208 active cells, 36% cut, 1,464k nodes) | 4.39 M | not measured | stair-step unless cut-cell |
| Grid, 4 mm / 3 mm (extrapolated from 5 mm) | about 8.6 M / 20 M | not measured | same |

agenticCAE's conclusion: *"The fixed grid costs more DOF than the body-fitted mesh and spends them
worse."* The housing fills about 10.4% of its bounding box and its median wall is 27.6 mm, so a
Cartesian grid spends most of its resolution straddling surfaces. At 10 mm the grid needs 4× the DOF
of the linear-tet mesh with 61% of its cells cut; at 5 mm, 4.39 M DOF is beyond `scipy_splu`. (The
inside test ran on a tessellation 0.26% low in volume.) A GPU still handles 9-20 M unknowns with
matrix-free multigrid, but that is 7-16× the work of the TET10 mesh, for worse stress. A rough
estimate from the part's volume alone (about 121,000 cm³) - 4.5 M cells and 13.5 M unknowns at 3 mm,
1.9 M and 5.7 M at 4 mm, 1 M and 2.9 M at 5 mm - undercounts: cut cells add nodes, which is why the
measured 5 mm grid has 4.39 M.

Also measured there: the old mesh path (B-rep → OCC tessellation → STL → gmsh volume, MeshSizeMax 20
mm) was non-deterministic - identical CAD gave 57,240 nodes on one run and 57,372 on another; q_min
0.00788, 67 elements below q 0.1. gmsh alone cannot mesh the STEP (`Impossible to mesh periodic
surface 2`; `occ.healShapes()` fails; surface meshing at 6 mm ran past 10 minutes). A 1 mm dense
grid is not workable (an R8 fillet needs ≲ 1 mm voxels to be resolved to a few voxels across its
radius); a narrow band is.

## Measured here: every candidate against Code_Aster

Design #7 of campaign `w4zf5` and agenticCAE's design e56235, each meshed as TET10 at 20 mm (about
1.06-1.1 M unknowns), agenticCAE's load case, the 25 bolt positions held, agenticCAE's metrics - on
this workstation. Full tables: [../../bench/solvers/RESULTS.md](../../bench/solvers/RESULTS.md).

| Design #7, 1.06 M unknowns | Total | Against Code_Aster |
|---|---:|---|
| cuDSS, sparse Cholesky, GPU | 13 s | 3·10⁻¹⁰, 5.2 GB of the card |
| PETSc CG + GAMG, GPU | 35 s | 2·10⁻⁹ |
| CG + PyAMG levels, CuPy V-cycles, GPU | 51 s | 1·10⁻⁹ |
| Code_Aster 18, MUMPS block low-rank, one core | 57 s | the reference |
| CHOLMOD, CPU | 61 s | 3·10⁻¹⁰ |
| JAX-FEM, autodiff assembly + cuDSS | 112 s | 3·10⁻¹⁰ |
| FEniCSx P2, its own assembly, CG + GAMG, one core | 253 s | 7·10⁻⁸ |
| Voxel grid, Warp, 6 mm / 5 mm (2.3 M / 3.8 M unknowns) | 51 s / 109 s | worst tilt +14% / +17% |
| Cut cells, Warp + cuDSS, linear, 12 mm / 10 mm | 9 s / 43 s | worst tilt -6%, gear-mesh lead -17 to -19%, p99.9 within 0.4% |

- On one mesh every TET10 solver gives the same answer; the difference is time. cuDSS is the
  fastest and exact; keeping part of its factor in host memory it holds 1.49 M unknowns on the card.
  PETSc is not used; a design past that is proposed for Code_Aster. Why each solver got its result,
  who uses the CPU and who the GPU, and what not choosing the others gives up:
  [solver-choice.md](solver-choice.md).
- The voxel grid moves further from the answer as it refines - its supports and loads land on the
  grid nodes nearest the surface. Cut cells get stress right but their linear cells are too stiff in
  bending; quadratic cells need a multigrid solver on the grid before they fit the card.
- The supports matter more than the solver: agenticCAE's couplings, which let each bolt hole turn
  about its bolt, give 2.07' on the worst bore where clamping the holes gives 1.25'. With its
  couplings, on its own mesh, this setup reproduces agenticCAE's recorded tilts within 10% and its
  gear-mesh lead within 2.4%; the GPU solves the couplings to Code_Aster's answer at 2·10⁻¹⁰.
- The design took 33 minutes to build and 31-103 minutes to mesh with fTetWild - and both can be fast.
  Built with the grid's distance on the GPU it takes 79 s and is the same design; meshed straight
  from its field by CGAL, 46 s through Python and 4-14 s compiled, no slivers; solved by cuDSS, within
  2.3 % of the slow route everywhere. About 2 minutes a design, end to end. Every approach tried, and
  why each won or failed: [design-to-solution.md](design-to-solution.md).

## What a "GPU solver" means

The solver does not care how the elements were made. Either way, the finite element method ends with
one giant set of linear equations, K·u = f - millions of unknowns saying how far each point moves.
There are two ways to solve it:

1. **Direct**, like Gaussian elimination: factorise K once. Exact and robust, but memory-hungry -
   agenticCAE needed about 10 GB per design. On CPU: MUMPS (in Code_Aster), PARDISO or PaStiX (in
   CalculiX). One factorisation serves many load cases at almost no extra cost. On GPU: NVIDIA cuDSS
   ([nvmath-python API](https://docs.nvidia.com/cuda/nvmath-python/latest/host-apis/sparse/generated/nvmath.sparse.advanced.direct_solver.html)),
   adopted by [COMSOL 6.4 (November 2025)](https://www.comsol.com/blogs/faster-simulation-with-nvidia-gpu-support-for-comsolmph)
   and OptiStruct, which accepts SciPy CSR matrices - only if the factorisation fits in GPU memory:
   measured here, about 1.1 M unknowns wholly on the 8 GB card, 1.49 M with part of the factor in host
   memory.
2. **Iterative**: start from a guess and improve it step by step - conjugate gradient with a
   preconditioner, usually multigrid. Little memory, very fast on GPUs. On a regular grid every cell
   is identical, so the GPU never stores K at all: it applies it on the fly ("matrix-free"). This is
   how GPU topology optimisation handles 10-100 M cells.

**The iterative method works on meshes too**, TET10 included. On an irregular tet mesh it needs a
stronger preconditioner - algebraic multigrid (AMG) - to converge quickly, and still uses little
memory:
- Code_Aster has iterative solving built in (PETSc, with preconditioners such as GAMG or hypre
  BoomerAMG, or `LDLT_SP`, a single-precision factorisation used as a preconditioner). agenticCAE used
  the direct solver (MUMPS).
- CalculiX has iterative options, less robust.
- On GPU: NVIDIA AMGX (GPU algebraic multigrid for any sparse matrix, mainly Linux), PETSc on GPU
  (Linux; [a blocked GPU AMG path for elasticity](https://arxiv.org/abs/2606.24748), June 2026), cuDSS
  (direct - measured below: a 1.06-1.1 M-unknown TET10 system factors in 5-6 GB of an 8 GB card). Warp
  fem, JAX-FEM and torch-fem also do quadratic tets.

Scale shown by GPU topology optimisation, on regular grids like fastcae's:
[Träff et al., CMAME 2023](https://www.sciencedirect.com/science/article/pii/S0045782523001676)
optimised 65.5 M elements in about 2 h on one GPU; [Aage et al., Nature 2017](https://pubmed.ncbi.nlm.nih.gov/28980645/)
passed a billion voxels. Linear-elastic solves at 10⁷-10⁸ voxels are routine with matrix-free
multigrid.

## Voxel, immersed and GPU FEM on distance-field grids

- **NVIDIA Warp `warp.fem`** ([docs](https://nvidia.github.io/warp/domain_modules/fem.html), Warp 1.12,
  2026). GPU finite elements written in Python. Supports sparse-voxel geometry built from NanoVDB
  (`Nanogrid`, `AdaptiveNanogrid`) as well as tet and hex meshes; installs on Windows. *Fit: high* for
  a GPU voxel path straight from the distance field. The elasticity form and a strong preconditioner
  (multigrid) are ours to write, or to bring in (AMGX).
- **JAX-FEM** ([arXiv 2212.00964](https://arxiv.org/abs/2212.00964), CPC 2023). A 7.7 M-DOF
  linear-elastic model took 523 s on one GPU versus 4,769 s for Abaqus on 24 MPI ranks; includes
  TET10; gives gradients for optimisation. *Fit: medium*: JAX has no native Windows CUDA,
  [WSL2 only](https://docs.jax.dev/en/latest/installation.html).
- **torch-fem** ([GitHub](https://github.com/meyer-nils/torch-fem), active 2025-26). PyTorch solid
  mechanics with autograd sensitivities, quadratic tets included. *Fit: medium*: CUDA works on
  Windows; targets moderate model sizes; the same framework as the surrogate's training.
- **cuDSS** (above). *Fit: high* as a drop-in accelerator where the factorisation fits in GPU memory.
- **PETSc GPU / AMGX**. *Fit: low on Windows*: an HPC/Linux stack; natural under WSL.

| | NVIDIA Warp fem | JAX-FEM | torch-fem |
|---|---|---|---|
| What it is | NVIDIA's Python GPU toolkit, with a finite-element module | FEM written in JAX (Google's GPU and auto-gradient library) | FEM written in PyTorch |
| Windows GPU | yes | no (Linux/WSL only) | yes |
| Element types | tets, hexes, sparse voxel grids; higher order too | includes TET10 | includes quadratic tets |
| Strength | fast on grids; flexible | proven fast (7.7 M unknowns in 523 s on one GPU); gradients | same framework as the model training; gradients |
| Weakness | only simple built-in preconditioners; multigrid is ours to write or add | WSL only | moderate model sizes |
| Fit here | high, for the grid route | medium | medium |

## Cut-cell (immersed) methods

Think of the grid as Lego bricks. A plain voxel solve treats each brick as wholly solid or wholly
empty, so curved surfaces become stair-steps and stress at fillets comes out wrong. A cut-cell solve
keeps the same bricks, but for every brick the true surface cuts through, it integrates over the
solid part only - knowing the exact surface from the distance field, which fastcae already has for
every design.

**Their role:** the middle route. No meshing, so nothing fails, and it runs well on a GPU, yet stress
near surfaces approaches a body-fitted mesh.

**The catches:** very thin solid slivers inside a brick make the equations ill-conditioned, so a
stabilisation ("ghost penalty") is needed; cut bricks cost more to integrate; and on this housing
36-61% of bricks are cut, its walls being thin compared with the grid.

**Methods and libraries:**
- The finite cell method ([Düster 2008](https://www.sciencedirect.com/science/article/abs/pii/S0045782508001163)).
- Shifted Boundary / Gap-SBM elasticity ([2025](https://arxiv.org/html/2508.09613)).
- SBM on distance-field / neural-implicit geometry in 3D elasticity ([Karki et al., July 2025](https://arxiv.org/abs/2507.03087)).
- [ngsxfem](https://github.com/ngsxfem/ngsxfem): CutFEM on level sets, pip install, CPU.
- Research code on FEniCSx.
- Commercial: [Intact.Simulation in nTop](https://intact-solutions.com/intact-simulation-for-ntop/)
  (stress and modal on implicit geometry) and [Ansys Discovery Explore](https://innovationspace.ansys.com/forum/forums/topic/explore-mode-vs-refine-mode/)
  (GPU voxels, with a separate "Refine" mode for fidelity).

**Accuracy verdict:** stair-stepped voxel boundaries produce spurious surface stresses; filtering
only partly fixes them ([Charras & Guldberg 2000](https://pubmed.ncbi.nlm.nih.gov/10653042/); voxel
versus X-FEM/level-set in [Lian et al. 2013](https://link.springer.com/article/10.1007/s00466-012-0723-9)).
Stiffness, displacements and natural frequencies converge fine. Cut-cell and SBM methods recover
boundary accuracy with good quadrature, but fillet peak stress still wants body-fitted quadratic tets.
So: voxel and immersed solves for low fidelity and interactive preview; TET10 for the stress labels -
unless a measured comparison on this part says otherwise.

## Tet meshing

Each tried on design #7 ([design-to-solution.md](design-to-solution.md) has the numbers):

- **fTetWild / pytetwild** ([TOG 2020](https://ar5iv.labs.arxiv.org/html/1908.03581),
  [pytetwild](https://github.com/pyvista/pytetwild): MPL-2.0, Windows wheels). Meshes 98.7% of the
  Thingi10k test set in under 2 min (18.5 s on average), its output within a tolerance envelope of the
  input surface. *Measured here*: 26-103 minutes on the design's surface, whatever it is given - its
  optimisation passes dominate - and decimating its input far enough to matter spoils the part. Robust,
  too slow for 4,000 designs.
- **TetGen** (AGPLv3 [or commercial licence](https://www.wias-berlin.de/software/tetgen/FAQ-license.jsp)).
  Fails to produce a constrained Delaunay mesh on about 8.5% of valid Thingi10k models
  ([Diazzi et al. 2023](https://cims.nyu.edu/gcl/papers/2023-CDT.pdf)). *Measured here*: 4-8 s on a
  cleaned surface, but it refuses one that crosses itself and leaves slivers; AGPL is a problem for a
  hosted product.
- **gmsh**. Its parallel Delaunay kernel (HXT) makes 3 billion tets in 53 s
  ([IJNME 2019](https://arxiv.org/abs/1805.08831)); size fields and second-order elements. *Measured
  here*: re-parametrising a 200,000-triangle surface stalled past 30 minutes; handed the cleaned,
  repaired surface as it is, HXT fills it in 9 s - the fallback route, 73 s for the whole mesh step.
- **MMG `mmg3d -ls`** ([man page](https://www.mankier.com/1/mmg3d), LGPL). Takes level-set values on a
  background tet mesh and produces a conforming, quality-optimised mesh of the zero set, preserving
  ridges. *Measured here* (mmgpy 0.17, MMG 5.8): on the field's own grid cut into tets it refined
  instead of coarsening and ran single-threaded past 15 minutes. Not usable as tried.
- **CGAL Mesh_3** ([manual](https://doc.cgal.org/latest/Mesh_3/index.html)). Meshes implicit
  functions and labelled images; sharp-feature protection improved in
  [6.0.1, December 2024](https://www.cgal.org/2024/12/01/mesh3-improvements/); Python via
  [pygalmesh](https://github.com/meshpro/pygalmesh) (conda-forge, Linux - in WSL). *Measured here*:
  straight from the field, 46 s through pygalmesh - its questions answered in Python, its surface up
  to 1.07 mm off - and 4-8 s compiled (`bench/solvers/cgal_field.cpp`), surface within 0.005 mm;
  8-14 s with element sizes from rules and the seats' edges as lines. On the production housing its
  answers from the 3 mm field match meshing the CAD's surface within the noise of meshing itself
  ([field-meshing-gate.md](field-meshing-gate.md)) - the recommended mesher. GPL or commercial licence.
- **MeshLab and MeshFix**, for the surface route: MeshLab's isotropic remeshing makes the field's
  2.54 M-triangle surface 100,000 even triangles in about 60 s; the surface, it turned out, crosses
  itself where two sheets pass closer than the grid (2,333 faces on design #7), and MeshFix patches
  those in seconds. Both GPL.
- **quartet** ([GitHub](https://github.com/crawforddoran/quartet)), isosurface stuffing
  ([Labelle & Shewchuk 2007](https://people.eecs.berkeley.edu/~jrs/papers/stuffing.pdf); dihedral angles
  guaranteed between 10.7° and 164.8°). Never fails on a distance field, but element size is uniform:
  low fidelity.
- **Snapping boundary nodes onto the surface** after building TET10 - corners and mid-side nodes
  moved onto the CAD - was measured on the production housing: it changed no answer that matters and
  distorted elements at curved places (the stress map 27 % apart, one mesh failing in Code_Aster), so
  it is not used ([field-meshing-gate.md](field-meshing-gate.md)). Mid-side nodes stay straight, as
  agenticCAE's were.

## Solvers and realistic runtimes

*(est.)* For a 0.5-2 M-DOF TET10 model on an 8-16-core workstation: a static solve with a sparse
direct solver (PARDISO, MUMPS or PaStiX) about 0.5-2 min and 8-25 GB RAM; the first 10 modes
(shift-invert Lanczos) another 1-3 min; with meshing and I/O about 3-6 min per design - 4,000 designs
in about 8-17 days one at a time, or 3-6 days three at once. Anchors: CalculiX forum users solve
1.87 M-node models in 64 GB with PARDISO, and PaStiX beats PARDISO below about 1 M nodes
([thread](https://calculix.discourse.group/t/problem-with-large-model-solution/748?page=2)); PaStiX
gives up to 4× (CPU) and 8× (GPU) speed-ups at 1-5 M DOF ([dhondt.de](https://www.dhondt.de/)).
agenticCAE's measured campaign: 559.9 s per solve on GCP (TET10), a median 687 s per design, 36 min
wall time for 29 designs at 14 at a time; 243 s per design on the laptop with linear elements.

- **CalculiX** (GPL). Text `.inp` input, static and frequency steps, quadratic tets (C3D10). Runs on
  Windows via [PrePoMax](https://prepomax.fs.um.si/), in Linux containers, and as a cloud API on
  [Inductiva](https://inductiva.ai/simulators/calculix). *Fit: high* as a label generator; ran out of
  memory at C3D10 on this housing in 7.8 GB.
- **Code_Aster**. MUMPS/PETSc solvers; official builds are Linux and containers only
  ([SALOME_MECA 2025](https://open-simulation-center.org/downloads/code_aster/SALOME_MECA/2025));
  community Windows builds lag ([code-aster-windows](https://code-aster-windows.com/)). agenticCAE's
  proven solver on this housing - the reference here.
- **FEniCSx / dolfinx**. Native Windows via
  [conda-forge](https://github.com/conda-forge/fenics-dolfinx-feedstock). CG with PETSc's GAMG
  multigrid for elasticity, SLEPc for modes, many right-hand sides per factorisation. *Fit: high* for
  an all-Python route.
- **scikit-fem**. Pure Python; its multigrid option (PyAMG) is serial
  ([discussion](https://github.com/kinnala/scikit-fem/discussions/1079)). *Fit: medium*, for QA
  re-solves and prototypes.
- **MFEM / deal.II**. GPU matrix-free high-order ([MFEM performance](https://mfem.org/performance/));
  C++ and Linux-first. *Fit: low* (overkill here).
- **Kratos**. pip wheels including Windows ([install guide](https://github.com/KratosMultiphysics/Kratos/blob/master/INSTALL.md));
  an MMG remeshing process. *Fit: medium-low*.

## Multi-fidelity setups

A multi-fidelity graph network trained coarse mesh first, then fine
([Taghizadeh et al., CACAIE 2025](https://onlinelibrary.wiley.com/doi/10.1111/mice.13312)); a
multi-fidelity Graph U-Net ([arXiv 2412.15372](https://arxiv.org/abs/2412.15372)); a
pretrain-then-finetune neural operator for structural dynamics
([Eng. Struct. 2025](https://www.sciencedirect.com/science/article/abs/pii/S0141029625016098)). At
4,000 designs a single fidelity of TET10 solves is affordable; a GPU voxel low-fidelity level earns its
place for well over 10,000 designs or for live previews in the interface.

## What speeds each route up

- **Many designs at once** - the biggest lever; agenticCAE ran 14 at a time on the cloud.
- **Start from the unmodified housing's solution** as the iterative solver's first guess: a variant
  differs by a few ribs, so it starts near the answer.
- **Fine cells only near ribs and fillets**, coarse elsewhere: Warp's sparse NanoVDB grids support it.
- **On the mesh route**: gmsh's parallel mesher; PaStiX (faster than MUMPS below 1 M nodes); an AMG
  iterative solver on GPU; one factorisation shared by several load cases (Code_Aster
  `MACRO_ELAS_MULT`, or cuDSS's 0.04 s a further load case); fine elements only where a design
  changes the part.
- **On this laptop** (i7-13700HX, 16 cores/24 threads, 15.7 GB RAM, RTX 5060 Laptop 8 GB): one
  Code_Aster TET10 solve at a time fits (about 10 GB); memory, not cores, limits parallel work.

## Where fastcae stands

Measured, on the same load case, supports and metrics as agenticCAE: the design built with its
grid's distance on the GPU, meshed straight from its field by the compiled CGAL mesher, solved as
TET10 by cuDSS - about 2 minutes a design - is the recommended route; meshing from the 3 mm field
matches meshing the CAD within the noise of meshing itself, while agenticCAE's own route changes the
production housing's geometry. The cleaned surface filled by gmsh is the meshing fallback, Code_Aster
the audit; PETSc is not used, and the solver for a design too big for the card is open. The grid
routes stay for previews and a low-fidelity level until a cut-cell solve with quadratic cells and a
grid multigrid earns its place. See [design-to-solution.md](design-to-solution.md),
[field-meshing-gate.md](field-meshing-gate.md) and [../build-plan.md](../build-plan.md).
