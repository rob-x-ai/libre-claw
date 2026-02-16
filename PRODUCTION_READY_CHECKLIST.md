# LibreClaw Production Readiness Checklist

Last updated: 2026-02-16

Purpose: practical checklist to ship LibreClaw as a reliable coding assistant, taking proven patterns from OpenClaw and OpenCode.

## P0 - Must have before production

- [x] Gateway lifecycle as a real service (`libre-claw --gateway-service install|start|stop|status|uninstall`) - completed 2026-02-16
  - Inspired by: OpenClaw daemon install flow.
  - Done when: users can install as launchd/systemd service and recover after reboot.

- [x] `doctor` command for environment and config validation - completed 2026-02-16
  - Inspired by: OpenClaw `doctor`.
  - Done when: one command validates auth, gateway reachability, workspace permissions, container runtime, and heartbeat config.

- [x] Deterministic heartbeat event stream in TUI - completed 2026-02-16
  - Inspired by: OpenCode client/server + live TUI focus.
  - Done when: every completed heartbeat tick appears in chat with timestamp, action id, and result.

- [x] Deterministic heartbeat query command (`/heartbeat last`, `/heartbeat log`) - completed 2026-02-16
  - Inspired by: OpenClaw operational control surface.
  - Done when: user can query exact last N ticks without model hallucination.

- [x] Safe command execution contract (no false "cannot run commands" responses) - completed 2026-02-16
  - Inspired by: OpenCode coding-agent reliability expectations.
  - Done when: capability claims are always consistent with actual execution path.

- [x] Show command output by default after auto-apply shell execution - completed 2026-02-16
  - Inspired by: OpenCode transparent command UX.
  - Done when: stdout/stderr snippets are rendered in chat with truncation markers.

- [x] Sandbox policy profiles - completed 2026-02-16
  - Inspired by: OpenClaw security model (`main` vs sandboxed sessions).
  - Done when: clear policy modes exist (`host`, `container`, `non-main`) with default-safe settings.

- [x] Strong command sanitization that preserves valid shell syntax - completed 2026-02-16
  - Inspired by: production shell runners in agent frameworks.
  - Done when: pipelines and control-flow are preserved; unsafe commands are blocked with explicit reason.

- [x] Heartbeat action id rotation state (`HEARTBEAT-ROTATION.json`) enforced by runtime - completed 2026-02-16
  - Inspired by: reliable autonomous loops.
  - Done when: runtime validates no repeated action id unless others are inapplicable.

- [x] Structured audit schema and log compaction - completed 2026-02-16
  - Inspired by: OpenClaw operations focus.
  - Done when: audit entries are parseable and capped automatically.

## P1 - Should have for strong release

- [x] Onboarding wizard (`libre-claw --onboard`) - completed 2026-02-16
  - Inspired by: OpenClaw onboarding.
  - Done when: it sets backend auth, workspace, gateway, and sandbox mode in one flow.

- [x] Multi-agent modes with explicit permissions (`build`, `plan`) - completed 2026-02-16
  - Inspired by: OpenCode built-in agents.
  - Done when: `plan` is read-only and asks before execution; `build` has full edit permissions.

- [x] Model profile and failover system - completed 2026-02-16
  - Inspired by: OpenClaw model selection/failover.
  - Done when: backend/model profiles can fail over with clear status in TUI.

- [x] Gateway API auth and local security defaults - completed 2026-02-16
  - Inspired by: OpenClaw security defaults.
  - Done when: loopback default, optional token auth, rate limiting, and explicit remote exposure settings.

- [x] TUI status line with live gateway health - completed 2026-02-16
  - Inspired by: OpenCode TUI polish.
  - Done when: current agent mode, proactive state, last tick status, and sandbox state are always visible.

- [x] Session compaction and summary reliability improvements - completed 2026-02-16
  - Inspired by: both projects' long-running session handling.
  - Done when: compaction preserves key context and exposes summary freshness signals.

- [x] Release packaging and upgrade path - completed 2026-02-16
  - Inspired by: OpenCode/OpenClaw install story.
  - Done when: pipx/homebrew package path and `libre-claw self-update` (or documented upgrade) are stable.

## P2 - Nice to have after first stable release

- [x] Client/server split hardening for remote clients - completed 2026-02-16
  - Inspired by: OpenCode architecture.
  - Done when: TUI can connect to remote gateway cleanly with auth and reconnection.

- [x] Web control UI for proactive loop and logs - completed 2026-02-16
  - Inspired by: OpenClaw control UI.
  - Done when: basic browser dashboard supports status, wake, start/stop, and recent actions.

- [x] Skill marketplace/install flow - completed 2026-02-16
  - Inspired by: OpenClaw skills platform.
  - Done when: curated skills can be discovered and installed from CLI.

- [x] Voice and channel integrations roadmap - completed 2026-02-16
  - Inspired by: OpenClaw channel/node ecosystem.
  - Done when: explicit roadmap exists with security boundaries and non-goals.

## Test gates for "production-ready" label

- [ ] Reliability gate: 24h proactive run with zero stuck ticks and no contradictory capability messages.
- [ ] Safety gate: blocked destructive commands are rejected with deterministic error text.
- [ ] UX gate: command output, heartbeat events, and errors are visible in TUI without hidden side effects.
- [ ] Recovery gate: gateway/service restart restores proactive loop and sandbox correctly.
- [ ] Upgrade gate: no workspace data loss across version upgrade.

## Suggested execution order

1. Finish all P0 items.
2. Add `doctor` and onboarding.
3. Add permissioned multi-agent modes (`build`/`plan`).
4. Ship first stable release tag.
5. Iterate on P1 and P2.
