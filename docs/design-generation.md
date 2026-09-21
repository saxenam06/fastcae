# Design generation: what has been tried, what was learned, and why none of it has worked yet

**In one line.** From one housing, its deck and the volumes the engineer keeps, fastcae makes
castable rib designs by the hundred and solves every one. **Only one family of them has ever beaten
the production casting**, and that family cannot currently be built without losing what made it
good. This document says where each attempt stopped, what it left behind that is worth keeping, and
what the evidence says to do next.

Measured on the GRC housing, 2026-09-20. Everything is judged against the **production casting**,
which the project holds as its target and solves exactly as a design is solved - and re-solves
whenever the mesher or the deck changes, so the two are always read on the same footing.

---

## 1. Where it stands

| | |
|---|---|
| Designs solved in C3D10 | **152** across six campaigns |
| Designs that beat production's J_robust | **46** - four of them from the gradient route |
| Best ever | J_robust **1.68 against 3.51 (-52 %)**, gear lead 2.7 µm against 22.1, rib metal -41 % |
| **Designs robust to the load case** | **0 of 29 tested** - every one loses badly when the load turns |
| **The last 20, chosen for variety** | **18 solved, every one worse than production** (+99 % to +9079 %) |
| Throughput | about 45 designs an hour, CAD → mesh → solve with every check |
| Rib library | 2,289 candidates in 11 forms; **478 fuse cleanly** at 20 mm |

Read the two bold rows together. They are the whole problem. **A design that scores well does so
only under one assumed load case, and a design chosen for interesting shape does not carry load at
all.** Nothing yet is both.

## 2. How it works today

1. **Design volumes** - closed volumes from face picks, clear of every bore, hole, mating face and
   the room the parts inside need.
2. **A rib library** - every rib a design may have, as a plate or a chain of plates in the mould's
   pull: webs, T-ribs, gussets, windowed webs, run-outs, islands, tapered webs, arcs, chevrons,
   tees. All at **20 mm**, because the production housing casts every rib at one section and a fixed
   thickness is what lets a rib fuse into a wall cleanly.
3. **Vetting** - each candidate fused alone into the part and rejected if it adds a face under
   5 mm². 478 of 2,289 survive.
4. **Sizing** - one adjoint run on the voxel model gives every candidate a thickness against **J**
   (robust gear-mesh lead + largest displacement + p99.9 stress). Five minutes.
5. **CP-SAT** - legal sets: ribs 100 mm apart, crossings no sharper than 60°, a metal budget.
6. **Screen** - every set solved on the voxel model before any is built.
7. **Build** - fused into the part's own STEP, meshed face by face, solved by cuDSS, with a check
   after every stage.

## 3. Everything that has been tried, and what each gave

| Attempt | What it gave | Where it stopped |
|---|---|---|
| **Voxels read back as plates** | metal where the loads put it | blobs; reading plates back lost most of the optimised metal |
| **A fixed library of production forms** | castable by construction, fast | every rib a plane through or tangent to the axis: every design a radial comb; -16 to -25 % J |
| **An agent choosing each try** | 4 of 6 tries beat production, each reasoned and recorded | still inside the library: it rearranges spokes |
| **Free density on J, with deflation** | the J-optimal metal runs as inclined and tangential plates, not spokes | blobs, and something must interpret them into ribs |
| **CP-SAT covering a load path** | plates in any orientation | 29 of 33 failed vetting; covering matches geometry, not physics |
| **Rib networks + CP-SAT + J sizing** | **the best designs to date: -52 % J_robust at -41 % metal**, 66 of 72 built | one shape only - every rib a flat web held at both ends |
| **Geometry projection on plates** (gradients) | **-58 % on the voxel model; 4 of 4 solved beat production (-6 to -47 %)** | **the gains die at the fuse** - see §5 |
| **Load cases and a robust objective** | 12 cases; production's own lead spans 7.9-51.3 µm across them | showed the designs are not robust; did not make them so |
| **Eleven rib forms + diversity selection** | 43 of 47 feature axes alive; no two designs alike | **every one worse than production** - variety without physics |
| **Fin networks: oracle, chooser, sunk ends** (2026-09-21) | 60 load-path seeds, a short pass, 22 pass the oracle, CP-SAT keeps 8-10, 6-7 build; meshed and solved: largest displacement 1.69 mm at +9.4 kg against production's 0.443 at +47.5 | every network rejected at the 5 mm² check for corner faces under 1.5 mm² at the sunk ends - faces the mesher then handled (0.04 % bad tets); and the optimiser and the builder read a rib's height differently ([rib-optimisation-plan.md](rib-optimisation-plan.md) §10) |

