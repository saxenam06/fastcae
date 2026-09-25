# fastCAD: AI/Agent-Native Engineering Design-Space Discovery Architecture

## Core Position

fastCAD should be **AI/agent-native**, but its CAD, geometry qualification, meshing, and simulation execution must remain deterministic and governed.

These are not conflicting ideas.

```text
AI/Agent = decides, plans, adapts, explains, and learns
CP-SAT   = creates feasible structured design-space configurations
GET      = discovers smooth structural topology inside allowed design spaces
CAD/Mesh/FEA = produces and verifies engineering truth
```

The product is not a fixed script that produces variants. It is an autonomous, traceable engineering campaign system that decides what design-space experiments to run next, executes trusted tools, learns from outcomes, and continuously improves the value of its simulation dataset.

---

## Product Thesis

> fastCAD is a governed, AI-native simulation-data factory that converts one trusted CAD/CAE baseline into a qualified, physics-indexed family of structural alternatives, simulation records, surrogate models, and next-best engineering experiments.

The immediate objective is to produce approximately **100–200 trustworthy gearbox-housing simulation records** from a single GRC housing baseline.

The later objective is to generalize the same architecture to other customer CAD/CAE baselines such as:

- E-motor housings.
- Pump casings.
- Inverter enclosures.
- Battery structures.
- Brackets and cast structural parts.
- Thermal/structural housings.

fastCAD is not initially:

- A general-purpose CAD modeller.
- A natural-language CAD editor.
- A gearbox-specific expert system.
- An unconstrained generative-shape system.
- A replacement for engineering sign-off.

---

## Why Deterministic Tools Are Required

The product must be agent-native, but the engineering truth layer must be deterministic.

| Layer | Must it be deterministic? | Reason |
|---|---:|---|
| Protected bore/seat preservation | Yes | Functional interfaces cannot be changed unpredictably |
| Keep-out and clearance checks | Yes | Assembly and moving-part safety constraints are hard constraints |
| CP-SAT constraint solution | Yes | Feasibility and repeatable campaign generation |
| GET objective/domain execution | Yes | Reproducible geometry/topology optimization runs |
| Geometry validation | Yes | Detect self-intersection, thin features, non-manifold surfaces |
| Meshing | Yes | Mesh quality must be objectively measured |
| FEA solver run | Yes | Physics labels must come from verified analysis |
| Dataset admission | Yes | Only qualified records may train the surrogate |
| Campaign selection | Initially rules; later learned | This is where adaptive AI creates value |
| Failure diagnosis and recovery selection | Initially rules; later learned | Agents can react to typed failures inside approved policies |
| Next-best simulation choice | Initially DOE; later learned | Active learning reduces wasted simulations |

The agent should never replace the solver, mesher, or geometric validity checks. It should use those systems as authoritative tools.

---

## What Makes fastCAD Agent-Native

A conventional automated CAE workflow is:

```text
Engineer defines parameters
→ fixed DOE generates designs
→ batch solver runs
→ engineer manually studies results
→ engineer manually defines the next DOE
```

An agent-native fastCAD workflow is:

```text
Engineer approves a Design Contract
→ agent understands campaign state and available design space
→ agent proposes and selects useful CP-SAT + GET experiments
→ deterministic tools generate and qualify candidates
→ mesher and FEA create trustworthy labels
→ agent interprets structured results, failures, novelty, uncertainty, and cost
→ agent builds the next campaign under fixed engineering guardrails
→ engineer reviews consequential and ambiguous decisions
```

The important difference is not that an LLM draws ribs. The difference is that the platform forms a **closed loop**:

```text
Engineering context
→ proposal
→ qualification
→ simulation
→ evidence
→ learning
→ next proposal
```

---

## Overall System Architecture

```text
                               Engineer
                                  │
                                  │ approves Design Contract:
                                  │ protected geometry, loads,
                                  │ objectives, process, limits
                                  ▼
                    ┌─────────────────────────────┐
                    │ Campaign / Orchestrator      │
                    │ Agent                        │
                    │ What should be explored      │
                    │ next, and why?               │
                    └──────────────┬──────────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐n            ▼                      ▼                      ▼
 ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
 │ Context Agent    │   │ Design Agent     │   │ QA / Recovery     │
 │ CAD + FEA        │   │ CP-SAT + GET     │   │ Agent             │
 │ interpretation   │   │ experiment plan  │   │ qualification     │
 └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘
          │                      │                      │
          └──────────────────────┴──────────────┬───────┘
                                                  ▼
                                ┌────────────────────────────┐
                                │ Deterministic Tool Plane   │
                                │ CAD / field geometry /     │
                                │ CP-SAT / GET / mesher / FEA│
                                └──────────────┬─────────────┘
                                               │
                                               ▼
                                ┌────────────────────────────┐
                                │ Results + Failure +        │
                                │ Provenance Data Plane      │
                                └──────────────┬─────────────┘
                                               │
                                               ▼
                                ┌────────────────────────────┐
                                │ Surrogate / Feasibility /  │
                                │ Diversity / Uncertainty ML │
                                └──────────────┬─────────────┘
                                               │
                                               └──── back to Campaign Agent
```

