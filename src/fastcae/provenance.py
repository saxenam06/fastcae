"""Where a piece of information came from, and how much weight it can carry.

Every fact this system acts on has a source: a released drawing, a technical report, the CAD
itself, a previous solver setup, or nobody at all. The difference matters operationally, not
philosophically. A bore diameter measured off the B-rep and a bore diameter transcribed by hand
from a PDF are not interchangeable, and a fact with no source behind it must not be allowed to
quietly acquire authority by being repeated.

The failure this defends against is a value that was once checked, then copied, then relied on
long after whatever made it true had changed. Recording the source alongside the value is the
cheapest possible defence, because it makes "how do you know?" answerable without archaeology.

Two things this module deliberately does *not* do. It does not rank sources into a single
authority order - a drawing beats CAD for a toleranced interface and CAD beats a drawing for what
was actually built, and which applies depends on the question. And it does not resolve conflicts.
A disagreement between two sources is information; collapsing it into one number destroys that
information, so :class:`Fact` carries the disagreement and says so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SourceKind(StrEnum):
    """Where information entered the system.

    Ordered from strongest to weakest only in the loose sense that CAD and DRAWING are direct
    observations while DERIVED and ASSUMED are not. This is not a precedence order.
    """

    CAD = "cad"
    """Measured from the B-rep by an OCC query. Reproducible from assets/ alone."""

    DRAWING = "drawing"
    """Parsed from a released 2D drawing. Carries tolerance and datum authority, and is text
    without coordinates - it can say what is controlled, never which feature."""

    REPORT = "report"
    """Read from a technical report or test document."""

    FEM = "fem"
    """From a previous solver setup or solved result."""

    DERIVED = "derived"
    """Computed from other evidence. Its strength is the weakest input's."""

    ASSUMED = "assumed"
    """Nobody has checked. Present so that unchecked things are visible rather than absent."""


class EvidenceState(StrEnum):
    """What a fact's evidence adds up to. Computed, never set by hand."""

    MEASURED = "measured"
    """At least one direct observation - CAD, drawing, report or FEM - and no disagreement."""

    DERIVED = "derived"
    """Computed from other evidence, with no direct observation of its own."""

    ASSUMED = "assumed"
    """No evidence beyond somebody's judgement."""

    CONFLICTED = "conflicted"
    """Two or more sources disagree. Never silently resolved."""


@dataclass(frozen=True)
class Evidence:
    """One citation: what was consulted, how, and what it said.

    ``locator`` must be specific enough to return to. A document's name alone is not a locator; a
    document, a page and the literal text read from it is. Likewise "the CAD" is not; a named file
    and a face id is.
    """

    kind: SourceKind
    locator: str
    method: str
    detail: str = ""
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        if not self.locator:
            raise ValueError(f"{self.kind} evidence needs a locator you can go back to")

    def render(self) -> str:
        parts = [f"{self.kind}:{self.locator}", f"via {self.method}"]
        if self.confidence < 1.0:
            parts.append(f"confidence {self.confidence:.2f}")
        if self.detail:
            parts.append(self.detail)
        return " | ".join(parts)


@dataclass(frozen=True)
class Fact[T]:
    """A value together with everything known about where it came from.

    ``disagrees`` is set by whoever assembles the fact, because only they know whether two sources
    a few hundredths apart are agreeing within tolerance or disagreeing. The type cannot decide
    that: a machined diameter and a cast wall have very different ideas of "close".
    """

    value: T
    evidence: tuple[Evidence, ...] = ()
    disagrees: bool = False
    note: str = ""

    @property
    def state(self) -> EvidenceState:
        if self.disagrees:
            return EvidenceState.CONFLICTED
        if not self.evidence:
            return EvidenceState.ASSUMED
        kinds = {e.kind for e in self.evidence}
        if kinds & {SourceKind.CAD, SourceKind.DRAWING, SourceKind.REPORT, SourceKind.FEM}:
            return EvidenceState.MEASURED
        if SourceKind.DERIVED in kinds:
            return EvidenceState.DERIVED
        return EvidenceState.ASSUMED

    @property
    def confidence(self) -> float:
        """The weakest link. A chain of evidence is no better than its worst step."""
        if self.disagrees:
            return 0.0
        if not self.evidence:
            return 0.0
        return min(e.confidence for e in self.evidence)

    @property
    def trustworthy(self) -> bool:
        """Whether this may be acted on without a human looking first.

        Deliberately strict. An assumed or conflicted fact can still be displayed, discussed and
        proposed - it just cannot be the silent basis of an irreversible decision such as marking
        a face permanently unmovable.
        """
        return self.state is EvidenceState.MEASURED

    def render(self) -> str:
        head = f"{self.value}  [{self.state}]"
        if self.note:
            head += f"  ({self.note})"
        lines = [head] + [f"    - {e.render()}" for e in self.evidence]
        return "\n".join(lines)


@dataclass
class Conflict:
    """A recorded disagreement between sources about one subject.

    Kept as an object rather than a log line because the UI has to show it and the agent has to
    be able to refuse to act on it.
    """

    subject: str
    left: Evidence
    right: Evidence
    left_value: object
    right_value: object
    tolerance: str = ""

    def render(self) -> str:
        return (
            f"{self.subject}: {self.left_value} vs {self.right_value}"
            + (f" (tolerance {self.tolerance})" if self.tolerance else "")
            + f"\n    left  {self.left.render()}"
            + f"\n    right {self.right.render()}"
        )


@dataclass
class ProvenanceLog:
    """Everything asserted during one extraction, in order.

    Kept beside the result so that a question about any single value can be answered without
    re-running anything.
    """

    entries: list[tuple[str, Evidence]] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)

    def record(self, subject: str, evidence: Evidence) -> None:
        self.entries.append((subject, evidence))

    def conflict(self, conflict: Conflict) -> None:
        self.conflicts.append(conflict)

    def render(self) -> str:
        lines = [f"provenance: {len(self.entries)} assertions, {len(self.conflicts)} conflicts"]
        if self.conflicts:
            lines.append("")
            lines.append("conflicts:")
            lines += [f"  {c.render()}" for c in self.conflicts]
        return "\n".join(lines)
