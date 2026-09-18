# fastCAD Agentic Intelligence Architecture

## An agentic system for governed geometry variation, simulation-data generation, and continuous engineering learning

**Scope:** Stage 1 of fastCAD, focused on producing 100–200 trustworthy, diverse, feasible, and engineering-qualified gearbox-housing variants and their resulting simulation data.

**Primary demonstration:** NREL GRC gearbox rear housing, while preserving a generic core architecture that can later operate on other housings and structural parts through a new engineering context and Design Contract.

---

## 1. The central correction

fastCAD must not be merely a safe scripted geometry-to-FEA pipeline.

A safe deterministic pipeline is necessary, but it is not sufficient to make the product intelligent or agentic. The system becomes genuinely agentic when it can repeatedly:

```text
Understand the engineering context
        ↓
Form hypotheses about useful structural changes
        ↓
Synthesize contract-compliant architecture proposals
        ↓
Choose the most informative experiments
        ↓
Execute trusted deterministic tools
        ↓
Observe geometry, mesh, solver, and engineering outcomes
        ↓
Learn from successes and failures
        ↓
Update its campaign strategy
        ↓
Choose what to try next
```

The key distinction is:

```text
Agent-assisted automation
= Runs a static predetermined workflow.

Agentic engineering system
= Observes state, reasons over evidence, plans actions, learns from outcomes,
  and changes the next plan while remaining inside explicit engineering rules.
```

---

## 2. The primary objective

The agent must be optimized for a real engineering campaign objective, not simply for making geometries.

```yaml
goal:
  accepted_variant_target: 120
  part_family: GRC gearbox rear housing

hard_constraints:
  - Frozen bearing and mounting interfaces
  - Manufacturing-compatible geometry
  - Valid geometry identity and lineage
  - Qualified mesh
  - Valid physics transfer
  - Solver-qualified result
  - Engineering-qualified response

coverage_objectives:
  - At least 7 architecture families
  - Minimum accepted samples per architecture family
  - Broad parameter-bin coverage
  - Hybrid-architecture coverage
  - Response-space diversity

required_outputs:
  - Geometry and mesh artifacts
  - Mass and volume
  - Stress and displacement measures
  - Bearing-seat translations and rotations
  - Shaft/bearing relative-motion descriptors
  - Gear-misalignment-relevant outputs
  - Full provenance and replay manifests

budget:
  - Maximum solve count
  - Maximum CPU hours
  - Maximum storage
  - Maximum wall-clock duration
```

The real optimization problem is:

> Build the most informative, diverse, engineering-valid dataset possible under a finite compute budget.

---

## 3. The final architecture

```text
                         ┌───────────────────────────────┐
                         │       FASTCAD SUPERVISOR       │
                         │ Goal / State / Memory / Plan   │
                         │ Reflection / Stop Conditions   │
                         └───────────────┬───────────────┘
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        │                                │                                │
        ▼                                ▼                                ▼
┌───────────────────┐          ┌───────────────────┐          ┌───────────────────┐
│ Engineering Agent │          │   Design Agent    │          │ Campaign Scientist│
│ Understand        │          │ Hypothesize       │          │ Choose experiments│
│ relationships     │          │ Synthesize recipes│          │ Coverage / value  │
└─────────┬─────────┘          └─────────┬─────────┘          └─────────┬─────────┘
          │                              │                              │
          └──────────────────────────────┼──────────────────────────────┘
                                         ▼
                              Structured Variant Recipe
                                         │
                                 Design Contract Gate
                                         │
                               Deterministic CAD Operators
                                         │
                                    Exact B-rep Variant
                                         │
                                   CAD-conforming Mesh
                                         │
                                  Physics Mapping Layer
                                         │
                                         FEA
                                         │
                                Qualification Plane
                                         │
                    ┌────────────────────┴─────────────────────┐
                    ▼                                          ▼
         Result Analysis / Dataset Agent           Failure Diagnosis Agent
                    │                                          │
                    └────────────────────┬─────────────────────┘
                                         ▼
                              Persistent Shared Memory
                                         │
                                         └──────────────→ Supervisor
```

The agentic intelligence sits above a deterministic trust layer.

```text
Agents understand, hypothesize, plan, experiment, diagnose and learn.

Deterministic engineering tools realize, mesh, transfer physics, solve,
and certify the results of those decisions.
```

