# Vercel Skills Integration

Libre Claw supports AgentSkills-style `SKILL.md` files and can optionally
interoperate with the open skills ecosystem from
[`vercel-labs/skills`](https://github.com/vercel-labs/skills).

The integration has two parts:

- Local skill loading from bundled, user, project, and cached external
  `SKILL.md` files.
- A read-only `skills_search` tool that can run the configured Skills CLI search
  command when external discovery is enabled.

External discovery is opt-in because it can contact GitHub and npm. Normal local
skills keep working with no network access.

## Enable External Discovery

Edit `~/.libre-claw/config.toml`:

```toml
[skills]
enabled = true
external_discovery_enabled = true
external_auto_refresh = true
external_cache_dir = "~/.libre-claw/skills/catalogs"
vercel_source_enabled = true
vercel_repo_url = "https://github.com/vercel-labs/skills.git"
vercel_ref = "main"
cli_enabled = true
cli_command = "npx -y skills@latest"
cli_timeout = 45
```

Then refresh the catalogue:

```text
/skills sync
```

Telegram also supports:

```text
/skills status
/skills list
/skills sync
```

## How It Works

Libre Claw loads skills from these sources, in increasing override priority:

```text
src/libre_claw/skills/
~/.libre-claw/skills/catalogs/vercel-labs-skills/
~/.libre-claw/skills/
<project>/.libre-claw/skills/
```

The Vercel source is cached locally. When `external_auto_refresh` is enabled,
Libre Claw refreshes the cache at most once per `external_refresh_seconds`.
If GitHub is unavailable, the last cached copy remains usable.

Relevant skills are injected before each turn. Project skills override user,
external, and bundled skills with the same name.

## Agent Search Behavior

When external discovery is enabled, the agent sees a `skills_search` tool.
It should use this tool when:

- The task is specialized and no relevant local skill was injected.
- The user asks whether a skill exists.
- The user asks how to extend Libre Claw for a repeatable workflow.

The tool runs the configured command without shell interpolation:

```text
npx -y skills@latest find "<query>"
```

It is read-only. Installing or editing skills remains a user-visible action via
`/skills add`, manual file edits, or a future explicit installer command.

## Create A Local Skill

Use AgentSkills-compatible Markdown:

```markdown
---
name: server-monitor
description: Use for compact server weather, power, and outage snapshots.
---

# Server Monitor

## When to Use

- The user asks whether a server location is at risk.

## Procedure

1. Fetch weather and alert data.
2. Fetch power/outage data.
3. Return a compact status snapshot.

## Verification

- The final answer cites sources and avoids raw scratch output.
```

Save it as either:

```text
~/.libre-claw/skills/server-monitor/SKILL.md
<project>/.libre-claw/skills/server-monitor/SKILL.md
```

## Tests

The integration is tested without network access:

- Config defaults and opt-in flags.
- Cached external `SKILL.md` discovery.
- External sync refusal when disabled.
- `skills_search` command construction with a fake subprocess.
- TUI `/skills sync` parsing.
