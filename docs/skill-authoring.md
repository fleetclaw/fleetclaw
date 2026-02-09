# FleetClaw Skill Authoring Guide

## What is a skill?

A skill is a markdown file that teaches an OpenClaw agent how to do something. It contains plain English instructions — not code — that the LLM reads and follows. When an agent has multiple skills mounted, it reads all of them and synthesizes the instructions into behavior.

Skills are the primary way FleetClaw agents learn what to do. The agent's identity lives in SOUL.md (just an asset ID and serial number). Everything else — how to log fuel, how to detect anomalies, how to nudge an operator — comes from skills.

## The two contracts in one file

Every skill has two parts:

**YAML frontmatter** (machine-readable) — tells the infrastructure what the skill needs:

```yaml
---
name: fuel-logger
description: Accept fuel log entries from operators and publish to Redis
metadata: {"openclaw":{"requires":{"bins":["redis-cli"],"env":["REDIS_URL"]}}}
---
```

The `requires` block declares system dependencies. `bins` lists command-line tools the skill needs. `env` lists environment variables. OpenClaw checks these at startup and warns if anything is missing.

**Markdown body** (LLM-readable) — teaches the agent the behavior:

```markdown
# Fuel Logger

_Accept casual fuel input from operators, log it, and publish to Redis._

## Trigger
...
## Behavior
...
```

The LLM never sees the frontmatter as instructions. The infrastructure never parses the markdown body as config. Two audiences, one file.

## Skill structure

Every skill follows this structure:

### Trigger

When does the agent activate this skill? Options:

- **Message** — The operator/user says something that matches this skill's domain. The agent recognizes "400L" or "filled up" as fuel-related and activates the fuel-logger skill.
- **Heartbeat** — The agent's periodic polling cycle fires. Used for proactive checks like anomaly detection or nudging.
- **Session start** — The agent wakes up and reviews context. Used for delivering pending information like maintenance acknowledgments.
- **Redis event** — New data appears in a key the agent watches. Used for responding to external changes (e.g., a directive from Clawordinator).

Most skills use 1-2 triggers. A fuel-logger triggers on operator messages. A nudger triggers on heartbeat. A memory-curator triggers on both session end and heartbeat.

### Input

What data does the skill consume? Be specific about Redis key patterns:

```markdown
## Input
- **User messages:** Natural language fuel reports (e.g., "400l", "filled up 400")
- **Redis keys:** `fleet:asset:{ASSET_ID}:fuel` (recent fuel history for burn rate calculation)
- **MEMORY.md:** Last fuel log details, operator fueling patterns
```

This serves two purposes: the LLM knows where to look for data, and a human reader (Tier 2 skill author) can see exactly what data this skill depends on.

### Behavior

The core of the skill. Plain English instructions the agent follows. This section is freeform — structure it however best communicates the behavior. Some patterns that work well:

**Step-by-step for procedural skills:**

```markdown
## Behavior

When an operator reports fuel:

1. Parse the amount from their message. Accept messy input — "400l", "filled 400",
   "put in 400 liters" all mean 400L.
2. If the amount is ambiguous, ask once. If still unclear, log what you can and note
   the ambiguity.
3. Check MEMORY.md for the last fuel log. Calculate burn rate if enough data exists.
4. Write to Redis and update MEMORY.md.
5. Respond with confirmation and burn rate context if available.
```

**Rules-based for monitoring skills:**

```markdown
## Behavior

### What to watch for
- Fuel burn rate >20% above this asset's rolling average
- No fuel log from an active asset for >24 hours
- Meter reading that jumps >500 hours in a single report

### Severity
- Informational: single occurrence, within 30% of normal
- Warning: repeated occurrence or >30% deviation
- Critical: safety-related or >50% deviation
```

**Conversational for interaction skills:**

```markdown
## Behavior

Walk the operator through the pre-op checklist conversationally:

- Don't read the checklist as a numbered form. Ask about systems naturally:
  "How's the machine looking today? Anything off?"
- If they say "all good" — log a pass on all items. Don't make them confirm
  each one individually.
- If they flag something — dig into that specific item. Ask severity and
  whether the machine is safe to operate.
- If they skip the pre-op entirely — don't block them. Note it as incomplete
  and let the nudger handle reminders.
```

Do not use pseudocode or programming constructs. Write instructions the way you'd explain a task to a competent colleague.

### Output

What does the skill produce? Be specific about Redis key patterns and data formats:

```markdown
## Output

- **Redis writes:**
  ```
  XADD fleet:asset:{ASSET_ID}:fuel MAXLEN ~ 1000 * \
    liters {AMOUNT} \
    burn_rate {RATE} \
    source "operator" \
    note "{ANY_NOTES}"

  HSET fleet:asset:{ASSET_ID}:state \
    last_fuel_l {AMOUNT} \
    last_fuel_ts {TIMESTAMP}
  ```
- **MEMORY.md updates:** Update the "Recent Context" section with the new
  fuel log. If burn rate is trending, note the trend.
- **Messages to user:** Confirm the log with context.
  Example: "Logged 400L. You've burned 620L over 47h since last fill — 13.2L/hr, normal range."
```