---

## 4. Three kinds of intelligence

### 4.1 Generative intelligence

Question:

> What design architectures could exist inside this approved design family?

Inputs:

- Engineering graph.
- Design Contract.
- Feature/operator library.
- Architecture-pattern knowledge.
- Existing accepted and failed variants.

Outputs:

- Structured architecture hypotheses.
- Typed `VariantRecipe` proposals.
- Candidate operator compositions.

Examples:

```text
H1: Reinforce HSS support using a radial rib group.
H2: Couple two bearing-support regions with a deep inter-bore bridge.
H3: Create a triangular bore-to-mount support path.
H4: Use an X-braced bridge to alter translation-rotation coupling.
H5: Combine a local collar, diagonal path and windowed web.
```

### 4.2 Engineering intelligence

Question:

> Which candidate architectures make physical and engineering sense for the stated objective?

The reasoning chain should be explicit:

```text
Geometry change
        ↓
Structural load path and stiffness distribution
        ↓
Bearing-seat translation and rotation
        ↓
Shaft-axis change
        ↓
Gear-mesh misalignment descriptor
        ↓
Gear microgeometry/LTCA relevance
```

This intelligence comes from:

- Engineering graph relationships.
- Physical hypotheses.
- Baseline FE/CAE context.
- Explicit manufacturing and physics rules.
- Response histories from completed simulations.

### 4.3 Experimental intelligence

Question:

> Which simulation should be run next to learn most efficiently?

The campaign planner should balance:

```text
information gain
+ design diversity
+ architecture coverage
+ response uncertainty
+ feasibility probability
+ engineering relevance
- compute cost
```

A candidate should be selected because it has expected campaign value, not merely because it is geometrically valid.

---

## 5. Five intelligence loops

### 5.1 Engineering Understanding Loop

Question:

> What is important in this housing and how is it structurally connected?

The system must reason beyond individual detected features.

```text
HSS bearing support
       │
       ├── surrounding wall
       ├── local existing/confirmed rib system
       ├── load path toward mount
       ├── relation to adjacent bearing support
       └── relation to shaft axis and outputs
```

The output is an **Engineering Context Model**, not a CAD edit.

### 5.2 Design Synthesis Loop

Question:

> Which structural architecture classes could meaningfully alter the target mechanism while respecting the contract?

The Design Agent reasons from:

```text
Engineering objective
+ structural mechanism
+ confirmed entities
+ frozen interfaces
+ mutable zones
+ manufacturing rules
+ operator capabilities
```

to a candidate architecture and recipe.

### 5.3 Campaign Intelligence Loop

Question:

> Which members of the feasible design space deserve scarce CAD/mesh/FEA compute?

The Campaign Scientist combines:

- CP-SAT feasibility.
- Design of experiments.
- Architecture and parameter coverage.
- Failure-risk probability.
- Surrogate uncertainty.
- Expected engineering information gain.
- Compute resource cost.

### 5.4 Failure and Physics Learning Loop

Question:

> What did the system learn from CAD, mesh, physics mapping, solver, or engineering failure?

A failure is not only a rejected candidate. It is a structured observation about the valid boundary of the design family and pipeline.

### 5.5 Surrogate and Active-Learning Loop

Question:

> Given the accepted records, which unexplored candidate is most likely to improve knowledge or meet an objective?

This loop begins with simple response and feasibility models and becomes stronger as the accepted dataset grows.

---

## 6. The engineering graph

### 6.1 Purpose

The engineering graph is the agent’s machine-readable view of the part. It is richer than a B-rep adjacency graph and more reliable than prose.

```text
B-rep graph
        ↓
Feature graph
        ↓
Engineering semantic graph
        ↓
Physics graph
        ↓
Design Contract graph
        ↓
Variant lineage graph
```

### 6.2 Graph layers

| Layer | Represents | Example |
|---|---|---|
| Geometry graph | CAD entities, adjacency, geometry | cylindrical face adjacent to wall faces |
| Feature graph | feature candidates | bore, boss, wall, rib candidate, fillet candidate |
| Semantic graph | engineering meaning | HSS bearing seat, mounting face, split line |
| Physics graph | simulation context | bearing coupling, pressure load, support, contact |
| Contract graph | permissions and rules | frozen seat, mutable zone, legal rib anchors |
| Lineage graph | variant history | source wall → modified wall → variant mesh group |

