# Customizing FleetClaw

Every organization is different. FleetClaw provides defaults that work out of the box, but most deployments will need customization. This guide covers the extension points.

## Writing custom skills

The most common customization. Organizations add skills for their specific operations:

- **Tire pressure logger** — Track tire pressures for haul trucks
- **Blast log** — Record blast events and vibration measurements
- **Payload tracker** — Log payload weights from scale systems
- **Water cart logger** — Track water usage for dust suppression
- **Drill log** — Record drill depths, rates, and bit changes

To write a custom skill:

1. Copy `skills/SKILL-TEMPLATE.md` to `skills/{your-skill-name}/SKILL.md`
2. Fill in the frontmatter (name, description, any required bins or env variables)
3. Write Trigger, Input, Behavior, Output sections following the conventions in `docs/skill-authoring.md`
4. If the skill produces data on a cadence, add an Overdue Condition section
5. Place the skill directory where OpenClaw can discover it (see `docs/implementation.md`)
6. Restart the agent service for the skill to take effect

Custom skills follow the same message format as Tier 1 skills — YAML frontmatter + markdown body in outbox files. See `docs/communication.md` for the protocol.

## Choosing messaging channels

OpenClaw supports multiple messaging channels. FleetClaw is channel-agnostic — skills don't reference any specific messaging platform. The messaging channel is configured during OpenClaw setup, not by FleetClaw skills.

Common choices:

- **Telegram** — Recommended for most deployments. Simple bot creation, works on mobile, supports inline keyboards.
- **Slack** — Better for organizations already using Slack. Channel-based access control.
- **Discord** — Alternative for teams familiar with Discord.
- **SMS** — For remote sites with limited data connectivity.
- **Custom webhooks** — For integration with existing communication systems.

Each agent gets its own messaging channel connection (bot token, webhook URL, etc.). This ensures messages to one machine go to that machine's agent.

## Configuring heartbeat intervals

Heartbeat intervals control how often agents proactively check for work. Defaults:

| Agent role | Default | Range |
|-----------|---------|-------|
| Asset agents | 30 min | 15m - 2h |
| Clawvisor | 2 hr | 30m - 4h |
| Clawordinator | 4 hr | 2h - 12h |

Tune based on:

- **Shift length** — Shorter shifts need shorter asset heartbeats so nudges land during the shift
- **Cost tolerance** — Each heartbeat is an LLM API call. Longer intervals = lower cost.
- **Freshness requirements** — How quickly does management need to see anomalies or compliance gaps?
- **Active hours** — Restrict heartbeats to operational shifts. Prevents off-hours API costs. Use `activeHours` with `start`, `end` (exclusive, 24:00 allowed), and `timezone` (IANA format).

Configure in each agent's `openclaw.json`:

```json
"agents": {
  "defaults": {
    "heartbeat": {
      "every": "30m",
      "activeHours": {
        "start": "06:00",
        "end": "20:00",
        "timezone": "America/Moncton"
      }
    }
  }
}
```

Replace `America/Moncton` with the fleet's operational timezone. Heartbeat interval is the primary cost control — longer intervals reduce API costs.

HEARTBEAT.md must have real content for heartbeats to fire — OpenClaw skips ticks when it is effectively empty. See `docs/implementation.md` for setup and `templates/` for role-specific templates.

## Adapting SOUL.md templates

The default SOUL.md templates are deliberately minimal. Organizations may want to add:

- **Org-specific tone** — "You work for Acme Mining. Be professional but friendly."
- **Language preferences** — "Operators may speak Spanish. Respond in their language."
- **Safety emphasis** — "Always ask about safety hazards when operators report issues."
- **Communication style** — "Use metric units only. Never use imperial."

Edit the templates in `templates/` before deploying, or modify individual agent SOUL.md files in their workspaces.

Keep additions brief — SOUL.md is loaded at every session start and competes with skills for context window space.

## Configuring tools.deny

OpenClaw agents have access to various tools by default. FleetClaw restricts unnecessary ones:

```json
"tools": {
  "deny": ["browser", "canvas", "nodes", "cron"]
}
```

Organizations may want to:

- **Allow browser** — For skills that fetch external data (telematics APIs, weather)
- **Allow cron** — For scheduled tasks beyond heartbeat. Cron provides exact timing, session isolation, and one-shot reminders. See `docs/scheduling.md` for the full cron reference and when to use cron vs heartbeat
- **Deny exec** — For high-security environments (prevents agents from running shell commands)

Consider the security implications of each tool. See OpenClaw documentation for the full tool list.

## Adding new assets at runtime

When a new machine arrives on site:

1. Tell Clawordinator via its messaging channel: "Add new CAT 390F, asset ID EX-005, serial CAT0390F-2024-M2"
2. Clawordinator's `asset-onboarder` skill guides the process:
   - Creates the system user
   - Installs OpenClaw
   - Injects FleetClaw customizations
   - Sets permissions
   - Creates and starts the service
   - Updates fleet.md
3. Set up the new agent's messaging channel connection
4. The new agent is live — operators can start messaging it

For the detailed onboarding procedure, see the `asset-onboarder` skill and `docs/implementation.md`.

## Multi-site deployments

For organizations with multiple sites:

### Shared skill repository

All sites use the same FleetClaw skills from a central git repository. Site-specific customizations go in separate skill directories or branches.

### Site-specific fleet.md

Each site has its own fleet.md, Clawvisor, and Clawordinator. A regional Clawordinator (Tier 2) could aggregate across sites.

### Independent servers

Each site runs its own server with its own agents. No shared filesystem needed between sites. Skills are deployed via git pull on each server.

### Cross-site visibility

Not built into Tier 1. For Tier 2, consider:

- A dashboard skill on a regional Clawordinator that reads fleet.md from multiple sites
- API-based aggregation via custom skills
- Shared file sync (rsync, NFS) for outbox directories across sites

## Outbox retention

Outbox files accumulate over time. Configure a retention policy:

- **Short retention (7 days)** — Suitable for small fleets where storage is limited
- **Medium retention (30 days)** — Default recommendation. Covers monthly reporting periods.
- **Long retention (90+ days)** — For compliance-heavy organizations that need audit trails

Implement retention via a cron job that archives or deletes outbox files older than the retention period. The memory-curator skills keep MEMORY.md current regardless of outbox retention.

## Tier 2 integrations

Common Tier 2 integrations that organizations build:

| Integration | Skill type | What it does |
|-------------|-----------|-------------|
| CMMS (SAP PM, Pronto) | Asset agent | Auto-create work orders from issue reports |
| Telematics (CAT PL, KOMTRAX) | Asset agent | Import meter readings automatically |
| Fuel management (FuelForce) | Asset agent | Cross-reference fuel logs with bowser data |
| ERP (SAP, Oracle) | Clawvisor | Export compliance reports |
| Dashboards (Grafana, Power BI) | Clawordinator | Export fleet metrics |

Each integration is a custom skill with the external system's API endpoint and credentials declared in the frontmatter's `env` requirements and the agent's env file.
