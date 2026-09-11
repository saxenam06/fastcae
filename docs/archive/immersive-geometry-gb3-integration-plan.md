# Immersive Geometry Integration Plan for `ui_agentic` and GRC GB3

## Executive decision

**Immersive Geometry must be a first-class input artifact and a first-class platform capability—not a plugin panel and not a replacement for CAD.** For the GRC GB3 demonstration, it should become the visual and semantic layer that turns the already-existing CAD/FEM/design-space pipeline into an inspectable spatial engineering workspace.

The correct product statement is:

> The platform compiles CAD, drawings, FEM setup, simulation results, and immersive geometry into a versioned Design Space Object. Agents reason over that object; users inspect it spatially; solvers and surrogates evaluate candidate variants produced from it.

This preserves the key technical boundary: an immersive representation is excellent for **viewing, spatial querying, presenting, annotating, and interacting with very large geometry**, but it is not authoritative CAD, it must not become the manufacturing geometry, and it cannot make topology-changing CAD operations safe by itself.

The current handbook establishes the same boundary in a different form: B-rep/CAD remains the manufacturing representation; a continuous Wendland RBF morph is valid for shape changes but cannot add or remove a rib; topology change requires a discrete CAD operation. The later SDF representation is explicitly an eventual search representation beside—not in place of—the B-rep. [file:79][file:73]

---

## 1. What “immersive geometry” should mean here

The phrase can mean several technically different things. The platform should support all three over time, but the GRC GB3 demo needs only the first two initially.

| Level | Representation | Main purpose | GRC GB3 priority | Cannot be used for |
|---|---|---|---|---|
| **A. Immersive 3D scene** | Progressive GLB/GLTF mesh, hierarchy, semantic IDs, LODs, pickable regions | Browser viewing, selection, clipping, exploded view, collaboration, agent handoff | Build now | Exact CAD editing, manufacturing release |
| **B. Semantic spatial twin** | Entity/identity graph connected to faces, FEM sets, drawing callouts, result fields, design-space controls | Cross-artifact traceability and semantic hover | Build now; this is the moat | Replacing validated solver results |
| **C. Differentiable geometric field** | SDF/occupancy + surface samples / mesh graph + morph basis | Surrogate inference, gradients, high-throughput exploration, future topology search | Build after scalar surrogate/validation | Directly issuing a B-rep manufacturing model |

The product must never claim “we convert arbitrary CAD to a generative geometry model and optimize it.” That would overstate what the present corpus supports. Your corpus has 490 variants of one casting and currently supports a housing-specific claim; it does **not** yet demonstrate cross-geometry generalization. [file:69][file:66]

A defensible near-term claim is:

> “The platform ingests an engineering assembly into a spatially inspectable design-space model. It can explain which regions are controlled, mapped, movable, uncertain, or currently unsupported; it can generate and evaluate governed design variants through the same model.”

---

## 2. Why this fits the GRC GB3 project

GB3 is unusually good as a platform demo because it has all the artifact classes a real customer will have:

- A large industrial gearbox-housing B-rep / STEP baseline.
- Released drawings that define selected frozen interfaces, datums, bores, bolt patterns, seals, and machining intent.
- FEM setup, named groups, bore couplings, loads, meshes, and solver outputs.
- A solved design corpus with metrics, geometry variants, mesh quality and solver provenance.
- A design space with two fundamentally different design levers: discrete rib/topology choices and continuous morph amplitudes. [file:79]
- Evidence-backed limitations: some geometry has drawing evidence, some regions are selected by geometry rules and therefore remain `ASSUMED`; the UI should expose that rather than conceal it. [file:73]

The GB3 geometry should not be presented as “a gearbox optimizer.” It should be presented as one loaded **workspace** called something like:

```text
Workspace: GRC GB3 rear housing
Study: Joint stiffness / robustness design-space exploration
Revision: PoC geometry baseline
```

The same workspace shell must be able to host:

```text
Bracket assembly
Battery cold plate
Pump/manifold housing
BIW substructure
Heat-exchanger casing
Gearbox rear housing
```

Only the artifact data and capability descriptors change.

---

## 3. Design Space Object: the integration backbone

The existing compiler framing is the correct foundation: inputs are B-rep, mesh, drawing sheets, FE setup, load case, and standards; passes build topology/identity, feature recognition, freeze inference, interface detection, RBF morph fitting, validity-limit measurement, and load basis selection; output is a typed and versioned Design Space Object. [file:73]

Make that implicit object explicit and persist it.

```python
class DesignSpaceObject(BaseModel):
    id: str
    workspace_id: str
    baseline_revision_id: str
    schema_version: str
    geometry_digest: str
    created_at: datetime

    source_artifacts: list[ArtifactRef]
    entity_graph: EntityGraphRef
    geometry_representations: GeometryRepresentations
    controls: list[DesignControl]
    constraints: list[Constraint]
    objectives: list[ObjectiveRef]
    load_basis: LoadBasisRef
    validity: ValidityManifoldRef
    cache_keys: CacheSet
    provenance: ProvenanceEnvelope

class GeometryRepresentations(BaseModel):
    brep: ArtifactRef                 # authoritative engineering geometry
    analysis_mesh: ArtifactRef        # authoritative solve mesh per variant
    immersive_scene: ArtifactRef      # GLB / scene manifest, LODs and pick IDs
    surface_samples: ArtifactRef | None  # surrogate-ready point set
    sdf: ArtifactRef | None             # later, optional search representation
```

### Required entity model

```python
class EngineeringEntity(BaseModel):
    id: str                            # e.g. GB3:region:outer_skin:003
    type: str                          # face, region, bore, bolt_group, rib, load_case, mesh_group
    label: str                         # domain-neutral display label
    stable_geometry_refs: list[str]    # B-rep face IDs + immutable baseline references
    scene_node_ids: list[str]          # GLTF pick mapping
    fem_refs: list[str]                # node/element-set/group IDs
    drawing_refs: list[DrawingRef]
    status: Literal['measured', 'derived', 'assumed', 'unresolved']
    confidence: float | None
    provenance: ProvenanceEnvelope
```

### Required control model

```python
class DesignControl(BaseModel):
    id: str
    kind: Literal['binary_topology', 'continuous_morph', 'material', 'load_weight']
    target_entity_ids: list[str]
    unit: str | None
    bounds: tuple[float, float] | None
    enum_values: list[str] | None
    authority: Literal['frozen', 'morphable', 'free', 'proposed']
    evidence_status: Literal['measured', 'derived', 'assumed']
    validity_rule: str
    generator: str                     # e.g. CAD fuse / RBF mode / load-basis weighting
    cache_scope: str
```

This schema is what the UI, agents, sampler, solver runner, and future surrogate all read and write. It is the technical mechanism that prevents `ui_agentic` from hardcoding GB3-specific concepts.

---

## 4. GB3 input-artifact manifest

Create a single machine-readable workspace manifest for the current GRC GB3 project. It can initially be hand-authored, but it must be byte-compatible with the outputs future automated ingesters will produce. The handbook already makes the same recommendation for a QIF-3.0-aligned drawing/constraint contract. [file:79]

```yaml
workspace:
  id: grc-gb3-rear-housing
  label: GRC GB3 rear housing
  domain: drivetrain-structural
  baseline: stripped-housing-poc

artifacts:
  - id: cad-baseline
    type: brep
    format: brep
    role: authoritative_geometry
    uri: object://grc-gb3/housingbaseline.brep

  - id: cad-production-reference
    type: step
    format: step
    role: reference_geometry
    uri: object://grc-gb3/production.step

  - id: drawing-254492-sheet-1
    type: drawing
    format: pdf
    role: released_interface_evidence
    uri: object://grc-gb3/254492-sheet-1.pdf

  - id: fem-setup
    type: fem_setup
    format: json
    role: solver_setup
    uri: object://grc-gb3/groups.json

  - id: load-basis
    type: load_basis
    format: npy
    role: unit_load_response_basis
    uri: object://grc-gb3/basis.npy

  - id: design-corpus
    type: simulation_corpus
    format: variant-json
    role: solved_design_history
    uri: object://grc-gb3/results/

  - id: immersive-scene
    type: immersive_geometry
    format: glb+manifest
    role: interactive_scene
    uri: object://grc-gb3/scene/gb3-baseline.glb
```

