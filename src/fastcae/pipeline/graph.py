"""The pipeline as one graph: its steps in two stages, every entity they produced, and every link
between entities read both ways.

Built from what the server already holds - the extraction and the derived design space - so asking
for it never recomputes anything. The rail, the canvases and the agent all read this one graph.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import TypeAdapter

from ..space.model import Space
from .entities import AnyEntity, Entity, Link, Stage
from .read import read_stage
from .space import space_stage

ENTITY_SCHEMA = TypeAdapter(AnyEntity)


class Graph:
    def __init__(self, stages: list[Stage], entities: list[Entity]) -> None:
        self.stages = stages
        self.entities: dict[str, Entity] = {e.id: e for e in entities}
        self.backlinks: dict[str, list[Link]] = defaultdict(list)
        for e in entities:
            for link in e.links:
                self.backlinks[link.to].append(Link(to=e.id, role=link.role))

    def pipeline(self) -> dict[str, Any]:
        return {"stages": [s.model_dump(mode="json") for s in self.stages]}

    def summary(self, e: Entity) -> dict[str, Any]:
        return {
            "id": e.id,
            "kind": e.kind,
            "label": e.label,
            "step": e.step,
            "origin": e.origin,
            "status": e.status,
            "show": e.show.model_dump(mode="json"),
        }

    def entity(self, entity_id: str) -> dict[str, Any] | None:
        """One entity in full, with the entities that link to it, each named in a few words."""
        e = self.entities.get(entity_id)
        if e is None:
            return None
        out = e.model_dump(mode="json")
        out["backlinks"] = [
            {
                "from": link.to,
                "role": link.role,
                "label": self.entities[link.to].label,
                "kind": self.entities[link.to].kind,
            }
            for link in self.backlinks.get(entity_id, [])
            if link.to in self.entities
        ]
        out["links"] = [
            {
                **link.model_dump(),
                "label": self.entities[link.to].label if link.to in self.entities else link.to,
                "kind": self.entities[link.to].kind if link.to in self.entities else "",
            }
            for link in e.links
        ]
        return out

    def find(
        self,
        kind: str | None = None,
        step: str | None = None,
        ids: list[str] | None = None,
        text: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> dict[str, Any]:
        pool = (
            [self.entities[i] for i in ids if i in self.entities]
            if ids
            else list(self.entities.values())
        )
        if kind:
            pool = [e for e in pool if e.kind == kind]
        if step:
            pool = [e for e in pool if e.step == step]
        if text:
            needle = text.lower()
            pool = [e for e in pool if needle in e.label.lower() or needle in e.id.lower()]
        return {
            "total": len(pool),
            "entities": [self.summary(e) for e in pool[offset : offset + limit]],
        }


def build(  # type: ignore[no-untyped-def]
    extraction,
    space: Space | None,
    answers: dict[str, str] | None = None,
    live: dict | None = None,
    running: bool = False,
) -> Graph:
    """The graph of what the server holds: the extraction's entities, and the design space's -
    unless a run is replacing it, when only what the run has reported so far is shown."""
    read_steps, read_entities = read_stage(extraction)
    space_steps, space_entities = space_stage(space, read_entities, answers, live, running)
    stages = [
        Stage(id="read", label="Read the engineer's files", steps=read_steps),
        Stage(id="space", label="Derive the design space", steps=space_steps),
    ]
    return Graph(stages, read_entities + space_entities)


def schema() -> dict[str, Any]:
    """Every entity kind's fields, as JSON Schema: what an agent can expect to read."""
    return ENTITY_SCHEMA.json_schema()
