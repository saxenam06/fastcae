"""Reading a 2D drawing, deterministically.

Every callout this module returns cites the page it came from and the **literal string** it was
parsed out of. That is what makes a reading checkable: anyone can search the page for that string
and judge for themselves whether it was read correctly. A number typed in by hand offers nothing to
check against.

Nothing here is specific to a component. A drawing of a bracket carries the same grammar - counted
callouts, toleranced dimensions, thread specifications, datum letters, geometric tolerance frames -
because that grammar is ASME Y14.5 and ISO, not gearboxes.

**What this cannot do**, stated plainly because the next stage has to know: it reads *text*, not
geometry. It cannot tell which dimension applies to which feature, cannot read a leader line, and
cannot see anything on a scanned drawing that has no text layer at all. It extracts claims; matching
them to geometry is somebody else's job, and matching them by *value* is exactly why the values
must be exact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

# Symbols CAD systems emit for diameter. Several codepoints mean the same thing, and which one a
# given CAD system writes is not predictable, so all of them are accepted.
DIAMETER_MARKS = "⌀øØ"

# A number, optionally signed, with optional decimals.
NUM = r"[-+]?\d+(?:\.\d+)?"


class CalloutKind(StrEnum):
    DIMENSION = "dimension"
    """A length or diameter, possibly with a tolerance band."""

    COUNTED = "counted"
    """A feature repeated a stated number of times: `25X 26.00 THRU`."""

    THREAD = "thread"
    """A thread specification: `M24 - 6H`, `1-1/2-11-1/2 NPSM`, `3/4-16 PORT`."""

    DATUM = "datum"
    """A datum letter established on the drawing."""

    TOLERANCE_FRAME = "tolerance_frame"
    """A geometric tolerance and the datums it references: `0.025 A`, `0.03 EX EY EW`."""

    NOTE = "note"
    """Free text a person wrote: named faces, finish instructions, warnings."""

    DEFAULT_TOLERANCE = "default_tolerance"
    """The title block's unspecified-tolerance rule."""


@dataclass(frozen=True)
class Callout:
    """One claim read off a drawing, with the text it came from.

    ``raw`` is the locator. It is what makes a disagreement arguable: anyone can search the page
    for that string and see for themselves whether the reading was right.
    """

    kind: CalloutKind
    page: int
    raw: str
    value: float | None = None
    upper: float | None = None
    lower: float | None = None
    count: int | None = None
    is_diameter: bool = False
    """A diameter symbol survived extraction next to this value.

    Usually false, and not because the drawing lacks the symbol. The glyph lives in a symbol font
    that text extraction maps to nothing - on the drawing in ``assets/`` it survives zero times out
    of hundreds. Treat false as "unknown", never as "not a diameter".
    """

    through: bool = False
    hole_basis: str = ""
    """Why this callout reads as a hole, or empty if it does not.

    An **inference**, and named so it can be shown as one. Since the diameter symbol is lost, the
    only honest way to tell a hole size from a spacing is the rest of the callout: `THRU` says the
    feature passes through the part, and a counted pair of numbers is the ordinary form of a hole
    with a counterbore. Anything else is just a number that happened to be repeated.
    """

    text: str = ""

    @property
    def reads_as_hole(self) -> bool:
        """Whether this callout can be compared against a hole diameter at all.

        Guards the association. Without it `2X 150` - a spacing between two features - is a
        candidate to match a 150 mm hole pattern, and nothing in the text distinguishes them.
        """
        return bool(self.hole_basis)

    @property
    def nominal(self) -> float | None:
        """The middle of a toleranced pair, or the value itself."""
        if self.upper is not None and self.lower is not None:
            return (self.upper + self.lower) / 2.0
        return self.value

    @property
    def tolerance(self) -> float | None:
        """Half the band, where one was given."""
        if self.upper is None or self.lower is None:
            return None
        return abs(self.upper - self.lower) / 2.0

    def describe(self) -> str:
        bits = [f"p{self.page}", str(self.kind)]
        if self.count:
            bits.append(f"{self.count}x")
        if self.nominal is not None:
            mark = "O" if self.is_diameter else ""
            band = f" +/-{self.tolerance:.3f}" if self.tolerance else ""
            bits.append(f"{mark}{self.nominal:g}{band}")
        if self.through:
            bits.append("THRU")
        if self.text:
            bits.append(self.text[:40])
        return "  ".join(bits)


