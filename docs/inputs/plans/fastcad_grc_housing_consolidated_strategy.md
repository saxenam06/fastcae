# fastCAD / GRC Gearbox Housing: Consolidated Strategy and Research Report

## 1. Executive decision

The project should proceed as a **governed, housing-only simulation-data factory** for industrial gearbox housings.

The near-term purpose is not to train a general CAD foundation model, build a large semantic ontology, or let an LLM freely edit CAD. It is to transform one trusted GRC gearbox housing into a growing set of **structurally meaningful, feasible, traceable, simulation-qualified housing variants** that can train a surrogate model and later support constrained housing optimization under changed bearing load cases.

The current best architecture is:

```text
Exact original GRC housing B-Rep
        +
Protected functional geometry
        +
Structured CP-SAT pattern grammar
        +
Implicit/field-based local reinforcement generation
        +
Exact precision-core meshing
        +
Fast and trusted FEA validation rails
        +
Quality-diversity data selection
        +
Housing-response surrogate
```

The main generator is **not MMC or GET**. The main generator is the existing CP-SAT plus implicit-field capability, upgraded so it generates realistic structural pattern families rather than arbitrary feasible voxel patterns.

- **CP-SAT** generates many feasible and intentionally structured design variants.
- **Implicit fields** create clean blended rib-to-wall and rib-to-rib transitions, which are difficult to make robustly through generic B-Rep Boolean-and-fillet automation.
- **The original B-Rep housing** remains the authority for bearing bores, bearing-seat surfaces, shaft axes, mounting interfaces, sealing/split faces, and internal clearance.
- **FEA** decides engineering quality.
- **Quality-diversity search** prevents the dataset from becoming a collection of near-duplicate variants.
- **MMC** is a future local optimizer for tuning an already promising rib pattern.
- **GET** is a future concept-discovery experiment for finding a small number of smooth topology families outside the grammar.
- **HNC-CAD, CAD-Editor, CAD-Recode, DPO, and LLM agents** are later accelerators and interfaces, not Stage-1 dependencies.

The short strategic statement is:

> Keep the functional gearbox geometry exact; generate only the mutable reinforcement layer in field space; use CP-SAT to produce structured feasible topology families; use simulation to learn which patterns work under different bearing-load directions.

---

## 2. Product objective

### Long-term vision

Build an agentic, AI-native CAE platform that accepts engineering inputs such as CAD, solver decks, drawings, load cases, materials, and interface definitions, then creates governed design variations, solver-ready simulation cases, verified simulation data, surrogate models, optimized designs, and reviewable engineering decisions.

The platform should be positioned as a **governed simulation-data factory**, not as:

- A general-purpose CAD modeller.
- An LLM wrapper around CAD.
- A generic text-to-CAD system.
- A black-box topology-optimization tool.
- A replacement for trusted high-fidelity simulation.

The intended value proposition is:

```text
One trusted engineering baseline
        ↓
Many qualified geometry–physics records
        ↓
Trustworthy surrogate models
        ↓
Fast constrained design exploration
        ↓
High-fidelity validation of selected candidates
```

### Immediate demonstration objective

Use one GRC gearbox housing to prove that the platform can:

1. Preserve the trusted functional geometry.
2. Create structurally meaningful housing reinforcement variants.
3. Automatically generate simulation-ready records.
4. Run and validate a controlled FEA campaign.
5. Create training data that varies directional housing stiffness and load paths.
6. Train a surrogate that predicts housing response under changed bearing-interface loads.
7. Later search for the best housing reinforcement geometry for a new operating/load case.

### What the first stage is not

The first stage should explicitly exclude:

- Natural-language CAD modification as a core feature.
- Large feature-tree reverse engineering.
- A universal gearbox semantic ontology.
- Training HNC-CAD from the single housing.
- Rebuilding the full housing in CadQuery.
- Whole-housing voxel-to-mesh simulation as the trusted path.
- Full transmission NVH in every design iteration.
- DPO/RL fine-tuning before a qualified simulation ledger exists.

---

## 3. Starting constraints and requirements

### Available starting artifact

The GRC housing is available as a STEP/Parasolid-style **dumb B-Rep**, not as a usable native SolidWorks/Onshape feature tree.

This has direct consequences:

- The system cannot rely on original named ribs, sketches, dimensions, or feature-tree history.
- CAD-Editor-style feature-tree editing is not directly applicable.
- Imported face/edge identifiers are not a stable long-term abstraction after Boolean operations.
- Persistent naming is a known CAD problem because B-Rep entities may split, merge, or disappear after modification.

### Precision requirements

The following geometry must remain exact or be protected by strict tolerances:

- Bearing bores and bearing-seat cylindrical faces.
- Bearing bore axes and bearing-center locations.
- Shaft relationships and relevant coaxiality.
- Mounting pads, mounting datums, bolt holes, dowel holes, and locator regions.
- Split lines, sealing faces, and mating interfaces.
- Internal cavity, oil region, gear/shaft clearance, and packaging volumes.
- Machining-critical faces and access regions.

The key engineering concern is that small deviations in bearing-seat geometry, axes, or the definition of the bearing-coupling region can corrupt predictions of shaft alignment, bearing displacement, gear mesh misalignment, and NVH-relevant response.

### Dataset objective

The desired dataset must not be a large number of random shapes. It must contain:

- Structurally distinct reinforcement layouts.
- Variants that route load in different directions.
- Variants with controlled mass/stiffness trade-offs.
- Exact or protected bearing interface geometry.
- Consistent load and coordinate-system definitions.
- Repeatable meshing and solver settings.
- Traceable CAD/geometry/mesh/solver artifacts.
- Response labels relevant to bearing motion and housing structural behavior.

