# Solver benchmark

Which way should fastcae solve thousands of generated designs? Every candidate solves the same
design with the same load case, supports, material and metrics, and is judged against Code_Aster -
agenticCAE's solver on this housing - on accuracy, time and memory. Results: [RESULTS.md](RESULTS.md);
each case's table in `results/<case>/results.md`. The scripts' raw JSON records are written into
`results/` locally and kept out of the repository; running a script again writes them again.

A measurement harness for today's study, the GRC housing - not product code: the seats, loads and
bolt circle are agenticCAE's, written in `common.py`, and the scripts read a scratch copy of the
project, never the user's.

## The setup - agenticCAE's, applied the same way by every solver

- **Load case:** agenticCAE's DLC 1.3 extreme (low-speed shaft 401 kN·m): a force on each of the six
  loaded bearing seats, from `agenticCAE/assets/loads.json`.
- **Material:** cast iron, E 169,000 MPa, ν 0.275, as agenticCAE solved it.
- **Supports:** the flange's 25 bolt positions - each 55 mm counterbore and the through-hole under it
  - held. Every node on those hole surfaces is fixed. (agenticCAE tied each position rigidly to a
  point on its axis and held that point, which leaves the hole free to rotate about it; holding the
  surface is a little stiffer. `solve_aster.py couplings` runs agenticCAE's exact couplings for the
  check below.) The flange's other holes - tapped holes, dowel holes, a port - are not bolts.
