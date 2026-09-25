"""A rib network for a project: **one constrained problem**, from the seed to the solved design.

For the deck's load case and its objective - the largest displacement - find the fins, in every
kept design volume, that bring it lowest with **no more metal than the target's**, every rule of
the foundry and of the design volumes kept from the first fin placed:

1. **Seed** - a seeder proposes fins and the gate of placement admits them
   (:func:`.fins.placeable`, the fins already placed, and the CAD's own sections): as many as the
   target's metal affords at full height.
2. **Pass** - a short optimisation of every fin's numbers inside bounds, the metal capped, the
   clearance and spacing rules held.
3. **Oracle** - every fin judged on its numbers before any boolean. It should find nothing.
4. **Chooser** - CP-SAT keeps a network under the rules that are decisions, each fin valued in
   the company of the rest; a fin dropped on its value alone is measured back in.
5. **Polish** - the same optimisation with the topology fixed.
6. **Ribs, CAD, mesh, solve** - each fin a swept solid rooted in its walls, fused, meshed face by
   face and solved as the target was (:func:`.campaign.realise`).

Every continuous stage is read against the target on the same cubes - the true largest
displacement, at one drawing radius - and the design's record says whether it beats the target
with no more metal, on the cubes and then on the mesh. **Nothing here knows the part**: the
volumes, the deck and the target are the project's.
"""

from __future__ import annotations

import dataclasses
import json
import re
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..designs import cad, sweep, target
from ..designs import campaign as designs
from ..project import Project
from . import campaign, choose, curved, fins, library, networks, oracle, paths, patterns

Say = Callable[[str], None]

SEEDERS = (*fins.ANCHOR_PATTERNS, "scatter")
SEEDER_WORDS = {
    "spokes": "from each boss to the first wall it meets, by angle",
    "chords": "wall to wall, closing a ring round each boss",
    "tangents": "leaving each boss aslant",
    "wheel": "spokes and the ring across them: closed cells",
    "scatter": "at random, placed by the rules alone",
}
RAYS = (12, 72)
"""The fewest and the most rays - or scattered fins - a volume is asked for."""
STEPS = (5, 60)
POLISH = (0, 60)
CELL_MM = 10.0
"""The cubes the pass and the polish are solved on."""
DRAW_MM = 1.5 * CELL_MM
"""The one radius every reading against the target is drawn at: the pass's own figures follow its
continuation, radius by radius, and cannot be set side by side."""
SLIDE_MM = 40.0
"""How far an end may slide either way in the pass and the polish."""
SLIDE_SHARE = 0.25
"""And never more than this of its chord: an end that slides half a short fin's length along its
wall turns the fin on itself."""
MARGIN_DEFAULT = 1.3
"""How much more the cubes flatter a rib network than they flatter the target, before any design
of the project has been solved to learn it from. Measured on the first housing: 1.1 to 1.9."""
VALUE_FLOOR = 1.5 / choose.SCALE
"""What a fin that passes every rule counts for at the least. While the cap has room no rule
removes such a fin: a first-order value at or under nothing is within the cubes' own error."""
DEFLECTION_ONLY = [0.0] * 400
"""The pass answers for the largest displacement alone: no weight on the lead at any step."""
SHAPE_FROM_THE_START = [1.0] * 400
"""The shape charges hold from the first step: the seed is already in one piece."""
ABOUT = (
    "A rib network: fins proposed by a seeder and admitted by the gate of placement, moved by a "
    "short pass under the target's metal with every rule held, judged by the oracle before any "
    "boolean, chosen as a network by CP-SAT on the objective's own derivative, polished with the "
    "topology fixed, then built as CAD, meshed face by face and solved as the target was - every "
    "stage read against the target, every fin's fate kept."
)


