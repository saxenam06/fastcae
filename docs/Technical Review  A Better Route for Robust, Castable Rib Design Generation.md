# Technical Review: A Better Route for Robust, Castable Rib Design Generation

## Executive verdict

The new direction in `design-generation.md` is fundamentally correct: the next representation should be a **surface-rooted fin**, described by a root curve on the housing, a height field along that curve, thickness, draft, and a continuous presence variable. That diagnosis follows directly from the strongest evidence in the project: production ribs have 16–33% root attachment, generated forms have only 0–2%, and the best physics-driven plate locations lose their gains when the CAD construction turns them into notched, weakly attached solids.[^1]

However, the current proposal is not yet a complete solution. It should be upgraded from “one differentiable fin” into a **robust, surface-attached explicit-component optimizer with two synchronized realizations**:

1. A smooth fixed-grid analysis representation, used for gradients and robust load optimization.
2. A clean B-rep feature representation generated from the same parameters, used only at checkpoints and final validation.

The best route is therefore **not** a return to voxel-to-CAD reconstruction, a larger discrete rib library, generic MMC, or GET. It is a purpose-built hybrid of force-flow stiffeners, curved-skeleton MMC/generalized geometry projection, casting-aware fin features, worst-case load optimization, and a robust CAD realization pipeline. Published work supports explicit curved stiffeners, geometric components projected to fixed analysis meshes, NURBS force-flow paths, variable height, and manufacturing constraints; no available repo supplies the housing-specific combination out of the box.[^2][^3][^4][^5]

The immediate recommendation is to stop expanding the eleven-form library and run a tightly gated **rooted-fin proof**. It should optimize one then several continuously parameterized fins on one accepted volume, include load-direction uncertainty from the first meaningful test, and prove that the final STEP preserves both the optimized parameters and structural response. CP-SAT remains useful, but as a graph/topology seeder and manufacturing-rule solver—not as the primary physics optimizer.

## What the evidence proves

The six completed campaigns already resolve several architecture questions more convincingly than another broad literature survey could. A fixed library can produce exact CAD and legal patterns, but it constrains the optimizer to variations of a supplied vocabulary. Free density and projected plates discover useful inclined and tangential material, but reconstruction or fusing destroys their structural effect. Diversity selection without physics has produced visually different but mechanically poor designs, while nominally excellent designs fail when the uncertain bending direction changes.[^1]

| Observation | What it rules out | Architectural consequence |
|---|---|---|
| Generated ribs attach along 0–2% of their perimeter, versus 16–33% for production | More sampling from the current plate library | Attachment must be part of the primitive, not a downstream test |
| Gradient plates improve the voxel objective but 25 of 30 moved plates fail because their fused outline contains sliver-producing notches | Treating CAD repair as a minor post-processing task | The optimized object and CAD object must share a smooth generative definition |
| No tested design beats production over all 12 derived cases | Nominal-case optimization followed by a robustness check | Load uncertainty must be inside optimization |
| The last diverse campaign was uniformly worse than production | Diversity as a selection objective by itself | Diversity must be constrained to a near-optimal robust performance band |
| Four silent implementation bugs removed whole shape families | Counting candidates or feature axes without coverage tests | Representation coverage and invariants require automated reports and tests |
| The fixed library’s strongest designs are mostly flat, two-ended webs | Adding more named forms as the main route | Named forms should become regions of one continuous fin parameterization |

These findings also explain why the earlier rib-family plan was necessary but insufficient. That plan correctly retained engineer-approved design volumes, exact interfaces, CP-SAT manufacturing rules, a fast fixed-grid physics model, and STEP-to-C3D10 validation. Its limiting choice was to treat candidates as prebuilt ribs and optimize mostly presence or thickness. The new evidence shows that **root path and attachment geometry are first-order design variables**; a candidate library that freezes them cannot recover the best physics-driven designs.[^6][^1]

## The recommended representation

### Surface-rooted fin

A fin should be defined by the parameter tuple

\[
q_i = \{\Gamma_i, h_i(s), t_i, \alpha_i, r_i, a_i, g_i\},
\]

where:

- \(\Gamma_i\) is a root curve constrained to an approved attachment surface or surface complex.
- \(h_i(s)\) is a nonnegative height profile along normalized arc length \(s\).
- \(t_i\) is nominal top thickness.
- \(\alpha_i\) is casting draft relative to a specified pull direction.
- \(r_i\) controls the root transition or fillet surrogate.
- \(a_i\) is a continuous presence variable used during optimization and driven toward zero or one.
- \(g_i\) identifies connectivity, symmetry, family, and manufacturing groups.

This is closely aligned with published explicit stiffener methods. Curved-skeleton MMC optimizes stiffener shape, size, and layout using explicit geometric parameters, while force-flow-member work constructs NURBS paths from principal-stress trajectories and uses control-point heights as design variables. Component projection onto a fixed ground mesh is also established for large curved stiffened shells, demonstrating the key separation between a low-dimensional geometric component and the analysis discretization.[^7][^3][^4][^5][^8][^2]

The fin direction should not automatically be the local surface normal. For a casting, the generative direction should be tied to a **declared mould pull vector or admissible pull cone**. The root lies on the housing surface, and the fin is formed as a ruled or swept feature within the approved design volume, with draft widening toward the root. Local normals may be used to initialize or regularize the construction, but blindly sweeping along changing normals can introduce twist, self-intersection, and undercuts.

### Smooth analysis field

The existing geometry-projection machinery should be retained, but its primitive should become the swept fin. A smooth density field can be formed from distance to sampled root segments, a height window, a thickness window, a root-blend term, and the presence variable. Use a smooth minimum or partition-of-unity blend between curve segments rather than a hard closest-segment switch, because the latter creates gradient discontinuities when the nearest segment changes.

