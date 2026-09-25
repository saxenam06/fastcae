# The pipeline

**One pipeline from the engineer's files to the design space, and one vocabulary for everyone who
reads it.** Every step's inputs and outputs are typed entities; the rail shows the steps, the
canvases show the entities, the card shows one in full, and the agent reads the same JSON. The code is
`src/fastcae/pipeline/` (entities, read, space, graph) and `src/fastcae/api/pipeline.py`.

---

## The steps

**Read the engineer's files** - the extraction steps ([extract.md](extract.md)): discover the
artifacts, read the CAD, check its health, measure every face, detect features, read the drawing,
cross-check it against the CAD, read the solver deck and its results, and tie the deck's groups to
the CAD faces they lie on. Each feeds something after it: the CAD and its faces and features the
design space and every design's mesh; the drawing and its controls the faces the design space keeps
clear, and the Drawing tab; the deck and its ties to the CAD the design space, every design's solve
and the Mesh & setup tab. They run when the files are extracted and are kept while the files do not
change.

**Design space** - the last step ([design-space.md](design-space.md)): read from the project's
folder, or - when the engineer brought none - defined there by fastcae's rules, which say what they
are doing as they go. It is one entity, the volume where metal may be added.

Each step says its status - to run, running, done, read back, skipped, failed - how long it took, a
line on what it found, what it **read** and what it **made**. An input names the step that made it.

## Typed entities

Every entity has an id, a kind, a few words, the step that made it, an **origin**, where it can be
**shown**, its **links** to other entities and the **evidence** behind it; each kind adds typed
fields of its own (pydantic models, one discriminated union - `GET /api/entities/schema`).

| origin | means |
|---|---|
| imported | read from a file the engineer brought: a face of the CAD, a group of the deck, their design space |
| derived | computed from imported entities by a rule: a feature, the design space the rules defined |
| inferred | a reading that could be wrong: a callout matched to a feature |
| generated | proposed by fastcae: a design |

Ids are readable and stable while the files do not change: `face:196`, `bore:196`, `group:BORE_MAIN_S2`,
`callout:p2:14`, `design_space`.

Kinds: artifact, part, health, face, axis, feature, callout, control, conflict, deck group, support,
coupling, load, material, signal, result field, anchor (a deck group on CAD faces), and the design
space - its volume outside and inside, what it keeps clear and how much, the settings it was defined
with, and where metal helps.

**Links are read both ways.** A feature lies on its faces; a control is evidenced by the drawing's
callout; an anchor ties a deck group to its faces; the design space is round the part.
`GET /api/entities/{id}` gives an entity with every link named and every entity that links to it.

## On screen

**The rail is the pipeline.** Each step a row with its dot - filled when done, hollow when read back,
pulsing while it runs - its name and time, and under it the line it said. A step opens to what it
read, as chips that go to the step that made them, and what it made, as groups that open to their
entities.

**Focus.** A click on a step, a group, an entity, a chip, a link on the card, a face on the part or an
entity the agent shows puts it in focus, and focus decides what every canvas shows:

| canvas | shows |
|---|---|
| **Drawing** | the callout, highlighted and brought into view; a group of callouts filters the list |
| **CAD · Part** | the entity's faces, selected; something small picked from the rail or a card is looked at |
| **CAD · Design space** | the design space, opaque, over the part - with switches for the part, the design space and where metal helps |
| **Mesh & setup · Setup** | the deck group, lit on the deck's mesh |
| **Mesh & setup · Solve results** | the deck solved: the engineer's Code_Aster run and cuDSS on the same mesh, as tabs under the picture |

Something picked from the rail or a card, or shown by the agent, is looked at: a flat face from the
side it faces, a round one down its axis from the end away from the part's middle.

**The card** on the right shows what is in focus in full: an entity's kind, origin and status, the
step that made it, its typed fields, its evidence with where each piece was found, and what it is
tied to both ways - every one a link. A group shows its members; a step what it read and made.

## The agent

The agent reads the same graph with a few general tools: **pipeline** (every step, what it said and
made), **entities** (by kind, step or words), **entity** (one in full, links both ways) and **show**
(put entities in focus on the engineer's screen). It reads the part itself with find, describe,
relate and measure, and the drawing with search_drawing. What is in focus goes to it with the
engineer's words. It never makes geometry or designs, and never changes what was read from the files
or the design space.

## Over HTTP

| route | what |
|---|---|
| `GET /api/pipeline` | every step with its status, what it read and made; the design space last |
| `POST /api/pipeline/run` | read the design space - or define it - as a stream; `{"again": true}` defines it anew by the rules |
| `GET /api/entities` | entities in a few words: by kind, step, ids or words |
| `GET /api/entities/{id}` | one in full, with its links both ways |
| `GET /api/entities/schema` | every kind's fields, as JSON Schema |
| `GET /api/designspace` | what the design space holds and how it was defined |
| `GET /api/designspace/cells/design` | its cells, one integer a visible face |
| `GET /api/designspace/values/benefit` | where metal helps, a value a visible face |
| `POST /api/agent/chat` | a message to the agent with what is in focus, answered as a stream |
