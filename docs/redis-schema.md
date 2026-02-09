# FleetClaw Redis Schema

This is the authoritative reference for all Redis key patterns used by FleetClaw agents. Every skill that reads or writes Redis must conform to this schema.

## Architecture

Redis is the **message bus** between FleetClaw agents. It is not the source of truth — MEMORY.md on each agent is the permanent record. Redis holds recent operational data long enough for all consumers to read it.

**Data flow:**

```
Asset Agent writes event → Redis Stream (short-lived, trimmed)
                         → MEMORY.md (permanent, curated summary)

Clawvisor reads Redis → aggregates, detects anomalies, reports
Clawordinator reads Redis → fleet-level decisions, lifecycle management
```

## Key naming convention

Keys are **hierarchical, entity-first**, following Redis's recommended `object-type:id` pattern.

```
fleet:asset:{ASSET_ID}:{data_type}
```

This enables efficient per-asset prefix scanning:

```bash
# Everything about EX-001
redis-cli --scan --pattern "fleet:asset:EX-001:*"
```

Cross-asset queries (e.g., "all fuel logs") use **index SETs**, not wildcard SCAN:

```bash
# Get all active asset IDs, then read each one's fuel stream
SMEMBERS fleet:index:active
# → ["EX-001", "KOT28", "CAE52", ...]
# Then: XRANGE fleet:asset:EX-001:fuel - + COUNT 10
```

## Key reference

### Per-asset keys

| Key | Type | Written by | Read by | Retention |
|-----|------|-----------|---------|-----------|
| `fleet:asset:{ID}:state` | HASH | Asset agent | Clawvisor, Clawordinator | Persistent (no TTL) |
| `fleet:asset:{ID}:fuel` | STREAM | Asset agent | Clawvisor (compliance, anomalies) | MAXLEN ~ 1000 |
| `fleet:asset:{ID}:meter` | STREAM | Asset agent | Clawvisor (compliance, anomalies) | MAXLEN ~ 1000 |
| `fleet:asset:{ID}:preop` | STREAM | Asset agent | Clawvisor (compliance) | MAXLEN ~ 500 |
| `fleet:asset:{ID}:issues` | STREAM | Asset agent | Clawvisor (tracking, escalation) | MAXLEN ~ 500 |
| `fleet:asset:{ID}:maintenance` | STREAM | Clawvisor | Asset agent (acknowledgments) | MAXLEN ~ 500 |
| `fleet:asset:{ID}:alerts` | STREAM | Clawvisor | Clawvisor, Clawordinator | MAXLEN ~ 200 |
| `fleet:asset:{ID}:inbox` | STREAM | Clawvisor, Clawordinator | Asset agent | MAXLEN ~ 100 |
| `fleet:asset:{ID}:lifecycle` | HASH | Clawordinator | Clawvisor, Asset agent | Persistent (no TTL) |

### Fleet-wide keys

| Key | Type | Written by | Read by | Retention |
|-----|------|-----------|---------|-----------|
| `fleet:directives` | STREAM | Clawordinator | Asset agents, Clawvisor | MAXLEN ~ 200 |
| `fleet:escalations` | STREAM | Clawvisor | Clawordinator | MAXLEN ~ 500 |

### Index keys

| Key | Type | Written by | Read by | Purpose |
|-----|------|-----------|---------|---------|
| `fleet:index:active` | SET | Clawordinator | Clawvisor | O(1) active fleet enumeration |
| `fleet:index:idle` | SET | Clawordinator | Clawvisor | O(1) idle fleet enumeration |

## Data formats

### State HASH: `fleet:asset:{ID}:state`

Discrete key-value fields. No JSON blobs. Each field is independently readable with HGET.

```bash
HSET fleet:asset:EX-001:state \
  status        "active" \
  operator      "Mike" \
  last_fuel_l   "400" \
  last_fuel_ts  "1707350400" \
  last_meter    "8542" \
  last_meter_ts "1707264000" \
  last_preop    "pass" \
  last_preop_ts "1707350400" \
  last_seen     "1707353000"
```

**Reading specific fields (preferred — O(1) per field):**

```bash
HMGET fleet:asset:EX-001:state last_fuel_ts last_preop_ts last_meter_ts
```

**Avoid HGETALL** in hot paths — it's O(N) and tagged `@slow` by Redis. Use HMGET for the specific fields you need.

#### State fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `active`, `idle`, `maintenance`, `down` |
| `operator` | string | Current operator name (from Telegram) |
| `last_fuel_l` | string (numeric) | Last fuel log amount in liters |
| `last_fuel_ts` | string (unix timestamp) | When last fuel was logged |
| `last_meter` | string (numeric) | Last meter reading value |
| `last_meter_ts` | string (unix timestamp) | When last meter was read |
| `last_preop` | string | `pass`, `fail`, `partial` |
| `last_preop_ts` | string (unix timestamp) | When last pre-op was completed |
| `last_seen` | string (unix timestamp) | Last interaction with operator |

