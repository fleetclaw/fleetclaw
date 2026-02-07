---
name: fleet-coordinator
description: Status aggregation, hourly summaries, and daily reports for fleet oversight
metadata: {"openclaw":{"requires":{"bins":[],"env":["REDIS_URL"]}}}
---

# Fleet Coordinator

The Fleet Coordinator (FC) aggregates status from all assets, generates periodic summaries, and provides fleet-wide oversight. The FC runs as a dedicated OpenClaw agent with its own workspace.

## When to Use

- **Hourly**: Generate and post fleet status summary
- **Daily**: Generate end-of-day fleet report
- **On request**: Answer queries about fleet status
- **On alert**: Process alerts from the event stream

## Status Collection

### Read All Asset Status Keys

To get current status from all assets, scan for status keys:

```bash
# Get all status keys
redis-cli -u "$REDIS_URL" --scan --pattern "fleet:status:*"
```

Then read each key:

```bash
# Get specific asset status
redis-cli -u "$REDIS_URL" GET "fleet:status:FRT81"
```

### Batch Status Collection

For fleet-wide status, iterate over known assets or scan:

```bash
# Scan and read all status keys
for key in $(redis-cli -u "$REDIS_URL" --scan --pattern "fleet:status:*"); do
    echo "=== $key ==="
    redis-cli -u "$REDIS_URL" GET "$key"
done
```

### Detecting Offline Assets

Assets are offline if their status key is missing (expired keys are auto-deleted by Redis):

```bash
# Check if asset is online (1=yes, 0=no)
redis-cli -u "$REDIS_URL" EXISTS "fleet:status:FRT81"

# Seconds until offline (-2 if already offline)
redis-cli -u "$REDIS_URL" TTL "fleet:status:FRT81"
```

### Store Status Locally

Cache collected status in memory for reporting:

```yaml
# memory/fleet-status.yaml
assets:
  FRT81:
    status: operational
    hour_meter: 12849
    fuel_pct: 65
    last_update: "2026-02-04T10:00:00Z"
  FRT83:
    status: operational
    hour_meter: 8523
    fuel_pct: 45
    last_update: "2026-02-04T10:01:00Z"
  LD-001:
    status: offline
    last_known_update: "2026-02-04T06:00:00Z"
```

## Event Stream Monitoring

Read events from the `fleet:events` list:

```bash
# Get all recent events (newest first)
redis-cli -u "$REDIS_URL" LRANGE "fleet:events" 0 -1

# Get last 10 events
redis-cli -u "$REDIS_URL" LRANGE "fleet:events" 0 9

# Get events 10-20 (for pagination)
redis-cli -u "$REDIS_URL" LRANGE "fleet:events" 10 19
```

### Event Types to Monitor

| Event Type | Action |
|------------|--------|
| `alert` | Log and assess severity for routing |
| `fuel_log` | Update activity tracking |
| `pre_op` | Update activity tracking |
| `maintenance_start` | Update asset status cache |
| `maintenance_complete` | Update asset status cache |
| `status_change` | Update asset status cache |
| `reconnected` | Note reconnection, check for missed data |

### Alert Processing

When processing events, filter for alerts and route by severity:

```bash
# Get events and filter for alerts (each line is a separate JSON object)
redis-cli -u "$REDIS_URL" LRANGE "fleet:events" 0 99 | while read -r line; do
    if echo "$line" | jq -e '.event_type == "alert"' > /dev/null 2>&1; then
        echo "$line" | jq -c '.'
    fi
done
```

### Alert Routing

| Severity | Action |
|----------|--------|
| `info` | Log only |
| `low` | Post to channel |
| `medium` | Post to channel + tag relevant parties |
| `high` | Post + DM supervisor |
| `critical` | Post + trigger escalation chain |

## Hourly Summary

Every hour, generate and post a fleet summary.

### Aggregation Steps

1. **Scan status keys** using `--scan --pattern "fleet:status:*"`
2. **GET each status** and parse JSON
3. **Identify offline assets** (missing keys or expired TTL)
4. **Count by status category**:
   - Operational
   - Idle
   - Maintenance
   - Offline
5. **Identify concerns**:
   - Low fuel (<20%)
   - Approaching maintenance
   - Recent alerts in event stream
   - Offline assets that were recently operational

### Summary Format

Post to #fleet-coordination channel:

```
Fleet Status - 10:00

Operational: 8 | Idle: 2 | Maintenance: 1 | Offline: 0

Excavators:
  EX-001: OK 12849h, 65% fuel
  EX-002: OK 9823h, 80% fuel
  EX-003: LOW FUEL 11502h, 15% fuel

Haul Trucks:
  RT-001: OK 8523h, 45% fuel
  HT-044: OK 7891h, 70% fuel
  HT-045: MAINTENANCE

Concerns:
  - EX-003: Low fuel (15%)
  - LD-001: Offline (no status key)
```

## Daily Report

At end of shift (configurable time), generate comprehensive daily report.

### Report Sections

1. **Fleet Overview**
   - Total assets by status
   - Hours worked across fleet
   - Fuel consumed across fleet

2. **Production Summary**
   - Total loads by material type
   - Tonnage moved (if tracked)
   - Cycle times and efficiency

3. **Fuel Summary**
   - Total fuel consumed
   - Consumption rates by asset
   - Anomalies flagged

4. **Maintenance**
   - Completed maintenance
   - Upcoming services
   - Unplanned downtime

