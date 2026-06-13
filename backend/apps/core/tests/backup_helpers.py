from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from django.core.management import call_command
from django.db import connection

from apps.core.backup_ops import (
    BACKUP_MANIFEST_NAME,
    ENCRYPTED_SUFFIX,
    safe_extract_tar,
    decrypt_file,
)


TEST_BACKUP_PASSPHRASE = "unit-test-backup-passphrase"


def run_encrypted_backup(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    if connection.vendor != "sqlite":
        pytest.skip("Sprint 8 backup command is SQLite-only.")
    monkeypatch.setenv("MAGPIE_BACKUP_PASSPHRASE", TEST_BACKUP_PASSPHRASE)
    call_command("backup", output_dir=str(tmp_path))
    archive_path = sorted(tmp_path.glob(f"magpie-backup-*{ENCRYPTED_SUFFIX}"))[-1]
    return archive_path, extract_encrypted_backup(archive_path, tmp_path)


def extract_encrypted_backup(archive_path: Path, tmp_path: Path) -> Path:
    tar_path = tmp_path / "decrypted-backup.tar.gz"
    extract_dir = tmp_path / "decrypted-backup"
    decrypt_file(archive_path, tar_path, TEST_BACKUP_PASSPHRASE)
    safe_extract_tar(tar_path, extract_dir)
    return extract_dir


def load_backup_manifest(extract_dir: Path) -> dict:
    return json.loads((extract_dir / BACKUP_MANIFEST_NAME).read_text(encoding="utf-8"))


def sqlite_count(db_path: Path, table_name: str) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        return int(cursor.fetchone()[0])
    finally:
        conn.close()


def sqlite_column_values(db_path: Path, table_name: str, *columns: str) -> list[tuple]:
    column_sql = ", ".join(f'"{column}"' for column in columns)
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(f'SELECT {column_sql} FROM "{table_name}"')
        return list(cursor.fetchall())
    finally:
        conn.close()
