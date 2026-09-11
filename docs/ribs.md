# Ribs from intent

**Being built.** How an engineer explores ways to add ribs to a structure, by saying what they want
and letting an agent work out the designs. This file is the design as currently agreed;
[status.md](status.md) says how much of it runs.

---

## What it is for

An engineer brings a structure that has no ribs yet - its CAD, and its drawings if they have them -
and wants to see the different ways ribs could be added to it, and later how each affects the
results. The platform generates the designs, simulates them, learns from the results, and optimises
toward the engineer's objectives, which in turn steers which designs are sampled next. This file is
about the first step of that loop: turning intent into designs.

1. **Extract.** The platform reads the files and names what it finds: planar groups, bores, bosses,
   holes, fillets, and what the drawing controls.
2. **Say what you want.** The engineer talks to the agent in plain language, referring to named
   features: *"ribs on planar group 60, between planar group 45 and the bore, not over any holes, no
   taller than the bore."* They can say a lot or a little; wherever they say nothing, the agent is
   free.
3. **The agent writes a spec.** It turns the words into a written spec, shows it, and asks about
   anything missing or ambiguous - the fillet, the draft, which "bore height" is meant.
4. **Designs.** Generated to follow the spec strictly, each with a verdict: accept or reject, and
   every rule and check behind it.
5. **Refine.** The engineer looks and adds or changes a constraint in the next turn. The agent
   updates the spec, re-evaluates the designs already made, and updates the current one.
6. **A design space.** The agent says in which ways more designs satisfying the spec can be made -
   which levers are free, over what ranges, how many distinct designs that holds - and saves it as a
   constrained, parameterised space for a later campaign.

There is **no finished version of the part to compare against**. Where ribs go comes from the
engineer's intent and nothing else; the system never guesses a layout from another CAD file, and
never "corrects" the engineer's part. If the CAD carries an artefact, the engineer fixes it in CAD.

## The spec is the source of truth

The conversation is how intent is found; the **spec** is what was agreed. Generation reads only the
spec, never the chat, so the same spec always gives the same designs and a campaign can be re-run
months later without the conversation that produced it.

**The spec changes only through the agent.** An edit by hand could not be guaranteed to satisfy
every constraint the engineer has stated, so there is no such edit: to change the spec, the engineer
tells the agent, which checks the change against everything already agreed before writing a new
version.

A spec holds:

- **the engineer's words** - every constraint as the engineer stated it, verbatim, in the order it
  was given. Each structured rule below cites the words it came from, so anyone can check that the
  encoding says what the engineer said
- **the baseline** - the CAD designs grow from
- **placements** - for each group of ribs, its host, supports and keep-outs (below)
- **rules** - what every design must satisfy, enforced and verified
- **fixed values** - one value for every design
- **levers** - what designs vary over, each with a range and a step values snap to
- **the layout** - how rib paths are drawn, composed from the layout vocabulary
- **the section** - thickness, draft, root fillet, edge round - each a rule, a fixed value or a lever
- **the pull direction** - how the part leaves its mould, for draft and release
- **check thresholds** - each with who set it: the engineer, or the agent (marked *assumed*)
- **measured references** - every number the spec rests on ("the bore's top is z 154"), what it was
  measured on, and whether the engineer confirmed it

**Features are named by id and fingerprint** - kind, size, position - so that when the CAD is read
again and numbers shift, the spec still finds the right faces, or says plainly that it cannot.

**Every change is a new version.** The agent shows what changed, in the engineer's words and as a
diff. Designs made under an earlier version are re-checked against the new one; those that now break
a rule are marked, not deleted, so the engineer can see what the new rule ruled out.

**Where it lives.** One file per spec, `<project>/specs/<name>.json`, holding every version of it -
a part can carry several studies. `project.json` names the active one.

## Where ribs go

A placement names three things:

- **host** - the surface the ribs stand on. Any surface: a planar group, a cylinder, a free-form
  face.
- **supports** - what each rib runs between: a wall and a bore, two walls, a boss and a flange. With
  no supports named, ribs stop at the host's own edges.
- **keep-outs** - what ribs must stay clear of, with a clearance: all holes, particular features.

The region ribs may occupy is **computed** from these: the stretch of host surface between the
supports, minus the keep-outs grown by their clearance.

