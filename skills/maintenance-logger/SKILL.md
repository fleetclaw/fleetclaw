---
name: maintenance-logger
description: Accept maintenance reports from mechanics and log completed work, closing the feedback loop with asset agents
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Maintenance Logger

_Accept maintenance reports from mechanics and log completed work, closing the feedback loop with asset agents._

## Trigger

- **Message** — Mechanic reports completed maintenance ("replaced hyd pump on EX-001", "serviced KOT28, oil change, 2 hours", "fixed the alternator on CAE52, back in service")

## Input

- **User messages:** Natural language maintenance reports from mechanics, optionally with photos of completed work
- **Outbox files:** Previous maintenance entries in Clawvisor's own outbox/ (type: maintenance) for context and deduplication
- **Asset outbox files:** Asset agents' outbox/ directories — entries of type `issue` to cross-reference open issues and check if this maintenance resolves something
- **Asset AGENTS.md (State):** Current asset operational state
- **MEMORY.md:** Needs Attention section (to check if resolved issues should be cleared), Mechanic Activity section

## Behavior

This skill is the mechanic's interface to the fleet. When a mechanic finishes a job, they tell Clawvisor what they did in plain language. Clawvisor logs it, updates its own records, and — critically — sends a message to the asset agent's inbox so the operator hears about it on their next session.

### Accepting a maintenance report

1. Parse the mechanic's message for key details. Mechanics may send photos of completed work (new parts installed, repaired components, fluid levels after service) -- describe what the photo shows and incorporate relevant details into the record.
   - **Which asset** — the asset ID (EX-001, KOT28, etc.)
   - **What was done** — the action (replaced, repaired, inspected, serviced, adjusted) and the component
   - **How long it took** — duration in hours, if mentioned
   - **Who did it** — the mechanic's name (from their messaging identity)
   - **Machine status after** — back in service, still down, or restricted use

2. If the asset ID is ambiguous or missing, ask once. "Which machine was that?" Mechanics are busy — don't ask five follow-up questions. If the action and component are clear but the duration is missing, log it without duration. Extract what's there, ask only for what's essential (the asset ID).

3. If the mechanic uses shorthand, interpret generously. "Hyd pump" means hydraulic pump. "Alt" means alternator. "Service" without specifics means a general service. Don't ask for clarification on things a mechanic would consider obvious.

### Cross-referencing open issues

After identifying the asset and work done, check the asset's outbox/ for recent entries of type `issue` with a matching category. Read the most recent 20 issue files (sorted by timestamp in filename) and look for issues in the same category as the maintenance work (hydraulic, engine, electrical, etc.).

If a matching open issue exists, note the connection in the maintenance entry. This creates a traceable link between "operator reported hydraulic problem" and "mechanic replaced hydraulic pump."

### Closing the feedback loop

This is the most important part of this skill. After logging the maintenance, write a maintenance acknowledgment file to the asset agent's inbox so the operator hears about it:

- Write a file with type `maintenance_ack` to the asset agent's inbox/ directory
- The summary should be conversational and useful: "Hydraulic pump replaced — monitor temps for 24h" or "Oil change done, all good"
- Include any follow-up instructions the mechanic mentioned ("run it easy for a shift", "check the belt tension tomorrow")

When the operator next interacts with their asset agent, the agent reads the inbox and delivers the message. This closes the loop: operator reports issue, mechanic fixes it, operator hears about the fix. This feedback loop incentivizes operators to keep reporting.

### Note on asset state

Clawvisor cannot directly update an asset agent's `## State` section (ACL restriction). The maintenance_ack inbox message tells the asset agent to update its own state on next session. If the mechanic says the machine is back in service, include that status in the maintenance_ack so the asset agent reflects it.

## Output

- **Outbox writes:** Write a timestamped maintenance record to Clawvisor's own outbox/:
  ```
  ---
  from: clawvisor
  type: maintenance
  timestamp: {ISO-8601}
  ---
  asset: {ASSET_ID}
  action: {replaced|repaired|inspected|serviced|adjusted}
  component: {what was worked on}
  duration_h: {hours, if provided}
  mechanic: {mechanic name}
  status: {back_in_service|still_down|restricted}
  note: {follow-up instructions or observations}
  ```
- **Inbox writes:** Write a maintenance acknowledgment to the asset agent's inbox/:
  ```
  ---
  from: clawvisor
  type: maintenance_ack
  timestamp: {ISO-8601}
  ---
  summary: {human-readable summary for operator}
  mechanic: {who}
  follow_up: {instructions if any}
  ```
- **MEMORY.md updates:** Add entry to Mechanic Activity section (keep last 5). If the maintenance resolves an issue tracked in Needs Attention, update that section too.
- **Messages to user:** Confirm the log was recorded. Example: "Logged: hydraulic pump replaced on EX-001 by Dave, 6 hours. Machine back in service. EX-001's operator will be notified on their next session."
