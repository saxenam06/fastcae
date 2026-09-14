# Ribs: a design space from the engineer's words

**Being built.** How an engineer gets thousands of near-production designs of their own part - ribs,
webs, faces moved, holes - that follow every rule they set, with solver decks, and how what they
object to narrows the next campaign. This file is the design as agreed; [build-plan.md](build-plan.md)
is the order it is built in, and [status.md](status.md) says how much of it runs.

---

## What it is for

Generative design in CAD tools gives a handful of optimal shapes per setup, which someone then
redraws. ZenryxAI gives thousands of near-production variants that already follow the engineer's
rules, with solver decks. A surrogate trained on them finds clusters of designs that do well on
several objectives at once - each a real, castable design - and shows which choices matter for the
next design.

One engine serves four kinds of user: CAE teams who need variants and decks for a study, teams who
need training data for surrogate models, design engineers who want ribs suggested and modelled, and
foundries who want reinforcement that casts.

The engineer brings a structure without the ribs - its CAD as a plain STEP, its drawing, later its
solver deck. There is **no finished version of the part to compare against**: where ribs go comes
from what the engineer asks for, never from another CAD file, and the system never "corrects" the
engineer's part.

1. **Extract** names what the part holds - faces, planar groups, holes, bosses, bores, walls,
   fillets - and what the drawing controls.
2. **Author variants.** On the CAD tab the engineer selects faces and says what to add there - ribs
   on them, webs between them, the faces thickened, holes through a plate. Each **variant** is one
   change in one place, with what it may vary and every rule it must hold, in the part's named
   entities. By hand today; from words too when the model returns - *"ribs between the bearing boss
   and the outer wall, clear of the holes, no taller than the boss"* - written into a variant for
   the engineer to keep.
3. **Compose a campaign** on Generate: the variants it takes, how its designs are drawn and how
   many; a hundred of them screened in seconds before it is launched.
4. **Place, repair and screen.** Each design is a set of the variants at a point of each, placed on
   the part, mended by a solver where its pieces break a rule between them, and checked - a
   fraction of a second a design.
5. **Build and review.** A design's field is built and checked when asked; the designs that differ
   most are shown side by side.
6. **Object.** The engineer rejects what they do not want and says why; the reason becomes a rule of
   the variant it is about, and the next campaign obeys it.
7. **Simulate and learn.** Every design comes with its deck; the results train a surrogate that
   searches the same space for designs that do well on several objectives.

## Variants and campaigns are the truth

A **variant** is one change in one place, written in the part's named entities from what the
engineer selected - and said, when the model returns - citing both:

```
Variant:    k7f3a · Ribs on face:1201
Adds:       ribs
Where:      on face:1201 · ending on the walls round it · clear of the holes through it
Varies:     pattern square grid or free lines · thickness 15–25 mm by 5 · spacing 60–200 mm by 5
            · height 2–5 thicknesses, by halves · root fillet 5 mm
Holds:      5 mm clear of the holes on face:1201 (assumed) · no taller than what each end meets
            · R ≥ 3 (drawing p.1) · room for the sand between ribs, 2 thicknesses (assumed)
            · no X crossings
```

- **Adds** - which kind of change: ribs standing on faces, webs between faces with nothing under
  them, faces made thicker or thinner, holes through a plate. One to a variant; a design takes as
  many variants as it needs. The part is cast in one material, which no variant changes.
- **Where** - the named entities it stands on, ends on or moves, and what it keeps clear of: faces,
  the holes found, the ribs or holes of another variant. Webs have two sides - what they run from
  and what they run to - and every web runs from one to the other, never between two faces of one.
- **Varies** - every setting fixed, a range with a step, or some of its choices, suggested from the
  part and the drawing and citing where from. The patterns ribs may take are choices, so *"only a
  square grid"* is one choice and anything another. A variant counts the distinct designs it
  allows.
- **Holds** - every rule its designs satisfy: placed to them, repaired to them, checked on the
  result. Only rules the pipeline checks are offered. Each has a strength and a source: *hard* -
  the engineer or the drawing said it; *assumed* - a default the part suggested, kept or taken out
  by hand; *learned* - from a rejection the engineer confirmed.

A variant holds no pull direction, preferences or objectives: until designs are simulated nothing
ranks them but their geometry and mass, and the pull comes back with mould release.

A **campaign** is a card - its name, the variants it takes, the screening checks it holds, how its
designs are drawn, how many, from which seed, and whether to draw more and keep the most different -
and nothing else decides its designs. Each design is a set of the chosen variants at a point of
each. A campaign never narrows a variant: to hold a setting fixed, change the variant.

**Variants are edited freely; campaigns keep a copy.** A campaign keeps every variant as it was when
it was launched, with the part's digest and the code's commit, so the same card and seed give the
same designs, and its designs can be built again months later whatever has happened to its variants
since. Every launch is a campaign of its own. A variant's versions exist inside and are never shown;
the library says which campaigns used a variant and whether it has changed since.