Each rib is a **span**. Along its path, it runs from where it leaves one support to where it meets
the next, with its ends buried a few millimetres into both - so it lands cleanly with a fillet at
each end, never floats, and never passes through a wall to the outside. A path that crosses a
keep-out is split or dropped, never trimmed on the grid.

**Its height follows what it spans between.** Unless the spec says otherwise, a rib is never taller
than the lower of its two supports at the point it meets them, and its top runs between the two.
**Its thickness follows the wall it meets**, held under the rib-to-wall ratio while it is built, not
only checked after.

**Which way a rib stands** is set by the spec, per group of ribs, from the surfaces and constraints
the engineer gave - never assumed. For cast or moulded parts that is along the pull direction, so a
rib on a curved host stays releasable; a rib that is not cast can stand square to its host. When the
spec does not say, the agent asks.

## The layout vocabulary

The agent designs layouts. The four formations built first (spokes, web, square and triangle
grids) are examples of what it can compose, not the mechanism. Layouts are composed from small
blocks, held in the spec as data:

- **paths** - straight from A to B; radial from an axis; circular at a radius; a parallel family;
  offset from an edge; the shortest path between two features
- **patterns** - repeat along a line or a circle; a grid; a mirror
- **trims** - to supports; around keep-outs

Anything composed from blocks can be shown, explained, edited and re-run exactly, which is what
keeps the agent's inventions auditable. There is room to invent - a web between two bores, a fan from
a boss to a wall, ribs along a load path. When the agent needs a block that does not exist, it says
so, and the block is added to the code.

## What the engineer's words become

Every statement lands as one of three things:

| | means | example |
|---|---|---|
| **rule** | every design satisfies it; the generator enforces it and a check verifies it | "not over any holes" |
| **fixed** | one value for every design | "R10 fillet" |
| **lever** | a range designs vary over | "six to ten ribs" |

A single value is **fixed** until the engineer says otherwise. The agent may offer a range around
it, with what it computed to be feasible ("8 as asked; 6 to 10 fit between the holes here"), and the
engineer decides.

**Every feasible limit cites where it came from.** A geometric limit - holes, spans, spacing - is
measured exactly on the part's surfaces, and cites the measurement. A limit set by a check - mould
release, thick spots - is found by sampling the range and cites the designs where the check starts
to fail.

**When a phrase has more than one meaning, the agent asks.** "No taller than the bore" could be the
bore's top face, the top of the boss around it, or its length; the agent measures each, shows the
numbers, and asks which is meant. What was confirmed is written into the spec with the measurement.

The first vocabulary of constraints, each with an exact geometric meaning:

1. host, and supports
2. keep out of holes - all, or named - with a clearance
3. keep out of any other named feature, with a clearance
4. height - a number, or relative to a feature
5. layout - a formation, or a composition of blocks
6. count or spacing - fixed or a range
7. section - thickness, draft, root fillet, edge round
8. connection - support to support, or free ends allowed

Anything outside it, the agent says it cannot enforce yet rather than pretending to.

## The verdict

Every design comes back with a verdict in two parts, and every rule and check the system applied is
listed, so the verdict can be audited.

**Your constraints.** Each is enforced while the design is built and verified on the result: *"not
over holes - pass, nearest hole edge 7.2 mm."*

**Engineering checks.** What the platform holds every rib to, whether or not anyone asked: the
fillet actually achieved, thickness against the wall, mould release, thick spots at junctions, gaps
between ribs, nothing floating, protected areas unchanged, the surface closed. Thresholds come from
the spec; any the engineer did not set, the agent proposes and marks *assumed*.

The agent may add constraints at runtime. It may not add checks: a check is code, shown to fail on a
part built to make it fail before it is trusted, and added between sessions. An agent that could
write its own checks could write one that passes everything.

## Preview and full

A design at full fidelity takes minutes on a large part, which is too slow for a conversation.

- **Preview** - the same design on a coarser grid. Nothing else is relaxed: placement, every
  constraint and every check are exactly those of a full design; only the voxel is bigger. What the
  engineer and the agent iterate on, always labelled a preview. If previews are still too slow, the
  speed has to come from elsewhere, never from dropping geometry or checks.
- **Full** - the design grid. Run on designs worth keeping, or in the background. A design can only
  be *accepted* at full fidelity.

## The design space

