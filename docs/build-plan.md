# Build plan

**The plan as agreed.** What is built, in what order, and how each step is judged. Variants and
campaigns are built; the next phase takes their designs to a trained, trusted surrogate. The design
behind the variants is in [ribs.md](ribs.md); the research behind the next phase in
[research/](research/README.md); what runs today in [status.md](status.md).

---

## What is being built

Generative design in CAD tools gives a handful of optimal shapes per setup, which someone then
redraws. ZenryxAI gives thousands of near-production variants of the engineer's own part that already
follow their rules, with solver decks. A surrogate trained on them finds groups of designs that do
well on several objectives at once - each a real, castable design - and shows which choices matter
for the next design.

The engineer brings a plain STEP file and its drawing. On the CAD tab they author **variants**: each
one change in one place - ribs on a floor, webs between two faces, a wall thickened, holes through a
plate - with what it may vary and every rule it must hold. On the Generate tab they compose a
**campaign** from the variants they choose, see how many combinations it could make, screen a
hundred in half a minute, and launch it - twenty designs to try the flow, four thousand for a
training set. The designs appear in Designs with their stages - paths, field, mesh, setup, results -
and the ones that differ most side by side.

## What is agreed

1. **A variant is one change in one place**: ribs on, webs between, faces thickened or thinned,
   holes in. It carries what always comes with it - ribs bring their pads; a floor is never
   thickened under them. Its identity is a short random code and a name that says what and where
   (`k7f3a · Ribs on face:1201`). The part's alloy is not a variant: a part is cast in one material.
2. **A variant holds everything that decides its designs**: where (what it stands on, ends on, keeps
   clear of - faces, or another variant's ribs or holes; for webs, the two sides they run between,
   from one to the other and never within one), what it may vary, and every rule it is held to.
   Each lever is fixed, a range with a step, or a set of options. Every range steps by 5 in its own
   unit unless the engineer says otherwise; height is in percent. Patterns are options: parallel,
   square grid, triangle grid, spokes, and **free** - independent lines at any angle and position -
   so "only square" is one choice and "anything" another. Drawn at random, every option and every
   step is as likely as the next.
3. **Only rules that are checked are offered.** A rule the pipeline cannot hold a design to is not
   on the card. Rules a variant may hold: keep clear of, no taller than, at most so tall, every rib
   ends on what it runs between, no rib thicker than a share of the wall it meets, no radius under,
   room for the sand between ribs (root gap), and no X crossings.
4. **The part's interfaces are held for every variant**: bores, holes, what the drawing controls and
   its datums, each citing where it is known from. Everything else is open.
5. **Variants are edited freely.** A campaign keeps a copy of each variant as it was when it was
   launched, so its designs can always be built again; the library says which campaigns used a
   variant and whether it changed since. Versions exist inside, never on the screen.
6. **A campaign is a card**: its name, the variants it takes, which screening checks it holds,
   how designs are drawn - spread evenly (the default), random, or every combination - how many to
   keep, from which seed, and whether to draw more and keep the most different. Each design is a
   random set of the chosen variants - as many designs with one of them as with two, three or all -
   each variant at a point of what it allows. A campaign never narrows a variant: to hold a lever
   fixed, change the variant.
7. **Repaired, not discarded.** A design whose pieces break a rule between them - ribs too close,
   a narrow wedge of sand, a hole on a rib, an X crossing a variant forbids - is repaired by CP-SAT,
   which leaves out the fewest ribs, pads or holes so every rule holds, and the design says what was
   left out. A design repair cannot save is drawn again.
8. **Clearance is measured from real metal**: a rib's footprint is half its thickness at the root
   and its root fillet, not its centre line - for holes, for faces kept clear of, and between ribs.
9. **Every design can be made again**: a campaign keeps its card, the part's digest, the code it
   ran, the copy of its variants and its seed; each design its recipe, a hash of it, its own seed,
   what was left out and how it screened.
10. **Cheapest first.** Placing and screening a design takes a fraction of a second, building its
    field minutes, meshing and solving more. A campaign places and screens every design; a field is
    built when someone asks for it.
11. **Designs are measured for spread**: how many were tried, kept and dropped and why, how each
    lever spread, how many distinct rib layouts, how far each design sits from its nearest
    neighbour.
12. **No code is written for one part or one request.** What a variant cannot express is added as a
    general piece - a rule kind, a pattern, a kind of change - and every old campaign must build its
    designs again exactly afterwards.

## The pipeline

