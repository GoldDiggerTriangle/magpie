from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db import models

from cryptography.fernet import Fernet, InvalidToken


class EncryptedTextField(models.TextField):
    description = "TextField encrypted with MAGPIE_TOKEN_ENCRYPTION_KEY"

    def from_db_value(self, value, expression, connection):
        if value in (None, ""):
            return value
        return _fernet().decrypt(str(value).encode("utf-8")).decode("utf-8")

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value in (None, ""):
            return value
        if _is_existing_ciphertext(str(value)):
            return value
        return _fernet().encrypt(str(value).encode("utf-8")).decode("utf-8")

    def value_to_string(self, obj):
        if obj.pk is None:
            return self.get_prep_value(self.value_from_object(obj))
        return _raw_db_value(obj, self)


def _fernet() -> Fernet:
    key = getattr(settings, "MAGPIE_TOKEN_ENCRYPTION_KEY", "")
    if not key:
        raise ImproperlyConfigured(
            "MAGPIE_TOKEN_ENCRYPTION_KEY is required to encrypt eBay tokens."
        )
    try:
        return Fernet(key.encode("utf-8") if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            "MAGPIE_TOKEN_ENCRYPTION_KEY must be a valid Fernet key."
        ) from exc


def ensure_token_key_configured() -> None:
    _fernet()


def can_decrypt(value: str) -> bool:
    try:
        _fernet().decrypt(value.encode("utf-8"))
    except InvalidToken:
        return False
    return True


def _is_existing_ciphertext(value: str) -> bool:
    if not value.startswith("gAAAAA"):
        return False
    return can_decrypt(value)


def _raw_db_value(obj, field) -> str:
    meta = obj._meta
    qn = connection.ops.quote_name
    sql = (
        f"SELECT {qn(field.column)} FROM {qn(meta.db_table)} "
        f"WHERE {qn(meta.pk.column)} = %s"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, [_db_pk_value(obj.pk)])
        row = cursor.fetchone()
    return "" if row is None or row[0] is None else row[0]


def _db_pk_value(value):
    if connection.vendor == "sqlite" and hasattr(value, "hex"):
        return value.hex
    return value
