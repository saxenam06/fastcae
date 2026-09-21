"""Reading an engineer's picks: the axis a design volume is measured along, how far along it and
out from it the volume goes, and the round thing its ribs would grow from.

- **The axis** is that of the largest round face picked - a boss, a bore's collar, a round wall -
  or, when only flat faces are picked, the largest bore standing square to the largest flat one
  within its outline, else that face's own normal through its middle.
- **The band** along the axis: from a floor, towards the side it faces, as far as the tallest round
  thing standing round the axis goes - "up to the height of the bearing's boss"; between faces with
  no floor, the heights all of them share. The engineer may set it.
- **The anchor** is the round thing ribs would grow from: the round faces picked, or - from a
  floor - the bosses standing on it round the axis, the innermost first.
- **The reach** from the axis: as far as the walls the anchor faces - rays cast straight out from it
  across the band, to the first metal - or as far as a wall picked goes, whichever is further, and a
  margin past it, so a wall is reached through its fillets.

Nothing here knows what the part is for: faces, bores and their axes decide.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from ..features import FeatureKind

if TYPE_CHECKING:
    from ..extract import Extraction

# How far past the picks the region reaches from the axis, at the least: past the fillets at a
# wall's foot to the wall itself.
MARGIN_MM = 30.0

# A floor stands square to the axis within this.
SQUARE = math.cos(math.radians(8.0))

# Two axes are one when they lean less than this and pass within AXIS_TOL_MM of each other.
PARALLEL = math.cos(math.radians(2.0))

AXIS_TOL_MM = 2.0

# Without a round thing to stand as tall as, a band from a floor is this deep.
DEFAULT_STAND_MM = 100.0


@dataclass
class Frame:
    """The axis a volume is measured along, and the side its floor faces."""

    axis: np.ndarray
    point: np.ndarray
    round_face: int | None = None
    """The round pick the axis came from, when one did."""
    bore: str | None = None
    """The bore a floor's axis was taken from, when one was."""

    def along(self, points: np.ndarray) -> np.ndarray:
        return (np.asarray(points, float) - self.point) @ self.axis

    def radial(self, points: np.ndarray) -> np.ndarray:
        offset = np.asarray(points, float) - self.point
        return np.linalg.norm(offset - np.outer(offset @ self.axis, self.axis), axis=1)


_BY_FACE: dict[int, tuple[object, dict[int, np.ndarray]]] = {}


def face_points(extraction: Extraction, face_id: int) -> np.ndarray:
    """The vertices of one face's triangles; every face's found once per triangulation."""
    tess = extraction.tess
    assert tess is not None
    held = _BY_FACE.get(id(tess))
    if held is None or held[0] is not tess:
        order = np.argsort(tess.face_id, kind="stable")
        ids, starts = np.unique(tess.face_id[order], return_index=True)
        ends = np.append(starts[1:], len(order))
        table = {
            int(i): tess.vertices[np.unique(tess.triangles[order[a:b]])]
            for i, a, b in zip(ids, starts, ends, strict=True)
        }
        _BY_FACE.clear()
        _BY_FACE[id(tess)] = (tess, table)
        held = _BY_FACE[id(tess)]
    found = held[1].get(int(face_id))
    if found is None:
        raise ValueError(f"face:{face_id} has no triangles")
    return found


def unit(v) -> np.ndarray:  # type: ignore[no-untyped-def]
    v = np.asarray(v, float)
    return v / max(float(np.linalg.norm(v)), 1e-12)


def bores(extraction: Extraction) -> list[dict[str, Any]]:
    """Every bore: its axis, radius, own extent and depth."""
    features, atlas = extraction.features, extraction.atlas
    assert features is not None and atlas is not None
    out = []
    for bore in features.of_kind(FeatureKind.BORE):
        walls = [
            atlas.faces[f]
            for f in bore.face_ids
            if f in atlas.faces and atlas.faces[f].axis is not None
        ]
        if not walls or walls[0].axis_point is None:
            continue
        axis = unit(walls[0].axis)
        point = np.asarray(walls[0].axis_point, float)
        radius = max((w.radius_mm or 0.0) for w in walls)
        points = np.concatenate([face_points(extraction, f) for f in bore.face_ids])
        s = (points - point) @ axis
        out.append(
            {
                "id": bore.id,
                "axis": axis,
                "point": point,
                "radius": float(radius),
                "lo": float(s.min()),
                "hi": float(s.max()),
            }
        )
    return out