Note: the `\n` artifact in the diagram should be ignored in implementation; the architecture is the agent layer above a deterministic tool plane.

---

## The Engineering Design Contract

Every campaign begins with an explicit, versioned Design Contract. This is the source of engineering authority.

```yaml
baseline:
  geometry: grc_housing.step
  solver_model: baseline_solver.inp
  material: specified_material

protected:
  interfaces:
    - bearing_seats
    - bearing_bores
    - mounting_faces
    - sealing_faces
    - bolt_holes
    - machined_datums
  keep_out_volumes:
    - gear_clearance
    - shaft_clearance
    - oil_cavity
    - assembly_access

design_space:
  candidate_zones:
    - sidewall_left
    - sidewall_right
    - mount_to_bearing_corridor
    - upper_shell_region
  allowed_operations:
    - material_addition
    - controlled_material_removal
  max_added_mass_percent: 10
  max_removed_mass_percent: 8

manufacturing:
  process: casting
  minimum_wall_thickness_mm: 4
  minimum_feature_spacing_mm: 6
  draft_rules: required

analysis:
  load_cases:
    - static_torque_and_mount
    - modal
  objectives:
    - minimize_mass
    - reduce_displacement
    - reduce_bearing_seat_tilt
    - increase_first_target_mode
```

The engineer confirms what cannot be inferred safely from geometry alone. The agents then execute, reason, and learn within that contract.

---

## CP-SAT and GET Under Agent Control

### CP-SAT role

CP-SAT creates **structured, feasible design-space configurations**.

It selects or constrains:

- Active design zones.
- Symmetry mode.
- Material-addition/removal budget.
- Allowed holes/relief zones.
- Hole count and organization rules.
- Required connectivity conditions.
- Feature-count and complexity limit.
- Spacing and non-overlap conditions.
- Manufacturing constraints.
- High-level exploration family.

Example CP-SAT configuration:

```yaml
configuration:
  active_zones:
    - sidewall_left
    - sidewall_right
    - mount_to_bearing_corridor
  symmetry: mandatory_mirror
  added_volume_budget: 0.08
  holes:
    enabled: false
  connectivity:
    - mount_neighborhood_to_flexible_sidewall
  objective_emphasis: first_mode_and_mass
```

### GET role

GET receives the selected design volume and discovers **smooth material topology** inside it.

GET inputs:

- Active design zones from CP-SAT.
- Protected B-rep functional core.
- Keep-out geometry.
- Boundary conditions and loads.
- Objective and volume/mass limit.
- Minimum feature size.
- Manufacturing and symmetry conditions.
- Optional required connectivity.

GET output can be:

- Smooth ribs.
- Wide webs.
- Curved braces.
- Tapered supports.
- Gussets.
- Material bands.
- Merged reinforcement networks.
- Local smooth wall thickening.

Combined relationship:

```text
CP-SAT says:
“Explore this legal, symmetric, 8%-mass design-space configuration.”

GET says:
“Inside that allowed volume, this is the smooth material pattern
that best improves the requested structural objective.”
```

---

## Agent Roles

## 1. Context Agent

Purpose: transform baseline CAD/FEA into a structured engineering context.

Inputs:

- B-rep CAD or mesh.
- Solver deck and mesh.
- Boundary conditions.
- Baseline FEA results.
- Design Contract.

Actions:

- Extract face/patch topology.
- Identify broad wall panels, junctions, bosses, and cavities.
- Estimate wall thickness.
- Map FEA fields to geometry.
- Propose flexible panels and high strain-energy regions.
- Propose candidate reinforcement/design zones.
- Detect possible symmetry planes or relations.
- Propose protected/functional entities with confidence.
- Ask the engineer for confirmation when confidence is insufficient.

Example:

```text
“I found two near-mirrored exterior sidewall regions.
Modal analysis shows high deformation in both.
Suggested campaign rule: enforce mirror symmetry.
Engineer confirmation required: yes/no.”
```

