# Meshing from the field, checked against the real CAD

Two questions, measured on this workstation (i7-13700HX, 16 cores, 15.7 GB RAM, RTX 5060 Laptop 8 GB;
WSL with 12 GB). How fast can a design be meshed from its distance field, with the element sizes its
features need? And does meshing from a 3 mm field lose anything against meshing the CAD itself? A
design has no CAD - only its field - so the second is answered on the one part that has both: the
production housing with its ribs and fillets (`254492_0_closed_volume.step`), meshed four ways and
solved alike. September 2026; everything here measured. Scripts in `bench/solvers/`; the tables in
[../../bench/solvers/RESULTS.md](../../bench/solvers/RESULTS.md); the scripts' raw records are written
locally into `bench/solvers/results/`, not kept in the repository.

## In one table

The production housing, every mesh held to the same element sizes, the same seat and bolt labels,
solved by Code_Aster with agenticCAE's couplings; seat tilts as agenticCAE reads them, from the
rotation of each seat's reference node.

| | A - the CAD's surface | B - the 3 mm field | B2 - B meshed again | C - agenticCAE's route |
|---|---:|---:|---:|---:|
| BORE_AX1_S1 tilt | 0.399' | 0.427' | 0.396' | 0.481' |
| BORE_AX1_S4 | 1.193' | 1.206' | 1.194' | 1.207' |
| BORE_AX2_S2 | 0.873' | 0.901' | 0.876' | **0.407'** |
| BORE_AX2_S3 | 1.420' | 1.431' | 1.419' | 1.412' |
| BORE_MAIN_S2 | 1.843' | 1.835' | 1.794' | 1.707' |
| BORE_MAIN_S3 | 0.696' | 0.699' | 0.688' | 0.686' |
| IMS gear-mesh lead | -0.1233 mrad | -0.1234 | -0.1267 | -0.1207 |
| HSS gear-mesh lead | -0.3849 mrad | -0.3884 | -0.3876 | -0.4011 |
| p99.9 von Mises | 55.1 MPa | 54.9 | 53.7 | 54.1 |
| Largest displacement | 0.418 mm | 0.415 | 0.407 | 0.398 |
| Unknowns (TET10) | 1.19 M | 1.17 M | 1.17 M | 1.10 M |
| Mesh | 12.6 s | 7.9 s | 7.0 s | 17 s |
| Code_Aster solve | 2 min 25 s | 2 min 16 s | 2 min 17 s | 2 min 32 s |

- **A against B is what the grid costs**: every metric within what meshing the same field again moves
  it (B against B2) - so a 3 mm field is enough; 1.5 mm is not needed.
- **agenticCAE's route is not a reference on this housing**: it leaves out six CAD faces, lids their
  holes flat and cuts into metal under one bearing seat - half the tilt there, a fifth more on another.
- **At about 1.2 M unknowns the mesh itself is the largest noise**: meshing the same field again moves
  the smallest seat's tilt 7 %, element stresses about 18 %, single peaks up to 30 %.

## The words, plainly

- **CGAL's mesher (Mesh_3)** builds tets by asking a shape questions - is this point inside, where
  does this segment cross the surface. Asked of a design's field, the answer is read off the grid.
- **Compiled** - the questions answered in C++, inside CGAL, instead of calling back into Python for
  each of millions of them.
- **Size map** - the element edge length wanted at every point: small where a rule asks, up to a
  panel size elsewhere, growing gradually between.
- **Edge lines (features)** - lines the mesher must lay vertices along and connect, so the faces they
  bound come out exactly. CGAL keeps other vertices out of a small ball round each vertex on a line.
- **Labels** - which boundary triangles carry a seat's load and which are tied at a bolt.
- **Kinematic coupling (RBE2)** - a bolt hole's nodes moving as one rigid body about a held point.
  **Distributed coupling (RBE3)** - a seat's force spread over its nodes, every node weighted equally,
  its reference node's rotation read as the seat's tilt.
