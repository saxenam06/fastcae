# Solver benchmark - results

Measured 14 September 2026 on the workstation (i7-13700HX 16 cores, 15.7 GB RAM, RTX 5060 Laptop 8 GB;
WSL Ubuntu 24.04 given 12 GB). Setup, cases and scripts: [README.md](README.md). Per-case tables with
every seat: `results/<case>/results.md`.

## The answer

**Solve TET10 on the GPU with cuDSS.** On design #7 (1.06 M unknowns) it gives Code_Aster's answer
to a relative field error of 3·10⁻¹⁰ - every metric identical to four decimals - in **13 s** against
Code_Aster's 57 s, using 5.2 GB of the card. With agenticCAE's own supports (an RBE2 per bolt, an
RBE3 per seat) it reproduces Code_Aster's `LIAISON_SOLIDE` + `LIAISON_RBE3` to 2·10⁻¹⁰, in 14 s.

**Solving is no longer the bottleneck. Building and meshing are:** design #7 took 33 min to build at
preview and 31-103 min to mesh with fTetWild; the solve takes 13 s.

**The grid routes are not label-grade at a size this card holds:** the voxel grid is off by 14-17 %
on the worst tilt and moves further off as it refines; the cut-cell grid (finite cell method, linear
cells) is 6 % low on the worst tilt and 17-19 % low on the gear-mesh lead, though its p99.9 stress
is within 0.4 %.

**How the bolts are held matters more than which solver holds them:** the worst tilt on agenticCAE's
design is 1.25' with the bolt holes clamped and 2.07' with agenticCAE's couplings, which let each
hole turn about its bolt.

## Design #7 - 1,056,945 unknowns, TET10

fTetWild, 20 mm edges, 0.95 mm envelope, 190,739 elements (worst quality 0.30). Supports clamped;
the reference is Code_Aster.

| Solver | Where | Setup s | Solve s | Total s | Field error | Memory |
|---|---|---:|---:|---:|---:|---|
| **cuDSS**, sparse Cholesky | GPU | 12.8 | 0.3 | **13.1** | 3.3·10⁻¹⁰ | 5.2 GB GPU |
| PETSc CG + GAMG, cuSPARSE (422 iterations) | GPU, WSL | 23.4 | 11.7 | 35.1 | 1.7·10⁻⁹ | 3 GB host |
| CG + PyAMG levels, CuPy V-cycles (525 iterations) | GPU | 34.6 | 16.3 | 50.8 | 1.3·10⁻⁹ | |
| **Code_Aster 18**, MUMPS block low-rank, one core | CPU, WSL | 4.7 | 51.9 | **56.6** | reference | 3.4 GB |
| PETSc + CHOLMOD | CPU, WSL | 59.7 | 1.3 | 61.0 | 3.3·10⁻¹⁰ | 6.9 GB |
| JAX-FEM TET10, autodiff assembly + cuDSS | GPU, WSL | 111.7 | 0.1 | 111.8 | 3.3·10⁻¹⁰ | 11.6 GB host |
| FEniCSx P2, its own assembly, PETSc CG + GAMG (433 it.) | CPU, WSL | 4.5 | 248.8 | 253.3 | 6.8·10⁻⁸ | 2.0 GB |
| PETSc CG + GAMG (422 iterations) | CPU, WSL | 25.9 | 290.2 | 316.1 | 1.7·10⁻⁹ | |

Every TET10 solver gives the same metrics: worst tilt 1.4678' at BORE_MAIN_S2, IMS gear-mesh lead
73.35 µm, p99.9 von Mises 113.96 MPa, largest displacement 0.8540 mm, reactions balancing the loads
to 0.1 N in 460 kN. FEniCSx assembles the system itself, independently of ours, and still agrees to
7·10⁻⁸ - a check on the assembly the GPU solvers share.

Without a mesh, on the design's own grid:

