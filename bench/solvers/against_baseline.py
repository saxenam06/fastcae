"""A route's answer against the baseline's: the same design solved on another mesh - every seat's
tilt, the gear-mesh leads, the p99.9 stress, the largest displacement - beside the baseline
(Code_Aster on the fTetWild mesh of the slow route), with the difference of each.

    python against_baseline.py design7gpu [design7]
"""

from __future__ import annotations

import json
import sys

from common import SCRATCH, SEATS


def metrics_of(case: str, name: str) -> dict:
    data = json.loads((SCRATCH / "solve" / case / "results.json").read_text(encoding="utf-8"))
    return data["results"][name]["metrics"]


def main() -> None:
    case = sys.argv[1]
    baseline = sys.argv[2] if len(sys.argv) > 2 else "design7"
    new = metrics_of(case, "cudss")
    ref = metrics_of(baseline, "aster_clamped")
    rows = []

    def row(label: str, a: float, b: float, unit: str) -> None:
        rows.append((label, a, b, 100.0 * (a - b) / b, unit))

    for seat in SEATS:
        row(f"tilt {seat}", new["per_seat"][seat]["tilt_arcmin"], ref["per_seat"][seat]["tilt_arcmin"], "′")
    for mesh in ref["gear_mesh"]:
        row(f"lead {mesh}", abs(new["gear_mesh"][mesh]["lead_mrad"]), abs(ref["gear_mesh"][mesh]["lead_mrad"]), "mrad")
    row("p99.9 von Mises", new["vm_p999_mpa"], ref["vm_p999_mpa"], "MPa")
    row("p99 von Mises", new["vm_p99_mpa"], ref["vm_p99_mpa"], "MPa")
    row("largest displacement", new["umax_mm"], ref["umax_mm"], "mm")
    print(f"{case} (cuDSS) against {baseline} (Code_Aster):")
    for label, a, b, d, unit in rows:
        print(f"  {label:<28} {a:10.4f} {b:10.4f} {unit:<4} {d:+7.2f} %")
    out = {
        "case": case,
        "baseline": baseline,
        "rows": [{"what": r[0], "route": r[1], "baseline": r[2], "diff_pct": r[3]} for r in rows],
    }
    (SCRATCH / "solve" / case / "against_baseline.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
