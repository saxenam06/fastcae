"""Reading a drawing.

Asserts the **grammar**, never the values. A drawing of a bracket carries counted callouts,
toleranced pairs, threads and datums exactly as a drawing of a casting does, because that grammar
is ASME Y14.5 and ISO rather than any component type - so a test that pinned an expected diameter
would be testing the part rather than the reader.

The parser's specific failures are guarded, because each was real: a thread specification read as a
count, a countersink angle read as a count, and two adjacent unrelated numbers read as a tolerance
band.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fastcae import drawing
from fastcae.drawing import CalloutKind
from fastcae.project import ArtifactKind, discover


@pytest.fixture(scope="module")
def read():
    for project in discover():
        artifact = project.first(ArtifactKind.DRAWING)
        if artifact is not None:
            return drawing.read(artifact.path)
    pytest.skip("no drawing in any project under assets/")


def test_a_drawing_yields_pages_and_text(read):
    assert read.pages > 0
    if not read.has_text:
        assert read.warnings, "a drawing with no text layer must say so"


def test_every_callout_cites_the_text_it_came_from(read):
    """The raw string is the locator, and the only thing that makes a reading arguable."""
    for callout in read.callouts:
        assert callout.raw.strip(), f"{callout.kind} on page {callout.page} has no source text"
        assert 1 <= callout.page <= read.pages


def test_a_toleranced_pair_becomes_a_nominal_and_a_band(read):
    toleranced = [c for c in read.callouts if c.tolerance is not None]
    if not toleranced:
        pytest.skip("this drawing states no toleranced dimensions")

    for callout in toleranced:
        assert callout.upper is not None and callout.lower is not None
        assert callout.upper > callout.lower
        assert callout.nominal == pytest.approx((callout.upper + callout.lower) / 2)
        # A band that is a large fraction of the size is two unrelated numbers that happened to be
        # adjacent in the extracted text, not a tolerance.
        assert callout.tolerance < 0.02 * abs(callout.nominal)


def test_a_thread_specification_is_not_read_as_a_count(read):
    """`M5X0.8 - 6H` is one thread, not five of something.

    The count regex matched the digit inside the thread designation, because it is followed by an
    X. Guarded by requiring that nothing alphanumeric precedes the count.
    """
    for callout in read.of_kind(CalloutKind.COUNTED):
        assert callout.count is not None
        # A genuine repeat count is stated at the start of a callout, not buried mid-token.
        index = callout.raw.upper().find(f"{callout.count}X")
        if index > 0:
            assert not callout.raw[index - 1].isalnum(), callout.raw
            assert callout.raw[index - 1] != ".", callout.raw


def test_a_countersink_angle_is_not_read_as_a_size(read):
    """`10.05 x 90` is a countersink, and 90 is degrees rather than millimetres."""
    for callout in read.of_kind(CalloutKind.COUNTED):
        assert callout.value is not None
        assert "NEAR SIDE" not in callout.raw.upper() or callout.value != 90.0


def test_counts_are_positive_and_plausible(read):
    for callout in read.of_kind(CalloutKind.COUNTED):
        assert callout.count is not None and 1 < callout.count < 10_000


def test_datums_are_deduplicated_across_pages(read):
    letters = read.datums()
    assert len(letters) == len(set(letters))
    for letter in letters:
        assert 1 <= len(letter) <= 2 and letter.isupper()


def test_units_are_read_or_the_assumption_is_declared(read):
    """Never silently assumed. A drawing in inches read as millimetres is wrong by 25x."""
    if not read.units:
        assert any("assumed" in w for w in read.warnings)


def test_the_summary_is_serialisable(read):
    """It crosses the HTTP boundary, so it has to be plain data."""
    import json

    json.dumps(drawing.summarise(read))


def test_a_missing_file_is_reported_rather_than_raised(tmp_path: Path):
    result = drawing.read(tmp_path / "not-a-drawing.pdf")
    assert result.warnings
    assert result.callouts == []
