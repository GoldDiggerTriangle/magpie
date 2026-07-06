from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

IDENTIFY_SCOPE_REGISTRY_PATH = Path(__file__).with_name("identify_scope.json")


def load_identify_scope_registry(path: str | Path | None = None) -> dict[str, dict]:
    registry_path = Path(
        path
        or os.environ.get("MAGPIE_IDENTIFY_SCOPE_REGISTRY", "")
        or IDENTIFY_SCOPE_REGISTRY_PATH
    )
    with registry_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return {
        str(profile_key): _normalise_scope(scope)
        for profile_key, scope in raw.items()
        if isinstance(scope, dict)
    }


def build_identify_scope(profile_key: str, *, registry_path: str | Path | None = None) -> dict:
    return load_identify_scope_registry(registry_path).get(profile_key or "", _normalise_scope({}))


def _normalise_scope(scope: dict) -> dict:
    return {
        "fields": _dedupe(scope.get("fields", [])),
        "candidate_fields": _dedupe(scope.get("candidate_fields", [])),
        "observation_fields": _dedupe(scope.get("observation_fields", [])),
        "copywriting_drafts": _dedupe(scope.get("copywriting_drafts", [])),
        "notes": str(scope.get("notes", "") or ""),
    }


def _dedupe(values: Iterable[str]) -> list[str]:
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
