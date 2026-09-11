"""Placement: where one of an engineer's placements puts ribs on a part.

A placement names a **host** the ribs stand on, the **supports** they run between, and what they
**keep out** of. This turns that into ribs, and says what happened to every path it tried.

**Paths are drawn on the host's plane** by the layout - families of straight paths, or spokes out
from a feature's axis - laid only across where the host is, and walked in short steps. A rib can
only be where the path is over the host and clear of every keep-out, grown by half the rib's
thickness and the clearance asked for; keep-outs and gaps in the host cut a path into pieces.

**Each rib is a span.** Where a stretch of path ends, the walk carries on a little way, a few
millimetres above the host, to see what is there: metal belonging to a support, metal belonging to
something else, a keep-out, or nothing. A rib runs only between two supports - unless the placement
allows free ends - and is carried into each support so its end is a filleted junction, not a cut.
Nothing is trimmed on the grid, so nothing can pass through a wall.

**Height follows what a rib spans, end by end.** Each end is buried in what it meets, as deep as it
must be for its last few millimetres to stay inside the metal all the way up - a wall with draft
leans away from a rib as it rises, so the deeper the end, the taller the rib can stand there. Each
end is no taller than that, nor than any feature named as a cap, nor than a height given outright -
whichever is least - times the fraction asked for; the top runs straight from one end's height to
the other's, or is held level at the lower when the placement asks for that.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..features import Feature, FeatureKind, FeatureSet, extent
from ..geometry.atlas import Atlas
from ..geometry.brep import Tessellation
from ..spec import Placement
from .field import Field
from .ribs import Rib

# How far past the end of a stretch of path the walk looks for what the rib would meet, as a
# multiple of the root fillet: a wall stands where the fillet at its foot ends.
LOOK_PAST = 3.0

# A stretch shorter than this many rib thicknesses is a stub, not a rib.
SHORTEST = 2.0

# How deep a rib's end may go into what it meets, as a multiple of how deep it is buried at least:
# far enough to stay inside a wall with draft to the wall's top.
DEEPEST = 10.0


@dataclass(frozen=True)
class HostFrame:
    """The host's plane: an origin on it, its outward normal, and two axes in it."""

    origin: np.ndarray
    normal: np.ndarray
    e1: np.ndarray
    e2: np.ndarray

    def to_plane(self, points: np.ndarray) -> np.ndarray:
        p = np.asarray(points, dtype=float) - self.origin
        return np.stack([p @ self.e1, p @ self.e2], axis=-1)

    def to_world(self, uv: np.ndarray, height: float | np.ndarray = 0.0) -> np.ndarray:
        uv = np.atleast_2d(uv)
        h = np.asarray(height, dtype=float).reshape(-1, 1) if np.ndim(height) else height
        return self.origin + uv[:, :1] * self.e1 + uv[:, 1:2] * self.e2 + h * self.normal