@dataclass
class DrawingRead:
    """Everything one drawing yielded, and everything it did not."""

    path: Path
    pages: int = 0
    characters: int = 0
    callouts: list[Callout] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    units: str = ""
    lines: list[tuple[int, str]] = field(default_factory=list)
    """Every line of text, with its page: what a search reads, notes and all, parsed or not."""

    def search(self, text: str) -> list[tuple[int, str]]:
        """The lines containing ``text``, case-insensitive, with their pages."""
        needle = text.lower().strip()
        return [(page, line) for page, line in self.lines if needle and needle in line.lower()]

    def of_kind(self, kind: CalloutKind) -> list[Callout]:
        return [c for c in self.callouts if c.kind is kind]

    def diameters(self) -> list[Callout]:
        """Every diameter claim, counted or not, largest first.

        The most useful view by far, because a diameter is the one quantity a drawing and a solid
        model can be compared on without interpreting either.
        """
        found = [
            c for c in self.callouts if c.is_diameter and c.nominal is not None and c.nominal > 0
        ]
        return sorted(found, key=lambda c: -(c.nominal or 0))

    def datums(self) -> list[str]:
        """The distinct datum letters the drawing establishes, across all pages."""
        return sorted({c.text for c in self.of_kind(CalloutKind.DATUM)})

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for callout in self.callouts:
            out[str(callout.kind)] = out.get(str(callout.kind), 0) + 1
        return out

    @property
    def has_text(self) -> bool:
        return self.characters > 0


def read(path: Path) -> DrawingRead:
    """Parse a drawing PDF into callouts.

    A drawing with no text layer is not an error. It returns an empty read with a warning saying
    exactly that, which is the signal that this file needs something other than a parser.
    """
    result = DrawingRead(path=path)

    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - dependency is declared
        result.warnings.append("pypdf is not installed, so no drawing could be read")
        return result

    try:
        reader = PdfReader(str(path))
    except Exception as error:
        result.warnings.append(f"could not open the PDF: {error}")
        return result

    result.pages = len(reader.pages)
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as error:
            result.warnings.append(f"page {index} text extraction failed: {error}")
            continue
        result.characters += len(text)
        result.lines.extend((index, line.strip()) for line in text.splitlines() if line.strip())
        result.callouts.extend(_parse_page(text, index))

    if not result.has_text:
        result.warnings.append(
            "no text layer - this drawing is scanned or outlined, so nothing can be parsed from "
            "it deterministically"
        )

    result.units = _units(result)
    if not result.units:
        result.warnings.append("no unit statement found; dimensions are assumed to be millimetres")

    return result


def _parse_page(text: str, page: int) -> list[Callout]:
    """Every callout on one page.

    Order matters. Counted callouts are matched before bare dimensions so that `25X 26.00 THRU`
    is read as twenty-five holes rather than as the two numbers 25 and 26.
    """
    out: list[Callout] = []
    lines = [line.strip() for line in text.splitlines()]

    for line in lines:
        if not line:
            continue
        out.extend(_counted(line, page))
        out.extend(_threads(line, page))
        out.extend(_tolerance_frames(line, page))
        out.extend(_notes(line, page))

    # Toleranced pairs run across two lines in the extracted text - the drawing stacks the upper
    # limit above the lower - so they are matched on the joined text rather than line by line.
    out.extend(_toleranced_pairs(text, page))
    out.extend(_plain_dimensions(lines, page))
    out.extend(_datums(text, page))
    out.extend(_default_tolerances(text, page))
    return out


