# Copyright 2026 Kroonen AI (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
import shlex
from typing import Any

from libre_claw.core.tools import BaseTool, ToolResult, register_tool


MAX_SKILLS_OUTPUT_CHARS = 40000


@register_tool
class SkillsSearchTool(BaseTool):
    name = "skills_search"
    description = (
        "Search the open agent skills ecosystem through the configured Vercel Skills CLI. "
        "Use this when a specialized task may have an existing reusable AgentSkills-compatible workflow."
    )
    parameters = {
        "query": {"type": "string", "description": "Skill search keywords, for example 'react performance'."},
        "owner": {"type": "string", "description": "Optional GitHub owner or organization to scope the search.", "default": ""},
        "max_output_chars": {
            "type": "integer",
            "description": f"Maximum CLI output characters to return, capped at {MAX_SKILLS_OUTPUT_CHARS}.",
            "default": 12000,
        },
    }
    required = ("query",)
    permission_level = "allow"

    async def execute(self, query: str, owner: str = "", max_output_chars: int = 12000) -> ToolResult:
        if not self.context.skills_enabled:
            return ToolResult(error="skills_search is disabled by [skills].enabled")
        if not self.context.skills_external_discovery_enabled:
            return ToolResult(error="skills_search is disabled by [skills].external_discovery_enabled")
        if not self.context.skills_cli_enabled:
            return ToolResult(error="skills_search is disabled by [skills].cli_enabled")

        query = " ".join(str(query).split())
        owner = str(owner).strip()
        if not query:
            return ToolResult(error="query must not be empty")
        if max_output_chars < 1:
            return ToolResult(error="max_output_chars must be >= 1")
        if max_output_chars > MAX_SKILLS_OUTPUT_CHARS:
            return ToolResult(error=f"max_output_chars must be <= {MAX_SKILLS_OUTPUT_CHARS}")

        base_command = shlex.split(self.context.skills_cli_command)
        if not base_command:
            return ToolResult(error="[skills].cli_command must not be empty")
        command = [*base_command, "find", query]
        if owner:
            command.extend(["--owner", owner])

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=self.context.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            return ToolResult(error=f"Could not start skills CLI: {exc}")

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=self.context.skills_cli_timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return ToolResult(error=f"skills_search timed out after {self.context.skills_cli_timeout} seconds")

        stdout = stdout_bytes.decode("utf-8", "replace")
        stderr = stderr_bytes.decode("utf-8", "replace")
        text = _compact(stdout.strip() or stderr.strip(), max_output_chars)
        exit_code = process.returncode if process.returncode is not None else 0
        if exit_code != 0:
            return ToolResult(
                error=f"skills_search exited with {exit_code}: {text}",
                metadata=_metadata(command, query, owner, exit_code, stdout, stderr, text),
            )

        content = "\n".join(
            [
                f"skills_search: {query}",
                f"owner: {owner or 'any'}",
                "",
                text or "No skills output returned.",
            ]
        ).rstrip()
        return ToolResult(
            content=content,
            metadata=_metadata(command, query, owner, exit_code, stdout, stderr, text),
        )


def _compact(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + f"\n... truncated {len(text) - limit} characters ..."


def _metadata(
    command: list[str],
    query: str,
    owner: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    returned: str,
) -> dict[str, Any]:
    return {
        "artifact_type": "skills_search",
        "command": command,
        "query": query,
        "owner": owner,
        "exit_code": exit_code,
        "stdout_chars": len(stdout),
        "stderr_chars": len(stderr),
        "truncated": len(returned) < len(stdout.strip() or stderr.strip()),
    }
