# FleetClaw Architecture

## What FleetClaw is

FleetClaw is a skill library and architecture reference that gives every piece of mining equipment its own AI agent. Operators message their machine's agent to log fuel, record meter readings, complete pre-op inspections, and report issues. The system makes compliance feel like a conversation rather than a form.

FleetClaw is built on [OpenClaw](https://openclaw.ai), an open-source framework for persistent AI agents. Each agent runs as its own system user with its own identity, memory, and skills.

FleetClaw is a platform, not a product. The core system provides agent architecture, communication patterns, and operational skills. What those agents actually do is defined by **skills** — swappable markdown instructions that organizations can customize, extend, or replace.

## The three agents

FleetClaw runs three agent roles, each serving a different audience:

```
Operators ──────────────► Asset Agents (one per machine)
                               │
                               │ outbox files
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

One agent per machine. Operators talk to their machine's agent exclusively. The agent accepts messy natural-language input ("400l", "filled up 400", "put 400 in at smoko"), logs it, and provides immediate feedback ("13.2 L/hr, normal range"). Each agent has its own messaging channel connection — operators message the machine directly.

**Audience:** Operators only.

**Skills:** `fuel-logger`, `meter-reader`, `pre-op`, `issue-reporter`, `nudger`, `memory-curator-asset`

### Clawvisor

The fleet oversight agent. Everyone in a supervisory or maintenance role uses Clawvisor. It reads data from all asset agents' outbox directories, tracks compliance, detects anomalies, accepts maintenance logs from mechanics, and generates shift/daily summaries. Clawvisor is read-write — mechanics log completed repairs through it, and that data flows back to asset agents via inbox files.

**Audience:** Mechanics, foremen, supervisors, safety reps, managers, owners.

**Skills:** `fleet-status`, `compliance-tracker`, `maintenance-logger`, `anomaly-detector`, `shift-summary`, `escalation-handler`, `asset-query`, `memory-curator-clawvisor`

### Clawordinator

The command layer. Only people who can change how the fleet operates get access. Clawordinator has process management access — it can onboard new assets (create users, install OpenClaw, start services), decommission old ones (stop and disable services), idle seasonal equipment, and manage skill deployment across the fleet. It receives escalations from Clawvisor and presents them to leadership for decisions.

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

Skills are markdown files that teach agents how to do things. They contain plain English instructions — not code — that the LLM reads and follows. When an agent has multiple skills, it reads all of them and synthesizes the instructions into behavior.

### Skill structure

Every skill follows this pattern:

1. **Trigger** — When does the agent activate this skill? (message, heartbeat, session start, inbox message)
2. **Input** — What data does it consume? (user messages, inbox files, outbox files, state.md, fleet.md, MEMORY.md, .env variables)
3. **Behavior** — Plain English instructions. Not code. Not pseudocode.
4. **Output** — What does it produce? (outbox writes, inbox writes, state.md updates, fleet.md updates, MEMORY.md updates, messages to user, escalation flags)
5. **Overdue Condition** (optional) — When is something missing that the nudger should catch?

See `skills/SKILL-TEMPLATE.md` for the blank template and `docs/skill-authoring.md` for the comprehensive guide.

### The nudger pattern

The nudger is a standalone skill that coordinates reminders across all domain skills. It works through convention:

- **Domain skills** (fuel-logger, meter-reader, pre-op) each define an `## Overdue Condition` section: "No fuel log within 8 hours of the operator's first message this shift."
- **The nudger skill** defines tone, cadence, and rules: one gentle reminder per missing item per shift, never stack multiple nudges.
- **The agent reads both** and synthesizes: "fuel is overdue (from fuel-logger), and I know how to remind (from nudger)."

A Tier 2 skill author building `tire-pressure-logger` just adds their own `## Overdue Condition`, and the nudger automatically picks it up. The convention is the API.

### Skill tiers

**Tier 1 — Ships with FleetClaw.** Works out of the box using filesystem communication and MEMORY.md only. No external integrations. These define the baseline platform experience.

**Tier 2 — Organization-built.** Integrates with external systems via .env credentials (CMMS like SAP PM or Pronto, telematics like CAT Product Link or Komatsu KOMTRAX, fuel management systems). FleetClaw provides the skill template and authoring guide; the organization fills in the integration.

**Tier 3 — Community/advanced.** Extends the platform in ways not anticipated by the core team: voice transcription, predictive analytics, custom dashboards, multi-site management.

### Skill mounting

No skills are shared across agent roles. Each role has its own skill set:

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

OpenClaw's skill discovery determines which skills each agent uses — configured during setup. See `docs/implementation.md` for details.

## Communication model

Agents communicate through filesystem directories — each agent has an inbox and outbox in its workspace. This replaces centralized data stores with a simple, auditable, file-based protocol.

```
Asset Agent writes event → outbox/ (timestamped file)
                         → MEMORY.md (permanent, curated summary)

Clawvisor reads outboxes → aggregates, detects anomalies, reports
Clawordinator reads inbox → fleet-level decisions, lifecycle management
```

### How it works

- **Asset agents** write timestamped files to their own `outbox/` (fuel logs, meter readings, pre-ops, issues). They read their own `inbox/` for messages from Clawvisor or Clawordinator.
- **Clawvisor** reads all asset outbox directories on heartbeat, processes new files (tracked via a `.clawvisor-last-read` marker), and writes to asset inboxes (maintenance acknowledgments) or its own outbox (escalations, alerts).
- **Clawordinator** reads its own inbox (escalations from Clawvisor), writes to any agent's inbox (directives), and manages `fleet.md` (the fleet composition registry).

See `docs/communication.md` for the complete protocol specification — message format, filename conventions, read tracking, and lifecycle.

### The maintenance acknowledgment loop

The inbox/outbox system closes the feedback loop between operators and mechanics:

```
1. Operator tells asset agent: "hydraulics are sluggish"
   → Asset agent writes issue file to its own outbox/

2. Mechanic tells Clawvisor: "replaced hyd pump on EX-001, 6 hours"
   → Clawvisor writes maintenance record to its own outbox/
   → Clawvisor writes maintenance_ack file to EX-001's inbox/

3. Next operator session with EX-001's agent:
   → Agent checks inbox on session start
   → "Heads up — hydraulic pump was replaced yesterday. Monitor temps."
```

This loop is what makes operators keep reporting issues. They see that reporting leads to action.

## Permission model

Each agent runs as its own system user. Filesystem ACLs control what each agent can read and write:

- **Asset agents** — full control of own workspace, read-only access to fleet.md
- **Clawvisor** — read access to all asset outboxes and state files, write access to asset inboxes and Clawordinator's inbox
- **Clawordinator** — write access to any agent inbox, sole writer of fleet.md, scoped sudo for service management

See `docs/permissions.md` for the complete ACL rules, user creation, and auditing commands.

## Shared state — fleet.md

`fleet.md` is the fleet composition registry — a shared file readable by all agents, writable only by Clawordinator. It lists all assets with their status (Active, Idle, Decommissioned), system user, and home directory.

All agents read `fleet.md` to understand fleet composition. Clawordinator updates it when assets are onboarded, idled, woken, or decommissioned.

## Process management

Each agent runs as a system service under its own user. The service management system (systemd on Linux, launchd on macOS, NSSM on Windows) handles:

- Starting agents on boot
- Restarting on crash
- Resource limits (memory, CPU)
- Log management

Clawordinator has scoped sudo access to manage agent services — it can start, stop, and restart individual agents without root access to anything else.

See `platform/ubuntu.md`, `platform/macos.md`, or `platform/windows.md` for platform-specific service configuration.

## MEMORY.md — The permanent record

MEMORY.md is the agent's hot cache — curated context loaded at session start. It passes this test: "Would I need this in the first 10 seconds of a conversation?"

### The 15,000 character constraint

FleetClaw sets `agents.defaults.bootstrapMaxChars` to 15,000 characters (down from OpenClaw's 20,000 default) to leave headroom for skills context. Each agent role has a dedicated memory-curator skill that defines structure, pruning rules, and character budgets.

### Per-agent-role design

**Asset agent MEMORY.md** — Target: under 5,000 characters.

```
## Current Shift        — Who's operating, what's been logged/nudged
## Recent Context       — Last 5 fuel logs, last 3 meters, open issues
## Operator Patterns    — Regular operators' habits and preferences
## Learned Patterns     — Normal burn rates, fueling frequency
## Open Items           — Unresolved issues awaiting maintenance
```

**Clawvisor MEMORY.md** — Target: under 8,000 characters. Hard ceiling: 15,000.

Clawvisor's memory is an **exception report, not an inventory**. Only assets with active problems appear. Healthy assets are tracked in outbox files.

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
## Fleet Composition    — Active/idle counts
## Pending Escalations  — Unresolved, from Clawvisor
## Pending Directives   — Active, with acknowledgment status
## Recent Actions       — Last 10 lifecycle/deployment actions
## Skill Deployment     — What's mounted where
```

### Shift detection

Asset agents detect shift changes via messaging user ID: a different user messaging after a 2+ hour gap triggers a new shift. This resets nudge tracking, expects a new pre-op, and delivers any pending maintenance acknowledgments to the new operator. No shift configuration needed — it works for 8h, 10h, 12h, or irregular shifts.

Fallback: same operator active >14 hours = new shift period for nudge/pre-op purposes.

## Heartbeat intervals

Each agent role has a different heartbeat cadence matching its operational rhythm:

| Agent | Interval | Rationale |
|-------|----------|-----------|
| Asset agents | 30 min | Operator-facing; nudges need to land mid-shift |
| Clawvisor | 2 hr | Oversight cadence; mechanic updates need reasonable freshness |
| Clawordinator | 4-8 hr | Strategic, mostly reactive; only checks escalation queue |

Configurable per organization. See `docs/customization.md` for tuning guidance.

## Data flow — Complete picture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OPERATORS (messaging channel)                     │
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
│   → outbox/ files   │              │   → outbox/ files   │
│   → state.md        │              │   → state.md        │
└─────────┬───────────┘              └─────────┬───────────┘
          │                                    │
          │  Clawvisor reads outbox/ dirs      │
          ▼                                    ▼
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
│   Reads asset outboxes   │          │   Process management access  │
│   Writes: inbox files,   │          │   Writes: directives,        │
│   escalations, alerts    │          │   lifecycle, fleet.md        │
└──────────┬───────────────┘          └──────────────┬───────────────┘
           │                                         │
           ▼                                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  STAKEHOLDERS (messaging channel)                    │
│                                                                     │
│  Mechanic: "replaced hyd pump on EX-001"     (→ Clawvisor)         │
│  Foreman: "who hasn't done pre-ops?"          (→ Clawvisor)         │
│  Supervisor: "compliance this week?"          (→ Clawvisor)         │
│  Manager: "add new CAT 390F, ID EX-005"      (→ Clawordinator)     │
│  Owner: "cost per ton moved this month?"      (→ Clawordinator)     │
└─────────────────────────────────────────────────────────────────────┘
```

## Scaling considerations

| Fleet size | Deployment |
|-----------|-----------|
| Up to ~100 assets | Single host, filesystem communication |
| 100-500 assets | Multi-host with shared filesystem (NFS) or rsync for outbox/inbox replication |
| 500+ assets | Regional Clawvisor instances, sharded asset directories, custom architecture |

For multi-host deployments, shared NFS mounts for outbox directories allow Clawvisor to read asset data across hosts. Skills remain identical — only the filesystem paths change.
