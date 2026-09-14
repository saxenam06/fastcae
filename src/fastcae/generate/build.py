"""A design of a launched campaign, built by any process from the campaign's folder alone.

A campaign keeps everything its designs are made from beside the project, in
``_archived_designs/<project>/<run>/``: ``campaign.json`` - the card, the part's digest, a copy of
every variant - ``study.json``, the composed version, and ``designs.jsonl``, a line a design with
the variants it holds and the values each took. :func:`build_design` reads those and nothing else -
no server, no session - and builds one design exactly as Build field on Designs builds it: the same
grid, the same placing, repair and field, the same checks.

**For a dataset, no surface.** By default the surface is not drawn - no recontour, and no check that
reads it: the field is what the mesher and the solver take, and the surface is drawn only when
someone opens the design. Every other check reads the field; the design is weighed from it.

**A worker keeps the part open.** Opening the part - what was read of its CAD, its field at the
campaign's grid, the part's own surface - takes seconds from what is kept on disk; a
:class:`Workshop` holds it, with what placing reads off the part once, for every design built after.

    from fastcae.generate.build import Workshop, build_design

    shop = Workshop.of("_archived_designs/GRC_Gearbox_Housing/w4zf5-ribs-on-face-1201")
    for index in (0, 1, 2):
        built = build_design(shop.folder, index, workshop=shop)
        built.field            # the design's Field
        built.verdict["outcome"], built.verdict["checks"]   # each with its outcome and seconds
        built.steps            # each step of the build, in seconds
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .. import extract
from .. import study as studies
from ..extract import Extraction
from ..project import ASSETS_ROOT, Project
from ..spec import Version
from . import session as sessions
from .field import Field
from .intent import FIDELITIES, Made, Opened
from .placement import _Faces


class BuildError(ValueError):
    """A design that cannot be built from its campaign's folder, and why."""


@dataclass
class Workshop:
    """A campaign's part, opened for building its designs: the project, what was read of its CAD,
    the grids it is opened at, and what placing reads off the part once."""

    folder: Path
    project: Project
    extraction: Extraction
    version: studies.StudyVersion
    opened: dict[tuple[str, float], Opened] = field(default_factory=dict)
    memo: dict = field(default_factory=dict)
    finder: _Faces | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    @staticmethod
    def of(folder: str | Path, project: str | Path | None = None) -> Workshop:
        """The part of the campaign kept in ``folder``, opened: its project is ``project`` - or,
        when not given, the one the archive sits beside, ``<root>/assets/<project>`` for a folder
        ``<root>/_archived_designs/<project>/<run>``. Refused when the part is not the one the
        campaign was made from."""
        folder = Path(folder).resolve()
        for name in ("study.json", "designs.jsonl"):
            if not (folder / name).is_file():
                raise BuildError(f"{folder} holds no {name}: it is not a campaign kept whole")
        root = Path(project) if project is not None else _project_of(folder)
        if not root.is_dir():
            raise BuildError(f"there is no project at {root}")
        chosen = Project(root=root.resolve())
        extraction = extract.run(chosen)
        manifest = folder / "campaign.json"
        said = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}
        part = said.get("part")
        if part and part != extraction.cad_digest:
            raise BuildError(
                f"{chosen.name}'s CAD is not the part campaign {folder.name} was made from"
            )
        version = studies.StudyVersion.model_validate_json(
            (folder / "study.json").read_text(encoding="utf-8")
        )
        return Workshop(folder, chosen, extraction, version)

    def faces(self) -> _Faces:
        """Which of the part's faces is nearest a point, and what a ray meets - built once."""
        if self.finder is None:
            assert self.extraction.tess is not None
            self.finder = _Faces(self.extraction.tess)
        return self.finder

    def open_at(self, point: Version, fidelity: str, radius: float) -> Opened:
        """The part opened at a fidelity and the grid of a root fillet - once each."""
        key = (fidelity, radius)
        with self.lock:
            if key not in self.opened:
                self.opened[key] = Opened.open(
                    self.project, self.extraction, point, fidelity, radius
                )
        return self.opened[key]

    def design(self, index: int) -> dict[str, Any]:
        """Design ``index`` as the campaign kept it: the variants it holds and their values."""
        if index < 0:
            raise BuildError(f"there is no design {index} in {self.folder.name}")
        with (self.folder / "designs.jsonl").open(encoding="utf-8") as lines:
            for number, line in enumerate(lines):
                if number == index:
                    return json.loads(line)
        raise BuildError(f"there is no design {index} in {self.folder.name}")


