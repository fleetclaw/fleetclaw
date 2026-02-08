---
name: onboarding-agent
description: Add new equipment to the fleet configuration via natural language
metadata: {"openclaw":{"requires":{"bins":["python3"],"env":[]}}}
---

# Onboarding Agent

Add new assets to the fleet through conversational interaction.

## When to Use

Trigger on requests like:
- "Add new excavator EX-005"
- "Onboard a Komatsu HD785 rigid haul truck"
- "Register new loader LD-004 on host-02"

## Workflow

### Step 1: Collect Required Fields

Ask for these if not provided:
- **asset_id** - Format: `XX-NNN` (e.g., EX-005, LD-012)
- **type** - One of: `excavator`, `loader`, `rigid_haul_truck`, `material_handler`, `semi_truck`, `dump_truck`, `motor_grader`, `wheel_tractor`, `skid_steer`, `track_dozer`, `telehandler`, `water_truck`, `backhoe`, `dth_drill`
- **host** - Deployment host (e.g., host-01)

### Step 2: Collect Common Fields

Ask for or use defaults:
- **make** - Manufacturer (default: "Unknown")
- **model** - Model number (default: "Unknown")
- **telegram_group** - e.g., `@ex005_ops` (default: derive from asset_id)

### Step 3: Collect Specs (Optional)

If user provides fuel info:
- **tank_capacity** - Liters
- **avg_consumption** - L/hr (min/max computed automatically)

### Step 4: Validate with Dry Run

```bash
python scripts/auto_onboard.py --dry-run --json '{
  "asset_id": "EX-005",
  "type": "excavator",
  "host": "host-01",
  "make": "CAT",
  "model": "390F",
  "telegram_group": "@ex005_ops",
  "specs": {"tank_capacity": 680, "avg_consumption": 28}
}'
```

### Step 5: Execute Onboarding

If validation passes:
```bash
python scripts/auto_onboard.py --json '{...}'
```

### Step 6: Regenerate Configs

```bash
python scripts/generate-configs.py --target-asset EX-005
```

## Response Templates

### Success
```
Asset EX-005 added to fleet configuration.

Next steps:
1. Add TELEGRAM_TOKEN_EX_005 to .env
2. Workspace generated at generated/workspaces/EX-005/
3. Deploy with: docker compose up -d ex-005
```

### Validation Error
```
Cannot add asset: [error message]

Please correct and try again.
```

## Examples

**User:** "Add excavator EX-005, it's a CAT 390F going on host-01"

**Agent:** Extracts: asset_id=EX-005, type=excavator, make=CAT, model=390F, host=host-01
Derives: telegram_group=@ex005_ops
Executes onboarding script and reports success.
