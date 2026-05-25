# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

from libre_claw.core.agent import AgentError, AgentEvent
from libre_claw.core.session import ChatMessage, ContentBlock, Session, text_block
from libre_claw.providers.base import Done, LLMProvider, ProviderError, TextDelta, Usage, combine_usage


JUDGE_SYSTEM_PROMPT = """\
You are the Libre Claw goal completion judge.
Decide whether the coding agent has fully completed the user's goal.

Rules:
- You do not have tools and must not ask for tool access.
- Mark done true only when the transcript shows the goal is verifiably complete.
- If verification is missing, done must be false.
- If done is false, next_prompt must be a concise instruction for the agent's next turn.
- Return only JSON with this shape:
  {"done": boolean, "confidence": number, "reason": string, "next_prompt": string}
"""

MAX_JUDGE_TRANSCRIPT_CHARS = 24000


class AgentLike(Protocol):
    def run(self, user_message: str) -> AsyncIterator[AgentEvent]:
        """Run one agent turn."""


@dataclass(frozen=True)
class JudgeDecision:
    done: bool
    confidence: float
    reason: str
    next_prompt: str
    raw_response: str = ""


@dataclass(frozen=True)
class GoalTurnStarted:
    turn: int
    max_turns: int
    prompt: str


@dataclass(frozen=True)
class GoalJudgeResult:
    turn: int
    decision: JudgeDecision
    usage: Usage | None = None


@dataclass(frozen=True)
class GoalComplete:
    turns: int
    decision: JudgeDecision


@dataclass(frozen=True)
class GoalStopped:
    turns: int
    reason: str
    decision: JudgeDecision | None = None


GoalEvent = AgentEvent | GoalTurnStarted | GoalJudgeResult | GoalComplete | GoalStopped


class GoalRunner:
    """Bounded supervisor that repeats agent turns until a judge says the goal is done."""

    def __init__(
        self,
        agent: AgentLike,
        judge_provider: LLMProvider,
        session: Session,
        goal: str,
        max_turns: int = 20,
        judge_temperature: float = 0.0,
        judge_max_tokens: int = 1024,
    ) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be >= 1")
        self.agent = agent
        self.judge_provider = judge_provider
        self.session = session
        self.goal = goal.strip()
        self.max_turns = max_turns
        self.judge_temperature = judge_temperature
        self.judge_max_tokens = judge_max_tokens

    async def run(self) -> AsyncIterator[GoalEvent]:
        prompt = _initial_goal_prompt(self.goal, self.max_turns)
        last_decision: JudgeDecision | None = None

        for turn in range(1, self.max_turns + 1):
            yield GoalTurnStarted(turn=turn, max_turns=self.max_turns, prompt=prompt)

            agent_failed = False
            async for event in self.agent.run(prompt):
                yield event
                if isinstance(event, AgentError):
                    agent_failed = True

            if agent_failed:
                yield GoalStopped(turns=turn, reason="Agent turn failed before goal completion.", decision=last_decision)
                return

            decision, usage = await self._judge(turn)
            last_decision = decision
            yield GoalJudgeResult(turn=turn, decision=decision, usage=usage)

            if decision.reason.startswith("Judge provider error:"):
                yield GoalStopped(turns=turn, reason=decision.reason, decision=decision)
                return

            if decision.done:
                yield GoalComplete(turns=turn, decision=decision)
                return

            prompt = _continuation_prompt(self.goal, decision, turn, self.max_turns)

        yield GoalStopped(
            turns=self.max_turns,
            reason=f"Reached max goal turns ({self.max_turns}) before the judge marked the goal done.",
            decision=last_decision,
        )

    async def _judge(self, turn: int) -> tuple[JudgeDecision, Usage | None]:
        chunks: list[str] = []
        usage: Usage | None = None
        prompt = _judge_prompt(self.goal, turn, self.max_turns, self.session)
        messages = [ChatMessage(role="user", content=[text_block(prompt)])]

        async for event in self.judge_provider.complete(
            messages=messages,
            tools=None,
            system=JUDGE_SYSTEM_PROMPT,
            stream=True,
            temperature=self.judge_temperature,
            max_tokens=self.judge_max_tokens,
        ):
            if isinstance(event, TextDelta):
                chunks.append(event.text)
            elif isinstance(event, Done):
                usage = combine_usage(usage, event.usage)
            elif isinstance(event, ProviderError):
                return (
                    JudgeDecision(
                        done=False,
                        confidence=0.0,
                        reason=f"Judge provider error: {event.message}",
                        next_prompt="Inspect the current state, continue the goal, and verify your work.",
                        raw_response=event.message,
                    ),
                    usage,
                )

        raw = "".join(chunks).strip()
        return parse_judge_decision(raw), usage


