# Solver benchmark - results

Measured 14 September 2026 on the workstation (i7-13700HX 16 cores, 15.7 GB RAM, RTX 5060 Laptop 8 GB;
WSL Ubuntu 24.04 given 12 GB). Setup, cases and scripts: [README.md](README.md). Per-case tables with
every seat: `results/<case>/results.md`; the scripts' raw JSON records stay local. What every approach
means and what was learned, in plain words: [docs/research/design-to-solution.md](../../docs/research/design-to-solution.md);
why each solver got its result and why cuDSS: [docs/research/solver-choice.md](../../docs/research/solver-choice.md).

## The answer

**Solve TET10 on the GPU with cuDSS.** On design #7 (1.06 M unknowns) it gives Code_Aster's answer
to a relative field error of 3·10⁻¹⁰ - every metric identical to four decimals - in **13 s** against
Code_Aster's 57 s, using 5.2 GB of the card. With agenticCAE's own supports (an RBE2 per bolt, an
RBE3 per seat) it reproduces Code_Aster's `LIAISON_SOLIDE` + `LIAISON_RBE3` to 2·10⁻¹⁰, in 14 s.

**Build on the GPU and mesh straight from the field.** The slow route took 33 min to build design #7
and 103 min to mesh it with fTetWild. Built with the grid's distance on the GPU it takes 79 s and is
the same design; meshed from its field by CGAL, 46 s; with cuDSS, about 2.5 minutes a design, within
2.3 % of the slow route on every metric. See [The fast route](#the-fast-route---built-on-the-gpu-meshed-from-the-cleaned-surface)
and [Meshing straight from the field](#meshing-straight-from-the-field).

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

## Per design, the slow route

| Step | Design #7 | |
|---|---|---|
| Build at preview (3 mm field) | 1,962 s | the field's exact point-to-triangle distances in `window_between` |
| Decimate the surface, 2.5 M triangles to 0.2-0.4 M | 10 s | |
| Mesh, fTetWild | 1,871-6,174 s | 1.9 mm / 0.95 mm envelope |
| Assemble on the GPU | 4-8 s | |
| Solve, cuDSS | 13 s | |

At the slow route's build and mesh times a design takes 1-2.3 hours - 4,000 of them, 6-12 months one
at a time on this machine; their solves alone, 15 hours. What follows makes the build and the mesh
fast.

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
precision it misreads the cells nearest OCC's sliver triangles - chords across big faces, 570 mm long
and a millimetre high - by up to 0.43 mm (8,414 of the band's 5.9 M cells, all at the surface).
Split into pieces no longer than 16 mm - the same surface - it agrees with the exact answer to
0.004 mm on every cell, and needs no recheck (`build_gpu.py`). libigl's double-precision tree on the
CPU is exact but only 1.7× faster than today's code.

## The fast route - built on the GPU, meshed from the cleaned surface

The same design #7, end to end, in under three minutes instead of 2.3 hours:

| Step | Slow route | Fast route |
|---|---:|---:|
| Build at preview | 1,962 s | **79 s** - the grid's distance to the part on the GPU (`build_gpu.py`) |
| Mesh | 6,174 s - fTetWild | **73 s** - the field's surface remeshed evenly (58 s), repaired where it crosses itself (2 s), filled by gmsh's parallel mesher (9 s), made TET10 (`mesh_clean.py`) |
| Assemble on the GPU and solve | 57 s - Code_Aster | **10 s** - cuDSS |

**The build is the same design.** Not one of the field's 50.8 M cells changes side; its distances
agree to 0.005 mm; the surface has the same triangles, 8 of its 1.27 M vertices more than 0.01 mm
apart. The GPU's single precision misread the distance to OCC's sliver triangles - 570 mm long, a
millimetre high - so each long triangle is first split into pieces no longer than 16 mm, once for
the part; after that no cell differs by more than 0.004 mm from the exact CPU answer. What is left
of the build is contouring the surface (23 s), the checks (25 s) and moving faces (17 s).

**The mesh.** The field's dual-contoured surface - 2.54 M triangles - remeshed to 100,000 even
triangles within 1 mm of it, finer where it curves, its sharp edges kept. It crosses itself at 2,333
faces, nearly all on one 556 mm column where two sheets pass closer than the 3 mm grid; MeshFix
removes them and patches the gaps, within 2.4 mm of the design. gmsh fills that surface - kept as
given - with 167,713 tets: 985,905 unknowns, beside the slow route's 1,056,945; volume within
0.04 % of the design; 0.75 % of the tets thin slivers at the surface (TetGen made more, and failed
outright on the unrepaired surface).

**The answer**, against the slow route's Code_Aster:

| | Fast route | Slow route | |
|---|---:|---:|---:|
| BORE_AX1_S1 tilt | 0.5337' | 0.5256' | +1.5 % |
| BORE_AX1_S4 | 1.0723' | 1.0702' | +0.2 % |
| BORE_AX2_S2 | 1.1343' | 1.1306' | +0.3 % |
| BORE_AX2_S3 | 1.2877' | 1.2860' | +0.1 % |
| BORE_MAIN_S2 | 1.4695' | 1.4678' | +0.1 % |
| BORE_MAIN_S3 | 0.6647' | 0.6729' | -1.2 % |
| IMS gear-mesh lead | 0.3895 mrad | 0.3943 mrad | -1.2 % |
| HSS gear-mesh lead | 0.3671 mrad | 0.3660 mrad | +0.3 % |
| p99.9 von Mises | 114.8 MPa | 114.0 MPa | +0.8 % |
| Largest displacement | 0.8520 mm | 0.8540 mm | -0.2 % |

Within the 1.8-3.5 % the slow route's own two meshes differ by, and inside the accuracy the build
plan asks of the data. At about three minutes a design, 4,000 designs take eight days on this
machine one at a time.

### Meshing straight from the field

No surface at all: CGAL's mesher (Mesh_3, through pygalmesh, in WSL) asks the design's distance
field, point by point, whether it is inside and how far from the surface - trilinear across the
3 mm grid, exact within its band - and builds tets whose surface facets lie within a set distance of
where the field is zero, then removes slivers (`mesh_cgal.py`, finished by `finish_mesh.py`).

| | From the field (CGAL) | From the cleaned surface (gmsh) | Slow route (fTetWild) |
|---|---:|---:|---:|
| Mesh time | 46 s, + 5 s to make TET10 and label | 73 s | 6,174 s |
| Unknowns | 905,154 | 985,905 | 1,056,945 |
| Worst element quality | 0.175 - no slivers | 0.005 - 0.75 % slivers | 0.30 |
| Surface repair | none needed | 2,333 crossing faces patched | none |
| Boundary from the design's surface | median 0.3 mm, 99 % within 1.0 mm | within 2.4 mm | within 1.95 mm |
| Tilts against the slow route | within 2.3 % (worst seat +1.5 %) | within 1.6 % | - |
| Gear-mesh leads | -1.2 %, -0.3 % | -1.2 %, +0.3 % | - |
| p99.9 von Mises | -1.2 % | +0.8 % | - |
| Largest displacement | +0.2 % | -0.2 % | - |

Holding the facets within 2 mm of the surface gives these 905,154 unknowns; within 1 mm, 3.4 million -
CGAL refines every small fillet and hole to hold it - and neither its assembly nor cuDSS then fits
the 8 GB card. Nearly all of CGAL's 46 s is 18 million questions to the field answered in Python.

### The compiled field mesher

`cgal_field.cpp` answers CGAL's questions in C++ (`build_cgal_field.sh` builds it into WSL's
`fieldmesh` environment; `mesh_cgal.py` drives it; `--python` keeps the pygalmesh way). pygalmesh left
CGAL's surface tolerance at a thousandth of a sphere about the origin - up to 1.07 mm on the housing;
the compiled mesher puts boundary nodes within 0.005 mm of the field. Design #7, the same sizes as
above (cells 40, facets 30, facet distance 2 mm):

| | Time | Tets | Unknowns | Worst dihedral angle |
|---|---:|---:|---:|---:|
| pygalmesh | 46 s | 157,358 | 905 k | - |
| compiled, 1 core | 17.6 s (refine 1.3, perturb 7.4, exude 8.3) | 144,973 | 838 k | 10.0° |
| compiled, 4 cores | 4.4 s | 146,309 | 844 k | 9.0° |
| compiled, 1 core, sliver passes to 10° | 7.8 s | 148,728 | 849 k | 10.0° |
| compiled, no sliver passes | 1.1 s | 151,749 | 858 k | 0.2° - 1,839 slivers |

### Element sizes from rules

`sizes.py` computes a size map from the field - thickness along the inward normal, a concave curve's
radius from second differences, the rules, a growth rate - and `mesh_report.py` checks a mesh against
it. CGAL's tets come out at 0.81 and its boundary triangles at 0.75 of a regular tet's size for the
bound; the bounds are set that much looser. Design #7 (`results/design7sizes/`):

| Fine sizes where, panels | Unknowns | Mesh |
|---|---:|---:|
| every rib, fillet and hole of the housing, 20 mm (before calibration) | 43.8 M | 41 s |
| where the design changes, 20 mm (before calibration) | 10.9 M | 48 s |
| where it changes: 2 through its ribs, 20 mm | 2.00 M | 12 s |
| where it changes: 2 through ribs, fillets under their radius, 20 mm | 2.65 M | 16 s |
| where it changes: the agreed rules (16 round holes, fillets under half their radius), 20 mm | 2.73 M | 17 s |
| where it changes: 2 through ribs, 40 mm | 1.69 M | 9 s |
| where it changes: 2 through ribs, 40 mm, sizes growing 1 mm a mm | **1.49 M** | 9-14 s |
| - and fillets under their radius | 1.72 M | 10 s |
| - the agreed rules, 40 mm | 2.42 M | 13-19 s |

The 1.49 M mesh against the coarse one (0.84 M), agenticCAE's couplings, cuDSS: worst tilt +2.8 %,
largest displacement +6.4 %, p99.9 +4.7 %, p99 +8.2 %. cuDSS, part of its factor in host memory:
10 s to factorise and 0.1 s to solve at 1.49 M; at 2.4 M it fails (`EXECUTION_FAILED`). The GPU
assembly sums its pieces in host memory past 1.6 M unknowns - at 2.42 M it ran the card out.

## The gate - the production housing's field against its CAD

The production housing (`254492_0_closed_volume.step`, `gate_part.py`), meshed four ways to the element
sizes of agenticCAE's own mesh of it (`sizes_from_mesh.py`), labelled alike (`labels.py --within 2.0`),
solved by Code_Aster with agenticCAE's couplings; compared by `gate_compare.py` into
`results/gate/*.json`. The whole account: [../../docs/research/field-meshing-gate.md](../../docs/research/field-meshing-gate.md).

| Mesh | Made by | Tets | Unknowns | Mesh | Code_Aster |
|---|---|---:|---:|---:|---:|
| A - the CAD's surface | `gate_cad.py`, the 0.5 mm triangulation, seat circles | 220,337 | 1.19 M | 12.6 s | 2 min 25 s |
| B - the 3 mm field | `mesh_cgal.py --lines`, seat circles 8 mm apart | 216,439 | 1.17 M | 7.9 s | 2 min 16 s |
| B2 - B from another start | `--seed 1` | 217,034 | 1.17 M | 7.0 s | 2 min 17 s |
| C - agenticCAE's route | `gate_regular.py` (its own code, `GATE_REGULAR=agentic`) | 204,091 | 1.10 M | 17 s | 2 min 32 s |

Seat tilts from the reference nodes, per cent:

| | A vs B | B vs B2 | A vs C |
|---|---:|---:|---:|
| BORE_AX1_S1 | +7.0 | -7.2 | +20.5 |
| BORE_AX1_S4 | +1.1 | -1.0 | +1.2 |
| BORE_AX2_S2 | +3.2 | -2.8 | -53.5 |
| BORE_AX2_S3 | +0.7 | -0.8 | -0.6 |
| BORE_MAIN_S2 | -0.4 | -2.3 | -7.3 |
| BORE_MAIN_S3 | +0.4 | -1.7 | -1.5 |
| IMS lead | +0.1 | +2.7 | -2.1 |
| HSS lead | +0.9 | -0.2 | +4.2 |
| p99.9 von Mises | -0.3 | -2.3 | -1.9 |
| largest displacement | -0.6 | -2.0 | -4.7 |
| displacement map | 1.2 | 2.1 | 3.8 |
| stress map, element by element | 17.4 | 17.7 | 19.6 |

The field against the CAD differs by what meshing the same field twice does. C leaves out six CAD
faces (lids 241.6, 134, 79 mm), its worst element quality is 6·10⁻⁵, and its repair cuts up to 24.6 mm
into metal under seat AX2_S2 (`gate_geometry.py`, `results/gate/section_ax2.png`). Snapping A's and
B's boundary nodes onto the CAD (`snap_to_cad.py`) left the gap as it was (worst tilt 6.4 %) and
distorted elements (stress map 27 %, peak +16 %); one snapped mesh failed in Code_Aster.

What did not work on the way: gmsh on the STEP itself (a wire it cannot fix, a 1D mesh that does not
close); CGAL finding every sharp CAD edge itself (past 15 minutes, 9.5 GB); size rules written for the
gate (2.4-2.9 M unknowns, past Code_Aster's memory in WSL); seat circles at the element size (a
shoulder cut off) or 3 mm apart (seats too dense - Code_Aster's coupling wanted 8.2 GB); the bolt
holes' circles too (408,289 tets); labels by nearest face alone (triangles across a seat's edge) or by
corners within 1 mm of the cylinder (the field's seats 11-26 % short).

MMG, the other way to mesh from a field - the field's grid cut into tets, cut again at the zero of
the distance and remeshed - refined instead of coarsening: on a crop of the housing it turned 2,484
tets into 12,000-26,000 whatever the target size, chasing the facets the lattice cut leaves, and on
the whole design it had not finished after 15 minutes on one core (`mesh_field.py`).

## What the measurements rule out, and why

- **Code_Aster for the campaign:** exact, but 4-9× slower than cuDSS here and CPU-bound; it stays
  as the audit - the reference a sample of designs is re-solved against.
- **Iterative GPU solvers as the default:** PETSc GAMG on the GPU (23-35 s) and the CuPy AMG
  (51-58 s) are right to 10⁻⁹, but slower than cuDSS and their setup is CPU work. PETSc is not used in
  the route; cuDSS keeping part of its factor in host memory reaches 1.49 M unknowns.
- **JAX-FEM:** exact once it is handed the seat faces - its own face search loaded interior and
  neighbouring faces, 30 % extra area on one seat - but its assembly takes 90-110 s and 11.6 GB of
  host memory. Its value is gradients, for optimisation later, not throughput.
- **FEniCSx:** a valuable independent check (its own assembly, 7·10⁻⁸); 2-4 minutes on one core.
- **CHOLMOD:** exact, 1-5 minutes and 7-9 GB.
- **Voxel grids:** wrong in the direction that matters, and worse with refinement.
- **Cut cells:** promising for stress and for previews - no mesh, 9 s at 12 mm - but not yet accurate
  enough in bending for labels; quadratic cells need a grid multigrid solver first.
- **fTetWild for the campaign:** robust, but 26-103 minutes a design whatever it is given.
- **gmsh re-parametrising the surface:** stalled past 30 minutes; gmsh filling a surface given as it
  is works, in 9 s.
- **TetGen:** fast, but slivers, and it refuses a surface that crosses itself.
- **MMG on the field's grid:** refines instead of coarsening; past 15 minutes on one core.

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
- The GPU build and both fast meshers are bench trials: `build_gpu.py` swaps the build's distance
  function in at run time, and the meshers run beside the product, not in it.
- Accuracy of the fast routes is against the slow route's Code_Aster answer, itself a 20 mm TET10
  mesh; its own two meshes differ by 1.8-3.5 %, so differences below that are within the meshes'
  own uncertainty, not errors of the route.
