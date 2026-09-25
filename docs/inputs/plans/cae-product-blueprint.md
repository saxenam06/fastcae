# Constraint-Governed Simulation Data Factory

## Product, Technology, and Commercial Blueprint

**Prepared for an AI-native CAE startup focused on trustworthy design-family generation, simulation-data production, surrogate modeling, and agentic engineering.**

## Executive decision

The product should be built, but with a precise boundary: it should become a **constraint-governed engineering design-family compiler and simulation-data factory**, not a general-purpose CAD system, a generic cloud solver, or a broad “Physical AI platform.” The core proposition is to accept one engineering analysis the customer already trusts, reconstruct its explicit simulation context, require approval of a controlled design contract, generate only admissible variants, qualify those variants geometrically and physically, and convert accepted results into traceable AI-ready records.

The product addresses a real market. Neural Concept reports adoption by more than 70 OEM and Tier-1 customers, including major automotive and aerospace organizations; Siemens, Ansys, Altair, PhysicsX, and Monolith are all commercializing engineering AI, surrogate modeling, generative geometry, or AI-guided design exploration.[cite:22][cite:25][cite:67][cite:241][cite:244] This validates demand, but also makes a broad horizontal platform an unattractive entry strategy.

The defensible opening is the customer-specific layer between existing CAD/CAE assets and AI models:

> **Bring one trusted CAE analysis. The platform converts it into an approved design family, generates diverse and traceable solver-qualified variants, and produces a private surrogate and decision workflow tied to a defined engineering use.**

No document can assure startup success. Success will depend on selecting a narrow first workflow, proving repeatability on unrelated components, securing paid design partners, and refusing to overbuild geometry functionality before customer evidence justifies it. The plan below maximizes the probability of success by defining what to build, what to integrate, what not to build, and which evidence must be obtained before each expansion.

## Product thesis

### Customer problem

Industrial organizations possess valuable CAD models, drawings, solver decks, meshes, test results, and analyst knowledge, but these assets rarely form a reusable design intelligence system. Producing a new design family often requires repeated geometry edits, remeshing, load and boundary-condition reconstruction, job submission, failure investigation, result extraction, and dataset cleaning. Existing AI-surrogate products can learn from historical or generated CAE data, but a customer may still lack a reliable upstream mechanism for generating diverse, valid, consistently labeled data.

This gap is strategically important because engineering-AI incumbents increasingly emphasize complete model lifecycles. PhysicsX describes a platform spanning data generation, private physics and geometry models, active learning, deployment, and agentic optimization; Siemens positions Simcenter around surrogate training, intelligent exploration, and digital twins; Ansys now combines SimAI with GeomAI-generated concepts.[cite:193][cite:67][cite:196][cite:241] Competing at the final neural-network layer alone is therefore unlikely to produce durable differentiation.

### Product answer

The product converts customer truth into governed exploration:

```text
CUSTOMER TRUTH
CAD + drawing + mesh + solver deck + reference result
        |
        v
CANONICAL ENGINEERING CONTEXT
geometry entities + mesh groups + materials + loads + BCs + contacts + outputs
        |
        v
BASELINE REPRODUCTION
reference comparison + discrepancies + supported/unsupported constructs
        |
        v
APPROVED DESIGN CONTRACT
mutable features + fixed interfaces + parameter domains + topology rules + DFM rules
        |
        v
CONSTRAINT-GOVERNED GENERATION
CP-SAT configuration + implicit/field construction + geometry qualification
        |
        v
SOLVER-READY VARIANTS
meshing + physics inheritance + deterministic validation + execution
        |
        v
AI-READY DATA FACTORY
accepted records + lineage + quality flags + fields + derived quantities
        |
        v
DESIGN INTELLIGENCE
surrogate + uncertainty + active learning + optimization + solver confirmation
```

This is not merely CAD generation. It is **simulation-context-preserving design-space industrialization**.

## Category and positioning

### Primary category

The strongest category is:

> **Validated Engineering AI Infrastructure**

Useful secondary descriptions are:

- Constraint-governed simulation-data factory
- Design-family automation for CAE
- Trusted data infrastructure for physics AI
- Solver-qualified generative engineering
- Private surrogate lifecycle platform

“Physical AI” can be used as an ecosystem connection, especially for industrial equipment, robotics, vehicles, batteries, digital twins, and operational models. It should not be the primary category because much of the Physical AI market centers on embodied systems, synthetic sensor data, robotics simulation, and sim-to-real. The product’s initial value is upstream: improving the design and engineering of physical products.

### Positioning sentence

> **The platform learns explicit engineering context from a simulation the customer already trusts, compiles that context into a controlled design family, and produces validated simulation data and solver-verified design recommendations.**

### What not to claim

Avoid claims such as:

- “Understands every engineering problem from one file upload.”
- “Generates any automotive component.”
- “Automatically transfers all loads and boundary conditions.”
- “Replaces Abaqus, Ansys, Nastran, or Code_Aster.”
- “CP-SAT guarantees engineering feasibility.”
- “cuDSS is the FEA solver.”
- “A single 99% agreement score proves equivalence.”
- “4,000 variants are inherently more valuable than 40.”
- “Agents autonomously perform safe engineering without deterministic controls.”

The credible promise is narrower and stronger: explicit extraction, ambiguity detection, controlled generation, traceable qualification, and bounded AI predictions.

## Strategic product objects

A durable platform should revolve around first-class engineering objects rather than pages and buttons.