5. **Issues & Escalations**
   - Alerts from event stream
   - Escalations triggered
   - Resolution status

6. **Data Quality**
   - Assets that went offline
   - Duration of offline periods
   - Missing fuel logs

### Daily Report Format

```markdown
# Fleet Daily Report - 2026-02-04

## Overview
| Metric | Value |
|--------|-------|
| Assets Tracked | 12 |
| Operational Hours | 156.5 |
| Fuel Consumed | 4,850 L |
| Loads Completed | 89 |

## Fleet Status at Close
- Operational: 10
- Maintenance: 1
- Offline: 1

## Production
| Asset | Hours | Loads | Fuel (L) | L/hr |
|-------|-------|-------|----------|------|
| EX-001 | 14.5 | 28 | 406 | 28.0 |
| EX-002 | 12.0 | 24 | 336 | 28.0 |
| RT-001 | 13.5 | - | 270 | 20.0 |
...

## Fuel Anomalies
- EX-003: Consumption 35.2 L/hr (normal: 28 L/hr) - FLAGGED

## Maintenance
### Completed
- HT-045: 500-hour service (4 hours downtime)

### Upcoming (next 7 days)
- EX-001: 1000-hour service at 13000h (151h remaining)

## Issues
- 10:15: EX-003 alert - hydraulic pressure warning (resolved 10:45)

## Data Quality
- LD-001: Offline 06:00-14:00 (8 hours)
- No fuel log from FRT82 (>24h gap)
```

## Answering Fleet Queries

When asked about the fleet (in chat or via query):

### "What's the fleet status?"

1. Scan all `fleet:status:*` keys
2. GET each status
3. Aggregate counts
4. Report summary with any concerns

```bash
# Quick fleet overview (single GET per asset)
echo "=== Fleet Status ==="
for key in $(redis-cli -u "$REDIS_URL" --scan --pattern "fleet:status:*"); do
    data=$(redis-cli -u "$REDIS_URL" GET "$key")
    asset=$(echo "$data" | jq -r '.asset_id')
    status=$(echo "$data" | jq -r '.status')
    concerns=$(echo "$data" | jq -r '.concerns // 0')
    if [ "$concerns" -gt 0 ]; then
        echo "$asset: $status ($concerns concerns)"
    else
        echo "$asset: $status"
    fi
done
```

### "How is FRT81 doing?"

1. GET the specific status key
2. Parse and report status
3. Check event stream for recent activity

```bash
# Get specific asset status
redis-cli -u "$REDIS_URL" GET "fleet:status:FRT81"

# Check TTL (freshness)
redis-cli -u "$REDIS_URL" TTL "fleet:status:FRT81"

# Recent events for this asset (each line is a separate JSON object)
redis-cli -u "$REDIS_URL" LRANGE "fleet:events" 0 99 | while read -r line; do
    if echo "$line" | jq -e '.asset_id == "FRT81"' > /dev/null 2>&1; then
        echo "$line" | jq -c '.'
    fi
done
```

### "Show fuel consumption today"

1. Read cached status for fuel percentages
2. Cross-reference with event stream for fuel_log events
3. Present comparison table

### "Any issues in the last hour?"

1. Read `fleet:events` list
2. Filter for alerts and issues by timestamp
3. Report issues and their status

```bash
# Get recent alert events (each line is a separate JSON object)
redis-cli -u "$REDIS_URL" LRANGE "fleet:events" 0 49 | while read -r line; do
    if echo "$line" | jq -e '.event_type == "alert"' > /dev/null 2>&1; then
        echo "$line" | jq -c '.'
    fi
done
```

## Offline Detection

Every status check, identify offline assets:

```
For each known asset:
  if key "fleet:status:{id}" does not exist:
    Mark as OFFLINE
    if asset was previously OPERATIONAL:
      Log: "Asset {id} went offline"
      Check last known status from cache
```

Assets with expired keys (TTL reached) are automatically cleaned up by Redis. The 8-hour TTL means any asset not updating for 8 hours is considered offline.

## Fleet Commands

FC can issue fleet-wide commands via the event stream. Assets check for commands during their heartbeat cycle.

### Emergency Stop

```bash
redis-cli -u "$REDIS_URL" LPUSH "fleet:events" "$(cat <<EOF
{
  "asset_id": "FLEET-COORD",
  "event_type": "command",
  "command": "emergency_stop",
  "message": "Site evacuation - all equipment stop immediately",
  "severity": "critical",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)"
redis-cli -u "$REDIS_URL" LTRIM "fleet:events" 0 99
```

### Shift Change Notice

```bash
redis-cli -u "$REDIS_URL" LPUSH "fleet:events" "$(cat <<EOF
{
  "asset_id": "FLEET-COORD",
  "event_type": "command",
  "command": "shift_change",
  "message": "Shift change in 30 minutes",
  "severity": "info",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)"
redis-cli -u "$REDIS_URL" LTRIM "fleet:events" 0 99
```

### Command Types

| Command | Severity | Expected Action |
|---------|----------|-----------------|
| `emergency_stop` | critical | Immediate safe shutdown |
| `shutdown_notice` | high | Acknowledge and prepare |
| `shift_change` | info | Log current status |
| `notice` | info | Read and acknowledge |

For critical commands, also send via Telegram for immediate visibility since assets only check events during heartbeat cycles.
