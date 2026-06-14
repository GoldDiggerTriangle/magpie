from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import struct
import tarfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.utils import timezone


ARCHIVE_PREFIX = "magpie-backup"
PLAINTEXT_SUFFIX = ".tar.gz"
ENCRYPTED_SUFFIX = ".tar.gz.enc"
DB_SNAPSHOT_NAME = "db.sqlite3"
MEDIA_DIR_NAME = "media_files"
ENV_MANIFEST_NAME = "env_manifest.json"
BACKUP_MANIFEST_NAME = "backup_manifest.json"
RESTORE_RUNBOOK_NAME = "RESTORE_RUNBOOK.md"

MAGIC = b"MAGPIE-BACKUP-AES256-GCM\n"
VERSION = 1
SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32
CHUNK_SIZE = 1024 * 1024
KDF_N = 2**14
KDF_R = 8
KDF_P = 1

LOCAL_APP_LABELS = {
    "core",
    "catalog",
    "locations",
    "acquisitions",
    "inventory",
    "photos",
    "research",
    "valuation",
    "listing",
    "sales",
    "audit",
    "ebay",
    "dashboard",
    "intelligence",
}

ENV_VAR_NAMES = [
    "DATABASE_URL",
    "SECRET_KEY",
    "ALLOWED_HOSTS",
    "CORS_ALLOWED_ORIGINS",
    "CSRF_TRUSTED_ORIGINS",
    "MAGPIE_TOKEN_ENCRYPTION_KEY",
    "EBAY_ENV",
    "EBAY_CLIENT_ID",
    "EBAY_CLIENT_SECRET",
    "EBAY_RU_NAME",
    "EBAY_SCOPES",
    "METALS_PROVIDER",
    "METALS_API_KEY",
    "MAGPIE_BACKUP_PASSPHRASE",
    "MAGPIE_BACKUP_RCLONE_DEST",
]

KEY_ROW_TABLES = {
    "items": "inventory_inventoryitem",
    "photos": "photos_photoasset",
    "valuations": "valuation_valuationreport",
    "drafts": "listing_listingdraft",
    "sales": "sales_salerecord",
    "ebay_staging": "ebay_ebayorderstaging",
    "ebay_duplicates": "ebay_ebayorderduplicatecandidate",
    "dashboard_preferences": "dashboard_dashboardpreference",
    "field_suggestions": "intelligence_fieldsuggestion",
    "image_fingerprints": "intelligence_imagefingerprint",
    "credential": "ebay_ebaycredential",
}

SECRET_MARKERS = [
    "gAAAA",
    "v^1",
    "code=",
    "refresh_token",
    "client_secret",
    "MAGPIE_TOKEN_ENCRYPTION_KEY",
    "MAGPIE_BACKUP_PASSPHRASE",
]

TIMESTAMP_RE = re.compile(
    rf"^{ARCHIVE_PREFIX}-(?P<date>\d{{8}})-(?P<time>\d{{6}})\.tar\.gz\.enc$"
)


class BackupError(Exception):
    pass


class BackupCryptoError(BackupError):
    pass


@dataclass(frozen=True)
class RetentionResult:
    kept: list[Path]
    deleted: list[Path]


def require_backup_passphrase() -> str:
    passphrase = os.getenv("MAGPIE_BACKUP_PASSPHRASE", "")
    if not passphrase:
        raise BackupError("Backup passphrase environment variable is required.")
    return passphrase


def backup_file_stem(now=None) -> str:
    current = now or timezone.now()
    return f"{ARCHIVE_PREFIX}-{current.strftime('%Y%m%d-%H%M%S')}"


def create_sqlite_snapshot(db_path: Path, snapshot_path: Path) -> None:
    db_path = db_path.resolve()
    if not db_path.exists():
        raise BackupError(f"SQLite database file does not exist: {db_path}")

    src = sqlite3.connect(str(db_path))
    create_sqlite_snapshot_from_connection(src, snapshot_path, close_source=True)


def create_sqlite_snapshot_from_connection(
    src: sqlite3.Connection,
    snapshot_path: Path,
    *,
    close_source: bool = False,
) -> None:
    dst = sqlite3.connect(str(snapshot_path))
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        if close_source:
            src.close()


def copy_media_tree(media_root: Path, destination: Path) -> None:
    media_root = Path(media_root)
    if destination.exists():
        shutil.rmtree(destination)
    if media_root.exists():
        shutil.copytree(media_root, destination)
    else:
        destination.mkdir(parents=True, exist_ok=True)


