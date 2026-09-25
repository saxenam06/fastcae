# Rib networks: where the work stands

**Status on 2026-09-21.** A rib network made by fastcae for the GRC housing now beats the
production housing on the solved mesh: **0.359 mm largest displacement with +30.1 kg, against
production's 0.443 mm with +47.5 kg** - 19 % less displacement with 37 % less metal - with all 18
of its 18 ribs built, fused, meshed and solved, launched from the product. A campaign takes ten
to thirty minutes. This page says what was asked, what was built, what is solved and
how, what is not, and what comes next. How the method works is in
[rib-optimisation-plan.md](rib-optimisation-plan.md); the product around it in
[designs.md](designs.md).

---

## 1. The problem as it was given

Generate many meaningful, load-aware rib networks of the quality an engineer would draw, from a
rib-free housing, that are **always CAD-valid, castable, meshable and solvable**, so their solved
fields can train surrogates. The rules set along the way:

- **The pass line.** A run passes only if its design has a lower largest displacement than the
  production housing with no more added metal, with an optimised pattern in every design volume.
  Anything less is a failing run.
- **The conversion rate matters.** Sixty fins seeded and four built is a failure in itself, and
  has to be explained stage by stage.
- **Constraints inside the optimisation.** A rule enforced by removing ribs after the optimiser
  has answered moves the design away from the answer. Every feasibility rule belongs in placement,
  in bounds or in the optimiser's constraints - so that closed, intersecting networks can be found
  at all, whatever the seed, and so that the rules bring the order, not a pattern.
- **Rib height.** Never taller than the metal at its ends; the optimiser's to raise within that;
  and a rib must cover a bore's boss, not kiss its edge.
- **Every stage visible in the product**, as a product and not a report on one housing.

## 2. What was built

One constrained problem, run as nine stages (`ribs/workflow.py`, a `ribs.network` runner job):

| stage | |
|---|---|
| **Seed** | a seeder proposes fins - spokes, a ring of chords, tangents, a wheel, a random scatter - and **one gate of placement** admits them: across the volume's own air, square to its walls, a wall to root in, clear of the metal, apart from the fins already placed, and passed by the CAD's own sections. As many as the target's metal affords at full height |
| **Pass** | MMA on 10 mm cubes moves every fin inside bounds, the metal capped at the target's, the clearance and spacing rules held |
| **Oracle** | every fin judged on its numbers before any boolean |
| **Chooser** | CP-SAT keeps a network under the rules that are decisions, each fin valued in the company of the rest; a fin dropped on value alone is measured back in |
| **Polish** | the same optimisation with the topology fixed; then the reading against the target |
| **Path, CAD, Mesh, Solve** | each fin a swept solid rooted in its walls, fused, meshed face by face, solved by cuDSS as the target was |

Round it: a ledger that keeps every fin's fate and the rule behind it; the Designs screens showing
each stage on the part; a New campaign form that launches a network from the product; and the
reading against the target stamped on every stage.

## 3. What is solved, and how

### CAD fusion and boolean failures

**Solved: every rib solid that has reached the boolean has fused** - 5 of 5, 4 of 4, 7 of 7,
14 of 14, 17 of 17, 15 of 15, 14 of 14 and 18 of 18 across the day's designs.

- **One swept solid a rib, not lapped plates.** A curved rib built as a chain of flat plates laps
  itself at every joint: 25 slivers for two chords rose to 291 for six. A rib is now one solid
  swept along its curve - six faces, no laps.
- **The end is sunk whole into its wall.** Each end is drawn into a *root window*: the stretch of
  the wall's section thick enough to hold the rib across its whole thickness, tapered over 25 mm,
  ending 4 mm short of the wall's far side. No rib face lands on, or a hair from, a face of the
  part.
- **The ribs are joined to each other first**, then the network to the part, so junctions are
  made between simple solids and the part is cut once.
- **Nothing reaches the boolean unjudged.** The oracle reads each fin on its numbers, on its
  outline on the CAD's own sections, and as a solid. Its refusals became rules of placement (§3,
  conversion), so it now finds almost nothing.

### Slivers

**Mostly solved.** The causes were found one by one, and each is now a rule kept at placement or
in the optimiser rather than a rejection afterwards:

| cause | kept by |
|---|---|
| plates lapping along a curve | one swept solid a rib |
| a face running a hair from a wall | the clearance rule: a rib's middle 18 mm clear of metal it does not end on - **the same measure** in the gate, the pass and the oracle |
| a rib meeting its wall at a glance | placed only at 35° or steeper; the curve leaves its wall square |
| two ribs crossing at a shallow angle | a crossing is a junction at 60° or steeper, otherwise a conflict |
| an end on a wall too low or thin to root in | placed only where the metal stands 25 mm, and the CAD's sections agree |
| tessellated section corners read as edges | the outline is read on the rib's own sheet, not the polygon |

