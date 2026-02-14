# FleetClaw Implementation Guide

How to set up FleetClaw on a server. This document complements `architecture.md` (the what) with the how. Read `architecture.md` first.

## Prerequisites

- A server or machine (Ubuntu 24.04 LTS recommended — see `platform/ubuntu.md`)
- Node.js 22+ (required by OpenClaw)
- Git
- A coding agent or admin who can follow these instructions

## Overview

Setting up a FleetClaw deployment involves:

1. Create system users for each agent
2. Install OpenClaw per user
3. Inject FleetClaw customizations (SOUL.md, HEARTBEAT.md, skills, inbox/outbox, configuration)
4. Set filesystem permissions (ACLs)
5. Create and start system services
6. Configure fleet.md
7. Set up messaging channel connections
8. Set up outbox archival cron job

## SOUL.md and OpenClaw workspaces

OpenClaw agents read their identity from a workspace directory at `~/.openclaw/workspace`. FleetClaw puts two files there:

- **SOUL.md** — The agent identity template with injected values. For asset agents: `{ASSET_ID}` and `{SERIAL}`. For Clawvisor and Clawordinator: just their name.
- **MEMORY.md** — Not created during setup. OpenClaw auto-creates it on the first agent session. The memory-curator skills define its structure and pruning rules.

The `agents.defaults.skipBootstrap: true` setting in openclaw.json prevents OpenClaw from overwriting SOUL.md with its default template on first run.

## Per-user OpenClaw installation

Each agent runs as its own system user. For each agent:

1. **Create the system user** — See the platform doc for exact commands. User belongs to the `fc-agents` group.
2. **Install OpenClaw as that user** — Run `openclaw onboard --install-daemon` under the agent's user account. This sets up the OpenClaw runtime in `~/.openclaw/`.
3. **Verify** — The `~/.openclaw/` directory should contain `dist/`, `openclaw.json`, and `workspace/`.

## Upgrading OpenClaw

All agents on a host share the same globally-installed OpenClaw binary (`/usr/bin/openclaw` on Linux, `/usr/local/bin/openclaw` on macOS, `openclaw.cmd` on Windows). Upgrading the global package upgrades every agent simultaneously — no per-agent updates needed.

### Upgrade procedure

1. **Check current version:**
   ```bash
   openclaw --version
   ```

2. **Stop all agent services on the host.** Stop everything first, then start everything after — this avoids relay port race conditions (see "System service configuration" below for why). See the platform docs for OS-specific stop commands.

3. **Update the global package:**
   ```bash
   sudo npm install -g openclaw@<version>
   ```
   Use `openclaw@latest` for the latest stable release, or pin a specific version. Alternatively: `sudo npm update -g openclaw`.

4. **Verify new version:**
   ```bash
   openclaw --version
   ```

5. **Start all agent services.** See the platform docs for OS-specific start commands.

6. **Verify services are running.** Gateway warmup takes 3-4 minutes while TypeScript plugins compile — services may report as active before the agent is fully responsive. Check logs to confirm the gateway is ready.

### Rollback

Same procedure: stop services, install the previous version (`sudo npm install -g openclaw@<previous-version>`), start services.

### Breaking changes

Check OpenClaw release notes before upgrading. If a release changes config format, update all agents' `openclaw.json` files while services are stopped.

### What doesn't change

For non-breaking upgrades, `openclaw.json` and service configuration files (systemd units, launchd plists, NSSM settings) remain unchanged. ExecStart points to the global binary, which npm replaces in-place.

## FleetClaw injection

After OpenClaw is installed, customize each agent's workspace:

### 1. Replace SOUL.md

Copy the appropriate template from `templates/` and substitute placeholders:

- **Asset agents:** Copy `templates/soul-asset.md` → `~/.openclaw/workspace/SOUL.md`. Replace `{ASSET_ID}` and `{SERIAL}` with actual values.
- **Clawvisor:** Copy `templates/soul-clawvisor.md` → `~/.openclaw/workspace/SOUL.md`.
- **Clawordinator:** Copy `templates/soul-clawordinator.md` → `~/.openclaw/workspace/SOUL.md`.

### 2. Create inbox and outbox directories

```bash
mkdir -p ~/.openclaw/workspace/inbox
mkdir -p ~/.openclaw/workspace/outbox
```

### 3. Add `## State` to AGENTS.md (asset agents only)

Append an initial `## State` section to the asset agent's `~/.openclaw/workspace/AGENTS.md`:

```markdown
## State

status: active
```

Skills will populate additional fields during operation. Because OpenClaw auto-loads AGENTS.md into every session, the agent always has its operational state in context.

### 4. Populate HEARTBEAT.md

OpenClaw skips heartbeat ticks when HEARTBEAT.md is effectively empty (only blank lines, headers, or empty checkboxes). Copy the appropriate template to activate heartbeats:

- **Asset agents:** Copy `templates/heartbeat-asset.md` → `~/.openclaw/workspace/HEARTBEAT.md`
- **Clawvisor:** Copy `templates/heartbeat-clawvisor.md` → `~/.openclaw/workspace/HEARTBEAT.md`
- **Clawordinator:** Copy `templates/heartbeat-clawordinator.md` → `~/.openclaw/workspace/HEARTBEAT.md`

Keep HEARTBEAT.md concise — a short checklist that tells the agent what to check on each tick. The agent reads it strictly and replies HEARTBEAT_OK (suppressed — no message sent) if nothing needs attention. See `docs/scheduling.md` for the full heartbeat model.

### 5. Link skills

OpenClaw discovers skills from directories listed in `skills.load.extraDirs` in openclaw.json. Point it to the shared skills directory where FleetClaw skills are installed:

```json
"skills": {
  "load": {
    "extraDirs": ["/opt/fleetclaw/skills"]
  }
}
```

Alternatively, symlink the relevant skill directories into the agent's workspace skills directory:

```bash
mkdir -p ~/.openclaw/workspace/skills
ln -s /opt/fleetclaw/skills/fuel-logger ~/.openclaw/workspace/skills/fuel-logger
ln -s /opt/fleetclaw/skills/meter-reader ~/.openclaw/workspace/skills/meter-reader
# ... etc for each skill this agent role uses
```

### 6. Tune openclaw.json

Key settings to configure after onboard:

```json
{
  "port": 7600,
  "agents": {
    "defaults": {
      "skipBootstrap": true,
      "bootstrapMaxChars": 15000,
      "heartbeat": {
        "every": "30m",
        "activeHours": {
          "start": "06:00",
          "end": "20:00",
          "timezone": "America/Moncton"
        }
      },
      "sandbox": {
        "mode": "off"
      },
      "model": {
        "primary": "fireworks/accounts/fireworks/models/<model>"
      },
      "models": {
        "fireworks/accounts/fireworks/models/<model>": { "alias": "Model Name" }
      },
      "compaction": {
        "mode": "safeguard",
        "memoryFlush": {
          "softThresholdTokens": 4000
        }
      }
    }
  },
  "models": {
    "mode": "merge",
    "providers": {
      "fireworks": {
        "baseUrl": "https://api.fireworks.ai/inference/v1",
        "apiKey": "${FIREWORKS_API_KEY}",
        "api": "openai-completions",
        "models": [
          {
            "id": "accounts/fireworks/models/<model>",
            "name": "Model Name",
            "reasoning": true,
            "input": ["text", "image"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072,
            "maxTokens": 32768
          }
        ]
      }
    }
  },
  "tools": {
    "deny": ["browser", "canvas", "nodes", "cron"]
  },
  "skills": {
    "load": {
      "extraDirs": ["/opt/fleetclaw/skills"]
    }
  }
}
```

