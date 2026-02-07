#!/usr/bin/env python3
"""
Bulk import assets from CSV to fleet.yaml.

Usage:
    # Dry-run validation
    python scripts/csv_import.py --csv assets.csv --host my-host --dry-run

    # Actual import (add to existing host)
    python scripts/csv_import.py --csv assets.csv --host existing-host

    # Create new host without Redis
    python scripts/csv_import.py --csv assets.csv --host new-host --create-host

    # Create new host with Redis enabled
    python scripts/csv_import.py --csv assets.csv --host new-host --create-host --redis
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from pydantic import ValidationError
from ruamel.yaml import YAML, YAMLError

from models import ASSET_TYPE_METADATA, AssetConfig

SCRIPT_DIR = Path(__file__).parent
DEFAULT_FLEET_FILE = SCRIPT_DIR.parent / 'config' / 'fleet.yaml'

# Regex for normalizing category names to snake_case
NORMALIZE_PATTERN = re.compile(r'[.\s-]+')
UNDERSCORE_COLLAPSE_PATTERN = re.compile(r'_+')

# Manual aliases for edge cases (abbreviations, inconsistencies in CSV data)
# Only needed when normalized form doesn't match ASSET_TYPE_METADATA keys
CATEGORY_ALIASES = {
    'motorgrader': 'motor_grader',
    'rigid_frame_haul_trk': 'rigid_haul_truck',
}


def normalize_category(name: str) -> str:
    """Normalize category name to snake_case for type matching.

    Examples:
        'Artic. Dump Truck' -> 'artic_dump_truck'
        'DTH Surface Drill' -> 'dth_surface_drill'
        'Wheel Loader' -> 'wheel_loader'
    """
    name = name.lower()
    name = NORMALIZE_PATTERN.sub('_', name)  # Replace . space - with _
    name = UNDERSCORE_COLLAPSE_PATTERN.sub('_', name)  # Collapse multiple underscores
    return name.strip('_')


def resolve_asset_type(category: str) -> str | None:
    """Resolve CSV category to asset type key.

    First checks manual aliases for edge cases, then tries direct match
    against ASSET_TYPE_METADATA keys after normalization.

    Args:
        category: Raw category string from CSV

    Returns:
        Matched asset type key, or None if no match found
    """
    normalized = normalize_category(category)

    # Check alias first (handles abbreviations like 'trk' -> 'truck')
    if normalized in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[normalized]

    # Direct match against ASSET_TYPE_METADATA keys
    if normalized in ASSET_TYPE_METADATA:
        return normalized

    return None


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


def parse_csv(csv_path: Path) -> list[dict]:
    """Parse CSV file with BOM handling."""
    content = csv_path.read_text(encoding='utf-8-sig')
    reader = csv.DictReader(content.splitlines())
    return list(reader)


def map_csv_row_to_asset(row: dict, host: str, asset_type: str | None = None) -> dict:
    """
    Convert CSV row to asset dict suitable for fleet.yaml.

    Args:
        row: CSV row dict with asset data
        host: Host name to assign this asset to
        asset_type: Pre-resolved asset type (if None, resolves from category)

    Returns:
        Asset dict ready for fleet.yaml assets section.

    Raises:
        ValueError: If category cannot be resolved to an asset type
    """
    if asset_type is None:
        category = row['category']
        asset_type = resolve_asset_type(category)
        if not asset_type:
            available = sorted(ASSET_TYPE_METADATA.keys())
            raise ValueError(
                f"Unknown category '{category}' (normalized: '{normalize_category(category)}'). "
                f"Add to CATEGORY_ALIASES or check available types: {available[:10]}..."
            )

    asset_data = {
        'asset_id': row['asset_id'],
        'type': asset_type,
        'make': row['make'],
        'model': str(row['model']),  # Ensure model is string
        'host': host,
        'serial': row.get('serial_number', ''),
        'specs': {},
        'initial': {'hours': 0},
        'telegram_group': f"@{row['asset_id'].lower()}_ops",
    }

    # Add year if present
    if row.get('year'):
        asset_data['year'] = int(row['year'])

    return asset_data


def validate_assets(assets: list[dict], config: dict, host: str) -> list[str]:
    """
    Validate all assets before import.

    Returns list of error messages (empty if all valid).
    """
    errors = []

    # Check for host existence
    host_names = {h['name'] for h in config.get('hosts', [])}
    if host not in host_names:
        errors.append(f"Host '{host}' not found. Available: {sorted(host_names)}")

    # Collect existing IDs
    existing_ids = {a['asset_id'] for a in config.get('assets', [])}
    new_ids: set[str] = set()

    for asset_data in assets:
        asset_id = asset_data['asset_id']

        if asset_id in new_ids:
            errors.append(f"Duplicate asset_id in CSV: {asset_id}")
        new_ids.add(asset_id)

        if asset_id in existing_ids:
            errors.append(f"Asset ID '{asset_id}' already exists in fleet.yaml")

        try:
            AssetConfig.model_validate(asset_data)
        except ValidationError as e:
            errors.append(f"Validation error for {asset_id}: {e}")

    return errors


def create_host(config: dict, host_name: str, redis: bool = False) -> None:
    """Add a new host to the config.

    Args:
        config: Fleet configuration dict
        host_name: Name for the new host
        redis: Whether this host should run Redis
    """
    if 'hosts' not in config:
        config['hosts'] = []

    # Check if host already exists
    for host in config['hosts']:
        if host['name'] == host_name:
            # Update redis setting if host exists
            if redis:
                host['redis'] = True
            return

    # Add new host with FLEET-COORD included
    config['hosts'].append({
        'name': host_name,
        'assets': ['FLEET-COORD'],
        'redis': redis
    })


def add_assets_to_host(config: dict, asset_ids: list[str], host_name: str) -> None:
    """Add asset IDs to the host's assets list."""
    for host in config.get('hosts', []):
        if host['name'] != host_name:
            continue
        host.setdefault('assets', [])
        existing = set(host['assets'])
        host['assets'].extend(aid for aid in asset_ids if aid not in existing)
        return


