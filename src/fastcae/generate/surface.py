"""Turning a field back into a surface, for the things that need one.

Solving does not. An immersed solve asks the field how full each cell is and never sees a triangle.
What needs a surface is checking it (volume, area and watertightness are measured on one), handing
it over (export, or a body-fitted mesh for a reference solver), and **selecting on it** - authoring
a parameter means clicking a face, and picking runs against triangles carrying CAD face ids.

**Dual contouring**, not marching cubes. Marching cubes places vertices only on cell edges, so it
cannot represent a corner inside a cell and rounds every machined edge off to the voxel. On a
casting whose character is crisp machined faces against soft cast ones, that erases the distinction
the part is about. Dual contouring puts one vertex per cell, positioned where the surface's own
tangent planes intersect, and reproduces an edge exactly.

**A vertex per piece of surface, not per cell.** A cell the surface passes through twice - two thin
walls meeting at a diagonal, two sheets a voxel apart - holds two separate pieces, and one vertex
shared between them puts four triangles on an edge. Each cell's corner signs decide how many pieces
it holds and which crossed edges belong to which.

**A face whose corners alternate is never crossed directly.** It carries two stretches of surface,
and joining the cells either side of it straight across would put both stretches on one edge. Each
stretch gets its own vertex on the face instead, and the quads through it become small polygons
fanned around their centres. A rule that reads only the face, so both cells agree on it; on 400
random solids built to hit every such face, it left no edge in more than two triangles.

**Only what changed.** Every vertex depends on its own cell's eight samples and every quad on the
four cells around one lattice edge, so a design that changed some samples changes only the vertices
and quads that touch them. Everything is ordered by a key - a vertex by its cell and piece, a quad
by its lattice edge - so a window re-contoured on the same grid drops back in by key. Nothing is
joined, and the result is byte-for-byte what contouring the whole field would give; the tests
hold it to exactly that.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .. import cache
from ..geometry.health import edge_faults
from .field import CODE as FIELD_CODE
from .field import Field

# What a stored contour depends on. The field it came from is already named by the key, so this is
# only the code that turns one into triangles.
CODE = (*FIELD_CODE, "generate/surface.py")

# The eight corners of a cell, as offsets in the sample lattice.
#
# Ordered so that corner ``c`` is ``(c >> 2, (c >> 1) & 1, c & 1)`` - x-major, exactly what
# ``reshape(-1, 2, 2, 2)`` produces. The gradient below indexes the reshaped array as [x][y][z],
# and any other corner order silently permutes the axes: normals come out with two components
# exchanged, which leaves the surface closed and moves vertices by up to a voxel.
_CORNERS = np.array(
    [
        [0, 0, 0],
        [0, 0, 1],
        [0, 1, 0],
        [0, 1, 1],
        [1, 0, 0],
        [1, 0, 1],
        [1, 1, 0],
        [1, 1, 1],
    ],
    dtype=np.int64,
)

# The twelve edges of a cell, as pairs of corner indices into _CORNERS.
_EDGES = np.array(
    [
        [0, 4],
        [1, 5],
        [2, 6],
        [3, 7],  # along x
        [0, 2],
        [1, 3],
        [4, 6],
        [5, 7],  # along y
        [0, 1],
        [2, 3],
        [4, 5],
        [6, 7],  # along z
    ],
    dtype=np.int64,
)

# How strongly the cell's own centre pulls the vertex when the tangent planes do not pin it down.
#
# A flat region constrains the vertex along one direction only, and a straight edge along two; the
# rest is free, and without a bias the solve wanders off to wherever the residual happens to be
# flattest. Small enough not to round a genuine corner, large enough that the system is never
# singular.
QEF_REGULARISATION = 0.02

# Cells whose vertices are solved at once.
#
# The solve materialises twelve crossings and twelve normals per cell, so memory scales with the
# number of active cells and nothing else bounds it. Unchunked, a 2.4 mm field on the part in
# ``assets/`` asked for several gigabytes of intermediates, and a machine that has to swap for them
# turns half a minute of arithmetic into hours. This makes the footprint independent of resolution.
CELL_CHUNK = 200_000


# Vertex keys. Every vertex is owned by one cell and sits in one of that cell's slots, and its key
# is ``cell * SLOTS + slot``. Sorted keys are the vertex order, which is what lets part of a
# surface be re-contoured and dropped back in by key.
#
#   0 .. 7    the pieces of surface inside the cell (at most four occur)
#   8 .. 13   the cell's upper faces, where a face's corners alternate: 8 + 2 * normal + which
#             of its two solid corners the surface cuts off
#   16 .. 18  the centre of the lattice edge starting at the cell's first corner: 16 + axis
SLOTS = 32
_FACE_SLOT = 8
_CENTRE_SLOT = 16

# The six faces of a cell, each as its four corners in order around it.
_FACES = ((0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5))


def _piece_table() -> tuple[np.ndarray, np.ndarray]:
    """For each of the 256 sign patterns of a cell, which piece of surface each edge belongs to.

    Two crossed edges on one face belong to the same piece: the surface enters the face through
    one and leaves through the other. A face with four crossed edges has its corners alternating;
    its two solid corners are kept apart, each cut off by its own stretch of surface. The rule
    reads only that face's four corners, so both cells sharing the face apply it identically.
    """
    edge_of = {frozenset((int(a), int(b))): i for i, (a, b) in enumerate(_EDGES)}
    rings = [
        [edge_of[frozenset((face[i], face[(i + 1) % 4]))] for i in range(4)] for face in _FACES
    ]
    pieces = np.full((256, 12), -1, dtype=np.int8)
    counts = np.zeros(256, dtype=np.int8)
    for pattern in range(256):
        solid = [(pattern >> c) & 1 for c in range(8)]
        crossed = [solid[a] != solid[b] for a, b in _EDGES]
        parent = list(range(12))

        def find(x: int, parent: list[int] = parent) -> int:
            while parent[x] != x:
                x = parent[x]
            return x

        for face, ring in zip(_FACES, rings, strict=True):
            hit = [e for e in ring if crossed[e]]
            if len(hit) == 2:
                parent[find(hit[0])] = find(hit[1])
            elif len(hit) == 4:
                for i in range(4):
                    if solid[face[i]]:
                        parent[find(ring[i - 1])] = find(ring[i])

        label: dict[int, int] = {}
        for e in range(12):
            if crossed[e]:
                pieces[pattern, e] = label.setdefault(find(e), len(label))
        counts[pattern] = len(label)
    assert counts.max() < _FACE_SLOT
    return pieces, counts


_PIECES, _PIECE_COUNTS = _piece_table()

# For a lattice edge along each axis: the four cells around it, as offsets from the edge's first
# sample, and which of each cell's twelve edges it is.
#
# The order has to circle the edge right-handedly, so that a quad taken in this order has its
# normal along the axis. The pairs are (y, z) about x, **(z, x) about y** and (x, y) about z - and
# getting the middle one backwards, as (x, z), silently reverses every quad on a y edge. That is a
# third of the surface: it leaves the mesh closed and manifold, so only the winding count catches
# it, and the volume comes out wrong by cancellation rather than by being absurd.
_AROUND = {
    0: ((0, -1, -1), (0, 0, -1), (0, 0, 0), (0, -1, 0)),
    1: ((-1, 0, -1), (-1, 0, 0), (0, 0, 0), (0, 0, -1)),
    2: ((-1, -1, 0), (0, -1, 0), (0, 0, 0), (-1, 0, 0)),
}
_LOCAL_EDGE = {
    0: tuple(2 * -dy + -dz for _, dy, dz in _AROUND[0]),
    1: tuple(4 + 2 * -dx + -dz for dx, _, dz in _AROUND[1]),
    2: tuple(8 + 2 * -dx + -dy for dx, dy, _ in _AROUND[2]),
}


@dataclass
class Surface:
    """A triangle surface contoured out of a field.

    Deliberately the same three arrays a :class:`~fastcae.geometry.brep.Tessellation` carries -
    vertices, triangles and a CAD face id per triangle - so everything already built to draw, pick
    and measure one works on this unchanged.
    """

    vertices: np.ndarray
    triangles: np.ndarray
    face_id: np.ndarray
    spacing_mm: float

    volume_mm3: float = 0.0
    area_mm2: float = 0.0
    faults: tuple[int, int, int] = (0, 0, 0)
    """Boundary, non-manifold and winding faults - the same gate the B-rep surface passes.

    Measured once, when the surface is built, and stored with it. Counting edges on three and a
    half million triangles is a sort, and recomputing it to answer "is this closed" made a cached
    contour take twelve seconds to describe itself.
    """

    vertex_key: np.ndarray | None = None
    """Each vertex's key, ascending - see ``SLOTS``. What a re-contour matches vertices by."""

    triangle_edge: np.ndarray | None = None
    """The lattice edge each triangle's quad sits on, ``axis * samples + first sample``, ascending.
    What a re-contour matches triangles by."""

    @property
    def n_vertices(self) -> int:
        return int(self.vertices.shape[0])

    @property
    def n_triangles(self) -> int:
        return int(self.triangles.shape[0])

    @property
    def watertight(self) -> bool:
        return self.faults == (0, 0, 0)


