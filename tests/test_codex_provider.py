# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

import libre_claw.providers.codex as codex_provider
from libre_claw.auth.codex import CodexCommandResult, CodexStatus
from libre_claw.core.session import ChatMessage, text_block
from libre_claw.providers.base import ProviderError, TextDelta
from libre_claw.providers.codex import CodexProvider, _extract_codex_text


def test_extract_codex_text_from_jsonl_and_plain_fallback() -> None:
    output = "\n".join(
        [
            '{"type":"agent_message_delta","delta":"Hello"}',
            '{"item":{"content":[{"text":" world"}]}}',
            "plain line",
        ]
    )

    assert _extract_codex_text(output) == ["Hello", " world", "plain line\n"]


async def test_codex_provider_requires_login(monkeypatch, tmp_path: Path) -> None:
    async def fake_status(executable: str = "codex") -> CodexStatus:
        del executable
        return CodexStatus(available=True, logged_in=False, detail="Not logged in")

    monkeypatch.setattr(codex_provider, "codex_status", fake_status)
    provider = CodexProvider(model="gpt-5.5", working_directory=tmp_path)

    events = [
        event
        async for event in provider.complete(messages=[ChatMessage(role="user", content=[text_block("hi")])])
    ]

    assert isinstance(events[0], ProviderError)
    assert "/codex login" in events[0].message


async def test_codex_provider_runs_codex_exec_with_prompt(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    async def fake_status(executable: str = "codex") -> CodexStatus:
        del executable
        return CodexStatus(available=True, logged_in=True, detail="Logged in using ChatGPT")

    async def fake_run(args, input_text=None, timeout=None):  # noqa: ANN001
        captured["args"] = args
        captured["input_text"] = input_text
        captured["timeout"] = timeout
        return CodexCommandResult(
            args=tuple(args),
            exit_code=0,
            stdout='{"delta":"Codex works"}\n',
            stderr="",
        )

    monkeypatch.setattr(codex_provider, "codex_status", fake_status)
    monkeypatch.setattr(codex_provider, "run_codex_command", fake_run)
    provider = CodexProvider(model="gpt-5.5", working_directory=tmp_path, timeout=12)

    events = [
        event
        async for event in provider.complete(
            messages=[ChatMessage(role="user", content=[text_block("build this")])],
            system="System text",
        )
    ]

    assert any(isinstance(event, TextDelta) and event.text == "Codex works" for event in events)
    assert captured["args"][:3] == ["codex", "exec", "--json"]
    assert "--model" in captured["args"]
    assert "build this" in str(captured["input_text"])
    assert "System text" in str(captured["input_text"])
    assert captured["timeout"] == 12
