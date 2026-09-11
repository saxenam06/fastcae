"""Corrections made to a baseline before any design grows on it.

A baseline is usually made by deleting features from a production part in CAD, and deleting a
feature is not always clean. The patched surface a CAD system puts where a rib was can sit above the
floor that was under the rib - on the part in ``assets/``, 51 cm3 of material that exists in neither
the production casting nor anybody's intent.

**A baseline may not add material its reference lacks.** Where the baseline is a pure removal from
its reference, every solid point of the baseline is a solid point of the reference, and the larger
of the two signed distances removes exactly what the patch added:

    phi = max(phi_baseline, phi_reference)

Exact, not a smoothing: the reference carries the true surface at exactly the places the patch got
it wrong. The same reasoning is why a feature still *in* a baseline cannot be removed this way.
Removing it needs the surface that was underneath it, and neither file has that surface.

A correction is a decision, so it is proposed with what it would remove and applied only once a
person has approved it in ``project.json``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .. import cache
from ..geometry import check, exact_properties, load_cad, tessellate
from ..project import Artifact, Project
from .field import CODE as FIELD_CODE
from .field import Field, Grid, build_field

CODE = (*FIELD_CODE, "generate/corrections.py")

# The one kind of correction there is so far, as it is named in ``project.json``.
TRIM_TO_REFERENCE = "trim_to_reference"
KINDS = (TRIM_TO_REFERENCE,)


def approve(project: Project, kind: str) -> None:
    """Record that a person approved a correction. Checked before anything is written."""
    if kind not in KINDS:
        raise ValueError(f"{kind!r} is not a correction; there is {', '.join(KINDS)}")
    if kind == TRIM_TO_REFERENCE and project.reference() is None:
        raise ValueError("a trim needs a reference to trim to, and this project names none")
    approved = dict(project.data().get("corrections", {}))
    approved[kind] = "approved"
    project.write_data("corrections", approved)


def withdraw(project: Project, kind: str) -> None:
    """Take an approval back. The correction stops being applied; nothing else changes."""
    approved = dict(project.data().get("corrections", {}))
    approved.pop(kind, None)
    project.write_data("corrections", approved)


def approved(project: Project) -> list[str]:
    return [k for k, v in project.data().get("corrections", {}).items() if v == "approved"]


def corrected(project: Project, baseline: Field) -> tuple[Field, list[dict]]:
    """The baseline with every approved correction applied, and what each one did.

    Nobody approving anything is the common case, and returns the baseline itself.
    """
    field, applied = baseline, []
    if TRIM_TO_REFERENCE in approved(project):
        reference = project.reference()
        if reference is None:
            raise ValueError("the trim was approved but the project no longer names a reference")
        trimmed, _ = trimmed_field_for(project.root, field, reference)
        applied.append(
            {
                "kind": TRIM_TO_REFERENCE,
                "reference": reference.name,
                "removed_mm3": field.volume_mm3() - trimmed.volume_mm3(),
            }
        )
        field = trimmed
    return field, applied


def trim_to(baseline: Field, reference: Field) -> Field:
    """The baseline with every point the reference does not also hold removed.

    Cell by cell, so the two must have been sampled on one grid. Off the band a field knows only
    which side a cell is on, and that is carried as a distance of the reach, signed; a cell stays
    in the band only where the larger distance came from a value one of the fields actually stored.
    """
    if baseline.grid != reference.grid:
        raise ValueError("the baseline and the reference were not sampled on the same grid")

    cells = np.union1d(baseline.band_index, reference.band_index)
    ours, theirs = baseline.at(cells), reference.at(cells)
    ours_stored = np.isin(cells, baseline.band_index, assume_unique=True)
    theirs_stored = np.isin(cells, reference.band_index, assume_unique=True)

    take_ours = ours >= theirs
    value = np.where(take_ours, ours, theirs)
    stored = np.where(take_ours, ours_stored, theirs_stored)
    keep = stored & (np.abs(value) <= baseline.reach_mm)

    return Field(
        grid=baseline.grid,
        band_index=cells[keep].astype(np.int32),
        band_mm=value[keep].astype(np.float32),
        inside=baseline.inside & reference.inside,
        reach_mm=baseline.reach_mm,
        headroom_mm=baseline.headroom_mm,
        source_digest=f"{baseline.source_digest}|trimmed:{reference.source_digest}",
    )


def reference_field_for(
    root: Path, reference: Artifact, grid: Grid, reuse: bool = True
) -> tuple[Field, bool]:
    """The reference sampled on the baseline's grid, built once and kept.

    Read, tessellated and checked the way the baseline is. A reference that does not close cannot
    say where its inside is, and trimming to it would cut wherever it leaked.
    """
    digest = reference.digest()
    key = cache.key_for(digest, repr(grid), code=CODE)

    def build() -> Field:
        shape, _ = load_cad(reference.path)
        tess = tessellate(shape)
        health = check(tess, exact_properties(shape))
        if not health.watertight:
            raise ValueError(f"{reference.name} does not close, so it cannot be trimmed to")
        return build_field(tess, grid=grid, source_digest=digest)

    field, hit = cache.memoise(cache.entry(root, "reference-field", key), build, reuse=reuse)
    field.key = key
    return field, hit


def trimmed_field_for(
    root: Path, baseline: Field, reference: Artifact, reuse: bool = True
) -> tuple[Field, bool]:
    """The baseline trimmed to its reference, built once and kept."""
    ref, _ = reference_field_for(root, reference, baseline.grid, reuse=reuse)
    key = cache.key_for(baseline.key, ref.key, code=CODE)
    field, hit = cache.memoise(
        cache.entry(root, "trimmed-field", key), lambda: trim_to(baseline, ref), reuse=reuse
    )
    field.key = key
    return field, hit
