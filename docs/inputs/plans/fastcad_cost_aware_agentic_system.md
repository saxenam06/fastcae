# fastCAD Cost-Aware Agentic Engineering System

## Final architecture for intelligent, economical generation of qualified geometry–simulation datasets

**Scope:** This document defines the cost-aware agentic layer for fastCAD. It complements the deterministic engineering foundation: canonical engineering model, Design Contract, qualification model, exact B-rep operators, CAD-conforming meshing, physics mapping, solver execution, accepted records and replay.

**Primary Stage-1 objective:** Create 100–200 diverse, feasible, reproducible and engineering-qualified gearbox-housing variants from an approved baseline and produce a trustworthy training dataset under a finite CAD/mesh/FEA compute budget.

---

## 1. Executive decision

fastCAD should not use a premium frontier model for routine engineering automation. Most of the workflow already has exact or structured answers and should remain deterministic, analytical, or handled by inexpensive specialized models.

The correct architecture is a **cost-aware intelligence router**:

```text
Engineering goal
        ↓
FastCAD Supervisor
        ↓
Cost / Value / Risk Intelligence Router
        ├── Tier 0: deterministic engineering tools
        ├── Tier 1: local analytics and specialized models
        ├── Tier 2: premium strategic reasoning
        └── Human review when approval is mandatory
        ↓
Batch campaign plan
        ↓
Exact CAD → mesh → physics mapping → FEA → qualification
        ↓
Results, failures, coverage and model updates
        ↓
Next-batch decision
```

The most important optimization objective is not token cost alone:

> **Maximize engineering information gained per expensive CAD/mesh/FEA campaign cost.**

Premium reasoning should be used only when it materially improves a high-value campaign decision.

---

## 2. The operating principle

```text
Spend reasoning where it changes the next expensive engineering decision.

Spend simulation compute where it produces new engineering information.

Use deterministic software wherever an exact answer already exists.
```

This makes fastCAD both more economical and more trustworthy.

---

## 3. Why this matters for fastCAD

For a real campaign of 100–200 housing variants, major costs are normally associated with:

- CAD construction failures and repair attempts.
- Surface/volume meshing.
- TET10 model size and preprocessing.
- Solver CPU/HPC usage.
- Storage and movement of result fields.
- Engineering review of ambiguous results.
- Repeated low-value simulation of near-duplicate designs.

A limited number of strategic AI calls is usually much cheaper than unnecessary high-fidelity solves. The right use of reasoning is therefore to prevent wasteful simulation and improve the information content of each accepted record.

---

## 4. Three-tier intelligence system

### 4.1 Tier 0 — Deterministic engineering truth

Use deterministic tools whenever the task has a known algorithmic or rule-based answer.

```text
OpenCascade / B-rep geometry
Gmsh meshing
OR-Tools CP-SAT
Python numerical/statistical routines
Geometry identity signatures
Manufacturing rules
Physics mapping rules
Qualification checks
Solver execution
Result extraction
Replay verification
```

Tier 0 must own all certification and high-consequence decisions.

### 4.2 Tier 1 — Local analytical and specialized ML intelligence

Use inexpensive, local, batchable models only within known applicability domains.

Appropriate tasks:

```text
Candidate feature classification
Rib/boss/fillet candidate ranking
Failure categorization where rules are insufficient
Historical failure retrieval
Variant similarity and duplicate detection
Architecture embeddings
Recipe normalization
Campaign summaries
Feasibility probability prediction
Response surrogate prediction
Uncertainty estimates
Coverage clustering
```

Tier 1 models rank, prioritize and advise. They do not certify critical identities, physics mappings or final qualification.

### 4.3 Tier 2 — Premium strategic reasoning

Use a premium reasoning model only for high-leverage, ambiguous or cross-domain decisions.

Appropriate tasks:

```text
New engineering problem interpretation
Ambiguous campaign objective clarification
Competing architecture hypotheses
Cross-checking design rationale against the engineering graph
Novel/unknown failure diagnosis after deterministic analysis
Major change in campaign strategy
High-value next-batch decision review
Human-readable explanation of a complex evidence package
Synthesis of accumulated campaign knowledge
```

