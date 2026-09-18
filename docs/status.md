# Status

**This file describes what is true now.** Superseded content is deleted, not annotated.

---

## Where it stands

**Extract** and **Model** run end to end on any part. Opening a project runs **one pipeline**: the
Read stage - the extraction steps over the CAD, the drawing and the solver deck - and the
**design-space** stage, which derives from them where metal may be added, what must stay clear and
why, and what waits on the engineer's answer ([design-space.md](design-space.md)). Every step's
inputs and outputs are typed entities; Input shows the pipeline on the left, the entity in focus on
its canvas and on a card on the right, and the agent reads the same entities
([pipeline.md](pipeline.md)).

**Generate** runs campaigns over the variants the project keeps - read, no longer authored in the
interface: composed, counted, screened, launched; the runner builds, meshes, sets up, solves and
records their designs two or three at a time; every design is followed through its stages on
Designs. **Simulate** reads the engineer's deck and shows its setup and answer; cuDSS reproduces the
answer on the runner, set aside in the interface for now ([simulate.md](simulate.md)). Learn and
Optimize are visible and not built.

The next phase ([build-plan.md](build-plan.md)): patterns found in the derived design space and
regularised into families, every design made as its own CAD - rib solids fused into the baseline's
STEP - meshed face by face as the baseline's deck mesh is, and solved by cuDSS.

What runs:

- **Four tabs** - Input (Drawing, CAD with *Part* and *Design space*, Mesh & setup with *Setup* and
  *Answer*), Generate (Campaign, Designs), Learn, Optimize. On Input the rail is the pipeline and the
  right pane the card of what is in focus; on Generate the rail lists campaigns or designs.
- **The pipeline**, two stages in one rail: each step with its status - to run, running, done, read
  back, skipped, failed - its time and a line on what it found; opened, what it read, as chips that go
  to the step that made them, and what it made, as groups that open to their entities. A run streams
  each step as it starts and finishes; the design space is read back in about a second while nothing
  it depends on changes, and derived again - about 80 s on the housing - when something does.
- **Typed entities** of 29 kinds, from faces, features, callouts, deck groups, supports, couplings and
  loads to interfaces, keep-outs, the inside, bands, regions, questions and mirror planes: each with
  its origin - imported, derived, inferred, confirmed, generated - its evidence and where that was
  found, and its links read both ways.
- **Focus**: a step, a group, an entity, a link on the card, a face clicked on the part or what the
  agent shows is brought into focus on its canvas - the callout on the drawing, the faces on the part
  (looked at when picked from the rail), the layers of the design space, the deck group on the
  deck's mesh.
- **The design space on the CAD**: every layer a step made - the part in cells; allowed and waiting;
  what sits in a bore, beyond the bores, what mates on a plane, what fits over a boss, fastener and
  tool, the buffer, what waits round faces in doubt; the inside and what lies behind narrow
  openings; the candidate layer and pockets; where metal helps as a heat scale - each switched on
  and off in its key; the part painted by wall thickness, height straight out, interface or sealing
  walls. While a run derives, each step's volumes appear as it finishes.
- **Questions and answers**: every interface in doubt, the inside, the inner walls, the grid - each
  with its options and what holds meanwhile. An answer is kept in `project.json`, applied when the
  space is derived again, and taken back at a click; a face answered *free* stays in view, released.
- **The agent**, above every tab: what the engineer says goes to it with what is in focus; it reads
  the pipeline and its entities and the part, shows what it talks about, records an answer only when
  the engineer's words give it, and derives the space again to apply it - the rail following the run.
- **The solver deck, read.** A Code_Aster deck in the project folder - `.export`, `.comm`, MED mesh,
  and the run's results, tables and log - is read on Extract: the mesh with its groups, the setup,
  the answer; its groups tied to the CAD faces they lie on. *Setup* draws the mesh with the supports,
  couplings and loads as agenticCAE drew them, named on hover; *Answer* shows the answer as contours
  with the deck's signals. Everything says whether it was imported, derived or generated.