The Context Agent does not silently decide whether a critical functional surface can be modified.

---

## 2. Design-Space Agent

Purpose: form a portfolio of useful CP-SAT + GET experiments.

Instead of merely requesting “generate 100 variants,” it proposes distinct engineering hypotheses:

```text
Campaign A:
Symmetric sidewall reinforcement.
Goal: raise first bending-mode frequency.

Campaign B:
Mount-to-bearing structural corridor.
Goal: reduce bearing-seat tilt under torque.

Campaign C:
Upper-shell stiffening with organized relief holes.
Goal: maximize stiffness-to-mass.
```

Actions:

- Build candidate CP-SAT configurations.
- Enforce geometry, manufacturing, and campaign policies.
- Select diverse design-domain combinations.
- Specify GET objective weighting and initialization policy.
- Avoid repeatedly sampling equivalent design families.
- Submit only valid configuration contracts to GET.

Stage 1 may use deterministic diversity rules. Later it uses surrogate uncertainty, predicted performance, feasibility probability, and simulation cost.

---

## 3. Geometry/Topology Execution Agent

Purpose: execute the approved design configuration through trusted tools.

Actions:

- Invoke CP-SAT to generate feasible configuration variants.
- Materialize selected design-zone masks.
- Invoke GET with domains, loads, objectives, and constraints.
- Clip GET material to allowed geometry.
- Subtract protected and keep-out volumes.
- Produce the candidate analysis geometry.
- Register geometry parameters and hashes.

This agent executes deterministic tools. It does not invent unapproved CAD modifications.

---

## 4. Qualification and Recovery Agent

Purpose: determine whether a candidate is eligible for meshing and FEA, and respond to known failures according to approved policy.

Checks:

- Protected-interface deviation.
- Keep-out and clearance collision.
- Minimum thickness.
- Root attachment and connectivity.
- Self-intersection.
- Non-manifold/watertightness failure.
- Minimum spacing.
- Manufacturability/draft constraints.
- Surface and volume mesh quality.
- Mass budget.
- Near-duplicate geometry.

Typed recovery example:

```yaml
failure:
  type: min_feature_violation
  observed_minimum_mm: 2.7
  required_minimum_mm: 4.0

approved_policy:
  action: rerun_get
  updated_constraint:
    min_feature_size_mm: 4.5
  max_retries: 1
```

Another example:

```yaml
failure:
  type: keep_out_intersection
  region: shaft_clearance

approved_policy:
  action: reject_candidate
  reason: hard_functional_constraint
```

The agent can adapt; it cannot weaken a hard safety or functional condition.

---

## 5. Simulation Execution Agent

Purpose: execute qualified CAE cases and transform raw output into comparable engineering records.

Actions:

- Create solver input/deck from the validated candidate.
- Submit mesh and solver jobs.
- Monitor execution.
- Apply approved retry logic for infrastructure or known numerical failures.
- Extract static, modal, stress, displacement, and interface metrics.
- Record mesh diagnostics and solver logs.
- Mark each record accepted, rejected, or unresolved.

Metrics include:

- Mass.
- Maximum displacement.
- Stress metrics.
- Natural frequencies.
- Mode-shape indicators.
- Bearing-seat translation and angular tilt.
- Mount-interface deformation.
- Mesh quality.
- Runtime.
- Solver convergence.

---

## 6. Learning and Campaign Agent

Purpose: improve simulation efficiency and design-space coverage after an initial dataset exists.

First models to train:

1. Feasibility classifier: likelihood of geometry, mesh, and solver success.
2. Performance surrogate: predicted mass, stress, displacement, frequency, and interface misalignment.
3. Uncertainty estimator: where predictions are not reliable.
4. Diversity model: detect redundant candidates.
5. Failure-pattern model: predict likely failure cause and useful safe recovery.

The agent ranks potential future experiments using a decision score such as:

```text
Priority =
  predicted engineering improvement
+ surrogate uncertainty
+ dataset diversity contribution
− predicted failure risk
− expected simulation cost
```

Example decision:

```text
“Do not run 40 additional symmetric sidewall configurations.
The surrogate already has good coverage there.

Run 12 mount-to-bearing corridor configurations.
They have high uncertainty, strong bearing-seat tilt sensitivity,
and 0.86 predicted mesh success probability.”
```

This is the point where fastCAD transitions from high-throughput automation to closed-loop AI-native engineering exploration.

---

## Stage-1 Agent-Native Product

Stage 1 does not require natural-language CAD modification or a large pre-trained engineering model.

