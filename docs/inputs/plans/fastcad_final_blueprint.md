# fastCAD: Constraint-Governed Engineering Simulation Data Factory

## End-to-End Product, Architecture, and Implementation Blueprint

**Status:** Final synthesized direction for Stage 1

**Primary demonstrator:** NREL GRC gearbox rear housing (drawing 254492)

**Primary goal:** Generate 100–200 diverse, feasible, reproducible and engineering-qualified gearbox-housing geometry variants; solve them using a trusted CAE pipeline; and produce a traceable dataset suitable for later surrogate modeling and active learning.

---

## 1. Executive decision

fastCAD should not begin as a natural-language CAD editing product, a general CAD modeler, a generic topology-optimization tool, or an implicit-geometry FEA platform.

It should begin as a **constraint-governed engineering simulation-data factory**:

> Import one trusted engineering analysis, define exactly what may vary, automatically generate diverse qualified variants, and convert successful simulations into AI-ready engineering records.

The Stage-1 product is deliberately narrow:

```text
Trusted baseline CAD/mesh/deck/result
        ↓
Extract and confirm engineering context
        ↓
Approve a Design Contract
        ↓
Generate feasible geometry recipes
        ↓
Construct exact CAD variants
        ↓
CAD-conforming mesh and inherited physics
        ↓
Solve, qualify and preserve evidence
        ↓
Accepted simulation records
        ↓
Later: surrogates, active learning and design optimisation
```

The competitive differentiation is not that fastCAD can add a rib. CAD, implicit modeling, design exploration and AI prediction tools already exist. The differentiation is that fastCAD preserves engineering intent, controls variation, validates each transition, and produces a trustworthy data asset from an existing CAE case.

---

## 2. Product thesis

### 2.1 The user problem

An engineering team may possess:

- A production or advanced-development CAD model.
- A solver mesh and deck.
- Boundary conditions, loads, materials, contacts and output requests.
- A baseline result they already trust.
- A need to explore many allowable structural variants.
- A need for data to train an optimisation or surrogate model.

Today, creating hundreds of meaningful variants often requires repeated manual CAD edits, remeshing, deck work, solver execution, post-processing and data cleanup. The bottleneck is not only compute. It is preserving the original simulation context while safely changing geometry.

### 2.2 The fastCAD promise

```text
One validated engineering case
        ↓
One approved design family
        ↓
Many controlled structural variants
        ↓
Many qualified geometry–physics records
        ↓
A reusable simulation dataset
        ↓
A trustworthy surrogate and active-learning loop
```

### 2.3 What fastCAD is

fastCAD is:

- A design-family compiler.
- A simulation campaign control plane.
- A geometry/mesh/physics qualification system.
- A lineage and provenance system.
- A dataset factory for engineering AI.
- An agent-orchestrated workflow around deterministic engineering tools.

### 2.4 What fastCAD is not in Stage 1

fastCAD is not:

- A chat-to-CAD product.
- A replacement for CATIA, NX, Creo, SolidWorks or nTop.
- A free-form generative-CAD product.
- An LLM that invents engineering semantics.
- A field/voxel-only FEA solution for interface-sensitive gearbox analysis.
- An autonomous final-design approval system.

---

## 3. Core differentiation

### 3.1 Plain statement

> CAD tools help engineers create geometry. CAE tools solve individual models. AI tools learn from existing datasets. fastCAD turns one trusted CAE model into a governed design family, a validated simulation dataset, and eventually a trustworthy surrogate.

### 3.2 The five differentiators

1. **Engineering-context inheritance**
   - The customer supplies a trusted simulation rather than describing the problem from scratch.
   - Existing loads, boundary conditions, materials, solver context and outputs are extracted, shown and governed.

2. **Design Contract**
   - Every campaign has an explicit, versioned definition of immutable interfaces, mutable regions, allowed operations, parameter ranges and engineering rules.

3. **Engineering-entity identity and lineage**
   - The system knows what came from source CAD, what was derived, what was generated, what was preserved, split, merged, deleted or created.

4. **Qualification Plane**
   - Every variant must pass identity, geometry, manufacturing, mesh, physics-transfer, solver and engineering-usefulness checks.

5. **Accepted simulation records**
   - The output is not a pile of result files. It is a vetted dataset with complete provenance, failure records and training eligibility.

---

## 4. The three truth layers

fastCAD must keep three distinct models. Blurring them creates unsafe automation.

```text
Canonical Engineering Model
        ↓
What exists in the imported customer package

Design Contract
        ↓
What may change in a specific campaign

Qualification Model
        ↓
What must remain true before a variant is accepted
```

### 4.1 Canonical Engineering Model

The canonical model is an immutable normalized representation of the imported engineering input.

It includes:

- CAD geometry and source-file hashes.
- Geometric entities and extracted feature candidates.
- Mesh entities and element/node groups.
- Solver deck objects.
- Materials, sections, loads, constraints, contacts and output requests.
- Coordinate systems and units.
- Reference solution metadata and available fields.
- Provenance and extraction confidence.

### 4.2 Design Contract

The Design Contract specifies how the baseline may vary.

It includes:

- Frozen interfaces.
- Moved interfaces, if deliberately allowed.
- Mutable design zones.
- Allowed operator types.
- Valid feature anchors.
- Parameter domains.
- Discrete configuration logic.
- Geometric and manufacturing constraints.
- Physics-transfer policies.
- Campaign objectives.
- Approval state and version.

### 4.3 Qualification Model

The Qualification Model defines evidence required before an output becomes a trusted record.

It includes:

- Interface identity requirements.
- Geometric invariants.
- Manufacturing acceptance rules.
- Meshing acceptance rules.
- Physics mapping rules.
- Solver and numerical checks.
- Engineering plausibility rules.
- Dataset eligibility rules.
- Reproducibility requirements.

---

## 5. Stage-1 scope

### 5.1 Primary objective

Generate and solve 100–200 accepted GRC gearbox-housing variants without manual CAD/deck editing during a campaign.

### 5.2 Required outcome

Each accepted record must contain:

```text
Variant recipe
+ contract version
+ geometry artifact
+ geometry qualification report
+ mesh artifact and quality report
+ physics-transfer audit
+ solver inputs and outputs
+ bearing-seat motion and tilt extraction
+ gear-misalignment-relevant outputs
+ engineering qualification report
+ deterministic replay manifest
```

### 5.3 Initial GRC design space

Do not change nominal bearing-bore centres, axes, bearing diameters, gear centre distances, primary mounting coordinates, sealing faces or other frozen interfaces in the first campaign.

Focus on structural support material around those interfaces:

- Bearing-seat external collars.
- Radial and tangential ribs.
- Bore-to-wall paths.
- Bore-to-mount paths.
- Inter-bearing bridges.
- X/K-braced bridges.
- Front-to-rear tie rails.
- Circumferential belts.
- Local reinforcement pads.
- Split-line and flange reinforcement.
- Windows/pockets only in generated webs or approved low-sensitivity zones.
- Approved wall-thickness zones.

### 5.4 Later moved-interface regimes

Support these only after the frozen-interface pipeline is proven:

- Bore diameter changes.
- Bearing centre and axis changes.
- Mount position changes.
- Envelope enlargement/reduction.
- New housing family generation.

These require additional rework, assembly, centre-distance, comparison-frame and re-baseline rules.

---

## 6. GRC housing strategy

### 6.1 Frozen engineering core

For the first GRC campaign, the frozen core should include at least:

- Bearing-seat analytic cylinders and seat end boundaries.
- Gear/shaft packaging-clearance regions.
- Essential bolt interfaces.
- Machined datum faces.
- Mounting interfaces required by the baseline FE model.
- Split-line/sealing interfaces where appropriate.
- Baseline coordinate systems and named reference points.

### 6.2 Mutable design region

The mutable region is the structural material outside protected interface islands and outside keep-out zones.

```text
Frozen bearing-seat island
        +
Frozen mounting / sealing / datum islands
        +
Frozen clearance volumes
        +
Approved editable structural zones
        =
Governed GRC design family
```

### 6.3 Relevant variant classes

| Class | Structural intent | Examples |
|---|---|---|
| Bearing support | Change local bore-support stiffness without changing bore | collar, radial ribs, tangential ribs, local pad |
| Inter-bearing coupling | Control differential support movement | straight bridge, deep bridge, double web, X/K brace |
| Bore-to-mount path | Alter how bearing loads reach mounts | diagonal rib, triangular web, shared trunk, base rail |
| Front–rear coupling | Control shaft-support differential motion | tie rail, sidewall spine, boxed corridor |
| Joint/split-line support | Control cover/flange flexibility | flange thickening, bolt-boss support, cover rib |
| Global shell | Redistribute structural material | wall zone, belt, local bulkhead, approved windowed web |
| Hybrid | Combine approved classes | collar + bridge + window + tie rail |

### 6.4 Do not confuse architecture with dimensions

A campaign should contain architecture diversity, not only many values of rib height.

```text
Weak campaign:
40 values of one rib height

Strong campaign:
collar architecture
+ radial-rib architecture
+ inter-bore bridge architecture
+ X-brace architecture
+ bore-to-mount path architecture
+ tie-rail architecture
+ windowed structural web architecture
+ selected hybrids
```

---

## 7. Geometry representation strategy

### 7.1 Trusted analysis representation

For GRC bearing-motion and gear-misalignment outputs, use exact B-rep geometry and CAD-conforming tetrahedral meshing as the trusted path.

```text
Imported STEP B-rep
        ↓
Local exact B-rep operations
        ↓
CAD-conforming surface and volume mesh
        ↓
TET10 FE model
        ↓
Stable bearing-seat coupling and motion extraction
```

### 7.2 Field/SDF representation

Field, voxel and SDF methods are useful but must not be the authority for final interface-sensitive analysis.

Use fields for:

- Candidate screening.
- Collision and clearance tests.
- Approximate wall-thickness tests.
- Feature-layout planning.
- Region visualization.
- Fast plausibility estimates.
- Potential later proposal models.

Do not use field-only geometry as the high-fidelity analysis representation when it smooths or changes bearing-seat geometry, critical sharp edges, face groups or coupling membership.

### 7.3 Why protected interfaces matter

If a variant remeshes a bearing cylinder differently each time, changes in bore translation/tilt may partly reflect surface approximation, coupling-node selection or mesh variation rather than actual housing stiffness.

The system must ensure that the numerical definition of each key interface remains stable.

---

## 8. Interface identity and lineage

### 8.1 InterfaceIdentity

Every critical engineering entity must be a first-class typed object.

```python
class InterfaceIdentity(BaseModel):
    semantic_id: str
    source_entity_ids: list[str]
    role: str
    geometry_signature: GeometrySignature
    topology_signature: TopologySignature
    reference_frame: InterfaceFrame
    allowed_deviation: DeviationPolicy
    ownership_rule: OwnershipRule
    regeneration_rule: MappingRule | None
    status: Literal["FROZEN", "MOVED", "RETIRED", "AMBIGUOUS"]
```

### 8.2 Geometry signature

A bearing seat should be identified deterministically by more than a face number:

- Surface type: analytic cylinder.
- Centre/origin.
- Axis direction.
- Radius/diameter.
- Axial limits.
- Area and angular span.
- Neighbourhood/topology signature.
- Source face IDs where preserved.
- Cylinder-fit residual.

### 8.3 Entity genealogy states

Every source/generated object should have one of these lineage states:

```text
IMPORTED
DERIVED
PRESERVED
TRANSFORMED
SPLIT
MERGED
CREATED
DELETED
AMBIGUOUS
```

### 8.4 Identity authority

Identity must be certified using deterministic geometry and topology checks. ML may assist recognition or flag suspicious situations, but it must not be the final authority for a bearing seat, mount, seal, datum or physics entity.

---

## 9. Protected interface islands

### 9.1 Definition

A protected interface island is a local exact CAD and mesh region surrounding a critical interface.

For a bearing seat, it includes:

- Exact cylindrical seat.
- Axial seat limits.
- Local surrounding collar.
- Nearby datum or reference surfaces.
- Stable coordinate frame.
- An artificial transition boundary located outside the sensitive region.

### 9.2 Purpose

```text
Variant may alter surrounding compliance
but may not alter the geometric or numerical definition
used to measure bearing-seat motion.
```

### 9.3 Mesh options

| Option | Use | Requirement |
|---|---|---|
| Conformal shared-node interface | Preferred | Variant bulk must reuse the transition triangulation |
| Tied/nonconformal interface | Fallback | Transition must be far enough from the sensitive bore region; validate convergence |
| MPC/RBE-style coupling | Controlled special case | Explicit formulation and verification required |
| Embedded/mortar/contact-like approach | Later/special cases | Must have a formal coupling contract |

### 9.4 Interface coupling module

Coupling must be a dedicated module, not a hidden side effect of meshing.

It decides and records:

- Interface type.
- Slave/master or symmetric policy.
- Node correspondence or interpolation map.
- Stiffness/constraint method.
- Validation test.
- Applicability envelope.
- Reuse or regeneration policy.

---

## 10. Operator contracts

### 10.1 Why operator contracts are mandatory

An operation cannot simply mean “add a rib here.” For production reliability, every operator needs an executable contract.

```text
Operator
 ├── Preconditions
 ├── Input entities and anchor roles
 ├── Reference frames
 ├── Parameter domain
 ├── Protected entities
 ├── Construction method
 ├── Expected topology effect
 ├── Postconditions
 ├── Manufacturing invariants
 ├── Failure modes
 ├── Rollback strategy
 └── Evidence emitted
```

### 10.2 Base protocol

```python
class Operator(Protocol):
    name: str
    version: str

    def validate_preconditions(
        self,
        model: CanonicalEngineeringModel,
        contract: DesignContract,
        request: OperatorCall,
    ) -> PreconditionReport: ...

    def resolve(
        self,
        shape: ShapeRef,
        anchors: list[InterfaceIdentity],
        request: OperatorCall,
    ) -> Placement: ...

    def build(
        self,
        shape: ShapeRef,
        placement: Placement,
        request: OperatorCall,
    ) -> BuildResult: ...

    def validate_postconditions(
        self,
        before: ShapeRef,
        after: ShapeRef,
        placement: Placement,
        contract: DesignContract,
    ) -> OperatorQualification: ...

    def rollback(self, checkpoint: ShapeRef) -> ShapeRef: ...
```

### 10.3 Example: BoreToWallRib contract

**Preconditions**

- Anchor bearing seat exists and passes identity validation.
- Editable wall target exists.
- Rib path lies within an approved mutable zone.
- Path does not cross keep-out volumes.
- Chosen dimensions are inside the approved parameter domain.

**Postconditions**

- Rib is attached to the required structural body.
- Protected bearing seat is unchanged within tolerance.
- Minimum rib thickness and root radius are satisfied.
- No zero-thickness/sliver faces were created.
- Feature remains attached after healing.
- Expected volume change is within tolerance.
- Exact topology event is recorded.
- Result passes local meshability screening.

