# GB3 Agentic Immersed Simulation and AI Platform — Master Plan

## Version and purpose

This document consolidates the product, numerical, AI/surrogate, agent, backend, UI, validation, and delivery plan for the GRC GB3 demonstration.

The goal is not to duplicate Intact.Simulation or nTop. The goal is to build a differentiated engineering platform that:

1. Compiles CAD, drawings, FEM setup, load cases, and requirements into a trusted engineering model.
2. Represents permitted geometry changes as a versioned Design Space Object.
3. Supports two simulation paths:
   - conventional body-fitted Code_Aster FEM for validation;
   - a future immersed/SDF grid path for robust exploration of topology-changing or difficult geometry.
4. Uses structured AI/agent capabilities to investigate, explain, propose, govern, and verify engineering actions.
5. Generates a data model suitable for conventional scalar surrogates, GeoTransolver-type field surrogates, and future multi-fidelity learning.

The intended claim is:

> **The platform compiles engineering artifacts into an evidence-backed, executable design space. It tells engineers what may change, what the available data supports, which simulation action is worth taking, and what must be verified before the result is trusted.**

---

# 1. Strategic Position

## 1.1 What a meshing-free solver does

An immersed/mesh-free workflow does not eliminate numerical discretization. Instead, it removes the requirement for a body-fitted volume mesh:

```text
Conventional FEM
B-rep / implicit geometry
→ surface healing
→ surface triangulation
→ conforming tetra/hex mesh
→ FE setup bound to mesh groups
→ solve

Immersed FEM
B-rep / implicit geometry
→ signed-distance / occupancy representation
→ fixed Cartesian or octree background grid
→ cut-cell geometry integration
→ semantic boundary masks
→ solve
```

The geometry boundary may cut through a fixed background grid. The method integrates material behavior only where material exists. Geometry can change without constructing a new conformal tetrahedral mesh.

## 1.2 What this approach is better at

A mesh-free/immersed implementation is stronger than the present GB3 body-fitted path for:

```text
- Implicit bodies, TPMS, lattices, and organic shapes.
- Frequent topology changes: rib addition/removal, hole/channel creation, lattice variation.
- Reducing body-fitted mesh failures and repair effort.
- Establishing a stable spatial coordinate frame for data/ML.
- Rapid exploration when conventional remeshing is the bottleneck.
```

## 1.3 What it is not automatically better at

It is not automatically better for:

```text
- High-fidelity stress around sharp or unfilleted features.
- Complex contact, bolt preload, plasticity, and strongly nonlinear physics.
- Release/certification-facing results without measured verification.
- Understanding drawing intent, GD&T, manufacturing constraints, or existing FEM semantics.
- Determining whether a geometry change is permitted.
- Making a workflow agentic merely because it is automated.
```

## 1.4 The product differentiation

The differentiated product is not “another meshless solver.”

```text
Immersed solver:
Fast geometry-aware physics evaluation.

Code_Aster solver:
High-fidelity validation reference.

Surrogate:
Near-instant approximation inside a measured trust region.

Agent:
Evidence-aware decision and action layer.

Platform:
The persistent engineering model connecting artifacts, constraints,
design permission, solver choices, results, uncertainty, and approvals.
```

---

# 2. GB3 Current State

## 2.1 Existing assets to reuse

```text
- Existing GB3 B-rep baselines and rib templates.
- Existing body-fitted CAD → mesh → setup → Code_Aster workflow.
- 490 solved designs across existing campaigns.
- Existing 16-case load-response basis for robust reweighting.
- Existing Postgres corpus and analysis APIs.
- Existing agent runtime, tool calls, SSE, proposal persistence, and approval gate.
- Existing React/Vite UI, renderer, Viewer, Split, store, and API patterns.
- Existing sparse Wendland-C2 RBF morph engine.
- Existing region resolver and evidence-aware frozen/morphable classes.
- Existing Code_Aster installation and baseline data pipeline.
```

## 2.2 Current conventional-path limitations

The immersed R&D stream is justified by known conventional-path issues:

```text
- B-rep Boolean and fillet operations can fail.
- The baseline includes unparameterisable faces/geometry repair exposure.
- MeshFix is currently part of the geometry-to-mesh survival path.
- Tetrahedral mesh quality is marginal even before morphing.
- Re-meshing identical CAD has not been perfectly deterministic.
- Changing a rib configuration requires new CAD, mesh, FEM setup, and basis cache.
- Morphed-node setup rebinding has to be implemented and verified before the first morphed solve is trusted.
```

## 2.3 Current morph capability

The existing morphing capability is not replaced by immersed geometry.

```text
RBF morphing:
- Changes existing mesh-node positions continuously.
- Preserves mesh connectivity for a fixed rib configuration.
- Keeps frozen nodes exactly fixed.
- Supports panel crown, bulge, skin thickening, flare, and stretch-type modes.
- Requires mesh-quality monitoring and amplitude limits.
- Cannot add or remove a rib topology.
```

## 2.4 Current rib topology capability

```text
Rib configuration:
- Discrete present/absent variables.
- Implemented through B-rep Boolean geometry changes.
- Requires re-meshing and setup/basis rebuilding in the current workflow.
- Creates/changes load paths.
```

The joint GB3 design space is therefore mixed:

\[
\theta = [\mathbf{r}, \mathbf{m}, \mathbf{p}]
\]

where:

```text
r = discrete rib presence/topology variables
m = continuous panel-morph amplitudes
p = future continuous rib layout / implicit geometry parameters
```

---

# 3. Morphing Versus Immersed Geometry

## 3.1 They are complementary, not alternatives

| Question | Morphing | SDF / implicit geometry + immersed FEM |
|---|---|---|
| What changes? | Existing material moves | Material occupancy/geometry can change |
| Main representation | Deformed existing mesh | Signed-distance field / implicit solid |
| Topology | Fixed | Can change |
| Add a rib | No | Yes |
| Remove a rib | No | Yes |
| Change rib count | No | Yes |
| Change wall thickness | Yes | Yes |
| Crown or bulge a panel | Yes | Yes |
| Body-fitted mesh | Preserved/deformed then quality checked | Not required for screening solve |
| Dominant numerical risk | Distorted/inverted tetrahedra | Under-resolved features, cut cells, weak BC handling |
| Best immediate use | Continuous local shape changes | Topology/implicit geometry screening |

## 3.2 Morphing equation

For existing mesh nodes:

\[
\mathbf{x}'_i = \mathbf{x}_i + \sum_j a_j\mathbf{u}_j(\mathbf{x}_i)
\]

The material remains connected in the same topology. Large movements can degrade element quality.

## 3.3 Implicit geometry equation

Under a negative-inside signed-distance convention:

\[
\phi(\mathbf{x}) < 0 \Rightarrow \text{solid}, \qquad
\phi(\mathbf{x}) > 0 \Rightarrow \text{void}
\]

For a housing plus included ribs:

\[
\phi_{\text{part}}(\mathbf{x};\mathbf{r}) =
\min\left(\phi_{\text{housing}}(\mathbf{x}),
\phi_{\text{rib}_i}(\mathbf{x})\;\forall\;i\text{ with }r_i=1\right)
\]

A rib disappears by excluding its SDF from this material-union expression. The background grid remains, but the material region changes.

## 3.4 Recommended combined execution path

```text
Continuous panel edits
→ RBF/B-rep morph preview today
→ Code_Aster verification after setup rebind
→ SDF deformation + immersed screening later

Discrete rib/topology edits
→ B-rep Boolean + Code_Aster validation today
→ SDF Boolean composition + immersed screening later

All edits
→ one versioned Design Space Object
→ one semantic boundary-condition model
→ one provenance/approval policy
```

---

# 4. The Engineering Compiler

## 4.1 Core reframe

This product is not a pipeline with an agent attached. It is an engineering compiler whose output is a versioned Design Space Object.

```text
INPUTS
CAD / B-rep / implicit geometry
Drawing sheets and GD&T
FEM setup, loads, supports, materials
Requirements and standards
Existing results and test data

PASSES
Feature recognition
Stable identity assignment
CAD ↔ drawing ↔ FEM mapping
Freeze and interface inference
Boundary mask compilation
Morph fitting / implicit geometry compilation
Validity-limit measurement
Load-basis selection

INTERMEDIATE REPRESENTATION
Identity graph + evidence records + semantic boundary regions

OUTPUT
Design Space Object
- typed parameters
- topology options
- geometric modes
- measured limits
- evidence state
- solver bindings
- surrogate schema
- provenance
```

## 4.2 Engineering identity graph

Every material engineering concept must become an entity rather than a source-file-specific item.

```text
Entity: BORE_O541
  CAD evidence: stable face / recognised bore
  Drawing evidence: tolerance and datum callout
  FEM evidence: RBE/master/load interface
  Design status: frozen
  Reason: precision interface

Entity: OUTER_SKIN
  CAD evidence: outward-facing surface region
  Drawing evidence: not yet resolved
  FEM evidence: no direct binding currently known
  Design status: provisional morphable
  Reason: geometry rule
  Evidence state: assumed

Entity: RIB_N259
  CAD evidence: discrete rib feature
  FEM evidence: associated structural region if available
  Design status: discrete topology member
  Actions: keep/remove/relocate subject to constraints
```

## 4.3 Evidence states

```text
Measured   Direct source artifact or completed simulation result.
Derived    Deterministic calculation from known inputs.
Assumed    Inference/rule without sufficient source evidence.
Unresolved Required information is missing.
Conflicted Sources disagree.
```

The agent, API, UI, report, and optimization policy must preserve these states. No statement derived from an assumed region should be presented as released design permission.

## 4.4 Boundary Region Object

Boundary conditions should not be owned only by mesh node groups. They must be solver-neutral semantic objects.

```python
BoundaryRegion(
    id,
    kind,                       # fixed, traction, bearing_load, symmetry
    semantic_entity_id,
    geometric_selector,         # cylindrical band, plane patch, surface region
    load_or_constraint,
    evidence_ids,
    evidence_state,
    solver_bindings,
)
```

This compiles to:

```text
Code_Aster:
mesh groups / RBE relationships / MED definitions

Immersed solver:
intersection of SDF boundary with geometric selector

Surrogate:
semantic boundary-condition mask/embedding
```

---

# 5. Immersed-Grid Solver Plan

## 5.1 Release 0 scope

```text
Physics
- Linear, static, isotropic, small-strain elasticity.
- One GB3 baseline first.
- One simplified support/load fixture first.

Geometry
- Existing B-rep baseline.
- Existing discrete rib candidates.
- B-rep-derived signed-distance field.

Numerics
- Uniform Cartesian 8-node hexahedral background grid.
- Full-cell Gauss quadrature for inside cells.
- Adaptive subcell quadrature for cut cells.
- Scaled penalty enforcement for displacement constraints.
- Surface-traction integration over semantic masks.
- Sparse assembly and direct sparse solve initially.

Results
- Surface/probe displacement.
- Strain energy/compliance.
- Reactions and residuals.
- Selected stable stress invariants only.
- Grid/mask/cut-cell diagnostics.
```

## 5.2 Out of scope for Release 0

```text
- Native nTop integration.
- Copying proprietary Intact methods.
- Contact, nonlinear material, plasticity, bolt preload, FSI.
- Peak stress at sharp or unfilleted rib roots.
- General modal/thermal claims before static validation.
- GPU-first development.
- Full topology optimization.
- Replacing Code_Aster for release-facing results.
```

## 5.3 Numerical formulation

For linear elasticity:

\[
K(\theta)u(\theta) = f(\theta)
\]

For a background cell \(\Omega_e\) intersected by the solid \(\Omega_s(\theta)\):

\[
K_e(\theta) = \int_{\Omega_e \cap \Omega_s(\theta)} B^TDB\,d\Omega
\]

The following are fixed for a fixed grid:

```text
- Background grid topology.
- Degree-of-freedom numbering.
- Hex element connectivity.
- Element-to-global assembly map.
- Sparse matrix sparsity pattern, if a fixed active-band policy is used.
```

The following change with geometry:

```text
- SDF values.
- Material occupancy/volume fraction.
- Cut-cell quadrature points and weights.
- Boundary-mask intersection.
- Numerical values in K(θ) and potentially F(θ).
```

## 5.4 Geometry-to-SDF service

Initial implementation:

```text
OpenCascade B-rep
→ controlled tessellation
→ triangle BVH / Embree closest-point query
→ signed distance
→ OCC solid classifier or robust winding/parity sign query
→ narrow-band cached SDF
```

The SDF API must return quality metadata:

```python
SdfQuery(
    phi_mm,
    signed,
    nearest_point,
    normal,
    distance_quality,  # exact_brep | tessellated | uncertain
)
```

## 5.5 Grid classification

Each cell is one of:

```text
outside
inside
cut
unresolved
```

Initial classifier samples:

```text
8 corners + cell center + 12 edge midpoints
```

For cut cells, perform adaptive subcell integration. If local geometry is too small for the specified grid resolution, report `unresolved`; do not silently erase it.

## 5.6 Cut-cell integration

Release 0 method:

```text
For each cut cell:
1. Subdivide into n³ subcells.
2. Evaluate SDF at subcell centers.
3. Keep solid subcells.
4. Apply standard quadrature on retained subcells.
5. Recursively refine mixed regions to bounded depth.
6. Store material fraction, quadrature count, and convergence diagnostics.
```

Later improvements:

```text
- Local interface reconstruction.
- Adaptive octree integration.
- Moment-fitting quadrature.
- High-order finite-cell basis.
- Nitsche boundary enforcement.
- Robust small-cut-cell stabilization.
```

## 5.7 Small cut-cell policy

```text
If volume fraction ≥ f_ok:
  integrate normally.

If f_min ≤ volume fraction < f_ok:
  integrate but mark conditioning risk.

If volume fraction < f_min:
  refine locally once or more.
  if still too small: mark unresolved/reject representation.
```

Do not silently delete low-volume material cells in Release 0.

## 5.8 Boundary treatment

Start with a calibrated penalty method for essential BCs:

\[
K \mathrel{+}= \alpha \int_{\Gamma_D}N^TN\,d\Gamma
\]

\[
f \mathrel{+}= \alpha \int_{\Gamma_D}N^T\bar{u}\,d\Gamma
\]

with:

\[
\alpha = c_{\alpha}\frac{E}{h}
\]

where \(c_{\alpha}\) is determined by benchmark study, documented in run provenance, and never hidden as a magic constant.

Move to Nitsche boundary conditions only after basic static validation passes.

## 5.9 GB3 load/support translation

Do not reproduce every complex existing RBE condition in the first immersed fixture.

```text
Fixture A
- One mounting/flange support mask.
- One bearing-seat cylindrical load mask.
- Static force or moment.
- Compare probes, reaction, and energy.

Fixture B
- A selected existing GB3 service case.
- Incremental translation of supports and loads.
- Compare housing-level response and bearing/bore motion.

Fixture C
- Existing 16-unit-load basis on one immersed geometry.
- Validate superposition and robust response recombination.
```

---

# 6. Continuous Stiffness and Parametric Physics

## 6.1 Why the immersed representation is useful

For continuous geometric variables \(\theta\), the background grid stays fixed while stiffness values vary:

\[
K(\theta)u(\theta)=f(\theta)
\]

This creates a structured parametric operator.

```text
Continuous panel morph
→ surface moves
→ cut-cell material fraction changes
→ quadrature changes
→ K(θ) changes continuously or piecewise smoothly

Discrete rib removal
→ material region changes discontinuously
→ K(r, m) changes by topology state
```

## 6.2 What can be reused

| Asset | Reuse across geometry states |
|---|---:|
| Background grid and DOFs | Yes |
| Sparsity pattern / symbolic ordering | Usually yes |
| Element shapes and assembly maps | Yes |
| SDF engine | Yes |
| Semantic BC definitions | Yes, although intersection must be re-evaluated |
| Unit-load multi-RHS solution | Yes per geometry state |
| Numeric LU/Cholesky factorization | Generally no |
| Exact preconditioner values | Generally no; structure/warm start may be reusable |

For one geometry state, maintain the valuable existing unit-load philosophy:

\[
K(\theta) [u_1\;u_2\;\ldots\;u_{16}] = [f_1\;f_2\;\ldots\;f_{16}]
\]

Factorize/precondition once per geometry and solve multiple right-hand sides. Load reweighting afterward remains nearly free.

## 6.3 Differentiability warning

Naive binary occupancy is discontinuous:

```python
alpha = 1.0 if phi < 0 else 0.0
```

Small geometry changes may leave stiffness unchanged until a cell classification flips, producing jumps. This is acceptable for early screening but poor for gradients.

Progression:

```text
1. Binary occupancy / adaptive subcells for visualization and static MVP.
2. Cut-cell volume fractions for smoother response.
3. Finite-difference validation of continuous parameters.
4. Smoothed Heaviside/material indicator research.
5. Analytic/differentiable dK/dθ only after validation.
```

For a smooth indicator \(H_\epsilon\):

\[
K(\theta)=\int_{\Omega_{grid}}H_\epsilon(-\phi(\mathbf{x};\theta))B^TDB\,d\Omega
\]

This enables gradients but introduces a diffuse boundary approximation. It must be calibrated, reported, and never presented as exact sharp-interface high-fidelity FEM.

---

# 7. Surrogate and GeoTransolver Strategy

## 7.1 Immediate rule

Do **not** abandon the current 490-design Code_Aster corpus or delay first surrogate baselines to build an immersed solver.

The current corpus already supports:

```text
- Scalar regression benchmark.
- Surface-point field surrogate baseline.
- Held-out topology and rib-identity validation.
- Existing unit-load/bore response analysis.
- Demonstration of robust-vs-nominal ranking.
```

## 7.2 Why immersed/SDF helps future surrogates

The core benefit is **aligned geometry and field data**.

```text
Body-fitted path:
Each topology change gives different node IDs, element connectivity,
local point density, and mesh sampling.

Immersed path:
All designs can share a world coordinate system, SDF/occupancy layout,
semantic-mask definitions, and output query coordinates.
```

This makes it easier to encode rib removal/addition as a physical material change rather than an arbitrary new mesh graph.

## 7.3 GeoTransolver implication

GeoTransolver-type models can already operate on unstructured meshes and point clouds. An immersed grid is not required for them.

The benefit is that an SDF/occupancy field augments point-cloud/mesh input with stable volumetric geometry context:

```text
- Material occupancy.
- Interior cavities and rib connectivity.
- Local wall thickness.
- Geometry distance field.
- Distance to frozen/drawing-controlled regions.
- Distance to bearing/load/support interfaces.
- Topology changes in consistent physical coordinates.
```

Recommended future hybrid:

```text
SDF / sparse voxel geometry + semantic masks
→ multiscale geometry encoder
→ GeoTransolver geometry-aware context
→ query at surface/volume/semantic probe points
→ predict fields, metrics, uncertainty, or high-fidelity correction
```

## 7.4 Semantic masks are the product advantage

A raw SDF only represents where material exists. It does not know engineering meaning.

Add machine-readable channels:

```text
M_frozen(x)
M_morphable(x)
M_assumed(x)
M_bore_O541(x)
M_bolt_flange(x)
M_load_case_k(x)
M_support_region(x)
M_rib_candidate_j(x)
M_material_j(x)
```

This allows the learned operator to distinguish the same geometric shape in different engineering roles.

## 7.5 Multi-fidelity route

The eventual high-value model is not simply:

```text
SDF → high-fidelity Code_Aster field
```

It is:

\[
\hat y_{hi}(x)=y_{immersed}(x)+\widehat{\Delta y}(x)
\]

where:

```text
y_immersed: cheap immersed screening response
y_hi: Code_Aster reference response
Δy: learned low-to-high fidelity correction
```

Candidate correction targets:

```text
- Semantic probe displacement.
- Bearing/bore axis motion.
- Compliance or strain energy.
- Stable stress percentile.
- Robust load-basis metric.
- Surface field correction at aligned query points.
```

Do not start with a full correction field. Start with semantic metrics/probes.

## 7.6 Surrogate roadmap

```text
Stage S1 — Scalar baseline now
XGBoost/LightGBM over existing design variables and scalar outputs.
Validate on held-out rib identity, rib count, and uniform holdout block.

Stage S2 — Surface point-cloud field baseline
Existing curated Zarr corpus.
Geometry through points/normals, not direct rib-ID leakage.

Stage S3 — SDF/semantic representation
Build enriched geometry channels from immersed compiler.
Train low-fidelity immersed field/metric emulator if useful.

Stage S4 — Multi-fidelity semantic correction
Immersed result + SDF/masks → Code_Aster probe/metric correction.

Stage S5 — Field correction and active learning
Only after correlation, uncertainty calibration, and verification policy exist.
```

## 7.7 Non-negotiable ML rules

```text
- Split by design, never by sampled point or load-pattern instance.
- Never claim many point samples equal many independent shapes.
- Do not feed fixed rib flags into a geometry-generalization field model.
- Do not use raw peak stress at singular/unfilleted roots as a target.
- Do not let a surrogate autonomously spend compute before measured accuracy and uncertainty gates exist.
- Report held-out rib identity and topology/count tests, not only random interpolation.
```

---

# 8. Agent-Native Product Design

## 8.1 Definition

The product becomes agent-native when the agent works over structured engineering state, not a collection of screens or text files.

```text
Not agentic:
- Chat generates a script.
- Natural language starts a fixed DOE.
- LLM summarizes plots.
- LLM selects a parameter but cannot inspect evidence.

Agent-native:
- Agent inspects typed geometry, evidence, loads, results, constraints,
  design-space limits, solver fidelity, and cost.
- Agent chooses bounded investigation tools.
- Agent explains what is unsupported or ambiguous.
- Agent proposes exact consequential actions.
- Engineer approves/rejects/edits the action.
- The platform records the decision and resulting evidence.
```

## 8.2 Capability model

### Free/read-only capabilities

```text
query_designs
pareto_front
neighbourhood
robustness
sensitivity
correlate
compare_designs
read_artifact
geometry_probe
freeze_evidence
design_space
feasible_range
headroom
mass_delta
noise_floor
preview_morph
preview_immersed_representation
inspect_immersed_diagnostics
estimate_immersed_cost
compare_solver_results
```

### Gated/consequential capabilities

```text
propose_parameter
edit_design_space
ingest_drawing_as_evidence
preview_campaign
submit_campaign
run_remote_immersed_campaign
request_code_aster_verification
cancel_or_modify_job
export_or_sign_report
```

## 8.3 Autonomy boundary

```text
Agent autonomy:
Investigate, compare, query, explain, estimate, preview, diagnose,
identify missing evidence, and draft proposals.

Engineer authority:
Spend compute, alter released design-space constraints, introduce a
new parameter, submit high-fidelity work, approve a report, and sign
or release decisions.
```

## 8.4 Agent workflow example

```text
User:
“Can we remove Rib N259 without worsening bearing-seat displacement?”

Agent:
1. Resolve RIB_N259 in identity graph.
2. Inspect drawing, FEM, manufacturing, and design-space evidence.
3. Report allowed / assumed / forbidden status.
4. Build geometry revision with rib absent.
5. Preview immersed grid, feature resolution, cut-cell and BC-mask coverage.
6. Run or propose low-cost screening analysis.
7. Compare against baseline.
8. State exploration fidelity and uncertainty.
9. Preview exact Code_Aster verification action.
10. Wait for user approval before high-fidelity execution.
```

## 8.5 The most agentic action

The strongest platform behavior is **design-space authorship**.

```text
User:
“Can we do better?”

Agent:
- Finds current parameterization has limited headroom.
- Identifies candidate geometry that is not clearly constrained.
- Explains CAD/drawing/FEM evidence and uncertainty.
- Proposes a new typed parameter with range, validity work, cost,
  affected entities, and verification plan.
- Waits for approval.
- After approval, creates a Design Space Object revision.
- The new parameter appears in the same UI/sampler/solver/surrogate path
  used by human-created parameters.
```

The agent must never invent a hidden parameter or mutate a design space without a versioned proposal.

---

# 9. Backend Plan

## B0 — Compatibility boundary

```text
Keep current ui/ and API behavior intact.
Create ui_agentic as separate frontend package/entry.
Add versioned platform API without breaking existing routes.
```

Suggested API namespaces:

```text
/api/v1/capabilities
/api/v1/workspaces
/api/v1/artifacts
/api/v1/entity-graph
/api/v1/design-space
/api/v1/immersed
/api/v1/analysis
/api/v1/campaigns
/api/v1/agent
/api/v1/sessions
```

## B1 — Capability registry

```text
GET /api/v1/capabilities
```

Backend describes:

```text
Artifact types
Entity types
Evidence states
Metric descriptors
View descriptors
Tool descriptors
Approval policies
Available solver backends
```

The frontend must render this contract rather than hardcoding GB3-specific metrics/plots.

## B2 — Artifact registry and ingestion passes

Core objects:

```text
Workspace
Artifact
ArtifactRevision
ArtifactPass
```

Each pass records:

```text
Pass name/version
Status
Input/output artifacts
Content hash/cache key
Cache hit/miss
Duration
Warnings
Diagnostics
```

## B3 — Identity graph

Core objects:

```text
Entity
EntityEvidence
EntityRelation
GeometryAnchor
Conflict
```

Required relationships:

```text
maps_to
controls
constrains
binds_to
belongs_to
derived_from
uses
affects
conflicts_with
supersedes
```

Key endpoint:

```text
POST /api/v1/entity-graph/resolve-face
```

Input: geometry revision and stable face identifier.

Output: recognized feature, CAD/drawing/FEM evidence, region class, evidence state, available actions, associated results, and relevant design-space rules.

## B4 — Design Space Object

```text
DesignSpace
Parameter
RegionClass
ValidityLimit
DesignSpaceChange
```

Every parameter has:

```text
Identifier and label
Type and units
Domain/range/default
Evidence state and provenance
Affected entities
Manufacturing/FEM constraints
Measured/provisional validity limits
Design-space version
```

Human UI edits and agent proposals must use the same server-side path.

## B5 — Immersed API

```text
POST /api/v1/immersed/preview
POST /api/v1/immersed/run-static
GET  /api/v1/immersed/{representation_id}
GET  /api/v1/immersed/{run_id}/diagnostics
POST /api/v1/immersed/{run_id}/compare-reference
POST /api/v1/immersed/{representation_id}/refine
POST /api/v1/immersed/compile-basis
```

Every result returns a universal artifact envelope:

```json
{
  "artifact_id": "...",
  "kind": "immersed_grid_diagnostic",
  "title": "GB3 immersed representation at 10 mm",
  "status": "complete",
  "fidelity": "exploration",
  "data": {},
  "view": {"renderer": "immersed-grid", "stage_view": "results"},
  "warnings": [],
  "evidence_state": "derived",
  "provenance": {},
  "actions": ["promote", "refine", "compare", "request_verification"]
}
```

## B6 — Agent and session gateway

Bind every agent thread to:

```text
Workspace
Active artifact revisions
Active Design Space Object version
Pinned artifacts
Pending proposals/approvals
```

Structured streaming events:

```text
assistant_token
agent_status
plan
selected_capability
tool_start
tool_result
artifact_created
approval_required
approval_resolved
error
complete
```

The agent uses thin wrappers to the same APIs available to the UI. No hidden privileged route.

## B7 — Approval and execution

Every consequential proposal includes:

```text
Exact tool name and typed arguments
Requirement interpretation
Scope and named baseline
Design-space/artifact revisions
Expected runtime and cost
Evidence artifacts
Alternatives
Requested approval state
```

An approval binds to one exact payload. Any edit invalidates it.

---

# 10. UI-Agentic Plan

## 10.1 Product shell

```text
┌──────────────────────────────────────────────────────────────┐
│ Workspace / part / revision       coverage    backend status  │
├──────────────┬───────────────────────────────┬───────────────┤
│ ENTITY INDEX │            STAGE              │ AGENT RAIL    │
│ entities,    │ CAD / drawing / FEM /         │ conversation  │
│ evidence,    │ design space / result /       │ cards, pins,  │
│ filters      │ workflow / immersed-grid      │ approvals     │
├──────────────┴───────────────────────────────┴───────────────┤
│ Pass log / run status / provenance / approval title block      │
└──────────────────────────────────────────────────────────────┘
```

## 10.2 Visual direction

Use an engineering-sheet visual language:

```text
- Light neutral/machined-surface background.
- White sheet/stage surfaces.
- Graphite text, hairline dividers, restrained corner radii.
- Engineering blue only for active edit/morphable state.
- Muted green for measured evidence.
- Drawing-revision red for conflict/unresolved warning.
- Ocher for running/execution state.
- IBM Plex Sans + IBM Plex Mono.
- Drafting-style leader lines and balloons for selections/pins.
```

Evidence should use line pattern as well as color:

```text
Measured: solid full-opacity line.
Derived: lighter solid line.
Assumed: dashed line.
Conflict/unresolved: revision-red marker plus text.
```

## 10.3 Entity index

Organize by engineering entity, not source file:

```text
BORE_O541        [CAD] [DWG] [FEM]      measured
FLANGE_BOLTS_25  [CAD] [DWG] [FEM]      measured
OUTER_SKIN       [CAD]                  assumed
RIB_N259         [CAD] [FEM]            derived
LOAD_CASE_03           [DWG] [FEM]      measured
```

Filters:

```text
Evidence state
Artifact source
Region class
Frozen/morphable/free
FEM-bound
Drawing-controlled
Conflict
Unmapped
Available action
```

## 10.4 Central stage

The stage is a shared artifact presentation surface:

```text
3D Model
Drawing
FEM
Design Space
Immersed Preview
Results
Workflow Proposal
```

Required interactions:

```text
- CAD face hover → graph resolution and evidence popover.
- Drawing callout selection → CAD/FEM highlight.
- FEM group selection → associated geometry highlight.
- Pinned semantic leader line → session annotation.
- Agent card promotion → stage displays returned artifact.
- Design-space parameter edit → preview geometry and constraints.
```

## 10.5 Immersed representation UI

```text
IMMERSION PREVIEW

Geometry revision: GB3 / current configuration
Cell size: 10 mm
Active cells: …
Cut cells: …
Unresolved cells: …
Minimum feature / cell ratio: …
Boundary mask coverage: …
Estimated RAM: …
Estimated solve time: …

Warnings
- Feature below selected resolution.
- Incomplete boundary mask.
- Cut-cell conditioning risk.

[Refine locally] [Run screening] [Use Code_Aster]
```

## 10.6 Agent rail

Use cards rather than floating subwindows.

Every card includes:

```text
Title
State
Capability/tool call
Exact arguments
Summary
Result artifact
Evidence/provenance
Pin
Promote to stage
Rerun
Edit arguments
Export
```

The chat prose is explanatory. The structured artifact is authoritative.

## 10.7 Approval surface

The agent rail can announce a pending action, but approval occurs in the relevant design/workflow stage. There must be one authoritative spending/approval surface.

---

# 11. Software Layout

## 11.1 Backend package layout

```text
src/fastcae/
  immersed/
    models.py
    geometry.py
    tessellation.py
    sdf.py
    selectors.py
    grid.py
    classify.py
    quadrature.py
    shape.py
    material.py
    assembly.py
    boundary.py
    solve.py
    results.py
    compare.py
    diagnostics.py
    cache.py
    manifest.py

  designspace/
    boundary_regions.py
    compiler.py

  graph/
    entities.py
    evidence.py
    relations.py

  artifacts/
    models.py
    envelopes.py
    render_models.py

  agent/
    runtime.py
    tools.py
    policies.py

  api/
    capabilities.py
    workspaces.py
    artifacts.py
    graph.py
    designspace.py
    immersed.py
    agent.py
```