def contour(field: Field, face_ids_from: object | None = None) -> Surface:
    """Extract the zero level set of a field as a closed triangle surface.

    ``face_ids_from`` is the tessellation the field was built from. Given one, every contoured
    triangle inherits the CAD face id nearest its centroid, so picking, the selection tools and the
    controlled-face highlighting keep working on a generated design. Without one, every triangle
    carries face 0 and the surface is for looking at only.
    """
    cells = _active_cells(field)
    if not cells.size:
        raise ValueError("the field has no surface in it - nothing changes sign")

    cell_key, cell_position = _vertices_for(field, cells)
    tri_keys, tri_edge, extra_key, extra_position = _quads_for(
        field, _crossed_edges(field), cell_key, cell_position
    )
    vertex_key, vertices = _merge_vertices(cell_key, cell_position, extra_key, extra_position)
    triangles = _index(vertex_key, tri_keys)
    face_id = _nearest_face(vertices, triangles, face_ids_from, field.grid.spacing_mm)
    return _surface(field, vertices, triangles, face_id, vertex_key, tri_edge)


def recontour(
    base: Surface, field: Field, changed: np.ndarray, face_ids_from: object | None = None
) -> Surface:
    """``base`` updated to ``field``, re-contouring only what the ``changed`` samples reach.

    ``base`` must have been contoured from a field on the same grid that differs from ``field``
    only at ``changed``. The cells with a changed corner get their vertices again; the lattice
    edges of those cells get their quads again; everything else is carried over by key. The
    result is exactly :func:`contour` of ``field``, and the tests hold it to that.
    """
    if base.vertex_key is None or base.triangle_edge is None:
        raise ValueError("this surface carries no keys to splice by; contour it again")

    reached = _cells_touching(field, np.asarray(changed, dtype=np.int64))

    # Cell vertices: the reached cells' are placed again, everyone else's are carried over.
    base_slot = base.vertex_key % SLOTS
    carried = (base_slot < _FACE_SLOT) & ~np.isin(base.vertex_key // SLOTS, reached)
    new_key, new_position = _vertices_for(field, reached)
    cell_key = np.concatenate([base.vertex_key[carried], new_key])
    cell_position = np.concatenate([base.vertices[carried], new_position])
    order = np.argsort(cell_key, kind="stable")
    cell_key, cell_position = cell_key[order], cell_position[order]

    # Quads: those on the reached cells' edges are built again, the rest carried over.
    edges = _edges_of(field, reached)
    kept = ~np.isin(base.triangle_edge, edges)
    kept_keys = base.vertex_key[base.triangles[kept]]
    new_keys, new_edge, extra_key, extra_position = _quads_for(
        field, edges, cell_key, cell_position
    )

    # Vertices on faces and at quad centres belong to the quads that use them.
    used = np.unique(kept_keys[kept_keys % SLOTS >= _FACE_SLOT])
    where = np.searchsorted(base.vertex_key, used)
    extra_key = np.concatenate([used, extra_key])
    extra_position = np.concatenate([base.vertices[where], extra_position])
    vertex_key, vertices = _merge_vertices(cell_key, cell_position, extra_key, extra_position)

    tri_edge = np.concatenate([base.triangle_edge[kept], new_edge])
    tri_keys = np.concatenate([kept_keys, new_keys])
    face_id = np.concatenate([base.face_id[kept], np.full(new_edge.size, -1, dtype=np.int32)])
    order = np.argsort(tri_edge, kind="stable")
    tri_edge, tri_keys, face_id = tri_edge[order], tri_keys[order], face_id[order]

    triangles = _index(vertex_key, tri_keys)
    fresh = face_id < 0
    face_id[fresh] = _nearest_face(vertices, triangles[fresh], face_ids_from, field.grid.spacing_mm)
    return _surface(field, vertices, triangles, face_id, vertex_key, tri_edge)


def changed_samples(before: Field, after: Field) -> np.ndarray:
    """Flat indices of the samples whose sign or stored distance differs between two fields."""
    if before.grid != after.grid:
        raise ValueError("the two fields were not sampled on the same grid")
    band = np.union1d(before.band_index, after.band_index)
    moved = band[before.at(band) != after.at(band)]
    flipped = np.flatnonzero(before.inside.ravel() != after.inside.ravel())
    return np.union1d(moved, flipped).astype(np.int64)


def _surface(
    field: Field,
    vertices: np.ndarray,
    triangles: np.ndarray,
    face_id: np.ndarray,
    vertex_key: np.ndarray,
    triangle_edge: np.ndarray,
) -> Surface:
    a = vertices[triangles[:, 0]]
    b = vertices[triangles[:, 1]]
    c = vertices[triangles[:, 2]]
    return Surface(
        vertices=vertices,
        triangles=triangles,
        face_id=face_id,
        spacing_mm=field.grid.spacing_mm,
        volume_mm3=float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0),
        area_mm2=float(np.linalg.norm(np.cross(b - a, c - a), axis=1).sum() / 2.0),
        faults=edge_faults(triangles),
        vertex_key=vertex_key,
        triangle_edge=triangle_edge,
    )


