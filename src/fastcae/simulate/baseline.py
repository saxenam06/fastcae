"""The baseline's solver deck and the answer it gave, as the engineer handed them over, and every
answer fastcae has made for the baseline since.

**Found by the export.** A Code_Aster ``.export`` names the command file, the mesh and what the run
wrote back, each by type; without one, the files are taken by extension. Whatever is missing is
said to be missing - a project with a deck and no results has a setup and nothing to compare with.

**Imported, derived, generated.** What is read from the engineer's files is *imported*; what fastcae
computes from them without solving - the mesh's outside, which CAD faces a group lies on, a
coupling's tilt - is *derived*; what fastcae solves or meshes is *generated*, and each generated
answer says how it was made. The interface shows which is which on everything it draws.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..project import ArtifactKind, Project
from . import aster, med
from .fem import FEMesh
from .setup import Setup
from .signals import Answer, from_med

SOLVE_DIR = ".fastcae/solve"


@dataclass
class DeckFiles:
    export: Path | None = None
    comm: Path | None = None
    mesh: Path | None = None
    results: Path | None = None
    tables: list[Path] = field(default_factory=list)
    log: Path | None = None

    @property
    def complete(self) -> bool:
        return self.comm is not None and self.mesh is not None

    def to_json(self) -> dict:
        def row(path: Path | None, role: str, kind: str) -> dict:
            present = path is not None and path.exists()
            return {
                "role": role,
                "kind": kind,
                "name": path.name if path else None,
                "present": present,
                "size_bytes": path.stat().st_size if present and path else 0,
            }

        rows = [
            row(self.export, "run", "deck"),
            row(self.comm, "commands", "deck"),
            row(self.mesh, "mesh", "deck"),
            row(self.results, "results", "results"),
            *[row(t, "table", "results") for t in self.tables],
            row(self.log, "message log", "results"),
        ]
        return {
            "files": [r for r in rows if r["name"] or r["role"] in ("commands", "mesh", "results")]
        }


def deck_files(project: Project) -> DeckFiles:
    """The deck and results in a project folder: as its export names them, else by extension."""
    deck = [a.path for a in project.of_kind(ArtifactKind.FEM)]
    results = [a.path for a in project.of_kind(ArtifactKind.RESULTS)]
    exports = [p for p in deck if p.suffix.lower() == ".export"]
    if exports:
        export = exports[0]
        spec = aster.read_export(export)
        at = lambda f: export.parent / f.path  # noqa: E731
        out = DeckFiles(export=export)
        for f in spec.files:
            path = at(f)
            if f.kind == "comm" and "D" in f.mode:
                out.comm = path
            elif f.kind in ("mmed", "mail") and "D" in f.mode:
                out.mesh = path
            elif f.kind == "rmed" and "R" in f.mode:
                out.results = path
            elif f.kind in ("resu", "dat") and "R" in f.mode:
                out.tables.append(path)
            elif f.kind == "mess":
                out.log = path
        out.results = out.results if out.results and out.results.exists() else None
        out.tables = [t for t in out.tables if t.exists()]
        out.log = out.log if out.log and out.log.exists() else None
        return out
    pick = lambda paths, *ext: next((p for p in paths if p.suffix.lower() in ext), None)  # noqa: E731
    return DeckFiles(
        comm=pick(deck, ".comm"),
        mesh=pick(deck, ".med", ".mail"),
        results=pick(results, ".rmed"),
        tables=[p for p in results if p.suffix.lower() == ".resu"],
        log=pick(results, ".mess"),
    )


def _digest(*paths: Path | None) -> str:
    h = hashlib.sha256()
    for path in paths:
        if path is None or not path.exists():
            h.update(b"-")
            continue
        h.update(path.name.encode())
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 22), b""):
                h.update(chunk)
    return h.hexdigest()[:24]


@dataclass
class Deck:
    """A deck read: its files, what it asks for, its mesh."""

    files: DeckFiles
    setup: Setup
    io: dict
    skipped: list[str]
    mesh: FEMesh
    digest: str
    results_digest: str
    seconds: float = 0.0
    _answer: Answer | None = None
    _fields: dict | None = None

    @property
    def fields(self) -> dict[str, med.NodalField]:
        """The results file's nodal fields, read once."""
        if self._fields is None:
            self._fields = med.read_fields(self.files.results) if self.files.results else {}
        return self._fields

    def answer(self) -> Answer | None:
        """The engineer's own answer, from the results file."""
        if self._answer is None and self.files.results is not None:
            self._answer = from_med(self.mesh, self.fields, self.setup, source="Code_Aster")
        return self._answer

    def tables(self) -> list[aster.Table]:
        out = []
        for path in self.files.tables:
            out += aster.read_tables(path)
        return out


_lock = threading.Lock()
_decks: dict[str, Deck] = {}


