from decimal import Decimal
from io import BytesIO
import csv

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.catalog.models import ProductCategory
from apps.core.backup_ops import DB_SNAPSHOT_NAME, MEDIA_DIR_NAME
from apps.core.models import SkuSequence
from apps.core.tests.backup_helpers import (
    load_backup_manifest,
    run_encrypted_backup,
    sqlite_count,
)
from apps.inventory.models import InventoryItem
from apps.locations.models import StorageLocation
from apps.photos.models import PhotoAsset


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="tester", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def category():
    return ProductCategory.objects.create(
        name="Stamps",
        slug="stamps-test",
        sku_prefix="STM",
    )


@pytest.fixture
def location():
    return StorageLocation.objects.create(label="Shelf 1", type=StorageLocation.LocationType.SHELF)


def image_upload(name="photo.jpg", size=(640, 480), color="red"):
    image = Image.new("RGB", size, color)
    output = BytesIO()
    image.save(output, format="JPEG")
    output.seek(0)
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, output.read(), content_type="image/jpeg")


@pytest.mark.django_db
def test_sku_format_uniqueness_and_sequence_increment(category):
    first = InventoryItem.objects.create(title="First", category=category)
    second = InventoryItem.objects.create(title="Second", category=category)

    assert first.sku == "STM-00001"
    assert second.sku == "STM-00002"
    assert first.sku != second.sku
    assert SkuSequence.objects.get(prefix="STM").last_value == 2


