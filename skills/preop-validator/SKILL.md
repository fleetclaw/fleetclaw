---
name: preop-validator
description: Pre-operation checklist validation for shift start
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Pre-Operation Validator

Validates pre-operation checklists submitted by operators at shift start. Ensures basic safety checks are completed before equipment operation.

## When to Use

When an operator submits a pre-op check. Recognize these patterns:

- "preop complete", "pre-op done", "prestart check done"
- "daily inspection complete"
- "starting shift" with checklist items

## Universal Checklist

All mobile equipment uses the same 6-item checklist:

| Item | Check |
|------|-------|
| Engine Oil | Level OK |
| Hydraulic Oil | Level OK |
| Coolant Level | Level OK |
| Fire Extinguisher | Present and charged |
| Horn | Operational |
| Backup Alarm | Operational |

## Validation Flow

### Step 1: Parse Submission

When operator submits "preop complete" or similar:

```
Please confirm these items are OK:

1. Engine Oil level
2. Hydraulic Oil level
3. Coolant level
4. Fire Extinguisher present
5. Horn tested
6. Backup Alarm tested

Reply "confirmed" or list any issues.
```

### Step 2: Evaluate Response

| Condition | Action |
|-----------|--------|
| All items OK | Equipment Cleared |
| Any item requires attention | Reported for Maintenance |

### Step 3: Log to Memory

Append to `memory/YYYY-MM-DD.md`:

```markdown
## Pre-Op Check - {time}

- **Operator:** @operator_name
- **Status:** Equipment Cleared / Reported for Maintenance
- **Notes:** {any issues}
```

## Response Templates

### Equipment Cleared

```
Pre-op check recorded

  Operator: {operator}
  Time: {time}
  Status: All items OK

Equipment cleared for operation.
```

### Reported for Maintenance

```
Pre-op check recorded

  Operator: {operator}
  Time: {time}

Issue noted:
  - {issue}

Reported for maintenance. Await supervisor guidance before operating.
```

## Prompting for Pre-Op

If asset is used without pre-op that shift:

```
Pre-operation check not recorded for this shift.

Please complete pre-op check before continuing.

Reply "preop complete" after walk-around and safety checks.
```

## Integration

The `asset-monitor` skill reads `preop_checks.latest` from SOUL.md to verify pre-op compliance. If no pre-op recorded for current shift, asset-monitor will flag the asset.
