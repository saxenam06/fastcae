<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# I want to reduce computational time of build and mesh stages so that I can achieve creating data for 4000 designs in few hours than in days.. what are the options.. can you do a deep research.. search all the papers, github repos, libraries that can help us to reduce the time..

Here are all the details that may be relevant for you...
Here's where things stand, as far as this conversation shows. I can't see what any other agent is doing right now.
Committed
Variants and campaigns: named variants on the CAD, the three-step campaign card, and CP-SAT repair (drops the fewest pieces so every combination rule holds). Commits dac5e2b, f6aa0bf, 1dc28b2.
Research and plan docs, including the next-phase plan (95b160e).
The solver benchmark on design \#7:
TET10 solved by cuDSS on the GPU matches Code_Aster to 3·10⁻¹⁰ in 13 s, against 57 s.
Our setup reproduces agenticCAE's recorded answer within 10%.
How the bolts are held changes the answer by 40%.
Commits 8605847, 8648511, 594fd46, 5099525, bd614ce, and the results page is published.
Built but not committed: the fast route (bench scripts only, nothing in src/ changed)
Build on the GPU: 79 s instead of 33 min, with an identical field once long triangles are split.
Mesh straight from the field with CGAL: 46 s, 905k unknowns, no slivers, no repair needed.
The alternative, a cleaned surface filled by gmsh, takes 73 s.
MMG was tried and dropped.
Solve with cuDSS: about 5 s.
Result: within about 2% of the slow baseline, about 2.5–3 minutes per design, so 4,000 designs in roughly 8 days on this machine.
Waiting on you
Commit the fast-route scripts and results?
Bring the GPU build and field meshing into the product?
Supports: agenticCAE's bolt ties or clamped holes?
Still open from before: the job runner, the optimisation approach, the next-batch mix, and rib thickness from the floor.
Agreed but not started
The first fixes:
rib height from what a rib actually meets;
no floor thickening;
holes that look see-through;
builds that finish in the background;
the self-crossing surface from dual contouring.
CP-SAT as a generator (the "chosen" pattern, which gives layouts outside the known families) is planned but not built. Until then, variety is still limited to the pattern families.
The "4,000 runs copied under your housing" message you quoted earlier came from another agent. I can't confirm its state from here.
how much time that is expected to take for 4000 designs-> a variant -> build -> mesh -> solve
About 7–8 days one design after another on this laptop with the fast route, or roughly 2–3 days if several designs run in parallel. That's extrapolated from one measured design, \#7.
Per design, measured on design \#7
StepTime
Place the variants and screen (campaign)
well under 1 s
Build (distance step on the GPU)
~79 s
Mesh (CGAL from the field, plus TET10 and labels)
~51 s
Labels, assembly and cuDSS solve
~15 s
File handling and overhead
~5–10 s
Total
~2.5 min (~3 min with the cleaned-surface mesher)
For 4,000 designs
One at a time: 4,000 × 2.5–3 min is about 170–200 hours, so 7–8 days.
Several in parallel: the build and mesh mostly run on one core each, so 3–4 designs could run at once, limited by the 16 GB of RAM. The GPU solve takes only about 10 s per design, so it would queue fine. That gives roughly 2–3 days. This is an estimate, not measured.
The old route, for comparison: about 2.3 hours per design, over a year for 4,000.
What could move this
Faster (likely):
CGAL's 18 million field queries run in Python; compiled code would cut the 46 s to a few seconds.
The build's remaining steps (checks 25 s, contouring 23 s, moving faces 17 s) are the next targets.
Together that could make it roughly 1 minute per design, about 3 days one at a time or about 1 day in parallel. That's my estimate.
Slower:
Designs that move many faces took far longer before; that's not re-measured with the GPU build.
Designs over about 1.1–1.2M unknowns don't fit cuDSS on the 8 GB card and would fall back to the PETSc GPU solver, about 35 s.
Failures and retries.
Not in the product yet: the fast route is a bench trial. It still has to be built into the pipeline with a job runner before a 4,000-design run.
where we have used Nvidia warp?
Warp is used in four places, all bench scripts in bench/solvers/. It isn't used in the product (src/), where it isn't a dependency yet.
The voxel solver (solve_warp_voxel.py). Design \#7's field is resampled to a grid of cubes, and each solid cell becomes a hex element on a sparse NanoVDB grid. Warp FEM assembles the stiffness on the GPU and solves it with its conjugate gradient and a diagonal preconditioner.
6 mm: 2.29M unknowns, 51 s, worst tilt +13.8% against Code_Aster.
5 mm: 3.77M unknowns, 109 s, +16.8%.
4 mm: ran out of GPU memory.
The cut-cell solver (solve_fcm_warp.py). Warp finds which cells the surface cuts, using its GPU mesh queries. Warp FEM integrates those cells at sub-cell points, puts the seat loads and a bolt penalty on the real surface, and assembles the system. cuDSS then solves it. On design \#7:
12 mm: 9 s, worst tilt −6.1%.
10 mm: 43 s, −5.9%.
Quadratic cells and 8 mm: ran out of GPU memory.
The distance benchmark (distance_gpu.py). It times the build's slowest step, each grid cell's exact distance to the part, as Warp nearest-point queries on the GPU. That's 5.9M cells in 0.02 s, about 4,600× faster than the CPU. This is also where the single-precision misreads on OCC's long, thin triangles showed up.
The GPU build (build_gpu.py). It swaps the build's distance function for those Warp queries, after splitting long triangles to 16 mm or less. Design \#7 builds in 79 s instead of 1,962 s, with an identical field.
The TET10 GPU solvers that won the benchmark (cuDSS, and the CuPy multigrid) don't use Warp; they use CuPy and nvmath. In the fast route, Warp's only role is the GPU build.
explain this -> , Warp's only role is the GPU build.
In the fast route (build, then mesh, then solve), Warp is used in only one step: building the design. Specifically, it handles the build's distance calculation. The other steps use different tools.
What Warp does in the build. Building a design means turning its ribs and pads into the design's 3D shape: a distance field on a 3 mm grid, and a surface. The slow part was working out, for millions of grid cells, how far each cell is from the part's surface. The CPU did this one point against one triangle at a time, about 70,000 cells a second, which is why design \#7 took 33 minutes.
Warp puts the part's triangles into a fast search structure on the GPU and answers "nearest point on the surface" for every cell in parallel: 5.9 million cells in 0.02 s. The part's very long, thin triangles are first split into pieces no longer than 16 mm, so the answers match the CPU exactly. The whole build then takes 79 s instead of 33 minutes, with an identical result.
What Warp doesn't do in the fast route:
Meshing is done by CGAL from the field, or by MeshLab plus MeshFix plus gmsh on the cleaned surface.
Assembling the stiffness is done on the GPU with CuPy.
Solving is done by cuDSS, NVIDIA's GPU direct solver, through nvmath-python.
Where else Warp appeared. In the benchmark, two solvers were built on Warp: solving directly on the voxel grid, and the cut-cell method. Both avoid meshing, but they were 6–17% off on bearing tilt, so they weren't chosen. That leaves the build as Warp's only job in the route we're keeping.
how did we build now in Build (distance step on the GPU)? which cost 79s? will be able to reduce that time with warp?
How the 79 s build worked
It ran the normal product build for design \#7, unchanged except for one function, swapped at run time by the bench script build_gpu.py. Nothing in src/ changed.
The swapped function measures how far each grid cell is from the part's surface. It's the step that had taken about 30 of the 33 minutes.
The Warp version:
The part's CAD triangles (133k from OCC) have their very long, thin ones split into pieces no longer than 16 mm, giving 1.49M triangles. This happens once per part and takes 3 s.
Warp puts them in a GPU search structure, a BVH.
A GPU kernel works out each cell's position from its index and asks for the nearest point on the surface, for millions of cells in parallel.
The same triangles are selected as the product code selects, and the old cached result was set aside so the step really recomputed.
The result: the distance step took about 8 s in total, 117M cells over 9 calls. The design came out identical.
Where the 79 s goes now (steps overlap slightly)
StepTime
Design checks
25 s
Contouring the surface from the field (dual contouring)
23 s
Moving faces: floor thickening and pads
17 s
The GPU distance itself
~8 s + 3 s split (once per part)
Blending ribs into the field (compose)
2.5 s
Loading, screening, saving
a few s
Can Warp cut it further? Yes, but by moving other steps to the GPU. The distance step is already done.
Moving faces (17 s): it still makes nearest-face queries on the CPU (a KD-tree). The same kind of GPU nearest-point query should bring it to a few seconds.
Checks (25 s): many are geometric measurements, like thickness, gaps and fillet radii. Those could use GPU ray and nearest-point queries. I haven't profiled inside them, so I can't say which parts would move.
Contouring (23 s): each cell's vertex is solved independently, so it suits the GPU. But the surface code's handling of pieces and topology is intricate, so this is the most work.
The 3 s split can be cached per part.
My rough estimate, not measured: moving face-moving and the heavy checks to the GPU could bring a build down to about 20–30 s, and GPU contouring could take it lower. Some time will stay as Python overhead and I/O.
Before any of this counts, the GPU distance (with the triangle split) has to go into the product code with tests, and Warp becomes a dependency. So far it's only a bench trial.
explaion plain.y u said build took 79 s and now u sayu it tool 33 mins
Both numbers are right. They're the same design built two ways: before and after the change.
33 minutes: the normal way (before)
This is how the product builds a design today.
One step, measuring how far each point of the grid is from the part's surface, runs on the CPU and checks point after point.
That one step took about 30 of the 33 minutes.
79 seconds: with the GPU (after)
The same build, run by a test script.
Only that slow step was swapped for a GPU version (Warp), which checks millions of points at once.
That step dropped from about 30 minutes to about 8 seconds.
Everything else stayed the same, and together the other steps take roughly 70 seconds.
The result is the same. The design came out identical either way.
The catch. The 79-second version exists only in the test script (bench/solvers/build_gpu.py). The app itself still builds the slow way, 33 minutes, until the GPU step is added to the product code.
so wer already used warp in 79s build?
Yes. The 79-second build already used Warp, but only for one step and only in a test script.
What Warp did. It measured the distance from every grid point to the part's surface on the GPU, millions of points at once. That's the step that used to take about 30 of the 33 minutes. With Warp it took about 8 seconds.
What didn't use Warp. The rest of the build still ran on the CPU as before:
the checks, about 25 s;
making the surface from the field, about 23 s;
moving faces, about 17 s.
Together those make up most of the remaining ~70 seconds.
Where it ran. Only in the test script bench/solvers/build_gpu.py. The app itself doesn't use Warp yet; it still builds the slow way until the GPU step is added to the product code.
so how much we can resuce this time with warp
Warp could probably bring the build from 79 s down to about 20–30 s, and maybe further. These are my estimates from the timings, not measurements.
Where the 79 s goes now
StepTimeCan Warp help?
Design checks
25 s
Partly: the geometric measurements (gaps, thickness, fillets) could use GPU queries
Contouring the surface from the field
23 s
Yes, but it's the most work to move to the GPU
Moving faces (floors, pads)
17 s
Yes, easily: it still does nearest-face searches on the CPU
Splitting long triangles
3 s
No Warp needed: done once per part, so it can be cached
Distance step (already on Warp)
~8 s, counted inside the rows above
Already done
Blending ribs in, loading, saving
~7–8 s
Little
Likely savings, in steps
Cache the triangle split and move face-moving to the GPU: 79 s to about 60 s. Easy.
Also move the heavy checks to the GPU: to about 40–50 s. Medium, and I haven't profiled inside the checks.
Also move contouring to the GPU: to about 20–25 s. Hard.
Floor: about 10–15 s would remain for Python overhead, loading and saving, whatever is done.
What that means per design. The build is only part of it; meshing takes about 51 s and solving about 15 s. With the build at about 25 s, a design takes roughly 1.5 minutes instead of 2.5. If CGAL's field lookups were also moved into compiled code (46 s down to a few seconds), a design would take roughly 40–60 s. That puts 4,000 designs at about 2–3 days one at a time, or under a day running several in parallel.

