# GRC GB3 Immersed / Meshing-Free FEA Implementation Plan

## Decision

Implement a **GB3-specific immersed-grid structural-analysis prototype** that achieves the useful architectural properties of Intact.Simulation’s public approach:

- Geometry may change without generating a body-fitted tetrahedral mesh.
- The solver works from a B-rep-derived signed-distance field (SDF) and semantic boundary masks.
- Rib presence, removal, placement, and eventually implicit topology changes modify geometry occupancy rather than FEM connectivity.
- Structural results are produced on a fixed Cartesian/octree background discretisation.
- The initial solver is explicitly an **exploration-fidelity backend** and is correlated against the existing Code_Aster pipeline before it informs decisions or surrogate labels.

This is not a plan to copy Intact’s proprietary Immersed Method of Moments implementation. It is a plan to build a technically defensible immersed/cut-cell FEM prototype for the GRC GB3 housing using independently implemented methods: a B-rep/SDF geometry adapter, Cartesian background grid, adaptive subcell quadrature, explicit boundary masks, sparse linear elasticity, and measured convergence/correlation gates.

## Why GB3 is the right fixture

GB3 exposes the exact contrast between conventional body-fitted FEM and an immersed path:

```text
Current path
B-rep → Boolean ribs → root fillet → heal / MeshFix → Gmsh/TetGen
      → mesh quality → FEM setup → Code_Aster → results

Immersed path
B-rep / rib configuration → SDF and semantic masks → Cartesian grid
                         → cut-cell quadrature → sparse solve → results
```

The existing conventional pipeline is valuable as a reference rather than something to replace:

- The project has 490 solved discrete-rib designs and retained result/provenance records.
- The corpus includes a 16-case load-response basis, allowing robust ranking after the solve.
- Code_Aster 18.0.12 is installed and the baseline flow is known.
- The nominal 15-rib baseline already supplies geometry, loads, FEM entities, and result fields.
- Existing morphing, regions, and semantic identity work provide a starting point for solver-neutral regions and design-space integration.

The conventional mesh path is also the reason to test the immersed route. The documented baseline mesh has 57,240 nodes, 202,496 tetrahedra, 67 elements below quality 0.1, and minimum quality 0.00788 before a morph. Identical CAD has also produced different mesh node counts on re-run. This makes body-fitted mesh preparation, quality, and repeatability a real engineering cost rather than a theoretical inconvenience. [file:29]

## Scope

## In scope: Release 0

```text
Physics
- Linear, isotropic, small-strain static elasticity only.
- One selected existing GB3 service-load case.
- One simplified, well-defined set of supports and bearing loads.

Geometry
- Existing GB3 baseline B-rep.
- Existing 15 discrete rib templates: presence/absence first.
- Existing drawing-controlled frozen regions and FEM interfaces.

Numerics
- Uniform Cartesian hexahedral background grid.
- Occupancy/SDF geometry classification.
- Adaptive subcell integration for cut cells.
- Penalty Dirichlet enforcement for an MVP.
- Surface traction / distributed load through semantic geometric masks.
- SciPy sparse assembly and sparse direct solve for initial sizes.

Validation
- Analytic verification fixtures.
- Baseline GB3 comparison to existing Code_Aster result.
- Grid-resolution study.
- Reaction balance, energy, constraint residual, and field comparison.
```

## Explicitly out of scope: Release 0

```text
- Reproducing Intact’s proprietary method or performance.
- Native nTop plugin or direct nTop implicit API integration.
- Nonlinear material, plasticity, contact, bolts with nonlinear preload, or dynamics.
- Accurate peak stress at sharp/unfilleted rib roots.
- General FSI.
- GPU acceleration before correctness is demonstrated.
- Automatic topology optimization.
- Using immersed outputs as unqualified high-fidelity labels for the existing surrogate.
- Replacing Code_Aster in any release-facing or customer-facing claim.
```

## Success statement

Release 0 succeeds when the platform can truthfully demonstrate:

> “For this GB3 baseline and this bounded class of rib/topology changes, the system compiles geometry and semantic boundary conditions into an immersed analysis representation without generating a body-fitted volume mesh; produces static structural screening results; quantifies resolution/convergence and correlation to Code_Aster; and routes a promising candidate to high-fidelity validation.”

It does **not** succeed merely because it outputs a coloured stress field.

---

# 1. Target Architecture

## 1.1 Solver-neutral engineering representation

The Design Space Object and identity graph remain the authority. The immersed solver receives compiled geometry and boundary masks, not UI-specific face IDs.

```text
CAD / drawings / FEM setup / load definitions
                  │
                  ▼
       Identity graph + evidence records
                  │
                  ▼
   Design Space Object + Boundary Region Objects
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
Body-fitted compiler   Immersed compiler
Gmsh/TetGen → MED      SDF → Cartesian grid
Code_Aster             Cut cells → sparse FEM
        │                   │
        └─────────┬─────────┘
                  ▼
     Universal result/provenance artifact
```

## 1.2 Required objects

### GeometryRevision

