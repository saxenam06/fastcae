# Status

**This file describes what is true now.** Superseded content is deleted, not annotated.

---

## Where it stands

**Extract** and **Model** run end to end on any part. **Generate** runs end to end as the product
flow in [build-plan.md](build-plan.md): the engineer authors **variants** by hand on the CAD tab -
each one change in one place, with what it may vary and every rule it holds - composes a
**campaign** of the variants they choose on Generate, counts it, screens a hundred designs, and
launches it; every design is followed through its stages on Designs, and any one's field is built
at a click. Meshing, simulation, Learn and Optimize are visible in the interface and not built.

Every step of the build plan runs, the clean start included: the housing starts empty. The agent
is paused: its bar is hidden while variants and campaigns are built by hand.

What runs:

- **Five tabs** - Drawing, CAD, Generate, Learn, Optimize. Each tab lays out a rail of its subject's
  detail, the subject in the middle, and a pane on the right that folds to a strip at the edge.
- **Design a variant**, on the CAD tab's right. A tab for each variant kept - its code and name -
  and one for a new one. A new variant starts from the faces selected on the part and what to add
  there: **ribs on** them, **webs between** them, the faces **thickened** or thinned, **holes in** a
  plate; the card names the faces it will use. Ribs stand on flat faces in one plane: a selection
  that is not one is refused at once, naming what is curved and saying what to select. One change
  a variant: a second is refused, and so is the part's material, which no variant changes. The
  card shows a little and opens the rest on demand: where, in one sentence - its entities behind
  *change where* - then its shape and its rules. Every list of faces - stands on, ends on, keeps
  clear of, what spokes turn about - has an × on each face and *+ add* for the faces selected.
  Webs have two sides, **from** and **to**: every web runs from one to the other, never within one
  side; until the other side is added the variant says it needs it, and a face is on one side only.
  Webs from something round - a bearing - stand along its axis, and each web hangs from the height
  of its own two ends, so walls that step up and down are joined all round. A sample of faces moved
  says how many move and how far, with *show them*.
  A new variant of ribs starts from a starting point kept as data: 20 mm thick, 100 mm apart, as
  tall as what they meet, two to ten of them, two suggested; root fillet, edge round and draft
  each of three choices, the middle first.
- **What a variant may vary** - its shape: the settings that decide its designs first (for ribs the
  patterns, thickness, spacing, count, height), the rest under *More settings*; what spokes turn
  about and how they spread only while spokes are allowed, with *show*. Every setting applies to
  every pattern it is shown for - how many and how far apart included: lines each way for
  parallel ribs and grids, round the middle of the floor; spokes; free lines. Every setting is
  fixed, a range with a step, or some choices - each suggested by the part and changed where it
  shows: choices as chips switched on and off at a click, every choice the part offers shown;
  numbers in place, as a range or one value, kept on Enter, on done or on clicking elsewhere once
  touched, marked until then, a range from a value to itself that value; what the engineer set
  marked, with *reset*. Every range the part suggests steps by five in its
  own unit, its ends rounded inward onto fives; a height is a percentage stepping by five;
  thinning stops at five millimetres and never below the least wall.
  The patterns ribs may take are choices among parallel, square grid, triangle grid, spokes and
  **free** - independent lines, each at an angle of the range and a place across the floor, drawn
  from a layout seed nobody sets - so "only square" is one choice and anything another. The card
  counts the distinct designs the variant allows: for each pattern, the values of every setting
  that makes a difference to it, multiplied; free layouts have no end.
- **What a variant must hold**: every rule it holds is its own. The rules offered are the kinds the
  pipeline checks - keep clear of faces or of another variant's ribs or holes, no taller than, at
  most so tall, every rib ends on what it runs between, no rib thicker than a share of the wall it
  meets, no radius under, room for the sand between ribs (the root gap), no X crossings. The part
  suggests some for each variant, marked assumed and kept or taken out by hand. The part's
  interfaces are held for every variant: every rib and pad keeps 5 mm clear of every hole and bore
  of the part, and what the drawing controls, in three dimensions - its ends buried in what it meets
  included - or is not placed, drawn as reaching what the part keeps closed, naming it; what the
  ribs run between is theirs to meet.
