# The design space on the GRC housing: what was measured

The derived design space ([../design-space.md](../design-space.md)) run on the rib-free GRC housing
with its Code_Aster deck and drawing, and checked against the production housing's own ribs. Every
number here was measured on this workstation (RTX 5060 Laptop 8 GB, 16 cores, 15.7 GB RAM) at 4 mm
cells unless it says otherwise.

---

## The production ribs are inside

The production housing (`assets/_archive/254492_0_closed_volume.step`) has nine ribs, 6.6 L in all,
found as the metal the finished part has and the rib-free baseline does not. **All nine are inner
webs**: they join the main seat's ring to the barrel and to the rear wall, inside the housing. None
is on an outer wall.

So a design space that only grows outside cannot reach any of them, however it is tuned:

| design space | allowed | waiting | production ribs in allowed | in allowed or waiting |
|---|---|---|---|---|
| outside only, pockets c = 4 | 106 L | 30 L | 0 % | 0 % |
| outside only, c = 6 | 106 L | 30 L | 0 % | 0 % |
| outside only, c = 8 | 106 L | 31 L | 0 % | 0 % |
| inner walls too, 3 walls deep, c = 4 | 280 L | 99 L | 61 % | 77 % |
| inner walls too, 3 walls deep, c = 6 or 8 | 280-281 L | 99-100 L | 61 % | 77 % |
| inner walls too, 5 walls deep | 457 L | 176 L | 78 % | 99 % |

After the lids were made two cells deep along each face (below), inner walls 3 deep came to 60 % and
75 %. The pocket reach c changes nothing: what the layer does not reach is the middle of the tall
webs, far from every wall and open along the axis, not a pocket between features. Rib by rib, 3 walls
deep covers 42-87 % of each; 5 walls deep 62-99 %.

## Where metal helps

The physics preview solves the part alone under the deck's loads and supports, then the allowed space
as a separate body pinned to how the part moved, and reads the strain energy each cell would carry as
metal:

| | outside only | inner walls too |
|---|---|---|
| grid | 8 mm cells | 8 mm cells |
| the part | 276,537 cells, 1.08 M unknowns | same |
| the allowed space | 215,229 cells, 0.86 M unknowns, 44,724 nodes on the part | 561,397 cells, 2.13 M unknowns, 106,409 nodes on the part |
| time | 22 s | 31 s |
| the part's largest movement | 16.1 mm | 16.1 mm |

The production ribs sit in the quarter of the allowed space where metal helps most 2.5 times more
often than chance: 38 % of their volume is there, where ribs spread evenly over the allowed space
they reach (61 % of their volume, inner walls 3 deep) would put 15 %.

**One solve with a soft filler does not converge.** The allowed space solved together with the part
as a very soft material took 60,000 CG iterations and an hour without converging: the stiffness jumps
by orders of magnitude between the two. Solving the part first and the allowed space pinned to it
after converges in about 20 s and 2 s.

**The rib-free part is soft.** In the deck's own answer the main seat moves 22.3 mm on the rib-free
baseline and 0.42 mm on the production housing: the ribs carry the load.

## What it costs to derive

| | |
|---|---|
| the grid | 41.8 M cells; 2.7 s once the part's field is kept, 2-4 minutes the first time on a project |
| the whole derivation | 79 s with the field kept and memory free |
| read back while nothing changed | under a second |
| peak memory | about 7 GB in the server's process |
| on 16 GB with a browser, two editors and the rest open | 8.5 minutes: 4 GB of the process paged out, every step 3-7 times slower |

The derivation holds many full grids at once - distances in floats, masks, and nearest-cell tables
of about half a gigabyte each. Cutting the peak - freeing each as soon as it is used, smaller types,
slices - would keep it in memory on a 16 GB machine.

## A part made to fail it: a closed box

A box with 12 mm walls, a bore through two opposite walls and four holes in its lid, no deck, no
drawing. Every face is an exact sharp-edged plane, so every face is asked about and the space in
front of each waits. When what mates against a plane was taken as a lid over its whole depth, those
lids filled the whole inside and the whole outside: the inside came out empty and the band had no
wall left to grow from. Taken two cells deep along each face's own normal - as deep as a cover -
the box's inside comes to its true volume (5.2 L), both bores carry on outside and as a shaft
inside, and its six outer walls hold the inside. On the housing the same change moved the inside to
523 L with its lids and let 18 of 20 bores carry on past an end, where 10 did before.

## What the housing cannot say

**What turns inside.** Gears, the planet carrier and every other part inside the gearbox are in
neither the housing's CAD nor its deck. Inside, the derivation keeps clear only each bore's bearing
and a shaft at 60 % of its radius; a design space that reaches the inner walls - where the production
ribs are - can therefore run through where a gear turns. Designing the inside of a housing needs the
whole gearbox in context: the assembly, each rotating part swept round its own axis and kept clear.
The GRC's parts are in `cae-data` as SolidWorks files (149 parts, 30 assemblies; only the planet gear
as STEP), so they need exporting to STEP first.
