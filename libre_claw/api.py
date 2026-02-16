"""FastAPI HTTP API for Libre Claw."""

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .agent import Agent
from .backends import BackendConfig, get_backend
from .config import Config
from .memory import MemoryManager
from .workspace import Workspace


# Request/Response models
class MessageRequest(BaseModel):
    """Request model for sending a message."""

    message: str
    context: Optional[Dict[str, str]] = None
    tools: Optional[List[Dict[str, Any]]] = None


class MessageResponse(BaseModel):
    """Response model for messages."""

    content: str
    session_id: str
    mode: str


class HeartbeatRequest(BaseModel):
    """Request model for heartbeat."""

    prompt: Optional[str] = None


class MemorySearchRequest(BaseModel):
    """Request model for memory search."""

    query: str
    memory_type: Optional[str] = None
    limit: int = 10


class MemoryAddRequest(BaseModel):
    """Request model for adding memory."""

    content: str
    memory_type: str = "general"
    importance: float = 0.5
    tags: Optional[List[str]] = None


class SessionInfo(BaseModel):
    """Session information."""

    session_id: str
    mode: str
    started_at: Optional[str]
    last_activity: Optional[str]
    message_count: int
    backend: str
    workspace: str


# Create FastAPI app
app = FastAPI(
    title="Libre Claw API",
    description="HTTP API for Libre Claw agentic AI framework",
    version="0.1.0",
)

# Global agent instance
_agent: Optional[Agent] = None
_app_config: Optional[Config] = None
_gateway_mode: bool = False
_autostart_proactive: bool = False


def get_agent() -> Agent:
    """Get or create the global agent instance."""
    global _agent
    if _agent is None:
        config = _app_config or Config.load()
        backend = get_backend(
            config.backend.type,
            BackendConfig(
                claude_path=config.backend.claude_path,
                codex_path=config.backend.codex_path,
                codex_model=config.backend.codex_model,
                openai_codex_auth_profiles_file=config.backend.openai_codex_auth_profiles_file,
                openai_codex_profile=config.backend.openai_codex_profile,
                openai_codex_model=config.backend.openai_codex_model,
                openai_codex_base_url=config.backend.openai_codex_base_url,
                anthropic_api_key=config.backend.anthropic_api_key,
                anthropic_auth_file=config.backend.anthropic_auth_file,
                anthropic_model=config.backend.anthropic_model,
                anthropic_base_url=config.backend.anthropic_base_url,
                openai_api_key=config.backend.openai_api_key,
                openai_auth_file=config.backend.openai_auth_file,
                openai_model=config.backend.openai_model,
                openai_base_url=config.backend.openai_base_url,
                ollama_url=config.backend.ollama_url,
                ollama_model=config.backend.ollama_model,
            ),
        )
        workspace = Workspace(config.workspace.path, config)
        memory = None
        if config.memory.enabled:
            memory = MemoryManager(config.memory.chromadb_url)

        _agent = Agent(backend=backend, workspace=workspace, config=config, memory=memory)
        if _autostart_proactive:
            _agent.start_proactive()

    return _agent


def _proactive_status_payload(agent: Agent) -> Dict[str, Any]:
    return {
        "gateway_mode": _gateway_mode,
        "proactive_running": agent.proactive_running,
        "heartbeat_enabled": bool(agent.config.heartbeat.enabled),
        "interval_seconds": agent.heartbeat._resolve_interval_seconds(agent.config.heartbeat.interval_seconds),
        "last_activity": agent.state.last_activity.isoformat() if agent.state.last_activity else None,
        "heartbeat_state": agent.workspace.get_heartbeat_state(),
    }


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize agent and optionally start proactive loop on server boot."""
    if _autostart_proactive:
        agent = get_agent()
        agent.start_proactive()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Stop background proactive loop on server shutdown."""
    global _agent
    if _agent:
        _agent.stop_proactive()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Libre Claw API",
        "version": "0.1.0",
        "description": "HTTP API for Libre Claw agentic AI framework",
        "gateway_mode": _gateway_mode,
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    agent = get_agent()
    return {
        "status": "healthy",
        "backend": agent.backend.name,
        "mode": agent.state.mode.value,
    }


