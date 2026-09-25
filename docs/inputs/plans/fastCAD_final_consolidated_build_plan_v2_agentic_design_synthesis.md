# fastCAD — Final Consolidated Stage-1 Build Specification, v2

## Constraint-Governed, Cost-Aware, Agentic Engineering Simulation Data Factory

**Status:** Architecture frozen; implementation roadmap active

**Primary demonstrator:** NREL Gearbox Reliability Collaborative rear housing, drawing 254492

**Stage-1 purpose:** Convert one trusted structural CAD/CAE baseline into a governed design family, generate diverse exact geometry variants, solve and qualify them, and produce a replayable engineering dataset for later surrogate-guided design decisions.

**Primary acceptance target:** 100–200 accepted, diverse, reproducible, engineering-qualified geometry–simulation records.

**Early proof target:** 40 variants executed end to end with no manual CAD or solver-deck editing after campaign launch.

---

## 1. Executive decision

fastCAD is a **constraint-governed, cost-aware, agentic engineering experiment system**.

It is not a chat-to-CAD product, not a general CAD system, and not an LLM that improvises geometry, meshing, loads, or solver settings. It takes a trusted engineering baseline, establishes and confirms its engineering context, defines exactly what may vary, proposes and realizes governed structural architectures, then turns solver-qualified results into a reusable data asset.

The operating model is:

```text
Trusted CAD + mesh + deck + baseline result
                    ↓
Canonical Engineering Model
                    ↓
Engineer-confirmed Design Contract
                    ↓
Engineering Graph + Knowledge Bases + Campaign Memory
                    ↓
Agent Supervisor / Design Synthesis / Campaign Science
                    ↓
Intelligence Router
                    ↓
Structured VariantRecipes
                    ↓
Exact deterministic B-rep → mesh → physics mapping → FEA → qualification
                    ↓
Accepted simulation records + failures + experiment evidence
                    ↓
Memory update → next campaign plan
```

The product’s defensible value is not the ability to add a rib. It is the ability to turn one trusted CAE case into many comparable, qualified, semantically traceable, replayable geometry–physics records while preserving engineering intent and operating under a finite compute budget.

---

## 2. Final product definition

### 2.1 Product thesis

> fastCAD compiles an engineer-approved design family into exact, solver-qualified structural variants and learns which experiments to run next, while deterministic engineering tools remain the final authority for geometry, physics, numerical validity, and record acceptance.

### 2.2 The target customer problem

A customer commonly has:

- A production or advanced-development CAD model.
- A validated or trusted solver mesh/deck/result baseline.
- Materials, loads, constraints, contacts, and output requests.
- A need to test many allowable structural alternatives.
- Scarce analyst time for manual CAD edits, meshing, deck repair, job management, post-processing, and dataset curation.
- A future goal to use surrogate models, optimization, or digital-twin workflows.

The practical bottleneck is not just solver runtime. It is safely preserving the original engineering context while topology changes.

### 2.3 What fastCAD is

fastCAD is:

- A governed design-family compiler.
- A simulation campaign control plane.
- A deterministic qualification system for geometry, mesh, physics, solver outputs, and reproducibility.
- A semantic lineage system.
- A qualified simulation-data factory.
- An agentic experiment planner that learns from campaign outcomes.

### 2.4 What fastCAD is not in Stage 1

Do not build the following until the deterministic data-factory rail is proven:

- General-purpose CAD authoring.
- Free-form chat-to-CAD editing.
- LLM-generated geometry code directly executed by the kernel.
- Arbitrary learned STEP/B-rep generation as trusted geometry.
- Generic topology optimization platform.
- Field/voxel/SDF-only geometry used as final analysis geometry for bearing-motion-sensitive cases.
- Autonomous design release or certification.
- Deep field surrogates before scalar response and data-integrity baselines.
- Moved-bore/moved-mount/scaled-housing campaigns before frozen-interface campaigns succeed.

### 2.5 Core differentiation

| Existing category | Typical capability | fastCAD differentiation |
|---|---|---|
| CAD systems | Create exact geometry | Governs how an existing validated design may vary while preserving engineering intent |
| Implicit/field modelers | Create field-driven geometry | Creates solver-qualified variants and evidence-backed data from a trusted CAE baseline |
| DOE tools | Sweep declared dimensions | Creates architecture-changing variants under explicit constraints |
| CAE solvers and cloud tools | Run simulations | Assesses what to generate, whether the model remains valid, and whether results become trusted data |
| AI surrogate platforms | Learn from data | Generates and qualifies the missing dataset upstream |
| PLM/SPDM | Organize files/process | Tracks semantic engineering lineage, qualification, replay, and accepted-record eligibility |

---

## 3. Non-negotiable principles

1. **Topology variation over dimension sweeps.** Campaign richness comes from multiple structural mechanisms and architecture classes, not many values of one parameter.
2. **Never invent semantics.** Imported labels remain facts; inferred labels remain candidates until confirmed.
3. **Interfaces are first-class objects.** Bearing seats, mounts, datums, seals, bolt patterns, load surfaces, and constraint surfaces are semantic engineering entities, not transient CAD face IDs.
4. **Freeze what defines the measurement.** First campaigns change surrounding compliance, not the geometry or numerical definition of critical bearing/mount interfaces.
5. **Exact B-rep is the trusted analysis representation.** Fields/SDFs may screen or plan but cannot be the authority for final interface-sensitive analysis.
6. **Agents plan; deterministic tools execute and certify.** Probabilistic intelligence cannot override deterministic qualification.
7. **Only qualified records become response-training data.** A solver exit code alone is not proof of engineering validity.
8. **Failures are data.** Failures must be structured, retained, and used to improve feasibility, recovery, and campaign planning.
9. **Yield and coverage are co-equal metrics.** Never celebrate yield while hiding unexplored difficult contract-approved space.
10. **Part-agnostic core; part-specific configuration.** New parts require a new baseline, semantic confirmation, and Design Contract—not core conditional branches.
11. **Replay is mandatory.** Every accepted record must be reconstructible from an immutable manifest and versioned artifacts.
12. **Spend intelligence only where it improves an expensive engineering decision.** Use deterministic methods whenever they can answer exactly.

---

## 4. Stage-1 success definition

### 4.1 Required dataset outcome

The Stage-1 target is 100–200 `ACCEPTED` records across diverse architecture and parameter regions. Every accepted record must contain:

```text
Baseline identity and source hashes
+ contract version
+ typed recipe and genealogy
+ exact CAD artifact
+ geometry/manufacturing qualification evidence
+ protected-interface evidence
+ mesh and coupling evidence
+ physics transfer audit
+ solver/deck/runtime metadata
+ numerical qualification evidence
+ scalar and retained field outputs
+ bearing-motion / misalignment descriptors
+ campaign and planning context
+ replay manifest
```

### 4.2 Record states

| State | Definition | Response-surrogate eligibility |
|---|---|---|
| `ACCEPTED` | Passes all applicable deterministic qualification gates with complete evidence | Yes |
| `QUARANTINED` | Potentially informative but lower-fidelity, ambiguous, novel, or review-required | No |
| `REJECTED` | Fails a hard contract or qualification gate | No |

Quarantined and rejected outcomes remain part of failure memory and feasibility learning, never silent response-training inputs.

### 4.3 Campaign success formula

A campaign should not be declared successful based only on accepted count. Define a campaign scorecard with separate gates:

```text
Campaign Success
=
Accepted-record target achieved
AND
minimum architecture-family coverage achieved
AND
minimum parameter-bin coverage achieved
AND
response-space diversity reported
AND
critical interface fidelity maintained
AND
replay pass rate achieved
AND
budget respected or explicitly reviewed
```

A practical scalar campaign-health score may be used for ranking campaign plans, but it must never replace hard acceptance gates:

\[
S_{\mathrm{campaign}} =
 w_A A_{\mathrm{normalized}}
+ w_C C_{\mathrm{coverage}}
+ w_D D_{\mathrm{response}}
+ w_Y Y_{\mathrm{yield}}
+ w_R R_{\mathrm{replay}}
- w_B B_{\mathrm{budget\_overrun}}
\]

where all weights and component definitions are visible and contract/configuration versioned.

### 4.4 Stage-1 exit criteria

1. The GRC baseline imports, is semantically reviewed, and is reproduced with a formal certificate.
2. Critical interfaces are confirmed, protected, traceable, and stable across frozen-interface variants.
3. The system proposes several architecture classes for stated engineering mechanisms.
4. Architecture proposals compile into typed `VariantRecipe` programs governed by the Design Contract.
5. Deterministic tools build, mesh, transfer/rebuild physics, solve, and qualify variants without manual CAD/deck editing during a campaign.
6. Each failure has a typed cause, evidence, recovery disposition, and replay manifest.
7. Campaign selection changes after evidence is observed.
8. Yield and coverage are shown together by architecture class, parameter region, topology, and response region.
9. The 100–200 accepted-record target is met under an adaptive solver budget.
10. Scalar surrogate predictions are evaluated on genealogy-aware held-out architecture/parameter regions and expose uncertainty/OOD state.
11. The generic core works on a second structural part using a new baseline and contract only.

---

## 5. Governing models and data authority

### 5.1 The three truth layers

```text
Canonical Engineering Model
        ↓
What was imported or deterministically derived from customer artifacts

Design Contract
        ↓
What may vary in this approved campaign

Qualification Model
        ↓
What must remain true for a candidate to be trusted and accepted
```

### 5.2 Canonical Engineering Model

This is the immutable normalized representation of a baseline package. It includes:

- CAD sources, source hashes, units, coordinate systems, and import reports.
- B-rep geometry/topology entities and analytic surfaces.
- Feature candidates and extraction confidence.
- Mesh nodes/elements/groups and geometry mapping where available.
- Solver deck objects and original labels.
- Materials, sections, loads, constraints, contacts, steps, and output requests.
- Reference-result metadata, probes, scalar outputs, field outputs, and baseline artifacts.
- Provenance classification and unresolved ambiguities.
- Extraction coverage report.

### 5.3 Design Contract

The Design Contract is an engineer-approved campaign policy. It includes:

- Frozen/moved interface policies.
- Protected islands and transition boundaries.
- Mutable regions and keep-out volumes.
- Permitted operator versions, anchors, composition rules, and parameter ranges.
- Logical, geometric, manufacturing, and physics-transfer rules.
- Campaign goal, required outputs, and response constraints.
- Coverage requirements.
- Compute, solver, retry, storage, and premium-reasoning budgets.
- Approval, supersession, and audit metadata.

### 5.4 Qualification Model

