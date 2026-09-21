# Plan: ribs the loads shape, castable by construction

**Agreed 2026-09-20.** Supersedes the lane in [archive/rib-families-plan.md](archive/rib-families-plan.md). What is
built, in what order, and how each step is judged. Where the work stands and what every earlier
approach measured is in [design-generation.md](design-generation.md).

---

## 1. Why this, and not more of what we have

Two routes have been tried to the end and both are half-answers, measured on the same housing
against the same production casting:

| | castable | carries load | can be nudged |
|---|---|---|---|
| rib library + CP-SAT | yes | **the 20 varied designs were all worse than production**, +99 % to +9079 % | **no** - CP-SAT swaps ribs, it cannot move one |
| geometry projection on free plates | **no** - 25 of 30 plates rejected for sliver faces at the fuse | **yes - 4 of 4 beat production, -6 % to -47 %** | yes |

The gradient route is the only one that has produced a design worth casting. It loses its answers
at the step where a free shape is forced back into something buildable.

**So the parameterisation itself must be castable.** Then there is no conversion step to lose the
gains at, and the optimiser can still move every number.

## 2. What a rib is

> **A root curve on a surface, extruded along that surface's draw, with a set of profiles along it.**

Nothing in that sentence names a bore, a wall or a boss. The part supplies the surface and the draw;
the loads supply everything else.

### 2.1 The root curve

Four control points:

| | count | what it does |
|---|---|---|
| **ends**, on the rail | 2 × 1 | how far along the metal boundary each end sits |
| **interior**, free in the plane | 2 × 2 | bend the curve between them |

Both ends are **pinned to the metal boundary**: an end has one degree of freedom, it slides along
the rail, never two. The interior points are free.

Moving them gives: a straight rib, an **arc** (bow one), a **chevron** (pull them opposite ways).

### 2.2 The profiles along it

Each is a small spline in the run parameter `s`, and each is continuous, so `dJ/d(·)` exists.

| profile | what moving it produces |
|---|---|
| **h(s)** - height above the base | full-depth web → tapered rib → **run-out** → **gusset** (full at one end, zero at the other) |
| **w(s)** - flange width on the free edge | plain web → **T-rib**; a local bulge → a **boss or pad** |
| **r(s)** - root thickening | a **fillet** where it meets metal, heavier at the loaded end |
| **holes** - centres and radii along `s` | **lightening windows** |
| **α** - presence, 0 to 1 | the rib fades out and disappears |

A gusset is not a form; it is `h(s)` falling to zero. A boss is not a form; it is `w(s)` bulging.
**The eleven shapes we built as a discrete library become regions of one continuous space**, and the
optimiser reaches them by moving numbers rather than by picking from a menu.

### 2.3 Thickness is not a variable

Fixed at **20 mm**. The production housing casts every rib at one section; a fixed thickness is also
what lets a rib fuse into a wall without leaving a wedge. `w(s)` and `r(s)` vary metal locally where
a foundry would; the web itself does not.

### 2.4 The base is read, not chosen

`base(s)` is **whatever lies underneath at that point** - the top of the metal below if there is
any, otherwise the bottom of the volume's band. It is computed from the part.

This is what stops a rib hovering above a floor: there is no number that would let it.

### 2.5 The surface and the draw

The same parameterisation covers both places ribs live. Only the surface and the draw change, and
both are read from the part.

| | surface the root runs on | draw | what it gives |
|---|---|---|---|
| **inside a pocket** | the volume's cross-section | the volume's axis | ribs between a bore and a wall - what we do now |
| **on an outside wall** | the wall itself | normal to the wall | the diagonal and zig-zag ribs on real housings |

One precision that decides castability: **a zig-zag across the draw is fine; a zig-zag along it is an
undercut.** The rib's faces stay parallel to the draw or it will not leave the mould. The
parameterisation enforces this by construction - the profiles run along `s`, and the extrusion is
always along the draw.

