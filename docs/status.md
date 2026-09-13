# Status

**This file describes what is true now.** Superseded content is deleted, not annotated.

---

## Where it stands

**Extract** and **Model** run end to end on any part. **Generate** runs end to end in a first form
of the design in [ribs.md](ribs.md). The engineer builds the **study** by hand on **Design a
variant**, on the CAD tab - blocks of ribs, webs, faces to thicken, holes and the material, from
faces selected on the part - or says what they want to the agent above every tab, which writes the
same draft; they accept it or undo it, and make one variant of it to look at. A **campaign**, on
Generate, makes as many designs as asked - thousands - each placed and screened in a fraction of a
second and kept beside the project, with the whole pipeline shown and any block, rule or check
switched off for that campaign alone; every design is followed through its stages - its paths, its
field built and checked, then mesh, setup and results - and any one's field is built at a click.
Meshing, simulation, Learn and Optimize are visible in the interface and not implemented.

The steps are in [build-plan.md](build-plan.md). Step 1, the study, runs; so do the first part of
step 4 - the model writing the study from words, over a few general tools and skills - a first form
of step 6 - webs with nothing under them, T sections, the pull direction for them - most of step 3
without its solver - Sobol over each block alone and then together, screening, the archive - and
the first kinds of step 10: faces moved, holes, the material, pads. Next is CP-SAT choosing and
repairing combinations.

What runs:

- **Five tabs** - Drawing, CAD, Generate, Learn, Optimize - with the agent in a bar above them all,
  one conversation whichever tab is open. Each tab lays out a rail of its subject's detail, the
  subject in the middle, and a pane on the right that folds to a strip at the edge.
- **Design a variant, by hand**, on the CAD tab's right. Faces selected on the part become a block:
  ribs standing on them, webs between them, faces to thicken, a plate to cut holes in - or the
  material, which needs nothing selected; until a face is selected the card says how. What a block
  stands on and ends on is taken from the selection; every setting is fixed, ranged with a step,
  narrowed to some choices or handed back to the part where it shows; a block keeps a clearance
  from what is selected or from another block's ribs or holes; a rule the part suggested is kept or
  taken out; a block is taken out. Each is the engineer's own, said in words among the study's -
  *"By hand: b1 thickness from 15 to 25"* - with the faces selected. What the study rests
  on - every word said, every version - folds away under the blocks.
