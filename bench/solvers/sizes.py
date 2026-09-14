"""An element size for every point of a design, from its distance field alone - the rules agreed for
meshing, as an edge length h:

- through a rib or thin wall (thinner than RIB_MAX): at least THROUGH elements, h <= thickness / THROUGH;
- round a concave curve - a fillet or a hole of radius R: h <= 2 pi R / AROUND, so a hole has at least
  AROUND elements round it and a fillet's elements stay under half its radius;
- elsewhere, on panels and in thick metal: h <= PANEL; no rule asks for less than SMALLEST;
- a size grows by at most GROWTH mm for every mm away from where a rule sets it.

The part's thickness at a surface point is measured along the inward normal to where the field crosses
zero again - the stored field holds distances only in a band round the surface; the radius of a
concave curve from the field's second differences. Sizes are kept on a grid STRIDE times coarser than
the field's; ``mesh_cgal.py --sizes`` holds CGAL's cells and facets to them.

``--only-changed MM`` applies the rules only within MM of the samples the design changed - its ribs,
pads, fillets and holes - and leaves the part's own surface at PANEL. The numbers can be overridden;
``--around 0`` sets no size round curves.

    python sizes.py <case dir> [--only-changed MM] [--through N] [--around N] [--rib-max MM]
        [--panel MM] [--smallest MM] [--growth G]     # writes sizes.npz and sizes.json
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from mesh_cgal import load_sdf
from scipy import ndimage

THROUGH = 2  # elements through a rib's thickness
AROUND = 16  # elements round a hole
RIB_MAX = 25.0  # mm: thinner metal is a rib or thin wall
PANEL = 20.0  # mm: the largest element
SMALLEST = 2.0  # mm: the smallest element any rule asks for
GROWTH = 0.4  # mm of size per mm of distance
STRIDE = 2  # the size grid takes every STRIDE-th point of the field's grid
REACH = 60.0  # mm: thickness is measured up to this; thicker metal is a panel


def sample(sdf: np.ndarray, origin: np.ndarray, spacing: float, p: np.ndarray) -> np.ndarray:
    """The field at points, by trilinear interpolation; clamped to the grid."""
    u = (p - origin) / spacing
    i = np.clip(np.floor(u).astype(np.int64), 0, np.array(sdf.shape) - 2)
    t = np.clip(u - i, 0.0, 1.0)
    out = np.zeros(len(p))
    for di in (0, 1):
        for dj in (0, 1):
            for dk in (0, 1):
                w = (t[:, 0] if di else 1 - t[:, 0]) * (t[:, 1] if dj else 1 - t[:, 1])
                w = w * (t[:, 2] if dk else 1 - t[:, 2])
                out += w * sdf[i[:, 0] + di, i[:, 1] + dj, i[:, 2] + dk]
    return out


def near_surface(sdf: np.ndarray, spacing: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Size-grid nodes within one size-grid spacing of the surface - their field-grid index, the field,
    its unit gradient and the mean curvature of its level set there, from central differences."""
    coarse = sdf[::STRIDE, ::STRIDE, ::STRIDE]
    idx = np.argwhere(np.abs(coarse) <= STRIDE * spacing) * STRIDE
    idx = idx[np.all((idx >= 1) & (idx <= np.array(sdf.shape) - 2), axis=1)]
    i, j, k = idx.T

    def f(di: int, dj: int, dk: int) -> np.ndarray:
        return sdf[i + di, j + dj, k + dk].astype(np.float64)

    c = f(0, 0, 0)
    g = np.stack([f(1, 0, 0) - f(-1, 0, 0), f(0, 1, 0) - f(0, -1, 0), f(0, 0, 1) - f(0, 0, -1)], 1) / (2 * spacing)
    hxx = (f(1, 0, 0) - 2 * c + f(-1, 0, 0)) / spacing**2
    hyy = (f(0, 1, 0) - 2 * c + f(0, -1, 0)) / spacing**2
    hzz = (f(0, 0, 1) - 2 * c + f(0, 0, -1)) / spacing**2
    hxy = (f(1, 1, 0) - f(1, -1, 0) - f(-1, 1, 0) + f(-1, -1, 0)) / (4 * spacing**2)
    hxz = (f(1, 0, 1) - f(1, 0, -1) - f(-1, 0, 1) + f(-1, 0, -1)) / (4 * spacing**2)
    hyz = (f(0, 1, 1) - f(0, 1, -1) - f(0, -1, 1) + f(0, -1, -1)) / (4 * spacing**2)
    norm = np.maximum(np.linalg.norm(g, axis=1), 1e-9)
    n = g / norm[:, None]
    nhn = (
        n[:, 0] ** 2 * hxx + n[:, 1] ** 2 * hyy + n[:, 2] ** 2 * hzz
        + 2 * (n[:, 0] * n[:, 1] * hxy + n[:, 0] * n[:, 2] * hxz + n[:, 1] * n[:, 2] * hyz)
    )
    mean = (hxx + hyy + hzz - nhn) / norm
    return idx, c, n, mean


