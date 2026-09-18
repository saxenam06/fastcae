# Physical-AI Cast Housing Design Generation

## Research Report: A Reproducible Open-Source System for Generating 4,000 Rich, Valid, Diverse Cast-Housing Variants per Study

## Executive summary

The appropriate solution is not an unconstrained text-to-CAD or mesh generative model. It is a deterministic, constraint-aware **design compiler** that turns a baseline STEP housing, drawing-derived rules, and an engineer-approved study definition into a large population of traceable CAD recipes.

Each candidate should be represented as a compact declarative program rather than as an opaque edited STEP file:

```text
variant =
  base housing
  + rib connection graph
  + continuous geometry parameters
  + wall/boss displacement fields
  + hole patterns
  + conditional pads
  + material selection
```

The system should generate a candidate pool larger than the 4,000 required final designs, validate candidates in a progressively more expensive funnel, and select the final population explicitly for topology diversity, parameter-space coverage, geometric separation, and simulation readiness. Quality-diversity methods are particularly suitable because their objective is a collection of high-quality, behaviourally diverse solutions rather than one single optimum. `pyribs` provides practical Python implementations of archives, emitters and schedulers for this type of search, including centroidal Voronoi tessellation archives that partition a multidimensional measure space into cells.[web:498][web:499][web:501]

The key architectural decision is to make both the **rib connection topology** and the **continuous manufacturing-aware geometry** first-class design variables. This prevents the system from collapsing into a handful of square, triangular, radial or spoke rib templates.

---

## 1. Problem definition

### 1.1 Target capability

Given:

- A cast housing as a STEP file.
- One or more engineering drawings.
- A study configuration describing allowed materials, loads, manufacturing process, pull direction, protected regions and solver setup.
- An engineer feedback loop.

Produce a reproducible dataset of 4,000 variants in which every member:

- Is materially and geometrically different from the others.
- Varies rib topology, attachment points, angles, count, thickness, height, taper, fillets and draft.
- Varies approved wall, floor and boss thicknesses.
- Varies hole patterns and conditional local pads where approved.
- Respects protected bearing seats, machined faces, interfaces and tapped holes.
- Passes deterministic B-Rep, manufacturability, meshing and solver-quality checks.
- Has a complete immutable recipe and provenance record.

### 1.2 What “rich”, “varied” and “valid” mean

| Requirement | Operational definition |
|---|---|
| Rich | Multiple independent feature classes vary, individually and in combinations: topology, attachment locations, geometry, wall field, holes, pads and material. |
| Varied | Designs have a calibrated minimum pairwise distance in a mixed topology/geometry/material descriptor space. |
| Coverage | The final set occupies a high fraction of empirically reachable cells in a feasibility-filtered reference space. |
| Valid | Each design passes exact CAD validation, protected-geometry invariance, castability checks, production meshing and target solver checks. |
| Repeatable | Identical input files, rule version, software environment and seed regenerate the same canonical recipes and equivalent outputs. |
| Traceable | Every design contains file hashes, source-rule provenance, generated values, code versions, tool versions, random seeds, checks and artifacts. |

### 1.3 The central anti-pattern

Do not create a library of predefined rib motifs and randomly perturb their parameters. That approach gives the illusion of variety while clustering heavily around a few families. It also leaves legal portions of the connection and angle spaces unexplored.

Instead:

1. Build an explicit set of legal **semantic attachment regions**.
2. Construct a large potential graph of legal rib connections.
3. Generate arbitrary feasible subgraphs and attachment positions.
4. Generate continuous geometry under manufacturing constraints.
5. Measure diversity and coverage explicitly.
6. Preserve only candidates that pass deterministic downstream gates.

---

## 2. Reference architecture

```text
STEP + drawing + study configuration
                |
                v
     Semantic ingestion and alignment
                |
                v
  Protected/mutable region decomposition
                |
                v
       Study rule compiler and DSL
                |
                v
  Rib graph + continuous-field generation
                |
                v
 Cheap symbolic and proxy geometric checks
                |
                v
       Exact B-Rep CAD construction
                |
                v
 Castability and protected-face validation
                |
                v
      Quality-diversity archive/search
                |
                v
    Production mesh -> solver -> result QC
                |
                v
       Final 4,000-design selection
                |
                v
 Engineer review of approximately 20 designs
                |
                v
    Approved new constraints/preferences
```

The system should be built as independent services or worker processes. CAD-kernel operations, meshing and solvers may fail or exhaust memory. A failed candidate must never terminate a campaign.

### 2.1 Separation of authority

| Layer | Authority | Role |
|---|---|---|
| Engineering truth | Approved engineer rules and drawing interpretation | Determines what is allowed. |
| Exact geometry | B-Rep kernel | Determines whether the candidate can be built. |
| Manufacturing checks | Deterministic geometric and process-specific validators | Determines whether it is castable under declared assumptions. |
| CAE truth | Production mesher and solver | Determines training-data eligibility. |
| ML models | Advisory only | Prioritize, rank, predict failure risk and guide exploration. |
| LLM/VLM interpretation | Proposal only | Helps translate drawings, notes and objections into reviewable rules. |

An LLM must never silently determine whether a bearing seat can move, whether a feature has sufficient draft, or whether a design is castable.

---

## 3. Input ingestion and semantic decomposition

## 3.1 STEP ingestion

Use Open CASCADE Technology (OCCT) as the authoritative B-Rep kernel, directly or through `pythonocc-core`, CadQuery or build123d. OCCT provides STEP translation and a Shape Healing toolkit intended to analyse and repair topology and geometry defects, including tools that operate on full shapes and subshapes.[web:611][web:612][web:613]

The STEP ingestion process should extract:

- Solids, shells, faces, edges, wires and vertices.
- Analytic surface categories: planes, cylinders, cones, tori and freeform surfaces.
- Face area, centroid, normal distribution, curvature and bounding boxes.
- Face adjacency and local concavity/convexity.
- Cylindrical features that may be bearing seats, bores, counterbores or threaded-hole candidates.
- Planar faces that may be machined interfaces, flange faces or datum surfaces.
- Candidate wall, floor, boss, flange and plate regions.
- Baseline thickness samples.
- Candidate mould pull directions and parting strategies.

