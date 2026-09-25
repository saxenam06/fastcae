# fastCAD — Final Consolidated Build Plan

## Constraint-Governed, Cost-Aware, Agentic Engineering Simulation Data Factory

**Document status:** Final Stage-1 build specification

**Primary demonstrator:** NREL Gearbox Reliability Collaborative (GRC) rear housing, drawing 254492

**First commercial wedge:** Automate governed structural design-family exploration from an existing trusted CAD/CAE baseline, producing solver-qualified datasets for stiffness, bearing-motion, and gear-misalignment-relevant engineering decisions.

**Primary Stage-1 target:** Produce 100–200 diverse, feasible, reproducible, and engineering-qualified geometry–simulation records. Demonstrate an unattended 40-variant campaign early, then prove the core is generic on a second housing or bracket without introducing part-specific branches in core code.

---

## 1. Executive decision

fastCAD is **not** a chat-to-CAD product, a generic CAD replacement, a free-form generative-CAD system, a generic topology-optimization tool, or an LLM wrapper around CAD/FEA commands.

fastCAD is a **constraint-governed engineering simulation-data factory**:

> Take one trusted engineering analysis, determine and confirm its engineering context, define exactly what may vary, generate meaningful structural alternatives, preserve engineering intent through CAD/mesh/physics changes, qualify every result, and turn accepted simulations into reusable AI-ready engineering data.

The Stage-1 product flow is:

```text
Trusted CAD + mesh + deck + result baseline
                    ↓
Deterministic extraction and normalized engineering model
                    ↓
Engineer confirmation of semantics and critical interfaces
                    ↓
Approved versioned Design Contract
                    ↓
Typed structural architecture and variant recipes
                    ↓
Exact local B-rep variant construction
                    ↓
Geometry and manufacturability qualification
                    ↓
CAD-conforming mesh with protected-interface integrity
                    ↓
Audited physics inheritance / deck construction
                    ↓
Solver execution and numerical qualification
                    ↓
Accepted / quarantined / rejected simulation records
                    ↓
Coverage analysis, feasibility models, surrogate models, active learning
```

The product moat is not “we can add ribs.” The moat is the governed conversion of a trusted CAE case into a **qualified, replayable, semantically traceable, reusable simulation dataset**.

---

## 2. Product thesis and boundaries

### 2.1 User problem

The target customer already has valuable engineering assets:

- Production or development CAD.
- A mesh and solver deck.
- Materials, loads, constraints, contacts, and output requests.
- A baseline result the organization considers credible.
- A need to explore many allowable structural alternatives.
- Insufficient time to manually edit CAD, remesh, repair solver decks, run campaigns, post-process results, and curate a dataset.
- A longer-term objective to train a surrogate, optimize a design, or build a digital-twin-grade response model.

The difficult problem is preserving engineering meaning while geometry changes. A new rib can split a face, delete a face, create a new load path, change mesh connectivity, invalidate a load mapping, or create a result that is numerically complete but physically incomparable. fastCAD exists to make those transitions explicit, testable, and auditable.

### 2.2 What fastCAD is

fastCAD is:

- A **design-family compiler**: it compiles an approved Design Contract and typed variant recipe into a candidate CAD/CAE model.
- A **simulation campaign control plane**: it plans, queues, observes, retries, and stops bounded campaigns.
- A **geometry, mesh, physics, and solver qualification system**: it does not treat successful file export or solver exit as success.
- A **lineage and provenance system**: it records how every geometry, mesh group, load, result, and model was derived.
- A **dataset factory**: accepted results become training-ready records; quarantined and rejected cases become engineering and failure evidence.
- An **agent-orchestrated deterministic workflow**: agents reason over structured evidence but do not directly certify high-consequence engineering facts.

### 2.3 What fastCAD is not in Stage 1

Explicitly exclude the following until the validated data-factory rail is complete:

- Free-form natural-language CAD editing.
- LLM-generated CAD kernel code that is executed directly.
- General-purpose parametric CAD authoring.
- Replacement for CATIA, NX, Creo, SolidWorks, nTop, or a customer’s CAE solver.
- Automatic invention of geometry, load, or functional semantics without human confirmation.
- Field-only, voxel-only, or SDF-only geometry as the trusted final representation for interface-sensitive FEA.
- Autonomous final-design approval.
- Full-field neural surrogate development before scalar response baselines and data integrity are proven.
- Moved-bore, moved-mount, or fully rescaled design regimes before frozen-interface campaigns work reliably.

### 2.4 Product positioning

| Existing product category | Typical center of gravity | fastCAD differentiation |
|---|---|---|
| CAD systems | Create/edit exact geometry | Govern how an existing validated design can vary without losing engineering context |
| Implicit/field modeling | Create field-driven or lattice-like geometry | Produce solver-qualified, traceable variants from a validated CAE case |
| DOE/optimization tools | Sweep declared parameters | Create topology-changing but contract-compliant structural variants |
| CAE solvers/cloud simulation | Solve individual jobs at scale | Decide what should be generated, whether its setup remains valid, and whether its data is trustworthy |
| AI surrogate tools | Learn from an existing dataset | Build the missing qualified dataset upstream |
| PLM/SPDM | Manage artifacts and process | Represent accepted simulation records, semantic lineage, and replay evidence |

### 2.5 The core promise

```text
One validated engineering case
        ↓
One approved governed design family
        ↓
Many structurally meaningful variants
        ↓
Many qualified comparable simulations
        ↓
A private proprietary engineering dataset
        ↓
Trustworthy response surrogates and active-learning optimization
```

---

## 3. Guiding principles

1. **Topology diversity beats parameter sweeps.** Forty values of rib height are not a strong campaign. A useful campaign spans multiple structural architecture classes and response mechanisms.
2. **Never invent semantics.** Imported names and groups remain imported facts until an engineer confirms their role.
3. **Interfaces are first-class engineering objects.** Bearing seats, mounting surfaces, seals, datums, bolt patterns, and load-transfer surfaces are not anonymous faces.
4. **Freeze what defines the measurement.** In the first campaign, modify surrounding stiffness but not the geometry or numerical definition of critical interfaces.
5. **Exact B-rep is the trusted geometry path.** Fields/SDFs may support screening, collision checks, candidate planning, and visualization, but not final interface-sensitive analysis.
6. **Agents plan; deterministic tools execute and certify.** The system must separate probabilistic recommendation from engineering authority.
7. **A completed solve is not automatically data.** Only qualified records may train response surrogates.
8. **Failures are evidence.** Store failure type, location, context, attempted recovery, and disposition; use them to improve future feasibility and recovery policies.
9. **Yield and coverage must always be reported together.** High yield achieved by avoiding hard areas is not a successful campaign.
10. **Part-agnostic core, part-specific configuration.** A new component gets a new baseline package, semantic confirmation, Design Contract, and rule configuration—not new product-core branches.
11. **Every result must be replayable.** A record without enough information to rebuild the geometry, mesh policy, physics mapping, and result is not a reliable record.
12. **Spend intelligence where it changes expensive engineering decisions.** Do not spend premium model calls on work deterministic geometry, meshing, solvers, or rules already know how to do.

---

## 4. Stage-1 outcome definition

### 4.1 Primary engineering target

Generate and solve 100–200 **accepted** GRC gearbox-housing variants from one approved baseline. The first operational demonstration should be a campaign of 40 variants without manual CAD or deck edits during campaign execution.

### 4.2 Required outcomes per accepted record

Each accepted simulation record must contain:

```text
Baseline identity and source artifact hashes
+ approved Design Contract version
+ typed VariantRecipe and parent genealogy
+ exact geometry artifact
+ entity lineage and protected-interface comparison
+ geometry qualification report
+ manufacturability report
+ mesh artifact and mesh-quality report
+ protected-island and coupling evidence
+ physics transfer/rebuild audit
+ solver deck, environment, and execution metadata
+ solver/numerical qualification report
+ scalar outputs
+ field outputs where retained
+ bearing-seat translation, rotation, ovalization, and fit evidence
+ gear-misalignment-relevant descriptors
+ campaign and planner context
+ deterministic replay manifest
+ ACCEPTED status
```

### 4.3 Dataset states

Use three mutually exclusive states:

| State | Meaning | Surrogate training eligibility |
|---|---|---|
| `ACCEPTED` | Passed all applicable geometry, mesh, physics, solver, and engineering qualification gates | Yes |
| `QUARANTINED` | Inconclusive, lower-fidelity, ambiguous, or requires review; preserve artifacts and evidence | No |
| `REJECTED` | Failed a hard gate or is outside the approved contract | No |

Quarantined/rejected cases are retained as failure and feasibility-learning data but must not silently enter response-surrogate training.

### 4.4 Stage-1 success criteria

The product has passed Stage 1 only when it can show all of the following:

1. A GRC baseline was imported, semantically reviewed, reconstructed, and reproduced with a documented certificate.
2. Critical interfaces are confirmed, stable, protected, and traceable across variants.
3. Several structural architecture classes can be proposed and compiled into typed recipes under an approved contract.
4. Deterministic tools can construct, mesh, map physics, solve, and qualify variants without manual CAD/deck editing during campaign execution.
5. Every failure has a typed cause, attached evidence, and bounded disposition/recovery policy.
6. Every accepted record has complete lineage, qualification evidence, and replay data.
7. The system reports coverage and yield by architecture family and parameter region.
8. The system has 100–200 accepted, diverse, engineering-qualified records.
9. A scalar surrogate has been evaluated using genealogy-aware holdout splits and exposes uncertainty/OOD conditions.
10. The same generic engine runs a second structural part after only a new baseline, confirmation, and Design Contract.

---

## 5. The three truth layers

Do not merge these. They are different objects with different authority.

```text
Canonical Engineering Model
        ↓
What exists in the imported package

Design Contract
        ↓
What may vary in one approved campaign

Qualification Model
        ↓
What must be demonstrated before acceptance
```

### 5.1 Canonical Engineering Model

The Canonical Engineering Model is an immutable, normalized representation of customer input. It records facts, not recommendations.

It contains:

- CAD source files, source hashes, import status, units, and coordinate-system metadata.
- B-rep topology and geometry entities.
- Extracted analytic surfaces, feature candidates, and confidence/provenance.
- Mesh nodes, elements, sets, physical groups, and mesh-to-geometry mapping where available.
- Solver deck objects and original labels.
- Materials, sections, loads, constraints, contacts, analysis steps, and output requests.
- Reference result metadata, scalar results, field artifacts, and available comparison probes.
- Imported, derived, inferred-candidate, confirmed, and generated provenance states.
- Extraction coverage and unresolved ambiguities.

The Canonical Engineering Model is versioned and immutable after baseline lock. Corrections create a new baseline-derived revision, never silent mutation.

### 5.2 Design Contract

The Design Contract is the engineer-approved, versioned policy that governs one campaign.

It specifies:

- Frozen interfaces and protected islands.
- Deliberately moved interfaces, if a later campaign allows them.
- Mutable design zones and keep-out volumes.
- Approved operator types, permissible anchors, and composition rules.
- Discrete and continuous parameter domains.
- Logical, geometric, manufacturing, and physics-transfer constraints.
- Campaign objectives, output objectives, and acceptance thresholds.
- Budget limits and approval status.

A contract must be in `APPROVED` state before a production campaign can run. Any edit produces a new version; all downstream artifacts must reference the exact version used.

### 5.3 Qualification Model

The Qualification Model is the set of deterministic and reviewable gates that decide record state.

It defines:

- Interface identity requirements.
- Geometry validity and fidelity requirements.
- Manufacturing requirements.
- Mesh validity and quality requirements.
- Physics mapping conditions.
- Solver and numerical requirements.
- Engineering plausibility/response requirements.
- Dataset eligibility requirements.
- Reproducibility requirements.
- Quarantine conditions and escalation rules.

---

## 6. GRC Stage-1 design space

### 6.1 Frozen engineering core

For the first GRC campaign, preserve at minimum:

- Bearing-seat analytic cylinders, radii, axes, axial limits, and their stable local frames.
- Gear/shaft packaging-clearance volumes.
- Essential bolt interfaces and machined datum faces.
- Mounting interfaces used by the baseline FEA model.
- Sealing/split-line interfaces where relevant to the baseline analysis.
- Baseline coordinate systems, reference points, and output frames.
- Any load/constraint/contact surfaces whose semantics cannot be safely reconstructed after alteration.

Do not initially change nominal bearing-bore centers, bearing axes, bearing diameters, gear center distance, primary mounting coordinates, or sealing interfaces.

### 6.2 Mutable structural region

The editable region is the structural material outside all protected-interface islands and all keep-out volumes.

```text
Frozen bearing islands
+ frozen mount/seal/datum islands
+ packaging-clearance volumes
+ load/constraint preservation regions
+ approved mutable structural zones
= governed design family
```

### 6.3 Initial architecture families

| Architecture family | Structural mechanism | Example operators |
|---|---|---|
| Bearing support | Change local radial/tangential support stiffness without changing the bore | collar, radial rib group, tangential rib, reinforcement pad |
| Inter-bearing coupling | Change relative support translation and rotation | straight bridge, deep bridge, double web, X/K brace |
| Bore-to-wall path | Connect bearing support to nearby shell/wall load path | bore-to-wall rib, triangular web |
| Bore-to-mount path | Change how bearing loads reach mounting structure | diagonal rib, trunk, base rail, reinforced support path |
| Front-to-rear coupling | Change longitudinal/shaft-support differential compliance | tie rail, sidewall spine, boxed corridor |
| Split-line/flange support | Change joint or cover flexibility | flange reinforcement, bolt-boss support, cover rib |
| Global shell | Redistribute allowable material in approved zones | belt, wall-zone adjustment, local bulkhead, windowed generated web |
| Hybrid | Combine compatible structural mechanisms | collar + bridge + tie rail; brace + windowed web; collar + bore-to-mount path |

### 6.4 Campaign diversity requirement

A campaign must report architecture diversity, not just numeric parameter variation.

```text
Weak campaign:
40 values of a single rib height

Strong campaign:
collar
+ radial-support group
+ inter-bore bridge
+ X/K brace
+ bore-to-mount path
+ tie rail
+ windowed web
+ selected hybrid cases
```

### 6.5 Moved-interface regimes are later phases

Support only after frozen-interface reliability is proven:

| Regime | Change | Additional required logic |
|---|---|---|
| A: Frozen-interface | Ribs, walls, bridges around unchanged interfaces | Protected-island reuse and stable measurement frames |
| B: Bore diameter | Diameter changes, axis remains fixed | Re-bore operator, manufacturing/rework distinction, new seat identity policy |
| C: Moved center/axis | Center or axis relocates | Assembly update, center-distance/coaxiality checks, per-variant nominal frame, re-baseline rules |
| D: Rescaled/new family | Envelopes or family geometry changes broadly | Parametric rebuild or new baseline family, non-dimensional comparison, new contract |

If an interface moves, measure distortion relative to that variant’s nominal assembly definition. Otherwise the model may learn intended center-distance changes instead of deformation under load.

---

## 7. System architecture

### 7.1 Functional architecture

```text
Customer input package
(CAD + drawing + mesh + deck + baseline results)
                     ↓
Ingestion and deterministic extraction
                     ↓
Canonical Engineering Model + extraction coverage report
                     ↓
Engineer semantic confirmation
                     ↓
Versioned Design Contract + Qualification Model
                     ↓
Engineering graph + operator/mfg/physics knowledge bases
                     ↓
Constraint planner + portfolio planner + campaign supervisor
                     ↓
Typed VariantRecipe candidates
                     ↓
Exact local B-rep operators + geometry oracle
                     ↓
CAD-conforming meshing + protected-interface coupling
                     ↓
Physics Mapping Layer + variant deck builder
                     ↓
Solver workers + numerical qualification
                     ↓
Accepted Simulation Records + failure memory
                     ↓
Coverage / cost / yield analytics
                     ↓
Feasibility model + scalar surrogate + active-learning planner
```

### 7.2 Authority boundary

```text
Agents:
understand → hypothesize → plan → prioritize → diagnose → explain → learn

Deterministic engineering tools:
extract → construct → validate → mesh → map physics → solve → qualify → certify
```

No probabilistic model can override a failed deterministic gate.

### 7.3 Suggested deployment architecture

```text
React + TypeScript UI
        ↓
FastAPI application / typed API
        ↓
PostgreSQL metadata + object storage artifacts + DVC dataset versioning
        ↓
Workflow/state-machine engine
        ↓
Worker queues
   ├── CAD/OCCT workers
   ├── meshing workers
   ├── deck/physics workers
   ├── solver workers
   ├── post-processing workers
   └── ML/analytics workers
        ↓
Compute environment: local workstation, on-prem cluster, or cloud batch/HPC
```

Start with a modular monolith and worker processes. Do not begin with microservices. Separate services only where isolation, licensing, scaling, or solver scheduling requires it.

---

## 8. Shared typed vocabulary and schemas

Pydantic v2 models are authoritative. Generate TypeScript types from the backend schemas to prevent UI/API/agent drift. Use unit-aware quantities wherever a physical value crosses an API boundary.

### 8.1 Core schema examples

```python
from __future__ import annotations
from enum import Enum
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field

class Provenance(str, Enum):
    IMPORTED = "IMPORTED"
    DERIVED = "DERIVED"
    INFERRED_CANDIDATE = "INFERRED_CANDIDATE"
    CONFIRMED = "CONFIRMED"
    GENERATED = "GENERATED"

class RecordState(str, Enum):
    ACCEPTED = "ACCEPTED"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"

class Vec3(BaseModel):
    x: float
    y: float
    z: float

class Quantity(BaseModel):
    value: float
    unit: str

class InterfaceFrame(BaseModel):
    semantic_id: str
    label: str
    kind: Literal[
        "bearing_seat", "pilot", "flange", "bolt_pattern",
        "datum", "seal", "mount", "load_surface", "constraint_surface"
    ]
    origin: Vec3
    axis: Vec3 | None = None
    reference_direction: Vec3 | None = None
    radius: Quantity | None = None
    axial_bounds: tuple[Quantity, Quantity] | None = None
    tolerance: Quantity
    provenance: Provenance

class GeometrySignature(BaseModel):
    surface_type: str
    centroid: Vec3
    axis: Vec3 | None = None
    radius: Quantity | None = None
    axial_length: Quantity | None = None
    area: Quantity | None = None
    cylinder_fit_residual: Quantity | None = None
    neighbor_signature_hash: str
    topology_signature_hash: str

class InterfaceIdentity(BaseModel):
    semantic_id: str
    source_entity_ids: list[str]
    role: str
    geometry_signature: GeometrySignature
    reference_frame: InterfaceFrame
    allowed_deviation: dict
    ownership_rule: str
    regeneration_rule: dict | None = None
    status: Literal["FROZEN", "MOVED", "RETIRED", "AMBIGUOUS"]

class DesignContract(BaseModel):
    baseline_id: UUID
    contract_version: str
    frozen_interfaces: list[InterfaceIdentity]
    mutable_regions: list[dict]
    keep_out_volumes: list[dict]
    allowed_operators: list[dict]
    parameters: list[dict]
    logical_constraints: list[dict]
    geometry_constraints: list[dict]
    manufacturing_constraints: list[dict]
    physics_transfer_rules: list[dict]
    campaign_objectives: list[dict]
    approval_status: Literal["DRAFT", "APPROVED", "SUPERSEDED"]

class OperatorCall(BaseModel):
    operator_name: str
    operator_version: str
    anchors: list[str]
    parameters: dict[str, float | int | str | bool]
    requested_by: Literal["USER", "PLANNER", "AGENT", "REPLAY"]

class VariantRecipe(BaseModel):
    variant_id: UUID
    baseline_id: UUID
    contract_version: str
    architecture_class: str
    operations: list[OperatorCall]
    parent_variants: list[UUID]
    expected_mechanisms: list[str]
    planner_reason: dict
    random_seed: int | None = None

class FailureRecord(BaseModel):
    code: str
    stage: str
    severity: Literal["INFO", "WARNING", "HARD_FAIL"]
    message: str
    evidence_artifacts: list[str]
    affected_entities: list[str]
    attempted_recovery: list[str]
    retryable: bool

class AcceptedSimulationRecord(BaseModel):
    variant_id: UUID
    baseline_id: UUID
    contract_version: str
    recipe: VariantRecipe
    geometry_checks: dict
    mesh_checks: dict
    physics_audit: dict
    solver_checks: dict
    scalar_outputs: dict[str, Quantity]
    field_outputs: list[dict]
    bearing_motion: list[dict]
    gear_misalignment: list[dict]
    state: RecordState
    replay_manifest_uri: str
```

