# Status

**This file describes what is true now.** Superseded content is deleted, not annotated.

---

## Where it stands

**Input** runs end to end on any part. Opening a project runs **one pipeline**: the engineer's files
read - the CAD, the drawing, the solver deck and its results - and, last, the **design space**: the
one volume round the part where metal may be added, read from the project's folder or, where the
engineer brought none, defined there by fastcae's rules ([design-space.md](design-space.md)). Every
step's inputs and outputs are typed entities; the rail shows the steps, the canvases what is in
focus, the card on the right the entity in full, and the agent reads the same entities
([pipeline.md](pipeline.md)).

**Design volumes** are where the engineer allows metal: on the CAD they pick a face - the floor
ribs would stand on, the ring or boss they would grow from - and see at once the closed volume it
bounds, the part's own faces round it, up to the height they set, every interface kept clear; they
keep the volumes they mean ([archive/rib-families-plan.md](archive/rib-families-plan.md)).

**Generate** makes a **rib network** in the kept volumes: one constrained problem, held to the
**target** (the production housing, an input solved exactly as a design is). A seeder proposes fins
- spokes, a ring of chords, tangents, a wheel, a random scatter - and one gate of placement admits
them, all at **20 mm**, the one section the production housing casts; an optimiser moves every
fin's ends, curve and heights on the voxel model under the target's metal with the clearance and
spacing rules held; CP-SAT keeps the network, each fin valued by the objective's own derivative with
the rest standing; and the network is built - each fin a swept solid rooted in its walls, fused into
the part's own STEP, meshed face by face and solved by cuDSS. Every stage is read against the target,
a check after every stage stops a design that would carry a flaw on, and a run passes only if its
design beats the target with no more metal ([designs.md](designs.md),
[rib-network-status.md](rib-network-status.md)).

Every solved design keeps **all 16 of the deck's load components** - each one's whole displacement
field and how each bearing moved and turned under it - so any load case and any objective built from
the same signals can be read afterwards without solving again. The study's load cases are data
(`loads/cases.json`). A campaign makes one network, unattended, on the runner
([design-generation.md](design-generation.md), [designs.md](designs.md)). **Simulate** is in Input's Mesh & setup: the deck's setup, and its
results - the engineer's Code_Aster run and cuDSS on the same mesh - as tabs. Learn and Optimize are
visible and not built.

What runs:

- **Four tabs** - Input (Drawing, CAD with *Part*, *Design space* and *Design volumes*, Mesh &
  setup with *Setup* and *Solve results*), Generate (Campaign, Designs - with a design's Optimisation, **Path**, CAD, Mesh and Solve results), Learn, Optimize.
- **Design volumes on the CAD**: a click on a face proposes the volume it bounds in a second or two,
  see-through over the part; its band along the axis on two sliders; what it keeps clear as pills
  to switch; kept volumes listed, shown or hidden, deleted. Found in flat slices of the part's own
  surface, never by solid booleans on the whole part.
- **The section tool** on every 3D canvas: a plane square to X, Y, Z or the view, tilted, moved,
  flipped; cut faces hatched; on the deck's and a design's mesh the slice through the elements,
  with the field shown on it.
- **The pipeline**: the extraction's ten steps and the design space, each with its status, its time
  and a line on what it found; opened, what it read and what it made.
- **The design space on the CAD**: one volume, opaque, in its own green; switches for the part, the
  design space and where metal helps, as the deck's view has its own.
- **Solve results**: the deck's own mesh - face by face from the CAD - with Code_Aster's answer, and
  cuDSS's on the same mesh a tab beside it, solved on the runner at a click.
- **Campaigns**: a new one planned from the kept volumes, the target it is held to - the cap and
  the pass line - and the seeder, as pills; made by the runner in the background, its stages filling
  the grid as they finish, and a chart of what each design bought: metal added against the deck's
  strain energy left.
- **Designs**: a network campaign shows its nine stages - Seed, Pass, Oracle, Chooser, Polish,
  Path, CAD, Mesh, Solve - the first five as fins drawn on the part in the colour of their fate,
  with the reasons tallied and the pass's and the polish's histories; then the CAD's new faces with
  its STEP, the second-order mesh, the stress and displacement from cuDSS - and a card with every
  stage's numbers, the network against the target on the cubes and on the mesh, what the gate of
  placement refused, every fin's fate, and the deck's signals beside the target's and the bare
  part's. Campaigns made the older ways still open ([designs.md](designs.md#on-the-screen)).
- **The agent**, above every tab: reads the pipeline, its entities, the part and the drawing, and
  shows what it talks about. It never makes geometry or designs.

## On the housing

The GRC housing, rib-free (`housing_baseline.brep`), with its Code_Aster deck and drawing.

**The deck** is the housing meshed face by face (281,132 second-order tets, 1.47 M unknowns) with
agenticCAE's supports, couplings and load case; a narrow face's rim is divided to its width, so the
2 mm fillet round the flange and the 5 mm fillet strips on the barrel mesh without needles
(0.03 % of tets below quality 0.1, none inverted). Code_Aster solved it in about 3 min; cuDSS on the
same mesh agrees to 5·10⁻¹⁰ in 30 s.

**The design space**, defined by the rules in 81 s: 319 L - 171 L on the outer walls, 148 L on the
inner - clear of 20 bores' bearings, shafts and collars, 67 held faces' mating space, and 206 holes'
fasteners and tools. Read back in about a second.

**The target** is the production housing, kept in the project and solved the way every design is
(face by face, 295,917 TET10, the deck carried by CAD face, cuDSS): its nine ribs add 6.54 L and
47.5 kg and take the largest displacement from 21.8 mm to 0.443 mm, the main seat S2's tilt to
1.91', S3's to 0.67', the strain energy to 3.7 % of the rib-free part's. Its gear-mesh lead is
22.1 µm and its J_robust 3.51. Designs are held to its metal and read beside it.

It is **solved again whenever the mesher or the deck changes**, so the two are always read on the
same footing: the fold collapse added to the mesher moved production's own lead from 24.8 µm to
22.1, and until the target was re-solved every design was being flattered by about three points.

**Design volumes**, picked on the CAD: *S3 ceiling* - the two halves of the ceiling round the rear
seat S3, 25.5 L, holding 94 % of the production ribs there; *S2 ring* - the upwind seat's ring, set to
the production ribs' height (z 24-161 mm), 35.4 L, holding 71 % of them (the rest stands where the
rules keep the Ø1030 register and a Ø610 recess clear). Each found in 1-3 s once the part's
keep-outs are known (10 s, once).

**Rib networks**: the latest, launched from the product, reads **0.359 mm largest displacement
with +30.1 kg against production's 0.443 mm with +47.5 kg** on the solved mesh, all 18 of its 18
ribs built; its strain energy is 4.3 % of the bare part's against production's 3.9 %
([rib-network-status.md](rib-network-status.md)).

**The methods before it**: 152 designs solved, 46 better than production's J_robust; the best held
the gear mesh's lead at 2.7 µm against production's 22.1 with 41 % less rib metal. Two results
decided what was built next:

- **Chosen for physics, by gradient**: five sets polished by geometry projection, four solved,
  **all four beat production** (-6 % to -47 %). The fifth was rejected at the fuse.
- **Chosen for variety, not physics**: 20 designs picked to be as unlike each other as a library of
  forms allowed, 18 solved, **every one worse than production** - up to 21 mm of deflection against
  production's 0.443.

And no design yet is robust: of 29 scored under 12 load cases, **none** beats production's lead
under all of them; the best on the deck's case (-88 %) is +488 % when the rotor's bending is turned.
Production's own lead reads 7.9 µm under one defensible case and 51.3 under another, so a percentage
against it needs its case named ([design-generation.md](design-generation.md),
[rib-optimisation-plan.md](rib-optimisation-plan.md)).

Earlier, from the production-form library held to the target's metal - the agent's six tries on the
deck's case:

| design | ribs | metal | S2 | S3 | AX1 S1 | AX1 S4 | AX2 S2 | AX2 S3 | largest displacement | strain energy |
|---|---|---|---|---|---|---|---|---|---|---|
| **production** (target) | 9 | 6.54 L | 1.91' | 0.67' | 0.37' | 1.23' | 0.83' | 1.45' | 0.425 mm | 1 |
| spokes, webs, mirrored | 16 | 5.89 L | 0.56 | 0.87 | 0.66 | 0.97 | 0.89 | 0.97 | 0.76 | 1.00 |
| free, sized from the AX1 side, T-ribs | 13 | 6.43 L | 0.83 | 0.78 | 0.92 | 0.94 | 0.26 | 0.97 | 1.02 | 1.08 |
| mirrored, sized from S3, T-ribs | 13 | 6.01 L | 0.60 | 0.83 | 0.59 | 0.98 | 0.80 | 1.01 | 0.77 | 1.01 |
| lighter, spread, T-ribs | 13 | 4.58 L | 0.65 | 0.83 | 0.55 | 0.96 | 0.78 | 1.00 | 0.82 | 1.05 |
| free of the mirror | 16 | 5.89 L | 0.83 | 0.79 | 1.05 | 0.92 | 0.17 | 0.93 | 1.03 | 1.07 |
| ten thick ribs | 10 | 5.95 L | 1.29 | 0.83 | 2.37 | 0.88 | 1.01 | 0.88 | 2.21 | 1.64 |

Tilts of the loaded seats, and the rest, as shares of production's (below 1 is better); production's own
in its row.

