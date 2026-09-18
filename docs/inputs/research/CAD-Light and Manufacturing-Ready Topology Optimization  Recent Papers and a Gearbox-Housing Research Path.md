# CAD-Light and Manufacturing-Ready Topology Optimization
## Executive assessment
The closest research family to 3D MMC and Gaussian Ensemble Topology (GET) is **explicit or geometry-parameterized topology optimization**: the optimization variables describe components, voids, patches, splines, Gaussian fields, or stiffener paths instead of assigning an independent density to every finite element. Feature-mapping methods explicitly combine a high-level geometric description with projection onto a non-body-fitted analysis mesh, giving more geometric control without remeshing at every iteration.[^1][^2]

For a cast gearbox housing, the papers divide into four practically different groups:

1. **Native explicit geometry:** GET, MMC/MMV, Moving Morphable Patches, Generalized Geometry Projection, and B-spline parameterized level-set methods.
2. **CAD-integrated stiffener design:** Force Flow Members, embedded-solid MMC on curved shells, surface-MMC using conformal mapping, and NURBS/IGA stiffener workflows.
3. **Manufacturing-constrained optimization:** casting/demolding, variable-height ribs, self-supporting AM, and filling/solidification-aware optimization.
4. **Automated reconstruction:** medial-axis feature reconstruction, casting-aware medial-axis reconstruction, and SDF/RBF smoothing.

The best immediate direction is **not one method alone**. Use a surface/rib-specific explicit optimizer—preferably Force Flow Members or embedded-solid/surface MMC—as the primary gearbox-housing generator; use GET as a smooth volumetric discovery engine; and add automated medial-axis or SDF extraction only for candidates that cannot already be expressed as editable ribs and webs.
## Priority shortlist
| Priority | Paper/method | Representation | Why CAD work is reduced | Gearbox-housing fit | Main caveat |
|---|---|---|---|---|---|
| 1 | CAD-integrated stiffener sizing-topology via Force Flow Members, 2023 | Explicit force-flow/stiffener members integrated with CAD/IGA | The optimization output already consists of stiffener-like entities rather than a voxel solid[^3] | **Very high** for bearing-to-mount ribs and wall reinforcement | Access and implementation details appear less open than GET/GGP |
| 2 | Extrinsic geometric constraints in MMC, 2025 | MMC components with coincidence, tangency and normal relations | CAD-style constraints are optimized directly; a reported example reduced design variables by 52.5% with a 1.51% performance reduction[^4] | **Very high** for connected ribs, collars, gussets and controlled junctions | Demonstrated example is simpler than a full 3D cast housing |
| 3 | Embedded-solid MMC for complex thin-walled structures, 2023/2024 | Explicit solid MMCs embedded into shell geometry | Handles topology, reinforced-rib layout and sandwich design in a single explicit framework; components follow the underlying curved surface[^5][^6] | **Very high** for curved housing walls | Requires reliable surface parameterization/embedding |
| 4 | GET, 2025 preprint | Superposition of anisotropic Gaussian fields | Produces smooth curvature-continuous boundaries without mesh/corner smoothing or feature extraction[^7] | **High** for discovering volumetric webs, blended collars and organic load paths | Smooth implicit geometry is not automatically editable B-rep or castable geometry |
| 5 | Implicit B-spline self-supporting TO, 2024 | Implicit tensor-product B-spline field | Smooth spline field, fewer variables and boundary-based manufacturing constraints; designed for large 3D cases[^8][^9] | **Medium-high** as a smooth field engine adaptable from overhang to draft/demolding constraints | Manufacturing focus is AM, not casting; still implicit rather than feature CAD |
| 6 | Non-parametric geometry patching for MMC, 2024 | MMC plus moving-node boundary patches | Produces smooth boundaries in both 2D and 3D without a separate manual smoothing stage[^10][^1] | **High** as an MMC refinement layer | Smooth boundary does not by itself produce semantic ribs or native parametric CAD |
| 7 | Medial-axis parametric reconstruction, 2023, plus casting extension | MAT surface skeleton, quad decomposition, T-splines and retained B-rep interfaces | Generates editable CAD from 3D TO and preserves original analytic non-design regions; casting extension adjusts sections using solidification logic[^4] | **High** for converting discovered wall/web topology into CAD | Current reconstruction includes a manual retopology step and noisy/non-manifold skeleton handling |
| 8 | SDF/RBF smooth geometry extraction, 2025 preprint | Signed-distance field plus Gaussian RBF smoothing | Converts arbitrary SIMP results into smooth volume-preserving implicit geometry and releases implementation/code[^11] | **Medium-high** for robust automatic meshing and fallback geometry | It is post-processing, not native CAD; protected interfaces require special treatment |
| 9 | NURBS hyper-surface CAD-compatible TO | NURBS pseudo-density field independent of FE mesh | CAD-compatible topology descriptor, reduced variable count and straightforward boundary reconstruction[^12][^13] | **Medium** for smooth global concepts and surrogate parameters | A scalar NURBS density field is not the same as an editable set of ribs/web features |
| 10 | IGA/ABM/FCM shell shape-topology optimization, 2023 | NURBS shell plus adaptive parametric holes | Shape changes act on NURBS control points while holes are introduced in the surface parameter domain[^14] | **Medium** for windows/cutouts and shell evolution | Less directly suitable for adding production ribs to an existing thick cast housing |
## Most relevant papers
### Applying extrinsic geometric constraints in the MMC framework
**Citation:** *Applying extrinsic geometric constraints in the MMC framework*, Structural and Multidisciplinary Optimization 68, Article 104, published June 2025, DOI `10.1007/s00158-025-04031-w`.[^4]

