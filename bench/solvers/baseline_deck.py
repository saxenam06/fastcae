"""The rib-less baseline housing as its engineer would hand it over: a Code_Aster deck and the answer
Code_Aster gave - the stand-in for the files a customer uploads beside the CAD and the drawing.

Meshed face by face as agenticCAE meshed its designs (the product's fastcae.simulate.face_mesh):
gmsh on every CAD face, 20 mm most and 4 mm least, curved edges at least 12 elements a turn so
holes stay round, the faces gmsh cannot parametrise meshed in their unrolled plane instead of
lidded; weld, collapse, MeshFix, gmsh tets; TET10 with straight mid-side nodes; a boundary triangle
a seat's or bolt hole's when its middle is nearest that CAD face and every corner lies within 2 mm
of it.

Set up as agenticCAE set up its designs: the nine bores and the 25 flange bolt positions found by
geometry and named as agenticCAE named them; each bolt a kinematic coupling to a reference node held
in translation; each of the six loaded seats a distributing coupling to a reference node on its axis
carrying agenticCAE's DLC 1.3 extreme forces - as the gate coupled them; iron as agenticCAE had it.
The deck asks for the displacement and rotation of every loaded seat's reference node - its signals.

Everything here is this study's; nothing of it is product code. The product reads what it writes.

    python baseline_deck.py [--copy]     # --copy puts the deck and its results into the project folder
    python baseline_deck.py --compare    # the deck already run: read it back and solve it again
"""

from __future__ import annotations

import json
import math
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from common import AGENTICCAE, SCRATCH

from fastcae import extract
from fastcae.project import Project
from fastcae.simulate import aster, carry, face_mesh, med, signals, solve, tetmesh
from fastcae.simulate.fem import FEMesh
from fastcae.simulate.setup import Analysis, Distributing, Held, Material, NodalLoad, Output, Rigid, Setup

PROJECT = Path(r"C:\Work\fastcae\assets\GRC_Gearbox_Housing")
BREP = PROJECT / "housing_baseline.brep"
WORK = SCRATCH / "baseline_deck"
STAGE = WORK / "deck"
TOLERANCE_MM = 2.0  # a boundary triangle on a face: every corner this close to it, as the gate

# agenticCAE's nine bearing bores (assets/housing_faces.json, BORE_MAIN_S1/S4, AX1_S2 and AX2_S1
# left out as it left them out), by diameter, axis and height.
BORES = {
    "BORE_MAIN_S2": {"dia": 541.0, "xy": (0.0, 0.0), "z": (70.2, 125.2)},
    "BORE_MAIN_S3": {"dia": 360.02, "xy": (0.0, 0.0), "z": (554.7, 659.6)},
    "BORE_AX1_S1": {"dia": 180.0, "xy": (0.0, 520.0), "z": (113.9, 170.1)},
    "BORE_AX1_S3": {"dia": 190.0, "xy": (0.0, 520.0), "z": (394.9, 426.1)},
    "BORE_AX1_S4": {"dia": 200.0, "xy": (0.0, 520.0), "z": (425.9, 469.6)},
    "BORE_AX1_S5": {"dia": 211.0, "xy": (0.0, 520.0), "z": (470.8, 680.2)},
    "BORE_AX2_S2": {"dia": 180.0, "xy": (246.3, 376.6), "z": (113.9, 170.1)},
    "BORE_AX2_S3": {"dia": 272.0, "xy": (246.3, 376.6), "z": (554.7, 670.3)},
    "BORE_AX2_S4": {"dia": 345.0, "xy": (246.3, 376.6), "z": (669.8, 680.2)},
}
BOLT_PCD_MM = 1120.0
COUNTERBORE_R = 27.5


def closed(vertices: np.ndarray, triangles: np.ndarray, face_id: np.ndarray):
    """The triangulation without the odd pair of identical, oppositely wound triangles."""
    _, inverse, count = np.unique(np.sort(triangles, 1), axis=0, return_inverse=True, return_counts=True)
    keep = count[inverse.ravel()] == 1
    triangles, face_id = triangles[keep], face_id[keep]
    used, compact = np.unique(triangles, return_inverse=True)
    return vertices[used], compact.reshape(triangles.shape), face_id


