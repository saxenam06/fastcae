"""A campaign's designs solved by the runner, two or three at a time, like a conveyor: each design
built, meshed, given the deck's setup, solved and recorded, while the next is meshing and the one
after is waiting for the GPU.

**Every step is one already proven**, the route walked on the baseline:

1. **Build** - the design's field, from the campaign's folder alone
   (:func:`~fastcae.generate.build.build_design`), on the grid the campaign placed it on. A design
   its own checks reject is set aside with the check that rejected it.
2. **Mesh** - CGAL on the field in WSL, held to the deck mesh's element sizes where the design
   leaves the part as it was and to two elements through every rib it adds (:mod:`.sizes`), the
   edges of the faces loads go in through followed as lines.
3. **Setup** - the deck's groups carried by the CAD faces they lie on (:mod:`.carry`). A design that
   covers a face the deck acts on is set aside: its setup would not be the deck's.
4. **Solve** - cuDSS on the GPU.
5. **Record** - a Zarr store, a JSON record and a row of the run's metrics (:mod:`.records`).

**The GPU takes one thing at a time** - a build or a solve - and meshing runs in WSL on the cores
beside it, at most :data:`MESHING_AT_ONCE` at once.

**A step that fails is tried once more on its fallback**: a mesh from another random start; a
solve by Code_Aster, one thread, stopped on Linux's side after a quarter of an hour. Failing again,
or taking longer than :data:`DESIGN_LIMIT_S` in all, the design is set aside with its reason and the
run goes on.
"""

from __future__ import annotations

import copy
import json
import shutil
import threading
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .. import machine
from ..gpu import release
from ..project import Project, open_project
from . import aster, baseline, carry, fem, med, records, signals, sizes, solve, tetmesh
from .jobs import ROUTE

IN_FLIGHT = 3
MESHING_AT_ONCE = 2
DESIGN_LIMIT_S = 15 * 60
# A design waits to start while the runner holds more than this share of the machine's memory.
MEMORY_SHARE = 0.6
# A design whose boundary holds less than this share of a group's area in the deck lost that face.
LEAST_SHARE = 0.5
STAGES = ("build", "mesh", "setup", "solve", "record")


class SetAside(RuntimeError):
    """A design that cannot go on, and why."""


def solved_folder(project: Project, run: str) -> Path:
    from ..generate.session import archive_root

    return archive_root(project) / run / records.SOLVED


@dataclass
class Shared:
    """What every design of a run is made against, opened once."""

    project: Project
    folder: Path
    out: Path
    work: Path
    shop: object
    deck: baseline.Deck
    anchoring: carry.Anchoring
    lines: list[np.ndarray]
    groups: list[str]
    density: float | None
    meshing: threading.Semaphore = field(
        default_factory=lambda: threading.Semaphore(MESHING_AT_ONCE)
    )
    base: dict[tuple, tetmesh.SizeGrid] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    @staticmethod
    def open(project: Project, run: str) -> Shared:
        from ..generate.build import Workshop
        from ..generate.session import archive_root

        folder = archive_root(project) / run
        shop = Workshop.of(folder, project.root)
        deck = baseline.read_deck(project)
        if deck is None:
            raise RuntimeError("the project has no solver deck: nothing says how to solve a design")
        tess = shop.extraction.tess
        anchoring = carry.anchor(deck.mesh, deck.setup, tess.vertices, tess.triangles, tess.face_id)
        faces = sorted(
            {
                f
                for d in deck.setup.distributing
                if d.group in anchoring.groups
                for f in anchoring.groups[d.group].faces
            }
        )
        lines = tetmesh.face_edges(tess.vertices, tess.triangles, tess.face_id, set(faces))
        materials = deck.setup.materials
        out = folder / records.SOLVED
        out.mkdir(parents=True, exist_ok=True)
        work = folder / "_work"
        work.mkdir(parents=True, exist_ok=True)
        return Shared(
            project=project,
            folder=folder,
            out=out,
            work=work,
            shop=shop,
            deck=deck,
            anchoring=anchoring,
            lines=lines,
            groups=sorted(anchoring.groups),
            density=materials[0].density if len(materials) == 1 else None,
        )

    def base_sizes(self, grid) -> tetmesh.SizeGrid:  # type: ignore[no-untyped-def]
        """The deck mesh's element sizes on a design's grid - once a grid."""
        key = (tuple(np.round(grid.origin, 6)), float(grid.spacing_mm), tuple(grid.shape))
        with self.lock:
            if key not in self.base:
                mesh = self.deck.mesh
                tets = mesh.tet10 if mesh.tet10 is not None else mesh.cells["TETRA4"]
                self.base[key] = tetmesh.sizes_from_mesh(
                    mesh.nodes,
                    tets[:, :4],
                    np.asarray(grid.origin, float),
                    tuple(grid.shape),
                    float(grid.spacing_mm),
                )
            return self.base[key]


