# Plain-English Guide to the Methods and Tools for Rooted-Rib Optimization

## Direct answer

The long list mixes five very different things: optimization methods, surface-path algorithms, CAD-kernel repair tools, AI research prototypes, and uncertainty methods. They should not all be added to the implementation. The core solution should remain small: **surface-rooted parametric fins, MMC-style continuous optimization, physics-derived candidate paths, robust multi-load optimization, and a disciplined Open CASCADE Boolean pipeline**.

The highest-value additions are:

1. Use **CGAL or geometry-central** to create and manipulate root curves on the housing surface.
2. Use **curved-skeleton MMC and explicit stiffener optimization** as the mathematical model for each rib.
3. Borrow **Force Flow Member** ideas to seed ribs from principal-stress trajectories.
4. Put **bounded load directions and a KS worst-case aggregation** inside the optimizer.
5. Upgrade the CAD path to **controlled penetration → General Fuse/CellsBuilder → same-domain unification → validation**.
6. Keep **GET, OAT, TO-Master, IGA/MNFFD, and generative B-rep AI** as research or later-stage capabilities, not blockers for the current proof of concept.

## A useful classification

| Group | Examples | What they fundamentally do | Decision |
|---|---|---|---|
| Geometry representation for optimization | MMC, GET, explicit stiffeners, FFM | Describe where structural material may exist | MMC-style rooted fins now; GET later |
| Surface-curve computation | CGAL, libigl, geometry-central, MMP | Compute paths and distances along curved surfaces | Add now |
| CAD robustness | CellsBuilder, BuilderSolid, fuzzy Boolean, ShapeFix, UnifySameDomain, defeaturing | Turn proposed ribs into valid B-rep solids | Add now, but with strict limits |
| AI generation/orchestration | OAT, TO-Master, GraphBRep, DTGBrepGen, DreamCAD | Predict topologies, generate CAD-like geometry, or orchestrate tools | Research lane only |
| Analysis and optimization infrastructure | FEniTop, PyTopo3D, IGA/MNFFD | Solve topology/shape-optimization problems | Benchmark or future lane |
| Uncertainty handling | scenario sets, KS, probabilistic, reliability, interval, min-max | Prevent a design from winning only for one assumed load | Add bounded scenarios and KS now |

## GET

### What it is

**Gaussian Ensemble Topology**, or GET, represents a structure as the combined influence of many anisotropic Gaussian functions. Each Gaussian is like a smooth 3D blob with an adjustable centre, size, orientation and strength. A threshold converts the combined field into solid and empty regions. Because Gaussian functions are smooth, the resulting boundary is naturally smooth rather than a jagged voxel boundary.[^1]

A simple mental model is: instead of painting individual material cells, place and reshape a collection of smooth magnetic clouds; wherever their combined field exceeds a threshold, material exists.

### Industrial problem

Conventional density topology optimization can produce checkerboards, gray regions and irregular boundaries that require interpretation before CAD construction. GET tries to make the optimized representation smooth and explicit enough that less post-processing is required. Its published demonstrations report mesh-independent parameterization and results comparable to MMC on standard 2D and 3D compliance and compliant-mechanism benchmarks.[^1]

### How it could help

GET could be useful as a **discovery engine**. It may reveal inclined webs, curved load paths or junctions that are absent from a predefined rib library. Recurring discoveries could then be converted into new rooted-fin families.

### Why not use it as the main route

GET does not automatically know that a casting rib must remain rooted to a particular housing wall, follow a pull direction, avoid bearing bores, preserve machined interfaces or become a clean editable STEP feature. A smooth implicit field is not the same as a valid production B-rep. The method is also newer and its published evidence is predominantly benchmark-oriented.[^1]

### Plan status

**Included only as a later discovery lane. That is correct.** It should not replace rooted fins for the current proof. Revisit it only after one-fin and multi-fin rooted optimization work end to end.

## OAT

### What it is

**Optimize Any Topology**, or OAT, is a learned generative model. Instead of running topology optimization from scratch, it predicts a minimum-compliance material layout from the domain, supports, loads, volume fraction and resolution. Its architecture combines a shape/resolution-agnostic autoencoder, an implicit neural-field decoder and a conditional diffusion model. It was trained on the OpenTO corpus containing 2.2 million optimized structures and reports sub-second inference over its tested 2D resolutions.[^2][^3]

Plainly, OAT has seen millions of solved topology-optimization examples and has learned to make a fast first guess.

### Industrial problem

Repeated topology optimization can be expensive during interactive concept exploration. A foundation model can propose candidate layouts almost instantly and can provide multiple plausible designs rather than one local optimum.

### How it could help

OAT could eventually provide:

- A fast load-path picture for a simplified 2D section.
- Initial guesses for a conventional optimizer.
- A diversity generator for research experiments.
- A learned prior for future surrogate or topology-generation work.

### Why not use it now

The present problem is an imported 3D cast housing with protected B-rep interfaces, surface-attached fins, uncertain loads and a requirement for validated C3D10 results. OAT’s published task is minimum-compliance topology prediction over its training representation; it does not produce production-grade rooted ribs or guarantee valid housing CAD.[^3]

### Plan status

**Not required in the core plan, correctly.** Keep the repository as a research benchmark. It becomes relevant only if a simplified canonical representation of the housing can be defined and enough validated housing cases exist for adaptation.

