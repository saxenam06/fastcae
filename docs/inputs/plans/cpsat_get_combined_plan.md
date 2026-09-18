# CP-SAT + GET Combined Plan for Gearbox Housing Design-Space Discovery

## Plain Summary

The combined architecture has two levels:

```text
CP-SAT = selects a feasible, organized design experiment
GET    = discovers the smooth structural material pattern inside it
FEA    = determines whether the generated design actually performs well
```

CP-SAT does **not** disappear, and it should not be reduced to selecting individual anchors. Your existing CP-SAT rib/hole-pattern work remains valuable.

The update is that CP-SAT moves upward from only selecting local rib/hole placements to defining a controlled **design-space configuration**:

- Which housing zones are allowed to evolve.
- Which zones must be mirrored.
- Which holes may exist.
- How much material can be added or removed.
- Which protected interfaces must remain unchanged.
- Which structural regions should have a material connection.
- Which pattern complexity and manufacturing constraints apply.

GET then uses the CP-SAT-selected design volume and constraints to discover the detailed smooth structural shape: ribs, webs, braces, gussets, bands, or merged reinforcement networks.

---

## Objective

Create a governed simulation-data factory for the GRC gearbox housing that produces approximately **100–200 qualified simulation records**.

Each record must contain:

```text
trusted baseline reference
+ protected functional geometry
+ a versioned design-space configuration
+ generated reinforcement/relief geometry
+ geometry and mesh qualification result
+ solver inputs and outputs
+ structural/NVH performance metrics
+ complete provenance
```

The objective is not to learn a full gearbox-design distribution from one housing. The objective is to create a **physics-informed local design space** around one trusted housing while preserving critical functional interfaces.

---

## The Three Responsibilities

| Layer | Main question | Output |
|---|---|---|
| Engineering Contract | What must be preserved, what loads/process/targets apply? | Protected geometry, keep-outs, objectives, limits |
| CP-SAT | What legal and organized class of experiment should be explored? | Selected zones, symmetry, budget, hole policy, connectivity rules |
| GET | What smooth material distribution performs best inside this allowed space? | Smooth topology: ribs, webs, braces, gussets, material bands |
| FEA | Is the candidate valid and how well does it perform? | Stress, displacement, modes, mass, interface motion, pass/fail |

---

## High-Level Workflow

```text
Validated baseline gearbox CAD + FEA
              ↓
Protect functional core:
bores, seats, bolts, mounts, seals, gear/shaft/oil/assembly clearances
              ↓
Define candidate exterior/interior design zones
              ↓
CP-SAT selects a feasible organized configuration:
active zones + symmetry + material budget + holes + connectivity + rules
              ↓
GET performs smooth topology/material discovery inside selected zones
              ↓
Clip generated material to permitted domain and subtract keep-outs
              ↓
Deterministic geometry qualification
              ↓
Mesh + static/modal FEA
              ↓
Store qualified record, or store a labeled failure record
              ↓
Later: train surrogate and select the next experiments
```

---

## 1. Baseline Truth Layer

Start with a completely reproducible reference model.

Inputs:

- Original GRC gearbox housing geometry.
- Existing mesh or reproducible mesh recipe.
- Static load/support case.
- Modal analysis case.
- Material properties.
- Solver deck/template.
- Baseline expected results.

Store baseline metrics:

- Mass.
- Maximum displacement.
- Stress metrics.
- Target natural frequencies.
- Mode shapes.
- Bearing-seat translation.
- Bearing-seat axis tilt/misalignment.
- Mount-interface deformation.
- Mesh quality and solver status.

No variant generation should start before this baseline can be rerun automatically and compared reliably.

---

## 2. Protected Functional Core

Separate the housing into immutable functional geometry and allowed design space.

### Protect exactly

For the gearbox, protect:

- Bearing bores and bearing-seat cylinders.
- Bearing-seat axes, diameters, and fit surfaces.
- Bolt holes and bolt access zones.
- Mounting faces.
- Sealing faces and seal lands.
- Machined datum surfaces.
- Gear and shaft clearance volumes.
- Oil cavity / internal fluid volumes where required.
- Assembly envelopes.

### Build keep-out volumes

Every protected feature gets a tolerance and a surrounding buffer volume.

```text
Protected bore surface
+ geometric tolerance
+ assembly/manufacturing clearance
= bore keep-out volume
```

Generated material may attach near a protected region, but it must never alter or invade it.

### Hybrid representation

Use:

```text
Exact B-rep functional core
+
GET-generated smooth reinforcement in allowed domains
−
keep-out volumes
=
final simulation candidate
```

This protects analytic bearing cylinders and other interface-critical geometry while retaining field-based smooth design freedom in non-critical regions.

---

## 3. Candidate Design Zones

