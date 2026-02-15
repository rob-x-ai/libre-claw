"""Tests for backend modules."""

import pytest

from libre_claw.backends import get_backend, BackendConfig, Message, Response
from libre_claw.backends.base import BaseBackend
from libre_claw.backends.claude_code import ClaudeCodeBackend
from libre_claw.backends.ollama import OllamaBackend


class TestBackendConfig:
    """Test backend configuration."""

    def test_defaults(self):
        config = BackendConfig()
        assert config.claude_path == "/opt/homebrew/bin/claude"
        assert config.ollama_url == "http://localhost:11434"
        assert config.ollama_model == "llama2"
        assert config.max_tokens == 4096

    def test_custom_values(self):
        config = BackendConfig(
            claude_path="/usr/local/bin/claude",
            ollama_model="qwen2.5:14b",
            max_tokens=8192,
        )
        assert config.claude_path == "/usr/local/bin/claude"
        assert config.ollama_model == "qwen2.5:14b"
        assert config.max_tokens == 8192


class TestMessage:
    """Test message dataclass."""

    def test_user_message(self):
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_calls is None

    def test_assistant_message_with_tools(self):
        msg = Message(
            role="assistant",
            content="Using tool...",
            tool_calls=[{"name": "search", "args": {"q": "test"}}],
        )
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1


class TestResponse:
    """Test response dataclass."""

    def test_simple_response(self):
        resp = Response(content="Hello back!")
        assert resp.content == "Hello back!"
        assert resp.model is None
        assert resp.usage is None

    def test_full_response(self):
        resp = Response(
            content="Result",
            usage={"input_tokens": 100, "output_tokens": 50},
            model="claude-sonnet-4",
            stop_reason="end_turn",
        )
        assert resp.usage["input_tokens"] == 100
        assert resp.model == "claude-sonnet-4"


class TestGetBackend:
    """Test backend factory function."""

    def test_get_claude_code_backend(self):
        backend = get_backend("claude_code")
        assert isinstance(backend, ClaudeCodeBackend)
        assert backend.name == "claude-code"

    def test_get_ollama_backend(self):
        backend = get_backend("ollama")
        assert isinstance(backend, OllamaBackend)
        assert backend.name == "ollama"

    def test_get_anthropic_raises(self):
        with pytest.raises(NotImplementedError):
            get_backend("anthropic")

    def test_get_unknown_raises(self):
        with pytest.raises(ValueError):
            get_backend("openai")


class TestClaudeCodeBackend:
    """Test Claude Code backend."""

    def test_name(self):
        backend = ClaudeCodeBackend()
        assert backend.name == "claude-code"

    def test_supports_tools(self):
        backend = ClaudeCodeBackend()
        assert backend.supports_tools is True

    def test_history_management(self):
        backend = ClaudeCodeBackend()
        backend.add_message(Message(role="user", content="hi"))
        backend.add_message(Message(role="assistant", content="hello"))

        history = backend.get_history()
        assert len(history) == 2

        backend.clear_history()
        assert len(backend.get_history()) == 0

    def test_build_prompt(self):
        backend = ClaudeCodeBackend()
        prompt = backend._build_prompt(
            prompt="What is 2+2?",
            system_prompt="You are a calculator.",
            context={"SOUL.md": "I am helpful."},
        )
        assert "What is 2+2?" in prompt
        assert "calculator" in prompt
        assert "helpful" in prompt


class TestOllamaBackend:
    """Test Ollama backend."""

    def test_name(self):
        backend = OllamaBackend()
        assert backend.name == "ollama"

    def test_supports_tools(self):
        backend = OllamaBackend()
        assert backend.supports_tools is False

    def test_build_messages(self):
        backend = OllamaBackend()
        messages = [
            Message(role="user", content="hello"),
            Message(role="assistant", content="hi"),
        ]
        formatted = backend._build_messages_format(
            messages, system_prompt="Be nice."
        )
        assert formatted[0]["role"] == "system"
        assert formatted[1]["role"] == "user"
        assert formatted[2]["role"] == "assistant"
