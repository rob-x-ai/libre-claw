# Copyright 2026 Kroonen AI (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from libre_claw.config import load_config, user_config_path
from libre_claw.core.soul import SOUL_FILENAME
from libre_claw.core.workspace import (
    default_claw_workspace_path,
    initialize_claw_workspace,
    workspace_result_text,
    workspace_status_text,
)


def test_default_workspace_path_uses_documents_workspace(tmp_path: Path) -> None:
    assert default_claw_workspace_path(tmp_path) == tmp_path / "Documents" / ".workspace" / "libre-claw"


def test_initialize_workspace_copies_markdown_and_updates_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "SOUL.md").write_text("# Source Soul\n\nBe Libre Claw.", encoding="utf-8")
    skill = source / ".libre-claw" / "skills" / "release-flow.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# Release Flow\n\nRun tests before release.", encoding="utf-8")
    target = tmp_path / "Documents" / ".workspace" / "libre-claw"

    result = initialize_claw_workspace(source_root=source, target=target)

    assert result.path == target
    assert result.config_path == user_config_path()
    assert (target / "README.md").exists()
    assert (target / "goals.md").exists()
    assert (target / "memory.md").exists()
    assert (target / "SOUL.md").read_text(encoding="utf-8") == "# Source Soul\n\nBe Libre Claw."
    assert (target / ".libre-claw" / "skills" / "release-flow.md").exists()
    assert load_config().general.working_directory == target
    assert "copied files: 2" in workspace_result_text(result)


def test_initialize_workspace_preserves_existing_files_without_overwrite(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "source"
    target = tmp_path / "workspace"
    source.mkdir()
    target.mkdir()
    (source / "SOUL.md").write_text("# New Soul", encoding="utf-8")
    (target / "SOUL.md").write_text("# Existing Soul", encoding="utf-8")

    result = initialize_claw_workspace(source_root=source, target=target, set_default=False)

    assert (target / "SOUL.md").read_text(encoding="utf-8") == "# Existing Soul"
    assert target / "SOUL.md" in result.skipped_files
    assert result.config_path is None


def test_initialize_workspace_upgrades_legacy_lowercase_soul(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "source"
    target = tmp_path / "workspace"
    source.mkdir()
    target.mkdir()
    legacy_path = target / SOUL_FILENAME.lower()
    legacy_path.write_text("# Existing Legacy Soul", encoding="utf-8")

    result = initialize_claw_workspace(source_root=source, target=target, set_default=False)

    assert (target / SOUL_FILENAME).read_text(encoding="utf-8") == "# Existing Legacy Soul"
    assert SOUL_FILENAME.lower() not in {path.name for path in target.iterdir()}
    assert target / SOUL_FILENAME not in result.created_files


def test_workspace_status_text_reports_paths(tmp_path: Path) -> None:
    text = workspace_status_text(tmp_path)

    assert "Libre Claw workspace:" in text
    assert str(tmp_path.resolve()) in text
