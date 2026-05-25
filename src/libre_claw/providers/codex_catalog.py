# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CodexModelPreset:
    model: str
    label: str
    description: str


# Mirrors the listed models exposed by Codex CLI 0.133.0 / its model catalog.
# Keep hidden internal helpers such as codex-auto-review out of the picker.
CODEX_MODEL_PRESETS: tuple[CodexModelPreset, ...] = (
    CodexModelPreset(
        "gpt-5.5",
        "GPT-5.5",
        "Frontier Codex model for complex coding, research, and real-world work.",
    ),
    CodexModelPreset(
        "gpt-5.4",
        "GPT-5.4",
        "Strong model for everyday coding and professional work.",
    ),
    CodexModelPreset(
        "gpt-5.4-mini",
        "GPT-5.4 Mini",
        "Small, fast model for simpler coding tasks and cheaper throughput.",
    ),
    CodexModelPreset(
        "gpt-5.3-codex",
        "GPT-5.3 Codex",
        "Coding-optimized Codex model.",
    ),
    CodexModelPreset(
        "gpt-5.3-codex-spark",
        "GPT-5.3 Codex Spark",
        "Ultra-fast Codex research preview.",
    ),
    CodexModelPreset(
        "gpt-5.2",
        "GPT-5.2",
        "Legacy professional-work model for long-running agents.",
    ),
)