@dataclass
class Built:
    """One design of a campaign, built: its field, its verdict - the engineer's rules, then every
    check with its outcome and how long it took - and how long each step of the build took."""

    index: int
    fidelity: str
    field: Field
    verdict: dict[str, Any]
    steps: dict[str, float]
    made: Made


def build_design(
    folder: str | Path,
    index: int,
    *,
    fidelity: Literal["preview", "full"] = "preview",
    surface: bool = False,
    project: str | Path | None = None,
    workshop: Workshop | None = None,
) -> Built:
    """Design ``index`` of the campaign kept in ``folder`` - ``_archived_designs/<project>/<run>/``
    - built from that folder alone, as Build field builds it on Designs.

    ``fidelity``: ``preview``, on the grid the campaign placed its designs on, or ``full``, at a
    quarter of the design's smallest root fillet. ``surface``: False, by default, draws no surface
    - no recontour, no check that reads it - and weighs the design from its field; True draws it,
    as the interface does. ``project``: the project the campaign's part is in, when it is not the
    one the archive sits beside. ``workshop``: a part already opened with :meth:`Workshop.of`, kept
    between the designs a worker builds; opened here when not given.

    Returns a :class:`Built`: ``field``, the design's :class:`~fastcae.generate.field.Field`, the
    one the build makes; ``verdict``, its outcome, the engineer's rules as ``constraints`` and every
    check as ``checks`` - each with ``check``, ``outcome``, ``reason``, ``rule`` and ``seconds`` -
    with ``steps``, ``cut_faces`` and what it weighs; ``steps``, how long each step took, in
    seconds, opening the part at its grid included when this call opened it. Raises
    :class:`BuildError` for a design that cannot be built, with why."""
    if fidelity not in FIDELITIES:
        raise BuildError(f"fidelity is one of {', '.join(FIDELITIES)}")
    shop = workshop or Workshop.of(folder, project)
    if workshop is not None and Path(folder).resolve() != shop.folder:
        raise BuildError(f"the workshop is open on {shop.folder.name}, not {Path(folder).name}")
    design = shop.design(index)
    held = design.get("variants")
    opening = [0.0]

    def opener(point: Version, level: str, radius: float) -> Opened:
        started = time.perf_counter()
        try:
            return shop.open_at(point, level, radius)
        finally:
            opening[0] += time.perf_counter() - started

    built = sessions.built_of(
        shop.extraction,
        shop.version,
        design["values"],
        set(held) if held is not None else None,
        fidelity,
        opener=opener,
        finder=shop.faces(),
        memo=shop.memo,
        surface=surface,
    )
    if isinstance(built, str):
        raise BuildError(f"design {index} of {shop.folder.name} cannot be built: {built}")
    made, _ = built
    # Opening the part at its grid - nothing once it is open - then the build's own steps.
    steps = {"open part": round(opening[0], 3), **(made.design.stats.get("steps") or {})}
    verdict = {
        **sessions.verdict(made),
        "run": shop.folder.name,
        "index": index,
        "recipe": design.get("recipe"),
    }
    verdict["steps"] = steps
    return Built(index, fidelity, made.design.composition.field, verdict, steps, made)


def _project_of(folder: Path) -> Path:
    """The project a campaign's folder was kept for: beside the archive, in the folder projects
    live in - the inverse of :func:`.session.archive_root`."""
    archive = folder.parent
    if archive.parent.name != sessions.ARCHIVE_DIR:
        raise BuildError(
            f"{folder} is not in {sessions.ARCHIVE_DIR}/<project>/: say which project it is of"
        )
    return archive.parent.parent / ASSETS_ROOT.name / archive.name
