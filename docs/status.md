# Status

**This file describes what is true now.** Superseded content is deleted, not annotated.

---

## Where it stands

**Extract** and **Model** run end to end on any part. **Generate** runs end to end in a first form
of the design in [ribs.md](ribs.md): the engineer selects faces, starts the rib card from them, sets
what it has wrong, sees where the ribs would go, and makes a design from it - the card is written as
a new version of the **study**, and the design is made from the study at its suggested point, with a
verdict in two parts and a list of what nothing checks yet. No language model is involved.
Simulate, Learn and Optimize are visible in the interface and not implemented.

The steps are in [build-plan.md](build-plan.md). Step 1, the study, runs - but for the model
writing it from words, which comes with the archive it needs, in step 4. Next is step 2: candidate
ribs and the conflicts between them.

What runs:

- **The rib card**, in the right pane, open by default. Started from the faces selected, it fills
  every slot from the selection, the part and the drawing, or with a labelled default, each marked
  you, selected, drawing, measured, default or needed.
  - **Faces** are chips: shown on the part by a click, taken out by their cross, added from the
    selection or replaced by it. A slot the engineer has not set shows what the part gave, dashed.
  - **Values** have steppers; the pattern, radii, draft, a rib's top and how spokes spread are
    lists. What spokes turn about is a list of the bosses and bores there, largest first, each
    shown on the part as it is picked.
  - **Words** can go in any slot, read by code, with the faces selected put in where the cursor is.
    Words it cannot read are kept and flagged, never guessed; only words typed are quoted.
  - **Orientation** starts from the longest wall round where ribs stand - a grid along it, parallel
    ribs square to it - or from a face the engineer picks, or a number, with a note saying which way
    0° points. Spokes fan across where ribs stand and need none.
  - **What is wrong shows on its slot as it happens**, down to a height limit that leaves no room
    for a rib, such as a face to stay below on the other side of the host, or a face to run between
    that does not stand up from it. Flat faces selected in one plane are where ribs stand together.
  - **Show paths** draws every line the layout lays across where ribs stand, never past it, cut
    into pieces by holes and gaps and coloured by what becomes of each piece, and redraws as the
    card changes: one to three seconds once the part is open. The words count lines, pieces and
    what each piece became, so the numbers add up; a design's verdict says the same.
- **Selecting**: each click is grown by its own angle or not at all; the stage lists the clicks,
  and the grow control acts on one of them. A face clicked after growing another starts ungrown.
- **Reading the part**: holes go round (a fillet in a corner is not a hole; a cast hole with draft
  is); what stands up round a host is found across fillets, rounds and chamfers, on the side ribs
  stand on; the card chooses spokes only about a boss or bore the host surrounds; the plate is
  measured by a ray through it; the smallest radius is the drawing's note, cited.
- **The study**, one file per study in `studies/`, every version kept with what changed, written
  from the card on every design:
  - one block of ribs: the card's values as the suggested point, and everything the engineer left
    open varying over a range read from the part - every pattern the floor allows, the round
    things spokes could turn about, the angle, spacing in thicknesses, 4 to 16 spokes, thickness
    from 0.6 to 1.0 of the plate, radii from the smallest the drawing allows. What the engineer
    set is fixed.
  - constraints, each hard, assumed or learned, with its source: the card's rules, the drawing's
    smallest radius, and the part's interfaces closed - every hole and bore, what the drawing
    controls, and the datums it names, waiting for someone to point at their faces.
  - the pull direction, assumed from the floor.
  - beside it, what nothing enforces yet - here the interfaces, until step 2 - and everything nobody
    confirmed.

  It refuses words never said, faces never selected, entities the part does not have, a hard rule
  that cites nothing, a range that holds no value. Entities are kept with their fingerprints and
  found again by them. The block at its suggested point is exactly the placement the card makes.
  The Generate tab shows the study; the verdict lists what was not checked.
- **The spec**, the study's first form, one file per spec in `specs/` - still what the agent reads
  and writes.
