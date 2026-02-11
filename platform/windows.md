# Windows Platform Reference

Platform-specific commands for deploying FleetClaw on Windows. This is a secondary platform — Ubuntu is primary.

## User management

### Create the shared group

```powershell
New-LocalGroup -Name "fc-agents" -Description "FleetClaw agent users"
```

### Create an agent user

```powershell
# Create user with random password (no interactive login)
$password = ConvertTo-SecureString (New-Guid).ToString() -AsPlainText -Force
New-LocalUser -Name "fc-ex001" -Password $password -Description "FleetClaw agent EX-001" -AccountNeverExpires

# Add to shared group
Add-LocalGroupMember -Group "fc-agents" -Member "fc-ex001"
```

Repeat for `fc-clawvisor`, `fc-clawordinator`, and each asset agent.

### Run commands as an agent user

```powershell
runas /user:fc-ex001 "command here"
```

## Package management

### Node.js (required by OpenClaw)

```powershell
winget install OpenJS.NodeJS.LTS
```

Or via Chocolatey:

```powershell
choco install nodejs-lts
```

## Process management (NSSM)

NSSM (Non-Sucking Service Manager) wraps Node.js processes as Windows services.

### Install NSSM

```powershell
choco install nssm
```

### Create a service

```powershell
nssm install fc-agent-ex001 "C:\Program Files\nodejs\openclaw.cmd" gateway --force

# Set working directory
nssm set fc-agent-ex001 AppDirectory "C:\FleetClaw\agents\fc-ex001\.openclaw"

# Set user
nssm set fc-agent-ex001 ObjectName ".\fc-ex001" "password-here"

# Set environment variables
nssm set fc-agent-ex001 AppEnvironmentExtra "FIREWORKS_API_KEY=your-key" "TELEGRAM_BOT_TOKEN=your-token" "FLEET_MD_PATH=C:\FleetClaw\fleet.md"

# Set auto-restart
nssm set fc-agent-ex001 AppRestartDelay 10000

# Set log files
nssm set fc-agent-ex001 AppStdout "C:\FleetClaw\logs\fc-agent-ex001.log"
nssm set fc-agent-ex001 AppStderr "C:\FleetClaw\logs\fc-agent-ex001.err"

# Set memory limit (1 GB for assets, 1.5 GB for supervisory)
nssm set fc-agent-ex001 AppEnvironmentExtra+ "NODE_OPTIONS=--max-old-space-size=768"
```

### Service commands

```powershell
# Start
nssm start fc-agent-ex001

# Stop
nssm stop fc-agent-ex001

# Restart
nssm restart fc-agent-ex001

# Status
nssm status fc-agent-ex001

# Remove service
nssm remove fc-agent-ex001 confirm
```

### Upgrading OpenClaw

```powershell
# 1. Stop all agent services
Get-Service fc-agent-* | Stop-Service

# 2. Update global package
npm install -g openclaw@<version>

# 3. Verify version
openclaw --version

# 4. Start all agent services
Get-Service fc-agent-* | Start-Service

# 5. Check status
Get-Service fc-agent-* | Format-Table Name, Status
```

NSSM services are registered as standard Windows services, so `Get-Service`/`Stop-Service`/`Start-Service` work. Alternatively, use `nssm stop fc-agent-ex001` per agent.

## File permissions (NTFS ACLs)

### Grant Clawvisor read access to asset outbox

```powershell
$acl = Get-Acl "C:\FleetClaw\agents\fc-ex001\.openclaw\workspace\outbox"
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("fc-clawvisor", "ReadAndExecute", "ContainerInherit,ObjectInherit", "None", "Allow")
$acl.AddAccessRule($rule)
Set-Acl -Path "C:\FleetClaw\agents\fc-ex001\.openclaw\workspace\outbox" -AclObject $acl
```

### Grant Clawvisor write access to asset inbox

```powershell
$acl = Get-Acl "C:\FleetClaw\agents\fc-ex001\.openclaw\workspace\inbox"
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("fc-clawvisor", "Modify", "ContainerInherit,ObjectInherit", "None", "Allow")
$acl.AddAccessRule($rule)
Set-Acl -Path "C:\FleetClaw\agents\fc-ex001\.openclaw\workspace\inbox" -AclObject $acl
```

### Grant Clawordinator write access to any inbox

```powershell
$acl = Get-Acl "C:\FleetClaw\agents\fc-ex001\.openclaw\workspace\inbox"
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("fc-clawordinator", "Modify", "ContainerInherit,ObjectInherit", "None", "Allow")
$acl.AddAccessRule($rule)
Set-Acl -Path "C:\FleetClaw\agents\fc-ex001\.openclaw\workspace\inbox" -AclObject $acl
```

### View ACLs

