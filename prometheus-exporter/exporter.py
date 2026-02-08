#!/usr/bin/env python3
"""
Prometheus Exporter for Fleetclaw SOUL.md metrics.

Reads state from state.json (preferred) or parses SOUL.md YAML as fallback.
Exposes metrics at /metrics endpoint.
Runs as a sidecar container alongside each asset agent.
"""

import json
import os
import re
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Optional

import yaml


# Configuration
STATE_FILE = os.environ.get('STATE_FILE', '/app/workspace/state.json')
SOUL_FILE = os.environ.get('SOUL_FILE', '/app/workspace/SOUL.md')
ASSET_ID = os.environ.get('ASSET_ID', 'unknown')
ASSET_TYPE = os.environ.get('ASSET_TYPE', 'unknown')
PORT = int(os.environ.get('METRICS_PORT', '9090'))
SCRAPE_INTERVAL = int(os.environ.get('SCRAPE_INTERVAL', '15'))

# Pattern to extract YAML from SOUL.md
YAML_BLOCK_PATTERN = re.compile(
    r'^```ya?ml\s*\n(.*?)^```',
    re.MULTILINE | re.DOTALL
)


def parse_soul_md(soul_path: str) -> Optional[dict]:
    """Parse SOUL.md and extract YAML state."""
    try:
        content = Path(soul_path).read_text(encoding='utf-8')

        # Try code fence block first
        match = YAML_BLOCK_PATTERN.search(content)
        if match:
            return yaml.safe_load(match.group(1))

        # Try extracting state section
        state_match = re.search(
            r'^## (?:State|Current State|Operational State)\s*\n([\s\S]*?)(?=^## |\Z)',
            content,
            re.MULTILINE
        )
        if state_match:
            return yaml.safe_load(state_match.group(1))

        return None
    except Exception as e:
        print(f"Error parsing SOUL.md: {e}")
        return None


def load_state() -> Optional[dict]:
    """Load state from JSON sidecar, falling back to SOUL.md parsing.

    Prefers state.json (written by soul-guard) as it's cleaner and faster.
    Falls back to parsing SOUL.md for backwards compatibility.
    """
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('state', {})
    except FileNotFoundError:
        pass
    except json.JSONDecodeError as e:
        print(f"Warning: Invalid JSON in state.json: {e}")

    return parse_soul_md(SOUL_FILE)


def get_nested(data: dict, *keys, default: Any = None) -> Any:
    """Safely get nested dictionary value."""
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def format_metric(name: str, value: Any, labels: dict, help_text: str = '', metric_type: str = 'gauge') -> str:
    """Format a single Prometheus metric."""
    if value is None:
        return ''

    # Build label string
    label_str = ','.join(f'{k}="{v}"' for k, v in labels.items())

    lines = []
    if help_text:
        lines.append(f'# HELP {name} {help_text}')
    lines.append(f'# TYPE {name} {metric_type}')
    lines.append(f'{name}{{{label_str}}} {value}')

    return '\n'.join(lines)


