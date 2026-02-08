# Skills Prompt

Write all 21 Tier 1 SKILL.md files for FleetClaw.

## Reference documents

Read these before writing any skills:

1. `docs/skill-authoring.md` — Philosophy, template conventions, example fuel-logger skill
2. `docs/redis-schema.md` — All Redis key patterns, field definitions, consumer groups
3. `skills/SKILL-TEMPLATE.md` — Blank scaffolding to copy for each new skill
4. `skills/memory-curator-asset/SKILL.md` — Style reference (existing, complete)
5. `skills/memory-curator-clawvisor/SKILL.md` — Style reference (existing, complete)
6. `skills/memory-curator-clawordinator/SKILL.md` — Style reference (existing, complete)

## What already exists (place, don't rewrite)

These 3 skills are complete. They are already in place at their target paths:

- `skills/memory-curator-asset/SKILL.md`
- `skills/memory-curator-clawvisor/SKILL.md`
- `skills/memory-curator-clawordinator/SKILL.md`

## What to formalize (1 skill)

The fuel-logger skill has a complete example in `docs/skill-authoring.md` (lines 269-346). Extract it into a standalone `skills/fuel-logger/SKILL.md`.

## What to write from scratch (17 skills)

### Asset Agent Skills

| Skill | Trigger | Redis keys (write) | Overdue Condition |
|-------|---------|-------------------|-------------------|
| `meter-reader` | Message | `fleet:asset:{ID}:meter`, state HASH | No reading within 7 days |
| `pre-op` | Session start, Message | `fleet:asset:{ID}:preop`, state HASH | No pre-op within 2h of first message |
| `issue-reporter` | Message | `fleet:asset:{ID}:issues`, state HASH | None (reactive) |
| `nudger` | Heartbeat | None (reads only) | None (IS the nudger) |

### Clawvisor Skills

| Skill | Trigger | Redis keys (write) | Notes |
|-------|---------|-------------------|-------|
| `fleet-status` | Message | None | Read-only, answers fleet questions |
| `compliance-tracker` | Heartbeat, Message | None | Reads state HASHes, updates MEMORY.md |
| `maintenance-logger` | Message | `maintenance`, `inbox`, state HASH | Closes feedback loop to asset agents |
| `anomaly-detector` | Heartbeat | `alerts` | Routes alerts by type |
| `shift-summary` | Message | None | Aggregates from streams |
| `escalation-handler` | Heartbeat, Message | `escalations` | Pattern-based escalation creation |
| `asset-query` | Message | None | Drill-down queries on any asset |

### Clawordinator Skills

| Skill | Trigger | Redis keys (write) | Notes |
|-------|---------|-------------------|-------|
| `asset-onboarder` | Message | indexes, lifecycle, state | Spins up new container |
| `asset-lifecycle` | Message | indexes, lifecycle | Idle/wake/decommission |
| `fleet-director` | Message | `directives`, per-asset `inbox` | Fan-out by scope |
| `escalation-resolver` | Heartbeat, Message | None (MEMORY.md only) | Records leadership decisions |
| `fleet-analytics` | Message | None | Aggregates from streams |
| `fleet-config` | Message | None (MEMORY.md only) | Tracks skill deployment |

## Cross-cutting concerns

### Session start behavior (all asset agent skills)
On session start, check `fleet:asset:{ASSET_ID}:inbox` for pending messages. Deliver maintenance acknowledgments to operator. Note delivery in MEMORY.md.

### Shift detection
Different Telegram user ID after 2+ hour gap = new shift. 14h fallback for double shifts. Resets: nudger tracking, pre-op expectation, fuel log expectation.

### Maintenance acknowledgment loop
1. Operator reports issue → `issue-reporter` → `fleet:asset:{ID}:issues`
2. Mechanic logs repair via Clawvisor → `maintenance-logger` → `fleet:asset:{ID}:maintenance` + `fleet:asset:{ID}:inbox`
3. Asset agent reads inbox on session start → delivers acknowledgment to operator

### MEMORY.md cold-start
If MEMORY.md is empty or missing sections, initialize the standard structure before proceeding.

### Nudger is a meta-skill
The nudger does NOT have its own Overdue Condition. It reads `## Overdue Condition` sections from all other mounted skills and evaluates them against Redis timestamps and MEMORY.md shift data.

## Rules for all skills

1. Valid YAML frontmatter: `name`, `description`, `metadata.openclaw.requires` with `bins: ["redis-cli"]` and `env: ["REDIS_URL"]`
2. Clawordinator skills that use Docker: add `"docker"` to bins
3. Section structure: Trigger, Input, Behavior, Output, Overdue Condition (optional)
4. Plain English in Behavior — no code, no pseudocode, no programming constructs
5. Redis commands in Output are documentation, not executable code
6. Every Redis key referenced must exist in `docs/redis-schema.md`
7. Skills write to existing MEMORY.md sections defined by memory-curator skills — don't create new top-level sections

## Output

Write each skill to `skills/{skill-name}/SKILL.md`.
