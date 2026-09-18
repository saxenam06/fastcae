"""Campaigns: many designs from the variants chosen, each a random set of them.

A campaign is a card - its name, the variants it takes, the screening checks it holds, how designs
are drawn, how many to keep, from which seed, and whether to draw more and keep the most
different - and nothing else decides its designs.

**Composed once.** The variants chosen become one study version: their blocks as they are, each
variant's rules on its own block, the part's interfaces once, and the rules that hold between
variants without anyone writing them - holes keep their ligament from every variant's ribs; ribs
of two variants keep the root gap, which placing and repair see to. A rule naming a variant the
campaign does not take is left out.

**Each variant alone first.** Points of what it allows - spread evenly, at random, or every one -
each placed with nothing else, repaired and screened: the ones that pass are its pool, and a
variant none of whose points passes stops the campaign, saying why.

**Then designs.** A set of the variants - as many designs with one of them as with two, three or
all - and a point of each from its pool, by the method; placed together, repaired, screened. A
design repair cannot save is drawn again; designs alike in every rib, pad, hole and face moved
are kept once; ``n`` are kept of at most ``4n + 100`` tried. Asked to, ``k·n`` are kept and the
``n`` farthest apart chosen.

**Kept whole**, a folder per launch beside the project's other runs: the card, the part's digest,
the code's commit, a copy of every variant as it was, the seed and the method; each design's
variants, values, recipe and its hash, its own seed, what repair left out, how it screened, and
its paths; how many were tried and why the rest were not kept, how each lever spread, how many
distinct rib layouts, how far each design sits from its nearest neighbour.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
import re
import secrets
import string
import subprocess
import time
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, Field

from .. import study as studies
from .. import variants
from ..project import Project
from . import session as sessions
from .intent import IntentError
from .screen import measure_walls
from .variety import layouts, most_varied, plane_of, separation

# How designs are drawn: spread evenly (a scrambled Sobol sequence), at random, or every one.
METHODS = ("even", "random", "every")
# How many designs a campaign tries, at most, for each it is asked to keep.
TRIES_PER_DESIGN = 4
# How many points of each variant a campaign keeps to draw designs from - a quarter as many as
# the designs asked for, within these - and how many it tries for each it keeps, at most.
POOL = (32, 1024)
POOL_TRIES = 4
# How many designs Screen tries, and how many points of each variant it pools for them.
SCREENED = 100
SCREEN_POOL = 8


class Card(BaseModel):
    """What a campaign is: everything that decides its designs."""

    name: str = ""
    variants: list[str] = Field(default_factory=list)
    checks_off: list[str] = Field(default_factory=list)
    """Screening checks this campaign does not hold its designs to, by name."""
    method: Literal["even", "random", "every"] = "even"
    n: int = Field(default=20, ge=1, le=20000)
    seed: int = 0
    diverse: int = Field(default=0, ge=0, le=10)
    """0: keep designs as drawn; ``k`` of 2 or more: keep ``k`` times ``n``, then the ``n`` that
    differ most."""


# What a campaign's name calls each kind of variant, when it has no name of its own.
KIND_WORDS = {"thicken": "faces moved"}


def default_name(found: list[studies.Study]) -> str:
    """A campaign's name when the card gives none: what its variants add, counted - a few words
    a list can show, never every variant's label strung together."""
    counts = Counter(variants.kind_of(v.current.blocks[0]) for v in found)
    return " · ".join(
        f"{KIND_WORDS.get(kind, kind)} ×{n}" if n > 1 else KIND_WORDS.get(kind, kind)
        for kind, n in counts.items()
    )


# --- composing ------------------------------------------------------------------------------------


def chosen(project: Project, ids: list[str]) -> list[studies.Study] | str:
    """The variants a card names, as kept - or why a campaign cannot be made of them."""
    if not ids:
        return "choose at least one variant"
    found = []
    for vid in dict.fromkeys(ids):
        variant = variants.load(project, vid)
        if variant is None or not variant.current.blocks:
            return f"there is no variant {vid}"
        found.append(variant)
    return found


