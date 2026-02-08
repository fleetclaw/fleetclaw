# Platform Prompt

Build the FleetClaw config generation system and deployment infrastructure.

## Reference documents

1. `docs/architecture.md` — System design and agent roles
2. `docs/redis-schema.md` — All Redis key patterns and consumer groups
3. `docs/implementation.md` — How design maps to OpenClaw/Docker/Redis patterns

## Files to create

### Config generation

- `generate-configs.py` (~200 lines) — Reads fleet.yaml, produces all output
- `fleet.yaml.example` — Example fleet config with inline documentation

### Templates

- `templates/soul-asset.md` — Vanilla OpenClaw SOUL.md + `**You are {ASSET_ID}.** Serial: {SERIAL}.`
- `templates/soul-clawvisor.md` — Vanilla OpenClaw SOUL.md + `**You are Clawvisor.**`
- `templates/soul-clawordinator.md` — Vanilla OpenClaw SOUL.md + `**You are Clawordinator.**`
- `templates/openclaw-asset.json` — OpenClaw config: heartbeat 30m, per-asset bot token
- `templates/openclaw-clawvisor.json` — OpenClaw config: heartbeat 2h, Clawvisor bot token
- `templates/openclaw-clawordinator.json` — OpenClaw config: heartbeat 4h, Clawordinator bot token

### Docker

- `docker/Dockerfile` — OpenClaw base + redis-tools + jq (asset agents + Clawvisor)
- `docker/Dockerfile.clawordinator` — OpenClaw base + redis-tools + jq + docker.io + docker group

## generate-configs.py specification

### Input: fleet.yaml

```yaml
fleet:
  name: "Site Name"
  timezone: "Australia/Perth"
  shift_start: "06:00"
  shift_end: "18:00"
  model: "fireworks/accounts/fireworks/models/kimi-k2p5"
  redis_url: "redis://redis:6379"
  contacts:
    manager: {name: "...", telegram: "..."}
    safety: {name: "...", telegram: "..."}
    owner: {name: "...", telegram: "..."}

assets:
  - id: EX-001
    type: excavator
    serial: CAT0390F2ABC12345

heartbeats:
  asset: "30m"
  clawvisor: "2h"
  clawordinator: "4h"
```

### Output: output/ directory

```
output/
  workspaces/{ID}/SOUL.md        — per-agent identity
  config/openclaw-{ID}.json      — per-agent OpenClaw config
  docker-compose.yml             — full compose file
  .env.template                  — all required env vars
  setup-redis.sh                 — consumer group creation
```

### Skill mounting map

```python
SKILL_MOUNTS = {
    "asset": ["fuel-logger", "meter-reader", "pre-op", "issue-reporter", "nudger", "memory-curator-asset"],
    "clawvisor": ["fleet-status", "compliance-tracker", "maintenance-logger", "anomaly-detector", "shift-summary", "escalation-handler", "asset-query", "memory-curator-clawvisor"],
    "clawordinator": ["asset-onboarder", "asset-lifecycle", "fleet-director", "escalation-resolver", "fleet-analytics", "fleet-config", "memory-curator-clawordinator"],
}
```

### Docker-compose rules

- Redis: `redis:7-alpine`, appendonly, maxmemory 512mb, noeviction, maxclients 256, healthcheck
- Per asset: build from `docker/Dockerfile`, entrypoint `node /app/openclaw.mjs gateway run`, env vars, skill volumes, depends_on redis
- Clawvisor: same as asset with different skills/heartbeat/identity
- Clawordinator: `docker/Dockerfile.clawordinator`, + docker.sock mount, + COMPOSE_FILE env var
- Network: single `fleetclaw` bridge

### Consumer groups (setup-redis.sh)

| Stream | Consumer Groups |
|--------|----------------|
| `fleet:asset:{ID}:fuel` | `clawvisor`, `anomaly-detector` |
| `fleet:asset:{ID}:meter` | `clawvisor`, `anomaly-detector` |
| `fleet:asset:{ID}:preop` | `clawvisor` |
| `fleet:asset:{ID}:issues` | `clawvisor` |
| `fleet:asset:{ID}:alerts` | `clawordinator` |
| `fleet:directives` | `clawvisor` |
| `fleet:escalations` | `clawordinator` |

### OpenClaw config options

| Option | Value | Why |
|--------|-------|-----|
| `skipBootstrap` | `true` | Don't overwrite generated SOUL.md |
| `bootstrapMaxChars` | `15000` | Leave headroom for skills |
| `tools.deny` | `["browser","canvas","nodes","cron"]` | Not needed |
| `sandbox.mode` | `"off"` | No sandboxing needed |
| `compaction.memoryFlush.softThresholdTokens` | `4000` | Early memory flush |
| `skills.load.extraDirs` | `["/app/skills"]` | Skill discovery |
| `session-memory` hook | enabled | Session transcript saves |

## Verification

After implementation:
1. `python generate-configs.py` runs against `fleet.yaml.example` without errors
2. Generated `docker-compose.yml` is valid YAML with correct service structure
3. Generated `openclaw-*.json` files are valid JSON with correct substitutions
4. Generated `SOUL.md` files contain the identity line
5. `.env.template` lists every required token
6. `setup-redis.sh` creates consumer groups for all assets