Yes—but **not by simply applying more Warp to the existing 79-second build**. The credible route to 4,000 designs in hours is to combine **work elimination, cached geometry/fields, compiled meshing, mesh reuse, staged scheduling, and—if all designs must be solved—more than one GPU or fewer high-fidelity evaluations**.

# Build–Mesh Acceleration Study

## Bottom line

Your current measured build-plus-mesh time is approximately:

$$
79 + 51 = 130\text{ seconds/design}
$$

For 4,000 designs, that is about **144 hours, or six days**, before solving. To finish build and mesh in six hours, the system must sustain one completed design every **5.4 seconds**; for four hours, the budget is **3.6 seconds/design**.

That target is unlikely with independent high-quality remeshing of every design on one laptop. It becomes plausible through one of these architectures:


| Strategy | Expected role | Realistic outcome |
| :-- | :-- | --: |
| Optimize present Warp + CGAL route | Lowest-risk production path | 20–40 s build+mesh |
| Reference-mesh morphing by design family | Fast path for topology-preserving variants | Potentially seconds/design |
| Cached base SDF plus local updates | Fast path for localized ribs/pads | Potentially 3–15 s build |
| Fixed-grid CutFEM/FCM | Eliminates conforming meshing | Research path; accuracy work required |
| 8–16 worker equivalents | Throughput rather than latency | 4–8 hours at 30–60 s/design |
| Active/multi-fidelity sampling | Avoids 4,000 expensive runs | Often the best dataset strategy |

## Critical throughput limit

Your complete labels–assembly–solve stage currently costs around 15 seconds/design. Even if build and mesh took zero time, serial execution of this stage would require:

$$
4000 \times 15\text{ s}=16.7\text{ hours}
$$

The actual cuDSS solve is around five seconds, giving an absolute single-GPU solve-only floor near **5.6 hours**, assuming perfect utilization and no assembly or transfer overhead. Consequently:

- **Build and mesh in a few hours:** possible with mesh reuse or enough CPU workers.
- **Build, mesh, and solve in under six hours:** extremely tight on one GPU.
- **End-to-end in three to five hours:** likely requires two or more GPUs, aggressive batching/reuse, or solving fewer designs at high fidelity.


## Highest-impact finding

The best next step is **not GPU dual contouring**. It is determining whether contouring is needed at all.

Your retained meshing route constructs the tetrahedral mesh directly from the scalar field. If the 23-second dual-contouring stage only creates a visualization/intermediate surface, introduce a `mesh_only` build mode and bypass it. That would remove nearly 30% of the current 79-second build without writing another GPU kernel.

The same “delete rather than accelerate” principle applies to:

- Floor thickening, which is already scheduled for removal.
- Repeated surface exports and imports.
- Repeated construction of the static housing field.
- Geometry checks that can run before the expensive build.
- Expensive optimization passes on every mesh.
- Recomputing labels that can be inherited from field provenance or a reference mesh.


## Recommended architecture

### Static family cache

Create one cache for each housing and pattern family containing:

- Cleaned OCC triangulation.
- Long-triangle split result.
- Persistent Warp mesh and BVH.
- Base housing signed-distance field.
- Bounding boxes for every editable feature.
- Surface and volume labels.
- One or more validated reference TET4/TET10 meshes.
- Fixed support, load and contact lookup data.
- A geometry hash and software-version hash.

OpenVDB supports sparse level sets, mesh-to-volume conversion and sparse field operations; NanoVDB provides a GPU-oriented portable representation suitable for accelerated sparse-volume processing. These are strong candidates if the present dense field contains large inactive regions.[^1_1][^1_2]

### Per-design build

For each accepted CP-SAT configuration:

1. Load the immutable base field by reference, not by copying.
2. Evaluate only the changed rib, pad and hole regions.
3. Represent simple features analytically as capsules, boxes, extrusions or swept SDFs.
4. Compose the local fields on the GPU.
5. Record the winning primitive ID while composing the field, providing label provenance.
6. Run inexpensive field-based checks.
7. Skip surface extraction unless visualization or a fallback mesher requires it.
8. Send the field directly to the compiled mesher.

OpenVDB’s CSG routines operate using sparse traversal, and its grid transformations and value operations support multithreaded execution. This matches a workflow where most of the housing remains unchanged while only localized design features vary.[^1_2]

### Meshing decision

Use a three-route decision tree:


| Geometry change | Route | Reason |
| :-- | :-- | :-- |
| Same topology, moderate deformation | Reference-mesh morphing | Avoid complete remeshing |
| Topology changes but field is valid | Compiled CGAL implicit meshing | Current proven route |
| Surface is defective or field route fails | fTetWild fallback | Robust triangle-soup handling |

The routing decision should use inexpensive indicators such as topology signature, predicted minimum Jacobian after morphing, feature clearance and local field complexity.

## Optimize the current build

### Cache the base queries

The raw Warp nearest-point kernel already processed 5.9 million points in approximately 0.02 seconds. The eight-second distance-stage total therefore appears dominated by repeated calls, BVH/setup work, host-device movement, array preparation, synchronization or processing substantially more than one grid.

Recommended changes:

- Construct the split base mesh and Warp BVH once per worker.
- Keep grid coordinates resident on the GPU.
- Avoid regenerating identical point arrays for every design.
- Batch all active regions into one launch where possible.
- Keep the base SDF resident on the device.
- Transfer only the final narrow-band field or compact active blocks.
- Measure with synchronized GPU timers; Warp notes that device work must be synchronized to obtain complete execution timing.[^1_3]

Warp caches compiled modules, and NVIDIA recommends declaring kernels before the initial module load, limiting runtime specialization, disabling backward generation when gradients are unnecessary, and using ahead-of-time compilation for controlled deployments. For a production campaign, build CUBINs for the laptop’s GPU architecture and start persistent workers before timing the campaign.[^1_4]

### Replace face movement

The 17-second moving-faces stage should not merely be ported line-by-line to Warp. Refactor it around field composition:

- Remove floor thickening.
- Express pads and simple moved features directly as signed-distance primitives.
- Evaluate only feature bounding boxes plus blend radius.
- Use a single GPU kernel for distance, feature ownership and blend.
- Preserve the old CPU path only as a validation oracle.

If an exact closest-face calculation remains necessary, reuse the same persistent Warp acceleration structure already used for distance queries.

### Split the checks

The 25 seconds of checks should be divided into three levels:


| Level | Timing | Examples |
| :-- | :-- | :-- |
| Parameter checks | Before build | Rib bounds, overlap rules, minimum parameter thickness |
| Field checks | After local composition | Gaps, connectivity, local thickness, enclosed voids |
| Surface/mesh checks | After meshing | Jacobian, inverted elements, missing labels, boundary integrity |

Only the last category requires a complete geometric representation. This prevents an invalid design from consuming build and mesh time and avoids repeatedly triangulating geometry merely to measure quantities available from the field.

### Remove Python callbacks

Your estimate that CGAL performs approximately 18 million field evaluations through Python is probably the single clearest mesh-stage bottleneck. CGAL’s meshing engine accepts implicit functions and labeled image domains and provides shared-memory parallel algorithms through `Parallel_tag` and TBB.[^1_5]

Implement the field oracle in C++:

- Own the field in a contiguous or sparse C++ structure.
- Perform trilinear lookup entirely in C++.
- Return inside/outside, material label and sizing value without re-entering Python.
- Release the Python GIL for the complete meshing operation.
- Return mesh arrays through zero-copy buffers where practical.
- Avoid a Python call for each point.

Python/C++ bindings require the GIL when invoking Python objects, so calling a Python field function from CGAL’s inner loop obstructs both latency and parallel scaling. Python should configure the mesher once; it should not participate in the millions of geometry predicates.[^1_6]

### Tune CGAL

CGAL Mesh_3 supports shared-memory meshing and optimization with `Parallel_tag`; its default mesh generation activates perturbation and exudation unless explicitly disabled. Run an ablation over:[^1_5]

- Sequential versus `Parallel_tag`.
- 1, 2, 4 and 8 TBB threads per design.
- One multithreaded mesh versus several single/dual-thread meshes.
- `no_perturb().no_exude()` followed by your own quality acceptance.
- Bounded perturb/exude only when the raw mesh violates requirements.
- Relaxed `facet_distance` away from bolts, loads and thin ribs.
- Spatially varying `cell_size`.
- Warm-start/refinement from a reusable triangulation where compatible.

For campaign throughput, four one- or two-thread mesh jobs may outperform one eight-thread job. Benchmark **designs/hour**, not only seconds for one mesh.

## Mesh reuse

### Reference morphing

For variants that retain topology, morphing a validated reference mesh is likely the only route to consistently approach a few seconds/design.

PyGeM supports free-form deformation, radial basis functions and inverse-distance weighting for CAD and computational meshes, including STEP, STL, UNV, OpenFOAM and LS-DYNA formats. Research using direct computational-mesh deformation reports that preserving mesh topology can avoid additional meshing while enabling reduced-order workflows.[^1_7][^1_8]

A practical implementation would:

1. Cluster designs by rib layout and topology signature.
2. Generate one high-quality TET10 mesh per family.
3. Identify control points on moved ribs, pads, seats and holes.
4. Propagate their displacement using compact-support RBF or FFD.
5. Reproject designated boundary nodes.
6. Recompute Jacobians and midside-node positions.
7. Accept the morphed mesh if quality thresholds pass.
8. Fall back to CGAL otherwise.

This route will not work when ribs appear or disappear, holes merge, connectivity changes, or deformation collapses elements. It therefore needs a deterministic quality gate rather than an assumption that every family is morphable.

### Local remeshing

Local cavity remeshing is attractive when only a small region changes, but it is considerably harder to make reliable with TET10, labels and conforming interfaces. CGAL supplies tetrahedral remeshing operations including edge splitting, collapsing, flipping and vertex relocation. ParMmg provides distributed 3D volume mesh adaptation, although its published scope and your failed MMG trial make it a lower-priority option for this laptop pipeline.[^1_9][^1_10]

Recommendation: implement family-level morphing first. Attempt local cavity remeshing only if the morphing fallback rate remains too high.

## Mesher alternatives

| Tool | Use case | Recommendation |
| :-- | :-- | :-- |
| **CGAL Mesh_3** | Implicit/labeled field to quality tetrahedra | Keep as primary; compile the oracle and enable TBB selectively [^1_5] |
| **Gmsh HXT** | Parallel tetrahedralization from a valid surface/CAD model | Benchmark as the primary challenger [^1_11] |
| **fTetWild** | Imperfect or non-watertight triangle soups | Use as robust fallback [^1_12][^1_13] |
| **PyTetWild** | Fast Python integration of fTetWild | Useful for experimentation [^1_14] |
| **PyGeM** | Reusable mesh deformation | High priority for topology-stable families [^1_7] |
| **OpenVDB/NanoVDB** | Sparse SDF, CSG and narrow-band updates | High priority for build refactor [^1_1][^1_2] |
| **VTK Flying Edges** | Fast visualization surface extraction | Replace slow contouring if a surface is still required [^1_15] |
| **Open3D RaycastingScene** | Alternative batched distance/occupancy benchmark | Benchmark only; Warp already performs very well [^1_16] |
| **ParMmg** | Large-scale mesh adaptation | Low priority unless local adaptation becomes essential [^1_9] |
| **snappyHexMesh** | Parallel hex-dominant batch meshing | Not a drop-in TET10 route [^1_17] |

### Gmsh HXT

Gmsh supports OpenMP-based parallel meshing and explicit controls such as `General.NumThreads` and `Mesh.MaxNumThreads3D`. Its Delaunay and HXT algorithms support general size fields and embedded entities.[^1_11]

Test HXT using:

- A cleaned triangulated surface.
- The same target cell-size distribution.
- Physical groups applied before export.
- Binary MSH output or direct API array retrieval.
- One persistent C++ process.
- First-order tetrahedralization followed by TET10 upgrading.
- Optimization disabled initially and invoked only on failed quality gates.

