"""The signed distance field: the representation a design is edited in.

A design does not edit geometry, it edits a **field sampled on a fixed grid**. Every variant is
therefore measured at the same points, so two designs differ because the design differs and never
because something was discretised differently in between. That is the whole reason for the
representation: remesh variance stops being small and starts being impossible.

**Narrow band.** Distance is stored only within a few voxels of the surface; beyond that a cell
carries a sign and nothing else. A dense field over the bounding box is never built and never
needs to be - on the part in ``assets/`` a dense 2.5 mm grid would be 78.5 M cells while the band
is 8.8 M, and the band is the only part any design touches.

**Built once.** Construction is expensive and completely determined by the CAD file, so it is keyed
on the content digest and cached. Nothing about the base is recomputed when a parameter moves; a
parameter is an analytic primitive evaluated on the cells it can reach.

**What a field cannot hold.** A feature needs roughly three voxels across to exist. At 2.5 mm a
Ø21 hole is 8.4 voxels and survives well, Ø8 is marginal, and Ø4.2 is gone. This is a property of
the representation, not a bug in it, and it is why the spacing is reported on every field.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import ndimage

from .. import cache
from ..geometry.brep import Tessellation

# Voxel size as a fraction of the model's bounding diagonal, and the range it is held within.
#
# Derived rather than absolute, for the same reason every other geometric tolerance here is: 2.5 mm
# resolves a bolt hole on a two-metre casting and is coarser than a whole feature on a forty-
# millimetre bracket. On the part in ``assets/`` this gives 2.5 mm.
SPACING_FRACTION = 1.25e-3
MIN_SPACING_MM = 0.25
MAX_SPACING_MM = 10.0

# How far the band reaches, in voxels.
#
# Three is the smallest that works. Dual contouring needs a signed value at all eight corners of
# every cell the surface crosses, and a blend of radius k needs distance out to k - so the band has
# to hold more than the surface itself, and one voxel of slack on each side is not enough to blend
# in.
BAND_VOXELS = 3

# How far outside the part a design may add material, as a fraction of the bounding diagonal.
#
# The grid has to be big enough for what a design *will* be, not for what the base part *is*. A rib
# taller than the space above the part is silently clipped by the edge of the grid otherwise, and
# what that looks like is a dial that stops working partway along - which is how it was found.
#
# Proportional, because a rib on a two-metre casting is not the size of a rib on a bracket. Two
# percent of the diagonal is 40 mm here, and costs about a quarter more cells.
HEADROOM_FRACTION = 0.02

# Triangles whose distance is evaluated against cells in one pass. Bounds peak memory: each pass
# materialises one (cell, triangle) pair per candidate, and a large planar triangle covers a large
# box.
PAIR_BUDGET = 4_000_000

# What a stored field depends on: how it is built, and the shape of the tessellation it is built
# from. Nothing else can change it, so nothing else invalidates it - three minutes is too long to
# throw away because a route or a colour changed.
CODE = ("generate/field.py", "geometry/brep.py")


def scale_spacing(diagonal_mm: float) -> float:
    """A voxel size proportional to the model, clamped to a usable range."""
    return min(max(diagonal_mm * SPACING_FRACTION, MIN_SPACING_MM), MAX_SPACING_MM)


def scale_headroom(diagonal_mm: float, spacing_mm: float) -> float:
    """How far past the part the grid reaches. Never less than the band needs."""
    return max(diagonal_mm * HEADROOM_FRACTION, (BAND_VOXELS + 2) * spacing_mm)


@dataclass(frozen=True)
class Grid:
    """A uniform sampling lattice. Fixed for the life of a base geometry.

    ``origin`` is the world position of cell (0, 0, 0). A cell's centre is
    ``origin + (i, j, k) * spacing_mm``, so a design and its variants address identical points.
    """

    origin: tuple[float, float, float]
    spacing_mm: float
    shape: tuple[int, int, int]

    @property
    def n_cells(self) -> int:
        return int(self.shape[0]) * int(self.shape[1]) * int(self.shape[2])

    def centres(self, index: np.ndarray) -> np.ndarray:
        """World coordinates of the given flat cell indices, as (n, 3)."""
        i, j, k = np.unravel_index(index, self.shape)
        return np.stack([i, j, k], axis=1) * self.spacing_mm + np.asarray(self.origin)


@dataclass
class Field:
    """A signed distance field, stored as a narrow band over a sign.

    ``band_index``     flat cell indices carrying a distance, ascending.
    ``band_mm``        signed distance at those cells, negative inside the solid.
    ``inside``         sign for every cell of the grid. True is solid.
    ``reach_mm``       how far the band extends; beyond it distance is only known to exceed this.
    ``source_digest``  the CAD content hash this was built from. A field belongs to one file.
    """

    grid: Grid
    band_index: np.ndarray
    band_mm: np.ndarray
    inside: np.ndarray
    reach_mm: float

    headroom_mm: float = 0.0
    """How far past the part the grid reaches, and therefore how much a design may add."""

    source_digest: str = ""

    key: str = ""
    """What this field is stored under. Anything derived from it is keyed on this in turn."""

    @property
    def n_band(self) -> int:
        return int(self.band_index.size)

    @property
    def n_inside(self) -> int:
        return int(self.inside.sum())

    def volume_mm3(self) -> float:
        """Volume by counting solid cells.

        Coarse by construction - it quantises the surface to whole voxels - and useful precisely
        because it is measured the same way for every variant. Comparing it against the B-rep
        volume says how much the field's resolution costs on this part.
        """
        return float(self.n_inside) * self.grid.spacing_mm**3

    def shell(self) -> np.ndarray:
        """Flat indices of the solid cells that touch something that is not solid.

        The field drawn as itself. A contour is a *reconstruction* - one vertex per cell, placed by
        a least-squares fit - and it can be wrong in ways the field is not; these are the cells,
        exactly as stored, and a cube each is the whole picture.

        It is also far cheaper. On the part in ``assets/`` at 10 mm this is about 90 thousand cells
        against 223 thousand triangles, and one position per cell against three vertices with
        normals and ids per triangle.

        Only the cells on the boundary: the interior is solid and hidden, and drawing eight million
        cubes to see the outside of them is work for nothing.
        """
        inside = self.inside
        exposed = np.zeros(inside.shape, dtype=bool)
        for axis in range(3):
            lower = [slice(None)] * 3
            upper = [slice(None)] * 3
            lower[axis] = slice(None, -1)
            upper[axis] = slice(1, None)
            low, high = tuple(lower), tuple(upper)
            exposed[low] |= inside[low] & ~inside[high]
            exposed[high] |= inside[high] & ~inside[low]
        return np.flatnonzero(exposed.ravel())

    def plane(self, axis: int, index: int) -> np.ndarray:
        """Signed distance across one plane of the grid, as a 2D array in mm.

        The most direct thing a field can be asked for, and the only view that shows the numbers
        rather than an interpretation of them: the sign, the band, how thick a wall is, whether a
        cavity is open. A surface has to be reconstructed and can be reconstructed wrongly; a plane
        of the field cannot.

        Beyond the band the value is the reach, signed - which is the truth. The field does not
        know how far away a distant cell is, only which side it is on.
        """
        if axis not in (0, 1, 2):
            raise ValueError(f"axis must be 0, 1 or 2, got {axis}")
        if not 0 <= index < self.grid.shape[axis]:
            raise IndexError(f"index {index} outside 0..{self.grid.shape[axis] - 1} on axis {axis}")

        sign = np.take(self.inside, index, axis=axis)
        out = np.where(sign, -self.reach_mm, self.reach_mm).astype(np.float32)

        coordinates = np.unravel_index(self.band_index, self.grid.shape)
        on_plane = coordinates[axis] == index
        rows, columns = (c[on_plane] for a, c in enumerate(coordinates) if a != axis)
        out[rows, columns] = self.band_mm[on_plane]
        return out

    def __getstate__(self) -> dict:
        """Store the sign a bit per cell instead of a byte per cell.

        ``inside`` is one boolean for every cell of the dense grid, and numpy spends a whole byte
        on each. At 2.5 mm that is 74.5 MB of the 144 MB a stored field costs, for one bit of
        information per cell. Packing it is two calls and takes the file to 79 MB.
        """
        state = self.__dict__.copy()
        state["inside"] = np.packbits(self.inside.ravel())
        state["inside_shape"] = self.inside.shape
        return state

    def __setstate__(self, state: dict) -> None:
        shape = state.pop("inside_shape")
        count = int(np.prod(shape))
        state["inside"] = np.unpackbits(state["inside"], count=count).astype(bool).reshape(shape)
        self.__dict__.update(state)

    def at(self, flat: np.ndarray) -> np.ndarray:
        """Signed distance at the given flat cell indices.

        The band is sorted, so a lookup is a binary search rather than a dense array: reconstituting
        the whole grid as floats would cost 298 MB on the part in ``assets/`` at 2.5 mm, to answer
        questions that only ever touch the surface.

        Off the band the answer is the reach, signed. That is not an approximation - it is what the
        field knows about a distant cell, which is which side of the surface it is on.
        """
        flat = np.asarray(flat)
        position = np.clip(np.searchsorted(self.band_index, flat), 0, self.band_index.size - 1)
        on_band = self.band_index[position] == flat
        far = np.where(self.inside.ravel()[flat], -self.reach_mm, self.reach_mm)
        return np.where(on_band, self.band_mm[position], far).astype(np.float32)

    def sample(self, points: np.ndarray) -> np.ndarray:
        """Signed distance at arbitrary points, by nearest cell.

        Nearest rather than interpolated: this exists to answer "is this inside" and "how far from
        a wall", not to reconstruct a surface. Contouring reads the band directly.
        """
        grid = self.grid
        index = np.rint(
            (np.asarray(points, dtype=float) - np.asarray(grid.origin)) / grid.spacing_mm
        ).astype(np.int64)
        index = np.clip(index, 0, np.asarray(grid.shape) - 1)
        return self.at(np.ravel_multi_index((index[:, 0], index[:, 1], index[:, 2]), grid.shape))


def build_field(
    tess: Tessellation,
    spacing_mm: float | None = None,
    source_digest: str = "",
    headroom_mm: float | None = None,
    grid: Grid | None = None,
) -> Field:
    """Sample a watertight tessellation into a narrow-band signed distance field.

    ``grid`` samples onto a lattice that already exists instead of one fitted to this surface. Two
    versions of a part can only be combined cell by cell if they were sampled at the same points.

    Three passes, in this order, because each needs the one before it.

    **Unsigned distance**, by scan conversion: every triangle writes the exact point-to-triangle
    distance into the cells near it, and each cell keeps the smallest. Exact rather than sampled -
    an approximate distance shows up as sub-voxel wobble that dual contouring then reproduces
    faithfully as noise.

    **Sign**, by connectivity away from the surface and by ray parity within half a voxel of it -
    each method used only where it is sound. See :func:`_classify`.
    """
    if grid is None:
        spacing_mm, headroom_mm = _resolved(tess, spacing_mm, headroom_mm)
        grid = _grid_for(tess, spacing_mm, headroom_mm)
    elif headroom_mm is None:
        headroom_mm = 0.0
    reach = BAND_VOXELS * grid.spacing_mm

    distance = _unsigned_distance(tess, grid, reach)
    inside = _classify(tess, grid, distance)

    band_mask = distance <= reach
    # int32 halves what the band costs to hold and to store, and a grid large enough to overflow it
    # would need two billion cells - four times the dense count of the largest case measured.
    band_index = np.flatnonzero(band_mask.ravel()).astype(np.int32)
    signed = distance.ravel()[band_index]
    signed[inside.ravel()[band_index]] *= -1.0

    return Field(
        grid=grid,
        band_index=band_index,
        band_mm=signed.astype(np.float32),
        inside=inside,
        reach_mm=reach,
        headroom_mm=float(headroom_mm),
        source_digest=source_digest,
    )


def field_for(
    root: Path,
    tess: Tessellation,
    source_digest: str,
    spacing_mm: float | None = None,
    reuse: bool = True,
    headroom_mm: float | None = None,
) -> tuple[Field, bool]:
    """The field for one geometry, built once and kept. Returns it and whether it was already there.

    Three minutes is worth paying once and not worth paying on every restart. The key is the CAD's
    own digest and the voxel size, so a different file or a different resolution is a different
    field rather than a stale one.
    """
    spacing_mm, headroom_mm = _resolved(tess, spacing_mm, headroom_mm)
    key = field_key(tess, source_digest, spacing_mm, headroom_mm)
    item = cache.entry(root, "field", key)
    found, hit = cache.memoise(
        item,
        lambda: build_field(
            tess,
            spacing_mm=spacing_mm,
            source_digest=source_digest,
            headroom_mm=headroom_mm,
        ),
        reuse=reuse,
    )
    found.key = key
    return found, hit


def field_key(
    tess: Tessellation,
    source_digest: str,
    spacing_mm: float | None = None,
    headroom_mm: float | None = None,
) -> str:
    """What a field is stored under. The one place that says so.

    Asking whether a field is already built has to compute exactly the key building it would
    store under; a second copy of this rule that left the headroom out made every built field
    read as unbuilt.
    """
    spacing_mm, headroom_mm = _resolved(tess, spacing_mm, headroom_mm)
    return cache.key_for(source_digest, f"{spacing_mm:.6f}", f"{headroom_mm:.6f}", code=CODE)


def _resolved(
    tess: Tessellation, spacing_mm: float | None, headroom_mm: float | None
) -> tuple[float, float]:
    """The spacing and headroom a request means, with the part's own defaults filled in."""
    lo, hi = tess.vertices.min(axis=0), tess.vertices.max(axis=0)
    diagonal = float(np.linalg.norm(hi - lo))
    if spacing_mm is None:
        spacing_mm = scale_spacing(diagonal)
    if headroom_mm is None:
        headroom_mm = scale_headroom(diagonal, spacing_mm)
    return spacing_mm, headroom_mm


