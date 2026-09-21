# fastcae docs

The directory. Every document in `docs/` is reachable from here, either directly or through its
folder's index. Start with [status.md](status.md) for what runs today.

## Pages

| Page | What it is |
|---|---|
| [status.md](status.md) | What runs now, tab by tab, and what is next. Start here |
| [build-plan.md](build-plan.md) | The plan as agreed: what is built, in what order, how each step is judged |
| [architecture.md](architecture.md) | The system as it is: a general platform, the stages in the order they run, how a new part loads without an edit |
| [pipeline.md](pipeline.md) | One pipeline from the files to the design space: its steps, the typed entities they make, the rail, focus, the card, the agent, the routes |
| [design-space.md](design-space.md) | The one volume where metal may be added: kept with the project, defined by rules where none is brought, measured on the housing |
| [rib-network-status.md](rib-network-status.md) | Rib networks, where the work stands: the problem as given, what was built, what is solved and how - fusion, slivers, conversion, beating the target - what is not, and what comes next |
| [design-generation.md](design-generation.md) | Every generation approach tried and where each stopped, what 152 solved designs measured, why the only designs that beat production cannot yet be built, what each piece built so far is for, and what the evidence says to do |
| [rib-optimisation-plan.md](rib-optimisation-plan.md) | The plan as agreed: a rib as a root curve with profiles along it, castable by construction and differentiable throughout, the steps to build it and the gate each one is judged at |
| [designs.md](designs.md) | A rib network in the design volumes the engineer picks: one constrained problem held to the target - seeded through one gate of placement, moved under the target's metal, chosen by CP-SAT, built as CAD, meshed face by face, solved - and every stage on screen |
| [extract.md](extract.md) | The ten extraction steps: CAD, geometry health, the face atlas, features, drawing, solver deck, and tying the deck's groups to CAD faces |
| [simulate.md](simulate.md) | How the engineer's own deck and results are read and solved again, and carried to every design |
| [tasks.md](tasks.md) | Not built. How the system asks a person for work |
| [verification.md](verification.md) | Not built. How extraction's claims get checked by a person |

## Folders

| Folder | What is in it |
|---|---|
| [research/](research/README.md) | fastcae's own research and measurements: the market, how others generate variants, meshing and solver benchmarks on this housing, the baseline deck, campaign runs, surrogates, agents, and how the outside documents were read. The index summarises each |
| [inputs/](inputs/README.md) | Documents from outside fastcae: method reports, plans written for fastcad, role strategies, fastcad's own pages. They inform decisions; they are not the plan. The index summarises each |
| [archive/](archive/README.md) | Superseded plans and methods, and what the current design kept from each |

## Where to find

| Looking for | Read |
|---|---|
| What works today | [status.md](status.md) |
| How a solver deck is read and reproduced | [simulate.md](simulate.md), [extract.md](extract.md) |
| Measured meshing accuracy, field against CAD | [research/field-meshing-gate.md](research/field-meshing-gate.md) |
| Why cuDSS, and every solver tried | [research/solver-choice.md](research/solver-choice.md), [research/design-to-solution.md](research/design-to-solution.md) |
| The baseline's own deck | [research/baseline-deck.md](research/baseline-deck.md) |
| Campaigns solved unattended | [research/campaign-runs.md](research/campaign-runs.md) |
| Where metal may go, and why | [design-space.md](design-space.md) |
| The design space measured on the housing | [research/design-space-on-the-housing.md](research/design-space-on-the-housing.md) |
| The typed entities an agent reads | [pipeline.md](pipeline.md) |
| How designs are made and what each stage shows | [designs.md](designs.md) |
| Which generation approach works, and why, and what is next | [design-generation.md](design-generation.md) |
| The earlier variant method | [archive/generate.md](archive/generate.md), [archive/ribs.md](archive/ribs.md) |
| Competitors and positioning | [research/market.md](research/market.md), [research/geometry-generation.md](research/geometry-generation.md) |
| Surrogates and datasets | [research/surrogates.md](research/surrogates.md), [research/data-factories.md](research/data-factories.md) |
| Topology optimisation methods (MMC, GET, TreeTOp, SIMP) | [inputs/research/](inputs/README.md#research---reports-on-methods) |
| The earlier agenticCAE project on the same housing | [research/agenticcae.md](research/agenticcae.md) |
