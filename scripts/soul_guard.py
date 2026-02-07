#!/usr/bin/env python3
"""
Soul Guard - Atomic YAML state manager for SOUL.md files.

Provides safe, atomic updates to YAML sections in SOUL.md files,
preventing LLM hallucination and YAML syntax errors.

Usage:
    soul-guard update --key "hour_meter.current" --value "12850.5"
    soul-guard append --key "consumption_rates.samples" --value '{"date":"2026-01-31","rate":28}'
    soul-guard get --key "hour_meter.current"
    soul-guard validate
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap


# Allowed key paths for updates (prevents arbitrary writes)
ALLOWED_KEY_PATHS = {
    # Hour meter tracking
    'hour_meter.current',
    'hour_meter.last_updated',
    'hour_meter.trend',

    # Fuel tracking
    'fuel.current_level',
    'fuel.last_fill_date',
    'fuel.last_fill_liters',
    'fuel.estimated_remaining',

    # Consumption rates
    'consumption_rates.current',
    'consumption_rates.average',
    'consumption_rates.samples',

    # Status
    'status.current',
    'status.last_updated',
    'status.concerns',

    # Maintenance
    'maintenance.next_250',
    'maintenance.next_500',
    'maintenance.next_1000',
    'maintenance.next_2000',

    # Pre-op tracking
    'preop_checks.latest',
    'preop_checks.history',

    # Shift tracking
    'shift_tracking.current_shift',
    'shift_tracking.compliance',

    # Location
    'location.lat',
    'location.lon',
    'location.last_updated',
}

# Pattern to match YAML block in markdown
YAML_BLOCK_PATTERN = re.compile(
    r'^```ya?ml\s*\n(.*?)^```',
    re.MULTILINE | re.DOTALL
)


def load_soul_md(soul_path: Path) -> tuple[str, dict, int, int]:
    """Load SOUL.md and extract YAML content.

    Returns:
        Tuple of (full_content, yaml_dict, yaml_start_pos, yaml_end_pos)
    """
    content = soul_path.read_text(encoding='utf-8')

    # Find YAML block
    match = YAML_BLOCK_PATTERN.search(content)
    if not match:
        # Try to find inline YAML section
        yaml_section = extract_yaml_section(content)
        if yaml_section:
            yaml = YAML()
            yaml.preserve_quotes = True
            data = yaml.load(yaml_section['content'])
            return content, data, yaml_section['start'], yaml_section['end']
        raise ValueError("No YAML block found in SOUL.md")

    yaml_content = match.group(1)
    yaml = YAML()
    yaml.preserve_quotes = True
    data = yaml.load(yaml_content)

    return content, data, match.start(1), match.end(1)


def extract_yaml_section(content: str) -> Optional[dict]:
    """Extract YAML section from SOUL.md without code fence markers.

    Looks for a section starting with "## State" or similar and containing YAML.
    """
    # Look for state section
    state_match = re.search(
        r'^## (?:State|Current State|Operational State)\s*\n([\s\S]*?)(?=^## |\Z)',
        content,
        re.MULTILINE
    )
    if state_match:
        return {
            'content': state_match.group(1),
            'start': state_match.start(1),
            'end': state_match.end(1)
        }
    return None


def save_soul_md(soul_path: Path, content: str, data: dict, start: int, end: int) -> None:
    """Save updated SOUL.md with atomic write.

    Creates a backup and uses atomic rename for safety.
    """
    # Create backup
    backup_path = soul_path.with_suffix('.md.bak')
    shutil.copy2(soul_path, backup_path)

    # Serialize YAML
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    yaml.width = 120

    from io import StringIO
    stream = StringIO()
    yaml.dump(data, stream)
    new_yaml = stream.getvalue()

    # Replace YAML section
    new_content = content[:start] + new_yaml + content[end:]

    # Atomic write
    temp_path = soul_path.with_suffix('.md.tmp')
    temp_path.write_text(new_content, encoding='utf-8')
    temp_path.replace(soul_path)


def to_plain_dict(obj: Any) -> Any:
    """Convert CommentedMap/CommentedSeq to plain dict/list for JSON serialization."""
    if isinstance(obj, dict):
        return {k: to_plain_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_plain_dict(item) for item in obj]
    return obj


def write_state_sidecar(soul_path: Path, state_dict: dict) -> None:
    """Write state.json sidecar for Prometheus exporter.

    Creates a JSON file alongside SOUL.md containing the parsed state,
    allowing the exporter to read clean JSON instead of parsing markdown.
    Uses atomic write for safety.
    """
    sidecar_path = soul_path.parent / "state.json"
    tmp_path = sidecar_path.with_suffix('.json.tmp')

    export_data = {
        "extracted_at": datetime.now(timezone.utc).isoformat() + "Z",
        "source": str(soul_path),
        "state": to_plain_dict(state_dict)
    }

    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2)
    tmp_path.replace(sidecar_path)


def get_nested_value(data: dict, key_path: str) -> Any:
    """Get a nested value from a dictionary using dot notation."""
    keys = key_path.split('.')
    current = data

    for key in keys:
        if isinstance(current, dict):
            if key not in current:
                return None
            current = current[key]
        elif isinstance(current, list):
            try:
                idx = int(key)
                current = current[idx]
            except (ValueError, IndexError):
                return None
        else:
            return None

    return current


def set_nested_value(data: dict, key_path: str, value: Any) -> None:
    """Set a nested value in a dictionary using dot notation."""
    keys = key_path.split('.')
    current = data

    for key in keys[:-1]:
        if key not in current:
            current[key] = CommentedMap()
        current = current[key]

    current[keys[-1]] = value


def append_nested_value(data: dict, key_path: str, value: Any) -> None:
    """Append a value to a nested list using dot notation."""
    keys = key_path.split('.')
    current = data

    for key in keys[:-1]:
        if key not in current:
            current[key] = CommentedMap()
        current = current[key]

    final_key = keys[-1]
    if final_key not in current:
        current[final_key] = []

    if not isinstance(current[final_key], list):
        raise ValueError(f"Cannot append to non-list at {key_path}")

    current[final_key].append(value)


def parse_value(value_str: str) -> Any:
    """Parse a value string into appropriate Python type."""
    # Try JSON first (handles objects, arrays, quoted strings)
    try:
        return json.loads(value_str)
    except json.JSONDecodeError:
        pass

    # Try numeric
    try:
        return float(value_str) if '.' in value_str else int(value_str)
    except ValueError:
        pass

    # Boolean
    lower_value = value_str.lower()
    if lower_value in ('true', 'yes'):
        return True
    if lower_value in ('false', 'no'):
        return False

    return value_str


def validate_key_path(key_path: str) -> bool:
    """Check if a key path is allowed for updates."""
    # Check exact match
    if key_path in ALLOWED_KEY_PATHS:
        return True

    # Check if it's a sub-path of an allowed path (for nested updates)
    for allowed in ALLOWED_KEY_PATHS:
        if key_path.startswith(allowed + '.'):
            return True

    return False


def cmd_get(args: argparse.Namespace) -> int:
    """Get a value from SOUL.md."""
    soul_path = Path(args.soul_file)
    if not soul_path.exists():
        print(json.dumps({'error': f'File not found: {soul_path}', 'success': False}))
        return 1

    try:
        _, data, _, _ = load_soul_md(soul_path)
        value = get_nested_value(data, args.key)
        print(json.dumps({'success': True, 'key': args.key, 'value': value}))
        return 0
    except Exception as e:
        print(json.dumps({'error': str(e), 'success': False}))
        return 1


def cmd_update(args: argparse.Namespace) -> int:
    """Update a value in SOUL.md."""
    soul_path = Path(args.soul_file)
    if not soul_path.exists():
        print(json.dumps({'error': f'File not found: {soul_path}', 'success': False}))
        return 1

    if not args.force and not validate_key_path(args.key):
        print(json.dumps({
            'error': f'Key path not allowed: {args.key}',
            'allowed_paths': sorted(ALLOWED_KEY_PATHS),
            'success': False
        }))
        return 1

    try:
        content, data, start, end = load_soul_md(soul_path)
        value = parse_value(args.value)
        old_value = get_nested_value(data, args.key)
        set_nested_value(data, args.key, value)
        save_soul_md(soul_path, content, data, start, end)
        write_state_sidecar(soul_path, data)

        print(json.dumps({
            'success': True,
            'key': args.key,
            'old_value': old_value,
            'new_value': value,
            'timestamp': datetime.now(timezone.utc).isoformat() + 'Z'
        }))
        return 0
    except Exception as e:
        print(json.dumps({'error': str(e), 'success': False}))
        return 1


def cmd_append(args: argparse.Namespace) -> int:
    """Append a value to a list in SOUL.md."""
    soul_path = Path(args.soul_file)
    if not soul_path.exists():
        print(json.dumps({'error': f'File not found: {soul_path}', 'success': False}))
        return 1

    if not args.force and not validate_key_path(args.key):
        print(json.dumps({
            'error': f'Key path not allowed: {args.key}',
            'allowed_paths': sorted(ALLOWED_KEY_PATHS),
            'success': False
        }))
        return 1

    try:
        content, data, start, end = load_soul_md(soul_path)
        value = parse_value(args.value)
        append_nested_value(data, args.key, value)
        save_soul_md(soul_path, content, data, start, end)
        write_state_sidecar(soul_path, data)

        current_list = get_nested_value(data, args.key)
        print(json.dumps({
            'success': True,
            'key': args.key,
            'appended_value': value,
            'list_length': len(current_list) if current_list else 0,
            'timestamp': datetime.now(timezone.utc).isoformat() + 'Z'
        }))
        return 0
    except Exception as e:
        print(json.dumps({'error': str(e), 'success': False}))
        return 1


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate SOUL.md YAML structure."""
    soul_path = Path(args.soul_file)
    if not soul_path.exists():
        print(json.dumps({'error': f'File not found: {soul_path}', 'success': False}))
        return 1

    try:
        _, data, _, _ = load_soul_md(soul_path)

        recommended_keys = ['hour_meter', 'status', 'fuel', 'maintenance']
        issues = [
            f"Missing recommended key: {key}"
            for key in recommended_keys
            if key not in data
        ]

        is_valid = len(issues) == 0
        print(json.dumps({
            'success': True,
            'valid': is_valid,
            'issues': issues,
            'keys_found': list(data.keys()) if data else []
        }))
        return 0 if is_valid else 1
    except Exception as e:
        print(json.dumps({'error': str(e), 'success': False, 'valid': False}))
        return 1


