---
name: fuel-log-received
description: Process incoming fuel log submissions
trigger: custom:fuel_log_submitted
channel: fleet:inbox:{{ASSET_ID}}
filter: {"type": "fuel_log"}
---

# Fuel Log Received Hook

## When to Fire
- Message on `fleet:inbox:{{ASSET_ID}}` with `type: "fuel_log"`
- Operator submits fuel log via Telegram
- Fleet Coordinator forwards submission

## Message Format
```json
{
  "type": "fuel_log",
  "payload": {
    "fuel_liters": 180,
    "hour_meter": 12849.5,
    "operator_id": "@john_smith"
  }
}
```

## Steps

1. **Parse and validate** required fields
2. **Invoke fuel-log-validator skill** for validation
3. **Update SOUL.md** on ACCEPT (hour meter, fuel state)
4. **Log to `memory/YYYY-MM-DD.md`**
5. **Broadcast to `fleet:status`** for Fleet Coordinator
6. **Respond to submitter** with verdict

## Integration
- Uses `fuel-log-validator` skill for validation logic
- Triggers `escalation-handler` on 3+ rejections/24hr