**Features are named by id and fingerprint** - kind, size, position - so that when the CAD is read
again and numbers shift, a variant still finds the right faces, or says plainly that it cannot.

**Where they live.** A variant is a file, `<project>/variants/<code>.json`, called by a short random
code and words that say what and where: a study of one block - the same schema, checked by the same
function - with a name. A campaign is a folder, `_archived_designs/<project>/<code>-<name>/` beside
`assets/`, that composes its variants into one study version; a design is one point in it - the
variants it holds and the values each took.

## What the engineer does not say is explored

Anything a variant leaves unstated varies within a range read from the part and the drawing, marked
assumed where it shows: *"height varies from half to all of the support at each end"*. The engineer
fixes or narrows it after seeing samples. A variant waits for the engineer only where a gap would
make every design of it invalid or meaningless - webs with fewer than two things to join, words that
name no region.

What is selected is the scope. Ribs on `face:1201` alone stay there; select both halves of the
ceiling and they may go anywhere on both; keep them clear of the bearing region and they are; say
nothing and they may go there. Whether ribs may span both faces, stay within one, or must bridge
them is a setting of its own - three different design spaces.

**Interfaces are the exception: closed unless allowed.** Bearing bores, holes with room above them
for the tool, datums and machined faces are forbidden to every variant by default, each citing where
it is known from - the drawing's toleranced dimensions and notes, or the geometry. A datum the
drawing names but the system cannot yet place on a face is shown for the engineer to point at.
Forbidding a bore forbids its bearing surface, not the boss round it. Every rib and pad keeps clear
of what is closed in three dimensions, wherever it reaches: a bolt hole in the boss a rib ends on,
reached by the end buried in it, is as much in the way as a hole in the floor. What ribs run
between is theirs to meet.

## One kind of rib: a web between anchors

Every rib is a **web** - a thin plate in a plane - attached to two or more **anchors**, which can be
any named entity: a floor, a wall, a boss, a ring. It grows until it meets the part and is cut back
by the rules - a height limit, keep-outs. A floor rib is a web with a floor along its bottom edge; a
hanging rib, between a ring and a wall with nothing under it, is anchored at its ends; a gusset is
anchored along two edges. None needs a class of its own.

Its **section** is its thickness, a taper along its height or its length, a T or L flange, draft, a
root fillet where it meets an anchor, and an edge round on its free edges. Its **footprint** is what
it takes of the floor: half its thickness at the root and its root fillet each side, or half its
flange where that is wider - everything kept clear of a rib is measured from it, never from its
centre line. Its **plane** is set by the variant or left free: *"parallel to YZ"*, *"vertical in
XZ"*, *"square to face:723"*, *"radial about face:1453"*. **Which way it leaves the mould** - the
pull direction - is said, never assumed from a floor.

## Patterns, never limits

A layout is a **graph**: anchors on named entities, joined by ribs. Spokes are a star, a grid a
lattice, triangles a triangulated graph - shapes of graph, not classes. A variant lays its ribs by
**patterns** - parallel ribs, square and triangle grids, spokes about a boss, and **free lines**:
independent lines, each at an angle of the variant's range and a place across what they stand on,
drawn from a layout seed nobody sets, the same seed the same lines. A grid is one lattice: its
families share a spacing and an origin, so they cross at common points. A pattern is a limit only
when the engineer makes it one: *"a triangle grid only"*.

**How many and how far apart apply to every pattern.** Parallel ribs and grids take at most so
many lines each way, the spacing apart, round the middle of the floor - a spacing alone fills it;
spokes, so many and no nearer than the spacing where they end; free lines, so many, crossing at
places the spacing apart. No setting shown is one a pattern ignores.

**A solver mends what placing breaks.** Each piece of a design - rib, pad, hole - is placed where
its variant says and held to every rule about one piece. Conflicts between pairs are then found
once: two ribs with no room for the sand between their footprints; a wedge where two meet at a
shallow angle - a finger of sand narrower than the root gap for longer than it is wide, or, where
the fillets rounding their corner fill it, a lump of metal that long, two ribs run into one -
judged where their bodies touch in the open, wherever their lines cross; a hole on a rib; a
junction of more than three arms - an X - where a variant forbids them. A constraint solver
(CP-SAT) leaves out the fewest
pieces so that none is left - holes before ribs where it is a tie, a rib taking its pads with it,
the same answer every time. The design says what was left out and why, and a design the solver
cannot save is drawn again. Foundry practice enters as rules: room for the sand between ribs - two
thicknesses by the rule of thumb, suggested for every variant of ribs and measured at the wedges
where ribs meet - and no X crossings, since foundries stagger them into T-junctions, for the
engineer to add.