The initial product KPI is not “4,000 designs generated.” It is:

> A high yield of qualified, diverse, engineering-useful geometry–physics records.

---

## 4. What has been tried

### 4.1 Deterministic CAD feature extraction

#### Idea

Extract bores, bosses, flanges, pads, pockets, ribs, webs, and other entities from the B-Rep, then generate editable variants by modifying recognized features.

#### What worked

Some geometric primitives could be identified with reasonable reliability:

- Cylinders and bores.
- Holes.
- Some planar faces.
- Some outer surfaces and simple feature types.

#### What failed or remained insufficient

The difficult features were also the most structurally important:

- Ribs.
- Webs.
- Braces.
- Gussets.
- Structural reinforcement systems.
- Load paths.
- Functional meaning of a cylinder, such as bearing seat versus locator versus support.

Feature extraction identified geometry more readily than engineering intent.

#### Conclusion

Do not make complete feature recognition or a reverse-engineered feature tree a prerequisite.

Use lightweight geometry interpretation only to identify the minimum required protected features and mutable regions.

---

### 4.2 Parameterized ribs: thickness and on/off variation

#### Idea

Use parameterized ribs and vary:

- Rib thickness.
- Rib height.
- Rib on/off state.
- Existing design dimensions.

For example, 15 independently switchable ribs imply a theoretical design space of \(2^{15}\) combinations.

#### What worked

- Variants could be generated.
- The approach is deterministic.
- It supports DOE and automated simulation campaigns.
- It is suitable for creating initial baseline data.

#### What failed or remained insufficient

- Most variants were incremental changes of the same housing architecture.
- The system did not create genuinely new load paths or new reinforcement concepts.
- Removing existing production ribs and replacing them with simple unfilleted parametric ribs created poor-quality CAD.
- A large number of binary combinations does not imply a large number of meaningful structural concepts.

#### Conclusion

Keep this as a baseline/sensitivity generator, not as the main source of design discovery.

---

### 4.3 Mesh-first and mesh-morphing approaches

#### Idea

Convert CAD to a mesh and generate shape variations through mesh morphing or mesh-level modification.

#### What worked

- Meshes are directly compatible with FEA.
- Small known parameter changes can be fast.
- Mesh correspondence can be useful for some surrogate formulations.

#### Problems

- A mesh does not retain semantic meaning by itself.
- Nodes and elements do not know which region is a bearing seat, mounting interface, rib, or functional wall.
- Large topology changes are not natural with mesh morphing.
- Large modifications can degrade mesh quality.
- Exact cylindrical bores and mounting planes are difficult to preserve.
- Results can become unsuitable for CAD export or manufacturing.

#### Conclusion

Use mesh morphing only for limited known shape perturbations or screening. Do not use it as the main structural-concept generator.

---

### 4.4 Voxel / implicit / field-based generation with CP-SAT

#### Idea

Start from a rib-free housing or local housing regions, generate ribs and holes in a voxel or field representation, and use CP-SAT to enforce geometric feasibility.

The approach can create patterns such as:

- Spokes.
- Parallel ribs.
- Triangular patterns.
- Rib-and-hole combinations.
- Symmetric and constrained variations.

#### What worked well

This is an important strength of the project:

- Field/implicit operations generated smooth rib-to-wall connections.
- Rib-to-rib and rib-to-housing blending looked clean.
- Fillet-like transitions appeared naturally through field union/blending.
- Complex patterns and holes could be generated more easily than through B-Rep Boolean plus fillet automation.
- CP-SAT could enforce discrete feasibility constraints.
- The approach created a large design space without needing a large CAD dataset.

#### Problems discovered

The whole-housing field workflow damaged precision geometry:

```text
B-Rep housing
        ↓
Voxel / implicit conversion
        ↓
Field modifications
        ↓
Tetrahedralization / surface extraction
        ↓
Bore and sharp-interface approximation
```

Specific issues:

- Bearing bores lost exact cylindrical representation.
- Sharp engineering features were smoothed or approximated.
- Bore radius, axis, circularity, and bearing-face quality became resolution-dependent.
- CGAL-based tetrahedralization and voxel-derived meshes did not preserve precision interfaces sufficiently for trusted bearing coupling.
- Housing/bearing/shaft/gear-mesh response could no longer be trusted without careful correction.

#### Additional problem: patterns were feasible but unrealistic

CP-SAT produced variety, but much of it was not human-like or structurally meaningful:

- Random-looking orientations.
- Arbitrary rib endpoints.
- No clear hierarchy of primary/secondary ribs.
- Weak or missing load-path logic.
- Holes placed independently of structural panels.
- Inconsistent symmetry and spacing.

#### Conclusion

Do not discard the field generator. It solves a real CAD difficulty: robust blended geometry.

Instead:

- Keep the field representation for the **mutable reinforcement layer**.
- Keep the original B-Rep as the **exact precision core**.
- Change CP-SAT from free voxel selection to a structured pattern grammar.

---

### 4.5 Large semantic/context graph

#### Idea

Construct a graph of gearbox entities and relationships:

```text
bearing bore
wall
rib
flange
mounting interface
support
load path
manufacturing rule
simulation interface
```

Then let an agent reason over this engineering context and call CAD operators.

#### Advantages

- Encodes useful engineering meaning.
- Supports explainable decisions.
- Can represent protected versus mutable regions.
- Could become useful for lineage, retrieval, product generalization, and agent reasoning.

