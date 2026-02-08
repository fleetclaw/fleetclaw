---
name: anomaly-detector
description: Proactively scan fleet data for anomalies — fuel burn spikes, meter gaps, recurring issues, compliance patterns
metadata: {"openclaw":{"requires":{"bins":["redis-cli"],"env":["REDIS_URL"]}}}
---

# Anomaly Detector

_Proactively scan fleet data for anomalies — fuel burn spikes, meter gaps, recurring issues, compliance patterns._

## Trigger

- **Heartbeat** — Every 2 hours, scan active assets for data anomalies

## Input

- **Redis keys:**
  - `fleet:index:active` — SET of currently active asset IDs
  - `fleet:asset:{ID}:fuel` — STREAM (XREVRANGE for recent entries, last 10 for rolling average)
  - `fleet:asset:{ID}:meter` — STREAM (XREVRANGE for recent entries)
  - `fleet:asset:{ID}:issues` — STREAM (XRANGE over last 30 days for recurrence patterns)
  - `fleet:asset:{ID}:preop` — STREAM (XREVRANGE for recent entries, pattern detection)
  - `fleet:asset:{ID}:state` — HASH (HMGET: last_seen, status, last_fuel_ts, last_preop)
- **MEMORY.md:** Recent Alerts Sent section (to avoid re-alerting for the same issue within 24 hours)

## Behavior

The anomaly detector runs silently on every heartbeat. It does not interact with users — it scans data, identifies problems, writes alerts to Redis, and updates MEMORY.md so the right people see the alert when they next interact with Clawvisor.

### What to scan for

On each heartbeat, iterate over active assets from `SMEMBERS fleet:index:active` and check for these anomaly types:

**Fuel burn rate anomaly.** Read the last 10 fuel entries from the asset's fuel stream using XREVRANGE with COUNT 10. Calculate the rolling average burn rate from the `burn_rate` field. Compare the most recent entry's burn rate against this average. If the latest burn rate is more than 20% above the rolling average, flag it as a warning. If more than 50% above, flag it as critical. A sudden spike in fuel consumption can indicate mechanical problems, operator behavior issues, or a metering error.

**Meter gap.** Read the last 2 meter entries from the asset's meter stream. If the most recent reading jumped more than 500 hours (or equivalent distance units) from the previous reading in a single report, flag it as a data quality concern. This usually means a reading was missed or entered incorrectly.

**Activity gap.** Read the asset's `last_seen` field from the state HASH. If an asset is in the active index but hasn't had any operator interaction in over 48 hours, flag it. The machine might actually be idle and should be reclassified, or the operator is using the machine without interacting with the agent.

**Issue recurrence.** Read the asset's issues stream for the last 30 days using XRANGE with a calculated start timestamp. Group entries by the `category` field. If the same category appears 3 or more times in 30 days, flag it as a recurring issue. This suggests the root cause hasn't been addressed — patching symptoms instead of fixing the problem.

**Pre-op pattern.** Read the last 10 pre-op entries from the asset's preop stream. If the asset consistently gets "partial" or "fail" results — say, 3 or more out of the last 10 — flag it as a pattern. Either the machine has a persistent issue that isn't being addressed, or the operator is half-doing their pre-ops every time.

### Avoiding duplicate alerts

Before writing any alert, check MEMORY.md Recent Alerts Sent for an existing alert of the same type for the same asset within the last 24 hours. If one exists, skip it. This prevents the same alert from being generated every 2 hours.

The 24-hour window means an alert will fire again if the condition persists past a full day — which is appropriate. If fuel burn is still anomalous after 24 hours, it's worth flagging again.

### Alert routing

Different anomaly types matter to different people. Route by type:

- **Data quality issues** (meter gaps, suspicious readings) — route to foreman. They manage operators and can verify readings.
- **Performance anomalies** (fuel burn rate spikes) — route to foreman and mechanic. Could be operator behavior or mechanical issue.
- **Compliance gaps** (activity gaps on active assets) — route to supervisor. They own compliance.
- **Safety concerns** (pre-op patterns showing persistent failures, recurring safety-category issues) — route to supervisor and safety rep.

"Route to" means writing the `notified` field in the alert entry and, for critical or safety alerts, noting them prominently in the Fleet Health section of MEMORY.md. The actual notification happens when that person next interacts with Clawvisor — they'll see the alert in the conversation context.

### Severity levels

- **Info:** Single occurrence, minor deviation, or an observation that doesn't require action yet.
- **Warning:** Repeated occurrence, significant deviation (20-50% above normal), or a pattern forming.
- **Critical:** Safety-related, extreme deviation (>50% above normal), or a persistent unaddressed issue.

## Output

- **Redis writes:**
  ```
  XADD fleet:asset:{ID}:alerts MAXLEN ~ 200 * \
    type        "{fuel_anomaly|meter_gap|activity_gap|issue_recurrence|preop_pattern}" \
    severity    "{info|warning|critical}" \
    description "{human-readable description of the anomaly}" \
    notified    "{role or roles: foreman, mechanic, supervisor, safety_rep}" \
    value       "{the anomalous value}" \
    baseline    "{the expected/normal value}"
  ```
- **MEMORY.md updates:** Add new alerts to Recent Alerts Sent section (keep last 10). If a new anomaly is critical or safety-related, add the asset to Needs Attention. Update Fleet Health summary if a fleet-wide pattern emerges.
- **No messages to user.** The anomaly detector is a silent background scan. Users see alerts when they interact with Clawvisor through other skills.
