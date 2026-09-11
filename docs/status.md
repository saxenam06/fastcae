# Status

**This file describes what is true now.** Superseded content is deleted, not annotated.

---

## Built

**Extract**, **Model** and **Generate** run end to end. Generate places ribs on a rib-free baseline
in formations - spokes, webs, square and triangle grids - inside zones a person has approved, joins
them with true root fillets, and hands back a closed surface with every check's verdict. Simulate,
Learn and Optimize are visible in the interface and not implemented.

What Generate does not have yet: a batch of designs run on the housing (the script is built and
tested on synthetic parts), use through a browser, and zones drawn on the part rather than listed.
See [rib-layouts.md](rib-layouts.md#not-done-yet).

- 75 source files: ~13,900 lines of Python with its tests, ~3,900 of TypeScript
- 279 tests, all passing
- One project in `assets/`: **GRC Gearbox Housing** - the rib-free baseline (`.brep`), the
  production casting kept as the reference (`.step`), a 4-page drawing, and `project.json`
- Everything derived is cached, so a restart costs seconds rather than minutes

## What the pipeline produces today

The pipeline reads the baseline, as `project.json` names it:

```
GRC Gearbox Housing  (7.3 s)
  ok  Discover artifacts                 2 CAD, 1 Drawing
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

The 29 loose edges are what deleting the old ribs left behind at their roots; the reader keeps the
solid and says so. The reference reads as 1 solid, 2,167 faces, 127,917 cm3, with 262 fillets,
238 bosses, 25 bores and the same 7 hole patterns - the drawing's associations are the same on
either.

Geometry, on the reference: watertight, one shell, zero boundary/non-manifold/winding faults,
volume within 0.117% of the B-rep. Unit declared `millimetre`, read as mm.

Drawing: 255 callouts - 22 counted, 21 threads, 16 tolerance frames, 8 toleranced dimensions,
7 datums (A, B, D, EV, EW, EX, EY), units mm.

## What is verified

**Nothing.**

No association this system has produced has been checked by a person. The matching rule was written
here, run on one drawing, and its output reported as working. There is no ground truth, no
validation set, and therefore no measured accuracy.

The three associations currently asserted:

| feature | model | drawing | basis | confidence |
|---|---|---|---|---|
| `bore:196` | Ø541.00 | `'541.080 / 541.020'` | toleranced dimension, exact size | 0.70 |
| `bore:202` | Ø1166.00 | `'1166.11 / 1166.04'` | toleranced dimension, exact size | 0.70 |
| `hole_pattern:2` | Ø21.00 ×5 | `'5X 21.00 63.00'` | size and count both agree | 0.70 |

Feature ids are numbered per CAD file, so these are the baseline's.

Plausible. Unconfirmed. Each is capped at 0.70 because each rests on an inference the drawing does
not state - that the value is a diameter. The symbol that would say so survives extraction **zero
times out of 255 callouts** on this drawing, so the inference is cited as `derived` evidence rather
than folded into the reading.

## Measured limits

**The association rule has a low hit rate.** Of 15 hole callouts on the drawing, 3 find any
candidate at all and 1 also agrees on count. The other 12 have no pattern within 4 mm — the drawing
describes families at Ø14, Ø10.20, Ø8.0 and Ø4.20 that feature detection does not produce.

**The gap is detection, not matching.** Tuning the match tolerance changes nothing: from 1 µm to
0.5 mm the result is identical, because drawing values and CAD nominals are either exactly equal or
several millimetres apart, with nothing in between.

**Two unresolved pairings.** Both are cases where size agrees exactly and count does not:

```
hole_pattern:4   drawing 25 at Ø26   ·   model 23 at Ø26.00
hole_pattern:5   drawing  3 at Ø20   ·   model  4 at Ø20.00
```

Neither is called a count conflict, because the pairing itself is in doubt. On the Ø1120 pitch
circle the model carries Ø55.00 ×25, Ø27.00 ×8, Ø26.50 ×7, Ø26.00 ×23 and Ø21.00 ×5 — so a drawing
callout of `25X` has an exact count match against the Ø55 counterbores, and 26.00 + 26.50 together
give 30. The callout may well describe features the model splits differently.

**Detection finds circular patterns only.** Holes in a straight row are a real pattern and are
not found: collinear centres fit a circle of enormous radius, which the size bound rejects. Holes
are also grouped by diameter and axis *direction* with no reference to position, so two separate
bolt circles of the same size and orientation are put in one bucket and fitted as one. Both are
candidate explanations for the twelve missing families, and neither has been measured yet.

**One ambiguity correctly refused.** `'50.34 / 50.22'` matches two distinct bosses both at Ø50.00,
so nothing is asserted.

**The part's volume is only exact to about 0.1%.** Three faces carry negative analytic area, so the
analytic volume and the tessellated surface disagree by more than discretisation explains. Part of
it is OCC's default volume integration, which reads both files about 70 cm3 high: tight integration
and a mesh convergence study agree on 127,857 cm3 for the reference and 121,301 cm3 for the baseline.

**No mass read.** Nothing in the project states a material. The drawing states a mass, 921.15 kg,
and nothing reads it yet; `project.json` records the density it implies over the reference volume,
7.20 g/cm3, marked *derived* with that basis, so it is never mistaken for a measured value.

**The baseline is not the reference minus its ribs.** Where the old rear rib at 135° was deleted,
the patch left stands up to 13 mm proud of the original floor: 50.7 cm3 in neither the casting nor
anybody's intent, and 2.0 cm3 more at a fillet. The approved correction trims the baseline to the
reference; at 2.5 mm it removes 58.8 cm3, a voxel count over a bump 13 mm thick.

## What the field reproduces

The reference sampled onto a fixed grid, and that field contoured back into triangles, against the
B-rep both came from:

| voxel | band cells | field volume | error | contour triangles | contour volume | error |
|---|---|---|---|---|---|---|
| 10 mm | 0.40 M | 126,283 cm3 | 1.28% | 222,756 | 126,740 cm3 | 0.92% |
| 5 mm | 1.88 M | 127,150 cm3 | 0.60% | 897,468 | 127,699 cm3 | 0.17% |
| **2.5 mm** | **8.70 M** | **127,631 cm3** | **0.22%** | **3,605,868** | **127,751 cm3** | **0.13%** |

0.13% is near the floor rather than near a target: the B-rep's own volume and its own tessellation
already disagree by 0.117%, so the field cannot be more right about this part than the part is
about itself. The baseline at 2.5 mm: 121,331 cm3 in the field, against 121,301 from tight
integration.

Checked against shapes with closed-form answers rather than against the casting - a sphere's signed
distance is right to within its own faceting, and a box comes back the size it went in, which is
what dual contouring is for.

**The contour is closed and manifold.** The corrected baseline at 2.5 mm contours to 1.70 M vertices
and 3.40 M triangles with no boundary, non-manifold or winding faults. The old contour left 64
non-manifold edges on the reference; how that was fixed is in
[rib-layouts.md](rib-layouts.md#contouring-only-what-changed). Self-intersections are not counted.

## What it costs to open

A restart, then opening the Field tab:

| voxel | field | contour | cells | cold, first time |
|---|---|---|---|---|
| 10 mm | 0.01 s | 0.01 s | 0.02 s | 62 s + 1 s |
| 5 mm | 0.03 s | 0.02 s | 0.11 s | 144 s + 3 s |
| 2.5 mm | 0.18 s | 0.07 s | 0.72 s | 287 s + 26 s |

To send and to draw, per layer:

| layer | 10 mm | 5 mm | 2.5 mm | vertices a frame |
|---|---|---|---|---|
| field cells | 0.4 MB | 1.8 MB | 7.2 MB | 0.7 / 2.7 / 10.8 M |
| contour | 5.2 MB | 20.0 MB | 79.8 MB | 0.7 / 2.7 / 10.8 M |
| geometry | 4.3 MB | — | — | 0.5 M |

Cells and contour are two drawings of one surface in the same place, so only ever one is shown.
**10.8 M vertices a frame is the honest cost of 2.5 mm** however it is drawn, and 10 mm is fifteen
times lighter - which is the resolution for looking, as against measuring.

Those were measured on the reference. Opening the housing for designing, cold:

| step | cold |
|---|---|
| the baseline's field at 2.5 mm | 158 s |
| the reference's field on the same grid, and the trim | 194 s |
| contouring the corrected baseline | 20 s |
| proposing zones | 1.5 s |
| each approved zone's window | about 11 minutes |

All of it is cached, and none of it is paid again until the baseline, the reference, a correction
or a zone changes. A design's own geometry is only the design sent back: its new surfaces - ribs
and fillets - rather than the whole part.

## Open, in the order I would take them

Two tracks. Generate is the one being built; the Extract questions are real and none of them blocks
a design.

### Generate

**1. Designs on the housing.** One design of each formation, then the 64 - 16 per formation - from
`fastcae designs`, with the time each takes. Until someone has looked at them, nobody knows whether
the formations read as the formations on this part, or whether the checks say the right things
there.

**2. The Generate tab in a browser.** It builds and type-checks; it has never been opened. The
approvals in the housing's `project.json` were set to test this build and go back to *proposed*, for
a person to approve there.

**3. Zones and protected areas drawn on the part**, instead of listed; each rib's triangles tagged
by rib and part of rib.

**4. A cheaper window.** Eleven minutes a zone is paid once, but it is paid again every time the
baseline or a correction changes.

**5. Simulate.** The point of the formations is to see how each affects the results. That needs the
design's surface, whose faces already carry the baseline face they came from, taken into an
analysis.

### Extract

**6. Confirmation instead of assertion.** No association should become a fact automatically, and no
conflict should be raised on a pairing nobody has confirmed. Designed in full in
[verification.md](verification.md): three passes, a queue holding only what changes an outcome,
labelling on the model, and verified work persisted so the next run reads it back. That is the only
route to the ground truth that does not exist today.

**7. Why detection misses twelve hole families.** Whether those holes are not on circles, not
axial, or fall outside the small-hole threshold. Worth answering with numbers before any further
work on matching.

**8. Positional reading of the drawing.** Extracting text with coordinates would give leader lines
and view membership, which is what a pairing actually needs. This is where a deterministic read
ends and an extraction agent begins.

## Decisions in force

| decision | choice |
|---|---|
| Project definition | a folder under `assets/`; its name is the folder's name |
| Configuration | `project.json`: decisions only - which CAD is the baseline and which the reference, corrections, zones, protected areas, density, rules. The system proposes, a person confirms; facts are never written there |
| Baseline | the CAD designs grow from, named in `project.json`; the reference is kept to compare against and to trim the baseline to |
| Tessellation | OCC `BRepMesh`, chord tolerance derived from the model |
| `cadquery-ocp` | pinned at 7.9.3.1.1; 8.x ships an unsigned binary Smart App Control blocks |
| SciPy | `scipy.stats` is blocked by the same policy, through a native library it loads; sampling and anything else needing it is written in numpy |
| Units | `xstep.cascade.unit` set explicitly to MM; the file's own declaration is read and reported |
| Scale-dependent tolerances | derived from the bounding diagonal, never absolute |
| Control | derived from a toleranced drawing dimension matching a detected feature |
| Conflicts | recorded, never resolved, and not shown until an association is confirmed |
| Derived results | cached under `<project>/.fastcae/`, keyed on artifact content **and** on a digest of the source; a miss is never an error |
| Design representation | a signed distance field on a fixed grid; a design is its settings against a baseline, never stored geometry |
| Contouring | manifold dual contouring. The baseline is contoured whole, once; a design re-contours only the cells it changed and splices them in by key. No mesh boolean anywhere |
| Root fillet | a round blend at the root, radius corrected for the angle it meets, exact to the plain union wherever it does not act |
| Voxel sizes offered | round numbers only, each labelled with whether it is already built |
| Grid headroom | how far past the part the grid reaches, and so how tall a rib may be. 2% of the diagonal by default, asked for explicitly when more is wanted, and paid for in cells |
| Parameters | a formation and its levers, per approved zone. Every lever has a range and a step, and values snap to it |
| Design | a baseline, its corrections and its settings. Geometry is regenerated, never stored |
| Checks | pass, warn or reject, each with a reason and the rule it used. Casting rules are *assumed* until a foundry confirms them, and say so |
| Sampling | a seeded Latin hypercube per formation, 16 each |
| Ports | API 8021, interface 5183 |
| Checks enforced | `ruff` and `tsc`. `mypy --strict` is configured but does not pass (245 errors in 21 files) and is not in the loop |
| Version control | source only; `assets/` is not tracked |
