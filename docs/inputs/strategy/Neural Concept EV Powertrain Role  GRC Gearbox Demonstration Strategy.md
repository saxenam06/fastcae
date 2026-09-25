# Neural Concept EV Powertrain Role: GRC Gearbox Demonstration Strategy

## Executive answer

Neural Concept is not merely training a neural network to replace one CAE solve. Its product direction is a **geometry-aware engineering intelligence layer** above CAD, CAE, optimization, and enterprise data: engineering requirements define a legal design space; CAE generates training truth; geometric deep-learning surrogates predict fields and KPIs rapidly; optimization explores trade-offs; and copilots or agents coordinate the campaign while engineers retain review authority.[^1][^2][^3]

The Applied AI Engineer role is therefore a **vertical workflow builder**, not primarily a foundation-model researcher. The expected output is a reusable, customer-facing EV-powertrain workflow that embeds domain assumptions, connects tools and data, handles edge cases, validates predictions, and can move from prototype to a production-quality application. The current careers page also indicates that Neural Concept's technical hiring may include a coding challenge, home project, or technical interview, followed by an on-site assessment.[^4][^5][^6]

The strongest portfolio strategy is **not to abandon the GRC gearbox**. Build a deep GRC-based gearbox/EDU-housing workflow as the main demonstration, then add a smaller open-source electric-motor extension using Pyleecan/FEMM and optionally an OpenModelica vehicle-level context. GRC alone can prove geometry-to-mesh-to-CAE-to-surrogate-to-optimization-to-verification and robust workflow orchestration, but it cannot honestly prove complete EV powertrain expertise because it is a wind-turbine gearbox without an electric motor, inverter, traction duty cycle, or battery.

## What Neural Concept is solving

### Product-level problem

Traditional engineering AI projects often end as isolated surrogate notebooks. Neural Concept instead positions its platform between the application experience and the existing CAD/CAE/PLM stack, with capabilities for geometry-aware learning, physics prediction, design-space ranking, optimization, deployment, and enterprise control.[^3][^7][^1]

The company describes an engineer starting from requirements, defining or refining a design space, running optimization, reviewing Pareto trade-offs, and evolving the design space as new information appears. In the agentic motor example, Neural Concept supplies geometry, physics, optimization, and human-review interfaces, while NVIDIA NemoClaw supplies persistent, long-running orchestration across tools, documents, and sessions.[^2]

The commercial use case is therefore:

1. Translate an engineering decision into a formal workflow contract.
2. Generate or ingest valid design variants.
3. Automate CAE preparation and simulation.
4. Learn geometry-to-physics relationships from CAE data.
5. evaluate many designs fast enough for interactive decisions.
6. optimize multiple conflicting KPIs and constraints.
7. send selected candidates back to authoritative solvers.
8. package the capability as a reusable application rather than a research notebook.
9. capture failures, uncertainty, evidence, and human approvals so the workflow can be trusted and scaled.

### Concrete powertrain use cases

Neural Concept has publicly described a Bosch Research e-drive motor-housing application in which a geometric convolutional neural network emulated finite-element output in milliseconds and was then extended toward shape optimization. This is highly aligned with a gearbox or EDU housing workflow: the learned model consumes geometry or mesh information, predicts structural responses, supports rapid exploration, and leaves full FEA as the verification authority.[^8][^9]

Its more recent electric-motor workflow is broader. The company describes electromagnetics, thermal behavior, mechanical integrity, and NVH as coupled concerns and presents the workflow challenge as maintaining continuity from requirements through design exploration, optimization, and review rather than rebuilding brittle scripts for each project. A technically complete e-motor process normally includes CAD and meshing, electromagnetic fields and torque, thermal losses and temperatures, mechanical stresses, and vibration or acoustic responses.[^10][^11][^2]

Likely customer decisions include:

- **Motor geometry selection:** maximize torque and efficiency while constraining current, losses, demagnetization risk, temperature, stress, and noise.
- **Motor/EDU housing design:** reduce mass while controlling bearing/stator-interface compliance, modes, vibration response, cooling performance, and manufacturing constraints.
- **Gearbox/e-axle NVH:** identify critical operating orders, modify structural transfer paths, and reduce radiated noise across speed/load conditions.
- **Battery housing:** reduce mass while retaining structural performance; Neural Concept also describes using existing CAD and CAE data to predict battery-housing 3D fields and support verification.[^12][^13]
- **System-level EDU trade-offs:** connect component maps to duty-cycle energy, temperatures, performance, durability, and vehicle targets.

A published e-drive transmission process illustrates the engineering form of the gearbox use case: gear and shaft layout, housing stiffness and eigenfrequency assessment, flexible multibody and acoustic analysis over speed/load, root-cause analysis, housing optimization, and final re-verification. The Neural Concept value proposition is to make the repeated geometry-to-physics evaluations and handoffs dramatically faster and more reusable, not to eliminate domain modeling or high-fidelity validation.[^14]

## What the job actually tests