| Method | Unknowns | Total s | Worst tilt | Worst tilt error | IMS lead error | p99.9 error |
|---|---:|---:|---:|---:|---:|---:|
| Voxel, trilinear hexes, 6 mm (Warp, CG, 10,677 it.) | 2.29 M | 50.7 | 1.670' | +13.8 % | +24.5 % | +14.2 % |
| Voxel, 5 mm (13,073 it.) | 3.77 M | 108.9 | 1.715' | +16.8 % | +35.9 % | +22.0 % |
| Voxel, 4 mm | 7 M | - | - | out of GPU memory | | |
| Cut cells (finite cell), linear, 12 mm (Warp + cuDSS LU) | 0.44 M | 9.3 | 1.379' | -6.1 % | -18.7 % | +0.4 % |
| Cut cells, linear, 10 mm | 0.68 M | 43.0 | 1.381' | -5.9 % | -16.6 % | +0.2 % |
| Cut cells, linear 8 mm; quadratic 16-20 mm | | - | - | out of GPU memory (the LU) | | |

The voxel grid gets worse as it refines: its supports and loads land on the grid nodes nearest the
surface, and its stair-stepped holes and seats are not the part's. The cut-cell grid integrates the
true surface and puts the loads and the bolt penalty on it, so its stress percentile is right; its
linear cells are too stiff in bending, which the tilts and the lead show. Quadratic cells would cure
that, but their LU does not fit the card - they need a multigrid solver on the grid, which is not
written.

## Mesh sensitivity - the same design, meshed coarser

The coarser mesh: fTetWild with a 1.9 mm envelope and lighter optimisation - 648,165 unknowns,
119,753 elements (worst quality 0.15). Against the fine mesh: worst tilt +1.8 %, IMS lead -2.3 %,
p99.9 -3.4 %, largest displacement -0.2 %. TET10 at 20 mm is converged to a few per cent here.
cuDSS takes 8.3 s on it, Code_Aster 47 s, CHOLMOD 97 s, PETSc GAMG on the CPU 189 s.

## agenticCAE's design e56235 - 1,098,279 unknowns, on agenticCAE's own mesh

| Solver | Setup s | Solve s | Total s | Field error |
|---|---:|---:|---:|---:|
| cuDSS | 15.0 | 0.2 | 15.2 | 5.8·10⁻¹⁰ |
| PETSc CG + GAMG, GPU (126 iterations) | 19.2 | 3.7 | 22.8 | 6.1·10⁻¹⁰ |
| CG + PyAMG levels, CuPy (203 iterations) | 51.1 | 6.7 | 57.8 | 5.6·10⁻¹⁰ |
| PETSc CG + GAMG, CPU | 24.7 | 76.0 | 100.7 | 6.1·10⁻¹⁰ |
| Code_Aster, MUMPS BLR, one core | 5.7 | 113.8 | 119.6 | reference |
| FEniCSx P2, CG + GAMG, CPU (215 iterations) | 5.4 | 118.3 | 123.7 | 2.0·10⁻⁸ |
| JAX-FEM + cuDSS | 149.2 | 0.1 | 149.3 | 5.8·10⁻¹⁰ |
| PETSc + CHOLMOD | 254.7 | 53.2 | 307.9 | 5.8·10⁻¹⁰ |
| Cut cells, linear, 20 / 12 / 10 mm | | | 5.1 / 21.0 / 30.1 | worst tilt -18 % / -12 % / -10 % |

**Against agenticCAE's recorded answer.** With agenticCAE's own couplings - each bolt position tied
rigidly to a held point on its axis, each seat's force through an RBE3 - Code_Aster here gives:

| | here | agenticCAE (handbook 14-objective) | |
|---|---:|---:|---:|
| BORE_AX1_S1 tilt | 0.2959' | 0.3294' | 0.90 |
| BORE_AX1_S4 | 1.1109' | 1.1259' | 0.99 |
| BORE_AX2_S2 | 0.3448' | 0.3131' | 1.10 |
| BORE_AX2_S3 | 1.3383' | 1.3490' | 0.99 |
| BORE_MAIN_S2 | 2.0665' | 2.1960' | 0.94 |
| BORE_MAIN_S3 | 0.5093' | 0.5252' | 0.97 |
| IMS lead | 19.50 µm | 19.04 µm | +2.4 % |
| HSS lead | 0.3297 mrad | 0.3264 mrad | +1.0 % |
| Largest displacement | 0.391 mm | 0.4285 mm | -9 % |

The load case, material and metrics carried over. What is left - within 10 % - is agenticCAE's
slightly different mesh and which faces its bolt and seat couplings gathered (it took nodes within
3 mm of the faces). agenticCAE's p99.9 (67.8 MPa) is not comparable: it came from nodal stresses,
here from element centres. The GPU solve of the same couplings matches Code_Aster's to 2·10⁻¹⁰ on
every tilt.

