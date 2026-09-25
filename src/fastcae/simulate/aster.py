"""Code_Aster decks: read as the engineer wrote them, written for designs, and run in WSL.

**A deck** is an ``.export`` file naming the others - the command file (``.comm``), the mesh
(``.med`` or Code_Aster's own text format), and what the run writes back: results (``.rmed``),
tables, the message log (``.mess``) - each against the unit number the commands refer to it by.

**Commands are read, never run.** A ``.comm`` file is Python, and running an engineer's file to find
out what it says would run whatever else it says too. It is parsed instead: each command's keywords
are read as literals - numbers, strings, tuples, ``_F(...)`` groups - and a name assigned earlier
is a reference to that command's result. A value that is not a literal (a loop, a computed list)
is reported as not read, never guessed at.

**Only what is read is used.** :func:`interpret` turns the commands into a :class:`~.setup.Setup`
and lists every command and keyword it did not interpret, so what the deck asks for and what is
solved here can be told apart.
"""

from __future__ import annotations

import ast
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .. import wsl
from .fem import FEMesh
from .setup import (
    FORCES,
    MOMENTS,
    ROTATIONS,
    TRANSLATIONS,
    Analysis,
    Distributing,
    Held,
    Material,
    NodalLoad,
    Output,
    Rigid,
    Setup,
    SurfaceLoad,
)

ENV = "aster"
RUNS = "~/aster_runs"

# ---------------------------------------------------------------------------------------------
# The .export file


@dataclass
class ExportFile:
    """One file of a run: its type (comm, mmed, rmed, resu, mess ...), path, whether it is read
    (D) or written (R), and the unit the commands open it on."""

    kind: str
    path: str
    mode: str
    unit: int


@dataclass
class Export:
    params: dict[str, str] = field(default_factory=dict)
    files: list[ExportFile] = field(default_factory=list)

    def of(self, kind: str) -> list[ExportFile]:
        return [f for f in self.files if f.kind == kind]

    def unit(self, unit: int) -> ExportFile | None:
        return next((f for f in self.files if f.unit == unit), None)


def read_export(path: Path) -> Export:
    """An ``.export`` file: ``P name value`` parameters and ``F type path mode unit`` files."""
    out = Export()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "P":
            out.params[parts[1]] = " ".join(parts[2:])
        elif len(parts) >= 5 and parts[0] == "F":
            out.files.append(
                ExportFile(kind=parts[1], path=parts[2], mode=parts[3], unit=int(parts[4]))
            )
    return out


def write_export(path: Path, export: Export) -> None:
    lines = [f"P {k} {v}" for k, v in export.params.items()]
    lines += [f"F {f.kind} {f.path} {f.mode} {f.unit}" for f in export.files]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------------------------
# Reading commands


class Ref(str):
    """A name the deck assigned earlier: a reference to that command's result."""


class NotLiteral(ValueError):
    pass


@dataclass
class Command:
    name: str
    target: str | None
    args: dict[str, Any]
    line: int


def _value(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Tuple | ast.List):
        return [_value(e) for e in node.elts]
    if isinstance(node, ast.Name):
        return Ref(node.id)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
        inner = _value(node.operand)
        if isinstance(inner, int | float):
            return -inner if isinstance(node.op, ast.USub) else inner
    if isinstance(node, ast.BinOp):
        left, right = _value(node.left), _value(node.right)
        if isinstance(node.op, ast.Mult) and isinstance(left, list) and isinstance(right, int):
            return left * right
        if isinstance(left, int | float) and isinstance(right, int | float):
            ops = {ast.Add: left + right, ast.Sub: left - right, ast.Mult: left * right}
            if isinstance(node.op, ast.Div) and right:
                return left / right
            if isinstance(node.op, ast.Pow):
                return left**right
            for kind, result in ops.items():
                if isinstance(node.op, kind):
                    return result
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_F":
        return {kw.arg: _value(kw.value) for kw in node.keywords if kw.arg}
    raise NotLiteral(ast.unparse(node)[:80])