Replace `<model>` with the actual model path (e.g., `accounts/fireworks/models/kimi-k2p5`). Any OpenAI-compatible provider (Together, Groq, Ollama) works the same way — change `baseUrl`, `apiKey`, and model details. Set `cost` values to actual provider pricing for cost tracking; zeros disable tracking. Use `reasoning: true` for models that support chain-of-thought.

If the model supports vision, include `"image"` in the `input` array so OpenClaw routes photos directly to the primary model. If the model is text-only, use `["text"]` — OpenClaw will fall back to `imageModel` if configured.

The `agents.defaults.models` allowlist is required alongside `model.primary` — without it, the model may resolve on cold start but 404 on subsequent calls. The `models.mode: "merge"` setting is required for custom providers.

**Port configuration:** Set `port` at the root level of openclaw.json (not on the CLI). Each agent needs a unique port. OpenClaw's browser extension relay opens at exactly `gateway_port + 3` (browser control at `+2`, relay at `+3`). With sequential ports, agent N's relay collides with agent N+3's gateway. Space ports with gaps of 4+ or use non-sequential assignments.

Omitting `prompt` from the heartbeat config uses the OpenClaw default, which reads HEARTBEAT.md and follows it strictly. If nothing needs attention the agent replies HEARTBEAT_OK (suppressed — no message sent to the operator).

`activeHours` prevents heartbeat API calls outside operational hours. `start` is inclusive, `end` is exclusive (24:00 allowed), and `timezone` is IANA format. Replace `America/Moncton` with the fleet's operational timezone.

Adjust `agents.defaults.heartbeat.every` per agent role:
- Asset agents: `"30m"`
- Clawvisor: `"2h"`
- Clawordinator: `"4h"`

`activeHours` should match the fleet's operational schedule. Different roles can have different active hours if needed (e.g., Clawordinator might run 24h for urgent escalations).

## fleet.md format and ownership

fleet.md is the fleet composition registry. Create it during initial setup:

```markdown
# Fleet Registry

Last updated: {ISO timestamp}
Updated by: clawordinator

## Active

| ID | Serial | User | Home |
|----|--------|------|------|

## Idle

| ID | Serial | User | Home | Idled |
|----|--------|------|------|-------|

## Decommissioned

| ID | Serial | User | Decommissioned |
|----|--------|------|----------------|
```

**Location:** `/opt/fleetclaw/fleet.md` (Linux/macOS) or `C:\FleetClaw\fleet.md` (Windows).

**Ownership:** Clawordinator user owns it, `fc-agents` group has read access. See `docs/permissions.md`.

Clawordinator updates fleet.md via its skills (asset-onboarder, asset-lifecycle). All agents read it for fleet composition awareness.

## AGENTS.md `## State` format

Each asset agent maintains a `## State` section in its AGENTS.md with flat key-value pairs:

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

Skills update specific fields. Because OpenClaw auto-loads AGENTS.md into every session, the agent always has its operational state in context without parsing outbox history.

## System service configuration

Each agent runs as a system service. See the platform docs for full templates:

- **Linux:** systemd unit files — `platform/ubuntu.md`
- **macOS:** launchd plists — `platform/macos.md`
- **Windows:** NSSM services — `platform/windows.md`

Key settings across all platforms:

| Setting | Asset agents | Clawvisor | Clawordinator |
|---------|-------------|-----------|---------------|
| Memory limit | 1 GB | 1.5 GB | 1.5 GB |
| Restart policy | On failure | On failure | On failure |
| Restart delay | 10 seconds | 10 seconds | 10 seconds |

Service start commands should use `openclaw gateway --force` (the `--force` flag kills stale port listeners on startup — this is the fix for orphaned gateway processes that survive service restarts). Port is configured in `openclaw.json` (root-level `port` key), not on the CLI.

