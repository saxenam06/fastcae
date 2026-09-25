# fastCAD Updated Plan

## Purpose

Build a governed simulation-data factory that converts one trusted GRC gearbox-housing baseline into **100–200 qualified simulation records** for surrogate modeling and later autonomous exploration.

The immediate product is **not** a general CAD editor, a gearbox-specific rule tool, or an LLM that improvises geometry. It is a deterministic, traceable engineering workflow:

```text
Baseline CAD + solver model + engineering contract
→ protected functional core
→ automatically discovered structural anchor regions
→ structured reinforcement patterns
→ smooth implicit/GET geometry
→ deterministic qualification
→ mesh + FEA
→ qualified dataset
→ surrogate-guided next variants
```

---

## Core Design Decision

Do not try to learn how humans design gearboxes from one gearbox.

Instead, represent every problem using a reusable contract:

```text
Protected interfaces
+ keep-out volumes
+ designable material domain
+ load/support conditions
+ manufacturing constraints
+ generic structural anchors
+ generic material-addition/removal operators
+ simulation objectives
```

A gearbox is the first demonstration case. The same architecture can later apply to pump casings, e-motor housings, inverter enclosures, brackets, battery structures, and other constrained structural parts.

---

## Product Positioning

> fastCAD is a governed simulation-data and design-space discovery engine that converts one trusted engineering baseline into a qualified, physics-indexed family of feasible structural alternatives.

It should:

- Preserve functional geometry that must not change.
- Identify where structural modification is allowed and potentially useful.
- Generate controlled, diverse reinforcement alternatives.
- Reject invalid geometry before expensive simulation.
- Automate meshing, solver execution, result extraction, and provenance.
- Create training data for feasibility and performance surrogate models.
- Later use uncertainty-aware active learning to decide what to simulate next.

It should not initially:

- Learn a full latent distribution of gearbox designs from one housing.
- Rely on natural-language CAD modification.
- Allow AI to alter bearing seats, sealing faces, or other functional geometry.
- Treat smooth field geometry as automatically mesh-safe.
- Force every simulation candidate into editable feature-history CAD.

---

## System Architecture

```text
                         ┌─────────────────────────────┐
                         │ Engineer Design Contract     │
                         │ protected regions, loads,    │
                         │ process, goals, constraints  │
                         └──────────────┬──────────────┘
                                        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 1. Baseline Truth Layer                                          │
│ CAD B-rep + baseline mesh + validated FE model + result mapping  │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Protected-Core Layer                                          │
│ Preserve bores, bearing seats, mounting faces, seals, holes,     │
│ internal clearances, and interface-critical geometry             │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Structural Context Extraction                                 │
│ Patch segmentation + thickness + junctions + FEA fields +        │
│ flexible panels + candidate anchor regions                       │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Connection Discovery                                          │
│ Anchor compatibility graph + legal corridors + structural score  │
│ + symmetry hypotheses                                            │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. Variant Proposal                                              │
│ CP-SAT structured motif selection + GET/implicit smooth          │
│ ribs, webs, gussets, bands, and limited holes                    │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. Deterministic Qualification                                   │
│ Clearance + protected geometry + thickness + manufacturing +     │
│ connectivity + meshability + mass + duplicate rejection          │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. Meshing and CAE Factory                                       │
│ Geometry realization → mesh → solver → result extraction → QA    │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ 8. Dataset and Learning                                          │
│ Qualified records → surrogates → uncertainty/diversity sampling  │
│ → next simulation batch                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Engineering Design Contract

The Engineering Design Contract is the main product abstraction. It captures what geometry alone cannot safely infer.

```yaml
problem:
  objectives:
    - minimize_mass
    - minimize_peak_displacement
    - maximize_target_natural_frequency

baseline:
  geometry: grc_housing.step
  analysis_model: baseline_solver_deck.inp

protected:
  interfaces:
    - type: bearing_seat
      tolerance: 0.02_mm
    - type: mounting_face
      tolerance: 0.05_mm
    - type: sealing_surface
      tolerance: 0.02_mm
  keep_out_volumes:
    - shaft_clearance
    - gear_clearance
    - internal_oil_cavity
    - assembly_access