## 4. What was learned, measured

Each of these is a number from the part or from a solve, not a judgement.

**Our ribs are attached; three of the eleven forms are not.** The share of a rib outline's
perimeter joined to the part, measured **in each rib's own plane**:

| | attached |
|---|---|
| webs, T-ribs, gussets, windowed, tapered, chevrons, tees | **47-50 %**, both ends buried |
| `island`, `arc` and `run-out` **as generated today** | **17 %, 23 %, 40 %** |

Two earlier figures on this were wrong and are withdrawn. "Production 16-33 %, ours 0-2 %" compared
each rib against the metal in the *volume's* mid-plane instead of the rib's own - the comparison was
meaningless. "Only 4 of 9 production ribs touch metal at both ends" tested the extremes of a bounding
box, not the root. **Attachment is not what is wrong with the designs**: the eight rooted forms are
rooted. The three that float are retired, and a production rib that fades out is a fin whose *height*
falls to zero while its root stays attached - which is what the parameterisation of §7 makes a
number rather than a form.

**Variety without physics is worthless.** The 20 designs chosen to be as unlike each other as
possible: best +99 % J_robust, median about +900 %, worst **+9079 %** with 21 mm of deflection
against production's 0.44 mm. One reached misalignment 0.34 against production's 2.21 - superb gear
alignment - while deflecting 2.7 mm. A housing that aligns beautifully and folds up.

**No design is robust to the load case.** Of 29 solved designs scored under 12 cases, **none** beats
production's lead under all of them. The best on the deck's case (-88 %) is **+488 %** when the
rotor's bending is pointed another way - a direction the source says outright has no fixed value.
The ±5 % band already in the objective does not catch this: it perturbs magnitudes, not direction.

**Production's own alignment is an assumption.** Its lead reads 7.9 µm under one defensible case and
51.3 µm under another. So "-52 % against production" is not one number; it needs its case named.

**There is one load case.** The deck and agenticCAE both hold a single DLC (1.3 extreme, 401 kN·m);
the 16 components are its decomposition, not 16 cases. Variety in loading has to be derived.

**The objective cannot be chosen freely.** agenticCAE's 490 designs settled it: bore tilt ranks
almost in reverse of misalignment, stress never binds (448 of 490 pass), and mass belongs on the
Pareto axis rather than in the sum. Storing many objectives for many readers is a different thing
from ranking on them, and is worth doing.

**Four silent bugs cost whole families of shape.** The both-ends rule applied to chain pieces (killed
every arc and three quarters of the chevrons); 111 duplicate candidate ids (a design could be built
from a rib never vetted); no lap at chain joints (every arc joint a sliver); `_chain` refusing
one-piece branches (killed every tee). None raised anything - **the library was simply smaller, and
nothing said so.**

## 5. Why the good designs cannot be built

The gradient route produced the only designs that beat production convincingly. It lost them at
**one check**, and the numbers are exact: of 30 plates that could not stay where the optimiser put
them, **25 were rejected for sliver faces under 5 mm² at the OCC fuse** and 5 by the rib-shape rules.
**None was a meshing failure, and CP-SAT was not involved.** The walk-back then returned 23 of the 30
to their starting position, erasing the optimisation.

Those slivers are not arbitrary boolean artefacts. **The sliver is the notch.** `_finished` unions
the plate with the metal it sinks into, so the outline follows every small step of the wall -
measured at **7-31 short stepped edges a rib** (in-plane width is fine at 34-110 mm, so notches
rather than needles). Fuse a notched outline into the part and it leaves a face of a few square
millimetres.

