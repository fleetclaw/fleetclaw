# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

FleetClaw is a platform that gives every piece of mining equipment its own AI agent via Telegram. Operators text their machine to log fuel, meters, pre-ops, and issues. The system makes compliance feel like a conversation. Built on [OpenClaw](https://github.com/openclaw/openclaw), each agent runs in its own Docker container.

FleetClaw is a **platform, not a product**. The core system provides agents, communication, and infrastructure. Behavior is defined entirely by **skills** — swappable markdown files, not code.

## Commands

```bash
# Generate all deployment artifacts from fleet.yaml
python generate-configs.py [fleet.yaml]
# Falls back to fleet.yaml.example if fleet.yaml doesn't exist

# Dependency
pip install pyyaml

# Deploy (on Linux server with Docker)
cp fleet.yaml.example fleet.yaml        # edit with your assets
python generate-configs.py
cp output/.env.template .env            # fill in tokens
bash output/setup-redis.sh              # one-time Redis consumer groups
docker compose -f output/docker-compose.yml up -d
```

There are no tests, linting, or build steps. The only executable code is `generate-configs.py`.

## Architecture

### Three Agent Types

| Agent | Audience | Role | Container |
|---|---|---|---|
| **Asset Agents** | Operators only | One per machine. Logs data, gives feedback, nudges. | `fc-agent-{id}` |
| **Clawvisor** | Mechanics, foremen, supervisors | Fleet oversight. Aggregates, tracks compliance, detects anomalies. | `fc-clawvisor` |
| **Clawordinator** | Managers, owners | Command layer. Fleet composition, directives, Docker control. | `fc-clawordinator` |

Data flows: Asset Agents → Redis → Clawvisor → (escalates to) → Clawordinator

### Skills-First Design

Skills are markdown files (`skills/{name}/SKILL.md`) that teach agents behavior in plain English. Each agent role has a fixed set of skill mounts defined in `SKILL_MOUNTS` in `generate-configs.py`. Skills follow a standard structure: YAML frontmatter + Trigger/Input/Behavior/Output/Overdue Condition sections. See `skills/SKILL-TEMPLATE.md` for the blank scaffolding and `docs/skill-authoring.md` for the philosophy guide.

### SOUL.md — Minimal Identity

Agent identity templates live in `templates/soul-{type}.md`. They are intentionally minimal — just the agent name and serial number. All behavior comes from skills, not identity documents.

### generate-configs.py — The Single Generator

This is the only code in the repo. It reads `fleet.yaml` and outputs everything to `output/`:
- `workspaces/{ID}/SOUL.md` — per-agent identity (substitutes `{ASSET_ID}`, `{SERIAL}`)
- `config/openclaw-{ID}.json` — per-agent OpenClaw config (substitutes `{HEARTBEAT}`, `{SHIFT_START}`, `{SHIFT_END}`, `{TIMEZONE}`, `{ASSET_ID}`)
- `docker-compose.yml` — full compose with Redis, all agents, docker-socket-proxy
- `.env.template` — required environment variables
- `setup-redis.sh` — one-time Redis consumer group creation

Template substitution uses simple string replacement (`{PLACEHOLDER}`), not Jinja2. OpenClaw's own env vars use `${ENV_VAR}` syntax and are resolved at runtime by OpenClaw, not by this script.

### Redis Schema

Entity-first hierarchical keys: `fleet:asset:{ASSET_ID}:{type}`. State is HASH (discrete fields, not JSON blobs). Events are STREAM (with MAXLEN trimming). Indexes are SET. The authoritative reference is `docs/redis-schema.md`.

### Key Config Values

- OpenClaw default gateway port: 18789 (set in openclaw.json templates, matched by healthchecks in generate-configs.py)
- OpenClaw base image: `ghcr.io/openclaw/openclaw:2026.2.x`
- MEMORY.md bootstrap limit: 15,000 chars (`bootstrapMaxChars` in openclaw.json templates)
- Heartbeat defaults: asset 30m, clawvisor 2h, clawordinator 4h
- Container memory: asset 512m, clawvisor/clawordinator 1g, redis 768m
- Redis: 7.4-alpine, noeviction policy, AOF persistence

## File Layout

- `generate-configs.py` — reads fleet.yaml, produces all output (the only code)
- `fleet.yaml.example` — example fleet configuration
- `templates/` — SOUL.md and openclaw.json templates per agent role
- `skills/` — 21 Tier 1 skills, each in `{name}/SKILL.md`
- `docker/` — Dockerfile (standard) and Dockerfile.clawordinator (adds docker.io)
- `docs/` — architecture.md, redis-schema.md, skill-authoring.md, implementation.md
- `output/` — generated artifacts (gitignored, recreate with generate-configs.py)
- `data/` — runtime container data (gitignored)

## When Editing Skills

- Follow the structure in `skills/SKILL-TEMPLATE.md`
- YAML frontmatter defines machine-readable contract (name, description, bins, env requirements)
- `## Behavior` stays freeform — existing Tier 1 skills are the style guide
- Each skill declares which Redis keys it reads/writes in Input/Output sections
- Overdue Condition format: `[what's missing] after [time threshold] since [reference event]`
- Skills are mounted read-only into containers; changes require container restart

## When Editing generate-configs.py

- `SKILL_MOUNTS` dict controls which skills each agent role receives
- `CONSUMER_GROUPS` / `FLEET_CONSUMER_GROUPS` define Redis XGROUP setup
- Template substitution is plain string replace — if you add a new placeholder, update both the template files and the `generate_*` functions
- The compose output uses PyYAML `dump()` — dict key order matters for readability
