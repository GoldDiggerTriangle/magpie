# Sprint 9 Robustness Evidence

Date: 2026-06-13 to 2026-06-14
Repo path: `C:\Users\Regan\Documents\Codex\2026-06-13\reasoning-extra-high-i-approve-sprint-2`

Current closure status: Sprint 9 is formally closed and the post-closure data checkout risk is reconciled. The real NSSM service is installed, starts automatically after reboot, serves the production app on port 8000, accepts LAN access from a second device, restarts after the Waitress/python listener is killed, and now uses the live Sprint 8 business data in the Sprint 9 runtime checkout.

## Local Validation Summary

| Check | Result | Evidence |
| --- | --- | --- |
| Waitress launcher | Passed | `scripts\production_smoke.py` started `backend\serve.py` with `DJANGO_SETTINGS_MODULE=config.settings.prod` and received `Production Waitress/WhiteNoise smoke passed.` |
| Built SPA through WhiteNoise | Passed | `npm run build` emitted `frontend\dist`; `manage.py collectstatic --noinput` copied 162 files to `backend\staticfiles`; production smoke fetched a built `/assets/...` JS/CSS file. |
| Same-origin production API base | Passed | `rg "http://localhost:8000|http://127\.0\.0\.1:8000" frontend\dist` found no matches; smoke fetched `/api/health/` on the same origin. |
| One process serves SPA + `/api` + `/admin` | Passed locally | Production smoke verified `/`, `/api/health/`, `/admin/login/`, and `/inventory/sprint9-smoke` from the same Waitress process on a local temporary port. |
| SPA deep-link reload | Passed | Production smoke verified `/inventory/sprint9-smoke` returned the built `index.html`. |
| `DEBUG=False` behavior | Passed locally | Production smoke ran with `DEBUG=0` and verified a missing file returned a plain 404 without debug markers. |
| Host allow-list rejection | Passed locally | Production smoke sent `Host: not-allowed.example` and verified HTTP 400. |
| Production deploy check | Passed with expected warnings | `manage.py check --deploy` exited 0. Expected LAN-HTTP warnings: HSTS off, SSL redirect off, secure session cookie off, secure CSRF cookie off. The local dummy `SECRET_KEY` also triggered a warning; the real service must use a strong `SECRET_KEY` from `backend\.env`. |
| SQLite backend tests | Passed | `python -m pytest --basetemp ..\.tmp\pytest`: 92 passed, 1 skipped. |
| Frontend tests | Passed | `npm run test`: 16 files passed, 43 tests passed. |
| Frontend typecheck | Passed | `npm run typecheck` exited 0. |
| Frontend build | Passed | `npm run build` exited 0 and generated hashed assets. |
| Sprint 8 backup | Passed | `manage.py backup --output-dir ..\.tmp\sprint9-backups --no-upload` produced `magpie-backup-20260613-120743.tar.gz.enc`. |
| Sprint 8 backup with production `.env` | Passed | `DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py backup --output-dir ..\.tmp\sprint9-service-backups --no-upload` produced `magpie-backup-20260613-124135.tar.gz.enc`. |
| Sprint 8 backup after NSSM service install | Passed | `DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py backup --output-dir ..\.tmp\sprint9-service-backups --no-upload` produced `magpie-backup-20260613-204913.tar.gz.enc`. |
| Sprint 8 backup after LAN/firewall correction | Passed | `DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py backup --output-dir ..\.tmp\sprint9-service-backups --no-upload` produced `magpie-backup-20260613-205446.tar.gz.enc`. |
| Sprint 8 restore spot check | Passed | `manage.py restore ... --target ..\.tmp\sprint9-restore` restored counts: items=6, photos=0, valuations=5, drafts=1, credential=0. |
| Migrations | Passed | `manage.py makemigrations --check --dry-run --noinput` reported `No changes detected`. |
| `restart servers.txt` removed | Passed | `Test-Path "restart servers.txt"` returned `False`; no file existed in this checkout. |
| Production `.env` loaded by app mechanism | Passed locally | A prior Magpie `backend\.env` was copied into this checkout without printing contents, then missing Sprint 9 names were completed. `backend\.env` is ignored by Git. |
| Waitress on service port 8000 | Passed manually | After stopping the old listener, `scripts\production_smoke.py` passed on port 8000 using `backend\.env` for secret settings. |
| Real NSSM service installed and running | Passed | Administrator PowerShell observed `Get-Service Magpie` as `Running`, `nssm status Magpie` as `SERVICE_RUNNING`, `netstat -ano` showing `0.0.0.0:8000 LISTENING 24148`, and localhost `/` returning the built SPA. This non-elevated shell also observed `Get-Service Magpie` as `Running` with `StartType Automatic`. |
| Real NSSM service configuration | Passed | `nssm get Magpie Application` returned `backend\.venv\Scripts\python.exe`; `AppDirectory` returned `backend`; `AppParameters` returned `backend\serve.py`; `Start` returned `SERVICE_AUTO_START`; `AppExit Default` returned `Restart`; `AppThrottle` returned `5000`; stdout/stderr logs point to `backend\logs\service-stdout.log` and `backend\logs\service-stderr.log`. |
| NSSM wrapper and Waitress child process | Passed with admin-only command-line caveat | `sc.exe queryex Magpie` reported service PID `1904`; `Get-Process -Id 1904` identified `nssm`; `netstat -ano` showed the port-8000 listener as Python PID `24148` before crash testing, Python PID `27088` after NSSM restart, and Python PID `5804` after reboot. The protected process command line remains unreadable from this non-elevated shell, but NSSM settings show the wrapper launches the repo venv Python with `backend\serve.py`. |
| Real service serves SPA + `/api` + `/admin` + static assets | Passed | On port 8000, `/` returned the built SPA index for `Gold, Stamps & Phonetech`; `/api/health/` returned 200 with `{"status":"ok"}`; `/admin/login/` returned 200; `/inventory/sprint9-final-deep-link` returned the SPA index; `/assets/index-zZJy-lIB.js` returned 200 with `text/javascript`. The built asset did not contain `http://localhost:8000` or `http://127.0.0.1:8000`. |
| Real service LAN IP from host and second LAN device | Passed | `http://192.168.1.86:8000/` returned 200 with the built SPA when requested on the Windows host. Regan confirmed `http://192.168.1.86:8000` works from another LAN device after firewall/network-profile correction, and confirmed after reboot that the Magpie Dashboard loads from `192.168.1.86` on a phone with the expected unauthenticated state. |
| Real service `DEBUG=False` behavior | Passed | `http://localhost:8000/api/definitely-not-a-real-sprint9-route/` returned 404 with a plain Not Found page and no debug markers (`Using the URLconf`, `Request Method:`, `Traceback`, `DEBUG = True`). |
| Real service Host allow-list rejection | Passed | Requesting `http://127.0.0.1:8000/api/health/` with `Host: not-allowed.example` returned HTTP 400 with a plain Bad Request page and no debug markers. |
| Crash-restart by killing Waitress/python | Passed | An elevated proof script killed listener PID `24148`; NSSM restarted Magpie as listener PID `27088`; `Get-Service Magpie` remained `Running` with `StartType Automatic`; `/api/health/` returned 200 with `{"status":"ok"}`. |
| Start-on-boot / reboot survival | Passed | After reboot, Regan did not manually start the service. `Get-Service Magpie` showed `Running`; `netstat -ano` showed `0.0.0.0:8000 LISTENING 5804`; `Invoke-WebRequest http://localhost:8000/api/health/ -UseBasicParsing` returned 200 with `{"status":"ok"}`; `Invoke-WebRequest http://localhost:8000 -UseBasicParsing` returned 200 and served the built SPA. This shell also verified `Magpie` as `Running`/`Automatic`, port 8000 listening on PID `5804`, `/api/health/` returning 200, and `/` serving the built SPA. |