It is still agent-native because the agent owns campaign state, tool orchestration, typed decision-making, recovery, traceability, and evolving dataset strategy.

```text
1. Engineer uploads CAD/CAE baseline and approves Design Contract.

2. Context Agent creates structured geometry/physics context and
   proposes design zones, symmetry, and potential risks.

3. Campaign Agent creates diverse CP-SAT + GET experiment contracts.

4. Execution Agent runs CP-SAT and GET.

5. Qualification Agent validates each candidate and applies only
   approved recovery actions.

6. Simulation Agent runs mesh + static/modal FEA and extracts KPIs.

7. Campaign Agent stores all records, failures, and provenance.

8. Engineer views design families, campaign reasoning, failure
   distribution, and results.
```

Initially, candidate selection can use deterministic rules and diversity sampling. The platform remains agent-native because it manages and reasons over stateful engineering workflows rather than merely launching a fixed script.

---

## Governance and Provenance

Every agent decision must be stored as a structured object.

```yaml
agent_decision:
  decision_id: decision_014
  campaign_id: campaign_003
  agent: design_space_agent
  action: launch_get_experiment
  reason:
    - underrepresented_load_path_family
    - high_baseline_modal_deformation
    - satisfies_symmetry_policy
  proposed_configuration:
    active_zones:
      - mount_corridor
      - bearing_support_exterior
    symmetry: none
    added_volume_budget: 0.06
    objective: minimize_bearing_seat_tilt
  predicted:
    mesh_success_probability: 0.87
    value_score: 0.74
  approval_state: policy_approved
```

For every generated variant, store:

```text
baseline ID
Design Contract version
protected-core version
context-extraction version
CP-SAT configuration
GET input parameters and result identifier
geometry hash
qualification results
mesh diagnostics
solver deck and solver version
FEA results
agent decisions and recovery actions
accept/reject status
```

This makes the system explainable, reproducible, auditable, and safe enough for serious engineering workflows.

---

## What Agents May and May Not Do

| Agents may | Agents may not |
|---|---|
| Select next campaign candidates | Change bearing-seat tolerance |
| Propose design zones for review | Modify protected geometry without approval |
| Schedule CP-SAT, GET, meshing, and FEA tools | Override clearance violations |
| Rank configurations by diversity/value | Accept a failed mesh |
| Diagnose typed failures | Invent new load cases silently |
| Retry within approved parameter bounds | Relax hard manufacturing limits |
| Decide which simulation is most informative | Claim physical performance without FEA |
| Ask engineer for clarification | Replace engineering sign-off |

The authority hierarchy is:

```text
Engineering Contract = functional and safety authority
Deterministic geometry checks = geometric authority
Mesher = mesh authority
FEA solver = physics authority
Agent = planning, execution, adaptation, and explanation authority
```

---

## Roadmap

## Phase 0 — Baseline Truth

- Reproduce baseline GRC housing mesh and solver results.
- Extract target static and modal KPIs.
- Create the versioned Design Contract.
- Establish protected interfaces and keep-outs.

## Phase 1 — Governed Variant Factory

- CP-SAT generates organized zone/symmetry/hole/budget configurations.
- GET discovers smooth topology inside selected zones.
- Qualification checks enforce hard rules.
- Mesher and solver produce qualified records.
- Agent orchestrates all tools and stores provenance.

Target: 100–200 qualified gearbox-housing simulation records.

## Phase 2 — Data-Aware Agent

- Train feasibility and scalar-performance models.
- Use uncertainty and diversity to prioritize new campaigns.
- Automatically avoid likely failures and redundant samples.
- Produce evidence-backed campaign recommendations.

## Phase 3 — Closed-Loop Design Discovery

- Agent identifies weak, uncertain, or high-value design-space regions.
- Agent proposes new CP-SAT + GET contracts within guardrails.
- FEA verifies each proposal.
- New results update surrogate models.
- Engineer approves major campaign policy changes.

---

## Final Architecture Statement

```text
Engineer-approved Design Contract
+
AI/Agent campaign intelligence
+
CP-SAT structured configuration generation
+
GET smooth topology discovery
+
Deterministic geometry and mesh qualification
+
FEA physics validation
+
Provenance-rich simulation dataset
+
Surrogate and active-learning feedback
```

The defining principle is:

> Agents decide and coordinate. Deterministic tools generate and verify. FEA provides engineering truth.

This is how fastCAD can be genuinely AI/agent-native without making critical engineering geometry, meshing, or physical validation depend on unreliable free-form AI behavior.