- **Kinds of block** beyond ribs, each read off the part round what the engineer gave:
  - **thicken**: faces - a wall, a plate, a boss - moved along their normal, from a few mm thinner
    (never below 8 mm, or the material's least) to 10 mm thicker unless ranged by hand, blended into
    what is round them; built exactly in a window round them, the part's bores left as they are. A
    block that would move a bore is refused.
  - **holes**: a square or staggered lattice through a plate - diameter one to four plate
    thicknesses, pitch, angle from its longest direction, edge distance - each hole a plate
    thickness of metal from the next, the plate's edges, the holes it has, and the ribs of every
    block, over the plate or under it; none over something standing under the plate.
  - **material**: what the part is cast in - one of a catalogue of six casting materials, grey and
    ductile irons, cast steel, cast aluminium, each with its density, stiffness, strength and least
    wall from its standard - chosen once, never varied: a part is cast in one material, which its
    designs do not change. Assumed EN-GJS-400-18-LT until someone says, and marked so; a block
    letting it vary over several, or a second material block, is refused.
  - **ribs** hold to the wall they meet: no thicker than 0.8 of it, a rule the part suggests and the
    engineer may take out. With pads on - suggested - a wall too thin gets a pad round the rib's
    end, never more than doubling it, and a floor too thin for its ribs is thickened for them in
    that design; off, the rib is left out, or the design screened out.
- **Screening** on what placing a design knows, milliseconds a design: every block made something;
  ribs no thicker than the floor under them allows, as the design leaves it; holes a ligament clear
  of the ribs they keep clear of; the root gap between ribs, within each block and between blocks;
  no wall thinned below its least. Each design weighed in its material.
- **Campaigns**, on Generate: how many designs to keep and from which seed, and launch. Each
  block's settings are tried alone first - Sobol over them, the others at their suggested points -
  keeping the ones that make something and hold the block's own rules, and saying how many of how
  many; then designs spread over which of each block's points to combine, placed together, screened,
  alike ones kept once, until the target is reached. What a block reads off the part is read once
  for every design, and a block placed alike before is reused, so a design costs its own paths. The
  launch pane counts designs as they come - per block, kept and tried, what screened the rest out,
  from what mass to what - and opens the run's designs when it is done.
- **The pipeline in the open.** The Campaign tab lays out everything a campaign runs: what varies -
  each block, where, what its settings may take and who said so; what must hold - each block's
  rules, the study's, the part's interfaces; the screening checks, each with its rule and source;
  how ribs, pads and holes are placed - how far a rib's end looks, stubs, pads, floors, holes over
  plate, ribs of other blocks, how far faces move, T flanges, how clear the interfaces stay; the
  rules of thumb and the six materials with their sources; how designs are spread; the stages a
  design goes through, and what a built design is checked for. Any block, rule or check is switched
  off there for one campaign without touching the study.
- **Runs**: every campaign is kept in `_archived_designs/<project>/<run>/` beside `assets/` - every
  design kept, with everything it is made of, how it screened and what it weighs; the study version
  it was made from with what the campaign switched off; a summary; and each design built so far.
  A run is named by its study and version, and by a few characters more when it switched anything
  off or spread from another seed, so another campaign of one version is a run of its own.
- **Every design's paths are kept with its run** - each stretch each block tried and what became of
  it - so any design is drawn on the part as fast as Show Paths draws the draft: 0.01 s a design once
  the run is read. A run kept without them is placed again on the grid its campaign used, the part
  opened on it once.
- **Designs**, on Generate: a run's designs, each with its stages as letters - P its paths placed
  and screened, F its field built and checked, M meshed, S the solver set up, R results - filled
  green, amber or red for how each came out; how many are at each; the 20, 30 or 50 that differ
  most, those built, or all of them 200 at a time. A design's paths are drawn on the part; its field,
  once built, is the surfaces it changes over the part and its new metal as cells; the designs that
  differ most are side by side as plans along the pull. Build field makes it from the study version
  its run was made from, checks it, and keeps it beside the run.
- **The agent**, in the bar above every tab. The engineer's words, with any faces selected, go to
  it, and it reads the part with a few general tools and writes the draft:
  - it composes eight tools - find entities; describe them; relate them to the part (what they
    stand on, what rises round a floor, what is round a face, what shares an axis, what lies across
    the open space in front of them, what lies between several of them, under and over); measure
    them; search the drawing; read and edit the study; and read a skill - composing them as a skill
    says for a kind of request: ribs round a round thing, on a face, between things; keeping clear
    of anything; rules from words; sections; naming things; refining turn by turn. Skills hold no
    ids, numbers or example sentences.
  - an edit is checked as a study version is - refused, with the reason and nothing changed, if a
    quote is not the engineer's exact words or an entity is not on the part - and the part's
    interfaces are closed whatever it sends. Every edit comes back with where each block's ribs
    would go, counted, so the agent sees its reading makes ribs before the engineer does.
  - each turn refines the study: another place is a new block; a limit on ribs already there is a
    rule in their block; "without interfering with the ribs already there" keeps a new block clear
    of every earlier block's ribs. A rule about one block's ribs lives in that block; one about
    every rib, after the blocks.
  - it says only what needs the engineer: at most three attention lines, entities as chips. They
    stay until an edit gives them again or clears them, and every edit shows them back to the agent
    to check they still hold. After eight questions of the part since the study last changed, every
    answer reminds it that the engineer can be asked instead.
- **Design a variant** is the draft of the study's next version, read back from the study when the
  project opens, changed by hand or by the agent.
  - **Each block is its entities**: what its ribs stand on - a floor, or nothing, for webs between
    what they join, with the way they stand and how high they reach; what they end on - named, or
    read off the part; what they keep clear of - any face or feature, the holes found, another
    block's ribs - each a chip that shows it on the part and says whose it is. Then its settings,
    each fixed or what it may vary over and who suggested that, and its rules, each hard, assumed
    or learned, with whether anything enforces it yet.
  - After the blocks: rules for every block, what makes a design better, the pull, and the part's
    interfaces, folded. What the draft changes is marked; a bar folds the changes, and Accept writes
    the next version while Undo reads the study back. A rule the words put in, or one the part
    suggested, is taken out by its cross; the interfaces stay closed.
  - **Where ribs would go** is drawn on the part as the draft changes: every line each block's
    layout lays, cut into pieces by what it keeps clear of and by gaps, each piece coloured by what
    became of it - pads and holes in colours of their own - and counted so the numbers add up.
  - Preview and Full make the study's suggested variant, with its verdict - ribs, pads, holes, mass
    and material - and draw the surfaces it changes over the part.
- **Reading the part**:
  - holes go round (a fillet in a corner is not a hole; a cast hole with draft is);
  - what a feature stands on is found across the fillets and chamfers at its foot, and through
    every band of a round feature the CAD split, so a stacked boss stands on the floor at the foot
    of the stack; floors at one level are said together, with whether they go round it;
  - what rises round a floor is found across fillets, rounds and chamfers, on the side ribs stand
    on;
  - what lies across the open space from an entity - the wall a web from it would reach - by rays
    straight out of its metal; and what lies under and over the space between several things -
    a floor at their foot, or open space;
  - the plate and walls are measured by rays through them; a rib is 0.8 of the thinner of the plate
    it stands on and the thinnest of the six largest walls it meets; the smallest radius is the
    drawing's note, cited.
- **The study**, one file per study in `studies/`, every version kept with what changed:
  - blocks, each what to add and where - what it stands on, possibly nothing, and ends on - with
    its free settings, each a range or choices with a step, a suggested value and a source. What
    the words set is fixed; the rest is read off the part: on a floor, every pattern it allows,
    what spokes could turn about, the angle, spacing, count, thickness from the plate and walls,
    radii from the drawing's smallest, draft, height, flat or T sections with the flange ranged from
    the web; for webs with nothing under them, the way they stand, spokes about the round thing they
    join or straight webs, thickness from the thinnest thing they join, a level top.
  - constraints, each hard, assumed or learned, with its source and who wrote it - the engineer's
    words, the part's suggestion for a block (recomputed each time the draft is read, and kept out
    once taken out), or the platform closing the part's interfaces: every hole and bore, what the
    drawing controls, and the datums it names.
  - preferences, objectives, the pull, the target and seed; beside it, what nothing enforces yet and
    everything nobody confirmed.

  It refuses words never said, entities the part does not have, a hard rule that cites nothing, a
  range that holds no value; words it already holds can be quoted again. Entities are kept with
  their fingerprints and found again by them.
