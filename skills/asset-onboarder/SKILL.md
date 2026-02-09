---
name: asset-onboarder
description: Onboard new assets into the fleet — create user, install agent, configure services, update fleet.md
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Asset Onboarder

_Accept new asset details from leadership, set up the agent, and bring it online._

## Trigger

- **Message** — A manager or owner requests adding a new asset (e.g., "add new CAT 390F, ID EX-005, serial CAT0390F5DEF67890")

## Input

- **User messages:** Natural language asset details from leadership
- **fleet.md:** Check Active and Idle sections for asset ID conflicts

## Behavior

When a manager or owner requests a new asset:

### Gather required details

Two pieces of information are required: asset ID and serial number. Extract them from the natural language message. People say things like "add new CAT 390F, we'll call it EX-005, serial CAT0390F5DEF67890" or "onboard a Komatsu PC200, ID KOM05, serial KOM200ABC123."

If either is missing, ask once. Be specific about what you need: "Got the serial. What ID should this asset use?"

### Validate the asset ID

Check fleet.md Active and Idle sections to confirm the proposed asset ID does not already exist. If it conflicts, tell the user and ask for a different ID. Do not silently overwrite an existing asset.

### Onboarding sequence

Once validated, the following steps bring the new asset agent online. Reference `docs/implementation.md` and `platform/{os}.md` for OS-specific commands.

1. **Create a system user** for the new asset (e.g., `fc-{id}` with the ID lowercased). The user should be a member of the `fc-agents` group. No login shell needed.

2. **Install OpenClaw** as that user. Follow the standard OpenClaw installation process for the platform.

3. **Run `openclaw onboard --install-daemon`** to initialize the OpenClaw workspace and install the background service.

4. **Inject FleetClaw customizations** into the agent's workspace:
   - Copy the SOUL.md template from `templates/soul-asset.md`, substituting `{ASSET_ID}` and `{SERIAL}` with the actual values
   - Create `inbox/` and `outbox/` directories in the workspace
   - Mount or copy the appropriate skills (fuel-logger, meter-reader, pre-op, issue-reporter, nudger, memory-curator-asset)
   - Tune `openclaw.json` settings: `bootstrapMaxChars: 15000`, heartbeat interval, shift configuration

5. **Set file permissions** using the platform's ACL mechanism. The asset agent user needs read/write on its own workspace. Clawvisor needs read access to this agent's outbox/ and state.md, and write access to its inbox/. See `docs/permissions.md` for the specific ACL rules.

6. **Create and start the agent service** using the platform's service manager. The service runs OpenClaw as the asset agent's system user.

7. **Update fleet.md** — add the new asset ID to the Active section with today's date.

8. **Remind user about messaging channel configuration.** The new agent needs its own messaging channel token/configuration to function. After confirming the service is running, remind the user to configure the agent's messaging channel credentials in the environment file.

### Confirm to user

Respond with the full details of what was created: asset ID, serial, that the agent is registered and the service is running. If there were any issues (service not starting, token reminder), include those notes.

## Output

- **fleet.md updates:** Add the new asset ID to the Active section.
- **state.md:** Initialize the new asset's state.md with `status: active`.
- **Process management:** Create and start the agent service.
- **MEMORY.md updates:** Add to Recent Actions (date, asset ID, serial). Update Fleet Composition counts.
- **Messages to user:** Confirmation with asset details, service status, and messaging channel configuration reminder.
