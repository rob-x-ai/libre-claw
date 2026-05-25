# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re

from libre_claw.config import LibreClawConfig


class HeartbeatError(RuntimeError):
    """Raised when a heartbeat command cannot be parsed."""


def heartbeat_prompt(config: LibreClawConfig, *, surface: str = "tui") -> str:
    custom_prompt = config.heartbeat.prompt.strip()
    if custom_prompt:
        return custom_prompt
    checklist = "\n".join(f"- {item}" for item in config.heartbeat.checklist)
    return (
        "Run a Libre Claw heartbeat check.\n"
        f"Surface: {surface}.\n"
        "Go through this checklist, use safe read-only tools when useful, and send a concise report:\n"
        f"{checklist}\n\n"
        "Keep the report short. Include only actionable risks, blocked work, and recommended next steps."
    )


def parse_heartbeat_interval(argument: str, default_minutes: int) -> int:
    text = " ".join(argument.strip().lower().split())
    if not text:
        return max(1, default_minutes)
    if text.startswith("every "):
        text = text.removeprefix("every ").strip()
    if text == "hourly":
        return 60

    compact = re.fullmatch(r"([1-9]\d*)\s*([mh])", text)
    if compact:
        amount = int(compact.group(1))
        return amount * 60 if compact.group(2) == "h" else amount

    words = re.fullmatch(r"([1-9]\d*)\s+(minutes?|mins?|m|hours?|hrs?|h)", text)
    if words:
        amount = int(words.group(1))
        unit = words.group(2)
        return amount * 60 if unit.startswith("h") else amount

    raise HeartbeatError("Usage: /heartbeat status|once|start [every 30 minutes|1h]|stop")