```python
GeometryRevision(
    id: str,
    baseline_id: str,
    rib_layout: RibLayout,
    morph_vector: MorphVector | None,
    brep_path: str | None,
    geometry_hash: str,
    evidence_state: Literal['measured', 'derived', 'assumed'],
)
```

### BoundaryRegion

A portable definition that can compile to either mesh groups or immersed-boundary quadrature.

```python
BoundaryRegion(
    id: str,
    kind: Literal['fixed', 'traction', 'bearing_load', 'symmetry'],
    semantic_entity_id: str,
    selector: GeometricSelector,
    vector_or_load: list[float] | LoadBasisReference,
    evidence_ids: list[str],
    evidence_state: EvidenceState,
    solver_bindings: dict[str, SolverBinding],
)
```

Use selectors such as:

```text
cylindrical_band
annular_face_band
plane_band
surface_patch
axis_aligned_box
implicit_boolean_mask
entity-derived face set
```

### ImmersedRepresentation

```python
ImmersedRepresentation(
    id: str,
    geometry_revision_id: str,
    sdf_version: str,
    bbox_mm: tuple[float, float, float, float, float, float],
    grid_type: Literal['uniform_cartesian', 'octree'],
    cell_size_mm: float,
    padding_cells: int,
    active_cell_count: int,
    inside_cell_count: int,
    cut_cell_count: int,
    unresolved_cell_count: int,
    min_feature_resolution_ratio: float,
    boundary_mask_coverage: dict[str, float],
    content_hash: str,
)
```

### ImmersedRun

```python
ImmersedRun(
    id: str,
    representation_id: str,
    boundary_set_id: str,
    material_id: str,
    solver_version: str,
    quadrature_version: str,
    bc_version: str,
    status: RunStatus,
    result_artifact_id: str | None,
    validation_state: Literal['unvalidated', 'screening_validated', 'rejected'],
)
```

---

# 2. Numerical Method

## 2.1 Geometry representation

Use the sign convention:

\[
\phi(\mathbf{x}) < 0 \quad \text{inside solid}, \qquad
\phi(\mathbf{x}) = 0 \quad \text{on boundary}, \qquad
\phi(\mathbf{x}) > 0 \quad \text{outside solid}
\]

The first implementation may use a tessellated B-rep plus a BVH:

```text
OpenCascade B-rep
→ controlled tessellation
→ triangle BVH / Embree proximity query
→ closest-point distance
→ OCC solid classifier or robust winding/parity sign query
→ narrow-band cache around the GB3 housing
```

The signed-distance implementation must return diagnostic validity—not merely a float:

```python
SdfQuery(
    phi_mm: float,
    signed: bool,
    nearest_point: Vec3,
    normal: Vec3 | None,
    distance_quality: Literal['exact_brep', 'tessellated', 'uncertain'],
)
```

### Required geometry tests

- Sphere: analytic SDF and normal.
- Box: signs and distances.
- Thick cylinder: signs and near-cylinder normals.
- B-rep baseline: random point classification cross-checked against OCC `BRepClass3d_SolidClassifier`.
- Rib union and rib absence: validate SDF sign in known rib volumes.
- Boundary sampling: verify projection lands on the expected tessellated/B-rep surface tolerance.

## 2.2 Background grid

Start with a uniform Cartesian hexahedral grid covering the GB3 bounding box plus padding.

```text
Grid origin:  bbox minimum − p × h
Grid extent:  bbox maximum + p × h
Cell size:    h
Padding:      2–3 cells initially
```

Initial candidate resolutions should be selected from a memory/time estimator, not guessed in the UI:

```text
Coarse:  20 mm
Medium:  10 mm
Fine:     5 mm
```

Do not assume all three will fit practical memory. Generate an estimator before committing:

```text
estimated cells
estimated active degrees of freedom
estimated cut-cell quadrature points
estimated sparse nonzeros
estimated RAM
estimated solve class
minimum detected feature / h ratio
```

### Cell classification

Each cell is one of:

```text
outside      no material contribution
inside       standard element integration
cut          material/boundary intersects cell; special quadrature
unresolved   feature too thin or sign/configuration uncertain at h
```

Use more than corner samples. Initial classifier:

```text
8 corners + center + 12 edge midpoints
```

If classifications disagree or \(\min |\phi|\) is below a threshold, mark cell `cut`. If a potential feature cannot be resolved at the selected resolution, mark it `unresolved`, emit a diagnostic, and require either local refinement or a lower-fidelity acknowledgement.

## 2.3 Element formulation

Use trilinear eight-node hexahedral background elements initially.

For a full inside cell:

\[
K_e = \int_{\Omega_e} B^T D B\,d\Omega
\]

For a cut cell:

\[
K_e = \int_{\Omega_e \cap \Omega_s} B^T D B\,d\Omega
\]

where \(\Omega_s\) is the solid region defined by the SDF.

Material starts as homogeneous linear isotropic elastic:

\[
\sigma = D\epsilon
\]

The material representation must remain extensible to piecewise material masks, but multi-material behavior is not a Release 0 task.

## 2.4 Cut-cell quadrature: MVP method

