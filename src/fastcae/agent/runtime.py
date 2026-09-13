"""The agent runtime: LangChain's agent loop on a SQLite checkpointer, streamed as events.

**The model** comes from ``FASTCAE_AGENT_MODEL``, as ``provider:model``. ``openrouter:`` is not a
provider LangChain knows: it is rewritten to ``openai:`` with the base URL pointed at OpenRouter
and the key from ``OPENROUTER_API_KEY`` - without that the key falls back to ``OPENAI_API_KEY``
and every call is refused. OpenRouter speaks chat completions, not the Responses API, so that
stays off. Reasoning effort and a pinned upstream provider ride in the request body.

**The conversation** is kept with the project, in SQLite under ``.fastcae/agent/``, one thread at a
time. What the engineer typed is also kept as text, because a study may quote only that.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from ..extract import Extraction
from ..project import Project
from . import tools as agent_tools
from .prompt import SYSTEM

MODEL = "openrouter:deepseek/deepseek-v4-pro"
RECURSION_LIMIT = 60

# What the engineer can say a selection is for, and how it reads to the agent.
ROLES = {
    "auto": "",
    "host": " as where ribs stand",
    "supports": " as what ribs run between",
    "keep_out": " as what ribs keep clear of",
}


def model_name() -> str:
    return os.environ.get("FASTCAE_AGENT_MODEL", MODEL).strip() or MODEL


def key_var(name: str) -> str | None:
    provider = name.split(":", 1)[0]
    return {"openrouter": "OPENROUTER_API_KEY", "openai": "OPENAI_API_KEY", "fake": None}.get(
        provider, f"{provider.upper()}_API_KEY"
    )


def make_model(name: str | None = None):
    """The chat model for ``provider:model``. See the module note."""
    from langchain.chat_models import init_chat_model

    name = name or model_name()
    kwargs: dict[str, Any] = {}
    target = name
    if name.startswith("openrouter:"):
        target = "openai:" + name.split(":", 1)[1]
        kwargs["base_url"] = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        kwargs["api_key"] = os.environ.get("OPENROUTER_API_KEY", "")
        kwargs["use_responses_api"] = False
        body: dict[str, Any] = {}
        effort = os.environ.get("FASTCAE_AGENT_EFFORT", "high").strip()
        if effort and effort != "off":
            body["reasoning"] = {"effort": effort}
        provider = os.environ.get("FASTCAE_OR_PROVIDER", "").strip()
        if provider:
            body["provider"] = {
                "order": [provider],
                "allow_fallbacks": os.environ.get("FASTCAE_OR_FALLBACKS", "0").strip() == "1",
            }
        if body:
            kwargs["extra_body"] = body
    return init_chat_model(target, **kwargs)


def status() -> dict:
    """Which model, whether its key is present, whether tracing is on - never the key itself."""
    name = model_name()
    var = key_var(name)
    tracing_asked = os.environ.get("LANGSMITH_TRACING", "").lower() == "true"
    return {
        "model": name,
        "key_var": var,
        "key_present": bool(var is None or os.environ.get(var)),
        "tracing": tracing_asked and bool(os.environ.get("LANGSMITH_API_KEY")),
        "tracing_project": os.environ.get("LANGSMITH_PROJECT", ""),
    }


class Runtime:
    """One project's agent: its tools, its conversation, its checkpointer."""

    def __init__(
        self,
        project: Project,
        extraction: Extraction,
        model: Any = None,
        context: agent_tools.Context | None = None,
    ):
        from langchain.agents import create_agent
        from langgraph.checkpoint.sqlite import SqliteSaver

        self.project = project
        self.folder = project.root / ".fastcae" / "agent"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.thread = self._thread()
        self.context = context or agent_tools.Context(project, extraction, said=[])
        self.context.said[:] = self._said()
        self.context.selections[:] = self._selections()
        self.connection = sqlite3.connect(
            self.folder / "checkpoints.sqlite", check_same_thread=False
        )
        self.saver = SqliteSaver(self.connection)
        self.agent = create_agent(
            model if model is not None else make_model(),
            agent_tools.build(self.context),
            system_prompt=SYSTEM,
            checkpointer=self.saver,
        )

    # --- the thread -----------------------------------------------------------------------------

    def _thread(self) -> str:
        path = self.folder / "thread.txt"
        return path.read_text(encoding="utf-8").strip() if path.is_file() else "1"

    def _said_path(self) -> Path:
        return self.folder / f"said-{self.thread}.json"

    def _said(self) -> list[str]:
        path = self._said_path()
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []

    def _selections_path(self) -> Path:
        return self.folder / f"selected-{self.thread}.json"

    def _selections(self) -> list[list[int]]:
        path = self._selections_path()
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []

    def remember_said(self) -> None:
        """Keep what the engineer has said and typed, for this thread."""
        self._said_path().write_text(json.dumps(self.context.said, indent=1), encoding="utf-8")

    def new_thread(self) -> None:
        self.thread = str(int(self.thread) + 1 if self.thread.isdigit() else 1)
        (self.folder / "thread.txt").write_text(self.thread, encoding="utf-8")
        self.context.said[:] = []
        self.context.selections[:] = []

    def config(self) -> dict:
        return {
            "configurable": {"thread_id": self.thread},
            "recursion_limit": RECURSION_LIMIT,
            "run_name": "fastcae agent",
            "tags": ["fastcae", self.project.name],
            "metadata": {"project": self.project.name, "thread": self.thread},
        }

    def history(self) -> list[dict]:
        """The conversation so far, as the pane shows it."""
        state = self.agent.get_state(self.config())
        out = []
        for message in (state.values or {}).get("messages", []):
            if isinstance(message, HumanMessage):
                out.append({"role": "engineer", "text": _text(message)})
            elif isinstance(message, AIMessage):
                text = _text(message)
                if text:
                    out.append({"role": "agent", "text": text})
                for call in message.tool_calls or []:
                    out.append({"role": "tool", "name": call["name"], "args": call.get("args", {})})
            elif isinstance(message, ToolMessage):
                filled = _draft(message)
                if filled is not None:
                    out.append({"role": "draft", **filled})
        return out

    # --- a turn ---------------------------------------------------------------------------------

    def turn(
        self, message: str, selection: list[int] | None = None, role: str = "auto"
    ) -> Iterator[dict]:
        """Send one message - with the faces selected on the part, if any, and what the engineer
        said they are for - and yield what happens: text as it comes, tools as they run, the card
        as it is filled. The selection goes to the agent with the words; only the agent puts it
        on the card, so a question about a face changes nothing."""
        self.context.said.append(message)
        self._said_path().write_text(json.dumps(self.context.said, indent=1), encoding="utf-8")
        self.context.questions = 0
        text = message
        if selection:
            chosen = sorted({int(f) for f in selection})
            self.context.selections.append(chosen)
            self._selections_path().write_text(
                json.dumps(self.context.selections), encoding="utf-8"
            )
            what = ROLES.get(role, ROLES["auto"])
            text += (
                f"\n\n(selected on the part{what}: " + ", ".join(f"face:{f}" for f in chosen) + ")"
            )
        self.context.changed.clear()
        streamed = False
        try:
            for mode, chunk in self.agent.stream(
                {"messages": [HumanMessage(text)]},
                self.config(),
                stream_mode=["messages", "updates"],
            ):
                if mode == "messages":
                    piece, _ = chunk
                    if isinstance(piece, AIMessageChunk):
                        text = _text(piece)
                        if text:
                            streamed = True
                            yield {"type": "token", "text": text}
                    continue
                for update in (chunk or {}).values():
                    for m in (update or {}).get("messages", []) if isinstance(update, dict) else []:
                        if isinstance(m, AIMessage):
                            if not streamed and _text(m):
                                yield {"type": "token", "text": _text(m)}
                            for call in m.tool_calls or []:
                                yield {
                                    "type": "tool_start",
                                    "id": call.get("id"),
                                    "name": call["name"],
                                    "args": call.get("args", {}),
                                }
                            streamed = False
                        elif isinstance(m, ToolMessage):
                            filled = _draft(m)
                            if filled is not None:
                                yield {"type": "draft", **filled}
                            yield {
                                "type": "tool_result",
                                "id": m.tool_call_id,
                                "name": m.name,
                                "summary": _summary(m),
                            }
        except Exception as error:  # noqa: BLE001 - the pane has to say what went wrong
            yield {"type": "error", "message": f"{type(error).__name__}: {error}"}
        yield {"type": "changed", "what": sorted(self.context.changed)}
        yield {"type": "done"}


