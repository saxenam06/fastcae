# Architecture

**This file describes the system as it is now.** Superseded content is deleted, not annotated.

---

## The claim the architecture has to support

fastcae is a **general platform**. The gearbox housing in `assets/` is one study. Tomorrow it is a
bracket, then a shaft. Every layer has to survive that without an edit.

The arc, in the order it runs:

> **Extract → Model → Generate → Simulate → Learn → Optimize**

and back: what is learned and the objectives set steer which designs are sampled next.

Generate leads because it is the thing a solver cannot do: the campaign, the training set and the
search all exist to serve designs that had to be generated first. Generative design in CAD tools
gives a handful of optimal shapes per setup; this gives thousands of production-grade variants of
the engineer's own part, each its own CAD, meshed and solved as their deck solves the part, for a
surrogate to find designs good on several objectives at once.

What is generated grows inside the **design space** - one volume round the part where metal may go,
taken as defined and kept with the project; where the engineer brings none, fastcae's rules define it
from the CAD's faces, the solver deck's loads and supports tied to them, and what the drawing
tolerances ([design-space.md](design-space.md)). One **pipeline** reads the files and, last, the
design space, every step's inputs and outputs typed entities that the interface and the agent read
alike ([pipeline.md](pipeline.md)). Designs are optimised in it, built as their own CAD, meshed face
by face and solved ([designs.md](designs.md)).

**What leaves the engineer's machine** is only what a model is sent: entities in a few words, names
and numbers - never CAD files or meshes. The provider is a setting, so a client's approved one or a
local model can take its place.

Extract, Model and the design space are built; Generate and Simulate are being built. Learn and
Optimize are shown in the interface and not yet implemented — a shell that hides its unbuilt stages
describes a tool; one that shows them describes a product.

## The rule that keeps it general

**Geometry gives you the *kind*. Documents give you the *role*.**

A concave cylinder is a **bore** — true of a housing, a bracket and a shaft alike. Whether it is
*controlled*, and what it is called, is something a document has to say.

Kinds are universal, so they live in code. Roles are per-part, so they arrive from artifacts.

A module that detects "the dowels that locate a ring gear" has to be edited before a bracket can
load. One that detects "equal holes repeated on a circle" does not.

### Nothing absolute that governs geometry

An absolute millimetre threshold is a hidden assumption about part size. Half a millimetre of chord
tolerance is reasonable on a two-metre casting, is a percent of a forty-millimetre bracket, and is
larger than a five-millimetre one.

So every tolerance that governs geometry is derived from the model's own bounding diagonal:

| quantity | derivation |
|---|---|
| tessellation chord tolerance | `diagonal × 2.5e-4`, clamped to 0.01–1.0 mm |
| small-hole threshold | `diagonal × 0.03` |
| axis coincidence | `diagonal × 1e-3` |
| concentricity of a pattern to an axis | `diagonal × 1e-3` |
| ray offset for visibility testing | `max(diagonal × 5e-6, 10 × weld tolerance)` |
| similarity of two faces by radius | `diagonal × 5e-5` |
| drawing-to-model size match | `diagonal × 2.5e-4`, capped at 0.5 mm |

What stays absolute is what genuinely does not scale: the 1 µm vertex weld tolerance, which sits
between the sub-micron mismatches real CAD carries and the smallest geometry anyone deliberately
models. Angles, counts and fractions are dimensionless and need no derivation.

### Units are declared, not inherited

OCC rescales a STEP into whatever `xstep.cascade.unit` names, and that setting reads as **empty**
by default — so the system was relying on an unstated default being millimetres. It is now set
explicitly, and the unit the file declares is read from its own records and reported. A file
drawn in inches would otherwise have been silently 25× wrong with nothing to notice it.

## Layers