- **Placement**, for ribs on a floor - faces in one plane - and for webs with nothing under them:
  - straight families; grids laid as one lattice, so their families cross at common points; spokes
    all the way round, or fanned across the floor - or, for webs, across the things they reach.
  - webs with nothing under them stand along the direction the most of what they join runs along -
    the pull first among equals - from the level where the most of it is present, laid across the
    open space between them; each runs from one of them to another. Straight webs are laid where
    two of them face each other.
  - ribs are spans from one support to another, each end buried as deep as it must be to stay
    inside what it meets all the way up; the top slopes between the ends or stays level at the
    lower; a named feature, a given height or anything standing over the path caps it. Spokes may
    meet at their roots; past them each leaves twice its thickness clear of the next, as does a rib
    of a later block beside one of an earlier.
  - a rib free to end anywhere ends on whatever is nearer its end than room for the sand - twice
    its thickness - so no finger of sand is left between a rib and a wall beyond a fillet; a built
    design with one anyway is rejected.
  - each end's wall measured square through it where the rib meets it, with what the design moves
    its faces by; padded, or the rib left out, where it is too thin.
  - keeps clear of any entity by its outline - a disc for something round - and of another block's
    ribs and holes in three dimensions, placing that block first: a rib on a ceiling is no obstacle
    to one far below it.
  - every piece of every path is accounted for: a rib, or why not - a keep-out, an open edge,
    something not named (and what), one thing at both ends, crowded, too short, no room, a wall too
    thin.