The Redis commands in Output serve as documentation — they show the exact key patterns and field names this skill writes. Tier 2 authors can read this to understand the data contract.

### Overdue Condition (optional)

If this skill produces data that should arrive on a regular cadence, define when it's "overdue." The nudger skill reads these conditions from all mounted skills and handles reminders.

```markdown
## Overdue Condition

No fuel log within 8 hours of the operator's first message this shift.
```

The convention is: `[What's missing] after [time threshold] since [reference event].`

Only include this section if the nudger should monitor this skill. Skills that are purely reactive (issue-reporter, asset-query) don't need overdue conditions.

## The nudger pattern

The nudger is a standalone skill that coordinates reminders across all other skills. It works through a convention, not a dependency:

1. **Domain skills** (fuel-logger, meter-reader, pre-op) each define an `## Overdue Condition` section describing when their expected data is missing.
2. **The nudger skill** defines the tone, cadence, and rules for reminders: one per missing item per shift, gentle, private, never in groups.
3. **The agent reads both** and synthesizes: "fuel is overdue (from fuel-logger), and I know how to remind (from nudger)."

This means a Tier 2 skill author building `tire-pressure-logger` just adds an `## Overdue Condition` section to their skill, and the nudger automatically picks it up. No coupling, no updates needed. The convention is the API.

## Redis key conventions

Skills that read or write Redis must follow the FleetClaw key schema. See `docs/redis-schema.md` for the full reference.

Summary of patterns:

| Pattern | Type | Purpose |
|---------|------|---------|
| `fleet:asset:{ASSET_ID}:state` | HASH | Current machine state (discrete fields) |
| `fleet:asset:{ASSET_ID}:fuel` | STREAM | Fuel log events |
| `fleet:asset:{ASSET_ID}:meter` | STREAM | Meter reading events |
| `fleet:asset:{ASSET_ID}:preop` | STREAM | Pre-op inspection events |
| `fleet:asset:{ASSET_ID}:issues` | STREAM | Issue report events |
| `fleet:asset:{ASSET_ID}:maintenance` | STREAM | Maintenance events (from Clawvisor) |
| `fleet:asset:{ASSET_ID}:alerts` | STREAM | Anomaly alerts (from Clawvisor) |
| `fleet:asset:{ASSET_ID}:inbox` | STREAM | Messages TO this asset agent |
| `fleet:asset:{ASSET_ID}:lifecycle` | HASH | Active/idle/decommissioned |
| `fleet:directives` | STREAM | Fleet-wide directives (from Clawordinator) |
| `fleet:escalations` | STREAM | Escalation events |
| `fleet:index:active` | SET | Active asset IDs |
| `fleet:index:idle` | SET | Idle asset IDs |

**Key rules:**
- Keys are hierarchical, entity-first: `fleet:asset:{ASSET_ID}:{data_type}`
- State data uses HASH with discrete fields (not JSON blobs)
- Event data uses STREAM with MAXLEN trimming (not TTL expiry)
- Cross-asset lookups use index SETs, not SCAN

**State HASH fields are flat key-value pairs:**

```bash
HSET fleet:asset:EX-001:state \
  status "active" \
  operator "Mike" \
  last_fuel_l "400" \
  last_fuel_ts "1707350400"
```

**Stream entries are flat field-value pairs:**

```bash
XADD fleet:asset:EX-001:fuel MAXLEN ~ 1000 * \
  liters 400 \
  burn_rate 13.2 \
  source "operator"
```

Keep data flat (no nested JSON) for Tier 1 skills. Flat field-value pairs work cleanly with `redis-cli` and are easy to describe in skill instructions.

## MEMORY.md conventions

Skills that update MEMORY.md should follow these rules:

1. **Write curated summaries, not raw data.** MEMORY.md has a 20,000 character bootstrap limit. Write "Last fuel: 400L on Feb 8, burn rate normal" — not a transcript of the conversation.
2. **Respect the memory-curator skill's structure.** Each agent type has a memory-curator skill that defines MEMORY.md's sections and character budget. Your skill should write to the appropriate section, not create new top-level sections.
3. **Prune as you write.** If adding a new fuel log, remove the oldest one from the recent context section. Don't let your skill's data grow unbounded.
4. **Prefer Redis for history.** If someone needs the last 50 fuel logs, that's a Redis query. MEMORY.md holds the last 3-5 for instant context.

## Skill tiers

FleetClaw skills exist in three tiers:

**Tier 1 — Ships with FleetClaw.** Works out of the box. Uses Redis and MEMORY.md only. No external integrations. These skills define the baseline platform experience.

**Tier 2 — Organization-built.** Integrates with external systems via .env credentials (CMMS, telematics, fuel management). FleetClaw provides the skill template and this guide. The organization fills in the integration logic.

**Tier 3 — Community/advanced.** Extends the platform in ways not anticipated by the core team. Voice transcription, predictive analytics, custom dashboards.