- **Show paths and Another sample**: the variant alone at its suggested point, or at points drawn at
  random from what it allows - every choice, and every step of a range, as likely as the next -
  placed, repaired, screened, until one passes - drawn on the part with what repair left out drawn
  as left out; ribs and pads drawn as wide as they are, everything not made faint; the card says how
  the sample was drawn and on which try it passed, how many ribs and pads were made, the colours
  folded under it, and the values it took that make a difference to its pattern. Every sample keeps
  to what the variant allows. **Create variant**, at the bottom,
  keeps it in `<project>/variants/<id>.json` under its name once a point passes, and refuses one
  none of whose points does, saying why. A variant kept is changed and saved, discarded back,
  duplicated or deleted - moved aside, never lost.
- **Campaign**, on Generate, a card in three steps:
  - **Compose**: its name, and the variants it takes, each with how many designs it allows.
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
- **Designs**, on Generate: a campaign's designs, each with its stages as letters - P its paths
  placed and screened, F its field built and checked, M meshed, S the solver set up, R results -
  coloured by how each came out, and dots for the variants it holds; the 20, 30 or 50 that differ
  most, those built, or all of them 200 at a time; only those holding one variant, when asked. A
  design reads by variant - code, name, what it made and the values it took - with the variants it
  leaves out, what repair left out, and its recipe and seed. Its paths are drawn at once; its field,
  once built, is the surfaces it changes over the part - run down to where they meet it, taking the
  part's colour there - and its new metal as cells; the designs that differ most are side by side
  as plans.
- **Building a design**: its field at preview or full, from the copy of the variants its campaign
  kept - faces moved, each rib and pad filleted with its own root fillet, holes cut, mended, one
  recontour - checked, and kept beside the campaign. Mould release is not among the checks while
  variants hold no pull direction.
- **Kinds of change**, each read off the part round what the engineer gave:
  - **ribs** on a floor - faces in one plane - and **webs** with nothing under them, between what
    they join; spans between supports, each end buried in what it meets, the top sloping or level;
    held to the wall they meet - no thicker than 0.8 of it - with a pad round a rib's end where a
    wall is too thin, and a floor thickened for ribs too thick for it, never either past twice
    itself.
  - **faces thickened** - a wall, a plate, a boss - along their normal, blended into what is round
    them; built exactly in a window round them; a variant that would move a bore is refused.
  - **holes**: a square or staggered lattice through a plate, each hole a ligament of metal from the
    next, the plate's edges, the holes it has and the ribs of every variant; none over something
    standing under the plate.
- **Reading the part**: holes go round (a fillet in a corner is not a hole; a cast hole with draft
  is); what a feature stands on is found across the fillets and chamfers at its foot; what rises
  round a floor across fillets, rounds and chamfers; what lies across the open space from an entity
  by rays out of its metal; the plate and walls measured by rays through them; the smallest radius
  is the drawing's note, cited.

Not yet: tapers and gussets; bulges, boss transitions, existing ribs varied; staggered crossings; a
review loop turning objections into rules; the agent writing variants and campaigns. The zone and
formation code from before is still in the tree, unused by the interface; the study functions the
agent writes through are kept for it.

## On the housing

**The project starts empty**: the housing's CAD, its drawing and what was read of them; no variant,
no campaign, no conversation. What was made before - the ten-block study, its campaigns, the agent's
conversation - is kept in `_archived_designs/_retired/2026-09-13/`, where nothing lists it.

**The flow, walked in a browser** on a scratch copy of the housing, as an engineer would:

| step | what | came to |
|---|---|---|
| variant | ribs on `planar_group:114` (`face:1201`), square grid only, 15 to 25 mm | 8 ribs and 8 pads at its suggested point; 19,293,120 designs |
| variant | `boss:1612` moved, −5 to 10 mm | 12 designs |
| variant | holes through `planar_group:115` (`face:1543`) | 4 holes at its suggested point; 214,200 designs |
| campaign | the three, spread evenly, 20 designs | 5.4 × 10¹⁵ designs allowed; Screen 100: 100 pass, 8 after repair |
| launch | alone: the ribs 32 of 90 points pass, the boss 12 of 12, the holes 32 of 36 | 20 kept of 20 tried, 3 repaired, 2 s |
| design | #1, the grid ribs, the boss 5 mm thicker and three Ø35 holes, built at preview | warn - blend bridging and clipping - 15 checks pass; 91 s |

A campaign of 4,000 designs of ten blocks, before the product flow, placed and screened each in
about 60 ms once each block was known; 20 designs of three variants took 2 s above.

## Open

- **Mould release waits for the pull.** Variants hold no pull direction, and a check that rejected
  any metal along the pull from a rib tip - however far, and not knowing that cores form the pockets
  inside a casting - rejected every design built on the housing. It comes back with the pull and
  with cores.
