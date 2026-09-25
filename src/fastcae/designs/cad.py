"""A design's own CAD: its ribs, already built as solids, fused into the part by OpenCascade.

A design is only worth solving, and only worth learning from, as exact geometry: crisp edges, round
holes, the part's bores as they were drawn. So each rib is a solid (:class:`Body`) fused into the
part's B-rep where it stands, and the design is written as STEP to open anywhere and as BREP for
the steps after this one. Nothing is voxelised or blended, and no fillet follows the fuse. The
records still call each fused solid a plate, as the screens and older campaigns do.

**A plate the fuse cannot take is dropped, not approximated.** It is reported as "CAD failed" with
the reason, and the design goes on without it. A mesh-only stand-in would be a design whose CAD
does not exist, and every step after this one would then describe geometry nobody can open.

**The part is left as it was.** One part is fused many times over, once per design, so the boolean
runs non-destructively: by default OCC may raise tolerances on its arguments in place, and the next
design would inherit them. The clean-up after the fuse, which merges coplanar pieces, is kept to
the faces the fuse made. Run over the whole part in ``assets/`` it also merges a pair of the part's
own faces, and a design whose faces differ from the part's away from its plates meshes differently
there for no reason. A face the fuse did not touch is the same OCC face in the result.

**Why a failure says little.** OCP's binding of ``BRepAlgoAPI_Fuse`` leaves out its
``BOPAlgo_Options`` base, so OCC's own account of a failure (``HasErrors``, ``GetReport``) cannot be
read. A failed plate's reason is what the checks here saw: the boolean not completing, a result
that fails ``BRepCheck``, or a result that is more than one solid.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypedDict

import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_Copy,
)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepTools import BRepTools
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.ShapeFix import ShapeFix_Face, ShapeFix_Shape
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS_Shape
from OCP.TopTools import (
    TopTools_FormatVersion,
    TopTools_IndexedMapOfShape,
    TopTools_ListOfShape,
    TopTools_MapOfShape,
)

from ..geometry import brep

# A fused design holding less of the part's volume than this share short of it has lost the part.
LOST_SHARE = 0.01


@dataclass(frozen=True, eq=False)
class Body:
    """A rib built as a solid: one body swept along its curve (:mod:`.sweep`), never a chain of
    flat plates - built as a chain it leaves a sliver face at every lap."""

    name: str
    shape: TopoDS_Shape
    outline: np.ndarray | None = None
    """The rib's own mid-surface as a closed ring, (n, 3) mm - its bottom edge out and its top
    edge back. This is what is drawn, so that what is shown is what is built: drawing a flat proxy
    beside a swept body shows a shape that does not exist."""
    normal: np.ndarray | None = None
    thickness_mm: float = 0.0


class PlateStatus(TypedDict):
    """What became of one plate. A ``failed`` plate is shown as "CAD failed", with its reason."""

    name: str
    status: Literal["fused", "failed"]
    reason: str


@dataclass
class Fused:
    """A part with plates fused into it, and what became of each plate.

    ``shape`` is one solid, or the part as it came when no plate fused. ``plates`` has one entry
    per plate asked for, in the order asked; the reason is empty for a plate that fused.

    Volumes are GProp's default integration, which on the part in ``assets/`` is 0.06% off the
    adaptive one. The error sits in faces the plates leave alone, so it cancels in the difference:
    the volume added agrees with the plates' own volume outside the part to 0.2%. Adaptive
    integration closes that to 6 mm3, and takes more than ten times as long.
    """

    shape: TopoDS_Shape
    plates: list[PlateStatus]
    volume_before_mm3: float
    volume_after_mm3: float
    solids: int
    faces: int
    seconds: float

    @property
    def failed(self) -> list[str]:
        """Names of the plates the fuse could not take."""
        return [p["name"] for p in self.plates if p["status"] == "failed"]


def fuse(base: TopoDS_Shape, plates: Sequence[Body]) -> Fused:
    """Fuse the plates into ``base`` one at a time, in the order given, each that fails dropped
    with its reason, so a bad plate costs only itself. A plate that stood apart is tried again once
    others have joined: it may stand on one of them.

    One boolean taking every plate at once is no faster where it matters: with plates crossing one
    another on the housing it ran nearly three minutes and handed back no solid at all, where the
    plates one at a time took a minute and a half.
    """
    started = time.perf_counter()
    status: list[PlateStatus] = []
    solids: list[tuple[int, TopoDS_Shape]] = []
    for i, plate in enumerate(plates):
        status.append({"name": plate.name, "status": "fused", "reason": ""})
        try:
            solids.append((i, plate.shape))
        except Exception as exc:  # OCC's own failures arrive as Python exceptions too
            status[i] = _failed(plate.name, f"no solid: {exc}")

    shape = base
    whole = _volume(base)
    # A part that is not one valid solid fails every result, and blaming the plates for it would
    # send someone to fix the wrong thing.
    flaw = _flaw(base)
    # Plates kept apart by the sand between them go in one boolean: the part is touched once, with
    # its own tolerances, where plate after plate stacks each fuse's loose tolerances and repairs
    # on the last - on the housing, 16 ribs that each fuse alone left 4 failing in turn, and went
    # in whole at once in 4 s. Plate by plate is the fallback.
    if not flaw and len(solids) > 1:
        made, _ = _fuse_checked(base, [s for _, s in solids], whole)
        if made is not None:
            return Fused(
                shape=made,
                plates=status,
                volume_before_mm3=whole,
                volume_after_mm3=_volume(made),
                solids=len(_solids(made)),
                faces=len(brep.faces_of(made)),
                seconds=time.perf_counter() - started,
            )
    waiting = solids
    # A plate standing on another joins only once that one has: again, while any joins.
    while waiting:
        apart = []
        for i, solid in waiting:
            if flaw:
                status[i] = _failed(plates[i].name, f"the part itself {flaw}")
                continue
            made, why = _fuse_checked(shape, [solid], whole)
            if made is None:
                status[i] = _failed(plates[i].name, why)
                if "separate solids" in why:
                    apart.append((i, solid))
            else:
                status[i] = {"name": plates[i].name, "status": "fused", "reason": ""}
                shape = made
        waiting = apart if len(apart) < len(waiting) else []

    return Fused(
        shape=shape,
        plates=status,
        volume_before_mm3=whole,
        volume_after_mm3=_volume(shape),
        solids=len(_solids(shape)),
        faces=len(brep.faces_of(shape)),
        seconds=time.perf_counter() - started,
    )


def write(shape: TopoDS_Shape, step_path: Path, brep_path: Path) -> None:
    """Write the shape as STEP, in millimetres, and as OCC's own BREP.

    The BREP reads back exactly. The STEP reads back as one valid solid with the same faces, but
    not bit for bit: on the part in ``assets/`` three tori come back as surfaces of revolution and
    the volume moves by 0.005%, with plates or without - the part's own translation, not the fuse.

    The BREP is written without triangulation. Tessellating a shape for display stores triangles
    on it, and they would otherwise go into the file and swell it with what any reader rebuilds.
    """
    step_path, brep_path = Path(step_path), Path(brep_path)
    for path in (step_path, brep_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    # The unit the shape is in, and the unit the file is written in: both stated, as on reading.
    # Set after the writer exists, since making it is what registers the STEP parameters, and
    # read by the transfer.
    writer = STEPControl_Writer()
    Interface_Static.SetCVal_s("xstep.cascade.unit", brep.INTERNAL_UNIT)
    Interface_Static.SetCVal_s("write.step.unit", brep.INTERNAL_UNIT)
    if writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone:
        raise OSError(f"STEP transfer failed: {step_path}")
    if writer.Write(str(step_path)) != IFSelect_RetDone:
        raise OSError(f"STEP write failed: {step_path}")

    version = TopTools_FormatVersion.TopTools_FormatVersion_CURRENT
    if not BRepTools.Write_s(shape, str(brep_path), False, False, version):
        raise OSError(f"BREP write failed: {brep_path}")


def load(path: Path) -> TopoDS_Shape:
    """Read a design's CAD, or the part's, from ``.step``/``.stp`` or ``.brep``.

    The solids only; :func:`fastcae.geometry.brep.load_cad` also says what else a file held.
    """
    shape, _ = brep.load_cad(Path(path))
    return shape


def tessellate(shape: TopoDS_Shape) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The shape as triangles for display: vertices (n, 3) mm, triangles (m, 3), and the CAD face
    each triangle came from (m,). :func:`fastcae.geometry.brep.tessellate`, as three arrays."""
    tess = brep.tessellate(shape)
    return tess.vertices, tess.triangles, tess.face_id


