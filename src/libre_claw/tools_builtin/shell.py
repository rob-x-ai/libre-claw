# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
import codecs
import os
import signal
import time
from dataclasses import dataclass
from typing import Any

from libre_claw.core.sandbox import SandboxViolation
from libre_claw.core.tools import BaseTool, ToolResult, register_tool


DEFAULT_MAX_OUTPUT_CHARS = 20000
MAX_OUTPUT_CHARS = 100000
STREAM_READ_CHUNK_SIZE = 8192


@dataclass(frozen=True)
class CapturedOutput:
    text: str
    total_chars: int
    total_bytes: int
    truncated: bool


@register_tool
class BashTool(BaseTool):
    name = "bash"
    description = "Execute a shell command with timeout, sandbox checks, and bounded captured output."
    parameters = {
        "command": {"type": "string", "description": "Shell command to execute"},
        "timeout": {"type": "integer", "description": "Timeout in seconds", "default": None},
        "max_output_chars": {
            "type": "integer",
            "description": f"Maximum stdout/stderr characters to return per stream, capped at {MAX_OUTPUT_CHARS}",
            "default": DEFAULT_MAX_OUTPUT_CHARS,
        },
    }
    required = ("command",)
    permission_level = "ask"

    async def execute(
        self,
        command: str,
        timeout: int | None = None,
        max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
    ) -> ToolResult:
        try:
            self.context.sandbox_policy().validate_command(command)
        except SandboxViolation as exc:
            return ToolResult(error=str(exc))

        timeout_value = self.context.command_timeout if timeout is None else timeout
        if timeout_value < 1:
            return ToolResult(error="timeout must be >= 1")
        if max_output_chars < 1:
            return ToolResult(error="max_output_chars must be >= 1")
        if max_output_chars > MAX_OUTPUT_CHARS:
            return ToolResult(error=f"max_output_chars must be <= {MAX_OUTPUT_CHARS}")

        process: asyncio.subprocess.Process | None = None
        started_at = time.monotonic()

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=str(self.context.working_directory),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=os.name != "nt",
            )
            stdout_task = asyncio.create_task(_read_stream(process.stdout, max_output_chars))
            stderr_task = asyncio.create_task(_read_stream(process.stderr, max_output_chars))
            try:
                await asyncio.wait_for(process.wait(), timeout=timeout_value)
            except asyncio.TimeoutError:
                _terminate_process(process)
                await process.wait()
                await _cancel_reader_tasks(stdout_task, stderr_task)
                return ToolResult(error=f"Command timed out after {timeout_value} seconds")
            stdout_capture, stderr_capture = await asyncio.gather(stdout_task, stderr_task)
        except asyncio.TimeoutError:
            if process is not None:
                _terminate_process(process)
                await process.wait()
            return ToolResult(error=f"Command timed out after {timeout_value} seconds")
        except asyncio.CancelledError:
            if process is not None and process.returncode is None:
                _terminate_process(process)
                await process.wait()
            if "stdout_task" in locals() and "stderr_task" in locals():
                await _cancel_reader_tasks(stdout_task, stderr_task)
            raise
        except OSError as exc:
            return ToolResult(error=str(exc))

        stdout_display = _display_output(stdout_capture)
        stderr_display = _display_output(stderr_capture)
        duration_ms = int((time.monotonic() - started_at) * 1000)
        content = _format_command_output(process.returncode or 0, stdout_display, stderr_display, duration_ms)
        return ToolResult(
            content=content,
            metadata={
                "exit_code": process.returncode,
                "stdout": stdout_display,
                "stderr": stderr_display,
                "stdout_truncated": stdout_capture.truncated,
                "stderr_truncated": stderr_capture.truncated,
                "stdout_chars": stdout_capture.total_chars,
                "stderr_chars": stderr_capture.total_chars,
                "stdout_bytes": stdout_capture.total_bytes,
                "stderr_bytes": stderr_capture.total_bytes,
                "duration_ms": duration_ms,
            },
        )


def _format_command_output(exit_code: int, stdout: str, stderr: str, duration_ms: int) -> str:
    sections = [f"exit_code: {exit_code}", f"duration_ms: {duration_ms}"]
    if stdout:
        sections.append("stdout:\n" + stdout.rstrip())
    if stderr:
        sections.append("stderr:\n" + stderr.rstrip())
    return "\n".join(sections)


async def _read_stream(
    stream: asyncio.StreamReader | None,
    max_chars: int,
) -> CapturedOutput:
    if stream is None:
        return CapturedOutput(text="", total_chars=0, total_bytes=0, truncated=False)

    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    parts: list[str] = []
    stored_chars = 0
    total_chars = 0
    total_bytes = 0

    while True:
        chunk = await stream.read(STREAM_READ_CHUNK_SIZE)
        if not chunk:
            break
        total_bytes += len(chunk)
        text = decoder.decode(chunk, final=False)
        total_chars += len(text)
        stored_chars = _append_capped(parts, text, stored_chars, max_chars)

    tail = decoder.decode(b"", final=True)
    if tail:
        total_chars += len(tail)
        stored_chars = _append_capped(parts, tail, stored_chars, max_chars)

    return CapturedOutput(
        text="".join(parts),
        total_chars=total_chars,
        total_bytes=total_bytes,
        truncated=total_chars > stored_chars,
    )


def _append_capped(parts: list[str], text: str, stored_chars: int, max_chars: int) -> int:
    if not text or stored_chars >= max_chars:
        return stored_chars

    available = max_chars - stored_chars
    chunk = text[:available]
    parts.append(chunk)
    return stored_chars + len(chunk)


def _display_output(output: CapturedOutput) -> str:
    if not output.truncated:
        return output.text
    omitted = output.total_chars - len(output.text)
    suffix = f"\n... truncated {omitted} characters ..."
    return output.text + suffix


async def _cancel_reader_tasks(*tasks: asyncio.Task[CapturedOutput]) -> None:
    for task in tasks:
        if not task.done():
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def _terminate_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    if os.name == "nt":
        process.kill()
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except OSError:
        process.kill()