With the bolt holes clamped instead, BORE_MAIN_S2 tilts 1.248' against 2.066' - the support model
moves the answer by 40 %; the solver, by nothing.

## Per design, end to end

| Step | Design #7 | |
|---|---|---|
| Build at preview (3 mm field) | 1,962 s | the field's exact point-to-triangle distances in `window_between` |
| Decimate the surface, 2.5 M triangles to 0.2-0.4 M | 10 s | |
| Mesh, fTetWild | 1,871-6,174 s | 1.9 mm / 0.95 mm envelope |
| Assemble on the GPU | 4-8 s | |
| Solve, cuDSS | 13 s | |

At today's build and mesh times a design takes 1-2.3 hours - 4,000 of them, 6-12 months one at a
time on this machine; their solves alone, 15 hours. The next speed work is the build and the mesher,
not the solver.

**The mesher.** fTetWild took 103 minutes on the surface decimated to 400,000 triangles with a
0.95 mm envelope, and 31 minutes on 200,000 with a 1.9 mm envelope and lighter optimisation. A
coarser input does not rescue it: decimated as far as it would go, to 102,100 triangles, it still
took 26 minutes, and the decimation had spoiled the part - its boundary up to 23 mm from the design
in places, the bolt holes down to a third of their triangles. gmsh, asked to split the
200,000-triangle surface into patches and re-parametrise them before its parallel mesher, had not
finished that first step after 30 minutes (`mesh_gmsh.py`). A faster mesher has to start from
somewhere else - the distance field itself, or a cleanly remeshed surface.

**The build's slowest step** is the exact distance from the design's grid cells to the part's
surface, point against triangle on the CPU - about 70,000 cells a second. The same query against a
bounding-volume hierarchy on the GPU (Warp, `distance_gpu.py`) answers all 5.9 M cells of design #7's
band in 0.02 s, after 3 s to build the hierarchy once for the part: about 4,600× faster. In single
precision it misreads 0.6% of the cells within a few hundredths of a millimetre of the surface, by
up to 0.26 mm - thin triangles along fillets - so those cells need an exact recheck. libigl's
double-precision tree on the CPU is exact but only 1.7× faster than today's code.

## What the measurements rule out, and why

- **Code_Aster for the campaign:** exact, but 4-9× slower than cuDSS here and CPU-bound; it stays
  as the audit - the reference a sample of designs is re-solved against.
- **Iterative GPU solvers as the default:** PETSc GAMG on the GPU (23-35 s) and the CuPy AMG
  (51-58 s) are right to 10⁻⁹, but slower than cuDSS and their setup is CPU work. They are the
  fallback for a design whose factorisation outgrows the card.
- **JAX-FEM:** exact once it is handed the seat faces - its own face search loaded interior and
  neighbouring faces, 30 % extra area on one seat - but its assembly takes 90-110 s and 11.6 GB of
  host memory. Its value is gradients, for optimisation later, not throughput.
- **FEniCSx:** a valuable independent check (its own assembly, 7·10⁻⁸); 2-4 minutes on one core.
- **CHOLMOD:** exact, 1-5 minutes and 7-9 GB.
- **Voxel grids:** wrong in the direction that matters, and worse with refinement.
- **Cut cells:** promising for stress and for previews - no mesh, 9 s at 12 mm - but not yet accurate
  enough in bending for labels; quadratic cells need a grid multigrid solver first.

## Caveats

- Code_Aster ran sequential MUMPS on one core, with block low-rank compression and its memory capped
  at 3.7 GB, so factors went out of core; parallel MUMPS would be faster. agenticCAE's quadratic
  solve took 560 s on a cloud machine.
- The laptop ran other work at times: cuDSS's setup - its reordering, CPU work - rose from 13 s to
  37-68 s when a CPU-heavy job ran beside it. The table's figures are from quiet runs.
- PETSc on the GPU needs its multigrid setup's sparse products on the CPU
  (`-matmatmult_backend_cpu`, `-matptap_backend_cpu`); cuSPARSE's want more than 8 GB here.
- The cut-cell stiffness is integrated in single precision, so its matrix is factored by LU, not
  Cholesky.
