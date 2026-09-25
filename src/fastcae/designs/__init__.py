"""Designs made in the design space: where metal goes found on the voxel grid under each load mix,
read as rib plates, built as CAD fused into the part, meshed face by face and solved.

- :mod:`.optimise` - the material layout that carries a load mix best for a volume of metal.
- :mod:`.ribs` - that layout read as rib plates.
- :mod:`.cad` - the plates as solids fused into the part's CAD, written as STEP.
- :mod:`.solve` - the design's CAD meshed as the deck's mesh was, the deck carried onto it, solved.
"""
