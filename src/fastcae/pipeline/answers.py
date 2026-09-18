"""The engineer's answers to the pipeline's questions, kept in the project's own data.

Answers are decisions, not derived results: they belong with the part, in ``project.json``, beside
the roles - not in a cache that is thrown away when the code changes. Each one is keyed by the
question's entity id and says what it settles.
"""

from __future__ import annotations

from typing import Any

SECTION = "answers"


def load(project) -> dict[str, str]:  # type: ignore[no-untyped-def]
    return {str(k): str(v) for k, v in project.data().get(SECTION, {}).items()}


def save(project, question: str, value: str | None) -> dict[str, str]:  # type: ignore[no-untyped-def]
    """Record an answer, or take it back with ``None``."""
    answers = load(project)
    if value is None:
        answers.pop(question, None)
    else:
        answers[question] = value
    project.write_data(SECTION, answers)
    return answers


def for_interfaces(answers: dict[str, str]) -> dict[str, str]:
    """``question:bore:271 -> freeze`` as the interface rules read it: ``bore:271 -> freeze``."""
    out = {}
    for question, value in answers.items():
        name = question.removeprefix("question:")
        if ":" in name and value in ("freeze", "free"):
            out[name] = value
    return out


def settings(answers: dict[str, str]) -> dict[str, Any]:
    """Answers that change a setting of the rules rather than one interface."""
    out: dict[str, Any] = {}
    inside = answers.get("question:inside")
    if inside is not None:
        out["inside"] = inside == "inside too"
    return out
