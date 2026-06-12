from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone

import integrations.ebay as ebay_integration
from apps.audit.services import record
from apps.ebay.constants import (
    AUDIT_TAXONOMY_ASPECTS_FETCHED,
    AUDIT_TAXONOMY_CATEGORY_SUGGESTED,
    EBAY_ENV_PRODUCTION,
    EBAY_MARKETPLACE_ID,
)
from apps.ebay.services import get_app_access_token


_ASPECT_CACHE: dict[str, dict] = {}


@dataclass(frozen=True)
class AspectCheck:
    satisfied_required: list[str]
    missing_required: list[str]
    optional_known: list[str]
    unmapped_specifics: list[str]
    aspects: list[dict]
    fetched_at: str | None

    def as_dict(self) -> dict:
        return {
            "satisfied_required": self.satisfied_required,
            "missing_required": self.missing_required,
            "optional_known": self.optional_known,
            "unmapped_specifics": self.unmapped_specifics,
            "aspects": self.aspects,
            "fetched_at": self.fetched_at,
        }


def suggest_categories(*, q: str, actor=None) -> dict:
    environment = ebay_integration.effective_environment()
    if environment != EBAY_ENV_PRODUCTION:
        return {"supported": False, "suggestions": [], "detail": "Category suggestions are unavailable outside production."}
    access_token = get_app_access_token()
    suggestions = ebay_integration.get_ebay_taxonomy_adapter(
        access_token=access_token,
    ).suggest_categories(q=q)
    record(
        actor=actor,
        action=AUDIT_TAXONOMY_CATEGORY_SUGGESTED,
        target_type="ebay_category",
        payload={
            "environment": environment,
            "query": q,
            "count": len(suggestions),
        },
    )
    return {"supported": True, "suggestions": suggestions}


def get_category_aspects(*, category_id: str, actor=None) -> dict:
    category_id = str(category_id)
    cached = _ASPECT_CACHE.get(category_id)
    if cached:
        return cached
    access_token = get_app_access_token()
    adapter = ebay_integration.get_ebay_taxonomy_adapter(access_token=access_token)
    aspects = adapter.item_aspects(category_id=category_id)
    fetched_at = timezone.now().isoformat()
    payload = {
        "category_id": category_id,
        "marketplace": EBAY_MARKETPLACE_ID,
        "aspects": aspects,
        "fetched_at": fetched_at,
    }
    _ASPECT_CACHE[category_id] = payload
    record(
        actor=actor,
        action=AUDIT_TAXONOMY_ASPECTS_FETCHED,
        target_type="ebay_category",
        target_id=category_id,
        payload={
            "category_id": category_id,
            "aspect_count": len(aspects),
            "required_count": len([aspect for aspect in aspects if aspect.get("required")]),
            "fetched_at": fetched_at,
        },
    )
    return payload


def check_aspects(draft, *, actor=None) -> dict:
    category_id = str((draft.channel_data or {}).get("category_id") or "")
    if not category_id:
        return AspectCheck([], ["category_id"], [], [], [], None).as_dict()

    category_aspects = get_category_aspects(category_id=category_id, actor=actor)
    aspects = category_aspects["aspects"]
    known = {normalize_name(aspect.get("name")): aspect for aspect in aspects}
    specifics = {
        normalize_name(row.get("name")): row.get("name")
        for row in draft.item_specifics or []
        if isinstance(row, dict) and str(row.get("name") or "").strip() and str(row.get("value") or "").strip()
    }

    satisfied_required: list[str] = []
    missing_required: list[str] = []
    optional_known: list[str] = []

    for aspect in aspects:
        name = str(aspect.get("name") or "")
        normalized = normalize_name(name)
        if aspect.get("required"):
            if normalized in specifics:
                satisfied_required.append(name)
            else:
                missing_required.append(name)
        elif normalized in specifics:
            optional_known.append(name)

    unmapped_specifics = [
        original for normalized, original in specifics.items() if normalized not in known
    ]
    return AspectCheck(
        satisfied_required=satisfied_required,
        missing_required=missing_required,
        optional_known=optional_known,
        unmapped_specifics=unmapped_specifics,
        aspects=aspects,
        fetched_at=category_aspects.get("fetched_at"),
    ).as_dict()


def normalize_name(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())
