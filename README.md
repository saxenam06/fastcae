# fastcae

**ZenryxAI — Generate. Learn. Optimize.**

A platform for generating design variants of any engineered part, running them at scale, learning a
surrogate from the results, and searching it.

This repository holds the first stage: **extract**. Artifacts in, an understood model out, with
every claim traceable to the file it came from.

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
    254492_0_closed_volume.step
    254492.pdf
```

The folder's name is the project's name. Its artifacts are the files inside it, classified by
extension — `.step` is CAD, `.pdf` is a Drawing. There is no manifest and nothing to configure.

Add `assets/DEEPJEB_Bracket/` containing a STEP file and it is a second project called DEEPJEB
Bracket. If it has no drawing, the pipeline runs the steps it can and reports the two it cannot.

`assets/` is **not** tracked by git. A STEP file is megabytes of geometry belonging to a part, not
source belonging to this application — so a fresh clone has no project until you put a folder there.

## What it knows

Only what it can read out of those files, and where in them it read it. There is nowhere to write a
fact by hand, deliberately: a hand-written fact is indistinguishable, three stages later, from one
that was measured.

## Layout

```
src/fastcae/
  project.py      a folder of artifacts - the only unit of configuration
  geometry/
    brep.py       STEP loading, face-tagged tessellation, vertex welding
    health.py     the watertightness and fidelity gate
    atlas.py      per-face measurement, adjacency, measured dihedrals, visibility
  features.py     generic detection: axes, bores, bosses, hole patterns, planar groups, fillets
  drawing.py      PDF text extraction and callout parsing
  extract.py      the deterministic pipeline, and drawing-to-CAD association
  generate/
    field.py      the narrow-band signed distance field a design is edited in
  provenance.py   Evidence, Fact, Conflict - how anything is known
  api/app.py      HTTP surface; routes contain no logic
ui/src/
  app/            shell, stage definitions, product strings
  stage/          upload, pipeline, geometry
  panel/          the card vocabulary, model index, inspector
  render/         WebGL2 renderer and ID-buffer picking
```

## Documentation

- [architecture.md](docs/architecture.md) — how it is built, and the rule that keeps it general
- [extract.md](docs/extract.md) — the pipeline, and the limits of associating a drawing with a model
- [generate.md](docs/generate.md) — how a design variant is represented, and what the field costs
- [tasks.md](docs/tasks.md) — how the system asks a person for work; designed, not built
- [verification.md](docs/verification.md) — the human-verification workflow; designed, not built
- [status.md](docs/status.md) — what is true today, what is unverified, what is next

## Development

```
uv run pytest tests -q          51 tests
uv run ruff check src tests
cd ui && npx tsc -b
```
