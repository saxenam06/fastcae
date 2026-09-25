"""What every design volume keeps clear, by the design space's own rules, as closed meshes that any
plane can cut.

- **Every bore** over its own length; past each end what carries on - outward at its full radius,
  into the part at its full radius and a clearance more, as far as air runs along the axis; nothing
  past a register (a bore shallower than a tenth of its diameter). Which way is outward is found
  by probing along the axis from across the bore's end; what sits in another bore closes it, so a
  ray leaving through another bore's opening does not make the part's inside look like outside.
- **Every bearing's line**: a bore the deck loads or holds carries a shaft, kept clear along its
  axis past any lip or shoulder with the clearance more - to the next bearing on the same axis at
  the smaller of the two radii, for the shaft passes through both; on through the part at its own
  where no bearing follows.
- **Every hole, and its tool**: 1.8 times its radius, three diameters past each open end.
- **In front of every flat face the deck holds or loads**, what mates against it: a lid 8 mm deep.

Each keep-out reaches a fraction of a millimetre into the metal it stands on, so none lies exactly
on the part's own surface. Each is named, with the rule in words, so the engineer sees what is kept
clear and can switch any of them off for a volume.

Found once for a part's triangulation and deck, and kept.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from ..features import FeatureKind
from . import reading, slices

if TYPE_CHECKING:
    from ..extract import Extraction

CLEARANCE_MM = 5.0
REGISTER_SHARE = 0.1
TOOL_RADIUS = 1.8
TOOL_LENGTH = 3.0
LID_MM = 8.0
INTO_METAL_MM = 0.3


@dataclass
class Keepout:
    """One solid kept clear, why, and the closed mesh it is."""

    kind: str
    """``bore``, ``beyond`` (what carries on past a bore's end), ``line`` (a bearing's line through
    the part), ``hole``, or ``lid``."""
    ref: str
    """What it is kept clear for: the bore, the hole, or the deck's group."""
    key: str
    """Its own name among the keep-outs, unique."""
    words: str
    vertices: np.ndarray = field(repr=False)
    triangles: np.ndarray = field(repr=False)
    box: np.ndarray = field(repr=False)

    def summary(self) -> dict[str, Any]:
        return {"key": self.key, "kind": self.kind, "ref": self.ref, "words": self.words}


def _keepout(kind: str, ref: str, key: str, words: str, mesh: tuple) -> Keepout:
    vertices, triangles = mesh
    box = np.concatenate([vertices.min(axis=0), vertices.max(axis=0)])
    return Keepout(kind, ref, key, words, vertices, triangles, box)


_HELD: dict[tuple[int, int], tuple[object, list[Keepout]]] = {}


def every(extraction: Extraction, setup: Any = None) -> list[Keepout]:
    """Every keep-out of the part."""
    key = (id(extraction.tess), id(setup))
    held = _HELD.get(key)
    if held is not None and held[0] is extraction.tess:
        return held[1]
    found = _find(extraction, setup)
    _HELD.clear()
    _HELD[key] = (extraction.tess, found)
    return found


def _bearings(extraction: Extraction, setup: Any) -> dict[str, str]:
    """The bores the deck loads or holds, each with its group: each carries a shaft."""
    if setup is None:
        return {}
    from ..space.interfaces import deck_roles

    roles = deck_roles(setup)
    groups = (extraction.anchoring or {}).get("groups", {})
    held = {int(f): g for g, a in groups.items() if g in roles for f in a["faces"]}
    assert extraction.features is not None
    out = {}
    for bore in extraction.features.of_kind(FeatureKind.BORE):
        named = sorted({held[f] for f in bore.face_ids if f in held})
        if named:
            out[bore.id] = ", ".join(named)
    return out


def _line(
    bore: dict[str, Any], bearings: list[dict[str, Any]], span: np.ndarray
) -> list[tuple[str, float, float, float, str]]:
    """A bearing's line, each way from its bore: to the next bearing on the same axis at the smaller
    of the two radii - the shaft passes through both - or on through the part at its own."""
    axis, point, radius = bore["axis"], bore["point"], bore["radius"]
    middle = 0.5 * (bore["lo"] + bore["hi"])
    partners = []
    for other in bearings:
        if other is bore or abs(float(other["axis"] @ axis)) < reading.PARALLEL:
            continue
        offset = other["point"] - point
        if np.linalg.norm(offset - (offset @ axis) * axis) > 0.1 * min(radius, other["radius"]):
            continue
        centre = other["point"] + other["axis"] * 0.5 * (other["lo"] + other["hi"])
        partners.append((float((centre - point) @ axis), other))
    s = (span - point) @ axis
    out = []
    for side, end, edge in ((1.0, "a", float(s.max())), (-1.0, "b", float(s.min()))):
        ahead = [(abs(at - middle), at, o) for at, o in partners if side * (at - middle) > 0]
        if ahead:
            _, at, other = min(ahead, key=lambda t: t[0])
            r = min(radius, other["radius"])
            words = f"to {other['id']}, at the smaller radius"
        else:
            at, r, words = edge, radius, "on through the part"
        lo, hi = sorted((middle, at))
        out.append((f"{bore['id']}:line:{end}", lo, hi, r, words))
    return out


