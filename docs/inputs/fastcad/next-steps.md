# Next steps (as of 2026-09-16)

Status: planning is complete. The plan of record is [fastcad-v1-plan.md](fastcad-v1-plan.md) (rev B), committed on branch `task/gen_cad_framework`. **Nothing is built until the user confirms it.**

## 0. Confirmed (2026-09-16)

- **Plan rev B is accepted**, and will be adjusted as work progresses.
- **Models:** start with LangGraph plus DeepSeek, and move to Claude later.
- **Solver:** Code_Aster, with the GPU copy for every variant and Code_Aster itself on a sample.
- **Also standing:** one meshing pipeline for the baseline and every variant; the repo stays in git.

## M0: foundations

1. **Save the outputs that live in Temp** into the repo. **Done 2026-09-16:** 126 files, about 75 MB, now in [`data/analysis/`](../data/analysis/README.md).
   - The full `gate3cad` case, which is the reference solve of the production housing.
   - Summaries of the other gate cases; the 2.1 GB system matrix was left behind.
   - This session's STEP analysis, deck analysis and drawing crops.
   - Large rebuildable binaries (`field.npz`, `sizes.npz`, `surface.npz`) are kept on disk but not in git.
2. **Scaffold the package.**
   - A Python 3.12/uv package with a test skeleton.
   - Port modules from fastcae and agenticCAE, with their tests ([prior-work](prior-work/fastcae-and-agenticcae.md)).
3. **Fill in `assets/`. Done 2026-09-16.** `assets/target/` holds only engineering artifacts: `cad/` (the canvas), `drawing/` and `deck/` (mesh and setup). Everything else, including the YAML notes written during the research, went to `reference/`, which no run reads. Whatever the artifacts don't say is derived by the code or asked at sign-off; the gap list is in the plan, section 2. `fastcad.toml` names the canvas, and `MANIFEST.csv` records digests. Original plan:
   - Copy the core set from `cae-data`: drawings, reports, and `tech-data/*.yaml` with a source and page for every value.
   - Add `MANIFEST.csv` ([grc/data-inventory.md](grc/data-inventory.md)).
4. **Build the production baseline deck.** Nothing about the loads is re-derived.
   1. Re-mesh the production STEP with fTetWild, and convert to TET10.
   2. Apply the seat and bolt labels (the edge-line and 2 mm-corner rules), and write `.comm`/`.med`/`.export`.
   3. **Take the load vectors from fastcae's existing `loads.json`**, the same ones in the current deck.
   4. Solve with both Code_Aster and cuDSS.
   5. Compare with the gate study: 0.418 mm, 55 MPa, and the seat tilts.
   6. **The user signs off two things** ([grc/baseline-deck.md](grc/baseline-deck.md)):
      - which bearing sits in which seat (two are disputed between sources);
      - **the carrier-share fraction.** `loads.json` assumes the rear housing takes 50% of the carrier torque reaction: 460 kN·m over an assumed 750 mm arm, giving 306.7 kN, plus 71.5 kN of thrust, all at the Ø541 seat. Its stated plausible range is 460–920 kN·m. This one number is most of the 345 kN net load: without it, that seat would carry about a fourteenth as much. Keeping 50% is a valid answer.
5. **The Input Console: the UI that shows what actually goes into a run** (added by the user, 2026-09-16).
   - `assets/` is the only folder the user fills. The UI lists everything in it and marks the files the product needs as selected, so the user controls exactly what enters a run.
   - The user imports the selected artifacts, and then sees: **the drawings, the CAD, the mesh, and the solver setup** that the coming variant work will use.
   - A button solves the baseline with Code_Aster: run once, cached afterwards.
   - Ported from fastcae's Input and Reproduce tabs where that is cheaper than writing fresh.
6. **Kernel bake-off, run on the current STEP as it is** (moved ahead of any repair, 2026-09-16). About 30 operations in three lanes:
   - OpenCascade, with SimpleCADAPI and a FreeCAD repair pass first;
   - an Onshape FeatureScript interpreter;
   - CGM, if Spatial grants an evaluation.

   Parasolid and CGM heal imported geometry as they read it, so the winner decides how much repair we actually need ([research/platforms-and-kernels.md](research/platforms-and-kernels.md)).
7. **Repair, scoped to what the winning kernel still fails on**, plus the silent-failure check.
   - **Settled 2026-09-16:** the canvas is `254492_prep_small_adv.step`. It removes the 24.6% silent volume loss at the HSS plane and most defects, and behaves identically in every operation test.
   - **Also settled:** rib operators build their own root fillet, because filleting a contour after fusing fails whenever it crosses the existing blends.
   - Remaining detail below (validity, expected volume change, nothing changed outside the edited region via geometric signature matching, mesh consistency).
   - The user's closed solid stays the canvas. Its known defects: 469 edges with tolerance above 0.1 mm, 26 slivers, 3 negative-area faces, 24 self-intersecting pieces, and the 10° cone (face 1904) that makes whole-body cuts silently lose volume.
   - **Optional, 5 minutes:** one tighter Onshape re-export, to see whether the loose tolerances disappear without any repair. If it doesn't help, we repair the current file.
8. **First onboarding pass.**
   - The interface map as typed frames.
   - The design-style statistics.
   - A report of CAD-to-drawing mismatches: 4 known so far, each shown to the user to decide.
   - **The user signs off.**
9. **Measure the time per variant** for an operation, the mesh and the solve, and set the M1 throughput targets.

## M1 → M5

- **M1, structural core:** the collar, radial-rib, connect and pad operators (split into family plus resolver), the casting and style checks, variant decks, GPU solves, the results table, a CLI. **Done when:** 50 variants across at least 4 classes, at least 90% passing.
- **M2, agent and all 12 classes:** LangGraph plus the MCP server; a Requirement Spec with typed rows and a clarifier that asks all its questions at once; CP-SAT planning and diversity; windows; equal-mass campaigns; "Generate 100 more"; the web app.
- **M3, moved interfaces:** re-bore, move bore, morph, envelope growth; the rework check; the round-trip test; loads from the gear-statics tool; the GB2 → GB3 answer key.
- **M4, generality:** the front housing 254506, with a deck drafted by analogy and loads asked from the engineer.
- **M5, demo:** the benchmark in the Agents' Last Exam format with a general-agent baseline, the yield funnel, the blind panel, the investor cut.

## The user's action items

- **Optional:** re-export 254492 from Onshape at a tighter tolerance, only as a 5-minute test of whether that removes the loose tolerances. Your existing closed solid stays the canvas.
- Convert 254506 (front housing) to STEP and close it.
- Convert 251342-1 (the GB2 housing, from the D: copy or a re-download) to STEP and close it.
- Request an evaluation of CGM plus 3D InterOp from Spatial.
- Get Onshape API access on a paid plan. Check whether fastcad qualifies for Onshape's startup programme.
- Name 2–3 engineers for the blind panel.