Do not assume HXT will beat your 46-second CGAL result. It is a benchmark candidate, not a guaranteed replacement.

### fTetWild

fTetWild was designed to produce valid tetrahedral meshes from triangle soups while avoiding TetWild’s costly rational-number construction; its paper reports runtime comparable to less-robust Delaunay approaches, with the trade-off that preservation of every input triangle is not theoretically guaranteed. It is valuable for failed surfaces and self-intersection recovery, but CGAL’s direct-field route is preferable when your field is already valid and carries semantic labels.[^1_12]

### Faster contouring

If contouring cannot be deleted, first benchmark VTK’s `vtkFlyingEdges3D` or SurfaceNets before writing a custom Warp dual-contouring implementation. Kitware reports that these algorithms can be one to two orders of magnitude faster than basic marching cubes depending on the machine and threading backend.[^1_15]

A GPU marching-cubes path is easier than GPU dual contouring, but may lose sharp-feature behavior. GPU dual contouring is technically feasible and has published parallel formulations, although topology handling and watertight output remain the difficult parts. Treat it as a later optimization, not the first milestone.[^1_18]

## Sparse field generation

CUDA-accelerated narrow-band SDF generation has been demonstrated for closed triangulated surfaces containing tens of thousands to millions of features, explicitly targeting reduced preprocessing and mesh-generation time. A sparse narrow-band architecture is therefore better aligned with your local rib/pad edits than recomputing a full dense field.[^1_19]

A useful representation would store:

- Distance.
- Material or feature owner.
- Closest primitive ID.
- Active/inactive status.
- Optional local mesh size.
- Dirty-block flag.

Only blocks intersecting a modified feature’s expanded bounding box are recomputed. Neighboring unchanged blocks continue referencing the immutable base field.

## Eliminate meshing

Your Warp voxel and cut-cell experiments should not be abandoned, but they should be treated as a separate research track rather than mixed into the production tetrahedral route.

CutFEM uses unfitted meshes so boundaries and interfaces do not require a conforming mesh. GridapEmbedded provides level-set geometry, constructive solid geometry and embedded finite-element examples, including bimaterial linear elasticity. Fixed-grid shape-optimization studies specifically exploit design-independent meshes to avoid remeshing and mesh deformation between design updates.[^1_20][^1_21][^1_22]

For your application, the research tasks are:

- Better cut-cell integration.
- Nitsche or stabilized enforcement of bolt and clamped boundaries.
- Moment fitting or adaptive subcell quadrature.
- Conditioning and preconditioning of small-cut cells.
- Higher-order geometry reconstruction.
- GPU memory reduction.
- Validation of bearing tilt across the complete design envelope.

Because your current cut-cell result differs by about 6% and the voxel result by 14–17%, this is not yet the trustworthy production route. It may eventually become the fastest route because it removes surface and conforming-volume meshing entirely.

## Campaign scheduling

Do not launch four complete pipelines independently and let each compete for CPU, RAM and GPU. Use a bounded, staged pipeline:

```text
Generator/screen
      ↓
Persistent GPU build worker
      ↓
2–4 CPU mesh workers
      ↓
Label/assembly workers
      ↓
Persistent GPU solve worker
      ↓
Validation and compact storage
```

Dask supports abstract per-worker resource constraints for GPUs, memory and process-isolated work. Ray provides native CPU, GPU and memory resource scheduling. On an HPC system, Slurm job arrays are designed for large sets of independent parameterized jobs.[^1_23][^1_24][^1_25]

For a laptop prototype, a custom `multiprocessing` runner or Prefect is adequate. Prefect supports mapped concurrent tasks and explicit dependency control between stages.[^1_26][^1_27]

### Scheduling rules

- Use persistent processes so OCC, CGAL, Warp and cuDSS initialize once.
- Allocate exactly one GPU build/solve owner initially.
- Use bounded queues so meshes do not accumulate in RAM.
- Limit TBB/OpenMP threads inside each mesher.
- Avoid nested thread oversubscription.
- Group designs by family to maximize field and reference-mesh cache reuse.
- Process geometrically adjacent designs consecutively.
- Keep intermediate arrays in memory or memory-mapped binary storage.
- Write only final meshes, responses and diagnostics.
- Retry with a more robust route, not identical settings.
- Record the route and fallback reason for every design.

CUDA streams can overlap data movement with kernel execution when non-default streams and pinned host memory are used on capable devices. This can help overlap field transfer, assembly data transfer and solving, but it will not remove the GPU’s aggregate service-time limit.[^1_28]

## Expected scenarios

These are engineering targets, not measurements.


| Scenario | Build | Mesh | Other + solve | Full/design | 4,000 serial | Parallel requirement for 6 h |
| :-- | --: | --: | --: | --: | --: | --: |
| Current fast route | 79 s | 51 s | 20 s | 150 s | 167 h | 28 ideal workers |
| Remove contour + face operation | 35–45 s | 51 s | 20 s | 106–116 s | 118–129 h | 20–22 |
| Compiled CGAL oracle | 35–45 s | 5–15 s | 15–20 s | 55–80 s | 61–89 h | 11–15 |
| Cached SDF + compiled mesh | 8–20 s | 5–15 s | 15–20 s | 28–55 s | 31–61 h | 6–11 |
| Morphing fast path | 1–5 s | 1–5 s | 10–15 s | 12–25 s | 13–28 h | 3–5 |
| Two GPUs + 8 CPU workers | Pipeline-dependent | Pipeline-dependent | Pipeline-dependent | — | — | Plausible 4–8 h |

A mixed strategy is more realistic than forcing every design down one route. For example:

- 60–80% topology-stable designs: mesh morphing.
- 15–35% topology-changing designs: compiled CGAL.
- 1–5% difficult designs: fTetWild or cleaned-surface Gmsh.
- Failed or suspicious designs: quarantine for review.

The actual percentages must come from a representative 100-design benchmark.

## Avoid all 4,000 fidelities

If the purpose of 4,000 runs is surrogate training rather than mandatory exhaustive certification, do not automatically give all 4,000 designs the same fidelity.

Multi-fidelity active learning selects both the design point and the fidelity level using prediction uncertainty and benefit-to-cost considerations. Batch multi-fidelity acquisition methods additionally encourage diversity while respecting a simulation budget.[^1_29][^1_30]

A defensible campaign could use:

- 4,000 cheap geometric and low-fidelity evaluations.
- 800–1,500 medium-resolution conforming or cut-cell solves.
- 200–500 high-resolution TET10 solves.
- Adaptive enrichment where the surrogate has high uncertainty.
- A held-out stratified validation set.
- Additional high-fidelity samples near feasibility boundaries and response extrema.

This is frequently more useful than 4,000 uniformly meshed designs because it allocates expensive simulations where they add information.

## Validation gate

Only one design, \#7, currently supports the approximately 2% fast-route accuracy statement. Before scaling, test at least 30–50 stratified designs covering:

- Minimum and maximum rib count.
- Thin and thick ribs.
- Large face movement.
- Near-contacting features.
- All pattern families.
- CP-SAT-generated layouts outside the original families.
- Meshes near and above the cuDSS memory threshold.
- Designs with different support sensitivity.
- Known difficult contouring and hole configurations.

Record:

- Build, contour, mesh, TET10 conversion, labeling, assembly and solve times.
- Peak host and GPU memory.
- Number of field queries.
- Elements and unknowns.
- Minimum scaled Jacobian and dihedral angle.
- Sliver and inverted-element counts.
- Label completeness.
- Failure and fallback rates.
- Response error against the slow baseline.
- p50, p90 and p99—not only the fastest design.

Your reported 40% response change from bolt-support treatment is much larger than the approximately 2% meshing-route difference. Therefore, freeze and validate the bolt model before generating the final dataset; otherwise, faster meshing will create a large but internally inconsistent training set.

## Implementation priorities

### Week 1: establish truth

- Commit the bench scripts and measured results.
- Keep them under a feature flag rather than making them the product default.
- Add end-to-end stage tracing and synchronized GPU timings.
- Run a 20-design stratified benchmark.
- Confirm whether contouring is required by field meshing.
- Measure CGAL time with optimization disabled.
- Sweep mesher threads versus concurrent jobs.
- Freeze the support-condition specification.


### Weeks 2–3: remove overhead

- Add a `mesh_only` build mode.
- Cache split triangles, Warp BVHs and base fields.
- Keep the persistent GPU worker warm.
- Use Warp AOT compilation and disable gradients.
- Replace face movement with local analytic SDF operations.
- Move checks before or into field composition.
- Eliminate intermediate surface and mesh files.
- Implement the bounded staged runner.


### Weeks 3–5: compiled mesher

- Implement the CGAL field oracle in C++.
- Add zero-copy NumPy interfaces.
- Release the GIL during meshing.
- Enable and benchmark `Parallel_tag`.
- Add adaptive sizing and conditional optimization.
- Compare CGAL against Gmsh HXT and fTetWild on the same 50 designs.


### Weeks 5–7: reuse

- Cluster designs by topology.
- Build reference meshes for the largest families.
- Implement RBF/FFD morphing.
- Add Jacobian and boundary-projection checks.
- Route failed morphs to CGAL.
- Measure hit rate and throughput on 500 designs.


## Recommended decision

1. **Commit the fast-route scripts and results now.**
2. **Integrate Warp distance into the product behind a feature flag.**
3. **Do not spend the next sprint porting dual contouring to Warp.**
4. **First skip contouring, cache the base field/BVH, remove face movement and compile the CGAL field oracle.**
5. **Develop mesh morphing for topology-stable families in parallel.**
6. **Use CGAL as the main remesher, HXT as the first challenger and fTetWild as the robustness fallback.**
7. **Build a persistent staged job runner with explicit CPU, GPU and memory limits.**
8. **For a true four-to-six-hour end-to-end campaign, plan for at least two GPUs or reduce the number of high-fidelity solves through active learning.**

The most credible near-term target on the current laptop is approximately **20–40 seconds for build plus mesh**, followed by **8–12 hours for 4,000 builds/meshes with carefully controlled parallelism**. Reaching **four to six hours** requires a high mesh-morphing hit rate, additional worker capacity, or both; reaching that time for all 4,000 complete solves also requires addressing the single-GPU solve bottleneck.

