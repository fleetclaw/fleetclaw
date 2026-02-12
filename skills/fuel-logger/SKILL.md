---
name: fuel-logger
description: Accept fuel log entries from operators and record them
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Fuel Logger

_Accept casual fuel input from operators and record it._

## Trigger

- **Message** -- Operator mentions fuel, refueling, or sends a number that looks like a fuel amount (e.g., "400l", "filled up", "put 400 in")

## Input

- **User messages:** Natural language fuel reports
- **Outbox files:** Previous fuel entries in outbox/ (type: fuel) for burn rate calculation
- **AGENTS.md (State):** `last_fuel_l`, `last_fuel_ts`, `last_meter` for context
- **MEMORY.md:** Last fuel log details in Recent Context, operator fueling patterns in Operator Patterns, normal burn rate in Learned Patterns

## Behavior

When an operator reports fuel:

1. Parse the amount from their message. Accept messy input. Operators are busy and typing on a phone in a dusty cab. All of these mean 400 liters:
   - "400l"
   - "filled up 400"
   - "put 400 in at smoko"
   - "400 litres before I started"
   - Just "400" if the conversation is already about fuel

2. If the amount is ambiguous after one follow-up, log what you can with a note that the amount is estimated or unknown. Don't ask twice. "Filled up" with no amount is fine to log as a fill event without a liter figure -- just note it.

3. Check MEMORY.md for the previous fuel log. If available, calculate:
   - Liters consumed since last fill
   - Hours operated since last fill (from meter readings in MEMORY.md if available)
   - Burn rate in liters per hour

4. Compare burn rate to this asset's recent average from Learned Patterns in MEMORY.md. If more than 20% above average, mention it casually -- don't alarm, just inform. Something like: "That's a bit higher than usual -- 15.1 L/hr vs your typical 12.8. Might be worth keeping an eye on if it stays up." If this is the first or second fuel log and there's no baseline yet, skip the comparison. Don't invent averages.

5. If the burn rate is reasonable or this is early data, just confirm. Keep it short and conversational. Operators don't want a report -- they want to know the number landed.

6. Write a timestamped fuel entry to outbox/ and update `## State`.

7. Update MEMORY.md Recent Context with the new fuel log. Include date, liters, and burn rate if calculated. If there are more than 5 recent fuel entries in MEMORY.md, remove the oldest. If the burn rate is establishing a trend (consistently higher or lower than recorded normal), update Learned Patterns.

### Notes on operator input

Some operators will report fuel every fill. Some will go days without reporting and then catch up with "put 400 in yesterday and 380 this morning." Accept both entries. Parse what you can. If timestamps are ambiguous, use "today" and "yesterday" relative to the message time.

If an operator sends a number with no context and you're not sure if it's fuel, hours, or something else, ask: "Is that a fuel log or a meter reading?" One question, not a quiz.

## Output

- **Outbox writes:** Write a timestamped fuel entry to outbox/:
  ```
  ---
  from: {ASSET_ID}
  type: fuel
  timestamp: {ISO-8601}
  ---
  liters: {AMOUNT}
  burn_rate: {RATE}
  source: operator
  note: {ANY_NOTES}
  ```
- **AGENTS.md (State) updates:** Update `last_fuel_l`, `last_fuel_ts` with the new values.
- **MEMORY.md updates:** Add fuel log to Recent Context section (date, liters, burn rate). Note burn rate trend in Learned Patterns if it's changing. Update Operator Patterns if this operator has a consistent fueling habit (e.g., always fuels at shift start).
- **Messages to user:** Confirmation with burn rate context when available. Example: "Logged 400L. 620L burned over 47h since last fill -- 13.2 L/hr, right in your normal range."

## Overdue Condition

No fuel log within 8 hours of the operator's first message this shift.