@dataclass
class Placed:
    """The ribs a placement made, and what happened to every path it tried."""

    ribs: list[Rib]
    spans: list[dict] = field(default_factory=list)
    paths: int = 0
    """How many paths the layout drew. Each becomes ribs, or is counted in ``dropped`` with why."""
    tried: list[dict] = field(default_factory=list)
    """Every stretch of path tried, as a line just off the host - ``a``, ``b`` - and what became
    of it: ``rib``, or why not. What the layout will do, to see before anything is made."""
    dropped: dict[str, int] = field(default_factory=dict)
    keep_outs: list[dict] = field(default_factory=list)
    caps: dict = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    ended_on: dict[str, int] = field(default_factory=dict)
    """What pieces that ended on something not named to run between ended on, by feature - what
    could be named to make ribs of them."""

    def tally(self) -> str:
        """What became of every path, in counts that add up. Keep-outs and gaps cut a path into
        pieces, so ribs can outnumber paths: this counts the lines that cross where ribs stand,
        the pieces they are cut into and what each piece became - then the lines that miss."""
        missed = self.dropped.get("missed", 0)
        crossed = self.paths - missed
        if not self.paths:
            return "the layout lays no lines"
        if not crossed:
            if missed == 1:
                return "the line misses where ribs stand"
            return f"all {missed} lines miss where ribs stand"
        rest = sorted((why, n) for why, n in self.dropped.items() if why != "missed")
        pieces = len(self.ribs) + sum(n for _, n in rest)
        cross = "crosses" if crossed == 1 else "cross"
        words = f"{_many(crossed, 'line')} {cross} where ribs stand"
        if pieces != crossed:
            words += f", cut into {pieces} pieces"
        became = [_many(len(self.ribs), "rib")]
        for why, n in rest:
            said = f"{n} {NOT_PLACED.get(why, why.replace('_', ' '))}"
            if why == "ended_elsewhere" and self.ended_on:
                named = sorted(self.ended_on, key=lambda name: (-self.ended_on[name], name))
                more = f" and {len(named) - 3} more" if len(named) > 3 else ""
                said += f" ({', '.join(named[:3])}{more})"
            became.append(said)
        words += ": " + ", ".join(became)
        if missed:
            miss = "line misses" if missed == 1 else "lines miss"
            words += f"; {missed} more {miss} where ribs stand"
        return words


# Why a piece of a path did not become a rib, in the words the verdict uses.
NOT_PLACED = {
    "keep_out": "stopped by something to keep clear of",
    "open_end": "ending at an edge with nothing to meet",
    "ended_elsewhere": "ending on something not named to run between",
    "too_short": "too short to be a rib",
    "no_height": "with no room for a rib's height",
}


def _many(n: int, thing: str) -> str:
    return f"no {thing}s" if n == 0 else f"{n} {thing}" + ("" if n == 1 else "s")


