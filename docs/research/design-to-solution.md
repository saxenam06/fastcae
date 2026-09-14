# From a design to a solved example, measured

What it takes to turn one generated design into a solved training example, every step tried more
than one way on this workstation (i7-13700HX, 16 cores, 15.7 GB RAM, RTX 5060 Laptop 8 GB; WSL with
12 GB). The design: #7 of campaign `w4zf5` - six variants, 15 ribs and 11 pads on the GRC housing,
128,942 cm³, 915.5 kg. The yardstick: the slow route - a 33-minute build, a 103-minute fTetWild
mesh, Code_Aster - on agenticCAE's load case, supports and metrics. September 2026; everything here
measured, nothing estimated. Tables and raw timings: [../../bench/solvers/RESULTS.md](../../bench/solvers/RESULTS.md)
and `bench/solvers/results/`.

## In one table

| Step | Slow route | Fast route | Fallback |
|---|---:|---:|---:|
| Build the design | 1,962 s - exact distances on the CPU | **79 s** - the same distances on the GPU | - |
| Mesh it | 6,174 s - fTetWild | **51 s** - CGAL meshing the field itself | 73 s - the field's surface cleaned, gmsh |
| Assemble and solve | 57 s - Code_Aster, one core | **10 s** - cuDSS on the GPU | 35 s - PETSc multigrid on the GPU |
| A design, end to end | about 2.3 hours | **about 2.5 minutes** | about 3 minutes |

The fast route's answer against the slow route's: every seat's tilt within 2.3 %, the gear-mesh
leads within 1.2 %, the 99.9th-percentile stress within 1.2 %, the largest displacement within 0.2 %
- the spread the slow route's own two meshes of this design show (1.8-3.5 %), and inside the accuracy
the build plan asks of training data. At 2.5 minutes a design, 4,000 designs take about a week on
this machine one at a time.

## The words, plainly

- **Distance field** - at every point of a grid, how far it is to the part's surface, negative
  inside. A fastcae design lives as one: a 3 mm grid at preview, 50.8 M points on this housing, exact
  distances within 9 mm of the surface (the band).
- **Dual contouring** - turning the field back into triangles: one vertex per grid cell the surface
  crosses, placed where the surface's tangent planes meet, so machined edges stay sharp.
- **Tessellation** - the CAD's own surface as triangles, from OCC: 133,102 for the housing, each
  tagged with its CAD face. The build measures distances to it.
- **Bounding-volume hierarchy** - a tree of boxes around the triangles, so "which triangle is
  nearest this point" checks a handful, not all; on a GPU, millions of points at once.
- **Single and double precision** - numbers held to about 7 and 16 significant digits. GPUs are
  fastest in single.
- **Tet mesh, TET10** - the part filled with tetrahedra. TET10 adds a node at the middle of every
  edge, so displacement can bend inside an element; agenticCAE measured linear tets 25-35 % too stiff
  on this housing.
- **Element quality** - 1 for a regular tetrahedron, 0 for a flat one. A **sliver** is a nearly flat
  tet: four corners almost in one plane.
- **Envelope** - how far fTetWild may move the surface to make good tets.
- **Decimation** - fewer triangles by merging neighbours, keeping the shape roughly. **Isotropic
  remeshing** - the surface rebuilt with even triangles of a chosen size, finer where it curves,
  sharp edges kept.
- **Self-intersection** - a surface passing through itself. No tet mesher can fill one.
- **Level set** - a surface given as where a field equals zero. Meshing from the field means meshing
  a level set.
- **Direct solver** - factorises the stiffness matrix, like Gaussian elimination: exact and robust,
  memory-hungry. **Iterative solver** - improves a guess step by step (conjugate gradient): little
  memory, but needs a **preconditioner**. **Multigrid (AMG)** is the usual one: it solves coarser and
  coarser versions of the problem to steer the fine one.
- **Voxel method** - each grid cell a brick element; no mesh, but stair-stepped surfaces. **Cut-cell
  (finite cell) method** - the same bricks, those the surface cuts integrated over their solid part
  only.
- **Supports** - how the flange's bolts hold the housing. *Clamped*: every node on the bolt holes
  fixed. *Couplings*, as agenticCAE solved it: each bolt position a rigid body tied to a held point on
  its axis (an RBE2), free to turn about it; each seat's force spread over the seat's nodes so force
  and moment balance (an RBE3).