- **Reproduce**, on the runner and the deck's routes: the deck's mesh and setup solved again by cuDSS -
  on the housing's baseline deck, to about 10⁻¹¹ of Code_Aster in 23 s against its 2 min 35 s - with
  a certificate holding each quantity to its own tolerance. Not in the interface for now.
- **A campaign's designs solved** (Campaign, a launched campaign chosen): the runner takes the designs
  that differ most through build, mesh, setup, solve and record; the page shows how many are solved
  and set aside, how many an hour, each design's stages and times, and what happened. A design
  solved leaves a Zarr store, a JSON record and a row of the run's Parquet table; the Designs view's
  M, S and R fill from them.
- **Campaign**, a card in three steps:
  - **Compose**: its name, and the variants it takes from those the project keeps, each with how
    many designs it allows.
  - **Check**, at a glance - a few words an item, its rule on hover: what each variant varies and
    the rules it holds, as pills; what holds always - holes keep their ligament from every
    variant's ribs, ribs of two variants keep the root gap, the part's interfaces stay clear,
    clashes are repaired by CP-SAT; the screening checks, each switched off for this campaign at a
    click; the checks a design's field is held to, folded.
  - **Sample & launch**: spread evenly (the default), random - every choice and every step as likely
    as the next - or every combination when the variants allow no more than the designs asked for;
    how many designs and from which seed; keep
    the most different of two to five times as many; how many designs the variants allow; **Screen
    100** - a hundred drawn, placed, repaired and screened, nothing kept, how many pass and how long
    the launch will take; **Launch**. Its progress - each variant pooled alone, designs kept, tried,
    repaired and why the rest were not kept - and the campaign opened on Designs when done.
- **How a campaign draws designs**: each variant alone first - points of what it allows placed,
  repaired and screened, those that pass its pool; then each design a set of the variants, as many
  designs with one as with two or all, and a pool point of each by the method; placed together,
  repaired, screened, drawn again when repair cannot save it; alike designs kept once; `n` kept of
  at most `4n + 100` tried. Every launch is a campaign of its own.
- **Repair**: a design whose pieces break a rule between them - ribs with no room for the sand
  between their footprints, a wedge where two meet at a shallow angle (a thin finger of sand, or a
  lump where their fillets run them into one), a hole on a rib, an X crossing a variant forbids -
  is mended by CP-SAT, which leaves out the fewest ribs, pads or
  holes, holes before ribs where it is a tie, the same way every time. The design says what was
  left out and why. A design built is mended the same way, so the field is the design screened.
- **Clearance from real metal**: a rib's footprint is half its thickness at the root and its root
  fillet; everything kept clear of a rib - holes, faces kept clear of, other ribs, other variants'
  ribs - is measured from it. Two ribs meet where their bodies cross in the open; spokes meeting
  inside the boss they turn about are held apart where they stand in the open.
- **Screening** on what placing a design knows: every variant in it made something; a rib no
  thicker than its floor allows, as the design leaves the floor; the root gap and wedges; holes a
  ligament clear of ribs; no wall thinned below its least. Each design weighed in the part's
  material.
- **The archive**: a folder per launch in `_archived_designs/<project>/<id>-<name>/` beside
  `assets/` - the card, the part's digest, the code's commit, a copy of every variant as it was, the
  seed and method; every design with the variants it holds, its values, its recipe and the recipe's
  hash, its own seed, what repair left out, how it screened and its paths; a summary of what was
  tried, kept and dropped and why, how each lever spread, how many distinct rib layouts, how far
  designs sit from their nearest neighbour; and each design built so far.
- **Designs**: a campaign's designs, each with its stages as letters - P its paths
  placed and screened, F its field built and checked, M meshed, S the solver set up, R results -
  coloured by how each came out, and dots for the variants it holds; the 20, 30 or 50 that differ
  most, those built, or all of them 200 at a time; only those holding one variant, when asked. A
  design reads by variant - code, name, what it made and the values it took - with the variants it
  leaves out, what repair left out, and its recipe and seed. Its paths are drawn at once; its field,
  once built, is the surfaces it changes over the part - run down to where they meet it, taking the
  part's colour there, and the faces it cuts hidden and drawn as its own surface, so a hole looks
  like a hole - and its new metal as cells; its verdict says how long each check and each step
  took. The designs that differ most are side by side as plans.