@dataclass
class Asked:
    """What a network campaign is asked for."""

    pattern: str = "spokes"
    rays: int = 36
    steps: int = 20
    polish: int = 30
    seed: int = 0
    """A scatter's seed: the same seed scatters the same fins."""
    share: float = 1.0
    """Of the target's metal: the cap."""
    most: int = 40
    """Ribs at most to a volume."""
    volumes: list[str] = field(default_factory=list)
    """The kept volumes to use, by name; all of them when none is named."""
    name: str | None = None

    @classmethod
    def of(cls, args: dict[str, Any]) -> Asked:
        """From a job's arguments, held to sense."""
        pattern = str(args.get("pattern") or "spokes")
        if pattern not in SEEDERS:
            raise ValueError(f"no seeder {pattern!r}: one of {', '.join(SEEDERS)}")

        def held(key: str, default: int, within: tuple[int, int]) -> int:
            return int(np.clip(int(args.get(key, default)), *within))

        return cls(
            pattern=pattern,
            rays=held("rays", 36, RAYS),
            steps=held("steps", 20, STEPS),
            polish=held("polish", 30, POLISH),
            seed=int(args.get("seed", 0)),
            share=float(np.clip(float(args.get("share", 1.0)), 0.1, 1.0)),
            most=int(args.get("most", 40)),
            volumes=[str(v) for v in args.get("volumes") or []],
            name=args.get("name") or None,
        )


def litres(fields_: dict[str, fins.Field], layout: fins.Layout, numbers: np.ndarray) -> np.ndarray:
    """Each fin's metal as it would be cast, in litres: its section times its height along its
    run. The cubes draw a fin about a fifth lighter than its CAD weighs, and the cap is the
    target's metal as cast."""
    out = []
    for name, (ia, ib), number in zip(layout.where, layout.ends, numbers, strict=True):
        f = fields_[name]
        pts, _ = fins.run(number, f.rails[ia], f.rails[ib], pieces=48)
        along = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
        tall = fins._bernstein2(along / max(float(along[-1]), 1e-9)) @ np.asarray(
            number[6:9], float
        )
        out.append(fins.THICKNESS_MM * float(np.trapezoid(tall, along)) / 1e6)
    return np.asarray(out, float)


def slides(fields_: dict[str, fins.Field], layout: fins.Layout, numbers: np.ndarray) -> np.ndarray:
    """How far each fin's ends may slide: :data:`SLIDE_MM`, and never more than
    :data:`SLIDE_SHARE` of its chord."""
    out = []
    for name, (ia, ib), number in zip(layout.where, layout.ends, numbers, strict=True):
        f = fields_[name]
        pts, _ = fins.run(number, f.rails[ia], f.rails[ib])
        out.append(min(SLIDE_MM, SLIDE_SHARE * float(np.linalg.norm(pts[-1] - pts[0]))))
    return np.asarray(out, float)


def placement_words(refused: list[tuple[str, str]]) -> str:
    """What the gate of placement refused, in a few words, the commonest first."""
    groups: Counter[str] = Counter()
    for _, why in refused:
        groups[
            "no outline on the CAD"
            if why.startswith("on the CAD")
            else "crowding or crossing one already placed"
            if "already placed" in why
            else "over a hole or keep-out"
            if why.startswith("passes over")
            else "wall too low to root in"
            if why.startswith("the metal at one end")
            else "glancing the wall"
            if why.startswith("meets its wall")
            else "not clear of the metal"
            if "clear of the metal" in why
            else why
        ] += 1
    return ", ".join(f"{n} {what}" for what, n in groups.most_common())


def margin_from(
    records: list[dict[str, Any]], target_mesh_mm: float, target_cubes_mm: float
) -> tuple[float, list[float]]:
    """How much more the cubes flatter a rib network than they flatter the target, and what it
    was learned from: each solved design's mesh reading over its cubes reading, against the
    target's own - the median, never under one. Only a design whose every kept fin was built says
    anything about the cubes: one built short of its network reads worse for that, not for them."""
    learned: list[float] = []
    for record in records:
        cubes = (record.get("against_target") or {}).get("largest_mm")
        mesh = ((record.get("solve") or {}).get("headline") or {}).get("largest_displacement_mm")
        kept = [f for f in record.get("fins") or [] if str(f.get("chooser", "")).startswith("kept")]
        built = [f for f in networks.fin_states(record, "polish") if f["state"] == "built"]
        known = cubes and mesh and target_mesh_mm and target_cubes_mm
        if known and kept and len(built) == len(kept):
            learned.append((mesh / cubes) / (target_mesh_mm / target_cubes_mm))
    if not learned:
        return MARGIN_DEFAULT, []
    return max(float(np.median(learned)), 1.0), learned