| Object | Role | Durable value |
|---|---|---|
| Baseline Package | Immutable record of supplied CAD, mesh, decks, drawings, results, units, versions, and checksums | Preserves customer truth |
| Canonical Simulation Graph | Solver-neutral representation of entities, materials, loads, BCs, contacts, analysis steps, and outputs | Enables additional solver connectors |
| Design Contract | Approved mutable features, parameter ranges, fixed regions, constraints, topology rules, and intended use | Prevents uncontrolled generation |
| Feature Program | Typed, composable feature graph with anchors, parameters, Boolean operations, provenance, and expected topology effects | Avoids a monolithic CAD feature tree |
| Variant Manifest | Exact assignment of configuration and continuous parameters, parent baseline, random seeds, and generator versions | Reproducibility |
| Entity Genealogy | Mapping of preserved, transformed, split, merged, deleted, and created regions | Safe physics inheritance |
| Reproduction Certificate | Quantity-specific evidence comparing customer reference and reconstructed pipeline | Trust bridge |
| Campaign | Candidate policy, budget, job states, retries, validation gates, and results | Industrial execution |
| Accepted Simulation Record | Geometry, mesh, context, fields, KPIs, quality metrics, and provenance | AI-ready data asset |
| Surrogate Model Card | Training domain, errors, uncertainty, intended use, restrictions, and fallback policy | Governed deployment |
| Decision Record | Objectives, constraints, candidate rankings, human approvals, and confirming simulations | Auditability |

Enterprise simulation-data products already emphasize traceability, process reuse, and relationships across models and results. Siemens Teamcenter Simulation, for example, positions SPDM around managing simulation tools, processes, and data while preserving a digital thread.[cite:57][cite:59] The proposed product should integrate with SPDM/PLM rather than attempting to replace it initially.

## Design contract

One trusted simulation is an anchor, not a complete specification of design intent. It can establish supplied geometry, named groups, loads, constraints, materials, analysis steps, and outputs. It cannot safely infer allowable feature changes, parameter limits, manufacturing constraints, or whether a load remains meaningful after topology changes.

The product must therefore produce a **draft design contract** for engineer approval.

### Required contract sections

```yaml
context_of_use:
  decision: "screen housing variants before detailed release"
  supported_physics: "small-strain linear static"
  prohibited_use: [fatigue_release, crash_certification]

immutable_regions:
  - bearing_seat_A
  - sealing_face_01
  - gearbox_interface

mutable_regions:
  - outer_wall_zone_03
  - rib_zone_A

feature_permissions:
  rib:
    allowed: true
    anchors: [boss_group_A, wall_zone_03]
  through_hole:
    allowed: false

parameter_domains:
  rib_count: [2, 3, 4]
  rib_height_mm: [10, 12, 14, 16, 18]
  rib_thickness_mm: [4, 5, 6]

constraints:
  - boss_A requires at least two supporting ribs
  - sealing_face_01 cannot be modified
  - minimum_clearance_mm >= 5

physics_inheritance:
  material: inherit
  load_case_01: inherit_if_target_preserved
  fixed_support: review_if_face_splits
```

### Contract provenance

Every rule must carry:

- Source: customer file, customer statement, platform template, inferred proposal, or generated result
- Owner and approval state
- Version
- Units
- Severity: hard, soft, advisory, or review-required
- Applicability: feature, geometry family, material, process, load case, or analysis type
- Evidence or rationale

This converts the “do not invent semantics” principle into enforceable architecture.

## Constraint-governed generation

### CP-SAT’s exact role

Google OR-Tools describes constraint programming as identifying feasible assignments from a large candidate space, and CP-SAT works over bounded integer and Boolean variables.[cite:142][cite:146][cite:216] It is therefore well suited to the discrete configuration layer:

- Feature presence or absence
- Number and arrangement of ribs
- Approved mounting configurations
- Pattern selection
- Standard-size selection
- Symmetry and pairing
- Mutually exclusive options
- Dependency rules
- Discretized distances and dimensions
- Manufacturing-route selections
- Campaign-resource allocation

Channeling and conditional enforcement support implications such as “if this boss exists, at least two supporting webs must exist.”[cite:214]

CP-SAT must not be described as a complete geometry, manufacturing, or physics validator. It does not determine whether a constructed solid is watertight, a wall becomes locally too thin, a fillet fails, a tet mesh is acceptable, a casting fills, or a stress constraint is met.

### Layered feasibility

| Layer | Representative question | Mechanism |
|---|---|---|
| Logical | Are selected features and options mutually compatible? | CP-SAT |
| Parametric | Are dimensions selected from approved domains? | CP-SAT and continuous bounds |
| Geometric | Do features fit, connect, avoid forbidden zones, and preserve minimum thickness? | Field/B-rep algorithms |
| Mesh | Can a quality mesh be generated with required labels and resolution? | CGAL plus mesh checks |
| Numerical | Does the solver converge and pass equilibrium/energy checks? | Deterministic CAE pipeline |
| Performance | Are stress, displacement, frequency, mass, or temperature requirements satisfied? | FEA, reduced model, or qualified surrogate |
| Manufacturing | Does the geometry satisfy draft, access, thickness transition, and process rules? | DFM rule engine plus geometry checks |
| Decision | Is the model credible enough for the stated use? | Context-of-use validation and approval |

### Conflict-learning loop

A cutting-edge extension is to turn downstream failures into reusable constraint knowledge:

```text
CP-SAT assignment
    -> field construction
    -> geometric check
    -> failure explanation
    -> minimal conflicting assignment
    -> no-good constraint
    -> CP-SAT resumes search
```

Examples include:

- A boss diameter and rib height combination collides with a keep-out volume.
- A selected window deletes the support surface required by a boundary condition.
- A radial rib count creates sub-resolution gaps.
- A hole pattern violates minimum ligament thickness.

The platform should store these learned clauses at three scopes: current baseline, component-family template, and globally reusable rule only after engineering review. This creates a **Constraint Memory** without allowing an agent to silently promote local failures into universal engineering rules.

### Diversity selection

CP-SAT feasibility is not campaign design. After obtaining feasible assignments, a separate selector should maximize useful diversity across:

- Parameter distance
- Topology fingerprints
- Feature-graph distance
- Geometric descriptors
- Predicted response diversity
- Boundary and corner coverage
- Surrogate uncertainty
- Expected improvement
- Cost and meshability

This prevents 1,000 nominally feasible but nearly identical variants.

## Geometry strategy

### Continue field-based generation

The field route should continue because it offers robust Boolean composition, offsets, blending, local deformation, and rapid generation across topology changes. nTop’s market position confirms that implicit and field-driven design are powerful for automated geometry and design exploration.[cite:85][cite:202][cite:203][cite:206] That evidence is a reason to retain the method—but also a warning not to compete as a general implicit CAD authoring environment.

### Replace “voxel CAD” language

The persistent design representation should not be a dense occupancy grid. Use:

```text
Baseline geometry
+ typed feature program
+ parameter assignment
+ constraint set
+ entity genealogy
+ provenance
```

An adaptive sparse signed-distance field or level set should be the execution representation. OpenVDB provides a hierarchical structure and tools for sparse volumetric data, level sets, Boolean operations, sampling, and voxelization, making it relevant as an implementation option.[cite:247][cite:249][cite:251][cite:253]

### Hybrid representations

No single geometry representation should be forced across every stage.

| Representation | Best use |
|---|---|
| B-rep/STEP | Imported exact interfaces, analytic bores, sealing faces, dimensions, export |
| Tessellated scene | Browser interaction and visualization |
| Sparse SDF/level set | Robust feature composition, offsets, blends, topology changes |
| Feature graph | Persistent parametric intent and provenance |
| Volume mesh | High-fidelity structural or thermal solution |
| Surface/graph samples | Geometry-aware surrogate input |

Open Cascade supports STEP/IGES translation and B-rep processing, making it a practical exact-geometry ingestion layer.[cite:248][cite:252][cite:258] The platform should preserve exact functional interfaces where field discretization would damage tolerances or analytic identity.

### Functional-interface policy

Classify geometry into:

- **Frozen exact:** bearing seats, sealing faces, bolt interfaces, connector interfaces, datum features
- **Field-mutable:** walls, rib zones, pads, pockets, noncritical exterior surfaces
- **Morphable with bounds:** envelopes, local bulges, thickness patches
- **Generated:** ribs, webs, gussets, windows, reinforcement pads
- **Forbidden:** clearances, assembly sweep volumes, tooling access volumes

Generated solids should be clipped and blended against these classes according to explicit rules.

## Feature grammar

The company should not implement every feature found in CATIA, NX, Creo, SolidWorks, or nTop. Instead, build a small set of composable field operators and domain-specific engineering templates.

### Core operators

1. Union
2. Subtraction
3. Intersection
4. Offset or shell
5. Sweep along path
6. Loft or envelope interpolation
7. Smooth blend
8. Local deformation or morph
9. Pattern and symmetry
10. Trim by region or keep-out
11. Thickness measurement field
12. Connected-component and topology check

### Cast housing pack

Prioritize:

- Straight, curved, tapered, radial, and branching ribs
- Webs and gussets
- Bosses and cored bosses
- Mounting pads, ears, and lugs
- Local wall-thickness patches
- Reinforcement collars
- Pockets and lightening windows
- Through-holes, blind holes, slots, and bolt patterns
- Local bulges and depressions
- Fillets, root blends, and tapers
- Draft-aware feature variants
- Machining allowances
- Parting-line and pull-direction keep-outs

Casting DFM sources consistently identify wall uniformity, gradual transitions, ribs, bosses, draft, and fillets as interacting design considerations.[cite:159][cite:164][cite:165][cite:169] Rules should be supplied as configurable templates rather than hard-coded universal constants because process, alloy, foundry, and customer standards differ.

### Solid bracket pack

Prioritize:

- Mounting ears and bolt groups
- Load-introduction pads
- Connecting webs
- Triangular, curved, and branching gussets
- Local thickness zones
- Pockets and windows
- Envelope-constrained morphing
- Symmetry or mirrored supports
- Interface collars
- Blend and transition controls

### Separate sheet-metal pack

Sheet metal requires a different representation and manufacturing grammar: mid-surfaces, gauges, bends, flanges, beads, embossments, dimples, hems, reliefs, cutouts, and forming constraints. Do not mix sheet-metal and cast-solid authoring in the first release.

### Extensibility

Support three authoring modes:

- **Template mode:** guided engineering features and rules for most users
- **SDK mode:** Python/C++ feature operators, constraints, and validators for advanced teams
- **External-generator mode:** NX/CATIA/Creo/SolidWorks/nTop/Onshape or internal scripts create geometry; the platform governs campaigns, physics inheritance, lineage, solving, data, and AI