- **Placement** on a host of faces in one plane: straight families; grids laid as one lattice, so
  their families cross at common points; spokes all the way round or fanned across the host. Ribs
  are spans from one support to another. Each end stands as tall as what it meets there - buried as
  deep as it must be to stay inside it all the way up, never through it - and the top slopes
  between the ends, or stays level at the lower if asked; a named feature or a given height caps
  both. No rib is shorter than its root fillet. Every piece of every path is accounted for: a rib,
  or why not - a keep-out, an open edge, something not named (and what), too short, no room.
- **Designs from the study**, at its suggested point or at other values, at preview (twice the
  design grid) or full; the verdict lists the engineer's constraints, verified on the ribs placed and
  citing their words, then the checks, then what nothing enforces yet.
- **The agent** - a model with tools over the same card and engine, on LangChain, OpenRouter and
  LangSmith - is kept in the code, tested, and not in the interface.

Not yet: candidate ribs and a solver choosing among them; many designs from one study; the model
writing the study; layouts beyond straight families and spokes; ribs with no floor under them;
re-checking earlier designs against a new version. The zone and formation code from before is still
in the tree, unused by the interface.

## On the housing

**The card, started from the two halves of the ceiling** - `face:1201` and `face:1543`, one plane,
facing down - is ready with nothing typed: both halves are where ribs stand; 60 faces stand round
them; 12 holes go through them, two of them cast holes with draft; a square grid every 100 mm along
`face:723`, the longest wall; 12 mm thick, 0.8 of the 15 mm plate; R6 root; R3 edges and smallest
radius, from the drawing's *"ALL NON-SPECIFIED RADII R3.0"*, page 1; 1° draft. Spokes turn about
the bearing boss `face:1453`, Ø421, the largest round thing standing in the ceiling; the boss
`face:262`, Ø290, and two bores are offered too.

What each pattern draws there with nothing else set, before anything is made:

| pattern | set out | lines | pieces | ribs | the other pieces |
|---|---|---|---|---|---|
| square grid, every 100 mm | along `face:723`, 135° | 18 | 37 | 13 | at holes 16; too short 6; at an open edge 2 |
| parallel, every 100 mm | square to `face:723`, 45° | 8 | 18 | 10 | at holes 5; too short 2; no room for a rib's height 1 |
| triangle grid, every 100 mm | along `face:723`, 135° | 26 | 59 | 18 | at holes 25; too short 10; at an open edge 6 |
| spokes, 8 | fanned across the ceiling about `face:1453` | 8 | 9 | 4 | at holes 4; too short 1 |

Spokes about `face:262` make 7 ribs of 8 lines; about the Ø20 bore `face:1536`, 2 - its fan crosses
the holes and runs off the ceiling's open edges.

**Written as a study**, that card is one block of 12 free settings - every pattern, the four round
centres (`face:1453`, `face:262`, `face:1262`, `face:1536`), 0-179°, 60-200 mm apart, 4-16 spokes,
9-15 mm from the 15 mm plate, R3-R12 roots - and 9 constraints: the 12 holes where ribs stand 5 mm
clear, each end no taller than what it meets and every rib ending on what it runs between (both
assumed), no radius under 3 mm (the drawing), and the part's 206 holes, 20 bores, `bore:196`,
`bore:202` and `hole_pattern:2` closed as interfaces - listed as not enforced until step 2. All 289
entities it names are found again by fingerprint.

Designs made from the first half, `face:1201`, alone (preview):

| design | ribs | tall, each end | added | made in | verdict |
|---|---|---|---|---|---|
| spokes about `face:1453`, 16 all the way round, 12 mm thick | 5 | 105 mm at the boss; 52-133 mm at the walls | 837 cm³ | 227 s | keep-out, height, supports pass; mould release rejects |
| triangle grid at 45°, 8 across, 20 mm thick | 8 | up to 191 mm | 2,380 cm³ | 292 s | the same; a 20 mm rib on a 22 mm wall warned |

Opening the housing at a preview grid the first time builds its field: about 2 minutes.

## Open

- **Mould release rejects every design on the housing.** It rejects any metal along the pull from
  a rib tip however far away, and a rib hanging from a ceiling has the rest of the housing below
  it. Correcting it is step 3 of the build order.
- **Which way ribs stand.** A rib's pull is its host's normal; the spec does not yet carry the
  part's own pull direction.
- **Tall ribs are slow.** Heights that follow each end made the housing's ribs 100 mm and more, and
  a preview 4 to 6 minutes, most of it checking a window that grows with the ribs.
