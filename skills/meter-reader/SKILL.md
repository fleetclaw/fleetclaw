---
name: meter-reader
description: Accept hour meter and odometer readings from operators and record them
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Meter Reader

_Accept casual meter readings from operators, validate them, and record them._

## Trigger

- **Message** -- Operator reports an hour meter or odometer reading (e.g., "8542 hours", "meter's at 8542", just "8542" in context)

## Input

- **User messages:** Natural language meter reports, optionally with photos of meter displays
- **Outbox files:** Previous meter entries in outbox/ (type: meter) for delta calculation and trend validation
- **AGENTS.md (State):** `last_meter`, `last_meter_ts` for quick reference
- **MEMORY.md:** Last meter reading in Recent Context, typical usage rate in Learned Patterns

## Behavior

When an operator reports a meter reading:

1. Parse the reading from their message. Operators report these casually:
   - "8542 hours"
   - "meter's at 8542"
   - "8542"
   - "just ticked over 8500"
   - "showing 23,400 km"
   - [Photo of meter display showing 8542]

   If the operator sends a photo of the meter display, read the value from the image. This eliminates transcription errors -- confirm what you see: "I'm reading 8542 hours from the photo, that right?"

2. Determine the meter type. Most heavy equipment uses hour meters. Vehicles and some support equipment use odometers (km or miles). If this asset's previous readings in MEMORY.md are in hours, assume hours. If in km or miles, assume that. If this is the first reading and the type is unclear from context, ask once: "Is that hours or km?"

3. Check MEMORY.md for the last meter reading. If available, calculate:
   - Delta: difference between this reading and the last one
   - Days since last reading
   - Daily average usage (delta divided by days since)

4. Validate the reading against the last known value. If the delta seems unreasonable, ask once for confirmation before logging:
   - **Negative delta** (reading is lower than last recorded): "Last reading I have is 8542 -- you're saying 8440? Just want to make sure that's right."
   - **Large jump** (more than 500 hours or 5,000 km in a single report): "That's a jump of 620 hours since last time -- does that sound right?"
   - If the operator confirms, log it. They know their machine better than the data does. Note the confirmation in the entry.
   - If the operator corrects themselves, use the corrected value.
   - Only ask once. Don't interrogate.

5. Write the reading to outbox/ and update `## State`.

6. Update MEMORY.md Recent Context with the new reading. Include date, value, type, and delta. Keep only the last 3 meter readings in MEMORY.md -- remove the oldest if needed. If usage rate is shifting (e.g., machine running longer days), note the trend in Learned Patterns.

7. Respond with confirmation and useful context. Include the delta and daily average if this isn't the first reading. Keep it brief.

### Notes on ambiguous numbers

A bare number like "8542" could be a meter reading or a fuel amount. Consider the conversation context. If the operator just started the shift and you asked about the machine, it's probably a meter reading. If they just mentioned fueling, it's probably liters. If you genuinely can't tell, ask: "Is that a meter reading or a fuel log?" One question.

## Output

- **Outbox writes:** Write a timestamped meter entry to outbox/:
  ```
  ---
  from: {ASSET_ID}
  type: meter
  timestamp: {ISO-8601}
  ---
  value: {READING}
  unit: {hours|km|miles}
  delta: {DELTA}
  days_since: {DAYS}
  ```
- **AGENTS.md (State) updates:** Update `last_meter`, `last_meter_ts` with the new values.
- **MEMORY.md updates:** Add meter reading to Recent Context section (date, value, type, delta). Update Learned Patterns if daily usage rate is shifting. Keep at most 3 readings in Recent Context.
- **Messages to user:** Confirmation with delta and usage context. Example: "Logged 8542 hours. That's 87 hours over the last 6 days -- about 14.5 hrs/day."

## Overdue Condition

No meter reading within 7 days of the last recorded reading.
