"""Tests for workspace module."""

from pathlib import Path

import pytest

from libre_claw.config import Config
from libre_claw.workspace import Workspace


class TestWorkspace:
    """Test workspace management."""

    def test_init_creates_directory(self, tmp_path):
        """Test workspace initialization creates the directory."""
        ws_path = tmp_path / "test_workspace"
        config = Config()
        config.git.enabled = False

        ws = Workspace(str(ws_path), config)
        ws.init()

        assert ws_path.exists()
        assert ws_path.is_dir()

    def test_init_creates_default_files(self, tmp_path):
        """Test workspace init creates all default template files."""
        ws_path = tmp_path / "test_workspace"
        config = Config()
        config.git.enabled = False

        ws = Workspace(str(ws_path), config)
        ws.init()

        for filename in Workspace.DEFAULT_FILES:
            filepath = ws_path / filename
            assert filepath.exists(), f"Missing default file: {filename}"
            content = filepath.read_text()
            assert len(content) > 0, f"Empty default file: {filename}"

    def test_init_does_not_overwrite(self, tmp_path):
        """Test workspace init does not overwrite existing files."""
        ws_path = tmp_path / "test_workspace"
        ws_path.mkdir()
        (ws_path / "SOUL.md").write_text("My custom soul")

        config = Config()
        config.git.enabled = False
        ws = Workspace(str(ws_path), config)
        ws.init()

        assert (ws_path / "SOUL.md").read_text() == "My custom soul"

    def test_init_force_overwrites(self, tmp_path):
        """Test workspace init with force overwrites existing files."""
        ws_path = tmp_path / "test_workspace"
        ws_path.mkdir()
        (ws_path / "SOUL.md").write_text("My custom soul")

        config = Config()
        config.git.enabled = False
        ws = Workspace(str(ws_path), config)
        ws.init(force=True)

        content = (ws_path / "SOUL.md").read_text()
        assert content != "My custom soul"

    def test_read_write(self, tmp_path):
        """Test reading and writing files."""
        ws = Workspace(str(tmp_path))
        ws.ensure_exists()

        ws.write("test.md", "Hello, world!")
        content = ws.read("test.md")
        assert content == "Hello, world!"

    def test_read_nonexistent(self, tmp_path):
        """Test reading a non-existent file returns None."""
        ws = Workspace(str(tmp_path))
        assert ws.read("nonexistent.md") is None

    def test_append_to_file(self, tmp_path):
        """Test appending to a file."""
        ws = Workspace(str(tmp_path))
        ws.ensure_exists()

        ws.write("log.md", "Line 1\n")
        ws.append_to_file("log.md", "Line 2\n")

        content = ws.read("log.md")
        assert "Line 1" in content
        assert "Line 2" in content

    def test_list_files(self, tmp_path):
        """Test listing workspace files."""
        ws = Workspace(str(tmp_path))
        ws.ensure_exists()

        ws.write("one.md", "one")
        ws.write("two.md", "two")
        ws.write("three.txt", "three")

        md_files = ws.list_files("*.md")
        assert len(md_files) == 2

        all_files = ws.list_files("*")
        assert len(all_files) == 3

    def test_get_context(self, tmp_path):
        """Test getting workspace context."""
        config = Config()
        config.git.enabled = False
        ws = Workspace(str(tmp_path), config)
        ws.init()

        context = ws.get_context()
        assert "SOUL.md" in context
        assert "USER.md" in context
        assert "AGENTS.md" in context

    def test_heartbeat_state_empty(self, tmp_path):
        """Test heartbeat state when no audit file exists."""
        ws = Workspace(str(tmp_path))
        state = ws.get_heartbeat_state()

        assert state["last_run"] is None
        assert state["consecutive_failures"] == 0
        assert state["total_runs"] == 0

    def test_update_heartbeat_audit(self, tmp_path):
        """Test updating heartbeat audit log."""
        ws = Workspace(str(tmp_path))
        ws.ensure_exists()

        ws.write("HEARTBEAT-AUDIT.md", "# Heartbeat Audit\n")
        ws.update_heartbeat_audit("SUCCESS", "Test run")

        content = ws.read("HEARTBEAT-AUDIT.md")
        assert "SUCCESS" in content
        assert "Test run" in content

    def test_exists_property(self, tmp_path):
        """Test the exists property."""
        ws = Workspace(str(tmp_path / "nonexistent"))
        assert not ws.exists

        ws = Workspace(str(tmp_path))
        assert ws.exists
