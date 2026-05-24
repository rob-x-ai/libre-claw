# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from libre_claw.providers.openrouter import (
    OPENROUTER_APP_TITLE,
    OPENROUTER_CATEGORIES,
    OPENROUTER_HTTP_REFERER,
    OpenRouterProvider,
)


class FakeClient:
    chat: object = object()


def test_openrouter_provider_uses_openai_compatible_defaults() -> None:
    provider = OpenRouterProvider(
        api_key="test-key",
        model="openrouter/auto",
        max_tokens=99,
        client=FakeClient(),
    )

    assert provider.base_url == "https://openrouter.ai/api/v1"
    assert provider.display_name == "OpenRouter"
    assert provider.default_headers == {
        "HTTP-Referer": OPENROUTER_HTTP_REFERER,
        "X-OpenRouter-Title": OPENROUTER_APP_TITLE,
        "X-OpenRouter-Categories": OPENROUTER_CATEGORIES,
    }


def test_openrouter_provider_always_uses_libre_claw_attribution() -> None:
    provider = OpenRouterProvider(
        api_key="test-key",
        model="openrouter/auto",
        max_tokens=99,
        client=FakeClient(),
    )

    assert provider.default_headers["HTTP-Referer"] == "https://kroonen.ai"
    assert provider.default_headers["X-OpenRouter-Title"] == "Libre Claw"
    assert provider.default_headers["X-OpenRouter-Categories"] == "cli-agent"