## TO-Master

### What it is

TO-Master is an LLM-agent framework that translates natural-language instructions and optional geometry, mesh or image inputs into deterministic topology-optimization workflows. The agent selects tools, prepares finite-element and optimization inputs, checks meshes and boundary conditions, launches the solver, and returns fields and convergence data. Its examples cover 2D and 3D compliance, multiple load cases, thermal conduction and stress-constrained problems.[^4]

The important idea is not “an LLM solves mechanics.” The LLM plans and calls typed numerical tools; deterministic software performs mechanics and optimization.

### Industrial problem

Topology optimization has many setup steps and expert-only parameters. An agent can reduce repetitive model construction, guide a user through missing inputs, diagnose failures and explain results.

### How it could help

This directly supports the intended product architecture:

- The agent interprets intent and plans experiments.
- Geometry, meshing, optimization and solving remain deterministic tools.
- Every result carries typed inputs, checks and margins.
- The agent can propose another legal experiment after a failure.

### Why it should not generate ribs directly

An LLM should not emit arbitrary Open CASCADE geometry code and hope that it works. It should select among trusted actions such as `create_root_curve`, `optimize_fin_height`, `build_fin_solid`, `validate_keepouts` and `solve_load_envelope`.

### Plan status

**The concept is already included.** TO-Master is useful as architectural evidence, not a library that must be embedded. The current plan’s separation—agent owns reasoning, tools own geometry and physics—is the right one.

## Surface geodesics

### What a geodesic is

A geodesic is the surface equivalent of a straight line. On a flat plane it is an ordinary straight line; on a curved housing wall it is the shortest locally straight route constrained to remain on that wall.

For rooted ribs, surface paths are useful because the rib root must remain attached to the housing. A 3D line between two points may leave the wall; a surface path does not.

### CGAL Surface_mesh_shortest_path

CGAL’s package computes shortest paths between points on a triangulated surface. It supports points inside faces through barycentric coordinates and does not require a convex mesh. Its implementation is based on the Xin–Wang improvement of the Chen–Han exact-geodesic family.[^5][^6]

**Use it when:** two anchor points are known and a globally shortest path over the selected surface patch is wanted.

**How it helps:** it can create an initial root curve between a bearing-seat region and a wall or barrel while remaining on the triangulated housing skin.

**Limitation:** the shortest route is not automatically the best structural route. It should produce a seed or a length regularizer, not dictate the final fin.

### libigl

libigl is a compact C++ geometry-processing library built around Eigen matrices. Its `exact_geodesic` routine implements the Mitchell–Mount–Papadimitriou family for exact distances on triangular meshes.[^7]

**Use it when:** a quick matrix-oriented prototype needs exact source-to-target distances with minimal framework overhead.

**How it helps:** distance fields can enforce spacing between fin roots, find nearest anchors, or measure whether two proposed roots are too close.

**Limitation:** the exposed exact-geodesic interface is more distance-oriented than a complete surface-curve editing framework. CGAL or geometry-central is usually more convenient for richer path handling.

### geometry-central

geometry-central provides high-level intrinsic surface algorithms. It can trace a path from a surface point in a tangent direction and can shorten a path or network by intrinsic edge flips. Its flip-geodesic implementation is designed to preserve non-crossing relationships and can also support surface Bézier constructions.[^8][^9]

**Use it when:** a root curve must be moved, traced from a stress direction, shortened, smoothed or treated as part of a network rather than merely connected by a globally shortest route.

**How it helps:** this is a strong match for moving root-curve control points over a housing wall while keeping the curve on the surface.

**Limitation:** its algorithms operate on a manifold triangle mesh. The final curve must still be transferred to the corresponding CAD face or face parameter space.

### MMP

MMP means the **Mitchell–Mount–Papadimitriou** exact geodesic algorithm. Conceptually, it propagates distance information across mesh triangles while respecting how paths unfold across edges. libigl exposes an implementation derived from this method; CGAL uses a later optimized exact-geodesic lineage.[^6][^7]

MMP is an algorithm, not a separate CAD library. There is little benefit in implementing it from scratch when CGAL and libigl already provide maintained implementations.

### Plan status

**Surface geodesics are not explicit enough in the attached plan and should be added.** They belong in the root-curve initialization and constraint layer. Recommended split:

- CGAL for anchor-to-anchor shortest paths and surface distance fields.
- geometry-central for directional tracing and curve/network manipulation.
- Do not integrate both initially unless each has a demonstrated role; one compiled surface-geometry service is preferable.

## Explicit stiffener optimization

### What it is

Explicit stiffener optimization treats every rib as a geometric object with meaningful variables: skeleton curve, endpoints, control points, thickness, height and presence. Research on stiffened plates shows simultaneous optimization of stiffener shape, size and layout with both straight and curved skeletons. Because the design is explicit, the result has clear stiffener boundaries rather than an image that must be interpreted.[^10][^11]

### Industrial problem

Density topology optimization answers “where should material exist?” but often does not answer “which cast rib should the engineer model?” Explicit methods keep the design language close to real stiffeners.

### How it helps

This is almost exactly the housing problem. A rooted fin can be parameterized by:

- A surface root curve.
- A height spline along the root.
- Thickness and draft.
- Root and end treatment.
- A presence variable.