#### Risks

- High manual infrastructure cost.
- Risk that the graph becomes the project.
- A detailed gearbox ontology would be gearbox-specific rather than general.
- It does not itself generate variants or discover load paths.
- It still requires CAD, meshing, simulation, and validation afterwards.

#### Conclusion

Do not build a large context graph first.

Build a minimal **preserve/explore/validate contract** instead.

---

### 4.6 SolidWorks / Onshape feature-tree agents

#### Idea

Let an agent manipulate a native CAD feature tree:

```text
Disable Rib_12
Increase Rib_12 thickness
Create rib between selected features
Modify a pad, boss, or wall feature
```

#### Advantages

- A native feature tree provides design history and parameterization.
- Existing feature intent can be reused.
- It is attractive for future customer models that have good native parametric history.

#### Limitation for the current GRC housing

The available housing is a dumb B-Rep. It does not provide the feature tree needed for this approach.

#### Conclusion

Feature-tree control is a future optional ingestion path for customer-native CAD. It is not the foundation for the current GRC project.

---

### 4.7 HNC-CAD and related generative CAD models

#### Idea

Use a generative model to learn CAD design distributions, generate full parts, or locally complete/mutate designs.

#### What research says

HNC-CAD uses hierarchical neural code trees and supports conditional generation/local completion. Its public implementation uses DeepCAD sketch-and-extrude data for training and evaluation.

#### Advantages

- Could later propose diverse local alternatives.
- Supports a future learned local-completion or motif-suggestion layer.
- May help warm-start design search once a relevant engineering corpus exists.

#### Problems for the current project

- One gearbox housing is not enough to learn an industrial gearbox distribution.
- Public CAD datasets often contain simplified sketch/extrude histories rather than complex cast gearbox structures.
- A generative model does not know bearing stiffness, bore tilt, shaft alignment, gear mesh requirements, casting constraints, or solver behavior unless those are added through validation data.
- It produces candidate ideas, not trustworthy engineering designs.

#### Conclusion

Do not use HNC-CAD as the Stage-1 generator.

Use it later as a proposal model trained or adapted after the platform has accumulated validated structural variation data.

---

### 4.8 CAD-Editor and locate-then-infill

#### Idea

First identify a local region to change, then generate an edit inside that region rather than generating a full CAD model from scratch.

#### Valuable insight

The decomposition is highly relevant:

```text
Where should the housing change?
        ↓
What structural reinforcement should be added there?
```

#### Limitation

CAD-Editor is a text-based CAD editing framework and relies on edit representations and learned/synthesized data. It does not solve gearbox physics, precision interface preservation, or dumb-B-Rep feature-tree absence.

#### Conclusion

Borrow the **locate-then-infill architecture**, but implement it as:

```text
Physics / contract locates allowed reinforcement patch
        ↓
CP-SAT grammar / GET / MMC proposes structural form
        ↓
Field generator creates blended reinforcement
        ↓
FEA validates
```

Do not make text-to-CAD or LLM feature editing the critical loop.

---

### 4.9 CAD-Recode

#### Idea

Convert point-cloud geometry into executable CadQuery Python code.

#### Potential benefit

- Could produce editable proxy scripts.
- Could help test generic procedural CAD representations.
- Might later assist with simple reverse engineering or program-prior generation.

#### Limitation

It is not appropriate as a trusted reconstruction path for the GRC housing:

```text
STEP / Parasolid
        ↓
Point cloud
        ↓
Learned reconstructed CadQuery program
        ↓
Approximate geometry
```

This would reintroduce loss of analytic bearing geometry and functional fidelity.

#### Conclusion

Do not use CAD-Recode to rebuild the master housing or create trusted solver geometry. Keep it as a future experimental developer tool only.

---

### 4.10 DPO, RL, and solver-guided agents

#### Idea

Train an LLM or agent using preference/reward feedback from CAD checkers, constraint solvers, or simulation outcomes.

#### Research context

Solver-aligned training has improved CAD sketch-constraint validity in research settings. However, being fully constrained in a 2D sketch is not equivalent to a mechanically valid gearbox housing.

#### Important correction

A geometry/code checker can improve the probability of valid outputs, but it cannot by itself ensure:

- Bearing-interface preservation.
- Manufacturability.
- Mesh quality.
- Correct structural response.
- Low bore tilt.
- Gear alignment.
- NVH suitability.

#### Conclusion

DPO/RL is a later learning layer. First collect qualified positive/negative examples from the deterministic pipeline.

The early agent role is not “generate CAD.” It is:

- Schedule campaigns.
- Select next simulations.
- Route candidates to fast versus trusted fidelity.
- Diagnose typed failures.
- Track coverage and diversity.
- Learn feasibility/performance surrogate models.

---

## 5. Research findings

### 5.1 Field modeling and blending

Implicit/field-based modeling is naturally strong for blending, filleting, offsetting and Boolean composition of many complex features. This explains why the CP-SAT voxel/field workflow produced cleaner rib intersections than direct B-Rep automation.

The implication is not to abandon fields. The implication is to use fields only where approximation is acceptable: the mutable external reinforcement layer.

### 5.2 CAD precision and persistent naming

B-Rep topological entities can split, merge or disappear under CAD modeling operations. This makes direct face/edge references fragile, especially for imported neutral CAD and repeated Boolean modifications.

The system should use geometric, analytic, and coordinate-based protection rules rather than relying only on imported face IDs.

### 5.3 Explicit topology optimization and MMC

