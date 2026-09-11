"""The agent: a language model with tools over the platform, which turns what an engineer asks
for into a spec and designs made from it.

Credentials come from the environment. A ``.env`` at the repository root is read first, before
anything from LangChain is imported, so tracing and keys are set when those libraries look.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)
