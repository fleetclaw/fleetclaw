---
name: asset-onboarder
description: Onboard new assets into the fleet — register in Redis, initialize state, start container
metadata: {"openclaw":{"requires":{"bins":["redis-cli","docker"],"env":["REDIS_URL"]}}}
---

# Asset Onboarder

_Accept new asset details from leadership, register the asset in Redis, and bring its agent container online._

## Trigger

- **Message** — A manager or owner requests adding a new asset (e.g., "add new CAT 390F, ID EX-005, serial CAT0390F5DEF67890")

## Input

- **User messages:** Natural language asset details from leadership
- **Redis keys:**
  - `fleet:index:active` — check for ID conflicts
  - `fleet:index:idle` — check for ID conflicts (asset may have been idled previously)
  - `fleet:index:type:{ASSET_TYPE}` — current type groupings

## Behavior

When a manager or owner requests a new asset:

### Gather required details

Three pieces of information are required: asset ID, equipment type, and serial number. Extract them from the natural language message. People say things like "add new CAT 390F, we'll call it EX-005, serial CAT0390F5DEF67890" or "onboard a Komatsu PC200, ID KOM05, serial KOM200ABC123."

If any of the three are missing, ask once. Be specific about what you need: "Got the serial and type. What ID should this asset use?"

Equipment type should be normalized to a short category: excavator, haul_truck, loader, dozer, grader, drill, water_cart, or whatever fits. If uncertain, ask the user to confirm.

### Validate the asset ID

Check `fleet:index:active` and `fleet:index:idle` to confirm the proposed asset ID does not already exist. If it conflicts, tell the user and ask for a different ID. Do not silently overwrite an existing asset.

### Register in Redis

Once validated, perform the following registrations:

1. Add the asset ID to the active index so Clawvisor and other skills can discover it.
2. Add the asset ID to the appropriate type index for type-scoped queries.
3. Initialize the lifecycle HASH with state "active", today's date, and changed_by "clawordinator."
4. Initialize the state HASH with status "active" so the new agent has a baseline state record.

### Start the agent container

The container name follows the convention `fc-agent-{ID}` with the ID lowercased. Run `docker compose up -d fc-agent-{id}` to create and start the container.

This requires the service to already be defined in docker-compose.yml. If it is not (runtime addition), remind the user that `generate-configs.py` needs to be re-run to add the service definition, or they can manually add the service block.

### Telegram bot token reminder

The new agent container needs its own Telegram bot token to function. After confirming the container is up, remind the user: "Make sure `TELEGRAM_TOKEN_{ID}` is set in .env. The agent won't connect to Telegram without it."

### Confirm to user

Respond with the full details of what was created: asset ID, type, serial, that it was registered in Redis and the container is running. If there were any issues (compose service missing, token reminder), include those notes.

## Output

- **Redis writes:**
  ```
  SADD fleet:index:active {ID}
  SADD fleet:index:type:{TYPE} {ID}

  HSET fleet:asset:{ID}:lifecycle \
    state "active" \
    since "{DATE}" \
    changed_by "clawordinator"

  HSET fleet:asset:{ID}:state \
    status "active"
  ```
- **Docker:** `docker compose up -d fc-agent-{id}`
- **MEMORY.md updates:** Add to Recent Actions (date, asset ID, type, serial). Update Fleet Composition counts and type breakdown.
- **Messages to user:** Confirmation with asset details, container status, and Telegram token reminder.