### 2.6 Where a rib is placed - the rail and the gate

Placement is not chosen from a list; it is read from the volume, proposed by a seeder, and admitted
by one gate.

1. Slice the design volume into its cross-section. **Its outline where it meets metal is the
   rail** - the only place an end may sit.
2. A rib is **two points on that rail**: bore → wall gives a spoke, wall → wall a chord.
3. **Every seeder goes through one gate of placement** (`fins.placeable`). Spokes, chords that
   close a ring, tangents, a wheel, a random scatter and load-path members differ in what they
   propose and never in what is allowed. A straight fin between two rail positions is placed only
   if it is at least three sections long; lies across the volume's own air - never over a bore, a
   keep-out or an island of metal; meets the wall at each end at 35° or steeper; ends on metal
   that stands at least 25 mm, so the end can root; and keeps its middle clear of the metal by
   **the same measure the pass holds** (`fins.clearance`).
4. A fin takes its place only if it also **stands with those already placed**
   (`fins._against`): a section and its sand apart, but for a root the two share
   (`ROOT_FREE` - spokes converge on their boss, two ribs meet a wall in a V), or across the other
   at 60° or steeper, a junction. Rays cast closer than the rule allows seed every second or
   third spoke; nothing is left for a chooser to thin.
5. **The CAD's own sections judge a seed too** (`sow_anchor(also=…)` → `oracle.on_sheet`). They
   see what no plan or cube does - a wall 4 mm tall that the cubes read as 25, a leaning wall an
   end would run along - and cost seconds a fin, so they are asked last. A fin they refuse never
   takes its place, and its neighbour may stand instead.
6. Both ends then slide along the rail and the curve between them bends - **inside bounds**
   (`Layout.narrow`): an end slides 40 mm at most and never more than a quarter of its chord; the
   two interior control points stay in a band the seed's own room sets (`fins.bands`), never
   more than 15 % of the chord. The pass can neither fold a fin nor push it out of the air it was
   seeded across.

**What order there is in a seed is the rules'.** A scatter (`fins.sow_scatter`) draws two rail
positions at random and keeps the pair only through the gate and against those already kept: it
comes out square to its walls, evenly apart, crossing steeply or not at all. A pattern is a
proposal, never a limit.

## 3. What is impossible, and what is merely expensive

The line is **"is this ever right?"**. Hard constraints only where there is no legitimate case.

**Structural - no number can express it:**

| | why |
|---|---|
| a rib coming adrift at its ends | the ends are pinned to the metal boundary |
| a rib hovering above a surface | its base *is* that surface |
| an undercut | the extrusion is along the draw |

**Charged - the optimiser may do it if the physics pays:**

| | charge |
|---|---|
| standing taller than what holds it | free-edge charge |
| a hump in the middle | falls out of the same charge |
| crowding another rib | the spacing rule (`fins.spacing`), kept at placement and in the pass |
| metal anywhere | the budget constraint |

The **free edge** is the length of the rib's boundary standing in air with nothing to tie into. It
is a physical quantity, not an invented penalty, and it is what makes a rib that rises above its
supports cost something without forbidding it. A rib carrying load *over* a boss is unusual, not
impossible; forbidding it means never finding out.

## 4. From parameters to density

The optimiser needs `ρ(x)` for every voxel and its derivative with respect to every parameter.

1. **Mid-surface.** The root curve `c(s)`, swept along the draw `d̂` from `base(s)` to
   `base(s) + h(s)`.
2. **Distance.** For a voxel centre `x`, the distance `δ` to that surface, and the run parameter `s*`
   of the nearest point - blended smoothly between the curve's pieces, never by picking the nearest
   one. A hard nearest-piece switch puts a step in the gradient wherever that nearest piece changes.
3. **Thickness and flange.** Half-width at `s*` is `T/2`, widened to `w(s*)` near the free edge and
   `r(s*)` near the base.