**Failure modes**

```text
ANCHOR_NOT_FOUND
INVALID_PATH
KEEP_OUT_INTERSECTION
BOOLEAN_FAILURE
SLIVER_CREATED
PROTECTED_INTERFACE_CHANGED
DISCONNECTED_FEATURE
MIN_THICKNESS_VIOLATION
HEALING_FAILURE
LOCAL_MESH_FAILURE
```

### 10.4 First operators

Build only a compact high-value library initially:

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

Each one must use named anchors and local frames, never hardcoded global coordinates.

---

## 11. Manufacturing rule engine

Manufacturability is not one boolean. It is an executable collection of rules with scope and evidence.

### 11.1 Acceptance levels

```text
1. Geometrically feasible
2. Manufacturable
3. Numerically solvable
4. Structurally acceptable
5. Engineering-useful
```

A candidate can pass an earlier level and fail a later one.

### 11.2 Cast-housing rules

The initial GRC rule pack should include configurable values for:

- Minimum wall thickness.
- Minimum rib thickness.
- Rib-to-wall thickness ratio.
- Minimum rib root radius.
- Minimum fillet/blend radius.
- Maximum abrupt section transition.
- Draft angle and pull-direction compatibility.
- Minimum spacing between parallel features.
- Minimum ligament around windows and holes.
- No zero-thickness contacts.
- No unintended internal voids.
- No prohibited undercuts under declared tooling assumptions.
- Core accessibility/check envelope where modeled.
- Machining allowance and machining-access keep-outs where supplied.
- Boss/collar support rules.
- Rules preventing unsupported thick isolated regions/hot-spot-prone junctions.

### 11.3 Style rules

Extract baseline design language where possible and expose it as reviewable defaults:

- Typical wall thickness bands.
- Rib thickness bands.
- Common fillet radii.
- Common draft direction.
- Feature spacing.
- Existing symmetry patterns.

These are not automatically hard constraints. The user decides whether each becomes advisory or binding in the Design Contract.

---

## 12. Extraction architecture

### 12.1 Principle

Extraction must be honest. It must not invent engineering semantics.

Each finding has:

```text
Imported / Derived / Inferred candidate / Confirmed by user / Generated
```

and a confidence level:

```text
HIGH / MEDIUM / LOW / NOT DETECTED
```

### 12.2 Deterministic extraction first

Use OpenCascade-based deterministic methods for geometry classes with strong analytic signatures:

- Planes.
- Cylinders.
- Cones.
- Spheres/tori where relevant.
- Holes and bore candidates.
- Coaxial cylinder groups.
- Bolt patterns.
- Planar mounting faces.
- Split-line candidates.
- Bounding box and principal directions.
- Face adjacency graph.
- Edge convexity/concavity.
- Surface area, normals and curvature.

### 12.3 Rib extraction reality

Existing ribs are difficult to extract perfectly from production cast B-reps because they may blend into walls, share fillets, branch, taper and use nonuniform geometry.

Use a staged strategy:

1. Deterministic candidate detection.
   - Thin-wall regions.
   - Elongated faces.
   - High-curvature blend boundaries.
   - Thickness-map ridges.
   - Face-adjacency motifs.
   - Repeated radial patterns near bosses/bearing regions.

2. Feature graph classification.
   - Build an attributed adjacency graph from faces, edges, curvature, surface classes, local thickness and graph neighbourhood.

3. Optional ML-assisted recognition.
   - Use B-rep graph/GNN methods only as a candidate-ranking or annotation aid.
   - Do not make pretrained machining-feature models the final authority on cast gearbox ribs.

4. Human confirmation.
   - Present candidate rib groups in the UI.
   - Let the engineer confirm, reject, merge, split or name them.

### 12.4 Extraction output

```python
class ExtractionResult(BaseModel):
    baseline_id: UUID
    findings: list[ExtractedEntity]
    unresolved_items: list[UnresolvedQuestion]
    coverage: CoverageReport
    source_provenance: list[ArtifactReference]
```

### 12.5 Minimal human effort

Minimize labelling by asking only high-value questions:

- Is this cylinder a bearing seat, bore, or nonfunctional feature?
- Which interfaces are frozen?
- Which regions may receive new structural material?
- Which candidate ribs are meaningful existing features?
- Which source groups correspond to loads, supports, contacts and mounts?
- Which manufacturing assumptions are binding?

The system should prefill candidates and require confirmation only where ambiguity affects the Design Contract.

---

## 13. Canonical engineering graph

### 13.1 Graph layers

```text
Geometry graph
  faces, edges, solids, analytic surfaces, adjacency

Feature graph
  bore, seat, bolt pattern, wall, rib candidate, boss candidate, fillet candidate

Engineering semantic graph
  bearing seat, mount, datum, sealing face, load surface, support region, contact pair

Physics graph
  materials, loads, constraints, contacts, analysis steps, output requests

Design Contract graph
  frozen/mutable/moved entities, operator permissions, rules, dependencies

Variant lineage graph
  source → operation → created/modified entities → mesh → physics → solve → record
```

### 13.2 Context graph role

The context graph is the common language for UI, API, deterministic tools and agents. Nothing should be passed only as prose.

---

## 14. Typed schemas: one shared language

### 14.1 Rule

Pydantic models are the backend source of truth. Generate TypeScript types and client schemas from the API/OpenAPI model. Do not maintain independently hand-written copies of critical schemas.

### 14.2 Required schema groups

```text
schemas/
  primitives.py
  artifacts.py
  geometry.py
  interfaces.py
  extraction.py
  physics.py
  contract.py
  operators.py
  qualification.py
  campaigns.py
  jobs.py
  records.py
  surrogate.py
  agent.py
```

### 14.3 Important Pydantic models

```python
class CanonicalEngineeringModel(BaseModel): ...
class InterfaceIdentity(BaseModel): ...
class InterfaceFrame(BaseModel): ...
class ExtractedEntity(BaseModel): ...
class DesignContract(BaseModel): ...
class QualificationModel(BaseModel): ...
class OperatorCall(BaseModel): ...
class VariantRecipe(BaseModel): ...
class PhysicsMappingDecision(BaseModel): ...
class StageResult(BaseModel): ...
class FailureRecord(BaseModel): ...
class Campaign(BaseModel): ...
class JobSpec(BaseModel): ...
class AcceptedSimulationRecord(BaseModel): ...
class ContextEnvelope(BaseModel): ...
```

### 14.4 Stable IDs

Every object must have a stable UUID/string identifier:

```text
baseline_id
entity_id
interface_id
contract_id
contract_version
operator_call_id
variant_id
mesh_id
physics_mapping_id
job_id
record_id
agent_decision_id
```

---

## 15. Design Contract

### 15.1 Example schema

```python
class DesignContract(BaseModel):
    baseline_id: UUID
    contract_id: UUID
    version: int
    status: Literal["DRAFT", "IN_REVIEW", "APPROVED", "SUPERSEDED"]

    frozen_interfaces: list[InterfaceRule]
    moved_interfaces: list[MovedInterfaceRule]
    mutable_regions: list[MutableRegion]
    keep_out_regions: list[KeepOutRegion]

    allowed_operators: list[OperatorPermission]
    parameter_domains: list[ParameterDomain]
    logical_constraints: list[LogicalConstraint]
    geometric_constraints: list[GeometryConstraint]
    manufacturing_constraints: list[ManufacturingConstraint]
    physics_transfer_rules: list[PhysicsTransferRule]

    campaign_objectives: list[CampaignObjective]
    approvals: list[Approval]
```

