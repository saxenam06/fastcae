# Plan: rib and hole families from the engineer's intent and the loads

**Superseded by [rib-optimisation-plan.md](rib-optimisation-plan.md).** The lane below was built and measured; what it gave and where it stopped is in [design-generation.md](design-generation.md).

**Agreed 2026-09-19; M0-M4 built and measured, M5 under way** - how it runs and what it measured on the housing is in [designs.md](designs.md). A plan for how fastcae turns one part's CAD
into meaningful designs: ribs and holes placed in production patterns, derived from the loads,
built as CAD, and solved the way the part's own deck is solved. It starts from the goal, looks at
the three end-to-end lanes tried so far and a fourth researched, names what went wrong in each, and
derives the next lane from that and from a small, targeted literature search.

---

## 1. The goal

**fastcae takes an engineer's part - CAD, drawing, solver deck - and grows a family of meaningful
designs from it, each one solved properly, as training data for a surrogate that learns how the
design changes the answer.** Agents run the pipeline with the engineer. It works on any cast part;
nothing in it names what a part is for.

A design is **meaningful** when:

1. **It stays where the engineer allows.** Metal goes only inside volumes the engineer has seen and
   accepted, clear of every interface (bores, bolt holes, mating faces).
2. **It is made of production features.** Ribs are plates of a set thickness, taller than they are
   thick, ending in the metal they join, with draft and root fillets. Holes are round and keep a
   ligament clear. There are no loose cells or patches.
3. **Its patterns are organised.** Spokes about a bore, rings round a seat, parallel ribs and grids,
   symmetric wherever the loads and the engineer want symmetry, following foundry rules: room for
   the sand between ribs, and no X crossings.
4. **The loads decide it.** Which ribs exist, where, and how thick comes from the physics of the load
   case. Different load paths give different patterns.
5. **It is CAD.** A STEP made by adding solids to the engineer's B-rep. Bores and faces stay exact.
6. **It is solved like the deck.** Face-by-face second-order tetrahedra (C3D10) from the STEP, the
   deck's own loads and supports, cuDSS, and Code_Aster where a check is wanted.

A dataset of such designs, with their patterns as compact parameters (which ribs, what angles,
what thickness) and their answers, is what a surrogate can learn from. A pile of voxels or meshes
is not.

**The first product is the GRC GB3 gearbox housing.** The rib-free housing (`housing_baseline.brep`)
with its Code_Aster deck and drawing is the input. The production housing, with its nine ribs, is
the one piece of real engineering truth we have. It is a **yardstick** for the method, never a
target to copy. As recorded in [research/design-space-on-the-housing.md](research/design-space-on-the-housing.md):

- all nine production ribs are **inner webs** joining the main bearing seat's ring to the barrel and
  the rear wall;
- together they are **6.6 L**, and they take the main seat's motion under the deck's loads from
  **22.3 mm** (rib-free) down to **0.42 mm**.

## 2. The lanes tried, end to end

Each lane is judged on the whole chain: CAD → design space → optimisation → geometry → mesh → solve.

### Lane A - Parametric ribs in a CAD tool (agenticCAE)

| step | how | space |
|---|---|---|
| design space | the existing 15 ribs, each on or off, plus thickness (2^15 designs) | CAD features |
| optimisation | none - sampled | - |
| geometry | Onshape feature scripts regenerate the STEP | B-rep |
| mesh, solve | agenticCAE's mesh route, Code_Aster | TET10 |

- **Outcome:** valid CAD, but every design is the same architecture with its ribs switched on or
  off. The mesh route was defective: measured, it drops six CAD faces, lids holes flat and cuts into
  metal under one bearing seat ([research/field-meshing-gate.md](research/field-meshing-gate.md)).
- **Good:** real, exact CAD.
- **Bad:** no new structural ideas. It needs ribs that already exist. Nothing comes from the loads.

### Lane B - The engineer's rules, CP-SAT, and a distance field (fastcae, early September)