These variables can drive both the smooth voxel projection used for sensitivities and the exact B-rep builder used for final validation.

### Plan status

**This should be the core of the revised plan.** It is the strongest research match and directly addresses the measured failure of floating plates.

## MMC

### What it is

**Moving Morphable Components** represents the structure as a collection of parameterized members. Instead of assigning a density to every cell, the optimizer moves, rotates, bends, grows, shrinks, overlaps or removes components. Curved MMC variants use Bézier or NURBS skeletons, which gives direct control over the shape and position of each structural member.[^11][^12]

A rooted fin is a specialized MMC component: its skeleton is constrained to the housing surface and its cross-section grows outward from that surface.

### Industrial problem

MMC narrows a huge cell-by-cell search into a smaller set of engineering variables. It also avoids much of the topology-to-CAD interpretation problem because the components already have geometric meaning.

### How it helps

MMC provides the mathematical pattern for:

- Smooth projection of a fin onto the existing voxel grid.
- Analytical or automatic derivatives with respect to curve controls, height and thickness.
- Presence/removal variables for topology changes.
- Feature-size constraints and casting bounds.

### Why a custom version is still needed

Generic MMC components move freely in space. Housing fins must obey stronger rules: roots remain on approved faces, fin direction respects casting, height fades correctly, keep-outs remain untouched and junctions remain buildable. Therefore, the correct implementation is **MMC-inspired surface-attached fins**, not an unmodified MMC package.

### Plan status

**Included as later continuous refinement, but it should move forward and become the core representation now.** CP-SAT should still select discrete patterns and junction rules around this continuous component optimizer.

## Force Flow Members

### What they are

Force Flow Members, or FFM, are clear stiffener curves extracted from principal-stress trajectories. The published CAD-integrated workflow traces dense stress trajectories, clusters them into representative members, represents those members as NURBS curves in a surface parameter domain and then optimizes their heights. It couples this geometry with an isogeometric workflow for stiffened shells.[^13]

Plainly, FFM asks: “In which directions is force naturally trying to travel over this wall?” It then places understandable stiffeners along those directions.

### Industrial problem

A fixed spoke/ring library may miss inclined or curved load paths. Raw stress plots are also too dense for an engineer to turn directly into ribs. FFM reduces a field into a few readable structural members.

### How it helps

FFM is ideal for **seeding** root curves:

1. Solve the bare or baseline housing.
2. Project relevant stress directions onto approved housing surfaces.
3. Trace many surface trajectories.
4. Cluster nearby trajectories.
5. Fit a few root curves.
6. Let MMC-style optimization adjust them.

This can discover chords and inclined fins beyond radial spokes.

### Why not copy the complete method

The published FFM workflow targets stiffened shell structures and uses a NURBS/IGA stack. The housing is a thick cast solid with an already validated C3D10 route. Replacing that route with full IGA would create a large new program of work.

### Plan status

**The plan mentions cheap load lines inspired by FFM; keep and strengthen this.** Add principal-stress trajectory tracing and clustering as a candidate generator, but retain C3D10 as final authority.

## IGA and MNFFD

### What IGA is

**Isogeometric Analysis** uses CAD-like spline basis functions, often NURBS, for both geometry and numerical analysis. The attraction is that design geometry and analysis geometry share the same mathematical representation, reducing repeated CAD-to-mesh conversion.

### What MNFFD is

**Multi-level NURBS-based Free-Form Deformation** embeds curves and surfaces in nested NURBS parameter spaces. In the cited stiffened-shell workflow, curves represent stiffeners and cutouts, surfaces represent skins or ribs, and the same mappings support design, analysis and optimization.[^14]

### Industrial problem

Traditional shape optimization can require repeated remeshing and can introduce inconsistency between CAD control points and FE nodes. IGA/MNFFD aims to keep geometry exact and sensitivities smooth during optimization.

### How it could help

The most valuable transferable idea is not the entire IGA solver. It is this:

> Define root curves in a 2D surface parameter domain, optimize them there, and map them consistently to the 3D housing surface.

That gives stable surface attachment and low-dimensional variables.

### Why not adopt full IGA now

The housing is an imported multi-face solid, not one clean NURBS shell. A full IGA route would require patch decomposition, coupling across trimmed and non-matching faces, loads/support remapping, solid analysis verification and a new validation campaign. That would distract from the immediate representation and Boolean problems.

### Plan status

**Not in the core plan, correctly.** Borrow the parameter-space mapping concept. Consider full IGA only for a future product lane focused on thin-walled shells or composite panels.

## Spline fitting details

### Feature-sensitive parameterization

Uniformly spaced spline parameters spend the same representational effort everywhere. Feature-sensitive parameterization allocates more parameter space—and therefore more effective control—to regions with high curvature or rapidly changing normals. Published work shows that uniform knots combined with such a parameterization naturally place more fitting capacity around ridges, valleys and curved features.[^15]

**How it helps:** when a root curve crosses a strongly curved transition, more control is needed there than on a nearly planar wall. This can reduce fitting error without increasing control points everywhere.

**Plan status:** not explicitly included. Add it only after the basic root-curve representation works. For the first proof, use adaptive control-point insertion based on geometric fitting error; it is simpler.

### Third-order surface energies

