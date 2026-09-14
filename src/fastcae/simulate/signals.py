"""An answer, whichever solver gave it, and the signals read off it.

**An answer** is the same thing from Code_Aster's results file or from a solve here: displacement at
every node, rotation at the reference points, stress and von Mises at the nodes, the reactions of
every held group. Everything shown or compared is read off an answer, in one way, so two solvers
can differ only in what they computed.

**Signals** come in two kinds, and each says which:

- *deck* - what the deck itself reads off its answer (``POST_RELEVE_T``), under the deck's name;
- *derived* - what fastcae computes from the answer by geometry alone: the tilt of a coupling
  acting on
  a cylindrical surface (its rotation square to the cylinder's axis), each held group's reaction,
  the largest displacement, and von Mises at the 99.9th percentile of volume - the peak chases
  sharp corners and says more about the mesh than the part.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

from .fem import FEMesh, tet_volumes, triangle_areas
from .med import NodalField
from .setup import ROTATIONS, TRANSLATIONS, Setup

ARCMIN = 180.0 / math.pi * 60.0


@dataclass
class Answer:
    source: str
    u: np.ndarray
    rotation: np.ndarray
    von_mises: np.ndarray | None
    stress: np.ndarray | None
    reactions: dict[str, list[float]]


def from_med(
    mesh: FEMesh, fields: dict[str, NodalField], setup: Setup, source: str = "Code_Aster"
) -> Answer:
    """The answer in a Code_Aster results file."""
    n = mesh.n_nodes
    u = np.zeros((n, 3))
    rotation = np.full((n, 3), np.nan)
    depl = fields.get("DEPL")
    if depl is not None:
        for c, name in enumerate(TRANSLATIONS):
            if name in depl.components:
                u[:, c] = np.nan_to_num(depl.component(name, n, 0.0))
        points = [int(m[0]) for m in mesh.node_groups.values() if len(m) == 1]
        for c, name in enumerate(ROTATIONS):
            if name in depl.components:
                values = depl.component(name, n)
                rotation[points, c] = values[points]
    vm = fields["SIEQ_NOEU"].component("VMIS", n) if "SIEQ_NOEU" in fields else None
    stress = None
    if "SIGM_NOEU" in fields:
        sig = fields["SIGM_NOEU"]
        stress = np.column_stack(
            [sig.component(c, n) for c in ("SIXX", "SIYY", "SIZZ", "SIXY", "SIXZ", "SIYZ")]
        )
    reactions: dict[str, list[float]] = {}
    reac = fields.get("REAC_NODA")
    if reac is not None:
        values = np.column_stack([np.nan_to_num(reac.component(c, n, 0.0)) for c in TRANSLATIONS])
        for h in setup.held:
            for g in h.groups:
                # A reference point held through a rigid coupling carries nothing itself in
                # Code_Aster's reactions: the coupling's nodes carry it. Summed over both.
                members = [mesh.group_nodes(g)]
                for tie in setup.rigid:
                    if tie.reference == g:
                        members += [mesh.group_nodes(x) for x in tie.groups]
                reactions[g] = values[np.unique(np.concatenate(members))].sum(axis=0).tolist()
    return Answer(
        source=source, u=u, rotation=rotation, von_mises=vm, stress=stress, reactions=reactions
    )


def from_solution(solution, source: str) -> Answer:  # type: ignore[no-untyped-def]
    return Answer(
        source=source,
        u=solution.u,
        rotation=solution.rotation,
        von_mises=solution.von_mises,
        stress=solution.stress,
        reactions=solution.reactions,
    )


@dataclass
class Signal:
    name: str
    component: str
    value: float
    unit: str
    kind: str
    group: str

    def to_json(self) -> dict:
        return asdict(self)


def cylinder_axis(mesh: FEMesh, group: str) -> np.ndarray | None:
    """The axis of a group's surface patch when it is a cylinder: the direction every one of its
    normals is square to, with the normals spread round it."""
    members = np.zeros(mesh.n_nodes, bool)
    members[mesh.group_nodes(group)] = True
    skin = mesh.skin
    patch = skin.corners[members[skin.corners].all(axis=1)]
    if len(patch) < 6:
        return None
    p = mesh.nodes[patch]
    normal = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    area = np.linalg.norm(normal, axis=1)
    normal = normal / np.maximum(area, 1e-300)[:, None]
    scatter = np.einsum("n,ni,nj->ij", area, normal, normal) / area.sum()
    values, vectors = np.linalg.eigh(scatter)
    if values[0] > 0.02 or values[1] < 0.15:
        return None
    return vectors[:, 0]


def _weights(mesh: FEMesh) -> np.ndarray:
    """Each corner node's share of the volume: a quarter of every tetrahedron round it."""
    tets = mesh.tet10 if mesh.tet10 is not None else mesh.cells.get("TETRA4")
    w = np.zeros(mesh.n_nodes)
    if tets is not None:
        np.add.at(w, tets[:, :4].ravel(), np.repeat(tet_volumes(mesh.nodes, tets) / 4.0, 4))
    return w