The Qualification Model defines deterministic acceptance evidence:

- Contract validity.
- Interface identity/fidelity.
- Geometry health and expected topology.
- Manufacturing rules.
- Mesh quality and coupling integrity.
- Physics transfer/rebuild validity.
- Solver/numerical validity.
- Engineering output completeness and plausibility.
- Dataset eligibility.
- Replay integrity.

### 5.5 Shared typed vocabulary

Pydantic v2 models are authoritative. Generate TypeScript types from schemas so backend, UI, tools, and agents share a single versioned language. Physical quantities must carry units at API boundaries.

```python
class VariantRecipe(BaseModel):
    variant_id: UUID
    baseline_id: UUID
    contract_version: str
    architecture_class: str
    structural_mechanisms: list[str]
    operations: list[OperatorCall]
    parent_variants: list[UUID]
    proposal_provenance: dict
    planner_reason: dict
    random_seed: int | None = None

class CampaignMemory(BaseModel):
    campaign_id: UUID
    contract_version: str
    active_hypotheses: list[dict]
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
    revision: int
```

---

## 6. GRC Stage-1 design family

### 6.1 Frozen engineering core

Initially preserve:

- Bearing-seat cylinders, radii, axes, axial boundaries, and local frames.
- Gear/shaft packaging-clearance envelopes.
- Essential mounting, bolt, datum, and sealing interfaces.
- Baseline coordinate frames and reference points.
- Interfaces required by loads, constraints, contacts, or output definitions unless an explicit mapping/rebuild policy exists.

Do not initially vary bearing-bore centers, axes, diameters, gear center distance, primary mount locations, or key sealing faces.

### 6.2 Mutable region

```text
Frozen bearing/mount/seal/datum islands
+ packaging and load/constraint keep-outs
+ approved structural design zones
= governed design family
```

### 6.3 Structural mechanisms

The Design Synthesis Engine reasons at the mechanism level before it selects geometry.

| Structural mechanism | Engineering intent | Possible architecture families |
|---|---|---|
| Local bearing support | Change radial/tangential stiffness around a seat | collar, radial ribs, tangential ribs, pad |
| Inter-bearing coupling | Alter relative bearing translation/rotation | bridge, double web, X/K brace |
| Bore-to-wall load path | Couple a bearing support to a shell region | diagonal rib, triangular web, local trunk |
| Bore-to-mount load path | Change how bearing loads reach mounts | bore-to-mount rib, rail, shared trunk |
| Front-to-rear coupling | Control longitudinal differential compliance | tie rail, sidewall spine, boxed corridor |
| Split-line/flange support | Change joint flexibility | flange reinforcement, bolt-boss support, cover rib |
| Shell redistribution | Alter global shell stiffness/mass | belt, bulkhead, approved wall-zone adjustment, generated web/window |
| Directional/asymmetric reinforcement | Deliberately alter coupling in a preferred direction | biased ribs, asymmetric bridge, one-sided rail |

### 6.4 Architecture diversity requirement

Do not treat 40 numerical variations of one operator as meaningful diversity. A strong campaign spans multiple architecture classes and selected hybrid combinations.

---

## 7. Design Synthesis Engine

### 7.1 Purpose

The Design Synthesis Engine closes the gap between a high-level engineering objective and a deterministic geometry program. It must create genuinely new **structured architectures** from reusable grammar and patterns—not merely choose one of ten fixed operators independently.

Its output is always a typed, contract-validatable design program. It never emits arbitrary CAD code, raw STEP geometry, mesh modifications, or solver edits.

### 7.2 Final design-synthesis pipeline

```text
Engineering objective
        ↓
Structural mechanism identification
        ↓
Architecture Pattern Knowledge Base
        ↓
Architecture Grammar
        ↓
Rule-based / learned / premium-reasoned proposal generators
        ↓
Architecture composition and canonicalization
        ↓
Structured architecture proposal
        ↓
Recipe compiler
        ↓
Typed VariantRecipe
        ↓
Design Contract validation + CP-SAT feasibility
        ↓
Deterministic exact B-rep operators
```

### 7.3 Architecture Grammar

The grammar is the bounded generative substrate of fastCAD. It defines the legal language for building structural architectures from functional components, not arbitrary geometry.

A grammar production combines:

```text
Structural mechanism
+ eligible semantic anchors
+ permitted architecture pattern
+ operator composition
+ local frames
+ parameter domains
+ symmetry/bias choice
+ compatibility constraints
+ manufacturing and protected-interface restrictions
```

Example conceptual grammar:

```text
Architecture
  ::= LocalSupport
   | InterBearingCoupling
   | BoreToMountPath
   | FrontRearCoupling
   | ShellReinforcement
   | HybridArchitecture

LocalSupport
  ::= Collar(SeatAnchor, CollarParams)
   | RadialRibGroup(SeatAnchor, WallAnchor, RibParams)
   | LocalPad(SeatAnchor, PadParams)

InterBearingCoupling
  ::= Bridge(SeatAnchorA, SeatAnchorB, BridgeParams)
   | XBrace(BridgeAnchorA, BridgeAnchorB, BraceParams)
   | DoubleWeb(SeatAnchorA, SeatAnchorB, WebParams)

HybridArchitecture
  ::= Compose(Architecture, Architecture)
  subject_to ContractCompatibility
```

