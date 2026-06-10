from __future__ import annotations

from dataclasses import asdict
from io import BytesIO, StringIO
import csv
import json
import zipfile

from django.core.serializers.json import DjangoJSONEncoder

from apps.listing.readiness import check_readiness, resolve_photo_ids
from integrations.storage import LocalFileStorageAdapter


def build_export_bundle(draft, *, storage=None) -> tuple[bytes, dict]:
    storage = storage or LocalFileStorageAdapter()
    photo_resolution = resolve_photo_ids(draft)
    skipped_photo_ids = list(photo_resolution["missing"])
    photo_manifest = []

    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("title.txt", draft.title or "")
        if draft.subtitle:
            archive.writestr("subtitle.txt", draft.subtitle)
        archive.writestr("description.html", draft.description_html or "")
        archive.writestr("specifics.csv", specifics_csv(draft.item_specifics or []))

        for index, photo in enumerate(photo_resolution["photos"], start=1):
            try:
                photo_bytes = storage.open(photo.processed_path)
            except FileNotFoundError:
                skipped_photo_ids.append(str(photo.id))
                continue
            name = f"photos/{index:02d}_{draft.item.sku}.jpg"
            archive.writestr(name, photo_bytes)
            photo_manifest.append(
                {
                    "id": str(photo.id),
                    "filename": name,
                    "processed_path": photo.processed_path,
                }
            )

        checks = [asdict(check) for check in check_readiness(draft)]
        readiness = {
            "checks": checks,
            "skipped_photo_ids": skipped_photo_ids,
        }
        archive.writestr("readiness.json", json_dump(readiness))
        archive.writestr(
            "listing-summary.json",
            json_dump(listing_summary(draft, photo_manifest, skipped_photo_ids)),
        )

    return output.getvalue(), {
        "skipped_photo_ids": skipped_photo_ids,
        "photo_manifest": photo_manifest,
    }


def specifics_csv(rows) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "value"])
    for row in rows:
        writer.writerow([row.get("name", ""), row.get("value", "")])
    return output.getvalue()


def listing_summary(draft, photo_manifest, skipped_photo_ids) -> dict:
    return {
        "id": str(draft.id),
        "item": str(draft.item_id),
        "item_sku": draft.item.sku,
        "status": draft.status,
        "channel": draft.channel,
        "channel_data": draft.channel_data,
        "title": draft.title,
        "subtitle": draft.subtitle,
        "description_html": draft.description_html,
        "listing_format": draft.listing_format,
        "price": str(draft.price) if draft.price is not None else None,
        "currency": draft.currency,
        "quantity": draft.quantity,
        "est_shipping_note": draft.est_shipping_note,
        "item_specifics": draft.item_specifics,
        "photo_ids": draft.photo_ids,
        "include_sku_footer": draft.include_sku_footer,
        "boilerplate": str(draft.boilerplate_id) if draft.boilerplate_id else None,
        "title_edited": draft.title_edited,
        "description_edited": draft.description_edited,
        "generated_meta": draft.generated_meta,
        "exported_at": draft.exported_at.isoformat() if draft.exported_at else None,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
        "photo_manifest": photo_manifest,
        "skipped_photo_ids": skipped_photo_ids,
    }


def json_dump(payload) -> str:
    return json.dumps(payload, cls=DjangoJSONEncoder, indent=2)