- **Where a variant fits is found by trying.** Nothing says, before a variant is added, which floors
  or plates take ribs of a given thickness, or holes of a given size: Show paths tries up to 48
  points, and a variant none of whose points passes is refused.
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
- **The agent is paused.** Its tools write the study draft; it comes back writing variants and
  campaigns, and the objections a review turns into rules.
- **Holes cut most paths.** On the ceiling, nearly half the pieces a grid is cut into stop at a
  hole's keep-out, and a piece that ends there is not a rib: round holes a grid comes apart instead
  of closing on its own crossings.
- **Only named supports count at both ends.** Name two faces and spokes that reach any other wall
  are dropped, reported as ending on something not named, with what.
- **Bosses and bores are not yet required to go round.** Holes are; convex cylinders are still all
  bosses, and 216 on the housing are mostly rounded wall corners and edge rounds.
- **The mesh, solver setup and results stages are not built** in the product; a design's M, S and R
  stay empty, and nothing ranks designs but their geometry and mass. The solving route is measured on
  design #7 and agenticCAE's design ([../bench/solvers/RESULTS.md](../bench/solvers/RESULTS.md)):
  TET10 solved by cuDSS on the GPU gives Code_Aster's answer in 13 s.
- **Meshing a design takes 31-103 minutes.** fTetWild on the design's surface, decimated from 2.5 M
  triangles, with a 1.9 or 0.95 mm envelope; the solve after it takes 13 s.
- **Ribs grow as tall as the metal behind their ends.** An end's height is the tallest column of
  metal found up to 60 mm into what it meets, and the housing's walls are 560-640 mm tall, so ribs
  reach 105-241 mm and a web 422 mm - through a 494 mm column behind a 45 mm boss. No variant holds a
  height limit, and the starting height is 100% of what each end meets. Fix agreed: height from what
  an end actually meets, webs within where both sides overlap, height a setting in thicknesses.
- **Spokes turn about freeform faces' middles.** A spoke centre that is a freeform face has no axis, so
  spokes fan from a point on it - 296 mm off the bearing's axis on the housing. Fix agreed: only round
  things with an axis.
- **Floors are thickened under ribs too thick for them** - a layer over the whole floor face. Agreed:
  no floor thickening; such a rib is left out.
- **Holes look blind in the Field view, though they go through.** The view draws the part's CAD surface
  and, over it, only the surfaces a design changes; the CAD faces a hole cuts are still drawn. Fix
  agreed: hide the faces a design cuts, and a verdict check that holes go through.
- **Builds block, show no progress and die with the development server.** A field build runs inside
  the request; a reload of the development server kills it and nothing is saved. Thickening 262 faces
  spends 30-40 minutes in one step of the face-moving pass - its nearest-face queries cover the whole
  grid per group of faces - so such a design takes 45-60 minutes.

Size: 50 Python files, ~23,900 lines; 21 TypeScript files, ~7,500 lines; 8 skills. Tests are kept
locally as working checks and are not tracked.

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
| Show paths of a variant, once the part is open | about 1 s |
| Screen 100 of three variants | about 4 s |
| a campaign of 20 designs of three variants, pools included | 2 s |
| a campaign of 4,000 designs of ten blocks, together | about 60 ms a design once each block is known |
| a design built at preview - its field, surfaces and cells, checked, kept | 1.5 to 16 minutes the first time; 80 s once its windows are kept; 45-60 minutes with 262 faces thickened |
| the preview grid | 425 × 463 × 258 = 50.8 M cells at 3 mm, 5.5 M near the surface; the full grid at 1.5 mm about 403 M |
| design #7 of `w4zf5` (15 ribs, 11 pads) built at preview, outside the interface | 1,962 s; 2.54 M surface triangles |
| that design meshed as TET10 by fTetWild, 20 mm | 31 min for 648 k unknowns (1.9 mm envelope); 103 min for 1.06 M (0.95 mm) |
| its TET10 solve, 1.06 M unknowns | 13 s by cuDSS on the GPU (5.2 GB); 35 s PETSc multigrid on the GPU; 57 s Code_Aster, one core |
| the workstation | i7-13700HX (16 cores, 24 threads), 15.7 GB RAM, RTX 5060 Laptop 8 GB; WSL Ubuntu 24.04 with 12 GB |

## Next

