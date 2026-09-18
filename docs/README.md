# fastcae docs

The directory. Every document in `docs/` is reachable from here, either directly or through its
folder's index. Start with [status.md](status.md) for what runs today.

## Pages

| Page | What it is |
|---|---|
| [status.md](status.md) | What runs now, tab by tab, and what is next. Start here |
| [build-plan.md](build-plan.md) | The plan as agreed: what is built, in what order, how each step is judged |
| [architecture.md](architecture.md) | The system as it is: a general platform, the stages in the order they run, how a new part loads without an edit |
| [extract.md](extract.md) | The ten extraction steps: CAD, geometry health, the face atlas, features, drawing, solver deck, and tying the deck's groups to CAD faces |
| [simulate.md](simulate.md) | How the engineer's own deck and answer are reproduced before anything is built, and carried to every design |
| [generate.md](generate.md) | What a design is, how it is built, turned into a surface and checked |
| [ribs.md](ribs.md) | The design space from the engineer's words: variants, placements, rules, campaigns |
| [tasks.md](tasks.md) | Not built. How the system asks a person for work |
| [verification.md](verification.md) | Not built. How extraction's claims get checked by a person |

## Folders

| Folder | What is in it |
|---|---|
| [research/](research/README.md) | fastcae's own research and measurements: the market, how others generate variants, meshing and solver benchmarks on this housing, the baseline deck, campaign runs, surrogates, agents, and how the outside documents were read. The index summarises each |
| [inputs/](inputs/README.md) | Documents from outside fastcae: method reports, plans written for fastcad, role strategies, fastcad's own pages. They inform decisions; they are not the plan. The index summarises each |
| [archive/](archive/README.md) | Superseded plans from the earlier project, and what the current design kept from each |

## Where to find

| Looking for | Read |
|---|---|
| What works today | [status.md](status.md) |
| How a solver deck is read and reproduced | [simulate.md](simulate.md), [extract.md](extract.md) |
| Measured meshing accuracy, field against CAD | [research/field-meshing-gate.md](research/field-meshing-gate.md) |
| Why cuDSS, and every solver tried | [research/solver-choice.md](research/solver-choice.md), [research/design-to-solution.md](research/design-to-solution.md) |
| The baseline's own deck | [research/baseline-deck.md](research/baseline-deck.md) |
| Campaigns solved unattended | [research/campaign-runs.md](research/campaign-runs.md) |
| How variants are defined and sampled | [ribs.md](ribs.md), [generate.md](generate.md) |
| Competitors and positioning | [research/market.md](research/market.md), [research/geometry-generation.md](research/geometry-generation.md) |
| Surrogates and datasets | [research/surrogates.md](research/surrogates.md), [research/data-factories.md](research/data-factories.md) |
| Topology optimisation methods (MMC, GET, TreeTOp, SIMP) | [inputs/research/](inputs/README.md#research---reports-on-methods) |
| The earlier agenticCAE project on the same housing | [research/agenticcae.md](research/agenticcae.md) |