Implement adaptive subcell integration first.

```text
For every cut cell:
1. Subdivide into n × n × n subcells.
2. Evaluate SDF at each subcell center.
3. Retain inside subcells.
4. Apply standard Gauss integration over retained subcells.
5. Recursively subdivide mixed subcells to depth dmax.
6. Record material volume fraction and quadrature convergence.
```

Initial controlled parameters:

```text
n_base = 2
max_refinement_depth = 3
material fraction tolerance = documented experiment parameter
minimum retained fraction = documented experiment parameter
```

The objective is correctness and measured convergence—not peak speed.

### Do not do in Release 0

- Do not silently treat every cut cell as half-solid.
- Do not discard small material fractions without an explicit stabilization/diagnostic policy.
- Do not advertise stress convergence around sharp rib roots.
- Do not call the method “exact geometry integration.”

## 2.5 Small cut-cell policy

Small solid fractions can create ill-conditioned systems and nonphysical stiffness behavior. Make the policy explicit.

```text
If volume fraction ≥ f_ok:
  use quadrature normally.

If f_min ≤ volume fraction < f_ok:
  use quadrature, mark cell as conditioning-risk.

If volume fraction < f_min:
  Release 0: locally refine one level, then reclassify.
  If still below f_min: mark unresolved / reject representation.
```

Do not remove the material or aggregate it into a neighbor until that behavior is separately implemented and benchmarked.

## 2.6 Essential boundary conditions

### Release 0 method: scaled penalty enforcement

For a displacement condition \(u = \bar{u}\) on \(\Gamma_D\), add:

\[
K \uplus= \alpha \int_{\Gamma_D} N^T N\,d\Gamma
\]

\[
f \uplus= \alpha \int_{\Gamma_D} N^T \bar{u}\,d\Gamma
\]

Set penalty scale through a documented calibration study, conceptually proportional to:

\[
\alpha = c_\alpha \frac{E}{h}
\]

where \(c_\alpha\) is chosen from numerical tests—not hidden as a solver magic constant.

### Required metrics

- Maximum displacement-condition residual.
- Constraint reaction balance.
- Matrix conditioning / solver convergence behavior.
- Sensitivity to \(c_\alpha\) and grid size.

### Production direction

Move to Nitsche-type consistent boundary treatment only after Release 0 static correlation succeeds. Nitsche is the preferred production direction because it avoids an arbitrarily oversized penalty, but it is not a prerequisite for demonstrating the core no-body-fitted-mesh path.

## 2.7 Traction and bearing loads

For traction \(t\) on a selected geometric boundary \(\Gamma_t\):

\[
f_e^\Gamma = \int_{\Gamma_e \cap \Gamma_t} N^T t\,d\Gamma
\]

Use geometric masks compiled from semantic GB3 entities rather than mesh node IDs.

### Initial GB3 boundary-condition strategy

Do not reproduce the full existing RBE2/RBE3/bearing model in the first immersed solve. Begin with a reduced static fixture that is mechanically unambiguous and can be matched on the Code_Aster side.

Suggested staged fixtures:

```text
Fixture A
- Fixed mounting/flange region.
- Distributed force or moment on one bearing-seat cylindrical band.
- Compare displacement at 2–3 semantic landmarks.

Fixture B
- Existing structural support representation translated into a set of geometric masks.
- One selected service case from the current load system.
- Compare housing-level displacement, energy, and bore/axis movement.

Fixture C
- Existing 16-case basis, where each load case compiles to a geometric bearing mask.
- Only after Fixture B correlation is acceptable.
```

This prevents a new method and a complex existing setup from being debugged simultaneously.

---

# 3. GB3 Integration Plan

## P0 — Baseline freeze and reference package

**Purpose:** make the comparison reproducible before writing the immersed solver.

### Tasks

- Select one canonical GB3 baseline geometry revision.
- Select one baseline rib configuration: recommended nominal 15-rib configuration first.
- Freeze one material card, one support/load fixture, and one Code_Aster reference result.
- Export the B-rep, surface tessellation, MED mesh, node groups, load definitions, Code_Aster command file, and relevant result samples into a single `gb3_immersed_reference` fixture.
- Record content hashes, mesh size, Code_Aster version, material values, load magnitudes, and unit system.
- Define 10–20 semantic comparison probes: bore centers, bearing-seat axis samples, mounts, outer-skin points, and low-gradient bulk locations.

### Deliverables

```text
fixtures/gb3_immersed_reference/
  geometry/baseline.brep
  geometry/baseline_surface.stl
  fem/reference.med
  fem/reference.comm
  fem/boundary_regions.json
  loads/load_case_*.json
  probes/semantic_probes.json
  results/code_aster_reference.npz
  manifest.json
```

### Gate P0

A clean environment can reproduce and hash the same reference package. No immersed work begins until this fixture is frozen.

## P1 — Solver-neutral boundary masks

**Purpose:** decouple GB3 engineering setup from mesh node groups.

### Tasks

