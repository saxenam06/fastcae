# Inputs

Documents brought in from outside fastcae: research reports, plans written for the sibling fastcad
project, career strategy, and fastcad's own pages. They inform decisions; they are not fastcae's
plan. What fastcae does now is in [../status.md](../status.md) and [../build-plan.md](../build-plan.md);
how several of these were read against fastcae is in
[../research/reference-docs.md](../research/reference-docs.md).

## research/ - reports on methods

| Document | What it covers |
|---|---|
| [CAD-Light and Manufacturing-Ready Topology Optimization](research/CAD-Light%20and%20Manufacturing-Ready%20Topology%20Optimization%20%20Recent%20Papers%20and%20a%20Gearbox-Housing%20Research%20Path.md) | Explicit and geometry-parameterised topology optimisation (MMC, GET, Force Flow Members, GGP, B-spline and NURBS fields), casting-constrained methods, turning TO results into CAD, and a proposed gearbox research path |
| [Exact CAD-Face Provenance Through Tetrahedral Meshing](research/Exact%20CAD-Face%20Provenance%20Through%20Tetrahedral%20Meshing.md) | Keeping every mesh triangle tied to the CAD face it came from, through tet meshing |
| [Physical-AI Cast Housing Design Generation](research/physical_ai_cast_housing_design_generation_research.md) | A deterministic, constraint-aware "design compiler" for 4,000 valid cast-housing variants per study, each a compact declarative program |
| [Reducing the build and mesh time](research/I%20want%20to%20reduce%20computational%20time%20of%20build%20and%20m.md) | A Perplexity deep-research answer on cutting build and mesh time so 4,000 designs take hours, not days |
| [deep-research-report.md](research/deep-research-report.md) | Related projects and methods, grouped by relevance |
| [deep-research-report (1).md](research/deep-research-report%20%281%29.md) | A generic guide to planning a research project |

## plans/ - architectures and product plans, mostly for fastcad

| Document | What it covers |
|---|---|
| [cpsat_get_combined_plan.md](plans/cpsat_get_combined_plan.md) | CP-SAT picks an organised experiment (zones, symmetry, budget, holes), GET finds the smooth material inside it, FEA judges; 100-200 records from the GRC housing |
| [fastCAD_agent_native_architecture.md](plans/fastCAD_agent_native_architecture.md) | Agents decide and coordinate, deterministic tools generate and verify, FEA is the truth; agent roles, the Design Contract, what agents may not do |
| [fastCAD_updated_plan.md](plans/fastCAD_updated_plan.md) | A governed simulation-data factory: protected functional core, discovered anchor regions, 100-200 qualified records |
| [fastcad_final_blueprint.md](plans/fastcad_final_blueprint.md) | The synthesised Stage-1 blueprint: no natural-language CAD editing, no implicit-geometry FEA; product, architecture and implementation |
| [fastCAD_final_consolidated_build_plan.md](plans/fastCAD_final_consolidated_build_plan.md) | Stage-1 build specification: cost-aware, agentic data factory; a 40-variant unattended campaign early, a second part later |
| [fastCAD_final_consolidated_build_plan_v2_agentic_design_synthesis.md](plans/fastCAD_final_consolidated_build_plan_v2_agentic_design_synthesis.md) | Version 2 of that specification, adding agentic design synthesis |
| [fastCAD_final_consolidated_build_plan_v3_implementation_freeze.md](plans/fastCAD_final_consolidated_build_plan_v3_implementation_freeze.md) | Version 3, frozen for implementation: governed design synthesis, deterministic engineering truth, cost-aware campaign learning |
| [fastCAD End-to-End Build Document.md](plans/fastCAD%20End-to-End%20Build%20Document.md) | An end-to-end build document for the same Stage 1: one trusted CAE case in, qualified design/physics records out |
| [fastcad_agentic_intelligence_architecture.md](plans/fastcad_agentic_intelligence_architecture.md) | What makes the system agentic rather than a scripted pipeline: propose, evaluate, learn, re-plan |
| [fastcad_cost_aware_agentic_system.md](plans/fastcad_cost_aware_agentic_system.md) | A cost-aware router: deterministic and cheap models for routine work, frontier models only where they pay |
| [fastcad_grc_housing_consolidated_strategy.md](plans/fastcad_grc_housing_consolidated_strategy.md) | A housing-only data factory built on the exact GRC B-rep; strategy and research consolidated |
| [cae-product-blueprint.md](plans/cae-product-blueprint.md) | The "constraint-governed simulation data factory" as a product: market, technology, commercial model |
| [Constraint-Governed Simulation Data Factory](plans/Constraint-Governed%20Simulation%20Data%20Factory%20%20Product%20and%20Technology%20Blueprint.md) | An earlier copy of the same blueprint, nearly identical |
| [fastcad-v1-plan.md](plans/fastcad-v1-plan.md) | fastcad's plan of record, rev B: its grilling decisions plus what research added |
| [fastcad-positioning.md](plans/fastcad-positioning.md) | fastcad against 21 research sources, platforms and startups: variants of existing production parts, castable, checked in the customer's FE setup |

## strategy/ - applying the work to roles

| Document | What it covers |
|---|---|
| [Neural Concept EV Powertrain Role](strategy/Neural%20Concept%20EV%20Powertrain%20Role%20%20GRC%20Gearbox%20Demonstration%20Strategy.md) | How the GRC gearbox work maps to Neural Concept's EV powertrain Applied AI Engineer role, with an e-motor extension |
| [End-to-End CAE + Physics-AI Portfolio](strategy/End-to-End%20CAE%20+%20Physics-AI%20Portfolio%20for%20Neural%20Concept.md) | A portfolio plan led by a bumper-beam crash workflow, with a drop-test transfer benchmark |

## fastcad/ - the sibling project's own pages

Copied on 2026-09-18. Their links point inside the fastcad repository and do not resolve here.

| Document | What it covers |
|---|---|
| [README.md](fastcad/README.md) | fastcad's docs index |
| [status.md](fastcad/status.md) | fastcad's status on 2026-09-16: planning accepted, M0 steps 1-3 done |
| [next-steps.md](fastcad/next-steps.md) | fastcad's step list |
| [environment.md](fastcad/environment.md) | fastcad's environment, checked 2026-09-15 |