def _fuse_checked(
    base: TopoDS_Shape, tools: list[TopoDS_Shape], whole: float
) -> tuple[TopoDS_Shape | None, str]:
    """One boolean, its coplanar pieces merged, the result checked against ``whole``, the part's
    own volume: the shape and ``""``, or ``None`` and what went wrong."""
    try:
        op = BRepAlgoAPI_Fuse()
        op.SetArguments(_listed([base]))
        op.SetTools(_listed(tools))
        op.SetRunParallel(True)
        op.SetNonDestructive(True)
        op.Build()
        if not op.IsDone() or op.Shape().IsNull():
            return None, "the boolean did not complete"
        shape = _unify(op.Shape(), base)
    except Exception as exc:  # OCC's own failures arrive as Python exceptions
        return None, f"OCC raised {type(exc).__name__}: {exc}"

    flaw = _flaw(shape)
    if flaw == "fails BRepCheck":
        # Most often the boolean's own loose tolerances where a plate crosses curved faces:
        # ShapeFix mends them, and the plate is kept rather than dropped - first only the faces
        # BRepCheck flags, since mending the whole shape rewrites faces far from any plate, and the
        # face-by-face mesher then breaks there; the whole shape only when that is not enough.
        # On a copy: ShapeFix sets tolerances in place, and the result shares the faces the fuse
        # left alone with the part - mending it in place would change the part for every design
        # fused after it.
        copy = BRepBuilderAPI_Copy(shape).Shape()
        shape = _mend_flagged(copy)
        flaw = _flaw(shape)
        if flaw == "fails BRepCheck":
            fix = ShapeFix_Shape(copy)
            fix.Perform()
            shape = fix.Shape()
            flaw = _flaw(shape)
    if flaw:
        return None, f"the result {flaw}"
    # The boolean hands back a compound; the one solid inside it is the design - and it must hold
    # the part: a boolean that lost its argument can still hand back one valid solid.
    solid = _solids(shape)[0]
    if _volume(solid) < (1.0 - LOST_SHARE) * whole:
        return None, "the result lost the part"
    return solid, ""