### 15.2 UI edits become binding rules

When a user:

- Renames `CYLINDER_14` to `HSS_B_BEARING_SEAT`.
- Marks it `FROZEN`.
- Adds an exclusion zone around it.
- Defines a new rib path.
- Sets a minimum rib thickness.
- Disables a class of geometry changes.

the UI creates a typed revision to the Design Contract. That revision becomes the binding context for planners, operators, meshing, physics mapping, agents and later campaigns.

### 15.3 Approval gate

A campaign cannot execute against an unapproved contract.

```text
DRAFT
  ↓
USER REVIEW
  ↓
APPROVED
  ↓
CAMPAIGN EXECUTION
```

Any edit after approval creates a new revision. Existing records remain linked to the old revision.

---

## 16. Physics Mapping Layer

### 16.1 Why it exists

Copying a solver deck is easy. Determining whether its entities remain physically meaningful after a geometry change is hard.

```text
Source physics entity
        ↓
Semantic mapping
        ↓
Candidate target entities
        ↓
Applicability test
        ↓
Confidence / ambiguity
        ↓
TRANSFER / REBUILD / BLOCK
```

### 16.2 Transfer statuses

```text
TRANSFERRED
TRANSFERRED_NOT_EQUIVALENT
REBUILT_BY_RULE
REQUIRES_REVIEW
BLOCKED
MISSING
```

“Transferred” must never mean “physically equivalent” by default.

### 16.3 Physics mapping decision

```python
class PhysicsMappingDecision(BaseModel):
    source_physics_id: str
    source_entity_ids: list[str]
    target_entity_ids: list[str]
    mapping_method: str
    applicability_status: str
    equivalence_status: str
    confidence: float
    evidence: list[Evidence]
    required_action: Literal["TRANSFER", "REBUILD", "BLOCK", "REVIEW"]
```

### 16.4 Mapping methods

Use deterministic methods first:

- Preserved source IDs where possible.
- Analytic signature matching.
- Surface overlap.
- Normal/direction consistency.
- Area/extent comparison.
- Parent-child split/merge lineage.
- Local-frame consistency.
- Named mesh group transfer through protected regions.

Use ML similarity only to rank ambiguous candidates already identified as requiring review; never use it as the authority for load, contact or constraint transfer.

### 16.5 Examples

```text
Bearing coupling target preserved
→ TRANSFERRED

Pressure surface split into two child faces
→ REBUILT_BY_RULE, preserve pressure magnitude and approved resultant policy

Contact partner deleted by geometry operation
→ BLOCKED

Load surface exists but changed orientation/area beyond policy
→ TRANSFERRED_NOT_EQUIVALENT or REQUIRES_REVIEW
```

---

## 17. Baseline reproduction and calibration

### 17.1 Formal stage

Baseline reproduction is not a dashboard feature. It is a calibration gate.

```text
Reference CAE result
        ↓
Reconstructed fastCAD pipeline
        ↓
Comparison metrics
        ↓
Calibrated acceptance bands
        ↓
Reproduction Certificate
```

### 17.2 Required comparisons

Where results are available, compare:

- Applied force and moment resultants.
- Reaction force and moment resultants.
- Maximum and selected-point displacement.
- Displacement norm.
- Strain energy.
- Stress at approved non-singular probe regions.
- Field correlation/mapped field error.
- Modal quantities where applicable.
- Bearing-interface translations and rotations.
- Mesh sensitivity.

### 17.3 Tolerance policies

Every check must declare its metric form:

```text
absolute tolerance
relative tolerance
RMS tolerance
maximum-error tolerance
field correlation threshold
engineering-significance threshold
```

### 17.4 Result

```python
class ReproductionCertificate(BaseModel):
    baseline_id: UUID
    reference_solver: SolverIdentity
    reproduced_solver: SolverIdentity
    checks: list[CalibrationCheck]
    status: Literal["PASS", "REVIEW", "FAIL"]
    approved_by: list[Approval]
```

---

## 18. Qualification Plane

### 18.1 Cross-cutting architecture

The Qualification Plane spans all pipeline stages.

```text
                 QUALIFICATION PLANE
┌─────────────────────────────────────────────────────────────┐
│ Identity │ Geometry │ Manufacturing │ Mesh │ Physics │ Solver│
└─────────────────────────────────────────────────────────────┘
        ↓       ↓            ↓           ↓        ↓        ↓
                 PASS / QUARANTINE / REJECT
```

### 18.2 Every stage must answer

```text
What did we expect?
What actually happened?
Is the difference acceptable?
What evidence proves it?
What is the next permitted action?
```

### 18.3 Qualification states

```text
PASSED
FAILED
QUARANTINED
BLOCKED
REQUIRES_REVIEW
SKIPPED_WITH_REASON
```

### 18.4 Engineering qualification

A solver-qualified run is not automatically engineering-qualified.

Engineering qualification checks include:

- Loads remain correctly oriented and applied to intended regions.
- No unexpected rigid-body response.
- Bearing-motion extraction remains valid.
- Output remains comparable to the intended baseline/campaign purpose.
- Variant has not accidentally altered a frozen interface or analysis condition.
- Results fall within declared physically plausible/scaling ranges.
- Required output fields and metadata exist.

---

## 19. Geometry oracle and failure handling

### 19.1 Silent-failure oracle

Every geometry operation must be followed by a standard oracle.

```text
Check valid solid
Check expected volume change
Check protected interfaces unchanged
Check only allowed regions changed
Check topology invariants
Check local geometric rules
Check preliminary meshability
```

### 19.2 Failure record

```python
class FailureRecord(BaseModel):
    failure_id: UUID
    variant_id: UUID
    stage: str
    code: str
    severity: str
    locations: list[str]
    operator_sequence: list[str]
    parameter_values: dict[str, Any]
    kernel_version: str
    artifacts: list[ArtifactReference]
    attempted_repairs: list[RepairAttempt]
    final_disposition: Literal["RETRY", "QUARANTINE", "REJECT"]
```

### 19.3 Failure as a dataset

Store all failed attempts, not only successes:

```text
geometry failure
mesh failure
physics-mapping failure
solver failure
numerical instability
engineering rejection
```

Later, this supports a feasibility surrogate:

```text
candidate
    ↓
P(geometry success)
P(mesh success)
P(physics transfer success)
P(solver success)
    ↓
planner prioritization
```

### 19.4 Bounded recovery

The agent may only choose among explicit retry policies returned by a deterministic tool.

```text
Geometry
- alternate local Boolean strategy
- local healing
- reject

Mesh
- local refinement
- modified mesh sizing
- CAD repair route
- quarantine

Solver
- approved solver retry
- mapping rebuild route
- reject
```

No infinite retries. No unlogged manual fixes. No agent-generated solver internals.

---

## 20. Mesh architecture

### 20.1 Primary meshing path

Use a CAD-conforming B-rep mesher for trusted geometry variants.

```text
B-rep variant
        ↓
Named CAD surface groups
        ↓
CAD-conforming surface mesh
        ↓
Constrained tetrahedral volume mesh
        ↓
TET10 conversion/refinement policy
        ↓
Mesh quality and interface checks
```

### 20.2 Recommended open-source approach

- OpenCascade-based geometry editing through pythonOCC/build123d/CadQuery-level tools.
- Gmsh with OpenCascade geometry for CAD-conforming meshing and physical groups.
- meshio/VTK/PyVista for interchange and inspection.
- MeshFix/libigl/PyMeshLab only in controlled repair paths.
- fTetWild only as a robust fallback and explicitly marked as an approximate-surface route.

