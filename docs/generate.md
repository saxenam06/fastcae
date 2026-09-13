# Generate

**Being built.** The stage that produces design variants: how a design is represented, built,
turned back into a surface and checked. How the engineer's intent decides *what* is built -
variants, placements, Design a variant, the layout vocabulary - is in [ribs.md](ribs.md).
[status.md](status.md) says how much of it runs.

---

## What a design is

**The variants it holds and one value for each of their free settings, against a baseline**, and
nothing else. Geometry is never stored, only regenerated. Identical inputs produce an identical field and
surface bit for bit, which is the property the whole campaign rests on: two runs that differ must
differ *because the design differs*, not because something was rebuilt slightly differently in
between.

A design holds some of the variants its campaign takes - faces moved, walls, plates and bosses made
thicker or thinner; ribs and webs with their pads; holes cut through plates - and is cast in the
part's one material.

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
are fewer voxels across and come out approximate, held only to the fillet floor. A preview is twice
that; every preview of one campaign shares one grid - the one its designs are placed on, set by its
variants' suggested points - so a design that chose a smaller fillet is previewed coarser than its
own grid and held to its fillet only at full.

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

## Faces moved

A wall, a plate or a boss made thicker or thinner is its faces moved along their own normal - one
subtraction on the field:

```
phi = part - offset · weight
```

`weight` is one on the faces moved and nothing on the rest of the part, ramped between over the
block's blend: a point belongs to the faces moved by how much nearer it is to them than to any other
face, so a move never reaches through a wall to its far side. Moving further than the stored band
would drag a clamped number, so the part's distance is computed again, exactly, in a window round
the faces moved - out as far as they move, their blend and the band - and the move is made there.
Blocks that move faces near each other move them together: each window sees every block's weight.

**Interfaces stay as they are.** A cell within the clearance of a face kept closed - a bore, a
hole - and nearer that face than any face moved keeps its base value. The closed face stays exactly
where it is; what is added beside it meets it, so a boss thickened round a bore makes the bore
longer, never narrower, and leaves no groove. A block that would move a closed face itself is
refused.

Ribs standing on or ending at a moved face are filleted to the surface where it now is: their
blend reads the part's distance with the move taken off.

## Pads, and floors thickened

A rib is no thicker than the foundry's rule of thumb allows of the wall it meets - 0.8 of it,
assumed, a rule the engineer can take out. Where a rib ends on a wall, the wall is measured square
through it from where the rib meets it, with whatever the design moves its two faces by. A wall too
thin gets a **pad**: a plate along the wall, half in it, standing out as far as the rule needs,
as tall as the rib there and a good deal wider - never more than doubling the wall, a lump that
size being a hot spot. A pad is composed like a rib and filleted like one; the checks measure it as
wall, not as rib.

A **floor** too thin for the ribs standing on it - measured under each rib - is thickened for them
in that design: its faces moved, as a wall is, by what the thickest rib needs - never to more than
twice what it was - and every block placed after stands on it as thickened. Without pads, the rib
on a thin wall is left out, and a design whose ribs are too thick for their floor is screened out.

## Holes

A hole is a capped cylinder, square to the plate it goes through: from past the plate's face - past
any thickening of it - to a little past its far side, measured at the hole. Cutting is a maximum,
`max(part, −hole)`: metal stays where the hole is not. The hole's edge is sharp.

Holes go on a lattice - square, or staggered with every other row shifted by half, both a pitch from
each neighbour - laid from the middle of the plate at an angle. A point of the lattice is a hole
only if the hole keeps an edge distance inside the plate - from its outline, the foot of every wall
standing on it and every hole it has already - keeps a ligament of metal from what its variant keeps
clear of, from the footprints of ribs and the holes of variants placed before it, in three
dimensions, over the plate or under it, and stands over plain plate: the metal under its rim runs no deeper than under its middle,
else something stands under the plate there and the hole would cut into it. A lattice whose holes
would leave less than a ligament between them makes none, and says so.

## The order a design is built in

1. **Faces moved**, exactly, as above - the variants' own, and floors thickened for ribs.
2. **Ribs and pads**, composed together: each filleted to the part where it now is with its own
   variant's root fillet, and to each other where they cross with the smaller of theirs.
