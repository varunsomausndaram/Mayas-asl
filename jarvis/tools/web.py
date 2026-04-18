"""Web search and fetch tools.

``web_search`` uses DuckDuckGo's HTML endpoint, which requires no API key.
``web_fetch`` downloads a URL and returns a stripped-down textual version —
useful to give the model something to read without paying for every token of
a JS-rendered page.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx

from jarvis.tools.base import Tool, ToolResult

_UA = "Mozilla/5.0 (Jarvis/1.0; +https://github.com/varunsomausndaram/mayas-asl)"
_MAX_BYTES = 2_000_000
_MAX_TEXT = 20_000


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web via DuckDuckGo and return the top results."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
        },
        "required": ["query"],
    }

    async def run(self, *, query: str, limit: int = 5, **_: Any) -> ToolResult:
        query = query.strip()
        if not query:
            return ToolResult(ok=False, error="empty query")
        limit = max(1, min(int(limit), 10))
        url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": _UA}, follow_redirects=True) as client:
            r = await client.post("https://duckduckgo.com/html/", data={"q": query})
        if r.status_code >= 400:
            return ToolResult(ok=False, error=f"search failed {r.status_code}")
        results = _parse_ddg(r.text, limit)
        return ToolResult(ok=True, output={"query": query, "results": results, "source": url})


class WebFetchTool(Tool):
    name = "web_fetch"
    description = "Fetch a URL and return readable text (HTML stripped)."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "max_chars": {"type": "integer", "minimum": 500, "maximum": _MAX_TEXT, "default": 8000},
        },
        "required": ["url"],
    }

    async def run(self, *, url: str, max_chars: int = 8000, **_: Any) -> ToolResult:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return ToolResult(ok=False, error=f"unsupported scheme: {parsed.scheme!r}")
        if not parsed.netloc:
            return ToolResult(ok=False, error="invalid URL")
        async with httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml"},
            follow_redirects=True,
            max_redirects=5,
        ) as client:
            try:
                r = await client.get(url)
            except httpx.HTTPError as exc:
                return ToolResult(ok=False, error=f"fetch failed: {exc}")
        if r.status_code >= 400:
            return ToolResult(ok=False, error=f"HTTP {r.status_code}")
        raw = r.content[:_MAX_BYTES]
        content_type = r.headers.get("content-type", "")
        if "html" in content_type or "<html" in raw[:2048].lower().decode("utf-8", errors="ignore"):
            text = _html_to_text(raw.decode(r.encoding or "utf-8", errors="replace"))
        else:
            text = raw.decode(r.encoding or "utf-8", errors="replace")
        limit = max(500, min(int(max_chars), _MAX_TEXT))
        truncated = len(text) > limit
        if truncated:
            text = text[:limit]
        return ToolResult(
            ok=True,
            output={
                "url": str(r.url),
                "status": r.status_code,
                "content_type": content_type,
                "text": text,
                "truncated": truncated,
            },
        )


# ----------------------------------------------------------------------- utils
_DDG_RESULT = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
    re.DOTALL,
)


class _Stripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript", "template", "svg"):
            self._skip += 1
        elif tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript", "template", "svg"):
            self._skip = max(0, self._skip - 1)
        elif tag in ("p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        self._parts.append(data)

    def text(self) -> str:
        joined = "".join(self._parts)
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        joined = re.sub(r"[ \t]+", " ", joined)
        return joined.strip()


def _html_to_text(html: str) -> str:
    p = _Stripper()
    try:
        p.feed(html)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)
    return p.text()


def _parse_ddg(html: str, limit: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for match in _DDG_RESULT.finditer(html):
        url, title_html, snippet_html = match.groups()
        title = _html_to_text(title_html)
        snippet = _html_to_text(snippet_html)
        results.append({"url": url, "title": title, "snippet": snippet})
        if len(results) >= limit:
            break
    return results