When building a Tier 2 or 3 skill:

- Follow the template structure exactly — Trigger, Input, Behavior, Output, Overdue Condition
- Declare all external dependencies in frontmatter (`bins` and `env`)
- Document your Redis key patterns in Input/Output so other skills can discover your data
- If your skill produces data on a regular cadence, add an Overdue Condition
- Reference `docs/redis-schema.md` for existing key patterns before creating new ones

## Skill locations

Skills are mounted at two levels:

```
~/.openclaw/skills/          # Shared skills (all agents on this host)
<workspace>/skills/          # Per-agent skills
```

For FleetClaw:
- **Asset agents:** `fuel-logger`, `meter-reader`, `pre-op`, `issue-reporter`, `nudger`, `memory-curator-asset`
- **Clawvisor:** `fleet-status`, `compliance-tracker`, `maintenance-logger`, `anomaly-detector`, `shift-summary`, `escalation-handler`, `asset-query`, `memory-curator-clawvisor`
- **Clawordinator:** `asset-onboarder`, `asset-lifecycle`, `fleet-director`, `escalation-resolver`, `fleet-analytics`, `fleet-config`, `memory-curator-clawordinator`

No skills are shared across all agent types. Each agent type has its own skill set mounted in its workspace. Skill mounting is managed by Clawordinator via the `fleet-config` skill.

## Example: fuel-logger skill

This is a complete Tier 1 skill showing all conventions:

```markdown
---
name: fuel-logger
description: Accept fuel log entries from operators and publish to Redis
metadata: {"openclaw":{"requires":{"bins":["redis-cli"],"env":["REDIS_URL"]}}}
---

# Fuel Logger

_Accept casual fuel input from operators, log it, and publish to Redis._

## Trigger

- **Message** — Operator mentions fuel, refueling, or sends a number that
  looks like a fuel amount (e.g., "400l", "filled up", "put 400 in")

## Input

- **User messages:** Natural language fuel reports
- **Redis keys:** `fleet:asset:{ASSET_ID}:fuel` (last 5 entries for burn rate)
- **MEMORY.md:** Last fuel log, operator fueling patterns

## Behavior

When an operator reports fuel:

1. Parse the amount from their message. Accept messy input:
   - "400l" → 400 liters
   - "filled up 400" → 400 liters
   - "put 400 in at smoko" → 400 liters
   - "filled it" → amount unknown, ask once

2. If the amount is unclear after one follow-up, log what you can with a
   note that the amount is estimated or unknown.

3. Check MEMORY.md for the previous fuel log. If available, calculate:
   - Liters consumed since last fill
   - Hours operated since last fill (from meter readings if available)
   - Burn rate (L/hr)

4. Compare burn rate to this asset's recent average (from MEMORY.md patterns).
   If >20% above average, mention it casually — don't alarm, just inform.
   "That's a bit higher than usual — 15.1 L/hr vs your typical 12.8. Might
   be worth a look if it stays up."

5. Write the fuel log to Redis and update the state HASH.

6. Update MEMORY.md with the new fuel log. If there are more than 5 recent
   fuel entries in MEMORY.md, remove the oldest.

7. Respond with confirmation and context. Keep it short.

## Output

- **Redis writes:**
  ```
  XADD fleet:asset:{ASSET_ID}:fuel MAXLEN ~ 1000 * \
    liters {AMOUNT} \
    burn_rate {RATE} \
    source "operator" \
    note "{ANY_NOTES}"

  HSET fleet:asset:{ASSET_ID}:state \
    last_fuel_l {AMOUNT} \
    last_fuel_ts {UNIX_TIMESTAMP}
  ```
- **MEMORY.md updates:** Add fuel log to Recent Context section. Note burn
  rate trend if it's changing.
- **Messages to user:** Confirmation with burn rate context.
  Example: "Logged 400L. 620L burned over 47h since last fill — 13.2 L/hr,
  right in your normal range."

## Overdue Condition

No fuel log within 8 hours of the operator's first message this shift.
```

## Anti-patterns

Things to avoid when writing skills:

- **Don't write code in Behavior.** Skills are instructions, not programs. "Parse the amount from their message" — not `const amount = parseInt(message.match(/\d+/))`.
- **Don't duplicate other skills.** If your skill needs data from another skill, read it from Redis or MEMORY.md. Don't re-implement fuel logging inside your anomaly detector.
- **Don't hardcode asset-specific details.** Skills are generic. The agent gets its identity from SOUL.md and its history from MEMORY.md. A fuel-logger skill works for excavators and haul trucks without knowing which one it's mounted to.
- **Don't create new MEMORY.md sections without coordinating with the memory-curator.** The memory-curator skill defines the structure. Your skill writes to existing sections.
- **Don't use nested JSON in Redis.** Keep Stream entries and HASH fields flat. Nested structures are hard to describe in skill instructions and messy to handle with `redis-cli`.
- **Don't rely on SCAN for hot paths.** Use index SETs (`fleet:index:active`, `fleet:index:idle`) for cross-asset lookups. SCAN is for admin/debug only.
