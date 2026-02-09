#!/usr/bin/env python3
"""
FleetClaw Config Generator

Reads fleet.yaml and produces:
  output/workspaces/{ID}/SOUL.md       — per-agent identity
  output/config/openclaw-{ID}.json     — per-agent OpenClaw config
  output/docker-compose.yml            — full compose file
  output/.env.template                 — all required env vars
  output/setup-redis.sh                — one-time consumer group creation

Usage:
  python generate-configs.py [fleet.yaml]

If no argument is given, reads fleet.yaml from the current directory.
"""

import json
import os
import sys
from pathlib import Path

# Optional: PyYAML
try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Skill mount mapping — which skills each agent role gets
# ---------------------------------------------------------------------------
SKILL_MOUNTS = {
    "asset": [
        "fuel-logger",
        "meter-reader",
        "pre-op",
        "issue-reporter",
        "nudger",
        "memory-curator-asset",
    ],
    "clawvisor": [
        "fleet-status",
        "compliance-tracker",
        "maintenance-logger",
        "anomaly-detector",
        "shift-summary",
        "escalation-handler",
        "asset-query",
        "memory-curator-clawvisor",
    ],
    "clawordinator": [
        "asset-onboarder",
        "asset-lifecycle",
        "fleet-director",
        "escalation-resolver",
        "fleet-analytics",
        "fleet-config",
        "memory-curator-clawordinator",
    ],
}

# Consumer groups per stream type
CONSUMER_GROUPS = {
    "fuel": ["clawvisor", "anomaly-detector"],
    "meter": ["clawvisor", "anomaly-detector"],
    "preop": ["clawvisor"],
    "issues": ["clawvisor"],
    "alerts": ["clawordinator"],
}

FLEET_CONSUMER_GROUPS = {
    "fleet:directives": ["clawvisor"],
    "fleet:escalations": ["clawordinator"],
}


def load_fleet_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_template(template_name: str) -> str:
    template_path = Path(__file__).parent / "templates" / template_name
    with open(template_path, "r") as f:
        return f.read()


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def generate_soul(template: str, asset_id: str = "", serial: str = "") -> str:
    """Apply substitutions to a SOUL.md template."""
    result = template.replace("{ASSET_ID}", asset_id)
    result = result.replace("{SERIAL}", serial)
    return result


def generate_openclaw_config(
    template: dict,
    heartbeat: str,
    shift_start: str,
    shift_end: str,
    timezone: str,
    asset_id: str = "",
) -> dict:
    """Apply substitutions to an openclaw.json template."""
    raw = json.dumps(template)
    raw = raw.replace("{HEARTBEAT}", heartbeat)
    raw = raw.replace("{SHIFT_START}", shift_start)
    raw = raw.replace("{SHIFT_END}", shift_end)
    raw = raw.replace("{TIMEZONE}", timezone)
    raw = raw.replace("{ASSET_ID}", asset_id)
    return json.loads(raw)


def generate_compose_service_asset(asset: dict, fleet: dict) -> dict:
    """Generate a docker-compose service definition for an asset agent."""
    aid = asset["id"]
    aid_lower = aid.lower().replace("-", "")
    service_name = f"fc-agent-{aid_lower}"

    skill_volumes = [
        f"./skills/{s}:/app/skills/{s}:ro" for s in SKILL_MOUNTS["asset"]
    ]

    return {
        service_name: {
            "build": {"context": ".", "dockerfile": "docker/Dockerfile"},
            "container_name": service_name,
            "entrypoint": "node",
            "command": "dist/index.js gateway",
            "environment": [
                f"REDIS_URL={fleet.get('redis_url', 'redis://redis:6379')}",
                f"TELEGRAM_TOKEN_{aid}=${{TELEGRAM_TOKEN_{aid}}}",
                "FIREWORKS_API_KEY=${FIREWORKS_API_KEY}",
                f"OPENCLAW_MODEL={fleet.get('model', '')}",
                "OPENCLAW_GATEWAY_TOKEN=${OPENCLAW_GATEWAY_TOKEN}",
                "NODE_OPTIONS=--max-old-space-size=384",
            ],
            "deploy": {
                "resources": {
                    "limits": {"memory": "512m"},
                    "reservations": {"memory": "256m"},
                },
            },
            "logging": {
                "driver": "json-file",
                "options": {"max-size": "10m", "max-file": "3"},
            },
            "volumes": [
                f"./data/{aid}:/home/node/.openclaw",
                f"./output/workspaces/{aid}:/home/node/.openclaw/workspace",
                f"./output/config/openclaw-{aid}.json:/home/node/.openclaw/openclaw.json:ro",
            ]
            + skill_volumes,
            "depends_on": {
                "redis": {"condition": "service_healthy"},
            },
            "restart": "unless-stopped",
            "healthcheck": {
                "test": ["CMD", "node", "-e", "require('http').get('http://localhost:18789/health', r => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"],
                "interval": "60s",
                "timeout": "10s",
                "retries": 3,
                "start_period": "60s",
            },
            "networks": ["fleetclaw"],
        }
    }


