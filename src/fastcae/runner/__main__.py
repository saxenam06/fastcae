"""The runner's loop: take queued jobs in order, run each on a thread of its own, write a heartbeat.

It stops by itself when it has been idle a while, or when idle and the code it was started with has
changed - the next job submitted starts a fresh one on the new code.

    python -m fastcae.runner
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
import traceback
from pathlib import Path

from . import HEARTBEAT, JOBS, Job, _write
from .handlers import HANDLERS

IDLE_EXIT_S = 20 * 60
MAX_JOBS = 4


def code_digest() -> str:
    h = hashlib.sha256()
    for path in sorted(Path(__file__).resolve().parents[1].rglob("*.py")):
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


def run(job: Job) -> None:
    spec = job.spec()
    handler = HANDLERS.get(spec.get("kind", ""))
    job.update(state="running", started=time.time(), pid=os.getpid(), message="started")
    job.event(f"started {spec.get('kind')}")
    if handler is None:
        job.update(state="failed", finished=time.time(), error=f"no such job: {spec.get('kind')}")
        return
    try:
        result = handler(job, spec)
        job.update(
            state="cancelled" if job.cancelled() else "done",
            finished=time.time(),
            progress=1.0,
            message="done",
            result=result,
        )
        job.event("done")
    except Exception as error:  # noqa: BLE001 - every failure is the job's, reported in full
        job.update(state="failed", finished=time.time(), error=f"{type(error).__name__}: {error}")
        job.event(
            f"failed: {type(error).__name__}: {error}", traceback=traceback.format_exc()[-3000:]
        )


def main() -> None:
    started = time.time()
    code = code_digest()
    running: dict[str, threading.Thread] = {}
    last_busy = time.time()
    checked = time.time()
    # Jobs a runner that is gone left running were interrupted: say so, so they can be run again.
    if JOBS.exists():
        for folder in JOBS.iterdir():
            job = Job(folder.name)
            if job.status().get("state") == "running":
                job.update(state="interrupted", message="the runner stopped while this was running")
    while True:
        for key, thread in list(running.items()):
            if not thread.is_alive():
                del running[key]
        _write(
            HEARTBEAT,
            {
                "pid": os.getpid(),
                "t": time.time(),
                "started": started,
                "code": code,
                "running": list(running),
            },
        )
        if JOBS.exists() and len(running) < MAX_JOBS:
            queued = sorted(
                (
                    f.name
                    for f in JOBS.iterdir()
                    if f.is_dir() and Job(f.name).status().get("state") == "queued"
                ),
            )
            for name in queued[: MAX_JOBS - len(running)]:
                job = Job(name)
                job.update(state="starting")
                thread = threading.Thread(target=run, args=(job,), name=name, daemon=True)
                running[name] = thread
                thread.start()
        if running:
            last_busy = time.time()
        else:
            changed = False
            if time.time() - checked > 10.0:
                checked = time.time()
                changed = code_digest() != code
            if changed or time.time() - last_busy > IDLE_EXIT_S:
                _write(HEARTBEAT, {"pid": os.getpid(), "t": 0, "stopped": time.time()})
                return
        time.sleep(1.0)


if __name__ == "__main__":
    main()