Moving Morphable Components represents topology through explicit geometric components with parameters such as position, orientation, length, thickness, and shape. It is more CAD-adjacent than density topology optimization.

MMC is useful for:

- Refining a known rib topology.
- Moving rib anchors/endpoints.
- Optimizing rib angle, length, thickness, height and activation.
- Locally improving a promising CP-SAT pattern using FEA.

MMC is not the primary bulk variant generator. Standard MMC tends to optimize toward one or a few high-performing layouts for a defined objective and load case.

### 5.4 GET

Gaussian Ensemble Topology represents material using superposed anisotropic Gaussian fields and aims to produce smooth, explicit and curvature-continuous topology-optimization results.

GET is attractive because:

- It is field-compatible.
- It can generate smooth, free-form branching/web-like material distributions.
- It may discover archetypes outside a hand-built pattern grammar.
- It does not need historical gearbox CAD data.

However:

- It does not itself preserve precision B-Rep interfaces.
- It does not automatically create production CAD or a casting-ready feature tree.
- It still needs protected masks, field-to-CAD or hybrid-mesh handling, and validation.
- A public official implementation was not readily identified during research.

GET should be used later as a **small-scale grammar-expansion / concept-discovery tool**, not as the Stage-1 bulk generator.

### 5.5 Stress-aligned ribs

Research on rib-reinforced shell structures uses principal stress directions and stress trajectories to seed or optimize rib networks. The core idea is physically relevant: principal stress paths approximate directions of internal force flow and can suggest useful material continuity.

For the GRC housing, baseline FEA stress/energy fields should be used as a prior for:

- Choosing mutable patches.
- Choosing likely rib directions.
- Ranking anchor pairs.
- Avoiding arbitrary orientations.

Stress directions should not be the only rule. They must be combined with symmetry, manufacturing, packaging, protected geometry and multi-load-case considerations.

### 5.6 Quality-diversity search

Traditional optimization searches for one optimum. The project needs many structurally distinct good solutions.

Quality-diversity methods such as MAP-Elites maintain elites across user-defined behavioral niches, for example:

- Rib count.
- Pattern family.
- Bearing-to-mount connectivity.
- Orientation distribution.
- Junction count.
- Symmetry class.
- Added mass band.

This is the correct strategy for avoiding 1,000 near-duplicate variants.

### 5.7 Surrogate modeling

Surrogates should not learn only:

```text
Geometry → one response under one nominal load
```

They should learn:

```text
Housing reinforcement geometry
        +
Bearing-interface load vector
        +
Mounting boundary condition
        ↓
Bearing-frame translations and rotations
Housing response metrics
```

This makes a changed gear design relevant without including gears in the housing surrogate. A changed helix or pressure angle changes bearing reaction forces/moments; those become new surrogate inputs.

---

## 6. The actual problem to solve

### Incorrect framing

```text
How can an agent generate a gearbox housing?
```

### Correct framing

```text
How can one trusted gearbox housing create a large, diverse,
engineering-qualified dataset of reinforcement-pattern and
bearing-load relationships while preserving precision interfaces?
```

### More precise formulation

For a housing geometry/reinforcement pattern \(G\), bearing/interface load vector \(f\), mount condition \(m\), and optional bearing parameter state \(b\), predict housing response:

\[
q = \mathcal{H}(G, f, m, b)
\]

where \(q\) contains:

- Bearing-frame translations.
- Bearing-frame rotations.
- Relative motion between bearing frames.
- Bore tilt/alignment metrics.
- Compliance/stiffness measures.
- Stress/strain-energy metrics.
- Mass.
- Modal or NVH-relevant responses later.

The later housing-optimization problem is:

\[
G^*(f,m,b) = \arg\min_G J(G,f,m,b)
\]

subject to:

- Protected-interface preservation.
- Mass limit.
- Stress limit.
- Packaging clearance.
- Manufacturability.
- Meshability.
- Bore geometry tolerance.

In plain language:

```text
For this changed bearing load condition,
which feasible housing reinforcement pattern
best controls bearing motion and structural performance?
```

---

## 7. Current best architecture

## 7.1 Precision core and mutable reinforcement layer

Split the housing into two representations.

```text
A. Exact precision B-Rep core
B. Implicit mutable reinforcement layer
```

### A. Exact precision B-Rep core

Keep unchanged:

- Bearing bores and bearing seats.
- Bearing axes and reference frames.
- Mounting interfaces.
- Bolt/dowel regions.
- Split and sealing faces.
- Internal cavity, oil volume, gear/shaft clearances.
- Critical machining surfaces.

### B. Implicit mutable reinforcement layer

Represent in field/voxel/implicit geometry:

- External ribs.
- Webs.
- Gussets.
- Local wall reinforcement.
- Controlled safe lightening patterns later.
- Blended rib roots and intersections.

This preserves the advantage of the existing field workflow while preventing the field from becoming authoritative for bearing geometry.

---

## 7.2 Minimal design contract

Do not build a large semantic graph. Define a compact contract for each housing.

```text
Preserve:
    protected CAD interfaces and volumes

Explore:
    external reinforcement patches
    anchor bands
    allowed material envelopes

Constrain:
    mass, minimum thickness, spacing,
    draft, packaging, no-go regions

Judge:
    load cases, mesh policy, solver settings,
    response metrics, validation thresholds
```

### Required contract objects

```text
HousingBaseline
ProtectedCylinder
ProtectedFaceSet
KeepOutVolume
HostPatch
AnchorBand
ReinforcementEnvelope
ManufacturingRuleSet
LoadCase
MountCondition
BearingInterfaceDefinition
MeshPolicy
ResponseDefinition
ValidationThreshold
```