**To come**: free layouts grown from a graph of legal connections between regions, the solver
choosing which to join with a random objective each time for variety; staggered crossings as a
pattern; and, when nothing fits, the solver naming the assumed rules to blame, for the model to
explain.

Designs are described by what they are, not by which pattern made them: how many ribs, the angles
between them, their spacing, how much of each region they cover, what each connects, the mass they
add. Variety, feedback and the surrogate all work on those properties. *"Sixty degrees between
ribs"* is a property; a triangle grid is one way to get it.

## Where ribs may go

The client may point - *"here and here"* - or leave it open. The system proposes **regions** where
ribs could go - every floor, every bay between walls, the space round every boss - named and shown on
the part, so the engineer picks some or says *"anywhere except the bearing region"*, and rules can
refer to them.

## Screening, building, checking

Cheapest first:

1. **Screening**, a fraction of a second a design: placement, repair, and every check that needs no
   geometry - every variant in the design making something, ribs against the floor under them,
   room for the sand between ribs and at their wedges, holes a ligament clear of ribs, walls thinned
   no further than they may be.
2. **Building**, seconds a design: the part and its changes as a distance field - mended as it was
   screened - and the checks on geometry, each read off the field and timed: fillets achieved,
   thick spots, nothing floating, protected areas unchanged, holes through. Its surface is drawn when
   someone opens it, and checked closed then.
3. **Simulation**: the decks solved.

A **preview** builds a design on a coarser grid, nothing else relaxed, and is always labelled one; a
**full** design is built at the design grid, and only a full design can be accepted.

Every design comes with a **verdict** in two parts, and every rule and check applied is listed, so
it can be audited. **Your rules**, each enforced while the design is built and verified on the
result: *"keep out - pass, nearest hole edge 7.2 mm."* **Engineering checks**, which the platform
holds every rib to whether or not anyone asked: the fillet achieved, thickness against the wall,
thick spots at junctions, gaps between ribs, nothing floating, protected areas unchanged, holes
open through their plate, the surface closed where one is drawn - and mould release, once the pull
is known. Each says how long it took. Thresholds come from the variant; any
the engineer did not set is marked assumed. A check is code, shown to fail on a part built to make
it fail before it is trusted, and added between sessions - never by a model at runtime. A model that
could write its own checks could write one that passes everything.

## Variety

Every free setting has a **step** - five in its own unit unless the engineer says otherwise - so a
spacing of 100 mm and one of 101 mm are one design, not two, and designs alike in every rib, pad,
hole and face moved are kept once. A campaign spreads what it draws: as many designs with one of its
variants as with two or all of them, and the points of each spread evenly over what it allows.
Asked to, it draws two to five times as many and keeps the most spread out, in a space of
properties - rib count, total length, which entities are tied, orientations, added mass. If the
rules leave fewer truly different designs than were asked for, the campaign says how many: the
count is a result, not a target. Every campaign measures its spread - how each setting spread, how
many distinct rib layouts, how far each design sits from its nearest neighbour.

With the review loop, every design's margin against every rule is kept, so any proposed rule shows at
once how many designs it would remove - its **kill count**.

## Review, and objections that become rules

The engineer sees about 20 designs a round - the most representative of a campaign - each with a
picture, what it is, the assumptions it used, and accept or reject, and any design on the part with
its verdict. The thousands behind them are the surrogate's training set; nobody browses them.

**Rejecting asks why, and where.** The engineer points at the rib they object to, or picks between
two designs that differ in one thing - which pins the reason down in far fewer questions than a yes
or no on whole designs. The model offers one to three readings as rules in named entities - *"no rib
within 30 mm of face:1453"*, *"ribs parallel to XZ only"*, *"spacing at least 120 mm"* - each with
its kill count, and the engineer confirms one. The rule goes into the variant it is about; the
campaign's designs are rechecked against it at once - those that now break it hidden with the rule
named, not deleted - and the next campaign obeys it. A rejection without a reason only makes similar
designs rarer, visibly; it never becomes a hidden rule. Every rule can be relaxed or removed later.
Designs rejected for taste still go to the solver: physics does not care what anyone likes.

**What is learned** stays within a project - which settings fail, so less sampling is wasted; which
checks keep failing for one cause, which become rules at an earlier stage. Making a learned rule
one for a family of parts or a company is a deliberate act; if a client opts in, it stays within
that client. Never across clients.

## Where the model sits

**The model is paused**, its bar hidden, while variants and campaigns are made by hand. When it
returns:

- **Before a campaign** it turns words, clicks, the drawing and the extraction into variants -
  every entity it names checked to exist, every rule it writes checkable or flagged - asks the few
  questions that block everything, splits *"ribs here and here"* into variants, and chooses
  patterns and ranges.
- **After a campaign** it explains what failed - *"most triangle layouts fail at the holes on
  face:1543; spacing over 140 mm avoids them"* - and turns objections into rules.
