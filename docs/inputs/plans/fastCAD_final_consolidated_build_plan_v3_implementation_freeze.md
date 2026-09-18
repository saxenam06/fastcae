# fastCAD — Final Consolidated Stage-1 Build Specification, v3

## Implementation-Freeze Edition: Governed Design Synthesis, Deterministic Engineering Truth, and Cost-Aware Campaign Learning

**Status:** Architecture frozen for implementation

**Primary demonstrator:** NREL Gearbox Reliability Collaborative rear housing, drawing 254492

**Stage-1 goal:** Convert one trusted CAD/CAE baseline into a governed family of exact structural variants, produce 100–200 engineering-qualified and replayable simulation records, and establish the data and campaign-control foundation for solver-backed surrogate-guided design.

**Early proof:** Execute a 40-variant campaign without manual CAD or solver-deck editing after launch; show qualification evidence, failures, coverage, budget, and a deterministic evidence-based next-batch recommendation.

---

## 1. Final product definition

fastCAD is a **constraint-governed, cost-aware, agentic engineering experiment system**.

It does not attempt to make an LLM into a CAD system. It uses structured intelligence to decide which structural architectures and experiments are worth trying, while deterministic geometry, meshing, physics, solver, qualification, and replay systems determine what is actually true.

> **Agents decide what is worth trying; deterministic engineering systems decide what is actually true.**

The final operational chain is:

```text
Trusted CAD + mesh + deck + baseline result
                    ↓
Canonical Engineering Model
                    ↓
Engineer-confirmed Design Contract
                    ↓
Engineering Graph + Knowledge Bases + CampaignMemory + DecisionBudget
                    ↓
Engineering Context / Design Synthesis / Campaign Science
                    ↓
Intelligence Router
                    ↓
Architecture Grammar + Pattern KB + Proposal Generators
                    ↓
Structured VariantRecipe
                    ↓
Deterministic Trust Layer
Exact B-rep → CAD-conforming mesh → Physics mapping → FEA → Qualification → Replay
                    ↓
Accepted / Quarantined / Rejected Experiment Records
                    ↓
Memory, coverage, budget, feasibility, and surrogate update
                    ↺
Next campaign batch
```

---

## 2. Scope and operating principles

### 2.1 Stage-1 scope

Build a system that can:

- Ingest a trusted CAD/mesh/deck/result baseline.
- Extract deterministic geometric and physics facts with transparent uncertainty.
- Let an engineer confirm semantic entities, interfaces, mutable regions, and rules.
- Version an approved Design Contract.
- Generate structurally diverse, grammar-constrained architecture proposals.
- Compile those proposals into typed executable `VariantRecipe` programs.
- Construct exact local B-rep variants using deterministic operators.
- Mesh, map physics, solve, qualify, and replay each candidate.
- Store accepted records and structured failures.
- Run budget-aware, coverage-aware campaign batches.
- Learn from results through feasibility models and scalar response surrogates after enough accepted data exists.

### 2.2 Explicit exclusions

Do not build these as Stage-1 dependencies:

- General-purpose CAD authoring.
- Free-form chat-to-CAD.
- Direct execution of LLM-generated CAD kernel scripts.
- Learned STEP/B-rep generation as trusted final geometry.
- Automated invention of engineering semantics.
- Field/voxel/SDF-only final geometry for bearing-motion-sensitive analysis.
- Autonomous design release or safety certification.
- Deep field surrogates before data integrity and scalar baselines.
- Moved interface regimes before frozen-interface workflows are proven.

### 2.3 Principles

1. Topology/architecture diversity is more valuable than repetitive dimension sweeps.
2. Imported facts, derived facts, inferred candidates, confirmations, and generated entities must remain distinguishable.
3. Critical interfaces are semantic objects, never merely face indices.
4. Frozen interfaces define stable geometry and numerical measurement conditions.
5. Exact B-rep is the trusted geometry route; field methods are advisory/screening tools.
6. Agents reason, plan, prioritize, diagnose, explain, and learn; deterministic tools construct, map, solve, qualify, and certify.
7. Only complete qualified records train engineering response surrogates.
8. Failures are structured campaign evidence, not discarded errors.
9. Coverage and yield must always be evaluated together.
10. Every record is replayable from immutable artifacts and versions.
11. The architecture grammar defines legal structural concepts; the operator library defines deterministic construction; recipes are compiled executable programs.
12. Budget enforcement is a typed system capability, not a verbal guideline.

---

## 3. Authority model

### 3.1 Three truth layers

```text
Canonical Engineering Model
        ↓
Facts imported or deterministically derived from the trusted baseline

Design Contract
        ↓
Engineer-approved allowed design freedom for one campaign

Qualification Model
        ↓
Evidence requirements that determine whether a candidate is trustworthy
```

