# Copyright 2026 Kroonen AI (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from libre_claw.providers.local import LocalProvider


class OllamaProvider(LocalProvider):
    """Ollama provider name for local daemon and Ollama Cloud endpoints."""
