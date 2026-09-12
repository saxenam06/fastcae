# End-to-End CAE + Physics-AI Portfolio for Neural Concept

## Executive decision

The strongest flagship is **automotive component crashworthiness: a parameterized bumper-beam pole-impact workflow**, followed by a **smaller consumer-electronics drop-test transfer benchmark**. This choice has the best current open-source chain: OpenRadioss for nonlinear explicit simulation, an official bumper-beam model, an existing OpenRadioss-to-PhysicsNeMo pipeline, a 131-run ready-to-use dataset, NVIDIA's crash-surrogate recipe, and the much larger CarCrashNet benchmark.[^1][^2][^3][^4][^5]

This is a better first project than full occupant or pedestrian safety. It permits real CAD/geometry changes, shell remeshing or controlled mesh morphing, contacts, rate-dependent plasticity and failure, automated runs, field post-processing, temporal neural surrogates, uncertainty-aware optimization, HPC execution, CI, and an auditable handover package—without immediately inheriting the licensing, calibration, and validation burden of human-body models, dummies, belts, airbags, and complete restraint systems.

The portfolio should be branded as a **production vertical-solution asset**, not as a notebook collection. The core claim should be: *a reproducible design-change-to-validated-result system in which AI accelerates exploration, while the explicit solver remains the release authority*.

## Why this domain wins

| Candidate | Open model/data | Full CAD-to-AI feasibility | Job relevance | Main limitation | Decision |
|---|---|---:|---:|---|---|
| Bumper-beam pole impact | Official OpenRadioss example, 131-run community dataset, CarCrashNet with 14,742 component simulations[^1][^6][^5] | Excellent | Crash, contact, material failure, DOE, surrogate, optimization | Component rather than complete vehicle | **Flagship** |
| Phone drop | Official simplified 1.5 m example and OpenRadioss/ParaView demonstration[^1][^7] | Excellent | Directly addresses consumer-electronics durability | Less public AI training data; simplified CAD | **Transfer benchmark** |
| Full-vehicle frontal crash | Public NHTSA/CCSA Yaris models and CarCrashNet full-vehicle data[^8][^9][^10] | Moderate, but computationally heavy | Very high automotive relevance | Hundreds of thousands to more than 1.5 million elements; geometry variation is difficult[^9] | Phase 2 validation |
| Occupant safety | NHTSA integrated Yaris/occupant model exists and was validated for several frontal configurations[^11] | Low for a first independent build | Very high | Dummy, belt, airbag, injury criteria, licensing and specialist calibration | Do not lead with it |
| Pedestrian safety | Possible with subsystem impactors | Moderate | High | Public end-to-end data and validated model availability are weaker | Future extension |

## Target architecture

```text
FreeCAD/OpenCascade parameter model or controlled baseline mesh
                         |
             geometry/mesh quality gates
                         |
       Gmsh or SALOME SMESH + named physical groups
                         |
             OpenRadioss deck templating
                         |
      unit-aware model lint + small coupon verification
                         |
       local Docker runner / Slurm Submitit campaign
                         |
 OpenRadioss Starter -> Engine -> animation/time histories
                         |
 Vortex-Radioss / lasso-python -> VTP/Zarr + KPI tables
                         |
 baseline correlation + DOE database + data/version lineage
                         |
 PhysicsNeMo MGN/Transolver/GeoTransolver + uncertainty gate
                         |
 BoTorch constrained multiobjective candidate selection
                         |
         solver confirmation of every proposed optimum
                         |
 ParaView/PyVista dashboard + benchmark and handover report
```

OpenRadioss is explicitly intended for crash, shock, impact and electronics drop testing, and it can consume many LS-DYNA-format public models. PhysicsNeMo provides reusable PyTorch components and end-to-end recipes, with MeshGraphNet identified for unstructured-mesh dynamics and vehicle crash. Its crash recipe supports GeoTransolver, Transolver and MeshGraphNet, while the documented ETL path ingests solver outputs such as d3plot and converts geometry and time-dependent deformation to GPU-oriented formats such as Zarr or VTP.[^12][^13][^2][^14]

## Repositories to use

