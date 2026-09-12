# Rib sections
when: the words ask for flat, T-shaped, tapered or flanged ribs, or a thickness

- A rib is flat - a plain web - or a T - the web with a flange along its free edge.
- "T-shaped ribs": the block's `section` setting fixed at T. "Flat and T-shaped": `section` with
  both as options, so designs are made of each. "Also T-shaped" for ribs already there: add T to
  that block's options; the flat ones stay.
- The flange's width and thickness are read off the part - in thicknesses of the web - unless the
  words give them: `flange_width_mm`, `flange_thickness_mm`.
- A thickness given is the web's: `thickness_mm`. The root fillet and edge round follow from it
  unless given.
- A taper is not built yet: write it as a setting named for it, kept and listed as not used, and
  say so in an attention line.