---

## 7.3 Structured CP-SAT pattern grammar

### Main change

Do not use CP-SAT to decide arbitrary voxel occupancy.

Use CP-SAT to choose a structured reinforcement pattern family and parameter values.

### Pattern families for Version 1

1. Symmetric diagonal pair.
2. V-brace.
3. Y-brace.
4. X-brace / shear-panel bracing.
5. Ring/collar plus spokes.
6. Ladder / parallel-rib panel.
7. Bearing-to-mount reinforcement.
8. Bearing-to-bearing cross support.
9. Local gusset cluster.
10. Framed panel with an optional controlled window later.

### Primary CP-SAT variables

```text
pattern_family
host_patch
symmetry_class
primary_anchor_pairs
secondary_anchor_pairs
rib count
spacing
orientation range
primary thickness/height
secondary thickness/height
taper
hole enabled/disabled
hole size/location only in safe panels
added mass budget
```

### Hard constraints

```text
No reinforcement in bore keep-out volume.
No reinforcement in internal cavity/oil/gear clearance.
No interference with bolts, dowels, seals or machining zones.
Minimum rib thickness and root-support length.
Maximum rib height and packaging envelope.
Minimum spacing between members.
Explicit allowable junction rules.
Draft/manufacturing constraints.
Mass/volume budget.
Symmetry requirements when selected.
```

### Realism rules

A feasible pattern is not automatically plausible. Add a realism score or CP-SAT objective that rewards:

```text
Symmetry or justified asymmetry.
Anchor-connected primary ribs.
Stress-aligned orientation.
Regular spacing.
Primary/secondary hierarchy.
Panel-contained holes.
Repeated motif logic.
Low unnecessary complexity.
```

Penalize:

```text
Isolated rib endpoints.
Wall-to-wall members without structural reason.
Random angle mixtures.
Unsupported rib roots.
Holes outside framed safe panels.
Unjustified asymmetry.
Excessive rib density.
```

### Correct generation order

```text
Primary load-path ribs
        ↓
Secondary stabilizing ribs/gussets
        ↓
Identify structurally framed safe panels
        ↓
Optional lightening holes
```

Do not create ribs and holes independently in the first campaign.

---

## 7.4 Physics priors for pattern generation

Run trusted baseline FEA and compute:

- Principal stress directions.
- Strain-energy density.
- Displacement sensitivity near bearing supports.
- Bearing-frame translation and rotation.
- Reaction flow toward mounts.
- Relevant wall deformation regions.

Use these as priors:

```text
High strain-energy region → candidate mutable patch
Stress trajectory → preferred rib direction
Bearing support → preferred primary anchor
Mount/wall support → preferred target anchor
Low-energy framed panel → candidate lightening-hole region
```

The pattern grammar should remain capable of deliberate transverse and torsional braces, because not every useful rib follows a single principal direction.

---

## 7.5 Field geometry generation

The existing field generator remains valuable.

```text
CP-SAT structured pattern parameters
        ↓
Implicit primitives for ribs/webs/holes
        ↓
Smooth union / blending
        ↓
Clean rib-root and junction geometry
        ↓
Reinforcement-only implicit geometry
```

The field must be clipped to the mutable external envelope and must not replace the precision core.

### Output required from field generator

For every generated pattern, produce:

- Field parameters.
- Pattern grammar parameters.
- Reinforcement-only implicit surface/solid.
- Smoothness/blend parameters.
- Added volume/mass estimate.
- Keep-out intersection result.
- Pattern topology descriptors.

---

## 7.6 Two simulation rails

### Rail A: fast screening

```text
Exact original B-Rep housing mesh
        +
Separately meshed field reinforcement
        +
Tie/bond coupling at intended attachment surfaces
        ↓
Fast static screening FEA
```

Use this for hundreds or thousands of candidates.

Extract:

- Added mass.
- Global compliance.
- Bearing-frame translations.
- Bearing-frame rotations/tilt.
- Mount reactions.
- Strain energy.
- Coarse stress flags.
- Relevant initial modal metrics later.

A tied interface is a screening approximation. Do not use it for final stress/fatigue certification at the root junction.

### Rail B: trusted validation

```text
Selected reinforcement design
        ↓
CAD-compatible fusion / monolithic representation
        ↓
Conforming high-quality mesh
        ↓
Exact bearing and mount interface sets
        ↓
High-fidelity FEA
```

Use this for:

- Archive elites.
- High-surrogate-uncertainty candidates.
- New pattern families.
- Final optimization candidates.

Compare Rail A and Rail B continuously to learn whether the fast rail ranks concepts reliably.

---

## 7.7 Bearing bore preservation rules

The system must verify bore preservation, not merely assume it.

For every protected bearing bore, store:

```text
axis
radius
axial extent
reference frame
machining margin
minimum reinforcement clearance
allowable deviation
```

For every candidate:

1. Check reinforcement against cylindrical keep-out volume before meshing.
2. Ensure no field operation is allowed inside the precision-core mask.
3. Use the exact B-Rep bore for final mesh generation.
4. Re-identify the bore analytically after any CAD-level fusion.
5. Compare radius, axis, extent and cylindrical type with baseline.
6. Reject a candidate if protected geometry deviates beyond tolerance.

---

## 8. Training data required for the housing surrogate

## 8.1 Correct surrogate input/output

The housing-only surrogate should not require a full gear model as input. It should receive the bearing/interface loads resulting from external drivetrain analysis.