| step | how | space |
|---|---|---|
| design space | the engineer picks faces; ribs on floors, webs between anchors; the walls and bosses a rib ends on found automatically (`rises_round`, `between`) | B-rep faces |
| optimisation | none: Sobol draws of each variant's settings, then CP-SAT repair (leaves out the fewest pieces so every rule holds) | discrete |
| geometry | the part and its ribs as a distance field, fillets included | 3 mm voxels |
| mesh, solve | CGAL meshes the field; Code_Aster or cuDSS | TET10 |

- **Outcome:** organised patterns (spokes, grids, parallel ribs, free lines) that hold every rule,
  each design screened in a fraction of a second. But the patterns were drawn at random: not from
  the loads, not symmetric. A 3 mm field matched the CAD mesh on bearing tilts within meshing noise,
  yet the geometry was not crisp: edges rounded, holes not quite round. That fails the fidelity bar,
  and a field has no STEP.
- **Good:** the engineer's intent by picking faces; anchors found automatically; CP-SAT for rules;
  production-shaped ribs.
- **Bad:** no physics in where the ribs go; symmetry not enforced; no CAD at the end.

### Lane C - A derived design space and voxel optimisation to STEP (this week)

| step | how | space |
|---|---|---|
| design space | derived by rules: a layer three wall-thicknesses deep over every wall, inside and out, minus bores, fasteners and mating space | 4 mm voxels |
| optimisation | BESO on an 8 mm grid, cells only on candidate rib planes 48 mm apart; GPU CG solves | 8 mm voxels |
| geometry | plates traced from each plane's cells, fused one by one onto the B-rep | B-rep → STEP |
| mesh, solve | face-by-face C3D10 from the STEP; cuDSS; Code_Aster agrees | TET10 |

- **Outcome:** the first chain from the loads to a solved STEP. 4 of 6 designs were solved; 2 failed
  in meshing. The best, with 6.1 L of metal, has 39 % of the bare part's strain energy but still 72 %
  of its largest displacement (15.7 mm). The production ribs, with 6.6 L, reach 0.42 mm. The metal
  lies scattered over the walls, not in ribs from the bore to the wall.
- **Good:** STEP, exact bores, C3D10 solved like the deck, every stage on screen.
- **Bad:**
  - **The design space was wrong.** Three walls deep reaches only 60 % of the production ribs'
    volume: the middle of the tall webs between the seat ring and the barrel is out, and a collar
    round each bore opening is kept clear. So no rib could join the bore to the wall.
  - **Each cell was free.** The optimiser can put metal anywhere on a plane, so plates came out
    patchy. Tracing them into plates kept only two thirds of the optimised metal.
  - **No production rules, no symmetry, no CP-SAT.**
  - **Unions of many irregular plates are hard to mesh.** Designs were also capped at about 300 k
    tets by the 8 GB GPU.

### Lane D - Explicit topology optimisation (researched, not built)

MMC, GGP, GET, and Force Flow Members (the list is in
[inputs/research/CAD-Light ...](inputs/research/CAD-Light%20and%20Manufacturing-Ready%20Topology%20Optimization%20%20Recent%20Papers%20and%20a%20Gearbox-Housing%20Research%20Path.md)).

- **Good:** the variables are components, not cells, so the results are explicit and smooth.
- **Bad for now:**
  - GET has no public code and shows only benchmark cases, with no casting rules.
  - Force Flow Members is not open.
  - MMC has open 3D code, but as a general free-component method it still needs the constraints
    that make its bars into production ribs.

## 3. What went wrong, underneath

| # | problem | lanes | consequence |
|---|---|---|---|
| P1 | **Where metal may go was derived by generic rules, in voxels, and never agreed with the engineer.** | C | It missed the load path. The design space is the first decision, and it was wrong. |
| P2 | **The optimiser's variables were cells.** | C | Metal anywhere, scattered like bees; nothing a foundry would make. |
| P3 | **The patterns ignored the loads.** | A, B | Organised, but not better. |
| P4 | **Production rules and symmetry lived outside the optimiser, or nowhere.** | B, C | Asymmetric, rule-less designs. |
| P5 | **Geometry was rebuilt from voxels.** | B, C | Soft edges (B), lost metal and fragile unions (C). |
| P6 | **CP-SAT dropped out when physics came in.** | C | The rules engine and the physics never met. |

