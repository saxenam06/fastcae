# fastCAD — End-to-End Build Document

## 1. Executive Summary

fastCAD is an **autonomous, constraint-governed engineering simulation-data factory**. It ingests one trusted CAE case, learns its engineering context, lets an engineer approve how that design may vary, then generates diverse, feasible, traceable geometry variants, solves them, and produces AI-ready simulation records. The first demonstration part is the NREL Gearbox Reliability Collaborative (GRC) rear housing (drawing 254492), but the architecture is part-agnostic by construction.

Stage 1 explicitly **excludes natural-language CAD editing**. The single Stage-1 objective is: *generate many geometry variations and their resulting solved training data, as reliably and autonomously as possible.* Agents provide intelligence at the level of planning, orchestration, failure recovery, and active learning — never at the level of improvising geometry or touching numerical kernels.

The product's defensible value is not the ability to add a rib. It is the ability to take **one trusted simulation** and industrialize it into **hundreds of qualified design/physics records** while preserving engineering meaning, manufacturability, and provenance.

## 2. Problem Statement and Scope

The task is to convert a validated gearbox-housing CAE model into a rich, feasible family of variants and their solved outputs, suitable for training surrogates that predict bearing-bore motion, gear-mesh misalignment, and related quantities. The GRC housing is the anchor; the system must run a second part with no part-specific code paths.

### In-scope (Stage 1)

- Deterministic ingestion of CAD, drawing, mesh, solver deck, and baseline result.
- Deterministic feature extraction with explicit coverage reporting.
- Human confirmation of interfaces, mutable regions, and semantic names.
- A typed, versioned Design Contract as the single source of truth.
- Exact B-rep local variant generation under constraints.
- CAD-conforming meshing that preserves bearing-seat geometry.
- Physics inheritance, solver execution, and numerical qualification.
- Accepted simulation records with full lineage.
- Agentic campaign planning, failure recovery, and active learning.
- A surrogate baseline trained only on qualified records.

### Out-of-scope (Stage 1)

- Chat-to-CAD or free-form natural-language geometry editing.
- LLM-generated geometry code executed on the kernel.
- Automatic invention of engineering semantics.
- Field/voxel geometry used as trusted analysis geometry.
- Agents modifying meshes or solver matrices.

## 3. Product Positioning and Differentiation

The market splits the problem: implicit/parametric generation is mature (nTop for field-driven implicit modeling; CadQuery/build123d for authored parametric B-rep), and meshing-oriented feature recognition exists (Coreform Cubit), but no single library performs recognition plus large constraint-respecting variant editing plus frozen interfaces plus an FEA loop on foreign production castings.

The differentiation is therefore integration and governance, not any single geometry trick:

| Competitor center of gravity | fastCAD differentiation |
|---|---|
| CAD systems author exact production geometry | Govern how an existing validated design may vary |
| nTop builds powerful implicit/field workflows | Convert a validated CAE case into solver-qualified variants and records |
| DOE tools vary declared parameters | Create topology-changing variants preserving engineering context |
| SimAI/PhysicsAI learn from existing data | Generate and qualify the missing training data upstream |
| Cloud CAE executes simulations | Decide what to generate, whether it is valid, and whether its data is trustworthy |
| PLM/SPDM manage files | Produce accepted simulation records and lineage |

The moat components are: topology-aware transfer of loads/constraints/entities; separation of imported, derived, and generated information; reproduction certificates rather than vague agreement scores; simulation lineage and accepted-record schemas; automatic detection and controlled repair of failed variants; surrogate domain-of-validity with solver fallback; and private deployment around existing CAE investment.

## 4. Guiding Principles

