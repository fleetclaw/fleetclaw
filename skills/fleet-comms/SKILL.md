---
name: fleet-comms
description: Redis commands for publishing and reading asset status
metadata: {"openclaw":{"requires":{"bins":["redis-cli"],"env":[]}}}
---

# Fleet Communications

Publish your status to Redis so Fleet Coordinator can monitor the fleet.

## Prerequisites

- `redis-cli` available in container
- Redis accessible at hostname `redis`

## Publishing Your Status

Run this command to publish your current status:

```bash
redis-cli -h redis SET "fleet:status:ASSET_ID" '{"asset_id":"ASSET_ID","status":"operational","last_update":"2026-02-04T12:00:00Z"}' EX 28800
```

### Example: EXC99

```bash
redis-cli -h redis SET "fleet:status:EXC99" '{"asset_id":"EXC99","status":"operational","last_update":"2026-02-04T12:00:00Z"}' EX 28800
```

### Example: RCK11

```bash
redis-cli -h redis SET "fleet:status:RCK11" '{"asset_id":"RCK11","status":"operational","last_update":"2026-02-04T14:30:00Z"}' EX 28800
```

### How to Use

1. Copy the example command above
2. Replace `ASSET_ID` with your asset ID (check your IDENTITY.md)
3. Replace the timestamp with current UTC time
4. Replace `operational` with your actual status
5. Run the command

### Status Values

| Status | When to Use |
|--------|-------------|
| `operational` | Normal operations |
| `idle` | No current activity |
| `maintenance` | Under maintenance |
| `offline` | Shutting down |

The `EX 28800` sets an 8-hour TTL. If you don't publish within 8 hours, your status key expires.

## Reading Another Asset's Status

```bash
redis-cli -h redis GET "fleet:status:EXC99"
```

## Checking Your Own Status

```bash
redis-cli -h redis GET "fleet:status:RCK11"
```

## Verifying TTL

Check how long until your status expires:

```bash
redis-cli -h redis TTL "fleet:status:RCK11"
```

Returns seconds remaining (max 28800 = 8 hours).

## Publishing Events

Push important events to the fleet event stream:

```bash
redis-cli -h redis LPUSH "fleet:events" '{"asset_id":"RCK11","event_type":"fuel_log","timestamp":"2026-02-04T14:30:00Z"}'
redis-cli -h redis LTRIM "fleet:events" 0 99
```

Always run both commands together. LTRIM keeps the list capped at 100 events.

## Quick Reference

| Action | Command |
|--------|---------|
| Publish status | `redis-cli -h redis SET "fleet:status:ID" 'JSON' EX 28800` |
| Read status | `redis-cli -h redis GET "fleet:status:ID"` |
| Check TTL | `redis-cli -h redis TTL "fleet:status:ID"` |
| Push event | `redis-cli -h redis LPUSH "fleet:events" 'JSON'` |
| Cap events | `redis-cli -h redis LTRIM "fleet:events" 0 99` |

## Troubleshooting

**Connection refused**: Redis container may not be running. Check with `redis-cli -h redis PING` (should return `PONG`).

**Key not found**: Status expired or never published. Publish a new status.
