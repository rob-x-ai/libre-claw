---
name: hacker-news-brief
description: Use for Hacker News, HN, startup, coding, AI, infra, security, open-source, or scheduled HN brief requests.
---

# Hacker News Brief

## When to Use

- Use when the user asks about Hacker News, HN, top stories, new stories, startup news, coding news, AI news, infrastructure news, security news, open-source news, or recurring HN watches.

## Prerequisites

- Prefer `http_request` against the official Hacker News Firebase API:
  - `https://hacker-news.firebaseio.com/v0/topstories.json`
  - `https://hacker-news.firebaseio.com/v0/newstories.json`
  - `https://hacker-news.firebaseio.com/v0/item/<id>.json`
- Do not use a browser unless a linked article needs page inspection.
- Compare against memory or recent runs when available.

## Procedure

1. Fetch `topstories.json` and `newstories.json`.
2. Inspect only the first 30 IDs from each list unless the user asks for a wider scan.
3. Fetch item details only for promising stories.
4. Prefer AI, coding, infrastructure, security, startups, open source, developer tools, and notable tech-business stories.
5. Filter out repeats when memory or recent run records contain prior HN story IDs or links.
6. Final answer only: no process narration, no raw ID arrays, no candidate scratch lists, and no tool logs.

## Output

- Start with `HN Brief`.
- Use at most 8 bullets unless the user asks for more.
- Each bullet should include title, URL, score/comment count when available, and one sharp sentence on why it matters.
- If nothing qualifies, output exactly: `No high-signal HN updates.`
- If the source fails before a usable brief can be produced, give one concise failure sentence and no partial notes.

## Pitfalls

- Do not say "Let me fetch", "Good data", "Now let me", or similar process narration in the final answer.
- Do not paste raw ID arrays, JSON payloads, HTTP logs, or candidate notes.
- Do not send expanded tool activity to Telegram unless the run failed or the user asks for logs.
- Avoid low-signal general-interest stories unless the user asks for a broad HN digest.

## Verification

- The final answer is compact enough for Telegram.
- The final answer contains curated story links, not collection data.
- The final answer has no visible tool logs or intermediate reasoning text.