### Inputs

```text
Geometry:
- structured pattern family
- CP-SAT parameters
- field representation / field latent / occupancy representation
- host patches and anchor connectivity
- rib/web topology descriptors
- mass and volume descriptors

Loads:
- forces at each bearing interface: Fx, Fy, Fz
- moments at each bearing interface: Mx, My, Mz where relevant
- mount boundary condition / mount stiffness state
- optional bearing stiffness/preload operating state

Static metadata:
- material
- baseline identifier
- coordinate-system convention
- mesh policy / fidelity
```

### Outputs

```text
Bearing-frame translations: ux, uy, uz
Bearing-frame rotations: rx, ry, rz
Relative bearing-frame translation
Relative bearing-frame rotation
Bore-axis tilt / misalignment metrics
Compliance / directional stiffness
Mass
Stress and strain-energy flags
Modal/NVH quantities later
Prediction uncertainty
```

## 8.2 Why loads must vary

Future changes in helix angle, pressure angle, torque, direction, bearing stiffness, and mount condition change the forces/moments transmitted to the housing through the bearing locations.

Therefore the housing surrogate must learn:

```text
Same housing geometry
+ different bearing load direction/magnitude
→ different bearing displacement/rotation response
```

The housing does not need to know the gear geometry directly if the gear/shaft/bearing system supplies the corresponding interface-load vector.

## 8.3 Basis load cases

Build a basis of independent bearing-interface load directions before relying on actual gear sweeps.

Example initial set:

```text
LC1: Bearing A + radial-Y
LC2: Bearing A - radial-Y
LC3: Bearing A + radial-Z
LC4: Bearing A - radial-Z
LC5: Bearing A axial-X
LC6: Bearing B + radial-Y
LC7: Bearing B + radial-Z
LC8: Representative combined A/B radial case
LC9: Torsional/mount-reaction case
LC10: Reverse-drive/coast-equivalent combined case
```

Use only physically relevant components for the actual bearing model. The exact list must follow the GRC housing/shaft/bearing configuration.

## 8.4 Learn directional housing response

In an approximately linear static regime, the housing response can be viewed as:

\[
q = H(G)f
\]

where:

- \(G\) is the reinforcement geometry.
- \(f\) is the bearing/mount force-moment vector.
- \(q\) is the vector of bearing-frame translations and rotations.
- \(H(G)\) is a reduced compliance operator associated with the housing geometry.

This is the key scalable concept.

A later changed gear design gives a new \(f\). The surrogate estimates the resulting \(q\) for many candidate housing variants, and the optimizer selects the best one for high-fidelity verification.

## 8.5 Dataset coverage matrix

The dataset should cover:

```text
Geometry topology family
        ×
Directional load class
        ×
Mass budget
        ×
Mount boundary condition
        ×
Bearing operating condition where applicable
```

Do not create:

```text
1,000 random housing variants
×
1 nominal load case
```

Create:

```text
A smaller number of structurally different patterns
×
multiple directional bearing-load cases
```

A useful initial target is:

```text
80–200 structured housing patterns
×
6–10 basis load cases
=
480–2,000 housing-only geometry–load response records
```

Then add a smaller number of realistic combined bearing-load cases to validate the basis/surrogate model.

---

## 9. Roles of CP-SAT, GET, MMC, and other methods

| Method | Role now | Role later | Do not use it for |
|---|---|---|---|
| CP-SAT | Main feasible structured-pattern generator | Constraint layer for optimization and agent planning | Deciding structural quality alone |
| Implicit/field geometry | Main reinforcement realization and blending mechanism | Local topology/shape representation | Trusted reconstruction of precision bore geometry |
| Baseline FEA/stress fields | Physics prior for patterns and patch selection | Ongoing response label generation | Replacing validation |
| Quality-diversity | Select diverse high-performing cases | Archive and active discovery mechanism | CAD validity checks |
| Fast hybrid FEA | Bulk screening | Surrogate data expansion | Final root-stress certification |
| Trusted conforming FEA | Ground truth for selected designs | Final release authority | Every early random candidate |
| MMC | Not required initially | Local refinement of promising CP-SAT layouts | Bulk generation of 1,000 variants |
| GET | Not required initially | Discover a few new smooth/web-like topology archetypes | Bulk data generation or final CAD authority |
| HNC-CAD/CAD-Editor | Not required | Local learned proposal/ranking/UI layer | Core physics-aware generator from one housing |
| CAD-Recode | Not required | Proxy/program experimentation | Rebuilding trusted GRC B-Rep |
| DPO/RL | Not required | Learn proposal preferences from qualified result pairs | Hard engineering constraints or early exploration |

### CP-SAT

CP-SAT is the bulk generator because it can produce many feasible variants from a structured grammar.

### GET

GET should be used after the pipeline works, for selected cells and selected load cases:

```text
CP-SAT pattern seed
        ↓
GET refines / discovers a smooth material distribution
        ↓
If useful and valid:
convert result into a new structured grammar family
        ↓
CP-SAT generates many variants of that new family
```

GET is a **grammar-expansion tool**.

### MMC

MMC should be used after the pipeline works, for local continuous refinement:

```text
Promising CP-SAT V-brace or ring-spoke pattern
        ↓
MMC moves anchors/endpoints, adjusts thickness/height,
activates or suppresses secondary members
        ↓
Return refined parameters to field generator
        ↓
Generate clean blended field geometry
```

MMC is a **local physics-driven tuner**.

---

## 10. Phased implementation plan

