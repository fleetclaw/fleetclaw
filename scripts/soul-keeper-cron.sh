#!/bin/bash
# Soul Keeper Cron Script - Hourly Auto-Commit
# Add to crontab: 0 * * * * /path/to/soul-keeper-cron.sh
#
# This script runs hourly to commit any changes to workspace state,
# protecting against disk failures and enabling state recovery.

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACES_DIR="${WORKSPACES_DIR:-/generated/workspaces}"
LOG_FILE="${LOG_FILE:-/var/log/soul-keeper.log}"
PYTHON="${PYTHON:-python3}"

# Logging function
log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG_FILE"
}

# Run soul-keeper auto-commit
log "Starting auto-commit run"

if [ -d "$WORKSPACES_DIR" ]; then
    result=$("$PYTHON" "$SCRIPT_DIR/soul_keeper.py" auto-commit --workspaces-dir "$WORKSPACES_DIR" 2>&1)
    log "Result: $result"

    # Parse result to check for errors
    committed=$(echo "$result" | grep -o '"committed": [0-9]*' | grep -o '[0-9]*' || echo "0")
    log "Workspaces committed: $committed"
else
    log "ERROR: Workspaces directory not found: $WORKSPACES_DIR"
    exit 1
fi

log "Auto-commit run completed"
