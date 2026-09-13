# fastcae

**ZenryxAI — Generate. Learn. Optimize.**

Generative design in CAD tools gives a handful of optimal shapes per setup, which someone then
redraws. ZenryxAI gives thousands of near-production variants of the engineer's own part that
already follow their rules, with solver decks. A surrogate trained on them finds clusters of designs
that do well on several objectives at once - each a real, castable design - and shows which choices
matter for the next design.

The loop: extract what the part and its drawing say, generate designs from what the engineer asks
for, simulate them, learn from the results, and optimise - which steers what is sampled next.

Two of the six stages run. **Extract** reads a folder of artifacts and produces an understood
model, with every claim traceable to the file, page and literal text it came from. **Generate** runs
as a product flow. On the CAD tab the engineer authors **variants** - each one change in one place:
ribs on a floor, webs between two faces, faces thickened, holes through a plate - with what it may
vary and every rule it must hold, in the part's named entities. On Generate they compose a
**campaign** of the variants they choose, count it, screen a hundred designs and launch it: each
design a set of the variants at a point of each, placed, repaired by CP-SAT where its pieces break a
rule between them, screened, and kept beside the project with everything needed to make it again.
Every design is followed through its stages, and any one's field is built at a click. Under it: the
part as a signed distance field on a fixed grid, ribs on a floor or webs between what they join with
nothing under them, each with its own root fillet, flat or T, pads where a wall is too thin, faces
moved exactly, holes cut, a closed surface, checks. The agent that writes the design space from
words is paused while the flow is made by hand - see [docs/ribs.md](docs/ribs.md).
[docs/status.md](docs/status.md) is the honest account of where that stands.

---

## Running it

```
uv run python scripts/dev.py
```

API on `127.0.0.1:8021`, interface on **http://localhost:5183/**. Neither port is the conventional
one, because the machine this was built on already runs something on 8000 and 5173 and a silent
bind failure is worse than an unusual number.

Five tabs, in the order the work happens: **Drawing**, **CAD**, **Generate**, **Learn**,
**Optimize**. **Design a variant**, on the CAD tab's right, is where variants are authored: select
faces on the part, choose what to add there, set what it may vary and what it must hold, look at its
paths and another sample, and create it at the bottom. **Generate** is for many: *Campaign* is a card
in three steps - compose the variants, check everything the pipeline will hold them to, sample and
launch - and *Designs* lists every design a campaign kept, with how far each has got - its paths, its
field, then mesh, setup and results - and builds any one's field. **The agent** - `agent/`, a model
composing a few general tools over the engine - is paused, its bar hidden. Its settings go in a
`.env` at the repository root, which is never committed:

```
FASTCAE_AGENT_MODEL=openrouter:deepseek/deepseek-v4-pro
OPENROUTER_API_KEY=...
LANGSMITH_TRACING=true          # optional, with LANGSMITH_API_KEY and LANGSMITH_PROJECT
```

Nothing is loaded at startup. The interface opens on a list of projects and waits.

## A project is a folder

```
assets/
  GRC_Gearbox_Housing/
    housing_baseline.brep
    254492.pdf
    project.json
    variants/          the variants authored for it, one file each
```

The folder's name is the project's name. Its artifacts are the files inside it, classified by
extension — `.step` and `.brep` are CAD, `.pdf` is a Drawing.

A project is what an engineer brings: the part to add ribs to, and its drawings. There is no
finished version to compare against.

`project.json` holds the decisions made about the part, and only those: which CAD file designs grow
from (the *baseline*, when there is more than one), and what a person approved. The system proposes;
a person confirms. A project without it behaves as if nobody had decided anything. Variants live in
`variants/`, one file each, written when the engineer creates or saves one on Design a variant.

What campaigns make is kept outside the project, in `_archived_designs/<project>/<code>-<name>/`
beside `assets/`: the card, a copy of every variant as it was launched, every design kept with its
recipe and seed, a summary, and each design built so far. It is output, not a decision, and not
tracked by git.

A folder whose name starts with `_` or `.` is set aside rather than a project.

Add `assets/DEEPJEB_Bracket/` containing a STEP file and it is a second project called DEEPJEB
Bracket. If it has no drawing, the pipeline runs the steps it can and reports the two it cannot.

`assets/` is **not** tracked by git. A STEP file is megabytes of geometry belonging to a part, not
source belonging to this application — so a fresh clone has no project until you put a folder there.

## What it knows

Only what it can read out of those files, and where in them it read it. There is nowhere to write a
fact by hand, deliberately: a hand-written fact is indistinguishable, three stages later, from one
that was measured. `project.json` holds decisions, not facts, and every assumed rule reads
*assumed* wherever it is shown.

## Layout