def generate_compose_service_clawvisor(fleet: dict) -> dict:
    """Generate Clawvisor's docker-compose service."""
    skill_volumes = [
        f"./skills/{s}:/app/skills/{s}:ro" for s in SKILL_MOUNTS["clawvisor"]
    ]

    return {
        "fc-clawvisor": {
            "build": {"context": ".", "dockerfile": "docker/Dockerfile"},
            "container_name": "fc-clawvisor",
            "entrypoint": "node",
            "command": "dist/index.js gateway",
            "environment": [
                f"REDIS_URL={fleet.get('redis_url', 'redis://redis:6379')}",
                "TELEGRAM_TOKEN_CLAWVISOR=${TELEGRAM_TOKEN_CLAWVISOR}",
                "FIREWORKS_API_KEY=${FIREWORKS_API_KEY}",
                f"OPENCLAW_MODEL={fleet.get('model', '')}",
                "OPENCLAW_GATEWAY_TOKEN=${OPENCLAW_GATEWAY_TOKEN}",
                "NODE_OPTIONS=--max-old-space-size=384",
            ],
            "deploy": {
                "resources": {
                    "limits": {"memory": "1g"},
                    "reservations": {"memory": "512m"},
                },
            },
            "logging": {
                "driver": "json-file",
                "options": {"max-size": "10m", "max-file": "3"},
            },
            "volumes": [
                "./data/clawvisor:/home/node/.openclaw",
                "./output/workspaces/clawvisor:/home/node/.openclaw/workspace",
                "./output/config/openclaw-clawvisor.json:/home/node/.openclaw/openclaw.json:ro",
            ]
            + skill_volumes,
            "depends_on": {
                "redis": {"condition": "service_healthy"},
            },
            "restart": "unless-stopped",
            "healthcheck": {
                "test": ["CMD", "node", "-e", "require('http').get('http://localhost:18789/health', r => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"],
                "interval": "60s",
                "timeout": "10s",
                "retries": 3,
                "start_period": "60s",
            },
            "networks": ["fleetclaw"],
        }
    }


def generate_compose_service_clawordinator(fleet: dict) -> dict:
    """Generate Clawordinator's docker-compose service."""
    skill_volumes = [
        f"./skills/{s}:/app/skills/{s}:ro" for s in SKILL_MOUNTS["clawordinator"]
    ]

    return {
        "fc-docker-proxy": {
            "image": "tecnativa/docker-socket-proxy:latest",
            "container_name": "fc-docker-proxy",
            "environment": [
                "CONTAINERS=1",
                "POST=1",
            ],
            "volumes": ["/var/run/docker.sock:/var/run/docker.sock:ro"],
            "restart": "unless-stopped",
            "networks": ["fleetclaw"],
            "logging": {
                "driver": "json-file",
                "options": {"max-size": "5m", "max-file": "2"},
            },
        },
        "fc-clawordinator": {
            "build": {
                "context": ".",
                "dockerfile": "docker/Dockerfile.clawordinator",
            },
            "container_name": "fc-clawordinator",
            "entrypoint": "node",
            "command": "dist/index.js gateway",
            "environment": [
                f"REDIS_URL={fleet.get('redis_url', 'redis://redis:6379')}",
                "TELEGRAM_TOKEN_CLAWORDINATOR=${TELEGRAM_TOKEN_CLAWORDINATOR}",
                "FIREWORKS_API_KEY=${FIREWORKS_API_KEY}",
                f"OPENCLAW_MODEL={fleet.get('model', '')}",
                "OPENCLAW_GATEWAY_TOKEN=${OPENCLAW_GATEWAY_TOKEN}",
                "DOCKER_HOST=tcp://fc-docker-proxy:2375",
                "NODE_OPTIONS=--max-old-space-size=384",
            ],
            "deploy": {
                "resources": {
                    "limits": {"memory": "1g"},
                    "reservations": {"memory": "512m"},
                },
            },
            "logging": {
                "driver": "json-file",
                "options": {"max-size": "10m", "max-file": "3"},
            },
            "volumes": [
                "./data/clawordinator:/home/node/.openclaw",
                "./output/workspaces/clawordinator:/home/node/.openclaw/workspace",
                "./output/config/openclaw-clawordinator.json:/home/node/.openclaw/openclaw.json:ro",
            ]
            + skill_volumes,
            "depends_on": {
                "redis": {"condition": "service_healthy"},
                "fc-docker-proxy": {"condition": "service_started"},
            },
            "restart": "unless-stopped",
            "healthcheck": {
                "test": ["CMD", "node", "-e", "require('http').get('http://localhost:18789/health', r => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"],
                "interval": "60s",
                "timeout": "10s",
                "retries": 3,
                "start_period": "60s",
            },
            "networks": ["fleetclaw"],
        },
    }


