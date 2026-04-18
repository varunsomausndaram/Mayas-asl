"""Async HTTP client the CLI uses to talk to the Jarvis server."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx


class JarvisClient:
    """Thin wrapper around the Jarvis HTTP + SSE + WS surface."""

    def __init__(self, base_url: str, api_key: str, *, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> JarvisClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    # --------------------------------------------------------------- health
    async def health(self) -> dict[str, Any]:
        r = await self._client.get("/healthz")
        r.raise_for_status()
        return r.json()

    async def runtime_info(self) -> dict[str, Any]:
        r = await self._client.get("/v1/runtime/info")
        r.raise_for_status()
        return r.json()

    # -------------------------------------------------------------- sessions
    async def create_session(self, title: str = "cli") -> dict[str, Any]:
        r = await self._client.post("/v1/sessions", json={"title": title})
        r.raise_for_status()
        return r.json()

    async def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        r = await self._client.get("/v1/sessions", params={"limit": limit})
        r.raise_for_status()
        return r.json()["sessions"]

    async def list_messages(self, session_id: str) -> list[dict[str, Any]]:
        r = await self._client.get(f"/v1/sessions/{session_id}/messages")
        r.raise_for_status()
        return r.json()["messages"]

    # -------------------------------------------------------------- chat
    async def chat(self, message: str, session_id: str | None = None) -> dict[str, Any]:
        body = {"message": message, "session_id": session_id}
        r = await self._client.post("/v1/chat", json=body)
        r.raise_for_status()
        return r.json()

    async def chat_stream(
        self, message: str, session_id: str | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        body = {"message": message, "session_id": session_id}
        async with self._client.stream("POST", "/v1/chat/stream", json=body) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    continue

    async def interrupt(self, session_id: str) -> None:
        await self._client.post(f"/v1/chat/{session_id}/interrupt")

    # ------------------------------------------------------------- approvals
    async def pending_approvals(self) -> list[dict[str, Any]]:
        r = await self._client.get("/v1/approvals/pending")
        r.raise_for_status()
        return r.json()["pending"]

    async def resolve_approval(self, approval_id: str, decision: str) -> None:
        r = await self._client.post(
            f"/v1/approvals/{approval_id}", json={"decision": decision}
        )
        r.raise_for_status()

    # ------------------------------------------------------------ scheduler
    async def list_jobs(self) -> list[dict[str, Any]]:
        r = await self._client.get("/v1/scheduler/jobs")
        r.raise_for_status()
        return r.json()["jobs"]

    async def create_job(self, **kwargs: Any) -> dict[str, Any]:
        r = await self._client.post("/v1/scheduler/jobs", json=kwargs)
        r.raise_for_status()
        return r.json()

    async def delete_job(self, job_id: str) -> None:
        await self._client.delete(f"/v1/scheduler/jobs/{job_id}")

    # ------------------------------------------------------------- dispatch
    async def dispatch(self, prompt: str, repo_url: str | None = None) -> dict[str, Any]:
        r = await self._client.post(
            "/v1/dispatch", json={"prompt": prompt, "repo_url": repo_url}
        )
        r.raise_for_status()
        return r.json()

    async def stream_dispatch(self, job_id: str) -> AsyncIterator[dict[str, Any]]:
        async with self._client.stream("GET", f"/v1/dispatch/jobs/{job_id}/stream") as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                try:
                    yield json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue

    # -------------------------------------------------------------- profile
    async def get_profile(self) -> dict[str, Any]:
        r = await self._client.get("/v1/profile")
        r.raise_for_status()
        return r.json()

    async def patch_profile(self, **kwargs: Any) -> dict[str, Any]:
        r = await self._client.patch("/v1/profile", json=kwargs)
        r.raise_for_status()
        return r.json()