Tier 2 creates plans, hypotheses and recommendations. It never directly generates arbitrary CAD/kernel code, modifies mesh nodes, changes solver matrices, or overrides qualification gates.

---

## 5. What each tier should own

| Task | Owner | Reason |
|---|---|---|
| Cylinder, bore, cone and bolt-circle detection | Tier 0 | Analytic geometry is exact and repeatable |
| Bearing interface identity | Tier 0 | Must be auditable and deterministic |
| Protected-interface checks | Tier 0 | Cannot depend on probabilistic labels |
| Draft, wall thickness, clearance and ligament checks | Tier 0 | Executable numerical rules |
| CP-SAT configuration feasibility | Tier 0 | Exact discrete constraint solving |
| CAD operation execution | Tier 0 | Deterministic operator contracts |
| Mesh generation/quality | Tier 0 | Mesher and numerical quality metrics |
| Physics transfer/qualification | Tier 0 | High-consequence engineering decision |
| FEA execution and numerical qualification | Tier 0 | Must be reproducible |
| Duplicate candidate ranking | Tier 1 | Similarity is cheap and batchable |
| Failure type refinement | Tier 0 then Tier 1 | Use tool failure code first; model only if needed |
| Geometry/mesh/solver success probability | Tier 1 | Learned from fastCAD’s own campaign history |
| Response prediction | Tier 1 | Surrogate models are a core later capability |
| Coverage analysis | Tier 0 + Tier 1 | Metrics are deterministic; clustering/embedding can help |
| Architecture proposal | Tier 2 with pattern library | Strategic synthesis across graph, constraints and outcomes |
| Major campaign strategy change | Tier 2 | High leverage and sparse decision |
| Unusual failure diagnosis | Tier 2 after evidence retrieval | Requires reasoning, but must stay evidence-bound |
| Final acceptance/rejection | Tier 0 | Qualification Plane is deterministic |

---

## 6. The Intelligence Router

### 6.1 Responsibility

The router determines **who should solve a task**. It is separate from the agents that formulate engineering intent or execute workflows.

```text
Task request
        ↓
Can Tier 0 answer exactly?
        ├── Yes → deterministic tool
        └── No
             ↓
Is a local model validated for this task/domain?
        ├── Yes → Tier 1 local intelligence
        └── No
             ↓
Does the task exceed ambiguity, consequence and value thresholds?
        ├── Yes → Tier 2 premium reasoning
        └── No → deterministic heuristic, defer, or human review
```

### 6.2 Router inputs

- Task type.
- Required confidence.
- Consequence of error.
- Reversibility of action.
- Deterministic tool availability.
- Local-model applicability and confidence.
- Current campaign phase.
- Current compute/model budget.
- Expected decision value.
- Expected FEA/CAD cost avoided or enabled.
- Contract permissions.
- Human-review requirement.

### 6.3 Router output

```python
class RouteDecision(BaseModel):
    task_id: UUID
    executor: Literal[
        "DETERMINISTIC_TOOL",
        "LOCAL_MODEL",
        "PREMIUM_REASONER",
        "HUMAN_REVIEW",
    ]
    rationale: str
    required_confidence: float
    estimated_quality: float | None
    estimated_model_cost: float
    estimated_latency_s: float
    estimated_downstream_compute_cost: float | None
    escalation_condition: str | None
    context_package_id: UUID | None
    approval_requirement: str | None
```

### 6.4 Router rules

1. A premium model never decides on its own that it should be called.
2. A deterministic answer always wins over an LLM answer for certification tasks.
3. Local models can only be used within their validated domain.
4. Premium calls are budgeted by campaign and batch.
5. Human review remains available for low-confidence/high-consequence decisions.
6. Every route choice is recorded as an audit event.

---

## 7. Premium reasoning should think in batches

### 7.1 Anti-pattern

Do not create a premium-model loop around every mechanical operation.

```text
Premium model → construct one CAD operation
Premium model → inspect
Premium model → mesh
Premium model → inspect
Premium model → run solver
Premium model → inspect
```

This is expensive, slow, difficult to audit and causes the model to act as a fragile workflow interpreter.

