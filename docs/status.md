# Status

**This file describes what is true now.** Superseded content is deleted, not annotated.

---

## Where it stands

**Extract** and **Model** run end to end on any part. **Generate** has its geometry machinery - the
field, manifold contouring and splicing, ribs with true root fillets, protected areas, the checks -
and is being rebuilt around the engineer's intent, as agreed in [ribs.md](ribs.md): an agent turns
what the engineer asks for into a spec, and designs follow the spec. Simulate, Learn and Optimize are
visible in the interface and not implemented.

What that means today:

- Ribs can be composed into a part in four formations (spokes, web, square grid, triangle grid) with
  levers, checked and measured - but only inside a zone written into the project, and nothing writes
  zones any more. Zones will come from the spec's placements. Until then the Generate tab has
  nothing to design in.
- There is no agent. The agent pane is a placeholder.
- There is no reference part. A project is the engineer's rib-free CAD and its drawings.

Size: 29 Python files, ~9,400 lines; 16 TypeScript files, ~3,900 lines. 266 tests pass; they are
kept locally as working checks and are not tracked.

One project in `assets/`: **GRC Gearbox Housing** - the rib-free housing (`housing_baseline.brep`),
its 4-page drawing, and `project.json`.

## What the pipeline produces today

```
GRC Gearbox Housing  (6.8 s)
  ok  Discover artifacts                 1 CAD, 1 Drawing
  ok  Read CAD                           1 solid, 1753 faces, 121,374 cm3
  ok  Check geometry health              watertight, 133,102 triangles
  ok  Measure every face                 1753 faces, 732 reachable from outside
  ok  Detect features                    216 boss, 197 fillet, 154 planar_group, 20 bore,
                                         7 hole_pattern
  ok  Read drawing                       4 pages, 255 callouts, 8 toleranced
  ok  Cross-check drawing against CAD    5 of 30 callouts associated, 1 ambiguous,
                                         7 controlled faces, 2 unresolved
   warn cad.load the file also holds 29 loose edges outside any face; not read
   warn cad.load the file declares no length unit; it was read as mm
```

The loose edges are what deleting features in CAD left behind; the reader keeps the solid and says
so. Drawing: 255 callouts - 22 counted, 21 threads, 16 tolerance frames, 8 toleranced dimensions,
7 datums (A, B, D, EV, EW, EX, EY), units mm.

## What is verified

**Nothing by a person.**

No association this system has produced has been checked by a person. The matching rule was written
here, run on one drawing, and its output reported as working. There is no ground truth, no
validation set, and therefore no measured accuracy. The three associations currently asserted:

| feature | model | drawing | basis | confidence |
|---|---|---|---|---|
| `bore:196` | Ø541.00 | `'541.080 / 541.020'` | toleranced dimension, exact size | 0.70 |
| `bore:202` | Ø1166.00 | `'1166.11 / 1166.04'` | toleranced dimension, exact size | 0.70 |
| `hole_pattern:2` | Ø21.00 ×5 | `'5X 21.00 63.00'` | size and count both agree | 0.70 |

Each is capped at 0.70 because each rests on an inference the drawing does not state - that the
value is a diameter. The symbol that would say so survives extraction **zero times out of 255
callouts**, so the inference is cited as `derived` evidence.

Every Generate check has rejected a synthetic part built to fail it. On the housing, four of them
are wrong in ways listed below.

## Measured limits

### Extract

**The association rule has a low hit rate.** Of 15 hole callouts, 3 find any candidate and 1 also
agrees on count. The other 12 have no pattern within 4 mm - the drawing describes families at Ø14,
Ø10.20, Ø8.0 and Ø4.20 that detection does not produce. **The gap is detection, not matching**: from
1 µm to 0.5 mm of match tolerance the result is identical.

**Two unresolved pairings**, where size agrees exactly and count does not:

```
hole_pattern:4   drawing 25 at Ø26   ·   model 23 at Ø26.00
hole_pattern:5   drawing  3 at Ø20   ·   model  4 at Ø20.00
```

**Detection finds circular hole patterns only.** Holes in a straight row, and single holes, are not
found; holes are grouped by diameter and axis direction with no reference to position. Planar groups
gather every coplanar face however far apart. Features record no extent, and nothing links a hole to
the face it pierces. All of this matters now: it is what the agent will need to be specific.

**One ambiguity correctly refused.** `'50.34 / 50.22'` matches two bosses both at Ø50.00, so nothing
is asserted.

**Volumes read about 70 cm3 high** with OCC's default integration: 121,374 cm3 against 121,301 from
tight integration on the housing.

**No mass.** Nothing states a material or a density. The drawing states a mass, but for the part as
drawn, not as brought; nothing reads it.

