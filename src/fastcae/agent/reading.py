"""What the agent reads off a part: one job to each function, for the agent to compose.

- **What a feature stands on**: the flat faces a boss or a wall rises from - and those a bore opens
  onto, or that top a boss - reached across the fillets and chamfers at its foot.
- **What rises round a floor**: walls, bosses and bores, past the blends at its edges, each with
  how far it stands above the floor.
- **What lies across** the open space in front of a feature, straight out of its metal, and **what
  lies between** things: the way they run together, and what is under and over the space between
  them.
- **The part's axes**, and the bores, bosses and holes on each, largest first.
- **How thick the metal is** through a face.

Everything is read from what extraction found - the CAD's faces, the features on them, its
tessellated surface - with rays cast through that surface where a question needs them. Nothing here
changes the part or decides anything about it: every answer names what it found by id, with a few
words, so the agent can match it to what the engineer said - and ask when it cannot.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from ..extract import Extraction
from ..features import Feature, FeatureKind, FeatureSet, extent
from ..geometry.brep import Tessellation

# A flat face is square to an axis when its normal is within this of it.
SQUARE = math.cos(math.radians(10.0))

# Faces a walk may cross to reach a floor: the fillets, rounds and chamfers at a feature's foot.
BLENDS = ("torus", "sphere", "bspline", "cone", "cylinder")

# What a face belongs to, most telling first.
TELLING = (FeatureKind.BORE, FeatureKind.BOSS, FeatureKind.HOLE, FeatureKind.PLANAR_GROUP)

# What rises from where ribs stand is found by walking out across blends - fillets of any shape,
# chamfers - to the first faces that stand up. A face stands up when it is at least this steep.
STANDS_UP = math.cos(math.radians(45.0))
BLEND_DEPTH = 3


def stands_on(extraction: Extraction, ref: str, most: int = 8) -> list[dict]:
    """The flat faces at the foot and the ends of a feature, and how it stands to each: ``rises
    from`` - it stands up from that face, on the side the face looks - ``opens onto`` for a bore
    that goes down from it, ``tops it`` for a face at the far end of a boss or wall. Those it rises
    from come first, largest first.

    A round feature is walked out from with every face it is stacked with on its axis - a boss the
    CAD made of bands, fillets and chamfers stands on the floor at the foot of the stack, whichever
    band is named. Floors at one level are said together, ``level_with`` each other - the CAD often
    splits a floor - and ``round`` says whether, together, they go more than halfway round the
    feature: whether spokes could go all the way round it."""
    features, atlas, tess = extraction.features, extraction.atlas, extraction.tess
    assert features is not None and atlas is not None and tess is not None
    feature = features.get(ref)
    if feature is None:
        raise ValueError(f"the part has no {ref}")
    first = features.faces[feature.face_ids[0]]
    axis = None if first.axis is None else np.asarray(first.axis, dtype=float)
    plane = None if axis is not None or first.normal is None else np.asarray(first.normal, float)
    mine = set(feature.face_ids)
    if feature.axis_id and feature.axis_id in features.axes and axis is not None:
        mine |= _stack(atlas, mine, set(features.axes[feature.axis_id].face_ids), axis)
    # How far the stack reaches from its axis: a step between two of its bands lies within it.
    radii = [atlas.faces[f].radius_mm for f in mine if atlas.faces[f].radius_mm is not None]
    seen = set(mine)
    frontier = [(n, 0) for f in sorted(mine) for n in atlas.faces[f].neighbours]
    flat: set[int] = set()
    while frontier:
        face_id, depth = frontier.pop(0)
        if face_id in seen:
            continue
        seen.add(face_id)
        face = atlas.faces[face_id]
        if face.surface_type == "plane" and face.normal is not None:
            normal = np.asarray(face.normal, dtype=float)
            square_to_axis = axis is not None and abs(float(normal @ axis)) > SQUARE
            square_to_wall = plane is not None and abs(float(normal @ plane)) < 1.0 - SQUARE
            if square_to_axis or square_to_wall:
                flat.add(face_id)
            if square_to_axis and radii and _within(tess, face_id, first, min(radii), max(radii)):
                # A step between bands of the stack: the stack goes on past it.
                frontier.extend((n, depth) for n in face.neighbours)
            continue
        if depth < BLEND_DEPTH and face.surface_type in BLENDS:
            frontier.extend((n, depth + 1) for n in face.neighbours)

    out: dict[str, dict] = {}
    tolerance = max(features.diagonal_mm * 1e-4, 1e-3)
    for face_id in sorted(flat):
        group = _owner(features, face_id, (FeatureKind.PLANAR_GROUP,))
        if group in out:
            continue
        base = features.get(group)
        assert base is not None
        normal = np.asarray(atlas.faces[face_id].normal, dtype=float)
        level = float(np.asarray(atlas.faces[face_id].centroid) @ normal)
        _, top = extent(tess, feature.face_ids, tuple(normal))
        if top > level + tolerance:
            relation = "rises from"
        else:
            relation = "opens onto" if first.concave else "tops it"
        out[group] = {
            "ref": group,
            "relation": relation,
            "round": None,
            "facing": [round(float(v), 3) for v in normal],
            "level_mm": round(level * float(np.sign(normal[int(np.argmax(np.abs(normal)))])), 1),
            "area_mm2": round(base.area_mm2),
            "about": names(features, [group])[group],
            "_normal": normal,
            "_level": level,
        }
    # Floors at one level, facing one way, are one floor the CAD split: said together.
    for entry in out.values():
        together = [
            other
            for other in out.values()
            if float(other["_normal"] @ entry["_normal"]) > SQUARE
            and abs(other["_level"] - entry["_level"]) < max(tolerance, 0.5)
        ]
        entry["level_with"] = [o["ref"] for o in together if o["ref"] != entry["ref"]]
        if axis is not None and first.axis_point is not None:
            faces = [f for o in together for f in features.get(o["ref"]).face_ids]
            mesh = np.isin(tess.face_id, faces)
            entry["round"] = bool(_surrounds(tess.vertices[np.unique(tess.triangles[mesh])], first))
    for entry in out.values():
        del entry["_normal"], entry["_level"]
    order = {"rises from": 0, "opens onto": 1, "tops it": 2}
    ranked = sorted(out.values(), key=lambda b: (order[b["relation"]], -b["area_mm2"]))
    return ranked[:most]


def _within(tess, face_id: int, round_face, low: float, high: float) -> bool:
    """Whether a flat face lies wholly between two radii of a round face's axis - a step between
    bands of one stack, not a floor spreading out from it or a cap across it."""
    mesh = np.isin(tess.face_id, [face_id])
    points = tess.vertices[np.unique(tess.triangles[mesh])]
    axis = np.asarray(round_face.axis, dtype=float)
    offset = points - np.asarray(round_face.axis_point, dtype=float)
    radial = np.linalg.norm(offset - np.outer(offset @ axis, axis), axis=1)
    slack = max(0.02 * high, 0.5)
    return bool(radial.min() >= low - slack and radial.max() <= high + slack)


def _stack(atlas, start: set[int], on_axis: set[int], axis: np.ndarray) -> set[int]:
    """The faces on one axis joined to ``start`` - through each other, or through a flat step
    square to the axis between them: the bands, fillets and chamfers one round feature is made of,
    not every face that happens to share the axis."""
    stack, frontier = set(start), list(start)

    def step(face) -> bool:
        return (
            face.surface_type == "plane"
            and face.normal is not None
            and abs(float(np.asarray(face.normal, dtype=float) @ axis)) > SQUARE
        )

    while frontier:
        face_id = frontier.pop()
        for n in atlas.faces[face_id].neighbours:
            reach = [n]
            if n not in on_axis and step(atlas.faces[n]):
                reach = list(atlas.faces[n].neighbours)
            for m in reach:
                if m in on_axis and m not in stack:
                    stack.add(m)
                    frontier.append(m)
    return stack


def rises_round(extraction: Extraction, refs: list[str], most: int = 40) -> dict:
    """What stands up round a floor - faces in one plane - past the fillets and chamfers at its
    edges, on the side it faces: walls, bosses, bores, each with how far it stands above the
    floor, tallest first. Holes are not walls."""
    features, atlas, tess = extraction.features, extraction.atlas, extraction.tess
    assert features is not None and atlas is not None and tess is not None
    host, why = host_of(features, refs)
    if host is None:
        raise ValueError(why)
    normal = np.asarray(host.normal, dtype=float)
    level = float(np.dot(host.centroid, normal))
    holes = {f for h in features.of_kind(FeatureKind.HOLE) for f in h.face_ids}
    found = _walls_around(atlas, set(host.face_ids), normal, holes, level)
    grouped: dict[str, list[int]] = {}
    for face_id in found:
        grouped.setdefault(_owner(features, face_id, TELLING), []).append(face_id)
    rows = []
    for ref, faces in grouped.items():
        _, top = extent(tess, tuple(faces), tuple(normal))
        rows.append(
            {
                "ref": ref,
                "faces": [f"face:{f}" for f in faces],
                "stands_mm": round(top - level, 1),
                "about": names(features, [ref])[ref],
            }
        )
    rows.sort(key=lambda row: -row["stands_mm"])
    return {
        "floor": list(refs),
        "facing": [round(float(v), 3) for v in normal],
        "round": rows[:most],
    }


def across(extraction: Extraction, finder, ref: str, most: int = 6, rays: int = 200) -> dict:
    """What lies across the open space in front of an entity: from points spread over its faces,
    straight out of the metal, the first things met - each named by the feature it belongs to, with
    how much of the entity looks at it and how far away it is - and how much looks out of the part.
    The wall a web from it would reach, the face opposite it across a gap."""
    features, tess = extraction.features, extraction.tess
    assert features is not None and tess is not None
    feature = features.get(ref)
    if feature is None:
        raise ValueError(f"the part has no {ref}")
    mine = np.flatnonzero(np.isin(tess.face_id, list(feature.face_ids)))
    corners = tess.vertices[tess.triangles[mine]]
    normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    areas = np.linalg.norm(normals, axis=1)
    usable = areas > 1e-12
    corners, normals, areas = corners[usable], normals[usable], areas[usable]
    normals /= areas[:, None]
    chosen = np.random.default_rng(0).choice(
        len(areas), size=rays, p=areas / areas.sum(), replace=True
    )
    # From the middle of each chosen facet, a hair out of the metal, straight out.
    lift = max(features.diagonal_mm * 1e-5, 1e-3)
    origins = corners[chosen].mean(axis=1) + lift * normals[chosen]
    hits, which, triangles = finder.mesh.ray.intersects_location(
        origins, normals[chosen], multiple_hits=False
    )
    met: dict[str, list[float]] = {}
    for location, ray, triangle in zip(hits, which, triangles, strict=True):
        owner = _owner(features, int(tess.face_id[int(triangle)]), TELLING)
        met.setdefault(owner, []).append(float(np.linalg.norm(location - origins[ray])))
    rows = [
        {
            "ref": other,
            "share": round(len(gaps) / rays, 2),
            "gap_mm": [round(min(gaps), 1), round(float(np.median(gaps)), 1), round(max(gaps), 1)],
            "about": names(features, [other])[other],
        }
        for other, gaps in met.items()
    ]
    rows.sort(key=lambda row: -row["share"])
    return {
        "from": ref,
        "out_of_the_part": round(1.0 - len(which) / rays, 2),
        "across": [row for row in rows if row["ref"] != ref][:most],
        "itself": next((row["share"] for row in rows if row["ref"] == ref), 0.0),
    }


def between(extraction: Extraction, finder, refs: list[str], rays: int = 120) -> dict:
    """What lies between things: the way they run together, the heights they share along it, and
    what is under and over the open space between them - from points halfway across it, straight
    down and straight up - each named by its feature, with how far past where they begin or end it
    is, and for how much of the space. Something right where they begin is a floor that ribs between
    them can stand on; open space there means webs with nothing under them."""
    features, tess = extraction.features, extraction.tess
    assert features is not None and tess is not None
    hang, problem = hang_frame(features, tess, refs)
    if hang is None:
        return {"between": list(refs), "stand_on": None, "says": problem}
    frame, band = hang.frame, hang.band
    step = max(features.diagonal_mm * 1e-3, 1.0)
    middle = band / 2.0
    points = {
        ref: _sliced(tess, features.get(ref).face_ids, frame, (middle,), step) for ref in hang.joins
    }
    # Halfway across from each thing to its nearest other - where they face each other, not from
    # the far end of a long wall: points in the space between them.
    halfway, gaps = [], []
    named = [ref for ref in hang.joins if len(points[ref])]
    for ref in named:
        others = np.concatenate([points[r] for r in named if r != ref])
        mine = points[ref][:: max(1, len(points[ref]) // 60)]
        distance = np.linalg.norm(mine[:, None] - others[None], axis=2)
        nearest = np.argmin(distance, axis=1)
        halfway.append((mine + others[nearest]) / 2.0)
        gaps.append(distance[np.arange(len(mine)), nearest])
    if not halfway:
        said = "nothing of them at the heights they share"
        return {"between": list(refs), "stand_on": None, "says": said}
    gap = np.concatenate(gaps)
    if float(np.median(gap)) < max(3.0 * step, 5.0):
        said = "they meet: there is no space between them"
        return {"between": list(hang.joins), "stand_on": None, "says": said}
    across = np.concatenate(halfway)
    # Halfway across open space is well clear of every one of them; halfway between two faces
    # round a corner of one piece lies on one of the faces.
    every = np.concatenate([points[r] for r in named])
    clear = np.array([float(np.min(np.linalg.norm(every - m, axis=1))) for m in across])
    spaced = (gap > max(3.0 * step, 5.0)) & (gap <= 1.5 * float(np.median(gap)))
    across = across[spaced & (clear >= 0.25 * gap)]
    if not len(across):
        said = "they meet, or face away from each other: there is no open space between them"
        return {"between": list(hang.joins), "stand_on": None, "says": said}
    across = across[np.random.default_rng(0).permutation(len(across))[:rays]]
    level = float(frame.origin @ frame.normal)
    out: dict[str, Any] = {
        "between": list(hang.joins),
        "running_along": _signed(frame.normal),
        "from_mm": round(level, 1),
        "to_mm": round(level + band, 1),
    }
    if len(hang.joins) < len(refs):
        out["taking_no_part"] = [r for r in refs if r not in hang.joins]
    # Only what is in the open: halfway between two faces of one piece is the piece itself.
    solid = finder.mesh.contains(frame.to_world(across, middle))
    out["open"] = round(1.0 - float(solid.mean()), 2)
    across = across[~solid]
    # A few points on an edge of the piece are neither in it nor out of it.
    if out["open"] < 0.1:
        out["stand_on"] = None
        out["note"] = "metal fills the space between them where they face each other: one piece"
        out["says"] = out["note"]
        return out
    out["stand_on"] = None
    for name, sense, past in (("under", -1.0, middle), ("over", 1.0, middle)):
        origins = frame.to_world(across, middle)
        hits, which, triangles = finder.mesh.ray.intersects_location(
            origins, np.tile(sense * frame.normal, (len(origins), 1)), multiple_hits=False
        )
        met: dict[str, list[float]] = {}
        for location, ray, triangle in zip(hits, which, triangles, strict=True):
            owner = _owner(features, int(tess.face_id[int(triangle)]), TELLING)
            beyond = float(np.linalg.norm(location - origins[ray])) - past
            met.setdefault(owner, []).append(round(max(beyond, 0.0), 1))
        rows = [
            {
                "ref": r,
                "share": round(len(d) / len(origins), 2),
                "past_them_mm": round(float(np.median(d)), 1),
            }
            for r, d in met.items()
        ]
        rows.sort(key=lambda row: -row["share"])
        out[name] = {"open_share": round(1.0 - len(which) / len(origins), 2), "met": rows[:5]}
        # Right where they begin or end - a fillet's width off - under or over most of the space.
        at = next(
            (r for r in rows if r["share"] >= 0.5 and r["past_them_mm"] <= max(10.0, 0.1 * band)),
            None,
        )
        if at is not None and out["stand_on"] is None:
            out["stand_on"] = {"ref": at["ref"], "side": name}
    if out["stand_on"] is not None:
        ref, side = out["stand_on"]["ref"], out["stand_on"]["side"]
        out["says"] = f"{ref} lies right {side} most of the space between them: ribs stand on it"
    else:
        out["says"] = (
            "nothing under or over most of the space between them, near where they begin or end: "
            "ribs between them are webs with nothing under them"
        )
    return out


def axes(extraction: Extraction, most: int = 8) -> list[dict]:
    """The part's axes that carry bores, bosses or holes, the largest first, each with what is on
    it - largest first - its direction and a point on it."""
    features = extraction.features
    assert features is not None
    on: dict[str, list[Feature]] = {}
    for feature in features.features.values():
        kinds = (FeatureKind.BORE, FeatureKind.BOSS, FeatureKind.HOLE)
        if feature.axis_id and feature.kind in kinds and feature.diameter_mm:
            on.setdefault(feature.axis_id, []).append(feature)
    ranked = sorted(on.items(), key=lambda item: -max(f.diameter_mm or 0.0 for f in item[1]))
    out = []
    for axis_id, members in ranked[:most]:
        axis = features.axes[axis_id]
        members.sort(key=lambda f: -(f.diameter_mm or 0.0))
        out.append(
            {
                "id": axis_id,
                "direction": _signed(axis.direction),
                "point": [round(float(v), 1) for v in axis.point],
                "features": [
                    {"ref": f.id, "kind": str(f.kind), "diameter_mm": round(f.diameter_mm or 0, 1)}
                    for f in members[:10]
                ],
            }
        )
    return out


def thickness_at(extraction: Extraction, exit_along, ref: str) -> float | None:
    """How thick the metal is under a face: a ray into the metal from the middle of its largest
    facet, square to it - through a plate, a wall, the rim of a boss or a bore."""
    if extraction.features is not None and extraction.features.get(ref) is None:
        raise ValueError(f"the part has no {ref}")
    return _through(extraction, exit_along, ref)


def _owner(features, face_id: int, kinds: tuple) -> str:
    """The feature a face is best named by: the first of ``kinds`` holding it, or the face."""
    held = features.containing(face_id)
    for kind in kinds:
        for feature in held:
            if feature.kind == kind:
                return feature.id
    return f"face:{face_id}"


def _signed(direction) -> list[float]:
    """A direction with its largest part positive: an axis runs both ways."""
    d = np.asarray(direction, dtype=float)
    if d[int(np.argmax(np.abs(d)))] < 0.0:
        d = -d
    return [round(float(v), 3) + 0.0 for v in d]


# --- a floor, and what stands up round it ---------------------------------------------------------


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


def _walls_around(
    atlas, host_faces: set[int], normal: np.ndarray, hole_faces: set[int], level: float
) -> list[int]:
    """What stands up round where ribs stand - walls, bosses, bores - reached across whatever
    blends into it at its edge: a fillet of any shape, a chamfer. Only on the side ribs stand on:
    past a round on the outer edge of a floor is the outside of the part, falling away below it.
    Holes are not walls, and nothing is looked for past a hole."""
    tolerance = max(atlas.diagonal_mm * 1e-4, 1e-3)
    found: set[int] = set()
    seen = set(host_faces)
    frontier = [(n, 0) for f in sorted(host_faces) for n in atlas.faces[f].neighbours]
    while frontier:
        face_id, depth = frontier.pop(0)
        if face_id in seen:
            continue
        seen.add(face_id)
        face = atlas.faces[face_id]
        if face_id in hole_faces or float(np.dot(face.centroid, normal)) - level < tolerance:
            continue
        if _rises(face, normal):
            found.add(face_id)
        elif depth < BLEND_DEPTH and _blends(face, normal):
            frontier.extend((n, depth + 1) for n in face.neighbours)
    return sorted(found)


def _rises(face, normal: np.ndarray) -> bool:
    """Whether a face stands up from a surface facing ``normal``, as a wall or a boss does."""
    if face.surface_type == "plane" and face.normal is not None:
        return abs(float(np.dot(face.normal, normal))) < STANDS_UP
    if face.surface_type in ("cylinder", "cone") and face.axis is not None:
        return abs(float(np.dot(face.axis, normal))) > 0.7
    if face.surface_type == "bspline" and face.flatness > 0.9:
        return abs(float(np.dot(face.facing, normal))) < STANDS_UP
    return False


def _blends(face, normal: np.ndarray) -> bool:
    """Whether a face is a way across from where ribs stand to something else: a fillet, a round,
    a chamfer - not a step to another flat area."""
    if face.surface_type in ("torus", "sphere", "bspline"):
        return True
    if face.surface_type in ("cylinder", "cone"):
        return True
    if face.surface_type == "plane" and face.normal is not None:
        return abs(float(np.dot(face.normal, normal))) < 0.98
    return False


def _surrounds(points: np.ndarray, face) -> bool:
    """Whether points lie round more than half of a face of revolution, outside it: a floor round
    a boss standing in it, or beside a bore it fans out from - not a floor inside a ring wall."""
    axis = np.asarray(face.axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    offset = points - np.asarray(face.axis_point, dtype=float)
    radial = offset - np.outer(offset @ axis, axis)
    distance = np.linalg.norm(radial, axis=1)
    if len(points) < 3 or float(np.median(distance)) <= face.radius_mm:
        return False
    reference = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = reference - (reference @ axis) * axis
    u = u / np.linalg.norm(u)
    v = np.cross(axis, u)
    angles = np.sort(np.degrees(np.arctan2(radial @ v, radial @ u)) % 360.0)
    gaps = np.diff(np.concatenate([angles, [angles[0] + 360.0]]))
    return float(gaps.max()) < 180.0


# --- webs with nothing under them -----------------------------------------------------------------


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


# A round face runs along a direction within this of its axis; a flat one, when its normal is within
# this of square to the direction.
ALONG = math.cos(math.radians(10.0))
SQUARE_TO = math.sin(math.radians(10.0))


@dataclass(frozen=True)
class Level:
    """A height webs may hang from, along the way they stand: how far past it they may reach, and
    which of the things named they join there."""

    at: float
    band: float
    joins: tuple[str, ...]


@dataclass(frozen=True)
class Hang:
    """Where webs with nothing under them stand: the plane their paths are drawn on, how far along
    its normal they may reach past it, and which of the things named they join there - and every
    height a web may hang from, lowest first, that one among them."""

    frame: HostFrame
    band: float
    joins: tuple[str, ...]
    levels: tuple[Level, ...] = ()


# Heights webs may hang from closer than this are one: the highest of them, where all are.
LEVELS_APART_MM = 5.0
# The most heights a web is looked for at.
MOST_LEVELS = 8


def hang_frame(
    features: FeatureSet,
    tess: Tessellation,
    supports: list[str],
    pull=None,
    other_side: list[str] | tuple[str, ...] = (),
) -> tuple[Hang | None, str]:
    """For webs with nothing under them: where they stand, or None and why.

    Webs that run from something round - ``other_side`` names what they run to, the rest of
    ``supports`` what they run from - stand along its axis: the webs of a bearing stand along the
    bearing, whatever else is named. Otherwise they stand along the direction the most of the
    things named run along - the axis of a round one, the line two flat ones meet along, else one
    of the part's own axes - the pull first among equals, then the axis of a round thing: a thing
    runs along a direction when most of its faces do.

    They join those things, from the level where the most of them are present - of both sides,
    when there are two - as far up as all of those go, so a web standing there meets every one.
    Each web may hang from any height where both of its ends can begin: every height one of the
    things named begins at, where two of them are present - one of each side - is among
    ``levels``. Things that run along some other way, or are elsewhere, take no part."""
    found = [features.get(ref) for ref in supports]
    missing = [ref for ref, f in zip(supports, found, strict=True) if f is None]
    if missing:
        return None, f"the part has no {', '.join(missing)}"
    if len(found) < 2:
        return None, "a web with nothing under it joins two things or more: name what it joins"
    far = set(other_side)

    def sided(refs: list[str]) -> bool:
        """Both sides among them, when there are two; else two things or more."""
        if not far:
            return len(refs) >= 2
        return any(r in far for r in refs) and any(r not in far for r in refs)

    n = None
    if far:
        axis = _round_axis(
            features, [f for ref, f in zip(supports, found, strict=True) if ref not in far]
        )
        if axis is not None:
            ran = [
                ref
                for ref, f in zip(supports, found, strict=True)
                if _runs_along(features, f, axis)
            ]
            n = axis if sided(ran) else None
    if n is None:
        n, problem = _most_along(features, supports, found, pull)
        if n is None:
            return None, problem
    # Up is the pull's way, or - with none - the way the direction's largest part points.
    sign = float(n @ np.asarray(pull, dtype=float)) if pull is not None else n[np.abs(n).argmax()]
    if sign < 0.0:
        n = -n
    along = [ref for ref, f in zip(supports, found, strict=True) if _runs_along(features, f, n)]
    spans = {ref: extent(tess, features.get(ref).face_ids, tuple(n)) for ref in along}

    def present(level: float) -> list[str]:
        return [r for r, (lo, hi) in spans.items() if lo <= level + 1e-6 and hi >= level + 1.0]

    # Heights where things begin, those within a few millimetres of each other one - the highest
    # of them, where every one of them is - where webs can join something on each side.
    heights: list[float] = []
    first = -math.inf
    for z in sorted({lo for lo, _ in spans.values()}):
        if z - first < LEVELS_APART_MM:
            heights[-1] = z
        else:
            heights.append(z)
            first = z
    heights = [z for z in heights if sided(present(z))]
    if not heights:
        said = ", ".join(f"{ref} {lo:.0f} to {hi:.0f}" for ref, (lo, hi) in spans.items())
        joined = "join them" if not far else "run from one side to the other"
        return None, (
            f"{', '.join(supports)} do not overlap along {_way(n)} ({said} mm), so no web can "
            f"{joined}"
        )
    level = max(heights, key=lambda z: len(present(z)))
    if len(heights) > MOST_LEVELS:
        # As many as that, spread evenly from the lowest to the highest - the main one kept.
        picks = {
            heights[round(k * (len(heights) - 1) / (MOST_LEVELS - 1))] for k in range(MOST_LEVELS)
        }
        heights = sorted({*picks, level})
    joins = present(level)
    top = min(spans[ref][1] for ref in joins)
    centre = np.mean([np.asarray(features.get(r).centroid, dtype=float) for r in joins], axis=0)
    frame = _frame_at(centre + (level - float(centre @ n)) * n, n)
    levels = tuple(
        Level(at=z, band=min(spans[r][1] for r in present(z)) - z, joins=tuple(present(z)))
        for z in heights
    )
    return Hang(frame=frame, band=top - level, joins=tuple(joins), levels=levels), ""


def _round_axis(features: FeatureSet, found: list[Feature]) -> np.ndarray | None:
    """The axis of what webs run from, when it is round - most of its faces, by area, turn about
    an axis, as a bearing's do: the largest of those faces' axis. None for anything else."""
    faces = [features.faces[i] for f in found for i in f.face_ids]
    turning = [f for f in faces if f.surface_type in ("cylinder", "cone") and f.axis is not None]
    flat = [f for f in faces if f.surface_type == "plane" and f.normal is not None]
    if not turning or sum(f.area for f in turning) < sum(f.area for f in flat):
        return None
    axis = np.asarray(max(turning, key=lambda f: f.area).axis, dtype=float)
    return axis / np.linalg.norm(axis)


def _most_along(
    features: FeatureSet, supports: list[str], found: list[Feature], pull
) -> tuple[np.ndarray | None, str]:
    """The direction the most of the things named run along - the pull first among equals, then
    the axis of a round thing, the line two flat ones meet along, else one of the part's own axes.
    Or None and why."""
    faces = [features.faces[i] for f in found for i in f.face_ids]
    axes = sorted(
        (face for face in faces if face.surface_type in ("cylinder", "cone") and face.axis),
        key=lambda face: -face.area_mm2,
    )
    flats = sorted(
        (face for face in faces if face.surface_type == "plane" and face.normal is not None),
        key=lambda face: -face.area_mm2,
    )
    candidates = [] if pull is None else [np.asarray(pull, dtype=float)]
    candidates += [np.asarray(face.axis, dtype=float) for face in axes[:3]]
    for i, first in enumerate(flats[:4]):
        for second in flats[i + 1 : 4]:
            across = np.cross(np.asarray(first.normal), np.asarray(second.normal))
            if np.linalg.norm(across) > 0.2:
                candidates.append(across)
    # With nothing else to go by - flat faces all facing one way or the other - the part's own axes.
    candidates += [np.eye(3)[2], np.eye(3)[1], np.eye(3)[0]]
    candidates = [c / np.linalg.norm(c) for c in candidates if np.linalg.norm(c) > 1e-9]
    # Which of the things named run along each candidate; the first with the most wins.
    along = [
        [ref for ref, f in zip(supports, found, strict=True) if _runs_along(features, f, c)]
        for c in candidates
    ]
    best = max(range(len(candidates)), key=lambda k: (len(along[k]), -k), default=None)
    if best is None or len(along[best]) < 2:
        return None, (
            f"{', '.join(supports)} share no direction a web could stand along - name it, or "
            "something for the webs to stand on"
        )
    return candidates[best], ""


def _runs_along(features: FeatureSet, feature: Feature, d: np.ndarray) -> bool:
    """Whether a thing runs along a direction: most of its round faces turn about it, and its flat
    ones stand square to it - by area, blends aside."""
    counted = ran = 0.0
    for face in (features.faces[i] for i in feature.face_ids):
        if face.surface_type in ("cylinder", "cone") and face.axis is not None:
            counted += face.area_mm2
            ran += face.area_mm2 * (abs(float(np.asarray(face.axis) @ d)) > ALONG)
        elif face.surface_type == "plane" and face.normal is not None:
            counted += face.area_mm2
            ran += face.area_mm2 * (abs(float(np.asarray(face.normal) @ d)) < SQUARE_TO)
    return counted > 0.0 and ran >= 0.5 * counted


def _way(n: np.ndarray) -> str:
    """A direction in words: the axis it is, or its parts."""
    for i, name in enumerate("xyz"):
        if abs(n[i]) > 0.999:
            return name
    return "(" + ", ".join(f"{v:.2f}" for v in n) + ")"


def _frame_at(origin: np.ndarray, normal: np.ndarray) -> HostFrame:
    n = normal / np.linalg.norm(normal)
    reference = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = reference - (reference @ n) * n
    e1 = e1 / np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    return HostFrame(origin=origin, normal=n, e1=e1, e2=e2)


def _sliced(tess: Tessellation, face_ids, frame: HostFrame, heights, step: float) -> np.ndarray:
    """Where faces cross the planes ``heights`` above the frame's, as points on its plane about a
    ``step`` apart - what a big face with few corners is at those heights - with the corners of its
    facets that lie between the lowest and highest."""
    mine = np.isin(tess.face_id, list(face_ids))
    corners = tess.vertices[tess.triangles[mine]]
    along = corners @ frame.normal - float(frame.origin @ frame.normal)
    out = [corners[(along >= min(heights)) & (along <= max(heights))]]
    for height in heights:
        d = along - height
        crossing = (d.min(axis=1) < 0.0) & (d.max(axis=1) > 0.0)
        ends = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            di, dj = d[crossing, i], d[crossing, j]
            t = np.where((di < 0.0) != (dj < 0.0), di / np.where(di == dj, 1.0, di - dj), np.nan)
            ends.append(
                corners[crossing, i] + t[:, None] * (corners[crossing, j] - corners[crossing, i])
            )
        ends = np.stack(ends, axis=1)
        found = ~np.isnan(ends[:, :, 0])
        pairs = [row[ok][:2] for row, ok in zip(ends, found, strict=True) if ok.sum() >= 2]
        for p, q in pairs:
            n = int(math.ceil(float(np.linalg.norm(q - p)) / step)) + 1
            out.append(p + np.outer(np.linspace(0.0, 1.0, n), q - p))
    points = np.concatenate([o.reshape(-1, 3) for o in out]) if out else np.zeros((0, 3))
    return frame.to_plane(points) if len(points) else np.zeros((0, 2))


# --- what things are called, and how thick the metal is -------------------------------------------


def names(features: FeatureSet, refs: list[str]) -> dict[str, str]:
    """A few words for each ref, for the card to show beside it."""
    out = {}
    for ref in refs:
        feature = features.get(ref)
        if feature is None:
            out[ref] = "not on the part"
            continue
        if feature.kind == FeatureKind.FACE:
            face = features.faces[feature.face_ids[0]]
            text = f"{face.surface_type}, {face.area:,.0f} mm²"
            if face.diameter_mm is not None and face.surface_type in ("cylinder", "cone"):
                text += f", Ø{face.diameter_mm:.1f}"
        elif feature.kind == FeatureKind.HOLE:
            text = f"hole, Ø{feature.diameter_mm:.1f}" if feature.diameter_mm else "hole"
        else:
            text = f"{feature.kind}, {feature.area_mm2:,.0f} mm², {len(feature.face_ids)} faces"
        out[ref] = text
    return out


def _through(extraction, exit_along, ref: str) -> float | None:
    """How thick the metal is under a face or a feature: a ray into the metal from the middle of
    its largest facet, square to it - through a plate, a wall, the rim of a boss or a bore."""
    features, tess = extraction.features, extraction.tess
    feature = features.get(ref) if features is not None else None
    if feature is None or exit_along is None:
        return None
    mine = np.flatnonzero(np.isin(tess.face_id, list(feature.face_ids)))
    if not mine.size:
        return None
    corners = tess.vertices[tess.triangles[mine]]
    cross = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    largest = int(np.argmax(np.linalg.norm(cross, axis=1)))
    centre = corners[largest].mean(axis=0)
    face = features.faces[int(tess.face_id[mine[largest]])]
    if face.surface_type == "plane" and face.normal is not None:
        inward = -np.asarray(face.normal, dtype=float)
    elif face.axis is not None and face.axis_point is not None:
        direction = np.asarray(face.axis, dtype=float)
        offset = centre - np.asarray(face.axis_point, dtype=float)
        radial = offset - (offset @ direction) * direction
        radial = radial / max(float(np.linalg.norm(radial)), 1e-12)
        inward = radial if face.concave else -radial
    else:
        inward = -cross[largest] / max(float(np.linalg.norm(cross[largest])), 1e-12)
    found = exit_along(centre + inward * 0.05, inward)
    return round(float(found), 2) if found else None