- **Noise floor** - the same shape meshed twice, only CGAL's random start changed: whatever the two
  answers differ by is noise of meshing itself, and no two meshes can agree better.
- **Snap** - moving a mesh's boundary nodes onto the CAD's surface after meshing.

## 1. The compiled mesher

`native/cgal_field/cgal_field.cpp`, built into the WSL environment `fieldmesh` (conda-forge: CGAL 6.2.1,
TBB, pybind11, a C++ compiler) by `native/cgal_field/build.sh`, driven by `mesh_cgal.py`. It holds the field
as an array and answers CGAL's questions by trilinear interpolation in C++; it can also mesh a closed
triangulated surface (`mesh_surface`), and both take a size map and edge lines.

**The surface was up to a millimetre off.** pygalmesh, the Python route, never set CGAL's
`relative_error_bound`, so CGAL located surface points to a thousandth of a box round a sphere about
the origin - 1,241 mm on the housing, so up to 1.07 mm. The compiled mesher sets it to 5·10⁻⁶ of the
grid's diagonal: boundary nodes within 0.005 mm of where the field is zero.

**On a sphere** (radius 50 mm, 3 mm grid): boundary nodes within 0.045 mm of the true sphere (the
default bound: 0.078 mm), no tet inside out, the same in parallel; a size grid honoured; the same
sphere as a triangulated surface meshed alike.

**On design #7**, at the old coarse settings (cells to 40 mm circumradius, facets 30 mm, facets within
2 mm of the surface):

| | Time | Tets | Unknowns | Worst dihedral angle | Surface off the field |
|---|---:|---:|---:|---:|---:|
| pygalmesh, questions in Python | 46 s | 157,358 | 905 k | - | up to 1.07 mm |
| compiled, one core, CGAL's sliver passes as they are | 17.6 s | 144,973 | 838 k | 10.0° | 0.005 mm |
| compiled, four cores | **4.4 s** | 146,309 | 844 k | 9.0° (77 tets under 10°) | 0.005 mm |
| compiled, one core, sliver passes stop at 10° | 7.8 s | 148,728 | 849 k | 10.0° | 0.005 mm |
| compiled, no sliver passes | 1.1 s | 151,749 | 858 k | 0.2° (1,839 slivers) | 0.005 mm |

Refinement itself takes about a second; the rest is CGAL's two sliver passes (perturb, exude), which
cannot be left out. On four cores with a stop at 12° two runs placed a few surface points 0.4-0.9 mm
off; the default passes on four cores do not.

## 2. Element sizes from the rules

`sizes.py` computes the size map from the field alone: the part's thickness at each surface point
along the inward normal to where the field turns positive again (the stored field holds exact
distances only 9 mm deep), a concave curve's radius from the field's second differences, then the
rules, spread into the volume growing so many millimetres per millimetre. `mesh_report.py` checks
each design's mesh against them: elements through ribs, elements round curves, the largest element,
quality, how far the boundary sits from the field.

**Calibration.** Held to a regular tet's circumradius for an edge length, CGAL's tets came out at 0.81
and its boundary triangles at 0.75 of the size asked; the bounds are set that much looser.

**What the rules cost, design #7** (15 ribs, 11 pads), in unknowns:

| Where the fine sizes go | Panels | Unknowns | Mesh |
|---|---:|---:|---:|
| every rib, fillet and hole of the housing (2 through ribs, fillets under half their radius, 16 round holes) | 20 mm | 44 M (before calibration) | 41 s |
| only where the design changes the part | 20 mm | 10.9 M (before calibration) | 48 s |
| only where it changes - 2 elements through its ribs | 20 mm | 2.00 M | 12 s |
| - plus fillets no longer than their radius | 20 mm | 2.65 M | 16 s |
| - the agreed rules, sizes growing faster | 20 mm | 2.73 M | 17 s |
| only where it changes - 2 through its ribs | 40 mm | 1.69 M | 9 s |
| - plus fillets no longer than their radius | 40 mm | 2.34 M | 17 s |
| - the agreed rules | 40 mm | 2.42 M | 13-19 s |
| **only where it changes - 2 through its ribs, sizes growing 1 mm a mm** | **40 mm** | **1.49 M** | **9-14 s** |
| - plus fillets no longer than their radius | 40 mm | 1.72 M | 10 s |

