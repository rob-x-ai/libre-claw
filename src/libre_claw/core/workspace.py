# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from libre_claw.config import set_global_working_directory
from libre_claw.core.soul import DEFAULT_SOUL_TEMPLATE


WORKSPACE_README = """# Libre Claw Workspace

This is Libre Claw's runtime workspace.

Use it as the agent's stable home for persona, goals, memory notes, and
project-independent context. Keep product source code and throwaway cloned
repositories outside this directory unless you intentionally want the agent to
operate on them from here.

## Files
- `soul.md` shapes Libre Claw's persona and collaboration style.
- `goals.md` can hold active priorities, checklists, or recurring work.
- `memory.md` can hold human-readable pinned memory notes.
- `.libre-claw/skills/` can hold project-scoped skills for this workspace.
"""

GOALS_TEMPLATE = """# Libre Claw Goals

- Keep this workspace useful, calm, and shippable.
- Prefer secure defaults, clear docs, and verified changes.
- Add active priorities here when Libre Claw should remember them explicitly.
"""

MEMORY_TEMPLATE = """# Libre Claw Pinned Memory

Use this file for human-readable memory you want to keep visible in the
workspace. Automatic searchable memory still lives in `~/.libre-claw/memory.db`.
Do not store secrets, tokens, private keys, or passwords here.
"""


@dataclass(frozen=True)
class WorkspaceInitResult:
    path: Path
    source_root: Path
    config_path: Path | None
    created_files: tuple[Path, ...]
    copied_files: tuple[Path, ...]
    skipped_files: tuple[Path, ...]


def default_claw_workspace_path(home: Path | str | None = None) -> Path:
    root = Path(home).expanduser() if home is not None else Path.home()
    return root / "Documents" / ".workspace" / "libre-claw"


def initialize_claw_workspace(
    *,
    source_root: Path | str,
    target: Path | str | None = None,
    set_default: bool = True,
    config_path: Path | str | None = None,
    overwrite: bool = False,
) -> WorkspaceInitResult:
    source = Path(source_root).expanduser().resolve()
    workspace = (Path(target).expanduser() if target is not None else default_claw_workspace_path()).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    copied: list[Path] = []
    skipped: list[Path] = []

    _write_template(workspace / "README.md", WORKSPACE_README, overwrite=overwrite, created=created, skipped=skipped)
    _write_template(workspace / "goals.md", GOALS_TEMPLATE, overwrite=overwrite, created=created, skipped=skipped)
    _write_template(workspace / "memory.md", MEMORY_TEMPLATE, overwrite=overwrite, created=created, skipped=skipped)

    _copy_markdown_file(source / "soul.md", workspace / "soul.md", overwrite=overwrite, copied=copied, skipped=skipped)
    if not (workspace / "soul.md").exists():
        _write_template(workspace / "soul.md", DEFAULT_SOUL_TEMPLATE, overwrite=overwrite, created=created, skipped=skipped)

    _copy_markdown_file(
        source / ".libre-claw" / "soul.md",
        workspace / ".libre-claw" / "soul.md",
        overwrite=overwrite,
        copied=copied,
        skipped=skipped,
    )
    _copy_markdown_tree(
        source / ".libre-claw" / "skills",
        workspace / ".libre-claw" / "skills",
        overwrite=overwrite,
        copied=copied,
        skipped=skipped,
    )

    written_config = set_global_working_directory(workspace, config_path=config_path) if set_default else None
    return WorkspaceInitResult(
        path=workspace,
        source_root=source,
        config_path=written_config,
        created_files=tuple(created),
        copied_files=tuple(copied),
        skipped_files=tuple(skipped),
    )


def workspace_status_text(working_directory: Path | str) -> str:
    current = Path(working_directory).expanduser().resolve()
    default_path = default_claw_workspace_path()
    state = "exists" if default_path.exists() else "missing"
    return "\n".join(
        [
            "Libre Claw workspace:",
            f"- current working directory: {current}",
            f"- default workspace: {default_path} ({state})",
            "Use `libre-claw workspace init` or `/workspace init` to create and use it.",
        ]
    )


def workspace_result_text(result: WorkspaceInitResult) -> str:
    lines = [
        "Libre Claw workspace initialized.",
        f"- workspace: {result.path}",
        f"- source: {result.source_root}",
    ]
    if result.config_path is not None:
        lines.append(f"- default config updated: {result.config_path}")
    lines.append(f"- created files: {len(result.created_files)}")
    lines.append(f"- copied files: {len(result.copied_files)}")
    lines.append(f"- skipped existing files: {len(result.skipped_files)}")
    return "\n".join(lines)


def _write_template(
    path: Path,
    text: str,
    *,
    overwrite: bool,
    created: list[Path],
    skipped: list[Path],
) -> None:
    if path.exists() and not overwrite:
        skipped.append(path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    created.append(path)


def _copy_markdown_file(
    source: Path,
    target: Path,
    *,
    overwrite: bool,
    copied: list[Path],
    skipped: list[Path],
) -> None:
    if not source.is_file() or source.suffix.lower() != ".md":
        return
    if target.exists() and not overwrite:
        skipped.append(target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    copied.append(target)


def _copy_markdown_tree(
    source: Path,
    target: Path,
    *,
    overwrite: bool,
    copied: list[Path],
    skipped: list[Path],
) -> None:
    if not source.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        return
    for path in sorted(source.rglob("*.md")):
        relative = path.relative_to(source)
        _copy_markdown_file(path, target / relative, overwrite=overwrite, copied=copied, skipped=skipped)