- **Building a design**: its field at preview or full, from the copy of the variants its campaign
  kept - faces moved, each rib and pad filleted with its own root fillet, holes cut, mended, one
  recontour - checked, and kept beside the campaign. Each window's exact distance to the part, and
  the faces moved's nearest-face distances, on the GPU with NVIDIA Warp - the part's triangles split
  to 16 mm first - or on the CPU without it, within 0.004 mm of each other. Every check and every
  step timed; the root fillet read off the field; holes checked open through their plate. Mould
  release is not among the checks while variants hold no pull direction.
- **Building without a surface**, for datasets: `build_design(folder, index)` builds any design of
  a launched campaign from its folder alone - no server, no session - the same field Build field
  builds, with no recontour and no check that reads a surface, weighed from its field; it returns
  the field, the verdict with each check's outcome and time, and the step times. A `Workshop` keeps
  the part open between the designs one process builds.
- **Kinds of change**, each read off the part round what the engineer gave:
  - **ribs** on a floor - faces in one plane - and **webs** with nothing under them, between what
    they join; spans between supports, each end buried in what it meets and no taller than what it
    meets - never the metal behind it - a web no taller than the lower of what it joins, the top
    sloping or level; held to the wall they meet - no thicker than 0.8 of it - with a pad round a
    rib's end where a wall is too thin, never past twice the wall. A floor is never thickened: a
    rib too thick for the floor under it is left out, and the design says so with the rule.
  - **faces thickened** - a wall, a plate, a boss - along their normal, blended into what is round
    them; built exactly in a window round them, 262 faces in seconds; a variant that would move a
    bore is refused.
  - **holes**: a square or staggered lattice through a plate, each hole a ligament of metal from the
    next, the plate's edges, the holes it has and the ribs of every variant; none over something
    standing under the plate.
- **Reading the part**: holes go round (a fillet in a corner is not a hole; a cast hole with draft
  is); what a feature stands on is found across the fillets and chamfers at its foot; what rises
  round a floor across fillets, rounds and chamfers; what lies across the open space from an entity
  by rays out of its metal; the plate and walls measured by rays through them; how tall a rib's end
  stands by the faces of what it meets, within its width; the smallest radius is the drawing's
  note, cited.

Not yet: tapers and gussets; bulges, boss transitions, existing ribs varied; staggered crossings; a
review loop turning objections into rules. The study functions and the zone and formation code from
before are still in the tree, unused by the interface.

## On the housing

**Walked in a browser** on the housing's own project, the servers running as they do for the engineer:
the pipeline streams both stages; the design space fills in step by step on the CAD; a step, a group,
an entity, a link on the card, a face clicked on the part each come into focus on their canvas - the
callout on the drawing, faces on the part looked at from where they can be seen, volumes and paints
in the design-space view, the deck group on its mesh; the Answer view shows the engineer's contours
and the deck's 78 signals; Designs shows a launched campaign's designs. Asked in words why the Ø541
bore is frozen, the agent read the pipeline and the entities and answered with the deck group and
the drawing's control that freeze it, and showed the bore and what is kept clear round it - 14-25 s.
No errors in the browser.

**The design space, derived** from the rib-free housing, its Code_Aster deck and its drawing at
4 mm (41.8 M cells), in 79 s the first time: 62 interfaces frozen - 6 loaded by the deck, 25 held,
29 planes held bolts clamp, 2 toleranced on the drawing - and 34 asked about; 250 L kept clear and
525 L waiting near the part; the inside closed, 523 L; 18 of 20 bores carrying on past an end; 47
sealing faces; 110 L allowed and 60 L waiting outside; a median 35 mm of height straight out from
the free wall; 37 questions. No mirror plane matches more than 24 % of the surface.

**Against the production housing's ribs**: all nine (6.6 L) are inner webs joining the main seat's
ring to the barrel and the rear wall, so outside-only covers none. With the inner walls allowed,
three wall thicknesses deep, 60 % of their volume lies in allowed space and 75 % in allowed or
waiting space; five deep, 78 % and 99 % at 457 L. Where metal helps, from one solve of the part on
the grid, puts the production ribs 2.5 times more often than chance in its top quarter.