**What remains:** corner faces under 5 mm², at most 1.5 mm², where a sunk end meets its wall -
about one a rib, 22 to 24 on the latest designs. They are counted and reported on the design's
checks; the mesh decides, and every design has meshed with 0.03 to 0.06 % of tets below quality
0.1, none inverted, no hole closed flat. This is tolerated, not fixed (§4).

### Meshing and solving

**Solved for everything that reaches them.** Every fused design meshed (284,000 to 301,000
second-order tets) and solved by cuDSS with its reactions balancing its loads. One solve died of a
CUDA memory error inside a long-lived scratch process that also held the optimiser on the card;
the same mesh solved in a clean process. The product's runner holds the card one job at a time.

### The conversion rate

| | seeded | past the oracle | kept | built |
|---|---|---|---|---|
| the afternoon's runs | 60 | 44 | 11 | 4 |
| now | 18 | 18 | 18 | 18 |

Each loss was traced from the ledger and moved upstream:

- **Spokes cast to the farthest wall** passed over other bores' shafts. A spoke now runs to the
  first rooted boundary it meets across the volume's own air.
- **The pass folded fins and pushed them off their volume.** Ends now slide 40 mm at most and
  never more than a quarter of the chord; control points stay in a band the seed's room sets.
- **The chooser thinned 26 fins to 13 for spacing.** The spacing rule is kept by where fins are
  placed, with the first 35 % of a run free at a root two ribs share.
- **The optimiser and the oracle held different rules.** The pass averaged a fin's intrusion over
  its run, so a long fin could graze a wall for 27 mm and pass, and the oracle then refused it;
  the pass's margin (14 mm) also sat inside the oracle's. One fin lost this way took a network
  from 0.34 to 0.46 mm. Both now count millimetres along the run, and the margin is 18 mm.
- **Walls the cubes misread.** A wall 4 mm tall read as 25 on the plan: the CAD's own sections
  now judge every seed, and a kept fin the CAD refuses after the polish is built as it was seeded.

### Beating the target

- **Fins valued in company.** Valued alone on the bare part, every fin of the second volume read
  as worth under 0.02 % - the bare part's whole displacement is one face dishing - and all
  seventeen were dropped. Valued by the objective's own derivative with the network standing,
  they carry the most.
- **Removals are measured.** While the cap has room no rule-passing fin is dropped; one dropped on
  value alone is measured back in.
- **Ribs as deep as their walls.** The cap read the wall's height 12 to 24 mm behind the rail and
  overshot a 15 mm wall onto the low flange behind it: ribs in the sector that moves most were
  50 mm deep against a wall of 180. Read from just inside the face, the next design beat the target.

| on the solved mesh | ribs built | largest displacement | metal added |
|---|---|---|---|
| production (target) | 9 | 0.443 mm | +47.5 kg |
| first spokes run | 7 of 10 | 0.892 mm | +9.8 kg |
| rules at placement | 14 of 18 | 0.501 mm | +20.2 kg |
| rules agreed, CAD at seeding | 17 of 17 | 0.549 mm | +23.6 kg |
| ribs as deep as their walls | 14 of 14 | 0.416 mm | +22.1 kg |
| launched from the product | 18 of 18 | **0.359 mm** | **+30.1 kg** |

## 4. What is not solved

- **Corner faces under 5 mm²** at sunk ends. The fix is to cut the rib's end against the wall's
  own section rather than sink a rectangle into it.
- **The cubes are not a fair judge.** They read rib networks 1.1 to 2.3 times lower than their
  meshes (production 1.18), because 10 mm cubes over-stiffen thin webs and count rib depth that
  attaches to nothing. A margin is learned from every solved design, and for now only informs.
- **Overall stiffness.** The best design's strain energy is 4.3 % of the bare part's against
  production's 3.9 %; it wins on the largest displacement, not yet on compliance.
- **Only spokes are proven end to end.** The ring of chords, tangents, the wheel and the scatter
  go through the same gate and are tested, but have not been run on the housing - so a closed,
  intersecting network under these rules is built for, not yet shown.
- **Two figures are placeholders**: 100 mm between rib centres, and one 20 mm section. With them
  spokes spend about two thirds of the target's metal; production's own webs are about 30 mm.
- **One load case**, the deck's; no root fillets; the register keep-out covers space production's
  own ribs use, and switching it off did not help (the extra depth attaches to nothing).

## 5. Next steps

1. **Run the other seeders** - wheel, tangents, scatter - one campaign at a time against the same
   pass line: closed cells under the rules, and the claim that the result does not depend on the
   seed.
2. **Spend the rest of the cap** where the mesh says it matters, and close the strain-energy gap.
3. **Set the two placeholder figures** with the engineer, from the production casting.
4. **Make the cubes honest** for thin webs and unattached depth, so the margin can gate a build.
5. **Cut the rib end against the wall's section** to end the corner faces.
6. **Variety for surrogates**: many campaigns across seeders, seeds and load mixes, every one
   held to the same rules, every solved field kept.
