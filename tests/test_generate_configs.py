"""Tests for generate-configs.py script."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add scripts directory to path for imports
SCRIPTS_DIR = Path(__file__).parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

# Mock models module to avoid circular import
# models.py imports generate-configs to get ASSET_TYPE_METADATA, causing circular import
mock_models = MagicMock()
mock_models.validate_fleet_config = MagicMock()
sys.modules['models'] = mock_models

# Import after path setup and mocking
from importlib import import_module
generate_configs = import_module('generate-configs')

copy_asset_to_compose = generate_configs.copy_asset_to_compose
generate_env_template = generate_configs.generate_env_template
copy_directory_to_compose = generate_configs.copy_directory_to_compose
copy_to_compose_dir = generate_configs.copy_to_compose_dir
copy_skills_to_compose_dir = generate_configs.copy_skills_to_compose_dir
copy_dockerfile_to_compose = generate_configs.copy_dockerfile_to_compose
set_ownership_for_container = generate_configs.set_ownership_for_container
load_env_file = generate_configs.load_env_file
check_compose_permissions = generate_configs.check_compose_permissions
warn_permission_issues = generate_configs.warn_permission_issues


class TestLoadEnvFile:
    """Tests for load_env_file function."""

    def test_parses_key_value_pairs(self, tmp_path):
        """Parses simple key=value pairs."""
        env_file = tmp_path / '.env'
        env_file.write_text('FOO=bar\nBAZ=qux\n')

        result = load_env_file(env_file)

        assert result == {'FOO': 'bar', 'BAZ': 'qux'}

    def test_ignores_comments_and_empty_lines(self, tmp_path):
        """Ignores lines starting with # and empty lines."""
        env_file = tmp_path / '.env'
        env_file.write_text('# This is a comment\nFOO=bar\n\n# Another comment\nBAZ=qux\n')

        result = load_env_file(env_file)

        assert result == {'FOO': 'bar', 'BAZ': 'qux'}

    def test_handles_values_with_equals_sign(self, tmp_path):
        """Handles values containing = character."""
        env_file = tmp_path / '.env'
        env_file.write_text('CONNECTION_STRING=host=localhost;port=5432\n')

        result = load_env_file(env_file)

        assert result == {'CONNECTION_STRING': 'host=localhost;port=5432'}

    def test_strips_surrounding_double_quotes(self, tmp_path):
        """Strips surrounding double quotes from values."""
        env_file = tmp_path / '.env'
        env_file.write_text('SUPERVISOR_ID="12345"\nNAME="John Doe"\n')

        result = load_env_file(env_file)

        assert result == {'SUPERVISOR_ID': '12345', 'NAME': 'John Doe'}

    def test_strips_surrounding_single_quotes(self, tmp_path):
        """Strips surrounding single quotes from values."""
        env_file = tmp_path / '.env'
        env_file.write_text("API_KEY='secret123'\n")

        result = load_env_file(env_file)

        assert result == {'API_KEY': 'secret123'}

    def test_preserves_internal_quotes(self, tmp_path):
        """Preserves quotes that are not surrounding the value."""
        env_file = tmp_path / '.env'
        env_file.write_text('MESSAGE=He said "hello"\n')

        result = load_env_file(env_file)

        assert result == {'MESSAGE': 'He said "hello"'}

    def test_returns_empty_dict_for_nonexistent_file(self, tmp_path):
        """Returns empty dict if file doesn't exist."""
        env_file = tmp_path / '.env'

        result = load_env_file(env_file)

        assert result == {}

    def test_strips_whitespace_from_keys_and_values(self, tmp_path):
        """Strips whitespace from keys and values."""
        env_file = tmp_path / '.env'
        env_file.write_text('  FOO  =  bar  \n')

        result = load_env_file(env_file)

        assert result == {'FOO': 'bar'}