**The flow of the variant library**, walked in a browser before authoring left the interface, on a
scratch copy of the housing:

| step | what | came to |
|---|---|---|
| variant | ribs on `planar_group:114` (`face:1201`), square grid only, 15 to 25 mm | 8 ribs and 8 pads at its suggested point; 19,293,120 designs |
| variant | `boss:1612` moved, −5 to 10 mm | 12 designs |
| variant | holes through `planar_group:115` (`face:1543`) | 4 holes at its suggested point; 214,200 designs |
| campaign | the three, spread evenly, 20 designs | 5.4 × 10¹⁵ designs allowed; Screen 100: 100 pass, 8 after repair |
| launch | alone: the ribs 32 of 90 points pass, the boss 12 of 12, the holes 32 of 36 | 20 kept of 20 tried, 3 repaired, 2 s |
| design | #1, the grid ribs, the boss 5 mm thicker and three Ø35 holes, built at preview | warn - blend bridging and clipping - 15 checks pass; 91 s |

## Open

- **The whole gearbox in context.** What turns inside - gears, carrier, shafts - is in neither the
  housing's CAD nor its deck, so the inside is kept clear only of each bore's bearing and a shaft
  through it. Designing the inside needs the assembly; the GRC's is in `cae-data` as SolidWorks files,
  to be exported to STEP.
- **Memory.** The derivation peaks at about 7 GB; with a browser and editors open on 16 GB it paged
  out and took 8.5 minutes, where it takes 79 s with memory free. The first run on a project also
  builds the part's grid, 2-4 minutes.
- **The inside counted twice.** The inside's question counts the free air enclosed (421 L), the
  inside itself that air with the lids that close it (523 L).
- **Kept-clear volumes are whole-part totals**, one a kind: what sits in a bore is every bore
  together, so nothing can say what is kept clear round one bore.
- **Inner walls.** Every production rib is an inner web; outside only, the default, covers none. Whether
  inner walls are allowed by default, and how deep - three wall thicknesses or five, or webs from wall
  to wall - waits on the engineer.
- **34 questions about faces** on the housing, one a face; grouping them - a flange's faces together,
  a pattern's planes together - waits on the engineer.
- **cuDSS on the face-by-face baseline mesh**: the baseline's deck mesh is now made face by face, the
  recipe designs will use; cuDSS's agreement with Code_Aster is to be shown again on it before
  designs are solved.
- **Placing memo and the grid**: a campaign that placed its designs on one grid and builds them on
  another can build a different field for the same design - placement's memo is not keyed on the
  grid. The tests hold the root fillet fixed so every design shares one grid; the product is not
  fixed yet.
- **Mould release waits for the pull.** Variants hold no pull direction, and a check that rejected
  any metal along the pull from a rib tip - however far, and not knowing that cores form the pockets
  inside a casting - rejected every design built on the housing. It comes back with the pull and
  with cores.
- **Ribs stand only on flat faces.** A curved wall - the housing's outer skirt, a round boss -
  takes webs between, not ribs on, until ribs can follow a curved face.
- **A rib that would reach a hole is left out, not ended short.** Its end, buried in what it
  meets, is not yet buried less deep to stay clear: round the bearing boss's bolt holes some
  pieces go for that.
- **The part's suggested ranges are wide.** Holes through a 30 mm plate are suggested 30 to 115 mm
  across, 30 to 90 mm from its edge; ribs 5 to 16 thicknesses apart. Most points of such a variant
  pass nothing, and the engineer narrows them.
- **A campaign runs on one core.** Placing and screening a design is milliseconds - tens of
  milliseconds with repair on many pieces - and building a design's field minutes, so campaigns are
  placed and screened, and designs built one at a time on Designs.
- **Mass is an estimate** for screening - ribs as plates, fillets and draft aside - beside the base
  part's exact volume; a built design is weighed exactly.
- **Holes cut most paths.** On the ceiling, nearly half the pieces a grid is cut into stop at a
  hole's keep-out, and a piece that ends there is not a rib: round holes a grid comes apart instead
  of closing on its own crossings.
