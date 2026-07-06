from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

DENOMINATION_REGISTRY_PATH = Path(__file__).with_name("denominations.json")


def load_denomination_registry(path: str | Path | None = None) -> dict[str, list[str]]:
    registry_path = Path(
        path
        or os.environ.get("MAGPIE_DENOMINATION_REGISTRY", "")
        or DENOMINATION_REGISTRY_PATH
    )
    with registry_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return {
        str(profile_key): dedupe_clean(values)
        for profile_key, values in raw.items()
        if isinstance(values, list)
    }


def denomination_values(profile_key: str, *, extra_values: Iterable[str] = ()) -> list[str]:
    registry = load_denomination_registry()
    return dedupe_clean([*registry.get(profile_key or "", []), *extra_values])


def live_denomination_values(profile_key: str) -> list[str]:
    from apps.inventory.models import InventoryItem

    values = []
    queryset = InventoryItem.objects.filter(category__profile_key=profile_key)
    for attributes in queryset.values_list("attributes", flat=True):
        if not isinstance(attributes, dict):
            continue
        value = attributes.get("denomination")
        if value not in {None, ""}:
            values.append(str(value))
    return dedupe_clean(values)


def apply_denomination_suggestions(fields: list[dict], profile_key: str) -> list[dict]:
    suggestions = denomination_values(
        profile_key,
        extra_values=live_denomination_values(profile_key),
    )
    if not suggestions:
        return fields
    return [_with_denomination_suggestions(field, suggestions) for field in fields]


def _with_denomination_suggestions(field: dict, suggestions: list[str]) -> dict:
    next_field = dict(field)
    if next_field.get("name") == "denomination" and next_field.get("type") == "str":
        next_field["suggestions"] = suggestions
    item_shape = next_field.get("item_shape")
    if isinstance(item_shape, dict):
        next_field["item_shape"] = {
            name: _with_denomination_suggestions(nested, suggestions)
            for name, nested in item_shape.items()
        }
    return next_field


def dedupe_clean(values: Iterable[str]) -> list[str]:
    seen = set()
    cleaned = []
    for value in values:
        text = str(value or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned
