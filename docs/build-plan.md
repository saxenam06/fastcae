# Build plan

**The plan as agreed.** What is built, in what order, and how each step is judged. The design space
is one defined volume; designs are optimised in it, read as ribs, made as their own CAD, meshed face
by face and solved; the next phase regularises them into families and takes them to a trained,
trusted surrogate. The design space is in [design-space.md](design-space.md), the pipeline in
[pipeline.md](pipeline.md), designs in [designs.md](designs.md), the research behind the next phase in
[research/](research/README.md); what runs today in [status.md](status.md).

---

## What is being built

Generative design in CAD tools gives a handful of optimal shapes per setup, which someone then
redraws. ZenryxAI gives thousands of production-grade variants of the engineer's own part - meaningful
families of ribs, symmetric where the part is, each variant its own CAD, meshed and solved exactly as
the engineer's deck solves the part. A surrogate trained on them finds designs that do well on
several objectives at once - each a real, castable design - and shows which choices matter for the
next one.

The engineer brings a plain STEP file, its solver deck with the answer it gave, and its drawing when
there is one - and its design space when there is one; where there is none, fastcae defines it from
the files and keeps it with the part. The designs grow inside it.

## What is agreed

1. **Crisp features are a hard requirement.** Bores stay exact cylinders, edges stay sharp, holes
   round, in every mesh that is solved. Cells, shells and fields never produce training data.
2. **Every design is its own CAD.** Its rib solids - a section swept along a line, with its own
   flared foot and draft - are fused locally into the baseline's STEP by OpenCascade, with no fillet
   after the fuse. A fuse that fails is rejected, labelled, and another design drawn in its place -
   never a mesh made another way.
3. **Meshed as the baseline is.** Every design is meshed face by face as TET10 with the recipe the
   baseline's deck mesh is made with (`src/fastcae/simulate/face_mesh.py`), and solved by cuDSS -
   which reproduces the deck's Code_Aster answer on that mesh to about 10⁻¹⁰.
4. **The design space is defined, one volume.** Taken as an input kept with the part; where none is
   brought, fastcae's rules define it from the CAD, the deck and the drawing: a layer three walls deep
   over every wall, outside and in, and the pockets between features, clear of every bore's bearing,
   shaft and collar, of what mates against held faces, and of every fastener and its tool
   ([design-space.md](design-space.md)). No questions, no workflow to derive it on screen.
5. **Where metal goes is optimised, then kept as ribs.** For each load mix the deck offers and each
   volume of metal, the layout is optimised on the voxel grid (BESO) and read as rib plates, fused into
   the part's CAD ([designs.md](designs.md)). Next, the ribs are straightened, snapped to what they
   meet, and regularised by CP-SAT - mirror pairs, a set of angles, spacing - into families; designs
   are drawn inside a family, never as random stacks of variants.
6. **One pipeline of typed entities.** Every step's inputs and outputs are entities with an origin,
   evidence and links; the interface and the agent read the same ones ([pipeline.md](pipeline.md)).
   Everything derived is kept in the cache while nothing it depends on changes.
7. **Minimal input, general code.** No code names a part's faces; no step is written for one part or
   one request.
8. **Not pursued**: learned CAD generators (HNC-CAD and its kind), a library of B-rep operators over a
   hand-built context graph, agents driving a CAD tool's feature tree, and GET, MMC or TreeTOp as the
   source of patterns - TreeTOp's blending may refine a family later. Variants authored by hand on a
   card are out of the main flow; the variant library stays readable for the campaigns made from it.

## The pipeline

```
STEP + deck + drawing
      │  Read: faces, features, callouts, deck groups, supports, couplings, loads - tied to CAD faces
      ▼
design space ─── one volume, kept with the project: the engineer's, or defined by the rules
      │           (outside and inside, clear of bores, held faces, fasteners) · where metal helps
      ▼
optimise ─── per load mix and volume of metal, on the voxel grid (BESO)
      │
      ▼
ribs ─── the layout read as plates ─► [next: ridges straightened, CP-SAT families]
      │
      ▼
designs ─── plates fused into the part's CAD, a STEP each (a failed fuse or mesh: rejected)
      │
      ▼
mesh ─── face by face, TET10, the baseline's recipe ─► the deck's setup by CAD face ─► cuDSS
      │
      ▼
record ─── Zarr per design, Parquet of metrics, the recipe and every check ─► rounds ─► surrogate
```