### 3.1.1 Semantic identifiers, not raw STEP IDs

Never use raw STEP face indexes as durable references. Boolean operations, healing and STEP re-export can change topological entity numbering.

Assign semantic feature identifiers based on geometric signatures. Example:

```yaml
semantic_id: bearing_seat_02
surface_type: cylinder
axis: [0.000000, 0.000000, 1.000000]
radius_mm: 42.000
center_mm: [118.400, 77.250, 31.000]
adjacent_surface_signature: [...]
reference_sample_hash: sha256:...
```

After every build, rematch features by surface class, axis, radius, center, adjacency, sampled surface points and local neighbourhood. The rematching threshold must be part of the ruleset.

### 3.1.2 Healing policy

Apply healing during **input normalization**, not as an unrestricted post-generation repair tool. Healing can make an imported baseline usable, but it can also conceal a generated defect or move geometry beyond what a manufacturing study permits.

Recommended policy:

- Heal imported source STEP with a logged, bounded tolerance.
- Preserve a raw source artifact and a normalized baseline artifact.
- Reject a generated candidate if it needs substantial healing.
- Permit only explicit, bounded repair classes after generation.
- Reject any repair that modifies protected geometry beyond its allowed deviation.

OCCT Shape Healing is designed to inspect and fix several categories of geometry and topology problems, but its ability to modify shapes is precisely why its use must be logged and constrained.[web:612][web:615]

## 3.2 Drawing ingestion

Support inputs in the following priority order:

1. Native DXF/DWG-derived vector drawing.
2. Vector PDF.
3. Raster PDF or scan.
4. Engineer-authored study form where automatic extraction is uncertain.

Recommended open-source components:

| Need | Candidate tools |
|---|---|
| DXF parsing | `ezdxf` |
| PDF vector/text extraction | PyMuPDF, `pdfplumber` |
| Image preprocessing | OpenCV |
| OCR | Tesseract, PaddleOCR |
| Schema validation | Pydantic, JSON Schema |
| Units | Pint |
| Rule proposal | Local/open-weight VLM or LLM, with human approval |

The drawing interpretation process should propose:

- Dimensional limits.
- Datum references.
- Geometric dimensioning and tolerancing callouts.
- Surface finish and machining annotations.
- Thread, hole and bore information.
- Material notes.
- Section views.
- Untouchable faces and interfaces.
- Permitted modification zones.
- Foundry process notes.

Every rule must retain provenance:

```yaml
rule_id: protected_face_bearing_A
source_type: drawing_dimension
source_file_sha256: sha256:...
page: 2
view: section_B_B
source_region_px: [1020, 334, 1355, 511]
raw_text: "Ø84 H7 MACHINED"
parser_confidence: 0.91
approval_status: approved
approved_by: engineer_user_id
approved_at: 2026-09-13T...
```

A campaign must not begin with unreviewed low-confidence interpretations that affect hard constraints.

## 3.3 Region classification

Partition the housing into three classes:

| Region class | Examples | Permitted treatment |
|---|---|---|
| Protected | Bearing seats, seal bores, tapped holes, machined faces, mounting interfaces, datums | Frozen unless explicitly released. |
| Mutable | Cast walls, floors, rib zones, noncritical bosses, plates and flanges | May be altered only within study limits. |
| Exclusion | Tool clearances, assembly envelopes, lubricant paths, core/access volumes, keep-outs | No generated material may occupy these volumes. |

Create explicit clearance solids around protected and exclusion features. Generator operations are permitted only in mutable regions and must remain outside all clearance solids.

Define semantic region labels such as:

```text
floor_rear
left_wall_upper
bearing_boss_A_outer
bearing_boss_B_outer
mounting_plate_03
flange_front_lower
```

These labels form the nodes of the rib connectivity graph.

---

## 4. Generative representation

## 4.1 Rib topology graph

Represent generated stiffening as a graph:

\[
G=(V,E)
\]

Where:

- `V` is the set of semantic regions and approved intermediate junction regions.
- `E` is the set of generated ribs or web segments.
- An edge has endpoint attachment domains, anchor coordinates, path representation and geometry attributes.

A generic edge record is:

```yaml
edge_id: rib_012
source_region: bearing_boss_A_outer
target_region: left_wall_upper
source_anchor_uv: [0.34, 0.72]
target_anchor_uv: [0.63, 0.29]
path_type: cubic_bezier
control_points: [[...], [...]]
base_thickness_mm: 5.0
top_thickness_mm: 4.2
height_mm: 24.0
longitudinal_taper: 0.85
side_draft_deg: 2.5
root_fillet_mm: 4.0
end_fillet_mm: 3.0
pad_mode: conditional
```

This representation allows all of the requested rib freedoms:

- What a rib connects.
- Rib count.
- Attachment points.
- Angles.
- Path shape.
- Thickness.
- Height.
- Taper.
- Draft.
- Fillets.
- Conditional pads.

A radial, triangular or rectangular motif can still arise as an output, but it is not hard-coded as a family.

## 4.2 Potential connection graph

Before campaign generation, create a set of candidate edges between approved region pairs. A candidate edge is admitted only if inexpensive checks show it is plausible:

- Source and target anchors are inside permitted attachment domains.
- The preliminary swept volume does not enter protected or exclusion volumes.
- The span is within configured limits.
- A legal drafted profile can be oriented relative to the pull direction.
- Required sand clearance is potentially achievable.
- The edge does not create an immediate forbidden crossing or junction.
- Attachment does not force protected-face modification.

The potential connection graph becomes a study-specific search substrate. Store it as an artifact with version and hash.

## 4.3 Topology generation methods

Use a portfolio, not a single sampling method:

