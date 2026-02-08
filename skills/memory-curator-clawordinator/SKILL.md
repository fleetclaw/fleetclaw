---
name: memory-curator-clawordinator
description: Curate MEMORY.md for Clawordinator — fleet composition, pending actions, and strategic context
metadata: {"openclaw":{"requires":{"bins":["redis-cli"],"env":["REDIS_URL"]}}}
---

# Memory Curator (Clawordinator)

_Clawordinator's memory is lean. It knows what the fleet looks like, what actions are pending, and what decisions need attention. Everything else is in Redis._

## Trigger

- **Session end** — After each interaction (with managers, safety reps, owners), record actions taken
- **Heartbeat** — Every 4-8 hours, refresh escalation queue and directive status

## Input

- **MEMORY.md:** Current contents (read before updating)
- **Redis keys:**
  - `fleet:index:active` — active asset IDs
  - `fleet:index:idle` — idle asset IDs
  - `fleet:index:type:{ASSET_TYPE}` — asset IDs by type
  - `fleet:escalations` — escalation stream from Clawvisor
  - `fleet:directives` — directive stream (to check acknowledgment status)

## Behavior

Clawordinator is the command layer. It's mostly reactive — it acts when a manager gives a command or Clawvisor escalates something. Its memory reflects pending work and fleet structure, not operational details.

### Structure

Maintain these sections in MEMORY.md. Do not add new top-level sections.

```
# MEMORY.md

## Fleet Composition
- Active: {count} assets ({breakdown by type}: {n} excavators, {n} haul trucks, ...)
- Idle: {count} assets ({list IDs if <10, otherwise just count})
- Decommissioned recently: {any in last 30 days}

## Pending Escalations
- From Clawvisor: {description}, received {date}, severity {level}
- (Only unresolved escalations. Remove once a decision is made.)

## Pending Directives
- "{directive text}" — issued {date} by {person}, scope: {all/type/specific}
  Status: {acknowledged by X of Y assets / pending}
- (Only active directives. Remove expired or fully acknowledged ones.)

## Recent Actions
- {date}: Onboarded {ASSET_ID} ({type}, serial {SERIAL})
- {date}: Decommissioned {ASSET_ID} (reason: {reason})
- {date}: Idled {ASSET_ID} / Woke {ASSET_ID}
- {date}: Deployed skill {skill_name} to {scope}
- (Last 10 actions. Provides context for follow-up questions.)

## Skill Deployment State
- Asset agents: {list of mounted skills}
- Clawvisor: {list of mounted skills}
- Clawordinator: {list of mounted skills}
- Recent changes: {any skill additions/removals in last 30 days}
```

### On session end

After any interaction with a manager, safety rep, or owner:

1. If an asset was onboarded, decommissioned, idled, or woken: update "Fleet Composition" and add to "Recent Actions."
2. If a directive was issued: add to "Pending Directives."
3. If an escalation was resolved (decision made): remove from "Pending Escalations" and add the decision to "Recent Actions."
4. If skills were deployed or removed: update "Skill Deployment State" and add to "Recent Actions."

Record decisions, not discussions:
- ❌ "Owner asked about KOT80 maintenance costs and I showed the analysis and he decided to ground it"
- ✅ "KOT80: Owner decision to ground for workshop evaluation (Feb 8). Lifecycle updated to maintenance."

### On heartbeat

Every 4-8 hours:

1. Check `fleet:escalations` for new entries from Clawvisor. Add any unresolved ones to "Pending Escalations."
2. Check `fleet:directives` for directive acknowledgment progress. Update status in "Pending Directives." Remove fully acknowledged or expired directives.
3. Verify "Fleet Composition" counts against index SETs (`fleet:index:active`, `fleet:index:idle`). Update if they've drifted.
4. Prune if approaching character limit.

### Pruning rules

**Target: under 5,000 characters.** Clawordinator's memory should be the leanest of the three agents.

Prune in this order (least valuable first):

1. "Recent Actions" — reduce from 10 to 5 entries (keep only last 30 days)
2. "Pending Directives" — remove any that are expired or >7 days old and fully acknowledged
3. "Fleet Composition" — compress type breakdown if fleet is large (e.g., "12 loaders" instead of listing subtypes)
4. "Skill Deployment State" — remove "Recent changes" detail, keep only current state

Never prune:
- "Pending Escalations" — these need decisions
- Active directives that haven't been fully acknowledged
- "Fleet Composition" counts — Clawordinator must always know fleet size

### Fleet composition detail level

For fleets under 30 assets: list idle/decommissioned assets by ID.
For fleets 30-100 assets: list by type with counts.
For fleets over 100 assets: list by category with counts only. Individual asset details live in Redis.

This scales the memory footprint with fleet size rather than letting it grow linearly.

## Output

- **MEMORY.md updates:** Restructured/pruned content following the sections above
- **No Redis writes from this skill.** Other Clawordinator skills (asset-onboarder, fleet-director) handle Redis writes.
- **No messages to user:** Memory curation is silent background work.