def bores(features) -> dict[str, list[int]]:
    out = {}
    for name, b in BORES.items():
        found = []
        for face in features.faces.values():
            if face.surface_type != "cylinder" or face.axis is None or face.radius_mm is None:
                continue
            if abs(abs(face.axis[2]) - 1.0) > 1e-3 or abs(2 * face.radius_mm - b["dia"]) > 0.6:
                continue
            p = np.asarray(face.axis_point, float)
            if np.hypot(p[0] - b["xy"][0], p[1] - b["xy"][1]) > 1.0:
                continue
            z = np.asarray(face.bbox_mm, float)[[2, 5]]
            if z[0] < b["z"][0] - 1.5 or z[1] > b["z"][1] + 1.5:
                continue
            found.append(face.face_id)
        out[name] = found
    return out


def bolts(features) -> list[dict]:
    """The 25 bolt positions: each 55 mm counterbore with the through-hole under it."""
    holes = []
    for face in features.faces.values():
        if face.surface_type != "cylinder" or face.axis is None or face.radius_mm is None:
            continue
        if abs(abs(face.axis[2]) - 1.0) > 1e-3 or not face.concave or face.radius_mm > 30.0:
            continue
        p = np.asarray(face.axis_point, float)
        if abs(np.hypot(p[0], p[1]) - BOLT_PCD_MM / 2.0) > 3.0:
            continue
        z = np.asarray(face.bbox_mm, float)[[2, 5]]
        holes.append({"face": face.face_id, "xy": p[:2], "r": face.radius_mm, "z": z})
    angle = lambda c: math.degrees(math.atan2(c["xy"][1], c["xy"][0])) % 360.0  # noqa: E731
    out = []
    for cb in sorted((c for c in holes if abs(c["r"] - COUNTERBORE_R) < 0.1), key=angle):
        a = angle(cb)
        members = [
            c
            for c in holes
            if abs((angle(c) - a + 180.0) % 360.0 - 180.0) < 1.0 and c["r"] <= 27.6 and c["z"][1] <= 71.0
        ]
        out.append({"xy": cb["xy"], "faces": [c["face"] for c in members]})
    return out


def patch_nodes(mesh: FEMesh, faces: list[int], vertices, triangles, face_id) -> np.ndarray:
    """The nodes of the boundary triangles lying on the faces: middle nearest them, every corner
    within the tolerance."""
    import igl

    skin = mesh.skin
    corners = mesh.nodes[skin.corners]
    _, nearest, _ = igl.point_mesh_squared_distance(corners.mean(axis=1), vertices, triangles.astype(np.int64))
    candidates = np.flatnonzero(np.isin(face_id[nearest], faces))
    squared, _, _ = igl.point_mesh_squared_distance(
        corners[candidates].reshape(-1, 3), vertices, triangles[np.isin(face_id, faces)].astype(np.int64)
    )
    chosen = candidates[(np.sqrt(squared).reshape(-1, 3) < TOLERANCE_MM).all(axis=1)]
    return np.unique(skin.six[chosen])


