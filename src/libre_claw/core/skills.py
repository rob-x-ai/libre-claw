# Copyright 2026 Kroonen AI (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, ParamSpec, TypeVar
from uuid import uuid4


SkillScope = Literal["bundled", "user", "project"]
MAX_SKILL_CHARS = 6000
SCOPE_ORDER: dict[SkillScope, int] = {"bundled": 0, "user": 1, "project": 2}
MUTABLE_SCOPES: set[SkillScope] = {"user", "project"}
SKILL_AUTHORING_GUIDANCE = (
    "Skill authoring guidance: when asked to create or improve a skill, use an "
    "AgentSkills-compatible SKILL.md structure with YAML frontmatter (`name`, "
    "`description`) and concise sections: When to Use, Prerequisites, Procedure, "
    "Pitfalls, Verification. Keep secrets out, keep descriptions short, reference "
    "Libre Claw tool names, and prefer deterministic scripts for fragile repeated work."
)
P = ParamSpec("P")
T = TypeVar("T")


class SkillError(RuntimeError):
    """Raised when a skill cannot be loaded or changed."""


@dataclass(frozen=True)
class Skill:
    name: str
    scope: SkillScope
    path: Path
    title: str
    description: str
    content: str

    @property
    def prompt_text(self) -> str:
        body = self.content.strip()
        if len(body) > MAX_SKILL_CHARS:
            body = body[:MAX_SKILL_CHARS].rstrip() + "\n\n[Skill truncated by Libre Claw]"
        return "\n".join(
            [
                f"Skill: {self.title or self.name}",
                f"Scope: {self.scope}",
                f"Path: {self.path}",
                "",
                body,
            ]
        )


