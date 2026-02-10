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
3. Inject FleetClaw customizations (SOUL.md, skills, inbox/outbox, configuration)
4. Set filesystem permissions (ACLs)
5. Create and start system services
6. Configure fleet.md
7. Set up messaging channel connections

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

### 3. Create state.md (asset agents only)

Create an initial `~/.openclaw/workspace/state.md`:

```markdown
# State

status: active
```

Skills will populate additional fields during operation.

### 4. Link skills

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

### 5. Tune openclaw.json

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
        "prompt": "Run heartbeat tasks from your mounted skills."
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
            "input": ["text"],
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

The `agents.defaults.models` allowlist is required alongside `model.primary` — without it, the model may resolve on cold start but 404 on subsequent calls. The `models.mode: "merge"` setting is required for custom providers.

**Port configuration:** Set `port` at the root level of openclaw.json (not on the CLI). Each agent needs a unique port. OpenClaw's browser extension relay opens at exactly `gateway_port + 3` (browser control at `+2`, relay at `+3`). With sequential ports, agent N's relay collides with agent N+3's gateway. Space ports with gaps of 4+ or use non-sequential assignments.

Adjust `agents.defaults.heartbeat.every` per agent role:
- Asset agents: `"30m"`
- Clawvisor: `"2h"`
- Clawordinator: `"4h"`

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

## state.md format

Each asset agent maintains its own state.md with flat key-value pairs:

```markdown
# State

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

Skills update specific fields. The agent reads state.md at session start for instant context without parsing outbox history.

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
| `agents.defaults.sandbox.mode` | `"off"` | No code execution sandboxing needed |
| `agents.defaults.compaction.mode` | `"safeguard"` | Default compaction mode |
| `agents.defaults.compaction.memoryFlush.softThresholdTokens` | `4000` | Trigger memory flush early |
| `models.mode` | `"merge"` | Required for custom providers |
| `tools.deny` | `["browser","canvas","nodes","cron"]` | Fleet agents don't need these |
| `skills.load.extraDirs` | `["/opt/fleetclaw/skills"]` | Tell OpenClaw where skills are |
| `port` | unique per agent | Avoid gateway and relay port collisions |

## Cost implications

Each heartbeat is a full agent turn (~5K-15K input tokens). Budget at scale:

| Fleet size | Heartbeats/day | Notes |
|-----------|---------------|-------|
| 10 assets | ~500 | Manageable |
| 50 assets | ~2,500 | Moderate |
| 100 assets | ~4,800 | Consider 1h asset heartbeat |

Heartbeat interval is the primary cost control lever — set longer intervals for agents that don't need frequent checks. Plus Clawvisor and Clawordinator heartbeats, plus operator-initiated conversations.

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
- state.md timestamps: detect stale agents

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
- [ ] Create inbox/outbox directories per agent
- [ ] Create state.md for asset agents
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
- [ ] Verify agents respond to messaging channels
