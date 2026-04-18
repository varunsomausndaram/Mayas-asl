"""Health and root endpoints — intentionally unauthenticated."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from jarvis import __version__
from jarvis.server.auth import require_api_key
from jarvis.server.deps import get_runtime

router = APIRouter()


@router.get("/healthz")
async def healthz(request: Request) -> dict:
    runtime = getattr(request.app.state, "runtime", None)
    llm_ok = False
    if runtime is not None:
        try:
            llm_ok = await runtime.orchestrator.llm.health()
        except Exception:
            llm_ok = False
    return {
        "ok": True,
        "version": __version__,
        "llm_ok": llm_ok,
    }


@router.get("/v1/runtime/info", dependencies=[Depends(require_api_key)])
async def runtime_info(request: Request) -> dict:
    runtime = get_runtime(request)
    tools = [s.name for s in runtime.orchestrator.registry.schemas()]
    profile = await runtime.profile_store.load()
    return {
        "version": __version__,
        "llm": {"provider": runtime.orchestrator.llm.name, "model": runtime.orchestrator.llm.model},
        "tools": tools,
        "persona": {
            "name": runtime.persona.name,
            "address": runtime.persona.address,
            "humor_level": runtime.persona.humor_level,
            "verbosity": runtime.persona.verbosity,
        },
        "profile": profile.to_json(),
    }