What each lane got right, and must be kept:

- the engineer picking faces, with anchors found automatically (B);
- CP-SAT for rules and patterns (B);
- load-driven sensitivities on the fast GPU voxel solver, which agreed with TET10 on bearing motions (C);
- STEP → face-by-face C3D10 → cuDSS, with Code_Aster matching (C).

## 4. What the targeted search found

Six queries and four page reads (three blocked by paywalls, so those rest on their abstracts),
aimed only at the problems above.

- **Stiffener layout by ground structure is established practice for cast and machined plates.**
  Every candidate stiffener gets one thickness variable, and intermediate thicknesses are penalised
  until a clear layout remains. This was used on a machine-tool headstock cover plate
  ([Computers & Structures, 2024](https://dl.acm.org/doi/10.1016/j.compstruc.2024.107633)). A
  related method projects stiffener components onto a ground mesh
  ([SMO 2021](https://link.springer.com/article/10.1007/s00158-021-02945-9)), and another optimises
  rib layout and height together under casting constraints
  ([H-DGTP, SMO](https://link.springer.com/article/10.1007/s00158-015-1281-5)).
- **Gearbox practice** puts ribs radially about the bearing axis and in rings round the seat. Studies
  use topology optimisation to find load paths, then choose rib positions, then size the thickness
  ([housing rib design](https://www.researchgate.net/publication/336853704_Rib_Design_for_Improving_the_Local_Stiffness_of_Gearbox_Housing_for_Agricultural_Electric_Vehicles),
  [two-stage gearbox](https://link.springer.com/article/10.1007/s12206-023-0810-1),
  [transmission housing ribbing](https://www.researchgate.net/publication/304661592_The_optimization_of_the_ribbing_of_gear_transmission_housing_used_in_transportation_machines)).
  These are exactly the families to offer: spokes and rings.
- **Explicit TO code:** MMC has open 3D code
  ([MATLAB, 2022](https://arxiv.org/abs/2201.02491); [Python 2D](https://github.com/ThomasRochefortB/MMC188_python)).
  [GET](https://arxiv.org/abs/2510.05572) has no code released and shows benchmark cases in 2D and 3D.
- **No published method was found for turning a B-rep into enclosed design volumes automatically.**
  Commercial tools have the user draw the design space. Our edge is to propose it from a click and
  let the engineer accept it.

The conclusion matches the earlier research doc's own ranking - explicit, rib-shaped variables
first - but reaches it with components we already have running: face picking, the GPU solver,
CP-SAT, OCC and the C3D10 route.

## 5. The proposed lane

```text
the engineer's CAD, drawing, deck
  → 1. design volumes from intent        B-rep     click a face, see the closed volume, accept it
  → 2. candidate ribs from a library     B-rep     spokes, rings, parallel, chords, load-path lines
  → 3. physics sizing                    voxels    one thickness per candidate rib, all solved together
  → 4. patterns by CP-SAT                discrete  production patterns that keep the most physics
  → 5. the CAD                           B-rep     each rib a solid, fused onto the part → STEP
  → 6. mesh and solve                    TET10     face by face, the deck's loads, cuDSS
  → 7. the record                                  pattern parameters + load case + answers
```

**The key change: the optimiser's variables are ribs from a library, not cells.** Each candidate
rib is one entity with one thickness (and later a height). The physics solve sizes all of them
together and pushes each towards all or nothing. CP-SAT then chooses which to keep, as production
patterns - symmetric, spaced, counted - maximising the physics weight kept. The patterns are
production-shaped because they come from the library, and load-derived because the weights come
from the solve.

### Step 1 - Design volumes from intent (B-rep, OCC)

**On screen:** CAD tab → **Design volumes**.

1. The engineer clicks a face: the floor round a bore, the inside of a wall, a boss.
2. In a second or two a **transparent closed volume** appears: the air over that face, bounded by the
   walls and bosses round it, up to a cap.
3. The cap defaults to the top of the tallest boss or bore the face goes round - "up to the height
   of the bearing bore". The engineer can pick another face as the cap or drag it.
4. Keep-outs are subtracted and listed: the bearing and shaft in each bore, fasteners and tool
   access, mating space. Each can be switched.
5. Ctrl-click adds faces; clicking a wall excludes it. The section tool cuts through the volume.
6. **Accept** makes it a named volume - *V1 · over face:262 up to the main bore's top · 38 L*.
7. Where the part has a matching region - a mirror, or the same seat at the other end of the shaft
   (upwind and downwind) - its partner is offered for acceptance.

**Underneath**, all in OpenCascade:

- **what rises round the face:** walls, bosses and bores, found by `rises_round` from lane B
  (archived, to restore);
- **the volume:** a prism of the face's region along its normal up to the cap plane, intersected
  with the air (a box minus the part), keeping the pieces that touch the face;
- **keep-outs:** exact cylinders and prisms cut out, reusing the interface rules of today's design
  space in exact shapes;
- **storage:** each volume in the project as `volumes/<name>.brep` plus JSON (faces, cap,
  keep-outs), shown by tessellation.

**Nothing inside depends on the other parts of the gearbox.** The cap and the engineer's choice of
faces stand in for the room gears need. An optional "keep clear of what turns" cylinder about a
bore's axis can be added when the engineer knows the radius.

### Step 2 - Candidate ribs from a library

A **rib family** is a generic kind with parameters, attached to named anchors:

| family | anchors | candidates |
|---|---|---|
| spokes | a bore or boss axis, the walls round it | planes through the axis every 5-10° |
| rings | a bore or boss axis | cylinders or planes round it, radius steps |
| parallel | the longest wall round the floor | planes square to it, every half-thickness step |
| chords | two anchors (boss to boss, boss to corner) | planes through the line joining them |
| load lines | the bare part's principal stress directions in the volume | planes along them - Force Flow Members' idea, made cheap |

- Each candidate is the family's plane (or cylinder) intersected with the volume, so **every rib
  ends in its anchors by construction**.
- Its height runs up to the cap, or to what it meets.
- Holes are a second library: round and oblong lightening holes in kept webs and floors, in rows or
  rings.
- **On screen:** the families on the volume as thin translucent planes, with how many candidates
  each gives.

### Step 3 - Physics sizing: every candidate at once

**What is solved:** the part plus every candidate rib on the voxel grid (8 mm, which measured in
agreement with TET10 on bearing motions). Each candidate's cells get stiffness `E · x_i^p`, where
`x_i` is its thickness over the largest allowed.

**The loop:**

1. One warm-started GPU CG solve per iteration, per load case.
2. The sensitivity of each rib is the strain energy in its cells. It is exact and cheap, and every
   candidate gets it at once.
3. An optimality-criteria update under a volume budget.
4. Continuation on `p` (1 → 3) drives each rib to present or absent.
5. About 30-60 iterations, seconds each.

**Load cases:** the deck's full case, each loaded group alone, and chosen mixes. Each gives its own
weights, which is where "different patterns for different load paths" comes from.

**On screen:**

- the optimisation in voxel space: the candidate ribs thickening and fading, iteration by iteration,
  beside the compliance curve and a bar of each rib's weight;
- a free-cell load-path map of the same volume, kept as a reference picture - it explains, it does
  not design.

### Step 4 - Patterns by CP-SAT

**Variables:** for each candidate, *kept* (yes or no) and *thickness* (15, 20 or 25 mm).

**Rules**, all existing kinds from lane B:

- symmetry groups - mirror, or cyclic about an axis, when the engineer or the loads ask for it;
- room for the sand between footprints: two thicknesses at the root, and at wedges;
- no X crossings (optional);
- at most N ribs per volume;
- the metal budget.

**Objective:** keep the most physics weight.

**Variety:** the best K patterns that differ by at least d ribs (no-good cuts), so one load case
gives several production alternatives - 6 spokes, 4 spokes and a ring, 8 spokes. Each is re-solved
on the voxel grid in seconds to rank it.

**On screen:** the alternatives side by side, each with its kept weight, its rules (all held) and
its voxel answer.

### Step 5 - The CAD

- **Each kept rib is built exactly:** the plane intersected with the volume, thickened to its
  thickness with draft, buried a few millimetres into its anchors, and fused onto the part.
- **Root fillets:** a later option; first without.
- **Holes** are cut after the ribs.
- **Checks:** the part's volume is kept, and no keep-out is touched. The result is written as STEP.
- Few ribs, each a clean prism, fuse and mesh far more reliably than lane C's traced plates.

### Step 6 - Mesh and solve, as proven

`face_mesh` C3D10 from the STEP, the deck's supports and loads, cuDSS; Code_Aster on chosen designs.
Kept from lane C unchanged. Measured on every design:

- bearing seat motions and tilts;
- strain energy, stresses, mass.

### Step 7 - The record, and the families

Each design is recorded with:

- its volumes and library;
- the candidate weights;
- the CP-SAT pattern: anchors, angles, thicknesses, heights;
- the load case;
- the STEP, the mesh and the answers.

**A family** is one choice of volumes, library, symmetry and load case; its designs are the CP-SAT
alternatives and their thickness variants. The surrogate learns from the pattern parameters, which
are compact, meaningful and comparable across designs.

## 6. How it is judged

| gate | what must hold |
|---|---|
| **G0** | The production housing re-solved on today's route (face-by-face C3D10, the same deck, cuDSS). The yardstick is fixed before anything is compared with it. |
| **G1** | The volume the engineer accepts round the main seat holds ≥ 95 % of the production ribs' volume and touches no keep-out. |
| **G2** | With spokes and rings in that volume and the production ribs' 6.6 L, the chosen pattern's C3D10 answer comes near the production housing's. A first bar, to agree: the main seat's motion within 2× of G0's. For scale: lane C's best leaves 15.7 mm largest displacement; the production housing, 0.42 mm. |
| **G3** | Every pattern holds its rules and symmetry. Every STEP meshes and solves. |
| **G4** | Five load cases give at least five distinct families. |

G1 and G2 turn "meaningful" into a measurement: given the right volume, does the method find ribs
that work like the ones the housing's engineers drew?

## 7. What changes in the code

| keep | restore from `_archived_code/` | retire to `_archived_code/` |
|---|---|---|
| extraction, face hover and picking, the section tool | `rises_round`, `between`, `across` (part reading) | the rules-derived voxel design space as what decides where metal goes - its interface rules move to exact keep-outs |
| the GPU voxel solver and deck mapping | CP-SAT repair and the pattern rules | BESO on cells |
| OCC fusing, `face_mesh`, cuDSS, Code_Aster | | tracing plates from contours |
| the campaign and design cards, re-staged: Volumes → Candidates → Sizing → Patterns → CAD → Mesh → Solve | | |

## 8. Order and size

| milestone | content | rough size |
|---|---|---|
| M0 | Re-solve the production housing on today's route; G0 | half a day, alongside M1 |
| M1 | Design volumes from intent: OCC volume, keep-outs, the UI (click, transparent volume, cap, accept, partner offer); G1 | 3-4 days |
| M2 | Rib library (spokes, rings, parallel) and physics sizing on the voxel solver, on screen | 3 days |
| M3 | CP-SAT patterns with symmetry, spacing, count, variety; on screen | 2 days |
| M4 | Ribs as exact solids → STEP → C3D10 → cuDSS, reusing lane C; G2, G3 | 2 days |
| M5 | Load cases → families campaign; holes library; G4 | 2-3 days plus compute |

**Later:**

- continuous refinement of kept ribs' angles and positions (MMC-style feature mapping on the same
  voxel solver);
- GET, if its code appears, as a discovery lane whose recurring shapes become new library families;
- root fillets;
- casting checks (draft direction, hot spots).

## 9. The agent: decides design moves, checked by CAE

Every step above is a tool with typed inputs and outputs - the same tool the screen's buttons call -
so the agent can do anything the engineer can do on screen, and everything it does shows on the
same cards. **The agent owns intent, planning, explanation and learning; tools own geometry, physics
and the rules.**

**The loop.** One published result shaped it: an agent that writes a part's CAD code, has it
rendered, meshed and solved, and reads back **typed pass or fail against every requirement, with
the measured margin**, then revises
([Self-Improving CAD Generation Agents with FEA as Feedback, 2026](https://arxiv.org/html/2605.17448v2)).
Its findings:

- first attempts almost never pass: 0 of 20 single parts;
- one round of FEA feedback adds about 13 points on average;
- ten rounds reach 60.5 % of requirements met, at 68 minutes a design;
- feedback helps when it is concrete - margins, not advice;
- the weak part is the agent writing geometry itself;
- nothing carries over from one task to the next.

Here the agent never writes geometry: the library, CP-SAT and OpenCascade always give valid CAD.
It decides the **design move**, and CAE checks it:

```text
requirements - from the drawing, the deck and the engineer:
  seat tilt <= x', seat motion <= y mm, stress <= allowable, added mass <= m
        |
agent picks a move  ->  tools run it: sizing -> CP-SAT -> STEP -> C3D10 -> cuDSS
        ^                                              |
        +---- typed verdicts with margins: "main seat tilt 2.1' against 1.5': fails by 40 %"
```

**Moves the agent may make on its own**, within the volumes, rules and compute budget the engineer
approved:

- add or drop a rib family: a ring when the seat's tilt fails, rings dropped when they carry under 5 %;
- more metal when stiffness fails, less when it passes with room to spare;
- change the rib count or the range of thicknesses;
- weight the load cases differently, or ask CP-SAT for more or different alternatives;
- stop when every requirement passes, or when three moves in a row gain under 2 %.

**Moves that wait for the engineer:**

- changing a design volume;
- relaxing a hard rule - one from the drawing or the engineer, such as allowing asymmetry;
- accepting a design as final.

**Never the agent's:** geometry, loads, supports, material, the checks themselves. Tools own those,
so every verdict can be run again and give the same answer.

**Beyond the paper: learning across tasks.** Every move is kept with its situation and outcome -
*"thrust case, seat tilt failing by 40 %: a ring gained 4 %; spokes 30-60 deg from the load gained
55 %"*. In the next study, or on the next part, the agent recalls what worked in situations like
it before choosing, so its first moves get better. Once a surrogate exists, it predicts a move's
outcome in milliseconds: the agent tries moves on the surrogate, and real CAE checks only the
promising ones.

**What else the agent does:**

| where | the agent's job | why no form or code can |
|---|---|---|
| design volumes | from *"ribs between the main bore and the barrel, up to the bore's top, both ends of the shaft"*: the faces, the cap, the partner at the other end - shown for the engineer to accept | it takes things named by their role, read off the deck and the drawing |
| keep-outs | the drawing's notes and the deck read into keep-outs, citing the page | documents turned into checkable rules |
| load cases | the cases and budgets a study needs for the coverage the surrogate wants | planning a study from a brief |
| the library | where the free load-path map carries metal no family covers, a new family proposed - a chord between two anchors - for the engineer to accept | how the system finds patterns it was not given |
| explanation | "why 6 spokes?": each rib taken out in turn, re-solved on the voxels in seconds, and answered in numbers | explaining across many designs |
| objections | *"no rib within 30 mm of the oil port"* becomes a CP-SAT rule, with how many patterns it removes | free words into exact rules |
| failures | a fuse or a mesh that fails: the log read, only approved repairs applied, what was done recorded | diagnosis across many failed runs |

**How the agent is judged:** a fixed set of requests with expected results. For example, *"ribs
between the main bore and the barrel up to the bore's top, both ends"* must give the volumes the
engineer's own clicks give, every run. Measured: correctness, agreement across runs, time, and
cost against doing it by hand.

## 10. Risks and open questions

- **Smeared thickness at 8 mm.** A 20 mm rib is two or three cells. The sizing only ranks ribs,
  and every design is judged in C3D10, but the ranking should be checked once against TET10 on
  the production ribs (part of G2).
- **What turns inside** is not in the data. The engineer's cap and the optional clearance cylinder
  stand in for it.
- **OCC robustness** on the air-minus-part boolean over the housing's 1,753 faces. If it is slow,
  the air is computed once per project and each proposal intersects it.
- **One load case in the deck.** Families need more cases: the loaded groups alone and in mixes,
  agreed with the engineer.
- **Symmetry is a choice:** enforced where asked, offered where the loads are nearly symmetric,
  never assumed.