1. **Topology variation over dimension sweeps.** Richness comes from architecture classes and feature composition, not from many values of one rib height.
2. **Provenance on everything.** Every visible object is imported, derived, or generated, and says so.
3. **Never invent semantics.** Preserve source entity names (for example a solver-deck group) until an engineer maps them.
4. **Interfaces are frozen within a campaign** unless the contract explicitly declares a moved interface.
5. **Exact geometry is the trusted analysis path.** Fields are for reasoning and screening only.
6. **Agents plan; deterministic tools execute.** The agent is the brain, the engines are the hands, the solver is the numerical engine, and the customer solver is the reference.
7. **Only qualified records become data.** A completed solve is not automatically training data.
8. **Part-agnostic core.** No housing-specific names hardcoded in core services.

## 5. System Architecture

```text
Customer input package (CAD + drawing + mesh + deck + baseline result)
                         v
Deterministic extraction  ->  Canonical Engineering Model
                         v
Human confirmation  ->  Versioned Design Contract
                         v
Typed operator + parameter catalogue
                         v
CP-SAT feasibility  ->  Portfolio planner  ->  Active-learning planner
                         v
Local B-rep variant generation
                         v
Geometry qualification (silent-failure oracle + fidelity contract)
                         v
CAD-conforming mesh (protected islands reused)
                         v
Physics-transfer audit
                         v
Solver + numerical qualification
                         v
Accepted Simulation Records  ->  Coverage analysis  ->  Surrogate + active learning
```

The **Canonical Engineering Model** and **Design Contract** form the control plane; every artifact and agent decision references a contract version.

## 6. Typed Vocabulary (Shared Ground Truth)

One vocabulary is shared by UI, API, and Agent. Pydantic v2 models are authoritative on the backend; TypeScript types are auto-generated so UI and API cannot drift.

### Core schemas

```python
class InterfaceFrame(BaseModel):
    id: str
    label: str                 # conversational name, engineer-confirmed
    kind: Literal["bearing_seat","pilot","flange","bolt_pattern","datum","seal"]
    origin: Vec3
    axis: Vec3
    reference: Vec3
    radius: float | None
    axial_bounds: tuple[float, float] | None
    tolerance: float
    provenance: Literal["imported","derived","generated"]

class DesignContract(BaseModel):
    baseline_id: UUID
    contract_version: str
    frozen_interfaces: list[InterfaceFrame]
    mutable_regions: list[MutableRegion]
    allowed_operators: list[OperatorPermission]
    parameters: list[ParameterDomain]
    logical_constraints: list[Constraint]
    geometry_constraints: list[GeometryConstraint]
    manufacturing_constraints: list[ManufacturingRule]
    physics_transfer_rules: list[PhysicsRule]
    campaign_objectives: list[CampaignObjective]
    approval_status: Literal["DRAFT","APPROVED","SUPERSEDED"]

class VariantRecipe(BaseModel):
    baseline_id: UUID
    contract_version: str
    architecture_class: str
    operations: list[OperatorCall]
    expected_outcomes: list[ExpectedOutcome]
    parent_variants: list[UUID]
    planner_reason: PlannerReason

class StageResult(BaseModel):
    stage: PipelineStage
    status: Literal["PASSED","FAILED","QUARANTINED"]
    metrics: dict[str, float]
    artifacts: list[ArtifactReference]
    failure: FailureRecord | None
    retry_options: list[RetryPolicy]

class AcceptedSimulationRecord(BaseModel):
    variant_id: UUID
    baseline_id: UUID
    contract_version: str
    recipe: VariantRecipe
    geometry_checks: GeometryQualification
    mesh_checks: MeshQualification
    physics_audit: PhysicsTransferAudit
    solver_checks: SolverQualification
    scalar_outputs: dict[str, Quantity]
    field_outputs: list[FieldArtifact]
    bearing_motion: list[BearingMotion]
    gear_misalignment: list[GearMeshMisalignment]
    training_status: Literal["ACCEPTED","QUARANTINED","REJECTED"]
```

## 7. Extraction Pipeline and Reality Bands

Extraction runs automatically on upload, scoped to the files the user selects. Each detected entity carries provenance and a confidence, and unrecognized geometry is reported as such rather than invented.

