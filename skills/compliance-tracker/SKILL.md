---
name: compliance-tracker
description: Track and report on data capture compliance across the fleet — pre-ops, fuel logs, meter readings
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Compliance Tracker

_Track and report on data capture compliance across the fleet — pre-ops, fuel logs, meter readings._

## Trigger

- **Heartbeat** — Every 2 hours, proactively scan the fleet for compliance gaps
- **Message** — User asks about compliance ("who hasn't done pre-ops?", "compliance this week?", "which machines are behind on fuel logs?")

## Input

- **User messages:** Compliance questions from supervisors, foremen, managers
- **fleet.md:** Active asset list (fleet composition)
- **Asset state.md files:** Per-asset compliance timestamps (last_fuel_ts, last_preop_ts, last_meter_ts, last_seen, operator, status)
- **MEMORY.md:** Compliance Trends section (previous percentages and trends for comparison)

## Behavior

Compliance tracking is FleetClaw's core mission. This skill monitors whether operators are actually logging the data they're supposed to — fuel, pre-ops, and meter readings — and surfaces gaps to the people who can act on them.

### On heartbeat

Every 2 hours, scan the fleet for compliance gaps:

1. Read the Active section of fleet.md to get all active asset IDs.
2. For each active asset, read compliance-relevant timestamps from the asset's state.md: last_fuel_ts, last_preop_ts, last_meter_ts, last_seen, operator.
3. Flag assets that are non-compliant against these thresholds:
   - **Pre-op:** No pre-op inspection logged in the last 12 hours for an active asset. This means the current shift likely started without a pre-op.
   - **Fuel:** No fuel log in the last 24 hours for an active asset. Most machines fuel at least once per shift.
   - **Meter:** No meter reading in the last 7 days. Meter readings are less frequent but still expected weekly.
   - **Activity:** No operator interaction at all in the last 48 hours. The machine may be inactive without being marked idle.
4. Calculate compliance percentages for each category. Pre-op compliance is the number of active assets with a pre-op in the last 12 hours, divided by total active assets. Same pattern for fuel and meter.
5. Compare current percentages against the values stored in MEMORY.md Compliance Trends. Note whether each category is improving, declining, or stable compared to the last check.
6. Identify problem areas — specific operators who are consistently non-compliant, or assets with lower compliance rates.
7. Update MEMORY.md Compliance Trends section with the new percentages and trend direction.

### On message

When a supervisor, foreman, or manager asks about compliance:

1. Pull fresh data from asset state.md files, not just MEMORY.md. Compliance questions deserve current numbers.
2. Answer the specific question asked:
   - "Who hasn't done pre-ops?" — List the non-compliant assets with their operators and how long ago their last pre-op was.
   - "Compliance this week?" — Provide percentages for all three categories with trend direction.
   - "How's night shift doing?" — If you can determine which assets are on night shift from recent activity patterns, filter accordingly. If not, explain what data you have and offer fleet-wide numbers.
3. Keep the answer focused. If they ask about pre-ops, lead with pre-ops. Don't dump all three categories unless they ask for a full overview.
4. When listing non-compliant assets, include context: the operator name, when they were last active, and how overdue they are. "EX-003 (Mike) — last pre-op 18 hours ago, active 2 hours ago" tells the supervisor exactly what's happening.

### Thresholds

These thresholds are designed for typical mining operations with 12-hour shifts:

- Pre-op: 12 hours (one per shift expected)
- Fuel: 24 hours (at least once per day expected)
- Meter: 7 days (weekly reading expected)
- Activity: 48 hours (if truly inactive, should be marked idle)

Tier 2 deployments may adjust these thresholds via configuration. For Tier 1, these are hardcoded in the skill instructions.

## Output

- **MEMORY.md updates:** Update Compliance Trends section with current percentages, trend direction, and problem areas. Keep it concise — percentages and trends, not per-asset lists.
- **Messages to user:** Compliance reports when queried, with specific assets and operators named.
- **No outbox writes.** Compliance-tracker is read-only. It observes but doesn't modify fleet data.