4. **Smooth step.** `ρ_rib = α · S((halfwidth − δ) / ε)` with `S` the same smooth step the plates
   already used.
5. **Holes.** Multiply by `Π(1 − S((R_k − |x − centre_k|)/ε))`.
6. **Union.** `ρ = 1 − Π_ribs (1 − ρ_rib)`, as now. **Metal is measured from this field**, never
   summed rib by rib, or the budget charges twice wherever two ribs cross.

Every step is differentiable; the chain rule gives `dρ/d(parameter)`, and `paths.Model` already
gives `dJ/dρ` by adjoint. Nothing here is new machinery - it is the plates' projection with a
curve and profiles in place of a straight segment and one thickness.

## 5. The optimisation

**One problem.** For the load case and the objective given:

| | |
|---|---|
| minimise | the objective - here the largest displacement, smooth |
| over | each fin's ten numbers: two ends on the rail, two interior control points (4), three height stations, presence |
| metal | **no more than the target's**, binding from the first step |
| clearance | each fin's middle clear of the metal - counted by the millimetre along its run, so it agrees with the oracle (`clearance`, `GRAZE_MM` = half a section + the oracle's gap + a little) |
| spacing | two fins a section and its sand apart, but for a shared root; steep crossings are junctions |
| heights | an end no taller than the metal it roots in, the middle under the volume's roof, an end on the anchor's round at least 80 % of the boss |
| bounds | ends slide, control points stay in their band (§2.6) |

The seed places **as many fins as the target's metal affords at full height** - the cap is met by
how many ribs there are, not by ribs too short to stiffen anything - and the metal is reckoned as
it would be cast, section times height along the run (`workflow.litres`), which reads
about a fifth above what the cubes draw.

**Solver**: MMA, warm-started, a short pass of about twenty steps, presence held, every rule on.

**Seeds.** Spokes cast from the volume's anchor, chords that close a ring across them (four sides,
meeting the wall at 45°), tangents, a wheel of spokes and ring, a scatter, and the ground
structure's load-path members - all through the gate of §2.6. Different seeds settle into
different designs under the same rules; that is where variety comes from.

### 5.1 The constraints live in the optimiser

**Nothing leaves a network without the physics being asked.** A rule enforced by removing fins
after the optimisation moves the design away from the solution that was found: measured on the
housing, a network read 0.236 mm on the cubes and 0.62 mm once fins had been thinned for spacing
by a chooser that valued each alone; another lost a third of its stiffness to **one** fin the
oracle refused for a margin the optimiser had never been held to. So:

| rule | where it is kept |
|---|---|
| inside the volume, off the bores and keep-outs | the gate; then the control points' band |
| square to the wall, a wall to root in | the gate; the CAD's sections at seeding |
| clearance from the metal | the gate, then a rule of the pass - one measure for the gate, the pass and the oracle |
| spacing, crossings | against the fins already placed at seeding, then a rule of the pass and the polish |
| no fold | the band: a control point moves at most 15 % of the chord |
| metal | the count at seeding, then the budget rule |
| symmetry | tie the two ribs' variables together |

**The oracle is a check that should not fire.** It still reads every fin - on its numbers, on its
sheet, as a solid - before any boolean, because the CAD is the last word. But each of its refusals
is a rule that belongs upstream, and is moved there when it fires.

**CP-SAT decides which fins stand, on the objective's own derivative.** Each fin is valued **in
the company of the rest** (`fins.values_carried`): how far the objective would rise, to first
order, were the metal that fin alone accounts for taken away - one evaluation of the adjoint
gradient with every fin standing, so it costs one solve and not one a fin. Standing alone on the
bare part a fin is read against whatever moves most there: on the housing the bare part's whole
displacement is one face dishing, every fin on the other volume read as worth under 0.02 % and
all seventeen were dropped - though with the first face held the largest displacement moves to the
second, where those fins are what holds it. Leave-one-out reads the opposite error: every fin with
a neighbour covering for it is worth nothing. In company each is read for the load it carries,
and metal two fins share is credited only as far as the other leaves room. Under the rules that
are decisions - conflicts, junctions, a hoop with three of its spokes, a branch with its spine, a
mirror pair together, at most so many ribs to a volume, the cap - CP-SAT keeps the most value, and
every fin it leaves out carries the rule that removed it (`ribs/choose.py`). With the rules kept
at placement it finds almost nothing to remove.