### 3.2 Canonical Engineering Model

The immutable normalized model contains:

- CAD source artifacts, hashes, units, coordinate systems, and import reports.
- B-rep entities, analytic surfaces, adjacency, feature candidates, and confidence.
- Mesh entities/groups and geometry mapping where available.
- Solver deck labels/objects, materials, sections, loads, constraints, contacts, steps, and outputs.
- Baseline result artifacts, probes, fields, scalar values, and comparison metadata.
- Provenance, extraction coverage, and unresolved ambiguity reports.

### 3.3 Design Contract

The engineer-approved campaign policy contains:

- Frozen and later moved-interface policies.
- Protected interface islands and transition boundaries.
- Mutable zones and keep-out volumes.
- Allowed architecture families, patterns, grammar productions, and operator versions.
- Valid semantic anchors, compositions, parameter domains, and discretization.
- Geometric/manufacturing/physics-transfer rules.
- Output objectives and response constraints.
- Coverage Contract.
- DecisionBudget.
- Approval and audit metadata.

### 3.4 Qualification Model

The deterministic acceptance framework contains:

- Contract compliance requirements.
- Interface identity/fidelity requirements.
- Geometry oracle rules.
- Manufacturing rules.
- Mesh/coupling quality requirements.
- Physics mapping conditions.
- Solver/numerical requirements.
- Output extraction and plausibility requirements.
- Replay requirements.
- Accept/quarantine/reject conditions.

---

## 4. GRC frozen-interface campaign

### 4.1 Frozen core

Preserve initially:

- Bearing-seat analytic cylinders, radii, axes, axial boundaries, and local reference frames.
- Gear/shaft packaging clearance volumes.
- Essential mounting, bolt, datum, and sealing interfaces.
- Baseline coordinate systems and output reference frames.
- Any physics interface that cannot be transferred/rebuilt under an approved typed policy.

Do not initially vary nominal bore centers, axes, diameters, gear center distance, primary mount locations, or sealing interfaces.

### 4.2 Mutable structural space

```text
Protected bearing/mount/seal/datum islands
+ packaging and physics keep-outs
+ approved editable structural zones
= Stage-1 governed design family
```

### 4.3 Structural mechanisms

| Mechanism | Engineering intent | Architecture examples |
|---|---|---|
| Local bearing support | Change radial/tangential support stiffness | collar, radial-rib group, tangential ribs, pad |
| Inter-bearing coupling | Alter relative translation/rotation | bridge, double web, X/K brace |
| Bore-to-wall path | Couple bearing support to shell | diagonal rib, triangular web, local trunk |
| Bore-to-mount path | Change bearing-to-mount load path | diagonal support, rail, shared trunk |
| Front-rear coupling | Control longitudinal/shaft-support compliance | tie rail, spine, boxed corridor |
| Split-line/flange support | Change joint flexibility | flange reinforcement, bolt-boss support |
| Shell redistribution | Change allowable shell stiffness/mass | belt, bulkhead, wall-zone adjustment, windowed web |
| Directional reinforcement | Deliberately alter directional coupling | asymmetric ribs, biased bridge, one-sided rail |

---

## 5. Coverage Contract for 100–200 records

### 5.1 Purpose

Coverage must be an executable, measurable campaign requirement—not a subjective report written after the campaign.

The Coverage Contract is part of the approved Design Contract. It defines minimum portfolio requirements for architecture, parameter, topology/genealogy, response, and boundary coverage. The planner uses it to choose candidates; the campaign dashboard uses it to prove completion.

### 5.2 Default 150-record coverage matrix

Use this as the default configuration for a 150-accepted-record GRC campaign. Scale targets proportionally for a final target of 100 or 200 while preserving minimum class diversity.

```yaml
coverage_contract:
  accepted_target: 150

  architecture:
    minimum_primary_architecture_classes: 8
    core_class_minimum_fraction: 0.12
    minimum_records_per_core_class: 12
    hybrid_minimum_fraction: 0.15
    minimum_hybrid_records: 23
    maximum_single_architecture_fraction: 0.22

  parameter:
    parameter_bin_policy: low_nominal_high
    minimum_accepted_per_active_bin: 4
    minimum_joint_coverage_for_key_pairs: 9
    key_parameter_pair_bins: low_low, low_nominal, low_high, nominal_low, nominal_nominal, nominal_high, high_low, high_nominal, high_high

  topology_and_genealogy:
    minimum_unique_topology_classes: 12
    maximum_near_duplicate_fraction: 0.15
    max_descendants_per_parent_recipe: 6
    minimum_novel_operator_compositions: 10

  boundary:
    minimum_near_feasible_boundary_fraction: 0.10
    boundary_definition: within_10_percent_of_any_active_parameter_or_rule_limit
    minimum_high_risk_exploration_fraction: 0.05

  response:
    response_metrics:
      - mass
      - max_displacement
      - max_stress_kpi
      - relative_bearing_translation
      - relative_bearing_tilt
      - center_distance_change
    minimum_response_quantile_coverage: [0.10, 0.25, 0.50, 0.75, 0.90]
    minimum_non_dominated_or_tradeoff_records: 15

  quality:
    minimum_replay_pass_rate: 0.98
    required_full_lineage_fraction: 1.00
    required_protected_interface_pass_fraction: 1.00
```