@app.post("/message", response_model=MessageResponse)
async def send_message(request: MessageRequest):
    """Send a message to the agent.

    Args:
        request: Message request

    Returns:
        Agent response
    """
    agent = get_agent()

    try:
        response = agent.handle_message(
            message=request.message,
            context=request.context,
            tools=request.tools,
        )

        return MessageResponse(
            content=response,
            session_id=agent.state.session_id,
            mode=agent.state.mode.value,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/heartbeat")
async def trigger_heartbeat(request: HeartbeatRequest = None):
    """Trigger a heartbeat tick.

    Args:
        request: Optional heartbeat request

    Returns:
        Heartbeat response
    """
    agent = get_agent()

    try:
        prompt = request.prompt if request else None
        response = agent.handle_heartbeat(prompt=prompt)

        return {
            "content": response,
            "mode": agent.state.mode.value,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/proactive/status")
async def proactive_status():
    """Get proactive loop status."""
    agent = get_agent()
    return _proactive_status_payload(agent)


@app.post("/proactive/start")
async def proactive_start():
    """Start proactive loop."""
    agent = get_agent()
    agent.start_proactive()
    payload = _proactive_status_payload(agent)
    payload["status"] = "started"
    return payload


@app.post("/proactive/stop")
async def proactive_stop():
    """Stop proactive loop."""
    agent = get_agent()
    agent.stop_proactive()
    payload = _proactive_status_payload(agent)
    payload["status"] = "stopped"
    return payload


@app.get("/gateway/status")
async def gateway_status():
    """Gateway alias for proactive status."""
    agent = get_agent()
    return _proactive_status_payload(agent)


@app.post("/gateway/wake")
async def gateway_wake(request: HeartbeatRequest = None):
    """Force an immediate heartbeat run."""
    agent = get_agent()
    prompt = request.prompt if request else None
    try:
        response = agent.handle_heartbeat(prompt=prompt)
        payload = _proactive_status_payload(agent)
        payload["status"] = "ran"
        payload["content"] = response
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session", response_model=SessionInfo)
async def get_session():
    """Get current session information.

    Returns:
        Session information
    """
    agent = get_agent()
    info = agent.get_session_info()

    return SessionInfo(**info)


@app.post("/session/clear")
async def clear_session():
    """Clear conversation history."""
    agent = get_agent()
    agent.backend.clear_history()

    return {"status": "cleared", "session_id": agent.state.session_id}


@app.post("/memory/search")
async def search_memory(request: MemorySearchRequest):
    """Search long-term memory.

    Args:
        request: Search request

    Returns:
        Search results
    """
    agent = get_agent()

    if not agent.memory:
        raise HTTPException(status_code=503, detail="Memory not enabled")

    try:
        results = agent.search_memory(
            query=request.query,
            memory_type=request.memory_type,
            limit=request.limit,
        )

        return {"results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/add")
async def add_memory(request: MemoryAddRequest):
    """Add a memory.

    Args:
        request: Memory to add

    Returns:
        Success status
    """
    agent = get_agent()

    if not agent.memory:
        raise HTTPException(status_code=503, detail="Memory not enabled")

    try:
        success = agent.remember(
            content=request.content,
            memory_type=request.memory_type,
            importance=request.importance,
            tags=request.tags,
        )

        if success:
            return {"status": "added"}
        else:
            raise HTTPException(status_code=500, detail="Failed to add memory")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workspace/files")
async def list_workspace_files(pattern: str = "*.md"):
    """List workspace files.

    Args:
        pattern: File pattern

    Returns:
        List of files
    """
    agent = get_agent()
    files = agent.workspace.list_files(pattern)

    return {
        "files": [str(f.relative_to(agent.workspace.path)) for f in files]
    }


@app.get("/workspace/file/{filename}")
async def read_workspace_file(filename: str):
    """Read a workspace file.

    Args:
        filename: File name

    Returns:
        File contents
    """
    agent = get_agent()
    content = agent.workspace.read(filename)

    if content is None:
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    return {"filename": filename, "content": content}


@app.post("/workspace/file/{filename}")
async def write_workspace_file(filename: str, content: str):
    """Write to a workspace file.

    Args:
        filename: File name
        content: Content to write

    Returns:
        Success status
    """
    agent = get_agent()
    agent.workspace.write(filename, content)

    return {"status": "saved", "filename": filename}


def create_app(
    config: Optional[Config] = None,
    *,
    gateway_mode: bool = False,
    autostart_proactive: bool = False,
) -> FastAPI:
    """Create FastAPI app with custom config.

    Args:
        config: Configuration
        gateway_mode: Whether app is running as gateway service
        autostart_proactive: Whether proactive loop should start on startup

    Returns:
        FastAPI app
    """
    global _agent, _app_config, _gateway_mode, _autostart_proactive

    _agent = None  # Force recreation with supplied lifecycle settings
    _app_config = config
    _gateway_mode = bool(gateway_mode)
    _autostart_proactive = bool(autostart_proactive)

    return app