def _text(message: Any) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )
    return ""


def _draft(message: ToolMessage) -> dict | None:
    """The study, changed by the agent and let through by the checks: what the pane says of it -
    only what the agent asked the engineer to look at. The variant card shows the rest."""
    if message.name != "edit_study":
        return None
    try:
        data = json.loads(_text(message))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or "refused" in data:
        return None
    needed = [f"{b['id']}: {n}" for b in data.get("blocks", []) for n in b.get("needed", [])]
    return {"attention": list(data.get("attention", [])), "needed": needed}


def _summary(message: ToolMessage) -> str:
    """A few words about a tool's result, for the pane - never the result itself."""
    try:
        data = json.loads(_text(message))
    except (ValueError, TypeError):
        return _text(message)[:120]
    if isinstance(data, dict) and "answer" in data and "note" in data:
        data = data["answer"]
    if isinstance(data, list):
        return f"{len(data)} described"
    if not isinstance(data, dict):
        return str(data)[:120]
    for key in ("refused", "error"):
        if key in data:
            return f"{key}: {data[key]}"[:240]
    if "accepted_version" in data:
        if data.get("cannot"):
            return f"the study cannot be written: {data['cannot']}"[:240]
        placed = data.get("where_ribs_go")
        if isinstance(placed, dict) and placed:
            return "ribs at the suggested point - " + "; ".join(
                f"{block}: {found['ribs']}" for block, found in placed.items()
            )
        changes = len(data.get("changes", []))
        return f"the study: {changes} changes" if changes else "the study, as accepted"
    if "entities" in data:
        return f"{len(data['entities'])} described"
    if "axes" in data:
        return f"{len(data['axes'])} axes"
    if "found" in data:
        return f"{data.get('total', len(data['found']))} found"
    if "round" in data and "floor" in data:
        return f"{len(data['round'])} things rise round {', '.join(data['floor'])}"
    if "between" in data:
        return f"between {', '.join(data['between'])}: {data.get('says', '')}"[:240]
    if isinstance(data, dict) and all(isinstance(v, dict) and "across" in v for v in data.values()):
        return "; ".join(
            f"across from {ref}: {v['across'][0]['ref']}" if v["across"] else f"{ref}: open"
            for ref, v in data.items()
        )[:240]
    if "low_mm" in data:
        return f"{data['low_mm']} to {data['high_mm']} mm"
    if "metal_under_it_mm" in data:
        return f"{data['metal_under_it_mm']} mm of metal"
    if "total" in data:
        return f"{data['total']} found"
    return "done"
