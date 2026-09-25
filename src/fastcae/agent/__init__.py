"""The agent: a language model with tools over the pipeline and the part, which helps an engineer
read what fastcae made of their files and settle, in their own words, what it could not.

Credentials come from the environment. A ``.env`` at the repository root is read first, before
anything from LangChain is imported, so tracing and keys are set when those libraries look.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)
