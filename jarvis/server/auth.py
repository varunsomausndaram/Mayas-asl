"""API-key authentication.

Every protected route requires a matching ``Authorization: Bearer ...``
header or ``?api_key=...`` query parameter. WebSocket clients supply the
key in the first message frame. The key comes from ``JARVIS_API_KEY`` and
is compared with :func:`hmac.compare_digest`.
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, Query, Request, status

from jarvis.config import Settings, get_settings


def _extract(request: Request | None, authorization: str | None, api_key_q: str | None) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if api_key_q:
        return api_key_q.strip()
    if request is not None:
        header = request.headers.get("x-api-key")
        if header:
            return header.strip()
    return ""


def require_api_key(
    request: Request,
    authorization: str | None = Header(default=None),
    api_key: str | None = Query(default=None),
) -> None:
    """FastAPI dependency that enforces the API-key policy."""
    settings: Settings = get_settings()
    presented = _extract(request, authorization, api_key)
    expected = settings.api_key
    if not expected or expected == "change-me":
        # Default unsafe value — fail closed with a helpful message.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JARVIS_API_KEY is not configured. Set it in .env before exposing Jarvis.",
        )
    if not presented or not hmac.compare_digest(presented.encode(), expected.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


def websocket_api_key_ok(presented: str) -> bool:
    settings: Settings = get_settings()
    expected = settings.api_key
    if not expected or expected == "change-me":
        return False
    return hmac.compare_digest((presented or "").encode(), expected.encode())
