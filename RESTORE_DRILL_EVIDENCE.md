# Sprint 8 Restore Drill Evidence

Date: 2026-06-13
Workspace: clean Magpie clone for Sprint 8 implementation

## Local Validation

- Django check: PASS.
- Migration check: PASS, no model changes detected.
- Backend tests on SQLite: PASS, 92 passed and 1 skipped.
- Frontend tests: PASS, 43 passed across 16 files.
- Frontend typecheck: PASS.
- Frontend production build: PASS.

## Backup And Restore Drill

- Command path: `python manage.py backup --output-dir backups --no-upload`.
- Result: PASS, encrypted `.tar.gz.enc` archive created locally.
- Plaintext tar cleanup: PASS, backup command deletes the plaintext tar after encryption.
- Restore command path: `python manage.py restore <archive> --target ..\.restore-drill --force`.
- Result: PASS, restore completed into a clean target.
- App boot check against restored DB: PASS, `python manage.py check` reported no issues.

## Row Counts

This clone did not include the live SQLite database or live media tree described in the Sprint 8 spec. The completed drill used the repository seed data.

| Dataset | Items | Photos | Valuations | Drafts | Credential |
| --- | ---: | ---: | ---: | ---: | ---: |
| Seed source | 6 | 0 | 5 | 1 | 0 |
| Restored target | 6 | 0 | 5 | 1 | 0 |

Live-data acceptance remains pending until the drill is rerun in the checkout containing the live SQLite database and media tree.

## Media

- Restored media tree: PASS, `media_files` was restored.
- Photo render/presence check against live data: PENDING, because this clean clone's seed dataset has no photo rows or live media files.

## Archive Contents

Covered by automated Sprint 8 tests:

- SQLite snapshot present.
- Media tree present.
- Environment-name manifest present and value-free.
- Restore runbook present.
- Archive is encrypted and not a readable plaintext tar.
- AES-GCM tamper detection raises loudly.

## Logging

- `backend\logs\magpie.log` exists after command execution.
- Rotating handler behavior: PASS in automated test.
- Secret-marker log scan: PASS.
- Log scan output recorded only pass/fail and byte count; no marker strings or secret values were copied here.

## eBay Reconnect Handling

- Documented in bundled restore runbook: PASS.
- Live restored credential usability check: PENDING, because the seed dataset has no credential row. A live restore requires either the out-of-band token decryption key or a reconnect through the browser paste-back flow.

## Scheduler And Cloud Upload

- Windows PowerShell backup wrapper: ADDED at `scripts\backup.ps1`.
- Task Scheduler runbook: ADDED at `docs\WINDOWS_TASK_SCHEDULER_BACKUP.md`.
- Scheduled unattended backup fire: PENDING.
- Cloud upload: PENDING.

Per instruction, no cloud-upload test has been run. Before that test, the rclone remote and backup archive passphrase must be configured locally by the operator. Do not paste secret values into chat or evidence.

## CI

- Workflow updated to keep PostgreSQL schema validation while running backup/restore coverage on SQLite.
- Remote CI status: PASS.
- Workflow: PostgreSQL Validation.
- Commit: `d7d290f`.
- Run: https://github.com/GoldDiggerTriangle/magpie/actions/runs/27462116873.
