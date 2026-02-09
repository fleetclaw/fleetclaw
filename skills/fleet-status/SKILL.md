---
name: fleet-status
description: Answer questions about current fleet state — what's running, what's down, how many machines are active
metadata: {"openclaw":{"requires":{"bins":["redis-cli"],"env":["REDIS_URL"]}}}
---

# Fleet Status

_Answer questions about current fleet state — what's running, what's down, how many machines are active._

## Trigger

- **Message** — User asks about fleet state ("what's running?", "status of EX-001", "how many machines are up?", "fleet overview", "anything down?")

## Input

- **User messages:** Questions about fleet state, individual asset status, or fleet-wide counts
- **Redis keys:**
  - `fleet:index:active` — SET of currently active asset IDs
  - `fleet:index:idle` — SET of currently idle asset IDs
  - `fleet:asset:{ID}:state` — HASH (HMGET specific fields: status, operator, last_seen, last_fuel_ts, last_preop_ts)
  - `fleet:asset:{ID}:lifecycle` — HASH (state, since, changed_by)
- **MEMORY.md:** Fleet Health section for quick overview without querying every asset

## Behavior

This is Clawvisor's "what's the fleet look like right now?" skill. It answers status questions at two levels: fleet-wide and per-asset.

### Fleet-wide queries

When someone asks "what's running?" or "fleet overview" or "how many machines are up?":

1. Start with the Fleet Health summary from MEMORY.md. This gives a fast, high-level answer without hitting Redis for every asset.
2. If the user needs current numbers (or if MEMORY.md seems stale), query Redis indexes:
   - SCARD `fleet:index:active` for active count
   - SCARD `fleet:index:idle` for idle count
3. Present the overview concisely. Group by status first (active, idle, in maintenance, down), then by equipment category (inferred from asset ID prefixes) if the fleet is large enough that grouping helps.
4. If the fleet has more than 20 assets, summarize by category rather than listing every machine individually. "32 active (18 excavators, 8 haul trucks, 6 others), 4 idle, 2 in maintenance."
5. If there are assets in the "Needs Attention" section of MEMORY.md, mention them briefly. "Two machines flagged — EX-003 has an open hydraulic issue, KOT28 hasn't logged fuel in 36 hours."

### Specific asset queries

When someone asks about a particular asset ("status of EX-001", "what's going on with KOT28?"):

1. Read the asset's state HASH using HMGET for the relevant fields: status, operator, last_seen, last_fuel_ts, last_preop_ts, last_meter_ts.
2. Read the asset's lifecycle HASH for active/idle/decommissioned state.
3. Check MEMORY.md "Needs Attention" for any flags on this asset.
4. Present a concise status summary: current state, who's operating it, when it was last active, whether its compliance data is current.
5. If the asset has active flags or issues noted in MEMORY.md, include those. If it's not in MEMORY.md, that means it's healthy — say so.

### Presentation

Keep responses crisp and scannable. Foremen and supervisors are busy — they want the answer, not a report. Use short bullet points for multi-asset responses. Lead with the most important information (anything down or flagged), then the routine stuff.

If someone asks a question this skill can't answer from state data alone — like "what issues does EX-001 have?" or "show me fuel history" — that's asset-query territory. Answer what you can from the state HASH and point to the deeper data if relevant.

## Output

- **Messages to user:** Fleet status information, formatted for clarity.
- **No Redis writes.** Fleet-status is read-only.
- **No MEMORY.md changes.** Fleet-status doesn't update memory — that's the memory-curator's job.
