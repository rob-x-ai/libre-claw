"""Backends package for Libre Claw."""

from typing import Optional

from .base import BackendConfig, BaseBackend, Message, Response
from .claude_code import ClaudeCodeBackend
from .ollama import OllamaBackend


def get_backend(backend_type: str, config: Optional[BackendConfig] = None) -> BaseBackend:
    """Get a backend instance by type.

    Args:
        backend_type: Type of backend ("claude_code", "ollama", "anthropic")
        config: Backend configuration

    Returns:
        Backend instance
    """
    if backend_type == "claude_code":
        return ClaudeCodeBackend(config)
    elif backend_type == "ollama":
        return OllamaBackend(config)
    elif backend_type == "anthropic":
        # Placeholder for future Anthropic API backend
        raise NotImplementedError("Anthropic API backend not yet implemented")
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")


__all__ = [
    "BackendConfig",
    "BaseBackend",
    "Message",
    "Response",
    "ClaudeCodeBackend",
    "OllamaBackend",
    "get_backend",
]
