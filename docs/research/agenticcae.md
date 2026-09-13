# agenticCAE: the earlier project on the same housing

`C:\Work\agenticCAE` (remote `github.com/saxenam06/agenticCAE`, branch `fastcae_framework`) built a
surrogate for the **NREL GRC 750 kW gearbox, GB3 rear housing part 254492** - the same CAD file as
fastcae's, byte for byte. Its design space was 15 ribs, each present or absent (9 upwind at 25 mm, 6
downwind at 20 mm: 2^15 designs); each design went CAD → mesh → setup → solve. **490 designs were
solved on Google Cloud, 448 within the stress limit.** Its handbook is in `handbook/`; the NREL source
PDFs in `C:\Work\cae-data\grc-common\reports\`.

Stack: Python 3.12, cadquery/OCP, gmsh, pymeshfix, Code_Aster 18.0.12 (CalculiX kept as a cross-check),
FastAPI with server-sent events, a React/Vite console, Postgres 16 in docker-compose, a
LangChain/LangGraph agent, Zarr for the dataset, Google Cloud Slurm with Apptainer containers.

## Load case

One load case: **DLC 1.3 extreme, low-speed-shaft torque 401 kN·m**, bearing-seat forces derived by
gear statics. Units mm, N, N·mm; +Z along the main axis toward the generator; the main axis through
(0, 0), the intermediate shaft (AX2) through (246.3, 376.6), the high-speed shaft (AX1) through
(0, 520). From `assets/loads.json`:

```json
"_load_case": "DLC 1.3 extreme, LSS torque 401 kN.m. Rotor thrust and bending NOT included.",
"BORE_AX1_S1": {"FX": 5650.2, "FY": 55753.4, "FZ": -0.0},
"BORE_AX1_S4": {"FX": 9800.8, "FY": 35145.3, "FZ": -21524.2},
"BORE_AX2_S2": {"FX": -57911.6, "FY": 5846.0, "FZ": -0.0},
"BORE_AX2_S3": {"FX": -83661.3, "FY": 75243.6, "FZ": -28263.9},
"BORE_MAIN_S2": {"FX": 57185.8, "FY": -330205.7, "FZ": 71500.0},
"BORE_MAIN_S3": {"FX": 68936.2, "FY": -148449.3, "FZ": 137023.1},
```

- No moments, no MZ: shaft torque leaves through the annulus and the flange studs, not the bores.
- **`BORE_MAIN_S2` includes an assumed 50% carrier share**: 460 kN·m of rotor bending over an assumed
  750 mm arm, plus 71.5 kN of thrust - marked in the file as a "STATED ASSUMPTION", plausible band
  460-920 kN. The file also records an alternative helix-hand set. The handbook's `13-loads.md` gives
  `MAIN_S2` without the carrier share and `05-analysis.md` an older set with moments; `loads.json` has
  not changed since 2026-08-31, so every cloud campaign solved the set above.
- Gravity is supported in the deck (`PESANTEUR`) but was never switched on.
- The seats (from its interface proposals, by geometry): `BORE_AX1_S1` Ø180 z 113.9-170.1,
  `BORE_AX1_S4` Ø200 z 425.9-469.6, `BORE_AX2_S2` Ø180 z 113.9-170.1, `BORE_AX2_S3` Ø272 z 554.7-670.3,
  `BORE_MAIN_S2` Ø541 z 70.2-125.2, `BORE_MAIN_S3` Ø360.02 z 554.7-659.6; three cover registers
  (`BORE_AX1_S3`, `BORE_AX1_S5`, `BORE_AX2_S4`) coupled but unloaded.

## Supports and material

From `src/fastcae/fem/aster.py`:

```python
fix  = AFFE_CHAR_MECA(MODELE=model,
        DDL_IMPO=_F(GROUP_NO=tuple("REF_" + b for b in bolts), DX=0.0, DY=0.0, DZ=0.0),
        LIAISON_SOLIDE=tuple(_F(GROUP_NO=(b, "REF_" + b)) for b in bolts))
