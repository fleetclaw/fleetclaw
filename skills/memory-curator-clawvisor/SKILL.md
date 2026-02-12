---
name: memory-curator-clawvisor
description: Curate MEMORY.md for Clawvisor — fleet-wide context as an exception report, not an inventory
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Memory Curator (Clawvisor)

_Clawvisor's MEMORY.md is an exception report, not an inventory. Only problems and patterns make it into memory. Everything normal lives in asset outbox files and AGENTS.md._

## Trigger

- **Session end** — After each interaction (with mechanics, foremen, supervisors), distill what happened
- **Heartbeat** — Every 2 hours, refresh from fleet data (new anomalies, escalation updates, compliance changes)

## Input

- **MEMORY.md:** Current contents (read before updating)
- **fleet.md:** Current fleet composition (active, idle, decommissioned asset lists)
- **Asset AGENTS.md (State):** Per-asset operational state (compliance timestamps, operator, status)
- **Asset outbox files:** Per-asset outbox/ directories for recent activity data
- **Clawvisor outbox files:** Clawvisor's own outbox/ entries — type `alert` (recent anomaly alerts), type `escalation` (escalation records), type `maintenance` (recent maintenance events)
- **Clawvisor inbox files:** Incoming messages (escalation resolutions from Clawordinator)

## Behavior

Clawvisor oversees the entire fleet. With 64+ assets, MEMORY.md cannot hold per-asset details for every machine. Instead, it holds:

- **Fleet-level summaries** — the big picture in 2-3 sentences
- **Assets needing attention** — only machines with active problems
- **Compliance trends** — improving or declining, not raw numbers
- **Active escalations** — the 2-3 currently open, with context

If a mechanic asks "what's going on with KOE57?" and KOE57 is healthy, Clawvisor won't find it in MEMORY.md — and that's correct. It reads the `## State` section in KOE57's AGENTS.md and its outbox files. MEMORY.md only contains assets that are exceptional.

### Structure

Maintain these sections in MEMORY.md. Do not add new top-level sections.

```
# MEMORY.md

## Fleet Health
- {2-3 sentence summary: how many active, how many down/in maintenance,
  overall compliance trend, any fleet-wide concerns}
- Fleet size: {count} active, {count} idle, {count} in maintenance

## Needs Attention
- {ASSET_ID}: {what's wrong, since when, who's been notified}
- {ASSET_ID}: {what's wrong, since when, who's been notified}
- (Only assets with active flags — anomalies, unresolved issues,
  overdue maintenance, compliance failures)

## Active Escalations
- Escalation #{id}: {asset_id} — {description}, assigned to {person},
  open since {date}, severity {level}
- (Only currently open escalations. Remove resolved ones.)

## Compliance Trends
- Pre-op: {trend} ({percentage this week vs last week})
- Fuel logs: {trend}
- Meter readings: {trend}
- Problem areas: {specific operators or assets with low compliance}

## Recent Alerts Sent
- {date}: {alert type} for {asset_id} sent to {person}
- (Last 10 alerts only — prevents re-alerting for the same issue)

## Mechanic Activity
- {date}: {mechanic} logged {action} on {asset_id}
- (Last 5 maintenance logs — provides context for follow-up questions)
```

### On session end

After any interaction with a mechanic, foreman, or supervisor:

1. If a mechanic logged maintenance, add it to "Mechanic Activity" and check "Needs Attention" — if the maintenance resolves an open issue, remove that asset from the section.
2. If a supervisor asked about compliance and you provided numbers, update "Compliance Trends" with the current state.
3. If an escalation was resolved during the conversation, remove it from "Active Escalations."
4. Update "Fleet Health" summary if anything materially changed.

Do not record the conversation. Record the outcome:
- Bad: "Supervisor Mike asked about pre-op compliance and I told him it was 82% fleet-wide and he said that was concerning"
- Good: "Pre-op compliance: 82% fleet-wide (Feb 8). Supervisor flagged as concern."

### On heartbeat

Every 2 hours:

1. Read the Active section of fleet.md to confirm fleet size. Update "Fleet Health" if changed.
2. Scan active assets for compliance gaps:
   - For each asset listed as Active in fleet.md, read the `## State` section in the asset's AGENTS.md for last_fuel_ts, last_preop_ts, last_meter_ts, last_seen
   - Flag assets with stale data (no fuel log >24h, no pre-op this shift, no meter reading >7 days, no activity >48h)
   - Add newly flagged assets to "Needs Attention." Remove assets that are no longer flagged.
3. Check Clawvisor's outbox/ for recent escalation files (type: escalation) since last heartbeat. Add to "Active Escalations."
4. Check Clawvisor's outbox/ for recent alert files (type: alert). Add to "Recent Alerts Sent."
5. Check Clawvisor's inbox/ for escalation resolution messages from Clawordinator. Remove resolved escalations from "Active Escalations."
6. Prune if approaching character limit.

### Pruning rules

**Target: under 8,000 characters. Hard ceiling: 15,000 characters** (leaves room for OpenClaw overhead within the 15K bootstrap limit).

Prune in this order (least valuable first):

1. "Recent Alerts Sent" — reduce from 10 to 5 entries
2. "Mechanic Activity" — reduce from 5 to 3 entries
3. "Compliance Trends" — compress to single-line summaries (remove week-over-week detail)
4. "Needs Attention" — remove assets where the flag is informational (>7 days old, no escalation). Keep warnings and criticals.
5. "Active Escalations" — archive resolved escalations that somehow weren't cleaned up

Never prune:
- "Fleet Health" summary — always needed for any conversation
- Active escalations with severity "critical"
- Assets in "Needs Attention" with unresolved safety concerns

### Scaling note

The "Needs Attention" section is the primary scaling risk. In a well-run fleet, only 5-10% of assets need attention at any time (3-6 assets out of 64). In a poorly-run fleet or during a bad week, this could spike.

If "Needs Attention" grows beyond 15 assets:
- Group by issue type instead of listing individually: "Fuel compliance: KOT28, KOT39, KOT44, KOT80 (all >24h without log)"
- This compresses 4 entries into 1 line

If the fleet grows beyond ~150 assets, consider splitting Clawvisor into zone-based instances (e.g., Clawvisor-North, Clawvisor-South), each with its own MEMORY.md tracking a subset of the fleet.

## Output

- **MEMORY.md updates:** Restructured/pruned content following the sections above
- **No outbox writes from this skill.** Other Clawvisor skills (anomaly-detector, escalation-handler) handle outbox writes.
- **No messages to user:** Memory curation is silent background work.