design_space:
  allowed_operations:
    - bridge
    - sheet
    - buttress
    - reinforce_band
    - relieve
  modification_domains:
    - exterior_shell
    - selected_internal_wall_regions
  material_budget:
    max_added_mass_percent: 12
    max_removed_mass_percent: 8
  symmetry:
    mode: discover_or_confirm

manufacturing:
  process: casting
  min_wall_thickness_mm: 4
  min_feature_spacing_mm: 6
  draft_constraints: enabled

analysis:
  load_cases:
    - static_mount_and_torque
    - modal
  acceptance:
    mesh_quality_threshold: defined
    protected_interface_deviation: defined
    solver_convergence: required
```

The contract is product-specific configuration, not product-specific platform code.

---

## Protected Functional Core

The protected core is exact geometry that must remain unchanged or stay within tightly defined tolerances.

For the GRC gearbox housing, protect:

- Bearing bores and bearing-seat cylinders.
- Bearing-seat axes and alignment.
- Shaft and gear clearance envelopes.
- Bolt holes.
- Mounting faces.
- Sealing surfaces and seal lands.
- Machined interfaces.
- Datum features.
- Internal oil, gear, and moving-part volumes.
- Assembly access zones.

Use this rule:

```text
Exact B-rep functional core
+ generated field reinforcement inside allowed regions
− keep-out volumes
= final candidate design
```

The system may attach reinforcement near a protected bearing interface, but never on or through the precision bore/seat surface itself.

---

## Structural Context Extraction

The system should not operate directly on manually selected CAD faces. It should derive meaningful **surface patches** and structural context from B-rep geometry and baseline FEA.

### Geometry context

Create a face-adjacency graph:

```text
Node = CAD face
Edge = shared CAD edge / adjacency relation
```

For each face or merged patch, compute:

- Surface type: planar, cylindrical, conical, freeform.
- Area and bounding dimensions.
- Surface normal and curvature.
- Local wall thickness.
- Face adjacency and junction topology.
- Edge convexity, concavity, and smoothness.
- Distance to protected geometry and keep-out volumes.
- Available attachment footprint.
- Distance to internal cavities and external envelopes.

Merge fragmented STEP/B-rep faces into higher-level patches such as broad wall panels, shell segments, boss neighborhoods, and wall junctions.

### Physics context

Project baseline FEA information to surface patches and/or a volume field:

- Static displacement.
- Von Mises stress.
- Principal stress directions.
- Strain-energy density.
- Compliance sensitivity or equivalent stiffness proxy.
- Modal displacement.
- Modal strain energy.
- Reaction-force neighborhoods.
- Relative motion of bearing-seat/interface regions.

Physics tells the system where structural changes may matter. Geometry and constraints tell it where changes are legal.

---

## Candidate Anchor Regions

An anchor is not necessarily one exact face. It is a permitted surface patch or volume zone where added material can join the existing structure.

### Initial Stage-1 anchor types

| Anchor class | Detection basis | Typical role |
|---|---|---|
| Stiff wall junction | Multiple connected walls, strong edge network, local thickness | Strong rib root/load-transfer source |
| Thick boss neighborhood | Cylindrical or raised feature with surrounding material | Attach reinforcement near bearing/bolt structures |
| Mount/support neighborhood | Near constrained faces, mount points, or reaction zones | Transfer support reaction into housing |
| Flexible shell panel | Broad, thin, highly deforming patch | Main stiffening destination |
| High strain-energy patch | Static or modal strain-energy field | High-value intervention region |
| Long unsupported span | Large panel between stiff boundaries | Candidate for web/rib support |
| Existing reinforcement root | Existing rib/web termination or junction | Extension or branching candidate |
| Symmetry counterpart | Geometric mirror or rotational counterpart | Supports structured mirrored patterns |

### Invalid anchor conditions

Reject a patch as an anchor when it is:

- On a protected, machined, sealing, or datum face.
- Inside an internal clearance/assembly keep-out volume.
- Too thin for a stable rib root.
- Too close to a bore, bolt hole, shaft, or gear cavity.
- Too small, fragmented, or curved for the required attachment footprint.
- Inaccessible for the specified manufacturing process.
- Likely to make a thick casting hot spot or inaccessible pocket.
- Too close to another proposed reinforcement member.

### Anchor representation

```yaml
anchor:
  id: anchor_104
  patch_id: patch_21
  center: [x, y, z]
  normal: [nx, ny, nz]
  footprint: boundary_or_local_surface_parameterization
  local_wall_thickness_mm: 8.1
  distance_to_keepout_mm: 14.4
  stiffness_score: 0.84
  flexibility_score: 0.16
  strain_energy_score: 0.63
  manufacturing_score: 0.91
  attachment_allowed: true
  role: stiff_source
