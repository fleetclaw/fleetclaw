---
name: asset-query
description: Answer detailed questions about any specific asset — fuel history, issues, maintenance, readings, and patterns
metadata: {"openclaw":{"requires":{"bins":["redis-cli"],"env":["REDIS_URL"]}}}
---

# Asset Query

_Answer detailed questions about any specific asset — fuel history, issues, maintenance, readings, and patterns._

## Trigger

- **Message** — User asks specific questions about a particular asset ("when was EX-001 last fueled?", "what issues does KOT28 have?", "show me EX-003's maintenance history", "how much fuel has CAE52 burned this week?")

## Input

- **User messages:** Asset-specific questions from mechanics, foremen, supervisors, managers
- **Redis keys:**
  - `fleet:asset:{ID}:state` — HASH (all fields available via HMGET)
  - `fleet:asset:{ID}:fuel` — STREAM (fuel log history)
  - `fleet:asset:{ID}:meter` — STREAM (meter reading history)
  - `fleet:asset:{ID}:preop` — STREAM (pre-op inspection history)
  - `fleet:asset:{ID}:issues` — STREAM (reported issues)
  - `fleet:asset:{ID}:maintenance` — STREAM (maintenance history)
  - `fleet:asset:{ID}:alerts` — STREAM (anomaly alerts for this asset)
  - `fleet:asset:{ID}:lifecycle` — HASH (active/idle/decommissioned state)
  - `fleet:index:active` — SET (to verify asset exists and is active)
  - `fleet:index:idle` — SET (to check if asset is idle)

## Behavior

Asset-query is the "drill down" skill. Where fleet-status gives the overview, asset-query gives the detail. When someone wants to know the specifics about a particular machine, this skill queries Redis directly and presents the answer.

### Identifying the asset

Parse the asset ID from the user's question. Asset IDs follow patterns like EX-001, KOT28, CAE52 — a short prefix and a number. If the user uses a nickname or abbreviation ("the big Cat", "number 28"), try to match it against known assets from the active and idle indexes. If ambiguous, ask once.

If the user asks about an asset that doesn't appear in the active or idle indexes, check the lifecycle HASH. If the asset exists but is decommissioned, say so. If the asset doesn't exist in any index, say it clearly: "I don't have a record of an asset with that ID."

### Answering queries

Match the user's question to the appropriate data source and query accordingly:

**Last fueled / fuel history.** Use XREVRANGE on the fuel stream with COUNT to get the most recent entries. "When was EX-001 last fueled?" needs COUNT 1. "Last 5 fuel logs for EX-001" needs COUNT 5. Include the amount, burn rate, and timestamp for each entry.

**Current state.** Use HMGET on the state HASH for the relevant fields. "Is EX-001 active?" needs just status. "Who's operating KOT28?" needs operator and last_seen.

**Issues.** Use XREVRANGE on the issues stream. "What issues does KOT28 have?" returns recent issues with their description, category, severity, and whether the machine was still operational. If the user asks about open/unresolved issues, cross-reference against the maintenance stream — issues with matching maintenance entries after them are likely resolved.

**Maintenance history.** Use XREVRANGE on the maintenance stream. "Show me EX-003's maintenance history" returns recent maintenance entries with action, component, mechanic, and outcome.

**Meter readings.** Use XREVRANGE on the meter stream. Include the value, delta from previous, and when it was recorded.

**Pre-op history.** Use XREVRANGE on the preop stream. Show results, any flagged items, and who completed each one.

**Anomaly alerts.** Use XREVRANGE on the alerts stream. Show type, severity, description, and when it was generated.

**Patterns and aggregations.** For questions like "how much fuel has EX-001 burned this week?" or "how many issues has KOT28 had this month?", use XRANGE with a calculated start timestamp and aggregate the results. Sum fuel liters, count issues by category, calculate average burn rate over the period.

### Handling time-based queries

When the user specifies a time period ("last week", "this month", "since January"), convert it to a Unix timestamp in milliseconds for XRANGE. Use XRANGE with the start timestamp and "+" for the end. For "last N entries" style queries, use XREVRANGE with COUNT.

### Presentation

Present data clearly and concisely. Use the format that fits the data:

- Single data point: one sentence. "EX-001 was last fueled 6 hours ago — 400L, burn rate 13.2 L/hr."
- Short list (under 5 items): bullet points with key details.
- Longer history: summarize with highlights. "KOT28 has had 12 fuel logs this month, averaging 380L per fill at 11.8 L/hr. Burn rate has been steady."

If the data tells a story (rising burn rate, recurring issue category, declining pre-op results), mention it. The user asked about one thing, but relevant context helps them make decisions.

## Output

- **Messages to user:** Asset-specific data, formatted for the type of query asked.
- **No Redis writes.** Asset-query is read-only.
- **No MEMORY.md changes.** Asset-query surfaces data on demand — it doesn't persist anything. The memory-curator handles what stays in MEMORY.md.