### 6.3 Example relationships

```text
BearingSeat --supported_by--> SurroundingWall
BearingSeat --connected_to--> BearingSupportRib
BearingSeat --load_path_to--> MountingInterface
BearingSeat --paired_with--> OppositeBearingSeat
Rib --reinforces--> WallZone
LoadSurface --mapped_to--> MeshSurfaceGroup
BearingCoupling --applies_to--> BearingSeat
```

### 6.4 What agents query

The agent should be able to ask structured graph questions:

```text
What supports HSS_B_SEAT?
Which frozen interfaces are within 100 mm of this mutable zone?
Which approved operators can connect HSS_B_SEAT to MOUNT_2?
Which existing variants changed this load path?
Which outputs are associated with this bearing interface?
```

---

## 7. Hierarchical design reasoning

Do not let an agent plan individual ribs first. Use a hierarchy from engineering intent to exact geometry.

```text
Level 1: Engineering objective
  “Generate meaningful diversity in differential bearing tilt.”

Level 2: Structural mechanisms
  Local bearing support
  Inter-bearing coupling
  Bore-to-mount load path
  Front-to-rear coupling
  Shell flexibility
  Directional/asymmetric reinforcement

Level 3: Architecture classes
  Radial rib group
  Collar
  Straight bridge
  X/K brace
  Triangular support path
  Tie rail
  Windowed web
  Hybrid

Level 4: Parameters
  Thickness, height, length, angle, count, taper, location, symmetry

Level 5: Exact recipe
  Typed deterministic OperatorCall[]
```

This structure creates design intelligence without allowing arbitrary CAD generation.

---

## 8. Architecture Reasoner

### 8.1 Role

The Architecture Reasoner is the central Design Agent capability.

Input:

```text
Engineering graph
+ Design Contract
+ Qualification Model
+ campaign objective
+ known response patterns
+ known failure patterns
+ available operator library
```

Output:

```text
Architecture hypothesis
+ expected structural mechanism
+ candidate anchors
+ permitted operators
+ risk assessment
+ test rationale
```

### 8.2 Structured architecture proposal

```python
class ArchitectureHypothesis(BaseModel):
    hypothesis_id: UUID
    objective_id: UUID
    mechanism: str
    architecture_class: str
    anchors: list[str]
    candidate_operators: list[str]
    expected_response_changes: list[str]
    manufacturing_risks: list[str]
    physics_risks: list[str]
    evidence: list[str]
    confidence: float
```

### 8.3 Example

```yaml
architecture_class: INTER_BORE_X_BRACE
mechanism: change differential support compliance between two bearing regions
anchors:
  - HSS_B_SEAT_OUTER_COLLAR
  - HSS_C_SEAT_OUTER_COLLAR
operators:
  - add_inter_bore_bridge
  - add_x_or_k_brace
  - add_window_in_generated_web
expected_response_changes:
  - reduced relative bearing translation
  - changed translation-rotation coupling
risks:
  - local thin regions near brace intersection
  - higher meshing complexity
```

---

## 9. HNC-CAD and learned proposal models

### 9.1 Correct role

Learned CAD systems should not be trusted geometry authorities in Stage 1.

They may be introduced early as **proposal generators**, not as final geometry generators.

```text
Engineering graph
        ↓
Rule-based design synthesis
+ optional learned graph/latent proposal model
        ↓
Structured candidate program
        ↓
Design Contract validation
        ↓
Deterministic B-rep operators
        ↓
Exact geometry
        ↓
Qualification
```

### 9.2 Initial implementation

Before an internal GRC dataset exists, use:

- Architecture-pattern templates.
- Rule-based composition.
- LLM reasoning over typed graph/contract information.
- Diversity planners.
- Optional public-model experimentation only as an offline research aid.

### 9.3 Later implementation

After sufficient accepted variants:

- Train a feature-graph/recipe encoder.
- Learn a latent representation of valid architecture/parameter programs.
- Generate structured proposals constrained to known operator vocabulary.
- Use the proposal model to increase creative search diversity.

The model output should be a recipe, not a STEP/B-rep/mesh file.

---

## 10. Persistent memory system

A genuine agentic system needs decision-relevant persistent memory, not only logs.

