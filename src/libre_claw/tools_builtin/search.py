# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
import codecs
import fnmatch
import os
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from libre_claw.core.tools import BaseTool, ToolResult, register_tool


MAX_GLOB_RESULTS = 2000
MAX_SEARCH_MATCHES = 500
MAX_SEARCH_CONTEXT = 5
MAX_SEARCH_OUTPUT_CHARS = 60000
SEARCH_TIMEOUT_SECONDS = 30
IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        "dist",
        "build",
        "htmlcov",
    }
)


@dataclass(frozen=True)
class CommandCapture:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False


@register_tool
class GlobTool(BaseTool):
    name = "glob"
    description = "Find files and directories matching a glob pattern within the sandboxed working directory."
    parameters = {
        "pattern": {"type": "string", "description": "Glob pattern such as '*.py' or '**/*.md'"},
        "path": {"type": "string", "description": "Directory to search from", "default": "."},
        "max_results": {
            "type": "integer",
            "description": f"Maximum number of matching paths to return, capped at {MAX_GLOB_RESULTS}",
            "default": 500,
        },
        "include_hidden": {"type": "boolean", "description": "Include dotfiles and hidden directories", "default": False},
    }
    required = ("pattern",)
    permission_level = "allow"

    async def execute(
        self,
        pattern: str,
        path: str = ".",
        max_results: int = 500,
        include_hidden: bool = False,
    ) -> ToolResult:
        try:
            return await asyncio.to_thread(self._glob, pattern, path, max_results, include_hidden)
        except Exception as exc:
            return ToolResult(error=str(exc))

    def _glob(self, pattern: str, path: str, max_results: int, include_hidden: bool) -> ToolResult:
        pattern = pattern.strip()
        if not pattern:
            return ToolResult(error="pattern must not be empty")
        if max_results < 1:
            return ToolResult(error="max_results must be >= 1")
        if max_results > MAX_GLOB_RESULTS:
            return ToolResult(error=f"max_results must be <= {MAX_GLOB_RESULTS}")

        root = self.resolve_path(path)
        if not root.exists():
            return ToolResult(error=f"Directory does not exist: {root}")
        if not root.is_dir():
            return ToolResult(error=f"Path is not a directory: {root}")

        matches: list[str] = []
        truncated = False
        for candidate in _walk_paths(root, include_hidden=include_hidden):
            rel = candidate.relative_to(root).as_posix()
            if _matches_glob(rel, pattern):
                matches.append(rel + ("/" if candidate.is_dir() else ""))
                if len(matches) >= max_results:
                    truncated = True
                    break

        content = "\n".join(matches)
        if truncated:
            content += f"\n... truncated after {len(matches)} results; narrow the pattern or raise max_results"
        return ToolResult(
            content=content,
            metadata={
                "path": str(root),
                "pattern": pattern,
                "result_count": len(matches),
                "truncated": truncated,
                "max_results": max_results,
            },
        )


@register_tool
class SearchFilesTool(BaseTool):
    name = "search_files"
    description = "Search file contents with ripgrep when available, falling back to bounded Python text search."
    parameters = {
        "query": {"type": "string", "description": "Text or regex pattern to search for"},
        "path": {"type": "string", "description": "Directory or file to search", "default": "."},
        "glob": {"type": "string", "description": "Optional file glob filter, for example '*.py'", "default": ""},
        "case_sensitive": {"type": "boolean", "description": "Use case-sensitive matching", "default": False},
        "context": {
            "type": "integer",
            "description": f"Context lines before and after each match, capped at {MAX_SEARCH_CONTEXT}",
            "default": 0,
        },
        "max_matches": {
            "type": "integer",
            "description": f"Maximum matching lines to return, capped at {MAX_SEARCH_MATCHES}",
            "default": 100,
        },
        "include_hidden": {"type": "boolean", "description": "Include dotfiles and hidden directories", "default": False},
    }
    required = ("query",)
    permission_level = "allow"

    async def execute(
        self,
        query: str,
        path: str = ".",
        glob: str = "",
        case_sensitive: bool = False,
        context: int = 0,
        max_matches: int = 100,
        include_hidden: bool = False,
    ) -> ToolResult:
        try:
            return await self._search(query, path, glob, case_sensitive, context, max_matches, include_hidden)
        except Exception as exc:
            return ToolResult(error=str(exc))

    async def _search(
        self,
        query: str,
        path: str,
        glob: str,
        case_sensitive: bool,
        context: int,
        max_matches: int,
        include_hidden: bool,
    ) -> ToolResult:
        query = query.strip()
        if not query:
            return ToolResult(error="query must not be empty")
        if context < 0:
            return ToolResult(error="context must be >= 0")
        if context > MAX_SEARCH_CONTEXT:
            return ToolResult(error=f"context must be <= {MAX_SEARCH_CONTEXT}")
        if max_matches < 1:
            return ToolResult(error="max_matches must be >= 1")
        if max_matches > MAX_SEARCH_MATCHES:
            return ToolResult(error=f"max_matches must be <= {MAX_SEARCH_MATCHES}")

        root = self.resolve_path(path)
        if not root.exists():
            return ToolResult(error=f"Path does not exist: {root}")

        rg = shutil.which("rg")
        if rg is not None:
            result = await _search_with_rg(rg, root, query, glob, case_sensitive, context, max_matches, include_hidden)
            if result is not None:
                return result

        return await asyncio.to_thread(
            _search_with_python,
            root,
            query,
            glob,
            case_sensitive,
            context,
            max_matches,
            include_hidden,
        )


