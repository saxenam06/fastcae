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
   the outer wall, clear of the holes, no taller than the boss"*. A model writes it into the
   **study**, in the part's named entities, and asks only what blocks every design.
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

It is one agent with tools over the study, and its edits show as marked changes the engineer accepts
or undoes. It quotes the engineer's words exactly, every number it gives comes from a tool that
measured it, and it is never scripted to an example sentence. It sees the study and summaries of
named entities - names and numbers - never CAD files or meshes, and the provider can be changed: a
client's approved one, or a local model.

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

## The card

The rib card is how one **Add: ribs** block is edited by hand, and it needs no model: what is typed
into a slot is read by code, and what code cannot read is kept exactly as typed and flagged, never
guessed. Started from the faces selected, it fills every slot a group of ribs needs - from the
selection, the part and the drawing, or with a default that says it is one:

| slot | the engineer sets | otherwise |
|---|---|---|
| where ribs stand | faces, selected | the flat area the rest of the selection rises from, with every other selected flat face in its plane - not merely the largest |
| what they run between | faces, selected or named | the other faces selected that stand up from the host; with none, what stands up round the host, past any fillet or chamfer at its foot, on the side ribs stand |
| keep clear of | the faces whose holes to avoid, a clearance - or none | every hole through where ribs stand, 5 mm clear, listed |
| pattern | parallel, square grid, triangle grid, spokes - and for spokes, what they turn about, picked from the bosses and bores standing round the host, largest first, and whether they fan across where ribs stand or go all the way round | spokes about the largest boss or bore standing in the host with the host round more than half of it; else a square grid. Asked for spokes, the largest boss or bore there is. Spokes fan across the host, so a count is ribs there - unless turned by an angle or a face, which needs them all the way round |
| orientation | an angle - or a face to run along or square to, or for spokes, to point the first one toward | set out from the longest wall round the host: a grid along it, parallel ribs square to it, running out from it; spokes fan, needing none. With no wall, the host's longest direction, and a number says which way 0° points |
| how many | a count, or a spacing | 8 spokes, or a pitch of 8 thicknesses |
| how tall | a height, faces to stay below, and whether the top slopes or is level | each end as tall as what it meets, the top sloping between |
| thickness | a value | 0.8 of the plate they stand on, measured through it |
| root fillet | a radius | half the thickness, not below the smallest radius |
| edge round | a radius, or none | the smallest radius |
| draft | an angle | 1° |
| smallest radius | a radius | the drawing's note, cited by page and text |

**Every slot says where its value came from** - *you*, *selected*, *drawing*, *measured*, *default*
or *needed* - and each is set in place:

- **faces** are chips, one per face, by the name the hover card shows. A click shows it on the part;
  its cross takes it out. The faces selected now can be added, or put in place of them. A slot the
  engineer has not set shows what the part gave, and editing starts from that.
- **numbers** have steppers and their unit; **choices** - the pattern, radii from a standard series,
  draft angles, a rib's top, how spokes spread, what they turn about - are lists. A face picked
  from a list is shown on the part as it is picked. Blank clears a value that may be left out.
- **words** can be typed into any slot, starting from what it holds, with the faces selected put in
  where the cursor is: *"holes on face:1201, 8 mm clear"*, *"spokes about face:1453"*, *"no taller
  than face:1453"*. Faces show as chips in the words too.
- **reset** forgets what the engineer set in a slot, and the part and the drawing fill it again.

**The card draws where ribs would go before anything is made.** "Show paths" draws every line its
layout lays across where ribs stand - never past it - cut into pieces by holes and gaps, each piece
coloured by what becomes of it: a rib, stopped by something to keep clear of, ending at an edge with
nothing to meet, ending on something not named (which it names, to be added), too short, or no room
for its height. The words count lines, pieces and what each piece became, so the numbers add up:
*"18 lines cross where ribs stand, cut into 37 pieces: 13 ribs, 16 stopped by something to keep
clear of, …"*. It redraws as the card changes, in seconds once the part is open at the preview grid.

**The card says what is wrong, as it goes.** A face that is not on the part, a host that is not one
plane, a face both stood on and run between, a face to run between that does not stand up from the
host, spokes with nothing to turn about, ribs closer than their own thickness, a height limit - a
number, or a face to stay below - that leaves no room for a rib taller than its root fillet, a radius
below the smallest the part allows, an edge round more than half the rib, words it could not read.
The card is **ready** when nothing is needed and nothing is wrong, and only then makes designs.

**What the engineer set is kept in their terms.** Each slot they set is one line - their words as
typed, or the value they picked - and those lines and the faces they selected are what the study
quotes and cites. What the part, the drawing or a default filled goes in as measured references,
unconfirmed.

## Reading the part

Everything the card and the proposers start from is read off the part by code, in one pass:

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
  host, named to run between or not. The card chooses spokes by itself only when the host goes round
  more than half of one; asked for spokes, it takes the largest, and lists the rest.
- **Which wall straight ribs are set out from** is the longest flat face standing round the host,
  measured along it.
- **How tall a rib can stand at an end** is measured on the metal its end is buried in, at every
  depth it could be buried to, so a wall with draft is met as tall as it stands.
- **The plate's thickness** is measured by a ray through it, from the largest facet of the host.
- **The smallest radius** is the drawing's own note, found by its text and cited with it.

## Seeing, naming and selecting faces

Hovering a face on any 3D tab shows a small card with its one name, `face:N` - which the study and
the card take wherever they take a feature - and its type, area, which way it faces or its axis,
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