def surface_for(
    root: Path,
    field: Field,
    field_key: str,
    face_ids_from: object | None = None,
    reuse: bool = True,
) -> tuple[Surface, bool]:
    """The contour of one field, built once and kept.

    Contouring is not free - half a minute on a two-metre casting at a fine voxel - and it is
    completely determined by the field and this module. Paying it on every restart made the field
    cache look broken when it was working perfectly.
    """
    item = cache.entry(root, "surface", cache.key_for(field_key, code=CODE))
    return cache.memoise(item, lambda: contour(field, face_ids_from=face_ids_from), reuse=reuse)


def _cell_shape(field: Field) -> tuple[int, int, int]:
    nx, ny, nz = field.grid.shape
    return (nx - 1, ny - 1, nz - 1)


def _active_cells(field: Field) -> np.ndarray:
    """Cells whose eight corners are not all on one side.

    Found from the sign array alone, which is a byte per cell rather than a float, so the dense
    float grid a naive implementation would build - 298 MB on the part in ``assets/`` at 2.5 mm -
    is never needed. Only the corners that matter are then looked up.
    """
    nx, ny, nz = field.grid.shape
    inside = field.inside
    corners = [
        inside[dx : dx + nx - 1, dy : dy + ny - 1, dz : dz + nz - 1] for dx, dy, dz in _CORNERS
    ]
    any_solid = np.logical_or.reduce(corners)
    all_solid = np.logical_and.reduce(corners)
    return np.flatnonzero((any_solid & ~all_solid).ravel()).astype(np.int64)