def place(
    base: Field,
    features: FeatureSet,
    atlas: Atlas,
    tess: Tessellation,
    placement: Placement,
) -> Placed:
    """Ribs for ``placement`` on the part ``base`` samples. See the module note."""
    host, problem = host_of(features, placement.host)
    if host is None:
        return Placed(ribs=[], problems=[problem])
    frame = _frame(host)
    section = placement.section
    thickness = section.thickness_mm
    spacing = base.grid.spacing_mm
    step = max(min(spacing / 2.0, 1.0), features.diagonal_mm * 2e-4)

    footprint = _Footprint.of(tess, host.face_ids, frame, step)
    keep = _keep_outs(features, atlas, tess, placement, frame, host)
    reach = LOOK_PAST * section.root_fillet_mm + spacing
    probe_height = max(2.0 * spacing, 0.5 * section.root_fillet_mm)
    # How far a rib's end is buried in what it meets: set by the rib, not by the grid, so a
    # preview and a full design end in the same place.
    bury = max(section.root_fillet_mm, 2.0 * spacing)
    finder = _Faces(tess)
    support_faces = _support_faces(features, atlas, placement.supports)

    placed = Placed(ribs=[], keep_outs=[k.row() for k in keep])
    caps = _caps(features, tess, placement, frame)
    placed.caps = caps
    # Why stretches had no room for a rib. A problem only if no rib had room at all; otherwise
    # they are counted among what was not placed, like any other stretch dropped.
    no_room: list[str] = []
    # Lines are drawn a little off the host, so they show over it rather than in it.
    lift = max(spacing / 2.0, 0.5)

    def tried(p: np.ndarray, q: np.ndarray, outcome: str) -> None:
        a, b = frame.to_world(np.array([p, q]), lift)
        placed.tried.append(
            {
                "a": [round(float(v), 2) for v in a],
                "b": [round(float(v), 2) for v in b],
                "outcome": outcome,
            }
        )

    for path_id, (start, direction, length) in enumerate(
        _paths(placement, frame, footprint, features)
    ):
        placed.paths += 1
        s = np.arange(0.0, length + step, step)
        uv = start + np.outer(s, direction)
        over = footprint.covers(uv)
        if not over.any():
            _count(placed, "missed")
            tried(uv[0], uv[-1], "missed")
            continue
        blocked = np.zeros(s.size, dtype=bool)
        for k in keep:
            blocked |= k.blocks(uv, thickness / 2.0)
        usable = over & ~blocked
        if not usable.any():
            _count(placed, "keep_out")
            where = np.flatnonzero(over)
            tried(uv[where[0]], uv[where[-1]], "keep_out")
            continue
        for first, last in _runs(usable):
            if (s[last] - s[first]) < SHORTEST * thickness:
                _count(placed, "too_short")
                tried(uv[first], uv[last], "too_short")
                continue
            mets = [
                _end(
                    base,
                    frame,
                    finder,
                    support_faces,
                    uv[index],
                    sense * direction,
                    reach,
                    step,
                    probe_height,
                    blocked,
                    index,
                    int(sense),
                    bury,
                )
                for index, sense in ((first, -1.0), (last, 1.0))
            ]
            ends = [met.kind for met in mets]
            if placement.connection == "supports" and ends != ["support", "support"]:
                # What stops it most: a keep-out, then an edge with nothing past it - naming a
                # face would not help either - then something that could be named to run between.
                reason = next(
                    why
                    for kind, why in (
                        ("keep_out", "keep_out"),
                        ("edge", "open_end"),
                        ("elsewhere", "ended_elsewhere"),
                    )
                    if kind in ends
                )
                _count(placed, reason)
                tried(uv[first], uv[last], reason)
                for met in mets:
                    if reason != "ended_elsewhere" or met.kind != "elsewhere" or met.face is None:
                        continue
                    for feature in features.containing(met.face) or [None]:
                        name = feature.id if feature else f"face:{met.face}"
                        placed.ended_on[name] = placed.ended_on.get(name, 0) + 1
                continue
            heights, why = _height(caps, [met.top for met in mets], placement)
            if heights is None or min(heights) <= section.root_fillet_mm:
                # No room for a rib: taller than its own root fillet is the least a rib is.
                reason = (
                    why
                    if heights is None
                    else f"{why} leaves {min(heights):.1f} mm above the host - no taller than "
                    f"the R{section.root_fillet_mm:g} root fillet, so no rib"
                )
                if reason not in no_room:
                    no_room.append(reason)
                _count(placed, "no_height")
                tried(uv[first], uv[last], "no_height")
                continue
            a = mets[0].end_for(heights[0]) if mets[0].ends is not None else uv[first]
            b = mets[1].end_for(heights[1]) if mets[1].ends is not None else uv[last]
            tried(a, b, "rib")
            sink = spacing
            rib = Rib(
                start=tuple(float(v) for v in frame.to_world(a, -sink)[0]),
                end=tuple(float(v) for v in frame.to_world(b, -sink)[0]),
                thickness_mm=thickness,
                height_mm=heights[0] + sink,
                end_height_mm=heights[1] + sink,
                pull=tuple(float(v) for v in frame.normal),
                draft_deg=section.draft_deg,
                edge_round_mm=section.edge_round_mm,
            )
            placed.ribs.append(rib)
            placed.spans.append(
                {
                    "path": path_id,
                    "ends": ends,
                    "length_mm": round(float(np.linalg.norm(b - a)), 1),
                    "height_mm": round(max(heights), 1),
                    "heights_mm": [round(h, 1) for h in heights],
                    "limited_by": why,
                    "clearance_mm": _clearance(keep, a, b, thickness / 2.0),
                }
            )
    if not placed.ribs:
        placed.problems.extend(no_room)
    return placed


# --- the host -------------------------------------------------------------------------------------


