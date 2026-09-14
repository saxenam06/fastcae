# The baseline's own deck, made and reproduced

The product takes the engineer's own solver deck and answer for the baseline as input (see
[../simulate.md](../simulate.md)). For the GRC housing without ribs there was no such deck, so one was
made the way agenticCAE made its designs' decks - the stand-in for what a customer uploads - and read
back and solved again by the product. September 2026, on this workstation (RTX 5060 Laptop 8 GB, WSL
with 12 GB). Script: `bench/solvers/baseline_deck.py`.

## The deck

Meshed exactly as the gate's CAD-surface route ([field-meshing-gate.md](field-meshing-gate.md), route
A): agenticCAE's own procedure meshes the part first (193,450 tets in 13-17 s; gmsh skips 4 faces, as
it did on the production housing) and its element sizes are read off that mesh; the compiled CGAL
mesher fills the CAD's own 0.5 mm triangulation held to those sizes, following the six loaded seats'
edges with vertices 8 mm apart - 209,044 TET10 and 377,270 nodes in 13 s, about 1.13 M unknowns.
Seats and bolt holes labelled by the within-2 mm rule; the six loaded seats' patches hold 1,099-3,834
nodes, as the gate's did (1,124-3,891).

Setup as agenticCAE's: 25 bolt positions each a rigid coupling to a reference node held in translation;
the six loaded seats each a distributing coupling to a reference node on the bore's axis carrying the
DLC 1.3 extreme forces; iron, E 169,000 MPa, ν 0.275. The deck asks for the displacement and rotation
of each seat's reference node. Written as Code_Aster's `.export`, `.comm` and MED mesh; the MED
converted from Code_Aster's own text format by Code_Aster itself.

The six files - `baseline.export`, `baseline.comm`, `baseline.med`, and Code_Aster's `baseline.rmed`
(141 MB), `baseline_signals.resu` and `baseline.mess` - sit in the project folder beside the CAD and
the drawing, as a customer's would.

## The run, and the product's own solve of it

| | Code_Aster 18.0.12 (MUMPS, one thread) | fastcae (cuDSS, RTX 5060 8 GB) |
|---|---:|---:|
| Unknowns | 1.13 M, the couplings as equations beside them | 1,118,199, the couplings eliminated |
| Time | 2 min 35 s | 23 s: assemble 3.3, reduce 4.1, plan 5.4, factor 4.3, back-solve 0.2, stress 3.5 |
| Memory | 6.36 GB peak | GPU hybrid memory, 8 GB card |

The product's solve of the deck it read agrees with Code_Aster's answer to about 10⁻¹¹: the
displacement field to 4.4·10⁻¹¹ and the von Mises field to 5.6·10⁻¹¹ of their largest values, every
deck signal (each seat reference node's three displacements and three rotations) within 3.6·10⁻⁹,
each of the 25 bolt reactions within 3·10⁻¹¹, and the supports together carrying 345,313 N - the
applied load.

## The variant route on the baseline

Every design will be built as a 3 mm field, meshed from it by the compiled CGAL mesher held to the
deck mesh's own element sizes (the loaded seats' edges followed), given the deck's setup by the CAD
faces each group lies on, and solved by cuDSS. Walked on the baseline itself by the product's runner,
in about 100 s end to end (the field kept; CGAL 9 s for 214,210 TET10 and 1.15 M unknowns, no element
below quality 0.1; the setup carried; cuDSS), and set against the engineer's Code_Aster answer on its
own mesh:

| Quantity | Code_Aster (deck mesh) | fastcae's route (its own mesh) | Held to |
|---|---:|---:|---:|
| Tilts, six seats | 1.94' - 86.5' | every one within 0.51 % | 3 % |
| Largest displacement | 22.32 mm | 22.26 mm, -0.27 % | 3 % |
| Work of the loads (the strain energy) | 1,146 J | -1.4 % | 3 % |
| p99.9 von Mises | 880.6 MPa | 859.2 MPa, -2.4 % | 5 % |
| Each reference point's displacement, as a vector | | worst 1.5 % (BORE_AX1_S1) | 5 % |
| Each reference point's rotation, as a vector | | worst 0.7 % (BORE_MAIN_S2) | 5 % |
| p99 von Mises (advisory) | 264.9 MPa | -6.1 % | - |