### 7.2 Correct pattern

```text
Premium reasoning model
        ↓
Creates strategic batch plan
        ↓
Deterministic campaign engine executes 20–30 candidates
        ↓
Analytics layer summarizes batch results
        ↓
Premium model receives one compact evidence package
        ↓
Chooses next strategic batch
```

### 7.3 Example campaign sequence

```text
Batch 0
Baseline understanding, interface confirmation, contract approval

Batch 1
Broad architecture exploration
- collars
- radial support
- inter-bore bridge
- bore-to-mount path
- tie rail

Batch 2
Fill architecture and parameter coverage gaps

Batch 3
Probe high-response or high-uncertainty regions

Batch 4
Explore selected hybrid architectures and boundary cases

Batch 5
Validate surrogate/OOD gaps and confirm best candidates
```

The premium model may therefore make only a handful of high-level planning decisions while controlling a much larger deterministic campaign.

---

## 8. Candidate value versus model-route value

Separate the question “should this candidate be simulated?” from “which model should decide?”

### 8.1 Candidate simulation value

For candidate \(x\):

\[
V_{\mathrm{sim}}(x) =
\frac{
I(x) R(x) P_{\mathrm{complete}}(x)
}{
C_{\mathrm{CAD}}(x) + C_{\mathrm{mesh}}(x) + C_{\mathrm{FEA}}(x)
}
\]

Where:

- \(I(x)\): expected information gain.
- \(R(x)\): relevance to the campaign objective.
- \(P_{\mathrm{complete}}(x)\): predicted probability that the candidate reaches engineering-qualified status.
- \(C_{\mathrm{CAD}}(x)\): expected geometry construction cost.
- \(C_{\mathrm{mesh}}(x)\): expected meshing cost.
- \(C_{\mathrm{FEA}}(x)\): expected solve cost.

### 8.2 Model-route value

For reasoning task \(q\) and executor \(m\):

\[
V_{\mathrm{route}}(q,m) =
\frac{
\Delta Q(q,m)
}{
C_{\mathrm{model}}(q,m) + C_{\mathrm{delay}}(q,m)
}
\]

Where:

- \(\Delta Q(q,m)\): expected improvement in decision quality over the next-cheapest eligible alternative.
- \(C_{\mathrm{model}}(q,m)\): inference cost.
- \(C_{\mathrm{delay}}(q,m)\): decision latency cost.

Escalate to a premium reasoner only when it is expected to improve a decision enough to justify the extra cost/latency.

---

## 9. Decision budgets

Premium reasoning must be constrained by an explicit, auditable budget.

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

### 9.1 Measure actual value

Track:

- Premium calls, latency and spend.
- Local-model inference count and latency.
- CAD/mesh/solver resource usage.
- Cost per attempted variant.
- Cost per accepted record.
- Cost per coverage increment.
- Cost per uncertainty reduction.
- Premium-strategy benefit versus DOE-only baseline.
- Yield and coverage together.

The objective is not “use fewer model calls” in isolation. The objective is “use model calls where they lower total campaign cost or improve dataset value.”

---

## 10. Strategic context compression

### 10.1 Principle

The premium reasoner must receive a compact evidence package, not raw CAD, all solver files, complete historical logs or hundreds of records.

```text
Databases and graph tools retrieve evidence.
Analytics compress it.
The premium model reasons over the evidence package.
```

### 10.2 Strategic context package

```python
class StrategicContextPackage(BaseModel):
    campaign_goal: CampaignGoal
    contract_summary: ContractSummary
    engineering_subgraph: GraphFragment

    latest_batch: BatchSummary
    coverage_gaps: CoverageReport
    response_summary: ResponseSummary
    uncertainty_summary: UncertaintyReport
    feasibility_summary: FeasibilityReport

    top_success_patterns: list[PatternEvidence]
    top_failure_patterns: list[FailureEvidence]
    candidate_portfolio: list[CandidateSummary]

    budget_status: BudgetReport
    decision_question: str
    allowed_decisions: list[str]
```

### 10.3 Example premium-model prompt content

