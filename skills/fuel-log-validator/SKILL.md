---
name: fuel-log-validator
description: Validates fuel logs against asset self-knowledge in SOUL.md
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Fuel Log Validator

Validates fuel submissions against the asset's learned models stored in SOUL.md. This skill ensures data integrity by checking hour meter progression, fuel quantity constraints, and consumption rate anomalies.

## When to Use

When an operator submits a fuel log. Recognize these input patterns:

- Direct format: `@ASSET fuel 180 12849.5`
- Labeled format: `fuel log: 180L, hours 12849.5`
- Natural language: "Put 180 liters in, hour meter shows 12849.5"
- Variations: "refueled", "filled up", "added fuel", "topped off"

Extract two values from any submission:
1. **Fuel quantity** (liters) - the amount added
2. **Hour meter reading** - current equipment hours

## Validation Steps

### Step 1: Read Current State from SOUL.md

Open `SOUL.md` in the workspace and extract these values:

```yaml
# From SOUL.md learned_models section:
hour_meter:
  current: <last_known_hours>

fuel:
  tank_capacity: <capacity_liters>
  last_fill: <liters_at_last_fill>
  last_hours: <hours_at_last_fill>

consumption_rates:
  average: <liters_per_hour>
  operator_norms:
    <operator_id>: <their_average_rate>
```

### Step 2: Validate Hour Meter

| Check | Condition | Action |
|-------|-----------|--------|
| Hours decreased | `submitted_hours < current_hours` | **REJECT** - Hours cannot decrease |
| Stuck meter | Same reading 3+ consecutive submissions | **FLAG** - Meter may be stuck |
| Large gap | `delta_hours > 24` | **FLAG** - Large gap since last reading |
| Future hours | `submitted_hours > current_hours + 48` | **FLAG** - Unusually large jump |

### Step 3: Validate Fuel Quantity

1. **Calculate estimated current fuel level:**
   ```
   hours_since_fill = submitted_hours - last_hours
   fuel_consumed = hours_since_fill × average_consumption_rate
   estimated_current = last_fill - fuel_consumed
   ```

2. **Check tank capacity:**
   ```
   new_total = estimated_current + submitted_fuel
   max_allowed = tank_capacity × 1.05  # 5% tolerance for gauge variance
   ```

| Check | Condition | Action |
|-------|-----------|--------|
| Overfill | `new_total > max_allowed` | **REJECT** - Exceeds tank capacity |
| Tiny fill | `submitted_fuel < 20` | **FLAG** - Unusually small fill |
| Massive fill | `submitted_fuel > tank_capacity × 0.9` | **FLAG** - Verify tank was near empty |

### Step 4: Validate Consumption Rate

1. **Calculate implied consumption:**
   ```
   implied_rate = fuel_consumed / hours_since_fill
   ```

2. **Compare to operator's historical average:**
   ```
   deviation = |implied_rate - operator_average| / operator_average × 100
   ```

| Check | Condition | Action |
|-------|-----------|--------|
| High deviation | `deviation > 30%` | **FLAG** - Consumption anomaly |
| Very high | `deviation > 50%` | **FLAG** - Possible data entry error |

### Step 5: Update SOUL.md (On Accept)

When validation passes (ACCEPT or ACCEPT_WITH_FLAGS), update SOUL.md:

```yaml
hour_meter:
  current: <submitted_hours>
  last_updated: <ISO_timestamp>

fuel:
  last_fill: <submitted_fuel>
  last_hours: <submitted_hours>
  last_updated: <ISO_timestamp>

consumption_samples:
  - date: <today>
    hours: <delta_hours>
    liters: <fuel_consumed>
    rate: <implied_rate>
    operator: <operator_id>
```

Keep the last 20 consumption samples. Remove oldest when adding new.

### Step 6: Log to Memory

Append to `memory/YYYY-MM-DD.md`:

```markdown
## Fuel Log - HH:MM

- **Operator:** @operator_name
- **Fuel added:** XXX liters
- **Hour meter:** XXXXX.X hours
- **Validation:** ACCEPTED / ACCEPTED_WITH_FLAGS / REJECTED
- **Notes:** [any flags or rejection reasons]
```

## Response Templates

### ACCEPT

```
✓ Fuel log recorded

  Fuel: {fuel}L
  Hours: {hours}
  Consumption: {rate} L/hr ({status} vs normal)

Tank estimate: ~{estimated_level}L ({percentage}% full)
```

### ACCEPT_WITH_FLAGS

```
✓ Fuel log recorded with notes

  Fuel: {fuel}L
  Hours: {hours}

⚠ Flags:
  {flag_list}

Please verify if anything looks wrong.
```

### REJECT

```
✗ Fuel log rejected

  Submitted: {fuel}L at {hours} hours

Reason: {rejection_reason}

{guidance_for_correction}
```

## Examples

### Valid Submission
```
Input: "@EX-001 fuel 180 12849.5"
Current state: hours=12840, tank=680L, last_fill=400L at 12800 hours

Calculation:
- Hours delta: 12849.5 - 12840 = 9.5 hours ✓ (increased)
- Consumed: (12849.5 - 12800) × 28 L/hr = 1386L estimated consumed
- But last_fill was 400L, so current estimate = 400 - (49.5 × 28) = -986L
- This means tank was refilled before; accept the 180L as new baseline

Response: ACCEPT
```

### Invalid - Hours Decreased
```
Input: "@EX-001 fuel 180 8000"
Current state: hours=12849.5

Calculation:
- Hours delta: 8000 - 12849.5 = -4849.5 ✗ (decreased)

Response: REJECT
Reason: Hour meter cannot decrease. Last reading was 12849.5 hours.
```

### Invalid - Exceeds Capacity
```
Input: "@EX-001 fuel 800 12850"
Current state: tank_capacity=680L

Calculation:
- 800L > 680L × 1.05 = 714L ✗

Response: REJECT
Reason: 800L exceeds tank capacity of 680L.
```

## Edge Cases

1. **First fuel log for new asset**: Accept with FLAG, establish baseline
2. **Hour meter reset**: Requires supervisor approval, manual SOUL.md update
3. **Multiple fills same day**: Accept all, consumption calc uses cumulative
4. **Operator not recognized**: Accept with FLAG, prompt to identify operator