- **Designs built**, the study's suggested point or any design a campaign kept, at preview (twice
  the design grid) or full: faces moved, each rib and pad filleted to the part as moved with its own
  block's root fillet, holes cut, one recontour; the verdict lists the engineer's constraints,
  verified on what was placed and citing their words, then the checks - each rib held to its own
  block's thickness and draft and to the fillet it was made with - and what screening found, then
  what nothing enforces yet.

Not yet: a solver choosing and repairing combinations; tapers and gussets; bulges, boss transitions,
existing ribs varied; keeping clear of one rib picked from a design; re-checking earlier designs
against a new version; kill counts. The zone and formation code from before is still in the tree,
unused by the interface.

## On the housing

**A study of ten blocks, built by hand on the card**, in a scratch project, as an engineer would:

| block | adds | where | what varies |
|---|---|---|---|
| b1 | ribs | under the top plate, half A (`face:1201`) | spokes about the upper bearing's boss `face:1453`, fanned or all round, 4 to 16; clear of `face:1417` and `face:1456` |
| b2 | ribs | under the top plate, half B (`face:1543`) | parallel, square or triangle grid; clear of `planar_group:161` |
| b3 | webs | between the intermediate bearing's boss `face:349` and the side walls | spokes or straight; 40 mm clear of b1's and b2's ribs |
| b4 | ribs | on the floor at z 20 (`planar_group:104`) | every pattern |
| b5 | ribs | under the ceiling at z 100 (`planar_group:12`) | every pattern |
| b6 | thicken | the side walls b3 ends on | 4 mm thinner to 10 mm thicker |
| b7 | thicken | the main bearing's Ø600 boss ring, nine pieces | 0 to 15 mm thicker |
| b8 | thicken | the upper bearing's boss | 0 to 10 mm thicker |
| b9 | holes | through the top plate, both halves | square or staggered, Ø15 to 55, pitch, angle, edge distance; a plate thickness clear of every block's ribs |
| b10 | material | the part | nothing: the part is cast in EN-GJS-400-18-LT, as assumed until someone says - a part's material is not varied |

Every rib block is 15 to 25 mm thick, by hand, with pads. Where 15 to 25 mm ribs fit was found by
trying each flat face the part has: under both halves of the top plate, the floor at z 20 and the
ceiling at z 100; the large floors low in the housing are cut into stretches too short for them.
Webs round the main bearing's boss ring, to the outer walls, made nothing at any of 200 settings and
were taken out.

**A campaign of 4,000 designs**, in 21 minutes on one core beside other work: each block alone first,
then 4,022 combined to keep 4,000 - 723 of them once the one block screening them out had taken
another of its points; 15 screened out for holes with no room between that design's ribs and 7 for
a block left without ribs. Alone, each block's settings made something at these rates: b1 1,000 of
2,399, b2 1,000 of 3,885 - mostly ribs too thick for the top plate even with it thickened - b3
1,000 of 3,339, b4 1,000 of 2,483, b5 1,000 of 1,714, the holes 1,000 of 2,142; every setting of
the faces moved.

