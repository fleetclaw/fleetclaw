# Report Templates

Standard templates for Fleet Coordinator reports and summaries.

---

## Hourly Summary (Compact)

For posting to #fleet-coordination channel:

```
📊 Fleet Status - {TIME}

{OPERATIONAL_EMOJI} {OPERATIONAL_COUNT} operational | {IDLE_EMOJI} {IDLE_COUNT} idle | {MAINT_EMOJI} {MAINT_COUNT} maint | {DOWN_EMOJI} {DOWN_COUNT} down

{ASSET_TYPE_SUMMARIES}

{CONCERNS_SECTION}
```

### Asset Type Summary Block

```
{ASSET_TYPE}:
  {ASSET_ID}: {STATUS_EMOJI} {HOURS}h, {FUEL_PCT}% fuel{FLAGS}
```

Status emoji mapping:
- ✓ = OPERATIONAL
- ⏸ = IDLE
- 🔧 = MAINTENANCE
- ❌ = DOWN
- ❓ = UNKNOWN/STALE

Flags (append if applicable):
- ` (LOW)` = fuel < 20%
- ` (STALE)` = no update in >2 hours
- ` ⚠` = has active concern

### Concerns Section

Only include if there are concerns:

```
⚠ Concerns:
  - {ASSET_ID}: {CONCERN_DESCRIPTION}
  - {ASSET_ID}: {CONCERN_DESCRIPTION}
```

---

## Hourly Summary (Detailed)

For shift supervisor request or when concerns exist:

```
📊 Fleet Status Report - {DATE} {TIME}

═══════════════════════════════════════

SUMMARY
  Total Assets: {TOTAL}
  Operational:  {OPERATIONAL} ({OPERATIONAL_PCT}%)
  Idle:         {IDLE}
  Maintenance:  {MAINTENANCE}
  Down:         {DOWN}
  Unknown:      {UNKNOWN}

═══════════════════════════════════════

EXCAVATORS ({COUNT})
┌─────────┬──────────────┬────────┬──────┬───────────┐
│ Asset   │ Status       │ Hours  │ Fuel │ Last Seen │
├─────────┼──────────────┼────────┼──────┼───────────┤
│ {ID}    │ {STATUS}     │ {HRS}  │ {F}% │ {TIME}    │
└─────────┴──────────────┴────────┴──────┴───────────┘

HAUL TRUCKS ({COUNT})
┌─────────┬──────────────┬────────┬──────┬───────────┐
│ Asset   │ Status       │ Hours  │ Fuel │ Last Seen │
├─────────┼──────────────┼────────┼──────┼───────────┤
│ {ID}    │ {STATUS}     │ {HRS}  │ {F}% │ {TIME}    │
└─────────┴──────────────┴────────┴──────┴───────────┘

{ADDITIONAL_ASSET_TYPES}

═══════════════════════════════════════

CONCERNS
{CONCERNS_LIST_OR_NONE}

═══════════════════════════════════════

ALERTS (Last Hour)
{ALERTS_LIST_OR_NONE}
```

---

## Daily Report

Full end-of-day report:

```markdown
# Fleet Daily Report
**Date:** {DATE}
**Shift:** {SHIFT_START} - {SHIFT_END}
**Report Generated:** {TIMESTAMP}

---

## Executive Summary

| Metric | Today | 7-Day Avg | Variance |
|--------|-------|-----------|----------|
| Operational Hours | {HRS} | {AVG} | {VAR}% |
| Fuel Consumed (L) | {FUEL} | {AVG} | {VAR}% |
| Loads Completed | {LOADS} | {AVG} | {VAR}% |
| Downtime Hours | {DOWN} | {AVG} | {VAR}% |
| Alerts Generated | {ALERTS} | {AVG} | - |

---

## Fleet Status at Close

| Status | Count | Assets |
|--------|-------|--------|
| Operational | {N} | {ASSET_LIST} |
| Idle | {N} | {ASSET_LIST} |
| Maintenance | {N} | {ASSET_LIST} |
| Down | {N} | {ASSET_LIST} |

---

## Production by Asset

### Excavators

| Asset | Hours | Loads | Material | Fuel (L) | L/hr | Efficiency |
|-------|-------|-------|----------|----------|------|------------|
| {ID} | {H} | {L} | {MAT} | {F} | {RATE} | {EFF}% |
| **Total** | **{H}** | **{L}** | - | **{F}** | **{RATE}** | - |

### Haul Trucks

| Asset | Hours | Cycles | Distance (km) | Fuel (L) | L/hr |
|-------|-------|--------|---------------|----------|------|
| {ID} | {H} | {C} | {D} | {F} | {RATE} |
| **Total** | **{H}** | **{C}** | **{D}** | **{F}** | **{RATE}** |

{ADDITIONAL_ASSET_TYPE_TABLES}

---

## Fuel Analysis

### Consumption Summary

| Asset | Consumed (L) | Rate (L/hr) | vs. Baseline | Status |
|-------|--------------|-------------|--------------|--------|
| {ID} | {L} | {RATE} | {VAR}% | {STATUS} |

### Anomalies

{FUEL_ANOMALIES_OR_NONE}

---

## Maintenance

### Completed Today

| Asset | Type | Duration | Notes |
|-------|------|----------|-------|
| {ID} | {TYPE} | {HRS}h | {NOTES} |

### Scheduled (Next 7 Days)

| Asset | Type | Due At | Hours Remaining |
|-------|------|--------|-----------------|
| {ID} | {TYPE} | {HRS}h | {REMAINING}h |

### Overdue

{OVERDUE_LIST_OR_NONE}

---

## Issues & Escalations

### Alerts Generated

| Time | Asset | Type | Severity | Status |
|------|-------|------|----------|--------|
| {T} | {ID} | {TYPE} | {SEV} | {STATUS} |

### Escalations

{ESCALATION_SUMMARY_OR_NONE}

---

## Data Quality

### Assets with Data Gaps

| Asset | Gap Type | Duration | Impact |
|-------|----------|----------|--------|
| {ID} | {TYPE} | {DUR} | {IMPACT} |

### Missing Submissions

{MISSING_SUBMISSIONS_OR_ALL_COMPLETE}

---

## Notes

{SHIFT_NOTES_IF_ANY}

---

*Report generated by Fleet Coordinator*
*Next report: {NEXT_REPORT_TIME}*
```

---

## Alert Summary

For posting to channel when alert occurs:

```
🚨 Alert - {SEVERITY}

Asset: {ASSET_ID}
Type: {ALERT_TYPE}
Time: {TIMESTAMP}

{ALERT_MESSAGE}

{ACTION_ITEMS_IF_ANY}
```

Severity headers:
- 🔔 Alert - Info
- ⚠️ Alert - Low
- ⚠️ Alert - Medium
- 🚨 Alert - High
- 🆘 Alert - CRITICAL

---

## Stale Asset Warning

When asset hasn't reported in threshold time:

```
⚠️ Communication Gap

Asset {ASSET_ID} has not reported in {DURATION}.
Last known status: {LAST_STATUS}
Last update: {LAST_UPDATE_TIME}

{POSSIBLE_REASONS}

Attempting to re-establish contact...
```

---

## Roll Call Response Summary

After issuing roll call command:

```
📋 Roll Call Complete - {TIME}

Responded: {RESPONDED_COUNT}/{TOTAL_COUNT}

✓ Responding:
  {RESPONDING_ASSET_LIST}

✗ Not Responding:
  {NON_RESPONDING_ASSET_LIST}

{ACTIONS_FOR_NON_RESPONDERS}
```
