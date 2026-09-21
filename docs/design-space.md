# The design space

**One volume of air round the part where metal may be added - taken as defined, like the CAD.** An
engineer who brings a design space brings it with the part; where none is brought, fastcae's rules
define one from the CAD, the solver deck and the drawing, in the engineer's place, and keep it with
the project. It is then read like any other input: the last step of the pipeline
([pipeline.md](pipeline.md)), shown on the CAD, and what every design is made in
([designs.md](designs.md)). The code is `src/fastcae/space/`.

Designs are no longer made in it: they are made in the **design volumes** the engineer picks on the
CAD ([designs.md](designs.md)), which keep clear by the same rules. It stays the pipeline's last
step, drawn on the CAD with where metal helps.

---

## What it is

Every cell of a grid over the CAD (4 mm on the housing: 41.8 M cells) is one of:

| label | means |
|---|---|
| **design space** | metal may be added here |
| part | the part itself |
| bore | what sits in a bore and passes through it - a bearing, a shaft, a cover - and the collar round its openings |
| mating | in front of a face the deck or the drawing holds: what mates against it |
| ring | round a held boss: what fits over it |
| fastener and tool | a fastener in a hole, and its tool beyond each open end |
| buffer | close to a held face |
| inside | the inside beyond the layer over its walls: room for what turns there |
| open air | beyond the layer over the outer walls |

The kept-clear labels mark only the cells they took from where metal could go, so the grid says why
metal may not go where it otherwise could. The grid only says **where**: every design is made as its
own CAD and meshed from its faces; no cell is ever meshed or solved as a design.

## Kept with the project

A design space is two files in the project's folder, beside the engineer's own:

- `design_space.npz` - the grid, every cell's label, and where metal helps on each cell;
- `design_space.json` - what it holds, the CAD it was defined on, how it was defined (`rules` or
  `engineer`), the settings, every interface it keeps clear round.

It is read back for as long as the CAD it was defined on is the project's CAD - about a second on the
housing. The files are not among the artifacts the extraction reads, so defining it again never
makes the engineer's files look changed. Defining it again replaces only one the rules defined,
never one the engineer brought.

## The rules that define it

The same rules on any part; nothing names what a part is for.

**Where metal could go**: a layer over every wall - outside, and inside the part as well - three
local wall thicknesses deep, and the pockets between features a ball of four local wall thicknesses
cannot enter. Local wall thickness is twice the deepest point straight behind a point of the
surface, held between half and one and a half times the part's typical wall.

**The inside** is the air the grid's edge cannot reach once every opening is capped by what sits in
it: what sits in each bore and fits over each boss, whole; what mates against any plane, as deep as
a cover (two cells); every hole's fastener. The air behind narrow openings - found by thickening every
wall one to three cells and watching the inside grow - is inside too.

**Kept clear**:

- **every bore**, whatever the evidence says about it: what sits in it over its own length; past its
  ends, what carries on - outward at its full radius, inward a shaft at 60 % of it, nothing past a
  register (a bore shallower than a tenth of its diameter); and a collar one wall wide round its
  openings, **outside** the bore;
- **round a face the deck or the drawing holds** - the deck loads it or holds it, the drawing
  tolerances it, a hole the deck holds opens onto it: what mates against it over its whole outline,
  what fits over it, and a buffer one wall deep;
- **every hole**: the fastener in it, and a cylinder 1.8 times its radius and three diameters long
  beyond each open end for its tool.

A face with only weak evidence - one that looks machined, one an unmentioned hole pattern opens onto -
keeps nothing clear: metal may go up to it. So the design space is one volume: nothing in it waits on
an answer.

**What turns inside** - gears, a planet carrier - is in neither the part's CAD nor its deck. The layer
over the inner walls stops three walls deep, which leaves the middle of the inside to what turns
there; the room it really needs comes with the whole assembly in context, not yet read.

**Where metal helps**, when the deck can be solved: the part alone under the deck's loads and
supports on an 8 mm grid, then the design space solved as a separate body pinned to how the part
moved; the strain energy each cell would carry as metal. A value on every cell of the design space,
shown as a heat scale on it - a preview for ranking, never a design's answer.

## On the screen

The CAD tab's **Design space** view draws the volume opaque, in its own green, over the part; three
switches, as the deck's view has its own: **part**, **design space**, **where metal helps**. Hide the
part to see the design space inside it. The rail's last step says what it holds.

## On the housing

The GRC housing, rib-free (`housing_baseline.brep`), with its Code_Aster deck and drawing, at 4 mm:

| | |
|---|---|
| design space | **319 L**: 171 L on the outer walls, 148 L on the inner |
| could go, before what is kept clear | 445 L: 444 L layer, 27 L pockets (overlapping) |
| kept clear of it | 81.5 L round the 20 bores, 20.8 L mating space, 21.5 L fasteners and tools, 1.7 L buffers |
| interfaces | 67 held by the deck or the drawing; 20 bores; 17 faces with weak evidence, which keep nothing clear |
| the inside | closed, 523 L |
| bores | 18 of 20 carry on past an end |
| where metal helps | the part on 1.08 M unknowns, the design space pinned to it: 29 s |
| defined in | 81 s with the part's grid kept (the grid itself 2-4 minutes the first time); read back in about a second |

What was measured on the housing along the way - the production ribs, how much of them each setting
reaches, where metal helps, time and memory, a box made to fail it -
[research/design-space-on-the-housing.md](research/design-space-on-the-housing.md).

## Limits

- **Only held evidence keeps a face clear.** A face the deck does not touch and the drawing does not
  tolerance keeps nothing clear round it, however sure its shape makes it - except a bore.
- **The grid sets the smallest opening.** An opening narrower than about two cells reads as closed.
- **Bores carry on straight.** What passes through a bore is a cylinder along its axis; a shaft that
  steps is not known.
- **What turns inside is not known** until the assembly is read: the three-wall layer stands in for
  the clearance gears and carriers need.
- **Memory.** At 4 mm on the housing the rules peak at about 7 GB; on a 16 GB machine with other
  applications open they page out and run several times slower.