- **Holes cut most paths.** On the ceiling, nearly half the pieces a grid is cut into stop at a
  hole's keep-out, and a piece that ends there is not a rib. A grid's ribs cannot end on each other yet,
  only on what they run between, so round holes a grid comes apart instead of closing on its own
  crossings.
- **Only named supports count at both ends.** Name two faces and spokes that reach any other wall
  are dropped, reported as the fillet at that wall's foot rather than the wall.
- **Bosses and bores are not yet required to go round.** Holes are; convex cylinders are still all
  bosses, and 216 on the housing are mostly rounded wall corners and edge rounds. The card's list
  of what spokes turn about leaves those out; the Geometry tab still lists them.
- **Words** are read with a fixed vocabulary per slot; anything else is flagged for the engineer to
  set another way.

Size: 39 Python files, ~15,600 lines; 18 TypeScript files, ~5,200 lines. Tests are kept locally
as working checks and are not tracked; all 396 pass.

One project in `assets/`: **GRC Gearbox Housing** - the rib-free housing (`housing_baseline.brep`),
its 4-page drawing, and `project.json`.

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

Every Generate check has rejected a synthetic part built to fail it. On the housing, two of them
are wrong in ways listed below.

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
200° round its axis, so the fillets in corners that were counted as holes before are fillets now,
and the four "holes" at Ø20 that were fillets of R10 no longer make a pattern. The association rule
does not use single holes yet, so the hole callouts still find nothing. Patterns are still fitted
to circles only, and grouped by diameter and axis direction with no reference to position.

**One ambiguity correctly refused.** `'50.34 / 50.22'` matches two bosses both at Ø50.00, so nothing
is asserted.

**Volumes read about 70 cm3 high** with OCC's default integration: 121,374 cm3 against 121,301 from
tight integration on the housing.

**No mass.** Nothing states a material or a density. The drawing states a mass, but for the part as
drawn, not as brought; nothing reads it.

### Generate, on the housing

| | measured |
|---|---|
| field at 2.5 mm, once | 158 s |
| contour of the whole part, once | 20 s: 1.70 M vertices, 3.40 M triangles, closed, no faults |
| field at 3 mm, the preview grid for R6 ribs, once | about 2 minutes |
| the rib card filled from a selection | 0.1 s |
| the card's paths drawn, once the part is open | 1 to 3 s |
| a preview design from the card | 15 s to 6 minutes, growing with how tall the ribs are |
| a zone's exact distance, once per zone | about 11 minutes |
| a design, formations across a zone | 1.5 to 8 minutes, of which the checks are 1 to 7 |

Formation designs, from the zone code no longer in the interface, showed these defects:

- **Ribs escape the part.** A formation's lines are trimmed to a zone's air on the grid; where that
  air leaks through an opening, ribs pass through walls to the outside, and trimmed ends are ragged.
  A rib that runs as far as the grid's edge is now held back from it, so the surface still closes,
  and the design is rejected as off the grid.
- **Ribs are taller than what they meet.** Height is one fraction of the zone, so a rib overhangs a
  boss it lands on.
- **Mould release is too strict**: it rejects any part above a rib tip along the pull, however far.
  **Root gap** fires near crossings of arcs and lines. **Floating pieces** are left for the check to
  find rather than dropped.
- **Checks are slow** - most of a design's time.

Placement from the card - ribs as spans between supports, height following them, no trimming on
the grid - does not have the first two. Mould release is still as strict.

## Next

The steps in [build-plan.md](build-plan.md), each keeping every earlier study reproducing its
designs:

1. The study - the document, entities by fingerprint, constraints with strength and source,
   interfaces closed by default, the card as the editor of one block
