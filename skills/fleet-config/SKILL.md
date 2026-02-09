---
name: fleet-config
description: Manage skill deployment across the fleet — track what is mounted where and handle deployment requests
metadata: {"openclaw":{"requires":{"bins":["redis-cli","docker"],"env":["REDIS_URL"]}}}
---

# Fleet Config

_Track skill deployment across the fleet. Deploy, remove, or query which skills are mounted on which agents._

## Trigger

- **Message** — Leadership wants to deploy or remove a skill (e.g., "add tire-pressure skill to all excavators", "remove gamification from KOT28", "what skills does EX-001 have?")

## Input

- **User messages:** Skill deployment requests or queries from managers or owners
- **Redis keys:**
  - `fleet:index:active` — active asset IDs (for fleet-wide deployment)
- **MEMORY.md:** Skill Deployment State section (current mapping of skills to agents)

## Behavior

### Querying current deployment

When leadership asks "what skills does EX-001 have?" or "what's deployed to the excavators?", answer from the Skill Deployment State in MEMORY.md. This section tracks what skills are mounted to each agent type and any per-asset exceptions.

If the deployment state in MEMORY.md is empty or stale, note that. The authoritative source is the docker-compose.yml volume mounts, but Clawordinator tracks the desired state in memory.

### Deploying a skill

When leadership requests deploying a skill ("add tire-pressure to all excavators"):

1. **Validate the skill exists.** Check whether the skill directory is present in the skills volume. If the skill name is not recognized, tell the user and ask them to confirm the exact name.

2. **Determine scope.** Same patterns as fleet-director: all active assets, or specific asset IDs (resolve category references to IDs from the active index). Ask once if the scope is unclear.

3. **Update MEMORY.md.** Record the desired change in the Skill Deployment State section: which skill, which agents, when the change was requested.

4. **Provide deployment instructions.** In Tier 1, skill mounts are defined in docker-compose.yml. The user (or generate-configs.py) needs to update the compose file. Provide the specific volume mount line they need to add to each affected service:

   `./skills/{skill-name}:/app/skills/{skill-name}:ro`

5. **Restart affected containers.** If the compose file has already been updated (or if the user confirms the update is done), restart the affected containers so they pick up the new skill mount. For each affected asset: `docker restart fc-agent-{id}`.

   If restarting multiple containers, note that this will briefly interrupt those agents. Ask the user if they want to proceed, or if they prefer to wait for a maintenance window.

### Removing a skill

When leadership requests removing a skill ("remove gamification from KOT28"):

1. **Confirm the removal.** "Removing {skill-name} from {scope} — the agent will no longer have that behavior after restart. Go ahead?"

2. **Update MEMORY.md.** Remove the skill from the Skill Deployment State for the affected agents.

3. **Provide instructions.** The volume mount line for that skill needs to be removed from docker-compose.yml for the affected services.

4. **Restart affected containers** after the compose file is updated.

### Tier 1 limitations

In Tier 1, skill deployment is a compose-file operation. Clawordinator cannot hot-swap skills without a container restart. This skill tracks the desired state and provides the instructions and container restarts. It does not modify docker-compose.yml directly — that is a file the user or generate-configs.py manages.

For organizations that want hot-reload (Tier 2), a custom mechanism would need to be built. This skill's tracking of deployment state is the foundation for that.

### Keeping deployment state accurate

When any skill deployment change is made, update the Skill Deployment State in MEMORY.md immediately. This section should reflect the current truth of what is deployed. If the user reports that something is out of sync ("EX-001 has tire-pressure but your records don't show it"), update MEMORY.md to match reality.

## Output

- **MEMORY.md updates:** Update Skill Deployment State with skill additions or removals. Add to Recent Actions with date, skill name, scope, and operation (deployed/removed).
- **Docker:** `docker restart fc-agent-{id}` for affected containers after compose changes.
- **Messages to user:** Current deployment state when queried. Deployment instructions with specific volume mount lines. Confirmation of changes and restart status.