class SkillStore:
    """Loads bundled, user, and project skills for prompt injection and slash commands."""

    def __init__(
        self,
        project_root: Path | str,
        *,
        user_root: Path | str | None = None,
        include_bundled: bool = True,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.user_root = Path(user_root).expanduser() if user_root is not None else default_user_skills_path()
        self.project_skills_root = self.project_root / ".libre-claw" / "skills"
        self.bundled_root = default_bundled_skills_path()
        self.include_bundled = include_bundled

    async def list_skills(self) -> list[Skill]:
        return await _to_thread(self._list_skills_sync)

    async def add_skill(self, name: str, content: str, *, scope: SkillScope = "user") -> Skill:
        return await _to_thread(self._add_skill_sync, name, content, scope)

    async def edit_skill(self, name: str, content: str, *, scope: SkillScope | None = None) -> Skill:
        return await _to_thread(self._edit_skill_sync, name, content, scope)

    async def delete_skill(self, name: str, *, scope: SkillScope | None = None) -> bool:
        return await _to_thread(self._delete_skill_sync, name, scope)

    async def relevant_skills(self, prompt: str, *, limit: int = 5) -> list[Skill]:
        return await _to_thread(self._relevant_skills_sync, prompt, limit)

    def relevant_skill_texts(self, prompt: str, *, limit: int = 5) -> list[str]:
        return [skill.prompt_text for skill in self._relevant_skills_sync(prompt, limit)]

    def _list_skills_sync(self) -> list[Skill]:
        skills = []
        if self.include_bundled:
            skills.extend(self._load_scope("bundled", self.bundled_root))
        skills.extend(self._load_scope("user", self.user_root))
        skills.extend(self._load_scope("project", self.project_skills_root))
        skills.sort(key=lambda skill: (SCOPE_ORDER[skill.scope], skill.name))
        return skills

    def _load_scope(self, scope: SkillScope, root: Path) -> list[Skill]:
        if not root.exists():
            return []
        skills: list[Skill] = []
        for path in sorted(root.glob("*.md")):
            skill = _load_skill_file(path, scope, path.stem)
            if skill is not None:
                skills.append(skill)
        for path in sorted(root.glob("*/SKILL.md")):
            skill = _load_skill_file(path, scope, path.parent.name)
            if skill is not None:
                skills.append(skill)
        return skills

    def _add_skill_sync(self, name: str, content: str, scope: SkillScope) -> Skill:
        slug = normalize_skill_name(name)
        root = self._root_for_scope(scope)
        path = root / f"{slug}.md"
        if path.exists() or (root / slug / "SKILL.md").exists():
            raise SkillError(f"Skill already exists: {slug}")
        _write_text(path, _skill_content(slug, content))
        skill = _load_skill_file(path, scope, slug)
        if skill is None:
            raise SkillError(f"Could not load skill after writing: {slug}")
        return skill

    def _edit_skill_sync(self, name: str, content: str, scope: SkillScope | None) -> Skill:
        existing = self._find_skill(name, scope=scope)
        if existing is None:
            raise SkillError(f"Skill not found: {name}")
        if existing.scope not in MUTABLE_SCOPES:
            raise SkillError(f"Bundled skill {existing.name} cannot be edited directly; add a user or project override.")
        _write_text(existing.path, _skill_content(existing.name, content))
        skill = _load_skill_file(existing.path, existing.scope, existing.name)
        if skill is None:
            raise SkillError(f"Could not load skill after editing: {existing.name}")
        return skill

    def _delete_skill_sync(self, name: str, scope: SkillScope | None) -> bool:
        existing = self._find_skill(name, scope=scope)
        if existing is None:
            return False
        if existing.scope not in MUTABLE_SCOPES:
            raise SkillError(f"Bundled skill {existing.name} cannot be deleted; add a user or project override.")
        existing.path.unlink()
        if existing.path.name == "SKILL.md":
            try:
                existing.path.parent.rmdir()
            except OSError:
                pass
        return True

    def _find_skill(self, name: str, *, scope: SkillScope | None = None) -> Skill | None:
        slug = normalize_skill_name(name)
        matches = [skill for skill in self._list_skills_sync() if skill.name == slug and (scope is None or skill.scope == scope)]
        if len(matches) > 1:
            raise SkillError(f"Skill name exists in multiple scopes; specify --user or --project: {slug}")
        return matches[0] if matches else None

    def _relevant_skills_sync(self, prompt: str, limit: int) -> list[Skill]:
        tokens = _tokens(prompt)
        if not tokens:
            return []
        scored: dict[str, tuple[int, Skill]] = {}
        for skill in self._list_skills_sync():
            haystack = _tokens(" ".join([skill.name, skill.title, skill.description, skill.content]))
            score = sum(3 if token in _tokens(skill.title + " " + skill.description) else 1 for token in tokens if token in haystack)
            if score > 0:
                existing = scored.get(skill.name)
                if existing is None or score > existing[0] or (
                    score == existing[0] and SCOPE_ORDER[skill.scope] > SCOPE_ORDER[existing[1].scope]
                ):
                    scored[skill.name] = (score, skill)
        ranked = list(scored.values())
        ranked.sort(key=lambda item: (-item[0], -SCOPE_ORDER[item[1].scope], item[1].name))
        return [skill for _, skill in ranked[: max(1, limit)]]

    def _root_for_scope(self, scope: SkillScope) -> Path:
        if scope == "bundled":
            raise SkillError("Bundled skills are read-only.")
        return self.user_root if scope == "user" else self.project_skills_root


def default_user_skills_path() -> Path:
    return Path.home() / ".libre-claw" / "skills"


def default_bundled_skills_path() -> Path:
    return Path(__file__).resolve().parents[1] / "skills"


def normalize_skill_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", name.strip().lower()).strip("-._")
    if not slug:
        raise SkillError("Skill name cannot be empty.")
    if slug in {".", ".."} or "/" in slug or "\\" in slug:
        raise SkillError(f"Invalid skill name: {name}")
    return slug[:80]


def _load_skill_file(path: Path, scope: SkillScope, name: str) -> Skill | None:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    title = _first_heading(content) or name.replace("-", " ").title()
    description = _description(content)
    return Skill(
        name=normalize_skill_name(name),
        scope=scope,
        path=path,
        title=title,
        description=description,
        content=content,
    )


def _first_heading(content: str) -> str | None:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def _description(content: str) -> str:
    in_frontmatter = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter and stripped.lower().startswith("description:"):
            return stripped.split(":", 1)[1].strip().strip("\"'")
    for line in content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and stripped != "---":
            return stripped[:240]
    return ""


def _skill_content(name: str, content: str) -> str:
    body = content.strip()
    if not body:
        body = "\n".join(
            [
                "---",
                f"name: {name}",
                f"description: Repeatable {name.replace('-', ' ')} workflow.",
                "---",
                "",
                f"# {name.replace('-', ' ').title()}",
                "",
                "Use this skill when this workflow appears again.",
                "",
                "## When to Use",
                "",
                "- Describe the user requests or task patterns that should trigger this skill.",
                "",
                "## Prerequisites",
                "",
                "- List required tools, credentials, files, or APIs. Do not include secrets.",
                "",
                "## Procedure",
                "",
                "1. Inspect the relevant context first.",
                "2. Use the smallest reliable set of tools.",
                "3. Keep intermediate scratch output out of the final answer.",
                "",
                "## Pitfalls",
                "",
                "- Note common failure modes and what to avoid.",
                "",
                "## Verification",
                "",
                "- State how the agent should know the task is done.",
                "",
            ]
        )
    if not body.endswith("\n"):
        body += "\n"
    return body


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9][a-z0-9._-]{1,}", text.lower()) if token not in _STOPWORDS}


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


async def _to_thread(function: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    import asyncio

    return await asyncio.to_thread(function, *args, **kwargs)


_STOPWORDS = {
    "and",
    "an",
    "as",
    "at",
    "be",
    "by",
    "do",
    "for",
    "if",
    "in",
    "is",
    "it",
    "me",
    "my",
    "no",
    "of",
    "on",
    "or",
    "the",
    "this",
    "that",
    "to",
    "with",
    "from",
    "into",
    "when",
    "then",
    "have",
    "your",
    "you",
    "use",
    "using",
}
