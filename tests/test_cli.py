# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Iterable

from click.testing import CliRunner

from libre_claw import __version__
from libre_claw.cli import main


class FakeLookup:
    def __init__(self, source: str) -> None:
        self.source = source


class FakeKeyStore:
    stored: dict[str, str] = {}

    def set_api_key(self, provider: str, api_key: str) -> str:
        self.stored[provider] = api_key
        return "encrypted_file"

    def get_api_key(self, provider: str, env_var: str | None = None) -> FakeLookup:
        del env_var
        return FakeLookup("encrypted_file" if provider in FakeKeyStore.stored else "missing")

    def key_status(self, providers: Iterable[tuple[str, str | None]]) -> dict[str, str]:
        return {provider: self.get_api_key(provider, env).source for provider, env in providers}


def test_cli_entrypoint_imports() -> None:
    assert main.name == "main"


def test_cli_version() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_exposes_telegram_command() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "daemon" in result.output
    assert "telegram" in result.output
    assert "auth" in result.output
    assert "config" in result.output


def test_cli_telegram_help_exposes_setup_and_up() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["telegram", "--help"])

    assert result.exit_code == 0
    assert "setup" in result.output
    assert "up" in result.output
    assert "status" in result.output


def test_cli_telegram_setup_stores_token_and_config(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    FakeKeyStore.stored.clear()
    monkeypatch.setattr("libre_claw.cli.ApiKeyStore.from_config", lambda config: FakeKeyStore())

    result = runner.invoke(
        main,
        [
            "telegram",
            "setup",
            "--bot-token",
            "secret-token",
            "--user-id",
            "123",
            "--provider",
            "openrouter",
            "--model",
            "qwen/qwen3.7-max",
        ],
    )

    assert result.exit_code == 0
    assert FakeKeyStore.stored["telegram"] == "secret-token"
    assert "secret-token" not in result.output
    config_text = (tmp_path / ".libre-claw" / "config.toml").read_text(encoding="utf-8")
    assert "enabled = true" in config_text
    assert "use_daemon = true" in config_text
    assert "allowed_user_ids = [123]" in config_text
    assert 'default_provider = "openrouter"' in config_text


def test_cli_config_defaults_outputs_toml() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["config", "defaults"])

    assert result.exit_code == 0
    assert "[general]" in result.output
    assert 'default_provider = "anthropic"' in result.output


def test_cli_auth_status_does_not_print_keys(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-anthropic-key")

    result = runner.invoke(main, ["auth", "status"])

    assert result.exit_code == 0
    assert "anthropic: environment" in result.output
    assert "openrouter: missing" in result.output
    assert "secret-anthropic-key" not in result.output