| Method | Best use |
|---|---|
| OR-Tools CP-SAT | Enforce integer/rule constraints: rib count, forbidden connections, required ties, degree limits and no-good cuts. |
| Markov-chain graph moves | Add, delete, rewire, split and merge edges while remaining close to feasible populations. |
| Random spanning structures | Create diverse connectivity backbones before adding secondary ribs. |
| Anchor resampling | Change attachment positions independently of the region-level graph. |
| Graph crossover | Exchange coherent valid rib subgraphs between parents. |
| Quality-diversity emitters | Focus effort on empty behavioural regions and rare connection patterns. |

Required graph-level constraints may include:

```yaml
graph_constraints:
  min_ribs: 3
  max_ribs: 18
  max_region_degree: 6
  forbidden_connection_pairs:
    - [bearing_seat_02, machined_face_04]
  forbidden_subgraphs:
    - x_crossing
    - high_degree_compact_junction
  must_connect_any:
    - [bearing_boss_A_outer, floor_rear, left_wall_upper]
```

## 4.4 Continuous sampling

Continuous variables should not be sampled by independent pseudorandom draws. Use:

- Scrambled Sobol sequences.
- Latin hypercube sampling.
- Maximin sampling.
- Boundary-biased samples for rule validation.
- Conditional distributions based on topology and local thickness.

For categorical variables such as material grade, hole-family type or pad mode, use balanced or novelty-weighted sampling rather than raw frequency sampling.

## 4.5 Rib primitive construction

Construct draft directly into each rib primitive. Do not create a constant-section rib and rely on downstream face drafting to fix it.

A robust feature-construction sequence is:

1. Resolve endpoint anchors on the semantic surfaces.
2. Construct a centreline with bounded curvature and span.
3. Construct local frames along the path.
4. Create a drafted, tapered cross-section.
5. Sweep or loft the profile.
6. Blend roots and endpoints with controlled fillets.
7. Fuse locally with nearby target region geometry.
8. Apply pad geometry, if activated and feasible.
9. Validate the isolated feature before performing global union.

Perform local fillets before the final large Boolean union where practical. This reduces B-Rep fragility.

## 4.6 Wall, floor and boss variation

Global offset/thickening operations are often unreliable on complex imported castings. OCCT exposes thick-solid and offset operations, including joined construction, intersection controls and configurable joins, but failure handling remains necessary.[web:520][web:522][web:526]

Represent approved thickness variation as a bounded continuous field:

\[
t(u,v)=t_0(u,v)+\sum_k a_k\phi_k(u,v)
\]

Where:

- \(t_0(u,v)\) is baseline thickness.
- \(\phi_k(u,v)\) are localized smooth basis functions.
- \(a_k\) are bounded design variables.

Ensure each basis function decays to zero near protected boundaries. Apply changes region-wise and reconstruct transition surfaces using a controlled blending strategy.

Recommended sequence:

1. Apply face-family or region-level thickness changes.
2. Apply smoothly blended localized changes.
3. Rebuild transition geometry.
4. Sew and validate.
5. Rematch protected geometry.
6. Reject if any protected surface is displaced beyond tolerance.

## 4.7 Hole patterns

Hole variables should include:

- Hole count.
- Pattern center.
- Pattern orientation.
- Diameter.
- Depth and through/blind condition, where allowed.
- Pitch.
- Angular position.
- Circular, linear, staggered and free-point distributions.
- Minimum edge distance.
- Minimum distance to ribs, holes, bosses and protected regions.

For free-point patterns, use constrained Poisson-disk sampling on an approved plate region. This creates a controlled spatial spread without collapsing into a few standard bolt-circle templates.

## 4.8 Conditional pads

Pads should be generated from explicit conditions:

```text
IF a rib terminates at a wall
AND local wall thickness is below a configured threshold
AND predicted junction severity exceeds a configured limit
THEN a local pad is eligible
ELSE no pad is generated
```

Pads require limits on footprint, height, taper, draft, root fillet and local mass concentration. They must be included in hot-spot and section-thickness checks.

---

## 5. Rules and provenance

## 5.1 Rule DSL

Compile source drawings, engineer selections and process constraints into a versioned declarative study language:

```yaml
study:
  id: gearbox_housing_modal_v7
  version: 7
  seed: 918273
  units: mm
  pull_direction: [0, 0, 1]
  casting_process: green_sand

protected:
  - semantic_id: bearing_seat_02
    clearance_mm: 2.0
    max_surface_deviation_mm: 0.005

ribs:
  count: [3, 18]
  thickness_mm: [3.5, 9.0]
  height_mm: [8.0, 42.0]
  side_draft_deg: [1.5, 4.0]
  longitudinal_taper: [0.70, 1.00]
  root_fillet_mm: [2.5, 8.0]
  min_sand_gap_mm: 8.0
  max_aspect_ratio: 8.0
  forbid_x_junctions: true

materials:
  catalogue_version: cast_materials_2026_04
  allowed:
    - AlSi7Mg
    - AlSi10Mg
    - EN_GJL_250

conditional_rules:
  - if: rib.wall_junction_ratio > 1.6
    then:
      require_one_of: [thin_rib, local_pad, junction_offset]
```

Rule categories:

| Type | Example |
|---|---|
| Hard rule | Do not alter bearing seat `bearing_seat_02`. |
| Range rule | Rib root thickness must be 3.5–9.0 mm. |
| Relational rule | Rib thickness must not exceed a configured fraction of supporting wall thickness. |
| Conditional rule | Add an offset or pad when a stiffener meets a thin wall. |
| Preference | Avoid visible near-parallel rib crowding. |
| Study metric | Require minimum topology count and descriptor-space coverage. |

## 5.2 Material catalogue

Treat material as a controlled catalogue rather than a text field. Each entry should include:

- Alloy identity and applicable standard.
- Density.
- Elastic modulus.
- Poisson ratio.
- Yield/ultimate strength model and temperature range.
- Thermal expansion, conductivity and heat capacity where required.
- Casting-process compatibility.
- Minimum section and draft guidance.
- Solver material-card mapping.
- Source and applicability metadata.

Public data sources are useful as research inputs but require validation for a particular foundry, heat treatment and casting process. NIST provides materials data resources and property data summaries, while open datasets and repositories can provide machine-readable starting points.[web:602][web:607][web:609]