### 20.3 Mesh recovery ladder

```text
CAD-conforming Gmsh mesh
        ↓
quality gate
        ↓
controlled local repair/refinement
        ↓
approved geometry-healing attempt
        ↓
last-resort robust tetrahedralization
        ↓
quarantine if fidelity requirements are not met
```

### 20.4 Mesh requirements for bearing seats

For frozen interface campaigns, verify:

- Analytic seat geometry unchanged.
- Surface group identity unchanged.
- Canonical/reused island mesh where applicable.
- Stable coupling membership and weights.
- Cylinder-fit residual below threshold.
- Mesh convergence of bore-motion metrics.

---

## 21. Bearing-motion extraction

### 21.1 Stable interface definition

Do not find “nodes near a bore” independently per variant.

Define a permanent interface object:

```python
class BearingSeatInterface(BaseModel):
    interface_id: str
    frame: InterfaceFrame
    analytic_geometry: CylinderDescriptor
    protected_island_id: UUID | None
    node_set_policy: NodeSetPolicy
    coupling_policy: CouplingPolicy
    output_policy: BearingMotionOutputPolicy
```

### 21.2 Motion extraction

Use a weighted least-squares rigid fit over the controlled seat-node set:

\[
\min_{\mathbf{t},\boldsymbol{\theta}}
\sum_i w_i
\left\|
\mathbf{u}_i-
\left(
\mathbf{t}+
\boldsymbol{\theta}\times
(\mathbf{x}_i-\mathbf{x}_0)
\right)
\right\|^2
\]

Store:

- Rigid translation.
- Rigid rotation/tilt.
- Radial expansion.
- Ovalization indicators.
- Higher-order residual distortion.
- Fit residual.

### 21.3 Gear-misalignment relevance

The housing dataset should expose bearing/interface motion so later gearbox-system/LTCA models can map it to:

- Relative shaft-axis tilt.
- Centre-distance change.
- Lead-direction mesh misalignment.
- Profile-direction mesh misalignment.
- Axial displacement.
- Drive/coast asymmetry.

---

## 22. CP-SAT, DOE and search architecture

### 22.1 Separate responsibilities

```text
CP-SAT
= Which discrete architecture/configuration combinations satisfy binding logical rules?

DOE / portfolio planning
= Which feasible candidates give diverse coverage?

Continuous optimisation / Bayesian optimisation / active learning
= Which continuous parameter settings are most informative or promising?

Exact geometry + mesh + FEA
= Is the candidate actually valid and what is the engineering response?
```

### 22.2 CP-SAT use

Use CP-SAT for:

- Presence/absence of features.
- Architecture choice.
- Pattern count.
- Mutually exclusive features.
- Feature dependencies.
- Approved discrete dimension catalogues.
- Symmetry and asymmetry rules.
- Manufacturing configuration logic.
- Coverage quotas across architecture classes.

Do not make CP-SAT the authority for continuous geometric feasibility, meshing or structural adequacy.

### 22.3 Continuous layer

Design the interface now, even if implemented later:

```text
CP-SAT feasible recipe family
        ↓
low-discrepancy / DOE sampling
        ↓
feasibility risk screening
        ↓
exact evaluation
        ↓
active-learning or Bayesian proposal
```

### 22.4 No-good constraints

When a deterministic failure corresponds to a discrete combination, add a scoped no-good constraint.

```text
NOT(
  architecture = X_BRACE
  AND collar_level = LARGE
  AND window = LARGE
)
```

Do not generalize a local failure across all parts or all contexts without review.

### 22.5 Yield and coverage

Always report both:

```text
Yield: how many attempted candidates complete successfully
Coverage: how much of the approved design family is represented by accepted records
```

High yield with low coverage is not campaign success.

---

## 23. Campaign execution and HPC architecture

### 23.1 Required execution model

```text
Campaign
        ↓
Job queue
        ↓
Resource allocator
  ├── CPU
  ├── memory
  ├── storage
  ├── GPU where applicable
  ├── solver license/resource policy
  └── priority/concurrency limits
        ↓
Isolated worker sandbox
        ↓
Geometry → mesh → deck → solver → qualification
        ↓
Artifact store + record store
```

### 23.2 Required capabilities

- Idempotent jobs.
- Job cancellation.
- Timeouts.
- Bounded retries.
- Retry policy by typed failure code.
- Concurrency control.
- Resource requests and admission control.
- Artifact retention/cleanup policy.
- Checkpoint/restart where solver supports it.
- Deterministic container/environment manifests.
- Queue and worker health reporting.

### 23.3 Campaign health UI

```text
Campaign #001

Attempted: 40
Accepted: 31
Quarantined: 5
Rejected: 4

Geometry yield: 90%
Mesh yield: 94%
Solver yield: 96%
Coverage: 68%

Most common failure:
THIN_REGION_NOT_RESOLVED

Underrepresented architecture:
INTER_BORE_X_BRACE
```

---

## 24. Agent architecture

### 24.1 Stage-1 agent role

Agents are not required to edit CAD through natural language. They are campaign controllers operating over a typed finite action space.

```text
Approved contract
+ known entities
+ approved operators
+ parameter domains
+ constraints
+ campaign objective
+ current coverage
+ failure memory
= agent context
```

### 24.2 Agent may decide

- Which architecture classes need coverage.
- Which CP-SAT-feasible configurations to include.
- Which continuous parameter samples to evaluate.
- Which deterministic retry policy to use.
- Which variants to quarantine.
- Which successful records meet dataset criteria.
- Which unsimulated candidates are most valuable next.
- When to stop a campaign or request human review.

### 24.3 Agent may not decide autonomously

- It may not modify solver matrices.
- It may not create arbitrary mesh nodes.
- It may not silently redefine loads/BCs/contacts.
- It may not invent engineering identities.
- It may not override a blocked qualification result.
- It may not alter the approved Design Contract.

### 24.4 Agent tool protocol

Every tool returns structured state, evidence and permitted next actions.

```python
class StageResult(BaseModel):
    status: Literal["PASSED", "FAILED", "QUARANTINED", "BLOCKED"]
    stage: str
    metrics: dict[str, float]
    artifacts: list[ArtifactReference]
    failure: FailureRecord | None
    retry_options: list[RetryPolicy]
    evidence: list[Evidence]
```

### 24.5 Context envelope

UI state must be sent to the agent as typed context, never inferred from screenshots or chat text.

```python
class ContextEnvelope(BaseModel):
    project_id: UUID
    baseline_id: UUID
    contract_id: UUID
    contract_version: int
    active_tab: str
    selected_entity_ids: list[str]
    highlighted_entity_ids: list[str]
    selected_variant_ids: list[UUID]
    selected_record_ids: list[UUID]
    user_action: str
    permissions: list[str]
```

### 24.6 Auditability

Every agent decision must show:

```text
Decision
Reason
Inputs used
Contract version
Evidence
Tool calls
Outcome
```

---

## 25. UI architecture

### 25.1 Product navigation

Use a lifecycle-oriented UI:

```text
Input | Extract | Design Contract | Generate | Campaign | Dataset | Surrogate
```

Avoid making “CAD” the product’s top-level identity. The product is engineering simulation-data generation.

### 25.2 Input

Purpose: establish customer truth.

Features:

- Upload/select CAD, drawing, mesh, deck and baseline result.
- Per-file validation and extraction status.
- Source metadata and hashes.
- Explicit display of missing inputs.
- No invented drawings/results/features.