The fine sizes near a fillet (2-4 mm) spread 40 mm into the metal while growing 0.4 mm a millimetre;
most of the unknowns were there, not in the ribs.

**It moves the answer.** 2 elements through the design's ribs (1.49 M unknowns) against the coarse mesh
(0.84 M), same supports: worst tilt +2.8 %, largest displacement +6.4 %, p99.9 +4.7 %, p99 +8.2 % -
the coarse mesh was too stiff.

**It fits the card.** cuDSS solved the 1.49 M-unknown system, keeping part of its factor in host
memory: 10 s to factorise, 0.1 s to solve. Assembling and solving in one process the first time ran
the card out; the assembly now sums its pieces in host memory past 1.6 M unknowns. At 2.42 M the GPU
assembly ran out of memory and cuDSS failed (`EXECUTION_FAILED`) at 2.4 M.

## 3. The gate: the field against real CAD

### The part

The production housing, in a scratch project of its own - a test of the meshing route, never a
project's part or a source for designs. 2,167 CAD faces (the housing without ribs has 1,753). The
product's triangulation of it: 153,388 triangles, within 0.5 mm; the CAD's surface for reference:
578,366 triangles within 0.05 mm, after three pairs of identical, oppositely wound triangles
OpenCASCADE left in a fold were taken out. Its 3 mm field: 425 × 463 × 258 points, 101 s on the CPU.
The six seats and the flange's bolt holes found by geometry, as for every case. CAD volume
127,800.9 cm³.

### The four meshes

- **A - the CAD's surface.** The compiled mesher on the product's triangulation of the CAD - the shape
  the field is built from - with no grid between: 220,337 tets in 12.6 s. Letting CGAL find every
  sharp CAD edge itself ran past 15 minutes on one core and filled 9.5 GB at the 0.05 mm surface; on
  the 0.5 mm surface it also ran past 15 minutes. Given only the seat edge lines, it takes seconds.
- **B - the field.** The compiled mesher on the 3 mm field - the product's route: 216,439 tets in
  7.9 s.
- **B2 - B meshed again.** B run a second time with one thing changed: CGAL's random seed, 1 instead
  of 0 (`mesh_cgal.py gate3seed 40 30 2 --sizes sizes.npz --lines lines.npz --edge 8 --threads 4
  --seed 1`). The same field, size map, 12 seat circles and settings. The seed decides where CGAL puts
  its first surface points and the order it refines in, so the shape and sizes stay and the elements
  land elsewhere: 217,034 tets against 216,439. Four threads add a little run-to-run variation of their
  own. Then the same TET10, labels and solve as B - so whatever B and B2 differ by is the mesh itself.
- **C - agenticCAE's route**, its own code and settings (`src/fastcae/mesh/surface.py` in its
  repository): gmsh triangulates the CAD's faces - carrying on past those it cannot parametrise - the
  triangles are welded at 0.5 mm and their short edges collapsed at 3 mm, MeshFix closes the holes,
  gmsh fills the volume. 104,752 triangles in 10.6 s, 6 faces left out, 3 holes lidded flat (241.6,
  134 and 79 mm across), 204,091 tets and 57,214 nodes in 3.9 s - the size agenticCAE's 490 designs
  had. Worst element quality 6·10⁻⁵, 90 tets under 0.1; volume +0.49 %.