| Job expectation | Evidence a portfolio must show |
|---|---|
| Build EV-powertrain workflows | One executable application from requirement to verified design decision, not disconnected notebooks |
| Deep subsystem judgment | Correct interfaces, loads, operating points, KPIs, constraints, failure modes, and engineering sign-off criteria |
| Work with lead customers | A written discovery artifact: user persona, decision, current workflow, bottleneck, acceptance criteria, and value metric |
| Use foundation models and coding assistants | A documented AI-assisted build process plus an LLM workflow component with structured outputs, tool schemas, guardrails, tests, and measurable reliability |
| Strong Python/CAE scripting | Reproducible APIs or CLI commands for variant generation, meshing, solver execution, extraction, training, inference, optimization, and reporting |
| Collaborate across CAD/CAE/ML | Explicit interface contracts and versioned artifacts between geometry, mesh, solver, dataset, model, and application layers |
| Production-ready quality | Containerization, configuration management, experiment tracking, provenance, retries, observability, regression tests, and deployment instructions |
| Validate to engineering standards | Held-out design tests, solver re-runs, mesh convergence, load/boundary-condition reviews, uncertainty or out-of-domain checks, and documented release gates |
| Feed insights to roadmap | A section identifying platform gaps, reusable components, failure patterns, and the next highest-value workflow capabilities |
| Builder mindset | A working demonstration with an API/UI, recorded end-to-end run, technical report, and source repository |

The important interpretation is that **AI tooling in this job has two roles**. Geometric/physics ML supplies fast prediction and optimization; foundation models or LLM assistants accelerate implementation and handle bounded workflow reasoning. Using an LLM to write scripts is not enough—the delivered engineering workflow and its quality controls are the evidence.

## Comparison with the existing use case

The current project is an agentic, AI-native CAE workflow for the GRC gearbox housing: customer-like CAD ingestion, deterministic generation of legal variants, meshing and solver execution, surrogate training, rapid optimization, authoritative verification, and bounded agents for failure recovery and QA. Its geometry strategy preserves the original housing BREP, functional faces, bores, interfaces, and existing production ribs, while using controlled morph families for walls, shells, bulges, and related same-topology changes.

| Dimension | Neural Concept vertical workflow | Current GRC workflow | Assessment |
|---|---|---|---|
| Core value | Domain-specific application on an engineering-AI platform | Governed surrogate-assisted CAE and optimization system | Strong overlap |
| Geometry | CAD/mesh-aware learning and increasingly CAD-ready design copilots[^1][^15] | Existing BREP plus legal, semantics-preserving morphing | Strong and credible; less generative |
| Physics | Powertrain-specific multiphysics | Initially structural/modal/harmonic gearbox-housing response | Good depth, narrower domain coverage |
| ML | Geometry-aware field/KPI surrogate, deployment, optimization | PhysicsNeMo/PyTorch surrogate over legal variants | Strong overlap |
| Optimization | Pareto exploration with evolving design spaces[^2] | Differentiable or Bayesian surrogate optimization plus solver verification[^16][^17][^18] | Strong overlap |
| Agentic layer | Long-running coordination across requirements, tools, and reviews[^2] | Agents restricted to failed-run diagnosis, QA, escalation, and repair | Safer but narrower; present as deliberate governance |
| End user | OEM/Tier-1 engineer making a component or system decision | Gearbox analyst optimizing a real public housing | Strong industrial persona |
| Production layer | Enterprise deployment, sovereignty, reusable apps[^1][^7] | Currently prototype/product concept | Largest gap to close |
| EV relevance | Motor, gearbox, battery, and integrated EDU | Wind-turbine gearbox adapted as an e-transmission-housing analogue | Transferable but not literally EV |
| Validation | Customer standards, existing data, human review | NREL public geometry/test context plus solver truth | Valuable public benchmark, but not EV test correlation |

The differentiation should not be “a better Neural Concept.” The strongest framing is: **an open, auditable reference implementation of the same vertical-solution pattern, specialized in drivetrain structural/NVH workflows and governed CAE recovery**. The project’s distinctive ideas are semantic preservation of functional interfaces, legal morph spaces, solver-backed active learning, and explicit separation between deterministic engineering transformations and agentic exception handling.

## Can GRC satisfy the role?

### What it can prove

The GRC dataset was created around combined gearbox testing, modeling, and analysis, and the public GB3 record describes dynamometer tests intended to support interpretation of released data. Public GRC resources include engineering drawings, solid-body visualization models, and several categories of measured static, dynamic, thrust, torque-oscillation, misalignment, and field-condition data; the GB2 catalog explicitly marks those resources as public under Creative Commons Attribution.[^19][^20]

The drivetrain is a substantial industrial reference rather than a toy: it is a 750-kW, three-stage gearbox with one planetary stage and two parallel stages; published descriptions report an overall ratio near 81.49 and a floating sun, with the ring connected to the housing. This makes it well suited to demonstrating housing flexibility, bearing/ring-interface response, modal transfer paths, rotating or operating-condition load variation, and simulation/test provenance.[^21][^22][^23]

A GRC demonstration can cover:

- Public industrial CAD/drawing ingestion.
- Preservation and semantic tagging of bores, ring connection, bearings, mounts, split lines, and protected regions.
- Controlled wall, panel, boss, and existing-rib morph variables.
- Automatic tetrahedral or shell-solid meshing and mesh-quality gates.
- Static interface compliance, modal analysis, harmonic response, and an acoustic proxy or radiation stage.
- Geometry-aware field and KPI surrogate training.
- Multi-objective exploration and constrained optimization.
- Uncertainty or out-of-domain screening.
- High-fidelity solver verification and active learning.
- Agentic diagnosis of failed CAD/mesh/solver/post-processing jobs.
- Provenance, dashboards, reports, and a decision-oriented user experience.

Code_Aster is an open-source solver for mechanics, thermal analysis, and dynamics, and it supports modal and harmonic-response workflows including modal reduction. Gmsh supplies an open-source CAD/meshing engine with a Python API, while SALOME offers scripted CAD import, groups, 2D/3D meshing, and integration with Code_Aster. This is enough to construct a fully open structural workflow.[^24][^25][^26][^27][^28][^29]

### What it cannot prove honestly

GRC does not provide an EV traction motor, electromagnetic force harmonics, inverter switching, battery electrothermal behavior, or an automotive drive cycle. Its test evidence concerns a wind-turbine drivetrain, and its low-speed, high-torque operating envelope differs from an automotive e-axle.

Consequently, the portfolio must not claim:

- A validated EV gearbox or complete EDU model.
- Electromagnetic-to-structural e-motor NVH using GRC alone.
- Automotive efficiency or range optimization.
- Battery or inverter expertise.
- Direct compliance with an OEM release standard without corresponding requirements and test evidence.
- Fully autonomous engineering approval.

Instead, label the GRC case **“AI-assisted flexible housing optimization for an electrified-drivetrain analogue”** or **“transferable gearbox/EDU structural-NVH vertical workflow demonstrated on the public NREL GRC gearbox.”** Then explain which workflow contracts transfer unchanged to an e-axle and which loads, operating maps, materials, and validation evidence must be replaced.

## Recommended portfolio architecture

### Primary demonstration

**GRC Gearbox/EDU Housing Intelligence Workflow**

**User story:** A transmission/EDU CAE engineer must find lighter housing variants that preserve interfaces and manufacturing intent while reducing critical bearing/ring-seat motion and vibration response across multiple operating conditions.

**Decision outputs:**

- Pareto set for mass, interface compliance/misalignment, critical modal separation, and harmonic vibration or equivalent radiated power.
- Field predictions of displacement/stress and selected frequency-response quantities.
- Sensitivity and design-driver explanations.
- Model confidence and out-of-domain status.
- Verification evidence for selected candidates.
- Audit trail of geometry, mesh, solver, data, model, optimization, and human approvals.

The housing objective should remain consistent with the existing direction: find the stiffest/lightest legal housing under defined load cases, then extend to NVH-relevant dynamic targets rather than claiming direct minimization of gear-mesh load distribution before a sufficiently coupled drivetrain model exists.[^30]

### Motor extension

**Open-source Prius IPMSM Electromagnetic-Force-to-NVH Workflow**

Pyleecan is an Apache-2.0, Python-based framework for multiphysics design and optimization of electrical machines. It includes a Toyota Prius 2004 IPMSM definition that can be generated or modified through Python, and it connects to FEMM for nonlinear magnetostatic analysis. Its tutorials demonstrate operating-point sweeps and calculation of air-gap magnetic forces through the Maxwell stress tensor.[^31][^32][^33][^34][^35]

A compact but credible extension would:

1. Parameterize a bounded set of rotor/stator variables in the Prius machine.
2. Sweep speed/current-angle operating points.
3. Run FEMM through Pyleecan to obtain torque, flux density, losses where supported, and air-gap force harmonics.
4. Map selected force orders to a simplified but explicit stator-frame/housing structural model in Code_Aster.
5. Compute modes and harmonic responses, then an acoustic proxy such as equivalent radiated power.
6. Train a surrogate mapping motor geometry plus operating point to torque, ripple/force harmonics, losses, modal separation, and vibration proxy.
7. Optimize torque or efficiency-related performance against NVH and geometry constraints.
8. Verify Pareto candidates with the original FEMM and structural chain.

This mirrors the accepted scientific sequence for e-motor NVH: electromagnetic FEA produces force excitation, structural dynamics transforms it into vibration, and acoustic modeling estimates radiation. It also demonstrates the multi-tool continuity emphasized in Neural Concept's current agentic motor narrative.[^11][^36][^37][^2]

### System extension

**OpenModelica EV duty-cycle context**

EHPTlib contains component, subsystem, and full-vehicle models for electric and hybrid powertrains, including map-based electric drives, batteries, vehicle drag, and full-vehicle examples. Its example package includes basic and map-based EV models, while OpenModelica is an open-source Modelica simulation environment.[^38][^39][^40][^41]

Use this only as the outer context:

- Export the optimized motor/gearbox candidate as efficiency, torque-speed, mass, inertia, ratio, or loss-map parameters.
- Run a vehicle duty cycle.
- Report energy use, battery demand, acceleration/gradeability constraints, and thermal load proxies.
- Show how a component-level design decision propagates to vehicle-level value.