- **The metrics** (agenticCAE's): a seat's **tilt**, arc-minutes - its best-fit rigid rotation; the
  **gear-mesh lead** - how differently two shafts skew across a gear's face, mrad or µm over the face
  width; **p99.9 von Mises** - the stress 99.9 % of the volume stays under (the peak chases sharp
  corners and says more about the mesh than the part); the **largest displacement**.

## 1. Building the design

The build takes the part's cached field, blends in ribs and pads with their fillets, moves faces and
cuts holes. The fillets need the part's exact distance near every rib, so the build measures, cell by
cell, the distance to the CAD's triangles - point against triangle, on the CPU, about 70,000 cells a
second. That one step was nearly all of design #7's 33 minutes.

**On the GPU**, the same question against a bounding-volume hierarchy of the triangles (NVIDIA Warp)
answers all 5.9 M cells of the design's band in 0.02 s, after 3 s to build the tree once for the part.

**The catch.** OCC tessellates big faces with slivers - triangles 570 mm long and 1.3 mm high,
chords across a face. In single precision the GPU's nearest point on such a triangle is wrong by up
to 0.43 mm: 8,414 of the band's 5.9 M cells misread, every one at the surface - exactly where the
fillets and the contour read the field. Moving the part to the origin does not help; it is the
triangle's shape, not its size.

**The fix.** Every triangle longer than 16 mm halved across its longest edge, again and again - the
same surface in 1.49 M better-shaped triangles, 3 s once per part. Then no cell differs from the
exact answer by more than 0.004 mm. (At 40 mm: 390,808 triangles, one cell off by 0.011 mm.)

**Exact on the CPU instead.** libigl's double-precision tree is exact, but 5.9 M cells take 48 s -
only 1.7× today's code. The GPU with split triangles is the way.

**The result.** Design #7 rebuilt in 79 s instead of 1,962 s, and the same design: not one of the
field's 50.8 M cells changes side, its distances agree within 0.005 mm, the surface has the same
2.54 M triangles, and 8 of its 1.27 M vertices lie more than 0.01 mm from before (dual contouring's
vertex placement is sensitive in a few nearly degenerate cells). What is left of the 79 s: the
checks 25 s, contouring the surface 23 s, moving faces 17 s, the distances 8 s. Still a trial -
`bench/solvers/build_gpu.py` swaps the function in at run time; the product code is unchanged.

## 2. Meshing

A mesher needs a closed surface that does not cross itself - or the field itself. What each did:

**fTetWild, the slow route.** Robust to messy input: it may move the surface within its envelope.
But on design #7 its surface, decimated from 2.54 M triangles:

| Input | Envelope | Time | Result |
|---|---|---:|---|
| 400,000 triangles | 0.95 mm, full optimisation | 6,174 s | 190,739 tets, 1.06 M unknowns, worst quality 0.30 |
| 200,000 | 1.9 mm, lighter optimisation | 1,871 s | 119,753 tets, 648 k unknowns, worst 0.15 |
| 102,100 - as far as decimation goes | 1.9 mm, lighter | 1,564 s | 102,967 tets - and a spoilt part: boundary up to 23 mm from the design, bolt holes down to a third of their triangles |

Its time does not follow its input: its optimisation passes dominate. Metrics differ by 1.8-3.5 %
between its two good meshes - the mesh's own uncertainty at this size.

**gmsh, re-parametrising the surface.** Asked to split the 200,000-triangle surface into patches
and re-parametrise them before meshing, it had not finished that first step after 30 minutes.

**The field's surface cleaned, then filled.** MeshLab's adaptive isotropic remeshing rebuilds the
2.54 M-triangle surface as 100,000-290,000 even triangles in about 60 s, closed and manifold, within
a set distance of the original. Then a finding: **the dual-contoured surface crosses itself** - 2,333
faces on design #7, 95 % of them on one 556 mm column (a flat face between two R25 rounds) where two
sheets pass closer than the 3 mm grid. A defect in the contouring, not the remesh. MeshFix removes
the crossing triangles and patches the gaps in 2-5 s, within 2.4 mm of the design.

- **TetGen** refuses the unrepaired surface ("Internal TetGen error within recoversubfaces"). On the
  repaired one it is fast - 4-8 s - but leaves slivers: 749-8,626 tets below quality 0.1; allowed to
  split the surface, it makes more tets, not better ones.
- **gmsh's parallel mesher (HXT)**, the repaired surface kept exactly as given: 167,713 tets in 9 s,
  985,905 unknowns, volume within 0.04 % of the design, 0.75 % slivers - at the surface, which it may
  not touch. The whole step 73 s. Its answer: tilts within 1.6 % of the slow route, leads within 1.3 %,
  p99.9 +0.8 %.

**MMG, meshing the field's grid.** The field's grid cut into tets - six to a cube, split along its
long diagonal alike in every cube (the Kuhn split), so neighbours share faces - each corner carrying
the field's distance; MMG cuts the tets where the distance is zero and remeshes. It refined instead
of coarsening: on a crop of the housing, 2,484 tets became 5,900-25,500 whatever the target size, as
it chased the facets the lattice cut leaves; on the whole design, one core, it had not finished after
15 minutes. Dropped.

**CGAL, meshing the field itself - the fast route.** CGAL's mesher (Mesh_3, through pygalmesh, in
WSL) treats the field as a function: it asks, point by point, whether a point is inside and how far
from the surface - trilinear across the 3 mm grid, exact in its band - and builds a Delaunay mesh whose
surface facets lie within a set distance of where the field is zero, holds the cells to a size, then
removes slivers.