<span style="display:none">[^1_100][^1_101][^1_102][^1_103][^1_104][^1_105][^1_106][^1_107][^1_108][^1_109][^1_110][^1_111][^1_112][^1_113][^1_114][^1_115][^1_116][^1_117][^1_118][^1_119][^1_120][^1_121][^1_122][^1_123][^1_124][^1_125][^1_126][^1_127][^1_128][^1_129][^1_130][^1_131][^1_132][^1_133][^1_134][^1_135][^1_136][^1_137][^1_138][^1_139][^1_140][^1_141][^1_142][^1_143][^1_144][^1_145][^1_146][^1_147][^1_148][^1_149][^1_150][^1_151][^1_152][^1_153][^1_154][^1_155][^1_156][^1_157][^1_158][^1_159][^1_160][^1_161][^1_162][^1_163][^1_164][^1_165][^1_166][^1_167][^1_168][^1_169][^1_170][^1_171][^1_172][^1_173][^1_174][^1_175][^1_176][^1_177][^1_178][^1_179][^1_180][^1_181][^1_182][^1_183][^1_184][^1_185][^1_186][^1_187][^1_188][^1_189][^1_190][^1_191][^1_192][^1_193][^1_194][^1_195][^1_196][^1_197][^1_198][^1_199][^1_200][^1_201][^1_202][^1_203][^1_204][^1_205][^1_206][^1_207][^1_208][^1_209][^1_210][^1_211][^1_212][^1_213][^1_214][^1_215][^1_216][^1_217][^1_218][^1_219][^1_220][^1_221][^1_222][^1_223][^1_224][^1_225][^1_226][^1_227][^1_228][^1_229][^1_230][^1_231][^1_232][^1_233][^1_234][^1_235][^1_236][^1_237][^1_238][^1_239][^1_240][^1_241][^1_242][^1_243][^1_244][^1_245][^1_246][^1_247][^1_248][^1_249][^1_250][^1_251][^1_252][^1_253][^1_254][^1_255][^1_256][^1_257][^1_258][^1_259][^1_260][^1_261][^1_262][^1_263][^1_264][^1_265][^1_266][^1_267][^1_268][^1_269][^1_270][^1_271][^1_272][^1_273][^1_274][^1_275][^1_276][^1_277][^1_278][^1_279][^1_280][^1_281][^1_282][^1_283][^1_284][^1_285][^1_286][^1_287][^1_288][^1_289][^1_290][^1_291][^1_292][^1_293][^1_294][^1_295][^1_296][^1_297][^1_298][^1_299][^1_300][^1_301][^1_302][^1_303][^1_304][^1_305][^1_306][^1_307][^1_308][^1_309][^1_31][^1_310][^1_311][^1_312][^1_313][^1_314][^1_315][^1_316][^1_317][^1_318][^1_319][^1_32][^1_320][^1_321][^1_322][^1_323][^1_324][^1_325][^1_326][^1_327][^1_328][^1_329][^1_33][^1_330][^1_331][^1_332][^1_333][^1_334][^1_335][^1_336][^1_337][^1_338][^1_339][^1_34][^1_340][^1_341][^1_342][^1_343][^1_344][^1_345][^1_346][^1_347][^1_348][^1_349][^1_35][^1_350][^1_351][^1_352][^1_353][^1_354][^1_355][^1_356][^1_357][^1_358][^1_359][^1_36][^1_360][^1_361][^1_362][^1_363][^1_364][^1_365][^1_366][^1_367][^1_368][^1_369][^1_37][^1_370][^1_371][^1_372][^1_373][^1_374][^1_375][^1_376][^1_377][^1_378][^1_379][^1_38][^1_380][^1_381][^1_382][^1_383][^1_384][^1_385][^1_386][^1_387][^1_388][^1_389][^1_39][^1_390][^1_391][^1_392][^1_393][^1_394][^1_395][^1_396][^1_397][^1_398][^1_399][^1_40][^1_400][^1_401][^1_402][^1_403][^1_404][^1_405][^1_406][^1_407][^1_408][^1_409][^1_41][^1_410][^1_411][^1_412][^1_413][^1_414][^1_415][^1_416][^1_417][^1_418][^1_419][^1_42][^1_420][^1_421][^1_422][^1_423][^1_424][^1_425][^1_426][^1_427][^1_428][^1_429][^1_43][^1_430][^1_431][^1_432][^1_433][^1_434][^1_435][^1_436][^1_437][^1_438][^1_439][^1_44][^1_440][^1_441][^1_442][^1_443][^1_444][^1_445][^1_446][^1_447][^1_448][^1_449][^1_45][^1_450][^1_451][^1_452][^1_453][^1_454][^1_455][^1_456][^1_457][^1_458][^1_459][^1_46][^1_460][^1_461][^1_462][^1_463][^1_464][^1_465][^1_466][^1_467][^1_468][^1_469][^1_47][^1_470][^1_471][^1_472][^1_473][^1_474][^1_475][^1_476][^1_477][^1_478][^1_479][^1_48][^1_480][^1_481][^1_482][^1_483][^1_484][^1_485][^1_486][^1_487][^1_488][^1_489][^1_49][^1_490][^1_491][^1_492][^1_493][^1_494][^1_495][^1_496][^1_497][^1_498][^1_499][^1_50][^1_500][^1_501][^1_502][^1_503][^1_504][^1_505][^1_506][^1_507][^1_508][^1_509][^1_51][^1_510][^1_511][^1_512][^1_513][^1_514][^1_515][^1_516][^1_517][^1_518][^1_519][^1_52][^1_520][^1_521][^1_522][^1_523][^1_524][^1_525][^1_526][^1_527][^1_528][^1_529][^1_53][^1_530][^1_531][^1_532][^1_533][^1_534][^1_535][^1_536][^1_537][^1_538][^1_539][^1_54][^1_540][^1_541][^1_542][^1_543][^1_544][^1_545][^1_546][^1_547][^1_548][^1_549][^1_55][^1_550][^1_551][^1_552][^1_553][^1_554][^1_555][^1_556][^1_557][^1_558][^1_559][^1_56][^1_560][^1_561][^1_562][^1_563][^1_564][^1_565][^1_566][^1_567][^1_568][^1_57][^1_58][^1_59][^1_60][^1_61][^1_62][^1_63][^1_64][^1_65][^1_66][^1_67][^1_68][^1_69][^1_70][^1_71][^1_72][^1_73][^1_74][^1_75][^1_76][^1_77][^1_78][^1_79][^1_80][^1_81][^1_82][^1_83][^1_84][^1_85][^1_86][^1_87][^1_88][^1_89][^1_90][^1_91][^1_92][^1_93][^1_94][^1_95][^1_96][^1_97][^1_98][^1_99]</span>

<div align="center">⁂</div>

[^1_1]: https://research.nvidia.com/labs/prl/publication/nanovdb/

[^1_2]: https://www.openvdb.org/documentation/doxygen/MeshToVolume_8h.html

[^1_3]: https://nvidia.github.io/warp/profiling.html

[^1_4]: https://github.com/tianyikillua/paraview-mapping

[^1_5]: https://github.com/nschloe/meshio/issues/715

[^1_6]: https://pybind11.readthedocs.io/en/stable/advanced/misc.html

[^1_7]: https://github.com/tianyikillua/pymapping

[^1_8]: https://arxiv.org/abs/2101.03781

[^1_9]: https://github.com/MmgTools/parmmg

[^1_10]: https://doc.cgal.org/latest/Tetrahedral_remeshing/index.html

[^1_11]: https://www.piwheels.org/project/medcoupling/

[^1_12]: https://vcpkg.roundtrip.dev/ports/salome-medcoupling

[^1_13]: https://replicability.graphics/papers/10.1145-3386569.3392385/index.html

[^1_14]: https://github.com/pyvista/pytetwild

[^1_15]: https://www.kitware.com/really-fast-isocontouring/

[^1_16]: https://www.open3d.org/docs/latest/python_api/open3d.t.geometry.RaycastingScene.html

[^1_17]: https://www.openfoam.com/documentation/guides/latest/doc/guide-meshing-snappyhexmesh.html

[^1_18]: https://onlinelibrary.wiley.com/doi/10.1111/j.1467-8659.2010.01825.x

[^1_19]: https://arxiv.org/abs/1903.00353

[^1_20]: https://github.com/topics/mesh-editing?o=desc\&s=updated

[^1_21]: https://people.cs.umu.se/martinb/downloads/Papers/BeWaBe19.pdf

[^1_22]: https://www.cambridge.org/core/journals/acta-numerica/article/cut-finite-element-methods/97D22C4D003C93666739D1BCF7AEBAF7

[^1_23]: https://github.com/nschloe/meshio

[^1_24]: https://docs.ray.io/en/latest/ray-core/scheduling/resources.html

[^1_25]: https://slurm.schedmd.com/job_array.html

[^1_26]: https://docs.prefect.io/v3/concepts/task-runners

[^1_27]: https://docs.prefect.io/v3/how-to-guides/workflows/run-work-concurrently

[^1_28]: https://developer.nvidia.com/blog/how-overlap-data-transfers-cuda-cc/

[^1_29]: https://arxiv.org/abs/2202.06902

[^1_30]: https://neurips.cc/virtual/2022/poster/53663

[^1_31]: https://nvidia.github.io/warp/api_reference/\_generated/warp.Mesh.html

[^1_32]: https://nvidia.github.io/warp/stable/api_reference/\_generated/warp.Mesh.html

[^1_33]: https://docs.nvidia.com/physicsnemo/26.08/physicsnemo/api/mesh/spatial.html

[^1_34]: https://docs.nvidia.com/physicsnemo/latest/physicsnemo/api/mesh/spatial.html

[^1_35]: https://nvidia.github.io/warp/v1.15/\_sources/language_reference/\_generated/warp.bvh_query_aabb.rst.txt

[^1_36]: https://nvidia.github.io/warp/v1.15/api_reference/\_generated/warp.Bvh.html

[^1_37]: https://www.openvdb.org/documentation/doxygen/namespaceopenvdb_1_1v13\_\_0_1_1tools.html

[^1_38]: https://nvidia.github.io/warp/v1.14/api_reference/\_generated/warp.Bvh.html

[^1_39]: https://artifacts.aswf.io/io/aswf/openvdb/openvdb_toolset_2013/1.0.0/openvdb_toolset_2013-1.0.0.pdf

[^1_40]: https://raw.githubusercontent.com/NVIDIA/warp/main/CHANGELOG.md

[^1_41]: https://www.openvdb.org/documentation/doxygen/LevelSetDilatedMesh_8h_source.html

[^1_42]: https://www.openvdb.org/documentation/doxygen/LevelSetRebuild_8h_source.html

[^1_43]: https://gist.github.com/cgmb/6e0aabf45584a74b56114cd7405932d1

[^1_44]: https://github.com/RenderKit/embree/blob/master/README.md

[^1_45]: https://github.com/lighttransport/embree-aarch64/blob/master/README.md

[^1_46]: https://doc.cgal.org/latest/Mesh_3/index.html

[^1_47]: https://doc.cgal.org/4.6/Mesh_3/index.html

[^1_48]: https://doc.cgal.org/4.8/Mesh_3/index.html

[^1_49]: https://doc.cgal.org/4.5.2/Mesh_3/index.html

[^1_50]: https://doc.cgal.org/5.5.1/Mesh_3/Mesh_3_2mesh_implicit_domains_8cpp-example.html

[^1_51]: https://doc.cgal.org/5.4.1/Mesh_3/Mesh_3_2mesh_implicit_domains_8cpp-example.html

[^1_52]: https://cgal.geometryfactory.com/CGAL/doc/master/Mesh_3/group\_\_PkgMesh3Ref.html

[^1_53]: https://doc.cgal.org/latest/Mesh_3/Mesh_3_2mesh_3D_weighted_image_with_detection_of_features_8cpp-example.html

[^1_54]: https://doc.cgal.org/latest/Periodic_3_mesh_3/index.html

[^1_55]: https://doc.cgal.org/latest/Mesh_3/Mesh_3_2mesh_optimization_example_8cpp-example.html

[^1_56]: https://doc.cgal.org/latest/Mesh_3/Mesh_3_2mesh_3D_image_with_custom_initialization_8cpp-example.html

[^1_57]: https://doc.cgal.org/latest/Mesh_3/structCGAL_1_1Mesh\_\_triangulation\_\_3.html

[^1_58]: https://doc.cgal.org/latest/Mesh_3/Mesh_3_2mesh_3D_image_8cpp-example.html

[^1_59]: https://www.cgal.org/2018/10/01/cgal413/

[^1_60]: https://github.com/CGAL/releases/blob/master/CHANGES.md

[^1_61]: https://sympa.inria.fr/sympa/arc/cgal-discuss/2017-08/msg00064.html

[^1_62]: https://github.com/CGAL/cgal/issues/6168

[^1_63]: https://www.cgal.org/2020/09/08/cgal51/

[^1_64]: https://fossies.org/linux/CGAL/CHANGES.md

[^1_65]: https://stackoverflow.com/questions/31854419/cgal-multi-thread

[^1_66]: https://www.cgal.org/2020/07/28/cgal51-beta2/

[^1_67]: https://github.com/wildmeshing/fTetWild

[^1_68]: https://cims.nyu.edu/gcl/papers/2020-fTetWild.pdf

[^1_69]: https://github.com/Yixin-Hu/TetWild

[^1_70]: https://cims.nyu.edu/gcl/papers/2018-TetWild.pdf

[^1_71]: https://github.com/wildmeshing/wildmeshing-python/blob/master/src/tetrahedralize.cpp

[^1_72]: https://github.com/wildmeshing

[^1_73]: https://cs.nyu.edu/media/publications/Thesis_NYU_Yixin_Hu-compressed.pdf