- Define `BoundaryRegion` Pydantic models.
- Hand-author the first 3–5 GB3 regions with source/evidence links.
- Implement geometric selectors against B-rep/SDF:
  - mounting plane/patch.
  - bearing-seat cylindrical band.
  - bolt/flange support region if needed.
  - load application band.
- Implement a compiler that maps each boundary region to:
  - Existing Code_Aster mesh groups for the reference path.
  - Immersed surface-mask queries for the new path.
- Add coverage metrics: mask area, detected connected components, distance from intended CAD anchors, and overlap/conflict checks.

### Gate P1

The same semantic region renders visibly and correctly on the CAD surface and maps to the known Code_Aster mesh group. If the semantic mask does not reproduce the intended physical interface, do not proceed to the immersed solve.

## P2 — B-rep to signed-distance field service

**Purpose:** create the geometry interface required by an immersed solver.

### Tasks

- Create `src/fastcae/immersed/geometry.py`.
- Implement `BrepSdf` using OCC classification plus a tessellation/BVH proximity query.
- Cache a narrow-band SDF grid keyed by geometry hash and resolution.
- Implement surface projection and approximate normal query.
- Add a `geometry_diagnostics` command and API.
- Compare occupancy/volume from SDF sampling against B-rep volume over increasing resolutions.

### Files

```text
src/fastcae/immersed/
  __init__.py
  geometry.py
  tessellation.py
  sdf.py
  selectors.py
  diagnostics.py

tests/immersed/
  test_sdf_primitives.py
  test_sdf_gb3.py
```

### Metrics

```text
- Random point sign agreement with OCC classifier.
- Surface distance error against tessellated/B-rep projection.
- Estimated SDF volume versus B-rep volume.
- Missing-sign / ambiguous-query count.
- Runtime and cache hit ratio.
```

### Gate P2

- Primitive tests pass.
- GB3 random-point sign agreement is documented and meets a defined threshold.
- The volume estimate converges toward B-rep volume as grid resolution increases.
- All ambiguous queries are counted and surfaced; none are silently treated as inside.

## P3 — Grid compiler and diagnostic viewer

**Purpose:** prove geometry is representable before solving physics.

### Tasks

- Create uniform Cartesian grid from SDF bounding box.
- Classify cells as outside, inside, cut, unresolved.
- Implement adaptive cell subdivision for cut-cell occupancy/volume estimate.
- Generate visualization artifacts:
  - grid slice views;
  - cut-cell cloud;
  - unresolved-feature markers;
  - boundary-mask coverage;
  - cell material-fraction histogram.
- Add grid cost/memory estimator.
- Build `POST /api/v1/immersed/preview` endpoint.

### API

```text
POST /api/v1/immersed/preview
{
  "geometry_revision_id": "...",
  "cell_size_mm": 10.0,
  "padding_cells": 2,
  "max_refinement_depth": 3,
  "boundary_region_ids": ["mount_01", "bearing_load_01"]
}
```

### Response

```json
{
  "representation_id": "immrep_...",
  "cell_size_mm": 10.0,
  "active_cells": 0,
  "cut_cells": 0,
  "unresolved_cells": 0,
  "minimum_feature_to_cell_ratio": 0.0,
  "estimated_ram_gb": 0.0,
  "boundary_coverage": [],
  "warnings": [],
  "artifact_ids": []
}
```

### Gate P3

At a documented initial GB3 grid size, the preview demonstrates:

- expected housing envelope;
- interior cavity and rib occupancy represented correctly;
- no unreported loss of a load/support mask;
- explicit warnings for under-resolved features;
- reproducible content hash and diagnostics.

## P4 — Independent verification fixtures

**Purpose:** prove the discretisation and boundary handling before GB3 correlation.

### Fixtures

| Fixture | Verifies | Required comparison |
|---|---|---|
| 3D cantilever beam | Displacement, bending, penalty BC | Euler–Bernoulli reference and body-fitted FEM |
| Torsion bar | Shear response | Analytic torsion solution where applicable |
| Thick cylinder | Radial displacement/stress trend | Lame solution or trusted FEM |
| Plate/cube patch test | Element consistency | Constant-strain response |
| Hole/cut geometry | Cut-cell handling | Body-fitted FEM away from singular boundary zones |
| Simple ribbed plate | Rib add/remove behavior | Matched Code_Aster model |

### Mandatory reported quantities

```text
Displacement relative error
Total strain-energy relative error
Reaction-force imbalance
Maximum Dirichlet residual
Linear solver residual
Cell-size convergence slope
Cut-cell count and fraction
```

### Gate P4

No GB3 result can be shown beyond internal debugging until:

- all fixture tests pass;
- grid refinement trends are monotonic or explained;
- reactions balance within a stated tolerance;
- penalty calibration is documented;
- results are reproducible from manifest inputs.

## P5 — GB3 Fixture A: simplified static comparison

**Purpose:** establish the first trustworthy GB3 correlation.

### Definition

Use the baseline 15-rib geometry and a simple, independently understandable fixture:

```text
Support
- One or more mounting/flange geometric masks constrained.

Load
- A distributed force/moment over a single bearing-seat cylindrical band.

Outputs
- Displacement at selected semantic probes.
- Total strain energy.
- Reaction force/moment.
- Broad displacement field comparison.
```

Create the exact equivalent Code_Aster reference fixture from the same semantic `BoundaryRegion` definitions.

### Grid sequence

Attempt a feasible sequence such as:

```text
20 mm → 10 mm → 5 mm
```

The actual values depend on memory estimates. If 5 mm is infeasible, do not hide it; report the available convergence sequence and move to local refinement only after the uniform-grid baseline is characterized.

### Comparison rules

Compare only quantities that are meaningful across representations:

```text
Good early comparison
- Probe displacements.
- Bore-center/axis translations and rotations derived from probes.
- Overall compliance / strain energy.
- Net reaction forces and moments.
- Displacement field sampled onto common CAD-surface points.

Deferred comparison
- Peak stress at sharp corners.
- Stress at unfilleted rib roots.
- Single raw element stress maxima.
```

### Gate P5

Define acceptance thresholds before inspecting the result. Example initial research targets—not product promises:

```text
- Reaction equilibrium: < 1% relative imbalance.
- Key displacement probe agreement: target < 10% at medium/fine grid.
- Strain energy agreement: target < 10–15% at medium/fine grid.
- Clear refinement trend from coarse to medium to fine.
- All BC mask coverage and constraint residuals reported.
```

If the grid does not converge or cannot represent the relevant load path, stop and debug P2/P3/P4. Do not compensate using a fitted correction model.

## P6 — GB3 Fixture B: existing service-case alignment

**Purpose:** compare against the useful engineering output from the current workflow.

### Tasks

- Compile one selected existing service load case into semantic masks.
- Translate existing constraints incrementally.
- Use the same material and baseline geometry revision.
- Derive comparable bore/axis quantities from immersed displacement samples.
- Compare displacement, bearing-seat movement, relative axis misalignment proxy, strain energy, and robust response where the basis permits.

### Important limitation

The existing solver setup contains RBE-based interfaces and a 16-case basis. Do not assume an immersed geometric-mask replacement is mechanically equivalent merely because the selected surface looks similar.

For each translated condition, record:

```text
Existing FEM definition
Immersed geometric mask definition
Total applied load/moment comparison
Mask coverage/area
Resulting reaction distribution
Known equivalence limitation
```

### Gate P6

- The representation of each support/load has an explicit mapping record.
- The baseline comparison is acceptable for the selected decision metrics.
- Any mismatch is reported by condition, not averaged away globally.

## P7 — Rib presence/absence study

**Purpose:** demonstrate the advantage over re-meshed topology changes.

### Candidate set

Use a deliberately small, interpretable set:

```text
1. Baseline 15-rib design.
2. Baseline minus one known structurally relevant rib.
3. Baseline minus one less influential rib.
4. Baseline plus a permitted candidate rib, if CAD geometry exists.
5. Two-rib removal configuration.
```

For every candidate:

```text
B-rep / SDF geometry revision
Immersed representation at same grid definition
Immersed result
Existing Code_Aster result or selected new verification solve
Comparison artifact
```

### Measurements

- Representation compile time.
- No body-fitted mesh required on immersed path.
- Background-grid active/cut-cell change.
- Displacement/energy change relative to baseline.
- Difference of immersed delta versus Code_Aster delta.
- Whether the sign/ranking of change is correct.
- Boundary-mask coverage stability after rib change.

### Key principle

The first question is not “does immersed stress match everywhere?” It is:

> “When a rib is removed, does the immersed method correctly predict the direction and approximate magnitude of the engineering-relevant change compared with Code_Aster?”

### Gate P7

The solver must correctly preserve and report fixed interfaces while ribs disappear, and must achieve documented agreement on the **delta** of selected global/probe measures. If it cannot rank one-rib removal changes correctly, it is not ready for topology screening.

## P8 — Response-basis integration

**Purpose:** integrate the existing load-basis advantage with the new representation.

### Sequence

1. Run the 16 unit load cases on a single immersed GB3 configuration.
2. Store selected probe/bore/axis response contributions per case.
3. Recompose arbitrary specified service load combinations by linear superposition.
4. Compare re-composed response against a directly solved service case.
5. Expose the basis through the same robust-ranking and load-reweighting artifact model as the existing solver.

### Requirements

```text
- Every stored basis response identifies geometry revision and grid specification.
- Superposition self-check is mandatory.
- Basis cannot be mixed across geometry revisions.
- Robust ranking from immersed results is labeled exploration fidelity.
- High-fidelity Code_Aster verification is available as a direct next action.
```

### Gate P8

The immersed response basis reconstitutes its direct service-case response to an agreed tolerance for the linear fixture. Only then expose instant load reweighting in the UI.

## P9 — Platform and agent integration

**Purpose:** make the immersed solver an agent-operable backend, not a separate technical demo.

### New platform capabilities

```text
preview_immersed_representation
inspect_immersed_diagnostics
estimate_immersed_cost
run_immersed_static
compare_immersed_to_reference
refine_immersed_region
compile_immersed_load_basis
verify_with_code_aster
```

