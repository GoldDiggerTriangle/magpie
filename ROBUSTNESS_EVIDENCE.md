# Sprint 9 Robustness Evidence

Date: 2026-06-13
Repo path: `C:\Users\Regan\Documents\Codex\2026-06-13\reasoning-extra-high-i-approve-sprint-2`

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
| Sprint 8 restore spot check | Passed | `manage.py restore ... --target ..\.tmp\sprint9-restore` restored counts: items=6, photos=0, valuations=5, drafts=1, credential=0. |
| Migrations | Passed | `manage.py makemigrations --check --dry-run --noinput` reported `No changes detected`. |
| `restart servers.txt` removed | Passed | `Test-Path "restart servers.txt"` returned `False`; no file existed in this checkout. |

A direct local smoke on `127.0.0.1:8000` was attempted after the isolated-port smoke. It was blocked by an existing listener on PID 18632 that returned an older DEBUG=True Django 404 for `/api/health/`. That process was not stopped because it was outside this sprint change.

## CI Coverage

Configured in `.github\workflows\postgresql-validation.yml` as workflow name `Validation`:

- `sqlite` job: SQLite runtime lane, backend tests, Sprint 8 encrypted backup/restore, frontend tests/typecheck/build, production `collectstatic`, `check --deploy`, and Waitress/WhiteNoise smoke.
- `postgres` job: Postgres service lane, migrations, seed, Sprint 7 schema/fake eBay adapter assertions, and backend tests against Postgres.

Remote GitHub Actions status was not verified in this local run because no commit/push was performed.

## Operational Gates Still Requiring The Windows Host

These checks require NSSM installed on the host, elevated service control, reboot access, and/or a second LAN device. They were not executed in this sandbox.

| Check | Status | Reason |
| --- | --- | --- |
| NSSM service named `Magpie` installed | Not run | `Get-Command nssm` found no NSSM executable on PATH in this sandbox. |
| Service auto-start on boot | Not run | Requires installing the Windows service and rebooting the host. |
| Crash-restart by killing Waitress/python | Not run | Requires NSSM managing the process; the sandbox smoke used a direct temporary Waitress process. |
| `http://192.168.1.86:8000` from another LAN device | Not run | Requires the host service bound to port 8000 and a second LAN client. |

The exact NSSM install, boot-proof, and crash-restart commands are in `DEPLOYMENT.md`.
