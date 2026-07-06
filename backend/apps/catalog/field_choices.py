from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

FIELD_CHOICE_REGISTRY_PATH = Path(__file__).with_name("field_choices.json")


def load_field_choice_registry(path: str | Path | None = None) -> dict[str, dict[str, list[str]]]:
    registry_path = Path(
        path
        or os.environ.get("MAGPIE_FIELD_CHOICE_REGISTRY", "")
        or FIELD_CHOICE_REGISTRY_PATH
    )
    with registry_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    registry: dict[str, dict[str, list[str]]] = {}
    for profile_key, fields in raw.items():
        if not isinstance(fields, dict):
            continue
        registry[str(profile_key)] = {
            str(field_name): dedupe_clean(values)
            for field_name, values in fields.items()
            if isinstance(values, list)
        }
    return registry


def field_choice_values(
    profile_key: str,
    field_name: str,
    *,
    extra_values: Iterable[str] = (),
    registry_path: str | Path | None = None,
) -> list[str]:
    registry = load_field_choice_registry(registry_path)
    configured = registry.get(profile_key or "", {}).get(field_name, [])
    return dedupe_clean([*configured, *extra_values])


def live_field_values(profile_key: str, field_name: str) -> list[str]:
    from apps.inventory.models import InventoryItem

    values = []
    queryset = InventoryItem.objects.filter(category__profile_key=profile_key)
    for attributes in queryset.values_list("attributes", flat=True):
        if not isinstance(attributes, dict):
            continue
        value = attributes.get(field_name)
        if value not in {None, ""}:
            values.append(str(value))
    return dedupe_clean(values)


def apply_field_choice_suggestions(
    fields: list[dict],
    profile_key: str,
    *,
    registry_path: str | Path | None = None,
) -> list[dict]:
    configured_fields = load_field_choice_registry(registry_path).get(profile_key or "", {})
    if not configured_fields:
        return fields
    return [
        _with_field_choice_suggestions(
            field,
            profile_key,
            configured_fields,
            registry_path=registry_path,
        )
        for field in fields
    ]


def _with_field_choice_suggestions(
    field: dict,
    profile_key: str,
    configured_fields: dict[str, list[str]],
    *,
    registry_path: str | Path | None = None,
) -> dict:
    next_field = dict(field)
    field_name = str(next_field.get("name") or "")
    if field_name in configured_fields and next_field.get("type") == "str":
        next_field["suggestions"] = field_choice_values(
            profile_key,
            field_name,
            extra_values=live_field_values(profile_key, field_name),
            registry_path=registry_path,
        )
    item_shape = next_field.get("item_shape")
    if isinstance(item_shape, dict):
        next_field["item_shape"] = {
            name: _with_field_choice_suggestions(
                nested,
                profile_key,
                configured_fields,
                registry_path=registry_path,
            )
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