class TestCopyToComposeDir:
    """Tests for copy_to_compose_dir function."""

    def test_copy_workspace_creates_directory(self, tmp_path):
        """Copies workspace to compose directory."""
        # Setup source workspace
        workspaces_dir = tmp_path / 'workspaces'
        workspaces_dir.mkdir()
        src_workspace = workspaces_dir / 'EX-001'
        src_workspace.mkdir()
        (src_workspace / 'SOUL.md').write_text('# Test SOUL')
        (src_workspace / 'memory').mkdir()
        (src_workspace / 'memory' / '2024-01-15.md').write_text('# Daily log')

        # Setup compose directory
        compose_dir = tmp_path / 'compose'
        compose_dir.mkdir()
        (compose_dir / 'workspaces').mkdir()

        # Execute
        copy_to_compose_dir(workspaces_dir, compose_dir, 'EX-001')

        # Verify
        dest_workspace = compose_dir / 'workspaces' / 'EX-001'
        assert dest_workspace.exists()
        assert (dest_workspace / 'SOUL.md').read_text() == '# Test SOUL'
        assert (dest_workspace / 'memory' / '2024-01-15.md').exists()

    def test_copy_workspace_overwrites_existing(self, tmp_path):
        """Overwrites existing workspace in compose directory."""
        # Setup source workspace
        workspaces_dir = tmp_path / 'workspaces'
        workspaces_dir.mkdir()
        src_workspace = workspaces_dir / 'EX-001'
        src_workspace.mkdir()
        (src_workspace / 'SOUL.md').write_text('# Updated SOUL')

        # Setup compose directory with existing workspace
        compose_dir = tmp_path / 'compose'
        (compose_dir / 'workspaces' / 'EX-001').mkdir(parents=True)
        (compose_dir / 'workspaces' / 'EX-001' / 'SOUL.md').write_text('# Old SOUL')
        (compose_dir / 'workspaces' / 'EX-001' / 'old_file.txt').write_text('old')

        # Execute
        copy_to_compose_dir(workspaces_dir, compose_dir, 'EX-001')

        # Verify old file is gone, new content is present
        dest_workspace = compose_dir / 'workspaces' / 'EX-001'
        assert (dest_workspace / 'SOUL.md').read_text() == '# Updated SOUL'
        assert not (dest_workspace / 'old_file.txt').exists()


class TestCopySkillsToComposeDir:
    """Tests for copy_skills_to_compose_dir function."""

    def test_copy_skills_creates_directory(self, tmp_path):
        """Copies skills directory to compose directory."""
        # Setup source skills
        skills_dir = tmp_path / 'skills'
        skills_dir.mkdir()
        (skills_dir / 'fleet-comms').mkdir()
        (skills_dir / 'fleet-comms' / 'SKILL.md').write_text('# Fleet Comms')
        (skills_dir / 'fuel-log-validator').mkdir()
        (skills_dir / 'fuel-log-validator' / 'SKILL.md').write_text('# Fuel Log')

        # Setup compose directory
        compose_dir = tmp_path / 'compose'
        compose_dir.mkdir()

        # Execute
        copy_skills_to_compose_dir(skills_dir, compose_dir)

        # Verify
        dest_skills = compose_dir / 'skills'
        assert dest_skills.exists()
        assert (dest_skills / 'fleet-comms' / 'SKILL.md').read_text() == '# Fleet Comms'
        assert (dest_skills / 'fuel-log-validator' / 'SKILL.md').read_text() == '# Fuel Log'

    def test_copy_skills_overwrites_existing(self, tmp_path):
        """Overwrites existing skills in compose directory."""
        # Setup source skills
        skills_dir = tmp_path / 'skills'
        skills_dir.mkdir()
        (skills_dir / 'fleet-comms').mkdir()
        (skills_dir / 'fleet-comms' / 'SKILL.md').write_text('# Updated Fleet Comms')

        # Setup compose directory with existing skills
        compose_dir = tmp_path / 'compose'
        (compose_dir / 'skills' / 'fleet-comms').mkdir(parents=True)
        (compose_dir / 'skills' / 'fleet-comms' / 'SKILL.md').write_text('# Old')
        (compose_dir / 'skills' / 'old-skill').mkdir()

        # Execute
        copy_skills_to_compose_dir(skills_dir, compose_dir)

        # Verify old skill directory is gone
        dest_skills = compose_dir / 'skills'
        assert (dest_skills / 'fleet-comms' / 'SKILL.md').read_text() == '# Updated Fleet Comms'
        assert not (dest_skills / 'old-skill').exists()


