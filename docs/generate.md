# Generate

**Being built.** The stage that produces design variants. This file describes the design it is
being built to; [status.md](status.md) says how much of it runs.

The representation is built and measured - the field, the contour, and three ways of looking at
both against the CAD they came from. Ribs are placed in formations - spokes, webs and grids on a
rib-free baseline, with true root fillets - and every design comes back checked; how, and what it
measures on the part in `assets/`, is in [rib-layouts.md](rib-layouts.md).

---

## What a design is

A **parameter vector against a base geometry**, and nothing else:

```
design = (CAD content digest, [p0, p1, ... pn])
```

Geometry is never stored, only regenerated. Identical values produce an identical field bit for
bit, which is the property the whole campaign rests on: two runs that differ must differ *because
the design differs*, not because something was rebuilt slightly differently in between.

That is the failure being engineered out. Re-meshing each variant makes every response the sum of a
design effect and a discretisation effect, with no way to separate them, and a surrogate trained on
that learns the mesh as much as the part.

## The representation

The part is a **signed distance field on a fixed grid**. A design edits the field; the grid never
moves.

Three things follow, and they are the reasons for choosing it:

**Remesh variance becomes impossible**, not merely small. Every variant is sampled on the same
grid at the same points, so there is no discretisation difference between two designs to confound
with the design difference.

**Topology is free.** Adding a rib, merging two bosses, opening a passage - all the same operation
on a field. Nothing has to be re-parametrised, and no boolean can fail.

