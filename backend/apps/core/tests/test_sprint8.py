from __future__ import annotations

import json
import logging
import tarfile
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.catalog.models import ProductCategory
from apps.core.backup_ops import (
    DB_SNAPSHOT_NAME,
    ENCRYPTED_SUFFIX,
    ENV_MANIFEST_NAME,
    MAGIC,
    MEDIA_DIR_NAME,
    RESTORE_RUNBOOK_NAME,
    BackupCryptoError,
    collect_django_row_counts,
    decrypt_file,
    encrypt_file,
    find_secret_markers,
    prune_local_backups,
)
from apps.core.tests.backup_helpers import (
    TEST_BACKUP_PASSPHRASE,
    load_backup_manifest,
    run_encrypted_backup,
    sqlite_count,
)
from apps.inventory.models import InventoryItem
from apps.photos.models import PhotoAsset


def test_encrypt_decrypt_round_trip_and_tamper_detection(tmp_path):
    source = tmp_path / "source.tar.gz"
    encrypted = tmp_path / "source.tar.gz.enc"
    decrypted = tmp_path / "decrypted.tar.gz"
    source.write_bytes((b"magpie durability payload\n" * 1000) + b"end")

    encrypt_file(source, encrypted, TEST_BACKUP_PASSPHRASE, chunk_size=1024)
    assert encrypted.read_bytes().startswith(MAGIC)

    decrypt_file(encrypted, decrypted, TEST_BACKUP_PASSPHRASE)
    assert decrypted.read_bytes() == source.read_bytes()

    tampered = tmp_path / "tampered.tar.gz.enc"
    payload = bytearray(encrypted.read_bytes())
    payload[-1] ^= 1
    tampered.write_bytes(payload)
    with pytest.raises(BackupCryptoError):
        decrypt_file(tampered, tmp_path / "tampered.tar.gz", TEST_BACKUP_PASSPHRASE)


@pytest.mark.django_db(transaction=True)
def test_backup_refuses_without_passphrase(tmp_path, monkeypatch):
    monkeypatch.delenv("MAGPIE_BACKUP_PASSPHRASE", raising=False)
    with pytest.raises(CommandError, match="passphrase"):
        call_command("backup", output_dir=str(tmp_path))


@pytest.mark.django_db(transaction=True)
def test_backup_contains_sqlite_media_manifest_and_runbook(
    tmp_path,
    monkeypatch,
    settings,
):
    if connection.vendor != "sqlite":
        pytest.skip("Sprint 8 backup command is SQLite-only.")

    settings.MEDIA_ROOT = tmp_path / "media"
    media_file = Path(settings.MEDIA_ROOT) / "originals" / "stamp.jpg"
    media_file.parent.mkdir(parents=True)
    media_file.write_bytes(b"fake image bytes")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "not-in-archive-value")

    category = ProductCategory.objects.create(
        name="Sprint 8 Stamps",
        slug="sprint-8-stamps",
        sku_prefix="S8",
    )
    item = InventoryItem.objects.create(title="Restorable stamp", category=category)
    PhotoAsset.objects.create(item=item, original_path="originals/stamp.jpg", is_main=True)

    archive_path, extract_dir = run_encrypted_backup(tmp_path, monkeypatch)

    assert archive_path.name.endswith(ENCRYPTED_SUFFIX)
    assert archive_path.read_bytes().startswith(MAGIC)
    with pytest.raises(tarfile.ReadError):
        tarfile.open(archive_path, "r:gz")

    assert (extract_dir / DB_SNAPSHOT_NAME).exists()
    assert (extract_dir / MEDIA_DIR_NAME / "originals" / "stamp.jpg").read_bytes() == b"fake image bytes"
    assert (extract_dir / ENV_MANIFEST_NAME).exists()
    assert (extract_dir / RESTORE_RUNBOOK_NAME).exists()

    env_manifest_text = (extract_dir / ENV_MANIFEST_NAME).read_text(encoding="utf-8")
    env_manifest = json.loads(env_manifest_text)
    assert "EBAY_CLIENT_SECRET" in env_manifest["env_var_names"]
    assert "not-in-archive-value" not in env_manifest_text

    manifest = load_backup_manifest(extract_dir)
    assert manifest["database_artifact"] == DB_SNAPSHOT_NAME
    assert manifest["row_counts"]["inventory.inventoryitem"] == 1
    assert sqlite_count(extract_dir / DB_SNAPSHOT_NAME, "photos_photoasset") == 1