This is one of the strongest follow-ons to conventional MMC. It introduces CAD-like coincidence, tangency and normal constraints between components, including parent-child propagation, so the optimizer searches among structurally connected and geometrically coherent assemblies rather than arbitrary overlapping bars.[^4]

For the housing, this suggests components such as:

- A rib remains tangent to a bearing collar.
- A web terminates normally at a mounting pad.
- Child gussets follow the movement of their parent rib.
- Symmetric or patterned ribs share parameters.
- Rib junctions remain connected throughout optimization.

This paper directly addresses the concern that unconstrained MMC components can overlap messily and later require interpretation. It should be treated as the **geometric constraint layer** over a 3D or surface-MMC implementation.
### CAD-integrated stiffener design via Force Flow Members
**Citation:** Yu Wang, Lingzhi Jin, Yueyi Zhang, Peng Hao, and Bo Wang, *CAD-integrated stiffener sizing-topology design via force flow members (FFM)*, Computer Methods in Applied Mechanics and Engineering 415 (2023).[^3]

FFM is conceptually closer to the actual gearbox task than general solid TO: the target is a stiffener layout, and the output is represented through force-flow members within a CAD/analysis workflow. Its literature lineage includes curvilinear ribs, shells, IGA, NURBS stiffeners and principal-stress-driven reinforcement.[^3]

The transferable architecture is:

```text
Exact housing midsurface / B-rep wall
        ↓
Candidate bearing–mount force-flow paths
        ↓
Explicit member centerlines + width/height parameters
        ↓
CAD rib/web generation
        ↓
Solid validation of bearing-seat displacement and NVH
```

This should be the **first paper to reproduce or reimplement** for a two-region gearbox pilot, because it naturally generates rib graphs rather than free-form organic solids.
### Embedded solid MMC on curved thin-walled structures
The embedded-solid MMC line proposes explicit components that conform to complex thin-walled surfaces and unifies topology optimization, reinforcement-rib layout, and sandwich-structure design. A related air-rudder application emphasizes that explicit modeling allows results to be imported into CAD systems and is aimed at stiffeners inside irregular enclosed design regions.[^5][^6]

This is particularly relevant because a gearbox housing is largely a curved, thick-walled shell with local solid features. Instead of optimizing the complete casting volume, a midsurface or offset-surface model can host solid rib components whose centerline, width, height, taper and position remain explicit.
### Gaussian Ensemble Topology
GET represents geometry as a sum of anisotropic Gaussians; the mean and covariance of each Gaussian encode location, orientation and length scales, while a thresholded topology-description field defines the solid. It reports inherently smooth, curvature-continuous boundaries, mesh-independent explicit parameterization, and 2D/3D benchmarks with performance comparable to MMC.[^7]

GET is attractive as a **concept-discovery engine** because Gaussian primitives merge smoothly and can form webs and blended branches without the sharp overlap artifacts of simple MMC bars. However, it should not be described as native production CAD: the output is still a level set/implicit boundary, so STEP-quality analytic features, draft, machining allowances and robust rib semantics remain downstream tasks.

A housing-specific extension would split the Gaussian population into typed groups:

- Surface-tangent Gaussians for wall ribs.
- Ring Gaussians around bearing seats.
- Corridor Gaussians between bearing and mount anchors.
- Negative Gaussians or protected fields for keep-outs.
- Frozen analytic fields for bores and mating interfaces.
### Non-parametric geometry patching for MMC
**Citation:** Weisheng Zhang, Shengqi Zhang, Sung-Kie Youn, and Xu Guo, *Non-parametric geometry patching technique for MMC topology optimization*, Structural and Multidisciplinary Optimization 67 (2024), DOI `10.1007/s00158-024-03789-9`.[^10]

The paper combines MMC with a moving-node patching technique to obtain smooth boundaries in 2D and 3D. It is valuable if the selected MMC implementation produces component-intersection artifacts, because it attacks geometric quality without giving up the topology-discovery behavior of MMC.[^10]

For the housing, use patching only on newly created structural regions. Bearing bores, pads and other exact interfaces should remain untouched B-rep entities.
### Generalized Geometry Projection
GGP unifies geometry projection, MMC and moving-node approaches in one feature-based framework. A design is assembled from simple geometric components whose position, size and orientation are optimized, and implementations are publicly available in MATLAB, Julia and Python.[^15][^16]

GGP is an excellent **research scaffold** even though the central paper predates the newest methods. It gives a reproducible way to test new primitives—curved ribs, tapered webs, polygonal voids or Gaussian-like features—on a fixed analysis mesh. The newer polygonal-primitive direction explicitly targets minimum/maximum sizes, overhang, alignment and straight-edged fabrication constraints while retaining feature-mapping's differentiability.[^17]
### Implicit B-spline self-supporting optimization
**Citation:** Nan Zheng, Xiaoya Zhai, Jingchao Jiang, and Falai Chen, *Topology Optimization of Self-supporting Structures for Additive Manufacturing via Implicit B-spline Representations*, Computer-Aided Design 175 (2024), Article 103745, DOI `10.1016/j.cad.2024.103745`.[^8][^18]

The method represents geometry using implicit tensor-product B-splines and analytically derives self-supporting constraints on boundary points. It uses super-elements, multigrid and GPU programming for large 3D problems, and reports a substantial reduction in constraint-evaluation effort relative to prior B-spline methods.[^8]

Its overhang constraint is not directly useful for a cast housing, but its **representation and boundary-differentiation strategy** are. The same boundary normals and gradients can support:

- Positive draft constraints relative to a draw direction.
- No-undercut constraints.
- Minimum wall/rib thickness constraints.
- Controlled curvature and fillet-radius proxies.
- Parting-plane-aware topology restrictions.
### NURBS hyper-surface topology optimization
The NURBS hyper-surface family separates topology description from the FE mesh. A NURBS entity represents the pseudo-density field; this reduces design variables, provides implicit spatial regularization, and makes reconstruction easier because the topology descriptor is CAD-compatible. Recent work extends the same family to anisotropic strength-based TO in a CAD-compatible framework.[^19][^12][^13][^20]

This is a good representation for a **global smooth family generator** and for surrogate learning because the control-point parameters form a compact, continuous design vector. It is less suitable as the only product representation because thresholding a scalar spline field still yields an implicit solid rather than a semantically editable rib network.
### Isogeometric stiffened-structure workflows
The multilevel NURBS free-form-deformation workflow jointly optimizes stiffener arrangement and shell shape in an integrated design-analysis-optimization process. Another IGA/Adaptive Bubble/Finite Cell approach directly optimizes NURBS shell control points and introduces holes in the parametric surface, giving exact shell-surface geometry while allowing topology changes.[^3][^14]

These methods are valuable where the housing can be idealized as a midsurface and where the desired changes are panel shape, windows, rib paths and local shell reinforcement. They avoid repeated CAD-to-analysis translation, but final thick-solid generation and intersection with bearing collars still require a deterministic materialization step.
## Manufacturing-focused papers
### Casting-aware medial-axis reconstruction
*Reconstruction of Topology Optimized Geometry with Casting Constraints in a Feature-Based Approach* extends medial-axis reconstruction by using maximally inscribed-sphere cross sections and Heuvers-circle-inspired adaptation to encourage directed solidification toward a predefined feeder; it generates CAD models and structurally evaluates them.[^4]

