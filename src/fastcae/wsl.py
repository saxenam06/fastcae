"""Linux work, run in WSL from Windows: the compiled mesher and Code_Aster live there.

A script goes to bash on standard input rather than on a command line, so nothing in it is ever
quoted twice; micromamba's environments are activated inside it. Paths cross as ``/mnt/<drive>/``.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


def to_wsl(path: Path | str) -> str:
    """A Windows path as WSL sees it."""
    p = Path(path).resolve()
    drive = p.drive.rstrip(":").lower()
    return f"/mnt/{drive}{p.as_posix()[len(p.drive) :]}"


@dataclass
class Ran:
    """How a script ended, and what it printed."""

    code: int
    out: str
    err: str

    @property
    def ok(self) -> bool:
        return self.code == 0


def bash(script: str, timeout: float | None = None) -> Ran:
    """Run a bash script in WSL as its default user.

    Sent as bytes: a text-mode pipe on Windows turns every line ending into CRLF, and bash then
    reads each command with a stray carriage return on the end."""
    done = subprocess.run(
        ["wsl.exe", "-e", "bash", "-s"],
        input=script.replace("\r\n", "\n").encode("utf-8"),
        capture_output=True,
        timeout=timeout,
    )
    return Ran(
        code=done.returncode,
        out=done.stdout.decode("utf-8", errors="replace"),
        err=done.stderr.decode("utf-8", errors="replace"),
    )


def in_env(env: str, body: str) -> str:
    """A script body run with a micromamba environment active."""
    return f'set -e\neval "$(micromamba shell hook -s bash)"\nmicromamba activate {env}\n{body}\n'


def available(env: str) -> bool:
    """Whether WSL answers and has the environment."""
    try:
        ran = bash(in_env(env, "echo ok"), timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    return ran.ok and "ok" in ran.out