def compose(chosen_variants: list[studies.Study], card: Card) -> studies.StudyVersion:
    """One study version of the variants chosen - see the module note."""
    ids = {v.name for v in chosen_variants}
    blocks: list[studies.Block] = []
    rules: list[studies.Constraint] = []
    interfaces: list[studies.Constraint] = []
    fingerprints: dict[str, dict[str, Any]] = {}
    measured = []
    for variant in chosen_variants:
        version = variant.current
        block = version.blocks[0].model_copy(deep=True)
        blocks.append(block)
        for rule in version.constraints:
            if rule.by == "platform":
                if not any(_alike(rule, kept) for kept in interfaces):
                    interfaces.append(rule)
                continue
            named = [r for r in rule.refs if studies.made_by(r) in (None, *ids)]
            if rule.refs and not named:
                continue
            rules.append(
                rule.model_copy(
                    update={"id": f"{block.id}-{rule.id}", "block": block.id, "refs": named}
                )
            )
        fingerprints.update(version.fingerprints)
        measured += version.measured
    rules += _between(blocks, rules)
    rules += [rule.model_copy(update={"id": f"i{n}"}) for n, rule in enumerate(interfaces, 1)]
    return studies.StudyVersion(
        version=1,
        created=datetime.now(UTC).isoformat(timespec="seconds"),
        words=[],
        blocks=blocks,
        constraints=rules,
        fingerprints=fingerprints,
        measured=measured,
        target=studies.Target(n=card.n, seed=card.seed),
    )


def _alike(a: studies.Constraint, b: studies.Constraint) -> bool:
    return (a.kind, sorted(a.refs), a.params) == (b.kind, sorted(b.refs), b.params)


def _between(blocks: list[studies.Block], rules: list[studies.Constraint]) -> list:
    """The rules that hold between variants without anyone writing them: holes keep their ligament
    from the ribs of every variant of ribs - placed after them, so holes go where ribs leave
    room - unless the holes' variant already says how far."""
    ribs = [b.id for b in blocks if b.add == "ribs"]
    out = []
    for block in blocks:
        if block.add != "holes" or not ribs:
            continue
        said = {
            ref
            for rule in rules
            if rule.block == block.id and rule.kind == "keep_clear_of"
            for ref in rule.refs
        }
        others = [r for r in ribs if f"{studies.RIBS}{r}" not in said]
        ligament = block.free.get("ligament_mm")
        clearance = None
        if ligament is not None:
            clearance = ligament.suggested if ligament.suggested is not None else ligament.low
        if not others or clearance is None:
            continue
        out.append(
            studies.Constraint(
                id=f"{block.id}-between",
                kind="keep_clear_of",
                refs=[f"{studies.RIBS}{r}" for r in others],
                params={"clearance_mm": float(clearance)},
                block=block.id,
                strength="assumed",
                by="part",
                basis="a hole keeps a ligament of metal from any rib, as from another hole",
            )
        )
    return out


def count(chosen_variants: list[studies.Study]) -> int | None:
    """How many designs the variants chosen allow: every non-empty set of them, at every point of
    each - ``Π(1 + c) − 1``. None when one of them has no end - free layouts."""
    total = 1
    for variant in chosen_variants:
        each = studies.combinations(variant.current.blocks[0])
        if each is None:
            return None
        total *= 1 + each
    return total - 1


def estimate(project: Project, card: Card) -> dict[str, Any]:
    """What a card would make, before anything is placed: how many designs its variants allow,
    each variant's share, and whether every one of them can be asked for."""
    found = chosen(project, card.variants)
    if isinstance(found, str):
        return {"cannot": found}
    total = count(found)
    return {
        "count": total,
        "variants": [
            {
                "id": v.name,
                "label": v.label or variants.suggested_label(v.current.blocks[0]),
                "combinations": studies.combinations(v.current.blocks[0]),
            }
            for v in found
        ],
        "every": total is not None and total <= card.n,
    }


# --- drawing designs ------------------------------------------------------------------------------


