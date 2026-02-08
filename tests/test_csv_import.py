"""Tests for csv_import.py script."""

import sys
from pathlib import Path

import pytest

# Add scripts directory to path for imports
SCRIPTS_DIR = Path(__file__).parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

from csv_import import (
    ASSET_TYPE_METADATA,
    create_host,
    map_csv_row_to_asset,
    normalize_category,
    parse_csv,
    resolve_asset_type,
    validate_assets,
)


class TestParseCSV:
    """Tests for CSV parsing with edge cases."""

    def test_parse_valid_csv(self, tmp_path):
        """Parse a valid CSV file."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "asset_id,category,make,model,year,serial_number\n"
            "EX-001,Excavator,CAT,390F,2020,ABC123\n"
        )
        rows = parse_csv(csv_file)
        assert len(rows) == 1
        assert rows[0]['asset_id'] == 'EX-001'
        assert rows[0]['category'] == 'Excavator'

    def test_parse_csv_with_bom(self, tmp_path):
        """Parse CSV with UTF-8 BOM (Windows export)."""
        csv_file = tmp_path / "test_bom.csv"
        # Write with BOM
        csv_file.write_bytes(
            b'\xef\xbb\xbf'  # UTF-8 BOM
            b'asset_id,category,make,model,year\n'
            b'EX-001,Excavator,CAT,390F,2020\n'
        )
        rows = parse_csv(csv_file)
        assert len(rows) == 1
        # BOM should not appear in first column name
        assert 'asset_id' in rows[0]
        assert rows[0]['asset_id'] == 'EX-001'

    def test_parse_csv_empty_rows(self, tmp_path):
        """Parse CSV with empty rows (should be skipped by DictReader)."""
        csv_file = tmp_path / "test_empty.csv"
        csv_file.write_text(
            "asset_id,category,make,model,year\n"
            "EX-001,Excavator,CAT,390F,2020\n"
            "\n"  # Empty row
            "EX-002,Excavator,Komatsu,PC490,2019\n"
        )
        rows = parse_csv(csv_file)
        # Empty rows produce dicts with empty values, not skipped
        # Filter out rows with empty asset_id in real usage
        valid_rows = [r for r in rows if r.get('asset_id')]
        assert len(valid_rows) == 2

    def test_parse_csv_header_only(self, tmp_path):
        """Parse CSV with only header row."""
        csv_file = tmp_path / "test_header.csv"
        csv_file.write_text("asset_id,category,make,model,year\n")
        rows = parse_csv(csv_file)
        assert len(rows) == 0

    def test_parse_csv_missing_columns(self, tmp_path):
        """Parse CSV with missing columns returns None for those fields."""
        csv_file = tmp_path / "test_missing.csv"
        csv_file.write_text(
            "asset_id,category\n"
            "EX-001,Excavator\n"
        )
        rows = parse_csv(csv_file)
        assert len(rows) == 1
        assert rows[0]['asset_id'] == 'EX-001'
        assert rows[0].get('make') is None
        assert rows[0].get('model') is None

    def test_parse_csv_extra_columns(self, tmp_path):
        """Parse CSV with extra columns includes them."""
        csv_file = tmp_path / "test_extra.csv"
        csv_file.write_text(
            "asset_id,category,make,model,year,extra_field\n"
            "EX-001,Excavator,CAT,390F,2020,extra_value\n"
        )
        rows = parse_csv(csv_file)
        assert len(rows) == 1
        assert rows[0]['extra_field'] == 'extra_value'

    def test_parse_csv_quoted_fields(self, tmp_path):
        """Parse CSV with quoted fields containing commas."""
        csv_file = tmp_path / "test_quoted.csv"
        csv_file.write_text(
            'asset_id,category,make,model,year\n'
            'EX-001,"DTH Surface Drill [4-6"" Hmr]",Sandvik,DI-500,2008\n'
        )
        rows = parse_csv(csv_file)
        assert len(rows) == 1
        # Note: The actual category in the CSV has quotes escaped
        assert 'DTH Surface Drill' in rows[0]['category']


class TestCategoryMapping:
    """Tests for category to type mapping."""

    def test_normalize_category(self):
        """Test category name normalization to snake_case."""
        assert normalize_category('Artic. Dump Truck') == 'artic_dump_truck'
        assert normalize_category('DTH Surface Drill') == 'dth_surface_drill'
        assert normalize_category('Wheel Loader') == 'wheel_loader'
        assert normalize_category('Motor Grader') == 'motor_grader'
        assert normalize_category('  Excavator  ') == 'excavator'

    def test_resolve_direct_match(self):
        """Categories that normalize to valid type keys should match directly."""
        # These normalize to exact ASSET_TYPE_METADATA keys
        assert resolve_asset_type('Excavator') == 'excavator'
        assert resolve_asset_type('Wheel Loader') == 'wheel_loader'
        assert resolve_asset_type('Artic. Dump Truck') == 'artic_dump_truck'
        assert resolve_asset_type('DTH Surface Drill') == 'dth_surface_drill'

    def test_resolve_alias_match(self):
        """Categories that need aliases should resolve correctly."""
        # These need CATEGORY_ALIASES because normalized form doesn't match
        assert resolve_asset_type('Motorgrader') == 'motor_grader'
        assert resolve_asset_type('Rigid Frame Haul Trk') == 'rigid_haul_truck'

    def test_resolve_unknown_returns_none(self):
        """Unknown categories should return None."""
        assert resolve_asset_type('Unknown Equipment') is None
        assert resolve_asset_type('Spaceship') is None

    def test_all_expected_categories_resolve(self):
        """Verify all expected CSV categories resolve to valid types."""
        expected_categories = [
            'Artic. Dump Truck',
            'Backhoe',
            'DTH Surface Drill',
            'Dump Truck',
            'Excavator',
            'Material Handler',
            'Motorgrader',
            'Rigid Frame Haul Trk',
            'Semi Truck',
            'Service Truck',
            'Skid Steer',
            'Supervisor Truck',
            'Telehandler',
            'Track Dozer',
            'Water Truck',
            'Wheel Loader',
            'Wheel Tractor',
            'Work Truck',
        ]
        for category in expected_categories:
            resolved = resolve_asset_type(category)
            assert resolved is not None, f"Failed to resolve: {category}"
            assert resolved in ASSET_TYPE_METADATA, f"Resolved to invalid type: {resolved}"

    def test_map_excavator_row(self):
        """Map an excavator CSV row to asset dict."""
        row = {
            'asset_id': 'KOE32',
            'category': 'Excavator',
            'make': 'Komatsu',
            'model': 'PC160LC-7KA',
            'year': '2006',
            'serial_number': 'KMTPC047P55K41058',
        }
        asset_data = map_csv_row_to_asset(row, 'test-host')

        assert asset_data['asset_id'] == 'KOE32'
        assert asset_data['type'] == 'excavator'
        assert asset_data['make'] == 'Komatsu'
        assert asset_data['model'] == 'PC160LC-7KA'
        assert asset_data['year'] == 2006
        assert asset_data['host'] == 'test-host'
        assert asset_data['telegram_group'] == '@koe32_ops'

    def test_map_supervisor_truck_row(self):
        """Map a supervisor truck to asset dict (gets dedicated agent like all assets)."""
        row = {
            'asset_id': 'GMT76',
            'category': 'Supervisor Truck',
            'make': 'GMC',
            'model': 'Sierra',
            'year': '2013',
            'serial_number': '',
        }
        asset_data = map_csv_row_to_asset(row, 'test-host')

        assert asset_data['asset_id'] == 'GMT76'
        assert asset_data['type'] == 'supervisor_truck'
        assert asset_data['host'] == 'test-host'
        assert asset_data['telegram_group'] == '@gmt76_ops'

    def test_map_unknown_category_raises(self):
        """Mapping unknown category raises ValueError."""
        row = {
            'asset_id': 'UNK-001',
            'category': 'Unknown Equipment',
            'make': 'Unknown',
            'model': 'Unknown',
            'year': '2020',
            'serial_number': '',
        }
        with pytest.raises(ValueError, match="Unknown category"):
            map_csv_row_to_asset(row, 'test-host')

    def test_map_row_without_year(self):
        """Map row without year field."""
        row = {
            'asset_id': 'EX-001',
            'category': 'Excavator',
            'make': 'CAT',
            'model': '390F',
            'year': '',
            'serial_number': 'ABC123',
        }
        asset_data = map_csv_row_to_asset(row, 'test-host')
        assert 'year' not in asset_data

    def test_map_row_model_as_number(self):
        """Model field should always be string even if numeric."""
        row = {
            'asset_id': 'CAL10',
            'category': 'Wheel Loader',
            'make': 'Caterpillar',
            'model': '992',  # Numeric-looking model
            'year': '1992',
            'serial_number': '49Z01904',
        }
        asset_data = map_csv_row_to_asset(row, 'test-host')
        assert asset_data['model'] == '992'
        assert isinstance(asset_data['model'], str)


class TestDuplicateDetection:
    """Tests for duplicate asset detection."""

    def test_detect_duplicate_in_csv(self):
        """Detect duplicate asset IDs within the CSV."""
        assets = [
            {'asset_id': 'EX-001', 'type': 'excavator', 'host': 'test', 'make': 'CAT', 'model': '390F'},
            {'asset_id': 'EX-001', 'type': 'excavator', 'host': 'test', 'make': 'CAT', 'model': '390F'},
        ]
        config = {'assets': [], 'hosts': [{'name': 'test'}]}

        errors = validate_assets(assets, config, 'test')

        assert any('Duplicate asset_id in CSV: EX-001' in e for e in errors)

    def test_detect_duplicate_in_existing_config(self):
        """Detect duplicate against existing fleet.yaml assets."""
        assets = [
            {'asset_id': 'EX-001', 'type': 'excavator', 'host': 'test', 'make': 'CAT', 'model': '390F'},
        ]
        config = {
            'assets': [{'asset_id': 'EX-001'}],
            'hosts': [{'name': 'test'}],
        }

        errors = validate_assets(assets, config, 'test')

        assert any("already exists in fleet.yaml" in e for e in errors)

    def test_no_duplicates_passes(self):
        """No errors when there are no duplicates."""
        assets = [
            {'asset_id': 'EX-001', 'type': 'excavator', 'host': 'test', 'make': 'CAT', 'model': '390F'},
            {'asset_id': 'EX-002', 'type': 'excavator', 'host': 'test', 'make': 'Komatsu', 'model': 'PC490'},
        ]
        config = {'assets': [], 'hosts': [{'name': 'test'}]}

        errors = validate_assets(assets, config, 'test')

        # Filter out host-related errors and validation errors
        duplicate_errors = [e for e in errors if 'Duplicate' in e or 'already exists' in e]
        assert len(duplicate_errors) == 0


class TestCreateHost:
    """Tests for host creation with FLEET-COORD and Redis handling."""

    def test_create_host_adds_fleet_coord(self):
        """New host should include FLEET-COORD in assets."""
        config = {'hosts': []}
        create_host(config, 'new-host')

        assert len(config['hosts']) == 1
        host = config['hosts'][0]
        assert host['name'] == 'new-host'
        assert 'FLEET-COORD' in host['assets']
        assert host['redis'] is False

    def test_create_host_with_redis(self):
        """New host with redis=True should have redis enabled."""
        config = {'hosts': []}
        create_host(config, 'new-host', redis=True)

        host = config['hosts'][0]
        assert host['redis'] is True
        assert 'FLEET-COORD' in host['assets']

    def test_create_host_existing_does_not_duplicate(self):
        """Creating existing host should not duplicate it."""
        config = {
            'hosts': [
                {'name': 'existing-host', 'assets': ['EX-001'], 'redis': False}
            ]
        }
        create_host(config, 'existing-host')

        assert len(config['hosts']) == 1
        # Original assets should be preserved
        assert config['hosts'][0]['assets'] == ['EX-001']

    def test_create_host_existing_updates_redis(self):
        """Creating existing host with redis=True should enable redis."""
        config = {
            'hosts': [
                {'name': 'existing-host', 'assets': ['EX-001'], 'redis': False}
            ]
        }
        create_host(config, 'existing-host', redis=True)

        assert len(config['hosts']) == 1
        assert config['hosts'][0]['redis'] is True

    def test_create_host_initializes_hosts_list(self):
        """Create host should initialize hosts list if missing."""
        config = {}
        create_host(config, 'new-host')

        assert 'hosts' in config
        assert len(config['hosts']) == 1


class TestValidateAssets:
    """Tests for asset validation."""

    def test_missing_host_error(self):
        """Error when host doesn't exist."""
        assets = [
            {'asset_id': 'EX-001', 'type': 'excavator', 'host': 'missing-host', 'make': 'CAT', 'model': '390F'},
        ]
        config = {'assets': [], 'hosts': [{'name': 'other-host'}]}

        errors = validate_assets(assets, config, 'missing-host')

        assert any("Host 'missing-host' not found" in e for e in errors)

    def test_empty_hosts_list_error(self):
        """Error when no hosts configured."""
        assets = [
            {'asset_id': 'EX-001', 'type': 'excavator', 'host': 'any-host', 'make': 'CAT', 'model': '390F'},
        ]
        config = {'assets': [], 'hosts': []}

        errors = validate_assets(assets, config, 'any-host')

        assert any("not found" in e for e in errors)
