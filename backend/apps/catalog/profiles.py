"""
Attribute schema registry. Sprint 0 keeps the default validator permissive.

Later phases can register real per-category schemas without changing the
InventoryItem table shape.
"""

from typing import Protocol


class AttributeSchema(Protocol):
    profile_key: str

    def validate(self, attributes: dict) -> dict: ...


class PermissiveSchema:
    profile_key = ""

    def validate(self, attributes: dict) -> dict:
        if not isinstance(attributes, dict):
            raise ValueError("attributes must be an object")
        return attributes


_REGISTRY: dict[str, AttributeSchema] = {}


def register(schema: AttributeSchema) -> None:
    _REGISTRY[schema.profile_key] = schema


def get_schema(profile_key: str) -> AttributeSchema:
    return _REGISTRY.get(profile_key or "", PermissiveSchema())