class TestCopyDockerfileToCompose:
    """Tests for copy_dockerfile_to_compose function."""

    def test_copy_dockerfile_creates_directory(self, tmp_path):
        """Copies Dockerfile directory to compose directory."""
        # Setup source docker directory
        repo_root = tmp_path / 'repo'
        docker_dir = repo_root / 'docker' / 'openclaw'
        docker_dir.mkdir(parents=True)
        (docker_dir / 'Dockerfile').write_text('FROM ghcr.io/openclaw/openclaw:2026.2.6\n')

        # Setup compose directory
        compose_dir = tmp_path / 'compose'
        compose_dir.mkdir()

        # Execute
        copy_dockerfile_to_compose(repo_root, compose_dir)

        # Verify
        dest_docker = compose_dir / 'docker' / 'openclaw'
        assert dest_docker.exists()
        assert (dest_docker / 'Dockerfile').read_text() == 'FROM ghcr.io/openclaw/openclaw:2026.2.6\n'

    def test_copy_dockerfile_skips_when_source_missing(self, tmp_path):
        """Does nothing if source docker directory doesn't exist."""
        repo_root = tmp_path / 'repo'
        repo_root.mkdir()
        # No docker/openclaw directory

        compose_dir = tmp_path / 'compose'
        compose_dir.mkdir()

        # Execute - should not raise
        copy_dockerfile_to_compose(repo_root, compose_dir)

        # Verify no docker directory created
        assert not (compose_dir / 'docker').exists()


class TestCopyAssetToCompose:
    """Tests for copy_asset_to_compose function."""

    def test_copies_workspace_and_config(self, tmp_path):
        """Copies workspace and openclaw config to data directory."""
        # Setup source workspace
        workspaces_dir = tmp_path / 'workspaces'
        workspaces_dir.mkdir()
        src_workspace = workspaces_dir / 'EX-001'
        src_workspace.mkdir()
        (src_workspace / 'SOUL.md').write_text('# Test SOUL')

        # Setup source config
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        (config_dir / 'openclaw-ex-001.json').write_text('{"test": true}')

        # Setup compose directory
        compose_dir = tmp_path / 'compose'
        (compose_dir / 'workspaces').mkdir(parents=True)
        (compose_dir / 'data').mkdir(parents=True)

        # Execute
        copy_asset_to_compose('EX-001', workspaces_dir, config_dir, compose_dir)

        # Verify workspace copied
        dest_workspace = compose_dir / 'workspaces' / 'EX-001'
        assert dest_workspace.exists()
        assert (dest_workspace / 'SOUL.md').read_text() == '# Test SOUL'

        # Verify config copied to data directory as openclaw.json
        dest_data = compose_dir / 'data' / 'EX-001'
        assert dest_data.exists()
        assert (dest_data / 'openclaw.json').read_text() == '{"test": true}'

    def test_handles_fleet_coord_id(self, tmp_path):
        """Handles FLEET-COORD asset ID correctly."""
        # Setup source workspace
        workspaces_dir = tmp_path / 'workspaces'
        workspaces_dir.mkdir()
        src_workspace = workspaces_dir / 'FLEET-COORD'
        src_workspace.mkdir()
        (src_workspace / 'SOUL.md').write_text('# FC SOUL')

        # Setup source config
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        (config_dir / 'openclaw-fleet-coord.json').write_text('{"fc": true}')

        # Setup compose directory
        compose_dir = tmp_path / 'compose'
        (compose_dir / 'workspaces').mkdir(parents=True)
        (compose_dir / 'data').mkdir(parents=True)

        # Execute
        copy_asset_to_compose('FLEET-COORD', workspaces_dir, config_dir, compose_dir)

        # Verify
        assert (compose_dir / 'workspaces' / 'FLEET-COORD' / 'SOUL.md').exists()
        assert (compose_dir / 'data' / 'FLEET-COORD' / 'openclaw.json').exists()