- **Loads:** each seat's force as a uniform traction, force over area, on its cylindrical surface.
- **Metrics** (agenticCAE's): each seat's tilt (arc-minutes) from its best-fit rigid rotation; the
  IMS gear-mesh lead misalignment (µm over the face width) from the two shafts' skews; the
  volume-weighted 99.9th-percentile von Mises stress (MPa) - the peak chases singularities; the
  largest displacement (mm); the sum of reactions, which must balance the loads. Computed the same
  way from every solver's displacement (`tet10_post.py`, `common.py`), so the solvers differ only in
  their answer.

## Cases

- **design7** - design #7 of the 20-design campaign `w4zf5` (6 variants: 15 ribs, 11 pads), rebuilt
  on a scratch copy of the project at preview (3 mm) and meshed by fTetWild (20 mm edges, 0.95 mm
  envelope) as TET10: 1,056,945 unknowns.
- **design7b** - the same design meshed coarser (1.9 mm envelope, lighter optimisation): 648,165
  unknowns - the mesh-sensitivity check.
- **e56235** - agenticCAE's production design, on agenticCAE's own gmsh mesh made TET10 (1,098,279
  unknowns), for which agenticCAE recorded a Code_Aster answer.

## Candidates

| | Where | What |
|---|---|---|
| `solve_aster.py` | WSL | **The reference.** Code_Aster 18, MUMPS with block low-rank - agenticCAE's settings. |
| `solve_gpu_tet10.py cudss` | Windows, GPU | NVIDIA cuDSS: sparse Cholesky on the GPU (nvmath-python). |
| `solve_gpu_tet10.py amg_gpu` | Windows, GPU | Conjugate gradient on the GPU (CuPy), smoothed-aggregation AMG levels from PyAMG with the rigid-body modes, Chebyshev V-cycles on the GPU. |
| `solve_petsc.py` | WSL, GPU | PETSc 3.25 CG + GAMG with the matrix on the GPU (cuSPARSE); the same on the CPU; CHOLMOD. |
| `solve_fenicsx.py` | WSL | FEniCSx 0.11, P2 elements, its own assembly: PETSc CG + GAMG, and MUMPS. |
| `solve_jaxfem.py` | WSL, GPU | JAX-FEM 0.0.12, TET10: assembly by automatic differentiation on the GPU, cuDSS for the solve. |
| `solve_warp_voxel.py` | Windows, GPU | No mesh: the design's grid as trilinear hexes (NVIDIA Warp, NanoVDB), CG with a diagonal preconditioner. |
| `solve_fcm_warp.py` | Windows, GPU | No mesh, cut cells: the finite cell method on Warp - cells the surface cuts integrated at sub-cell points against the true surface, seat loads and a bolt penalty on the real surface; cuDSS. |

## Running it

A Windows virtual environment with `fastcae`, `warp-lang`, `cupy-cuda12x[ctk]`, `nvmath-python[cu12]`,
`nvidia-cudss-cu12`, `pyamg`, `pytetwild`, `fast-simplification`; micromamba environments in WSL:
`aster` (code-aster 18.0.12), `fenicsx` (fenics-dolfinx 0.11), `petscgpu` (petsc 3.25 built with CUDA,
run with `PETSC_OPTIONS=-use_gpu_aware_mpi 0`), `jaxfem` (jax[cuda12] 0.11, jax-fem 0.0.12, nvmath).

```
python export_design.py 6          # design #7: surface, field, seats and bolt holes
python cylinders.py                # the seats' and bolt holes' cylinders, off the CAD
python mesh_tet10.py 20            # TET10, 20 mm  (BENCH_CASE picks the case folder)
python labels.py design7           # seats and the 25 bolt positions on the mesh
python solve_gpu_tet10.py cudss amg_gpu
python solve_gpu_tet10.py couplings              # agenticCAE's RBE2/RBE3 supports, cuDSS
wsl: micromamba run -n aster python solve_aster.py <case dir> clamped|couplings
wsl: solve_petsc.py, solve_fenicsx.py, solve_jaxfem.py <case dir>
python solve_warp_voxel.py 6 5     # no mesh: the grid
python solve_fcm_warp.py 12 10     # no mesh: cut cells
python compare.py design7          # the table
python check_couplings.py e56235   # the GPU's couplings against Code_Aster's
```

`case_e56235.py` builds the second case from agenticCAE's mesh; `labels.py e56235` labels it.
`system_tet10.py` assembles the TET10 system on the GPU once for every solver that reads it.
Beyond the solvers: `mesh_gmsh.py` tries gmsh in place of fTetWild, and `distance_gpu.py` times the
build's slowest step - the grid's exact distance to the part - on the GPU and against libigl.

The fast route: `build_gpu.py` rebuilds the design with that step on the GPU (a trial - it swaps the
function at run time, the product code unchanged); `mesh_clean.py 20 25 1.0 --gmsh` remeshes the
field's surface, repairs it and fills it with gmsh; `against_baseline.py design7gpu` sets the
answer beside the slow route's. Needs `pymeshlab`, `pymeshfix`, `gmsh` (and `tetgen` to try it).
Straight from the field: `mesh_cgal.py` in WSL - compiled (`cgal_field.cpp`, built into the
`fieldmesh` environment by `build_cgal_field.sh`: conda-forge python 3.12, numpy, scipy, cgal-cpp,
tbb-devel, pybind11, cxx-compiler), or `--python` through pygalmesh in the `galmesh` environment -
then `finish_mesh.py cgal_tets.npz`; `mesh_field.py` is the MMG attempt (`mmgpy`). Its options:
`--sizes` (a size map from `sizes.py`, or from another mesh by `sizes_from_mesh.py`), `--lines` (edge
circles from `interface_lines.py [--seats]`) with `--edge` spacing, `--threads`, `--seed`, the sliver
passes. `mesh_report.py` checks a mesh against its size map.

The gate, on the production housing: `gate_part.py` (its field and surfaces, in a scratch project),
`gate_regular.py` (agenticCAE's gmsh-weld-collapse-MeshFix route, `GATE_REGULAR=agentic` for its own
sizes), `gate_cad.py` (the compiled mesher on the CAD's triangulated surface), `gate_gmsh.py` (gmsh on
the STEP itself - it does not mesh it), `labels.py <case> --within 2.0`, `solve_aster.py <case>
couplings`, `gate_compare.py <reference> <test> --out ...`, `gate_geometry.py` (where each mesh
leaves the CAD), `snap_to_cad.py` (boundary nodes onto the CAD - measured, not used).

Two things to know when running on one 8 GB card and 16 GB of RAM: run one GPU job at a time - a
PETSc or CuPy process keeps its GPU memory pool until it exits - and run Code_Aster from a Linux
directory (`$ASTER_RUNS`): MUMPS writes its factors there, and through WSL's bridge to a Windows
drive that crawls.
