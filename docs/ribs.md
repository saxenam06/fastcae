# Ribs from intent

**Being built.** How an engineer explores ways to add ribs to a structure: select where on the part,
say what they want on a card, and see the designs that follow. This file is the design as currently
agreed; [status.md](status.md) says how much of it runs.

---

## What it is for

An engineer brings a structure that has no ribs yet - its CAD, and its drawings if they have them -
and wants to see the different ways ribs could be added to it, and later how each affects the
results. The platform generates the designs, simulates them, learns from the results, and optimises
toward the engineer's objectives, which in turn steers which designs are sampled next. This file is
about the first step of that loop: turning intent into designs.

1. **Extract.** The platform reads the files and names what it finds: planar groups, bores, bosses,
   holes, fillets, and what the drawing controls.
2. **Select where.** The engineer selects faces on the part - a click, a Ctrl-click to add or take
   one out, and a grow angle that belongs to each click.
3. **The card.** Started from the selection, the rib card fills every slot a group of ribs needs:
   from the selection, the part and the drawing, or with a default that says it is one. The
   engineer sets anything it has wrong on the card itself - faces, values from steppers and lists,
   or words with faces in them.
4. **Designs.** When nothing on the card is needed or wrong, a design is made from it: the card is
   written as a new version of the spec, and the design follows the spec strictly, with a verdict -
   accept or reject, and every rule and check behind it.
5. **Refine.** The engineer changes the card and makes another design. Each is a new spec version.
6. **A design space.** In which ways more designs satisfying the spec can be made - which levers
   are free, over what ranges, how many distinct designs that holds - saved as a constrained,
   parameterised space for a later campaign.

There is **no finished version of the part to compare against**. Where ribs go comes from the
engineer's intent and nothing else; the system never guesses a layout from another CAD file, and
never "corrects" the engineer's part. If the CAD carries an artefact, the engineer fixes it in CAD.

## Where language comes in

**The card works with no language model.** Everything it fills is read off the part by code, in one
pass, and everything the engineer types into it is read by code too: face and feature ids, numbers
and units, and a small vocabulary per slot. What that cannot read is kept exactly as typed and
flagged on its slot - never guessed at - and the card is not ready until it is set another way.

