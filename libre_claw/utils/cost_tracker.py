"""Cost tracking utilities for Libre Claw.

Tracks usage and costs per session for different backends.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


# Cost per 1M tokens (approximate)
CLAUDE_COSTS = {
    "claude-opus-4-5": {"input": 15.00, "output": 75.00},  # opus
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},  # sonnet
    "claude-haiku-3-5": {"input": 0.80, "output": 4.00},  # haiku
    "claude-opus-4": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "claude-haiku-3": {"input": 0.80, "output": 4.00},
    "default": {"input": 3.00, "output": 15.00},
}

ANTHROPIC_COSTS = CLAUDE_COSTS  # Same as Claude Code

OLLAMA_COSTS = {
    # Ollama is free (local), but we track compute time
    "default": {"input": 0.0, "output": 0.0},
}


@dataclass
class UsageRecord:
    """Record of API usage for a single request."""

    timestamp: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    backend: str
    duration_ms: int


@dataclass
class SessionCost:
    """Cost tracking for a session."""

    session_id: str
    backend: str
    start_time: datetime
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    request_count: int = 0
    records: list[UsageRecord] = field(default_factory=list)

    def add_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
    ) -> None:
        """Add a usage record and update totals."""
        cost = calculate_cost(
            backend=self.backend,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        record = UsageRecord(
            timestamp=datetime.now(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            backend=self.backend,
            duration_ms=duration_ms,
        )

        self.records.append(record)
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += cost
        self.request_count += 1

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "backend": self.backend,
            "start_time": self.start_time.isoformat(),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost": self.total_cost,
            "request_count": self.request_count,
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
        }


class CostTracker:
    """Track costs across sessions."""

    def __init__(self):
        """Initialize cost tracker."""
        self.sessions: Dict[str, SessionCost] = {}

    def start_session(self, session_id: str, backend: str) -> SessionCost:
        """Start tracking a new session.

        Args:
            session_id: Unique session identifier
            backend: Backend type

        Returns:
            New session cost tracker
        """
        session = SessionCost(
            session_id=session_id,
            backend=backend,
            start_time=datetime.now(),
        )
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[SessionCost]:
        """Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session cost tracker or None
        """
        return self.sessions.get(session_id)

    def end_session(self, session_id: str) -> Optional[SessionCost]:
        """End and return session summary.

        Args:
            session_id: Session identifier

        Returns:
            Session cost tracker or None
        """
        return self.sessions.pop(session_id, None)

    def get_total_cost(self) -> float:
        """Get total cost across all sessions."""
        return sum(s.total_cost for s in self.sessions.values())

    def get_summary(self) -> Dict:
        """Get summary of all sessions."""
        return {
            "total_sessions": len(self.sessions),
            "total_cost": self.get_total_cost(),
            "sessions": [s.to_dict() for s in self.sessions.values()],
        }


def calculate_cost(
    backend: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Calculate cost for API usage.

    Args:
        backend: Backend type
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD
    """
    if backend == "ollama":
        return 0.0  # Ollama is free

    # Get cost rates
    if backend in ("claude_code", "anthropic"):
        costs = CLAUDE_COSTS
    else:
        costs = {"default": {"input": 0.0, "output": 0.0}}

    # Find matching model
    model_lower = model.lower()
    rates = costs.get("default")

    for model_key, model_rates in costs.items():
        if model_key != "default" and model_key in model_lower:
            rates = model_rates
            break

    if rates is None:
        rates = costs["default"]

    # Calculate cost
    input_cost = (input_tokens / 1_000_000) * rates["input"]
    output_cost = (output_tokens / 1_000_000) * rates["output"]

    return input_cost + output_cost
