# The design space

**Where metal may be added to the engineer's part, derived from their CAD and solver deck.** This
page is the rule set, what each step makes, and how it was measured on the housing. The pipeline that
runs it and shows it is in [pipeline.md](pipeline.md); the code is `src/fastcae/space/`.

---

## What it answers

Before a single design is made, every cell of space round the part is one of: **the part**, **the
inside**, **kept clear** because something else meets the part there - and why - **waiting** on an
answer the files do not give, or **allowed**: metal may go there. Every cell keeps every reason
that applies to it, not only the one that decided it.

It is derived from what the engineer brought and nothing else: the CAD's faces, the solver deck's
groups, supports, couplings and loads tied to those faces, and - when there is one - what the
drawing tolerances. No code names a part's faces; the same rules run on a housing, a bracket or a
box. What the files leave open becomes a **question**, and the engineer's answer is kept with the
part.

The geometry is a grid of cells over the CAD (4 mm on the housing: 41.8 M cells). It only says
**where** metal may go. Every design is still made as its own CAD and meshed from its faces (see
[build-plan.md](build-plan.md)); no cell is ever meshed or solved as a design.

## The steps

Twelve steps, each a rule that holds for any part, each reporting what it made as it finishes:

| step | what it does | what it makes |
|---|---|---|
| **Grid** | the part sampled on one grid; inside and outside exact on a watertight surface | the part in cells |
| **Wall thickness** | at points spread over the whole surface, twice the deepest point straight behind each - a plate reads as its thickness, a solid boss as its width | wall thickness on every face |
| **Interfaces** | faces taken to meet something else, frozen on strong evidence and asked about on weak (below) | interfaces, grouped by what froze them; each face painted by it |
| **What sits round them** | what occupies the space round each interface: what sits in a bore, what mates against a plane over its whole outline - openings in it included - what fits over a boss, a fastener and its tool in and beyond each hole, and a buffer round every frozen face | kept-clear volumes; round an asked face, waiting volumes |
| **The inside** | the air flooded from the grid's edge, with what sits in each bore, boss and hole as a lid, and what mates against a plane as deep as a cover (two cells) - never the whole space in front of a face. What the flood cannot reach is inside; every swept cell takes the side of the free air nearest it. Probed again with every wall thickened by one to three cells: if the inside grows, it leaks through narrow openings | the inside, and the air behind narrow openings |
| **Beyond each bore** | along each bore's axis past each end, to the first free air: toward the outside what sits in it carries on at full radius; toward the inside a shaft carries on at 60 % of it, unless the bore is a register (shallower than a tenth of its diameter), where nothing passes | a continuation for each bore end |
| **Sealing walls** | faces with the outside in front and the inside behind: no through-holes there | the faces that hold the inside |
| **Where metal could go** | a layer over every wall but a frozen one, three local wall thicknesses deep, and the pockets between features that a ball of four local wall thicknesses cannot enter | the candidate layer and pockets |
| **Allowed, forbidden, waiting** | the candidate space minus everything kept clear is allowed; what an unanswered question covers waits | the design space: allowed and waiting |
| **Height straight out** | from points on the free wall - no interface, frozen or asked - straight out along the normal, how far metal may go before it leaves the allowed space | the height cap on every face |
| **Symmetry and questions** | mirror planes and how much of the surface each maps onto itself; a question for every interface in doubt, the inside, the inner walls, holes whose tool has no room, and walls thinner than two cells | mirror planes, questions |
| **Where metal helps** | when the deck can be solved: the part alone under the deck's loads and supports, then the allowed space solved with its surface pinned to how the part moved; the strain energy a cell would carry as metal | the benefit of metal on the allowed space |

Inside and outside: metal is added **outside only** by default; the inner walls take metal only
when the engineer answers so, clear of what sits in and passes through each bore.

## Evidence: frozen, asked, released

An interface is **frozen** - the space round it kept clear - on evidence that something meets it:

| evidence | source |
|---|---|
| the deck loads it (a coupling carries a load, or its reference does) | deck |
| the deck holds it | deck |
| the drawing tolerances it | drawing |
| a hole the deck holds opens onto it - the plane a held bolt clamps | deck |
| the engineer said something meets it | engineer |

