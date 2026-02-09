# FleetClaw Architecture

## What FleetClaw is

FleetClaw is a platform that gives every piece of mining equipment its own AI agent. Operators text their machine's agent via Telegram to log fuel, record meter readings, complete pre-op inspections, and report issues. The system makes compliance feel like a conversation rather than a form.

FleetClaw is built on [OpenClaw](https://openclaw.ai), an open-source framework for persistent AI agents. Each agent runs in its own Docker container with its own identity, memory, and skills. Agents communicate through Redis and persist context through markdown files.

FleetClaw is a platform, not a product. The core system provides agents, communication, and infrastructure. What those agents actually do is defined by skills — swappable markdown instructions that organizations can customize, extend, or replace.

## The three agents

FleetClaw runs three types of agents, each serving a different audience:

```
Operators ──────────────► Asset Agents (one per machine)
                               │
                               │ Redis
                               ▼
Mechanics ──────────────►
Foremen ────────────────► Clawvisor (fleet oversight)
Supervisors ────────────►
Safety Reps ────────────►        │
                                 │ escalations
Managers ───────────────►        ▼
Owners ─────────────────► Clawordinator (command layer)
Safety Reps ────────────►
```

### Asset Agents

One agent per machine. Operators talk to their machine's agent exclusively. The agent accepts messy natural-language input ("400l", "filled up 400", "put 400 in at smoko"), logs it, and provides immediate feedback ("13.2 L/hr, normal range"). Each agent has its own Telegram bot token — operators text the machine directly.

**Audience:** Operators only.

**Skills:** `fuel-logger`, `meter-reader`, `pre-op`, `issue-reporter`, `nudger`, `memory-curator-asset`

### Clawvisor

The fleet oversight agent. Everyone in a supervisory or maintenance role uses Clawvisor. It aggregates data from all asset agents via Redis, tracks compliance, detects anomalies, accepts maintenance logs from mechanics, and generates shift/daily summaries. Clawvisor is read-write — mechanics log completed repairs through it, and that data flows back to asset agents.

**Audience:** Mechanics, foremen, supervisors, safety reps, managers, owners.

**Skills:** `fleet-status`, `compliance-tracker`, `maintenance-logger`, `anomaly-detector`, `shift-summary`, `escalation-handler`, `asset-query`, `memory-curator-clawvisor`

### Clawordinator

The command layer. Only people who can change how the fleet operates get access. Clawordinator has Docker control — it can onboard new assets (spin up containers), decommission old ones (stop and archive), idle seasonal equipment, and manage skill deployment across the fleet. It receives escalations from Clawvisor and presents them to leadership for decisions.

**Audience:** Safety reps, managers, owners.

**Skills:** `asset-onboarder`, `asset-lifecycle`, `fleet-director`, `escalation-resolver`, `fleet-analytics`, `fleet-config`, `memory-curator-clawordinator`

### The relationship between them

```
Clawvisor is the eyes and mouth — it sees everything and tells people.
Clawordinator is the brain and hands — it decides and changes the fleet.
Asset agents are the frontline — they talk to operators and collect data.
```

Clawvisor can see all asset data but cannot change fleet composition. Clawordinator can change fleet composition but relies on Clawvisor for operational visibility. Asset agents are focused entirely on their one machine and one operator.

## SOUL.md — Minimal identity

Every OpenClaw agent has a SOUL.md file — its identity and personality. In FleetClaw, SOUL.md is the vanilla OpenClaw template with exactly two values injected:

```markdown
## Core Truths

**You are {ASSET_ID}.** Serial: {SERIAL}.

**Be genuinely helpful, not performatively helpful.** Skip the "Great question!"...
```

That's it. No specs, no fuel thresholds, no escalation chains, no operator directories. The agent learns everything else from its skills and builds context in MEMORY.md over time.

For Clawvisor and Clawordinator, the identity line is simply "You are Clawvisor" or "You are Clawordinator" — no asset ID or serial needed.

## Skills — How agents learn behavior

Skills are markdown files that teach agents how to do things. They contain plain English instructions — not code — that the LLM reads and follows. When an agent has multiple skills mounted, it reads all of them and synthesizes the instructions into behavior.

### The two contracts in one file

Every skill has YAML frontmatter (machine-readable, declares dependencies) and a markdown body (LLM-readable, teaches behavior):

```yaml
---
name: fuel-logger
description: Accept fuel log entries from operators and publish to Redis
metadata: {"openclaw":{"requires":{"bins":["redis-cli"],"env":["REDIS_URL"]}}}
---
```

### Skill structure

Every skill follows this pattern:

1. **Trigger** — When does the agent activate this skill? (message, heartbeat, session start, Redis event)
2. **Input** — What data does it consume? (user messages, Redis keys, MEMORY.md, .env variables)
3. **Behavior** — Plain English instructions. Not code. Not pseudocode.
4. **Output** — What does it produce? (Redis writes, MEMORY.md updates, messages to user, escalation flags)
5. **Overdue Condition** (optional) — When is something missing that the nudger should catch?

See `skills/SKILL-TEMPLATE.md` for the blank template and `docs/skill-authoring.md` for the comprehensive guide.

### The nudger pattern

The nudger is a standalone skill that coordinates reminders across all domain skills. It works through convention:

- **Domain skills** (fuel-logger, meter-reader, pre-op) each define an `## Overdue Condition` section: "No fuel log within 8 hours of the operator's first message this shift."
- **The nudger skill** defines tone, cadence, and rules: one gentle reminder per missing item per shift, never stack multiple nudges, never in group chats.
- **The agent reads both** and synthesizes: "fuel is overdue (from fuel-logger), and I know how to remind (from nudger)."

A Tier 2 skill author building `tire-pressure-logger` just adds their own `## Overdue Condition`, and the nudger automatically picks it up. The convention is the API.

### Skill tiers

**Tier 1 — Ships with FleetClaw.** Works out of the box using Redis and MEMORY.md only. No external integrations. These define the baseline platform experience.

**Tier 2 — Organization-built.** Integrates with external systems via .env credentials (CMMS like SAP PM or Pronto, telematics like CAT Product Link or Komatsu KOMTRAX, fuel management systems). FleetClaw provides the skill template and authoring guide; the organization fills in the integration.

**Tier 3 — Community/advanced.** Extends the platform in ways not anticipated by the core team: voice transcription, predictive analytics, custom dashboards, multi-site management.

### Skill mounting

No skills are shared across all agent types. Each agent type has its own skill set:

```
skills/
├── fuel-logger/SKILL.md              # Asset agents
├── meter-reader/SKILL.md             # Asset agents
├── pre-op/SKILL.md                   # Asset agents
├── issue-reporter/SKILL.md           # Asset agents
├── nudger/SKILL.md                   # Asset agents
├── memory-curator-asset/SKILL.md     # Asset agents
├── fleet-status/SKILL.md             # Clawvisor
├── compliance-tracker/SKILL.md       # Clawvisor
├── maintenance-logger/SKILL.md       # Clawvisor
├── anomaly-detector/SKILL.md         # Clawvisor
├── shift-summary/SKILL.md            # Clawvisor
├── escalation-handler/SKILL.md       # Clawvisor
├── asset-query/SKILL.md              # Clawvisor
├── memory-curator-clawvisor/SKILL.md # Clawvisor
├── asset-onboarder/SKILL.md          # Clawordinator
├── asset-lifecycle/SKILL.md          # Clawordinator
├── fleet-director/SKILL.md           # Clawordinator
├── escalation-resolver/SKILL.md      # Clawordinator
├── fleet-analytics/SKILL.md          # Clawordinator
├── fleet-config/SKILL.md             # Clawordinator
└── memory-curator-clawordinator/SKILL.md # Clawordinator
```

Skills are mounted as read-only Docker volumes. Skill deployment is managed by Clawordinator via the `fleet-config` skill.

## Redis — The message bus

Redis is the communication layer between all FleetClaw agents. It is **not the source of truth** — MEMORY.md on each agent is the permanent record. Redis holds recent operational data long enough for all consumers to read it.

```
Asset Agent writes event → Redis Stream (short-lived, trimmed)
                         → MEMORY.md (permanent, curated summary)

Clawvisor reads Redis → aggregates, detects anomalies, reports
Clawordinator reads Redis → fleet-level decisions, lifecycle management
```

### Key naming convention

Keys are hierarchical, entity-first: `fleet:asset:{ASSET_ID}:{data_type}`

This enables efficient per-asset prefix scanning (`fleet:asset:EX-001:*`) while cross-asset queries use index SETs (`fleet:index:active`, `fleet:index:idle`).

### Data types

- **State data** → HASH with discrete fields (not JSON blobs). Each field independently readable with HGET.
- **Event data** → STREAM with MAXLEN trimming (not TTL expiry). Built-in timestamps, consumer groups, range queries.
- **Index data** → SET for O(1) membership checks and fleet enumeration.

### Key reference

| Key | Type | Writer | Reader |
|-----|------|--------|--------|
| `fleet:asset:{ID}:state` | HASH | Asset agent | Clawvisor, Clawordinator |
| `fleet:asset:{ID}:fuel` | STREAM | Asset agent | Clawvisor |
| `fleet:asset:{ID}:meter` | STREAM | Asset agent | Clawvisor |
| `fleet:asset:{ID}:preop` | STREAM | Asset agent | Clawvisor |
| `fleet:asset:{ID}:issues` | STREAM | Asset agent | Clawvisor |
| `fleet:asset:{ID}:maintenance` | STREAM | Clawvisor | Asset agent |
| `fleet:asset:{ID}:alerts` | STREAM | Clawvisor | Clawvisor, Clawordinator |
| `fleet:asset:{ID}:inbox` | STREAM | Clawvisor, Clawordinator | Asset agent |
| `fleet:asset:{ID}:lifecycle` | HASH | Clawordinator | Clawvisor, Asset agent |
| `fleet:directives` | STREAM | Clawordinator | Asset agents, Clawvisor |
| `fleet:escalations` | STREAM | Clawvisor | Clawordinator |
| `fleet:index:active` | SET | Clawordinator | Clawvisor |
| `fleet:index:idle` | SET | Clawordinator | Clawvisor |

See `docs/redis-schema.md` for complete field definitions, data formats, consumer group setup, and retention strategy.

### Retention

No key-level TTL. Streams use MAXLEN trimming (entries removed by XADD itself). HASHes and SETs are persistent. Single Redis instance with `maxmemory-policy noeviction` for Tier 1. Separate instances recommended for Tier 2 deployments with heavy caching.

### The maintenance acknowledgment loop

The inbox stream (`fleet:asset:{ID}:inbox`) closes the feedback loop between operators and mechanics:

```
1. Operator tells asset agent: "hydraulics are sluggish"
   → Asset agent writes to fleet:asset:EX-001:issues

2. Mechanic tells Clawvisor: "replaced hyd pump on EX-001, 6 hours"
   → Clawvisor writes to fleet:asset:EX-001:maintenance
   → Clawvisor writes to fleet:asset:EX-001:inbox (maintenance_ack)

3. Next operator session with EX-001's agent:
   → Agent checks inbox on session start
   → "Heads up — hydraulic pump was replaced yesterday. Monitor temps."
```

This loop is what makes operators keep reporting issues. They see that reporting leads to action.

## MEMORY.md — The permanent record

MEMORY.md is the agent's hot cache — curated context loaded at session start without querying Redis. It passes this test: "Would I need this in the first 10 seconds of a conversation?"

### The 15,000 character constraint

FleetClaw sets `bootstrapMaxChars` to 15,000 characters (down from OpenClaw's 20,000 default) to leave headroom for skills context. This means MEMORY.md must contain curated summaries, not raw data. Each agent type has a dedicated memory-curator skill that defines structure, pruning rules, and character budgets.

### Per-agent-type design

**Asset agent MEMORY.md** — Target: under 5,000 characters.

```
## Current Shift        — Who's operating, what's been logged/nudged
## Recent Context       — Last 5 fuel logs, last 3 meters, open issues
## Operator Patterns    — Regular operators' habits and preferences
## Learned Patterns     — Normal burn rates, fueling frequency
## Open Items           — Unresolved issues awaiting maintenance
```

**Clawvisor MEMORY.md** — Target: under 8,000 characters. Hard ceiling: 15,000.

Clawvisor's memory is an **exception report, not an inventory**. Only assets with active problems appear. Healthy assets live in Redis.

```
## Fleet Health         — 2-3 sentence summary
## Needs Attention      — Only flagged assets (anomalies, escalations, overdue)
## Active Escalations   — Currently open, with context
## Compliance Trends    — Improving/declining by category
## Recent Alerts Sent   — Last 10 (prevents re-alerting)
## Mechanic Activity    — Last 5 maintenance logs
```

**Clawordinator MEMORY.md** — Target: under 5,000 characters. The leanest.

```
## Fleet Composition    — Active/idle counts by type
## Pending Escalations  — Unresolved, from Clawvisor
## Pending Directives   — Active, with acknowledgment status
## Recent Actions       — Last 10 lifecycle/deployment actions
## Skill Deployment     — What's mounted where
```

### Curation triggers

| Agent | Session end | Heartbeat |
|-------|------------|-----------|
| Asset agent | Distill conversation into facts | Check inbox, refresh open items |
| Clawvisor | Update based on interaction outcome | Scan fleet state, refresh flags |
| Clawordinator | Record decisions and actions taken | Check escalations, directive status |

See the three `memory-curator-*.md` skill files for complete curation rules, pruning priorities, and scaling notes.

### Shift detection

Asset agents detect shift changes via Telegram user ID: a different user messaging after a 2+ hour gap triggers a new shift. This resets nudge tracking, expects a new pre-op, and delivers any pending maintenance acknowledgments to the new operator. No shift configuration needed — it works for 8h, 10h, 12h, or irregular shifts.

Fallback: same operator active >14 hours = new shift period for nudge/pre-op purposes.

## Heartbeat intervals

Each agent type has a different heartbeat cadence matching its operational rhythm:

| Agent | Interval | Rationale |
|-------|----------|-----------|
| Asset agents | 30 min | Operator-facing; nudges need to land mid-shift |
| Clawvisor | 2 hr | Oversight cadence; mechanic updates need reasonable freshness |
| Clawordinator | 4-8 hr | Strategic, mostly reactive; only checks escalation queue |

Configurable in `fleet.yaml` or `.env` so organizations can tune them.

## Data flow — Complete picture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        OPERATORS (Telegram)                         │
│    Mike texts EX-001: "400l"    Dave texts KOT28: "8542 hours"     │
└─────────────┬───────────────────────────────────┬───────────────────┘
              │                                   │
              ▼                                   ▼
┌─────────────────────┐              ┌─────────────────────┐
│   Asset Agent       │              │   Asset Agent       │
│   EX-001            │              │   KOT28             │
│                     │              │                     │
│   Skills:           │              │   Skills:           │
│   - fuel-logger     │              │   - meter-reader    │
│   - nudger          │              │   - nudger          │
│   - memory-curator  │              │   - memory-curator  │
│                     │              │                     │
│   Writes:           │              │   Writes:           │
│   → MEMORY.md       │              │   → MEMORY.md       │
│   → Redis streams   │              │   → Redis streams   │
└─────────┬───────────┘              └─────────┬───────────┘
          │                                    │
          │    Redis (fleet:asset:*:*)          │
          ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                            REDIS                                    │
│                                                                     │
│  fleet:asset:EX-001:fuel    (STREAM)   ◄── fuel events              │
│  fleet:asset:EX-001:state   (HASH)     ◄── current state            │
│  fleet:asset:KOT28:meter    (STREAM)   ◄── meter events             │
│  fleet:asset:EX-001:inbox   (STREAM)   ──► maintenance acks         │
│  fleet:index:active          (SET)     ◄── [EX-001, KOT28, ...]    │
│  fleet:escalations           (STREAM)  ◄── escalation events        │
│  fleet:directives            (STREAM)  ◄── fleet directives         │
└─────────┬──────────────────────────────────────────┬────────────────┘
          │                                          │
          ▼                                          ▼
┌──────────────────────────┐          ┌──────────────────────────────┐
│   CLAWVISOR              │          │   CLAWORDINATOR              │
│                          │          │                              │
│   Skills:                │          │   Skills:                    │
│   - compliance-tracker   │          │   - asset-onboarder          │
│   - anomaly-detector     │          │   - fleet-director           │
│   - maintenance-logger   │          │   - escalation-resolver      │
│   - escalation-handler   │          │   - fleet-config             │
│   - memory-curator       │          │   - memory-curator           │
│                          │          │                              │
│   Reads all asset data   │          │   Docker control             │
│   Writes: maintenance,   │          │   Writes: directives,        │
│   alerts, escalations,   │          │   lifecycle, indexes,        │
│   inbox messages         │          │   skill deployment           │
└──────────┬───────────────┘          └──────────────┬───────────────┘
           │                                         │
           ▼                                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      STAKEHOLDERS (Telegram)                        │
│                                                                     │
│  Mechanic: "replaced hyd pump on EX-001"     (→ Clawvisor)         │
│  Foreman: "who hasn't done pre-ops?"          (→ Clawvisor)         │
│  Supervisor: "compliance this week?"          (→ Clawvisor)         │
│  Manager: "add new CAT 390F, ID EX-005"      (→ Clawordinator)     │
│  Owner: "cost per ton moved this month?"      (→ Clawordinator)     │
└─────────────────────────────────────────────────────────────────────┘
```

## Deployment

### Prerequisites

- Linux server or VM with Docker and Docker Compose
- 16-32GB RAM (for ~64 asset agents + Clawvisor + Clawordinator + Redis)
- One Telegram bot token per agent (each asset + Clawvisor + Clawordinator)
- Fireworks API key (or other LLM provider configured in OpenClaw)

### Five steps from zero to running fleet

1. **Fill in `fleet.yaml`** with your fleet roster, escalation contacts, and any custom settings
2. **Run `generate-configs.py`** → produces workspaces (minimal SOUL.md per agent), openclaw.json configs, docker-compose.yml, .env template, and setup-redis.sh
3. **Fill in `.env`** with Telegram bot tokens, Redis URL, API keys, and escalation contact Telegram IDs
4. **Run `setup-redis.sh`** → creates consumer groups for all asset streams
5. **`docker compose up`** → fleet is live. Each agent creates its own MEMORY.md on first operator interaction.

### What generate-configs produces

```
output/
├── workspaces/
│   ├── EX-001/
│   │   ├── SOUL.md          # Vanilla OpenClaw + "You are EX-001. Serial: CAT0390..."
│   │   └── MEMORY.md        # Empty (agent populates on first session)
│   ├── KOT28/
│   │   ├── SOUL.md
│   │   └── MEMORY.md
│   ├── clawvisor/
│   │   ├── SOUL.md          # "You are Clawvisor."
│   │   └── MEMORY.md
│   └── clawordinator/
│       ├── SOUL.md          # "You are Clawordinator."
│       └── MEMORY.md
├── docker-compose.yml       # One service per agent + Redis
├── .env.template            # All required variables with placeholders
└── setup-redis.sh           # One-time consumer group creation
```

### Volume structure

```
host/
├── workspaces/{ASSET_ID}/   # SOUL.md + MEMORY.md (read-write, per agent)
├── skills/                  # Skill files (read-only mounts to all agents)
├── redis-data/              # Redis persistence (RDB snapshots)
└── .env                     # Credentials and configuration
```

### Permission model

No Gatekeeper service in Tier 1. Permission control via Telegram:

- Each asset agent has its own bot → only operators added to that bot can message it
- Clawvisor has its own bot → add mechanics, foremen, supervisors, safety reps, managers, owners
- Clawordinator has its own bot → add safety reps, managers, owners only

For Tier 2 deployments needing programmable permissions, organizations can build a gateway skill or custom middleware.

### Scaling

| Fleet size | Deployment |
|-----------|-----------|
| Up to ~100 assets | Single host, single Redis instance |
| 100-500 assets | Multi-host, shared Redis, zone-based Clawvisor instances |
| 500+ assets | Multiple Redis instances, regional Clawordinator, custom architecture |

The multi-host model is supported by `fleet.yaml`'s `hosts` section. Each host runs a subset of asset agents pointing to a shared Redis. Clawvisor and Clawordinator can run on any host.
