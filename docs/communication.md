# Filesystem Communication Protocol

How FleetClaw agents exchange data through inbox and outbox directories.

## Overview

Every agent has two communication directories in its workspace:

- **`outbox/`** — Files the agent writes to share data with other agents
- **`inbox/`** — Files other agents write to send messages to this agent

These directories replace centralized data stores. Each file is a self-contained message with YAML frontmatter (structured metadata) and a markdown body (human-readable content).

## Directory locations

```
~/.openclaw/workspace/
├── inbox/              # Messages TO this agent
├── outbox/             # Messages FROM this agent
├── outbox-archive/     # Archived outbox files (YYYY-MM/ subdirectories)
├── SOUL.md             # Agent identity
└── MEMORY.md           # Curated working memory
```

## Message format

Every message file uses YAML frontmatter followed by a markdown body:

```markdown
---
from: EX-001
type: fuel
timestamp: 2026-02-09T06:12:00-04:00
---
liters: 400
meter_at_fill: 12847
burn_rate: 13.2
status: normal
```

### Required frontmatter fields

| Field | Description | Example |
|-------|-------------|---------|
| `from` | Agent ID of the writer | `EX-001`, `clawvisor`, `clawordinator` |
| `type` | Message category | `fuel`, `meter`, `preop`, `issue`, `maintenance_ack`, `escalation`, `directive` |
| `timestamp` | ISO 8601 with timezone | `2026-02-09T06:12:00-04:00` |

### Optional frontmatter fields

Skills may add additional frontmatter fields relevant to the message type (e.g., `severity`, `asset_id`, `scope`). The body contains the message payload in plain key-value or prose format.

## Filename convention

```
{ISO-timestamp}_{type}.md
```

Colons in the timestamp are replaced with hyphens for filesystem compatibility:

```
2026-02-09T06-12-00_fuel.md
2026-02-09T14-30-00_preop.md
2026-02-09T08-45-22_maintenance_ack.md
```

Files sort chronologically by default. The combination of timestamp + type makes filenames unique for a single writer. Different agents writing to the same inbox have different `from` fields, and sub-second collisions between independent writers are not a practical concern.

## Who writes where

### Asset agents

- Write to their own `outbox/` — fuel logs, meter readings, pre-ops, issue reports
- Read their own `inbox/` — maintenance acknowledgments, directives
- Update their own `## State` section in AGENTS.md — current operational state

### Clawvisor

- Reads all asset agents' `outbox/` directories on heartbeat
- Writes to asset agents' `inbox/` — maintenance acknowledgments, alerts
- Writes to its own `outbox/` — escalations, maintenance records, anomaly alerts
- Reads its own `inbox/` — escalation resolutions from Clawordinator
- Reads `fleet.md` — fleet composition

### Clawordinator

- Writes to any agent's `inbox/` — directives, lifecycle commands
- Writes to its own `outbox/` — directive audit records, lifecycle actions
- Reads its own `inbox/` — escalations from Clawvisor
- Reads and writes `fleet.md` — fleet composition (sole writer)

## Read tracking

Clawvisor needs to know which outbox files it has already processed. Each asset's outbox directory contains a marker file:

```
~/.openclaw/workspace/outbox/.clawvisor-last-read
```

This file contains a single ISO timestamp — the timestamp of the last outbox file Clawvisor processed. On each heartbeat, Clawvisor:

1. Reads the marker timestamp
2. Lists outbox files with timestamps newer than the marker
3. Processes new files
4. Updates the marker to the newest processed timestamp

If the marker file doesn't exist, Clawvisor processes all files in the outbox.

## Message lifecycle

### Outbox files

1. **New** — Agent writes the file to its outbox
2. **Processed** — Clawvisor (or another reader) has read it; marker updated past its timestamp
3. **Archived** — A nightly OS cron job moves files older than the retention period (default: 30 days) to `outbox-archive/YYYY-MM/`. Month directories older than 90 days are compressed.

