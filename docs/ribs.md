# Ribs: a design space from the engineer's words

**Being built.** How an engineer gets thousands of near-production rib designs that satisfy what they
asked for, with solver decks, and how what they object to narrows the next batch. This file is the
design as agreed; [status.md](status.md) says how much of it runs.

---

## What it is for

Generative design in CAD tools gives a handful of optimal shapes per setup, which someone then
redraws. ZenryxAI gives thousands of near-production variants that already follow the engineer's
rules, with solver decks. A surrogate trained on them finds clusters of designs that do well on
several objectives at once - each a real, castable design - and shows which choices matter for the
next design.

One engine serves four kinds of user: CAE teams who need variants and decks for a study, teams who
need training data for surrogate models, design engineers who want ribs suggested and modelled, and
foundries who want reinforcement that casts.

The engineer brings a structure without the ribs - its CAD as a plain STEP, its drawing, later its
solver deck. There is **no finished version of the part to compare against**: where ribs go comes
from what the engineer asks for, never from another CAD file, and the system never "corrects" the
engineer's part.

1. **Extract** names what the part holds - faces, planar groups, holes, bosses, bores, walls,
   fillets - and what the drawing controls.
2. **Say what you want**, in words, clicks on the part, or both: *"ribs between the bearing boss and
   the outer wall, clear of the holes, no taller than the boss"*. A model writes it into the draft
   of the **study**, in the part's named entities, shown on the study card; it asks only what blocks
   every design, and the engineer accepts what it wrote.
3. **Screen.** Proposers lay out candidate designs across what the study leaves free; each is
   placed and checked against the rules in seconds.
4. **Build and review.** A varied set is built and shown; the rest build in the background.
5. **Object.** The engineer rejects what they do not want and says why; the reason becomes a rule,
   and the next batch obeys it.
6. **Simulate and learn.** Every design comes with its deck; the results train a surrogate that
   searches the same space for designs that do well on several objectives.

## The study is the one source of truth

A study is one document in the part's named entities, written from words and clicks, versioned, and
citing what the engineer said and selected:

```
Add:        ribs
Where:      on face:1201, face:1543 · between the walls round them and boss face:1453
Free:       count 4–16 · any angle · spacing 60–200 mm · thickness 9–15 mm · straight or tapered
Must:       5 mm clear of holes on face:1201, face:1543 · no taller than the support at each end
            · R ≥ 3 (drawing p.1) · draft ≥ 1° along +z
Prefer:     symmetric about the bore axis
Objective:  least added mass (geometric) · most stiffness at the bearings (once simulated)
Assumed:    pull +z · ribs may enter the bearing region (nothing said)
```

- **Add** - which kind of feature, one block per group of them; a study may have several.
- **Where** - the named entities features may stand on, run between or attach to, and the regions
  they keep away from.
- **Free** - what designs vary over, each a range with a step, suggested from the part and the
  drawing and citing where from. A setting locked to one value is fixed.
- **Must** - rules every design satisfies: generated to them, verified on the result. Each has a
  strength and a source: *hard* - the engineer or the drawing said it; *assumed* - a default the
  system took, the only kind it may offer to relax; *learned* - from a rejection the engineer
  confirmed. A rule no tool can check yet says so, and is never dropped.
- **Prefer** - what makes a design better, not required.
- **Objective** - what "better" means: geometric until designs are simulated, physical after, and
  never folded into one number.
- **Assumed** - every freedom taken because nothing was said, with its range, to confirm, lock or
  narrow.

Generation reads only the study, so the same study always gives the same designs and a campaign can
run again months later. **Every change is a new version**, with what changed and why. Designs made
under an earlier version are rechecked against the new one; those that now break a rule are hidden
with the rule named, not deleted.

**Features are named by id and fingerprint** - kind, size, position - so that when the CAD is read
again and numbers shift, the study still finds the right faces, or says plainly that it cannot.

**Where it lives.** One file per study, `<project>/studies/<name>.json`, holding every version;
`project.json` names the active one. Today's spec - the engineer's words, placements, rules and
levers - is the study's first form: its levers are ranges already, and a design made from a study
is a spec for one point in it.

## What the engineer does not say is explored

Anything the study leaves unstated varies within a range read from the part and the drawing, and is
listed under **Assumed** beside the results: *"height varies from 30% to all of the support at each
end; say if it should be fixed"*. The engineer locks or narrows it after seeing designs. The system
asks first only when a gap would make every design invalid or meaningless - the pull direction of a
casting, words that name no region.

