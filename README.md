# Libre Claw

An agentic AI framework for Kroonen AI Inc. that wraps the Claude Code CLI (`claude`) as its primary backend, with support for additional backends (Anthropic API, Ollama).

## Overview

Libre Claw is an agentic AI framework designed to provide a flexible, extensible interface for interacting with Claude Code and other AI backends. It features:

- **TUI (Terminal User Interface)**: Interactive Rich-based terminal interface
- **HTTP API**: FastAPI-based REST API for programmatic access
- **Multiple Backend Support**: Claude Code, Anthropic API, Ollama
- **Session Management**: Persistent sessions with workspace context
- **Heartbeat System**: Autonomous task execution during idle periods
- **Memory Integration**: ChromaDB-backed long-term memory

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Libre Claw                        │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐ │
│  │   TUI    │  │ HTTP API │  │ Discord/Telegram  │ │
│  │  (Rich)  │  │ (FastAPI)│  │    (future)       │ │
│  └────┬─────┘  └────┬─────┘  └────────┬──────────┘ │
│       └──────────────┼────────────────┘             │
│                      ▼                              │
│              ┌───────────────┐                      │
│              │  Agent Core   │                      │
│              │  - Session    │                      │
│              │  - Workspace  │◄── .md files         │
│              │  - Heartbeat  │                      │
│              └───────┬───────┘                      │
│                      │                              │
│          ┌───────────┼───────────┐                  │
│          ▼           ▼           ▼                  │
│  ┌────────────┐ ┌──────────┐ ┌──────────┐          │
│  │Claude Code │ │ Anthropic│ │  Ollama  │          │
│  │  Backend   │ │   API    │ │ Backend  │          │
│  │(claude -p) │ │ Backend  │ │ (local)  │          │
│  └────────────┘ │ (future) │ └──────────┘          │
│                 └──────────┘                        │
└─────────────────────────────────────────────────────┘
```

## Requirements

- Python 3.11+
- Claude Code CLI v2.1.42+ (for Claude Code backend)
- Ollama (optional, for local models)
- ChromaDB server (optional, for memory)

## Installation

```bash
# Clone the repository
git clone git@git.kroonen.ai:kroonen-ai/libre-claw.git
cd libre-claw

# Install with uv
uv pip install -e .

# Or with pip
pip install -e .
```

## Configuration

Create a `config.yaml` file in your workspace or use the default configuration:

```yaml
# config.yaml
backend:
  type: claude_code  # claude_code, anthropic, ollama
  claude_path: /opt/homebrew/bin/claude

workspace:
  path: ~/.openclaw/workspace

heartbeat:
  enabled: true
  interval_seconds: 30

memory:
  chromadb_url: http://stargate.local:8420
```

## Usage

### CLI

```bash
# Start the TUI
python -m libre_claw

# Start the API server
python -m libre_claw --api

# Initialize a new workspace
python -m libre_claw init /path/to/workspace
```

### Python API

```python
from libre_claw import Agent
from libre_claw.workspace import Workspace
from libre_claw.backends import ClaudeCodeBackend

# Create backend and workspace
backend = ClaudeCodeBackend()
workspace = Workspace("~/my-workspace")

# Create agent
agent = Agent(backend=backend, workspace=workspace)

# Send a message
response = agent.handle_message("Hello, how are you?")
print(response)
```

## Workspace Files

Libre Claw uses markdown files for configuration and context:

- `SOUL.md` — Agent's core identity and purpose
- `USER.md` — User profile and preferences
- `IDENTITY.md` — Current session identity
- `AGENTS.md` — Workspace rules and behavioral guidelines
- `MEMORY.md` — Long-term memory and curated learnings
- `HEARTBEAT.md` — Autonomous task checklist
- `HEARTBEAT-AUDIT.md` — Heartbeat execution log
- `INFRA.md` — Infrastructure documentation
- `TOOLS.md` — Tool configurations and notes

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=libre_claw
```

## License

Apache License 2.0 — See [LICENSE](LICENSE) for details.

## Authors

- Robin Kroonen — Founder, Kroonen AI Inc.
