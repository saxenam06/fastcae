"""The reference solve: Code_Aster 18 on the TET10 mesh, linear static, MUMPS with the settings
agenticCAE solved its quadratic campaign with (block low-rank, automatic memory and renumbering).
Runs inside WSL, in the ``aster`` micromamba environment:

    micromamba run -n aster python solve_aster.py /mnt/c/.../<case> [clamped|couplings] [memory_mb]

``clamped`` - the benchmark's supports, the same as every solver here: the bolt holes held (by
elimination), each seat's force as a uniform traction on its faces.

``couplings`` - agenticCAE's own: each of the 25 bolt positions tied rigidly to a reference node on
its axis whose translations alone are held (an RBE2); each seat's force on a reference node on its
axis, spread to the seat's nodes with equal weights (an RBE3), the seat's tilt read off that node's
rotation. For checking this setup against agenticCAE's recorded answer on its own mesh.

Each run gets a fresh directory on Linux's own disk (``$ASTER_RUNS``, ``~/aster_runs`` by default):
Code_Aster pickles its session into its working directory and restores it on the next start there,
and MUMPS writes its factors out of core there - through WSL's bridge to a Windows drive that crawls.
Writes ``aster_<mode>.npz`` beside the mesh - displacement at every TET10 node, the reactions, the
times (and, for couplings, each seat's reference rotation).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(sys.argv[1])
MODE = sys.argv[2] if len(sys.argv) > 2 else "clamped"
MEMORY_MB = int(sys.argv[3]) if len(sys.argv) > 3 else 7000
E_MPA, NU = 169_000.0, 0.275


def block(out, title: str, rows: list[str]) -> None:
    out.write(f"{title}\n")
    for start in range(0, len(rows), 8):
        out.write(" ".join(rows[start : start + 8]) + "\n")
    out.write("FINSF\n%\n")


def write_mail(path: Path, nodes, tets, tris, group, names, extra_nodes=None, node_groups=None) -> None:
    """The mesh in Code_Aster's text format: nodes, TETRA10 cells (group BULK), the labelled TRIA6
    skin (a group per seat, BOLTS, and SKIN for them all); for couplings, reference nodes as POI1
    cells (group REFPT) and the node groups the couplings tie.

    The reader stops at 80 characters a line, and a TETRA10 with seven-digit node names runs past
    it - so each is written over two lines."""
    everything = nodes if extra_nodes is None else np.vstack([nodes, extra_nodes])
    with path.open("w") as out:
        out.write("TITRE\ndesign\nFINSF\n%\nCOOR_3D\n")
        np.savetxt(
            out,
            np.column_stack([np.arange(1, len(everything) + 1), everything]),
            fmt="N%d %.9e %.9e %.9e",
        )
        out.write("FINSF\n%\nTETRA10\n")
        np.savetxt(
            out,
            np.column_stack([np.arange(1, len(tets) + 1), tets + 1]),
            fmt="M%d" + " N%d" * 5 + "\n " + " N%d" * 5,
        )
        out.write("FINSF\n%\nTRIA6\n")
        first = len(tets) + 1
        keep = group >= 0
        chosen = tris[keep]
        ids = np.arange(first, first + len(chosen))
        np.savetxt(out, np.column_stack([ids, chosen + 1]), fmt="M%d" + " N%d" * 6)
        out.write("FINSF\n%\n")
        poi = []
        if extra_nodes is not None:
            start = first + len(chosen)
            poi = [f"M{start + i}" for i in range(len(extra_nodes))]
            out.write("POI1\n")
            for i in range(len(extra_nodes)):
                out.write(f"M{start + i} N{len(nodes) + i + 1}\n")
            out.write("FINSF\n%\n")
        block(out, "GROUP_MA\nBULK", [f"M{m}" for m in range(1, len(tets) + 1)])
        block(out, "GROUP_MA\nSKIN", [f"M{m}" for m in ids])
        chosen_group = group[keep]
        for k, name in enumerate(names):
            members = ids[chosen_group == k]
            if len(members):
                block(out, f"GROUP_MA\n{name}", [f"M{m}" for m in members])
        if poi:
            block(out, "GROUP_MA\nREFPT", poi)
        for name, members in (node_groups or {}).items():
            block(out, f"GROUP_NO\n{name}", [f"N{m + 1}" for m in members])
        out.write("FIN\n")


def main() -> None:
    mesh = np.load(HERE / "tet10.npz")
    setup = json.loads((HERE / "setup.json").read_text())
    nodes, tets, tris, group = mesh["nodes"], mesh["tets"], mesh["tris"], mesh["group"]
    names = [str(n) for n in mesh["names"]]
    seats = names[:-1]
    started = time.time()
    run = Path(os.environ.get("ASTER_RUNS", Path.home() / "aster_runs")) / f"{HERE.name}_{MODE}"
    shutil.rmtree(run, ignore_errors=True)
    run.mkdir(parents=True)
    os.chdir(run)
    elem = Path(os.environ.get("CONDA_PREFIX", "")) / "lib" / "elem.1"
    if elem.exists():
        (run / "elem.1").symlink_to(elem)
    mail = run / "design.mail"

    refs, node_groups = None, None
    if MODE == "couplings":
        bolt = mesh["bolt"]
        ref_points, node_groups = [], {}
        for k, name in enumerate(seats):
            members = np.unique(tris[group == k])
            node_groups[name] = members
            axis = setup_axis(name)
            ref_points.append([axis[0], axis[1], float(nodes[members, 2].mean())])
        positions = setup["bolt_positions"]
        for p, position in enumerate(positions):
            members = np.unique(tris[bolt == p])
            node_groups[f"B{p:02d}"] = members
            ref_points.append([position["xy"][0], position["xy"][1], float(nodes[members, 2].mean())])
        refs = np.asarray(ref_points)
        first_ref = len(nodes)
        for i, name in enumerate([*seats, *[f"B{p:02d}" for p in range(len(positions))]]):
            node_groups[f"R_{name}"] = np.array([first_ref + i])
    write_mail(mail, nodes, tets, tris, group, names, refs, node_groups)
    written = time.time() - started

    def area(k):
        p = nodes[tris[group == k][:, :3]]
        return 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1).sum()

    from code_aster import CA
    from code_aster.Cata.Syntax import _F  # noqa: N811 - Code_Aster's own name
    from code_aster.Commands import (
        AFFE_CARA_ELEM,
        AFFE_CHAR_CINE,
        AFFE_CHAR_MECA,
        AFFE_MATERIAU,
        AFFE_MODELE,
        CALC_CHAMP,
        DEFI_FICHIER,
        DEFI_MATERIAU,
        LIRE_MAILLAGE,
        MECA_STATIQUE,
    )

    CA.init("--memory", str(MEMORY_MB))
    DEFI_FICHIER(ACTION="ASSOCIER", FICHIER=str(mail), UNITE=20, ACCES="OLD")
    t0 = time.time()
    ma = LIRE_MAILLAGE(UNITE=20, FORMAT="ASTER")
    mat = DEFI_MATERIAU(ELAS=_F(E=E_MPA, NU=NU))
    solver = _F(METHODE="MUMPS", ACCELERATION="LR", GESTION_MEMOIRE="AUTO", RENUM="AUTO")
    if MODE == "clamped":
        mo = AFFE_MODELE(
            MAILLAGE=ma,
            AFFE=_F(GROUP_MA=("BULK", "SKIN"), PHENOMENE="MECANIQUE", MODELISATION="3D"),
        )
        cm = AFFE_MATERIAU(MAILLAGE=ma, AFFE=_F(GROUP_MA="BULK", MATER=mat))
        fix = AFFE_CHAR_CINE(MODELE=mo, MECA_IMPO=_F(GROUP_MA="BOLTS", DX=0.0, DY=0.0, DZ=0.0))
        tractions = {n: np.asarray(setup["seats"][n]["force_N"], float) / area(k) for k, n in enumerate(seats)}
        load = AFFE_CHAR_MECA(
            MODELE=mo,
            FORCE_FACE=[_F(GROUP_MA=n, FX=t[0], FY=t[1], FZ=t[2]) for n, t in tractions.items()],
        )
        t1 = time.time()
        res = MECA_STATIQUE(MODELE=mo, CHAM_MATER=cm, EXCIT=(_F(CHARGE=fix), _F(CHARGE=load)), SOLVEUR=solver)
    else:
        mo = AFFE_MODELE(
            MAILLAGE=ma,
            AFFE=(
                _F(GROUP_MA="BULK", PHENOMENE="MECANIQUE", MODELISATION="3D"),
                _F(GROUP_MA="REFPT", PHENOMENE="MECANIQUE", MODELISATION="DIS_TR"),
            ),
        )
        cara = AFFE_CARA_ELEM(MODELE=mo, DISCRET=_F(GROUP_MA="REFPT", CARA="K_TR_D_N", VALE=(0.0,) * 6))
        cm = AFFE_MATERIAU(MAILLAGE=ma, AFFE=_F(GROUP_MA="BULK", MATER=mat))
        bolts = [f"B{p:02d}" for p in range(len(setup["bolt_positions"]))]
        fix = AFFE_CHAR_MECA(
            MODELE=mo,
            DDL_IMPO=_F(GROUP_NO=tuple("R_" + b for b in bolts), DX=0.0, DY=0.0, DZ=0.0),
            LIAISON_SOLIDE=tuple(_F(GROUP_NO=(b, "R_" + b)) for b in bolts),
        )
        rbe3 = AFFE_CHAR_MECA(
            MODELE=mo,
            LIAISON_RBE3=tuple(
                _F(
                    GROUP_NO_MAIT="R_" + s,
                    DDL_MAIT=("DX", "DY", "DZ", "DRX", "DRY", "DRZ"),
                    GROUP_NO_ESCL=s,
                    DDL_ESCL=("DX-DY-DZ",),
                    COEF_ESCL=(1.0,),
                )
                for s in seats
            ),
        )
        load = AFFE_CHAR_MECA(
            MODELE=mo,
            FORCE_NODALE=tuple(
                _F(GROUP_NO="R_" + s, FX=f[0], FY=f[1], FZ=f[2])
                for s, f in ((s, setup["seats"][s]["force_N"]) for s in seats)
            ),
        )
        t1 = time.time()
        res = MECA_STATIQUE(
            MODELE=mo,
            CHAM_MATER=cm,
            CARA_ELEM=cara,
            EXCIT=(_F(CHARGE=fix), _F(CHARGE=rbe3), _F(CHARGE=load)),
            SOLVEUR=solver,
        )
    solve = time.time() - t1
    res = CALC_CHAMP(reuse=res, RESULTAT=res, FORCE="REAC_NODA")

    def grab(name, comps):
        """Components by name: the field also holds Lagrange multipliers and, on the reference
        nodes, rotations - a stride would sweep them in."""
        sf = res.getField(name, 1).toSimpleFieldOnNodes()
        values, mask = sf.getValues()
        have = list(sf.getComponents())
        ix = [have.index(c) for c in comps]
        return np.where(np.asarray(mask)[:, ix], np.asarray(values)[:, ix], 0.0)

    u = grab("DEPL", ("DX", "DY", "DZ"))
    # Summed over every node: under couplings the held nodes are the bolts' reference nodes.
    reactions = grab("REAC_NODA", ("DX", "DY", "DZ")).sum(axis=0)
    out = {
        "u": u[: len(nodes)],
        "reactions": reactions,
        "solve_s": solve,
        "setup_s": t1 - t0,
        "mail_s": written,
        "total_s": time.time() - started,
    }
    if MODE == "couplings":
        rotation = grab("DEPL", ("DRX", "DRY", "DRZ"))
        out["seat_rotation"] = rotation[len(nodes) : len(nodes) + len(seats)]
        out["seat_translation"] = u[len(nodes) : len(nodes) + len(seats)]
    np.savez_compressed(HERE / f"aster_{MODE}.npz", **out)
    print(
        json.dumps(
            {
                "mode": MODE,
                "solve_s": solve,
                "setup_s": t1 - t0,
                "mail_s": written,
                "umax": float(np.linalg.norm(u[: len(nodes)], axis=1).max()),
                "reactions": reactions.tolist(),
            }
        )
    )
    CA.close()


def setup_axis(name: str) -> tuple[float, float]:
    """A seat's axis in the plane, as agenticCAE recorded it."""
    return {
        "BORE_AX1_S1": (0.0, 520.0),
        "BORE_AX1_S4": (0.0, 520.0),
        "BORE_AX2_S2": (246.3, 376.6),
        "BORE_AX2_S3": (246.3, 376.6),
        "BORE_MAIN_S2": (0.0, 0.0),
        "BORE_MAIN_S3": (0.0, 0.0),
    }[name]


if __name__ == "__main__":
    main()