def generate_metrics(data: dict) -> str:
    """Generate Prometheus metrics from SOUL.md data."""
    metrics = []
    labels = {'asset_id': ASSET_ID, 'asset_type': ASSET_TYPE}

    # Hour meter
    hour_meter = get_nested(data, 'hour_meter', 'current')
    if hour_meter is not None:
        metrics.append(format_metric(
            'fleetclaw_hour_meter_hours',
            hour_meter,
            labels,
            'Current hour meter reading'
        ))

    # Fuel metrics
    fuel_data = data.get('fuel', {})
    if isinstance(fuel_data, dict):
        tank_capacity = get_nested(data, 'specs', 'tank_capacity') or get_nested(fuel_data, 'tank_capacity')
        if tank_capacity:
            metrics.append(format_metric(
                'fleetclaw_fuel_tank_capacity_liters',
                tank_capacity,
                labels,
                'Fuel tank capacity in liters'
            ))

        current_level = fuel_data.get('current_level') or fuel_data.get('estimated_remaining')
        if current_level:
            metrics.append(format_metric(
                'fleetclaw_fuel_current_liters',
                current_level,
                labels,
                'Current estimated fuel level in liters'
            ))

        last_fill = fuel_data.get('last_fill_liters')
        if last_fill:
            metrics.append(format_metric(
                'fleetclaw_fuel_last_fill_liters',
                last_fill,
                labels,
                'Last fuel fill amount in liters'
            ))

    # Consumption rate
    consumption = get_nested(data, 'consumption_rates', 'average') or get_nested(data, 'consumption', 'average')
    if consumption:
        metrics.append(format_metric(
            'fleetclaw_consumption_rate_avg_lph',
            consumption,
            labels,
            'Average fuel consumption rate (L/hr or L/100km)'
        ))

    # Status (convert to numeric for alerting)
    status = get_nested(data, 'status', 'current')
    if status:
        status_map = {
            'OPERATIONAL': 1,
            'IDLE': 2,
            'MAINTENANCE': 3,
            'DOWN': 4,
            'CRITICAL': 5,
            'UNKNOWN': 0
        }
        status_value = status_map.get(str(status).upper(), 0)
        metrics.append(format_metric(
            'fleetclaw_asset_status',
            status_value,
            {**labels, 'status': str(status)},
            'Asset operational status (1=operational, 2=idle, 3=maintenance, 4=down, 5=critical)'
        ))

    # Maintenance due
    maintenance = data.get('maintenance', {})
    if isinstance(maintenance, dict):
        for interval, due_hours in maintenance.items():
            if isinstance(due_hours, (int, float)):
                metrics.append(format_metric(
                    'fleetclaw_maintenance_next_due_hours',
                    due_hours,
                    {**labels, 'maintenance_type': str(interval)},
                    'Hours until next maintenance'
                ))

    # Concerns count by severity
    concerns = get_nested(data, 'status', 'concerns') or data.get('concerns', [])
    if isinstance(concerns, list):
        severity_counts = {'high': 0, 'medium': 0, 'low': 0}
        for concern in concerns:
            if isinstance(concern, dict):
                severity = concern.get('severity', 'medium').lower()
                if severity in severity_counts:
                    severity_counts[severity] += 1
            else:
                severity_counts['medium'] += 1

        for severity, count in severity_counts.items():
            metrics.append(format_metric(
                'fleetclaw_concerns_active_count',
                count,
                {**labels, 'severity': severity},
                'Number of active concerns'
            ))

    # Pre-op compliance
    compliance = get_nested(data, 'shift_tracking', 'compliance', 'last_7_days')
    if isinstance(compliance, dict):
        expected = compliance.get('checks_expected', 0)
        completed = compliance.get('checks_completed', 0)
        if expected > 0:
            metrics.append(format_metric(
                'fleetclaw_preop_compliance_ratio',
                completed / expected,
                labels,
                'Pre-op check compliance ratio (0-1)'
            ))

    # Exporter metadata
    metrics.append(format_metric(
        'fleetclaw_exporter_scrape_timestamp',
        int(time.time()),
        labels,
        'Last successful scrape timestamp',
        'counter'
    ))

    # Exporter health indicator (1 = healthy, successfully parsed SOUL.md)
    metrics.append(format_metric(
        'fleetclaw_exporter_up',
        1,
        labels,
        'Exporter health status (1=up, 0=failed to parse SOUL.md)'
    ))

    return '\n\n'.join(filter(None, metrics)) + '\n'


def generate_error_metrics() -> str:
    """Generate minimal metrics when SOUL.md cannot be parsed."""
    labels = {'asset_id': ASSET_ID, 'asset_type': ASSET_TYPE}
    metrics = []

    # Indicate exporter is down/unhealthy
    metrics.append(format_metric(
        'fleetclaw_exporter_up',
        0,
        labels,
        'Exporter health status (1=up, 0=failed to parse SOUL.md)'
    ))

    # Still report scrape timestamp
    metrics.append(format_metric(
        'fleetclaw_exporter_scrape_timestamp',
        int(time.time()),
        labels,
        'Last scrape attempt timestamp',
        'counter'
    ))

    return '\n\n'.join(filter(None, metrics)) + '\n'


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for /metrics endpoint."""

    def do_GET(self):
        if self.path == '/metrics':
            data = load_state()
            if data:
                metrics = generate_metrics(data)
            else:
                # Return error metrics instead of 500 to avoid scrape failures
                metrics = generate_error_metrics()
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(metrics.encode('utf-8'))
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress access logs
        pass


def main():
    """Start the metrics server."""
    print(f"Starting Fleetclaw Prometheus Exporter")
    print(f"  Asset ID: {ASSET_ID}")
    print(f"  Asset Type: {ASSET_TYPE}")
    print(f"  State file: {STATE_FILE} (primary)")
    print(f"  SOUL file: {SOUL_FILE} (fallback)")
    print(f"  Metrics port: {PORT}")

    server = HTTPServer(('0.0.0.0', PORT), MetricsHandler)
    print(f"Serving metrics at http://0.0.0.0:{PORT}/metrics")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == '__main__':
    main()