The manifest makes immersive geometry an explicit artifact, not an incidental frontend build output.

---

## 5. Technical architecture

```text
                           ┌─────────────────────────────────┐
                           │          ui_agentic             │
                           │  Entity index · Stage · Rail    │
                           └──────────────┬──────────────────┘
                                          │ HTTPS / SSE
┌─────────────────────────┐    ┌──────────▼──────────────────┐
│ Artifact storage        │    │ FastAPI platform API         │
│ B-rep / STEP / PDF      │◄──►│ capabilities / entities      │
│ mesh / atlases / GLB    │    │ design space / analysis      │
│ results / Zarr          │    │ campaigns / agent SSE        │
└─────────────────────────┘    └─────┬───────────┬───────────┘
                                      │           │
                        ┌─────────────▼───┐ ┌─────▼──────────────┐
                        │ Postgres         │ │ Agent runtime      │
                        │ metadata/prov.   │ │ LangGraph tools    │
                        └─────────────────┘ └─────┬──────────────┘
                                                   │ same HTTP APIs
               ┌───────────────────────────────────▼───────────────────────┐
               │ Engineering workers                                        │
               │ OCCT ingest · GLB export · RBF morph · Gmsh · Code_Aster  │
               │ scalar/field extraction · surrogate train/infer           │
               └───────────────────────────────────────────────────────────┘
```

### Open-source implementation choices

| Need | Recommended technology | Feasibility note |
|---|---|---|
| Authoritative CAD ingestion and face extraction | OCCT / OCP Python bindings | STEP/IGES/B-rep handling, geometry queries, boolean/fuse support are appropriate for the engineering back end |
| Browser immersive scene | Three.js + GLTFLoader + GLB export | Keep current renderer where possible; add progressive scene manifests and semantic pick IDs |
| CAD-to-browser conversion | OCCT tessellation → GLB, one material per semantic region or per encoded face-ID batch | Never use the GLB as the source for meshing or manufacturing |
| FEM field rendering | VTK.js or Three.js custom vertex textures / scalar LUT shader | Store scalar fields separately and bind them by node/triangle mapping, not only as baked colors |
| PDF drawing interaction | PDF.js + SVG/HTML leader-line overlay | Drawing callouts map to entity IDs, bbox and source citation |
| Spatial acceleration | BVH (`three-mesh-bvh`) in browser; `trimesh`/Embree server-side | Enables responsive ray picking, nearest-surface and clearance queries |
| Continuous morph | Existing SciPy sparse `splu` + `cKDTree` + Wendland C2 RBF | The handbook specifically chose this because it avoids dense-RBF memory blowups and supports a per-rib-config factorization reused across morphs. [file:79] |
| GPU geometry experiments later | NVIDIA Warp | Warp JIT-compiles Python kernels for CPU/GPU and supports differentiable kernels in ML pipelines. [web:89][web:93] |
| Surrogate model later | PyTorch + PhysicsNeMo DoMINO / Transolver-family experimentation | DoMINO is a geometry-informed point-cloud architecture that uses local geometry and global encoding for large-scale industrial simulation surrogates. Treat this as an architecture reference, not proof that it transfers to GB3 structural mechanics without validation. [web:85][web:86] |

---

## 6. GB3 geometry pipeline

### 6.1 Ingestion pipeline