| Layer | Primary repository/tool | Use in the asset | Caveat |
|---|---|---|---|
| Explicit solver | `OpenRadioss/OpenRadioss`[^15] | Nonlinear contact, impact, failure, time histories | Learn native Radioss cards; do not rely only on LS-DYNA compatibility |
| Reference decks | `OpenRadioss/ModelExchange`[^4] | Bumper beam, phone drop, coupons, HPC examples | Freeze an exact model revision in the project |
| Existing E2E bridge | `HoussemMouradi/OpenRadioss2PhysicsNeMo`[^3] | Fastest bootstrap for solve-to-curated-data workflow | Audit and refactor rather than merely forking unchanged |
| Large benchmark | `Mohamedelrefaie/CarCrashNet`[^10] | External generalization and full-vehicle extension | Full release is multi-terabyte; begin with component subset |
| AI framework | `NVIDIA/physicsnemo` crash example[^2][^16] | MGN/Transolver/GeoTransolver training and rollout | GPU memory and temporal error accumulation require profiling |
| CAD | `FreeCAD/FreeCAD`[^17] | Parameterized manufacturable beam and bracket geometry via Python/OpenCascade | For production-like thin sheets, preserve midsurface semantics |
| Meshing | `SalomePlatform/smesh`[^18] | Groups, filters, mesh editing and quality control | Heavy deployment; use only where it adds robust grouping |
| Python Gmsh | `nschloe/pygmsh`[^19] | Scriptable geometry/mesh prototyping | Use native Gmsh API when advanced control is needed |
| Radioss results | `Vortex-CAE/Vortex-Radioss`[^20] | Read animation/time history and convert animation to d3plot | Beta-quality areas need tests |
| d3plot results | `open-lasso-python/lasso-python`[^21][^22] | Extract fields, parts, displacement, strain and deletion | Add regression fixtures for the arrays actually consumed |
| Optimization | `meta-pytorch/botorch`[^23] | Constrained multiobjective Bayesian optimization | Keep hard physics/geometry constraints outside learned acquisition |
| HPC | `facebookincubator/submitit`[^24] | Same Python run API locally and on Slurm | Solver binaries and MPI configuration remain environment-specific |
| Visualization | ParaView/PyVista | Automated contours, deformation, curves and comparative views | Visuals must accompany quantitative correlation, not replace it |

Avoid making `freecad-parametric-fea` a foundation: its own repository calls it an early release, warns against serious structural analysis, and reports only static testing. FreeCAD itself remains suitable as a scriptable parametric CAD source because it provides an OpenCascade-backed parametric modeler and broad Python API.[^17][^25]

## Flagship engineering definition

### Baseline problem

Start with the official OpenRadioss **bumper beam against rigid pole** model. Create a controlled design family with 5–8 variables:[^1]

- Beam gauge.
- Hat-section depth and width.
- Flange width.
- Corner radius.
- Local reinforcement length and gauge.
- Pole lateral offset.
- Impact velocity.
- Material card choice or selected calibrated material parameters.

Use shell elements and named sets for beam, reinforcement, impactor, constraints and measurement sections. Preserve a frozen baseline deck before introducing geometry automation.

### Outputs and constraints

Report full time series as well as scalars:

- Intrusion or maximum displacement at defined nodes/regions.
- Peak and filtered reaction/contact force.
- Absorbed internal energy and specific energy absorption.
- Force-displacement response.
- Plastic strain field and failed-element pattern.
- Beam mass.
- Energy balance: kinetic, internal, contact, hourglass and total energy.
- Minimum stable time step, mass increase from mass scaling and wall time.

Optimization should minimize mass and intrusion while constraining force, energy-balance error, hourglass contribution, mesh quality and failure mode. Exact acceptance thresholds must be established from baseline mesh/time-step sensitivity and relevant company practice; do not invent universal thresholds.

### Verification ladder

1. **Card verification:** tensile coupon for the chosen elastoplastic/failure law; contact and element tests.
2. **Baseline reproduction:** rerun the unmodified official deck and compare documented curves/energies.
3. **Mesh study:** at least three meaningful mesh resolutions, comparing force, intrusion, energy and failure topology.
4. **Time-step/mass-scaling study:** demonstrate that acceleration does not materially distort the target KPIs.
5. **Parameter sanity:** monotonic expectations where physically appropriate; investigate counterintuitive cases.
6. **Cross-solver check:** if temporary LS-DYNA access exists, run selected designs in both solvers. CarCrashNet itself reports an OpenRadioss workflow validated against physical testing and commercial LS-DYNA, making it a useful external benchmark.[^6]
7. **Physical correlation extension:** use published NHTSA/CCSA full-vehicle data only as an external extension, and clearly respect that NHTSA says its models are validated only for specific crash conditions.[^8]

## AI surrogate plan

### Dataset strategy