def import_csv(
    csv_path: Path,
    fleet_path: Path,
    host: str,
    create_host_flag: bool = False,
    redis: bool = False,
    dry_run: bool = False
) -> dict:
    """
    Import assets from CSV to fleet.yaml.

    Args:
        csv_path: Path to CSV file
        fleet_path: Path to fleet.yaml
        host: Host name to assign assets to
        create_host_flag: Create host if it doesn't exist
        redis: Enable Redis on created host (requires --create-host)
        dry_run: Validate without saving

    Returns result dict with success/error info.
    """
    backup_path = fleet_path.with_suffix('.yaml.bak')

    try:
        # Parse CSV
        rows = parse_csv(csv_path)
        if not rows:
            return {"success": False, "error": "CSV file is empty"}

        # Load config
        config, yaml_parser = load_fleet_yaml(fleet_path)

        # Create host if requested
        if create_host_flag:
            create_host(config, host, redis=redis)

        # Map rows to assets, collecting unmapped categories
        assets = []
        unmapped_categories = set()

        for row in rows:
            category = row['category']
            asset_type = resolve_asset_type(category)
            if not asset_type:
                unmapped_categories.add(category)
                continue

            asset_data = map_csv_row_to_asset(row, host, asset_type)
            assets.append(asset_data)

        if unmapped_categories:
            available = sorted(ASSET_TYPE_METADATA.keys())
            normalized_unmapped = {f"'{c}' -> '{normalize_category(c)}'" for c in unmapped_categories}
            return {
                "success": False,
                "error": f"Unknown categories (add to CATEGORY_ALIASES): {sorted(normalized_unmapped)}. "
                         f"Available types: {available[:15]}..."
            }

        # Validate all assets
        errors = validate_assets(assets, config, host)
        if errors:
            return {"success": False, "errors": errors}

        # Summary for dry-run
        summary = {
            "total_rows": len(rows),
            "assets": len(assets),
            "host": host
        }

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "summary": summary,
                "asset_ids": [a['asset_id'] for a in assets],
            }

        # Create backup before modifying
        if fleet_path.exists():
            backup_content = fleet_path.read_bytes()
            backup_path.write_bytes(backup_content)

        # Add assets to config
        config.setdefault('assets', []).extend(assets)

        # Add asset IDs to host
        add_assets_to_host(config, [a['asset_id'] for a in assets], host)

        # Save atomically
        save_fleet_yaml(fleet_path, config, yaml_parser)

        # Clean up backup on success
        if backup_path.exists():
            backup_path.unlink()

        return {
            "success": True,
            "summary": summary,
            "message": f"Imported {len(assets)} assets",
            "next_steps": [
                "Run: python scripts/generate-configs.py",
                "Add TELEGRAM_TOKEN_* entries to .env for each asset"
            ]
        }

    except (ValueError, ValidationError, FileNotFoundError, YAMLError, OSError) as e:
        # Restore backup on error
        if backup_path.exists():
            backup_content = backup_path.read_bytes()
            fleet_path.write_bytes(backup_content)
            backup_path.unlink()
        return {"success": False, "error": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk import assets from CSV to fleet.yaml"
    )
    parser.add_argument(
        '--csv', required=True, type=Path,
        help='Path to CSV file with asset data'
    )
    parser.add_argument(
        '--host', required=True,
        help='Host name to assign assets to'
    )
    parser.add_argument(
        '--fleet-file', type=Path, default=DEFAULT_FLEET_FILE,
        help='Path to fleet.yaml'
    )
    parser.add_argument(
        '--create-host', action='store_true',
        help='Create host if it does not exist'
    )
    parser.add_argument(
        '--redis', action='store_true',
        help='Enable Redis on created host (requires --create-host)'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Validate without saving changes'
    )

    args = parser.parse_args()

    if not args.csv.exists():
        print(json.dumps({"success": False, "error": f"CSV file not found: {args.csv}"}))
        sys.exit(1)

    if args.redis and not args.create_host:
        print(json.dumps({"success": False, "error": "--redis requires --create-host"}))
        sys.exit(1)

    result = import_csv(
        csv_path=args.csv,
        fleet_path=args.fleet_file,
        host=args.host,
        create_host_flag=args.create_host,
        redis=args.redis,
        dry_run=args.dry_run
    )

    print(json.dumps(result, indent=2))
    sys.exit(0 if result['success'] else 1)


if __name__ == "__main__":
    main()