def parse_judge_decision(raw_response: str) -> JudgeDecision:
    try:
        payload = _json_object_from_text(raw_response)
    except ValueError as exc:
        return JudgeDecision(
            done=False,
            confidence=0.0,
            reason=f"Judge response was not valid JSON: {exc}",
            next_prompt="Review the goal, inspect current progress, continue the most important remaining work, and verify it.",
            raw_response=raw_response,
        )

    done = bool(payload.get("done", False))
    confidence = _confidence(payload.get("confidence", 0.0))
    reason = _clean_text(payload.get("reason"), "Judge did not provide a reason.")
    next_prompt = _clean_text(payload.get("next_prompt"), "")
    if not done and not next_prompt:
        next_prompt = "Continue the goal, focus on unverified requirements, and verify the result."
    return JudgeDecision(
        done=done,
        confidence=confidence,
        reason=reason,
        next_prompt=next_prompt,
        raw_response=raw_response,
    )


def _json_object_from_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("missing JSON object")

    parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("top-level value is not an object")
    return parsed


def _confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _clean_text(value: Any, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    cleaned = value.strip()
    return cleaned or fallback


def _initial_goal_prompt(goal: str, max_turns: int) -> str:
    return (
        "Start supervised goal mode.\n\n"
        f"Goal:\n{goal}\n\n"
        f"You have up to {max_turns} agent turns. Work autonomously, use tools, and verify completion."
    )


def _continuation_prompt(goal: str, decision: JudgeDecision, turn: int, max_turns: int) -> str:
    return (
        "Continue supervised goal mode.\n\n"
        f"Goal:\n{goal}\n\n"
        f"Completed turns: {turn}/{max_turns}\n"
        f"Judge reason:\n{decision.reason}\n\n"
        f"Next instruction:\n{decision.next_prompt}\n\n"
        "Do not repeat completed work unless needed for verification."
    )


def _judge_prompt(goal: str, turn: int, max_turns: int, session: Session) -> str:
    transcript = _session_transcript(session)
    return (
        f"Goal:\n{goal}\n\n"
        f"Turn just completed: {turn}/{max_turns}\n\n"
        "Transcript and tool observations:\n"
        f"{transcript}\n\n"
        "Decide whether the goal is fully complete."
    )


def _session_transcript(session: Session) -> str:
    parts: list[str] = []
    if session.summary:
        parts.append("Summary:\n" + session.summary)

    for message in session.messages:
        text = _message_text(message.content)
        if text:
            parts.append(f"{message.role.upper()}:\n{text}")

    transcript = "\n\n".join(parts)
    if len(transcript) <= MAX_JUDGE_TRANSCRIPT_CHARS:
        return transcript
    return "... transcript truncated ...\n" + transcript[-MAX_JUDGE_TRANSCRIPT_CHARS:]


def _message_text(blocks: list[ContentBlock]) -> str:
    parts: list[str] = []
    for block in blocks:
        block_type = block.get("type")
        if block_type == "text":
            parts.append(str(block.get("text", "")))
        elif block_type == "tool_use":
            parts.append(
                f"Tool call {block.get('name', '')}: "
                f"{json.dumps(block.get('input', {}), sort_keys=True, default=str)}"
            )
        elif block_type == "tool_result":
            status = "error" if block.get("is_error") else "result"
            parts.append(f"Tool {status} {block.get('tool_use_id', '')}: {block.get('content', '')}")
    return "\n".join(part for part in parts if part)