A material catalogue record should include source, condition and uncertainty; a single nominal Young’s modulus is not sufficient for high-consequence simulation labels.

---

## 6. Deterministic validation funnel

The campaign should reject invalid designs as early as possible. A candidate should only enter a costly mesher or solver after cheaper gates pass.

| Stage | Relative cost | Main checks |
|---|---:|---|
| Rule/genome validation | 1 | Domains, graph rules, forbidden combinations, unit/schema checks. |
| Proxy geometry | 5 | Bounding-box collisions, preliminary clearance, edge crossings, rough draft and span checks. |
| Exact B-Rep build | 50 | Booleans, sewing, solid closure, semantic rematching. |
| Manufacturing checks | 100 | Draft, undercuts, thickness, sand clearance, junction severity. |
| Coarse mesh | 300 | Meshability, basic boundary tagging and volume sanity. |
| Production mesh | 1,000 | Frozen analysis mesh criteria. |
| Solver | 2,000–20,000 | Convergence, results completeness and physics-specific QC. |

The ratios are planning principles rather than universal benchmarks. Profile the target housing before defining campaign capacity.

## 6.1 Exact CAD validity

Required checks:

- Candidate is a non-null solid.
- Positive volume.
- Expected solid count.
- Closed and oriented shells.
- No free edges.
- No invalid wires.
- No self-intersecting wires.
- No invalid tolerance state.
- No protected-face deviation above permitted limit.
- Successful STEP write and re-read.
- Successful tessellation.

OCCT’s B-Rep validation status includes conditions such as free edges, invalid or intersecting wires, unorientable shapes, nonclosed shapes and invalid orientation states.[web:619]

## 6.2 Draft and undercuts

Draft must be checked against the declared pull direction and parting/core assumptions. Face-angle thresholds alone are insufficient because another portion of geometry may block withdrawal.

Validation procedure:

1. Tessellate the candidate at controlled resolution.
2. Classify surfaces relative to pull direction.
3. Shoot rays along positive and negative pull directions from sampled surface locations.
4. Detect self-occlusion, multiple intersections and trapped geometry.
5. Account for explicitly permitted core regions.
6. Return a per-face draft/undercut diagnostic map.

PyVista exposes ray tracing over surface meshes, while Open3D provides point-cloud nearest-distance tools useful for geometric comparisons.[web:517][web:514]

Production implementation should use a BVH-accelerated ray engine such as Embree, CGAL, FCL or equivalent rather than pure Python loops.

## 6.3 Wall thickness

Use two independent estimators:

- Normal-ray intersections on B-Rep or fine triangulation.
- Signed-distance or medial-field estimates from a mesh.

Trimesh exposes signed-distance queries for sampled points relative to a mesh, which can support clearance and thickness analyses.[web:508]

Store not just global minimum thickness, but:

- Minimum thickness.
- First, fifth and tenth percentile thickness.
- Regional thickness statistics.
- Maximum gradient in thickness.
- Thin-area fraction.
- Disagreement between B-Rep and mesh-based estimators.

Reject candidates with local wall thinning below process-specific constraints, opposing-face intersections, abrupt thickness jumps or near-zero sliver regions.

## 6.4 Hot spots and junctions

Before expensive solidification simulation, calculate a conservative geometric hot-spot proxy:

- Largest local inscribed-sphere diameter.
- Local casting modulus proxy: volume divided by cooling surface area.
- Thickness ratio across a junction.
- Count and angular distribution of intersecting sections.
- Boss/rib alignment across the same wall.
- Junction compactness.
- Distance to candidate feed direction or riser-access area.

Casting references consistently emphasize uniform section thickness, smooth transitions and care with rib/boss junctions. T and X junctions create local thickness concentrations; offset or staggered alternatives and cored intersections are common mitigations.[web:546][web:547][web:549][web:551]

An X-crossing should therefore be forbidden by graph construction, not merely detected as a downstream geometry defect.

A later qualification tier may run higher-fidelity thermal solidification simulations using OpenFOAM, MOOSE or a validated in-house enthalpy formulation. Use it initially for high-risk candidates, selected representatives and calibration of the proxy—not necessarily for every candidate.

## 6.5 Sand and core clearance

Assess manufacturable clearance through geometry rather than only rib-centreline distance:

1. Dilate each rib by half the required sand-clearance distance.
2. Test dilated geometry against adjacent ribs, walls, bosses and protected areas.
3. Sample planes normal to pull direction.
4. Identify narrow wedges and enclosed channels.
5. Determine whether sand/core volumes have accessible paths to an approved mould/core boundary.

This avoids a common false pass: two ribs can meet centreline-spacing limits yet form an unmanufacturable narrow wedge.

## 6.6 Protected geometry invariance

For every protected semantic entity:

- Rematch the generated surface to its baseline counterpart.
- Compare cylinders by radius, axis, coaxiality and center shift.
- Compare planes by normal, plane offset and bounded sampled distance.
- Compare freeform faces with bidirectional sampled distance.
- Verify protected hole axes, diameters and thread-designated zones.
- Verify clearance envelope remains empty.

The check should yield a binary pass/fail plus a numerical deviation report.

---

## 7. Explicit diversity and coverage

## 7.1 Candidate descriptor

For every candidate, compute a mixed descriptor:

\[
z = [z_{topology},z_{attachments},z_{angles},z_{sizes},z_{walls},z_{holes},z_{pads},z_{material}]
\]

Suggested descriptor components:

| Group | Descriptor examples |
|---|---|
| Topology | Canonical semantic edge set, node degree histogram, graph spectral values, Weisfeiler-Lehman graph features. |
| Attachments | Region-pair identity, endpoint coordinates in local UV parameterization, anchor distribution moments. |
| Angles | Relative-to-reference and relative-to-pull-direction angle histograms; largest angular gap. |
| Rib geometry | Count, span, path curvature, height, base/top thickness, taper and fillet distributions. |
| Wall field | Basis-function coefficients, regional average/minimum thickness, thickness gradients. |
| Holes | Counts, diameter histogram, spatial moments, minimum spacing and pattern type. |
| Pads | Count, location, size and junction class. |
| Material | Categorical material label and, separately, relevant physical-property vector. |