class Tracker:
    """Where every design of the run is, kept beside the job: a small file a design, and the run's
    counts in the job's status."""

    def __init__(self, job, total: int) -> None:  # type: ignore[no-untyped-def]
        self.job = job
        self.total = total
        self.started = time.time()
        self.lock = threading.Lock()
        self.designs: dict[int, dict] = {}
        (job.folder / "designs").mkdir(parents=True, exist_ok=True)

    def set(self, index: int, **changes) -> None:  # type: ignore[no-untyped-def]
        with self.lock:
            state = self.designs.setdefault(index, {"index": index, "stages": {}})
            state.update(changes, updated=time.time())
            path = self.job.folder / "designs" / f"{index}.json"
            path.write_text(json.dumps(state, default=float), encoding="utf-8")
            self._status()

    def _status(self) -> None:
        done = [d for d in self.designs.values() if d.get("outcome") == "solved"]
        aside = [d for d in self.designs.values() if d.get("outcome") == "set aside"]
        flying = [d["index"] for d in self.designs.values() if d.get("outcome") is None]
        hours = max(time.time() - self.started, 1.0) / 3600.0
        rate = len(done) / hours
        self.job.update(
            stage="campaign",
            progress=(len(done) + len(aside)) / max(self.total, 1),
            message=f"{len(done)} solved, {len(aside)} set aside of {self.total}"
            + (f" · {rate:.1f} an hour" if done else ""),
            solved=len(done),
            set_aside=len(aside),
            in_flight=flying,
            per_hour=rate if done else None,
            total=self.total,
        )


def _room(tracker: Tracker, index: int) -> float:
    """Wait, before a design takes its first stage, while the runner holds more of the machine's
    memory than :data:`MEMORY_SHARE` - the others in flight finish and hand theirs back. Returns
    the seconds waited."""
    limit = MEMORY_SHARE * machine.physical_gb()
    t0 = time.time()
    said = False
    while machine.committed_gb() > limit and not tracker.job.cancelled():
        if not said:
            tracker.set(index, stage="waiting")
            tracker.job.event(
                f"design {index}: waiting - the runner holds {machine.committed_gb():.1f} GB "
                f"of the {limit:.1f} GB it may use",
                design=index,
            )
            said = True
        time.sleep(5.0)
    return time.time() - t0


def _timed(tracker: Tracker, index: int, name: str, started: float):  # type: ignore[no-untyped-def]
    """Enter a stage: say so, and refuse when the design has already run too long."""
    if time.time() - started > DESIGN_LIMIT_S:
        raise SetAside(f"over {DESIGN_LIMIT_S // 60} minutes before {name}")
    tracker.set(index, stage=name)
    return time.time()


def _mesh(shared: Shared, built, index: int, seed: int) -> tuple:  # type: ignore[no-untyped-def]
    field_ = built.field
    changed = np.asarray(built.made.design.composition.changed)
    held, info = sizes.design_sizes(field_, changed, shared.base_sizes(field_.grid))
    work = tetmesh.workspace(shared.work / f"{index}")
    try:
        with shared.meshing:
            nodes, lin, meshed = tetmesh.mesh_field(
                field_,
                work,
                sizes=held,
                lines=shared.lines,
                **{k: ROUTE[k] for k in ("cell", "facet", "distance", "edge", "threads")},
                seed=seed,
            )
    finally:
        tetmesh.clean(work)
    mesh = tetmesh.finish(nodes, lin)
    return mesh, {**meshed, "sizes": info, "seed": seed}


