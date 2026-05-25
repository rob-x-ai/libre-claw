# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
import builtins
import codecs
import time
from dataclasses import dataclass
from pathlib import Path

from libre_claw.core.sandbox import SandboxViolation
from libre_claw.core.tools import BaseTool, ToolResult, register_tool


MAX_GIT_OUTPUT_CHARS = 60000
MAX_GIT_LOG_COUNT = 50
MAX_GIT_DIFF_CONTEXT = 20
GIT_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class GitCommandResult:
    args: tuple[str, ...]
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    truncated: bool

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@register_tool
class GitStatusTool(BaseTool):
    name = "git_status"
    description = "Inspect git status, recent commits, and optionally a bounded working-tree diff."
    parameters = {
        "path": {"type": "string", "description": "Repository path to inspect", "default": "."},
        "show_diff": {"type": "boolean", "description": "Include a bounded git diff", "default": True},
        "diff_context": {
            "type": "integer",
            "description": f"Unified diff context lines, capped at {MAX_GIT_DIFF_CONTEXT}",
            "default": 3,
        },
        "log_count": {
            "type": "integer",
            "description": f"Recent commits to include, capped at {MAX_GIT_LOG_COUNT}",
            "default": 5,
        },
    }
    permission_level = "allow"

    async def execute(
        self,
        path: str = ".",
        show_diff: bool = True,
        diff_context: int = 3,
        log_count: int = 5,
    ) -> ToolResult:
        if diff_context < 0:
            return ToolResult(error="diff_context must be >= 0")
        if diff_context > MAX_GIT_DIFF_CONTEXT:
            return ToolResult(error=f"diff_context must be <= {MAX_GIT_DIFF_CONTEXT}")
        if log_count < 0:
            return ToolResult(error="log_count must be >= 0")
        if log_count > MAX_GIT_LOG_COUNT:
            return ToolResult(error=f"log_count must be <= {MAX_GIT_LOG_COUNT}")

        try:
            repo_path = self.resolve_path(path)
        except SandboxViolation as exc:
            return ToolResult(error=str(exc))
        if not repo_path.exists():
            return ToolResult(error=f"Path does not exist: {repo_path}")

        root_result = await _git(repo_path, "rev-parse", "--show-toplevel")
        if not root_result.ok:
            return ToolResult(error=_git_error("Not a git repository", root_result))
        repo_root = Path(root_result.stdout.strip())

        status = await _git(repo_root, "status", "--short", "--branch")
        diff_stat = await _git(repo_root, "diff", "--stat")
        log = await _git(repo_root, "log", "--oneline", "--decorate", f"-n{log_count}") if log_count else None
        diff = await _git(repo_root, "diff", f"--unified={diff_context}") if show_diff else None

        for label, result in (("status", status), ("diff stat", diff_stat), ("log", log), ("diff", diff)):
            if result is not None and not result.ok:
                return ToolResult(error=_git_error(f"git {label} failed", result))

        sections = [
            f"repo: {repo_root}",
            "status:\n" + (status.stdout.strip() or "clean"),
            "diff_stat:\n" + (diff_stat.stdout.strip() or "no working tree diff"),
        ]
        if log is not None:
            sections.append("recent_commits:\n" + (log.stdout.strip() or "no commits"))
        if diff is not None:
            sections.append("diff:\n" + (diff.stdout.strip() or "no working tree diff"))

        truncated = any(result.truncated for result in (status, diff_stat, log, diff) if result is not None)
        return ToolResult(
            content="\n\n".join(sections),
            metadata={
                "repo_root": str(repo_root),
                "show_diff": show_diff,
                "diff_context": diff_context,
                "log_count": log_count,
                "truncated": truncated,
            },
        )