## 7.2 Mixed distance

Define an engineer-calibrated mixed distance:

\[
d(i,j)=w_Td_{graph}+w_Pd_{position}+w_Ad_{angle}+w_Sd_{size}+w_Wd_{wall}+w_Hd_{holes}+w_Md_{material}
\]

The geometric diversity threshold should not be satisfied merely by changing material. Use a separate geometric distance gate and a total-design distance gate.

Potential implementations:

- NetworkX and GraKeL for graph features.
- SciPy and scikit-learn for normalized continuous descriptors.
- POT for distributional/optimal-transport distances.
- FAISS for scalable nearest-neighbour retrieval.
- Exact graph-edit distance only for local checks, not the full population.

Calibrate weights and acceptance thresholds with engineer-labelled pairs:

- Duplicate.
- Different but still too similar.
- Meaningfully different.
- Radically different.

The labels produce an empirical, defensible minimum meaningful-difference threshold.

## 7.3 Quality-diversity search

Quality-diversity search should replace “generate 4,000 random samples.” QD seeks collections where individual candidates are good and the collection spans a descriptor/behaviour space.[web:499][web:501]

Use a centroidal Voronoi tessellation archive over a selected low-dimensional measure vector, for example:

```text
measures = [
  rib_count,
  topology_complexity,
  angle_entropy,
  wall_mass_delta,
  boss_connection_count,
  hole_pattern_complexity,
  pad_count
]
```

`pyribs` CVT archives divide a measure space into a fixed number of Voronoi cells by sampling and clustering centroids. Candidates are assigned to their nearest measure-space centroid.[web:498]

Use richer graph and geometry descriptors for final deduplication and separation; use a compact measure vector for the archive itself.

## 7.4 Emitter portfolio

| Emitter | Purpose |
|---|---|
| Random graph | Discover previously unseen connection patterns. |
| Rewire | Alter what features are tied together. |
| Anchor mutation | Change attachment positions and angles without changing graph edges. |
| Geometry mutation | Change rib section, height, taper, draft and fillet attributes. |
| Wall-field mutation | Change permitted local and global thickness patterns. |
| Hole/pad mutation | Explore secondary feature variations. |
| Combination emitter | Deliberately modify multiple independent feature classes. |
| Empty-cell emitter | Target unoccupied QD archive cells. |
| Boundary emitter | Probe near constraint boundaries. |
| Repair emitter | Search local feasible neighbourhoods around classified failures. |

A learned feasibility classifier can prioritize expensive evaluations, but must not become an authority. Reserve a fixed exploration fraction for uncertain and predicted-low-feasibility candidates, otherwise the system will systematically abandon difficult but feasible regions.

## 7.5 Final 4,000 selection

After collecting a substantially larger population of valid mesh-and-solve candidates:

1. Deduplicate by canonical recipe and geometry fingerprint.
2. Enforce minimum topology representation or quotas where required.
3. Keep representatives from occupied feasible CVT cells.
4. Apply greedy farthest-point selection under the mixed distance.
5. Reject candidates below geometric or complete-design nearest-neighbour thresholds.
6. Backfill from underrepresented cells.
7. Verify marginal distributions: angle, count, topology, thickness, holes, pads and material.
8. Rerun every deterministic validation on the frozen final selection.

For 4,000 members, the complete pairwise distance matrix has 16 million entries, which is manageable. Use approximate nearest-neighbour retrieval only for larger preselection pools, followed by exact local comparisons.

## 7.6 Coverage measurement

“Uniform coverage” is meaningless without a reference measure and a definition of feasible space.

Estimate reachable coverage:

1. Generate a large broad symbolic proposal pool.
2. Apply deterministic rule and cheap geometric feasibility filtering.
3. Calculate behavioural measures for feasible candidates.
4. Create the CVT reference tessellation.
5. Estimate reachable cells through repeated exploration.
6. Calculate final occupancy only against reachable cells.
7. Flag persistent empty cells as likely infeasible or weakly explored.

Never claim coverage relative to the rectangular parameter bounding box because many mixed discrete-continuous configurations are impossible.

---

## 8. Meshing and solver readiness

## 8.1 Meshing stack

Use three meshing routes for robustness:

| Priority | Tool | Role |
|---|---|---|
| Primary | Gmsh with HXT | CAD-aware production meshing and physical-group support. |
| Independent secondary | Netgen | STEP/B-Rep based automatic tetrahedral meshing. |
| Tessellated fallback | fTetWild/TetWild | Robust tetrahedralization for difficult triangulated geometry. |

Netgen is an open-source automatic 3D tetrahedral mesh generator with Python scripting, geometry-kernel support for IGES and STEP, mesh optimization and refinement capabilities.[web:536][web:538]

Gmsh includes HXT support; published HXT benchmarking describes high-throughput tetrahedral refinement and reports speed and quality advantages under the tested benchmark conditions.[web:534][web:543]

TetWild and fTetWild convert triangle surface meshes into tetrahedral volume meshes and were designed for robust processing of imperfect inputs.[web:530][web:541][web:542]

### 8.1.1 Mesh strategy

Use primary CAD meshing for the authoritative dataset. Preserve physical groups for loads, constraints and result extraction.

Use a fallback mesher only when:

- The candidate’s exact B-Rep is valid.
- The primary mesher fails with a classified known failure.
- Boundary semantic labels can be transferred with verified error limits.

Tessellated fallback paths must not silently replace exact CAD truth. Record fallback status as a dataset feature.

## 8.2 Mesh quality gates

Record and threshold:

- Element count.
- Minimum and percentile scaled Jacobian.
- Aspect ratio.
- Minimum dihedral angle.
- Sliver fraction.
- Disconnected components.
- Boundary-group coverage.
- CAD-to-mesh volume discrepancy.
- Protected-face projection error.
- Mesher, version and full options.