- **Code** proposes, places, repairs, builds and checks designs, samples, and picks the varied set
  shown.
- **Never** the model computing geometry, and never a model call per design: four thousand designs
  are a workflow with a handful of model decisions in it.

It is one agent with **a few general tools**, each doing one job, and it composes them:

- **find** entities - by kind, by what they touch, by which way they face, by the axis they turn
  about - or the part's axes and what is on each;
- **describe** entities - what each is, and how several stand to each other;
- **relate** an entity to the part - what it stands on, what rises round a floor, what is round a
  face, what shares its axis, what lies across the open space in front of it - or several
  together: what lies between them, under and over;
- **measure** an entity - how far it reaches along a direction, how thick the metal is under it;
- **search the drawing** for its words;
- **read and edit a variant** - the only way to change one. An edit comes back with where its ribs
  would go, counted, so the agent sees its reading makes ribs before the engineer does.

**Skills** say how to compose them for a kind of request - ribs round a round thing, on a face,
between things; keeping clear of anything; rules from words; sections; naming things; refining turn
by turn. The agent reads one when a request is of its kind. Skills, like the prompt, hold no ids, no
numbers and no example sentences. No tool is made for one kind of request: a new kind is a new
skill composing the same tools, or a new general tool if a job is missing. A decision the part can
settle - whether anything lies under the space between two things - belongs in a tool that
computes it, not in a skill that tells the model how to guess it.

What the agent changes shows on Design a variant, marked, for the engineer to keep or undo. Its own
words are the few lines it asks the engineer to look at - a question that blocks, an assumption
that matters, a rule nothing enforces yet - never what the card already shows; they stand until it
gives them again or clears them, and every edit shows them back to it to check they still hold. It
quotes the engineer's words exactly, every number it gives comes from a tool that measured it, and
it is never scripted to an example sentence. It sees the variants and summaries of named entities -
names and numbers - never CAD files or meshes, and the provider can be changed: a client's approved
one, or a local model.

**Where words are worth more than a form.** A request that names what it means by id - a face, a
number - is better as a click or a stepper on the card: faster, exact, the same every time. Words
earn their place where no form reaches:

- **documents** - drawings, requirement specs, load cases, standards - read into cited rules,
  objectives and loads, which code then checks;
- **objections** at review - *"too close to the bolt bosses"*, *"nothing over the drain"* - read
  into candidate rules, each with its kill count;
- **explanation** over hundreds of designs - why a variant makes one rib, why designs fail a check,
  what the best of them share;
- **a brief** - *"a tenth less mass, bearings as stiff, thinner side panels, ribs on the covers"* -
  read into variants of several kinds of change and a campaign of them, with its objectives, for the
  engineer to edit;
- **things named by what they are for** - *"every bearing boss of the intermediate stage"*.

**What the model must know.** It can reason only about what its tools answer, and today they
answer geometry: which wall a word means is several questions and minutes of reasoning, afresh each
time. Two bodies of knowledge would make the answers engineering:

- **A model of the part's regions and what they are for**: bearing seats by shaft and stage, the
  plates that carry them, outer and inner walls, split and mounting flanges, covers, compartments,
  bolt patterns, sealing faces and clearance envelopes - with their relations worked out once: what
  stands on what, what faces what across open space, what has nothing under it. Computed from the
  geometry and the drawing's labels, proposed by the model where they cannot be computed, and
  approved by the engineer, its names are the ones the variants, the cards, the agent and the
  simulation's result regions all use. With it, *"the wall"* is looked up, not searched for.
- **Design knowledge as data**: casting and rib rules, a materials catalogue, and each kind of
  feature's ranges, each with its source - read by the code that fills a variant, cited by the
  agent, changed by the engineer.

With them go the loads, operating points and targets in the project's documents, and what earlier
campaigns decided.

## Objectives, physics and learning

Until designs are simulated, objectives only rank and filter - added mass, rib volume, coverage,
symmetry - and are labelled geometric; no design is called optimal without physics. The physical
objectives come with simulation.

Simulation runs two ways: the Code_Aster pipeline the housing was solved with before, gated so that
the same design solved twice agrees within 0.1% - mesh noise once made its top eight designs
indistinguishable - and analysis directly on the distance field, which needs no mesh, checked
against Code_Aster. Results are kept apart - bearing-seat tilt, stiffness, stress, mass, then natural
frequencies - so the surrogate learns several objectives. A design the surrogate recommends is solved
for real before it is called good, and that result joins the data.

## What comes out

For every design: its mesh, its solver deck, a row of its settings and properties, and a **recipe** -
the part, each of its variants as it was and the values each took, hashed, and what it is in words
and numbers - from which anyone can rebuild it. A STEP solid of the part with its ribs follows, then
native CAD features when a customer needs them.