For multiple fins, use a smooth union that does not double-count overlapping material. Suitable choices include a regularized maximum or probabilistic union, followed by a projection continuation. Material volume must be evaluated from the same union field used for stiffness, rather than summed per fin, or intersections will be penalized twice. Existing GGP and geometry-projection implementations are directly relevant to this field construction; the TopGGP project offers Python, Julia, and MATLAB formulations, while GPTO provides reproducible 2D/3D bar projection code.[^9][^10][^11]

The analysis geometry does **not** need to be the deliverable geometry. It needs to preserve objective ranking and gradients across the admissible parameter range. Exact functional B-rep faces, bearing cylinders, loads, and coupling definitions should remain frozen as already established in the project’s canonical validation route.[^12]

### Clean CAD feature

The CAD feature should be generated directly from \(q_i\), not extracted from its voxel density. Construct a smooth root wire, a top wire determined by \(h_i(s)\), and the two drafted side surfaces, then cap the ends and give the feature a deliberate penetration foot below the attachment surface. OCCT supports sweep construction along wires, corrected-Frenet or fixed-binormal frames, draft operations, and same-domain unification.[^13][^14][^15][^16]

The raw fin must remain a **clean, unnotched solid before fusion**. The current `_finished` operation should not first trim or union the plate against every local step in the wall; that is exactly how 7–31 short outline edges are created. Instead, let a simple fin penetrate the parent by a controlled overlap and perform one controlled Boolean composition. This changes the failure from “the design primitive itself is notched” to the narrower problem of intersecting two clean solids.

## The key architectural change

The plan currently implies that the design is differentiable and CAD-ready end to end. That should be stated more precisely:

> The **parameterization and fixed-grid analysis are differentiable**; the final B-rep Boolean is a validated realization of those parameters, not part of the gradient tape.

B-rep topology changes and Boolean classification remain discrete and can invalidate direct differentiation. Research on differentiated OCCT shows that exact CAD sensitivities are possible for controlled parameterized geometry, but it requires a differentiated kernel and careful treatment of parameterized features; it does not make arbitrary Boolean topology changes smoothly differentiable. Modern CAD-generation research likewise treats geometry and topology as coupled but distinct problems because B-rep topology is discrete.[^17][^18][^19][^20][^21]

This leads to a two-model contract:

| Model | Purpose | Must guarantee |
|---|---|---|
| Smooth fin field | Optimization, gradients, rapid robust scoring | Gradient correctness, stable continuation, rank agreement with high-fidelity solves |
| B-rep fin builder | STEP export, exact interfaces, manufacturing and meshing checks | Parameter fidelity, valid solid, clean Boolean, meshability, bounded performance loss |

The critical metric is not visual similarity. It is the **realization gap** between the optimized field and final C3D10 design. For every checkpoint, record parameter deviation, volume deviation, response deviation, and objective deviation. A route that gains 40% in the optimizer and loses 30% after fusion is not successful even if the STEP is valid.

## CAD robustness strategy

The current 5 mm² sliver threshold is a useful rejection gate, but it should not define geometry construction. The recommended CAD sequence is:

1. Build all raw fins as simple, valid solids with controlled base penetration, continuous root/tip wires, minimum end width, minimum height, and bounded curvature.
2. Validate each raw fin before fusion: solid validity, self-intersection, minimum edge length, minimum face width, pull-direction feasibility, and keep-out clearance.
3. Submit the parent and all fins to one General Fuse/CellsBuilder operation rather than repeated pairwise fuses where practical.
4. Classify and retain the intended material cells, remove internal same-material boundaries, and unify same-domain faces.
5. Use fuzzy tolerance only when measured near-coincidence justifies it, with a strict project-level cap.
6. Re-run validity, sliver, interface-preservation, volume, and meshing gates; never silently delete structurally meaningful faces.

OCCT’s General Fuse–based CellsBuilder can split all arguments, combine selected cells, and remove internal boundaries between parts assigned the same material. Fuzzy Boolean operations are designed for touching, near-coincident, or slightly misaligned entities and can suppress small entities caused by gaps, but the tolerance must be based on measured gaps rather than used as a blanket repair. Shape-healing tools can detect or remove small edges and spot/strip faces, and same-domain unification can merge coincident surfaces and curves; these are diagnostics and cleanup tools, not permission to alter engineering geometry without a deviation check.[^22][^23][^24][^25][^26][^27][^15][^28]

Two important tests should be added. First, compare sequential fuse, one-shot general fuse, and CellsBuilder on the exact same optimized fin set. Second, translate or rotate a known clean fin through the region that currently generates notches and map Boolean success, smallest-face area, and final objective. This produces an empirical **CAD-feasibility field** that can become a smooth penalty or trust region for the optimizer.

## Robust loads must come first

The present evidence says the largest technical risk is no longer simply CAD generation. It is **optimizing against an unverified load case**. The best nominal design becoming 488% worse when the bending direction changes is the classic failure mode of topology optimization under directional uncertainty.[^1]

Robust topology-optimization research distinguishes stochastic mean/variance formulations from bounded worst-case formulations. For uncertain but bounded direction, a min–max objective is appropriate; recent ground-structure work explicitly finds the critical load angle and then minimizes worst-case compliance, while related work handles continuously varying magnitude and direction rather than a small arbitrary case list. Multi-load KS aggregation is useful when there is a finite, physically validated case set, but it can still miss a critical angle between sampled cases.[^29][^30][^31][^32]

For this housing, robust loading should be implemented in two layers:

- **Engineering envelope:** define which resultants may rotate, their admissible angular ranges, correlated magnitude changes, torque sign, bearing reactions, and combinations. Each bound needs provenance from the source model, drawing, duty-cycle information, or engineer approval. Arbitrarily rotating individual deck components can create nonphysical cases.
- **Inner adversary:** at each design iteration, search the low-dimensional envelope for the load parameters that maximize the active objective. Warm-start from previous critical directions and retain several near-active cases to avoid oscillating between angles.

Because the solver is linear and component responses are already stored, load recombination can be inexpensive for a fixed design. During optimization, the basis responses must still be updated as stiffness changes, but the number of independent basis solves can remain much smaller than dense angular sampling. For a nonsmooth maximum, use an epigraph formulation or smooth maximum continuation and aggregate gradients from all active or near-active cases.[^1]

The 12 existing cases are useful as a diagnostic set, not yet a certified duty envelope. The next plan should therefore have a gate before claiming robustness: an engineer must approve the uncertainty set, and production must be solved across exactly that same set.

## Objective formulation

A single weighted sum of gear lead, largest displacement, stress, and mass is difficult to interpret and can hide unacceptable trade-offs. The prior dataset already shows bore tilt can rank almost opposite to misalignment, stress is usually nonbinding, and mass is more naturally a Pareto coordinate.[^1]

Use a constrained or lexicographic formulation:

1. Minimize worst-case gear-mesh lead or the physically accepted alignment metric.
2. Constrain worst-case bearing-seat displacement and tilt to agreed limits.
3. Constrain p-norm or aggregated stress when a reliable stress gradient is available.
4. Sweep added mass or rib volume as the Pareto parameter rather than burying it in the score.
5. Report all secondary metrics for every design, regardless of which one drives optimization.

Before the stress adjoint exists, stress can remain an outer validation gate because most historical designs passed it. It should not block the rooted-fin experiment. Once the representation works, add a relaxed p-norm/KS stress adjoint and verify it against finite differences and C3D10 stress trends.

## CP-SAT’s revised role

CP-SAT should remain in the architecture, but the order should change. A continuous fin optimizer should not be forced to choose only among thousands of pre-vetted frozen solids; that recreates the limitation already measured. Conversely, completely free continuous components tend to overlap, duplicate, cross illegally, or depend on initialization.

A stronger hybrid loop is:

1. **Seed topology:** CP-SAT selects a legal connection graph among anchors, symmetry groups, allowable root regions, and a maximum component count.
2. **Continuous optimize:** MMA or another constrained gradient optimizer moves root control points, height coefficients, thickness, draft, and presence against the robust objective.
3. **Prune and introduce:** remove components with persistently low presence; introduce a new component where the free-field sensitivity or uncovered force flow is strongest.
4. **Rule projection:** CP-SAT resolves discrete manufacturing conflicts, symmetry choices, and component-count decisions.
5. **Polish:** re-optimize continuous variables with the discrete topology fixed.
6. **Diversify:** add graph no-good cuts or repulsion in parameter space, but only keep designs within an agreed robust-performance band.

MMC research has proposed component-introduction mechanisms specifically to reduce dependence on the initial component layout. Work on CAD-like geometric constraints in MMC also shows that coincident, tangent, and normal relationships can be imposed by linking component variables algebraically, reducing design variables without making them numerical optimization constraints. These ideas fit CP-SAT seeding and continuous fin refinement better than asking CP-SAT to approximate physics with static weights.[^33][^34]

## Surface parameterization

“Root curve on the part surface” becomes difficult when the root crosses several trimmed B-rep faces. Optimizing directly in each face’s UV coordinates will encounter seams, face changes, orientation flips, and severe UV distortion. A robust implementation should use a temporary **surface atlas on a triangulated attachment skin**, while preserving the exact B-rep for export and final analysis.

Recommended representation:

- Extract only engineer-approved attachment faces and create a conforming, sufficiently fine surface mesh with persistent mapping back to B-rep face IDs and UV coordinates.
- Represent root control points as barycentric coordinates on the mesh or as coordinates in one or more low-distortion local charts.
- Trace and regularize curves intrinsically on that surface; permit controlled crossing of CAD face seams.
- At CAD export, project or interpolate the optimized sampled root back onto the exact B-rep faces and construct per-face p-curves joined with continuity and tolerance checks.

Open-source libraries can support this layer. Geometry-central traces straightest/geodesic paths on manifold surface meshes and exposes path points and end directions; CGAL computes exact geodesic shortest paths on general triangulated surfaces; libigl provides exact and heat-method geodesic distances. Research on combined surface-mesh and B-spline parameterization shows that stiffener material fields can be optimized over complex surfaces even when no analytical surface parameterization exists.[^35][^36][^37][^38][^39]

Do not require roots to be exact geodesics. Geodesics are useful initializations and regularizers, but force-flow paths and manufacturing constraints may demand non-geodesic curves. Penalize excessive geodesic curvature, short oscillations, and rapid control-point movement instead.

## Casting constraints in the variables

The representation should make bad castings difficult to express rather than relying entirely on rejection. Add the following constraints early:

- Declared pull direction or admissible pull cone per design volume.
- Draft built into thickness as a function of height.
- Lower and upper bounds on thickness, height, and root radius.
- Bounds on \(|dh/ds|\) and curvature so run-outs fade smoothly.
- Minimum root length and minimum effective attached perimeter.
- Minimum spacing measured between finished drafted footprints, not centerlines.
- No isolated height islands unless explicitly permitted.
- Controlled intersections: T and Y junctions may be allowed; shallow X crossings may be forbidden.
- Keep-out and machining allowances evaluated on the final drafted envelope.
- Local thickness/hot-spot heuristics at junctions, followed later by thermal solidification checks.

A sharp-root prototype is acceptable only for the first diagnosis-killing experiment. Root transition must enter before stress-driven optimization and before a production dataset is generated. Otherwise the optimizer learns from an unreal casting and the C3D10 stress field is dominated by a deliberately singular feature.

## Better experimental plan

### Phase A — Kill or confirm the hypothesis

Build one rooted fin in one accepted volume with a fixed root and a 3–5 coefficient height spline. The test must demonstrate:

- Root attachment comparable to the lower end of production’s measured range.
- Analytic gradients for height, lateral root movement, thickness, and presence matching central finite differences.
- A valid STEP from at least 95 of 100 random admissible parameter perturbations.
- C3D10 objective change tracking the fixed-grid objective change with acceptable rank correlation.
- Less than an agreed realization loss from optimized field to final STEP.

This should precede UI work, agent behavior, library expansion, lightening holes, and surrogate training. If the fin cannot move through a useful range without CAD failure or analysis/CAD disagreement, the representation needs revision before any campaign.

### Phase B — Prove interaction

Optimize 3–6 fins simultaneously. Include intersections, shared roots, one tee, one run-out, and a symmetry pair. This phase tests smooth union, volume accounting, gradient interference, batch fusion, and multi-rib slivers—the failure modes that a one-fin test cannot expose.

Run an ablation matrix:

| Variant | Purpose |
|---|---|
| Current floating plate | Reproduce the weak-attachment baseline |
| Rooted fin, fixed height | Isolate attachment benefit |
| Rooted fin, variable height | Measure gain from the new design variable |
| Rooted fin plus root blend | Measure stress and CAD effects |
| Nominal load only | Expose optimistic performance |
| Robust directional envelope | Measure robustness cost and layout change |
| Sequential fuse | CAD baseline |
| Batch General Fuse/CellsBuilder | Test Boolean strategy |

### Phase C — Add topology changes

Introduce CP-SAT seeding, presence continuation, pruning, and component introduction. Run several deliberately different initial graphs and measure whether they converge to distinct, similarly strong designs. A representation that reaches only one architecture from all seeds is not yet a design-family generator.

### Phase D — High-fidelity closure

For each retained design:

- Export exact STEP.
- Verify invariant interfaces and keep-outs.
- Mesh face by face with C3D10.
- Solve the full approved robust envelope.
- Compare fixed-grid and C3D10 response profiles, not only one scalar.
- Verify Code_Aster on selected boundary designs.
- Record CAD failures and performance gaps as training data for the feasibility model.

### Phase E — Dataset generation

Only after the first four phases pass should the system generate hundreds of designs. Use active sampling over mass budget, load envelope, topology graph, and manufacturing parameters. Diversity should be measured among designs that satisfy robust performance gates, not across all legal geometry.

## Revised gates

The following thresholds are proposed starting points and should be calibrated from production and meshing noise rather than treated as universal constants.

| Gate | Proposed criterion |
|---|---|
| R0: Gradient | Central finite-difference agreement for every variable type over random admissible points; failures are explicit |
| R1: Attachment | Effective attached perimeter at least 15%, or a production-calibrated lower bound |
| R2: CAD fidelity | Parameter and volume deviation after STEP realization below agreed tolerances; no unrequested geometry healing |
| R3: Realization gap | C3D10 robust objective no more than 5–10% worse than the smooth optimized prediction after bias calibration |
| R4: Ranking | Spearman rank correlation above a calibrated target, initially 0.8, between screening and C3D10 over a held-out design set |
| R5: Robustness | Passes every point in the approved uncertainty envelope or a verified continuous worst-case search |
| R6: Reliability | At least 95% CAD build success and 95% mesh/solve success over randomized admissible parameters |
| R7: Manufacturability | Draft, thickness, spacing, keep-out, junction, root-radius, and pull checks pass on final B-rep |
| R8: Value | At equal or lower rib volume, at least one family beats production on the agreed robust primary metric without violating secondary constraints |

The existing “every STEP meshes and solves” target is ideal but too brittle as an early research gate. Track build, mesh, and solve success separately so a representation failure is not confused with mesher reliability.

## Repositories and papers

### Highest-value references

| Resource | Use in this project | Limitation |
|---|---|---|
| CAD-integrated Force Flow Members | NURBS root paths from principal-stress trajectories; variable control-point heights; CAD-oriented watertight geometry[^2] | No open implementation found; focused on shell panels |
| Explicit stiffened plates via curved-skeleton MMC | Direct precedent for optimizing straight/curved stiffener shape, size, and layout[^3][^4] | Benchmark-style plates; casting and imported housing B-reps still need custom work |
| Component projection on cylindrical shells | Strong precedent for projecting geometric stiffener components onto a fixed analysis mesh[^7][^5] | Shell/beam ground model, not a thick cast housing |
| Geometric constraints in MMC | Coincident, tangent, and normal relations linked algebraically; useful for tees, shared anchors, and symmetry[^34] | Requires adaptation to surface-rooted fins |
| Robust ground structures under directional uncertainty | Continuous worst-angle inner problem and smooth maximum[^30] | Demonstrated on truss ground structures |
| Continuously varying load direction and magnitude | Confirms discrete nominal cases are insufficient for realistic robustness[^31] | Compliance-focused; housing alignment objectives need custom adjoints |

### Open-source building blocks

| Repository/tool | Recommended role | Readiness |
|---|---|---|
| TopGGP | Reference formulas and implementations for smooth component projection and gradients[^9][^10] | Useful research code; adapt rather than integrate blindly |
| GPTO | Compact 2D/3D geometry-projection validation cases and gradient reference[^11] | CC-BY-NC; licensing unsuitable for a commercial core without permission |
| MMC188 Python | Small readable MMC/MMA reference for continuation and component derivatives[^40] | 2D educational implementation |
| 256-line 3D MMC MATLAB | 3D explicit-component reference and reproducible benchmark[^41] | MATLAB educational code, not production software |
| Moveable Morphable Components Python | Open-source-oriented MMC package[^42] | Marked work in progress |
| Geometry-central | Surface mesh data structures, straightest paths, exact/heat geodesics[^36][^39][^43] | C++; needs B-rep mapping layer |
| CGAL surface shortest paths | Exact paths on arbitrary triangulated surfaces[^37][^44] | Shortest paths only; not a complete curve optimizer |
| libigl | Exact and heat geodesic utilities, broad geometry-processing support[^38][^45] | Similar limitation; root-to-B-rep export remains custom |
| build123d/OCCT | Python-accessible parametric B-rep prototyping on OCCT[^46][^47] | Direct OCCT control is still likely needed for robust batch Boolean diagnostics |
| FEniTop | Parallel FEniCSx topology-optimization reference for independent experiments[^48] | Not necessary for the existing fast solver; useful for verification only |

