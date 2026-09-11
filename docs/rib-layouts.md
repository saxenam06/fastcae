# Rib layouts

**Built** on 2026-09-11, the day it was designed. How Generate places ribs on a rib-free
baseline in many different
**formations** (spokes, webs, grids), the way nTop does it. The lines of a formation become ribs,
the ribs join the part through a blend that rounds their roots, and protected areas come back
exactly as they were. [generate.md](generate.md) describes the representation this is built on;
[status.md](status.md) says what runs.

**The goal is range, not a copy of production.** Many kinds of formation, each set up by a few
levers, so that once designs are simulated their effect on the part can be compared.

Agreed in a design review and built the same day. Where the build departed from the design, or
found the design wrong, the text says so; [What we learned](#what-we-learned) collects those
findings, and [Measured on the housing](#measured-on-the-housing) the numbers.

---

## In one paragraph

A design is a short settings file against a baseline. For each **zone** of the part it names a
**formation** and its **levers**. The formation draws a pattern of lines across the zone, and each
line becomes a **rib**: a plate with a thickness, a height, a draft and rounded free edges. Each rib
is an exact distance function. It is trimmed to the air of its zone, then joined to the part through
a **round blend**, which makes a true root fillet where rib meets metal and changes nothing anywhere
else. **Protected areas** are then copied back from the baseline. Every design is checked and comes
out pass, warn or reject, always with a reason. Only the cells the ribs changed are re-contoured, so
a design costs seconds and its surface is byte-identical every time it is rebuilt. In the Generate
stage a person picks a formation, sets its levers, presses Generate, and sees the new design and its
checks.

```
formation + levers ─▶ lines ─▶ ribs, trimmed to the zone ─▶ round blend into the baseline
                   ─▶ protected areas back ─▶ re-contour only what changed ─▶ checks ─▶ shown
```

## Scope

In scope:

- four formations: **spokes**, **web**, **square grid** and **triangle grid**, in zones given as
  project data
- **castable ribs only**, extruded along the zone's pull direction and drafted about it. Changing
  orientation means rotating, spacing or skewing the pattern. It never means tilting a rib out of the
  pull direction.
- root fillets, rounded free edges, and blends where ribs cross
- checks on every design, each with its reason
- **levers in the Generate stage**: pick a formation, set its values, press Generate, see the new
  design and its checks
- a script that builds a seeded list of designs from the command line and writes a summary table
- a watertight, tagged surface per design, as the hand-over to whatever simulates it

Out of scope, and where each goes:

| out | where it goes |
|---|---|
| rebuilding the production ribs | not a goal. The generator is proved on test shapes whose answers are known |
| physics: screening or accurate solves | its own plan, after this one. It is what compares the formations |
| launching a campaign from the interface; the agent drafting settings | the campaign plan |
| browsing many designs at once: a designs list, flipping, thumbnails, sweeps | not planned |
| the design updating while a lever is dragged | later, once timings show where the time goes |
| crossed (X-braced) and honeycomb formations | later. Each is one more function that draws lines |
| placing a single rib on a face selection | later, as the manual formation |
| ribs tilted off the pull direction | a labelled printed-sand-mould mode, later, and never ranked alongside castable designs |
| formations on flat walls, conformal to curved walls, or following stress | later. They produce the same lines, so nothing downstream changes |
| changing wall thickness (face-set offset) | parked. Walls do not change in this plan |
| exporting a design as STEP | not planned. A design worth making is rebuilt in CAD by hand and checked again there |

## How nTop does it, and what each step becomes here

| nTop (Rib Design, 5.10) | here |
|---|---|
| `Graph on Quad Mesh` / `Graph on CAD Face`: a pattern of lines laid on the part | a formation draws lines across a zone |
| `Ribs from Graph`: height, thickness, direction and draft, each one drivable | the rib: one exact distance function per line |
| `Boolean Union` with a blend radius; `Blend Intersections` | the round blend, between rib and part and between ribs |
| passive regions; functional faces added back after the boolean | protected areas, copied back from the baseline after blending |
| one JSON input per design to nTopCL | one settings file per design |
| mesh from the implicit body, then remesh for FEA | contour on the fixed grid. Meshing is the physics plan's decision |

nTop remeshes every variant before it simulates one. The field removes the boolean and the fillet
operation, which are the steps that fail. It does not remove meshing.

---

## The pieces

### Project data

The project folder gains one file, `project.json`. The system writes proposals into it, and a
person approves them. It holds everything specific to the part, so that code holds none of it:

| entry | what it holds | where it comes from |
|---|---|---|
| roles | which CAD file is the **baseline** and which the **reference** | a person |
| corrections | changes made to the baseline before anything grows on it | proposed from comparing baseline and reference, approved |
| density | for mass | derived where a drawing states a mass, otherwise assumed |
| spacing | the grid spacing designs are delivered at | derived: the smallest root fillet radius ÷ 4, rounded down to an offered size |
| rules | casting rules: thickness and draft windows, root fillet, edge round, gaps | assumed unless a source says otherwise, each labelled |
| protected areas | faces nothing may touch, and a clearance around them | proposed from detected features, approved on a picture |
| zones | where ribs may exist: region, levels, pull direction | proposed from reference − baseline, approved on a picture |
| levers | per formation: bounds and step | defaults taken from the rules |

Every entry carries its evidence the way every other fact does (`provenance.py`). An assumed
casting rule reads *assumed* wherever it is shown. A rule taken from a drawing cites the drawing.

This changes a decision in force, *"Configuration: none — no manifest, nothing written by hand"*.
Which file is the baseline is a role, and a role cannot be derived from geometry. Approvals also
have to be written somewhere. What stays true is that nothing enters the file silently: the system
proposes and a person confirms. `assets/` is not tracked, so the file lives beside the CAD it
describes and is backed up the same way.

### Baseline and reference

- The **baseline** is the CAD every design grows from. Extract, the field and the contour are built
  on it.
- The **reference** is optional: another version of the same part. When there is one,
  `reference − baseline` is material a person removed, which proposes where zones go.

A `.brep` reader joins the STEP reader. It keeps the solid and reports anything else the file
carries, such as loose edges. Extract stops taking whichever CAD file sorts first.

**A baseline may not add material the reference lacks.** Removing a feature in CAD sometimes leaves
a patched surface that bulges past the original one. When the baseline is meant as a pure removal,
the correction trims it to the reference, `φ = max(φ_baseline, φ_reference)`, which is exact: the
reference carries the true surface at exactly the places the patch got wrong. It is proposed with
the volume it removes, and applied only once approved.

This is also why a feature that is still in the baseline cannot be removed in the field. Removing
it would need the surface underneath it, and neither file has that surface.

### Zones

A zone is where ribs may exist. It has:

- a **region**: for the first study, an arc of an annulus about a detected axis
- **levels** along the pull direction: a **host face** the ribs grow from, or two levels they span
  between
- a **pull direction**: the mould opens along it, and ribs are extruded along it
- the **air** it contains

A zone is proposed from the reference. Each connected cluster of removed material becomes the arc,
radial band and levels about the nearest detected axis that hold it. Its air is found once, by
flooding outward through empty cells from where the removed material was, staying inside the arc
and levels. A person approves the zone on a picture before any lever for it exists.

The air is what makes any pattern safe. A formation's lines run across the whole zone, and each rib
is trimmed to the zone's air plus a small depth into the surrounding metal, so the joint has no gap.
The flood never crosses a wall, so a rib can never poke through one to the outside.

### Formations

A formation turns its levers into a set of line segments in the zone's plane, square to the pull
direction. Every segment becomes one rib.

| formation | its own levers | the lines it draws |
|---|---|---|
| **spokes** | count N, phase φ, skew ψ | N lines across the arc, evenly spaced, each leaning ψ off radial. With skew it becomes a pinwheel |
| **web** | spoke count N, phase φ, hoops H | N spokes plus H circular hoops at evenly spaced radii, spanning the arc |
| **square grid** | spacing s, angle α, offset o | two families of parallel lines, at α and α + 90° |
| **triangle grid** | spacing s, angle α, offset o | three families, at α, α + 60° and α + 120° |

Every formation also takes **thickness** t and **height** h, shared by all its ribs.

Spoke i of N across an arc from θa to θb sits at `θa + (i + φ) · (θb − θa) / N`. A grid is laid in
a frame centred on the zone's axis, turned by α and shifted by o · s.

After trimming, a piece shorter than twice its thickness is dropped. The report says how many pieces
were dropped and where, so nothing disappears silently.

**Every lever has a step, and values snap to it.** A design's digest then stays stable, and a
sample cannot fill a campaign with designs that differ by a hundredth of a degree. This does the job
the 10 mm placement grid in [generate.md](generate.md) was meant to do: placement comes from a
formation's levers, so there is no grid of positions.

Adding a formation, whether crossed, honeycomb, or one that follows stress, means adding one
function that draws segments. Nothing downstream changes.

The face-pick rib flow in the Generate stage today is removed when the formations arrive, so the
stage has one way of making ribs rather than two. It returns later as the manual formation.

### The rib

A rib is an exact distance function built from its segment:

- **Section**: a plate of thickness t, extruded along the pull direction.
- **Height**: from the zone's host face by h × the zone's depth, or from the lower of its two
  levels by h × the span between them.
- **Draft**: the flanks taper about the pull direction, so the rib gets thinner with height.
- **Free edges**: rounded, at the edge-round radius.
- **Extent**: the segment runs across the zone, and the rib is trimmed to the zone's air plus the
  embed depth.

It replaces `Slab` in `primitives.py`.

### The root fillet

The blend in use today is a polynomial smooth minimum. Its size is not a radius, and it is capped at
the band's reach of 7.5 mm (3 voxels at 2.5 mm), so an R10 root cannot exist at all.

Rib layouts use a **round blend** between each rib and the part:

```
k = R · (1 − n_a · n_b)
d = max(k, min(a, b)) − ‖ max((k − a, k − b), 0) ‖
```

Here `a` and `b` are the distances to the part and to the rib, `n_a` and `n_b` are their unit
normals, and `R` is the radius wanted.

- **Where a rib stands square to a surface** (`n_a · n_b = 0`), this is exactly a rolling ball of
  radius R: a rib meeting a ceiling, a boss or an outer wall head-on.
- **Where it meets at an angle**, from skew, a grid's angle or draft, `k` is corrected by the local
  angle, so the fillet touches both surfaces where a ball of radius R would. Between those two points
  the curve is not exactly circular. How much that matters is measured by the achieved-radius check
  rather than assumed.
- **It changes the field only where both `a` and `b` are below `k`**, which means at a junction. The
  part's own edges are never rounded. A blend over the whole part would round them all.
- **Where ribs cross**, ribs are joined to each other with the same radius before they are joined
  to the part - with ``k = R`` and no angle correction, since the composer keeps only which rib is
  nearest, not both normals. Exact for a square grid's right angles; approximate for a triangle
  grid's 60 degrees, and the achieved-radius check measures it.

The baseline distance has to be known out to the largest `k` plus a margin, which is well past the
band. Zones are fixed, so each zone's baseline distance is extended that far **once and cached**,
computed by the same exact point-to-triangle scan conversion `field.py` uses. Changing a lever then
recomputes only the ribs.

**The rib's normal must be its own, exact.** The part's normal is taken from its distance by central
differences on the grid; the rib's is not. A grid difference beside a rib's root reaches past the
root into the part below, tilts the normal down, reads the corner as wider than it is, and grows
the fillet - R13.7 for R10 on the test plate. Evaluated exactly, only in the strip within 2R of both
surfaces where the blend can act, it comes out R9.55.

The fallback is a grow-then-shrink closing restricted to the ribs. It gives a true rolling ball at
any angle, at several times the cost, and is used only if the achieved radii fail the check.

### Protected areas

After blending, the field inside each protected area and its clearance band is copied back from the
baseline. Protected surfaces therefore come out byte-identical to the baseline, and the check proves
it by comparing cells. A rib or fillet cut short by a protected area is a warning, reported with its
location.

Protected areas are proposed from detected features: every bore, every hole pattern, and the
planar groups a drawing tolerances (the existing `controlled` faces). Each gets a 5 mm clearance. A
person adds what the drawings do not show, such as bolt-head access, tool access and envelopes, and
approves the result on a coloured picture.

Material already in the baseline is not protected unless it is marked so. A rib may run into an
existing rib or boss; the junction gets a fillet like any other.

### A design is an exact function

A design can be evaluated at any point. The baseline distance comes from its cached field, or from
the zone's extended distance near a rib; the ribs and blends are analytic. Grid spacing only matters
when the function is sampled, which happens when a person presses Generate or the script builds a
design. The samples are then contoured.

**The spacing is the smallest root fillet radius ÷ 4.** With the production-style R10 root that is
2.5 mm, today's grid, which is already built and cached. An R10 fillet is 4 voxels across. The R5
free-edge rounds are 2 voxels across, so they come out approximate and are held only to the R3 floor.
Finer spacing is available if a root fillet below R10 is wanted; 2.0 mm costs about 1.6× the
one-time build and 2× per design.

### Contouring only what changed

A design changes the part only near its ribs. Re-contouring the whole housing takes about 20 s at
2.5 mm, so the baseline is contoured once and cached, and a design re-contours only the cells its
ribs changed.

This is not the patch joined by a mesh boolean that [generate.md](generate.md) once ruled out. Dual
contouring is local: a vertex depends on its own cell's eight samples, and a quad on the four cells
around one lattice edge. Every vertex carries a key - its cell and which piece of surface in that
cell - and every triangle the key of the lattice edge its quad sits on, and both are kept in key
order. A splice re-places the vertices of the cells a changed sample is a corner of, rebuilds the
quads on those cells' edges, and merges the two by key. Nothing is joined. The result is exactly
what contouring the whole field gives, and the tests hold it to the byte - on random solids, on the
test plate, and on the housing with a rib-sized edit (54,162 changed samples: 6.8 s to splice, 18.7 s
to contour everything, identical bytes).

**Manifold, and how.** The old contour put one vertex in each cell, and a cell the surface passes
through twice shared it between two sheets: 64 edges in more than two triangles on the housing.

- A vertex per *piece* of surface in each cell, from the cell's corner signs, fixes most of it.
- A face whose corners alternate is the rest. It carries two stretches of surface, and whichever
  way it is resolved, both stretches can land in one piece on *both* sides of the face - four
  triangles to one edge again. A fixed rule ("solids separate") left 4 of 12 random solids faulty;
  deciding each face from both cells' connectivity left 174 of 400, because pieces also join through
  other faces' decisions.
- What works: a face whose corners alternate is never crossed directly. Each stretch across it gets
  a vertex of its own on the face, and the quads through it become small polygons fanned around
  their centres. It reads only the face, so it is local and splices like everything else. 400 random
  solids: no fault. The housing: no fault, for 390 extra vertices among 1.7 million.

Self-intersections are not counted yet.

### Checks

Every design comes out pass, warn or reject, never silently dropped, with the reason and a location:

| check | rule | outcome |
|---|---|---|
| protected areas unchanged | every cell in every protected band equals the baseline | reject |
| nothing floating | every connected piece of rib touches the part, directly or through other ribs; this is also what keeps the design one solid | reject |
| rib thickness | inside the thickness window, and at least 4 voxels at the delivered spacing | reject |
| rib against wall | rib thickness ≤ 0.8 × the wall it meets, the wall measured through the part within 1.5 rib thicknesses of the root | warn |
| root gap | the clear gap between neighbouring ribs' flanks, away from where they cross and only where they stand in open air, is ≥ 2 × thickness | reject |
| root fillet | the achieved radius, read off the contour, is ≥ the floor | reject; warn if more than 20% off target |
| blend bridging | fillet material filling a gap between a rib and a surface it does not touch | warn |
| blend clipped | a fillet cut short by a protected area | warn |
| mould release | draft inside the window, and nothing of the part above a rib's tip along the pull | reject |
| thick spots | a section at a junction more than 2× the adjacent wall, where cast iron shrinks | warn |
| surface | closed and oriented, every edge shared by exactly two triangles | reject if not closed |

Thresholds come from the rules in project data. Each check reports which rule it used, and whether
that rule is assumed. No check is trusted on the housing until it has rejected a synthetic part
built to fail it - and every one has.

**The achieved fillet is read off the surface.** On a fillet, the distances to the part and to the
rib satisfy ``(k - a)^2 + (k - b)^2 = k^2``, so every contoured vertex on one says the radius it was
built to: ``k = a + b + sqrt(2ab)``, ``R = k / (1 - n_a . n_b)``. The median per rib, and the
smallest of those, is what is reported - grid error and all.

### Designs on disk, and what is derived

A design is its **settings**: per zone a formation and its lever values, plus the baseline's digest
and the spacing. For example:

```json
{
  "baseline": "sha256:…",
  "spacing_mm": 2.5,
  "zones": {
    "zone-1": {"formation": "spokes", "count": 7, "phase": 0.4, "skew": 12, "thickness": 20, "height": 0.8},
    "zone-2": {"formation": "triangle_grid", "spacing": 150, "angle": 15, "offset": 0.0, "thickness": 20, "height": 0.9}
  }
}
```

Its digest is a hash of the settings plus the code, as every cache key already is. The settings are
the only thing written that is not derived.

Everything else is derived. In this build a design's geometry and checks are held in memory for the
session and rebuilt from its settings when asked for again; they are not written to disk.
*"Geometry is regenerated, never stored"* therefore still holds; what is new is that regenerating
takes seconds. What *is* kept on disk is everything a design is made from: the corrected baseline,
its contour, and each zone's window.

The same settings, the same baseline and the same code give the same bytes, and a test enforces it.
Designs built by older code are not yet marked stale.

### What the physics plan receives

For each design:

- a closed, oriented surface in which every edge is shared by exactly two triangles
- on every triangle, the baseline CAD face nearest it, so bores can carry loads. Tagging a rib's
  triangles with the rib and which part of it they are - flank, top, edge round, fillet - is not
  built yet.
- the field at the delivered spacing, for a route that immerses the part rather than meshing it
- the settings, the digests and the check report

How the part is then meshed or immersed is that plan's decision.

---

## The interface

In the Generate stage. No part's name appears in code: zones, formations, levers and rules are
labelled from project data.

1. **Approve once.** The proposed zones, protected areas and baseline corrections are listed, each
   with what it covers and one Approve. A zone has no levers until it is approved. Drawing them on
   the part in colour is not built yet.
2. **Pick a formation** for each zone: spokes, web, square grid or triangle grid.
3. **Set its levers.** They are sliders with their bounds, which come from the rules, with an
   *assumed* badge where the rule is assumed. Fixed values, such as the fillets, edge rounds and
   draft, are shown but cannot be edited.
4. **Generate.** Builds the design from the lever values: ribs, fillets, protected areas, surface,
   checks.
5. **See it.** The new design replaces the one in the viewer. Beside it:
   - pass, warn or reject, with each reason
   - mass, and its change from the baseline
   - added rib volume
   - the smallest fillet achieved
   - any pieces dropped as too short

   The design's new surfaces - ribs and fillets - are drawn in blue over the part. Only those are
   sent: a triangle is new when its middle stands off the baseline's surface.

The same lever values always generate the same design. So any design the script built can be seen
by entering its values and pressing Generate, and nothing more is needed to browse them.

---

## The first study: the GRC rear housing

Everything in this section is project data, not code. Measured on 2026-09-11 by comparing the two
files line by line on a 1 mm grid, and cross-checked against OCC booleans where those ran.

**Files.** Both are in the same frame: identical bounding boxes, and 1,604 faces identical in type,
area and centroid.

| file | role | contents | volume |
|---|---|---|---|
| `housing_baseline.brep` | **baseline** | 1 valid solid, 1,753 faces, plus 29 loose edges left at the old rib roots | 121,301 cm³ |
| `254492_0_closed_volume.step` | **reference** | 1 valid solid, 2,167 faces | 127,857 cm³ |

The volumes come from tight integration. OCC's default integration reads both about 70 cm³ high
(121,373.7 and 127,916.9 cm³), which bears on the 0.117% volume disagreement in
[status.md](status.md).

**What was removed.** 9 solids, 6,615.7 cm³ with their fillets:

- **Rear**, 5 ribs, 4,249 cm³, at 135°, 201°, 244°, 296° and 339°.
- **Front**, 4 solids, 2,366 cm³, at 130°, 237°, 303° and 342°. The one at 130° has a second plate
  that is not radial.

Every plate is exactly vertical and radial. Root fillets are R10, free edges are rounded R5, and
corners have R10 spherical blends. The rear ribs span the gap between the main bore's boss and the
outer wall, with free tops and bottoms. The front ribs hang from the underside of a wall at z 660
down to a free edge at z 555. **In both rings, ribs sit only between about 130° and 342°**, and none
sit on the side facing the other two shafts.

**What Onshape added.** 52.6 cm³:

- 50.7 cm³ under the old rear rib at 135°: a patched floor up to 13 mm above the original floor at z ≈ 70
- 2.0 cm³ at the inner top fillet of the old front rib at 130°

The baseline correction trims both away.

**One rib was never removed.** A 20 mm radial plate in the front ring at 198°, spanning z 560–650,
is in both files. It stays, as part of the housing. New ribs may run into it and are filleted there,
and the root-gap rule keeps them from running alongside it.

**Density** is 7.20 g/cm³, *derived*: the drawing's stated mass of 921.15 kg divided by the
reference volume. It is written in `project.json` with that basis; nothing in the pipeline reads the
mass off the drawing yet.

**Zones.** As proposed on the housing from the removed material, about its three major axes (the
shafts at (0, 0), (0, 520) and (246, 377)):

| zone | about | arc | band | levels | ribs |
|---|---|---|---|---|---|
| zone-1, rear | the main axis | 115°–359° | r 295–642 mm | from z 29, 125 mm deep | span between walls, pull up |
| zone-2, front | the main axis | 85°–357° | r 205–544 mm | from z 661 down, 112 mm | hang from the ceiling, pull down |

The front arc reaches 85° because the old front rib at 130° branched towards 100°.

In the rear, ribs span the gap between boss and wall, and any piece touching neither is rejected as
floating. In the front every rib hangs from the ceiling, so it is attached along its whole length.

**Rules.**

| rule | value | basis |
|---|---|---|
| rib thickness | 15–25 mm | *assumed*; production is 20 mm front and 25 mm rear, *measured* |
| draft | 0–2°; 1° in the campaign | *assumed*; production flanks have 0°, *measured* |
| root fillet | R10, never below R3 | R10 as production, *measured*; the floor is drawing note 3, *"ALL NON-SPECIFIED RADII R3.0"* |
| free-edge round | R5 | as production, *measured* |
| rib against wall | ≤ 0.8 × wall | *assumed* foundry rule |
| root gap | ≥ 2 × thickness | *assumed* |
| thick spot | ≤ 2 × the adjacent wall | *assumed* |
| clearance around protected areas | 5 mm, plus bolt-head and tool access still to be entered | *assumed* |

No draft, minimum-wall or foundry rule appears on any drawing. Drawing 254492 says only *"CHECK CAST
WALL THICKNESS"*.

**The first 64 designs.** 16 per formation, so that the physics plan compares formations fairly.
Each design uses one formation, with the same lever values in both zones:

| formation | levers and bounds |
|---|---|
| spokes | count 3–12 · phase 0–1 of a pitch · skew −30° to +30° |
| web | spokes 3–10 · phase 0–1 · hoops 1–3 |
| square grid | spacing 80–240 mm · angle 0–90° · offset 0–1 of a spacing |
| triangle grid | spacing 100–300 mm · angle 0–60° · offset 0–1 |
| every formation | thickness 15–25 mm · height 0.5–1.0 |

Steps: counts 1, phase and offset 0.02, angles 1°, spacing 5 mm, thickness 0.5 mm, height 0.02.
Within each formation the 16 come from a seeded Latin hypercube: each lever's range is cut into 16
bands and each band is used once. The design named a scrambled Sobol sequence; SciPy's quasi-random
module sits behind a native library this machine's Windows Application Control policy refuses to
load. Values snap to their steps, and any duplicates that creates are built once. How many designs pass is a result, not a target. All bounds are assumed and can be edited in
project data.

---

## Built, and how each gate came out

**0. Ground - passed.**

- The three defects found while planning are fixed: the field-options key, the design surface route,
  and the test count.
- `project.json` holds roles; the `.brep` reader keeps the solid and reports the rest.
- On the housing: the baseline reads as 1 solid, 1,753 faces, watertight, 133,102 triangles; the 29
  loose edges are reported; the drawing still gives the same 7 controlled faces.
- The trim to the reference removes **58.8 cm³** at 2.5 mm. The gate said 52.6 ± 1; a count of
  2.5 mm voxels over a bump 13 mm thick cannot resolve that, and reads 12% over. The fine
  measurement stands; the voxel figure is what the field holds.

**1. Contouring only what changed - passed.** The housing contours with no faults; a splice of a
rib-sized edit is byte-identical to a full contour. See
[Contouring only what changed](#contouring-only-what-changed).

**2. The rib and the blend - passed.** On a plate, R9.55 achieved for R10 square to it, R9.61 with 2°
draft, centre within 0.3 mm of where a rolling ball puts it; untouched cells bit-identical; a
protected face next to a rib byte-identical; crossing ribs blended. The angle correction is tested on
the blend itself at 60°, 90° and 120°; a field-level test of a rib at an angle is not written.

**3. Zones and formations - passed on test parts, proposed on the housing.** On a synthetic ring the
zone comes out as the half ring the ribs occupied, standing on its plate, and all four formations
stay inside the wall and contour closed. On the housing the two rings come out as above. Nobody has
yet looked at a design of each formation on the housing.

**4. Checks - passed.** Every check has rejected a part built to make it fail.

**5. The interface - built, not yet driven.** It type-checks and builds; it has not been opened in a
browser, because starting the development server is a person's call.

**6. Designs, and the script - built.** `fastcae designs` builds a seeded batch and writes
`settings.json` and `summary.csv` to the project's `designs/` folder; on the test ring every
formation is sampled and a listed design rebuilds to its digest. The 64 on the housing have not been
run.

## Measured on the housing

| | measured |
|---|---|
| extract the baseline | 7 s |
| field at 2.5 mm, cold | 158 s |
| reference field on the same grid, cold, and the trim | 194 s |
| contour the corrected baseline | 20 s: 1.70 M vertices, 3.40 M triangles, closed, no faults |
| splice a rib-sized edit | 6.8 s, against 18.7 s for a full contour; identical bytes |
| propose zones | 1.5 s |
| build a zone's window, cold | about 11 minutes; kept after |
| a design, compose to checks | being measured |

What the window costs is the exact distance out to 2R past the band - 30 mm at R10 - over every cell
of a box round the zone's arc, about 20 million cells a zone; it is paid once per baseline and zone.

## What we learned

**About the part.**

- The baseline is not the reference minus its ribs. Onshape's patch under the old rear rib at 135°
  stands up to 13 mm proud of the original floor, adding 50.7 cm³ that is in neither the casting
  nor anybody's intent; another 2.0 cm³ sits at a fillet. That is what the trim correction is for.
- The `.brep` is a dump of an editing session: one solid, and 29 loose edges where features were
  deleted. A reader that passed them on would have handed the atlas edges with no face.
- One rib was never removed, at 198° in the front ring. It stays as housing.
- The production ribs are not what the old notes said: the rear ones are T-sections spanning boss
  to wall with free tops; the front ones hang from a ceiling; all have R10 roots and R5 edges and sit
  only between about 130° and 342°. That set the rules' defaults and the 2.5 mm grid (R10 ÷ 4).
- OCC's default volume integration reads this part about 70 cm³ high. A tighter integration and a
  mesh convergence study agree on 127,857 cm³ for the reference, 121,301 cm³ for the baseline.

**About the method.**

- Contouring only what changed needs no boolean, and generate.md was wrong to think it did: on a
  fixed grid a vertex depends only on its own cell's samples.
- Manifold contouring took three rules to get right; the first two each passed the small cases and
  failed at scale. Random solids by the hundred found what patterns by the handful did not.
- The blend must pass the plain union through exactly where it does not act, or every cell near the
  part counts as changed and a splice redoes the whole window.
- The rib's normal in the blend must be its own. A grid difference tilted it and grew R10 to R13.7.
- A round union's interior distances are exact, not a lower bound: a test expecting ``min(a, b)``
  deep inside two overlapping half-spaces was wrong, not the blend.
- A rib's axis is not the nearest one. Ribs run away from their axis, so a neighbouring axis is
  often nearer; a rib is a plate, and its plate contains its axis. But feature detection offers 188
  axes on this part, and a rib's plane contains many by accident, so zones are proposed only about
  axes carrying at least a tenth of the largest one's surface - the three shafts, at 100%, 59% and
  24%; the next carries 2.5%. A piece that is no plain plate joins the group at its levels.

**About the checks - each of these was wrong once, and each now has a test.**

- Every cell of a window read as protected: a distance clamped at the clearance equals the
  clearance, so ``<=`` was always true.
- Root gaps were measured on whole centrelines, including stretches inside a boss where spokes
  converge and are trimmed away.
- Mould release looked at rib tips drawn into a boss, which are the boss.
- Wall thickness was read only where a rib reaches, one voxel into the metal: a 30 mm plate measured
  8 mm.

**About the machine and the code.**

- Windows Application Control blocks SciPy's `scipy.stats`, through a native library it loads;
  anything needing it has to be written in numpy. `cadquery-ocp` stays pinned at 7.9.3.1.1 for the
  same reason.
- Over a whole window, the base-grid index and the normal of every cell would be about 400 MB a
  zone. They are worked out for the cells a design touches instead.
- A window's cache key has to name only the code that builds a window. Keying it on the checks'
  code threw away eleven minutes of distance work every time a check changed.
- The cache keeps four entries of each kind. Tests that open the real project at 20 mm write field
  entries too; so far the 2.5 mm field has survived, but it is the one that costs minutes to lose.

## Decisions now in force

These replaced rows in the decision table in [status.md](status.md) when they were built.

| was | is |
|---|---|
| Configuration: none, no manifest | `project.json`: roles, corrections, zones, protected areas, density, proposed by the system and confirmed by a person |
| Contouring: whole-field, every time | the baseline whole and once; a design re-contours the cells it changes, spliced in by key |
| Parameters: authored on a face selection; placement fixed, height is the dial | a formation and its levers per approved zone; placing a rib on a face selection returns later as the manual formation |
| Design: a CAD digest and a vector | unchanged. A design is settings against a baseline, and geometry is derived |

## Not done yet

- The 64 designs on the housing, and the time a design takes there.
- Opening the Generate tab in a browser.
- Drawing zones and protected areas on the part; tagging a rib's triangles by rib and part of rib.
- Counting self-intersections; marking designs built by older code as stale.
- A field-level test of a rib meeting a wall at an angle.
- Approvals on the housing: they were set to test this build end to end, and go back to *proposed*
  for a person to approve in the Generate tab.

## Later

- **The physics plan**, which is where formations are compared. Every archived plan agrees that a
  design is screened fast and confirmed accurately; they disagree on how. The earlier study measured
  that a fixed Cartesian grid spends more degrees of freedom than a body-fitted mesh on this part.
  At 10 mm the grid needed 0.72 M DOF with 61% of its cells cut, against 0.17 M for linear
  tetrahedra. That plan starts from those numbers.
- Launching a campaign from the interface, and the agent drafting settings: the agent proposes, a
  person confirms, as [tasks.md](tasks.md) sets out.
- The design updating while a lever is dragged.
- Crossed and honeycomb formations; placing a single rib on a face selection.
- Formations on flat walls, conformal to curved walls, or following stress; height driven by a
  field.
- Tilted ribs, as a labelled mode.
- Wall thickness, through face-set offset.

## Sources

The five documents this plan was drawn from are in [archive/](archive/README.md), with a note on
what each contributed. The measurement of the removed ribs, and the timing runs on the housing, were
made with scripts outside the repo; their numbers are recorded above.