def points_of(block: studies.Block) -> Iterator[dict[str, Any]]:
    """Every point a block allows, each once: for each pattern and section, every value of each
    setting that makes a difference to it."""
    decided = [n for n in ("generator", "section") if n in block.free]
    for picked in studies._every(block, decided):
        used = studies.effective(block, picked)
        names = [
            n
            for n, d in sorted(block.free.items())
            if n in used and n not in decided and not d.fixed
        ]
        fixed = {n: v for n, v in picked.items() if not block.free[n].fixed}
        for values in itertools.product(*(studies.values_of(block.free[n]) for n in names)):
            yield {**fixed, **dict(zip(names, values, strict=True))}


def _candidates(
    version: studies.StudyVersion, block: studies.Block, method: str, seed: int
) -> Iterator[dict[str, Any]]:
    """Points of one block to try alone, in order: its suggested point first, then spread evenly,
    at random, or every point it allows."""
    if method == "every":
        yield from points_of(block)
        return
    yield {}
    if method == "random":
        draw = random.Random(seed)
        while True:
            yield sessions.random_point(block, draw)
    for values in studies.spread(version, seed, blocks=[block.id]):
        if values[block.id]:
            yield values[block.id]


def _draws(
    card: Card, ids: list[str], pools: dict[str, list[dict[str, Any]]]
) -> Iterator[dict[str, dict[str, Any]]]:
    """Designs to try: a set of the variants and a pool point of each. Every one of them in turn,
    for every combination; else the set's size spread evenly over one to all, which set of that
    size and which point of each drawn by the method."""
    m = len(ids)
    if card.method == "every":
        for size in range(1, m + 1):
            for subset in itertools.combinations(ids, size):
                for combo in itertools.product(*(pools[b] for b in subset)):
                    yield dict(zip(subset, combo, strict=True))
        return
    subsets = {k: list(itertools.combinations(ids, k)) for k in range(1, m + 1)}
    if card.method == "even":
        from scipy.stats import qmc

        engine = qmc.Sobol(d=2 + m, scramble=True, seed=card.seed)

        def rows():
            while True:
                yield from engine.random(1024)
    else:
        draw = np.random.default_rng(card.seed)

        def rows():
            while True:
                yield from draw.random((1024, 2 + m))

    for row in rows():
        size = 1 + min(int(row[0] * m), m - 1)
        options = subsets[size]
        subset = options[min(int(row[1] * len(options)), len(options) - 1)]
        yield {
            b: pools[b][min(int(row[2 + ids.index(b)] * len(pools[b])), len(pools[b]) - 1)]
            for b in subset
        }


# --- running --------------------------------------------------------------------------------------


class _Prepared:
    """What every design of a campaign is placed with: its version, the grid, the walls moved."""

    def __init__(self, session: sessions.Session, version: studies.StudyVersion):
        self.version = version
        first = sessions._pieces(version)
        self.cannot = first.cannot
        self.any = first.any()
        self.radius = first.radius()
        self.opened = None
        self.walls: dict[str, float | None] = {}
        if self.any:
            self.opened = sessions._opened(
                session, sessions._spec_of(version, first), "preview", self.radius
            )
            self.walls = measure_walls(
                session.extraction, sessions._measure(session).exit_along, first.offsets
            )