GET should remain a research branch, not the product path. Its Gaussian superposition yields smooth explicit boundaries and promising geometric expressiveness, but the published method is validated on standard 2D/3D benchmarks and does not solve surface attachment, casting pull, functional B-rep preservation, or exact gearbox interfaces. It may later serve as a discovery engine whose recurring shapes are fitted by rooted fins, or as a smooth junction model inside the fixed-grid representation.[^49]

Recent work on explicit reconstruction plus shape optimization is relevant as a fallback when a density result contains a genuinely new topology. It shows that NURBS reconstruction followed by fixed-grid shape optimization can limit performance deviation on benchmark cases. It is still secondary here because the project has already measured that reconstruction is where useful rib designs are being lost; the preferred representation should avoid reconstruction entirely for the main lane.[^50][^51]

## Implementation blueprint

### Parameter data model

Each fin record should contain:

- Persistent ID and graph node/edge IDs.
- Attachment-surface region and chart ID.
- Root control points in chart or barycentric coordinates.
- Height spline coefficients.
- Thickness, draft, root radius, and penetration depth.
- Presence and symmetry-group variables.
- Junction relations to other fins.
- Bounds and provenance for every constraint.
- Hashes of the smooth field and final B-rep realization.

Store both intended and realized measurements. This makes CAD drift visible rather than silently treating the Boolean result as the requested design.

### Optimization loop

1. Validate the uncertainty envelope and solve production over it.
2. Seed one or more legal fin graphs.
3. Build the smooth union field from current parameters.
4. Solve independent load bases and find active worst-case combinations.
5. Evaluate objectives, constraints, and adjoint gradients.
6. Add manufacturing penalties and surface-curve regularization.
7. Update variables with MMA or a trust-region constrained optimizer.
8. Continue presence and projection sharpness gradually.
9. At scheduled checkpoints, generate the B-rep and compute realization gaps.
10. Reject the step or shrink the trust region if CAD feasibility or realization error degrades.
11. Prune weak fins and introduce new fins only at outer-loop boundaries.
12. After topology stabilizes, round discrete decisions and polish continuous geometry.
13. Run final STEP, C3D10, robust envelope, and Code_Aster checks.

Do not invoke OCC in every gradient iteration. CAD checkpoint frequency can start high during development, then reduce once a reliable feasibility model exists.

### Tests that prevent silent loss

- Every requested family or graph operation must report requested, generated, unique, raw-valid, independently fuseable, jointly fuseable, meshable, and solved counts.
- Candidate IDs must be content-addressed or checked globally for uniqueness.
- Junction builders need property-based tests over random angles, heights, and thicknesses.
- Every gradient variable type needs automated finite-difference tests.
- Every constraint needs a deliberately failing fixture.
- Every optimization run must preserve a replayable parameter trace and solver version.
- A nightly test should run production plus a fixed small design set through both screening and C3D10 to detect ranking drift.

## What to retain

The following parts of the current system are valuable and should remain:

- Engineer-approved exact design volumes and keep-outs.
- Frozen functional interfaces and canonical measurement definitions.
- Stored load-component responses and load-case recombination.
- GPU fixed-grid solver, multigrid, adjoints, MMA machinery, and smooth projections.
- CP-SAT manufacturing rules, symmetry handling, and no-good cuts.
- Exact STEP output, face-by-face C3D10 meshing, cuDSS, and Code_Aster cross-checks.
- Stage-wise validation, design records, and explicit failure reporting.
- The agent’s role at the level of intent, envelope selection, experiment planning, and failure explanation—not free-form geometry generation.

The project’s earlier experience already established that direct field meshing must not redefine bearing seats or measurement surfaces, and that CP-SAT and continuous geometry solve different levels of the problem. The rooted-fin route preserves those lessons rather than replacing them.[^12][^52]

## What to stop

Stop or freeze the following until the rooted-fin gates pass:

- Adding more named rib forms to the current floating-plate library.
- Selecting designs for geometric diversity before robust performance.
- Claiming robustness from ±5% magnitude perturbations or an unapproved set of rotated cases.
- Walking optimized plates back to their initial positions after a Boolean failure.
- Treating small-face deletion or large fuzzy tolerances as acceptable automatic healing.
- Reconstructing the main design lane from voxels, SDFs, GET fields, or density contours.
- Building a surrogate on the present 47-feature vector as if it were the final design representation.
- Expanding UI and agent autonomy around a representation that has not passed the one-fin and multi-fin realization tests.

A future surrogate should consume a set or graph of fins—root control points, height coefficients, graph connectivity, symmetry, manufacturing parameters, and load-envelope descriptors—because topology and component count will vary. A fixed flat vector can still be retained for reporting and simple baselines.

## Final recommendation

The documents have reached the right diagnosis, but the plan should be reframed as **surface-attached explicit component optimization**, not merely a new rib primitive. The complete route is:

> Engineer-approved B-rep volumes and interfaces → surface atlas and legal anchor graph → rooted-fin components → smooth fixed-grid projection → continuous worst-case load optimization → CP-SAT topology/manufacturing projection → continuous polish → clean parametric B-rep fins → batch Boolean and CAD gates → C3D10 robust validation.

This route directly addresses all three corners identified in the project: load carrying, castability, and differentiability. It also incorporates the strongest ideas from curved-skeleton MMC, geometry projection, force-flow members, robust topology optimization, and OCCT’s robust Boolean machinery without inheriting their benchmark-only assumptions.[^4][^10][^30][^26][^2][^1]

