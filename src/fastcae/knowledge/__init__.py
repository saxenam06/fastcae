"""Design knowledge as data: what a default or a platform rule rests on, each with its source.

Code that fills a block reads its ranges and rules from here, the study cites where they came from,
and the engineer can see and change them. A value here is a starting point that says what it is -
never a hidden constant.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_HERE = Path(__file__).parent


@lru_cache(maxsize=1)
def _catalogue() -> dict[str, Any]:
    return json.loads((_HERE / "materials.json").read_text(encoding="utf-8"))


def materials() -> list[dict[str, Any]]:
    """Every casting material the catalogue holds, each with its properties and their source."""
    return [dict(m) for m in _catalogue()["materials"]]


def material(ref: str) -> dict[str, Any] | None:
    """One material by its id, or None."""
    return next((dict(m) for m in _catalogue()["materials"] if m["id"] == ref), None)


def default_material() -> tuple[str, str]:
    """The material a part is taken to be cast in when nothing says, and why."""
    entry = _catalogue()["default"]
    return str(entry["id"]), str(entry["source"])


def rule(name: str) -> tuple[float, str]:
    """A platform rule's value and where it comes from."""
    entry = _catalogue()["rules"][name]
    return float(entry["value"]), str(entry["source"])


def rib_start() -> dict[str, Any]:
    """Where a new variant of ribs starts, with its source: how thick, how far apart, how tall,
    how many, and how many choices of each radius and draft."""
    return dict(_catalogue()["rib_start"])


def rib_height() -> dict[str, Any]:
    """How tall ribs are when nothing says, in thicknesses of the rib - ``low``, ``high``, ``step``
    and ``suggested`` - with its source: each end never taller than what it meets."""
    start = rib_start()
    return {**start["height_thicknesses"], "source": str(start["source"])}