An initial direct local smoke on `127.0.0.1:8000` was blocked by an existing listener on PID 18632 that returned an older DEBUG=True Django 404 for `/api/health/` and DRF 403 for `/api/dashboard/summary/`. PID 18632 was stopped with `Stop-Process -Id 18632 -Force`; port 8000 then had no active listener.

Earlier attempts to install NSSM from this non-Administrator shell failed because service installation requires Administrator access. Regan subsequently installed and started the `Magpie` NSSM service from Administrator PowerShell. The service is now observable as running and automatic, with NSSM configured to launch the repo venv Python and `backend\serve.py`.

## CI Coverage

Configured in `.github\workflows\postgresql-validation.yml` as workflow name `Validation`:

- `sqlite` job: SQLite runtime lane, backend tests, Sprint 8 encrypted backup/restore, frontend tests/typecheck/build, production `collectstatic`, `check --deploy`, and Waitress/WhiteNoise smoke.
- `postgres` job: Postgres service lane, migrations, seed, Sprint 7 schema/fake eBay adapter assertions, and backend tests against Postgres.

Remote GitHub Actions:

- Commit `ce44fa0` triggered `Validation` run `27466714726`, which failed in both jobs at `Run backend tests`.
- The failure was reproduced locally as `test_local_dev_frontend_origin_is_csrf_trusted` when CI set production-only `CSRF_TRUSTED_ORIGINS` globally.
- Commit `4c587e7` removed the global CI CSRF override and made dev settings always include Vite dev CSRF origins even when `.env` is production-shaped.
- Commit `4c587e7` triggered `Validation` run `27467046136`, which completed successfully.
- Commit `8d787a8` triggered `Validation` run `27467084438`; Postgres passed, SQLite failed at `Run frontend tests`. The same frontend suite was rerun locally afterward and passed: 16 files, 43 tests.
- Commit `97ee71d` triggered `Validation` run `27467137542`, which completed successfully on GitHub Actions.
- Commit `8fb35d4` triggered `Validation` run `27478741258`, which completed successfully on GitHub Actions.
- Commit `399ba62` triggered `Validation` run `27478903082`, which completed successfully on GitHub Actions.
- Commit `b175e84` triggered `Validation` run `27480316801`, which completed successfully on GitHub Actions.

