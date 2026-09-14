# How variants are generated, and how combinations are kept feasible

How industry, vendors and research generate design variants, how each keeps a *combination* of
features feasible - a rib pattern and a hole pattern that must not interfere - and how vendors get
training data. September 2026.

## What "geometry AI" means

Models trained on many past designs that do two things:
1. **Predict** simulation results for a new shape in seconds - the surrogate: Neural Concept, Ansys
   SimAI, Siemens PhysicsAI.
2. **Invent** new shapes in the style of their training designs - since 2026: Ansys GeomAI, Siemens
   PhysicsAI Generate, the Neural Concept AI Design Copilot.

## The bottom line

No CAD/CAE vendor, as of September 2026, uses constraint programming, SAT or MILP to pick a feasible
subset of geometric features. Vendors sidestep the problem in five ways:
- **Freeze topology:** mesh morphing, or rib sizing only after topology optimisation.
- **Discard or penalise:** optimiser wrappers mark failed designs and move on.
- **Guarantee valid geometry only:** nTop's implicit modelling.
- **Check rules afterwards:** knowledge-based and DFM rule checkers.
- **Learn plausibility from data:** GeomAI, PhysicsAI Generate, Neural Concept's copilot - none
  publishes validity rates.

The mathematics is classical: independent sets on a conflict graph, SAT-based product configuration,
EDA placement legalisation, Dessia's logic programming. Applying it to casting-feature variants of a
plain STEP part, feeding FE and optimisation, looks genuinely distinctive. A team could approximate it
on nTop with scripting and sample-and-reject, but no vendor ships it as a feature.

## Every way of iterating on geometry, and fastcae

fastcae does not look for one best shape, and it is not a CAD modeller. It takes a plain STEP of an
existing casting and generates thousands of variants that obey every rule encoded, then meshes and
solves them. The other approaches start from scratch, work inside a fixed shape, or learn from past
designs.

| Approach | How variants are made | Can ribs and holes appear or disappear? | How feasibility is handled | Starts from | What comes out |
|---|---|---|---|---|---|
| Parametric CAD - SolidWorks, Onshape, Inventor and Fusion, NX, CATIA (AutoCAD is mostly 2D) | parameters in the feature tree changed by hand, or swept by a DOE tool (HEEDS, optiSLang) | only features modelled beforehand and switched off | the rebuild succeeds or fails - nTop says 70-80 % of automated sweeps fail; manufacturing rules checked afterwards, if at all | a clean parametric model - a legacy STEP has no tree | editable CAD |
| Morphing - ANSA, HyperMorph, RBF Morph, PyGeM | control points push a baseline mesh | no: shapes stretch, features stay | mesh quality only | one baseline mesh | a morphed mesh |
| Shape optimisation - OptiStruct, Tosca, adjoint solvers | one design's surface moved along its sensitivities | no | some constraints - least thickness, draw direction | a good starting design and its loads | one improved design |
| Topology optimisation - OptiStruct, Ansys, Fusion | material laid out from the loads | yes | draw direction and least member size available; the result is a density field, redrawn by hand | a design space and its loads | a handful of organic shapes per setup |
| Generative design - Fusion, nTop | topology-optimisation-style options with manufacturing presets | yes | presets - draft, parting line, least wall; the shapes still need cleaning up | loads and keep-outs | new organic shapes, not variants of an existing part |
| Learned generators - Ansys GeomAI, Siemens PhysicsAI Generate, Neural Concept's Copilot | a model trained on past designs | yes | imitates the style of past designs; rules not checked - 6-69 % validity in independent tests | many past designs | plausible shapes, not guaranteed |
| Implicit modelling - nTop | field-based workflows; ribs from 2D pattern graphs | yes | the geometry never breaks - 2,400 variants, no failures; clash logic hand-built in each workflow, no solver for combinations | a workflow the engineer builds per part | geometry and meshes |
| **fastcae** | **variants - each one change in one place - placed by rules, repaired by CP-SAT, built as a distance field** | **yes: which ribs, pads and holes exist is part of the design space** | **every design obeys every encoded rule, each piece left out says why, nothing to heal - no rib has ever crossed a hole** | **a plain STEP and its drawing** | **field, mesh, labels and solved results** |

## Parametric CAD with optimiser wrappers