All values are stored as strings (Redis HASH convention). Parse to numbers as needed.

### Lifecycle HASH: `fleet:asset:{ID}:lifecycle`

```bash
HSET fleet:asset:EX-001:lifecycle \
  state       "active" \
  since       "2026-01-15" \
  changed_by  "clawordinator"
```

| Field | Type | Description |
|-------|------|-------------|
| `state` | string | `active`, `idle`, `decommissioned` |
| `since` | string (ISO date) | When this state was set |
| `changed_by` | string | Who changed it (`clawordinator`, `manager:{name}`) |

### Fuel STREAM: `fleet:asset:{ID}:fuel`

```bash
XADD fleet:asset:EX-001:fuel MAXLEN ~ 1000 * \
  liters      "400" \
  burn_rate   "13.2" \
  source      "operator" \
  note        "filled at smoko"
```

| Field | Type | Description |
|-------|------|-------------|
| `liters` | string (numeric) | Amount fueled in liters |
| `burn_rate` | string (numeric) | Calculated L/hr since last fill (if available) |
| `source` | string | `operator`, `telematics`, `bowser` (Tier 2 sources) |
| `note` | string | Free-form operator notes |

### Meter STREAM: `fleet:asset:{ID}:meter`

```bash
XADD fleet:asset:EX-001:meter MAXLEN ~ 1000 * \
  value       "8542" \
  type        "hours" \
  delta       "87" \
  days_since  "6"
```

| Field | Type | Description |
|-------|------|-------------|
| `value` | string (numeric) | Current meter reading |
| `type` | string | `hours` (hour meter) or `km`/`miles` (odometer) |
| `delta` | string (numeric) | Change since last reading |
| `days_since` | string (numeric) | Days since last reading |

### Pre-op STREAM: `fleet:asset:{ID}:preop`

```bash
XADD fleet:asset:EX-001:preop MAXLEN ~ 500 * \
  result      "partial" \
  flags       "mirror_cracked" \
  operator    "Mike" \
  severity    "minor"
```

| Field | Type | Description |
|-------|------|-------------|
| `result` | string | `pass`, `fail`, `partial` |
| `flags` | string | Comma-separated flagged items (empty if pass) |
| `operator` | string | Who completed the pre-op |
| `severity` | string | `none`, `minor`, `major`, `safety` |

### Issues STREAM: `fleet:asset:{ID}:issues`

```bash
XADD fleet:asset:EX-001:issues MAXLEN ~ 500 * \
  description "hydraulics sluggish on boom" \
  category    "hydraulic" \
  operational "yes" \
  reporter    "Mike"
```

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Free-form issue description |
| `category` | string | Agent-determined category (hydraulic, engine, electrical, structural, safety, other) |
| `operational` | string | `yes` (can still operate) or `no` (machine down) |
| `reporter` | string | Who reported the issue |

### Maintenance STREAM: `fleet:asset:{ID}:maintenance`

Written by Clawvisor when a mechanic logs completed work.

```bash
XADD fleet:asset:EX-001:maintenance MAXLEN ~ 500 * \
  action      "replaced" \
  component   "hydraulic pump" \
  duration_h  "6" \
  mechanic    "Dave" \
  status      "back_in_service" \
  note        "monitor temps for 24h"
```

| Field | Type | Description |
|-------|------|-------------|
| `action` | string | `replaced`, `repaired`, `inspected`, `serviced`, `adjusted` |
| `component` | string | What was worked on |
| `duration_h` | string (numeric) | Hours spent |
| `mechanic` | string | Who did the work |
| `status` | string | `back_in_service`, `still_down`, `restricted` |
| `note` | string | Follow-up instructions or observations |

### Inbox STREAM: `fleet:asset:{ID}:inbox`

Messages directed to a specific asset agent. Read on session start and heartbeat.

```bash
XADD fleet:asset:EX-001:inbox MAXLEN ~ 100 * \
  type        "maintenance_ack" \
  summary     "Hydraulic pump replaced — monitor temps" \
  from        "clawvisor" \
  ref_stream  "fleet:asset:EX-001:maintenance" \
  ref_id      "1707350400000-0"
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `maintenance_ack`, `directive`, `alert`, `message` |
| `summary` | string | Human-readable summary for the operator |
| `from` | string | `clawvisor`, `clawordinator` |
| `ref_stream` | string | Source stream key (for cross-reference) |
| `ref_id` | string | Source stream entry ID (for cross-reference) |

### Alerts STREAM: `fleet:asset:{ID}:alerts`

Anomaly alerts generated by Clawvisor.

```bash
XADD fleet:asset:EX-001:alerts MAXLEN ~ 200 * \
  type        "fuel_anomaly" \
  severity    "warning" \
  description "Burn rate 40% above 7-day average" \
  notified    "foreman" \
  value       "18.5" \
  baseline    "13.2"
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `fuel_anomaly`, `meter_gap`, `preop_pattern`, `issue_recurrence`, `activity_gap` |
| `severity` | string | `info`, `warning`, `critical` |
| `description` | string | Human-readable description |
| `notified` | string | Who was alerted (role or name) |
| `value` | string | The anomalous value |
| `baseline` | string | The expected/normal value |