The grammar must be typed and limited to available deterministic operators. Its purpose is controlled novelty through **new legal compositions, anchors, parameterizations, symmetry modes, and topology classes**.

### 7.4 Architecture Pattern Knowledge Base

Patterns encode engineering intent and known composition structures. A pattern is more than a code template.

```yaml
pattern_id: INTER_BEARING_X_BRACE
mechanism: alter differential support compliance between two bearing regions
required_anchor_roles:
  - bearing_support_outer_region
  - bearing_support_outer_region
optional_anchor_roles:
  - mutable_web_zone
operator_sequence:
  - add_inter_bore_bridge
  - add_x_or_k_brace
  - add_window_in_generated_web
expected_response_changes:
  - reduce relative bearing translation
  - alter translation_rotation coupling
relevant_outputs:
  - relative_bearing_tilt
  - center_distance_change
  - mass
risks:
  - brace intersection thin region
  - mesh complexity
  - mass increase
compatibility_rules:
  - requires: INTER_BORE_WEB_ZONE
  - excludes: CONFLICTING_THROUGH_WINDOW
```

Patterns may be authored initially and extended by campaign evidence. A pattern is not a final recipe: it is a mechanism-aware structural template with allowed variations.

### 7.5 Proposal mechanisms

The `proposal_generator` supports multiple proposal sources behind one typed interface:

| Proposal source | Best role | Authority limitation |
|---|---|---|
| Rule-based grammar enumeration | Reliable initial candidate generation | Limited to authored grammar/patterns |
| Constraint-guided composition | Legal hybrid architecture generation | Must pass exact geometry and qualification |
| Local learned proposal model | Suggest novel/underexplored grammar programs using campaign data | Must output grammar-constrained recipes only |
| HNC-CAD or graph-generative plug-in | Generate latent or graph proposals that decode to structured architecture programs | Never emits trusted final CAD/B-rep directly |
| Premium strategic reasoner | Suggest mechanisms, architecture hypotheses, and strategic combinations | Must return typed proposals grounded in available patterns/grammar |
| Human engineer | Add/approve new patterns or constraints | Must be compiled and contract-bound like every other proposal |

### 7.6 HNC-CAD / graph generative model role

HNC-CAD-like or graph-generative models should be plugged into `propose_architectures()` as an optional proposal mechanism once a compatible representation exists.

The correct integration is:

```text
Engineering graph + contract + campaign memory
        ↓
Learned latent / graph proposal model
        ↓
Candidate architecture program or grammar choices
        ↓
Proposal normalizer and grammar validator
        ↓
Typed VariantRecipe
        ↓
Contract validation
        ↓
Deterministic B-rep realization
        ↓
Qualification
```

The learned model does not become CAD authority. It is a structured design-proposal engine. Its output must remain restricted to known anchors, operators, parameter domains, and grammar productions. It may increase novelty and diversity from the start as an experimental proposal plug-in, but the critical campaign path must not depend on it until it earns evidence-based value.

### 7.7 Design-synthesis modules

```text
src/fastcad/intelligence/design/
  mechanism_reasoner.py
  architecture_grammar.py
  architecture_patterns.py
  proposal_generator.py
  proposal_normalizer.py
  architecture_composer.py
  recipe_compiler.py
  proposal_ranker.py
  novelty.py
  compatibility.py
```

### 7.8 Required design-synthesis tools

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

Suggested typed interfaces:

```python
class ArchitectureHypothesis(BaseModel):
    hypothesis_id: UUID
    objective_id: UUID
    mechanisms: list[str]
    architecture_class: str
    anchors: list[str]
    operator_candidates: list[str]
    expected_response_changes: list[str]
    manufacturing_risks: list[str]
    physics_risks: list[str]
    evidence: list[dict]
    proposal_source: str
    confidence: float | None = None

class ArchitectureProposal(BaseModel):
    proposal_id: UUID
    hypothesis_id: UUID
    grammar_trace: list[dict]
    pattern_ids: list[str]
    chosen_anchors: list[str]
    operator_plan: list[dict]
    parameter_domains: dict
    novelty_features: dict
    contract_compatibility: dict
    expected_mechanisms: list[str]

class ProposalRanking(BaseModel):
    proposal_id: UUID
    novelty_score: float
    mechanism_relevance: float
    contract_risk: float
    feasibility_estimate: float | None
    coverage_deficit: float
    expected_cost: float
    rationale: list[str]
```

### 7.9 New architecture versus arbitrary geometry

fastCAD should define “new architecture” as a new valid composition of known structural primitives, mechanism patterns, semantic anchors, topology choices, and parameter policies.

For example:

```text
Not new architecture:
Increase a rib height from 18 mm to 22 mm.

New architecture:
Replace isolated radial support with a collar + asymmetric bore-to-mount path + windowed inter-bore web, targeted to change translation-rotation coupling while preserving both bearing seats.
```

This creates meaningful novelty while preserving deterministic realizability and qualification.

---

## 8. Campaign Memory and operational agent loop

### 8.1 CampaignMemory is mandatory

The agentic loop must operate on a concrete, versioned state object, not informal logs.

```text
Supervisor state
=
Goal
+ approved Design Contract
+ Engineering Graph
+ CampaignMemory
+ current Budget
```

### 8.2 CampaignMemory contents

`CampaignMemory` must contain:

- Current engineering hypotheses and confidence/evidence.
- Architecture proposals considered, selected, deferred, rejected, and why.
- Attempted recipes and their genealogy.
- Accepted patterns and observed response patterns.
- Failure patterns, recovery attempts, and no-good constraints.
- Unresolved engineering/semantic/physics questions.
- Architecture, parameter, topology, and response-space coverage state.
- Current feasibility-model state and applicability metrics.
- Current surrogate version, uncertainty state, and OOD state.
- Budget/resource state.
- Current campaign phase and stop conditions.
- Next recommended experiments and their evidence.

### 8.3 Operational loop

```text
Observe campaign state
        ↓
Retrieve Goal + Contract + Engineering Graph + CampaignMemory + Budget
        ↓
Identify unresolved mechanism, coverage, uncertainty, or failure question
        ↓
Route reasoning task through intelligence router
        ↓
Propose/compose/rank architecture candidates
        ↓
Select bounded batch
        ↓
Execute deterministic factory
        ↓
Qualify accepted/quarantined/rejected outcomes
        ↓
Update memory, coverage, feasibility, and surrogate state
        ↓
Choose next batch or stop/escalate
```

### 8.4 CampaignMemory update rules

- Every candidate lifecycle transition writes an immutable event.
- Summaries are derived from underlying typed records and never replace them.
- Agent-written narratives are tagged as interpretation, linked to evidence, and cannot modify engineering facts.
- Contract changes create a new campaign-memory branch or campaign revision; do not merge evidence across incompatible contract versions without an explicit policy.

---

## 9. Exact geometry and operator contracts

### 9.1 Trusted geometry route

```text
Imported STEP B-rep
        ↓
Resolve semantic anchors in local frames
        ↓
Construct local parametric feature solids
        ↓
Boolean fuse/cut with checkpoint
        ↓
Local healing
        ↓
Geometry oracle
        ↓
Protected-interface comparison
        ↓
Export exact variant B-rep
```

Use OpenCascade through build123d, CadQuery, pythonOCC, or direct OCCT bindings. Keep direct OCCT access for reliable local operations and healing.

### 9.2 Initial operator library

Implement incrementally:

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

Every operator must use semantic anchors and local frames, never hardcoded global coordinates.

### 9.3 Operator contract

```text
Purpose
Allowed anchor roles
Local reference frame requirements
Parameter schema, units, and allowable domains
Preconditions
Construction method
Protected entities / keep-outs
Expected topology event
Postconditions
Manufacturing checks
Known failure codes
Bounded recovery options
Evidence emitted
Version
```

### 9.4 Geometry oracle

The geometry oracle must detect silent bad outputs, not only thrown exceptions. It checks:

- B-rep validity, shell/solid completeness, and expected body count.
- No unintended disconnection unless approved.
- Expected volume change and no accidental global volume loss.
- Protected-interface signature preservation.
- Keep-out intersections.
- Self-intersections, zero-thickness regions, slivers, and tiny edges.
- Minimum thickness/clearance conditions.
- Expected topology event and lineage consistency.
- Export/reimport validity where required.

---

## 10. Interface identity, meshing, and physics integrity

### 10.1 Interface identity

Critical interfaces are identified through deterministic analytic/topological signatures, not face indices. A bearing-seat identity includes cylinder type, axis, radius, axial bounds, area/span, fit residual, local frame, neighborhood signature, source entities, and allowable tolerance.

### 10.2 Protected islands

A protected island contains the exact sensitive interface, local collar/datum geometry, stable measurement frame, and a transition boundary outside the sensitive region.

```text
Surrounding structural material may vary.
The exact physical/numerical definition used for bearing motion must not vary.
```

### 10.3 CAD-conforming meshing

Use exact B-rep, CAD-conforming meshing—initially Gmsh—with semantic physical groups. Preserve/prove protected-interface mesh/coupling definitions across variants.

### 10.4 Interface coupling module

The coupling module records:

- Coupling type: conformal, tied/nonconformal, MPC/RBE-like, or special method.
- Node correspondence/interpolation map.
- Master/slave/symmetric configuration.
- Formulation/weights/stiffness.
- Validation evidence and applicability conditions.
- Reuse versus regeneration policy.

### 10.5 Mesh quality and recovery

Mesh qualification checks element quality, size/growth, inverted elements, domain connectivity, physical-group completeness, protected-interface consistency, and solver-required characteristics.

Recovery is bounded:

```text
Gmsh CAD-conforming mesh
        ↓ fail
Approved geometry/mesh repair
        ↓ fail
Approved controlled local remesh/refinement
        ↓ fail
Explicit lower-fidelity fallback, flagged for quarantine
        ↓ fail
Quarantine or reject with typed evidence
```

### 10.6 Physics Mapping Layer

Every load, constraint, contact, material region, section, coupling, coordinate frame, and output request receives one of:

- Direct transfer.
- Approved aggregate transfer.
- Typed rebuild.
- Ambiguous/block.
- Invalid/reject.

A mapping audit must document source identity, target entities, mapping method, evidence, rebuild parameters, contract rule used, and final outcome. No ambiguous physics case proceeds to a normal solver run.

---

## 11. Solver, response extraction, and qualification

### 11.1 Baseline reproduction certificate

Before variation, reconstruct and compare the baseline against the trusted reference across:

- Load resultants/directions/moments.
- Reactions and force/moment balance.
- Displacement norms, extrema, and probes.
- Strain energy or relevant energy measures.
- Stress/strain probe or mapped-field values.
- Bearing translation/rotation extraction.
- Mesh sensitivity near critical interfaces.
- Output presence, units, and coordinate consistency.