## Steps

Each step names what is built and what shows it done. Every step keeps the tests passing.

**1. The design space, one defined volume** - built.
- `src/fastcae/space/`: kept in the project's folder and read back; defined by the rules where none
  is brought; where metal helps on every cell.
- *Done*: on the housing, 319 L defined in 81 s and read back in a second; on a closed box with a bore
  and holes and no deck, the inside found to its true volume, the bore kept clear with its collar
  outside it.

**2. The pipeline as typed entities, on screen** - built.
- `src/fastcae/pipeline/`: the entity kinds, the Read steps and the design space as entities, one
  graph with links both ways.
- The interface: four tabs - Input, Generate, Learn, Optimize; the pipeline as Input's rail; focus
  on the drawing, the CAD, the design space and the deck's mesh; the card; the agent over the same
  entities.

**3. The baseline, reproduced on its face-by-face mesh** - built. cuDSS against Code_Aster on the deck
mesh made by `face_mesh.py`: about 10⁻¹⁰ on the fields, 30 s against 196 s; a fresh mesh of the same
CAD, the deck carried by CAD face, reproduces the deck node for node.

**4. Designs as CAD, end to end** - built. Optimised per load mix and volume of metal, read as plates,
fused into the part's CAD, meshed face by face, the deck carried by CAD face, solved by cuDSS; a
failed fuse or mesh rejected with its reason; every stage on screen. The runner makes a campaign
(`ribs.network`, [designs.md](designs.md)).

**5. Families.** The plates straightened and snapped, CP-SAT's families - mirror pairs, angles,
spacing; members drawn inside a family. *Done when* the housing yields families an engineer
recognises as ribs and their members build as CAD.

**6. Designs run at scale.** Two or three designs in progress at once - the GPU optimising and
solving, the cores meshing - shown as a timeline.

## Next: from designs to a trained, trusted surrogate

Agreed with the engineer on 14 September 2026. The research behind each choice is in
[research/](research/README.md); how the companies building physics AI make their data, in
[research/data-factories.md](research/data-factories.md); the field meshed against the real CAD, in
[research/field-meshing-gate.md](research/field-meshing-gate.md).

**How speed is judged.** A trusted model, not 4,000 solves, is the goal, so the data comes in rounds
that stop when they stop helping. What counts is designs finished an hour - how many run at once times
how fast each is. The slowest step is worked first; a step is deleted before it is sped up, compiled
before it is moved to the GPU, and never called back and forth once per point. Speed never moves the
answer: the setup is settled before data is made, since how bolts are held moves results 40 % where a
mesher moves them 2 %. At thousands of designs, failures and the slowest designs matter more than the
average.

**What it is for.** ZenryxAI first as a **castable training-data factory**: a plain STEP file and its
rules in; castable variants, meshes, solved labels and standard records out, ready for any physics-AI
platform. The GRC gearbox run is its showcase and the first public dataset of solved cast-part
variants; the other markets in [research/market.md](research/market.md) follow. No date - the best
product.

### Decided

1. **Compute.** Open-source solvers. This workstation first (RTX 5060 Laptop 8 GB, 16 cores, 16 GB
   RAM), its GPU and cores working at once: what needs Linux (the compiled mesher, Code_Aster) runs
   in WSL, the rest on Windows. The same Linux build later on rented GPUs (RunPod) for large rounds,
   and for training when the laptop is not enough.
2. **Physics: agenticCAE's setup as it is, one version.** Linear static; DLC 1.3 extreme, 401 kN·m on
   the low-speed shaft; its material; its supports - each of the 25 bolt positions a kinematic
   coupling to a centre node held fixed, each of the 9 bearing bores a distributed coupling to a
   centre node on its axis, where the service loads go in. Which nodes a coupling takes and how each
   result is measured follow agenticCAE's code, so every design stands beside its 490 solved
   designs. One load case to start, the 16-unit-load basis kept switchable. Modal and harmonic
   later, by agenticCAE's method.
