# Copyright 2026 Kroonen AI (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlparse

import httpx

from libre_claw.core.tools import BaseTool, ToolResult, register_tool


MAX_WEB_SEARCH_RESULTS = 50
MAX_WEB_SEARCH_SNIPPET_CHARS = 500
MAX_WEB_SEARCH_ERROR_CHARS = 1200


@register_tool
class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web through the configured SearXNG instance and return compact normalized results."
    parameters = {
        "query": {"type": "string", "description": "Search query."},
        "max_results": {
            "type": "integer",
            "description": f"Maximum results to return, capped at {MAX_WEB_SEARCH_RESULTS}.",
            "default": 10,
        },
        "categories": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional SearXNG categories, for example ['general', 'news', 'it'].",
            "default": [],
        },
        "engines": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional SearXNG engine names.",
            "default": [],
        },
        "language": {"type": "string", "description": "SearXNG language code. Empty uses config default.", "default": ""},
        "safesearch": {
            "type": "integer",
            "description": "SearXNG safesearch level. Use -1 for config default.",
            "default": -1,
        },
        "time_range": {
            "type": "string",
            "description": "Optional SearXNG time range such as day, week, month, or year.",
            "default": "",
        },
        "page": {"type": "integer", "description": "SearXNG result page number.", "default": 1},
    }
    required = ("query",)
    permission_level = "allow"

    async def execute(
        self,
        query: str,
        max_results: int | None = None,
        categories: Sequence[str] | None = None,
        engines: Sequence[str] | None = None,
        language: str = "",
        safesearch: int = -1,
        time_range: str = "",
        page: int = 1,
    ) -> ToolResult:
        if not self.context.web_search_enabled:
            return ToolResult(error="web_search is disabled by [web_search].enabled")
        if self.context.web_search_provider.lower() != "searxng":
            return ToolResult(error=f"Unsupported web search provider: {self.context.web_search_provider}")

        query = query.strip()
        if not query:
            return ToolResult(error="query must not be empty")
        result_limit = self.context.web_search_max_results if max_results is None else max_results
        if result_limit < 1:
            return ToolResult(error="max_results must be >= 1")
        if result_limit > MAX_WEB_SEARCH_RESULTS:
            return ToolResult(error=f"max_results must be <= {MAX_WEB_SEARCH_RESULTS}")
        if page < 1:
            return ToolResult(error="page must be >= 1")
        if page > 20:
            return ToolResult(error="page must be <= 20")

        base_url = self.context.web_search_base_url.rstrip("/")
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ToolResult(error="[web_search].base_url must be an absolute http(s) URL")

        selected_categories = _clean_list(categories) or list(self.context.web_search_default_categories)
        selected_engines = _clean_list(engines) or list(self.context.web_search_default_engines)
        selected_language = (language or self.context.web_search_default_language).strip()
        selected_safesearch = safesearch if safesearch >= 0 else self.context.web_search_default_safesearch

        params: dict[str, str | int] = {
            "q": query,
            "format": "json",
            "pageno": page,
        }
        if selected_categories:
            params["categories"] = ",".join(selected_categories)
        if selected_engines:
            params["engines"] = ",".join(selected_engines)
        if selected_language and selected_language.lower() != "auto":
            params["language"] = selected_language
        if selected_safesearch >= 0:
            params["safesearch"] = selected_safesearch
        if time_range.strip():
            params["time_range"] = time_range.strip()

        try:
            async with httpx.AsyncClient(timeout=self.context.web_search_timeout, follow_redirects=True) as client:
                response = await client.get(f"{base_url}/search", params=params, headers={"accept": "application/json"})
        except Exception as exc:
            return ToolResult(error=f"SearXNG request failed: {exc}")

        if response.status_code == 403:
            return ToolResult(
                error=(
                    "SearXNG returned 403. Enable JSON search output in settings.yml by adding "
                    "`json` to `search.formats`, then restart SearXNG."
                )
            )
        if response.status_code < 200 or response.status_code >= 300:
            return ToolResult(error=f"SearXNG returned HTTP {response.status_code}: {_compact_text(response.text)}")

        try:
            payload = response.json()
        except ValueError as exc:
            return ToolResult(error=f"SearXNG did not return JSON: {exc}")
        if not isinstance(payload, Mapping):
            return ToolResult(error="SearXNG returned an unexpected JSON payload")

        raw_results = payload.get("results", [])
        if not isinstance(raw_results, list):
            raw_results = []
        normalized = [_normalize_result(result) for result in raw_results if isinstance(result, Mapping)]
        normalized = [result for result in normalized if result["url"]]
        returned = normalized[:result_limit]

        content = _format_results(query=query, base_url=base_url, results=returned)
        metadata = {
            "artifact_type": "web_search",
            "provider": "searxng",
            "base_url": base_url,
            "query": query,
            "result_count": len(normalized),
            "returned_results": len(returned),
            "page": page,
            "categories": selected_categories,
            "engines": selected_engines,
            "language": selected_language,
            "safesearch": selected_safesearch,
            "time_range": time_range.strip(),
            "results": returned,
        }
        return ToolResult(content=content, metadata=metadata)


def _clean_list(values: Sequence[str] | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return [values.strip()] if values.strip() else []
    return [str(value).strip() for value in values if str(value).strip()]


def _normalize_result(result: Mapping[str, Any]) -> dict[str, Any]:
    title = str(result.get("title") or "Untitled").strip()
    url = str(result.get("url") or "").strip()
    snippet = str(result.get("content") or result.get("snippet") or "").strip()
    published = str(result.get("publishedDate") or result.get("published_date") or "").strip()
    engine = str(result.get("engine") or result.get("engines") or "").strip()
    category = str(result.get("category") or "").strip()
    score = result.get("score")
    return {
        "title": _one_line(title),
        "url": url,
        "snippet": _compact_snippet(snippet),
        "engine": _one_line(engine),
        "category": _one_line(category),
        "published": _one_line(published),
        "score": score if isinstance(score, int | float | str) else None,
    }


def _format_results(*, query: str, base_url: str, results: list[dict[str, Any]]) -> str:
    lines = [
        f"web_search: {query}",
        f"source: {base_url}",
        f"results: {len(results)}",
    ]
    if not results:
        lines.append("")
        lines.append("No results.")
        return "\n".join(lines)

    for index, result in enumerate(results, start=1):
        lines.extend(["", f"{index}. {result['title']}", f"   url: {result['url']}"])
        if result["snippet"]:
            lines.append(f"   snippet: {result['snippet']}")
        details = []
        if result["engine"]:
            details.append(f"engine: {result['engine']}")
        if result["category"]:
            details.append(f"category: {result['category']}")
        if result["published"]:
            details.append(f"published: {result['published']}")
        if result["score"] is not None:
            details.append(f"score: {result['score']}")
        if details:
            lines.append("   " + " | ".join(details))
    return "\n".join(lines)


def _compact_snippet(value: str) -> str:
    return _compact_text(_one_line(value), limit=MAX_WEB_SEARCH_SNIPPET_CHARS)


def _compact_text(value: str, limit: int = MAX_WEB_SEARCH_ERROR_CHARS) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + f"... truncated {len(text) - limit} characters ..."


def _one_line(value: str) -> str:
    return " ".join(value.split())