Begin with the public 131-run OpenRadioss bumper-beam dataset, which includes raw d3plot and curated VTP, then regenerate a smaller subset to prove ownership of the workflow. Next generate 200–500 runs from the new parameterization using a space-filling DOE, retaining failed simulations and their failure labels instead of silently deleting them.[^5]

For scaling, use CarCrashNet's 14,742 bumper-beam simulations and 825 full-vehicle simulations; the reported release totals 6.65 TB, so staged or subset-based ingestion is essential. SHIFT-Crash is another full-vehicle resource with more than 5,000 morphed Yaris simulations and time-resolved fields, but its approximately 1.4 TB size and CC-BY-NC license make it better for research benchmarking than commercial solution packaging.[^26][^10][^6]

### Model ladder

- **Scalar baseline:** XGBoost or a small MLP predicting mass, peak force, intrusion and absorbed energy.
- **Field baseline:** POD/PCA coefficients plus a regressor; this establishes whether a deep geometry model is truly adding value.
- **Primary temporal model:** PhysicsNeMo MeshGraphNet or Transolver on the unstructured surface mesh.
- **Scale candidate:** GeoTransolver for larger meshes and cross-geometry behavior.
- **Failure classifier:** separate model predicting run failure, mesh failure or unacceptable energy behavior.
- **Uncertainty:** deep ensemble or conformal calibration; route out-of-distribution/high-uncertainty cases to OpenRadioss.

Split by **geometry family or parameter regions**, not randomly by individual frames. Otherwise time frames from nearly identical simulations leak between train and test. Evaluate scalar errors, field errors, temporal rollout stability, peak timing, curve similarity, deformed-shape topology, energy behavior and inference latency.

### Trust contract

The surrogate proposes and ranks designs; it does not certify them. Every Pareto candidate must be rerun in OpenRadioss, compared against the prediction with predeclared tolerances, and added to the versioned dataset. This active-learning loop uses BoTorch's modular models, acquisition functions and optimizers for an expensive black-box function while retaining deterministic engineering gates.[^23][^27]

## Production workflow

### Repository structure

```text
neural-crash-vertical/
  apps/                 # dashboard/API
  cad/                  # parameter definitions, STEP exports
  mesh/                 # meshing scripts, quality checks, named groups
  decks/                # templates and frozen baseline
  materials/            # cards, provenance, coupon validation
  workflows/            # local and Slurm execution
  post/                 # readers, filters, KPIs, VTK exports
  data_contracts/       # schemas for design/run/field metadata
  surrogate/            # configs, training, inference, calibration
  optimization/         # DOE, constraints, BO and solver confirmation
  validation/           # benchmark curves and acceptance criteria
  tests/                # unit, integration, regression and smoke cases
  containers/           # pinned CPU/GPU images
  docs/                 # solution guide, sales demo, CS runbook
  .github/workflows/    # lint, unit tests and tiny solver regression
```

Each run should have immutable identifiers for geometry, mesh, deck, material, solver build, container, hardware, random seed and post-processing version. Store a `manifest.json`, logs, quality report, KPI parquet/CSV, curated mesh/field files and generated report for each run.

### CI levels

- **Pull-request CI:** formatting, type checking, unit tests, deck-schema tests, geometry constraints and a seconds-long explicit smoke test.
- **Nightly CI:** coupon suite, mesh regression, baseline bumper run and post-processing golden-file comparisons.
- **Release CI:** selected DOE cases, surrogate inference regression, uncertainty calibration check and regenerated customer-facing report.
- **HPC qualification:** strong/weak scaling study, restart/resubmission, corrupted-output detection and deterministic result checks.

Submitit provides a lightweight Python abstraction that can switch between local execution and Slurm and exposes job results and logs, making it appropriate for the campaign runner.[^24]

## Delivery roadmap

| Phase | Duration | Exit artifact |
|---|---:|---|
| Solver foundation | Weeks 1–3 | Reproduced bumper, tensile/contact coupons, documented nonlinear explicit choices |
| Parameterized preprocessing | Weeks 4–6 | CAD or controlled mesh parameterization, repeatable mesh/deck creation, quality gates |
| Automation and post | Weeks 7–9 | One-command local run, KPI extraction, ParaView/PyVista assets, run manifests |
| DOE and HPC | Weeks 10–13 | 100+ valid solver runs, Slurm execution, failure recovery, database/data card |
| Surrogate | Weeks 14–18 | Scalar baseline plus temporal field model, held-out validation and uncertainty gate |
| Optimization | Weeks 19–21 | Pareto search with solver-confirmed candidates and measured acceleration |
| Productization | Weeks 22–24 | UI/API, CI, containers, benchmark report, sales demo and Customer Success runbook |
| Transfer benchmark | Weeks 25–28 | Phone-drop workflow reusing the same orchestration/data contracts/model interfaces |