### 5.3 Interpretation of architecture quota

For a 150-record target:

- At least 8 primary architecture classes must appear.
- Every core architecture class must have at least 12 accepted records and at least 12% representation where feasible.
- At least 23 accepted records must be hybrids.
- No single architecture family may dominate more than 22% of accepted records unless an engineer explicitly modifies and approves the Coverage Contract.

A practical initial class set is:

```text
1. External collar
2. Radial/tangential local support
3. Bore-to-wall support path
4. Bore-to-mount path
5. Inter-bore bridge
6. X/K brace
7. Front-rear tie rail
8. Shell/flange/belt reinforcement
9. Hybrid compositions
```

The exact mapping from operator families to architecture classes must be explicit and versioned.

### 5.4 Parameter coverage

Each active continuous parameter is discretized into low, nominal, and high bins for coverage reporting. For key coupled parameters, include a 3×3 joint-bin coverage matrix.

Example key pairs:

```text
Rib thickness × rib height
Bridge depth × window fraction
Collar thickness × radial-rib count
Brace angle × brace thickness
Tie-rail section × attachment location
```

Boundary cases are not an accidental side effect. At least 10% of accepted records should be within 10% of one or more approved parameter/rule bounds, and at least 5% of candidate budget should be reserved for high-risk but coverage-critical exploration.

### 5.5 Topology and genealogy coverage

Define a topology class using a canonical structural descriptor, for example:

```text
architecture grammar production trace
+ operator composition sequence
+ anchor-role graph
+ connectivity/topology signature
+ symmetry class
```

Do not count trivial dimension changes as new topology. Limit near-duplicate descendants from any parent recipe and require a minimum number of new composition structures.

### 5.6 Response-space coverage

The campaign must not only cover input design space. It should deliberately populate response-space regions. Track quantile coverage for mass, stiffness/displacement, stress, relative bearing translation, relative tilt, and center-distance change.

The planner should seek records that occupy underrepresented response regions while preserving engineering relevance and feasibility.

### 5.7 Coverage status categories

Every required coverage cell is one of:

```text
UNTOUCHED
ATTEMPTED_BUT_UNQUALIFIED
PARTIALLY_COVERED
SATISFIED
BLOCKED_BY_CONTRACT_OR_TOOL_LIMITATION
```

Blocked cells must be visible and require explicit disposition, not silent removal from the reported denominator.

---

## 6. Design Synthesis Engine

### 6.1 The synthesis hierarchy

```text
Engineering objective
        ↓
Structural mechanism
        ↓
Architecture patterns
        ↓
Architecture grammar
        ↓
Proposal generation and composition
        ↓
Structured architecture proposal
        ↓
Recipe compilation
        ↓
Typed VariantRecipe
        ↓
Contract validation + CP-SAT feasibility
        ↓
Deterministic operator execution
```

### 6.2 Strict code-ownership separation

This distinction is mandatory in architecture and code review:

| Layer | Meaning | Must not do |
|---|---|---|
| Architecture Grammar | Defines what structural concepts and compositions are legal | Must not call OCCT or construct solid geometry |
| Architecture Pattern KB | Encodes engineering-mechanism templates, risks, and relevant outputs | Must not contain kernel construction logic |
| Proposal Generator | Suggests grammar-constrained architecture candidates | Must not create raw CAD, mesh, or deck artifacts |
| Recipe Compiler | Converts validated architecture proposals into typed executable operation programs | Must not decide final geometry validity |
| Operator Library | Performs deterministic physical construction and emits evidence | Must not decide campaign strategy or invent structural intent |
| VariantRecipe | Immutable compiled executable representation | Must not contain unconstrained code snippets |

### 6.3 Architecture Grammar

The architecture grammar is fastCAD’s bounded generative substrate. It defines legal combinations of mechanisms, semantic anchors, architecture patterns, operators, and parameter policies.

