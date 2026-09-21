# Simulate

How fastcae takes the engineer's own solver deck and results for the baseline, solves the same deck
again before anything is built on it, and carries the same setup to every design - each design its
own CAD, meshed face by face with the recipe the baseline's mesh is made with.
[status.md](status.md) says how much of it runs; the measurements behind it are in
[research/field-meshing-gate.md](research/field-meshing-gate.md), [research/solver-choice.md](research/solver-choice.md)
and [research/design-to-solution.md](research/design-to-solution.md).

---

## What the engineer brings

The baseline's CAD and drawing, and **the solver deck they already trust with the answer it gave**:
for Code_Aster, the `.export` that names the rest, the command file (`.comm`), the mesh (MED), and
what the run wrote back - the results (`.rmed`), the tables its commands print, the message log. They
go in the project folder beside the CAD; Extract reads them.

The deck says what the analysis is: the mesh and its named groups, the material, what is held, the
couplings, the loads, what is read off the answer. Nothing about the part's physics is assumed - a
bore is called what the deck calls it, a signal what the deck asks for. A project without a deck is
still a project: its CAD opens, the design space is defined from the geometry and the drawing
alone, and the views that need the deck say it is not provided.

On Input, **Mesh & setup** shows the deck: *Setup* draws the mesh with every support, coupling and
load where the deck puts it, under the deck's own names; *Solve results* draws the deck solved as
contours, with the signals the deck asks for - the engineer's Code_Aster run and cuDSS on the same
mesh as two tabs under the picture, cuDSS solved on the runner at a click. What the deck holds - groups, supports, couplings,
loads, material, signals, fields - is listed by the pipeline's Read stage as typed entities
([pipeline.md](pipeline.md)).

## Reading a deck

**Commands are read, never run.** A `.comm` file is Python; running an engineer's file to learn what
it says would run whatever else it says too. It is parsed instead, each keyword read as a literal -
numbers, strings, tuples, `_F(...)` groups - and a name assigned earlier as a reference to that
command's result. What is not a literal (a loop, a computed list) is reported as not read.

**What is understood** becomes a setup in words that do not depend on the solver, each item keeping
the deck's names - the group it acts on, the load set it belongs to:

| deck | setup |
|---|---|
| `DEFI_MATERIAU(ELAS=...)`, `AFFE_MATERIAU` | a linear-elastic material on cell groups |
| `DDL_IMPO`, `AFFE_CHAR_CINE(MECA_IMPO)` | degrees of freedom held |
| `LIAISON_SOLIDE` | a rigid coupling; the single-node group among its groups is its reference |
| `LIAISON_RBE3` | a distributing coupling: reference, group, weights |
| `FORCE_NODALE`, `FORCE_FACE`, `PRES_REP` | loads |
| `MECA_STATIQUE(EXCIT=...)` | a linear static analysis and the load sets it applies |
| `POST_RELEVE_T(ACTION=...)` | the signals, under the deck's `INTITULE` |

Every other command and keyword is listed as not interpreted, so what the deck asks for and what
fastcae solves can be told apart. The MED mesh is read with its groups; MED numbers a tetrahedron's
nodes the other way round from Code_Aster's own format, and they are permuted on the way in.

**Tied to the CAD.** Every group a support, coupling or load acts on is matched to the CAD faces its
triangles lie on; single-node groups keep their coordinates as reference points. This is what lets
the setup be carried to a mesh the deck never saw.

## Imported, derived, generated

Everything on screen says where it came from:

- **imported** - read from the engineer's files as they are: the mesh, the groups, the setup, the
  results;
- **derived** - computed by fastcae from those files without solving: the mesh's outside, which CAD
  faces a group lies on, a coupling's tilt, a percentile;
- **generated** - meshed or solved by fastcae, each saying how.

## Solved again

Before a design is trusted to fastcae, fastcae solves the deck's own question and sets its answer
beside the engineer's: the *cuDSS* tab of Solve results, solved on the runner.

- **The same mesh, solved by cuDSS.** The deck's mesh and setup, assembled as quadratic tetrahedra
  on the GPU and factorised by cuDSS - part of its factor in host memory when the card is short.
  Held degrees of freedom are taken out; a rigid coupling makes its nodes one body moving with its
  reference; a distributing coupling's load is spread over its nodes so force and moment balance,
  and its reference's motion read as their weighted best fit. Stress is taken at every node of every
  element and averaged round each node, von Mises likewise - as Code_Aster's `SIEQ_NOEU` is.

**The reproduction certificate** compares quantity by quantity, never with one score: the applied
load, the reactions and what is left unbalanced, the work of the loads, the largest displacement, the
displacement and stress fields node by node on the same mesh, the stress percentiles, each coupling's
tilt and the deck's own signals - each with the tolerance it is held to. On the same mesh every
quantity is held to a millionth; on a mesh of its own, to what meshing the same shape twice was
measured to move. The certificate names both solvers and their versions.

The GRC housing's baseline deck is meshed face by face (`src/fastcae/simulate/face_mesh.py`, 274,204
second-order tets, 1.44 M unknowns) - the recipe every design is meshed with. Code_Aster solved it in
196 s; cuDSS on the same mesh agrees to about 10⁻¹⁰ on the fields in 30 s, and a fresh face-by-face
mesh of the same CAD with the deck carried onto it by CAD face reproduces the deck node for node
([research/baseline-deck.md](research/baseline-deck.md)).

Views: the answers as banded contours (48 bands, agenticCAE's colours, over the true range - a
legend that stops short of the real maximum disagrees with the number beside it), side by side with
one camera, or as their difference; on the deformed shape; element edges on or off.

## What a design takes

Every design is its own CAD: the baseline's STEP with the design's rib solids fused into it - never
a field, a shell or cells. It is meshed face by face, TET10, by the recipe the baseline's deck mesh
is made with, so its bores stay round and its edges crisp; the deck's setup is carried by the CAD
faces its groups lie on - supports, couplings, loads and signals unchanged - and it is solved by
cuDSS. A design whose fuse or mesh fails is rejected with its reason; there is no mesh-only
fallback ([designs.md](designs.md)). What a design inherits and what fastcae makes is listed item by item:
geometry built for each design and its mesh made by fastcae; the material, supports, couplings,
loads, analysis and signals the deck's.

## The runner

Everything that takes longer than a click runs outside the development server, in a process of its
own (`python -m fastcae.runner`), so a server reload does not stop it: solving the deck again, and
making a campaign's designs. Jobs are folders under `_archived_designs/_runner/jobs/` - what to do,
how far it has got, what happened - and survive the runner stopping. One GPU job at a time; meshing
runs in WSL beside it. Code_Aster and the mesher are stopped on Linux's side if they run past a
quarter of an hour: every run of a part this size has finished in minutes.
