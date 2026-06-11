from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from apps.audit.models import AuditLog


SECRET_KEY_FRAGMENTS = {
    "access",
    "authorization",
    "auth_code",
    "bearer",
    "client_secret",
    "code",
    "password",
    "refresh",
    "secret",
    "token",
}


def record(
    *,
    actor=None,
    action: str,
    target_type: str = "",
    target_id: str = "",
    payload: Mapping[str, Any] | None = None,
) -> AuditLog:
    return AuditLog.objects.create(
        actor=_actor_label(actor),
        action=action,
        target_type=target_type,
        target_id=str(target_id or ""),
        payload=sanitize_payload(payload or {}),
    )


def sanitize_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized = {}
        for key, child in value.items():
            key_text = str(key)
            if _is_secret_key(key_text):
                continue
            sanitized[key_text] = sanitize_payload(child)
        return sanitized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [sanitize_payload(child) for child in value]
    if isinstance(value, bytes):
        return "[bytes]"
    return value


def _actor_label(actor) -> str:
    if actor is None:
        return "system"
    if isinstance(actor, str):
        return actor[:120]
    if getattr(actor, "is_authenticated", False):
        username = getattr(actor, "get_username", lambda: "")()
        return (username or str(getattr(actor, "pk", "")))[:120]
    return "system"


def _is_secret_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(fragment in normalized for fragment in SECRET_KEY_FRAGMENTS)