This is unusually relevant to cast gearbox housings because it recognizes that geometric drawability alone is insufficient. It offers a way to adjust rib/web thickness progression after load-path discovery so the reconstructed geometry has a more plausible solidification path.
### Structural TO with filling constraints
A 2024 mega-casting study couples stiffness optimization to an OpenFOAM-based turbulent filling model and adjoint sensitivities rather than using only geometric casting constraints. This is not a minimal-CAD representation, but it is important as a **late qualification or co-optimization stage**: a smooth, drafted topology may still fill badly or create trapped flow regions.[^21]
### Variable-height casting stiffeners
*Variable-height stiffener design using topology optimization with anisotropic filter-based casting constraints* introduces a Helmholtz-type anisotropic filter for casting-constrained stiffener height design. This is directly relevant to housing walls because it searches a height field for ribs normal to a base panel, yielding geometry much closer to cast wall reinforcement than unconstrained 3D SIMP.[^22]
### Mega-casting multidisciplinary workflow
A 2023 automotive mega-casting workflow first derives load paths through topology/free-size optimization with casting constraints and many linearized loads, then optimizes thickness and rib orientation using response-surface methods with nonlinear crash and casting simulations. The main lesson is architectural: **separate family/load-path discovery from detailed rib sizing and casting qualification**, rather than forcing one expensive optimizer to solve every level simultaneously.[^23]
### Print-ready TO
A 2025 Modified AVD algorithm combines density TO, quasi-binary Heaviside filtering and Langelaar's overhang filter to improve convergence toward support-free, interpretable designs, but the paper validates only 2D examples and still outputs a density field rather than native CAD. It is relevant for continuation strategies and robust binarization, not as the primary gearbox representation.[^4]
## Automated conversion papers
### Parametric medial-axis reconstruction
Mayer and Wartzack's 2023 method takes a faceted 3D TO result, computes a Voronoi medial-axis surface, transforms it into a decomposition structure, maps local thickness information, retains analytic B-rep non-design regions, and generates editable CAD through quad/T-spline reconstruction, DOI `10.14733/cadaps.2023.960-975`. It demonstrates cantilever, GE bracket, nacelle hinge, Alcoa bracket and surface-like truck examples.

This is currently one of the closest papers to **automatic TO-to-editable-CAD**. Its important limitation is that general surface-skeleton retopology is still manual and the raw medial axis can be noisy, self-intersecting and non-manifold. Therefore it is better used on a small set of family representatives than on every dataset member.
### Smooth SDF extraction
A 2025 preprint converts arbitrary SIMP fields to an SDF on a regular grid, smooths it with Gaussian RBFs, applies a volume-preserving level-set shift and creates a surface or tetrahedral discretization; implementation and test cases are available in the `rho2sdf.jl` repository.[^11]

This is a strong **automatic meshing path** and a fallback when GET/MMC output is already implicit. It does not solve semantic CAD reconstruction, and global smoothing can disturb load/application interfaces, so the method should operate only on the mutable reinforcement field while the exact functional CAD core is unioned afterward.
### Sequential SIMP-to-level-set refinement
A 2026 preprint transfers a 3D SIMP result into an SDF and then uses it to initialize level-set shape refinement, describing the second stage as optimization-driven post-processing rather than purely geometric smoothing. This is promising for improving boundary quality while preserving structural performance, but is newer and less validated than direct MMC/GET approaches.[^24]
## Ranking by actual CAD burden
| Method class | Output after optimization | Expected downstream work | Recommended role |
|---|---|---|---|
| Force Flow Members / constrained MMC ribs | Centerlines/components with section parameters | Generate sweeps, drafts, fillets and Boolean unions | **Primary production-family generator** |
| Embedded/surface MMC | Explicit ribs/webs following a curved surface | Section regularization, junction blending, B-rep materialization | **Primary or co-primary generator** |
| GET | Smooth implicit field | Isosurface/SDF extraction, semantic decomposition if editable CAD is required | **Concept-discovery generator** |
| B-spline/PLSM/NURBS density | Smooth compact implicit field | Threshold boundary, convert to solid or mesh, protect interfaces | **Alternative discovery/surrogate representation** |
| Shell topography/variable-height ribs | Surface or height field | Convert ridges to explicit rib curves/sections | **Very practical wall-reinforcement generator** |
| Classical SIMP + SDF/RBF | Smooth implicit result | Interface repair, semantic reconstruction, casting checks | **Fallback/baseline** |
| SIMP + medial-axis feature reconstruction | Editable reconstructed CAD | Retopology review, feature cleanup, junction engineering | **Family promotion tool, not bulk generation** |
## Recommended gearbox implementation
### Track A: production-ready rib families
Start with a B-rep or shell representation of the exterior housing wall and immutable analytic anchors. Implement a restricted 3D/surface MMC or FFM vocabulary:

```text
Bearing collar component
Surface rib component
Bearing-to-mount web component
Junction/gusset component
Circumferential ring component
Relief-window void component
```

Each component should expose centerline control points, surface coordinates, height, base width, top width, draft, taper and root radius. CAD-style coincidence, tangency and normal constraints from the 2025 MMC paper should maintain valid interfaces during optimization.[^4]
### Track B: unrestricted family discovery
Run GET within selected volumetric corridors around one wall panel and one bearing-to-mount region. Freeze the functional B-rep core and encode its keep-outs as fixed negative or non-design fields. Cluster results by connectivity and load-path topology rather than surface appearance.

When GET discovers a recurring useful mechanism, promote it into Track A by fitting:

- A rib graph to thin branches.
- A midsurface plus thickness to sheet/web regions.
- A collar primitive to bearing-adjacent material.
- A tapered solid feature to thick junctions.
### Track C: reconstruction fallback
For designs that resist explicit fitting, use SDF/RBF smoothing for analysis-ready geometry and medial-axis/T-spline reconstruction only for the best family representatives. Do not reconstruct every candidate into detailed CAD before the surrogate and low-fidelity FEA have screened it.
### Casting qualification
Use a staged manufacturing filter:

1. During optimization: minimum/maximum feature size, draw direction, no trapped voids, permissible component intersections.
2. During CAD materialization: exact draft, root fillets, wall-rib ratios, machining stock and core access.
3. For Pareto finalists: filling and solidification simulation, feeder-aware thickness progression and hot-spot evaluation.

The casting-aware reconstruction and filling-constrained mega-casting papers show why demolding constraints alone cannot establish production readiness.[^4][^21]
## Reproduction order
1. **GGP codebase:** use the available Python/Julia/MATLAB implementations to validate the component-projection and fixed-grid analysis pipeline.[^15][^16]
2. **Extrinsic MMC constraints:** reproduce parent-child, tangency and normal constraints before attacking the complete housing.[^4]
3. **Surface/embedded MMC or FFM:** implement one flexible panel and one bearing-to-mount corridor.[^3][^5]
4. **GET:** reproduce 3D benchmarks, then replace generic Gaussians with surface-tangent and anchor-aware populations.[^7]
5. **SDF fallback:** integrate `rho2sdf.jl`-style smoothing and direct volume meshing for implicit concepts.[^11]
6. **Casting layer:** add draw/size constraints first, feeder-aware thickness progression second, and flow/solidification only for finalists.[^21][^4]
## Paper-search map
The following keyword families will uncover more work adjacent to MMC and GET:

- `feature-mapping topology optimization`
- `explicit geometric topology optimization`
- `moving morphable patch 3D`
- `moving morphable void B-spline`
- `force flow member stiffener optimization`
- `embedded solid MMC thin-walled structures`
- `surface topology optimization conformal mapping MMC`
- `parameterized level set B-spline topology optimization`
- `NURBS hyper-surface CAD-compatible topology optimization`
- `medial axis topology optimization CAD reconstruction`
- `casting-aware topology reconstruction directed solidification`
- `implicit B-spline manufacturing constrained topology optimization`
## Final decision
For the stated objective—many production-plausible gearbox-housing families with minimal CAD remodeling—the best central research line is **constrained surface/solid MMC or Force Flow Members**, not generic full-volume SIMP and not a generative CAD model. GET should run beside it as the broader, smoother topology-discovery mechanism. The conversion strategy should be asymmetric: production-family candidates remain explicit from the beginning; only genuinely novel GET/TO discoveries are reconstructed into the explicit rib grammar.

This architecture minimizes CAD work while retaining the possibility of discovering structures outside the initial rib library. It also creates clean surrogate inputs: family graph, component geometry parameters, load descriptors and protected-interface descriptors, instead of unstructured CAD or millions of mesh coordinates.

---

## References

