# HEARTBEAT.md

Checklist for autonomous heartbeat ticks.
Add tasks here that should run periodically.

## Checks

- [ ] Example: Check service health
- [ ] Example: Sync workspace to git
- [ ] Example: Check for new messages

## Rules

- Continue until no more work is found or the configured proactive limit is reached.
- Report if actionable, otherwise reply NO_REPLY
- If useful, update memory by including a MEMORY_UPDATE: entry in your output
- Update timestamps in heartbeat-state.json after each check