def _counted(line: str, page: int) -> list[Callout]:
    """`25X 26.00 THRU`, `12X 10.20 35.00`, `2X 45.34`.

    The most valuable callout on any drawing: it states a count *and* a size, which together are
    enough to test against a detected pattern without interpreting anything.
    """
    # The count must not be preceded by a letter, digit or decimal point. Without that guard
    # `M5X0.8 - 6H` reads as five of something and `10.05 x 90` - a countersink angle - reads as
    # five more, because the "5" inside each is followed by an X.
    pattern = re.compile(
        rf"(?<![A-Za-z0-9.])(\d+)\s*X\s*[{DIAMETER_MARKS}]?\s*({NUM})(?!\s*°)",
        re.IGNORECASE,
    )
    out = []
    # A counted callout carrying two numbers is the ordinary form of a hole with a counterbore or
    # a depth: `12X 10.20 35.00`. One number and THRU is a plain through-hole. Either way the
    # first number is the hole, which is what makes it comparable with a detected pattern.
    numbers = re.findall(rf"(?<![A-Za-z])({NUM})", line)
    counterbore_form = len(numbers) >= 3

    for match in pattern.finditer(line):
        count, value = int(match.group(1)), float(match.group(2))
        # A repeat count of one is not a repeat. `CHAMFERS 1x45` is a chamfer specification, and
        # reading it as one of something at 45 mm invents a feature out of a note.
        if count < 2:
            continue
        # Angles are counted too - `12X 30 degrees` - and are not sizes.
        if "°" in line[match.end() : match.end() + 3]:
            continue
        marked = _looks_like_diameter(line, match.start())
        through = "THRU" in line.upper()
        if marked:
            basis = "diameter symbol"
        elif through:
            basis = "THRU"
        elif counterbore_form:
            basis = "counterbore form"
        else:
            basis = ""

        out.append(
            Callout(
                kind=CalloutKind.COUNTED,
                page=page,
                raw=line,
                value=value,
                count=count,
                is_diameter=marked,
                through=through,
                hole_basis=basis,
            )
        )
    return out


def _toleranced_pairs(text: str, page: int) -> list[Callout]:
    """Two numbers stacked as an upper and lower limit, the upper above the lower.

    This is where a drawing's authority lives. A bare round number is a nominal anyone could have
    guessed; a pair of limits is a controlled size, and the presence of the band is itself the
    evidence that the feature is toleranced.

    A band says the size is **controlled**. It does not say the size is a **diameter** - a stacked
    pair of limits is as likely to be a width, a depth or a position - so ``is_diameter`` is set
    from the symbol alone and is therefore usually false. Whoever matches one of these to geometry
    owns that inference and has to cite it.
    """
    pattern = re.compile(rf"({NUM})\s*\n\s*({NUM})")
    out = []
    for match in pattern.finditer(text):
        upper, lower = float(match.group(1)), float(match.group(2))
        if upper <= lower:
            continue
        # A real tolerance band is small relative to the size, and small in absolute terms. Both
        # tests are needed: a proportional limit alone accepted `5.0 / 4` as a 0.5 mm band on a
        # 4.5 mm dimension, which is two unrelated numbers that happened to be adjacent in the
        # extracted text. The tightest band on this drawing is 0.010 mm and the loosest real one
        # 0.060 mm, so 2% and 1 mm leave ample room.
        band = upper - lower
        nominal = (upper + lower) / 2.0
        if band > 1.0 or band > 0.02 * abs(nominal):
            continue
        out.append(
            Callout(
                kind=CalloutKind.DIMENSION,
                page=page,
                raw=match.group(0).replace("\n", " / ").strip(),
                upper=upper,
                lower=lower,
                is_diameter=_looks_like_diameter(text, match.start()),
            )
        )
    return out


def _plain_dimensions(lines: list[str], page: int) -> list[Callout]:
    """Bare dimensions, kept only where they are unambiguous.

    A drawing's extracted text is full of loose numbers - section labels, scales, sheet numbers -
    so only lines that are a number and nothing else are taken, and only above a size that rules
    out page furniture.
    """
    out = []
    for line in lines:
        stripped = line.strip(" ()")
        if not re.fullmatch(NUM, stripped):
            continue
        value = float(stripped)
        if value < 10.0:
            continue
        out.append(Callout(kind=CalloutKind.DIMENSION, page=page, raw=line.strip(), value=value))
    return out


def _threads(line: str, page: int) -> list[Callout]:
    """`M24 - 6H`, `M5X0.8 - 6H`, `1-1/2-11-1/2 NPSM`, `3/4-16 PORT`, `1/2 NPT`."""
    out = []
    for match in re.finditer(r"\bM(\d+(?:\.\d+)?)(?:\s*X\s*[\d.]+)?\s*-?\s*6[HhGg]\b", line):
        out.append(
            Callout(
                kind=CalloutKind.THREAD,
                page=page,
                raw=line,
                value=float(match.group(1)),
                text=match.group(0).strip(),
            )
        )
    for match in re.finditer(r"\b(NPSM|NPT|NPTF|UNC|UNF|PORT)\b", line, re.IGNORECASE):
        out.append(
            Callout(kind=CalloutKind.THREAD, page=page, raw=line, text=match.group(0).upper())
        )
    return out


