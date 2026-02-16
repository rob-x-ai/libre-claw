"""Workspace management for Libre Claw.

Handles loading/writing .md files, heartbeat state, git sync, and workspace initialization.
Supports mode-aware context loading (direct vs heartbeat mode load different files).
"""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import Config, GitConfig


class Workspace:
    """The core workspace manager for Libre Claw.

    Manages workspace directory, loads/saves markdown files,
    handles git sync, and provides workspace initialization.
    """

    # Files loaded in every mode
    CORE_FILES = ["SOUL.md", "USER.md", "IDENTITY.md", "AGENTS.md", "CONVERSATION_SUMMARY.md"]

    # Additional files for direct mode (main session with human)
    DIRECT_FILES = ["MEMORY.md"]

    # Additional files for heartbeat mode
    HEARTBEAT_FILES = ["HEARTBEAT.md"]

    # All possible template files
    ALL_TEMPLATES = [
        "SOUL.md", "USER.md", "IDENTITY.md", "AGENTS.md", "CONVERSATION_SUMMARY.md",
        "MEMORY.md", "HEARTBEAT.md", "HEARTBEAT-AUDIT.md",
        "INFRA.md", "TOOLS.md",
    ]

    def __init__(
        self,
        path: str = "~/.libre-claw/workspace",
        config: Optional[Config] = None,
    ):
        self.path = Path(path).expanduser().resolve()
        self.config = config or Config()
        self.git_config: GitConfig = self.config.git

    @property
    def exists(self) -> bool:
        return self.path.exists() and self.path.is_dir()

    def ensure_exists(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        # Also ensure memory/ subdirectory exists
        (self.path / "memory").mkdir(exist_ok=True)

    def init(self, force: bool = False) -> None:
        """Initialize workspace with default template files."""
        self.ensure_exists()

        from . import defaults

        for filename in self.ALL_TEMPLATES:
            filepath = self.path / filename
            if filepath.exists() and not force:
                continue

            # Resolve attribute name: SOUL.md -> DEFAULT_SOUL, HEARTBEAT-AUDIT.md -> DEFAULT_HEARTBEAT_AUDIT
            attr_name = f"DEFAULT_{filename.replace('-', '_').replace('.md', '').upper()}"
            content = getattr(defaults, attr_name, None)
            if content is None:
                content = f"# {filename.replace('.md', '')}\n\nYour content here.\n"

            filepath.write_text(content)

        # Create memory directory
        (self.path / "memory").mkdir(exist_ok=True)

        # Initialize git if enabled
        if self.git_config.enabled:
            self._init_git()

        # Create default config.yaml if it doesn't exist
        config_path = self.path / "config.yaml"
        if not config_path.exists():
            self.config.save(config_path)

    def _init_git(self) -> None:
        """Initialize git repository."""
        if (self.path / ".git").exists():
            return
        try:
            subprocess.run(["git", "init"], cwd=self.path, capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to initialize git: {e}")

    def read(self, filename: str) -> Optional[str]:
        """Read a file from the workspace."""
        filepath = self.path / filename
        if not filepath.exists():
            return None
        try:
            return filepath.read_text()
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            return None

    def write(self, filename: str, content: str) -> None:
        """Write content to a file in the workspace."""
        filepath = self.path / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        try:
            filepath.write_text(content)
        except Exception as e:
            print(f"Error writing {filename}: {e}")

    def append(self, filename: str, content: str) -> None:
        """Append content to a file."""
        filepath = self.path / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        existing = ""
        if filepath.exists():
            existing = filepath.read_text()
        if existing and not existing.endswith("\n"):
            existing += "\n"
        filepath.write_text(existing + content)

    def list_files(self, pattern: str = "*.md") -> List[Path]:
        """List files matching a glob pattern."""
        if not self.exists:
            return []
        return sorted(self.path.glob(pattern))

    def get_context(self, mode: str = "direct") -> Dict[str, str]:
        """Get workspace context files based on mode.

        Args:
            mode: "direct" for main session, "heartbeat" for autonomous mode

        Returns:
            Dictionary mapping filenames to their contents
        """
        context = {}

        # Always load core files
        for filename in self.CORE_FILES:
            content = self.read(filename)
            if content:
                context[filename] = content

        # Load mode-specific files
        if mode == "direct":
            for filename in self.DIRECT_FILES:
                content = self.read(filename)
                if content:
                    context[filename] = content
        elif mode == "heartbeat":
            for filename in self.HEARTBEAT_FILES:
                content = self.read(filename)
                if content:
                    context[filename] = content

        # Load today's daily note if it exists
        today = datetime.now().strftime("%Y-%m-%d")
        daily_note = self.read(f"memory/{today}.md")
        if daily_note:
            context[f"memory/{today}.md"] = daily_note

        return context

    def write_daily_note(self, content: str) -> None:
        """Append to today's daily note."""
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"memory/{today}.md"
        filepath = self.path / filename
        if not filepath.exists():
            self.write(filename, f"# {today}\n\n")
        self.append(filename, content + "\n")

    def get_heartbeat_state(self) -> Dict[str, Any]:
        """Get heartbeat state from heartbeat-state.json."""
        content = self.read("heartbeat-state.json")
        if not content:
            return {}
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}

    def save_heartbeat_state(self, state: Dict[str, Any]) -> None:
        """Save heartbeat state to heartbeat-state.json."""
        self.write("heartbeat-state.json", json.dumps(state, indent=2))

    def update_heartbeat_audit(self, status: str, details: str = "") -> None:
        """Append to heartbeat audit log."""
        timestamp = datetime.now().isoformat()
        details_text = (details or "").strip()
        entry = f"\n## {timestamp}\n\n- Status: {status}\n"
        if details_text:
            entry += f"- Details: {details_text[:2400]}\n"
        self.append("HEARTBEAT-AUDIT.md", entry)

        action_id = ""
        result = ""
        if details_text:
            action_match = re.search(r"action:([A-Za-z0-9._-]+)", details_text)
            if action_match:
                action_id = action_match.group(1)
            result_match = re.search(r"result:([^\n]+)", details_text)
            if result_match:
                result = result_match.group(1).strip()

        event = {
            "ts": timestamp,
            "status": status,
            "action_id": action_id,
            "result": result,
            "details": details_text[:4000],
        }
        self.append("HEARTBEAT-AUDIT.jsonl", json.dumps(event, ensure_ascii=True) + "\n")
        self._compact_heartbeat_audit_files()

    def _compact_heartbeat_audit_files(self) -> None:
        self._compact_lines("HEARTBEAT-AUDIT.md", max_lines=500, keep_lines=300)
        self._compact_lines("HEARTBEAT-AUDIT.jsonl", max_lines=2000, keep_lines=1000)

    def _compact_lines(self, filename: str, max_lines: int, keep_lines: int) -> None:
        path = self.path / filename
        if not path.exists():
            return
        try:
            lines = path.read_text().splitlines()
        except Exception:
            return

        if len(lines) <= max_lines:
            return

        trimmed = lines[-keep_lines:]
        content = "\n".join(trimmed).strip("\n")
        if content:
            content += "\n"
        try:
            path.write_text(content)
        except Exception:
            return

    def git_sync(self, message: Optional[str] = None) -> bool:
        """Commit and push workspace changes."""
        if not self.git_config.enabled:
            return False
        try:
            if not (self.path / ".git").exists():
                return False

            subprocess.run(["git", "add", "-A"], cwd=self.path, capture_output=True, check=True)

            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.path, capture_output=True, text=True,
            )
            if not result.stdout.strip():
                return True  # Nothing to commit

            commit_msg = message or self.git_config.commit_message
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=self.path, capture_output=True, check=True,
            )

            if self.git_config.remote:
                subprocess.run(
                    ["git", "push", self.git_config.remote],
                    cwd=self.path, capture_output=True, check=True,
                )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Git sync failed: {e}")
            return False