## 11.2 Frontend layout

```text
ui_agentic/src/
  app/
    App.tsx
    routes.ts
    capabilityRegistry.ts
    workspaceStore.ts

  shell/
    ProductTopBar.tsx
    WorkspaceHeader.tsx
    EntityIndex.tsx
    Stage.tsx
    AgentRail.tsx
    ActivityStrip.tsx

  ingest/
    WorkspaceLanding.tsx
    ArtifactDropzone.tsx
    ArtifactInventory.tsx
    PassLog.tsx
    CoveragePanel.tsx

  graph/
    EntityRow.tsx
    EntityInspector.tsx
    EvidenceBadge.tsx
    ConflictList.tsx
    MappingOverlay.tsx

  stage/
    CadStage.tsx
    DrawingStage.tsx
    FemStage.tsx
    DesignSpaceStage.tsx
    ImmersedStage.tsx
    ResultsStage.tsx
    WorkflowStage.tsx

  agent/
    Composer.tsx
    ThreadList.tsx
    AgentCard.tsx
    ToolCallDetails.tsx
    ApprovalCard.tsx

  api/
    client.ts
    capabilities.ts
    graph.ts
    immersed.ts
    agent.ts

  styles/
    tokens.css
    base.css
    shell.css
    components.css
```

## 11.3 Existing components to reuse

```text
Reuse:
- renderer.ts
- Viewer.tsx after extracting generic selection/highlight interfaces
- Split.tsx
- Existing external-store pattern
- Existing API-client patterns
- Existing Ask Rail streaming logic

Do not copy:
- Housing/rib/bore specific React panels
- Hardcoded plot definitions
- Study-specific metrics/axes
- Fixed assumptions embedded in UI text
```

---

# 12. Validation Plan

## 12.1 Geometry validation

```text
- Analytic SDF tests: sphere, box, cylinder.
- GB3 random sign agreement against OCC solid classifier.
- Surface projection distance verification.
- SDF-derived volume convergence toward B-rep volume.
- Rib present/absent volume/sign checks.
- SDF cache reproducibility by geometry hash.
```

## 12.2 Numerical validation fixtures

| Fixture | Verifies |
|---|---|
| Patch test | Constant strain / element consistency |
| Cantilever beam | Bending displacement, penalty BC |
| Torsion bar | Shear/torsional response |
| Thick cylinder | Radial displacement/stress trend |
| Hole/cut geometry | Cut-cell integration |
| Simple ribbed plate | Rib presence/absence response |
| GB3 Fixture A | First real housing correlation |

For every test report:

```text
Displacement error
Strain-energy/compliance error
Reaction imbalance
Constraint residual
Linear-solver residual
Grid convergence trend
Cut-cell statistics
Boundary-mask coverage
```

## 12.3 GB3 comparison policy

Compare stable, meaningful quantities first:

```text
- Selected semantic-probe displacements.
- Bearing/bore center or axis movement.
- Global compliance/strain energy.
- Reaction force/moment balance.
- Broad surface displacement field sampled on common CAD points.
```

Defer:

```text
- Raw peak stress at sharp/unfilleted rib roots.
- Any single-element extreme as a release criterion.
- Complex RBE equivalence claims before explicit condition-by-condition comparison.
```

## 12.4 Trust labels

Every result must declare:

```text
Fidelity:
exploration | correlated screening | verification candidate | high fidelity

Geometry:
B-rep / SDF version and hash

Discretization:
grid type, cell size, active/cut cells, refinement policy

Boundary conditions:
method, mask coverage, constraint residual

Validation:
not compared | compared to reference | mismatch flagged

Evidence state:
measured | derived | assumed | unresolved | conflicted
```

## 12.5 Agent validation

Maintain trap and session evaluations for:

```text
- No invented numerical claims.
- No NULL interpreted as zero.
- Correct sign/magnitude behavior.
- Named baseline and objective mode.
- Ranking always includes tie/noise/robustness policy.
- No tool call beyond declared parameter schema.
- No gated action without exact approval.
- No overstatement of immersed/surrogate fidelity.
- Correct refusal for unsupported geometry, evidence, or trust region.
```

---

# 13. Phased Build Plan

## Phase 0 — Do not disrupt existing credibility work

Continue existing immediate work in parallel:

```text
- Measure current objective noise floor.
- Complete setup rebind and first morphed Code_Aster solve.
- Measure strain-energy fraction in morphable regions.
- Validate gradient/local-model path against finite differences.
- Train first scalar surrogate baseline.
- Preserve current Code_Aster corpus and result provenance.
```

These are not displaced by the immersed work.

## Phase 1 — Platform shell over existing data

### Backend

```text
- Versioned API boundary.
- Capability registry.
- Universal artifact envelope for current analysis output.
- Workspace/session binding for current agent.
```

### UI

```text
- ui_agentic shell.
- Entity/stage/agent rail/title-block layout.
- Existing analysis card promotion to stage.
- Evidence/provenance affordances.
```

### Milestone

The existing 490-design agent demo runs inside a platform-shaped workspace without creating hardcoded chart pages for each result.

## Phase 2 — Artifact and identity graph MVP

### Backend

```text
- Artifact registry and pass-event model.
- CAD entities and stable face IDs.
- Existing CAD-to-FEM mappings.
- Evidence records for region rules.
- `resolve-face` endpoint.
```

### UI

```text
- Artifact-first workspace landing.
- Named ingest-pass log.
- Entity index.
- CAD-to-FEM semantic hover and selection.
- Measured/derived/assumed/unresolved indicators.
```

### Milestone

A user opens GB3, hovers a face, and sees real CAD/FEM mapping and evidence status. The platform visibly distinguishes evidence from assumptions.

## Phase 3 — Immersed geometry compiler preview

### Backend

```text
- GB3 reference fixture package.
- Solver-neutral boundary masks.
- B-rep tessellation and SDF service.
- Uniform grid compiler.
- Cell classification and material-fraction estimate.
- `/immersed/preview` endpoint.
```

### UI

```text
- Immersed representation stage.
- Cut-cell/grid visualization.
- Feature-resolution/mask-coverage diagnostics.
- Memory/runtime estimate.
```

### Milestone

The platform can compile GB3 geometry into a reproducible immersed representation with no body-fitted volume mesh, but makes no physics claim yet.

## Phase 4 — Numerical verification and GB3 Fixture A

### Backend

