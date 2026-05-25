# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from libre_claw.core.tools import BaseTool, ToolResult, register_tool


MAX_THOUGHT_CHARS = 12000


@register_tool
class ThinkTool(BaseTool):
    name = "think"
    description = "Record a bounded private scratchpad note for planning. This tool has no side effects."
    parameters = {
        "thought": {
            "type": "string",
            "description": f"Reasoning scratchpad note, capped at {MAX_THOUGHT_CHARS} characters",
        }
    }
    required = ("thought",)
    permission_level = "allow"

    async def execute(self, thought: str) -> ToolResult:
        if not thought.strip():
            return ToolResult(error="thought must not be empty")
        if len(thought) > MAX_THOUGHT_CHARS:
            return ToolResult(error=f"thought must be <= {MAX_THOUGHT_CHARS} characters")
        return ToolResult(
            content="Thought noted.",
            metadata={
                "characters": len(thought),
                "side_effects": False,
            },
        )