def _grid_for(tess: Tessellation, spacing_mm: float, headroom_mm: float) -> Grid:
    """A lattice with room for the band, and for whatever a design is going to add.

    The margin is not slack. A design adds material and the grid is fixed, so a rib taller than the
    space above the part gets quietly cut off by the edge of the lattice - which looks like a dial
    that stops working halfway along rather than like a grid that is too small.

    The extra half voxel is what keeps samples **off** the surface. Machined faces sit at round
    coordinates, so a lattice starting a whole number of voxels below the bounding box puts sample
    points exactly on them - where the distance is zero, the sign is a coin toss, and a flat face
    comes back a voxel out of place. Half a voxel of offset costs nothing and removes the case.
    """
    # Rounded up to a whole voxel and then offset by half of one, so the padding is a half-integer
    # number of voxels whatever was asked for. Adding a fixed half to an arbitrary millimetre
    # figure does not work: headroom of 87.5 mm on a 5 mm voxel lands back on a whole number, and
    # then sample points sit exactly on axis-aligned faces again - where the distance is zero, the
    # sign is a coin toss, and the encoding of "on the surface but solid" is negative zero.
    wanted = max(headroom_mm, (BAND_VOXELS + 2) * spacing_mm)
    pad = (math.ceil(wanted / spacing_mm) + 0.5) * spacing_mm
    lo = tess.vertices.min(axis=0) - pad
    hi = tess.vertices.max(axis=0) + pad
    shape = tuple(int(math.ceil((hi[axis] - lo[axis]) / spacing_mm)) + 1 for axis in range(3))
    return Grid(origin=tuple(float(v) for v in lo), spacing_mm=spacing_mm, shape=shape)


