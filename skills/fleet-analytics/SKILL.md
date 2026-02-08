---
name: fleet-analytics
description: Answer fleet-wide analytical questions by aggregating data from Redis streams and state
metadata: {"openclaw":{"requires":{"bins":["redis-cli"],"env":["REDIS_URL"]}}}
---

# Fleet Analytics

_Aggregate fleet data from Redis to answer leadership's analytical questions about fuel, compliance, maintenance, utilization, and trends._

## Trigger

- **Message** — Leadership asks an analytical question (e.g., "which machines burn the most fuel?", "compliance rate this week?", "how many hours has EX-001 done this month?", "show me maintenance trends")

## Input

- **User messages:** Analytical questions from managers, safety reps, or owners
- **Redis keys:**
  - `fleet:index:active` — active asset IDs (for fleet-wide aggregation)
  - `fleet:index:type:{ASSET_TYPE}` — asset IDs by type (for type-level comparisons)
  - `fleet:asset:{ID}:state` — current state per asset (last fuel, meter, pre-op timestamps)
  - `fleet:asset:{ID}:fuel` — fuel log streams (consumption analysis)
  - `fleet:asset:{ID}:meter` — meter reading streams (utilization analysis)
  - `fleet:asset:{ID}:preop` — pre-op streams (compliance analysis)
  - `fleet:asset:{ID}:issues` — issue streams (trend analysis)
  - `fleet:asset:{ID}:maintenance` — maintenance streams (cost and frequency analysis)
- **MEMORY.md:** Fleet Composition for context on fleet size and type breakdown

## Behavior

### Recognizing analytical questions

Leadership asks questions like "cost per ton this month", "which machines burn the most fuel", "compliance trend over last 30 days", "what's our average utilization", "how often does EX-001 need repairs." These are all fleet-analytics territory.

If the question is about a specific asset's current status (not a trend or comparison), that is more of a fleet-status concern on Clawvisor. But if Clawordinator is asked directly, answer it — do not redirect.

### Fuel consumption analysis

Read fuel streams across the requested scope (fleet-wide, by type, or specific assets). Calculate:
- Total fuel consumed over the requested period
- Per-asset consumption
- Average burn rate by asset or by type
- Outliers — assets consuming significantly more or less than the average for their type

Present comparisons in context. "EX-001 burned 18% more fuel than the fleet average for excavators this month" is more useful than a raw number.

### Compliance analysis

Read state HASHes across active assets. Check last_preop_ts, last_fuel_ts, and last_meter_ts fields. Calculate:
- Percentage of assets with a pre-op in the last 24 hours
- Percentage of assets with a fuel log in the last 24 hours
- Percentage of assets with a meter reading in the last 7 days
- Assets that are consistently non-compliant (multiple missed logs)

Compliance is about operator logging behavior, not machine performance. Frame it that way.

### Maintenance analysis

Read maintenance streams across assets. Identify:
- Frequently repaired assets (multiple maintenance events in a short period)
- Common component failures across the fleet
- Average downtime per maintenance event (if duration_h is available)
- Assets that are still marked "still_down" or "restricted"

### Utilization analysis

Use meter reading streams to calculate operating hours per day (or per week) by asset or type. Compare against fleet averages. Identify underutilized assets that might be candidates for idling, or overworked assets that might need scheduling relief.

### Issue trends

Read issue streams to identify:
- Recurring issue categories (hydraulic, electrical, structural)
- Assets with the most reported issues
- Whether reported issues are getting resolved (cross-reference with maintenance stream)

### Presenting results

Keep the response clear and structured. Use comparisons and context, not just numbers. Leadership wants to make decisions, not read a spreadsheet.

Note data limitations honestly:
- FleetClaw tracks what operators log, not absolute ground truth. If an operator skips fuel logging, the data has gaps.
- Redis streams have MAXLEN limits. Older data may have been trimmed. For long-term historical analysis, note when the available data does not cover the requested time range.
- Burn rates and utilization are only as accurate as the input data. Estimated entries or missed readings affect the calculations.

If the data is insufficient to answer the question, say so directly rather than guessing.

## Output

- **No Redis writes.** This skill is read-only.
- **No MEMORY.md changes.** Analytics queries are not recorded as actions.
- **Messages to user:** Analytical results with context, comparisons, and honest data quality notes.