### Required artifact types

```text
immersed_representation_preview
immersed_grid_diagnostic
immersed_static_result
immersed_basis_result
solver_comparison
verification_request
```

### Agent rules

```text
Free
- Preview representation.
- Inspect grid/cut-cell/mask diagnostics.
- Estimate cost.
- Run a local low-cost screening solve if policy permits.
- Compare existing results.

Gated
- Launch remote/high-cost immersed campaigns.
- Create a new design-space parameter.
- Submit Code_Aster verification.
- Use an immersed result in a release-facing report.
```

### Example agent behavior

```text
User:
“Can we remove Rib N259 without worsening bearing-seat displacement?”

Agent:
1. Inspects design-space permission and drawing/FEM evidence.
2. Reports whether rib removal is allowed, assumed, or blocked.
3. Creates an SDF geometry revision with Rib N259 absent.
4. Previews immersed resolution and boundary-mask coverage.
5. Runs or proposes a low-cost static screening solve.
6. Compares delta with baseline.
7. States fidelity and whether a Code_Aster verification is required.
8. Previews exact verification cost/arguments.
9. Waits for approval before submitting the high-fidelity run.
```

---

# 4. Software Structure

## Package layout

```text
src/fastcae/
  immersed/
    __init__.py
    models.py             # Pydantic data contracts
    geometry.py           # GeometryField protocol, BrepSdf
    tessellation.py       # OCC tessellation, BVH setup
    sdf.py                # narrow-band field, cache, sign queries
    grid.py               # Cartesian grid and active-cell indexing
    classify.py           # inside/cut/outside/unresolved classification
    quadrature.py         # standard and adaptive subcell quadrature
    shape.py              # hex shape functions and B matrices
    material.py           # elastic material cards
    assembly.py           # sparse K/f assembly
    boundary.py           # penalty BC and traction integration
    solve.py              # solver adapters, residual diagnostics
    results.py            # CAD-surface sampling and semantic probes
    compare.py            # Code_Aster correlation artifacts
    diagnostics.py        # grid/mask/feature/conditioning reports
    cache.py              # content-addressed artifact cache
    manifest.py           # immutable run and representation manifest

  designspace/
    boundary_regions.py   # solver-neutral semantic selectors
    compiler.py           # B-rep / immersed / FEM compilation paths

  api/
    immersed.py           # FastAPI routers

tests/
  immersed/
    test_sdf_primitives.py
    test_grid_classification.py
    test_quadrature.py
    test_patch.py
    test_cantilever.py
    test_torsion.py
    test_thick_cylinder.py
    test_gb3_masks.py
    test_gb3_baseline.py
```

## Content-addressed cache keys

Every cached object requires an explicit digest.

```text
SDF cache
hash(B-rep geometry revision, tessellation settings, SDF resolution, implementation version)

Immersed representation
hash(SDF cache key, bounding box, h, padding, classification settings, quadrature settings)

Boundary integration cache
hash(representation, BoundaryRegion definition, BC integration settings)

Stiffness cache
hash(representation, material card, quadrature, BC enforcement scheme)

Result
hash(stiffness cache, load definition, solver tolerance, output sampling schema)
```

Never key these artifacts by a short design ID alone. The existing mesher is non-deterministic enough that mesh-linked caches already require content hashing; the immersed path should preserve the same discipline. [file:24][file:29]

## Manifest

Each immersed result must be reconstructible from one immutable manifest:

```json
{
  "geometry_revision": "...",
  "geometry_hash": "...",
  "design_space_version": "...",
  "boundary_regions": ["..."],
  "load_case": "...",
  "material": {"id": "...", "E": 0, "nu": 0, "rho": 0},
  "grid": {"type": "uniform_cartesian", "cell_size_mm": 0, "padding": 2},
  "classification": {"version": "...", "samples": "corners-center-edges"},
  "quadrature": {"method": "adaptive_subcells", "max_depth": 3},
  "boundary_enforcement": {"method": "penalty", "c_alpha": 0},
  "solver": {"backend": "scipy_splu", "tolerance": 0},
  "code_commit": "...",
  "container_image": "...",
  "created_at": "..."
}
```

---

# 5. Validation and Trust Policy

## 5.1 Required result labels

Every UI card, agent response, report, and API result includes:

```text
Fidelity: exploration | correlated screening | verification candidate | high fidelity
Geometry representation: B-rep-derived SDF
Discretisation: cell size, grid type, active/cut cell counts
Boundary treatment: method and mask coverage
Convergence status: untested | partial | grid-converged for metric
Comparison state: no reference | compared to Code_Aster | mismatch flagged
Evidence state: measured | derived | assumed
```

## 5.2 What Release 0 may claim

```text
- No body-fitted volume mesh was generated for the immersed solve.
- The GB3 geometry was compiled into an SDF/background-grid representation.
- Structural screening results were produced at stated grid resolution.
- Selected global/probe response measures were compared to Code_Aster.
- Rib removal candidates can be screened without remeshing.
- The solver reports unresolved features, boundary-mask coverage, and convergence diagnostics.
```

