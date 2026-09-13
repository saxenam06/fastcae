# Build plan: a design space from the engineer's words

**The plan as agreed.** What is built, in what order, and how each step is judged. The design behind
it is in [ribs.md](ribs.md); what runs today is in [status.md](status.md).

---

## What is being built

Generative design in CAD tools gives a handful of optimal shapes per setup, which someone then
redraws. ZenryxAI gives thousands of near-production variants of the engineer's own part that already
follow their rules, with solver decks. A surrogate trained on them finds groups of designs that do
well on several objectives at once - each a real, castable design - and shows which choices matter
for the next design.

The engineer brings a plain STEP file and its drawing, builds the study on Design a variant by
hand - or says what they want in words, and the agent writes the same draft - launches a campaign,
and reviews about 20 designs a round, the ones that differ most. The 4,000 behind them are the
surrogate's training set, each followed through its stages, which nobody browses one by one.

## What is agreed

1. **The study is the one source of truth**: a versioned document in the part's named entities -
   what to add and where, what may vary (ranges with steps), what must hold, what is preferred, what
   "better" means, and a seed. Generation reads only the study; the same version and seed give the
   same designs, bit for bit.
2. **Entities are bound by fingerprint** - kind, size, position. `face:1201` is a name to show; when
   the CAD is read again the study finds its faces by fingerprint, or says it cannot.
3. **Every constraint has a strength and a source.** *Hard* - the engineer or the drawing said it.
   *Assumed* - a default the system took, the only kind it may offer to relax. *Learned* - from a
   rejection the engineer confirmed. Each cites the words, the callout or the measurement it came
   from.
4. **Interfaces are closed**: bearing bores, holes with room for the tool, datums and machined faces
   are forbidden unless the engineer allows them, each citing where it is known from. Everywhere
   else is open: what the engineer does not say is explored, and listed as assumed.
5. **A layout is a graph**: anchors on named entities, joined by ribs. A rib is a web in a plane
   between two anchors - a floor under it optional - with a section: thickness, taper, height, draft,
   root fillet, edge round. Spokes, grids and triangles are shapes of graph; they survive as
   proposers with weights, never as limits.
6. **A solver chooses the combinations.** Candidate ribs and their conflicts are computed once;
   CP-SAT picks sets of ribs that satisfy every combination rule at once, with a random objective
   for variety, and names the assumed rules to blame when nothing fits. Sobol sampling sets the
   sizes.
7. **Cheapest checks first**: one rib at a time, then combinations, then sizes, then geometry, then
   physics. Every design's margin against every constraint is kept, so any proposed rule shows at
   once how many designs it would remove - its **kill count**.
8. **Designs are chosen for difference**: five to ten times too many are made, the 4,000 most spread
   out in a space of properties are kept - rib count, total length, which entities are tied,
   orientations, added mass - and the ~20 most representative are shown.
9. **Objections become rules**: the engineer points at the rib they object to; the model offers one
   to three readings, each with its kill count; the engineer confirms one. Learned rules belong to
   the study; making one a rule for a family of parts is a deliberate act. Designs rejected for taste
   stay in the physics set.
10. **Design a variant writes the study by hand**: blocks from the faces selected, their entities,
    settings and rules, each the engineer's own and said in words in the study. **The model** writes
    the same draft from words, grounds names, asks only what blocks every design, explains why a
    request is impossible, and turns objections into readings - where words are worth more than a
    form. It never makes geometry and is never called once per design. Its tools are study-level.
11. **No code is written for one part or one request.** What the study cannot express is added to
    the library as a general piece - a rule kind, a proposer, a feature kind, a query - and every old
    study must reproduce its designs exactly afterwards.
12. **Physics**: Code_Aster, gated so the same design solved twice agrees within 0.1%, and analysis
    on the distance field; results kept apart, never folded into one number. After physics, search
    keeps the best design in each cell of the property space (MAP-Elites), and a design the
    surrogate recommends is solved for real before it is called good.

## The pipeline

```
words + clicks + drawing + CAD
        │  the model, with tools: ground names, write entries, ask what blocks
        ▼
  study (versioned, seeded)
        │
        ├─ anchors ─► candidate ribs ─────────── one-rib rules remove candidates
        │                 │
        │                 └─► conflicts between pairs, at the thickest a rib may be
        ▼
  CP-SAT: sets of ribs ──────────────────────── combination rules; random objectives;
        │                                        spread over which entities are tied
        ▼
  Sobol: sizes of each rib ──────────────────── size rules
        ▼
  screening (seconds) ─► building (minutes) ─► checks ─► archive: every margin, kill counts
        ▼
  5-10× over-made ─► 4,000 most spread out ─► ~20 representatives ─► the engineer
        ▲                                                                   │
        └──────── new study version ◄─ confirmed rule ◄─ readings ◄─ objection
```