def read_deck(project: Project) -> Deck | None:
    """The project's deck, read once per content; None when it has none."""
    files = deck_files(project)
    if not files.complete:
        return None
    digest = _digest(files.comm, files.mesh)
    results_digest = _digest(files.results, *files.tables)
    key = f"{project.root.resolve()}:{digest}:{results_digest}"
    with _lock:
        if key in _decks:
            return _decks[key]
        started = time.time()
        text = files.comm.read_text(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        commands, skipped = aster.parse_comm(text)
        setup, io = aster.interpret(commands)
        if files.mesh.suffix.lower() == ".mail":  # type: ignore[union-attr]
            raise ValueError(
                "meshes in Code_Aster's text format are not read yet; give the deck its MED mesh"
            )
        mesh = med.read_mesh(files.mesh)  # type: ignore[arg-type]
        setup.resolve({g for g, m in mesh.node_groups.items() if len(m) == 1})
        deck = Deck(
            files=files,
            setup=setup,
            io=io,
            skipped=skipped,
            mesh=mesh,
            digest=digest,
            results_digest=results_digest,
            seconds=time.time() - started,
        )
        _decks.clear()
        _decks[key] = deck
        return deck


# --- roles each group plays, for showing them -------------------------------------------------


def group_roles(setup: Setup) -> dict[str, list[str]]:
    """What the setup does with each group, in the deck's own terms."""
    roles: dict[str, list[str]] = {}

    def add(group: str, role: str) -> None:
        roles.setdefault(group, [])
        if role not in roles[group]:
            roles[group].append(role)

    for h in setup.held:
        for g in h.groups:
            add(g, "held")
    for r in setup.rigid:
        for g in r.groups:
            add(g, "rigid coupling reference" if g == r.reference else "rigid coupling")
    for d in setup.distributing:
        add(d.group, "distributing coupling")
        add(d.reference, "distributing coupling reference")
    for n in setup.nodal_loads:
        add(n.group, "loaded")
    for s in setup.surface_loads:
        add(s.group, "loaded")
    for o in setup.outputs:
        add(o.group, "signal")
    return roles


def summary(deck: Deck) -> dict:
    """What the deck says, for showing: files, mesh, groups, setup, and what was not read."""
    mesh = deck.mesh
    roles = group_roles(deck.setup)
    groups = []
    for name in mesh.groups():
        count = (
            len(mesh.node_groups[name])
            if name in mesh.node_groups
            else int(sum(len(v) for v in mesh.cell_groups[name].values()))
        )
        groups.append(
            {
                "name": name,
                "of": "nodes" if name in mesh.node_groups else "cells",
                "cells": {k: int(len(v)) for k, v in mesh.cell_groups.get(name, {}).items()},
                "count": int(count),
                "roles": roles.get(name, []),
            }
        )
    fields = [
        {"name": f.name, "components": f.components, "nodes": int(len(f.nodes))}
        for f in deck.fields.values()
    ]
    warnings = []
    # A point that nothing ties - a discrete element with no stiffness, no coupling, not held - is a
    # mechanism: the matrix is singular and the solver stops on it.
    points = {int(p) for p in mesh.cells.get("POI1", np.empty((0, 1), np.int64)).ravel()}
    for name, members in mesh.node_groups.items():
        if len(members) == 1 and int(members[0]) in points and name not in roles:
            warnings.append(f"{name} is a point nothing ties: the solve will find it free")
    tables = [{"columns": t.columns, "rows": len(t.rows)} for t in deck.tables()]
    return {
        "files": deck.files.to_json()["files"],
        "mesh": {
            "name": mesh.name,
            "nodes": int(mesh.n_nodes),
            "cells": {k: int(len(v)) for k, v in mesh.cells.items()},
            "unknowns": int(3 * len(np.unique(mesh.tet10))) if mesh.tet10 is not None else None,
            "bbox_mm": [float(x) for x in (*mesh.nodes.min(axis=0), *mesh.nodes.max(axis=0))],
        },
        "groups": groups,
        "setup": deck.setup.to_json(),
        "io": {k: v for k, v in deck.io.items()},
        "skipped": deck.skipped,
        "warnings": warnings,
        "fields": fields,
        "tables": tables,
        "digest": deck.digest,
        "results_digest": deck.results_digest,
        "read_s": round(deck.seconds, 2),
    }


# --- answers fastcae made for the baseline ----------------------------------------------------


def answer_path(project: Project, kind: str, digest: str) -> Path:
    return project.root / SOLVE_DIR / f"{kind}-{digest}.npz"


def store_answer(project: Project, kind: str, digest: str, answer: Answer, meta: dict) -> Path:
    path = answer_path(project, kind, digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".partial.npz")
    np.savez_compressed(
        partial,
        u=answer.u,
        rotation=answer.rotation,
        von_mises=answer.von_mises if answer.von_mises is not None else np.empty(0),
        stress=answer.stress if answer.stress is not None else np.empty((0, 6)),
        meta=np.array(json.dumps({**meta, "reactions": answer.reactions, "source": answer.source})),
    )
    partial.replace(path)
    return path


def load_answer(project: Project, kind: str, digest: str) -> tuple[Answer, dict] | None:
    path = answer_path(project, kind, digest)
    if not path.exists():
        return None
    data = np.load(path)
    meta = json.loads(str(data["meta"]))
    vm = data["von_mises"]
    stress = data["stress"]
    answer = Answer(
        source=meta.get("source", kind),
        u=data["u"],
        rotation=data["rotation"],
        von_mises=vm if vm.size else None,
        stress=stress if stress.size else None,
        reactions=meta.get("reactions", {}),
    )
    return answer, meta