| per design | least | median | most |
|---|---|---|---|
| ribs | 5 | 13 | 26 |
| pads | 0 | 6 | 16 |
| holes | 1 | 3 | 84 |
| added, kg | 18 | 49 | 113 |
| mass, kg | 878 | 910 | 974 |

The bare housing is 862 kg in EN-GJS-400-18-LT. Every design thickens the floors its ribs stand on
where they are too thin for them; every rib block takes every thickness from 15 to 25 mm, every
thicken block every offset, every hole diameter from 15 to 55 mm. Each design is a line of
`_archived_designs/GRC_Gearbox_Housing/ten-blocks-v3/designs.jsonl`, with every rib, pad, hole and
face moved, and its paths a line of `paths.jsonl` beside it.

A campaign of 8 from the same ten blocks, launched in the interface with one check switched off
and another seed, took 16 seconds; one of its designs was built from the interface in 12 minutes
the first time and 80 seconds once its windows were kept. Mould release rejects every design built
on the housing - see Open.

**The engineer's five requests, in one conversation**, the agent on DeepSeek through OpenRouter at
high reasoning effort, each refining the study the earlier ones wrote:

| # | the engineer wrote | the agent wrote | ribs at the suggested point | time |
|---|---|---|---|---|
| 1 | *add ribs all around the bearing with face:1453 but make sure the ribs dont cross face:1417 and face:1456* | b1: spokes all the way round `face:1453`, standing on both ceiling halves, `planar_group:114` and `planar_group:115`; clear of `face:1417` and `face:1456`, a rule of b1's own; the 12 holes through the ceiling 5 mm clear, suggested by the part | 5 | 64 s |
| 2 | *Add ribs on the face: face:1201* | b2 on `face:1201`, everything else read off the part - every pattern left open | 8 | 20 s |
| 3 | *add ribs on the face:1543 but they should not cross the boss with face:1167* | b3 on `face:1543`, clear of `boss:1397` - of the two bosses `face:1167` touches, the one standing on `face:1543` - naming the other, `boss:1398`, in an attention line | 9 | 88 s |
| 4 | *can you add ribs all around the bearing with face:1645 and face:349 and the wall without interfering with other ribs already in place due to the result of above queries* | b4: webs with nothing under them - spokes all the way round `boss:349` out to the outer wall, `planar_group:147`, found across the open space from it - clear of the ribs of b1 to b3 | 1 | 241 s |
| 5 | *add ribs between face:349 and the wall without interfering with other ribs* | b5: webs between `face:349` and `planar_group:147`, fanned across the wall, clear of the ribs of b1 to b4 | 4 | 36 s |

`boss:349` and `face:1645` are the edge of a plate 70 mm thick round a bearing bore, and the
housing's outer wall stands 130 to 160 mm across open space from it, from 110 mm up to 160; nothing
lies under that space. So both b4 and b5 stand along z, from 110 mm, level with the lower end - 12
mm thick, 0.8 of the 15 mm outer wall. The agent said in its attention lines which reading it took
where the words allow two: which boss, which wall, and why b4 and b5 stand on nothing. Spokes all
the way round `boss:349` reach the wall with one of four; fanned across the wall, as b5's are, four
do.

A design of the same five blocks, written by hand and made at preview: 28 ribs, 5,309 cm³ added, 63
seconds once the part is open. Every rule the engineer gave passes; the checks reject it for mould
release and for ribs of two blocks 0.4 mm apart - a gap placing now leaves out as crowded.

## What the agent adds

On those five, every decision that shaped a block came from the part or from a rule written for
the model:

| # | decided by | left to the model |
|---|---|---|
| 1 | what `face:1453` stands on: both ceiling halves, round it together | turning *"dont cross"* into a rule of b1's |
| 2 | the block read off `face:1201` | nothing a click could not do |
| 3 | what `face:1167` touches - two bosses - and the rule to take the one standing where the ribs go | following the rule |
| 4 | what `boss:349` looks at across open space, and that nothing lies under it: webs | putting the answers together |
| 5 | the same, and the rule that words adding ribs start a new block | following the rule |