def frame_of(extraction: Extraction, faces: list[int]) -> tuple[Frame, str]:
    """The axis a volume is measured along, and whether the picks hold a floor."""
    atlas = extraction.atlas
    assert atlas is not None
    records = [atlas.faces[f] for f in faces if f in atlas.faces]
    if len(records) != len(faces):
        missing = sorted(set(faces) - set(atlas.faces))
        raise ValueError(f"the part has no {', '.join(f'face:{f}' for f in missing)}")
    round_ = [
        r
        for r in records
        if r.surface_type in ("cylinder", "cone")
        and r.axis is not None
        and r.axis_point is not None
    ]
    flat = [r for r in records if r.surface_type == "plane" and r.normal is not None]
    if round_:
        pick = max(round_, key=lambda r: r.area)
        frame = Frame(unit(pick.axis), np.asarray(pick.axis_point, float), round_face=pick.face_id)
    elif flat:
        floor = max(flat, key=lambda r: r.area)
        normal = unit(floor.normal)
        outline = face_points(extraction, floor.face_id)
        middle = outline.mean(axis=0)
        span = float(np.linalg.norm(outline - middle, axis=1).max())
        best = None
        for bore in bores(extraction):
            if abs(float(bore["axis"] @ normal)) < PARALLEL:
                continue
            offset = middle - bore["point"]
            off_axis = float(np.linalg.norm(offset - (offset @ bore["axis"]) * bore["axis"]))
            if off_axis <= span and (best is None or bore["radius"] > best["radius"]):
                best = bore
        if best is not None:
            frame = Frame(best["axis"], best["point"], bore=best["id"])
        else:
            frame = Frame(normal, middle)
    else:
        raise ValueError("pick a flat face or a round one: a floor, a boss, a wall")
    # A floor among the picks: flat and square to the axis.
    floors = [r for r in flat if abs(float(unit(r.normal) @ frame.axis)) > SQUARE]
    return frame, ("floor" if floors else "between")


def default_band(
    extraction: Extraction, faces: list[int], frame: Frame, kind: str
) -> tuple[float, float]:
    """From a floor, as far as the tallest round thing on the axis goes on the side it faces;
    between picks, the heights all of them share."""
    atlas = extraction.atlas
    assert atlas is not None
    if kind == "floor":
        floors = [
            atlas.faces[f]
            for f in faces
            if atlas.faces[f].surface_type == "plane"
            and atlas.faces[f].normal is not None
            and abs(float(unit(atlas.faces[f].normal) @ frame.axis)) > SQUARE
        ]
        floor = max(floors, key=lambda r: r.area)
        side = 1.0 if float(unit(floor.normal) @ frame.axis) > 0 else -1.0
        level = float(frame.along(face_points(extraction, floor.face_id)).mean())
        # The tallest round thing standing on this axis from the floor, on the side it faces:
        # a boss, a collar, the band of a bore.
        stand = 0.0
        for face in atlas.faces.values():
            if face.surface_type not in ("cylinder", "cone") or face.axis is None:
                continue
            if face.axis_point is None or abs(float(unit(face.axis) @ frame.axis)) < PARALLEL:
                continue
            offset = np.asarray(face.axis_point, float) - frame.point
            if np.linalg.norm(offset - (offset @ frame.axis) * frame.axis) > AXIS_TOL_MM:
                continue
            s = frame.along(face_points(extraction, face.face_id)) - level
            s = s * side
            # It stands on the floor: starts at it (within a few mm) and goes out from it.
            if s.min() > -1.0 and s.min() < 5.0 and s.max() > stand:
                stand = float(s.max())
        # A rim a few millimetres tall is no height for a rib: a floor's own default instead.
        stand = stand if stand >= 20.0 else DEFAULT_STAND_MM
        ends = sorted((level, level + side * stand))
        return float(ends[0]), float(ends[1])
    ranges = [frame.along(face_points(extraction, f)) for f in faces]
    lo = max(float(s.min()) for s in ranges)
    hi = min(float(s.max()) for s in ranges)
    if hi - lo < 1.0:
        lo = min(float(s.min()) for s in ranges)
        hi = max(float(s.max()) for s in ranges)
    return lo, hi