Every design that is to train a surrogate must mesh under the frozen production settings. Do not hand-tune individual failed candidates into the dataset.

## 8.3 Solver stack

For linear static, modal and linear dynamic housing studies, CalculiX is a strong open-source baseline. Its modal dynamic analysis uses modes obtained in a preceding frequency extraction and supports direct or Rayleigh damping.[web:555][web:556][web:558]

Suggested solver roles:

| Solver | Best use |
|---|---|
| CalculiX | Automated Abaqus-like linear static, modal and many structural workflows. |
| Code_Aster | Advanced structural workflows and mature open-source CAE capabilities. |
| FEniCSx | Custom variational formulations and research-grade PDE integration. |
| SfePy | Rapid Python-native finite-element prototypes and coupled PDE experiments. |
| OpenRadioss | Explicit nonlinear/transient structural studies. |

FEniCSx is an open-source finite-element library with Python and C++ components.[web:566] SfePy supports coupled PDE systems through FEM in 1D, 2D and 3D and can serve as a Python package for custom solver applications.[web:554][web:567]

## 8.4 Solver quality checks

The study template—not each candidate—owns load cases, boundary-condition semantics, contact settings, solver controls and output requirements.

Required checks include:

- Solver return code.
- Matrix singularity and rigid-body-mode detection.
- Convergence status.
- NaN/Inf detection.
- Expected output completeness.
- Mass and volume sanity.
- Boundary-condition label coverage.
- Displacement and stress plausibility ranges.
- Modal frequency count and modal mass participation where applicable.
- Energy checks where applicable.

Record all failure classes for downstream learned triage and repair policies.

---

## 9. Distributed execution and data operations

## 9.1 Orchestration

Use a two-level pattern:

| Layer | Recommended tool | Role |
|---|---|---|
| Campaign workflow | Prefect or Dagster | Dependency orchestration, retries, caching, lineage, monitoring and review events. |
| Parallel execution | Ray | Distributed CAD, validation, meshing and solver tasks. |

Prefect supports resilient workflow features such as scheduling, caching, retries and self-hosted monitoring.[web:570] Dagster provides declarative asset-oriented orchestration with lineage, observability and testability in an Apache 2.0 licensed open-source core.[web:571][web:576]

Ray supports asynchronous tasks with CPU, GPU and custom resource requirements; it can distribute work based on resource feasibility, locality and spread strategies.[web:569][web:579]

### 9.1.1 Worker design

Recommended worker classes:

```text
InputNormalizerWorker
SemanticRegionWorker
RuleCompilerWorker
TopologyProposalWorker
ProxyValidatorWorker
CadBuilderWorker
CastabilityValidatorWorker
MeshWorker
SolverWorker
ResultQcWorker
DescriptorWorker
ArchiveWorker
RepresentativeSelectionWorker
ProvenanceWriterWorker
```

Keep OCCT/CAD operations isolated in process workers. Cache baseline geometric queries and immutable source artifacts, but never reuse a partially mutated CAD session across candidates.

## 9.2 Artifact storage and versioning

Use:

- Git for source code, rule DSL, study definitions and solver templates.
- DVC initially for dataset artifacts, pipeline reproduction and ML experiments.
- lakeFS for object-store-scale data branching, versioning and atomic operations when campaigns become large.
- S3-compatible object storage for STEP, meshes, solver outputs and visualizations.
- PostgreSQL for manifests, status, metrics and provenance indexes.

DVC is intended to version data and models in connection with Git, describe reproducible pipelines and compare experiments.[web:478] lakeFS provides Git-like versioning for object-storage-based data repositories and is Apache 2.0 licensed.[web:480][web:486]

Review object-store licensing carefully. Current MinIO community source is AGPLv3 and its project explicitly warns that commercial/proprietary usage must be evaluated for AGPL obligations.[web:481]

## 9.3 Canonical manifest

Every design needs an immutable manifest:

```json
{
  "study_id": "gearbox_housing_modal_v7",
  "study_version": 7,
  "study_commit": "git-sha",
  "ruleset_hash": "sha256:...",
  "source_step_hash": "sha256:...",
  "drawing_hashes": ["sha256:..."],
  "material_catalog_hash": "sha256:...",
  "solver_template_hash": "sha256:...",
  "candidate_index": 1729,
  "candidate_seed": 483920174,
  "genome": {},
  "repair_operations": [],
  "cad_kernel": {},
  "mesh_settings": {},
  "solver_settings": {},
  "validation_results": {},
  "artifact_hashes": {},
  "created_at": "..."
}
```

## 9.4 Deterministic seeds

Derive stage-specific random streams from stable identity inputs:

\[
s_k=H(\text{study ID},\text{study version},\text{campaign seed},\text{candidate index},\text{stage name})
\]

Canonicalize manifests before hashing:

- Stable key ordering.
- Explicit units.
- Defined float serialization.
- No implicit default settings.
- Pinned container images and package versions.

The canonical candidate identity is the hash of the recipe, not a sequential filename or runtime execution order.

---

## 10. Engineer review loop

## 10.1 Representative selection

The engineer should see a deliberately diverse review batch, not random samples:

- 12 medoids spanning major valid regions.
- 4 maximum-novelty cases.
- 2 near-hard-constraint-boundary cases.
- 2 high-uncertainty or model-disagreement cases.

Each card should show:

- Baseline/candidate overlay.
- Highlighted changed geometry.
- Rib graph overlay.
- Genome and values.
- Protected-face verification.
- Minimum wall and sand clearance.
- Draft and undercut summary.
- Junction/hot-spot proxy map.
- Mesh and solver outcome.
- Nearest-neighbour design and mixed distance.
- Source and provenance of every active rule.

## 10.2 Structured engineer actions