The most important sequencing change is simple: **prove one rooted fin, then interacting fins, then robust topology variation, and only then generate families at scale**. If the one-fin experiment cannot preserve both physics and CAD, stop and repair the representation. If it passes, the rest of the current platform becomes unusually well positioned: the fast solver, rules engine, exact interface handling, meshing route, and validation records are already the difficult supporting infrastructure that published methods usually omit.

---

## References

1. [design-generation.md](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/148611546/4eace516-f22a-4bcd-8df4-2d56b1f14379/design-generation.md?AWSAccessKeyId=ASIA2F3EMEYEZWAXJX3E&Signature=65B3TFV8UgVvyVVXxh8JgnKh4R0%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEK3%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJHMEUCIQCVoPLsBtkZdqL9yO6oR8J9%2BfVJ1SPPqCeEm%2BmSMDTDowIgSgTZ%2BbkZP1SI2JFbpy%2B8svwjeJtH9QMICnMC%2F%2F6jrQ8q8wQIdRABGgw2OTk3NTMzMDk3MDUiDC7F8tWMPiS%2BZeeCZSrQBALErrt3kSBC7FWsQ4Qv%2FK0vrRyVRml%2BKXQo6pbgBWTTcUd6hV62BvBkK3QcQI830365%2BMEI5ktlMQPVpARfsoZU6XvSW4ZU%2FbUAW64OoOHJTqK4ib22W2uvR%2B1eSSOVLFcEAlNOu34Q0dX8YJgkBnXVKg1XcSJhlPdir6D8bWDZzT6aG0g148N1YnbfkOYhBr64yb%2BI3KlphHKOGyKCIzXDj3tmZUZyAbKMXWNLC4zNK0AUa2pabnLYddcbMCiLBcOmLf7cFAICIcUarzuBJszmNH4f6s%2BAz1%2Bi9VzbgkX9UknOkprNE8orfF3j0I80mA2%2Baw1apEb7vZPKI4RBQfzs2dafr2oVB1iGjHiJ7eP7Vexa4OJzqnXKiZDqOE92xLbeXNqHxNN2qFUkKy16PgYZbwpZEQ3YiwvHlsu4WgIoLu1VJZD91jzaSfb48g%2FBQdAem717kMGlLqOo%2BCvzED2EMETZ%2Fk2HGHUz0sjXql4fPNCsB57bbfCmiFeFG7mEZDcAyz120WLnDOA6g7g%2FHFGUFswlW5qCHfMijiAbx9Y0MEyk4ki6MyAcE0yV7M7go4U6UoZoVp%2FQAIzyyc9BPNEl7A896hHaf28mX6Jyhe9qVh%2Bv4%2FlptR2xEPQzJdpB8P%2BM%2FtzNDIkmBsrlKbUuYx1SHRjmPV3C971JNz%2BTQM7v4LcPa66pXr4cflYC9gGV4Pf4xhYwOVnc12yZ58BuSQOvfuL9YxNSBK%2BWCQx6X2pUL2OTg2KOsO4DQePssyj6uZDku6PWR5BdBSElP%2BkuEtkwtpy%2F1QY6mAGjVTty9AX%2BTgKWHSUG%2Bc91vOOR0y3gu04sFfda85jbqf9QvU9729c0rE7HFoclvtYHk2LYMC7p6fq64Uh9Qcu3UEqNf9ES2c%2BAhoalaabl681Y9ZQX1bMP5Al6Ax7B8cc097Sreo2C3pomSBQqvYdxU09qX7XFttlurK8qlLT7A6OzxOitA7ER7XLHdFcZ3naY1AlZGWjx2g%3D%3D&Expires=1789910025) - In one line. From one housing, its deck and the volumes the engineer keeps, fastcae makes castable r...

