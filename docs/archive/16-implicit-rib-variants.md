# 16 · Implicit rib variants — nTop-style rib layouts on the GB3 housing

How to generate rib variants on the rear housing 254492 the way nTop shows on its website:
ribs that change orientation, re-organise into different layouts, change height, with root
fillets and blends re-forming automatically. This page covers the mechanism, the housing as
measured, the open-source stack that can reproduce it, the steps, and who does what (user,
scripts, AI).

**State: designed, not built.** The design interview is open — six questions are awaiting
answers (§10). The recommendations in this page are the current proposal; nothing here is
decided until §10 says so.

Sources: web research, measurements taken on this machine, and this repo. Measured values
are marked as measured. Claims from vendor material are marked as vendor claims. Anything
that could not be verified is listed in §13.

---

## 0. In one paragraph

nTop stores a part as a **signed distance field** — for every point in space, the distance to
the surface, negative inside. On that representation a rib is a centreline pushed up into a
wall; a layout is a pattern of centrelines; and a union *with a blend radius* rounds every
junction where rib meets metal. Moving a rib re-evaluates the field, so its fillets re-form
wherever it now lands, with no B-rep boolean or fillet operation to fail. **It does not remove
meshing**: nTop's own FEA converts each variant to a surface and then a tet mesh. For this
housing the method is feasible only with a sparse (narrow-band) voxel kernel — a dense 1 mm grid
is 5 GB — and the candidate kernels are native binaries that this machine's Windows policy is
currently blocking, which points the geometry kernel at WSL.

---

## 1. The goal

- Ribs that **change orientation** — rotate about the bore axis, tilt off radial.
- Ribs that **re-organise** — change pattern (radial, grid, diagonal, crossed), count and spacing.
- Ribs that **change height and thickness**.
- **Fillets and other smooth regions adapt automatically** as ribs move.
- Seen live, as nTop demonstrates.
- Technical output: the steps, the inputs a user must supply, what scripts automate, and where
  agents/AI help.

It replaces the current rib path, whose problems are measured (§3.6): production ribs removed and
replaced by hand polygons with **sharp roots** (no fillet), fused by boolean, then remeshed per
design through a path that is **not deterministic**.

---

## 2. The geometry, measured

### 2.1 The STEP files

`assets/254492_0_closed_volume.step` and `assets/254492_0 - Part 1.step` are the **same
geometry**. They differ by 9 bytes (name string and timestamp).

| | |
|---|---|
| Format | STEP AP242 Edition 2 |
| Origin | `ONSHAPE BY PTC INC, 1.220`, written by ST-DEVELOPER v20 |
| Exported | 2026-09-06T14:01:33Z |
| Entities | 1 `MANIFOLD_SOLID_BREP`, 1 closed shell, 2,149 `ADVANCED_FACE` in the file |
| As read by OCC and by gmsh | 1 solid, 1 shell, **2,167 faces**, `BRepCheck_Analyzer` valid |
| Volume | **127,916.9 cm³** → **921.1 kg** at 7.201 g/cm³, against the drawing's stated 921.15 kg |
| Surface area | **9.213 m²** (gmsh `getMass` summed over all faces) |
| OCC bounding box | 1289 × 1379 × 690 mm |
| Tessellated extent | **1190 × 1305 × 688 mm** |

The OCC bounding box is inflated — `Bnd_Box` includes NURBS control points — so the tessellated
extent is the true one. Dense-grid budgets in §6 use the OCC box and are therefore slightly
conservative.

`_closed_volume` adds nothing: the other export is already a closed manifold solid.

### 2.2 The three B-reps in `assets/`

| file | faces | volume cm³ | what it is |
|---|---|---|---|
| `254492_0_closed_volume.step` | 2,167 | 127,916.9 | production housing, as exported |
| `housing_healed.brep` | 2,658 | 127,884.6 | production housing, healed; nine rib tops split into separate faces |
| `housing_baseline.brep` | 1,753 | 121,373.7 | **production ribs removed, in Onshape** — 6,543 cm³ (47.1 kg) less |

`housing_baseline.brep` is not regenerable from this repo (`.gitignore:100-103`). **Rib B was
never removed** and remains inside it. gmsh cannot parametrise 6 of its 1,753 faces
(`mesh/surface.py:21`).

### 2.3 Wall thickness, measured

Inward ray casting from 29,843 surface samples on the healed production housing:

```
p1 10.6   p5 14.9   p25 15.0   p50 27.6   p75 67.6   p95 166.9 mm
thinner than  5 mm:  0.2 % of surface
thinner than 10 mm:  0.9 %
thinner than 20 mm: 44.1 %
thinner than 40 mm: 56.4 %
```

A chunky casting, not a thin-walled one; p95 is solid bosses. Sheet 4 of the drawing shows walls
and ribs of 50, 70, 55, 40 and 20 mm (general tolerance X ±1.0).

The tessellation used for this was not watertight and its volume came out 0.26 % low
(127,550 cm³). That is immaterial to percentiles.

### 2.4 The machine

Checked 2026-09-10:

| module | state |
|---|---|
| `OCP` (OpenCASCADE, via cadquery) | **blocked** — `DLL load failed: An Application Control policy has blocked this file` |
| `netgen` | **blocked** — `WinError 4551` |
| gmsh 4.15.2 (carries its own OpenCASCADE) | loads |
| trimesh 5.1.0, embreex 4.4.0, pyvista 0.48.4, scipy 1.18.1 | load |
| `rtree` | not installed, so trimesh proximity and signed-distance queries are unavailable |
| WSL Ubuntu-24.04 | Code_Aster 18.0.12 at `/opt/ca` |

