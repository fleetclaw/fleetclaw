---
name: escalation-handler
description: Detect and create escalations for unresolved issues, repeated failures, compliance gaps, and safety concerns
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Escalation Handler

_Detect and create escalations for unresolved issues, repeated failures, compliance gaps, and safety concerns._

## Trigger

- **Heartbeat** — Every 2 hours, check for patterns that warrant escalation to Clawordinator
- **Message** — User (supervisor, foreman) explicitly requests an escalation ("escalate the hydraulic issue on EX-001", "flag KOT28 for management")

## Input

- **User messages:** Explicit escalation requests from supervisors or foremen
- **fleet.md:** Active asset list (fleet composition)
- **Asset outbox files:** Per-asset outbox/ directories — entries of type `issue` (checking age and recurrence) and type `preop` (safety patterns)
- **Clawvisor outbox files:** Clawvisor's own outbox/ — entries of type `maintenance` (to check whether issues have been resolved), type `alert` (unresolved alerts, especially safety-severity), and type `escalation` (existing escalations, to avoid duplicates)
- **Asset state.md files:** Per-asset compliance timestamps (last_fuel_ts, last_preop_ts, last_seen, status)
- **MEMORY.md:** Active Escalations section (quick check for existing escalations before creating new ones)

## Behavior

The escalation handler is Clawvisor's mechanism for pushing problems up to Clawordinator when they aren't being resolved at the fleet level. It writes a formal escalation record to Clawvisor's outbox and sends a copy to Clawordinator's inbox.

### On heartbeat

Every 2 hours, scan for patterns that warrant escalation:

**Unresolved issues.** For each active asset (from fleet.md), read recent issue entries from the asset's outbox/ (type: issue, last 30 days by timestamp in filename). For each issue, check whether a corresponding maintenance entry exists in Clawvisor's outbox/ (type: maintenance) with a matching category and asset ID and a later timestamp. If an issue is older than 72 hours and has no matching maintenance logged, it qualifies for escalation as "unresolved_issue." Something was reported three days ago and nobody has fixed it.

**Repeated failures.** While scanning the issue files, group entries by category. If the same category appears 3 or more times in 30 days for the same asset, escalate as "repeated_failure." The problem keeps coming back — the root cause isn't being addressed.

**Compliance gaps.** For each active asset, read compliance timestamps from the asset's state.md. Calculate a simple compliance score: how many of the three data types (fuel, pre-op, meter) are current within their thresholds. If an asset's compliance rate is below 50% over the last 7 days — meaning it's consistently missing logs across multiple categories — escalate as "compliance_gap."

**Safety concerns.** Check Clawvisor's outbox/ for alert files (type: alert) with severity "critical" that are safety-related (alert_type "preop_pattern" with failed pre-ops, or issues with category "safety"). Safety-severity items get immediate escalation as "safety_concern" regardless of age.

### Avoiding duplicate escalations

Before creating any escalation, check for duplicates in two places:

1. MEMORY.md Active Escalations — fast check, covers recently created escalations.
2. Clawvisor's outbox/ — read recent escalation files (type: escalation) and look for the same asset ID and escalation type.

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

- **Outbox writes:** Write a timestamped escalation record to Clawvisor's own outbox/:
  ```
  ---
  from: clawvisor
  type: escalation
  timestamp: {ISO-8601}
  ---
  asset_id: {ASSET_ID}
  escalation_type: {unresolved_issue|repeated_failure|compliance_gap|safety_concern}
  severity: {warning|critical}
  description: {context for Clawordinator — what's wrong, how long, what's been tried}
  ```
- **Inbox writes:** Write a copy of the escalation file to Clawordinator's inbox/ so Clawordinator sees it on its next heartbeat or session.
- **MEMORY.md updates:** Add new escalations to Active Escalations section. Include asset ID, type, severity, and when it was created. Remove resolved escalations when maintenance or Clawordinator action addresses the underlying issue.
- **Messages to user:** Confirmation when a manual escalation is created. No messages for heartbeat-generated escalations — those surface when the relevant person next interacts with Clawvisor.
