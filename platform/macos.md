# macOS Platform Reference

Platform-specific commands for deploying FleetClaw on macOS. This is a secondary platform — Ubuntu is primary.

## User management

### Create the shared group

```bash
dscl . -create /Groups/fc-agents
dscl . -create /Groups/fc-agents PrimaryGroupID 600
```

### Create an agent user

```bash
# Create user
sysadminctl -addUser fc-ex001 -shell /bin/bash -home /Users/fc-ex001 -password ""

# Add to shared group
dscl . -append /Groups/fc-agents GroupMembership fc-ex001
```

Or using `dscl` directly for system-level users:

```bash
dscl . -create /Users/fc-ex001
dscl . -create /Users/fc-ex001 UserShell /bin/bash
dscl . -create /Users/fc-ex001 NFSHomeDirectory /Users/fc-ex001
dscl . -create /Users/fc-ex001 UniqueID 601  # Pick unused UID
dscl . -create /Users/fc-ex001 PrimaryGroupID 600
createhomedir -c -u fc-ex001
```

Repeat for `fc-clawvisor`, `fc-clawordinator`, and each asset agent.

### Run commands as an agent user

```bash
su -l fc-ex001 -c "command here"
```

## Package management

### Node.js (required by OpenClaw)

```bash
brew install node@22
```

Or install nvm per user for isolated Node.js versions.

## Process management (launchd)

### Plist template

Create one plist per agent at `/Library/LaunchDaemons/com.fleetclaw.agent.{id}.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.fleetclaw.agent.ex001</string>

    <key>UserName</key>
    <string>fc-ex001</string>

    <key>GroupName</key>
    <string>fc-agents</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/node</string>
        <string>/Users/fc-ex001/.openclaw/dist/index.js</string>
        <string>gateway</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/fc-ex001/.openclaw</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>FIREWORKS_API_KEY</key>
        <string>your-key-here</string>
        <key>TELEGRAM_BOT_TOKEN</key>
        <string>your-token-here</string>
        <key>FLEET_MD_PATH</key>
        <string>/opt/fleetclaw/fleet.md</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>StandardOutPath</key>
    <string>/var/log/fleetclaw/fc-agent-ex001.log</string>

    <key>StandardErrorPath</key>
    <string>/var/log/fleetclaw/fc-agent-ex001.err</string>

    <key>SoftResourceLimits</key>
    <dict>
        <key>MemoryLock</key>
        <integer>536870912</integer>
    </dict>
</dict>
</plist>
```

### Service commands

```bash
# Load and start
launchctl load /Library/LaunchDaemons/com.fleetclaw.agent.ex001.plist

# Stop
launchctl unload /Library/LaunchDaemons/com.fleetclaw.agent.ex001.plist

# Check status
launchctl list | grep fleetclaw

# View logs
tail -f /var/log/fleetclaw/fc-agent-ex001.log
```

## File permissions (macOS ACLs)

macOS uses a different ACL syntax from Linux. Use `chmod +a` instead of `setfacl`.

### Grant Clawvisor read access to asset outbox

```bash
chmod +a "fc-clawvisor allow read,readattr,readextattr,readsecurity,list,search" /Users/fc-ex001/.openclaw/workspace/outbox/
```

### Grant Clawvisor write access to asset inbox

```bash
chmod +a "fc-clawvisor allow read,write,append,readattr,writeattr,readextattr,writeextattr,list,search,add_file,delete_child" /Users/fc-ex001/.openclaw/workspace/inbox/
```

### Grant Clawordinator write access to any inbox

```bash
chmod +a "fc-clawordinator allow read,write,append,readattr,writeattr,readextattr,writeextattr,list,search,add_file,delete_child" /Users/fc-ex001/.openclaw/workspace/inbox/
```

### Grant Clawvisor write access to Clawordinator inbox (for escalations)

```bash
chmod +a "fc-clawvisor allow read,write,append,readattr,writeattr,readextattr,writeextattr,list,search,add_file,delete_child" /Users/fc-clawordinator/.openclaw/workspace/inbox/
```

### View ACLs

```bash
ls -le /Users/fc-ex001/.openclaw/workspace/outbox/
```

## fleet.md setup

```bash
mkdir -p /opt/fleetclaw
touch /opt/fleetclaw/fleet.md
chown fc-clawordinator:fc-agents /opt/fleetclaw/fleet.md
chmod 640 /opt/fleetclaw/fleet.md
```

## Log directory

```bash
mkdir -p /var/log/fleetclaw
chown root:fc-agents /var/log/fleetclaw
chmod 770 /var/log/fleetclaw
```
