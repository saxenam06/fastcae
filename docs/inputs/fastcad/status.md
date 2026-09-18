# Status

**Updated 2026-09-16, 12:50.** A living page: where the work stands, and what happens next. The plan itself is [fastcad-v1-plan.md](fastcad-v1-plan.md) (rev B, accepted); the step list is [next-steps.md](next-steps.md).

## Where we are

**Planning is finished and accepted.** 33 decision questions answered, 21 papers and tools reviewed, plus research on platforms, startups, industry practice and the GRC data. All of it is written down in `docs/` (20 documents), with every decision's reasoning and evidence in [decisions/decision-rationale.md](decisions/decision-rationale.md).

**M0 is under way: steps 1–3 are done, step 4 is next.**

| Step | State | What came of it |
|---|---|---|
| 1. Preserve the outputs stuck in Temp | **Done** | 126 files, ~75 MB in `data/analysis/`: the reference solve of the production housing, the STEP and deck analyses, the drawing crops, and the scripts. |
| 2. Scaffold the package | **Done, partly** | `pyproject.toml`, `src/fastcad/assets.py`, 11 passing tests, a venv on Python 3.12. The modules to port from fastcae have not been ported yet. |
| 3. Fill `assets/` | **Done** | `assets/target/` holds only artifacts: the CAD, the drawing and the deck. Everything else went to `reference/`, which no run reads. |
| 4. The production deck | **Next** | fTetWild mesh of the canvas, named regions, the deck written with the existing load vectors, solved against the 0.418 mm reference. |
| 5. The Input Console | Planned | The UI that shows what goes into a run, with a cached baseline solve. |
| 6. Kernel bake-off | Planned | OpenCascade against Parasolid (Onshape) and CGM, on the canvas as it is. |
| 7–9. Repair, onboarding, timings | Planned | Scoped by what the winning kernel fails at. |

## What is settled, and how

**By measurement, since the plan was accepted:**
- **The canvas is `254492_prep_small_adv.step`.** Your re-export with "remove small entities" cuts self-intersecting pieces from 24 to 1 and slivers from 23 to 6, and removes the silent 24.6% volume loss when cutting at the HSS plane. It behaves identically in every operation test. The HealAndSew export changed nothing.
- **Rib operators build their own root fillet.** Filleting a root contour after fusing fails whenever it crosses the existing blends: 0 of 3 radii worked, on both files, while the same operation on a clean wall passes. This is OpenCascade's documented limit, not a defect in the file.
- **Whole-body cuts are unreliable** on both files, so operators cut locally only.

**By decision, in conversation:**
- **Models:** LangGraph with DeepSeek first, Claude later.
- **Solver:** Code_Aster, with the GPU copy for every variant.
- **Principle 8, names carry meaning:** the deck's names are read as they are and carried through. Our decks use conversational names. One vocabulary, no alias tables.
- **Principle 9, inputs are engineering artifacts:** only drawings, CAD and decks are read. Anything else is derived by the code or asked at sign-off, never hardcoded from research.
- **The gap list shrank to almost nothing.** Bearing identity, ratings, load cases, the mounting scheme, the carrier-share assumption and the material grade all come from the deck or don't matter for variants. What remains: the brief's own targets, an optional foundry rule sheet, the cavity keep-out (measured from the CAD), and confirming the region names once.

## The repo

```
assets/          5 files a run reads: target/cad, target/drawing, target/deck
reference/       the library no run reads: earlier exports, 286 drawings, 8 reports,
                 the rib-free housing, and the YAML notes from the research (not in git)
src/fastcad/     assets.py: what a run may read, and what is ticked
scripts/         make_manifest.py, make_reference.py
tests/           11 tests, passing
data/analysis/   preserved results and the scripts behind the numbers in docs/
docs/            20 documents: plan, decisions, research, GRC data, prior work
```

**Git:** branch `task/gen_cad_framework`, pushed through `40f06b8`. **Everything since then is uncommitted, by your instruction.** That covers the scaffold, both scripts, the `assets/` and `reference/` restructure, `data/analysis/`, and all the doc updates since.

## What is next

**M0 step 4, the production deck.** Nothing needed from you to start:
1. Mesh the canvas with fTetWild and convert to TET10, keeping edges, corners, holes and ribs.
2. Find the bearing seats, the flange bolt holes and the flange face in the geometry, and **propose conversational names** for them: `hss_rear_bearing_seat`, `carrier_adaptor_seat`, `ring_flange_bolt_07`.
3. Write the deck: the same couplings, supports and **the load vectors already in fastcae's `loads.json`**. Nothing re-derived.
4. Solve it with Code_Aster and with the GPU solver, and compare against the reference: 0.418 mm, 55 MPa, and the six seat tilts.
5. **Then one sign-off from you:** confirm the region names.

**Then step 5, the Input Console**, ported from fastcae's Input and Reproduce tabs: the asset list with what a run reads, the drawing, the CAD, the mesh and the deck's own setup, and a baseline solve that runs once and caches.

## Waiting on you

| What | Why it matters |
|---|---|
| Confirm the region names, after step 4 | They become the only vocabulary: UI, decks, agent, results. |
| A Spatial CGM evaluation licence | Without it the bake-off runs OpenCascade only, and possibly Onshape. |
| Onshape API access on a paid plan | To put Parasolid in the bake-off, a few hundred calls. |
| Convert 254506 (front housing) to STEP | Needed in M4, not before. |
| Name 2–3 engineers for the blind panel | Needed in M5. |
| Say when to commit | Nothing has been committed since `40f06b8`. |