```text
- Hex element assembly.
- Adaptive cut-cell subcell quadrature.
- Penalty displacement BCs.
- Traction integration on semantic masks.
- Sparse static solve.
- Result/probe sampling.
- Comparison artifact.
```

### Validation

```text
- Canonical numerical fixtures.
- Simplified matched GB3 Code_Aster fixture.
- Coarse-to-fine grid study.
```

### Milestone

The immersed solver produces traceable static displacement/compliance/reaction results for GB3 Fixture A, correlated to Code_Aster within predeclared research thresholds.

## Phase 5 — Topology demonstration

### Backend

```text
- Rib present/absent SDF composition.
- Small GB3 rib-removal candidate set.
- Delta-comparison artifact.
- Geometry and mask stability diagnostics.
```

### Milestone

The solver correctly predicts the directional/ranking effect of selected rib-removal changes against Code_Aster, while preserving fixed interfaces.

## Phase 6 — Load basis and agent tools

### Backend

```text
- 16-case immersed response basis for one valid geometry.
- Superposition check.
- Robust reweighting and result policy.
- Agent tools for preview, run, compare, and verification request.
```

### UI

```text
- Load-basis sliders.
- Immersed-vs-Code_Aster comparison card.
- Agent fidelity/uncertainty language.
- Approval-based validation request.
```

### Milestone

A user can modify load mix, see no-resolve re-ranking for a fixed geometry, and have an agent propose—not automatically run—the next verification action.

## Phase 7 — Surrogate and multi-fidelity research

```text
- SDF/semantic-mask data schema.
- Immersed low-fidelity model or result corpus.
- Selected Code_Aster high-fidelity paired runs.
- Semantic metric correction model.
- Uncertainty calibration and out-of-distribution diagnostics.
- Agent policy for surrogate trust/verification.
```

### Milestone

The platform can state when a fast prediction is inside its measured trust region and when it requires a Code_Aster solve.

---

# 14. GB3 Immersed Solver Work Breakdown

## P0 — Freeze reference package

```text
Select:
- Canonical B-rep revision.
- Nominal 15-rib geometry.
- Material card.
- One simplified support/load fixture.
- Matched Code_Aster result.
- 10–20 semantic probes.

Store:
geometry, tessellation, FEM setup, loads, regions, probes,
Code_Aster outputs, manifest, hashes, versions.
```

**Gate:** clean environment reconstructs the same reference package.

## P1 — Boundary masks

```text
Implement:
- Mount/flange support region.
- Bearing-seat cylindrical load band.
- Required geometry selector engine.
- CAD/FEM mapping checks.
- Area/coverage/component diagnostics.
```

**Gate:** each semantic region visibly maps to the intended CAD region and known FEM reference region.

## P2 — SDF service

```text
Implement:
- Tessellation/BVH.
- Distance/sign query.
- Surface projection/normal.
- Narrow-band cache.
- Volume and sign diagnostics.
```

**Gate:** analytic tests pass; GB3 sign/volume behavior is documented.

## P3 — Immersed preview

```text
Implement:
- Cartesian grid.
- Cell classification.
- Subcell material-fraction estimate.
- Cut/unresolved visualization.
- Cost/memory estimator.
```

**Gate:** GB3 cavity/ribs/masks are represented visibly and reproducibly.

## P4 — Canonical solver validation

```text
Implement:
- Element matrices.
- Cut-cell quadrature.
- Penalty BC.
- Traction integration.
- Sparse solver.
- Reaction/residual/energy output.
```

**Gate:** analytic fixture and convergence results pass.

## P5 — GB3 Fixture A

```text
Run:
- 20 mm, 10 mm, feasible finer grid.
- Matched Code_Aster fixture.

Compare:
- forces/reactions;
- semantic-probe displacement;
- compliance/strain energy;
- broad displacement pattern.
```

**Gate:** meet predeclared research thresholds or return to preceding numerical phases.

## P6 — GB3 service-case translation

```text
Incrementally translate existing support/load setup.
Document equivalence and limitations per condition.
```

**Gate:** conditions are individually mapped and differences are never hidden in one aggregate score.

## P7 — Rib-topology study

```text
Candidates:
- baseline;
- minus one structurally relevant rib;
- minus one less influential rib;
- optional candidate addition;
- two-rib removal.
```

**Gate:** correct direction/ranking of selected engineering-relevant delta versus Code_Aster.

## P8 — Unit-load basis

```text
Solve 16 unit cases on one valid immersed geometry.
Verify direct service case versus superposition.
Store semantic response basis.
```

**Gate:** superposition is validated before UI reweighting is exposed.

---

# 15. API and Data Contracts to Lock Early

## Contract A — Capability registry

No UI hardcodes available artifacts, metrics, tools, renderers, or approval policies.

## Contract B — Artifact envelope

Every backend result is a renderable, provenance-carrying artifact.

## Contract C — Structured evidence

Evidence includes source artifact, locator, extraction method, state, confidence, timestamp, and entity relation. Evidence is not markdown prose.

## Contract D — Design Space Object

Every parameter is typed, versioned, bounded, source-linked, and solver-aware.

## Contract E — Metric semantics

Metric descriptors specify units, null behavior, direction, baseline, objective mode, robustness/noise policy, and valid renderers.

## Contract F — Exact approval binding

A consequential action approval binds to exact source/tool/arguments. Any change requires new preview and approval.

## Contract G — Fidelity and trust state

All fast-solver and surrogate results expose their intended use, diagnostics, comparison state, and escalation/verification requirement.

---

# 16. Testing Strategy

## Backend tests

```text
- Pydantic/API contract tests.
- Golden fixtures from GB3/reference corpus.
- Geometry/SDF primitive tests.
- Cell classification and quadrature tests.
- Canonical elasticity benchmark tests.
- Semantic BC mask coverage tests.
- Content-addressed cache tests.
- Approval mismatch/timeout/duplicate execution tests.
- Read-only role cannot mutate data.
- Objective/null/sign/baseline trap tests.
- Agent function-call and session evaluation tests.
```

## UI tests

```text
- Descriptor-driven rendering tests.
- Evidence state styling and accessibility tests.
- Selection synchronization across CAD/drawing/FEM.
- Ingest pass/SSE stream integration.
- Agent-card promotion to stage.
- Approval lifecycle integration.
- Visual regression for entity index, leaders, stage, diagnostics, and cards.
- End-to-end GB3 demo flow.
```

## Required end-to-end test

