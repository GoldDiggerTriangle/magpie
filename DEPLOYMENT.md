# Magpie Sprint 9 Deployment

Magpie Sprint 9 runs the existing Windows + SQLite app as one production Waitress process. The same origin serves the React SPA, `/api/`, `/admin/`, and local media on one LAN port.

## Runtime Contract

- OS: Windows 10, PowerShell 7.
- Database: SQLite at `backend\db.sqlite3`.
- Media: `backend\media_files`.
- App server: Waitress through `backend\serve.py`.
- Static serving: WhiteNoise from `backend\staticfiles`.
- Service manager: NSSM service named `Magpie`.
- URLs: `http://localhost:8000`, `http://127.0.0.1:8000`, and `http://192.168.1.86:8000`.
- HTTPS, public exposure, Docker, Linux, and Postgres runtime migration are not part of this deployment.

## Environment

Create or update `backend\.env`. Do not commit this file.

Required names:

```text
SECRET_KEY
DEBUG
DATABASE_URL
ALLOWED_HOSTS
CSRF_TRUSTED_ORIGINS
MAGPIE_HOST
MAGPIE_PORT
MAGPIE_THREADS
HIGH_VALUE_THRESHOLD
METALS_PROVIDER
METALS_API_KEY
METALS_BASE_CURRENCY
METALS_CACHE_TTL_SECONDS
EBAY_ENV
EBAY_CLIENT_ID
EBAY_CLIENT_SECRET
EBAY_RU_NAME
MAGPIE_TOKEN_ENCRYPTION_KEY
MAGPIE_BACKUP_PASSPHRASE
MAGPIE_BACKUP_RCLONE_DEST
```

Production values must include:

```text
DEBUG=0
DATABASE_URL=sqlite:///db.sqlite3
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.86
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://192.168.1.86:8000
MAGPIE_HOST=0.0.0.0
MAGPIE_PORT=8000
MAGPIE_THREADS=4
```

`backend\serve.py` loads `backend\.env` before Django starts, so the NSSM service does not depend on an interactive PowerShell session. If `.env` cannot be used, set the same names with `nssm set Magpie AppEnvironmentExtra ...`; keep real values in the password manager, not in scripts or Git.

## Build And Update

Run from the repo root:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..\frontend
npm ci
npm run build
cd ..\backend
$env:DJANGO_SETTINGS_MODULE = "config.settings.prod"
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
.\.venv\Scripts\python.exe manage.py check --deploy
```

Expected `check --deploy` warnings while LAN HTTP remains in use:

- HSTS is off.
- SSL redirect is off.
- secure session and CSRF cookies are off.

Those flip only after an HTTPS front end is in place. A weak or missing `SECRET_KEY` warning is not acceptable for the real service; set a real value in `backend\.env`.

## NSSM Service

Install NSSM and make `nssm.exe` available on `PATH`, then run an elevated PowerShell:

```powershell
$repo = "C:\path\to\magpie"
$python = Join-Path $repo "backend\.venv\Scripts\python.exe"
$serve = Join-Path $repo "backend\serve.py"
$backend = Join-Path $repo "backend"
$logs = Join-Path $backend "logs"
New-Item -ItemType Directory -Force $logs | Out-Null

nssm install Magpie $python $serve
nssm set Magpie AppDirectory $backend
nssm set Magpie Start SERVICE_AUTO_START
nssm set Magpie AppStdout (Join-Path $logs "service-stdout.log")
nssm set Magpie AppStderr (Join-Path $logs "service-stderr.log")
nssm set Magpie AppExit Default Restart
nssm set Magpie AppThrottle 5000
nssm start Magpie
```

Useful lifecycle commands:

```powershell
nssm status Magpie
nssm stop Magpie
nssm start Magpie
nssm restart Magpie
nssm remove Magpie confirm
```

Update procedure:

```powershell
nssm stop Magpie
git pull
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..\frontend
npm ci
npm run build
cd ..\backend
$env:DJANGO_SETTINGS_MODULE = "config.settings.prod"
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
nssm start Magpie
```

## Verification

After service start:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8000/ | Select-Object StatusCode
Invoke-WebRequest -UseBasicParsing http://localhost:8000/api/health/ | Select-Object StatusCode,Content
Invoke-WebRequest -UseBasicParsing http://localhost:8000/admin/login/ | Select-Object StatusCode
Invoke-WebRequest -UseBasicParsing http://localhost:8000/inventory/sprint9-deep-link | Select-Object StatusCode
```

From another LAN device, open:

```text
http://192.168.1.86:8000
```

Crash-restart proof:

```powershell
nssm status Magpie
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match "backend\\serve.py" } |
  Select-Object ProcessId,CommandLine
Stop-Process -Id <WaitressPythonProcessId> -Force
Start-Sleep -Seconds 10
nssm status Magpie
Invoke-WebRequest -UseBasicParsing http://localhost:8000/api/health/ | Select-Object StatusCode,Content
```

Boot proof:

1. Confirm `nssm get Magpie Start` returns `SERVICE_AUTO_START`.
2. Reboot Windows.
3. Without starting anything manually, open `http://localhost:8000/api/health/`.

## Backups

Sprint 8 backups still use the same command and paths:

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py backup --no-upload
```

Scheduled backups use `scripts\backup.ps1`; see `docs\WINDOWS_TASK_SCHEDULER_BACKUP.md`. Logs are under `backend\logs`, local backup archives under `backend\backups`, and media under `backend\media_files`.

## Optional Port 80

Port 8000 avoids privileged binding. If a cleaner URL is wanted later, bind port 80 only after checking Windows permissions and conflicts:

```text
MAGPIE_PORT=80
```

That does not add HTTPS.

## Internet Exposure Appendix

Do not expose Waitress directly to the internet. If public access is ever required, put Magpie behind Caddy with automatic HTTPS or a Cloudflare Tunnel, restrict `/admin/`, tighten `ALLOWED_HOSTS`, then enable:

```text
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=<nonzero>
SECURE_SSL_REDIRECT=True
```

This appendix is a runbook only. Sprint 9 does not execute HTTPS or public exposure.