```text
FASTCAD MEMORY

Engineering Memory
Design Memory
Failure Memory
Experiment Memory
Model Memory
```

### 10.1 Engineering Memory

Contains:

- Confirmed semantic entities.
- Interface identities and frames.
- Loads, BCs, contacts and output definitions.
- Engineering graph relationships.
- Load paths and structural hypotheses.
- Baseline reproduction evidence.

### 10.2 Design Memory

Contains:

- Architecture classes.
- Variant recipes.
- Operator sequences.
- Successful construction strategies.
- Geometry descriptors.
- Variant genealogy.

### 10.3 Failure Memory

Contains:

- Geometry failures.
- Topology failures.
- Mesh failures.
- Physics mapping failures.
- Solver failures.
- Engineering qualification failures.
- Parameter combinations.
- Failure locations.
- Repair attempts and outcomes.

### 10.4 Experiment Memory

Contains:

- What was simulated.
- Which regions and architectures are covered.
- Response distributions.
- Compute costs.
- Hypotheses supported or contradicted.
- Current uncertainty/gaps.

### 10.5 Model Memory

Contains:

- Feasibility model versions.
- Response surrogate versions.
- Active-learning state.
- Training dataset versions.
- Validation metrics.
- Domain-of-validity information.

### 10.6 Storage principle

Use typed relational/graph records as the source of truth. Use vector retrieval only as a supplementary interface for text notes, operator narratives, design rationale and historical diagnosis narratives.

Do not substitute a vector database for deterministic engineering identity, constraints or provenance.

---

## 11. Knowledge bases

### 11.1 Engineering ontology

A generic vocabulary defining types and relationships.

```text
Entities
BearingSeat
Mount
BoltPattern
Datum
Wall
Rib
Boss
Flange
LoadSurface
ConstraintSurface
ContactPair
ShaftAxis
GearAxis

Relations
supports
connects_to
constrains
transfers_load_to
aligned_with
protects
depends_on
near
mapped_to
```

### 11.2 GRC engineering knowledge base

Part-specific confirmed truth:

- Bearing identities and axes.
- Mounting interfaces.
- Baseline deck entities.
- Load cases.
- Materials.
- Known support paths.
- Critical outputs.
- Interface constraints.
- Geometry/mesh/solver artifacts.

### 11.3 Operator knowledge base

Each operator is a knowledge object, not only Python code.

```text
Purpose
Allowed anchor types
Reference-frame requirements
Parameter domains
Preconditions
Postconditions
Topology invariants
Manufacturing invariants
Known failure modes
Recovery policies
Successful examples
Known-risk combinations
```

### 11.4 Manufacturing knowledge base

Store each rule with:

```text
Rule
Scope
Severity
Input fields
Metric
Threshold
Evidence
Source/rationale
Version
Binding/advisory status
```

### 11.5 Physics-transfer knowledge base

Store reusable patterns:

```text
Preserved face → direct transfer
Split face → rebuild under approved aggregate rule
Deleted load target → block
Changed contact pair → rebuild/review
Protected bearing island → reuse mapping/coupling
```

### 11.6 Failure knowledge base

Enable queries such as:

```text
What happened previously when an X-brace was placed in this zone?
Which repair policy succeeded for a thin root region?
What parameter ranges led to repeated local Boolean failures?
```

### 11.7 Architecture pattern knowledge base

Example pattern:

```yaml
pattern: inter_bearing_coupling
intent: alter differential bearing-support displacement and rotation
variants:
  - straight_bridge
  - deep_bridge
  - double_web
  - x_brace
relevant_outputs:
  - relative bearing tilt
  - centre-distance-related displacement
risks:
  - local thin regions
  - mass growth
  - mesh complexity
eligible_operators:
  - add_inter_bore_bridge
  - add_x_or_k_brace
  - add_window_in_generated_web
```

---

## 12. Agent tool ecosystem

The system should expose a small number of powerful typed skills, grouped by intent.

```text
EXPLORE → RETRIEVE → REASON → ACT → OBSERVE → LEARN → FEEDBACK
```

### 12.1 Explore tools

#### `inspect_engineering_model`

Returns:

- Solids/faces/features.
- Interfaces.
- Materials.
- Loads/BCs/contacts.
- Mesh groups.
- Outputs.
- Provenance and extraction confidence.

#### `traverse_engineering_graph`

Example:

```python
traverse_engineering_graph(
    start="HSS_BEARING_SEAT",
    relations=["supported_by", "connected_to", "load_path_to", "mapped_to"],
    depth=3,
)
```

#### `analyze_design_space`

Returns:

- Frozen and mutable entities.
- Available operators.
- Parameter domains.
- Keep-outs.
- Logical dependencies.
- Existing coverage.
- Feasible architecture families.

### 12.2 Retrieve tools

#### `retrieve_operator_knowledge`

Question answered:

> Which operators can alter HSS support stiffness without modifying its frozen seat?

#### `retrieve_manufacturing_rules`

Question answered:

> Which casting rules apply to a generated rib connected to this wall zone?

#### `retrieve_physics_mapping_policy`

Question answered:

> What is the approved policy if this pressure surface is split by an operator?

#### `retrieve_similar_variants`

Question answered:

> Which previously accepted or failed variants are closest in architecture, parameters and location?

#### `retrieve_failure_patterns`

Question answered:

> What failures and successful repairs occurred for this operator combination?

### 12.3 Reason tools

#### `formulate_design_hypothesis`

Input:

- Campaign goal.
- Engineering graph context.
- Contract constraints.

Output:

- Mechanism hypothesis.
- Candidate architecture classes.
- Evidence and risk.

#### `propose_architecture`

Produces a structured, contract-aware architecture proposal.

#### `explain_candidate`

Returns:

- What changed.
- Which load path changed.
- Expected output sensitivity.
- Main risks.
- Why it was selected.

### 12.4 Act tools

These tools must be deterministic.

#### `validate_recipe`

Checks recipe against the active Design Contract before geometry creation.

#### `construct_variant`

```text
VariantRecipe → exact B-rep geometry artifact
```

#### `qualify_geometry`

Checks:

- Valid solid.
- Interface identity.
- Expected volume change.
- Allowed edit region.
- Topology invariants.
- Manufacturing rules.
- Local meshability.

#### `build_mesh`

```text
B-rep → named surface groups → CAD-conforming tetrahedral mesh → TET10 policy → quality report
```

#### `map_physics`

```text
Baseline physics → candidate geometry → mapping audit → TRANSFER / REBUILD / BLOCK
```

#### `run_fea`

Runs in a sandbox and returns solver outputs, convergence, reactions, energy, artifacts, runtime and typed failure state.

#### `extract_engineering_response`

Produces engineering quantities rather than raw solver files:

- Bearing translations/rotations.
- Bore distortion measures.
- Relative bearing motion.
- Mass.
- Stress/displacement measures.
- Compliance descriptors.
- Gear-misalignment-relevant outputs.

### 12.5 Observe tools

#### `compare_variants`

Compares geometry, topology, mass, stress, bearing motion, qualification state and cost.

#### `analyze_response_sensitivity`

Estimates which architecture/parameter choices are associated with response changes.

#### `analyze_failure`

Combines typed failure evidence with historical failures and produces permitted recovery options.

### 12.6 Learn tools

#### `update_feasibility_model`

Learns completion probabilities:

```text
P(geometry success)
P(mesh success)
P(physics mapping success)
P(FEA success)
P(engineering qualification)
```

#### `update_response_surrogate`

Learns relationships such as:

```text
architecture + parameters + geometry descriptors
        ↓
mass + bearing translation + bearing tilt + stress + displacement
```

#### `measure_coverage`

Measures:

- Architecture coverage.
- Parameter coverage.
- Topology coverage.
- Response-space coverage.
- Boundary coverage.
- Genealogy coverage.

#### `propose_next_experiments`

Combines coverage, uncertainty, feasibility, diversity, engineering relevance and compute budget into a batch proposal.

---

## 13. Supervisor state and loop

### 13.1 Persistent state

```python
class CampaignState(BaseModel):
    goal: CampaignGoal
    contract: DesignContract
    engineering_context: EngineeringContext
    qualification_model: QualificationModel

    current_hypotheses: list[ArchitectureHypothesis]
    explored_architectures: list[ArchitectureSummary]
    evaluated_variants: list[VariantSummary]
    accepted_records: list[RecordSummary]
    failures: list[FailureSummary]

    coverage: CoverageVector
    feasibility_model: ModelRef | None
    response_surrogate: ModelRef | None

    compute_budget: ComputeBudget
    current_plan: list[PlannedAction]
    observations: list[Observation]
    stop_conditions: list[StopCondition]
```

