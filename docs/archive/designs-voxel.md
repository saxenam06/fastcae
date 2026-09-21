# Designs

**Designs made in the design space, each taken through five stages - optimise, ribs, CAD, mesh,
solve - and every stage in view.** A campaign makes one design for each load mix the deck offers at
each volume of metal; every number that becomes data comes from the design's own CAD, meshed and
solved as the deck was. The code is `src/fastcae/designs/`; the routes are `src/fastcae/api/designs.py`.

---

## The five stages

| stage | what it does | what it keeps |
|---|---|---|
| **Optimise** | where metal goes for the load mix and the volume of metal, on the voxel grid, only where a candidate rib plane crosses the design space (below) | the layout at every iteration; where metal could go; the history - volume, each case's compliance against the bare part's, cells changed, solver iterations, seconds |
| **Ribs** | each plane's metal read as plates in that plane: its outline where the metal lies - any shape, with the holes the metal leaves - one rib thick; where the design space is only half a rib deep - one of the optimiser's cells, beside a bore's room or the space the parts inside need - the metal left is read again as plates half as thick, in whichever half of the slab it fills; a plate that reaches the part is a **rib**, its foot sunk into the wall; one that does not is a **web**, standing on the plates it meets; no plate reaches outside the part and the design space | every plate's outline, holes, plane and thickness; how much of the optimised metal the plates cover |
| **CAD** | every plate a solid - its outline, less its holes, extruded through its thickness - fused into the part's own B-rep by OpenCascade plate by plate, no fillet after - one boolean taking every plate at once ran nearly three minutes on the housing and handed back no solid; a result BRepCheck faults - most often the boolean's loose tolerances where a plate crosses curved faces - mended by ShapeFix; every result one solid holding the whole part; a plate that stood apart tried again once others have joined; a plate that does not fuse is left out and said so; a design none of whose plates fuse is rejected, never meshed from anything else | the design's STEP and BREP; its faces for display |
| **Mesh** | the design's CAD meshed face by face, exactly as the deck's own mesh was ([simulate.md](simulate.md)): gmsh on every face, 20 mm most and 4 mm least, curved edges 12 elements a turn; second-order tets, the mesher stopped past ten minutes. A design whose surface does not close into tets, or whose mesh is more than the card can solve - past about 305,000 elements (1.65 M unknowns) cuDSS fails on an 8 GB card, part of its factor in host memory or not - is built again from the larger three quarters of its plates, then half, then a quarter, and meshed again; the CAD stage says so | the mesh |
| **Solve** | the deck's supports, couplings and loads carried onto the design's mesh by CAD face, solved by cuDSS | displacement and von Mises stress at every node; the deck's signals beside the bare part's |

Voxels only find **where** metal goes. The design is its CAD; its answer is the solve of that CAD.

## Load mixes and volumes of metal

What a design is optimised for comes from the deck, never from what the part is for:

- **the deck** - its own load case;
- **each line of shafting alone** - the loaded groups that share an axis, the deck's loads on them only;
- **the lines** - every line of shafting as a case of its own, carried together: the objective is
  the mean of each case's compliance against the bare part's under that case.

Volumes of metal are shares of the part's own: 5 % and 10 %. A campaign is planned as every mix at
every volume; the engineer picks which to make.

## Where metal can go: the rib planes

A casting is stiffened by ribs - flat plates of about the wall's thickness standing on its walls -
so the optimiser is given only places a rib could stand: candidate planes (`src/fastcae/designs/planes.py`),
each a slab one rib thick, crossing the design space.

- **Across** - planes square to each of the part's three axes, three ribs' thickness apart - room
  for the mould between them - one through the part's centre;
- **Spokes** - planes through the axis of each loaded line of shafting, every 30° around it, out to
  six walls beyond its bore.

A rib is the part's wall rounded to the optimiser's cells. Where metal can go is the design space on
the planes, a cell of the optimiser's only where all of it lies in the part or the design space - a
cell reaching even in part into a bore's room or the space the parts inside need would stiffen the
voxels where no CAD can follow. Whatever the optimiser chooses there is ribs already, and each
plane's share is read as plates in that plane. Metal chosen freely in the design space hugs the
part's curved walls, and flat plates read from it leave the design space or drop most of the metal.

What the voxels promise is what the CAD can build: on the housing, the voxel model with only the
plates' metal moves each bearing as the design's own CAD solved on TET10 does, to within a few
percent - so where a design falls short of its optimisation, the ribs stage says by how much.

## Optimisation on the voxel grid

Bi-directional evolutionary optimisation (BESO), hard-kill, on the design space's grid coarsened to
8 mm: the structure is always the part and whole cells of added metal, so every solve is as well
conditioned as the part's own (a structure of soft cells never converges at this size - measured on
the design space's preview). Each iteration solves the structure under every case of the mix
(Warp, conjugate gradients, warm-started), then scores every cell of added metal by the strain energy
it carries, and every empty cell where metal can go by the strain energy it would carry if it were
metal - those cells solved as a body pinned to how the structure moved. Scores are smoothed over a
12 mm sphere and averaged with the last iteration's; the volume grows by a fifth of the target an
iteration; the cells scoring highest make the next layout, kept only where they join the part
through a face - a cell held by an edge or a corner is a hinge - and topped up with the best cells
that do, so the volume is what was asked. Once it is reached, a cell already metal is favoured a
little and an iteration may add at most a tenth of the volume, so the layout settles; it stops when
the objective has settled or not bettered its best for four iterations, or after 14, and the best
layout at the full volume is kept. Each solve, warm-started from the last iteration's, stops when
its residual is a ten-thousandth of the loads'; the history records whether it got there.