```text
B-rep / STEP
  → OCCT import + heal
  → canonicalize and assign stable baseline entity IDs
  → extract faces, surfaces, bores, flange patterns, axes, regions
  → tessellate to high / medium / low LOD meshes
  → encode entity/face mapping in scene manifest
  → export GLB + metadata
  → build entity graph edges to drawing and FEM artifacts
  → produce Design Space Object version 1
```

### 6.2 Stable identity: the hard requirement

Do not assume raw OCCT face indices survive topology edits, healing, B-rep re-export, or boolean fuse. For GB3, give every baseline face/region a persistent application-level ID and record the method that resolves it.

Recommended resolver stack, in this order:

1. **Exact baseline face digest**: canonicalized surface type, trimmed-UV bounds, area, centroid, principal directions, adjacency signature.
2. **Geometric fingerprint fallback**: location/orientation/area/curvature and adjacent-face signature.
3. **Region rule fallback**: named rule such as “outward-facing surfaces within Z band, excluding frozen interfaces.”
4. **Human resolution required**: if confidence remains below threshold, label `unresolved`, show it in the UI, and do not let an agent assume it is safe to morph.

A morph that preserves topology can preserve entity lineage. A discrete rib fuse creates a new CAD configuration and therefore a new geometry digest, mesh, mode basis, and scene artifact. The handbook makes this explicit: changing ribs forces CAD fuse → remesh → setup/rebind → RBF matrix/factorization; cached mode fields are valid only per rib configuration. [file:79]

### 6.3 The nested representation is essential

GB3 has both discrete and continuous design levers:

```text
Outer loop: rib configuration r
  CAD fuse(r)
  → validate boolean / castability
  → Gmsh remesh
  → rebind FEM setup/groups
  → solve/factorize RBF morph basis for this r
  → generate immersive scene for this r

Inner loop: morph vector m
  u = Σ m_i * mode_i
  → update mesh coordinates / CAD preview
  → geometry-quality and validity checks
  → fast solve / surrogate inference / selected full solve
```

The current engineering plan already estimates the important economic property: 20 rib configurations × 25 morph vectors gives 500 designs while requiring 20 remeshes rather than 500, because the expensive geometry setup and RBF factorization are reused within each discrete configuration. [file:79]

This is the central immersive-geometry benefit for your platform UI too: the user can interactively explore `m` live in the Stage because the inner-loop morph preview is cheap, while the UI visibly distinguishes “preview geometry” from “validated/solved design.”

---

## 7. UI integration

### 7.1 Workspace layout

```text
┌────────────────────────────────────────────────────────────────────────┐
│ GRC GB3 rear housing · baseline PoC · rev 1     coverage 62% · synced  │
├───────────────┬──────────────────────────────────┬─────────────────────┤
│ ENTITY INDEX  │ STAGE                            │ AGENT / EVIDENCE    │
│               │                                  │                     │
│ Components    │ [3D] [Drawing] [FEM] [Design]    │ Conversation        │
│ Interfaces    │                                  │ Tool cards          │
│ Design space  │ Immersive geometry scene         │ Proposed actions    │
│ Constraints   │ leader lines / clip / inspect    │ Approvals           │
│ Evidence gaps │                                  │                     │
├───────────────┴──────────────────────────────────┴─────────────────────┤
│ PASS + RUN LOG · provenance · active jobs · cache / geometry digest     │
└────────────────────────────────────────────────────────────────────────┘
```

No panel is called “Ribs,” “Bores,” “Gearbox,” or “GB3.” GB3 supplies entity types and labels through the Design Space Object.

### 7.2 First-stage immersive interactions

Build these before AR/VR, avatars, collaborative cursors, or elaborate spatial interfaces:

| Interaction | User experience | Back-end action |
|---|---|---|
| Semantic hover | Hover a face/region; leader line opens to identity/evidence card | `GET /entities/{id}` and scene pick ID lookup |
| Tri-directional selection | Select CAD face ↔ drawing callout ↔ FEM group | Entity graph traversal |
| Region-status rendering | Solid / faded / dashed outline for measured / derived / assumed | Entity status from graph |
| Cross-section / clipping | Drag section plane through housing; view bore paths, ribs, groups, stress | GPU clip plane; no solver action |
| Exploded semantic layers | CAD surface, FEM groups, loads, constraints, result field toggle separately | Scene layer masks |
| Design-space overlay | Frozen regions neutral; morphable regions layout blue; proposed regions striped | `DesignControl.authority` + evidence status |
| Variant A/B comparison | Split or ghosted alignment of baseline versus candidate | Load two GLB variants, shared camera, entity lineage lookup |
| Morph preview slider | Drag an approved continuous mode; see shape displacement live | Cached mode-field client-side or streamed preview mesh |
| Tool trace link | Click a number/result → card with exact API tool call, args, rows, provenance | Trace / provenance lookup |

The test is simple: every visual element must answer one of three questions:

1. What is this engineering entity?
2. What evidence connects it to a source artifact?
3. What can be changed here, under what rule, and what would it cost to validate?

If it does not answer one of those, remove it from the initial product UI.

### 7.3 The immersive geometry stage is not a decorative viewer

A face hover should show something like:

```text
OUTER SURFACE REGION 003
Status: ASSUMED · confidence 0.72

CAD
  Baseline region rule: outward normal + Z = 180–520 mm

Drawing
  No direct callout matched

FEM
  Elements: shell/solid set REGION_OUTER_003
  Last response: vm_p99.9 = [solved value]

Design authority
  Continuous morph mode M07
  Range: [-0.8, +0.8] mm
  Validity: measured sweep v1

Actions
  Explain selection · Pin · Freeze · Request morph study
```

For a frozen bore:

```text
BORE MAIN S2
Status: MEASURED

Drawing
  254492 · sheet 1 · concentricity datum reference

FEM
  RBE3 master group · load-basis components attached

Design authority
  FROZEN
  Reason: controlled machining/interface feature
```

This turns “immersive geometry” into an evidence-native engineering interaction rather than a shiny CAD viewer.

---

## 8. Agent integration

The agent does not need privileged geometry behavior. It uses the same API the UI uses. The key is to add spatial/Design-Space tools to the existing twelve-tool set rather than build a second special agent.

### 8.1 New free tools

```text
get_workspace_capabilities(workspace_id)
get_design_space(workspace_id, version)
search_entities(query, filters)
inspect_entity(entity_id)
trace_mapping(entity_id, source_type?)
get_region_controls(entity_id)
preview_morph(config_id, amplitudes)
compare_geometry(variant_a, variant_b, entity_scope?)
get_geometry_coverage(workspace_id)
propose_region(objective, constraints, budget)
```

All are read-only or preview tools and therefore remain free. They return artifacts plus server-side provenance envelopes, preserving the existing rule that the UI renders evidence from tool results rather than trusting model prose. [file:70]

### 8.2 New gated actions

```text
create_design_space_revision(changes)
submit_campaign(sampler, params, n, seed, ...)
materialize_candidate_geometry(rib_config, morph_vector)
launch_validation_solves(candidate_ids, solver_config)
train_surrogate(model_config, dataset_version)
promote_surrogate(model_id, acceptance_report)
```

`submit_campaign` remains the primary cost/spend gate. `create_design_space_revision` must also be approval-gated because it changes the legal/engineering interpretation of what the system is permitted to modify. A user or designated reviewer must explicitly approve a transition such as “outer boss region changes from assumed/free to approved/morphable.”

### 8.3 Agent handoff sequence