def anchors_of(
    extraction: Extraction, faces: list[int], frame: Frame, band: tuple[float, float], kind: str
) -> list[int]:
    """The round faces ribs would grow from: those picked, coaxial with the axis - or, from a floor,
    the bosses standing on it round the axis within the band, the innermost ones."""
    atlas = extraction.atlas
    assert atlas is not None

    def coaxial(face) -> bool:  # type: ignore[no-untyped-def]
        if face.surface_type not in ("cylinder", "cone") or face.axis is None:
            return False
        if face.axis_point is None or abs(float(unit(face.axis) @ frame.axis)) < PARALLEL:
            return False
        offset = np.asarray(face.axis_point, float) - frame.point
        return bool(np.linalg.norm(offset - (offset @ frame.axis) * frame.axis) <= AXIS_TOL_MM)

    picked = [f for f in faces if coaxial(atlas.faces[f])]
    if picked:
        return picked
    if kind != "floor":
        return []
    found = []
    for face in atlas.faces.values():
        if not coaxial(face) or face.concave:
            continue
        points = face_points(extraction, face.face_id)
        s = frame.along(points)
        if s.max() < band[0] or s.min() > band[1]:
            continue
        found.append((float(frame.radial(points).max()), face.face_id))
    if not found:
        return []
    inner = min(r for r, _ in found)
    return [f for r, f in found if r <= 1.5 * inner]


def rays_out(
    extraction: Extraction, frame: Frame, band: tuple[float, float], start: float
) -> np.ndarray:
    """From ``start`` mm off the axis, straight out at every 5 deg and three heights across the
    band: how far from the axis each ray first meets metal (NaN where it meets none)."""
    tess = extraction.tess
    assert tess is not None
    s = frame.along(tess.vertices)
    span = s[tess.triangles]
    triangles = tess.triangles[
        (span.max(axis=1) >= band[0] - 5.0) & (span.min(axis=1) <= band[1] + 5.0)
    ]
    u = np.cross(frame.axis, [1.0, 0.0, 0.0] if abs(frame.axis[0]) < 0.9 else [0.0, 1.0, 0.0])
    u /= np.linalg.norm(u)
    v = np.cross(frame.axis, u)
    out = []
    for height in np.linspace(band[0], band[1], 5)[1:-1]:
        for angle in np.radians(np.arange(0.0, 360.0, 5.0)):
            direction = math.cos(angle) * u + math.sin(angle) * v
            origin = frame.point + height * frame.axis + start * direction
            hit = first_hit(extraction, origin, direction, triangles)
            out.append(np.nan if hit is None else start + hit)
    return np.asarray(out)


def reach(
    extraction: Extraction,
    faces: list[int],
    frame: Frame,
    band: tuple[float, float],
    anchors: list[int],
) -> float:
    """How far from the axis the region goes: as far as the furthest wall the anchor faces - or as
    far as a wall picked goes, whichever is further - and the margin past it."""
    atlas = extraction.atlas
    assert atlas is not None
    far = 0.0
    walls = [
        f
        for f in faces
        if f not in anchors
        and not (
            atlas.faces[f].surface_type == "plane"
            and atlas.faces[f].normal is not None
            and abs(float(unit(atlas.faces[f].normal) @ frame.axis)) > SQUARE
        )
    ]
    for f in walls if anchors else faces:
        points = face_points(extraction, f)
        s = frame.along(points)
        inside = (s >= band[0] - 1.0) & (s <= band[1] + 1.0)
        chosen = points[inside] if inside.any() else points
        far = max(far, float(frame.radial(chosen).max()))
    if anchors:
        start = max(float(frame.radial(face_points(extraction, f)).max()) for f in anchors) + 1.0
        hits = rays_out(extraction, frame, band, start)
        hits = hits[np.isfinite(hits)]
        if len(hits):
            # To the furthest wall the rays meet: the corners of a box as well as its sides. What
            # lies past the part's own outline is cut off slice by slice, so a ray that leaves
            # through a window cannot carry the volume outside.
            far = max(far, float(hits.max()))
    return far + max(MARGIN_MM, 0.05 * far)


