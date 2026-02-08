---
name: session-memory
description: Persist session context when /new command issued
trigger: lifecycle:new_session
command: /new
---

# Session Memory Hook

## When to Fire
- `/new` command issued by operator
- Before starting a new conversation session

## Steps

1. **Assess session value** - Check for significant events (fuel logs, status changes, escalations)
2. **Create summary** if valuable events occurred
3. **Append to `memory/YYYY-MM-DD.md`**:
   ```
   ## Session End - HH:MM
   - Duration: X hours
   - Fuel logs: N (A accepted, F flagged)
   - Status: OPERATIONAL
   ```
4. **Update `MEMORY.md`** if durable lessons learned
5. **Confirm ready** - Silent unless verbose mode

## Response Template
```
Session saved. Ready for new conversation.
```