Second-order smoothness penalizes curvature. Third-order energies penalize how quickly curvature changes. They are used in aesthetic surface design to suppress waviness and produce visually smooth curvature transitions.[^16][^17]

**How it helps:** it could smooth a free-form housing skin or a broad blended rib surface.

**Why it is not central:** the immediate object is a thin fin with a root curve and height profile, not an automotive Class-A surface. Arc-length, curvature and height-slope penalties are simpler and easier to engineer.

**Plan status:** correctly absent. Consider only after basic manufacturability and structural performance work.

## Robust loading frameworks

### Three different questions

| Framework | Question answered | Data required | Best use here |
|---|---|---|---|
| Probabilistic robust | Is average performance good and variability small? | Estimated distributions or at least moments | Later, when telemetry or a credible duty-cycle model exists |
| Reliability-based | Is failure probability below a target? | Credible probability distributions and failure thresholds | Certification-oriented later stage |
| Non-probabilistic interval | Does it work for every load inside agreed bounds? | Defensible ranges, not probabilities | Best current choice |

Research comparisons distinguish these approaches: moment-based robust formulations use mean and variance; reliability-based formulations impose failure-probability constraints; non-probabilistic formulations seek feasibility across bounded uncertainty sets.[^18]

The current project knows that load direction is not fixed but does not yet have enough statistical evidence to claim a probability distribution. Therefore, an interval/scenario formulation is more honest than Monte Carlo probabilities.

### Multiple cases and KS aggregation

The **Kreisselmeier–Steinhauser function** is a smooth approximation of a maximum. If twelve load cases produce twelve objective values, KS turns them into one differentiable number dominated by the worst cases while retaining gradient contributions from more than one case. Multi-load topology research reports more stable optimization than treating only the currently active bound.[^19]

A practical normalized form is:

\[
J_{KS}=J_{max}+\frac{1}{\rho}\log\left(\sum_i \exp\left(\rho(J_i-J_{max})\right)\right)
\]

Here, larger \(\rho\) makes the result closer to a hard maximum.

**How it helps:** the optimizer can no longer create a brilliant design for one rotor-bending direction and ignore the others.

### Separating sampling from optimization

For linear elastic systems, responses to load components can be combined through superposition. The existing component-response storage can therefore evaluate many load mixtures without rerunning every base component solve, provided boundary conditions and material behavior remain linear and the response metric is assembled correctly.

This does not eliminate optimization cost entirely: each design iteration still needs the required independent load-basis solves and corresponding sensitivities. It does eliminate wasteful Monte Carlo FE solves for every sampled linear combination.

### Min-max game

In game-theoretic robust topology optimization, one player chooses the structure while another chooses the worst admissible load. The design player minimizes the objective; the load player maximizes it. Published work formulates this as a generalized Nash or alternating worst-load/design problem for uncertain load directions.[^20]

**How it helps:** it can search a continuous angle range rather than relying only on twelve manually sampled directions.

**Why not start there:** it is a nested optimization and adds convergence complexity. First use a defensible finite envelope with adaptive enrichment: optimize over current cases, search the angle range for a worse case, add it, and repeat. This gives most of the value with much less implementation risk.

### Plan status

The plan includes load families but should be made more precise:

- Add bounded physical parameters, not arbitrary independent component rotations.
- Start with engineer-approved extreme and intermediate directions.
- Use normalized KS or smooth worst-case aggregation during optimization.
- Add adaptive worst-case search after the finite-case implementation is stable.
- Reserve probabilistic and reliability methods for when real distributions are available.

## Open CASCADE robustness

### BOPAlgo_BuilderSolid

BuilderSolid takes faces and tries to assemble closed shells and solids. Current documentation includes classification of unused faces, warnings for faces that cannot be classified and an option to avoid adding internal shapes. Earlier OCCT changes specifically stopped constructing invalid internal solids from unclassified faces.[^21][^22]

**Problem solved:** after complex splitting or fusing, the kernel may have many faces whose correct shell membership must be decided.

**How it helps:** use a recent, pinned OCCT version and capture every warning. An unclassified face must fail the geometry gate; it must not silently enter the result.

**Plan status:** not explicit enough. Add version pinning, `SetAvoidInternalShapes(true)` where appropriate, warning capture and result-content checks.

### General Fuse and CellsBuilder

General Fuse splits all input arguments against one another and returns the resulting cells. `BOPAlgo_CellsBuilder` lets the application select the desired cells and remove internal boundaries between cells assigned the same material.[^23][^24]

**Problem solved:** sequentially fusing rib 1, then rib 2, then rib 3 repeatedly modifies topology and can compound slivers and naming instability. Batch splitting sees all interactions together.

**How it helps:** submit the housing and all selected fin solids in one operation, classify which cells belong to the final casting, give them the same material and remove internal boundaries.

**Plan status:** this should be added as the preferred multi-fin construction experiment. It is not a guarantee; compare it empirically against a standard batch fuse and keep the more reliable path.

### ShapeUpgrade_UnifySameDomain

This tool merges adjacent faces on the same supporting surface and adjacent edges on the same curve. It can simplify planar or cylindrical regions fragmented by a Boolean and records modification history.[^25][^26]

**Problem solved:** valid Boolean results may contain unnecessary coplanar face fragments and split edges that complicate meshing and downstream selection.