The marks are the gate's, from what meshing the same shape twice moves. Two rules of the comparison
came out of it: a deck signal is compared a point at a time as a vector - one rotation component of
2·10⁻⁵ rad inside a rotation of 8·10⁻⁴ rad differed by 24 % while the rotation differed by 0.6 % - and
stress percentiles below p99.9 are advisory on another mesh, since on design #7 p99 moved 8 % with
the mesh alone.

## What the baseline answers

Without ribs the housing is far softer than any ribbed one solved so far, under the same loads:

| | Rib-less baseline (this deck) | Design 7 (baseline + campaign ribs, bolt holes clamped) | Production housing (ribs, agenticCAE's couplings) |
|---|---:|---:|---:|
| Largest displacement | 22.3 mm | 0.854 mm | 0.418 mm |
| BORE_MAIN_S2 tilt | 86.5' | 1.47' | 1.84' |
| BORE_AX2_S2 tilt | 10.3' | 1.13' | 0.87' |
| p99.9 von Mises | 881 MPa | 114 MPa | 55 MPa |

The number was checked independently: the benchmark's own setup code (`solve_aster.py couplings`,
which builds agenticCAE's couplings itself and does not read the deck) on the same mesh gives
22.324 mm - so it is the part, not the deck writer. The baseline is the starting point the ribs are
designed onto; every variant's answer is read against it.

## What went wrong on the way, and why

- **A new recipe instead of the proven one.** The first deck was meshed at a uniform 20 mm with edge
  lines on all nine bores and a distributing coupling on each. The three narrow bores (AX1_S3, AX1_S4,
  AX2_S4) meshed at about 4 mm instead of 12-14 mm - AX1_S4 held 4,640 nodes where the gate's had
  1,135 - and the nine couplings together 26,604 nodes against the gate's 12,652. Code_Aster sat in
  its factorisation 30 minutes and was stopped.
- **The cost of a distributing coupling in Code_Aster.** Each ties its reference node to every node
  of its patch through constraint equations that touch all of them, which MUMPS factorises as dense
  blocks. Coupled nodes, not the mesh's size, set the time: the decks were all 1.1-1.2 M unknowns.
  fastcae's own solve has no such cost - the coupling's load is spread over the nodes as forces.
- **A reference node nothing ties.** Coupling only the six loaded seats while keeping reference nodes
  for all nine left three zero-stiffness points free: the matrix is singular and Code_Aster stops
  (`FACTOR_11`). The product now reports such a point when it reads a deck.
- **Threads.** Given 4 or 8 threads, MUMPS on these couplings crawled (resident memory flat at
  2.3-2.6 GB for tens of minutes); every run that finished had one. The deck asks for one, and every
  Code_Aster run is stopped from the Linux side after its time limit (15 minutes for one design).
- **cuDSS out of GPU memory.** Assembling on the GPU leaves CuPy's pool holding the blocks it freed;
  cuDSS allocates outside that pool and ran out while factorising - with a design being built on the
  same card at the time. The solve now empties the pool before cuDSS plans, and in the product only
  the runner uses the GPU, one job at a time.

## The deck read back and solved here

On a small deck of the same kind - a bar held through a rigid coupling at one end and loaded through a
distributing one at the other, run by Code_Aster 18.0.12 through `run_aster` - the product reads the
mesh, groups, setup, fields and table, and its own solve agrees with Code_Aster to about 10⁻¹²:
displacement everywhere, the distributing coupling's reference motion in all six components, stress,
and von Mises. Code_Aster's `SIEQ_NOEU` von Mises is the average over the elements round a node of each
element's own value there - not the von Mises of the averaged stress, which differs by 5.6 % on that
bar - and fastcae averages the same way. A rigid coupling's reaction appears in Code_Aster's
`REAC_NODA` on the coupled nodes, not on its held reference node.

MED stores a tetrahedron's nodes the other way round from Code_Aster's own format (second and third
corners swapped, mid-side nodes with them); the reader permutes them.