- **Only named supports count at both ends.** Name two faces and spokes that reach any other wall
  are dropped, reported as ending on something not named, with what.
- **Bosses and bores are not yet required to go round.** Holes are; convex cylinders are still all
  bosses, and 216 on the housing are mostly rounded wall corners and edge rounds.
- **agenticCAE's meshing route changes the housing's geometry**: on the production housing gmsh leaves
  out six CAD faces, MeshFix lids their holes flat (up to 242 mm across) and the repair cuts up to
  24 mm into metal under a bearing seat - 20-53 % off on two seats' tilts. Its 490 designs were meshed
  this way.
- **At about 1.2 M unknowns the mesh is the largest noise**: the same field meshed twice differs by up
  to 7 % on the smallest seat's tilt, 18 % on element stresses, 30 % on single peaks.
- **The design's surface crosses itself** where two sheets pass closer than the grid: dual contouring
  left 2,333 crossing faces on design #7, nearly all on one 556 mm column. A mesher from the surface
  cannot fill it without a repair; meshing from the field never makes the surface.
- **The housing's floors are too thin for the starting ribs.** A floor is never thickened, and 20 mm
  ribs - where a new variant starts - need 25 mm of floor under them: on the housing's ceilings and
  floors they are left out. Design #7 of `w4zf5`, built today, keeps its webs - each no taller than
  what its ends meet, 10 to 97 mm - and none of its ribs on a floor, so its build is rejected for
  those variants. Starting ribs at 0.6-0.8 of the floor they stand on would keep them
  ([build-plan.md](build-plan.md), Open).
- **Builds in the interface block and die with the development server.** A field build runs inside
  the request; a reload of the development server kills it and nothing is saved. A separate process
  can build any design of a launched campaign from its folder (`build_design`); the runner that keeps
  designs in progress that way is not built.

Tests are kept locally as working checks and are not tracked.

One project in `assets/`: **GRC Gearbox Housing** - the rib-free housing (`housing_baseline.brep`),
its 4-page drawing, its Code_Aster deck and answer, and `project.json`.

## What the pipeline produces today

```
GRC Gearbox Housing  (7.4 s)
  ok  Discover artifacts                 1 CAD, 1 Drawing
  ok  Read CAD                           1 solid, 1753 faces, 121,374 cm3
  ok  Check geometry health              watertight, 133,102 triangles
  ok  Measure every face                 1753 faces, 732 reachable from outside
  ok  Detect features                    254 planar_group, 241 fillet, 216 boss, 206 hole,
                                         20 bore, 5 hole_pattern
  ok  Read drawing                       4 pages, 255 callouts, 8 toleranced
  ok  Cross-check drawing against CAD    4 of 30 callouts associated, 1 ambiguous,
                                         7 controlled faces, 1 unresolved
   warn cad.load the file also holds 29 loose edges outside any face; not read
   warn cad.load the file declares no length unit; it was read as mm
```

The loose edges are what deleting features in CAD left behind; the reader keeps the solid and says
so. Drawing: 255 callouts - 22 counted, 21 threads, 16 tolerance frames, 8 toleranced dimensions,
7 datums (A, B, D, EV, EW, EX, EY), units mm.

## What is verified

**Nothing by a person.**

No association this system has produced has been checked by a person. The matching rule was written
here, run on one drawing, and its output reported as working. There is no ground truth, no
validation set, and therefore no measured accuracy. The three associations currently asserted:

| feature | model | drawing | basis | confidence |
|---|---|---|---|---|
| `bore:196` | Ø541.00 | `'541.080 / 541.020'` | toleranced dimension, exact size | 0.70 |
| `bore:202` | Ø1166.00 | `'1166.11 / 1166.04'` | toleranced dimension, exact size | 0.70 |
| `hole_pattern:2` | Ø21.00 ×5 | `'5X 21.00 63.00'` | size and count both agree | 0.70 |

Each is capped at 0.70 because each rests on an inference the drawing does not state - that the
value is a diameter. The symbol that would say so survives extraction **zero times out of 255
callouts**, so the inference is cited as `derived` evidence.