def _unsigned_distance(tess: Tessellation, grid: Grid, reach: float) -> np.ndarray:
    """Exact distance from every nearby cell to the surface, by triangle scan conversion.

    Each triangle only has to be compared against cells within ``reach`` of its own bounding box,
    which is what keeps this proportional to surface area rather than to volume. Triangles are
    processed in groups sized by how many cell-triangle pairs they generate, so one enormous
    planar triangle does not decide the memory footprint of the whole pass.
    """
    spacing = grid.spacing_mm
    origin = np.asarray(grid.origin)
    shape = np.asarray(grid.shape)

    a = tess.vertices[tess.triangles[:, 0]]
    b = tess.vertices[tess.triangles[:, 1]]
    c = tess.vertices[tess.triangles[:, 2]]

    lo = np.floor((np.minimum(np.minimum(a, b), c) - origin - reach) / spacing).astype(np.int64)
    hi = np.ceil((np.maximum(np.maximum(a, b), c) - origin + reach) / spacing).astype(np.int64)
    lo = np.clip(lo, 0, shape - 1)
    hi = np.clip(hi, 0, shape - 1)
    extent = hi - lo + 1
    per_triangle = extent.prod(axis=1)

    distance = np.full(grid.shape, np.inf, dtype=np.float32)
    flat = distance.ravel()

    for start, stop in _groups(per_triangle, PAIR_BUDGET):
        counts = per_triangle[start:stop]
        owner = np.repeat(np.arange(start, stop), counts)
        offset = np.arange(int(counts.sum())) - np.repeat(np.cumsum(counts) - counts, counts)

        span = extent[start:stop]
        ny = np.repeat(span[:, 1], counts)
        nz = np.repeat(span[:, 2], counts)
        k = offset % nz
        j = (offset // nz) % ny
        i = offset // (nz * ny)

        cell = np.stack(
            [
                np.repeat(lo[start:stop, 0], counts) + i,
                np.repeat(lo[start:stop, 1], counts) + j,
                np.repeat(lo[start:stop, 2], counts) + k,
            ],
            axis=1,
        )
        points = cell * spacing + origin
        d = _point_triangle_distance(points, a[owner], b[owner], c[owner])

        index = np.ravel_multi_index((cell[:, 0], cell[:, 1], cell[:, 2]), grid.shape)
        near = d <= reach
        np.minimum.at(flat, index[near], d[near].astype(np.float32))

    return distance


def _groups(counts: np.ndarray, budget: int):
    """Consecutive spans of triangles whose total cell count stays under ``budget``.

    A single triangle over budget still forms a span of its own: refusing it would leave a hole in
    the field, and the alternative - subdividing it - changes the surface being measured.
    """
    start = 0
    running = 0
    for index, count in enumerate(counts):
        if running and running + count > budget:
            yield start, index
            start, running = index, 0
        running += int(count)
    if start < counts.size:
        yield start, int(counts.size)


def _point_triangle_distance(
    p: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray
) -> np.ndarray:
    """Exact distance from each point to its triangle.

    The barycentric region test: a point's closest point on a triangle lies in the interior, on one
    of three edges, or at one of three vertices, and which it is falls out of two dot products
    without any branching per point.
    """
    ab, ac, ap = b - a, c - a, p - a
    d1 = np.einsum("ij,ij->i", ab, ap)
    d2 = np.einsum("ij,ij->i", ac, ap)

    bp = p - b
    d3 = np.einsum("ij,ij->i", ab, bp)
    d4 = np.einsum("ij,ij->i", ac, bp)

    cp = p - c
    d5 = np.einsum("ij,ij->i", ab, cp)
    d6 = np.einsum("ij,ij->i", ac, cp)

    vc = d1 * d4 - d3 * d2
    vb = d5 * d2 - d1 * d6
    va = d3 * d6 - d5 * d4
    denom = va + vb + vc

    with np.errstate(divide="ignore", invalid="ignore"):
        v_edge_ab = np.where(d1 - d3 != 0, d1 / (d1 - d3), 0.0)
        w_edge_ac = np.where(d2 - d6 != 0, d2 / (d2 - d6), 0.0)
        edge_bc = np.where((d4 - d3) + (d5 - d6) != 0, (d4 - d3) / ((d4 - d3) + (d5 - d6)), 0.0)
        inv = np.where(denom != 0, 1.0 / denom, 0.0)

    v = np.clip(vb * inv, 0.0, 1.0)
    w = np.clip(vc * inv, 0.0, 1.0)
    closest = a + v[:, None] * ab + w[:, None] * ac

    on_a = (d1 <= 0) & (d2 <= 0)
    on_b = (d3 >= 0) & (d4 <= d3)
    on_c = (d6 >= 0) & (d5 <= d6)
    on_ab = (vc <= 0) & (d1 >= 0) & (d3 <= 0)
    on_ac = (vb <= 0) & (d2 >= 0) & (d6 <= 0)
    on_bc = (va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0)

    closest = np.where(on_bc[:, None], b + np.clip(edge_bc, 0.0, 1.0)[:, None] * (c - b), closest)
    closest = np.where(on_ac[:, None], a + np.clip(w_edge_ac, 0.0, 1.0)[:, None] * ac, closest)
    closest = np.where(on_ab[:, None], a + np.clip(v_edge_ab, 0.0, 1.0)[:, None] * ab, closest)
    closest = np.where(on_c[:, None], c, closest)
    closest = np.where(on_b[:, None], b, closest)
    closest = np.where(on_a[:, None], a, closest)

    return np.linalg.norm(p - closest, axis=1)


def _classify(tess: Tessellation, grid: Grid, distance: np.ndarray) -> np.ndarray:
    """Which cells are solid. Two methods, each used where it is sound.

    **Connectivity says which cells share an answer.** Two cells one voxel apart on opposite sides
    of the surface cannot both be further than half a voxel from it: the surface lies on the
    segment between their centres, so one of them is within half its length. So the cells further
    than half a voxel from any triangle are cut into components by the surface, and every cell in a
    component is on the same side of it. That reduces the question from millions of cells to a
    handful of components.

    **Ray parity says what that answer is.** One representative cell per component is tested by
    counting how many triangles a ray from it crosses; odd is inside. The direction is a fixed
    irrational one rather than an axis, because a ray down an axis grazes axis-aligned geometry and
    a grazing hit is the one case parity gets wrong.

    **The shell is tested cell by cell.** Within half a voxel of the surface the separation
    argument does not apply, so those cells get a ray each.

    Two earlier versions were wrong here, and both were caught by a shape with a known answer.
    Resolving the shell by growing the outside into it biased every surface outward by a third of a
    voxel - on a sphere, 4.9% of band cells on the wrong side and 3.9% of the volume lost as a
    rind. Then calling any component that does not touch the edge of the grid solid **filled in
    sealed voids**: connectivity cannot tell the material inside a wall from the air inside a
    cavity, since neither reaches the boundary. Only the ray knows.
    """
    structure = ndimage.generate_binary_structure(3, 1)
    resolvable = distance > grid.spacing_mm * 0.501

    labels, count = ndimage.label(resolvable, structure=structure)
    solid = np.zeros(distance.shape, dtype=bool)

    if count:
        representative = np.array(
            [
                _first_cell(labels, box, label)
                for label, box in enumerate(ndimage.find_objects(labels), 1)
            ]
        )
        component_is_solid = _inside_by_parity(tess, grid, representative)
        lookup = np.zeros(count + 1, dtype=bool)
        lookup[1:] = component_is_solid
        solid = lookup[labels]
    del labels

    shell = np.flatnonzero(~resolvable.ravel())
    if shell.size:
        solid.ravel()[shell] = _inside_by_parity(tess, grid, shell)
    return solid


def _first_cell(labels: np.ndarray, box: tuple[slice, ...], label: int) -> int:
    """A flat index of any one cell carrying ``label``. Its component's answer is the whole
    component's answer, so which cell it is does not matter."""
    window = labels[box]
    local = int(np.argmax(window == label))
    offset = np.unravel_index(local, window.shape)
    return int(
        np.ravel_multi_index(
            tuple(int(o) + s.start for o, s in zip(offset, box, strict=True)), labels.shape
        )
    )


# A direction with no rational relationship to any axis, so a ray never runs along an edge or
# inside the plane of a face. Grazing is the only way parity gives a wrong answer on a closed
# surface, and it only happens when the ray is aligned with something.
_PARITY_DIRECTION = np.array([0.31622776601683794, 0.5477225575051661, 0.7745966692414834])

# Rays per call to the intersector. Each ray can report many hits, so the returned arrays are
# several times this and the peak is what has to stay bounded.
_RAY_CHUNK = 500_000


def _inside_by_parity(tess: Tessellation, grid: Grid, cells: np.ndarray) -> np.ndarray:
    """Whether each cell is inside the solid, by counting surface crossings.

    Exact on a watertight, coherently wound surface: a ray from an interior point leaves it an odd
    number of times. The health gate is what makes that assumption safe to rely on here.
    """
    try:
        from trimesh import Trimesh
        from trimesh.ray.ray_pyembree import RayMeshIntersector

        mesh = Trimesh(vertices=tess.vertices, faces=tess.triangles, process=False, validate=False)
        intersector = RayMeshIntersector(mesh)
    except ImportError:  # pragma: no cover - embreex is a declared dependency
        return _inside_by_winding(tess, grid, cells)

    inside = np.zeros(cells.size, dtype=bool)
    for start in range(0, cells.size, _RAY_CHUNK):
        block = cells[start : start + _RAY_CHUNK]
        origins = grid.centres(block)
        directions = np.tile(_PARITY_DIRECTION, (block.size, 1))
        _, ray = intersector.intersects_id(origins, directions, multiple_hits=True)
        hits = np.bincount(ray, minlength=block.size)
        inside[start : start + block.size] = hits % 2 == 1
    return inside


def _inside_by_winding(tess: Tessellation, grid: Grid, cells: np.ndarray) -> np.ndarray:
    """Fallback for the case Embree's wheel is unavailable. Correct, and far slower.

    The solid angle a closed surface subtends at a point is 4 pi from inside it and zero from
    outside, with no ray, no tolerance and nothing to graze.
    """
    a = tess.vertices[tess.triangles[:, 0]]
    b = tess.vertices[tess.triangles[:, 1]]
    c = tess.vertices[tess.triangles[:, 2]]

    inside = np.zeros(cells.size, dtype=bool)
    for start in range(0, cells.size, 256):
        block = cells[start : start + 256]
        p = grid.centres(block)[:, None, :]
        va, vb, vc = a[None] - p, b[None] - p, c[None] - p
        la = np.linalg.norm(va, axis=2)
        lb = np.linalg.norm(vb, axis=2)
        lc = np.linalg.norm(vc, axis=2)
        numerator = np.einsum("ijk,ijk->ij", va, np.cross(vb, vc))
        denominator = (
            la * lb * lc
            + np.einsum("ijk,ijk->ij", va, vb) * lc
            + np.einsum("ijk,ijk->ij", vb, vc) * la
            + np.einsum("ijk,ijk->ij", vc, va) * lb
        )
        total = 2.0 * np.arctan2(numerator, denominator).sum(axis=1)
        inside[start : start + block.size] = np.abs(total) > 2.0 * np.pi
    return inside
