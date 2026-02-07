---
name: asset-monitor
description: 4-hour self-check loops for data freshness and operating-without-tracking detection
metadata: {"openclaw":{"requires":{"bins":[],"env":["REDIS_URL"]}}}
---

# Asset Monitor

Performs periodic self-checks to detect data staleness, operating-without-tracking conditions, and other anomalies. Runs as a background loop every 4 hours.

## When to Use

This skill runs automatically in the background. It should be triggered:
- Every 4 hours (via cron or OpenClaw scheduler)
- On startup (initial health check)
- When manually requested: "run health check", "check status"

## Self-Check Loop

### Step 1: Check Data Freshness

Review data sources and their last update times:

| Data Source | Stale Threshold | Action if Stale |
|-------------|-----------------|-----------------|
| GPS/Location | 2 hours | FLAG |
| Fuel logs | 24 hours | FLAG |
| Operator contact | 8 hours | FLAG |
| System health | 4 hours | FLAG |

Read from SOUL.md:
```yaml
data_freshness:
  gps:
    last_update: "2024-01-15T08:00:00Z"
  fuel:
    last_log: "2024-01-15T06:00:00Z"
  operator:
    last_contact: "2024-01-15T10:00:00Z"
```

Calculate staleness:
```bash
now=$(date -u +%s)
last_gps=$(date -d "$GPS_LAST_UPDATE" +%s)
gps_age_hours=$(( (now - last_gps) / 3600 ))

if [ $gps_age_hours -gt 2 ]; then
  echo "GPS data stale: ${gps_age_hours} hours"
fi
```

### Step 2: Detect Operating-Without-Tracking

**Critical Check:** Determine if asset is operating but not being tracked.

Signs of operating without tracking:
1. Hour meter has advanced since last check
2. But GPS data is stale (>4 hours)
3. Or no operator contact (>8 hours)

```yaml
# Compare current vs last check
last_check:
  hour_meter: 12840
  timestamp: "2024-01-15T06:00:00Z"

current:
  hour_meter: 12849  # Advanced by 9 hours
  gps_age: 6 hours   # Stale!
```

**If detected:**
1. Flag as `operating_without_tracking`
2. Post warning to operator chat
3. If not resolved in 30 minutes, trigger escalation

Warning message:
```
⚠️ Operating Without Tracking

Your asset appears to be operating but tracking data is stale.

  Hour meter: Advanced by {DELTA} hours
  GPS last seen: {GPS_AGE} ago
  Last contact: {CONTACT_AGE} ago

Please confirm status. If operating normally, respond with current location.

If no response in 30 minutes, this will be escalated.
```

### Step 3: Check Pending Concerns

Review any flagged items that need attention:

```yaml
# From SOUL.md
concerns:
  - type: fuel_anomaly
    date: "2024-01-14"
    description: "Consumption 35 L/hr vs normal 28 L/hr"
    status: pending
  - type: maintenance_due
    date: "2024-01-20"
    description: "500-hour service at 13000 hours"
    status: upcoming
```

For each pending concern older than 24 hours without resolution:
- Post reminder to operator
- If older than 72 hours, notify supervisor

### Step 4: Verify Communication Channels

Test that Redis communication is working:

```bash
# Test Redis connectivity
redis-cli -u "$REDIS_URL" PING
# Expected: PONG

# Test write capability
redis-cli -u "$REDIS_URL" SET "fleet:test:${ASSET_ID}" "ok" EX 60
redis-cli -u "$REDIS_URL" GET "fleet:test:${ASSET_ID}"
redis-cli -u "$REDIS_URL" DEL "fleet:test:${ASSET_ID}"
```

If Redis connection fails:
1. Log the failure
2. Retry 3 times with 30-second intervals
3. If still failing, operate in degraded mode (see fleet-comms skill)

### Step 5: Post Status Update

Publish current status to Redis key with 8-hour TTL:

```bash
redis-cli -u "$REDIS_URL" SET "fleet:status:${ASSET_ID}" "$(cat <<EOF
{
  "asset_id": "$ASSET_ID",
  "status": "$CURRENT_STATUS",
  "last_update": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "location": "$LOCATION",
  "hour_meter": $HOUR_METER,
  "fuel_pct": $FUEL_PCT,
  "data_freshness": {
    "gps_hours": $GPS_AGE_HOURS,
    "fuel_hours": $FUEL_AGE_HOURS,
    "operator_hours": $OPERATOR_AGE_HOURS
  },
  "concerns": $CONCERN_COUNT,
  "notes": "$NOTES"
}
EOF
)" EX 28800
```

The 8-hour TTL (`EX 28800`) ensures FC treats the asset as offline if no update is received.

Also publish a heartbeat event:

```bash
redis-cli -u "$REDIS_URL" LPUSH "fleet:events" "$(cat <<EOF
{
  "asset_id": "$ASSET_ID",
  "event_type": "activity",
  "activity_type": "heartbeat",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)"
redis-cli -u "$REDIS_URL" LTRIM "fleet:events" 0 99
```

### Step 6: Log Check Results

Append to `memory/YYYY-MM-DD.md`:

```markdown
## Health Check - HH:MM

- **Status:** {STATUS}
- **Hour meter:** {HOURS}
- **Data freshness:**
  - GPS: {AGE} ({STATUS})
  - Fuel: {AGE} ({STATUS})
  - Operator: {AGE} ({STATUS})
- **Concerns:** {COUNT} pending
- **Communication:** {STATUS}
- **Flags:** {ANY_FLAGS}
```

## Status Determination

Set status based on check results (always lowercase):

| Condition | Status |
|-----------|--------|
| All checks pass, minor flags | `operational` |
| Operating without tracking, comms failure, critical concern, scheduled service | `maintenance` |
| Available but not working | `idle` |

## Check Intervals

| Check Type | Interval | Purpose |
|------------|----------|---------|
| Full self-check | 4 hours | Comprehensive health |
| Heartbeat | 15 minutes | Communication alive |
| Freshness scan | 1 hour | Early staleness detection |

## Manual Health Check

When operator requests health check:

```
User: "run health check" / "check status" / "how am I doing"

Response:
📋 Health Check - {TIME}

Status: {STATUS}

Data Freshness:
  ✓ GPS: Updated 15 minutes ago
  ✓ Fuel: Logged 3 hours ago
  ⚠ Operator: Last contact 7 hours ago

Hour Meter: {HOURS}
Fuel Estimate: {PCT}%

Pending Concerns: {COUNT}
{CONCERN_LIST_IF_ANY}

Communication: ✓ Online
```

## Fleet Coordinator Integration

FC reads your status directly from `fleet:status:{ASSET_ID}` via scan and GET. Update your status:
- After each 4-hour health check (automatic)
- When status changes (operational to maintenance, etc.)
- When requested by operator

The 8-hour TTL means you must update at least once per 8 hours to remain visible to FC.

## Escalation Triggers

The asset-monitor will trigger escalation for:

| Condition | Trigger | Severity |
|-----------|---------|----------|
| Operating without tracking >4 hours | `operating_without_tracking` | HIGH |
| No operator contact >24 hours | `operator_unreachable` | MEDIUM |
| Redis connection failed >2 hours | `communication_failure` | MEDIUM |
| Critical concern unaddressed >24 hours | `unaddressed_concern` | Based on concern |

## Recovery Actions

### GPS Data Restored
```markdown
✓ GPS tracking restored

  Previous gap: {DURATION}
  Current location: {COORDINATES}

Operating-without-tracking flag cleared.
```

### Operator Contact Restored
```markdown
✓ Operator contact restored

  Previous gap: {DURATION}

Status updated to OPERATIONAL.
```

### Communication Restored
```markdown
✓ Fleet communication restored

  Downtime: {DURATION}

Sending missed status updates...
```
