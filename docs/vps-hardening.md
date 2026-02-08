# VPS Hardening Guide for Ubuntu 24.04 LTS

Security hardening guide for deploying FleetClaw on OVH VPS-3 (24 GB RAM, 8 vCores).

This guide adapts the [OpenClaw 4-layer security model](https://github.com/openclaw/clawdbot-ansible/blob/main/docs/security.md) for our multi-agent fleet deployment.

## Security Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    INTERNET                                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  LAYER 1: UFW Firewall                                       │
│  - Default deny incoming                                     │
│  - Allow: SSH (22), Tailscale (41641/udp)                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  LAYER 2: DOCKER-USER Chain                                  │
│  - Prevents Docker from bypassing UFW                        │
│  - Drops external traffic to container ports                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  LAYER 3: Localhost-Only Binding                            │
│  - Container ports bind to 127.0.0.1 only                   │
│  - Services accessible only from host                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  LAYER 4: Non-Root Containers                                │
│  - OpenClaw runs as unprivileged user                        │
│  - Limited blast radius if compromised                       │
└─────────────────────────────────────────────────────────────┘
```

## 1. Initial System Setup

### Update System Packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git unzip htop tmux ufw fail2ban
```

### Set Timezone and Hostname

```bash
# Set timezone
sudo timedatectl set-timezone UTC

# Set hostname
sudo hostnamectl set-hostname fleetclaw-prod
echo "127.0.0.1 fleetclaw-prod" | sudo tee -a /etc/hosts
```

### Create Dedicated User

```bash
# Create fleetclaw user
sudo adduser fleetclaw --disabled-password --gecos ""

# Note: Docker group membership is added in Section 4

# Set up SSH key access
sudo mkdir -p /home/fleetclaw/.ssh
sudo cp ~/.ssh/authorized_keys /home/fleetclaw/.ssh/
sudo chown -R fleetclaw:fleetclaw /home/fleetclaw/.ssh
sudo chmod 700 /home/fleetclaw/.ssh
sudo chmod 600 /home/fleetclaw/.ssh/authorized_keys
```

## 2. SSH Hardening

Edit `/etc/ssh/sshd_config`:

```bash
sudo nano /etc/ssh/sshd_config
```

Apply these settings:

```
# Disable root login
PermitRootLogin no

# Key-only authentication
PasswordAuthentication no
PubkeyAuthentication yes

# Restrict to specific users
AllowUsers fleetclaw ubuntu

# Disable empty passwords
PermitEmptyPasswords no

# Disable X11 forwarding (not needed)
X11Forwarding no

# Reduce login grace time
LoginGraceTime 30

# Limit authentication attempts
MaxAuthTries 3
```

Restart SSH:

```bash
sudo systemctl restart ssh
```

> **Note:** Ubuntu uses `ssh` as the service name (not `sshd` like RHEL/CentOS). Ubuntu 24.04 also uses socket-based activation by default via `ssh.socket`.

> **Warning:** Test SSH access in a new terminal before closing your current session.

## 3. UFW Firewall (Layer 1)

```bash
# Reset to clean state
sudo ufw reset

# Default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH
sudo ufw allow ssh

# Allow Tailscale (optional, for VPN access)
sudo ufw allow 41641/udp comment 'Tailscale'

# Enable firewall
sudo ufw enable

# Verify
sudo ufw status verbose
```

Expected output:

```
Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), disabled (routed)
New profiles: skip

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW IN    Anywhere
41641/udp                  ALLOW IN    Anywhere                   # Tailscale
22/tcp (v6)                ALLOW IN    Anywhere (v6)
41641/udp (v6)             ALLOW IN    Anywhere (v6)              # Tailscale
```

## 4. Docker Engine Installation

Install Docker Engine from the official repository (not snap or `docker.io`).

See: https://docs.docker.com/engine/install/ubuntu/

```bash
# Add Docker's official GPG key
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add Docker repository (DEB822 format)
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt-get update

# Install Docker Engine
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add fleetclaw user to docker group
sudo usermod -aG docker fleetclaw
```

Log out and back in for the group membership to take effect:

```bash
exit
```

Then reconnect and verify:

```bash
docker --version
docker ps
```

`docker ps` should work without `sudo`.

## 5. DOCKER-USER Chain (Layer 2) - Critical

Docker modifies iptables directly, bypassing UFW. This is the most important security layer.

### Create iptables Rules File

```bash
sudo nano /etc/docker/iptables-rules.conf
```

Add:

```
*filter
:DOCKER-USER - [0:0]
# Allow established connections (responses to outgoing requests)
-A DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
# Allow traffic from loopback (localhost)
-A DOCKER-USER -i lo -j ACCEPT
# Allow traffic from Docker networks (inter-container)
-A DOCKER-USER -i br-+ -j ACCEPT
-A DOCKER-USER -i docker0 -j ACCEPT
# DROP all external traffic to containers
# NOTE: Replace 'ens3' with your actual interface (run: ip link show)
-A DOCKER-USER -i ens3 -j DROP
COMMIT
```

> **Important:** OVH VPS uses `ens3` as the primary network interface (not `eth0`). Verify your interface name with `ip link show` and update the rule accordingly. Common names include `ens3`, `enp0s3`, or `eth0`.

### Apply Rules on Boot

Create systemd service:

```bash
sudo nano /etc/systemd/system/docker-iptables.service
```

Add:

```ini
[Unit]
Description=Apply Docker iptables rules
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/sbin/iptables-restore -n /etc/docker/iptables-rules.conf
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable docker-iptables.service
sudo systemctl start docker-iptables.service
```

### Verify DOCKER-USER Chain

```bash
sudo iptables -L DOCKER-USER -n -v
```

Expected output:

```
Chain DOCKER-USER (1 references)
 pkts bytes target     prot opt in     out     source       destination
    0     0 ACCEPT     all  --  *      *       0.0.0.0/0    0.0.0.0/0    ctstate RELATED,ESTABLISHED
    0     0 ACCEPT     all  --  lo     *       0.0.0.0/0    0.0.0.0/0
    0     0 ACCEPT     all  --  br-+   *       0.0.0.0/0    0.0.0.0/0
    0     0 ACCEPT     all  --  docker0 *      0.0.0.0/0    0.0.0.0/0
    0     0 DROP       all  --  ens3   *       0.0.0.0/0    0.0.0.0/0
```

## 6. Localhost-Only Binding (Layer 3)

Ensure all service ports in `docker-compose.yml` bind to localhost only.

### Recommended Port Bindings

```yaml
services:
  redis:
    ports:
      - "127.0.0.1:6379:6379"  # NOT "6379:6379"

  loki:
    ports:
      - "127.0.0.1:3100:3100"

  prometheus:
    ports:
      - "127.0.0.1:9090:9090"
```

> **Note:** The current `docker-compose.yml.j2` template exposes Redis and Loki without localhost binding. This is acceptable when Layer 2 (DOCKER-USER) is properly configured, but localhost binding provides defense-in-depth.

### Verify No External Port Exposure

From an external machine:

```bash
nmap -p- YOUR_VPS_IP
```

Expected: Only port 22 (SSH) should be open.

## 7. Fail2ban Configuration

Create jail configuration:

```bash
sudo nano /etc/fail2ban/jail.local
```

Add:

```ini
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5
ignoreip = 127.0.0.1/8 ::1

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 24h
```

Restart fail2ban:

```bash
sudo systemctl restart fail2ban
sudo systemctl enable fail2ban
```

Verify:

```bash
sudo fail2ban-client status sshd
```

## 8. Automatic Security Updates

```bash
sudo apt install -y unattended-upgrades
```

Configure:

```bash
sudo nano /etc/apt/apt.conf.d/50unattended-upgrades
```

Ensure these lines are uncommented:

```
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}";
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};

// Exclude Docker to avoid unexpected container issues
Unattended-Upgrade::Package-Blacklist {
    "docker-ce";
    "docker-ce-cli";
    "containerd.io";
};

Unattended-Upgrade::Automatic-Reboot "false";
```

Enable automatic updates:

```bash
sudo dpkg-reconfigure -plow unattended-upgrades
```

## 9. Docker Daemon Hardening

Create or edit `/etc/docker/daemon.json`:

```bash
sudo nano /etc/docker/daemon.json
```

Add:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "live-restore": true,
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 65536,
      "Soft": 65536
    }
  },
  "no-new-privileges": true
}
```

Restart Docker:

```bash
sudo systemctl restart docker
```

## 10. Fleet-Specific Security

### Redis ACL Verification

FleetClaw uses Redis ACL for per-asset access control. Verify configuration:

```bash
# Check ACL is loaded
docker exec fleetclaw-redis redis-cli ACL LIST