What is selected is the scope. Ribs on `face:1201` alone stay there; select both halves of the
ceiling and they may go anywhere on both; say *"keep away from the bearing region"* and they do; say
nothing and they may go there. Whether ribs may span both faces, stay within one, or must bridge
them is a setting of its own - three different design spaces.

**Interfaces are the exception: closed unless allowed.** Bearing bores, holes with room above them
for the tool, datums and machined faces are forbidden by default, each citing where it is known
from - the drawing's toleranced dimensions and notes, or the geometry. A datum the drawing names but
the system cannot yet place on a face is shown for the engineer to point at. Forbidding a bore
forbids its bearing surface, not the boss round it.

## One kind of rib: a web between anchors

Every rib is a **web** - a thin plate in a plane - attached to two or more **anchors**, which can be
any named entity: a floor, a wall, a boss, a ring. It grows until it meets the part and is cut back
by the rules - a height limit, keep-outs. A floor rib is a web with a floor along its bottom edge; a
hanging rib, between a ring and a wall with nothing under it, is anchored at its ends; a gusset is
anchored along two edges. None needs a class of its own.

Its **section** is its thickness, a taper along its height or its length, a T or L flange, draft, a
root fillet where it meets an anchor, and an edge round on its free edges. Its **plane** is set by
the study or left free: *"parallel to YZ"*, *"vertical in XZ"*, *"square to face:723"*, *"radial
about face:1453"*. **Which way it leaves the mould** - the pull direction - is in the study, never
assumed from a floor.

## Proposers, never limits

A layout is a **graph**: anchors on named entities, joined by ribs. Spokes are a star, a grid a
lattice, triangles a triangulated graph - shapes of graph, not classes. **Proposers** - parallel
ribs, grids, spokes about a boss, and a free proposer that joins any two anchors - carry weights, so
the structure production ribs have - even spacing, lined up with walls, joining stiff points - is
likely, not required. A grid is one lattice: its families share a spacing and an origin, so they
cross at common points. A pattern is a limit only when the engineer makes it one: *"a triangle grid
only"*.

**A solver chooses the combinations.** Candidate ribs are laid between anchors and each is tested
against every rule about one rib; conflicts between pairs - too close, crossing in an X, meeting at
a sharp angle - are computed once, at the thickest a rib may be. A constraint solver (CP-SAT) then
picks sets of ribs that satisfy every rule about combinations at once - how many, where, what they
tie together - with a random objective each time for variety. Foundry practice enters as assumed
rules: no X-crossings, since foundries stagger them into T-junctions; ribs meeting at least 30°
apart; a rib's plane containing the pull direction, so nothing undercuts. When nothing fits, the
solver names the assumed rules to blame, and the model explains them.

Designs are described by what they are, not by which proposer made them: how many ribs, the angles
between them, their spacing, how much of each region they cover, what each connects, the mass they
add. Variety, feedback and the surrogate all work on those properties. *"Sixty degrees between
ribs"* is a property; a triangle grid is one way to get it.

## Where ribs may go

The client may point - *"here and here"* - or leave it open. The system proposes **regions** where
ribs could go - every floor, every bay between walls, the space round every boss - named and shown on
the part, so the engineer picks some or says *"anywhere except the bearing region"*, and rules can
refer to them.

## Screening, building, checking

Cheapest first:

1. **Screening**, seconds a design: placement, and every check that needs no geometry - the
   engineer's rules, thickness, gaps between ribs, the draft part of mould release.
2. **Building**, minutes a design: the part and its ribs as a distance field, a closed surface, and
   the checks on geometry - fillets achieved, thick spots, nothing floating, protected areas
   unchanged.
3. **Simulation**: the decks solved.

A **preview** builds a design on a coarser grid, nothing else relaxed, and is always labelled one; a
**full** design is built at the design grid, and only a full design can be accepted.

Every design comes with a **verdict** in two parts, and every rule and check applied is listed, so
it can be audited. **Your rules**, each enforced while the design is built and verified on the
result: *"keep out - pass, nearest hole edge 7.2 mm."* **Engineering checks**, which the platform
holds every rib to whether or not anyone asked: the fillet achieved, thickness against the wall,
mould release, thick spots at junctions, gaps between ribs, nothing floating, protected areas
unchanged, the surface closed. Thresholds come from the study; any the engineer did not set is
marked assumed. A check is code, shown to fail on a part built to make it fail before it is trusted,
and added between sessions - never by a model at runtime. A model that could write its own checks
could write one that passes everything.