When the agent states in which ways more designs can be made, it saves that as a design space: the
spec version it belongs to, the free levers with their feasible ranges and the citations behind
them, the fixed values, the sampler (a seeded Latin hypercube and a count), and the agent's plain
statement of the space. A campaign reads it and builds its designs at full fidelity. Once Simulate
exists, the objectives join it, and what is learned steers the next sample.

## The agent

A language model with tools. It reads, asks, proposes and explains; **it never makes geometry**.
Every number it quotes comes from a tool that measured it.

- **Tools** call the platform's own routes - list and measure features, find hole-free space on a
  host, measure a feature's extent along a direction, write a spec version, generate, check, state a
  design space. Anything the agent can do, the interface can do through the same routes.
- **Asking the engineer** is a tool too: the agent pauses and the question appears in the chat.
- **Flexible at runtime.** Nothing in its prompt or tools is scripted to an example. The prompt
  states rules that always hold and how to work, not flows or sample questions, and a test checks it
  carries no planted answers. The engineer's asks will change turn to turn.
- **Brief.** It says what it did, what it measured, and what it needs, and stops.

Built the way the agent in `agenticCAE` is: LangChain's agent loop on LangGraph with human-in-the-loop
middleware, a model reached through OpenRouter (DeepSeek by default, configurable), LangSmith
tracing, and the chat streamed to the agent pane. Credentials come from the environment - variable
names only in the code: `OPENROUTER_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_TRACING`,
`LANGSMITH_PROJECT`, and `FASTCAE_AGENT_MODEL` for the model. The conversation and the agent's
checkpoints are kept with the project, in SQLite under `.fastcae/`, as the record of how each spec
version came to be - no database server to run.

## What the model has to say about a part

The agent can only be as specific as extraction is. For intent like the example above:

- **Planar groups** - connected flat areas, one per place a finger could rest without lifting. A
  set of coplanar faces far apart is several groups.
- **Holes** - every hole, single or in a row or on a circle, not only circular patterns - and which
  face each one pierces.
- **Extents** - how far a feature reaches along any direction: a bore's top and bottom, a wall's
  height above a host.
- **Neighbours** - which features touch which.

## Seeing and naming faces

Hovering a face on any 3D tab shows a card: the face number, its surface type, area, normal or axis,
diameter, extent, every feature it belongs to (`planar_group:60`, `boss:12`) and whether a drawing
controls it. Clicking pins the card; **use in chat** puts a reference such as `@planar_group:60`
into the agent's message box. Selecting a feature highlights all its faces, in a colour no design
uses.

## The acceptance test

The build is done when this works end to end on the housing in `assets/`, with the feature numbers
replaced by the real ones:

> *"Ribs on planar group 60, between planar group 45 and the bore. Not over any holes. No taller than
> the bore. Square grid, 8 ribs. Ask me about fillet and draft."*

The agent asks about the fillet and the draft and about anything ambiguous, writes the spec and
shows it; Generate makes a design in which every rib runs from one support to the other, none
crosses a hole, none is taller than the bore, and every check passes; the agent then states the
design space and saves it. Then a second turn adds a constraint, and the agent re-evaluates.

This is a test of the agent's behaviour, not a script for it. Nothing in the code or the prompt
knows this sentence.

## Build order

1. **The surface splice at scale.** Re-contouring only what changed leaves open edges on the
   housing, where the synthetic tests do not. Fixed first - no verdict can pass until it is.
2. **What the model says about a part.** Planar groups, every hole and the face it pierces,
   extents along a direction, feature neighbours - each exposed through a route.
3. **Seeing and naming faces.** The hover card on every 3D tab, feature highlighting in its own
   colour, picking that sees ribs.
4. **The spec.** Its schema, the engineer's words with citations, versions and diffs, feature
   fingerprints; one file per spec, written and read through routes.
5. **Placement.** The region from host, supports and keep-outs; ribs as spans; height and
   thickness following the supports; smooth cuts at clearances.
6. **The layout vocabulary.** Paths, patterns and trims, with the four formations rebuilt as
   compositions.
7. **The verdict.** Constraints enforced and verified; checks with thresholds from the spec and
   their basis; mould release, root gap and floating pieces corrected; preview on a coarser grid
   with nothing else relaxed.
8. **The agent.** Tools over the routes, asking, spec writing, re-evaluation on a new version,
   feasible ranges with citations, the design space, the chat in the agent pane.
9. **The acceptance test**, run by a person.
