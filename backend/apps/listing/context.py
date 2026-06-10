from apps.catalog.profiles import get_schema

from apps.listing.constants import BLOCKED_FIELDS


def safe_context(item) -> dict:
    """Allowlisted item context for listing text and item-specifics generation."""
    category = item.category
    profile_key = category.profile_key if category else ""
    context = {
        "title": item.title or "",
        "condition": item.condition or "",
        "condition_display": item.get_condition_display() if item.condition else "",
        "category": category.name if category else "",
        "profile_key": profile_key or "generic",
    }

    attributes = item.attributes if isinstance(item.attributes, dict) else {}
    schema_fields = get_schema(profile_key).fields()
    allowed_names = {field["name"] for field in schema_fields}

    for name in sorted(allowed_names):
        if name in BLOCKED_FIELDS:
            continue
        if name not in attributes:
            continue
        value = _safe_value(attributes[name])
        if value not in (None, "", [], {}):
            context[name] = value

    cert = context.get("cert")
    if isinstance(cert, dict) and cert.get("cert_no"):
        context["cert_no"] = cert["cert_no"]

    primary_catalogue_ref = _primary_catalogue_ref(context.get("catalogue_refs"))
    if primary_catalogue_ref:
        context["primary_catalogue_ref"] = primary_catalogue_ref

    return context


def _safe_value(value):
    if isinstance(value, dict):
        return {
            key: _safe_value(nested)
            for key, nested in value.items()
            if key not in BLOCKED_FIELDS and _safe_value(nested) not in (None, "", [], {})
        }
    if isinstance(value, list):
        return [
            cleaned
            for cleaned in (_safe_value(entry) for entry in value)
            if cleaned not in (None, "", [], {})
        ]
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    return value


def _primary_catalogue_ref(refs) -> str:
    if not isinstance(refs, list):
        return ""
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        system = str(ref.get("system") or "").strip()
        number = str(ref.get("number") or "").strip()
        value = " ".join(part for part in [system, number] if part)
        if value:
            return value
    return ""