It works from its instructions (3,500 characters), the eight tools' descriptions, eight skills
(about 2,000 words, each read when a request is of its kind), what the tools answer, and the study.
It has no knowledge base, no model of what the part's regions are for, no memory beyond the
conversation, and no sight of the part. Its tools answer geometric questions, not engineering ones:
which wall a word means takes several questions and minutes of reasoning, afresh each time - which
is where the time goes, and where one run differs from the next.

So, on requests that name what they mean by id, it adds only time; where the words name things
loosely, it resolves them and says which reading it took. Nothing in making designs depends on it:
the card now writes the study by hand, and the agent is a second way into the same draft. The work
where words are worth more than a form - documents, objections, explanation over many designs, a
brief read into several kinds of feature - is not built, and needs the knowledge it lacks, in
[ribs.md](ribs.md). Finding where a kind of block fits at a size - which floors take 15 to 25 mm
ribs, which the part answered only by trying each - is one such question worth a tool.

## Open

- **Combinations are repaired only by trying again.** A design screened out by one block alone
  takes a few other of that block's workable points - 723 of the 4,000 on the housing came so - but
  no solver yet leaves out the one rib or hole in the way, and a design screened out by two blocks
  together is dropped. CP-SAT is next.
- **Where a block fits is found by trying.** Nothing says, before a block is added, which floors or
  plates take ribs of a given thickness, or holes of a given size.
- **The agent knows only what its tools answer.** The part's regions carry no roles - bearing seat,
  web, outer wall, flange, cover. Design knowledge is data for the rules and materials campaigns screen
  with - a rib 0.8 of the wall it meets, a root gap of two thicknesses, a ligament of a plate
  thickness, a least wall, six materials, each with its source, in `knowledge/materials.json` - but
  the ranges a block is read off with are still constants in code: ribs 5 to 16 thicknesses apart,
  a 1° draft.
- **A campaign runs on one core**, a design of ten blocks in about 60 ms once each block is known;
  building a design's field is minutes, so the 4,000 are placed and screened, and built one at a
  time on Designs.
- **Mass is an estimate** for screening - ribs as plates, fillets and draft aside - beside the base
  part's exact volume; a built design is weighed exactly.
- **The agent is slow**: a minute or more of reasoning between tool calls on DeepSeek at high
  effort, so a request that needs the part read round an unfamiliar name takes several minutes; the
  tools themselves answer in well under a second. Lower effort or a faster model would cut it; both
  are settings.
- **The same words can be read two ways from one run to the next** - one ceiling half or both,
  spokes fanned across a wall or all the way round, a new block or the last one changed. The
  attention lines say which reading was taken, and the engineer's next words settle it.
- **Mould release rejects every design built on the housing** - the one check they all fail. It
  rejects any metal along the pull from a rib tip however far away, and inside the housing a line
  from any tip meets another wall: it does not know that cores form the pockets inside. Correcting
  it is step 3 of the build order, before anything built can come out green.
- **A built design is drawn by the surfaces it changes**, over the part as its CAD describes it:
  within three quarters of a cell of the part the part's own surface shows, which can read as a
  seam at a rib's root where the metal is joined.
- **The mesh, solver setup and results stages are not built**; a design's M, S and R stay empty.
- **Holes cut most paths.** On the ceiling, nearly half the pieces a grid is cut into stop at a
  hole's keep-out, and a piece that ends there is not a rib. A grid's ribs cannot end on each other
  yet, only on what they run between, so round holes a grid comes apart instead of closing on its
  own crossings.
- **Only named supports count at both ends.** Name two faces and spokes that reach any other wall
  are dropped, reported as ending on something not named, with what.
