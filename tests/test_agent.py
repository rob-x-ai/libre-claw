"""Tests for agent module."""

import pytest

from libre_claw.agent import Agent, AgentMode, AgentState
from libre_claw.backends.base import BackendConfig, BaseBackend, Message, Response
from libre_claw.config import Config
from libre_claw.workspace import Workspace


class MockBackend(BaseBackend):
    """Mock backend for testing."""

    def __init__(self):
        super().__init__(BackendConfig())
        self._response = "Mock response"

    @property
    def name(self) -> str:
        return "mock"

    def set_response(self, text: str):
        self._response = text

    def complete(self, prompt, system_prompt=None, context=None, tools=None):
        return Response(content=self._response, model="mock-1.0")

    def chat(self, messages, tools=None):
        return Response(content=self._response, model="mock-1.0")


class TestAgentState:
    """Test agent state."""

    def test_default_state(self):
        state = AgentState()
        assert state.mode == AgentMode.DIRECT
        assert state.message_count == 0

    def test_mode_values(self):
        assert AgentMode.DIRECT.value == "direct"
        assert AgentMode.HEARTBEAT.value == "heartbeat"


class TestAgent:
    """Test agent class."""

    def _make_agent(self, tmp_path):
        """Create an agent with mock backend for testing."""
        config = Config()
        config.git.enabled = False
        config.memory.enabled = False

        backend = MockBackend()
        workspace = Workspace(str(tmp_path), config)
        workspace.init()

        return Agent(backend=backend, workspace=workspace, config=config)

    def test_create_agent(self, tmp_path):
        agent = self._make_agent(tmp_path)
        assert agent.state.mode == AgentMode.DIRECT
        assert agent.backend.name == "mock"

    def test_handle_message(self, tmp_path):
        agent = self._make_agent(tmp_path)
        agent.backend.set_response("Hello from mock!")

        response = agent.handle_message("Hi there")
        assert response == "Hello from mock!"
        assert agent.state.message_count == 1
        assert agent.state.mode == AgentMode.DIRECT

    def test_handle_heartbeat(self, tmp_path):
        agent = self._make_agent(tmp_path)
        agent.backend.set_response("HEARTBEAT_OK")

        response = agent.handle_heartbeat()
        assert "HEARTBEAT_OK" in response
        assert agent.state.mode == AgentMode.HEARTBEAT

    def test_mode_switching(self, tmp_path):
        agent = self._make_agent(tmp_path)

        agent.handle_heartbeat()
        assert agent.state.mode == AgentMode.HEARTBEAT

        agent.handle_message("Direct message")
        assert agent.state.mode == AgentMode.DIRECT

    def test_session_info(self, tmp_path):
        agent = self._make_agent(tmp_path)
        info = agent.get_session_info()

        assert "session_id" in info
        assert info["mode"] == "direct"
        assert info["backend"] == "mock"
        assert info["message_count"] == 0

    def test_search_memory_disabled(self, tmp_path):
        agent = self._make_agent(tmp_path)
        results = agent.search_memory("test query")
        assert results == []

    def test_remember_disabled(self, tmp_path):
        agent = self._make_agent(tmp_path)
        result = agent.remember("something")
        assert result is False