```

---

## Connection Discovery

Build an **anchor compatibility graph**.

```text
Node = valid anchor patch
Edge = a feasible candidate structural connection
```

A candidate connection should pass the following tests before it becomes available to the generator.

### Geometric feasibility

- Both anchors have sufficient attachment area.
- A connecting corridor exists between them.
- The corridor remains inside the permitted design domain.
- The provisional connector does not intersect protected geometry.
- The provisional connector does not invade clearance, oil, gear, shaft, bolt-access, or assembly volumes.
- The path permits minimum rib thickness and root radius.

### Structural usefulness

Prefer connections that:

- Join a stiff/support/load-carrying region to a flexible panel.
- Shorten a long unsupported bending span.
- Follow a principal deformation or stress direction.
- Connect a high modal-strain-energy region to a stiff boundary.
- Improve a plausible load-transfer route.
- Produce balanced/symmetric stiffening where symmetry is required.

### Manufacturing and mesh feasibility

- Minimum thickness is satisfied.
- Minimum spacing is satisfied.
- Draft constraints are satisfied where required.
- Root blends are viable.
- No near-tangent contacts or sliver regions are created.
- The field geometry can be converted into a clean analysis surface and volume mesh.

### Example gearbox connection

```text
Outer material surrounding protected bearing-seat envelope
                         ↓
              stiff wall junction / mount neighborhood
                         ↓
               flexible outer housing sidewall panel
```

The protected bearing cylinder is never used as the attachment face. The outer material around its keep-out envelope is an anchor candidate.

---

## Generic Structural Operators

The platform should use a small reusable operator library rather than gearbox-specific commands.

| Operator | Generic purpose | Common physical form |
|---|---|---|
| Bridge | Connect two compatible anchor regions | Rib, strut, diagonal brace |
| Sheet | Span a loop or multiple anchors | Web, diaphragm, bulkhead |
| Buttress | Support a local interface/junction toward a target | Gusset, rib foot |
| Reinforce band | Add distributed stiffening along a direction/field | Rib array, bead, stiffener band |
| Relieve | Remove low-utility material while retaining rules | Pocket, lightening hole |
| Morph | Smoothly alter an allowed region | Wall thickening, bulge, transition |
| Repeat/reflect | Transform a valid intervention | Mirrored/radial pattern |

A gearbox rib is therefore a geometric realization of a generic `bridge` or `buttress` operation.

---

## CP-SAT Pattern Selection

Keep CP-SAT as the **discrete layout and feasibility engine**.

CP-SAT decides:

- Which anchor pairs receive a connector.
- Number of connectors.
- Which structural motif is used.
- Spacing and non-overlap.
- Symmetry/mirroring.
- Added-mass budget.
- Pattern complexity.
- Optional holes or relief features.
- Rule-based aesthetic/organization constraints.

It should generate structured motif families such as:

```text
Single diagonal bridge
Mirrored diagonal pair
Parallel bridge pair
Fan from a stiff junction
Wide web across a flexible span
Closed-frame support
Rib network plus limited relief feature
```

The key update is that CP-SAT selects from the **automatically discovered anchor graph**, not from a manually maintained gearbox face list.

---

## GET / Implicit Geometry Role

Use GET or an equivalent smooth implicit field method to create the detailed reinforcement geometry after CP-SAT chooses a structural layout.

```text
CP-SAT chooses anchor connections and pattern
→ GET creates smooth connector components
→ field is clipped to allowed design region
→ keep-out volumes are subtracted
→ geometry is qualified, meshed, and simulated
```

### GET connector inputs

```yaml
connector:
  anchor_A: anchor_104
  anchor_B: anchor_283
  connection_role: stiff_to_flexible
  center: [x, y, z]
  orientation: [qx, qy, qz, qw]
  length_mm: 85
  width_mm: 6
  height_mm: 24
  taper: 0.35
  root_blend_mm: 4
  component_count: 1
  symmetry_group: mirror_xy