### 13.2 Agent loop

```text
OBSERVE current state
        ↓
IDENTIFY information, coverage, response, or yield gap
        ↓
RETRIEVE relevant engineering/design/failure knowledge
        ↓
FORM hypothesis
        ↓
PROPOSE candidate architectures and recipes
        ↓
CHECK Design Contract and qualification preconditions
        ↓
EXECUTE deterministic tools
        ↓
OBSERVE results and failures
        ↓
UPDATE memory, coverage and models
        ↓
REFLECT on goal progress
        ↓
PLAN next actions
```

### 13.3 Stop conditions

Examples:

```text
Accepted target reached
AND architecture coverage target reached
AND parameter/response coverage target reached
AND compute budget is not exceeded
AND surrogate validation gate is reached
```

---

## 14. The five agents

Do not create a large swarm. Use five focused agents sharing the same memory and tool registry.

### 14.1 Supervisor Agent

Owns:

- Campaign goal.
- State.
- Planning hierarchy.
- Budget.
- Delegation.
- Reflection.
- Stop/continue/escalate decisions.

### 14.2 Engineering Context Agent

Owns:

- Engineering graph interpretation.
- Structural relationship discovery.
- Identification of relevant interfaces and load paths.
- Context confidence and unresolved questions.
- Engineering hypotheses grounded in baseline evidence.

### 14.3 Design Synthesis Agent

Owns:

- Architecture hypothesis generation.
- Operator composition.
- Recipe proposal.
- Use of architecture-pattern knowledge.
- Optional later learned proposal models.

### 14.4 Campaign Scientist Agent

Owns:

- CP-SAT/DOE/portfolio planning.
- Coverage gaps.
- Feasibility and compute trade-offs.
- Surrogate uncertainty.
- Batch selection.
- Experiment value scoring.

### 14.5 Recovery and Data Agent

Owns:

- Failure diagnosis.
- Selection of allowed repair policies.
- Failure-memory updates.
- Dataset quality.
- Qualification-state management.
- Feasibility/response model update triggers.

---

## 15. Safety boundary

The system must remain agentic without becoming unsafe or irreproducible.

```text
Agents may:
✓ understand
✓ retrieve
✓ hypothesize
✓ propose
✓ compare
✓ plan experiments
✓ select candidates
✓ diagnose failures
✓ choose bounded recovery actions
✓ update models and strategy

Agents may not:
✗ write arbitrary CAD/kernel code
✗ directly alter topology outside typed operators
✗ directly alter mesh nodes
✗ silently change loads, BCs or contacts
✗ invent engineering identity
✗ override failed qualification checks
✗ alter an approved Design Contract without a new revision/approval
✗ run unlimited retries
```

The action interface is:

```text
Agent
        ↓
Typed engineering skill
        ↓
Deterministic tool
        ↓
Evidence + qualification state + permitted next actions
```

---

## 16. Variant selection score

For a feasible candidate \(x\), the Campaign Scientist may use a weighted decision score:

\[
S(x) =
 w_I I(x)
+ w_D D(x)
+ w_U U(x)
+ w_C C(x)
+ w_F F(x)
+ w_E E(x)
- w_K K(x)
\]

where:

- \(I(x)\): expected information gain.
- \(D(x)\): geometry/architecture diversity.
- \(U(x)\): response-surrogate uncertainty.
- \(C(x)\): coverage contribution.
- \(F(x)\): probability of successful qualification.
- \(E(x)\): engineering relevance to the campaign objective.
- \(K(x)\): estimated compute cost.

The weights are campaign-configurable and must be recorded in the decision audit.

---

## 17. Feedback loop example

```text
Batch: 20 candidates
        ↓
Geometry qualified: 16
        ↓
Mesh qualified: 14
        ↓
Physics transfer qualified: 13
        ↓
Solver qualified: 12
        ↓
Engineering qualified: 11
```

The system then updates:

```text
Design memory
Failure memory
Architecture coverage
Parameter coverage
Response coverage
Feasibility model
Response surrogate
Architecture-priority ranking
Next candidate portfolio
```

A later batch should not be a repeated random sample. It should reflect what was learned.

---

## 18. Failure learning example

