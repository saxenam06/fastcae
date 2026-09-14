"""A campaign design rebuilt on the scratch copy of the project and written out for the solvers:
its whole surface - each triangle with the CAD face it lies on - its distance field at the grid it
was built on with the samples the design changed, and the faces of its six bearing seats and 25
flange bolt holes, found by geometry.

    python export_design.py [index]     # 6 is design #7 of campaign w4zf5

Reads the user's campaign archive, never writes it: the run's recipe files are copied beside the
scratch project first.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from common import BOLT_PCD_MM, OUT, SCRATCH, SEATS, loads

from fastcae import extract
from fastcae.generate import session as sessions
from fastcae.project import Project

PROJECT = SCRATCH / "e2e" / "projects" / "GRC_Gearbox_Housing"
RUN = "w4zf5-ribs-on-face-1201-ribs-on-face-1543-ribs"
SOURCE = Path(r"C:\Work\fastcae\_archived_designs\GRC_Gearbox_Housing") / RUN
INDEX = int(sys.argv[1]) if len(sys.argv) > 1 else 6


def seat_faces(features) -> dict[str, list[int]]:
    """Each seat's CAD faces: cylinders of its diameter on its axis, within its height."""
    out: dict[str, list[int]] = {}
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
            found.append(face.face_id)
        out[name] = sorted(found)
    return out


def bolt_faces(features) -> list[int]:
    """The flange's bolt holes: small concave cylinders along the main axis, on the pitch circle."""
    found = []
    for face in features.faces.values():
        if face.surface_type != "cylinder" or face.axis is None or face.radius_mm is None:
            continue
        if abs(abs(face.axis[2]) - 1.0) > 1e-3 or not face.concave or face.radius_mm > 30.0:
            continue
        p = np.asarray(face.axis_point, float)
        if abs(np.hypot(p[0], p[1]) - BOLT_PCD_MM / 2.0) > 3.0:
            continue
        found.append(face.face_id)
    return sorted(found)


def main() -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    project = Project(root=PROJECT)
    target = sessions.archive_root(project) / RUN
    target.mkdir(parents=True, exist_ok=True)
    for name in ("study.json", "designs.jsonl", "campaign.json", "summary.json"):
        shutil.copy(SOURCE / name, target / name)
    result = extract.run(project)
    features = result.features
    context = sessions.Session(project, result)
    found = sessions._run(context, RUN)
    assert not isinstance(found, str), found
    version, designs = found
    design = designs[INDEX]
    values = design["values"]
    present = set(design.get("variants") or values)
    print(f"design #{INDEX + 1}: {sorted(present)}", flush=True)
    reply = sessions.design_from_study(context, "preview", values=values, run=RUN, present=present)
    assert "cannot" not in reply, reply
    made = context.made
    surface = made.design.surface
    field = made.design.composition.field
    print(f"built in {time.time() - started:.0f} s: {made.design.stats}", flush=True)

    seats = seat_faces(features)
    bolts = bolt_faces(features)
    for name, faces in seats.items():
        print(f"  {name}: faces {faces}", flush=True)
    print(f"  bolt hole faces: {len(bolts)}", flush=True)

    np.savez_compressed(
        OUT / "surface.npz",
        vertices=surface.vertices.astype(np.float64),
        triangles=surface.triangles.astype(np.int64),
        face_id=surface.face_id.astype(np.int64),
    )
    np.savez_compressed(
        OUT / "field.npz",
        origin=np.asarray(field.grid.origin, float),
        spacing=float(field.grid.spacing_mm),
        shape=np.asarray(field.grid.shape, np.int64),
        inside=np.packbits(field.inside.ravel()),
        band_index=field.band_index,
        band_mm=field.band_mm,
        reach_mm=float(field.reach_mm),
        changed=made.design.composition.changed.astype(np.int64),
    )
    force = loads()
    (OUT / "setup.json").write_text(
        json.dumps(
            {
                "design": INDEX + 1,
                "run": RUN,
                "variants": sorted(present),
                "values": values,
                "stats": made.design.stats,
                "seats": {n: {"faces": f, "force_N": force[n].tolist()} for n, f in seats.items()},
                "bolt_faces": bolts,
                "surface": {
                    "vertices": int(surface.n_vertices),
                    "triangles": int(surface.n_triangles),
                    "volume_mm3": float(surface.volume_mm3),
                    "watertight": bool(surface.watertight),
                },
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"written to {OUT} in {time.time() - started:.0f} s", flush=True)


if __name__ == "__main__":
    main()
