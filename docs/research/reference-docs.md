# The three strategy documents in `docs/`

What each decides and leaves open for the next phase - mesh, solve, dataset, surrogate, agents,
positioning.

- **A:** `docs/Neural Concept EV Powertrain Role  GRC Gearbox Demonstration Strategy.md`
- **B:** `docs/End-to-End CAE + Physics-AI Portfolio for Neural Concept.md`
- **C:** `docs/physical_ai_cast_housing_design_generation_research.md`
- **D:** `docs/I want to reduce computational time of build and m.md`

A and B are plans for applying to Neural Concept roles; C is about fastcae's own problem; D is a
study of how to shorten the build and the mesh. None of A-C sets a numeric accuracy target, and none
covers meshing a design that exists only as a distance field.

## A. The EV powertrain role: the GRC gearbox strategy

**Purpose.** A plan for Neural Concept's "EV Powertrain: Applied AI Engineer" role (hiring may include
a coding challenge, a home project or a technical interview, then an on-site assessment). It reads the
role as a "vertical workflow builder, not primarily a foundation-model researcher".

**Timeline.** 12-16 weeks, no calendar deadline: reproduce the baseline (1-2); legal variants (3-4);
mesh and solver pipeline (5-6); "static/modal dataset campaign" (7-8); scalar and field surrogates
(9-10); optimisation and verification, one retraining cycle (11-12); recovery agent and interface
(13-14); motor/system extension and packaging (15-16).

**Deliverables.** A 2-minute video, a technical walkthrough, a repository with a fast reduced example;
an architecture decision record on "why agents do not own CAD or physics assumptions"; a
customer-discovery brief, model and dataset cards, a failure runbook, a validation report and a
roadmap.

**End goal:** "ship a complete gearbox/EDU vertical solution", not "train a PhysicsNeMo model on a
gearbox".
- Outputs: a Pareto set over mass, interface compliance and misalignment, modal separation, and
  harmonic vibration or equivalent radiated power; displacement and stress fields; design-driver
  explanations; confidence and out-of-domain status; verification evidence and an audit trail.
- An engineering contract: load cases `rated_torque_equivalent`, `non_torque_rotor_load`,
  `rotating_planet_or_bearing_load_phase`; protected bearing seats, ring interface, trunnion mounts,
  sealing faces, bolt holes; `solver: code_aster`, `require_high_fidelity_rerun: true`; no load values -
  they must be "traceable to a source or clearly marked assumptions".
- Simulation order: static, then modal, then harmonic via modal reduction, then radiated power.
- A surrogate ladder: gradient boosting or MLP, a multi-task model, a MeshGraphNet field model,
  ensemble or calibrated uncertainty. "The platform must still compute mass exactly from geometry."
- A dataset record per design: CAD hash and parameters, entity map, mesh with metrics and hash,
  materials, supports, loads and solver version, metrics and fields, failure class, split, parent,
  verification status.
- Optimisation: "Do not submit the single surrogate optimum as the answer" - verify a diverse Pareto
  set plus uncertain points, add them to the data, retrain until predefined stopping criteria.
- Limits: the GRC is a wind-turbine gearbox, an "electrified-drivetrain analogue"; never claim "Fully
  autonomous engineering approval".

## B. The crash portfolio

