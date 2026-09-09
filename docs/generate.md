# Generate

**Being built.** The stage that produces design variants. This file describes the design it is
being built to; [status.md](status.md) says how much of it runs. The field is built and measured;
nothing above it is.

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

**Fillets fall out of the blend.** A smooth minimum with radius `k` joins two solids with a fillet
of radius `k`. That is the single global fillet control, and it is a property of the combine rather
than a feature anybody has to construct.

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

Two separate grids, and confusing them would be a mistake:

- the **field grid** at 2.5 mm, which decides what geometry can exist;
- the **placement grid** at 10 mm, which decides where a rib is allowed to sit. Coarse on purpose,
  because a continuous position turns every campaign into a search over near-duplicates.

### Building it, and why it is not rebuilt

The base field is built **once per CAD file** and cached against its content digest. Unsigned
distance is a triangle scan-conversion - each triangle writes exact point-to-triangle distances into
the cells near it and each cell keeps the smallest. The sign is then settled in two moves:
connectivity groups the cells more than half a voxel from the surface into regions that must share
an answer, and one ray per region says what that answer is. The cells straddling the surface get a
ray each.

Connectivity alone is not enough, and assuming it was cost two defects. A region that never reaches
the edge of the grid can be the material inside a wall **or the air inside a sealed cavity**, and
nothing topological separates them.

Per design, nothing about the base is recomputed. Parameters are analytic primitives evaluated only
on the cells they can reach, and only that region is re-contoured. That is what makes apply-and-see
interactive on a two-metre casting: the expensive part happens once and the cheap part is the only
thing a dial moves.

### Accuracy

Checked against shapes with closed-form answers rather than against the casting, because "is this
the right distance" is a question a sphere can answer exactly and a casting cannot.

On a sphere of radius 100 at an 8 mm voxel the signed distance is within **0.2 mm** everywhere in
the band - which is the faceting of the tessellated sphere, not the voxel size, because the
distance itself is computed exactly rather than sampled.

### Getting a surface back

**Dual contouring**, not marching cubes. Marching cubes cannot represent an edge inside a cell, so
every machined corner comes back rounded to the voxel - on a casting whose whole character is crisp
machined faces against soft cast ones, that erases the distinction the part is about. Dual
contouring places one vertex per cell where the surface's own planes intersect, and reproduces an
edge exactly.

The surface is for display and for measurement. The field is the design.

## Parameters

Every parameter is a person's or an agent's choice, authored on the geometry. **Nothing is
preloaded** - a fresh project has no parameters until someone puts one there.

### Ribs first

A rib is a rounded slab: a footprint on a host face, a height, a thickness, and the global blend
`k` where it meets the wall. Its distance function is closed-form, so unioning it is a few lines,
and unioning it onto the **production casting as it stands** means no ribs have to be stripped
first. That was the root of the quality problem in the previous system, and in a field it simply
does not arise.

`height` is the continuous dial. Footprint and thickness are authored once; height is what a
campaign sweeps.

### Face-set offset second

Select faces, push them along a direction. The atlas, the picking and `grow`/`similar` already
exist to author the selection. It lands second because offsetting an arbitrary subset of the
boundary means building a field for that patch and blending it into its neighbours, which is
genuinely harder than adding a primitive.

### Authoring is a task

An agent may propose parameters freely; a person confirms before one is saved. That is a
`confirm_parameter` task, ranked and queued like any other - see [tasks.md](tasks.md). Nothing an
agent produces becomes a parameter on its own.

## The loop

**Apply and see, first.** Set values, press apply, see the result in under a second, server-side.
Not a live slider: a live slider on a two-metre casting is a large investment for a demo effect,
and it buys no understanding that a sub-second round trip does not.

**Sample, second.** Fix the parameters, sample N designs across their ranges, and get a gallery.
This is the workflow that actually feeds a campaign, and the reason designs are stored as vectors:
a hundred variants is a hundred short rows, and any of them regenerates exactly.

## Validity

Three things are checked before a design is offered, because an invalid one poisons a campaign more
quietly than it fails:

- **Watertight by construction.** A level set of a continuous field is closed. There is nothing to
  gate, which is the point.
- **Minimum wall thickness**, measured on the field itself - the distance transform already holds
  it.
- **Controlled faces unmoved.** A face a drawing tolerances must not be within reach of any
  parameter. That check exists already and it is why `controlled` is derived rather than typed.

## Build order

1. `field.py` - the narrow-band signed distance field, cached against the CAD digest
2. `primitives.py` - the rib slab, and smooth-min with the global `k`
3. `design.py` - a design as a digest and a vector; deterministic regeneration
4. `surface.py` - dual contouring back to the face-tagged mesh the renderer already reads
5. the API routes and the Generate stage in the interface