A campaign of 4,000 designs - the surrogate's training set - is placed and screened in minutes on
one workstation; building, meshing and solving follow, the representatives first and the rest in the
background. Every one of them must build, mesh and solve, so what keeps a design robust is a hard
rule, not a hope.

## How it is judged

- **Acceptance** - the share of the designs shown that an engineer accepts, tracked per round of
  objections: at least 70% by the third round on the housing. Judged by the engineer building it
  for now, and by an engineer at the client for the demo.
- **Generality** - a suite of at least 30 varied requirements on the housing - different regions;
  floor, hanging and gusset ribs; orientations; height, spacing and keep-away rules; tapered and T
  sections - with the client's own, and a second cast part. A requirement passes when the variants
  written from it are right and every design they yield follows every rule. The suite runs on every
  change; nothing is fixed for one case.

## Design a variant

Design a variant - a pane on the CAD tab's right, beside the faces it names - authors one variant at
a time, by hand. A tab for each variant kept, with its code and name, and one for a new variant.

**A new variant starts from faces.** Faces selected on the part, and what to add there: **ribs on**
them - a floor, faces in one plane; **webs between** them, with nothing under them; the faces
**thickened** or thinned; **holes in** a plate. The card names the faces each would take. What the
variant stands on and ends on is taken from the selection, or read off the part. Ribs stand on flat
faces in one plane: a selection that is not one is refused at once, saying which faces are curved
and what to select instead. A second change is a second variant, and the part's material is no
variant's.

The card shows a little, and opens the rest on demand. What a variant still needs from the
engineer, and what cannot be built yet, stays at its top.

**Where, in a sentence** - *"on face:1201, ending on what rises round it (31); 5 mm clear of 12
holes"* - each group a chip or a count that shows it on the part. **Change where** opens them one
by one: what its ribs **stand on** - a floor, as faces or features in one plane, or nothing, for
webs that hang between what they join; what they **end on** - named, or read off the part: what
rises round the floor; for webs, what they run **from** - the faces they were added between - and
what they run **to**, the other side, added from the faces selected: a web runs from one side to
the other, never between two faces of one side, and until the other side is added the variant says
it needs it, with *change where* open to add it; a face is on one side only. What they **keep clear
of** - any entity: a face, a boss, the holes found; the ribs or holes of another variant, named like
any entity as `ribs:` or `holes:` and its code.
Every list of faces on the card - what spokes turn about among them - has an × on each face to
take it out, but the last where one must stay, and **+ add** for the faces selected on the part.
Another variant's ribs are in the way only where they stand at the same height: ribs on a ceiling
are no obstacle to webs far below it.

**Its shape**: the settings that decide its designs first - for ribs the patterns, thickness,
spacing, count and height; for holes the pattern, diameter and pitch; for faces, how far they move -
and the rest - what spokes turn about, angle, radii, draft, top, pads - under **More settings**.
What spokes turn about and how they spread show only while spokes are allowed, with **show** to see
the choices on the part. Choices are chips, switched on and off at a click, every choice the part
offers shown so one left out can be taken back; numbers change in place, as a **range** in steps
or **one value**, chosen at the head of the editor, and what it shows is kept on Enter, on done, or
on clicking anywhere else once anything in it was touched - Escape leaves it as it was - a range
from a value to itself being that value. What the engineer set is marked, with
**reset** to hand it back to the part; where the part's suggestion comes from is in the setting's
tooltip. Every range the part suggests steps by five in its own unit, its ends rounded inward onto
fives; a height is said in thicknesses of the rib, by halves. The card counts the distinct designs the variant allows:
for each pattern, the values of every setting that makes a difference to it, multiplied; free lines
have no end.

**Its rules**, in words, each its own - keep clear of; no taller than; at most so tall; every rib
ends on what it runs between; no rib thicker than a share of the wall it meets; no radius under;
room for the sand between ribs; no X crossings. A rule the part suggested says so, and a click on
that makes it the engineer's; one from the drawing says so; any is taken out with ×, and **add a
rule** offers only the kinds the pipeline checks. The part's interfaces, held for every variant,
fold into one line below them.

**Seen before it is kept.** **Show paths** draws the variant alone at its suggested point;
**Another sample** at a point drawn at random from what it allows - every choice, and every step
of a range, as likely as the next: no pattern is weighted over another. Each is placed, repaired
and screened, up to 48 points tried until one passes, so a sample shown is one that passes, and the
card says how it was drawn - its suggested point, or at random from which seed - and on which try it
passed; when none does, the card says why, the commonest reasons first. What is made is drawn as
wide as it is - a rib or a pad by its outline - and everything else faint. The paths are every line
the variant's pattern lays across its floor - never past it - or across the open space between what
its webs join, cut into pieces by what it keeps clear of, each piece coloured by what became of it:
a rib; left out by repair; stopped by something to keep clear of; ending at an edge with nothing to
meet; ending on something not named (which it names); ending on one thing at both ends; running
within one side of its webs; too close to another; too short; no room for its height; reaching a
hole or bore the part keeps closed. The card says what was made - so many ribs and pads - with the
colours and the count of every piece folded under it, the values the sample took that make a
difference to its pattern, and what repair left out, and why. Faces moved draw no lines: how many
move and how far is said - a few faces by name, more as a count, never every face - with *show
them* to see them on the part.