```
STEP + drawing
      │  read once: faces, features, interfaces, the part's field
      ▼
variants (CAD tab) ─── each: where + levers + rules; samples shown only when they pass
      │
      ▼
campaign card ─── variants chosen · checks held · method, n, seed · count · screen 100
      │
      ▼
each variant alone ─── its pool of points that place and pass on their own (repaired)
      │
      ▼
designs ─── a random set of variants, a point of each ─► placed ─► CP-SAT repair ─► screened
      │                                                   (a design repair cannot save: drawn again)
      ▼
archive: card, part digest, code, variants copy, seed · each design's recipe, hash, what was left
      │   out, how it screened, its paths
      ▼
Designs: P for every design ─► F built on demand ─► M, S, R (to come)
```

## Where each rule is enforced

| stage | rules |
|---|---|
| **placing** a variant's ribs and holes | on what they stand on · clear of the faces and variants named, from the rib's footprint · clear of every hole, bore and controlled feature of the part in three dimensions, ends buried in what they meet included · so many thicknesses tall and no taller than what each end meets, named features or a height · ends on what they run between · pads where a wall is too thin · a rib too thick for its floor left out · stubs left out |
| **repair** (CP-SAT) | root gap between footprints, within a variant and between variants · no narrow wedge of sand where two ribs meet · a ligament of metal between holes and ribs · no X crossings, where a variant says so |
| **screening** | every variant in the design made something · a rib no thicker than its floor allows · the root gap · holes clear of ribs · no wall thinned below its least |
| **built** (field checks, each timed) | protected cells unchanged · inside the grid · nothing floating · rib thickness · root gap · root fillet achieved, read off the field · rib ends · blend bridging and clipping · thick spots · rib against wall · holes through · the surface closed, where one is drawn |
| **physics** (to come) | bearing-seat tilt · stiffness · stress · mass · natural frequencies |

Mould release is not checked while the pull direction is out of the variants; it comes back with
the pull and with cores that form the pockets inside a casting.

## Steps

Each step names what is built and what shows it done. Every step keeps the tests passing.

**1. The variant library**
- `src/fastcae/variants.py`: a variant is a study of one block - the same schema, checked by the
  same function - with a label, kept in `<project>/variants/<id>.json`. Its id is five characters,
  a letter then letters and digits, random and unique in the project; its block's id is the same,
  so another variant's ribs are `ribs:<id>`. Listing gives each variant's code, name, kind, where,
  how many combinations it allows, which campaigns used it and whether it changed since. Delete
  moves the file to `variants/.deleted/`.
- `study.py`: reading and writing take the folder - `studies` or `variants` - and writing a variant
  does not make it the project's study. A rule may name the ribs or holes of any variant in the
  library.
- The session's draft holds one block: the variant being authored, new or opened. Adding a second
  block is refused.
- Routes: `GET /api/variants`, `GET /api/variants/{id}`, `POST /api/variants/new`,
  `POST /api/variants/{id}/open`, `GET /api/variant/draft`, `POST /api/variant/hand`,
  `POST /api/variant/sample`, `POST /api/variant/save` (creates a new one, or saves the changes to
  one kept), `POST /api/variant/discard`, `POST /api/variants/{id}/duplicate`,
  `DELETE /api/variants/{id}`.
- *Done when* tests on the ring part create, list, open, edit, save, duplicate and delete variants;
  a variant naming another's ribs is written and read back; nothing touches `project.json`'s study.

**2. What a variant may vary**
- Every range the part suggests steps by 5 in its unit, its ends rounded inward to multiples of 5 -
  kept as they are when that would leave nothing. Height is a percentage, stepping by 5.
- The **free** pattern: `Layout.kind` `lines`, each line an angle and a place across the host,
  drawn from the design's `layout` lever - a seed, never shown - the count and the angle range from
  the variant's levers; `_paths` lays each across the host like any other.
- Only levers that change the design are sampled and counted: spacing for straight patterns that
  have one, count for spokes, free lines and straight patterns without spacing, centre and spread
  for spokes only.
- `combinations(block)`: the exact number of distinct points a variant allows - summed over its
  patterns, the product of each pattern's levers' values; "unlimited" with the free pattern.
- Rules: the kinds a variant may hold (above) - `root_gap` a new kind, suggested from the rule of
  thumb, and `no_x_junctions` enforced by repair. Kinds nothing reads (along, square to, draft at
  least, thickness to wall, wall at least) are marked not enforced and not offered. Hand actions
  `rule` and `drop` add and take them out.
