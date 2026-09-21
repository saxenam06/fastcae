"""Which faces meet something else: the interfaces, each with the evidence that says so.

Four kinds of evidence hold a face - the deck loads it, the deck holds it, the drawing tolerances
it, or a hole the deck holds or loads opens onto it. Three are weak - it looks machined, a hole
pattern the deck does not mention opens onto it, or it is a bore the deck does not mention. A face
is then grown into the whole of what it belongs to: the rest of the same bore (coaxial, same
radius, touching) or the rest of the same plane (coplanar, touching).

Nothing here knows what a face is for. A bearing seat and a pin bore are both concave cylinders the
deck couples to a loaded point.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

import numpy as np

from ..features import AXIS_DISTANCE_TOL_FRACTION, FeatureKind, FeatureSet, _coaxial
from ..geometry.atlas import Atlas, FaceRecord
from .model import Evidence, Interface, Params

PLANE_ANGLE_TOL_DEG = 0.5


def deck_roles(setup: Any) -> dict[str, tuple[Evidence, str]]:
    """What the deck does to each group that lies on the part's surface: loads it or holds it, and
    a few words on how.

    A coupling passes its reference point's role to the faces it ties: a distributing coupling to a
    loaded point is a loaded face; a rigid coupling to a held point is a held face.
    """
    held_groups = {g for h in setup.held for g in h.groups}
    loaded = {n.group: n.values for n in setup.nodal_loads}
    loaded |= {s.group: s.values for s in setup.surface_loads}
    roles: dict[str, tuple[Evidence, str]] = {}
    for d in setup.distributing:
        if d.reference in loaded:
            roles[d.group] = (
                Evidence.DECK_LOAD,
                f"distributing coupling to {d.reference}, which is loaded",
            )
        elif d.reference in held_groups:
            roles[d.group] = (
                Evidence.DECK_SUPPORT,
                f"distributing coupling to {d.reference}, which is held",
            )
    for r in setup.rigid:
        reference = r.reference
        surfaces = [g for g in r.groups if g != reference]
        if reference in held_groups or any(g in held_groups for g in r.groups):
            for g in surfaces:
                roles.setdefault(
                    g, (Evidence.DECK_SUPPORT, f"rigid coupling to {reference}, which is held")
                )
        elif reference in loaded:
            for g in surfaces:
                roles.setdefault(
                    g, (Evidence.DECK_LOAD, f"rigid coupling to {reference}, which is loaded")
                )
    for g in held_groups:
        roles.setdefault(g, (Evidence.DECK_SUPPORT, "held directly"))
    for g in loaded:
        roles.setdefault(g, (Evidence.DECK_LOAD, "loaded directly"))
    return roles


def _canonical(direction: np.ndarray) -> np.ndarray:
    d = np.asarray(direction, float)
    d = d / max(float(np.linalg.norm(d)), 1e-12)
    for component in d:
        if abs(component) > 1e-9:
            return d if component > 0 else -d
    return d


def grow_cylinder(atlas: Atlas, seed: set[int], tol_radius: float, tol_axis: float) -> set[int]:
    """The rest of a bore or boss: touching cylinders on the same axis with the same radius."""
    out = set(seed)
    frontier = [atlas.faces[f] for f in seed if f in atlas.faces]
    while frontier:
        face = frontier.pop()
        for other_id in face.neighbours:
            if other_id in out:
                continue
            other = atlas.faces.get(other_id)
            if other is None or other.surface_type != "cylinder" or other.radius_mm is None:
                continue
            if face.radius_mm is None or abs(other.radius_mm - face.radius_mm) > tol_radius:
                continue
            if other.concave != face.concave or not _coaxial(face, other, tol_axis):
                continue
            out.add(other_id)
            frontier.append(other)
    return out


def grow_plane(atlas: Atlas, seed: set[int], tol_offset: float) -> set[int]:
    """The rest of a flat face: touching planes, parallel and in the same plane."""
    out = set(seed)
    frontier = [atlas.faces[f] for f in seed if f in atlas.faces]
    limit = math.cos(math.radians(PLANE_ANGLE_TOL_DEG))
    while frontier:
        face = frontier.pop()
        if face.normal is None:
            continue
        n = np.asarray(face.normal, float)
        for other_id in face.neighbours:
            if other_id in out:
                continue
            other = atlas.faces.get(other_id)
            if other is None or other.surface_type != "plane" or other.normal is None:
                continue
            if float(np.dot(n, other.normal)) < limit:
                continue
            if (
                abs(float(np.dot(n, np.asarray(other.centroid) - np.asarray(face.centroid))))
                > tol_offset
            ):
                continue
            out.add(other_id)
            frontier.append(other)
    return out


class _Builder:
    """Collects face sets with their evidence, merging any two that share a face."""

    def __init__(self, atlas: Atlas, features: FeatureSet) -> None:
        self.atlas = atlas
        self.features = features
        diagonal = atlas.diagonal_mm
        self.tol_radius = max(diagonal * 5e-5, 1e-3)
        self.tol_axis = diagonal * AXIS_DISTANCE_TOL_FRACTION
        self.tol_offset = max(diagonal * 2e-5, 0.01)
        self.hole_of_face: dict[int, str] = {
            f: h.id for h in features.of_kind(FeatureKind.HOLE) for f in h.face_ids
        }
        self.sets: list[dict[str, Any]] = []

    def grown(self, faces: set[int]) -> tuple[str, set[int]]:
        """Grow faces into the whole feature they belong to, and say what kind it is."""
        atlas = self.atlas
        records = [atlas.faces[f] for f in faces if f in atlas.faces]
        holes = {self.hole_of_face[f] for f in faces if f in self.hole_of_face}
        if holes:
            out = set(faces)
            for h in holes:
                out |= set(self.features.features[h].face_ids)
            return "hole", out
        if records and all(r.surface_type == "cylinder" for r in records):
            out = grow_cylinder(atlas, set(faces), self.tol_radius, self.tol_axis)
            return ("bore" if records[0].concave else "boss"), out
        if records and all(r.surface_type == "plane" for r in records):
            return "plane", grow_plane(atlas, set(faces), self.tol_offset)
        return "surface", set(faces)

    def add(
        self,
        faces: set[int],
        evidence: Evidence,
        detail: str,
        confidence: float = 1.0,
        ref: str | None = None,
    ) -> None:
        """Faces, grown into their whole feature, with one piece of evidence. ``ref`` names the
        entity the evidence came from - a deck group, a drawing control, a feature."""
        if not faces:
            return
        kind, grown = self.grown(faces)
        proof = {"kind": str(evidence), "detail": detail, "confidence": confidence}
        if ref:
            proof["ref"] = ref
        self.sets.append({"kind": kind, "faces": grown, "evidence": [proof]})

    def covered(self) -> set[int]:
        return {f for s in self.sets for f in s["faces"]}

    def held_faces(self) -> set[int]:
        return {
            f
            for s in self.sets
            if any(Evidence(e["kind"]).holds for e in s["evidence"])
            for f in s["faces"]
        }

    def merged(self) -> list[dict[str, Any]]:
        """Sets sharing a face are one interface; its evidence is all that is said about any."""
        parent = list(range(len(self.sets)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        owner: dict[int, int] = {}
        for i, s in enumerate(self.sets):
            for f in s["faces"]:
                if f in owner:
                    parent[find(i)] = find(owner[f])
                else:
                    owner[f] = i
        groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for i, s in enumerate(self.sets):
            groups[find(i)].append(s)
        out = []
        for members in groups.values():
            faces = set().union(*(m["faces"] for m in members))
            kinds = [m["kind"] for m in members]
            kind = next((k for k in ("hole", "bore", "boss", "plane") if k in kinds), kinds[0])
            seen: set[tuple[str, str]] = set()
            evidence = []
            for m in members:
                for e in m["evidence"]:
                    key = (e["kind"], e["detail"])
                    if key not in seen:
                        seen.add(key)
                        evidence.append(e)
            out.append({"kind": kind, "faces": faces, "evidence": evidence})
        return out


def _describe(atlas: Atlas, faces: set[int]) -> dict[str, Any]:
    """Area, and the direction or axis the faces share."""
    records: list[FaceRecord] = [atlas.faces[f] for f in faces if f in atlas.faces]
    area = float(sum(r.area for r in records))
    out: dict[str, Any] = {"area_mm2": area}
    planes = [r for r in records if r.surface_type == "plane"]
    if planes:
        n = sum(np.asarray(r.facing) * r.area for r in planes)
        norm = float(np.linalg.norm(n))
        if norm > 1e-9:
            out["normal"] = tuple(float(v) for v in n / norm)
    cylinders = sorted(
        (r for r in records if r.surface_type in ("cylinder", "cone") and r.axis is not None),
        key=lambda r: -r.area,
    )
    if cylinders:
        c = cylinders[0]
        out["axis"] = tuple(float(v) for v in _canonical(np.asarray(c.axis)))
        out["axis_point"] = tuple(float(v) for v in c.axis_point) if c.axis_point else None
        radii = [
            r.radius_mm for r in records if r.surface_type == "cylinder" and r.radius_mm is not None
        ]
        out["radius_mm"] = float(min(radii)) if radii else c.radius_mm
    return out


def _sharp_share(atlas: Atlas, faces: set[int], sharp_deg: float) -> float:
    """Of the edges a feature shares with the rest of the part, the share that are sharp."""
    total = sharp = 0
    for f in faces:
        record = atlas.faces.get(f)
        if record is None:
            continue
        for other, angle in record.dihedral.items():
            if other in faces:
                continue
            total += 1
            sharp += angle >= sharp_deg
    return sharp / total if total else 0.0


def find(
    atlas: Atlas,
    features: FeatureSet,
    params: Params,
    anchoring: dict[str, Any] | None = None,
    setup: Any = None,
    controlled: dict[str, Any] | None = None,
) -> tuple[list[Interface], dict[str, Any]]:
    """Every interface of the part, with its evidence. Returns them and what was only counted."""
    build = _Builder(atlas, features)

    # 1. The deck: what it loads and what it holds.
    deck_holes: list[tuple[str, set[int]]] = []
    if params.use_deck and anchoring and setup is not None:
        roles = deck_roles(setup)
        for group, anchor in anchoring.get("groups", {}).items():
            role = roles.get(group)
            if role is None:
                continue
            evidence, how = role
            faces = {int(f) for f in anchor["faces"]}
            build.add(faces, evidence, f"group {group}: {how}", ref=f"group:{group}")
            if any(f in build.hole_of_face for f in faces):
                deck_holes.append((group, faces))

    # 2. A hole the deck holds or loads clamps the planes it opens onto.
    for group, faces in deck_holes:
        holes = {build.hole_of_face[f] for f in faces if f in build.hole_of_face}
        opens = {o for h in holes for o in features.features[h].opens_onto}
        planes = {o for o in opens if atlas.faces.get(o) and atlas.faces[o].surface_type == "plane"}
        for p in planes:
            build.add(
                {p},
                Evidence.DECK_HOLE_PLANE,
                f"hole of group {group} opens onto it",
                ref=f"group:{group}",
            )

    # 3. The drawing: the features it tolerances.
    if params.use_drawing and controlled:
        for feature_id, fact in controlled.items():
            if not getattr(fact, "value", False) or not getattr(fact, "trustworthy", False):
                continue
            feature = features.features.get(feature_id)
            if feature is None:
                continue
            build.add(
                set(feature.face_ids),
                Evidence.DRAWING,
                f"{feature_id} is toleranced on the drawing",
                ref=f"control:{feature_id}",
            )

    strong = build.held_faces()

    # 4. Hole patterns the deck says nothing about: the planes their holes open onto.
    hole_by_wall = {f: h for h in features.of_kind(FeatureKind.HOLE) for f in h.face_ids}
    for pattern in features.of_kind(FeatureKind.HOLE_PATTERN):
        if any(f in strong for f in pattern.face_ids):
            continue
        holes = {hole_by_wall[f].id for f in pattern.face_ids if f in hole_by_wall}
        opens = {o for h in holes for o in features.features[h].opens_onto}
        planes = {
            o
            for o in opens
            if atlas.faces.get(o) and atlas.faces[o].surface_type == "plane" and o not in strong
        }
        for p in planes:
            build.add(
                {p},
                Evidence.HOLE_PATTERN_PLANE,
                f"{pattern.id} ({pattern.count} x O{pattern.diameter_mm:.1f}) opens onto it",
                0.6,
                ref=pattern.id,
            )

    # 5. Bores the deck does not mention.
    for bore in features.of_kind(FeatureKind.BORE):
        if any(f in strong for f in bore.face_ids):
            continue
        build.add(
            set(bore.face_ids),
            Evidence.BORE_GEOMETRY,
            f"{bore.id} O{bore.diameter_mm:.1f}",
            0.5,
            ref=bore.id,
        )

    # 6. Anything else that looks machined: exact, sharp-edged, large enough to land on.
    skipped = {"count": 0, "area_mm2": 0.0}
    covered = build.covered()
    for feature in [
        *features.of_kind(FeatureKind.PLANAR_GROUP),
        *features.of_kind(FeatureKind.BOSS),
    ]:
        faces = set(feature.face_ids)
        if faces & covered:
            continue
        records = [atlas.faces[f] for f in faces if f in atlas.faces]
        if not records or not all(r.surface_type in ("plane", "cylinder") for r in records):
            continue
        if not all(r.exterior for r in records):
            continue
        share = _sharp_share(atlas, faces, params.sharp_deg)
        if share < 0.9:
            continue
        if feature.area_mm2 < params.min_question_area_mm2:
            skipped["count"] += 1
            skipped["area_mm2"] += feature.area_mm2
            continue
        build.add(
            faces,
            Evidence.MACHINED,
            f"{feature.id}: {share:.0%} of its edges sharp",
            round(0.4 + 0.3 * share, 2),
            ref=feature.id,
        )

    interfaces: list[Interface] = []
    for s in build.merged():
        info = _describe(atlas, s["faces"])
        interfaces.append(
            Interface(
                id="",
                kind=s["kind"],
                faces=sorted(int(f) for f in s["faces"]),
                evidence=s["evidence"],
                area_mm2=info["area_mm2"],
                normal=info.get("normal"),
                axis=info.get("axis"),
                axis_point=info.get("axis_point"),
                radius_mm=info.get("radius_mm"),
            )
        )
    # Named by kind and lowest face: the same interface keeps its name while the file does not
    # change.
    for i in interfaces:
        i.id = f"{i.kind}:{min(i.faces)}"
    interfaces.sort(key=lambda i: (not i.held, i.kind, -i.area_mm2))
    return interfaces, {"machined_too_small": skipped}