External-generator mode is strategically essential. It allows the company to win even when customer geometry cannot or should not be recreated in the field kernel.

## Entity genealogy

Persistent identity is one of the hardest and most valuable problems. CAD research documents how faces and edges can split, merge, disappear, or become ambiguous after model regeneration; this is the persistent naming problem.[cite:112][cite:113][cite:116][cite:266]

Every variant operation should emit explicit ancestry:

```text
Baseline entity -> Variant entity relationship
PRESERVED
TRANSFORMED
SPLIT
MERGED
DELETED
CREATED
AMBIGUOUS
```

### Physics inheritance rules

| Entity event | Default behavior |
|---|---|
| Preserved | Inherit approved assignment |
| Smoothly transformed | Inherit only if transform rule and measure checks pass |
| Split | Apply declared distribution rule or require review |
| Merged | Block if incompatible assignments meet |
| Deleted | Mark dependent physics invalid |
| Created | Assign no physics unless an explicit generated-region rule exists |
| Ambiguous | Block campaign or request approval |

Each load and BC needs an applicability predicate, not only an entity name. For example, a bearing pressure may remain applicable only if the cylindrical support radius and axis remain within tolerance; a fixed support may remain applicable only if the complete interface patch is preserved.

This genealogy and applicability engine is a stronger moat than the number of feature buttons.

## Meshing architecture

CGAL Mesh_3 is a sensible initial tetrahedral meshing backend. It supports isotropic simplicial meshing of implicit and labeled domains and can preserve supplied corners and curves through its feature-aware domain concepts.[cite:147][cite:215] Sharp features in an implicit domain may need to be provided explicitly, rather than expected to emerge automatically.[cite:144][cite:215]

### Required mesh pipeline

```text
Qualified field solid
    -> surface patches and feature curves
    -> local sizing field
    -> CGAL tetrahedralization
    -> optional quadratic-node elevation
    -> Jacobian/quality checks
    -> material and boundary labels
    -> load/BC transfer audit
    -> mesh convergence policy
    -> solver deck
```

### Performance hierarchy

To scale campaigns, use the cheapest valid path per variant:

1. Reuse baseline mesh when geometry is unchanged.
2. Morph the mesh when topology is unchanged and quality remains acceptable.
3. Apply local remeshing when changes are confined.
4. Perform full CGAL remeshing for topology changes.
5. Reject variants whose required resolution exceeds the campaign budget.

Cache baseline distance fields, immutable subdomains, sizing fields, interface descriptions, and feature templates. Run field evaluation in compiled code, batch independent candidates, and avoid repeatedly converting representations.

The user’s earlier target of thousands of designs in hours should be treated as a campaign-level systems objective, not a single-kernel promise. Useful throughput is **accepted records per engineer-hour and per compute cost**, not raw generated solids per second.[cite:188][cite:192]

## Solver and validation strategy

### Code_Aster first, solver-neutral core

Code_Aster is a reasonable demonstrator because it exposes groups and works with MED mesh/result exchange. The canonical simulation graph must remain independent of Code_Aster so the first paid customer can drive the next connector.

### cuDSS boundary

NVIDIA cuDSS solves sparse linear systems; it is not a full finite-element solver. A credible in-house fast structural engine must separately implement and verify element formulations, integration, constitutive behavior, assembly, BC treatment, loads, result recovery, and engineering checks. Initial scope should be small-strain linear elasticity with a controlled element and load catalogue.

### Reproduction certificate

Never collapse baseline comparison into one “agreement percentage.” Compare:

- Units and coordinate systems
- Material and section definitions
- Element formulations and integration choices
- Constrained degrees of freedom
- Applied load totals and moments
- Reaction balance
- Strain energy
- Displacement norms and extrema
- Field differences on a documented common representation
- Stress metrics away from known singularities
- Mesh sensitivity
- Solver tolerances and version information

ASME’s VVUQ guidance distinguishes verification, validation, and uncertainty quantification, and links credibility evidence to the intended context of use and decision risk.[cite:56][cite:62][cite:224][cite:233] The product can use these principles without claiming certification under a standard that may not directly govern the target application.

### Accepted-record gate

A simulation result enters the training dataset only if it passes:

- Geometry validity
- Entity-genealogy completeness
- Mesh quality
- Physics assignment completeness
- Solver completion
- Equilibrium/energy checks
- Output completeness
- Duplicate detection
- Distribution and coverage checks
- Version and provenance completeness

Failed and questionable cases remain visible but quarantined.

## Surrogate architecture

### Model portfolio

Do not commit the company to one neural architecture. Select by response and data regime:

| Use case | Candidate model |
|---|---|
| Scalar KPIs, low-dimensional parameters | Gaussian process, gradient boosting, MLP |
| Mixed discrete and continuous design | Tree ensembles, embeddings plus MLP, probabilistic models |
| Mesh fields across related topology | MeshGraphNet or geometric GNN |
| Surface-driven field prediction | Point-cloud or surface transformer |
| Regular field representation | 3D CNN or neural operator |
| Dynamic response | POD/ROM plus regression, temporal neural operator |
| Small data | Transfer learning, pretrained geometry encoders, classical ROM |