def parse_comm(text: str) -> tuple[list[Command], list[str]]:
    """Every top-level command call in a ``.comm`` file, and what could not be read literally."""
    tree = ast.parse(text)
    commands: list[Command] = []
    skipped: list[str] = []
    for statement in tree.body:
        target = None
        call = None
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
        elif (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and isinstance(statement.value, ast.Call)
        ):
            target, call = statement.targets[0].id, statement.value
        elif isinstance(statement, ast.Import | ast.ImportFrom):
            continue
        if call is None or not isinstance(call.func, ast.Name):
            skipped.append(f"line {statement.lineno}: {ast.unparse(statement)[:80]}")
            continue
        args: dict[str, Any] = {}
        for kw in call.keywords:
            if kw.arg is None:
                skipped.append(
                    f"line {statement.lineno}: {call.func.id} **{ast.unparse(kw.value)[:40]}"
                )
                continue
            try:
                args[kw.arg] = _value(kw.value)
            except NotLiteral as why:
                skipped.append(f"line {statement.lineno}: {call.func.id} {kw.arg}={why}")
        commands.append(Command(name=call.func.id, target=target, args=args, line=statement.lineno))
    return commands, skipped


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _groups(entry: dict[str, Any]) -> list[str]:
    return [str(g) for key in ("GROUP_NO", "GROUP_MA") for g in _as_list(entry.get(key))]


# Commands that set up or close a run and carry nothing a setup needs.
_QUIET = {"DEBUT", "POURSUITE", "FIN", "DEFI_FICHIER", "LIRE_MAILLAGE", "MODI_MAILLAGE"}


