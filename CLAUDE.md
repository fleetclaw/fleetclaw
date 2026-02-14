# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## What This Is

FleetClaw is a skill library and architecture reference that gives every piece of mining equipment its own AI agent. Operators message their machine to log fuel, meters, pre-ops, and issues. The system makes compliance feel like a conversation. Built on [OpenClaw](https://github.com/openclaw/openclaw).

FleetClaw is a **platform, not a product**. Behavior is defined entirely by **skills** -- swappable markdown files, not code. This repository contains no executable code.

## Key Files

- `AGENTS.md` -- Entry point for coding agents. Start here for setup and architecture overview.
- `docs/architecture.md` -- System design, agent roles, data flow, communication model
- `docs/communication.md` -- Filesystem message protocol (inbox/outbox format, fleet.md)
- `docs/permissions.md` -- POSIX ACL permission model for multi-agent filesystem access
- `docs/implementation.md` -- Setup guide: OpenClaw install, FleetClaw injection, services
- `docs/skill-authoring.md` -- How to write skills
- `docs/customization.md` -- Extending FleetClaw for specific organizations
- `docs/scheduling.md` -- Heartbeat, cron, and scheduling reference
- `platform/` -- OS-specific references (Ubuntu, macOS, Windows)
- `skills/` -- 21 Tier 1 skills, each in `{name}/SKILL.md`
- `templates/` -- SOUL.md identity templates and HEARTBEAT.md templates per agent role

## Architecture

### Three Agent Roles

| Agent | Audience | Role |
|---|---|---|
| **Asset Agents** | Operators only | One per machine. Logs data, gives feedback, nudges. |
| **Clawvisor** | Mechanics, foremen, supervisors | Fleet oversight. Aggregates, tracks compliance, detects anomalies. |
| **Clawordinator** | Managers, owners | Command layer. Fleet composition, directives, service management. |

Data flows: Asset Agents write to outbox/ --> Clawvisor reads asset outboxes --> (escalates to) --> Clawordinator via inbox files

### Communication

Agents communicate through **filesystem inbox/outbox directories** containing timestamped markdown files with YAML frontmatter. See `docs/communication.md` for the full protocol.

Key files per agent:
- `outbox/` -- Files the agent writes to share data
- `outbox-archive/` -- Archived outbox files (managed by OS cron job, not agents)
- `inbox/` -- Files other agents write to send messages
- `AGENTS.md` `## State` -- Current operational state (flat key-value, always in context)
- `fleet.md` -- Shared fleet registry (owned by Clawordinator, readable by Clawvisor)
- `MEMORY.md` -- Curated working memory

### Skills-First Design

Skills are markdown files (`skills/{name}/SKILL.md`) that teach agents behavior in plain English. Skills follow a standard structure: YAML frontmatter + Trigger/Input/Behavior/Output/Overdue Condition sections. See `skills/SKILL-TEMPLATE.md` for the blank scaffolding and `docs/skill-authoring.md` for the philosophy guide.

### SOUL.md -- Minimal Identity

Agent identity templates live in `templates/soul-{type}.md`. They are intentionally minimal -- just the agent name and serial number. All behavior comes from skills, not identity documents.

### Key Config Values

- MEMORY.md bootstrap limit: 15,000 chars
- Heartbeat defaults: asset 30m, clawvisor 2h, clawordinator 4h
- `activeHours` restricts heartbeats to operational hours (e.g., 06:00-20:00)
- HEARTBEAT.md must have real content or heartbeat ticks are skipped
- Outbox archival: 30-day default retention, OS cron job (not OpenClaw cron). Canonical reference: `docs/scheduling.md`
- `.clawvisor-last-read` marker file must never be archived or deleted
- Model vision: include `"image"` in the model's `input` array to enable photo routing to the primary model

## When Editing Skills

- Follow the structure in `skills/SKILL-TEMPLATE.md`
- YAML frontmatter defines machine-readable contract (name, description, bins, env requirements)
- `## Behavior` stays freeform -- existing Tier 1 skills are the style guide
- Skills reference filesystem operations: inbox files, outbox files, AGENTS.md `## State`, fleet.md, MEMORY.md
- User messages may include photos when the model supports vision
- Skill input label for state: `**AGENTS.md (State):** {keys}` -- output label: `**AGENTS.md (State) updates:** {desc}`
- Cross-agent state reads (Clawvisor/Clawordinator skills): `**Asset AGENTS.md (State):** {desc}` for input, "the `## State` section in the asset's AGENTS.md" in behavior prose
- Skills should be channel-agnostic -- don't assume a specific messaging platform
- Skills should be platform-agnostic -- use generic phrasing like "stop the agent service" rather than OS-specific commands. Platform docs provide the specifics.
- Overdue Condition format: `[what's missing] after [time threshold] since [reference event]`
- When removing numbered steps, renumber the remaining steps -- don't leave gaps
- Use "agent role" (not "agent type") when referring to asset/clawvisor/clawordinator to avoid confusion with equipment types
- When removing a concept, grep the entire repo -- skills, docs, CLAUDE.md, and templates may all reference it