## Phase M0: baseline truth

### Goal

Freeze a trusted, reproducible baseline housing FEA case.

### Tasks

1. Import and validate original GRC STEP/Parasolid B-Rep.
2. Create baseline mesh policy.
3. Define global coordinate system.
4. Define bearing reference frames from analytic bore axes.
5. Define mount interfaces and boundary conditions.
6. Define material model and solver version.
7. Define baseline static load cases.
8. Extract bearing-frame translations and rotations.
9. Establish mesh-sensitivity checks around bearing regions.
10. Store all artifacts, hashes and solver settings.

### Exit gate

The same baseline result can be reproduced automatically and bearing responses are stable enough to compare variants.

---

## Phase M1: preserve/explore contract

### Goal

Define where geometry must stay exact and where reinforcement can change.

### Tasks

1. Define protected bore cylinders and bearing-seat bands.
2. Define protected mounting, bolt, seal, split and internal regions.
3. Define 1–3 external reinforcement host patches.
4. Define anchor bands around bearing supports and target walls/mounts.
5. Define external reinforcement envelopes.
6. Define initial manufacturing constraints.
7. Define mass budgets and packaging heights.

### Exit gate

Every candidate can be checked against a versioned, deterministic contract before simulation.

---

## Phase M2: structured CP-SAT grammar

### Goal

Generate realistic, non-random pattern parameters.

### Tasks

1. Implement five initial pattern families:
   - Symmetric diagonal pair.
   - V-brace.
   - Y-brace.
   - Ring plus spokes.
   - Ladder/parallel-rib panel.
2. Add meaningful anchor-pair choices.
3. Add symmetry rules.
4. Add primary/secondary rib hierarchy.
5. Add spacing and orientation regularity rules.
6. Add protected-volume constraints.
7. Add mass and manufacturing constraints.
8. Implement a rule-based realism score.
9. Generate 20–50 visually/structurally deliberate layouts.

### Exit gate

The generated patterns are visibly structured, anchor-connected and non-random before FEA.

---

## Phase M3: field reinforcement generation

### Goal

Use the existing field system to create smooth blended reinforcement-only geometry.

### Tasks

1. Map grammar parameters to implicit rib/web primitives.
2. Restrict field operations to external mutable envelope.
3. Produce smooth unions and controlled root blending.
4. Export reinforcement-only surfaces/volumes.
5. Check keep-out intersections.
6. Calculate added volume/mass.
7. Compute topology descriptors.

### Exit gate

At least 20 structured variants generate smooth reinforcement geometry without touching protected precision regions.

---

## Phase M4: fast simulation rail

### Goal

Screen variants without voxelizing the precision housing core.

### Tasks

1. Mesh original B-Rep housing with exact bearing surfaces.
2. Mesh field-generated reinforcement separately.
3. Define reliable attachment/tie/bond treatment at the reinforcement interface.
4. Run static screening load cases.
5. Extract mass, compliance, bearing translation and bearing rotation.
6. Store failure codes and run telemetry.

### Exit gate

A batch of at least 50–100 candidates can be screened reproducibly with a measurable success rate.

---

## Phase M5: trusted validation rail

### Goal

Verify that promising field candidates remain valid under a higher-fidelity representation.

### Tasks

1. Select 10–20 diverse/high-performing candidates.
2. Build controlled CAD-compatible fused or monolithic representations.
3. Create conforming high-quality mesh.
4. Reapply exact bearing/mount boundary conditions.
5. Compare screening versus trusted results.
6. Measure discrepancies in:
   - Bearing displacement.
   - Bore tilt.
   - Compliance.
   - Modal response if included.
   - Stress near junctions.

### Exit gate

Fast-rail rankings are sufficiently correlated with trusted results for the intended screening decisions, or a correction model is defined.

---

## Phase M6: coverage-first dataset campaign

### Goal

Create qualified geometry–load data that spans directional housing response.

### Geometry campaign

Generate 80–200 structured patterns across pattern families and mass budgets.

### Load campaign

Apply 6–10 bearing/interface load basis cases to selected patterns.

### Example record count

```text
80 patterns × 8 basis load cases = 640 records
```

Use fast rail for broad coverage and trusted rail for selected elites and uncertainty cases.

### Exit gate

Dataset coverage is visible across:

```text
pattern family
× load direction
× mass band
× mount condition
```

---

## Phase M7: first surrogate

### Goal

Train a housing-only surrogate.

### Inputs

```text
pattern/field representation + bearing load vector + mount condition
```

### Outputs

```text
bearing translations/rotations + compliance + mass + stress flags
```

### Tasks

1. Train baseline regression/surrogate models.
2. Evaluate errors by pattern family and load direction.
3. Estimate uncertainty.
4. Identify under-covered regions.
5. Use active learning to select next simulations.

### Exit gate

The model can rank candidate variants for held-out load cases within the covered envelope and flags extrapolative cases with high uncertainty.

---

## Phase M8: selective MMC and GET research spikes

### MMC spike

Take 10–30 promising CP-SAT designs and locally refine:

```text
rib endpoint location
rib orientation
rib thickness
rib height
secondary-rib activation
```

Return parameters to the field generator for clean blending.

### GET spike

Use one local reinforcement cell and several CP-SAT seed patterns. Test whether GET produces:

- New smooth topology families.
- Better bearing-motion improvement per added mass.
- Meshable and convertible reinforcement geometries.
- Higher validated concept yield than grammar-only generation.

If a GET result yields a new useful archetype, encode it as a new CP-SAT grammar family.

