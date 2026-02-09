---
name: fleet-director
description: Distribute fleet-wide directives from leadership to scoped asset agents via Redis
metadata: {"openclaw":{"requires":{"bins":["redis-cli"],"env":["REDIS_URL"]}}}
---

# Fleet Director

_Accept directives from leadership, fan them out to the right asset agents, and log them for audit._

## Trigger

- **Message** — Leadership issues a directive (e.g., "all machines need fire extinguisher check before next shift", "excavators should reduce idle time in zone 3", "EX-001 and EX-003 need to avoid the north pit today")

## Input

- **User messages:** Natural language directives from managers, safety reps, or owners
- **Redis keys:**
  - `fleet:index:active` — all active asset IDs (for scope "all" and resolving category references)
  - `fleet:directives` — audit log of all issued directives

## Behavior

### Parse the directive

When leadership gives a directive, extract four things from their message:

1. **The instruction** — what needs to happen, in plain language. Keep their wording. Do not rephrase a safety directive into something softer.
2. **The scope** — who it applies to. Two options:
   - All active assets (they say "all machines", "entire fleet", "everyone")
   - Specific assets by ID (they say "EX-001 and EX-003", "just KOT28", or refer to equipment categories like "all excavators" — resolve to specific IDs from the active index)
3. **Who issued it** — the person giving the directive (from their Telegram identity or what they say: "this is from the safety rep")
4. **Expiry** — optional. If they say "until end of shift", "for the next 24 hours", "until further notice", note it. If they do not mention a timeframe, leave it open-ended.

If the scope is unclear, ask once. "Should that go to all machines, or just the excavators?"

### Fan out to asset agents

Once the directive is clear, distribute it to the scoped assets:

- **Scope "all":** Read `fleet:index:active` to get every active asset ID. Write to each asset's inbox.
- **Scope by category:** If the user refers to an equipment category ("excavators", "haul trucks"), read `fleet:index:active` to get all active IDs, identify matching assets by their ID prefixes or naming conventions, then write to each matching asset's inbox.
- **Scope specific:** Write directly to the named assets' inboxes.

Each inbox message should include the type "directive", a human-readable summary (the instruction text), and from "clawordinator."

### Log for audit

Write the directive to the central `fleet:directives` stream with the full details: scope, instruction text, who issued it, and expiry if applicable. This is the fleet-wide audit trail that Clawvisor and Clawordinator can reference later.

### Confirm to the user

Tell the user exactly what happened: what instruction was sent, to how many assets, with what scope. If scoped by type or specific IDs, list them. If there is an expiry, confirm it.

Example: "Sent 'fire extinguisher check before next shift' to all 14 active assets. No expiry set."

Example: "Sent 'reduce idle time in zone 3' to 5 excavators (EX-001, EX-003, EX-005, EX-007, EX-009). Expires end of shift."

## Output

- **Redis writes:**
  ```
  XADD fleet:directives MAXLEN ~ 200 * \
    scope "{all|specific}" \
    instruction "{INSTRUCTION_TEXT}" \
    issued_by "{PERSON_OR_ROLE}" \
    expires "{ISO_DATETIME_OR_EMPTY}"

  # Per scoped asset:
  XADD fleet:asset:{ID}:inbox MAXLEN ~ 100 * \
    type "directive" \
    summary "{INSTRUCTION_TEXT}" \
    from "clawordinator"
  ```
- **MEMORY.md updates:** Add to Pending Directives with instruction text, date, who issued it, scope, and asset count. Active until expired or fully acknowledged.
- **Messages to user:** Confirmation with scope, asset count, and instruction summary.