A credible compressed version can be completed in roughly six months if GPU/HPC access is available and scope stays at component level. The phone-drop transfer should reuse the platform abstractions rather than becoming a second bespoke codebase. OpenRadioss provides a simplified phone dropped from 1.5 m and an OpenRadioss/ParaView demonstration, which is enough to prove vertical transfer.[^7][^1]

## Job-requirement evidence

| Requirement | Portfolio evidence |
|---|---|
| Own vertical assets end to end | Versioned bumper-crash solution template plus phone-drop transfer package |
| CAD to visualization | Parameterized FreeCAD/OpenCascade geometry, mesh automation, deck, solve, post and web/ParaView review |
| Nonlinear structural depth | Contact, finite deformation, plasticity, rate effects, failure, element deletion, explicit stability and energy controls |
| Benchmarking | Coupon verification, mesh/time-step studies, baseline regression, external CarCrashNet/NHTSA comparison |
| Python tooling | Typed packages, CLI/API, deck builder, runner, parsers, KPI library and report generator |
| AI acceleration | Scalar and field/time surrogate, uncertainty/OOD routing, solver-verified active learning |
| Optimization | Constrained multiobjective BoTorch loop with solver confirmation |
| HPC/cloud | Local/Slurm runner, MPI scaling, checkpoint/retry, workload and cost telemetry |
| Product roadmap | Issue log translating workflow failures into platform capabilities and acceptance tests |
| Sales/Customer Success handover | Five-minute demo, solution brief, deployment guide, troubleshooting runbook and acceptance matrix |

## What not to claim

- Do not claim five to eight years of production crash experience from a portfolio project. Present prior NVH/FEM/MBD experience honestly and frame this as a rigorous explicit-dynamics specialization.
- Do not call a solver-trained surrogate “validated” solely because test loss is low.
- Do not use peak von Mises stress as the only crash metric.
- Do not random-split temporal frames from the same simulation.
- Do not hide divergent runs, negative volume, excessive mass scaling or poor energy balance.
- Do not begin with the full 1.5-million-element detailed Yaris; the public model is excellent for a later scale demonstration but unnecessary for proving the architecture.[^9]
- Do not make an agent responsible for changing material cards, contacts or solver controls without deterministic rules and approval. Agents may triage logs and recommend repairs; verified scripts and engineering gates remain authoritative.

## Application package

The public repository should contain enough data for a small end-to-end reproduction, while large/protected datasets are downloaded by scripts with license checks. Include:

- A 90-second architecture video.
- A 5–8 minute engineering demonstration.
- An explicit-solver validation note.
- A surrogate model card and data card.
- A benchmark dashboard showing accuracy, latency, uncertainty and solver confirmation.
- A failure gallery explaining bad contact, hourglass, time-step and mesh cases.
- A one-page vertical solution brief written for Sales.
- A deployment and troubleshooting runbook written for Customer Success.
- A technical roadmap showing how the component pipeline extends to the public NHTSA Yaris, occupant models and commercial HyperMesh/ANSA/LS-DYNA/Abaqus connectors.

The strongest interview demonstration is not the best-looking prediction. It is a live parameter change followed by automated model generation, quality gating, rapid surrogate inference with uncertainty, queued solver confirmation, comparison against the previous design, and a fully traceable result package.

---

## References

