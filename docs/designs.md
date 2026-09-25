# Designs

**A rib network made in the design volumes the engineer kept: one constrained problem, held to
the target's metal and read against the target at every stage - every stage checked, every stage
in view.** For the deck's load case and its objective, fins are proposed by a seeder and admitted
by one gate of placement, moved by an optimiser inside bounds under the target's metal, chosen as
a network by CP-SAT on the objective's own derivative, and built, meshed and solved as their own
CAD, the way the target and the deck were solved. A run passes only if its design beats the target
with no more metal. Why it is this way: [rib-optimisation-plan.md](rib-optimisation-plan.md). The
code is `src/fastcae/volumes/`, `src/fastcae/ribs/` and `src/fastcae/designs/`; the routes are
`src/fastcae/api/volumes.py`, `src/fastcae/api/ribs.py` and `src/fastcae/api/designs.py`.

---

## Design volumes

Where a design may put metal is the engineer's to say. On the CAD's **Design volumes** view they
click a face and see at once the closed volume it bounds; they set its height, switch off what it
keeps clear if they must, and keep it.

- **The recipe** is what is kept, in `<project>/volumes/volumes.json`: the faces picked, the axis,
  the band along it, the reach out from it, the anchor ribs grow from, the keep-outs switched off.
- **The axis** is the largest round face picked, or - from flat faces - the largest bore square to
  them within their outline. **The band**: from a floor towards the side it faces, as tall as the
  tallest round thing standing on it; between faces, the heights they share. **The anchor**: the
  round faces picked, or the bosses standing on the floor. **The reach**: rays cast out from the
  anchor to the walls it faces, or a wall picked, and a margin past.
- **Found in flat slices**, a few millimetres apart along the axis: each slice the region's disc less
  the part's metal - the part's own triangulated faces, cut by the plane - less what is kept clear;
  pieces in neighbouring slices that overlap join into pockets; the volume is the pockets that
  touch the anchor and, when a floor was picked, the floor. No solid boolean runs on the part.
- **Kept clear**, as exact meshes:
  - every bore over its length, and what carries on past it - outward at full radius, inward at
    full radius and 5 mm more as far as air runs, nothing past a register;
  - **every bearing's line** - a bore the deck loads carries a shaft: kept clear along its axis past
    any lip, to the next bearing on the same axis at the smaller of the two radii, on through the
    part where none follows;
  - every hole and its tool; a lid in front of every flat face the deck holds.

## The target

What a design is to beat is an input, like the CAD and the deck: for a housing, the production
casting. Its CAD is kept in `<project>/target/`, meshed face by face as C3D10, the deck's own groups
carried onto it by the CAD faces it shares with the part, the deck's loads and supports unchanged,
solved by cuDSS - the route every design takes. Its added metal is the budget designs are held to
(at most that, at least 90 % of it), and every design's signals are read beside it.

## The network workflow

`ribs/workflow.py`, run by the runner as a `ribs.network` job. Nothing in it knows the part: the
volumes, the deck and the target are the project's.

| stage | what it does | read after it |
|---|---|---|
| **Seed** | a seeder proposes fins; the **gate of placement** admits them (`fins.placeable`): across the volume's own air and never over a bore or keep-out, square enough to its walls, a wall to root in, its middle clear of the metal, apart from the fins already placed but for a root they share, and passed by the CAD's own sections. As many fins as the target's metal affords at full height | the fins, their metal as cast, the largest displacement on the cubes beside the target's; what the gate refused, and why |
| **Pass** | every fin's numbers - its ends on the rail, its curve, its three heights - moved by MMA on 10 mm cubes, inside bounds (ends slide a little, control points stay in a band), the metal capped at the target's, the clearance and spacing rules held | the same reading |
| **Oracle** | every fin judged on its numbers before any boolean: faded, alongside the metal, buried, folded. It should find nothing | how many passed, each refusal's reason |
| **Chooser** | CP-SAT keeps a network under the rules that are decisions - conflicts, junctions, the cap, at most so many to a volume - each fin valued **in the company of the rest** by the objective's own derivative. While the cap has room no rule-passing fin is dropped, and a fin dropped on value alone is measured back in | what was kept, every other fin with the rule that left it out |
| **Polish** | the same optimisation, the topology fixed | the reading against the target: **beats it or not**, and by the cubes' margin |
| **Path** | each kept fin a swept solid rooted in its walls - as polished, or as it was seeded if the CAD will not have that | fins built as solids |
| **CAD** | the solids fused into the part's B-rep; STEP written | every solid fused; one solid; metal added 0.8-1.2 of the plan; new faces under 5 mm² counted and reported |
| **Mesh** | face by face as the deck's mesh; second-order tets | at most 305,000 tets; none inverted; no hole closed flat; at most 0.08 % below quality 0.1 |
| **Solve** | the deck carried onto the mesh by CAD face, solved by cuDSS | the reactions balance the loads within 2 %; largest displacement and added mass beside the target's |

