# Copyright 2026 Kroonen AI (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, cast

from libre_claw.core.automations import (
    AutomationError,
    AutomationRecord,
    AutomationRoute,
    AutomationStatus,
    AutomationStore,
)
from libre_claw.core.tools import BaseTool, ToolResult, register_tool


@register_tool
class ScheduleListTool(BaseTool):
    name = "schedule_list"
    description = "List Libre Claw recurring automations from the local automation store."
    parameters = {
        "limit": {
            "type": "integer",
            "description": "Maximum schedules to return.",
            "default": 50,
        },
    }
    permission_level = "allow"

    async def execute(self, limit: int = 50) -> ToolResult:
        if not self.context.automations_enabled:
            return ToolResult(error="Automations are disabled by [automations].enabled")
        if limit < 1:
            return ToolResult(error="limit must be >= 1")
        store = AutomationStore(self.context.automations_root)
        records = await store.list(limit=min(limit, 200))
        if not records:
            return ToolResult(content="No schedules found.", metadata={"count": 0})
        lines = ["Schedules:"]
        for record in records:
            lines.append(_record_line(record))
        return ToolResult(
            content="\n".join(lines),
            metadata={"count": len(records), "automations": [_record_payload(record) for record in records]},
        )


@register_tool
class ScheduleTool(BaseTool):
    name = "schedule"
    description = (
        "Create or change Libre Claw recurring automations. Use this instead of asking the user "
        "to edit host cron, launchd, or systemd timers. Supports schedules like daily HH:MM, "
        "weekly mon HH:MM, every N minutes, hourly, and five-field cron."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "Action to perform: create, update, pause, resume, or delete.",
            "enum": ["create", "update", "pause", "resume", "delete"],
        },
        "automation_id": {
            "type": "string",
            "description": "Existing automation id for update, pause, resume, or delete.",
            "default": "",
        },
        "name": {
            "type": "string",
            "description": "Human-readable schedule name.",
            "default": "",
        },
        "prompt": {
            "type": "string",
            "description": "Self-contained task prompt for the scheduled run.",
            "default": "",
        },
        "schedule": {
            "type": "string",
            "description": "daily HH:MM, weekly mon HH:MM, every N minutes, hourly, or five-field cron.",
            "default": "",
        },
        "route": {
            "type": "string",
            "description": "Where scheduled results go.",
            "enum": ["report", "tui", "telegram"],
            "default": "report",
        },
        "status": {
            "type": "string",
            "description": "Initial or updated status.",
            "enum": ["active", "paused"],
            "default": "active",
        },
        "provider": {
            "type": "string",
            "description": "Provider override. Empty uses the current global default.",
            "default": "",
        },
        "model": {
            "type": "string",
            "description": "Model override. Empty uses the current global default.",
            "default": "",
        },
        "telegram_chat_id": {
            "type": ["integer", "null"],
            "description": "Telegram chat id required when route is telegram.",
            "default": None,
        },
    }
    required = ("action",)
    permission_level = "ask"

    async def execute(
        self,
        action: str,
        automation_id: str = "",
        name: str = "",
        prompt: str = "",
        schedule: str = "",
        route: str = "",
        status: str = "",
        provider: str = "",
        model: str = "",
        telegram_chat_id: int | str | None = None,
    ) -> ToolResult:
        if not self.context.automations_enabled:
            return ToolResult(error="Automations are disabled by [automations].enabled")

        action = action.strip().lower()
        try:
            chat_id = _optional_chat_id(telegram_chat_id)
        except AutomationError as exc:
            return ToolResult(error=str(exc))
        store = AutomationStore(self.context.automations_root)
        try:
            if action == "create":
                return await self._create(
                    store,
                    name=name,
                    prompt=prompt,
                    schedule=schedule,
                    route=route,
                    status=status,
                    provider=provider,
                    model=model,
                    telegram_chat_id=chat_id,
                )
            if action == "update":
                return await self._update(
                    store,
                    automation_id=automation_id,
                    name=name,
                    prompt=prompt,
                    schedule=schedule,
                    route=route,
                    status=status,
                    provider=provider,
                    model=model,
                    telegram_chat_id=chat_id,
                )
            if action in {"pause", "resume"}:
                return await self._status(store, automation_id=automation_id, status="paused" if action == "pause" else "active")
            if action == "delete":
                return await self._delete(store, automation_id=automation_id)
        except AutomationError as exc:
            return ToolResult(error=str(exc))
        return ToolResult(error="action must be create, update, pause, resume, or delete")

    async def _create(
        self,
        store: AutomationStore,
        *,
        name: str,
        prompt: str,
        schedule: str,
        route: str,
        status: str,
        provider: str,
        model: str,
        telegram_chat_id: int | None,
    ) -> ToolResult:
        clean_route = _route(route)
        if clean_route == "telegram" and telegram_chat_id is None:
            return ToolResult(error="telegram_chat_id is required when route is telegram")
        record = await store.create(
            name=name,
            prompt=prompt,
            schedule=schedule,
            route=clean_route,
            provider=provider.strip() or self.context.default_provider,
            model=model.strip() or self.context.default_model,
            working_directory=self.context.working_directory,
            status=_status(status),
            telegram_chat_id=telegram_chat_id,
            metadata={"created_by": "schedule_tool"},
        )
        return _record_result("Created schedule", record)

    async def _update(
        self,
        store: AutomationStore,
        *,
        automation_id: str,
        name: str,
        prompt: str,
        schedule: str,
        route: str,
        status: str,
        provider: str,
        model: str,
        telegram_chat_id: int | None,
    ) -> ToolResult:
        automation_id = automation_id.strip()
        if not automation_id:
            return ToolResult(error="automation_id is required for update")
        clean_route = _route(route) if route.strip() else None
        if clean_route == "telegram" and telegram_chat_id is None:
            existing = await store.load(automation_id)
            if existing is None or existing.telegram_chat_id is None:
                return ToolResult(error="telegram_chat_id is required when route is telegram")
        updates: dict[str, Any] = {
            "name": name if name.strip() else None,
            "prompt": prompt if prompt.strip() else None,
            "schedule": schedule if schedule.strip() else None,
            "route": clean_route,
            "status": _status(status) if status.strip() else None,
            "provider": provider.strip() if provider.strip() else None,
            "model": model.strip() if model.strip() else None,
        }
        if telegram_chat_id is not None:
            updates["telegram_chat_id"] = telegram_chat_id
        record = await store.update(automation_id, **updates)
        if record is None:
            return ToolResult(error=f"Unknown automation: {automation_id}")
        return _record_result("Updated schedule", record)

    async def _status(self, store: AutomationStore, *, automation_id: str, status: AutomationStatus) -> ToolResult:
        automation_id = automation_id.strip()
        if not automation_id:
            return ToolResult(error="automation_id is required")
        record = await store.update_status(automation_id, status)
        if record is None:
            return ToolResult(error=f"Unknown automation: {automation_id}")
        return _record_result(f"{status.title()} schedule", record)

    async def _delete(self, store: AutomationStore, *, automation_id: str) -> ToolResult:
        automation_id = automation_id.strip()
        if not automation_id:
            return ToolResult(error="automation_id is required")
        deleted = await store.delete(automation_id)
        if not deleted:
            return ToolResult(error=f"Unknown automation: {automation_id}")
        return ToolResult(content=f"Deleted schedule {automation_id}.", metadata={"automation_id": automation_id, "deleted": True})