## Variety

Every free setting has a **step**, so a spacing of 100 mm and one of 101 mm are one design, not two,
and two designs count as different only when they differ by at least a set number of ribs. Five to
ten times too many designs are made, and the most spread out are kept, in a space of properties -
rib count, total length, which entities are tied, orientations, added mass. If the rules leave fewer
truly different designs than were asked for, the system says how many: the count is a result, not a
target.

Every design's margin against every constraint is kept, so any proposed rule shows at once how many
designs it would remove - its **kill count**.

## Review, and objections that become rules

The engineer sees about 20 designs a round - the most representative of the kept set - each with a
picture, what it is, the assumptions it used, and accept or reject, and any design on the part with
its verdict. The thousands behind them are the surrogate's training set; nobody browses them.

**Rejecting asks why, and where.** The engineer points at the rib they object to, or picks between
two designs that differ in one thing - which pins the reason down in far fewer questions than a yes
or no on whole designs. The model offers one to three readings as rules in named entities - *"no rib
within 30 mm of face:1453"*, *"ribs parallel to XZ only"*, *"spacing at least 120 mm"* - each with
its kill count, and the engineer confirms one. The study gets a new version, the designs made so far
are rechecked at once, and the sampler refills. A rejection without a reason only makes similar
designs rarer, visibly; it never becomes a hidden rule. Every rule can be relaxed or removed later.
Designs rejected for taste still go to the solver: physics does not care what anyone likes.

**What is learned** stays within a study - which settings fail, so less sampling is wasted; which
checks keep failing for one cause, which become rules at an earlier stage. Making a learned rule
one for a family of parts or a company is a deliberate act; if a client opts in, it stays within
that client. Never across clients.

## Where the model sits

- **Before a batch** it turns words, clicks, the drawing and the extraction into the study - every
  entity it names checked to exist, every rule it writes checkable or flagged - asks the few
  questions that block everything, splits *"ribs here and here"* into groups, and chooses proposers
  and ranges.
- **After a batch** it explains what failed - *"most triangle layouts fail at the holes on
  face:1543; spacing over 140 mm avoids them"* - and turns objections into rules.
- **Code** proposes, builds and checks designs, samples, and picks the varied set shown.
- **Never** the model computing geometry, and never a model call per design: four thousand designs
  are a workflow with a handful of model decisions in it.

It is one agent with **a few general tools**, each doing one job, and it composes them:

- **find** entities - by kind, by what they touch, by which way they face, by the axis they turn
  about - or the part's axes and what is on each;
- **describe** entities - what each is, and how several stand to each other;
- **relate** an entity to the part - what it stands on, what rises round a floor, what is round a
  face, what shares its axis, what lies across the open space in front of it - or several
  together: what lies between them, under and over;
- **measure** an entity - how far it reaches along a direction, how thick the metal is under it;
- **search the drawing** for its words;
- **read and edit the study** - the only way to change it. An edit comes back with where each
  block's ribs would go, counted, so the agent sees its reading makes ribs before the engineer does.

**Skills** say how to compose them for a kind of request - ribs round a round thing, on a face,
between things; keeping clear of anything; rules from words; sections; naming things; refining turn
by turn. The agent reads one when a request is of its kind. Skills, like the prompt, hold no ids, no
numbers and no example sentences. No tool is made for one kind of request: a new kind is a new
skill composing the same tools, or a new general tool if a job is missing. A decision the part can
settle - whether anything lies under the space between two things - belongs in a tool that
computes it, not in a skill that tells the model how to guess it.

What the agent changes shows on the study card, marked, for the engineer to accept or undo. Its own
words are the few lines it asks the engineer to look at - a question that blocks, an assumption
that matters, a rule nothing enforces yet - never what the card already shows; they stand until it
gives them again or clears them, and every edit shows them back to it to check they still hold. It
quotes the engineer's words exactly, every number it gives comes from a tool that measured it, and
it is never scripted to an example sentence. It sees the study and summaries of named entities -
names and numbers - never CAD files or meshes, and the provider can be changed: a client's approved
one, or a local model.

**Where words are worth more than a form.** A request that names what it means by id - a face, a
number - is better as a click or a stepper on the card: faster, exact, the same every time. Words
earn their place where no form reaches:

- **documents** - drawings, requirement specs, load cases, standards - read into cited rules,
  objectives and loads, which code then checks;
- **objections** at review - *"too close to the bolt bosses"*, *"nothing over the drain"* - read
  into candidate rules, each with its kill count;
- **explanation** over hundreds of designs - why a block makes one rib, why designs fail a check,
  what the best of them share;
- **a brief** - *"a tenth less mass, bearings as stiff, thinner side panels, ribs on the covers,
  cast iron or ductile iron"* - read into a study of several kinds of feature, materials and
  objectives, for the engineer to edit;
- **things named by what they are for** - *"every bearing boss of the intermediate stage"*.

**What the model must know.** It can reason only about what its tools answer, and today they
answer geometry: which wall a word means is several questions and minutes of reasoning, afresh each
time. Two bodies of knowledge would make the answers engineering:

- **A model of the part's regions and what they are for**: bearing seats by shaft and stage, the
  plates that carry them, outer and inner walls, split and mounting flanges, covers, compartments,
  bolt patterns, sealing faces and clearance envelopes - with their relations worked out once: what
  stands on what, what faces what across open space, what has nothing under it. Computed from the
  geometry and the drawing's labels, proposed by the model where they cannot be computed, and
  approved by the engineer, its names are the ones the study, the card, the agent and the
  simulation's result regions all use. With it, *"the wall"* is looked up, not searched for.
- **Design knowledge as data**: casting and rib rules, a materials catalogue, and each kind of
  feature's ranges, each with its source - read by the code that fills a block, cited by the agent,
  changed by the engineer.

With them go the loads, operating points and targets in the project's documents, and what earlier
studies decided.

## Objectives, physics and learning

Until designs are simulated, objectives only rank and filter - added mass, rib volume, coverage,
symmetry - and are labelled geometric; no design is called optimal without physics. The physical
objectives are recorded in the study for when it is.

Simulation runs two ways: the Code_Aster pipeline the housing was solved with before, gated so that
the same design solved twice agrees within 0.1% - mesh noise once made its top eight designs
indistinguishable - and analysis directly on the distance field, which needs no mesh, checked
against Code_Aster. Results are kept apart - bearing-seat tilt, stiffness, stress, mass, then natural
frequencies - so the surrogate learns several objectives. A design the surrogate recommends is solved
for real before it is called good, and that result joins the data.

## What comes out

For every design: its mesh, its solver deck, a row of its settings and properties, and a **recipe** -
its anchors, plane and section in words and numbers - from which anyone can rebuild it. A STEP solid
of the part with its ribs follows, then native CAD features when a customer needs them.

A campaign of 4,000 designs - the surrogate's training set - runs overnight on one workstation:
every candidate screened, the representatives built first, the rest in the background. Every one of
them must build, mesh and solve, so what keeps a design robust is a hard rule, not a hope.

## How it is judged

- **Acceptance** - the share of the designs shown that an engineer accepts, tracked per round of
  objections: at least 70% by the third round on the housing. Judged by the engineer building it
  for now, and by an engineer at the client for the demo.
- **Generality** - a suite of at least 30 varied requirements on the housing - different regions;
  floor, hanging and gusset ribs; orientations; height, spacing and keep-away rules; tapered and T
  sections - with the client's own, and a second cast part. A requirement passes when the study
  written from it is right and every design it yields follows every rule. The suite runs on every
  change; nothing is fixed for one case.

## The study card

The study card is the one structured view of the study: the draft of its next version, read back
from the study when the project opens. It is written from the engineer's words by the agent; the
engineer accepts it or undoes it.

**Each block is its entities.** What its ribs **stand on** - a floor, as faces or features in one
plane, or nothing, for webs that hang between what they join. What they **end on** - named, or read
off the part: what rises round the floor. What they **keep clear of** - any entity: a face, a boss,
the holes found, each one listed; the ribs of another block, named like any entity as `ribs:` and
the block. Each is a chip that shows it on the part, and each says whose it is - the engineer's
words, the part's suggestion, the drawing. As the engineer says more, entities are added to a block,
or a new block is started: "without interfering with the ribs already there" adds every earlier
block's ribs to what the new one keeps clear of, and a design places those blocks first. Another
block's ribs are in the way only where they stand at the same height: ribs on a ceiling are no
obstacle to webs far below it.

A rule about the ribs of one block belongs to that block - "these ribs must not cross face:1417" -
and a rule about every rib belongs to the study, after the blocks - the drawing's smallest radius.