**Kept at the bottom.** Its name - suggested, what it changes and where - and **Create variant**,
which keeps it in the library once one of its points passes, and refuses one none of whose points
does. A variant kept is changed and **saved**, **discarded** back to what was kept, **duplicated**
or **deleted** - moved aside, never lost. The campaigns that used it are listed on it, each keeping
the copy it was launched with, and marked where the variant has changed since.

## A campaign

A **campaign**, on Generate, is a card in three steps, each greyed until the one before holds
something:

- **Compose** - its name, and the variants it takes, each with what it adds, where, and how many
  designs it allows.
- **Check** - at a glance, each item a few words with its full rule on hover: what each variant
  varies and the rules it holds, as pills; what holds always without anyone writing it - holes
  keep their ligament from every variant's ribs, ribs of two variants keep the root gap, the part's
  interfaces stay clear, clashes are repaired by CP-SAT; the screening checks, each switched off
  for this campaign alone at a click; and, folded, the checks a design's field is held to. A
  variant that cannot be read says why beside it, to try again.
- **Sample & launch** - how designs are drawn: **spread evenly**, the default - a scrambled Sobol
  sequence over which variants and which point of each - **at random**, every choice and every step
  as likely as the next, or **every combination**
  when the variants allow no more than the designs asked for; how many designs, from which seed;
  whether to keep the most different of two to five times as many; how many designs the variants
  allow - every set of them at every point of each, `Π(1 + c) − 1`; **Screen 100** - a hundred drawn
  as the launch would draw them, placed, repaired and screened, nothing kept: how many pass, how
  many needed repair, why the rest do not, and how long the launch will take; and **Launch**.

Launched, it pools each variant alone - points of what it allows, placed with nothing else,
repaired and screened, those that pass its pool; a variant none of whose points passes stops the
campaign, saying why. Then designs: a set of the variants, its size spread evenly over one to all,
and a pool point of each by the method; placed together, repaired, screened, drawn again when repair
cannot save it; alike designs kept once; `n` kept of at most `4n + 100` tried. Its progress shows as
it goes - each variant pooled, designs kept and tried, repaired, and why the rest were not kept -
and the campaigns launched are listed beside the card, each opening in Designs.

**The archive** keeps each launch whole, beside the project: the card, the part's digest, the code's
commit, a copy of every variant as it was, the seed and the method; every design with the variants
it holds, the values each took, its recipe and the recipe's hash, its own seed, what repair left
out, how it screened and its paths; a summary of what was tried, kept and dropped and why, how each
setting spread, how many distinct rib layouts, how far each design sits from its nearest neighbour;
and each design built so far.

**Designs** lists a campaign's designs: the 20, 30 or 50 that differ most, those built, or all of
them a page at a time - or only those holding one variant. Each has its stages as letters, filled as
each is done in the colour of how it came out - P its paths placed and screened, F its field built
and checked, M, S and R its mesh, setup and results - and a dot for each variant it holds. A design
reads by variant - code, name, what it made and the values it took - with the variants it leaves
out, what repair left out, and its recipe and seed. Its paths are drawn on the part at once; **Build
field** builds it from the copy of the variants its campaign kept, checks it and keeps it, so it is
built once. Its field is the surfaces it changes over the part, run down to where they meet it -
the faces it cuts shown as its own surface, so a hole looks like a hole - and its new metal as
cells; its verdict says how long each check took.

## What is read off the part for ribs on a floor

For a variant standing on a floor, everything left open is read off the part, round what the
engineer gave - or a default that says it is one. Every range read off the part steps by five in
its own unit - a height in thicknesses by halves - its ends rounded inward onto fives, unless that
would leave nothing. A new variant of ribs then starts simple, from a **starting point kept as
data** beside the rules of thumb, which the engineer changes on the card: ribs 20 mm thick, 100 mm
apart, two to five times as tall as they are thick - three suggested - and never taller than what
they meet, two to ten of them - two suggested - and a root fillet, edge round and draft each of
three choices, the smallest, the middle and the largest the part offers, the middle one first:

| what | read off the part as |
|---|---|
| what they end on | what stands up round the floor, past any fillet or chamfer at its foot, on the side ribs stand - each wall, boss or bore once |
| keep clear of | every hole through the floor, 5 mm clear of the rib's footprint, listed and suggested; the engineer's own distance replaces it |
| pattern | every pattern the floor allows - parallel, square grid, triangle grid, spokes - and free lines; suggesting spokes about the largest boss or bore the floor goes round more than halfway, else a square grid |
| what spokes turn about | the bosses and bores standing round the floor, largest first - only round things with an axis; a face of a ring turns about the ring's axis, and a face with nothing round about it is refused |
| orientation | set out from the longest wall round the floor: a grid along it, parallel ribs square to it; spokes fan across the floor, or go all the way round; free lines at any angle |
| how many, how far apart | two to ten lines each way, or spokes, and 100 mm apart to start - both, for every pattern; read off the part as 4 to 16, and 5 to 16 thicknesses apart |
| how tall | 2 to 5 thicknesses of the rib, three to start, each end no taller than what it meets - the face or feature it runs into, never the metal behind it - the top sloping between |
| thickness | 20 mm to start; read off the part as 0.6 to 1.0 of the plate they stand on, measured through it |
| thickness against the wall | no thicker than 0.8 of the wall they meet, assumed - a rule the engineer may take out |
| room between ribs | the root gap: two thicknesses of sand between footprints, and at the wedges where ribs meet, assumed |
| pads | on: a wall too thin for a rib is thickened round its end rather than the rib left out. A floor is never thickened: a rib too thick for the floor under it is left out, saying the rule it broke |
| root fillet, edge round | from the smallest radius the part allows up to half the thickness - three of those choices to start, the middle first |
| draft | half a degree to three - three choices to start, the middle first |
| section | flat, unless the engineer asks for a T; a T's flange 2 to 4 times the web wide |
| smallest radius | the drawing's note, cited by page and text |

## What is read off the part for webs with nothing under them

For a variant that stands on nothing, the webs join its two sides - what they run from, and what
they run to - and the rest is read off what they join:

| what | read off the part as |
|---|---|
| which way they stand | along the axis of what they run from when that is round - a bearing's webs stand along the bearing, whatever else is named; else the direction the most of what they join runs along - the axis of a round one, the line two flat ones meet along, else one of the part's own axes |
| from where to where | each web from the height of its own two ends: every height where one of each side begins - a few millimetres apart counting as one, at most eight - is tried, lowest first, and each web hangs from the first where it runs from one side to the other, so a part whose walls step up and down is joined all round; what runs along some other way takes no part |
| where they may go | the open space between them at those heights - where the part is not, in the pieces of open space that reach two of them or more |
| pattern | spokes about the round thing among them - a boss before a bore - or straight webs; both stay open |
| orientation | spokes fanned across the others than what they turn about; straight webs square to the largest flat one, laid across where two of them face each other |
| how many, how far apart | two to ten and 100 mm apart to start, as for ribs on a floor; read off the part as 2 to 12 webs, or 5 to 16 thicknesses apart |
| how tall | 2 to 5 thicknesses, level by default; never taller than where both sides stand - the lower of the two things a web joins - nor into what stands over it |
| thickness | 20 mm to start; read off the part as 0.6 to 1.0 of the thinnest of what they join, measured through it |
| root fillet, edge round, draft | as for ribs on a floor |

Each web runs from one side to the other - never within one side, never from one thing to itself -
and is buried in both. Spokes meet inside what they turn about; where they stand in the open, each
keeps the root gap from the next, measured between footprints - room for the mould between them -
or is left out. Placing sees to that within a variant, and repair between variants.

## Beyond ribs

The recipe that makes ribs makes other variations: a kind of change - where it goes, what may vary,
its rules - a way to build it on the distance field, its checks, and what is read off the part for
it. Ribs, faces moved and holes are built; the rest are to come:

| kind | where | what varies | built as | checked for |
|---|---|---|---|---|
| **thicken** (built) | faces - a wall, a plate, a boss | how far they move along their normal, from 5 mm thinner - never below the least a wall may be - to 10 mm thicker, unless the engineer says; the blend | the faces' weight in the field, times the offset, exactly in a window round them | the wall left at least its least - the variant's, or the material's |
| **holes** (built) | a plate | square or staggered lattice; diameter, one to four plate thicknesses; pitch; angle, from the plate's longest direction; edge distance | capped cylinders cut away, through the plate and no further | a ligament of metal - one plate thickness - between holes, from edges, ribs, holes the plate has, and nothing standing under the plate |
| bulge or crown | a panel | how high, where, how wide | the same weight, times a smooth bump | draft; clearance envelopes kept |
| boss transition | a boss and the floor it rises from | the transition radius, the boss's wall | a local growth and fillet at its foot | the bore unchanged; thick spots |
| existing rib | a rib the part already has | its height and thickness, scaled | its region offset | as for ribs |

What is read off the part for each: for faces to thicken, the metal under them, so thinning never
goes below the least a wall may be; for holes, the plate's thickness, its longest direction, and the
holes it has already, kept a ligament clear.

