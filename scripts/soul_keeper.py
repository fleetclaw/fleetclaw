#!/usr/bin/env python3
"""
Soul Keeper - Git-backed state persistence for Fleetclaw workspaces.

Provides automated Git operations to persist learned state in SOUL.md files,
protecting against disk failures and enabling state recovery.

Usage:
    soul-keeper init --workspace /workspaces/EX-001 [--remote git@...]
    soul-keeper commit --workspace /workspaces/EX-001 [--message "..."]
    soul-keeper rollback --workspace /workspaces/EX-001 --commit abc123
    soul-keeper status --workspace /workspaces/EX-001
    soul-keeper auto-commit  # Run from cron for automated backups
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def run_git(workspace: Path, *args, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command in the workspace directory."""
    cmd = ['git', '-C', str(workspace)] + list(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"Git command failed: {result.stderr}")
    return result


def is_git_repo(workspace: Path) -> bool:
    """Check if workspace is a git repository."""
    return (workspace / '.git').is_dir()


def get_current_commit(workspace: Path) -> Optional[str]:
    """Get the current commit hash."""
    try:
        result = run_git(workspace, 'rev-parse', 'HEAD', check=False)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def has_changes(workspace: Path) -> bool:
    """Check if there are uncommitted changes."""
    result = run_git(workspace, 'status', '--porcelain', check=False)
    return bool(result.stdout.strip())


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize git repository in workspace."""
    workspace = Path(args.workspace)

    if not workspace.exists():
        print(json.dumps({'error': f'Workspace not found: {workspace}', 'success': False}))
        return 1

    if is_git_repo(workspace):
        print(json.dumps({
            'success': True,
            'message': 'Repository already initialized',
            'current_commit': get_current_commit(workspace)
        }))
        return 0

    try:
        # Initialize repository
        run_git(workspace, 'init')

        # Create .gitignore for workspace
        gitignore_path = workspace / '.gitignore'
        gitignore_content = """# Soul Keeper - Workspace .gitignore

# Temporary files
*.tmp
*.bak
*.swp

# Buffer files (transient state)
buffer/outgoing_queue.json
buffer/connection_state.json

