---
name: idle-manager
description: Manages asset idle/wake lifecycle based on activity for Fleet Coordinator
metadata: {"openclaw":{"requires":{"bins":["docker","redis-cli","jq"],"env":["REDIS_URL","COMPOSE_FILE"]}}}
---

# Idle Manager

Manages asset container lifecycle based on activity. The Fleet Coordinator uses this skill to automatically idle inactive assets and wake them when activity is detected.

## When to Use

- At the nightly check time (00:00 by default) to idle stale assets
- When an activity event is received for an idle asset (wake trigger)
- When a user requests manual idle/wake of an asset
- When FC boots and needs to restore active assets

## Idle Management Concepts

### Asset States

| State | Container | FC Tracking | Receives Messages |
|-------|-----------|-------------|-------------------|
| `active` | Running | Real-time | Yes, directly |
| `idle` | Stopped | Last known | Buffered, replayed on wake |

### Activity Types

These events reset an asset's idle timer:

- `fuel_log` - Fuel log submitted
- `pre_op` - Pre-op checklist completed
- `operator_message` - Any message in asset's Telegram group
- `heartbeat_response` - Asset responded to status request

### Idle Threshold

Default: 7 days without activity. Configurable via `idle_management.threshold_days` in fleet.yaml.

## Commands

### Check Status

```bash
# Get current idle/active status for all assets
for key in $(redis-cli -u "$REDIS_URL" KEYS "fleet:lifecycle:*"); do
    echo "=== ${key#fleet:lifecycle:} ==="
    redis-cli -u "$REDIS_URL" HGETALL "$key"
done
```

### Manual Wake

```bash
# Wake an idle asset
docker compose -f "$COMPOSE_FILE" start fleetclaw-{asset_id}

# Update status in Redis
redis-cli -u "$REDIS_URL" HSET "fleet:lifecycle:{asset_id}" \
  status "active" \
  last_activity "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  last_activity_type "manual_wake"

# Notify the asset group
# Post: "▶️ {ASSET_ID} resumed from idle"
```

### Manual Idle

```bash
# Stop an active asset
docker compose -f "$COMPOSE_FILE" stop fleetclaw-{asset_id}

# Update status in Redis
redis-cli -u "$REDIS_URL" HSET "fleet:lifecycle:{asset_id}" \
  status "idle" \
  idle_since "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Notify the asset group
# Post: "⏸️ {ASSET_ID} entering idle mode"
```

### Set Threshold

```bash
# Update threshold (days)
redis-cli -u "$REDIS_URL" SET "fleet:idle_threshold_days" 7
```

## Nightly Check Procedure

At the configured nightly check time (default 00:00):

1. **Load current status** from Redis
2. **For each active asset:**
   - Calculate days since `last_activity`
   - If > threshold days:
     - Stop container: `docker compose stop fleetclaw-{asset_id}`
     - Update status to `idle`
     - Post to asset group: "⏸️ {ASSET_ID} entering idle mode (no activity since {date})"
3. **Post summary** to FC group: "Nightly check: {N} assets idled ({list})"

```bash
#!/bin/bash
# Nightly idle check script

THRESHOLD_DAYS=${IDLE_THRESHOLD_DAYS:-7}
NOW=$(date +%s)
THRESHOLD_SECONDS=$((THRESHOLD_DAYS * 86400))

# Get all active assets
ACTIVE_ASSETS=$(redis-cli -u "$REDIS_URL" KEYS "fleet:lifecycle:*" | while read key; do
    STATUS=$(redis-cli -u "$REDIS_URL" HGET "$key" status)
    if [ "$STATUS" = "active" ]; then
        echo "${key#fleet:lifecycle:}"
    fi
done)

IDLED=()

for ASSET_ID in $ACTIVE_ASSETS; do
    LAST_ACTIVITY=$(redis-cli -u "$REDIS_URL" HGET "fleet:lifecycle:$ASSET_ID" last_activity)
    LAST_TS=$(date -d "$LAST_ACTIVITY" +%s 2>/dev/null || echo 0)

    if [ $((NOW - LAST_TS)) -gt $THRESHOLD_SECONDS ]; then
        # Idle the asset
        docker compose -f "$COMPOSE_FILE" stop "fleetclaw-${ASSET_ID,,}"

        redis-cli -u "$REDIS_URL" HSET "fleet:lifecycle:$ASSET_ID" \
            status "idle" \
            idle_since "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

        IDLED+=("$ASSET_ID")
    fi
done

if [ ${#IDLED[@]} -gt 0 ]; then
    echo "Nightly check: ${#IDLED[@]} assets idled (${IDLED[*]})"
fi
```

