"""A design's solids fused into the part's own B-rep and written as STEP and BREP
(:func:`build`), one at a time (:func:`fastcae.designs.cad.fuse`). A solid the fuse cannot take is
dropped and said so; the design goes on without it, and says what it holds."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..designs import cad

if TYPE_CHECKING:
    pass


def build(part, folder: Path, bodies: list[Any]) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Fuse a design's solids into ``part`` and write the design as STEP and BREP."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    fused = cad.fuse(part, bodies)
    failed = fused.failed
    report = {
        "plates": len(fused.plates),
        "fused": len(fused.plates) - len(failed),
        "failed": [p for p in fused.plates if p["status"] == "failed"],
        "added_L": round((fused.volume_after_mm3 - fused.volume_before_mm3) / 1e6, 3),
        "solids": fused.solids,
        "faces": fused.faces,
        "seconds": round(time.perf_counter() - started, 1),
    }
    if fused.solids != 1:
        raise RuntimeError(f"the fused design is {fused.solids} solids, not one")
    cad.write(fused.shape, folder / "design.step", folder / "design.brep")
    (folder / "cad.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report