A language model earns a place only where code cannot do the job: reading a sentence into card
values, proposing layouts that make engineering sense, stating a design space, explaining a verdict.
Two first steps are on the table: one call that fills the card from what the engineer wrote,
checked by the card's own rules like any other edit; or a model proposing a few meaningful families
of variants in a design language whose words are relative to the part - along this wall, fanned
about that boss, no taller than the bore at that end - each built and checked by the system. Which
comes first is [open](status.md#open-decision-whether-a-model-proposes-layouts). The agent built
earlier - a model with tools over the engine, on LangChain and LangGraph, reached through
OpenRouter, traced in LangSmith - is kept in the code and out of the interface until then.

Whatever language does, the rules that hold now keep holding: it quotes the engineer's words
exactly, every number it gives comes from a tool that measured it, it is never scripted to an
example sentence, and it may add constraints but never checks.

## The spec is the source of truth

The card is how intent is set; the **spec** is what was asked for. Generation reads only the spec,
never the card, so the same spec always gives the same designs and a campaign can be re-run months
later.

**The spec is written only from the card.** Every design made from the card writes a new version
first. There is no hand edit of a spec: one could not be guaranteed to satisfy every constraint the
engineer set, so to change the spec the engineer changes the card, whose rules check the change
before it is written.

A spec holds:

- **the engineer's words** - each slot they set on the card, as a line in their own terms: the words
  they typed, verbatim, or the value they picked - and **the faces they selected**. Each placement
  cites the lines and selections it came from (`w1`, `s1`), so anyone can check that the encoding
  says what the engineer said and pointed at
- **the baseline** - the CAD designs grow from
- **placements** - for each group of ribs, where it stands, what it runs between and what it keeps
  clear of (below)
- **rules** - what every design must satisfy, enforced and verified
- **fixed values** - one value for every design
- **levers** - what designs vary over, each with a range and a step values snap to
- **the layout** - how rib paths are drawn, composed from the layout vocabulary
- **the section** - thickness, draft, root fillet, edge round - each a rule, a fixed value or a lever
- **the pull direction** - how the part leaves its mould, for draft and release
- **check thresholds** - each with who set it; any the engineer did not set is marked *assumed*
- **measured references** - every number the spec rests on that the engineer did not set - a
  measurement, the drawing, a default - what it was taken from, and marked unconfirmed

**Features are named by id and fingerprint** - kind, size, position - so that when the CAD is read
again and numbers shift, the spec still finds the right faces, or says plainly that it cannot.

**Every change is a new version**, with what changed. Designs made under an earlier version are
re-checked against the new one; those that now break a rule are marked, not deleted, so the engineer
can see what the new rule ruled out.

**Where it lives.** One file per spec, `<project>/specs/<name>.json`, holding every version of it -
a part can carry several studies. `project.json` names the active one.

## Where ribs go

A placement names three things, each by the one name a face has (`face:1453`) or by a feature:

- **host** - where the ribs stand: faces in one plane. Any surface eventually - a cylinder, a
  free-form face; flat ones only, so far.
- **supports** - what each rib runs between: walls, bosses, bores. With none, ribs stop at the
  host's own edges.
- **keep-outs** - what ribs stay clear of, with a clearance: the holes through given faces - a face
  with no hole through it is kept clear of itself.

The region ribs may occupy is **computed** from these: the stretch of host surface between the
supports, minus the keep-outs grown by their clearance.

Each rib is a **span**. Along its path, it runs from where it leaves one support to where it meets
the next, with its ends buried a few millimetres into both - so it lands cleanly with a fillet at
each end, never floats, and never passes through a wall to the outside. A path that crosses a
keep-out is split or dropped, never trimmed on the grid.

**Its height follows what it spans between, end by end.** Unless the spec says otherwise, each end
of a rib stands as tall as what it meets there, and its top runs straight from one end's height to
the other's - a rib from a short boss to a tall wall rises toward the wall. A level top, held to
the lower end all along, is the other choice. Each end is buried in what it meets as deep as it
must be to stay inside it all the way up: a wall with draft leans away from a rib as it rises.
**Its thickness follows the wall it meets**, held under the rib-to-wall ratio while it is built, not
only checked after.

**Which way a rib stands** is set by the spec, per group of ribs - never assumed. For cast or
moulded parts that is along the pull direction, so a rib on a curved host stays releasable; a rib
that is not cast can stand square to its host.

## The card

One group of ribs is a fixed list of slots:

| slot | the engineer sets | otherwise |
|---|---|---|
| where ribs stand | faces, selected | the flat area the rest of the selection rises from - not merely the largest |
| what they run between | faces, selected or named | the other faces selected; with none, what stands up round the host, past any fillet or chamfer at its foot, on the side ribs stand |
| keep clear of | the faces whose holes to avoid, a clearance - or none | every hole through where ribs stand, 5 mm clear, listed |
| pattern | parallel, square grid, triangle grid, spokes - and for spokes, what they turn about, picked from the bosses and bores among what they run between, largest first, and whether they fan across where ribs stand or go all the way round | spokes about the largest boss or bore standing in the host with the host round more than half of it; else a square grid. Asked for spokes, the largest boss or bore there is. Spokes fan across the host, so a count is ribs there - unless turned by an angle or a face, which needs them all the way round |
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
layout tries on the part, coloured by what becomes of it - a rib, stopped by something to keep clear
of, ending on something not named, too short, no room for its height, or missing where ribs stand -
with the count in words, and redraws as the card changes. Only placing is done for it, so it takes
seconds once the part is open at the preview grid; nothing is written to the spec.

**The card says what is wrong, as it goes.** A face that is not on the part, a host that is not one
plane, a face both stood on and run between, spokes with nothing to turn about, ribs closer than
their own thickness, a height limit - a number, or a face to stay below - that leaves no room for a
rib taller than its root fillet, a radius below the smallest the part allows, an edge round more
than half the rib, words it could not read. The card is **ready** when nothing is needed and nothing is wrong, and
only then makes designs.

**What the engineer set is kept in their terms.** Each slot they set is one line - their words as
typed, or the value they picked - and those lines and the faces they selected are what the spec
quotes and cites. The card quotes only what they typed; a value picked shows as the value. What the part, the drawing or a default filled goes into the spec as measured
references, unconfirmed.

## Reading the part

Everything the card fills is read off the part by code, in one pass:

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
  fillet or a rounded wall corner never does. The card chooses spokes by itself only when the host
  goes round more than half of one; asked for spokes, it takes the largest, and lists the rest.
- **Which wall straight ribs are set out from** is the longest flat face standing round the host,
  measured along it.
- **How tall a rib can stand at an end** is measured on the metal its end is buried in, at every
  depth it could be buried to, so a wall with draft is met as tall as it stands.
- **The plate's thickness** is measured by a ray through it, from the largest facet of the host.
- **The smallest radius** is the drawing's own note, found by its text and cited with it.

## The layout vocabulary

Layouts are composed from small blocks, held in the spec as data. The card offers four patterns -
parallel, square grid, triangle grid, spokes - which are compositions of these, not the mechanism.
A grid is one lattice: its families share a spacing and an origin, so they cross at common points,
and a triangle grid's three families meet in triangles.

- **paths** - straight from A to B; radial from an axis; circular at a radius; a parallel family;
  offset from an edge; the shortest path between two features
- **patterns** - repeat along a line or a circle; a grid; a mirror
- **trims** - to supports; around keep-outs

Anything composed from blocks can be shown, explained, edited and re-run exactly. There is room for
more - a web between two bores, a fan from a boss to a wall, ribs along a load path - and a block
that does not exist yet is added to the code.

## What the engineer's settings become

Every setting lands as one of three things:

| | means | example |
|---|---|---|
| **rule** | every design satisfies it; the generator enforces it and a check verifies it | keep clear of holes |
| **fixed** | one value for every design | R10 root fillet |
| **lever** | a range designs vary over | six to ten ribs |

A single value is **fixed** until the engineer says otherwise. **Every feasible limit cites where it
came from.** A geometric limit - holes, spans, spacing - is measured exactly on the part's surfaces,
and cites the measurement. A limit set by a check - mould release, thick spots - is found by sampling
the range and cites the designs where the check starts to fail.

## The verdict

Every design comes back with a verdict in two parts, and every rule and check the system applied is
listed, so the verdict can be audited.

**Your constraints.** Each is enforced while the design is built and verified on the result: *"keep
out - pass, nearest hole edge 7.2 mm."*

**Engineering checks.** What the platform holds every rib to, whether or not anyone asked: the
fillet actually achieved, thickness against the wall, mould release, thick spots at junctions, gaps
between ribs, nothing floating, protected areas unchanged, the surface closed. Thresholds come from
the spec; any the engineer did not set is marked *assumed*.

A check is code, shown to fail on a part built to make it fail before it is trusted, and added
between sessions - never by a model at runtime. A model that could write its own checks could write
one that passes everything.

## Preview and full

A design at full fidelity takes minutes on a large part, which is too slow to iterate on.

- **Preview** - the same design on a coarser grid. Nothing else is relaxed: placement, every
  constraint and every check are exactly those of a full design; only the voxel is bigger. What the
  engineer iterates on, always labelled a preview. If previews are still too slow, the speed has to
  come from elsewhere, never from dropping geometry or checks.
- **Full** - the design grid. Run on designs worth keeping, or in the background. A design can only
  be *accepted* at full fidelity.

## The design space

A design space is the spec version it belongs to, the free levers with their feasible ranges and the
citations behind them, the fixed values, the sampler (a seeded Latin hypercube and a count), and a
plain statement of the space. A campaign reads it and builds its designs at full fidelity. Once
Simulate exists, the objectives join it, and what is learned steers the next sample.

## Seeing, naming and selecting faces

Hovering a face on any 3D tab shows a small card with its one name, `face:N` - which the rib card
takes wherever it takes a feature - and its type, area, which way it faces or its axis, diameter,
height, and whether a drawing controls it. Clicking pins the card.

**Selecting is how faces get onto the card.** A click selects a face; a Ctrl-click adds one or takes
it out. The **grow** angle spreads a click across every edge shallower than it - and belongs to that
click alone: the stage lists the clicks, the grow control acts on the last one or whichever is
picked, and a face clicked after growing another starts ungrown. Lowering an angle takes faces back
out. Selections are highlighted in a colour no design uses.

## The acceptance test

The build is done when this works end to end on the housing in `assets/`, by a person, with no model
involved:

> Select a floor. Start the card. Keep clear of the holes on it, choose a pattern and a count, set
> the smallest radius if the drawing does not. Preview.

The design has every rib running from one support to another, none crossing a hole or closer to it
than asked, none taller than what it spans, and every check passing - or a verdict that says exactly
which rib fails which rule. Then a change on the card, and another design.

## Build order

1. **The card on the housing**, used by a person, until it makes good designs there. What it shows
   reorders what follows.
2. **The layout vocabulary**, completed: circles about an axis, offsets from an edge, shortest
   paths between features, mirrors - and the four patterns kept only as compositions.
3. **The verdict**, corrected: mould release that looks only at what a rib can collide with, root
   gap that knows where paths cross; checks fast enough to iterate with.
4. **The design space**: feasible lever ranges with citations, saved for a campaign; earlier designs
   re-checked against a new spec version.
5. **Hosts that are not flat**: ribs on cylinders and free-form faces.
6. **Language**: a sentence read into the card, checked by the card's rules like any edit.