def main() -> None:
    started = time.time()
    WORK.mkdir(parents=True, exist_ok=True)
    STAGE.mkdir(parents=True, exist_ok=True)
    scratch_project = WORK / "projects" / PROJECT.name
    scratch_project.mkdir(parents=True, exist_ok=True)
    if not (scratch_project / BREP.name).exists():
        shutil.copy2(BREP, scratch_project / BREP.name)
    result = extract.run(Project(root=scratch_project))
    vertices, triangles, face_id = closed(result.tess.vertices, result.tess.triangles, result.tess.face_id)
    bore_faces = bores(result.features)
    positions = bolts(result.features)
    print(
        f"read in {time.time() - started:.0f} s; bores:",
        {k: len(v) for k, v in bore_faces.items()},
        f"bolt positions: {len(positions)}",
        flush=True,
    )
    assert all(bore_faces.values()) and len(positions) == 25

    loads = json.loads((AGENTICCAE / "loads.json").read_text(encoding="utf-8"))
    seats = [b for b in bore_faces if b in loads]
    t0 = time.time()
    nodes, tets, info = face_mesh.mesh(BREP, WORK)
    assert not info["patched_holes"], info
    print(
        f"mesh: {len(tets):,} tets in {time.time() - t0:.0f} s; {info['faces']} faces, {len(info['unrolled_faces'])} "
        f"meshed unrolled, none lidded; below q 0.1 {info['below_q0.1_pct']} %, {info['volume_cm3']} cm3",
        flush=True,
    )
    body = tetmesh.finish(nodes, tets)

    node_groups: dict[str, np.ndarray] = {}
    refs: list[tuple[str, np.ndarray]] = []
    for name, faces in bore_faces.items():
        members = patch_nodes(body, faces, vertices, triangles, face_id)
        node_groups[name] = members
        # A reference node only where a coupling ties one: a loose point with zero stiffness is a
        # mechanism, and Code_Aster stops on it (FACTOR_11).
        if name not in seats:
            continue
        axis_point = np.array([*BORES[name]["xy"], 0.0])
        z = float(body.nodes[members, 2].mean())
        refs.append((f"REF_{name}", axis_point + np.array([0.0, 0.0, z])))
    for i, position in enumerate(positions):
        name = f"BOLT_{i:02d}"
        members = patch_nodes(body, position["faces"], vertices, triangles, face_id)
        node_groups[name] = members
        refs.append((f"REF_{name}", np.array([*position["xy"], float(body.nodes[members, 2].mean())])))
    first = len(body.nodes)
    all_nodes = np.vstack([body.nodes, np.array([p for _, p in refs])])
    for i, (name, _) in enumerate(refs):
        node_groups[name] = np.array([first + i])
    mesh = FEMesh(
        nodes=all_nodes,
        cells={"TETRA10": body.cells["TETRA10"], "POI1": np.arange(first, first + len(refs))[:, None]},
        node_groups=node_groups,
        cell_groups={
            "BULK": {"TETRA10": np.arange(len(body.cells["TETRA10"]))},
            "REFPT": {"POI1": np.arange(len(refs))},
        },
        name="HOUSING",
    )
    for name in [*bore_faces, *[f"BOLT_{i:02d}" for i in range(len(positions))]]:
        print(f"  {name}: {len(node_groups[name])} nodes", flush=True)

    bolt_names = [f"BOLT_{i:02d}" for i in range(len(positions))]
    coupled = seats
    setup = Setup(
        model=[
            {"groups": ["BULK"], "physics": "MECANIQUE", "modelling": "3D"},
            {"groups": ["REFPT"], "physics": "MECANIQUE", "modelling": "DIS_TR"},
        ],
        discrete=[{"groups": ["REFPT"], "kind": "K_TR_D_N"}],
        materials=[Material(name="iron", young=169000.0, poisson=0.275, density=7.2e-9, groups=["BULK"])],
        held=[
            Held(load_set="supports", groups=[f"REF_{b}" for b in bolt_names], dofs={"DX": 0.0, "DY": 0.0, "DZ": 0.0})
        ],
        rigid=[Rigid(load_set="supports", groups=[b, f"REF_{b}"]) for b in bolt_names],
        distributing=[
            Distributing(
                load_set="couplings",
                reference=f"REF_{b}",
                group=b,
                reference_dofs=["DX", "DY", "DZ", "DRX", "DRY", "DRZ"],
                group_dofs=["DX-DY-DZ"],
                weights=[1.0],
            )
            for b in coupled
        ],
        nodal_loads=[
            NodalLoad(load_set="loads", group=f"REF_{b}", values={c: float(loads[b][c]) for c in ("FX", "FY", "FZ")})
            for b in bore_faces
            if b in loads
        ],
        outputs=[
            Output(name=b, group=f"REF_{b}", field="DEPL", components=None, operation="EXTRACTION", table="signals")
            for b in coupled
        ],
        analysis=Analysis(
            kind="linear static",
            load_sets=["supports", "couplings", "loads"],
            solver={"METHODE": "MUMPS", "ACCELERATION": "LR", "GESTION_MEMOIRE": "AUTO", "RENUM": "AUTO"},
        ),
    )
    print("loaded bores:", [n.group for n in setup.nodal_loads], flush=True)

    # The mesh as Code_Aster's text, turned into MED by Code_Aster itself.
    aster.write_mail(mesh, STAGE / "baseline.mail", title="GRC gearbox housing, baseline without ribs")
    (STAGE / "convert.comm").write_text(
        "DEBUT(LANG='EN')\nHOUSING = LIRE_MAILLAGE(FORMAT='ASTER', UNITE=20)\n"
        "IMPR_RESU(FORMAT='MED', UNITE=21, RESU=_F(MAILLAGE=HOUSING))\nFIN()\n",
        encoding="ascii",
    )
    aster.write_export(
        STAGE / "convert.export",
        aster.Export(
            params={
                "actions": "make_etude",
                "version": "stable",
                "ncpus": "1",
                "memory_limit": "4000",
                "time_limit": "900",
            },
            files=[
                aster.ExportFile("comm", "convert.comm", "D", 1),
                aster.ExportFile("mail", "baseline.mail", "D", 20),
                aster.ExportFile("mmed", "baseline.med", "R", 21),
                aster.ExportFile("mess", "convert.mess", "R", 6),
            ],
        ),
    )
    t0 = time.time()
    converted = aster.run(STAGE / "convert.export")
    print(f"MED written by Code_Aster: {converted.diagnosis} in {time.time() - t0:.0f} s", flush=True)
    assert converted.ok, converted.log_tail

    (STAGE / "baseline.comm").write_text(aster.write_comm(setup, mesh_format="MED", mesh_unit=20), encoding="ascii")
    aster.write_export(
        STAGE / "baseline.export",
        aster.Export(
            # One thread, as every proven run had it: with these couplings MUMPS crawls on 4-8 threads.
            params={
                "actions": "make_etude",
                "version": "stable",
                "ncpus": "1",
                "memory_limit": "7000",
                "time_limit": "900",
            },
            files=[
                aster.ExportFile("comm", "baseline.comm", "D", 1),
                aster.ExportFile("mmed", "baseline.med", "D", 20),
                aster.ExportFile("rmed", "baseline.rmed", "R", 80),
                aster.ExportFile("resu", "baseline_signals.resu", "R", 81),
                aster.ExportFile("mess", "baseline.mess", "R", 6),
            ],
        ),
    )
    t0 = time.time()
    ran = aster.run(STAGE / "baseline.export")
    print(f"Code_Aster: {ran.diagnosis} in {time.time() - t0:.0f} s", flush=True)
    assert ran.ok, ran.log_tail
    (STAGE / "aster_run.json").write_text(json.dumps({"seconds": ran.seconds}), encoding="utf-8")
    compare(vertices, triangles, face_id)
    print(f"done in {time.time() - started:.0f} s", flush=True)


