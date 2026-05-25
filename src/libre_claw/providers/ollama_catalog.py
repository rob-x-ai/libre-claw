# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OllamaModelPreset:
    model: str
    label: str


# Keep this list small and biased toward the current official Ollama Cloud
# library pages. Users can still type any exact name returned by /api/tags.
OLLAMA_MODEL_PRESETS: tuple[OllamaModelPreset, ...] = (
    OllamaModelPreset("kimi-k2.6:cloud", "Kimi K2.6 Cloud"),
    OllamaModelPreset("deepseek-v4-flash:cloud", "DeepSeek V4 Flash Cloud"),
    OllamaModelPreset("deepseek-v4-pro:cloud", "DeepSeek V4 Pro Cloud"),
    OllamaModelPreset("glm-5.1:cloud", "GLM 5.1 Cloud"),
    OllamaModelPreset("minimax-m2.7:cloud", "MiniMax M2.7 Cloud"),
    OllamaModelPreset("qwen3.5:cloud", "Qwen3.5 Cloud"),
    OllamaModelPreset("gemma4:31b-cloud", "Gemma 4 31B Cloud"),
    OllamaModelPreset("nemotron-3-super:cloud", "Nemotron 3 Super Cloud"),
    OllamaModelPreset("gpt-oss:120b", "GPT OSS 120B API"),
    OllamaModelPreset("gpt-oss:20b", "GPT OSS 20B API"),
    OllamaModelPreset("qwen3.6:27b", "Qwen3.6 local daemon"),
    OllamaModelPreset("qwen3:32b", "Qwen3 local daemon"),
)