This establishes **verification** of the inherited workflow. It does not claim new experimental validation of the customer’s physics model.

### 11.2 Solver qualification

A result is solver-qualified only if it has:

- Normal job completion.
- Appropriate convergence.
- No NaN/Inf/nonphysical field state.
- Required output artifacts.
- Force/moment balance within tolerance.
- Finite/plausible displacement range.
- Energy consistency where applicable.
- No fatal element/model errors.
- Successful extraction of required engineering outputs.

### 11.3 Bearing motion

Use a weighted rigid-body least-squares fit over protected seat nodes/points:

\[
\min_{\mathbf{t},\boldsymbol{\theta}}
\sum_i w_i
\left\|
\mathbf{u}_i - \left(
\mathbf{t} + \boldsymbol{\theta} \times (\mathbf{x}_i - \mathbf{x}_0)
\right)
\right\|^2
\]

Store rigid translation, rigid rotation, residual, radial expansion, ovalization, local/global-frame components, and membership/coupling evidence separately.

### 11.4 Core outputs

- Housing mass and volume.
- Maximum displacement/stress metrics with context.
- Load/reaction balance.
- Per-interface translation and rotation.
- Relative bearing motion/tilt per shaft.
- Center-distance change.
- Pinion/gear axis tilt and gear-mesh-relevant lead/profile misalignment where available.
- Optional condensed interface compliance.
- Geometry, mesh, mapping, and solver quality descriptors.

---

## 12. Intelligence router and cost-aware operation

### 12.1 Authority tiers

| Tier | Appropriate work | Forbidden work |
|---|---|---|
| Tier 0: Deterministic tools | Extraction, identity, rules, CP-SAT, exact CAD, meshing, mapping, solver execution, qualification, replay | Probabilistic certification |
| Tier 1: Local models/analytics | Similarity, feature ranking, failure analysis, feasibility prediction, response surrogates, uncertainty, coverage clustering | Interface/physics/acceptance authority |
| Tier 2: Premium reasoning | Mechanism synthesis, architecture hypotheses, unusual failure diagnosis after retrieval, major batch strategy, evidence explanation | Per-operation CAD/mesh/solver control; qualification override |
| Human review | Semantic confirmation, contract approval, high-consequence ambiguity | Routine deterministic work |

### 12.2 Router policy

```text
Can Tier 0 answer exactly?
  yes → Tier 0
  no  → Is a validated Tier 1 model applicable?
            yes → Tier 1
            no  → Is the decision high-value, ambiguous, and budget-approved?
                      yes → Tier 2
                      no  → deterministic heuristic, defer, or human review
```

### 12.3 Premium reasoning operates on batches

```text
Premium strategic plan
        ↓
Deterministic execution of 20–30 candidates
        ↓
Analytics compress outcome evidence
        ↓
Premium review only when expected strategic benefit exceeds cost/latency
```

Never create the loop:

```text
LLM → one CAD edit → inspect → mesh → inspect → solve → inspect
```

### 12.4 Candidate value with coverage deficit

Use coverage deficit explicitly in candidate selection:

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
- \(R(x)\): relevance to campaign objective.
- \(P_{\mathrm{complete}}(x)\): estimated probability of qualification.
- \(D_{\mathrm{coverage}}(x)\): architecture/parameter/topology/response-space coverage deficit addressed by the candidate.
- \(C\): expected geometry, meshing, and solve cost.

Use explicit exploration quotas so low predicted feasibility cannot silently erase underrepresented but contract-approved regions.

### 12.5 Adaptive solver budget

Never hardcode a solver budget independent of target and expected yield. Calculate it from campaign conditions:

\[
N_{\mathrm{solver\_attempts}} =
\left\lceil
\frac{N_{\mathrm{accepted\_target}}}
{Y_{\mathrm{expected\_postmesh}}}
\times F_{\mathrm{safety}}
\right\rceil
\]

Where:

- \(N_{\mathrm{accepted\_target}}\) is the campaign accepted-record goal.
- \(Y_{\mathrm{expected\_postmesh}}\) is expected probability that a solver attempt becomes accepted, estimated from observed stage yields.
- \(F_{\mathrm{safety}}\) covers uncertainty, exploration, and retry overhead.

Example:

```text
Target accepted records: 150
Expected post-mesh acceptance yield: 0.82
Safety factor: 1.05
Required solver-attempt budget: ceil(150 / 0.82 × 1.05) = 193
```

The planner must expose this calculation and re-estimate it as yields improve or degrade.

---

## 13. Data, replay, and model learning

### 13.1 Storage

- PostgreSQL for typed metadata, state transitions, contracts, entity lineage, campaign memory, and audit events.
- Object storage for CAD, meshes, decks, logs, reports, images, and result artifacts.
- Parquet for scalar/tabular records.
- Zarr for large field arrays.
- DVC or equivalent for curated accepted dataset/model snapshots.

### 13.2 Replay manifest

Every attempted candidate gets a manifest containing baseline/contract/recipe hashes, operator/kernel/mesher/solver versions, mesh settings, physics mapping version, random seed, container digest, hardware/runtime metadata, and all relevant artifact hashes.

### 13.3 Surrogate sequence

Start with scalar, interpretable baselines trained solely on accepted records:

- Mass/volume.
- Stress/displacement KPIs.
- Bearing translation/rotation.
- Center-distance/misalignment descriptors.
- Geometry/mesh/physics/solver feasibility.

Use regularized regression, random forest, gradient boosting, XGBoost, ensembles, and calibrated uncertainty before graph/deep models.

### 13.4 Prediction trust layer

Every prediction includes:

- Prediction.
- Uncertainty/confidence.
- OOD indicator.
- Nearest accepted examples.
- Contract applicability.
- Recommended action: rank, simulate, or block.

A solver fallback is mandatory for high uncertainty, OOD, unseen topology, near-boundary, or Pareto-critical candidates.

### 13.5 Learned proposal evolution

The learned design-proposal plug-in may be tested early as a noncritical architecture proposer, but it becomes a primary ranking/proposal contributor only after it outperforms rule/DOE baselines on measured novelty, qualification yield, coverage gain, and engineering response value.

---

## 14. Repository architecture

```text
src/fastcad/
  schemas/
  ingest/
  geometry/
  operators/
  constraints/
  mesh/
  physics/
  solver/
  post/
  records/
  campaign/
  intelligence/
    router.py
    policies.py
    context_builder.py
    engineering_graph.py
    campaign_memory.py
    decision_audit.py
    design/
      mechanism_reasoner.py
      architecture_grammar.py
      architecture_patterns.py
      proposal_generator.py
      proposal_normalizer.py
      architecture_composer.py
      recipe_compiler.py
      proposal_ranker.py
      novelty.py
      compatibility.py
  ml/
  api/

apps/
  api/
  ui/
  worker/

tests/
  unit/
  property/
  golden/
  integration/
  qualification/
  replay/
  generality/
```

Use a modular monolith plus isolated workers first. Split into services only for clear reasons such as solver licensing/isolation, HPC scheduling, independent scaling, or deployment boundaries.

---

## 15. Revised milestone plan

### M0 — Baseline truth and reproducibility

Build:

- Baseline package manifests and hashing.
- CAD/mesh/deck/result ingestion.
- Units/coordinates framework.
- Analytic extraction and initial engineering graph.
- Semantic confirmation UI.
- Canonical Engineering Model.
- Design Contract and Qualification Model schemas.
- Baseline solver adapter and bearing-motion extractor.
- Baseline reproduction certificate.

Exit: The reconstructed baseline passes reviewed thresholds; critical interfaces are confirmed and traceable.

### M1 — Feasibility rail

Build:

- Interface identity/protected islands.
- Geometry oracle.
- Manufacturing rules v1.
- Operator base contract.
- External collar and radial-rib-group operators.
- CAD-conforming meshing and mesh quality path.
- Replay/failure taxonomy.

Exit: At least 20 geometry-and-mesh-qualified dry-run variants; no frozen-interface violation accepted.

### M2 — Structural vocabulary and design-synthesis substrate

Build:

- Bore-to-wall, bore-to-mount, inter-bore bridge, X/K brace, pad, windowed web, and tie rail operators.
- Architecture Pattern KB.
- Typed Architecture Grammar.
- Rule-based architecture composer and recipe compiler.
- CP-SAT compatibility rules.
- Basic proposal ranking using novelty, mechanism relevance, contract risk, and coverage deficit.

Exit: At least four qualified architecture classes and working conversion from objective → mechanism → architecture proposal → recipe.

### M3 — Deterministic factory plus basic agentic campaign loop

Build:

- Physics Mapping Layer and variant deck builder.
- Solver workers and numerical qualification.
- Accepted/quarantined/rejected writer.
- Basic Campaign Supervisor state machine.
- CampaignMemory object and immutable update events.
- Cost-aware batch planning using deterministic coverage/diversity/cost rules.
- Bounded failure feedback and retry policy.
- Campaign-health UI.
- First 40-variant end-to-end campaign.

Exit: The first campaign runs without manual CAD/deck editing; the supervisor observes outcomes, updates CampaignMemory, and selects at least one subsequent batch using failure/coverage evidence.

### M4 — Full adaptive campaign intelligence

Build:

- Intelligence Router with deterministic/local/premium/human routes.
- Failure-memory retrieval and feasibility model prototype.
- Coverage optimization and cost model.
- Architecture Reasoner with mechanism-based hypotheses.
- Premium batch-strategy context package, only under budgeted routing.
- Decision audit and strategy comparison versus DOE-only baseline.

Exit: Campaigns adapt batch strategy under approved contract, budget, coverage, and evidence constraints. Every major agent action is inspectable and bounded.

### M5 — Surrogate, active learning, and learned design proposal

Build:

- Dataset version/export and genealogy-aware split engine.
- Scalar response surrogates, uncertainty, and OOD layer.
- Solver fallback policies.
- Active-learning batch selector using coverage deficit.
- HNC-CAD/graph-generative/learned-recipe proposal plug-in behind `propose_architectures()`.
- Benchmark of learned proposals against grammar/DOE baselines.

Exit: 100–200 accepted records; held-out evaluation; solver-confirmed ranking; learned proposal plug-in remains grammar-constrained and evidence-audited.

### M6 — Generality proof and pilot hardening

Build:

- Second-part baseline/contract onboarding.
- Adapter hardening and deployment runbooks.
- Audit exports, user roles, pilot workflow.