def generate_compose_redis() -> dict:
    """Generate Redis service definition."""
    return {
        "redis": {
            "image": "redis:7.4-alpine",
            "container_name": "fc-redis",
            "command": (
                "redis-server"
                " --appendonly yes"
                " --aof-use-rdb-preamble yes"
                " --maxmemory 512mb"
                " --maxmemory-policy noeviction"
                " --maxclients 512"
            ),
            "volumes": ["redis-data:/data"],
            "deploy": {
                "resources": {
                    "limits": {"memory": "768m"},
                    "reservations": {"memory": "256m"},
                },
            },
            "logging": {
                "driver": "json-file",
                "options": {"max-size": "10m", "max-file": "3"},
            },
            "healthcheck": {
                "test": ["CMD", "redis-cli", "ping"],
                "interval": "10s",
                "timeout": "5s",
                "retries": 5,
            },
            "restart": "unless-stopped",
            "networks": ["fleetclaw"],
        }
    }


def generate_setup_redis(assets: list, redis_url: str) -> str:
    """Generate setup-redis.sh for consumer group creation."""
    lines = [
        "#!/bin/bash",
        "# FleetClaw Redis Setup - Consumer Group Creation",
        "# Run once before first deployment:",
        "#   chmod +x setup-redis.sh && ./setup-redis.sh",
        "",
        f'REDIS_URL="${{REDIS_URL:-{redis_url}}}"',
        "",
        'echo "Creating consumer groups..."',
        "",
        "# Per-asset streams",
    ]

    for asset in assets:
        aid = asset["id"]
        lines.append(f"# {aid}")
        for stream_type, groups in CONSUMER_GROUPS.items():
            for group in groups:
                lines.append(
                    f'redis-cli -u $REDIS_URL XGROUP CREATE fleet:asset:{aid}:{stream_type} {group} $ MKSTREAM 2>/dev/null || echo "  {aid}:{stream_type}/{group} already exists"'
                )
        lines.append("")

    lines.append("# Fleet-wide streams")
    for stream, groups in FLEET_CONSUMER_GROUPS.items():
        for group in groups:
            lines.append(
                f'redis-cli -u $REDIS_URL XGROUP CREATE {stream} {group} $ MKSTREAM 2>/dev/null || echo "  {stream}/{group} already exists"'
            )

    lines.append("")
    lines.append('echo "Done."')
    return "\n".join(lines) + "\n"


def generate_env_template(assets: list) -> str:
    """Generate .env.template with all required variables."""
    lines = [
        "# FleetClaw Environment Variables",
        "# Fill in all values before running docker compose up",
        "",
        "# LLM Provider",
        "FIREWORKS_API_KEY=",
        "",
        "# OpenClaw Gateway (generate a random token)",
        "OPENCLAW_GATEWAY_TOKEN=",
        "",
        "# Telegram Bot Tokens - one per agent",
        "# Create bots via @BotFather on Telegram",
        "",
        "# Asset Agents",
    ]

    for asset in assets:
        lines.append(f"TELEGRAM_TOKEN_{asset['id']}=")

    lines.extend([
        "",
        "# Clawvisor",
        "TELEGRAM_TOKEN_CLAWVISOR=",
        "",
        "# Clawordinator",
        "TELEGRAM_TOKEN_CLAWORDINATOR=",
    ])

    return "\n".join(lines) + "\n"