def interpret(commands: list[Command]) -> tuple[Setup, dict[str, Any]]:
    """What the commands ask for, and where they read and write: the mesh's unit and format, the
    results' unit, each table's unit."""
    setup = Setup()
    io: dict[str, Any] = {
        "mesh_unit": None,
        "mesh_format": None,
        "results_unit": None,
        "tables": {},
    }
    materials: dict[str, Material] = {}
    for c in commands:
        a = c.args
        where = f"line {c.line}"
        if c.name == "LIRE_MAILLAGE":
            io["mesh_unit"] = a.get("UNITE", 20)
            io["mesh_format"] = a.get("FORMAT", "ASTER")
        elif c.name in _QUIET:
            continue
        elif c.name == "AFFE_MODELE":
            for part in _as_list(a.get("AFFE")):
                setup.model.append(
                    {
                        "groups": [str(g) for g in _as_list(part.get("GROUP_MA"))] or ["(all)"],
                        "physics": part.get("PHENOMENE"),
                        "modelling": part.get("MODELISATION"),
                    }
                )
        elif c.name == "DEFI_MATERIAU":
            elastic = a.get("ELAS")
            if isinstance(elastic, dict) and "E" in elastic and "NU" in elastic:
                materials[c.target or f"material{len(materials)}"] = Material(
                    name=c.target or f"material{len(materials)}",
                    young=float(elastic["E"]),
                    poisson=float(elastic["NU"]),
                    density=float(elastic["RHO"]) if "RHO" in elastic else None,
                )
            else:
                setup.not_read.append(f"{where}: DEFI_MATERIAU without ELAS E and NU")
        elif c.name == "AFFE_MATERIAU":
            for part in _as_list(a.get("AFFE")):
                ref = str(part.get("MATER", ""))
                if ref in materials:
                    materials[ref].groups += [str(g) for g in _as_list(part.get("GROUP_MA"))]
        elif c.name == "AFFE_CARA_ELEM":
            for part in _as_list(a.get("DISCRET")):
                setup.discrete.append(
                    {
                        "groups": [str(g) for g in _as_list(part.get("GROUP_MA"))],
                        "kind": part.get("CARA"),
                    }
                )
            for key in a:
                if key not in ("MODELE", "DISCRET"):
                    setup.not_read.append(f"{where}: AFFE_CARA_ELEM {key}")
        elif c.name in ("AFFE_CHAR_MECA", "AFFE_CHAR_CINE"):
            name = c.target or f"loads{c.line}"
            for key, value in a.items():
                if key == "MODELE":
                    continue
                for entry in _as_list(value):
                    if not isinstance(entry, dict):
                        setup.not_read.append(f"{where}: {c.name} {key}")
                        continue
                    if key in ("DDL_IMPO", "MECA_IMPO"):
                        dofs = {
                            k: float(v) for k, v in entry.items() if k in TRANSLATIONS + ROTATIONS
                        }
                        setup.held.append(Held(load_set=name, groups=_groups(entry), dofs=dofs))
                    elif key == "LIAISON_SOLIDE":
                        setup.rigid.append(Rigid(load_set=name, groups=_groups(entry)))
                    elif key == "LIAISON_RBE3":
                        setup.distributing.append(
                            Distributing(
                                load_set=name,
                                reference=str(_as_list(entry.get("GROUP_NO_MAIT"))[0]),
                                group=str(_as_list(entry.get("GROUP_NO_ESCL"))[0]),
                                reference_dofs=[str(d) for d in _as_list(entry.get("DDL_MAIT"))],
                                group_dofs=[str(d) for d in _as_list(entry.get("DDL_ESCL"))],
                                weights=[float(w) for w in _as_list(entry.get("COEF_ESCL"))],
                            )
                        )
                    elif key == "FORCE_NODALE":
                        values = {k: float(v) for k, v in entry.items() if k in FORCES + MOMENTS}
                        for g in _groups(entry):
                            setup.nodal_loads.append(
                                NodalLoad(load_set=name, group=g, values=values)
                            )
                    elif key in ("FORCE_FACE", "PRES_REP"):
                        values = {k: float(v) for k, v in entry.items() if k in (*FORCES, "PRES")}
                        for g in _groups(entry):
                            setup.surface_loads.append(
                                SurfaceLoad(load_set=name, kind=key, group=g, values=values)
                            )
                    else:
                        setup.not_read.append(f"{where}: {c.name} {key}")
        elif c.name == "MECA_STATIQUE":
            sets = [str(e.get("CHARGE")) for e in _as_list(a.get("EXCIT")) if isinstance(e, dict)]
            solver = a.get("SOLVEUR") if isinstance(a.get("SOLVEUR"), dict) else {}
            setup.analysis = Analysis(kind="linear static", load_sets=sets, solver=solver)
        elif c.name == "CALC_CHAMP":
            if setup.analysis is not None:
                for key in ("CONTRAINTE", "CRITERES", "FORCE", "DEFORMATION", "ENERGIE"):
                    setup.analysis.fields += [str(f) for f in _as_list(a.get(key))]
        elif c.name == "IMPR_RESU":
            if str(a.get("FORMAT", "RESULTAT")).upper() == "MED":
                for part in _as_list(a.get("RESU")):
                    if isinstance(part, dict) and "RESULTAT" in part:
                        io["results_unit"] = a.get("UNITE", 80)
                        if setup.analysis is not None:
                            setup.analysis.written += [
                                str(f) for f in _as_list(part.get("NOM_CHAM"))
                            ]
        elif c.name == "POST_RELEVE_T":
            for action in _as_list(a.get("ACTION")):
                if not isinstance(action, dict):
                    continue
                groups = _groups(action)
                components = (
                    None
                    if action.get("TOUT_CMP") == "OUI"
                    else [str(x) for x in _as_list(action.get("NOM_CMP"))]
                )
                setup.outputs.append(
                    Output(
                        name=str(action.get("INTITULE", groups[0] if groups else "?")).strip(),
                        group=groups[0] if groups else "",
                        field=str(action.get("NOM_CHAM", "")),
                        components=components,
                        operation=str(action.get("OPERATION", "EXTRACTION")),
                        table=c.target or "",
                    )
                )
        elif c.name == "IMPR_TABLE":
            io["tables"][str(a.get("TABLE", ""))] = a.get("UNITE", 8)
        else:
            setup.not_read.append(f"{where}: {c.name}")
    setup.materials = list(materials.values())
    return setup, io


# ---------------------------------------------------------------------------------------------
# Writing a deck


def _fmt(value: float) -> str:
    return repr(float(value))


def _names(names: list[str]) -> str:
    quoted = ", ".join(f"'{n}'" for n in names)
    return f"({quoted},)" if len(names) == 1 else f"({quoted})"