## Where each rule is enforced

| stage | rules |
|---|---|
| **one rib** - decides which candidate ribs exist | on the support and within the span · interfaces closed · clear of holes by the clearance · plane contains the pull direction · orientation asked for (parallel to a plane, along or square to a face, radial about an axis) · ends on allowed anchors, never on excluded ones · room for a height taller than the root fillet · at least two thicknesses long |
| **combinations** - CP-SAT | how many, in total, per group, per anchor or region · not closer than the spacing · no X-crossings · junction angle at least 30° · at most a few ribs meeting at one point · ties asked for between two entities · symmetric pairs together, if required · rejected combinations never return · each new design differs from those kept by at least *d* ribs · a rough added-mass limit |
| **sizes** - Sobol within ranges | root fillet at least the smallest radius · thickness at most 0.7 of the wall met · edge round at most half the thickness · draft at least 1° |
| **built** - checks | fillets achieved · thick spots · mould release · nothing floating · protected faces unchanged · the surface closed |
| **physics** | bearing-seat tilt · stiffness · stress · mass · natural frequencies |

Preferences are weights in the solver's objective, never limits. An assumed rule is a switch the
solver can blame. A check that keeps failing for one cause becomes a rule at an earlier stage.

## The model's tools

A few general tools, each doing one job, which the model composes - with **skills** that say how,
for a kind of request. Today: find entities, describe them, relate them to the part - what they
stand on, what rises round a floor, what is round a face, what shares an axis, what lies across the
open space in front of them, what lies between several of them - measure them, search the drawing,
and read and edit the study, each edit coming back with where every block's ribs would go. To
come: an entry's kill count, running a study version, why nothing fits, the representatives,
readings of an objection. No tool is made for one kind of request.

What the model knows is what those tools answer, and today they answer geometry. The knowledge that
would let them answer engineering - a model of the part's regions and what they are for, and
design knowledge as cited data - is described in [ribs.md](ribs.md) and not built.

## Steps

Each step names what is built and what shows it done. Every step keeps all tests passing and every
earlier study reproducing its designs.

**1. The study** - the document, and Design a variant as its one structured view.
- The study: entities by fingerprint, blocks (what to add, where, span), the pull direction, free
  ranges with steps and sources, constraints with strength and source, preferences, objectives, the
  target (how many, spread how, how different, the seed). Written only through one function that
  refuses names the part does not have, words never said, and hard rules citing nothing.
- The catalogue of rule kinds, each with the stage that enforces it and whether that stage is built.
  A rule no stage enforces yet is kept and listed as open, never dropped.
- Assumptions listed: every range and rule nobody confirmed.
- Interfaces closed by default, from the part and the drawing: bores, holes, drawing-controlled
  features; the drawing's datums listed for the engineer to point at.
- A block is read off the part round what the words gave - on a floor, or webs between what it
  joins with nothing under them: its settings ranged round a suggested point, the rules the part
  suggests for it marked as the part's, and what the words said always winning.
- Design a variant, on the CAD tab, is the draft of the study's next version, read back from the
  study when the project opens: block by block, what its ribs stand on, end on and keep clear of -
  any entity, each a chip - then its settings and rules, each with what the study makes of it; what
  the draft changes marked, Accept and Undo. The agent, above every tab, changes the study only
  through the draft, and says only what needs the engineer's attention.
- Preview and Full make the design at the study's suggested point, accepting the draft first.
- *Done when* a request on the housing writes a study, the study reads back the same draft, and
  every refusal and open item is tested.

**2. Candidates and conflicts**
- Anchors on the entities the study names; candidate ribs between them, each tested against every
  one-rib rule; conflicts between pairs at the thickest allowed.
- Show paths becomes show candidates: every candidate rib on the part, coloured by the rule that
  removed it.
- *Done when* the housing's candidates and conflicts are computed in seconds and every removed
  candidate names its rule.

**3. Choosing, sizing, screening, the archive**
- Built: Sobol over every block's free settings - each block alone first, then which of each block's
  workable points to combine; screening in a fraction of a second a design; alike designs kept once;
  the archive of every design kept, in `designs/`, with what it is made of, how it screened and what
  it weighs, keyed by study version.