def compare(vertices: np.ndarray, triangles: np.ndarray, face_id: np.ndarray) -> None:
    """The deck and Code_Aster's answer read back as the product reads them, and solved again here."""
    back = med.read_mesh(STAGE / "baseline.med")
    commands, skipped = aster.parse_comm((STAGE / "baseline.comm").read_text())
    read, _ = aster.interpret(commands)
    read.resolve({g for g, m in back.node_groups.items() if len(m) == 1})
    assert not skipped and not read.not_read, (skipped, read.not_read)
    fields = med.read_fields(STAGE / "baseline.rmed")
    reference = signals.from_med(back, fields, read)
    t0 = time.time()
    mine = solve.solve(back, read, gpu=True)
    print(f"cuDSS: {mine.unknowns:,} unknowns in {time.time() - t0:.0f} s", flush=True)
    rows = signals.compare(
        signals.signals(back, read, reference), signals.signals(back, read, signals.from_solution(mine, "cuDSS"))
    )
    worst = max(abs(r["difference"]) for r in rows if abs(r["reference"]) > 1e-12)
    agreement = signals.field_agreement(back, reference, signals.from_solution(mine, "cuDSS"))
    print(f"cuDSS against Code_Aster: signals within {worst:.1e}, fields {agreement}", flush=True)
    for r in rows:
        if r["component"] in ("tilt", "p99.9", "largest", "reaction") and r["name"] != "BOLT":
            print(
                f"  {r['name']:14s} {r['component']:9s} {r['reference']:12.5g} "
                f"{r['other']:12.5g} {r['difference']:+.1e}"
            )
    ran = json.loads((STAGE / "aster_run.json").read_text(encoding="utf-8"))
    summary = {
        "tets": int(back.count("TETRA10")),
        "nodes": int(back.n_nodes),
        "unknowns_cudss": int(mine.unknowns),
        "code_aster_s": ran["seconds"],
        "cudss_s": mine.times.get("total_s"),
        "cudss_times": mine.times,
        "worst_signal_difference": worst,
        "fields": agreement,
        "signals": rows,
        "anchored": carry.anchor(back, read, vertices, triangles, face_id).to_json(),
    }
    (WORK / "baseline_deck.json").write_text(json.dumps(summary, indent=1, default=float), encoding="utf-8")
    if "--copy" in sys.argv:
        for name in (
            "baseline.export",
            "baseline.comm",
            "baseline.med",
            "baseline.rmed",
            "baseline_signals.resu",
            "baseline.mess",
        ):
            target = PROJECT / name
            if target.exists():
                raise SystemExit(f"{target} exists; not overwritten")
            shutil.copy2(STAGE / name, target)
        print(f"deck and results copied into {PROJECT}", flush=True)


def read_part() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    scratch_project = WORK / "projects" / PROJECT.name
    result = extract.run(Project(root=scratch_project))
    return closed(result.tess.vertices, result.tess.triangles, result.tess.face_id)


if __name__ == "__main__":
    if "--compare" in sys.argv:  # the deck already made and run: read it back and solve it again
        compare(*read_part())
    else:
        main()
