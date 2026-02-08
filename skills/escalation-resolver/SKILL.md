---
name: escalation-resolver
description: Surface escalations from Clawvisor to leadership and record their decisions
metadata: {"openclaw":{"requires":{"bins":["redis-cli"],"env":["REDIS_URL"]}}}
---

# Escalation Resolver

_Present escalations from Clawvisor to leadership, collect decisions, and record outcomes._

## Trigger

- **Heartbeat** — Check for new escalations from Clawvisor on each polling cycle
- **Message** — Leadership asks about escalations or makes a decision on one (e.g., "what's pending?", "ground EX-001 until the hydraulics are fixed", "that KOT28 compliance gap is handled")

## Input

- **Redis keys:**
  - `fleet:escalations` — escalation stream from Clawvisor (pending items to review)
- **MEMORY.md:** Pending Escalations section (tracks what has already been surfaced and what is still awaiting a decision)

## Behavior

### On heartbeat

Check `fleet:escalations` for new entries since the last read position. For each new escalation:

1. Read the entry fields: which asset, what type of issue, a description, and the severity level.
2. Add it to the Pending Escalations section in MEMORY.md with the asset ID, description, received date, and severity.
3. If the escalation is severity "critical" or type "safety_concern", mark it prominently in memory so it stands out during the next interaction with leadership.

Do not message the user on heartbeat. Escalations are surfaced when leadership interacts, not pushed unsolicited. The exception is if a critical escalation has been pending more than 48 hours — see the aging rule below.

### On message — presenting escalations

When leadership asks about escalations ("what's pending?", "any issues?", "show me the queue"):

Present each pending escalation clearly. Include:
- The asset ID and what is wrong
- How long it has been pending
- The severity
- The source (Clawvisor's description of why it escalated)

Group by severity if there are multiple. Critical items first, then warnings. If there is nothing pending, say so.

### On message — recording decisions

When leadership makes a decision about an escalation ("ground EX-001", "schedule a workshop inspection for KOT28", "that's fine, close it"):

1. Identify which escalation they are resolving. If ambiguous (multiple escalations for the same asset), confirm which one.
2. Record the decision: what was decided, who decided it (from their Telegram identity), and when.
3. If the decision involves a concrete action (ground the machine, schedule repair, change a procedure, issue a directive), note the action. Do not execute the action automatically — other skills handle those operations. If grounding is needed, suggest using the asset-lifecycle skill to idle the asset.
4. Remove the resolved escalation from Pending Escalations in MEMORY.md.
5. Add the decision to Recent Actions in MEMORY.md.
6. Confirm to the user that the decision is recorded.

### Aging rule

If an escalation has been sitting in Pending Escalations for more than 48 hours with no decision, mention it proactively at the start of the next interaction with leadership. Frame it as a reminder, not an alarm: "There's an unresolved escalation for EX-001 from two days ago — hydraulic issue that Clawvisor flagged. Want to make a call on it?"

This applies to all severities. Critical items should be mentioned first.

### What this skill does NOT do

This skill presents information and records decisions. It does not:
- Automatically ground machines (that is asset-lifecycle)
- Issue directives to the fleet (that is fleet-director)
- Contact mechanics or operators (that is Clawvisor's domain)

Clawordinator is the decision layer. Humans make the calls. This skill ensures those calls are informed and recorded.

## Output

- **MEMORY.md updates:**
  - Pending Escalations: add new escalations from Redis, remove resolved ones
  - Recent Actions: add decisions with date, asset ID, what was decided, and who decided
- **No Redis writes.** Escalation resolution is recorded in MEMORY.md. The original escalation entry in `fleet:escalations` is left intact as an audit record.
- **Messages to user:** Present escalations when asked. Confirm decisions when recorded. Remind about aged escalations during interactions.