Four of the five nicest beat production on every seat's tilt; the lightest does it with 70 % of
its metal ([designs.md](designs.md#on-the-housing)).

## Open

- **The shape cannot be nudged.** CP-SAT chooses between ribs at fixed positions; nothing can move
  one. So physics can select a design but never improve it, which is why the only designs that beat
  production came from the gradient route. The plan is to make the parameterisation itself castable
  and differentiable ([rib-optimisation-plan.md](rib-optimisation-plan.md)).
- **A notched outline becomes a sliver face.** A rib's outline follows every small step of the wall
  it sinks into - 7 to 31 stepped edges a rib - and the fuse turns those into faces under 5 mm².
  That check, not meshing and not CP-SAT, is where the gradient route lost its gains: 25 of 30
  rejections. Smoothing the metal boundary would fix the notches and the slivers together.
- **Nothing measures a bore going out of round.** Every bore reading passes through a coupling that
  reduces it to six rigid numbers. A hoop rib exists mainly to stop ovalisation, so no optimiser can
  produce one: it cannot see the benefit. The measure is arithmetic on fields already stored.
- **Three forms float.** `island`, `arc` and `run-out` as generated today are 17 %, 23 % and 40 % of
  their outline attached, against 47-50 % for a web, because they were built on a measurement that
  asked the wrong question. They are retired; their shapes return properly rooted.
- **A rib network is one constrained problem, and its rules are kept where fins are placed.**
  Every seeder - spokes, a ring of chords, tangents, a wheel, a random scatter, load-path members -
  goes through one gate of placement: across the volume's own air and never over a bore, square
  enough to its walls, a wall to root in, its middle clear of the metal by the measure the pass
  itself holds, apart from the fins already placed but for a root they share, and passed by the
  CAD's own sections. The pass then moves each fin inside bounds under the target's metal as a
  binding cap; a **chooser** (CP-SAT) values each fin in the company of the rest, by the
  objective's own derivative, and a fin it drops on value alone is measured back in; an
  **oracle** reads every fin before any boolean and should find nothing. Each stage is read
  against the target on the cubes, and a run passes only if its design beats the target with no
  more metal ([rib-optimisation-plan.md](rib-optimisation-plan.md) §2.6, §5). Measured on the
  housing, 2026-09-21: 18 spokes seeded, 18 past the oracle, 14 kept, 14 of 14 built, meshed and
  solved in under fifteen minutes - **largest displacement 0.416 mm with +22.1 kg against
  production's 0.443 mm with +47.5 kg**; its strain energy is still 4.7 % of the bare part's
  against production's 3.9 %. Corner faces under 5 mm2 where a sunk end meets its wall remain,
  22 on that design; they are reported, and the mesh's own checks decide.
- **The cubes flatter a rib network.** On 10 mm cubes production reads 0.374 mm against 0.443 mm on
  the mesh, a factor of 1.18; rib networks read 1.3 to 2.3 times lower than their meshes, because
  the cubes over-stiffen thin webs and count rib depth that attaches to nothing. The run learns a
  margin from every solved design; until that spread narrows it informs and does not gate.
- **A rib's height is read once.** An end is capped by the metal it roots in - read from just
  inside the wall's face, so a 15 mm wall with a low flange behind it is not overshot - and the
  middle by the roof over it; an end on a boss covers at least 80 % of the boss; the builder
  draws the ends at the optimiser's heights under the same caps
  ([rib-optimisation-plan.md](rib-optimisation-plan.md) §10).
- **Keep-outs against practice.** Two rules keep clear space the production housing's S2 ribs use:
  the Ø1030 register's whole disc over its depth, and a Ø610 recess read as a bore. Both can be
  switched off for a volume; whether they should be kept by default is the engineer's call.
- **Symmetry is offered, not measured to be exact**: the housing maps about half its surface across
  its best plane; the engineer turns it on or off.
- **Plates the card can solve.** A design is built from at most as many plates as keep its mesh
  within what cuDSS factors on an 8 GB card (about 305,000 second-order tets); the smallest go
  first, so part of the optimised metal is never built. A bigger card, or a solver with its factor
  out of core, lifts it ([designs.md](designs.md#on-the-housing)).
- **What turns inside** - gears, a carrier - is not known until the whole gearbox is read; the inner
  layer three walls deep stands in for the room they need.
- **Associations on the drawing** are unconfirmed; single holes are not yet matched to callouts.
- `mypy --strict` is configured and does not pass.

## Decisions in force

| decision | choice |
|---|---|
| Project | a folder under `assets/`; its name is the folder's name. Folders starting `_` or `.` are set aside |
| What a project holds | the engineer's CAD - no ribs - drawings, solver deck and results, and the design space. No reference part, ever |
| `project.json` | decisions only: the baseline's role |
| The pipeline | the engineer's files read, the design space last; every step's inputs and outputs typed entities with an origin, evidence and links read both ways; the same entities for the rail, the canvases, the card and the agent |
| The design space | one volume, taken as defined - kept in the project's folder; where none is brought, defined by rules that hold for any part: a layer three walls deep over every wall, outside and in, and the pockets between features, clear of every bore's bearing, shaft and collar (outside the bore), of what mates against faces the deck or the drawing holds, and of every fastener and its tool |
| Designs | a rib network in the design volumes the engineer kept: fins placed by one gate of rules, moved by an optimiser on the voxel model under the target's metal - the voxel model only says where metal helps - chosen by CP-SAT; every design its own CAD - each fin a swept solid rooted in its walls, fused into the part's B-rep, no fillet after - meshed face by face as TET10 by the deck's recipe, the deck carried by CAD face, solved by cuDSS; a failed fuse or mesh stops the design, never meshed another way |
| Training data | never from cells, shells or a field: only designs made as CAD and meshed from their faces |
| The part's material | fixed: a part is cast in one material |
| Simulation | agenticCAE's load case, material and supports - kinematic couplings at the bolts, distributed couplings at the bearing bores, loads at their centre nodes; cuDSS on the GPU, Code_Aster the reference; PETSc not used |
| Meshing | `simulate/face_mesh.py`: gmsh on every CAD face, 20 mm most and 4 mm least, curved edges 12 elements a turn, faces gmsh cannot parametrise meshed unrolled; agenticCAE's weld, collapse, MeshFix and gmsh tets; gmsh 4.15.2, pymeshfix 0.18.1 |
| The interface | four tabs in the order the work happens - Input, Generate, Learn, Optimize - every one shown built or not; everything marked imported, derived, inferred or generated; the agent's bar above every tab; everything drawn opaque |
| Agent | tools over the pipeline's entities and the part: reads and shows - never geometry, never a design; LangChain on LangGraph, OpenRouter, LangSmith; conversation in SQLite with the project |
| Derived results | cached under `<project>/.fastcae/`, keyed on content and on the code that produced them; a miss is never an error |
| Campaigns | kept under `_archived_designs/<project>/campaigns/`, a folder a design, beside `assets/` |
| Code no longer run | kept whole in `_archived_code/` at its own path, for reference; nothing in `src/` or `ui/src/` reaches it |
| `cadquery-ocp` | pinned at 7.9.3.1.1 |
| Units | millimetres; `xstep.cascade.unit` set explicitly to MM |
| Scale-dependent tolerances | derived from the bounding diagonal, never absolute |
| Ports | API 8021, interface 5183 |
| Checks enforced | `ruff` and `tsc` |
| Version control | source and docs; `assets/`, `tests/` and `_archived_designs/` are not tracked |