Then a **polish** with the topology fixed, under the same rules and bounds.

**Read against the target at every stage.** After the seed, the pass and the polish the network's
true largest displacement is read on the cubes at one drawing radius - the pass's own figures
follow its continuation and cannot be set side by side - beside the target's on the same cubes
and the metal as cast beside the target's. A network that does not beat the target on the cubes
is not built.

## 6. From parameters to CAD

Two rules, both changes from how designs are built today.

**A fin is a clean solid pushed slightly into the wall.** Its outline is its own - a smooth curve and
a height profile - and it overlaps the metal it meets by a controlled depth. It is never trimmed or
unioned against the wall's silhouette first. That union is what `_finished` does today, and it is
what makes an outline follow 7-31 small steps of the wall and leave a sliver face at every one: the
cause of 25 of the 30 rejections that killed the gradient route. The overlap also removes the other
failure at a stroke - a fin that reaches into metal cannot end in mid-air.

**Every fin is fused in one operation.** `cad.py` fuses plates one at a time today, so each pass
re-cuts the topology the last one made and small faults compound. One batch operation - OCC's
General Fuse, or `CellsBuilder` where cells must be chosen - sees all the interactions at once. The
current path stays until the batch one is measured against it on the same fin set; the more reliable
one wins.

**The whole end is sunk.** Measured on this housing: every face under 5 mm² the fuse left on the
curved ribs sat where a rib's end stood on the wall's face above or below the stretch of wall
thick enough to root it, or where a rail ran a millimetre or two alongside a wall's top edge, the
floor's face or a ceiling. So each end has a **root window** - the heights where the wall is metal
across the rib's whole thickness and deep enough - and over the last 25 mm the base rises and the
top falls into that window, 4 mm inside it; the end is one rectangle sunk into the wall
(`curved.outline_on_sheet`). Clean fusions among ribs the oracle passed went from 13 of 29 to 16 of
25 on the same saved fin sets. The faces that remain are corner faces of a square millimetre or
less where the sunk end's rails meet the wall on the rib's side faces. They are **not** at the
housing's edges: a window kept 3 mm clear of every B-rep edge (`curved.edge_tree`, fillet rims
included) refused most fins and left the faces where they were, so it is built but not used. What
makes them is the next thing to trace, in 3D, before the gate can be measured again.

**The oracle judges before OCC** (`ribs/oracle.py`). A fin that will not build is cheapest to
refuse from its numbers, next cheapest from its outline on its own sheet, and dearest of all at
the fuse. On the numbers: faded; running alongside the metal with its face a hair from it for
more than 10 mm; mostly buried; turning tighter than 40 mm, where the swept faces fold. On the
sheet: no room, no root window, space kept clear in the way; the floor open under the run, in a
volume picked from a floor - one picked between faces spans them by design; a rail alongside a
metal edge within 2 mm on either side or 6 mm of air outside it, the ends unjudged. Every verdict
carries its reason and its measures, and a run's record keeps them for every seeded fin - the
**ledger** - so a run says why each fin was kept or dropped, which is what a feasibility model can
later be fitted on.

Otherwise the existing route: fuse → `UnifySameDomain` → face-by-face mesh → cuDSS → every stage
check. The flange is a second solid as a T-rib's is today; holes are the outline's interiors.

## 7. The steps