def percentile(values: np.ndarray, weights: np.ndarray, share: float) -> float:
    keep = (weights > 0) & np.isfinite(values)
    v, w = values[keep], weights[keep]
    order = np.argsort(v)
    cum = np.cumsum(w[order]) / w.sum()
    return float(v[order][min(int(np.searchsorted(cum, share)), len(order) - 1)])


def signals(mesh: FEMesh, setup: Setup, answer: Answer) -> list[Signal]:
    out: list[Signal] = []
    for o in setup.outputs:
        try:
            members = mesh.group_nodes(o.group)
        except KeyError:
            continue
        if o.field == "DEPL":
            names = o.components or [*TRANSLATIONS, *ROTATIONS]
            for name in names:
                if name in TRANSLATIONS:
                    value = float(answer.u[members, TRANSLATIONS.index(name)].mean())
                    unit = "mm"
                elif name in ROTATIONS:
                    column = answer.rotation[members, ROTATIONS.index(name)]
                    if not np.isfinite(column).all():
                        continue
                    value, unit = float(column.mean()), "rad"
                else:
                    continue
                out.append(Signal(o.name, name, value, unit, "deck", o.group))
        elif o.field == "REAC_NODA" and o.group in answer.reactions:
            for c, name in enumerate(TRANSLATIONS):
                out.append(
                    Signal(o.name, name, float(answer.reactions[o.group][c]), "N", "deck", o.group)
                )
    for d in setup.distributing:
        try:
            ref = int(mesh.group_nodes(d.reference)[0])
        except KeyError:
            continue
        theta = answer.rotation[ref]
        axis = cylinder_axis(mesh, d.group)
        if axis is None or not np.isfinite(theta).all():
            continue
        along = float(theta @ axis)
        tilt = float(np.linalg.norm(theta - along * axis))
        out.append(Signal(d.group, "tilt", tilt * ARCMIN, "arcmin", "derived", d.reference))
        out.append(Signal(d.group, "spin", along * ARCMIN, "arcmin", "derived", d.reference))
    for group, force in sorted(answer.reactions.items()):
        out.append(Signal(group, "reaction", float(np.linalg.norm(force)), "N", "derived", group))
    total = np.zeros(3)
    for force in answer.reactions.values():
        total += force
    if answer.reactions:
        out.append(
            Signal("all supports", "reaction", float(np.linalg.norm(total)), "N", "derived", "")
        )
    volume_nodes = np.unique(mesh.skin.corners) if mesh.tet10 is None else np.unique(mesh.tet10)
    out.append(
        Signal(
            "displacement",
            "largest",
            float(np.linalg.norm(answer.u[volume_nodes], axis=1).max()),
            "mm",
            "derived",
            "",
        )
    )
    if answer.von_mises is not None:
        weights = _weights(mesh)
        out.append(
            Signal(
                "von Mises",
                "p99.9",
                percentile(answer.von_mises, weights, 0.999),
                "MPa",
                "derived",
                "",
            )
        )
        out.append(
            Signal(
                "von Mises",
                "p99",
                percentile(answer.von_mises, weights, 0.99),
                "MPa",
                "derived",
                "",
            )
        )
        out.append(
            Signal(
                "von Mises",
                "largest",
                float(np.nanmax(answer.von_mises[volume_nodes])),
                "MPa",
                "derived",
                "",
            )
        )
    return out


def compare(reference: list[Signal], other: list[Signal]) -> list[dict]:
    """Each signal the two answers share, side by side, with how far apart they are."""
    theirs = {(s.name, s.component): s for s in other}
    rows = []
    for s in reference:
        o = theirs.get((s.name, s.component))
        if o is None:
            continue
        scale = abs(s.value)
        rows.append(
            {
                "name": s.name,
                "component": s.component,
                "unit": s.unit,
                "kind": s.kind,
                "reference": s.value,
                "other": o.value,
                "difference": (o.value - s.value) / scale if scale > 0 else 0.0,
            }
        )
    return rows