# Log files (too large, use Loki instead)
logs/*.log

# Keep directory structure
!logs/.gitkeep
!buffer/.gitkeep

# Memory files older than 30 days are typically pruned
# memory/*.md files ARE tracked (daily logs)
"""
        gitignore_path.write_text(gitignore_content)

        # Initial commit
        run_git(workspace, 'add', '.')
        run_git(workspace, 'commit', '-m', 'Initial workspace state')

        # Add remote if specified
        if args.remote:
            run_git(workspace, 'remote', 'add', 'origin', args.remote)
            print(json.dumps({
                'success': True,
                'message': 'Repository initialized with remote',
                'remote': args.remote,
                'current_commit': get_current_commit(workspace)
            }))
        else:
            print(json.dumps({
                'success': True,
                'message': 'Repository initialized (no remote)',
                'current_commit': get_current_commit(workspace)
            }))

        return 0

    except Exception as e:
        print(json.dumps({'error': str(e), 'success': False}))
        return 1


def cmd_commit(args: argparse.Namespace) -> int:
    """Commit current workspace state."""
    workspace = Path(args.workspace)

    if not workspace.exists():
        print(json.dumps({'error': f'Workspace not found: {workspace}', 'success': False}))
        return 1

    if not is_git_repo(workspace):
        print(json.dumps({
            'error': 'Workspace is not a git repository. Run init first.',
            'success': False
        }))
        return 1

    try:
        # Check for changes
        if not has_changes(workspace):
            print(json.dumps({
                'success': True,
                'message': 'No changes to commit',
                'current_commit': get_current_commit(workspace)
            }))
            return 0

        # Stage all changes
        run_git(workspace, 'add', '.')

        # Generate commit message
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        if args.message:
            message = args.message
        else:
            # Auto-generate message based on changed files
            result = run_git(workspace, 'diff', '--cached', '--name-only')
            changed_files = result.stdout.strip().split('\n')

            if 'SOUL.md' in changed_files:
                message = f"State update: SOUL.md modified ({timestamp})"
            elif any('memory/' in f for f in changed_files):
                message = f"Memory update: Daily log ({timestamp})"
            else:
                message = f"Workspace state update ({timestamp})"

        # Commit
        run_git(workspace, 'commit', '-m', message)

        # Push if remote exists
        pushed = False
        result = run_git(workspace, 'remote', check=False)
        if result.stdout.strip():
            try:
                run_git(workspace, 'push', '-u', 'origin', 'HEAD', check=False)
                pushed = True
            except Exception:
                pass

        print(json.dumps({
            'success': True,
            'message': 'Changes committed',
            'commit_message': message,
            'current_commit': get_current_commit(workspace),
            'pushed': pushed,
            'timestamp': datetime.now(timezone.utc).isoformat() + 'Z'
        }))
        return 0

    except Exception as e:
        print(json.dumps({'error': str(e), 'success': False}))
        return 1


def cmd_rollback(args: argparse.Namespace) -> int:
    """Rollback to a previous commit."""
    workspace = Path(args.workspace)

    if not workspace.exists():
        print(json.dumps({'error': f'Workspace not found: {workspace}', 'success': False}))
        return 1

    if not is_git_repo(workspace):
        print(json.dumps({
            'error': 'Workspace is not a git repository',
            'success': False
        }))
        return 1

    try:
        current_commit = get_current_commit(workspace)

        # Verify target commit exists
        result = run_git(workspace, 'cat-file', '-t', args.commit, check=False)
        if result.returncode != 0:
            print(json.dumps({
                'error': f'Commit not found: {args.commit}',
                'success': False
            }))
            return 1

        # Create backup branch
        backup_branch = f"backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        run_git(workspace, 'branch', backup_branch)

        # Reset to target commit
        run_git(workspace, 'reset', '--hard', args.commit)

        print(json.dumps({
            'success': True,
            'message': f'Rolled back to {args.commit}',
            'previous_commit': current_commit,
            'current_commit': args.commit,
            'backup_branch': backup_branch
        }))
        return 0

    except Exception as e:
        print(json.dumps({'error': str(e), 'success': False}))
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Show workspace git status."""
    workspace = Path(args.workspace)

    if not workspace.exists():
        print(json.dumps({'error': f'Workspace not found: {workspace}', 'success': False}))
        return 1

    if not is_git_repo(workspace):
        print(json.dumps({
            'success': True,
            'is_repo': False,
            'message': 'Workspace is not a git repository'
        }))
        return 0

    try:
        # Get current status
        result = run_git(workspace, 'status', '--porcelain')
        changes = result.stdout.strip().split('\n') if result.stdout.strip() else []

        # Get current commit
        current_commit = get_current_commit(workspace)

        # Get remote info
        result = run_git(workspace, 'remote', '-v', check=False)
        remotes = result.stdout.strip().split('\n') if result.stdout.strip() else []

        # Get recent commits
        result = run_git(workspace, 'log', '--oneline', '-5', check=False)
        recent_commits = result.stdout.strip().split('\n') if result.stdout.strip() else []

        print(json.dumps({
            'success': True,
            'is_repo': True,
            'current_commit': current_commit,
            'has_changes': len(changes) > 0,
            'changed_files': changes,
            'remotes': remotes,
            'recent_commits': recent_commits
        }))
        return 0

    except Exception as e:
        print(json.dumps({'error': str(e), 'success': False}))
        return 1


def cmd_auto_commit(args: argparse.Namespace) -> int:
    """Auto-commit all workspaces (for cron job)."""
    workspaces_dir = Path(args.workspaces_dir)

    if not workspaces_dir.exists():
        print(json.dumps({'error': f'Workspaces directory not found: {workspaces_dir}', 'success': False}))
        return 1

    results = []
    for workspace in workspaces_dir.iterdir():
        if not workspace.is_dir():
            continue

        if not is_git_repo(workspace):
            results.append({
                'workspace': workspace.name,
                'status': 'skipped',
                'reason': 'not a git repo'
            })
            continue

        try:
            if has_changes(workspace):
                # Stage and commit
                run_git(workspace, 'add', '.')
                timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
                run_git(workspace, 'commit', '-m', f"Auto-commit: State backup ({timestamp})")

                # Try to push
                pushed = False
                result = run_git(workspace, 'remote', check=False)
                if result.stdout.strip():
                    try:
                        run_git(workspace, 'push', check=False)
                        pushed = True
                    except Exception:
                        pass

                results.append({
                    'workspace': workspace.name,
                    'status': 'committed',
                    'pushed': pushed,
                    'commit': get_current_commit(workspace)
                })
            else:
                results.append({
                    'workspace': workspace.name,
                    'status': 'no_changes'
                })

        except Exception as e:
            results.append({
                'workspace': workspace.name,
                'status': 'error',
                'error': str(e)
            })

    committed = sum(1 for r in results if r.get('status') == 'committed')
    print(json.dumps({
        'success': True,
        'total_workspaces': len(results),
        'committed': committed,
        'results': results,
        'timestamp': datetime.now(timezone.utc).isoformat() + 'Z'
    }))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Soul Keeper - Git-backed state persistence for Fleetclaw',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  soul-keeper init --workspace /workspaces/EX-001 --remote git@github.com:org/fleet-state.git
  soul-keeper commit --workspace /workspaces/EX-001
  soul-keeper rollback --workspace /workspaces/EX-001 --commit abc123
  soul-keeper status --workspace /workspaces/EX-001
  soul-keeper auto-commit --workspaces-dir /generated/workspaces
        """
    )

    subparsers = parser.add_subparsers(dest='command', required=True)

    # init command
    init_parser = subparsers.add_parser('init', help='Initialize git repository')
    init_parser.add_argument('--workspace', required=True, help='Path to workspace directory')
    init_parser.add_argument('--remote', help='Remote repository URL')

    # commit command
    commit_parser = subparsers.add_parser('commit', help='Commit current state')
    commit_parser.add_argument('--workspace', required=True, help='Path to workspace directory')
    commit_parser.add_argument('--message', '-m', help='Commit message')

    # rollback command
    rollback_parser = subparsers.add_parser('rollback', help='Rollback to previous commit')
    rollback_parser.add_argument('--workspace', required=True, help='Path to workspace directory')
    rollback_parser.add_argument('--commit', required=True, help='Target commit hash')

    # status command
    status_parser = subparsers.add_parser('status', help='Show workspace status')
    status_parser.add_argument('--workspace', required=True, help='Path to workspace directory')

    # auto-commit command
    auto_parser = subparsers.add_parser('auto-commit', help='Auto-commit all workspaces')
    auto_parser.add_argument('--workspaces-dir', default='/generated/workspaces',
                            help='Directory containing all workspaces')

    args = parser.parse_args()

    commands = {
        'init': cmd_init,
        'commit': cmd_commit,
        'rollback': cmd_rollback,
        'status': cmd_status,
        'auto-commit': cmd_auto_commit,
    }

    return commands[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