- **gmsh on the STEP directly** does not mesh it: with gmsh's own repair, "could not fix wire in
  surface 788" (and 865 after healing); without it, "the 1D mesh seems not to be forming a closed
  loop". agenticCAE's procedure works because it lets gmsh skip those faces.

### The meshes in numbers

Every mesh TET10 with straight mid-side nodes, counted from the meshes as solved:

| | A - CAD surface | B - field | B2 - field again | C - agenticCAE |
|---|---:|---:|---:|---:|
| Tets | 220,337 | 216,439 | 217,034 | 204,091 |
| Nodes | 398,008 | 390,296 | 391,152 | 367,329 |
| - of them corners | 62,520 | 61,228 | 61,326 | 57,214 |
| Unknowns, three per node | 1,194,024 | 1,170,888 | 1,173,456 | 1,101,987 |
| Boundary triangles | 105,054 | 102,600 | 102,726 | 97,456 |
| Nodes on the surface | 209,845 | 204,946 | 205,221 | 194,748 |
| - corners | 52,290 | 51,063 | 51,141 | 48,564 |
| - mid-side | 157,555 | 153,883 | 154,080 | 146,184 |
| Nodes on the six seats | 12,786 | 12,652 | 12,642 | 5,958 |
| Nodes on the bolt holes | 4,543 | 4,411 | 4,335 | 5,424 |

More than half of every mesh's nodes lie on the surface: the walls are one or two elements thick.

### Held alike

- **Sizes.** Every mesh held to the element sizes of agenticCAE's own mesh of the part, read off it
  point by point (`sizes_from_mesh.py`): tet edges 10-26 mm (5th to 95th percentile), median 19 mm;
  1.1-1.2 M unknowns each.
  Rules written for the gate first - 2 elements through all thin metal - gave 2.4 and 2.9 M
  unknowns; Code_Aster then wanted more than WSL's memory, spilled to disk and crawled. Rules cannot
  copy how gmsh grades from the CAD's own faces - its elements shrink to a narrow face's width and 7
  round every circle - so the sizes were taken from its mesh instead.
- **Seat edge lines.** Each seat's two edge circles (12 lines) given to the mesher, vertices 8 mm
  apart. The spacing matters: at the element size (about 18 mm) the balls round the line vertices
  kept the mesher off the 10 × 12 mm shoulder under seat AX2_S2 and cut it off; at 3 mm the seats
  came out 4-9 times denser than C's (10,918 nodes on MAIN_S2 against 1,207) - and Code_Aster's
  distributed coupling wanted 8.2 GB for it, past its limit, its memory growing with the square of
  the seat's nodes; at 8 mm the shoulder is kept and the seats hold 1.5-3 times C's nodes. The bolt
  holes' 142 circles as well doubled the mesh (408,289 tets) and were left out: B's bolt holes
  already matched A's.
- **Labels.** A boundary triangle is a seat's, or a bolt hole's, when its middle is nearest that CAD
  face and every corner lies within 2 mm of it. Labelled by the nearest face alone, triangles
  straddling a seat's edge counted in (C's seat AX2_S2 ran from z = 100 mm instead of 114); by
  corners within 1 mm of the cylinder, B's seats came out 11-26 % short where the grid rounds their
  edges. With the edge lines and this rule, every seat's area is within about 1 % of its CAD face in
  A and B, within 4 % in C; the bolt holes 97,594 mm² in A, 97,062 in B, 115,551 in C.
- **Solve.** Code_Aster 18 with agenticCAE's couplings, MUMPS with block low-rank: 2-2.5 minutes and
  4.2-4.5 GB each.

### What differs where

A cut through the AX2 shaft's axis under seat S2 ([the section](../../bench/solvers/results/gate/section_ax2.png)): the seat's bore,
radius 90 mm, stands on a shoulder stepping in to 80 mm, 12 mm tall, over a fillet and a 5 mm lip at
one side. B follows the CAD there at every angle cut. C's repair cuts 15-24 mm into the metal on one
side - where it is 53 % below A on that seat's tilt.