```
project.py     a folder of artifacts, and the decisions a person has recorded about them.
cache.py       derived results, keyed on content and on the code that made them.
geometry/      B-rep in, tagged surface out; the part on a grid of cells, and what the renderer
               needs of cells and surfaces. Knows shapes, never purposes.
features.py    generic feature detection. No domain vocabulary anywhere.
drawing.py     PDF text to callouts. Every one cites its page and literal text.
extract.py     the deterministic pipeline, and the drawing-to-CAD association.
provenance.py  Evidence, Fact, Conflict. How anything is known.
pipeline/      the pipeline as typed entities: the kinds (pydantic, one discriminated union), the
               Read steps from the extraction, the design space as the last step, one graph with
               every link read both ways.
space/         the design space: kept in the project's folder and read back; defined by rules where
               none is brought - interfaces and their evidence, what sits round them, the inside, the
               layer over the walls, what is kept clear - and where metal helps.
volumes/       the design volumes the engineer keeps: a face picked, the closed volume it bounds
               found in flat slices of the part, what it keeps clear, kept as a recipe.
ribs/          a rib network made in the kept volumes, one constrained problem held to the target:
               fins.py (a fin's ten numbers, the gate of placement, the seeders, the optimiser and
               its rules), oracle.py (every fin judged before any boolean), choose.py (CP-SAT keeps
               the network), curved.py (a fin's outline on the CAD's own sections, its swept solid),
               paths.py, sizing.py, multigrid.py, mma.py (the part on cubes, its solve, the MMA
               step), workflow.py (the nine stages in order), campaign.py (a design fused, meshed,
               solved and checked), networks.py (what the screens read), jobs.py (the runner's job).
designs/       what every design shares: a campaign's records, a design's CAD - fused solid by
               solid - the target, the deck carried onto a design's mesh and solved, the objective
               it is scored by, the deck's load mixes, its per-load answers.
simulate/      the engineer's solver deck read as data - its mesh, groups, setup and results - and
               tied to the CAD faces its groups lie on; a CAD meshed face by face; a deck carried to
               another mesh by CAD face; solved by cuDSS; results compared quantity by quantity.
runner/        a process of its own, outside the server, working through jobs kept as folders: the
               deck solved again by cuDSS, a campaign's designs. One GPU job at a time.
wsl.py         a script run in WSL, sent whole and stopped on Linux's side past its limit.
agent/         a model with a few general tools over the pipeline's entities, the part and the
               drawing; what it reads of the part.
api/           HTTP surface: app.py (the session and what was read), pipeline.py, designspace.py,
               simulate.py (the deck and jobs), designs.py. Routes contain no logic.
```

`project.json` is not configuration in the usual sense: it holds no facts and no settings, only
decisions - which CAD designs grow from. The design space is kept beside it as `design_space.npz` and
`design_space.json`: an input like the CAD, read by its own step, never among the artifacts the
extraction reads. What campaigns make is output, not a decision, and lives outside the project in
`_archived_designs/<project>/campaigns/<campaign>/<design>/` beside `assets/`: what each design was
made for and what each stage found, and what each stage made - its layout, plates, STEP, mesh and
answer.

Code the product no longer runs is kept whole in `_archived_code/` at its own path, for reference;
nothing in `src/` or `ui/src/` reaches it.

The solver deck and its answer are the engineer's files like the CAD and the drawing, in the project
folder; what fastcae solves from them is derived and lives in `.fastcae/solve/`.

## Nothing derived is computed twice

Reading the CAD takes ten seconds and building a distance field takes three minutes. Neither
depends on anything but the files in the project folder and the code that reads them, so neither is
paid twice for the same inputs. Results live in `<project>/.fastcae/`, hidden because they are
derived and inside the project because they belong to the part.

**The key is content plus code.** An entry names a digest of every artifact that fed it *and* a
digest of the source that produced it. Change the STEP and the key changes; change a threshold and
the key changes. There is no timestamp to be wrong about and no cache to clear.

**Which source is declared per result, and it has to be only that source.** A key names the
modules that build the result and nothing downstream of it - a region's exact distance takes
minutes, and must not be thrown away because a check that merely reads it changed.

The four newest entries of each kind are kept, which is enough for one project at a time.

Including the source is what makes it safe rather than merely fast. A cache keyed on inputs alone
hands back a result computed by code that no longer exists, and that failure presents as the new
code not working.

Everything cached is rebuildable, so a missing, corrupt or unreadable entry is a **miss, never an
error**, and deleting the directory is always safe. What a person means by *re-extract* is not
"the cache is broken" - it cannot go stale on its own - but "read the files again anyway", so that
is a flag on the request rather than a repair.

## Provenance

Every fact carries `Evidence`: a source kind, a locator specific enough to return to, the method,
and a confidence. A `Fact` resolves to one of four states — `measured`, `derived`, `assumed`,
`conflicted` — computed, never set by hand.

Two things the model deliberately does not do:

**It does not rank sources into one authority order.** A drawing is authoritative for what is
*controlled*; the CAD for what was *modelled*. Which wins depends on the question.

**It does not resolve conflicts.** A disagreement is information, and collapsing it into a single
number destroys the only signal that something needs a person.