## 5.3 What Release 0 must not claim

```text
- Equivalent high-fidelity stress everywhere.
- Certified stress result.
- Accurate singular peak stress.
- General “any geometry” robustness.
- Validity across all GB3 load cases before basis validation.
- Automatic replacement of the current Code_Aster verification workflow.
- Direct replacement of Intact.Simulation.
```

## 5.4 Comparison dashboard

For each GB3 comparison, show:

| Category | Immersed | Code_Aster | Difference | Status |
|---|---:|---:|---:|---|
| Grid / mesh resolution | stated | stated | n/a | informational |
| Applied force | stated | stated | % | required |
| Reaction balance | stated | stated | % | required |
| Probe displacement | stated | stated | % | required |
| Compliance / strain energy | stated | stated | % | required |
| Bore/axis metric | stated | stated | % | required once fixture supports it |
| Stress percentile | stated | stated | % | exploratory only |
| Peak stress | stated | stated | n/a | explicitly non-comparable initially |
| Runtime | stated | stated | ratio | informational |

---

# 6. UI Plan

## 6.1 Representation selector

Add a representation panel to the platform stage:

```text
ANALYSIS BACKENDS

Validated FEM
Code_Aster · body-fitted tetrahedral mesh
Best for: confirmation and reported results
Status: current reference backend

Immersed screening
B-rep-derived SDF · Cartesian cut-cell FEM
Best for: rapid topology and complex-geometry checks
Status: experimental / correlated for selected GB3 fixture
```

The user does not see “meshless” as a magic label. They see a capability, its fidelity, and its valid use.

## 6.2 Immersed preview

Before any solve, show:

```text
IMMERSION PREVIEW

Geometry revision: GB3 / 15-rib baseline
Cell size: 10 mm
Active cells: …
Cut cells: …
Unresolved cells: …
Minimum feature / cell ratio: …
Boundary mask coverage: …
Estimated RAM: …
Estimated solve time: …

Warnings
- Rib root fillet below selected resolution.
- Load mask has multiple disconnected components.
- Outer-skin morphability is assumed, not drawing verified.

[Refine] [Run screening] [Use Code_Aster]
```

## 6.3 Solver-comparison card

```text
SCREENING VS REFERENCE

Fixture: GB3 bearing-seat static load
Metric: bore-axis displacement
Immersed: …
Code_Aster: …
Difference: …
Grid convergence: …
Boundary coverage: …

Interpretation
Suitable / not suitable for candidate ranking at this resolution.

[Inspect probes] [Refine grid] [Request verification]
```

## 6.4 Agent card

The agent must never present an immersed result as a final release recommendation without stating its fidelity.

```text
Agent result

Rib N259 removal reduces mass by …
Immersed screening predicts bearing-seat displacement changes by …

Confidence
- Grid: 10 mm, correlated on Fixture A only.
- Boundary-mask coverage: …
- Rib-root stress: not used for this conclusion.

Recommended next action
Run one Code_Aster verification solve.

[Preview verification] [Approve]
```

---

# 7. Build Sequence and Gates

| Phase | Duration target | Deliverable | Hard gate |
|---|---:|---|---|
| P0 | 2–3 days | Frozen GB3 reference fixture | Reproducible baseline package |
| P1 | 3–5 days | Solver-neutral GB3 boundary masks | CAD + existing FEM mapping checks |
| P2 | 1–2 weeks | B-rep/SDF service | Sign, volume, projection diagnostics pass |
| P3 | 1 week | Grid compiler and preview UI/API | Correct cut/inside/outside/mask visualization |
| P4 | 2–3 weeks | Analytical/canonical validation suite | Convergence, reaction, BC tests pass |
| P5 | 1–2 weeks | GB3 simplified static correlation | Predeclared displacement/energy targets met |
| P6 | 2–4 weeks | Selected GB3 service-case mapping | Condition-by-condition mapping documented |
| P7 | 1–2 weeks | Rib removal/addition delta study | Correct directional/ranking behavior |
| P8 | 1–2 weeks | Immersed response basis | Direct-vs-superposition check passes |
| P9 | 1–2 weeks | Platform/agent integration | Agent cannot overstate fidelity or bypass gate |

These durations are planning estimates, not promises. P4 and P6 can expose numerical issues that require returning to the preceding phase.

## Priority order

Do not start with a large GB3 campaign.

```text
P0 → P1 → P2 → P3 → P4 → P5
```

is the non-negotiable correctness chain.

Only after P5:

```text
P6 → P7 → P8 → P9
```

P7 is the commercial demonstration. P5 is what makes it believable.

---

# 8. First Two-Week Sprint

## Goal

No physics result yet. Deliver an honest immersed-representation preview for the GB3 baseline.

## Backend tickets