Then the block's **settings** - pattern, what spokes turn about, angle, how many, thickness, radii,
draft, height, section - each fixed, or what it may vary over and who suggested that; and its
**rules**, each hard, assumed or learned, and whether anything enforces it yet. What a block still
needs from the engineer, and what cannot be built yet, stays on it. After the blocks: rules for every
block, what makes a design better, the pull direction, how many designs, and the part's interfaces,
closed by the platform.

**What the draft changes is marked**; **Accept** writes it as the next version, checked as any
version is, and **Undo** reads it back as the study has it. Nothing is written until then. A design
is made from the study, never from the draft: making one accepts the draft first.

**It draws where ribs would go before anything is made.** "Show paths" draws every line each block's
layout lays across its floor - never past it - or across the open space between what its webs join,
cut into pieces by what it keeps clear of and by gaps, each piece coloured by what becomes of it: a
rib, stopped by something to keep clear of, ending at an edge with nothing to meet, ending on
something not named (which it names), ending on one thing at both ends, too close to another of its
spokes, too short, or no room for its height. The words count lines, pieces and what each piece
became, so the numbers add up.

**Go** makes many designs at once: the draft accepted if it differs, then points spread over what
every block leaves free - the suggested point first - each placed on the part and counted in
seconds, listed as it is done; designs whose ribs all fall in the same places are made once. A click
draws one on the part; Make builds it and checks it.

## What is read off the part for ribs on a floor

For a block standing on a floor, everything the words leave open is read off the part, round what
they gave - or a default that says it is one:

| what | read off the part as |
|---|---|
| what they end on | what stands up round the floor, past any fillet or chamfer at its foot, on the side ribs stand - each wall, boss or bore once |
| keep clear of | every hole through the floor, 5 mm clear, listed and suggested; the engineer's own distance replaces it |
| pattern | every pattern the floor allows - parallel, square grid, triangle grid, spokes - suggesting spokes about the largest boss or bore the floor goes round more than halfway, else a square grid |
| what spokes turn about | the bosses and bores standing round the floor, largest first |
| orientation | set out from the longest wall round the floor: a grid along it, parallel ribs square to it; spokes fan across the floor, or go all the way round |
| how many | 4 to 16 ribs, or 5 to 16 thicknesses apart |
| how tall | each end as tall as what it meets, the top sloping between; half to all of that |
| thickness | 0.6 to 1.0 of the plate they stand on, measured through it |
| root fillet, edge round | from the smallest radius the part allows up to half the thickness |
| draft | half a degree to three |
| section | flat, unless the words ask for a T; a T's flange 2 to 4 times the web wide |
| smallest radius | the drawing's note, cited by page and text |

## What is read off the part for webs with nothing under them

For a block that stands on nothing, the webs join what it ends on - two things or more - and the
rest is read off what they join:

| what | read off the part as |
|---|---|
| which way they stand | the direction the most of what they join runs along - the axis of a round one, the line two flat ones meet along, else one of the part's own axes - the pull first among equals |
| from where to where | from the level where the most of them are present, up to where the first of those stops: every web meets all of them; the others take no part, and the card says so |
| where they may go | the open space between them at those heights - where the part is not, in the pieces of open space that reach two of them or more |
| pattern | spokes about the round thing among them - a boss before a bore - or straight webs; both stay open |
| orientation | spokes fanned across the others than what they turn about; straight webs square to the largest flat one, laid across where two of them face each other |
| how many | 2 to 12 webs, or 5 to 16 thicknesses apart |
| how tall | level with the lower end, or sloping; half to all of it; never into what stands over them |
| thickness | 0.6 to 1.0 of the thinnest of what they join, measured through it |
| root fillet, edge round, draft | as for ribs on a floor |

Each web runs from one of them to another - never from one to itself - and is buried in both. Spokes
may meet at their roots, but one that would run into another past them is left out.

## Beyond ribs

The recipe that makes ribs makes other variations: a kind of block - where it goes, what may vary,
its rules - a way to build it on the distance field, its checks, and what is read off the part for
it. The kinds after ribs:

| kind | where | what varies | built as | checked for |
|---|---|---|---|---|
| wall offset | a panel of faces | how far it moves along its normal, how it blends into what is round it | the selection's weight in the field, times the offset | the wall left thick enough; protected faces unchanged |
| bulge or crown | a panel | how high, where, how wide | the same weight, times a smooth bump | draft; clearance envelopes kept |
| boss transition | a boss and the floor it rises from | the transition radius, the boss's wall | a local growth and fillet at its foot | the bore unchanged; thick spots |
| hole pattern | a plate or web | count, diameter, spacing, edge distance | cylinders cut away | ligaments wide enough; clear of ribs and bolts |
| existing rib | a rib the part already has | its height and thickness, scaled | its region offset | as for ribs |
| material | the study | a choice among those permitted | not geometry: a property of every design | castability; allowables |

Blocks are built in one order - what changes the shape (offsets, bulges, transitions), then what
adds to it (ribs, webs), then what cuts it (holes), then fillets - and rules run across kinds: holes
keep clear of ribs, ribs are sized from the wall as offset. A customer's own part, ribs and all, is
a baseline to vary like any other - never a reference to match.

**Three generations of variation.** Same-shape changes to what the part already has - offsets,
bulges, transitions, existing ribs - are the most often valid, and come first. Features from
templates - ribs, webs, holes - change the part's topology within rules. Free exploration on the
field changes it further, and a design found there is rebuilt as features only when it is worth it.

**How variants are made.** The study holds every block. Go samples them together - continuous
settings spread evenly, choices balanced - checks each design cheapest first, makes alike designs
once, keeps the most spread out, and records every margin, so a proposed rule shows its kill count
before it is confirmed. A chosen few are then meshed and solved, a surrogate learns from them, the
search runs on the surrogate, and the best are solved for real before anyone calls them good.

## Reading the part

Everything a block and the proposers start from is read off the part by code, in one pass:

- **Holes go round.** A hole is a small concave cylinder or cone - with the cones that chamfer or
  countersink it - whose faces go more than 200° round their axis. A fillet in a square corner is a
  small concave cylinder too, and goes a quarter of the way: it is a fillet, not a hole. A cast
  hole with draft, all cone and no cylinder, is a hole.
- **What rises round a host** is found by walking out from its edges across blends - fillets of any
  shape, rounds, chamfers - to the first faces that stand up at least 45°: walls, bosses, bores.
  Only on the side ribs stand on, so past the round on a floor's outer edge is not a wall; never
  through a hole.
- **What spokes turn about** is a boss or a bore: something round standing square to the host that
  goes a good way round its axis, with the rest of it if the CAD split it in pieces - a corner
  fillet or a rounded wall corner never does. It is looked for among everything standing round the
  host, named to run between or not. Spokes are suggested by themselves only when the host goes round
  more than half of one; asked for spokes, it takes the largest, and lists the rest.
- **Which wall straight ribs are set out from** is the longest flat face standing round the host,
  measured along it.
- **How tall a rib can stand at an end** is measured on the metal its end is buried in, at every
  depth it could be buried to, so a wall with draft is met as tall as it stands.
- **The plate's thickness** is measured by a ray through it, from the largest facet of the host.
- **What lies across the open space from an entity** is found by rays from points spread over its
  faces, straight out of its metal: the first things they meet, each with the share of the entity
  that looks at it and the gap - the wall a web from it would reach.
- **What lies between things** is found from points halfway across the space where they face each
  other, at the heights they share: rays straight down and up say what is under and over that
  space and how far past where they begin or end - a floor at their foot to stand on, or open
  space, and webs with nothing under them. When metal fills the space - two faces of one piece -
  it says so.
- **The smallest radius** is the drawing's own note, found by its text and cited with it.

## Seeing, naming and selecting faces

Hovering a face on any 3D tab shows a small card with its one name, `face:N` - which the study takes
wherever it takes a feature - and its type, area, which way it faces or its axis,
diameter, height, and whether a drawing controls it. Clicking pins the card.

**Selecting is how faces get into the study.** A click selects a face; a Ctrl-click adds one or
takes it out. The **grow** angle spreads a click across every edge shallower than it - and belongs
to that click alone: the stage lists the clicks, the grow control acts on the last one or whichever
is picked, and a face clicked after growing another starts ungrown. Lowering an angle takes faces
back out. Selections are highlighted in a colour no design uses.

## Build order

[build-plan.md](build-plan.md) has the steps and what shows each done: the study; candidates and
conflicts; choosing, sizing, screening and the archive; the model on the study; choosing what to
show, and objections; the general rib; an unseen housing; speed; Simulate and Learn; the next kinds
of feature.
