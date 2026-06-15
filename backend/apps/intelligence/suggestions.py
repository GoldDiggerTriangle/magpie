from __future__ import annotations

from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.intelligence.models import FieldSuggestion


WRITABLE_ITEM_FIELDS = {
    "title",
    "condition",
    "notes",
    "estimated_value",
    "acquisition_cost",
    "refurb_cost",
    "inbound_shipping_cost",
    "est_outbound_shipping",
    "est_packaging_cost",
}
AI_BLOCKED_FIELD_FRAGMENTS = {
    "price",
    "value",
    "valuation",
    "acquisition",
    "cost",
    "profit",
    "catalogue_id",
    "catalogue_number",
    "catalog_id",
    "grade",
}


class SuggestionError(ValueError):
    pass


@transaction.atomic
def resolve_suggestion(
    suggestion: FieldSuggestion,
    *,
    action: str,
    value=None,
) -> FieldSuggestion:
    locked = FieldSuggestion.objects.select_for_update().select_related("item").get(
        pk=suggestion.pk
    )
    if locked.status != FieldSuggestion.Status.PENDING:
        raise SuggestionError("This suggestion has already been resolved.")
    if action == "reject":
        locked.status = FieldSuggestion.Status.REJECTED
        locked.resolved_value = None
        locked.resolved_at = timezone.now()
        locked.save(update_fields=["status", "resolved_value", "resolved_at", "updated_at"])
        return locked
    if action not in {"approve", "edit"}:
        raise SuggestionError("Unsupported suggestion resolution action.")

    resolved_value = locked.proposed_value if action == "approve" else value
    if resolved_value is None or resolved_value == "":
        raise SuggestionError("A value is required to resolve this suggestion.")
    item_changed = apply_value_to_item(locked, resolved_value)
    locked.status = (
        FieldSuggestion.Status.APPROVED
        if action == "approve"
        else FieldSuggestion.Status.EDITED
    )
    locked.resolved_value = resolved_value
    locked.resolved_at = timezone.now()
    locked.save(update_fields=["status", "resolved_value", "resolved_at", "updated_at"])
    if item_changed:
        locked.item.save()
    return locked


def apply_value_to_item(suggestion: FieldSuggestion, value) -> bool:
    field = suggestion.field
    item = suggestion.item
    if field == "duplicate_candidate":
        return False
    if field.startswith("ai_candidate."):
        return False
    if suggestion.source == FieldSuggestion.Source.AI and any(
        fragment in field.lower() for fragment in AI_BLOCKED_FIELD_FRAGMENTS
    ):
        raise SuggestionError("AI suggestions cannot write price, value, cost, profit, grade, or catalogue fields.")
    if field.startswith("attributes."):
        attribute_name = field.split(".", 1)[1]
        attributes = deepcopy(item.attributes or {})
        attributes[attribute_name] = value
        item.attributes = attributes
    elif field in WRITABLE_ITEM_FIELDS:
        setattr(item, field, value)
    else:
        raise SuggestionError(f"Suggestion field is not writable: {field}")

    try:
        item.full_clean()
    except ValidationError as exc:
        raise SuggestionError(str(exc)) from exc
    return True
