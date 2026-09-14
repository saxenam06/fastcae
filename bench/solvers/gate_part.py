"""The gate's part: the production housing - its ribs and fillets as cast - read from its STEP in a
scratch project of its own (never one of the engineer's projects, never a source for designs), its
distance field built by the product at the grid a design would have, and written out for both routes
the way ``export_design.py`` writes a design: the field; the part's own CAD surface, triangulated to
within 0.05 mm, with each triangle's face; the faces of its six bearing seats and the cylinders of
its 25 flange bolt holes, found by geometry.

    python gate_part.py [spacing_mm]     # 3 by default; BENCH_CASE picks the case folder (gate3)
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

os.environ.setdefault("BENCH_CASE", "gate3")

import numpy as np  # noqa: E402
from common import OUT, SCRATCH, loads  # noqa: E402
from cylinders import find  # noqa: E402

from fastcae import extract  # noqa: E402
from fastcae.generate.field import field_for  # noqa: E402
from fastcae.geometry.brep import load_step, tessellate  # noqa: E402
from fastcae.project import Project  # noqa: E402

STEP = Path(r"C:\Work\fastcae\assets\_archive\254492_0_closed_volume.step")
PROJECT = SCRATCH / "gate" / "projects" / "GRC_production"
SPACING = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
# The CAD's own surface for the regular route and for both routes' labels: far finer than the
# product's own triangulation, which the field is built from, so it stands for the CAD itself.
FINE_MM, FINE_DEG = 0.05, 10.0


def closed(vertices: np.ndarray, triangles: np.ndarray, face_id: np.ndarray):
    """The triangulation without its folds: OpenCASCADE leaves the odd pair of identical triangles
    wound opposite ways - a millionth of a square millimetre each - whose shared edges four triangles
    then meet at. Both of a pair go, and vertices no triangle uses."""
    _, inverse, count = np.unique(np.sort(triangles, 1), axis=0, return_inverse=True, return_counts=True)
    keep = count[inverse.ravel()] == 1
    triangles, face_id = triangles[keep], face_id[keep]
    used, compact = np.unique(triangles, return_inverse=True)
    return vertices[used], compact.reshape(triangles.shape), face_id


def main() -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    PROJECT.mkdir(parents=True, exist_ok=True)
    if not (PROJECT / STEP.name).exists():
        shutil.copy(STEP, PROJECT / STEP.name)
    result = extract.run(Project(root=PROJECT))
    tess = result.tess
    print(f"read in {time.time() - started:.0f} s: {len(tess.triangles)} triangles, {len(tess.face_ids)} faces",
          flush=True)
    t0 = time.time()
    field, kept = field_for(PROJECT, tess, result.cad_digest, spacing_mm=SPACING)
    print(f"field at {SPACING} mm: {field.grid.shape}, {'kept' if kept else 'built'} in {time.time() - t0:.0f} s",
          flush=True)

    cylinders = find(result.features)
    (OUT / "cylinders.json").write_text(json.dumps(cylinders, indent=1), encoding="utf-8")
    t0 = time.time()
    fine = tessellate(load_step(STEP), deflection_mm=FINE_MM, angle_deg=FINE_DEG)
    vertices, triangles, face_id = closed(fine.vertices, fine.triangles, fine.face_id)
    edges = np.sort(np.concatenate([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]]), 1)
    _, uses = np.unique(edges, axis=0, return_counts=True)
    print(f"CAD surface within {FINE_MM} mm: {len(triangles)} triangles in {time.time() - t0:.0f} s, "
          f"edges not shared by exactly two: {int((uses != 2).sum())}", flush=True)
    np.savez_compressed(
        OUT / "surface.npz",
        vertices=vertices.astype(np.float64),
        triangles=triangles.astype(np.int64),
        face_id=face_id.astype(np.int64),
    )
    # The product's own triangulation, which the field is built from: what the CAD-surface route meshes.
    vertices, triangles, face_id = closed(tess.vertices, tess.triangles, tess.face_id)
    np.savez_compressed(
        OUT / "cad_surface.npz",
        vertices=vertices.astype(np.float64),
        triangles=triangles.astype(np.int64),
        face_id=face_id.astype(np.int64),
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
        changed=np.empty(0, np.int64),
    )
    force = loads()
    seats = {name: [c["face"] for c in found] for name, found in cylinders["seats"].items()}
    (OUT / "setup.json").write_text(
        json.dumps(
            {
                "part": STEP.name,
                "spacing_mm": SPACING,
                "seats": {n: {"faces": f, "force_N": force[n].tolist()} for n, f in seats.items()},
                "bolt_faces": sorted(c["face"] for c in cylinders["bolts"]),
                "field_from": {"triangles": int(len(tess.triangles)), "deflection_mm": float(tess.deflection_mm)},
                "surface": {"triangles": int(len(fine.triangles)), "deflection_mm": FINE_MM, "angle_deg": FINE_DEG},
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    for name, faces in seats.items():
        print(f"  {name}: faces {faces}", flush=True)
    print(f"  bolt faces: {len(cylinders['bolts'])}; written to {OUT} in {time.time() - started:.0f} s", flush=True)


if __name__ == "__main__":
    main()
