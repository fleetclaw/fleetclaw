# Scheduling

OpenClaw has three scheduling mechanisms. FleetClaw uses heartbeat as the primary one.

## Heartbeat

### How it works

Heartbeat runs agent turns at a fixed interval (setTimeout, not setInterval). Each tick reads HEARTBEAT.md and follows it strictly.

Gating by HEARTBEAT.md:
- **Effectively empty** (every line is blank, a markdown header, or an empty checkbox) — tick skipped, no LLM call made
- **Real content** — tick runs normally
- **Missing file** — tick runs (OpenClaw default behavior)

Default prompt: "Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK."

### HEARTBEAT_OK response contract

- If the agent replies with HEARTBEAT_OK and the remainder is 300 characters or less, it is treated as an acknowledgment — suppressed, no message sent to the operator
- Duplicate responses within 24 hours are suppressed
- Tick is skipped if the main queue has requests in-flight (retries after 1 second)

### HEARTBEAT.md

The file that drives heartbeat behavior. The agent reads it on each tick and follows it strictly.

- Must have real content (not just comments, headers, or empty checkboxes) or ticks are skipped
- Keep concise — roughly 4 lines — to minimize prompt bloat
- Templates live in `templates/heartbeat-{role}.md`

See `docs/implementation.md` for how to populate HEARTBEAT.md during setup.

### activeHours

Restricts heartbeats to operational hours, preventing off-shift API costs.

Config path: `agents.defaults.heartbeat.activeHours`

```json
"activeHours": {
  "start": "06:00",
  "end": "20:00",
  "timezone": "America/Moncton"
}
```

- `start` — HH:MM, inclusive
- `end` — HH:MM, exclusive (24:00 allowed for end-of-day)
- `timezone` — IANA format (e.g., `America/Moncton`), `"user"`, or `"local"`

Replace `America/Moncton` with the fleet's operational timezone. Different agent roles can have different active hours if needed (e.g., Clawordinator might run 24h for urgent escalations).

### Console logging

Only `[heartbeat] started` and errors are logged to the console. There is no per-tick console output — check for LLM fetch activity in logs to confirm heartbeats are firing.

## Cron

### How it works

Cron is built into the Gateway process (not OS crontab). Jobs persist in `~/.openclaw/cron/jobs.json` and survive restarts. Consecutive failures trigger exponential backoff: 30s, 1m, 5m, 15m, 60m.

### Schedule types

- `at` — One-shot at an ISO timestamp
- `every` — Fixed millisecond interval
- `cron` — 5-field cron expression with IANA timezone

### Execution modes

- `main` — Enqueues a system event into heartbeat flow (shares session context)
- `isolated` — Fresh `cron:<jobId>` session, supports model/thinking overrides

### FleetClaw default: cron denied

FleetClaw denies cron by default via `tools.deny: ["cron"]`. This prevents agents from creating jobs through tool calls. The cron service still runs and executes existing jobs.

Manual job creation via `openclaw cron add` CLI bypasses the tool deny list. See `docs/customization.md` for enabling cron for agents.

## Heartbeat vs cron

| Use case | Mechanism | Why |
|----------|-----------|-----|
| Batch periodic checks | Heartbeat | Context-aware, conversational continuity, low overhead |
| Exact timing | Cron | Precise schedule, not interval-dependent |
| Session isolation | Cron | Fresh session, model overrides |
| One-shot reminders | Cron | `at` type fires once |
| Noisy/frequent tasks | Cron (isolated) | Avoids cluttering main session |
| Routine awareness | Heartbeat | Reads HEARTBEAT.md checklist, follows mounted skills |

They are complementary, not alternatives. Best practice: heartbeat for routine awareness, cron for precise schedules.

## Outbox archival (OS cron job)

### Why

Every fuel log, meter reading, pre-op, and issue report is an outbox file that never gets cleaned up on its own. A single asset can produce 10+ files per shift, so disk usage grows without bound.

### What it does

A nightly OS cron job archives in two phases:

1. **Archive** — Moves outbox files older than the retention period (default: 30 days) from `outbox/` to `outbox-archive/YYYY-MM/`
2. **Compress** — Compresses `outbox-archive/` month directories older than 90 days into `.tar.gz` archives (Linux/macOS) or `.zip` archives (Windows)

The `.clawvisor-last-read` marker file is always excluded — it must remain in `outbox/` for Clawvisor's read tracking. See `docs/communication.md` for the marker file protocol.

### Default retention: 30 days

The 30-day default matches the `anomaly-detector` skill, which scans 30 days of issue-type outbox files for recurrence patterns. Shorter retention breaks anomaly detection — only shorten it if your deployment doesn't use that skill.

| Retention | Use case | Trade-off |
|-----------|----------|-----------|
| 7 days | Small fleets, limited storage | Breaks anomaly-detector recurrence scanning |
| 30 days | Default | Covers anomaly detection + monthly reporting |
| 90+ days | Compliance-heavy organizations | Higher disk usage, full audit trail |

### Why OS cron, not OpenClaw cron

This is an OS-level cron job (crontab on Linux/macOS, Task Scheduler on Windows), not an OpenClaw cron job. Reasons:

- **No LLM reasoning needed** — archival is a deterministic file operation
- **Runs as root** — needs filesystem write access across agent home directories
- **Exact timing** — runs once nightly at a fixed time, not on a heartbeat interval
- **No API cost** — no LLM call for a simple file operation

OpenClaw cron is for tasks that need agent reasoning. OS cron is for deterministic filesystem tasks.

### Setup

See the platform docs for OS-specific crontab entries, scripts, and Task Scheduler commands:

- `platform/ubuntu.md` — crontab + bash
- `platform/macos.md` — crontab + bash
- `platform/windows.md` — Task Scheduler + PowerShell

## Skills — not scheduled

Skills are instructional markdown loaded on demand. They have no scheduling component — skills are triggered by messages, heartbeat prompts, or cron events. The heartbeat prompt causes the agent to read HEARTBEAT.md, which references skill behaviors.
