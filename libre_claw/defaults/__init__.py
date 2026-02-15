"""Default workspace templates for Libre Claw.

Each DEFAULT_* constant holds the content for the corresponding .md template file.
These are loaded by workspace.py during `init()`.
"""

from pathlib import Path

_DEFAULTS_DIR = Path(__file__).parent


def _load(filename: str) -> str:
    """Load a default template file."""
    path = _DEFAULTS_DIR / filename
    if path.exists():
        return path.read_text()
    return f"# {filename.replace('.md', '')}\n\nYour content here.\n"


# Load all default templates as module-level constants.
# workspace.py resolves these via:
#   getattr(defaults, f"DEFAULT_{filename_stem}", None)

DEFAULT_SOUL = _load("SOUL.md")
DEFAULT_USER = _load("USER.md")
DEFAULT_IDENTITY = _load("IDENTITY.md")
DEFAULT_AGENTS = _load("AGENTS.md")
DEFAULT_MEMORY = _load("MEMORY.md")
DEFAULT_HEARTBEAT = _load("HEARTBEAT.md")
DEFAULT_HEARTBEAT_AUDIT = _load("HEARTBEAT-AUDIT.md")
DEFAULT_INFRA = _load("INFRA.md")
DEFAULT_TOOLS = _load("TOOLS.md")