def _past(project: Project) -> list[dict[str, Any]]:
    out = []
    for path in sorted(designs.root(project).glob("*/*/design.json")):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return out


class _Stopped(Exception):
    """The job was cancelled between two stages."""


def run(  # noqa: C901 - the stages in order read better in one place
    project: Project,
    extraction: Any,
    deck: Any,
    found: list[tuple[str, Any]],
    held: dict[str, Any],
    asked: Asked,
    say: Say = print,
    lock: Any = None,
    cancelled: Callable[[], bool] = lambda: False,
) -> Path:
    """The campaign's folder: one network, every stage stamped on its record as it finishes so
    the screens follow it. ``found`` is the kept design volumes, ``(name, volume)``; ``held`` the
    target's summary (:func:`fastcae.designs.target.load`); ``lock`` the card's, held while the
    cubes are solved and again for the mesh's solve."""
    from contextlib import nullcontext

    from ..gpu import release

    gpu = lock if lock is not None else nullcontext()
    budget = asked.share * float(held["metal_L"])
    vols = dict(found)

    # --- the campaign and its design exist from here on --------------------------------------
    folder = designs.create(project, [], name=asked.name or f"network · {asked.pattern}")
    head = designs._read(folder / "campaign.json") or {}
    head.update(
        {
            "kind": "ribs.network",
            "target": held,
            "stages": [s for s, _ in networks.STAGES],
            "about": ABOUT,
            "asked": asdict(asked),
            "designs": 1,
        }
    )
    designs._write(folder / "campaign.json", head)
    d = folder / "01"
    designs._write(
        d / "design.json",
        {
            "id": f"{folder.name}/01",
            "index": 1,
            "name": f"{asked.pattern} · network",
            "why": f"seeded as {asked.pattern}, {SEEDER_WORDS[asked.pattern]}; a pass of "
            f"{asked.steps} steps under the target's metal; CP-SAT chooses; a polish of "
            f"{asked.polish} steps",
            "mix": {"name": "deck", "words": "the deck's load case"},
            "budget_L": budget,
            "fins": [],
            "stages": {s: {"status": "pending"} for s, _ in networks.STAGES},
        },
    )

    def stamp(stage: str, **changes: object) -> None:
        designs._Design(d).stage(stage, **changes)

    def keep(**fields: object) -> None:
        rec = designs._Design(d)
        rec.record.update(fields)
        rec.save()

    def check() -> None:
        if cancelled():
            raise _Stopped

    try:
        with gpu:
            polished = _on_the_cubes(
                project, extraction, deck, found, held, asked, budget, d, say, stamp, keep, check
            )
        release()
        if polished is None:
            return folder
        check()
        _build(project, extraction, deck, vols, held, d, polished, say, stamp, lock)
    except _Stopped:
        record = designs._Design(d).record
        for stage, _ in networks.STAGES:
            if record["stages"][stage].get("status") in ("pending", "running"):
                stamp(stage, status="failed", detail="stopped by the user")
        say("stopped by the user")
    except Exception as error:  # noqa: BLE001 - a campaign that fails says so on its record
        record = designs._Design(d).record
        running = next(
            (s for s, _ in networks.STAGES if record["stages"][s].get("status") == "running"),
            None,
        )
        stamp(running or "seed", status="failed", detail=f"{type(error).__name__}: {error}"[:300])
        raise
    return folder


@dataclass
class _Polished:
    """What the cubes hand to the builder."""

    where: dict[str, fins.Field]
    layout: fins.Layout
    start: np.ndarray
    ids: list[str]
    kept: list[int]
    sub: fins.Layout
    numbers: np.ndarray
    score: float


