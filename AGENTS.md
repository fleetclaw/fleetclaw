# AGENTS.md — FleetClaw Setup Guide

This is your entry point. FleetClaw is a skill library and architecture reference that gives every piece of mining equipment its own AI agent. You are setting it up for an organization.

There is no executable code in this repository. No scripts to run, no config files to generate. You read the docs, understand the architecture, and set up the fleet interactively based on the organization's needs.

## Prerequisites

- A server or machine (Ubuntu 24.04 LTS recommended)
- Node.js 22+
- Git (to clone this repo)
- An LLM API key (Fireworks, OpenAI, Anthropic, etc.)
- One messaging channel token per agent (e.g., Telegram bot tokens)

## The three agent roles

| Role | Audience | What it does |
|------|----------|-------------|
| **Asset Agents** | Operators only | One per machine. Logs fuel, meters, pre-ops, issues. Nudges operators. |
| **Clawvisor** | Mechanics, foremen, supervisors, safety reps | Fleet oversight. Tracks compliance, detects anomalies, logs maintenance. |
| **Clawordinator** | Managers, safety reps, owners | Command layer. Onboards assets, manages lifecycle, issues directives. |

Data flows: Asset Agents → (outbox files) → Clawvisor → (escalations) → Clawordinator

## Setup flow

1. **Detect your platform** — Read the appropriate platform reference:
   - Ubuntu/Linux: `platform/ubuntu.md` (primary, recommended)
   - macOS: `platform/macos.md`
   - Windows: `platform/windows.md`

2. **Understand the architecture** — Read `docs/architecture.md` for the full system design: agent roles, communication model, permission model, data flow.

3. **Follow the implementation guide** — Read `docs/implementation.md` for step-by-step setup: user creation, OpenClaw installation, FleetClaw injection, ACLs, services, fleet.md.

4. **Understand the communication protocol** — Read `docs/communication.md` for how agents exchange data via inbox/outbox files.

5. **Set up permissions** — Read `docs/permissions.md` for the ACL model that replaces container isolation.

6. **Deploy** — For each agent:
   - Create a system user (platform doc)
   - Install OpenClaw as that user
   - Copy the appropriate SOUL.md template from `templates/`
   - Create inbox/outbox directories
   - Configure skills (point OpenClaw at the skills directory)
   - Tune openclaw.json (agents.defaults: heartbeat, bootstrapMaxChars, model)
   - Set ACLs (permissions doc)
   - Create env file with secrets
   - Create and start the system service (platform doc)

7. **Initialize fleet.md** — Create the fleet registry with all assets listed

8. **Verify** — Each agent should respond via its messaging channel

## Where to find things

| What | Where |
|------|-------|
| System architecture | `docs/architecture.md` |
| Step-by-step setup | `docs/implementation.md` |
| Communication protocol | `docs/communication.md` |
| Permission model | `docs/permissions.md` |
| Platform commands (Ubuntu) | `platform/ubuntu.md` |
| Platform commands (macOS) | `platform/macos.md` |
| Platform commands (Windows) | `platform/windows.md` |
| Customization guide | `docs/customization.md` |
| Skill writing guide | `docs/skill-authoring.md` |
| Skill template | `skills/SKILL-TEMPLATE.md` |
| SOUL.md templates | `templates/soul-asset.md`, `soul-clawvisor.md`, `soul-clawordinator.md` |
| All 21 Tier 1 skills | `skills/*/SKILL.md` |

## Quick reference: what each agent needs

### Every agent

- System user in `fc-agents` group
- OpenClaw installed (`openclaw onboard --install-daemon`)
- SOUL.md from appropriate template
- inbox/ and outbox/ directories
- Skills linked via openclaw.json `extraDirs` or workspace symlinks
- Environment file with API key and messaging token
- System service (systemd/launchd/NSSM)
- Read access to fleet.md

### Asset agents additionally

- state.md initialized
- ACL: Clawvisor can read outbox/ and state.md
- ACL: Clawvisor and Clawordinator can write to inbox/

### Clawvisor additionally

- ACL: Can read all asset outbox/ directories and state.md files
- ACL: Can write to all asset inbox/ directories
- ACL: Can write to Clawordinator's inbox/

### Clawordinator additionally

- ACL: Can write to any agent's inbox/
- Owns fleet.md (sole writer)
- Scoped sudo for service management commands
