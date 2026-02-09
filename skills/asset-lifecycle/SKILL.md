---
name: asset-lifecycle
description: Manage asset lifecycle transitions — idle, wake, and decommission fleet assets
metadata: {"openclaw":{"requires":{"bins":["redis-cli","docker"],"env":["REDIS_URL"]}}}
---

# Asset Lifecycle

_Idle, wake, or decommission assets. Manages Redis indexes, lifecycle records, and Docker containers._

## Trigger

- **Message** — A manager or owner requests idling, waking, or decommissioning an asset (e.g., "idle KOT28", "bring EX-003 back online", "decommission DZ-010")

## Input

- **User messages:** Natural language lifecycle commands from leadership
- **Redis keys:**
  - `fleet:index:active` — active asset IDs
  - `fleet:index:idle` — idle asset IDs
  - `fleet:asset:{ID}:lifecycle` — current lifecycle state
  - `fleet:asset:{ID}:state` — current operational state

## Behavior

Three operations. Identify which one the user is requesting from their message. People say "park it", "lay up", "seasonal shutdown" for idle. They say "wake", "bring back", "reactivate" for wake. They say "decommission", "retire", "scrap", "permanently remove" for decommission.

### Idle an asset

Idling takes a machine out of the active fleet. The container is stopped to save resources, but the asset's data stays in Redis for historical access.

Before proceeding, check that the asset is currently in `fleet:index:active`. If it is already idle, tell the user — do not double-idle.

1. Remove the asset ID from the active index and add it to the idle index.
2. Update the lifecycle HASH: state "idle", since today's date, changed_by "clawordinator."
3. Stop the container: `docker stop fc-agent-{id}`.
4. Confirm to the user: which asset was idled, that the container is stopped, and that the data is preserved.

### Wake an asset

Waking brings an idle machine back into the active fleet.

Before proceeding, check that the asset is currently in `fleet:index:idle`. If it is already active, say so. If it is decommissioned, warn the user that waking a decommissioned asset is not standard — they should re-onboard instead.

1. Remove the asset ID from the idle index and add it to the active index.
2. Update the lifecycle HASH: state "active", since today's date, changed_by "clawordinator."
3. Start the container: `docker start fc-agent-{id}`.
4. Confirm to the user: which asset was woken, that the container is running.

### Decommission an asset

Decommissioning is permanent removal from the fleet. The container is stopped and removed. Data stays in Redis for historical queries but the asset is removed from all indexes.

This is a significant action. Before proceeding, confirm with the user: "Decommissioning {ID} is permanent — the container will be removed and the asset will no longer appear in fleet indexes. Data is preserved for historical queries. Go ahead?"

If the user confirms:

1. Remove the asset ID from whichever index it is in (active or idle).
2. Update the lifecycle HASH: state "decommissioned", since today's date, changed_by "clawordinator."
3. Stop and remove the container: `docker stop fc-agent-{id}` then `docker rm fc-agent-{id}`.
4. Confirm to the user: which asset was decommissioned, that the container is removed, and that historical data is preserved in Redis.

### Validation for all operations

Always validate that the asset ID exists before attempting any operation. Check both `fleet:index:active` and `fleet:index:idle`. If the ID is not found in either, check the lifecycle HASH — it may be decommissioned. Report what you find to the user.

## Output

- **Redis writes:**
  ```
  # Idle
  SREM fleet:index:active {ID}
  SADD fleet:index:idle {ID}
  HSET fleet:asset:{ID}:lifecycle state "idle" since "{DATE}" changed_by "clawordinator"

  # Wake
  SREM fleet:index:idle {ID}
  SADD fleet:index:active {ID}
  HSET fleet:asset:{ID}:lifecycle state "active" since "{DATE}" changed_by "clawordinator"

  # Decommission
  SREM fleet:index:active {ID}   (or fleet:index:idle)
  HSET fleet:asset:{ID}:lifecycle state "decommissioned" since "{DATE}" changed_by "clawordinator"
  ```
- **Docker:**
  - Idle: `docker stop fc-agent-{id}`
  - Wake: `docker start fc-agent-{id}`
  - Decommission: `docker stop fc-agent-{id}` then `docker rm fc-agent-{id}`
- **MEMORY.md updates:** Update Fleet Composition (active/idle counts). Add to Recent Actions with date, asset ID, and operation performed.
- **Messages to user:** Confirmation of the operation with asset details and container status.
