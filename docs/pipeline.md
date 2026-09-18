# The pipeline

**One pipeline from the engineer's files to the design space, and one vocabulary for everyone who
reads it.** Every step's inputs and outputs are typed entities; the rail shows the steps, the
canvases show the entities, the card shows one in full, and the agent reads the same JSON. The code is
`src/fastcae/pipeline/` (entities, adapters, graph, answers) and `src/fastcae/api/pipeline.py`.

---

## Two stages

**Read the engineer's files** - the extraction steps ([extract.md](extract.md)): discover the
artifacts, read the CAD, check its health, measure every face, detect features, read the drawing,
cross-check it against the CAD, read the solver deck and its results, and tie the deck's groups to
the CAD faces they lie on. It runs when the files are extracted, and is kept while they do not
change.

**Derive the design space** - the twelve steps in [design-space.md](design-space.md): the grid, wall
thickness, interfaces, what sits round them, the inside, beyond each bore, sealing walls, where metal
could go, allowed / forbidden / waiting, height straight out, symmetry and questions, where metal
helps. It starts as soon as a project is open - read back in about a second when nothing it depends
on changed - and runs again when the engineer applies answers.

Each step says its status - to run, running, done, read back, skipped, failed - how long it took, a
line on what it found, what it **read** and what it **made**. An input names the step that made it,
and when it is only some of that step's output - the bores among the interfaces, the holes among the
features - which ones.

## Typed entities

Every entity has an id, a kind, a few words, the step that made it, an **origin**, where it can be
**shown**, its **links** to other entities and the **evidence** behind it; each kind adds typed
fields of its own (pydantic models, one discriminated union - `GET /api/entities/schema`).

| origin | means |
|---|---|
| imported | read from a file the engineer brought: a face of the CAD, a group of the deck |
| derived | computed from imported entities by a rule: a volume, a thickness |
| inferred | a reading that could be wrong: a callout matched to a feature, a face that looks machined |
| confirmed | settled by the engineer's answer |
| generated | proposed by fastcae: a question |

Ids are readable and stable while the files do not change: `face:196`, `bore:196`,
`group:BORE_MAIN_S2`, `callout:p2:14`, `interface:bore:196`, `keep_out:plug`, `question:plane:1714`.

Kinds, by stage:

- **Read**: artifact, part, health, face, axis, feature, callout, control, conflict, deck group,
  support, coupling, load, material, signal, result field, anchor (a deck group on CAD faces).
- **Design space**: grid, face map (a value painted on faces: thickness, height, interface, sealing),
  interface (frozen, asked or released), keep-out (plug, beyond, mating, ring, hole, buffer,
  waiting), inside, opening, continuation, band (layer, pockets), region (allowed, waiting),
  question, mirror, benefit.

**Links are read both ways.** An interface is evidenced by the deck group, the anchor and the drawing
control that froze it, and lies on its faces; the keep-outs swept from it and the question about it
link back to it. `GET /api/entities/{id}` gives an entity with every link named and every entity that
links to it.

**Answers are decisions**, kept in `project.json` beside the roles; derived entities are kept in the
cache and rebuilt when anything they depend on changes.

## On screen

**The rail is the pipeline.** Both stages, each step a row with its dot - filled when done, hollow
when read back, pulsing while it runs - its name and time, and under it the line it said. A step
opens to what it read, as chips that go to the step that made them, and what it made, as groups that
open to their entities. While a run derives, the rail shows each step start and finish; the entities
arrive with the space when it ends.

**Focus.** A click on a step, a group, an entity, a chip, a link on the card, a face on the part or
an entity the agent shows puts it in focus, and focus decides what every canvas shows:

| canvas | shows |
|---|---|
| **Drawing** | the callout, highlighted and brought into view; a group of callouts filters the list |
| **CAD · Part** | the entity's faces, selected; something small picked from the rail or a card is looked at |
| **CAD · Design space** | the layers of cells a step made - each its own colour - and per-face values painted on the part; a key to switch each layer and paint |
| **Mesh & setup** | the deck group, lit on the deck's mesh |

The design space's colours say what a volume is for, on every part: green allowed, amber waiting on
an answer, reds for what something else occupies, blue the inside, a heat scale for where metal
helps. The key's **View** shows or hides the part and sets how see-through it is - a see-through part
is drawn as glass, its nearest surface only, over the volumes - and how see-through the volumes are.
While a run derives, the view follows it: each step's volumes are shown as that step finishes, and
the step running counts its time on the rail.

Something picked from the rail or a card, or shown by the agent, is looked at: a flat face from the
side it faces, a round one down its axis from the end away from the part's middle. Several entities
with volumes among them open the design-space view with those volumes on.

**The card** on the right shows what is in focus in full: an entity's kind, origin and status, the
step that made it, its typed fields, its evidence with where each piece was found, and what it is
tied to both ways - every one a link. A question offers its options; an answer given shows until it
is applied - *Apply* on the rail derives the space again - and a click takes it back. A group shows
its members; a step what it read and made. Clicking a face on the part opens that face's card: what
lies on it, which features and interfaces it belongs to.

## The agent

The agent reads the same graph with a few general tools: **pipeline** (every step, what it said and
made), **entities** (by kind, step or words), **entity** (one in full, links both ways), **show**
(put entities in focus on the engineer's screen), **answer** (record an answer - only one the
engineer's words give, quoted exactly, and only as one of the question's options) and **derive**
(apply the answers; the rail shows the run). It reads the part itself with find, describe, relate
and measure, and the drawing with search_drawing. What is in focus goes to it with the engineer's
words. It never makes geometry or designs, and never changes what was read from the files.

## Over HTTP

| route | what |
|---|---|
| `GET /api/pipeline` | both stages: every step with its status, what it read and made |
| `POST /api/pipeline/run` | derive the design space - or read it back - as a stream of steps |
| `GET /api/entities` | entities in a few words: by kind, step, ids or words |
| `GET /api/entities/{id}` | one in full, with its links both ways |
| `GET /api/entities/schema` | every kind's fields, as JSON Schema |
| `POST /api/answers` | keep an answer - one of the question's options, or none to take it back |
| `GET /api/designspace/cells/{layer}` | a layer's cells, one integer a visible face; mid-run, the layers made so far |
| `GET /api/designspace/values/benefit` | where metal helps, a value a face of the allowed cells |
| `GET /api/designspace/faces/{kind}` | a per-face value: thickness, height, interface, sealing |
| `POST /api/agent/chat` | a message to the agent with what is in focus, answered as a stream |