```text
Goal:
Increase architecture and response coverage for differential bearing tilt,
while keeping frozen interfaces unchanged and mass within the approved range.

Current gap:
Only one accepted inter-bore X-brace variant; no accepted asymmetric bore-to-mount variants.

Evidence:
- 5 relevant engineering graph relationships
- 5 nearest successful designs
- 5 relevant failure patterns
- feasibility estimates for candidate portfolio
- surrogate uncertainty
- current resource budget

Decision request:
Select the next 12 variants by architecture category and explain the expected information value.
```

---

## 11. Local specialist models

### 11.1 Principle

As the dataset grows, local models should learn from **fastCAD’s own qualified and failed history**. They should reduce unnecessary premium reasoning and unnecessary high-fidelity solves.

### 11.2 Useful local models

| Model | Input | Output | Use |
|---|---|---|---|
| Geometry feasibility | recipe, anchors, parameters, descriptors | probability of geometry qualification | prioritize/reject only with coverage safeguards |
| Mesh feasibility | geometry descriptors, operator history | probability of mesh qualification | choose mesh policy and rank candidates |
| Physics mapping risk | topology/lineage events | probability of transfer/rebuild/block | plan review effort |
| Solver completion | mesh and deck descriptors | probability of solver qualification | scheduling and risk-aware portfolio |
| Response surrogate | recipe/descriptors/conditions | mass, stress KPI, bearing motion | uncertainty-driven active learning |
| Architecture embedding | recipe/graph | similarity/distance | diversity and duplicate detection |
| Failure retrieval model | failure signature/evidence | similar failures/repair outcomes | recovery support |

### 11.3 Safety restriction

Local models may:

- Rank.
- Prioritize.
- Recommend.
- Estimate uncertainty.
- Propose a limited set of experiments.

Local models may not:

- Certify protected interface identity.
- Certify physics equivalence.
- Override a deterministic failed check.
- Accept a simulation record on their own.

---

## 12. Cost-efficient campaign loop

```text
Engineering goal
        ↓
Supervisor observes campaign state
        ↓
Intelligence Router assigns reasoning tasks
        ↓
Engineering/Design/Campaign agents produce a batch plan
        ↓
CP-SAT and DOE generate feasible candidate portfolio
        ↓
Local feasibility/response models score candidates
        ↓
Batch selection under compute budget
        ↓
Deterministic exact CAD / mesh / physics / FEA execution
        ↓
Qualification Plane
        ↓
Cheap analytics layer
        ↓
Update failure memory, coverage, feasibility model and surrogate
        ↓
Premium strategic review only if routing policy allows and value is high
        ↓
Next batch
```

### 12.1 Initial campaign behavior

Before a response surrogate exists:

```text
Use architecture quotas
+ low-discrepancy parameter sampling
+ deterministic feasibility checks
+ diversity metrics
+ limited premium reasoning for architecture strategy
```

### 12.2 Later campaign behavior

After 20–30 accepted records:

```text
Candidate pool
        ↓
Cheap feasibility and response screen
        ↓
Low value / near duplicate → do not simulate now
Uncertain / boundary / high value → simulate
High-risk but coverage-critical → limited deliberate exploration
        ↓
FEA
```

### 12.3 Important safeguard

Do not allow the feasibility model to quietly eliminate all difficult regions. Report:

```text
Yield
Coverage
Feasibility uncertainty
Unexplored approved regions
Rejected-by-model count
Exploration budget for high-risk candidates
```

---

## 13. Agent roles under cost-aware routing

### 13.1 Supervisor Agent

Owns:

- Campaign goal.
- Budget.
- Planning/observation/reflection loop.
- Delegation.
- Stop/continue/escalate decisions.

The Supervisor does not execute CAD or solvers directly. It asks the router to choose the correct intelligence/execution route.

### 13.2 Engineering Context Agent

Uses mostly deterministic graph/query tools and Tier 1 classification aids.

Escalates to premium reasoning only when:

- The objective is ambiguous.
- Important semantic conflicts remain unresolved.
- Competing engineering mechanisms require synthesis.

### 13.3 Design Synthesis Agent

Uses:

- Architecture-pattern library.
- Design Contract.
- Operator knowledge base.
- CP-SAT feasibility.
- Optional premium reasoning for high-level hypotheses.
- Optional future learned proposal models.

Output is always a typed `VariantRecipe`, never raw kernel code.

### 13.4 Campaign Scientist Agent

Uses mostly deterministic and local tools:

- DOE.
- CP-SAT.
- Diversity metrics.
- Coverage analysis.
- Feasibility models.
- Response surrogates.
- Cost estimators.

Requests premium review only for major strategy changes or uncertain high-value trade-offs.

### 13.5 Recovery/Data Agent

Uses:

- Typed failure codes.
- Repair policies.
- Similar-failure retrieval.
- Local failure models.
- Qualification reports.

Escalates unusual failures to the premium reasoner only after collecting structured deterministic evidence.

---

## 14. HNC-CAD and learned proposal models in the router

### 14.1 Initial role

In early Stage 1, do not depend on HNC-CAD or any learned geometry generator for the critical campaign path.

Use:

```text
Architecture-pattern templates
+ engineering graph
+ Design Contract
+ CP-SAT
+ deterministic recipe generator
```

### 14.2 Later role

After fastCAD has sufficient accepted variants, a learned proposal model may be a Tier 1 or Tier 2 component depending on cost and maturity.

```text
Engineering graph
        ↓
Learned recipe/architecture proposal model
        ↓
Proposal normalizer
        ↓
Design Contract validation
        ↓
Deterministic exact B-rep operators
        ↓
Qualification Plane
```

The proposal model provides creativity and candidate diversity. It is never the final geometry or engineering authority.

---

## 15. API and data models

### 15.1 New modules

```text
src/fastcad/
  intelligence/
    router.py
    policies.py
    budgets.py
    context_builder.py
    cost_model.py
    telemetry.py
    batch_planner.py

  memory/
    engineering.py
    designs.py
    failures.py
    experiments.py
    models.py
    retrieval.py

  analytics/
    batch_summary.py
    coverage.py
    response_summary.py
    feasibility.py
    cost.py

  agent/
    supervisor.py
    engineering_agent.py
    design_agent.py
    campaign_scientist.py
    recovery_data_agent.py
```

### 15.2 Core schemas

```python
class TaskRequest(BaseModel): ...
class RouteDecision(BaseModel): ...
class DecisionBudget(BaseModel): ...
class BudgetReport(BaseModel): ...
class StrategicContextPackage(BaseModel): ...
class CandidateScore(BaseModel): ...
class BatchPlan(BaseModel): ...
class BatchSummary(BaseModel): ...
class PremiumDecisionRequest(BaseModel): ...
class PremiumDecisionResponse(BaseModel): ...
class ModelApplicability(BaseModel): ...
class CostEstimate(BaseModel): ...
class AgentDecisionAudit(BaseModel): ...
```

### 15.3 API endpoints

```text
POST /intelligence/route
GET  /intelligence/budget
GET  /intelligence/telemetry
POST /campaigns/{id}/plan-batch
POST /campaigns/{id}/strategic-review
GET  /campaigns/{id}/context-package
GET  /campaigns/{id}/candidate-scores
GET  /campaigns/{id}/batch-summary
GET  /memory/failures/search
GET  /memory/designs/similar
POST /models/feasibility/train
POST /models/response/train
```

### 15.4 Audit record

```python
class AgentDecisionAudit(BaseModel):
    decision_id: UUID
    campaign_id: UUID
    task: str
    route: RouteDecision
    context_package_id: UUID | None
    options_considered: list[str]
    selected_action: str
    rationale: str
    outcome: str | None
    downstream_cost: CostEstimate | None
    created_at: datetime
```

---

## 16. UI requirements

### 16.1 Intelligence and budget panel

Show the user:

```text
Campaign budget
- FEA runs remaining
- CPU hours remaining
- Premium reasoning calls remaining
- Local model usage
- Retry budget

Current strategy
- architecture coverage mode
- uncertainty reduction mode
- boundary exploration mode
- exploitation/confirmation mode

Decision source
- deterministic policy
- local model
- premium reasoning
- human review
```

### 16.2 Decision cards

