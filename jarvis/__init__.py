"""Jarvis — a local-first AI assistant for phone and computer.

The package exposes a small, stable surface:

* :class:`jarvis.config.Settings` — typed configuration loaded from env / .env.
* :class:`jarvis.core.orchestrator.Orchestrator` — the agent loop.
* :func:`jarvis.server.app.create_app` — FastAPI application factory.

Everything else is an implementation detail that may move between versions.
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__ = ["__version__"]