On Linux with `ProtectSystem=strict`, add `PrivateTmp=no` and include `/tmp` in `ReadWritePaths` — OpenClaw writes lock files to `/tmp/openclaw-*/`. Do NOT use `PrivateTmp=true` — it isolates /tmp, breaking `--force` which uses `lsof` on the real /tmp.

When restarting multiple agents on the same host, stop all first, wait for ports to clear, then start all — prevents relay port race conditions.

## Clawordinator sudo access

Clawordinator needs to manage agent services. On Linux, create a sudoers file granting scoped access:

```
# /etc/sudoers.d/fc-clawordinator
fc-clawordinator ALL=(root) NOPASSWD: /usr/bin/systemctl stop fc-agent-*
fc-clawordinator ALL=(root) NOPASSWD: /usr/bin/systemctl start fc-agent-*
fc-clawordinator ALL=(root) NOPASSWD: /usr/bin/systemctl enable fc-agent-*
fc-clawordinator ALL=(root) NOPASSWD: /usr/bin/systemctl disable fc-agent-*
fc-clawordinator ALL=(root) NOPASSWD: /usr/bin/systemctl restart fc-agent-*
```

See the platform docs for macOS and Windows equivalents.

## Environment files

Each agent needs an environment file with secrets and configuration:

```bash
# /opt/fleetclaw/env/{id}.env
FIREWORKS_API_KEY=your-key-here
TELEGRAM_BOT_TOKEN=your-bot-token-here
FLEET_MD_PATH=/opt/fleetclaw/fleet.md
NODE_OPTIONS=--max-old-space-size=768
```

Use `--max-old-space-size=1024` for Clawvisor and Clawordinator (they process data from multiple asset outboxes).

**Permissions:** Owner-only read (chmod 600), owned by the agent's system user. The service management system loads this file at service start.

Never commit env files to version control.

## Messaging channel setup

The messaging plugin is disabled by default. Each agent needs its channel enabled and configured individually:

1. **Enable the messaging plugin** (run as the agent user):
   ```bash
   openclaw plugins enable telegram
   ```

2. **Add the channel with the bot token:**
   ```bash
   openclaw channels add --channel telegram --token <token>
   ```

3. **Restart the agent service** after enabling the plugin.

4. **Pair users** — after channel setup, users must be paired: the user messages the bot, gets a pairing code, then an admin approves it:
   ```bash
   openclaw pairing approve telegram <code>
   ```

Each agent needs its own channel connection with its own bot token.

**Important:** CLI commands run via `sudo su` don't load the systemd EnvironmentFile. Source the env file first:
```bash
source /opt/fleetclaw/env/{id}.env && openclaw <command>
```

## Key OpenClaw config options

| Option | Value | Why |
|--------|-------|-----|
| `agents.defaults.skipBootstrap` | `true` | Don't overwrite generated SOUL.md |
| `agents.defaults.bootstrapMaxChars` | `15000` | Leave headroom for skills context |
| `agents.defaults.heartbeat.every` | `"30m"` | Asset heartbeat interval (adjust per role) |
| `agents.defaults.heartbeat.activeHours` | `{start, end, timezone}` | Suppress heartbeats outside operational hours |
| `agents.defaults.sandbox.mode` | `"off"` | No code execution sandboxing needed |
| `agents.defaults.compaction.mode` | `"safeguard"` | Default compaction mode |
| `agents.defaults.compaction.memoryFlush.softThresholdTokens` | `4000` | Trigger memory flush early |
| `models.mode` | `"merge"` | Required for custom providers |
| `tools.deny` | `["browser","canvas","nodes","cron"]` | Fleet agents don't need these |
| `skills.load.extraDirs` | `["/opt/fleetclaw/skills"]` | Tell OpenClaw where skills are |
| `port` | unique per agent | Avoid gateway and relay port collisions |

## Cost implications

Each heartbeat is a full agent turn (~5K-15K input tokens). Budget at scale:

| Fleet size | Heartbeats/day (24h) | With activeHours (06:00-20:00) |
|-----------|---------------------|-------------------------------|
| 10 assets | ~500 | ~290 |
| 50 assets | ~2,500 | ~1,450 |
| 100 assets | ~4,800 | ~2,800 |

`activeHours` reduces daily heartbeat counts — a 06:00-20:00 window cuts asset heartbeats from ~48/day to ~28/day per agent. Heartbeat interval is the primary cost control lever — set longer intervals for agents that don't need frequent checks. Plus Clawvisor and Clawordinator heartbeats, plus operator-initiated conversations.

## Outbox archival

A nightly OS cron job archives outbox files older than the retention period (default: 30 days) and compresses old month directories. See `docs/scheduling.md` for the archival model (retention tiers, why OS cron) and the platform docs for setup commands:

- `platform/ubuntu.md` — crontab + bash
- `platform/macos.md` — crontab + bash
- `platform/windows.md` — Task Scheduler + PowerShell

## Operational considerations

### Secrets management

Env files contain sensitive credentials (messaging tokens, API keys). For production:

- Never commit env files to version control
- Restrict file permissions to owner-only read
- Rotate API keys periodically
- Each messaging token is unique per agent — a compromised token only affects one agent

### Monitoring

- Service status: `systemctl status fc-agent-*` (Linux)
- Logs: `journalctl -u fc-agent-ex001 -f` (Linux)
- Outbox file counts: quick indicator of agent activity
- `## State` timestamps in AGENTS.md: detect stale agents

### Log management

System service managers handle log rotation by default. For additional control on Linux, configure journald limits. See `platform/ubuntu.md`.

### Resource limits

Memory and CPU limits are set in the service configuration. OpenClaw agents typically use 300-500 MB of memory under normal load. Asset agents need 1 GB MemoryMax; supervisory agents (Clawvisor, Clawordinator) need 1.5 GB due to larger working sets from processing multiple asset outboxes. Set `NODE_OPTIONS=--max-old-space-size=768` (assets) or `--max-old-space-size=1024` (supervisory) in the env file.

### Kernel tuning (Linux)

OpenClaw uses inotify for file watching. For fleets with many agents:

```bash
echo "fs.inotify.max_user_instances=8192" >> /etc/sysctl.conf
echo "fs.inotify.max_user_watches=524288" >> /etc/sysctl.conf
sysctl -p
```

### Host sizing

| Fleet size | RAM | CPU | Disk |
|-----------|-----|-----|------|
| 10 assets | 8 GB | 4 cores | 50 GB SSD |
| 50 assets | 16 GB | 8 cores | 100 GB SSD |
| 100 assets | 32 GB | 16 cores | 200 GB SSD |

## Setup checklist

For a new fleet deployment:

- [ ] Install Node.js 22+
- [ ] Create `fc-agents` group
- [ ] Create system user per agent
- [ ] Install OpenClaw per user (`openclaw onboard --install-daemon`)
- [ ] Copy SOUL.md templates with substitutions
- [ ] Populate HEARTBEAT.md from templates per agent role
- [ ] Create inbox/outbox directories per agent
- [ ] Add `## State` section to AGENTS.md for asset agents
- [ ] Install skills to shared directory
- [ ] Configure skill discovery in openclaw.json
- [ ] Tune openclaw.json (agents.defaults: heartbeat, bootstrapMaxChars, model)
- [ ] Enable messaging plugin and add channel per agent
- [ ] Pair/authorize users via openclaw pairing approve
- [ ] Configure LLM provider in openclaw.json (models.providers)
- [ ] Set up fleet.md with initial fleet roster
- [ ] Set ACLs (outbox read, inbox write, fleet.md, env files)
- [ ] Configure Clawordinator sudoers
- [ ] Create env files with secrets
- [ ] Create and enable system services
- [ ] Start all services
- [ ] Set up outbox archival cron job (see platform docs)
- [ ] Verify agents respond to messaging channels