Altair PhysicsAI and Ansys SimAI demonstrate commercial demand for geometry-aware prediction across varying meshes and shapes without requiring conventional design parameters.[cite:48][cite:235][cite:244][cite:245] PhysicsX is moving toward pretrained large physics models, reporting a data factory with more than 20,000 automotive RANS simulations and reduced fine-tuning data needs for a particular car-aerodynamics model.[cite:201] A new startup should therefore differentiate through data creation and governance while remaining model-architecture agnostic.

### Active learning

Do not default to uniform production of 4,000 simulations. Begin with a diverse qualification set, train an initial model, evaluate uncertainty and failure regions, then select the next simulations based on information value. Published active-learning work shows that adaptive selection can substantially reduce simulation requirements in some PDE surrogate settings.[cite:225][cite:226][cite:229][cite:231]

### Trust contract

Every surrogate prediction should expose:

- Model version
- Training design-family version
- Input distance or out-of-distribution score
- Uncertainty or error proxy
- Relevant held-out metrics
- Context of use
- Unsupported outputs
- Solver fallback threshold
- Whether the result is AI-predicted, reduced-order, or high-fidelity

The optimization loop should always support selective high-fidelity confirmation.

## Agentic layer

Agents belong above deterministic tools, not inside numerical kernels.

```text
Engineering agent layer
  - interpret
  - plan
  - explain
  - select approved tools
  - diagnose
  - request approval
          |
          v
Deterministic capability layer
  import -> canonicalize -> generate -> qualify -> mesh -> solve -> validate -> package data
```

### Recommended agents

| Agent | Responsibility | Forbidden behavior |
|---|---|---|
| Intake Agent | Inventory files, units, entities, unsupported constructs, inconsistencies | Inventing missing semantics |
| Baseline Agent | Run reproduction workflow and organize discrepancy evidence | Declaring equivalence from one score |
| Contract Agent | Draft features, constraints, and applicability rules from explicit evidence | Approving rules on behalf of engineer |
| Generation Agent | Request candidate batches and explain rejected configurations | Editing geometry outside approved operators |
| Campaign Agent | Schedule, retry known failures, quarantine records, manage budgets | Relaxing engineering constraints silently |
| Data Curator | Validate schema, coverage, duplicates, and leakage | Promoting failed runs into training data |
| Surrogate Agent | Train candidate models and generate model cards | Declaring unrestricted validity |
| Optimization Agent | Propose candidates using objectives, uncertainty, and cost | Releasing a design without solver/human gate |
| Evidence Agent | Assemble lineage, comparisons, and decision records | Hiding adverse evidence |

PhysicsX’s Microsoft collaboration similarly separates geometry/physics models, agent orchestration, enterprise knowledge, and secure compute.[cite:193] The proposed product’s differentiation should be stronger deterministic governance and design-contract enforcement.

### Engineering tool protocol

Each tool should publish:

- Typed input/output schema
- Preconditions
- Deterministic version
- Side effects
- Cost estimate
- Evidence produced
- Failure taxonomy
- Retry policy
- Required approval level

This makes tools usable by agents, CLI workflows, APIs, and human UI without duplicating logic.

## User experience

### Main lifecycle

```text
INPUT | REPRODUCE | VARIANT SETUP | CAMPAIGN | EXPLORE | MODELS
```

### Input

Show exactly what was supplied, including missing and unsupported assets. Preserve names from source files. Every visible object carries Imported, Derived, Generated, Predicted, or Approved provenance.

### Reproduce

Show the customer reference and reconstructed result side by side, with field differences and quantity-specific evidence. A discrepancy inspector should trace every result back through material, load, BC, mesh, entity, and source file.

### Variant Setup

Use a contract builder rather than a blank CAD canvas:

1. Select an imported region or interface.
2. Choose an approved engineering feature template.
3. Set parameter domains.
4. Define hard, soft, and review constraints.
5. Preview diverse feasible examples.
6. Review inherited and invalidated physics.
7. Approve the design contract.

### Campaign

Expose useful health metrics:

- Proposed candidates
- CP-SAT feasible configurations
- Geometry accepted/rejected
- Mesh accepted/rejected
- Solver completed/failed
- Dataset accepted/quarantined
- Failure clusters
- Mean and median time by stage
- Compute cost
- Human interventions
- Coverage score

### Explore

Separate sources explicitly:

- Customer reference
- Platform high-fidelity result
- External high-fidelity result
- Reduced-order result
- AI prediction

Allow Pareto exploration, topology filtering, uncertainty filtering, nearest-training-example inspection, and one-click high-fidelity confirmation.

## Competitive strategy

| Competitor class | Existing advantage | Do not fight on | Differentiation target |
|---|---|---|---|
| nTop | Mature implicit modeling, field-driven design, automation | General geometry authoring and broad feature count | Baseline-to-design-contract compilation, safe physics inheritance, dataset qualification |
| Siemens/Altair | Solver and PLM integration, PhysicsAI, optimization | Broad enterprise suite | Cross-stack workflow qualification and faster customer-specific deployment |
| Ansys | Installed solver base, SimAI, optiSLang, GeomAI | Generic predictive AI and full CAE breadth | Solver-neutral customer truth, data-factory governance, private deployment |
| PhysicsX | Capital, large physics models, services, enterprise partnerships | Foundation-model scale | Narrow repeatable workflow, explicit design contracts, provenance, integration speed |
| Neural Concept | Geometry-aware AI, OEM references, workflow maturity | Generic 3D AI training | Upstream admissible-variant generation and accepted-record production |
| Monolith | No-code engineering ML and test intelligence | Generic tabular/test AI | Geometry/mesh/solver lineage and simulation-context generation |
| HEEDS/optiSLang/HyperStudy | Mature DOE and process integration | Batch orchestration alone | Semantic transfer, failure learning, model cards, constraint memory |
| SimScale/Rescale | Cloud simulation/HPC | Compute access | Compute-neutral engineering intelligence layer |
| CAD vendors | Exact geometry, feature depth, assemblies | Replacing production CAD | Controlled design-family features plus external-generator adapters |