## On the screen

**Generate · Campaign** - the campaigns kept, on the left; a campaign as a grid on the page, a
design a row and a stage a column, each cell saying where that stage is and what it found, filled in
as the designs are made; under it, what each solved design bought - metal added against the deck's
strain energy left, the bare part at the top. **+ new** shows the plan - every mix at every volume - to choose from and
launch; the runner makes them.

**Generate · Designs** - one design, stage by stage, on the canvas each stage belongs to:

| view | shows |
|---|---|
| **Optimisation** | the metal added at any iteration - a slider and play through the iterations - on the rib planes where it could have gone, beside the history: compliance against the bare part's and metal added, iteration by iteration, cells changed, solver iterations and seconds; the part and the design space can be shown with it |
| **Ribs** | the metal and the outline of every plate read from it, holes and all |
| **CAD** | the design's new faces over the part; its STEP to take away |
| **Mesh** | the design's second-order mesh, with its edges |
| **Solve results** | von Mises stress or displacement on it, from cuDSS |

The card on the right: what the design was made for - its load cases and volume of metal - each
stage's numbers, the rib planes and how much of the design space lies on them, its plates and the
plane each stands on, and the deck's signals on the design beside the bare part's.

## Kept

A campaign is a folder of designs under `_archived_designs/<project>/campaigns/`, beside the folder
projects live in - never in the project's own folder, which holds only what the engineer brought and
decided. A design is a folder: `design.json` - what it was made for, the rib planes, where each stage
is, what each found - and what each stage made: `optimise.npz` (every iteration's layout and where
metal could go), `fine.npz`, `plates.json`, `design.step`, `design.brep`, `cad.npz`, `mesh.npz`,
`result.npz`.

The runner makes a campaign as a job (`designs.campaign`), design by design, one GPU user at a time.

## Over HTTP

| route | what |
|---|---|
| `GET /api/campaigns` | every campaign, each design with where each stage is; the job making one |
| `GET /api/campaigns/plan` | every load mix the deck offers at every volume of metal |
| `POST /api/campaigns` | a new campaign of the designs chosen from the plan, made by the runner |
| `GET /api/designs/**The campaign** on the 48 mm planes - the deck's case at 5 % and 10 % of the part's volume,
each line of shafting alone, and the three lines as cases of their own - each design its own CAD,
second-order tets face by face, the deck carried on, cuDSS. *Voxels* is the optimisation's
compliance against the bare part's; *strain energy* and *largest displacement* are the deck's on
the design's own mesh, as shares of the bare part's. A design keeps the plates that fit the card:
the larger ones, until its mesh is small enough to solve.

| design | metal | voxels | plates, metal held | CAD | TET10 | strain energy | largest displacement | kg |
|---|---|---|---|---|---|---|---|---|
| deck · 5% | 6.1 L | 48% (9 it.) | 48, 64% | 24 fused, +4.2 L | 299,362 | 39% | 72% | +31 |
| deck · 10% | 12.2 L | 46% (9 it.) | 48, 51% | 12 fused, +4.1 L | 298,458 | 40% | 73% | +31 |
| line 1 · 5% | 6.1 L | 48% (9 it.) | 48, 60% | 24 fused, +4.0 L | 299,648 | 39% | 72% | +29 |
| line 2 · 5% | 6.1 L | 80% (13 it.) | 48, 56% | 12 fused, +3.2 L | 297,641 | 92% | 97% | +24 |
| lines · 5% | 6.1 L | 79% (13 it.) | 48, 56% | 10 fused, +3.9 L | - | not solved - mesh: RuntimeError: gmsh produced no tetrahedra from the repaired  |  |  |
| line 3 · 5% | 6.1 L | 81% (9 it.) | 48, 70% | 12 fused, +5.4 L | - | not solved - mesh: design.brep: gmsh left faces unmeshed - 1 holes MeshFix woul |  |  |

**Per bearing** - each seat's tilt under the deck, as a share of the bare part's:

| design | AX1_S1 | AX1_S4 | AX2_S2 | AX2_S3 | MAIN_S2 | MAIN_S3 |
|---|---|---|---|---|---|---|
| ribs 48 mm apart: deck · 5% | 73% | 90% | 70% | 90% | 95% | 44% |
| ribs 48 mm apart: deck · 10% | 95% | 98% | 89% | 98% | 96% | 90% |
| ribs 48 mm apart: line 1 · 5% | 73% | 95% | 69% | 91% | 95% | 50% |
| ribs 48 mm apart: line 2 · 5% | 100% | 88% | 99% | 89% | 99% | 99% |
