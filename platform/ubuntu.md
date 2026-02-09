# Ubuntu 24.04 LTS Platform Reference

Platform-specific commands for deploying FleetClaw on Ubuntu. This is the primary supported platform.

## User management

### Create the shared group

```bash
groupadd fc-agents
```

### Create an agent user

```bash
# Asset agent (e.g., EX-001 → fc-ex001)
useradd -r -m -s /bin/bash -G fc-agents fc-ex001

# Lock password (no interactive login)
passwd -l fc-ex001
```

- `-r` — System user (lower UID range)
- `-m` — Create home directory
- `-s /bin/bash` — Shell required for OpenClaw installation
- `-G fc-agents` — Add to shared group

Repeat for each agent: `fc-clawvisor`, `fc-clawordinator`, and each asset agent.

### Run commands as an agent user

```bash
su -s /bin/bash fc-ex001 -c "command here"
```

## Package management

### Node.js (required by OpenClaw)

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install -y nodejs
```

Or use nvm per user for isolated Node.js versions.

### Other dependencies

```bash
apt install -y acl      # For setfacl/getfacl (ACL management)
```

## Process management (systemd)

### Unit file template

Create one unit file per agent at `/etc/systemd/system/fc-agent-{id}.service`:

```ini
[Unit]
Description=FleetClaw Agent {ASSET_ID}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=fc-{id}
Group=fc-agents
WorkingDirectory=/home/fc-{id}/.openclaw
ExecStart=/usr/bin/node /home/fc-{id}/.openclaw/dist/index.js gateway
Restart=on-failure
RestartSec=10
EnvironmentFile=/opt/fleetclaw/env/{id}.env

# Resource limits
MemoryMax=512M
CPUQuota=25%

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=/home/fc-{id}/.openclaw
ReadOnlyPaths=/opt/fleetclaw/skills /opt/fleetclaw/fleet.md

[Install]
WantedBy=multi-user.target
```

For Clawvisor and Clawordinator, adjust `MemoryMax` to `1G` and add appropriate `ReadWritePaths` for inbox access to other agents (see `docs/permissions.md`).

### Service commands

```bash
# Enable and start
systemctl enable fc-agent-ex001
systemctl start fc-agent-ex001

# Check status
systemctl status fc-agent-ex001

# View logs
journalctl -u fc-agent-ex001 -f

# Stop / restart
systemctl stop fc-agent-ex001
systemctl restart fc-agent-ex001

# Disable (decommission)
systemctl disable fc-agent-ex001
```

### Reload after unit file changes

```bash
systemctl daemon-reload
```

## File permissions (POSIX ACLs)

### Install ACL tools

```bash
apt install -y acl
```

### Set ACLs on asset outbox (Clawvisor read access)

```bash
# Grant Clawvisor read+execute on existing files
setfacl -R -m u:fc-clawvisor:rx /home/fc-ex001/.openclaw/workspace/outbox/

# Set default ACL so new files inherit the grant
setfacl -R -d -m u:fc-clawvisor:rx /home/fc-ex001/.openclaw/workspace/outbox/
```

### Set ACLs on asset inbox (Clawvisor write access)

```bash
setfacl -R -m u:fc-clawvisor:rwx /home/fc-ex001/.openclaw/workspace/inbox/
setfacl -R -d -m u:fc-clawvisor:rwx /home/fc-ex001/.openclaw/workspace/inbox/

# Clawordinator can also write to any inbox
setfacl -R -m u:fc-clawordinator:rwx /home/fc-ex001/.openclaw/workspace/inbox/
setfacl -R -d -m u:fc-clawordinator:rwx /home/fc-ex001/.openclaw/workspace/inbox/
```

### Set ACLs on asset state.md (Clawvisor read access)

```bash
setfacl -m u:fc-clawvisor:r /home/fc-ex001/.openclaw/workspace/state.md
```

### Set ACLs on Clawordinator inbox (Clawvisor write access for escalations)

```bash
setfacl -R -m u:fc-clawvisor:rwx /home/fc-clawordinator/.openclaw/workspace/inbox/
setfacl -R -d -m u:fc-clawvisor:rwx /home/fc-clawordinator/.openclaw/workspace/inbox/
```

### Verify ACLs

```bash
getfacl /home/fc-ex001/.openclaw/workspace/outbox/
```

## fleet.md setup

```bash
mkdir -p /opt/fleetclaw
touch /opt/fleetclaw/fleet.md
chown fc-clawordinator:fc-agents /opt/fleetclaw/fleet.md
chmod 640 /opt/fleetclaw/fleet.md
```

## Skills directory setup

```bash
# Copy skills from the FleetClaw repo
cp -r /path/to/fleetclaw/skills /opt/fleetclaw/skills

chown -R root:fc-agents /opt/fleetclaw/skills
chmod -R 750 /opt/fleetclaw/skills
find /opt/fleetclaw/skills -type f -exec chmod 640 {} \;
```

## Environment files

```bash
mkdir -p /opt/fleetclaw/env

# Create per-agent env file
cat > /opt/fleetclaw/env/ex001.env << 'EOF'
FIREWORKS_API_KEY=your-key-here
TELEGRAM_BOT_TOKEN=your-token-here
FLEET_MD_PATH=/opt/fleetclaw/fleet.md
EOF

chown fc-ex001:root /opt/fleetclaw/env/ex001.env
chmod 600 /opt/fleetclaw/env/ex001.env
```

## Firewall

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw enable
```

No inbound ports needed for FleetClaw agents — they connect outbound to messaging APIs and LLM providers.

## Log management

Systemd journals handle log rotation by default. For additional control:

```bash
# /etc/systemd/journald.conf
SystemMaxUse=500M
MaxFileSec=1week
```

```bash
systemctl restart systemd-journald
```

## Kernel tuning

OpenClaw uses inotify for file watching. For fleets with many agents:

```bash
echo "fs.inotify.max_user_instances=8192" >> /etc/sysctl.conf
echo "fs.inotify.max_user_watches=524288" >> /etc/sysctl.conf
sysctl -p
```

## Host sizing

| Fleet size | RAM | CPU | Disk |
|-----------|-----|-----|------|
| 10 assets | 8 GB | 4 cores | 50 GB SSD |
| 50 assets | 16 GB | 8 cores | 100 GB SSD |
| 100 assets | 32 GB | 16 cores | 200 GB SSD |
