---
name: web-research
description: Research current, external information on the public web with the Serper-backed web_search tool - market trends, recent launches, prices, standards and news - and report it with URLs and dates. Use only for information that internal documents cannot contain; never for company policies, product manuals or customer data.
---

# Web research

Tool: `web_search(query, kind="search"|"news", time_range=None|"d"|"w"|"m"|"y", num)`.

## When to search
- Current trends, recent product launches, market prices, new standards (e.g. HDMI 2.2), regulation changes.
- Never for internal facts: HR entitlements, manual specifications, customers or tickets belong to other agents.

## How to search
1. Write 1-3 focused queries; add the year for time-sensitive topics ("TV market trends India 2026").
2. Use `kind="news"` with `time_range="m"` for recent developments; `kind="search"` for background.
3. Prefer primary or reputable sources (manufacturers, standards bodies, regulators, major publications).
4. Cross-check a number in at least two sources when possible; otherwise mark it as single-source.

## Reporting
- Every claim gets an evidence entry of kind `web` with `url`, `title` and `date` (if shown).
- Separate facts from opinions or forecasts, and say how recent the information is.
- Snippets can be truncated - do not over-interpret them; state uncertainty in `gaps`.