- **Bosses and bores are not yet required to go round.** Holes are; convex cylinders are still all
  bosses, and 216 on the housing are mostly rounded wall corners and edge rounds. What spokes turn
  about leaves those out; the CAD tab still lists them.
- **Bulges, boss transitions and ribs the part already has** are not yet kinds of block.
- **Nothing after the field.** No meshing, simulation, dataset, surrogate, search or verification:
  nothing ranks designs but their geometry and mass.

Size: 47 Python files, ~21,600 lines; 21 TypeScript files, ~7,200 lines; 8 skills. Tests are kept
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
| a block read off the part | under a second |
| where ten blocks' ribs and holes would go, drawn, once the part is open | about 1 s |
| a campaign, each of ten blocks alone: up to 1,000 of each block's points kept | 5 minutes |
| a campaign, together: a design of ten blocks placed and screened | about 60 ms; 4,000 kept of 4,022 tried |
| a campaign of 8 designs from the ten blocks, launched in the interface | 16 s |
| the 20 of 4,000 that differ most | 1.7 s, once |
| a design of the ten blocks built at preview - its field, surfaces and cells, checked, kept | 6 to 16 minutes the first time; 80 s once its windows are kept |
| a preview design from the study: five blocks, 28 ribs, once the part is open | about 1 minute |
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

Placement - ribs as spans between supports, height following them, no trimming on the grid - does
not have the first two. Mould release is still as strict.

## Next

**Now, to be chosen between:** mould release that knows cores form the pockets inside a casting - the
one check every design built on the housing fails, so nothing built can come out green until it is
right - or CP-SAT choosing and repairing combinations. Then meshing, the M of a design's stages, on
some twenty of those that differ most.

The steps in [build-plan.md](build-plan.md), each keeping every earlier study reproducing its
designs:

1. The study - the document, entities by fingerprint, constraints with strength and source,
   interfaces closed by default, Design a variant as its view, built by hand
2. Candidates and conflicts
3. Choosing (CP-SAT) and repairing combinations, and kill counts - sizing (Sobol), screening and the
   archive run
