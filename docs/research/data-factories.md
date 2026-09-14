# How the companies building physics AI make their data

What the job ads, products and papers of the companies building physics AI say about how they make
training data - geometry, meshing, solving, running at scale, how much data, agents - and what
fastcae takes from it. A company hires for its bottleneck, so its job ads show what it is building
now. Read 14 September 2026 on the companies' own job boards: NVIDIA (507 postings, through its
Workday search), Neural Concept (35), PhysicsX (42), Luminary Cloud (17), Mistral AI, Synopsys/Ansys,
Cadence/BETA CAE, Siemens/Altair, Dassault Systèmes, Autodesk, nTop, BeyondMath, Navier AI, Rescale
and CoreWeave. Postings since closed were read on job-board mirrors, and are marked so.

## What they do

- **Data generation is a factory of its own.** PhysicsX's Senior Simulation Data Engineer (closed;
  [mirror](https://careers.atomico.com/companies/physicsx/jobs/74279471-senior-simulation-data-engineer))
  builds a "Data Factory… that orchestrates thousands of CFD simulations per day on cloud compute":
  "mesh preparation, morphing, watertightness validation", checks of "solver convergence, physical
  field bounds", and bad data quarantined. BeyondMath's
  [simulation engineer](https://jobs.ashbyhq.com/beyondmath/63725706-95b3-476c-944e-a85873fe584a) is the
  "guardian of the ground truth". nTop's distributed-computing team
  ([posting](https://jobs.gem.com/ntop/am9icG9zdDrST58zgyuRJEkIZxNkOJUO)) has one north-star metric:
  "headless nTop notebook executions".
- **Geometry comes from morphing one baseline or driving parametric CAD, sampled by Latin
  hypercube.** Luminary's [SHIFT-SUV](https://huggingface.co/datasets/luminary-shift/SUV) uses a
  "deformation cage approach to morph"; [SHIFT-Wing](https://luminary.ai/resources/shift-wing-a-physics-ai-model-to-accelerate-aircraft-design-innovation/)
  a parametric Onshape model, 2,276 of 3,000+ runs kept for training; PhysicsX's
  [CFD engineers](https://job-boards.eu.greenhouse.io/physicsx/jobs/4644844101) "parametric CAD models
  (NX or CATIA)… DoE"; [DrivAerML](https://arxiv.org/abs/2408.11969) morphs 16 parameters in ANSA. No
  posting checks variants against manufacturing rules.
- **Meshing is where the senior hires go.**
  - Luminary: a C++17/CUDA engineer for the "toughest technical challenges related to geometry
    ingestion and mesh generation" ([posting](https://ats.rippling.com/luminarycloud/jobs/f84e11f6-9b15-4a4d-b25b-4adfadc98fb6)).
  - Synopsys: "AI/ML-driven algorithms for 3D geometry processing and mesh generation"
    ([posting](https://synopsys.avature.net/careers/JobDetail/18520-Staff-Engineer-R-D-Engineering/18520));
    Ansys 2026 R1 ships a [Mesh Agent](https://news.synopsys.com/2026-03-11-Synopsys-Launches-Ansys-2026-R1-to-Re-Engineer-Engineering-with-Joint-Solutions-and-AI-Powered-Products)
    to fix failed meshes.
  - Cadence/BETA: an "AI Meshing" engineer ([posting](https://cadence.wd1.myworkdayjobs.com/External_Careers/job/THERMI-01/Software-Engineer-II----Meshing_R55841));
    Siemens: a product manager for "batch meshing workflows" ([posting](https://jobs.siemens.com/en_US/externaljobs/JobDetail/519201)).
  - Dassault: "over 70% of simulation time goes toward … model cleanup or manual meshing"
    ([blog](https://blog.3ds.com/brands/simulia/generative-simulation-fix-slow-high-tech-workflows/));
    nTop: "your geometry breaks at case 47" ([blog](https://www.ntop.com/resources/blog/ntop-coreweave-nasa-2030-grand-challenge-in-cfd/));
    NVIDIA: the remaining challenges are "computer-aided design, meshing, simulation setup and
    debugging" ([blog](https://blogs.nvidia.com/blog/industrial-software-leaders-secure-autonomous-ai-engineers-nemoclaw/)).
- **Structural training data comes from CPU codes** - Abaqus, Nastran, LS-DYNA, OpenRadioss,
  CalculiX; no posting names a GPU finite-element solver. NVIDIA's cuDSS is in Ansys HFSS and Altair
  OptiStruct ([NVIDIA](https://blogs.nvidia.com/blog/cuda-x-grace-hopper-blackwell/)) and COMSOL 6.4
  ([COMSOL](https://www.comsol.com/release/6.4/gpu-acceleration)); none was found in Ansys Mechanical.
- **Speed comes from running many at once**: Slurm, Kubernetes and Temporal at PhysicsX; nTop with
  CoreWeave, 12,000 runs of 2,400 variants on 280 GPUs "without any geometry failures"; Inductiva,
  "hundreds of cloud machines" ([blog](https://inductiva.ai/blog/article/supercharge-your-physics-ml-with-inductivas-cloud-based-simulation-api));
  Luminary, over 1,000 runs of about 1.2 H100-hours each ([blog](https://luminary.ai/resources/introducing-luminary-shift-models-a-suite-of-physics-ai-foundation-models-to-transform-engineering-design/)).
- **Products train from tens of runs; thousands appear in showcases.** Ansys SimAI: "typically 30 to
  100 simulation results" ([FAQ](https://ansys.synopsys.com/products/ai/simai)); Altair PhysicsAI: "at
  least 10 … many require dozens or even hundreds" ([FAQ](https://altair.com/physicsai-studio)); a
  Siemens gear-stress study trained on 64 ([blog](https://blogs.sw.siemens.com/simcenter/ai-accelerated-gear-stress-analysis/)).
  Mistral's physics team, built from Emmi AI, wants "one model serving an entire design family"
  ([blog](https://mistral.ai/news/introducing-physics-ai-at-mistral/)) with uncertainty and
  out-of-distribution estimation "first-class" ([posting](https://jobs.ashbyhq.com/mistral.ai/3fb3a425-b151-4ad6-be40-7049249f919a));
  PhysicsX asks "is it better to train a bigger model or to generate more data?"
  ([posting](https://job-boards.eu.greenhouse.io/physicsx/jobs/4922319101)).
- **Agents run the pipeline; they do not predict physics.** Rescale hardens "early agent use cases into
  deterministic, production-ready systems" ([posting](https://jobs.ashbyhq.com/rescale/5c035308-cc3b-4cd4-bd9d-9fb4624f1bfd));
  Navier's agents clean geometry, mesh, set up and run solvers, each run shipped "as a report with its
  assumptions, mesh, boundary conditions, and convergence history" ([site](https://www.navier.ai/));
  Mistral asks its engineers to "define verifiers" ([posting](https://jobs.ashbyhq.com/mistral.ai/f090ef1d-372e-40dc-bf46-ce0bf2850204));
  Siemens builds MCP into STAR-CCM+ ([posting](https://jobs.siemens.com/en_US/externaljobs/JobDetail/519123)).
- **People go into delivery.** Delivery and forward-deployed roles are 27 of PhysicsX's 42 openings,
  9 of Luminary's 17 and 16 of Neural Concept's 35: each customer's pipeline - "design change,
  automated meshing, solver configuration, job execution" with Abaqus, ANSA and HyperMesh - is wired
  by hand ([Neural Concept](https://jobs.ashbyhq.com/neuralconcept/b8c0c95e-3279-4259-8c21-80014db3b4dd)).

## Space by space, them and fastcae

| | The market | fastcae |
|---|---|---|
| **Design variants** | parametric CAD (NX, CATIA, Onshape) or a baseline morphed, sampled by Latin hypercube; learned generators (Ansys GeomAI, Siemens PhysicsAI Generate, Neural Concept's Copilot) that imitate past designs; nTop's field-based modelling, "without any geometry failures" on 2,400 variants; CAD sweeps failing 70-80 % (nTop) | rule-valid variants of the engineer's own part, placed and repaired by CP-SAT, built as a distance field - every design obeys every encoded rule, none fails to rebuild |
| **Geometry to mesh** | the senior hires: batch meshing (ANSA, HyperMesh BatchMesher, Ansys Prime), a Mesh Agent to fix failures, C++/CUDA meshing engineers; morphing where topology stays | the field meshed directly by a compiled CGAL mesher, 8-14 s, nothing to heal; as good as meshing the CAD within the mesh's own noise - where agenticCAE's gmsh-and-MeshFix route leaves out faces ([field-meshing-gate.md](field-meshing-gate.md)) |
| **Solving** | CPU codes for structural data (Abaqus, Nastran, LS-DYNA, OpenRadioss, CalculiX); cuDSS in Ansys HFSS, OptiStruct, COMSOL; GPUs for CFD and training | TET10 by cuDSS on the GPU, 5-10 s a design; Code_Aster re-solving a sample |
| **Running many** | fleets: Slurm, Kubernetes, Temporal; 280 GPUs (nTop with CoreWeave); "hundreds of cloud machines" (Inductiva); thousands of runs a day (PhysicsX) | a runner keeping the laptop's GPU and cores busy at once; the same build on rented GPUs later |
| **How much data** | products from tens of runs (SimAI 30-100, PhysicsAI from 10); thousands in showcases; active learning in SimAI, PhysicsAI, ODYSSEE, Monolith | rounds that double from 300 to at most 4,000, at least half random, stopping when a doubling stops helping ([surrogates.md](surrogates.md)) |
| **Quality and trust** | runs quarantined, samples traceable to geometry and settings, a "guardian of the ground truth"; reports per run (Navier) | a design failing is set aside with its reason; every record keeps its recipe, versions and checks; mesh reports per design; the noise of meshing measured |
| **Agents** | operating the pipeline - geometry cleanup, meshing, setup, failure triage, reports; "verifiers" (Mistral); MCP into STAR-CCM+ (Siemens) | one copilot with helpers - failed runs, data checks, the next batch - every step logged, every spend approved |
| **People** | delivery: 27 of PhysicsX's 42 openings, 16 of Neural Concept's 35 - each customer's pipeline wired by hand | the pipeline itself - STEP and rules in, labelled designs out |

## Tools checked for fastcae's route

- **CGAL Mesh_3** reads a float grid itself, with trilinear interpolation - its gray-image domain
  ([source](https://github.com/CGAL/cgal/blob/master/Mesh_3/include/CGAL/Mesh_3/Labeled_mesh_domain_3_image.h),
  [example](https://github.com/CGAL/cgal/blob/master/Mesh_3/examples/Mesh_3/mesh_3D_gray_image.cpp)) -
  so a compiled module needs no call back into Python. Its parallel mode (`Parallel_tag`, TBB) refines
  3.4-4.2× faster on 4 threads ([manual](https://doc.cgal.org/latest/Mesh_3/index.html)); perturbation
  and exudation run by default.
- **pygalmesh 0.10.7** never sets CGAL's `relative_error_bound`, so surface points are found to a
  thousandth of a box round a sphere about the origin ([source](https://github.com/meshpro/pygalmesh/blob/main/src/generate.cpp)) -
  up to about 1.1 mm on the housing, whose sphere is 1,241 mm. It has no compiled grid domain:
  `generate_from_array` takes integer labels only.
- **GPU tet meshing is not ready for graded TET10**: gDel3D triangulates points only
  ([repo](https://github.com/ashwin/gDel3D), 2018); gQM3D refines a surface mesh without removing
  slivers ([paper](https://arxiv.org/abs/1903.03406)); Quartet ([repo](https://github.com/crawforddoran/quartet),
  two commits, 2014) and PhysicsNeMo 2.2's `mesh_implicit_domain`
  ([releases](https://github.com/NVIDIA/physicsnemo/releases), August 2026) make tets of one size.
- **A surface to look at, from a grid, in under a second**: VTK's Flying Edges contours 432³ cells in
  0.21 s on one thread ([Kitware](https://www.kitware.com/really-fast-isocontouring/)); Warp has GPU
  marching cubes; Kaolin's FlexiCubes is Apache-2.0 ([repo](https://github.com/NVIDIAGameWorks/kaolin/blob/master/README.md)).
- **gmsh** runs on one thread unless `General.NumThreads` says otherwise ([manual](https://gmsh.info/doc/texinfo/gmsh.html)).
- **Morphing** ([PyGeM](https://github.com/mathLab/PyGeM)) holds only while a mesh's connectivity
  stays: a rib that appears, disappears or slides is out of its reach.
- **cuDSS** cannot reuse its analysis between meshes of different sparsity; its reordering runs on the
  CPU ([docs](https://docs.nvidia.com/cuda/cudss/)). Keeping part of its factor in host memory it
  solved 1.49 M unknowns on the 8 GB card in 10 s; it failed at 2.4 M.
- **NVIDIA's own tools for fastcae's CPU steps** (Warp 1.17, PhysicsNeMo 2.2): Warp's closest-point,
  ray and sphere queries for the checks and face moves; Kaolin's FlexiCubes, NVIDIA's GPU dual
  contouring, for drawing a surface; PhysicsNeMo 2.2's `mesh_implicit_domain`, a GPU tet mesher for
  implicit fields - linear tets of one size, 18 days old when read, not yet shown on engineering
  stress; Warp's ahead-of-time compilation and shared kernel cache for runner start-up. fVDB 0.5 (Linux)
  for sparse voxel models on distance fields.
- **PhysicsNeMo-Curator** ([repo](https://github.com/NVIDIA/physicsnemo-curator)) writes Zarr or
  memory-mapped `.pmsh`; NVIDIA found VTU's XML parsing made the data loader the bottleneck
  ([blog](https://nvidia.github.io/physicsnemo/blog/2026/04/07/physicsnemo-mesh/)).

## Where fastcae stands

The companies above hire to fix geometry and meshing. fastcae's designs are born as fields: every
design obeys the part's rules and meshes straight from its field, with nothing to heal. What fastcae
takes from them is the factory's discipline - a runner that sets failures aside with their reason,
every design traceable to its recipe, data in rounds against a fixed test set - and what it leaves:
morphing (its ribs appear and disappear), GPU tet meshing (not ready), and Kubernetes before one
machine is full. The decisions are in [../build-plan.md](../build-plan.md).