def _on_the_cubes(  # noqa: C901 - the stages in order read better in one place
    project: Project,
    extraction: Any,
    deck: Any,
    found: list[tuple[str, Any]],
    held: dict[str, Any],
    asked: Asked,
    budget: float,
    d: Path,
    say: Say,
    stamp: Callable[..., None],
    keep: Callable[..., None],
    check: Callable[[], None],
) -> _Polished | None:
    """The seed, the pass, the oracle, the chooser and the polish - everything the card's cubes
    are needed for."""
    from ..designs.optimise import mixes
    from ..gpu import release
    from . import mma

    t0 = time.time()
    stamp("seed", status="running", started=t0)
    mix = next(m for m in mixes(extraction, deck.setup) if m.name == "deck")
    vols = dict(found)

    # the target on the same cubes: what every stage is read against
    v, t, _ = cad.tessellate(cad.load(target.folder(project) / "target.brep"))
    theirs = paths.Model(
        project,
        extraction,
        deck.setup,
        [],
        mix,
        CELL_MM,
        lambda _: None,
        solid=paths.solid_of(extraction, v, t, CELL_MM),
    )
    m = theirs.evaluate(np.ones(len(theirs.cells)))
    ref = paths.Reference(m["robust_um"], m["smooth_max_mm"], 1.0)
    target_cubes = float(m["largest_mm"])
    target_mesh = float((held.get("headline") or {}).get("largest_displacement_mm") or 0.0)
    del theirs
    release()
    margin, learned = margin_from(_past(project), target_mesh, target_cubes)
    say(
        f"the target on the cubes: largest {target_cubes:.3f} mm with {held['metal_L']:.2f} L; "
        f"the cubes' margin {margin:.2f}"
        + (f", learned from {len(learned)} solved designs" if learned else ", nothing solved yet")
    )

    model = paths.Model(project, extraction, deck.setup, [f for _, f in found], mix, CELL_MM, say)
    where = fins.fields(model, found, extraction)

    def largest(layout_: fins.Layout, numbers_: np.ndarray) -> float:
        drawing = fins.draw(where, layout_, numbers_, model.n_design, DRAW_MM, 1.0)
        stiff = np.ones(len(model.cells))
        stiff[model.n_metal :] = paths.E_MIN + (1.0 - paths.E_MIN) * drawing.metal
        got, _, _ = model.gradient(stiff, 0.0, ref, {})
        return float(got["largest_mm"])

    def capped(layout_: fins.Layout, numbers_: np.ndarray) -> np.ndarray:
        out = np.array(numbers_, float)
        for n, (name, (ia, ib)) in enumerate(zip(layout_.where, layout_.ends, strict=True)):
            f = where[name]
            out[n] = fins.capped(out[n], f, f.rails[ia], f.rails[ib])
        return out

    def on_cad(name: str, f: fins.Field, ends: tuple[int, int], number: np.ndarray, fin: str):  # type: ignore[no-untyped-def]
        return _on_cad(extraction, vols[name], f, ends, number, fin)

    def seed_on_cad(
        name: str, f: fins.Field, a: tuple[int, float], b: tuple[int, float], row: list[float]
    ) -> str | None:
        number = fins.capped(np.asarray(row, float), f, f.rails[a[0]], f.rails[b[0]])
        verdict, _, _, _ = on_cad(name, f, (a[0], b[0]), number, "seed")
        return None if verdict.ok else f"on the CAD: {verdict.reason}"

    def sow(rays: int, also: Any = None) -> tuple[fins.Layout, np.ndarray, list[tuple[str, str]]]:
        refused: list[tuple[str, str]] = []
        if asked.pattern == "scatter":
            layout_, start_ = fins.sow_scatter(
                where, rays, seed=asked.seed, refused=refused, also=also
            )
        else:
            layout_, start_ = fins.sow_anchor(
                where, asked.pattern, rays, refused=refused, also=also
            )
        return layout_, start_, refused

    # --- 1. the seed: as many fins as the target's metal affords at full height ---------------
    # the spacing rule is kept by where the fins are put, so more rays do not always place more
    # fins: of the counts tried, the one that places the most under the cap
    best: tuple[int, int] | None = None
    for rays in range(asked.rays, RAYS[0] - 1, -2):
        layout_, start_, _ = sow(rays)
        cast = float(litres(where, layout_, capped(layout_, start_)).sum()) if len(start_) else 0.0
        if cast <= budget and (best is None or len(start_) > best[1]):
            best = (rays, len(start_))
    rays = best[0] if best else RAYS[0]
    check()
    # and then with the CAD's own word on every fin: it sees what no plan or cube does
    layout, start, refused = sow(rays, also=seed_on_cad)
    if not len(start):
        stamp("seed", status="failed", detail="the gate of placement admitted no fin")
        return None
    start = capped(layout, start)
    layout = layout.narrow(
        start, slides(where, layout, start), band_mm=fins.bands(where, layout, start)
    )
    ids = [f"{w}:fin:{k}" for k, w in enumerate(layout.where)]
    _, junctions0 = choose.relations(layout, start, where, root_free=fins.ROOT_FREE)
    big = largest(layout, start)
    cast = float(litres(where, layout, start).sum())
    ledger: dict[str, dict[str, Any]] = {
        i: {
            "id": i,
            "kind": asked.pattern,
            "ends": list(layout.ends[n]),
            "seed": np.round(start[n], 3).tolist(),
            "verdicts": [],
        }
        for n, i in enumerate(ids)
    }
    networks.save_runs(d, {"seed": (layout, start, ids)}, where)
    words = placement_words(refused)
    keep(
        fins=[ledger[i] for i in ids],
        placement={"rays": rays, "refused": [{"volume": a, "why": b} for a, b in refused]},
    )
    say(f"seed '{asked.pattern}': {len(ids)} fins, {cast:.2f} L, largest {big:.3f} mm; {words}")
    stamp(
        "seed",
        status="done",
        seconds=round(time.time() - t0, 1),
        detail=f"{len(ids)} fins, {cast:.1f} L; largest {big:.2f} mm on the cubes, target "
        f"{target_cubes:.2f}" + (f"; placement refused {len(refused)}: {words}" if words else ""),
    )
    check()

    # --- 2. the pass: every fin moved by the loads, inside its bounds, under the cap ----------
    t1 = time.time()
    stamp("pass", status="running", started=t1, detail=f"{asked.steps} steps")
    passed = fins.optimise(
        model,
        where,
        layout,
        start,
        budget,
        ref,
        steps=asked.steps,
        say=say,
        lead_weights=DEFLECTION_ONLY,
        skip=junctions0,
        hold_apart=True,
        root_free=fins.ROOT_FREE,
        late=SHAPE_FROM_THE_START,
        hold_presence=True,
    )
    numbers = passed.numbers
    for n, i in enumerate(ids):
        ledger[i]["after_pass"] = np.round(numbers[n], 3).tolist()
    networks.save_runs(d, {"seed": (layout, start, ids), "pass": (layout, numbers, ids)}, where)
    big = largest(layout, numbers)
    cast = float(litres(where, layout, numbers).sum())
    keep(fins=[ledger[i] for i in ids], **{"pass": {"history": passed.history}})
    say(f"after the pass: largest {big:.3f} mm on the cubes, {cast:.2f} L")
    stamp(
        "pass",
        status="done",
        seconds=round(time.time() - t1, 1),
        detail=f"largest {big:.2f} mm on the cubes, target {target_cubes:.2f}; "
        f"{cast:.1f} L of {budget:.1f}",
    )
    check()

    # --- 3. the oracle, on the numbers ---------------------------------------------------------
    t2 = time.time()
    stamp("oracle", status="running", started=t2)
    verdicts = oracle.on_numbers(layout, numbers, where)
    for verdict in verdicts:
        ledger[verdict.fin]["verdicts"].append(verdict.row())
        if not verdict.ok:
            say(f"   {verdict.fin}: {verdict.reason}")
            ledger[verdict.fin]["chooser"] = f"refused by the oracle: {verdict.reason}"
    passing = {verdict.fin for verdict in verdicts if verdict.ok}
    keep(fins=[ledger[i] for i in ids])
    stamp(
        "oracle",
        status="done",
        seconds=round(time.time() - t2, 1),
        detail=networks.stage_details({"fins": [ledger[i] for i in ids]})["oracle"],
    )
    if not passing:
        stamp("chooser", status="failed", detail="nothing passed the oracle")
        return None
    check()

    # --- 4. the chooser: each fin valued in the network's company -----------------------------
    t3 = time.time()
    stamp("chooser", status="running", started=t3, detail="each fin's value, in company")
    radius = mma.RADII[min(asked.steps - 1, len(mma.RADII) - 1)] * model.grid.spacing_mm
    judged = numbers.copy()
    refused_now = [n for n, i in enumerate(ids) if i not in passing]
    judged[refused_now, 9] = 0.0
    value = fins.values_carried(model, where, layout, judged, ref, radius, lead_weight=0.0)
    metal_each = litres(where, layout, numbers)
    conflicts, junctions = choose.relations(layout, numbers, where, root_free=fins.ROOT_FREE)
    for n, i in enumerate(ids):
        ledger[i]["value"] = round(float(value[n]), 5)
        ledger[i]["metal_L"] = round(float(metal_each[n]), 4)
    table = choose.Table(
        ids=ids,
        volume=list(layout.where),
        value=np.maximum(value, VALUE_FLOOR),
        metal_L=metal_each,
        conflicts={c for c in conflicts if c[0] != c[1]},
        junctions=junctions,
    )
    table.value = np.where(np.isin(np.arange(len(ids)), refused_now), -1e3, table.value)
    choices = choose.choose(table, budget_L=budget, most=asked.most, alternatives=1)
    if not choices or not choices[0].kept:
        stamp("chooser", status="failed", detail="no network keeps the rules")
        return None
    chosen = choices[0]
    kept = list(chosen.kept)

    def read(which: list[int]) -> float:
        lay = fins.Layout.of(
            where, [layout.where[n] for n in which], [layout.ends[n] for n in which]
        )
        return largest(lay, numbers[which])

    # nothing leaves the network on a first-order estimate alone: a fin dropped for its value,
    # and not by a rule, is measured back in, and stays out only if the true largest displacement
    # is no worse without it
    measured_in: dict[str, str] = {}
    by_value = [
        int(n)
        for n in np.argsort(-value)
        if n not in kept
        and ids[n] in passing
        and str(chosen.why.get(ids[n], "")).startswith(("worth nothing", "a better set"))
    ]
    if by_value:
        now = read(kept)
        for n in by_value:
            clash = any((min(n, k), max(n, k)) in table.conflicts for k in kept)
            if clash or float(metal_each[kept].sum() + metal_each[n]) > budget:
                continue
            with_it = read([*kept, n])
            if with_it < now - 1e-4:
                measured_in[ids[n]] = (
                    f"kept: measured {now:.3f} mm without it, {with_it:.3f} mm with it"
                )
                say(f"   {ids[n]}: {measured_in[ids[n]]}")
                kept.append(n)
                now = with_it
        kept.sort()
    standing = {ids[n] for n in kept}
    for i in ids:
        row = ledger[i]
        if i in standing:
            row["chooser"] = measured_in.get(i, "kept")
        elif i in chosen.why and not str(row.get("chooser", "")).startswith("refused"):
            row["chooser"] = chosen.why[i]
    keep(fins=[ledger[i] for i in ids], network=chosen.summary(table))
    stamp(
        "chooser",
        status="done",
        seconds=round(time.time() - t3, 1),
        detail=f"{len(kept)} kept, {float(metal_each[kept].sum()):.2f} L"
        + (f"; {len(measured_in)} measured back in" if measured_in else ""),
    )
    check()

    # --- 5. the polish: the same problem, the topology fixed -----------------------------------
    t4 = time.time()
    stamp("polish", status="running", started=t4, detail=f"{len(kept)} fins, {asked.polish} steps")
    sub = fins.Layout.of(where, [layout.where[n] for n in kept], [layout.ends[n] for n in kept])
    sub = sub.narrow(
        numbers[kept],
        slides(where, sub, numbers[kept]),
        band_mm=fins.bands(where, sub, numbers[kept]),
    )
    sub_numbers = numbers[kept].copy()
    sub_numbers[:, 9] = 1.0
    index = {n: k for k, n in enumerate(kept)}
    sub_junctions = {(index[a], index[b]) for a, b in junctions if a in index and b in index}
    history: list[dict[str, Any]] = []
    if asked.polish:
        result = fins.optimise(
            model,
            where,
            sub,
            sub_numbers,
            budget,
            ref,
            steps=asked.polish,
            say=say,
            hold=True,
            lead_weights=DEFLECTION_ONLY,
            skip=sub_junctions,
            root_free=fins.ROOT_FREE,
        )
        sub_numbers, history = result.numbers, result.history
    big = largest(sub, sub_numbers)
    cast = float(litres(where, sub, sub_numbers).sum())
    beats = bool(big < target_cubes and cast <= budget)
    for k, n in enumerate(kept):
        ledger[ids[n]]["polished"] = np.round(sub_numbers[k], 3).tolist()
    networks.save_runs(
        d,
        {
            "seed": (layout, start, ids),
            "pass": (layout, numbers, ids),
            "polished": (sub, sub_numbers, [ids[n] for n in kept]),
        },
        where,
    )
    keep(
        fins=[ledger[i] for i in ids],
        polish={"history": history},
        optimise={
            "history": [
                {
                    "iteration": h["iteration"],
                    "cells": None,
                    "volume_L": h["metal_L"],
                    "objective": h["j"],
                    "seconds": h["seconds"],
                }
                for h in [*passed.history, *history]
            ],
            "stats": {"fins": len(ids), "kept": len(kept)},
        },
        against_target={
            "on": "cubes",
            "largest_mm": round(big, 4),
            "target_largest_mm": round(target_cubes, 4),
            "metal_L": round(cast, 3),
            "target_metal_L": round(budget, 3),
            "margin": round(margin, 3),
            "beats": beats,
            "beats_by_the_margin": bool(big < target_cubes / margin and cast <= budget),
        },
    )
    say(
        f"polished: largest {big:.3f} mm on the cubes against the target's {target_cubes:.3f}, "
        f"{cast:.2f} L of {budget:.2f}"
    )
    stamp(
        "polish",
        status="done",
        seconds=round(time.time() - t4, 1),
        detail=f"{len(kept)} fins; largest {big:.2f} mm on the cubes, target {target_cubes:.2f}; "
        f"{cast:.1f} L of {budget:.1f}",
    )
    score = float(history[-1]["j"]) if history else float(passed.history[-1]["j"])
    return _Polished(where, layout, start, ids, kept, sub, sub_numbers, score)