nTop openly promotes robust implicit modeling, reusable design processes, and automated variation; Siemens and Ansys now combine AI prediction with design generation.[cite:83][cite:202][cite:203][cite:196][cite:241] Consequently, the startup must own a narrower but painful workflow rather than rely on “implicit + AI” as differentiation.

## Moat architecture

The durable moat is a compound system:

1. **Canonical Simulation Graph:** solver-neutral, provenance-rich engineering semantics.
2. **Design Contract DSL:** explicit, versioned, approvable variation and inheritance policy.
3. **Entity Genealogy:** topology-aware lineage across generated variants.
4. **Constraint Memory:** learned, explainable failure clauses and family-specific feasibility rules.
5. **Accepted-Record Standard:** consistent AI-ready simulation data with quality evidence.
6. **Reproduction Certificates:** automated trust bridge from customer solver to platform pipeline.
7. **Feature Packs:** vertical engineering grammars rather than generic CAD tools.
8. **Failure Intelligence:** geometry, meshing, numerical, and data-quality diagnosis accumulated across campaigns.
9. **Deployment Connectors:** CAD, solver, PLM, scheduler, object-store, and model-serving integrations.
10. **Qualified Surrogate Lifecycle:** uncertainty, context of use, drift, fallback, and decision evidence.

None is individually sufficient. Together they create switching cost, deployment learning, proprietary workflow data, and trust.

## New product ideas

### Design-Family Compiler

Treat the baseline package plus design contract as source code and the campaign as compiled output:

```text
Engineering source
    -> semantic analysis
    -> constraint checking
    -> geometry intermediate representation
    -> mesh/solver target
    -> evidence and data artifacts
```

This framing encourages compiler-like guarantees: typed entities, unsupported construct errors, deterministic builds, cached intermediate representations, reproducible target backends, and source maps from results to inputs.

### Constraint Copilot

The copilot does not invent rules. It suggests rules from customer standards, source decks, prior approved projects, and detected geometry, then asks the engineer to accept, modify, or reject them. Each accepted rule becomes executable and testable.

### Physics Applicability Predicates

Replace naïve load transfer with predicates such as:

```text
inherit pressure P1 only if:
  target patch exists
  patch normal change < threshold
  area change within approved range
  patch does not intersect generated cutout
```

This transforms “inherit baseline physics” into a safe and inspectable mechanism.

### Variant Unit Tests

Allow engineers to write tests similar to software tests:

```text
assert sealing_face_01 unchanged
assert boss_A connected_to main_body
assert min_wall_thickness >= approved_minimum
assert no_material_inside keepout_shaft_sweep
assert resultant(load_case_01) == baseline_resultant
```

Every generated variant runs these tests before meshing.

### Simulation Data Contracts

Define required fields, units, coordinate systems, meshes, interpolations, and quality flags before a campaign begins. A record that violates the contract cannot enter training.

### Counterexample Mining

Use geometry, mesh, solver, and surrogate failures to identify the most informative invalid or uncertain designs. These counterexamples improve constraints and model boundaries rather than being discarded.

### Multi-fidelity Ladder

Create four evaluation tiers:

- Analytical and rule checks
- Coarse mesh or reduced-order physics
- Standard campaign FEA
- Customer reference solver confirmation

Route candidates dynamically based on risk and uncertainty.

### Geometry Capability Marketplace

Long term, third parties and customer teams can publish signed feature packs, validators, solver connectors, and export adapters. Each package declares compatibility, tests, and required approvals. This expands geometry coverage without making the startup implement every feature.

### Private Physics Asset Registry

Manage customer-owned datasets, models, feature packs, design contracts, and validation evidence as versioned private assets. This can become an engineering counterpart to an ML model registry.

### Engineering Change Impact

When a baseline, load case, material, or requirement changes, identify which variants, records, models, and decisions are invalidated. This is highly valuable for sustaining engineering and creates linkage to PLM/SPDM.

### Campaign Economics Optimizer

Optimize not only performance but information gained per unit time, license token, GPU hour, engineer review, and solver cost. CP-SAT can also schedule jobs and licenses while active learning chooses informative designs.

### Solver Arbitration

For supported cases, compare results from the internal fast solver, Code_Aster, and customer solver, then route discrepancies to diagnostics. The product sells evidence and orchestration rather than insisting one solver is universally authoritative.

## Commercial model

### Initial offer

Sell a fixed-scope **Design-Family Qualification Pilot**:

- One component family
- One supported analysis type
- One baseline package
- One design contract
- Two or three feature classes
- 20–50 qualification variants
- Baseline reproduction evidence
- Accepted-record dataset
- Campaign health and failure report
- Optional first surrogate and model card
- Scale/no-scale recommendation

Do not give away customer-specific qualification work. It contains the highest integration and engineering effort.

### Expansion ladder