def field_agreement(mesh: FEMesh, a: Answer, b: Answer) -> dict:
    """How far two answers on the same mesh are apart: the largest displacement difference against
    the largest displacement, and von Mises likewise."""
    nodes = np.unique(mesh.tet10) if mesh.tet10 is not None else np.arange(mesh.n_nodes)
    du = np.linalg.norm(a.u[nodes] - b.u[nodes], axis=1).max() / max(
        np.linalg.norm(a.u[nodes], axis=1).max(), 1e-300
    )
    out = {"displacement": float(du)}
    if a.von_mises is not None and b.von_mises is not None:
        va, vb = a.von_mises[nodes], b.von_mises[nodes]
        keep = np.isfinite(va) & np.isfinite(vb)
        out["von_mises"] = float(
            np.abs(va[keep] - vb[keep]).max() / max(np.abs(va[keep]).max(), 1e-300)
        )
    return out


def applied(mesh: FEMesh, setup: Setup) -> tuple[np.ndarray, np.ndarray]:
    """The resultant force of every load the analysis applies, and its moment about the origin."""
    force = np.zeros(3)
    moment = np.zeros(3)
    active = setup.active()
    for load in setup.nodal_loads:
        if load.load_set not in active:
            continue
        members = mesh.group_nodes(load.group)
        f = np.array([load.values.get(c, 0.0) for c in ("FX", "FY", "FZ")])
        m = np.array([load.values.get(c, 0.0) for c in ("MX", "MY", "MZ")])
        force += f * len(members)
        moment += m * len(members) + np.cross(mesh.nodes[members], f).sum(axis=0)
    return force, moment


def work(mesh: FEMesh, setup: Setup, answer: Answer) -> float:
    """Half the work the loads do through the answer's motion at their points - the strain energy,
    for a linear answer in equilibrium."""
    total = 0.0
    active = setup.active()
    for load in setup.nodal_loads:
        if load.load_set not in active:
            continue
        members = mesh.group_nodes(load.group)
        f = np.array([load.values.get(c, 0.0) for c in ("FX", "FY", "FZ")])
        m = np.array([load.values.get(c, 0.0) for c in ("MX", "MY", "MZ")])
        total += float((answer.u[members] @ f).sum())
        if np.any(m):
            theta = np.nan_to_num(answer.rotation[members])
            total += float((theta @ m).sum())
    return 0.5 * total