def _tolerance_frames(line: str, page: int) -> list[Callout]:
    """A geometric tolerance and the datums it cites: `0.025 A`, `0.03 EX EY EW`.

    Their presence is the point rather than their value. A face inside a tolerance frame is a face
    the drawing controls, which is precisely the thing a design parameter must never move.
    """
    match = re.fullmatch(rf"\.?({NUM})((?:\s+[A-Z]{{1,2}}){{1,4}})\s*", line)
    if not match:
        return []
    datums = match.group(2).split()
    return [
        Callout(
            kind=CalloutKind.TOLERANCE_FRAME,
            page=page,
            raw=line.strip(),
            value=float(match.group(1)),
            text=" ".join(datums),
        )
    ]


def _datums(text: str, page: int) -> list[Callout]:
    """Datum letters the drawing establishes, taken from the tolerance frames that cite them.

    Emitted per page, so the same letter appears once per page it is used on. Deduplication is
    left to :meth:`DrawingRead.datums`, because which pages cite a datum is information worth
    keeping rather than collapsing at the point of reading.
    """
    letters: set[str] = set()
    for line in text.splitlines():
        match = re.fullmatch(rf"\.?({NUM})((?:\s+[A-Z]{{1,2}}){{1,4}})\s*", line.strip())
        if match:
            letters.update(match.group(2).split())
    return [
        Callout(kind=CalloutKind.DATUM, page=page, raw=letter, text=letter)
        for letter in sorted(letters)
    ]


def _notes(line: str, page: int) -> list[Callout]:
    """Text a person wrote. Named faces and instructions, which nothing else can supply.

    Kept because a drawing's words are often the only place a feature is *named* at all - and a
    name that comes from the drawing is worth far more than one invented downstream.
    """
    stripped = line.strip()
    if len(stripped) < 6 or len(stripped) > 90:
        return []
    if not re.fullmatch(r"[A-Z0-9 ,.:;()/&+\"'\-]+", stripped):
        return []
    words = [w for w in re.split(r"[^A-Z]+", stripped) if len(w) > 2]
    if len(words) < 2:
        return []
    return [Callout(kind=CalloutKind.NOTE, page=page, raw=stripped, text=stripped)]


def _default_tolerances(text: str, page: int) -> list[Callout]:
    """The title block's unspecified-tolerance rule.

    Everything the drawing does *not* tolerance explicitly falls under this, so it bounds how
    precisely any un-framed dimension can be believed.
    """
    if "UNSPECIFIED TOLERANCES" not in text.upper():
        return []
    window = text[text.upper().index("UNSPECIFIED TOLERANCES") :][:240]
    return [
        Callout(
            kind=CalloutKind.DEFAULT_TOLERANCE,
            page=page,
            raw=" ".join(window.split())[:200],
            text=" ".join(window.split())[:200],
        )
    ]


def _looks_like_diameter(line: str, position: int) -> bool:
    """Whether a value is a diameter, from the symbol before it.

    A window before the number rather than the character immediately preceding it, because
    extraction moves the symbol around. Expect this to return false almost always: the glyph
    typically does not survive extraction at all, which is why :attr:`Callout.hole_basis` exists.
    """
    window = line[max(0, position - 6) : position + 4]
    return any(mark in window for mark in DIAMETER_MARKS)


def _units(result: DrawingRead) -> str:
    for callout in result.callouts:
        upper = callout.raw.upper()
        if "MILLIMET" in upper:
            return "mm"
        if "INCH" in upper:
            return "in"
    return ""


def summarise(result: DrawingRead) -> dict:
    """A compact account of what the drawing yielded, for the extraction report."""
    diameters = result.diameters()
    counted = [c for c in result.of_kind(CalloutKind.COUNTED)]
    return {
        "pages": result.pages,
        "characters": result.characters,
        "has_text": result.has_text,
        "units": result.units or "assumed mm",
        "callouts": len(result.callouts),
        "by_kind": result.counts(),
        "toleranced_dimensions": sum(1 for c in result.callouts if c.tolerance is not None),
        "counted_features": len(counted),
        "largest_diameter_mm": round(diameters[0].nominal, 3) if diameters else None,
        "datums": result.datums(),
        "warnings": list(result.warnings),
    }