def _mend_flagged(shape: TopoDS_Shape) -> TopoDS_Shape:
    """``shape`` with only the faces BRepCheck flags mended by ShapeFix, every other face as it
    was."""
    from OCP.ShapeBuild import ShapeBuild_ReShape

    reshape = ShapeBuild_ReShape()
    for face in brep.faces_of(shape):
        if BRepCheck_Analyzer(face).IsValid():
            continue
        fix = ShapeFix_Face(face)
        fix.Perform()
        reshape.Replace(face, fix.Face())
    return reshape.Apply(shape)


def _flaw(shape: TopoDS_Shape) -> str:
    """What stops a shape being one valid solid, in words; empty when nothing does.

    Separate solids after a fuse mean some plate is not joined to the part: it stood clear of it,
    or touched it only along an edge or at a point.
    """
    if not _valid(shape):
        return "fails BRepCheck"
    n = len(_solids(shape))
    return "" if n == 1 else f"is {n} separate solids, not one"


def _unify(shape: TopoDS_Shape, base: TopoDS_Shape) -> TopoDS_Shape:
    """Merge the coplanar pieces the fuse left, touching no face the fuse did not make.

    A face of ``base`` the fuse left alone is the same face in its result, so every such face keeps
    its edges and vertices out of the merge - which holds it apart from every other face.
    """
    before = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(base, TopAbs_FACE, before)
    keep = TopTools_MapOfShape()
    for face in brep.faces_of(shape):
        if before.Contains(face):
            TopExp.MapShapes_s(face, keep)

    unify = ShapeUpgrade_UnifySameDomain(shape, True, True, False)
    unify.KeepShapes(keep)
    unify.Build()
    return unify.Shape()


def _failed(name: str, reason: str) -> PlateStatus:
    return {"name": name, "status": "failed", "reason": reason}


def _listed(shapes: list[TopoDS_Shape]) -> TopTools_ListOfShape:
    out = TopTools_ListOfShape()
    for shape in shapes:
        out.Append(shape)
    return out


def _valid(shape: TopoDS_Shape) -> bool:
    # In parallel: a quarter of the time on a part of 1,800 faces (0.15 s against 0.65 s).
    return bool(BRepCheck_Analyzer(shape, True, True).IsValid())


def _solids(shape: TopoDS_Shape) -> list[TopoDS_Shape]:
    found = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, TopAbs_SOLID, found)
    return [found.FindKey(i) for i in range(1, found.Extent() + 1)]


def _volume(shape: TopoDS_Shape) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return float(props.Mass())
