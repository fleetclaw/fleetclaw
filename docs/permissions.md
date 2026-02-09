# Permission Model

How FleetClaw uses system users and filesystem ACLs to isolate agents.

## Why system users

Each FleetClaw agent runs as its own system user. This provides:

- **Process isolation** — One agent crashing doesn't affect others
- **Filesystem isolation** — Each agent can only access its own workspace plus explicitly granted paths
- **Auditable access** — `ls -la` and ACL tools show exactly who can read or write what
- **No container overhead** — Native OS security, no Docker daemon required

## User conventions

| Agent | System user | Group |
|-------|-------------|-------|
| Asset agent EX-001 | `fc-ex001` | `fc-agents` |
| Asset agent KOT28 | `fc-kot28` | `fc-agents` |
| Clawvisor | `fc-clawvisor` | `fc-agents` |
| Clawordinator | `fc-clawordinator` | `fc-agents` |

All FleetClaw users belong to the shared `fc-agents` group. User IDs are derived from asset IDs: lowercase, hyphens removed, prefixed with `fc-`.

Users are created as system users with home directories and locked passwords (no interactive login). See `platform/ubuntu.md`, `platform/macos.md`, or `platform/windows.md` for the exact commands per platform.

## ACL rules by agent role

### Asset agent (e.g., fc-ex001)

| Path | Access | Purpose |
|------|--------|---------|
| Own workspace (`~/.openclaw/`) | rwx | Full control of own data |
| Own `outbox/` | rwx | Write fuel logs, meter readings, etc. |
| Own `inbox/` | r-x | Read maintenance acks, directives |
| Own `state.md` | rw- | Read and update operational state |
| `fleet.md` | r-- | Read fleet composition |
| Own skill directories | r-x | Read mounted skills |
| Everything else | --- | No access |

Asset agents cannot read other agents' workspaces, outboxes, or inboxes.

### Clawvisor (fc-clawvisor)

| Path | Access | Purpose |
|------|--------|---------|
| Own workspace (`~/.openclaw/`) | rwx | Full control of own data |
| All asset `outbox/` directories | r-x | Read fuel logs, meters, issues, etc. |
| All asset `inbox/` directories | rwx | Write maintenance acks, alerts |
| All asset `state.md` files | r-- | Read current operational state |
| Clawordinator `inbox/` | -wx | Write escalations (no read needed) |
| `fleet.md` | r-- | Read fleet composition |
| Own skill directories | r-x | Read mounted skills |

Clawvisor can read all asset data and write to asset inboxes (for maintenance acknowledgments) and to Clawordinator's inbox (for escalations).

### Clawordinator (fc-clawordinator)

| Path | Access | Purpose |
|------|--------|---------|
| Own workspace (`~/.openclaw/`) | rwx | Full control of own data |
| Any agent `inbox/` | rwx | Write directives, lifecycle commands |
| `fleet.md` | rw- | Sole writer of fleet composition |
| Own skill directories | r-x | Read mounted skills |
| Scoped sudo | --- | `systemctl` for agent services only |

Clawordinator is the only agent that can modify `fleet.md`. It can write to any agent's inbox for directives.

## Default ACLs

Directories need default ACL entries so that new files created inside them inherit the correct permissions. For example, an asset agent's outbox directory needs a default ACL granting Clawvisor read access, so every new outbox file is automatically readable by Clawvisor without manual permission changes.

See the platform-specific docs for the exact `setfacl` (Linux), `chmod +a` (macOS), or `Set-Acl` (Windows) commands.

## fleet.md ownership

```
Owner:    fc-clawordinator
Group:    fc-agents
Mode:     640 (owner rw, group r, other none)
```

All agents in the `fc-agents` group can read `fleet.md`. Only `fc-clawordinator` can write it. The file lives at a shared location (e.g., `/opt/fleetclaw/fleet.md`) accessible to the group.

## Environment file permissions

Each agent has its own environment file containing secrets (API keys, messaging tokens):

```
Owner:    {agent-user}
Group:    root
Mode:     600 (owner rw only)
```

No other agent can read another agent's env file. See `docs/implementation.md` for env file locations.

## Skills directory permissions

Skills are shared read-only files. The simplest approach:

```
Owner:    root
Group:    fc-agents
Mode:     750 (directories), 640 (files)
```

All agents can read all skill files. OpenClaw's skill discovery and the SOUL.md template determine which skills each agent actually uses — filesystem permissions don't need to enforce per-role skill scoping.

For stricter isolation (Tier 2 concern), use ACLs to restrict which agent users can read which skill directories.

## Clawordinator sudo access

Clawordinator needs to manage agent services (start, stop, restart). This requires scoped sudo access for the service management command:

```
# /etc/sudoers.d/fc-clawordinator (Linux)
fc-clawordinator ALL=(root) NOPASSWD: /usr/bin/systemctl stop fc-agent-*
fc-clawordinator ALL=(root) NOPASSWD: /usr/bin/systemctl start fc-agent-*
fc-clawordinator ALL=(root) NOPASSWD: /usr/bin/systemctl enable fc-agent-*
fc-clawordinator ALL=(root) NOPASSWD: /usr/bin/systemctl disable fc-agent-*
fc-clawordinator ALL=(root) NOPASSWD: /usr/bin/systemctl restart fc-agent-*
```

On macOS, equivalent `launchctl` access. On Windows, NSSM service management. See the platform docs for specifics.

## Auditing

Verify the permission setup with:

```bash
# Check a specific directory's ACLs (Linux)
getfacl /home/fc-ex001/.openclaw/workspace/outbox/

# Verify fleet.md ownership
ls -la /opt/fleetclaw/fleet.md

# Verify env file isolation
ls -la /opt/fleetclaw/env/

# Test that Clawvisor can read an asset outbox
su -s /bin/bash fc-clawvisor -c "ls /home/fc-ex001/.openclaw/workspace/outbox/"

# Test that an asset agent cannot read another agent's workspace
su -s /bin/bash fc-ex001 -c "ls /home/fc-kot28/.openclaw/workspace/"  # Should fail
```