### 8.2 Provenance and lineage states

Every entity and artifact should have a source state:

```text
IMPORTED
DERIVED
INFERRED_CANDIDATE
CONFIRMED
GENERATED
```

Every geometry entity should also carry genealogy state:

```text
PRESERVED
TRANSFORMED
SPLIT
MERGED
CREATED
DELETED
AMBIGUOUS
```

### 8.3 Context envelope

Agent interactions must be anchored to UI and contract context:

```python
class ContextEnvelope(BaseModel):
    baseline_id: UUID
    contract_version: str
    active_tab: str
    selected_entities: list[str]
    highlighted_region: str | None = None
    campaign_id: UUID | None = None
```

---

## 9. Ingestion and extraction pipeline

### 9.1 Accepted inputs

The input package should support, in order of implementation priority:

- CAD: STEP first; later IGES, Parasolid, native CAD through dedicated adapters where licensing permits.
- Mesh: Gmsh, MED, UNV, Abaqus INP, Nastran BDF, solver-native formats as required by the selected benchmark.
- Solver deck: Code_Aster input path first; adapters later for CalculiX, Abaqus, Nastran, OptiStruct, Ansys, etc.
- Baseline results: solver-native result plus normalized result export.
- Drawings/PDF: optional supporting evidence for entity names/dimensions; never the sole authority for geometry/physics semantics.

### 9.2 Extraction rule: honest uncertainty

Every finding is one of:

```text
Imported fact
Derived deterministic fact
Inferred candidate
Engineer-confirmed semantic object
Generated object
Not detected / unknown
```

Every inferred candidate has confidence:

```text
HIGH
MEDIUM
LOW
NOT_DETECTED
```

Do not convert candidate labels into engineering truth without confirmation when they affect contract permissions or physics mapping.

### 9.3 Deterministic extraction first

Use OCCT/OpenCascade-based topology and analytic fitting for:

- Planes, cylinders, cones, spheres, and tori where relevant.
- Hole and bore candidates.
- Coaxial cylindrical groups.
- Bearing-seat candidates.
- Bolt-circle candidates.
- Planar mounting/datum/flange candidates.
- Face area, centroid, normals, curvature, and bounding boxes.
- Face adjacency graph.
- Edge concavity/convexity.
- Principal axes and reference coordinate candidates.
- Approximate wall-thickness sampling.

### 9.4 Extraction reality bands

| Reliability band | Typical entities | Method | Required human role |
|---|---|---|---|
| High | Analytic cylindrical bores/seats, bolt patterns, planes, datum faces | OCCT topology + fitting + deterministic thresholds | Confirm semantic name/role |
| Medium | Bosses, pockets, cones, fillets, basic walls | Heuristics and geometric thresholds | Confirm/correct candidate |
| Low initially | Ribs, webs, gussets, functional load paths, blended casting motifs | Dedicated motif detector plus human annotation | Label and record reusable truth |

### 9.5 Feature recognition and ML role

B-rep graph methods, UV-Net-style descriptors, AAGNet/FilletRec/BRepMFR-like recognition, and custom motif detectors may assist with:

- Rib/boss/fillet candidate discovery.
- Candidate ranking.
- Region similarity.
- Annotation prioritization.
- Suspicious topology-change detection.
- Geometry embedding for diversity and failure retrieval.

They must not be final authority for bearing-seat identity, protected-interface validity, or physics mapping. Those remain deterministic geometry/topology checks plus human confirmation where ambiguity exists.

### 9.6 Required extraction output

The extraction stage produces:

- Canonical Engineering Model.
- Candidate feature and semantic graph.
- Extraction coverage report.
- Unresolved-question list.
- UI review tasks.
- Baseline source manifest.
- First interface identity candidates.

---

## 10. Interface identity and protected islands

### 10.1 Why identity matters

A CAD face index is not a stable engineering identity. Booleans can split, merge, delete, or reorder faces. A bearing seat must be recognized by its engineering signature, not by a transient face number.

### 10.2 Bearing-seat identity signature

A bearing seat should include at least:

- Analytic surface type: cylinder.
- Cylinder origin/centerline and axis direction.
- Radius/diameter.
- Axial limits and axial length.
- Angular span and surface area.
- Cylinder-fit residual.
- Local reference frame.
- Neighboring face/topology signature.
- Source face IDs where preserved.
- Expected ownership and mapping behavior.

### 10.3 Protected interface island

A protected island is an exact local CAD and mesh region around a critical interface.

For a bearing seat, include:

- The exact cylindrical seat.
- Axial boundaries and nearby datum surfaces.
- A local surrounding collar sufficient to isolate sensitive geometry.
- A stable local measurement frame.
- A transition boundary outside the measurement-sensitive zone.

```text
The surrounding structural bulk may change.
The critical seat’s geometric and numerical definition may not change.
```

### 10.4 Mesh/coupling choices

| Coupling option | Use | Requirements |
|---|---|---|
| Conformal shared-node transition | Preferred | Reuse or reproduce transition triangulation and prove correspondence |
| Tied/nonconformal transition | Controlled fallback | Keep transition far from sensitive interface and verify mesh-convergence impact |
| MPC/RBE-style distributing coupling | Special controlled case | Explicit weights, formulation, and verification evidence |
| Mortar/embedded/contact-like coupling | Later/special cases | Formal coupling contract and independent validation |

### 10.5 Interface coupling module

Make coupling a dedicated module. It records:

- Interface type and policy.
- Master/slave or symmetric configuration.
- Node correspondence/interpolation map.
- Constraint or stiffness definition.
- Coupling validation test.
- Applicability envelope.
- Mesh reuse/regeneration policy.
- Evidence artifacts.

### 10.6 Frozen-interface gate

Before a variant can proceed:

- Compare analytic parameters against allowed tolerance.
- Compare cylinder-fit residual.
- Compare stable local frame.
- Verify seat mesh nodes or approved coupling definition.
- Verify relevant load/constraint/coupling groups remain valid.
- Verify no operator intersects protected geometry/keep-out region.

Hard failure if any frozen interface fails its contract.

---

## 11. Design Contract details

### 11.1 Contract content

The Design Contract must define:

- Baseline ID and baseline revision.
- Contract version, author, approvals, timestamp, and rationale.
- Frozen interfaces and moved-interface policies.
- Mutable regions and their coordinate definitions.
- Keep-out volumes: packaging, tools, machining access, sealing, load/constraint sensitivity.
- Permitted operator library and versions.
- Operator-to-anchor permissions.
- Parameter ranges and discretization policy.
- Architecture compatibility rules.
- Geometric constraints.
- Manufacturing constraints.
- Physics transfer policies.
- Campaign goals, response outputs, and acceptance conditions.
- Compute/model/retry budgets.

### 11.2 Contract example

```yaml
baseline_id: grc-rear-housing-r1
contract_version: 1.0.0
approval_status: APPROVED

frozen_interfaces:
  - HSS_BEARING_SEAT
  - LSS_BEARING_SEAT
  - MOUNT_A
  - MOUNT_B
  - SPLIT_LINE_SEAL

mutable_regions:
  - id: HSS_OUTER_SUPPORT_ZONE
    type: BREP_FACE_SET
  - id: INTER_BORE_WEB_ZONE
    type: VOLUME_ENVELOPE

allowed_operators:
  - add_external_collar
  - add_radial_rib_group
  - add_bore_to_wall_rib
  - add_inter_bore_bridge
  - add_x_or_k_brace
  - add_local_reinforcement_pad
  - add_window_in_generated_web

campaign_objectives:
  - minimize: mass
  - minimize: relative_bearing_tilt
  - minimize: center_distance_change
  - constrain: max_stress <= allowable

budgets:
  max_solver_runs: 160
  max_cpu_hours: 800
  max_retries_per_variant: 2
```

### 11.3 Contract approval workflow

1. System extracts candidates and displays confidence/provenance.
2. Engineer confirms names, semantic roles, frozen interfaces, and mutable zones.
3. Engineer selects allowed architecture families and operators.
4. Engineer sets parameter ranges, manufacturing rules, transfer rules, goals, and budget.
5. System validates internal consistency and reports unresolved ambiguities.
6. Engineer explicitly approves the contract.
7. Campaign execution can only reference that immutable approved version.

---

## 12. Operator library and exact B-rep generation

### 12.1 Geometry strategy

Trusted route:

```text
Imported STEP B-rep
        ↓
Local exact B-rep construction on approved anchors
        ↓
Boolean fuse/cut
        ↓
Local healing
        ↓
Protected-interface comparison
        ↓
Geometry oracle
        ↓
STEP/B-rep artifact for meshing
```

Use OpenCascade through build123d, CadQuery, pythonOCC, or direct OCCT bindings. Keep low-level OCCT escape hatches for robust local operations.

### 12.2 Do not use fields as trusted final geometry

SDF/voxel/field methods are useful for:

- Fast collision and clearance screening.
- Approximate wall-thickness checks.
- Feature layout planning.
- Visual region masks.
- Candidate plausibility/risk scoring.
- Future learned proposal representations.

They are not the final analysis authority where bearing-seat shape, sharp edges, face groups, or stable coupling membership matter.

### 12.3 Operator protocol

```python
class Operator:
    name: str
    version: str

    def validate_preconditions(self, model, contract, request):
        ...

    def resolve_anchors(self, shape, identities, request):
        ...

    def construct_local_geometry(self, shape, placement, request):
        ...

    def apply_boolean_and_heal(self, shape, local_feature):
        ...

    def validate_postconditions(self, before, after, placement, contract):
        ...

    def emit_evidence(self, before, after, report):
        ...

    def rollback(self, checkpoint):
        ...
```

Every operator must declare:

```text
Purpose
Allowed anchor types
Reference frames
Parameter schema and units
Preconditions
Construction approach
Protected entities
Expected topology event
Postconditions
Manufacturing checks
Known failure modes
Recovery options
Evidence artifacts
Version
```

### 12.4 Initial operator sequence

Do not implement all operators at once. Build in this order:

1. `add_external_collar`
2. `add_radial_rib_group`
3. `add_bore_to_wall_rib`
4. `add_bore_to_mount_rib`
5. `add_inter_bore_bridge`
6. `add_x_or_k_brace`
7. `add_local_reinforcement_pad`
8. `add_window_in_generated_web`
9. `adjust_approved_wall_zone`
10. `add_front_rear_tie_rail`

The first two operators establish local support variation. The next four create meaningful architecture diversity. Subtractive/windowing features must operate only on generated or explicitly approved structural material, not by cutting uncontrolled regions of imported cast geometry.

### 12.5 Example: Bore-to-wall rib contract

**Preconditions**

- A confirmed bearing-seat anchor exists and passes identity checks.
- An eligible mutable wall target exists.
- The proposed path remains in approved mutable zones.
- The path does not intersect any keep-out or protected island.
- Thickness, height, root radius, draft, and taper are inside the contract range.

**Postconditions**

- The rib is attached to the intended structural body.
- The protected bearing-seat signature is unchanged within tolerance.
- The feature has no disconnected bodies, self-intersections, zero-thickness contacts, or unacceptable sliver faces.
- Minimum wall/rib thickness and root-radius constraints pass.
- Expected volume change is physically plausible and within stated bounds.
- A topology event and entity genealogy are recorded.
- Local meshability screening passes.

**Failure codes**

```text
ANCHOR_NOT_FOUND
ANCHOR_AMBIGUOUS
INVALID_PATH
KEEP_OUT_INTERSECTION
BOOLEAN_FAILURE
HEALING_FAILURE
SLIVER_CREATED
SELF_INTERSECTION
DISCONNECTED_FEATURE
PROTECTED_INTERFACE_CHANGED
MIN_THICKNESS_VIOLATION
DRAFT_VIOLATION
LOCAL_MESH_FAILURE
```

### 12.6 Geometry oracle

The geometry oracle is a deterministic post-operation qualification system. It must detect silent failures, not just exceptions.

Check at minimum:

- Valid B-rep topology and non-null solid volume.
- Expected body count.
- No accidental disconnected solids unless explicitly allowed.
- Volume change consistent with requested addition/cut.
- No unintended global-volume loss.
- Protected-interface signature preservation.
- No keep-out intersections.
- No self-intersections/invalid shells.
- Sliver-face and tiny-edge thresholds.
- Local thickness/clearance constraints.
- Expected topology class changes.
- Export/re-import consistency if required by downstream tools.

---

## 13. Manufacturing rule engine

### 13.1 Acceptance ladder

A candidate is evaluated progressively:

```text
1. Geometrically feasible
2. Manufacturable under declared process assumptions
3. Meshable and numerically solvable
4. Structurally/engineering acceptable
5. Engineering-useful as a comparable dataset record
```

Passing an earlier stage does not imply passing a later stage.

### 13.2 Initial cast-housing rule pack

Make thresholds contract-configurable and attach evidence for each evaluation:

- Minimum wall thickness.
- Minimum rib thickness.
- Rib-to-parent-wall thickness ratio.
- Minimum root/fillet radius.
- Maximum abrupt section transition.
- Minimum spacing and ligament around holes/windows.
- Draft angle and pull-direction compatibility.
- No zero-thickness contact.
- No unintended enclosed voids.
- No prohibited undercuts under the declared casting/tooling assumption.
- Core accessibility or allowable-core envelope where modeled.
- Machining allowance and tool-access keep-outs where supplied.
- Boss/collar support requirements.
- Limits on isolated thick masses and hot-spot-prone junctions.
- Clearance from frozen faces and packaging zones.

### 13.3 Rule object

```yaml
rule_id: MIN_RIB_THICKNESS
scope: GENERATED_RIB
severity: HARD_FAIL
input_fields:
  - rib_thickness
metric: local_minimum_thickness_mm
threshold: ">= 6.0"
evidence:
  - thickness_map
  - min_location
binding_status: BINDING
version: 1.0.0
```

### 13.4 Baseline style rules

Extract baseline patterns where feasible:

- Typical wall-thickness bands.
- Rib-thickness bands.
- Typical fillet radii.
- Common draft direction.
- Symmetry patterns.
- Feature spacing.

Expose them as advisory defaults; the engineer chooses which become contract-binding.

---

## 14. Meshing and protected-interface integrity

### 14.1 Trusted meshing route

Use CAD-conforming surface/volume meshing on exact B-rep geometry. For the initial open-source route, use Gmsh with physical groups mapped from semantic/lineage identifiers.

```text
Exact B-rep
        ↓
Named/protected face sets
        ↓
CAD-conforming surface mesh
        ↓
High-order volume mesh as required (for example TET10)
        ↓
Mesh quality checks
        ↓
Stable interface/coupling definitions
```

### 14.2 Why previous field/CGAL-style pathways are insufficient

Any route that smooths bearing cylinders, changes sharp edges, changes local surface discretization unpredictably, or changes coupling-node membership may cause apparent bearing motion changes that originate from numerical representation rather than stiffness. For bore-tilt/misalignment studies, that is unacceptable.

### 14.3 Protected-island mesh strategy

Preferred pattern:

```text
Freeze and mesh protected bearing islands once
        ↓
Define fixed transition boundaries outside sensitive zones
        ↓
Modify only the mutable bulk B-rep
        ↓
Mesh bulk under controlled policy
        ↓
Join through conformal transition or validated coupling
        ↓
Verify protected seat geometry, mesh/coupling evidence, and measurement frame
```

### 14.4 Mesh quality gates

Configure solver-appropriate thresholds for:

- Jacobian quality / scaled Jacobian.
- Element aspect ratio.
- Minimum/maximum angle.
- Skewness.
- Element size and growth ratio.
- Curvature and proximity resolution.
- Boundary-layer/critical-region size control where needed.
- Inverted/negative-volume element absence.
- Connected-domain checks.
- Physical-group completeness.
- Protected-interface node/coupling consistency.

### 14.5 Mesh recovery ladder

Use a deterministic bounded ladder. Every attempted path is logged.

```text
Primary: Gmsh CAD-conforming mesh
        ↓ failure
Repair 1: local geometry repair / MeshFix where appropriate
        ↓ failure
Repair 2: controlled local remesh/refinement using libigl/PyMeshLab class tools
        ↓ failure
Repair 3: fTetWild or alternative lower-fidelity route, explicitly flagged
        ↓ failure or out of fidelity envelope
QUARANTINE / REJECT with typed reason
```

Do not allow an agent to invent arbitrary meshing parameters. It may choose only among contract-approved policies and bounded retry options.

---

## 15. Physics Mapping Layer

### 15.1 Purpose

Topology changes make physics transfer dangerous. A load target may split, a constraint face may be altered, a contact pair may disappear, or an interface may become ambiguous.

The Physics Mapping Layer determines whether each baseline physics object can be:

| Mapping outcome | Meaning | Action |
|---|---|---|
| Direct transfer | Target geometry/entity is preserved with sufficient evidence | Transfer mapping and record proof |
| Approved aggregate transfer | A split/derived target is still governed by a declared rule | Rebuild mapping under explicit aggregation rule |
| Rebuild required | A semantic target changed but can be recreated with a typed method | Rebuild and record evidence |
| Ambiguous | No safe deterministic mapping exists | Block or quarantine for review |
| Invalid | Required physics target deleted/changed unlawfully | Reject |

### 15.2 Required audit content

For every load, constraint, contact, material region, section, coupling, output request, and coordinate system:

- Source object identity.
- Mapping method.
- Target entities/groups.
- Mapping confidence/evidence.
- Area/normal/centroid/role comparison where relevant.
- Any rebuild method and parameters.
- Approval policy invoked.
- Final state: transferred, rebuilt, blocked, or ambiguous.

### 15.3 Hard safety rules

- A pressure/load group cannot silently map to an unrelated face.
- A deleted load or constraint target is not “ignored”; it blocks the variant unless an approved rebuild policy exists.
- Contacts changed by topology must be rebuilt/reviewed; do not assume equivalence.
- Frozen bearing islands use a known coupling/mapping policy that is validated independently.
- Ambiguous physics mapping blocks solver eligibility.

### 15.4 Variant deck builder

The initial solver path should clone a validated baseline deck and substitute only explicitly mapped, versioned, and audited objects. Never regenerate an entire physics deck from informal labels if the trusted baseline deck is available.

---

## 16. Solver execution and baseline reproduction

### 16.1 Solver strategy

Use the solver closest to the trusted reference for Stage 1. If Code_Aster is the operational open-source route, first establish baseline equivalence to the reference case. Optionally cross-check selected cases with CalculiX or the original customer/reference solver where possible.

### 16.2 Baseline reproduction certificate

Before any variant campaign, reproduce the baseline and compare against the trusted reference across:

- Applied-load resultants, directions, moments, and coordinate frames.
- Constraint reactions and balance.
- Displacement norms, extrema, and selected probes.
- Strain energy / relevant energy checks.
- Stress/strain result comparisons at defined probes or mapped locations.
- Bearing-seat motion and rotation extraction.
- Mesh-sensitivity behavior around critical interfaces.
- Output presence and unit consistency.

The certificate must define reviewed tolerances and explicitly distinguish:

```text
Verification: Does the reconstructed workflow behave consistently with the baseline reference?

Validation: Is the underlying physical model adequate for reality?
```

Stage 1 requires verification of the inherited pipeline; it does not claim to create new experimental validation.

### 16.3 Solver qualification gates

A solver result is eligible only if it passes:

- Normal process completion.
- Convergence criteria appropriate to the analysis type.
- No NaN/Inf/nonphysical numerical fields.
- Required output artifacts present.
- Load/reaction force and moment balance within tolerance.
- Finite and plausible displacement range.
- Energy consistency where applicable.
- No invalid elements or solver-reported fatal model conditions.
- Required bearing-motion and key-response extraction completed.

### 16.4 Execution workers

Implement idempotent jobs with:

- Immutable input bundle hashes.
- Job ID, variant ID, contract version, solver version, and environment digest.
- Resource request and measured resource use.
- Retries controlled by policy and budget.
- Structured logs, stdout/stderr, result locations, and failure codes.
- Cancellation and resume semantics.

---

## 17. Bearing motion and gear-misalignment outputs

### 17.1 Why this is core