Every Generate check has rejected a synthetic part built to fail it; repair has mended synthetic
designs built to break each rule between pieces, and left out the fewest pieces each time.

## Measured limits

### Extract

**The association rule has a low hit rate.** Of 15 hole callouts, 3 find any candidate and 1 also
agrees on count. The other 12 have no pattern within 4 mm - the drawing describes families at Ø14,
Ø10.20, Ø8.0 and Ø4.20 that detection does not produce. **The gap is detection, not matching**: from
1 µm to 0.5 mm of match tolerance the result is identical.

**One unresolved pairing**, where size agrees exactly and count does not:

```
hole_pattern:4   drawing 25 at Ø26   ·   model 23 at Ø26.00
```

**Every hole is found; patterns only on circles.** The housing has 206 holes - among them Ø14 ×38
and Ø10.2 ×22, families the drawing calls out and pattern detection misses. A hole goes more than
200° round its axis. The association rule does not use single holes yet, so the hole callouts still
find nothing. Patterns are fitted to circles only, and grouped by diameter and axis direction with
no reference to position.

**One ambiguity correctly refused.** `'50.34 / 50.22'` matches two bosses both at Ø50.00, so nothing
is asserted.

**Volumes read about 70 cm3 high** with OCC's default integration: 121,374 cm3 against 121,301 from
tight integration on the housing.

### Generate, on the housing

| | measured |
|---|---|
| field at 2.5 mm, once | 158 s |
| contour of the whole part, once | 20 s: 1.70 M vertices, 3.40 M triangles, closed, no faults |
| field at 3 mm, the preview grid for R6 ribs, once | about 2 minutes; kept on disk after |
| a variant read off the part | under a second |
| a variant's paths at its suggested point, once the part is open | about 1 s |
| Screen 100 of three variants | about 4 s |
| a campaign of 20 designs of three variants, pools included | 2 s |
| a campaign of 4,000 designs of ten blocks, together | about 60 ms a design once each block is known |
| design #7 of `w4zf5` built at preview by a worker from the campaign's folder - 9 ribs, 9 pads | 8 s with no surface the first time, 5.7 s of it placing's first read of the part; 1.8 s after; 20 s with its surface, 12 of them the recontour |
| its checks, each timed | 0.8 s in all: junction sections 0.56, nothing floating 0.19, root fillet read off the field 0.04, blend bridging 0.03 |
| 262 faces thickened | 11 s the first time, 4-5 s once what they read off the part is kept |
| the part's distance, cell by cell | on the GPU, 0.1-0.3 s a window of 200,000-370,000 cells within reach, where the CPU took 8-58 s; at most 0.0003 mm apart over 1.6 M cells; the part's triangles split to 16 mm, 5 s once |
| the preview grid | 425 × 463 × 258 = 50.8 M cells at 3 mm, 5.5 M near the surface; the full grid at 1.5 mm about 403 M |
| design #7 of `w4zf5` as built for the bench - 15 ribs, 11 pads, floors thickened | 1,962 s on the CPU; 79 s with the grid's distance on the GPU; 2.54 M surface triangles |
| that design meshed as TET10 | 4-8 s from the field by the compiled CGAL mesher at the old sizes (46 s through pygalmesh), 840-860 k unknowns; 9-14 s with 2 elements through its ribs, 1.49 M; 73 s from its cleaned surface by gmsh; fTetWild 26-103 min |
| its TET10 solve | 13 s by cuDSS at 1.06 M unknowns (5.2 GB of the card); 10 s at 1.49 M, part of the factor in host memory; 57 s Code_Aster, one core; cuDSS fails at 2.4 M |
| the production housing, for the gate | 2,167 faces; its 3 mm field 101 s; meshed from the field 7.9 s, from its CAD surface 12.6 s, by agenticCAE's route 17 s - 1.1-1.2 M unknowns each; Code_Aster 2-2.5 min and 4.2-4.5 GB each |
| the workstation | i7-13700HX (16 cores, 24 threads), 15.7 GB RAM, RTX 5060 Laptop 8 GB; WSL Ubuntu 24.04 with 12 GB |