[^1_74]: https://arxiv.org/abs/1908.03581

[^1_75]: https://github.com/wildmeshing/fTetWild/tree/master

[^1_76]: https://cims.nyu.edu/gcl/papers/2022-WildMeshingToolkit.pdf

[^1_77]: https://haopan.github.io/papers/MeshRepair.pdf

[^1_78]: https://dl.acm.org/doi/10.1145/3386569.3392385

[^1_79]: https://github.com/Yixin-Hu/TetWild/blob/master/README.md

[^1_80]: https://cgg.mff.cuni.cz/gitlab/i3d/fTetWild/-/blame/c73554663709555ec4eec21817d33b65444fc50c/src/main.cpp

[^1_81]: https://repository.bilkent.edu.tr/server/api/core/bitstreams/adbbfb54-8c08-49a1-955c-bcea4bd2773c/content

[^1_82]: https://github.com/TetGen/TetGen

[^1_83]: https://juliageometry.github.io/TetGen.jl/v1.1/

[^1_84]: https://github.com/pyvista/tetgen

[^1_85]: https://github.com/Universite-Gustave-Eiffel/I-Simpa/blob/main/src/tetgen/tetgen.h

[^1_86]: https://wias-berlin.de/software/tetgen/files/tetgen-manual.pdf

[^1_87]: https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual.pdf

[^1_88]: https://github.com/ufz/tetgen

[^1_89]: https://manpages.ubuntu.com/manpages/focal/man1/tetgen.1.html

[^1_90]: https://juliageometry.github.io/TetGen.jl/dev/

[^1_91]: https://wias-berlin.de/software/tetgen/features.html

[^1_92]: https://github.com/alicevision/geogram/blob/master/src/lib/geogram/third_party/tetgen/tetgen.h

[^1_93]: https://github.com/inducer/meshpy/blob/main/src/cpp/tetgen.h

[^1_94]: https://www.scribd.com/document/622423840/Gmsh-Reference-Manual

[^1_95]: https://wias-berlin.de/software/tetgen/

[^1_96]: https://github.com/tataratat/tetgenpy

[^1_97]: http://gmsh.info/doc/texinfo/

[^1_98]: https://gmsh.info/dev/doc/texinfo/gmsh.pdf

[^1_99]: https://gmsh.info/doc/texinfo/gmsh.pdf

[^1_100]: https://arxiv.org/html/2008.08508v1

[^1_101]: https://www.ring-team.org/research-publications/ring-meeting-papers?view=pub\&id=4849

[^1_102]: https://www.semanticscholar.org/paper/Quality-tetrahedral-mesh-generation-with-HXT-Marot-Remacle/e927bb011ebfd885f70da3fc9b69ad107ecfb707

[^1_103]: http://gmsh.info/doc/gmsh.pdf

[^1_104]: https://gmsh.info/doc/course/general_overview.pdf

[^1_105]: https://cs.nyu.edu/media/publications/Zhongshi_Jiang-compressed.pdf

[^1_106]: https://hal.univ-lorraine.fr/tel-03249549v1/file/main.pdf

[^1_107]: https://www.semanticscholar.org/paper/Tetrahedral-Mesh-Improvement-Using-Multi-face-Misztal-Bærentzen/51735b5505f72f89151cef9fa0eeef7e377d2a5a

[^1_108]: https://www.sciencedirect.com/science/article/pii/S2215016120302818

[^1_109]: https://chemphys.edu.ru/media/published/Kryuchkova_Ermakov_Vol_21_No_2.pdf

[^1_110]: https://deepwiki.com/live-clones/gmsh/5.2-mesh-generation

[^1_111]: https://link.springer.com/article/10.1007/s00366-013-0330-1

[^1_112]: https://iris.unica.it/retrieve/e2f56eda-afa8-3eaf-e053-3a05fe0a5d97/A MeshMorphing Computational Meth.pdf

[^1_113]: https://pmc.ncbi.nlm.nih.gov/articles/PMC7304786/

[^1_114]: https://github.com/mathLab/PyGeM

[^1_115]: https://github.com/mathLab/PyGeM/blob/master/README.md

[^1_116]: https://www.academia.edu/110474303/Automatic_shape_optimisation_of_structural_parts_driven_by_BGM_and_RBF_mesh_morphing

[^1_117]: https://www.academia.edu/143171306/A_Comparison_of_Mesh_Morphing_Methods_for_3D_Shape_Optimization

[^1_118]: https://mathlab.github.io/PyGeM/tutorials.html

[^1_119]: https://mathlab.github.io/PyGeM/ffd.html

[^1_120]: https://mathlab.sissa.it/pygem

[^1_121]: https://www.sciencedirect.com/science/article/abs/pii/S0965997818313115

[^1_122]: https://proceedings.neurips.cc/paper_files/paper/2023/file/89379d5fc6eb34ff98488202fb52b9d0-Paper-Conference.pdf

[^1_123]: https://fsalmoir.github.io/

[^1_124]: https://www.sandia.gov/imr/2015 IMR Papers/11.pdf

[^1_125]: https://arxiv.org/html/2003.13751v1

[^1_126]: https://fenicsproject.discourse.group/t/mesh-moving-ale-in-dolfinx-example-or-official-api/18323

[^1_127]: https://github.com/sandialabs/omega_h

[^1_128]: https://docs.mfem.org/html/pmesh-optimizer_8cpp_source.html

[^1_129]: https://www.osti.gov/servlets/purl/1458399

[^1_130]: https://docs.mfem.org/4.8/mesh-optimizer_8cpp_source.html

[^1_131]: https://sci-hub.se/downloads/2020-10-26/09/anderson2020.pdf

[^1_132]: https://github.com/sandialabs/omega_h/blob/main/example/fenics/python/poisson_adaptive.py

[^1_133]: https://github.com/mfem/mfem/blob/v3.3.2/CHANGELOG

[^1_134]: https://fenics.readthedocs.io/projects/dolfin/en/2017.2.0/apis/api_ale.html

[^1_135]: https://arxiv.org/pdf/2205.12721v2.pdf

[^1_136]: https://raw.githubusercontent.com/mfem/mfem/master/CHANGELOG

[^1_137]: https://github.com/SCOREC

[^1_138]: https://arxiv.org/html/2001.11536v1

[^1_139]: https://ar5iv.labs.arxiv.org/html/2402.15940

[^1_140]: https://kennyweiss.com/papers/Vargas21.arxiv.pdf

[^1_141]: https://libigl.github.io/tutorial/

[^1_142]: https://github.com/libigl/libigl/blob/main/include/igl/signed_distance.h

[^1_143]: https://github.com/libigl/libigl/releases

[^1_144]: https://libigl.github.io/dox/signed\_\_distance_8h.html

[^1_145]: https://github.com/libigl/libigl/blob/main/include/igl/signed_distance.cpp

[^1_146]: https://github.com/libigl/libigl/blob/main/tutorial/705_MarchingCubes/main.cpp

[^1_147]: https://libigl.github.io/dox/files.html

[^1_148]: https://github.com/libigl/libigl-python-bindings/pull/237

[^1_149]: https://github.com/libigl/libigl/blob/main/include/igl/copyleft/marching_cubes.h

[^1_150]: https://github.com/libigl/libigl/discussions/2103

[^1_151]: https://github.com/hjwdzh/ManifoldPlus

[^1_152]: https://github.com/Borges3D

[^1_153]: https://libigl.github.io/libigl-python-bindings/api/igl_copyleft/

[^1_154]: https://jkavalik.github.io/meshseal/

[^1_155]: https://libigl.github.io/dox/winding\_\_number_8h.html

[^1_156]: https://www.openvdb.org/documentation/doxygen/NanoVDB_HelloWorld.html

[^1_157]: https://developer.nvidia.com/blog/accelerating-openvdb-on-gpus-with-nanovdb/

[^1_158]: https://www.openvdb.org/documentation/

[^1_159]: https://www.openvdb.org/documentation/doxygen/NanoVDB_8h.html

[^1_160]: https://kaolin.readthedocs.io/en/latest/notes/volumetric_meshes.html

[^1_161]: https://www.openvdb.org/documentation/doxygen/files.html

[^1_162]: https://developer.nvidia.com/kaolin

[^1_163]: https://github.com/krrish94/kaolin-bleed/blob/master/kaolin/non_commercial/flexicubes/flexicubes.py

[^1_164]: https://www.aswf.io/news/nanovdb/

[^1_165]: https://github.com/AcademySoftwareFoundation/openvdb/blob/master/doc/CMakeLists.txt

[^1_166]: https://github.com/nv-tlabs/FlexiCubes/blob/main/README.md

[^1_167]: https://github.com/nv-tlabs/FlexiCubes

[^1_168]: https://idclip.github.io/openvdb-website/

[^1_169]: https://arxiv.org/html/2504.04564v1

[^1_170]: https://github.com/Juanxpeke/Marching-Cubes-CUDA

[^1_171]: https://github.com/tpn/cuda-samples/blob/master/v8.0/2_Graphics/marchingCubes/marchingCubes_kernel.cu

[^1_172]: https://docs.nvidia.com/cuda/archive/11.5.2/pdf/CUDA_Samples.pdf

[^1_173]: https://github.com/BenoitMorel/marching-cubes

[^1_174]: https://github.com/NVlabs/instant-ngp/blob/master/src/marching_cubes.cu

[^1_175]: https://github.com/NVIDIA/cuda-samples/blob/master/Samples/5_Domain_Specific/README.md

[^1_176]: https://github.com/tpn/cuda-samples/blob/master/v8.0/2_Graphics/marchingCubes/marchingCubes.cpp

[^1_177]: https://github.com/lzhnb/CuMCubes

[^1_178]: https://nvidia.github.io/warp/

[^1_179]: https://developer.download.nvidia.com/compute/DevZone/C/html_x64/Physically-Based_Simulation.html

[^1_180]: https://mewangcl.github.io/pubs/CADGPUModeler.pdf

[^1_181]: https://arxiv.org/html/2510.02894v1

[^1_182]: https://github.com/Tsarpf/procgen

[^1_183]: https://nvidia.github.io/warp/v1.14/index.html

[^1_184]: https://app.daily.dev/posts/release-v1-9-0-nvidia-warp-qjbny2qdz

[^1_185]: https://www.openvdb.org/documentation/doxygen/codeExamples.html

[^1_186]: https://deepwiki.com/AcademySoftwareFoundation/openvdb/5.2-csg-and-merge-operations

[^1_187]: https://www.openvdb.org/documentation/doxygen/Composite_8h_source.html

[^1_188]: https://perso.liris.cnrs.fr/eric.galin/Articles/2025-lod.pdf

[^1_189]: https://www.sidefx.com/docs/hdk/\_particles_to_level_set_8h_source.html

[^1_190]: https://github.com/libfive/libfive

[^1_191]: https://github.com/libfive

[^1_192]: https://gist.github.com/cgmb/56e53fd9fd0e745247b4af86aa67bd02

[^1_193]: https://www.openvdb.org/documentation/doxygen/Composite_8h.html

[^1_194]: https://github.com/mkeeter/fidget

[^1_195]: http://github.com/mkeeter

[^1_196]: https://docs.omniverse.nvidia.com/kit/docs/omni.vdb/latest/source/extensions/omni.vdb.tool/docs/ogn/nodes/vdblevelsetcsg.html

[^1_197]: https://www.openvdb.org/documentation/doxygen/LevelSetUtil_8h.html

[^1_198]: https://www.tandfonline.com/doi/full/10.1080/19942060.2016.1174888

[^1_199]: https://uwe-repository.worktribe.com/file/907749/1/An improved local remeshing algorithm for moving boundary problems.pdf

[^1_200]: https://arxiv.org/html/1703.07007v2

[^1_201]: https://msia.centre-mersenne.org/articles/10.5802/msia.22/

[^1_202]: https://www.mmgtools.org/mmg-remesher-publications

[^1_203]: https://people.eecs.berkeley.edu/~jrs/papers/elasto.pdf

