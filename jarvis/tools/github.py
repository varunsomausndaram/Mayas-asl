"""GitHub tools — list repos, read files, open issues.

The tools authenticate with a personal access token from ``GITHUB_TOKEN``.
They call the REST API over HTTPX so there is no dependency on ``PyGithub``.
Every tool returns data narrow enough to paste into a chat response: we do
not return whole repo trees, nor do we paginate beyond the first page
without being asked.
"""

from __future__ import annotations

import base64
from typing import Any
from urllib.parse import quote

import httpx

from jarvis.errors import ConfigurationError
from jarvis.tools.base import Tool, ToolResult

_BASE = "https://api.github.com"


def _client(token: str) -> httpx.AsyncClient:
    if not token:
        raise ConfigurationError("GITHUB_TOKEN is empty — set it to enable GitHub tools.")
    return httpx.AsyncClient(
        timeout=30.0,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "jarvis-assistant",
        },
    )


class GitHubListReposTool(Tool):
    name = "github_list_repos"
    description = "List repositories for the authenticated user (or a provided owner)."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 30},
            "visibility": {
                "type": "string",
                "enum": ["all", "public", "private"],
                "default": "all",
            },
        },
    }

    def __init__(self, token: str, default_owner: str = "") -> None:
        self.token = token
        self.default_owner = default_owner

    async def run(
        self, *, owner: str | None = None, limit: int = 30, visibility: str = "all", **_: Any
    ) -> ToolResult:
        limit = max(1, min(int(limit), 100))
        owner = (owner or self.default_owner or "").strip()
        path = f"/users/{quote(owner)}/repos" if owner else "/user/repos"
        async with _client(self.token) as c:
            r = await c.get(f"{_BASE}{path}", params={"per_page": limit, "visibility": visibility, "sort": "updated"})
        if r.status_code >= 400:
            return ToolResult(ok=False, error=f"GitHub {r.status_code}: {r.text[:300]}")
        repos = [
            {
                "full_name": r_["full_name"],
                "description": r_.get("description") or "",
                "private": r_.get("private", False),
                "default_branch": r_.get("default_branch"),
                "updated_at": r_.get("updated_at"),
                "url": r_.get("html_url"),
            }
            for r_ in r.json()
        ]
        return ToolResult(ok=True, output={"repos": repos, "count": len(repos)})


class GitHubGetFileTool(Tool):
    name = "github_get_file"
    description = "Read a file from a GitHub repository at a given ref."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "owner/name"},
            "path": {"type": "string"},
            "ref": {"type": "string", "description": "branch, tag, or SHA"},
        },
        "required": ["repo", "path"],
    }

    def __init__(self, token: str) -> None:
        self.token = token

    async def run(self, *, repo: str, path: str, ref: str | None = None, **_: Any) -> ToolResult:
        params = {"ref": ref} if ref else {}
        async with _client(self.token) as c:
            r = await c.get(f"{_BASE}/repos/{repo}/contents/{quote(path)}", params=params)
        if r.status_code >= 400:
            return ToolResult(ok=False, error=f"GitHub {r.status_code}: {r.text[:300]}")
        data = r.json()
        if isinstance(data, list):
            return ToolResult(
                ok=True,
                output={"kind": "dir", "entries": [{"path": e["path"], "type": e["type"]} for e in data]},
            )
        content_b64 = data.get("content") or ""
        content = base64.b64decode(content_b64).decode("utf-8", errors="replace")
        return ToolResult(
            ok=True,
            output={
                "kind": "file",
                "path": data.get("path"),
                "sha": data.get("sha"),
                "size": data.get("size"),
                "content": content,
            },
        )


class GitHubCreateIssueTool(Tool):
    name = "github_create_issue"
    description = "Open an issue on a repository."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "repo": {"type": "string"},
            "title": {"type": "string"},
            "body": {"type": "string"},
            "labels": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["repo", "title"],
    }

    def __init__(self, token: str) -> None:
        self.token = token

    async def run(
        self,
        *,
        repo: str,
        title: str,
        body: str = "",
        labels: list[str] | None = None,
        **_: Any,
    ) -> ToolResult:
        payload = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        async with _client(self.token) as c:
            r = await c.post(f"{_BASE}/repos/{repo}/issues", json=payload)
        if r.status_code >= 400:
            return ToolResult(ok=False, error=f"GitHub {r.status_code}: {r.text[:300]}")
        data = r.json()
        return ToolResult(
            ok=True,
            output={"number": data.get("number"), "url": data.get("html_url"), "state": data.get("state")},
        )


class GitHubSearchTool(Tool):
    name = "github_search"
    description = "Search GitHub repositories by keyword."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 10},
        },
        "required": ["query"],
    }

    def __init__(self, token: str) -> None:
        self.token = token

    async def run(self, *, query: str, limit: int = 10, **_: Any) -> ToolResult:
        limit = max(1, min(int(limit), 25))
        async with _client(self.token) as c:
            r = await c.get(
                f"{_BASE}/search/repositories",
                params={"q": query, "per_page": limit, "sort": "updated"},
            )
        if r.status_code >= 400:
            return ToolResult(ok=False, error=f"GitHub {r.status_code}: {r.text[:300]}")
        items = r.json().get("items") or []
        repos = [
            {
                "full_name": i["full_name"],
                "description": i.get("description") or "",
                "stars": i.get("stargazers_count"),
                "url": i.get("html_url"),
            }
            for i in items
        ]
        return ToolResult(ok=True, output={"query": query, "results": repos})
