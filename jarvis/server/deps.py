"""Shared FastAPI dependencies — accessors for the runtime.

The runtime is attached to ``app.state.runtime`` during ``lifespan`` and
retrieved here so route handlers don't need to reach into ``Request``.
"""

from __future__ import annotations

from fastapi import Request

from jarvis.core.factory import JarvisRuntime


def get_runtime(request: Request) -> JarvisRuntime:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise RuntimeError("Jarvis runtime not initialised")
    return runtime