```powershell
Get-Acl "C:\FleetClaw\agents\fc-ex001\.openclaw\workspace\outbox" | Format-List
# Or
icacls "C:\FleetClaw\agents\fc-ex001\.openclaw\workspace\outbox"
```

## Filesystem layout

```
C:\FleetClaw\
├── agents\
│   ├── fc-ex001\.openclaw\          # Agent workspace
│   ├── fc-clawvisor\.openclaw\
│   └── fc-clawordinator\.openclaw\
├── skills\                           # Shared skills (read-only)
├── fleet.md                          # Fleet registry
├── env\                              # Per-agent env files
│   ├── ex001.env
│   ├── clawvisor.env
│   └── clawordinator.env
└── logs\                             # Service logs
```

## fleet.md setup

```powershell
New-Item -Path "C:\FleetClaw\fleet.md" -ItemType File -Force

# Set owner to Clawordinator, grant read to fc-agents group
$acl = Get-Acl "C:\FleetClaw\fleet.md"
$owner = New-Object System.Security.Principal.NTAccount("fc-clawordinator")
$acl.SetOwner($owner)

$readRule = New-Object System.Security.AccessControl.FileSystemAccessRule("fc-agents", "Read", "Allow")
$writeRule = New-Object System.Security.AccessControl.FileSystemAccessRule("fc-clawordinator", "Modify", "Allow")
$acl.AddAccessRule($readRule)
$acl.AddAccessRule($writeRule)
Set-Acl -Path "C:\FleetClaw\fleet.md" -AclObject $acl
```

## Outbox archival

A nightly scheduled task archives outbox files older than 30 days and compresses month directories older than 90 days. See `docs/scheduling.md` for the archival model.

### Create the archival script

Save as `C:\FleetClaw\scripts\Archive-Outboxes.ps1`:

```powershell
# FleetClaw outbox archival — runs nightly via Task Scheduler
# Archives outbox files older than RetentionDays, compresses months older than 90 days

param(
    [int]$RetentionDays = 30
)

$cutoff = (Get-Date).AddDays(-$RetentionDays)
$compressCutoff = (Get-Date).AddDays(-90)

Get-ChildItem "C:\FleetClaw\agents" -Directory | ForEach-Object {
    $outbox = Join-Path $_.FullName ".openclaw\workspace\outbox"
    $archive = Join-Path $_.FullName ".openclaw\workspace\outbox-archive"
    if (-not (Test-Path $outbox)) { return }

    # Archive files older than retention period (skip .clawvisor-last-read)
    Get-ChildItem $outbox -Filter "*.md" -File | Where-Object {
        $_.LastWriteTime -lt $cutoff -and $_.Name -ne ".clawvisor-last-read"
    } | ForEach-Object {
        $month = $_.LastWriteTime.ToString("yyyy-MM")
        $dest = Join-Path $archive $month
        if (-not (Test-Path $dest)) { New-Item -Path $dest -ItemType Directory -Force | Out-Null }
        Move-Item $_.FullName -Destination $dest
    }

    # Compress month directories older than 90 days
    if (-not (Test-Path $archive)) { return }
    Get-ChildItem $archive -Directory | Where-Object {
        $_.LastWriteTime -lt $compressCutoff
    } | ForEach-Object {
        $zipFile = Join-Path $archive "$($_.Name).zip"
        if (Test-Path $zipFile) { return }
        Compress-Archive -Path $_.FullName -DestinationPath $zipFile
        Remove-Item $_.FullName -Recurse -Force
    }
}
```

### Register the scheduled task

```powershell
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File C:\FleetClaw\scripts\Archive-Outboxes.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At "2:00AM"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable

Register-ScheduledTask `
    -TaskName "FleetClaw-OutboxArchival" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -User "SYSTEM" `
    -RunLevel Highest `
    -Description "Archive FleetClaw outbox files older than 30 days"
```

To override the 30-day default, change the `-Argument` to include `-RetentionDays 7`:

```powershell
-Argument "-NoProfile -ExecutionPolicy Bypass -File C:\FleetClaw\scripts\Archive-Outboxes.ps1 -RetentionDays 7"
```

### Verify

```powershell
# Check that the task is registered
Get-ScheduledTask -TaskName "FleetClaw-OutboxArchival"

# Dry run — list files that would be archived (without moving them)
Get-ChildItem "C:\FleetClaw\agents\*\.openclaw\workspace\outbox\*.md" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) -and $_.Name -ne ".clawvisor-last-read" }
```

## Notes

- Windows Defender may flag OpenClaw's file-watching behavior. Add `C:\FleetClaw\` to exclusions if needed.
- For production Windows deployments, consider running agents in WSL2 instead, using the Ubuntu platform guide.
- NSSM services survive reboots automatically when configured with the default startup type.