3. **Holes** cut.
4. **One recontour** of every cell any of these changed, spliced into the baseline's surface.

Before they are composed, the design is **mended** as it was when it was screened - the same
pieces left out - so the design built is the design screened. Then the checks, measured on the
part as moved - what the ribs stand on and end on - and what
screening found that the checks do not look at. The design's mass is its closed volume times its
material's density, from the catalogue.

## Screening

Placing a design takes a fraction of a second; building one takes a minute or more. So every design
a campaign places is **screened** on what placing it already knows, and only one that passes is
kept:

| screened for | rule |
|---|---|
| every variant made something | ribs where a variant adds ribs, holes where it adds holes |
| rib on floor | a rib no thicker than 0.8 of the floor it stands on, as the design leaves the floor |
| holes clear of ribs | a ligament of metal between each hole and the footprint of every rib it keeps clear of; a hole through any other rib is a warning |
| root gap | the clear gap between rib footprints standing in the open, past the junctions at their ends, at least the root gap - twice the thinner, or what the variant says - within a variant and between; and no wedge where two meet: no finger of sand narrower than the root gap for longer than it is wide, nor a lump that long where the fillets rounding their corner run them into one - wherever their bodies touch in the open, whether their lines cross there or in metal |
| wall kept | no wall thinned below the least its variant allows - or its material, when that is more |

**Clearance is measured from real metal.** A rib's footprint is half its thickness at the root and
its root fillet - or half its flange, where that reaches further - and everything kept clear of a
rib is measured from it: a hole, a face kept clear of, another rib, another variant's rib. Two ribs
**meet** where their bodies cross in the open; where only their fillets overlap, the sand between
them is a slot, and a gap too narrow like any other. Where two meet at an acute angle, the sand
between two of their arms is a **wedge**: rounded at its tip by the fillet, then widening; where it
stays narrower than the root gap for longer than the root gap is wide, it is a finger of sand no
mould holds. Spokes whose lines cross inside the boss they turn about meet in metal, and are held
apart where they stand in the open.

**The part's interfaces are kept clear in three dimensions, where the ribs are placed.** Every hole
and bore of the part, and whatever the drawing controls, is held for every variant, 5 mm clear.
Each rib and pad - its sides and top, the root fillet where it meets the floor, the ends buried in
what it meets - is measured against the space each hole or bore holds open, a cylinder as long and
as wide as its faces go, counterbores and chamfers included, and against the faces of anything else
held. A rib that would come nearer is not placed, and is drawn as reaching what the part keeps
closed, naming it: a bolt hole in the boss a rib ends on is as much in the way as a hole in the
floor. What the ribs run between is theirs to meet.

**What it weighs.** Each rib as the plate it is, each pad half of its plate, each hole through its
plate, each face moved by its area: an estimate to compare designs by, added to the base part's
exact volume, times the density of the design's material.

## Repair

What no variant sees alone is what its pieces do together - and a pattern can crowd itself. A
design whose pieces break a rule between them - ribs with no room for the sand between their
footprints, a wedge, a hole on a rib, an X crossing where a variant forbids one - is **mended by
CP-SAT**: each conflict a pair of pieces of which one must go, each crossing a point where at most
three arms may meet (a rib passing through gives two, one ending there one), and the fewest pieces
left out. A rib takes its pads with it; where two choices leave out as many, holes go before ribs.
One worker and a fixed seed, so the same design is mended the same way every time. The design says
what was left out, piece by piece, with the rule each broke, and their lines are drawn as left out.
What leaving pieces out cannot mend - a variant that made nothing, a rib too thick for its floor, a
wall thinned too far - the screening that follows rejects, and such a design is drawn again.

## Campaigns

A campaign is a **card**: its name, the variants it takes, the screening checks it holds, how designs
are drawn - spread evenly, at random, or every combination - how many to keep, from which seed, and
whether to keep more and choose the most different. Nothing else decides its designs. It never
narrows a variant: to hold a lever fixed, the variant is changed.

**Composed once.** The variants chosen become one study version: their blocks as they are - a
variant's block has the variant's code for its id - each variant's rules on its own block, the
part's interfaces once, and the rules that hold between variants without anyone writing them: holes
keep their ligament from every variant's ribs, placed after them; ribs of two variants keep the root
gap, which placing and repair see to. A rule naming a variant the campaign does not take is left
out.

