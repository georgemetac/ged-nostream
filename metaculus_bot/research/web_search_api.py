"""Tavily-first and Nimbleway-fallback web search for research providers."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Mapping
from typing import Any

import aiohttp

from metaculus_bot.constants import NIMBLE_API_KEY_ENV, TAVILY_API_KEY_ENV, WEB_SEARCH_API_TIMEOUT_S

logger = logging.getLogger(__name__)

_TAVILY_SEARCH_URL = "https://api.tavily.com/search"
_NIMBLE_SEARCH_URL = "https://sdk.nimbleway.com/v2/search"


async def _post_json(url: str, *, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    timeout = aiohttp.ClientTimeout(total=WEB_SEARCH_API_TIMEOUT_S)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, headers=headers, json=payload) as response:
            response.raise_for_status()
            body = await response.json()
    if not isinstance(body, dict):
        raise ValueError("Search API returned a non-object JSON response")
    return body


def _render_results(results: object, *, provider: str) -> str:
    if not isinstance(results, list):
        return ""

    sections: list[str] = []
    for result in results:
        if not isinstance(result, Mapping):
            continue
        title = str(result.get("title") or "Untitled result").strip()
        url = str(result.get("url") or "").strip()
        content = str(result.get("content") or result.get("description") or "").strip()
        lines = [f"### {title}"]
        if url:
            lines.append(f"URL: {url}")
        if content:
            lines.append(content)
        if url or content:
            sections.append("\n".join(lines))
    if not sections:
        return ""
    return f"Search source: {provider}\n\n" + "\n\n".join(sections)


async def _search_tavily(query: str, *, end_date: str | None, topic: str) -> str:
    api_key = os.getenv(TAVILY_API_KEY_ENV)
    if not api_key:
        return ""
    payload: dict[str, Any] = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": 8,
        "include_answer": False,
        "include_raw_content": False,
        "topic": topic,
    }
    if end_date:
        payload["end_date"] = end_date
    response = await _post_json(_TAVILY_SEARCH_URL, headers={}, payload=payload)
    return _render_results(response.get("results"), provider="Tavily")


async def _search_nimble(query: str, *, end_date: str | None, topic: str) -> str:
    api_key = os.getenv(NIMBLE_API_KEY_ENV)
    if not api_key:
        return ""
    payload: dict[str, Any] = {
        "query": query,
        "search_depth": "lite",
        "max_results": 8,
        "focus": topic,
    }
    if end_date:
        payload["end_date"] = end_date
    response = await _post_json(
        _NIMBLE_SEARCH_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        payload=payload,
    )
    return _render_results(response.get("results"), provider="Nimbleway")


async def search_web_fallback(
    query: str,
    *,
    end_date: str | None = None,
    topic: str = "general",
    preferred: str = "tavily",
) -> tuple[str, str]:
    """Return ``(provider, markdown)`` using Tavily first and Nimbleway as fallback."""
    candidates = ("nimble",) if preferred == "nimble" else ("tavily", "nimble")
    last_error: Exception | None = None
    for provider in candidates:
        if provider == "tavily":
            search = _search_tavily
            key = os.getenv(TAVILY_API_KEY_ENV)
        else:
            search = _search_nimble
            key = os.getenv(NIMBLE_API_KEY_ENV)
        if not key:
            continue
        try:
            result = await asyncio.wait_for(
                search(query, end_date=end_date, topic=topic),
                timeout=WEB_SEARCH_API_TIMEOUT_S,
            )
        except Exception as exc:  # HARNESS-SCAN-EXEMPT-broad-except  # provider failover boundary
            last_error = exc
            logger.warning("%s search failed (%s); trying the next configured provider", provider, type(exc).__name__)
            continue
        if result:
            return provider, result

    if last_error is not None:
        raise RuntimeError("All configured web search providers failed") from last_error
    return "none", ""