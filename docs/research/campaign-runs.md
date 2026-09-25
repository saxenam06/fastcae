# A campaign's designs, solved unattended

What happened when the runner first took a campaign's designs through the whole route - built,
meshed, given the deck's setup, solved and recorded, two or three at a time - on the GRC housing,
September 2026, on this workstation (RTX 5060 Laptop 8 GB, 15.7 GB RAM, WSL with 12 GB). The route
itself is [../simulate.md](../simulate.md); the baseline it is checked against,
[baseline-deck.md](baseline-deck.md).

## What the first unattended run found

Twenty designs of a campaign, three at a time. None came out solved, for four reasons - each fixed:

- **Memory freed on the card stayed in pools.** CuPy keeps what its arrays free for reuse, and Warp,
  which builds a design's distances, keeps its own; cuDSS allocates outside both. After a few builds a
  solve ran out of memory nothing was using, and every build after it failed to find 15 MB. Now
  every build and solve hands the card back when done, and a failed cuDSS solve is tried once more
  after that before Code_Aster is called.
- **The runner committed 17.8 GB** through that cascade, three designs in flight, until the machine
  had 0.1 GB free. One design at a time, a design adds nothing after the first: 3.7 GB after one, 4.1
  GB after six. A design now waits to start while the runner holds more than 60 % of the machine's
  memory.
- **Windows' 260 characters.** Zarr writes each array through a temporary name 45 characters long;
  in a deep folder a solved design's store failed to write. Stores are written in a short temporary
  folder and moved into place whole.
- **The Code_Aster fallback ran past 15 minutes** on one design and was stopped by its limit. Its
  own log says why: the solve took 779 s, of which 301 s was the system's - memory, not arithmetic -
  where the baseline deck's, the same size at the same 6.4 GB peak, took 111 s with 21 s of the
  system's. The machine had 0.1 GB free: Code_Aster in WSL was starved by the runner's cascade. It
  now runs one at a time, and no design starts while it runs. On a machine with room it re-solved a
  design cuDSS had solved - 1.30 M unknowns, the same mesh and setup rebuilt from its record - in
  192 s, every seat's tilt the same to 10⁻⁷ and the displacement to 1.6·10⁻⁷, the precision a record
  keeps it in.

## The unattended run

A campaign of 40 designs of seven variants (three of ribs at 12 mm, three of webs, one of holes),
launched from its card - 40 kept of 48 tried, 41 s. Six solved one at a time first, to watch memory;
then the runner took the other 34, three at a time, unattended:

| | |
|---|---|
| Solved | 33 of 34 - with the six before, 39 of the campaign's 40 |
| Set aside | 1 - by one of the build's own casting checks: a 12 mm finger of sand between a rib's end and the metal ahead of it |
| Run | 18 min 40 s: **106 designs an hour**; a design 98 s from start to record, typically (38-161 s) |
| Stages, median | build 25 s · mesh 19 s · setup 1.3 s · solve 40 s (waiting for the card included) · record 1.9 s |
| Route | every one CGAL → cuDSS; no mesh needed a second start, no solve needed Code_Aster |
| Meshes | 1.15-1.47 M unknowns; no element below quality 0.1 (worst 0.14) |
| Solves | residual at most 4.2·10⁻¹⁰ |
| Memory | the runner at 4.5-12.2 GB, the most during a solve, whose factor spills to host memory; a design waited to start twice |
| Records | 40 JSON records, 39 Zarr stores (all finite, the peak stress on the surface), one Parquet table of 40 rows by 93 columns; 1.2 GB |

The answers spread as far as the designs do: largest displacement 0.66-22.5 mm, BORE_MAIN_S2's tilt
2.9'-87.4', p99.9 von Mises 113-882 MPa, 872-893 kg. A design without ribs near the main seat keeps
the baseline's answer there - one with two ribs elsewhere gave 22.36 mm and 86.55' against the deck's
22.32 mm and 86.49'.

## Two rules pinch rib thickness on this housing

With floors no longer thickened for ribs, a rib stands on a floor only when it is at most 0.8 of the
floor's thickness plus 0.5 mm; and the design's field must hold at least four cells across a rib - 12
mm on the 3 mm grid designs are built on. On the housing's 15 mm floors only 12 mm ribs pass both.
The campaigns made before the change had 20 mm ribs: rebuilt, 37 of 40 of their designs were
rejected by their own rules (two variants placing no rib at all), and a new campaign of them was
refused at launch - "variant xsaap makes nothing at any of the 128 points tried alone". At 10 mm
every rib design was rejected for the grid. The scratch campaign solved here holds its rib variants
at 12 mm. How a variant's rib thickness should follow the floor it stands on is the engineer's call
(the build plan's open item).
