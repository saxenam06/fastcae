# Generate

**Being built.** The stage that produces design variants: how a design is represented, built,
turned back into a surface and checked. How the engineer's intent decides *what* is built - the
study, placements, the study card, the layout vocabulary - is in [ribs.md](ribs.md).
[status.md](status.md) says how much of it runs.

---

## What a design is

**A spec version and a set of lever values, against a baseline**, and nothing else. Geometry is never
stored, only regenerated. Identical inputs produce an identical field and surface bit for bit, which
is the property the whole campaign rests on: two runs that differ must differ *because the design
differs*, not because something was rebuilt slightly differently in between.

That is the failure being engineered out. Re-meshing each variant makes every response the sum of a
design effect and a discretisation effect, with no way to separate them, and a surrogate trained on
that learns the mesh as much as the part.

## The representation

The part is a **signed distance field on a fixed grid**. A design edits the field; the grid never
moves.

**Remesh variance becomes impossible**, not merely small. Every variant is sampled on the same grid
at the same points, so there is no discretisation difference between two designs to confound with
the design difference.

**Topology is free.** Adding a rib, merging two bosses, opening a passage - all the same operation
on a field. Nothing has to be re-parametrised, and no boolean can fail.

**A design is an exact function.** The baseline's distance comes from its field, or from its exact
extended distance near a rib; ribs and their fillets are analytic. The grid only matters when the
function is sampled, and the samples are then contoured.

### Resolution, and what it costs

Held as a **narrow band**: distance is stored only within a few voxels of the surface, and everything
beyond is a sign. A dense grid over the bounding box is never built.

Measured on the cast gearbox housing this was developed on - 1288.6 x 1378.7 x 690.0 mm, 9.2 m2 of
surface, filling a tenth of its own bounding box:

| voxel | dense grid | narrow band | error vs the B-rep | build, once |
|---|---|---|---|---|
| 20.0 mm | 0.3 M | 0.08 M | 2.84% | 48 s |
| 10.0 mm | 1.5 M | 0.40 M | 1.28% | 51 s |
| 5.0 mm | 10.1 M | 1.88 M | 0.60% | 80 s |
| **2.5 mm** | **74.5 M** | **8.70 M** | **0.22%** | **180 s** |

The rib-free baseline in `assets/` at 2.5 mm: 121,331 cm3 in the field against 121,301 cm3 from
tight B-rep integration, built in 158 s.

**The design grid is a quarter of the smallest root fillet** unless a grid is asked for: four voxels
across the radius a design must hold. An R10 root gives 2.5 mm. Free-edge rounds smaller than the root
are fewer voxels across and come out approximate, held only to the fillet floor.

A feature needs roughly **three voxels** across to exist in a field. At 2.5 mm a Ø21 hole is 8.4
voxels and is reproduced well; Ø8 is marginal; Ø4.2 is gone.

The field is built **once per CAD file and grid** and kept, keyed on the CAD's digest; nothing about
it is recomputed per design. Unsigned distance is a triangle scan-conversion: each triangle writes
exact point-to-triangle distances into the cells near it and each cell keeps the smallest. The sign
is settled by connectivity - cells more than half a voxel from the surface fall into regions that
must share an answer - and one ray per region, plus one per cell straddling the surface. A region
that never reaches the edge of the grid can be the material inside a wall or the air inside a sealed
cavity, and nothing topological separates them; the ray does.

**Voxel sizes offered are round numbers**, each labelled with whether it is built: a size nobody can
name is a size nothing is ever cached for.

## Back to a surface

**Simulation never needs one.** An immersed solve puts cells on the same fixed grid and asks each
how full it is, which is a field question.

Three things do need a surface: **checking** (volume, area, closure, the fillet actually made),
**handing over** (export, or a body-fitted mesh for a reference solver), and **selecting** (picking
a face runs against triangles carrying CAD face ids).

**Dual contouring**, not marching cubes. Marching cubes cannot represent an edge inside a cell, so
every machined corner comes back rounded to the voxel. Dual contouring places each vertex where the
surface's own planes intersect, and reproduces an edge exactly.

**Manifold.** A cell the surface passes through twice gets a vertex per piece of surface, read from
its corner signs. A face whose corners alternate carries two stretches of surface and is never
crossed directly: each stretch gets a vertex of its own on the face, and the quads through it become
small polygons fanned around their centres. It reads only the face, so it stays local. Random solids
by the hundred contour with no edge in more than two triangles; so does the housing, for a few
hundred extra vertices among 1.7 million. Self-intersections are not counted yet.

**The baseline is contoured whole, once; a design re-contours only what it changes.** A vertex
depends only on its own cell's eight samples, and a quad on the four cells around one lattice edge.
Every vertex carries a key - its cell and which piece of surface in it - and every triangle the key
of the lattice edge its quad sits on, both kept in key order. A splice re-places the vertices of the
cells a changed sample touches, rebuilds the quads on those cells' edges, and merges by key. Nothing
is joined by a mesh boolean, and the result is exactly what contouring the whole field gives: on
the housing, a grid of eleven ribs splices to the same bytes as a whole contour, in about a third
of the time.