| | what | done when | time |
|---|---|---|---|
| **0** | the primitive: curve + profiles → density, with gradients | finite differences match the analytic gradient; the base field is smooth where a floor starts | ½ day |
| **1** | optimise one volume (S2 ring) on `h(s)` and the curve only | runs to convergence, budget holds, nothing detaches or hovers - both impossible by construction | ½ day |
| **2** | **go / no-go**: build it, mesh it, solve it | **does it beat production on J?** **No → stop and say so** | ½ day |
| **3** | add `w(s)`, `r(s)`, holes | each earns its place or is dropped, measured one at a time | ½ day |
| **4** | both volumes, several rib counts, the robust band; the worst load **angle** searched for, not listed | `hold_across` already exists and costs nothing; the search adds the case it finds and repeats | 1 day |
| **5** | the bore-distortion signal | applied to all 152 existing designs, no re-solving | 1 h |
| **6** | outside walls: same parameterisation, the wall as surface, its normal as draw | the zig-zag patterns become reachable | 1 day |
| **7** | the family: load case × objective | each pair its own optimum, all castable, all comparable | ongoing |

**Roughly 2½ days to the go/no-go and its answer.**

Three things wait deliberately until after it. **The realisation gap** - what J loses between the
optimiser's field and the solved C3D10 design - is recorded from step 2 onward but is not a gate
until there is something to gate. **The objective** stays exactly as every one of the 152 solved
designs was ranked on, so step 2 reads cleanly; afterwards tilt and stress become constraints rather
than terms in a sum (mass is already a Pareto axis, not part of J). **Outside walls** are step 6,
and the surface atlas they need - a root curve traced across many B-rep faces - is built then, not
before.

**The agent** sits above the optimiser and never inside it: it picks the experiment (which volume,
which load envelope, which objective, how many ribs to seed), reads the result, explains which gate
a failure hit, and proposes ends to seed. It never touches geometry, loads, keep-outs or foundry
rules, and the solve has the last word. Steps 0-4 each have one obvious next move, so it earns its
place at step 7, where load case × objective × volume outruns us.

The profiles are added **one at a time** (step 3) and the bore signal comes **after** the go/no-go
(step 5), deliberately. Changing the parameterisation and the objective together would leave us
unable to say which one moved the result.

## 8. The measurement we are missing

Every bore reading passes through a distributing coupling that reduces the whole bore to six rigid
numbers - where it moved and how it tilted. **Nothing measures the bore going out of round**, and a
hoop rib round a bearing exists mainly to stop exactly that. An optimiser cannot produce a shape
whose benefit it cannot see.

The fix is arithmetic on data already on disk: take the bore's surface nodes, fit the circle, and
read the **second Fourier harmonic** of the radial deviation - ovalisation, cleanly separated from
the bore merely moving or growing. Free for every design already solved, because
[responses.py](../src/fastcae/designs/responses.py) keeps every load component's whole field.

## 9. What is reused, and what is new

**Reused unchanged:** `paths.Model` and the multigrid (the objective and its gradient on the cubes);
the plates' MMA with many rules, its budget constraint and smooth-step projection, now
`ribs/mma.py` and `ribs/fins.py`; `cad.py`'s fuse; the face-by-face mesher and its fold collapse;
cuDSS; every stage check. Load cases as data and the worst case over a band
(`Model.hold_across`) wait for the robust round.

**New:** the rib primitive of §2 and its projection (§4); the clean-fin construction and batch
fuse of §6; the gate of placement, the seeders and the bands (`fins.placeable`, `sow_anchor`,
`sow_scatter`, `bands`); the oracle and the ledger (`ribs/oracle.py`); the chooser and the
relations between fins (`ribs/choose.py`); each fin's value in company (`fins.values_carried`);
spacing with a shared root free and junction pairs exempt (`fins.spacing`); the outline before
the solid with the end sunk into its root window (`curved.outline_on_sheet`); and the nine stages
in order, read against the target (`ribs/workflow.py`). Still to come: the free-edge charge and
the bore-distortion signal.