- To build: CP-SAT over the candidates with the combination rules as constraints and the assumed
  ones as switches - choosing the ribs of a design so every rule about sets of ribs holds, and
  repairing a combination by leaving out the one rib or hole in the way rather than discarding it;
  random objectives; spread over which entities are tied; each design differing from the last by at
  least *d* ribs; every margin against every constraint kept, for kill counts.
- *Done when* one study gives 40,000 screened candidates in minutes, the same version and seed give
  the same archive bit for bit, and an impossible request names the assumed rules to blame.

**4. The model on the study**
- The tools above over the study and the archive. Words and clicks become entries, each echoed back
  in plain words with its kill count. Blocking questions only.
- The requirement suite: thirty varied requirements on the housing, drafted here and vetted by the
  engineer, with the client's own when they come. The first five are the engineer's own, asked in
  one conversation, each refining the study the earlier ones wrote.
- *Done when* the suite's requirements become the right studies, judged by the engineer.

**5. Choosing what to show, and objections**
- The property space, farthest-point selection of the 4,000, k-medoids for the ~20 shown; the review
  screen; pointing at a rib; readings with kill counts; confirmed rules; recheck and refill.
- *Done when* a round of objections gives a new batch with none of them in it, and the engineer
  accepts at least 70% of what is shown by the third round.

**6. The general rib**
- Webs between any two anchors with nothing under them - boss to wall, bearing boss to bearing boss -
  the pull direction from the study, a rounded free edge; then taper and T sections.
- *Done when* "strengthen the bearings of all three shafts" gives valid designs of every family.

**7. An unseen housing**
- A second cast housing with a drawing, run with no code changed.
- *Done when* it gives 20 valid representatives, and the time from files to designs is known.

**8. Speed**
- Placing and screening are fast enough: 4,000 designs of a ten-block study in about a quarter of an
  hour on one core. Building and checking each is still a minute or more: to go overnight on one
  workstation, windows reused, cheaper checks, every core.

**9. Simulate and Learn**
- Decks for every design; Code_Aster with the repeatability gate; analysis on the distance field;
  the surrogate; MAP-Elites; real solves before a design is called good.

**10. The next kinds of feature**
- Built: faces moved along their normal - walls, plates, bosses thicker or thinner; hole patterns
  through plates, clear of ribs; the material the part is cast in, one, never varied; pads where
  a rib meets a wall too thin for it, and floors thickened for ribs too thick for them. One study
  varies them all at once, built in their order - shape changes, then additions, then cuts - with
  rules across kinds, and a campaign spreads designs over all of them.
- To come: bulges and crowns, bearing-boss transitions, ribs the part already has varied in height
  and thickness, pockets. Each through the same recipe: a kind of block, a way to build it on the
  field, its checks, what is read off the part for it - in [ribs.md](ribs.md), *Beyond ribs*.

## Always

- No code names a part's faces or an example sentence; examples go into the requirement suite.
- Every study in the suite reproduces its archive exactly after every change.
- Docs describe what is true now and the design as agreed; nothing records a journey.
- Nothing is committed and no server is started without the engineer saying so.

## Open

- **A second housing** with a drawing, allowed to be used - from the engineer, or a public model
  with a clear licence.
- **The requirement suite**, to vet once drafted, and the client's own requirements.
- **Which material the housing is cast in**: one, never varied - assumed the ductile iron
  wind-turbine housings are cast in by default, EN-GJS-400-18-LT; the drawing names the material
  only as the existing housing's.
- **The client's solver deck**, when there is one.
- **Employment and IP terms** to check before any commercial step with driveline suppliers - for a
  lawyer.

**Decided:** the study is built by hand on the card; the agent is kept, writing the same draft from
words, and will be moved to what no form reaches - documents, briefs, objections, explanation over
many designs - judged on a fixed set of such requests by how often it gives the right study, how
alike repeated runs are, and its time and cost against an engineer doing the same by hand.

**Proposed, not yet decided:**

1. **What comes next: the model of the part's regions and what they are for.** Computed from the
   geometry and the drawing, proposed by the model where it cannot be computed, approved by the
   engineer; the names the card, the agent and the simulation's result regions share. A first
   piece of it: where a kind of block fits at a given size - which floors take 15 to 25 mm ribs -
   asked of the part, not found by trying.
2. **The baseline.** Keep adding ribs to a part without them, and vary any part as it is - a
   customer's own ribbed part among them, as the thing to vary, never as a reference.
3. **The order after that.** CP-SAT choosing and repairing combinations; then a thin slice of step
   9 - mesh, static and modal - on some twenty designs a campaign kept, so the loop closes on real
   numbers, each design's M, S and R filled in;
   then bulges, boss transitions and existing ribs.
