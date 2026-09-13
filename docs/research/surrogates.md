# Surrogates for 3D fields on varying geometry, and the data they need

Which models predict stress and displacement fields on shapes that vary from design to design, how
well they do on structural parts, and how to generate the least data that trains them. September
2026.

## Architectures

- **MeshGraphNets** ([ICLR 2021](https://sites.google.com/view/meshgraphnets)). Its only
  solid-mechanics evidence is the hyperelastic DeformingPlate benchmark.
  **X-MeshGraphNet** ([November 2024](https://arxiv.org/abs/2411.17164)) partitions the graph and works
  on multiscale point clouds. *Fit: medium*: a graph over 1-2 M-DOF tets is heavy, and X-MGN trailed
  the others on lift in [NVIDIA's DrivAerML benchmark (July 2025)](https://arxiv.org/abs/2507.10747):
  R² 0.52 against 0.95-0.97.
- **The Transolver family.** [Transolver](https://github.com/thuml/Transolver) (ICML 2024);
  [Transolver++](https://arxiv.org/abs/2502.02414) (ICML 2025: a million points per GPU, includes the
  Elasticity and Plasticity benchmarks); [Transolver-3](https://arxiv.org/abs/2602.04940) (ICML 2026:
  160 M cells). GeoTransolver is used in PhysicsNeMo's
  [crash recipe](https://github.com/NVIDIA/physicsnemo/tree/main/examples/structural_mechanics/crash).
  *Fit: high*: the strongest general baseline; cost grows linearly with the number of points.
- **GINO** ([NeurIPS 2023](https://arxiv.org/abs/2309.00583)). Encodes the distance field on a latent
  grid plus a graph operator; trained on 500 cars. *Fit: high conceptually* - built on distance-field
  grids like fastcae's - though its evidence is CFD only.
- **DoMINO** ([January 2025](https://arxiv.org/abs/2501.13350)). Multiscale point-cloud and distance-
  field encoding; best on DrivAerML (drag R² 0.98 from 436 training cases). A tutorial trained it on
  SimJEB brackets ([May 2026](https://hodgesj.substack.com/p/training-domino-on-simulated-jet)).
  *Fit: medium-high*.
- **FIGConvUNet** ([February 2025](https://arxiv.org/abs/2502.04317)). Grid-based factorised
  convolutions; the best von Mises error on the bracket benchmark below. *Fit: high* for voxel
  distance-field input.
- **AB-UPT** ([TMLR 2025](https://arxiv.org/abs/2502.09692), Emmi AI) and its
  [Noether framework](https://github.com/Emmi-AI/noether) (January 2026). State-of-the-art CFD scaling.
  *Fit: medium*: Noether needs a paid licence for commercial use.
- **GAOT** ([NeurIPS 2025](https://github.com/camlab-ethz/GAOT)). A multiscale attention encoder plus
  a transformer on arbitrary domains. *Fit: medium* (research code).
- **GINOT** ([CMAME 2025](https://arxiv.org/abs/2504.19452)). On the DeepJEB bracket set (about 1.9 k
  training designs), von Mises test error 35.6% relative L2 (1.7% normalised RMSE).
- **The FC4NO benchmark** ([Zhong et al., October 2025](https://arxiv.org/abs/2510.05995),
  [code](https://github.com/WeihengZ/FC4NO)), comparing 12 operators:
  - on a parametric bracket family (3 k designs), errors of 1.75-3.9%, parameter-conditioned
    branch-trunk models leading;
  - on the topologically diverse JEB brackets (2 k designs), von Mises errors of 29.8%
    (FIGConvUNet), 36.6% (Transolver) and 47% (GANO);
  - **the lesson**: how parametric the family is decides the accuracy. A rule-driven variant family
    of one part should behave like the parametric set, except at newly created hot spots.
- **Sharp features are the weak spot.** A 2D MeshGraphNet reached R² 0.97 on hole shapes similar to
  its training set, but only 0.32-0.71 on novel sharp features ([June 2026](https://arxiv.org/html/2606.08287v1)).
- **Commercial** - all closed; none offers an open structural foundation model:
  - [Neural Concept](https://www.neuralconcept.com/post/neural-concept-closes-100m-funding-round-led-by-growth-equity-at-goldman-sachs-alternatives-to-scale-ai-native-engineering):
    geodesic CNNs (ICML 2018) grown into a CAD-native platform; $100M Series C in December 2025;
    structural and crash housings.
  - [PhysicsX LGM-Aero](https://www.physicsx.ai/newsroom/introducing-lgm-aero-genai-for-aero-engineering-and-airplane-showcase-application-for-aerostructures)
    (December 2024): 25 M geometries, including Nastran stress.
  - [Luminary](https://aerospaceamerica.aiaa.org/institute/advancing-the-field-luminary-cloud-announces-new-physics-ai-models-at-aiaa-scitech-forum/):
    SHIFT models, CFD first.
  - [Ansys SimAI](https://ansys.synopsys.com/products/ai/simai): supports static linear structural, from
    20 or more runs.
  - [Altair PhysicsAI](https://altair.com/physicsai): 500 designs used to predict stress hot spots.
  - [Rescale AI Physics](https://rescale.com/documentation/ai-physics/): includes a CalculiX static-FEA
    tutorial.

## Data-efficient generation

- **Active learning.** [AL4PDE](https://arxiv.org/abs/2408.01536) (ICLR 2025): up to 71% lower error
  than random sampling, or the same accuracy with up to 4× fewer samples. Batch-selection methods
  (such as LCMD) come from [bmdal_reg](https://github.com/dholzmueller/bmdal_reg) (JMLR 2023).
  [PhysicsNeMo](https://docs.nvidia.com/physicsnemo/26.05/user-guide/active_learning.html) has an
  active-learning loop (release 25.11), a Gaussian-process uncertainty head for fields, and a
  [geometry out-of-distribution guardrail](https://docs.nvidia.com/physicsnemo/26.05/user-guide/guardrails.html)
  (26.03). Monolith claims up to 70% fewer tests with active learning. *Fit: high*. Keep a fixed
  random share in every batch so rounds do not erase unusual but valid designs.
- **Uncertainty.** Deep ensembles beat MC dropout, but both need calibration; split-conformal
  wrappers add coverage guarantees ([neural operators, June 2026](https://arxiv.org/abs/2606.09923);
  [mesh-based surrogates, Phil. Trans. A](https://royalsocietypublishing.org/rsta/article/384/2327/20250076/483089/Uncertainty-quantification-using-conformal)).
  Deep ensembles of graph networks can show "epistemic collapse", giving "surprisingly little
  improvement over a single model" ([May 2026](https://arxiv.org/abs/2605.22593)) - calibrate rather
  than trust spread alone. *Fit*: an ensemble of 3-5 models with conformal intervals on the metrics.
- **Geometry pretraining.** [GeoPT](https://physics-scaling.github.io/GeoPT/) (ICML 2026): pretrained on
  over 1 M samples; 20-60% fewer labels; tested on crash; open weights.
  [Shape](https://arxiv.org/abs/2604.22826) (April 2026): self-supervised on 61 k CAD meshes. *Fit:
  medium*: worth one ablation as an initialisation.
- **Physics-informed losses.** Weak-form or energy losses exist ([WINO 2026](https://arxiv.org/pdf/2605.24651);
  stiffness-based [PI-DeepONet](https://arxiv.org/pdf/2409.00994)); label-free training from a distance
  field has only been shown in 2D ([July 2026](https://arxiv.org/html/2607.09382v1)). *Fit: low-medium*
  as a regulariser; checking equilibrium residuals is cheap QA regardless.
- **Linear superposition is the biggest data saver.** For linear elasticity: solve one unit load case
  per bearing-force component on a single factorisation; train on the per-unit stress tensors and
  displacements; combine the unit cases for any real load, then compute von Mises. Load magnitudes
  drop out of the input space, and mode shapes do not depend on load at all. agenticCAE's deck
  already solves 16 unit cases on one factorisation, with a superposition check on every run.
- **How much data vendors use** (see [geometry-generation.md](geometry-generation.md#the-training-data-problem)):
  about 30-100 FE solves for a surrogate on scalar metrics, hundreds for full stress fields.

## Benchmark datasets and what they teach

- [SimJEB](https://arxiv.org/abs/2105.03534) (2021): 381 brackets, 4 load cases each.
- [DeepJEB](https://arxiv.org/abs/2406.09047) (2024; J. Mech. Des. 2025): 2,138 designs with B-rep,
  surface and volume meshes. [DeepJEB++](https://arxiv.org/html/2606.12994): 15,360.
- The FC4NO sets, on Harvard Dataverse.
- [DrivAerNet++](https://github.com/Mohamedelrefaie/DrivAerNet) (NeurIPS 2024): 8 k car designs, 39 TB.
- [SHIFT-Crash](https://huggingface.co/datasets/luminary-shift/SHIFT-Crash): 5,000 crash runs, open.
- No public benchmark for structural castings exists.

Lessons: a few hundred samples are enough for smooth fields on parametric families, but 2 k
topologically diverse brackets still leave about 30% von Mises error; keep a fixed random test set
that active learning never touches; store fields on the original mesh nodes and sample points at
training time.

## Formats

[PhysicsNeMo-Curator](https://github.com/NVIDIA/physicsnemo-curator) converts VTK/STL to Zarr with
validation - the de-facto format. [VTKHDF](https://www.kitware.com/vtkhdf-file-format-2025-status-update/)
is HDF5-based VTK readable in ParaView 6. [The Well](https://github.com/PolymathicAI/the_well) uses
self-describing HDF5. A NAFEMS team is drafting a
[metadata specification for surrogate-ready datasets](https://www.nafems.org/community/working-groups/engineering-data-science/metadata/).
A record per design: the distance field in Zarr, surface and TET10 fields in PhysicsNeMo's layout,
metrics and provenance in Parquet.

## Where fastcae stands

A rule-driven family of one part is closer to the parametric bracket family (2-4% error) than to the
diverse one (about 30%), except where new ribs create new hot spots - the weak spot of every model.
fastcae already has what the grid-based families need as input: a distance field per design. The
plan takes the field model (a distance-field encoder with a point decoder, PhysicsNeMo), accuracy
targets on a fixed test set, and active-learning rounds with a random share - see
[../build-plan.md](../build-plan.md).
