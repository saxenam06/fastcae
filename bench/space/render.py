"""Pictures of a derived design space: 3D views of its regions and sections through it.

    python render.py GRC_Gearbox_Housing <out dir>

Reads ``space_4mm*.npz`` / ``.json``, the rib check and the benefit maps from the out dir; writes PNGs
into ``<out dir>/img``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import vtk
from matplotlib.colors import ListedColormap, LogNorm
from vtk.util import numpy_support

from fastcae import extract
from fastcae.project import open_project
from fastcae.space.grid import distance_to
from fastcae.space.model import Label

WHITE = (1.0, 1.0, 1.0)
PART = (0.80, 0.82, 0.85)
ALLOWED = (0.16, 0.45, 0.95)
UNKNOWN = (0.98, 0.80, 0.10)
RIB = (0.05, 0.62, 0.25)
CORRIDOR = (0.85, 0.25, 0.25)
MATING = (0.90, 0.45, 0.70)
ACCESS = (0.97, 0.60, 0.20)
CAVITY = (0.93, 0.87, 0.68)

EVIDENCE_COLOUR = {
    "deck_load": (0.85, 0.15, 0.15),
    "deck_support": (0.15, 0.35, 0.85),
    "deck_hole_plane": (0.10, 0.60, 0.65),
    "drawing": (0.55, 0.25, 0.75),
    "question": (0.98, 0.80, 0.10),
}


def load_space(path: Path) -> dict:
    d = np.load(path)
    return {k: d[k] for k in d.files}


def image_of(mask: np.ndarray, origin, h: float) -> vtk.vtkImageData:
    img = vtk.vtkImageData()
    img.SetDimensions(*mask.shape)
    img.SetSpacing(h, h, h)
    img.SetOrigin(*origin)
    arr = numpy_support.numpy_to_vtk(
        mask.astype(np.uint8).ravel(order="F"), deep=True, array_type=vtk.VTK_UNSIGNED_CHAR
    )
    img.GetPointData().SetScalars(arr)
    return img


def iso(mask: np.ndarray, origin, h: float, smooth: bool = True) -> vtk.vtkPolyData:
    fe = vtk.vtkFlyingEdges3D()
    fe.SetInputData(image_of(mask, origin, h))
    fe.SetValue(0, 0.5)
    fe.ComputeNormalsOn()
    fe.Update()
    out = fe.GetOutput()
    if smooth and out.GetNumberOfPoints():
        s = vtk.vtkWindowedSincPolyDataFilter()
        s.SetInputData(out)
        s.SetNumberOfIterations(12)
        s.SetPassBand(0.1)
        s.NormalizeCoordinatesOn()
        s.Update()
        n = vtk.vtkPolyDataNormals()
        n.SetInputData(s.GetOutput())
        n.Update()
        out = n.GetOutput()
    return out


def mesh_of(tess, colours: np.ndarray | None = None) -> vtk.vtkPolyData:
    pts = vtk.vtkPoints()
    pts.SetData(numpy_support.numpy_to_vtk(tess.vertices.astype(np.float64), deep=True))
    cells = vtk.vtkCellArray()
    tri = np.hstack([np.full((len(tess.triangles), 1), 3), tess.triangles]).astype(np.int64).ravel()
    cells.SetCells(len(tess.triangles), numpy_support.numpy_to_vtkIdTypeArray(tri, deep=True))
    poly = vtk.vtkPolyData()
    poly.SetPoints(pts)
    poly.SetPolys(cells)
    if colours is not None:
        c = numpy_support.numpy_to_vtk((colours * 255).astype(np.uint8), deep=True, array_type=vtk.VTK_UNSIGNED_CHAR)
        c.SetName("colours")
        poly.GetCellData().SetScalars(c)
    n = vtk.vtkPolyDataNormals()
    n.SetInputData(poly)
    n.SplittingOff()
    n.Update()
    return n.GetOutput()


def clip(poly: vtk.vtkPolyData, origin, normal) -> vtk.vtkPolyData:
    plane = vtk.vtkPlane()
    plane.SetOrigin(*origin)
    plane.SetNormal(*normal)
    c = vtk.vtkClipPolyData()
    c.SetInputData(poly)
    c.SetClipFunction(plane)
    c.Update()
    return c.GetOutput()


def actor(poly, colour=None, opacity=1.0, scalars: str | None = None, lut=None, rng=None) -> vtk.vtkActor:
    m = vtk.vtkPolyDataMapper()
    m.SetInputData(poly)
    if scalars == "cells":
        m.SetScalarModeToUseCellData()
        m.SetColorModeToDirectScalars()
        m.ScalarVisibilityOn()
    elif scalars == "points" and lut is not None:
        m.SetLookupTable(lut)
        m.SetScalarRange(*rng)
        m.SetScalarModeToUsePointData()
        m.ScalarVisibilityOn()
    else:
        m.ScalarVisibilityOff()
    a = vtk.vtkActor()
    a.SetMapper(m)
    if colour is not None:
        a.GetProperty().SetColor(*colour)
    a.GetProperty().SetOpacity(opacity)
    a.GetProperty().SetSpecular(0.15)
    a.GetProperty().SetAmbient(0.25)
    a.GetProperty().SetDiffuse(0.85)
    return a


def shoot(actors: list, path: Path, centre, direction, distance: float, up=(0, 0, 1), size=(1300, 950)) -> None:
    ren = vtk.vtkRenderer()
    ren.SetBackground(*WHITE)
    ren.SetUseDepthPeeling(True)
    ren.SetMaximumNumberOfPeels(8)
    for a in actors:
        ren.AddActor(a)
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetAlphaBitPlanes(1)
    win.SetMultiSamples(0)
    win.SetSize(*size)
    win.AddRenderer(ren)
    cam = ren.GetActiveCamera()
    d = np.asarray(direction, float)
    d /= np.linalg.norm(d)
    cam.SetFocalPoint(*centre)
    cam.SetPosition(*(np.asarray(centre) + d * distance))
    cam.SetViewUp(*up)
    cam.SetViewAngle(30)
    ren.ResetCameraClippingRange()
    kit = vtk.vtkLightKit()
    kit.SetKeyLightIntensity(1.0)
    kit.AddLightsToRenderer(ren)
    win.Render()
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(win)
    grab.SetInputBufferTypeToRGB()
    grab.Update()
    w = vtk.vtkPNGWriter()
    w.SetFileName(str(path))
    w.SetInputData(grab.GetOutput())
    w.Write()
    win.Finalize()


def heat_lut() -> vtk.vtkLookupTable:
    lut = vtk.vtkLookupTable()
    lut.SetNumberOfTableValues(256)
    cmap = plt.get_cmap("YlOrRd")
    for i in range(256):
        r, g, b, _ = cmap(0.15 + 0.85 * i / 255)
        lut.SetTableValue(i, r, g, b, 1.0)
    lut.SetScaleToLog10()
    lut.Build()
    return lut


def probe(poly: vtk.vtkPolyData, values: np.ndarray, origin, h: float) -> vtk.vtkPolyData:
    """Each vertex takes the value of the nearest cell - the benefit of the allowed cell it bounds."""
    pts = numpy_support.vtk_to_numpy(poly.GetPoints().GetData())
    ijk = np.clip(np.rint((pts - np.asarray(origin)) / h).astype(int), 0, np.asarray(values.shape) - 1)
    v = values[ijk[:, 0], ijk[:, 1], ijk[:, 2]].astype(np.float32)
    # A vertex on the boundary may round into a forbidden cell (value 0): take the largest neighbour.
    for off in np.array(np.meshgrid([-1, 0, 1], [-1, 0, 1], [-1, 0, 1], indexing="ij")).reshape(3, -1).T:
        n = np.clip(ijk + off, 0, np.asarray(values.shape) - 1)
        v = np.maximum(v, values[n[:, 0], n[:, 1], n[:, 2]])
    arr = numpy_support.numpy_to_vtk(v, deep=True)
    arr.SetName("benefit")
    poly.GetPointData().SetScalars(arr)
    return poly


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    img = args.out / "img"
    img.mkdir(exist_ok=True)

    project = open_project(args.project)
    ex = extract.run(project)
    tess = ex.tess
    outside = load_space(args.out / "space_4mm.npz")
    inside = load_space(args.out / "space_4mm_inside.npz")
    summary = json.loads((args.out / "space_4mm.json").read_text(encoding="utf-8"))
    ribs = np.load(args.out / "space_4mm_ribs.npz")["pieces"] > 0
    origin = tuple(float(v) for v in outside["origin"])
    h = float(outside["spacing"])
    labels = outside["labels"]
    lab_in = inside["labels"]
    centre = tess.vertices.mean(axis=0)
    centre[2] = 0.5 * (tess.vertices[:, 2].min() + tess.vertices[:, 2].max())
    far = 3.2 * float(np.linalg.norm(tess.vertices.max(axis=0) - tess.vertices.min(axis=0))) * 0.5

    views = {
        "front": (0.55, -0.75, -0.9),
        "rear": (-0.55, 0.75, 0.9),
        "side": (1.0, -0.35, 0.25),
    }

    # Interfaces on the part, coloured by what froze them.
    colours = np.tile(np.array(PART), (len(tess.triangles), 1))
    for i in summary["interfaces"]:
        kinds = {e["kind"] for e in i["evidence"]}
        key = (
            "question"
            if i["status"] == "question"
            else next((k for k in ("deck_load", "deck_support", "drawing", "deck_hole_plane") if k in kinds), None)
        )
        if key:
            colours[np.isin(tess.face_id, i["faces"])] = EVIDENCE_COLOUR[key]
    part_col = mesh_of(tess, colours)
    part_plain = mesh_of(tess)
    for name in ("front", "rear"):
        shoot([actor(part_col, scalars="cells")], img / f"interfaces_{name}.png", centre, views[name], far)
    print("interfaces done", flush=True)

    # Allowed and unknown, outside only.
    allowed = iso(labels == Label.ADMISSIBLE, origin, h)
    unknown = iso(labels == Label.UNKNOWN, origin, h)
    for name in ("front", "rear", "side"):
        shoot(
            [actor(part_plain, PART), actor(allowed, ALLOWED, 0.55), actor(unknown, UNKNOWN, 0.45)],
            img / f"allowed_{name}.png",
            centre,
            views[name],
            far,
        )
    print("allowed done", flush=True)

    # Keep-outs, near the part.
    d_part = distance_to(labels == Label.PART, h)
    near = d_part <= 120.0
    keep = [
        (labels == Label.BORE_CORRIDOR) & near,
        (labels == Label.PLANE_NEIGHBOUR) & near,
        (labels == Label.HOLE_ACCESS) & near,
    ]
    keep_polys = [iso(m, origin, h) for m in keep]
    for name in ("front", "rear"):
        shoot(
            [
                actor(part_plain, PART),
                actor(keep_polys[0], CORRIDOR, 0.5),
                actor(keep_polys[1], MATING, 0.4),
                actor(keep_polys[2], ACCESS, 0.6),
            ],
            img / f"keepouts_{name}.png",
            centre,
            views[name],
            far,
        )
    print("keep-outs done", flush=True)

    # Inside allowed, with the production ribs: cut away the half facing the camera.
    rib_poly = iso(ribs, origin, h, smooth=False)
    allowed_in = iso((lab_in == Label.ADMISSIBLE) & (labels != Label.ADMISSIBLE), origin, h)
    for name, normal, view in (("front", (0, 0, 1), (0.25, -0.35, -1.0)), ("rear", (0, 0, -1), (-0.25, 0.35, 1.0))):
        cut_at = (0, 0, 160.0) if name == "front" else (0, 0, 560.0)
        shoot(
            [
                actor(clip(part_plain, cut_at, normal), PART),
                actor(clip(allowed_in, cut_at, normal), ALLOWED, 0.35),
                actor(clip(rib_poly, cut_at, normal), RIB, 1.0),
            ],
            img / f"inside_{name}.png",
            centre,
            view,
            far,
        )
    print("inside done", flush=True)

    # Benefit on the allowed space, outside and inside.
    for tag, lab, bpath in (
        ("outside", labels, "space_4mm_benefit.npz"),
        ("inside", lab_in, "space_4mm_inside_benefit.npz"),
    ):
        path = args.out / bpath
        if not path.exists():
            continue
        benefit = np.load(path)["benefit"]
        adm = lab == Label.ADMISSIBLE
        vals = benefit[adm]
        lo, hi = float(np.percentile(vals[vals > 0], 5)), float(np.percentile(vals, 99.5))
        poly = probe(iso(adm, origin, h), np.where(adm, benefit, 0.0), origin, h)
        lut = heat_lut()
        if tag == "outside":
            for name in ("front", "rear", "side"):
                shoot(
                    [actor(part_plain, PART), actor(poly, scalars="points", lut=lut, rng=(lo, hi))],
                    img / f"benefit_{tag}_{name}.png",
                    centre,
                    views[name],
                    far,
                )
        else:
            for name, normal, view in (
                ("front", (0, 0, 1), (0.25, -0.35, -1.0)),
                ("rear", (0, 0, -1), (-0.25, 0.35, 1.0)),
            ):
                cut_at = (0, 0, 160.0) if name == "front" else (0, 0, 560.0)
                shoot(
                    [
                        actor(clip(part_plain, cut_at, normal), PART),
                        actor(clip(poly, cut_at, normal), scalars="points", lut=lut, rng=(lo, hi)),
                        actor(clip(rib_poly, cut_at, normal), RIB, 0.9),
                    ],
                    img / f"benefit_{tag}_{name}.png",
                    centre,
                    view,
                    far,
                )
    print("benefit done", flush=True)

    # Sections.
    colors = [
        "#ffffff",
        "#9aa3ad",
        "#f3e6c2",
        "#e59a9a",
        "#eeb4d4",
        "#dcc3f2",
        "#f7c48f",
        "#c9ccd1",
        "#ffe45c",
        "#6ea3ff",
    ]
    names = [
        "open air",
        "part",
        "cavity",
        "bore corridor",
        "mating space",
        "ring",
        "hole access",
        "buffer",
        "needs an answer",
        "allowed",
    ]
    cmap = ListedColormap(colors)
    benefit_in = (
        np.load(args.out / "space_4mm_inside_benefit.npz")["benefit"]
        if (args.out / "space_4mm_inside_benefit.npz").exists()
        else None
    )
    for tag, axis, value in (("z82", 2, 82.0), ("z607", 2, 607.0), ("z140", 2, 140.0), ("x0", 0, 0.0)):
        k = int(round((value - origin[axis]) / h))
        fig, axes = plt.subplots(1, 2, figsize=(16, 8.2))
        for ax, lab, title in ((axes[0], labels, "outside only"), (axes[1], lab_in, "inner walls too")):
            sl = np.take(lab, k, axis=axis)
            rb = np.take(ribs, k, axis=axis)
            other = [a for a in range(3) if a != axis]
            ext = [
                origin[other[1]],
                origin[other[1]] + sl.shape[1] * h,
                origin[other[0]] + sl.shape[0] * h,
                origin[other[0]],
            ]
            ax.imshow(sl, cmap=cmap, vmin=0, vmax=9, extent=ext, interpolation="nearest")
            if rb.any():
                ax.contour(
                    np.linspace(ext[0], ext[1], sl.shape[1]),
                    np.linspace(ext[3], ext[2], sl.shape[0]),
                    rb,
                    levels=[0.5],
                    colors="#07852b",
                    linewidths=1.6,
                )
            ax.set_title(title)
            ax.set_xlabel(f"{'xyz'[other[1]]} mm")
            ax.set_ylabel(f"{'xyz'[other[0]]} mm")
            part_rows = np.flatnonzero((sl == Label.PART).any(axis=1))
            part_cols = np.flatnonzero((sl == Label.PART).any(axis=0))
            if len(part_rows):
                pad = 30
                ax.set_ylim(origin[other[0]] + (part_rows[-1] + pad) * h, origin[other[0]] + (part_rows[0] - pad) * h)
                ax.set_xlim(origin[other[1]] + (part_cols[0] - pad) * h, origin[other[1]] + (part_cols[-1] + pad) * h)
        handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colors[1:]]
        fig.legend(handles, names[1:], loc="lower center", ncol=9, fontsize=9, frameon=False)
        fig.suptitle(
            f"Section {'xyz'[axis]} = {value:g} mm - green outline: the production housing's ribs", fontsize=11
        )
        fig.tight_layout(rect=(0, 0.05, 1, 0.97))
        fig.savefig(img / f"section_{tag}.png", dpi=85)
        plt.close(fig)
        if benefit_in is not None:
            fig, ax = plt.subplots(figsize=(8.5, 8.2))
            sl = np.take(lab_in, k, axis=axis)
            b = np.take(benefit_in, k, axis=axis)
            other = [a for a in range(3) if a != axis]
            ext = [
                origin[other[1]],
                origin[other[1]] + sl.shape[1] * h,
                origin[other[0]] + sl.shape[0] * h,
                origin[other[0]],
            ]
            ax.imshow(
                np.where(sl == Label.PART, 1, 0),
                cmap=ListedColormap(["#ffffff", "#b9bfc7"]),
                extent=ext,
                interpolation="nearest",
            )
            pos = b[b > 0]
            if len(pos):
                ax.imshow(
                    np.ma.masked_where(b <= 0, b),
                    cmap="YlOrRd",
                    norm=LogNorm(vmin=np.percentile(pos, 5), vmax=np.percentile(pos, 99.5)),
                    extent=ext,
                    interpolation="nearest",
                )
            rb = np.take(ribs, k, axis=axis)
            if rb.any():
                ax.contour(
                    np.linspace(ext[0], ext[1], sl.shape[1]),
                    np.linspace(ext[3], ext[2], sl.shape[0]),
                    rb,
                    levels=[0.5],
                    colors="#07852b",
                    linewidths=1.6,
                )
            part_rows = np.flatnonzero((sl == Label.PART).any(axis=1))
            part_cols = np.flatnonzero((sl == Label.PART).any(axis=0))
            if len(part_rows):
                pad = 30
                ax.set_ylim(origin[other[0]] + (part_rows[-1] + pad) * h, origin[other[0]] + (part_rows[0] - pad) * h)
                ax.set_xlim(origin[other[1]] + (part_cols[0] - pad) * h, origin[other[1]] + (part_cols[-1] + pad) * h)
            ax.set_title(
                f"Benefit of metal, {'xyz'[axis]} = {value:g} mm (inner walls too); green: production ribs", fontsize=10
            )
            fig.tight_layout()
            fig.savefig(img / f"benefit_section_{tag}.png", dpi=85)
            plt.close(fig)
    print("sections done", flush=True)


if __name__ == "__main__":
    main()