**The material is not a change.** A part is cast in one material, from the catalogue - the
catalogue's default for a cast housing until the engineer names the part's own - and every design
is weighed in it, its least wall the least any wall is thinned to.

A design's variants are built in one order - what changes the shape (faces moved), then what adds
to it (ribs, webs and their pads), then what cuts it (holes) - and rules run across variants: holes
keep a ligament clear of every variant's ribs, unless the holes' variant says how far itself; a rib
meets a wall as the design moves it, and a thin wall is padded, or thickened by another variant of
the design; a floor is never thickened for its ribs - a rib too thick for it is left out, unless
another variant of the design thickens it; a wall is never thinned below what its material allows. A face the part keeps closed - a bore - cannot be moved; faces round it can. A
customer's own part, ribs and all, is a baseline to vary like any other - never a reference to
match.

**Three generations of variation.** Same-shape changes to what the part already has - offsets,
bulges, transitions, existing ribs - are the most often valid, and come first. Features from
templates - ribs, webs, holes - change the part's topology within rules. Free exploration on the
field changes it further, and a design found there is rebuilt as features only when it is worth it.

**How designs are made.** A campaign tries each variant alone first - its points placed with
nothing else, repaired and screened, those that pass its pool - so a variant whose points mostly
make nothing says so before anything is combined. Then it draws designs - a set of the variants and
a pool point of each - places them together, repairs them, screens them, and draws again where
repair cannot save one. To come: every margin recorded so a proposed rule shows its kill count
before it is confirmed; a chosen few meshed and solved, a surrogate learning from them, the search
run on the surrogate, and the best solved for real before anyone calls them good.

## Reading the part

Everything a variant and its patterns start from is read off the part by code, in one pass:

- **Holes go round.** A hole is a small concave cylinder or cone - with the cones that chamfer or
  countersink it - whose faces go more than 200° round their axis. A fillet in a square corner is a
  small concave cylinder too, and goes a quarter of the way: it is a fillet, not a hole. A cast
  hole with draft, all cone and no cylinder, is a hole.
- **What rises round a host** is found by walking out from its edges across blends - fillets of any
  shape, rounds, chamfers - to the first faces that stand up at least 45°: walls, bosses, bores.
  Only on the side ribs stand on, so past the round on a floor's outer edge is not a wall; never
  through a hole.
- **What spokes turn about** is a boss or a bore: something round standing square to the host that
  goes a good way round its axis, with the rest of it if the CAD split it in pieces - a corner
  fillet or a rounded wall corner never does. It is looked for among everything standing round the
  host, named to run between or not. Spokes are suggested by themselves only when the host goes round
  more than half of one; asked for spokes, it takes the largest, and lists the rest.
- **Which wall straight ribs are set out from** is the longest flat face standing round the host,
  measured along it.
- **How tall a rib can stand at an end** is how tall what it meets stands there: the highest the
  face or feature the end runs into rises, within the rib's width and as deep as the end may be
  buried - never the metal found behind it, so a boss against a tall wall is met as tall as the
  boss. The end is buried as deep as it must be to stay inside that metal all the way up, so a wall
  with draft is met as tall as it stands. A web stands only where both of what it joins do.
- **The plate's thickness** is measured by a ray through it, from the largest facet of the host.
- **What lies across the open space from an entity** is found by rays from points spread over its
  faces, straight out of its metal: the first things they meet, each with the share of the entity
  that looks at it and the gap - the wall a web from it would reach.
- **What lies between things** is found from points halfway across the space where they face each
  other, at the heights they share: rays straight down and up say what is under and over that
  space and how far past where they begin or end - a floor at their foot to stand on, or open
  space, and webs with nothing under them. When metal fills the space - two faces of one piece -
  it says so.
- **The smallest radius** is the drawing's own note, found by its text and cited with it.

## Seeing, naming and selecting faces

Hovering a face on any 3D tab shows a small card with its one name, `face:N` - which a variant takes
wherever it takes a feature - and its type, area, which way it faces or its axis, diameter, height,
and whether a drawing controls it. Clicking pins the card.

**Selecting is how faces get into a variant.** A click selects a face; a Ctrl-click adds one or
takes it out. The **grow** angle spreads a click across every edge shallower than it - and belongs
to that click alone: the stage lists the clicks, the grow control acts on the last one or whichever
is picked, and a face clicked after growing another starts ungrown. Lowering an angle takes faces
back out. Selections are highlighted in a colour no design uses.

## Build order

[build-plan.md](build-plan.md) has the steps and what shows each done: the variant library; what a
variant may vary; footprints, wedges, crossings and repair; a variant's samples; campaigns; designs
by variant; the interface; a clean start. After them: the engineer's review loop, quality-diversity
search, mould release with the pull, wall fields, meshing and physics, the part's regions, and
scale.
