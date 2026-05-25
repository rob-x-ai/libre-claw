# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import libre_claw.auth.codex as codex_auth
from libre_claw.auth.codex import CodexCommandResult, codex_status


async def test_codex_status_reports_missing_cli(monkeypatch) -> None:
    monkeypatch.setattr(codex_auth, "codex_available", lambda executable="codex": False)

    status = await codex_status()

    assert status.available is False
    assert status.logged_in is False
    assert "not installed" in status.detail


async def test_codex_status_reports_chatgpt_login(monkeypatch) -> None:
    async def fake_run(args, input_text=None, timeout=None):  # noqa: ANN001
        del input_text, timeout
        return CodexCommandResult(args=tuple(args), exit_code=0, stdout="Logged in using ChatGPT\n", stderr="")

    monkeypatch.setattr(codex_auth, "codex_available", lambda executable="codex": True)
    monkeypatch.setattr(codex_auth, "run_codex_command", fake_run)

    status = await codex_status()

    assert status.available is True
    assert status.logged_in is True
    assert "ChatGPT" in status.detail
