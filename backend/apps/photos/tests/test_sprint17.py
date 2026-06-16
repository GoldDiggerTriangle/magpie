from io import BytesIO
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from PIL import Image, ImageDraw

from apps.catalog.models import ProductCategory
from django.db import connection

from apps.core.backup_ops import DB_SNAPSHOT_NAME, MEDIA_DIR_NAME
from apps.core.tests.backup_helpers import (
    load_backup_manifest,
    run_encrypted_backup,
    sqlite_count,
)
from apps.inventory.models import InventoryItem
from apps.photos.fixup import (
    PHOTO_FIXUP_OPERATIONS,
    PROHIBITED_PHOTO_FIXUP_STEPS,
    PhotoFixupService,
)
from apps.photos.models import PhotoAsset, PhotoDerivative
from apps.photos.services import MediaService
from integrations.storage import LocalFileStorageAdapter


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="regan", password="test")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def category(db):
    return ProductCategory.objects.create(name="Photos", slug="photos", sku_prefix="PHO")


def own_photo_upload(name="own-photo.jpg") -> SimpleUploadedFile:
    image = Image.new("RGB", (360, 280), "#ece7dc")
    draw = ImageDraw.Draw(image)
    draw.rectangle((88, 54, 278, 224), fill="#f8fafc", outline="#0f172a", width=5)
    draw.line((110, 96, 250, 182), fill="#8b5cf6", width=8)
    draw.ellipse((150, 100, 214, 164), outline="#b91c1c", width=5)
    output = BytesIO()
    image.save(output, format="JPEG", quality=92)
    output.seek(0)
    return SimpleUploadedFile(name, output.read(), content_type="image/jpeg")


def create_photo(settings, tmp_path: Path, category, title="Photo item") -> PhotoAsset:
    settings.MEDIA_ROOT = tmp_path
    item = InventoryItem.objects.create(title=title, category=category)
    return MediaService().process_upload(item, own_photo_upload(), PhotoAsset.Role.FRONT)


@pytest.mark.django_db
def test_local_fixup_stages_own_photo_without_applying_or_network(settings, tmp_path, category, monkeypatch):
    photo = create_photo(settings, tmp_path, category)
    original_processed = photo.processed_path

    def blocked_network(*args, **kwargs):
        raise AssertionError("Sprint 17 photo fix-up must not use network calls")

    monkeypatch.setattr("socket.create_connection", blocked_network)
    monkeypatch.setattr("urllib.request.urlopen", blocked_network)

    derivative = PhotoFixupService().generate(photo)
    photo.refresh_from_db()

    assert photo.processed_path == original_processed
    assert photo.fixup_status == PhotoAsset.FixupStatus.PENDING_REVIEW
    assert derivative.status == PhotoDerivative.Status.PENDING_REVIEW
    assert derivative.source_path == photo.original_path
    assert not derivative.source_path.startswith(("http://", "https://"))
    assert derivative.background_mode == "local_threshold_fallback"
    assert Path(settings.MEDIA_ROOT, derivative.fixed_path).exists()
    assert Path(settings.MEDIA_ROOT, derivative.thumb_path).exists()
    assert Path(settings.MEDIA_ROOT, photo.original_path).exists()

    operation_names = {entry["name"] for entry in derivative.operations}
    assert operation_names == set(PHOTO_FIXUP_OPERATIONS)
    assert operation_names.isdisjoint(PROHIBITED_PHOTO_FIXUP_STEPS)
    assert "condition-altering" in derivative.condition_note