```text
User: “Reduce robust IMS misalignment without altering machined interfaces.
       Show me where we still have design authority.”

Interpretation agent
  → resolves target metric, load-band mode, baseline and constraint scope
  → asks clarification only if ambiguity blocks a truthful answer

Spatial analysis agent
  → inspect Design Space Object
  → retrieves frozen/morphable/proposed regions, FEM bindings, drawing evidence
  → returns a spatial card and highlights candidates in Stage

Exploration agent
  → calls robustness + sensitivity + neighbourhood + propose_region
  → identifies whether known variables are exhausted
  → may say: “15-rib space has 1.09× headroom; dominant sensitivity lies
     outside present control authority.”

User: “Propose a study around the outer panel and an AX2 bridge region.”

Design-space agent
  → prepares two proposed controls with evidence status, morph/fuse mechanisms,
     sweep-derived validity bounds, affected FEM rebindings and estimated cost

Gate agent
  → sends exact campaign proposal: sampler, resolved parameters, design count,
     seed, objective interpretation, estimated compute, artifact revisions
  → pauses for human approval

Campaign worker
  → materializes CAD / immersive GLB / mesh / setup / solve artifacts
  → results sync into Postgres and object storage

Analysis agent
  → compares measured results and prediction error
  → produces next-round region proposal; does not launch it automatically
```

This satisfies the existing rule: the agent has capabilities, not a pre-authored flow; it may create a plan, but it cannot spend or redefine the design space without human approval. [file:71][file:70]

---

## 9. Surrogate integration and limitations

Immersive geometry creates a clean bridge to the eventual surrogate because it gives every design a consistent scene and surface representation. But the render mesh must not quietly become the ML truth.

### Data layers

| Layer | Use | Store |
|---|---|---|
| B-rep / CAD | Manufacturing authority, topology edits, exact interfaces | Object storage |
| Analysis mesh | Solver geometry and node/element correspondence | Object storage |
| Immersive GLB mesh | Progressive browser scene and pickable semantics | Object storage / CDN |
| Curated surface point cloud | ML input; normals, locations, entity labels, fields | Zarr / Parquet + object storage |
| SDF (later) | Search/topology representation, geometry-local features | Object storage |

### Sequence of implementation

1. **First train scalar baselines, not GeoTransolver.** The current project already has 490 rib-only variants, zero morph variants, and no trained ML model. Fit interpretable scalar models first (gradient-boosted tree baseline, ensemble MLP for continuous morph later) because they close the loop cheaply and tell you whether the data supports a useful predictor. [file:79]
2. **Do not claim arbitrary-geometry inference from GB3 alone.** The handbook is explicit: 490 variants of one casting supports the weak housing-specific claim, not “reads any housing geometry.” A second housing is more valuable than another thousand permutations for assessing transfer. [file:69][file:66]
3. **Keep strict split discipline.** Split on design ID, never point samples; do not feed rib flags as surrogate inputs; hold out rib count, rib identity, and a uniformly sampled held-out design block. [file:69]
4. **Use exact load-basis composition outside the learned model.** `basis.npy` already composes bore tilt, shaft skew, mesh misalignment and objective values for bearing-load weights. The model should not approximate arithmetic that is exactly available. [file:69]
5. **Use the field model as a field/gradient tool, not as an unqualified oracle.** The eventual goal is differentiability: gradients with respect to morph amplitudes and other continuous controls. The handbook correctly warns against deriving stiffness by inverting predicted fields: the measured condition number amplifies small prediction error substantially. If stiffness is needed, train it as a separate head. [file:69]
6. **Preserve measured/predicted separation in the UI.** Predicted contour = “surrogate estimate,” with model version, dataset version, OOD score and error bounds. Solved contour = “measured simulation result,” with mesh/solver/provenance. They must never share the same status color or export label.

### How the future fast loop works

```text
New candidate controls
  → materialize low-cost geometry preview
  → compute geometry validity and OOD distance
  → surrogate predicts scalar score / field / uncertainty
  → screen candidates on prediction + uncertainty + diversity
  → user approves bounded top-k real solves
  → full FEM results return
  → prediction-versus-truth card is displayed
  → only accepted, validated rows are folded into next training dataset
  → retrain/promotion is a separate gated action
```