@pytest.mark.django_db
def test_photo_asset_one_main_constraint_rejects_second_main(category):
    item = InventoryItem.objects.create(title="With photos", category=category)
    PhotoAsset.objects.create(
        item=item,
        is_main=True,
        original_path="originals/one.jpg",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PhotoAsset.objects.create(
                item=item,
                is_main=True,
                original_path="originals/two.jpg",
            )


@pytest.mark.django_db
def test_attributes_accept_dict_and_reject_non_dict(category):
    item = InventoryItem(title="Attributes", category=category, attributes={"ok": True})
    item.full_clean()

    item.attributes = []
    with pytest.raises(ValidationError):
        item.full_clean()


@pytest.mark.django_db
def test_api_item_create_list_retrieve_patch_delete(api_client, category, location):
    create_response = api_client.post(
        "/api/items/",
        {
            "title": "API item",
            "category": str(category.id),
            "location": str(location.id),
            "status": InventoryItem.Status.CAPTURED,
            "condition": InventoryItem.Condition.UNGRADED,
            "estimated_value": "42.00",
            "attributes": {"api": True},
        },
        format="json",
    )
    assert create_response.status_code == 201, create_response.data
    item_id = create_response.data["id"]
    assert create_response.data["sku"].startswith("STM-")

    list_response = api_client.get("/api/items/")
    assert list_response.status_code == 200
    assert list_response.data["count"] == 1

    retrieve_response = api_client.get(f"/api/items/{item_id}/")
    assert retrieve_response.status_code == 200
    assert retrieve_response.data["photos"] == []

    patch_response = api_client.patch(
        f"/api/items/{item_id}/",
        {"status": InventoryItem.Status.NEEDS_RESEARCH, "notes": "patched"},
        format="json",
    )
    assert patch_response.status_code == 200
    assert patch_response.data["status"] == InventoryItem.Status.NEEDS_RESEARCH

    delete_response = api_client.delete(f"/api/items/{item_id}/")
    assert delete_response.status_code == 204
    assert InventoryItem.objects.count() == 0


@pytest.mark.django_db
def test_api_filters_and_search(api_client, category):
    other = ProductCategory.objects.create(name="Coins", slug="coins-test", sku_prefix="COIN")
    target = InventoryItem.objects.create(
        title="Searchable stamp",
        category=category,
        status=InventoryItem.Status.NEEDS_RESEARCH,
        condition=InventoryItem.Condition.GOOD,
        estimated_value=Decimal("100.00"),
        notes="blue perforation",
    )
    InventoryItem.objects.create(
        title="Other coin",
        category=other,
        status=InventoryItem.Status.CAPTURED,
        condition=InventoryItem.Condition.UNGRADED,
        estimated_value=Decimal("5.00"),
    )

    response = api_client.get(
        "/api/items/",
        {
            "status": InventoryItem.Status.NEEDS_RESEARCH,
            "category": str(category.id),
            "condition": InventoryItem.Condition.GOOD,
            "search": "perforation",
            "min_value": "50",
            "max_value": "150",
        },
    )
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == str(target.id)


@pytest.mark.django_db
def test_api_items_export_csv(api_client, category):
    item = InventoryItem.objects.create(title="CSV API", category=category)

    response = api_client.get("/api/items/export.csv")

    assert response.status_code == 200
    assert response["content-type"].startswith("text/csv")
    body = response.content.decode("utf-8")
    assert "sku,title" in body
    assert item.sku in body


@pytest.mark.django_db
def test_api_photo_upload_reorder_set_main_and_delete(api_client, category, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    item = InventoryItem.objects.create(title="Photo API", category=category)

    first = api_client.post(
        f"/api/items/{item.id}/photos/",
        {"image": image_upload("first.jpg"), "role": PhotoAsset.Role.FRONT},
        format="multipart",
    )
    assert first.status_code == 201, first.data
    assert first.data["is_main"] is True

    second = api_client.post(
        f"/api/items/{item.id}/photos/",
        {"image": image_upload("second.jpg"), "role": PhotoAsset.Role.BACK},
        format="multipart",
    )
    assert second.status_code == 201, second.data
    assert second.data["is_main"] is False

    reorder = api_client.post(
        f"/api/items/{item.id}/photos/reorder/",
        {"order": [second.data["id"], first.data["id"]]},
        format="json",
    )
    assert reorder.status_code == 200
    assert [photo["id"] for photo in reorder.data] == [second.data["id"], first.data["id"]]

    set_main = api_client.patch(
        f"/api/photos/{second.data['id']}/",
        {"is_main": True},
        format="json",
    )
    assert set_main.status_code == 200
    assert PhotoAsset.objects.get(pk=second.data["id"]).is_main is True
    assert PhotoAsset.objects.get(pk=first.data["id"]).is_main is False

    second_photo = PhotoAsset.objects.get(pk=second.data["id"])
    paths = [tmp_path / second_photo.original_path, tmp_path / second_photo.processed_path, tmp_path / second_photo.thumb_path]
    assert all(path.exists() for path in paths)

    delete = api_client.delete(f"/api/photos/{second.data['id']}/")
    assert delete.status_code == 204
    assert all(not path.exists() for path in paths)


@pytest.mark.django_db
def test_api_photo_upload_rejects_non_image(api_client, category):
    from django.core.files.uploadedfile import SimpleUploadedFile

    item = InventoryItem.objects.create(title="Bad upload", category=category)
    response = api_client.post(
        f"/api/items/{item.id}/photos/",
        {"image": SimpleUploadedFile("bad.txt", b"not an image", content_type="text/plain")},
        format="multipart",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_dashboard_totals(api_client, category):
    InventoryItem.objects.create(
        title="Cheap",
        category=category,
        status=InventoryItem.Status.CAPTURED,
        estimated_value=Decimal("25.00"),
    )
    high = InventoryItem.objects.create(
        title="High",
        category=category,
        status=InventoryItem.Status.READY_TO_LIST,
        estimated_value=Decimal("150.00"),
    )
    PhotoAsset.objects.create(
        item=high,
        is_main=True,
        original_path="originals/high.jpg",
    )

    response = api_client.get("/api/dashboard/summary/")
    assert response.status_code == 200
    assert response.data["total_items"] == 2
    assert Decimal(response.data["total_estimated_value"]) == Decimal("175.00")
    assert response.data["by_status"][InventoryItem.Status.CAPTURED] == 1
    assert response.data["missing_photos"] == 1
    assert response.data["high_value_unlisted"] == 1


@pytest.mark.django_db
def test_unauthenticated_api_rejected(category):
    client = APIClient()
    response = client.get("/api/items/")
    assert response.status_code in {401, 403}


@pytest.mark.django_db(transaction=True)
def test_backup_and_export_commands_work(tmp_path, monkeypatch, category):
    InventoryItem.objects.create(title="Exported", category=category)

    export_path = tmp_path / "items.csv"
    call_command("export_items", csv=str(export_path))
    with export_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert rows[0]["sku"].startswith("STM-")

    _, extract_dir = run_encrypted_backup(tmp_path, monkeypatch)
    manifest = load_backup_manifest(extract_dir)
    assert "inventory.inventoryitem" in manifest["row_counts"]
    assert (extract_dir / MEDIA_DIR_NAME).is_dir()
    assert sqlite_count(extract_dir / DB_SNAPSHOT_NAME, "inventory_inventoryitem") == 1
