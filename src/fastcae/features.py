"""Generic geometric feature detection.

What this module knows: cylinders, cones, planes, axes, holes arranged on a circle. What it must
never know: bearings, gearboxes, ribs, flanges, brackets or shafts. A concave cylinder is a **bore**
whether it carries a bearing, a bush in a linkage, or nothing at all. Whether it is *controlled* is
a separate claim, made by a drawing, and established in :mod:`fastcae.extract`.

The split matters because it decides what has to be rewritten when the next part arrives. Kinds are
universal, so they live in code. Roles are per-part, so they live in data. A module that detects
"the dowels that locate a ring gear" has to be edited before a bracket can load; one that detects
"equal holes repeated on a circle" does not.

Every threshold here is expressed relative to the part's own size rather than in absolute
millimetres, for the same reason. A 5 mm hole is small on a 1.3 m casting and structural on a
40 mm bracket.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np

from .geometry.atlas import Atlas, FaceRecord

# Two axes are the same axis when their directions are parallel to within this angle and their
# lines pass within this fraction of the part's diagonal of each other.
AXIS_ANGLE_TOL_DEG = 1.0
AXIS_DISTANCE_TOL_FRACTION = 1e-3

# A hole is "small" below this fraction of the part diagonal. Everything larger is treated as a
# bore in its own right rather than as a member of a fastener pattern.
SMALL_HOLE_FRACTION = 0.03

# Circle fits accept this residual, relative to the fitted radius.
PATTERN_FIT_TOLERANCE = 0.02

# A pattern needs at least this many members. Two holes define a line, not a pattern.
MIN_PATTERN_COUNT = 3

# A pattern that does not wrap the full circle needs more members before it is believable. Three
# holes of equal size will always lie on *some* circle - three points always do - so accepting
# three on an arc turns every coincidence into a feature. On this housing that produced sixteen
# phantom patterns with pitch circles up to 7e15 mm across.
MIN_ARC_PATTERN_COUNT = 5


class FeatureKind(StrEnum):
    """Geometric kinds. Universal by construction - each is defined by shape alone."""

    AXIS = "axis"
    """A line about which one or more faces are rotationally arranged."""

    BORE = "bore"
    """A concave cylinder: material outside, void inside. Any hole large enough to matter."""

    BOSS = "boss"
    """A convex cylinder: material inside. A shaft journal, a spigot, a pin."""

    HOLE_PATTERN = "hole_pattern"
    """Equal holes repeated on a circle or a line. Fastener circles, dowel rings, bolt rows."""

    PLANAR_GROUP = "planar_group"
    """Coplanar faces. Mounting faces, split lines, machined pads."""

    FILLET = "fillet"
    """A toroidal or spherical blend between two surfaces."""


@dataclass(frozen=True)
class Axis:
    """A rotational axis shared by a set of faces.

    ``point`` is canonicalised to the axis's closest approach to the origin, so two descriptions of
    the same line compare equal regardless of which face proposed them.
    """

    id: str
    direction: tuple[float, float, float]
    point: tuple[float, float, float]
    face_ids: tuple[int, ...]
    area_mm2: float = 0.0
    """Total face area on this axis. Axes are ordered by it, so A0 is always the dominant one.

    Area rather than face count, because a part can have one enormous bore and a ring of thirty
    tiny holes, and the bore is what anyone means by "the main axis".
    """

    def station(self, position: tuple[float, float, float]) -> float:
        """How far along the axis a point lies, measured from ``point``."""
        delta = np.asarray(position) - np.asarray(self.point)
        return float(np.dot(delta, np.asarray(self.direction)))

    def radius_to(self, position: tuple[float, float, float]) -> float:
        """Perpendicular distance from the axis."""
        delta = np.asarray(position) - np.asarray(self.point)
        along = np.dot(delta, np.asarray(self.direction))
        return float(np.linalg.norm(delta - along * np.asarray(self.direction)))

    def describe(self) -> str:
        dx, dy, dz = self.direction
        px, py, pz = self.point
        return (
            f"{self.id}: through ({px:.1f}, {py:.1f}, {pz:.1f}) "
            f"along ({dx:.3f}, {dy:.3f}, {dz:.3f}), {len(self.face_ids)} faces"
        )


@dataclass
class Feature:
    """One detected feature, described only in geometric terms.

    ``metrics`` is a free bag rather than a fixed schema because different kinds measure different
    things, and forcing a bore to carry a ``pitch_deg`` of None teaches every consumer to check for
    nulls that cannot occur.
    """

    id: str
    kind: FeatureKind
    face_ids: tuple[int, ...]
    area_mm2: float
    axis_id: str | None = None
    diameter_mm: float | None = None
    station_mm: float | None = None
    centroid: tuple[float, float, float] = (0.0, 0.0, 0.0)
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return int(self.metrics.get("count", len(self.face_ids)))

    def describe(self) -> str:
        bits = [self.id, str(self.kind)]
        if self.diameter_mm is not None:
            bits.append(f"O{self.diameter_mm:.2f}")
        if self.count > 1:
            bits.append(f"x{self.count}")
        if self.station_mm is not None:
            bits.append(f"@{self.station_mm:.1f}")
        bits.append(f"{self.area_mm2:,.0f} mm2")
        return "  ".join(bits)


@dataclass
class FeatureSet:
    """Everything detected on one geometry."""

    axes: dict[str, Axis] = field(default_factory=dict)
    features: dict[str, Feature] = field(default_factory=dict)
    diagonal_mm: float = 0.0

    def of_kind(self, kind: FeatureKind) -> list[Feature]:
        return [f for f in self.features.values() if f.kind is kind]

    def on_axis(self, axis_id: str) -> list[Feature]:
        return [f for f in self.features.values() if f.axis_id == axis_id]

    def significant_axes(self, area_fraction: float = 0.01) -> list[Axis]:
        """Axes worth showing, in order of importance.

        A part with hundreds of small holes has hundreds of axes, one per hole, and every one is
        real. Almost none are interesting: what a person means by "the axes" is the handful that
        organise the part - this casting has 752 and three that matter.

        An axis earns a place by carrying a **detected feature**, which is the same thing as being
        addressable: a bore, a boss or a hole pattern sits on it and can be selected, measured or
        named. Small tappings never become features, so their axes drop out without needing a size
        threshold tuned to any particular part. The area share is a second door, so a large bore
        that happens to sit alone still appears.
        """
        total = sum(a.area_mm2 for a in self.axes.values()) or 1.0
        carrying = {f.axis_id for f in self.features.values() if f.axis_id}
        return [
            axis
            for axis in self.axes.values()
            if axis.id in carrying or axis.area_mm2 / total >= area_fraction
        ]

    def containing(self, face_id: int) -> list[Feature]:
        return [f for f in self.features.values() if face_id in f.face_ids]

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = defaultdict(int)
        for feature in self.features.values():
            out[str(feature.kind)] += 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def detect(atlas: Atlas, bbox_mm: tuple[float, float, float, float, float, float]) -> FeatureSet:
    """Find every generic feature on a part.

    Order matters: axes first, because bores, bosses and patterns are all described relative to one.
    """
    x0, y0, z0, x1, y1, z1 = bbox_mm
    diagonal = float(math.dist((x0, y0, z0), (x1, y1, z1)))

    result = FeatureSet(diagonal_mm=diagonal)
    result.axes = _detect_axes(atlas, diagonal)

    _detect_cylindrical(atlas, result, diagonal)
    _detect_hole_patterns(atlas, result, diagonal)
    _detect_planar_groups(atlas, result, diagonal)
    _detect_fillets(atlas, result)

    return result


def _detect_axes(atlas: Atlas, diagonal: float) -> dict[str, Axis]:
    """Group every face that has an axis onto shared axis lines.

    Cylinders, cones and tori all carry one. Two faces share an axis when their directions are
    parallel and their lines are coincident - not merely when the directions match, since a part
    is full of parallel holes that are nowhere near each other.

    Axes are ordered by how much face area sits on them, so the dominant axis of any part is
    ``A0`` whether that is a shaft centreline or a bracket's main bore.
    """
    distance_tol = diagonal * AXIS_DISTANCE_TOL_FRACTION
    angle_tol = math.radians(AXIS_ANGLE_TOL_DEG)

    candidates: list[tuple[np.ndarray, np.ndarray, int, float]] = []
    for face in atlas.faces.values():
        if face.axis is None or face.axis_point is None:
            continue
        direction = np.asarray(face.axis, dtype=float)
        norm = float(np.linalg.norm(direction))
        if norm < 1e-9:
            continue
        direction = direction / norm
        # Canonical sense: an axis and its reverse are the same line, so fix the sign by the
        # first non-zero component. Without this, two halves of one bore land on two axes.
        for component in direction:
            if abs(component) > 1e-9:
                if component < 0:
                    direction = -direction
                break
        candidates.append(
            (
                direction,
                _closest_point_to_origin(direction, np.asarray(face.axis_point)),
                face.face_id,
                face.area,
            )
        )

    groups: list[dict] = []
    for direction, point, face_id, area in candidates:
        for group in groups:
            if abs(float(np.dot(direction, group["direction"]))) < math.cos(angle_tol):
                continue
            if float(np.linalg.norm(point - group["point"])) > distance_tol:
                continue
            group["faces"].append(face_id)
            group["area"] += area
            break
        else:
            groups.append(
                {"direction": direction, "point": point, "faces": [face_id], "area": area}
            )

    groups.sort(key=lambda g: -g["area"])
    return {
        f"A{index}": Axis(
            id=f"A{index}",
            direction=tuple(float(v) for v in group["direction"]),
            point=tuple(float(v) for v in group["point"]),
            face_ids=tuple(sorted(group["faces"])),
            area_mm2=float(group["area"]),
        )
        for index, group in enumerate(groups)
    }


def _closest_point_to_origin(direction: np.ndarray, point: np.ndarray) -> np.ndarray:
    """Canonical representative of a line: its closest approach to the origin.

    Any point on a line describes it, which means the same line has infinitely many descriptions
    and none of them compare equal. Projecting out the component along the direction leaves one.
    """
    return point - float(np.dot(point, direction)) * direction


def _detect_cylindrical(atlas: Atlas, result: FeatureSet, diagonal: float) -> None:
    """Concave cylinders become bores, convex ones bosses.

    Concavity is the whole distinction and it is already measured: a face whose material lies
    outside the surface is a hole, one whose material lies inside is a protrusion. No domain
    knowledge is involved, which is why it transfers to any part.
    """
    axis_of_face = _face_to_axis(result)
    small = diagonal * SMALL_HOLE_FRACTION

    for face in atlas.of_type("cylinder"):
        if face.radius_mm is None or face.concave is None:
            continue
        # Small holes are left for pattern detection, which describes them far better as a group
        # than as thirty separate one-face bores.
        if face.concave and face.radius_mm < small:
            continue

        kind = FeatureKind.BORE if face.concave else FeatureKind.BOSS
        axis_id = axis_of_face.get(face.face_id)
        axis = result.axes.get(axis_id) if axis_id else None
        feature_id = f"{kind}:{face.face_id}"
        result.features[feature_id] = Feature(
            id=feature_id,
            kind=kind,
            face_ids=(face.face_id,),
            area_mm2=face.area,
            axis_id=axis_id,
            diameter_mm=face.diameter_mm,
            station_mm=None if axis is None else axis.station(face.centroid),
            centroid=face.centroid,
            metrics={"radius_mm": face.radius_mm},
        )


def _detect_hole_patterns(atlas: Atlas, result: FeatureSet, diagonal: float) -> None:
    """Find repeated equal holes arranged on a circle or a line.

    Generic on purpose: take the small holes, group them by diameter and axis direction, then ask
    whether their centres fit a circle. A bolt circle on a flange and a dowel ring are the same
    detection.

    **Only circles.** A straight row of holes is a real pattern and is not found here - collinear
    centres fit a circle of enormous radius, which the size bound below rejects. Linear patterns
    need their own fit.

    The reported pitch is the *grid* pitch, not 360/count. On this housing's stud circle, 30 holes
    sit on a 9 degree grid with gaps - the circle has 40 positions and 30 are used. Reporting
    360/30 = 12 degrees would describe a pattern that is not there.
    """
    small = diagonal * SMALL_HOLE_FRACTION
    holes = [
        face
        for face in atlas.of_type("cylinder")
        if face.radius_mm is not None and face.concave and face.radius_mm < small
    ]
    if len(holes) < MIN_PATTERN_COUNT:
        return

    buckets: dict[tuple[int, int, int, int], list[FaceRecord]] = defaultdict(list)
    for face in holes:
        if face.axis is None:
            continue
        direction = np.asarray(face.axis, dtype=float)
        for component in direction:
            if abs(component) > 1e-9:
                if component < 0:
                    direction = -direction
                break
        key = (
            round(face.radius_mm * 100),
            *(int(round(v * 100)) for v in direction),
        )
        buckets[key].append(face)

    index = 0
    for members in buckets.values():
        if len(members) < MIN_PATTERN_COUNT:
            continue
        direction = np.asarray(members[0].axis, dtype=float)
        direction = direction / float(np.linalg.norm(direction))
        centres = np.array([m.centroid for m in members], dtype=float)

        fit = _fit_circle(centres, direction)
        if fit is None:
            continue
        centre, radius, residual = fit

        # A pattern cannot be larger than the part it is on. Nearly collinear centres send the
        # algebraic fit off to an enormous radius that satisfies a *relative* residual test
        # trivially, which is how a row of three holes became a 7e15 mm pitch circle.
        if not math.isfinite(radius) or 2.0 * radius > diagonal:
            continue
        if residual > PATTERN_FIT_TOLERANCE * max(radius, 1e-6):
            continue

        angles = _angles_about(centres, centre, direction)
        # Wrapping the circle is itself strong evidence of intent. An arc is not, so it has to
        # earn belief through member count instead.
        if not _spans_full_circle(angles) and len(members) < MIN_ARC_PATTERN_COUNT:
            continue
        feature_id = f"hole_pattern:{index}"
        index += 1
        result.features[feature_id] = Feature(
            id=feature_id,
            kind=FeatureKind.HOLE_PATTERN,
            face_ids=tuple(sorted(m.face_id for m in members)),
            area_mm2=sum(m.area for m in members),
            axis_id=_axis_through(result, centre, direction),
            diameter_mm=2.0 * members[0].radius_mm,
            station_mm=None,
            centroid=tuple(float(v) for v in centre),
            metrics={
                "count": float(len(members)),
                "pitch_circle_diameter_mm": 2.0 * radius,
                "grid_pitch_deg": _angular_grid(angles),
                "fit_residual_mm": residual,
                "spans_full_circle": float(_spans_full_circle(angles)),
            },
        )


def _detect_planar_groups(atlas: Atlas, result: FeatureSet, diagonal: float) -> None:
    """Group coplanar faces into the interfaces a document would name.

    A mounting face is rarely one face - it is a ring, a pad, or a set of lands split by pockets.
    Grouping by plane rather than by connectivity finds the whole interface, which is what a
    document callout usually means.
    """
    tolerance = diagonal * 1e-4
    buckets: dict[tuple[int, int, int, int], list[FaceRecord]] = defaultdict(list)

    for face in atlas.of_type("plane"):
        if face.normal is None:
            continue
        normal = np.asarray(face.normal, dtype=float)
        for component in normal:
            if abs(component) > 1e-9:
                if component < 0:
                    normal = -normal
                break
        offset = float(np.dot(normal, np.asarray(face.centroid)))
        key = (
            *(int(round(v * 1000)) for v in normal),
            int(round(offset / max(tolerance, 1e-9))),
        )
        buckets[key].append(face)

    index = 0
    for members in buckets.values():
        area = sum(m.area for m in members)
        # A plane worth naming carries real area. Below a thousandth of the part's projected
        # size it is a chamfer land or a sliver, and listing those buries the interfaces.
        if area < (diagonal**2) * 1e-4:
            continue
        feature_id = f"planar_group:{index}"
        index += 1
        centre = np.average(
            np.array([m.centroid for m in members]),
            axis=0,
            weights=np.array([max(m.area, 1e-9) for m in members]),
        )
        result.features[feature_id] = Feature(
            id=feature_id,
            kind=FeatureKind.PLANAR_GROUP,
            face_ids=tuple(sorted(m.face_id for m in members)),
            area_mm2=area,
            centroid=tuple(float(v) for v in centre),
            metrics={
                "count": float(len(members)),
                "exterior": float(any(m.exterior for m in members)),
            },
        )


def _detect_fillets(atlas: Atlas, result: FeatureSet) -> None:
    """Toroidal and spherical blends, grouped into tangent-connected chains.

    Useful generically for two reasons: a fillet chain is usually the boundary of the feature it
    blends, and a part's smallest fillet radius bounds how fine a discretisation has to be before
    it resolves the geometry at all.
    """
    blends = {f.face_id for f in atlas.of_type("torus")} | {
        f.face_id for f in atlas.of_type("sphere")
    }
    if not blends:
        return

    seen: set[int] = set()
    index = 0
    for face_id in sorted(blends):
        if face_id in seen:
            continue
        chain = {face_id}
        frontier = [face_id]
        while frontier:
            current = atlas[frontier.pop()]
            for neighbour_id, angle in current.dihedral.items():
                if neighbour_id in chain or neighbour_id not in blends or angle > 15.0:
                    continue
                chain.add(neighbour_id)
                frontier.append(neighbour_id)
        seen |= chain

        radii = [atlas[i].minor_radius_mm or atlas[i].radius_mm or 0.0 for i in chain]
        feature_id = f"fillet:{index}"
        index += 1
        result.features[feature_id] = Feature(
            id=feature_id,
            kind=FeatureKind.FILLET,
            face_ids=tuple(sorted(chain)),
            area_mm2=sum(atlas[i].area for i in chain),
            centroid=atlas[face_id].centroid,
            metrics={
                "count": float(len(chain)),
                "min_radius_mm": float(min(radii)) if radii else 0.0,
                "max_radius_mm": float(max(radii)) if radii else 0.0,
            },
        )


def _face_to_axis(result: FeatureSet) -> dict[int, str]:
    return {face_id: axis.id for axis in result.axes.values() for face_id in axis.face_ids}


def _axis_through(result: FeatureSet, point: np.ndarray, direction: np.ndarray) -> str | None:
    """The detected axis a pattern is centred on, if any.

    A fastener circle is usually concentric with a bore, and saying so is what lets a document
    callout that names one find the other.
    """
    # Concentricity judged relative to the model. A fixed millimetre allowance is tight on a
    # small part and meaningless on a large one, and this decides whether two features are
    # described as sharing an axis at all.
    tolerance = max(result.diagonal_mm * AXIS_DISTANCE_TOL_FRACTION, 1e-3)
    best: tuple[float, str] | None = None
    for axis in result.axes.values():
        axis_direction = np.asarray(axis.direction)
        if abs(float(np.dot(axis_direction, direction))) < math.cos(
            math.radians(AXIS_ANGLE_TOL_DEG)
        ):
            continue
        distance = axis.radius_to(tuple(float(v) for v in point))
        if best is None or distance < best[0]:
            best = (distance, axis.id)
    return None if best is None or best[0] > tolerance else best[1]


def _fit_circle(
    centres: np.ndarray, direction: np.ndarray
) -> tuple[np.ndarray, float, float] | None:
    """Least-squares circle through points projected onto the plane perpendicular to ``direction``.

    Kasa's algebraic fit: linear, closed-form, and entirely adequate here because the points are
    machined hole centres rather than noisy measurements. Returns the centre in 3D, the radius, and
    the RMS residual, which is what decides whether these holes really are a pattern.
    """
    if centres.shape[0] < MIN_PATTERN_COUNT:
        return None

    origin = centres.mean(axis=0)
    basis_u = np.cross(direction, [0.0, 0.0, 1.0])
    if float(np.linalg.norm(basis_u)) < 1e-6:
        basis_u = np.cross(direction, [0.0, 1.0, 0.0])
    basis_u = basis_u / float(np.linalg.norm(basis_u))
    basis_v = np.cross(direction, basis_u)

    local = centres - origin
    u = local @ basis_u
    v = local @ basis_v

    matrix = np.column_stack([u, v, np.ones_like(u)])
    rhs = u**2 + v**2
    try:
        solution, *_ = np.linalg.lstsq(matrix, rhs, rcond=None)
    except np.linalg.LinAlgError:
        return None

    cu, cv = solution[0] / 2.0, solution[1] / 2.0
    radius_squared = solution[2] + cu**2 + cv**2
    if radius_squared <= 0:
        return None
    radius = math.sqrt(radius_squared)

    residual = float(np.sqrt(np.mean((np.hypot(u - cu, v - cv) - radius) ** 2)))
    centre = origin + cu * basis_u + cv * basis_v
    return centre, radius, residual


def _angles_about(points: np.ndarray, centre: np.ndarray, direction: np.ndarray) -> list[float]:
    basis_u = np.cross(direction, [0.0, 0.0, 1.0])
    if float(np.linalg.norm(basis_u)) < 1e-6:
        basis_u = np.cross(direction, [0.0, 1.0, 0.0])
    basis_u = basis_u / float(np.linalg.norm(basis_u))
    basis_v = np.cross(direction, basis_u)
    local = points - centre
    return sorted(
        math.degrees(math.atan2(float(p @ basis_v), float(p @ basis_u))) % 360.0 for p in local
    )


def _angular_grid(angles: list[float]) -> float:
    """The coarsest angular pitch every member sits on.

    The greatest common divisor of the gaps, not 360 divided by the count. A circle with forty
    positions and thirty holes in them has a 9 degree pitch; dividing by the count would report 12
    and describe a pattern that does not exist.

    Returns NaN rather than a spurious fraction when the gaps share no meaningful divisor, because
    a pitch of 0.01 degrees is not a pitch - it means the holes are not on a grid at all.
    """
    gaps = [round(b - a, 2) for a, b in zip(angles, angles[1:], strict=False) if b - a > 0.05]
    if not gaps:
        return math.nan
    grid = int(round(gaps[0] * 100))
    for gap in gaps[1:]:
        grid = math.gcd(grid, int(round(gap * 100)))
    pitch = grid / 100.0
    return pitch if pitch >= 0.5 else math.nan


def _spans_full_circle(angles: list[float]) -> bool:
    """Whether the members wrap the whole circle or occupy an arc.

    A bolt circle wraps; three holes in a bracket ear do not, and calling that a circular pattern
    would be a stretch worth flagging.
    """
    if len(angles) < MIN_PATTERN_COUNT:
        return False
    gaps = [b - a for a, b in zip(angles, angles[1:], strict=False)]
    gaps.append(360.0 - angles[-1] + angles[0])
    return max(gaps) < 180.0