def host_of(features: FeatureSet, refs: list[str]) -> tuple[Feature | None, str]:
    """Where ribs stand, as one flat area: every face of every ref, which must lie in one plane.
    None, and why, when they do not - or when the part has no such feature."""
    found = [features.get(ref) for ref in refs]
    missing = [ref for ref, feature in zip(refs, found, strict=True) if feature is None]
    if missing or not found:
        return None, f"the part has no {', '.join(missing) or 'place for ribs to stand'}"
    curved = [
        f.id
        for f in found
        if f.normal is None
        or not (
            f.kind == FeatureKind.PLANAR_GROUP
            or (f.kind == FeatureKind.FACE and f.metrics.get("flat") == 1.0)
        )
    ]
    if curved:
        return None, f"{', '.join(curved)} is not flat; ribs stand only on flat faces yet"
    if len(found) == 1:
        return found[0], ""
    normal = np.asarray(found[0].normal, dtype=float)
    level = float(np.asarray(found[0].centroid) @ normal)
    tolerance = max(features.diagonal_mm * 1e-4, 1e-3)
    for f in found[1:]:
        parallel = float(np.asarray(f.normal) @ normal) > math.cos(math.radians(1.0))
        if not parallel or abs(float(np.asarray(f.centroid) @ normal) - level) > tolerance:
            return None, f"{', '.join(refs)} are not one plane; ribs stand on one flat area"
    faces = tuple(sorted({face for f in found for face in f.face_ids}))
    areas = np.array([f.area_mm2 for f in found])
    centre = np.average(np.array([f.centroid for f in found]), axis=0, weights=areas)
    return (
        Feature(
            id=" + ".join(refs),
            kind=FeatureKind.FACE,
            face_ids=faces,
            area_mm2=float(areas.sum()),
            centroid=tuple(float(v) for v in centre),
            metrics={"flat": 1.0},
            normal=tuple(float(v) for v in normal),
        ),
        "",
    )


def _frame(host: Feature) -> HostFrame:
    n = np.asarray(host.normal, dtype=float)
    n = n / np.linalg.norm(n)
    reference = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = reference - (reference @ n) * n
    e1 = e1 / np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    return HostFrame(origin=np.asarray(host.centroid, dtype=float), normal=n, e1=e1, e2=e2)


@dataclass
class _Footprint:
    """Where the host is, seen square to its plane, as a raster of small cells."""

    lo: np.ndarray
    step: float
    mask: np.ndarray

    @staticmethod
    def of(tess: Tessellation, face_ids, frame: HostFrame, step: float) -> _Footprint:
        mine = np.isin(tess.face_id, list(face_ids))
        corners = frame.to_plane(tess.vertices[tess.triangles[mine]].reshape(-1, 3)).reshape(
            -1, 3, 2
        )
        lo = corners.reshape(-1, 2).min(axis=0) - step
        hi = corners.reshape(-1, 2).max(axis=0) + step
        shape = np.ceil((hi - lo) / step).astype(int) + 1
        mask = np.zeros(tuple(shape), dtype=bool)
        for tri in corners:
            a, b, c = tri
            t_lo = np.floor((tri.min(axis=0) - lo) / step).astype(int)
            t_hi = np.ceil((tri.max(axis=0) - lo) / step).astype(int)
            iu = np.arange(t_lo[0], t_hi[0] + 1)
            iv = np.arange(t_lo[1], t_hi[1] + 1)
            gu, gv = np.meshgrid(iu, iv, indexing="ij")
            p = np.stack([lo[0] + gu * step, lo[1] + gv * step], axis=-1)
            inside = _in_triangle(p, a, b, c, step * 0.5)
            mask[gu[inside], gv[inside]] = True
        return _Footprint(lo=lo, step=step, mask=mask)

    def covers(self, uv: np.ndarray) -> np.ndarray:
        index = np.round((uv - self.lo) / self.step).astype(int)
        ok = np.all((index >= 0) & (index < np.asarray(self.mask.shape)), axis=1)
        out = np.zeros(uv.shape[0], dtype=bool)
        out[ok] = self.mask[index[ok, 0], index[ok, 1]]
        return out

    def cells(self) -> np.ndarray:
        """Every cell where the host is, as a point on its plane."""
        return self.lo + np.argwhere(self.mask) * self.step