| Band | Entities | Method | Human effort |
|---|---|---|---|
| High reliability | Cylindrical bearing bores, bolt circles, planar flanges, datums | Deterministic OCCT topology + fitting | Confirm names |
| Medium reliability | Bosses, pockets, fillets, cones, walls | Heuristics + thresholds | Confirm/correct |
| Low / none today | Ribs, webs, gussets, functional groupings | Requires a dedicated motif detector | Label until detector matures |

The known gap is explicit: cones, bosses, and bores are not fully extracted, and ribs are not recognized at all. Stage 1 therefore ships a dedicated rib/motif detector and, where detection is uncertain, uses human labeling captured as typed data so the labels become reusable training signal rather than throwaway clicks. A `CoverageReport` shows exactly what was detected, what was labeled, and what remains unknown.

## 8. UI Design

The UI behaves like an engineering campaign configurator, not a modeling canvas or a chatbot. Tabs are Input, Design Contract, Generate, Campaign, Dataset, and Surrogate.

- **Input**: upload/select files; per-file extraction status; 3D views of CAD, mesh, BCs, loads, and results; a **selection bus** so clicking an entity in any tab co-highlights its linked entities in the others; rename and role-confirm entities.
- **Design Contract**: frozen-interface list, mutable-zone selection, approved operator cards (each backed by a Pydantic model), parameter ranges, manufacturing rules, physics-transfer rules, campaign goals, and an explicit Approve action.
- **Generate**: architecture-class selection, combination counts, CP-SAT feasibility summary, candidate-diversity visualization, recipe/geometry preview, and reject/pin/approve.
- **Campaign**: geometry/mesh/solve states, failure reasons, retry/quarantine decisions, pass-yield by architecture, runtime, and dataset-ready count.
- **Dataset**: accepted/quarantined/rejected records, coverage by architecture and parameter, output distributions, lineage, and export.
- **Surrogate**: training status, held-out-architecture validation, uncertainty/OOD coverage, ranking mode, and active-learning suggestions.

No chat interface is required in Stage 1.

## 9. API and UI-API-Agent Contract

The backend is FastAPI + Pydantic v2. Every endpoint speaks the shared schemas. The agent receives a typed `ContextEnvelope` carrying the active tab, selected entities, and highlighted region so that when a user highlights something, the agent operates in that exact context.

```python
class ContextEnvelope(BaseModel):
    active_tab: str
    selected_entities: list[str]
    highlighted_region: str | None
    contract_version: str
    baseline_id: UUID
```

User renames and new rules become **binding** by producing a new `DesignContract` version; all subsequent agent and pipeline actions cite that version. This is how the UI, API, and Agent share one language.

## 10. Geometry Generation Strategy

Exact B-rep local operators on the imported STEP are the trusted path. Fields are used only for clearance, thickness, collision, layout planning, and cheap plausibility scoring — never as the final analysis geometry for misalignment data.

```text
Imported STEP -> protected/mutable region map -> add/cut local parametric solids
             -> boolean fuse/cut -> local healing -> protected-interface comparison -> STEP variant
```

### Operator library (compact but rich)

- **Additive**: external bearing collar, straight rib, curved rib, bore-to-wall rib, bore-to-flange rib, bore-to-mount rib, inter-bearing bridge, X/K-braced bridge, front-rear tie rail, circumferential belt, reinforcement pad, split-line/flange reinforcement.
- **Subtractive**: rounded window in a generated web, pocket in an approved zone, local scallop, core in a generated thick feature.
- **Transformational**: rib thickness/height, taper, path adjustment, local wall offset, pattern count, blend radius, draft angle.

Richness derives from architecture composition (operator x anchor x parameters x symmetric/biased x pattern), which yields topology diversity from roughly 8-12 operators rather than a full CAD command set.

## 11. Constraint Solving with CP-SAT

CP-SAT (OR-Tools) governs discrete and discretized decisions only: feature presence/count, architecture compatibility, parameter levels, dependencies, symmetry, keep-out compatibility, and manufacturing configuration rules. Continuous dimensions are discretized to integer units.

