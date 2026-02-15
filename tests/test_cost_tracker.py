"""Tests for cost tracker module."""

import pytest

from libre_claw.utils.cost_tracker import (
    CostTracker,
    SessionCost,
    calculate_cost,
)


class TestCalculateCost:
    """Test cost calculation."""

    def test_ollama_is_free(self):
        cost = calculate_cost("ollama", "llama2", 1000, 500)
        assert cost == 0.0

    def test_claude_code_cost(self):
        cost = calculate_cost("claude_code", "claude-sonnet-4-5", 1_000_000, 0)
        assert cost == pytest.approx(3.0, rel=0.01)

    def test_claude_output_cost(self):
        cost = calculate_cost("claude_code", "claude-sonnet-4-5", 0, 1_000_000)
        assert cost == pytest.approx(15.0, rel=0.01)

    def test_unknown_model_uses_default(self):
        cost = calculate_cost("claude_code", "unknown-model", 1_000_000, 0)
        assert cost > 0  # should use default rates


class TestSessionCost:
    """Test session cost tracking."""

    def test_add_usage(self):
        session = SessionCost(
            session_id="test-123",
            backend="claude_code",
            start_time=__import__("datetime").datetime.now(),
        )

        session.add_usage(
            model="claude-sonnet-4-5",
            input_tokens=1000,
            output_tokens=500,
            duration_ms=1500,
        )

        assert session.request_count == 1
        assert session.total_input_tokens == 1000
        assert session.total_output_tokens == 500
        assert session.total_cost > 0
        assert len(session.records) == 1

    def test_to_dict(self):
        session = SessionCost(
            session_id="test-123",
            backend="ollama",
            start_time=__import__("datetime").datetime.now(),
        )
        d = session.to_dict()
        assert d["session_id"] == "test-123"
        assert d["backend"] == "ollama"
        assert d["request_count"] == 0


class TestCostTracker:
    """Test cost tracker."""

    def test_start_session(self):
        tracker = CostTracker()
        session = tracker.start_session("s1", "claude_code")
        assert session.session_id == "s1"

    def test_get_session(self):
        tracker = CostTracker()
        tracker.start_session("s1", "claude_code")
        session = tracker.get_session("s1")
        assert session is not None
        assert session.session_id == "s1"

    def test_get_nonexistent_session(self):
        tracker = CostTracker()
        assert tracker.get_session("nope") is None

    def test_end_session(self):
        tracker = CostTracker()
        tracker.start_session("s1", "claude_code")
        session = tracker.end_session("s1")
        assert session is not None
        assert tracker.get_session("s1") is None

    def test_total_cost(self):
        tracker = CostTracker()
        s1 = tracker.start_session("s1", "claude_code")
        s1.add_usage("claude-sonnet-4-5", 1000, 500, 100)

        s2 = tracker.start_session("s2", "ollama")
        s2.add_usage("llama2", 1000, 500, 100)

        total = tracker.get_total_cost()
        assert total > 0  # only claude_code has cost

    def test_summary(self):
        tracker = CostTracker()
        tracker.start_session("s1", "claude_code")
        summary = tracker.get_summary()
        assert summary["total_sessions"] == 1