Conflicts are recorded and **not shown**. A conflict is what two confirmed facts do when they
disagree, and nothing in the system is confirmed yet, so a disagreement between two things nobody
has agreed are the same feature is an open question rather than a conflict. It surfaces one link
earlier, as a task - see [tasks.md](tasks.md).

## The command layer

`api/app.py` is the single seam between the engine and anything driving it. The browser calls it
over HTTP, and anything else that drives the engine - a batch, a model's tools - calls the same
functions with no privileged path.

**Routes contain no logic.** A route unpacks a request, calls one engine function, and packs the
result. Anything a route can do that the engine cannot is something nothing else will be able to
do.

## The interface

**Four tabs, in the order the work happens**, in the bar at the top: **Input**, **Generate**,
**Learn**, **Optimize**. Every one is shown whether or not it is built yet - a shell that hides its
unbuilt stages describes a tool, one that shows them describes a product. Each lays out a rail on
the left, its subject in the middle, and a pane on the right that folds to a strip at the edge.

| tab | rail | stage | right |
|---|---|---|---|
| **Input · Drawing** | the pipeline | every callout beside the literal text it was parsed from; the one in focus highlighted | the card of what is in focus |
| **Input · CAD** - *Part* | the pipeline | the part, pickable; the faces in focus selected | the card |
| **Input · CAD** - *Design space* | the pipeline | the design space as one opaque volume over the part; switches for the part, the design space and where metal helps | the card |
| **Input · Mesh & setup** - *Setup* | the pipeline | the deck's mesh with its supports, couplings and loads as agenticCAE drew them, the group in focus lit | the card |
| **Input · Mesh & setup** - *Solve results* | the pipeline | the deck solved, as contours: Code_Aster's run and cuDSS on the same mesh as tabs under the picture; the field, deformed, edges, the signals the deck asks for | the card |
| **Generate · Campaign** | the campaigns kept; a new one | a campaign as a grid of designs by stages, filled in as they are made; for a new one, the plan to choose from and launch | - |
| **Generate · Designs** | a campaign's designs, each with its stages | the design at a stage: the optimisation at any iteration with its history, the plates, the CAD's new faces, the mesh, the solve results | the design: what it was made for, each stage's numbers, the deck's signals beside the bare part's |
| **Learn**, **Optimize** | - | what each will do, and what it waits for | - |

**The pipeline is the rail on Input**: every step, the design space last, what it read and what it made, and
a click on anything shows it on its canvas and on the card ([pipeline.md](pipeline.md)). What the
rail, the card, a canvas or the agent picks is **in focus**, and focus alone decides what each
canvas highlights.

**Everything says where it came from**: imported from the engineer's files, derived from them by a
rule, inferred - a reading that could be wrong - or generated. A name on
screen is the file's own: a bore is what the deck calls it, a signal what the deck asks for.

**The agent's place is above the tabs.** One conversation, whichever tab is open: a line to say
something in - what is in focus goes with it - and a drawer under it with what was said, what the
agent is doing and its answer, the ids in it chips that bring an entity into focus. What it shows
comes into focus on its canvas.

**The agent composes a few general tools** over the pipeline - its steps, its entities, one entity in
full, and show - and over the part: what one stands on, what rises round a floor, what
shares an axis, what lies across the open space in front of it, what lies between several, how far
it reaches and how thick the metal is under it; and it searches the drawing. No tool is made for one
kind of request. It never makes geometry or designs.

**Layers rather than one picture.** Where two things occupy the same space - the part and a design's
new faces, the part and the design space - each is a layer with a colour that can be switched off,
everything drawn opaque. That is the only honest way to answer "which of these am I looking at".

**Switching a layer off does not throw it away**, and nor does changing tab: the part is loaded into
the 3D view once and kept while any tab that shows it is open, and a page over it leaves it where it
was. A layer shown once is kept until the space it came from changes.

**Columns that move and fold.** The left and right columns are dragged to width, and the right one
folds to a strip at the edge with its name on it, a click from open again.

**Every face can be named.** Hovering a face in the 3D view shows its one name, `face:N`, and what it
is; clicking it opens its card, with what lies on it.

**The card is the test of whether the model is general** - it renders an entity of any kind from its
typed fields, its evidence and its links, never one kind of part. If a field would be meaningless
for a bracket, it belongs somewhere else.

Nothing tints the default 3D view. An always-on colour reads as a selection the viewer did not
make and competes with the one they did; controlled faces, the design space and its paints each
have their own view, entered deliberately.
