---
name: fleet-analytics
description: Answer fleet-wide analytical questions by aggregating data from outbox files and state
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Fleet Analytics

_Aggregate fleet data to answer leadership's analytical questions about fuel, compliance, maintenance, utilization, and trends._

## Trigger

- **Message** — Leadership asks an analytical question (e.g., "which machines burn the most fuel?", "compliance rate this week?", "how many hours has EX-001 done this month?", "show me maintenance trends")

## Input

- **User messages:** Analytical questions from managers, safety reps, or owners
- **fleet.md:** Active asset list (fleet composition for fleet-wide aggregation)
- **Asset AGENTS.md (State):** Per-asset current state (last fuel, meter, pre-op timestamps)
- **Asset outbox files:** Per-asset outbox/ directories containing:
  - Fuel entries (type: fuel) — consumption analysis
  - Meter entries (type: meter) — utilization analysis
  - Pre-op entries (type: preop) — compliance analysis
  - Issue entries (type: issue) — trend analysis
- **Clawvisor outbox files:** Clawvisor's outbox/ entries of type `maintenance` — maintenance cost and frequency analysis
- **MEMORY.md:** Fleet Composition for context on fleet size

## Behavior

### Recognizing analytical questions

Leadership asks questions like "cost per ton this month", "which machines burn the most fuel", "compliance trend over last 30 days", "what's our average utilization", "how often does EX-001 need repairs." These are all fleet-analytics territory.

If the question is about a specific asset's current status (not a trend or comparison), that is more of a fleet-status concern on Clawvisor. But if Clawordinator is asked directly, answer it — do not redirect.

### Fuel consumption analysis

Read fuel entries from asset outbox/ directories across the requested scope (fleet-wide, by equipment category, or specific assets). Filter by timestamp in filename to match the requested period. Calculate:
- Total fuel consumed over the requested period
- Per-asset consumption
- Average burn rate by asset or by equipment category (group by asset ID prefix)
- Outliers — assets consuming significantly more or less than the average for similar equipment (group by asset ID prefix)

Present comparisons in context. "EX-001 burned 18% more fuel than the fleet average for excavators this month" is more useful than a raw number.

### Compliance analysis

Read `## State` sections in AGENTS.md files across active assets (from fleet.md). Check last_preop_ts, last_fuel_ts, and last_meter_ts fields. Calculate:
- Percentage of assets with a pre-op in the last 24 hours
- Percentage of assets with a fuel log in the last 24 hours
- Percentage of assets with a meter reading in the last 7 days
- Assets that are consistently non-compliant (multiple missed logs)

Compliance is about operator logging behavior, not machine performance. Frame it that way.

### Maintenance analysis

Read Clawvisor's outbox/ for maintenance entries (type: maintenance) across assets. Identify:
- Frequently repaired assets (multiple maintenance events in a short period)
- Common component failures across the fleet
- Average downtime per maintenance event (if duration_h is available)
- Assets that are still marked "still_down" or "restricted"

### Utilization analysis

Use meter entries from asset outbox/ directories to calculate operating hours per day (or per week) by asset or type. Compare against fleet averages. Identify underutilized assets that might be candidates for idling, or overworked assets that might need scheduling relief.

### Issue trends

Read issue entries from asset outbox/ directories to identify:
- Recurring issue categories (hydraulic, electrical, structural)
- Assets with the most reported issues
- Whether reported issues are getting resolved (cross-reference with Clawvisor's maintenance entries)

### Presenting results

Keep the response clear and structured. Use comparisons and context, not just numbers. Leadership wants to make decisions, not read a spreadsheet.

Note data limitations honestly:
- FleetClaw tracks what operators log, not absolute ground truth. If an operator skips fuel logging, the data has gaps.
- Outbox files may be archived or deleted after a retention period. For long-term historical analysis, note when available data does not cover the requested time range.
- Burn rates and utilization are only as accurate as the input data. Estimated entries or missed readings affect the calculations.

If the data is insufficient to answer the question, say so directly rather than guessing.

## Output

- **No outbox writes.** This skill is read-only.
- **No MEMORY.md changes.** Analytics queries are not recorded as actions.
- **Messages to user:** Analytical results with context, comparisons, and honest data quality notes.