**How it helps:** run it after a successful Boolean, then validate protected faces, volume, topology and tolerances again.

**Important correction:** it should not be applied blindly as a promise to repair every model. It can alter face identity, and it does not remove real notches or geometric slivers that lie on different surfaces.

**Plan status:** add it to the post-Boolean candidate pipeline with A/B testing and history tracking.

### Fuzzy Boolean operations

Fuzzy Boolean mode adds a user-selected tolerance so that small gaps or near-coincident entities can be treated as coincident. OCCT recommends determining the fuzzy value from the measured gap or embedding depth rather than choosing a large arbitrary value.[^27][^28]

**Problem solved:** imported geometry and near-touching tools often differ by slightly more than stored tolerances, causing missed intersections or tiny unwanted entities.

**How it helps:** use a measured, bounded fuzzy value only on a retry step, after a zero-fuzz attempt. Record the value in the design manifest.

**Danger:** a large fuzz can erase a deliberate clearance, merge distinct faces or change protected geometry. It is not a general “robustness” switch.

**Plan status:** should be added to the controlled retry ladder, not enabled globally.

### Shape healing

OCCT’s ShapeFix tools can repair wire connectivity, missing or inconsistent 2D/3D curves, small edges and tolerance problems. OCCT also recommends checking with `BRepCheck_Analyzer` and using ShapeAnalysis/ShapeFix/ShapeUpgrade for invalid shapes.[^29][^30]

**Problem solved:** imported STEP shapes may contain inconsistent p-curves, disconnected wire topology or tolerances that later break Booleans.

**How it helps:** create a healed computational copy at import, compare it to the source and freeze that qualified baseline for the study.

**Danger:** “remove every small edge” can change real design detail. Healing must have a maximum tolerance, a geometry-deviation report and protected-interface checks.

**Plan status:** partially implicit in vetting, but should become an explicit baseline-qualification stage.

### Defeaturing

`BRepAlgoAPI_Defeaturing` removes selected faces representing holes, protrusions, gaps, chamfers or fillets and rebuilds a new shape. It supports solids, compsolids and compounds of solids.[^31]

**Problem solved:** tiny nonfunctional features can make meshing or Boolean operations unnecessarily difficult.

**How it could help:** create a separate simplified analysis or discovery model by removing approved cosmetic details.

**Why it should not be a default fix:** holes, fillets and protrusions may be functionally or structurally important. Defeaturing the authoritative housing could corrupt the comparison with production.

**Plan status:** correctly absent from core generation. Add it only as an engineer-approved preprocessing option on a derived copy, never as an automatic Boolean repair.

## Better STEP and AI B-reps

### Better STEP

Better STEP is an HDF5-based open representation and dataset for B-rep geometry and topology. It is designed for scalable data processing without requiring a CAD kernel for every downstream sampling, normal or curvature query.[^32][^33]

**Industrial problem:** large CAD-ML pipelines are awkward when every worker must parse STEP through a kernel or licensed stack.

**How it helps:** it could become an efficient ML/analytics cache for face graphs, surface samples, curvature and feature-learning datasets.

**What it does not do:** it is not a replacement for authoritative STEP exchange, Open CASCADE modeling or production CAD validation.

**Plan status:** not needed now. Consider later when the platform has thousands of accepted B-rep variants and trains geometry models at scale.

### GraphBRep

GraphBRep represents B-rep surfaces as graph nodes and surface contacts as graph edges. It learns surfaces, adjacency and edge geometry in conditioned stages, making topology an explicit generation target rather than hiding it inside geometric features.[^34][^35]

**Problem solved:** generative B-rep models must create both plausible surfaces and a valid incidence graph; learning only coordinates is insufficient.

**How it helps:** its representation is valuable for future face recognition, similarity search, failure prediction and learned feature proposals.

**Why not use it to make housing ribs:** it generates distributions of CAD objects; it does not preserve an arbitrary customer housing’s bearing faces and add a guaranteed rooted fin under engineering rules.

**Plan status:** future geometry-intelligence research, not the current builder.

### DTGBrepGen

DTGBrepGen separates B-rep generation into topology first and geometry second. It predicts edge–face and edge–vertex adjacency, then generates vertices, curves and B-spline surfaces with Transformer/diffusion models. Its code is public.[^36][^37]

**Problem solved:** geometry and topology are coupled, and generating one without the other creates invalid solids.

**How it helps:** it is a useful research baseline for understanding learned topology validity and for future synthetic CAD generation.

**Why not use it now:** multi-stage generation can accumulate errors, requires large training resources and still cannot guarantee preservation of a specific imported housing. The published repository reports training on multiple A800 GPUs, underscoring that this is a research program, not a small integration.[^36]

**Plan status:** not included, correctly.

### DreamCAD

DreamCAD generates editable parametric surface patches from text, images or points using point-level supervision and differentiable tessellation. Its goal is to exploit large mesh datasets without requiring full CAD construction histories or B-rep labels.[^38]

**Problem solved:** high-quality CAD training data with feature histories is scarce, while point clouds and meshes are abundant.

**How it helps:** it may eventually support concept reconstruction or editable surface generation from simulation/discovery geometry.

**Why not use it for the present task:** generating connected surface patches from point supervision is fundamentally different from performing a controlled, dimension-preserving edit on an existing production B-rep.

