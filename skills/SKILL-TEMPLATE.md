---
name: skill-name
description: One-line description of what this skill teaches the agent
metadata: {"openclaw":{"requires":{"bins":[],"env":[]}}}
---

# Skill Name

_One-line description of what this skill teaches the agent._

## Trigger

_When does the agent activate this behavior?_

- **Message** — Operator/user says something relevant
- **Heartbeat** — Agent checks on its regular polling cycle
- **Session start** — Agent wakes up and reviews context
- **Inbox message** — New file appears in inbox/

_(Delete triggers that don't apply. Most skills use 1-2 triggers.)_

## Input

_What data does this skill consume?_

- **User messages:** Natural language from operator/user
- **Inbox files:** _(describe expected message types and their frontmatter fields)_
- **Outbox files:** _(for Clawvisor/Clawordinator reading other agents' outboxes)_
- **state.md:** _(what state fields does this skill need?)_
- **fleet.md:** _(does this skill need fleet composition data?)_
- **MEMORY.md:** _(what historical context does this skill need?)_
- **.env variables:** _(API credentials, config — specify variable names)_

_(Delete inputs that don't apply.)_

## Behavior

_Plain English instructions for the agent. This is the core of the skill._

_Not code. Not pseudocode. Instructions a smart person would follow._

_Include examples of interactions where helpful._

## Output

_What does this skill produce?_

- **Outbox writes:** _(describe file format — YAML frontmatter + markdown body)_
- **Inbox writes:** _(for Clawvisor/Clawordinator writing to other agents' inboxes)_
- **state.md updates:** _(what fields to update)_
- **fleet.md updates:** _(Clawordinator only)_
- **MEMORY.md updates:** _(what to remember)_
- **Messages to user:** _(conversational responses)_
- **Escalation flags:** _(when to hand off, and to whom)_

_(Delete outputs that don't apply.)_

## Overdue Condition

_(Optional — only include if the nudger should monitor this skill.)_

_[What's missing] after [time threshold] since [reference event]._

_Example: No fuel log within 8 hours of the operator's first message this shift._
