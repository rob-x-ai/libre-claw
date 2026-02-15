"""Claude Code backend for Libre Claw.

Wraps the Claude Code CLI (`claude -p`) for programmatic access.
"""

import json
import subprocess
from typing import Any, Dict, List, Optional

from .base import BackendConfig, BaseBackend, Message, Response


class ClaudeCodeBackend(BaseBackend):
    """Backend that uses Claude Code CLI for completions.

    Requires Claude Code CLI v2.1.42+ installed and accessible.
    """

    def __init__(self, config: Optional[BackendConfig] = None):
        """Initialize Claude Code backend.

        Args:
            config: Backend configuration
        """
        super().__init__(config)
        self._claude_path = self.config.claude_path

    @property
    def name(self) -> str:
        """Get the backend name."""
        return "claude-code"

    @property
    def supports_tools(self) -> bool:
        """Claude Code supports tool calls."""
        return True

    def _build_prompt(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, str]] = None,
    ) -> str:
        """Build the full prompt for Claude Code.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            context: Optional workspace context files

        Returns:
            Formatted prompt string
        """
        parts = []

        # Add system prompt
        if system_prompt:
            parts.append(f"System: {system_prompt}")

        # Add workspace context
        if context:
            for filename, content in context.items():
                parts.append(f"\n# {filename}\n{content}\n")

        # Add current prompt
        parts.append(f"\n# Current Request\n{prompt}")

        return "\n".join(parts)

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Response:
        """Generate a completion using Claude Code CLI.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            context: Optional context from workspace files
            tools: Optional tool definitions

        Returns:
            Response object with completion content
        """
        full_prompt = self._build_prompt(prompt, system_prompt, context)

        # Build command
        cmd = [
            self._claude_path,
            "-p",
            "--output-format",
            "json",
        ]

        # Add tools if provided
        if tools:
            tools_json = json.dumps(tools)
            cmd.extend(["--tools", tools_json])

        try:
            result = subprocess.run(
                cmd,
                input=full_prompt,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                return Response(
                    content=f"Error: Claude Code failed with code {result.returncode}\n{result.stderr}",
                    stop_reason="error",
                )

            # Parse JSON output
            output = result.stdout.strip()
            if not output:
                return Response(
                    content="Error: No output from Claude Code",
                    stop_reason="error",
                )

            # Claude Code JSON output format
            data = json.loads(output)

            return Response(
                content=data.get("content", ""),
                tool_calls=data.get("tool_calls", []),
                usage=data.get("usage", {}),
                model=data.get("model", "claude-code"),
                stop_reason=data.get("stop_reason"),
            )

        except subprocess.TimeoutExpired:
            return Response(
                content="Error: Claude Code timed out after 5 minutes",
                stop_reason="timeout",
            )
        except json.JSONDecodeError as e:
            return Response(
                content=f"Error: Failed to parse Claude Code output: {e}\nOutput: {result.stdout}",
                stop_reason="parse_error",
            )
        except Exception as e:
            return Response(
                content=f"Error: {str(e)}",
                stop_reason="error",
            )

    def chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Response:
        """Generate a chat completion using Claude Code CLI.

        Args:
            messages: List of conversation messages
            tools: Optional tool definitions

        Returns:
            Response object with completion content
        """
        # Build prompt from messages
        prompt_parts = []
        for msg in messages:
            if msg.role == "user":
                prompt_parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                prompt_parts.append(f"Assistant: {msg.content}")
            elif msg.role == "tool":
                prompt_parts.append(f"Tool ({msg.tool_call_id}): {msg.content}")

        prompt = "\n".join(prompt_parts)

        return self.complete(prompt=prompt, tools=tools)

    def check_available(self) -> bool:
        """Check if Claude Code CLI is available.

        Returns:
            True if Claude Code is available and working
        """
        try:
            result = subprocess.run(
                [self._claude_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_version(self) -> Optional[str]:
        """Get Claude Code version.

        Returns:
            Version string or None if not available
        """
        try:
            result = subprocess.run(
                [self._claude_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None