OCP loaded normally on 2026-09-08, so the block is new. The error text is that of Windows code
integrity — most likely Smart App Control, which can only be switched off, not whitelisted per
file. **Any new native library — OpenVDB, PicoGK — should be expected to hit the same block on
Windows.**

gmsh alone cannot currently stand in for OCP on this part:

- Importing the STEP and surface-meshing it fails with `Impossible to mesh periodic surface 2`.
- `occ.healShapes()` fails with `Could not fix wire in surface 865`.
- Surface-meshing `housing_healed.brep` at 6 mm with curvature sizing ran past 10 minutes without
  finishing.

### 2.5 The current mesh path, and why it is noisy

`mesh/surface.py`: B-rep → OCC tessellation → STL → gmsh rebuilds a volume from the STL
(`Mesh.MeshSizeMax` 20 mm, `Mesh.Optimize` 1). The STL round trip and a proximity weld make it
non-deterministic: **identical CAD gave 57,240 nodes on one run and 57,372 on another.** Nominal
mesh: 57,240 nodes, 202,496 tets, q_min 0.00788, 67 elements below q 0.1.

The solver side is measured and sound (`fem/aster.py`):

| | C3D4 (193,557 DOF) | C3D10 (1,271,826 DOF) |
|---|---|---|
| Code_Aster `MACRO_ELAS_MULT`, 55 unit cases | 138 s | 1,139 s |
| Code_Aster, 55 × `MECA_STATIQUE` | 385 s | — |
| CalculiX, 55 × `*STEP` | 915 s | exhausts 7.8 GB |

Linear tets are 25–35 % too stiff on this housing. CalculiX agrees with Code_Aster node-wise to
0.000 % at C3D4 and is kept as the oracle.

---

## 3. The ribs as they exist

### 3.1 Two rings of radial gussets

Every rib is a flat, vertical slab — `ydir = (0,0,1)`, horizontal radial `xdir`, tangential
normal — bridging the bore boss to the outer wall. At nominal thickness each is a radial spoke
centred on the main bore axis through (0,0).

| ring | thickness | z range | serves | ribs |
|---|---|---|---|---|
| **Front** (code `dn`) | 20 mm | 544–673 | BORE_MAIN_S3, Ø360.02, z 554.7–659.6 | B, C, D, E, J, N259, N109 |
| **Rear** (code `up`) | 25 mm | 31–137 | BORE_MAIN_S2, Ø541, z 70.2–125.2, just above the main flange bolt circle (PCD 1120 at z 69.02) | A, F, G, H, I, M157, M017, M270, M030 |

The rings are split at `RING_SPLIT_Z = 300` (`pipeline/sample.py:34-38`), with 478 mm of bare
casting between them. None of the ribs is nearer than 239 mm to the high-speed axis AX1
(`handbook/14-objective.md:427-430`). Reaching the high-speed shaft would need ribs bridging
AX2_S3 to AX1_S4 inboard of z 446.

### 3.2 All sixteen

From `assets/rib_outlines.json`. θ is the azimuth of the origin; the production "home" angle is
in brackets where the rib has been moved. u × v is the profile extent in the rib's plane.

| rib | nominal mm | θ° (home) | u × v mm | r mm | z mm | status |
|---|---|---|---|---|---|---|
| B | 20.03 | 200.6 | 228.5 × 113.0 | 200–485 | 544–667 | production, fixed (`SKIP`) |
| C | 19.98 | 234.4 | 193.5 × 112.0 | 199–411 | 546–669 | production |
| D | 19.98 | 305.6 | 193.5 × 112.0 | 199–411 | 546–669 | production |
| E | 19.96 | 344.6 | 228.5 × 113.5 | 203–448 | 545–669 | production |
| J | 19.99 | 137.0 (131.06) | 392.6 × 111.5 | 194–596 | 548–673 | production, moved |
| N259 | 20.0 | 258.9 | 193.5 × 112 | 199–403 | 546–669 | candidate, fit of C |
| N109 | 20.0 | 109.1 | 236.0 × 112.1 | 195–461 | 546–669 | candidate, fit of C |
| A | 25.0 | 197.9 (202.5) | 185.5 × 104.1 | 287–477 | 32–137 | production, moved |
| F | 24.96 | 326.0 (337.5) | 191.6 × 104.9 | 294–487 | 31–136 | production, moved |
| G | 25.0 | 294.0 (297.58) | 171.5 × 99.7 | 295–469 | 37–137 | production, moved |
| H | 25.0 | 229.9 (242.42) | 182.6 × 99.8 | 294–479 | 37–137 | production, moved |
| I | 25.03 | 133.9 | 350.0 × 77.7 | 294–652 | 56–134 | production |
| M157 | 25.0 | 165.9 (157.0) | 208.0 × 103.7 | 292–501 | 33–137 | candidate, fit of A |
| M017 | 25.0 | 358.0 (16.6) | 188.0 × 103.7 | 294–484 | 32–137 | candidate, fit of A |
| M270 | 25.0 | 261.9 (270.0) | 168.0 × 103.7 | 292–464 | 32–137 | candidate, fit of A |
| M030 | 25.0 | 20.0 (30.0) | 212.0 × 103.7 | 295–513 | 32–137 | candidate, fit of A |

- The lettered ribs A–J lie on production rib face pairs in `housing_faces.json` (normal dot
  product 1.0000, plane offset exactly t/2): B↔RIB_44, C↔RIB_39, D↔RIB_40, E↔RIB_20, J↔RIB_14,
  A↔RIB_54, F↔RIB_53, G↔RIB_59, H↔RIB_58, I↔RIB_42.