### 25.3 Extract

Purpose: show what the deterministic pipeline actually found.

Features:

- CAD viewport.
- Extracted entities list grouped by confidence.
- Face/feature selection and highlight.
- Candidate bearings, bores, bolt patterns, planes, walls, rib candidates and feature candidates.
- Source provenance.
- Human confirmation/rejection/rename actions.
- Unresolved-question cards.

### 25.4 Design Contract

Purpose: turn confirmed engineering meaning into binding campaign rules.

Features:

- Frozen interface cards.
- Moved-interface policy cards.
- Mutable-zone selection.
- Keep-out selection.
- Operator-permission cards.
- Parameter range cards.
- Manufacturing rule cards.
- Physics-transfer policy cards.
- Approval timeline and contract diff.

### 25.5 Generate

Purpose: define the campaign portfolio before compute is spent.

Features:

- Architecture class selection.
- CP-SAT feasibility summary.
- Parameter domain overview.
- Candidate recipe table.
- Diversity/coverage view.
- Preview variants and their recipes.
- Explicit campaign launch action.

### 25.6 Campaign

Purpose: inspect autonomous execution.

Features:

- Per-variant pipeline state.
- Geometry, mesh, physics, solver and engineering qualification status.
- Failure reason cards.
- Artifact viewer.
- Retry/quarantine/review controls subject to permissions.
- Yield plus coverage metrics.
- Agent decision log.

### 25.7 Dataset

Purpose: expose the actual deliverable.

Features:

- Accepted/quarantined/rejected records.
- Search/filter by architecture, parameter, status and result metric.
- Variant genealogy graph.
- Download/export controls.
- Coverage and distribution plots.
- Per-record provenance and replay manifest.

### 25.8 Surrogate

Purpose: later model training and controlled use.

Features:

- Dataset version selection.
- Train/validation/test family split definition.
- Training progress.
- Error/uncertainty/OOD dashboards.
- Model card.
- Active-learning recommendations.
- Solver-confirmation requirements.

---

## 26. UI selection synchronization

### 26.1 Requirement

Clicking an entity in CAD, mesh, setup, solver deck or result view must highlight its linked representations across the application.

```text
CAD face
  ↔ geometric entity
  ↔ interface identity
  ↔ mesh surface group
  ↔ load/BC/contact object
  ↔ result region
  ↔ variant lineage
```

### 26.2 Selection bus

Implement an application-wide typed selection bus.

```typescript
type SelectionEvent = {
  entityIds: string[];
  source: "cad" | "mesh" | "setup" | "solve" | "dataset";
  interaction: "select" | "hover" | "pin" | "clear";
};
```

### 26.3 Resolution service

The API should provide graph traversal methods:

```text
GET /entities/{id}/relations
GET /entities/{id}/representations
GET /entities/{id}/lineage
GET /entities/{id}/physics-links
GET /entities/{id}/mesh-links
```

### 26.4 Provenance badges

Every displayed object should show one of:

```text
Imported
Derived
Confirmed
Generated
Transferred
Predicted
Unavailable
```

---

## 27. API architecture

### 27.1 Principles

- FastAPI + Pydantic v2.
- REST for durable resources and commands.
- Server-sent events or WebSockets for job status/progress.
- OpenAPI-generated TypeScript client/types.
- Immutable artifacts and versioned domain objects.
- Idempotency keys for launch/retry operations.
- Every mutation emits an audit event.

### 27.2 Resource groups

```text
/projects
/assets
/baselines
/extractions
/entities
/contracts
/operators
/variants
/campaigns
/jobs
/qualification
/records
/surrogates
/agent-decisions
```

### 27.3 Essential endpoint examples

```text
POST /projects
POST /projects/{id}/assets
POST /baselines/{id}/extract
GET  /baselines/{id}/engineering-model
GET  /entities/{id}
PATCH /entities/{id}/semantic-label
POST /contracts
PATCH /contracts/{id}
POST /contracts/{id}/approve
POST /campaigns/plan
POST /campaigns
GET  /campaigns/{id}/events
GET  /variants/{id}
POST /variants/{id}/retry
GET  /variants/{id}/qualification
GET  /records
POST /surrogates/train
GET  /agent-decisions/{id}
```

### 27.4 Command pattern

Do not let UI directly mutate geometry. UI submits typed commands.

```python
class LaunchCampaignCommand(BaseModel):
    contract_id: UUID
    contract_version: int
    requested_count: int
    architecture_quotas: dict[str, int]
    sampling_policy: SamplingPolicy
    idempotency_key: str
```

### 27.5 UI/API compatibility

- Generate TypeScript from the OpenAPI schema during CI.
- Fail CI if generated client differs from committed client.
- Version schema migrations.
- Reject commands whose contract version is stale.
- Use explicit units in every dimensional schema.

---

## 28. Repository implementation plan

The following structure extends the existing repository areas described in the project documentation: `src/fastcad/geometry.py`, `regions.py`, `meshing.py`, `patching.py`, `skin.py`, `deck.py`, `api.py`, the React UI under `ui/`, tests and GRC assets.

### 28.1 New backend layout

```text
src/fastcad/
  api/
    app.py
    routers/
    dependencies.py
    events.py

  schemas/
    primitives.py
    artifacts.py
    geometry.py
    interfaces.py
    extraction.py
    physics.py
    contract.py
    operators.py
    qualification.py
    campaigns.py
    jobs.py
    records.py
    surrogate.py
    agent.py

  ingest/
    step.py
    mesh.py
    deck.py
    results.py
    manifest.py

  extract/
    surfaces.py
    cylinders.py
    holes.py
    bolt_patterns.py
    planes.py
    thickness.py
    ribs.py
    bosses.py
    fillets.py
    feature_graph.py
    physics.py
    coverage.py

  identity/
    signatures.py
    matching.py
    lineage.py
    frames.py

  interfaces/
    islands.py
    protection.py
    coupling.py
    motion.py
    transition.py

  contract/
    service.py
    compiler.py
    validation.py
    revisioning.py

  ops/
    base.py
    collar.py
    rib.py
    bridge.py
    brace.py
    pad.py
    window.py
    wall_zone.py
    tie_rail.py
    registry.py

  geometry/
    kernel.py
    booleans.py
    healing.py
    local_ops.py
    checks.py

  mesh/
    gmsh.py
    sizing.py
    groups.py
    quality.py
    recovery.py
    island_mesh.py
    stitching.py

  physics/
    canonical.py
    mapping.py
    applicability.py
    deck_builder.py
    audit.py

  fe/
    code_aster.py
    execution.py
    qualification.py
    postprocess.py

  qualify/
    identity.py
    geometry.py
    manufacturing.py
    mesh.py
    physics.py
    solver.py
    engineering.py
    reproduction.py
    oracle.py

  campaign/
    cpsat.py
    doe.py
    portfolio.py
    coverage.py
    failure_memory.py
    planner.py

  jobs/
    queue.py
    worker.py
    resources.py
    sandbox.py
    artifacts.py

  records/
    writer.py
    parquet.py
    zarr.py
    lineage.py
    export.py

  surrogate/
    datasets.py
    splits.py
    baselines.py
    feasibility.py
    uncertainty.py
    active_learning.py
    model_cards.py

  agent/
    state.py
    tools.py
    planner.py
    recovery.py
    data_agent.py
    audit.py
```

### 28.2 Existing modules to evolve

