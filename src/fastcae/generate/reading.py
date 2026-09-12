"""Reading the part for the agent: one job to each function, for the agent to compose.

- **What a feature stands on**: the flat faces a boss or a wall rises from - and those a bore opens
  onto, or that top a boss - reached across the fillets and chamfers at its foot.
- **What rises round a floor**: walls, bosses and bores, past the blends at its edges, each with
  how far it stands above the floor.
- **The part's axes**, and the bores, bosses and holes on each, largest first.
- **How thick the metal is** through a face.

Nothing here decides where ribs go. Every answer names what it found by id, with a few words, so
the agent can match it to what the engineer said - and ask when it cannot.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from ..extract import Extraction
from ..features import Feature, FeatureKind, extent
from .placement import _sliced, hang_frame, host_of
from .slots import BLEND_DEPTH, _surrounds, _through, _walls_around, names

# A flat face is square to an axis when its normal is within this of it.
SQUARE = math.cos(math.radians(10.0))

# Faces a walk may cross to reach a floor: the fillets, rounds and chamfers at a feature's foot.
BLENDS = ("torus", "sphere", "bspline", "cone", "cylinder")

# What a face belongs to, most telling first.
TELLING = (FeatureKind.BORE, FeatureKind.BOSS, FeatureKind.HOLE, FeatureKind.PLANAR_GROUP)


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
