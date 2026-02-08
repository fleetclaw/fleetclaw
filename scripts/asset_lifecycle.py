#!/usr/bin/env python3
"""
Asset Lifecycle Management for Fleet Coordinator

Manages asset container lifecycle (active/idle) based on activity.
Provides CLI and library interface for:
- Waking idle assets
- Idling active assets
- Checking asset status
- Nightly idle checks
- Boot recovery

Usage:
    python scripts/asset_lifecycle.py status [asset_id]
    python scripts/asset_lifecycle.py wake <asset_id>
    python scripts/asset_lifecycle.py idle <asset_id>
    python scripts/asset_lifecycle.py nightly-check
    python scripts/asset_lifecycle.py boot-recovery
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


# Default configuration
DEFAULT_IDLE_THRESHOLD_DAYS = 7
DEFAULT_COMPOSE_FILE = 'generated/compose/docker-compose-host-01.yml'
WAKE_BUFFER_TTL_SECONDS = 300  # 5 minutes
SECONDS_PER_DAY = 86400

# Redis key patterns
KEY_LIFECYCLE_PREFIX = "fleet:lifecycle:"
KEY_LIFECYCLE = KEY_LIFECYCLE_PREFIX + "{}"
KEY_WAKE_BUFFER = "fleet:wake_buffer:{}"


def get_redis_client() -> Optional['redis.Redis']:
    """Get Redis client from environment."""
    if not REDIS_AVAILABLE:
        print("Warning: redis-py not installed, using CLI fallback")
        return None

    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    try:
        client = redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception as e:
        print(f"Warning: Redis connection failed: {e}")
        return None


def get_compose_file() -> str:
    """Get docker-compose file path from environment."""
    return os.environ.get('COMPOSE_FILE', DEFAULT_COMPOSE_FILE)


def get_container_name(asset_id: str) -> str:
    """Get container name for an asset."""
    return f"fleetclaw-{asset_id.lower()}"


def get_asset_status(asset_id: str, redis_client: Optional['redis.Redis'] = None) -> dict:
    """Get current status for an asset.

    Returns:
        dict with keys: status, last_activity, last_activity_type, idle_since
    """
    if redis_client:
        data = redis_client.hgetall(KEY_LIFECYCLE.format(asset_id))
        if data:
            return data

    # Fallback: check container status
    container = get_container_name(asset_id)
    result = subprocess.run(
        ['docker', 'inspect', '-f', '{{.State.Running}}', container],
        capture_output=True, text=True
    )

    if result.returncode == 0 and result.stdout.strip() == 'true':
        return {'status': 'active', 'source': 'docker'}
    return {'status': 'idle', 'source': 'docker'}


def get_all_asset_status(redis_client: Optional['redis.Redis'] = None) -> dict:
    """Get status for all tracked assets."""
    statuses = {}

    if redis_client:
        keys = redis_client.keys(KEY_LIFECYCLE_PREFIX + "*")
        for key in keys:
            asset_id = key.removeprefix(KEY_LIFECYCLE_PREFIX)
            statuses[asset_id] = redis_client.hgetall(key)

    return statuses


def wake_asset(
    asset_id: str,
    triggering_message: Optional[dict] = None,
    redis_client: Optional['redis.Redis'] = None,
    compose_file: Optional[str] = None
) -> bool:
    """Wake an idle asset's container.

    Args:
        asset_id: Asset identifier
        triggering_message: Optional message that triggered the wake
        redis_client: Optional Redis client
        compose_file: Optional path to docker-compose file

    Returns:
        True if successful, False otherwise
    """
    compose_file = compose_file or get_compose_file()
    container = get_container_name(asset_id)
    now = datetime.now(timezone.utc).isoformat()

    # Buffer the triggering message if provided
    if triggering_message and redis_client:
        redis_client.set(
            KEY_WAKE_BUFFER.format(asset_id),
            json.dumps(triggering_message),
            ex=WAKE_BUFFER_TTL_SECONDS
        )

    # Start the container
    result = subprocess.run(
        ['docker', 'compose', '-f', compose_file, 'start', container],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"Error starting {asset_id}: {result.stderr}")
        return False

    # Update status in Redis
    if redis_client:
        redis_client.hset(KEY_LIFECYCLE.format(asset_id), mapping={
            'status': 'active',
            'last_activity': now,
            'last_activity_type': 'wake'
        })
        # Remove idle_since if present
        redis_client.hdel(KEY_LIFECYCLE.format(asset_id), 'idle_since')

    print(f"▶️ {asset_id} resumed from idle")
    return True


def idle_asset(
    asset_id: str,
    reason: str = "manual",
    redis_client: Optional['redis.Redis'] = None,
    compose_file: Optional[str] = None
) -> bool:
    """Stop an active asset's container.

    Args:
        asset_id: Asset identifier
        reason: Reason for idling
        redis_client: Optional Redis client
        compose_file: Optional path to docker-compose file

    Returns:
        True if successful, False otherwise
    """
    compose_file = compose_file or get_compose_file()
    container = get_container_name(asset_id)
    now = datetime.now(timezone.utc).isoformat()

    # Stop the container
    result = subprocess.run(
        ['docker', 'compose', '-f', compose_file, 'stop', container],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"Error stopping {asset_id}: {result.stderr}")
        return False

    # Update status in Redis
    if redis_client:
        redis_client.hset(KEY_LIFECYCLE.format(asset_id), mapping={
            'status': 'idle',
            'idle_since': now,
            'idle_reason': reason
        })

    print(f"⏸️ {asset_id} entering idle mode ({reason})")
    return True


def nightly_check(
    threshold_days: int = DEFAULT_IDLE_THRESHOLD_DAYS,
    redis_client: Optional['redis.Redis'] = None,
    compose_file: Optional[str] = None,
    dry_run: bool = False
) -> list:
    """Run nightly idle check on all active assets.

    Args:
        threshold_days: Days without activity before idling
        redis_client: Optional Redis client
        compose_file: Optional path to docker-compose file
        dry_run: If True, don't actually idle assets

    Returns:
        List of asset IDs that were idled
    """
    if not redis_client:
        print("Error: Redis required for nightly check")
        return []

    compose_file = compose_file or get_compose_file()
    now = datetime.now(timezone.utc)
    threshold_seconds = threshold_days * SECONDS_PER_DAY
    idled = []

    keys = redis_client.keys(KEY_LIFECYCLE_PREFIX + "*")

    for key in keys:
        asset_id = key.removeprefix(KEY_LIFECYCLE_PREFIX)
        status_data = redis_client.hgetall(key)

        if status_data.get('status') != 'active':
            continue

        last_activity = status_data.get('last_activity')
        if not last_activity:
            continue

        try:
            last_dt = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
            delta = (now - last_dt).total_seconds()

            if delta > threshold_seconds:
                days_inactive = int(delta / SECONDS_PER_DAY)
                if dry_run:
                    print(f"Would idle {asset_id} (inactive {days_inactive} days)")
                else:
                    reason = f"no activity for {days_inactive} days"
                    if idle_asset(asset_id, reason, redis_client, compose_file):
                        idled.append(asset_id)
        except (ValueError, TypeError) as e:
            print(f"Warning: Could not parse last_activity for {asset_id}: {e}")

    if idled:
        print(f"\nNightly check: {len(idled)} assets idled ({', '.join(idled)})")
    else:
        print("Nightly check: No assets to idle")

    return idled


def boot_recovery(
    redis_client: Optional['redis.Redis'] = None,
    compose_file: Optional[str] = None
) -> list:
    """Restore previously active assets after FC restart.

    Args:
        redis_client: Optional Redis client
        compose_file: Optional path to docker-compose file

    Returns:
        List of asset IDs that were started
    """
    if not redis_client:
        print("Warning: Redis not available, cannot perform boot recovery")
        return []

    compose_file = compose_file or get_compose_file()
    started = []

    keys = redis_client.keys(KEY_LIFECYCLE_PREFIX + "*")

    for key in keys:
        asset_id = key.removeprefix(KEY_LIFECYCLE_PREFIX)
        status_data = redis_client.hgetall(key)

        if status_data.get('status') != 'active':
            continue

        # Check if container is actually running
        container = get_container_name(asset_id)
        result = subprocess.run(
            ['docker', 'inspect', '-f', '{{.State.Running}}', container],
            capture_output=True, text=True
        )

        if result.returncode != 0 or result.stdout.strip() != 'true':
            print(f"Boot recovery: Starting {asset_id}...")
            if wake_asset(asset_id, redis_client=redis_client, compose_file=compose_file):
                started.append(asset_id)

    if started:
        print(f"\nBoot recovery: Started {len(started)} assets ({', '.join(started)})")
    else:
        print("Boot recovery: All active assets already running")

    return started


def record_activity(
    asset_id: str,
    activity_type: str,
    redis_client: Optional['redis.Redis'] = None
) -> None:
    """Record activity for an asset (resets idle timer).

    Args:
        asset_id: Asset identifier
        activity_type: Type of activity (fuel_log, pre_op, etc.)
        redis_client: Optional Redis client
    """
    if not redis_client:
        return

    now = datetime.now(timezone.utc).isoformat()
    redis_client.hset(KEY_LIFECYCLE.format(asset_id), mapping={
        'last_activity': now,
        'last_activity_type': activity_type
    })


def main():
    parser = argparse.ArgumentParser(description='Asset lifecycle management')
    parser.add_argument('command', choices=['status', 'wake', 'idle', 'nightly-check', 'boot-recovery'])
    parser.add_argument('asset_id', nargs='?', help='Asset ID (required for wake/idle)')
    parser.add_argument('--compose-file', help='Path to docker-compose file')
    parser.add_argument('--threshold-days', type=int, default=DEFAULT_IDLE_THRESHOLD_DAYS,
                        help='Days without activity before idling (default: 7)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
    args = parser.parse_args()

    redis_client = get_redis_client()
    compose_file = args.compose_file or get_compose_file()

    if args.command == 'status':
        if args.asset_id:
            status = get_asset_status(args.asset_id, redis_client)
            print(f"{args.asset_id}: {json.dumps(status, indent=2)}")
        else:
            statuses = get_all_asset_status(redis_client)
            if statuses:
                for asset_id, status in sorted(statuses.items()):
                    print(f"{asset_id}: {status.get('status', 'unknown')}")
            else:
                print("No assets tracked in Redis")

    elif args.command == 'wake':
        if not args.asset_id:
            print("Error: asset_id required for wake command")
            sys.exit(1)
        success = wake_asset(args.asset_id, redis_client=redis_client, compose_file=compose_file)
        sys.exit(0 if success else 1)

    elif args.command == 'idle':
        if not args.asset_id:
            print("Error: asset_id required for idle command")
            sys.exit(1)
        success = idle_asset(args.asset_id, "manual", redis_client, compose_file)
        sys.exit(0 if success else 1)

    elif args.command == 'nightly-check':
        idled = nightly_check(args.threshold_days, redis_client, compose_file, args.dry_run)
        sys.exit(0)

    elif args.command == 'boot-recovery':
        started = boot_recovery(redis_client, compose_file)
        sys.exit(0)


if __name__ == '__main__':
    main()
