# Libre Claw Release Notes

## 0.1.0 - 2026-05-24

First shippable Libre Claw release from Kroonen AI Inc.

### Current State

- Terminal-native Textual TUI with streaming chat, Markdown rendering, command
  palette, slash-command suggestions, `/model` provider/model onboarding,
  startup ASCII art, session status, and startup release notes.
- `/model <provider>:<model> --global` persists the selected provider/model in
  `~/.libre-claw/config.toml`.
- Status bar context meter plus `/compact status`, `/compact --force`, and
  `/compact --keep N` controls for context-window management.
- File explorer with parent-directory navigation, agent working-directory
  sync, a visible `Hide` control, a left-side `Files` rail for restoring the
  sidebar, and `Ctrl+B` toggling.
- Provider support for Anthropic, OpenAI, OpenRouter, and Ollama. Default model
  selections are `claude-opus-4-6`, `gpt-5.5`, and `qwen3.6:27b`, with Ollama
  Cloud examples centered on `kimi-k2.6:cloud`.
- OpenRouter support with fixed Libre Claw app attribution headers:
  `https://kroonen.ai`, `Libre Claw`, and the `cli-agent` category.
- Cumulative session token tracking in the status bar, TUI `/cost`, and
  Telegram `/cost`. OpenRouter requests usage accounting so provider-reported
  cost, cached tokens, and reasoning tokens appear when OpenRouter returns
  them.
- Ollama covers local daemon use, direct Ollama Cloud access, and
  OpenAI-compatible Ollama endpoints. Native tool calling and XML tool-call
  fallback are both available.
- ReAct-style async agent loop with tool calling, concurrent tool execution,
  interrupt handling, context compaction, and configurable system prompt from
  TOML.
- Built-in `read_file`, `write_file`, `edit_file`, `list_directory`, and
  `bash` tools.
- Interactive TUI permission panel with approve, deny, always allow tool, and
  always allow exact command options. Dangerous sandbox-blocked commands show a
  warning and require one-time approval or denial.
- TUI polish: thin `#0070F3` scrollbars, blue user labels, purple `#8B5CF6`
  Libre Claw assistant labels, dark/light theme support, and cleaner panel
  borders.
- SQLite memory for facts, sessions, summaries, and file edit logs.
- Telegram daemon with allowlist auth, streaming updates, per-chat sessions,
  model/provider commands, and inline permission prompts.
- Secure key storage through environment variables, OS keyring, or encrypted
  local fallback. API keys are not stored in TOML.
- OAuth 2.0 PKCE and JWT scaffolding for a future dashboard.
- Apache-2.0 licensing with Kroonen AI Inc. source headers.
- GitHub Actions test/build CI and expanded user-facing README documentation.

### Known Limits

- Cost display depends on provider-reported usage. OpenRouter returns cost when
  usage accounting is available; other providers may only return token counts.
- Search, browser, git PR helpers, and richer diff UX are not yet at full
  parity with larger agent harnesses.
- Codex-style Sign in with ChatGPT OAuth is not implemented yet. OpenAI model
  calls currently use `OPENAI_API_KEY` or secure stored keys.
- GitLab `main` may remain protected; mirrored updates currently target the
  configured writable branch.

## Release Checklist

Use this checklist before publishing Libre Claw.

1. Update `src/libre_claw/__init__.py` and `pyproject.toml` to the same version.
2. Update `CHANGELOG.md` and this file with the release date and summary.
3. Run:

   ```bash
   python3 -m pytest
   python3 -m compileall src tests
   git diff --check
   python3 -m build
   ```

4. Inspect the wheel contents and confirm `libre_claw/default.toml` and
   `libre_claw/RELEASE.md` are included.
5. Install the wheel into a clean environment and run:

   ```bash
   libre-claw --version
   libre-claw --help
   libre-claw config defaults
   libre-claw auth status
   ```

6. Smoke-test at least one real provider before tagging.