def _setup(shared: Shared, mesh) -> carry.Carried:  # type: ignore[no-untyped-def]
    tess = shared.shop.extraction.tess  # type: ignore[attr-defined]
    carried = carry.carry(
        shared.deck.setup, shared.anchoring, mesh, tess.vertices, tess.triangles, tess.face_id
    )
    lost = [
        f"{name} ({g['area'] / max(g['deck_area'], 1e-9):.0%} of its area)"
        for name, g in carried.groups.items()
        if g["area"] < LEAST_SHARE * g["deck_area"]
    ]
    if lost:
        raise SetAside("the design covers faces the deck acts on: " + ", ".join(lost[:4]))
    return carried


def _solve_aster(shared: Shared, carried: carry.Carried, index: int) -> signals.Answer:
    """The fallback: the carried mesh and setup written as a Code_Aster deck and run - one thread,
    stopped on Linux's side after a quarter of an hour."""
    work = shared.work / f"{index}-aster"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    aster.write_mail(carried.mesh, work / "design.mail", title=f"design {index}")
    (work / "convert.comm").write_text(
        "DEBUT(LANG='EN')\nMESH = LIRE_MAILLAGE(FORMAT='ASTER', UNITE=20)\n"
        "IMPR_RESU(FORMAT='MED', UNITE=21, RESU=_F(MAILLAGE=MESH))\nFIN()\n",
        encoding="ascii",
    )
    params = {"actions": "make_etude", "version": "stable", "ncpus": "1", "time_limit": "900"}
    aster.write_export(
        work / "convert.export",
        aster.Export(
            params={**params, "memory_limit": "4000"},
            files=[
                aster.ExportFile("comm", "convert.comm", "D", 1),
                aster.ExportFile("mail", "design.mail", "D", 20),
                aster.ExportFile("mmed", "design.med", "R", 21),
                aster.ExportFile("mess", "convert.mess", "R", 6),
            ],
        ),
    )
    converted = aster.run(work / "convert.export", limit_s=900)
    if not converted.ok:
        raise RuntimeError(f"Code_Aster did not write the mesh: {converted.diagnosis}")
    (work / "design.comm").write_text(
        aster.write_comm(carried.setup, mesh_format="MED", mesh_unit=20), encoding="ascii"
    )
    aster.write_export(
        work / "design.export",
        aster.Export(
            params={**params, "memory_limit": "7000"},
            files=[
                aster.ExportFile("comm", "design.comm", "D", 1),
                aster.ExportFile("mmed", "design.med", "D", 20),
                aster.ExportFile("rmed", "design.rmed", "R", 80),
                aster.ExportFile("resu", "design_signals.resu", "R", 81),
                aster.ExportFile("mess", "design.mess", "R", 6),
            ],
        ),
    )
    ran = aster.run(work / "design.export", limit_s=900)
    if not ran.ok:
        raise RuntimeError(f"Code_Aster: {ran.diagnosis}")
    back = med.read_mesh(work / "design.med")
    if len(back.nodes) != len(carried.mesh.nodes):
        raise RuntimeError("Code_Aster's mesh is not the one written")
    answer = signals.from_med(carried.mesh, med.read_fields(work / "design.rmed"), carried.setup)
    shutil.rmtree(work, ignore_errors=True)
    return answer