## Next

**Now** - the next phase in [build-plan.md](build-plan.md), in its order: cuDSS shown again on the
face-by-face baseline mesh; one design's rib solids fused into the baseline's STEP, meshed face by
face and solved, as the test of the route; then patterns found in the design space - a height map on
the free wall, its ridges straightened and regularised by CP-SAT into families - and designs drawn
inside a family. Calls that wait on the engineer: the inner walls and how deep; grouping the face
questions; what a record keeps (about 28 MB a design with the volume).

Alongside, on Extract:

- **Associate single holes.** Holes are found now; the drawing's hole callouts can be matched to
  them, not only to circular patterns.
- **Confirmation instead of assertion.** No association should become a fact automatically, and no
  conflict should be raised on a pairing nobody has confirmed. Designed in
  [verification.md](verification.md).
- **Positional reading of the drawing** - text with coordinates, for leader lines and view
  membership, which is what a pairing actually needs.

## Decisions in force

| decision | choice |
|---|---|
| Project | a folder under `assets/`; its name is the folder's name. Folders starting `_` or `.` are set aside |
| What a project holds | the engineer's CAD - no ribs - drawings, solver deck and answer, and the variants kept for it. No reference part, ever |
| `project.json` | decisions only: the baseline, approvals, answers to the pipeline's questions. Proposed by the system, confirmed by a person; no facts |
| The pipeline | one pipeline, two stages - Read, then the design space - every step's inputs and outputs typed entities with an origin, evidence and links read both ways; the same entities for the rail, the canvases, the card and the agent |
| The design space | derived from the CAD, the deck and the drawing by rules that hold for any part: interfaces frozen on the deck's loads and supports, the drawing's tolerances, the planes held bolts clamp, or the engineer's word; asked about on shape alone; outside only by default; sealing walls take no through-holes; kept and read back while nothing it depends on changes |
| Answers | decisions, in `project.json`; applied when the space is derived again; a released interface stays in view |
| Who it is for | CAE teams (variants and decks for a study), surrogate-data teams, design engineers (ribs suggested and modelled), foundries (reinforcement that casts) |
| A variant | one change in one place - ribs on, webs between, faces thickened, holes in - with what it may vary and every rule it holds, in named entities bound by fingerprint; a short random code and a name that says what and where; kept in `variants/` and read by campaigns, no longer authored in the interface |
| What a variant may vary | every setting fixed, a range with a step, or choices; ranges the part suggests step by five, ends on fives, a height by five percent; patterns are choices, free lines among them; the count of distinct designs shown |
| What a variant must hold | every rule is the variant's own; only kinds the pipeline checks are offered; the part's interfaces held for every variant |
| A campaign | a card: name, variants, screening checks held, method (spread evenly, random, every combination), how many, seed, keep the most different of more. Each design a random set of the variants - sizes spread evenly - each at a pool point; never narrows a variant; every launch a campaign of its own |
| Repair | CP-SAT leaves out the fewest ribs, pads or holes so no rule between pieces breaks - root gap, wedges, holes clear of ribs, X crossings a variant forbids - holes before ribs on a tie, deterministic; a design built is mended the same way |
| Clearance | measured from a rib's footprint - half its thickness at the root and its root fillet - never its centre line |
| Mould release | not checked while variants hold no pull; back with the pull and with cores |
| Reproducing | a campaign keeps its card, the part's digest, the code's commit, a copy of its variants, its seed and method; each design its recipe, the recipe's hash and its own seed |
| What is unstated | explored within ranges read from the part and the drawing, and listed as assumed |
| A rib | a web between two or more anchors, a floor optional; section, plane and pull direction from the variant |
| The interface | four tabs in the order the work happens - Input, Generate, Learn, Optimize - every one shown built or not; on Input the pipeline as the rail, the canvases showing what is in focus, the card on the right; everything marked imported, derived, inferred, confirmed or generated; the agent's bar above every tab |
| Kinds of change | ribs and webs; faces moved along their normal - walls, plates, bosses; holes through a plate on a lattice. The part is cast in one material, which no variant changes. Built in one order - faces moved, then ribs and pads, then holes |
| Design knowledge | data with its sources, in `knowledge/materials.json`: rib to wall 0.8, root gap 2 thicknesses, a hole's ligament one plate thickness, a least wall 8 mm, six casting materials with density, stiffness, strength and least wall from their standards; where a new variant of ribs starts - 20 mm thick, 100 mm apart, 2 to 5 thicknesses tall, two to ten, three choices of each radius and draft |
| Pads | on unless the engineer says otherwise: a wall too thin for a rib is padded round its end, never past twice itself; off, the rib is left out |
| Floors | never thickened for their ribs: a rib too thick for the floor under it is left out, and the design says so with the rule it broke |
| Rib height | in thicknesses of the rib, 2 to 5 by default; each end never taller than what it meets - the face or feature it runs into, never the metal behind it; a web no taller than the lower of what it joins, its top level by default |
| The part's distance | exact, on the GPU with NVIDIA Warp when installed and a CUDA device is there - the part's triangles split to 16 mm first - the CPU's scan otherwise; the two within 0.004 mm |
| Building a design | from its campaign's folder by any process (`build_design`); no surface unless asked; every check and step timed; the root fillet read off the field |
| A design's stages | P paths, F field, M mesh, S setup, R results, each shown with how it came out; every design's paths kept with its campaign, drawn at once; a built field kept beside its campaign |
| Rib ends | a rib ends on what it meets, buried in it, or stops at least the root gap short of any metal ahead - never a finger of sand between |
| The model | tools over the pipeline's entities and the part: reads, shows, records an answer only from the engineer's quoted words, derives again - never geometry, never a design, never scripted to an example |
| Learning | within a project; within a client only if it opts in; never across clients |
| Simulation | agenticCAE's load case, material and supports - kinematic couplings at the bolts, distributed couplings at the bearing bores, loads at their centre nodes; every design its own CAD, meshed face by face as TET10 by the recipe the baseline's deck mesh is made with, the deck's setup carried by CAD face; solved by cuDSS on the GPU, Code_Aster re-solving a sample; a failed fuse set aside, never meshed another way; PETSc not used; results kept apart, never folded into one number |
| Training data | never from cells, shells or a field: only designs made as CAD and meshed from their faces |
| Agent stack | kept in `agent/`: LangChain agent loop on LangGraph, OpenRouter (DeepSeek by default), LangSmith; conversation and checkpoints in SQLite with the project; credentials from the environment |
| Constraints and checks | checks are code, tested against failing parts, thresholds from the variant, basis shown. A model may add rules, never checks |
| Fidelity | preview on a coarser grid with nothing else relaxed; accept only at full |
| Tessellation | OCC `BRepMesh`, chord tolerance derived from the model |
| `cadquery-ocp` | pinned at 7.9.3.1.1; 8.x ships an unsigned binary Smart App Control blocked. Smart App Control is off on the build machine; 8.x is untested |
| SciPy and OR-Tools | all of SciPy loads, `scipy.stats.qmc` included; OR-Tools CP-SAT repairs designs |
| Units | `xstep.cascade.unit` set explicitly to MM; the file's own declaration is read and reported |
| Scale-dependent tolerances | derived from the bounding diagonal, never absolute |
| A hole | goes more than 200° round its axis; a small concave cylinder that does not is a fillet |
| Control | derived from a toleranced drawing dimension matching a detected feature |
| Conflicts | recorded, never resolved, and not shown until an association is confirmed |
| Derived results | cached under `<project>/.fastcae/`, keyed on content and on the source that produced them; a miss is never an error |
| Design representation | a signed distance field on a fixed grid; a design is its variants and their values, never stored geometry |
| Contouring | manifold dual contouring; the baseline whole, once; a design re-contours only what it changed, spliced by key, and only when its surface is asked for. The grid's outermost layer is never solid |
| Design grid | a quarter of the root fillet unless asked for; voxel sizes offered are round numbers |
| Ports | API 8021, interface 5183 |
| Checks enforced | `ruff` and `tsc`. `mypy --strict` is configured and does not pass |
| Version control | source and docs; `assets/`, `tests/` and `_archived_designs/` are not tracked |
