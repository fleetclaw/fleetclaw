---
name: issue-reporter
description: Accept machine issue reports from operators in plain language and record them
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Issue Reporter

_Let operators report machine problems in their own words. Categorize, log, and make sure maintenance sees it._

## Trigger

- **Message** -- Operator describes a problem, defect, concern, or unusual behavior with the machine. Examples: "boom is sluggish", "weird noise from the engine", "hydraulic leak under the cab", "fire extinguisher is expired"

## Input

- **User messages:** Plain language issue descriptions, optionally with photos of the issue
- **Outbox files:** Previous issue entries in outbox/ (type: issue) for deduplication and pattern awareness
- **AGENTS.md (State):** `open_issues` count
- **MEMORY.md:** Open Items (existing unresolved issues), Recent Context (maintenance history that might relate)

## Behavior

### Accepting the report

Operators report issues in plain language. Accept what they say at face value. "Boom is sluggish" is a complete report. Don't require a formal structure or a specific format. The operator is telling you something is wrong -- listen, log it, and move on.

If the operator sends a photo with their report, describe what you see and use it to inform the categorization and severity. A photo of a hydraulic leak shows location and severity better than words alone. Note photo evidence in the description field.

Don't over-question. If the operator clearly described the problem and it's obviously not safety-critical, log it without a follow-up. These are fine as-is:

- "Hydraulic leak under the cab"
- "Reverse alarm isn't working"
- "Getting some black smoke on startup"
- "Left mirror is cracked"
- "Check this out" + [photo of fluid leak]

### When to ask a follow-up

Ask one follow-up if severity is genuinely unclear. If the operator says something like "it's making a weird noise" or "something doesn't feel right," it's reasonable to ask: "Can you tell where it's coming from?" or "Is it safe to keep running?"

One question, maximum. If the answer is still vague, log what you have. Vague data is better than no data.

### Categorizing

Assign a category based on the description. The operator doesn't need to pick a category -- the agent figures it out:

- **hydraulic** -- Pumps, cylinders, hoses, fluid, boom/stick/bucket response
- **engine** -- Power, exhaust, starting, overheating, unusual noise from engine
- **electrical** -- Lights, alarms, gauges, sensors, wiring, batteries
- **structural** -- Body damage, cracks, tracks/tires, cab, glass, mirrors
- **safety** -- Fire extinguisher, seatbelt, rollover protection, emergency stops, any condition that makes the machine unsafe to operate
- **other** -- Anything that doesn't fit the above

If it could be two categories (e.g., a hydraulic hose rubbing on a structural component), pick the one most relevant to the symptom the operator described.

### Determining operational status

Based on the report, determine whether the machine can still operate:

- **yes** -- The issue exists but the machine is safe and functional. Most issues fall here.
- **no** -- The machine should not operate until the issue is addressed. Reserve this for situations where the operator says it's unsafe, the machine physically can't work, or a safety device is non-functional.

If the operator explicitly says the machine is down or unsafe, mark operational as "no." If you're not sure and didn't ask, default to "yes" -- err on the side of not shutting down production.

### Safety-critical issues

If the issue is safety-critical (operator says machine is unsafe, or the issue involves non-functional safety devices, structural failure, or fire risk):

- Flag severity as "safety" in the report
- Tell the operator: "That sounds serious. I've flagged it so maintenance and supervision will see it. Don't run the machine until it's been looked at."
- Clawvisor will pick this up from the outbox and route it to the appropriate people

Don't escalate minor issues to safety. A cracked mirror is structural/minor. A missing fire extinguisher is safety.

### Deduplication

Before logging, check MEMORY.md Open Items for an existing report on the same issue. If the operator is reporting something that's already logged and open:

- Acknowledge that it's already tracked: "Yeah, that's been logged since Tuesday. No maintenance on it yet that I've heard."
- If the issue has worsened, log a new entry with the updated description and note that it's a recurrence or escalation.
- If it's the same status, don't create a duplicate. Just confirm it's still being tracked.

### After logging

Acknowledge the report. Let the operator know it's been recorded and will be visible to maintenance. Keep it brief:

- "Logged it. Maintenance will see it."
- "Got it -- hydraulic leak, logged and tracked."
- "Flagged the sluggish boom. Still good to run for now, but maintenance will be in the loop."

Add the issue to MEMORY.md Open Items so it persists across sessions until resolved.

## Output

- **Outbox writes:** Write a timestamped issue entry to outbox/:
  ```
  ---
  from: {ASSET_ID}
  type: issue
  timestamp: {ISO-8601}
  ---
  description: {ISSUE_DESCRIPTION}
  category: {hydraulic|engine|electrical|structural|safety|other}
  operational: {yes|no}
  reporter: {OPERATOR_NAME}
  ```
- **AGENTS.md (State) updates:** Update `open_issues` count.
- **MEMORY.md updates:** Add new issue to Open Items section with description, category, and date. If the issue resolves a question from a previous pre-op flag, note the connection.
- **Messages to user:** Brief acknowledgment confirming the issue was logged. If safety-critical, include the escalation note.
