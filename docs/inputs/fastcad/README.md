# fastcad docs

fastcad is an agent-native product. It edits a customer's existing production CAD into many variants, each one manufacturable and each checked by FE analysis. The NREL GRC gearbox rear housing (drawing 254492) is the first demo part. It is not the product: the system must work on other housings and parts too.

**Status, 2026-09-16:** planning. The plan of record is waiting for the user's confirmation. No code has been written.

## Start here

| Document | What it holds |
|---|---|
| [fastcad-v1-plan.md](fastcad-v1-plan.md) | The plan of record: principles, inputs, outputs, pipeline, what varies, checks, physics, agent, geometry-kernel bake-off, code, demo, milestones, the user's action items |
| [decisions/grilling-decision-log.md](decisions/grilling-decision-log.md) | Every decision question (Q1–Q33): its options, the recommendation, the user's answer, and the facts that changed recommendations along the way |
| [decisions/decision-rationale.md](decisions/decision-rationale.md) | For each key decision (R1–R24): why we took it, the evidence and its source, how others do it differently, and what would make us revisit it |
| [inputs/user-vision-and-notes.md](inputs/user-vision-and-notes.md) | What the user brought to the session: the original brief, their two long sets of notes, the posts they shared later, and every link they supplied |
| [fastcad-positioning.md](fastcad-positioning.md) | Our approach in five points, and how fastcad compares with 21 papers and tools, commercial platforms and startups: what we take from them, what we skip |
| [status.md](status.md) | **Where the work stands right now**, what is settled and how, and what happens next |
| [next-steps.md](next-steps.md) | The step list: the M0 steps in order, M1–M5, and the user's action items |

## Research

Index: [research/README.md](research/README.md)

| Document | What it holds |
|---|---|
| [research/housing-to-gear-misalignment.md](research/housing-to-gear-misalignment.md) | Every piece of evidence on how housing variants change bearing-seat motion, gear misalignment and microgeometry: KISSsoft, AAM, the NREL GRC reports, GRC-specific cautions, our own measured seat tilts and gear-mesh leads, and tables linking each variant to its effect |
| [research/linkedin-posts.md](research/linkedin-posts.md) | The 16 LinkedIn posts the user shared: who wrote each, what it claims, how relevant it is |
| [research/methods-landscape.md](research/methods-landscape.md) | Academic and open-source methods up to September 2026: LLM CAD, B-rep generators, drawing reading, ways to generate variants, plausibility scoring, ranked building blocks |
| [research/industry-practice-dfm-vendors.md](research/industry-practice-dfm-vendors.md) | How gearbox housings are varied in industry, casting design rules (DFM), the vendor landscape, how surrogate datasets are built |
| [research/paper-reviews.md](research/paper-reviews.md) | Full reviews of the 21 papers, repos and benchmarks the user sent |
| [research/platforms-and-kernels.md](research/platforms-and-kernels.md) | Onshape, SolidWorks, NX, Autodesk, CATIA, CGM, other kernel SDKs, FreeCAD and Houdini: can they do our operations, and at what cost and limits? Also covers OpenCascade's documented limits and a design for an operator layer that works on any kernel. |
| [research/startups-and-ntop.md](research/startups-and-ntop.md) | 20+ companies (MecAgent, Leo, Adam, Nebula, the SimScale agent, nTop, Synera, Neural Concept, PhysicsX and others), GPT-6 Astra, the V-model mapping of engineering-AI startups, an analysis of nTop's 70–80% claim with the yield metrics we should publish instead, and what solvers SimScale uses |

## The GRC demo part

| Document | What it holds |
|---|---|
| [grc/data-inventory.md](grc/data-inventory.md) | What `cae-data` holds, how the GB2 and GB3 housings relate, the parts around the rear housing, gear and bearing data, loads, material, the proposed `assets/` layout |
| [grc/rear-housing-254492.md](grc/rear-housing-254492.md) | Geometry and drawing analysis of the production STEP: interfaces, bolt patterns, design style, draft, how editable the B-rep is, CAD-to-drawing mismatches |
| [grc/baseline-deck.md](grc/baseline-deck.md) | The Code_Aster baseline deck, fastcae's machinery for using it, the production-housing solves from the meshing gate study, what a variant deck generator must do |

