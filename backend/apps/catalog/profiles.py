"""
Attribute schema registry.
"""

from decimal import Decimal, InvalidOperation

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


class PreciousMetalsSchema:
    profile_key = "gold"
    ALLOWED = {"metal", "weight_g", "fineness", "karat", "form", "notes"}
    METALS = {"gold", "silver", "platinum", "palladium"}
    FORMS = {"specimen", "jewellery", "coin", "scrap", "nugget", "other"}

    def validate(self, attributes: dict) -> dict:
        if not isinstance(attributes, dict):
            raise ValueError("attributes must be an object")

        unknown = sorted(set(attributes) - self.ALLOWED)
        if unknown:
            raise ValueError(f"Unknown precious-metals attribute(s): {', '.join(unknown)}")

        cleaned = dict(attributes)
        metal = str(cleaned.get("metal") or "gold").strip().lower()
        if metal not in self.METALS:
            raise ValueError("metal must be one of gold, silver, platinum, or palladium")
        cleaned["metal"] = metal

        if cleaned.get("weight_g") not in {None, ""}:
            weight = self._decimal(cleaned["weight_g"], "weight_g")
            if weight <= 0:
                raise ValueError("weight_g must be greater than zero")
            cleaned["weight_g"] = str(weight)

        if cleaned.get("fineness") not in {None, ""}:
            fineness = self._decimal(cleaned["fineness"], "fineness")
            if fineness <= 0 or fineness > 1:
                raise ValueError("fineness must be greater than zero and no greater than 1")
            cleaned["fineness"] = str(fineness)

        if cleaned.get("karat") not in {None, ""}:
            karat = self._decimal(cleaned["karat"], "karat")
            if karat < 1 or karat > 24:
                raise ValueError("karat must be between 1 and 24")
            cleaned["karat"] = str(karat)

        if cleaned.get("form") not in {None, ""}:
            form = str(cleaned["form"]).strip().lower()
            if form not in self.FORMS:
                raise ValueError("form is not a supported precious-metals form")
            cleaned["form"] = form

        return {
            key: value
            for key, value in cleaned.items()
            if value is not None and value != ""
        }

    def _decimal(self, value, field_name: str) -> Decimal:
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be a number") from exc


_REGISTRY: dict[str, AttributeSchema] = {}


def register(schema: AttributeSchema) -> None:
    _REGISTRY[schema.profile_key] = schema


def get_schema(profile_key: str) -> AttributeSchema:
    return _REGISTRY.get(profile_key or "", PermissiveSchema())


register(PreciousMetalsSchema())
