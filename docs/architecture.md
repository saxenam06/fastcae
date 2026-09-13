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
gives a handful of optimal shapes per setup; this gives thousands of near-production variants that
follow the engineer's rules, for a surrogate to find designs good on several objectives at once.
What is generated comes from a **study** the engineer states in words and clicks - what may vary,
what must hold, what is preferred, in the part's named entities - written by a model and checked by
code; designs are made and checked by code alone - see [ribs.md](ribs.md).

**What leaves the engineer's machine** is only what a model is sent: the study and summaries of
named entities, names and numbers - never CAD files or meshes. The provider is a setting, so a
client's approved one or a local model can take its place.

Extract and Model are built; Generate is being built. The other three are shown in the interface
and not yet implemented — a shell that hides its unbuilt stages describes a tool; one that shows
them describes a product.

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
geometry/      B-rep in, tagged surface out. Knows shapes, never purposes.
features.py    generic feature detection. No domain vocabulary anywhere.
drawing.py     PDF text to callouts. Every one cites its page and literal text.
extract.py     the deterministic pipeline, and the drawing-to-CAD association.
provenance.py  Evidence, Fact, Conflict. How anything is known.
study.py       the study: what the engineer wants, as a design space in the part's named
               entities - blocks, constraints with strength and source, preferences, objectives,
               the pull, the target - versioned. Generation reads nothing else.
knowledge/     design knowledge as data, each with its source: the rules designs are screened
               with, and the catalogue of casting materials.
generate/      the part as a distance field; the part read for each kind of block - what stands
               where, what rises round a floor, the metal under a face, a plate's thickness; a
               block of the study filled round what was given; the study's draft, changed by hand
               or by the agent; ribs, pads and holes placed; faces moved, ribs composed and holes
               cut in the field; designs screened, made by the thousand, and checked.
spec.py        a design's pieces - placements of ribs, faces moved, holes, the material - and the
               words and fingerprints the study shares.
agent/         a model with a few general tools over the engine, and skills on composing them:
               it reads the part and writes the same draft the card does.
cli.py         batches of designs, run without the interface.
api/app.py     HTTP surface. Routes contain no logic.
```

`project.json` is not configuration in the usual sense: it holds no facts and no settings, only
decisions - which CAD designs grow from, which study is active, which protected areas a person
approved. The system proposes each one; nothing in it is written except through an approval.
Studies live beside it in `studies/`, one file each with every version, written only when the
engineer accepts the draft on Design a variant. What campaigns make is output, not a decision, and
lives outside the project in `_archived_designs/<project>/<run>/` beside `assets/`: every design a
run kept, the study version and switches it used, its summary, and each design built so far.

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

**Five tabs, in the order the work happens**, in the bar at the top: **Drawing**, **CAD**,
**Generate**, **Learn**, **Optimize**. Every one is shown whether or not it is built yet - a shell
that hides its unbuilt stages describes a tool, one that shows them describes a product - and each
names its *subject*: the rail on the left holds that subject's detail, the stage in the middle the
subject itself, and the pane on the right what is done to it.

| tab | rail | stage | right |
|---|---|---|---|
| **Drawing** | callout kinds, and the steps that read them, warnings included | every callout beside the literal text it was parsed from | - |
| **CAD** | what the CAD yielded, its steps, axes, feature kinds; the selection | the part, pickable; where the study would put ribs; a variant's new surfaces | **Design a variant** |
| **Generate · Campaign** | the runs kept | the pipeline in the open, every part of it switchable | launching, and the campaign as it runs |
| **Generate · Designs** | a run's designs, each with its stages | the design at a stage - its paths, its field; mesh, setup, results - or the plans of those that differ most | the design: what it is made of, how it screened, its verdict; Build field |
| **Learn**, **Optimize** | - | what each will do, and what it waits for | - |

The pipeline report has no tab of its own because it does not need one: every step belongs to an
artifact, so it appears in that artifact's rail.

**The agent is above the tabs.** One conversation, whichever tab is open: a line to say something
in - the faces selected go with it - and a drawer under it with what was said, what the agent is
doing and its answer, folded away at a click. What it writes lands on Design a variant, marked, and
says where that is when the card is not in view.

**Design a variant is the design space, by hand.** The one structured view of the study - the
draft of its next version - on the CAD tab, where the faces it names are. Each block says what its
ribs stand on, end on and keep clear of - the part's named entities, or another block's ribs - then
its settings and rules; what the draft changes is marked, and nothing is written until the engineer
accepts it. It makes one variant at a time, at preview or in full, with its verdict; many at once
are a campaign.

**A campaign shows everything it runs.** What varies - each block, where, what its settings may
take; what must hold - each block's rules, the study's, the part's interfaces; the screening checks
every design passes before it is kept, the rules of thumb they rest on and their sources, the
materials; how ribs, pads and holes are placed; how designs are spread; the stages each design goes
through and what a built design is checked for. Any block, rule or check can be switched off for one
campaign without touching the study: the run keeps the version and the switches beside its designs,
and another set of switches - or another seed - is a run of its own. The interfaces stay closed
whatever is switched off.

**A design's stages are letters.** P its paths placed and screened, F its field built and checked, M
meshed, S the solver set up, R results - each filled once done, green, amber or red for how it came
out. Thousands are listed by the few that differ most, by those built, or a page at a time; a built
design's field is kept beside its run, so F stays done.

**Layers rather than one picture.** Where two things occupy the same space - the part and a design's
new surfaces, or those surfaces and the design's new metal as cells - each is a layer with a colour
that can be switched off. That is the only honest way to answer "which of these am I looking at".

**Switching a layer off does not throw it away**, and nor does changing tab: the part is loaded into
the 3D view once and kept while any tab that shows it is open, and a page over it - the campaign,
the plans - leaves it where it was. Uploading a surface takes about as long as downloading it.

**Columns that move and fold.** The left and right columns are dragged to width, and the right one
folds to a strip at the edge with its name on it, a click from open again.

**Nothing is said twice.** The card shows what the study holds; the agent's answer only the few
lines it asks the engineer to look at.

**The agent composes a few general tools.** It finds entities, describes them, relates them to the
part - what one stands on, what rises round a floor, what shares an axis, what lies across the open
space in front of it, what lies between several - measures them, searches the drawing, and reads
and edits the study. How to compose them for a kind of request is in skills: short recipes it reads
when needed, holding no ids, numbers or example sentences. No tool is made for one kind of request.
It knows what those tools answer, and nothing more: the part's regions carry no roles yet, and
design knowledge is data only for the rules and materials designs are screened with - what it lacks
is in [ribs.md](ribs.md). Design a variant writes the same draft by hand; the agent is the second
way in.

**Every face can be named.** Hovering a face in the 3D view shows its one name, `face:N`, and what
it is, so an engineer can refer to it - on the card, in words or as a chip.

The card vocabulary is the test of whether the model is general — each card renders one *kind of
thing the platform knows about*, never one kind of part:

| card | shows |
|---|---|
| **Artifact** | an extracted input, what was read from it, how far it can be trusted |
| **Step** | one pipeline stage: what it did, or precisely why it did not run |
| **Feature** | a detected geometric feature |
| **Callout** | one claim read off a drawing, beside the literal text it came from |
| **Fact** | a value with every source behind it |
| **Metric** | a measured quantity with its unit |
| **Layer** | one drawable thing, its colour, and whether it is shown |

If a card would be meaningless for a bracket, it belongs somewhere else.

Nothing tints the default 3D view. An always-on colour reads as a selection the viewer did not
make and competes with the one they did; controlled faces have their own mode, entered
deliberately.
