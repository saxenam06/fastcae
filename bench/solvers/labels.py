"""Which boundary triangles of a TET10 mesh carry a seat's load and which are held at a bolt - the
same for every case and every solver.

**The bolts** are the flange's 25 bolt positions, as agenticCAE coupled them: each position's 55 mm
counterbore and the through-hole under it. The flange has a hole every 9 degrees, and the others -
tapped holes, dowel holes, a port up the wall - are not bolts and are not held.

**The seats** are the six loaded bearing seats.

A mesh from the design's surface is labelled by the CAD face of the nearest design triangle; a mesh
of agenticCAE's, whose boundary nodes gmsh put on the CAD, by its corners lying on the cylinder.

    python labels.py design7        # or e56235
"""

from __future__ import annotations

import json
import math
import sys

import numpy as np
from common import SCRATCH, SEATS
from scipy.spatial import cKDTree

CYLINDERS = SCRATCH / "solve" / "cylinders.json"


def bolt_positions() -> list[dict]:
    """The 25 bolt positions: angle, axis point, and the cylinders (counterbore, through-hole) of each."""
    data = json.loads(CYLINDERS.read_text(encoding="utf-8"))
    cylinders = data["bolts"]
    angle = lambda c: math.degrees(math.atan2(c["xy"][1], c["xy"][0])) % 360.0  # noqa: E731
    counterbores = [c for c in cylinders if abs(c["radius_mm"] - 27.5) < 0.1]
    out = []
    for cb in sorted(counterbores, key=angle):
        a = angle(cb)
        members = [
            c
            for c in cylinders
            if abs((angle(c) - a + 180.0) % 360.0 - 180.0) < 1.0 and c["radius_mm"] <= 27.6 and c["z"][1] <= 71.0
        ]
        out.append({"angle_deg": a, "xy": cb["xy"], "cylinders": members})
    return out


def label_by_faces(case) -> None:
    """A mesh of the design's own surface: each boundary triangle takes the CAD face of the design
    triangle nearest its middle."""
    surface = np.load(case / "surface.npz")
    mesh = dict(np.load(case / "tet10.npz"))
    setup = json.loads((case / "setup.json").read_text(encoding="utf-8"))
    vertices, triangles, face_id = surface["vertices"], surface["triangles"], surface["face_id"]
    nodes, tris = mesh["nodes"], mesh["tris"]
    tree = cKDTree(vertices[triangles].mean(axis=1))
    distance, nearest = tree.query(nodes[tris[:, :3]].mean(axis=1))
    tri_face = face_id[nearest]
    group = np.full(len(tris), -1, np.int64)
    bolt = np.full(len(tris), -1, np.int64)
    names = list(SEATS)
    for k, name in enumerate(names):
        group[np.isin(tri_face, setup["seats"][name]["faces"])] = k
    positions = bolt_positions()
    for p, position in enumerate(positions):
        hit = np.isin(tri_face, [c["face"] for c in position["cylinders"]])
        group[hit] = len(names)
        bolt[hit] = p
    setup["bolt_faces"] = sorted(c["face"] for p in positions for c in p["cylinders"])
    setup["bolt_positions"] = [{"angle_deg": p["angle_deg"], "xy": p["xy"]} for p in positions]
    (case / "setup.json").write_text(json.dumps(setup, indent=1), encoding="utf-8")
    save(case, mesh, group, bolt, distance)


def label_by_corners(case) -> None:
    """A mesh with its boundary nodes on the CAD: a triangle lies on a cylinder when all three of
    its corners do - at its radius from its axis, within its height - and it faces sideways."""
    mesh = dict(np.load(case / "tet10.npz"))
    nodes, tris = mesh["nodes"], mesh["tris"]
    data = json.loads(CYLINDERS.read_text(encoding="utf-8"))
    corners = nodes[tris[:, :3]]
    normal = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    normal /= np.linalg.norm(normal, axis=1, keepdims=True)
    sideways = np.abs(normal[:, 2]) < 0.5

    def on(xy, radius, z):
        rho = np.hypot(corners[..., 0] - xy[0], corners[..., 1] - xy[1])
        inside = (np.abs(rho - radius) < 0.3) & (corners[..., 2] > z[0] - 0.5) & (corners[..., 2] < z[1] + 0.5)
        return inside.all(axis=1) & sideways

    group = np.full(len(tris), -1, np.int64)
    bolt = np.full(len(tris), -1, np.int64)
    names = list(SEATS)
    for k, name in enumerate(names):
        for c in data["seats"][name]:
            group[on(SEATS[name]["xy"], c["radius_mm"], SEATS[name]["z"])] = k
    positions = bolt_positions()
    for p, position in enumerate(positions):
        for c in position["cylinders"]:
            hit = on(c["xy"], c["radius_mm"], c["z"]) & (group < 0)
            group[hit] = len(names)
            bolt[hit] = p
    setup = json.loads((case / "setup.json").read_text(encoding="utf-8"))
    setup["bolt_positions"] = [{"angle_deg": p["angle_deg"], "xy": p["xy"]} for p in positions]
    (case / "setup.json").write_text(json.dumps(setup, indent=1), encoding="utf-8")
    save(case, mesh, group, bolt, None)


def save(case, mesh: dict, group: np.ndarray, bolt: np.ndarray, gap) -> None:
    mesh["group"], mesh["bolt"] = group, bolt
    np.savez_compressed(case / "tet10.npz", **mesh)
    names = list(SEATS)
    info = json.loads((case / "tet10.json").read_text(encoding="utf-8"))
    info["groups"] = {name: int((group == k).sum()) for k, name in enumerate(names)}
    info["groups"]["BOLTS"] = int((group == len(names)).sum())
    info["bolt_positions"] = int(len(np.unique(bolt[bolt >= 0])))
    if gap is not None:
        info["boundary_gap_mm"] = {"median": float(np.median(gap)), "max": float(gap.max())}
    (case / "tet10.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    for stale in ("system.npz", "system.json"):
        (case / stale).unlink(missing_ok=True)
    print(json.dumps({k: info[k] for k in ("groups", "bolt_positions")}, indent=1))


if __name__ == "__main__":
    name = sys.argv[1]
    case = SCRATCH / "solve" / name
    (label_by_corners if name == "e56235" else label_by_faces)(case)
