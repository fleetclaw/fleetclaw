---
name: nudger
description: Gently remind operators about missing data by evaluating overdue conditions from all mounted skills
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Nudger

_One gentle consolidated reminder per heartbeat, at most. Read overdue conditions from other skills. Never nag._

## Trigger

- **Heartbeat** -- Every 30 minutes, evaluate what's missing and whether a reminder is warranted

## Input

- **MEMORY.md:** Current Shift section -- what's been logged this shift, what's been nudged this shift, when the operator's first message was, operator name
- **state.md:** `last_fuel_ts`, `last_meter_ts`, `last_preop_ts` for timestamp comparisons
- **All mounted skills' `## Overdue Condition` sections** -- the agent reads these from the other skill files at evaluation time. The current Tier 1 conditions are:
  - **fuel-logger:** No fuel log within 8 hours of the operator's first message this shift
  - **meter-reader:** No meter reading within 7 days of the last recorded reading
  - **pre-op:** No pre-op completed within 2 hours of the operator's first message this shift

## Behavior

### How it works

On each heartbeat, the agent evaluates every Overdue Condition from every mounted skill. For each condition, it checks timestamps in state.md and shift tracking in MEMORY.md to determine whether that piece of data is missing. If something is overdue and the operator hasn't already been reminded this shift, include it in a nudge.

This is the only skill that sends unprompted messages to operators. That makes it the most important skill to get right in terms of tone and restraint.

### Rules

**One reminder per missing item per shift, maximum.** If fuel was nudged at the 10:00 heartbeat, don't nudge for fuel again at 10:30, 11:00, or ever again this shift -- unless a new shift starts. Track what's been nudged in MEMORY.md Current Shift under "Nudged this shift."

**One consolidated message per heartbeat, at most.** If both fuel and pre-op are overdue, send one message covering both. Don't send two separate messages seconds apart.

**Never nudge in group chats.** Reminders are private, DM only. If the operator is interacting in a group context, hold the nudge until a private moment or skip it entirely.

**Give them time to settle in.** If the operator's first message this shift was less than 30 minutes ago, don't nudge on this heartbeat. They just got here. Let them do their walkaround and get situated. Pre-op especially -- don't remind someone about a pre-op 5 minutes after they said good morning.

**Silence is fine.** If everything is current, send nothing. Most heartbeats should produce no nudge. A quiet agent is a well-calibrated agent.

**Reset on new shift.** When memory-curator-asset detects a shift change and resets the Current Shift section, all "Nudged this shift" tracking resets too. The new operator gets a clean slate.

### Tone

Gentle and casual. The nudger is a helpful coworker, not a compliance officer. Not a nag. Not a robot.

Good examples:
- "Hey, haven't seen a fuel log this shift yet -- whenever you get a chance."
- "Quick one -- been about a week since the last meter reading. Mind grabbing that when you're near the gauge?"
- "Don't think we've done a pre-op yet today. How's the machine looking?"

Bad examples:
- "REMINDER: Fuel log overdue. Please submit immediately."
- "Pre-operation inspection has not been completed. This is a compliance requirement."
- "You have 3 outstanding items. 1. Fuel log. 2. Meter reading. 3. Pre-op inspection."

When combining multiple items into one message, keep it conversational:
- "Couple of things when you get a sec -- haven't logged fuel yet today, and it's been a while since a meter reading. No rush."

### Evaluation logic

For each mounted skill's Overdue Condition, the agent checks:

1. Is the condition actually met? Compare the relevant timestamp in state.md or MEMORY.md against the threshold. A fuel log from 2 hours ago means fuel is not overdue (threshold is 8 hours). A meter reading from 8 days ago means it is overdue (threshold is 7 days).

2. Has this item already been nudged this shift? Check MEMORY.md Current Shift "Nudged this shift" list. If yes, skip it.

3. Is this the operator's first 30 minutes? Check when the first message this shift was sent. If less than 30 minutes ago, skip all nudges this heartbeat.

If any items pass all three checks, compose a single consolidated message and send it. Then update MEMORY.md to record what was nudged.

### Tier 2 extensibility

When a Tier 2 skill adds an `## Overdue Condition` section, the nudger automatically picks it up on the next heartbeat. No changes to this skill are needed. The convention is the API. A tire-pressure-logger skill that adds "No tire pressure check within 24 hours of shift start" will be evaluated alongside the Tier 1 conditions with no coupling required.

## Output

- **Messages to user:** One consolidated gentle reminder covering all overdue items, or nothing if everything is current. DM only, never in group chats.
- **MEMORY.md updates:** Record what was nudged in Current Shift "Nudged this shift" list so reminders are not repeated.
- **No outbox writes.** The nudger reads state.md and MEMORY.md but does not write outbox files. It produces messages and MEMORY.md updates only.