def solve_one(shared: Shared, tracker: Tracker, index: int) -> dict:
    """One design through every stage; its record, solved or set aside."""
    from ..generate.build import BuildError, build_design
    from ..runner import GPU

    job = tracker.job
    started = time.time()
    record: dict = {"run": shared.folder.name, "index": index, "started": started, "stages": {}}
    route: list[str] = []
    try:
        waited = _room(tracker, index)
        if waited:
            record["waited_s"] = waited
            started = time.time()  # the time limit counts from when it could start
        design = shared.shop.design(index)  # type: ignore[attr-defined]
        record.update(
            values=design.get("values"),
            variants=design.get("variants"),
            recipe=design.get("recipe"),
        )
        t = _timed(tracker, index, "build", started)
        try:
            with GPU:
                try:
                    built = build_design(shared.folder, index, workshop=shared.shop)
                finally:
                    release()  # the card handed back, whatever the build did with it
        except BuildError as error:
            raise SetAside(f"build: {error}") from error
        record["stages"]["build"] = time.time() - t
        record["build"] = built.verdict
        if built.verdict.get("outcome") == "reject":
            # The engineer's rules first, then the checks: whichever said no, and why.
            said = built.verdict.get("constraints", []) + built.verdict.get("checks", [])
            failed = [
                f"{c['check']}: {c.get('reason', '')}" for c in said if c["outcome"] == "reject"
            ]
            raise SetAside("its own rules reject it - " + "; ".join(failed)[:400])
        job.event(f"design {index}: built in {record['stages']['build']:.0f} s", design=index)

        t = _timed(tracker, index, "mesh", started)
        try:
            mesh, meshed = _mesh(shared, built, index, seed=int(ROUTE["seed"]))
            route.append("CGAL")
        except (tetmesh.MeshFailed, RuntimeError) as error:
            job.event(
                f"design {index}: mesh failed ({error}); again from another start", design=index
            )
            mesh, meshed = _mesh(shared, built, index, seed=int(ROUTE["seed"]) + 1)
            route.append("CGAL, second start")
        del built
        record["stages"]["mesh"] = time.time() - t
        quality = fem.quality(mesh.nodes, mesh.cells["TETRA10"])
        record["mesh"] = {
            "tets": int(len(mesh.cells["TETRA10"])),
            "nodes": int(mesh.n_nodes),
            "unknowns": int(3 * mesh.n_nodes),
            "quality_min": float(quality.min()),
            "quality_below_0.1": int((quality < 0.1).sum()),
            **{k: v for k, v in meshed.items() if k in ("seconds", "seed", "sizes")},
        }
        job.event(
            f"design {index}: meshed in {record['stages']['mesh']:.0f} s, "
            f"{record['mesh']['unknowns']:,} unknowns",
            design=index,
        )

        t = _timed(tracker, index, "setup", started)
        carried = _setup(shared, mesh)
        record["stages"]["setup"] = time.time() - t
        record["setup"] = carried.groups

        t = _timed(tracker, index, "solve", started)
        setup = copy.deepcopy(carried.setup)
        solution, failures = None, []
        # cuDSS, and once more after the card is handed back - memory other work left in a pool
        # is the likeliest reason it failed; Code_Aster only when it fails again.
        for _attempt in range(2):
            try:
                with GPU:
                    solution = solve.solve(carried.mesh, setup, gpu=True, log=lambda _: None)
                break
            except Exception as error:  # noqa: BLE001 - any failure of the GPU solve is retried
                failures.append(f"{type(error).__name__}: {error}"[:300])
                release()
        if solution is not None:
            answer = signals.from_solution(solution, "cuDSS")
            record["solver"] = {
                "name": "cuDSS",
                "residual": solution.info.get("residual"),
                "times": solution.times,
                "unknowns": solution.unknowns,
                **({"retried_after": failures[0]} if failures else {}),
            }
            route.append("cuDSS, second try" if failures else "cuDSS")
        else:
            job.event(
                f"design {index}: cuDSS failed twice ({failures[-1]}); Code_Aster instead",
                design=index,
            )
            answer = _solve_aster(shared, carried, index)
            record["solver"] = {"name": "Code_Aster", "fallback_for": failures}
            route.append("Code_Aster")
        record["solver"]["versions"] = records.versions()
        record["stages"]["solve"] = time.time() - t

        t = _timed(tracker, index, "record", started)
        found = signals.signals(carried.mesh, setup, answer)
        record["signals"] = [s.to_json() for s in found]
        record["metrics"] = records.signal_columns(found)
        if shared.density is not None:
            record["mass_kg"] = records.mass_kg(carried.mesh, shared.density)
            record["metrics"]["mass_kg"] = record["mass_kg"]
        record["store"] = records.write_store(
            shared.out / f"{index}.zarr",
            carried.mesh,
            answer,
            shared.groups,
            {"run": shared.folder.name, "index": index, "solver": record["solver"]["name"]},
        )
        record["stages"]["record"] = time.time() - t
        record.update(outcome="solved", route=" → ".join(route))
    except SetAside as why:
        record.update(outcome="set aside", reason=str(why), route=" → ".join(route))
    except Exception as error:  # noqa: BLE001 - a design that fails is set aside; the run goes on
        record.update(
            outcome="set aside",
            reason=f"{type(error).__name__}: {error}"[:500],
            route=" → ".join(route),
            traceback=traceback.format_exc()[-2000:],
        )
    record["seconds"] = time.time() - started
    records.write_record(shared.out / f"{index}.json", record)
    tracker.set(
        index,
        stage="done",
        outcome=record["outcome"],
        reason=record.get("reason", ""),
        route=record.get("route", ""),
        stages={k: round(v, 1) for k, v in record["stages"].items()},
        seconds=round(record["seconds"], 1),
    )
    said = (
        f"solved in {record['seconds']:.0f} s ({record['route']})"
        if record["outcome"] == "solved"
        else f"set aside: {record['reason']}"
    )
    job.event(f"design {index}: {said}", design=index, outcome=record["outcome"])
    return record


