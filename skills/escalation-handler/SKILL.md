---
name: escalation-handler
description: Multi-level escalation chain with timeouts and approval gates
metadata: {"openclaw":{"requires":{"bins":[],"env":["SUPERVISOR_ID","SAFETY_ID","OWNER_ID"]}}}
---

# Escalation Handler

Manages the 4-level escalation chain for unresolved issues. Uses Lobster workflows for multi-step processes with approval gates and timeouts.

## When to Use

Trigger escalation when:
- Operating-without-tracking detected (no GPS/comms for 4+ hours during operation)
- Safety concern raised by operator
- Critical system alert (hydraulic pressure, engine temp, etc.)
- Repeated validation failures (3+ rejected fuel logs)
- Asset marked DOWN without explanation

## Escalation Levels

| Level | Recipient | Timeout | Approval Required |
|-------|-----------|---------|-------------------|
| 1 | Supervisor | 4 hours | No |
| 2 | Safety Officer | 2 hours | Yes (to continue) |
| 3 | Owner/Manager | 2 hours | Yes (to continue) |
| 4 | CRITICAL State | Ongoing | N/A |

## Starting an Escalation

### Step 1: Create Escalation Record

Create `memory/escalations/{ESCALATION_ID}.yaml`:

```yaml
id: ESC-2024-0115-001
asset_id: EX-001
trigger: operating_without_tracking
severity: high
created: "2024-01-15T10:00:00Z"
status: active
current_level: 1
history:
  - level: 1
    notified: "2024-01-15T10:00:00Z"
    recipient: "@supervisor_name"
    acknowledged: null
    resolved: null
```

### Step 2: Start Lobster Workflow

Execute the escalation workflow:

```bash
lobster run escalation.lobster \
  --var ESCALATION_ID="ESC-2024-0115-001" \
  --var ASSET_ID="EX-001" \
  --var TRIGGER="operating_without_tracking" \
  --var MESSAGE="EX-001 has been operating without tracking data for 4+ hours"
```

## Escalation Workflow

See `escalation.lobster` for the full workflow definition.

### Level 1: Supervisor Notification

**Action:** Send Telegram DM to supervisor
**Timeout:** 4 hours
**On acknowledge:** Close escalation, log resolution
**On timeout:** Proceed to Level 2

Message template:
```
⚠️ Escalation Alert - Level 1

Asset: {ASSET_ID}
Issue: {TRIGGER_DESCRIPTION}
Time: {TIMESTAMP}

{DETAILED_MESSAGE}

Reply "ACK" to acknowledge, or "RESOLVED {notes}" to close.
```

### Level 2: Safety Officer Notification

**Action:** Send Telegram DM to Safety Officer
**Timeout:** 2 hours
**Approval:** Required to continue to Level 3
**On acknowledge:** Hold at Level 2 until resolved
**On timeout:** Proceed to Level 3

Message template:
```
🚨 Escalation Alert - Level 2

Asset: {ASSET_ID}
Issue: {TRIGGER_DESCRIPTION}
Time: {TIMESTAMP}

Supervisor did not acknowledge within 4 hours.

{DETAILED_MESSAGE}

Reply "ACK" to acknowledge.
Reply "RESOLVED {notes}" to close.
Reply "ESCALATE" to immediately proceed to Owner.
```

### Level 3: Owner/Manager Notification

**Action:** Send Telegram DM to Owner/Manager
**Timeout:** 2 hours
**Approval:** Required to continue to Level 4
**On acknowledge:** Hold at Level 3 until resolved
**On timeout:** Proceed to Level 4 (CRITICAL)

Message template:
```
🆘 Escalation Alert - Level 3

Asset: {ASSET_ID}
Issue: {TRIGGER_DESCRIPTION}
Time: {TIMESTAMP}

Neither Supervisor nor Safety Officer have resolved this issue.

{DETAILED_MESSAGE}

Reply "ACK" to acknowledge and take ownership.
Reply "RESOLVED {notes}" to close.
```

### Level 4: CRITICAL State

**Action:**
- Set asset status to CRITICAL
- Post hourly broadcasts to #fleet-coordination
- Continue until manually resolved

Message template (hourly):
```
🆘 CRITICAL - Unresolved Escalation

Asset: {ASSET_ID}
Issue: {TRIGGER_DESCRIPTION}
Escalation ID: {ESCALATION_ID}
Duration: {HOURS_SINCE_START} hours unresolved

This issue has not been acknowledged by Supervisor, Safety, or Owner.
Immediate attention required.

{ESCALATION_HISTORY_SUMMARY}
```

## Acknowledging Escalations

When a recipient replies with "ACK":

1. Update escalation record:
   ```yaml
   history:
     - level: 1
       acknowledged: "2024-01-15T12:30:00Z"
       acknowledged_by: "@supervisor_name"
   ```

2. Cancel the timeout for current level

3. Notify the asset:
   ```
   ✓ Escalation acknowledged by {RECIPIENT}
   Issue: {TRIGGER_DESCRIPTION}
   Awaiting resolution...
   ```

## Resolving Escalations

When a recipient replies with "RESOLVED {notes}":

1. Update escalation record:
   ```yaml
   status: resolved
   resolved: "2024-01-15T14:00:00Z"
   resolved_by: "@supervisor_name"
   resolution_notes: "{notes}"
   ```

2. Notify all parties:
   ```
   ✓ Escalation Resolved

   Asset: {ASSET_ID}
   Issue: {TRIGGER_DESCRIPTION}
   Resolved by: {RESOLVED_BY}
   Resolution: {NOTES}
   Duration: {RESOLUTION_TIME}
   ```

3. Update asset status (if changed to CRITICAL, restore previous)

4. Log to memory:
   ```markdown
   ## Escalation Resolved - {TIME}

   - **ID:** {ESCALATION_ID}
   - **Issue:** {TRIGGER_DESCRIPTION}
   - **Duration:** {DURATION}
   - **Resolved by:** {RESOLVED_BY}
   - **Resolution:** {NOTES}
   ```

## Escalation Triggers

### Operating Without Tracking

Detected by asset-monitor skill when:
- GPS data is stale (>4 hours)
- But hour meter has advanced (indicating operation)

Severity: HIGH

### Safety Concern

Operator explicitly raises safety issue:
- "safety concern", "safety issue", "unsafe"
- Equipment malfunction affecting safety

Severity: HIGH to CRITICAL (based on description)

### Critical System Alert

Automated alerts for:
- Hydraulic pressure outside range
- Engine temperature high
- Critical fault codes

Severity: CRITICAL

### Repeated Validation Failures

Triggered when:
- 3+ fuel logs rejected in 24 hours
- Suggests data quality or equipment issue

Severity: MEDIUM

### Unexplained Downtime

Asset marked DOWN but:
- No explanation provided
- No maintenance scheduled

Severity: MEDIUM

## Manual Escalation

Operators can manually trigger escalation:

```
@ASSET escalate: {description}
```

This creates a Level 1 escalation with the provided description.

## Viewing Active Escalations

Query active escalations:

```bash
ls memory/escalations/*.yaml | while read f; do
  status=$(grep "status:" "$f" | cut -d: -f2 | tr -d ' ')
  if [ "$status" = "active" ]; then
    cat "$f"
  fi
done
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SUPERVISOR_ID` | Telegram user ID for Level 1 |
| `SAFETY_ID` | Telegram user ID for Level 2 |
| `OWNER_ID` | Telegram user ID for Level 3 |
| `ESCALATION_CHANNEL` | Channel for Level 4 broadcasts |