- No pull, preferences, objectives or target in a variant.
- *Done when* tests show the ring's ribs ranged in fives, free lines the same for the same seed,
  counts exact on blocks built by hand, and only checked kinds offered.

**3. Footprints, wedges, crossings and repair**
- `Rib` carries its root fillet. A rib's footprint half-width is half its thickness plus its root
  fillet, or half its flange where that is wider.
- Placing: keep-outs, other variants' ribs and holes, spokes crowding each other and ribs crowding
  another variant's all measured from footprints.
- `_gaps` - screening and the built check alike - measures between footprints; two ribs whose
  footprints overlap meet in a junction. Where two ribs meet or cross at an acute angle, the sand
  between them is a finger from the rounded corner to where it is as wide as the root gap; longer
  than the root gap, the pair is a **wedge** conflict.
- A junction's arms are counted - a rib passing through gives two, one ending there one; more than
  three arms is an X crossing, which `no_x_junctions` forbids for the ribs of its variant.
- `src/fastcae/generate/repair.py`: the conflicts of a placed design - rib-rib gap, wedge,
  hole-rib ligament, X crossings - as a CP-SAT model that leaves out the fewest pieces (a rib takes
  its pads with it), the same answer for the same design; the lines of what was left out drawn as
  "left out"; screened again after.
- The built checks leave out mould release while there is no pull.
- *Done when* tests show: two ribs closer than the root gap lose one; a hole on a rib's fillet is
  left out rather than the rib; a square grid of a variant that forbids X crossings loses ribs until
  none cross; a shallow wedge is found; a hole 3 mm from a rib's side with an 8 mm root fillet is a
  conflict; the built checks name no mould release.

**4. A variant's samples**
- Show paths: the variant alone at its suggested point - or, for Another sample, at a random point
  of what it allows, every choice and every step as likely as the next - placed, repaired,
  screened; up to 48 points tried until one passes. The lines, what was left out, the counts, and
  how it was drawn and on which try it passed; or why none passes, the commonest reasons first.
- Create and Save refuse a variant none of whose samples pass.
- *Done when* the ring's variant shows passing paths, Another sample shows a different one, and a
  variant that cannot be placed is refused with its reason.

**5. Campaigns**
- `src/fastcae/generate/campaigns.py`: the card - `name`, `variants`, `checks_off`, `method`
  (`even`, `random`, `every`), `n`, `seed`, `diverse` (off, or draw `k` times `n` and keep the `n`
  most different).
- Composing: one study version from the chosen variants - their blocks as they are, each variant's
  rules on its own block, the part's interfaces once, and the rules between variants that hold
  automatically: holes keep their ligament from every variant's ribs, ribs of two variants the root
  gap. A rule naming a variant not in the campaign is left out.
- Counting: `Π(1 + c_i) − 1` over the variants' combinations - every non-empty set of them at every
  point of each. "Every combination" is offered when that is no more than `n`.
- Screen 100: a hundred designs drawn as the campaign would, placed, repaired and screened, nothing
  kept - how many pass, why the rest do not, and the time a design takes, so the launch's time is
  known.
- Go: each variant alone first - a pool of its points that place and pass on their own, repaired -
  then designs: a set of variants with its size spread evenly from one to all, a pool point of
  each by the method, placed, repaired, screened; a design repair cannot save drawn again; designs
  alike kept once; `n` kept of at most `4n + 100` tried. With `diverse`, `k·n` are kept and the `n`
  farthest apart chosen.
- `_pieces` builds only the variants a design holds.
- The archive, a folder per launch - `_archived_designs/<project>/<id>-<name>/`: `campaign.json`
  (the card, the part's digest, the code's commit, the variants' copy with their inside versions,
  the seed and method), `study.json` (the composed version), `designs.jsonl` (each design's
  variants, values, recipe hash, seed, what was left out, how it screened), `paths.jsonl`,
  `summary.json` (tried, kept, repaired, dropped by reason, how each lever spread, distinct rib
  layouts, nearest-neighbour distance), `built/`.
- Routes: `GET /api/campaign` (the pipeline: stages with their inputs and outputs, screening and
  field checks, placing rules, materials), `POST /api/campaign/estimate`,
  `POST /api/campaign/screen`, `POST /api/campaign/go` (a stream of events), `GET /api/campaigns`.
- *Done when* tests on the ring: two and three variants composed; counts exact; set sizes spread
  evenly over 300 designs; every combination enumerates each exactly once; `n` kept with repairs;
  the same card and seed give the same designs and hashes; the summary holds its metrics.

