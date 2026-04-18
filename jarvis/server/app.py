"""FastAPI application factory and ``jarvisd`` entry point."""

from __future__ import annotations

import contextlib
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from jarvis import __version__
from jarvis.config import Settings, get_settings
from jarvis.core.factory import build_runtime
from jarvis.core.permissions import RiskAssessment
from jarvis.errors import JarvisError
from jarvis.logging import configure_logging, get_logger
from jarvis.server.approvals import ApprovalRegistry
from jarvis.server.routes import (
    approvals as approvals_routes,
)
from jarvis.server.routes import (
    audit as audit_routes,
)
from jarvis.server.routes import (
    chat as chat_routes,
)
from jarvis.server.routes import (
    dispatch as dispatch_routes,
)
from jarvis.server.routes import (
    health as health_routes,
)
from jarvis.server.routes import (
    profile as profile_routes,
)
from jarvis.server.routes import (
    scheduler as scheduler_routes,
)
from jarvis.server.routes import (
    voice as voice_routes,
)
from jarvis.server.routes import (
    ws as ws_routes,
)

log = get_logger(__name__)
_WEB_ROOT = Path(__file__).resolve().parent.parent.parent / "web"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory used by ``uvicorn`` and tests."""
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, log_dir=settings.data_dir / "logs")

    app = FastAPI(
        title="Jarvis",
        version=__version__,
        description="Your personal AI assistant.",
        docs_url="/docs",
        redoc_url=None,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(JarvisError)
    async def jarvis_error_handler(_: Request, exc: JarvisError) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status, content=exc.to_dict())

    @app.on_event("startup")
    async def _startup() -> None:  # pragma: no cover - exercised via lifespan
        approvals = ApprovalRegistry()  # bus wired after runtime
        app.state.approvals = approvals

        async def requester(assessment: RiskAssessment):
            return await approvals.request(assessment)

        runtime = await build_runtime(settings, approval_requester=requester)
        approvals.attach_bus(runtime.bus)
        await runtime.start()
        app.state.runtime = runtime
        log.info("jarvis.ready", version=__version__, llm=runtime.orchestrator.llm.name)

    @app.on_event("shutdown")
    async def _shutdown() -> None:  # pragma: no cover
        runtime = getattr(app.state, "runtime", None)
        if runtime is not None:
            with contextlib.suppress(Exception):
                await runtime.stop()
        log.info("jarvis.shutdown")

    # routes
    app.include_router(health_routes.router)
    app.include_router(chat_routes.router)
    app.include_router(ws_routes.router)
    app.include_router(voice_routes.router)
    app.include_router(approvals_routes.router)
    app.include_router(scheduler_routes.router)
    app.include_router(dispatch_routes.router)
    app.include_router(profile_routes.router)
    app.include_router(audit_routes.router)

    # Serve the PWA if the web/ directory exists.
    if _WEB_ROOT.is_dir():
        app.mount("/static", StaticFiles(directory=str(_WEB_ROOT)), name="static")

        @app.get("/")
        async def index() -> FileResponse:
            return FileResponse(_WEB_ROOT / "index.html")

        @app.get("/manifest.json")
        async def manifest() -> FileResponse:
            return FileResponse(_WEB_ROOT / "manifest.json", media_type="application/manifest+json")

        @app.get("/sw.js")
        async def service_worker() -> FileResponse:
            return FileResponse(_WEB_ROOT / "sw.js", media_type="application/javascript")

    return app


def main() -> None:
    """Uvicorn entry point exposed as ``jarvisd`` in the console scripts."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "jarvis.server.app:create_app",
        host=settings.host,
        port=settings.port,
        factory=True,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