HEEDS, optiSLang, modeFRONTIER, Isight/Process Composer. Feasibility comes from sketch constraints,
parameter bounds and inequalities, discarding failures, and penalties.
- **optiSLang:** a CAD crash "marks it as failed, continues the study, and still builds surfaces from
  the successful points" ([EDRMedeso, August 2025](https://edrmedeso.com/article/optislang-explained-from-one-off-simulations-to-automated-data-driven-product-optimisation/)).
- **HEEDS:** tracks feasible and infeasible designs and "skips simulations with errors"
  ([ATA/Siemens seminar](https://www.ata-e.com/wp-content/uploads/2024/11/ATA_HEEDS-Simcenter3D-Seminar_2020-12-02.pdf)).
  Its AI Simulation Predictor has a "Constraint Confidence" setting that lets predictions replace runs:
  in one test 193 of 500 designs were predicted rather than simulated, saving 22% of the time
  ([Volupe, December 2023](https://volupe.com/simcenter-heeds/revolutionizing-optimization-studies-heeds-introduces-cutting-edge-ai-technology/));
  HEEDS 2510 claims up to 30% ([Siemens, November 2025](https://blogs.sw.siemens.com/simcenter/whats-new-in-simcenter-heeds-2510/)).
- **modeFRONTIER/VOLTA** flags designs that break input constraints before running them
  ([ESTECO 2022R3](https://www.esteco.com/news/volta-and-modefrontier-2022-r-3-available-now/)).
- **Measured waste:** a SolidWorks Design Study dataset dropped about 66% of sampled designs on
  feasibility checks, and 394 more failed to build ([Oct 2023](https://arxiv.org/abs/2310.18772));
  DTU/Novo Nordisk found sketch robustness "low even with a small amount of variation (±1%)"
  ([CAD Journal 2023](https://www.cad-journal.net/files/vol_20/CAD_20%281%29_2023_56-81.pdf)).
- **Casting practice:** the BMW/Altair mega-casting study ([Sci. Rep., December 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC10709356/))
  ran topology optimisation first, then froze the rib topology; it then used about 20 thickness and
  orientation variables, HyperStudy response surfaces, ML classifiers for failure modes and 150-600
  samples per study, saving 25 kg. Which ribs exist was decided once, by hand.

## Mesh morphing

ANSA (Cadence since the [2024 deal](https://www.cadence.com/en_US/home/company/newsroom/press-releases/pr/2024/cadence-to-acquire-beta-cae-expanding-into-structural-analysis.html)),
HyperMorph (now Siemens), Sculptor. Topology is fixed: nodes move, but ribs and holes are never added
or removed; failure means distorted elements. ANSA 2025.2 adds "fully parameterizable features,
ready-to-be-used in optimization loops" ([December 2025](https://www.beta-cae.com/news/20251223_announcement_suite_2025.2.htm)).
There is still no solver for combinations.

## Implicit modelling (nTop)

Geometry does not fail: nTop and CoreWeave ran 2,400 planform variants at 5 angles of attack on 280
GPUs with "no geometry failures, no manual restarts" ([nTop, April 2026](https://www.ntop.com/resources/blog/ntop-coreweave-nasa-2030-grand-challenge-in-cfd/);
[CoreWeave](https://coreweave.com/blog/10000-les-simulations-in-32-hours-ntop-and-coreweave-hit-nasas-cfd-2030-target):
10,000 LES runs in 32 h). Rib Design (nTop 5.10, early 2025) projects 2D pattern graphs onto a surface
and extrudes them into ribs, adds draft, blends where ribs intersect, and lets fields drive
orientation, thickness and fillets ([guide](https://support.ntop.com/hc/en-us/articles/35117560848275-Guide-to-Rib-Design),
[5.10](https://support.ntop.com/hc/en-us/articles/35301241302163-nTop-5-10-What-s-New)); 5.34 adds
[Parameter Optimization](https://support.ntop.com/hc/en-us/articles/46104666157331-nTop-5-34-What-s-New).
No rule-based removal of conflicting ribs was found: conflicts are resolved geometrically, by Booleans
and blends, which keeps the solid valid but guarantees neither sand gaps nor hole ligaments (a reading
from search snippets - nTop's support pages refused fetching). Intact.Simulation with nTop and Bayesian
optimisation: a ribbed panel with 4 parameters, 300 trials, about 12 h
([December 2025](https://intact-solutions.com/ai-guided-design-exploration-with-intact-simulation-for-ntop/)).

## Feature scripts and rule engines

- **Onshape FeatureScript:** [configurable](https://www.onshape.com/en/features/configurations) custom
  features; each instance regenerates or errors; no solver for combinations.
- **Synera AutoRib** ([May 2026](https://www.synera.ai/news/how-autorib-and-syneras-ai-agents-automate-structural-rib-design)):
  a rib network from a principal-stress map, profiles for moulding feasibility, callable by agents; no
  conflict handling disclosed.
- **Post-hoc checkers:** CATIA [Knowledge Expert](https://3dswym.3dexperience.3ds.com/wiki/catia-user-community/catia-knowledge-expert-2-kwe_tgqmO4ZmTgSzwoTX9Za9cA)
  shows green or red; [DFMPro](https://dfmpro.com/cad-systems/dfmpro-for-catia/) has 300+ rules.
- **OptiStruct [topography](https://help.altair.com/hwsolvers/os/topics/solvers/os/topography_opt_intro_c.htm):**
  beads with a minimum width and draw angle; continuous and filter-based.
- **Fusion generative design** puts [manufacturing constraints](https://www.autodesk.com/solutions/generative-design/manufacturing)
  inside the solver (draft, parting line, minimum wall for die casting); it makes new shapes, not
  variants of an existing part.
- **Dessia** ([October 2025](https://www.dessia.io/blog/inside-dessias-ai-libraries-design-engineering-logic-meets-machine-intelligence))
  formalises rules "into constraint networks and logic graphs" with "Symbolic Reasoning and Logic
  Programming, for rule enforcement, constraint solving"; its variants are valid by construction, but
  it targets routing and architecture - the closest analogue to fastcae's approach.

## Learned geometry

- **Ansys GeomAI** (2026 R1, 11 March 2026) learns a latent space from reference geometries the user
  supplies; optiSLang optimises across it ([Synopsys](https://ansys.synopsys.com/blog/introducing-ansys-geomai-software)).
- **Simcenter PhysicsAI Generate** is a diffusion model trained on "historical designs you already
  have"; experimental in HyperMesh 2026.0/2026.1, generally available in 2612
  ([blog, June 2026](https://blogs.sw.siemens.com/simcenter/generative-ai-engineering-design/);
  [release, July 2026](https://news.siemens.com/en-us/siemens-simcenter-summer-2026/)).
- **Neural Concept AI Design Copilot** ([7 January 2026](https://www.neuralconcept.com/post/neural-concept-introduces-a-physics--and-geometry-aware-ai-design-copilot-extending-its-established-engineering-ai-platform))
  claims "manufacturing-ready" geometry, with no validity data.
- **PhysicsX LGM-Aero** ([December 2024](https://www.physicsx.ai/newsroom/building-beyond-human-imagination-with-foundation-models-for-geometry-and-physics))
  adds geometric-consistency losses as priors on the latent space and takes gradient steps in the
  latent code "to obey constraints".
- **Autodesk** announced [neural CAD at AU 2025](https://www.engineering.com/autodesk-introduces-neural-cad-at-au-2025/).

Independent evidence that learned plausibility is not a guarantee: a GAN trained on 30 K valid ship
hulls produced valid hulls 6% of the time ([Regenwetter et al., rev. December 2024](https://arxiv.org/abs/2306.15166));
the best text-to-CAD model reached 68.9% geometric validity and about 50-55% on manufacturability
([MUSE, 2026](https://arxiv.org/abs/2605.28579)).

## Research

- Rib layout is called "a combinatorial, knowledge-intensive design task", yet the newest method uses
  density-based topology optimisation with a diffusion prior, feasibility "assessed downstream"
  ([Kwon & Kang, September 2026](https://arxiv.org/abs/2609.10643)); stiffener ground-structure methods
  penalise intermediate thicknesses ([C&S 2024](https://www.sciencedirect.com/science/article/abs/pii/S0045794924003626)).
- Solver-guaranteed generation exists elsewhere: GenCO (ICML 2024) routes generative models through
  combinatorial solvers so outputs "verifiably adhere" ([arXiv](https://arxiv.org/abs/2310.02442));
  NN+MILP for constrained discrete black-box optimisation ([ICML 2022](https://proceedings.mlr.press/v162/papalexopoulos22a/papalexopoulos22a.pdf));
  CP-SAT builds layouts from sketches with 95.5% success ([Sketch-to-Layout, 2026](https://arxiv.org/abs/2606.09849));
  mixed-integer truss topology ([Kanno](https://link.springer.com/article/10.1007/s10589-015-9766-0)).
- The same pattern in other industries: SAT for Mercedes product configuration
  ([Sinz et al.](https://www.academia.edu/109954745/Detection_of_Inconsistencies_in_Complex_Product_Configuration_Data_Using_Extended_Propositional_SAT_Checking)),
  feature models with more than 10,000 cross-tree constraints ([EMSE 2022](https://link.springer.com/article/10.1007/s10664-022-10265-9));
  map labelling as a maximum independent set on a conflict graph ([Agarwal et al. 1998](https://www.wikidata.org/wiki/Q29037138));
  PCB and VLSI placement legalised against clearance rules ([DAC 2024](https://dl.acm.org/doi/10.1145/3649329.3663495),
  [SMT floorplanning](https://arxiv.org/abs/1709.07241)).

## The training-data problem

| Source | Data needed or used |
|---|---|
| [Ansys SimAI](https://www.ansys.com/en-gb/products/ai/simai) | "typically 30 to 100 simulation results"; each result carries a confidence flag when the design is "too far away from the training data"; a structural bracket example used about 250 samples generated through Discovery and optiSLang ([blog](https://www.ansys.com/blog/chips-ships-optimize-design-ansys-simai-platform)) |
| [Neural Concept guide](https://www.neuralconcept.com/post/3d-convolutional-neural-network-a-guide-for-engineers) | "a few dozen to several thousand simulation cases"; "a few hundred well-distributed" cases beat thousands of redundant ones; DrivAerNet++ (8,000 cars, 39 TB) trained end to end within a week ([September 2025](https://www.neuralconcept.com/post/neural-concept-sets-record-aerodynamics-benchmark-with-its-enterprise-ready-ai-platform)) |
| Siemens | [PhysicsAI](https://news.siemens.com/en-us/siemens-simcenter-physicsai/) (27 May 2026) trains on "historical data … including previous Design of Experiments (DOE) studies", high-fidelity CFD as "the validation reference"; Altair [physicsAI](https://altair.com/physicsai) learns from past simulations without a design of experiments |
| PhysicsX | pretrained on 25 M shapes plus tens of thousands of CFD/FEA runs from Siemens solvers ([December 2024](https://news.siemens.com/en-us/siemens-physicsx/)) - 128 H100s for 4 weeks, then 64 A100s for 4 weeks; claims benefit "without the need for extensive fine-tuning"; a [forward-deployed delivery team](https://www.physicsx.ai/newsroom/simulation-engineering-at-physicsx-the-bridge-between-physics-and-ai) builds the models; a [$300M Series C](https://www.physicsx.ai/newsroom/physicsx-announces-300m-series-c-to-accelerate-physics-ai-for-industrial-engineering) (8 June 2026) funds "Large Physics Models" |
| [Luminary SHIFT](https://luminary.ai/resources/introducing-luminary-shift-models-a-suite-of-physics-ai-foundation-models-to-transform-engineering-design/) | pretrained models and datasets, fine-tuned "on a smaller set of custom data" |
| Compute partnerships | nTop and CoreWeave (above), the dataset itself pitched as the surrogate's foundation; nTop and Luminary ran 200 configurations as 3,400 CFD runs in under 6 h ([August 2025](https://www.ntop.com/resources/blog/designing-a-automation-pipeline-for-high-fidelity-design-space-exploration/)) |
| [Monolith](https://www.monolithai.com/blog/what-is-active-learning) | active learning claims up to 70% fewer tests |

A one-off casting has no simulation archive to reuse. The vendors' own numbers suggest about 30-100 FE
solves for a surrogate on scalar metrics, and hundreds for one that predicts full stress fields. From an
OEM's third programme, transfer learning cuts new simulations to under 300 ([market.md](market.md)).

## Where fastcae stands

**Meaningful: yes.** No vendor offers it; the mathematics is not new, the application is.

What is distinctive:
1. Every design sent to FE meets every encoded pairwise casting rule - against about 66% discarded
   plus build failures with parametric CAD, or 6-69% validity for learned generators.
2. The design space includes which ribs and holes exist - neither morphing nor sizing after topology
   optimisation (the BMW approach) can express that.
3. It works on a non-parametric STEP file with no feature history.
4. Each piece left out comes with the rule it broke.

What is not distinctive: generating ribs (nTop, Synera, OptiStruct), robust geometry (nTop),
surrogate optimisation (everyone), rule checking (DFMPro, Knowledge Expert), the mathematics
(independent sets, SAT, Dessia).

### What it gives

- **Starts from a plain STEP.** No feature tree, and no parametric model built by hand - what the
  delivery teams build per customer ([data-factories.md](data-factories.md)).
- **Topology is part of the design space.** Ribs, pads and holes appear, disappear and combine;
  morphing and shape optimisation cannot do that.
- **Valid by construction, at scale.** Placing and screening a design takes tens of milliseconds; every
  design comes back from its seed and recipe hash; nothing fails to rebuild silently.
- **Robust geometry.** A distance field is always a closed solid, and it meshes straight from the field
  with nothing to heal. On the production housing the regular CAD route left out six faces, and MeshFix
  lidded their holes flat, up to 242 mm across ([field-meshing-gate.md](field-meshing-gate.md)).
- **Interfaces held.** Bearing seats, bolt holes and the faces a drawing controls come out unchanged,
  cell for cell.
- **Explainable.** Each rule has a source; each piece left out names the rule it broke.
- **Data-ready.** It is the training-data factory the market is short of.

### Where it is not enough yet

- **Feasible is not yet fully castable.** Mould release - the pull direction, cores, draft,
  undercuts - is not checked; there is no solidification or porosity simulation; the thick-spot check is
  a geometric stand-in.
- **Only the rules and changes encoded**: ribs, webs, faces moved, holes. Ribs stand only on flat
  faces; a rib that would reach a hole is left out rather than ended short; nothing organic.
- **Not an optimiser on its own.** It makes feasible designs; choosing the best needs the surrogate
  and the optimiser planned.
- **Variety stays within the patterns** - parallel ribs, grids, spokes, free lines - until free layouts
  grown from a graph of legal connections come, the solver choosing which to join.
- **No editable CAD feature tree comes out.**
- **Fidelity**: the 3 mm grid rounds sharp edges by about a millimetre. On the production housing the
  field's answers match meshing the CAD within the noise of meshing itself
  ([field-meshing-gate.md](field-meshing-gate.md)). The drawn surface can cross itself where two
  sheets pass closer than the grid; meshing from the field never draws it.

### How the gaps close

- **Mould release** with the pull direction and cores; then draft and undercut maps.
- **A casting-process check** on the top candidates, in MAGMA or Inspire Cast.
- **Free layouts** from the graph of legal connections, for layouts no pattern makes.
- **Optimisation**: the surrogate and optimiser choose the best feasible design; shape optimisation or
  morphing then polishes it within its fixed topology.
- **Topology optimisation as a proposer**: its density field suggests where ribs want to be, and
  CP-SAT picks feasible layouts that follow it.
- **CAD for the winners only**: each recipe is parametric - rib paths, thicknesses, fillets - so the
  chosen few can be rebuilt as B-rep features.
- **Learned generators as customers**: rule-valid datasets are what they train on.

### How every variant is feasible

Feasible means it obeys every rule encoded and checked. The rules are enforced in layers, cheapest
first; whatever fails a layer is mended or dropped before the next:

1. **Only checkable rules are offered.** A rule the pipeline cannot hold a design to is not on the card.
2. **Each piece is placed by the rules.** A rib stands on a support with its ends buried in what it
   meets; keeps clear of named faces, measured from its footprint; keeps clear of holes and bores in
   three dimensions; is no taller than its limit; walls too thin for it get pads.
3. **CP-SAT holds the rules between pieces** - root gap, wedges of sand, hole ligaments, X crossings:
   it keeps the most pieces that obey them all and records what it left out.
4. **Screening** re-checks the placed design.
5. **The field build cannot make an invalid solid**: there are no Booleans to fail, and protected
   cells keep the interfaces untouched.
6. **Checks on the built shape**: rib thickness, root gap, fillets achieved, sand fingers at rib ends,
   blends not bridging or clipped, thick spots, nothing floating, the surface closed. A design that
   fails is rejected; one repair cannot save is drawn again.

### Limits of the repair

The repair (`src/fastcae/generate/repair.py`) minimises the number of pieces left out, holes before
ribs on a tie; it is deterministic (one worker, seed 0), which suits optimisation; it is value-blind - it keeps the most pieces, not the most useful ones, not knowing
which rib carries load; it makes the mapping from an optimiser's proposal to the realised design
discontinuous; pairwise rules are not castability - hot spots, feeding and porosity still need
screening or casting simulation; and the guarantee is only as good as the rule set.
