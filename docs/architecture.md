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
What is generated comes from **variants** the engineer authors on the part - each one change in one
place, with what it may vary and every rule it must hold, in the part's named entities - and from
**campaigns** that compose them: a card that says which variants, how designs are drawn and how
many. Designs are placed, repaired, screened and built by code alone - see [ribs.md](ribs.md).

**What leaves the engineer's machine** is only what a model is sent: variants and summaries of named
entities, names and numbers - never CAD files or meshes. The provider is a setting, so a client's
approved one or a local model can take its place. The model is paused while variants and campaigns
are made by hand.

Extract and Model are built; Generate and Simulate are being built. Learn and Optimize are shown in
the interface and not yet implemented — a shell that hides its unbuilt stages describes a tool; one
that shows them describes a product.

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
study.py       a design space in the part's named entities: blocks, constraints with strength and
               source, bound by fingerprint, versioned; what each setting may take, and how many
               distinct points that makes. A variant is one of one block; a campaign composes its
               variants into one.
variants.py    the project's library of variants: a code and a name each, kept in `variants/`,
               listed with the campaigns that used them.
knowledge/     design knowledge as data, each with its source: the rules designs are screened
               with, and the catalogue of casting materials.
generate/      the part as a distance field; the part read for each kind of change - what stands
               where, what rises round a floor, the metal under a face, a plate's thickness; a
               variant filled round what was given and authored by hand; ribs, pads and holes
               placed, measured from their footprints; designs repaired by CP-SAT, screened, drawn
               by the thousand for a campaign, and built - faces moved, ribs composed and holes cut
               in the field - and checked.
spec.py        a design's pieces - placements of ribs, faces moved, holes - and the words and
               fingerprints a variant shares.
simulate/      the engineer's solver deck read as data, never run - its mesh, groups, setup and
               answer - and tied to the CAD faces its groups lie on; the deck solved again by cuDSS;
               a design meshed from its field by CGAL in WSL, given the deck's setup by CAD face,
               solved and recorded; answers compared quantity by quantity.
runner/        a process of its own, outside the server, working through jobs kept as folders: the
               deck solved again, the route on the baseline, a campaign's designs two or three at a
               time. One GPU job at a time.
wsl.py         a script run in WSL, sent whole and stopped on Linux's side past its limit.
agent/         a model with a few general tools over the engine, and skills on composing them;
               paused, its bar hidden, while variants and campaigns are made by hand.
