"""LLM providers and router.

Use :func:`build_provider` to construct the default provider from
:class:`jarvis.config.Settings`. Providers speak a small common dialect
defined in :mod:`jarvis.llm.base` — the router can then swap implementations
without callers needing to know.
"""

from jarvis.llm.base import ChatMessage, ChatResult, LLMProvider, ToolSchema
from jarvis.llm.router import build_provider

__all__ = ["ChatMessage", "ChatResult", "LLMProvider", "ToolSchema", "build_provider"]
