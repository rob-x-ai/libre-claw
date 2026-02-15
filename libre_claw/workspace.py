"""Workspace management for Libre Claw.

Handles loading/writing .md files, heartbeat state, git sync, and workspace initialization.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import Config, GitConfig, WorkspaceConfig


class Workspace:
    """The core workspace manager for Libre Claw.

    Manages workspace directory, loads/saves markdown files,
    handles git sync, and provides workspace initialization.
    """

    DEFAULT_FILES = [
        "SOUL.md",
        "USER.md",
        "IDENTITY.md",
        "AGENTS.md",
        "MEMORY.md",
        "HEARTBEAT.md",
        "HEARTBEAT-AUDIT.md",
        "INFRA.md",
        "TOOLS.md",
    ]

    def __init__(
        self,
        path: str = "~/.openclaw/workspace",
        config: Optional[Config] = None,
    ):
        """Initialize workspace.

        Args:
            path: Path to workspace directory
            config: Optional configuration object
        """
        self.path = Path(path).expanduser().resolve()
        self.config = config or Config()
        self.git_config: GitConfig = self.config.git

    @property
    def exists(self) -> bool:
        """Check if workspace directory exists."""
        return self.path.exists() and self.path.is_dir()

    def ensure_exists(self) -> None:
        """Ensure workspace directory exists."""
        self.path.mkdir(parents=True, exist_ok=True)

    def init(self, force: bool = False) -> None:
        """Initialize workspace with default template files.

        Args:
            force: Overwrite existing files
        """
        self.ensure_exists()

        # Import defaults module to get template content
        from . import defaults

        for filename in self.DEFAULT_FILES:
            filepath = self.path / filename
            if filepath.exists() and not force:
                continue

            # Get default content from defaults module
            content = getattr(defaults, f"DEFAULT_{filename.replace('-', '_').replace('.md', '').upper()}", None)
            if content is None:
                content = f"# {filename.replace('.md', '')}\n\n" + "Your content here.\n"

            with open(filepath, "w") as f:
                f.write(content)

        # Initialize git repo if requested
        if self.git_config.enabled:
            self._init_git()

    def _init_git(self) -> None:
        """Initialize git repository if not already initialized."""
        git_dir = self.path / ".git"
        if git_dir.exists():
            return

        try:
            subprocess.run(
                ["git", "init"],
                cwd=self.path,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to initialize git: {e}")

    def read(self, filename: str) -> Optional[str]:
        """Read a file from the workspace.

        Args:
            filename: Name of file to read (e.g., 'SOUL.md')

        Returns:
            File contents or None if file doesn't exist
        """
        filepath = self.path / filename
        if not filepath.exists():
            return None

        try:
            return filepath.read_text()
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            return None

    def write(self, filename: str, content: str) -> None:
        """Write content to a file in the workspace.

        Args:
            filename: Name of file to write
            content: Content to write
        """
        filepath = self.path / filename
        self.ensure_exists()

        try:
            filepath.write_text(content)
        except Exception as e:
            print(f"Error writing {filename}: {e}")

    def list_files(self, pattern: str = "*.md") -> List[Path]:
        """List markdown files in workspace.

        Args:
            pattern: Glob pattern for files

        Returns:
            List of matching file paths
        """
        if not self.exists:
            return []
        return list(self.path.glob(pattern))

    def get_context(self) -> Dict[str, str]:
        """Get workspace context files as a dictionary.

        Loads SOUL.md, USER.md, IDENTITY.md, AGENTS.md, and MEMORY.md.

        Returns:
            Dictionary mapping filenames to their contents
        """
        context = {}
        for filename in ["SOUL.md", "USER.md", "IDENTITY.md", "AGENTS.md", "MEMORY.md"]:
            content = self.read(filename)
            if content:
                context[filename] = content
        return context

    def append_to_file(self, filename: str, content: str) -> None:
        """Append content to a file in the workspace.

        Args:
            filename: Name of file to append to
            content: Content to append
        """
        filepath = self.path / filename
        self.ensure_exists()

        existing = ""
        if filepath.exists():
            existing = filepath.read_text()

        # Add double newline if existing content doesn't end with one
        if existing and not existing.endswith("\n\n"):
            existing += "\n"

        filepath.write_text(existing + content)

    def git_sync(self, message: Optional[str] = None) -> bool:
        """Sync workspace with git remote.

        Args:
            message: Commit message (uses default if not provided)

        Returns:
            True if sync was successful
        """
        if not self.git_config.enabled:
            return False

        try:
            # Check if we're in a git repo
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.path,
                capture_output=True,
            )
            if result.returncode != 0:
                return False

            # Add all changes
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.path,
                capture_output=True,
                check=True,
            )

            # Check if there are changes
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.path,
                capture_output=True,
                text=True,
            )
            if not result.stdout.strip():
                return True  # Nothing to commit

            # Commit
            commit_msg = message or self.git_config.commit_message
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=self.path,
                capture_output=True,
                check=True,
            )

            # Push if remote is configured
            if self.git_config.remote:
                subprocess.run(
                    ["git", "push", self.git_config.remote],
                    cwd=self.path,
                    capture_output=True,
                    check=True,
                )

            return True

        except subprocess.CalledProcessError as e:
            print(f"Git sync failed: {e}")
            return False

    def get_heartbeat_state(self) -> Dict[str, Any]:
        """Get current heartbeat state from HEARTBEAT-AUDIT.md.

        Returns:
            Dictionary with last run time, consecutive failures, etc.
        """
        content = self.read("HEARTBEAT-AUDIT.md")
        if not content:
            return {
                "last_run": None,
                "consecutive_failures": 0,
                "total_runs": 0,
            }

        # Simple parsing - get last line with timestamp
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        last_run = None
        consecutive_failures = 0

        for line in reversed(lines):
            if line.startswith("## "):
                # Extract timestamp from header
                ts_str = line[3:].strip()
                try:
                    last_run = datetime.fromisoformat(ts_str)
                except ValueError:
                    pass
                break

        # Count consecutive failures
        for line in reversed(lines):
            if "FAILED" in line.upper():
                consecutive_failures += 1
            elif "SUCCESS" in line.upper():
                break

        return {
            "last_run": last_run,
            "consecutive_failures": consecutive_failures,
            "total_runs": len([l for l in lines if l.startswith("## ")]),
        }

    def update_heartbeat_audit(self, status: str, details: str = "") -> None:
        """Update heartbeat audit log.

        Args:
            status: Status message (SUCCESS, FAILED, etc.)
            details: Optional details about the run
        """
        timestamp = datetime.now().isoformat()
        content = f"\n## {timestamp}\n\n- Status: {status}\n"
        if details:
            content += f"- Details: {details}\n"

        self.append_to_file("HEARTBEAT-AUDIT.md", content)

    def get_infra_config(self) -> Dict[str, Any]:
        """Parse INFRA.md for infrastructure configuration.

        Returns:
            Dictionary with parsed infrastructure details
        """
        content = self.read("INFRA.md")
        if not content:
            return {}

        # Simple key-value parsing from markdown
        infra = {}
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("- ") and ":" in line:
                key, _, value = line[2:].partition(":")
                infra[key.strip()] = value.strip()

        return infra

    def get_tools_config(self) -> Dict[str, Any]:
        """Parse TOOLS.md for tool configurations.

        Returns:
            Dictionary with parsed tool configurations
        """
        content = self.read("TOOLS.md")
        if not content:
            return {}

        # Simple key-value parsing
        tools = {}
        current_section = None
        current_data = {}

        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("## "):
                if current_section:
                    tools[current_section] = current_data
                current_section = line[3:].strip()
                current_data = {}
            elif line.startswith("- ") and ":" in line:
                key, _, value = line[2:].partition(":")
                current_data[key.strip()] = value.strip()

        if current_section:
            tools[current_section] = current_data

        return tools
