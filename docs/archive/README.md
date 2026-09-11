# Archive

These documents are **not current**. [rib-layouts.md](../rib-layouts.md) was drawn from them on
2026-09-11 and supersedes them. Four of them were written for the previous project, so they cite
files that do not exist in this repository: `mesh/surface.py`, `fem/aster.py`, `handbook/`,
`production.step`, `groups.json`, `basis.npy`. They also disagree with each other on schedule and
phase order.

| document | what it is | what the plan took from it |
|---|---|---|
| [16-implicit-rib-variants.md](16-implicit-rib-variants.md) | Research note. How nTop builds ribs, with sources; the housing and its ribs as measured; candidate open-source kernels; the case for offset-closing; the measured cost of an immersed grid on this part | The mechanism: layout, then ribs, then blended union, then protected areas. The rib's parameters, the ring zones and the division of work. Offset-closing is kept as the fallback fillet. The grid-cost numbers go to the physics plan |
| [grc-rib-plan.html](grc-rib-plan.html) | Plain-language plan. Five rules, the checks, milestones M0 and M1, the tools | Ribs follow the mould. Building is not the same as correct. Videos are not designs. The agent suggests and a script checks. Protected areas are cut back after every blend. The check list, and the first campaign of 64 |
| [gb3-agentic-immersed-ai-platform-master-plan.md](gb3-agentic-immersed-ai-platform-master-plan.md) | Platform master plan. The Design Space Object, evidence states, gated agent actions, an immersed solver, a surrogate roadmap | Every rule and variable carries its evidence state. The rule that the agent proposes and a person confirms, which goes to the campaign plan |
| [grc-gb3-immersed-simulation-implementation-plan.md](grc-gb3-immersed-simulation-implementation-plan.md) | Implementation plan for a cut-cell FEM, phases P0–P9 with gates | Nothing for this plan. It is one starting point for the physics plan, to be read against the measured grid costs in the research note |
| [immersive-geometry-gb3-integration-plan.md](immersive-geometry-gb3-integration-plan.md) | Immersive scene and entity graph; the B-rep stays authoritative | The line that a generated surface is not manufacturing CAD: a finalist is rebuilt in CAD and checked again |
