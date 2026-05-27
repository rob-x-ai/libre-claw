# Copyright 2026 Kroonen AI (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from importlib import resources
from pathlib import Path


def packaged_release_text() -> str:
    """Return the packaged release notes shown at TUI startup."""
    try:
        return resources.files("libre_claw").joinpath("RELEASE.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        release_path = Path(__file__).resolve().parents[2] / "RELEASE.md"
        return release_path.read_text(encoding="utf-8")


def latest_release_notes() -> str:
    """Extract the latest version section from the release notes file."""
    text = packaged_release_text()
    lines = text.splitlines()
    start: int | None = None
    end = len(lines)

    for index, line in enumerate(lines):
        if line.startswith("## "):
            start = index
            break

    if start is None:
        return text.strip()

    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break

    return "\n".join(lines[start:end]).strip()
