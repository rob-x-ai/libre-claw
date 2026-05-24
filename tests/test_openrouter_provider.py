# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from libre_claw.providers.openrouter import OpenRouterProvider


class FakeClient:
    chat: object = object()


def test_openrouter_provider_uses_openai_compatible_defaults() -> None:
    provider = OpenRouterProvider(
        api_key="test-key",
        model="openrouter/auto",
        max_tokens=99,
        http_referer="https://kroonen.ai",
        app_title="Libre Claw",
        client=FakeClient(),
    )

    assert provider.base_url == "https://openrouter.ai/api/v1"
    assert provider.display_name == "OpenRouter"
    assert provider.default_headers == {
        "HTTP-Referer": "https://kroonen.ai",
        "X-OpenRouter-Title": "Libre Claw",
    }


def test_openrouter_provider_omits_empty_optional_headers() -> None:
    provider = OpenRouterProvider(
        api_key="test-key",
        model="openrouter/auto",
        max_tokens=99,
        http_referer="",
        app_title="",
        client=FakeClient(),
    )

    assert provider.default_headers == {}