def _find(extraction: Extraction, setup: Any) -> list[Keepout]:
    features, atlas, tess = extraction.features, extraction.atlas, extraction.tess
    assert features is not None and atlas is not None and tess is not None
    far = float(np.linalg.norm(tess.vertices.max(axis=0) - tess.vertices.min(axis=0)))
    out: list[Keepout] = []

    known = reading.bores(extraction)
    bearing = _bearings(extraction, setup)
    bearings = [b for b in known if b["id"] in bearing]
    for bore in known:
        axis, point, radius = bore["axis"], bore["point"], bore["radius"]
        mesh = slices.cylinder_mesh(point, axis, radius + INTO_METAL_MM, bore["lo"], bore["hi"])
        out.append(
            _keepout("bore", bore["id"], bore["id"], f"{bore['id']} Ø{2 * radius:.0f}", mesh)
        )
        register = bore["hi"] - bore["lo"] < REGISTER_SHARE * 2 * radius
        for side, station, end in ((1.0, bore["hi"], "a"), (-1.0, bore["lo"], "b")):
            hit = reading.runs_past(extraction, known, bore, side, station)
            if hit is not None and hit <= 1.5:
                continue  # metal, or the next bore of a stack, right at the end
            if hit is None:
                length, words = far, "what sits in it carries on outward"
            elif register:
                continue
            else:
                length, words = hit, "what sits in it carries on inside"
            lo, hi = sorted((station, station + side * length))
            clear = INTO_METAL_MM if hit is None else CLEARANCE_MM
            mesh = slices.cylinder_mesh(point, axis, radius + clear, lo, hi)
            key = f"{bore['id']}:{end}"
            out.append(_keepout("beyond", bore["id"], key, f"past {bore['id']}: {words}", mesh))
        if bore["id"] in bearing:
            for key, lo, hi, r, words in _line(bore, bearings, tess.vertices):
                mesh = slices.cylinder_mesh(point, axis, r + CLEARANCE_MM, lo, hi)
                words = f"the line of {bore['id']} ({bearing[bore['id']]}) {words}"
                out.append(_keepout("line", bore["id"], key, words, mesh))

    for hole in features.of_kind(FeatureKind.HOLE):
        if hole.normal is None:
            continue
        axis = reading.unit(hole.normal)
        radius = float(hole.metrics.get("radius_mm", 0.5 * (hole.diameter_mm or 0.0)))
        if radius <= 0:
            continue
        points = np.concatenate([reading.face_points(extraction, f) for f in hole.face_ids])
        centre = np.asarray(hole.centroid, float)
        s = (points - centre) @ axis
        tool = TOOL_LENGTH * 2 * radius
        mesh = slices.cylinder_mesh(
            centre, axis, TOOL_RADIUS * radius, float(s.min()) - tool, float(s.max()) + tool, 48
        )
        words = f"{hole.id} Ø{2 * radius:.0f} and its tool"
        out.append(_keepout("hole", hole.id, hole.id, words, mesh))

    if setup is not None:
        from ..space.interfaces import deck_roles

        roles = deck_roles(setup)
        groups = (extraction.anchoring or {}).get("groups", {})
        for group, anchor in groups.items():
            if group not in roles:
                continue
            for f in anchor["faces"]:
                record = atlas.faces.get(int(f))
                if record is None or record.surface_type != "plane" or record.normal is None:
                    continue
                patch = tess.triangles[tess.face_id == int(f)]
                if not len(patch):
                    continue
                mesh = slices.prism_mesh(
                    tess.vertices, patch, reading.unit(record.normal), INTO_METAL_MM, LID_MM
                )
                words = f"what mates on face:{f} ({group})"
                out.append(_keepout("lid", f"group:{group}", f"lid:{f}", words, mesh))
    return out