2. [CAD-integrated stiffener sizing-topology design via force flow members (FFM)](https://www.sciencedirect.com/science/article/abs/pii/S0045782523003250) - Stiffener design plays a crucial role in the lightweight design of stiffened panels. We propose a CA...

3. [bibtex](https://www.techscience.com/CMES/v135n2/50174/bibtex)

4. [Explicit Topology Optimization Design of Stiffened Plate ...](https://www.techscience.com/CMES/v135n2/50174/html) - This paper proposes an explicit method for topology optimization of stiffened plate structures. The ...

5. [A component-based method for the optimization of stiffener layout on large cylindrical rib-stiffened shell structures - Structural and Multidisciplinary Optimization](https://link.springer.com/article/10.1007/s00158-021-02945-9) - In the present work, an optimization method is proposed in order to produce innovative stiffening la...

6. [rib-families-plan.md](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/148611546/671b13c8-9008-492a-8857-c3b49faf9a19/rib-families-plan.md?AWSAccessKeyId=ASIA2F3EMEYEZWAXJX3E&Signature=k99xBSPAf3tpaOXzT%2BFBh1gDrFk%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEK3%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJHMEUCIQCVoPLsBtkZdqL9yO6oR8J9%2BfVJ1SPPqCeEm%2BmSMDTDowIgSgTZ%2BbkZP1SI2JFbpy%2B8svwjeJtH9QMICnMC%2F%2F6jrQ8q8wQIdRABGgw2OTk3NTMzMDk3MDUiDC7F8tWMPiS%2BZeeCZSrQBALErrt3kSBC7FWsQ4Qv%2FK0vrRyVRml%2BKXQo6pbgBWTTcUd6hV62BvBkK3QcQI830365%2BMEI5ktlMQPVpARfsoZU6XvSW4ZU%2FbUAW64OoOHJTqK4ib22W2uvR%2B1eSSOVLFcEAlNOu34Q0dX8YJgkBnXVKg1XcSJhlPdir6D8bWDZzT6aG0g148N1YnbfkOYhBr64yb%2BI3KlphHKOGyKCIzXDj3tmZUZyAbKMXWNLC4zNK0AUa2pabnLYddcbMCiLBcOmLf7cFAICIcUarzuBJszmNH4f6s%2BAz1%2Bi9VzbgkX9UknOkprNE8orfF3j0I80mA2%2Baw1apEb7vZPKI4RBQfzs2dafr2oVB1iGjHiJ7eP7Vexa4OJzqnXKiZDqOE92xLbeXNqHxNN2qFUkKy16PgYZbwpZEQ3YiwvHlsu4WgIoLu1VJZD91jzaSfb48g%2FBQdAem717kMGlLqOo%2BCvzED2EMETZ%2Fk2HGHUz0sjXql4fPNCsB57bbfCmiFeFG7mEZDcAyz120WLnDOA6g7g%2FHFGUFswlW5qCHfMijiAbx9Y0MEyk4ki6MyAcE0yV7M7go4U6UoZoVp%2FQAIzyyc9BPNEl7A896hHaf28mX6Jyhe9qVh%2Bv4%2FlptR2xEPQzJdpB8P%2BM%2FtzNDIkmBsrlKbUuYx1SHRjmPV3C971JNz%2BTQM7v4LcPa66pXr4cflYC9gGV4Pf4xhYwOVnc12yZ58BuSQOvfuL9YxNSBK%2BWCQx6X2pUL2OTg2KOsO4DQePssyj6uZDku6PWR5BdBSElP%2BkuEtkwtpy%2F1QY6mAGjVTty9AX%2BTgKWHSUG%2Bc91vOOR0y3gu04sFfda85jbqf9QvU9729c0rE7HFoclvtYHk2LYMC7p6fq64Uh9Qcu3UEqNf9ES2c%2BAhoalaabl681Y9ZQX1bMP5Al6Ax7B8cc097Sreo2C3pomSBQqvYdxU09qX7XFttlurK8qlLT7A6OzxOitA7ER7XLHdFcZ3naY1AlZGWjx2g%3D%3D&Expires=1789910025) - Superseded by rib-optimisation-plan.md. The lane below was built and measured what it gave and where...

7. [A component-based method for the optimization of stiffener layout on large cylindrical rib-stiffened shell structures](https://hal.science/hal-03284178v1/file/DMAS20135_AAM.pdf)

8. [Explicit structural topology optimization based on moving morphable components (MMC) with curved skeletons](https://www.sciencedirect.com/science/article/pii/S0045782516307691)

9. [Vers une recherche reproductible en optimisation topologique des aérostructures](https://hal.science/hal-03717745v1/file/CSMA2022.pdf)

10. [GitHub - topggp/blog: Topology Optimization using Generalized Geometric Projection](https://github.com/topggp/blog) - Topology Optimization using Generalized Geometric Projection - topggp/blog

11. [A MATLAB code for topology optimization using the geometry projection method](https://link.springer.com/article/10.1007/s00158-020-02552-0) - ## Abstract

This work introduces a MATLAB code to perform the topology optimization of structures m...

12. [Problem is to then mesh that resulting geometry on implicit field with tet elements where I already tried using CGAl which gives me a mesh which has completely missed the edges and sharp features and have smoothen it… so my analysis happens then in f...

... couplings may not exactly lie on the bearing seat face exactly and that may lead to also consider the displacement of nodes which are not on seats and not we are dependent on how fields get meshed between variants and effect of that in our results …](https://www.perplexity.ai/search/1b4fefa0-3b16-428f-aa34-9acdcce76de7) - Your concern is correct and is decisive for the architecture. For gear-misalignment work, a voxel/SD...

13. [BRepOffsetAPI_MakePipeShell Class Reference](https://dev.opencascade.org/doc/refman/html/class_b_rep_offset_a_p_i___make_pipe_shell.html)

14. [BRepOffsetAPI_MakePipe Class Reference](https://dev.opencascade.org/doc/occt-7.5.0/refman/html/class_b_rep_offset_a_p_i___make_pipe.html) - BRepOffsetAPI_MakePipe Class Reference - documentation, user manuals, examples, Open CASCADE Technol...

15. [ShapeUpgrade_UnifySameDom...](https://old.opencascade.com/doc/occt-7.5.0/refman/html/_shape_upgrade___unify_same_domain_8hxx.html)

16. [Open CASCADE Technology: Modeling Algorithms - OCCT3D](https://occt3d.com/dev/doc/overview/html/occt_user_guides__modeling_algos.html) - Open CASCADE Technology 8.0.1 guide: Modeling Algorithms.

17. [: Scaling Multi-modal CAD Generation using Differentiable ...](https://arxiv.org/html/2603.05607v2)

18. [DTGBrepGen: A Novel B-rep Generative Model through ...](https://arxiv.org/abs/2503.13110) - Boundary representation (B-rep) of geometric models is a fundamental format in Computer-Aided Design...

19. [Chapter 1](http://web.mit.edu/kwillcox/Public/ch01--ch05.pdf)

20. [NURBS-based and parametric-based shape optimization ...](https://www.cad-journal.net/files/vol_15/CAD_15(6)_2018_916-926.pdf)

21. [Optimizing Parameterized CAD Geometries Using ...](https://www.cad-journal.net/files/vol_9/CAD_9(3)_2012_253-268.pdf)

22. [Fuzzy Boolean Operations](https://dev.opencascade.org/content/fuzzy-boolean-operations) - Fuzzy Boolean Operations - solution of problems, Open CASCADE Technology.

23. [Boolean Operations - Open CASCADE Technology](https://dev.opencascade.org/doc/overview/html/specification__boolean_operations.html) - Open CASCADE Technology 8.0.1 guide: Boolean Operations.

24. [Introduction](https://dev.opencascade.org/doc/occt-7.9.0/overview/html/specification__boolean_operations.html)

25. [shape_healing · Open-Cascade-SAS/OCCT Wiki · GitHub](https://github.com/Open-Cascade-SAS/OCCT/wiki/shape_healing) - Open CASCADE Technology (OCCT) is an open-source software development platform for 3D CAD, CAM, CAE....

26. [BOPAlgo_CellsBuilder Class Reference - Open CASCADE ...](https://occt3d.com/dev/doc/refman/html/class_b_o_p_algo___cells_builder.html) - Open CASCADE Technology 8.0.1 API reference: BOPAlgo_CellsBuilder Class Reference.

27. [BOPAlgo_CellsBuilder.hxx File Reference](https://dev.opencascade.org/doc/refman/html/_b_o_p_algo___cells_builder_8hxx.html)

28. [Overview](https://dev.opencascade.org/doc/occt-7.7.0/overview/html/occt_user_guides__shape_healing.html)

29. [Robust topology optimization under loading uncertainty ...](http://www.me.buaa.edu.cn/__local/D/E7/DA/9BF14AE6586EAEAD8D123BAF5AE_D9ECCF0B_1177B5.pdf)

30. [A smooth maximum regularization approach for robust topology optimization in the ground structure setting](https://paulino.princeton.edu/journal_papers/2024/SMO_24_smoothRegularization.pdf)

31. [Topology optimization with continuously varying load magnitude and direction for compliance minimization - Structural and Multidisciplinary Optimization](https://link.springer.com/article/10.1007/s00158-024-03882-z?error=cookies_not_supported&code=57fb345e-fc34-462e-845f-576079ef9b99) - Traditional topology optimization methods only consider a limited number of loads in the optimizatio...

32. [[PDF] Structural topology optimization for multiple load cases using a ...](https://websites.umich.edu/~mdolaboratory/pdf/James2009a.pdf)

33. [Explicit Topology Optimization with Moving Morphable Component (MMC) Introduction Mechanism](https://link.springer.com/article/10.1007/s10338-021-00308-x)

34. [[PDF] Applying extrinsic geometric constraints in the MMC framework](https://pureadmin.qub.ac.uk/ws/portalfiles/portal/642489149/AppWork.pdf)

35. [Combined parameterization of material distribution and surface mesh for stiffener layout optimization of complex surfaces](https://arxiv.org/abs/2201.09983) - Stiffener layout optimization of complex surfaces is fulfilled within the framework of topology opti...

36. [Tracing Geodesic Paths](https://geometry-central.net/surface/algorithms/geodesic_paths/)

37. [CGAL 6.2.1 - Triangulated Surface Mesh Shortest Paths](https://doc.cgal.org/latest/Surface_mesh_shortest_path/index.html)

38. [libigl tutorial](https://libigl.github.io/tutorial/) - Exact Discrete Geodesic Distances¶. The discrete geodesic distance between two points is the length ...

39. [GitHub - nmwsharp/geometry-central: Applied 3D geometry in C++, with a focus on surface meshes.](https://github.com/nmwsharp/geometry-central) - Applied 3D geometry in C++, with a focus on surface meshes. - nmwsharp/geometry-central

40. [GitHub - ThomasRochefortB/MMC188_python: Python implementation of the 188 line Moving Morphable Components topology optimization code.](https://github.com/ThomasRochefortB/MMC188_python) - Python implementation of the 188 line Moving Morphable Components topology optimization code. - Thom...

41. [An efficient and easy-to-extend Matlab code of the Moving](https://arxiv.org/ftp/arxiv/papers/2201/2201.02491.pdf)

42. [moveable-morphable-components](https://pypi.org/project/moveable-morphable-components/0.3.0/) - An implementation of the Moveable Morphable Components algorithm

43. [Geodesic Distance](https://geometry-central.net/surface/algorithms/geodesic_distance/)

44. [◆ Barycentric_coordinate](https://doc.cgal.org/5.6.2/Surface_mesh_shortest_path/classCGAL_1_1Surface__mesh__shortest__path.html)

45. [libigl/include/igl/exact_geodesic.h at main - GitHub](https://github.com/libigl/libigl/blob/main/include/igl/exact_geodesic.h) - ... Exact geodesic algorithm for triangular mesh with the implementation from https://code.google.co...

46. [build123d - Open Source Tools](https://opensourcetools.org/tools/build123d/) - A curated directory of free, open and self-hostable software - each one a credible replacement for t...

47. [Build123d | OCCT Samples & Projects Registry](https://open-cascade-sas.github.io/OCCT-Samples/libraries/modeling/build123d/) - Curated registry of open-source projects built on Open CASCADE Technology.

48. [GitHub - missionlab/fenitop: FEniCSx-based topology optimization supporting parallel computing](https://github.com/missionlab/fenitop) - FEniCSx-based topology optimization supporting parallel computing - missionlab/fenitop

49. [Gaussian Ensemble Topology (GET): A New Explicit and Inherently ...](https://arxiv.org/abs/2510.05572) - Abstract:We introduce the Gaussian Ensemble Topology (GET) method, a new explicit and manufacture-re...

50. [Explicit Reconstruction and Shape Optimization of Topology ...](https://www.sciopen.com/article/10.32604/cmes.2026.079578) - This study proposes a two-stage post-processing framework to reconstruct topology optimization resul...

51. [Automated and Accurate Geometry Extraction and Shape Optimization of 3D Topology Optimization Results](https://arxiv.org/abs/2004.05448) - Designs generated by density-based topology optimization (TO) exhibit jagged and/or smeared boundari...

52. [CP-SAT and GET role combined is not clear](https://www.perplexity.ai/search/f37893b0-d1c6-41dd-9ddd-07b2b86ff533) - They solve two different levels of the same problem:
CP-SAT decides the layout: *Which regions shoul...