Where each mesh leaves the CAD surface by more than 1.5 mm (`gate_geometry.py`): C misses CAD surface
by up to 24.6 mm under seat AX2_S2 (a 2 mm-tall torus face and the 80 mm bore below the seat), 16.5
and 8.7 mm near it, and 2-3 mm along a wall; B, before its edge lines were spaced right, missed that
shoulder by up to 15.6 mm, and misses about 2-3.6 mm on sharp-edged detail along one wall - the grid
rounding edges.

### Against the pass marks

| | A vs B - the grid | B vs B2 - meshing's noise | A vs C - agenticCAE's route | Mark |
|---|---:|---:|---:|---:|
| Tilts, worst seat | 7.0 % (AX1_S1) | 7.2 % (AX1_S1) | 53 % (AX2_S2) | 3 % |
| Tilts, other seats | within 3.5 % | within 3.2 % | 20 %, 7 %, then within 1.5 % | 3 % |
| Gear-mesh leads | 0.1 %, 0.9 % | 2.7 %, 0.2 % | 2.1 %, 4.2 % | 3 % |
| p99.9 von Mises | 0.3 % | 2.3 % | 1.9 % | 5 % |
| Displacement map | 1.2 % | 2.1 % | 3.8 % | 3 % |
| Stress map, element by element | 17.4 % | 17.7 % | 19.6 % | 10 % |
| Ten highest peaks | -31 to +13 % | -32 to +14 % | - | 10 % |

The field against the CAD misses the marks on the worst seat's tilt, the stress map and the peaks -
by the same amounts meshing the same field twice moves them. The marks there are tighter than a mesh
of this size holds, whichever route made it.

**Snapping** B's and A's boundary nodes onto the CAD's surface - corners to the nearest point, mid-side
nodes to the nearest point to their edge's middle, eased back where an element would fold
(`snap_to_cad.py`) - made the two shapes the same (every seat within 0.5 % of each other) and moved
nothing that matters: the worst tilt 7.0 → 6.4 %, the rest as before. It distorted elements at curved
places instead - the stress map 27 %, the peak 16 % apart - and one snapped mesh failed in Code_Aster
(`ALGORITH2_59`). Snapping is not used.

## What it means

- **A design meshes from its 3 mm field as well as the CAD itself would**, in 8-14 s, surface within
  0.005 mm of the field, and needs no CAD.
- **Two things make that true**: the edges of the faces loads and supports go on, given to the mesher
  as lines with vertices about 8 mm apart; and labels that take a triangle only when its corners lie
  on the face.
- **agenticCAE's procedure changes this part's geometry** - six faces left out, lids up to 242 mm, a
  repair cutting into metal - and its answers on two seats move 20-53 %. Its 490 designs rest on it.
- **Mesh size, not route, now limits accuracy.** At about 1.2 M unknowns the same shape meshed twice
  differs by up to 7 % on the smallest seat's tilt and 18 % on element stresses: the noise in every
  label the dataset will carry. Finer elements where a design changes the part - 2 through its ribs -
  reduce it where the data varies.

## What each tool needed on this machine

- **cgal_field**: TBB's allocator linked (`-ltbbmalloc`) for the parallel mesher; a Surface_mesh built
  from a triangle soup only after the soup is oriented, which splits vertices where two sheets touch;
  a closed surface.
- **CGAL's sliver passes** hold most of the time; a stop angle shortens them.
- **Code_Aster 18**: its distributed coupling's memory grows with the square of a seat's nodes; past
  its limit it stops (`JEVEUX_62`) rather than spilling.
- **gmsh**: `General.AbortOnError = 0` or it stops at the first face it cannot parametrise; its own
  healing cannot fix this STEP.
- **libigl's nearest-point query**: the triangle truly nearest, where a CAD triangulation's triangles
  run hundreds of millimetres and their centres say nothing.