```
src/fastcae/
  project.py      a folder of artifacts, and the decisions recorded about them
  cache.py        derived results, keyed on content and on the code that made them
  geometry/
    brep.py       STEP and BREP loading, face-tagged tessellation, vertex welding
    health.py     the watertightness and fidelity gate
    atlas.py      per-face measurement, adjacency, measured dihedrals, visibility
  features.py     generic detection: axes, bores, bosses, holes, hole patterns, planar groups,
                  fillets - and how far a feature reaches, and what it touches
  drawing.py      PDF text extraction and callout parsing
  extract.py      the deterministic pipeline, and drawing-to-CAD association
  generate/
    field.py      the narrow-band signed distance field a design is edited in
    surface.py    manifold dual contouring, and re-contouring only what changed
    cells.py      the visible faces of the field's own cells, packed for drawing
    shading.py    normals for a contoured surface, so it can be looked at
    primitives.py the shapes a design adds, as distance functions
    offset.py     which part of the surface a face selection asks to move, as a weight per cell
    design.py     a parameter, a design, and the field one produces
    ribs.py       a rib as a distance function, and the round blend that fillets its root
    formations.py spokes, webs and grids: levers in, ribs out
    zones.py      a region ribs may go in, and the window composing into it needs
    compose.py    ribs joined into a part's field inside a zone's window
    checks.py     pass, warn or reject, with a reason and the rule it used - gaps and wedges between
                  ribs measured from their footprints, and the junctions where they meet
    designs.py    a project opened for designing, and a design made from settings
    placement.py  ribs from a placement: paths on a floor, free lines, spans between what they end
                  on, clear of anything by the rib's footprint - and of other variants' ribs and
                  holes; pads where a wall is too thin; holes on a lattice through a plate
    repair.py     a placed design mended by CP-SAT: the fewest ribs, pads or holes left out so no
                  rule between pieces breaks
    holes.py      a hole as a capped cylinder, and holes cut into a design's field
    thicken.py    faces moved along their normal, exactly, in a window round them
    screen.py     a placed design screened in milliseconds, and weighed in its material
    intent.py     designs made from their pieces - faces moved, ribs and pads, holes - with the
                  two-part verdict
    reading.py    reading the part for the agent: what a feature stands on, what rises round a
                  floor, the axes and what is on each, how thick the metal is
    slots.py      ribs on a floor read off the part: every slot filled round what was given
    blocks.py     a variant filled from the part round what was given - ribs, faces to thicken,
                  holes - its ranges stepped by five
    variety.py    the designs that differ most, how far apart they sit, and each as a plan
    campaigns.py  a campaign's card; its variants composed, counted, pooled alone, drawn together,
                  repaired and screened; a hundred screened before launch; the archive
    session.py    the work on an open project: the variant being authored, changed by hand, drawn
                  at a sample that passes, kept; one design built; each design's stages
  study.py        a design space: blocks, constraints, versioned, in named entities bound by
                  fingerprint; what each setting takes, and how many points that makes
  variants.py     the project's library of variants, each a code and a name
  knowledge/      design knowledge as data with its sources: screening rules, casting materials
  spec.py         a design's pieces - ribs, faces moved, holes - and the words and fingerprints a
                  variant shares
  agent/          a model with a few general tools over the engine, and skills on composing them;
                  paused
  cli.py          fastcae designs: a seeded list of designs and a summary table
  provenance.py   Evidence, Fact, Conflict - how anything is known
  api/app.py      HTTP surface; routes contain no logic
  api/mesh.py     the wire format a surface reaches the browser in
ui/src/
  app/            shell, the five tabs, product strings
  stage/          upload, the drawing, the 3D view and the card for the face under the cursor
  panel/          the per-tab rails, the selection, Design a variant, the agent bar (hidden)
  generate/       Campaign - the card: compose, check, sample and launch; the campaigns launched -
                  and Designs - a campaign's designs by stage and by variant, their paths, fields
                  and plans
  render/         WebGL2 renderer: surfaces, field cells, ID-buffer picking
```

## Documentation

- [architecture.md](docs/architecture.md) — how it is built, and the rule that keeps it general
- [extract.md](docs/extract.md) — the pipeline, and the limits of associating a drawing with a model
- [generate.md](docs/generate.md) — how a design variant is represented, and what the field costs
- [ribs.md](docs/ribs.md) — the design space from the engineer's words: variants and campaigns, the
  rib graph, repair, objections that become rules, the cards
- [build-plan.md](docs/build-plan.md) — the steps, in order, and what shows each one done
- [tasks.md](docs/tasks.md) — how the system asks a person for work; designed, not built
- [verification.md](docs/verification.md) — the human-verification workflow; designed, not built
- [status.md](docs/status.md) — what is true today, what is unverified, what is next

## Development

```
uv run ruff check src
cd ui && npx tsc -b
```

Tests live in `tests/` on the machine they are written on and are not tracked.

A seeded batch of designs, for a project with an approved zone:

```
uv run fastcae designs GRC_Gearbox_Housing --per-formation 16 --seed 0
```

It writes the settings and a summary row per design to the project's `designs/` folder.