def write_comm(
    setup: Setup,
    mesh_format: str = "MED",
    mesh_unit: int = 20,
    results_unit: int = 80,
    table_unit: int = 81,
    memory_note: str = "",
) -> str:
    """A command file asking for exactly what ``setup`` holds, in the order Code_Aster reads it."""
    lines = [
        "DEBUT(LANG='EN')",
        "",
        f"mesh = LIRE_MAILLAGE(FORMAT='{mesh_format}', UNITE={mesh_unit})",
        "",
    ]
    parts = []
    for part in setup.model:
        groups = [g for g in part["groups"] if g != "(all)"]
        where = f"GROUP_MA={_names(groups)}" if groups else "TOUT='OUI'"
        parts.append(
            f"        _F({where}, PHENOMENE='{part['physics']}', "
            f"MODELISATION='{part['modelling']}'),"
        )
    lines += ["model = AFFE_MODELE(", "    MAILLAGE=mesh,", "    AFFE=(", *parts, "    ),", ")", ""]
    if setup.discrete:
        discrete = [
            f"        _F(GROUP_MA={_names(d['groups'])}, CARA='{d['kind']}', VALE=(0.0,) * 6),"
            for d in setup.discrete
        ]
        lines += [
            "points = AFFE_CARA_ELEM(",
            "    MODELE=model,",
            "    DISCRET=(",
            *discrete,
            "    ),",
            ")",
            "",
        ]
    for m in setup.materials:
        rho = f", RHO={_fmt(m.density)}" if m.density is not None else ""
        lines += [
            f"{m.name} = DEFI_MATERIAU(ELAS=_F(E={_fmt(m.young)}, NU={_fmt(m.poisson)}{rho}))",
            "",
        ]
    assigned = [
        f"        _F({'GROUP_MA=' + _names(m.groups) if m.groups else 'TOUT=' + repr('OUI')}, "
        f"MATER={m.name}),"
        for m in setup.materials
    ]
    lines += [
        "materials = AFFE_MATERIAU(",
        "    MAILLAGE=mesh,",
        "    AFFE=(",
        *assigned,
        "    ),",
        ")",
        "",
    ]

    sets: dict[str, dict[str, list[str]]] = {}

    def add(load_set: str, key: str, text: str) -> None:
        sets.setdefault(load_set, {}).setdefault(key, []).append(text)

    for h in setup.held:
        dofs = ", ".join(f"{k}={_fmt(v)}" for k, v in h.dofs.items())
        add(h.load_set, "DDL_IMPO", f"_F(GROUP_NO={_names(h.groups)}, {dofs})")
    for r in setup.rigid:
        add(r.load_set, "LIAISON_SOLIDE", f"_F(GROUP_NO={_names(r.groups)})")
    for d in setup.distributing:
        add(
            d.load_set,
            "LIAISON_RBE3",
            f"_F(GROUP_NO_MAIT='{d.reference}', DDL_MAIT={_names(d.reference_dofs)}, "
            f"GROUP_NO_ESCL='{d.group}', DDL_ESCL={_names(d.group_dofs)}, "
            f"COEF_ESCL=({', '.join(_fmt(w) for w in d.weights)},))",
        )
    for n in setup.nodal_loads:
        values = ", ".join(f"{k}={_fmt(v)}" for k, v in n.values.items())
        add(n.load_set, "FORCE_NODALE", f"_F(GROUP_NO='{n.group}', {values})")
    for s in setup.surface_loads:
        values = ", ".join(f"{k}={_fmt(v)}" for k, v in s.values.items())
        add(s.load_set, s.kind, f"_F(GROUP_MA='{s.group}', {values})")
    for name, keys in sets.items():
        lines += [f"{name} = AFFE_CHAR_MECA(", "    MODELE=model,"]
        for key, entries in keys.items():
            lines += [f"    {key}=("] + [f"        {e}," for e in entries] + ["    ),"]
        lines += [")", ""]
    active = setup.analysis.load_sets if setup.analysis and setup.analysis.load_sets else list(sets)
    solver = setup.analysis.solver if setup.analysis else {"METHODE": "MUMPS"}
    solver_text = ", ".join(f"{k}={v!r}" for k, v in solver.items()) or "METHODE='MUMPS'"
    cara = "    CARA_ELEM=points,\n" if setup.discrete else ""
    lines += [
        "result = MECA_STATIQUE(",
        "    MODELE=model,",
        "    CHAM_MATER=materials,",
        *([cara.rstrip("\n")] if cara else []),
        f"    EXCIT=({', '.join(f'_F(CHARGE={s})' for s in active)},),",
        f"    SOLVEUR=_F({solver_text}),",
        ")",
        "",
        "result = CALC_CHAMP(",
        "    reuse=result,",
        "    RESULTAT=result,",
        "    CONTRAINTE=('SIGM_NOEU',),",
        "    CRITERES=('SIEQ_NOEU',),",
        "    FORCE=('REAC_NODA',),",
        ")",
        "",
        "IMPR_RESU(",
        "    FORMAT='MED',",
        f"    UNITE={results_unit},",
        "    RESU=_F(RESULTAT=result, NOM_CHAM=('DEPL', 'SIGM_NOEU', 'SIEQ_NOEU', 'REAC_NODA')),",
        ")",
        "",
    ]
    if setup.outputs:
        actions = []
        for o in setup.outputs:
            which = "TOUT_CMP='OUI'" if o.components is None else f"NOM_CMP={_names(o.components)}"
            actions.append(
                f"        _F(INTITULE='{o.name}', GROUP_NO='{o.group}', RESULTAT=result, "
                f"NOM_CHAM='{o.field}', {which}, OPERATION='{o.operation}'),"
            )
        lines += ["signals = POST_RELEVE_T(", "    ACTION=(", *actions, "    ),", ")", ""]
        lines += [f"IMPR_TABLE(TABLE=signals, UNITE={table_unit}, FORMAT='TABLEAU')", ""]
    lines += ["FIN()", ""]
    head = f"# {memory_note}\n" if memory_note else ""
    return head + "\n".join(lines)