The GRC housing use case is not merely about maximum stress. The structural changes should be related to bearing-seat translation/rotation, shaft-axis changes, center-distance change, and gear-mesh-relevant misalignment descriptors.

### 17.2 Rigid-fit extraction

For displacement vectors \(\mathbf{u}_i\) at seat-interface nodes/points \(\mathbf{x}_i\), estimate rigid translation \(\mathbf{t}\) and rotation \(\boldsymbol{\theta}\) through a weighted least-squares fit:

\[
\min_{\mathbf{t},\boldsymbol{\theta}}
\sum_i w_i
\left\|
\mathbf{u}_i - \left(
\mathbf{t} + \boldsymbol{\theta} \times (\mathbf{x}_i - \mathbf{x}_0)
\right)
\right\|^2
\]

Store:

- Rigid translation in global and local interface frames.
- Rigid rotation/tilt in local interface frames.
- Fit residual.
- Radial expansion component.
- Ovalization/non-rigid distortion descriptors.
- Node/coupling membership evidence.

### 17.3 Key GRC outputs

At minimum store:

- Housing mass and volume.
- Maximum displacement and stress metrics, with location/context.
- Reaction/load balance metrics.
- Per-bearing-interface translations and rotations.
- Relative bearing motion on each shaft.
- Relative pinion/gear axis tilt where reconstructable.
- Center-distance change.
- Lead-direction and profile-direction mesh-misalignment descriptors where the model supports them.
- Optional condensed interface compliance matrix.
- Geometry, mesh, and solver quality descriptors.

### 17.4 Separation of rigid movement and local distortion

Seat translation and rotation are relevant to assembly/gear alignment. Ovalization and local radial expansion are separate seat-integrity metrics. Never collapse them into a single “bore displacement” value.

---

## 18. Qualification Plane

### 18.1 Gate sequence

```text
Recipe validity
        ↓
Contract feasibility
        ↓
Geometry build
        ↓
Geometry oracle + protected-interface check
        ↓
Manufacturing checks
        ↓
Mesh quality + interface integrity
        ↓
Physics transfer audit
        ↓
Solver execution
        ↓
Numerical qualification
        ↓
Engineering-output extraction and plausibility
        ↓
Record acceptance / quarantine / rejection
```

### 18.2 Required qualification categories

| Category | Core questions |
|---|---|
| Contract | Was every action permitted by this exact contract version? |
| Identity | Are frozen engineering interfaces preserved and unambiguous? |
| Geometry | Is the B-rep valid and consistent with expected topology/volume? |
| Manufacturing | Does it pass declared cast/machining rules? |
| Mesh | Is the mesh valid, quality-qualified, and compatible with protected interfaces? |
| Physics | Are all loads, constraints, contacts, materials, and outputs mapped or rebuilt with evidence? |
| Solver | Did the numerical job complete, converge, balance, and produce valid outputs? |
| Engineering | Are output definitions complete, physically plausible, and comparable under the baseline frame/policy? |
| Reproducibility | Can the variant be deterministically rebuilt from manifest and artifacts? |

### 18.3 Quarantine conditions

Quarantine rather than reject when the case is potentially informative but outside normal training eligibility, for example:

- Lower-fidelity mesh fallback was used.
- A physics mapping required an approved but less direct rebuild.
- Numerical results are complete but a review threshold is exceeded.
- A new topology class has insufficient validation evidence.
- A solver result differs from an independent cross-check beyond a review threshold.

### 18.4 Acceptance requirement

Only a record with a complete evidence chain reaches `ACCEPTED`:

```text
Valid contract
+ valid geometry
+ protected interfaces preserved
+ manufacturing pass
+ qualified mesh
+ audited physics
+ solver qualification
+ complete outputs
+ replay manifest
= accepted simulation record
```

---

## 19. Data model, artifacts, and replay

### 19.1 Storage strategy

Use:

- PostgreSQL for typed metadata, state transitions, contract versions, entity lineage, campaign planning, and audit events.
- Object storage or file store for CAD, meshes, decks, solver artifacts, reports, images, logs, and field data.
- Parquet for scalar/tabular records and analytics.
- Zarr for scalable field arrays and spatial result data.
- DVC or equivalent dataset/artifact versioning for curated record sets and surrogate training snapshots.

### 19.2 Replay manifest

Every candidate, whether accepted or failed, must have a replay manifest. A minimum schema includes:

```python
class ReplayManifest(BaseModel):
    baseline_hash: str
    contract_hash: str
    recipe_hash: str
    operator_versions: dict[str, str]
    kernel_version: str
    mesher_version: str
    mesh_settings_hash: str
    physics_mapping_version: str
    solver_version: str
    solver_settings_hash: str
    random_seed: int | None
    container_digest: str | None
    artifact_hashes: list[str]
    hardware_runtime_metadata: dict
```

### 19.3 Replay test

For sampled variants:

```text
Replay from manifest
        ↓
Rebuild geometry within declared tolerance
        ↓
Reapply same mesh policy/quality class
        ↓
Reapply physics mapping
        ↓
Rerun solver or compare stored solver result
        ↓
Verify numerical outputs within declared tolerance
```

### 19.4 Dataset split policy

Do not randomly split near-duplicate siblings across train and test sets. Use genealogy-aware evaluation:

- Hold out entire architecture families.
- Hold out operator combinations.
- Hold out parameter regions.
- Hold out spatial anchor regions where relevant.
- Report in-distribution and out-of-distribution performance separately.

---

## 20. Engineering graph and knowledge system

### 20.1 Engineering graph

The engineering graph is the agent’s structured reasoning substrate. It is richer than B-rep adjacency and safer than prose.

```text
Geometry graph
        ↓
Feature graph
        ↓
Semantic engineering graph
        ↓
Physics graph
        ↓
Design Contract graph
        ↓
Variant lineage graph
```

### 20.2 Graph layers

| Layer | Represents | Example |
|---|---|---|
| Geometry graph | CAD faces, edges, solids, adjacency, geometry | cylinder adjacent to shell faces |
| Feature graph | Detected/confirmed features | bore, boss, wall, rib candidate, fillet |
| Semantic graph | Engineering roles | HSS bearing seat, mounting face, split line |
| Physics graph | Loads, constraints, contacts, output relationships | bearing coupling applies to bearing seat |
| Contract graph | Permissions and restrictions | frozen seat, allowed rib anchor, keep-out |
| Lineage graph | Variant evolution | source wall → transformed wall → mesh group |

### 20.3 Example relationships

```text
BearingSeat --supported_by--> SurroundingWall
BearingSeat --connected_to--> ExistingRib
BearingSeat --load_path_to--> MountingInterface
BearingSeat --paired_with--> OppositeBearingSeat
GeneratedRib --reinforces--> WallZone
LoadSurface --mapped_to--> MeshSurfaceGroup
BearingCoupling --applies_to--> BearingSeat
```

### 20.4 Knowledge bases

Build structured knowledge bases for:

- Engineering ontology: generic entity types and relations.
- Baseline-specific engineering truth: confirmed interfaces, loads, materials, outputs, known paths.
- Operator knowledge: preconditions, parameter ranges, risks, recovery options, examples.
- Manufacturing rules: scope, threshold, evidence, binding/advisory state.
- Physics mapping rules: transfer/rebuild/block policies.
- Architecture patterns: structural mechanism, valid anchors, relevant outputs, risks.
- Failure memory: failure context, repair attempts, outcomes, no-good constraints.
- Experiment memory: coverage, response patterns, resource use, hypotheses supported/contradicted.
- Model memory: model versions, data versions, validation metrics, applicability domain.

Use a relational/graph store as the source of truth. Use vector retrieval only to supplement text notes, design rationales, historical narratives, and unusual-failure explanations.

---

## 21. Campaign planning and CP-SAT

### 21.1 Planning layers

Use three planners with distinct jobs:

| Planner | Role | Inputs | Output |
|---|---|---|---|
| Constraint planner | Generate nominally permissible configurations | Contract rules, discrete parameters, compatibility rules | Feasible configuration space/candidate set |
| Portfolio planner | Build a diverse batch | Architecture quotas, parameter coverage, similarity, cost | Diverse candidate batch |
| Active-learning planner | Improve knowledge after data exists | Surrogate uncertainty, response gaps, feasibility, cost | High-value next batch |

### 21.2 CP-SAT scope

Use OR-Tools CP-SAT for discrete/discretized choices:

- Feature presence/absence.
- Architecture class selection.
- Operator compatibility.
- Anchor choice from approved sets.
- Pattern count.
- Symmetric versus biased configuration.
- Discretized thickness, height, angle, spacing, taper levels.
- Keep-out compatibility.
- Manufacturing configuration logic.
- Budget/portfolio quotas.

CP-SAT does **not** certify exact geometric feasibility, meshability, physics transfer, or structural response. Those are tested by downstream tools.

### 21.3 No-good feedback

When a nominally feasible recipe repeatedly fails construction, encode a bounded no-good rule when the evidence supports it:

```text
NOT(
  anchor_zone = INTER_BORE_3
  AND bridge_depth = 42
  AND rib_height = 28
  AND brace_angle = 45
)
```

Do not overgeneralize individual failures. Store the evidence, parameter region, operator versions, and geometry context.

### 21.4 Initial campaign strategy before surrogates

Before enough accepted data exists, use:

- Architecture quotas.
- Low-discrepancy or space-filling parameter sampling.
- Contract/CP-SAT filtering.
- Deterministic diversity metrics.
- Limited high-value strategic review only where objectives/architecture tradeoffs are ambiguous.

### 21.5 Candidate value

For candidate \(x\), prioritize approximate engineering information value per expected campaign cost:

\[
V_{\mathrm{sim}}(x) =
\frac{I(x)\,R(x)\,P_{\mathrm{complete}}(x)}
{C_{\mathrm{CAD}}(x) + C_{\mathrm{mesh}}(x) + C_{\mathrm{FEA}}(x)}
\]

Where:

- \(I(x)\) is expected information gain.
- \(R(x)\) is relevance to the campaign objective.
- \(P_{\mathrm{complete}}(x)\) is estimated probability of reaching qualified status.
- The denominator estimates geometry, meshing, and solve cost.

Initially, use simple proxy scores. Replace components with learned feasibility/surrogate estimates only after data supports them.

---

## 22. Agentic system and cost-aware routing