Do not make OpenModelica the main project. It proves system-level thinking, but by itself it does not demonstrate geometry-aware CAE AI.

## Model choice

| Option | Strength | Weakness | Recommendation |
|---|---|---|---|
| GRC housing only | Existing industrial CAD; strongest structural/gearbox story; public test context | Not EV; no electromagnetic or battery chain | Build as the deepest workflow |
| Pyleecan Prius motor | Direct EV relevance; Python; parameterized machine; FEMM and force extraction | Primarily 2D EM; structural/acoustic coupling must be built | Add as a focused second workflow |
| SyR-e motor | Mature open machine design, FEMM automation, and multi-objective optimization; supports several synchronous machine types[^42][^43] | MATLAB/Octave-centered and less aligned with a Python-first portfolio | Use only if Pyleecan blocks progress |
| OpenModelica EHPT | Full EV/powertrain context and duty cycles | No rich CAD-to-field surrogate by itself | Use as a thin system layer |
| Battery pack | Strong market relevance | Public geometry, material, coolant, and validation data are fragmented; open tools often use lumped thermal coupling[^44][^45] | Defer unless applying specifically to battery roles |
| EOMYS e-NVH benchmark | Public experimental benchmark for electromagnetic noise/vibration and multiphysics validation[^46] | Simplified benchmark rather than full production traction motor | Optional validation side-case |

If only one additional model is selected, choose **Pyleecan's Toyota Prius IPMSM**. If only one overall project can be finished to production quality, choose **GRC first** because the existing geometry work creates a much higher probability of a complete, polished delivery; incorporate motor-domain reasoning in the architecture and roadmap rather than leaving two half-finished demos.

## End-to-end GRC workflow

### Engineering contract

Represent the design request in a versioned schema rather than natural language alone:

```yaml
application: grc_flexible_housing
baseline_geometry: grc_gb3_housing.step
design_variables:
  - wall_panel_normal_offset
  - local_shell_bulge
  - existing_rib_height_scale
  - existing_rib_thickness_scale
protected_entities:
  - bearing_seats
  - ring_interface
  - trunnion_mounts
  - sealing_faces
  - bolt_holes
load_cases:
  - rated_torque_equivalent
  - non_torque_rotor_load
  - rotating_planet_or_bearing_load_phase
objectives:
  - minimize_mass
  - minimize_interface_motion
  - minimize_band_vibration_proxy
constraints:
  - stress_allowable
  - minimum_wall_thickness
  - minimum_modal_separation
  - geometry_and_mesh_quality
verification_policy:
  solver: code_aster
  require_high_fidelity_rerun: true
```

The LLM may convert a written brief into this schema, explain missing fields, and draft reports. Deterministic validators must reject invalid units, unknown entities, illegal ranges, inconsistent load cases, and unapproved model changes.

### Geometry and semantics

Operate directly on the existing BREP and retain the production ribs until sensitivity or topology evidence justifies a new rib family. Assign stable semantic groups for bearing seats, ring interface, trunnion mounts, split/sealing faces, bolt regions, protected clearances, morphable wall panels, and result-extraction regions.[^47]

Geometry generation should be deterministic and parameter driven. FreeCAD provides parametric modeling and a Python API, while Gmsh and SALOME can import CAD and expose scriptable geometry/mesh operations. For the first production-quality version, prefer a small set of robust same-topology morph modes over free-form generative CAD.[^27][^29][^48]

### Meshing and QA

The meshing service should:

- Apply local size controls at bores, fillets, ring connections, mounts, and rib intersections.
- Preserve named groups through meshing.
- Compute Jacobian, skewness, aspect ratio, minimum element size, disconnected-region, duplicate-node, and boundary-coverage checks.
- Compare mesh statistics and mass against expected ranges.
- Retry only approved meshing parameters.
- Escalate geometry or topology changes for human review.

Gmsh can be driven from Python and supports geometric entities and physical groups, making it suitable for automated solver-region tagging. SALOME's Python mesh interface supports geometry-based submeshes, local hypotheses, tetrahedral generation, and groups, and can export the resulting workflow as a reproducible script.[^49][^29][^27]

### Truth simulations

Use a staged fidelity ladder:

1. **Static screening:** interface displacement, bearing-seat relative motion/tilt, ring ovalization proxies, stress, and mass.
2. **Modal analysis:** natural frequencies, mode shapes, modal assurance checks, and participation at functional interfaces.
3. **Harmonic response:** critical force locations and order/frequency bands using modal reduction.
4. **Radiation proxy:** surface normal velocity or equivalent radiated power.
5. **Optional acoustic verification:** selected frequencies only, using an open acoustic workflow.

Code_Aster directly supports structural eigenmodes and harmonic response; modal projection can reduce the dynamic system before reconstructing physical responses. Published work has also chained Code_Aster vibration results into gearbox acoustic calculations using housing-surface vibration as the acoustic loading, demonstrating that the open stack is technically plausible even though the acoustic setup requires additional care.[^26][^50][^51][^24]