def cmd_list_keys(args: argparse.Namespace) -> int:
    """List allowed key paths."""
    print(json.dumps({
        'success': True,
        'allowed_paths': sorted(ALLOWED_KEY_PATHS)
    }))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Soul Guard - Atomic YAML state manager for SOUL.md',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  soul-guard get --key "hour_meter.current"
  soul-guard update --key "hour_meter.current" --value "12850.5"
  soul-guard append --key "consumption_rates.samples" --value '{"date":"2026-01-31","rate":28}'
  soul-guard validate
  soul-guard list-keys
        """
    )

    parser.add_argument('--soul-file', default='/app/workspace/SOUL.md',
                        help='Path to SOUL.md file')

    subparsers = parser.add_subparsers(dest='command', required=True)

    # get command
    get_parser = subparsers.add_parser('get', help='Get a value')
    get_parser.add_argument('--key', required=True, help='Key path (dot notation)')

    # update command
    update_parser = subparsers.add_parser('update', help='Update a value')
    update_parser.add_argument('--key', required=True, help='Key path (dot notation)')
    update_parser.add_argument('--value', required=True, help='New value (JSON or primitive)')
    update_parser.add_argument('--force', action='store_true',
                               help='Allow update even if key path not in allowed list')

    # append command
    append_parser = subparsers.add_parser('append', help='Append to a list')
    append_parser.add_argument('--key', required=True, help='Key path to list (dot notation)')
    append_parser.add_argument('--value', required=True, help='Value to append (JSON or primitive)')
    append_parser.add_argument('--force', action='store_true',
                               help='Allow append even if key path not in allowed list')

    # validate command
    subparsers.add_parser('validate', help='Validate SOUL.md structure')

    # list-keys command
    subparsers.add_parser('list-keys', help='List allowed key paths')

    args = parser.parse_args()

    commands = {
        'get': cmd_get,
        'update': cmd_update,
        'append': cmd_append,
        'validate': cmd_validate,
        'list-keys': cmd_list_keys,
    }

    return commands[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