## Wake Trigger Detection

The gatekeeper routes messages to FC when an idle asset receives activity:

1. **Gatekeeper receives message** for asset group
2. **Checks asset status** in Redis: `HGET fleet:lifecycle:{asset_id} status`
3. **If idle:**
   - Buffer the message: `SET fleet:wake_buffer:{asset_id} {message_json} EX 300`
   - Post to group: "⏸️ Waking {ASSET_ID}, this takes about 30 seconds..."
   - Wake container: `docker compose start fleetclaw-{asset_id}`
   - Update status to `active`

## Boot Recovery

When FC starts, restore previously active assets:

```bash
# Get all assets that were active before shutdown
redis-cli -u "$REDIS_URL" KEYS "fleet:lifecycle:*" | while read key; do
    STATUS=$(redis-cli -u "$REDIS_URL" HGET "$key" status)
    ASSET_ID="${key#fleet:lifecycle:}"

    if [ "$STATUS" = "active" ]; then
        # Ensure container is running
        RUNNING=$(docker inspect -f '{{.State.Running}}' "fleetclaw-${ASSET_ID,,}" 2>/dev/null)
        if [ "$RUNNING" != "true" ]; then
            docker compose -f "$COMPOSE_FILE" start "fleetclaw-${ASSET_ID,,}"
            echo "Boot recovery: Started $ASSET_ID"
        fi
    fi
done
```

## Activity Broadcasting

When an active asset receives activity, it should broadcast to Redis:

```bash
# Asset publishes activity event
redis-cli -u "$REDIS_URL" PUBLISH "fleet:activity" "$(cat <<EOF
{
    "asset_id": "$ASSET_ID",
    "activity_type": "fuel_log",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)"
```

FC subscribes to activity events and updates tracking:

```bash
# FC subscription handler
redis-cli -u "$REDIS_URL" SUBSCRIBE "fleet:activity" | while read type channel message; do
    if [ "$type" = "message" ]; then
        ASSET_ID=$(echo "$message" | jq -r '.asset_id')
        ACTIVITY_TYPE=$(echo "$message" | jq -r '.activity_type')
        TIMESTAMP=$(echo "$message" | jq -r '.timestamp')

        redis-cli -u "$REDIS_URL" HSET "fleet:lifecycle:$ASSET_ID" \
            last_activity "$TIMESTAMP" \
            last_activity_type "$ACTIVITY_TYPE"
    fi
done
```

## Redis Data Structures

### Asset Status Hash

```
fleet:lifecycle:{ASSET_ID}
  status: "active" | "idle"
  last_activity: "2025-01-15T14:32:00Z"
  last_activity_type: "fuel_log"
  idle_since: "2025-01-22T00:00:00Z"  # Only present if idle
```

### Wake Buffer

```
fleet:wake_buffer:{ASSET_ID}
  # JSON of triggering message
  # TTL: 300 seconds (5 minutes)
```

### Group Mapping

```
fleet:group_map:{telegram_group_id}
  asset_id: "EX-001"
  type: "agent" | "tracked" | "coordinator"
  status: "active" | "idle"
```

## Status Report Format

When reporting fleet status:

```markdown
## Fleet Status

### Active Assets (32)
Operating normally, containers running.

### Idle Assets (12)
No recent activity, containers stopped:
| Asset | Last Activity | Idle Since |
|-------|---------------|------------|
| EX-002 | Dec 20, 2024 | Dec 27 |
| JOS67 | Jan 5, 2025 | Jan 12 |

### Tracked Assets (20)
Light vehicles, FC-managed only (no containers).
```

## Error Handling

### Container Start Failure

If container fails to start:
1. Log the error
2. Retry once after 30 seconds
3. If still failing, mark asset as `error` status
4. Post to FC group: "Failed to wake {ASSET_ID}: {error}"

### Redis Connection Lost

If Redis unavailable:
1. Continue with local state if cached
2. Skip idle checks (cannot verify last activity)
3. Log degraded mode
4. Retry connection every 30 seconds

---

*Template version: 1.0*