| Facet distance | Time | Tets | Unknowns | Worst quality | Boundary from the design | Volume |
|---|---:|---:|---:|---:|---|---:|
| 2 mm | 46 s | 157,358 | 905,154 | 0.175, none below 0.1 | median 0.3 mm, 99 % within 1.0 mm | +0.08 % |
| 1 mm | 171 s | 606,100 | 3.37 M | 0.15 | median 0.4 mm | +0.02 % |

No surface is made, so nothing needs repairing. At 2 mm its answer is within 2.3 % of the slow route
on every tilt, 1.2 % on the leads, 1.2 % on p99.9. At 1 mm CGAL refines every small fillet and hole;
3.37 M unknowns neither assemble nor factor on the 8 GB card. Nearly all of the 46 s is 18 M questions
to the field answered in Python, about 2.5 µs each - a compiled field function would take it to
seconds. Without feature lines it rounds sharp edges at the facet size.

## 3. Solving

On one mesh every TET10 solver gives the same answer; what differs is time and memory. Design #7,
1.06 M unknowns:

| Solver | Total | Against Code_Aster | Memory |
|---|---:|---:|---|
| **cuDSS**, sparse Cholesky on the GPU | **13 s** | 3·10⁻¹⁰ | 5.2 GB of the card |
| PETSc conjugate gradient + GAMG multigrid, GPU | 35 s | 2·10⁻⁹ | 3 GB host |
| Conjugate gradient + PyAMG levels, CuPy V-cycles, GPU | 51 s | 1·10⁻⁹ | |
| **Code_Aster 18**, MUMPS block low-rank, one core - the reference | **57 s** | - | 3.4 GB |
| CHOLMOD, CPU | 61 s | 3·10⁻¹⁰ | 6.9 GB |
| JAX-FEM, automatic-differentiation assembly + cuDSS | 112 s | 3·10⁻¹⁰ | 11.6 GB host |
| FEniCSx, its own assembly, conjugate gradient + GAMG, one core | 253 s | 7·10⁻⁸ | 2 GB |
| PETSc conjugate gradient + GAMG, CPU | 316 s | 2·10⁻⁹ | |

- **cuDSS is the solver.** Exact, fastest, and it fits a design this size on the card. Its ceiling is
  about 1.1 M unknowns (5.2-6.1 GB used); past it PETSc's multigrid on the GPU, whose setup products
  run on the CPU.
- **FEniCSx** assembles the system itself and agrees to 7·10⁻⁸ - the independent check on the
  assembly every GPU solver shares.
- **JAX-FEM** is exact once handed the seat faces; its value is gradients for optimisation, not speed.
- **No mesh at all.** The voxel grid (Warp, trilinear bricks, 6 mm and 5 mm, 2.3-3.8 M unknowns) is
  14-17 % off on the worst tilt and moves further off as it refines: its supports and loads land on
  the grid nodes nearest the surface. Cut cells (finite cells on Warp, loads and a bolt penalty on
  the true surface, cuDSS) get the stress percentile within 0.4 % but are 6 % low on the worst tilt and
  17-19 % low on the gear-mesh lead - linear bricks are too stiff in bending; quadratic ones need a
  multigrid solver on the grid before they fit the card. Not label-grade yet; kept for previews.
- **Checked against agenticCAE.** On agenticCAE's own mesh of its production design, with its own
  couplings, Code_Aster here lands within 10 % of every tilt agenticCAE recorded and within 2.4 % of
  its gear-mesh lead - the load case, material and metrics carried over. The GPU route solves the same
  couplings - the bolts' rigid bodies eliminated, the seats' RBE3 loads applied as their force and
  moment - to Code_Aster's answer at 2·10⁻¹⁰, in 14 s.