| Action | System effect |
|---|---|
| Accept | Positive preference/training label. |
| Reject: manufacturability | Propose a hard manufacturing rule or revise process assumptions. |
| Reject: functional | Propose protected/exclusion region or relational rule. |
| Reject: appearance/engineering judgement | Preference label, not immediate hard rule. |
| Protect region | Create protected semantic region and clearance rule. |
| Change range | Update range constraint with review provenance. |
| Forbid connection | Add graph-edge exclusion. |
| Require connection | Add graph feasibility or quota condition. |
| Similar/redundant | Recalibrate diversity distance or descriptor weights. |

An objection should become a proposed rule first. The engineer should approve its scope: current study only, specific housing family, material/process family, or global policy.

## 10.3 Learning from feedback

Use feedback in two separate models:

1. **Hard-rule compiler:** only for explicit engineer-confirmed constraints.
2. **Preference/ranking model:** for subjective but recurring engineering judgement.

Never translate every rejection directly into a global hard constraint. Doing so causes the feasible search space to collapse around early reviewer preferences.

---

## 11. Success measurement

| Metric | Definition |
|---|---|
| Connection diversity | Number of unique canonical semantic rib-edge sets. |
| Fine topology diversity | Number of graph hashes including split/junction/path information. |
| Topology entropy | Entropy over meaningful graph families and connection-pair distributions. |
| Coverage | Occupied reachable CVT cells divided by estimated reachable reference cells. |
| Angle spread | Entropy, circular discrepancy and maximum empty interval in rib-angle distribution. |
| Separation | Minimum and fifth-percentile nearest-neighbour mixed distance. |
| Geometric duplicate rate | Fraction below calibrated geometric meaningful-difference threshold. |
| Build rate | Valid exact B-Rep builds divided by exact build attempts. |
| Manufacturing pass rate | Designs passing all process checks divided by valid B-Reps. |
| Mesh rate | Production-quality meshes divided by manufacturing-valid designs. |
| Solve rate | QC-passing solver runs divided by production meshes. |
| Dataset yield | Final usable variants divided by total attempted candidates. |
| Throughput | Wall-clock time from frozen input to 4,000 final candidates. |
| Acceptance | Engineer-approved representatives divided by reviewed representatives. |
| Improvement | Build, manufacturing, mesh, solve and acceptance improvement across rounds. |

### 11.1 Proposed initial gates

These must be calibrated on target housings, but a credible initial program should aim for:

- Several hundred unique canonical rib connection patterns in an early production campaign.
- A path to more than 1,000 patterns as semantic region granularity and legal anchors grow.
- No final pair below the calibrated geometric separation threshold.
- No hard-rule violations in the frozen final 4,000.
- Final candidates all build, mesh and solve under frozen production settings.
- Positive trend in build rate, pass rate and engineer acceptance across review rounds.
- Reproduction of the canonical recipe set from the same study version and seed on a clean pinned environment.

---

## 12. Recommended open-source stack

| Capability | Primary recommendation | Supporting options |
|---|---|---|
| B-Rep kernel | Open CASCADE Technology | `pythonocc-core`, CadQuery, build123d |
| STEP healing/validity | OCCT Shape Healing and BRep checks | Custom OCCT wrappers |
| Geometry processing | CGAL | Trimesh, Open3D, PyVista |
| Collision/ray checks | Embree/FCL/CGAL BVH | PyVista ray queries for prototypes |
| Constraint solving | OR-Tools CP-SAT | Z3 |
| Graph methods | NetworkX, GraKeL | PyTorch Geometric for learned embeddings |
| QD optimization | pyribs | QDax for JAX/GPU research |
| Multiobjective methods | pymoo | Custom constrained evolutionary operators |
| Primary meshing | Gmsh/HXT | Netgen |
| Robust fallback meshing | fTetWild/TetWild | CGAL repair/preprocessing |
| Structural simulation | CalculiX | Code_Aster, FEniCSx, SfePy, OpenRadioss |
| Workflow orchestration | Prefect or Dagster | Argo Workflows for Kubernetes-heavy operation |
| Distributed execution | Ray | Slurm/Kubernetes backend integration |
| Artifacts/data versioning | Git + DVC | lakeFS + S3-compatible storage |
| Metadata | PostgreSQL | DuckDB/Parquet for analytical extracts |
| Schemas/units | Pydantic + JSON Schema + Pint | Protocol Buffers where high-throughput needed |
| Drawing interpretation | ezdxf, PyMuPDF, OpenCV, Tesseract/PaddleOCR | Reviewable LLM/VLM extraction layer |
| Dashboard | FastAPI + React/Three.js | ParaView/VTK exports for inspection |

### 12.1 Licensing note

Licensing must be reviewed before product deployment. Examples from current project documentation: Netgen describes itself as LGPL, lakeFS as Apache 2.0, and MinIO source as AGPLv3 with explicit warnings concerning proprietary/commercial use.[web:536][web:480][web:481]

---

## 13. Machine learning components

## 13.1 Where ML helps

ML should initially improve throughput and exploration efficiency, not be trusted as the final geometric/manufacturing authority.

| Component | Inputs | Output | Authority |
|---|---|---|---|
| Semantic feature recognizer | B-Rep graph and drawing evidence | Proposed protected/mutable labels | Proposal only |
| Build feasibility predictor | Genome, proxy metrics, local geometry | Probability/failure class | Queue prioritization |
| Mesh feasibility predictor | Geometry descriptors, clearance metrics | Mesh failure/quality probability | Queue prioritization |
| Castability surrogate | Thickness/junction features, qualified labels | Hot-spot/defect-risk score | Screening, never sole approval |
| Physics surrogate | Mesh/B-Rep graph, material, loads | Stress/modal/thermal predictions | Active-learning prioritization |
| Preference ranker | Review labels and descriptors | Acceptance score | Representative ordering |
| Repair policy | Failure type plus local design state | Proposed deterministic edit | Proposal only |

## 13.2 Training sources

Open CAD datasets can help pretrain generic B-Rep and feature models, but they do not replace housing-specific labels.

- Fusion 360 Gallery contains B-Rep, mesh, segmentation and construction-sequence information, including thousands of human-created designs and an extended STEP collection.[web:581][web:583][web:590]
- The ABC dataset contains more than one million CAD models with parametrized geometry and annotations useful for geometric deep learning.[web:586]
- AAGNet provides methods and datasets for machining-feature recognition using geometric attributed adjacency graphs, including evaluation on MFCAD/MFCAD++ and MFInstSeg.[web:588][web:589]