2. Candidates and conflicts
3. Choosing (CP-SAT), sizing (Sobol), screening, and the archive with kill counts
4. The model on the study, and the requirement suite
5. Choosing what to show - about 20 representatives - and objections that become rules
6. The general rib - webs between any anchors, the pull direction, taper and T sections
7. An unseen housing, with no code changed
8. Speed - 4,000 designs overnight
9. Simulate and Learn
10. The next kinds of feature - pockets, local walls

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
| What a project holds | the engineer's CAD - no ribs - and drawings. No reference part, ever |
| `project.json` | decisions only: the baseline, which spec is active, approvals. Proposed by the system, confirmed by a person; no facts |
| Who it is for | CAE teams (variants and decks for a study), surrogate-data teams, design engineers (ribs suggested and modelled), foundries (reinforcement that casts) |
| The study | the source of truth, one file per study in `studies/` with every version: blocks (what to add, where, free settings with ranges and sources), constraints (hard, assumed or learned, with their source), preferences, objectives, the pull direction, the target and seed - in named entities bound by fingerprint, citing the engineer's words and selections; a rule nothing enforces yet is kept and listed. Written from the card today; generation reads only it. The agent still writes specs, the study's first form |
| What is unstated | explored within ranges read from the part and the drawing, and listed as assumed; asked first only when every design would otherwise be invalid |
| Where ribs go | where the study says - faces to stand on, anchors, regions to keep away from; the system proposes named regions when the client does not point |
| A rib | a web between two or more anchors, a floor optional; section, plane and pull direction from the study |
| Layouts | proposers - parallel, grids, spokes, a free proposer - never limits unless the engineer says so; designs described by properties, not by proposer |
| The rib card | the hand editor of one Add: ribs block: fixed slots filled from the part, set by value, face or words; works with no model; words it cannot read are flagged, never guessed |
| The model | writes the study from words and clicks, asks what blocks everything, explains failures, turns objections into rules; never makes geometry, never a call per design, never scripted to an example; sees names and numbers, never CAD files; provider is a setting |
| Objections | a stated reason becomes a rule the engineer confirms; a reason-less rejection only makes similar designs rarer, visibly |
| Variety | every free setting has a step; the designs shown are spread across their properties; the count of different designs is reported, not forced |
| Learning | within a study; within a client only if it opts in; never across clients |
| Judged by | the share of shown designs an engineer accepts - 70% by the third round on the housing - and a suite of 30 or more varied requirements plus a second part, run on every change |
| Simulation | Code_Aster, the same design twice agreeing within 0.1%, and analysis on the distance field; results kept apart, never folded into one number |
| Agent stack | kept in `agent/`: LangChain agent loop on LangGraph, OpenRouter (DeepSeek by default), LangSmith; conversation and checkpoints in SQLite with the project; credentials from the environment |
| Constraints and checks | constraints enforced and verified; checks are code, tested against failing parts, thresholds from the spec, basis shown. A model may add constraints, never checks |
| The part's own rules | rib section, root fillet, edge round, fillet floor: no default; set per part |
| Fidelity | preview on a coarser grid with nothing else relaxed; accept only at full |
| Tessellation | OCC `BRepMesh`, chord tolerance derived from the model |
| `cadquery-ocp` | pinned at 7.9.3.1.1; 8.x ships an unsigned binary Smart App Control blocked. Smart App Control is off on the build machine; 8.x is untested |
| SciPy | all of it loads, `scipy.stats.qmc` included: Sobol sampling is available |
| Constraint solver | OR-Tools CP-SAT, to choose rib combinations and to name the assumed rules that make a request impossible |
| Units | `xstep.cascade.unit` set explicitly to MM; the file's own declaration is read and reported |
| Scale-dependent tolerances | derived from the bounding diagonal, never absolute |
| A hole | goes more than 200° round its axis; a small concave cylinder that does not is a fillet |
| Control | derived from a toleranced drawing dimension matching a detected feature |
| Conflicts | recorded, never resolved, and not shown until an association is confirmed |
| Derived results | cached under `<project>/.fastcae/`, keyed on content and on the source that produced them; a miss is never an error |
| Design representation | a signed distance field on a fixed grid; a design is a study version and the values of its free settings, never stored geometry |
| Contouring | manifold dual contouring; the baseline whole, once; a design re-contours only what it changed, spliced by key. The grid's outermost layer is never solid |
| Design grid | a quarter of the root fillet unless asked for; voxel sizes offered are round numbers |
| Ports | API 8021, interface 5183 |
| Checks enforced | `ruff` and `tsc`. `mypy --strict` is configured and does not pass (235 errors in 20 files) |
| Version control | source and docs; `assets/` and `tests/` are not tracked |
