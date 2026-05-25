# Copyright 2026 Kroonen AI Inc. (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence

from libre_claw.core.agent import AgentDone, AgentEvent, AgentTextDelta
from libre_claw.core.goal import (
    GoalComplete,
    GoalJudgeResult,
    GoalRunner,
    GoalStopped,
    GoalTurnStarted,
    parse_judge_decision,
)
from libre_claw.core.session import ChatMessage, Session
from libre_claw.providers.base import Done, LLMProvider, StreamEvent, TextDelta, ToolSchema, Usage


class ScriptedGoalAgent:
    def __init__(self, session: Session, responses: list[str]) -> None:
        self.session = session
        self.responses = responses
        self.prompts: list[str] = []

    async def run(self, user_message: str) -> AsyncIterator[AgentEvent]:
        self.prompts.append(user_message)
        self.session.add_user_message(user_message)
        response = self.responses.pop(0) if self.responses else "nothing else"
        yield AgentTextDelta(response)
        self.session.add_assistant_message(response)
        yield AgentDone(Usage(input_tokens=1, output_tokens=1))


class ScriptedJudgeProvider(LLMProvider):
    def __init__(self, decisions: list[dict[str, object]]) -> None:
        self.decisions = decisions
        self.prompts: list[str] = []

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSchema] | None = None,
        system: str | None = None,
        stream: bool = True,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamEvent]:
        del tools, system, stream, temperature, max_tokens
        self.prompts.append(str(messages[0].content[0].get("text", "")))
        decision = self.decisions.pop(0)
        yield TextDelta(json.dumps(decision))
        yield Done(usage=Usage(input_tokens=2, output_tokens=3), stop_reason="stop")


async def test_goal_runner_reprompts_until_judge_marks_done() -> None:
    session = Session()
    agent = ScriptedGoalAgent(session, ["first pass", "verified pass"])
    judge = ScriptedJudgeProvider(
        [
            {
                "done": False,
                "confidence": 0.4,
                "reason": "Verification is missing.",
                "next_prompt": "Run tests and fix failures.",
            },
            {
                "done": True,
                "confidence": 0.95,
                "reason": "Tests passed.",
                "next_prompt": "",
            },
        ]
    )

    events = [event async for event in GoalRunner(agent, judge, session, "make tests pass", max_turns=3).run()]

    assert [event.turn for event in events if isinstance(event, GoalTurnStarted)] == [1, 2]
    assert len([event for event in events if isinstance(event, GoalJudgeResult)]) == 2
    assert isinstance(events[-1], GoalComplete)
    assert len(agent.prompts) == 2
    assert "Run tests and fix failures." in agent.prompts[1]
    assert judge.prompts and "first pass" in judge.prompts[0]


async def test_goal_runner_stops_at_max_turns() -> None:
    session = Session()
    agent = ScriptedGoalAgent(session, ["one", "two"])
    judge = ScriptedJudgeProvider(
        [
            {"done": False, "confidence": 0.2, "reason": "Not done.", "next_prompt": "Continue."},
            {"done": False, "confidence": 0.3, "reason": "Still not done.", "next_prompt": "Continue."},
        ]
    )

    events = [event async for event in GoalRunner(agent, judge, session, "finish", max_turns=2).run()]

    assert isinstance(events[-1], GoalStopped)
    assert "Reached max goal turns" in events[-1].reason
    assert len(agent.prompts) == 2


def test_parse_judge_decision_accepts_fenced_json() -> None:
    decision = parse_judge_decision(
        '```json\n{"done": true, "confidence": 1.2, "reason": "ok", "next_prompt": ""}\n```'
    )

    assert decision.done is True
    assert decision.confidence == 1.0
    assert decision.reason == "ok"


def test_parse_judge_decision_handles_invalid_json() -> None:
    decision = parse_judge_decision("not json")

    assert decision.done is False
    assert decision.confidence == 0.0
    assert "not valid JSON" in decision.reason
    assert decision.next_prompt