[^1_204]: https://onlinelibrary.wiley.com/doi/abs/10.1002/nme.1643

[^1_205]: https://www.sciencedirect.com/science/article/abs/pii/S004578250900334X

[^1_206]: https://minesparis-psl.hal.science/hal-00655134v1/document

[^1_207]: https://perso.telecom-paristech.fr/boubek/papers/MADVolumeRemesher/MADVolumeRemesher.pdf

[^1_208]: http://in4.iue.tuwien.ac.at/pdfs/sisdep1995/pdfs/BozekS-107.pdf

[^1_209]: https://www.sciencedirect.com/science/article/abs/pii/S0021999107005037

[^1_210]: https://eprints.whiterose.ac.uk/id/eprint/1758/1/jimackp32_MJ03.pdf

[^1_211]: https://www.ljll.fr/~frey/papers/meshing/Bousetta R., Adaptive remshing based on a posteriori error estimation for forging simulation.pdf

[^1_212]: https://www.sciencedirect.com/science/article/abs/pii/S1524070312000124

[^1_213]: https://arxiv.org/html/1807.01285v1

[^1_214]: https://assets.cambridge.org/97810097/08043/excerpt/9781009708043_excerpt.pdf

[^1_215]: https://link.springer.com/article/10.1007/s11831-014-9115-y

[^1_216]: https://research.chalmers.se/publication/524200/file/524200_Fulltext.pdf

[^1_217]: https://opendata.uni-halle.de/bitstream/1981185920/41967/1/von Wahl_Henry_Dissertation_2021.pdf

[^1_218]: https://www.igpm.rwth-aachen.de/Download/reports/pdf/IGPM519.pdf

[^1_219]: https://kth.diva-portal.org/smash/get/diva2:1903618/FULLTEXT02.pdf

[^1_220]: https://mediatum.ub.tum.de/doc/1093297/document.pdf

[^1_221]: https://iris.sissa.it/retrieve/68a91d2b-2767-420e-9d3a-dfbfe6af5750/2010.04953v2.pdf

[^1_222]: https://ar5iv.labs.arxiv.org/html/2003.00352

[^1_223]: https://arxiv.org/pdf/2607.02334v1.pdf

[^1_224]: https://arxiv.org/pdf/2412.17657.pdf

[^1_225]: https://mediatum.ub.tum.de/doc/1722474/1722474.pdf

[^1_226]: https://www.diva-portal.org/smash/get/diva2:1553828/FULLTEXT01.pdf

[^1_227]: https://imag.umontpellier.fr/~di-pietro/poems2019/erik_burman.pdf

[^1_228]: https://github.com/gridap/GridapEmbedded.jl

[^1_229]: https://amartinhuertas.github.io/menu2/

[^1_230]: https://arxiv.org/html/1902.01168v2

[^1_231]: https://github.com/ngsxfem/ngsxfem

[^1_232]: https://github.com/gridap

[^1_233]: https://github.com/gridap/GridapEmbedded.jl/blob/master/NEWS.md

[^1_234]: https://github.com/gridap/GridapEmbedded.jl/blob/master/test/GridapEmbeddedTests/BimaterialPoissonCutFEMTests.jl

[^1_235]: https://ar5iv.labs.arxiv.org/html/2106.13728

[^1_236]: https://github.com/sclaus2/CutFEMx

[^1_237]: https://researchportalplus.anu.edu.au/en/publications/distributed-memory-parallelization-of-the-aggregated-unfitted-fin/

[^1_238]: https://ar5iv.labs.arxiv.org/html/2201.06632

[^1_239]: https://gridap.github.io/GridapEmbedded.jl/

[^1_240]: https://amses-journal.springeropen.com/articles/10.1186/s40323-020-00154-5

[^1_241]: https://upcommons.upc.edu/bitstream/handle/2117/406723/TPAMP1de1.pdf;jsessionid=E0742F1CA0509E5B91DE9EAC4F052080?sequence=1

[^1_242]: https://ar5iv.labs.arxiv.org/html/2009.01596

[^1_243]: https://docs.dask.org/en/stable/gpu.html

[^1_244]: https://distributed.dask.org/en/latest/resources.html?highlight=resources

[^1_245]: https://distributed.dask.org/en/stable/scheduling-state.html

[^1_246]: http://distributed.dask.org/en/stable/resources.html

[^1_247]: https://distributed.dask.org/en/latest/resources.html?highlight=GPU

[^1_248]: https://distributed.dask.org/en/stable/scheduling-policies.html

[^1_249]: https://distributed.dask.org/en/latest/locality.html

[^1_250]: https://docs.rapids.ai/api/dask-cuda/nightly/api/

[^1_251]: https://docs.nvidia.com/datascience/deployment/stable/tools/dask-cuda/

[^1_252]: https://docs.nvidia.com/deploy/mps/latest/index.html

[^1_253]: https://docs.dask.org/en/latest/configuration.html

[^1_254]: https://cloudprovider.dask.org/\_/downloads/en/latest/pdf/

[^1_255]: https://docs.nvidia.com/deploy/mps/architecture.html

[^1_256]: https://docs.ray.io/en/latest/ray-core/examples/batch_prediction.html

[^1_257]: https://docs.rapids.ai/deployment/stable/guides/scheduler-gpu-requirements/

[^1_258]: https://nanobind.readthedocs.io/\_/downloads/en/latest/pdf/

[^1_259]: https://www.matecdev.com/posts/nanobind-vs-pybind11-cpp-python.html

[^1_260]: https://pybind11.readthedocs.io/en/stable/advanced/cast/functional.html

[^1_261]: https://cython.readthedocs.io/en/latest/src/userguide/memoryviews.html

[^1_262]: https://www.ion.org/publications/abstract.cfm?articleID=20040

[^1_263]: https://pybind11.readthedocs.io/\_/downloads/en/latest/pdf/

[^1_264]: https://www.ion.org/plans/abstracts.cfm?paperID=15353

[^1_265]: https://arxiv.org/html/2202.13889v2

[^1_266]: https://nanobind.readthedocs.io/en/latest/benchmark.html

[^1_267]: https://cython.readthedocs.io/en/3.1.x/src/userguide/memoryviews.html

[^1_268]: https://yanto.fi/2022/09/benchmark-of-python-c-bindings/

[^1_269]: https://api.pageplace.de/preview/DT0400.9781491901762_A24112871/preview-9781491901762_A24112871.pdf

[^1_270]: https://nanobind.readthedocs.io/en/latest/changelog.html

[^1_271]: https://github.com/wjakob/nanobind

[^1_272]: https://arxiv.org/html/2603.04668v1

[^1_273]: https://publications.ibpsa.org/proceedings/bs/2019/papers/BS2019_211232.pdf

[^1_274]: https://pubs.acs.org/doi/10.1021/acs.iecr.4c03303

[^1_275]: https://icas.org/icas_archive/ICAS2012/PAPERS/104.PDF

[^1_276]: https://repository.essex.ac.uk/15604/

[^1_277]: https://discovery.ucl.ac.uk/id/eprint/10134527/8/Diaz De La O_1-s2.0-S0307904X21003449-main.pdf

[^1_278]: https://hal.science/hal-04458288/document

[^1_279]: https://repository.essex.ac.uk/15604/1/1-s2.0-S1877750315300387-main.pdf

[^1_280]: https://www.cambridge.org/core/services/aop-cambridge-core/content/view/EDE3801EB370807254D5DD7F1B73EF37/S2632673625100361a.pdf/a-novel-adaptive-sampling-approach-with-batch-selection-for-the-automatic-generation-of-surrogate-models-in-geotechnical-engineering.pdf

[^1_281]: https://eprints.soton.ac.uk/373482/

[^1_282]: https://rpsonline.com.sg/proceedings/isrerm2022/pdf/MS-12-185.pdf

[^1_283]: https://link.springer.com/article/10.1007/s00158-020-02575-7

[^1_284]: https://personal.utdallas.edu/~jiezhang/Journals/Zhang_2019_SMO_Surrogate.pdf

[^1_285]: https://www.tandfonline.com/doi/full/10.1080/23789689.2026.2676339

[^1_286]: https://link.springer.com/content/pdf/10.1007/s00158-020-02575-7.pdf?error=cookies_not_supported\&code=dafb2203-153c-4294-b8bd-9a5726cbe783

[^1_287]: https://arxiv.org/html/2404.11965v1

[^1_288]: https://dev.opencascade.org/doc/occt-6.9.0/refman/html/class_b_rep_mesh\_\_\_incremental_mesh.html

[^1_289]: https://dev.opencascade.org/doc/refman/html/class_b_rep_mesh\_\_\_incremental_mesh.html

[^1_290]: https://dev.opencascade.org/doc/occt-7.8.0/refman/html/classBRepMesh\_\_IncrementalMesh.html

[^1_291]: https://github.com/xBimTeam/XbimGeometry/blob/master/Xbim.Geometry.Engine/OCC/src/BRepMesh/BRepMesh_IncrementalMesh.cxx

[^1_292]: https://github.com/Open-Cascade-SAS/OCCT/wiki/upgrade

[^1_293]: https://ocjs.org/reference-docs/classes/BRepMesh_IncrementalMesh

[^1_294]: https://git.rbts.co/OpenCascade/occt/src/commit/21095f2dc26b1c686254c2923bc03876de6bbb91/src/BRepMesh/BRepMesh_IncrementalMesh.hxx

[^1_295]: https://github.com/Open-Cascade-SAS/OCCT/releases

[^1_296]: https://occt3d.com/dev/doc/overview/html/occt_user_guides\_\_mesh.html

[^1_297]: https://occt3d.com/dev/doc/refman/html/package_brepmesh.html

[^1_298]: https://dev.opencascade.org/doc/occt-6.9.1/refman/html/class_b_rep_mesh\_\_\_incremental_mesh.html

[^1_299]: https://optics.engineering/manual/cad_step_responsiveness.html

[^1_300]: https://github.com/Open-Cascade-SAS/OCCT/discussions/1433

[^1_301]: https://occt3d.com/dev/content/brepmeshincremental-mesh-algorithm/

[^1_302]: https://old.opencascade.com/doc/occt-7.0.0/refman/html/\_b_rep_mesh\_\_\_incremental_mesh_8hxx.html

[^1_303]: https://deepwiki.com/NVIDIA/warp/8.1-cuda-graphs-and-async-operations

[^1_304]: https://sourceforge.net/projects/nvidia-warp.mirror/files/v1.16.0/

[^1_305]: https://warp.readthedocs.io/en/latest/

[^1_306]: https://nvidia.github.io/warp/deep_dive/codegen.html

[^1_307]: https://nvidia.github.io/warp/modules/allocators.html

[^1_308]: https://nvidia.github.io/warp/codegen.html

[^1_309]: https://sourceforge.net/projects/nvidia-warp.mirror/files/v1.14.0/

[^1_310]: https://nvidia.github.io/warp/modules/concurrency.html

[^1_311]: https://nvidia.github.io/warp/stable/user_guide/execution_and_performance/reducing_compilation_and_startup_time.html

[^1_312]: https://deepwiki.com/NVIDIA/warp/8.5-execution-performance-and-debugging

[^1_313]: https://deepwiki.com/NVIDIA/warp/2.6-jit-compilation-system

[^1_314]: https://github.com/erwincoumans/warp_cpp

[^1_315]: https://developer.nvidia.com/warp-python

[^1_316]: https://deepwiki.com/NVIDIA/warp/5.1-jax-integration

[^1_317]: https://github.com/yumka/Cleaver2

[^1_318]: https://github.com/SCIInstitute/Cleaver

[^1_319]: https://github.com/ahmadki/quartet

[^1_320]: http://github.com/crawforddoran/quartet/blob/master/README

[^1_321]: https://github.com/crawforddoran/quartet

[^1_322]: http://github.com/PyMesh/quartet

[^1_323]: https://pypi.org/project/itk-cleaver/

[^1_324]: http://github.com/crawforddoran

[^1_325]: https://repositum.tuwien.at/bitstream/20.500.12708/188054/1/Balla Cedrik - 2023 - Tetrahedral Mesh Cleaving of Level Set Surfaces.pdf