class TestCopyDirectoryToCompose:
    """Tests for copy_directory_to_compose function."""

    def test_copies_directory(self, tmp_path):
        """Copies directory to destination."""
        src = tmp_path / 'src'
        src.mkdir()
        (src / 'file.txt').write_text('content')
        (src / 'subdir').mkdir()
        (src / 'subdir' / 'nested.txt').write_text('nested')

        dest = tmp_path / 'dest'

        copy_directory_to_compose(src, dest)

        assert dest.exists()
        assert (dest / 'file.txt').read_text() == 'content'
        assert (dest / 'subdir' / 'nested.txt').read_text() == 'nested'

    def test_replaces_existing_directory(self, tmp_path):
        """Replaces existing directory at destination."""
        src = tmp_path / 'src'
        src.mkdir()
        (src / 'new.txt').write_text('new')

        dest = tmp_path / 'dest'
        dest.mkdir()
        (dest / 'old.txt').write_text('old')

        copy_directory_to_compose(src, dest)

        assert (dest / 'new.txt').read_text() == 'new'
        assert not (dest / 'old.txt').exists()


class TestSetOwnershipForContainer:
    """Tests for set_ownership_for_container function."""

    def test_windows_skips_chown(self, tmp_path, monkeypatch):
        """On Windows, function returns without error."""
        monkeypatch.setattr('platform.system', lambda: 'Windows')

        test_dir = tmp_path / 'test'
        test_dir.mkdir()
        (test_dir / 'file.txt').write_text('test')

        # Should not raise, even though chown doesn't exist on Windows
        set_ownership_for_container(test_dir)

    @pytest.mark.skipif(sys.platform == 'win32', reason="os.chown not available on Windows")
    def test_permission_error_handled(self, tmp_path, monkeypatch):
        """PermissionError is caught when running without root."""
        import os as os_module

        test_dir = tmp_path / 'test'
        test_dir.mkdir()
        (test_dir / 'file.txt').write_text('test')

        # Mock os.chown to raise PermissionError
        original_chown = os_module.chown

        def mock_chown(path, uid, gid):
            raise PermissionError("Operation not permitted")

        monkeypatch.setattr(os_module, 'chown', mock_chown)

        # Should not raise
        set_ownership_for_container(test_dir)


class TestGenerateEnvTemplateDryRun:
    """Tests for generate_env_template dry-run mode."""

    @pytest.fixture
    def base_config(self):
        """Base config with fleet and coordinator settings."""
        return {
            'fleet': {'site': 'Test Site', 'timezone': 'UTC'},
            'coordinator': {'shift_start': '06:00', 'shift_end': '18:00'},
            'assets': [],
        }

    def test_dry_run_shows_preview_but_does_not_write_file(self, capsys, tmp_path, base_config):
        """Dry-run mode shows preview but does not write file."""
        base_config['assets'] = [
            {'asset_id': 'EX-001', 'type': 'excavator'},
            {'asset_id': 'EX-002', 'type': 'excavator'},
        ]
        output_path = tmp_path / '.env.template'

        generate_env_template(base_config, output_path, dry_run=True)

        captured = capsys.readouterr()
        assert "Would generate .env.template" in captured.out
        assert "FLEET-COORD" in captured.out
        assert "Excavators (2)" in captured.out
        assert "EX-001" in captured.out
        assert "EX-002" in captured.out
        assert "Total: 3 Telegram token placeholders" in captured.out
        assert not output_path.exists()

    def test_dry_run_with_multiple_asset_types(self, capsys, tmp_path, base_config):
        """Dry-run mode shows multiple asset types."""
        base_config['assets'] = [
            {'asset_id': 'EX-001', 'type': 'excavator'},
            {'asset_id': 'WL-001', 'type': 'wheel_loader'},
            {'asset_id': 'WL-002', 'type': 'wheel_loader'},
        ]
        output_path = tmp_path / '.env.template'

        generate_env_template(base_config, output_path, dry_run=True)

        captured = capsys.readouterr()
        assert "Excavator (1)" in captured.out
        assert "Wheel Loaders (2)" in captured.out
        assert "Total: 4 Telegram token placeholders" in captured.out
        assert not output_path.exists()

    def test_normal_mode_writes_file(self, tmp_path, base_config):
        """Normal mode writes file to disk."""
        base_config['assets'] = [{'asset_id': 'EX-001', 'type': 'excavator'}]
        output_path = tmp_path / '.env.template'

        generate_env_template(base_config, output_path, dry_run=False)

        assert output_path.exists()
        content = output_path.read_text()
        assert "TELEGRAM_TOKEN_EX_001" in content
        assert "TELEGRAM_TOKEN_FLEET_COORD" in content