**Seeders**: spokes from each boss to the first wall it meets, chords that close a ring round a
boss, tangents, a wheel of spokes and ring, and a scatter - random pairs of wall positions placed
by the rules alone. They differ in what they propose and never in what is allowed, so different
seeds settle into different designs under the same rules.

**The cubes flatter a rib network** more than they flatter the target - they over-stiffen thin
webs and count rib depth that attaches to nothing - so each solved design teaches a margin (its
mesh reading over its cubes reading, against the target's own). The margin is shown with the
reading; it informs and does not yet gate the build.

A design that fails a check stops there, says which check and by how much, and stays on screen.

## Load cases

From the deck, never from what the part is for: **the deck** - its own case; **each line of shafting
alone** - the loaded groups that share an axis, the deck's loads on them only; **the lines** - every
line as a case of its own, carried together.

## On the screen

**Campaign** plans a new one: the kept volumes as chips, the target it is held to - the cap and the
pass line - the seeder as pills, and the steps folded away. One campaign makes one network.

**A campaign is shown in the stages it was made in**: Seed, Pass, Oracle, Chooser, Polish, then
Path, CAD, Mesh and Solve - the grid, the rail and the design's tabs follow the campaign's own
list. Each of the first five is drawn on the part: the fins as lines standing at their height on
the volume, every fin in the colour of what happened to it there - seeded, moved, passed or
refused, kept or dropped, built - with a chip per state counting them, a pill per reason, and the
pass's and the polish's histories on the iteration slider. The design's card adds **Network** -
how many fins went how far, what the gate of placement refused, and the design **against the
target**: on the cubes after its polish, on the mesh once solved, displacement and metal, beats it
or not - and **Fins**, every seeded fin with its value, its metal and its fate, the reason on hover.
The fins' runs are kept beside the design (`fins.npz`) and served by stage
(`/api/designs/{campaign}/{design}/fins?stage=`).

**Designs** shows each later stage on its canvas - the CAD's new faces with its STEP, the mesh, the
stress and displacement - with every stage's numbers, the checks, and the deck's signals beside the
target's and the bare part's.

## On the housing

The GRC housing, rib-free, with its deck; the production casting as the target: 0.443 mm largest
displacement with +47.5 kg (6.54 L) on the mesh, 0.374 mm on the cubes. The bare part moves
19.8 mm: the main bore's hub is a ring held at 12 o'clock and free round the rest, joined to a thin
outer wall only by webs across an open annulus - so every design moves most at the hub's lip at
6 o'clock, along the bore's axis. Filling both design volumes solid reads 0.130 mm on the cubes:
no network in them can do better.

| | ribs built | largest displacement | metal added |
|---|---|---|---|
| **production** (target) | 9 | 0.443 mm | +47.5 kg |
| spokes, launched from the product | 18 of 18 | **0.359 mm** (-19 %) | **+30.1 kg** (-37 %) |
| spokes, the run before | 14 of 14 | 0.416 mm (-6 %) | +22.1 kg (-53 %) |

Its strain energy is 4.3 % of the bare part's against production's 3.9 %. A campaign takes ten to
thirty minutes: the seed with the CAD's word on every fin, the pass and the polish on the cubes,
then the build, the mesh and the solve.

## Limits

- **Corner faces under 5 mm²** remain where a sunk rib end meets its wall - about one a rib. They
  are counted and reported; the mesh's own checks decide, and have passed every design.
- **The cubes are not yet a fair judge**: they read rib networks 1.1 to 2.3 times lower than their
  meshes, production 1.18. Until that spread narrows the margin informs and does not gate.
- **The spacing figure is a placeholder** - 100 mm between centres, 35 % of a run free at a shared
  root - and with it spokes alone spend about two thirds of the target's metal. It, and the one
  20 mm section, are the engineer's to set; production's own webs are about 30 mm thick.
- **No fillets**: the fuse adds no root fillet; a rib's root is as sharp as its solid.
- **One load case**: the deck's. Its sixteen components are kept solved with every design.