**Counted.** How many designs the variants allow is `Π(1 + c) − 1` over their counts - every
non-empty set of them at every point of each - where a variant's count is, for each pattern and
section it may take, the values of every setting that makes a difference to it, multiplied; a
variant with free layouts among its patterns has no end. **Screen 100** draws a hundred designs as
the campaign would, places, repairs and screens them and keeps nothing: how many pass, how many
needed repair, why the rest do not, and how long a design takes - so how long the launch will.

- **Each variant alone.** Points of what it allows - its suggested point, then spread evenly by a
  scrambled Sobol sequence, drawn at random with every choice and every step of a range as likely as
  the next, or every point there is - each placed with nothing
  else, repaired and screened; the ones that pass are its pool, a quarter as many as the designs
  asked for and at most a thousand. Points that make the same design - settings its pattern does not
  use - are one point. How many passed of how many tried, and why the rest did not, is said per
  variant; one none of whose points passes stops the campaign with why.
- **Designs.** A set of the variants - its size spread evenly from one to all, so as many designs hold
  one variant as two or all of them - and a pool point of each: by Sobol, at random, or every
  combination in turn. Every variant of a design is placed at once, each after those it keeps clear
  of, repaired and screened; a design repair cannot save is drawn again. Designs alike in every rib,
  pad, hole and face moved are kept once; `n` are kept of at most `4n + 100` tried. Asked to keep the
  most different, `k·n` are kept and the `n` farthest apart chosen.

**What placing a variant reads off the part is read once**: where it stands, what it keeps clear
of, what its ribs end on - kept for every design. A variant placed alike before - the same values,
clear of the same things, on faces moved alike wherever placing it looked - is taken as it was. Ribs
of a variant placed later that would pass one placed earlier closer than the root gap are left out
as crowded.

**Every launch is kept beside the project**, in `_archived_designs/<project>/<id>-<name>/` - output,
not a decision, so not in the project folder: `campaign.json`, the card with the part's digest, the
code's commit, a copy of every variant as it was - each at its inside version - the seed and the
method; `study.json`, the composed version, which is all a campaign read back needs to place or build
any of its designs; `designs.jsonl`, a line a design - the variants it holds, its values, what each
made, how it screened, what it weighs, what repair left out, its recipe's hash and its own seed, and
everything it is made of in the part's coordinates; `paths.jsonl`, a line a design in the same
order - every stretch of path each variant tried and what became of it - so any design is drawn at
once, nothing placed again; `summary.json`, how many were tried, kept, repaired and dropped by what,
how each lever spread, how many distinct rib layouts there are and how far each design sits from its
nearest neighbour; and `built/`, each design built so far. The recipe is the part's digest, each
variant's inside version and the values the design took; its hash is the design's identity, and the
same card and seed give the same designs and hashes.

## A design's stages

Every design goes through the same stages, shown as letters: **P** its paths placed, repaired and
screened - every design a campaign keeps has passed; **F** its field built and checked; **M** meshed; **S** the
solver set up; **R** its results. Each shows how it came out - pass, warn or reject - or that it is
not reached. Thousands are looked at by the few that differ most - farthest-point sampling over what
each design is made of, each variant weighed alike and whether a design holds it one more of its
properties, so the first 20 of the 50 that differ most are the 20 that do - by those built, by those
holding one variant, or a page at a time.

**Building a design's field** makes it from the copy of the variants its campaign kept - only those
the design holds - at preview or in full, checks it, and keeps it beside the campaign in
`built/<index>-<fidelity>`: the verdict, the
surfaces it changes - new metal and metal taken away alike - in the format the part reaches the
browser in, and its new metal as the field's own cells. F stays done; nothing is built twice.

## Checks

Every design comes out pass, warn or reject, with the reason, the place, the rule used and where the
rule came from. Every check is shown to reject a part built to fail it before it is trusted.

