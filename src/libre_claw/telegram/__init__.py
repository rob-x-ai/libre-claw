# Copyright 2026 Kroonen AI (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

__all__ = ["TelegramAuth", "TelegramBridge", "TelegramBot"]

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from libre_claw.telegram.auth import TelegramAuth
    from libre_claw.telegram.bot import TelegramBot
    from libre_claw.telegram.bridge import TelegramBridge


def __getattr__(name: str) -> Any:
    if name == "TelegramAuth":
        from libre_claw.telegram.auth import TelegramAuth

        return TelegramAuth
    if name == "TelegramBridge":
        from libre_claw.telegram.bridge import TelegramBridge

        return TelegramBridge
    if name == "TelegramBot":
        from libre_claw.telegram.bot import TelegramBot

        return TelegramBot
    raise AttributeError(name)
