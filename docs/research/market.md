# The physics-AI market, and where fastcae fits

Checked 13 September 2026 across about 70 sources. No product found takes an existing,
non-parametric cast part and automatically generates many variants guaranteed to meet casting
rules. What changed in 2026 is that the large vendors now ship generators that learn geometry from
past designs: they make designs look manufacturable by copying the style of their training
designs, not by checking rules.

## The market in 2026

**Learned generators now shipping:**
- [Ansys GeomAI](https://news.synopsys.com/2026-03-11-Synopsys-Launches-Ansys-2026-R1-to-Re-Engineer-Engineering-with-Joint-Solutions-and-AI-Powered-Products) (11 March 2026).
- The [Neural Concept AI Design Copilot](https://www.neuralconcept.com/post/neural-concept-introduces-a-physics--and-geometry-aware-ai-design-copilot-extending-its-established-engineering-ai-platform) (7 January 2026).
- [Simcenter PhysicsAI Generate](https://blogs.sw.siemens.com/simcenter/whats-new-in-simcenter-physicsai-2026-1/) (29 July 2026, experimental).

**Surrogate models are becoming a commodity:**
- NVIDIA released open physics models ([Apollo](https://blogs.nvidia.com/blog/apollo-open-models), November 2025).
- The market is consolidating:
  - Siemens bought Altair ([closed 26 March 2025](https://news.siemens.com/en-us/siemens-altair-engineering-closing/)).
  - Synopsys bought Ansys ([17 July 2025](https://news.synopsys.com/2025-07-17-Synopsys-Completes-Acquisition-of-Ansys)).
  - CoreWeave bought [Monolith](https://www.coreweave.com/news/coreweave-to-acquire-monolith-expanding-ai-cloud-platform-into-industrial-innovation) (October 2025).
  - Mistral bought [Emmi AI](https://www.emmi.ai/news/mistral-ai-acquires-emmi-ai) (May 2026).
  - Cadence bought [Hexagon's design and engineering business](https://www.cadence.com/en_US/home/company/newsroom/press-releases/pr/2026/cadence-completes-acquisition-of-hexagons-design-and-engineering.html), including the Romax drivetrain tool (23 February 2026).
- What is scarce is valid geometry and labelled data.

## Vendors

| Vendor | Latest moves | What it does for structural parts and castings | What it does not do |
|---|---|---|---|
| Neural Concept | [$100M Series C](https://www.neuralconcept.com/post/neural-concept-closes-100m-funding-round-led-by-growth-equity-at-goldman-sachs-alternatives-to-scale-ai-native-engineering) (December 2025). The Copilot (January 2026) claims "10 to 1,000 times more design variants". Customers: GM, Subaru, GE, Leonardo, MAHLE, four F1 teams. [Siemens STAR-CCM+/NX integration](https://news.siemens.com/en-us/neural-concept-simcenter/) (June 2024) | Predicts results on raw meshes. Bosch Research emulated FE on an [e-drive housing](https://www.neuralconcept.com/post/e-drive-housing-designs-optimized-using-neural-concept-shape) in milliseconds. Shows a [confidence index](https://www.neuralconcept.com/post/the-importance-of-uncertainty-quantification-for-deep-learning-models-in-cae) | No casting rules stated |
| PhysicsX | [$300M Series C at about $2.4B](https://www.physicsx.ai/newsroom/physicsx-announces-300m-series-c-to-accelerate-physics-ai-for-industrial-engineering) (8 June 2026); Siemens and NVIDIA are investors. [LGM-Aero](https://www.prnewswire.com/news-releases/physicsx-introduces-free-to-use-ai-for-advanced-engineering-to-transform-aerospace-development-302321544.html) trained on 25M+ meshes and tens of thousands of CFD/FEA runs made in Simcenter (December 2024) | Heavy on services: its [simulation engineers parametrise customer geometry](https://www.physicsx.ai/newsroom/simulation-engineering-at-physicsx-the-bridge-between-physics-and-ai) by hand. An [aerospace foundry defect model](https://www.physicsx.ai/newsroom/real-time-intelligence-in-the-foundry-ai-for-casting-quality-and-efficiency) (September 2025) covers mould and gating, not the part | No productised generator of castable variants |
| Ansys (Synopsys) | 2026 R1: SimAI Pro/Premium, optiSLang connectors (data generation to training to optimisation), GeomAI, Mesh Agent | [SimAI](https://ansys.synopsys.com/blog/explaining-simai): at least about 35 training runs recommended; its confidence score is the distance to the nearest training geometry. GeomAI works "without… complex parametric trees" | GeomAI keeps designs "manufacturable" by preserving their design language, not by enforcing casting rules |
| Siemens (including Altair) | [PhysicsAI add-on for STAR-CCM+](https://news.siemens.com/en-us/siemens-simcenter-physicsai/) (27 May 2026). [Unified Simcenter portfolio](https://www.prnewswire.com/news-releases/siemens-accelerates-engineering-simulation-with-a-unified-ai-powered-simcenter-portfolio-302835381.html) (28 July 2026). PhysicsAI 2026.1 adds Generate, a native link to Simcenter Inspire casting/moulding/forming, and a 0-1 similarity score | The most complete stack: Inspire Cast (defects plus AI) and the [HEEDS AI predictor](https://press.siemens.com/global/en/pressrelease/siemens-revolutionizes-engineering-simulation-heeds-ai-simulation-predictor-and) (up to 40% less compute). Examples: a [control arm, 500 variants](https://blogs.sw.siemens.com/simcenter/beyond-the-solver-how-geometric-deep-learning-is-reshaping-cae/); [Kinetic Vision](https://www.siemens.com/en-us/products/simcenter/engineering-data-science-ai/physicsai/), 4,000x faster FEA | No rule-driven variants of existing parts (yet) |
| Dassault SIMULIA | [NVIDIA partnership](https://nvidianews.nvidia.com/news/dassault-systemes-nvidia-industrial-ai) (February 2026). [LEO engineering companion](https://www.3ds.com/newsroom/press-releases/dassault-systemes-unveils-new-way-working-industry-ai-powered-virtual-companions) due 2026 | Surrogates giving real-time predictions | Nothing specific to castings |
| Luminary Cloud | [$72M Series B](https://luminary.ai/resources/luminary-cloud-secures-72m-series-b-to-lead-the-physics-ai-era/) (15 September 2025). [SHIFT-SUV](https://www.prnewswire.com/news-releases/luminary-cloud-unveils-first-physics-ai-open-source-automotive-foundation-model-for-suv-aerodynamics-in-collaboration-with-honda-and-nvidia-302424056.html) with Honda. [SHIFT-Crash](https://www.globenewswire.com/news-release/2026/04/14/3273745/0/en/luminary-launches-shift-crash-the-first-physics-ai-model-for-full-vehicle-crash-prediction.html) (14 April 2026): 5,000 runs, published openly on [Hugging Face](https://huggingface.co/datasets/luminary-shift/SHIFT-Crash) | Structural crash foundation models; publishes its datasets | No castings |
| NAVASTO (Autodesk, [October 2024](https://blogs.autodesk.com/design-studio/2024/12/10/welcome-navasto/)), Emmi AI, [BeyondMath](https://tech.eu/2026/02/25/beyondmath-secures-185m-to-expand-the-worlds-largest-foundational-physics-ai-model/) ($18.5M, February 2026), Monolith | - | CFD, or learning from test data (Monolith) | Not structural castings |
| nTop | [CEO: automated parameter sweeps in traditional CAD fail 70-80% of the time](https://www.ntop.com/resources/blog/you-can-t-reach-the-promise-of-ai-accelerated-engineering-without-fixing-the-geometry-bottleneck/) (14 April 2026). [CoreWeave demo](https://www.ntop.com/resources/blog/ntop-coreweave-nasa-2030-grand-challenge-in-cfd/): 2,400 variants and 12,000 CFD runs on 280 GPUs with zero geometry failures. [PhysicsX pipeline](https://www.ntop.com/resources/webinars/ai-accelerated-design-workflows-with-ntop-and-physicsx/) (June 2026) | Rib Design with draft and fillets; batch variants sold as surrogate training data | The engineer builds every workflow by hand |
| Synera | [$40M Series B](https://www.synera.io/press/synera-raises-40m-series-b-to-scale-agentic-ai-engineering-for-global-manufacturers) (April 2026), 60+ enterprise customers. [Agents with NVIDIA](https://www.businesswire.com/news/home/20260531683430/en/Synera-Advances-AI-Agents-for-Design-and-Engineering-Simulation-with-NVIDIA) (31 May 2026) | Markets [die-casting design automation](https://www.synera.ai/design-automation-die-casting-injection-molding) | [AutoRib](https://www.synera.ai/news/how-autorib-and-syneras-ai-agents-automate-structural-rib-design) targets injection moulding |
| Rescale | [Agents](https://www.prnewswire.com/news-releases/rescale-introduces-agentic-digital-engineering-to-accelerate-ai-first-product-development-302769317.html) for input validation, troubleshooting and reports (12 May 2026). Customers: McLaren, Daikin | Data curation, training, deployment | No geometry generation |
| Cadence | Now owns ANSA (mesh morphing plus AI prediction), Nastran and Romax | Has both a gearbox tool and morphing | No castability layer |

**Casting-process simulation:**
- MAGMASOFT [6.1](https://www.magmasoft.co.in/en/solutions/magmasoft/new_release/magmasoft_6.1/) adds cost and CO2 evaluation. Its "autonomous optimisation" is virtual design of experiments; no machine learning is listed.
- [ProCAST](https://www.keysight.com/us/en/lib/software-detail/des/casting-procast.html) 2026.0 (Keysight) and FLOW-3D CAST show no AI features.
- Simcenter Inspire Cast is the only process tool that markets AI.

**AI for the casting process** is all shop-floor process control:
- DISA/Monitizer [PRESCRIBE](https://www.foundry-planet.com/d/monitizer-prescribe-slashes-scrap-by-nearly-90-astonishing-results-from-disas-ai-driven-optimisation-tool-as-adoption-keeps-growing/) (with DataProphet) cuts scrap by about 40% on average.
- [Castella](https://www.euroguss.de/en/events-programme/2026/speakers-corner/castella-a-shopfloor-ai-app-for-die-casting-optimisation) (EUROGUSS 2026).
- The research platform [AI-CAST](https://iopscience.iop.org/article/10.1088/1742-6596/2921/1/012002), applied to a 6 MW wind hub.
- Tools that check designs but do not generate them: [DFMPro](https://dfmpro.com/manufacturing-processes/dfmpro-for-casting/), [aPriori](https://tech-clarity.com/apriori/23198).
- [Dessia](https://www.eu-startups.com/2024/10/paris-based-dessia-raises-e3-million-to-automate-engineering-processes-through-ai/) generates designs from rules, but for architectures such as gearboxes, not cast geometry.

**Case studies on housings** are thin: the Bosch e-drive housing and Siemens' control arm. None were
found on gearbox or wind castings.

## The hurdles industry reports

- **Data:**
  - [SimScale survey](https://explore.simscale.com/hubfs/resources/reports/state-of-engineering-ai-2026.pdf) (vendor-run; 350 leaders, February 2026):
    - Blockers: 74% name data preparation and availability as the top blocker, 48% governance, 42% interoperability.
    - Adoption: 92% use surrogates but only 8% extensively; 9% have mature programmes; pilot to production takes 8 months on average.
  - Some teams delete simulation data to save storage ([NAFEMS Americas recap](https://rescale.com/blog/nafems-americas-2026-recap/), June 2026).
- **Cost of generating data:** from about 35 runs (the SimAI minimum) to 5,000 (SHIFT-Crash), falling to under 300 by an OEM's third programme through transfer learning.
- **Parametrising existing CAD:** nTop reports 70-80% failure: "We wanted to explore fifty configs. We got to three."
- **Meshing:** Ansys shipped a Mesh Agent to fix meshing failures. 55% of engineers still pass results between simulation steps by hand (NAFEMS recap).
- **Manufacturability:**
  - Generated wall thickness comes "[from training data patterns rather than structural requirements](https://www.getleo.ai/blog/ai-generated-cad-models-production-guide)".
  - Generative tools are "[not capable of handling the manufacturing constraints](https://www.colabsoftware.com/post/ai-cad-in-2026-why-design-review-is-delivering-roi-while-generative-design-catches-up)" production engineering needs.
  - Topology-optimised castings are still rebuilt by hand ([Rosnitschek 2021](https://www.mdpi.com/1996-1944/14/13/3715)).
- **Trust:** 71% of organisations require human review of every AI output. No standard is finished yet ([ASME VVUQ 70](https://cstools.asme.org/csconnect/CommitteePages.cfm?Committee=103099834), [NAFEMS validation course](https://www.nafems.org/events/nafems/2026/ai-model-validation-for-simulation-data-2/)).
- **Out-of-distribution designs:** vendors rely on distance-to-training-data scores. Key Ward lists "[confident predictions that are physically wrong. No warnings](https://www.keyward.io/blog/surrogate-model-data-preparation)" as a top failure mode.
- **IP and PLM integration:** "How do we protect our IP… in a multi-tenant cloud?" (NAFEMS). 70% cite secure data governance as the enabler that matters; 42% cite interoperability as a blocker.
- **Standards:** a NAFEMS team chaired by Key Ward is drafting a [metadata specification for surrogate-ready datasets](https://www.nafems.org/community/working-groups/engineering-data-science/metadata/), with no publication date. [PhysicsNeMo Curator](https://github.com/NVIDIA/physicsnemo-curator) (Zarr) is the de-facto format.

## Where fastcae's capabilities are unique

fastcae's stack - rule-guaranteed castable variants from a plain STEP file, CP-SAT repair, automated
mesh and solve, agent supervision - addresses the three top hurdles: data, legacy geometry and
manufacturability. The vendors' core is the model; fastcae's is the data and geometry that feed it.

- **Product:** a castable design-space compiler. A STEP file and a process rule set go in; variants, meshes, FE labels and NAFEMS/Zarr metadata that import into SimAI, Simcenter PhysicsAI, PhysicsX or Neural Concept come out.
- **Services:** fixed-price casting datasets that solve the cold start; validation and out-of-distribution audits; castable alternatives for foundry RFQs.
- **Partnerships:** casting-data subcontractor to PhysicsX and Neural Concept delivery teams; process checks of the best candidates in MAGMA or Inspire Cast; rule sets co-authored with foundries; a PhysicsNeMo example for reach; Cadence (Romax plus ANSA) as a gearbox channel. The consolidators above are also the likely acquirers.

**What a credible GRC demonstration must show:**
1. A plain STEP file goes in; report the time to the first valid variant.
2. At least 2,000 variants, with CP-SAT repair and rejection statistics, and 100% rule compliance confirmed by an independent checker; a process check on the top 10.
3. Geometry, mesh and solve success rates - the answer to nTop's 70-80% failure claim - and the cost per labelled variant.
4. The baseline FE model checked against public [NREL GRC dynamometer data](https://data.nrel.gov/submissions/56); for example, the carrier moves [up to 63 µm](https://gearsolutions.com/features/validation-of-a-model-of-the-nrel-gearbox-reliability-collaborative-wind-turbine-gearbox/) relative to the housing.
5. A learning curve (error at 35, 100, 300 and 1,000 runs) with the agent choosing each batch, including held-out variant families to test whether confidence scores flag them.
6. Pareto trade-offs of mass, bearing-seat stiffness and stress margin, with the interfaces kept.
7. A second part - an automotive die-cast housing with its own rule set - to prove the method is not specific to the GRC housing.
8. An auditable trail from the engineer's words to the campaign to the agent's decisions.

## Risks, next 6-18 months

- **Siemens is the highest risk** (a judgement): adding rule constraints to PhysicsAI Generate, already linked to Inspire Cast, would overlap directly.
- **Ansys:** GeomAI, SimAI and Mesh Agent together already form a generate-mesh-predict loop.
- **nTop and Synera:** either could ship "STEP in, castable ribs out" templates.
- **Neural Concept:** it markets the Copilot as producing "manufacturing-ready" models; explicit manufacturing constraints are a plausible next step.
- **Cadence:** Romax plus ANSA morphing plus AI could become a gearbox-housing workflow.
- **Commoditisation:** data factories (Rescale, Luminary, CoreWeave with nTop) and agents (Rescale, Synera, Ansys, Dassault's LEO) make "we run many simulations" and "we have agents" non-differentiating.

## Positioning options, ranked

| # | Positioning | Buyer | Pain it solves | Proof point to build | Why incumbents leave room |
|---|---|---|---|---|---|
| 1 | Castable design-space and training-data compiler, sold through physics-AI vendors | CAE methods leads at automotive OEMs and Tier-1s piloting surrogates on cast housings; the vendors' delivery teams | Data is the top blocker; legacy STEP files; generated designs that cannot be cast; cold start | Demonstration items 1-5 and 7, plus one import into a vendor platform | Incumbents generate by imitation or hand-built workflows and deliver this as expensive services; none enforce casting rules on legacy parts |
| 2 | Castable-alternatives engine for casting suppliers (RFQs, early supplier involvement) | [Nemak](https://www.nemak.com/blog/news-3/nemak-completes-the-acquisition-of-gf-casting-solutions-automotive-business-12) (now including GF's automotive casting business, February 2026), [Linamar](https://www.foundrymag.com/molds-cores/news/55321854/canadian-manufacturer-buying-gf-foundry-in-germany-linamar-corp), ductile-iron foundries | DFM tools only flag problems; process AI tunes parameters, not geometry; RFQ speed (AI workflows about 3x faster, per SimScale) | A 48-hour drill: 5 castable alternatives with mass/stiffness trade-offs and a process check | Foundry AI stays on the shop floor; casting-simulation vendors optimise gating and feeding, not the part |
| 3 | Surrogate validation and out-of-distribution audit for cast parts | Simulation governance owners; vendors needing third-party evidence | 71% human review; unvalidated confidence scores; unfinished standards | Held-out, rule-valid GRC variant families and a report of error against confidence score | Vendors cannot audit themselves; realistic test cases need a castable-variant generator |
| 4 | Wind drivetrain castings as a first niche | ZF Wind Power, Flender/Winergy, large-casting foundries | Heavy castings, few simulations, mass and cost | The GRC demonstration plus an open dataset | Physics-AI vendors focus on automotive, aerospace and semiconductors; the niche is small |

- Don't lead with agent supervision: it is the audit trail behind the pitch.
- Publishing the GRC dataset openly builds credibility for options 1 and 3. No public benchmark for
  structural castings exists; the only structural ones are brackets ([SimJEB](https://simjeb.github.io/),
  381; [DeepJEB](https://arxiv.org/abs/2406.09047), 2,138; [DeepJEB++](https://arxiv.org/html/2606.12994), 15,360).

**Caveats:** some pages blocked fetching (the Ansys blogs, nTop support), so those facts come from
search excerpts; SimScale, Key Ward, Leo AI and CoLab are vendors writing about their own market;
"nobody does this" means no evidence was found across about 70 sources over two days.
