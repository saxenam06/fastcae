"""Simulate: the baseline's solver deck read as the engineer wrote it, solved again, and carried to
every design.

The engineer brings the baseline's CAD, its drawing, and the deck they solve it with - the mesh,
the material, how it is held, what loads it, what they read off the answer - with that answer.
Everything here takes its names from those files: a group is called what the deck calls it, a
signal what the deck asks for. Nothing about any one part is written in this package.

- :mod:`fem` - a mesh as a deck carries it: nodes, cells by type, named groups; TET10 helpers.
- :mod:`med` - the MED files Code_Aster reads meshes from and writes results to.
- :mod:`aster` - Code_Aster's command files read and written, its tables, its runs.
- :mod:`setup` - what a deck asks for, in words that do not depend on the solver.
"""
