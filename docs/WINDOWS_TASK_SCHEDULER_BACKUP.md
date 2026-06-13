# Windows Task Scheduler Backup Runbook

Sprint 8 keeps Magpie on the existing Windows/SQLite runtime. The scheduled task runs the same Django backup command through `scripts\backup.ps1`; it does not embed secret values.

## Prerequisites

1. Install PowerShell 7 and make `pwsh` available on PATH.
2. Install rclone and configure the chosen remote locally.
3. Store required secret values in the password manager and expose them to the scheduled task through the Windows account environment or another local secret mechanism.
4. Set the rclone destination through the local environment using the configured destination variable name.
5. Run one manual backup without upload first, then one manual upload test after rclone is configured.

## Register The Task

Run from PowerShell after replacing the repo path with the local checkout path:

```powershell
$repo = "<repo>"
$script = Join-Path $repo "scripts\backup.ps1"
$taskRun = "pwsh -NoProfile -ExecutionPolicy Bypass -File `"$script`""
schtasks /create /tn "Magpie Backup" /tr $taskRun /sc daily /st 02:00 /rl LIMITED /f
```

The task runs as the current Windows account. Confirm that account can read the repo, write `backend\backups`, write `backend\logs`, read the local environment, and access the configured rclone remote.

## Unattended Run Check

```powershell
schtasks /run /tn "Magpie Backup"
schtasks /query /tn "Magpie Backup" /v /fo LIST
```

After the run, verify:

- A fresh encrypted archive exists under `backend\backups`.
- `backend\logs\magpie.log` has a fresh backup entry.
- rclone shows the fresh encrypted archive on the configured remote.
- No plaintext `.tar.gz` remains in the backups directory.

## GUI Alternative

Create a daily task in Task Scheduler with:

- Program: `pwsh`
- Arguments: `-NoProfile -ExecutionPolicy Bypass -File "<repo>\scripts\backup.ps1"`
- Start in: `<repo>\backend`
- Run whether user is logged on or not, using the same Windows account that owns the local environment and rclone configuration.

## Remote Retention

Sprint 8 only prunes local encrypted archives. Remote retention should be configured on the cloud provider or handled in a later operations sprint.