### Dataset contract

For every design and load case, store:

- Source CAD hash and geometry parameter vector.
- Semantic entity map and geometry validity report.
- Mesh, mesh settings, mesh metrics, and mesh hash.
- Materials, contacts/joins, boundary conditions, loads, solver version, and command file.
- Scalar KPIs and nodal/cell fields.
- Solver warnings, convergence status, runtime, and failure class.
- Train/validation/test split assignment.
- Parent design, campaign ID, and verification status.

Split the data by **design family or geometric distance**, not by randomly shuffling load cases from the same design across training and test. Otherwise, reported accuracy can be optimistic because nearly identical geometry appears in both sets.

### Surrogate ladder

Start with the lowest-risk model that supports the decision:

1. Scalar gradient-boosted or multilayer-perceptron baseline over explicit morph parameters and load descriptors.
2. Multi-task PyTorch model for mass, compliance, interface metrics, modal frequencies, and response-band KPIs.
3. Geometry-aware field model after the deterministic data pipeline is stable.
4. Ensemble or calibrated uncertainty layer for candidate screening.

PhysicsNeMo's MeshGraphNet converts a simulation mesh to a graph, uses node and edge features, and predicts node-level outputs through an encoder-processor-decoder architecture. X-MeshGraphNet can construct graphs from tessellated geometry and addresses scalability and simulation-mesh dependency, but this is an advanced option rather than a prerequisite for the first usable workflow.[^52][^53]

For GRC, reasonable graph inputs are coordinates, material and region labels, boundary/load encodings, surface normals where relevant, morph descriptors, and operating-condition parameters. Outputs can include displacement or stress fields plus pooled engineering KPIs. The platform must still compute mass exactly from geometry and should derive invariant engineering metrics through deterministic post-processing wherever possible.

### Optimization and verification

The online loop should optimize over bounded, legal design variables:

\[
\min_{z \in \mathcal{D}} \left[m(z),\; C_{interface}(z),\; V_{band}(z)\right]
\]

subject to stress, geometry, wall-thickness, interface, mesh-quality, modal-separation, and surrogate-confidence constraints.

Do not submit the single surrogate optimum as the answer. Use the surrogate to explore the space, return a diverse Pareto set and informative uncertain points, then run authoritative geometry, meshing, and FEA for verification. Add verified points to the dataset and retrain until improvement, uncertainty, and Pareto movement satisfy predefined stopping criteria.[^17][^18]

### Agentic recovery

Keep the safety boundary already chosen for the project: deterministic services own CAD, meshing, solving, extraction, training, and optimization; agents classify exceptions, select from an approved repair catalog, collect evidence, and request approval for model-changing actions.[^54]

A robust recovery design contains:

- **Failure classifier:** geometry import, lost semantic group, meshing, licensing/environment, solver singularity, non-convergence, post-processing, missing artifact, or ML pipeline failure.
- **Evidence bundle:** logs, stack trace, mesh metrics, last successful configuration, changed files, and solver diagnostics.
- **Approved repairs:** reduce/increase local element size within bounds, switch meshing algorithm, raise solver iterations, change linear solver, re-stage output extraction, or restart an interrupted task.
- **Prohibited autonomous changes:** material properties, physical constraints, loads, contact assumptions, geometry topology, or acceptance thresholds.
- **Evaluator:** rerun the failed stage, execute regression checks, compare outputs with the previous valid baseline, and either close or escalate the incident.

This is narrower than Neural Concept's broad long-running campaign narrative, but it is a defensible production design. Add a separate **campaign copilot** for requirements, design-space review, result explanation, and Pareto interrogation while retaining deterministic execution underneath.

## Twelve-to-sixteen-week plan

| Weeks | Deliverable | Exit criterion |
|---|---|---|
| 1–2 | Product brief and baseline replay | One command reproduces baseline CAD import, mesh, static solve, extraction, and report |
| 3–4 | Semantic geometry and legal variants | Protected interfaces remain invariant; all intended parameters generate valid candidates over a defined test matrix |
| 5–6 | Meshing/solver production pipeline | Containerized or reproducible execution, typed configs, provenance, QA gates, and failure taxonomy |
| 7–8 | Static/modal dataset campaign | Versioned dataset with deterministic reruns, family-aware split, and data-quality dashboard |
| 9–10 | Baselines and geometry-aware surrogate | Scalar baseline plus field model; held-out errors, failure cases, calibration, and inference API documented |
| 11–12 | Optimization and active verification | Pareto exploration, uncertainty filtering, solver verification, and one retraining cycle operate automatically |
| 13–14 | Agentic recovery and application | Injected failures are diagnosed; only approved repairs execute; UI shows campaign, designs, fields, Pareto set, and evidence |
| 15–16 | Motor or system extension and portfolio packaging | Pyleecan motor mini-workflow or OpenModelica propagation runs; final video, architecture, tests, report, and roadmap are complete |

If the motor extension threatens the quality of the core workflow, defer it and provide a tested adapter interface plus one Pyleecan-to-dataset proof run. A polished vertical workflow is more persuasive than three incomplete subsystem demos.

