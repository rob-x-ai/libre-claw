"""Backends package for Libre Claw."""

from typing import Optional

from .anthropic_api import AnthropicBackend
from .base import BackendConfig, BaseBackend, Message, Response
from .claude_code import ClaudeCodeBackend
from .codex_cli import CodexCLIBackend
from .ollama import OllamaBackend
from .openai_api import OpenAIBackend


def get_backend(backend_type: str, config: Optional[BackendConfig] = None) -> BaseBackend:
    """Get a backend instance by type.

    Args:
        backend_type: Type of backend ("claude_code", "codex_cli", "ollama", "anthropic", "openai")
        config: Backend configuration

    Returns:
        Backend instance
    """
    if backend_type == "claude_code":
        return ClaudeCodeBackend(config)
    elif backend_type == "codex_cli":
        return CodexCLIBackend(config)
    elif backend_type == "ollama":
        return OllamaBackend(config)
    elif backend_type == "anthropic":
        return AnthropicBackend(config)
    elif backend_type == "openai":
        return OpenAIBackend(config)
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")


__all__ = [
    "BackendConfig",
    "BaseBackend",
    "Message",
    "Response",
    "ClaudeCodeBackend",
    "CodexCLIBackend",
    "OllamaBackend",
    "AnthropicBackend",
    "OpenAIBackend",
    "get_backend",
]
