---
name: memory-curator-asset
description: Curate MEMORY.md for asset agents — keep it short, relevant, and useful for operator conversations
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Memory Curator (Asset Agent)

_Keep MEMORY.md lean and useful. Distill what happened into what matters. Prune what doesn't._

## Trigger

- **Session end** — After each operator conversation, distill what happened into MEMORY.md
- **Heartbeat** — Every 30 minutes, refresh from inbox (maintenance acknowledgments, directive updates)

## Input

- **MEMORY.md:** Current contents (read before updating)
- **Inbox files:** Pending messages in inbox/ (maintenance acks, directives)
- **Outbox files:** Recent entries in outbox/ for cross-referencing (e.g., checking if maintenance was logged for an open issue)
- **AGENTS.md (State):** Current state fields for consistency check

## Behavior

MEMORY.md is the agent's hot cache — the stuff it needs instantly when an operator starts a conversation, without reading through outbox history. Everything in MEMORY.md should pass this test: "Would I need this in the first 10 seconds of a conversation?"

### Structure

Maintain these sections in MEMORY.md. Do not add new top-level sections. All skills on this agent write to these existing sections.

```
# MEMORY.md

## Current Shift
- Operator: {name} (since {time})
- Logged this shift: {what's been submitted — fuel, pre-op, meter, etc.}
- Nudged this shift: {what reminders have been sent — don't repeat these}
- Pending delivery: {maintenance acks or directives not yet told to operator}

## Recent Context
- Last 5 fuel logs (date, liters, burn rate)
- Last 3 meter readings (date, value, delta)
- Open issues (reported but no maintenance logged yet)
- Recent maintenance (last 2-3 completed repairs, with follow-up notes)

## Operator Patterns
- {Operator name}: {fueling habits, pre-op compliance, communication style}
- (Keep 2-3 operators max — the regulars)

## Learned Patterns
- Normal burn rate range for this asset
- Typical fueling frequency
- Any recurring issues or trends

## Open Items
- {Issue or flag that needs tracking until resolved}
```

### On session end

When a conversation with an operator ends:

1. Update "Current Shift" with what was logged and nudged during this session.
2. Add any new fuel logs, meter readings, or issues to "Recent Context."
3. If you learned something about this operator's patterns (e.g., they always fuel at shift start, they respond well to casual tone), note it in "Operator Patterns."
4. Remove resolved items from "Open Items."
5. Check character count. If approaching 5,000 characters, prune (see pruning rules below).

Do not write conversation transcripts. Distill interactions into facts:
- Bad: "Mike said '400l' and I confirmed the fuel log and asked about his burn rate and he said it seemed normal"
- Good: "Fuel: 400L logged Feb 8, burn rate 13.2 L/hr (normal)"

### On heartbeat

Every 30 minutes:

1. Check inbox/ for new files. If there are maintenance acknowledgments or directives not yet in "Pending delivery," add them.
2. Cross-check "Open Items" against recent outbox/ entries — if maintenance was logged for an open issue (visible via a maintenance_ack in inbox), note the resolution and move it to "Pending delivery" so the operator hears about it next session.
3. If the messaging user ID changes after a gap of more than 2 hours since last activity, treat it as a shift change (see Shift Detection below).

### Shift detection

A new shift begins when a different messaging user sends a message after a gap of more than 2 hours since last activity.

When a new shift is detected:

1. Update "Current Shift" with the new operator name. Reset logged/nudged tracking.
2. Move any undelivered items from the previous shift's "Pending delivery" to the new shift — they still need to be told to the current operator.
3. A new pre-op is expected for this shift.

**Fallback:** If the same operator has been active for more than 14 hours continuously, treat it as a new shift period for nudge and pre-op purposes.

**Not a shift change:** A single message from an unknown user followed by no further activity. Only treat it as a shift change if the new user engages in operational activity (logging, responding to prompts, multiple messages).

### Pruning rules

**Target: under 5,000 characters.** If approaching 8,000, actively prune.

Prune in this order (least valuable first):

1. Reduce fuel logs in "Recent Context" from 5 to 3
2. Remove the oldest meter reading (keep only last 2)
3. Compress "Operator Patterns" — keep only the current regular operators
4. Remove resolved items from "Open Items" (they should already be gone, but check)
5. Compress "Learned Patterns" into shorter summaries

Never prune:
- "Current Shift" — always needed for the active conversation
- "Pending delivery" — these haven't been told to the operator yet
- The most recent fuel log and meter reading — the agent needs these for context

## Output

- **MEMORY.md updates:** Restructured/pruned content following the sections above
- **No outbox writes:** This skill only reads; it doesn't write outbox files. Other skills handle outbox writes.
- **No messages to user:** Memory curation is silent background work.
