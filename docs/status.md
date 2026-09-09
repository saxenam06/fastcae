# Status

**This file describes what is true now.** Superseded content is deleted, not annotated.

---

## Built

Extract and Model. Generate, Simulate, Learn and Optimize are visible in the interface and not
implemented.

- 45 tracked files, ~4,400 lines of Python, ~2,000 of TypeScript
- 40 tests, all passing
- One project in `assets/`: **GRC Gearbox Housing** — a STEP file and a 4-page drawing

## What the pipeline produces today

```
GRC Gearbox Housing  (10.3 s)
  ok  Discover artifacts                 1 CAD, 1 Drawing
  ok  Read CAD                           1 solid, 2167 faces, 127,917 cm3
  ok  Check geometry health              watertight, 153,388 triangles
  ok  Measure every face                 2167 faces, 787 reachable from outside
  ok  Detect features                    262 fillet, 238 boss, 187 planar_group, 25 bore,
                                         7 hole_pattern
  ok  Read drawing                       4 pages, 255 callouts, 8 toleranced
  ok  Cross-check drawing against CAD    5 of 30 callouts associated, 1 ambiguous,
                                         7 controlled faces, 2 unresolved
```

Geometry: watertight, one shell, zero boundary/non-manifold/winding faults, volume within 0.117% of
the B-rep. Unit declared `millimetre`, read as mm.

Drawing: 255 callouts — 22 counted, 21 threads, 16 tolerance frames, 8 toleranced dimensions,
7 datums (A, B, D, EV, EW, EX, EY), units mm.

## What is verified

**Nothing.**

No association this system has produced has been checked by a person. The matching rule was written
here, run on one drawing, and its output reported as working. There is no ground truth, no
validation set, and therefore no measured accuracy.

The three associations currently asserted:

| feature | model | drawing | basis | confidence |
|---|---|---|---|---|
| `bore:1971` | Ø541.00 | `'541.080 / 541.020'` | toleranced dimension, exact size | 0.70 |
| `bore:1965` | Ø1166.00 | `'1166.11 / 1166.04'` | toleranced dimension, exact size | 0.70 |
| `hole_pattern:5` | Ø21.00 ×5 | `'5X 21.00 63.00'` | size and count both agree | 0.70 |

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
hole_pattern:2   drawing 25 at Ø26   ·   model 23 at Ø26.00
hole_pattern:1   drawing  3 at Ø20   ·   model  4 at Ø20.00
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
analytic volume and the tessellated surface disagree by more than discretisation explains.

**No mass anywhere.** Nothing in the project states a material, and a density assumed in code would
be indistinguishable downstream from one that was read.

## Open, in the order I would take them

**1. Confirmation instead of assertion.** No association should become a fact automatically, and no
conflict should be raised on a pairing nobody has confirmed. Designed in full in
[verification.md](verification.md): three passes, a queue holding only what changes an outcome,
labelling on the model, and verified work persisted so the next run reads it back. That is the only
route to the ground truth that does not exist today.

**2. Why detection misses twelve hole families.** Whether those holes are not on circles, not
axial, or fall outside the small-hole threshold. Worth answering with numbers before any further
work on matching.

**3. Positional reading of the drawing.** Extracting text with coordinates would give leader lines
and view membership, which is what a pairing actually needs. This is where a deterministic read
ends and an extraction agent begins.

## Decisions in force

| decision | choice |
|---|---|
| Project definition | a folder under `assets/`; its name is the folder's name |
| Configuration | none — no manifest, nothing written by hand |
| Tessellation | OCC `BRepMesh`, chord tolerance derived from the model |
| `cadquery-ocp` | pinned at 7.9.3.1.1; 8.x ships an unsigned binary Smart App Control blocks |
| Units | `xstep.cascade.unit` set explicitly to MM; the file's own declaration is read and reported |
| Scale-dependent tolerances | derived from the bounding diagonal, never absolute |
| Control | derived from a toleranced drawing dimension matching a detected feature |
| Conflicts | recorded, never resolved, and not shown until an association is confirmed |
| Ports | API 8021, interface 5183 |
| Checks enforced | `ruff` and `tsc`. `mypy --strict` is configured but does not pass (75 errors, mostly unannotated route returns) and is not in the loop |
| Version control | source only; `assets/` is not tracked |