| Stage | Commercial product |
|---|---|
| 1 | Paid qualification pilot |
| 2 | Repeat campaign and feature-pack expansion |
| 3 | Annual on-prem/hybrid platform license |
| 4 | Private data-factory operations |
| 5 | Surrogate training, deployment, and monitoring |
| 6 | Adaptive optimization and design-decision application |
| 7 | Multi-team enterprise registry and PLM integration |

### Pricing logic

Price around business outcome and accepted output, not only compute:

- Fixed pilot fee
- Annual platform and connector license
- Campaign fee based on accepted qualified records or workflow capacity
- Compute pass-through or customer-provided compute
- Surrogate deployment and maintenance fee
- Enterprise support and validation package

Avoid charging primarily per generated variant because it rewards low-value volume and creates arguments over failed jobs.

### Buyer map

- CAE methods manager: repeatability and solver integration
- Simulation lead: fewer manual rebuilds and failure investigations
- Digital engineering leader: reusable data and model lifecycle
- Chief engineer: faster decisions with evidence
- IT/security: deployment, isolation, identity, and audit
- PLM/SPDM owner: lineage and system integration
- Procurement: measurable pilot scope and conversion criteria

## Beachhead

Keep the architecture general but start with one repeatable archetype:

> **Linear-static structural design families for cast or machined housings, mounts, brackets, covers, and support structures.**

This aligns with existing expertise in gearbox housings, brackets, structural mechanics, geometry variation, meshing, and surrogate-assisted optimization.[cite:1][cite:3][cite:187] It can later extend to modal/NVH and thermal conduction without beginning with arbitrary contact, crash, CFD, plasticity, fatigue, or full assemblies.

The GRC gearbox housing and Deep JEB bracket should be treated as internal platform qualification cases, not as sufficient market validation.

## Build boundaries

### Build now

- Canonical simulation graph
- Provenance model
- Baseline importer and unsupported-feature report
- Reproduction comparison harness
- Design contract DSL and UI
- CP-SAT configuration compiler
- Sparse field kernel for limited feature packs
- Entity genealogy
- CGAL meshing pipeline
- Dataset acceptance gates
- Campaign health and failure taxonomy
- Solver-neutral job/result API
- Basic surrogate and model card
- Human approval and audit trail

### Integrate now

- STEP/B-rep import using established kernels
- Customer or open-source high-fidelity solvers
- HPC schedulers and cloud batch systems
- Object storage and metadata databases
- Existing DOE/optimization libraries where suitable
- Existing ML frameworks
- Existing identity, security, and observability platforms

### Do not build now

- General sketcher
- Assembly CAD
- Full drawing authoring
- Hundreds of CAD features
- General-purpose nonlinear FEA
- General CFD
- PLM replacement
- HPC cloud marketplace
- Foundation physics model trained across industries
- Fully autonomous design release
- A proprietary programming language before the schema stabilizes

## Technical architecture

```text
Web UI / Python SDK / REST API / Agent tools
                    |
              API gateway
                    |
  ------------------------------------------------
  | Project | Provenance | Approval | Asset registry |
  ------------------------------------------------
                    |
       Canonical Simulation Graph service
                    |
       Design Contract + Constraint service
                    |
     Candidate Generator / Diversity Selector
                    |
  ------------------------------------------------
  | Field kernel | External CAD adapters | Morphing |
  ------------------------------------------------
                    |
          Geometry Qualification service
                    |
  ------------------------------------------------
  | CGAL mesh | Mesh morph | External mesher adapters |
  ------------------------------------------------
                    |
       Physics Applicability and Deck Builder
                    |
        Scheduler / Runner / License manager
                    |
  ------------------------------------------------
  | Code_Aster | customer solver | internal fast FEM |
  ------------------------------------------------
                    |
      Validation + Accepted Record Builder
                    |
       Dataset store / Feature store / Registry
                    |
   Surrogate training / Active learning / Optimization
```

### Data storage

- Relational metadata store for projects, entities, contracts, campaigns, approvals, and lineage
- Object storage for CAD, meshes, decks, fields, logs, and model artifacts
- Columnar campaign tables for parameters and scalar outputs
- Chunked array formats for large field data
- Search index for entities, failures, and evidence
- Content-addressed storage for immutable artifacts and deduplication

### Security

Enterprise readiness requires:

- Customer-controlled encryption keys where demanded
- On-premises and air-gapped deployment option
- Strict tenant isolation
- Role-based approvals
- Immutable audit logs
- No training on customer data without explicit agreement
- Dependency and container provenance
- Signed tool and feature-pack versions
- Data-retention controls
- Exportable evidence package

Neural Concept advertises SaaS, on-premises, and air-gapped deployment, showing that deployment flexibility is already part of the competitive bar.[cite:28]

## Twelve-month execution plan

### Phase 0: Scope lock — Weeks 1–2

- Freeze supported physics and element formulations.
- Define baseline-package and canonical-graph schemas.
- Define variant identity and provenance.
- Select housing and unrelated bracket qualification cases.
- Establish explicit non-goals.

**Exit:** Architecture review passes; no housing-specific logic allowed in shared services.

### Phase 1: Truth and reproduction — Weeks 3–8

- Import CAD, mesh, deck, groups, materials, BCs, loads, and results.
- Build unsupported-construct inventory.
- Implement split-view and quantity-specific comparison.
- Produce first reproduction certificate.

**Exit:** Two baselines traverse the same metadata-driven pipeline.

### Phase 2: Contract and generation — Weeks 9–16

