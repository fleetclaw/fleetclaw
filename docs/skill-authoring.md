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
description: Accept fuel log entries from operators and record them
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---
```

The `requires` block declares system dependencies. `bins` lists command-line tools the skill needs. `env` lists environment variables. OpenClaw checks these at startup and warns if anything is missing. Most Tier 1 skills have no external bin or env requirements.

**Markdown body** (LLM-readable) — teaches the agent the behavior:

```markdown
# Fuel Logger

_Accept casual fuel input from operators and record it._

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
- **Inbox message** — A new file appears in the agent's inbox directory. Used for responding to messages from other agents (directives, maintenance acks, escalation resolutions).

Most skills use 1-2 triggers. A fuel-logger triggers on operator messages. A nudger triggers on heartbeat. A memory-curator triggers on both session end and heartbeat.

### Input

What data does the skill consume? Be specific about filesystem paths:

```markdown
## Input
- **User messages:** Natural language fuel reports (e.g., "400l", "filled up 400")
- **Outbox files:** Previous fuel entries in outbox/ (type: fuel) for burn rate calculation
- **state.md:** last_fuel_l, last_fuel_ts, burn_rate
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
   "put 400 in at smoko" all mean 400L.
2. If the amount is ambiguous, ask once. If still unclear, log what you can and note
   the ambiguity.
3. Check state.md and MEMORY.md for the last fuel log. Calculate burn rate if enough
   data exists.
4. Write a timestamped fuel entry to outbox/ and update state.md.
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
```

Do not use pseudocode or programming constructs. Write instructions the way you'd explain a task to a competent colleague.

### Output

What does the skill produce? Be specific about file formats:

```markdown
## Output

- **Outbox writes:** Write a timestamped fuel entry to outbox/:
  ```
  ---
  from: {ASSET_ID}
  type: fuel
  timestamp: {ISO-8601}
  ---
  liters: {AMOUNT}
  meter_at_fill: {METER}
  burn_rate: {RATE}
  status: {normal|high|low}
  ```
- **state.md updates:** Update last_fuel_l, last_fuel_ts, burn_rate
- **MEMORY.md updates:** Add fuel log to Recent Context section. Note burn
  rate trend if it's changing.
- **Messages to user:** Confirmation with burn rate context.
  Example: "Logged 400L. 620L burned over 47h since last fill — 13.2 L/hr,
  right in your normal range."
```

The file format in Output serves as documentation — it shows the exact frontmatter fields and body structure this skill writes. Tier 2 authors can read this to understand the data contract.

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

## Filesystem conventions

Skills that read or write data must follow the FleetClaw communication protocol. See `docs/communication.md` for the full reference.

### Message format

Every outbox and inbox file uses YAML frontmatter + markdown body:

```markdown
---
from: {agent-id}
type: {message-type}
timestamp: {ISO-8601}
---
{body content — key-value pairs or prose}
```

### Filename convention

```
{ISO-timestamp}_{type}.md
```

Colons replaced with hyphens: `2026-02-09T06-12-00_fuel.md`

### Key paths

| Path | Purpose |
|------|---------|
| `outbox/` | Agent writes its own data here |
| `inbox/` | Other agents write messages here |
| `state.md` | Agent's current operational state (flat key-value) |
| `fleet.md` | Fleet composition registry (read-only for most agents) |
| `MEMORY.md` | Agent's curated working memory |

### Cross-agent access

- **Clawvisor reads** asset agents' `outbox/` directories and `state.md` files
- **Clawvisor writes** to asset agents' `inbox/` directories (maintenance acks, alerts)
- **Clawvisor writes** to Clawordinator's `inbox/` (escalations)
- **Clawordinator writes** to any agent's `inbox/` (directives)
- **Clawordinator writes** `fleet.md` (sole writer)

ACLs enforce these access patterns. See `docs/permissions.md`.

## MEMORY.md conventions

Skills that update MEMORY.md should follow these rules:

1. **Write curated summaries, not raw data.** MEMORY.md has a 15,000 character bootstrap limit. Write "Last fuel: 400L on Feb 8, burn rate normal" — not a transcript of the conversation.
2. **Respect the memory-curator skill's structure.** Each agent role has a memory-curator skill that defines MEMORY.md's sections and character budget. Your skill should write to the appropriate section, not create new top-level sections.
3. **Prune as you write.** If adding a new fuel log, remove the oldest one from the recent context section. Don't let your skill's data grow unbounded.
4. **Prefer outbox files for history.** If someone needs the last 50 fuel logs, that's an outbox directory read. MEMORY.md holds the last 3-5 for instant context.

## Skill tiers

FleetClaw skills exist in three tiers:

**Tier 1 — Ships with FleetClaw.** Works out of the box. Uses filesystem communication and MEMORY.md only. No external integrations. These skills define the baseline platform experience.

**Tier 2 — Organization-built.** Integrates with external systems via .env credentials (CMMS, telematics, fuel management). FleetClaw provides the skill template and this guide. The organization fills in the integration logic.

**Tier 3 — Community/advanced.** Extends the platform in ways not anticipated by the core team. Voice transcription, predictive analytics, custom dashboards.

When building a Tier 2 or 3 skill:

- Follow the template structure exactly — Trigger, Input, Behavior, Output, Overdue Condition
- Declare all external dependencies in frontmatter (`bins` and `env`)
- Document your outbox file types in Output so other skills can discover your data
- If your skill produces data on a regular cadence, add an Overdue Condition
- Reference `docs/communication.md` for the message format specification

## Example: fuel-logger skill

This is a complete Tier 1 skill showing all conventions:

```markdown
---
name: fuel-logger
description: Accept fuel log entries from operators and record them
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Fuel Logger

_Accept casual fuel input from operators and record it._

## Trigger

- **Message** — Operator mentions fuel, refueling, or sends a number that
  looks like a fuel amount (e.g., "400l", "filled up", "put 400 in")

## Input

- **User messages:** Natural language fuel reports
- **Outbox files:** Previous fuel entries in outbox/ (type: fuel) for burn rate
- **state.md:** last_fuel_l, last_fuel_ts, burn_rate
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

3. Check state.md and MEMORY.md for the previous fuel log. If available,
   calculate:
   - Liters consumed since last fill
   - Hours operated since last fill (from meter readings if available)
   - Burn rate (L/hr)

4. Compare burn rate to this asset's recent average (from MEMORY.md patterns).
   If >20% above average, mention it casually — don't alarm, just inform.

5. Write the fuel entry to outbox/ and update state.md.

6. Update MEMORY.md with the new fuel log. If there are more than 5 recent
   fuel entries in MEMORY.md, remove the oldest.

7. Respond with confirmation and context. Keep it short.

## Output

- **Outbox writes:**
  ---
  from: {ASSET_ID}
  type: fuel
  timestamp: {ISO-8601}
  ---
  liters: {AMOUNT}
  meter_at_fill: {METER}
  burn_rate: {RATE}
  status: {normal|high|low}

- **state.md updates:** Update last_fuel_l, last_fuel_ts, burn_rate
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
- **Don't duplicate other skills.** If your skill needs data from another skill, read it from the relevant outbox files or MEMORY.md. Don't re-implement fuel logging inside your anomaly detector.
- **Don't hardcode asset-specific details.** Skills are generic. The agent gets its identity from SOUL.md and its history from MEMORY.md. A fuel-logger skill works for excavators and haul trucks without knowing which one it's mounted to.
- **Don't create new MEMORY.md sections without coordinating with the memory-curator.** The memory-curator skill defines the structure. Your skill writes to existing sections.
- **Don't assume infinite outbox growth.** Outbox files may be archived or deleted after a retention period. For recent data (last shift, last few days), outbox files are reliable. For long-term history, use MEMORY.md summaries.