GET needs a volume in which material is allowed to evolve. The system therefore creates a set of possible design zones around the housing.

Examples:

```text
Z1 = left external sidewall reinforcement zone
Z2 = right external sidewall reinforcement zone
Z3 = upper housing wall / top bridge zone
Z4 = mount-to-sidewall structural corridor
Z5 = outer material around bearing-support region
Z6 = lower wall/junction reinforcement zone
Z7 = selected internal wall region, if accessible and permitted
Z8 = possible relief-hole/void zone
```

These are not gearbox-specific code primitives. They are configuration instances of generic concepts:

```text
Designable shell region
Designable volume
Structural corridor
Interface neighborhood
Flexible-panel zone
Relief/void zone
```

### How zones are proposed

Use CAD geometry plus baseline FEA to identify:

- Broad thin wall panels.
- Stiff wall junctions.
- Thick material near bosses or interfaces.
- Mount/support neighborhoods.
- High displacement regions.
- High static or modal strain-energy regions.
- Long unsupported wall spans.
- Symmetric counterpart regions.

The engineer reviews and confirms the final allowed zones in Stage 1.

---

## 4. CP-SAT Role: Design-Space Configuration Generator

CP-SAT remains the principal **discrete feasibility, organization, and diversity engine**.

It does not need to create final ribs directly. It defines the experiment that GET will solve.

### CP-SAT chooses

- Active design zones.
- Inactive design zones.
- Symmetry mode.
- Allowed material-addition budget.
- Allowed material-removal budget.
- Enabled/disabled hole or relief zones.
- Number and organization of allowed voids.
- Required material connectivity between selected region groups.
- Feature-count limit.
- Structural complexity limit.
- Manufacturing rules.
- Pattern family / high-level motif constraints.
- Objective emphasis for the GET run.

### Example CP-SAT configuration A

```yaml
configuration_id: cfg_A
active_zones: [Z1, Z2]
symmetry: mandatory_mirror
added_volume_budget: 8_percent
relief_holes: disabled
required_connectivity:
  - left_stiff_junction_to_left_flexible_panel
  - right_stiff_junction_to_right_flexible_panel
objective_emphasis: first_bending_mode
```

Interpretation:

> Explore a symmetric reinforcement design in the left and right sidewall zones. Do not create holes. Add no more than 8% material. Ensure that each flexible sidewall receives a continuous structural path from a stiff local junction. Improve the first bending mode.

### Example CP-SAT configuration B

```yaml
configuration_id: cfg_B
active_zones: [Z4, Z5]
symmetry: none
added_volume_budget: 6_percent
relief_holes:
  enabled: true
  max_count: 2
  organization: aligned_or_mirrored
required_connectivity:
  - mount_neighborhood_to_bearing_support_neighborhood
objective_emphasis: static_stiffness_to_mass
```

Interpretation:

> Explore material around the mount-to-bearing corridor. No symmetry is required. Allow up to 6% added material and up to two controlled relief holes. Ensure at least one structural load-transfer path between mount and bearing-support outer material. Improve static stiffness per unit mass.

### Example CP-SAT configuration C

```yaml
configuration_id: cfg_C
active_zones: [Z1, Z3, Z4, Z6]
symmetry: partial
added_volume_budget: 10_percent
relief_holes:
  enabled: true
  max_count: 4
  organization: row_or_mirror_pair
complexity_limit:
  max_connected_reinforcement_groups: 3
objective_emphasis: combined_static_and_modal
```

Interpretation:

> Explore a broader but still controlled reinforcement family. Allow partial symmetry and a limited organized hole pattern. Limit the final result to three connected reinforcement groups to avoid an overly complex or random design.

### Why this improves your current CP-SAT patterns

Your earlier CP-SAT generation produced geometrically feasible rib/hole combinations but sometimes visually unorganized or mechanically weak patterns.

The improvement is to add grammar-like constraints such as:

```text
Mirror selected zones when symmetry is mandatory.
Mirror hole patterns when symmetry is mandatory.
Use only approved hole organization classes: row, ring, grid, mirrored pair.
Limit the number of active reinforcement zones.
Require selected zones to support a declared load-transfer purpose.
Limit isolated material islands.
Limit total feature count.
Limit material addition/removal.
Use minimum feature separation.
Avoid relief holes near interface buffers or expected rib-root regions.
Require a continuous material path for selected connectivity requirements.
```

CP-SAT therefore still creates diverse patterns, but now it creates **organized high-level structural experiment configurations**, not arbitrary independent rib/hole placements.

---

## 5. GET Role: Smooth Topology Discovery

GET receives a selected CP-SAT configuration and performs the continuous structural design step.

GET inputs:

```text
Selected active design zones
Exact non-design/protected core
Keep-out volumes
Boundary conditions and loads
Objective function
Added-material or volume budget
Minimum feature size
Manufacturing constraints
Symmetry requirement
Optional connectivity constraints
```

GET then discovers the smooth material distribution inside the selected design domain.

GET may produce:

- One or multiple ribs.
- Wide web-like material.
- Curved braces.
- Tapered supports.
- Gussets.
- Material bands.
- Merged reinforcement networks.
- Smooth local wall thickening.
- Smooth transition from a structural corridor into a flexible panel.

GET is not instructed to make a particular rib. It is instructed to improve an engineering objective while obeying the CP-SAT-defined domain and rules.

### Conceptual GET representation

GET represents material using a collection of anisotropic Gaussian components. Their position, orientation, length, width, height, and overlap are adjusted so their combined field forms smooth geometry.

```text
Small Gaussian near a junction      → local gusset
Long narrow Gaussian                → rib/brace
Long broad Gaussian                 → web
Multiple overlapping Gaussians      → curved or branching reinforcement network
```

This is why GET is useful: it can discover a smooth material topology rather than only instantiating predefined CAD rib features.

---

## 6. Combined CP-SAT + GET Example

### Housing setup

```text
Protected:
- Bearing bores/seats
- Bolt holes
- Mount faces
- Seal faces
- Gear/shaft/oil clearance

Candidate zones:
- Z1 left flexible sidewall
- Z2 right flexible sidewall
- Z3 upper wall
- Z4 mount-to-sidewall corridor
- Z5 bearing-support exterior neighborhood
```

### CP-SAT output

```text
Use zones: Z1, Z2, Z4, Z5
Symmetry: mandatory for Z1/Z2
Material budget: 8% added material
Holes: no holes in this experiment
Connectivity: mount neighborhood ↔ bearing-support exterior neighborhood
Objective: maximize first mode while limiting mass
```

### GET operation

GET receives the union of Z1, Z2, Z4, and Z5 as its permitted design volume.

It sees the actual gearbox load/support conditions and baseline response.

Within that allowed volume, GET may discover:

```text
- A smooth diagonal support from mount corridor into left sidewall.
- Its mirrored counterpart on the right.
- A wide tapered material band near the bearing-support exterior.
- A smooth merged transition instead of four separate predefined ribs.
```

### Validation

```text
Clip GET result to allowed design volume.
Subtract all keep-out volumes.
Check no protected geometry moved.
Check minimum wall thickness and manufacturability.
Generate analysis mesh.
Run static and modal FEA.
Store KPIs and accept/reject result.
```

---

## 7. Important Clarification: CP-SAT Does Not Become Unnecessary

There are two practical modes.

### Mode A: Current CP-SAT-first dataset generation

```text
CP-SAT directly selects organized rib/hole pattern variables
→ existing smooth field generator creates the geometry
→ mesh and FEA
```

Use this immediately if it is already producing valid smooth geometry reliably.

Improve CP-SAT with:

- Pattern motifs.
- Symmetry constraints.
- Shared source/target region rules.
- Spacing rules.
- Hole organization rules.
- Local feature-count limits.
- Physics-informed preference scores.

### Mode B: CP-SAT + GET two-level discovery

```text
CP-SAT selects active design zones, budgets, symmetry,
hole policies, connectivity, and objective emphasis
→ GET finds the smooth topology in those zones
→ mesh and FEA
```

Use this to discover structural archetypes that predefined rib-pattern variables may miss.

### Recommended hybrid strategy

```text
1. Keep CP-SAT + your present smooth field workflow for broad variation.
2. Add stronger symmetry and pattern-organization constraints.
3. Run GET on a smaller number of diverse CP-SAT-selected design-space configurations.
4. Treat GET outputs as new discovered structural archetypes.
5. Encode successful GET archetypes as new CP-SAT motif families.
6. Generate many controlled variants around those motifs.
7. Use FEA results to train feasibility/performance surrogates.
```

This avoids running expensive full GET topology optimization for every one of thousands of simulations.

---

## 8. Geometry and Meshing Strategy

Use a hybrid representation.

```text
Exact B-rep protected core
+
GET/implicit generated reinforcement
−
protected and clearance keep-outs
→
conforming analysis mesh
→
FEA
```

Do not require full editable CAD reconstruction for every candidate.

### Simulation-stage outputs

For every variant, retain:

- Exact protected baseline B-rep reference.
- Design-domain definition.
- CP-SAT configuration.
- GET parameters/field definition.
- Resulting watertight analysis surface/mesh.
- Solver deck.
- FEA results.
- Qualification status.

### Selected-best-design outputs

Only for high-performing candidates, invest in:

- STEP/B-rep conversion.
- CAD feature reconstruction.
- Manufacturing review.
- Detailed local design refinement.