This is technically feasible and avoids the documented surrogate failure mode: optimizers hunt model error. The existing project already measured that a 250-design surrogate’s top-10 ranking was only 2.4% better than random and confidently predicted beyond observed floors; therefore the model must not autonomously control spending. [file:71][file:69]

---

## 10. API extensions

### Artifact and geometry API

```text
POST   /api/workspaces
POST   /api/workspaces/{id}/artifacts
GET    /api/workspaces/{id}/artifacts
POST   /api/workspaces/{id}/ingest
GET    /api/workspaces/{id}/ingest/status
GET    /api/workspaces/{id}/capabilities

GET    /api/design-spaces/{id}
POST   /api/design-spaces/{id}/revisions             # gated
GET    /api/design-spaces/{id}/controls
GET    /api/design-spaces/{id}/coverage

GET    /api/entities/{entity_id}
POST   /api/entities/search
GET    /api/entities/{entity_id}/mappings
GET    /api/entities/{entity_id}/provenance

GET    /api/scenes/{geometry_digest}/manifest
GET    /api/scenes/{geometry_digest}/lod/{level}
POST   /api/geometry/preview-morph
POST   /api/geometry/compare
```

### Campaign, analysis, and agent APIs

Keep the existing API family and add only geometry-aware composition:

```text
POST /api/analysis/propose-region
POST /api/analysis/geometry-impact
POST /api/campaign/preview
POST /api/campaign/submit                  # gated
POST /api/agent/chat                       # SSE
GET  /api/agent/threads/{id}
GET  /api/agent/proposals
```

### Geometry/candidate event envelope

Every long-running job emits an SSE event with stable type and artifact references:

```json
{
  "event": "geometry_materialized",
  "workspace_id": "grc-gb3-rear-housing",
  "candidate_id": "gb3:variant:...",
  "geometry_digest": "sha256:...",
  "design_space_revision": "dso:...:v3",
  "artifacts": {
    "brep": "object://...",
    "scene": "object://...",
    "mesh": "object://..."
  },
  "provenance": { "tool": "materialize_candidate_geometry", "args": {} }
}
```

The UI is a subscriber and renderer. The agent is another API client. Neither is a special path.

---

## 11. Incremental delivery plan

### Phase 0 — Correctness debt before platform polish

- Implement the robust load-basis re-ranking in the current UI; the handbook says the current nominal leaderboard is gameable and the correction uses already-stored per-case values. [file:66]
- Finish the mesh-convergence/noise-floor benchmark before making winner claims.
- Verify real campaign submission end-to-end and preserve job/proposal provenance.
- Fix the known sampler-plan transparency defect: anchors must be reported separately or included in requested count. [file:70]

### Phase 1 — `ui_agentic` spatial foundation (2–4 weeks)

- Create `ui_agentic/` as a separate Vite app or route package, but share the current API client, viewer/renderer primitives, and state pattern.
- Build workspace shell: Entity Index / Stage / Agent Rail / Activity strip.
- Hand-author GB3 manifest and Design Space Object v1 from current known constraints.
- Export GB3 baseline B-rep to medium-LOD GLB plus scene manifest.
- Implement entity selection and CAD ↔ FEM mapping first; do not fake drawing mappings.
- Add measured/derived/assumed/unresolved visual encodings everywhere.

**Done when:** a user can open GB3, select a frozen bore, see its CAD/FEM/drawing evidence, select an assumed panel region, see why it is assumed, and no view contains a hardcoded GB3 component name.

### Phase 2 — First agent-native loop (2–3 weeks)

- Add `get_design_space`, `inspect_entity`, `trace_mapping`, `get_region_controls`, and `get_geometry_coverage` API/tool wrappers.
- Route tool artifacts into stage views and cards, preserving current compact tool-card contract.
- Add `propose_region` as a free analysis endpoint using existing `robustness`, `sensitivity`, `neighbourhood`, and Pareto results.
- Add approval-gated `create_design_space_revision` for newly proposed morphable regions.
- Make every UI action emit an equivalent tool trace; slider drag should visibly show the same `preview_morph(...)` call an agent would make.