def certificate(
    reference: tuple[FEMesh, Setup, Answer], other: tuple[FEMesh, Setup, Answer], same_mesh: bool
) -> list[dict]:
    """Quantity by quantity, how a reproduction compares with the reference - never one score.

    Each row says what was compared, both values, how far apart, the tolerance it is held to and
    whether it holds. On the same mesh every quantity is held to a millionth; on a mesh of its own,
    to what meshing the same shape twice was measured to move."""
    (mesh_a, setup_a, a), (mesh_b, setup_b, b) = reference, other
    rows: list[dict] = []

    def add(
        quantity: str, va: float, vb: float, tolerance: float | None, unit: str, note: str = ""
    ) -> None:
        scale = abs(va)
        diff = (vb - va) / scale if scale > 0 else (0.0 if vb == va else float("inf"))
        rows.append(
            {
                "quantity": quantity,
                "reference": va,
                "other": vb,
                "difference": diff,
                "unit": unit,
                "tolerance": tolerance,
                "holds": None if tolerance is None else bool(abs(diff) <= tolerance),
                "note": note,
            }
        )

    tight = 1e-6
    f_a, _ = applied(mesh_a, setup_a)
    f_b, _ = applied(mesh_b, setup_b)
    add(
        "applied load",
        float(np.linalg.norm(f_a)),
        float(np.linalg.norm(f_b)),
        tight,
        "N",
        "the deck's loads, as each run applied them",
    )
    r_a = np.sum([v for v in a.reactions.values()], axis=0) if a.reactions else np.zeros(3)
    r_b = np.sum([v for v in b.reactions.values()], axis=0) if b.reactions else np.zeros(3)
    add(
        "reactions",
        float(np.linalg.norm(r_a)),
        float(np.linalg.norm(r_b)),
        1e-4 if same_mesh else 1e-3,
        "N",
    )
    for of, f, r in (("reference", f_a, r_a), ("other", f_b, r_b)):
        # One answer's own balance: the load it applied, and what its reactions leave of it.
        rows.append(
            {
                "quantity": f"out of balance, {'reference' if of == 'reference' else 'reproduction'}",
                "of": of,
                "reference": float(np.linalg.norm(f)),
                "other": float(np.linalg.norm(f + r)),
                "difference": float(np.linalg.norm(f + r) / max(np.linalg.norm(f), 1e-300)),
                "unit": "N",
                "tolerance": 1e-3,
                "holds": bool(np.linalg.norm(f + r) <= 1e-3 * max(np.linalg.norm(f), 1e-300)),
                "note": "the applied load and the reactions summed: what is left, over the load",
            }
        )
    add(
        "work of the loads",
        work(mesh_a, setup_a, a),
        work(mesh_b, setup_b, b),
        tight if same_mesh else 0.03,
        "N·mm",
        "half the loads' work through the motion: the strain energy",
    )
    vol_a = np.unique(mesh_a.tet10) if mesh_a.tet10 is not None else np.arange(mesh_a.n_nodes)
    vol_b = np.unique(mesh_b.tet10) if mesh_b.tet10 is not None else np.arange(mesh_b.n_nodes)
    add(
        "largest displacement",
        float(np.linalg.norm(a.u[vol_a], axis=1).max()),
        float(np.linalg.norm(b.u[vol_b], axis=1).max()),
        tight if same_mesh else 0.03,
        "mm",
    )
    if same_mesh:
        agree = field_agreement(mesh_a, a, b)
        rows.append(
            {
                "quantity": "displacement field",
                "reference": 0.0,
                "other": agree["displacement"],
                "difference": agree["displacement"],
                "unit": "",
                "tolerance": tight,
                "holds": agree["displacement"] <= tight,
                "note": "largest nodal difference over the largest displacement",
            }
        )
        if "von_mises" in agree:
            rows.append(
                {
                    "quantity": "von Mises field",
                    "reference": 0.0,
                    "other": agree["von_mises"],
                    "difference": agree["von_mises"],
                    "unit": "",
                    "tolerance": tight,
                    "holds": agree["von_mises"] <= tight,
                    "note": "largest nodal difference over the largest stress",
                }
            )
    if a.von_mises is not None and b.von_mises is not None:
        wa, wb = _weights(mesh_a), _weights(mesh_b)
        add(
            "von Mises p99.9",
            percentile(a.von_mises, wa, 0.999),
            percentile(b.von_mises, wb, 0.999),
            tight if same_mesh else 0.05,
            "MPa",
            "by volume, away from the singular corners the peak chases",
        )
        add(
            "von Mises p99",
            percentile(a.von_mises, wa, 0.99),
            percentile(b.von_mises, wb, 0.99),
            tight if same_mesh else 0.05,
            "MPa",
        )
        add(
            "von Mises peak",
            float(np.nanmax(a.von_mises[vol_a])),
            float(np.nanmax(b.von_mises[vol_b])),
            tight if same_mesh else None,
            "MPa",
            "" if same_mesh else "advisory: the peak says more about the mesh than the part",
        )
    sa = {(s.name, s.component): s for s in signals(mesh_a, setup_a, a)}
    sb = {(s.name, s.component): s for s in signals(mesh_b, setup_b, b)}
    for key, s in sa.items():
        if key not in sb or s.kind != "derived" or s.component not in ("tilt",):
            continue
        add(
            f"tilt {s.name}",
            s.value,
            sb[key].value,
            tight if same_mesh else 0.03,
            "arcmin",
            "derived: rotation square to the bore's axis",
        )
    deck = [(s, sb[k]) for k, s in sa.items() if k in sb and s.kind == "deck" and abs(s.value) > 0]
    if deck:
        worst = max(deck, key=lambda p: abs((p[1].value - p[0].value) / p[0].value))
        add(
            f"deck signals, worst ({worst[0].name} {worst[0].component})",
            worst[0].value,
            worst[1].value,
            tight if same_mesh else 0.05,
            worst[0].unit,
            f"{len(deck)} signals the deck asks for",
        )
    rows.append(
        {
            "quantity": "mesh",
            "reference": float(mesh_a.count("TETRA10")),
            "other": float(mesh_b.count("TETRA10")),
            "difference": 0.0
            if same_mesh
            else float(mesh_b.count("TETRA10") / max(mesh_a.count("TETRA10"), 1) - 1),
            "unit": "TETRA10",
            "tolerance": None,
            "holds": None,
            "note": "the same mesh"
            if same_mesh
            else "the field's own mesh, at the deck mesh's element sizes",
        }
    )
    return rows


def surface_area(mesh: FEMesh, group: str) -> float:
    members = np.zeros(mesh.n_nodes, bool)
    members[mesh.group_nodes(group)] = True
    patch = mesh.skin.corners[members[mesh.skin.corners].all(axis=1)]
    return float(triangle_areas(mesh.nodes, patch).sum())