# Test asset isolation (should fail)
docker exec fleetclaw-redis redis-cli -u redis://ex_001:password@localhost:6379 GET fleet:inbox:DZ-001
# Expected: (error) NOPERM
```

See `templates/redis-acl.conf.j2` for the ACL template structure.

### Environment File Permissions

```bash
# Secure .env file
chmod 600 /home/fleetclaw/fleetclaw/.env
chown fleetclaw:fleetclaw /home/fleetclaw/fleetclaw/.env

# Verify
ls -la /home/fleetclaw/fleetclaw/.env
# Expected: -rw------- 1 fleetclaw fleetclaw
```

### Gatekeeper Deployment (Optional)

The Gatekeeper sidecar provides Telegram user permission enforcement. When enabled:

1. Uncomment the gatekeeper service in `docker-compose.yml`
2. Configure `config/users.yaml` with Telegram user IDs
3. Configure `config/permissions.yaml` with role-based access

## 11. OVH-Specific Notes

### No Swap by Default

OVH VPS instances typically have no swap. For a 64-agent fleet:

```bash
# Check current swap
free -h

# Add swap if needed
# Sizing guide:
#   - 4 GB: Light use, ~20 concurrent agents
#   - 8 GB: Heavy use, all 64 agents active concurrently
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Kernel Parameters

