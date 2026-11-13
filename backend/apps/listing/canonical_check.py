from django.db.models import Count


CONSTRAINT_NAME = "listing_one_active_draft"


def active_draft_violations(draft_model, *, condition, using):
    # Accept the historical model and frozen predicate when called by Migration B.
    rows = (
        draft_model.objects.using(using).filter(condition)
        .values("item_id", "item__sku", "channel")
        .annotate(active_count=Count("pk")).filter(active_count__gt=1)
        .order_by("item__sku", "channel", "item_id")
    )
    return [
        {
            "item_id": str(row["item_id"]), "sku": row["item__sku"],
            "channel": row["channel"], "active_count": row["active_count"],
        }
        for row in rows
    ]


def violation_message(rows):
    return "Migration B blocked by duplicate active drafts: " + "; ".join(
        f"{row['sku']} ({row['item_id']}), {row['channel']}: {row['active_count']} active drafts"
        for row in rows
    )
