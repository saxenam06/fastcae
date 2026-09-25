"""A swept solid from four rails: the shape a parametric rib really is.

A rib that follows a curve is **one solid**, not a chain of flat plates lapped end to end. Built as
a chain it leaves a sliver face at every lap - measured on this housing at two to four faces under
5 mm2 per joint, 25 of them for two plates a rib and 291 for six - and a design that adds any such
face is rejected. So the curve goes straight to a solid and there are no joints to leave anything.

**Four rails** run along the rib: the two bottom edges and the two top edges, each sampled at the
same stations. Between them:

* two **side** faces, one B-spline each through the bottom and top rail of that side;
* a **top** face and a **bottom** face, likewise;
* a flat **cap** at each end.

Six faces a rib, sewn into a shell and closed into a solid. The rails carry everything the rib is -
where its curve runs, how the floor rises under it, how tall it stands at each station and which way
the mould pulls - so nothing about the shape is decided here.
"""

from __future__ import annotations

from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeSolid,
    BRepBuilderAPI_Sewing,
)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.ShapeFix import ShapeFix_Shape
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.TopAbs import TopAbs_SHELL, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape
from OCP.TopTools import TopTools_ListOfShape

TOLERANCE_MM = 1e-3
"""How near two sewn faces must come to count as the same edge."""


def close(faces: list[TopoDS_Shape]) -> TopoDS_Shape:
    """Faces sewn into a shell and closed into one valid solid, turned outward.

    Raises ``ValueError`` when they will not: a shell is a surface, not a body, and is never
    handed back in place of one.
    """
    sew = BRepBuilderAPI_Sewing(TOLERANCE_MM)
    for f in faces:
        sew.Add(f)
    sew.Perform()
    sewn = sew.SewedShape()
    found = TopExp_Explorer(sewn, TopAbs_SHELL)
    if not found.More():
        raise ValueError("the faces do not sew into a shell")
    made = BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(found.Current()))
    if not made.IsDone():
        raise ValueError("the shell does not close into a solid")
    out: TopoDS_Shape = made.Solid()
    if not BRepCheck_Analyzer(out).IsValid():
        fix = ShapeFix_Shape(out)
        fix.Perform()
        out = fix.Shape()
    # the repair hands back whatever it could make valid, and a shell is valid - but a shell is a
    # surface, not a body, and the fuse would add no metal for it. Take the solid, or close the
    # shell into one; accepting the shell is how fifteen ribs came back as nothing to fuse.
    got = TopExp_Explorer(out, TopAbs_SOLID)
    if got.More():
        out = TopoDS.Solid_s(got.Current())
    else:
        shell = TopExp_Explorer(out, TopAbs_SHELL)
        if not shell.More():
            raise ValueError("the swept rib is neither a solid nor a shell")
        again = BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(shell.Current()))
        if not again.IsDone():
            raise ValueError("the repaired shell does not close into a solid")
        out = again.Solid()
    if not BRepCheck_Analyzer(out).IsValid():
        raise ValueError("the swept rib is not a valid solid")
    # which way round the rails run decides which way the faces face; a solid holding a negative
    # volume is inside out, and the fuse would take it as a hole rather than as metal
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(out, props)
    if props.Mass() < 0.0:
        out = out.Reversed()
    return out


def network(solids: list[TopoDS_Shape]) -> TopoDS_Shape:
    """Every rib of a design unioned into **one** solid, in a single operation.

    Fusing rib after rib into the housing asks the kernel to discover, one boolean at a time, a
    topology that is already known: where the ribs cross each other. Each crossing is then a sharp
    X between two solids and a chance to leave a face of a few square millimetres, which is what
    costs four to six ribs of every ten.

    Unioned among themselves first, the crossings are resolved once, together, with every rib in
    hand - and the housing then meets a single body rather than a queue of them.
    """
    if not solids:
        raise ValueError("no ribs to join")
    if len(solids) == 1:
        return solids[0]
    # a union, not a general fuse: the latter splits the arguments into cells and hands back every
    # piece - two crossing ribs came out as eight solids
    args, tools = TopTools_ListOfShape(), TopTools_ListOfShape()
    args.Append(solids[0])
    for shape in solids[1:]:
        tools.Append(shape)
    joined = BRepAlgoAPI_Fuse()
    joined.SetArguments(args)
    joined.SetTools(tools)
    joined.SetRunParallel(True)
    joined.Build()
    if not joined.IsDone():
        raise ValueError("the ribs do not join into one body")
    out = joined.Shape()
    unify = ShapeUpgrade_UnifySameDomain(out, True, True, False)
    unify.Build()
    return unify.Shape()