**Done when:** the user asks “where can I move material?” and the agent answers with spatially highlighted, evidence-tagged controls; the same action can be performed by clicking a UI control or by an agent tool call.

### Phase 3 — Joint ribs + morph in the platform (3–6 weeks)

- Implement the two-level campaign plan: `rib_configurations[]` outer loop, `morph_vectors[]` inner loop.
- Cache mode fields per rib digest, not per overall candidate.
- Freeze added-rib nodes under panel morphing, matching the current decided methodology. [file:79]
- Materialize a GLB/scene artifact for every candidate only at preview/selected-candidate tiers; do not generate full-quality scene artifacts for every rejected design.
- Add candidate comparison: baseline versus morph preview versus solved candidate.

**Done when:** a mixed configuration can be previewed interactively, submitted as a fully reproducible campaign, and re-opened after the solve with correct geometry/results/provenance lineage.

### Phase 4 — Scalar surrogate and informed screening (after valid mixed data)

- Produce a first mixed dataset: existing 490 designs are the zero-morph slice; add controlled rib/morph factorial or sparse mixed campaigns.
- Fit scalar baselines; report error across all required split types before any active-learning claim.
- Add prediction cards with uncertainty and OOD state.
- Add bounded top-k candidate screening; always solve a diversity/control subset too.
- Gate training, model promotion and top-k validation campaign independently.

**Done when:** the platform can show a predicted-versus-solved calibration card for each new batch and can prove whether screening saves solve budget on held-out variants.

### Phase 5 — Field surrogate / cross-geometry program

- Curate cross-geometry data from at least one additional housing/structural component.
- Standardize entity types, coordinate frames, loads, boundary-condition descriptors and material metadata.
- Train the point-cloud/field model only after a scalar baseline and dataset lineage are working.
- Evaluate geometry-family holdout separately from within-family held-out parameter tests.
- Add SDF only when topology search is truly needed; keep B-rep manufacturing path authoritative.

**Done when:** results separately report within-GB3 interpolation, GB3 topology extrapolation, and cross-geometry transfer. The product claim must follow whichever of those is actually demonstrated.

---

## 12. What not to build yet

- A full VR headset experience. Immersion here means spatially inspectable geometry in a browser, not virtual reality. VR does not improve CAD/FEM evidence grounding and would delay the core proof.
- Generic text-to-CAD generation. It is incompatible with controlled interfaces, drawing evidence, repeatable FEM binding and manufacturing traceability.
- Autonomous multi-round solve launching. The agent may reason, compare, and propose; every revision/campaign still requires explicit approval.
- Per-face unique materials for every face in huge assemblies. Use semantic regions and packed pick-ID textures/attributes; full face-level mapping can load on demand.
- An SDF-only representation. SDF is a future search/learning layer, not a substitute for released B-rep or manufacturing geometry.
- A claim that the current GB3 corpus proves arbitrary-geometry surrogate inference. It does not; the existing handbook correctly states this limitation. [file:69]

---

## Final product definition

The platform is not a CAD viewer, a simulation dashboard, an optimizer, or a chat wrapper.

It is a **governed compiler for engineering design spaces**:

1. It ingests heterogeneous engineering artifacts.
2. It builds a spatial identity graph and exposes evidence gaps.
3. It turns authorized geometry into typed, bounded, traceable design controls.
4. It lets humans and agents invoke the same capabilities through the same APIs.
5. It generates, evaluates and compares designs with full artifact provenance.
6. It uses measured results—and later validated surrogate inference—to propose more informative next regions of exploration.
7. It never obscures whether a statement is measured, derived, assumed, predicted or approved.

For GRC GB3, immersive geometry makes this proposition visible: users can literally point at a region of a large housing and see what the system knows, what it infers, what it is allowed to change, what it predicts will matter, and what evidence would be required before spending solver budget.