**The edge of the grid is always outside.** Nothing is ever made solid on the grid's outermost
layer, so a design's surface always closes; a surface that reached the edge would end there, open.
A rib that gets that far has left the part or outgrown the room the grid was built with, and the
design is rejected with where.

## The rib

A rib is an exact distance function along its path: a plate of a given thickness, standing in the
direction its placement sets, its flanks drafted about the pull so it thins with height, its free
edges rounded at the edge-round radius. Where a placement ends it on a support, it runs a few
millimetres into the support so the junction is a fillet, not an edge. A rib on a circle is the same
section swept round an arc.

## The root fillet

A **round blend** between each rib and the part:

```
k = R · (1 − n_a · n_b)
d = max(k, min(a, b)) − ‖ max((k − a, k − b), 0) ‖
```

`a` and `b` are the distances to the part and to the rib, `n_a` and `n_b` their unit normals, `R` the
radius wanted.

- Where a rib stands square to a surface (`n_a · n_b = 0`), this is exactly a rolling ball of radius
  R. Where it meets at an angle, `k` is corrected by the local angle so the fillet touches both
  surfaces where the ball would; between those points the curve is close to, not exactly, circular,
  and the achieved-radius check measures it.
- It changes the field **only where both distances are below `k`** - at a junction. It returns the
  plain union everywhere else, exactly, so the part's own edges are never rounded and a splice sees
  only the cells near ribs as changed.
- Where ribs cross, they are joined to each other with the same radius before they are joined to the
  part.
- **The rib's normal is its own, exact**, evaluated in the strip within 2R of both surfaces. A normal
  taken by differences on the grid beside a root reaches into the part below, tilts, and grows the
  fillet - R13.7 for R10 on a test plate, against R9.55 exact.

The part's distance is needed out to the largest `k` plus a margin, well past the band. It is
extended there **once per region and kept**, by the same exact scan-conversion the field uses, along
with which cells are protected and which are open to ribs. A design then pays only for its own ribs.

## Protected areas

After blending, the field inside each protected area and its clearance is copied back from the
baseline, so protected surfaces come out byte-identical and the check proves it by comparing cells.
Protected areas are proposed from detected features - bores, holes, the faces a drawing controls -
each with a clearance, and a person approves them. A rib cut short by one is reported with where.

## Checks

Every design comes out pass, warn or reject, with the reason, the place, the rule used and where the
rule came from. Every check is shown to reject a part built to fail it before it is trusted.

| check | rule | outcome |
|---|---|---|
| protected areas unchanged | every cell in every protected band equals the baseline | reject |
| within the grid | no rib reaches the grid's outermost layer | reject |
| nothing floating | every piece of rib touches the part, directly or through other ribs | reject |
| rib thickness | inside the thickness window, and at least 4 voxels | reject |
| rib against wall | thickness ≤ the rib-to-wall ratio × the wall under the root | warn |
| root gap | clear gap between neighbouring ribs' flanks, away from crossings, ≥ the ratio × thickness | reject |
| root fillet | the radius achieved, read off the surface, ≥ the fillet floor | reject; warn if > 20% off |
| blend bridging | fillet filling a gap to a surface the rib does not touch | warn |
| blend clipped | a fillet cut short by a protected area | warn |
| mould release | draft within the window, and nothing of the part above a rib's tip along the pull | reject |
| thick spots | a junction section more than the ratio × the wall beside it | warn |
| surface | closed and oriented, every edge in exactly two triangles | reject |

**The achieved fillet is read off the surface.** On a fillet the two distances satisfy
`(k − a)² + (k − b)² = k²`, so every contoured vertex on one says the radius it was built to:
`k = a + b + √(2ab)`, `R = k / (1 − n_a · n_b)`. The median per rib, and the smallest of those, is
what is reported - grid error and all.

Thresholds come from the spec. The part's own rules - rib section, root fillet, edge round, fillet
floor - have no default; general rules of thumb (rib-to-wall 0.8, root gap 2×, thick spot 2×, draft
0-2°) apply until replaced and are marked *assumed* wherever they are shown.

## Looking at a field

A field can be looked at directly; a contour is a reconstruction of it and can be wrong in ways the
field is not. The Field tab draws three switchable layers - the **field cells** as stored, the
**contour** fitted through them, and the **geometry** they were built from - because two of them
occupy the same space and the only way to tell which is which is to turn one off.

Surfaces travel **indexed and welded by normal**, normals as three signed bytes. Cells travel as one
integer per visible face - only boundary cells, only the faces that show - which is forty times
smaller than the contour for the same picture, so cells are the default view.

## What simulation receives

For each design: a closed, oriented surface with every triangle tagged by the baseline CAD face
nearest it, so loads and supports can be placed; the field on the design grid, for a solve that
immerses the part rather than meshing it; and the spec version, lever values, digests and verdict.
How the part is then meshed or immersed is Simulate's decision.