3. **Solving**: quadratic tets (TET10) by cuDSS on the GPU - Code_Aster's answer to 3·10⁻¹⁰, 5 s at
   0.9 M unknowns; past what the card holds, cuDSS keeping part of its factor in host memory (1.49 M
   unknowns in 10 s); Code_Aster re-solving a sample as the audit. PETSc is not used. Measured on
   design #7 of campaign `w4zf5` and agenticCAE's design e56235 against six other solvers and two grid
   methods: [../bench/solvers/RESULTS.md](../bench/solvers/RESULTS.md); why each got its result and
   what not choosing the others gives up: [research/solver-choice.md](research/solver-choice.md).
4. **Meshing**: every design face by face from its own CAD, TET10, by the recipe the baseline's
   deck mesh is made with (`src/fastcae/simulate/face_mesh.py`) - bores round, edges crisp, sizes graded,
   no lids. The compiled CGAL field mesher (`native/cgal_field/cgal_field.cpp`) measured below meshes
   a field, not a CAD, and makes no training data.
5. **The gate: the field route against real CAD** - run. The production housing with its ribs and
   fillets (`assets/_archive/254492_0_closed_volume.step`), in a scratch project, never a project's
   part or a source for designs, meshed four ways: the CAD's own surface by the same compiled mesher
   (the judge); its 3 mm field (the field route); the field again from another random start (the
   noise of meshing itself); and agenticCAE's route as it ran its 490 designs - gmsh on the CAD's
   faces, weld, collapse, MeshFix, gmsh tets. All four held to the element sizes of agenticCAE's own
   mesh of the part (1.1-1.2 M unknowns), the same seat edge lines and labels, solved by Code_Aster
   with agenticCAE's couplings. **The field matches the CAD within the noise of meshing itself**:
   the leads, p99.9 and the displacement map meet their marks; the worst seat's tilt (7%), the stress
   map (17%) and the peaks miss theirs by the same amounts meshing the same field twice moves them -
   marks tighter than a mesh of this size holds, whichever route made it. It stands as a
   measurement: the agreed route meshes every design from its own CAD (4 above).
   agenticCAE's route leaves out six faces, lids their holes flat and cuts into metal under a seat -
   20-53% off on two seats. Snapping the field mesh's boundary onto the CAD changed nothing that
   matters and distorted elements. Measured in
   [research/field-meshing-gate.md](research/field-meshing-gate.md).
6. **A design in a run**: its rib solids fused into the baseline STEP, meshed face by face, the
   deck's setup carried by the CAD faces its groups lie on, weighed exactly from its CAD; every check
   timed, the slow ones made fast.
7. **Runs**: a runner outside the development server keeps 2-3 designs in progress like a conveyor -
   the GPU builds and solves, the cores mesh, one solve at a time. A failed design is tried once more
   on the fallback, then set aside with its reason, and the run goes on. The run's design list shows
   each design's stage and time, designs an hour and how many were set aside; the Agent tab's log
   the same events. A run uses the whole workstation unless a setting leaves room. The effect is
   shown on 20 designs run one, two and three at a time, as a timeline.
8. **The 40-design check**, before round 1: 40 designs as varied as the families allow; at most 1 in
   50 fails; Code_Aster re-solves 10 on the same mesh and agrees within 0.1%; every mesh report shows
   the features held.
9. **Data in rounds**, not 4,000 at once: 300 spread evenly, with a fixed test set of 300 never
   trained on; then 600, 1,200, 2,400 and 4,000. At least half of each round is random, the rest
   picked by the agent from the last results.
10. **The field model**: stress and displacement anywhere on the part, from the design's distance
    field (PhysicsNeMo); agenticCAE's metrics; mass computed exactly from geometry, never learned.
11. **Accuracy and stopping**, on the test set: tilt and misalignment within 5%, p99.9 stress within
    10%, displacement maps within 5%, stress maps within 15%, confidence ranges holding the true value
    90% of the time. Stop when a doubling improves these by less than 10%, or at 4,000 designs.
12. **Data format**: a PhysicsNeMo Zarr folder per design, a Parquet table of metrics, and a record per
    design - its recipe, loads, solver version and every check it passed.
13. **Publishing**: the validated GRC dataset openly, on Hugging Face under an open licence; the
    generator stays private.
14. **Validation**: the gate against real CAD and Code_Aster's re-solves now; NREL's measured data
    later.