---

## 11. Quality-diversity archive

The dataset must not merely grow in count. It must grow in coverage and useful differences.

### Geometry descriptors

```text
pattern family
number of primary ribs
number of secondary ribs
number of curved members
junction count
bearing-to-mount connectivity
bearing-to-wall connectivity
bearing-to-bearing connectivity
orientation histogram
symmetry class
mass band
hole volume fraction
patch utilization
```

### Load descriptors

```text
loaded bearing
force direction
force magnitude band
moment direction
moment magnitude band
mount condition
bearing state
```

### Quality metrics

```text
bearing translation
bearing rotation / bore tilt
relative bearing motion
compliance
mass
stress flags
mesh/build status
manufacturing score
trusted-validation status
```

For each niche, retain the best feasible candidate rather than allowing the campaign to concentrate only on one topology family.

---

## 12. Simulation record schema

Every attempted design—not only successful ones—should be recorded.

```text
run_id
baseline_id
contract_version
pattern_family
cp_sat_solution_id
field_parameter_vector
host_patch_ids
anchor_graph
symmetry_class
manufacturing_rule_version
protected_geometry_check
reinforcement_geometry_hash
cad_fusion_status
mesh_status
mesh_hash
fidelity_level
load_case_id
bearing_force_moment_vector
mount_condition_id
bearing_model_id
material_id
solver_version
solver_status
runtime
mass
compliance
bearing_frame_responses
relative_bearing_response
stress_metrics
modal_metrics
quality_diversity_descriptors
surrogate_prediction
surrogate_uncertainty
validation_status
failure_code
parent_design_ids
```

### Failure taxonomy

Use typed failures rather than generic failure messages.

```text
PATTERN_INFEASIBLE
PROTECTED_VOLUME_COLLISION
FIELD_EXTRACTION_FAILURE
REINFORCEMENT_MESH_FAILURE
TIE_INTERFACE_FAILURE
CAD_FUSION_FAILURE
BORE_PRESERVATION_FAILURE
CONFORMING_MESH_FAILURE
SOLVER_NONCONVERGENCE
RESPONSE_EXTRACTION_FAILURE
MANUFACTURING_RULE_FAILURE
PHYSICS_THRESHOLD_FAILURE
```

Failures are training data for future feasibility models.

---

## 13. What not to do

Do not:

1. Voxelize and trust the entire gearbox housing for precision bearing simulations.
2. Reconstruct the trusted housing through point clouds and CAD-Recode.
3. Implement GET before the preserve/explore contract and dual FEA rails work.
4. Implement MMC before the structured CP-SAT-to-field-to-FEA pipeline works.
5. Let CP-SAT choose arbitrary voxel occupancy as the primary representation.
6. Generate holes independently from primary structural paths.
7. Build a huge gearbox ontology before generating results.
8. Train HNC-CAD from one housing.
9. Begin with natural-language CAD modification.
10. Start DPO/RL without a qualified preference/result corpus.
11. Run full transmission/NVH analyses on every exploratory candidate.
12. Set “4,000 designs” as a success metric without measuring validity, diversity and useful response coverage.

---

## 14. Success criteria

### First technical success

```text
One protected housing patch
        +
structured CP-SAT patterns
        +
clean implicit blended reinforcements
        +
exact bore preservation
        +
reproducible screening FEA
        +
trusted validation of selected cases
```

### First campaign success

- 100–200 qualified records.
- Several visibly and topologically distinct reinforcement families.
- Demonstrated variations in bearing translation/rotation under directional load cases.
- Stable protected bore geometry across accepted variants.
- Measurable mesh/build yield.
- Fast-screening versus trusted-validation comparison.

### Surrogate success

- Input includes housing pattern plus bearing load vector.
- Output predicts bearing-frame response and key housing metrics.
- Validation includes held-out geometry families and load directions within the defined envelope.
- Model uncertainty is used to schedule additional FEA.

### Product success

Given a changed bearing load vector derived elsewhere from a changed gear design, the system can:

```text
1. Search feasible housing patterns.
2. Predict responses using the housing surrogate.
3. Select a diverse shortlist of promising designs.
4. Send only high-value candidates to trusted FEA.
5. Return a traceable recommendation with constraints and uncertainty.
```

---

## 15. Final recommendation

The project should move forward with this exact priority order:

```text
1. Exact GRC baseline and FEA truth.
2. Protected B-Rep core and minimal design contract.
3. Structured CP-SAT pattern grammar.
4. Existing implicit field generator for clean blended reinforcement geometry.
5. Precision-core mesh + separate reinforcement mesh screening rail.
6. Trusted conforming validation rail for selected variants.
7. Directional bearing-load basis dataset.
8. Quality-diversity archive and coverage tracking.
9. Housing-response surrogate: geometry + bearing loads → housing response.
10. MMC for local tuning of promising patterns.
11. GET for discovery of occasional new smooth topology archetypes.
12. Learned generative CAD, DPO, agents and natural-language layers only after validated data exists.
```

The final architectural principle is:

> CP-SAT generates structured feasible design diversity. Field geometry creates the clean blended ribs that conventional CAD automation made difficult. The unchanged B-Rep core preserves bearing cylinders and functional interfaces. FEA produces engineering truth. Surrogates learn the relationship between housing pattern and bearing-load response. MMC improves promising families; GET expands the family vocabulary.

This path preserves the strongest work already completed, fixes the precision-geometry failure mode, avoids premature CAD/LLM infrastructure, and produces the kind of varied, load-path-rich training data required for future housing optimization.
