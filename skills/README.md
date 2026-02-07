# Fleetclaw Skills

This directory contains OpenClaw skills for the Fleetclaw fleet management system.

## Skill Overview

| Skill | Purpose | Priority |
|-------|---------|----------|
| `fuel-log-validator` | Validate fuel submissions against SOUL.md learned models | High |
| `fleet-comms` | Redis pub/sub for cross-asset messaging | High |
| `fleet-coordinator` | Status aggregation, hourly summaries, daily reports | High |
| `escalation-handler` | 4-level escalation chain with timeouts | High |
| `asset-monitor` | 4-hour self-check loops, staleness detection | Medium |
| `preop-validator` | Pre-operation checklist validation | Medium |

## Skill Architecture

### Key Concept: Skills = Instructions, Not Code

OpenClaw skills are **instructional documents** that guide the LLM on how to accomplish tasks. They don't contain validation logic — they tell the agent:

- What files to read (SOUL.md for learned models)
- What CLI tools to use (redis-cli, jq, curl)
- What patterns to follow (validation rules)
- When to escalate (conditions and targets)

### SKILL.md Format

Each skill has a `SKILL.md` file with:

1. **YAML Frontmatter** - Metadata, dependencies, requirements
2. **When to Use** - Trigger conditions
3. **Steps/Instructions** - What the agent should do
4. **Response Templates** - Standard output formats
5. **Examples** - Sample inputs and expected outputs

```markdown
---
name: skill-name
description: What the skill does
metadata: {"openclaw":{"requires":{"bins":["jq"],"env":["REDIS_URL"]}}}
---

# Skill Name

## When to Use
[Trigger conditions]

## Steps
[Instructions for the agent]

## Response Templates
[Standard output formats]
```

### Skill Locations

Skills can be installed at two levels:

```
~/.openclaw/skills/           # Shared skills (all agents)
<workspace>/skills/          # Per-asset skills
```

For Fleetclaw:
- Shared skills: `fleet-comms`, `escalation-handler`
- Per-asset skills: `fuel-log-validator`, `asset-monitor`, `preop-validator`
- FC-only skills: `fleet-coordinator`

## Skill Dependencies

### System Requirements

| Skill | Required Binaries | Environment Variables |
|-------|-------------------|----------------------|
| `fuel-log-validator` | `jq` | - |
| `fleet-comms` | `redis-cli`, `jq` | `REDIS_URL` |
| `fleet-coordinator` | `redis-cli`, `jq` | `REDIS_URL` |
| `escalation-handler` | `lobster` | `SUPERVISOR_ID`, `SAFETY_ID`, `OWNER_ID` |
| `asset-monitor` | `redis-cli`, `jq` | `REDIS_URL` |
| `preop-validator` | - | - |

### Inter-Skill Dependencies

```
fuel-log-validator
    └── (none - standalone)

fleet-comms
    └── (none - foundational)

fleet-coordinator
    ├── fleet-comms (for Redis communication)
    └── escalation-handler (for routing alerts)

escalation-handler
    └── fleet-comms (for status updates)

asset-monitor
    ├── fleet-comms (for status broadcasts)
    └── escalation-handler (for triggering escalations)

preop-validator
    └── (none - standalone)
```

## Usage by Agent Type

### Asset Agents (Excavators, Trucks, Loaders, etc.)

```json
{
  "skills": {
    "enabled": [
      "fuel-log-validator",
      "fleet-comms",
      "escalation-handler",
      "asset-monitor",
      "preop-validator"
    ]
  }
}
```

### Fleet Coordinator

```json
{
  "skills": {
    "enabled": [
      "fleet-coordinator",
      "fleet-comms",
      "escalation-handler"
    ]
  }
}
```

## Testing Skills

### Manual Testing

1. Start a OpenClaw session with the skill enabled
2. Send test inputs matching the skill's triggers
3. Verify responses match expected templates

### Test Scenarios

See each skill's SKILL.md for specific test cases. Key scenarios:

**fuel-log-validator:**
- Valid fuel log → ACCEPT
- Hours decreased → REJECT
- Exceeds tank capacity → REJECT
- Anomalous consumption → FLAG

**fleet-comms:**
- Send query to another asset → Response received
- Status broadcast → FC receives
- Inbox subscription → Messages processed

**escalation-handler:**
- Trigger escalation → Level 1 notification sent
- Timeout → Escalates to next level
- ACK response → Escalation paused
- RESOLVED response → Escalation closed

**asset-monitor:**
- Stale GPS → FLAG operating-without-tracking
- All data fresh → OPERATIONAL status
- Redis connection lost → DEGRADED mode

## Adding New Skills

1. Create directory: `skills/new-skill-name/`
2. Create `SKILL.md` with proper frontmatter
3. Add to openclaw.json `skills.enabled` array
4. Test with sample inputs
5. Document in this README

## Lobster Workflows

For multi-step processes with approval gates, use Lobster workflow files:

```yaml
# example.lobster
name: workflow-name
steps:
  - name: step_1
    command: "some command"
    timeout: 1h
    on_timeout: next_step
```

See `escalation-handler/escalation.lobster` for a complete example.

## More Information

- [OpenClaw Skills Documentation](https://docs.openclaw.dev/tools/skills.md)
- [Lobster Workflow Language](https://docs.openclaw.dev/tools/lobster.md)
- [Fleetclaw Architecture](../docs/architecture/)