1. [Models - OpenRadioss](https://openradioss.org/models/) - Get started with Models for OpenRadioss powerful, industry-proven finite element open-source solver

2. [physicsnemo/examples/structural_mechanics/crash/README.md at ...](https://github.com/NVIDIA/physicsnemo/blob/main/examples/structural_mechanics/crash/README.md) - In this recipe, we demonstrate a unified pipeline for crash dynamics modeling. The implementation su...

3. [HoussemMouradi/OpenRadioss2PhysicsNeMo - GitHub](https://github.com/HoussemMouradi/OpenRadioss2PhysicsNeMo) - This repository provides a full pipeline for generating crash simulation datasets using OpenRadioss ...

4. [GitHub - OpenRadioss/ModelExchange](https://github.com/OpenRadioss/ModelExchange) - OpenRadioss is a powerful, industry-proven finite element solver for dynamic event analysis. This re...

5. [Add OpenRadioss Bumper Beam Community Dataset Section to ...](https://github.com/NVIDIA/physicsnemo/pull/1598) - A freely available, pre-generated dataset (131 runs, both raw d3plot and curated VTP, hosted on Hugg...

6. [CarCrashNet: A Large-Scale Dataset and Hierarchical ...](https://arxiv.org/html/2605.07098v2)

7. [DROP YOUR CELL-PHONE! OpenRadioss & Paraview Webinar · OpenRadioss · Discussion #2964](https://github.com/orgs/OpenRadioss/discussions/2964) - Please, do not miss this webinar on October 8th, organized by The french Competence Center CC-FR, co...

8. [Crash Simulation Vehicle Models](https://www.nhtsa.gov/crash-simulation-vehicle-models) - These crash simulation models were developed to support various research programs. While these model...

9. [2010 Toyota Yaris Detailed Finite Element Model](https://www.ccsa.gmu.edu/models/2010-toyota-yaris/)

10. [CarCrashNet: A Large-Scale Dataset and Hierarchical Neural ...](https://arxiv.org/html/2605.07098v1)

11. [DOT HS 812 087](https://www.nhtsa.gov/sites/nhtsa.gov/files/documents/812087_ivomforcrashworthiness.pdf)

12. [OpenRadioss: Home Page](https://openradioss.org/) - OpenRadioss Users' Day 2026 September 2nd, 2026 MTC Ansty Park, Coventry, UK Event Complete, links t...

13. [Building AI Surrogate Models for Structural and Automotive Crash ...](https://nvidia.github.io/physicsnemo/blog/2026/03/17/structural-mechanics/) - PhysicsNeMo blog

14. [GitHub - NVIDIA/physicsnemo: Open-source deep-learning ...](https://github.com/NVIDIA/physicsnemo) - Open-source deep-learning framework for building, training, and fine-tuning deep learning models usi...

15. [OpenRadioss is a powerful, industry-proven finite element ...](https://github.com/OpenRadioss/OpenRadioss) - OpenRadioss is a powerful, industry-proven finite element solver for dynamic event analysis - GitHub...

16. [GitHub - NVIDIA/physicsnemo](https://github.com/nvidia/physicsnemo) - PhysicsNeMo is an open-source PyTorch framework. It provides reusable library components and end-to-...

17. [Official source code of FreeCAD, a free and opensource ... - GitHub](https://github.com/freecad/freecad) - FreeCAD is an open-source parametric 3D modeler made primarily to design real-life objects of any si...

18. [Salome MESH (SMESH) module to create and edit mesh in ... - GitHub](https://github.com/SalomePlatform/smesh) - SALOME Mesh module implements the functionalities for: - Creating meshes in different ways: * By mes...

19. [GitHub - nschloe/pygmsh: :spider_web: Gmsh for Python](https://github.com/nschloe/pygmsh) - :spider_web: Gmsh for Python. Contribute to nschloe/pygmsh development by creating an account on Git...

20. [Vortex-Radioss - D3plot convertor and open-source Python post-processing library for OpenRadioss - now released · OpenRadioss · Discussion #2361](https://github.com/orgs/OpenRadioss/discussions/2361) - Vortex-Radioss We are pleased to be announcing a beta release of our open-source Python post-process...

21. [D3plot](https://open-lasso-python.github.io/lasso-python/dyna/D3plot/)

22. [lasso.dyna](https://open-lasso-python.github.io/lasso-python/dyna/)

23. [GitHub - meta-pytorch/botorch: Bayesian optimization in PyTorch](https://github.com/meta-pytorch/botorch) - BoTorch is a library for Bayesian Optimization built on PyTorch. BoTorch is currently in beta and un...

24. [facebookincubator/submitit: Python 3.8+ toolbox for submitting jobs ...](https://github.com/facebookincubator/submitit) - Submitit is a lightweight tool for submitting Python functions for computation within a Slurm cluste...

25. [GitHub - da-crivelli/freecad-parametric-fea: A flexible parametric FEA library based on FreeCAD](https://github.com/da-crivelli/freecad-parametric-fea) - A flexible parametric FEA library based on FreeCAD - da-crivelli/freecad-parametric-fea

26. [luminary-shift/SHIFT-Crash · Datasets at Hugging Face](https://huggingface.co/datasets/luminary-shift/SHIFT-Crash) - We’re on a journey to advance and democratize artificial intelligence through open source and open s...

27. [Overview | BoTorch](https://botorch.org/docs/overview) - This overview describes the basic components of BoTorch and how they work