### 22.1 Core rule

The system is agentic if it can observe campaign outcomes, revise the next batch, and learn from successes/failures. It is not agentic merely because an LLM invokes CAD tools.

```text
Understand engineering context
        ↓
Form structural hypotheses
        ↓
Synthesize contract-compliant architecture candidates
        ↓
Choose informative experiments
        ↓
Execute deterministic tools
        ↓
Observe results and failures
        ↓
Update campaign knowledge
        ↓
Change the next plan under the same contract/budget
```

### 22.2 Agent roles

| Role | Responsibility | Hard boundary |
|---|---|---|
| Input/Context agent | Report files, extraction results, unknowns, and semantic confirmation tasks | Cannot invent semantics |
| Baseline validation agent | Coordinate reproduction evidence and diagnose mismatch packages | Cannot modify geometry kernel or bypass evidence |
| Engineering context agent | Query graph and formulate structural mechanisms | Cannot certify interfaces/physics |
| Design synthesis agent | Propose typed architecture hypotheses and VariantRecipes | Cannot output arbitrary CAD code |
| Campaign scientist | Select batches under coverage/value/budget constraints | Cannot override hard contract constraints |
| Execution agent | Schedule deterministic geometry/mesh/solve jobs | Cannot hand-edit mesh/deck |
| Recovery agent | Select bounded retry options from policy | Cannot exceed retry budget or invent procedures |
| Data agent | Assemble reports and apply deterministic acceptance state | Cannot fabricate/override results |
| Optimization agent, later | Select solver-confirmed candidates from surrogate/uncertainty evidence | Cannot declare final design accepted without solver confirmation |

### 22.3 Intelligence tiers

| Tier | Owner | Appropriate work | Forbidden work |
|---|---|---|---|
| Tier 0 | Deterministic engineering tools | Geometry extraction, interface signatures, rules, CP-SAT, CAD construction, meshing, physics mapping, solver execution, qualification, replay | Probabilistic final certification |
| Tier 1 | Local analytics/specialized models | Similarity, feature candidate ranking, failure classification, feasibility estimation, response surrogate, uncertainty, coverage clustering | Final interface/physics/record acceptance |
| Tier 2 | Premium strategic reasoner | High-level architecture hypotheses, ambiguous objective synthesis, unusual failure diagnosis after retrieval, major batch strategy decisions, explanation | Per-operation CAD/mesh/solver command loops; geometry/mesh/solver manipulation; gate overrides |
| Human review | Engineer | Semantic confirmation, contract approval, high-consequence ambiguity, policy escalation | Not needed for routine qualified pipeline operation |

### 22.4 Intelligence router

The router decides who handles each task:

```text
Task request
        ↓
Can a deterministic tool answer exactly?
        ├── yes → Tier 0
        └── no
             ↓
Is a local model validated within its applicability domain?
        ├── yes → Tier 1
        └── no
             ↓
Is the decision high-value, ambiguous, and within premium budget?
        ├── yes → Tier 2
        └── no → deterministic heuristic, defer, or human review
```

### 22.5 Router decision object

```python
class RouteDecision(BaseModel):
    task_id: str
    executor: Literal[
        "DETERMINISTIC_TOOL",
        "LOCAL_MODEL",
        "PREMIUM_REASONER",
        "HUMAN_REVIEW",
    ]
    rationale: str
    required_confidence: float
    estimated_quality: float | None = None
    estimated_model_cost: float = 0.0
    estimated_latency_s: float = 0.0
    estimated_downstream_compute_cost: float | None = None
    escalation_condition: str | None = None
    approval_requirement: str | None = None
```

### 22.6 Premium reasoning batch policy

Never wrap a premium model around each mechanical operation:

```text
Wrong:
LLM → make one CAD edit → inspect → mesh → inspect → solve → inspect
```

Use evidence-compressed batch reasoning:

```text
Premium reasoner chooses batch strategy
        ↓
Deterministic engine executes 20–30 candidates
        ↓
Analytics builds compact evidence package
        ↓
Premium reasoner chooses the next strategic batch only if justified
```

### 22.7 Strategic context package

```python
class StrategicContextPackage(BaseModel):
    campaign_goal: dict
    contract_summary: dict
    engineering_subgraph: dict
    latest_batch: dict
    coverage_gaps: dict
    response_summary: dict
    uncertainty_summary: dict
    feasibility_summary: dict
    top_success_patterns: list[dict]
    top_failure_patterns: list[dict]
    candidate_portfolio: list[dict]
    budget_status: dict
    decision_question: str
    allowed_decisions: list[str]
```

The premium model sees this package, not raw archives, unconstrained CAD, or unfiltered solver logs.

### 22.8 Decision budgets

```python
class DecisionBudget(BaseModel):
    max_premium_calls_per_campaign: int
    max_premium_calls_per_batch: int
    max_local_inferences_per_batch: int
    max_solver_runs: int
    max_cpu_hours: float
    max_gpu_hours: float
    max_storage_gb: float
    max_wall_clock_hours: float
    max_retries_per_variant: int
    max_total_retries_per_campaign: int
```

Track premium model spend, local-model usage, CAD/mesh/solver resource use, cost per accepted record, cost per coverage increment, and improvements over a DOE-only baseline.

---

## 23. Failure handling and bounded recovery

### 23.1 Principle

A failure is a structured observation. It must have a stage, code, evidence, retry policy, and final disposition.

### 23.2 Failure categories

```text
Input / extraction
Contract / configuration
Anchor resolution
Geometry construction
Geometry healing / topology
Protected-interface violation
Manufacturing rule violation
Meshing
Physics mapping
Solver execution
Numerical convergence
Output extraction
Engineering plausibility
Replay failure
Infrastructure / resource failure
```

### 23.3 Recovery state machine

```text
Failure observed
        ↓
Classify using deterministic error code/evidence
        ↓
Is retry policy approved and retry budget available?
        ├── no → quarantine/reject and record
        └── yes
             ↓
Select bounded alternative
             ↓
Retry deterministic stage
             ↓
Requalify from the affected gate onward
```

### 23.4 Example recovery constraints

- Boolean failure: try only predeclared local construction alternatives or parameter reductions; do not globally alter unrelated geometry.
- Mesh failure: try only approved mesh sizing/repair policies; flag lower-fidelity fallback.
- Physics ambiguity: no automated retry without a deterministic mapping policy; block for review or reject.
- Solver nonconvergence: apply only approved solver stabilization/retry policy; preserve original attempt and evidence.
- Protected-interface failure: hard reject; do not “repair” by changing the protected definition silently.

### 23.5 Failure memory

Store:

- Recipe, contract, baseline, operator versions, parameters, and anchor context.
- Geometry descriptors and relevant local subgraph.
- Failure code, messages, logs, location, and evidence artifacts.
- Recovery attempts and results.
- Whether a CP-SAT no-good or feasibility-model label should be emitted.

---

## 24. Surrogate models and active learning

### 24.1 Sequence matters

Do not begin with GNNs, neural operators, or generative CAD. First build reliable records and simple scalar baselines.

### 24.2 Initial models

Train only on `ACCEPTED` records:

- Mass/volume regression.
- Maximum displacement regression.
- Stress KPI regression.
- Bearing translation and rotation regressions.
- Center-distance and misalignment descriptor regressions.
- Geometry/mesh/physics/solver feasibility classifiers.
- Architecture/recipe similarity model.

Start with transparent baselines such as regularized regression, random forest, gradient boosting, XGBoost, and simple uncertainty ensembles. Add PyTorch/PyG only when graph-based representations demonstrably improve held-out performance.

### 24.3 Prediction trust layer

Every prediction must include:

- Predicted value.
- Uncertainty/confidence.
- Out-of-distribution indicator.
- Nearest accepted records or architecture evidence.
- Contract applicability status.
- Required action: rank, simulate, or block.

### 24.4 Solver fallback policy

Require solver confirmation when:

- Uncertainty is high.
- Candidate is out of distribution.
- Architecture or topology is unseen.
- Candidate is near a hard constraint boundary.
- Candidate appears Pareto-optimal.
- Protected-interface/coupling regime differs from trained records.

### 24.5 Active learning

After an initial accepted dataset exists:

```text
Generate candidate portfolio
        ↓
Apply deterministic contract/CP-SAT screen
        ↓
Estimate feasibility, similarity, response, and uncertainty
        ↓
Preserve a deliberate exploration allocation for difficult regions
        ↓
Select batch maximizing coverage + uncertainty reduction + objective relevance per cost
        ↓
Run deterministic CAD/mesh/physics/solver qualification
        ↓
Update record store and models
```

### 24.6 Critical safeguard

Never let a feasibility model eliminate difficult approved regions silently. Always report:

- Yield.
- Coverage.
- Unexplored approved regions.
- Feasibility uncertainty.
- Rejected-by-model count.
- Deliberate high-risk exploration budget.

---

## 25. User interface requirements

The UI is an engineering campaign configurator, not a free-form modeling canvas and not a required chatbot surface.

### 25.1 Required views

| View | Main capabilities |
|---|---|
| Input | Upload/select package, file status, extraction status, 3D CAD/mesh/result views, semantic confirmation |
| Design Contract | Frozen interfaces, mutable zones, keep-outs, allowed operators, parameter domains, rules, objectives, approval |
| Generate | Architecture selection, CP-SAT result, candidate portfolio, diversity display, recipe preview, pin/reject controls |
| Campaign | Variant stage state, yields, queues, resources, failure reasons, retries, decision audit, budget status |
| Dataset | Accepted/quarantined/rejected records, lineage, coverage, response distributions, exports |
| Surrogate | Dataset version, validation results, OOD/uncertainty, ranking, active-learning recommendations |

### 25.2 Selection bus

Clicking an entity anywhere must cross-highlight linked objects in all relevant views:

```text
CAD face ↔ semantic interface ↔ mesh group ↔ load/constraint ↔ result probe ↔ lineage event ↔ contract rule
```

### 25.3 Decision transparency

Campaign decision cards should show:

```text
Decision: Select 12 variants for Batch 3
Source: Local feasibility + deterministic diversity planner / premium strategic review if used
Why: Low X-brace coverage, high response uncertainty, acceptable success probability, remaining budget sufficient
Evidence: Contract version, coverage report, uncertainty report, failure patterns, cost estimate
```