def write_env_manifest(path: Path) -> None:
    payload = {
        "description": "Environment variable names required to operate Magpie after restore. Values are intentionally excluded.",
        "env_var_names": ENV_VAR_NAMES,
        "out_of_band_secret_names": [
            "MAGPIE_TOKEN_ENCRYPTION_KEY",
            "EBAY_CLIENT_SECRET",
            "MAGPIE_BACKUP_PASSPHRASE",
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_backup_manifest(path: Path) -> None:
    payload = {
        "created_at": timezone.now().isoformat(),
        "database_artifact": DB_SNAPSHOT_NAME,
        "media_artifact": MEDIA_DIR_NAME,
        "row_counts": collect_django_row_counts(),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def collect_django_row_counts() -> dict[str, int]:
    row_counts = {}
    existing_tables = set(connection.introspection.table_names())
    for model in apps.get_models():
        if model._meta.app_label in LOCAL_APP_LABELS:
            if model._meta.db_table in existing_tables:
                row_counts[model._meta.label_lower] = model.objects.count()
            else:
                row_counts[model._meta.label_lower] = 0
    return row_counts


def create_tar_gz(source_dir: Path, tar_path: Path) -> None:
    with tarfile.open(tar_path, "w:gz") as archive:
        for child in sorted(source_dir.iterdir(), key=lambda p: p.name):
            archive.add(child, arcname=child.name, recursive=True)


def safe_extract_tar(tar_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with tarfile.open(tar_path, "r:gz") as archive:
        for member in archive.getmembers():
            target = (destination / member.name).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise BackupError(f"Unsafe path in archive: {member.name}") from exc
        archive.extractall(destination, filter="data")


def encrypt_file(
    source_path: Path,
    encrypted_path: Path,
    passphrase: str,
    *,
    chunk_size: int = CHUNK_SIZE,
) -> None:
    salt = os.urandom(SALT_SIZE)
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)

    with source_path.open("rb") as source, encrypted_path.open("wb") as dest:
        dest.write(MAGIC)
        dest.write(bytes([VERSION]))
        dest.write(salt)
        chunk_index = 0
        while True:
            chunk = source.read(chunk_size)
            if not chunk:
                break
            nonce = os.urandom(NONCE_SIZE)
            ciphertext = aesgcm.encrypt(
                nonce,
                chunk,
                _record_aad(salt, chunk_index),
            )
            dest.write(struct.pack(">I", len(ciphertext)))
            dest.write(nonce)
            dest.write(ciphertext)
            chunk_index += 1


def decrypt_file(encrypted_path: Path, output_path: Path, passphrase: str) -> None:
    with encrypted_path.open("rb") as source:
        magic = source.read(len(MAGIC))
        if magic != MAGIC:
            raise BackupCryptoError("Encrypted archive header is not recognized.")
        version = source.read(1)
        if version != bytes([VERSION]):
            raise BackupCryptoError("Encrypted archive version is not supported.")
        salt = source.read(SALT_SIZE)
        if len(salt) != SALT_SIZE:
            raise BackupCryptoError("Encrypted archive header is incomplete.")

        key = _derive_key(passphrase, salt)
        aesgcm = AESGCM(key)
        chunk_index = 0
        with output_path.open("wb") as dest:
            while True:
                length_bytes = source.read(4)
                if not length_bytes:
                    break
                if len(length_bytes) != 4:
                    raise BackupCryptoError("Encrypted archive record is truncated.")
                (length,) = struct.unpack(">I", length_bytes)
                nonce = source.read(NONCE_SIZE)
                ciphertext = source.read(length)
                if len(nonce) != NONCE_SIZE or len(ciphertext) != length:
                    raise BackupCryptoError("Encrypted archive record is truncated.")
                try:
                    plaintext = aesgcm.decrypt(
                        nonce,
                        ciphertext,
                        _record_aad(salt, chunk_index),
                    )
                except InvalidTag as exc:
                    raise BackupCryptoError("Encrypted archive authentication failed.") from exc
                dest.write(plaintext)
                chunk_index += 1


def count_key_rows(db_path: Path) -> dict[str, int]:
    counts = {}
    conn = sqlite3.connect(str(db_path))
    try:
        for label, table_name in KEY_ROW_TABLES.items():
            if _sqlite_table_exists(conn, table_name):
                cursor = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                counts[label] = int(cursor.fetchone()[0])
            else:
                counts[label] = 0
    finally:
        conn.close()
    return counts


def prune_local_backups(
    output_dir: Path,
    *,
    keep_daily: int,
    keep_weekly: int,
) -> RetentionResult:
    candidates = []
    for path in output_dir.glob(f"{ARCHIVE_PREFIX}-*{ENCRYPTED_SUFFIX}"):
        parsed = parse_backup_timestamp(path.name)
        if parsed is not None:
            candidates.append((parsed, path))
    candidates.sort(key=lambda item: item[0], reverse=True)

    keep: set[Path] = set()
    daily_dates = set()
    daily_weeks = set()
    weekly_keys = set()

    for created_at, path in candidates:
        if len(daily_dates) < keep_daily and created_at.date() not in daily_dates:
            keep.add(path)
            daily_dates.add(created_at.date())
            daily_weeks.add(created_at.isocalendar()[:2])

    if not keep and candidates:
        created_at, path = candidates[0]
        keep.add(path)
        daily_weeks.add(created_at.isocalendar()[:2])

    for created_at, path in candidates:
        if path in keep:
            continue
        week_key = created_at.isocalendar()[:2]
        if (
            len(weekly_keys) < keep_weekly
            and week_key not in weekly_keys
            and week_key not in daily_weeks
        ):
            keep.add(path)
            weekly_keys.add(week_key)

    deleted = []
    for _, path in candidates:
        if path not in keep:
            path.unlink()
            deleted.append(path)

    return RetentionResult(
        kept=[path for _, path in candidates if path in keep],
        deleted=deleted,
    )


def parse_backup_timestamp(filename: str) -> datetime | None:
    match = TIMESTAMP_RE.match(filename)
    if not match:
        return None
    return datetime.strptime(
        f"{match.group('date')}{match.group('time')}",
        "%Y%m%d%H%M%S",
    )


def rclone_remote_name(destination: str) -> str:
    if ":" not in destination:
        return "configured-destination"
    return destination.split(":", 1)[0] or "configured-destination"


def find_secret_markers(text: str, markers: Iterable[str] = SECRET_MARKERS) -> list[str]:
    lowered = text.lower()
    return [marker for marker in markers if marker.lower() in lowered]


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(
        salt=salt,
        length=KEY_SIZE,
        n=KDF_N,
        r=KDF_R,
        p=KDF_P,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def _record_aad(salt: bytes, chunk_index: int) -> bytes:
    return MAGIC + bytes([VERSION]) + salt + chunk_index.to_bytes(8, "big")


def _sqlite_table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    cursor = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        [table_name],
    )
    return cursor.fetchone() is not None
