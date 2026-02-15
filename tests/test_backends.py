"""Tests for backend implementations."""

from libre_claw.backends.base import BaseBackend, BackendConfig, Message, Response
from libre_claw.backends.claude_code import ClaudeCodeBackend
from libre_claw.backends.ollama import OllamaBackend
from libre_claw.backends.openai_api import OpenAIBackend
from libre_claw.backends.anthropic_api import AnthropicBackend
from libre_claw.backends.codex_cli import CodexCLIBackend
from libre_claw.backends.openai_codex_oauth import OpenAICodexOAuthBackend
from libre_claw.backends import get_backend


def test_backend_config_defaults():
    config = BackendConfig()
    assert config.max_tokens == 4096
    assert config.temperature == 1.0


def test_message_creation():
    msg = Message(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"
    assert msg.tool_calls is None


def test_response_creation():
    resp = Response(content="World", model="test")
    assert resp.content == "World"
    assert resp.model == "test"


def test_claude_code_backend_name():
    backend = ClaudeCodeBackend()
    assert backend.name == "claude-code"
    assert backend.supports_tools is True


def test_ollama_backend_name():
    backend = OllamaBackend()
    assert backend.name == "ollama"
    assert backend.supports_tools is False


def test_get_backend_claude():
    backend = get_backend("claude_code")
    assert isinstance(backend, ClaudeCodeBackend)


def test_get_backend_ollama():
    backend = get_backend("ollama")
    assert isinstance(backend, OllamaBackend)


def test_get_backend_codex_cli():
    backend = get_backend("codex_cli")
    assert isinstance(backend, CodexCLIBackend)


def test_get_backend_openai():
    backend = get_backend("openai")
    assert isinstance(backend, OpenAIBackend)


def test_get_backend_openai_codex():
    backend = get_backend("openai_codex")
    assert isinstance(backend, OpenAICodexOAuthBackend)


def test_get_backend_anthropic():
    backend = get_backend("anthropic")
    assert isinstance(backend, AnthropicBackend)


def test_get_backend_unknown():
    try:
        get_backend("nonexistent")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_conversation_history():
    backend = ClaudeCodeBackend()
    assert len(backend.get_history()) == 0

    backend.add_message(Message(role="user", content="Hi"))
    assert len(backend.get_history()) == 1

    backend.add_message(Message(role="assistant", content="Hello"))
    assert len(backend.get_history()) == 2

    backend.clear_history()
    assert len(backend.get_history()) == 0