- Build design-contract schema and approvals.
- Add CP-SAT compilation for discrete features.
- Implement ribs, bosses, gussets, pads, pockets, holes/slots, local thickness, and patterns.
- Add sparse field evaluation and exact-interface protection.
- Implement variant unit tests.

**Exit:** Diverse feasible variants generated without hard-coded component semantics.

### Phase 3: Genealogy and meshing — Weeks 17–24

- Emit topology genealogy from every operator.
- Add physics applicability predicates.
- Integrate CGAL with patch labels, feature curves, and sizing fields.
- Add mesh reuse/morph/full-remesh routing.
- Add geometry and mesh failure taxonomies.

**Exit:** Deliberate split, merge, delete, and created-face tests behave safely.

### Phase 4: Data factory — Weeks 25–32

- Build campaign scheduler and health UI.
- Add retries, quarantine, accepted-record schema, and exports.
- Run 20–50 variants for both demonstrators.
- Add failure clustering and constraint feedback.

**Exit:** Every record is reproducible from its manifest; no rejected record enters training.

### Phase 5: Surrogate and active learning — Weeks 33–40

- Train scalar and field baselines.
- Add held-out splits by geometry/topology family.
- Implement uncertainty/OOD indicators.
- Add adaptive next-run selection.
- Produce model cards and solver fallback.

**Exit:** Surrogate supports one defined decision and beats an agreed simple baseline.

### Phase 6: Paid pilot — Weeks 41–52

- Integrate the first customer solver connector.
- Deploy in customer-controlled or hybrid environment.
- Qualify one customer-owned component family.
- Document time saved, accepted yield, interventions, and decision impact.
- Convert to repeat campaign or annual agreement.

**Exit:** Paid conversion, reusable product improvements, and customer reference or anonymized case study.

## Success metrics

### Technical

- Percentage of imported constructs classified as supported, unsupported, or review-required
- Baseline reproduction errors by physical quantity
- Entity genealogy completeness
- Variant unit-test pass rate
- Geometry acceptance rate
- Mesh acceptance rate
- Solver completion rate
- Accepted dataset yield
- Reproducibility rate from manifests
- Human interventions per accepted record
- Stage-level runtime and cost
- Surrogate held-out error and calibration
- OOD detection effectiveness

### Product

- Time to first reproduced baseline
- Time to approved design contract
- Time to first accepted 20-variant campaign
- Number of reusable rules versus customer-specific rules
- Percentage of workflows completed without developer intervention
- Customer engineer weekly active use
- Repeat campaigns per project

### Commercial

- Paid-pilot conversion rate
- Pilot-to-annual conversion
- Gross margin after engineering delivery
- Time to deploy next component in the same family
- Expansion to additional load cases, teams, or solver connectors
- Quantified analyst hours saved
- Reduction in turnaround for a named decision

## Kill and pivot criteria

Narrow or pivot if:

- Every new component requires mostly bespoke geometry code.
- Customers refuse automated physics transfer even with explicit review gates.
- Baseline packages are too incomplete to reconstruct without weeks of reverse engineering.
- Customers only want cheaper compute.
- Existing CAD/DOE scripts already solve the target workflow reliably.
- Useful surrogate life is too short because requirements or geometry families change constantly.
- Dataset generation cost exceeds the value of avoided tests or design-cycle acceleration.
- The platform cannot reproduce the second unrelated part without special-case logic.
- Paid pilots repeatedly fail to convert into recurring campaigns.

A service-heavy start is acceptable; permanently non-reusable service work is not.

## Immediate next build

The next product increment should demonstrate one complete vertical slice:

```text
Code_Aster baseline package
    -> canonical extraction
    -> source-provenance UI
    -> baseline reproduction evidence
    -> approved design contract
    -> CP-SAT configurations
    -> ribs + bosses + gussets + pockets/windows + thickness zones
    -> sparse field construction
    -> entity genealogy
    -> CGAL mesh with labels
    -> inherited physics audit
    -> 20–40 run qualification campaign
    -> accepted dataset
    -> first surrogate
    -> uncertainty-guided next five simulations
```

The same binary and UI must then run the housing and Deep JEB bracket with project metadata alone. That is the architectural gate separating a platform from a polished one-part demonstration.

## Final strategic rules

1. **Build a design-family compiler, not a new CAD system.**
2. **Treat one baseline as customer truth, not complete engineering intent.**
3. **Require an approved design contract before generation.**
4. **Use CP-SAT for combinatorial admissibility, not physics truth.**
5. **Use hybrid B-rep, feature-graph, field, mesh, and learning representations.**
6. **Make entity genealogy and physics applicability central.**
7. **Build feature packs for archetypes; expose an SDK and external-generator adapters.**
8. **Measure accepted records and decision acceleration, not variant count.**
9. **Train surrogates adaptively and publish their limits.**
10. **Keep agents above deterministic, versioned, testable engineering tools.**
11. **Sell paid qualification pilots before self-service SaaS.**
12. **Expand only when two unrelated customer cases reuse the same core.**

The strongest final proposition is:

> **A customer supplies one validated engineering case and approves how it may change. The platform compiles those rules into diverse engineering-valid variants, preserves simulation context through geometry and meshing, produces traceable high-fidelity data, trains a bounded private surrogate, and confirms important decisions with the trusted solver.**

That proposition is technically credible, commercially relevant, and differentiated enough to justify continued development—provided the company remains disciplined about scope and makes trust, semantic transfer, and accepted engineering data its core product rather than attempting to out-CAD CAD vendors or outspend foundation-model companies.