[^1_326]: https://github.com/lassoan/SlicerSegmentMesher/blob/master/SegmentMesher/SegmentMesher.py

[^1_327]: https://github.com/PyMesh

[^1_328]: https://www.slicer.org/wiki/Documentation/Nightly/Extensions/CleaverExtension

[^1_329]: https://core.ac.uk/download/pdf/276267101.pdf

[^1_330]: https://www.biorxiv.org/content/10.1101/2023.02.24.528183v1.full.pdf

[^1_331]: https://sofa-framework.github.io/doc/components/engine/generate/meshtetrastuffing/

[^1_332]: https://github.com/geolehmann/tetra_mesh

[^1_333]: https://github.com/fangq/mmc

[^1_334]: https://www.comp.nus.edu.sg/~tants/gdel3d_files/gDel3D.pdf

[^1_335]: https://www.comp.nus.edu.sg/~tants/gdel3d_files/AshwinNanjappaThesis.pdf

[^1_336]: https://gist.github.com/silky/86863795c83e63e56244

[^1_337]: https://research.chalmers.se/publication/553368/file/553368_Fulltext.pdf

[^1_338]: https://xianweiz.github.io/doc/papers/cfd_fgcs23.pdf

[^1_339]: https://gredos.usal.es/bitstream/handle/10366/139722/DICT_OrtegaTerolD_2.pdf?sequence=5\&isAllowed=y

[^1_340]: https://www.comp.nus.edu.sg/~tants/gdel3d.html

[^1_341]: https://scicomp.stackexchange.com/questions/2026/fastest-delaunay-triangulation-libraries-for-sets-of-3d-points

[^1_342]: https://github.com/imanf94/gDel3D

[^1_343]: https://dl.acm.org/doi/10.1007/s11227-013-1004-x

[^1_344]: https://arxiv.org/html/2406.01579

[^1_345]: https://github.com/ingowald/cudaAmrIsoSurfaceExtraction

[^1_346]: https://www.degruyter.com/document/doi/10.1515/rnam-2018-0026/html?lang=de

[^1_347]: https://github.com/NVIDIA/warp/issues/1816/linked_closing_reference

[^1_348]: https://github.com/NVIDIA/warp/issues/813

[^1_349]: https://github.com/NVIDIA/warp

[^1_350]: https://github.com/NVIDIA/warp/issues/1151

[^1_351]: https://deepwiki.com/NVIDIA/warp/4-rendering

[^1_352]: https://github.com/NVIDIA/warp/issues/324

[^1_353]: https://nvidia.github.io/warp/v1.1/index.html

[^1_354]: https://github.com/nvidia/warp

[^1_355]: https://sourceforge.net/projects/nvidia-warp.mirror/files/v1.12.0/

[^1_356]: https://github.com/NVIDIA/warp/issues/1594

[^1_357]: https://github.com/xylar/moab/blob/master/README.md

[^1_358]: https://pypi.org/project/medcoupling/

[^1_359]: https://github.com/ndjinga/SOLVERLAB

[^1_360]: https://github.com/obmun/moab

[^1_361]: https://github.com/xylar/moab

[^1_362]: https://github.com/vijaysm/MOAB2

[^1_363]: https://github.com/SalomePlatform/med

[^1_364]: https://github.com/SalomePlatform

[^1_365]: https://github.com/pyvista/pytetwild/blob/main/README.rst

[^1_366]: https://oomph-lib.github.io/oomph-lib/doc/meshes/mesh_from_tetgen/latex/refman.pdf

[^1_367]: https://github.com/JuliaGeometry/TetGen.jl

[^1_368]: https://simvascular.github.io/documentation/python_interface/modules/docs/meshing_TetGen.html

[^1_369]: https://ports.macports.org/port/tetgen/builds/

[^1_370]: https://github.com/NVIDIA/warp/blob/main/CHANGELOG.md

[^1_371]: https://research.nvidia.com/labs/prl/tag/sparse-volumes/

[^1_372]: https://research.nvidia.com/labs/prl/neuralvdb/neuralvdb2024.pdf

[^1_373]: https://github.com/NVIDIA/warp/blob/main/warp/examples/core/example_mesh.py

[^1_374]: https://research.nvidia.com/labs/prl/nanovdb/nanovdb2021.pdf

[^1_375]: https://github.com/NVlabs/nvdiffrec

[^1_376]: https://book.vtk.org/en/latest/VTKBook/12Chapter12.html

[^1_377]: https://github.com/ForeverDavid/marching-cubes-cuda

[^1_378]: https://www.kitware.com/ongoing-vtk-paraview-performance-improvements/

[^1_379]: https://discourse.vtk.org/t/it-takes-long-time-for-the-iso-surface-extraction-at-first-step/5456/4

[^1_380]: https://www.kennethmoreland.com/documents/miniIsosurface.pdf

[^1_381]: https://github.com/topics/dual-contouring?o=asc\&s=updated

[^1_382]: https://cad-journal.net/files/vol_19/CAD_19(5)\_2022_1000-1014.pdf

[^1_383]: https://www.sciencedirect.com/science/article/pii/S2452321617305310/pdf?md5=0ec66980862c84f467f9e59784ea5ebc\&pid=1-s2.0-S2452321617305310-main.pdf

[^1_384]: https://surface.syr.edu/cgi/viewcontent.cgi?article=2174\&context=etd

[^1_385]: https://publications.rwth-aachen.de/record/726057/files/726057.pdf

[^1_386]: https://www.honda-ri.de/pubs/pdf/2999.pdf

[^1_387]: https://cg.cs.tsinghua.edu.cn/papers/CAD_2010_quad.pdf

[^1_388]: https://cg.cs.tsinghua.edu.cn/people/~laiyk/papers/remesh_cad.pdf

[^1_389]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4614200

[^1_390]: https://www.academia.edu/74128253/Geometry_Parameterization_and_Computational_Mesh_Deformation_by_Physics_Based_Direct_Manipulation_Approaches

[^1_391]: https://www.foi.se/rest-api/report/FOI-R--1784--SE

[^1_392]: https://repository.tudelft.nl/record/uuid:cfc2f6aa-5bc8-40b0-b581-2f005239ed0f

[^1_393]: https://dev.opencascade.org/sites/default/files/pdf/release_notes_7.3.0.pdf

[^1_394]: https://dev.opencascade.org/doc/overview/html/specification\_\_boolean_operations.html

[^1_395]: https://dev.opencascade.org/sites/default/files/pdf/Release_Notes_6.7.1.pdf

[^1_396]: https://occt3d.com/dev/content/speed-boolean-operator-many-simple-shapes/index.html

[^1_397]: https://dev.opencascade.org/sites/default/files/pdf/OCCT_release_notes_6.9.0.pdf

[^1_398]: https://dev.opencascade.org/doc/occt-7.7.0/refman/html/class_b_rep_algo_a_p_i\_\_\_boolean_operation.html

[^1_399]: https://dev.opencascade.org/doc/refman/html/class_b_rep_algo_a_p_i\_\_\_boolean_operation.html

[^1_400]: https://dev.opencascade.org/doc/dev/refman/html/class_b_rep_algo_a_p_i\_\_\_boolean_operation.html

[^1_401]: https://occt3d.com/dev/doc/overview/html/occt_user_guides\_\_modeling_algos.html

[^1_402]: https://deepwiki.com/joe-warren/opencascade-hs/4.4-boolean-operation-bindings

[^1_403]: https://opencascade.blogspot.com/2008/12/why-boolean-operations-are-so-sloooooow.html

[^1_404]: https://github.com/NVIDIA/warp/issues/855

[^1_405]: https://github.com/NVIDIA/warp/releases

[^1_406]: https://github.com/keijiro/ComputeMarchingCubes

[^1_407]: https://github.com/topics/marching-cubes

[^1_408]: https://github.com/shermanlo77/marchingcubes

[^1_409]: https://olimot.github.io/marching-cubes/

[^1_410]: https://leofang.github.io/assets/cupy.pdf

[^1_411]: https://deepwiki.com/isl-org/Open3D/4.4-raycasting-and-distance-queries

[^1_412]: https://github.com/mikedh/trimesh/issues/155

[^1_413]: https://www.open3d.org/html/cpp_api/classopen3d_1_1t_1_1geometry_1_1_raycasting_scene.html

[^1_414]: https://www.open3d.org/docs/latest/cpp_api/classopen3d_1_1t_1_1geometry_1_1_raycasting_scene.html

[^1_415]: https://www.open3d.org/docs/0.14.1/cpp_api/classopen3d_1_1t_1_1geometry_1_1_raycasting_scene.html

[^1_416]: https://www.open3d.org/docs/0.17.0/python_api/open3d.t.geometry.RaycastingScene.html

[^1_417]: https://www.open3d.org/docs/0.19.0/python_api/open3d.t.geometry.RaycastingScene.html

[^1_418]: https://www.open3d.org/docs/0.17.0/tutorial/geometry/distance_queries.html

[^1_419]: https://www.open3d.org/docs/latest/tutorial/geometry/distance_queries.html

[^1_420]: https://github.com/mfem/mfem/blob/master/miniapps/meshing/mesh-optimizer.cpp

[^1_421]: http://github.com/MmgTools/ParMmg

[^1_422]: https://github.com/mfem/mfem/blob/master/miniapps/meshing/pmesh-fitting.cpp

[^1_423]: https://github.com/MmgTools/ParMmg/releases

[^1_424]: https://github.com/mfem/mfem

[^1_425]: http://github.com/MmgTools/ParMmg/wiki/Documentation

[^1_426]: https://arxiv.org/html/1911.09220v2

[^1_427]: http://github.com/MmgTools

[^1_428]: https://lcirrottola.github.io/activities/

[^1_429]: https://arxiv.org/html/2205.12721v2

[^1_430]: https://www.osti.gov/servlets/purl/1782786

[^1_431]: https://mfem.org/pdf/workshop21/14_VladimirTomov_Mesh_Optimization.pdf

[^1_432]: https://www.openfoam.com/documentation/user-guide/4-mesh-generation-and-conversion/4.4-mesh-generation-with-the-snappyhexmesh-utility

[^1_433]: https://enccs.github.io/openfoam/mesh/

[^1_434]: https://openfoam.org/release/2-3-0/snappyhexmesh/

[^1_435]: https://www.openfoam.com/documentation/guides/latest/api/snappyHexMesh_8C_source.html

[^1_436]: http://github.com/SCOREC/core/wiki

[^1_437]: https://www.openfoam.com/documentation/user-guide/4-mesh-generation-and-conversion

[^1_438]: https://openfoamwiki.net/images/b/b2/OFW11-Jackson-advSHM-FINAL.pdf

[^1_439]: https://www.cfd-online.com/Forums/openfoam-meshing/102126-snappyhexmesh-parallel.html

[^1_440]: https://www.openfoam.com/documentation/guides/latest/doc/guide-meshing-snappyhexmesh-castellation.html

[^1_441]: https://github.com/CEED/PUMI

[^1_442]: https://www.scorec.rpi.edu/REPORTS/2015-4.pdf

[^1_443]: https://extremecomputingtraining.anl.gov/wp-content/uploads/sites/96/2022/11/ATPESC-2022-Track-5-Talk-1-Yang-IntroToNumericalSoftware.pdf

[^1_444]: https://github.com/SCOREC/core/issues/245

[^1_445]: https://www.sciencedirect.com/science/article/pii/S2590123024007382

[^1_446]: https://arxiv.org/html/2601.21832v1

[^1_447]: https://www.scipedia.com/wd/images/b/b6/Draft_Sanchez_Pinedo_853948896762_paper.pdf

[^1_448]: https://www.academia.edu/7356912/A_Surrogate_Modeling_and_Adaptive_Sampling_Toolbox_for_Computer_Based_Design

[^1_449]: https://www.tandfonline.com/doi/full/10.1080/00401706.2024.2376173

[^1_450]: https://arxiv.org/abs/2508.20878

