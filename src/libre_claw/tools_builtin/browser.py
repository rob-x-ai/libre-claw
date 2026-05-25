# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from libre_claw.core.sandbox import SandboxViolation
from libre_claw.core.tools import BaseTool, ToolResult, register_tool


MAX_BROWSER_TEXT_CHARS = 30000
DEFAULT_SCREENSHOT_PATH = ".libre-claw/browser-screenshot.png"


class BrowserState:
    def __init__(self) -> None:
        self.playwright: Any | None = None
        self.browser: Any | None = None
        self.page: Any | None = None
        self.current_url = ""

    async def ensure_page(self) -> tuple[Any | None, str | None]:
        try:
            async_api = importlib.import_module("playwright.async_api")
        except ModuleNotFoundError:
            return None, "Playwright is not installed. Install the browser extra before using browser tools."

        if self.playwright is None:
            self.playwright = await async_api.async_playwright().start()
        if self.browser is None:
            self.browser = await self.playwright.chromium.launch(headless=True)
        if self.page is None:
            self.page = await self.browser.new_page()
        return self.page, None


_BROWSER_STATE = BrowserState()


@register_tool
class BrowserNavigateTool(BaseTool):
    name = "browser_navigate"
    description = "Open a URL in a headless browser session. Requires Playwright to be installed."
    parameters = {
        "url": {"type": "string", "description": "HTTP or HTTPS URL to open"},
        "timeout_ms": {"type": "integer", "description": "Navigation timeout in milliseconds", "default": 30000},
    }
    required = ("url",)
    permission_level = "ask"

    async def execute(self, url: str, timeout_ms: int = 30000) -> ToolResult:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ToolResult(error="url must be an absolute http(s) URL")
        if timeout_ms < 1000:
            return ToolResult(error="timeout_ms must be >= 1000")

        try:
            page, error = await _BROWSER_STATE.ensure_page()
        except Exception as exc:
            return ToolResult(error=str(exc))
        if error is not None:
            return ToolResult(error=error)
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            title = await page.title()
        except Exception as exc:
            return ToolResult(error=str(exc))

        _BROWSER_STATE.current_url = page.url
        status = getattr(response, "status", None)
        return ToolResult(
            content=f"Opened {page.url}\ntitle: {title}\nstatus: {status if status is not None else 'unknown'}",
            metadata={
                "url": page.url,
                "title": title,
                "status": status,
            },
        )


@register_tool
class BrowserReadTool(BaseTool):
    name = "browser_read"
    description = "Extract visible text from the current headless browser page."
    parameters = {
        "max_chars": {
            "type": "integer",
            "description": f"Maximum page text characters to return, capped at {MAX_BROWSER_TEXT_CHARS}",
            "default": 12000,
        }
    }
    permission_level = "allow"

    async def execute(self, max_chars: int = 12000) -> ToolResult:
        if max_chars < 1:
            return ToolResult(error="max_chars must be >= 1")
        if max_chars > MAX_BROWSER_TEXT_CHARS:
            return ToolResult(error=f"max_chars must be <= {MAX_BROWSER_TEXT_CHARS}")

        page = _BROWSER_STATE.page
        if page is None:
            return ToolResult(error="No browser page is open. Use browser_navigate first.")
        try:
            title = await page.title()
            text = await page.locator("body").inner_text(timeout=5000)
        except Exception as exc:
            return ToolResult(error=str(exc))

        content, truncated = _cap_text(text, max_chars)
        return ToolResult(
            content=f"title: {title}\nurl: {page.url}\n\n{content}",
            metadata={
                "url": page.url,
                "title": title,
                "characters": len(text),
                "truncated": truncated,
            },
        )


@register_tool
class BrowserScreenshotTool(BaseTool):
    name = "browser_screenshot"
    description = "Save a screenshot of the current headless browser page inside the working directory."
    parameters = {
        "path": {"type": "string", "description": "Screenshot output path", "default": DEFAULT_SCREENSHOT_PATH},
        "full_page": {"type": "boolean", "description": "Capture the full page instead of viewport", "default": True},
    }
    permission_level = "allow"

    async def execute(self, path: str = DEFAULT_SCREENSHOT_PATH, full_page: bool = True) -> ToolResult:
        page = _BROWSER_STATE.page
        if page is None:
            return ToolResult(error="No browser page is open. Use browser_navigate first.")
        try:
            resolved = self.resolve_path(path)
        except SandboxViolation as exc:
            return ToolResult(error=str(exc))

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(resolved), full_page=full_page)
        except Exception as exc:
            return ToolResult(error=str(exc))

        size_bytes = Path(resolved).stat().st_size
        return ToolResult(
            content=f"Saved screenshot to {resolved} ({size_bytes} bytes)",
            metadata={
                "path": str(resolved),
                "url": page.url,
                "full_page": full_page,
                "size_bytes": size_bytes,
            },
        )


def _cap_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + f"\n... truncated {len(text) - max_chars} characters ...", True