def solve_campaign(job, spec: dict) -> dict:  # type: ignore[no-untyped-def]
    """The runner's job: the designs asked for, ``in_flight`` at a time; those already solved are
    not solved again."""
    args = spec.get("args") or {}
    project = open_project(spec["project"])
    run = str(args["run"])
    wanted = [int(i) for i in args.get("designs") or []]
    in_flight = max(1, min(int(args.get("in_flight") or IN_FLIGHT), 4))
    job.update(stage="campaign", message="opening the part and the deck")
    shared = Shared.open(project, run)
    done = {
        int(p.stem)
        for p in shared.out.glob("*.json")
        if p.stem.isdigit() and json.loads(p.read_text(encoding="utf-8")).get("outcome") == "solved"
    }
    todo = deque(i for i in wanted if i not in done)
    tracker = Tracker(job, len(todo))
    job.event(
        f"{len(todo)} designs to solve, {in_flight} at a time"
        + (f"; {len(wanted) - len(todo)} already solved" if len(todo) < len(wanted) else "")
    )
    taking = threading.Lock()

    def worker() -> None:
        while not job.cancelled():
            with taking:
                if not todo:
                    return
                index = todo.popleft()
            solve_one(shared, tracker, index)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(in_flight)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    records.rebuild_table(shared.out)
    states = list(tracker.designs.values())
    return {
        "run": run,
        "solved": sum(s.get("outcome") == "solved" for s in states),
        "set_aside": sum(s.get("outcome") == "set aside" for s in states),
        "seconds": time.time() - tracker.started,
        "per_hour": tracker.job.status().get("per_hour"),
    }


def run_status(project: Project, run: str) -> dict:
    """What the run's records say: every design solved or set aside, with its stages and times."""
    out = solved_folder(project, run)
    rows = []
    for path in sorted(out.glob("*.json"), key=lambda p: int(p.stem) if p.stem.isdigit() else 0):
        if not path.stem.isdigit():
            continue
        try:
            r = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows.append(
            {
                "index": r.get("index"),
                "outcome": r.get("outcome"),
                "reason": r.get("reason", ""),
                "route": r.get("route", ""),
                "seconds": r.get("seconds"),
                "stages": r.get("stages") or {},
                "unknowns": (r.get("mesh") or {}).get("unknowns"),
                "mass_kg": r.get("mass_kg"),
                "metrics": r.get("metrics") or {},
            }
        )
    return {"run": run, "designs": rows}