```text
Open GB3 workspace
→ inspect a mapped entity
→ inspect an assumed entity
→ preview immersed representation
→ ask an agent a question
→ promote response artifact
→ inspect fidelity/diagnostics
→ preview verification proposal
→ approve exact action
→ observe run/session/provenance update
```

---

# 17. Near-Term Sprint Plan

## Sprint A — Platform shell and contracts

### Backend

```text
- Implement /api/v1/capabilities.
- Define ArtifactEnvelope.
- Adapt one existing analysis response into envelope.
- Bind agent thread to workspace/session context.
```

### UI

```text
- Scaffold ui_agentic.
- Implement engineering-sheet tokens/shell.
- Build generic stage and agent rail.
- Render existing analysis artifact card and promote it.
- Add title-block provenance strip.
```

**Definition of done:** existing corpus/agent demo runs in the new platform shell.

## Sprint B — GB3 identity graph slice

### Backend

```text
- Artifact/pass model for prepared GB3 inputs.
- Entity/evidence/relation tables.
- Stable face IDs and CAD↔FEM slice.
- resolve-face endpoint.
```

### UI

```text
- Entity index.
- Evidence badges.
- CAD hover/selection and FEM cross-highlight.
- Named pass log.
```

**Definition of done:** CAD-to-FEM semantic hover works on real GB3 data.

## Sprint C — Immersed representation preview

### Backend

```text
- Reference package.
- Boundary masks.
- B-rep tessellation/SDF.
- Cartesian grid classification.
- Diagnostic preview endpoint.
```

### UI

```text
- Immersed stage.
- Grid/cut-cell/mask visualisation.
- Memory and resolution diagnostics.
```

**Definition of done:** GB3 can be viewed as a reproducible immersed representation with explicit limitations.

## Sprint D — Static solver fixtures

### Backend

```text
- Hex element/assembly.
- Cut-cell subcell quadrature.
- Penalty BC and traction integration.
- Canonical test suite.
```

**Definition of done:** physics fixtures converge before GB3 solve is attempted.

## Sprint E — GB3 Fixture A correlation

### Backend/UI

```text
- Matched simplified GB3 fixture.
- Grid refinement runs.
- Solver-comparison artifact/card.
- Verification request flow.
```

**Definition of done:** immersed results are credibly correlated for named GB3 metrics and visibly labeled screening fidelity.

---

# 18. Demo Narrative

## Act 0 — Artifact understanding

```text
Drop/open CAD, drawing, FEM setup.
Pass log shows what is parsed/cached/missing.
Coverage panel shows mapping and evidence gaps.
```

## Act 1 — Semantic trust

```text
Hover a bearing bore.
Show CAD identity, drawing callout, FEM binding, frozen status.
Hover outer skin.
Show assumed morphability and missing drawing evidence.
```

## Act 2 — Existing data intelligence

```text
Ask “Which design is best?”
System refuses a false singular winner where ties/noise make it unsupported.
Move load-basis slider.
Rankings change without a new solve.
```

## Act 3 — Immersed capability

```text
Ask “Can we remove this rib?”
Agent inspects evidence and allowed design state.
Preview SDF/background-grid representation.
Show cut cells, resolution, mask coverage, and cost.
Run screening or propose it.
```

## Act 4 — Verification and governance

```text
Show immersed delta relative to baseline.
State screening fidelity and any uncertainty.
Agent proposes exact Code_Aster verification action.
User approves.
Session records requirements, argument payload, evidence, approver, and run.
```

## Act 5 — Design-space authorship

```text
Ask “Can we do better?”
Agent finds current parameterization exhausted/limited.
It proposes a new parameter based on graph evidence and physics diagnostics.
User approves a versioned Design Space Object change.
New slider appears in the workspace.
```

Closing statement:

> “The system does not only optimize variables. It understands which variables exist, which are allowed, what evidence supports them, when the current parameterization has failed, and what must be verified before a proposed engineering change becomes trustworthy.”

---

# 19. Explicit Non-Goals and Guardrails

```text
- Do not claim a general replacement for Intact, nTop, or Code_Aster.
- Do not call an immersed screening field a certification result.
- Do not train a surrogate on unvalidated low-fidelity labels and call it high fidelity.
- Do not let an agent run remote campaigns autonomously.
- Do not allow agent prose to be the only evidence for a result.
- Do not hide missing drawing evidence behind complete-looking mappings.
- Do not hardcode GB3-specific plots, metrics, or workflow assumptions into ui_agentic.
- Do not start GPU, FSI, topology optimization, and generic multiphysics before static validation.
- Do not use an unverified peak stress at a sharp/unfilleted root as an optimization target.
- Do not sacrifice existing Code_Aster/morph/surrogate credibility milestones for an attractive meshless prototype.
```

---

# 20. Immediate First Tickets

1. Create `ui_agentic` product shell, design tokens, central stage, entity index, agent rail, and provenance strip.
2. Implement `/api/v1/capabilities` and frontend capability registry.
3. Implement universal `ArtifactEnvelope`; adapt one analysis endpoint and card renderer.
4. Add workspace/session IDs to the existing agent runtime and restore pinned artifacts/pending proposals.
5. Freeze `gb3_immersed_reference` fixture with hashes, material, one simple BC fixture, probes, and Code_Aster output.
6. Implement `BoundaryRegion` models and hand-author the first mount and bearing-seat masks with evidence links.
7. Implement B-rep tessellation/BVH, SDF sign/distance service, and primitive tests.
8. Implement Cartesian grid compiler and `/api/v1/immersed/preview` diagnostics.
9. Reuse viewer selection/highlight paths to render CAD, mask, cut-cell, and unresolved-feature overlays.
10. Implement canonical linear elasticity fixture suite before writing GB3-specific immersed solve logic.
11. Build a matched simplified GB3 Code_Aster Fixture A and establish predeclared comparison thresholds.
12. Only after static correlation, implement selected rib-removal screening and the agent-driven verification proposal.

---

# Final Decision

Build the immersed path as a **parallel, evidence-first R&D backend**, not as a rewrite of the present GB3 workflow.

```text
Near-term value:
Existing corpus + agent + design-space platform + Code_Aster validation.

New exploration capability:
SDF/immersed representation, topology screening, stable ML geometry context.

Long-term AI-native product:
Typed design space + semantic masks + multi-fidelity surrogate + agentic,
approval-gated engineering decisions.
```

The single unifying product object is the **Design Space Object**, not the mesh, the solver, the LLM, or the plot.
