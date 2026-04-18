"""Exception hierarchy used across Jarvis.

Keeping these in one place makes it easy for the server to translate them
into HTTP responses and for the CLI to colourise them. Every error carries a
machine-readable ``code`` so clients can branch on the cause without parsing
human-readable text.
"""

from __future__ import annotations


class JarvisError(Exception):
    """Base class for every error Jarvis raises deliberately."""

    code: str = "jarvis_error"
    http_status: int = 500

    def __init__(self, message: str, *, code: str | None = None, status: int | None = None):
        super().__init__(message)
        if code is not None:
            self.code = code
        if status is not None:
            self.http_status = status

    def to_dict(self) -> dict[str, str | int]:
        return {"code": self.code, "message": str(self), "status": self.http_status}


class ConfigurationError(JarvisError):
    code = "configuration_error"
    http_status = 500


class AuthenticationError(JarvisError):
    code = "authentication_error"
    http_status = 401


class PermissionDenied(JarvisError):
    code = "permission_denied"
    http_status = 403


class NotFound(JarvisError):
    code = "not_found"
    http_status = 404


class BadRequest(JarvisError):
    code = "bad_request"
    http_status = 400


class ToolError(JarvisError):
    """Raised by a :class:`jarvis.tools.base.Tool` when it cannot complete."""

    code = "tool_error"
    http_status = 422


class ToolNotAllowed(ToolError):
    code = "tool_not_allowed"
    http_status = 403


class LLMError(JarvisError):
    code = "llm_error"
    http_status = 502


class LLMUnavailable(LLMError):
    code = "llm_unavailable"
    http_status = 503


class DispatchError(JarvisError):
    code = "dispatch_error"
    http_status = 500