Exit: Second housing/bracket runs with a new contract and semantic configuration but no GRC-specific core-code path.

---

## 16. First 12-week plan

### Weeks 1–2: Baseline and artifacts

- Freeze source CAD, mesh, deck, results, and reference metadata.
- Build immutable manifest/hashing and units/coordinate conventions.
- Implement STEP import and basic OCCT inspection.
- Implement enough solver deck parsing to expose materials, loads, constraints, contacts, outputs.
- Draft reproduction certificate metrics.
- Establish base Pydantic schemas.

### Weeks 3–4: Extraction and semantic confirmation

- Implement cylinders, planes, bolt patterns, coaxial groups, face adjacency, and signatures.
- Create interface candidates and a semantic-review workflow.
- Define protected-island representation/local frames.
- Build first Design Contract editor.
- Lock required bearing-motion and response output definitions.

### Weeks 5–6: Baseline verification

- Implement deck execution wrapper and result capture.
- Implement reactions/displacements/energy/output checks.
- Implement bearing-seat rigid fit.
- Run interface mesh sensitivity study.
- Review and lock baseline reproduction tolerances.

### Weeks 7–8: First operators and oracle

- Implement protected-interface comparison.
- Implement collar and radial-rib group with local-frame placement.
- Implement geometry health checks and manufacturing v1.
- Generate geometry candidates and replay manifests.

### Weeks 9–10: Mesh and interface integrity

- Build Gmsh semantic group mapping.
- Implement mesh quality checks and recovery ladder v1.
- Validate protected seat/coupling consistency across variants.
- Produce 20 qualified geometry/mesh candidates.

### Weeks 11–12: First factory run

- Implement physics mapping audit and variant deck creation.
- Run 10–20 end-to-end solved candidates.
- Implement accepted/quarantined/rejected records.
- Build minimal campaign dashboard and CampaignMemory event store.
- Generate a deterministic coverage-based next-batch recommendation.

---

## 17. Testing, metrics, and release gates

### 17.1 Test levels

| Test level | Purpose |
|---|---|
| Unit | Signatures, local frames, rules, parameter validation, result extraction |
| Property | Random valid/invalid parameter/operator cases and invariant checks |
| Golden artifact | Baseline extraction, identity, deck, solver probe regression |
| Operator integration | Precondition → construct → oracle → evidence pipeline |
| Full integration | CAD → mesh → physics → solver → accepted record |
| Qualification | Ensure failures cannot be accepted |
| Replay | Rebuild selected attempts from manifest |
| Generality | Execute on second part without core branch |

### 17.2 Required gates

1. Deterministic baseline import and manifest.
2. Reviewed baseline reproduction certificate.
3. Frozen-interface signatures stable under frozen-interface variants.
4. Every operator satisfies declared pre/postcondition tests.
5. Every accepted geometry yields a qualified mesh.
6. Physics maps/rebuilds with evidence or blocks.
7. Every accepted solver result passes numerical qualification.
8. Every accepted record has complete lineage/replay evidence.
9. UI mapping between CAD, mesh, physics, and results is correct.
10. Agents stay within tool/contract/retry/budget permissions.

### 17.3 Campaign KPIs

Track:

- Geometry, mesh, physics-transfer, solver, and engineering qualification yield.
- Accepted/quarantined/rejected counts.
- Coverage by architecture family, topology, parameter bin, anchor zone, boundary condition, and response space.
- Replay pass rate.
- Mean retries per accepted record.
- Cost per attempted and accepted record.
- Cost per coverage increment and uncertainty reduction.
- Solver/CPU/GPU/storage use versus adaptive budget.
- Duplicate/low-value candidate avoidance.
- Improvement versus DOE-only planning.
- Learned proposal contribution versus grammar-only baseline.

---

## 18. Final operating rules

1. GPT/Astra/local models are the strategic reasoning layer—not the CAD system.
2. The Engineering Graph and knowledge bases are the system’s world model.
3. CampaignMemory makes learning operational, versioned, and inspectable.
4. The architecture grammar bounds meaningful novelty to deterministic, contract-compliant design programs.
5. HNC-CAD/graph generative models plug into structured proposal generation, not final CAD authority.
6. The Design Contract defines allowed design freedom; the Qualification Plane defines reality.
7. A deterministic answer always wins for certification/high-consequence decisions.
8. Premium reasoning operates at batch strategy level and only when router policy justifies it.
9. Campaign value includes coverage deficit as well as information gain, relevance, feasibility, and cost.
10. Solver budgets must be adaptive to target accepted records and expected yield, not fixed by habit.
11. Yield must always be shown with coverage and failure distribution.
12. The product only expands design freedom at the rate that qualification, provenance, and replay capability can support.

---

## 19. Final definition of fastCAD

fastCAD is a governed engineering experiment system.

```text
One trusted simulation baseline
        ↓
One engineer-approved design family
        ↓
Architecture grammar + deterministic geometry realization
        ↓
Many controlled structural experiments
        ↓
Many qualified and replayable geometry–physics records
        ↓
Campaign memory and cost-aware learning
        ↓
Trustworthy surrogate-guided engineering decisions
```

Agents provide understanding, hypothesis formation, architecture synthesis, experiment selection, diagnosis, explanation, and learning. Deterministic CAD, mesh, physics, solver, and qualification tools provide the engineering authority. The result is genuinely agentic, economically controlled, and defensible for real CAE workflows.