- The production pairs mirror about θ = 270°: A/F, H/G, C/D, B/E.
- The rear ring as currently configured is evenly spaced: M157, A, H, M270, G, F, M017 sit exactly
  32° apart (165.9 … 358.0°). M030 is at 20°, I at 133.9°.
- Sheet 1 of the drawing carries a `12X 30°` callout, read in the repo as a radial array.
- Naming trap: the campaign calls the all-15-ribs design (`gcpv_e56235e636`, 44.6 kg of rib) the
  "production casting". It includes the six candidates.

### 3.3 Fillets, draft and thickness on the real casting

- **Production root fillets are R5–10 mm.** Fillet tori across the housing range R0.5–20.
- **Production rib flanks have zero draft** — exactly parallel and vertical.
- **Drawing note 3:** *"ALL NON-SPECIFIED RADII R3.0 AND CHAMFERS 1X45°"* — the only casting rule
  on any drawing, and the floor for any generated fillet.
- **No draft, minimum-wall, casting or foundry rule exists on any drawing.** 254492 says only
  *"CHECK CAST WALL THICKNESS. REPORT TO ENGINEERING PRIOR TO MACHINING"*. Casting rules must be
  entered as assumptions.
- **Thickness rule used by the repo:** rib ≤ wall, ideally 0.8 × wall; castable window roughly
  15–25 mm. Ribs as built: 24.999 ± 0.017 mm (rear), 19.991 ± 0.020 mm (front).

### 3.4 Keep-outs already evidenced

Built as FEM interfaces by `fem/model.py:build()` on `housing_healed.brep`:

- **9 bearing seats:** MAIN_S2 Ø541, MAIN_S3 Ø360.02, AX1_S1 Ø180, AX1_S3 Ø190, AX1_S4 Ø200,
  AX1_S5 Ø211, AX2_S2 Ø180, AX2_S3 Ø272, AX2_S4 Ø345. Axes: MAIN (0,0), AX1 (0,520),
  AX2 (246.3, 376.6). Four stations are skipped: MAIN_S1, MAIN_S4, AX1_S2, AX2_S1.
- **25 bolt positions** on the main flange, 25X Ø26.00 THRU, Ø55.00 counterbore, PCD 1120.

Cited on drawing 254492 rev J sheet 1 but **not built as an interface**: the mount pattern,
12X Ø14.00 THRU M16-6H, position Ø0.25 to D EV EW. Concentricity Ø0.035 to EW applies to both
main bores.

`housing_faces.json` classifies faces geometrically (fillet 617, freeform 432, hole 320,
wall_flat 272, fillet_tor 223, …) and proposes 26 frozen groups (13 `BORE_*`, 5 `HOLE_*`,
`BOLT_MAIN_PCD1120`, 7 `PATTERN_*` with identity not established). **It has no labels for seal,
datum or mount faces.**

Ribs start 15–25 mm outside the bore surfaces. The rear ribs reach r 477–513 mm, 47–83 mm inside
the bolt circle at r 560.

### 3.5 Loads and objective (context for evaluation)

`assets/loads.json`: DLC 1.3 extreme, low-speed-shaft torque 401 kN·m, forces on six seats
through RBE3 couplings, flange grounded by 25 RBE2 bolts, resolved into a 16-case unit-load
basis.

| seat | FX N | FY N | FZ N |
|---|---|---|---|
| AX1_S1 | 5,650 | 55,753 | 0 |
| AX1_S4 | 9,801 | 35,145 | −21,524 |
| AX2_S2 | −57,912 | 5,846 | 0 |
| AX2_S3 | −83,661 | 75,244 | −28,264 |
| MAIN_S2 (incl. 50 % carrier share) | 57,186 | −330,206 | 71,500 |
| MAIN_S3 | 68,936 | −148,449 | 137,023 |

Objective (`corpus/ingest.py:287`): J = |IMS_82_23 lead, µm| / 10 + umax / umax_ref + p99.9 / 250,
robust mode as the median over a ±5 % load band with 4,000 draws. 490 designs solved, all
presence/absence at fixed ring thickness (`RING_MM = {"up": 25.0, "dn": 20.0}`).

### 3.6 Why the current rib designs are not production-grade

- Hand polygons fused by `BRepAlgoAPI_Fuse` with **sharp roots**. Peak stress sits 4.6 mm from a
  46° edge with zero radius (`handbook/05-analysis.md:140`).
- No draft, no tip rounding.
- Removal of production ribs has only worked cleanly in Onshape. In-repo attempts removed 3.2×
  too much volume (triangle deletion, Rib I: 946 cm³) or were only ever completed for one rib
  (B-rep shell edit, Rib I: 296.6 cm³; `git show 4f8a926:docs/RIB_REMOVAL.md`).
- Every design is remeshed through the noisy path in §2.5.

---

## 4. How nTop does it

Every statement below carries its source. nTop's support site returned HTTP 403 to direct
fetches, so block details come from search-result excerpts of those pages.

### 4.1 Representation