1. Create `fastcae.immersed` package and immutable model contracts.
2. Freeze the GB3 reference manifest and artifact bundle.
3. Define 3 initial semantic `BoundaryRegion` objects.
4. Implement B-rep tessellation plus content-hashed cache.
5. Implement closest-point distance and inside/outside classifier.
6. Create narrow-band SDF sampling API.
7. Implement uniform Cartesian grid generation.
8. Classify cells from corners, centers, and edge-midpoints.
9. Implement basic material-fraction estimate by 2×2×2 subcell sampling.
10. Emit cut-cell, unresolved-cell, and mask-coverage diagnostics.
11. Implement `POST /api/v1/immersed/preview`.
12. Create primitive unit tests and GB3 smoke tests.

## UI tickets

1. Add an “Immersed screening” representation entry to the platform shell.
2. Build grid-preview card with resolution, active cells, cut cells, unresolved cells, estimated RAM, and warnings.
3. Reuse viewer to render CAD surface plus cut-cell cloud / slice planes.
4. Render boundary masks with evidence-state labels.
5. Add “What cannot be resolved at this resolution” panel.
6. Add exportable manifest/provenance link.

## Sprint acceptance test

A user opens the GB3 workspace, selects “Immersed screening,” chooses a grid resolution, and sees:

```text
- The unchanged CAD geometry.
- The background-grid occupancy representation.
- Cut cells around outer wall, bores, cavity, and ribs.
- Selected support/load masks over the geometry.
- Any unresolved small features.
- Memory/time estimate.
- A reproducible representation hash.
```

No one should call this an FEA result yet. It is a geometry/compiler milestone.

---

# 9. First Physics Sprint

## Goal

Produce one verified linear-elastic immersed FEM result for a canonical fixture, then move to GB3 Fixture A.

## Tasks

1. Implement trilinear hex shape functions, Jacobian, and strain-displacement matrix.
2. Implement full-cell 2×2×2 Gauss stiffness integration.
3. Implement cut-cell adaptive subcell quadrature.
4. Assemble sparse global stiffness/mass-independent right-hand-side system.
5. Implement simple penalty displacement boundary enforcement.
6. Implement distributed traction over selected geometric boundary region.
7. Solve with SciPy sparse direct solver.
8. Compute reactions, energy, residuals, and displacement output.
9. Implement surface/probe sampling of results.
10. Pass cantilever, patch, and simple ribbed plate tests.
11. Create matched simplified GB3 Fixture A in Code_Aster.
12. Run grid-resolution correlation study.

## Physics-sprint acceptance test

```text
Given: GB3 Fixture A, frozen geometry, frozen material, frozen load/support masks.

When: 20 mm, 10 mm, and feasible finer immersed grids are run.

Then:
- Applied load and reactions are reported.
- Dirichlet residual and linear-solve residual are reported.
- Probe displacement and energy converge in a documented direction.
- Results are compared to a matched Code_Aster fixture.
- Output is labeled exploration fidelity.
- A complete immutable manifest reproduces the run.
```

---

# 10. Decision Triggers

| Observation | Decision |
|---|---|
| SDF sign or volume tests fail | Fix geometry layer; do not tune solver |
| GB3 masks do not match intended CAD/FEM interfaces | Fix semantic boundary compilation; do not compare solutions |
| Canonical patch/cantilever tests fail | Fix assembly/BC implementation; stop GB3 work |
| Grid refinement does not converge | Inspect cut-cell quadrature, small-cell handling, BC enforcement |
| GB3 displacement mismatch persists across refinement | Isolate each support/load condition; do not fit correction |
| Stress mismatch only at sharp roots | Exclude from Release 0 metric; add fillets/appropriate stress treatment later |
| Uniform grid is prohibitively expensive | Implement octree/local refinement only after correctness is proven |
| Rib-removal delta has wrong sign/rank | Do not use for screening; return to resolution/BC/mapping diagnosis |
| Correlation is good for probes but not stress | Ship as compliance/displacement/bore-motion screening only |
| Fillet/Boolean failure rate becomes high in conventional path | Increase priority of implicit/SDF geometry generation for topology edits |

---

# 11. Relationship to Current Work

This work must not displace the immediate credibility gates already identified for the GB3 platform:

- Measure the noise floor for the current objective.
- Run the first morphed Code_Aster solve and validate setup rebind.
- Measure strain-energy participation of candidate morph regions.
- Validate gradients against finite differences before presenting them as engineering facts.
- Keep the existing Code_Aster pipeline as the current high-fidelity source of truth.

The immersed effort begins as a parallel R&D workstream because it targets a different bottleneck: topology/implicit-geometry representation and body-fitted meshing failure. The existing 490-design corpus and conventional solver remain the benchmark and validation asset. [file:16][file:29][file:30]

## Final product rule

The platform should never offer a false binary choice between “meshless AI” and “traditional FEA.”

```text
Immersed grid
- Fast topology/implicit-geometry screening.
- Grid and mask diagnostics visible.
- Suitable only in measured trust region.

Code_Aster body-fitted FEM
- Validation and release-facing confirmation.
- Retains current detailed setup/physics credibility.

Platform
- Preserves one Design Space Object, one evidence graph,
  one semantic boundary definition, one session/provenance model,
  and one governed action path across both backends.
```
