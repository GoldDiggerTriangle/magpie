"""
Attribute schema registry.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Protocol


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    type: str
    choices: tuple[str, ...] = ()
    min: Decimal | int | None = None
    max: Decimal | int | None = None
    help_text: str = ""
    item_shape: dict[str, "FieldSpec"] | None = None
    default: str | None = None
    exclusive_min: bool = False

    def as_dict(self) -> dict:
        payload = {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "required": False,
            "choices": list(self.choices),
            "min": str(self.min) if isinstance(self.min, Decimal) else self.min,
            "max": str(self.max) if isinstance(self.max, Decimal) else self.max,
            "help_text": self.help_text,
        }
        if self.item_shape is not None:
            payload["item_shape"] = {
                name: nested.as_dict() for name, nested in self.item_shape.items()
            }
        if self.default is not None:
            payload["default"] = self.default
        if self.exclusive_min:
            payload["exclusive_min"] = True
        return payload


class AttributeSchema(Protocol):
    profile_key: str

    def validate(self, attributes: dict) -> dict: ...

    def fields(self) -> list[dict]: ...


class PermissiveSchema:
    profile_key = ""

    def validate(self, attributes: dict) -> dict:
        if not isinstance(attributes, dict):
            raise ValueError("attributes must be an object")
        return attributes

    def fields(self) -> list[dict]:
        return []


class DefinedFieldsSchema:
    profile_key = ""
    FIELD_SPECS: tuple[FieldSpec, ...] = ()

    def validate(self, attributes: dict) -> dict:
        if not isinstance(attributes, dict):
            raise ValueError("attributes must be an object")

        unknown = sorted(set(attributes) - {spec.name for spec in self.FIELD_SPECS})
        if unknown:
            raise ValueError(
                f"Unknown {self.profile_key or 'item'} attribute(s): {', '.join(unknown)}"
            )

        cleaned = {}
        for spec in self.FIELD_SPECS:
            if spec.name not in attributes:
                continue
            value = self._clean_value(spec, attributes[spec.name], spec.name)
            if value is not None and value != "":
                cleaned[spec.name] = value
        return cleaned

    def fields(self) -> list[dict]:
        return [spec.as_dict() for spec in self.FIELD_SPECS]

    def _clean_value(self, spec: FieldSpec, value, path: str):
        if value is None or value == "":
            return None
        if spec.type == "str":
            return str(value).strip()
        if spec.type == "int":
            return self._clean_int(spec, value, path)
        if spec.type == "decimal":
            return self._clean_decimal(spec, value, path)
        if spec.type == "choice":
            return self._clean_choice(spec, value, path)
        if spec.type == "object":
            return self._clean_object(spec, value, path)
        if spec.type == "list[object]":
            return self._clean_object_list(spec, value, path)
        raise ValueError(f"{path} has unsupported field type: {spec.type}")

    def _clean_int(self, spec: FieldSpec, value, path: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{path} must be an integer")
        try:
            cleaned = int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{path} must be an integer") from exc
        if str(value).strip() not in {str(cleaned), f"+{cleaned}"}:
            raise ValueError(f"{path} must be an integer")
        self._check_bounds(spec, cleaned, path)
        return cleaned

    def _clean_decimal(self, spec: FieldSpec, value, path: str) -> str:
        try:
            cleaned = Decimal(str(value).strip())
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"{path} must be a number") from exc
        self._check_bounds(spec, cleaned, path)
        return str(cleaned)

    def _clean_choice(self, spec: FieldSpec, value, path: str) -> str:
        cleaned = str(value).strip()
        if cleaned not in spec.choices:
            choices = ", ".join(spec.choices)
            raise ValueError(f"{path} must be one of {choices}")
        return cleaned

    def _clean_object(self, spec: FieldSpec, value, path: str) -> dict:
        if not isinstance(value, dict):
            raise ValueError(f"{path} must be an object")
        shape = spec.item_shape or {}
        unknown = sorted(set(value) - set(shape))
        if unknown:
            raise ValueError(f"Unknown {path} attribute(s): {', '.join(unknown)}")

        cleaned = {}
        for nested_name, nested_spec in shape.items():
            nested_value = self._clean_value(
                nested_spec,
                value.get(nested_name),
                f"{path}.{nested_name}",
            )
            if nested_value is None or nested_value == "":
                raise ValueError(f"{path}.{nested_name} is required when {path} is present")
            cleaned[nested_name] = nested_value
        return cleaned

    def _clean_object_list(self, spec: FieldSpec, value, path: str) -> list[dict]:
        if not isinstance(value, list):
            raise ValueError(f"{path} must be a list")
        return [
            self._clean_object(
                FieldSpec(
                    name=spec.name,
                    label=spec.label,
                    type="object",
                    item_shape=spec.item_shape,
                ),
                entry,
                f"{path}[{index}]",
            )
            for index, entry in enumerate(value)
        ]

    def _check_bounds(self, spec: FieldSpec, value: Decimal | int, path: str) -> None:
        if spec.min is not None:
            if spec.exclusive_min and value <= spec.min:
                raise ValueError(f"{path} must be greater than {spec.min}")
            if not spec.exclusive_min and value < spec.min:
                raise ValueError(f"{path} must be at least {spec.min}")
        if spec.max is not None and value > spec.max:
            raise ValueError(f"{path} must be no greater than {spec.max}")


def catalogue_refs_shape(choices: tuple[str, ...]) -> dict[str, FieldSpec]:
    return {
        "system": FieldSpec("system", "System", "choice", choices=choices),
        "number": FieldSpec("number", "Number", "str"),
    }


class PreciousMetalsSchema:
    profile_key = "gold"
    FIELD_SPECS = (
        FieldSpec(
            "metal",
            "Metal",
            "choice",
            choices=("gold", "silver", "platinum", "palladium"),
            default="gold",
        ),
        FieldSpec("weight_g", "Weight g", "decimal", min=Decimal("0"), exclusive_min=True),
        FieldSpec("fineness", "Fineness", "decimal", min=Decimal("0"), max=Decimal("1"), exclusive_min=True),
        FieldSpec("karat", "Karat", "decimal", min=Decimal("1"), max=Decimal("24")),
        FieldSpec(
            "form",
            "Form",
            "choice",
            choices=("specimen", "jewellery", "coin", "scrap", "nugget", "other"),
        ),
        FieldSpec("notes", "Notes", "str"),
    )
    ALLOWED = {spec.name for spec in FIELD_SPECS}
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

    def fields(self) -> list[dict]:
        return [spec.as_dict() for spec in self.FIELD_SPECS]

    def _decimal(self, value, field_name: str) -> Decimal:
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be a number") from exc


class StampSchema(DefinedFieldsSchema):
    profile_key = "stamps"
    FIELD_SPECS = (
        FieldSpec("country", "Country", "str"),
        FieldSpec("year", "Year", "int", min=1840, max=date.today().year + 1),
        FieldSpec("denomination", "Denomination", "str", help_text="Example: 2d or 45c"),
        FieldSpec("face_value_currency", "Face value currency", "str", help_text="Free text for pre-decimal units"),
        FieldSpec("topic_theme", "Topic/theme", "str"),
        FieldSpec(
            "catalogue_refs",
            "Catalogue refs",
            "list[object]",
            item_shape=catalogue_refs_shape(("SG", "Scott", "Michel", "Yvert", "ACSC", "other")),
        ),
        FieldSpec(
            "mint_used",
            "Mint/used",
            "choice",
            choices=("mint_never_hinged", "mint_hinged", "used", "cto", "unknown"),
        ),
        FieldSpec("perforation", "Perforation", "str"),
        FieldSpec("watermark", "Watermark", "str"),
        FieldSpec("variety", "Variety", "str"),
        FieldSpec("colour", "Colour", "str"),
        FieldSpec("notes", "Notes", "str"),
    )


class CoinSchema(DefinedFieldsSchema):
    profile_key = "coins"
    FIELD_SPECS = (
        FieldSpec("country", "Country", "str"),
        FieldSpec("denomination", "Denomination", "str"),
        FieldSpec("mint_mark", "Mint mark", "str"),
        FieldSpec("ruler_or_reign", "Ruler/reign", "str"),
        FieldSpec("year", "Year", "int", min=-1000, max=date.today().year + 1),
        FieldSpec("composition", "Composition", "str", help_text="Example: 92.5% silver"),
        FieldSpec("grade", "Grade", "str", help_text="Suggested: VG, F, VF, EF, aUNC, UNC, or slab grade"),
        FieldSpec(
            "catalogue_refs",
            "Catalogue refs",
            "list[object]",
            item_shape=catalogue_refs_shape(("KM", "Renniks", "other")),
        ),
        FieldSpec("mintage", "Mintage", "int", min=0),
        FieldSpec(
            "cert",
            "Certification",
            "object",
            item_shape={
                "grader": FieldSpec("grader", "Grader", "choice", choices=("PCGS", "NGC", "other")),
                "cert_no": FieldSpec("cert_no", "Cert no.", "str"),
            },
        ),
        FieldSpec("obverse_type", "Obverse type", "str"),
        FieldSpec("reverse_type", "Reverse type", "str"),
        FieldSpec("weight_g", "Weight g", "decimal", min=Decimal("0"), exclusive_min=True),
        FieldSpec("fineness", "Fineness", "decimal", min=Decimal("0"), max=Decimal("1"), exclusive_min=True),
        FieldSpec("notes", "Notes", "str"),
    )


class PhoneSchema(DefinedFieldsSchema):
    profile_key = "phones"
    FIELD_SPECS = (
        FieldSpec("brand", "Brand", "str"),
        FieldSpec("model", "Model", "str"),
        FieldSpec("colour", "Colour", "str"),
        FieldSpec("carrier", "Carrier", "str"),
        FieldSpec("storage_gb", "Storage GB", "int", min=1),
        FieldSpec("ram_gb", "RAM GB", "int", min=1),
        FieldSpec("imei", "IMEI", "str", help_text="Any string accepted this sprint"),
        FieldSpec("serial_no", "Serial no.", "str"),
        FieldSpec(
            "network_status",
            "Network status",
            "choice",
            choices=("unlocked", "carrier_locked", "unknown"),
        ),
        FieldSpec("battery_health_pct", "Battery health %", "int", min=0, max=100),
        FieldSpec("faults", "Faults", "str"),
        FieldSpec("accessories", "Accessories", "str"),
        FieldSpec("notes", "Notes", "str"),
    )


_REGISTRY: dict[str, AttributeSchema] = {}


def register(schema: AttributeSchema) -> None:
    _REGISTRY[schema.profile_key] = schema


def get_schema(profile_key: str) -> AttributeSchema:
    return _REGISTRY.get(profile_key or "", PermissiveSchema())


register(PreciousMetalsSchema())
register(StampSchema())
register(CoinSchema())
register(PhoneSchema())