1. [A review on feature-mapping methods for structural optimization](https://dl.acm.org/doi/abs/10.1007/s00158-020-02649-6) - In this review we identify a new category of methods for implementing and solving structural optimiz...

2. [A review on feature-mapping methods for structural optimization](https://link.springer.com/article/10.1007/s00158-020-02649-6) - In this review we identify a new category of methods for implementing and solving structural optimiz...

3. [An isogeometric design-analysis-optimization workflow of stiffened ...](https://www.sciencedirect.com/science/article/abs/pii/S0045782523000592) - In this paper, a new design-analysis-optimization workflow is proposed based on isogeometric paradig...

4. [RECONSTRUCTION OF TOPOLOGY OPTIMIZED GEOMETRY ...](https://www.cambridge.org/core/journals/proceedings-of-the-design-society/article/reconstruction-of-topology-optimized-geometry-with-casting-constraints-in-a-featurebased-approach/24CABC0E601D57145D8FCF896B4FCB67) - RECONSTRUCTION OF TOPOLOGY OPTIMIZED GEOMETRY WITH CASTING CONSTRAINTS IN A FEATURE-BASED APPROACH -...

5. [A novel explicit design method for complex thin - walled structures base d on embedded solid moving morphable component s](https://arxiv.org/ftp/arxiv/papers/2306/2306.10449.pdf)

6. [英文版样板](http://arxiv.org/pdf/2401.08995.pdf)

7. [Gaussian Ensemble Topology (GET): A New Explicit and ...](https://arxiv.org/html/2510.05572v1)

8. [Topology Optimization of Self-supporting Structures for ...](https://www.sciencedirect.com/science/article/abs/pii/S0010448524000721)

9. [Topology Optimization of Self-supporting Structures for ...](https://openreview.net/forum?id=myO0uPJO0O) - Highlights•Analytical conditions for non-self-supporting constraints are derived based on the implic...

10. [Non-parametric geometry patching technique for MMC topology ...](https://link.springer.com/article/10.1007/s00158-024-03789-9) - A moving node patching technique for both 2D and 3D cases is developed in conjunction with MMC to ob...

11. [Smooth geometry extraction from SIMP topology optimization: Signed distance function approach with volume preservation](https://web3.arxiv.org/abs/2512.06976) - This paper presents a novel post-processing methodology for extracting high-quality geometries from ...

12. [Une méthode d'optimisation topologique multi-échelle CAO-compatible](https://pastel.hal.science/tel-03741356/file/106078_BERTOLINO_2022_archivage.pdf)

13. [Eigen-frequencies and harmonic responses in topology optimisation: A CAD-compatible algorithm](https://hal.inrae.fr/hal-03166964v1/file/S0141029619342105.pdf)

14. [An integrated design approach for simultaneous shape and topology optimization of shell structures](https://www.sciencedirect.com/science/article/pii/S0045782523003420) - In this work, a novel design approach is developed to carry out shape and topology optimization of s...

15. [GitHub - topggp/blog: Topology Optimization using Generalized Geometric Projection](https://github.com/topggp/blog) - Topology Optimization using Generalized Geometric Projection - topggp/blog

16. [GitHub - topggp/GGP-Matlab: GGP Matlab code](https://github.com/topggp/GGP-Matlab) - GGP Matlab code. Contribute to topggp/GGP-Matlab development by creating an account on GitHub.

17. [Large Scale Structural Systems and Optimal Design](https://www.usacm.org/site_page.cfm?pk_association_webpage_menu=11354&pk_association_webpage=25779)

18. [Topology optimization of elastic contact problems using B-spline ...](https://ouci.dntb.gov.ua/en/works/7WaMEMPl/)

19. [Strength-based topology optimisation of anisotropic continua in a CAD-compatible framework](https://www.sciencedirect.com/science/article/abs/pii/S0965997823001825)

20. [A topology optimization method based on non-uniform rational basis spline hyper-surfaces for heat conduction problems](https://hal.inrae.fr/hal-03307581/file/2021_Montemurro_symmetry.pdf)

21. [Topology Optimization of Mega-Casting Thin-Walled Structures of ...](https://www.techscience.com/icces/v29n3/58282) - Mega-casting techniques are widely used to manufacture large piece of thin-walled structures for veh...

22. [Variable-height stiffener design using topology optimization with ...](https://link.springer.com/article/10.1007/s00158-022-03428-1) - In this paper, a novel implementation of the casting constraint in topology optimization is proposed...

23. [Multidisciplinary optimization of automotive mega-castings ...](https://pmc.ncbi.nlm.nih.gov/articles/PMC10709356/) - Large high pressure die castings (HPDC), recently referred to as mega-castings, can replace plenty o...

24. [Sequential topology optimization: SIMP initialization for level-set ...](https://arxiv.org/html/2605.04735v1)