```text
Architecture
  ::= LocalSupport
   | InterBearingCoupling
   | BoreToMountPath
   | FrontRearCoupling
   | ShellReinforcement
   | DirectionalReinforcement
   | HybridArchitecture

LocalSupport
  ::= Collar(SeatAnchor, CollarParameters)
   | RadialRibGroup(SeatAnchor, WallAnchor, RibParameters)
   | LocalPad(SeatAnchor, PadParameters)

InterBearingCoupling
  ::= Bridge(SeatA, SeatB, BridgeParameters)
   | XBrace(BridgeA, BridgeB, BraceParameters)
   | DoubleWeb(SeatA, SeatB, WebParameters)

HybridArchitecture
  ::= Compose(ArchitectureA, ArchitectureB)
  subject_to ContractCompatibility
```

A grammar production includes:

- Mechanism(s).
- Required/optional semantic anchor roles.
- Allowed architecture pattern IDs.
- Operator composition structure.
- Parameter domain references.
- Symmetry/bias policy.
- Compatibility/exclusion rules.
- Manufacturing/protected-interface constraints.
- Expected topology descriptor.

### 6.4 Architecture Pattern Knowledge Base

Patterns capture engineering knowledge that connects structural mechanisms to legal topology choices.

```yaml
pattern_id: INTER_BEARING_X_BRACE
mechanism:
  - inter_bearing_coupling
objective_relevance:
  - relative_bearing_translation
  - relative_bearing_tilt
required_anchor_roles:
  - bearing_support_outer_region
  - bearing_support_outer_region
optional_anchor_roles:
  - mutable_web_zone
operator_sequence:
  - add_inter_bore_bridge
  - add_x_or_k_brace
  - add_window_in_generated_web
compatibility:
  requires:
    - INTER_BORE_WEB_ZONE
  excludes:
    - CONFLICTING_THROUGH_WINDOW
risks:
  - thin_intersection
  - meshing_complexity
  - excess_mass
expected_topology:
  - inter_bore_bridge_with_cross_brace
```

### 6.5 Proposal sources

All sources implement one typed proposal interface:

| Source | Role | Hard constraint |
|---|---|---|
| Rule-based grammar enumeration | Initial reliable architecture candidates | Grammar/contract bounded |
| Constraint-guided composition | Legal hybrid combinations | Must compile to typed recipe |
| Local learned proposal model | Suggest underexplored/high-value valid grammar programs | Output only grammar choices and recipe parameters |
| HNC-CAD/graph generative plug-in | Propose latent/graph structures decoded to architecture programs | Never produces trusted B-rep/STEP directly |
| Premium reasoner | Suggest mechanisms, pattern combinations, strategic hypotheses | Returns structured evidence-bound proposal only |
| Human engineer | Creates/approves new pattern or grammar version | Subject to normal contract/compiler/qualification flow |

### 6.6 HNC-CAD role

HNC-CAD-like, graph-generative, or learned recipe-generation models are proposal engines, not trusted geometry engines:

```text
Engineering graph + Contract + CampaignMemory
        ↓
Learned latent/graph architecture proposal
        ↓
Proposal normalizer
        ↓
Grammar validator
        ↓
Recipe compiler
        ↓
Typed VariantRecipe
        ↓
Deterministic B-rep realization
        ↓
Qualification Plane
```

The learned model may be available as an experimental proposal source earlier than M5, but the campaign must remain functional when it is disabled. Promote it only after measured benefit over grammar/DOE baselines.

### 6.7 Required tools

```text
identify_structural_mechanisms()
retrieve_architecture_patterns()
propose_architectures()
compose_architecture()
validate_architecture_grammar()
compile_to_recipe()
rank_design_proposals()
explain_design_proposal()
```

---

## 7. CampaignMemory and agentic operation

### 7.1 Supervisor state

```text
Campaign Supervisor State
=
Engineering Goal
+ approved Design Contract
+ Engineering Graph
+ CampaignMemory
+ DecisionBudget
```

### 7.2 CampaignMemory schema

```python
class CampaignMemory(BaseModel):
    campaign_id: UUID
    baseline_id: UUID
    contract_version: str
    revision: int

    active_hypotheses: list[dict]
    architecture_proposals: list[dict]
    attempted_variants: list[UUID]
    accepted_patterns: list[dict]
    failure_patterns: list[dict]
    unresolved_questions: list[dict]

    coverage_state: dict
    response_state: dict
    feasibility_state: dict
    surrogate_state: dict
    budget_state: dict

    next_recommended_experiments: list[dict]
    stop_conditions: list[dict]
    event_refs: list[str]
```

### 7.3 Operational loop

```text
Observe campaign outcomes
        ↓
Load Goal + Contract + Engineering Graph + CampaignMemory + DecisionBudget
        ↓
Identify highest-value unresolved question or coverage gap
        ↓
Route reasoning/execution decision
        ↓
Generate, compose, compile, and rank architecture proposals
        ↓
Select a bounded batch
        ↓
Run deterministic trust layer
        ↓
Qualify outcomes and update all state
        ↓
Plan next batch, stop, or escalate
```