```

### Parameters to vary automatically

- Start/end positions inside each anchor footprint.
- Connector center.
- Orientation.
- Span length.
- Width/thickness.
- Height/depth.
- Taper.
- Curvature.
- Root-blend extent.
- Number of components.
- Component overlap.
- Field amplitude/threshold.
- Symmetry transform.

From one anchor pair, generate alternatives such as:

```text
Thin diagonal rib
Thick tapered rib
Two parallel ribs
Wide web
Curved brace
Fan-shaped support
Mirrored rib pair
```

### GET and MMC roles

| Method | Recommended role |
|---|---|
| CP-SAT | Feasible, diverse, organized discrete structural layout |
| GET / implicit field | Smooth geometry realization and local continuous variation |
| Exact B-rep core | Preserve bearing bores, seats, mounting/sealing interfaces |
| MMC | Later local refinement, CAD-oriented component optimization, or comparison method |

Do not make MMC the immediate replacement for CP-SAT. MMC is useful later for refining promising local layouts, but CP-SAT remains the fastest way to obtain broad, structured dataset diversity.

---

## Geometry Realization and Meshing

For the Stage-1 simulation-data factory, do not require a fully editable CAD feature tree for every variant.

Use the trusted analysis pathway:

```text
Exact protected B-rep core
+
GET / implicit reinforcement in valid design domain
−
protected keep-out volumes
→
watertight analysis surface
→
conforming volume mesh
→
FEA
```

Only selected high-value candidates need conversion to STEP/B-rep or conventional parametric CAD reconstruction.

### Mandatory qualification before solver launch

- Protected-interface tolerance check.
- Clearance and keep-out collision check.
- Minimum wall/rib thickness check.
- Root-attachment and connectivity check.
- Self-intersection check.
- Manufacturability/draft/spacing check.
- Minimum feature-size check.
- Surface manifold/watertightness check.
- Surface-mesh quality check.
- Tetrahedral-mesh quality check.
- Mass-budget check.
- Duplicate/near-duplicate design rejection.

Smooth geometry is valuable, but it is not automatically simulation-ready. A smooth shape can still contain narrow gaps, tiny features, near-tangent contacts, poor local element quality, or bad transitions into the protected core.

---

## Milestones

## M0 — Baseline Truth

**Goal:** establish one reproducible trusted reference case.

Deliverables:

- Original GRC CAD ingestion and topology audit.
- Reproducible baseline mesh.
- Validated static and modal solver setup.
- Surface/mesh/result correspondence map.
- Baseline displacement, stress, modal, and bearing-seat metrics.
- Versioned baseline record.

Acceptance criteria:

- Automated reruns reproduce baseline outputs within agreed tolerance.
- Mesh and solver launch without manual intervention.
- Functional/interface response metrics are extracted consistently.
- All inputs, tool versions, and outputs have provenance.

## M1 — Protected Core and Design Domain

**Goal:** define where geometry can and cannot evolve.

Deliverables:

- Protected B-rep entity registry.
- Tolerance envelopes around protected interfaces.
- Keep-out volumes for internal and assembly regions.
- Allowed reinforcement volumes.
- Manufacturing and minimum-feature constraints.
- Boolean/clipping regression tests.

Acceptance criteria:

- No generated material can enter protected regions.
- Critical cylinders, bores, seats, and faces retain required geometry.
- Any violation is deterministically rejected before meshing.

## M2 — Structural Context and Anchors

**Goal:** replace manual rib-host selection with automatic candidates.

Deliverables:

- B-rep face-adjacency graph.
- Patch segmentation.
- Thickness and junction analysis.
- Flexible-panel extraction.
- FEA field projection to patches.
- Initial five anchor classes.
- Anchor confidence/ranking scores.
- Visualization and engineer review UI.

Acceptance criteria:

- At least 20–50 plausible candidate anchor patches are proposed.
- No downstream logic relies on hardcoded gearbox face IDs.
- Engineer can lock/reject a small number of uncertain regions.

## M3 — Connection Graph and CP-SAT Motifs

**Goal:** generate structured, meaningful reinforcement layouts.

Deliverables:

- Anchor compatibility graph.
- Collision-free corridor detection.
- Connection scoring.
- Pattern templates: diagonal, parallel, fan, web, mirrored pair.
- CP-SAT constraint model for non-overlap, symmetry, mass, and complexity.
- Diversity sampler.

Acceptance criteria:

- Generate 100+ distinct candidate layouts.
- Reject invalid connections before geometry creation.
- Produce organized pattern families rather than arbitrary scattered ribs.
- Cover multiple plausible load-transfer concepts.

## M4 — GET / Implicit Reinforcement Geometry

**Goal:** realize selected layouts as smooth structural geometry.

Deliverables:

- Tapered smooth bridge primitive between anchor patches.
- Sheet/web and buttress primitives.
- Field union, clipping, and keep-out subtraction.
- Root blend and feature-size controls.
- Geometry QA and analysis-surface preparation.

Acceptance criteria:

- Geometry is smooth, connected, and reproducible.
- Protected geometry remains untouched.
- 60–80% or more of qualified layouts should produce meshable candidates after calibration.

## M5 — Simulation Data Factory

**Goal:** create the first qualified dataset.

Deliverables:

- Automated meshing and solver-deck preparation.
- Static and modal batch execution.
- Result/KPI extraction.
- Failure classification and retry policy.
- Immutable record storage and campaign dashboard.
- Batch scheduling and provenance capture.

Store for every candidate:

```text
baseline ID
Design Contract version
protected-core version
anchor patches
connection graph
CP-SAT pattern
GET parameters
geometry hash
mesh diagnostics
solver inputs
solver outputs
KPIs
qualification status
failure mode, if applicable
software versions and timestamp
```

Acceptance criteria:

- 100–200 accepted, comparable, traceable records.
- Rejected candidates are retained with explicit failure labels.
- Every accepted variant can be regenerated and rerun from stored provenance.

---

## Dataset Plan

Do not begin with thousands of random designs.

| Batch | Purpose | Target quantity |
|---|---|---:|
| Baseline | Reference truth and repeatability | 1–5 |
| Calibration | Validate geometry, mesh, and constraints | 20–30 |
| Pattern coverage | Cover motif and parameter families | 40–60 |
| Physics coverage | Explore different likely load paths | 40–60 |
| Focused refinement | Densify promising/uncertain regions | 30–50 |

Target: **about 130–200 qualified records**, plus a separately stored collection of rejected and failed records.

Vary deliberately:

- Connection topology.
- Rib count.
- Orientation.
- Thickness and height.
- Taper and root blend.
- Symmetry.
- Added mass.
- Stiff anchor source.
- Flexible-panel target.
- Load-path family.
- Relief/hole policy where allowed.

---

## Metrics to Store

For each qualified design, store:

- Total mass and mass delta.
- Maximum displacement.
- Stress percentile and peak stress.
- Target natural frequencies.
- Mode-shape correlation where relevant.
- Bearing-seat translation.
- Bearing-seat tilt/axis misalignment.
- Mount-interface deformation.
- Local strain-energy changes.
- Mesh-quality metrics.
- Solver convergence status.
- Constraint and manufacturing checks.
- Generation and simulation runtime.

For rejected designs, store the exact reason:

- Protected-core intrusion.
- Clearance violation.
- Insufficient thickness.
- Non-manifold geometry.
- Failed mesh.
- Solver non-convergence.
- Excess stress/displacement.
- Duplicate design.

Failures are valuable supervised labels for future feasibility models.

---

## AI and Agent Roles

## Stage 1: deterministic tools first

Use rules, geometry algorithms, CP-SAT, and FEA to establish trust.

The workflow agent may:

- Start and monitor campaigns.
- Call geometry extraction, pattern generation, qualification, meshing, and solver tools.
- Retry known failure modes within approved bounds.
- Capture provenance and campaign state.
- Flag ambiguous functional regions for engineering review.
- Report coverage, throughput, and failure patterns.

The workflow agent must not:

- Alter protected geometry.
- Relax hard constraints silently.
- Declare mesh or solver validity without deterministic evidence.
- Replace explicit engineering contracts.

## After the initial dataset

Train models in this order:

1. Feasibility classifier: geometry/mesh/solver success probability.
2. Scalar surrogate: mass, displacement, stress, frequency, misalignment.
3. Uncertainty estimator.
4. Candidate ranking model for anchor pairs and GET parameters.
5. Graph/field surrogate conditioned on load and intervention representation.
6. Active-learning policy for next-batch selection.

Use the surrogate to prioritize candidates according to:

```text
Expected performance improvement
+ predictive uncertainty
+ dataset diversity
− predicted failure risk
```

Do not initially train a full generative CAD model or a latent gearbox-design model from one housing.

---

## Definition of Geometry Agnostic

The system is geometry-agnostic when its core language is:

```text
Protected interface
Keep-out region
Designable volume
Anchor patch
Anchor compatibility
Connection corridor
Material-addition operator
Material-removal operator
Manufacturing rule
Load/support field
Simulation metric
Qualification result
```

It is not geometry-agnostic if it contains hardcoded logic such as:

```text
gearbox_bearing_boss_to_sidewall_rib()
GRC_housing_face_82()
gearbox_left_wall_pattern()
fixed_gearbox_rib_angle()
```

The gearbox maps into the generic framework as follows:

| Gearbox-specific concept | General platform concept |
|---|---|
| Bearing seat | Protected cylindrical interface |
| Material around bearing seat | Candidate anchor neighborhood |
| Gearbox sidewall | Flexible designable shell patch |
| Mounting flange | Support-interface neighborhood |
| Rib | Smooth material connector / bridge |
| Rib array | Reinforcement-band pattern |
| Gearbox symmetry | Confirmed geometric transformation |

---

## Immediate Next Actions

1. Freeze the Stage-1 objective: 100–200 qualified housing simulation records.
2. Write and version the GRC Engineering Design Contract.
3. Complete M0 baseline geometry, mesh, and solver truth.
4. Implement protected-core and keep-out logic before new generators.
5. Implement basic B-rep patch segmentation and the initial five anchor classes.
6. Project static and modal FEA fields to the detected patches.
7. Build the anchor compatibility graph.
8. Refactor CP-SAT around generic anchors and structured motifs.
9. Implement one GET primitive: a tapered smooth bridge between two valid anchor patches.
10. Establish the protected-core + implicit-reinforcement meshing route.
11. Generate 20–30 calibration variants.
12. Fix geometry, mesh, and solver failure modes before scaling.
13. Run the 100–200 variant campaign.
14. Train first feasibility and scalar-performance models.
15. Add active learning and agent-selected campaigns only after the deterministic pipeline is reliable.

---

## Final Architecture Statement

```text
Exact protected B-rep core
+
automatic structural context and anchor discovery
+
CP-SAT structured reinforcement-pattern selection
+
GET / implicit smooth reinforcement realization
+
deterministic qualification
+
automated meshing and FEA
+
qualified simulation dataset
+
surrogate-guided exploration
```

This plan preserves the strongest parts of the current work: CP-SAT diversity, field-generated smooth ribs, protected functional interfaces, and simulation-driven dataset generation. It reduces manual CAD interaction and gearbox-specific hardcoding while keeping the engineering controls required for trustworthy structural exploration.
