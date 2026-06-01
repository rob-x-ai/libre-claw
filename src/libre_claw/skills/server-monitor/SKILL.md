---
name: server-monitor
description: Template for compact server-site weather, alert, utility outage, and reachability snapshots.
---

# Server Monitor Snapshot

Use this skill when the user asks whether a remote server site may be affected by severe weather, power outages, utility incidents, or network reachability problems.

This bundled skill is a public template. Replace the placeholders with the user's real site details in a user or project skill before relying on it for production monitoring.

## Placeholders to Customize

- Site label: `<SERVER_SITE_LABEL>`
- Street/location label: `<SERVER_SITE_ADDRESS_OR_DESCRIPTION>`
- Coordinates: `<LATITUDE>,<LONGITUDE>`
- Time zone: `<IANA_TIME_ZONE>`
- Utility outage map URL: `<UTILITY_OUTAGE_MAP_URL>`
- Optional TCP checks: `<HOST:PORT>`
- Optional status page or health endpoint: `<STATUS_OR_HEALTH_URL>`

## Recommended Sources

- Weather point metadata: `https://api.weather.gov/points/<LATITUDE>,<LONGITUDE>`
- Active alerts for the exact point: `https://api.weather.gov/alerts/active?point=<LATITUDE>,<LONGITUDE>`
- Current observation: use the `observationStations` URL from the NWS points response, then fetch the nearest station's latest observation.
- Hourly forecast: use the `forecastHourly` URL from the NWS points response only as context or fallback.
- Utility outage map: use `<UTILITY_OUTAGE_MAP_URL>` if it exposes a stable public API. If it only exposes a browser map or protected map tiles, report that limitation instead of inventing outage counts.
- Server reachability: check explicit host/port or health endpoints provided by the user.

## Procedure

1. Resolve the configured coordinates through the NWS points endpoint.
2. Fetch the nearest current observation and active alerts.
3. Fetch the utility outage-map status or public outage summary if available.
4. Run any explicit server reachability checks the user provided.
5. Return a compact snapshot. Do not include a 7-day forecast unless requested.

## Output Style

Use this shape:

```text
Server Monitor — <SERVER_SITE_LABEL>
<SERVER_SITE_ADDRESS_OR_DESCRIPTION> · Updated: <LOCAL_TIME> · Station: <STATION_ID>

Current: <CONDITION> · <TEMP_C>C (<TEMP_F>F)
Wind: <WIND> · Humidity: <HUMIDITY>

Alerts:
- <SEVERITY>: <ALERT_NAME> until <LOCAL_EXPIRATION>

Utility: <PUBLIC_OUTAGE_STATUS_OR_LIMITATION>
Grid Risk: <LOW|ELEVATED|HIGH> — <ONE_REASON>
Storm Watch: <None|Active>

Server Checks:
- <HOST:PORT>: <UP|DOWN> (<DETAIL>)
```

## Risk Rubric

- `HIGH`: tornado warning/watch, severe thunderstorm warning/watch, destructive wind, flash flood warning, confirmed outage affecting the site, or server unreachable during hazardous weather.
- `ELEVATED`: weather advisory/watch that can plausibly affect power or access, utility map degraded/unavailable during storms, or server reachability failure without severe weather confirmation.
- `LOW`: no active severe local alert, utility source reachable, and server checks pass.

## Pitfalls

- Do not scrape a rendered utility map in a way that hangs the agent. Prefer documented/public JSON or a short best-effort probe with a timeout.
- Do not claim exact outage counts unless the utility source returns them.
- Do not use stale coordinates from memory if the user provides a newer site location.
- Do not bury the answer under tool logs. Lead with risk and current state.

## Verification

- Verify timestamps are in the site time zone.
- Verify alerts are for the exact point or official zone containing the point.
- Verify any server reachability result names the target checked.
- If a source fails, say which source failed and summarize the remaining sources.