## Data Checkout Reconciliation

The proven Sprint 9 service implementation remains the runtime codebase:

`C:\Users\Regan\Documents\Codex\2026-06-13\reasoning-extra-high-i-approve-sprint-2\backend`

The live Sprint 8 business data was promoted from:

`C:\Users\Regan\Documents\Codex\2026-06-11\you-are-starting-a-fresh-codex\backend`

Pre-promotion counts confirmed the mismatch:

| Backend | Items | Photos | Valuations | Drafts | Credential | Media files |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Sprint 9 runtime before promotion | 6 | 0 | 5 | 1 | 0 | 0 |
| Sprint 8 live source | 8 | 2 | 5 | 2 | 1 | 6 |

Promotion steps:

- Stopped the `Magpie` service through an elevated PowerShell script before replacing data.
- Created safety copies of both databases and media trees under `.tmp\data-checkout-reconcile-20260614-091659`.
- Copied the live Sprint 8 `db.sqlite3` and `media_files` into the Sprint 9 runtime backend.
- Restarted the `Magpie` service. The script proof recorded `data_promoted=true`; it hit a late PowerShell variable-name error after promotion, then its recovery path started the service. This shell then verified `Magpie` as `Running`/`Automatic`, port `0.0.0.0:8000` listening on PID `1396`, and `/api/health/` returning 200 with `{"status":"ok"}`.

Post-promotion runtime counts:

| Backend | Items | Photos | Valuations | Drafts | Credential | Media files |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Sprint 9 runtime after promotion | 8 | 2 | 5 | 2 | 1 | 6 |

Post-promotion service checks:

- `http://localhost:8000/api/health/` returned 200 with `{"status":"ok"}`.
- `http://localhost:8000/` returned the built SPA index.
- `http://192.168.1.86:8000/` returned 200 with the built SPA from the Windows host.
- Media render proof: `/media/processed/ac7a39b2-306a-47f4-8a26-21f03d2dc2c8/5c4593f7761d4511b3575002b1c27196.jpg` returned 200 `image/jpeg`; the matching `/media/thumbs/...` URL also returned 200 `image/jpeg`.

Post-promotion encrypted backup proof:

- From the Sprint 9 runtime backend, `DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py backup --output-dir ..\.tmp\data-reconcile-backups --no-upload` produced `magpie-backup-20260613-232008.tar.gz.enc`.
- Restoring that archive into `.tmp\data-reconcile-restore-20260614-092019` produced counts `items=8`, `photos=2`, `valuations=5`, `drafts=2`, `credential=1`, plus 6 restored media files.

Scheduled backup task:

- Before reconciliation, `Magpie Backup` still pointed at the old `2026-06-11` checkout.
- The scheduled task action and working directory were updated through an elevated PowerShell script.
- The captured post-update task XML shows `scripts\backup.ps1` and `Start In` both pointing at the Sprint 9 runtime checkout, and no longer mentions the old checkout.
- The task remains enabled, daily at 02:00, with last recorded result `0` from its prior run.

## Operational Gate Status

All Sprint 9 operational gates are complete.

| Check | Status | Reason |
| --- | --- | --- |
| NSSM service named `Magpie` installed | Passed | Administrator PowerShell and this non-elevated shell both observed the service running; NSSM status is `SERVICE_RUNNING`. |
| Service auto-start on boot | Passed | After reboot, the service was running without manual startup, port 8000 was listening on PID `5804`, localhost health returned 200, and the built SPA loaded locally and from a phone on the LAN. |
| Crash-restart by killing Waitress/python | Passed | Elevated crash test killed PID `24148`; NSSM restarted the listener as PID `27088` and health recovered. |
| `http://192.168.1.86:8000` from another LAN device | Passed | Regan confirmed the LAN URL works from another device after firewall/network-profile correction and remains reachable from a phone after reboot. |

The exact NSSM install, boot-proof, and crash-restart commands are in `DEPLOYMENT.md`.
