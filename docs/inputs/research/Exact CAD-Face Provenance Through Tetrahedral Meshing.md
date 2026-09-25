# Exact CAD-Face Provenance Through Tetrahedral Meshing

## Direct answer

The problem is not primarily “how to improve nearest-neighbour relabelling.” It is **how to prevent CAD-face identity from being destroyed between the Gmsh surface mesh and the tetrahedral mesh**. The current surface-remesh → fTetWild route is geometrically good and robust, but fTetWild produces a boundary approximation inside an envelope rather than a boundary that is guaranteed to retain the original surface connectivity; therefore, the current projection is recovery, not provenance.[^1][^2][^3]

For this rear-housing baseline, implement two meshing lanes:

1. **Production lane: labeled Gmsh surface → TetGen PLC with facet markers → exact labeled boundary → TET10 → MED/Code_Aster.** This is the shortest route to exact CAD-face correspondence because TetGen natively accepts one integer marker per PLC facet and returns boundary triangles with inherited markers.[^4][^5][^6][^7]
2. **Robust fallback: current Gmsh surface → fTetWild → exact closest-point projection plus ambiguity checks.** Keep this for CAD variants that TetGen rejects, but explicitly mark its labels as inferred and reject ambiguous BC triangles rather than silently accepting them.

Do **not** make full B-rep repair the first dependency. The attached investigation already established that the CAD solid has valid volume and a watertight triangulation, while Gmsh’s B-rep route fails on a handful of periodic/seam face parametrizations. The exact-preservation experiment should therefore consume the already watertight, face-labeled surface triangulation as a discrete PLC instead of asking Gmsh to mesh the problematic STEP faces again.[^8]

## Problem definition

The required invariant is:

> Every boundary triangle in the final volume mesh has a deterministic, auditable owner: the original CAD face, a semantic engineering region, or an explicitly generated repair patch.

The current chain is:

`CAD face → Gmsh surface triangle (exact) → fTetWild boundary triangle (new) → projected CAD face (inferred)`

The desired chain is:

`CAD face → labeled PLC facet → volume-mesh boundary triangle with inherited marker → semantic group`

This distinction matters because the deck applies RBE3 bearing-seat couplings and bolt constraints to named boundary groups. A geometrically close triangle assigned to a neighbouring chamfer can still make the FEA model physically wrong. The attached run quantified this weakness: centroid matching and true closest-point projection disagreed on 2,765 of 67,556 boundary triangles, or 4.09%, before the projection fix.[^8]

## Recommended architecture

### Canonical data model

Create a `SurfacePLC` object and make it the hand-off contract between CAD processing and every volume mesher:

```python
@dataclass
class SurfacePLC:
    xyz: np.ndarray                 # (N, 3)
    tri: np.ndarray                 # (M, 3)
    cad_face_id: np.ndarray         # (M,)
    semantic_region_id: np.ndarray  # (M,), 0 means no BC region
    source_kind: np.ndarray         # gmsh_cad | occt_patch | repair
    source_local_id: np.ndarray     # original triangle or patch ID
```

Also persist a marker table:

```text
marker_id, cad_face_id, semantic_name, source_kind, confidence
```

Use **CAD face ID as the low-level marker** during tetrahedralization. Derive engineering groups such as `carrier_adaptor_seat` or `ring_flange_bolt_07` by joining against the signed-off face map. Do not encode only the engineering group: preserving the lower-level face identity makes later debugging and regrouping possible.

### Primary route

```text
STEP
  ↓ OCCT import + validation
CAD faces
  ↓ Gmsh 2D mesh per CAD face
Watertight triangles + cad_face_id
  ↓ weld only geometrically coincident seam nodes
Labeled PLC
  ↓ TetGen -p with facet markers
Linear tetrahedra + exact boundary markers
  ↓ controlled TET4→TET10 elevation
TET10 + TRI6 boundary groups
  ↓ MED writer
Code_Aster deck
```