### 7.4 Agent boundaries

| Agent role | Owns | Cannot do |
|---|---|---|
| Engineering context | Context synthesis, mechanism reasoning, graph retrieval | Certify interfaces or physics mapping |
| Design synthesis | Architecture hypotheses, grammar composition, recipes | Generate arbitrary kernel code |
| Campaign science | Coverage/value/budget-aware selection | Override hard contract gates |
| Execution | Job scheduling and state tracking | Manually alter mesh/deck |
| Recovery | Select bounded approved retry policy | Exceed retry policy or invent repairs |
| Data/qualification | Assemble evidence and apply deterministic status | Fabricate or override checks |

---

## 8. DecisionBudget as an enforceable contract object

### 8.1 Budget purpose

`DecisionBudget` is a first-class typed object attached to every campaign. It makes cost-aware behavior enforceable by the router, planner, scheduler, and UI.

### 8.2 Schema

```python
class BudgetLimit(BaseModel):
    limit: float | int
    consumed: float | int = 0
    reserved: float | int = 0
    remaining: float | int | None = None
    unit: str

class StageRetryBudget(BaseModel):
    stage: str
    max_retries_per_variant: int
    max_retries_campaign: int
    consumed_campaign_retries: int = 0

class DecisionBudget(BaseModel):
    campaign_id: UUID
    version: str

    max_premium_calls: int
    max_premium_calls_per_batch: int
    premium_calls_consumed: int = 0

    max_local_model_calls: int
    local_model_calls_consumed: int = 0

    max_geometry_attempts: int
    geometry_attempts_consumed: int = 0

    max_mesh_attempts: int
    mesh_attempts_consumed: int = 0

    max_solver_attempts: int
    solver_attempts_consumed: int = 0

    max_cpu_hours: float
    cpu_hours_consumed: float = 0.0

    max_gpu_hours: float
    gpu_hours_consumed: float = 0.0

    max_wallclock_hours: float
    wallclock_hours_consumed: float = 0.0

    max_storage_gb: float
    storage_gb_consumed: float = 0.0

    retry_budgets: list[StageRetryBudget]

    reserve_for_boundary_exploration_fraction: float = 0.10
    reserve_for_high_risk_coverage_fraction: float = 0.05
    reserve_for_replay_validation_fraction: float = 0.03

    status: Literal["ACTIVE", "WARNING", "EXHAUSTED", "PAUSED", "CLOSED"]
```

### 8.3 Enforcement rules

- No planner may schedule work that exceeds hard budget limits without explicit engineer approval and a new budget version.
- Reserved budget cannot be consumed by exploitation candidates unless a policy allows it.
- Each batch performs a preflight reservation for estimated geometry/mesh/solver/storage resources.
- On budget warning, the supervisor changes strategy or requests review.
- On budget exhaustion, active jobs finish safely; no new work starts.
- Every route/planning decision stores budget before/after state and estimated/actual cost.

### 8.4 Adaptive solver budget

Do not hardcode `max_solver_runs`. Derive it from target acceptance and observed yield:

\[
N_{\mathrm{solver\_attempts}} =
\left\lceil
\frac{N_{\mathrm{accepted\_target}}}
{Y_{\mathrm{expected\_postmesh}}}
\times F_{\mathrm{safety}}
\right\rceil
\]

Example:

```text
Accepted target: 150
Expected post-mesh acceptance yield: 0.82
Safety factor: 1.05
Required solver attempts: ceil(150 / 0.82 × 1.05) = 193
```

This is a planning estimate, not permission to exceed CPU/wall-clock budgets. The system must solve the complete budget constraint jointly.

---

## 9. Proposal evaluation and calibration

### 9.1 Proposal ranking

Every architecture proposal receives explicit scores:

```python
class ProposalScore(BaseModel):
    proposal_id: UUID
    mechanism_relevance: float
    grammar_novelty: float
    topology_novelty: float
    coverage_deficit_addressed: float
    predicted_geometry_success: float | None
    predicted_mesh_success: float | None
    predicted_physics_success: float | None
    predicted_solver_success: float | None
    predicted_information_gain: float | None
    expected_cost: dict
    contract_risk: float
    final_rank_score: float
    rationale: list[str]
```

### 9.2 Candidate value function

\[
V_{\mathrm{sim}}(x) =
\frac{
I(x)
\,R(x)
\,P_{\mathrm{complete}}(x)
\,D_{\mathrm{coverage}}(x)
}{
C_{\mathrm{CAD}}(x)+C_{\mathrm{mesh}}(x)+C_{\mathrm{FEA}}(x)
}
\]

Where:

- \(I(x)\): expected information gain.
- \(R(x)\): engineering relevance to objective/hypothesis.
- \(P_{\mathrm{complete}}(x)\): predicted probability that the candidate becomes accepted.
- \(D_{\mathrm{coverage}}(x)\): deficit addressed in the Coverage Contract.
- \(C\): expected execution cost.

Hard contract failures are excluded before scoring. The score ranks eligible candidates; it never overrides deterministic qualification.

### 9.3 Calibration loop

The Design Synthesis Engine must learn whether its predictions correspond to actual campaign results:

```text
Predicted proposal feasibility
        ↓
Actual geometry qualification
        ↓
Actual mesh qualification
        ↓
Actual physics mapping qualification
        ↓
Actual solver qualification
        ↓
Actual record acceptance
        ↓
Actual coverage gain
        ↓
Actual response/information gain
        ↓
Calibration update for proposal ranker and feasibility models
```

### 9.4 Required calibration metrics

Report by proposal source, architecture class, operator composition, and parameter region:

- Predicted vs actual geometry success probability.
- Predicted vs actual mesh success probability.
- Predicted vs actual physics/solver success probability.
- Calibration error, for example Brier score and reliability curves for probability predictions.
- Predicted vs actual cost/time.
- Predicted vs actual coverage gain.
- Predicted vs actual information/uncertainty reduction.
- Proposal novelty versus accepted topology novelty.
- Acceptance yield by proposal source.
- Qualified records per CPU hour by proposal source.
- Incremental value of learned/premium proposals compared with grammar/DOE-only baseline.

### 9.5 Promotion rules for learned proposal sources

A learned or premium proposal source is promoted only if it demonstrates, on comparable budgeted campaigns, one or more of:

- Higher accepted coverage gain per solver attempt.
- Higher information gain per CPU hour.
- Lower near-duplicate rate.
- Better qualified architecture diversity.
- Comparable or better acceptance yield with no reduction in hard-region coverage.
- Better response-space coverage.

If it does not outperform the deterministic grammar/portfolio baseline, keep it experimental or disable it.

---

## 10. Deterministic trust layer

### 10.1 Exact B-rep and operator library

```text
Imported STEP B-rep
        ↓
Resolve semantic anchors in local frames
        ↓
Construct local parametric solids
        ↓
Boolean fuse/cut with checkpoint
        ↓
Local healing
        ↓
Geometry oracle
        ↓
Protected-interface comparison
        ↓
Exact variant artifact
```

The initial library is:

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

### 10.2 Operator contract requirements

Every operator declares purpose, anchor roles, local-frame needs, parameter schema/units, preconditions, construction method, protected entities, expected topology event, postconditions, manufacturing gates, failure codes, bounded recovery options, emitted evidence, and version.

### 10.3 Geometry oracle

Check B-rep validity, expected body count, disconnection, volume change, protected interface preservation, keep-out intersection, self-intersection, zero-thickness/slivers, thickness/clearance, expected topology, and export/reimport validity where needed.

### 10.4 Meshing and protected islands

Use CAD-conforming Gmsh meshing with semantic physical groups. Protect bearing islands and verify stable geometry/coupling/member definitions. Apply a bounded repair ladder; lower-fidelity fallbacks are flagged and quarantined unless independently approved.

### 10.5 Physics Mapping Layer

Every baseline physics entity is explicitly direct-transferred, aggregate-transferred, rebuilt, blocked as ambiguous, or rejected as invalid. The mapping audit is mandatory before solve eligibility.

### 10.6 Solver and baseline reproduction

Before campaigns, produce a baseline reproduction certificate covering loads/reactions, displacements, energy, probes/fields, bearing motion, mesh sensitivity, output completeness, and units/coordinate systems.

### 10.7 Response extraction

Use weighted rigid fit for protected bearing interfaces, preserving translation, rotation, residual, radial expansion, and ovalization separately. Store mass, volume, stress/displacement KPIs, reactions, bearing motion, relative shaft behavior, center-distance change, and available gear-misalignment descriptors.

### 10.8 Replay

Every attempted record requires immutable baseline/contract/recipe/operator/kernel/mesher/physics/solver/runtime/artifact version evidence. Selected replay tests rebuild variants and compare qualified outputs within declared tolerance.

---

## 11. Intelligence router

### 11.1 Tiers

| Tier | Appropriate work | Not permitted |
|---|---|---|
| Tier 0 deterministic | Extraction, signatures, rules, CP-SAT, CAD, meshing, mapping, solver, qualification, replay | Probabilistic certification |
| Tier 1 local models | Similarity, candidate ranking, feasibility, failure retrieval, surrogate, uncertainty, coverage clustering | Interface/physics/final acceptance authority |
| Tier 2 premium reasoner | Mechanism synthesis, architecture hypotheses, unusual-failure reasoning after evidence retrieval, major batch strategy | Per-operation CAD/mesh/solver loops or gate overrides |
| Human review | Semantic confirmation, contract approval, high-consequence ambiguity | Routine deterministic execution |

