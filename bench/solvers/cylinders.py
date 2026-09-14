"""The six bearing seats' and the 25 flange bolt holes' cylinders, read off the CAD: axis point, axis,
radius and height of each - what any mesh of this housing needs to find its supports and loads by
geometry, whoever meshed it. Written to ``cylinders.json`` beside the other shared data; a case with
a part of its own (the gate's) keeps its own ``cylinders.json``.

    python cylinders.py
"""

from __future__ import annotations

import json

import numpy as np
from common import BOLT_PCD_MM, SCRATCH, SEATS

from fastcae import extract
from fastcae.project import Project

PROJECT = SCRATCH / "e2e" / "projects" / "GRC_Gearbox_Housing"


def main() -> None:
    out = find(extract.run(Project(root=PROJECT)).features)
    path = SCRATCH / "solve" / "cylinders.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    radii = sorted({round(b["radius_mm"], 2) for b in out["bolts"]})
    print(
        f"{len(out['bolts'])} bolt faces, radii {radii}; seats "
        + ", ".join(f"{n}: {len(f)}" for n, f in out["seats"].items())
    )


def find(features) -> dict:
    """The seats' and the flange bolt holes' cylinders among a part's CAD faces."""
    out: dict = {"seats": {}, "bolts": []}
    for name, seat in SEATS.items():
        found = []
        for face in features.faces.values():
            if face.surface_type != "cylinder" or face.axis is None or face.radius_mm is None:
                continue
            if abs(abs(face.axis[2]) - 1.0) > 1e-3 or abs(2 * face.radius_mm - seat["dia"]) > 0.6:
                continue
            p = np.asarray(face.axis_point, float)
            if np.hypot(p[0] - seat["xy"][0], p[1] - seat["xy"][1]) > 1.0:
                continue
            z = np.asarray(face.bbox_mm, float)[[2, 5]]
            if z[0] < seat["z"][0] - 1.5 or z[1] > seat["z"][1] + 1.5:
                continue
            found.append({"face": face.face_id, "radius_mm": face.radius_mm, "z": z.tolist()})
        out["seats"][name] = found
    for face in features.faces.values():
        if face.surface_type != "cylinder" or face.axis is None or face.radius_mm is None:
            continue
        if abs(abs(face.axis[2]) - 1.0) > 1e-3 or not face.concave or face.radius_mm > 30.0:
            continue
        p = np.asarray(face.axis_point, float)
        if abs(np.hypot(p[0], p[1]) - BOLT_PCD_MM / 2.0) > 3.0:
            continue
        z = np.asarray(face.bbox_mm, float)[[2, 5]]
        out["bolts"].append(
            {
                "face": face.face_id,
                "xy": p[:2].tolist(),
                "radius_mm": face.radius_mm,
                "z": z.tolist(),
            }
        )
    return out


if __name__ == "__main__":
    main()