def _route(value: str) -> AutomationRoute:
    route = value.strip().lower() or "report"
    if route not in {"report", "tui", "telegram"}:
        raise AutomationError("route must be report, tui, or telegram")
    return cast(AutomationRoute, route)


def _status(value: str) -> AutomationStatus:
    status = value.strip().lower() or "active"
    if status not in {"active", "paused"}:
        raise AutomationError("status must be active or paused")
    return cast(AutomationStatus, status)


def _optional_chat_id(value: int | str | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise AutomationError("telegram_chat_id must be an integer or null") from exc


def _record_result(prefix: str, record: AutomationRecord) -> ToolResult:
    return ToolResult(
        content=f"{prefix}:\n{_record_line(record)}",
        metadata={"automation": _record_payload(record)},
    )


def _record_line(record: AutomationRecord) -> str:
    model = ":".join(part for part in (record.provider, record.model) if part) or "default"
    chat = f" telegram_chat_id={record.telegram_chat_id}" if record.telegram_chat_id is not None else ""
    return (
        f"{record.automation_id} [{record.status}] {record.schedule} -> {record.route}{chat} | "
        f"{model} | next {record.next_run_at} | {record.name}"
    )


def _record_payload(record: AutomationRecord) -> dict[str, Any]:
    return {
        "automation_id": record.automation_id,
        "name": record.name,
        "prompt": record.prompt,
        "schedule": record.schedule,
        "route": record.route,
        "status": record.status,
        "provider": record.provider,
        "model": record.model,
        "working_directory": record.working_directory,
        "next_run_at": record.next_run_at,
        "last_run_at": record.last_run_at,
        "last_run_id": record.last_run_id,
        "telegram_chat_id": record.telegram_chat_id,
        "report_path": record.report_path,
    }