A portfolio for a crash/impact role. The flagship: an OpenRadioss bumper beam hitting a pole with 5-8
variables; the public 131-run set, then 200-500 own runs keeping failed runs with their labels;
CarCrashNet and SHIFT-Crash for scale. Models: XGBoost/MLP, a POD/PCA field baseline ("whether a deep
geometry model is truly adding value"), then MeshGraphNet/Transolver/GeoTransolver, with a failure
classifier and ensemble or conformal uncertainty. Tooling: VTP/Zarr, metrics in Parquet, a
`manifest.json` per run; BoTorch keeping "hard physics/geometry constraints outside learned
acquisition". Verification: coupon tests, baseline reproduction, three or more mesh resolutions,
monotonicity checks, a cross-solver check. "The surrogate proposes and ranks designs; it does not
certify them."

## C. Cast-housing design generation research

A deterministic "design compiler": a variant is the base part plus a rib connection graph,
continuous parameters, wall/boss thickness fields, holes, conditional pads and material. "Do not create
a library of predefined rib motifs and randomly perturb their parameters." Rib topology from CP-SAT,
graph moves, crossover and quality-diversity emitters, X-junctions forbidden by construction;
continuous values by Sobol or Latin hypercube; every rule keeps its source. Validation cheapest first
(relative cost): rules 1, proxy geometry 5, exact CAD build 50, castability 100, coarse mesh 300,
production mesh 1,000, solver 2,000-20,000. Mesh from exact CAD (Gmsh/HXT, Netgen, fTetWild as a flagged
fallback); CalculiX the baseline solver. A pyribs archive over 7 measures fed by 10 emitters; the final
pick maximises spread. About 20 review cards a round. Operations: Prefect or Dagster with Ray, Git plus
DVC then lakeFS, PostgreSQL, Parquet; a design's identity is its recipe hash. "An LLM must never
silently determine ... whether a design is castable." Active learning keeps "a fixed random
exploration fraction". It varies the alloy - which conflicts with fastcae's rule that a part is cast in
one material; fastcae keeps one material.

## D. Shortening the build and the mesh

**What it proposes.** Delete work before speeding it up: skip contouring when meshing from the field,
cache the part's field and search structure per part, express pads and moved faces as distance
primitives, split checks into parameter, field and mesh levels; answer CGAL's field questions in
compiled C++ with the GIL released and TBB threads; tune CGAL's sliver passes; morph a reference mesh
for designs of the same topology; sparse narrow-band fields (OpenVDB, NanoVDB); a staged runner with
persistent workers, one GPU owner and bounded queues; fewer high-fidelity solves through
multi-fidelity active learning; at least two GPUs for a four-to-six-hour end-to-end campaign.

**What checked out, and what fastcae took.** Answering CGAL's questions in C++ - the field mesh went
from 46 s to 4-8 s at the same settings ([field-meshing-gate.md](field-meshing-gate.md)); CGAL's
`Parallel_tag`, its default sliver passes, gmsh's thread options, Warp's kernel caching, OpenVDB's
composition and VTK Flying Edges' speed are as it says. The staged runner and deleting work (the
surface drawn only when a design is opened, floors never thickened) are in the plan.

**What does not apply.** Morphing needs every design to keep the same topology; fastcae's ribs appear
and disappear. Multi-fidelity pays when high-fidelity solves are dear; at about a minute a design they
are not ([surrogates.md](surrogates.md)). Contouring cannot simply be skipped today: the labels, two
checks, mass and the viewer read the surface - labels and mass move to the CAD faces and the mesh.

**Its sources.** Eight footnotes point to pages that do not support the claim beside them - every
CGAL claim cites a meshio issue, gmsh cites a piwheels page, Warp's caching a ParaView plugin, PyGeM
a different project, fTetWild a vcpkg port, CutFEM a GitHub topic, Dask the meshio repository,
OpenVDB's composition the mesh-to-volume header - and three links are dead. Its claims were checked
against the tools' own documentation instead ([data-factories.md](data-factories.md)).

## Decided across them, and left open

**Decided:** meshing with frozen production settings and quality gates; an open-source solver as the
authority, static and modal first; the study template owns loads and supports; failed runs kept with
their failure class; an immutable record per design, the recipe hash its identity; splits by design
family, never random; mass computed exactly; out-of-domain designs routed to FE; every Pareto pick
verified and fed back; agents bounded and approval-gated.

**Left open, and settled since** in [../build-plan.md](../build-plan.md): meshing a distance field;
Code_Aster or CalculiX; what the designs are solved for; accuracy and stopping rules; the surrogate's
input; orchestration and storage; agent scope; positioning.