15. **Agents**: one copilot the engineer talks to, in a dedicated Agent tab with a live log; helpers
    behind it - failed runs, data checks, the next batch, explanations - each labelled in the log.
    Safe, undoable steps they do themselves; anything that changes the design space or spends money
    waits for the engineer's yes. Built on LangGraph; models through OpenRouter chosen per helper - a
    cheap one for routine watching, Claude for next batches and explanations - each switchable to
    DeepSeek. No Slack or Teams.
16. **GRC only** for now; a second part once the loop runs.

### In this order

1. The baseline's own solver deck as an input, meshed face by face, reproduced by cuDSS - built
   ([research/baseline-deck.md](research/baseline-deck.md)).
2. The design space as one defined volume, and the pipeline on screen - built.
3. Designs as CAD, end to end, every stage on screen - built.
4. Families (step 5).
5. Designs run at scale, as a timeline (step 6).
7. The 40-design check.
8. Round 1.

### Open

- **A design too big for the card** - past what cuDSS holds with its factor partly in host memory;
  recommended: Code_Aster in WSL, about 2-3 minutes a design, rare.
- **Optimisation** - repair weighted by each piece's worth; pymoo on the surrogate with CP-SAT as its
  repair, then BoTorch/Ax with real solves (see [research/optimization.md](research/optimization.md)).
- **Plates from a layout.** Plates keep about half the metal the optimiser placed, the thickest
  members held to two walls; some spill a little outside the design space.
- **The whole gearbox in context** - the assembly, each rotating part swept round its axis - so the
  inside is kept clear of what turns there, not only of each bore's bearing and a shaft. Later.
- **What a record keeps** - a design's Zarr store is about 28 MB with the volume (TET10 connectivity,
  displacement and von Mises at every node) beside agenticCAE's surface arrays; about 110 GB at
  4,000 designs. The surface alone and the field would be about a third of that.
- **The Code_Aster fallback** needs 6-7 GB of its own in WSL; starved of memory by the runner it
  took seven times as long and ran out its 15 minutes. It now runs one at a time with no design
  starting meanwhile, and is called only when cuDSS fails twice. On a machine with more memory the
  runner could leave it room instead of pausing.

## Later

- **The engineer's review loop**: about twenty representatives a round - medoids, the most novel,
  the nearest a hard rule, the least certain - pointing at a rib, readings of an objection with
  the number of designs each would remove, confirmed rules.
- **Quality-diversity search**: an archive over a few measures of the design, emitters aimed at
  its empty cells; staggered crossings as a pattern; free layouts grown from a graph of legal
  connections between regions.
- **Mould release** with the pull and with cores; then draft and undercut maps.
- **Wall fields**: thickness varied smoothly over a region, fading to nothing at what is held.
- **Gated solves**: the same design solved twice agrees within 0.1%; MAP-Elites; a design the
  surrogate recommends solved for real before it is called good.
- **A second part**, with its own deck, once the loop runs on the housing.
- **Scale**: an unseen housing with no code changed; campaigns spread over every core; orchestration
  (Dagster, when the published dataset needs its lineage) and data versioning when campaigns outgrow
  one machine.
- **A finer-mesh study** on a few designs, if the mesh reports ever leave doubt - the gate measured the
  noise of meshing at 1.2 M unknowns: up to 7 % on the smallest seat's tilt, 18 % on element stresses.
- **Fillets held to their radius** where a design changes the part - 1.72 M unknowns on design #7,
  likely within the card - tried once the runner exists.
- **NVIDIA's GPU mesher for implicit fields** (PhysicsNeMo 2.2, tets of one size): a one-day trial.

## Always

- No code names a part's faces or an example sentence.
- Every campaign kept builds its designs again exactly after every change.
- Docs describe what is true now and the design as agreed; nothing records a journey.
- Nothing is committed and no server is started without the engineer saying so.

## Open

- **A second housing** with a drawing, allowed to be used - from the engineer, or a public model
  with a clear licence.
- **Which material the housing is cast in**: one, never varied - assumed the ductile iron
  wind-turbine housings are cast in by default, EN-GJS-400-18-LT; the drawing names the material
  only as the existing housing's.
- **The client's solver deck**, when there is one.
- **Employment and IP terms** to check before any commercial step with driveline suppliers - for a
  lawyer.