Every major decision should be inspectable:

```text
Decision
Selected 12 variants for Batch 3

Decision source
Premium strategic reasoning, approved by router policy

Why
Inter-bore X-brace coverage is low; response uncertainty is high;
geometry success probability is acceptable; remaining compute budget supports 12 runs.

Evidence
- contract version
- coverage report
- surrogate uncertainty report
- top failure patterns
- cost estimate
```

### 16.3 Batch result summary

Present a compact, comparable batch report:

```text
Attempted: 25
Geometry qualified: 21
Mesh qualified: 19
Physics qualified: 18
Solver qualified: 17
Engineering qualified: 16

Coverage gain: +12%
Cost per accepted record: ...
Most common failure: ...
Next gap: ...
```

---

## 17. Validation of the router

Do not assume premium reasoning improves the campaign. Measure it.

### 17.1 Offline benchmark set

Create fixed decision tasks:

- Select architecture families for a stated objective.
- Explain candidate relevance.
- Identify contract violations from evidence.
- Diagnose historical failure packages.
- Choose next batch from candidate portfolio.

Compare:

```text
Deterministic heuristic
Local model
Premium reasoning model
Human expert review where feasible
```

### 17.2 Online A/B policies

For comparable campaigns, compare:

```text
DOE-only planner
vs
DOE + local models
vs
DOE + local models + premium strategic review
```

Measure:

- Accepted records per CPU hour.
- Coverage gain per FEA run.
- Information/uncertainty reduction per FEA run.
- Geometry/mesh/solver yield.
- Number of duplicate/low-value simulations avoided.
- Time to reach target coverage.
- Premium model cost as a share of total campaign cost.

### 17.3 Replaceability

Premium models must remain provider-neutral. The router should target a `PremiumReasoner` interface, not a specific vendor/model identity.

---

## 18. Milestones

### M0 — Instrumentation and deterministic baseline

- Implement campaign budget model.
- Instrument CAD, mesh, solver and artifact costs.
- Build deterministic batch summaries and coverage reports.
- Establish DOE-only baseline.

### M1 — Intelligence Router

- Implement router rules.
- Add deterministic/local/premium/human route states.
- Add audit records.
- Enforce premium-call and retry budgets.

### M2 — Context packages and batch reasoning

- Build strategic context package.
- Add batch planning and results summarization.
- Ensure premium model sees compact evidence rather than raw archives.

### M3 — Local specialist models

- Implement feasibility model prototype.
- Add similarity/duplicate detection.
- Add response surrogate baseline after enough accepted records.

### M4 — Premium strategic review

- Add provider-neutral premium reasoner interface.
- Use it for architecture hypotheses and major batch strategy changes only.
- Benchmark against deterministic/DOE baselines.

### M5 — Adaptive campaigns

- Active-learning planner.
- Cost-aware candidate value scoring.
- Automatic next-batch planning under budget.
- Campaign-level measurement of decision quality and cost savings.

---

## 19. Final rules

1. Do not pay a premium model to answer what a deterministic tool already knows.
2. Do not use a premium model to issue individual CAD/mesh/solver commands.
3. Premium reasoning operates over batches and evidence packages.
4. Deterministic qualification remains the final authority.
5. Local models learn from fastCAD’s own qualified/failure data and remain advisory.
6. Cost is measured across the whole campaign, not only token usage.
7. Yield must always be reported with coverage.
8. The agent should optimize engineering information per expensive solve.
9. A premium model must be replaceable behind a typed interface.
10. The router—not the model—decides when escalation is justified.

---

## 20. Final statement

fastCAD should be a cost-aware agentic engineering system, not a premium-model wrapper around CAD tools.

```text
Cheap deterministic truth
+ local specialized learning
+ rare high-value strategic reasoning
+ exact CAD/mesh/FEA qualification
= a simulation-data factory that improves after every campaign batch
```

The premium model is not an expensive CAD operator. It is a high-level engineering strategist invoked only when deep reasoning can change a costly campaign decision. The deterministic stack remains responsible for geometry truth, interface identity, manufacturing checks, mesh quality, physics mapping, solver execution and final qualification.