[^1_451]: https://hal.science/hal-03681614v1/file/119_snh_preprint.pdf

[^1_452]: https://aiche.onlinelibrary.wiley.com/doi/full/10.1002/aic.17357

[^1_453]: https://www.osti.gov/servlets/purl/1985746

[^1_454]: https://www.ideals.illinois.edu/items/129004

[^1_455]: https://www.sciencedirect.com/science/article/abs/pii/S1877750323000066

[^1_456]: https://patents.google.com/patent/WO2024151535A1/en

[^1_457]: https://docs.hpc2n.umu.se/documentation/batchsystem/job_arrays/

[^1_458]: https://prefect-284-docs.netlify.app/ui/task-concurrency/

[^1_459]: https://nrel.github.io/HPC/Documentation/Slurm/job_arrays/

[^1_460]: https://docs.ray.io/en/latest/ray-core/scheduling/index.html

[^1_461]: https://docs.rcd.clemson.edu/palmetto/job_management/arrays/

[^1_462]: https://docs.ncsa.illinois.edu/en/latest/common/slurm/job-arrays.html

[^1_463]: https://stanford-rc.github.io/docs-earth/docs/slurm-arrays

[^1_464]: https://crc-pages.pitt.edu/user-manual/slurm/job-arrays/

[^1_465]: https://docs.nesi.org.nz/Batch_Computing/Job_Arrays/

[^1_466]: https://docs.prefect.io/v3/concepts/tag-based-concurrency-limits

[^1_467]: https://docs.prefect.io/v3/examples/per-worker-task-concurrency

[^1_468]: https://shintaro-iwasaki.github.io/pdfs/papers/PACT2019_paper.pdf

[^1_469]: https://docs.oracle.com/cd/E60778_01/html/E60751/aewbj.html

[^1_470]: https://citeseerx.ist.psu.edu/document?repid=rep1\&type=pdf\&doi=8a99fb7d5046c2f3eed5cc146fef44dde840d1d6

[^1_471]: https://docs.nvidia.com/cuda/cuda-c-programming-guide/

[^1_472]: https://www.intel.com/content/dam/develop/external/us/en/documents/using-nested-parallelism-in-openmp-r1.pdf

[^1_473]: https://docs.nvidia.com/deploy/pdf/CUDA_Multi_Process_Service_Overview.pdf

[^1_474]: https://docs.oracle.com/cd/E19205-01/819-5270/6n7c71vdm/index.html

[^1_475]: https://cuda.live/tutorials/streams-and-concurrency

[^1_476]: https://www.openmp.org/wp-content/uploads/openmp-webinar-vanderPas-20210318.pdf

[^1_477]: https://docs.oracle.com/cd/E37069_01/html/E37081/aewcw.html

[^1_478]: https://www.olcf.ornl.gov/wp-content/uploads/2021/06/MPS_ORNL_20210817.pdf

[^1_479]: https://www.cse.iitm.ac.in/~rupesh/teaching/gpu/jan23/7-streams.pdf

[^1_480]: https://www.cse.iitm.ac.in/~rupesh/teaching/gpu/jan22/7-streams.pdf

[^1_481]: https://ar5iv.labs.arxiv.org/html/2311.00626

[^1_482]: http://www.cad.zju.edu.cn/home/chenwei/vag/xc/files/3DPBA.pdf

[^1_483]: https://dl.acm.org/doi/10.1109/TIP.2019.2916741

[^1_484]: https://www.semanticscholar.org/paper/CUDA-based-Signed-Distance-Field-Calculation-for-Park-Lee/4ce31bd766b2c10e604568ca623c715ca82129f6

[^1_485]: https://www.comp.nus.edu.sg/~tants/pba.html

[^1_486]: https://link.springer.com/chapter/10.1007/978-3-642-11840-1_16

[^1_487]: https://www.semanticscholar.org/paper/CUDA-based-Signed-Distance-Field-Calculation-for-Park-Lee/4ce31bd766b2c10e604568ca623c715ca82129f6/figure/1

[^1_488]: https://www.comp.nus.edu.sg/~tants/pba_files/pba-old.pdf

[^1_489]: https://ideas.repec.org/a/gam/jmathe/v14y2026i4p597-d1860422.html

[^1_490]: https://developer.nvidia.com/gpugems/gpugems3/part-v-physics-simulation/chapter-34-signed-distance-fields-using-single-pass-gpu

[^1_491]: https://al-ro.github.io/projects/sdf/

[^1_492]: https://pdfs.semanticscholar.org/7317/d229ac973272a38e760459b10f781b5bf129.pdf

[^1_493]: https://www.sciopen.com/article/10.1007/s41095-015-0022-4

[^1_494]: https://arxiv.org/abs/2208.00001

[^1_495]: https://deepwiki.com/live-clones/gmsh/7.1-hxt-meshing-library

[^1_496]: https://dialnet.unirioja.es/descarga/articulo/10539969.pdf

[^1_497]: https://www.spec.org/cpu2026/Docs/benchmarks/737.gmsh_r/737.gmsh_r.html

[^1_498]: https://deepwiki.com/sasobadovinac/gmsh/3.3-3d-meshing-algorithms

[^1_499]: https://wildmeshing.github.io/

[^1_500]: https://github.com/wildmeshing/wildmeshing-toolkit

[^1_501]: https://cgg.mff.cuni.cz/gitlab/i3d/fTetWild/-/blame/8b7d1b9c7dae4544c15d0429dedfee2a03ae2e75/README.md

[^1_502]: https://gist.github.com/jorgensd/06f7f41815d91b3df9c3d0e33c6184b7

[^1_503]: https://github.com/wildmeshing/fTetWild/issues/34

[^1_504]: https://github.com/wildmeshing/fTetWild/issues

[^1_505]: https://github.com/zishun/awesome-geometry-processing

[^1_506]: https://github.com/wildmeshing/wildmeshing-python

[^1_507]: https://congress.cimne.com/eccm_ecfd2018/admin/files/fileabstract/a1979.pdf

[^1_508]: https://www.sciencedirect.com/science/article/pii/S0045782516316073

[^1_509]: https://www.academia.edu/22055341/Finite_cell_method

[^1_510]: https://mediatum.ub.tum.de/doc/1536673/1536673.pdf

[^1_511]: https://orca.cardiff.ac.uk/id/eprint/147315/2/PHD_Thesis.pdf

[^1_512]: https://backend.orbit.dtu.dk/ws/portalfiles/portal/200028725/NSCM_32_naage_CutFEM.pdf

[^1_513]: https://www.sciencedirect.com/science/article/abs/pii/S0965997814000684

[^1_514]: https://discovery.ucl.ac.uk/id/eprint/10131329/1/Burman_JOMP_ACCEPTED.pdf

[^1_515]: https://digitalcommons.unl.edu/cgi/viewcontent.cgi?article=1043\&context=mechengfacpub

[^1_516]: https://onlinelibrary.wiley.com/doi/abs/10.1002/nme.7093

[^1_517]: https://research.chalmers.se/publication/541440/file/541440_Fulltext.pdf

[^1_518]: https://csma2024.sciencesconf.org/499650/document

[^1_519]: https://link.springer.com/article/10.1007/s00158-025-04083-y?error=cookies_not_supported\&code=cde5d0f0-6861-49f5-861a-6e3903fe922a

[^1_520]: https://www.scribd.com/document/937281787/gmsh

[^1_521]: https://github.com/fangq/iso2mesh/blob/master/cgals2m.m

[^1_522]: https://github.com/fangq/iso2mesh/blob/master/cgalv2m.m

[^1_523]: https://elib.dlr.de/140195/1/Kusum_automatic_meshing_program_Master_thesis.pdf

[^1_524]: https://www.cgal.org/

[^1_525]: https://doc.cgal.org/5.1.5/Tetrahedral_remeshing/examples.html

[^1_526]: https://deepwiki.com/sasobadovinac/gmsh/3.4-high-order-mesh-generation

[^1_527]: https://manpages.debian.org/trixie/iso2mesh-tools/cgalmesh.7.en.html

[^1_528]: https://doc.cgal.org/5.4.2/Tetrahedral_remeshing/index.html

[^1_529]: https://doc.cgal.org/5.2/Tetrahedral_remeshing/index.html

[^1_530]: https://www.scribd.com/document/429517556/Gmsh-Manual

[^1_531]: https://gitlab.onelab.info/gmsh/gmsh/-/issues/816

[^1_532]: https://github.com/NVIDIAGameWorks/kaolin

[^1_533]: https://gist.github.com/cgmb/51c24714ea537565141cf9c426c2da00

[^1_534]: https://academysoftwarefoundation.github.io/openvdb/MeshToVolume_8h_source.html

[^1_535]: https://academysoftwarefoundation.github.io/openvdb/VolumeToMesh_8h_source.html

[^1_536]: https://github.com/NVIDIAGameWorks/kaolin/blob/master/README.md

[^1_537]: https://github.com/AcademySoftwareFoundation/openvdb/blob/master/openvdb_cmd/vdb_tool/README.md

[^1_538]: https://www.openvdb.org/documentation/doxygen/python.html

[^1_539]: https://github.com/AllwineDesigns/vdb_cmd

[^1_540]: https://docs.nvidia.com/nsight-compute/2020.1/pdf/ProfilingGuide.pdf

[^1_541]: https://docs.nvidia.com/cuda/archive/12.5.0/profiler-users-guide/index.html

[^1_542]: https://docs.nvidia.com/cuda/profiler-users-guide/index.html

[^1_543]: https://isaac-sim.github.io/IsaacLab/develop/source/overview/core-concepts/physical-backends/newton/warp-environments.html

[^1_544]: https://docs.nvidia.com/learning/physical-ai/getting-started-with-newton/latest/newton-fundamentals/core-concepts.html

[^1_545]: https://nvidia.github.io/warp/changelog.html

[^1_546]: https://mujoco.readthedocs.io/en/3.7.0/\_sources/mjwarp/index.rst.txt

[^1_547]: https://github.com/KarypisLab/ParMETIS

[^1_548]: https://github.com/KarypisLab/parmetis

[^1_549]: https://github.com/chiao45/mgmetis

[^1_550]: https://karypis.github.io/glaros/files/sw/parmetis/manual.pdf

[^1_551]: https://github.com/KarypisLab/ParMETIS/blob/main/README.md

[^1_552]: https://github.com/numpex/metis

[^1_553]: https://github.com/KarypisLab/metis/

[^1_554]: https://github.com/hydro-informatics/metis

[^1_555]: https://libmesh.github.io/doxygen/parmetis\_\_partitioner_8C_source.html

[^1_556]: https://lumi-supercomputer.github.io/LUMI-EasyBuild-docs/p/ParMETIS/ParMETIS-4.0.3-cpeAOCC-22.06/

[^1_557]: https://packages.gentoo.org/packages/sci-libs/parmetis

[^1_558]: https://sandialabs.github.io/Zoltan/ug_html/ug_alg_parmetis.html

[^1_559]: https://lumi-supercomputer.github.io/LUMI-EasyBuild-docs/p/ParMETIS/ParMETIS-4.0.3-cpeAMD-22.08/

[^1_560]: https://docs.easybuild.io/version-specific/supported-software/p/ParMETIS/

[^1_561]: https://lumi-supercomputer.github.io/LUMI-EasyBuild-docs/p/ParMETIS/ParMETIS-4.0.3-cpeAMD-23.09/

[^1_562]: https://pybind11.readthedocs.io/en/stable/advanced/functions.html

[^1_563]: https://pybind11.readthedocs.io/en/stable/advanced/pycpp/index.html

[^1_564]: https://stackoverflow.com/questions/42521830/call-a-python-function-from-c-using-pybind11

[^1_565]: https://github.com/pybind/pybind11/issues/2005

[^1_566]: https://gist.github.com/terasakisatoshi/79d1f656be9023cc649732c5162b3fc4

[^1_567]: https://pybind11.readthedocs.io/en/stable/reference.html

[^1_568]: https://pybind11.readthedocs.io/en/stable/changelog.html

