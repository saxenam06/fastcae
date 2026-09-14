# The solvers tried, and why cuDSS

Every solver was given the same design, load case, supports, material and metrics on this
workstation (i7-13700HX, 16 cores, 15.7 GB RAM, RTX 5060 Laptop 8 GB; WSL with 12 GB). Each was
judged against Code_Aster. The design is #7 of campaign `w4zf5`: 1,056,945 unknowns as TET10, with
the bolt holes clamped. This page is the plain account: why each solver got its result, why cuDSS was
chosen, and what not choosing the others gives up. The measured tables are in
[../../bench/solvers/RESULTS.md](../../bench/solvers/RESULTS.md). September 2026.

## The idea behind the results

- **The same mesh and the same equations give the same answer.** Every solver given the TET10 mesh
  agreed with Code_Aster to within 7 parts in 100 million. What differed was time, memory and what else
  each offers.
- **The two grid methods skip the mesh**, which changes the equations themselves. Their wrong answers
  come from that, not from how they solve.
- **There are two ways to solve.**
  - *Direct* (cuDSS, CHOLMOD, Code_Aster's MUMPS) factorises the matrix once, like Gaussian
    elimination, and gives the exact answer. It needs a lot of memory, but each further load case then
    costs almost nothing: 0.04 s.
  - *Iterative* (PETSc, CuPy + PyAMG, FEniCSx, the voxel grid) improves a guess step by step. It needs
    little memory, but it needs a good helper - multigrid, which solves coarser copies of the problem
    to steer the fine one - to finish quickly. It stops at a tolerance (hence 10⁻⁹-10⁻⁸ from the
    reference), and every load case is a new solve.

## What was measured

Design #7, 1.06 M unknowns; the grid methods on the design's own grid.

| Solver | Kind | On the CPU | On the GPU | Where | Time | Against Code_Aster | Memory, as recorded |
|---|---|---|---|---|---:|---|---|
| **cuDSS** | direct (Cholesky) | reordering | assembly (CuPy), factorising, solving | Windows | **13 s** | 3·10⁻¹⁰ | 5.2 GB of the 8 GB card; about 1.1 M unknowns fit wholly on it; 1.49 M with part of the factor in host memory; 2.4 M failed |
| PETSc CG + GAMG | iterative | the multigrid setup's sparse products | the matrix and the iterations (422) | WSL | 35 s | 2·10⁻⁹ | 3 GB of RAM; the setup ran the card out until it moved to the CPU |
| CuPy CG + PyAMG | iterative | the multigrid levels (26 s) | the iterations (525, 16 s) | Windows | 51 s | 1·10⁻⁹ | not recorded |
| **Code_Aster 18**, MUMPS | direct | everything, one core | - | WSL | **57 s** | the reference | 3.4 GB, capped at 3.7 GB, so factors went to disk |
| CHOLMOD | direct | everything | - | WSL | 61 s | 3·10⁻¹⁰ | 6.9 GB of RAM |
| JAX-FEM | direct (cuDSS), assembly by automatic derivatives | setting up the problem | assembly, factorising, solving | WSL | 112 s | 3·10⁻¹⁰ | 11.6 GB of RAM; JAX's GPU memory pool switched off to leave cuDSS room |
| FEniCSx, quadratic | iterative (PETSc CG + GAMG, 433 iterations) | everything, one core | - | WSL | 253 s | 7·10⁻⁸ | 2.0 GB of RAM |
| PETSc CG + GAMG | iterative | everything | - | WSL | 316 s | 2·10⁻⁹ | not recorded |
| Voxel grid (Warp) | iterative, no mesh | - | everything | Windows | 51 s at 6 mm, 109 s at 5 mm | worst tilt +14 % / +17 % | 2.3 M and 3.8 M unknowns fit; 4 mm (7 M) ran the card out |
| Cut cells (Warp + cuDSS LU) | direct, no mesh | - | everything | Windows | 9 s at 12 mm, 43 s at 10 mm | worst tilt -6 %, gear-mesh lead -17 to -19 %, p99.9 within 0.4 % | linear cells at 8 mm and quadratic cells ran the card out |

agenticCAE's records add one more: CalculiX used up 7.8 GB on this housing's TET10 mesh and failed.

## Why each got its result

- **cuDSS** factorises the whole system on the GPU in one go, with no iterations, and a 1 M-unknown
  factor fits in 5.2 GB. On the field's mesh of design #7 (905,154 unknowns): 5.2 s to assemble on the
  GPU, then 2.7 s of reordering on the CPU, 1.9 s factorising and 0.04 s solving.
- **PETSc** must build its multigrid helper first. Built on the GPU, the helper's sparse products
  wanted more than the 8 GB card, so they run on the CPU; then 422 iterations.
- **CuPy + PyAMG** is our own version of the same: PyAMG builds the helper on the CPU (26 s), it is
  copied to the GPU (9 s), and the GPU runs the iterations (16 s).
- **Code_Aster and CHOLMOD** do cuDSS's exact job on the CPU, so they are 4-5 times slower and use a
  lot of RAM. Code_Aster ran on one core, and at its 3.7 GB cap it wrote its factors to disk.
- **JAX-FEM's solve is cuDSS**: 14 s to factorise, 0.1 s to solve. The rest of its 112 s is JAX
  building the stiffness by automatic derivatives and compiling it, moving it to the GPU, and working
  around memory. Its own search for the seat faces also took in interior and neighbouring faces - 30 %
  extra area on one seat - until it was handed the seats' faces.
- **FEniCSx** is accurate, but it is iterative on one core with its own assembly, so it is the
  slowest. That independent assembly is its value: agreeing to 7·10⁻⁸ checks the assembly every GPU
  solver here shares.
- **The voxel grid** turns the surface into stair-steps. The bolts and loads land on grid points near
  the real surface, not on it, so the part is held and loaded in the wrong places. Refining made it
  worse, because that error does not shrink with the grid. It also has only a weak built-in helper (a
  diagonal one): 10,677-13,073 iterations.
- **The cut cells** use the true surface, which is why stress came out right. But simple 8-corner
  cells are too stiff in bending, which lowers tilt and gear-mesh lead. Quadratic cells would fix that,
  but they did not fit in 8 GB. More below.

## Why cuDSS

- **The reference's answer, faster**: 2.7 times faster than the next (PETSc on the GPU), 4.3 times
  faster than Code_Aster, 19 times faster than FEniCSx.
- **Nothing to tune and nothing to converge**: a direct solve cannot stall on a hard design.
- **Further load cases almost free**: 0.04 s each against the same factor.
- **On Windows, in the same process** as the GPU assembly (nvmath-python).
- **Where the industry is going**: in [COMSOL 6.4](https://www.comsol.com/release/6.4/gpu-acceleration),
  Altair OptiStruct and Ansys HFSS ([NVIDIA](https://blogs.nvidia.com/blog/cuda-x-grace-hopper-blackwell/)).

Its limits:

- **Memory.** About 1.1 M unknowns fit wholly on the 8 GB card (5.2-6.1 GB). Keeping part of its
  factor in host memory, it solved 1.49 M in 10 s (5.5 s reordering, 4.5 s factorising, 0.05 s
  solving); at 2.4 M it failed.
- **The reordering is redone for every design**, 2.7-10 s on the CPU: cuDSS cannot reuse it between
  meshes of different sparsity, and every design has its own mesh. It slows when other CPU work runs
  beside it.
- **One solve at a time** on the 8 GB card.

A design past what cuDSS holds goes to Code_Aster in WSL - about 2-3 minutes, rare - as proposed in
the build plan; PETSc is not used.

## What not choosing the others gives up

- **JAX-FEM: automatic gradients.** A gradient says how each result changes when a design setting
  changes - useful for optimisation, and for training a model on gradients as well as values. Training
  on gradients gains 10-20 % when data is scarce - less than one doubling of the data - and needs
  meshes consistent between neighbouring designs, which ribs appearing and disappearing break
  ([surrogates.md](surrogates.md)). With cuDSS the cheap half stays: the sensitivity of a result is
  one more solve against the same factor, 0.04 s. What JAX gives for free - how the stiffness changes
  with shape - would be ours to write. JAX-FEM stays in the bench for when gradient-based optimisation
  is the goal.
- **PETSc: larger meshes on the same card.** Multigrid needs far less memory than a factor. Not used;
  a design too big for cuDSS is proposed to go to Code_Aster instead.
- **CuPy + PyAMG: an iterative route native on Windows.** Kept in the bench.
- **Code_Aster: industry trust and ready-made physics** - vibration modes, harmonic response,
  contact, nonlinear material. It stays as the audit that re-solves 10 of the 40 check designs, and is
  proposed for a design too big for the card. Vibration modes later need an eigen-solver on our side
  or Code_Aster.
- **CHOLMOD: a route with no GPU**, for a machine without one.
- **FEniCSx: new physics written in a few lines**, and the independent check of the assembly. Too
  slow for the campaign.
- **The voxel grid and cut cells: no meshing at all.** Nothing to fail, and every design on the same
  grid, which suits machine learning and live previews. They stay out of the training data until
  quadratic cut cells with the couplings fit - most likely with a multigrid solver on the grid, or a
  bigger GPU. Kept for previews.

## CPU and GPU in the chosen route

- **GPU**: the build's exact distance to the part (Warp), the stiffness assembly (CuPy), the
  factorising and solving (cuDSS). The card peaks at about 5-6 GB for a 1 M-unknown design, so one
  solve runs at a time.
- **CPU**: the rest of the build (moving faces, blending, the checks), meshing (CGAL, on 4 threads),
  cuDSS's reordering, TET10 and the labels.
- **RAM**: 16 GB allows 2-3 designs in progress at once - an estimate; RAM per design was not measured.
  Code_Aster in WSL took 4.2-4.5 GB per solve on the gate's 1.1-1.2 M-unknown meshes.

## Cut cells, plainly

### How the method works

1. **A lattice of cubes over the part**, 10-12 mm across, with no mesh following its shape.
2. **Each cube sorted**: wholly outside (dropped), wholly inside (an ordinary element) or cut by the
   surface. The GPU asks the surface at each cube's sample points. Here the surface was the TET10
   mesh's own boundary, so the comparison with Code_Aster differs in the discretisation only.
3. **A cut cube counts only its metal.** Its stiffness is summed at many sample points inside it,
   points in the metal at full stiffness and points outside at a millionth of it, so the equations stay
   solvable.
4. **Loads on the real surface.** Each seat's force acts at points on the actual seat surface, not
   on the nearest cube corners.
5. **Bolts held on the real surface, approximately.** Cube corners do not lie on the bolt holes, so
   they cannot simply be fixed. Stiff springs pull points on the real hole surfaces towards zero
   movement instead.
6. **Assembled and solved on the GPU**: Warp builds the equations, cuDSS solves them - by LU, because
   the stiffness is summed in single precision and the near-empty cubes make it unreliable for the
   symmetric method.
7. **Results read anywhere** by interpolating inside each cube: displacement at the seats, stress at
   sample points.

The voxel grid is the crude version: each cube all metal or none, so surfaces become stair-steps and
loads and supports land on cube corners near the surface - 14-17 % off, and worse as it refines.

### Why its tilt and gear-mesh lead came out low

- **The comparison was like for like.** Both sides held the bolt holes clamped, with no couplings;
  both spread each seat's force over the seat's surface; and both read tilt and lead the same way, from
  the best-fit rigid movement of each seat's surface points. The missing couplings do not explain the
  difference.
- **The cells are too stiff in bending.** Simple 8-corner cubes, 10-12 mm across, act stiffer in
  bending than the real metal - linear cells lock. Tilt and lead come from bending, so both come out
  low.
- **The lead is a difference of two seats' movements.** A few per cent of error in each seat can
  become a much larger error in the difference: tilt was about 6 % low, the lead 17-19 %.
- **The bolts held by springs** add a little more.
- **Stress came out right** (p99.9 within 0.4 %) because the real surface shape is used and the
  percentile is averaged over a volume.

### Can couplings be added?

Yes, both kinds, but differently from a mesh: the lattice has no nodes on the bolt holes or seats, so
the couplings act at sample points on the real surface.

- **Distributed couplings at the bearing seats** are straightforward. They only spread each seat's
  force and moment over the seat surface, with the same weights and moment balance the GPU route uses.
  The seat's tilt, read at the coupling's centre node, is the best-fit rigid motion of those same
  points - so the lead would be measured the chosen way.
- **Kinematic couplings at the bolts** are possible, but approximate. Each bolt gets a centre node,
  held in translation and free to turn - 3 rotations per bolt, 75 unknowns in all - and points on the
  real hole surface are tied to its rigid motion, where the current run pulls them to zero. The tie can
  be stiff springs, as now, or Nitsche's method - the standard way to tie such grids, more accurate,
  more work. Springs need care: too soft and the bolts are too flexible; too stiff and the equations
  become hard to solve, especially with nearly empty cubes.

How the bolts are held moves this housing's answer far more than the solver does: clamping the holes
instead of agenticCAE's couplings moves the worst tilt from 2.07' to 1.25', 40 %. So couplings are
needed for a fair comparison with the chosen setup - but on their own they do not fix the cells'
bending stiffness.

### So, for bending

The cut cells as built are not accurate enough for bending results - tilt and misalignment, which this
project's data is about. The cause is the cell type, not the cutting. Quadratic cells, or cells fine
enough to put 2-3 through every wall and rib, would fix it; both need much more memory than the 8 GB
card, so a multigrid solver on the grid or a bigger GPU. Meshed quadratic tets with cuDSS carry the
training data; cut cells stay useful for quick previews and for stress.
