"""The field's cells, prepared for drawing.

A solid cell has six faces and you can see at most three of them; on the skin of a casting almost
every cell shows one. Drawing a whole cube each is therefore about six times the work for the same
picture - forty-eight million vertices a frame on the part in ``assets/`` at 2.5 mm, which no
browser will do sixty times a second.

So what goes to the renderer is the **exposed faces**: a solid cell face whose neighbour is not
solid. Ten point eight million vertices for the same 2.5 mm field, which is what the contour of it
costs, and that draws fine.

Each face is a single 32-bit integer - the cell's flat index and which way the face points - and
the grid it indexes into travels once as a uniform. That is four bytes per face against twelve for
a position, so the payload halves as well.

Deliberately not part of what a stored field depends on. How the cells are drawn cannot change what
they are, so changing this must not throw away minutes of sampling.
"""

from __future__ import annotations

import numpy as np

# Face direction, packed into the low three bits: axis * 2, plus one when it points the other way.
# The renderer decodes the same way, and the two must agree - so the order is stated once, here.
DIRECTIONS = ((0, 1), (0, -1), (1, 1), (1, -1), (2, 1), (2, -1))


def exposed_faces(inside: np.ndarray) -> np.ndarray:
    """Every solid cell face that touches something that is not solid.

    Returns one ``uint32`` per face: ``cell_index << 3 | direction``. The shift is by three rather
    than a multiply by six so the renderer can decode with a shift and a mask.
    """
    shape = inside.shape
    packed: list[np.ndarray] = []

    for direction, (axis, side) in enumerate(DIRECTIONS):
        lower: list[slice] = [slice(None)] * 3
        upper: list[slice] = [slice(None)] * 3
        lower[axis] = slice(None, -1)
        upper[axis] = slice(1, None)
        near, far = inside[tuple(lower)], inside[tuple(upper)]

        # Looking along +axis, the cell that shows a face is the nearer one; looking back along it,
        # the further one.
        exposed = (near & ~far) if side > 0 else (far & ~near)
        if not exposed.any():
            continue

        coordinates = list(np.nonzero(exposed))
        if side < 0:
            # Those coordinates are in the slice that starts one cell along.
            coordinates[axis] = coordinates[axis] + 1

        flat = np.ravel_multi_index(tuple(coordinates), shape).astype(np.uint32)
        packed.append((flat << np.uint32(3)) | np.uint32(direction))

    if not packed:
        return np.zeros(0, dtype=np.uint32)
    return np.concatenate(packed)