def _in_triangle(p: np.ndarray, a, b, c, pad: float) -> np.ndarray:
    """Whether points lie in a triangle, or within ``pad`` of it - so no cell falls between two."""

    def side(p0, p1):
        edge = p1 - p0
        length = max(float(np.hypot(*edge)), 1e-12)
        cross = edge[0] * (p[..., 1] - p0[1]) - edge[1] * (p[..., 0] - p0[0])
        return cross / length

    area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if abs(area) < 1e-12:
        return np.zeros(p.shape[:-1], dtype=bool)
    sign = 1.0 if area > 0 else -1.0
    return (sign * side(a, b) >= -pad) & (sign * side(b, c) >= -pad) & (sign * side(c, a) >= -pad)


# --- paths ----------------------------------------------------------------------------------------


def _paths(placement: Placement, frame: HostFrame, footprint: _Footprint, features: FeatureSet):
    """Every path the layout draws: (start, unit direction, length), on the host's plane. Each is
    laid only across where the host is - never through the empty corners of a rectangle round a
    host that is not one, where it could only miss."""
    layout = placement.layout
    cells = footprint.cells()
    if layout.kind == "radial":
        centre_feature = features.get(layout.centre)
        assert centre_feature is not None
        centre = frame.to_plane(np.asarray(_axis_point(features, centre_feature)).reshape(1, 3))[0]
        reach = float(np.max(np.linalg.norm(cells - centre, axis=1))) + footprint.step
        count = int(layout.count or 0)
        first, arc = math.radians(layout.phase_deg), 2.0 * math.pi
        if layout.spread == "across":
            fan = _arc_covered(footprint, centre)
            if fan is not None:
                first, arc = fan
        whole = arc > 2.0 * math.pi - 1e-9
        for k in range(count):
            # All the way round, the first spoke at the phase; across a fan, each in the middle
            # of its share, so none lies on the fan's edge.
            angle = first + arc * (k if whole else k + 0.5) / count
            yield centre, np.array([math.cos(angle), math.sin(angle)]), reach
        return
    # A grid is one lattice: every family at the first family's spacing, laid from one origin -
    # the host's middle - so families cross at common points. Three families 60 degrees apart
    # whose offsets add up then make triangles, not three unrelated sets of lines.
    lattice = None
    if layout.kind == "grid" and layout.families:
        first = layout.families[0]
        if first.count is not None:
            angle = math.radians(first.angle_deg)
            m = np.array([-math.sin(angle), math.cos(angle)])
            across = cells @ m
            lattice = float(across.max() - across.min()) / first.count
        else:
            lattice = float(first.spacing_mm)
    for family in layout.families:
        angle = math.radians(family.angle_deg)
        d = np.array([math.cos(angle), math.sin(angle)])
        m = np.array([-d[1], d[0]])
        across = cells @ m
        along = cells @ d
        low, high = float(across.min()), float(across.max())
        if lattice is not None:
            n = np.arange(math.floor(low / lattice) - 1, math.ceil(high / lattice) + 1)
            offsets = [c for c in (n + family.offset) * lattice if low <= c <= high]
        elif family.count is not None:
            gap = (high - low) / family.count
            offsets = [low + (k + family.offset) * gap for k in range(family.count)]
        else:
            gap = float(family.spacing_mm)
            offsets = list(np.arange(low + family.offset * gap, high, gap))
        for c in offsets:
            yield c * m + float(along.min()) * d, d, float(along.max() - along.min())


