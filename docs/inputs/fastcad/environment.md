# Environment

Checked on 2026-09-15.

## Machine

- **CPU:** Intel i7-13700HX (16 cores)
- **RAM:** 15.7 GB. WSL gets 12 GB.
- **GPU:** RTX 5060 Laptop, 8 GB
- **OS:** Windows 11 Home 10.0.26200. Shells: PowerShell, and Git Bash for POSIX scripts.

The hardware figures come from fastcae's `docs/research/field-meshing-gate.md`.

## Installed and not installed

These were checked in `Program Files` and with `wsl -l`.

**Installed:**
- WSL with **Ubuntu 24.04**. Code_Aster and fastcae's compiled CGAL mesher run there.

**Not installed:**
- SolidWorks and other Dassault software
- FreeCAD
- Autodesk products
- Siemens products
- ANSYS
- Rhino 8
- A Windows build of Code_Aster

The user will install FreeCAD, or anything else, if it gets the job done.

**Onshape:** the user has an account. They used it to convert SolidWorks files to STEP and to close the housing volume. The agenticCAE repo avoided the Onshape API because it needed about 16,000 calls (4 per design × 4,000 designs) and the account was capped at about 2,500.

## Python environments

These were checked read-only, from the folder names in `site-packages`.

| Environment | Python | Present | Missing |
|---|---|---|---|
| `C:\Work\fastcae\.venv` | 3.12 (>=3.12,<3.13) | `cadquery-ocp` 7.9.3.1.1 (OCP / OpenCascade 7.9), `ortools` 9.15.6755, `trimesh` 5.1.0 plus Embree, `warp`, `cupy` | `pyvista`, `torch`, `pymupdf`, `build123d`, `gmsh`, `libigl`. The `simulate` extra is only partly installed. |
| `C:\Work\agenticCAE\.venv` | >=3.11,<3.13 | `cadquery` 2.8.0 plus OCP, `gmsh`, `pyvista` (with trame), `pymupdf` | `ortools`, `torch`/PhysicsNeMo, `build123d`, `warp-lang` |

The STEP analysis used the agenticCAE environment in read-only mode (`python -B`).

## Solvers and meshers

- **Code_Aster 18.0.12**, a development build with MUMPS 5.8.2 and MED 4.2.0. It is used for the GRC decks.
  - It runs single-threaded on purpose: with 4–8 threads, runs "crawled".
  - One solve takes about 2–2.5 min and 4–6 GB.
- **fastcae's GPU solver** (TET10 elements, linear statics only, using NVIDIA cuDSS).
  - It solves 1.12 M unknowns in 23 s and matches Code_Aster to about 1e-11.
  - It fails at about 2.4 M unknowns on the 8 GB card.
- **fastcae's compiled CGAL mesher.**
  - It lives in `native/cgal_field`, built into the WSL environment `fieldmesh` (CGAL 6.2.1, TBB, pybind11).
  - It meshes the production housing's CAD surface in 12.6 s.
- **gmsh** (in the agenticCAE environment) **cannot mesh the 254492 STEP directly.** It fails with "could not fix wire in surface 788".
- **fTetWild:** chosen to re-mesh the production housing for the baseline deck, because it keeps edges and holes. It is not yet confirmed as installed. fastcae's bench scripts used it once, for a preview.

## Data locations

- **`C:\Work\cae-data`:** the NREL GRC GB2 and GB3 datasets. The README says `D:\Work\cae-data`, but the data is actually on C:.
  - Quarantined, never to be opened or copied: anything matching `*54530*` (the GRC round-robin answer key) and the OEDI-738 vibration data.
  - This copy is incomplete: GB2 has no `cad\` folder, and GB3 is missing some TDMS zips and `254719.SLDDRW`. See [grc/data-inventory.md](grc/data-inventory.md).
- **`C:\Work\fastcad\assets\`:** the product's only input folder, kept small on purpose. 9 files, 47 MB: `target/cad/` (the canvas), `target/drawing/`, `target/deck/` (mesh and setup), `target/tech-data/` (the YAML data with a source per value). `fastcad.toml` names the canvas; `MANIFEST.csv` lists every file with its digest. See `assets/README.md`.
- **`C:\Work\fastcad\reference\`:** the library no run reads: earlier CAD exports, 286 GB3 and GB2 drawings, 8 NREL reports, the rib-free housing. About 128 MB, kept out of git, rebuilt by `scripts/make_reference.py`.
- **`C:\Work\fastcae\assets\GRC_Gearbox_Housing\`:** the rib-free `housing_baseline.brep`, the `baseline.*` deck (meshed on the rib-free housing), and `project.json`.

## Outputs that will be deleted if not saved

These are in Temp scratchpads, which get cleared. Saving them is M0's first task.

- **This session's scratchpad:** `C:\Users\saxen\AppData\Local\Temp\claude\c--Work-fastcad\e6899217-c8c2-481c-b37d-e34670208fd5\scratchpad\`
  - `step-analysis\`: `interface_candidates.json`, `design_language.json`, renders, drawing crops, the editability trials, scripts
  - `deck-analysis\`: `mesh_summary.json`, `rmed_summary.json`, `cad_compare.json`, `cad_detail.json`, scripts
  - `cae-extract\`: crops of the drawing notes, e.g. `251342E_p1_notes.png` and `251338C_p1_notes.png`
- **fastcae's meshing gate study** of the production housing: `C:\Users\saxen\AppData\Local\Temp\claude\c--Work-fastcae\746a05ff-0c04-4b6d-aed8-06d9692b9036\scratchpad\`
  - `solve\gate3cad` (meshed from the CAD surface): TET10 mesh, labels, setup, Code_Aster results as `.npz`
  - `solve\gate3`, `gate3seed` and `gate3reg`: the other meshing routes
  - `gate\projects\GRC_production`: the scratch project

## Repository

- **Location:** `C:\Work\fastcad`, remote `https://github.com/saxenam06/fastcad`.
- **Branch:** `task/gen_cad_framework`. The first commit, `90070ff` (2026-09-16), holds the docs corpus and the baseline assets.
- **`.gitattributes`** keeps CAD and FE files byte-exact: `*.step -text`, and `*.med`, `*.pdf` and `*.SLDPRT` as binary.
- **`.gitignore`** excludes `.remember/` and Python caches.
- **Before the session:** the `.git` folder was created at 2026-09-16 00:24, empty, on `main`. Only the task branch has been pushed.

## Connectors this session

- The GitHub MCP server failed to connect (bad authorization header), and Terraform was skipped.
- Gmail, Calendar, Drive, Supabase and Vercel need authorising.

None of these is needed for fastcad.