**6. Designs by variant**
- A design's rows and its readout say what it is made of by variant - code, name, what it made -
  with the values it took and the variants it left out; plans are coloured by variant with a key;
  a list can be filtered to designs holding one variant. Runs are listed as campaigns: name, how
  many, method, when.
- *Done when* route tests show names, left-out variants and the filter.

**7. The interface**
- CAD - **Design a variant**, a pane on the right: a sub-tab for each variant and one for a new
  one. A new variant starts from the faces selected and what to add. The card: where - stand on,
  end on, keep clear of, chips from the selection; what varies - each lever fixed, a range with its
  step, or options, patterns among them; its rules, offered kinds only; how many combinations it
  allows; **Show paths** and **Another sample**, with what was left out. At the bottom: its name
  and **Create variant** - or, for one already made, **Save changes** and **Discard** - with
  Duplicate and Delete, and the campaigns that used it. The agent bar is hidden.
- Generate - **Campaign**, in three steps: **Compose** (name; variants, each with its variations and
  count), **Check** (at a glance, a few words an item and its rule on hover: what each variant
  varies and the rules it holds, what holds always, screening checks to switch, field checks
  folded), **Sample & launch** (method, n,
  seed, keep the most different, the count, Screen 100, the time it will take, Launch); a later step
  greyed until the one before holds something. Campaigns launched below, with their progress, each
  opening in Designs.
- Generate - **Designs**: as today, with the variant readout, left-out variants and the filter;
  "left out" lines in the paths key.
- *Done when* the interface type-checks and a walk in a headless browser, on a scratch copy of the
  housing, authors three variants, composes them, estimates, screens a hundred, launches twenty,
  and shows every design's paths and one design's field.

**8. A clean start, and the docs**
- Retired to `_archived_designs/_retired/2026-09-13/`, where nothing lists them: the housing's
  `studies/` and `specs/`, the agent's conversation in `.fastcae/agent/`, and every run under
  `_archived_designs/GRC_Gearbox_Housing/`; `project.json` forgets its study and spec. Kept: the
  part, its drawings, the caches and the knowledge.
- README, architecture, generate, ribs and status rewritten to what is true then.
- The whole test suite run once; committed when the engineer says so.

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
4. **Meshing**: CGAL Mesh_3 straight from the design's field, through a compiled module built in
   WSL (`bench/solvers/cgal_field.cpp`) - CGAL reads the field as a grid and interpolates it itself,
   so none of its millions of questions leaves C++ - with surface points within 0.005 mm of the
   field. Element sizes come from a map computed on the field: at least 2 elements through the ribs a
   design adds, fine only where the design changes the part, up to 40 mm on the housing's own panels,
   sizes growing 1 mm per mm away. The edges of the faces loads and supports go on - the seats' edge
   circles - are given to the mesher as lines with vertices 8 mm apart, so those faces come out
   exactly: at the element size the lines cut off a shoulder under a seat, at 3 mm they made the
   seats too dense for Code_Aster's couplings. The bolt holes' circles are not given - they doubled
   the mesh and the holes already come out right. A mesh report per design checks the sizes. Measured
   on design #7: 1.49 M unknowns, meshed in about 10 s and solved in about 10 s on the 8 GB card;
   against the coarser mesh it moves the worst tilt 2.8%, the largest displacement 6.4% and p99.9 4.7%
   - the coarser mesh was too stiff. The same rules over every rib, fillet and hole of the housing
   would take about 44 M unknowns; fillets and holes held finer only where the design changes, 2.4 M,
   past the card. The fallback: the field's surface evened out, repaired and filled by gmsh.
5. **The gate: the field route against real CAD** - run. The production housing with its ribs and
   fillets (`assets/_archive/254492_0_closed_volume.step`), in a scratch project, never a project's
   part or a source for designs, meshed four ways: the CAD's own surface by the same compiled mesher
   (the judge); its 3 mm field (fastcae's route); the field again from another random start (the
   noise of meshing itself); and agenticCAE's route as it ran its 490 designs - gmsh on the CAD's
   faces, weld, collapse, MeshFix, gmsh tets. All four held to the element sizes of agenticCAE's own
   mesh of the part (1.1-1.2 M unknowns), the same seat edge lines and labels, solved by Code_Aster
   with agenticCAE's couplings. **The field matches the CAD within the noise of meshing itself**:
   the leads, p99.9 and the displacement map meet their marks; the worst seat's tilt (7%), the stress
   map (17%) and the peaks miss theirs by the same amounts meshing the same field twice moves them -
   marks tighter than a mesh of this size holds, whichever route made it. A 3 mm field is enough.
   agenticCAE's route leaves out six faces, lids their holes flat and cuts into metal under a seat -
   20-53% off on two seats. Snapping the field mesh's boundary onto the CAD changed nothing that
   matters and distorted elements. Measured in
   [research/field-meshing-gate.md](research/field-meshing-gate.md).