rbe3 = AFFE_CHAR_MECA(MODELE=model, LIAISON_RBE3=tuple(
        _F(GROUP_NO_MAIT="REF_" + b, DDL_MAIT=("DX","DY","DZ","DRX","DRY","DRZ"),
           GROUP_NO_ESCL=b, DDL_ESCL=("DX-DY-DZ",), COEF_ESCL=(1.0,)) for b in bores))
```

- **Flange bolts:** 25 on a 1120 mm circle, each a rigid RBE2-style tie to a reference node, only
  that node fixed. No contact, springs or preload; a stud tension of 256 kN is recorded but not
  applied.
- **Bearing bores:** 9 RBE3 couplings to reference nodes on the bore axis - 6 loaded seats, 3 unloaded
  cover registers; the reference nodes carry zero-stiffness `DIS_TR` elements so they have rotations.
- **Mounts:** the trunnions are on another casting (254506), so the model is stiffer than the machine
  and its displacements are lower bounds.
- **Material** ("cast iron"): E 169,000 MPa, ν 0.275, ρ 7.2e-9 t/mm³. **Stress limit:** a volume-weighted
  p99.9 von Mises of 200 MPa (yield 250 MPa / 1.25).
- **Sources** (`assets/gearbox.json` `_sources`): NREL/TP-5000-47773 (Tables 1 and 7-12), GB3 drawings
  254492 rev J, 254550, 254719, 251243 rev F and 254507; the misalignment objective from Hexagon/Romax's
  EDISON project.
- Bolt counts disagree across sources (25 in the archive doc, 30 in a memory note, 32 studs in
  `gearbox.json`); the 12 × M16 mounting pattern was never modelled.

## Mesh and solve

- **Mesher** (`src/fastcae/mesh/surface.py`): gmsh surface mesh (max 20 mm, min 4 mm,
  `AbortOnError=0`), a 0.5 mm weld, 3 mm edge collapse and MeshFix, then gmsh tetrahedra: about 200 k
  linear tets and 57 k nodes (57,240 nodes, 202,496 tets; q_min 0.00788) - non-deterministic (identical
  CAD gave 57,240 and 57,372 nodes). Converted to TETRA10 with MEDCoupling's linear-to-quadratic
  conversion (about 360 k nodes), mid-side nodes on straight edges.
- **Solver:** Code_Aster with MUMPS. `MACRO_ELAS_MULT` factorises once for 17 cases - the service case
  plus 16 per-seat, per-direction cases that sum to it, a free superposition check; low-rank and
  out-of-core options for TETRA10. CalculiX agreed to 0.000% on linear elements but cannot hold TETRA10
  in 7.8 GB.
- **Measured** (`handbook/research/16-implicit-rib-variants.md`): C3D4 0.19 M DOF - `MACRO_ELAS_MULT`
  55 unit cases 138 s, 55 × `MECA_STATIQUE` 385 s, CalculiX 55 × `*STEP` 915 s; C3D10 1.27 M DOF -
  1,139 s. Linear tets are 25-35% too stiff on this housing; on identical geometry quadratic gives 59%
  more hollow-shaft skew, 33-83% more bore tilt and 11× the gear-mesh misalignment. At 40 mm, bore tilt
  is within 7% of the 20 mm value; mesh misalignment still moves 50% from 40 to 20 mm.
- **Campaign run times** (GCP, TETRA10, 20 mm): cad 11.7 s, mesh 23.8 s, setup 11.1 s, solve 559.9 s,
  peak memory 10 GB; a 29-design run took a median 687 s per design and 36 min wall time at 14 at a
  time; on the laptop, linear elements, 243 s per design.
- **Analysis:** linear static only - no modal, harmonic or contact.
- **Outputs:** nodal displacement `u.npy`, stress `s.npy`, bore rotations `rot.npy` from the RBE3
  reference nodes, the per-case basis `basis.npy`, reaction sums; one Zarr store per design in
  PhysicsNeMo's layout.
- **Metrics:** bore tilt in arc-minutes from reference-node rotations (`hypot(drx, dry)`); gear-mesh
  lead misalignment - the difference of two shafts' skews along the line of action, each shaft's skew
  from its two bores' displacement, µm over the face width (186 mm at the IMS); a robust misalignment
  (median over a ±5% load band); volume-weighted p99/p99.9 von Mises (the peak chases singularities:
  two runs of the same design 1% apart in mesh gave 71.7 and 98.3 MPa); peak stress; largest
  displacement; added mass. Contours: von Mises, |U|, Uz, principal stress.
- **The immersed-grid alternative, measured** (occupancy on the real casting): 20 mm grid 29,013
  active cells (83% cut) 0.13 M DOF; 10 mm 182,504 (61% cut) 0.72 M; 5 mm 1,239,208 (36% cut) 4.39 M -
  "The fixed grid costs more DOF than the body-fitted mesh and spends them worse."

## Cloud and agent

- **Cloud:** Google Cloud Cluster Toolkit (`gcp/fastcae.yaml`): 7 × n2-highmem-4 compute nodes, 2
  designs per node; controller and login n2-standard-2; project `fastcae-slurm`, zone `asia-south1-b`;
  Terraform state in a bucket. An Apptainer image of about 1.2 GB with `code-aster=18.0.12=py312_nompi*`;
  the pipeline code is bind-mounted from a `git archive`. `server/campaign.py` uploads the plan, then
  `sbatch --array=1-N%14 --cpus-per-task=1 --mem=14G` over IAP; each design drops its 2 GB of solver
  scratch, syncs results and writes a `done/<id>` marker. About ₹2.5 per design. RunPod was planned only
  for GPU training; "No training code exists yet".
- **Campaign card** (`ui/src/CampaignView.tsx`): a sampler (Hadamard screening, focused, neighbours),
  a plan review (hash-based design ids show new versus solved), launch after checking the staged code
  is current, with a time and rupee estimate.
- **Agent** (`src/fastcae/agent/`): LangGraph with a Postgres checkpointer; default model DeepSeek via
  OpenRouter; 12 tools - eleven free (read-only SQL, Pareto front, neighbourhood, robustness,
  sensitivity, correlate, compare, sampler spec, campaign preview, artifact read, ask-user) and
  `submit_campaign`, the only one that spends money, gated by human-in-the-loop middleware with an
  approval card. Tools are thin HTTP calls to the platform's own API.

## What fastcae reuses, and what it adapts

**Reused almost as is:** the solver deck and runner (`fem/aster.py`), the MED writer and quadratic
conversion (`fem/med.py`), the CalculiX reader (`fem/frd.py`); the per-case load basis with its
superposition check; the metric post-processing (volume-weighted p99.9, bore tilt, shaft-skew
misalignment); the mesh repair route; the container, Slurm scripts and cluster blueprint; the
preview → price → submit → done-marker pattern and hash-based design ids; the agent pattern of thin
tools and one gated spend tool.

**Adapted:**
- Part-specific names (`BORE_MAIN_S2`, `SEATS`, part number 254492, `Rib B`, `gearmesh.json` shafts)
  become study data - fastcae has no part-specific code.
- Interfaces are read from fastcae's own detected features, by geometry (agenticCAE's face numbers
  differ: it read the STEP into 2,649+ faces; fastcae reads 1,753).
- Geometry: fastcae designs are distance fields and surfaces, not B-reps, so meshing starts from the
  surface (or is skipped - see [simulation.md](simulation.md)).
- Windows/WSL shims and hard-coded paths; modal analysis added; the TETRA10 straight-edge mid-side
  nodes and the carrier-share assumption reviewed. The load files (`loads.json`, `gearbox.json`,
  `gearmesh.json`) are read from `C:\Work\agenticCAE\assets` until they become study data.
