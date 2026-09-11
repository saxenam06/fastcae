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
search all exist to serve designs that had to be generated first. What is generated comes from the
engineer's intent, stated in plain language and turned by an agent into a spec - see
[ribs.md](ribs.md).

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
generate/      the part as a distance field, ribs composed into it, and the checks.
agent/         (to build) the LLM agent: tools over the routes, the spec it writes.
cli.py         batches of designs, run without the interface.
api/app.py     HTTP surface. Routes contain no logic.
```

`project.json` is not configuration in the usual sense: it holds no facts and no settings, only
decisions - which CAD designs grow from, which spec is active, which protected areas a person
approved. The system proposes each one; nothing in it is written except through an approval. Specs
live beside it in `specs/`, one file each, written only by the agent.

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
over HTTP; the agent's tools call the same routes with no privileged path, so anything the agent can
do, the interface can do.

**Routes contain no logic.** A route unpacks a request, calls one engine function, and packs the
result. Anything a route can do that the engine cannot is something an agent will not be able to do.

## The interface

Six stages, always shown. `available` gates interaction, never display.

**Three tabs on the stage, one per thing there is to look at.** Drawing, Geometry and Field name
the *subject*, and the left rail holds that subject's own detail:

| tab | rail | stage |
|---|---|---|
| **Drawing** | callout kinds, and the steps that read them, warnings included | every callout beside the literal text it was parsed from |
| **Geometry** | what the CAD yielded, its steps, axes, feature kinds | the tessellated surface, pickable |
| **Field** | layers, the field's own statistics, the contour's | the field, its contour and the CAD, as switchable layers |
| **Generate** | the spec, its levers, and each design's verdict | the design's new surfaces over the part |

The pipeline report has no tab of its own because it does not need one: every step belongs to an
artifact, so it appears in that artifact's rail. Putting the tabs in the rail instead lets a tab and
its detail disagree about the subject.

**Layers rather than one picture.** Where two things occupy the same space - the field's cells and
the surface fitted through them and the B-rep both were built from - each is a layer with a colour
that can be switched off. That is the only honest way to answer "which of these am I looking at",
and it is what keeps a reconstruction from being mistaken for the thing it reconstructs.

**Switching a layer off does not throw it away.** Whether something is visible and whether it is
loaded are separate: uploading a surface to the GPU takes about as long as downloading it, so
tearing one down to hide it makes a checkbox cost what a fetch costs, in both directions. Layers are
uploaded once and drawn conditionally.

**Two columns, both movable, and the right one shut by default.** The left column carries the
current tab's detail and, under it, whatever is selected - a selection belongs beside the features
it was made from, and it applies to two tabs of the three, so a pane that sits empty on the third
is a pane in the wrong place. The right column is the **agent's**, opened from a mark in the bar
and closed again to get the width back. It is where the engineer talks to the agent; until the agent
exists it says so rather than offering a chat box that does nothing.

**Every face can be named.** Hovering a face on any 3D tab shows what it is and every feature it
belongs to, so an engineer can refer to it in words - and hand that reference to the agent.

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