def main():
    # Resolve input file
    config_path = sys.argv[1] if len(sys.argv) > 1 else "fleet.yaml"
    if not os.path.exists(config_path):
        # Try .example
        if os.path.exists(config_path + ".example"):
            config_path = config_path + ".example"
        else:
            print(f"ERROR: {config_path} not found")
            sys.exit(1)

    print(f"Reading {config_path}...")
    config = load_fleet_config(config_path)

    fleet = config["fleet"]
    assets = config["assets"]
    heartbeats = config.get("heartbeats", {})

    # Defaults
    hb_asset = heartbeats.get("asset", "30m")
    hb_clawvisor = heartbeats.get("clawvisor", "2h")
    hb_clawordinator = heartbeats.get("clawordinator", "4h")
    shift_start = fleet.get("shift_start", "06:00")
    shift_end = fleet.get("shift_end", "18:00")
    timezone = fleet.get("timezone", "UTC")
    redis_url = fleet.get("redis_url", "redis://redis:6379")

    # Output directory
    output = Path("output")
    ensure_dir(output / "workspaces")
    ensure_dir(output / "config")

    # Load templates
    soul_asset_tpl = load_template("soul-asset.md")
    soul_clawvisor_tpl = load_template("soul-clawvisor.md")
    soul_clawordinator_tpl = load_template("soul-clawordinator.md")

    with open(Path(__file__).parent / "templates" / "openclaw-asset.json") as f:
        oc_asset_tpl = json.load(f)
    with open(Path(__file__).parent / "templates" / "openclaw-clawvisor.json") as f:
        oc_clawvisor_tpl = json.load(f)
    with open(Path(__file__).parent / "templates" / "openclaw-clawordinator.json") as f:
        oc_clawordinator_tpl = json.load(f)

    # -----------------------------------------------------------------------
    # Generate per-asset files
    # -----------------------------------------------------------------------
    compose_services = {}
    compose_services.update(generate_compose_redis())

    for asset in assets:
        aid = asset["id"]
        serial = asset.get("serial", "")

        if "type" in asset:
            print(f"  WARNING: asset {aid} has deprecated 'type' field (ignored)", file=sys.stderr)

        print(f"  Generating {aid}...")

        # SOUL.md
        ws_dir = output / "workspaces" / aid
        ensure_dir(ws_dir)
        soul = generate_soul(soul_asset_tpl, aid, serial)
        with open(ws_dir / "SOUL.md", "w") as f:
            f.write(soul)

        # openclaw.json
        oc = generate_openclaw_config(
            oc_asset_tpl, hb_asset, shift_start, shift_end, timezone, aid
        )
        with open(output / "config" / f"openclaw-{aid}.json", "w") as f:
            json.dump(oc, f, indent=2)
            f.write("\n")

        # Compose service
        compose_services.update(
            generate_compose_service_asset(asset, fleet)
        )

    # -----------------------------------------------------------------------
    # Generate Clawvisor
    # -----------------------------------------------------------------------
    print("  Generating Clawvisor...")

    ws_dir = output / "workspaces" / "clawvisor"
    ensure_dir(ws_dir)
    with open(ws_dir / "SOUL.md", "w") as f:
        f.write(soul_clawvisor_tpl)

    oc = generate_openclaw_config(
        oc_clawvisor_tpl, hb_clawvisor, shift_start, shift_end, timezone
    )
    with open(output / "config" / "openclaw-clawvisor.json", "w") as f:
        json.dump(oc, f, indent=2)
        f.write("\n")

    compose_services.update(
        generate_compose_service_clawvisor(fleet)
    )

    # -----------------------------------------------------------------------
    # Generate Clawordinator
    # -----------------------------------------------------------------------
    print("  Generating Clawordinator...")

    ws_dir = output / "workspaces" / "clawordinator"
    ensure_dir(ws_dir)
    with open(ws_dir / "SOUL.md", "w") as f:
        f.write(soul_clawordinator_tpl)

    oc = generate_openclaw_config(
        oc_clawordinator_tpl, hb_clawordinator, shift_start, shift_end, timezone
    )
    with open(output / "config" / "openclaw-clawordinator.json", "w") as f:
        json.dump(oc, f, indent=2)
        f.write("\n")

    compose_services.update(
        generate_compose_service_clawordinator(fleet)
    )

    # -----------------------------------------------------------------------
    # Write docker-compose.yml
    # -----------------------------------------------------------------------
    print("  Writing docker-compose.yml...")

    compose = {
        "services": compose_services,
        "volumes": {"redis-data": {"driver": "local"}},
        "networks": {
            "fleetclaw": {"driver": "bridge"},
        },
    }

    with open(output / "docker-compose.yml", "w") as f:
        yaml.dump(compose, f, default_flow_style=False, sort_keys=False)

    # -----------------------------------------------------------------------
    # Write .env.template
    # -----------------------------------------------------------------------
    print("  Writing .env.template...")
    with open(output / ".env.template", "w") as f:
        f.write(generate_env_template(assets))

    # -----------------------------------------------------------------------
    # Write setup-redis.sh
    # -----------------------------------------------------------------------
    print("  Writing setup-redis.sh...")
    with open(output / "setup-redis.sh", "w") as f:
        f.write(generate_setup_redis(assets, redis_url))

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print()
    print(f"Generated config for {len(assets)} assets + Clawvisor + Clawordinator")
    print(f"Output directory: {output.resolve()}")
    print()
    print("Next steps:")
    print(f"  1. Copy {output / '.env.template'} to .env and fill in tokens")
    print(f"  2. Run: bash {output / 'setup-redis.sh'}")
    print(f"  3. Run: docker compose -f {output / 'docker-compose.yml'} --project-directory . up -d")


if __name__ == "__main__":
    main()
