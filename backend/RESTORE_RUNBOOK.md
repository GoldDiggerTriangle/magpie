# Magpie Restore Runbook

This runbook is bundled into every encrypted Sprint 8 backup archive. It describes the restore path only; it does not contain secret values.

## Required Out-of-Band Material

Keep these in the password manager, not in Git, logs, evidence files, chat, or backup notes:

- Backup archive passphrase.
- Token decryption key used by Magpie's eBay credential fields.
- eBay application secret material, including the Cert ID/client secret.
- rclone remote credentials.

## Restore To A Clean Directory

1. Install the normal Magpie Python dependencies.
2. Configure the backup archive passphrase in the local shell environment.
3. Run:

   ```powershell
   cd "<repo>\backend"
   python manage.py restore "<path>\magpie-backup-YYYYMMDD-HHMMSS.tar.gz.enc" --target "<clean-restore-dir>"
   ```

4. Confirm the restored target contains:

   ```text
   db.sqlite3
   media_files\
   ```

5. Point a local Magpie process at the restored SQLite file only after you have verified the target path:

   ```powershell
   $env:DATABASE_URL = "sqlite:///<clean-restore-dir>/db.sqlite3"
   python manage.py check
   ```

6. Confirm row counts printed by the restore command match the source evidence.
7. Confirm the media tree exists and expected photos are present under `media_files`.

## eBay Credential Handling After Restore

The restored database contains encrypted eBay credential rows, but it does not contain the key required to decrypt them. On a new machine, either supply the saved token decryption key from the password manager or reconnect eBay through Magpie's browser paste-back flow before using eBay features.

If the key is unavailable, treat the restored eBay credential row as unusable and reconnect through eBay OAuth. Do not attempt to recover the key from backup artifacts; it is intentionally excluded.

## Cloud Copy

The built-in backup command uploads only when `--upload` is passed and rclone is configured locally. rclone credentials stay in the operator's local rclone configuration. Remote retention is intentionally not automated in Sprint 8; configure provider lifecycle rules or a later operational policy if remote pruning is required.

## Linux Note For Future Migration

The same Django commands can run under a future Linux systemd timer, but Sprint 8 does not change the runtime platform or deployment model.