**Out of scope**, though each was considered and is written up in the two reviews in `docs/`: learned
CAD generators (OAT, DreamCAD, GraphBRep, DTGBrepGen, Better STEP), alternative solvers (FEniTop,
PyTopo3D), the full IGA/NURBS lane, and geodesic libraries (CGAL, geometry-central) until §6's
outside walls need them. GET stays a discovery lane, not the product path.

**Retired:** the discrete forms `island`, `arc` and `run-out` as generated today. They were built on
a measurement that asked the wrong question, and they float - 17 %, 23 % and 40 % of their outline
attached against 47-50 % for a web. Their shapes return as regions of the continuous space, properly
rooted.

## 10. Risks

1. **The base field may be non-smooth** where a floor begins, giving gradient noise. Smooth the base
   field before differentiating it.
2. **The ends slide along a stepped polygon.** The metal boundary carries 7-31 short stepped edges a
   rib. The fin's own outline no longer follows them (§6), so they can no longer become sliver
   faces - but the ends still *slide* along that polygon, and a stepped rail gives a noisy
   `dJ/d(end)`. Smooth the rail the ends run on, not the fin.
3. **The result could still fuse badly**, as the plate run did. Pinned ends remove the main cause - a
   plate end grazing a wall at a shallow angle - but this is unproven until step 2.
4. **A local optimum from a good start.** Starting from the -52 % set makes the first test clean but
   may not find a different family. The uniform-fan start in step 4 is the check.
5. **Height, read once.** Found and settled 2026-09-21: the optimiser capped a rib's ends by the
   air beside the rail, and at a boss's flank or a wall's foot that is a sliver, so every fin came
   out 15 to 35 mm tall and kissed the boss's edge, while the builder drew the ends to the metal's
   full height. Now both read the same thing: **an end is capped by the height of the metal it
   roots in** - the boss's top, the wall's top - **the middle by the roof over the middle, and an
   end on the anchor's round stands at least 80 % of the boss's height**, because a rib that meets a
   bearing's boss over a sliver stiffens nothing (`fins.capped`, `ROOT_SHARE`). The builder draws
   each end at the height the optimiser gave it, under the same metal top (`curved._full_ends`),
   so Path shows what Pass valued. Within those bounds the height is the optimiser's to raise.
   The curve's interior control points reach no further than 60 % of the chord (`REACH_SHARE`),
   so a fin cannot fold into a hairpin during the pass - 38 of 60 had, before.
6. **The spacing figure is a placeholder.** A section and twice 40 mm of sand - 100 mm between
   centres - and 35 % of a run free at a shared root are set by judgement, not read off a casting.
   Production's own nine ribs stand too far apart to test them. With them, spokes alone place
   about 4 to 6 L in the housing's two volumes against a cap of 6.5 L: whether a pattern can spend
   the cap is decided by this figure more than by anything else, and it is the engineer's to set.
7. **A fin read on the plan is not the fin on the CAD.** The gate's plan and height maps are laid
   at 5 mm; the CAD's sections are the truth and cost seconds a fin. They judge every seed, and a
   kept fin that fails on the sheet after the polish is built as it was seeded, not dropped.

## 11. How it is judged

- **A run passes only if its design beats the target with no more metal than the target's** -
  a lower objective under the same load case - on the cubes before anything is built, and on the
  mesh at the end. Anything less is a failing run, and is shown as one.
- **Step 2 is the gate.** One design, built and solved, against production on the same J every other
  design has been judged on. Beat it, or stop.
- **Every later step is judged the same way**: does it move J, at what metal, under which load case -
  named, because production itself reads 7.9 µm under one case and 51.3 under another.
- **Nothing is judged on how it looks.** The 20 varied designs looked like real housings and were
  worse than production by up to ninety times.