### 11.2 Routing policy

```text
Can deterministic logic answer exactly?
  yes → Tier 0
  no → Is a validated local model applicable?
          yes → Tier 1
          no → Is this high-value, ambiguous, and budget-approved?
                  yes → Tier 2
                  no → deterministic heuristic, defer, or human review
```

Premium reasoning sees compact evidence packages, never raw uncontrolled CAD/mesh/solver archives as its sole context.

---

## 12. Data and UI

### 12.1 Data stack

- PostgreSQL: contracts, entities, lineage, CampaignMemory, budgets, states, audit events.
- Object storage: CAD, meshes, decks, logs, reports, fields, artifacts.
- Parquet: scalar/tabular record data and analytics.
- Zarr: retained large field arrays.
- DVC/equivalent: curated dataset and model snapshot versioning.

### 12.2 UI views

| View | Purpose |
|---|---|
| Input | Inspect imported artifacts, extraction status, unresolved questions, semantic confirmation |
| Design Contract | Configure/approve interfaces, zones, grammar permissions, rules, Coverage Contract, DecisionBudget |
| Generate | Inspect architecture proposals, grammar trace, recipes, novelty, risk, coverage contribution |
| Campaign | Track stages, yields, coverage cells, DecisionBudget, failures, retries, decisions, and next batch |
| Dataset | Browse accepted/quarantined/rejected records, lineage, response coverage, replay evidence |
| Surrogate | Show training dataset, holdouts, uncertainty/OOD, solver fallback, and active-learning proposals |

A selection bus links CAD face ↔ semantic interface ↔ mesh group ↔ physics entity ↔ result probe ↔ lineage event ↔ contract rule.

---

## 13. Technology stack

| Layer | Recommended starting point |
|---|---|
| Geometry | OpenCascade through build123d/CadQuery/pythonOCC/direct OCCT |
| Extraction | OCCT topology and analytic fitting; motif detection later |
| Grammar/planning | Python typed schemas, OR-Tools CP-SAT |
| Meshing | Gmsh, semantic physical groups |
| Mesh repair | Controlled MeshFix/libigl/PyMeshLab/fTetWild fallback path |
| Solver | Code_Aster initial route; cross-check/adapter strategy as needed |
| Post-processing | NumPy, SciPy, meshio, VTK/PyVista |
| Backend | Python, FastAPI, Pydantic v2 |
| Orchestration | Explicit deterministic state machine first; add LangGraph only where useful |
| Metadata | PostgreSQL |
| Artifacts | Object storage + Parquet + Zarr + DVC/equivalent |
| ML | scikit-learn/XGBoost first; PyTorch/PyG after validated need |
| UI | React, TypeScript, three.js, VTK.js |
| Runtime | Containers and captured environment digests |

Review all licenses, especially solver and mesh-repair tools, before commercial distribution. Keep adapters replaceable.

---

## 14. Implementation roadmap

### M0 — Baseline truth and reproducibility

Build baseline package manifests, ingestion, units/coordinates, deterministic analytic extraction, engineering graph, semantic confirmation, core schemas, solver adapter, bearing-motion extraction, and reproduction certificate.

**Exit:** Baseline reproduction passes reviewed thresholds; critical entities are confirmed and traceable.

### M1 — Feasibility rail

Build interface identity/protected islands, geometry oracle, manufacturing rules v1, operator contract base, collar/radial-rib operators, CAD-conforming meshing, quality checks, and replay/failure taxonomy.

**Exit:** At least 20 geometry-and-mesh-qualified dry-run variants; zero accepted frozen-interface violations.

### M2 — Structural vocabulary and synthesis substrate

Build additional structural operators, Architecture Pattern KB, typed Architecture Grammar, rule-based composition, recipe compiler, CP-SAT compatibility, coverage contribution scoring, and proposal-ranker baseline.

**Exit:** At least four qualified architecture classes; objective → mechanism → proposal → recipe is functional and auditable.

### M3 — Deterministic factory plus basic agentic loop

Build Physics Mapping Layer, deck builder, solver workers, numerical qualification, record writer, CampaignMemory event store, basic Campaign Supervisor, deterministic cost/coverage/diversity planner, bounded failure feedback, DecisionBudget enforcement, and campaign UI.

**Exit:** 40-variant campaign runs without manual CAD/deck edits. The supervisor updates memory and selects a next batch from observed coverage/failure/budget evidence.

### M4 — Full adaptive campaign intelligence

Build Intelligence Router, feasibility prototype, failure-memory retrieval, cost model, mechanism reasoner, premium batch-strategy context package, decision audit, and benchmark against DOE-only planning.