@register_tool
class GitCommitTool(BaseTool):
    name = "git_commit"
    description = "Stage selected sandboxed paths or all changes, then create a git commit. This tool never pushes."
    parameters = {
        "message": {"type": "string", "description": "Commit message"},
        "paths": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific paths to stage before committing",
            "default": [],
        },
        "all": {"type": "boolean", "description": "Stage all changes in the repository", "default": False},
    }
    required = ("message",)
    permission_level = "ask"

    async def execute(
        self,
        message: str,
        paths: list[str] | None = None,
        all: bool = False,  # noqa: A002 - tool schema uses "all"
    ) -> ToolResult:
        message = message.strip()
        if not message:
            return ToolResult(error="message must not be empty")
        paths = paths or []
        if not isinstance(paths, list) or not builtins.all(isinstance(path, str) for path in paths):
            return ToolResult(error="paths must be a list of strings")
        if all and paths:
            return ToolResult(error="paths and all cannot both be set")
        if not all and not paths:
            return ToolResult(error="provide paths or set all=true")

        repo_path = self.context.working_directory.resolve()
        root_result = await _git(repo_path, "rev-parse", "--show-toplevel")
        if not root_result.ok:
            return ToolResult(error=_git_error("Not a git repository", root_result))
        repo_root = Path(root_result.stdout.strip())

        if self.context.restrict_to_working_dir and not _is_relative_to(repo_root, self.context.working_directory.resolve()):
            return ToolResult(error=f"Git repository root is outside the working directory: {repo_root}")

        if all:
            add_result = await _git(repo_root, "add", "-A")
            staged_paths = ["<all>"]
        else:
            try:
                staged_paths = [_repo_relative_path(self, repo_root, path) for path in paths]
            except SandboxViolation as exc:
                return ToolResult(error=str(exc))
            add_result = await _git(repo_root, "add", "--", *staged_paths)
        if not add_result.ok:
            return ToolResult(error=_git_error("git add failed", add_result))

        has_staged = await _git(repo_root, "diff", "--cached", "--quiet")
        if has_staged.exit_code == 0:
            return ToolResult(error="No staged changes to commit")
        if has_staged.exit_code not in {0, 1}:
            return ToolResult(error=_git_error("git diff --cached failed", has_staged))

        commit = await _git(repo_root, "commit", "-m", message)
        if not commit.ok:
            return ToolResult(error=_git_error("git commit failed", commit))

        rev = await _git(repo_root, "rev-parse", "--short", "HEAD")
        commit_id = rev.stdout.strip() if rev.ok else ""
        return ToolResult(
            content=commit.stdout.strip(),
            metadata={
                "repo_root": str(repo_root),
                "message": message,
                "paths": staged_paths,
                "commit": commit_id,
                "duration_ms": commit.duration_ms,
                "pushed": False,
            },
        )


async def _git(cwd: Path, *args: str) -> GitCommandResult:
    started_at = time.monotonic()
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_task = asyncio.create_task(_read_stream_capped(process.stdout, MAX_GIT_OUTPUT_CHARS))
    stderr_task = asyncio.create_task(_read_stream_capped(process.stderr, MAX_GIT_OUTPUT_CHARS))
    try:
        await asyncio.wait_for(process.wait(), timeout=GIT_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        await _cancel_reader_tasks(stdout_task, stderr_task)
        return GitCommandResult(
            args=("git", *args),
            stdout="",
            stderr=f"git command timed out after {GIT_TIMEOUT_SECONDS} seconds",
            exit_code=-1,
            duration_ms=int((time.monotonic() - started_at) * 1000),
            truncated=False,
        )

    stdout_text, stdout_truncated = await stdout_task
    stderr_text, stderr_truncated = await stderr_task
    return GitCommandResult(
        args=("git", *args),
        stdout=stdout_text,
        stderr=stderr_text,
        exit_code=process.returncode or 0,
        duration_ms=int((time.monotonic() - started_at) * 1000),
        truncated=stdout_truncated or stderr_truncated,
    )


async def _read_stream_capped(stream: asyncio.StreamReader | None, max_chars: int) -> tuple[str, bool]:
    if stream is None:
        return "", False

    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    parts: list[str] = []
    stored_chars = 0
    total_chars = 0
    while True:
        chunk = await stream.read(8192)
        if not chunk:
            break
        text = decoder.decode(chunk, final=False)
        total_chars += len(text)
        if stored_chars < max_chars:
            available = max_chars - stored_chars
            part = text[:available]
            parts.append(part)
            stored_chars += len(part)
    tail = decoder.decode(b"", final=True)
    if tail:
        total_chars += len(tail)
        if stored_chars < max_chars:
            available = max_chars - stored_chars
            part = tail[:available]
            parts.append(part)
            stored_chars += len(part)
    text = "".join(parts)
    if total_chars <= stored_chars:
        return text, False
    return text + f"\n... truncated {total_chars - stored_chars} characters ...", True


async def _cancel_reader_tasks(*tasks: asyncio.Task[tuple[str, bool]]) -> None:
    for task in tasks:
        if not task.done():
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def _repo_relative_path(tool: BaseTool, repo_root: Path, path: str) -> str:
    resolved = tool.resolve_path(path)
    if not _is_relative_to(resolved, repo_root):
        raise SandboxViolation(f"Path is outside the git repository: {resolved}")
    return resolved.relative_to(repo_root).as_posix()


def _git_error(prefix: str, result: GitCommandResult) -> str:
    detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.exit_code}"
    return f"{prefix}: {detail}"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