### 25.4 Campaign health panel

Show at all times:

- Attempted variants.
- Geometry-qualified count/yield.
- Mesh-qualified count/yield.
- Physics-qualified count/yield.
- Solver-qualified count/yield.
- Accepted/quarantined/rejected counts.
- Architecture and parameter coverage.
- Cost per accepted record.
- Remaining solver/CPU/storage/retry/premium budgets.
- Top failure categories.
- Current strategy mode: exploration, coverage fill, uncertainty reduction, boundary test, or confirmation.

---

## 26. Technology stack

### 26.1 Recommended initial stack

| Layer | Recommended technology | Notes |
|---|---|---|
| Geometry kernel | OpenCascade via build123d, CadQuery, pythonOCC, direct OCCT | Use direct OCCT where high-level wrappers are insufficient |
| CAD import/export | STEP first through OCCT | Preserve source metadata and hashes |
| Feature extraction | OCCT topology/analytic fitting; custom motif detectors | ML assists but does not certify identity |
| Constraint solving | OR-Tools CP-SAT | Discrete/discretized configuration feasibility only |
| Meshing | Gmsh | CAD-conforming, semantic physical groups |
| Mesh repair | MeshFix, libigl, PyMeshLab, fTetWild as controlled fallback | Verify licensing and fidelity implications |
| FE solver | Code_Aster first; CalculiX cross-check where useful | Solver choice follows trusted baseline and licensing constraints |
| Pre/post | meshio, VTK, PyVista, NumPy/SciPy | Build stable result extractors |
| Interface coupling | NumPy/SciPy formulations and solver-specific constructs | Treat coupling as a first-class module |
| Backend | Python, FastAPI, Pydantic v2 | Typed contracts and API generation |
| Orchestration | Explicit state machine first; LangGraph only if it adds value | Workflow determinism is more important than agent framework branding |
| Queue/workers | Celery/RQ/Temporal/custom queue as appropriate | Idempotency and artifact safety first |
| Metadata | PostgreSQL | Core typed records and audit data |
| Artifact data | Object store/local S3-compatible store, Parquet, Zarr | Separate metadata from large binaries/fields |
| Dataset versioning | DVC or equivalent | Version curated accepted datasets and model inputs |
| ML | scikit-learn, XGBoost first; PyTorch/PyG later | Baselines before deep models |
| UI | React, TypeScript, three.js, VTK.js | Engineer-oriented views and cross-selection |
| Schema synchronization | Pydantic-to-TypeScript generator | One vocabulary across backend, UI, and agents |
| Container/runtime | Docker/Apptainer as solver environment requires | Capture environment digests in replay manifest |

### 26.2 Licensing discipline

Before commercial distribution, explicitly review licenses and redistribution constraints for all kernel, mesher, solver, repair, UI, and ML components. Keep tool adapters isolated so a commercial solver or licensed kernel can replace an open-source component without rewriting the product control plane.

---

## 27. Repository architecture

Start as a modular monorepo:

```text
fastcad/
  apps/
    api/
    ui/
    worker/

  src/fastcad/
    schemas/
      canonical_model.py
      contracts.py
      interfaces.py
      recipes.py
      qualification.py
      records.py
      replay.py
      budgets.py

    ingest/
      step_import.py
      mesh_import.py
      deck_import.py
      result_import.py
      hashing.py
      units.py

    geometry/
      occt_adapter.py
      topology.py
      analytic_detection.py
      feature_candidates.py
      identity.py
      protected_islands.py
      regions.py
      geometry_oracle.py
      healing.py

    operators/
      base.py
      collar.py
      radial_ribs.py
      bore_to_wall.py
      bore_to_mount.py
      inter_bore_bridge.py
      xk_brace.py
      reinforcement_pad.py
      generated_web_window.py
      tie_rail.py

    constraints/
      contract_compiler.py
      cp_sat.py
      manufacturing.py
      keepouts.py
      feasibility.py

    mesh/
      gmsh_adapter.py
      physical_groups.py
      protected_interface_mesh.py
      quality.py
      repair_ladder.py
      coupling.py

    physics/
      canonical_physics.py
      mapping.py
      deck_builder.py
      audit.py

    solver/
      runner.py
      code_aster.py
      calculix.py
      qualification.py
      resources.py

    post/
      fields.py
      probes.py
      bearing_motion.py
      misalignment.py
      reports.py

    records/
      writer.py
      parquet.py
      zarr.py
      lineage.py
      replay.py
      dvc.py

    campaign/
      state_machine.py
      queue.py
      planner.py
      portfolio.py
      coverage.py
      diversity.py
      recovery.py
      cost.py
      telemetry.py

    intelligence/
      router.py
      policies.py
      context_builder.py
      engineering_graph.py
      architecture_reasoner.py
      failure_memory.py
      decision_audit.py

    ml/
      features.py
      feasibility_models.py
      scalar_surrogates.py
      uncertainty.py
      ood.py
      splits.py
      active_learning.py

    api/
      routes/
      dependencies.py
      services/

  tests/
    unit/
    property/
    golden/
    integration/
    qualification/
    replay/
    generality/

  infra/
    containers/
    compose/
    cluster/

  docs/
    architecture/
    contracts/
    operator_catalog/
    runbooks/
```

---

## 28. Development roadmap

### M0 — Baseline truth and reproducibility

**Goal:** Establish one trustworthy imported GRC baseline.

Build:

- Input manifests and immutable baseline package.
- STEP/mesh/deck/result ingestion adapters.
- Units and coordinate-system handling.
- Deterministic bore/plane/bolt-pattern extraction.
- Initial feature graph and interface candidates.
- Semantic confirmation UI.
- Canonical Engineering Model.
- Initial Design Contract and Qualification Model schemas.
- Baseline deck reconstruction/adapter.
- Bearing-motion extraction.
- Baseline reproduction certificate.
- UI selection bus prototype.

Exit criteria:

- Reference and reconstructed baseline pass reviewed thresholds.
- Critical interfaces are confirmed, typed, and traceable.
- CAD, mesh, physics, and result entities cross-highlight correctly.
- No hardcoded housing names in generic core modules.

### M1 — Feasibility rail

**Goal:** Prove repeatable exact geometry changes without compromising critical interfaces.

Build:

- Interface identity module.
- Protected island and transition-surface model.
- Geometry oracle.
- Manufacturing rule pack v1.
- Operator base contract.
- `add_external_collar` and `add_radial_rib_group`.
- CAD-conforming Gmsh path.
- Mesh quality module.
- Geometry/mesh failure taxonomy and replay manifests.

Exit criteria:

- Parameter sweeps for first operators preserve protected interfaces.
- At least 20 dry-run geometry/mesh candidates qualify.
- All failures are typed, evidenced, and replayable.
- No accepted candidate violates frozen-interface checks.

### M2 — Structural vocabulary

**Goal:** Build topology-diverse but governed structural architectures.

Build:

- Bore-to-wall rib.
- Bore-to-mount support path.
- Inter-bore bridge.
- X/K brace.
- Reinforcement pad.
- Generated-web window.
- Tie rail.
- CP-SAT architecture compatibility and discretized parameter modeling.
- Candidate portfolio diversity measures.

Exit criteria:

- At least four architecture classes appear in qualified dry-run candidates.
- Architecture and parameter coverage are visible.
- No manual global-coordinate placement is needed; all operators use semantic anchors/local frames.

### M3 — Physics and data factory

**Goal:** Produce trustworthy solved records with no manual deck editing during campaign execution.

Build:

- Physics Mapping Layer.
- Variant deck builder.
- Solver worker/job framework.
- Numerical qualification checks.
- Accepted/quarantined/rejected record writer.
- Parquet/Zarr artifacts and DVC snapshots.
- Campaign health dashboard.
- First 40-variant campaign.

Exit criteria:

- End-to-end campaign completes with accepted, quarantined, and rejected outcomes.
- Every outcome has full stage evidence and lineage.
- No manual CAD/deck edit occurs after campaign launch.
- First response distributions and coverage report are available.

### M4 — Autonomous coverage planning

**Goal:** Make campaigns adapt under governed policy.

Build:

- Campaign state machine.
- CP-SAT planner and portfolio planner.
- Coverage model and diversity metrics.
- Bounded recovery state machine.
- Failure memory.
- Cost/resource instrumentation.
- Decision audit log.
- Intelligence router.

Exit criteria:

- A campaign can plan and execute batches using only approved typed configuration.
- Every agent decision is explainable, budget-bound, and references a contract version.
- Yield and coverage are reported together.

### M5 — Dataset and scalar surrogate

**Goal:** Create the first useful predictive loop.

Build:

- Dataset export/versioning workflow.
- Genealogy-aware split engine.
- Scalar response baselines.
- Feasibility predictor prototype.
- Uncertainty and OOD layer.
- Solver fallback policy.
- Active-learning candidate selector.

Exit criteria:

- 100–200 accepted records with documented coverage.
- Held-out architecture/parameter-region performance is reported.
- Predictions expose uncertainty/OOD/evidence.
- High-uncertainty, OOD, or Pareto candidates are routed to solver confirmation.

### M6 — Generality proof and pilot hardening

**Goal:** Demonstrate a reusable product core.

Build:

- Second-part ingestion and contract workflow.
- Adapter hardening for relevant CAD/solver formats.
- Installation/deployment scripts.
- User/admin roles, audit exports, and campaign reproducibility reports.
- Pilot workflow documentation.

Exit criteria:

- A second housing or bracket runs with no GRC-specific core-code branch.
- Only baseline-specific semantic confirmation and contract configuration differ.
- A pilot user can reproduce the workflow with documented runbooks.

---

## 29. First 12-week execution plan

The first 12 weeks should focus on M0–M3 foundations. Do not implement sophisticated agent or deep-learning components before the deterministic rail works.

### Weeks 1–2: Baseline package and reproducibility

- Acquire and freeze the exact GRC CAD, deck, mesh, and reference artifacts.
- Define artifact hashing, file manifest, units, coordinate frames, and directory conventions.
- Build STEP import and basic OCCT topology inspection.
- Parse/import solver deck objects sufficiently to expose materials, loads, constraints, contacts, and outputs.
- Identify baseline result comparison metrics and write the reproduction-certificate template.
- Create the first Pydantic schema package.

