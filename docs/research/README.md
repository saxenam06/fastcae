# Research: physics AI on generated cast-part variants

What the field offers, September 2026, for every step from a plain cast part to a trained,
trusted surrogate - and where fastcae stands against it. Each document gives the sources with links
and dates; runtimes marked *(est.)* are estimates, not published benchmarks.

| Document | What it covers |
|---|---|
| [market.md](market.md) | The physics-AI market: vendors, what each does and does not do for structural parts and castings, the hurdles industry reports, where fastcae is distinctive, positioning, risks, what a credible demonstration shows |
| [geometry-generation.md](geometry-generation.md) | How variants are generated - parametric CAD with optimiser wrappers, mesh morphing, implicit modelling, feature scripts and rule engines, learned generative geometry, research - how each keeps a combination of features feasible, and how vendors get training data |
| [simulation.md](simulation.md) | Solving thousands of designs: meshing, solvers, GPU solvers (direct and iterative), voxel and cut-cell (immersed) methods, measured sizes and times on this housing, what speeds each route up |
| [design-to-solution.md](design-to-solution.md) | One generated design taken to a solved example every way we could on this workstation - building on the GPU, six meshers (fTetWild, gmsh, TetGen, MeshLab and MeshFix, MMG, CGAL from the field), eight solvers, voxel and cut-cell grids - what each approach means, what it measured, why it failed or won, and what each tool needed; from 2.3 hours to 2.5 minutes a design |
| [surrogates.md](surrogates.md) | Surrogate architectures for 3D fields on varying geometry, data-efficient generation (active learning, uncertainty, pretraining, superposition), benchmark datasets and formats |
| [orchestration-and-agents.md](orchestration-and-agents.md) | Running a campaign of thousands of solves - job runners, cloud bursts, provenance - and LLM agents in simulation workflows |
| [optimization.md](optimization.md) | Surrogate-based optimisation as vendors and open source practise it, and the stack recommended here |
| [agenticcae.md](agenticcae.md) | The earlier agenticCAE project on the same housing: its load case, supports, mesh, solver, measured times, cloud runs and agent - what fastcae reuses and what it adapts |
| [reference-docs.md](reference-docs.md) | What the three strategy documents in `docs/` decide and leave open |

## Where fastcae stands, in short

- **Distinctive**: rule-guaranteed castable variants of a plain, non-parametric part. No vendor
  selects feasible combinations of features with a solver; they freeze which features exist
  (morphing, sizing after topology optimisation), try and discard, check afterwards, or learn what
  looks plausible. fastcae places pieces from rules and keeps, with CP-SAT, the largest set of them
  that obeys every rule between them - so which ribs and holes exist is part of the design space,
  every design sent to a solver obeys every encoded rule, and every piece left out says which rule it
  broke. See [geometry-generation.md](geometry-generation.md).
- **Scarce in the market**: valid geometry and labelled data, not models. Surrogates are
  commoditising; data preparation is the top blocker industry names. See [market.md](market.md).
- **Not distinctive**: generating ribs, robust geometry, surrogate optimisation, rule checking, the
  mathematics itself. Agents are everywhere; they are the audit trail, not the pitch.
- **Hard part ahead**: stress at fillets and rib roots - in the labels (mesh fidelity) and in the
  model (the weakest spot of every published surrogate). See [simulation.md](simulation.md) and
  [surrogates.md](surrogates.md).
- **Measured, not guessed**: a design goes from recipe to solved example in about 2.5 minutes on this
  workstation - built on the GPU, meshed straight from its field, solved by cuDSS - within 2.3 % of the
  slow route's Code_Aster answer. See [design-to-solution.md](design-to-solution.md).