### Qualification gate

Before expensive solver execution, reject variants with:

- Protected-interface intrusion.
- Clearance collision.
- Insufficient thickness.
- Small gaps or near-tangent geometry.
- Disconnected material islands.
- Non-manifold/watertightness failure.
- Manufacturing-rule violation.
- Surface mesh failure.
- Tetrahedral mesh failure.
- Excessive mass or duplicate geometry.

Smooth implicit geometry is helpful, but smoothness alone does not guarantee meshability or engineering validity.

---

## 9. Dataset Campaign Plan

Do not launch thousands of random designs at the beginning.

| Batch | Purpose | Target |
|---|---|---:|
| Baseline repeatability | Establish reference truth | 1–5 |
| Geometry calibration | Test clipping, smoothing, meshing, and protected-core preservation | 20–30 |
| CP-SAT pattern coverage | Cover symmetric/asymmetric configurations, budgets, hole policies | 40–60 |
| GET archetype discovery | Run GET in diverse selected design-space contracts | 10–30 |
| Pattern refinement | Generate CP-SAT variations around promising GET archetypes | 40–70 |
| Focused learning batch | Add simulations where surrogate uncertainty is high | 20–50 |

Initial target: **100–200 accepted records**, plus all rejected and failed records stored with explicit labels.

### Metrics to store

- Mass and added/removed mass.
- Maximum displacement.
- Stress metrics.
- Target natural frequencies.
- Modal behavior indicators.
- Bearing-seat translation and angular misalignment.
- Mount-interface deformation.
- Mesh quality.
- Solver convergence.
- Runtime.
- Constraint violations.
- CP-SAT configuration.
- GET parameterization and geometry hash.

---

## 10. AI and Agent Roadmap

### Stage 1: deterministic workflow

Use deterministic geometry rules, CP-SAT, GET, meshing, and FEA.

The workflow agent may:

- Start and track simulation campaigns.
- Select the next prepared configuration.
- Execute geometry generation, qualification, meshing, and solver tools.
- Retry known failures inside pre-approved parameter bounds.
- Preserve provenance.
- Report data coverage and failure distributions.
- Ask an engineer to confirm uncertain protected zones or symmetry assumptions.

The agent must not silently modify protected interfaces, override hard constraints, or declare simulation validity without deterministic checks.

### After the first dataset

Train:

1. Feasibility classifier: predict geometry/mesh/solver success.
2. Scalar surrogate: predict mass, stress, displacement, frequency, and misalignment.
3. Uncertainty estimator.
4. Ranking model: choose useful CP-SAT configurations and GET starting conditions.
5. Active-learning policy: select simulations balancing performance improvement, uncertainty, diversity, and failure risk.

Do not start by training a full CAD generative model from one housing.

---

## 11. Stage Milestones

## M0 — Baseline Truth

- Reproducible original CAD, mesh, solver, and result pipeline.
- Baseline static/modal KPIs.
- Interface-motion extraction.
- Provenance storage.

## M1 — Protected Core

- Protected entity registry.
- Keep-out volume generation.
- Allowed design-domain specification.
- Regression tests proving protected geometry cannot be modified.

## M2 — Candidate Zones

- B-rep patch segmentation.
- Thickness and junction analysis.
- Baseline FEA field mapping.
- Candidate zone proposals.
- Engineer confirmation workflow.

## M3 — Better CP-SAT Grammar

- Zone activation variables.
- Symmetry rules.
- Hole organization rules.
- Connectivity requirements.
- Material/complexity budgets.
- Diverse configuration generation.

## M4 — GET Integration

- Translate a CP-SAT configuration into GET domain, constraints, and objectives.
- Smooth topology generation inside selected zones.
- Clip/protect/qualify generated geometry.
- Meshing reliability experiments.

## M5 — Dataset Factory

- Campaign orchestration.
- Automated batch meshing and FEA.
- Accepted/rejected record schemas.
- First 100–200 qualified variants.

## M6 — Learning and Active Exploration

- Feasibility and KPI surrogates.
- Diversity/uncertainty campaign selection.
- Agentic orchestration over trusted tools.

---

## Final Statement

```text
CP-SAT does not merely choose anchors.

CP-SAT defines structured, feasible, diverse design-space experiments:
which zones, which symmetry, which hole policy, which budget,
which connectivity, and which complexity/manufacturing rules.

GET then performs genuine smooth structural discovery inside
that CP-SAT-defined permitted space.

FEA validates every result and produces the dataset.
```

The final architecture is:

```text
Exact protected B-rep core
+
CP-SAT organized design-space contracts
+
GET smooth topology discovery in selected domains
+
deterministic geometry/mesh qualification
+
automated static and modal FEA
+
qualified simulation data
+
later surrogate-guided active exploration
```