def _arc_covered(footprint: _Footprint, centre: np.ndarray) -> tuple[float, float] | None:
    """The arc round ``centre`` that where ribs stand fills: where it starts, in radians, and how
    wide it is. None when it fills nearly all the way round - spokes then go all the way."""
    points = footprint.cells() - centre
    if not len(points):
        return None
    angles = np.sort(np.arctan2(points[:, 1], points[:, 0]) % (2.0 * math.pi))
    gaps = np.diff(np.concatenate([angles, [angles[0] + 2.0 * math.pi]]))
    widest = int(np.argmax(gaps))
    if gaps[widest] < math.radians(30.0):
        return None
    start = float(angles[(widest + 1) % len(angles)])
    return start, 2.0 * math.pi - float(gaps[widest])


def _axis_point(features: FeatureSet, feature: Feature) -> tuple[float, float, float]:
    if feature.axis_id and feature.axis_id in features.axes:
        return features.axes[feature.axis_id].point
    return feature.centroid


def _runs(usable: np.ndarray) -> list[tuple[int, int]]:
    """Index ranges where ``usable`` is true throughout, inclusive."""
    padded = np.concatenate([[False], usable, [False]])
    edges = np.flatnonzero(np.diff(padded.astype(int)))
    return [(int(a), int(b) - 1) for a, b in zip(edges[0::2], edges[1::2], strict=True)]


# --- what a path meets at its ends ----------------------------------------------------------------


class _Faces:
    """Which CAD face is nearest a point, exactly: the closest point on the tessellated surface."""

    def __init__(self, tess: Tessellation):
        import trimesh

        self.tess = tess
        self.mesh = trimesh.Trimesh(tess.vertices, tess.triangles, process=False)

    def nearest(self, point: np.ndarray) -> int:
        _, _, triangle = self.mesh.nearest.on_surface(np.asarray(point, dtype=float).reshape(1, 3))
        return int(self.tess.face_id[int(triangle[0])])

    def exit_along(self, inside: np.ndarray, direction: np.ndarray) -> float | None:
        """How far from a point inside the metal, along ``direction``, the metal ends."""
        distance = self.exits_along(np.asarray(inside, dtype=float).reshape(1, 3), direction)[0]
        return None if np.isnan(distance) else float(distance)

    def exits_along(self, inside: np.ndarray, direction: np.ndarray) -> np.ndarray:
        """The same for many points at once, in one cast: NaN where nothing is met."""
        origins = np.asarray(inside, dtype=float).reshape(-1, 3)
        out = np.full(len(origins), np.nan)
        if not len(origins):
            return out
        directions = np.tile(np.asarray(direction, dtype=float), (len(origins), 1))
        hits, rays, _ = self.mesh.ray.intersects_location(origins, directions, multiple_hits=False)
        if len(hits):
            out[rays] = np.linalg.norm(hits - origins[rays], axis=1)
        return out


def _support_faces(features: FeatureSet, atlas: Atlas, supports: list[str]) -> set[int]:
    """The faces that count as a support: its own, and those touching them - the fillet at its
    foot, a chamfer on its edge. Nothing further: a wall that merely shares a boss's axis is not
    the boss, and when a path ends on something else the report says what, so it can be named."""
    faces: set[int] = set()
    for ref in supports:
        own = set(features.get(ref).face_ids)
        faces |= own
        faces |= {n for f in own for n in atlas.faces[f].neighbours}
    return faces


@dataclass
class _Met:
    """What a stretch of path meets past one of its ends: ``support``, ``elsewhere``, ``keep_out``
    or ``edge``; the face it met; and where the rib's end could be buried in it, nearest first,
    with how tall a rib whose end is buried there can stand."""

    kind: str
    face: int | None = None
    ends: np.ndarray | None = None
    tops: np.ndarray | None = None

    @property
    def top(self) -> float | None:
        """The tallest a rib can stand at this end."""
        return None if self.tops is None else float(self.tops.max())

    def end_for(self, height: float) -> np.ndarray:
        """The nearest place to bury the end that keeps it inside all the way up to ``height``."""
        assert self.ends is not None and self.tops is not None
        enough = np.flatnonzero(self.tops >= height - 1e-6)
        return self.ends[int(enough[0]) if len(enough) else int(np.argmax(self.tops))]