```bash
sudo nano /etc/sysctl.d/99-fleetclaw.conf
```

Add:

```
# Reduce swappiness (prefer RAM)
vm.swappiness = 10

# Increase connection limits for 64 agents
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 1024

# File descriptor limits
fs.file-max = 100000
```

Apply:

```bash
sudo sysctl -p /etc/sysctl.d/99-fleetclaw.conf
```

## 12. Verification Checklist

Run these commands to verify security posture:

```bash
# 1. UFW status
sudo ufw status verbose

# 2. DOCKER-USER chain
sudo iptables -L DOCKER-USER -n -v

# 3. External port scan (from another machine)
nmap -p- YOUR_VPS_IP
# Expected: Only 22/tcp open

# 4. SSH configuration
sudo sshd -T | grep -E "permitrootlogin|passwordauthentication|allowusers"
# Expected: permitrootlogin no, passwordauthentication no

# 5. Fail2ban status
sudo fail2ban-client status sshd

# 6. Docker daemon config
docker info | grep -E "Live Restore|Logging Driver"

# 7. .env permissions
ls -la .env
# Expected: -rw------- (600)

# 8. Unattended upgrades
systemctl status unattended-upgrades
```

## 13. Accessing Services Securely

Since all ports are blocked externally, use SSH tunnels or Tailscale:

### SSH Tunnel

```bash
# Forward Loki to local machine
ssh -L 3100:localhost:3100 fleetclaw@YOUR_VPS_IP

# Forward Redis (for debugging)
ssh -L 6379:localhost:6379 fleetclaw@YOUR_VPS_IP
```

### Tailscale (Recommended)

[Tailscale](https://tailscale.com/) is a zero-config VPN that provides secure remote access without managing SSH tunnels. It's optional but recommended for convenient service access.

Install Tailscale:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Once configured, access services directly via Tailscale IP:

```bash
# From your local machine on Tailscale
curl http://100.x.x.x:3100/ready
```

## Related Documentation

- [Resource Monitoring Guide](monitoring.md) - Monitor fleet resource usage
- [OpenClaw Security Architecture](https://github.com/openclaw/clawdbot-ansible/blob/main/docs/security.md) - Upstream security docs
- `templates/redis-acl.conf.j2` - Redis ACL template
- `gatekeeper/` - Permission routing sidecar (Go)