### Directives STREAM: `fleet:directives`

Fleet-wide instructions from Clawordinator.

```bash
XADD fleet:directives MAXLEN ~ 200 * \
  scope       "all" \
  instruction "Fire extinguisher check before next shift" \
  issued_by   "safety_rep" \
  expires     "2026-02-09T18:00:00Z"
```

| Field | Type | Description |
|-------|------|-------------|
| `scope` | string | `all`, or specific ID (`EX-001`) |
| `instruction` | string | The directive text |
| `issued_by` | string | Role or name of the person who issued it |
| `expires` | string (ISO datetime) | When this directive is no longer relevant (optional) |

### Escalations STREAM: `fleet:escalations`

```bash
XADD fleet:escalations MAXLEN ~ 500 * \
  asset_id    "EX-001" \
  type        "unresolved_issue" \
  description "Hydraulic issue reported 72h ago, no maintenance logged" \
  severity    "warning" \
  from        "clawvisor"
```

| Field | Type | Description |
|-------|------|-------------|
| `asset_id` | string | Which asset this escalation concerns |
| `type` | string | `unresolved_issue`, `repeated_failure`, `compliance_gap`, `safety_concern` |
| `description` | string | Context for the person receiving the escalation |
| `severity` | string | `warning`, `critical` |
| `from` | string | `clawvisor` |

## Consumer groups

Streams that need fan-out to multiple independent readers use consumer groups:

```bash
# Create consumer groups (done once at setup)
XGROUP CREATE fleet:asset:EX-001:fuel clawvisor $ MKSTREAM
XGROUP CREATE fleet:asset:EX-001:fuel anomaly-detector $ MKSTREAM

# Clawvisor reads fuel events for compliance
XREADGROUP GROUP clawvisor clawvisor-1 COUNT 10 STREAMS fleet:asset:EX-001:fuel >

# Anomaly detector reads same events independently
XREADGROUP GROUP anomaly-detector detector-1 COUNT 10 STREAMS fleet:asset:EX-001:fuel >
```

Each consumer group tracks its own read position. Multiple readers process the same data without interference.

## Retention strategy

**No key-level TTL.** Streams use MAXLEN trimming (entries are removed by XADD itself). HASHes are persistent.

| Key type | Retention method | Rationale |
|----------|-----------------|-----------|
| State HASH | Persistent | Current state, always needed |
| Lifecycle HASH | Persistent | Fleet composition, always needed |
| Fuel STREAM | MAXLEN ~ 1000 | ~6 months of daily fueling |
| Meter STREAM | MAXLEN ~ 1000 | ~3 years of weekly readings |
| Pre-op STREAM | MAXLEN ~ 500 | ~1 year of daily pre-ops |
| Issues STREAM | MAXLEN ~ 500 | Long enough for pattern detection |
| Maintenance STREAM | MAXLEN ~ 500 | Long enough for history queries |
| Alerts STREAM | MAXLEN ~ 200 | Recent alert history |
| Inbox STREAM | MAXLEN ~ 100 | Small — read and processed quickly |
| Directives STREAM | MAXLEN ~ 200 | Recent directives |
| Escalations STREAM | MAXLEN ~ 500 | Active and recent escalations |
| Index SETs | Persistent | Fleet composition indexes |

The permanent record for all data lives in each agent's MEMORY.md (curated summaries) and can optionally be backed up from Redis Streams before trimming.

## Infrastructure notes

**Single Redis instance** for Tier 1 deployments. Set `maxmemory-policy noeviction` to reject writes when full rather than silently evicting data.

**Separate instances** recommended for Tier 2 deployments with heavy caching workloads (derived aggregations, external system caches).

**Persistence:** Enable RDB snapshots for crash recovery. AOF optional for deployments that need point-in-time recovery.

## Extending the schema

Tier 2 and Tier 3 skills may introduce new key patterns. Follow these rules:

1. **Use the `fleet:asset:{ID}:` prefix** for per-asset data.
2. **Use `fleet:` prefix** for fleet-wide data.
3. **Register new keys** by documenting them in this file via PR.
4. **Use STREAM for events, HASH for state.** Don't introduce new data types without good reason.
5. **Keep entries flat.** No nested JSON in Stream entries or HASH fields.
6. **Set MAXLEN on new Streams.** Don't create unbounded Streams.
7. **Create index SETs** if Clawvisor needs to enumerate keys of your new type.