CP-SAT does **not** certify geometric, manufacturing, or structural feasibility. When exact construction invalidates a nominally feasible candidate, the failure is fed back as a no-good constraint:

```text
NOT( BossRegion = 3 AND BossDiameter = 40 AND RibHeight = 28 )
```

Three planners cooperate: a **constraint planner** (CP-SAT feasibility), a **portfolio planner** (maximize coverage/diversity), and an **active-learning planner** (maximize information value after data exists).

## 12. Meshing and Interface Integrity

The prior CGAL-on-implicit-field route smoothed edges and altered bearing-seat cylinders, which is fatal for bore-tilt work because misalignment depends on the motion of exact seat nodes. The corrected approach meshes the actual B-rep with Gmsh so analytic cylinders, sharp edges, and named faces become conforming physical groups.

Key pattern for frozen interfaces:

```text
Freeze bearing islands -> mesh each island ONCE (reuse across variants)
Cut variant body at fixed transition surfaces -> mesh only the mutable bulk
Join by conformal shared nodes (imprint/merge) OR tied interface
Verify seat node IDs, coords, cylinder-fit residual, coupling weights UNCHANGED
```

This guarantees predicted bore motion changes because stiffness changed, not because the mesh or seat geometry changed.

### Mesh recovery ladder

```text
Gmsh CAD mesh -> quality gate
  fail -> MeshFix -> libigl remesh/refine -> fTetWild (flag lower fidelity) -> QUARANTINE with reason
```

This ensures the agent never acts on silently broken tools.

## 13. Moved-Interface Regimes

When variants change bores or size, the same stack applies but engineering-validity rules dominate.

| Regime | Change | Added logic |
|---|---|---|
| A. Frozen | Ribs/walls/bridges only | Island freeze |
| B. Bore diameter | Seat Ø changes, axis fixed | Re-bore operator + rework (machinable vs new casting) check |
| C. Moved centre | Centre/axis relocates | Centre-distance update, coaxiality, assembly, re-baseline |
| D. Rescaled housing | Larger/smaller variant | Parametric rebuild + size as explicit input + non-dimensional comparison |

The decisive rule: if a bore moves, misalignment must be measured against the new per-variant nominal assembly, otherwise the surrogate learns "centre distance changed" instead of "housing distorts under load." Regimes are sequenced A, B, C, D — D is treated as a new family, not an edit of the original STEP.

## 14. Physics Inheritance and Extraction

Loads, constraints, materials, contacts, analysis steps, and output requests are inherited from the baseline deck under explicit applicability rules. A machine-readable audit precedes every solve; variants with incomplete or ambiguous physics assignment are blocked.

Bearing motion is extracted from a persistent `BearingSeatInterface` using a weighted least-squares rigid fit rather than ad hoc node averaging:

\[
\min_{\mathbf{t},\boldsymbol{\theta}} \sum_i w_i \left\| \mathbf{u}_i - \left( \mathbf{t} + \boldsymbol{\theta}\times(\mathbf{x}_i-\mathbf{x}_0) \right) \right\|^2
\]

Seat displacement is decomposed into rigid translation, rigid rotation, radial expansion, and ovalization modes; translation and rotation drive gear alignment while ovalization is tracked separately as a seat-integrity metric.

## 15. Solver Execution and Baseline Reproduction

Code_Aster runs each variant using a deck cloned exactly from the baseline with labels transferred by semantic interface. Before any campaign, the reconstructed baseline is compared against the reference solver across resultant loads, reactions, moments, displacement norms/extrema, strain energy, probe values, mapped fields, and mesh sensitivity — a reproduction certificate, distinguishing verification from validation.

Solver qualification checks normal exit, convergence, force/moment balance, finite displacements, energy consistency, output presence, and absence of NaNs before a result is eligible to become a record.

## 16. Accepted Simulation Records and Dataset

