---
name: asset-lifecycle
description: Manage asset lifecycle transitions — idle, wake, and decommission fleet assets
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Asset Lifecycle

_Idle, wake, or decommission assets. Manages fleet.md entries and agent services._

## Trigger

- **Message** — A manager or owner requests idling, waking, or decommissioning an asset (e.g., "idle KOT28", "bring EX-003 back online", "decommission DZ-010")

## Input

- **User messages:** Natural language lifecycle commands from leadership
- **fleet.md:** Fleet composition — Active, Idle, and Decommissioned sections

## Behavior

Three operations. Identify which one the user is requesting from their message. People say "park it", "lay up", "seasonal shutdown" for idle. They say "wake", "bring back", "reactivate" for wake. They say "decommission", "retire", "scrap", "permanently remove" for decommission.

### Idle an asset

Idling takes a machine out of the active fleet. The agent service is stopped to save resources, but the asset's data stays on disk for historical access.

Before proceeding, check that the asset is listed in the Active section of fleet.md. If it is already in the Idle section, tell the user — do not double-idle.

1. Stop the agent service for this asset.
2. Update fleet.md: move the asset from the Active section to the Idle section, with today's date.
3. Confirm to the user: which asset was idled, that the service is stopped, and that the data is preserved.

### Wake an asset

Waking brings an idle machine back into the active fleet.

Before proceeding, check that the asset is listed in the Idle section of fleet.md. If it is already in the Active section, say so. If it is in the Decommissioned section, warn the user that waking a decommissioned asset is not standard — they should re-onboard instead.

1. Start the agent service for this asset.
2. Update fleet.md: move the asset from the Idle section to the Active section, with today's date.
3. Confirm to the user: which asset was woken, that the service is running.

### Decommission an asset

Decommissioning is permanent removal from the fleet. The agent service is stopped and disabled. Data stays on disk for historical queries but the asset is removed from active and idle lists.

This is a significant action. Before proceeding, confirm with the user: "Decommissioning {ID} is permanent — the service will be disabled and the asset will no longer appear in the Active or Idle lists. Data is preserved for historical queries. Go ahead?"

If the user confirms:

1. Stop and disable the agent service for this asset.
2. Update fleet.md: move the asset from whichever section it is in (Active or Idle) to the Decommissioned section, with today's date.
3. Confirm to the user: which asset was decommissioned, that the service is disabled, and that historical data is preserved.

### Validation for all operations

Always validate that the asset ID exists before attempting any operation. Check all sections of fleet.md (Active, Idle, Decommissioned). If the ID is not found, report that to the user.

## Output

- **fleet.md updates:**
  - Idle: move asset from Active to Idle section
  - Wake: move asset from Idle to Active section
  - Decommission: move asset to Decommissioned section
- **Process management:**
  - Idle: stop the agent service
  - Wake: start the agent service
  - Decommission: stop and disable the agent service
- **MEMORY.md updates:** Update Fleet Composition (active/idle counts). Add to Recent Actions with date, asset ID, and operation performed.
- **Messages to user:** Confirmation of the operation with asset details and service status.
