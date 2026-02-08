# FleetClaw

Fleet management system using OpenClaw AI agents for mining equipment.

## Project Structure

- `skills/` - OpenClaw SKILL.md files (instructional, not code)
- `templates/workspace/` - Workspace templates (*.template) per asset type
- `templates/coordinator/` - FC-specific workspace templates (separate from asset templates)
- `hooks/` - Event-driven HOOK.md files with lifecycle triggers
- `templates/*.j2` - Jinja2 templates for deployment configs
- `scripts/generate-configs.py` - Generates configs from `config/fleet.yaml`
- `config/fleet.yaml` - Fleet asset definitions
- `generated/` - Output directory (workspaces/, config/)
- `tests/` - pytest tests for scripts

## External APIs

- Fireworks AI API (`FIREWORKS_API_KEY`) - LLM for all agents (Kimi K2.5)
- Telegram Bot API (`TELEGRAM_TOKEN_{ASSET_ID}`) - One bot token per asset
- Rooster GPS API (`ROOSTER_ASSET_TRACKING_API_KEY`) - Pending whitelist, using CSV fallback
- OpenClaw Gateway (`OPENCLAW_GATEWAY_TOKEN`) - Mandatory auth for agent containers

## Commands

- `python scripts/generate-configs.py` - Generate all configs to `generated/`
- `python scripts/generate-configs.py --dry-run` - Preview what would be generated
- `python scripts/generate-configs.py --target-asset EX-001` - Regenerate single asset
- `python scripts/generate-configs.py --target-host host-02` - Regenerate single host
- `./scripts/add-asset.sh` - Interactive script to add new asset to fleet.yaml
- `python scripts/auto_onboard.py --json '{...}'` - Programmatic asset onboarding (used by Fleet Coordinator)
- `python scripts/soul_guard.py update --key "hour_meter.current" --value "12850"` - Update SOUL.md state
- `python scripts/asset_lifecycle.py status [asset_id]` - Check asset idle/active status
- `python scripts/asset_lifecycle.py wake <asset_id>` - Wake an idle asset
- `python scripts/asset_lifecycle.py nightly-check --dry-run` - Preview idle check
- `python scripts/csv_import.py --csv <file> --host <host> --dry-run` - Bulk CSV import validation
- `python scripts/csv_import.py --csv <file> --host <host> --create-host --redis` - Import with new host

## Code Patterns

### Jinja2 Templates
- Always use `SandboxedEnvironment` for templates with user-controlled input
- Pre-compute values in Python, don't call methods like `.split()` in templates
- Template variables must match context keys (e.g., `assets` not `host.assets`)

### Python
- Pre-compile regex patterns as module-level constants
- Avoid variable shadowing in loops: use `type_assets` not `assets` when iterating grouped data
- Extract repeated dicts/mappings as module-level constants
- Extract shared logic into helper functions (e.g., `group_assets_by_type()`) when used in 2+ places
- Use `yaml.safe_load()` for PyYAML; `ruamel.yaml.YAML()` defaults to safe round-trip mode
- Use `Path.read_text()`/`write_text()` over `open()`/`read()`/`write()`
- Use `Path.read_bytes()`/`write_bytes()` for binary backup/restore operations
- Atomic writes: write to `.tmp` file then `Path.replace()` to target
- When serializing ruamel.yaml data to JSON, convert `CommentedMap` to plain dict first
- Avoid naming variables after modules (e.g., use `yaml_parser` not `yaml` when using ruamel.yaml)
- Extract Redis key patterns as module-level constants (e.g., `KEY_LIFECYCLE = "fleet:lifecycle:{}"`)
- Use `str.removeprefix()` over `str.replace()` for stripping Redis key prefixes (semantically precise, avoids mid-string matches)
- `subprocess.run()` with list args (no `shell=True`) is safe from shell injection

