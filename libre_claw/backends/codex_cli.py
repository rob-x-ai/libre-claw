"""Codex CLI backend for Libre Claw.

Uses local Codex login session (ChatGPT OAuth) via `codex exec`.
"""

import subprocess
import tempfile
from typing import Any, Dict, List, Optional

from .base import BackendConfig, BaseBackend, Message, Response


class CodexCLIBackend(BaseBackend):
    def __init__(self, config: Optional[BackendConfig] = None):
        super().__init__(config)
        self._codex_path = self.config.codex_path

    @property
    def name(self) -> str:
        return "codex-cli"

    @property
    def supports_tools(self) -> bool:
        return False

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Response:
        parts = []
        if system_prompt:
            parts.append(f"<system>\n{system_prompt}\n</system>")
        if context:
            for filename, content in context.items():
                parts.append(f"<file name=\"{filename}\">\n{content}\n</file>")
        parts.append(prompt)
        full_prompt = "\n\n".join(parts)

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=True) as out:
            cmd = [
                self._codex_path,
                "exec",
                "--skip-git-repo-check",
                "--output-last-message",
                out.name,
                full_prompt,
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode != 0:
                    return Response(content=f"Error: Codex exec failed: {result.stderr.strip()}", stop_reason="error")

                out.seek(0)
                content = out.read().decode("utf-8").strip()
                if not content:
                    # fallback to stdout
                    content = result.stdout.strip()

                return Response(content=content, model="codex-cli", stop_reason="end_turn")
            except FileNotFoundError:
                return Response(content=f"Error: Codex CLI not found at {self._codex_path}", stop_reason="error")
            except Exception as e:
                return Response(content=f"Error: {e}", stop_reason="error")

    def chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Response:
        parts = []
        system = None
        for msg in messages:
            if msg.role == "system":
                system = msg.content
            elif msg.role == "user":
                parts.append(f"Human: {msg.content}")
            elif msg.role == "assistant":
                parts.append(f"Assistant: {msg.content}")

        return self.complete(prompt="\n\n".join(parts), system_prompt=system)

    def check_available(self) -> bool:
        try:
            status = subprocess.run([self._codex_path, "login", "status"], capture_output=True, text=True, timeout=10)
            return status.returncode == 0 and "Logged in" in status.stdout
        except Exception:
            return False
