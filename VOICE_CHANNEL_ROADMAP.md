# LibreClaw Voice + Channel Roadmap

Last updated: 2026-02-16

## Scope

This roadmap defines how LibreClaw can add optional voice/channel integrations without weakening core coding-assistant safety.

## Security boundaries (non-negotiable)

- Gateway remains loopback-first by default.
- Any remote access requires explicit auth (`LIBRE_CLAW_API_TOKEN`) and optional rate limiting.
- Channel/voice connectors run as optional modules, disabled by default.
- Tool execution policy remains explicit (`LIBRE_CLAW_SANDBOX_POLICY`), never silently escalated by channels.
- Message ingestion from channels is treated as untrusted input and must pass allowlist/auth policy.

## Phased plan

## Phase 1: Voice local loop (opt-in)

- Add local microphone capture command.
- Add speech-to-text provider abstraction.
- Add push-to-talk mode in TUI.
- No always-on wake word in phase 1.

Exit criteria:
- Voice input works locally in one session.
- No background daemon requirement.
- No auto-execution without explicit user confirmation.

## Phase 2: Channel bridge (opt-in)

- Add minimal webhook/channel adapter interface.
- Start with one channel implementation behind feature flag.
- Add allowlist and sender verification per channel.

Exit criteria:
- Message routing is deterministic and auditable.
- Per-channel enable/disable can be done at runtime.

## Phase 3: Advanced presence

- Typing/presence indicators.
- Optional reply threading.
- Structured event stream for channel activity.

Exit criteria:
- Channel events do not degrade core coding UX in TUI.
- Backpressure/retry behavior is observable and bounded.

## Non-goals (for now)

- No default public internet exposure.
- No automatic multi-channel fanout.
- No hidden background actions on behalf of user accounts.
- No privileged host actions triggered solely by remote channel input.