def _walk_paths(root: Path, include_hidden: bool) -> Iterator[Path]:
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [
            name
            for name in sorted(dirnames)
            if (include_hidden or not name.startswith(".")) and name not in IGNORED_DIRECTORIES
        ]
        base = Path(directory)
        for name in sorted(dirnames):
            yield base / name
        for name in sorted(filenames):
            if include_hidden or not name.startswith("."):
                yield base / name


def _matches_glob(path: str, pattern: str) -> bool:
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(Path(path).name, pattern)


async def _search_with_rg(
    rg: str,
    root: Path,
    query: str,
    glob: str,
    case_sensitive: bool,
    context: int,
    max_matches: int,
    include_hidden: bool,
) -> ToolResult | None:
    args = [
        rg,
        "--line-number",
        "--column",
        "--no-heading",
        "--color=never",
        "--max-filesize",
        "10M",
    ]
    if not case_sensitive:
        args.append("--ignore-case")
    if context:
        args.extend(["--context", str(context)])
    if include_hidden:
        args.append("--hidden")
    for ignored in sorted(IGNORED_DIRECTORIES):
        args.extend(["--glob", f"!{ignored}/**"])
    if glob:
        args.extend(["--glob", glob])
    args.extend(["--", query, str(root)])

    capture = await _run_capped(args, cwd=root if root.is_dir() else root.parent)
    if capture.timed_out:
        return ToolResult(error=f"search_files timed out after {SEARCH_TIMEOUT_SECONDS} seconds")
    if capture.exit_code not in {0, 1}:
        return None

    lines = [line for line in capture.stdout.splitlines() if line]
    truncated = capture.stdout_truncated or len(lines) > max_matches
    selected = lines[:max_matches]
    content = "\n".join(_relativize_rg_line(line, root) for line in selected)
    if truncated:
        content += f"\n... truncated after {len(selected)} matches; narrow query/path or raise max_matches"
    return ToolResult(
        content=content,
        metadata={
            "path": str(root),
            "query": query,
            "glob": glob,
            "match_count": len(selected),
            "truncated": truncated,
            "engine": "rg",
            "stderr": capture.stderr,
        },
    )


def _search_with_python(
    root: Path,
    query: str,
    glob: str,
    case_sensitive: bool,
    context: int,
    max_matches: int,
    include_hidden: bool,
) -> ToolResult:
    files = (root,) if root.is_file() else (path for path in _walk_paths(root, include_hidden) if path.is_file())
    needle = query if case_sensitive else query.lower()
    matches: list[str] = []
    truncated = False

    for file_path in files:
        rel = file_path.name if root.is_file() else file_path.relative_to(root).as_posix()
        if glob and not _matches_glob(rel, glob):
            continue
        try:
            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_index, line in enumerate(lines):
            haystack = line if case_sensitive else line.lower()
            if needle not in haystack:
                continue
            if context:
                start = max(0, line_index - context)
                end = min(len(lines), line_index + context + 1)
                for context_index in range(start, end):
                    prefix = ":" if context_index == line_index else "-"
                    matches.append(f"{rel}:{context_index + 1}{prefix}{lines[context_index]}")
            else:
                matches.append(f"{rel}:{line_index + 1}:{line}")
            if len(matches) >= max_matches:
                truncated = True
                break
        if truncated:
            break

    content = "\n".join(matches)
    if truncated:
        content += f"\n... truncated after {len(matches)} matches; narrow query/path or raise max_matches"
    return ToolResult(
        content=content,
        metadata={
            "path": str(root),
            "query": query,
            "glob": glob,
            "match_count": len(matches),
            "truncated": truncated,
            "engine": "python",
        },
    )


async def _run_capped(args: list[str], cwd: Path) -> CommandCapture:
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_task = asyncio.create_task(_read_stream_capped(process.stdout, MAX_SEARCH_OUTPUT_CHARS))
    stderr_task = asyncio.create_task(_read_stream_capped(process.stderr, MAX_SEARCH_OUTPUT_CHARS))
    try:
        await asyncio.wait_for(process.wait(), timeout=SEARCH_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        await _cancel_reader_tasks(stdout_task, stderr_task)
        return CommandCapture(stdout="", stderr="", exit_code=-1, timed_out=True)

    stdout_text, stdout_truncated = await stdout_task
    stderr_text, stderr_truncated = await stderr_task
    return CommandCapture(
        stdout=stdout_text,
        stderr=stderr_text,
        exit_code=process.returncode or 0,
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
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


def _relativize_rg_line(line: str, root: Path) -> str:
    prefix, separator, rest = line.partition(":")
    if not separator:
        return line
    try:
        rel = Path(prefix).resolve().relative_to(root if root.is_dir() else root.parent).as_posix()
    except ValueError:
        rel = prefix
    return rel + separator + rest