### Generate, on the housing

| | measured |
|---|---|
| field at 2.5 mm, once | 158 s |
| contour of the whole part, once | 20 s: 1.70 M vertices, 3.40 M triangles, closed, no faults |
| a zone's exact distance, once per zone | about 11 minutes |
| a design, formations across a zone | 1.5 to 8 minutes, of which the checks are 1 to 7 |

Formation designs made on the housing show these defects:

- **The splice leaves open edges** - 208 on a design with ribs across a zone, 1,182 on a grid.
  Synthetic parts splice exactly; the housing does not.
- **Ribs escape the part.** A formation's lines are trimmed to a zone's air on the grid; where that
  air leaks through an opening, ribs pass through walls to the outside, and trimmed ends are ragged.
- **Ribs are taller than what they meet.** Height is one fraction of the zone, so a rib overhangs a
  boss it lands on.
- **Mould release is too strict**: it rejects any part above a rib tip along the pull, however far.
  **Root gap** fires near crossings of arcs and lines. **Floating pieces** are left for the check to
  find rather than dropped.
- **Checks are slow** - most of a design's time.

The placement in [ribs.md](ribs.md) - ribs as spans between supports, height following them, smooth
cuts - replaces the trimming that causes the second, third and part of the fourth.

## Next

The build order in [ribs.md](ribs.md#build-order):

1. The surface splice at scale
2. What the model says about a part - planar groups as connected areas, every hole and the face it
   pierces, extents, neighbours
3. Seeing and naming faces - the hover card, highlighting, picking that sees ribs
4. The spec
5. Placement - host, supports, keep-outs, spans
6. The layout vocabulary
7. The verdict - constraints and checks, corrected; preview and full
8. The agent
9. The acceptance test, run by a person

Alongside, on Extract:

- **Confirmation instead of assertion.** No association should become a fact automatically, and no
  conflict should be raised on a pairing nobody has confirmed. Designed in
  [verification.md](verification.md).
- **Positional reading of the drawing** - text with coordinates, for leader lines and view
  membership, which is what a pairing actually needs.

## Decisions in force

| decision | choice |
|---|---|
| Project | a folder under `assets/`; its name is the folder's name. Folders starting `_` or `.` are set aside |
| What a project holds | the engineer's CAD - no ribs - and drawings. No reference part, ever |
| `project.json` | decisions only: the baseline, which spec is active, approvals. Proposed by the system, confirmed by a person; no facts |
| Where ribs go | from the engineer's intent: host, supports and keep-outs named in the spec |
| The spec | the source of truth, one file per spec with every version. Written only by the agent, carrying the engineer's words verbatim with each rule citing them; generation reads only it |
| The agent | an LLM with tools over the platform's routes; never makes geometry; asks when a phrase is ambiguous; nothing scripted to an example |
| Agent stack | LangChain agent loop on LangGraph with human-in-the-loop, OpenRouter (DeepSeek by default), LangSmith; conversation and checkpoints in SQLite with the project; credentials from the environment |
| Layouts | composed from a vocabulary of paths, patterns and trims, held as data. Formations are examples |
| Constraints and checks | constraints enforced and verified; checks are code, tested against failing parts, thresholds from the spec, basis shown. The agent adds constraints, never checks |
| The part's own rules | rib section, root fillet, edge round, fillet floor: no default; set per part |
| Fidelity | preview on a coarser grid with nothing else relaxed; accept only at full |
| Tessellation | OCC `BRepMesh`, chord tolerance derived from the model |
| `cadquery-ocp` | pinned at 7.9.3.1.1; 8.x ships an unsigned binary Smart App Control blocks |
| SciPy | `scipy.stats` is blocked by the same policy; anything needing it is written in numpy |
| Units | `xstep.cascade.unit` set explicitly to MM; the file's own declaration is read and reported |
| Scale-dependent tolerances | derived from the bounding diagonal, never absolute |
| Control | derived from a toleranced drawing dimension matching a detected feature |
| Conflicts | recorded, never resolved, and not shown until an association is confirmed |
| Derived results | cached under `<project>/.fastcae/`, keyed on content and on the source that produced them; a miss is never an error |
| Design representation | a signed distance field on a fixed grid; a design is a spec version and lever values, never stored geometry |
| Contouring | manifold dual contouring; the baseline whole, once; a design re-contours only what it changed, spliced by key |
| Design grid | a quarter of the root fillet unless asked for; voxel sizes offered are round numbers |
| Ports | API 8021, interface 5183 |
| Checks enforced | `ruff` and `tsc`. `mypy --strict` is configured and does not pass (235 errors in 20 files) |
| Version control | source and docs; `assets/` and `tests/` are not tracked |
