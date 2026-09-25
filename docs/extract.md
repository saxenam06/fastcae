# Extract

**This file describes the pipeline as it is now.** Superseded content is deleted, not annotated.

---

## Ten steps

Each declares the artifact kinds it needs. A step that cannot run reports `skipped` with the
reason; it is never silently absent.

| step | needs | produces |
|---|---|---|
| Discover artifacts | — | files classified by extension: CAD, drawing, solver deck, solver results |
| Read CAD | CAD | solid count, faces, volume, area, bbox, content digest, declared unit |
| Check geometry health | CAD | tessellation, watertightness, volume error |
| Measure every face | CAD | the atlas: type, area, axis, radius, adjacency, dihedrals, facing, visibility |
| Detect features | CAD | axes, bores, bosses, hole patterns, planar groups, fillets |
| Read drawing | Drawing | callouts, each citing a page and its literal text |
| Cross-check | CAD + Drawing | candidate associations, ambiguities, unresolved pairings |
| Read the solver deck | Solver deck | its mesh and groups, and its setup - material, what is held, couplings, loads, signals, analysis - with what was not read and anything that cannot solve (a reference point nothing ties) |
| Read the deck's answer | Solver results | the fields and tables the run wrote |
| Tie the deck's groups to the CAD | CAD + Solver deck | each group a support, coupling or load acts on as the CAD faces it lies on, and how far off |

A project with only CAD runs the CAD steps and reports `no Drawing in this project` and `no solver
deck in this project` on the rest. That is the whole test of whether this is a platform, and it
passes. A deck step that fails leaves the part's own steps standing: the CAD still opens.

How a deck is read - its commands parsed as data and never run - is in [simulate.md](simulate.md).

## The geometry gate

A closed surface uses every edge exactly twice, once in each direction. Anything else is one of
three faults, and the count says which: used once is a hole, more than twice is a non-manifold
junction, twice in the same direction is a flipped triangle.

The gate is here because these failures are **silent**. On a leaking surface, inside and outside
are undefined, and every number afterwards is confidently wrong. A failure raises rather than
warns.

Tessellation is OCC's `BRepMesh` rather than a mesher. A mesher must parametrise a face first, and
on real CAD that fails — gmsh cannot process the part in `assets/` at all, on any algorithm. A
mesher that loses faces leaves holes, and holes have to be bridged by geometry nobody modelled.

## Reading a drawing

`pypdf` extracts text per page; the parser turns it into callouts. Every callout carries the page
and the **literal string** it came from, which is what makes a reading checkable: anyone can search
the page for that string and judge it.

Recognised forms: toleranced limit pairs, counted callouts, thread specifications, datum letters,
geometric tolerance frames, notes, and the title block's default-tolerance rule.

**What it cannot do**, stated because everything downstream depends on it:

- It reads text, not geometry. No leader lines, no views, **no coordinates**.
- It cannot tell which dimension applies to which feature.
- On a drawing with no text layer it gets nothing, and says so.
- **The diameter symbol does not survive extraction.** Zero times out of 255 callouts on the
  drawing in `assets/` — the glyph lives in a symbol font that maps to nothing. So a bare number
  cannot be known to be a diameter.

That last point forces an inference, everywhere, and it is always cited rather than assumed.

A **counted** callout reads as a hole when it says `THRU`, when a diameter mark did survive, or
when it carries the counted-pair form of a hole with a counterbore. The basis is recorded on the
callout.

A **toleranced pair** says a size is controlled. It does not say the size is a diameter — a stacked
pair of limits is as likely to be a width, a depth or a position. Matching one to a bore is
therefore an inference too, recorded as `derived` evidence, and it caps the resulting fact's
confidence at 0.70.

## Associating a drawing with a model

**This is the weakest part of the system and the most important to understand.**

With no coordinates, size is all there is, and a size can belong to several features. So an
association is a **hypothesis**, and two rules decide whether it is worth acting on.

### Discrimination

The best candidate must be decisively better than the runner-up, not merely first past the post.
Separation must exceed half the matching tolerance. If a callout sits 0.00 mm from one feature and
0.50 mm from another, that is a reading; 0.40 and 0.50 is a coin toss.

Ranking is by **diameter, then area**. An earlier version ranked by area first, and a 20.0 callout
matched a Ø21.00 pattern of five holes while a Ø20.00 pattern of four sat within reach — the wrong
one won on size.

### Corroboration

Size and count agreeing is two independent quantities agreeing about one feature: an association.

Size agreeing while count disagrees is one agreeing and one dissenting, and **there is no way from
here to tell whether the count is wrong or whether these were never the same feature.** So the
doubt is recorded against the pairing, not the number, and nothing is marked controlled.

### The tolerance does not matter

Measured across the drawing in `assets/`, from 1 µm to 0.5 mm the answer is identical: three
associations, all at exactly zero error. The distances from each callout to its nearest pattern
are:

```
0.00  0.00  0.00  4.00  7.80  7.80  7.80  9.66  10.00  11.20  11.34  13.80  13.80  13.80  13.80
```

Nothing lies between 0.00 and 4.00. Drawing values and CAD nominals are either identical or nowhere
near each other, so the tolerance band is empty space and tuning it is theatre. It is kept tight
because that states what the rule actually requires.

### Where this stops

Resolving a pairing properly needs what text extraction cannot give: the callout's position on the
sheet, its leader line, and the view it belongs to. That is the boundary where a deterministic read
ends and either coordinate-aware PDF extraction or a visual pass begins.

## Where "controlled" comes from

Not from anybody's judgement typed into a file. A drawing that puts a **tolerance band** on a
dimension is stating the feature is controlled; a detected feature whose size matches is what it is
stating it about. Control is therefore derived from two artifacts agreeing, and every instance
cites a page and the text it was read from.

Only trustworthy claims contribute. An ambiguous or unresolved pairing is surfaced for a person
instead — freezing on weak evidence removes design freedom exactly as quietly as failing to freeze
removes correctness.
