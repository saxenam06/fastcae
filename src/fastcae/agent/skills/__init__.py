"""Skills: how to compose the agent's tools for a kind of request, read when it is needed.

One markdown file each: a title, a ``when:`` line saying what requests it covers, then the recipe.
Recipes name tools and kinds of entity - never an id, a number or an example sentence, which would
become the answer to every request that looks like it.
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).parent


def index() -> dict[str, str]:
    """Every skill by name, with the line that says when it is worth reading."""
    out = {}
    for path in sorted(HERE.glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        out[path.stem] = next((ln[len("when: ") :] for ln in lines if ln.startswith("when: ")), "")
    return out


def read(name: str) -> str | None:
    path = HERE / f"{name}.md"
    return path.read_text(encoding="utf-8") if path.is_file() else None