6. **A design in a run**: built with the grid's distance on the GPU; floors never thickened; faces
   moved with their nearest-face queries on the GPU; its surface drawn only when someone opens it;
   labelled from the part's own CAD faces - a triangle a seat's or bolt hole's when its middle is
   nearest that face and every corner lies within 2 mm of it; weighed from its mesh; the rib-root
   fillet measured on the field, and "the surface closed" replaced by "the mesh valid"; every check
   timed, the slow ones made fast. About a minute a design.
7. **Runs**: a runner outside the development server keeps 2-3 designs in progress like a conveyor -
   the GPU builds and solves, the cores mesh, one solve at a time. A failed design is tried once more
   on the fallback, then set aside with its reason, and the run goes on. The run's design list shows
   each design's stage and time, designs an hour and how many were set aside; the Agent tab's log
   the same events. A run uses the whole workstation unless a setting leaves room. The effect is
   shown on 20 designs run one, two and three at a time, as a timeline.
8. **The 40-design check**, before round 1: 40 designs as varied as the variants allow; at most 1 in
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

1. The compiled mesher, with the size rules, the edge lines and the mesh report - built, in the
   bench.
2. The gate against real CAD - run; the field matches the CAD within the noise of meshing.
3. The route in the product: each design built, meshed, solved and recorded by the runner, its
   conveyor, and the run's design list.
4. Designs made for runs: the fixes below, faces moved on the GPU, the surface drawn when opened,
   labels from CAD faces, mass from the mesh, every check timed and the slow ones made fast.
5. Runs one, two and three at a time, as a timeline.
6. The 40-design check.
7. Round 1.

### Fixes to the designs, before the 40-design check

1. **Rib height.** An end is as tall as what it actually meets, never the metal found behind it (a
   web reached 422 mm through a 494 mm column behind a 45 mm boss). Webs are no taller than where both
   sides overlap, their top level by default. Spokes turn only about round things with an axis - a
   ring's faces map to the ring's axis. Height becomes a setting in thicknesses, 2-5× by default,
   never taller than what the end meets.
2. **No floor thickening.** Floors are never thickened for ribs; a rib too thick for its floor is left
   out, saying why.
3. **Holes see-through.** The Field view hides the CAD faces a design cuts and draws the design's own
   surface there; the verdict adds a check that holes go through.
### Open

- **Counting the gate passed** - the field is within the noise of meshing the CAD, but three of the
  marks agreed are tighter than any mesh of this size holds; recommended: passed, the marks for tilt,
  stress map and peaks read against that noise.
- **A design too big for the card** - past what cuDSS holds with its factor partly in host memory;
  recommended: Code_Aster in WSL, about 2-3 minutes a design, rare.
- **Optimisation** - repair weighted by each piece's worth; pymoo on the surrogate with CP-SAT as its
  repair, then BoTorch/Ax with real solves (see [research/optimization.md](research/optimization.md)).
- **Rib thickness from the floor** - with no floor thickening, 20 mm ribs on a 15 mm floor are left
  out; starting ribs at 0.6-0.8 of the floor they stand on would keep them.

## Later

- **The engineer's review loop**: about twenty representatives a round - medoids, the most novel,
  the nearest a hard rule, the least certain - pointing at a rib, readings of an objection with
  the number of designs each would remove, confirmed rules, the agent writing variants and
  campaigns from words again.
- **Quality-diversity search**: an archive over a few measures of the design, emitters aimed at
  its empty cells; staggered crossings as a pattern; free layouts grown from a graph of legal
  connections between regions.
- **Mould release** with the pull and with cores; then draft and undercut maps.
- **Wall fields**: thickness varied smoothly over a region, fading to nothing at what is held.
- **Gated solves**: the same design solved twice agrees within 0.1%; MAP-Elites; a design the
  surrogate recommends solved for real before it is called good.
- **The part's regions and what they are for**, computed from the geometry and the drawing,
  approved by the engineer; the names the card, the agent and the results share.
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
