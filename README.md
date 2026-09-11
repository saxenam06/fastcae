# fastcae

**ZenryxAI — Generate. Learn. Optimize.**

A platform for generating design variants of any engineered part, running them at scale, learning a
surrogate from the results, and searching it.

Two of the six stages run. **Extract** reads a folder of artifacts and produces an understood
model, with every claim traceable to the file, page and literal text it came from. **Generate**
places ribs on a part in formations - spokes, webs, square and triangle grids - by editing its
signed distance field on a fixed grid: pick a formation, set its levers, press Generate, and the
design comes back with true root fillets, a closed surface and every check's verdict. Designs are
settings, so the same levers give the same bytes. [docs/status.md](docs/status.md) is the honest
account of where that stands.

---

## Running it

```
uv run python scripts/dev.py
```

API on `127.0.0.1:8021`, interface on **http://localhost:5183/**. Neither port is the conventional
one, because the machine this was built on already runs something on 8000 and 5173 and a silent
bind failure is worse than an unusual number.

Nothing is loaded at startup. The interface opens on a list of projects and waits.

## A project is a folder

```
assets/
  GRC_Gearbox_Housing/
    housing_baseline.brep
    254492_0_closed_volume.step
    254492.pdf
    project.json
```

The folder's name is the project's name. Its artifacts are the files inside it, classified by
extension — `.step` and `.brep` are CAD, `.pdf` is a Drawing.

`project.json` holds the decisions a person has made about the part, and only those: which CAD file
designs grow from (the *baseline*) and which is kept to compare against (the *reference*), which
proposed zones and protected areas are approved, and corrections to the baseline. The system
proposes; a person confirms. A project without the file behaves as if nobody had decided anything.

Add `assets/DEEPJEB_Bracket/` containing a STEP file and it is a second project called DEEPJEB
Bracket. If it has no drawing, the pipeline runs the steps it can and reports the two it cannot.

`assets/` is **not** tracked by git. A STEP file is megabytes of geometry belonging to a part, not
source belonging to this application — so a fresh clone has no project until you put a folder there.

## What it knows

Only what it can read out of those files, and where in them it read it. There is nowhere to write a
fact by hand, deliberately: a hand-written fact is indistinguishable, three stages later, from one
that was measured. `project.json` holds decisions, not facts, and every assumed casting rule reads
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
  features.py     generic detection: axes, bores, bosses, hole patterns, planar groups, fillets
  drawing.py      PDF text extraction and callout parsing
  extract.py      the deterministic pipeline, and drawing-to-CAD association
  generate/
    field.py      the narrow-band signed distance field a design is edited in
    corrections.py changes to a baseline before designs grow on it
    surface.py    manifold dual contouring, and re-contouring only what changed
    cells.py      the visible faces of the field's own cells, packed for drawing
    shading.py    normals for a contoured surface, so it can be looked at
    primitives.py the shapes a design adds, as distance functions
    design.py     a parameter, a design, and the field one produces
    ribs.py       a rib as a distance function, and the round blend that fillets its root
    formations.py spokes, webs and grids: levers in, ribs out
    zones.py      where ribs may go, proposed from what a person removed
    compose.py    ribs joined into a part's field inside a zone's window
    checks.py     pass, warn or reject, with a reason and the rule it used
    designs.py    a project opened for designing, and a design made from settings
  cli.py          fastcae designs: a seeded list of designs and a summary table
  provenance.py   Evidence, Fact, Conflict - how anything is known
  api/app.py      HTTP surface; routes contain no logic
  api/mesh.py     the wire format a surface reaches the browser in
ui/src/
  app/            shell, tab definitions, product strings
  stage/          upload, the drawing, the 3D view
  panel/          the per-tab rails, the selection, the agent's pane, the card vocabulary
  render/         WebGL2 renderer: surfaces, field cells, ID-buffer picking
```

## Documentation

- [architecture.md](docs/architecture.md) — how it is built, and the rule that keeps it general
- [extract.md](docs/extract.md) — the pipeline, and the limits of associating a drawing with a model
- [generate.md](docs/generate.md) — how a design variant is represented, and what the field costs
- [rib-layouts.md](docs/rib-layouts.md) — ribs in formations: zones, the rib, the fillet, the checks
- [tasks.md](docs/tasks.md) — how the system asks a person for work; designed, not built
- [verification.md](docs/verification.md) — the human-verification workflow; designed, not built
- [status.md](docs/status.md) — what is true today, what is unverified, what is next

## Development

```
uv run pytest tests -q          279 tests
uv run ruff check src tests
cd ui && npx tsc -b
```

A seeded batch of designs, once a zone is approved in the Generate tab:

```
uv run fastcae designs GRC_Gearbox_Housing --per-formation 16 --seed 0
```

It writes the settings and a summary row per design to the project's `designs/` folder.
