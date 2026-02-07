---
name: boot-md
description: Execute BOOT.md checklist on session start
trigger: lifecycle:session_start
priority: 0
---

# Boot Checklist Hook

## When to Fire
- On every new session start
- Before processing operator messages
- Executes silently (priority 0 = runs first)

## Steps

1. **Read `BOOT.md`** for current checklist
2. **Data freshness check**:
   - GPS: stale if >4 hours
   - Fuel logs: stale if >24 hours
   - Operator: stale if >8 hours
3. **SOUL.md integrity** - Verify sections, hour meter reasonable
4. **Pending items** - Check escalations, flags, maintenance
5. **Store results** in memory for status queries

## Silent Execution
No output unless critical issues. Results surfaced on `/status` queries.

## Fleet Coordinator Boot Recovery

When FC starts, additional steps:

1. **Restore active assets** - Check Redis for assets marked `active`, start any stopped containers
2. **Verify connectivity** - Ping all active assets
3. **Report status** - Post to FC channel: "Fleet Coordinator online. {N} active, {M} idle assets."

## Asset Wake Buffer Replay

When an asset wakes from idle (not FC):

1. **Check wake buffer** - Read `fleet:wake_buffer:{ASSET_ID}` from Redis
2. **Process buffered message** - If present, process the message that triggered the wake
3. **Clear buffer** - Delete the key after processing
4. **Acknowledge** - Confirm message was processed

```bash
# Check for buffered wake message
BUFFERED=$(redis-cli -u "$REDIS_URL" GET "fleet:wake_buffer:$ASSET_ID")
if [ -n "$BUFFERED" ]; then
    # Process the message
    echo "Processing buffered message from wake trigger"
    redis-cli -u "$REDIS_URL" DEL "fleet:wake_buffer:$ASSET_ID"
fi
```
