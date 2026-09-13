# Optimising with surrogates

How vendors and open source optimise with a surrogate, how a hard feasibility layer fits in, and the
stack recommended for fastcae. September 2026.

## Vendor loops

All follow "surrogate proposes, solver confirms".
- **optiSLang:** competing metamodels ranked by forecast quality, and "Always verify the final
  candidate with the high-fidelity solver"; release 2026 R1 adds SimAI connectors for generating
  data, training and optimising ([engineering.com](https://www.engineering.com/synopsys-releases-ansys-2026-r1-engineering-platform/)).
- **HEEDS:** hybrid adaptive search (SHERPA); release 2510 upgrades its multi-objective version and
  recommends minimum evaluation counts; its AI predictor replaces runs it is confident about.
- **HyperStudy:** global response-surface search, as in the BMW mega-casting study.
- **Neural Concept:** back-propagates gradients to mesh vertices, or uses evolutionary plus local
  search; variance maps plan the next samples ([post](https://www.neuralconcept.com/post/on-deep-learning-and-multi-objective-shape-optimization)).
- **PhysicsX:** gradient descent in latent space.

## Open source

| Library | What it is good at | Fit here |
|---|---|---|
| **BoTorch 0.18.1 (8 June 2026) and Ax 1.0 (18 November 2025)** ([changelog](https://github.com/meta-pytorch/botorch/blob/main/CHANGELOG.md), [Meta](https://engineering.fb.com/2025/11/18/open-source/efficient-optimization-ax-open-platform-adaptive-experimentation/)) | few expensive solves; several objectives at once with limits; mixed choices and numbers | best for finding designs with real solves |
| **pymoo 0.6** | genetic search (NSGA-II/III), mixed variables, and a [Repair operator](https://pymoo.org/constraints/repair.html) that "makes sure every solution that is evaluated is feasible" - exactly where CP-SAT fits | best for mapping trade-offs on the surrogate |
| **Optuna 4.5** | its Gaussian-process sampler does constrained multi-objective optimisation ([blog](https://medium.com/optuna/optuna-v4-5-81e78d8e077a)) | quick baseline |
| **SMT 2.x** | Kriging for hierarchical and mixed variables ([2024](https://arxiv.org/abs/2305.13998)) | niche |
| **HEBO** | won the NeurIPS 2020 black-box challenge ([arXiv](https://arxiv.org/abs/2012.03826)); single objective | baseline |
| **Bounce** | high-dimensional combinatorial spaces ([arXiv](https://arxiv.org/abs/2307.00618)) - assumes every combination is valid | no |
| **Nevergrad** | repeats mutations "until we get a satisfiable point" ([docs](https://facebookresearch.github.io/nevergrad/optimization.html)) - rejection sampling, which collapses when valid rib subsets are rare | no |
| **Dakota, OpenMDAO** | gradient-oriented multidisciplinary tools ([Dakota](https://snl-dakota.github.io/), [OpenMDAO](https://openmdao.org/what-is-openmdao/)) | overkill |

What BoTorch/Ax bring: qLogNEHVI multi-objective acquisition ([NeurIPS 2023](https://arxiv.org/abs/2310.20708))
with outcome constraints; mixed alternating optimisation (`optimize_acqf_mixed_alternating`) with
categoricals and equality constraints; nonlinear input constraints and projection onto the feasible
set; a conditional kernel for hierarchical spaces (0.18); an NSGA-II utility and ensemble models;
TuRBO/SCBO trust regions ([AISTATS 2021](https://arxiv.org/abs/2002.08526)); probabilistic
reparameterisation for mixed spaces ([NeurIPS 2022](https://arxiv.org/abs/2210.10199)).

**Known-constraint methods** - [ENTMOOT tree kernels](https://arxiv.org/abs/2207.00879),
[PK-MIQP 2024](https://arxiv.org/abs/2410.16893), NN+MILP - encode rules inside the acquisition step:
the formal version of a CP-SAT layer.

**Uncertainty:** deep ensembles of graph networks show "epistemic collapse", giving "surprisingly
little improvement over a single model" ([May 2026](https://arxiv.org/abs/2605.22593)); for large
batches, one option is non-dominated sorting that includes uncertainty
([Ansari et al. 2023](https://arxiv.org/abs/2306.01095)).

## The stack recommended for fastcae

1. **Keep CP-SAT, but weight it.** Maximise the weighted sum of kept pieces, the weights from what the
   optimiser asks for and later from a stiffness-sensitivity proxy. Keep the fixed seed. Return the
   realised design vector and the left-out count. Keep it as the feasible-design generator: the Sobol
   draw followed by repair in `src/fastcae/generate/campaigns.py`.
2. **Start with 2-3 times as many feasible designs as there are levers.** With about 10-25 levers a
   campaign, 30-75 FE solves - in line with SimAI's 30-100.
3. **Optimise with Ax 1.0 and BoTorch.**
   - Model: a mixed or hierarchical Gaussian process on scalar metrics; the sparse (SAAS) variant
     beyond about 20 levers.
   - Objectives: qLogNEHVI on mass and bearing-seat tilt or stiffness.
   - Constraints: stress margin at or above target as an outcome constraint, not a third objective;
     the left-out fraction as a soft constraint, so the optimiser learns to propose designs that need
     little repair.
   - Run repair inside the black box - or score a pool of about 10⁴ CP-SAT-feasible designs with the
     acquisition function.
   - Batch size matched to parallel FE capacity; TuRBO/SCBO trust regions beyond about 20 levers.
4. **Map the predicted Pareto front cheaply.** pymoo NSGA-II/III on the surrogate's mean with CP-SAT
   as its Repair step, then FE-verify a diverse subset.
5. **Verification rules:** report only FE-verified designs; log surrogate error for every batch; gate
   proposals on predictive spread or distance from existing data, as SimAI's confidence flag does;
   stop when the hypervolume stops improving and verified error is within tolerance; keep a test set
   the optimiser never touches.
6. **The field surrogate** joins as a lower-fidelity input once data accumulates across campaigns;
   calibrate it rather than relying on ensemble spread alone. Optuna 4.5's Gaussian-process sampler
   makes a quick baseline.

Mass is computed exactly from geometry, never learned.