**Fillets fall out of the blend.** Joining two solids with a blend rounds the junction by itself;
it is a property of the combine rather than a feature anybody has to construct. The blend built
today is a smooth minimum with one global `k`, capped at the band's reach because past the band a
cell knows only which side of the surface it is on. Rib formations use a round blend instead,
applied only where a rib meets the part and true to its radius, with the baseline's distance
extended past the band where ribs can reach - see
[rib-layouts.md](rib-layouts.md#the-root-fillet).

### Resolution, and what it costs

Held as a **narrow band**: distance is stored only within a few voxels of the surface, and
everything beyond is a sign. A dense grid over the bounding box is never built.

Measured on the part in `assets/` - 1288.6 x 1378.7 x 690.0 mm, 9.213 m2 of surface, filling
10.4% of its own bounding box, tessellated to 153,388 triangles:

| voxel | dense grid | narrow band | solid | field volume | error vs the B-rep | build |
|---|---|---|---|---|---|---|
| 20.0 mm | 0.3 M | 0.08 M | 0.02 M | 124,288 cm3 | 2.84% | 47.9 s |
| 10.0 mm | 1.5 M | 0.40 M | 0.13 M | 126,283 cm3 | 1.28% | 51.3 s |
| 5.0 mm | 10.1 M | 1.88 M | 1.02 M | 127,150 cm3 | 0.60% | 80.0 s |
| **2.5 mm** | **74.5 M** | **8.70 M** | **8.17 M** | **127,631 cm3** | **0.22%** | **179.8 s** |

**2.5 mm is the working resolution.** The band is 8.70 M cells, about 35 MB at four bytes - the
dense column is what makes fine fields look unaffordable, and it is the column nobody pays.

0.22% is close to the floor rather than to a target: the B-rep's own volume and its own
tessellation already disagree by 0.117%, because three faces carry a malformed analytic area. The
field cannot be more right about this part than the part is about itself.

Three minutes is a one-time cost per CAD file, cached against its digest. It is not paid again by
any design.

The limit is real and stated rather than discovered later: a feature needs roughly **three voxels**
across to exist in a field. At 2.5 mm a Ø21 hole is 8.4 voxels and is reproduced well; Ø8 is
marginal; Ø4.2 is gone. Where a design has to preserve small holes exactly, the base B-rep is still
there to carry them - but that is a later refinement, not this build.

Where a rib sits is not a grid of positions. It comes from its formation's levers, each with a step
the values snap to - coarse on purpose, because a continuous value turns every campaign into a
search over near-duplicates. See [rib-layouts.md](rib-layouts.md#formations).

### Building it, and why it is not rebuilt

The base field is built **once per CAD file** and kept, keyed on the CAD's digest and the voxel
size; the contour is kept against the field it came from. See the cache in
[architecture.md](architecture.md).

Measured on the part in `assets/`, a restart followed by opening the Field tab:

| voxel | field | contour | cells | cold |
|---|---|---|---|---|
| 10 mm | 0.01 s | 0.01 s | 0.02 s | 62 s + 1 s |
| 5 mm | 0.03 s | 0.02 s | 0.11 s | 144 s + 3 s |
| 2.5 mm | 0.18 s | 0.07 s | 0.72 s | 287 s + 26 s |

**Voxel sizes are round numbers, and the interface says which are built.** Offering one derived
from the part put 2.37 mm behind a button that looked like the others, matched nothing already
cached, and cost five minutes for the field and hours for the contour. A size nobody can name is a
size nothing is ever cached for.

Unsigned distance is a triangle scan-conversion: each triangle writes exact point-to-triangle
distances into the cells near it and each cell keeps the smallest. The sign is then settled in two moves:
connectivity groups the cells more than half a voxel from the surface into regions that must share
an answer, and one ray per region says what that answer is. The cells straddling the surface get a
ray each.

Connectivity alone is not enough, and assuming it was cost two defects. A region that never reaches
the edge of the grid can be the material inside a wall **or the air inside a sealed cavity**, and
nothing topological separates them.

Per design, nothing about the base is recomputed. Parameters are analytic primitives evaluated only
on the cells they can reach, which is a few tens of thousands of cells for a rib rather than
millions. That is what makes apply-and-see affordable: the expensive part happens once, and a dial
moves only the cheap part.

**The baseline is contoured whole, once; a design re-contours only what it changes.** Measured,
the whole part takes 26 s at 2.5 mm, and a design has to come back in about two. A patch joined to
the rest by a mesh boolean would be the fragile step every such pipeline has - coplanar faces,
slivers, floating-point ties - and a boolean that leaks fails the watertightness gate outright.
That is not what happens here. On the same grid dual contouring is local: a cell whose samples did
not change yields the same vertex bit for bit, so a re-contoured window's edge is the baseline's
own vertices and the window drops in by index. Nothing is joined, and the tests hold a splice to
exactly the bytes a whole-field contour gives - see
[rib-layouts.md](rib-layouts.md#contouring-only-what-changed).

### Accuracy

Checked against shapes with closed-form answers rather than against the casting, because "is this
the right distance" is a question a sphere can answer exactly and a casting cannot.

On a sphere of radius 100 at an 8 mm voxel the signed distance is within **0.2 mm** everywhere in
the band - which is the faceting of the tessellated sphere, not the voxel size, because the
distance itself is computed exactly rather than sampled.

### Looking at a field

**A field can be looked at directly.** It does not have to be turned into a surface first, and a
contour is not the field - it is a reconstruction of one, and it can be wrong in ways the field is
not.

The interface draws three layers, each switchable, because two of them occupy the same space and
the only way to tell which is which is to turn one off:

| layer | what it is | to send | to draw, each frame |
|---|---|---|---|
| **field cells** | the cells as stored. The field itself | 0.4 / 1.8 / 7.2 MB | 0.7 / 2.7 / 10.8 M vertices |
| **contour** | the surface fitted through them. A reconstruction | 5.2 / 20.0 / 79.8 MB | 0.7 / 2.7 / 10.8 M vertices |
| **geometry** | the tessellated B-rep it was all built from | 4.3 MB | 0.5 M vertices |

Both surfaces are **indexed and welded by normal**. Sending three separate corners per triangle
says everything three times - 10.8 million vertices for the 1.8 million a 2.5 mm contour has, and
303 MB for what fits in 80. Vertices are shared wherever they agree about which way the surface
faces, which is where they can be: a machined edge has two normals at one point and needs two
vertices, a smooth wall needs one. Welding on position alone rounds every edge off; not welding at
all costs four times the bytes for the same picture. Normals ride as three signed bytes, which is
under a degree of direction for a third of what floats cost.

Two things keep the cells cheap, and the second is not optional.

**Only the boundary**, because the interior is solid and hidden. **And only the faces that show** -
a cell has six and you see at most three, so drawing a whole cube each is six times the work for
the same picture. On a 2.5 mm field that is the difference between 48 million vertices a frame and
10.8 million, which is the difference between a browser drawing it and a browser stopping.

Each face is one integer - the cell's index and which way it points - and the grid it indexes into
travels once as a uniform. Four bytes a face against twelve for a position, so the payload is
**forty times smaller than the contour** while drawing the same amount. That is why the cells are
the default view and the contour is loaded on request.

Two more views are worth having and are not built: **slices**, which show the actual numbers on a
plane and are cheaper still, and **ray marching**, which draws the surface per pixel with no
geometry at all.

### Getting a surface back, and what for

**Simulation never needs one.** An immersed solve puts cells on the same fixed grid and asks each
how full it is, which is a field question. It sees no triangle, no contour and no boolean.

Three other things do need a surface:

- **Checking.** Volume, area and watertightness are measured on one.
- **Handing over.** Export, or a body-fitted mesh for whatever is used as the reference solver.
- **Selecting.** Picking a face to author a parameter on runs against triangles carrying CAD face
  ids. A ray-marched view is prettier and has nothing to click.

That last one is why contouring comes before the other two views despite being the most work: it
keeps the picking, the selection tools and the controlled-face highlighting that already exist.

**Dual contouring**, not marching cubes. Marching cubes cannot represent an edge inside a cell, so
every machined corner comes back rounded to the voxel - on a casting whose whole character is crisp
machined faces against soft cast ones, that erases the distinction the part is about. Dual
contouring places one vertex per cell where the surface's own planes intersect, and reproduces an
edge exactly.

## Parameters

Every parameter is a person's or an agent's choice, authored on the geometry. **Nothing is
preloaded** - a fresh project has no parameters until someone puts one there.

### Ribs

Ribs are generated, not placed one at a time. A formation - spokes, a web, a square or triangle
grid - draws lines across a zone; each becomes a rib with a thickness, a height, a draft and rounded
free edges, grown on a baseline with the production ribs removed - in CAD, where removing a face is
reliable, because a formation can only vary ribs it owns. The point is range: many kinds of
formation, each set by a few levers, to be compared once they are simulated. Designed in
[rib-layouts.md](rib-layouts.md).

The first version - one rounded slab on a face selection, its height the dial, joined by the
global blend `k` - is still in the API and gone from the interface. It returns as the manual
formation.

### Face-set offset

Select faces, push them along a direction. The atlas, the picking and `grow`/`similar` already
exist to author the selection, and `offset.py` computes it, unwired. It is parked: the rib layouts
keep the walls as they are.

### Authoring is a task

An agent may propose parameters freely; a person confirms before one is saved. That is a
`confirm_parameter` task, ranked and queued like any other - see [tasks.md](tasks.md). Nothing an
agent produces becomes a parameter on its own.

## The loop

**Set, then generate.** Pick a formation, set its levers, press Generate, and see the design and
its checks in a few seconds. The design updating while a lever is dragged is later work.

**Sample, second.** A seeded list of designs, built by a script that writes a summary table. This
is what feeds a campaign, and the reason designs are stored as settings: a hundred variants is a
hundred short rows, and any of them regenerates exactly - entering its values in the stage shows it.
Launching a campaign from the interface comes later.

## Validity

Three things are checked before a design is offered, because an invalid one poisons a campaign more
quietly than it fails. The full set for rib layouts - each pass, warn or reject with its reason - is
in [rib-layouts.md](rib-layouts.md#checks).

- **Watertight.** A level set of a continuous field is closed; its contour has to be made manifold
  to stay so. With a vertex per piece of surface in each cell, and a vertex of its own for each
  stretch across a face whose corners alternate, the part in `assets/` contours at 2.5 mm with no
  edge in more than two triangles - it had 64.
- **Minimum wall thickness**, measured on the field itself - the distance transform already holds
  it.
- **Controlled faces unmoved.** A face a drawing tolerances must not be within reach of any
  parameter. That check exists already and it is why `controlled` is derived rather than typed.

## Build order

Done:

- `field.py` - the narrow-band signed distance field, cached against the CAD digest
- `surface.py` - dual contouring the whole field back into triangles. No patching, no seam, no
  mesh boolean, and therefore no dependency for one
- `cells.py` and `shading.py` - the field drawn as itself, and a contour lit as one surface
- the Field tab: three layers, each switchable, each priced
- `primitives.py` - the rib as a rounded slab with an exact distance function, and the smooth
  minimum the fillets come out of
- `design.py` - a parameter, a design as a digest and a vector, and evaluation confined to the
  cells a parameter can reach. About ten milliseconds a move on the part in `assets/`
- `corrections.py` - a baseline trimmed to its reference, applied once a person approves it
- manifold dual contouring, and re-contouring only the cells a design changed
- `ribs.py`, `formations.py`, `zones.py`, `compose.py`, `checks.py`, `designs.py` - ribs in
  formations inside approved zones, with round-blend root fillets, checked and measured
- the Generate tab: approve zones and protected areas, pick a formation, set its levers, Generate
- `fastcae designs` - a seeded list of designs and a summary table

Next is in [status.md](status.md).