**Plan status:** research watchlist only.

## FEniTop

### What it is

FEniTop is an open-source FEniCSx-based topology-optimization framework supporting 2D and 3D, structured and unstructured meshes, different element types and distributed parallel execution. Its modular implementation separates the FE solve, parameterization, sensitivity and optimizer components.[^39][^40]

### Industrial problem

It reduces the effort needed to prototype new PDE-constrained topology formulations and scale them beyond a single workstation.

### How it could help

Use it as:

- An independent reference for small compliance and multi-load tests.
- A sandbox for formulations that are awkward in the custom voxel solver.
- A future route for multiphysics or unstructured design domains.

### Why not migrate now

The existing GPU voxel solver, deck mapping and C3D10 validation are already central assets. A FEniCSx migration would not solve the root-attachment or B-rep construction problem, which is the present bottleneck.

### Plan status

**Not part of the core plan, correctly.** Add only as an independent benchmark and formulation sandbox.

## PyTopo3D

### What it is

PyTopo3D is a Python implementation of 3D SIMP compliance optimization with volume constraints, obstacle regions, sparse solvers and optional CuPy GPU support.[^41][^42]

### Industrial problem

It makes conventional 3D density topology optimization accessible in Python without starting from old MATLAB reference codes.

### How it could help

It can provide a quick free-density benchmark showing where unrestricted material would like to form. This is valuable as an explanatory reference and as a check against the custom solver.

### Why it is not the final method

SIMP still produces a density field. It does not inherently produce attached cast fins, editable STEP, draft, root fillets or stable functional interfaces. Replacing the current solver with PyTopo3D would return to the same interpretation gap already encountered.

### Plan status

**Research/benchmark only.** The plan already keeps free-cell topology as an explanatory picture rather than the design representation; that is the right role.

## build123d

### What it is

build123d is a Pythonic parametric B-rep modeling framework on Open CASCADE. It supports explicit geometry, selectors, Boolean composition and STEP import/export.[^43][^44]

### Industrial problem

Raw Open CASCADE APIs are verbose and difficult to maintain. A higher-level Python layer can make deterministic feature builders easier to read, test and expose as agent tools.

### How it could help

It is suitable for implementing a concise `FinFeature` prototype with parameters such as root wire, height profile, thickness, draft and penetration. It can also make reproducible test cases and STEP export easier.

### Why it does not solve robustness itself

build123d uses the same Open CASCADE kernel underneath. A failing geometric intersection can still fail. Advanced control of CellsBuilder, fuzzy tolerances, shape history and detailed diagnostic reporting may require dropping into the underlying OCCT APIs.

### Plan status

The plan currently uses Open CASCADE directly. **Do not rewrite working code only to adopt build123d.** Use it if it accelerates a small prototype or becomes a thin authoring layer, but keep one authoritative OCCT geometry pipeline rather than two competing stacks.

## Recommended architecture

```text
Approved B-rep faces and keep-outs
              ↓
Triangulated surface + CAD-face correspondence
              ↓
Root-curve seeds
  - spokes/rings/chords
  - CGAL/geometry-central paths
  - FFM stress trajectories
              ↓
Surface-attached MMC fin variables
  - curve controls
  - height profile
  - thickness/draft
  - presence
              ↓
Smooth projection to fixed voxel grid
              ↓
Multi-load linear solves + KS objective
              ↓
Continuous optimization
              ↓
CP-SAT topology/manufacturing decisions
              ↓
Exact fin solids with controlled root penetration
              ↓
Batch General Fuse / CellsBuilder
              ↓
UnifySameDomain + validity/protection checks
              ↓
STEP re-import → C3D10 mesh → final solve
```

The key is that the same compact fin parameters generate both the optimization field and the exact CAD. There is no image-to-CAD reconstruction stage.

## Revised implementation order

### Phase 0: qualify the baseline

- Pin one supported OCCT version and Python binding build.
- Run validity, tolerance and p-curve checks on the imported housing.
- Create a healed copy only if required; quantify all deviations.
- Freeze protected bores, mating faces, mounting faces, volume and face signatures.

### Phase 1: one rooted fin

- Triangulate one approved housing surface patch with CAD-face correspondence.
- Generate one anchor-to-anchor surface curve.
- Fit it into the CAD face’s UV domain or a piecewise multi-face representation.
- Add 3–5 height controls, thickness, draft and controlled penetration.
- Project the same fin to the voxel grid.
- Verify analytical/automatic gradients against finite differences.

### Phase 2: prove CAD stability

- Perturb every parameter through its allowed range.
- Compare standard fuse, batch General Fuse and CellsBuilder.
- Test zero fuzz first and measured fuzzy retries second.
- Test UnifySameDomain as post-processing.
- Require valid solid, one intended body, no unclassified faces, protected-interface invariance, STEP re-import and C3D10 meshability.

### Phase 3: robust physics

- Define physical uncertain variables: rotor-bending direction, torque/thrust bounds and correlations.
- Create an initial finite scenario envelope.
- Optimize normalized KS across the scenarios.
- Search the continuous uncertainty range for a worse case, append it and repeat.

### Phase 4: multi-fin topology

- Introduce multiple roots, controlled crossings, shared endpoints and tee junctions.
- Use CP-SAT for presence, symmetry, counts, spacing, junction legality and thickness catalogues.
- Keep continuous optimization for curve positions and height profiles.

