"""A project: a folder of artifacts, and the decisions a person has made about them.

The whole configuration surface of the platform. A project is a directory; its **name is the
directory's name**; its artifacts are the files inside it, classified by extension. There is no
schema to fill in and no per-part code path.

**Decisions live in one file.** Which of two CAD files a design grows from is a *role*, and a role
cannot be read out of geometry. ``project.json`` holds those decisions, and only those: a person
makes them, the system checks them before writing, and a project without the file behaves exactly
as if nobody had decided anything.

That is the point. Dropping a `DEEPJEB_Bracket/` folder beside `GRC_Gearbox_Housing/` makes a
second project, and if it contains a STEP file and no drawing then the system has a STEP file and
no drawing - which every stage downstream must be able to say plainly rather than fail on.

**Nothing is assumed.** What the system knows is what it can read out of the files in the folder,
and where in them it read it. There is nowhere to write down a fact by hand, which is deliberate: a
hand-written fact is indistinguishable, three stages later, from one that was measured.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

ASSETS_ROOT = Path("assets")

# The file a project's decisions are written to. Not an artifact: it says things *about* the
# artifacts, and listing it among them would offer it up for extraction as data.
DATA_FILE_NAME = "project.json"

# The roles a CAD file can hold. The baseline is what every design grows from; the reference is
# another version of the same part, kept to compare against.
ROLES = ("baseline", "reference")


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
            if path.is_file() and not path.name.startswith(".") and path.name != DATA_FILE_NAME
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

    # --- decisions ---------------------------------------------------------------------------

    def data(self) -> dict[str, Any]:
        """Everything written to ``project.json``, or nothing if there is no such file."""
        path = self.root / DATA_FILE_NAME
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def write_data(self, section: str, value: Any) -> None:
        """Replace one section of ``project.json``, keeping every other section as it was."""
        data = self.data()
        data[section] = value
        (self.root / DATA_FILE_NAME).write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def roles(self) -> dict[str, str]:
        """Which file holds which role, by name. Empty when nobody has said."""
        return dict(self.data().get("roles", {}))

    def set_roles(self, **roles: str) -> None:
        """Record which CAD file holds each role.

        Checked before anything is written. A role naming a file that is not there, or one that is
        not CAD, would fall back to whichever file happens to sort first - the silent choice a
        role exists to replace.
        """
        cad = {a.name for a in self.of_kind(ArtifactKind.CAD)}
        for role, name in roles.items():
            if role not in ROLES:
                raise ValueError(f"{role!r} is not a role; roles are {', '.join(ROLES)}")
            if name not in cad:
                raise ValueError(f"{name!r} is not a CAD file in {self.root.name}")
        self.write_data("roles", dict(roles))

    def baseline(self) -> Artifact | None:
        """The CAD every design grows from: the one named as baseline, else the first CAD."""
        return self._holding("baseline") or self.first(ArtifactKind.CAD)

    def reference(self) -> Artifact | None:
        """The CAD kept to compare against, if one is named. Never guessed."""
        return self._holding("reference")

    def _holding(self, role: str) -> Artifact | None:
        name = self.roles().get(role)
        if name is None:
            return None
        return next((a for a in self.of_kind(ArtifactKind.CAD) if a.name == name), None)


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
