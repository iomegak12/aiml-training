"""Google web and news search through the Serper API (https://serper.dev).

The corpus is a frozen snapshot; Serper lets the Research agent answer questions about
current trends, prices and news. Each result keeps its URL and date for citation.
"""

from __future__ import annotations

from typing import Literal

import httpx
from pydantic import BaseModel

SERPER_ENDPOINTS = {"search": "https://google.serper.dev/search", "news": "https://google.serper.dev/news"}


class WebResult(BaseModel):
    """One web or news search result."""

    title: str
    url: str
    snippet: str = ""
    date: str | None = None
    source: str | None = None
    position: int = 0


class SerperError(RuntimeError):
    """Raised when the Serper API is not configured or the request fails."""


def _parse(payload: dict, kind: str) -> list[WebResult]:
    """Turn a Serper JSON response into ``WebResult`` objects."""
    items = payload.get("news" if kind == "news" else "organic", [])
    return [WebResult(title=item.get("title", ""), url=item.get("link", ""), snippet=item.get("snippet", ""),
                      date=item.get("date"), source=item.get("source"), position=item.get("position", i))
            for i, item in enumerate(items, start=1) if item.get("link")]


def _request(api_key: str | None, query: str, num: int, kind: str, country: str, time_range: str | None):
    """Validate inputs and build the Serper request arguments."""
    if not api_key:
        raise SerperError("SERPER_API_KEY is not set; web research is unavailable.")
    if kind not in SERPER_ENDPOINTS:
        raise SerperError(f"Unknown search kind {kind!r}; use 'search' or 'news'.")
    body: dict = {"q": query, "num": num, "gl": country}
    if time_range:
        body["tbs"] = f"qdr:{time_range}"  # h, d, w, m, y = past hour/day/week/month/year
    return SERPER_ENDPOINTS[kind], {"X-API-KEY": api_key, "Content-Type": "application/json"}, body


def serper_search(query: str, api_key: str | None, num: int = 5, kind: Literal["search", "news"] = "search",
                  country: str = "in", time_range: str | None = None, timeout: float = 20) -> list[WebResult]:
    """Search Google through Serper (synchronous).

    Args:
        query: Search query.
        api_key: ``SERPER_API_KEY``.
        num: Results to return.
        kind: ``search`` (web) or ``news``.
        country: Two-letter country code for localisation (default India).
        time_range: Optional recency filter: ``d`` (day), ``w`` (week), ``m`` (month) or ``y`` (year).
        timeout: Request timeout in seconds.
    """
    url, headers, body = _request(api_key, query, num, kind, country, time_range)
    try:
        response = httpx.post(url, headers=headers, json=body, timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise SerperError(f"Serper request failed: {exc}") from exc
    return _parse(response.json(), kind)[:num]


async def aserper_search(query: str, api_key: str | None, num: int = 5, kind: Literal["search", "news"] = "search",
                         country: str = "in", time_range: str | None = None, timeout: float = 20) -> list[WebResult]:
    """Asynchronous variant of :func:`serper_search` (same arguments)."""
    url, headers, body = _request(api_key, query, num, kind, country, time_range)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise SerperError(f"Serper request failed: {exc}") from exc
    return _parse(response.json(), kind)[:num]