def _patterns(field: Field, cell: np.ndarray) -> np.ndarray:
    """Each cell's sign pattern: bit ``c`` set where corner ``c`` is solid."""
    corners = (cell[:, None, :] + _CORNERS[None, :, :]).reshape(-1, 3)
    solid = field.inside[corners[:, 0], corners[:, 1], corners[:, 2]].reshape(-1, 8)
    return (solid.astype(np.int64) << np.arange(8)).sum(axis=1)


def _vertices_for(field: Field, cells: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Keys and positions of the vertices in the given cells, ascending by key.

    One vertex per piece of surface in each cell, where that piece's own tangent planes meet. Each
    crossed edge gives a point on the surface and a normal there, and the vertex is the
    least-squares intersection of those planes. On a flat region that is the plane itself; on a
    machined edge the two planes pin the vertex onto the crease; at a corner three planes fix it
    exactly. This is the whole reason for dual contouring over marching cubes.

    Normals come from the trilinear gradient of the cell, evaluated at each crossing rather than
    once per cell. A single normal per cell would make every plane parallel and leave the vertex
    free to slide along the surface, which is how a sharp edge gets rounded off.
    """
    cells = np.unique(np.asarray(cells, dtype=np.int64))
    cell = np.stack(np.unravel_index(cells, _cell_shape(field)), axis=1)
    pattern = _patterns(field, cell)
    count = _PIECE_COUNTS[pattern].astype(np.int64)
    owner = np.repeat(np.arange(cells.size), count)
    piece = np.arange(owner.size) - np.repeat(np.cumsum(count) - count, count)
    keys = cells[owner] * SLOTS + piece
    if not owner.size:
        return keys, np.empty((0, 3), dtype=np.float64)

    corner_flat = np.ravel_multi_index(
        (cell[:, None, :] + _CORNERS[None, :, :]).reshape(-1, 3).T, field.grid.shape
    )
    values = field.at(corner_flat).reshape(-1, 8)

    spacing = field.grid.spacing_mm
    origin = np.asarray(field.grid.origin)
    out = np.empty((owner.size, 3), dtype=np.float64)
    for start in range(0, owner.size, CELL_CHUNK):
        stop = min(start + CELL_CHUNK, owner.size)
        who = owner[start:stop]
        crosses = _PIECES[pattern[who]] == piece[start:stop, None]
        out[start:stop] = _solve_chunk(values[who], cell[who], crosses, spacing, origin)
    return keys, out


def _solve_chunk(
    values: np.ndarray, cell: np.ndarray, crosses: np.ndarray, spacing: float, origin: np.ndarray
) -> np.ndarray:
    lower = values[:, _EDGES[:, 0]]
    upper = values[:, _EDGES[:, 1]]

    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(lower != upper, lower / (lower - upper), 0.5)
    t = np.clip(t, 0.0, 1.0)

    start = _CORNERS[_EDGES[:, 0]].astype(np.float64)
    direction = (_CORNERS[_EDGES[:, 1]] - _CORNERS[_EDGES[:, 0]]).astype(np.float64)
    points = start[None, :, :] + t[:, :, None] * direction[None, :, :]

    normals = _trilinear_gradient(values, points)
    length = np.linalg.norm(normals, axis=2, keepdims=True)
    normals = np.divide(normals, length, out=np.zeros_like(normals), where=length > 1e-12)

    weight = crosses[:, :, None].astype(np.float64)
    n = normals * weight
    a = np.einsum("eij,eik->ejk", n, n)
    b = np.einsum("eij,ei->ej", n, np.einsum("eij,eij->ei", n, points))

    # Bias to the average of the crossings rather than the cell centre: on a thin feature the
    # centre can sit outside the material, and pulling towards it drags the surface off the part.
    count = np.maximum(crosses.sum(axis=1), 1)[:, None]
    centre = (points * weight).sum(axis=1) / count

    scale = np.trace(a, axis1=1, axis2=2)[:, None, None]
    lam = QEF_REGULARISATION * np.maximum(scale, 1e-9)
    a = a + lam * np.eye(3)[None, :, :]
    b = b + (lam[:, :, 0] * centre)

    local = np.linalg.solve(a, b[:, :, None])[:, :, 0]
    # A vertex belongs to its own cell. Clamping is what stops one bad solve from throwing a spike
    # across the model, and it costs nothing where the solve was already sound.
    local = np.clip(local, 0.0, 1.0)

    return (cell + local) * spacing + origin


def _trilinear_gradient(values: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Gradient of the trilinear interpolant of eight corner values, at points inside the cell.

    In cell coordinates, so it is a direction rather than a magnitude - which is all a plane needs.
    """
    v = values.reshape(-1, 2, 2, 2)  # indexed [x][y][z], matching _CORNERS
    u, w, z = points[:, :, 0], points[:, :, 1], points[:, :, 2]

    def edge(i0: int, j0: int, k0: int, i1: int, j1: int, k1: int) -> np.ndarray:
        return (v[:, i1, j1, k1] - v[:, i0, j0, k0])[:, None]

    gx = (
        edge(0, 0, 0, 1, 0, 0) * (1 - w) * (1 - z)
        + edge(0, 1, 0, 1, 1, 0) * w * (1 - z)
        + edge(0, 0, 1, 1, 0, 1) * (1 - w) * z
        + edge(0, 1, 1, 1, 1, 1) * w * z
    )
    gy = (
        edge(0, 0, 0, 0, 1, 0) * (1 - u) * (1 - z)
        + edge(1, 0, 0, 1, 1, 0) * u * (1 - z)
        + edge(0, 0, 1, 0, 1, 1) * (1 - u) * z
        + edge(1, 0, 1, 1, 1, 1) * u * z
    )
    gz = (
        edge(0, 0, 0, 0, 0, 1) * (1 - u) * (1 - w)
        + edge(1, 0, 0, 1, 0, 1) * u * (1 - w)
        + edge(0, 1, 0, 0, 1, 1) * (1 - u) * w
        + edge(1, 1, 0, 1, 1, 1) * u * w
    )
    return np.stack([gx, gy, gz], axis=2)


def _crossed_edges(field: Field) -> np.ndarray:
    """Keys of every interior lattice edge whose two samples differ in sign."""
    shape = field.grid.shape
    n = int(np.prod(shape))
    inside = field.inside
    out = []
    for axis in range(3):
        lo = _slice_along(inside, axis, 0, -1)
        hi = _slice_along(inside, axis, 1, None)
        index = np.stack(np.nonzero(lo != hi), axis=1)
        out.append(axis * n + np.ravel_multi_index(index.T, shape).astype(np.int64))
    return _interior(field, np.concatenate(out))


def _edges_of(field: Field, cells: np.ndarray) -> np.ndarray:
    """Keys of the twelve lattice edges of each of the given cells."""
    shape = field.grid.shape
    n = int(np.prod(shape))
    if not cells.size:
        return np.empty(0, dtype=np.int64)
    cell = np.stack(np.unravel_index(cells, _cell_shape(field)), axis=1)
    keys = []
    for axis in range(3):
        others = [a for a in range(3) if a != axis]
        for p in (0, 1):
            for q in (0, 1):
                start = cell.copy()
                start[:, others[0]] += p
                start[:, others[1]] += q
                keys.append(axis * n + np.ravel_multi_index(start.T, shape).astype(np.int64))
    return _interior(field, np.unique(np.concatenate(keys)))


def _interior(field: Field, keys: np.ndarray) -> np.ndarray:
    """The edge keys whose four surrounding cells all exist. Edges on the grid's rim have fewer."""
    shape = np.asarray(field.grid.shape)
    n = int(np.prod(shape))
    axis = keys // n
    coord = np.stack(np.unravel_index(keys % n, tuple(shape)), axis=1)
    ok = np.ones(keys.size, dtype=bool)
    for a in range(3):
        along = coord[:, a] <= shape[a] - 2
        across = (coord[:, a] >= 1) & (coord[:, a] <= shape[a] - 2)
        ok &= np.where(axis == a, along, across)
    return keys[ok]


def _quads_for(
    field: Field, edges: np.ndarray, cell_key: np.ndarray, cell_position: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Triangles on those of the given lattice edges that the surface crosses.

    Returns the triangles as vertex keys, the edge each belongs to, and the extra vertices they
    need beyond the cells' own. Ordered by edge key, and within an edge by construction.

    Every lattice edge that changes sign is crossed by the surface, and the four cells sharing it
    each hold the piece that edge belongs to - so those four vertices form a quad, wound by which
    end of the edge is solid. This is the dual of marching cubes: there, the surface passes through
    edges and vertices sit on them; here, vertices sit in cells and the edges say how to connect
    them.

    **Where a face's corners alternate**, the two cells either side of it are not joined straight
    across. That face carries two stretches of surface, and joining across it would put both
    stretches' quads on one edge - four triangles to an edge, which is exactly the fault this
    exists to prevent. Instead each stretch gets a vertex of its own on the face, between the two
    crossings it joins, and the quad becomes a polygon fanned around its centre. Rare on a real
    part, and the rule is local: it reads only the face.
    """
    shape = field.grid.shape
    n = int(np.prod(shape))
    cells = _cell_shape(field)
    inside = field.inside

    out_tri, out_edge, out_key, out_pos = [], [], [], []
    for axis in range(3):
        keys = edges[edges // n == axis]
        start = np.stack(np.unravel_index(keys % n, shape), axis=1)
        end = start.copy()
        end[:, axis] += 1
        first = inside[start[:, 0], start[:, 1], start[:, 2]]
        last = inside[end[:, 0], end[:, 1], end[:, 2]]
        crossed = first != last
        keys, start, first, last = keys[crossed], start[crossed], first[crossed], last[crossed]
        if not keys.size:
            continue

        ring = []
        for offset, local in zip(_AROUND[axis], _LOCAL_EDGE[axis], strict=True):
            cell = start + np.asarray(offset)
            piece = _PIECES[_patterns(field, cell), local].astype(np.int64)
            ring.append(np.ravel_multi_index(cell.T, cells).astype(np.int64) * SLOTS + piece)
        ring_keys = np.stack(ring, axis=1)

        faces = [
            _face_between(field, start, first, axis, _AROUND[axis][i], _AROUND[axis][(i + 1) % 4])
            for i in range(4)
        ]
        split = np.stack([f[0] for f in faces], axis=1)
        plain = ~split.any(axis=1)

        # The common case: four cells, one quad, two triangles.
        quad = np.where(last[plain, None], ring_keys[plain, ::-1], ring_keys[plain])
        tri = np.stack([quad[:, [0, 1, 2]], quad[:, [0, 2, 3]]], axis=1).reshape(-1, 3)
        out_tri.append(tri)
        out_edge.append(np.repeat(keys[plain], 2))

        # The rare case: a polygon through face vertices, fanned around its centre.
        for q in np.flatnonzero(~plain):
            polygon, positions = [], []
            for i in range(4):
                polygon.append(int(ring_keys[q, i]))
                positions.append(_position(cell_key, cell_position, int(ring_keys[q, i])))
                if split[q, i]:
                    polygon.append(int(faces[i][1][q]))
                    positions.append(faces[i][2][q])
                    out_key.append(int(faces[i][1][q]))
                    out_pos.append(faces[i][2][q])
            centre = int(ring_keys[q, 2] // SLOTS) * SLOTS + _CENTRE_SLOT + axis
            out_key.append(centre)
            out_pos.append(np.sum(positions, axis=0) / len(positions))
            if last[q]:
                polygon = polygon[::-1]
            size = len(polygon)
            tri = [(centre, polygon[i], polygon[(i + 1) % size]) for i in range(size)]
            out_tri.append(np.asarray(tri, dtype=np.int64))
            out_edge.append(np.full(len(tri), keys[q], dtype=np.int64))

    if not out_tri:
        empty = np.empty(0, dtype=np.int64)
        return np.empty((0, 3), dtype=np.int64), empty, empty, np.empty((0, 3))
    tri_edge = np.concatenate(out_edge)
    tri_keys = np.concatenate(out_tri).astype(np.int64)
    order = np.argsort(tri_edge, kind="stable")
    extra_key = np.asarray(out_key, dtype=np.int64)
    extra_pos = np.asarray(out_pos, dtype=np.float64).reshape(-1, 3)
    return tri_keys[order], tri_edge[order], extra_key, extra_pos


def _face_between(
    field: Field,
    start: np.ndarray,
    first: np.ndarray,
    axis: int,
    offset_a: tuple[int, int, int],
    offset_b: tuple[int, int, int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For each crossed edge, the face it shares with two consecutive cells around it.

    Returns whether that face's corners alternate, and where they do, the key and position of the
    vertex on the stretch of surface through this edge. That stretch cuts off the edge's solid end
    (solids are kept apart), and runs to the crossing on the face's other edge at that corner.
    """
    normal = next(k for k in range(3) if offset_a[k] != offset_b[k])
    across = 3 - axis - normal
    lower_cell = start + np.minimum(np.asarray(offset_a), np.asarray(offset_b))

    # The face's corners: the edge, and the edge beside it on the face.
    step = np.zeros(3, dtype=np.int64)
    step[across] = 1 if offset_a[across] == 0 else -1
    along = np.zeros(3, dtype=np.int64)
    along[axis] = 1
    p00, p10 = start, start + along
    p01, p11 = start + step, start + along + step
    inside = field.inside
    s00 = inside[p00[:, 0], p00[:, 1], p00[:, 2]]
    s10 = inside[p10[:, 0], p10[:, 1], p10[:, 2]]
    s01 = inside[p01[:, 0], p01[:, 1], p01[:, 2]]
    s11 = inside[p11[:, 0], p11[:, 1], p11[:, 2]]
    split = (s00 == s11) & (s01 == s10) & (s00 != s10)

    shape = field.grid.shape
    keys = np.zeros(start.shape[0], dtype=np.int64)
    positions = np.zeros((start.shape[0], 3), dtype=np.float64)
    if split.any():
        k = np.flatnonzero(split)
        cut = np.where(first[k, None], p00[k], p10[k])  # the edge's solid end
        other = np.where(first[k, None], p11[k], p01[k])  # the face's other solid corner
        beside = cut + step  # the corner next to it across the face
        cut_flat = np.ravel_multi_index(cut.T, shape)
        other_flat = np.ravel_multi_index(other.T, shape)
        slot = (cut_flat > other_flat).astype(np.int64)
        cell_flat = np.ravel_multi_index(lower_cell[k].T, _cell_shape(field)).astype(np.int64)
        keys[k] = cell_flat * SLOTS + _FACE_SLOT + 2 * normal + slot
        positions[k] = 0.5 * (
            _crossing(field, p00[k], p10[k]) + _crossing(field, *_ordered(cut, beside))
        )
    return split, keys, positions


def _ordered(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The two ends of each lattice edge, lower first, so a crossing is computed one way only."""
    swap = (b < a).any(axis=1)
    return np.where(swap[:, None], b, a), np.where(swap[:, None], a, b)


def _crossing(field: Field, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    """Where the surface crosses each lattice edge, from its lower sample to its upper one."""
    shape = field.grid.shape
    v0 = field.at(np.ravel_multi_index(lower.T, shape)).astype(np.float64)
    v1 = field.at(np.ravel_multi_index(upper.T, shape)).astype(np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(v0 != v1, v0 / (v0 - v1), 0.5)
    t = np.clip(t, 0.0, 1.0)[:, None]
    origin = np.asarray(field.grid.origin)
    spacing = field.grid.spacing_mm
    return (lower + t * (upper - lower)) * spacing + origin


def _position(keys: np.ndarray, positions: np.ndarray, key: int) -> np.ndarray:
    return positions[int(np.searchsorted(keys, key))]


def _merge_vertices(
    cell_key: np.ndarray, cell_position: np.ndarray, extra_key: np.ndarray, extra_pos: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Cell vertices and the face and centre vertices quads added, as one key-ordered set."""
    if extra_key.size:
        extra_key, first = np.unique(extra_key, return_index=True)
        extra_pos = extra_pos[first]
    keys = np.concatenate([cell_key, extra_key])
    positions = np.concatenate([cell_position, extra_pos.reshape(-1, 3)])
    order = np.argsort(keys, kind="stable")
    return keys[order], positions[order]


def _index(vertex_key: np.ndarray, tri_keys: np.ndarray) -> np.ndarray:
    """Triangles as indices into the vertices, from triangles as vertex keys."""
    index = np.searchsorted(vertex_key, tri_keys)
    if tri_keys.size:
        found = vertex_key[np.minimum(index, vertex_key.size - 1)]
        if not np.array_equal(found, tri_keys):
            raise AssertionError("a triangle refers to a vertex that was never placed")
    return index.astype(np.int32)


def _cells_touching(field: Field, samples: np.ndarray) -> np.ndarray:
    """Every cell that has one of the given samples as a corner."""
    if not samples.size:
        return np.empty(0, dtype=np.int64)
    cells = np.asarray(_cell_shape(field))
    point = np.stack(np.unravel_index(samples, field.grid.shape), axis=1)
    out = []
    for corner in _CORNERS:
        cell = point - corner
        ok = ((cell >= 0) & (cell < cells)).all(axis=1)
        out.append(np.ravel_multi_index(cell[ok].T, tuple(cells)).astype(np.int64))
    return np.unique(np.concatenate(out))


def _slice_along(array: np.ndarray, axis: int, start: int, stop: int | None) -> np.ndarray:
    index: list[slice] = [slice(None)] * 3
    index[axis] = slice(start, stop)
    return array[tuple(index)]


def _nearest_face(
    vertices: np.ndarray,
    triangles: np.ndarray,
    source: object | None,
    spacing_mm: float,
) -> np.ndarray:
    """Give every contoured triangle the CAD face id of the nearest point on the original surface.

    Without this a generated design is unclickable: picking, `grow`, `similar` and the
    controlled-face highlighting all key off the CAD face id, and a contour has none of its own.
    It is an association rather than a measurement, and it is used for selection only - never as
    evidence about the design.

    Nearest **point**, not nearest triangle centroid, and the difference is not subtle. A CAD
    tessellation is adaptive: it spends triangles on curvature and almost none on flat areas, so on
    the part in ``assets/`` edge lengths run from 2.3 mm to 374 mm. A large flat face is a handful
    of enormous triangles whose centroids sit hundreds of millimetres from most of their own area,
    and a contour triangle lying squarely on that face is nearer the centroid of some small
    triangle on a neighbour. Keyed on centroids, **half** the contour came back labelled with the
    wrong face - and it did not improve when the voxel was halved, because it was never a question
    of resolution.

    So the source is sampled to a density the association can resolve: every triangle contributes
    at least its own points, and a large one contributes enough that no part of it is unrepresented.
    The samples are deterministic, because a contour is cached and the same field must produce the
    same ids on any machine and on any day.
    """
    if source is None or triangles.size == 0:
        return np.zeros(max(triangles.shape[0], 0), dtype=np.int32)

    base = np.asarray(source.vertices)  # type: ignore[attr-defined]
    faces = np.asarray(source.triangles)  # type: ignore[attr-defined]
    face_id = np.asarray(source.face_id)  # type: ignore[attr-defined]

    tree, owner = _lookup(base, faces, face_id, spacing_mm)
    _, nearest = tree.query(vertices[triangles].mean(axis=1), k=1, workers=-1)
    return owner[nearest].astype(np.int32)


# Half the voxel: the association only has to resolve which face a contour triangle sits on, and
# the contour itself is built at the voxel. Finer buys little - a tenth of a percent per halving -
# and the cost is a kd-tree over the samples, paid once per field and then cached with it.
SAMPLE_FRACTION = 0.5
SAMPLE_LIMIT = 6_000_000


_LOOKUP: dict[tuple[int, int, float], tuple[object, np.ndarray]] = {}


def _lookup(
    vertices: np.ndarray, triangles: np.ndarray, face_id: np.ndarray, spacing_mm: float
) -> tuple[object, np.ndarray]:
    """The sample cloud and its tree, kept between contours.

    It depends on the tessellation and the voxel and on nothing else - not on the design - so every
    variant contoured against the same part reuses it. Without this, evaluating a parameter would
    rebuild a tree over millions of points each time a dial moved, which is most of the cost of a
    contour and all of it wasted.

    One entry, because the caller contours one part at a time and the arrays are large.
    """
    from scipy.spatial import cKDTree

    key = (id(vertices), int(triangles.shape[0]), float(spacing_mm))
    hit = _LOOKUP.get(key)
    if hit is None:
        points, owner = scatter(vertices, triangles, face_id, spacing_mm)
        _LOOKUP.clear()
        hit = (cKDTree(points), owner)
        _LOOKUP[key] = hit
    return hit


def scatter(
    vertices: np.ndarray, triangles: np.ndarray, face_id: np.ndarray, spacing_mm: float
) -> tuple[np.ndarray, np.ndarray]:
    """Points spread over a tessellation at roughly one per ``spacing_mm`` squared, and their faces.

    Area-proportional, so the adaptive tessellation is evened out: a triangle already smaller than
    the target contributes one point and a huge flat one contributes as many as it needs.
    """
    a = vertices[triangles[:, 0]]
    b = vertices[triangles[:, 1]]
    c = vertices[triangles[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)

    target = max(spacing_mm * SAMPLE_FRACTION, 1e-6)
    counts = np.maximum(1, np.ceil(area / (target * target)).astype(np.int64))
    if counts.sum() > SAMPLE_LIMIT:
        counts = np.maximum(1, counts * SAMPLE_LIMIT // counts.sum())

    index = np.repeat(np.arange(len(triangles)), counts)
    rng = np.random.default_rng(0)  # fixed: a cached contour must be reproducible
    u = rng.random(index.size)
    v = rng.random(index.size)
    folded = u + v > 1.0
    u[folded], v[folded] = 1.0 - u[folded], 1.0 - v[folded]

    points = a[index] + (b - a)[index] * u[:, None] + (c - a)[index] * v[:, None]
    return points, face_id[index]