### Phase 5: physics-derived discovery

- Trace principal-stress directions over approved surface patches.
- Cluster trajectories into FFM-like candidate roots.
- Compare these seeds against spokes, rings and chords.
- Add GET or OAT only as separate discovery experiments.

### Phase 6: agent layer

- Expose typed tools rather than raw CAD scripting.
- Let the agent choose experiments, diagnose failed gates and explain margins.
- Never let the agent modify loads, protected geometry or manufacturing rules without engineer approval.

## Final decisions

| Idea | Use now? | Exact role |
|---|---:|---|
| Curved-skeleton MMC | Yes | Core rooted-fin parameterization and optimization |
| Explicit stiffener optimization | Yes | Main mathematical formulation |
| CGAL surface shortest paths | Yes | Initial root paths and distance fields |
| geometry-central | Likely | Directional tracing and path/network editing; choose after a small bake-off |
| libigl/MMP | Optional | Lightweight exact-distance prototype or benchmark |
| FFM | Yes, selectively | Principal-stress-derived root seeds |
| KS aggregation | Yes | Smooth worst-case objective across load scenarios |
| Interval/scenario uncertainty | Yes | Honest current treatment of unknown load direction |
| Min-max game | Later | Adaptive continuous worst-load search |
| CellsBuilder/GFA | Yes, test | Batch multi-fin Boolean construction |
| BuilderSolid safeguards | Yes | Solid classification, warning and internal-shape controls |
| UnifySameDomain | Yes, guarded | Remove redundant same-surface splits after Boolean |
| Fuzzy Boolean | Retry only | Handle measured near-coincidence |
| ShapeFix/healing | Baseline only | Qualify imported computational copy |
| Defeaturing | Rare/approved | Simplified

---

## References