## Production acceptance criteria

### Engineering validity

- Baseline results are independently reviewed and reproduced.
- Mesh refinement changes priority KPIs by less than a declared tolerance.
- Boundary conditions and loads are traceable to a source or clearly marked assumptions.
- Protected interfaces remain within geometric invariance tolerances.
- All optimized candidates pass exact geometry, mesh, and solver verification.
- Dynamic KPIs use declared damping and frequency/order assumptions.
- Wind-turbine-to-EV transfer limitations are visible in the UI and report.

### ML validity

- Test designs are geometrically distinct from training designs.
- Metrics include normalized and physical-unit errors, worst cases, field maps, and engineering pass/fail agreement.
- Uncertainty or distance-to-training-data is exposed for every inference.
- Out-of-domain cases are refused or routed to FEA.
- Model, normalizers, feature schema, dataset, and code versions are linked.
- The optimizer cannot bypass confidence or hard engineering constraints.

### Software validity

- Typed configuration and schema validation.
- Idempotent stages and resumable campaigns.
- Artifact and model registry.
- Structured logs, traces, runtime and failure dashboards.
- Unit, integration, regression, and injected-failure tests.
- Container or reproducible environment.
- API plus a small decision-oriented UI.
- Security model for uploaded CAD and customer data.

### Agent validity

- A golden set of known failures and expected classifications.
- Measured repair success, false-repair, escalation, latency, and token/cost behavior.
- Structured tool calls rather than shell access by default.
- Full action log and reversible changes.
- Mandatory human approval for physics-model modifications.

## Portfolio narrative

A concise title is:

> **AI-Assisted Gearbox/EDU Housing Design: Geometry-Aware CAE Surrogates, Verified Optimization, and Governed Workflow Recovery**

The interview pitch should be:

> A public NREL gearbox was turned into a production-style vertical engineering workflow. The system preserves functional CAD interfaces, generates legal housing variants, meshes and solves them with an open CAE stack, learns geometry-to-field and geometry-to-KPI surrogates, explores mass–stiffness–NVH trade-offs, and returns only solver-verified candidates. Deterministic services own physics transformations; an LLM copilot structures requirements and explains trade-offs, while a governed recovery agent diagnoses and repairs approved workflow failures. A Pyleecan/FEMM adapter demonstrates how the same contracts extend to EV motor electromagnetic-force and NVH workflows.

The portfolio should include:

- A two-minute end-user video beginning with an engineering requirement and ending with verified candidates.
- A longer technical walkthrough of geometry semantics, mesh/solver contracts, dataset, ML validation, optimization, and agents.
- A repository with a fast reduced example and instructions for the full model.
- An architecture decision record explaining why agents do not own CAD or physics assumptions.
- A customer-discovery brief and quantified workflow baseline.
- A model card, dataset card, failure runbook, and validation report.
- A roadmap showing motor, battery, full EDU, PLM, private-cloud, and customer-data extensions.

## Highest-priority recommendation

Continue with GRC, but change the goal from “train a PhysicsNeMo model on a gearbox” to **“ship a complete gearbox/EDU vertical solution.”** The neural surrogate is one service inside that solution. The differentiator is the complete decision loop: requirements, legal geometry, meshing, solver truth, geometry-aware ML, uncertainty-aware optimization, verification, recovery, and traceable human review.

Add the Pyleecan Prius case only far enough to prove EV-specific transfer: electromagnetic operating points, Maxwell-force extraction, a structural transfer step, and multiobjective inference. Pyleecan already provides the parameterized Prius machine, FEMM connection, operating-point sweeps, and force calculation needed to avoid building the motor front end from scratch. OpenModelica EHPT can then show how selected component maps affect a drive cycle, but it should remain a supporting system-level demonstration.[^32][^39][^41][^34][^35][^31][^38]

The resulting portfolio directly covers the role's central combination: powertrain domain judgment, Python/CAE integration, geometric ML, LLM-enabled workflow construction, validation discipline, and the ability to carry a customer problem from ambiguous requirement to production-oriented engineering application.

---

## References