So the bind is three-cornered, and every attempt so far has held at most two corners:

| | castable | carries load | differentiable |
|---|---|---|---|
| rib library + CP-SAT | yes | no | **no** |
| free density / geometry projection | **no** | yes | yes |
| what is needed | yes | yes | yes |

## 6. What each piece built so far is for

Nothing here is wasted, and most of it is needed by whatever comes next.

| Piece | What it does | Why it carries forward |
|---|---|---|
| **`ribs/paths.py` + multigrid** | J and its gradient on the voxel model, four solves a step, 5 s | the physics any gradient method needs |
| **`ribs/fins.py` + `ribs/mma.py`** | smooth-step projection, union, **exact gradients**, MMA with many rules held at once - the plates' machinery, on the fin | the machinery was right; only the primitive was wrong |
| **`designs/responses.py`** | every design keeps all 16 load components, fields and rotations (~100 MB) | any objective under any load case, afterwards, **free** |
| **load cases as data** (`_archived_code/`, `designs/loadcases.py`) | re-weight, scale, turn | the band a robust design is sized against, when more than the deck's case is asked |
| **`Model.hold_across`** | the worst case over a band, smoothly, **at no extra cost** | makes a design robust rather than lucky |
| **47 numbers describing a design** (`_archived_code/`, `designs/features.py`) | the library's designs measured | proved 15 axes were dead; a fin's ten numbers are the design variables now |
| **The rib library** (`_archived_code/`) | 11 forms, 2,289 candidates, 478 vetted | the vocabulary a castable parameterisation must span; its limits and its metal reading are kept in `ribs/library.py` |
| **Vetting and the stage checks** | a rib that will not fuse never reaches a design | the honest gate; never patched |
| **The fins' ledger** | every fin's fate at every stage, with the rule behind it | so a silent loss cannot cost a network again: each loss is read, and its rule moved upstream |
| **Face-by-face mesher, fold collapse** | 90 % of designs mesh | without it nothing is solved at all |

## 7. What the evidence says to do

**A rib is a root curve on the part's surface, a height profile along it, and a fixed thickness.**
Density is a smooth function of distance to that swept fin.

- **one clean solid** - a simple fin pushed slightly into the wall and fused once, so its outline
  never inherits the wall's steps; that outline is where 25 of 30 gradient designs were lost (§5)
- **castable by construction** - a fin on a drawing surface draws; there is no projection step at
  which gains can be lost
- **rooted by construction** - the root lies on the surface and the height falls to zero where a rib
  fades, so a fin cannot hang in air
- **differentiable end to end** - `dJ/d(control point)`, `dJ/d(height)`, `dJ/d(presence)` all exist

The eleven discrete forms then **dissolve into regions of one continuous space**: a curved root is an
arc, a kinked root a chevron, a height falling to zero at one end a run-out, at both ends an island,
two fins sharing a root point a tee. The feature vector stops describing a design and becomes it -
which is what lets the gradient reach it.

Order: one volume first, one fin optimising end to end, solved and compared. That confirms the
diagnosis or kills it in a day. Then the band (§4), so the answer is robust rather than tuned to one
assumed load; then the objectives a surrogate serves.

Not free: **lightening holes and T-flanges** do not fall out of a root-plus-height fin and need
parameters of their own.

## 8. Open items

- **No stress adjoint on the voxel model.** Stress can be scored on any solved design under any load
  case, but no design can be *aimed* at it. agenticCAE's designs span 66.7-247.2 MPa at p99.9, so it
  varies enough to be worth aiming at.
- **A percentage against production needs its load case named.** Production reads 7.9 µm under one
  case and 51.3 under another.
- **Per-rib vetting is a filter, not a guarantee.** Ribs that each fuse cleanly alone can still make
  slivers together; two of the last 20 failed exactly that way.
- **Root fillets are not added**; ribs meet walls with sharp roots. The fin parameterisation would
  make a root fillet natural rather than an extra step.
- **One load case in the deck.** Everything else is derived.
