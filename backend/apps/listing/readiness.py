from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation

from apps.inventory.models import InventoryItem
from apps.listing.constants import EBAY_TITLE_MAX
from apps.photos.models import PhotoAsset


@dataclass
class Check:
    key: str
    level: str
    message: str

    def as_dict(self) -> dict:
        return asdict(self)


def check_readiness(draft) -> list[Check]:
    checks = []
    checks.extend(_fail_checks(draft))
    checks.extend(_warn_checks(draft))
    return checks


def readiness_summary(draft) -> dict:
    checks = check_readiness(draft)
    return {
        "fail_count": sum(1 for check in checks if check.level == "fail"),
        "warn_count": sum(1 for check in checks if check.level == "warn"),
        "pass_count": sum(1 for check in checks if check.level == "pass"),
    }


def has_failures(draft) -> bool:
    return any(check.level == "fail" for check in check_readiness(draft))


def _fail_checks(draft) -> list[Check]:
    photo_resolution = resolve_photo_ids(draft)
    return [
        _check(
            "no_photos",
            bool(draft.photo_ids),
            "At least one processed photo is selected.",
            "No listing photos selected.",
        ),
        _check(
            "title_missing",
            bool(str(draft.title or "").strip()),
            "Title is present.",
            "Title is required.",
        ),
        _check(
            "title_too_long",
            len(str(draft.title or "")) <= EBAY_TITLE_MAX,
            f"Title is at or below {EBAY_TITLE_MAX} characters.",
            f"Title is longer than {EBAY_TITLE_MAX} characters.",
        ),
        _check(
            "description_missing",
            bool(str(draft.description_html or "").strip()),
            "Description is present.",
            "Description is required.",
        ),
        _check(
            "price_invalid",
            _positive_decimal(draft.price),
            "Price is greater than zero.",
            "Price must be greater than zero.",
        ),
        _check(
            "quantity_invalid",
            int(draft.quantity or 0) > 0,
            "Quantity is greater than zero.",
            "Quantity must be greater than zero.",
        ),
        _check(
            "item_unavailable",
            draft.item.status
            not in {InventoryItem.Status.SOLD, InventoryItem.Status.ARCHIVED},
            "Item is available to list.",
            "Sold or archived items cannot be marked ready.",
        ),
        *_leak_checks(draft),
        _check(
            "photos_unresolvable",
            not photo_resolution["missing"],
            "All selected photos resolve to processed variants.",
            "Some selected photos are missing processed variants: "
            + ", ".join(photo_resolution["missing"]),
        ),
    ]


def _warn_checks(draft) -> list[Check]:
    item = draft.item
    profile_key = item.category.profile_key if item.category else ""
    resolved_count = len(resolve_photo_ids(draft)["photos"])
    price = _decimal_or_none(draft.price)
    min_price = _current_min_acceptable_price(item)
    true_cost = _true_cost_for_item(item)
    description = str(draft.description_html or "").lower()
    return [
        _warn(
            "fewer_than_3_photos",
            resolved_count >= 3,
            "Three or more processed photos selected.",
            "Fewer than three processed photos selected.",
        ),
        _warn(
            "condition_missing",
            bool(item.condition and item.condition != InventoryItem.Condition.UNGRADED),
            "Condition is set.",
            "Condition is missing or unknown.",
        ),
        _warn(
            "category_missing",
            item.category_id is not None,
            "Category is set.",
            "Category is missing.",
        ),
        _warn(
            "item_specifics_empty",
            bool(draft.item_specifics),
            "Item specifics are present.",
            "Item specifics are empty.",
        ),
        _warn(
            "no_price_source",
            bool((draft.generated_meta or {}).get("price_source")),
            "Price source is recorded.",
            "No price source is recorded.",
        ),
        _warn(
            "price_below_min_acceptable",
            price is None or min_price is None or price >= min_price,
            "Price is not below the current minimum acceptable price.",
            "Price is below the current minimum acceptable price.",
        ),
        _warn(
            "price_below_true_cost",
            price is None or true_cost is None or true_cost <= 0 or price >= true_cost,
            "Price is not below true cost.",
            "Price is below true cost.",
        ),
        _warn(
            "no_boilerplate",
            draft.boilerplate_id is not None,
            "Boilerplate is selected.",
            "No boilerplate selected.",
        ),
        _warn(
            "phones_faults_absent",
            profile_key != "phones" or bool(str((item.attributes or {}).get("faults") or "").strip()),
            "Phone faults are recorded.",
            "Phone faults attribute is empty.",
        ),
        _warn(
            "missing_whats_included",
            "what's included" in description,
            "Description includes the What's included heading.",
            "Description lacks the What's included heading.",
        ),
    ]


def resolve_photo_ids(draft) -> dict:
    ids = [str(photo_id) for photo_id in (draft.photo_ids or []) if str(photo_id).strip()]
    if not ids:
        return {"photos": [], "missing": []}
    photos_by_id = {
        str(photo.id): photo
        for photo in PhotoAsset.objects.filter(item=draft.item, id__in=ids)
    }
    photos = []
    missing = []
    for photo_id in ids:
        photo = photos_by_id.get(photo_id)
        if photo is None or not photo.processed_path:
            missing.append(photo_id)
        else:
            photos.append(photo)
    return {"photos": photos, "missing": missing}


def _leak_checks(draft) -> list[Check]:
    checks = []
    haystack = " ".join(
        [
            str(draft.title or ""),
            str(draft.subtitle or ""),
            str(draft.description_html or ""),
        ]
    ).lower()
    for key, check_key, label in [
        ("imei", "leak_imei", "IMEI"),
        ("serial_no", "leak_serial", "serial number"),
    ]:
        value = _identifier_value(draft.item, key)
        if len(value) < 6:
            checks.append(Check(check_key, "pass", f"No {label} leak detected."))
            continue
        leaked = value.lower() in haystack
        checks.append(
            Check(
                check_key,
                "fail" if leaked else "pass",
                f"{label} appears in listing text."
                if leaked
                else f"No {label} leak detected.",
            )
        )
    return checks


def _identifier_value(item, key: str) -> str:
    attributes = item.attributes if isinstance(item.attributes, dict) else {}
    return str(attributes.get(key) or getattr(item, key, "") or "").strip()


def _check(key: str, passed: bool, pass_message: str, fail_message: str) -> Check:
    return Check(key, "pass" if passed else "fail", pass_message if passed else fail_message)


def _warn(key: str, passed: bool, pass_message: str, warn_message: str) -> Check:
    return Check(key, "pass" if passed else "warn", pass_message if passed else warn_message)


def _positive_decimal(value) -> bool:
    number = _decimal_or_none(value)
    return number is not None and number > 0


def _decimal_or_none(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _current_min_acceptable_price(item) -> Decimal | None:
    report = item.valuation_reports.filter(is_current=True).first()
    if report and report.min_acceptable_price is not None:
        return Decimal(report.min_acceptable_price)
    if item.min_price is not None:
        return Decimal(item.min_price)
    return None


def _true_cost_for_item(item) -> Decimal:
    return sum(
        (
            Decimal(str(value))
            for value in [
                item.acquisition_cost,
                item.refurb_cost,
                item.inbound_shipping_cost,
            ]
            if value is not None
        ),
        Decimal("0"),
    )
