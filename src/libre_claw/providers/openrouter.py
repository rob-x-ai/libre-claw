# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from libre_claw.providers.openai import OpenAIProvider


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter provider using its OpenAI-compatible chat completions API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int,
        base_url: str = "https://openrouter.ai/api/v1",
        http_referer: str | None = None,
        app_title: str | None = None,
        client: object | None = None,
    ) -> None:
        headers: dict[str, str] = {}
        if http_referer:
            headers["HTTP-Referer"] = http_referer
        if app_title:
            headers["X-OpenRouter-Title"] = app_title

        super().__init__(
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            base_url=base_url,
            default_headers=headers,
            display_name="OpenRouter",
            client=client,
        )