| Existing area | Role now | Required evolution |
|---|---|---|
| `geometry.py` | STEP read, topology utilities | Refactor into kernel/ingest helpers; expose immutable artifacts and robust signatures |
| `regions.py` | cylinders/bands/regions | Become deterministic candidate extraction with confidence/provenance |
| `meshing.py` | tetrahedralization | Route trusted B-rep variants through Gmsh CAD-conforming meshing; preserve groups |
| `patching.py`, `skin.py` | surface/local operations | Keep as low-level helpers behind formal operator contracts |
| `deck.py` | deck parsing/generation | Split canonical extraction, mapping/audit and variant deck builder |
| `api.py` | initial server | Migrate to versioned FastAPI app/routers with typed resources/events |
| `tests/` | initial regression tests | Add contract, identity, operator, mesh, physics and replay test suites |
| `ui/` | initial UI skeleton | Reorganize around product lifecycle and shared generated API schemas |

---

## 29. UI source structure

```text
ui/src/
  api/
    generated/
    client.ts
    events.ts

  domain/
    selection.ts
    contract.ts
    entities.ts
    variants.ts

  state/
    projectStore.ts
    selectionStore.ts
    contractStore.ts
    campaignStore.ts

  components/
    CadViewport/
    MeshViewport/
    ResultViewport/
    EntityCard/
    ProvenanceBadge/
    QualificationBadge/
    ContractEditor/
    OperatorCard/
    FailureCard/
    CampaignHealth/
    AgentDecisionCard/

  pages/
    InputPage.tsx
    ExtractPage.tsx
    ContractPage.tsx
    GeneratePage.tsx
    CampaignPage.tsx
    DatasetPage.tsx
    SurrogatePage.tsx

  render/
    geometryRenderer.ts
    meshRenderer.ts
    resultRenderer.ts
    selectionOverlay.ts
```

### 29.1 UI state principles

- Server state: query/cache system.
- Interaction state: selection store.
- Contract editing: explicit local draft, diff, validation and submit.
- Long-running jobs: event stream plus durable status query.
- All UI objects resolve to stable backend IDs.

---

## 30. Dataset architecture

### 30.1 Accepted Simulation Record

```python
class AcceptedSimulationRecord(BaseModel):
    record_id: UUID
    baseline_id: UUID
    contract_id: UUID
    contract_version: int
    variant_id: UUID

    variant_recipe: VariantRecipe
    geometry_artifact: ArtifactReference
    geometry_qualification: QualificationReport
    mesh_artifact: ArtifactReference
    mesh_qualification: QualificationReport
    physics_mapping_audit: PhysicsTransferAudit
    solver_manifest: SolverManifest
    solver_qualification: QualificationReport
    engineering_qualification: QualificationReport

    scalar_outputs: dict[str, Quantity]
    field_outputs: list[FieldArtifact]
    bearing_motion: list[BearingMotion]
    gear_misalignment: list[GearMisalignment]

    lineage: LineageGraphReference
    replay_manifest: ReplayManifest
    dataset_status: Literal["ACCEPTED"]
```

### 30.2 Dataset states

```text
ACCEPTED
QUARANTINED
REJECTED
```

Only accepted records train a trusted surrogate by default.

### 30.3 Storage

- Geometry and mesh artifacts: content-addressed artifact store.
- Scalar tables and manifests: Parquet.
- Large fields: Zarr/HDF5/VTK as appropriate.
- Lineage and graph queries: relational store initially; graph projection later if useful.
- Dataset versions: immutable manifests with DVC or equivalent artifact/version workflow.

---

## 31. Surrogate roadmap

### 31.1 Do not begin with a full-field GNN

Begin with scalar outputs and simple models:

- Mean baseline.
- Linear/polynomial baseline.
- Random forest/gradient boosting.
- Gaussian process where practical.
- Small MLP.

Only add geometry-aware GNN/neural-operator models if they demonstrate meaningful benefit on the required held-out tests.

### 31.2 Initial target outputs

- Mass/volume.
- Maximum displacement.
- Selected stress metrics.
- Bearing-seat translations and rotations.
- Relative shaft/bore motion descriptors.
- Optional condensed compliance descriptors.
- Geometry/mesh/solver success probability.

### 31.3 Dataset splits

Never rely only on random variant splits.

Use:

```text
Random holdout
Parameter-boundary holdout
Unseen parameter-region holdout
Unseen operator-combination holdout
Unseen architecture-class holdout
Genealogy-family holdout
Hard test: unseen architecture + unseen parameter region
```

### 31.4 Trust layer

Every prediction should include:

- Prediction.
- Uncertainty/confidence estimate.
- Out-of-distribution indicator.
- Nearest accepted records.
- Contract applicability status.
- Required action: use for ranking, simulate, or block.

### 31.5 Solver fallback

```text
High uncertainty → run FEA
OOD architecture → run FEA
Near constraint boundary → run FEA
Pareto-optimal candidate → confirm with FEA
Unseen topology → run FEA and add record
```

---

## 32. Future role of learned CAD and graph ML

### 32.1 HNC-CAD-like generative models

Do not use learned latent CAD generation as the Stage-1 geometry authority.

Later role:

```text
Accepted housing variants
        ↓
Learned feature/contract representation
        ↓
Proposal of a structured variant recipe
        ↓
Design Contract validation
        ↓
Deterministic B-rep operators
        ↓
Qualification Plane
        ↓
FEA
```

The learned model proposes. Deterministic tools and qualification decide.

### 32.2 B-rep graph recognition models

Potential later uses:

- Candidate rib/boss/fillet detection.
- Annotation prioritization.
- Feature similarity search.
- Failure-risk features.
- Geometry embedding for campaign diversity.

Do not use pretrained recognition models as the sole authority for interface identity, contract compliance or physics mapping on production cast housings.

### 32.3 Feasibility surrogate

After sufficient failure history, train a model predicting:

```text
P(geometry success)
P(mesh success)
P(physics-mapping success)
P(solver success)
```

Use it to prioritize candidates, not silently reject regions without coverage reporting.

---

## 33. Deterministic replay

### 33.1 Requirement

Every variant must be reconstructible.

```text
Baseline hash
CAD hash
Contract version
Operator versions
Operator parameters
Kernel version
Mesh policy and settings
Physics mapping version
Solver version/settings
Random seed
Container/environment image
Hardware/runtime metadata
```

### 33.2 Replay manifest

```python
class ReplayManifest(BaseModel):
    baseline_hash: str
    contract_hash: str
    recipe_hash: str
    operator_versions: dict[str, str]
    kernel_version: str
    mesher_version: str
    mesh_settings_hash: str
    solver_version: str
    solver_settings_hash: str
    random_seed: int | None
    container_digest: str
    artifact_hashes: list[str]
```

### 33.3 Replay test

```text
Variant #1847
        ↓
Replay from manifest
        ↓
Same geometry within declared tolerance
Same mesh policy/quality class
Same physics mapping
Same result within declared numerical tolerance
```

---

## 34. Testing strategy

### 34.1 Test levels

| Level | Purpose |
|---|---|
| Unit | Individual signatures, rules, operator geometry helpers |
| Contract | API schema and UI client compatibility |
| Property | Random valid/invalid parameters against operator invariants |
| Golden artifact | Baseline GRC geometry, extraction and solver-output regression |
| Integration | Full geometry → mesh → deck → solver chain |
| Qualification | Ensure failures classify correctly and cannot be accepted |
| Replay | Rebuild selected variants from manifests |
| Generality | Run the generic pipeline on a second part with a new contract but no core code branching |

### 34.2 Required gates

