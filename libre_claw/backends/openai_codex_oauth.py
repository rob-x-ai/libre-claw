"""Standalone OpenAI Codex OAuth backend.

Reads OAuth access token from auth-profiles.json (OpenClaw-compatible format),
then calls OpenAI Chat Completions directly.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from .base import BackendConfig, BaseBackend, Message, Response


class OpenAICodexOAuthBackend(BaseBackend):
    def __init__(self, config: Optional[BackendConfig] = None):
        super().__init__(config)
        self._base_url = self.config.openai_codex_base_url.rstrip("/")
        self._model = self.config.openai_codex_model
        self._access = self._resolve_access_token()
        self._client = httpx.Client(timeout=300.0)

    @property
    def name(self) -> str:
        return "openai-codex-oauth"

    @property
    def supports_tools(self) -> bool:
        return False

    def _resolve_access_token(self) -> Optional[str]:
        profiles_path = Path(
            self.config.openai_codex_auth_profiles_file
            or "~/.openclaw/agents/main/agent/auth-profiles.json"
        ).expanduser()
        if not profiles_path.exists():
            return None

        try:
            data = json.loads(profiles_path.read_text())
            profiles = data.get("profiles", {})
            profile_name = self.config.openai_codex_profile or "openai-codex:default"
            profile = profiles.get(profile_name) or {}
            if profile.get("provider") != "openai-codex":
                return None
            return profile.get("access")
        except Exception:
            return None

    def _build_messages(self, messages: List[Message], system_prompt: Optional[str] = None) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        if system_prompt:
            out.append({"role": "system", "content": system_prompt})
        for msg in messages:
            if msg.role in ("user", "assistant", "system"):
                out.append({"role": msg.role, "content": msg.content})
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
        return self.chat([Message(role="user", content=full_prompt)])

    def chat(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None) -> Response:
        if not self._access:
            return Response(
                content=(
                    "Error: openai-codex oauth token missing. "
                    "Run 'codex login' and ensure auth-profiles.json contains openai-codex:default."
                ),
                stop_reason="auth_missing",
            )

        payload = {
            "model": self._model,
            "messages": self._build_messages(messages),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        try:
            res = self._client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._access}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if res.status_code >= 400:
                return Response(content=f"Error: OpenAI Codex HTTP {res.status_code}: {res.text}", stop_reason="error")

            data = res.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            return Response(
                content=message.get("content", ""),
                usage=data.get("usage"),
                model=data.get("model", self._model),
                stop_reason=choice.get("finish_reason"),
            )
        except Exception as e:
            return Response(content=f"Error: {e}", stop_reason="error")

    def list_models(self) -> List[str]:
        # Curated known codex model ids for picker UX.
        return [
            "openai-codex/gpt-5.1",
            "openai-codex/gpt-5.1-codex-max",
            "openai-codex/gpt-5.1-codex-mini",
            "openai-codex/gpt-5.2",
            "openai-codex/gpt-5.2-codex",
            "openai-codex/gpt-5.3-codex",
            "openai-codex/gpt-5.3-codex-spark",
        ]

    def check_available(self) -> bool:
        return bool(self._access)
