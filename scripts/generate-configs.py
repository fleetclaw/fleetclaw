#!/usr/bin/env python3
"""
Fleetclaw Configuration Generator

Reads fleet.yaml and generates:
- Per-host docker-compose.yml files
- Per-asset openclaw.json configs
- Per-asset workspace directories with full OpenClaw workspace structure

Usage:
    python scripts/generate-configs.py [--fleet-file fleet.yaml] [--output-dir ./generated]
"""

import argparse
import hashlib
import os
import platform
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jinja2 import FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment

try:
    from pydantic import ValidationError
    from models import validate_fleet_config
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False


TIME_FORMAT_PATTERN = re.compile(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')

# Maximum stagger offset in minutes for scheduled tasks
MAX_STAGGER_MINUTES = 10

# Default model for OpenClaw agents (Fireworks AI)
DEFAULT_OPENCLAW_MODEL = 'fireworks/accounts/fireworks/models/kimi-k2p5'


def calculate_stagger_minutes(asset_id: str, max_stagger: int = MAX_STAGGER_MINUTES) -> int:
    """Calculate deterministic stagger offset based on asset ID hash.

    This prevents thundering herd when all assets broadcast status at the same time.
    Uses MD5 hash for cross-platform/cross-process stability (Python's built-in
    hash() is randomized per process via PYTHONHASHSEED).

    Args:
        asset_id: Unique identifier for the asset
        max_stagger: Maximum number of minutes to stagger (default 10)

    Returns:
        Integer offset in minutes (0 to max_stagger-1)
    """
    # Use MD5 for deterministic hashing across processes/hosts
    digest = hashlib.md5(asset_id.encode('utf-8')).digest()
    return digest[0] % max_stagger

# Asset type metadata: (display_name, emoji, soul_template)
ASSET_TYPE_METADATA = {
    # Original types
    'excavator': ('Excavator', '\U0001F3D7', 'excavator-soul.md'),
    'wheel_loader': ('Wheel Loader', '\U0001F4E6', 'wheel-loader-soul.md'),
    'fleet_coordinator': ('Fleet Coordinator', '\U0001F4CB', 'fleet-coordinator-soul.md'),

    # Equipment types - existing
    'rigid_haul_truck': ('Rigid Frame Haul Truck', '\U0001F69B', 'rigid-haul-truck-soul.md'),
    'material_handler': ('Material Handler', '\U0001F9F2', 'material-handler-soul.md'),
    'semi_truck': ('Semi Truck', '\U0001F69A', 'semi-truck-soul.md'),
    'dump_truck': ('Dump Truck', '\U0001F6FB', 'dump-truck-soul.md'),
    'motor_grader': ('Motorgrader', '\U0001F6A7', 'motor-grader-soul.md'),
    'wheel_tractor': ('Wheel Tractor', '\U0001F69C', 'wheel-tractor-soul.md'),
    'skid_steer': ('Skid Steer', '\U0001F4A8', 'skid-steer-soul.md'),
    'track_dozer': ('Track Dozer', '\U0001F6A7', 'track-dozer-soul.md'),
    'telehandler': ('Telehandler', '\U0001F3D7', 'telehandler-soul.md'),

    # Odometer-based (on-road vehicles)
    'bucket_truck': ('Bucket Truck', '\U0001FA63', 'bucket-truck-soul.md'),
    'compact_pickup': ('Compact Pickup', '\U0001F6FB', 'compact-pickup-soul.md'),
    'delivery_truck': ('Delivery Truck', '\U0001F4E6', 'delivery-truck-soul.md'),
    'mixing_system': ('Mixing System Truck Mtd', '\U0001F504', 'mixing-system-truck-mtd-soul.md'),
    'service_truck': ('Service Truck', '\U0001F527', 'service-truck-soul.md'),
    'spreader_truck': ('Spreader Truck', '\U0001F9C2', 'spreader-truck-soul.md'),
    'supervisor_truck': ('Supervisor Truck', '\U0001F477', 'supervisor-truck-soul.md'),
    'suv': ('SUV', '\U0001F699', 'suv-soul.md'),
    'water_truck': ('Water Truck', '\U0001F4A7', 'water-truck-soul.md'),
    'work_truck': ('Work Truck', '\U0001F528', 'work-truck-soul.md'),

    # Months-based (specialized pumps)
    'boom_truck_pump': ('Boom Truck Pump', '\U0001F3D7', 'boom-truck-pump-soul.md'),
    'telebelt': ('Telebelt', '\U0001F4CF', 'telebelt-soul.md'),
    'tower_pump': ('Tower Pump', '\U0001F5FC', 'tower-pump-soul.md'),

    # Hour meter-based (off-road equipment)
    'artic_dump_truck': ('Artic. Dump Truck', '\U0001F69B', 'artic-dump-truck-soul.md'),
    'backhoe': ('Backhoe', '\U0001F9BE', 'backhoe-soul.md'),
    'ct_forklift': ('CT Forklift', '\U0001F3CB', 'ct-forklift-soul.md'),
    'directional_drill': ('Directional Drill', '\U0001F529', 'directional-drill-soul.md'),
    'dth_surface_drill': ('DTH Surface Drill', '\U000026CF', 'dth-surface-drill-soul.md'),
    'hb_rt_crane': ('HB RT Crane', '\U0001F3D7', 'hb-rt-crane-soul.md'),
    'hb_truck_crane': ('HB Truck Crane', '\U0001F3D7', 'hb-truck-crane-soul.md'),
    'hydro_seeder': ('Hydro-Seeder', '\U0001F331', 'hydro-seeder-soul.md'),
    'landfill_compactor': ('Landfill Compactor', '\U0001F5D1', 'landfill-compactor-soul.md'),
    'lb_track_crane': ('LB Track Crane', '\U0001F3D7', 'lb-track-crane-soul.md'),
    'lb_truck_crane': ('LB Truck Crane', '\U0001F3D7', 'lb-truck-crane-soul.md'),
    'pneumatic_roller': ('Pneumatic Roller', '\U0001F6DE', 'pneumatic-roller-soul.md'),
    'road_reclaimer': ('Road Reclaimer', '\U0001F6E3', 'road-reclaimer-soul.md'),
    'road_widener': ('Road Widener', '\U0001F6E3', 'road-widener-soul.md'),
    'rt_forklift': ('RT Forklift', '\U0001F3CB', 'rt-forklift-soul.md'),
    'scraper': ('Scraper', '\U0001FA92', 'scraper-soul.md'),
    'soil_compactor': ('Soil Compactor', '\U0001F6DE', 'soil-compactor-soul.md'),
    'soil_stabilizer': ('Soil Stabilizer', '\U0001F9F1', 'soil-stabilizer-soul.md'),
    'track_loader': ('Track Loader', '\U0001F4E6', 'track-loader-soul.md'),
    'track_mtd_auger': ('Track Mtd Auger', '\U0001F529', 'track-mtd-auger-soul.md'),
    'track_tractor': ('Track Tractor', '\U0001F69C', 'track-tractor-soul.md'),
    'trencher': ('Trencher', '\U0001F573', 'trencher-soul.md'),
    'trk_asphalt_paver': ('Trk Asphalt Paver', '\U0001F6E3', 'trk-asphalt-paver-soul.md'),
    'trk_cold_planer': ('Trk Cold Planer', '\U0001F6E3', 'trk-cold-planer-soul.md'),
    'truck_crane_rear_engine': ('Truck Crane Rear Engine', '\U0001F3D7', 'truck-crane-rear-engine-soul.md'),
    'truck_mtd_auger': ('Truck Mtd Auger', '\U0001F529', 'truck-mtd-auger-soul.md'),
    'vacuum_excavator': ('Vacuum Excavator', '\U0001F300', 'vacuum-excavator-soul.md'),
    'water_wagon': ('Water Wagon', '\U0001F4A7', 'water-wagon-soul.md'),
    'whl_asphalt_paver': ('Whl Asphalt Paver', '\U0001F6E3', 'whl-asphalt-paver-soul.md'),
    'whl_cold_planer': ('Whl Cold Planer', '\U0001F6E3', 'whl-cold-planer-soul.md'),

    # Legacy aliases
    'loader': ('Wheel Loader', '\U0001F4E6', 'wheel-loader-soul.md'),
    'dth_drill': ('DTH Drill', '\U0001F4A5', 'dth-surface-drill-soul.md'),
}

# Workspace template files to generate for each asset
WORKSPACE_TEMPLATES = [
    ('AGENTS.md.template', 'AGENTS.md'),
    ('USER.md.template', 'USER.md'),
    ('TOOLS.md.template', 'TOOLS.md'),
    ('IDENTITY.md.template', 'IDENTITY.md'),
    ('BOOT.md.template', 'BOOT.md'),
    ('HEARTBEAT.md.template', 'HEARTBEAT.md'),
]

# Hook definitions to copy to each workspace
HOOKS = ['session-memory', 'boot-md', 'fuel-log-received']


def asset_id_to_env_key(asset_id: str) -> str:
    """Convert asset ID to environment variable key format (EX-001 -> EX_001)."""
    return asset_id.replace('-', '_')


def group_assets_by_type(assets: list) -> dict:
    """Group assets by their type field.

    Args:
        assets: List of asset dictionaries with 'type' field

    Returns:
        Dict mapping asset_type -> list of assets
    """
    assets_by_type = {}
    for asset in assets:
        asset_type = asset['type']
        if asset_type not in assets_by_type:
            assets_by_type[asset_type] = []
        assets_by_type[asset_type].append(asset)
    return assets_by_type


def load_env_file(path: Path) -> dict[str, str]:
    """Load key=value pairs from a .env file.

    Ignores comments (#) and empty lines.
    Does not handle quoted values or variable expansion.
    """
    env_vars = {}
    if not path.exists():
        return env_vars
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, _, value = line.partition('=')
            value = value.strip()
            # Strip surrounding quotes (single or double)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
                value = value[1:-1]
            env_vars[key.strip()] = value
    return env_vars


def validate_time_format(time_str: str, field_name: str) -> str:
    """Validate time format (HH:MM). Raises ValueError if invalid."""
    if not isinstance(time_str, str):
        raise ValueError(f"{field_name} must be a string, got {type(time_str).__name__}")

    if not TIME_FORMAT_PATTERN.match(time_str):
        raise ValueError(f"{field_name} must be in HH:MM format (e.g., '06:00'), got '{time_str}'")

    return time_str


def extract_hour_from_time(time_str: str, field_name: str) -> int:
    """Extract and validate hour from time string. Returns hour as integer."""
    validated = validate_time_format(time_str, field_name)
    return int(validated.split(':')[0])


def load_fleet_config(fleet_file: Path, skip_validation: bool = False) -> dict:
    """Load and validate fleet configuration.

    Args:
        fleet_file: Path to fleet.yaml configuration file
        skip_validation: If True, skip Pydantic validation (for debugging)

    Returns:
        Validated configuration dictionary

    Raises:
        ValueError: If required keys are missing
        pydantic.ValidationError: If Pydantic validation fails
    """
    config = yaml.safe_load(fleet_file.read_text(encoding='utf-8'))

    required_keys = ['fleet', 'coordinator', 'assets', 'hosts']
    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required key in fleet.yaml: {key}")

    # Run Pydantic validation if available
    if PYDANTIC_AVAILABLE and not skip_validation:
        try:
            validate_fleet_config(config)
            print("  Configuration validation: PASSED")
        except ValidationError as e:
            print("\n  Configuration validation: FAILED")
            print("  " + "-" * 50)
            for error in e.errors():
                loc = ' -> '.join(str(x) for x in error['loc'])
                print(f"  {loc}: {error['msg']}")
            print("  " + "-" * 50)
            raise

    return config


def get_asset_display_name(asset_type: str) -> str:
    """Get display name for an asset type."""
    metadata = ASSET_TYPE_METADATA.get(asset_type)
    return metadata[0] if metadata else asset_type


def get_asset_emoji(asset_type: str) -> str:
    """Get emoji for an asset type."""
    metadata = ASSET_TYPE_METADATA.get(asset_type)
    return metadata[1] if metadata else ''


def get_asset_template(asset_type: str) -> str:
    """Get SOUL.md template name for an asset type."""
    metadata = ASSET_TYPE_METADATA.get(asset_type)
    return metadata[2] if metadata else 'misc-equipment-soul.md'


def calculate_next_service(current_hours: int, interval: int) -> int:
    """Calculate next service due hours."""
    return ((current_hours // interval) + 1) * interval


def build_operator_context(operators: list, fields: list) -> dict:
    """Build operator context variables for up to 2 operators.

    Args:
        operators: List of operator dicts with name, telegram, etc.
        fields: List of (field_suffix, dict_key, default) tuples.

    Returns:
        Dict with OPERATOR_1_*, OPERATOR_2_* keys.
    """
    context = {}
    for i in range(1, 3):
        operator = operators[i - 1] if i <= len(operators) else {}
        for suffix, key, default in fields:
            value = operator.get(key, default) if operator else default
            if key == 'telegram' and isinstance(value, str):
                value = value.lstrip('@')
            context[f'OPERATOR_{i}_{suffix}'] = value
    return context


def get_contact_field(coordinator: dict, escalation: dict, role: str, field: str, default: str) -> str:
    """Get contact field from coordinator or escalation config, with fallback."""
    value = coordinator.get(role, {}).get(field)
    if value is None:
        value = escalation.get(role, {}).get(field, default)
    if not value:
        return default
    if field == 'telegram' and isinstance(value, str):
        return value.lstrip('@')
    return value


def build_workspace_context(asset: dict, config: dict) -> dict:
    """Build common context for all workspace templates."""
    initial_date = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    coordinator = config['coordinator']
    escalation = config.get('escalation', {})

    operator_context = build_operator_context(
        asset.get('operators', []),
        [('NAME', 'name', ''), ('TG', 'telegram', ''), ('NOTES', 'notes', '')]
    )

    context = {
        'ASSET_ID': asset['asset_id'],
        'ASSET_TYPE': get_asset_display_name(asset['type']),
        'ASSET_EMOJI': get_asset_emoji(asset['type']),
        'ASSET_NICKNAME': asset.get('nickname', asset['asset_id']),
        'MAKE': asset.get('make', 'Unknown'),
        'MODEL': asset.get('model', 'Unknown'),

        'SITE_NAME': config['fleet'].get('site', 'Unknown Site'),
        'INITIAL_DATE': initial_date,
        'TODAY_DATE': today_date,
        'TELEGRAM_GROUP': asset.get('telegram_group', ''),
        'FC_TELEGRAM': coordinator.get('telegram_user', '').lstrip('@'),
        'FC_TELEGRAM_GROUP': coordinator.get('telegram_group', ''),
        'SUPERVISOR_NAME': escalation.get('supervisor', {}).get('name', 'Shift Supervisor'),
        'SUPERVISOR_TG': escalation.get('supervisor', {}).get('telegram', '').lstrip('@'),
        'SAFETY_NAME': get_contact_field(coordinator, escalation, 'safety', 'name', 'Safety Officer'),
        'SAFETY_TG': get_contact_field(coordinator, escalation, 'safety', 'telegram', ''),
        'OWNER_NAME': get_contact_field(coordinator, escalation, 'owner', 'name', 'Fleet Owner'),
        'OWNER_TG': get_contact_field(coordinator, escalation, 'owner', 'telegram', ''),
        'LANGUAGE': asset.get('language', 'English'),
        'TIMEZONE': asset.get('timezone', config['fleet'].get('timezone', 'UTC')),
        'SHIFT_START': coordinator.get('shift_start', '06:00'),
        'SHIFT_END': coordinator.get('shift_end', '18:00'),
        'REDIS_HOST': config.get('redis', {}).get('host', 'redis'),
        **operator_context,
    }

    return context


def build_fc_workspace_context(config: dict) -> dict:
    """Build context for Fleet Coordinator workspace templates.

    Uses coordinator.manager/safety/owner instead of operators.
    """
    initial_date = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    coordinator = config['coordinator']

    manager = coordinator.get('manager', {})
    safety = coordinator.get('safety', {})
    owner = coordinator.get('owner', {})

    return {
        'ASSET_ID': 'FLEET-COORD',
        'ASSET_TYPE': 'Fleet Coordinator',
        'ASSET_EMOJI': '📋',
        'ASSET_NICKNAME': 'Fleet Coordinator',
        'SITE_NAME': config['fleet'].get('site', 'Unknown Site'),
        'INITIAL_DATE': initial_date,
        'TODAY_DATE': today_date,
        'ASSET_COUNT': str(len(config['assets'])),
        'MANAGER_NAME': manager.get('name', 'Site Manager'),
        'MANAGER_TG': manager.get('telegram', '').lstrip('@'),
        'SAFETY_NAME': safety.get('name', 'Safety Officer'),
        'SAFETY_TG': safety.get('telegram', '').lstrip('@'),
        'OWNER_NAME': owner.get('name', 'Fleet Owner'),
        'OWNER_TG': owner.get('telegram', '').lstrip('@'),
        'TIMEZONE': config['fleet'].get('timezone', 'UTC'),
        'SHIFT_START': coordinator.get('shift_start', '06:00'),
        'SHIFT_END': coordinator.get('shift_end', '18:00'),
        'REDIS_HOST': config.get('redis', {}).get('host', 'redis'),
    }


def render_simple_template(template_path: Path, output_path: Path, context: dict) -> None:
    """Render a simple template by replacing {{KEY}} placeholders with context values."""
    if not template_path.exists():
        return
    content = template_path.read_text(encoding='utf-8')
    for key, value in context.items():
        content = content.replace('{{' + key + '}}', str(value))
    output_path.write_text(content, encoding='utf-8')


def render_soul_md(asset: dict, config: dict, templates_dir: Path) -> str:
    """Render SOUL.md for an asset."""
    env = SandboxedEnvironment(loader=FileSystemLoader(templates_dir / 'workspace'))

    template_name = get_asset_template(asset['type'])
    template = env.get_template(template_name)

    # Prepare context
    initial_date = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    initial_hours = asset.get('initial', {}).get('hours', 0)
    initial_km = asset.get('initial', {}).get('km', 0)

    context = {
        'ASSET_ID': asset['asset_id'],
        'ASSET_TYPE': get_asset_display_name(asset['type']),
        'MAKE': asset.get('make', 'Unknown'),
        'MODEL': asset.get('model', 'Unknown'),
        'SERIAL': asset.get('serial', 'Unknown'),
        'YEAR': asset.get('year', 'Unknown'),
        'SITE_NAME': config['fleet'].get('site', 'Unknown Site'),
        'INITIAL_DATE': initial_date,
        'INITIAL_HOURS': initial_hours,
        'INITIAL_KM': initial_km,
        'INITIAL_LAT': asset.get('initial', {}).get('lat', 0),
        'INITIAL_LON': asset.get('initial', {}).get('lon', 0),
        'TELEGRAM_GROUP': asset.get('telegram_group', ''),
        'FC_TELEGRAM': config['coordinator'].get('telegram_user', '').lstrip('@'),
        'SUPERVISOR_TG': config['escalation']['supervisor']['telegram'].lstrip('@'),
        'SAFETY_TG': config['escalation']['safety']['telegram'].lstrip('@'),
        'OWNER_TG': config['escalation']['owner']['telegram'].lstrip('@'),
        'ADDITIONAL_NOTES': '',
    }

    # Add specs - common to all asset types
    specs = asset.get('specs', {})
    context.update({
        'WEIGHT_TONS': specs.get('weight_tons', 0),
        'TANK_CAPACITY': specs.get('tank_capacity', 0),
        'AVG_CONSUMPTION': specs.get('avg_consumption', 0),
        'MIN_CONSUMPTION': specs.get('min_consumption', 0),
        'MAX_CONSUMPTION': specs.get('max_consumption', 0),
    })

    avg_consumption = context.get('AVG_CONSUMPTION', 0)
    operator_context = build_operator_context(
        asset.get('operators', []),
        [('NAME', 'name', ''), ('TG', 'telegram', ''), ('RATE', 'consumption_rate', avg_consumption)]
    )
    context.update(operator_context)

    # Maintenance intervals
    context.update({
        'NEXT_250_SERVICE': calculate_next_service(initial_hours, 250),
        'NEXT_500_SERVICE': calculate_next_service(initial_hours, 500),
        'NEXT_1000_SERVICE': calculate_next_service(initial_hours, 1000),
        'NEXT_2000_SERVICE': calculate_next_service(initial_hours, 2000),
        'NEXT_TIRE_INSPECTION': calculate_next_service(initial_hours, 50),
        'NEXT_COMPONENT_INSPECTION': calculate_next_service(initial_hours, 100),
    })

    return template.render(**context)


def render_fleet_coordinator_soul(config: dict, templates_dir: Path) -> str:
    """Render SOUL.md for Fleet Coordinator."""
    env = SandboxedEnvironment(loader=FileSystemLoader(templates_dir / 'workspace'))
    template = env.get_template('fleet-coordinator-soul.md')

    initial_date = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    assets_by_type = group_assets_by_type(config['assets'])

    def format_asset_list(asset_list):
        return '\n'.join(
            f"- **{a['asset_id']}** — {a.get('make', '')} {a.get('model', '')}, {a.get('telegram_group', '')}"
            for a in asset_list
        )

    # Build fleet composition sections
    fleet_sections = []
    for asset_type, type_assets in sorted(assets_by_type.items()):
        type_info = ASSET_TYPE_METADATA.get(asset_type, (asset_type.replace('_', ' ').title(), '\U0001F527', ''))
        fleet_sections.append({
            'name': type_info[0],
            'emoji': type_info[1],
            'count': len(type_assets),
            'list': format_asset_list(type_assets),
        })

    context = {
        'SITE_NAME': config['fleet'].get('site', 'Unknown Site'),
        'ASSET_COUNT': len(config['assets']),
        'FLEET_SECTIONS': fleet_sections,
        'INITIAL_DATE': initial_date,
        'FC_TELEGRAM': config['coordinator'].get('telegram_user', '').lstrip('@'),
        'MANAGER_NAME': config['coordinator'].get('manager', {}).get('name', ''),
        'MANAGER_TG': config['coordinator'].get('manager', {}).get('telegram', '').lstrip('@'),
        'SAFETY_NAME': config['coordinator'].get('safety', {}).get('name', ''),
        'SAFETY_TG': config['coordinator'].get('safety', {}).get('telegram', '').lstrip('@'),
        'OWNER_NAME': config['coordinator'].get('owner', {}).get('name', ''),
        'OWNER_TG': config['coordinator'].get('owner', {}).get('telegram', '').lstrip('@'),
        'SHIFT_START_TIME': config['coordinator'].get('shift_start', '06:00'),
        'SHIFT_END_TIME': config['coordinator'].get('shift_end', '18:00'),
        'ADDITIONAL_NOTES': '',
    }

    return template.render(**context)


FLEET_COORDINATOR_ASSET = {
    'asset_id': 'FLEET-COORD',
    'type': 'fleet_coordinator',
    'make': 'Fleetclaw',
    'model': 'Coordinator',
}


def render_docker_compose(host: dict, assets: list, config: dict, templates_dir: Path) -> str:
    """Render docker-compose.yml for a host."""
    env = SandboxedEnvironment(loader=FileSystemLoader(templates_dir))
    template = env.get_template('docker-compose.yml.j2')

    host_assets = [a for a in assets if a.get('host') == host['name']]

    if config['coordinator'].get('host') == host['name']:
        host_assets.append(FLEET_COORDINATOR_ASSET)

    return template.render(
        host=host,
        assets=host_assets,
        coordinator=config['coordinator'],
        default_model=DEFAULT_OPENCLAW_MODEL,
    )


def render_openclaw_json(asset: dict, config: dict, templates_dir: Path) -> str:
    """Render openclaw.json for an asset."""
    env = SandboxedEnvironment(loader=FileSystemLoader(templates_dir))
    template = env.get_template('openclaw.json.j2')

    # Get asset emoji for the identity section
    asset_emoji = get_asset_emoji(asset['type'])

    # Get supervisor ID for allowFrom (required for Telegram DM allowlist)
    supervisor_id = os.getenv('SUPERVISOR_ID', '')
    if supervisor_id and not supervisor_id.isdigit():
        print(f"  Warning: SUPERVISOR_ID '{supervisor_id}' is not a valid Telegram user ID (must be numeric)")
        supervisor_id = ''

    return template.render(asset=asset, asset_emoji=asset_emoji, supervisor_id=supervisor_id)


def create_daily_log(memory_dir: Path, asset_id: str, today_date: str, initial_date: str) -> None:
    """Create initial daily log file if it doesn't exist."""
    daily_log_path = memory_dir / f'{today_date}.md'
    if daily_log_path.exists():
        return

    content = f"""# {asset_id} Daily Log - {today_date}

> Append events as they happen. Format: HH:MM - Event description

## Events

(No events yet)

---
*Created: {initial_date}*
"""
    daily_log_path.write_text(content, encoding='utf-8')


def create_gitkeep(directory: Path) -> None:
    """Create .gitkeep file in directory to ensure it's tracked by git."""
    gitkeep = directory / '.gitkeep'
    if not gitkeep.exists():
        gitkeep.touch()


def setup_workspace_directories(workspace_dir: Path) -> Path:
    """Create workspace directory structure and return memory directory path."""
    workspace_dir.mkdir(parents=True, exist_ok=True)
    memory_dir = workspace_dir / 'memory'
    memory_dir.mkdir(exist_ok=True)
    create_gitkeep(memory_dir)

    logs_dir = workspace_dir / 'logs'
    logs_dir.mkdir(exist_ok=True)
    create_gitkeep(logs_dir)

    buffer_dir = workspace_dir / 'buffer'
    buffer_dir.mkdir(exist_ok=True)
    create_gitkeep(buffer_dir)

    # Create hooks directories
    hooks_dir = workspace_dir / 'hooks'
    hooks_dir.mkdir(exist_ok=True)
    for hook in HOOKS:
        (hooks_dir / hook).mkdir(exist_ok=True)
    return memory_dir


def render_workspace_templates(
    templates_dir: Path, workspace_dir: Path, context: dict, subdir: str = 'workspace'
) -> None:
    """Render all workspace template files.

    Args:
        templates_dir: Root templates directory
        workspace_dir: Target workspace directory
        context: Template variable context
        subdir: Template subdirectory ('workspace' for assets, 'coordinator' for FC)
    """
    for template_name, output_name in WORKSPACE_TEMPLATES:
        render_simple_template(
            templates_dir / subdir / template_name,
            workspace_dir / output_name,
            context
        )


def copy_hooks(hooks_src_dir: Path, workspace_dir: Path, context: dict, asset_type: str) -> None:
    """Copy hook definitions to workspace, rendering any template variables.

    Skips fuel-log-received hook for fleet coordinator since it doesn't process fuel logs.
    """
    hooks_dest_dir = workspace_dir / 'hooks'
    for hook in HOOKS:
        if hook == 'fuel-log-received' and asset_type == 'fleet_coordinator':
            continue
        src_file = hooks_src_dir / hook / 'HOOK.md'
        dest_file = hooks_dest_dir / hook / 'HOOK.md'
        if src_file.exists():
            render_simple_template(src_file, dest_file, context)


def generate_fleet_coordinator_workspace(
    config: dict,
    templates_dir: Path,
    workspaces_dir: Path,
    config_dir: Path,
    hooks_src_dir: Path,
    today_date: str,
) -> None:
    """Generate workspace for Fleet Coordinator.

    Uses FC-specific templates from templates/coordinator/ and
    coordinator-specific context builder.
    """
    fc_workspace = workspaces_dir / 'FLEET-COORD'
    fc_memory_dir = setup_workspace_directories(fc_workspace)

    fc_context = build_fc_workspace_context(config)

    fc_soul = render_fleet_coordinator_soul(config, templates_dir)
    (fc_workspace / 'SOUL.md').write_text(fc_soul, encoding='utf-8')

    render_workspace_templates(templates_dir, fc_workspace, fc_context, subdir='coordinator')
    copy_hooks(hooks_src_dir, fc_workspace, fc_context, 'fleet_coordinator')
    create_daily_log(fc_memory_dir, 'FLEET-COORD', today_date, fc_context['INITIAL_DATE'])

    fc_openclaw = render_openclaw_json(FLEET_COORDINATOR_ASSET, config, templates_dir)
    (config_dir / 'openclaw-fleet-coord.json').write_text(fc_openclaw, encoding='utf-8')


def set_ownership_for_container(path: Path) -> None:
    """Set ownership to uid 1000 for OpenClaw container compatibility.

    OpenClaw containers run as the 'node' user (uid 1000). On non-Windows systems
    with appropriate permissions, this sets file ownership accordingly.
    """
    if platform.system() == 'Windows':
        return

    try:
        for root, dirs, files in os.walk(path):
            root_path = Path(root)
            os.chown(root_path, 1000, 1000)
            for filename in files:
                os.chown(root_path / filename, 1000, 1000)
    except PermissionError:
        pass


def check_compose_permissions(compose_dir: Path) -> list[Path]:
    """Check for permission issues in compose directory.

    On Linux/macOS, detects files owned by uid 1000 that current user
    cannot write to. Skipped on Windows.

    Args:
        compose_dir: Path to the compose directory

    Returns:
        List of paths with permission issues
    """
    if platform.system() == 'Windows':
        return []

    if not compose_dir.exists():
        return []

    problem_paths = []

    for subdir in ['workspaces', 'data', 'skills']:
        subdir_path = compose_dir / subdir
        if not subdir_path.exists():
            continue

        try:
            stat_info = subdir_path.stat()
            if stat_info.st_uid == 1000 and not os.access(subdir_path, os.W_OK):
                problem_paths.append(subdir_path)
                continue
        except OSError:
            continue

        # Sample first 3 children
        for child in list(subdir_path.iterdir())[:3]:
            try:
                stat_info = child.stat()
                if stat_info.st_uid == 1000 and not os.access(child, os.W_OK):
                    problem_paths.append(child)
            except OSError:
                continue

    return problem_paths


def warn_permission_issues(compose_dir: Path, problem_paths: list[Path]) -> None:
    """Print warning about permission issues.

    Args:
        compose_dir: Path to the compose directory
        problem_paths: List of paths with permission issues
    """
    print(f"\nWarning: Permission issues detected in {compose_dir}/")
    print("  Files owned by uid 1000 (container user) cannot be overwritten.")
    print()
    print("  Affected paths:")
    for path in problem_paths[:3]:
        print(f"    - {path}")
    if len(problem_paths) > 3:
        print(f"    ... and {len(problem_paths) - 3} more")
    print()
    print("  To fix, run:")
    print(f"    sudo chown -R $(id -u):$(id -g) {compose_dir}")
    print()
    print("  Or use --skip-copy to only regenerate source workspaces.")
    print("  Or use --no-permission-check to suppress this warning.")
    print()


def copy_directory_to_compose(src: Path, dest: Path) -> None:
    """Copy a directory to compose location, replacing if it exists.

    Args:
        src: Source directory path
        dest: Destination directory path
    """
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    set_ownership_for_container(dest)


def copy_to_compose_dir(workspaces_dir: Path, compose_dir: Path, asset_id: str) -> None:
    """Copy workspace to compose directory for Docker mounting.

    Args:
        workspaces_dir: Source workspaces directory (generated/workspaces/)
        compose_dir: Target compose directory (generated/compose/)
        asset_id: Asset ID to copy workspace for
    """
    src_workspace = workspaces_dir / asset_id
    dest_workspace = compose_dir / 'workspaces' / asset_id
    copy_directory_to_compose(src_workspace, dest_workspace)


def copy_skills_to_compose_dir(skills_src_dir: Path, compose_dir: Path) -> None:
    """Copy skills directory to compose directory for Docker mounting.

    Args:
        skills_src_dir: Source skills directory (skills/)
        compose_dir: Target compose directory (generated/compose/)
    """
    dest_skills = compose_dir / 'skills'
    copy_directory_to_compose(skills_src_dir, dest_skills)


def copy_dockerfile_to_compose(repo_root: Path, compose_dir: Path) -> None:
    """Copy custom OpenClaw Dockerfile to compose directory for Docker build.

    Args:
        repo_root: Repository root directory
        compose_dir: Target compose directory (generated/compose/)
    """
    src = repo_root / 'docker' / 'openclaw'
    dest = compose_dir / 'docker' / 'openclaw'
    if not src.exists():
        return
    copy_directory_to_compose(src, dest)


def copy_asset_to_compose(
    asset_id: str,
    workspaces_dir: Path,
    config_dir: Path,
    compose_dir: Path,
) -> None:
    """Copy workspace and openclaw config for an asset to compose directory.

    Args:
        asset_id: Asset ID (e.g., 'EX-001' or 'FLEET-COORD')
        workspaces_dir: Source workspaces directory
        config_dir: Source config directory
        compose_dir: Target compose directory
    """
    copy_to_compose_dir(workspaces_dir, compose_dir, asset_id)

    # Create data directory for this asset (writable .openclaw mount)
    data_dir = compose_dir / 'data' / asset_id
    data_dir.mkdir(parents=True, exist_ok=True)

    # Copy config into data directory as openclaw.json
    config_filename = f"openclaw-{asset_id.lower()}.json"
    src_config = config_dir / config_filename
    dest_config = data_dir / 'openclaw.json'
    shutil.copy2(src_config, dest_config)

    # Set ownership for container
    set_ownership_for_container(data_dir)


def generate_env_template(config: dict, output_path: Path | None, dry_run: bool = False) -> None:
    """Generate .env.template with tokens for all assets in fleet.yaml.

    Args:
        config: Fleet configuration dictionary
        output_path: Path to write .env.template (None allowed if dry_run=True)
        dry_run: If True, print preview instead of writing file
    """
    assets_by_type = group_assets_by_type(config['assets'])

    # Pre-compute sorted asset groups (used for both template generation and dry-run output)
    sorted_groups = []
    for asset_type in sorted(assets_by_type.keys()):
        type_assets = assets_by_type[asset_type]
        sorted_assets = sorted(type_assets, key=lambda a: a['asset_id'])
        display_name = get_asset_display_name(asset_type)
        count = len(sorted_assets)
        plural = 's' if count != 1 else ''
        sorted_groups.append((display_name, plural, count, sorted_assets))

    if dry_run:
        print("\nWould generate .env.template:")
        print("  - FLEET-COORD")
        for display_name, plural, count, sorted_assets in sorted_groups:
            ids = ', '.join(a['asset_id'] for a in sorted_assets)
            print(f"  - {display_name}{plural} ({count}): {ids}")
        total = len(config['assets']) + 1  # +1 for FLEET-COORD
        print(f"  Total: {total} Telegram token placeholders")
        return

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    lines = [
        "# Fleetclaw Environment Configuration",
        f"# Auto-generated from fleet.yaml on {timestamp}",
        "# Regenerate with: python scripts/generate-configs.py",
        "#",
        "# Instructions:",
        "#   1. Copy this file to .env in the same directory",
        "#   2. Fill in actual values for each placeholder",
        "#   3. Keep .env out of version control",
        "",
        "# =============================================================================",
        "# CORE API KEYS",
        "# =============================================================================",
        "",
        "# Fireworks AI API Key (get from https://fireworks.ai/account/api-keys)",
        "FIREWORKS_API_KEY=your_fireworks_api_key",
        "",
        "# OpenClaw Gateway Token (Required for v2026.1.29+)",
        "# Generate: openssl rand -hex 32",
        "OPENCLAW_GATEWAY_TOKEN=generate_secure_token_here",
        "",
        "# =============================================================================",
        "# REDIS CONFIGURATION",
        "# =============================================================================",
        "",
        "REDIS_URL=redis://redis:6379",
        "",
        "# =============================================================================",
        "# TELEGRAM BOT TOKENS",
        "# =============================================================================",
        "# Each asset has its own bot token for failure isolation.",
        "# Create bots via @BotFather on Telegram.",
        "",
        "# Fleet Coordinator",
        "TELEGRAM_TOKEN_FLEET_COORD=",
        "",
    ]

    # Asset tokens grouped by type
    for display_name, plural, count, sorted_assets in sorted_groups:
        lines.append(f"# {display_name}{plural} ({count})")
        for asset in sorted_assets:
            env_key = asset_id_to_env_key(asset['asset_id'])
            lines.append(f"TELEGRAM_TOKEN_{env_key}=")
        lines.append("")

    # Remaining sections
    lines.extend([
        "# =============================================================================",
        "# ESCALATION CONTACTS (Telegram User IDs)",
        "# =============================================================================",
        "# Note: SUPERVISOR_ID must be set before running generate-configs.py",
        "# It is baked into openclaw.json at generation time for Telegram DM allowlist",
        "",
        "SUPERVISOR_ID=",
        "SAFETY_ID=",
        "OWNER_ID=",
        "",
        "# =============================================================================",
        "# SITE CONFIGURATION",
        "# =============================================================================",
        "",
        "# Site name is configured in fleet.yaml (requires regeneration to update)",
        f'TIMEZONE={config["fleet"].get("timezone", "UTC")}',
        f'SHIFT_START={config["coordinator"].get("shift_start", "06:00")}',
        f'SHIFT_END={config["coordinator"].get("shift_end", "18:00")}',
        "",
        "# =============================================================================",
        "# OPENCLAW CONFIGURATION",
        "# =============================================================================",
        "",
        f"OPENCLAW_MODEL={DEFAULT_OPENCLAW_MODEL}",
        "LOG_LEVEL=info",
        "LOG_FORMAT=json",
        "",
    ])

    output_path.write_text('\n'.join(lines), encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description='Generate Fleetclaw configurations')
    parser.add_argument('--fleet-file', default='config/fleet.yaml',
                        help='Path to fleet.yaml configuration')
    parser.add_argument('--output-dir', default='./generated',
                        help='Output directory for generated files')
    parser.add_argument('--templates-dir', default='./templates',
                        help='Directory containing Jinja2 templates')
    parser.add_argument('--skip-validation', action='store_true',
                        help='Skip Pydantic configuration validation')
    parser.add_argument('--git-init', action='store_true',
                        help='Initialize git repositories in workspaces for state persistence')
    parser.add_argument('--target-asset',
                        help='Regenerate only this asset (e.g., EX-001 or FLEET-COORD)')
    parser.add_argument('--target-host',
                        help='Regenerate only assets on this host (e.g., host-02)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be generated without writing files')
    parser.add_argument('--skip-copy', action='store_true',
                        help='Skip copying workspaces/skills to compose directory')
    parser.add_argument('--no-permission-check', action='store_true',
                        help='Skip pre-flight permission check (for CI environments)')
    args = parser.parse_args()

    # Resolve paths
    script_dir = Path(__file__).parent.parent
    fleet_file = script_dir / args.fleet_file
    output_dir = Path(args.output_dir)
    templates_dir = script_dir / args.templates_dir

    # Check fleet file exists
    if not fleet_file.exists():
        # Try example file
        example_file = fleet_file.with_suffix('.yaml.example')
        if example_file.exists():
            print(f"Note: Using {example_file} as fleet configuration")
            fleet_file = example_file
        else:
            print(f"Error: Fleet configuration not found: {fleet_file}")
            print("Copy config/fleet.yaml.example to config/fleet.yaml and customize")
            sys.exit(1)

    # Load configuration
    print(f"Loading configuration from {fleet_file}")
    config = load_fleet_config(fleet_file, skip_validation=args.skip_validation)

    # Filter assets/hosts if targets specified
    assets_to_process = config['assets']
    hosts_to_process = config['hosts']
    generate_fleet_coord = True

    if args.target_asset:
        if args.target_asset == 'FLEET-COORD':
            assets_to_process = []
            generate_fleet_coord = True
        else:
            assets_to_process = [a for a in config['assets']
                                if a['asset_id'] == args.target_asset]
            generate_fleet_coord = False
            if not assets_to_process:
                print(f"Error: Asset '{args.target_asset}' not found in fleet.yaml")
                print(f"Available assets: {[a['asset_id'] for a in config['assets']]}")
                sys.exit(1)
        print(f"Partial update: targeting asset {args.target_asset}")

    if args.target_host:
        hosts_to_process = [h for h in config['hosts']
                            if h['name'] == args.target_host]
        if not hosts_to_process:
            print(f"Error: Host '{args.target_host}' not found in fleet.yaml")
            print(f"Available hosts: {[h['name'] for h in config['hosts']]}")
            sys.exit(1)
        # Also filter assets to only those on this host
        if not args.target_asset:
            assets_to_process = [a for a in config['assets']
                                if a.get('host') == args.target_host]
            generate_fleet_coord = (config['coordinator'].get('host') == args.target_host)
        print(f"Partial update: targeting host {args.target_host}")

    if args.dry_run:
        print("\n=== DRY RUN - No files will be written ===")
        print(f"Assets to process: {[a['asset_id'] for a in assets_to_process]}")
        print(f"Hosts to process: {[h['name'] for h in hosts_to_process]}")
        print(f"Generate Fleet Coordinator: {generate_fleet_coord}")
        if not args.target_asset and not args.target_host:
            generate_env_template(config, None, dry_run=True)
        sys.exit(0)

    # Pre-flight permission check
    compose_dir = output_dir / 'compose'
    if not args.skip_copy and not args.no_permission_check:
        problem_paths = check_compose_permissions(compose_dir)
        if problem_paths:
            warn_permission_issues(compose_dir, problem_paths)

    # Create output directories
    output_dir.mkdir(parents=True, exist_ok=True)
    workspaces_dir = output_dir / 'workspaces'
    config_dir = output_dir / 'config'

    for d in [workspaces_dir, compose_dir, config_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Load .env file as fallback for environment variables
    env_file = compose_dir / '.env'
    if env_file.exists():
        for key, value in load_env_file(env_file).items():
            os.environ.setdefault(key, value)

    # Generate per-asset workspaces
    print("\nGenerating asset workspaces...")
    if not os.getenv('SUPERVISOR_ID'):
        print("  Warning: SUPERVISOR_ID not set - Telegram DM allowlist will be empty")
        print("           Set in environment or in generated/compose/.env")
    today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    hooks_src_dir = script_dir / 'hooks'

    for asset in assets_to_process:
        asset_id = asset['asset_id']
        workspace_dir = workspaces_dir / asset_id
        memory_dir = setup_workspace_directories(workspace_dir)
        workspace_context = build_workspace_context(asset, config)

        soul_content = render_soul_md(asset, config, templates_dir)
        (workspace_dir / 'SOUL.md').write_text(soul_content, encoding='utf-8')

        render_workspace_templates(templates_dir, workspace_dir, workspace_context)
        copy_hooks(hooks_src_dir, workspace_dir, workspace_context, asset['type'])
        create_daily_log(memory_dir, asset_id, today_date, workspace_context['INITIAL_DATE'])

        openclaw_json = render_openclaw_json(asset, config, templates_dir)
        (config_dir / f'openclaw-{asset_id.lower()}.json').write_text(openclaw_json, encoding='utf-8')

        print(f"  Created workspace for {asset_id}")

    # Generate Fleet Coordinator workspace
    if generate_fleet_coord:
        generate_fleet_coordinator_workspace(
            config, templates_dir, workspaces_dir, config_dir, hooks_src_dir, today_date
        )
        print("  Created workspace for FLEET-COORD")

    # Initialize git repositories for state persistence
    if args.git_init:
        print("\nInitializing git repositories for state persistence...")
        try:
            from soul_keeper import is_git_repo, run_git
            for workspace in workspaces_dir.iterdir():
                if workspace.is_dir() and not is_git_repo(workspace):
                    run_git(workspace, 'init')
                    run_git(workspace, 'add', '.')
                    run_git(workspace, 'commit', '-m', 'Initial workspace state')
                    print(f"  Initialized git repo in {workspace.name}")
        except ImportError:
            print("  Warning: soul_keeper module not found, skipping git init")
        except Exception as e:
            print(f"  Warning: git init failed: {e}")

    # Copy workspaces to compose directory for Docker mounting
    if not args.skip_copy:
        print("\nCopying workspaces to compose directory...")
        skills_src_dir = script_dir / 'skills'

        # Create compose subdirectories
        (compose_dir / 'workspaces').mkdir(parents=True, exist_ok=True)
        (compose_dir / 'data').mkdir(parents=True, exist_ok=True)

        for asset in assets_to_process:
            copy_asset_to_compose(asset['asset_id'], workspaces_dir, config_dir, compose_dir)
            print(f"  Copied workspace for {asset['asset_id']}")

        if generate_fleet_coord:
            copy_asset_to_compose('FLEET-COORD', workspaces_dir, config_dir, compose_dir)
            print("  Copied workspace for FLEET-COORD")

        # Copy skills directory to compose directory
        print("\nCopying skills to compose directory...")
        copy_skills_to_compose_dir(skills_src_dir, compose_dir)
        print("  Copied skills directory")

        # Copy Dockerfile for custom OpenClaw image
        print("\nCopying Dockerfile to compose directory...")
        copy_dockerfile_to_compose(script_dir, compose_dir)
        print("  Copied OpenClaw Dockerfile")

        # Check if chown is needed (non-Windows, non-root)
        if platform.system() != 'Windows':
            try:
                # Test if we can chown (requires root)
                test_file = compose_dir / '.chown_test'
                test_file.touch()
                os.chown(test_file, 1000, 1000)
                test_file.unlink()
            except (PermissionError, OSError):
                print("\n  Note: Run the following to set ownership for container:")
                print(f"    sudo chown -R 1000:1000 {compose_dir / 'workspaces'}")
                print(f"    sudo chown -R 1000:1000 {compose_dir / 'data'}")
                print(f"    sudo chown -R 1000:1000 {compose_dir / 'skills'}")
    else:
        print("\nSkipping copy to compose directory (--skip-copy)")

    # Generate per-host docker-compose files
    print("\nGenerating docker-compose files...")
    for host in hosts_to_process:
        # Use all assets when doing full generation, filtered assets for partial
        host_assets = config['assets'] if not (args.target_asset or args.target_host) else assets_to_process
        compose_content = render_docker_compose(host, host_assets, config, templates_dir)
        compose_file = compose_dir / f"docker-compose-{host['name']}.yml"
        compose_file.write_text(compose_content, encoding='utf-8')
        print(f"  Created {compose_file.name}")

    # Generate Redis initialization script for group mapping
    redis_init_file = config_dir / 'redis-init.sh'
    redis_commands = ["#!/bin/bash", "# Redis initialization for Fleetclaw group mapping", "# Run with: bash generated/config/redis-init.sh", ""]

    for asset in config['assets']:
        telegram_group = asset.get('telegram_group', '')
        if telegram_group:
            # Note: Real group IDs would be numeric, this is placeholder
            redis_commands.append(f"# {asset['asset_id']}: {telegram_group}")
            redis_commands.append(f"# redis-cli HSET 'fleet:group_map:<group_id>' asset_id '{asset['asset_id']}' type 'agent' status 'active'")

    # Add tracked assets if present
    tracked = config.get('tracked_assets', [])
    if tracked:
        redis_commands.append("")
        redis_commands.append("# Tracked assets (no agent)")
        for asset in tracked:
            redis_commands.append(f"# redis-cli HSET 'fleet:group_map:<group_id>' asset_id '{asset['asset_id']}' type 'tracked'")

    redis_commands.append("")
    redis_commands.append("# Fleet Coordinator")
    redis_commands.append("# redis-cli HSET 'fleet:group_map:<fc_group_id>' asset_id 'FLEET-COORD' type 'coordinator'")

    redis_init_file.write_text('\n'.join(redis_commands), encoding='utf-8')
    print(f"  Created Redis init script: {redis_init_file.name}")

    # Generate .env.template (only for full generation, not partial)
    if not args.target_asset and not args.target_host:
        env_template_path = compose_dir / '.env.template'
        generate_env_template(config, env_template_path)
        print(f"  Created {env_template_path.name}")

    # Summary
    tracked_count = len(config.get('tracked_assets', []))
    print(f"\n{'='*60}")
    print("Generation complete!")
    print(f"{'='*60}")
    print(f"  Assets with agents: {len(config['assets'])}")
    print(f"  Tracked assets (no agent): {tracked_count}")
    print(f"  Hosts configured: {len(config['hosts'])}")
    print(f"  Output directory: {output_dir}")
    print("\nNext steps:")
    print("  1. Copy .env.template to .env and fill in values")
    print("  2. Review generated configs in generated/")
    print("  3. Deploy with: docker compose -f generated/compose/docker-compose-<host>.yml up -d")
    print("  4. Initialize Redis group mapping with real Telegram group IDs")


if __name__ == '__main__':
    main()