**Deliverable:** Immutable `BaselinePackage` plus an inspection report and initial data model.

### Weeks 3–4: Semantic extraction and human confirmation

- Implement analytic cylinder/plane/bolt pattern/coaxial-group detection.
- Implement initial face adjacency graph and geometry signatures.
- Build interface candidate records and semantic confirmation UI.
- Define frozen-interface island representation and local reference frames.
- Implement the first Design Contract editor/workflow.
- Decide exact initial outputs for bearing motion and stress/displacement KPIs.

**Deliverable:** Confirmed baseline semantic map and approved draft contract.

### Weeks 5–6: Baseline physics and output validation

- Build baseline deck execution adapter.
- Implement solver execution wrapper and result storage.
- Implement reaction, displacement, energy, and output-presence checks.
- Implement bearing-seat rigid-fit motion extraction.
- Run mesh/refinement sensitivity checks for critical interface extraction.
- Review and lock reproduction tolerances with engineering judgment.

**Deliverable:** Baseline reproduction certificate; no variant generation yet.

### Weeks 7–8: First exact operators and geometry oracle

- Implement protected-interface comparisons.
- Implement `add_external_collar` and `add_radial_rib_group` using local frames.
- Implement geometry health checks: volume, body count, topology validity, sliver checks, keep-out intersection.
- Implement manufacturing rule pack v1.
- Export/re-import test variant geometry.

**Deliverable:** 10–20 geometry-qualified variants with deterministic replay manifests.

### Weeks 9–10: CAD-conforming mesh and quality pipeline

- Build Gmsh physical-group mapping from semantic/lineage IDs.
- Mesh first variants with protected islands.
- Implement quality metrics and recovery ladder v1.
- Verify bearing interface/coupling consistency across variants.
- Store mesh qualification reports.

**Deliverable:** At least 20 geometry-and-mesh-qualified dry-run records.

### Weeks 11–12: Physics transfer and first end-to-end campaign

- Build explicit mapping audit for baseline physics objects.
- Construct variant solver decks from baseline mappings.
- Execute initial 10–20 solved variants.
- Implement accepted/quarantined/rejected record states.
- Build a minimal campaign dashboard with stage/yield/failure reporting.
- Review top failure modes and prioritize the next operator/recovery improvements.

**Deliverable:** First end-to-end evidence-backed campaign records and a clear M3 backlog.

---

## 30. Testing strategy

### 30.1 Test levels

| Level | Purpose | Examples |
|---|---|---|
| Unit | Individual deterministic functions | cylinder fit, local frame construction, parameter validation |
| Property-based | Broad randomized invariants | invalid parameter rejection, protected island never intersected |
| Golden artifact | Regression against fixed known outputs | baseline extraction, geometry signatures, solver probe outputs |
| Operator integration | Full precondition → build → oracle sequence | collar/rib build with known success/failure cases |
| Pipeline integration | CAD → mesh → physics → solver → record | small fixed campaign |
| Qualification tests | Ensure bad outputs cannot become accepted | missing physics map, bad mesh, NaN result |
| Replay tests | Deterministic rebuild from manifests | selected accepted/rejected variants |
| Generality tests | New part without GRC code branch | bracket or second housing baseline |

### 30.2 Required gates

1. Baseline source import and manifest are deterministic.
2. Baseline reproduction passes reviewed thresholds.
3. Frozen bearing-seat signatures remain unchanged for frozen-interface variants.
4. Every operator passes declared pre/postcondition tests.
5. Every accepted geometry produces a quality-qualified mesh.
6. Physics audit either transfers/rebuilds with evidence or blocks execution.
7. Every accepted solver result passes numerical checks.
8. Every accepted record includes full lineage and replay manifest.
9. UI cross-selection remains correct across CAD/mesh/setup/result representations.
10. Agents cannot exceed typed permissions or retry/premium budgets.

### 30.3 Campaign metrics and targets

Initial targets should be stated as directional and reviewed by difficulty region, not used to hide hard cases:

- Geometry yield: target at least 90% within approved mature operator envelopes.
- Mesh yield: target at least 90% of geometry-qualified variants within mature envelopes.
- Solver yield: target at least 95% of mesh-qualified variants within stable solver setup.
- Replay pass rate: target 100% for selected replay sample set.
- Dataset integrity: 100% of accepted records have complete required lineage/evidence.
- Coverage: report architecture, parameter bins, topology classes, boundary cases, and response distribution.
- Generality: second part executes with no part-specific core branching.

Do not allow planners to improve yield by silently avoiding approved difficult design regions.

---

## 31. Key risks and mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Foreign B-rep boolean fragility | CAD booleans/healing can fail unpredictably | Local operators, checkpoints, geometry oracle, bounded alternatives, typed rejection |
| Silent interface corruption | Seat geometry can change without obvious errors | Deterministic analytic signatures, protected islands, hard gate |
| Existing rib extraction is weak | Castings have blended/branching ribs | Human confirmation, motif detector, coverage report; do not require perfect recognition to begin |
| Meshing damages critical interfaces | Misalignment outputs can become mesh artifacts | CAD-conforming meshing, island reuse, stable coupling verification |
| Physics mapping becomes wrong silently | A valid solve can represent the wrong model | Dedicated mapping layer, transfer/rebuild distinction, block ambiguity |
| High yield but poor diversity | Dataset becomes narrow and misleading | Report yield plus coverage; use quotas and diversity planning |
| Surrogate leakage | Sibling variants inflate metrics | Genealogy/architecture/region holdouts |
| Agent hides unsafe action | LLM behavior is hard to audit | Typed tools, contract binding, deterministic gates, audit records, bounded retries |
| Unmanaged HPC spend | Campaign costs grow rapidly | Budget model, cost telemetry, feasibility screen, batch planning |
| Premium LLM overuse | Cost/latency without engineering value | Router, budgets, batch-only strategic reasoning, DOE baseline comparison |
| Licensing blocks commercial path | Solver/mesher/kernel redistribution constraints | Early legal/license review; adapter boundaries and replaceable backends |
| Scope explosion | Product becomes generic CAD or broad CAE platform | Maintain narrow wedge: governed design-family automation and qualified simulation data |

---

## 32. Demo definition

### 32.1 First credible demo

Show the following, in sequence:

1. Import the GRC baseline package.
2. Show deterministic extraction of candidate bores, mounts, planes, mesh groups, and baseline physics objects.
3. Let the engineer confirm bearing seats, mounts, editable zones, and rules.
4. Approve a Design Contract.
5. Choose at least four structural architecture families.
6. Generate a 40-candidate portfolio with visible architecture/parameter diversity.
7. Execute geometry, mesh, physics mapping, solver, and qualification without manual file editing.
8. Show campaign health: yields, budget, failures, retry decisions, and coverage.
9. Explore accepted records with CAD/mesh/physics/result cross-linking.
10. Display mass, stress, displacement, bearing motion, and gear-misalignment-relevant outcomes.
11. Show a first scalar-surrogate ranking only with uncertainty/OOD labels and solver-confirmation policy.

### 32.2 Stronger proof

Repeat the same flow on a second housing or bracket with a new baseline and Design Contract, without altering generic core code.

### 32.3 What not to demo prematurely

- A natural-language chat command that creates arbitrary CAD.
- A visually impressive but unverified generated shape.
- A large surrogate trained on mixed-quality records.
- A high yield number without coverage and failure disclosure.
- A “fully autonomous engineer” claim.

---

## 33. Commercialization path

### 33.1 Early customer value

Sell the product first as a private/on-prem or controlled-environment engineering campaign accelerator for organizations that already possess:

- Trusted baseline CAD/CAE models.
- Repetitive structural variant exploration work.
- Solver capacity but scarce analyst time.
- Need for traceable design-space exploration and internal data generation.

### 33.2 Initial service-plus-product motion

Early engagements may combine:

- Baseline onboarding and solver adapter work.
- Design Contract definition workshop.
- Operator/rule pack configuration.
- A governed 40–200 variant campaign.
- Dataset delivery and surrogate feasibility assessment.

Productize the repeatable control plane, interfaces, qualification framework, record model, and campaign UI. Treat customer-specific physics adapters and initial rule calibration as high-value onboarding services until standardized.

### 33.3 Long-term platform expansion

After the Stage-1 wedge works, expand in this order:

1. More structural parts: brackets, housings, enclosures, mounts, frames.
2. Additional solver/deck adapters.
3. More load cases and optimization objectives.
4. Moved-interface regimes.
5. Higher-fidelity local models and graph representations.
6. Field-response learning and reduced-order models.
7. Multi-physics extensions such as thermal/structural coupling.
8. Digital-twin integration and telemetry-informed model updating.

Do not expand the design freedom faster than the qualification and provenance system can support it.

---

## 34. Final operating rules

1. Do not pay a premium model to answer what deterministic engineering tools already know.
2. Do not let any model issue arbitrary CAD, mesh, or solver commands.
3. Do not accept a completed solver run without geometry, mesh, physics, numerical, and replay evidence.
4. Do not use fields/SDFs as trusted final geometry for interface-sensitive gearbox analysis.
5. Do not train response surrogates on quarantined or rejected records.
6. Do not optimize yield without displaying design-space and architecture coverage.
7. Do not claim part-agnostic behavior until the second-part proof passes.
8. Do not build full generative CAD before the typed operator grammar and qualification rail work.
9. Do not let a planner suppress difficult approved regions without reporting that decision.
10. Do not change an approved contract silently; every change makes a new version.
11. Do not treat provenance as logging; make it a required product object and acceptance gate.
12. Optimize the system for **engineering information gained per expensive CAD/mesh/FEA cost**.

---

## 35. Final definition of success

fastCAD succeeds when an engineer can take an existing trusted CAE baseline, confirm its critical engineering context once, approve a governed design family, and launch a campaign that autonomously produces diverse, comparable, solver-qualified structural variants with complete evidence.

The system should understand enough context to propose meaningful architecture families, use deterministic tools to realize and certify them, learn from failures and accepted data, and adapt subsequent batches under explicit budget and contract constraints.

The final product is not an AI that draws parts. It is a governed engineering experiment system:

```text
One trusted model
        ↓
Many valid structural experiments
        ↓
Many qualified geometry–physics records
        ↓
A proprietary engineering dataset
        ↓
Trustworthy surrogate-guided design decisions
```