4. The model on the study, and the requirement suite
5. Choosing what to show - about 20 representatives - and objections that become rules
6. The general rib - webs between any anchors, the pull direction, taper and T sections
7. An unseen housing, with no code changed
8. Speed - 4,000 designs built overnight; placed and screened, they take a quarter of an hour
9. Simulate and Learn
10. The next kinds of feature - faces moved, holes, material and pads run; bulges, boss
    transitions, existing ribs, pockets to come

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
| The study | the source of truth, one file per study in `studies/` with every version: blocks (what to add - ribs, faces to thicken, holes, the material - where, free settings with ranges and sources), constraints (hard, assumed or learned, with their source), preferences, objectives, the pull direction, the target and seed - in named entities bound by fingerprint, citing the engineer's words, selections and what they did on the card; a rule nothing enforces yet is kept and listed. Written only when the engineer accepts the draft they built by hand or the agent wrote from their words; generation reads only it |
| What is unstated | explored within ranges read from the part and the drawing, and listed as assumed; asked first only when every design would otherwise be invalid |
| Where ribs go | where the study says - faces to stand on, anchors, regions to keep away from; the system proposes named regions when the client does not point |
| A rib | a web between two or more anchors, a floor optional; section, plane and pull direction from the study |
| Layouts | proposers - parallel, grids, spokes, a free proposer - never limits unless the engineer says so; designs described by properties, not by proposer |
| The interface | five tabs - Drawing, CAD, Generate, Learn, Optimize - every one shown built or not; the agent above them all; Generate is Campaign and Designs |
| Design a variant | on the CAD tab: the one structured view of the study - the draft of its next version, read back from it - and the way it is built by hand: blocks added from the faces selected, entities taken from the selection, every setting fixed, ranged, narrowed or handed back where it shows, clearances, rules kept or taken out, blocks taken out; each the engineer's own and said in words in the study; block by block, what its ribs stand on, end on and keep clear of, each entity a chip, then its settings and rules, each with what the study makes of it and whose it is; marked where the draft changes; nothing written until accepted; one variant made at a time |
| Kinds of block | ribs and webs; faces moved along their normal - walls, plates, bosses; holes through a plate on a lattice; the material, one to a part and never varied - what varies is local, the sections blocks add, move and cut. Built in one order - faces moved, then ribs and pads, then holes - with rules across kinds |
| Design knowledge | data with its sources, in `knowledge/materials.json`: the rules campaigns screen with - rib to wall 0.8, root gap 2 thicknesses, a hole's ligament one plate thickness, a least wall 8 mm - and six casting materials, each with density, stiffness, strength and least wall from its standard |
| Pads | on unless the engineer says otherwise: a wall too thin for a rib is padded round its end, a floor too thin for its ribs thickened for them, never either to more than twice itself; off, the rib is left out or the design screened out |
| Campaigns | as many designs as asked: each block's settings alone first, then combined, placed together and screened; alike designs kept once; every design kept in `_archived_designs/<project>/<run>/` with all it is made of, beside the study version and the switches the run used. Everything the pipeline runs is shown, and any block, rule or check can be switched off for one campaign; the interfaces never |
| A design's stages | P paths, F field, M mesh, S setup, R results, each shown with how it came out; every design's paths kept with its run, so any one is drawn at once; a built field kept beside its run |
| What is held as it is | the part's interfaces, closed whatever a campaign switches off; each feature a block keeps clear of, as far as its own clearance - one a rib must only not cross, not at all |
| Rib ends | a rib ends on what it meets, buried in it, or stops at least the root gap short of any metal ahead - never a finger of sand between |
| The model | writes the study's draft from words and clicks - its only way to change the study - composing a few general tools as skills say, never a tool made for one kind of request; asks what blocks everything, explains failures, turns objections into rules; says only what needs the engineer's attention, never what the card shows; never makes geometry, never a call per design, never scripted to an example; sees names and numbers, never CAD files; provider is a setting |
| Saying it once | the card shows what the study holds; the agent's answer only the few lines it asks the engineer to look at |
| Objections | a stated reason becomes a rule the engineer confirms; a reason-less rejection only makes similar designs rarer, visibly |
| Variety | every free setting has a step; the designs shown are spread across their properties; the count of different designs is reported, not forced |
| Learning | within a study; within a client only if it opts in; never across clients |
| Judged by | the share of shown designs an engineer accepts - 70% by the third round on the housing - and a suite of 30 or more varied requirements plus a second part, run on every change |
| Simulation | Code_Aster, the same design twice agreeing within 0.1%, and analysis on the distance field; results kept apart, never folded into one number |
| Agent stack | kept in `agent/`: LangChain agent loop on LangGraph, OpenRouter (DeepSeek by default), LangSmith; conversation and checkpoints in SQLite with the project; credentials from the environment |
| Constraints and checks | constraints enforced and verified; checks are code, tested against failing parts, thresholds from the spec, basis shown. A model may add constraints, never checks |
| The part's own rules | rib section, root fillet, edge round, fillet floor: no default; set per part |
| Fidelity | preview on a coarser grid with nothing else relaxed - every preview of a study on the grid its designs are placed on; accept only at full |
| Tessellation | OCC `BRepMesh`, chord tolerance derived from the model |
| `cadquery-ocp` | pinned at 7.9.3.1.1; 8.x ships an unsigned binary Smart App Control blocked. Smart App Control is off on the build machine; 8.x is untested |
| SciPy | all of it loads, `scipy.stats.qmc` included: Sobol sampling is available |
| Constraint solver | OR-Tools CP-SAT, to choose and repair rib and hole combinations and to name the assumed rules that make a request impossible - not yet built |
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