cli.py         batches of designs, run without the interface.
api/           HTTP surface: app.py and simulate.py. Routes contain no logic.
```

`project.json` is not configuration in the usual sense: it holds no facts and no settings, only
decisions - which CAD designs grow from, which protected areas a person approved. The system
proposes each one; nothing in it is written except through an approval. Variants live beside it in
`variants/`, one file each, written when the engineer creates or saves one on Design a variant; one
deleted is moved to `variants/.deleted/`. What campaigns make is output, not a decision, and lives
outside the project in `_archived_designs/<project>/<code>-<name>/` beside `assets/`: the card, the
part's digest, the code's commit and a copy of every variant as it was launched; every design kept,
with its recipe, its hash and its seed; a summary; each design built so far; and in `solved/` each
design solved - its Zarr store, its record, and the run's table of metrics.

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

**Six tabs, in the order the work happens**, in the bar at the top: **Input**, **Reproduce**,
**Variant Setup**, **Campaign**, **Explore**, **Models**. Every one is shown whether or not it is
built yet - a shell that hides its unbuilt stages describes a tool, one that shows them describes a
product - and each names its *subject*: the rail on the left holds that subject's detail, the stage
in the middle the subject itself, and the pane on the right what is done to it.

| tab | rail | stage | right |
|---|---|---|---|
| **Input · Drawing** | callout kinds, and the steps that read them, warnings included | every callout beside the literal text it was parsed from | - |
| **Input · CAD** | what the CAD yielded, its steps, axes, feature kinds; the selection | the part, pickable | - |
| **Input · Mesh & setup** | the deck's files, mesh, material, the groups it acts on with their roles, load sets, signals, analysis, what was not read | the deck's mesh with its supports, couplings and loads drawn as agenticCAE drew them, named on hover | - |
| **Input · Solve** | the engineer's answer and its signals | the answer as contours | - |
| **Reproduce** | the answers - the engineer's, the same mesh by cuDSS, the field route - and the certificate | one answer, two side by side with one camera, or their difference | - |
| **Variant Setup · Variants** | what the CAD yielded | the part, a variant's sample drawn as paths | **Design a variant** |
| **Variant Setup · Route** | the four steps every design takes, walked on the baseline; what a design inherits | the route's mesh, its setup, its answer | - |
| **Campaign** | the campaigns launched; a new one | the campaign card - Compose, Check, Sample & launch - or a launched campaign's designs being solved: how many solved and set aside, how many an hour, where each design is, what happened | - |
| **Explore** | a campaign's designs, each with its stages and its variants | the design at a stage - its paths, its field; mesh, setup, results - or the plans of those that differ most | the design: what it is made of by variant, how it screened, its verdict; Build field |
| **Models** | - | what it will do, and what it waits for | - |

**Everything says where it came from**: imported from the engineer's files, derived from them
without solving, or generated - meshed or solved by fastcae. A name on screen is the file's own: a
bore is what the deck calls it, a signal what the deck asks for.

The pipeline report has no tab of its own because it does not need one: every step belongs to an
artifact, so it appears in that artifact's rail.

**The agent's place is above the tabs.** One conversation, whichever tab is open: a line to say
something in - the faces selected go with it - and a drawer under it with what was said, what the
agent is doing and its answer. It is paused, and its bar hidden, while variants and campaigns are
made by hand; when it returns, what it writes lands on Design a variant, marked, for the engineer
to keep or undo.

**Design a variant is the design space, by hand.** On Variant Setup, where the faces it names are: a
tab for each variant kept and one for a new one. A variant starts from the faces selected and what
to add there; it says what it stands on, ends on and keeps clear of - the part's named entities, or
another variant's ribs or holes; webs, the two sides they run between - then what it may vary and
what it must hold, and how many designs that allows. It is drawn on the part before it is kept - at
its suggested point, or at another drawn at random, every choice as likely as the next, saying
which - only once a point of it passes; its name and Create variant are at the bottom.

**A campaign shows everything it runs, at a glance.** Its card composes variants - each with what it
may vary and how many designs it allows; checks - what each variant varies and the rules it holds,
what holds always - between variants, the part's interfaces, repair - the screening checks, and what
a built design is checked for, a few words each with the full rule on hover; and samples - the
method, how many, the seed, the count, a hundred screened before the launch. The screening checks
can be switched off for one campaign; nothing else can, and a campaign
never narrows a variant. Every launch is a campaign of its own, and keeps its card and a copy of its
variants beside its designs. The interfaces stay closed whatever is switched off.

**A design's stages are letters.** P its paths placed and screened, F its field built and checked, M
meshed, S the solver set up, R results - each filled once done, green, amber or red for how it came
out. Thousands are listed by the few that differ most, by those built, or a page at a time, or only
those holding one variant; a built design's field is kept beside its campaign, so F stays done.

**Layers rather than one picture.** Where two things occupy the same space - the part and a design's
new surfaces, or those surfaces and the design's new metal as cells - each is a layer with a colour
that can be switched off. That is the only honest way to answer "which of these am I looking at".

**Switching a layer off does not throw it away**, and nor does changing tab: the part is loaded into
the 3D view once and kept while any tab that shows it is open, and a page over it - the campaign,
the plans - leaves it where it was. Uploading a surface takes about as long as downloading it.

**Columns that move and fold.** The left and right columns are dragged to width, and the right one
folds to a strip at the edge with its name on it, a click from open again.

**Nothing is said twice.** The card shows what a variant holds; the agent's answer only the few
lines it asks the engineer to look at.

**The agent composes a few general tools.** It finds entities, describes them, relates them to the
part - what one stands on, what rises round a floor, what shares an axis, what lies across the open
space in front of it, what lies between several - measures them, searches the drawing, and reads
and edits the design space. How to compose them for a kind of request is in skills: short recipes
it reads when needed, holding no ids, numbers or example sentences. No tool is made for one kind of
request. It knows what those tools answer, and nothing more: the part's regions carry no roles yet,
and design knowledge is data only for the rules and materials designs are screened with - what it
lacks is in [ribs.md](ribs.md). Design a variant is the way in by hand; the agent, when it returns,
the second way in.

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
