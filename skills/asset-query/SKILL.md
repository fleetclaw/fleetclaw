---
name: asset-query
description: Answer detailed questions about any specific asset — fuel history, issues, maintenance, readings, and patterns
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Asset Query

_Answer detailed questions about any specific asset — fuel history, issues, maintenance, readings, and patterns._

## Trigger

- **Message** — User asks specific questions about a particular asset ("when was EX-001 last fueled?", "what issues does KOT28 have?", "show me EX-003's maintenance history", "how much fuel has CAE52 burned this week?")

## Input

- **User messages:** Asset-specific questions from mechanics, foremen, supervisors, managers
- **fleet.md:** Fleet composition — Active, Idle, and Decommissioned asset lists (to verify asset exists and check lifecycle state)
- **Asset AGENTS.md (State):** The target asset's `## State` section (all fields: status, operator, last_seen, last_fuel_ts, last_preop_ts, last_meter_ts, etc.)
- **Asset outbox files:** The target asset's outbox/ directory containing entries of all types:
  - Fuel entries (type: fuel) — fuel log history
  - Meter entries (type: meter) — meter reading history
  - Pre-op entries (type: preop) — pre-op inspection history
  - Issue entries (type: issue) — reported issues
- **Clawvisor outbox files:** Clawvisor's own outbox/ entries related to the target asset:
  - Maintenance entries (type: maintenance) with matching asset field
  - Alert entries (type: alert) with matching asset field

## Behavior

Asset-query is the "drill down" skill. Where fleet-status gives the overview, asset-query gives the detail. When someone wants to know the specifics about a particular machine, this skill reads the asset's files directly and presents the answer.

### Identifying the asset

Parse the asset ID from the user's question. Asset IDs follow patterns like EX-001, KOT28, CAE52 — a short prefix and a number. If the user uses a nickname or abbreviation ("the big Cat", "number 28"), try to match it against known assets from fleet.md. If ambiguous, ask once.

If the user asks about an asset that doesn't appear in the Active or Idle sections of fleet.md, check the Decommissioned section. If the asset exists but is decommissioned, say so. If the asset doesn't appear in fleet.md at all, say it clearly: "I don't have a record of an asset with that ID."

### Answering queries

Match the user's question to the appropriate data source and query accordingly:

**Last fueled / fuel history.** Read the most recent fuel files from the asset's outbox/ (type: fuel, sorted by timestamp in filename). "When was EX-001 last fueled?" needs the 1 most recent file. "Last 5 fuel logs for EX-001" needs the 5 most recent. Include the amount, burn rate, and timestamp for each entry.

**Current state.** Read the `## State` section in the asset's AGENTS.md for the relevant fields. "Is EX-001 active?" needs just status. "Who's operating KOT28?" needs operator and last_seen.

**Issues.** Read issue files from the asset's outbox/ (type: issue, sorted by timestamp). "What issues does KOT28 have?" returns recent issues with their description, category, severity, and whether the machine was still operational. If the user asks about open/unresolved issues, cross-reference against Clawvisor's outbox/ for maintenance entries (type: maintenance) matching the same asset — issues with matching maintenance entries after them are likely resolved.

**Maintenance history.** Read Clawvisor's outbox/ for maintenance entries (type: maintenance) where the asset field matches the target asset. Show action, component, mechanic, and outcome.

**Meter readings.** Read the most recent meter files from the asset's outbox/ (type: meter). Include the value, delta from previous, and when it was recorded.

**Pre-op history.** Read pre-op files from the asset's outbox/ (type: preop). Show results, any flagged items, and who completed each one.

**Anomaly alerts.** Read Clawvisor's outbox/ for alert entries (type: alert) where the asset field matches. Show alert_type, severity, description, and when it was generated.

**Patterns and aggregations.** For questions like "how much fuel has EX-001 burned this week?" or "how many issues has KOT28 had this month?", read outbox files filtered by timestamp in filename to match the requested period, then aggregate the results. Sum fuel liters, count issues by category, calculate average burn rate over the period.

### Handling time-based queries

When the user specifies a time period ("last week", "this month", "since January"), filter outbox files by the timestamp in their filenames. For "last N entries" style queries, sort by timestamp and take the N most recent files.

### Presentation

Present data clearly and concisely. Use the format that fits the data:

- Single data point: one sentence. "EX-001 was last fueled 6 hours ago — 400L, burn rate 13.2 L/hr."
- Short list (under 5 items): bullet points with key details.
- Longer history: summarize with highlights. "KOT28 has had 12 fuel logs this month, averaging 380L per fill at 11.8 L/hr. Burn rate has been steady."

If the data tells a story (rising burn rate, recurring issue category, declining pre-op results), mention it. The user asked about one thing, but relevant context helps them make decisions.

## Output

- **Messages to user:** Asset-specific data, formatted for the type of query asked.
- **No outbox writes.** Asset-query is read-only.
- **No MEMORY.md changes.** Asset-query surfaces data on demand — it doesn't persist anything. The memory-curator handles what stays in MEMORY.md.
