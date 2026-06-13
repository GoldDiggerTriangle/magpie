from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.backup_ops import (
    DB_SNAPSHOT_NAME,
    MEDIA_DIR_NAME,
    BackupCryptoError,
    BackupError,
    count_key_rows,
    decrypt_file,
    require_backup_passphrase,
    safe_extract_tar,
)


logger = logging.getLogger("apps.core.backup")


class Command(BaseCommand):
    help = "Decrypt and restore a Sprint 8 encrypted backup archive into a clean target."

    def add_arguments(self, parser):
        parser.add_argument("archive", help="Path to a .tar.gz.enc backup archive.")
        parser.add_argument(
            "--target",
            required=True,
            help="Clean directory where db.sqlite3 and media_files should be restored.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Clear an existing non-empty target directory before restore.",
        )

    def handle(self, *args, **options):
        archive_path = Path(options["archive"]).resolve()
        target = Path(options["target"]).resolve()
        if not archive_path.exists():
            raise CommandError(f"Backup archive does not exist: {archive_path}")
        self._prepare_target(target, force=options["force"])

        try:
            passphrase = require_backup_passphrase()
        except BackupError as exc:
            raise CommandError(str(exc)) from exc

        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            tar_path = temp_dir / "backup.tar.gz"
            extracted = temp_dir / "extracted"
            try:
                decrypt_file(archive_path, tar_path, passphrase)
                safe_extract_tar(tar_path, extracted)
            except (BackupCryptoError, BackupError) as exc:
                raise CommandError(str(exc)) from exc

            source_db = extracted / DB_SNAPSHOT_NAME
            source_media = extracted / MEDIA_DIR_NAME
            if not source_db.exists():
                raise CommandError("Backup archive does not contain a SQLite snapshot.")
            if not source_media.exists():
                raise CommandError("Backup archive does not contain a media tree.")

            shutil.copy2(source_db, target / DB_SNAPSHOT_NAME)
            shutil.copytree(source_media, target / MEDIA_DIR_NAME)

        counts = count_key_rows(target / DB_SNAPSHOT_NAME)
        logger.info(
            "Restored encrypted backup %s to %s with key row counts %s.",
            archive_path.name,
            target,
            counts,
        )
        self.stdout.write(self.style.SUCCESS(f"Restore written to {target}"))
        self.stdout.write(
            "Row counts: "
            + ", ".join(f"{label}={count}" for label, count in counts.items())
        )
        self.stdout.write(
            "eBay reconnect reminder: supply the saved token decryption key or reconnect via the browser paste-back flow before using restored eBay credentials."
        )

    def _prepare_target(self, target: Path, *, force: bool) -> None:
        if target.exists() and not target.is_dir():
            raise CommandError(f"Restore target is not a directory: {target}")
        if target.exists() and any(target.iterdir()):
            if not force:
                raise CommandError("Restore target is not empty; pass --force to clear it.")
            for child in target.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        target.mkdir(parents=True, exist_ok=True)