| check | rule | outcome |
|---|---|---|
| protected areas unchanged | every cell in every protected band equals the baseline | reject |
| within the grid | no rib reaches the grid's outermost layer | reject |
| nothing floating | every piece of rib touches the part, directly or through other ribs | reject |
| rib thickness | inside the thickness its block allows, and at least 4 voxels; pads are not ribs | reject |
| rib against wall | thickness ≤ the rib-to-wall ratio × the wall under the root, a pad counted as wall | warn |
| root gap | clear gap between rib footprints, past their junctions and away from crossings, ≥ the ratio × thickness - each variant's own - and no wedge of sand where two meet | reject |
| root fillet | the radius achieved, read off the surface, ≥ the fillet floor | reject; warn if > 20% off its block's own |
| rib ends | each rib's end meets the metal ahead of it, or stops at least the root gap short - no finger of sand between | reject |
| blend bridging | fillet filling a gap to a surface the rib does not touch | warn |
| blend clipped | a fillet cut short by a protected area | warn |
| thick spots | a junction section more than the ratio × the wall beside it | warn |
| surface | closed and oriented, every edge in exactly two triangles | reject |

**The achieved fillet is read off the surface.** On a fillet the two distances satisfy
`(k − a)² + (k − b)² = k²`, so every contoured vertex on one says the radius it was built to:
`k = a + b + √(2ab)`, `R = k / (1 − n_a · n_b)`, `a` measured to the part's surface where the design
leaves it - a face it moved, where it moved it to. The median per rib, against the radius its block
asked for, and the rib furthest from its own is what is reported - grid error and all; a pad's edge
against its wall is no rib's root.

**Mould release waits for the pull.** Variants hold no pull direction, and a check that rejects any
metal along the pull from a rib's tip, however far, and does not know that cores form the pockets
inside a casting, rejected every design built on the housing. It comes back with the pull and with
cores.

**A part is cast in one material, which its designs do not change.** What they add, move and cut is
theirs to vary; the alloy of the whole part is not. It is assumed EN-GJS-400-18-LT until someone
says, and marked so; no variant changes it.

**What a rib keeps clear of is held as it is, as far as the clearance kept from it**: cells within
that distance of the feature come out exactly as the part had them, and a rib or fillet that would
reach into them is cut back, and said so. Each feature is held by its own clearance - a face a rib
must only not cross is not held at all, and a rib may meet it.

Thresholds come from the variants. **Each rib is held to its own variant**: the thickness its design
space allows, the root fillet it was made with and the root gap it keeps - never one variant's value
for every rib, nor a window its own design space goes past. The part's own rules - rib section,
root fillet, edge round, fillet floor - have no default; general rules of thumb (rib-to-wall 0.8,
root gap 2×, thick spot 2×, a hole's ligament one plate thickness, a wall no thinner than 8 mm)
apply until a variant replaces them and are marked *assumed* wherever they are shown. They are data, not code: `knowledge/materials.json`
holds each with its source, beside the catalogue of casting materials - grey and ductile irons, cast
steel, cast aluminium - each with its density, stiffness, strength and least wall, from its
standard.

## Looking at a field

A field can be looked at directly; a contour is a reconstruction of it and can be wrong in ways the
field is not. A built design's field is drawn in switchable layers - the **part** as its CAD
describes it, the **surfaces the design changes**, contoured, and its **new metal as cells** as
stored - because they occupy the same space and the only way to tell which is which is to turn one
off.

**The surfaces a design changes run down to the part.** A vertex of the design's surface has moved
when the part's own surface has none like it - none with its key, or one somewhere else - and every
triangle with a moved vertex is drawn, so what is drawn ends exactly on the part's own surface and a
rib's fillet reaches it. Each vertex carries how far it stands off the part - the change of the
field round it, read between its cell's eight samples: nothing where no sample changed, half a cell
or more wholly the design's - and the viewer blends the part's colour into the design's by it, a
hair nearer the camera than the part, so the join reads as metal joined.

Surfaces travel **indexed and welded by normal**, normals as three signed bytes. Cells travel as one
integer per visible face - only boundary cells, only the faces that show - which is forty times
smaller than the contour for the same picture, so cells are the default view.

## What simulation receives

For each design: a closed, oriented surface with every triangle tagged by the baseline CAD face
nearest it, so loads and supports can be placed; the field on the design grid, for a solve that
immerses the part rather than meshing it; its material; and its campaign's copy of its variants,
its values, its recipe and hash, and its verdict. How the part is then meshed or immersed is Simulate's decision.
