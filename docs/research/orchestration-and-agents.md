# Running a campaign of thousands of solves, and agents in it

What runs thousands of designs through build, mesh, solve and extract - on a Windows workstation,
bursting to the cloud - how results keep their provenance, and what LLM agents do in simulation
workflows today. September 2026.

## What a job runner must do here

Queue every design through build → (mesh) → solve → extract → save; run several at once without
exhausting memory or the GPU; retry failures; carry on after a crash or restart; stream progress to
the interface; record where every number came from; send work to the cloud when the workstation is not
enough. A field build today runs inside the API's request, blocks, shows no progress and dies when the
development server reloads - the first thing to fix.

## Job runners

| | What it is | When it is worth it | When it is not | For fastcae |
|---|---|---|---|---|
| **[Prefect 3](https://www.prefect.io/blog/introducing-prefect-3-0)** (2024) | Python functions as tracked tasks: retries, caching of steps already done, limits on how many run at once, a web dashboard of every run; runs on Windows, can hand work to Dask or Ray | many steps per design needing retries and caching, when you do not want to build a dashboard | when you already have your own queue and interface; another server, a dashboard outside the app | useful, but duplicates the Agent tab |
| **[Dagster](https://dagster.io/blog/dynamic-partitioning)** | tracks every piece of data ("design 17's mesh") and what produced it; "dynamic partitions" map to one partition per design; re-runs only what changed - only meshes when the mesher changes | a data factory needing strict records of where everything came from | small teams early on; many new concepts | strongest for the published dataset later |
| **[Ray](https://docs.ray.io/en/latest/ray-overview/installation.html)** | spreads work across many machines and GPUs; distributed model training | multi-GPU training, big Linux clusters | Windows (support still beta, multi-node untested), a single laptop | only for large training runs on rented GPUs later |
| **[Dask](https://docs.dask.org/)** | parallel Python on one machine or a cluster; its local cluster works on Windows | many independent jobs across local cores | long campaigns that must survive restarts - it forgets everything when it stops | could run local builds, but still needs a job table |
| **[Snakemake](https://snakemake.readthedocs.io/en/stable/getting_started/installation.html)** | file-based workflow rules | Linux pipelines | limited on Windows (WSL advised) | low |
| **[HTCondor](https://htcondor.readthedocs.io/en/lts/platform-specific/windows-installer.html)** | batch scheduler | clusters | a workstation | low |
| **Own queue** | a table of design × stage jobs (queued, running, done, failed); workers outside the development server, sized to memory and GPU; progress into the Agent tab; cloud solves as agenticCAE's cluster batches | full control, one app, no extra servers | retry and resume are ours to write (a few hundred lines) | fits a workstation plus cloud bursts |

**Cloud bursts:** agenticCAE's Google Cloud cluster (Slurm array jobs, Apptainer container, results to
a bucket, a done marker per design - see [agenticcae.md](agenticcae.md)); [AWS Batch](https://aws.amazon.com/batch/)
with a Linux solver container on spot instances; [SkyPilot](https://docs.skypilot.co/) (managed spot
jobs across clouds, rented GPUs included); [Inductiva](https://inductiva.ai/simulators/calculix)
(CalculiX as an API); Rescale for enterprise. *(est.)* About 270-400 instance-hours, roughly $100-300,
for 4,000 runs; agenticCAE measured about ₹2.5 per design.

**Versioning and tracking:** [DVC](https://dvc.org/blog/dvc-joins-lakefs-your-questions-answered),
acquired by lakeFS on 18 November 2025 and still open source; lakeFS itself is overkill at this scale;
[MLflow 3](https://mlflow.org/blog/mlflow-3-0-launch) (June 2025) for self-hosted experiment tracking and
a model registry; W&B, owned by [CoreWeave since May 2025](https://www.coreweave.com/news/coreweave-completes-acquisition-of-weights-biases-2).

## LLM agents in CAE and simulation

**Research systems:**
- [MechAgents](https://arxiv.org/abs/2311.08166) (2023; EML 2024): FEniCS elasticity solved by
  planner, coder and critic agents.
- [An FEA multi-agent reliability study](https://arxiv.org/abs/2408.13406): only the
  Coder-Executor-Critic arrangement produced correct results.
- [FEABench](https://arxiv.org/abs/2504.06260) (Google, April 2025): LLMs driving COMSOL through its API.
- [MooseAgent](https://arxiv.org/abs/2504.08621) (April 2025): 93% success.
- [Foam-Agent](https://github.com/csml-rpi/Foam-Agent) (2025): 88.2% success with Claude 3.5 Sonnet;
  exposes MCP tools and runs on a LangGraph orchestrator that logs every call.
- [Engineering.ai](https://arxiv.org/abs/2511.00122) (October 2025): an agent team driving FreeCAD,
  Gmsh and CalculiX.
- [ALL-FEM](https://arxiv.org/abs/2603.21011) (March 2026): fine-tuned FEniCS agents, 71.8% success.
- [VFEAgent](https://arxiv.org/abs/2605.28978) (May 2026): engineering drawings to Abaqus runs.
- CAD agents: [CADCodeVerify](https://proceedings.iclr.cc/paper_files/paper/2025/file/81a934cd364e18ea6fdeaf57a93c17d4-Paper-Conference.pdf)
  (ICLR 2025); [CAD agents using FEA as feedback](https://arxiv.org/pdf/2605.17448) (May 2026).

**Steering simulation campaigns:** [Colmena](https://arxiv.org/abs/2110.02827) (2021), ML-steered
simulation ensembles; [Academy](https://arxiv.org/abs/2505.05428) (Argonne, May 2025), long-lived agents
on HPC; LLM agents with workflow engines for high-throughput screening
([April 2026](https://arxiv.org/pdf/2604.07681)); LLM agents running controlled simulation experiments
([August 2026](https://arxiv.org/abs/2608.23622)).

**Vendor copilots:** [Ansys Engineering Copilot](https://ansys.synopsys.com/blog/work-faster-smarter-with-ansys-engineering-copilot)
(2025 R2), mostly help and knowledge lookup; [Siemens NX Design Copilot](https://news.siemens.com/en-us/siemens-designcenter-nx-summer-2025/)
(July 2025); [Altair CoPilot](https://altair.com/newsroom/news-releases/altair-releases-altair-hyperworks-2025)
(beta); [Rescale agents](https://www.prnewswire.com/news-releases/rescale-introduces-agentic-digital-engineering-to-accelerate-ai-first-product-development-302769317.html)
(May 2026) for input validation, job-failure diagnosis and reports;
[Synera agents with AutoRib](https://www.synera.ai/news/how-autorib-and-syneras-ai-agents-automate-structural-rib-design)
(May 2026), the closest to a stress-then-ribs loop.

**The pattern for a campaign supervisor:** a deterministic orchestrator runs the jobs and owns the
state; the agent works only through tools, and a person approves each batch before compute is spent.
The agent's jobs: triage failures (mesh, solver, memory); check the data - reactions against applied
loads, mass, element quality, sane natural frequencies, outliers where ensemble members disagree;
propose the next batch with a reason; explain hot spots and sensitivities. agenticCAE's agent is this
pattern: eleven read-only tools and one spend tool gated by an approval card.

**Frameworks:**
- [LangGraph 1.0](https://www.langchain.com/blog/langchain-langgraph-1dot0) (22 October 2025):
  checkpointed durable execution and human-in-the-loop pauses; any model through OpenRouter.
- [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/migration-guide) (renamed from
  Claude Code SDK on 29 September 2025): subagents, hooks, sessions, in-process MCP tools; Claude only.
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) (March 2025): handoffs,
  guardrails, tracing.

## Where fastcae stands

Agents everywhere make "we have agents" non-differentiating ([market.md](market.md)); in fastcae they
are the audit trail - one copilot the engineer talks to, helpers behind it, every action logged, every
spend approved. The plan: an own job queue with workers outside the development server, agenticCAE's
cloud launcher for bursts, LangGraph with models chosen per helper through OpenRouter - see
[../build-plan.md](../build-plan.md).