## Prior work and environment

| Document | What it holds |
|---|---|
| [prior-work/fastcae-and-agenticcae.md](prior-work/fastcae-and-agenticcae.md) | Code map of the two existing repos: what each does, what to reuse, what to leave behind |
| [environment.md](environment.md) | The machine, installed tools, Python environments, solvers and meshers, data locations, and outputs that will be deleted if not preserved |

## Superseded

- [grc-rib-plan.html](grc-rib-plan.html): the 2026-09-11 rib plan. It added ribs to the rib-free housing using signed-distance-field (SDF) blending, with a GPU voxel check and CalculiX. The v1 plan replaces it.

## How the research was done

The research was done on 2026-09-15 and 2026-09-16 by background research agents using web search and reading local files.

- Repositories and `cae-data` were only read, never changed.
- Quarantined material was never opened: files matching `*54530*` and the OEDI-738 vibration data.
- Every fact carries its source where one exists, and inferences are marked as inferences.
- Some documents were read through a summarising fetch tool; key figures were re-checked against the original wording.
- The raw outputs (scripts, JSON, renders) are in the session's Temp scratchpad, which gets cleared. The paths are listed in [environment.md](environment.md); saving them is the first task of milestone M0.

## Glossary

- **Baseline, canvas:** the production part fastcad edits. Here, the closed STEP of 254492, including its ribs.
- **Interface:** faces that must fit other parts: bearing bores, pilots, flanges, bolt patterns, datums. Interfaces stay frozen within a campaign.
- **Interface map:** the signed-off list of interfaces. Each is stored as a typed frame: origin, axis, reference, label, tolerance.
- **Design language, style:** measurements taken from the baseline: wall and rib thicknesses, fillet sizes, draft and pull directions.
- **Operator:** a pre-written, tested, deterministic geometry tool, such as "add collar", "add bridge" or "re-bore". The agent calls operators through MCP.
- **Architecture class:** one kind of structural idea: collar, radial ribs, inter-bore bridge, tie rails, bore-to-flange path, belt, windowed web, or a hybrid of these.
- **Moved interface:** an interface that a campaign changes: a new bore diameter or position, a moved mount, or a larger envelope.
- **Campaign:** one run from a Requirement Spec to a set of variants.
- **Requirement Spec:** the typed form of the customer's brief, after clarifying questions, signed off before the campaign runs.
- **Silent-failure oracle:** the check run after every operation:
  - the result is a valid solid;
  - its volume changed by the expected amount;
  - nothing changed outside the edited region;
  - a mesh of it is consistent inside and out.
- **Deck:** the FE solver input files: Code_Aster `.comm`, `.med` and `.export`. Each variant's deck copies the baseline deck exactly.
- **Fingerprint:** the numbers used to judge how different variants are:
  - deck results (seat motions and tilts, gear-mesh lead misalignment, stresses);
  - mass;
  - geometry descriptors.
- **Rework check:** does a changed interface fit inside the existing casting's metal, so it can simply be machined, or does it need a new casting pattern?
- **Round-trip test:** move an interface, then move it back. The result must match the baseline within 0.2 mm.
- **RBE3:** a coupling that spreads a bearing seat's load over the seat's mesh nodes.
- **TET10:** a 10-node tetrahedral finite element.
- **CP-SAT:** the constraint solver in Google OR-Tools. We use it to enforce rules and force diversity.
- **GSM:** geometric signature matching. It finds the same face in two models by comparing geometry (type, size, position, normal), not by face number.
- **LSS, IMS, HSS, PLC:** low-, intermediate- and high-speed shafts of the GRC gearbox, and its planet carrier. Their bearings are named after them, e.g. PLC-B, ISS-A, HSS-B/C.
