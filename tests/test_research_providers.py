"""Tests for metaculus_bot.research.providers helpers."""

from __future__ import annotations

import pytest

from metaculus_bot.research.providers import choose_provider_with_name, is_asknews_subscription_error


class ForbiddenError(Exception):
    """Stand-in for ``asknews_sdk.errors.ForbiddenError``."""


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        pytest.param(
            ForbiddenError("403011 - subscription is not currently active"),
            True,
            id="forbidden_subscription_code",
        ),
        pytest.param(
            ForbiddenError("subscription is not currently active on this tier"),
            True,
            id="forbidden_subscription_phrase",
        ),
        pytest.param(
            ForbiddenError("403000 - rate limit hit"),
            False,
            id="forbidden_unrelated_message",
        ),
        pytest.param(RuntimeError("403 Forbidden"), False, id="generic_403"),
        pytest.param(PermissionError("forbidden path /tmp"), False, id="permission_error"),
        pytest.param(TimeoutError(), False, id="timeout_error"),
    ],
)
def test_is_asknews_subscription_error(exc: BaseException, expected: bool) -> None:
    """Match only the AskNews subscription-inactive error signature."""
    assert is_asknews_subscription_error(exc) is expected


def test_auto_selection_prefers_tavily_over_legacy_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test")
    monkeypatch.setenv("NIMBLE_API_KEY", "nimble-test")
    monkeypatch.setenv("ASKNEWS_CLIENT_ID", "legacy-client")
    monkeypatch.setenv("ASKNEWS_SECRET", "legacy-secret")
    monkeypatch.delenv("RESEARCH_PROVIDER", raising=False)

    provider, name = choose_provider_with_name()

    assert callable(provider)
    assert name == "web_search"


def test_forced_nimble_selection_uses_nimble_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESEARCH_PROVIDER", "nimble")
    monkeypatch.setenv("NIMBLE_API_KEY", "nimble-test")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    provider, name = choose_provider_with_name()

    assert callable(provider)
    assert name == "web_search"