def _pool(
    session: sessions.Session,
    prepared: _Prepared,
    block: studies.Block,
    card: Card,
    most: int | None,
    off: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The points of one variant that place and pass alone - at most ``most``, or all of them -
    and how many were tried and why the rest were not kept."""
    pool: list[dict[str, Any]] = []
    effective: set[str] = set()
    why: Counter[str] = Counter()
    tried = drawn = 0
    ceiling = None if most is None else most * POOL_TRIES
    for values in _candidates(prepared.version, block, card.method, card.seed):
        if (most is not None and len(pool) >= most) or (ceiling is not None and tried >= ceiling):
            break
        # A variant that allows few points gives the same ones again and again: past this many
        # draws, it has given what it has.
        drawn += 1
        if ceiling is not None and drawn > 8 * ceiling:
            break
        same = json.dumps(studies.effective(block, values), sort_keys=True, default=str)
        if same in effective:
            continue
        tried += 1
        outcome = sessions._tried(
            session, prepared.version, {block.id: values}, prepared.radius, prepared.walls, off
        )
        if isinstance(outcome, str):
            why[outcome] += 1
            continue
        _, _, screened = outcome
        if screened.outcome == "reject":
            why.update(f["check"] for f in screened.rejected())
            continue
        effective.add(same)
        pool.append(values)
    return pool, {"kept": len(pool), "tried": tried, "rejected": dict(why)}


def screen_sample(session: sessions.Session, card: Card, size: int = SCREENED) -> dict[str, Any]:
    """``size`` designs drawn as the campaign would draw them, placed, repaired and screened -
    nothing kept: how many pass, how many needed repair, why the rest do not, and how long a
    design takes, so how long the launch will."""
    found = chosen(session.project, card.variants)
    if isinstance(found, str):
        return {"cannot": found}
    version = compose(found, card)
    try:
        prepared = _Prepared(session, version)
    except IntentError as error:
        return {"cannot": str(error)}
    if not prepared.any:
        return {"cannot": "; ".join(prepared.cannot) or "nothing can be placed yet"}
    off = set(card.checks_off)
    started = time.perf_counter()
    pools: dict[str, list[dict[str, Any]]] = {}
    alone: dict[str, dict[str, Any]] = {}
    for block in version.blocks:
        pools[block.id], alone[block.id] = _pool(session, prepared, block, card, SCREEN_POOL, off)
        if not pools[block.id]:
            return {"cannot": _nothing_alone(block.id, alone[block.id]), "alone": alone}
    pooled = time.perf_counter() - started
    passed = repaired = tried = 0
    why: Counter[str] = Counter()
    started = time.perf_counter()
    for values in itertools.islice(_draws(card, list(pools), pools), size):
        tried += 1
        outcome = sessions._tried(session, version, values, prepared.radius, prepared.walls, off)
        if isinstance(outcome, str):
            why[outcome] += 1
            continue
        _, mended, screened = outcome
        if screened.outcome == "reject":
            why.update(f["check"] for f in screened.rejected())
            continue
        passed += 1
        repaired += bool(mended.repaired)
    each = (time.perf_counter() - started) / max(tried, 1)
    per_alone = pooled / max(sum(a["tried"] for a in alone.values()), 1)
    most = min(max(POOL[0], card.n // 4), POOL[1])
    alone_tries = sum(most * a["tried"] / max(a["kept"], 1) for a in alone.values())
    design_tries = card.n * max(card.diverse, 1) * tried / max(passed, 1)
    return {
        "tried": tried,
        "passed": passed,
        "repaired": repaired,
        "rejected": dict(why),
        "alone": alone,
        "seconds_per_design": round(each, 3),
        "estimate_seconds": round(alone_tries * per_alone + design_tries * each, 1),
    }


def _nothing_alone(block: str, alone: dict[str, Any]) -> str:
    reasons = ", ".join(f"{k} {v}" for k, v in Counter(alone["rejected"]).most_common(3))
    return (
        f"variant {block} makes nothing at any of the {alone['tried']} points tried alone "
        f"({reasons}) - change where it stands or what it may take"
    )


def go(session: sessions.Session, card: Card) -> Iterator[dict[str, Any]]:
    """A campaign launched: see the module note. Events as it goes - ``started``, a ``variant``
    as each is pooled alone, ``design`` as each is kept, ``progress``, then ``done`` or
    ``error``."""
    found = chosen(session.project, card.variants)
    if isinstance(found, str):
        yield {"type": "error", "message": found}
        return
    total = count(found)
    if card.method == "every" and (total is None or total > card.n):
        yield {
            "type": "error",
            "message": "every combination is for a campaign asked for at least as many designs "
            f"as its variants allow ({'no end' if total is None else total})",
        }
        return
    version = compose(found, card)
    try:
        prepared = _Prepared(session, version)
    except IntentError as error:
        yield {"type": "error", "message": str(error)}
        return
    if not prepared.any:
        yield {"type": "error", "message": "; ".join(prepared.cannot) or "nothing can be placed"}
        return
    project = session.project
    extraction = session.extraction
    cid = _new_id(project)
    name = card.name.strip() or default_name(found)
    folder = sessions.archive_root(project) / f"{cid}-{_slug(name)}"
    folder.mkdir(parents=True, exist_ok=True)
    kept_as = {
        v.name: {
            "id": v.name,
            "label": v.label or variants.suggested_label(v.current.blocks[0]),
            "kind": variants.kind_of(v.current.blocks[0]),
            "version": v.current.version,
            "combinations": studies.combinations(v.current.blocks[0]),
        }
        for v in found
    }
    manifest = {
        "id": cid,
        "name": name,
        "card": card.model_dump(),
        "variants": list(kept_as.values()),
        "copies": {v.name: v.current.model_dump() for v in found},
        "part": extraction.cad_digest,
        "code": _commit(),
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "count": total,
        "study": "campaign",
        "version": 1,
        "seed": card.seed,
        "off": {"checks": list(card.checks_off)},
    }
    (folder / "campaign.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    (folder / "study.json").write_text(version.model_dump_json(indent=1), encoding="utf-8")
    where = f"{sessions.ARCHIVE_DIR}/{project.name}/{folder.name}"
    session.loaded = {}
    started = time.perf_counter()
    off = set(card.checks_off)
    diverse = card.diverse if card.diverse >= 2 else 1
    target = card.n * diverse
    yield {
        "type": "started",
        "run": folder.name,
        "id": cid,
        "name": name,
        "n": card.n,
        "count": total,
        "archive": where,
        "waiting": prepared.cannot,
    }

    # Each variant alone.
    most = None if card.method == "every" else min(max(POOL[0], card.n // 4), POOL[1])
    pools: dict[str, list[dict[str, Any]]] = {}
    alone: dict[str, dict[str, Any]] = {}
    for block in version.blocks:
        pools[block.id], alone[block.id] = _pool(session, prepared, block, card, most, off)
        yield {"type": "variant", "variant": block.id, "label": kept_as[block.id]["label"],
               **alone[block.id]}  # fmt: skip
        if not pools[block.id]:
            yield {"type": "error", "message": _nothing_alone(block.id, alone[block.id])}
            return

    # Designs.
    budget = TRIES_PER_DESIGN * target + 100
    designs: list[dict[str, Any]] = []
    seen: set[str] = set()
    rejected: Counter[str] = Counter()
    tried = repaired = 0

    def progress() -> dict[str, Any]:
        return {
            "type": "progress",
            "tried": tried,
            "made": len(designs),
            "repaired": repaired,
            "rejected": dict(rejected),
            "seconds": round(time.perf_counter() - started, 1),
        }

    streaming = diverse == 1
    archive = (folder / "designs.jsonl").open("w", encoding="utf-8") if streaming else None
    paths = (folder / sessions.PATHS).open("w", encoding="utf-8") if streaming else None
    try:
        for values in _draws(card, list(pools), pools):
            if len(designs) >= target or tried >= budget:
                break
            tried += 1
            outcome = sessions._tried(
                session, version, values, prepared.radius, prepared.walls, off
            )
            if isinstance(outcome, str):
                rejected["cannot be placed"] += 1
                continue
            pieces, mended, screened = outcome
            if screened.outcome == "reject":
                rejected.update(f["check"] for f in screened.rejected())
                if tried % 25 == 0:
                    yield progress()
                continue
            key = sessions._key(pieces, mended.placed)
            if key in seen:
                rejected["alike"] += 1
                continue
            seen.add(key)
            design = sessions._design(
                len(designs), version, values, pieces, mended.placed, screened
            )
            design["variants"] = [b.id for b in version.blocks if b.id in values]
            design["left_out"] = mended.left_out
            repaired += bool(mended.repaired)
            _stamp(design, cid, extraction.cad_digest, kept_as)
            designs.append(design)
            if archive is not None and paths is not None:
                archive.write(json.dumps(sessions._archived(design)) + "\n")
                paths.write(json.dumps(sessions._compact(design["lines"])) + "\n")
                archive.flush()
            yield {"type": "design", **sessions._listed(design), "variants": design["variants"]}
            if len(designs) % 25 == 0:
                yield progress()
    finally:
        if archive is not None:
            archive.close()
        if paths is not None:
            paths.close()

    features = extraction.features
    assert features is not None
    axes = plane_of(None)[1:]
    if diverse > 1 and len(designs) > card.n:
        picked = sorted(most_varied(designs, card.n, axes))
        designs = [designs[i] for i in picked]
        for index, design in enumerate(designs):
            design["index"] = index
            _stamp(design, cid, extraction.cad_digest, kept_as)
    if not streaming:
        with (
            (folder / "designs.jsonl").open("w", encoding="utf-8") as archive_file,
            (folder / sessions.PATHS).open("w", encoding="utf-8") as paths_file,
        ):
            for design in designs:
                archive_file.write(json.dumps(sessions._archived(design)) + "\n")
                paths_file.write(json.dumps(sessions._compact(design["lines"])) + "\n")
    summary = {
        "project": project.name,
        "run": folder.name,
        "name": name,
        "study": "campaign",
        "version": 1,
        "asked": card.n,
        "made": len(designs),
        "tried": tried,
        "repaired": repaired,
        "rejected": dict(rejected),
        "alone": alone,
        "seconds": round(time.perf_counter() - started, 1),
        "archive": where,
        "spread": sessions._spread_of(designs),
        "layouts": layouts(designs),
        "separation": separation(designs, axes),
    }
    (folder / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    session.changed.add("designs")
    yield {"type": "done", **{k: v for k, v in summary.items() if k != "spread"}}


def _stamp(design: dict, cid: str, part: str, kept_as: dict[str, dict]) -> None:
    """A design's recipe - the part, each of its variants as it was, the values it took - its hash,
    and its own seed, from the campaign and its place in it."""
    recipe = {
        "part": part,
        "variants": {vid: kept_as[vid]["version"] for vid in design["variants"]},
        "values": design["values"],
    }
    canonical = json.dumps(recipe, sort_keys=True, separators=(",", ":"))
    design["recipe"] = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    design["seed"] = int(hashlib.sha256(f"{cid}:{design['index']}".encode()).hexdigest()[:8], 16)


def campaigns(session: sessions.Session) -> list[dict[str, Any]]:
    """Every campaign launched for the project, newest first: its name, what it took, how many it
    kept of how many tried - and one still running, or stopped, with no summary yet."""
    root = sessions.archive_root(session.project)
    out = []
    for folder in root.iterdir() if root.is_dir() else []:
        manifest = folder / "campaign.json"
        if not manifest.is_file():
            continue
        said = json.loads(manifest.read_text(encoding="utf-8"))
        if "card" not in said:
            continue
        summary = folder / "summary.json"
        done = json.loads(summary.read_text(encoding="utf-8")) if summary.is_file() else None
        out.append(
            {
                "run": folder.name,
                "id": said.get("id"),
                "name": said.get("name"),
                "variants": said.get("variants", []),
                "card": said.get("card", {}),
                "count": said.get("count"),
                "created": said.get("created"),
                "state": "done" if done else "unfinished",
                "made": (done or {}).get("made"),
                "tried": (done or {}).get("tried"),
                "seconds": (done or {}).get("seconds"),
                "built": len(sessions._built(session, folder.name)) if done else 0,
                "when": manifest.stat().st_mtime,
            }
        )
    return sorted(out, key=lambda r: -r["when"])


def _new_id(project: Project) -> str:
    root = sessions.archive_root(project)
    taken = {p.name.split("-", 1)[0] for p in root.iterdir()} if root.is_dir() else set()
    while True:
        cid = secrets.choice(string.ascii_lowercase) + "".join(
            secrets.choice(string.ascii_lowercase + string.digits) for _ in range(4)
        )
        if cid not in taken:
            return cid


def _slug(name: str) -> str:
    """A campaign's name as part of a folder's."""
    words = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return words[:40].rstrip("-") or "campaign"


def _commit() -> str:
    """The code's commit, and whether it had changes not committed - as git says, or unknown."""
    here = Path(__file__).resolve().parent
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=here, capture_output=True, text=True, timeout=10
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=here,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if not head:
        return "unknown"
    return f"{head}{' with changes' if dirty else ''}"