TetGen is designed around a piecewise-linear complex (PLC). It supports facet markers specifically to identify which final boundary faces correspond to which PLC facets and boundary-condition type. With `-Y`, TetGen preserves the input exterior boundary mesh; the important trade-off is that boundary resolution and surface quality must already be acceptable because boundary refinement is suppressed.[^9][^10][^5][^6][^11][^4]

### Fallback route

```text
Labeled surface
  ↓ fTetWild
Robust tetrahedra + reconstructed boundary
  ↓ exact point-to-triangle projection
candidate CAD face IDs
  ↓ border-distance, normal and multi-sample checks
accepted labels / ambiguous quarantine
```

fTetWild is intentionally robust to triangle soups, self-intersections and small gaps by permitting tracked faces to move within a user-selected envelope. That is why it succeeds on this model, but it is also why it should remain a robustness fallback rather than the canonical exact-provenance path.[^2][^1]

## Repositories and libraries

| Priority | Repository/library | Role in this solution | Decision |
|---|---|---|---|
| 1 | [TetGen/TetGen](https://github.com/TetGen/TetGen) | Constrained tetrahedralization of the labeled PLC; native `facetmarkerlist`, `trifacelist`, and `trifacemarkerlist` provide exact boundary provenance.[^7][^12] | Prototype first |
| 1 | [tataratat/tetgenpy](https://github.com/tataratat/tetgenpy) | Python wrapper that explicitly demonstrates `facet_markers` input and `trifacemarkers()` output.[^13] | Best rapid prototype wrapper |
| 1 | [libigl Python TetGen bindings](https://libigl.github.io/libigl-python-bindings/api/igl_copyleft_tetgen/) | Alternative binding exposing face markers and output surface triangles; useful for a second implementation check.[^14] | Backup wrapper |
| 1 | [Gmsh](https://gitlab.onelab.info/gmsh/gmsh) | Generate the target-size surface mesh per CAD face and retain the original CAD classification through that stage; Physical Groups are named collections of model entities.[^15][^16] | Keep current surface stage |
| 1 | [Open CASCADE / OCCT](https://github.com/Open-Cascade-SAS/OCCT) | Import STEP, inspect faces, triangulate only failed Gmsh faces, validate geometry, and perform tightly scoped healing. `ShapeFix_Face`, `ShapeFix_Shell`, and `ShapeFix_Shape` target wire, orientation, seam, shell and whole-shape defects.[^17][^18] | Keep as CAD authority |
| 1 | [meshio](https://github.com/nschloe/meshio) | Mesh-format conversion and inspection; supports MED/Salome files.[^19] | Use for verification/conversion, not provenance logic |
| 2 | [wildmeshing/fTetWild](https://github.com/wildmeshing/fTetWild) | Robust fallback tetrahedralizer for imperfect surfaces.[^20][^21] | Keep fallback |
| 2 | [pyvista/pytetwild](https://github.com/pyvista/pytetwild) | Existing Python-accessible fTetWild route; MPL-2.0.[^22][^23] | Keep current integration |
| 2 | [libigl](https://github.com/libigl/libigl) / `igl.AABB` | Exact closest-point-on-triangle query for fallback label recovery; use barycentric closest points instead of centroid-to-centroid KD trees. | Fallback relabelling |
| 2 | [trimesh](https://github.com/mikedh/trimesh) | Practical closest-point and surface validation utilities; already used successfully in the attached experiment. | Fallback and QA |
| 2 | [SalomePlatform/smesh](https://github.com/SalomePlatform/smesh) | Reference implementation for geometry-to-mesh groups and MED export; SMESH can create mesh groups directly on geometric groups.[^24][^25][^26] | Study and use as independent oracle |
| 3 | [MmgTools/mmg](https://github.com/MmgTools/mmg) / mmgpy | Optional labeled surface adaptation; Mmg references are intended to preserve interfaces between regions during remeshing.[^27][^28] | Later, if surface sizing needs improvement |
| 3 | [CadQuery/assembly-mesh-plugin](https://github.com/CadQuery/assembly-mesh-plugin) | Small, readable example of converting tagged CAD faces into Gmsh physical groups.[^29][^30] | Mine mapping patterns |

### Licensing warning

TetGen 1.5+ is AGPLv3 with a commercial-license option from WIAS; its repository explicitly describes the dual licensing model. This is acceptable for an internal technical prototype, but fastcad is intended as a commercial product, so legal review or a commercial TetGen licence is required before embedding or offering it as a network service. Gmsh is GPLv2-or-later with a linking exception, but its site states that closed-source integration or distribution can require a commercial licence; review the exact deployment architecture rather than assuming subprocess use resolves every obligation. By contrast, fTetWild and `pytetwild` are MPL-2.0.[^12][^31][^32][^22][^33]

## Step-by-step implementation

### Phase 0: Freeze evidence

1. Freeze the current good fTetWild result, the source surface, its per-triangle CAD face IDs, the six seat matches, 25 bolt matches, and the projection-based labels.
2. Give every artifact a content hash and write a `mesh_run.json` containing code revision, Gmsh version, mesher version, options, tolerances and timing.
3. Define the acceptance table before changing code:

| Gate | Required result |
|---|---|
| Input topology | One closed oriented surface; zero non-manifold edges; zero unmatched seams after welding |
| Provenance | 100% final boundary triangles have non-zero inherited markers in the exact lane |
| Connectivity | Every final boundary TRI3 is a face of exactly one TET4 |
| Semantic regions | Six seats and 25 bolt regions found; no ambiguous triangle in any driven region |
| Geometry | Seat-specific radial/normal error within the signed mesh tolerance; global surface distance reported by percentile and maximum |
| Quality | Positive tetra volume; no zero/negative Jacobian after TET10 elevation; quality no worse than an agreed threshold |
| Physics | Code_Aster solve completes; displacement, stress percentile and six seat responses compared with the 0.418 mm / 55.1 MPa reference using documented tolerances |

### Phase 1: Build the PLC

4. In the existing Gmsh surface-mesh loop, collect triangles **inside each CAD-face iteration**. Assign the CAD face’s stable internal ID to each triangle immediately; never reconstruct this association from triangle centroids later.
5. Append the OCCT triangles used for the few faces Gmsh cannot parameterize. Assign the same CAD face ID and `source_kind="occt_patch"`. These are not anonymous gap caps; each triangle remains tied to a real CAD face.
6. Weld seam vertices with a spatial hash and a deliberately small tolerance derived from the CAD edge tolerance. Do not run a generic mesh-repair package that can cap large loops or flatten holes.
7. Run topology checks after welding:
   - every undirected edge has exactly two incident triangles;
   - adjacent triangle orientation is coherent;
   - signed enclosed volume has the expected sign and agrees with OCCT volume within the meshing tolerance;
   - no duplicate or near-zero-area triangle remains;
   - marker discontinuities occur only where CAD face IDs change.
8. Export three debugging files: `surface_plc.npz`, `surface_plc.vtp` with `cad_face_id`, and `surface_plc.smesh` or `.poly` with facet markers.

### Phase 2: TetGen spike

9. Start with `tetgenpy` because it explicitly exposes facet-marker input and final triangle-marker output. Construct one PLC facet per input triangle for the first spike; after correctness is proven, group coplanar triangles only if memory or preprocessing time requires it.[^13]
10. Run a parameter matrix rather than choosing one switch string blindly:

```text
A: pYQ                 exact boundary, no quality constraint
B: pYq1.2Q             exact boundary + modest radius-edge quality
C: pYq1.2a<Vmax>Q      exact boundary + interior maximum volume
D: pYYq1.2a<Vmax>Q     stricter suppression on all boundaries, diagnostic only
```

11. For every run, retrieve:
   - output nodes and TET4 connectivity;
   - output boundary triangles;
   - output triangle markers;
   - neighbour/adjacency data if exposed;
   - log and failure reason.
12. Prove exactness mechanically, not visually:
   - sort each boundary triangle’s node triplet;
   - verify it belongs to the output tet-face set;
   - verify its marker is the original PLC marker;
   - under `-Y`, verify expected input boundary triangles survive unchanged;
   - produce a marker-wise area comparison between input and output.
13. Reject the route if any driven region loses a facet, marker or orientation, even if the rendered mesh looks correct.

### Phase 3: Surface-resolution strategy

14. The attached work showed the key TetGen trade-off: exact preservation couples the final boundary resolution to the input tessellation. Therefore, generate the Gmsh surface at an **FE-appropriate local size**, not drawing tessellation accuracy.
15. Use Gmsh mesh fields for:
   - tighter sizing on six bearing seats, bolt bores, shoulders, counterbores and load-transfer blends;
   - moderate sizing on flange and major ribs;
   - coarse sizing on large low-curvature, non-driven exterior walls;
   - smooth gradation between zones.
16. Evaluate three surface-size maps. The winner is the smallest model that clears seat geometry, tet quality and reference-solve gates. Do not optimize element count before exact labels and reference physics pass.

### Phase 4: TET10 conversion

17. Elevate TET4 to TET10 with a global edge table so each unique tet edge receives exactly one shared midpoint node.
18. Build TRI6 boundary faces from the same global edge table; never independently create boundary midside nodes.
19. Decide geometry treatment explicitly:
   - **Like-for-like baseline first:** keep midside nodes at straight-edge midpoints if that matches the existing reference methodology.
   - **Curved boundary later:** project boundary midside nodes back to their owning CAD face, but then run Jacobian checks and a mesh-noise study because this changes stiffness and stresses.
20. Run element-ordering tests against Code_Aster’s TETRA10 and TRIA6 conventions using a one-tet analytical fixture before converting the full housing.

### Phase 5: MED and Code_Aster

21. Write one face group per signed-off semantic region from the final boundary markers, plus diagnostic groups per CAD face where useful.
22. Preserve the existing six seat couplings, 25 bolt ties, reference nodes, material, loads, solver settings and requested outputs exactly. The attached plan states that the deck itself already carries the six load vectors, 25 bolt ties and six RBE3 couplings, so no load re-derivation is needed at this stage.[^8]
23. Validate the MED independently:
   - reopen it with the Code_Aster/SALOME stack;
   - list all group names and counts;
   - verify every group node belongs to the intended final boundary faces;
   - verify no boundary face belongs to two incompatible semantic groups.
24. Run Code_Aster, then compare displacement maximum, p99.9 von Mises, each seat reference-node motion, seat tilt and gear-mesh lead metric against the gate study.

### Phase 6: fTetWild fallback hardening

25. Replace centroid-nearest-centroid assignment everywhere with exact closest-point-on-source-triangle projection using libigl AABB or trimesh proximity.
26. Label with multiple samples per output boundary triangle: centroid and three inward-offset barycentric points. Accept only when all samples agree on the same CAD face or semantic region.
27. Add border awareness. For each projected point, calculate distance to the source triangle’s CAD-face boundary. If the distance is below a threshold tied to local edge length and two candidate faces are plausible, mark the triangle `AMBIGUOUS`.
28. Add normal consistency and distance gates. A label must satisfy closest distance, normal angle and region-cylinder evidence where applicable.
29. Resolve ambiguous triangles by constrained region growing only from high-confidence seeds, never by unconstrained nearest-neighbour copying. Region growth may not cross a preserved CAD-face boundary curve.
30. Enforce a stronger rule for driven regions: **zero ambiguous seat or bolt triangles**. Ambiguity on a remote cosmetic face may be reported and tolerated; ambiguity in a constrained or loaded group fails the mesh.

### Phase 7: Optional Gmsh discrete lane

31. Run a second research spike using the already watertight surface mesh as a Gmsh discrete model. Gmsh supports creating topology from an imported mesh and building a volume from a closed set of discrete surfaces.[^34][^35][^36]
32. Preserve one discrete surface entity per CAD face where feasible, create a surface loop and volume, and call `mesh.generate(3)`. Gmsh’s official examples show `classifySurfaces`, `createGeometry`, a surface loop and 3D meshing for imported surface meshes.[^37][^38]
33. This lane is worth testing because it could avoid TetGen’s licence issue and retain native Gmsh physical groups. However, make it secondary to the TetGen spike: discrete-surface parametrization and boundary recovery can still fail on complex imported meshes, as reflected in Gmsh issue reports.[^39]

### Phase 8: Repair only if needed

34. If both exact lanes fail on the watertight PLC, isolate the smallest offending patch; do not globally heal the full 2,500-face part.
35. Apply OCCT healing in a controlled ladder:
   - analyze validity and free bounds;
   - `ShapeFix_Face` for p-curves, wire orientation and missing seams;
   - `ShapeFix_Shell` for coherent shell orientation;
   - `ShapeUpgrade_ShapeDivideClosed` for problematic closed periodic faces;
   - replace the old face in the parent with `ShapeBuild_ReShape`;
   - sew and revalidate the solid.
36. OCCT’s shape-healing documentation explicitly recommends whole-shape `ShapeFix_Shape` for common defects and sub-shape tools plus a reshape context when only one face must be repaired. Use that as the repair framework, but accept a repair only if volume, unaffected-face signatures and all protected interfaces remain within the predeclared limits.[^17]

## Test suite

### Unit tests

- `test_face_ids_survive_surface_export`
- `test_weld_preserves_marker_boundaries`
- `test_plc_is_closed_oriented_manifold`
- `test_tetgen_marker_roundtrip_cube`
- `test_tetgen_marker_roundtrip_cylinder_chamfer`
- `test_boundary_faces_are_tet_faces`
- `test_tet4_to_tet10_shared_midnodes`
- `test_tria6_uses_tet10_midnodes`
- `test_codeaster_element_order_one_tet`
- `test_projection_marks_border_case_ambiguous`

### Real-input regression tests

- all six driven seats resolve to their expected CAD cylinders;
- all 25 bolt holes resolve through their deck reference points;
- each driven group contains boundary faces and no interior face;
- exact lane has 100% inherited markers and zero inferred markers;
- fallback lane reports inferred-label counts and zero ambiguity in driven groups;
- no stale background run can overwrite another mesh: output paths include run ID and mesher lane;
- rerunning with the same versions and options gives the same group counts and stable global metrics.

### Fault injection

Deliberately plant and confirm detection of:

- one flipped surface triangle;
- one missing seam triangle;
- two duplicate triangles;
- one face-marker shift;
- a boundary triangle crossing a seat/chamfer border;
- one TET10 midside node not shared;
- one semantic group attached to the wrong CAD face;
- an output file overwritten by a second lane.

## Decision tree

```text
Is the labeled surface a closed oriented manifold after seam welding?
├─ No → local OCCT face repair or regenerate only the failed patch
└─ Yes
   ├─ TetGen PLC succeeds and exact-marker gates pass
   │  └─ Use TetGen lane for baseline and variants
   ├─ TetGen fails, Gmsh discrete succeeds and group gates pass
   │  └─ Use Gmsh discrete lane
   └─ Both exact lanes fail
      ├─ driven regions unambiguous under fTetWild projection
      │  └─ use fallback, explicitly tagged as inferred
      └─ driven-region ambiguity remains
         └─ reject mesh; repair/local-refine and rerun
```

## Concrete work order

### First 2 days

1. Extract `SurfacePLC` from the current 98,899-triangle Gmsh/OCCT surface.
2. Add seam welding and manifold/orientation tests.
3. Write `.smesh`/`.poly` with one CAD-face marker per triangle.
4. Run `tetgenpy` on a small marked fixture, then on the housing.
5. Produce a CSV: input marker, input triangle count, output triangle count, input area, output area, status.

### Days 3–4

6. Tune three local Gmsh size maps and three TetGen option sets.
7. Select the smallest mesh that passes exactness, geometry and quality gates.
8. Convert to TET10/TRI6 and validate node sharing and Jacobians.
9. Write MED groups and inspect them in SALOME/ParaView.

### Days 5–7

10. Generate the production `.comm`, `.med` and `.export` without changing physics.
11. Solve in Code_Aster and compare with the gate-study reference.
12. Run the same deck through the GPU solver.
13. Record mesh-induced response differences and choose the canonical baseline settings.
14. Obtain the engineer’s one-time sign-off on conversational region names.

### Following week

15. Harden fTetWild fallback with exact projection, ambiguity quarantine and region-growing constraints.
16. Test the Gmsh discrete-volume route as a licensing/technology alternative.
17. Add deliberately damaged fixtures and full regression tests.
18. Package the meshing lane behind one deterministic API:

```python
mesh_variant(
    step_path,
    face_map,
    size_spec,
    policy="exact-first",
) -> MeshArtifact
```

`exact-first` means TetGen, then Gmsh discrete, then fTetWild only if the policy permits inferred provenance.

## Stop conditions

Stop investigating STEP export settings. Two independent translations already showed that re-exporting is not the core solution, and the current triangulated surface is already sufficient to build a closed labeled PLC.[^8]

Stop trying to improve centroid KD-tree transfer. It solves the wrong problem and has already produced measurable disagreement. Exact markers should replace it in the primary lane; exact projection with explicit ambiguity should replace it in the fallback lane.

Do not invest first in MOAB or a large mesh database. A provenance graph is valuable later, but today a compact NPZ/Parquet marker table plus MED groups is enough. Introduce MOAB only when fastcad needs multi-material interfaces, mesh version lineage across hundreds of variants, or distributed mesh operations.

Do not silently accept a geometrically valid mesh whose driven-region labels are inferred near face boundaries. For this product, semantic correctness is a first-class mesh-quality metric, not post-processing metadata.

## Final recommendation

Implement the **TetGen marked-PLC spike immediately** using the already successful Gmsh/OCCT surface. It directly addresses the missing correspondence, has native boundary-marker semantics, avoids global repair as a prerequisite, and can be proven correct through connectivity and marker round-trip tests.[^5][^7][^13]

Retain fTetWild because it is the stronger robustness tool for imperfect future variants, but classify it correctly: it provides an envelope-controlled geometric boundary, not an automatically auditable CAD-face provenance chain. In fastcad, the mesher policy should therefore be **exact-first, robust-second, never silent**.[^3][^1][^2]

---

## References

1. [Fast Tetrahedral Meshing in the Wild](https://cims.nyu.edu/gcl/papers/2020-fTetWild.pdf)

2. [[1908.03581] Fast Tetrahedral Meshing in the Wild - ar5iv - arXiv](https://ar5iv.labs.arxiv.org/html/1908.03581) - We propose a new tetrahedral meshing method, fTetWild, to convert triangle soups into high-quality t...

3. [[1908.03581] Fast Tetrahedral Meshing in the Wild - arXiv](https://arxiv.org/abs/1908.03581) - Abstract:We propose a new tetrahedral meshing method, fTetWild, to convert triangle soups into high-...

4. [TetGen: File Formats](https://wias-berlin.de/software/tetgen/fformats.face.html)

5. [5 File Formats](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html)

6. [TetGen: Features](https://wias-berlin.de/software/tetgen/features.html)

7. [6 Calling TetGen from Another Program](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual007.html)

8. [paste.txt](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/148611546/d965f6e2-ad79-4260-9d32-0d48dd020b13/paste.txt?AWSAccessKeyId=ASIA2F3EMEYE2HU6E3CX&Signature=gEpbcaoy7bRrQSaZfrxrgWdlkCE%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEEsaCXVzLWVhc3QtMSJHMEUCIQDNd3Fp7t1AnYZHiWI3unliSlx4DGVe44tLyxb6rsOW0QIgZKRPezfxKkswnEjkmlvBKkAo1i4lwl1E8PENGRkU7qwq8wQIExABGgw2OTk3NTMzMDk3MDUiDMsTAKxXDfQm3HEHMirQBCOq1f7bvo%2FKO157I1fHQ%2FLrvRr85BP8UriVfiR617ftgOUiBsB2QIp7RMpo53qABJou0DStNUSIqvffqlklevbAdi7ClDjFh8BEVJ5j8%2F46RKM9ru3d7pbXF4A5lytQKiN386qGN9K%2Fgjqghjs8U3k8mhUa%2BnnoK6XZshI0m4wKX5RXEavi%2FvICsInXOF%2Fhr%2FJqOCR5HCfX9Ay%2F6OWmleHqLQx6mJtis6K3%2FI28gzTjgmXVykukwlqxmtCwONzXhcqogtKU3VeTFlrapSOqxJWcovp6uS9Td1vktPtXZYM0xZwi6pOIEpekiPiBFE48NDAwQoaDwpazFmvyItAUx4OuCBKf1v%2B%2FSFpQWUpwDbIKnMszWb4WMkJo7bKTnDHPbXnSB%2BTHKRxCFBe5XjhCPIMzT3L1MRki%2FBb4mgbcShuEqGW2Hd5kFvC7qpSnkwiDbk1Mz4mUhSov%2FeX%2B07zz5CBkT3cydc6bFzGXGiHVq6aUXup7yvUe3P8BwhgsF2FYgrA4LZxw3R3eyAgUSphu4sXcWMnH1c8Ira6Nfp%2BYPiF3ht1J%2Froqd8xe7X0PMrFfjMQ97xc84q7y%2BpRy2O2mzuVaKiXt%2FLL%2BmatSWTyJQjZvTonCjTK5NNNdrUmFY1UpC1wFiDr5NJoM5N%2FqzjcSBE4DkGz40C1XcfNn5YuEVnc5GMedp4F2%2BbDk%2FXhlqjrN2egp5pX7OpgL7tzpA1U2a%2FVUpeUCxi1jw5keBCjgZwSndWUvh1YMyYZOoRkkAktiOHrjFS6RGkWJ6jZL7LNVnlsw7u2p1QY6mAFX0KHysK4Wt10JvGWixxSeTqls1HaGVXiJ3uFTxae2sJsqsgEh%2B7X8X3oP4YU1x8yeT3Ng3zFVk0HdSB90b0QPWQjN%2BM%2FtJK5eTpV%2Fmeq3dWMSk%2ByhTFYWyC5C5d4NXcp1%2F0u0IsQ42RyU9sxiUc0YH3yMr3%2FoKIDqw%2FJuZhDV0KtY1nCAageh249ANh0zQMBiMnDauhwuOg%3D%3D&Expires=1789560001) - Pasted markdown20260916-102958.md File can u solve this issue tell me libraries, github repos, ideas...

9. [Tetgen Manual (PDF)](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual.pdf)

10. [[PDF] A Quality Tetrahedral Mesh Generator and Three ... - TetGen](https://wias-berlin.de/software/tetgen/files/tetgen-manual.pdf)

11. [4 Using TetGen](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html)

12. [GitHub - TetGen/TetGen: Mirror repository for the TetGen mesh generator](https://github.com/TetGen/TetGen) - Mirror repository for the TetGen mesh generator. Contribute to TetGen/TetGen development by creating...

13. [GitHub - tataratat/tetgenpy: python tetgen wrapper](https://github.com/tataratat/tetgenpy) - python tetgen wrapper. Contribute to tataratat/tetgenpy development by creating an account on GitHub...

14. [igl.copyleft.tetgen¶](https://libigl.github.io/libigl-python-bindings/api/igl_copyleft_tetgen/) - Python bindings for libigl, a simple geometry processing library

15. [GitHub - zslwyuan/gmsh-doc: How to read the source code of gmsh](https://github.com/zslwyuan/gmsh-doc) - How to read the source code of gmsh. Contribute to zslwyuan/gmsh-doc development by creating an acco...

16. [gmsh.pdf](https://home.agh.edu.pl/~kbanas/MMNT/gmsh.pdf)

17. [Open CASCADE Technology: Shape Healing](https://dev.opencascade.org/doc/overview/html/occt_user_guides__shape_healing.html) - Open CASCADE Technology 8.0.1 guide: Shape Healing.

18. [step · Open-Cascade-SAS/OCCT Wiki](https://github.com/Open-Cascade-SAS/OCCT/wiki/step) - Open CASCADE Technology (OCCT) is an open-source software development platform for 3D CAD, CAM, CAE....

19. [meshio/README.md at main · nschloe/meshio](https://github.com/nschloe/meshio/blob/main/README.md) - :spider_web: input/output for many mesh formats. Contribute to nschloe/meshio development by creatin...

20. [GitHub - wildmeshing/fTetWild: Fast Tetrahedral Meshing in the Wild](https://github.com/wildmeshing/fTetWild/tree/master) - Fast Tetrahedral Meshing in the Wild. Contribute to wildmeshing/fTetWild development by creating an ...

21. [GitHub - wildmeshing/fTetWild: Fast Tetrahedral Meshing in the Wild](https://github.com/wildmeshing/fTetWild) - Fast Tetrahedral Meshing in the Wild. Contribute to wildmeshing/fTetWild development by creating an ...

22. [pyvista/pytetwild: Python wrapper for fTetWild - GitHub](https://github.com/pyvista/pytetwild) - License and Acknowledgments. This project relies on fTetWild and credit goes to the original authors...

23. [pytetwild](https://pypi.org/project/pytetwild/) - Python wrapper of fTetWild

24. [Salome MESH (SMESH) module to create and edit mesh in ... - GitHub](https://github.com/SalomePlatform/smesh) - - Creating groups of mesh elements. - Filtering mesh entities (nodes or elements) using Filters func...

25. [3.4. [U1.05.00]: FORMA00: An example of an axisymmetric cylinder under internal pressure¶](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u1.05.00.html)

26. [Grouping Elements¶](https://docs.salome-platform.org/latest/gui/SMESH/tui_grouping_elements.html)

27. [Surface Remeshing - mmgpy](https://kmarchais.github.io/mmgpy/latest/tutorials/surface-remeshing/) - Python bindings for the MMG remeshing library

28. [About references](https://www.mmgtools.org/about-references)

29. [GitHub - CadQuery/assembly-mesh-plugin: A plugin to convert CadQuery assemblies with tagged faces to a mesh](https://github.com/CadQuery/assembly-mesh-plugin) - A plugin to convert CadQuery assemblies with tagged faces to a mesh - CadQuery/assembly-mesh-plugin

30. [assembly-mesh-plugin/README.md at main · CadQuery/assembly-mesh-plugin](https://github.com/CadQuery/assembly-mesh-plugin/blob/main/README.md) - A plugin to convert CadQuery assemblies with tagged faces to a mesh - CadQuery/assembly-mesh-plugin

31. [tetgen/LICENSE at master · libigl/tetgen](https://github.com/libigl/tetgen/blob/master/LICENSE) - This is a mirror of the latest stable version of Tetgen. - libigl/tetgen

32. [Gmsh: a three-dimensional finite element mesh generator with built ...](https://gmsh.info/) - Gmsh is distributed under the terms of the GNU General Public License (GPL): Current stable release ...

33. [WildMeshing](https://github.com/orgs/wildmeshing/repositories) - Origanization for TetWild and TriWild codes. WildMeshing has 19 repositories available. Follow their...

34. [[PDF] Gmsh Reference Manual](https://gmsh.info/dev/doc/texinfo/gmsh.pdf)

35. [Gmsh 4.15.2](http://gmsh.info/doc/texinfo/) - Gmsh 4.15.2

36. [gmsh/tutorial/t13.geo at master · cycheung/gmsh](https://github.com/cycheung/gmsh/blob/master/tutorial/t13.geo) - Live clone of Gmsh <https://geuz.org/svn/gmsh/trunk> (username: gmsh, password: gmsh). - cycheung/gm...

37. [Gmsh 4.15.2](https://gmsh.info/doc/texinfo/gmsh.html) - Gmsh 4.15.2

38. [Fossies](https://fossies.org/linux/gmsh/examples/api/glue_and_remesh_stl.py)

39. [[Gmsh] Remeshing of STL file fails](http://geuz.org/pipermail/gmsh/2020/013597.html)

