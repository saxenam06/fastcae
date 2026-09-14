"""The runner: a process of its own, outside the development server, that works through jobs -
solving the baseline again, meshing and solving it by the variant route, building, meshing and
solving every design of a campaign - while the interface watches.

**Outside the server** because a server that reloads when its code changes would kill whatever it
was doing, and a campaign takes hours. The server only writes a job down and reads how it is going.

**Jobs are files.** Each job is a folder under ``_archived_designs/_runner/jobs/``: ``job.json``
what to do, ``status.json`` how far it has got, ``events.jsonl`` what happened, in order. The runner
takes queued jobs in the order they were written; anything can read them, and a job survives the
runner stopping - it is marked as interrupted and can be run again.

**One GPU job at a time.** The card holds one solve; every step that uses it takes the GPU lock.
Meshing runs in WSL on the cores, beside it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path("_archived_designs") / "_runner"
JOBS = ROOT / "jobs"
HEARTBEAT = ROOT / "runner.json"
# A runner that has not written its heartbeat for this long is taken to have stopped.
STALE_S = 15.0

GPU = threading.Lock()


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".partial")
    partial.write_text(json.dumps(value, indent=1, default=str), encoding="utf-8")
    partial.replace(path)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@dataclass
class Job:
    """A job's folder, and what can be said to it and asked of it."""

    id: str

    @property
    def folder(self) -> Path:
        return JOBS / self.id

    def spec(self) -> dict:
        return _read(self.folder / "job.json") or {}

    def status(self) -> dict:
        return _read(self.folder / "status.json") or {"state": "unknown"}

    def update(self, **changes: Any) -> dict:
        status = {**self.status(), **changes, "updated": time.time()}
        _write(self.folder / "status.json", status)
        return status

    def event(self, message: str, **data: Any) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        with open(self.folder / "events.jsonl", "a", encoding="utf-8") as out:
            out.write(
                json.dumps({"t": time.time(), "message": message, **data}, default=str) + "\n"
            )

    def events(self, since: int = 0) -> list[dict]:
        path = self.folder / "events.jsonl"
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[since:] if line.strip()]

    def cancelled(self) -> bool:
        return (self.folder / "cancel").exists()

    def cancel(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / "cancel").write_text("", encoding="utf-8")


def submit(kind: str, project: str | None, args: dict | None = None) -> Job:
    """Write a job down for the runner, and make sure a runner is there to take it."""
    job = Job(
        id=f"{time.strftime('%Y%m%d-%H%M%S')}-{kind.replace('.', '-')}-{uuid.uuid4().hex[:6]}"
    )
    _write(
        job.folder / "job.json",
        {"kind": kind, "project": project, "args": args or {}, "created": time.time()},
    )
    job.update(
        state="queued", kind=kind, project=project, progress=0.0, message="waiting for the runner"
    )
    ensure_running()
    return job


def jobs(project: str | None = None, kind: str | None = None, limit: int = 50) -> list[dict]:
    """The latest jobs, newest first, with their status."""
    if not JOBS.exists():
        return []
    out = []
    for folder in sorted(JOBS.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        job = Job(folder.name)
        spec = job.spec()
        if project is not None and spec.get("project") != project:
            continue
        if kind is not None and not str(spec.get("kind", "")).startswith(kind):
            continue
        out.append({"id": job.id, **spec, **job.status()})
        if len(out) >= limit:
            break
    return out


def alive() -> dict | None:
    """The runner's heartbeat, when it is recent."""
    beat = _read(HEARTBEAT)
    if not beat or time.time() - float(beat.get("t", 0)) > STALE_S:
        return None
    return beat


def ensure_running() -> dict | None:
    """Start a runner when none is beating. It lives on its own: a server reload does not stop
    it."""
    beat = alive()
    if beat is not None:
        return beat
    ROOT.mkdir(parents=True, exist_ok=True)
    log = open(ROOT / "runner.log", "a", encoding="utf-8")  # noqa: SIM115 - handed to the child
    flags = 0
    if os.name == "nt":
        flags = (
            subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_NO_WINDOW
        )
    subprocess.Popen(
        [sys.executable, "-m", "fastcae.runner"],
        cwd=Path.cwd(),
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=flags,
        close_fds=True,
    )
    return None