def _on_cad(
    extraction: Any, vol: Any, f: fins.Field, ends: tuple[int, int], number: np.ndarray, fin: str
):  # type: ignore[no-untyped-def]
    """A fin's verdict on the CAD's own sections, the outline it was offered, and the sheet and
    heights it was read at."""
    axis = np.asarray(vol.recipe.axis, float)
    axis /= np.linalg.norm(axis)
    pts, _ = fins.run(number, f.rails[ends[0]], f.rails[ends[1]], pieces=fins.STATIONS)
    at = curved.sheet(f.plane.to3d(pts), axis, np.asarray(vol.recipe.point, float))
    along = (at.s >= 0.0) & (at.s <= at.length)
    tall = fins._bernstein2(at.s[along] / at.length) @ np.asarray(number[6:9], float)
    verdict, offered = oracle.on_sheet(
        extraction, vol, at, tall, fin, floor_required=vol.recipe.kind == "floor"
    )
    return verdict, offered, at, tall


def _build(
    project: Project,
    extraction: Any,
    deck: Any,
    vols: dict[str, Any],
    held: dict[str, Any],
    d: Path,
    polished: _Polished,
    say: Say,
    stamp: Callable[..., None],
    lock: Any,
) -> None:
    """Each kept fin a solid - as polished, or as it was seeded if the CAD will not have that -
    then the network fused, meshed and solved as the target was."""
    from contextlib import nullcontext

    where, sub, numbers, ids, kept = (
        polished.where,
        polished.sub,
        polished.numbers.copy(),
        polished.ids,
        polished.kept,
    )
    # stamped before the record is read: what is read here is saved again with the fins' verdicts,
    # and must not take the stage back to where it was
    stamp("ribs", status="running", started=time.time())
    rec = designs._Design(d)
    by_id = {row["id"]: row for row in rec.record["fins"]}
    base = cad.load(designs._baseline(project))
    metals = {name: library._metal(extraction, f.plane) for name, f in where.items()}
    bodies: list[cad.Body] = []
    built: list[str] = []
    for k, (n, verdict) in enumerate(
        zip(kept, oracle.on_numbers(sub, numbers, where), strict=True)
    ):
        i = ids[n]
        by_id[i]["verdicts"].append({**verdict.row(), "stage": "numbers after polish"})
        if not verdict.ok:
            continue
        name = sub.where[k]
        f, vol = where[name], vols[name]
        got, at = None, None
        # the polished fin first; if the CAD will not have it, the fin as it was seeded, which
        # the CAD had already passed - a fin is not dropped for where the polish moved it
        for stage, number in (("sheet", numbers[k]), ("sheet, as seeded", polished.start[n])):
            sheet, offered, at, tall = _on_cad(extraction, vol, f, sub.ends[k], number, i)
            by_id[i]["verdicts"].append({**sheet.row(), "stage": stage})
            if not sheet.ok:
                continue
            reasons: list[str] = []
            got = curved.swept(
                extraction, vol, at, tall, base, fins.THICKNESS_MM, why=reasons, offered=offered
            )
            if got is None:
                by_id[i]["verdicts"].append(
                    {
                        "fin": i,
                        "stage": stage.replace("sheet", "solid"),
                        "ok": False,
                        "reason": "; ".join(reasons),
                    }
                )
                continue
            if stage != "sheet":
                by_id[i]["built_as"] = "seeded"
                numbers[k] = number
            break
        if got is None or at is None:
            continue
        bodies.append(
            cad.Body(
                name=i,
                shape=got[0],
                outline=got[1],
                normal=at.across[len(at.s) // 2],
                thickness_mm=fins.THICKNESS_MM,
            )
        )
        built.append(i)
    rec.record["name"] = f"{rec.record['name'].split(' · ')[0]} · network · {len(bodies)} ribs"
    rec.save()
    say(f"{len(bodies)} of {len(kept)} fins pass the oracle and build")
    if not bodies:
        stamp("ribs", status="failed", detail="no fin of the network passed the oracle")
        return
    groups = cad._solids(sweep.network([b.shape for b in bodies]))
    grouped = [
        cad.Body(
            name=f"group {g + 1}",
            shape=shape,
            outline=bodies[min(g, len(bodies) - 1)].outline,
            normal=bodies[min(g, len(bodies) - 1)].normal,
            thickness_mm=fins.THICKNESS_MM,
        )
        for g, shape in enumerate(groups)
    ]
    planned = sum(_outside(b.shape, base) for b in bodies) / 1e6
    # a proxy is named by its place in the polished layout; the ledger by its place in the seed
    proxies = []
    for p in fins.ribs(sub, numbers, where, metals, chords=2)[0]:
        found = re.search(r":fin:(\d+)", str(p.id))
        if found is not None:
            proxies.append(dataclasses.replace(p, id=ids[kept[int(found.group(1))]]))
    proxies = [p for p in proxies if p.id in set(built)]
    pattern = patterns.Pattern(
        ribs=[(p.id, fins.THICKNESS_MM) for p in proxies],
        score=polished.score,
        metal_L=float(planned),
    )
    rec = designs._Design(d)
    rec.record["pattern"] = pattern.summary()
    rec.save()
    campaign.realise(
        project,
        extraction,
        deck,
        d,
        pattern,
        {p.id: p for p in proxies},
        say,
        lock if lock is not None else nullcontext(),
        bodies=grouped,
        small_faces="report",
    )
    solved = (designs._Design(d).record.get("solve") or {}).get("headline") or {}
    theirs = held.get("headline") or {}
    if solved:
        say(
            f"on the mesh: largest {solved.get('largest_displacement_mm', 0):.3f} mm, "
            f"+{solved.get('added_kg', 0):.1f} kg; the target "
            f"{theirs.get('largest_displacement_mm', 0):.3f} mm, "
            f"+{theirs.get('added_kg', 0):.1f} kg"
        )


def _outside(shape: Any, base: Any) -> float:
    """How much of a rib's solid is new metal: what of it stands outside the part."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut

    cut = BRepAlgoAPI_Cut(shape, base)
    cut.Build()
    return float(cad._volume(cut.Shape()) if cut.IsDone() else cad._volume(shape))
