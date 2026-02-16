# Libre Claw 🐾

An agentic AI framework by [Kroonen AI Inc.](https://kroonen.ai)

Libre Claw wraps AI backends (Claude Code CLI, Anthropic API, OpenAI API/OAuth, Ollama) into a persistent agent with workspace management, heartbeat autonomy, semantic memory, and a polished terminal UI.

## Features

- **Multiple backends** — Claude Code CLI, Anthropic API, OpenAI API/OAuth token, Ollama (local)
- **Workspace system** — Markdown-based context files (SOUL.md, USER.md, AGENTS.md, etc.)
- **Mode-aware context** — Direct mode loads MEMORY.md, heartbeat mode loads HEARTBEAT.md
- **Heartbeat autonomy** — Idle-aware proactive loop with closed-loop follow-ups, retry/backoff behavior, and duration-style intervals (`30m`, `2h`, etc.)
- **Gateway daemon mode** — Long-running loopback server that keeps proactive heartbeat alive outside the TUI session
- **Semantic memory** — ChromaDB integration for long-term memory search/storage
- **Rich TUI** — OpenCode-style startup panel, bordered composer, paste summaries, keybinding-aware multiline input, diff/script previews
- **HTTP API** — FastAPI server for programmatic access
- **Cost tracking** — Token usage and cost estimation
- **Git sync** — Auto-commit and push workspace changes
- **Daily notes** — Automatic `memory/YYYY-MM-DD.md` journal entries

## Quick Start

```bash
# Clone
git clone https://github.com/kroonen-ai/libre-claw.git
cd libre-claw

# Install
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Initialize workspace
libre-claw --init ~/my-workspace

# Start TUI (auto-creates ./.workspace if not specified)
libre-claw

# Or explicit workspace
libre-claw -w ~/my-workspace

# Or start API server
libre-claw --api -w ~/my-workspace

# Or run dedicated proactive gateway (recommended for always-on heartbeat)
libre-claw --gateway -w ~/my-workspace

# Diagnostics / onboarding / upgrade
libre-claw --doctor -w ~/my-workspace
libre-claw --onboard
libre-claw --self-update

# Skills catalog + install
libre-claw --skills-list -w ~/my-workspace
libre-claw --skills-install coding-agent -w ~/my-workspace
```

## Skills (curated + install)

Use CLI-managed skill discovery/install inspired by OpenClaw:

```bash
# Show installed and curated skills
libre-claw --skills-list -w ~/my-workspace

# Install from curated catalog by name
libre-claw --skills-install coding-agent -w ~/my-workspace

# Install from git (single skill directory in repo)
libre-claw --skills-install "https://github.com/openclaw/openclaw.git#skills/healthcheck" -w ~/my-workspace

# Install from local path
libre-claw --skills-install ~/.codex/skills/.system/skill-creator -w ~/my-workspace
```

Catalog behavior:
- Built-in curated entries include selected OpenClaw skills and local Codex system skills.
- Optional external catalog file: set `LIBRE_CLAW_SKILLS_CATALOG=/path/to/skills-catalog.json`.
- Workspace-local catalog override: `<workspace>/skills-catalog.json`.
- Catalog JSON shape: `{ "skills": [{ "name": "...", "source": "...", "description": "..." }] }`.

## Workspace Structure

```
my-workspace/
├── SOUL.md              # Agent personality and traits
├── USER.md              # User profile
├── IDENTITY.md          # Agent identity
├── AGENTS.md            # Operating rules (direct vs heartbeat mode)
├── MEMORY.md            # Long-term curated memory
├── HEARTBEAT.md         # Autonomous task checklist
├── HEARTBEAT-AUDIT.md   # Heartbeat run log
├── INFRA.md             # Infrastructure notes
├── TOOLS.md             # Local tool configuration
├── config.yaml          # Framework configuration
├── heartbeat-state.json # Heartbeat state tracking
└── memory/
    └── 2026-02-15.md    # Daily notes
```

## TUI Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/clear` | Clear conversation history |
| `/info` | Show session information |
| `/memory <query>` | Search long-term memory |
| `/heartbeat` | Trigger manual heartbeat |
| `/heartbeat log [n]` | Show last heartbeat audit events |
| `/proactive [start\|stop\|status\|wake]` | Control proactive loop (gateway-first, local fallback) |
| `/agent [build\|plan\|status]` | Switch execution profile (`plan` is read-only) |
| `/mode [direct\|heartbeat]` | Show/switch mode |
| `/backend [claude_code\|codex_cli\|anthropic\|openai\|ollama]` | Show/switch model provider |
| `/login openai` | Use Codex OAuth session (or paste token) and switch backend |
| `/model [model-id]` | Show/set model for active backend and save config |
| `/context` | Show loaded context files |
| `/daily <text>` | Append to today's daily note |
| `/files` | List workspace files |
| `/read <file>` | Read a workspace file |
| `/cost` | Show token usage |
| `/quit` | Exit |

## Composer UX

- `Enter` sends the prompt immediately.
- `Shift+Enter` inserts a newline without sending.
- `Ctrl+J` is supported as a newline fallback.
- `Ctrl+U` clears the current input line.
- Large pastes are summarized inline as `++ paste N: X lines ++` to keep the composer readable.
- Proposed edits render in syntax-highlighted diff/script panels before approval.

## Proactive Heartbeat Behavior

- Heartbeat proactive mode runs in the background when `heartbeat.enabled: true` (or when started with `/proactive start`).
- Ticks are idle-aware: the loop waits until user inactivity reaches the configured interval.
- `interval_seconds` supports numeric and duration forms (`30`, `15m`, `2h`, `1d`) and is resolved safely across proactive + async heartbeat paths.
- `NO_REPLY` outcomes are retried sooner than a full interval to keep autonomous flow responsive.
- Failures use bounded retry delay instead of killing the loop.
- Every run updates `HEARTBEAT-AUDIT.md` and `heartbeat-state.json`.

## Gateway Mode (OpenClaw-style)

Run a dedicated gateway process when you want proactive autonomy independent from the TUI lifecycle:

```bash
libre-claw --gateway -w ~/my-workspace
```

Gateway defaults:
- host: `127.0.0.1` (loopback)
- port: `8421`

Override via CLI:

```bash
libre-claw --gateway --gateway-host 127.0.0.1 --gateway-port 8421 -w ~/my-workspace
```

Gateway endpoints:
- `GET /gateway/status` — proactive state + heartbeat state snapshot
- `POST /gateway/wake` — force immediate heartbeat run
- `GET /proactive/status` — proactive status
- `POST /proactive/start` — start proactive loop
- `POST /proactive/stop` — stop proactive loop

TUI integration:
- `/proactive ...` calls gateway endpoints first (URL from `LIBRE_CLAW_GATEWAY_URL`, default `http://127.0.0.1:8421`).
- If gateway is unavailable, TUI falls back to local proactive control.
- On TUI startup, if a gateway is reachable, local proactive autostart is skipped to avoid double loops.
- Set `LIBRE_CLAW_FORCE_LOCAL_PROACTIVE=1` to force local proactive even when gateway is up.

Gateway service management:
```bash
libre-claw --gateway-service install -w ~/my-workspace
libre-claw --gateway-service start
libre-claw --gateway-service status
libre-claw --gateway-service stop
libre-claw --gateway-service uninstall
```

API hardening (optional):
- `LIBRE_CLAW_API_TOKEN=<token>` enables token auth for non-public API routes.
- Use header `X-Libre-Claw-Token: <token>` or `Authorization: Bearer <token>`.
- `LIBRE_CLAW_API_RATE_LIMIT_PER_MIN=<n>` enables simple per-IP request limiting.

## Containerized Tool Execution (workspace-only)

To let the agent use shell tools (e.g., `sed`, `awk`, `bash`) in an isolated workspace container:

```bash
export LIBRE_CLAW_TOOL_MODE=container
libre-claw -w ~/my-workspace
```

Behavior:
- Commands run in a persistent sandbox container by default (one container per workspace, reused via `exec`).
- Sandbox container name format: `libre-claw-sandbox-<workspace-hash>`.
- Sandbox is prewarmed on agent startup when container mode is enabled.
- Workspace is bind-mounted at `/workspace`.
- Working directory is `/workspace`.
- Network is disabled (`--network none`).
- Files remain on your host workspace (bind mount).
- Set `LIBRE_CLAW_CONTAINER_PERSISTENT=0` to fall back to ephemeral `run --rm` containers.

Quick checks:
```bash
docker ps | rg libre-claw-sandbox
docker inspect libre-claw-sandbox-<workspace-hash> --format '{{.State.Running}}'
```

Environment knobs:
- `LIBRE_CLAW_TOOL_MODE=container` enables container execution (`local` by default).
- `LIBRE_CLAW_SANDBOX_POLICY` supports `host`, `container`, `non-main`.
  - `host`: always run on host.
  - `container`: always run in container.
  - `non-main`: direct mode on host, non-direct (heartbeat/proactive) in container.
- `LIBRE_CLAW_CONTAINER_ENGINE` (`docker` or `podman`, default `docker` with podman fallback).
- `LIBRE_CLAW_CONTAINER_IMAGE` (default `ubuntu:24.04`).
- `LIBRE_CLAW_CONTAINER_SHELL` (default `bash`).
- `LIBRE_CLAW_CONTAINER_PERSISTENT` (`1` default, set `0` for ephemeral per-command containers).
- `LIBRE_CLAW_CONTAINER_MEMORY` (default `1g`).
- `LIBRE_CLAW_CONTAINER_CPUS` (default `1.5`).
- `LIBRE_CLAW_CONTAINER_UID` / `LIBRE_CLAW_CONTAINER_GID` (default to current user when available).
- `LIBRE_CLAW_SKILLS_CATALOG` (optional path/URL to curated skills catalog JSON).

Heartbeat audit files:
- `HEARTBEAT-AUDIT.md` (human-readable log)
- `HEARTBEAT-AUDIT.jsonl` (structured events for tooling/queries)

## Configuration

```yaml
# config.yaml
backend:
  type: openai                # claude_code, codex_cli, anthropic, openai, ollama
  claude_path: /opt/homebrew/bin/claude

  # Anthropic backend
  anthropic_auth_file: ~/.config/libre-claw/auth/anthropic.json
  anthropic_model: claude-3-7-sonnet-latest

  # OpenAI backend (API key or OAuth access_token JSON)
  openai_auth_file: ~/.config/libre-claw/auth/openai.json
  openai_model: gpt-4.1

  # Ollama backend
  ollama_url: http://localhost:11434
  ollama_model: llama3

workspace:
  path: ~/.libre-claw/workspace

heartbeat:
  enabled: true
  interval_seconds: 30m  # supports seconds/minutes/hours, e.g. 30, 15m, 2h
  proactive_iterations: 3  # max follow-up model turns per heartbeat
  auto_apply_actions: true  # apply valid ```diff``` / ```bash``` heartbeat actions automatically
  prompt: |
    Read HEARTBEAT.md and follow it.
    If nothing needs action, reply NO_REPLY.
    Use MEMORY_UPDATE: <text> to curate memory during proactive runs.

memory:
  enabled: true
  chromadb_url: http://localhost:8420

git:
  enabled: true
  auto_commit: true
  remote: origin
```

Environment variables override config: `LIBRE_CLAW_BACKEND__TYPE=ollama`

## Backends

### Claude Code CLI (default)
Requires [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed:
```bash
npm install -g @anthropic-ai/claude-code
```

### Anthropic API
Set either env or auth file:
```bash
export LIBRE_CLAW_BACKEND__TYPE=anthropic
export ANTHROPIC_API_KEY=sk-ant-...
# or use ~/.config/libre-claw/auth/anthropic.json with {"api_key":"..."}
```

### OpenAI API / OAuth token
Recommended flow:
```bash
codex login
libre-claw
# inside TUI:
/login openai
```
`/login openai` tries to import token from common Codex/OpenAI auth locations,
or lets you paste a token and stores it in `~/.config/libre-claw/auth/openai.json`.

Alternative env setup:
```bash
export LIBRE_CLAW_BACKEND__TYPE=openai
export OPENAI_API_KEY=sk-...
```

### Ollama (local)
Requires [Ollama](https://ollama.ai) running:
```bash
ollama serve
ollama pull llama3
libre-claw --backend ollama
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check libre_claw/

# Type check
mypy libre_claw/
```

## License

Apache 2.0 — © 2026 Kroonen AI Inc.