Fine-tune semantic segmentation on manually labelled cast housings that distinguish:

- Machined faces.
- Bearing bores.
- Seal interfaces.
- Cast walls.
- Bosses.
- Existing ribs.
- Candidate rib zones.
- Keep-outs.
- Tool/access zones.

## 13.3 Active learning policy

Use ML uncertainty to allocate expensive solver budget, but keep a fixed nonzero random/QD novelty budget:

```text
expensive-evaluation budget =
  high predicted quality/diversity candidates
  + high uncertainty candidates
  + under-covered archive cells
  + fixed random exploration fraction
```

Without the last term, the feasibility and surrogate models can progressively erase unusual yet valid designs.

---

## 14. Implementation roadmap

## Phase 0: Study contract

- Choose one representative cast housing and one structural study.
- Freeze casting process assumptions, pull direction, parting/core assumptions and allowed material catalogue.
- Define source-file acceptance, protected regions, solver load cases and production mesh settings.
- Decide the exact definition of “same design” and “meaningfully different.”

**Exit criterion:** An approved study manifest exists and is reproducible from source files.

## Phase 1: Baseline reliability

- Implement STEP input normalization and bounded healing.
- Extract B-Rep topology and geometric signatures.
- Build engineer UI for protected/mutable/exclusion region approval.
- Implement rule DSL and provenance.
- Establish baseline meshing and solver deck.

**Exit criterion:** The unchanged baseline round-trips, meshes and solves automatically; protected entities are rematched correctly after STEP export/import.

## Phase 2: Generator MVP

- Build semantic region graph and legal attachment domains.
- Build potential connection graph.
- Implement arbitrary rib-graph generation.
- Implement drafted/tapered rib primitives, local fillets and conditional pads.
- Add controlled hole patterns and limited region-wise wall/boss thickness variation.
- Implement rule, proxy collision and exact CAD gates.

**Exit criterion:** Hundreds of valid B-Rep variants with visibly independent topology, angle, position and size variation.

## Phase 3: Castability and diversity

- Add pull-direction, undercut, wall-thickness, sand-clearance and junction-risk validators.
- Define mixed descriptors and engineer-pair calibration workflow.
- Integrate pyribs CVT archive and portfolio emitters.
- Implement final farthest-point selection.
- Build review cards and representative selection.

**Exit criterion:** A pilot set demonstrates measured topology diversity, broad angle coverage and no identified near-duplicates.

## Phase 4: Simulation productionization

- Integrate Gmsh/HXT primary meshing and independent fallback path.
- Add physical-group remapping and boundary label QC.
- Automate CalculiX/target solver decks.
- Implement result QC, retry policy and failure taxonomy.
- Scale candidate oversampling to reliably produce 4,000 fully validated designs.

**Exit criterion:** One end-to-end 4,000-design campaign with frozen settings and complete provenance.

## Phase 5: Learning acceleration

- Train build and mesh feasibility classifiers.
- Train engineer preference ranker.
- Calibrate a manufacturing-risk surrogate using trusted labels.
- Train structural surrogate only after sufficient verified solve data exists.
- Introduce active learning and failure-specific deterministic repairs.

**Exit criterion:** Measurable reduction in wasted expensive evaluations without reduced coverage or increased escaped invalidity.

---

## 15. Failure modes and controls

| Failure mode | Cause | Control |
|---|---|---|
| Pattern-family bias | Generator selects only a few named templates | Arbitrary graph generation and explicit coverage archive. |
| Topological naming drift | B-Rep IDs change after Boolean operations | Semantic signatures and post-build rematching. |
| False diversity | Material or tiny parameter differences appear diverse | Mixed geometric/topological descriptor and calibrated separation gate. |
| Coverage illusion | Measuring against impossible bounding-box space | Estimate feasible/reachable reference cells. |
| Overhealing | Automated healing masks invalid generated geometry | Bounded repair policy; reject excessive repair and protected changes. |
| Learned-validator leakage | ML model becomes de facto validity authority | Deterministic validators remain mandatory. |
| Mesh label loss | Tessellation/fallback breaks feature identity | Semantic boundary projection and group-coverage checks. |
| Parallel nondeterminism | Runtime scheduling changes random generation | Stage-specific deterministic seeds and canonical artifacts. |
| Process ambiguity | Pull direction/core/parting strategy unspecified | Campaign cannot launch without explicit process contract. |
| Reviewer overconstraint | Every subjective rejection becomes hard global rule | Separate confirmed hard rules from preference learning. |
| Dataset contamination | Per-candidate manual meshing/solver tuning | Frozen production settings and explicit fallback flags. |

---

## 16. Practical conclusion

A credible Physical-AI system for cast-housing generation is a **constraint-driven QD CAD-and-CAE pipeline**, not a one-shot generative model. The essential ingredients are:

1. Semantic decomposition of the baseline STEP and drawing into protected, mutable and excluded regions.
2. A graph grammar where arbitrary allowable rib-to-region connections and free attachment positions define topology.
3. Continuous geometry fields for thickness, height, taper, draft, fillets, wall movement, holes and pads.
4. Explicit rule compilation and source provenance.
5. Deterministic B-Rep, draft, undercut, thickness, sand-clearance and junction/hot-spot validation.
6. Production meshing and solve gates for every final training-data candidate.
7. Quality-diversity search and farthest-point selection to directly optimize spread rather than assume it.
8. Immutable manifests, stage-specific seeds and versioned artifacts for repeatability.
9. A focused engineer review loop that transforms objections into approved rules or learned preferences.

The best initial implementation is a single-housing, single-study pilot. Do not begin by training a geometry generator. First build a deterministic, semantically constrained generator and validator that can reliably create a few hundred rich, valid examples. Then scale the QD archive, worker pool and learned feasibility models until a reproducible 4,000-design campaign is routine.