The `.clawvisor-last-read` marker file is never archived — it must remain in `outbox/` for read tracking. See `docs/scheduling.md` for the archival model.

### Inbox files

1. **New** — Another agent writes the file to this agent's inbox
2. **Read** — Agent processes it on session start or heartbeat
3. **Deleted or archived** — Agent removes or archives the file after processing to prevent re-reading

Asset agents should process and remove inbox files on session start. Clawvisor and Clawordinator process inbox files on heartbeat.

## Escalation routing

Clawvisor writes escalation files to Clawordinator's inbox directory. This requires an ACL grant allowing the Clawvisor user to write to Clawordinator's inbox (see `docs/permissions.md`).

```
Clawvisor writes: ~fc-clawordinator/.openclaw/workspace/inbox/2026-02-09T10-30-00_escalation.md
Clawvisor also writes: own outbox/2026-02-09T10-30-00_escalation.md (audit copy)
```

**Alternative pattern:** If cross-user inbox writes are not desirable, Clawordinator can instead read Clawvisor's outbox directory for escalation-type files (requires Clawordinator to have read access to Clawvisor's outbox). Document whichever approach the deployment uses in the fleet's operational notes.

## fleet.md — The fleet registry

`fleet.md` is a shared file readable by all agents. Only Clawordinator writes it. It serves as the fleet composition index — the equivalent of a registry listing all assets and their status.

Location: a shared path readable by all agents (e.g., `/opt/fleetclaw/fleet.md`). See `docs/permissions.md` for ownership and access rules.

Format:

```markdown
# Fleet Registry

Last updated: 2026-02-09T14:00:00-04:00
Updated by: clawordinator

## Active

| ID | Serial | User | Home |
|----|--------|------|------|
| EX-001 | CAT0390F-2019-A7X | fc-ex001 | /home/fc-ex001 |
| KOT28 | KOM-PC2000-2021-B3 | fc-kot28 | /home/fc-kot28 |

## Idle

| ID | Serial | User | Home | Idled |
|----|--------|------|------|-------|
| DT-012 | CAT0777-2018-K9 | fc-dt012 | /home/fc-dt012 | 2026-01-15 |

## Decommissioned

| ID | Serial | User | Decommissioned |
|----|--------|------|----------------|
| EX-003 | CAT0330-2015-F2 | fc-ex003 | 2025-12-01 |
```

## Per-agent operational state (AGENTS.md)

Each asset agent maintains a `## State` section at the bottom of its AGENTS.md with current operational data. Because OpenClaw auto-loads AGENTS.md into every session, the agent always has its operational state in context — no separate file read needed.

```markdown
## State

status: active
operator: Mike
shift_start: 2026-02-09T06:00:00-04:00
last_fuel_l: 400
last_fuel_ts: 2026-02-09T06:12:00-04:00
burn_rate: 13.2
last_meter: 12847
last_meter_ts: 2026-02-09T06:05:00-04:00
last_preop_ts: 2026-02-09T06:02:00-04:00
last_preop_status: pass
open_issues: 1
```

Fields are flat key-value pairs, one per line. Skills read and update individual fields. The agent's skills update `## State` directly — other agents read it but do not write to it. Clawvisor reads asset AGENTS.md files for the `## State` section.

## Comparison to Redis

For developers familiar with the previous Redis-based architecture:

| Redis concept | Filesystem equivalent |
|---------------|----------------------|
| Stream (`XADD`/`XREAD`) | Outbox directory (timestamped files) |
| Inbox stream | Inbox directory |
| State HASH (`HSET`/`HGET`) | AGENTS.md `## State` (flat key-value) |
| Index SET (`SADD`/`SMEMBERS`) | fleet.md sections (Active/Idle/Decommissioned) |
| Consumer group read position | `.clawvisor-last-read` marker file |
| `XREVRANGE COUNT 10` | Read 10 most recent outbox files (sort by filename) |
| `MAXLEN` trimming | Nightly archival cron job (see `docs/scheduling.md`) |