def _end(
    base: Field,
    frame: HostFrame,
    finder: _Faces,
    support_faces: set[int],
    at: np.ndarray,
    outward: np.ndarray,
    reach: float,
    step: float,
    probe_height: float,
    blocked: np.ndarray,
    index: int,
    sense: int,
    bury: float,
) -> _Met:
    """What a stretch of path meets past one end, and how tall a rib can stand where it ends.

    A rib's end is buried in what it meets, and its last ``bury`` millimetres must stay inside the
    metal all the way up - taller, and the end would hang in the air. How tall that is depends on
    how deep the end goes: a wall with draft leans away from the rib as it rises, so the metal just
    inside its face runs out within millimetres while deeper in it goes on to the wall's top. So
    every depth into the metal is weighed, as far as the metal goes - never through to the other
    side - and the rib takes the nearest that is deep enough for the height it ends up with.
    """
    beyond = index + sense
    if 0 <= beyond < blocked.size and blocked[beyond]:
        return _Met("keep_out")
    s = np.arange(step, reach + step, step)
    probes = at + np.outer(s, outward)
    metal = base.sample(frame.to_world(probes, probe_height)) < 0.0
    if not metal.any():
        return _Met("edge")
    hit = probes[int(np.argmax(metal))]
    face = finder.nearest(frame.to_world(hit, probe_height)[0])
    kind = "support" if face in support_faces else "elsewhere"

    # Into the metal from where the path meets it, for as long as it stays metal.
    depth = np.arange(0.0, DEEPEST * bury + step, step)
    into = hit + np.outer(depth, outward)
    world = frame.to_world(into, probe_height)
    inside = base.sample(world)
    run = len(inside) if (inside < 0.0).all() else max(int(np.argmin(inside < 0.0)), 1)
    # How far the metal goes up from each point - only where the field is sure it is metal: just
    # inside a face the field and the true surface can disagree, and a ray from air measures air.
    rises = np.zeros(run)
    sure = np.flatnonzero(inside[:run] < -0.25 * base.grid.spacing_mm)
    if len(sure):
        rises[sure] = np.nan_to_num(finder.exits_along(world[sure], frame.normal), nan=0.0)
    width = int(round(bury / step))
    if run <= width:
        # Thinner than the burial: as deep as it goes, as tall as all of it allows.
        return _Met(kind, face, into[run - 1 : run], np.array([probe_height + rises.min()]))
    # An end at a depth keeps the last ``bury`` of the rib at the depths behind it inside, so it
    # stands as tall as the lowest of those columns of metal.
    held = np.lib.stride_tricks.sliding_window_view(rises, width + 1).min(axis=1)
    return _Met(kind, face, into[width:run], probe_height + held)


# --- keep-outs ------------------------------------------------------------------------------------


@dataclass
class _Disc:
    """A keep-out seen square to the host: a disc, and the clearance around it."""

    feature: str
    centre: np.ndarray
    radius: float
    clearance: float

    def blocks(self, uv: np.ndarray, half_width: float) -> np.ndarray:
        return np.linalg.norm(uv - self.centre, axis=1) < self.radius + self.clearance + half_width

    def row(self) -> dict:
        return {
            "feature": self.feature,
            "centre": [round(float(v), 2) for v in self.centre],
            "radius_mm": round(self.radius, 2),
            "clearance_mm": self.clearance,
        }