- Bodies are implicit distance fields: zero is the surface, negative inside; union is min,
  intersection is max. Rendering is on the GPU in shaders; nothing is voxelised until meshing.
  [nTop blog](https://www.ntop.com/resources/blog/implicits-and-fields-for-beginners/)
- A from-scratch kernel shipped in **nTop 5.0 (24 June 2024)**, for precision and faster booleans.
  [nTop 5](https://www.ntop.com/resources/product-updates/ntop-5/) ·
  [kernel note](https://support.ntop.com/hc/en-us/articles/26062971882131-nTop-5-0-New-Implicit-Modeling-Kernel)
- nTop's own 5.0 notes admit that after some operations gradients near medial axes are not unit
  length (the field is no longer an exact distance) and inside/outside can flip near zero.
  [expected differences](https://support.ntop.com/hc/en-us/articles/27281187796883-nTop-5-0-Outline-of-expected-differences)
- Resolution appears only at meshing. In `Mesh from Implicit Body`, voxel size = tolerance / 2,
  suggested tolerance 0.5 × thinnest feature; halving the tolerance roughly quadruples triangle
  count; a "Sharpen" pass restores sharp edges.
  [nTop Learn](https://learn.ntop.com/courses/102-guide-to-meshing/lessons/converting-to-a-mesh/)
  nTop 5.27 added adaptive tessellation (`Mesh from Implicit by AT`).
  [5.27](https://support.ntop.com/hc/en-us/articles/43355998101907-nTop-5-27-What-s-New)

### 4.2 Ribs — nTop 5.10 "Rib Design" (Beta, early 2025)

Shown in the [11 March 2025 webinar](https://www.ntop.com/resources/webinars/whats-new-in-ntop-march-2025/).
*"Project conformal patterns directly onto implicit geometry and then extrude the patterns into
solid ribs"*; simulation data or other fields can drive *"rib orientation…, thickness, draft
angle, and rib-rib fillets"*.
[Guide](https://support.ntop.com/hc/en-us/articles/35117560848275-Guide-to-Rib-Design) ·
[Intro](https://support.ntop.com/hc/en-us/articles/34963705378579-nTop-5-10-Introduction-to-Rib-Design)

1. `Quadrangulate Mesh` — a quad mesh over the part.
2. `Graph on Quad Mesh (BETA)` applies a 2D unit cell; or `Graph on CAD Face (BETA)` for a layout
   on one face. Grid types named elsewhere: **isogrid, orthogrid, honeycomb, Voronoi**.
   [blog](https://www.ntop.com/resources/blog/design-tips-structural-optimization-lightweighting/)
3. `Ribs from Graph (BETA)` — inputs: Body, **Height**, **Thickness** (both field-drivable),
   **Direction** (body normals, or an axis/plane — the casting pull direction), **Draft angle**.
   It conforms centrelines to the part even where the graph deviates.
4. `Boolean Union` with a blend radius adds the root fillet. `Blend Intersections` blends
   rib-to-rib junctions. [5.10](https://support.ntop.com/hc/en-us/articles/35301241302163-nTop-5-10-What-s-New)

Where alignment fails on complex curvature, nTop recommends a rotationally symmetric unit cell.
Before 5.10, ribbing used conformal lattices.
[Learn 311](https://learn.ntop.com/courses/311-ribbing-and-texturing/)

### 4.3 Fillets and blends

- `Boolean Union` blend types: Sharp, Rounded, Chamfered. The blend *"adds a fillet… where the
  merged bodies meet"*.
  [booleans](https://support.ntop.com/hc/en-us/articles/360041442674-How-to-use-boolean-operations)
  These match published SDF operators (`fOpUnionRound`, `fOpUnionChamfer` in
  [hg_sdf](https://mercury.sexy/hg_sdf/); smooth-min in [Quilez](https://iquilezles.org/articles/smin/));
  that nTop uses them is inference, not documented.
- `Smoothen Body` (fillet size set by grid size and iterations) and `Offset Body` (offset-based
  fillet). [lattice fillets](https://support.ntop.com/hc/en-us/articles/360056533394-How-to-add-fillets-to-lattices)

### 4.4 Import, keep-outs, export

- Import: `Implicit Body from CAD Body`; too coarse a tolerance merges small details.
  [support](https://support.ntop.com/hc/en-us/articles/360057842793-Why-does-my-part-appear-to-lose-detail-when-it-s-converted-to-an-implicit-body)
- Keep-outs: `Passive Region Constraint` in topology optimisation, often thickened mounting holes;
  functional regions added back with volumetric booleans.
  [passive regions](https://support.ntop.com/hc/en-us/articles/24854202367891-How-to-define-a-passive-region-for-optimization)
- Export: `CAD Body from Implicit Body (Beta)` since 3.28 (July 2022) — G1 NURBS, *"not
  necessarily nicely arranged"* on complex parts; or quad mesh → `CAD Body from Quad Mesh` → STEP
  or Parasolid. Their lattice-cube example: STEP over 600 MB against a .ntop under 30 kB.
  [export](https://support.ntop.com/hc/en-us/articles/7323484481555-How-to-export-geometry-as-a-CAD-part-STEP-or-Parasolid)

### 4.5 Simulation — nTop remeshes

- Built-in FEA: surface mesh → `Remesh Surface` → `Volume Mesh` (tets) → `FE Volume Mesh`.
  nTop 5.0 added FE Tetrahedral and FE Shell mesh blocks.
  [meshing blog](https://www.ntop.com/resources/blog/meshing-in-fea-cfd-manufacturing/) ·
  [5.0 meshing](https://support.ntop.com/hc/en-us/articles/30049593128211-nTop-5-0-Meshing-updates-for-Simulation-Optimization)
- Partner **Intact.Simulation** (Immersed Method of Moments) skips body-fitted meshing: the
  implicit sits in an independent hex background grid, and only boundary-cut cells are integrated.
  Stress, modal, thermal, thermo-mechanical; reads `.implicit` natively.
  [Intact](https://intact-solutions.com/closing-the-simulation-gap-for-implicit-design/) ·
  [nTop simulation](https://www.ntop.com/software/capabilities/simulation/)
  Vendor example: connecting rod 0.422 vs 0.421 mm displacement, 84 vs 88 MPa stress — one case,
  vendor-run.

### 4.6 Demos that exist

None shows a gearbox housing switching between rib layouts. The nearest:

- Conformal isogrid on a low-bypass turbofan casing (30 Jul 2020).
  [video](https://www.ntop.com/resources/videos/ntop-live-conformal-isogrid-ribbing-on-low-bypass-turbofan-engine-casing/)
- Topology-optimisation-driven rib grid on a cast swing arm, with casting draft (15 Mar 2022).
  [video](https://www.ntop.com/resources/videos/ntop-live-topology-optimization-driven-ribs-on-a-swing-arm/)
- Injection-moulded car pedal rib patterns via TO and lattices, exported to CATIA (28 May 2021).
  [video](https://www.ntop.com/resources/videos/ntop-live-topology-optimization-of-injection-molded-car-pedal-ribs/)
- TO for cast and moulded parts with de-moulding constraint and draft (4 Apr 2024).
  [video](https://www.ntop.com/resources/videos/topology-optimization-design-for-cast-and-injection-molded-parts/)

### 4.7 Automation

nTop Automate: `nTopCL.exe -j input.json -o out.json file.ntop`, headless on Windows or Linux,
typed JSON inputs, driven from Python via `subprocess`; a DoE is many JSON files.
[Python](https://support.ntop.com/hc/en-us/articles/360052703693-Running-nTop-Automate-in-Python-scripts) ·
[DoE](https://support.ntop.com/hc/en-us/articles/14566307798291-How-to-set-up-a-DOE-in-Python-for-nTop-Automate)
No public native Python geometry API was found.

### 4.8 Marketing against fact

- *"Booleans, offsets and rounds never fail"* holds for the function algebra only; nTop's own
  notes document detail loss at coarse tolerance and self-intersections at meshing.
- *"10× faster iterations"* is marketing.

---

## 5. The method for GB3

### 5.1 The mechanism

Let B be the housing's distance field, R the union of rib fields, K the keep-outs, r the fillet
radius.

1. **B** — built once from the rib-free skin (`housing_baseline.brep`).
2. **Each rib** — a centreline on its base surface, extruded along the pull axis with height h,
   thickness t and draft, then clipped to the zone where ribs may exist.
3. **Fillet** — offset-close, restricted to the ribs:
   `F = close_r(B ∪ R)`, then `result = B ∪ R ∪ (F ∩ dilate_(r+δ)(R))`.
4. **Keep-outs** — `result − K`, so bores, bolt holes and machined faces come out exact.
5. **Surface** — contour the field to a watertight triangle mesh.

**Why offset-close and not smooth-min.** A smooth-min union with blend k changes the field only
where the two bodies are within k of each other, but its radius is only approximately circular,
and with more than two bodies it can round features near a rib that should stay sharp.
Offset-close (grow by r, shrink by r) gives a true rolling-ball radius. It needs a **grid kernel**:
on an exact analytic field `(f − r) + r = f`, so closing does nothing unless the field is
re-distanced between the two steps, which grid kernels do.

**Why restrict the fillet.** Closing the whole of B ∪ R would also round the housing's existing
concave edges and fill narrow gaps. Intersecting F with a band around R limits the change to where
ribs meet metal.

### 5.2 The rib as a parametric object (proposed)

Modelled the way nTop's `Ribs from Graph` works. A **layout generator** emits a graph of
centrelines; each edge becomes one rib.

| parameter | meaning | proposed default / bound | basis |
|---|---|---|---|
| layout family | radial N-fold, paired, orthogrid, isogrid, diagonal/crossed; later stress-aligned | radial | production is radial |
| count N, phase φ₀, spacing | pattern controls | — | rear ring today: 32° pitch |
| azimuth θ | rotation about the bore axis, per rib | — | M-ribs already vary it |
| skew ψ | tilt off radial | 0 | production is radial |
| thickness t | wall thickness | rear 25, front 20; window 15–25 | foundry rule, §3.3 |
| height h, profile h(r) | free-edge height, constant or tapered | ≈ 100–113 mm | production extents |
| draft | flank taper about the pull axis | 0°, up to 3° | production 0; `taper_deg` 0–3 in research/11 |
| pull axis | extrusion direction | +Z | ribs are vertical |
| root fillet r_f | offset-close radius | **R8, floor R3** | production R5–10; note 3 |
| tip | free-edge treatment | fully rounded | removes a stress edge |
| rib-to-rib junction | blend at crossings | = r_f | — |

Every layout — hand-made, generated, or AI-proposed — reduces to the same list of ribs, so every
one can be inspected, clipped, filleted and meshed the same way.

### 5.3 Zones (proposed, milestone 1)

- **Rear ring zone** — the annulus between the MAIN_S2 boss and the outer wall above the main
  flange, z ≈ 31–137, r ≈ 290–650.
- **Front ring zone** — around MAIN_S3, z ≈ 544–673, r ≈ 195–600.

Extensions: the 478 mm bare band between the rings; any outer skin outside keep-outs, including
the AX2_S3–AX1_S4 bridge to the high-speed shaft.

### 5.4 What is fixed and what changes per variant

| fixed once | changes per variant |
|---|---|
| Skin field B | Rib fields R |
| Zone bodies, keep-out bodies K | Fillet band around R |
| Pull axis, grid | Contoured surface |
| Load definition, interfaces | Tet mesh |

---

## 6. Budgets, measured

### 6.1 Voxel budget for the distance field

Surface area 9.213 m²; dense sizes use the OCC bounding box.

| voxel | dense grid | narrow band ±3 voxels |
|---|---|---|
| 2 mm | 0.16 G voxels · 0.6 GB float32 | ~13.8 M voxels · ~72 MB |
| 1 mm | 1.26 G voxels · 5.0 GB | ~55.3 M voxels · ~287 MB |
| 0.5 mm | 9.94 G voxels · 39.7 GB | ~221.1 M voxels · ~1.15 GB |

- A dense 1 mm grid is not workable for interactive iteration; a narrow band is.
- An R8 fillet needs ≲ 1 mm voxels to be resolved to a few voxels across its radius.
- The offset-close band must be at least r wide. At 0.5 mm and r = 10 mm that is ~20 voxels, about
  1.5 × 10⁹ voxels globally — so closing must run in windows around the ribs, or use an
  interface-tracking offset (OpenVDB `LevelSetFilter::offset`).
- A surface mesh at 1 mm is roughly 2 × 10⁷ triangles before adaptivity or decimation.

### 6.2 The immersed-grid alternative, measured

Proposed in `handbook/new_plan/` (§11): solve on a fixed Cartesian grid instead of meshing each
variant. Occupancy on the real casting, node lattice classified by embree ray parity:

| grid | active cells | cut cells | FE nodes | DOF |
|---|---|---|---|---|
| 20 mm | 29,013 | **83 %** | 43k | 0.13 M |
| 10 mm | 182,504 | **61 %** | 239k | 0.72 M |
| 5 mm | 1,239,208 | **36 %** | 1,464k | 4.39 M |

Against the body-fitted mesh: 0.17 M DOF at C3D4 and 1.27 M at C3D10.

**The fixed grid costs more DOF than the body-fitted mesh and spends them worse.** At 10 mm it
needs 4× the DOF of the linear-tet mesh while 61 % of its cells are cut cells. At 5 mm, 4.39 M DOF
is beyond `scipy_splu`, the only solver any of the plans names. Cause: a Cartesian grid on a part
filling 10.4 % of its bounding box, with a 27.6 mm median wall, spends most of its resolution
straddling boundaries. Caveat: the inside test ran on a tessellation 0.26 % low in volume.

---

## 7. Open-source stack candidates

### 7.1 Geometry kernels

Columns: (a) mesh → SDF import · (b) smooth blend or morphological fillet · (c) copes with 1.3 m
at 0.5–1 mm · (d) watertight surface out.

| kernel | licence · language · latest | (a) | (b) | (c) | (d) |
|---|---|---|---|---|---|
| **PicoGK** + ShapeKernel (LEAP 71) | Apache-2.0 · C# on a C++ OpenVDB runtime · v2.3.0, 2026-08-05 · no Python | `Voxels(Mesh)` | offset-close: `DoubleOffset`, `TripleOffset`/`Smoothen`, `OverOffset`, `Fillet` | sparse | `mshAsMesh()` |
| **OpenVDB** (C++) | Apache-2.0 · v13.0.0, 2025-11-04 | `meshToLevelSet` | `LevelSetFilter::offset`, `fillet()` | narrow band | `volumeToMesh` with adaptivity |
| OpenVDB Python | not on PyPI; conda-forge 13.0.0 | `createLevelSetFromPolygons` | **no filters or morphology exposed** — offset-close only by re-voxelising at isovalue ±r | yes | `convertToPolygons` |
| NanoVDB | part of OpenVDB; v13 adds GPU morphology | via OpenVDB | GPU morphology | yes | via OpenVDB |
| fVDB | Apache-2.0 · 0.5.1 · Linux + CUDA only | `gridbatch_from_mesh` | dilation only | yes | marching cubes |
| NVIDIA Warp | Apache-2.0 · 1.17.0, 2026-08-31 · Windows ok | GPU mesh sign queries | write your own | `MarchingCubes` needs dense tiles | marching cubes |
| libfive | MPL-2.0 kernel · PyPI wheel from 2020 | no (F-rep only) | analytic blends | octree | feature-preserving |
| fidget | MPL-2.0 · Rust · v0.5.0 · "experimental" | no | analytic | JIT | dual contouring |
| fogleman/sdf | MIT · Python · last commit Aug 2024 | via OpenVDB | `smooth_union(k)`; its dilate/erode cannot close | slow at 10⁹ points | skimage MC |
| manifold3d | Apache-2.0 · 3.5.3 · pip incl. win_amd64 | no | `MinkowskiSum` impractical here | `LevelSet` dense, GIL-bound | manifold |

Only PicoGK and OpenVDB (C++) offset-close an imported CAD body natively. MeshLib does, but is free
only for non-commercial use.

Supporting pieces: libigl 2.6.3 (MPL-2.0) `signed_distance`; mesh2sdf 1.1.0 (MIT); scikit-image
0.26.0 `marching_cubes`; PyVista 0.49.0 `contour`.

### 7.2 Surface → tetrahedra

| tool | licence · version | notes | deterministic |
|---|---|---|---|
| fTetWild / `pytetwild` | MPL-2.0 · pytetwild 0.4.2, Win/Linux/macOS wheels | robust to imperfect input; `edge_length_fac`, `epsilon`, sizing field | not documented; use one thread |
| gmsh | GPL-2+ with linking exception · 4.15.2 | STL remeshing; HXT parallel Delaunay | **HXT has a reproducible mode**; without it element order varies |
| CGAL Mesh_3 / `pygalmesh` | GPL-3+ or commercial · CGAL 6.2 (2026-06-11) · pygalmesh 0.10.7 | **meshes an implicit domain directly**; sharp features supplied as polylines | seedable; sequential runs reproducible |
| TetGen | AGPL-3 or commercial · 1.6.0 (2020); `pip tetgen` wrapper MIT | needs a clean surface | sequential; not verified |
| Netgen | LGPL-2.1 · 6.2.2607 | STL → tets | not verified; blocked on this machine |

### 7.3 Implicit → B-rep / STEP

No production-grade open-source route to a feature-based B-rep exists. Faceted STEP (one face per
triangle, via OCCT) works but is huge and not editable. Primitive/freeform fitting is research
grade (Point2CAD, CVPR 2024). nTop's own converter is Beta. **Not needed for a proof of concept** —
FEA runs on the tet mesh and results display on the surface mesh. STEP matters only for foundry or
pattern hand-off.

---

## 8. Evaluation path and meshing noise

Implicit ribs change topology, so the tet mesh changes per variant — nTop included. The noise seen
in the current campaign is therefore controlled, not designed away:

- **Deterministic surface.** Contouring on a fixed grid is deterministic for identical fields.
- **Deterministic tets.** CGAL Mesh_3 with a fixed seed (meshes the implicit directly, no STL
  step); gmsh with HXT in reproducible mode; fTetWild single-threaded.
- **Measured noise floor.** Re-generate one design several times, solve each, report the spread
  in J. The top eight designs are within 1.8 % of one another, and until this number exists that
  ranking is not known to be real.

The immersed grid (§6.2) avoids meshing but was measured to cost more DOF for worse accuracy on
this part.

---

## 9. Who does what

### The user supplies

1. **Where ribs may exist** — zone bodies (§5.3).
2. **What must not be touched** — confirm the evidenced keep-outs (§3.4) and add clearances the
   drawings do not state: bolt-head and tool access, mainframe envelope, internal gear clearance.
3. **Casting rules** — thickness window, draft, minimum fillet, section ratio. None are on the
   drawings; they are assumptions and are labelled as such.
4. **Layout intent** — which families to explore and the bounds on each parameter.
5. **The objective** — what "better" means for this study.

### Scripts do, deterministically

- Build the skin distance field once.
- Generate the layout graph and each rib from parameters.
- Clip to zones, fillet, subtract keep-outs.
- Contour to a watertight surface; check volume, mass, minimum thickness and the fillet radius
  actually achieved.
- Render in the viewer.
- Mesh with a fixed seed; set up and solve in Code_Aster; extract J.

### AI and agents help with

- **Intent → parameters.** "Diagonal ribs between the two bearings, 30 mm tall" into a layout
  family, count, angles and bounds.
- **Stress-aligned layouts.** Propose centrelines along principal-stress trajectories from a
  baseline solve (refs 1–3 in §12).
- **Keep-out evidence.** Map drawing callouts (GD&T, datums) to faces to be protected.
- **Rule checking.** Flag thickness, draft or section-ratio violations and explain them.
- **Campaign design.** Choose which layouts to generate next, given what has been solved.

The geometry itself is never produced by a model — only by scripts, so it is repeatable.

---

## 10. Open decisions

### 10.1 Round 1 — awaiting answers

| # | question | options | recommended |
|---|---|---|---|
| Q1 | First milestone | (a) visual generator · (b) analysis-ready designs · (c) visual first, every variant watertight and analysis-capable from day one | **(c)** |
| Q2 | Where ribs may exist | (a) the two existing rings · (b) + the bare band between them · (c) anywhere on the outer skin outside keep-outs | **(a)**, with zones defined so (b) and (c) are new zone bodies, not new code |
| Q3 | Skin to grow ribs on | (a) `housing_baseline.brep` with Rib B fixed · (b) remove Rib B in Onshape first · (c) keep production ribs, infill only | **(a)** now, **(b)** when convenient |
| Q4 | What a rib is | (a) individual ribs · (b) layout generator emitting ribs · (c) field-driven ribs | **(b) on (a)** — nTop's graph → `Ribs from Graph` model (§5.2); (c) later as a generator that emits ordinary ribs |
| Q5 | Fillet policy | radius global / per family / from thickness; tip sharp / rounded / chamfered; crossings | **per-family root fillet, R8 default, R3 floor; rounded tip; crossings at r_f; offset-close, localised** |
| Q6 | Where the geometry kernel runs | (a) WSL · (b) Windows, only libraries that load · (c) relax the Windows policy | **(a)** — both kernels are native binaries likely to be blocked; the solver already runs there |

### 10.2 Round 2 — ready once Round 1 is answered

- **Kernel:** PicoGK (C#), OpenVDB C++ behind a small wrapper, or OpenVDB Python with the isovalue
  re-voxelisation workaround.
- **Voxel size:** 1 mm or 0.5 mm, against the budgets in §6.1.
- **Scope of the field:** voxelise the whole housing, or only the rib zones and stitch to the exact
  housing elsewhere.
- **Tet mesher and its determinism:** CGAL Mesh_3, gmsh HXT reproducible mode, or fTetWild.
- **The viewer loop:** target regeneration time per slider change.

### 10.3 Later

- The role of AI and agents, once the geometry loop exists.
- Output format — surface mesh only, or a STEP hand-off.

### 10.4 Also open, from the review of `handbook/new_plan/`

Asked on 2026-09-09 and not yet answered:

| question | recommended |
|---|---|
| Physics scope — static only, or must modal/NVH survive? | Static for this half, with modal recorded as a requirement the method must not foreclose |
| Deliverable — better designs, better data, or both staged? | Both staged, with a measured noise floor as the gate |
| **Does a live parametric Onshape model of 254492 exist, and can it be driven?** | If yes, it is the only route to genuinely production-grade CAD ribs |
| New package in this repo, or a separate folder? | New package in this repo |
| What survives — Code_Aster, the 490 designs, the morph engine, the 16-case basis, the UI? | All except the STL → gmsh mesher |
| The 42 existing handbook pages | A current-state set for the new work; migrate the measurements, retire the decision log |

Evidence bearing on the Onshape question: the STEP was exported from Onshape on 2026-09-06; the rib
set is described as *"currently in the Onshape tree"* (`assets/design_nominal.json`); *"Adding the
fillets needs Onshape"* (`handbook/10-open.md:12`); and the Onshape route was previously rejected on
API budget — 4,000 designs × 4 calls against 2,500 (`cad/design.py` docstring).

---

## 11. The `handbook/new_plan/` documents

Five markdown files and one PDF, untracked in git:

- `gb3-agentic-immersed-ai-platform-master-plan.md` (2,079 lines)
- `grc-gb3-immersed-simulation-implementation-plan.md` (1,288)
- `immersive-geometry-gb3-integration-plan.md` (665)
- `agentic-engineering-platform-strategy.md` (677)
- `ui-agentic-backend-build-plan (1).md` (1,043)
- `ui_agentic + Platform API — Full Build Plan.pdf`

What they propose:

- An **immersed / cut-cell FEM** on a fixed Cartesian grid, geometry from a B-rep-derived SDF,
  trilinear hexes, adaptive subcell quadrature, penalty boundary conditions (Nitsche later),
  `scipy_splu`. This is the Finite Cell Method family, though the documents never use that name.
- Static linear elasticity only. NVH appears nowhere; modal once, as a deferred claim.
- The immersive-geometry plan keeps the B-rep authoritative and ribs as B-rep booleans; SDF is
  *"later, optional"*.

Where they disagree or are incomplete:

- **The same capability is scheduled three ways:** "P2, 1–2 weeks" (implementation plan), "add
  next" (strategy), "Phase 5 · do not build yet" (immersive-geometry plan).
- **No cell count, DOF, RAM or solve time appears in any of them.** Manifest fields are `0`
  placeholders (`c_alpha: 0`, `E: 0`, `active_cells: 0`). §6.2 supplies the numbers.
- The 20 mm grid used as the default in their API examples is 83 % cut cells on this part.
- No iterative solver, preconditioner or AMG library is named as a fallback.
- The master plan's "fixed DOF numbering" conflicts with its own per-geometry active-cell counts.
- Rib SDFs in Release 0 still come from B-rep booleans, so the boolean failure mode is not removed.
- Phase order conflicts: platform first (master plan) against solver chain first and platform last
  (implementation plan).
- Endpoint paths (`/api/v1/...` against unversioned) and agent tool names differ between documents.
- Citations such as `[file:29]` and `[file:79]` have no legend.
- The named artefacts `production.step`, `groups.json`, `basis.npy` and `gb3-baseline.glb` do not
  exist in the repo.

---

## 12. Literature

1. Liu, Wu, Huang, Cao, Liu, Tu, Lu — *Principal stress field-guided optimization for rib
   structure generation*, Computer-Aided Design, 2025.
   [link](https://www.sciencedirect.com/science/article/abs/pii/S0010448525001162)
2. Li et al. — *Rib-reinforced Shell Structure*, Computer Graphics Forum, 2017; ribs from principal
   stress lines. [link](https://onlinelibrary.wiley.com/doi/abs/10.1111/cgf.13268)
3. *Reconstruction of principal stress lines using FEA applied to Nervi-type shell design*,
   Structural and Multidisciplinary Optimization, 2024.
   [link](https://link.springer.com/article/10.1007/s00158-024-03913-9)
4. Jiang, Huo, Liu, Du, Zhang, Li, Guo — conformal mapping + Moving Morphable Components for
   explicit rib layout on complex surfaces, CMAME 404:115745, 2023; output straight to CAD.
   [link](https://www.sciencedirect.com/science/article/abs/pii/S0045782522007009)
5. Kim et al. — structural–acoustic TO then rib design on a gearbox housing, −2.43 dB(A),
   *Scientific Reports* 14:4145, 2024. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10879208/)
   (see [15](15-differentiable-cad-and-gradients.md) §6)
6. *Rib Design for Improving the Local Stiffness of Gearbox Housing for Agricultural EVs*.
   [RG](https://www.researchgate.net/publication/336853704_Rib_Design_for_Improving_the_Local_Stiffness_of_Gearbox_Housing_for_Agricultural_Electric_Vehicles)
7. Guo et al. — *MDO Agent Driven by LLMs*, arXiv 2511.17511, 2025; LLM-driven parametric CAD
   including internal ribs, with an FEA loop. [link](https://arxiv.org/abs/2511.17511)
8. Lin et al. — *TO-Master: an LLM-agent framework for topology optimization*, arXiv 2607.01812,
   2026. [link](https://arxiv.org/abs/2607.01812)

No paper was found where an LLM agent proposes rib layouts for a casting specifically.

---

## 13. Could not verify

- nTop support pages returned HTTP 403 to direct fetches; block names and behaviour in §4 come
  from search-result excerpts that are consistent with each other.
- nTop's internal blend formula, and whether its CAD import is sampled on a grid.
- Whether fTetWild, TetGen and Netgen produce identical output across runs.
- Whether the conda-forge OpenVDB build ships the Python module on Windows (`import openvdb` not
  tried).
- The cause of the Windows block — Smart App Control is the likely policy; the policy itself was
  not inspected.
- Regeneration time per variant on this housing. A timing spike on the libraries that still load
  (gmsh surface mesh → embree/KD-tree distance field) did not complete; it will be re-run in
  whichever environment Q6 selects.
