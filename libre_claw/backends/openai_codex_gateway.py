"""OpenClaw-style OpenAI Codex OAuth backend via local OpenClaw gateway."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from .base import BackendConfig, BaseBackend, Message, Response


class OpenAICodexGatewayBackend(BaseBackend):
    def __init__(self, config: Optional[BackendConfig] = None):
        super().__init__(config)
        self._gateway_url = (self.config.openclaw_gateway_url or "http://127.0.0.1:18789").rstrip("/")
        self._model = self.config.openai_codex_model
        self._token = self._resolve_gateway_token()
        self._client = httpx.Client(timeout=300.0)

    @property
    def name(self) -> str:
        return "openai-codex"

    @property
    def supports_tools(self) -> bool:
        return False

    def _resolve_gateway_token(self) -> Optional[str]:
        if self.config.openclaw_gateway_token:
            return self.config.openclaw_gateway_token

        cfg_path = Path.home() / ".openclaw" / "openclaw.json"
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text())
                return data.get("gateway", {}).get("auth", {}).get("token")
            except Exception:
                return None
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
        if not self._token:
            return Response(content="Error: OpenClaw gateway token not found.", stop_reason="auth_missing")

        payload = {
            "model": self._model,
            "messages": self._build_messages(messages),
        }
        try:
            res = self._client.post(
                f"{self._gateway_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if res.status_code >= 400:
                return Response(content=f"Error: OpenClaw gateway HTTP {res.status_code}: {res.text}", stop_reason="error")
            data = res.json()
            choice = (data.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            return Response(
                content=msg.get("content", ""),
                usage=data.get("usage"),
                model=data.get("model", self._model),
                stop_reason=choice.get("finish_reason"),
            )
        except Exception as e:
            return Response(content=f"Error: {e}", stop_reason="error")

    def check_available(self) -> bool:
        if not self._token:
            return False
        try:
            r = self._client.get(f"{self._gateway_url}/v1/models", headers={"Authorization": f"Bearer {self._token}"})
            return r.status_code == 200
        except Exception:
            return False
