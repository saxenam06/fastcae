"""Derived results, kept so they are computed once rather than once per restart.

Reading the CAD takes ten seconds and building a distance field takes three minutes. Neither
depends on anything but the files in the project folder and the code that reads them, so neither
should be paid twice for the same inputs.

**Which source, though, is declared per result.** See :func:`code_digest`.

**Keyed on content, never on time.** A cache entry names the digest of every artifact that fed it
*and* a digest of the source that produced it. Change the STEP file and the key changes. Change the
detector and the key changes. Nothing goes stale silently, and there is no timestamp to be wrong
about and no "clear the cache" ritual to remember.

Including the source is what makes that safe rather than merely convenient. A cache keyed on inputs
alone hands back yesterday's answer from today's code, and the failure looks like the code not
working - which is worse than the cost it saved.

**Disposable by construction.** Everything here can be rebuilt from the project folder. A missing,
corrupt or unreadable entry is a miss, never an error, so deleting the directory is always safe.

Entries live in ``<project>/.fastcae/``. Inside the project, because a cache belongs to the part it
describes and should travel with it; hidden, because it is derived and the folder is somebody's
data directory. ``Project.artifacts()`` skips dotted names, so nothing here is ever mistaken for an
artifact.
"""

from __future__ import annotations

import hashlib
import pickle
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CACHE_DIR_NAME = ".fastcae"

# How many entries of one kind to keep. Fields at several voxel sizes are all worth having; six
# generations of the same one are 350 MB of files nothing will ask for again.
KEEP_PER_KIND = 4

_digests: dict[tuple[str, ...], str] = {}


def code_digest(modules: Sequence[str]) -> str:
    """A digest of the named source files, given relative to this package.

    Named rather than discovered. Hashing the whole package looks safer and is worse: editing the
    interface, or a route, or an unrelated parser throws away a result that took minutes and had
    nothing to do with any of them. Naming the modules a result actually depends on means a change
    invalidates exactly what it could have changed.
    """
    key = tuple(sorted(modules))
    if key not in _digests:
        h = hashlib.sha256()
        root = Path(__file__).parent
        for name in key:
            path = root / name
            h.update(name.encode())
            h.update(path.read_bytes() if path.is_file() else b"missing")
        _digests[key] = h.hexdigest()[:16]
    return _digests[key]


def key_for(*parts: str, code: Sequence[str] = ()) -> str:
    """A cache key from what a result depends on: its inputs, and the code that produced it."""
    h = hashlib.sha256()
    for part in (*parts, code_digest(code)):
        h.update(part.encode())
        h.update(b"\0")
    return h.hexdigest()[:32]


@dataclass(frozen=True)
class Entry:
    """Where one cached result lives, and whether it is there."""

    path: Path
    kind: str
    key: str

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    @property
    def size_bytes(self) -> int:
        return self.path.stat().st_size if self.exists else 0


def entry(root: Path, kind: str, key: str, suffix: str = ".pickle") -> Entry:
    return Entry(path=root / CACHE_DIR_NAME / f"{kind}-{key}{suffix}", kind=kind, key=key)


def load(item: Entry) -> Any | None:
    """Whatever was stored, or None.

    Any failure is a miss. An entry written by code that has since changed is already excluded by
    the key, so what is left is a truncated write or a file somebody edited, and neither is worth
    raising over when the answer can simply be recomputed.
    """
    if not item.exists:
        return None
    try:
        with open(item.path, "rb") as handle:
            return pickle.load(handle)
    except Exception:
        return None


def store(item: Entry, value: Any) -> Entry:
    """Write a result, atomically.

    Through a temporary file and a rename, because a process interrupted mid-write would otherwise
    leave a half-entry that looks present. The rename is what makes "the file exists" mean "the
    result is complete".
    """
    item.path.parent.mkdir(parents=True, exist_ok=True)
    temporary = item.path.with_suffix(item.path.suffix + ".partial")
    with open(temporary, "wb") as handle:
        pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)
    temporary.replace(item.path)
    return item


def memoise(item: Entry, build: Callable[[], Any], reuse: bool = True) -> tuple[Any, bool]:
    """Load if it is there, otherwise build and keep it. Returns the value and whether it was hit.

    ``reuse=False`` rebuilds and overwrites, which is what a *re-extract* means: not "the cache is
    broken" but "read the files again".
    """
    if reuse:
        found = load(item)
        if found is not None:
            item.path.touch()  # so "oldest" means least recently used, not least recently written
            return found, True
    value = build()
    store(item, value)
    _evict(item)
    return value, False


def _evict(item: Entry) -> None:
    """Drop the oldest entries of this kind once there are more than a few.

    Without it every change leaves its results behind. Six generations of one field is 350 MB of
    files nothing will ever ask for again, in a directory nobody looks in.
    """
    siblings = sorted(
        item.path.parent.glob(f"{item.kind}-*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in siblings[KEEP_PER_KIND:]:
        path.unlink(missing_ok=True)


def clear(root: Path) -> int:
    """Remove every entry for a project. Returns how many files went."""
    directory = root / CACHE_DIR_NAME
    if not directory.is_dir():
        return 0
    gone = 0
    for path in directory.iterdir():
        if path.is_file():
            path.unlink()
            gone += 1
    return gone