def thickness(sdf, origin, spacing, surface: np.ndarray, normal: np.ndarray, step: float) -> np.ndarray:
    """Metal along the inward normal from each surface point, to where the field turns positive again;
    REACH where it does not within REACH, or where the normal does not enter the metal."""
    t = np.full(len(surface), REACH)
    open_ = np.ones(len(surface), bool)
    entered = np.zeros(len(surface), bool)
    before = np.zeros(len(surface))
    for s in np.arange(step, REACH + step / 2, step):
        v = before.copy()
        v[open_] = sample(sdf, origin, spacing, surface[open_] - s * normal[open_])
        out = open_ & entered & (v >= 0)
        t[out] = s - step * v[out] / np.maximum(v[out] - before[out], 1e-9)
        open_ &= ~out
        entered |= v < 0
        before = v
    return t


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("--only-changed", type=float, help="rules only within this of the changed samples, mm")
    parser.add_argument("--through", type=float, default=THROUGH)
    parser.add_argument("--around", type=float, default=AROUND)
    parser.add_argument("--rib-max", type=float, default=RIB_MAX)
    parser.add_argument("--panel", type=float, default=PANEL)
    parser.add_argument("--smallest", type=float, default=SMALLEST)
    parser.add_argument("--growth", type=float, default=GROWTH)
    args = parser.parse_args()
    here, panel, smallest = args.case, args.panel, args.smallest

    t0 = time.time()
    sdf, origin, spacing, _ = load_sdf(here, np.float32)
    idx, value, normal, mean = near_surface(sdf, spacing)
    at = origin + idx * spacing
    surface = at - value[:, None] * normal
    thick = thickness(sdf, origin, spacing, surface, normal, spacing / 2)
    # A concave level set of radius r at signed distance c lies on a surface of radius r + c.
    radius = np.where(mean < -1e-4, 1.0 / np.maximum(-mean, 1e-9) + value, np.inf)
    radius = np.maximum(radius, 0.5)
    by_thickness = np.where(thick <= args.rib_max, thick / args.through, np.inf)
    by_curve = radius * 2 * np.pi / args.around if args.around > 0 else np.full(len(idx), np.inf)
    if args.only_changed is not None:
        from scipy.spatial import cKDTree

        changed = np.load(here / "field.npz")["changed"]
        where = origin + np.column_stack(np.unravel_index(changed, sdf.shape)) * spacing
        far, _ = cKDTree(where).query(surface, distance_upper_bound=args.only_changed)
        by_thickness[~np.isfinite(far)] = np.inf
        by_curve[~np.isfinite(far)] = np.inf
    target = np.clip(np.minimum(np.minimum(by_thickness, by_curve), panel), smallest, panel)
    rule = np.select(
        [target <= smallest, by_thickness <= np.minimum(by_curve, panel), by_curve < panel],
        ["smallest", "thickness", "curve"],
        "panel",
    )

    size = np.full(tuple(-(-np.array(sdf.shape) // STRIDE)), panel, np.float32)
    cells = idx // STRIDE
    np.minimum.at(size, tuple(cells.T), target.astype(np.float32))
    offsets = np.indices((3, 3, 3)).reshape(3, -1).T - 1
    rise = (args.growth * STRIDE * spacing * np.linalg.norm(offsets, axis=1)).reshape(3, 3, 3)
    for _ in range(int(np.ceil((panel - smallest) / (args.growth * STRIDE * spacing)))):
        size = ndimage.grey_erosion(size, structure=-rise)
    np.savez_compressed(
        here / "sizes.npz",
        size=size,
        origin=origin,
        spacing=STRIDE * spacing,
        surface=surface,
        thickness=thick,
        radius=radius,
        target=target,
        rule=rule,
    )
    info = {
        "rules": {"through": args.through, "around": args.around, "rib_max_mm": args.rib_max, "panel_mm": panel,
                  "smallest_mm": smallest, "growth": args.growth, "only_changed_mm": args.only_changed},
        "size_grid": {"shape": list(size.shape), "spacing_mm": STRIDE * spacing},
        "surface_nodes": int(len(idx)),
        "set_by": {name: int((rule == name).sum()) for name in ("thickness", "curve", "smallest", "panel")},
        "target_mm": {q: float(np.percentile(target, p)) for q, p in (("p1", 1), ("p10", 10), ("median", 50))},
        "seconds": time.time() - t0,
    }
    (here / "sizes.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
