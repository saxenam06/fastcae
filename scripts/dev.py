"""Run the API and the UI dev server together.

Ports 8021 and 5183 rather than the conventional 8000 and 5173: something else on this machine
already holds those, and uvicorn's bind failure is quiet enough that half an hour went into
debugging routes that belonged to another process. An unusual port makes a collision obvious.

Run:  uv run python scripts/dev.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

API_PORT = 8021
UI_PORT = 5183
ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    api = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "fastcae.api.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(API_PORT),
            "--reload",
            # A reload waits for open connections to finish, and an agent's reply can be minutes of
            # streaming - or a stream whose client has gone. Without a limit the old worker never
            # exits, and the server neither answers nor restarts.
            "--timeout-graceful-shutdown",
            "3",
        ],
        cwd=ROOT,
    )
    ui = subprocess.Popen(
        ["npm.cmd" if sys.platform == "win32" else "npm", "run", "dev"], cwd=ROOT / "ui"
    )
    print(f"\n  api  http://127.0.0.1:{API_PORT}/docs\n  ui   http://localhost:{UI_PORT}/\n")
    try:
        ui.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in (ui, api):
            _stop(process)
    return 0


def _stop(process: subprocess.Popen) -> None:
    """Kill a process and everything it started.

    ``uvicorn --reload`` runs the application in a child, and ``npm run dev`` runs vite in one.
    Terminating only the parent leaves the child holding the port, which looks exactly like the
    server having survived a kill.
    """
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
