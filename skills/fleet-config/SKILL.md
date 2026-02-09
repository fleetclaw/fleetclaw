---
name: fleet-config
description: Manage skill deployment across the fleet — track what is mounted where and handle deployment requests
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Fleet Config

_Track skill deployment across the fleet. Deploy, remove, or query which skills are mounted on which agents._

## Trigger

- **Message** — Leadership wants to deploy or remove a skill (e.g., "add tire-pressure skill to all excavators", "remove gamification from KOT28", "what skills does EX-001 have?")

## Input

- **User messages:** Skill deployment requests or queries from managers or owners
- **fleet.md:** Active asset list (for fleet-wide deployment scope)
- **MEMORY.md:** Skill Deployment State section (current mapping of skills to agents)

## Behavior

### Querying current deployment

When leadership asks "what skills does EX-001 have?" or "what's deployed to the excavators?", answer from the Skill Deployment State in MEMORY.md. This section tracks what skills are mounted to each agent role (asset, clawvisor, clawordinator) and any per-asset exceptions.

If the deployment state in MEMORY.md is empty or stale, note that. The authoritative source is each agent's skill directory, but Clawordinator tracks the desired state in memory.

### Deploying a skill

When leadership requests deploying a skill ("add tire-pressure to all excavators"):

1. **Validate the skill exists.** Check whether the skill directory is present in the shared skills location. If the skill name is not recognized, tell the user and ask them to confirm the exact name.

2. **Determine scope.** Same patterns as fleet-director: all active assets, or specific asset IDs (resolve category references to IDs from fleet.md). Ask once if the scope is unclear.

3. **Update MEMORY.md.** Record the desired change in the Skill Deployment State section: which skill, which agents, when the change was requested.

4. **Deploy the skill files.** Copy or symlink the skill directory into each affected agent's skills location so the agent can read it.

5. **Restart affected agent services.** After the skill files are in place, restart the affected agent services so they pick up the new skill. If restarting multiple services, note that this will briefly interrupt those agents. Ask the user if they want to proceed, or if they prefer to wait for a maintenance window.

### Removing a skill

When leadership requests removing a skill ("remove gamification from KOT28"):

1. **Confirm the removal.** "Removing {skill-name} from {scope} — the agent will no longer have that behavior after restart. Go ahead?"

2. **Update MEMORY.md.** Remove the skill from the Skill Deployment State for the affected agents.

3. **Remove the skill files.** Remove the skill directory (or unlink the symlink) from each affected agent's skills location.

4. **Restart affected agent services** after the skill files are removed.

### Keeping deployment state accurate

When any skill deployment change is made, update the Skill Deployment State in MEMORY.md immediately. This section should reflect the current truth of what is deployed. If the user reports that something is out of sync ("EX-001 has tire-pressure but your records don't show it"), update MEMORY.md to match reality.

## Output

- **MEMORY.md updates:** Update Skill Deployment State with skill additions or removals. Add to Recent Actions with date, skill name, scope, and operation (deployed/removed).
- **Process management:** Restart affected agent services after skill deployment changes.
- **Messages to user:** Current deployment state when queried. Confirmation of changes and restart status.
