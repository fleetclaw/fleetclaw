#!/usr/bin/env python3
"""
Auto-onboard new assets to fleet.yaml with validation.
Usage: python scripts/auto_onboard.py --json '{...}'
"""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError
from ruamel.yaml import YAML, YAMLError

from models import AssetConfig

SCRIPT_DIR = Path(__file__).parent
DEFAULT_FLEET_FILE = SCRIPT_DIR.parent / 'config' / 'fleet.yaml'


def load_fleet_yaml(fleet_path: Path) -> tuple[dict, YAML]:
    """Load fleet.yaml preserving comments."""
    yaml_parser = YAML()
    yaml_parser.preserve_quotes = True
    yaml_parser.indent(mapping=2, sequence=4, offset=2)

    content = fleet_path.read_text(encoding='utf-8')
    config = yaml_parser.load(content)
    return config, yaml_parser


def save_fleet_yaml(fleet_path: Path, config: dict, yaml_parser: YAML) -> None:
    """Save fleet.yaml atomically."""
    tmp_path = fleet_path.with_suffix('.yaml.tmp')
    with tmp_path.open('w', encoding='utf-8') as f:
        yaml_parser.dump(config, f)
    tmp_path.replace(fleet_path)


def compute_consumption_defaults(specs: dict) -> dict:
    """Add min/max consumption if avg provided."""
    if 'avg_consumption' in specs and specs['avg_consumption'] > 0:
        avg = specs['avg_consumption']
        specs.setdefault('min_consumption', max(0, avg - 5))
        specs.setdefault('max_consumption', avg + 10)
    return specs


def validate_and_prepare(asset_data: dict, config: dict) -> AssetConfig:
    """Validate asset data and check fleet constraints."""
    # Compute consumption defaults
    if 'specs' in asset_data:
        asset_data['specs'] = compute_consumption_defaults(asset_data['specs'])

    # Set initial state defaults
    if 'initial' not in asset_data:
        asset_data['initial'] = {'hours': 0, 'lat': 0, 'lon': 0}

    # Pydantic validation
    validated = AssetConfig.model_validate(asset_data)

    # Check for duplicate asset_id
    existing_ids = {a['asset_id'] for a in config.get('assets', [])}
    if validated.asset_id in existing_ids:
        raise ValueError(f"Asset ID '{validated.asset_id}' already exists")

    # Check host exists
    host_names = {h['name'] for h in config.get('hosts', [])}
    if validated.host not in host_names:
        raise ValueError(f"Host '{validated.host}' not found. Available: {sorted(host_names)}")

    return validated


def add_asset_to_host(config: dict, asset_id: str, host_name: str) -> None:
    """Add asset_id to the host's assets list."""
    for host in config.get('hosts', []):
        if host['name'] == host_name:
            if 'assets' not in host:
                host['assets'] = []
            if asset_id not in host['assets']:
                host['assets'].append(asset_id)
            break


def onboard_asset(asset_data: dict, fleet_path: Path, dry_run: bool = False) -> dict:
    """Add new asset to fleet.yaml with rollback on error."""
    backup_path = fleet_path.with_suffix('.yaml.bak')

    try:
        config, yaml_parser = load_fleet_yaml(fleet_path)
        validated = validate_and_prepare(asset_data, config)

        # Convert to dict for YAML insertion
        asset_dict = validated.model_dump(exclude_none=True, exclude_unset=False)

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "asset_id": validated.asset_id,
                "would_add": asset_dict
            }

        # Create backup before modifying
        if fleet_path.exists():
            backup_content = fleet_path.read_bytes()
            backup_path.write_bytes(backup_content)

        # Add to assets list
        if 'assets' not in config:
            config['assets'] = []
        config['assets'].append(asset_dict)

        # Add to host's assets array
        add_asset_to_host(config, validated.asset_id, validated.host)

        # Save atomically
        save_fleet_yaml(fleet_path, config, yaml_parser)

        # Clean up backup on success
        if backup_path.exists():
            backup_path.unlink()

        return {
            "success": True,
            "asset_id": validated.asset_id,
            "host": validated.host,
            "message": f"Asset {validated.asset_id} added to fleet.yaml",
            "next_steps": [
                f"Add TELEGRAM_TOKEN_{validated.asset_id.replace('-', '_')} to .env",
                "Run: python scripts/generate-configs.py",
                "Deploy the new container"
            ]
        }

    except (ValueError, ValidationError, FileNotFoundError, YAMLError, OSError) as e:
        # Restore backup on error if it exists
        if backup_path.exists():
            backup_content = backup_path.read_bytes()
            fleet_path.write_bytes(backup_content)
            backup_path.unlink()
        return {"success": False, "error": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated Asset Onboarding")
    parser.add_argument('--json', required=True, help='JSON string of asset configuration')
    parser.add_argument('--fleet-file', type=Path, default=DEFAULT_FLEET_FILE)
    parser.add_argument('--dry-run', action='store_true', help='Validate without saving')

    args = parser.parse_args()

    try:
        asset_data = json.loads(args.json)
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    result = onboard_asset(asset_data, args.fleet_file, args.dry_run)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['success'] else 1)


if __name__ == "__main__":
    main()
