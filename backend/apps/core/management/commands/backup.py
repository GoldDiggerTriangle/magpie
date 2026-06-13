from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.core.backup_ops import (
    BACKUP_MANIFEST_NAME,
    DB_SNAPSHOT_NAME,
    ENCRYPTED_SUFFIX,
    ENV_MANIFEST_NAME,
    MEDIA_DIR_NAME,
    PLAINTEXT_SUFFIX,
    RESTORE_RUNBOOK_NAME,
    BackupError,
    backup_file_stem,
    copy_media_tree,
    create_sqlite_snapshot_from_connection,
    create_tar_gz,
    encrypt_file,
    prune_local_backups,
    rclone_remote_name,
    require_backup_passphrase,
    write_backup_manifest,
    write_env_manifest,
)


logger = logging.getLogger("apps.core.backup")


class Command(BaseCommand):
    help = "Create an encrypted Sprint 8 SQLite and media backup archive."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=str(settings.BASE_DIR / "backups"),
            help="Directory where encrypted backup archives should be written.",
        )
        parser.add_argument(
            "--upload",
            dest="upload",
            action="store_true",
            default=False,
            help="Upload the encrypted archive with rclone after local creation.",
        )
        parser.add_argument(
            "--no-upload",
            dest="upload",
            action="store_false",
            help="Create only the local encrypted archive.",
        )
        parser.add_argument(
            "--rclone-dest",
            default="",
            help="rclone destination in remote:path form. Defaults to MAGPIE_BACKUP_RCLONE_DEST.",
        )
        parser.add_argument(
            "--keep-daily",
            type=int,
            default=7,
            help="Number of daily local encrypted archives to retain.",
        )
        parser.add_argument(
            "--keep-weekly",
            type=int,
            default=4,
            help="Number of older weekly local encrypted archives to retain.",
        )

    def handle(self, *args, **options):
        try:
            passphrase = require_backup_passphrase()
            self._ensure_sqlite_database()
        except BackupError as exc:
            raise CommandError(str(exc)) from exc

        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = backup_file_stem()
        tar_path = output_dir / f"{stem}{PLAINTEXT_SUFFIX}"
        encrypted_path = output_dir / f"{stem}{ENCRYPTED_SUFFIX}"

        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            workspace = temp_dir / "payload"
            workspace.mkdir()

            create_sqlite_snapshot_from_connection(
                connection.connection,
                workspace / DB_SNAPSHOT_NAME,
            )
            copy_media_tree(Path(settings.MEDIA_ROOT), workspace / MEDIA_DIR_NAME)
            write_env_manifest(workspace / ENV_MANIFEST_NAME)
            write_backup_manifest(workspace / BACKUP_MANIFEST_NAME)
            self._copy_restore_runbook(workspace / RESTORE_RUNBOOK_NAME)

            create_tar_gz(workspace, tar_path)
            try:
                encrypt_file(tar_path, encrypted_path, passphrase)
            finally:
                tar_path.unlink(missing_ok=True)

        retention = prune_local_backups(
            output_dir,
            keep_daily=max(options["keep_daily"], 0),
            keep_weekly=max(options["keep_weekly"], 0),
        )

        logger.info(
            "Created encrypted backup archive %s (%s bytes); pruned %s local archive(s).",
            encrypted_path.name,
            encrypted_path.stat().st_size,
            len(retention.deleted),
        )

        if options["upload"]:
            self._upload_with_rclone(encrypted_path, options["rclone_dest"])

        self.stdout.write(
            self.style.SUCCESS(f"Encrypted backup written to {encrypted_path}")
        )

    def _ensure_sqlite_database(self) -> None:
        connection.ensure_connection()
        if connection.vendor != "sqlite":
            raise BackupError(
                f"Sprint 8 backup requires SQLite; current database vendor is {connection.vendor}."
            )

    def _copy_restore_runbook(self, destination: Path) -> None:
        source = settings.BASE_DIR / "RESTORE_RUNBOOK.md"
        if not source.exists():
            raise CommandError(f"Restore runbook is missing: {source}")
        shutil.copy2(source, destination)

    def _upload_with_rclone(self, archive_path: Path, destination: str) -> None:
        destination = destination or os.getenv("MAGPIE_BACKUP_RCLONE_DEST", "")
        if not destination:
            raise CommandError("rclone upload destination is not configured.")
        if shutil.which("rclone") is None:
            raise CommandError("rclone is not available on PATH.")

        result = subprocess.run(
            ["rclone", "copy", str(archive_path), destination],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            logger.error(
                "rclone upload failed for %s to remote %s with exit code %s.",
                archive_path.name,
                rclone_remote_name(destination),
                result.returncode,
            )
            raise CommandError(f"rclone upload failed with exit code {result.returncode}.")

        logger.info(
            "Uploaded encrypted backup archive %s to rclone remote %s.",
            archive_path.name,
            rclone_remote_name(destination),
        )