def write_mail(mesh: FEMesh, path: Path, title: str = "mesh") -> None:
    """The mesh in Code_Aster's own text format: nodes, cells by type, groups.

    Its reader stops at 80 characters a line; a TETRA10 with seven-digit node names runs past it, so
    each is written over two lines."""
    order = [
        k for k in ("TETRA10", "TETRA4", "TRIA6", "TRIA3", "SEG3", "SEG2", "POI1") if mesh.count(k)
    ]
    first: dict[str, int] = {}
    with path.open("w", encoding="ascii") as out:
        out.write(f"TITRE\n{title}\nFINSF\n%\nCOOR_3D\n")
        np.savetxt(
            out,
            np.column_stack([np.arange(1, mesh.n_nodes + 1), mesh.nodes]),
            fmt="N%d %.12e %.12e %.12e",
        )
        out.write("FINSF\n%\n")
        number = 1
        for kind in order:
            cells = mesh.cells[kind] + 1
            first[kind] = number
            ids = np.arange(number, number + len(cells))
            out.write(f"{kind}\n")
            k = cells.shape[1]
            # Code_Aster's lines hold a cell's name and five nodes; the rest go on the next.
            fmt = "M%d" + " N%d" * min(k, 5) + ("\n " + " N%d" * (k - 5) if k > 5 else "")
            np.savetxt(out, np.column_stack([ids, cells]), fmt=fmt)
            out.write("FINSF\n%\n")
            number += len(cells)

        def block(title: str, rows: list[str]) -> None:
            out.write(f"{title}\n")
            for start in range(0, len(rows), 8):
                out.write(" ".join(rows[start : start + 8]) + "\n")
            out.write("FINSF\n%\n")

        for name, parts in mesh.cell_groups.items():
            rows = [f"M{first[k] + i}" for k, idx in parts.items() if k in first for i in idx]
            if rows:
                block(f"GROUP_MA\n{name}", rows)
        for name, members in mesh.node_groups.items():
            block(f"GROUP_NO\n{name}", [f"N{i + 1}" for i in members])
        out.write("FIN\n")


# ---------------------------------------------------------------------------------------------
# Tables


@dataclass
class Table:
    columns: list[str]
    rows: list[list[str]]

    def records(self) -> list[dict[str, Any]]:
        out = []
        for row in self.rows:
            record: dict[str, Any] = {}
            for name, text in zip(self.columns, row, strict=False):
                try:
                    record[name] = (
                        float(text) if re.fullmatch(r"[-+]?[\d.]+(?:[eE][-+]?\d+)?", text) else text
                    )
                except ValueError:
                    record[name] = text
            out.append(record)
        return out