```text
Observed pattern:
X-brace + low wall thickness + high brace height
        ↓
Geometry succeeds
        ↓
Mesh repeatedly fails at root transition

Learned condition:
wall_thickness < threshold
AND brace_height > threshold
        ↓
High local mesh-risk region
```

The system response may be:

- Add a scoped CP-SAT no-good combination.
- Prefer an alternative root/blend construction.
- Increase local geometry or mesh policy only if contract allows it.
- Mark the region low feasibility in the feasibility model.
- Preserve it as coverage information rather than silently delete it from the campaign story.

---

## 19. Integration with the existing fastCAD blueprint

This document extends, rather than replaces, the deterministic blueprint.

### Keep unchanged

- Canonical Engineering Model.
- Design Contract.
- Qualification Model.
- Interface identity and lineage.
- Protected interface islands.
- Exact B-rep for trusted analysis.
- CAD-conforming mesh.
- Physics Mapping Layer.
- Formal operator contracts.
- Accepted simulation records.
- Replay manifests.
- Yield plus coverage reporting.

### Make first-class

- Engineering Context Model.
- Architecture Reasoner.
- Design synthesis hypotheses.
- Persistent agent memory.
- Experiment/value-based campaign planning.
- Failure learning and feasibility modeling.
- Supervisor-led plan-act-observe-learn loop.

---

## 20. Implementation sequence

### Phase 0 — Trust substrate

Build:

- Canonical Engineering Model.
- Design Contract.
- Qualification Model.
- InterfaceIdentity.
- Operator contracts.
- Geometry/mesh/physics/solver qualification.
- Replay manifests.

### Phase 1 — Engineering reasoning substrate

Build:

- Engineering graph.
- Graph query tools.
- Architecture-pattern knowledge base.
- Operator knowledge base.
- Manufacturing and physics-mapping knowledge objects.
- Context Agent summary and unresolved-question output.

### Phase 2 — Design synthesis

Build:

- `ArchitectureHypothesis` schema.
- `propose_architecture` tool.
- Rule-based architecture templates.
- Structured recipe normalizer.
- Design Agent audit/explainability.

### Phase 3 — Campaign scientist

Build:

- CP-SAT architecture feasibility.
- DOE sampler.
- Diversity metrics.
- Coverage model.
- Estimated cost model.
- Candidate score implementation.
- Batch proposal tool.

### Phase 4 — Learn from execution

Build:

- Failure KB.
- Similar-failure retrieval.
- Bounded recovery policy selector.
- Feasibility model prototype.
- Result response analysis.
- Experimental-memory update pipeline.

### Phase 5 — Surrogate and active learning

Build:

- Scalar response surrogate.
- Genealogy-aware data splits.
- Uncertainty/OOD policy.
- Active-learning batch selector.
- Solver fallback rules.

### Phase 6 — Learned proposal model

Only after a sufficiently broad accepted dataset exists:

- Train feature/recipe graph representation.
- Train a constrained proposal model.
- Restrict output to available architecture/recipe grammar.
- Keep Design Contract and Qualification Plane as hard gates.

---

## 21. Stage-1 success criteria

The system is successful when it demonstrates all of the following:

1. The GRC baseline is imported, extracted, reviewed and reproduced with evidence.
2. Critical interfaces are confirmed, stable and protected.
3. The system proposes several architecture classes for a stated engineering objective.
4. Each proposal is represented as a typed recipe and bound to an approved contract.
5. Deterministic tools build, mesh and solve variants without manual CAD/deck editing during campaign execution.
6. Every failure has a typed cause, evidence and bounded disposition.
7. Every accepted result has complete provenance, qualification evidence and replay data.
8. Campaign selection changes after observing response/failure data.
9. The system shows yield and design-space coverage together.
10. The system generates 100–200 accepted, diverse and engineering-qualified records.

---

## 22. Final statement

fastCAD should not aim merely to automate a fixed CAD-to-FEA workflow.

It should become an agentic engineering experiment system:

> It understands an approved engineering context, hypothesizes meaningful structural architectures, generates contract-compliant exact variants, validates every deterministic step, learns from both successes and failures, and continuously chooses the next experiments that build the most valuable simulation dataset.

The final principle is:

> **Agents understand, hypothesize, plan, experiment, diagnose and learn. Deterministic engineering tools realize, solve and certify their decisions.**
