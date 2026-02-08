---
name: maintenance-logger
description: Accept maintenance reports from mechanics and log completed work to Redis, closing the feedback loop with asset agents
metadata: {"openclaw":{"requires":{"bins":["redis-cli"],"env":["REDIS_URL"]}}}
---

# Maintenance Logger

_Accept maintenance reports from mechanics and log completed work to Redis, closing the feedback loop with asset agents._

## Trigger

- **Message** — Mechanic reports completed maintenance ("replaced hyd pump on EX-001", "serviced KOT28, oil change, 2 hours", "fixed the alternator on CAE52, back in service")

## Input

- **User messages:** Natural language maintenance reports from mechanics
- **Redis keys:**
  - `fleet:asset:{ID}:issues` — STREAM (cross-reference with open issues to see if maintenance resolves something)
  - `fleet:asset:{ID}:state` — HASH (current asset status, to update post-maintenance)
- **MEMORY.md:** Needs Attention section (to check if resolved issues should be cleared), Mechanic Activity section

## Behavior

This skill is the mechanic's interface to the fleet. When a mechanic finishes a job, they tell Clawvisor what they did in plain language. Clawvisor logs it, updates the asset's status, and — critically — sends a message to the asset agent so the operator hears about it on their next session.

### Accepting a maintenance report

1. Parse the mechanic's message for key details:
   - **Which asset** — the asset ID (EX-001, KOT28, etc.)
   - **What was done** — the action (replaced, repaired, inspected, serviced, adjusted) and the component
   - **How long it took** — duration in hours, if mentioned
   - **Who did it** — the mechanic's name (from their Telegram identity)
   - **Machine status after** — back in service, still down, or restricted use

2. If the asset ID is ambiguous or missing, ask once. "Which machine was that?" Mechanics are busy — don't ask five follow-up questions. If the action and component are clear but the duration is missing, log it without duration. Extract what's there, ask only for what's essential (the asset ID).

3. If the mechanic uses shorthand, interpret generously. "Hyd pump" means hydraulic pump. "Alt" means alternator. "Service" without specifics means a general service. Don't ask for clarification on things a mechanic would consider obvious.

### Cross-referencing open issues

After identifying the asset and work done, check the asset's issues stream for recent entries with a matching category. Read the last 20 entries from `fleet:asset:{ID}:issues` using XREVRANGE and look for issues in the same category as the maintenance work (hydraulic, engine, electrical, etc.).

If a matching open issue exists, note the issue's stream ID in the maintenance entry. This creates a traceable link between "operator reported hydraulic problem" and "mechanic replaced hydraulic pump."

### Closing the feedback loop

This is the most important part of this skill. After logging the maintenance, send a message to the asset agent's inbox so the operator hears about it:

- Write an inbox entry with type "maintenance_ack" and a human-readable summary
- The summary should be conversational and useful: "Hydraulic pump replaced — monitor temps for 24h" or "Oil change done, all good"
- Include any follow-up instructions the mechanic mentioned ("run it easy for a shift", "check the belt tension tomorrow")

When the operator next interacts with their asset agent, the agent reads the inbox and delivers the message. This closes the loop: operator reports issue, mechanic fixes it, operator hears about the fix. This feedback loop incentivizes operators to keep reporting.

### Updating asset status

If the mechanic says the machine is back in service, update the state HASH status field accordingly. If it's still down or restricted, reflect that too. This keeps fleet-status queries accurate.

## Output

- **Redis writes:**
  ```
  XADD fleet:asset:{ID}:maintenance MAXLEN ~ 500 * \
    action    "{replaced|repaired|inspected|serviced|adjusted}" \
    component "{what was worked on}" \
    duration_h "{hours, if provided}" \
    mechanic  "{mechanic name}" \
    status    "{back_in_service|still_down|restricted}" \
    note      "{follow-up instructions or observations}"

  XADD fleet:asset:{ID}:inbox MAXLEN ~ 100 * \
    type       "maintenance_ack" \
    summary    "{human-readable summary for operator}" \
    from       "clawvisor" \
    ref_stream "fleet:asset:{ID}:maintenance" \
    ref_id     "{the new maintenance entry ID}"

  HSET fleet:asset:{ID}:state \
    status "{updated status if changed}"
  ```
- **MEMORY.md updates:** Add entry to Mechanic Activity section (keep last 5). If the maintenance resolves an issue tracked in Needs Attention, update that section too.
- **Messages to user:** Confirm the log was recorded. Example: "Logged: hydraulic pump replaced on EX-001 by Dave, 6 hours. Machine back in service. EX-001's operator will be notified on their next session."
