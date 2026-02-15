"""Agent core for Libre Claw.

Provides Agent class with handle_message, heartbeat_tick, and mode switching.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .backends import BackendConfig, BaseBackend, Message, get_backend
from .config import Config
from .heartbeat import Heartbeat
from .memory import MemoryManager
from .workspace import Workspace


class AgentMode(Enum):
    """Agent operating modes."""

    DIRECT = "direct"  # Direct conversation with user
    HEARTBEAT = "heartbeat"  # Autonomous heartbeat mode


@dataclass
class AgentState:
    """Current state of the agent."""

    mode: AgentMode = AgentMode.DIRECT
    session_id: str = ""
    started_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    message_count: int = 0


class Agent:
    """Main agent class for Libre Claw.

    Handles message processing, mode switching, and coordinates
    backend, workspace, heartbeat, and memory components.
    """

    def __init__(
        self,
        backend: Optional[BaseBackend] = None,
        workspace: Optional[Workspace] = None,
        config: Optional[Config] = None,
        memory: Optional[MemoryManager] = None,
    ):
        """Initialize the agent.

        Args:
            backend: AI backend instance
            workspace: Workspace instance
            config: Configuration
            memory: Memory manager instance
        """
        self.config = config or Config()

        # Initialize backend
        if backend is None:
            backend = get_backend(
                self.config.backend.type,
                BackendConfig(
                    claude_path=self.config.backend.claude_path,
                    anthropic_api_key=self.config.backend.anthropic_api_key,
                    ollama_url=self.config.backend.ollama_url,
                    ollama_model=self.config.backend.ollama_model,
                ),
            )
        self.backend = backend

        # Initialize workspace
        if workspace is None:
            workspace = Workspace(
                path=self.config.workspace.path,
                config=self.config,
            )
        self.workspace = workspace

        # Initialize memory
        if memory is None and self.config.memory.enabled:
            memory = MemoryManager(
                url=self.config.memory.chromadb_url,
                collection_name="libre_claw_memories",
            )
        self.memory = memory

        # Initialize heartbeat
        self.heartbeat = Heartbeat(
            workspace=self.workspace,
            config=self.config.heartbeat,
            on_tick=self._on_heartbeat_tick,
        )

        # Agent state
        self.state = AgentState(
            session_id=str(uuid.uuid4()),
            started_at=datetime.now(),
        )

    def handle_message(
        self,
        message: str,
        context: Optional[Dict[str, str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Handle an incoming message in direct mode.

        Args:
            message: User message
            context: Optional additional context
            tools: Optional tool definitions

        Returns:
            Agent response
        """
        # Switch to direct mode
        self._set_mode(AgentMode.DIRECT)

        # Load workspace context if not provided
        if context is None:
            context = self.workspace.get_context()

        # Build system prompt from workspace
        system_prompt = self._build_system_prompt(context)

        # Add user message to history
        self.backend.add_message(Message(role="user", content=message))

        # Get completion
        response = self.backend.complete(
            prompt=message,
            system_prompt=system_prompt,
            context=context,
            tools=tools,
        )

        # Add response to history
        self.backend.add_message(Message(role="assistant", content=response.content))

        # Update state
        self.state.message_count += 1
        self.state.last_activity = datetime.now()

        return response.content

    def handle_heartbeat(
        self,
        prompt: Optional[str] = None,
    ) -> str:
        """Handle a heartbeat poll in heartbeat mode.

        Args:
            prompt: Optional custom heartbeat prompt

        Returns:
            Heartbeat response
        """
        # Switch to heartbeat mode
        self._set_mode(AgentMode.HEARTBEAT)

        # Load workspace context
        context = self.workspace.get_context()

        # Build heartbeat prompt
        hb_prompt = prompt or self.config.heartbeat.prompt

        # Read HEARTBEAT.md for tasks
        hb_content = self.workspace.read("HEARTBEAT.md")
        if hb_content:
            hb_prompt += f"\n\n# HEARTBEAT.md\n{hb_content}"

        # Build system prompt
        system_prompt = self._build_system_prompt(context, is_heartbeat=True)

        # Get completion
        response = self.backend.complete(
            prompt=hb_prompt,
            system_prompt=system_prompt,
            context=context,
        )

        # Update state
        self.state.last_activity = datetime.now()

        return response.content

    def heartbeat_tick(self) -> str:
        """Execute a heartbeat tick manually.

        Returns:
            Response from heartbeat
        """
        return self.handle_heartbeat()

    def _on_heartbeat_tick(self) -> Any:
        """Internal callback for heartbeat ticks."""
        return self.handle_heartbeat()

    def _set_mode(self, mode: AgentMode) -> None:
        """Switch agent mode.

        Args:
            mode: New mode
        """
        if self.state.mode != mode:
            self.state.mode = mode
            print(f"Agent mode switched to: {mode.value}")

    def _build_system_prompt(
        self,
        context: Dict[str, str],
        is_heartbeat: bool = False,
    ) -> str:
        """Build system prompt from workspace context.

        Args:
            context: Workspace context files
            is_heartbeat: Whether this is a heartbeat prompt

        Returns:
            Formatted system prompt
        """
        parts = []

        # Add identity and rules
        if "SOUL.md" in context:
            parts.append(f"# SOUL\n{context['SOUL.md']}")

        if "AGENTS.md" in context:
            parts.append(f"# RULES\n{context['AGENTS.md']}")

        # Add user context
        if "USER.md" in context:
            parts.append(f"# USER\n{context['USER.md']}")

        # Add mode-specific instructions
        if is_heartbeat:
            parts.append(
                "\n# MODE\nYou are in HEARTBEAT MODE. Be proactive. Maintain systems. "
                "Follow HEARTBEAT.md checklist. Do not infer or repeat old tasks."
            )
        else:
            parts.append(
                "\n# MODE\nYou are in DIRECT MODE. Follow RULE #0: single task discipline. "
                "Do only what the user asks. Nothing more."
            )

        return "\n\n".join(parts)

    async def start_heartbeat(self) -> None:
        """Start the heartbeat loop."""
        await self.heartbeat.start()

    async def stop_heartbeat(self) -> None:
        """Stop the heartbeat loop."""
        await self.heartbeat.stop()

    def search_memory(
        self,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search long-term memory.

        Args:
            query: Search query
            memory_type: Optional type filter
            limit: Maximum results

        Returns:
            List of matching memories
        """
        if not self.memory:
            return []

        return self.memory.recall(
            query=query,
            memory_type=memory_type,
            limit=limit,
        )

    def remember(
        self,
        content: str,
        memory_type: str = "general",
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """Store a memory.

        Args:
            content: Memory content
            memory_type: Type of memory
            importance: Importance 0-1
            tags: Optional tags

        Returns:
            True if successful
        """
        if not self.memory:
            return False

        return self.memory.remember(
            content=content,
            memory_type=memory_type,
            importance=importance,
            tags=tags,
        )

    def get_session_info(self) -> Dict[str, Any]:
        """Get current session information.

        Returns:
            Session info dictionary
        """
        return {
            "session_id": self.state.session_id,
            "mode": self.state.mode.value,
            "started_at": self.state.started_at.isoformat() if self.state.started_at else None,
            "last_activity": self.state.last_activity.isoformat() if self.state.last_activity else None,
            "message_count": self.state.message_count,
            "backend": self.backend.name,
            "workspace": str(self.workspace.path),
        }