@pytest.mark.django_db
def test_approve_reject_and_revert_keep_original_non_destructive(settings, tmp_path, category):
    photo = create_photo(settings, tmp_path, category)
    original_path = photo.original_path
    original_processed = photo.processed_path
    original_thumb = photo.thumb_path
    service = PhotoFixupService()

    rejected = service.generate(photo)
    service.reject(rejected)
    photo.refresh_from_db()
    rejected.refresh_from_db()
    assert rejected.status == PhotoDerivative.Status.REJECTED
    assert photo.processed_path == original_processed
    assert photo.thumb_path == original_thumb
    assert photo.original_path == original_path

    approved = service.generate(photo)
    service.approve(approved)
    photo.refresh_from_db()
    approved.refresh_from_db()
    assert approved.status == PhotoDerivative.Status.APPROVED
    assert photo.active_derivative_id == approved.id
    assert photo.processed_path == approved.fixed_path
    assert photo.thumb_path == approved.thumb_path
    assert Path(settings.MEDIA_ROOT, original_path).exists()

    service.revert(photo)
    photo.refresh_from_db()
    approved.refresh_from_db()
    assert approved.status == PhotoDerivative.Status.REJECTED
    assert photo.active_derivative_id is None
    assert photo.fixup_status == PhotoAsset.FixupStatus.NONE
    assert photo.processed_path == original_processed
    assert photo.thumb_path == original_thumb
    assert Path(settings.MEDIA_ROOT, original_path).exists()


@pytest.mark.django_db
def test_batch_review_tweak_and_approve_api_paths(api_client, settings, tmp_path, category):
    settings.MEDIA_ROOT = tmp_path
    item = InventoryItem.objects.create(title="Batch photo item", category=category)
    first = MediaService().process_upload(item, own_photo_upload("first.jpg"), PhotoAsset.Role.FRONT)
    second = MediaService().process_upload(item, own_photo_upload("second.jpg"), PhotoAsset.Role.BACK)

    batch = api_client.post(f"/api/items/{item.id}/photos/fixup/", {}, format="json")
    assert batch.status_code == 201
    assert PhotoDerivative.objects.filter(photo__item=item, status=PhotoDerivative.Status.PENDING_REVIEW).count() == 2
    assert {entry["fixup_status"] for entry in batch.data} == {"pending_review"}

    tweak = api_client.post(
        f"/api/photos/{first.id}/fixup/tweak/",
        {"parameters": {"rotate_degrees": "2", "exposure_delta": "0.05"}},
        format="json",
    )
    assert tweak.status_code == 201
    pending = PhotoDerivative.objects.filter(photo=first, status=PhotoDerivative.Status.PENDING_REVIEW).latest("created_at")
    assert pending.source == PhotoDerivative.Source.LOCAL_TWEAK
    assert pending.parameters["rotate_degrees"] == 2.0

    approve = api_client.post(f"/api/photos/{first.id}/fixup/approve/", {}, format="json")
    assert approve.status_code == 200
    first.refresh_from_db()
    assert first.active_derivative_id == pending.id
    assert approve.data["fixup_status"] == "approved"

    reject = api_client.post(f"/api/photos/{second.id}/fixup/reject/", {}, format="json")
    assert reject.status_code == 200
    second.refresh_from_db()
    assert second.active_derivative_id is None
    assert second.fixup_status == PhotoAsset.FixupStatus.REJECTED


@pytest.mark.django_db(transaction=True)
def test_backup_restore_includes_photo_derivatives_and_fixed_media(settings, tmp_path, monkeypatch, category):
    if connection.vendor != "sqlite":
        pytest.skip("Sprint 8 backup command is SQLite-only.")

    photo = create_photo(settings, tmp_path, category)
    derivative = PhotoFixupService().generate(photo)
    PhotoFixupService().approve(derivative)

    _, extract_dir = run_encrypted_backup(tmp_path / "backups", monkeypatch)
    manifest = load_backup_manifest(extract_dir)
    restored_db = extract_dir / DB_SNAPSHOT_NAME

    assert manifest["row_counts"]["photos.photoderivative"] == 1
    assert sqlite_count(restored_db, "photos_photoderivative") == 1
    assert (extract_dir / MEDIA_DIR_NAME / derivative.fixed_path).exists()
    assert (extract_dir / MEDIA_DIR_NAME / derivative.thumb_path).exists()
    assert (extract_dir / MEDIA_DIR_NAME / photo.original_path).exists()
