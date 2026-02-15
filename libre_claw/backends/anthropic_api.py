"""Anthropic API backend for Libre Claw."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from .base import BackendConfig, BaseBackend, Message, Response


class AnthropicBackend(BaseBackend):
    """Backend that uses Anthropic Messages API."""

    def __init__(self, config: Optional[BackendConfig] = None):
        super().__init__(config)
        self._base_url = self.config.anthropic_base_url.rstrip("/")
        self._model = self.config.anthropic_model
        self._api_key = self._resolve_key()
        self._client = httpx.Client(timeout=300.0)

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def supports_tools(self) -> bool:
        return False

    def _resolve_key(self) -> Optional[str]:
        if self.config.anthropic_api_key:
            return self.config.anthropic_api_key

        env_key = os.environ.get("ANTHROPIC_API_KEY")
        if env_key:
            return env_key

        if self.config.anthropic_auth_file:
            path = Path(self.config.anthropic_auth_file).expanduser()
            if path.exists():
                try:
                    data = json.loads(path.read_text())
                    return data.get("api_key") or data.get("access_token")
                except Exception:
                    return None

        return None

    def _build_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for m in messages:
            if m.role in ("user", "assistant"):
                out.append({"role": m.role, "content": m.content})
        return out

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Response:
        full_prompt = prompt
        if context:
            ctx = "\n\n".join(f"# {k}\n{v}" for k, v in context.items())
            full_prompt = f"{ctx}\n\n# Current Request\n{prompt}"

        messages = [Message(role="user", content=full_prompt)]
        return self.chat(messages=messages, tools=tools)

    def chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Response:
        if not self._api_key:
            return Response(
                content=(
                    "Error: Anthropic auth missing. Set ANTHROPIC_API_KEY / LIBRE_CLAW_BACKEND__ANTHROPIC_API_KEY "
                    "or provide anthropic_auth_file JSON with api_key."
                ),
                stop_reason="auth_missing",
            )

        system_parts = [m.content for m in messages if m.role == "system"]
        system_text = "\n\n".join(system_parts) if system_parts else None

        payload = {
            "model": self._model,
            "max_tokens": self.config.max_tokens,
            "messages": self._build_messages(messages),
        }
        if system_text:
            payload["system"] = system_text

        try:
            res = self._client.post(
                f"{self._base_url}/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )

            if res.status_code >= 400:
                return Response(content=f"Error: Anthropic HTTP {res.status_code}: {res.text}", stop_reason="error")

            data = res.json()
            text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")

            usage = data.get("usage")
            return Response(
                content=text,
                usage=usage,
                model=data.get("model", self._model),
                stop_reason=data.get("stop_reason"),
            )
        except Exception as e:
            return Response(content=f"Error: {e}", stop_reason="error")

    def check_available(self) -> bool:
        return bool(self._api_key)
