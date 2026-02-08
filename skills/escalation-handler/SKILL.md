---
name: escalation-handler
description: Detect and create escalations for unresolved issues, repeated failures, compliance gaps, and safety concerns
metadata: {"openclaw":{"requires":{"bins":["redis-cli"],"env":["REDIS_URL"]}}}
---

# Escalation Handler

_Detect and create escalations for unresolved issues, repeated failures, compliance gaps, and safety concerns._

## Trigger

- **Heartbeat** — Every 2 hours, check for patterns that warrant escalation to Clawordinator
- **Message** — User (supervisor, foreman) explicitly requests an escalation ("escalate the hydraulic issue on EX-001", "flag KOT28 for management")

## Input

- **User messages:** Explicit escalation requests from supervisors or foremen
- **Redis keys:**
  - `fleet:index:active` — SET of active asset IDs
  - `fleet:asset:{ID}:issues` — STREAM (unresolved issues, checking age and recurrence)
  - `fleet:asset:{ID}:maintenance` — STREAM (to check whether issues have been resolved by maintenance)
  - `fleet:asset:{ID}:alerts` — STREAM (unresolved alerts, especially safety-severity)
  - `fleet:asset:{ID}:state` — HASH (HMGET: last_fuel_ts, last_preop_ts, last_seen, status)
  - `fleet:escalations` — STREAM (existing escalations, to avoid duplicates)
- **MEMORY.md:** Active Escalations section (quick check for existing escalations before creating new ones)

## Behavior

The escalation handler is Clawvisor's mechanism for pushing problems up to Clawordinator when they aren't being resolved at the fleet level. It creates a formal record in the escalations stream that Clawordinator monitors and acts on.

### On heartbeat

Every 2 hours, scan for patterns that warrant escalation:

**Unresolved issues.** For each active asset, read recent entries from the issues stream (last 30 days using XRANGE). For each issue, check whether a corresponding maintenance entry exists in the maintenance stream with a matching category and a later timestamp. If an issue is older than 72 hours and has no matching maintenance logged, it qualifies for escalation as "unresolved_issue." Something was reported three days ago and nobody has fixed it.

**Repeated failures.** While scanning the issues stream, group entries by category. If the same category appears 3 or more times in 30 days for the same asset, escalate as "repeated_failure." The problem keeps coming back — the root cause isn't being addressed.

**Compliance gaps.** For each active asset, check compliance timestamps from the state HASH. Calculate a simple compliance score: how many of the three data types (fuel, pre-op, meter) are current within their thresholds. If an asset's compliance rate is below 50% over the last 7 days — meaning it's consistently missing logs across multiple categories — escalate as "compliance_gap."

**Safety concerns.** Check the alerts stream for any unresolved alerts with severity "critical" that are safety-related (type "preop_pattern" with failed pre-ops, or issues with category "safety"). Safety-severity items get immediate escalation as "safety_concern" regardless of age.

### Avoiding duplicate escalations

Before creating any escalation, check for duplicates in two places:

1. MEMORY.md Active Escalations — fast check, covers recently created escalations.
2. The `fleet:escalations` stream — read recent entries (XREVRANGE with COUNT 50) and look for the same asset ID and escalation type.

If an existing escalation covers the same asset and type, skip it. Don't create a new escalation just because the heartbeat ran again. An escalation stays open until Clawordinator resolves it.

### On message

When a supervisor or foreman explicitly asks to escalate something:

1. Identify the asset and the concern from their message.
2. Create the escalation immediately — no threshold checking needed. The human decided it needs escalation.
3. Confirm the escalation was created and describe what happens next: "Escalated. Clawordinator will review the hydraulic issue on EX-001. I've flagged it as a repeated failure, severity warning."

### Severity assignment

- **Warning:** Unresolved issues, compliance gaps, repeated non-safety failures. These need attention but aren't urgent.
- **Critical:** Safety concerns, repeated safety-related failures, or any issue a supervisor explicitly marks as urgent.

## Output

- **Redis writes:**
  ```
  XADD fleet:escalations MAXLEN ~ 500 * \
    asset_id    "{ASSET_ID}" \
    type        "{unresolved_issue|repeated_failure|compliance_gap|safety_concern}" \
    description "{context for Clawordinator — what's wrong, how long, what's been tried}" \
    severity    "{warning|critical}" \
    from        "clawvisor"
  ```
- **MEMORY.md updates:** Add new escalations to Active Escalations section. Include asset ID, type, severity, and when it was created. Remove resolved escalations when maintenance or Clawordinator action addresses the underlying issue.
- **Messages to user:** Confirmation when a manual escalation is created. No messages for heartbeat-generated escalations — those surface when the relevant person next interacts with Clawvisor.