1. [The engineering platform to scale AI-first design](https://www.neuralconcept.com/platform) - Neural Concept empowers engineering teams to build, use and deploy domain-specific AI assistants

2. [Agentic AI Engineering: Neural Concept and NVIDIA ...](https://www.neuralconcept.com/post/agentic-ai-engineering-neural-concept-and-nvidia-nemoclaw-in-practice) - Engineering teams already use AI in many forms. What is missing is the possibility to connect entire...

3. [AI in Mechanical Engineering - How Is It Used? - Neural Concept](https://www.neuralconcept.com/post/how-is-ai-used-in-mechanical-engineering) - Mechanical engineers use AI to explore larger design spaces within the schedule and bring engineerin...

4. [EV Powertrain: Applied AI Engineer @ Neural Concept - Jobs](https://jobs.ashbyhq.com/neuralconcept/aa1301d4-ab37-46f5-bdb8-c59eb97a5547) - We're hiring an Applied AI Engineer to help transform how EV powertrains get designed — turning deep...

5. [Neural Concept - Jobs](https://jobs.ashbyhq.com/neuralconcept) - Neural Concept Jobs

6. [Join Us | Neural Concept](https://www.neuralconcept.com/careers) - AI Workflows Engineer. Vertical Solutions • Lausanne; Cambridge • Full time • Hybrid · EV Powertrain...

7. [Neural Concept to offer best in-class engineering AI using ...](https://www.neuralconcept.com/post/neural-concept-to-offer-best-in-class-engineering-ai-using-nvidia-accelerated-computing)

8. [E-Drive Housing Designs Optimized using Neural Concept Shape | Neural Concept](https://www.neuralconcept.com/post/e-drive-housing-designs-optimized-using-neural-concept-shape) - Neural Concept and Bosch Research collaborated over the past months on a set of successful applicati...

9. [AI in Engineering: Applications, Key Benefits, and Future ...](https://www.neuralconcept.com/post/what-is-artificial-intelligence-engineering) - The article shows how AI is transforming engineering by enabling teams to analyze, predict, and opti...

10. [Electric Motor Simulation: Powerful Tool for Design Optimization](https://www.neuralconcept.com/post/electric-motor-simulation-powerful-tool-for-design-optimization) - In this article, we will review design requirements for electric motor design and explore finite ele...

11. [NVH optimization of electric motors: optimization under constraints and uncertainty](https://hal.science/hal-04165662/document)

12. [AI Simulation for Engineering: Smarter Modeling and Better Insights](https://www.neuralconcept.com/post/ai-simulation-for-engineering-smarter-modeling-and-better-insights) - Explore how AI simulation enhances decision-making in engineering, improving efficiency and outcomes...

13. [Mubea using Neural Concept for the Design of Innovative ...](https://www.neuralconcept.com/post/mubea-using-shape-for-the-design-of-innovative-lightweight-components) - Mubea is an international partner to the automotive industry and an innovative lightweight specialis...

14. [2020-01-1578: Root Cause Analysis and Structural Optimization of E-Drive Transmission - Technical Paper](https://saemobilus.sae.org/papers/root-cause-analysis-structural-optimization-e-drive-transmission-2020-01-1578) - This paper describes the simulation tool chain serving to design and optimize the transmission of an...

15. [and Geometry-Aware AI Design Copilot, Extending Its ...](https://www.neuralconcept.com/press-release/neural-concept-ai-design-copilot) - Neural Concept today announced the launch of its ground-breaking AI Design Copilot, the first to com...

16. [My idea is to do the optimisation using surrogate](https://www.perplexity.ai/search/258caaea-9b44-4f2f-ad83-c99a46a7a0a8) - Yes—then the project should be shaped around surrogate-based design optimization, not around repeate...

17. [And how the surrogate used can be used for optimisation since the model is differentiable. Let’s say we set an objective then how can we come up with optimal design vector ,?? Possible](https://www.perplexity.ai/search/133ecd39-4de7-4645-81d0-2629db23f3da) - Yes—this is possible. Once you train a differentiable surrogate \( \hat{f}_\theta \) that maps your ...

18. [but then when the surrogate applies Evaluate 10,000 candidate geometries during early architecture trade studies , Evaluate many geometry × carrier-angle × load-imbalance combinations... etc then when we wantt to use the surrogate during runtime then its more looku o of the best design and then optimize on the best design.. ? or??](https://www.perplexity.ai/search/2f9533ce-c205-4eb9-8b68-7d4bd5b1d1cd) - Yes—but separate “search” from “final optimization.” The surrogate’s runtime role is usually to expl...

19. [Gearbox Reliability Collaborative Phase 3 Gearbox 3 Test](https://data.nlr.gov/submissions/56)

20. [Gearbox Reliability Collaborative Phase 3 Gearbox 2 Test - Catalog](https://catalog.data.gov/dataset/gearbox-reliability-collaborative-phase-3-gearbox-2-test-41b97) - The National Renewable Energy Laboratory (NREL) Gearbox Reliability Collaborative (GRC) was establis...

21. [34   JUNE   |   2013](https://www.windsystemsmag.com/wp-content/uploads/pdfs/Articles/2013_June/0613_NREL.pdf)

22. [RESEARCH ARTICLE](https://docs.wind-watch.org/guo2014.pdf)

23. [Wind Turbine Drivetrain Condition Monitoring During GRC ...](https://docs.nrel.gov/docs/fy12osti/52748.pdf)

24. [12.1. R4.06.02 : Modal computation by classic dynamic substructuring](https://biba1632.gitlab.io/code-aster-manuals/docs/reference/r4.06.02.html) - The method of calculation of harmonic response by modal synthesis available in Code_Aster is based o...

25. [Home | code_aster](https://code-aster.org/en) - Welcome to our website

26. [Titre de la présentation](https://community.code-aster.org/IMG/pdf/02-transient-harmonic.pdf)

27. [Gmsh: a three-dimensional finite element mesh generator with built ...](https://gmsh.info/) - Gmsh is an open source 3D finite element mesh generator with a built-in CAD engine and post-processo...

28. [SalomePlatform](https://github.com/SalomePlatform) - SalomePlatform has 51 repositories available. Follow their code on GitHub.

29. [Python interface¶](https://docs.salome-platform.org/latest/gui/SMESH/smeshpy_interface.html)

30. [so what happens during runtime.. how this surrogate is ued](https://www.perplexity.ai/search/142bf7f8-0edc-4eec-b611-9830609f76b7) - At runtime, the surrogate replaces repeated housing FE solves inside the optimization loop. It does ...

31. [PYthon Library for Electrical Engineering Computational ANalysis](https://pyleecan.org/01_tuto_Machine.html)

32. [Eomys/pyleecan: Electrical engineering open-source ...](https://github.com/Eomys/pyleecan) - Electrical engineering open-source software providing a user-friendly, unified, flexible simulation ...

33. [PYLEECAN — PYthon Library for Electrical Engineering ...](https://www.pyleecan.org/)

34. [Version information](https://pyleecan.org/06_tuto_Force.html)

35. [How to set the Operating Point - PYLEECAN](https://pyleecan.org/04_tuto_Operating_point.html)

36. [Multiphysics Modeling and Simulation of NVH Phenomena in ... - MDPI](https://www.mdpi.com/2032-6653/17/4/183) - This review adopts a source-to-perception perspective and consolidates the principal physical mechan...

37. [C:/Fabio/IEEE Journal/Final Submission/LaTeX_13-0595-TIE/LaTeX_13-0595-TIE.dvi](https://dipot.ulb.ac.be/dspace/bitstream/2013/152333/1/2014_dosSantos_multiphysics_NVH_Modeling_SRM_EV_8p_PP.pdf)

38. [EHPTlib - build - OpenModelica](https://build.openmodelica.org/Documentation/EHPTlib.html)

39. [PDF A new Modelica Electric and Hybrid Power Trains library](https://2015.international.conference.modelica.org/proceedings/html/submissions/ecp15118785_Ceraolo.pdf)

40. [Introduction](https://openmodelica.org/)

41. [EHPTexamples.EV - build - OpenModelica](https://build.openmodelica.org/Documentation/EHPTexamples.EV.html)

42. [GitHub - SyR-e/syre_public: SyR-e is an open-source platform to ...](https://github.com/SyR-e/syre_public) - SyR-e is an open-source platform to design, simulate and evaluate electrical machines and drives - S...

43. [syre download | SourceForge.net](https://sourceforge.net/projects/syr-e/) - SyR-e is a Matlab/Octave package developed to design, evaluate and optimize synchronous reluctance a...

44. [[PDF] A Python package for simulating packs of batteries with PyBaMM](https://www.theoj.org/joss-papers/joss.04051/10.21105.joss.04051.pdf)

45. [Lithium-Ion Pxd Simulations](https://www.sintef.no/en/software/battmo/) - BattMo is an open source simulation code for continuum modelling of electrochemical devices written ...

46. [2019_SAE_Full_Manuscript_Final_RG](https://e-nvh.eomys.com/wp-content/uploads/2019/08/pdf_2019_sae_full_manuscript_final_rg.pdf)

47. [where this approach has advantages as compared to topology optimization.. and how a surrogate model trained on the data created from these design variants could be better than topology optimixation](https://www.perplexity.ai/search/f1ca651c-c8ea-493e-925a-fb5dc61558b7) - Your mesh-morphing-plus-surrogate approach has a major advantage over topology optimization when the...

48. [GitHub - J-Dunn/FreeCAD: This is the official source code of FreeCAD, a free and opensource multiplatform 3D parametric modeler.](https://github.com/J-Dunn/FreeCAD) - This is the official source code of FreeCAD, a free and opensource multiplatform 3D parametric model...

49. [Fossies Dox](https://fossies.org/dox/gmsh-4.15.0-source/t1_8py_source.html)

50. [Comparison of finite-element methods to compute the transmission error to noise transfer function of a simple gear box.](https://past.isma-isaac.be/downloads/isma2018/proceedings/Contribution_272_proceeding_3.pdf)

51. [3.1. [U1.03.00]: Main principles of Code_Aster¶](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u1.03.00.html)

52. [MeshGraphNet: A Practical User Tutorial - NVIDIA Documentation](https://docs.nvidia.com/physicsnemo/latest/user-guide/model_architecture/meshgraphnet.html) - This guide is designed to help you understand the core architecture of this powerful Graph Neural Ne...

53. [Graph Neural Networks - PhysicsNeMo - NVIDIA Documentation](https://docs.nvidia.com/physicsnemo/latest/physicsnemo/api/models/gnns.html) - MeshGraphNet with Lagrangian mesh · Learning the flow field of Stokes ... Reference: Learning Mesh-B...

54. [faster with meshing requried + parameterizabel design variants+ physicsnemo +a agentic ai](https://www.perplexity.ai/search/f4b0ac30-9138-4047-aac0-faa0235a771b) - Yes. The best final concept is:

A GB3-inspired reduced gearbox housing with real automated meshing,...

