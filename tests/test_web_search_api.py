from __future__ import annotations

from typing import Any

import pytest

from metaculus_bot.research import web_search_api


@pytest.mark.asyncio
async def test_tavily_request_uses_body_key_and_formats_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")
    calls: list[tuple[str, dict[str, str], dict[str, Any]]] = []

    async def fake_post(url: str, *, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        calls.append((url, headers, payload))
        return {"results": [{"title": "Source", "url": "https://example.com", "content": "Evidence"}]}

    monkeypatch.setattr(web_search_api, "_post_json", fake_post)

    provider, result = await web_search_api.search_web_fallback("Will it happen?", end_date="2026-09-01")

    assert provider == "tavily"
    assert "Evidence" in result
    assert calls == [
        (
            "https://api.tavily.com/search",
            {},
            {
                "api_key": "test-tavily-key",
                "query": "Will it happen?",
                "search_depth": "basic",
                "max_results": 8,
                "include_answer": False,
                "include_raw_content": False,
                "topic": "general",
                "end_date": "2026-09-01",
            },
        )
    ]


@pytest.mark.asyncio
async def test_tavily_failure_falls_back_to_nimble_bearer_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")
    monkeypatch.setenv("NIMBLE_API_KEY", "test-nimble-key")
    calls: list[tuple[str, dict[str, str], dict[str, Any]]] = []

    async def fake_post(url: str, *, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        calls.append((url, headers, payload))
        if "tavily" in url:
            raise RuntimeError("temporary error")
        return {"results": [{"title": "Backup", "url": "https://backup.example", "description": "Found"}]}

    monkeypatch.setattr(web_search_api, "_post_json", fake_post)

    provider, result = await web_search_api.search_web_fallback("Will it happen?", topic="news")

    assert provider == "nimble"
    assert "Nimbleway" in result
    assert calls[1][0] == "https://sdk.nimbleway.com/v2/search"
    assert calls[1][1] == {"Authorization": "Bearer test-nimble-key"}
    assert calls[1][2]["focus"] == "news"


@pytest.mark.asyncio
async def test_empty_tavily_results_fall_back_to_nimble(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")
    monkeypatch.setenv("NIMBLE_API_KEY", "test-nimble-key")
    providers: list[str] = []

    async def fake_post(url: str, *, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        providers.append(url)
        if "tavily" in url:
            return {"results": []}
        return {"results": [{"title": "Backup", "url": "https://backup.example", "content": "Found"}]}

    monkeypatch.setattr(web_search_api, "_post_json", fake_post)

    provider, _ = await web_search_api.search_web_fallback("Will it happen?")

    assert provider == "nimble"
    assert len(providers) == 2