It is **asked about** on evidence that only suggests it:

| evidence | source |
|---|---|
| an exact plane or cylinder with sharp edges all round, where a casting leaves fillets | rule |
| a plane a pattern of holes the deck does not mention opens onto | rule |
| a bore the deck does not mention | rule |

A machined-looking face smaller than 40 × 40 mm is counted, not asked. Each interface keeps every
piece of evidence with where it came from - a deck group, a drawing control, a feature - so it can
be followed back to the file.

**Answers**: *freeze* adds the engineer's word as evidence; *free* releases the interface - it is no
interface any more, the space in front of it is candidate space again, and it stays listed as
released so the answer can be taken back. Answers are decisions, kept in the project's
`project.json` beside the roles; the design space is derived again to apply them. *Inside too*
lets metal go on the inner walls.

## Kept once, derived once

A derived space is kept in the project's `.fastcae/` with its record of every step. The key is the
project's files byte for byte, the rules' settings, the answers that apply, and the code that ran
them; while none changes it is read back in about a second - the steps replayed as read back -
and otherwise derived again. The part's grid is kept on its own, so a change of rules does not
rebuild it.

While a space is derived, each step's volumes are available as soon as the step has made them: the
design-space view fills in step by step, and the pipeline shows each step start and finish.

## On the housing

The GRC housing, rib-free (`housing_baseline.brep`), with its Code_Aster deck and drawing, at 4 mm:

| | |
|---|---|
| grid | 41.8 M cells, 2.7 s (the part's field kept) |
| interfaces | 62 frozen - 6 loaded by the deck, 25 held, 29 planes held bolts clamp, 2 toleranced on the drawing - and 34 asked |
| kept clear, near the part | 250 L; 525 L waiting round the faces in doubt |
| the inside | closed, 523 L with its lids |
| bores | 18 of 20 carry on past an end |
| sealing walls | 47 faces |
| candidate | 210 L layer, 4 L pockets |
| design space | 110 L allowed, 60 L waiting |
| height straight out | median 35 mm from the free wall |
| symmetry | best mirror plane matches 24 % of the surface: no symmetry assumed |
| questions | 37: 34 about faces, the inside, the inner walls, the grid |
| where metal helps | the part 18 s by CG on 1.08 M unknowns, the allowed space 2-3 s; the part's largest movement 16 mm on the grid - the deck's own answer moves the main seat 22 mm on the rib-free part, 0.42 mm on the production part |
| whole run | 79 s the first time; read back in about a second |

**Against the production housing's ribs.** The production housing (`254492_0_closed_volume.step`)
has nine ribs, 6.6 L, and **all nine are inner webs** joining the main seat's ring to the barrel and
the rear wall - so outside-only covers none of them. With the inner walls allowed, three wall
thicknesses deep, 60 % of the production ribs' volume lies in the allowed space and 75 % in allowed
or waiting space; five thicknesses deep, 78 % and 99 %, at 457 L. The pocket reach changes nothing:
what is not covered is the middle of tall webs, open along the axis. The ribs sit 2.5 times more
often than chance in the quarter of the allowed space where metal helps most. Every measurement, and
how it was made: [research/design-space-on-the-housing.md](research/design-space-on-the-housing.md).

## Limits

- **Only three evidence kinds freeze.** A face the deck does not touch and the drawing does not
  tolerance is at most asked about, however sure its shape makes it.
- **The grid sets the smallest opening.** An opening narrower than about two cells reads as closed;
  walls thinner than two cells are reported as a question.
- **Bores carry on straight.** What passes through a bore is a cylinder along its axis; a shaft that
  steps or a gear beside it is not known.
- **Where metal helps is a preview**, from one solve of the part on the grid - never a design's
  answer.
- **What turns inside is not known.** Gears, the planet carrier and every other part inside are in
  neither the housing's CAD nor its deck; inside, only each bore's bearing and a shaft through it are
  kept clear. Designing the inside needs the whole gearbox in context - the assembly, each rotating
  part swept round its axis.
- **Memory.** At 4 mm on the housing the derivation peaks at about 7 GB. On a 16 GB machine with
  other applications open it pages out and runs 5-10 times slower; the first run on a project also
  builds the part's grid, 2-4 minutes.