def read_tables(path: Path) -> list[Table]:
    """Tables Code_Aster printed in its TABLEAU format: a header of column names under each
    ``#`` block, then a row per line."""
    tables: list[Table] = []
    current: Table | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("#") or not line.strip():
            current = None
            continue
        cells = line.split()
        if current is None:
            current = Table(columns=cells, rows=[])
            tables.append(current)
        else:
            current.rows.append(cells)
    return tables


# ---------------------------------------------------------------------------------------------
# Running a deck


@dataclass
class Run:
    """How a Code_Aster run went: its diagnosis, its time, where its files came back to."""

    ok: bool
    diagnosis: str
    seconds: float
    folder: Path
    log_tail: str


def run(
    export: Path,
    back_to: Path | None = None,
    memory_mb: int | None = None,
    limit_s: int = 900,
    keep: bool = False,
    threads: int = 1,
) -> Run:
    """Run a deck in WSL, from a fresh folder on Linux's own disk.

    Code_Aster keeps its database in its working directory and MUMPS writes factors there; through
    WSL's bridge to a Windows drive both crawl, so the deck's inputs are copied across, the run made
    there, and the files it writes copied back - to ``back_to``, or beside the export.

    ``limit_s`` stops the run on Linux's side, where it runs: every run of a part this size has
    finished in minutes, so one going past a quarter of an hour is stuck, not slow."""
    back_to = back_to or export.parent
    back_to.mkdir(parents=True, exist_ok=True)
    spec = read_export(export)
    name = f"{export.stem}-{uuid.uuid4().hex[:8]}"
    local = Export(params=dict(spec.params), files=[])
    copy_in, copy_out = [], []
    for f in spec.files:
        source = (export.parent / f.path).resolve()
        local.files.append(
            ExportFile(kind=f.kind, path=Path(f.path).name, mode=f.mode, unit=f.unit)
        )
        if "D" in f.mode:
            copy_in.append(f"cp '{wsl.to_wsl(source)}' .")
        if "R" in f.mode:
            copy_out.append(
                f"[ -f '{Path(f.path).name}' ] && "
                f"cp '{Path(f.path).name}' '{wsl.to_wsl(back_to)}/' || true"
            )
    if memory_mb:
        local.params["memory_limit"] = str(memory_mb)
    staged = back_to / f".{name}.export"
    write_export(staged, local)
    body = "\n".join(
        [
            # Threads as the proven runs had them - OpenMP and BLAS both, from the environment.
            f"export OMP_NUM_THREADS={threads} OPENBLAS_NUM_THREADS={threads} "
            f"MKL_NUM_THREADS={threads}",
            f"RUN={RUNS}/{name}",
            'rm -rf "$RUN"; mkdir -p "$RUN"; cd "$RUN"',
            *copy_in,
            f"cp '{wsl.to_wsl(staged)}' run.export",
            "set +e",
            f"timeout --signal=TERM --kill-after=30 {int(limit_s)} "
            "run_aster run.export > run.out 2>&1",
            "code=$?",
            f"[ $code -eq 124 ] && "
            f'echo "DIAGNOSTIC JOB : STOPPED after {int(limit_s)} s" >> run.out',
            "pkill -f run_aster_main 2>/dev/null; true",
            *copy_out,
            "grep -h 'DIAGNOSTIC JOB' run.out | tail -1",
            "tail -40 run.out",
            *([] if keep else ['cd ~; rm -rf "$RUN"']),
            "exit $code",
        ]
    )
    started = time.time()
    ran = wsl.bash(wsl.in_env(ENV, body), timeout=limit_s + 120)
    staged.unlink(missing_ok=True)
    found = re.search(r"DIAGNOSTIC JOB : (\S+)", ran.out)
    diagnosis = found.group(1) if found else ("OK" if ran.ok else "FAILED")
    return Run(
        ok=ran.ok and diagnosis in ("OK", "<A>_ALARM"),
        diagnosis=diagnosis,
        seconds=time.time() - started,
        folder=back_to,
        log_tail=(ran.out + ran.err)[-4000:],
    )