Records use three states: ACCEPTED, QUARANTINED, REJECTED; only ACCEPTED records train surrogates. Each record carries the variant definition, feature program, geometry/mesh/physics/solver checks, entity genealogy, scalar and field outputs, bearing motion, gear misalignment, and complete provenance, stored as Parquet/Zarr and versioned with DVC.

Primary GRC outputs: housing mass/volume; max displacement/stress; reaction balance; per-interface translation and rotation; relative seat movement along each shaft; relative pinion-gear axis tilt; centre-distance change; lead- and profile-direction mesh misalignment; optional condensed interface compliance; geometry/mesh quality descriptors.

Dataset validity is judged by coverage — parameter space, feature combinations, topology classes, boundary cases, and response distribution — not merely record count.

## 17. Agent and Orchestrator Design

Agents sit above deterministic tools and are invisible in Stage 1, running as a campaign controller with an inspectable audit panel.

| Agent | Responsibility | Hard boundary |
|---|---|---|
| Input | Report found/missing/inconsistent inputs | No invented semantics |
| Baseline validation | Run pipeline, diagnose reference vs reconstruction | No kernel edits |
| Campaign | Select architecture classes and diverse batches | Choose from typed options only |
| Execution | Schedule geometry/mesh/solve | No manual mesh commands |
| Recovery | Apply bounded, typed retry policies | Respect retry budget |
| Data | Accept/quarantine/reject records | No fabricated outputs |
| Optimization (later) | Propose next simulations from surrogate | Confirm via solver |

Recovery is a bounded state machine with a retry budget; every failure is stored as data and, where appropriate, converted into a CP-SAT no-good constraint or a training example for a failure-risk model.

## 18. Open-Source Technology Stack

| Layer | Primary OSS | Notes |
|---|---|---|
| Geometry kernel | OpenCascade via build123d / CadQuery | pythonOCC for low-level ops |
| Feature recognition | OCCT topology scripts + rib motif detector | ML later |
| Field/SDF (screening only) | libigl, OpenVDB, scikit-fmm | Not analysis geometry |
| Constraints | OR-Tools CP-SAT | Discrete/discretized only |
| Meshing | Gmsh (OpenCASCADE geometry, physical groups) | Preserves CAD identity |
| Mesh repair | MeshFix, libigl, PyMeshLab, fTetWild | fTetWild last, flagged |
| FE solver | Code_Aster (GPL) | CalculiX cross-check |
| Pre/post | meshio, PyVista, VTK | Field mapping/contours |
| Coupling/fit | NumPy/SciPy | RBE3-equivalent distributing coupling |
| Surrogate | scikit-learn, XGBoost, then PyTorch/PyG | Simple baselines first |
| Records | pyarrow (Parquet), Zarr, DVC | Provenance + versioning |
| Orchestration | LangGraph or state machine + FastMCP | Agent above tools |
| API | FastAPI + Pydantic v2 | Typed contract |
| UI | React + TypeScript + three.js / VTK.js | Selection bus |
| Schema sync | pydantic to TypeScript (datamodel-codegen) | One vocabulary |

Licensing to verify: Code_Aster is GPL and fTetWild's license must be checked before commercial distribution.

## 19. Repository Change Plan

New and modified modules on the existing layout:

```text
src/fastcad/
  schemas/       Pydantic models + TS generation           NEW
  ingest/        OCCT read/heal/tessellate                 EXTEND geometry.py
  recognize/     bores, bosses, ribs, bolt patterns        EXTEND regions.py + ribs.py NEW
  interfaces/    ProtectedInterface, islands, frames        NEW (critical)
  partition/     cut islands, transition surfaces           NEW (critical)
  contract/      DesignContract + CP-SAT compile            NEW
  ops/           base protocol + collar/rib/bridge/pad      NEW (B-rep, local only)
  mesh/          Gmsh CAD-conforming, island reuse          REPLACE CGAL path
  meshfix/       recovery ladder + quarantine               NEW
  fe/            deck clone + Code_Aster run                EXTEND deck.py
  extract/       coupling, rigid-fit, distortion modes      NEW
  oracle/        silent-failure + fidelity contract         NEW
  records/       Parquet/Zarr writer                        NEW
  surrogate/     sklearn baseline then PyG                  NEW
  agent/         LangGraph nodes via MCP                    NEW
ui/src/          selection bus, contract editor, campaign   EXTEND stages
```

