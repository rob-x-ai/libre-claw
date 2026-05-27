# Copyright 2026 Kroonen AI (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

import pytest

from libre_claw.core.skills import SkillError, SkillStore, normalize_skill_name


async def test_skill_store_adds_lists_edits_and_deletes_user_skill(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    store = SkillStore(tmp_path / "project", include_bundled=False)

    added = await store.add_skill("Release Flow", "# Release Flow\n\nRun tests and update release notes.")
    listed = await store.list_skills()

    assert added.scope == "user"
    assert added.name == "release-flow"
    assert added.path == tmp_path / "home" / ".libre-claw" / "skills" / "release-flow.md"
    assert [skill.name for skill in listed] == ["release-flow"]

    edited = await store.edit_skill("release-flow", "# Release Flow\n\nRun pytest first.")
    assert "pytest" in edited.content

    assert await store.delete_skill("release-flow") is True
    assert await store.list_skills() == []


async def test_skill_store_supports_project_scope_and_agent_skill_layout(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    agent_skill = project / ".libre-claw" / "skills" / "review-code" / "SKILL.md"
    agent_skill.parent.mkdir(parents=True)
    agent_skill.write_text(
        "\n".join(
            [
                "---",
                "description: Review diffs with tests first.",
                "---",
                "# Review Code",
                "",
                "Inspect git diff, then run focused tests.",
            ]
        ),
        encoding="utf-8",
    )
    store = SkillStore(project, include_bundled=False)

    skills = await store.list_skills()

    assert len(skills) == 1
    assert skills[0].scope == "project"
    assert skills[0].name == "review-code"
    assert skills[0].title == "Review Code"
    assert skills[0].description == "Review diffs with tests first."
    assert "Agent" not in skills[0].prompt_text


async def test_relevant_skill_texts_returns_matching_skills(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    store = SkillStore(tmp_path / "project", include_bundled=False)
    await store.add_skill("pytest-debug", "# Pytest Debug\n\nUse for failing pytest cases and fixtures.")
    await store.add_skill("release-notes", "# Release Notes\n\nUse for changelog updates.")

    matches = store.relevant_skill_texts("Please debug failing pytest fixtures", limit=1)

    assert len(matches) == 1
    assert "Pytest Debug" in matches[0]
    assert "failing pytest" in matches[0]


async def test_skill_store_requires_scope_for_ambiguous_names(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    store = SkillStore(tmp_path / "project", include_bundled=False)
    await store.add_skill("deploy", "# Deploy\n\nUser deploy steps.")
    await store.add_skill("deploy", "# Deploy\n\nProject deploy steps.", scope="project")

    with pytest.raises(SkillError, match="multiple scopes"):
        await store.edit_skill("deploy", "# Deploy\n\nReplacement.")

    assert await store.delete_skill("deploy", scope="project") is True
    assert [skill.scope for skill in await store.list_skills()] == ["user"]


def test_normalize_skill_name_rejects_empty_names() -> None:
    with pytest.raises(SkillError):
        normalize_skill_name("...")


async def test_skill_store_loads_bundled_hacker_news_skill(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    store = SkillStore(tmp_path / "project")

    skills = await store.list_skills()
    matches = store.relevant_skill_texts("Tell me what is new on HN", limit=2)

    assert any(skill.scope == "bundled" and skill.name == "hacker-news-brief" for skill in skills)
    assert any("Hacker News Brief" in match for match in matches)
    assert any("no raw ID arrays" in match for match in matches)


async def test_bundled_skills_are_read_only(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    store = SkillStore(tmp_path / "project")

    with pytest.raises(SkillError, match="cannot be edited"):
        await store.edit_skill("hacker-news-brief", "# Replacement")

    with pytest.raises(SkillError, match="cannot be deleted"):
        await store.delete_skill("hacker-news-brief")


async def test_blank_skill_template_uses_agent_skills_shape(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    store = SkillStore(tmp_path / "project", include_bundled=False)

    added = await store.add_skill("Release Flow", "")

    assert "name: release-flow" in added.content
    assert "description: Repeatable release flow workflow." in added.content
    assert "## When to Use" in added.content
    assert "## Prerequisites" in added.content
    assert "## Procedure" in added.content
    assert "## Pitfalls" in added.content
    assert "## Verification" in added.content


async def test_project_skill_overrides_bundled_relevance(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    store = SkillStore(tmp_path / "project")
    await store.add_skill(
        "hacker-news-brief",
        "# Custom HN Brief\n\nUse for HN requests with Robin's private scoring rubric.",
        scope="project",
    )

    matches = store.relevant_skill_texts("HN brief", limit=1)

    assert len(matches) == 1
    assert "Custom HN Brief" in matches[0]
    assert "Hacker News Brief" not in matches[0]
