# Sprint 8 Restore Drill Evidence

Date: 2026-06-13
Live backend: `C:\Users\Regan\Documents\Codex\2026-06-11\you-are-starting-a-fresh-codex\backend`
Restore target: `C:\Users\Regan\Documents\Codex\2026-06-11\magpie-sprint8-restore-drill`

## Implementation And CI

- Implementation commit: `d7d290f`.
- Evidence update commit before live drill: `d6e80a4`.
- CI: PASS, PostgreSQL Validation run https://github.com/GoldDiggerTriangle/magpie/actions/runs/27462116873.
- Local validation from implementation: backend SQLite tests passed, frontend tests passed, typecheck passed, build passed, and migration check detected no model changes.

## Live Data Backup

- Live source counts before restore drill: items=8, photos=2, valuations=5, drafts=2, credential=1.
- Live media tree exists with 6 files across originals, processed images, and thumbnails.
- Manual command path: `python manage.py backup --output-dir backups --upload --rclone-dest magpie:MagpieBackups --keep-daily 7 --keep-weekly 4`.
- Manual encrypted archive: `magpie-backup-20260613-105908.tar.gz.enc`.
- Local archive size: 294742 bytes.
- Local archive exists: PASS.
- Remote archive exists at `magpie:MagpieBackups`: PASS.
- Archive header is Sprint 8 AES-256-GCM header: PASS.
- Archive opens as plaintext tar: FAIL as expected.
- Plaintext tar cleanup: PASS.

## Restore Drill

- Restore command path: `python manage.py restore <archive> --target <clean-target> --force`.
- Restore result: PASS.
- Django check against restored DB: PASS.

| Dataset | Items | Photos | Valuations | Drafts | Credential |
| --- | ---: | ---: | ---: | ---: | ---: |
| Live source | 8 | 2 | 5 | 2 | 1 |
| Restored target | 8 | 2 | 5 | 2 | 1 |

- Row counts match: PASS.
- Restored media file count: 6.
- Media file counts match source: PASS.
- Photo/media presence is verified by restored `photos_photoasset` rows and restored media files.

## Archive Contents

Temporary decrypt/extract check:

- SQLite snapshot exists: PASS.
- Media tree exists: PASS.
- `env_manifest.json` exists: PASS.
- `env_manifest.json` contains required environment variable names: PASS.
- `env_manifest.json` contains names only, not value maps: PASS.
- `RESTORE_RUNBOOK.md` exists in archive: PASS.

## eBay Restore Handling

- Restored database contains the encrypted eBay credential row count from live source: PASS.
- Token decryption key remains out-of-band and is not in the archive: PASS by archive design.
- Runbook documents the two recovery choices: supply the saved token decryption key locally or reconnect through the eBay browser paste-back flow.

## Logging

- Live rotating log file exists at `backend\logs\magpie.log`: PASS.
- Post-scheduler log size: 904 bytes.
- Rotated siblings at time of drill: 0.
- No-secret marker scan over the live log: PASS.
- Scan output recorded only pass/fail metadata, not marker strings or log content.

## Windows Task Scheduler And Cloud Upload

- Task name: `Magpie Backup`.
- Principal: `Regan`.
- Logon type: Interactive.
- Run level: Limited.
- Trigger: daily at 02:00 local time.
- Manual scheduled task run time: 2026-06-13T21:10:10+10:00.
- Last task result: 0.
- Scheduled-task archive: `magpie-backup-20260613-111034.tar.gz.enc`.
- Scheduled-task local archive size: 294752 bytes.
- Scheduled-task remote upload exists at `magpie:MagpieBackups`: PASS.

## Secret Handling

- No passphrase, rclone token, Google credential, `.env` value, eBay secret, token value, or authorization callback value was copied into this evidence file.