**Exit:** Campaign strategy adapts under contract, coverage, and budget constraints; major decisions are inspectable and bounded.

### M5 — Surrogate, active learning, learned proposals

Build dataset versioning/export, genealogy-aware split engine, scalar response surrogates, uncertainty/OOD, solver fallback, coverage-aware active learning, and learned/HNC-CAD/graph proposal plug-in behind the grammar-constrained proposal interface.

**Exit:** 100–200 accepted records meet Coverage Contract; learned proposal source is benchmarked against grammar/DOE baseline and promoted only on measured evidence.

### M6 — Generality and pilot hardening

Onboard a second housing/bracket with a new baseline and contract; harden adapters, deployment, roles, audit exports, and runbooks.

**Exit:** Second part runs without a GRC-specific core-code branch.

---

## 15. First 12-week implementation plan

### Weeks 1–2

- Freeze baseline CAD, mesh, deck, result, versions, and artifact hashes.
- Build STEP import, basic OCCT inspection, and canonical artifact manifest.
- Establish units and coordinate conventions.
- Parse enough deck structure to surface materials, loads, constraints, contacts, and requested outputs.
- Define baseline reproduction certificate inputs.
- Implement base schemas.

### Weeks 3–4

- Implement deterministic cylinder/plane/bolt pattern/coaxial-group detection.
- Build feature candidates, adjacency, signatures, and extraction coverage report.
- Implement semantic confirmation workflow.
- Define frozen-interface islands/local frames.
- Build first Design Contract editor.

### Weeks 5–6

- Implement solver wrapper and result capture.
- Implement reaction/displacement/energy/output-presence checks.
- Implement bearing-seat rigid-fit extraction.
- Run critical-interface mesh sensitivity assessment.
- Lock reviewed reproduction tolerances.

### Weeks 7–8

- Implement protected-interface comparison and geometry oracle.
- Implement external collar and radial-rib-group operators.
- Implement manufacturing v1.
- Generate first geometry variants with replay manifests.

### Weeks 9–10

- Implement Gmsh physical-group mapping and meshing.
- Implement mesh quality and controlled recovery ladder.
- Validate interface/coupling consistency across variants.
- Produce at least 20 qualified geometry/mesh dry-run candidates.

### Weeks 11–12

- Implement physics transfer audit and variant deck construction.
- Run 10–20 solved variants.
- Implement accepted/quarantined/rejected records.
- Implement CampaignMemory event storage and minimal DecisionBudget.
- Produce deterministic coverage-based next-batch recommendations.

---

## 16. Test gates and KPIs

### 16.1 Tests

- Unit: signatures, rules, frames, parameter validation, output extraction.
- Property: randomized invalid/valid operator and constraint cases.
- Golden: baseline extraction, deck, result-probe regression.
- Integration: operator → CAD → mesh → physics → solver → record.
- Qualification: prove failures cannot be accepted.
- Replay: rebuild selected cases from manifest.
- Generality: execute second part without product-core branches.

### 16.2 Required gates

1. Deterministic baseline import/manifest.
2. Reviewed baseline reproduction.
3. Protected interfaces stable in frozen regime.
4. Operator pre/postconditions enforced.
5. Accepted geometry has quality-qualified mesh.
6. Physics maps/rebuilds with evidence or blocks.
7. Accepted solver results pass numerical qualification.
8. Accepted records contain complete lineage/replay.
9. UI cross-links CAD, mesh, physics, and results correctly.
10. Agents cannot exceed tool, contract, coverage, or budget permissions.

### 16.3 KPIs

- Stage yields: geometry, mesh, physics, solver, engineering qualification.
- Coverage Contract completion by cell/status.
- Accepted/quarantined/rejected counts.
- Replay pass rate.
- Cost/time per attempt and accepted record.
- Cost per coverage increment and uncertainty reduction.
- Budget consumption versus planned/reserved budget.
- Failure distribution and recovery success.
- Proposal calibration and source-specific performance.
- Duplicate rate, topology novelty, and genealogy diversity.
- Comparison of grammar/DOE/local/premium proposal policies.

---

## 17. Final implementation rule

Do not add another major architectural subsystem before M0 and M1 are operational. The architecture is now complete enough to build.

The immediate work is executable contracts, deterministic ingestion/extraction, baseline reproduction, interface protection, the first two operators, CAD-conforming meshing, and the first qualified records.

fastCAD’s product identity is now fixed:

```text
Structured engineering intelligence chooses valuable experiments.

Architecture grammar constrains meaningful design novelty.

Variant recipes compile concepts into executable programs.

Deterministic engineering tools establish geometry, physics, numerical, and qualification truth.

CampaignMemory turns outcomes into operational learning.

DecisionBudget makes cost-awareness enforceable.

Accepted records become the proprietary engineering data asset.
```
