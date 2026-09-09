"""A project: a folder of artifacts, and nothing else.

The whole configuration surface of the platform. A project is a directory; its **name is the
directory's name**; its artifacts are the files inside it, classified by extension. There is no
manifest, no schema to fill in, no per-part code path.

That is the point. Dropping a `DEEPJEB_Bracket/` folder beside `GRC_Gearbox_Housing/` makes a
second project, and if it contains a STEP file and no drawing then the system has a STEP file and
no drawing - which every stage downstream must be able to say plainly rather than fail on.

**Nothing is assumed.** What the system knows is what it can read out of the files in the folder,
and where in them it read it. There is nowhere to write down a fact by hand, which is deliberate: a
hand-written fact is indistinguishable, three stages later, from one that was measured.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

ASSETS_ROOT = Path("assets")


class ArtifactKind(StrEnum):
    """What a file is, decided by extension alone.

    Extension rather than content sniffing, deliberately: it is what a person means when they say
    "here is the CAD", it is inspectable before anything is opened, and a wrong guess is visible
    in the upload list instead of surfacing three stages later.
    """

    CAD = "cad"
    DRAWING = "drawing"
    FEM = "fem"
    DATA = "data"
    UNKNOWN = "unknown"

    @property
    def label(self) -> str:
        return {
            ArtifactKind.CAD: "CAD",
            ArtifactKind.DRAWING: "Drawing",
            ArtifactKind.FEM: "FEM setup",
            ArtifactKind.DATA: "Data",
            ArtifactKind.UNKNOWN: "Unrecognised",
        }[self]


_EXTENSIONS = {
    ".step": ArtifactKind.CAD,
    ".stp": ArtifactKind.CAD,
    ".iges": ArtifactKind.CAD,
    ".igs": ArtifactKind.CAD,
    ".brep": ArtifactKind.CAD,
    ".pdf": ArtifactKind.DRAWING,
    ".dwg": ArtifactKind.DRAWING,
    ".dxf": ArtifactKind.DRAWING,
    ".med": ArtifactKind.FEM,
    ".inp": ArtifactKind.FEM,
    ".comm": ArtifactKind.FEM,
    ".bdf": ArtifactKind.FEM,
    ".csv": ArtifactKind.DATA,
    ".json": ArtifactKind.DATA,
    ".tdms": ArtifactKind.DATA,
}


@dataclass(frozen=True)
class Artifact:
    """One file offered for extraction."""

    path: Path
    kind: ArtifactKind
    size_bytes: int

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def label(self) -> str:
        return self.kind.label

    def digest(self) -> str:
        """Content hash.

        Content-addressed rather than name-addressed, because a filename is not an identity: two
        different files can carry one name, and anything keyed on the name serves whichever it saw
        first.
        """
        h = hashlib.sha256()
        with open(self.path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return "sha256:" + h.hexdigest()


@dataclass
class Project:
    """A folder of artifacts. The only unit of configuration in the system."""

    root: Path

    @property
    def name(self) -> str:
        """The folder's name, verbatim. Rename the folder and the product renames itself."""
        return self.root.name

    @property
    def title(self) -> str:
        """The name made readable. `GRC_Gearbox_Housing` reads as `GRC Gearbox Housing`."""
        return self.name.replace("_", " ").replace("-", " ")

    def artifacts(self) -> list[Artifact]:
        """Every file in the folder, classified and ordered by kind.

        Ordered so CAD comes first: it is the one artifact every project must have, and the one
        every later stage depends on.
        """
        found = [
            Artifact(
                path=path,
                kind=_EXTENSIONS.get(path.suffix.lower(), ArtifactKind.UNKNOWN),
                size_bytes=path.stat().st_size,
            )
            for path in sorted(self.root.iterdir())
            if path.is_file() and not path.name.startswith(".")
        ]
        order = list(ArtifactKind)
        return sorted(found, key=lambda a: (order.index(a.kind), a.path.name))

    def of_kind(self, kind: ArtifactKind) -> list[Artifact]:
        return [a for a in self.artifacts() if a.kind is kind]

    def first(self, kind: ArtifactKind) -> Artifact | None:
        """The primary artifact of a kind, or None.

        Returning None rather than raising is the whole design. A project with no drawing is not a
        broken project - it is a project whose drawing has not arrived - and every caller has to
        be able to carry on and say what it could not do.
        """
        of_kind = self.of_kind(kind)
        return of_kind[0] if of_kind else None


def classify(path: Path) -> Artifact:
    """Wrap any file as an artifact, classified by extension.

    Used when a path is given directly rather than discovered, which is what happens when someone
    edits one in the interface.
    """
    return Artifact(
        path=path,
        kind=_EXTENSIONS.get(path.suffix.lower(), ArtifactKind.UNKNOWN),
        size_bytes=path.stat().st_size if path.exists() else 0,
    )


def discover(root: Path = ASSETS_ROOT) -> list[Project]:
    """Every project folder under ``root``, alphabetically."""
    if not root.exists():
        return []
    return [Project(root=path) for path in sorted(root.iterdir()) if path.is_dir()]


def open_project(name_or_path: str | Path, root: Path = ASSETS_ROOT) -> Project:
    """Open a project by folder name or by path."""
    candidate = Path(name_or_path)
    if candidate.is_dir():
        return Project(root=candidate)
    inside = root / str(name_or_path)
    if inside.is_dir():
        return Project(root=inside)
    raise FileNotFoundError(f"no project {name_or_path!r} under {root}")