def _keep_outs(
    features: FeatureSet,
    atlas: Atlas,
    tess: Tessellation,
    placement: Placement,
    frame: HostFrame,
    host: Feature,
) -> list[_Disc]:
    host_faces = set(host.face_ids)
    touching = {n for f in host_faces for n in atlas.faces[f].neighbours}
    discs = []
    for keep in placement.keep_out:
        chosen = [features.get(f) for f in keep.features]
        for kind in keep.kinds:
            for feature in features.features.values():
                if str(feature.kind) != kind:
                    continue
                on_host = host_faces.intersection(feature.opens_onto) or touching.intersection(
                    feature.face_ids
                )
                if on_host:
                    chosen.append(feature)
        for feature in chosen:
            discs.append(_disc(features, tess, frame, feature, keep.clearance_mm))
    return discs


def _disc(features, tess, frame, feature: Feature, clearance: float) -> _Disc:
    """A keep-out seen square to the host: centred on the feature itself, as wide as it reaches.

    Centred on the feature's own middle, never on its axis line - a hole running sideways through a
    wall at the host's edge has an axis whose nearest point to anything can be far away.
    """
    mine = np.isin(tess.face_id, list(feature.face_ids))
    points = frame.to_plane(tess.vertices[np.unique(tess.triangles[mine])])
    centre = frame.to_plane(np.asarray(feature.centroid, dtype=float).reshape(1, 3))[0]
    radius = float(np.max(np.linalg.norm(points - centre, axis=1)))
    return _Disc(feature=feature.id, centre=centre, radius=radius, clearance=clearance)


def _clearance(keep: list[_Disc], a: np.ndarray, b: np.ndarray, half_width: float) -> float | None:
    """The smallest gap between the rib's side and any keep-out's edge, seen square to the host."""
    if not keep:
        return None
    gaps = []
    for k in keep:
        ab = b - a
        t = np.clip((k.centre - a) @ ab / max(ab @ ab, 1e-12), 0.0, 1.0)
        gaps.append(float(np.linalg.norm(a + t * ab - k.centre)) - k.radius - half_width)
    return round(min(gaps), 2)


# --- height ---------------------------------------------------------------------------------------


def _caps(features: FeatureSet, tess: Tessellation, placement: Placement, frame: HostFrame) -> dict:
    """The heights above the host that named features and a given height allow."""
    caps = {}
    level = float(frame.origin @ frame.normal)
    for ref in placement.height.not_above:
        _, top = extent(tess, features.get(ref).face_ids, tuple(frame.normal))
        caps[ref] = round(top - level, 3)
    if placement.height.max_mm is not None:
        caps["given"] = placement.height.max_mm
    return caps


def _height(
    caps: dict, tops: list[float | None], placement: Placement
) -> tuple[list[float] | None, str]:
    """How tall a rib stands at each end: no taller than what that end meets, than any feature
    named as a cap, or than a height given - times the fraction asked for. An end that meets
    nothing takes the other's height; a level top is held to the lower end all the way along."""
    heights: list[float | None] = []
    whys: list[str] = []
    for side, top in zip(("first support", "second support"), tops, strict=True):
        limits = dict(caps)
        if top is not None:
            limits[side] = top
        why = min(limits, key=limits.get) if limits else ""
        heights.append(float(limits[why]) if limits else None)
        whys.append(why)
    if heights[0] is None and heights[1] is None:
        return None, "nothing limits the height: name a height, or a feature ribs stay below"
    for i in (0, 1):
        if heights[i] is None:
            heights[i], whys[i] = heights[1 - i], whys[1 - i]
    if placement.height.top == "level":
        low = 0 if heights[0] <= heights[1] else 1
        heights, whys = [heights[low]] * 2, [whys[low]] * 2
    fraction = placement.height.fraction
    why = whys[0] if whys[0] == whys[1] else f"{whys[0]}, {whys[1]}"
    return [float(h) * fraction for h in heights], why


def _count(placed: Placed, reason: str) -> None:
    placed.dropped[reason] = placed.dropped.get(reason, 0) + 1
