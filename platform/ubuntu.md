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

# For CLI commands that need env vars (e.g., openclaw pairing, channels):
sudo su -s /bin/bash fc-ex001 -c "source /opt/fleetclaw/env/ex001.env && openclaw <command>"
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
ExecStart=/usr/bin/openclaw gateway --force
Restart=on-failure
RestartSec=10
EnvironmentFile=/opt/fleetclaw/env/{id}.env

# Resource limits — use 1536M for Clawvisor/Clawordinator
MemoryMax=1G
CPUQuota=25%

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
PrivateTmp=no
ReadWritePaths=/home/fc-{id}/.openclaw /tmp
ReadOnlyPaths=/opt/fleetclaw/skills /opt/fleetclaw/fleet.md

[Install]
WantedBy=multi-user.target
```

For Clawvisor and Clawordinator, set `MemoryMax=1536M` and add appropriate `ReadWritePaths` for inbox access to other agents (see `docs/permissions.md`).

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

### Upgrading OpenClaw

```bash
# 1. Stop all agent services
sudo systemctl stop fc-agent-*

# 2. Verify all stopped
systemctl is-active fc-agent-* 2>&1 | grep -v inactive
# (no output = all stopped)

# 3. Update global package
sudo npm install -g openclaw@<version>

# 4. Verify version
openclaw --version

# 5. Start all agent services
sudo systemctl start fc-agent-*

# 6. Verify all running (wait ~30s for startup)
systemctl is-active fc-agent-*
```

The `fc-agent-*` wildcard works with systemctl. For selective upgrades (if agents are split across hosts), list specific service names instead.

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

### Set ACLs on asset AGENTS.md (Clawvisor read access)

```bash
setfacl -m u:fc-clawvisor:r /home/fc-ex001/.openclaw/workspace/AGENTS.md
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
NODE_OPTIONS=--max-old-space-size=768
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

## Outbox archival

A nightly cron job archives outbox files older than 30 days and compresses month directories older than 90 days. See `docs/scheduling.md` for the archival model.

### Create the archival script

```bash
mkdir -p /opt/fleetclaw/scripts
cat > /opt/fleetclaw/scripts/archive-outboxes.sh << 'SCRIPT'
#!/bin/bash
# FleetClaw outbox archival — runs nightly via cron
# Archives outbox files older than RETENTION_DAYS, compresses months older than 90 days

RETENTION_DAYS=${FC_RETENTION_DAYS:-30}

for home in /home/fc-*; do
  outbox="$home/.openclaw/workspace/outbox"
  archive="$home/.openclaw/workspace/outbox-archive"
  [ -d "$outbox" ] || continue

  # Archive files older than retention period (skip .clawvisor-last-read)
  find "$outbox" -maxdepth 1 -name "*.md" -mtime +$RETENTION_DAYS \
    ! -name ".clawvisor-last-read" -print0 | while IFS= read -r -d '' file; do
    month=$(date -r "$file" +%Y-%m)
    dest="$archive/$month"
    mkdir -p "$dest"
    mv "$file" "$dest/"
  done

  # Compress month directories older than 90 days
  [ -d "$archive" ] || continue
  find "$archive" -mindepth 1 -maxdepth 1 -type d -mtime +90 | while read -r dir; do
    tarfile="$archive/$(basename "$dir").tar.gz"
    [ -f "$tarfile" ] && continue
    tar czf "$tarfile" -C "$archive" "$(basename "$dir")" && rm -rf "$dir"
  done
done
SCRIPT

chmod +x /opt/fleetclaw/scripts/archive-outboxes.sh
```

### Install the cron job

Add to root's crontab (`sudo crontab -e`):

```cron
0 2 * * * /opt/fleetclaw/scripts/archive-outboxes.sh
```

To override the 30-day default, set `FC_RETENTION_DAYS` in the crontab:

```cron
0 2 * * * FC_RETENTION_DAYS=7 /opt/fleetclaw/scripts/archive-outboxes.sh
```

### Verify

```bash
# Dry run — list files that would be archived (without moving them)
find /home/fc-*/. -path "*/.openclaw/workspace/outbox/*.md" -mtime +30 \
  ! -name ".clawvisor-last-read"
```

## Host sizing

| Fleet size | RAM | CPU | Disk |
|-----------|-----|-----|------|
| 10 assets | 8 GB | 4 cores | 50 GB SSD |
| 50 assets | 16 GB | 8 cores | 100 GB SSD |
| 100 assets | 32 GB | 16 cores | 200 GB SSD |