### CSV Import (csv_import.py)
- `ASSET_TYPE_METADATA` in `generate-configs.py` is the single source of truth for valid asset types
- CSV categories auto-match via normalization: "Artic. Dump Truck" → `artic_dump_truck`
- Normalization: lowercase, replace `.` `/` `-` with `_`, collapse multiple underscores
- `CATEGORY_ALIASES` dict handles edge cases only (abbreviations like `trk` → `truck`)
- Adding a new asset type to `ASSET_TYPE_METADATA` automatically enables CSV import for it
- `models.py` validates asset types at runtime against `ASSET_TYPE_METADATA` (no static Literal)
- `FleetConfig` allows empty `assets: []` for testing/scaffolding - only FLEET-COORD is required
- To add a new CSV category mapping: first check if normalization matches an existing type key; only add to `CATEGORY_ALIASES` if it doesn't
- All assets get dedicated agents - no `tracked_assets` concept (removed in PR #22)

### Fleet Coordinator (FLEET-COORD)
- FC Soul template dynamically lists all asset types using `FLEET_SECTIONS` loop
- FC workspace templates live in `templates/coordinator/`, not `templates/workspace/`
- `generate_fleet_coordinator_workspace()` handles all FC generation (separate from asset path)
- `build_fc_workspace_context()` uses coordinator.manager/safety/owner (no OPERATOR_* keys)
- FC templates use `{{MANAGER_NAME}}`, `{{SAFETY_NAME}}`, `{{OWNER_NAME}}` placeholders
- Idle management (asset_lifecycle.py) manages container start/stop based on activity - separate from removed tracked_assets
- Assets go idle after 7 days without activity; wake on fuel logs, pre-op checklists, or messages

### Go (gatekeeper/)
- Use `sync.RWMutex` for hot-reloadable config with `RLock()` for reads
- Return copies from lookups, not pointers to slice elements (prevents data races)
- Debounce fsnotify file watchers (100ms) to handle multiple write events
- `exec.Command()` with list args is safe from shell injection (no shell interpretation)

### Telegram Handles in Templates
- Soul templates prepend `@` (e.g., `@{{FC_TELEGRAM}}`), so context builders must `.lstrip('@')` values from fleet.yaml
- Three context builders exist: `build_workspace_context()`, `render_soul_md()`, `render_fleet_coordinator_soul()` — all must strip consistently

### Redis (fleet communication)
- All keys use `fleet:` namespace prefix: `fleet:{entity_type}:{identifier}`
- Status broadcast: `fleet:status:{ID}` (STRING with 8h TTL) - assets write, FC reads
- Lifecycle tracking: `fleet:lifecycle:{ID}` (HASH, persistent) - gatekeeper/lifecycle script manage
- Inbox: `fleet:inbox:{ID}` (PUB/SUB) - per-asset message channel
- Test keys: `fleet:test:{ID}` (STRING, 60s TTL) - connectivity checks in asset-monitor
- Event stream: `fleet:events` (list, capped at 100) - always LPUSH then LTRIM
- `redis-cli LRANGE` returns one JSON per line, not a JSON array - use `while read` loops with jq, not piped `jq 'select(...)'`

### Hooks (HOOK.md)
- YAML frontmatter: `name`, `description`, `trigger`, optional `priority`
- Triggers: `lifecycle:session_start`, `lifecycle:new_session`, `custom:*`
- Fleet Coordinator gets only `boot-md` and `session-memory` (no `fuel-log-received`)

### Workspace Templates (*.template)
- Use `{{KEY}}` placeholder format (no spaces inside braces)
- `render_workspace_templates()` takes `subdir` param: `'workspace'` (default for assets), `'coordinator'` (for FC)
- Include YAML frontmatter with `summary` and `read_when` metadata
- `read_when` format: YAML list of trigger descriptions (e.g., `- Heartbeat poll received`)
- Use `encoding='utf-8'` when rendering (for emoji support)
- All 55 asset soul.md templates share identical structure (intro → philosophy → Identity → rest) — bulk edits via Python script, not individual Edit calls
- `fleet-coordinator-soul.md` has unique structure — always handle separately from asset templates

### OpenClaw 2026.2.1 Deployment
- Skills mount individually to `/app/skills/<skill>/` (not as a single volume)
- Docker Compose requires explicit `entrypoint` and `command` directives
- `copy_to_compose_dir()` copies workspaces/skills for Docker volume mounts
- Skills directory is copied alongside workspaces in generated compose output
- Custom Dockerfile in `docker/openclaw/` extends base image with extra packages (redis-tools, jq)
- `OPENCLAW_DOCKER_APT_PACKAGES` build arg only works when building from source, not with pre-built images
- `image:` tag alongside `build:` in docker-compose enables build caching across `docker compose up` runs

### SOUL.md Templates (templates/workspace/*-soul.md)
- All asset types share a common structure - type-specific tracking sections were removed to reduce template complexity and maintenance burden
- Physical specs standardized to "Operating weight" only - detailed specs (bucket capacity, blade width, etc.) were removed as they added complexity without operational value
- Maintenance status blocks (tire_status, bucket_status) removed - only service intervals are kept
- Type-specific sections (Load Tracking, Cycle Patterns, Material Handling, etc.) were removed - these can be added dynamically via soul-guard if needed operationally
- Template version: 2.0 (simplified common structure)
- Three tracking methods: odometer-based (km + hours, for on-road), months-based (calendar, for pumps), hour meter-based (hours only, for off-road)
- Description line must decode abbreviations: HB=Hydraulic Boom, LB=Lattice Boom, RT=Rough Terrain, CT=Cushion Tire, DTH=Down-The-Hole, Mtd=Mounted, Trk=Track, Whl=Wheel
- Truck-mounted equipment should include "truck mounted" in description (e.g., "truck mounted vacuum excavator")

## Testing

Run pytest: `python -m pytest tests/ -v`

### Test Patterns
- Import hyphenated scripts with `import_module('generate-configs')` from `importlib`
- Mock `models` module when testing to avoid circular imports with `ASSET_TYPE_METADATA`
- Use `tmp_path` fixture for filesystem tests; create full directory structure before assertions

Manual verification:
- Run `generate-configs.py` and check `generated/` output
- Validate generated JSON with `jq . generated/config/*.json`
- Verify Python syntax: `python -m py_compile scripts/*.py`
- Test soul-guard: creates `state.json` sidecar alongside SOUL.md on update/append

## Generated Structure

Each asset gets a workspace directory:
```
generated/workspaces/{ASSET_ID}/
├── SOUL.md, AGENTS.md, USER.md, IDENTITY.md, TOOLS.md
├── BOOT.md, HEARTBEAT.md
├── hooks/boot-md/, hooks/session-memory/, hooks/fuel-log-received/
└── memory/YYYY-MM-DD.md (daily logs)
```

FLEET-COORD workspace has the same file structure but uses FC-specific templates from `templates/coordinator/` (fleet management focus instead of equipment operations).

Docker Compose generates 3 infrastructure containers plus 2 containers per asset (main agent + Prometheus exporter sidecar).

## Gotchas

- **Skills are instructional markdown** - No code to run/test; changes are documentation only
- **Docker Image:** Official image is now `ghcr.io/openclaw/openclaw` (Docker Hub is deprecated)
- **Docker image version bumps touch 4 files:** `docker/openclaw/Dockerfile`, `templates/docker-compose.yml.j2`, `README.md`, `tests/test_generate_configs.py` — CLAUDE.md version refs (line 114 header, line 187 gotcha) are historical markers for when features were introduced, not deployment targets
- **Auth Required:** OpenClaw v2026.1.29+ requires `OPENCLAW_GATEWAY_TOKEN`; containers will exit without it
- **GitHub:** `fleetclaw/fleetclaw` (https://github.com/fleetclaw/fleetclaw) - use `owner: fleetclaw`, `repo: fleetclaw` for GitHub API/MCP calls
- **Git remote:** `origin` → `https://github.com/fleetclaw/fleetclaw.git`, default branch `main`
- `add-asset.sh` inserts before `hosts:` section - verify YAML structure after
- Model versions in `.env.template` and `docker-compose.yml.j2` need periodic updates
- MEMORY.md is created by agents at runtime (no template) - `read_when: main_only`, never shared in group contexts
- Fleet Coordinator doesn't receive `fuel-log-received` hook
- Simple template placeholders: `{{KEY}}` not `{{ KEY }}` (no spaces)
- Agents cannot write directly to SOUL.md - must use `soul-guard` tool
- Go toolchain not always available - gatekeeper changes need separate build verification
- After PR squash-merge, local branch diverges - use `git reset --hard origin/main`
- YAML dates like `2025-06-15` are parsed as `datetime.date` - quote them for Pydantic string fields
- Numeric-looking YAML values (e.g., `model: 7600`) need quoting if target field is string
- `config/fleet.yaml` contains real asset data - use `fleet.yaml.example` as template
- `config/fleet.yaml` must exist before running `csv_import.py` - copy from `fleet.yaml.example`
- `fleet.yaml.example` has empty `assets: []` to avoid test ID collisions - asset structure shown in comments
- Some assets (rigid_haul_truck, semi_truck) may be missing `weight_tons` in specs - defaults to 0
- ruamel.yaml can malform YAML structure when appending to files with inline comments - write fresh files for bulk operations
- Model default is `fireworks/accounts/fireworks/models/kimi-k2p5` - change `DEFAULT_OPENCLAW_MODEL` in generate-configs.py to update fleet-wide
- **Migration from Together:** If upgrading from Together AI, replace `TOGETHER_API_KEY` with `FIREWORKS_API_KEY` in your `.env` file
- **Data Directory:** OpenClaw 2026.2.1+ needs writable `data/<ASSET_ID>/` for runtime state (telegram/, canvas/, cron/)
- **Docker Compose v2:** No `version:` attribute needed in compose files (ignored, triggers warning)
- **Nested Mounts:** Workspace mounts at `/home/node/.openclaw/workspace` overlay the data mount at `/home/node/.openclaw`
- **Two .env.template files:** `config/.env.template` (hand-maintained, full) and `generate_env_template()` in generate-configs.py (generated, subset) — both need updating for env var changes
- **LLM provider changes touch 6 files:** `openclaw.json.j2`, `docker-compose.yml.j2`, `generate-configs.py` (constant + env template function), `config/.env.template`, `CLAUDE.md`, `README.md`
- Removing a template from `WORKSPACE_TEMPLATES` stops future generation but doesn't delete existing files in `generated/workspaces/`
- **Windows Bash:** `cd /d` fails — use `git -C <path>` for git commands or absolute paths without `cd`