1. Baseline source import and manifest are deterministic.
2. Baseline reproduction passes calibrated thresholds.
3. Frozen bearing-seat signatures remain unchanged for frozen-interface variants.
4. Every operator passes its declared pre/postcondition tests.
5. Every accepted geometry produces a quality-qualified mesh.
6. Physics audit either transfers/rebuilds with evidence or blocks.
7. Every accepted solver result passes numerical checks.
8. Every accepted record has complete lineage and replay manifest.
9. UI selection links CAD, mesh, setup and result representations correctly.
10. Agent cannot exceed its typed action permissions.

### 34.3 Campaign-level targets

Targets must be reported alongside coverage:

```text
Geometry yield
Mesh yield
Physics-transfer yield
Solver yield
Engineering qualification yield
Design-envelope coverage
Architecture-class coverage
Parameter-bin coverage
Failure distribution
Mean retries per accepted record
Replay pass rate
```

Do not let a planner improve yield by silently avoiding difficult but approved regions.

---

## 35. Development milestones

### M0 — Baseline truth and reproducibility

**Goal:** one trustworthy imported GRC baseline.

Deliver:

- Immutable `BaselinePackage` manifest.
- Canonical Engineering Model.
- Deterministic bearing/bore/bolt/plane extraction.
- Initial feature graph.
- UI extraction review.
- Confirmed interface map.
- Baseline reproduction certificate.
- Stable bearing-motion extraction.
- Typed schemas and generated UI client.

Exit criteria:

- Reference and reconstructed baseline comparison passes reviewed thresholds.
- Critical interfaces are typed, confirmed and traceable.
- UI consistently cross-highlights source entities across CAD/mesh/setup/result.

### M1 — Feasibility rail

**Goal:** prove reliable exact geometry operations.

Deliver:

- Interface identity module.
- Protected island and transition model.
- Qualification Plane skeleton.
- Operator base contract.
- Geometry oracle.
- Manufacturing rule pack v1.
- `add_external_collar` and `add_radial_rib_group`.
- CAD-conforming Gmsh path.

Exit criteria:

- Parameter sweeps of first operators show stable protected interfaces.
- Failures are typed and replayable.
- No accepted variant violates frozen-interface checks.

### M2 — Structural vocabulary

**Goal:** introduce rich but governed GRC architecture classes.

Deliver:

- Bore-to-wall rib.
- Bore-to-mount path.
- Inter-bore bridge.
- X/K brace.
- Reinforcement pad.
- Window in generated web.
- Tie rail.
- CP-SAT architecture feasibility.

Exit criteria:

- At least four architecture classes are represented.
- Dry-run campaign generates 20 qualified geometry/mesh candidates.

### M3 — Physics and campaign execution

**Goal:** turn variants into trustworthy solved records.

Deliver:

- Physics Mapping Layer.
- Variant deck builder.
- Solver job execution architecture.
- Solver/numerical qualification.
- Accepted-record writer.
- Campaign health UI.

Exit criteria:

- End-to-end campaign produces the first 40 accepted or explicitly quarantined/rejected records.
- No manual deck/file edit is needed during execution.

### M4 — Autonomous coverage planning

**Goal:** make campaigns intelligent without natural-language CAD editing.

Deliver:

- CP-SAT planner.
- Portfolio diversity planner.
- Bounded recovery state machine.
- Failure memory.
- Coverage analysis.
- Agent decision audit.

Exit criteria:

- System can plan and execute a campaign under an approved contract with only typed user configuration.
- Every agent action is explainable and bound to a contract version.

### M5 — Dataset and surrogate

**Goal:** create the first useful predictive loop.

Deliver:

- Dataset versioning/export.
- Genealogy-aware split engine.
- Scalar surrogate baselines.
- Uncertainty/OOD layer.
- Feasibility predictor prototype.
- Active-learning candidate selection.

Exit criteria:

- 100–200 accepted records with documented coverage.
- Surrogate evaluated on unseen parameter regions and held-out architecture/genealogy families.
- Solver fallback policy operational.

---

## 36. What success looks like

### 36.1 Stage-1 demo

A user can:

1. Select/upload the GRC baseline package.
2. Inspect what fastCAD extracted and what remains uncertain.
3. Confirm bearing seats, mounting interfaces, editable zones and manufacturing rules.
4. Approve a Design Contract.
5. Select several architecture classes.
6. Launch a campaign of 40 variants.
7. Watch the system create, check, mesh, transfer physics, solve and qualify candidates.
8. Inspect failures with exact causes and evidence.
9. Explore 20–40 accepted geometry–physics records with complete lineage.
10. See coverage, bearing motion, mass/stress/displacement and gear-misalignment-relevant outputs.

### 36.2 Stronger proof

The same generic pipeline runs a second housing/bracket after a new Design Contract and semantic confirmation, without changing GRC-specific core logic.

Part-agnostic does not mean zero configuration. It means:

```text
Generic engine
+ part-specific baseline
+ part-specific Design Contract
+ part-specific semantic confirmation
+ no new core Python branches
```

---

## 37. Principal risks and mitigation

| Risk | Mitigation |
|---|---|
| Foreign B-rep Boolean/healing fragility | Local operators, checkpoints, oracle, bounded alternatives, reject/record failures |
| Existing rib extraction is incomplete | Candidate detection + human confirmation; do not require perfect recognition before adding new features |
| Implicit meshing smooths critical interfaces | Exact B-rep/CAD-conforming mesh for trusted route; fields only for screening |
| Physics mapping silently becomes wrong | Dedicated mapping layer, transfer/equivalence distinction, block ambiguity |
| High yield achieved by avoiding hard design space | Report coverage with yield; preserve all candidate/failure records |
| Surrogate leakage through sibling variants | Genealogy/architecture/parameter-region splits |
| Agent hides unsafe decisions | Typed tools, bounded policies, audit log, contract binding |
| HPC runs become unmanageable | Queue/workers/resource model, idempotency, artifact lifecycle, replay manifests |
| Attempt to compete with full CAD platforms | Keep scope at governed design-family automation and simulation data |

---

## 38. Final operating principles

1. **Customer input is the source of truth.**
2. **Do not invent engineering semantics.**
3. **Every visible object has provenance.**
4. **Every variant is a recipe, not just a STEP file.**
5. **Every operation has a formal contract.**
6. **Every critical entity has stable identity and lineage.**
7. **Every physics transfer is audited.**
8. **Every stage is qualified, not merely executed.**
9. **Every accepted record is reproducible.**
10. **Agents plan and orchestrate; deterministic tools generate, mesh, solve and verify.**
11. **Fields are useful for reasoning; exact B-rep is the trusted geometry path for interface-sensitive FEA.**
12. **High yield is meaningless without design-space coverage.**
13. **Part-agnostic means contract-configurable, not zero-configuration.**
14. **Learned geometry models become proposal engines only after the deterministic factory produces trustworthy data.**

---

## 39. Final product statement

> fastCAD is an autonomous, constraint-governed engineering simulation-data factory. It converts a trusted CAD/CAE baseline into a controlled design family, generates diverse and feasible exact geometry variants, preserves and audits the associated physics context, qualifies every mesh and solution, and produces replayable engineering records for surrogate modeling and design exploration.

The near-term task is not to build the most impressive CAD AI system. It is to build the most trustworthy path from:

```text
one trusted gearbox housing simulation
        ↓
to 100–200 diverse, feasible and qualified variants
        ↓
to a high-value simulation dataset
```

Once that factory exists, learned proposal models, feasibility predictors, surrogates and active-learning agents become accelerators built on evidence rather than substitutes for engineering truth.