def first_hit(
    extraction: Extraction,
    origin: np.ndarray,
    direction: np.ndarray,
    triangles: np.ndarray | None = None,
) -> float | None:
    """How far along ``direction`` from ``origin`` the part's surface is first met, if at all -
    among ``triangles`` when given."""
    tess = extraction.tess
    assert tess is not None
    v = tess.vertices
    t = tess.triangles if triangles is None else triangles
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    e1, e2 = b - a, c - a
    p = np.cross(direction, e2)
    det = np.einsum("ij,ij->i", e1, p)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    s = origin - a
    u = np.einsum("ij,ij->i", s, p) * inv
    q = np.cross(s, e1)
    w = (q @ direction) * inv
    dist = np.einsum("ij,ij->i", e2, q) * inv
    hit = ok & (u >= 0) & (w >= 0) & (u + w <= 1) & (dist > 1e-6)
    return float(dist[hit].min()) if hit.any() else None


def near_line(
    extraction: Extraction, point: np.ndarray, axis: np.ndarray, radius: float
) -> np.ndarray:
    """The part's triangles with a corner within ``radius`` of a line, and a triangle's size more:
    all a ray parallel to the line, within that radius of it, can meet."""
    tess = extraction.tess
    assert tess is not None
    offset = tess.vertices - point
    off_line = np.linalg.norm(offset - np.outer(offset @ axis, axis), axis=1)
    corners = tess.vertices[tess.triangles]
    size = np.linalg.norm(corners - corners.mean(axis=1, keepdims=True), axis=2).max()
    # A point a ray meets on a triangle lies within twice this of every corner.
    close = off_line <= radius + 2.0 * size
    return tess.triangles[close[tess.triangles].any(axis=1)]


def runs_past(
    extraction: Extraction,
    bores: list[dict[str, Any]],
    bore: dict[str, Any],
    side: float,
    station: float,
) -> float | None:
    """Past one end of a bore: how far open air runs along its axis before metal - or what sits in
    another bore, which closes it - or None when it runs out of the part.

    Probed from the axis and from four points half the radius out, the most of them deciding: a
    single ray down the axis can leave through another bore's opening and call the part's inside
    outside."""
    axis, point, radius = bore["axis"], bore["point"], bore["radius"]
    u = np.cross(axis, [1.0, 0.0, 0.0] if abs(axis[0]) < 0.9 else [0.0, 1.0, 0.0])
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    centre = point + axis * station
    origins = [centre] + [
        centre + 0.5 * radius * (math.cos(a) * u + math.sin(a) * v)
        for a in (0.0, 0.5 * math.pi, math.pi, 1.5 * math.pi)
    ]
    direction = side * axis
    near = near_line(extraction, point, axis, radius)
    found: list[float | None] = []
    for origin in origins:
        # From half a millimetre inside the bore: an end closed by metal is met at once.
        start = origin - direction * 0.5
        best = first_hit(extraction, start, direction, near)
        for other in bores:
            if other is bore or abs(float(other["axis"] @ axis)) < PARALLEL:
                continue
            offset = start - other["point"]
            if np.linalg.norm(offset - (offset @ other["axis"]) * other["axis"]) > other["radius"]:
                continue
            s0 = float(offset @ other["axis"])
            sense = float(direction @ other["axis"])
            if other["lo"] - 1.0 <= s0 <= other["hi"] + 1.0:
                enter = 0.0
            elif sense > 0 and s0 < other["lo"]:
                enter = other["lo"] - s0
            elif sense < 0 and s0 > other["hi"]:
                enter = s0 - other["hi"]
            else:
                continue
            best = enter if best is None else min(best, enter)
        found.append(best)
    closed = [f for f in found if f is not None]
    if len(closed) * 2 <= len(found):
        return None
    return max(float(np.median(closed)) - 0.5, 0.0)