- **The supports matter more than the solver.** Clamping the bolt holes instead of agenticCAE's
  couplings moves the worst bore's tilt from 2.07' to 1.25' - 40 %. The solvers agree to nine digits
  on either.

## 4. Reading the answer

- **Seats** are found by geometry - diameter, axis, height as agenticCAE recorded them - because the
  CAD is the same file but OCC numbers its faces differently from agenticCAE's reader.
- **Bolts.** The flange has a hole every 9°; the bolts are the 25 positions with a 55 mm counterbore,
  each with the through-hole under it. Taking every cylinder on the bolt circle - 71 faces - also held
  tapped holes, dowel holes and a port up the wall, which are not bolts.
- **Labels move to any mesh** by the CAD face of the design triangle nearest each boundary triangle,
  so every mesher here is labelled the same way.
- **One reading for every solver** - the metrics come from the displacement, stress from element
  centres weighted by volume. agenticCAE's p99.9 (67.8 MPa on its design) came from nodal stresses and
  is not comparable with these.

## The route this points to

1. **Build** with the grid's distance on the GPU, the part's long triangles split once.
2. **Mesh** straight from the field with CGAL, surface facets within 2 mm - about 0.9 M unknowns; the
   cleaned surface filled by gmsh as the fallback.
3. **TET10** with straight mid-side nodes, labelled by CAD face.
4. **Assemble** on the GPU and **solve** with cuDSS; PETSc's multigrid on the GPU for a design too
   big for the card; Code_Aster on a sample, as the audit.

About 2.5 minutes a design; the steps use different parts of the machine (CPU checks and contouring,
GPU distances and solves, CGAL in WSL), so overlapping designs shortens a campaign further.

## What still has to happen

- **Into the product**: the GPU distance in the build and the field mesher as a pipeline stage, with
  tests; Warp and CGAL (pygalmesh) become dependencies.
- **A compiled field function** for CGAL - its 46 s is Python answering questions.
- **The contouring where sheets cross** - the design's surface should never pass through itself.
- **The supports** - the engineer's decision: agenticCAE's couplings, which keep the data beside its
  490 solved designs, or clamped holes.
- **Licences**: MeshLab, MeshFix and gmsh are GPL, CGAL GPL or commercial, TetGen AGPL. A hosted
  service is not distribution; shipping the software to a customer would be.

## What each tool needed on this machine

- **Code_Aster 18** (WSL): `CA.init`, and `_F` from `code_aster.Cata.Syntax`. Its mesh reader stops
  at 80 characters a line - a TETRA10 with seven-digit node names must span two lines, or node numbers
  are cut short and the mesh is silently wrong. Run it from a Linux directory: MUMPS writes its
  factors out of core, and through WSL's bridge to a Windows drive that crawls. Its memory is capped at
  3.7 GB unless raised.
- **PETSc 3.25 with CUDA** (WSL): `-use_gpu_aware_mpi 0`; GAMG's setup products on the CPU
  (`-matmatmult_backend_cpu`, `-matptap_backend_cpu`) - cuSPARSE's want more than 8 GB.
- **One GPU job at a time**: a PETSc or CuPy process keeps its GPU memory until it exits.
- **cuDSS** (nvmath-python 1.0): Cholesky needs a positive-definite matrix; the cut-cell matrix,
  integrated in single precision, needs LU. Its threading library ships beside it.
- **JAX-FEM 0.0.12**: its location functions pick every cell face whose nodes lie on a seat, interior
  ones included - 30 % extra area on one seat - so it is handed the faces; its row elimination leaves
  the matrix unsymmetric - zeroing the held columns restores Cholesky; its surface-load sign is the
  opposite of a traction; JAX takes most of the GPU's memory unless told not to.
- **Warp**: single-precision nearest-point queries misread slivers; adding one sparse matrix into
  another in place reserves room for both - the pieces are added on the host.
- **fTetWild** writes the surface it tracked - the part's geometry - into the working directory.
- **gmsh**: re-parametrising a big triangulated surface stalls; the surface given as a discrete
  surface inside a surface loop meshes directly.
- **TetGen** (0.8.4) fails on self-intersections and returns four arrays.
- **pymeshlab 2025**: absolute lengths are `PureValue`.
- **mmgpy 0.17** (MMG 5.8): vertices and elements set together, the level set as an N×1 array, the
  inside is reference 3.
- **pygalmesh 0.10.7** is on conda-forge for Linux, not Windows; a domain written in Python costs
  about 2.5 µs a question.
