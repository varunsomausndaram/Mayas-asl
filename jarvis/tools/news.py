"""News and weather tools. API-key-free by design.

* ``news_headlines`` pulls from Google News RSS for a query or category.
* ``weather_current`` and ``weather_forecast`` use the Open-Meteo public API
  which requires no key. Cities are resolved via Open-Meteo's geocoding.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote_plus

import httpx

from jarvis.tools.base import Tool, ToolResult

_UA = "Mozilla/5.0 (Jarvis-News/1.0)"


class NewsHeadlinesTool(Tool):
    name = "news_headlines"
    description = (
        "Fetch top news headlines from Google News RSS. Accepts a free-text query "
        "(e.g. 'AI regulation') or 'top' for front-page headlines."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keywords or 'top'", "default": "top"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 8},
            "language": {"type": "string", "default": "en"},
            "country": {"type": "string", "default": "US"},
        },
    }

    async def run(
        self,
        *,
        query: str = "top",
        limit: int = 8,
        language: str = "en",
        country: str = "US",
        **_: Any,
    ) -> ToolResult:
        limit = max(1, min(int(limit), 20))
        if query.strip().lower() in ("top", "headlines", ""):
            url = f"https://news.google.com/rss?hl={language}-{country}&gl={country}&ceid={country}:{language}"
        else:
            url = (
                f"https://news.google.com/rss/search?q={quote_plus(query)}"
                f"&hl={language}-{country}&gl={country}&ceid={country}:{language}"
            )
        async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": _UA}, follow_redirects=True) as c:
            try:
                r = await c.get(url)
            except httpx.HTTPError as exc:
                return ToolResult(ok=False, error=f"news fetch failed: {exc}")
        if r.status_code >= 400:
            return ToolResult(ok=False, error=f"news feed error {r.status_code}")
        items = _parse_rss(r.text, limit)
        return ToolResult(ok=True, output={"query": query, "items": items, "source": url})


_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<(title|link|pubDate|source|description)[^>]*>(.*?)</\1>", re.DOTALL | re.IGNORECASE)


class _HTMLUnescape(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._buf: list[str] = []

    def handle_data(self, data: str) -> None:
        self._buf.append(data)

    def handle_entityref(self, name: str) -> None:
        self._buf.append(f"&{name};")

    def text(self) -> str:
        return "".join(self._buf)


def _unescape(s: str) -> str:
    p = _HTMLUnescape()
    try:
        p.feed(s)
    except Exception:
        return s
    return p.text().strip()


def _parse_rss(xml: str, limit: int) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for m in _ITEM_RE.finditer(xml):
        block = m.group(1)
        fields = {"title": "", "link": "", "pubDate": "", "source": "", "description": ""}
        for tm in _TAG_RE.finditer(block):
            key, value = tm.group(1).lower(), tm.group(2)
            fields[key] = _unescape(value)
        if fields["title"] and fields["link"]:
            items.append(
                {
                    "title": fields["title"],
                    "url": _strip_cdata(fields["link"]),
                    "published": fields["pubDate"],
                    "source": _strip_html(fields["source"]) or _strip_html(fields["description"]),
                }
            )
        if len(items) >= limit:
            break
    return items


def _strip_cdata(s: str) -> str:
    return re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s, flags=re.DOTALL).strip()


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


# ------------------------------------------------------------------- weather
class WeatherCurrentTool(Tool):
    name = "weather_current"
    description = "Current temperature, wind, and weather code for a city."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "city": {"type": "string"},
            "units": {"type": "string", "enum": ["metric", "imperial"], "default": "metric"},
        },
        "required": ["city"],
    }

    async def run(self, *, city: str, units: str = "metric", **_: Any) -> ToolResult:
        geo = await _geocode(city)
        if geo is None:
            return ToolResult(ok=False, error=f"could not resolve city: {city!r}")
        temp_unit = "celsius" if units == "metric" else "fahrenheit"
        wind_unit = "kmh" if units == "metric" else "mph"
        params = {
            "latitude": geo["lat"],
            "longitude": geo["lon"],
            "current": "temperature_2m,wind_speed_10m,relative_humidity_2m,weather_code",
            "temperature_unit": temp_unit,
            "wind_speed_unit": wind_unit,
        }
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get("https://api.open-meteo.com/v1/forecast", params=params)
        if r.status_code >= 400:
            return ToolResult(ok=False, error=f"weather fetch failed {r.status_code}")
        data = r.json()
        cur = data.get("current") or {}
        return ToolResult(
            ok=True,
            output={
                "city": geo["name"],
                "country": geo.get("country"),
                "temperature": cur.get("temperature_2m"),
                "temperature_unit": temp_unit,
                "wind_speed": cur.get("wind_speed_10m"),
                "wind_unit": wind_unit,
                "humidity": cur.get("relative_humidity_2m"),
                "weather_code": cur.get("weather_code"),
                "weather": _code_to_text(cur.get("weather_code")),
                "time": cur.get("time"),
            },
        )


class WeatherForecastTool(Tool):
    name = "weather_forecast"
    description = "Multi-day forecast for a city."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "city": {"type": "string"},
            "days": {"type": "integer", "minimum": 1, "maximum": 7, "default": 3},
            "units": {"type": "string", "enum": ["metric", "imperial"], "default": "metric"},
        },
        "required": ["city"],
    }

    async def run(
        self, *, city: str, days: int = 3, units: str = "metric", **_: Any
    ) -> ToolResult:
        days = max(1, min(int(days), 7))
        geo = await _geocode(city)
        if geo is None:
            return ToolResult(ok=False, error=f"could not resolve city: {city!r}")
        temp_unit = "celsius" if units == "metric" else "fahrenheit"
        params = {
            "latitude": geo["lat"],
            "longitude": geo["lon"],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
            "temperature_unit": temp_unit,
            "forecast_days": days,
            "timezone": "auto",
        }
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get("https://api.open-meteo.com/v1/forecast", params=params)
        if r.status_code >= 400:
            return ToolResult(ok=False, error=f"weather forecast failed {r.status_code}")
        data = r.json()
        daily = data.get("daily") or {}
        rows: list[dict[str, Any]] = []
        dates = daily.get("time") or []
        for i, date in enumerate(dates):
            rows.append(
                {
                    "date": date,
                    "high": _nth(daily.get("temperature_2m_max"), i),
                    "low": _nth(daily.get("temperature_2m_min"), i),
                    "precipitation": _nth(daily.get("precipitation_sum"), i),
                    "weather": _code_to_text(_nth(daily.get("weather_code"), i)),
                }
            )
        return ToolResult(
            ok=True,
            output={"city": geo["name"], "country": geo.get("country"), "days": rows, "unit": temp_unit},
        )


async def _geocode(city: str) -> dict[str, Any] | None:
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en", "format": "json"},
        )
    if r.status_code != 200:
        return None
    results = (r.json() or {}).get("results") or []
    if not results:
        return None
    it = results[0]
    return {
        "name": it.get("name"),
        "country": it.get("country"),
        "lat": it.get("latitude"),
        "lon": it.get("longitude"),
    }


def _nth(seq: list[Any] | None, i: int) -> Any:
    if not seq or i >= len(seq):
        return None
    return seq[i]


_WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Rain showers",
    81: "Heavy rain showers",
    82: "Violent rain showers",
    85: "Snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _code_to_text(code: Any) -> str:
    try:
        return _WEATHER_CODES.get(int(code), "Unknown")
    except (TypeError, ValueError):
        return "Unknown"
