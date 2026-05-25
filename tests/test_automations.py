# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from libre_claw.core.automations import (
    AutomationError,
    AutomationStore,
    automation_examples,
    automation_is_due,
    next_scheduled_at,
)


def test_next_scheduled_at_supports_aliases_and_cron() -> None:
    base = datetime(2026, 5, 25, 8, 15, tzinfo=timezone.utc)

    assert next_scheduled_at("daily 09:00", after=base) == datetime(2026, 5, 25, 9, 0, tzinfo=timezone.utc)
    assert next_scheduled_at("daily 07:00", after=base) == datetime(2026, 5, 26, 7, 0, tzinfo=timezone.utc)
    assert next_scheduled_at("weekly mon 10:00", after=base) == datetime(2026, 5, 25, 10, 0, tzinfo=timezone.utc)
    assert next_scheduled_at("weekly mon 07:00", after=base) == datetime(2026, 6, 1, 7, 0, tzinfo=timezone.utc)
    assert next_scheduled_at("every 30 minutes", after=base) == datetime(2026, 5, 25, 8, 45, tzinfo=timezone.utc)
    assert next_scheduled_at("hourly", after=base) == datetime(2026, 5, 25, 9, 15, tzinfo=timezone.utc)
    assert next_scheduled_at("0 12 * * mon", after=base) == datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)


def test_next_scheduled_at_rejects_invalid_schedule() -> None:
    with pytest.raises(AutomationError):
        next_scheduled_at("whenever")


async def test_automation_store_create_list_due_mark_and_delete(tmp_path: Path) -> None:
    store = AutomationStore(tmp_path / "automations")
    now = datetime.now().astimezone()
    record = await store.create(
        name="Health",
        prompt="Check repo",
        schedule="daily 09:00",
        provider="openrouter",
        model="openrouter/auto",
        working_directory=tmp_path,
    )

    listed = await store.list()
    loaded = await store.load(record.automation_id)

    assert listed[0].automation_id == record.automation_id
    assert loaded is not None
    assert loaded.provider == "openrouter"
    assert loaded.model == "openrouter/auto"
    assert loaded.working_directory == str(tmp_path)
    assert not automation_is_due(record, now)

    due_record = await store.create(name="Due", prompt="Run now", schedule="every 1 minutes")
    due_payload = due_record.path.read_text(encoding="utf-8").replace(
        due_record.next_run_at,
        (now - timedelta(minutes=1)).isoformat(timespec="seconds"),
    )
    due_record.path.write_text(due_payload, encoding="utf-8")

    due = await store.due(now=now)
    assert [item.automation_id for item in due] == [due_record.automation_id]

    report = store.report_path(due_record.automation_id, "run-123")
    updated = await store.mark_run(due_record.automation_id, "run-123", now=now, report_path=report)
    assert updated is not None
    assert updated.last_run_id == "run-123"
    assert updated.report_path == str(report)
    assert updated.next_run_at > now.isoformat(timespec="seconds")

    paused = await store.update_status(record.automation_id, "paused")
    assert paused is not None
    assert paused.status == "paused"
    assert await store.delete(record.automation_id) is True
    assert await store.load(record.automation_id) is None


def test_automation_examples_include_required_workflows() -> None:
    examples = {name for name, _schedule, _prompt in automation_examples()}

    assert "Daily repo health check" in examples
    assert "Weekly dependency review" in examples
    assert "Morning brief" in examples
