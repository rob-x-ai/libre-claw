# Copyright 2026 Kroonen AI (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape
from typing import Final

TELEGRAM_HARD_MESSAGE_LIMIT: Final = 4096
TELEGRAM_SAFE_MESSAGE_LIMIT: Final = 3900

_FENCE_RE: Final = re.compile(r"```[^\n]*\n?(.*?)```", re.DOTALL)
_LINK_RE: Final = re.compile(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)")
_INLINE_CODE_RE: Final = re.compile(r"`([^`\n]+)`")
_BOLD_RE: Final = re.compile(r"\*\*([^*\n]+)\*\*")
_ITALIC_RE: Final = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_PROCESS_PREFIXES: Final = (
    "let me ",
    "i'll ",
    "i will ",
    "now let me ",
    "good, ",
    "good —",
    "no prior ",
    "not relevant.",
    "most new stories",
)


@dataclass(frozen=True)
class TelegramFormattedChunk:
    text: str
    parse_mode: str | None = "HTML"


def telegram_message_limit(configured_limit: int) -> int:
    return max(1, min(configured_limit, TELEGRAM_HARD_MESSAGE_LIMIT, TELEGRAM_SAFE_MESSAGE_LIMIT))


def clean_final_answer_for_telegram(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    if not _looks_like_process_narration(cleaned):
        return cleaned

    divider_match = re.search(r"(?m)^\s*-{3,}\s*$", cleaned)
    if divider_match is not None:
        return cleaned[divider_match.end() :].strip()

    for pattern in (
        r"(?im)^#{1,6}\s+\S.*$",
        r"(?im)^\*\*[^*\n]+\*\*\s*$",
        r"(?im)^here (?:are|is)\b.*$",
        r"(?im)^final answer:\s*",
    ):
        match = re.search(pattern, cleaned)
        if match is not None and match.start() > 0:
            return cleaned[match.start() :].strip()

    paragraphs = re.split(r"\n\s*\n", cleaned)
    while paragraphs and _paragraph_is_process_narration(paragraphs[0]):
        paragraphs.pop(0)
    return "\n\n".join(paragraphs).strip() or cleaned


def telegram_html_chunks(text: str, configured_limit: int, *, clean_final: bool = False) -> list[TelegramFormattedChunk]:
    source = clean_final_answer_for_telegram(text) if clean_final else text.strip()
    if not source:
        source = "Done."
    limit = telegram_message_limit(configured_limit)
    chunks: list[TelegramFormattedChunk] = []
    current: list[str] = []
    for block in _markdown_blocks(source):
        candidate_blocks = [*current, block]
        candidate_html = markdown_to_telegram_html("\n\n".join(candidate_blocks))
        if len(candidate_html) <= limit:
            current = candidate_blocks
            continue
        if current:
            chunks.append(TelegramFormattedChunk(markdown_to_telegram_html("\n\n".join(current))))
            current = []
        block_html = markdown_to_telegram_html(block)
        if len(block_html) <= limit:
            current = [block]
            continue
        chunks.extend(TelegramFormattedChunk(markdown_to_telegram_html(part)) for part in _split_oversized_block(block, limit))
    if current:
        chunks.append(TelegramFormattedChunk(markdown_to_telegram_html("\n\n".join(current))))
    return chunks or [TelegramFormattedChunk(markdown_to_telegram_html(source))]


def plain_text_chunks(text: str, configured_limit: int) -> list[str]:
    limit = telegram_message_limit(configured_limit)
    remaining = text or " "
    chunks: list[str] = []
    while len(remaining) > limit:
        chunk = remaining[:limit]
        cut = max(chunk.rfind("\n"), chunk.rfind(" "))
        if cut < max(1, limit // 2):
            split_at = limit
        else:
            split_at = cut + 1
        chunks.append(remaining[:split_at] or remaining[:limit])
        remaining = remaining[split_at:]
    chunks.append(remaining or " ")
    return chunks


def markdown_to_telegram_html(text: str) -> str:
    rendered: list[str] = []
    cursor = 0
    for match in _FENCE_RE.finditer(text):
        if match.start() > cursor:
            rendered.append(_render_text_block(text[cursor : match.start()]))
        rendered.append(f"<pre><code>{escape(match.group(1).strip(), quote=False)}</code></pre>")
        cursor = match.end()
    if cursor < len(text):
        rendered.append(_render_text_block(text[cursor:]))
    return "".join(rendered).strip() or " "


def _render_text_block(text: str) -> str:
    output: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            output.append("")
            continue
        heading = re.match(r"^\s*#{1,6}\s+(.+)$", line)
        if heading is not None:
            output.append(f"<b>{_render_inline(heading.group(1).strip())}</b>")
            continue
        if re.match(r"^\s*-{3,}\s*$", line):
            output.append("----------")
            continue
        bullet = re.match(r"^(\s*(?:[-*]|•)\s+)(.+)$", line)
        if bullet is not None:
            output.append(f"{escape(bullet.group(1), quote=False)}{_render_inline(bullet.group(2))}")
            continue
        numbered = re.match(r"^(\s*\d+\.\s+)(.+)$", line)
        if numbered is not None:
            output.append(f"{escape(numbered.group(1), quote=False)}{_render_inline(numbered.group(2))}")
            continue
        output.append(_render_inline(line))
    return "\n".join(output)


def _render_inline(text: str) -> str:
    replacements: list[str] = []

    def stash(value: str) -> str:
        replacements.append(value)
        return f"@@LC_HTML_{len(replacements) - 1}@@"

    protected = _LINK_RE.sub(
        lambda match: stash(
            f'<a href="{escape(match.group(2), quote=True)}">{escape(match.group(1), quote=False)}</a>'
        ),
        text,
    )
    protected = _INLINE_CODE_RE.sub(
        lambda match: stash(f"<code>{escape(match.group(1), quote=False)}</code>"),
        protected,
    )
    html = escape(protected, quote=False)
    html = _BOLD_RE.sub(r"<b>\1</b>", html)
    html = _ITALIC_RE.sub(r"<i>\1</i>", html)
    for index, replacement in enumerate(replacements):
        html = html.replace(f"@@LC_HTML_{index}@@", replacement)
    return html


def _markdown_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and not line.strip():
            if current:
                blocks.append("\n".join(current).strip("\n"))
                current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current).strip("\n"))
    return blocks or [text]


def _split_oversized_block(block: str, limit: int) -> list[str]:
    pieces = [block]
    changed = True
    while changed:
        changed = False
        next_pieces: list[str] = []
        for piece in pieces:
            if len(markdown_to_telegram_html(piece)) <= limit or len(piece) <= 1:
                next_pieces.append(piece)
                continue
            split_at = _best_split_index(piece)
            next_pieces.append(piece[:split_at].rstrip())
            next_pieces.append(piece[split_at:].lstrip())
            changed = True
        pieces = [piece for piece in next_pieces if piece]
    return pieces


def _best_split_index(text: str) -> int:
    midpoint = max(1, len(text) // 2)
    candidates = [text.rfind("\n", 0, midpoint), text.rfind(" ", 0, midpoint)]
    split_at = max(candidates)
    if split_at < max(1, midpoint // 2):
        split_at = midpoint
    return split_at


def _looks_like_process_narration(text: str) -> bool:
    first = text.lstrip().lower()
    return any(first.startswith(prefix) for prefix in _PROCESS_PREFIXES)


def _paragraph_is_process_narration(text: str) -> bool:
    stripped = text.strip().lower()
    if not stripped:
        return True
    return any(stripped.startswith(prefix) for prefix in _PROCESS_PREFIXES)