@pytest.mark.django_db(transaction=True)
def test_backup_row_counts_tolerate_pre_migration_tables(monkeypatch):
    table_names = [
        table_name
        for table_name in connection.introspection.table_names()
        if table_name != "sales_salerecord"
    ]
    monkeypatch.setattr(connection.introspection, "table_names", lambda: table_names)

    counts = collect_django_row_counts()

    assert counts["sales.salerecord"] == 0


@pytest.mark.django_db(transaction=True)
def test_restore_command_restores_to_clean_target_and_refuses_dirty(
    tmp_path,
    monkeypatch,
    settings,
):
    if connection.vendor != "sqlite":
        pytest.skip("Sprint 8 backup command is SQLite-only.")

    settings.MEDIA_ROOT = tmp_path / "media"
    media_file = Path(settings.MEDIA_ROOT) / "processed" / "phone.jpg"
    media_file.parent.mkdir(parents=True)
    media_file.write_bytes(b"processed bytes")

    category = ProductCategory.objects.create(
        name="Sprint 8 Phones",
        slug="sprint-8-phones",
        sku_prefix="P8",
    )
    item = InventoryItem.objects.create(title="Restorable phone", category=category)
    PhotoAsset.objects.create(item=item, original_path="processed/phone.jpg", is_main=True)
    archive_path, _ = run_encrypted_backup(tmp_path, monkeypatch)

    target = tmp_path / "restore-target"
    target.mkdir()
    (target / "dirty.txt").write_text("existing", encoding="utf-8")
    with pytest.raises(CommandError, match="not empty"):
        call_command("restore", str(archive_path), target=str(target))

    call_command("restore", str(archive_path), target=str(target), force=True)

    restored_db = target / DB_SNAPSHOT_NAME
    assert restored_db.exists()
    assert (target / MEDIA_DIR_NAME / "processed" / "phone.jpg").read_bytes() == b"processed bytes"
    assert sqlite_count(restored_db, "inventory_inventoryitem") == 1
    assert sqlite_count(restored_db, "photos_photoasset") == 1


def test_retention_prunes_local_archives(tmp_path):
    filenames = [
        "magpie-backup-20260613-020000.tar.gz.enc",
        "magpie-backup-20260612-020000.tar.gz.enc",
        "magpie-backup-20260611-020000.tar.gz.enc",
        "magpie-backup-20260604-020000.tar.gz.enc",
        "magpie-backup-20260528-020000.tar.gz.enc",
    ]
    for name in filenames:
        (tmp_path / name).write_bytes(b"archive")

    result = prune_local_backups(tmp_path, keep_daily=2, keep_weekly=1)

    kept = {path.name for path in result.kept}
    deleted = {path.name for path in result.deleted}
    assert "magpie-backup-20260613-020000.tar.gz.enc" in kept
    assert "magpie-backup-20260612-020000.tar.gz.enc" in kept
    assert "magpie-backup-20260604-020000.tar.gz.enc" in kept
    assert "magpie-backup-20260611-020000.tar.gz.enc" in deleted
    assert "magpie-backup-20260528-020000.tar.gz.enc" in deleted


def test_secret_marker_scan_catches_crafted_log_lines():
    assert find_secret_markers("refresh_token=fake")
    assert find_secret_markers("client_secret=fake")
    assert find_secret_markers("code=fake")
    assert not find_secret_markers("Created encrypted backup archive example.enc")


def test_logging_handler_writes_and_rotates(tmp_path):
    assert settings.LOGGING["handlers"]["file"]["class"] == "logging.handlers.RotatingFileHandler"

    log_path = tmp_path / "magpie.log"
    handler = RotatingFileHandler(log_path, maxBytes=64, backupCount=1, encoding="utf-8")
    logger = logging.getLogger("tests.sprint8.rotation")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    try:
        logger.info("first durability log line")
        logger.info("second durability log line that forces rotation")
        logger.info("third durability log line that forces rotation")
    finally:
        handler.close()
        logger.handlers = []

    assert log_path.exists()
    assert (tmp_path / "magpie.log.1").exists()