**Now** - the next phase in [build-plan.md](build-plan.md): first the fixes the engineer asked for
(rib height, no floor thickening, holes seen through, builds that finish); the solving route, the
supports and the mesher decided from the measurement on design #7
([../bench/solvers/RESULTS.md](../bench/solvers/RESULTS.md)) - TET10 and cuDSS recommended, meshing
now the slow step; then the pipeline that meshes, solves and records each design, the data in rounds,
the field model, and the agents that supervise it. Mould release with the pull and cores, and the
engineer's review loop, after.

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
| What a project holds | the engineer's CAD - no ribs - drawings, and the variants authored for it. No reference part, ever |
| `project.json` | decisions only: the baseline, approvals. Proposed by the system, confirmed by a person; no facts |
| Who it is for | CAE teams (variants and decks for a study), surrogate-data teams, design engineers (ribs suggested and modelled), foundries (reinforcement that casts) |
| A variant | one change in one place - ribs on, webs between, faces thickened, holes in - with what it may vary and every rule it holds, in named entities bound by fingerprint; a short random code and a name that says what and where; kept in `variants/`, edited freely, versions never shown |
| What a variant may vary | every setting fixed, a range with a step, or choices; ranges the part suggests step by five, ends on fives, a height by five percent; patterns are choices, free lines among them; the count of distinct designs shown |
| What a variant must hold | every rule is the variant's own; only kinds the pipeline checks are offered; the part's interfaces held for every variant |
| A campaign | a card: name, variants, screening checks held, method (spread evenly, random, every combination), how many, seed, keep the most different of more. Each design a random set of the variants - sizes spread evenly - each at a pool point; never narrows a variant; every launch a campaign of its own |
| Repair | CP-SAT leaves out the fewest ribs, pads or holes so no rule between pieces breaks - root gap, wedges, holes clear of ribs, X crossings a variant forbids - holes before ribs on a tie, deterministic; a design built is mended the same way |
| Clearance | measured from a rib's footprint - half its thickness at the root and its root fillet - never its centre line |
| Mould release | not checked while variants hold no pull; back with the pull and with cores |
| Reproducing | a campaign keeps its card, the part's digest, the code's commit, a copy of its variants, its seed and method; each design its recipe, the recipe's hash and its own seed |
| What is unstated | explored within ranges read from the part and the drawing, and listed as assumed |
| A rib | a web between two or more anchors, a floor optional; section, plane and pull direction from the variant |
| The interface | five tabs - Drawing, CAD, Generate, Learn, Optimize - every one shown built or not; Design a variant on CAD; Generate is Campaign and Designs; the agent's bar hidden while it is paused |
| Kinds of change | ribs and webs; faces moved along their normal - walls, plates, bosses; holes through a plate on a lattice. The part is cast in one material, which no variant changes. Built in one order - faces moved, then ribs and pads, then holes |
| Design knowledge | data with its sources, in `knowledge/materials.json`: rib to wall 0.8, root gap 2 thicknesses, a hole's ligament one plate thickness, a least wall 8 mm, six casting materials with density, stiffness, strength and least wall from their standards; where a new variant of ribs starts - 20 mm thick, 100 mm apart, full height, two to ten, three choices of each radius and draft |
| Pads | on unless the engineer says otherwise: a wall too thin for a rib is padded round its end, a floor too thin for its ribs thickened for them, never either past twice itself; off, the rib is left out or the design screened out |
| A design's stages | P paths, F field, M mesh, S setup, R results, each shown with how it came out; every design's paths kept with its campaign, drawn at once; a built field kept beside its campaign |
| Rib ends | a rib ends on what it meets, buried in it, or stops at least the root gap short of any metal ahead - never a finger of sand between |
| The model | paused; when it returns it writes variants and campaigns from words - never geometry, never a call per design, never scripted to an example |
| Learning | within a project; within a client only if it opts in; never across clients |
| Simulation | Code_Aster or CalculiX, the same design twice agreeing within 0.1%, and analysis on the distance field; results kept apart, never folded into one number |
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
| Contouring | manifold dual contouring; the baseline whole, once; a design re-contours only what it changed, spliced by key. The grid's outermost layer is never solid |
| Design grid | a quarter of the root fillet unless asked for; voxel sizes offered are round numbers |
| Ports | API 8021, interface 5183 |
| Checks enforced | `ruff` and `tsc`. `mypy --strict` is configured and does not pass |
| Version control | source and docs; `assets/`, `tests/` and `_archived_designs/` are not tracked |