1. [Gaussian Ensemble Topology (GET): A New Explicit and Inherently ...](https://arxiv.org/abs/2510.05572) - Abstract:We introduce the Gaussian Ensemble Topology (GET) method, a new explicit and manufacture-re...

2. [Pretrained Checkpoints](https://github.com/ahnobari/OptimizeAnyTopology) - Optimize Any Topology: A framework for developing foundation models for topology optimization. - ahn...

3. [Optimize Any Topology: A Foundation Model for Shape - arXiv](https://arxiv.org/html/2510.23667v1)

4. [an LLM-agent framework for automated topology optimization - arXiv](https://arxiv.org/html/2607.01812v1) - This case shows that TO-Master can connect image-based geometry generation with topology optimizatio...

5. [◆ Barycentric_coordinate](https://doc.cgal.org/latest/Surface_mesh_shortest_path/classCGAL_1_1Surface__mesh__shortest__path.html)

6. [CGAL 6.2.1 - Triangulated Surface Mesh Shortest Paths](https://doc.cgal.org/latest/Surface_mesh_shortest_path/index.html)

7. [libigl/include/igl/exact_geodesic.h at main - GitHub](https://github.com/libigl/libigl/blob/main/include/igl/exact_geodesic.h) - ... Exact geodesic algorithm for triangular mesh with the implementation from https://code.google.co...

8. [Tracing Geodesic Paths](https://geometry-central.net/surface/algorithms/geodesic_paths/)

9. [Flip Geodesics](https://geometry-central.net/surface/algorithms/flip_geodesics/)

10. [[PDF] Explicit Topology Optimization Design of Stiffened Plate Structures ...](https://www.techscience.com/ueditor/files/cmes/TSP_CMES-135-2/TSP_CMES_23561/TSP_CMES_23561.pdf)

11. [Explicit Topology Optimization Design of Stiffened Plate ...](https://www.techscience.com/CMES/v135n2/50174/html) - This paper proposes an explicit method for topology optimization of stiffened plate structures. The ...

12. [Moving morphable component (MMC) topology optimization ... - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10760668/) - The skeleton of the modified component is described by the NURBS curve, then proposed to directly ge...

13. [CAD-integrated stiffener sizing-topology design via force flow members (FFM)](https://www.sciencedirect.com/science/article/abs/pii/S0045782523003250) - Stiffener design plays a crucial role in the lightweight design of stiffened panels. We propose a CA...

14. [An isogeometric design-analysis-optimization workflow of stiffened thin-walled structures via multilevel NURBS-based free-form deformations (MNFFD)](https://www.sciencedirect.com/science/article/abs/pii/S0045782523000592) - Stiffened thin-walled structures are widely used in various fields as load-carrying components, but ...

15. [doi:10.1016/j.cad.2006.04.007](https://archive.ymsc.tsinghua.edu.cn/pacm_download/12/436-cad_2006_fitting.pdf)

16. [[PDF] Minimizing Curvature Variation for Aesthetic Surface Design](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2008/EECS-2008-129.pdf)

17. [An intuitive explanation of third-order surface behavior](https://people.eecs.berkeley.edu/~sequin/PAPERS/2010_CAGD_HiOrderSurf.pdf)

18. [probabilistic topology optimization under uncertain loads ...](https://repositorio.usp.br/bitstreams/f1150428-114e-4fae-9e4a-0216e39a15fd)

19. [[PDF] Structural topology optimization for multiple load cases using a ...](https://websites.umich.edu/~mdolaboratory/pdf/James2009a.pdf)

20. [Game theory approach to robust topology optimization with uncertain loading](https://d-nb.info/1116315440/34)

21. [Open CASCADE Technology Reference Manual: BOPAlgo ...](https://occt3d.com/dev/doc/refman/html/class_b_o_p_algo___builder_solid.html) - Open CASCADE Technology 8.0.1 API reference: BOPAlgo_BuilderSolid Class Reference.

22. [OCCT v.7.3.0 Release Notes](https://dev.opencascade.org/sites/default/files/pdf/release_notes_7.3.0.pdf)

23. [BOPAlgo_CellsBuilder Class Reference - Open CASCADE ...](https://occt3d.com/dev/doc/refman/html/class_b_o_p_algo___cells_builder.html) - Open CASCADE Technology 8.0.1 API reference: BOPAlgo_CellsBuilder Class Reference.

24. [Open CASCADE Technology Reference Manual: Data Structures](https://occt3d.com/dev/doc/refman/html/annotated.html) - Open CASCADE Technology 8.0.1 API reference: Data Structures.

25. [ShapeUpgrade_UnifySameDom...](https://occt3d.com/dev/doc/refman/html/class_shape_upgrade___unify_same_domain.html) - Open CASCADE Technology 8.0.1 API reference: ShapeUpgrade_UnifySameDomain Class Reference.

26. [Shape Healing - Open CASCADE Technology - OCCT3D](https://occt3d.com/dev/doc/overview/html/occt_user_guides__shape_healing.html) - Open CASCADE Technology 8.0.1 guide: Shape Healing.

27. [[PDF] OCCT v.6.9.0 Release Notes - Open CASCADE Technology](https://dev.opencascade.org/sites/default/files/pdf/OCCT_release_notes_6.9.0.pdf)

28. [Fuzzy Boolean Operations](https://dev.opencascade.org/content/fuzzy-boolean-operations) - Fuzzy Boolean Operations - solution of problems, Open CASCADE Technology.

29. [Boolean Operations - Open CASCADE Technology](https://dev.opencascade.org/doc/overview/html/specification__boolean_operations.html) - Open CASCADE Technology 8.0.1 guide: Boolean Operations.

30. [shape_healing · Open-Cascade-SAS/OCCT Wiki · GitHub](https://github.com/Open-Cascade-SAS/OCCT/wiki/shape_healing) - Open CASCADE Technology (OCCT) is an open-source software development platform for 3D CAD, CAM, CAE....

31. [BRepAlgoAPI_Defeaturing Class Reference](https://dev.opencascade.org/doc/refman/html/class_b_rep_algo_a_p_i___defeaturing.html)

32. [Better STEP, a format and dataset for boundary representation - arXiv](https://arxiv.org/abs/2506.05417) - Boundary representation (B-rep) generated from computer-aided design (CAD) is widely used in industr...

33. [Better Step: Open‑source CAD Data Conversion & Sampling¶](https://better-step.github.io/) - A Better Step

34. [GraphBrep: Learning B-Rep in Graph Structure for Efficient CAD Generation](https://arxiv.org/abs/2507.04765) - Direct B-Rep generation is increasingly important in CAD workflows, eliminating costly modeling sequ...

35. [GraphBRep: Explicit Graph Diffusion of B–Rep Topology for Efficient ...](https://academic.oup.com/jcde/article/13/1/259/8381229) - Abstract. Direct B-Rep generation is increasingly important in Computer-Aided Design (CAD) workflows...

36. [DTGBrepGen: A Novel B-rep Generative Model through Decoupling ...](https://github.com/jinli99/DTGBrepGen) - DTGBrepGen is a novel framework for automatically generating valid and high-quality Boundary Represe...

37. [DTGBrepGen: A Novel B-rep Generative Model through ...](https://arxiv.org/abs/2503.13110) - Boundary representation (B-rep) of geometric models is a fundamental format in Computer-Aided Design...

38. [DreamCAD: Scaling Multi-modal CAD Generation using ... - arXiv](https://arxiv.org/abs/2603.05607) - Computer-Aided Design (CAD) relies on structured and editable geometric representations, yet existin...

39. [GitHub - missionlab/fenitop: FEniCSx-based topology optimization supporting parallel computing](https://github.com/missionlab/fenitop) - FEniCSx-based topology optimization supporting parallel computing - missionlab/fenitop

40. [FEniTop: a simple FEniCSx implementation for 2D and 3D ...](https://zhang.cee.illinois.edu/wp-content/uploads/2025/05/jia_fenitop_2024.pdf)

41. [PyTopo3D: 3D SIMP Topology Optimization Framework for ...](https://github.com/jihoonkim888/PyTopo3D) - PyTopo3D: 3D SIMP Topology Optimization Framework for Python - jihoonkim888/PyTopo3D

42. [A Python Framework for 3D SIMP-based Topology Optimization - arXiv](https://arxiv.org/html/2504.05604v1) - The PyTopo3D source code described in this paper is publicly available. The primary development repo...

43. [gumyr/build123d: A python CAD programming library - GitHub](https://github.com/gumyr/build123d) - build123d is a Python-based, parametric boundary representation (BREP) modeling framework for 2D and...

44. [About — build123d 0.11.1 documentation](https://build123d.readthedocs.io/en/stable/)