Perspective change: the repo shifts from a scripted read/reproduce demo to a governed, typed, self-checking generation-and-data platform.

## 20. Real Bugs and Risks to Fix

- Field/CGAL smoothing destroys bearing-seat cylinders and sharp features — replace with Gmsh-on-B-rep and protected islands.
- Silent volume loss at the HSS plane — enforce the silent-failure oracle after every operation.
- Post-fuse fillet failure across existing blends — rib operators build their own root fillet.
- Whole-body cuts unreliable on the canvas — use local cuts only.
- Incomplete extraction (cones/bosses/bores) and absent rib recognition — ship the motif detector and coverage report.
- Meshing failures previously required hand-crafted mesh2d/meshfix/mesh3d/fTetWild combinations — encode this as the bounded recovery ladder so the agent stands on solid tools.

## 21. Tests and Exit Criteria

| Area | Required proof |
|---|---|
| Geometry | At least four architecture classes generated |
| Constraint fidelity | Zero protected-interface violations accepted |
| Diversity | Topological diversity, not only dimensions |
| Geometry yield | >= 90% for approved envelopes |
| Mesh yield | >= 90% of geometry-qualified variants |
| Solver yield | >= 95% of mesh-qualified variants |
| Dataset integrity | Every accepted record has full lineage |
| Comparability | Bearing-motion extraction stable under mesh refinement |
| Recovery | Every failure typed with a bounded policy |
| Autonomy | Campaign completes without manual file editing |
| Generality | Second part runs with no part-specific code |
| Round-trip | Move an interface and back within 0.2 mm |

## 22. Development Milestones

- **M0 Baseline trust**: reproduce the GRC analysis; confirm entity mapping and provenance; freeze/classify interfaces; verify bearing-motion extraction; remove hardcoded housing names; lock conversational region names; resolve the canvas via blend-crossing-fillet and whole-body-cut tests.
- **M1 Generation rail**: typed schemas; operator protocol; collar/rib/bridge/pad operators; geometry oracle; 20 qualified dry-run variants.
- **M2 Data factory**: Gmsh meshing; physics-transfer audit; deck generation; solver qualification; accepted-record writer; first 40-variant campaign at target yields.
- **M3 Autonomy**: CP-SAT planner; diversity portfolio planner; bounded recovery; failure memory; scheduling; campaign-health UI.
- **M4 Richness**: curved ribs, X/K bridges, tie rails, belt/ring, windowed web, composition; >= 100 accepted simulations.
- **M5 Learning**: scalar surrogate; architecture-held-out testing; OOD/uncertainty; active-learning campaign; solver-confirmation policy.

## 23. Demo Design

Show a baseline reproduction certificate, then a 40-variant campaign spanning at least four architecture classes (for example radial boss support, inter-bore bridge, X-brace, windowed web), with a live campaign-health panel showing yields and typed failures, ending in a coverage map and a first surrogate ranking. Every displayed variant uses only features that are reliably extracted, reasoned over, and driven agentically in the loop, so the demo is impressive yet fully defensible.

## 24. Conclusion

fastCAD's success does not depend on natural-language CAD or on generating one beautiful part. It depends on reliably producing many qualified, comparable geometry-physics records from one trusted case, with agents supplying planning and recovery intelligence over deterministic engines. The corrected geometry and meshing strategy protects the exact bearing-seat definitions that gear-misalignment work requires, and the typed Design Contract makes constraints, renames, and rules the shared language of UI, API, and Agent. Building the feasibility rail before feature richness, and admitting only qualified records into the dataset, is what turns an interesting pipeline into a defensible engineering-data platform.