class TestCheckComposePermissions:
    """Tests for check_compose_permissions function."""

    def test_windows_skips_check(self, tmp_path, monkeypatch):
        """Returns empty list on Windows."""
        monkeypatch.setattr('platform.system', lambda: 'Windows')

        compose_dir = tmp_path / 'compose'
        compose_dir.mkdir()
        (compose_dir / 'workspaces').mkdir()

        result = check_compose_permissions(compose_dir)

        assert result == []

    def test_nonexistent_dir_returns_empty(self, tmp_path, monkeypatch):
        """Returns empty list if compose directory doesn't exist."""
        monkeypatch.setattr('platform.system', lambda: 'Linux')

        compose_dir = tmp_path / 'compose'
        # Don't create the directory

        result = check_compose_permissions(compose_dir)

        assert result == []

    def test_writable_dir_returns_empty(self, tmp_path, monkeypatch):
        """Returns empty list if directories are writable."""
        monkeypatch.setattr('platform.system', lambda: 'Linux')

        compose_dir = tmp_path / 'compose'
        compose_dir.mkdir()
        (compose_dir / 'workspaces').mkdir()
        (compose_dir / 'data').mkdir()

        result = check_compose_permissions(compose_dir)

        assert result == []

    @pytest.mark.skipif(sys.platform == 'win32', reason="stat().st_uid not available on Windows")
    def test_detects_uid_1000_files(self, tmp_path, monkeypatch):
        """Detects files owned by uid 1000 that are not writable."""
        import os as os_module

        monkeypatch.setattr('platform.system', lambda: 'Linux')

        compose_dir = tmp_path / 'compose'
        compose_dir.mkdir()
        workspaces_dir = compose_dir / 'workspaces'
        workspaces_dir.mkdir()

        # Create a test file
        test_asset = workspaces_dir / 'EX-001'
        test_asset.mkdir()

        # Mock stat to return uid 1000
        original_stat = Path.stat

        def mock_stat(self):
            result = original_stat(self)
            # Create a mock stat result with st_uid = 1000
            class MockStat:
                def __init__(self, real_stat):
                    for attr in dir(real_stat):
                        if not attr.startswith('_'):
                            setattr(self, attr, getattr(real_stat, attr))
                    self.st_uid = 1000
            return MockStat(result)

        monkeypatch.setattr(Path, 'stat', mock_stat)

        # Mock os.access to return False (not writable)
        monkeypatch.setattr(os_module, 'access', lambda path, mode: False)

        result = check_compose_permissions(compose_dir)

        # Should detect the workspaces directory as problematic
        assert len(result) > 0
        assert any('workspaces' in str(p) for p in result)


class TestWarnPermissionIssues:
    """Tests for warn_permission_issues function."""

    def test_prints_warning_message(self, capsys, tmp_path):
        """Prints warning message with fix instructions."""
        compose_dir = tmp_path / 'compose'
        problem_paths = [
            compose_dir / 'workspaces' / 'EX-001',
            compose_dir / 'data' / 'EX-001',
        ]

        warn_permission_issues(compose_dir, problem_paths)

        captured = capsys.readouterr()
        assert "Warning: Permission issues detected" in captured.out
        assert "uid 1000" in captured.out
        assert "Affected paths:" in captured.out
        assert "EX-001" in captured.out
        assert "sudo chown" in captured.out
        assert "--skip-copy" in captured.out
        assert "--no-permission-check" in captured.out

    def test_truncates_long_path_list(self, capsys, tmp_path):
        """Truncates path list if more than 3 paths."""
        compose_dir = tmp_path / 'compose'
        problem_paths = [
            compose_dir / 'workspaces' / 'EX-001',
            compose_dir / 'workspaces' / 'EX-002',
            compose_dir / 'workspaces' / 'EX-003',
            compose_dir / 'workspaces' / 'EX-004',
            compose_dir / 'workspaces' / 'EX-005',
        ]

        warn_permission_issues(compose_dir, problem_paths)

        captured = capsys.readouterr()
        assert "EX-001" in captured.out
        assert "EX-002" in captured.out
        assert "EX-003" in captured.out
        assert "EX-004" not in captured.out
        assert "... and 2 more" in captured.out
