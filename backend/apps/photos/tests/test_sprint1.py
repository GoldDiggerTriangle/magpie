from io import BytesIO

import pytest
from PIL import Image

from apps.catalog.models import ProductCategory
from apps.intelligence.ai_research import strip_exif_for_ai
from apps.inventory.models import InventoryItem
from apps.photos.models import PhotoAsset
from apps.photos.services import MediaService


class RecordingStorage:
    def __init__(self):
        self.files = {}
        self.saved = []

    def save(self, key: str, data: bytes, content_type: str = "image/jpeg") -> str:
        self.saved.append((key, data, content_type))
        self.files[key] = data
        return key

    def open(self, key: str) -> bytes:
        return self.files[key]

    def delete(self, key: str) -> None:
        self.files.pop(key, None)

    def url(self, key: str) -> str:
        return f"/media/{key}"


def oriented_jpeg_with_exif() -> BytesIO:
    image = Image.new("RGB", (120, 60), "blue")
    exif = Image.Exif()
    exif[274] = 6
    exif[34853] = {1: "S", 2: (33, 0, 0), 3: "E", 4: (151, 0, 0)}
    output = BytesIO()
    image.save(output, format="JPEG", exif=exif.tobytes())
    output.seek(0)
    output.name = "oriented.jpg"
    return output


def gps_tagged_library_jpeg() -> BytesIO:
    image = Image.new("RGB", (160, 120), "green")
    exif = Image.Exif()
    exif[34853] = {1: "S", 2: (33, 51, 0), 3: "E", 4: (151, 12, 0)}
    output = BytesIO()
    image.save(output, format="JPEG", exif=exif.tobytes())
    output.seek(0)
    output.name = "library-gps.jpg"
    return output


@pytest.mark.django_db
def test_image_pipeline_strips_exif_resizes_records_metadata_and_applies_orientation():
    category = ProductCategory.objects.create(name="Photos", slug="photos", sku_prefix="PHO")
    item = InventoryItem.objects.create(title="Pipeline", category=category)
    storage = RecordingStorage()

    photo = MediaService(storage=storage).process_upload(
        item,
        oriented_jpeg_with_exif(),
        PhotoAsset.Role.FRONT,
    )

    assert photo.is_main is True
    assert photo.order_index == 0
    assert photo.exif_stripped is True
    assert photo.width == 60
    assert photo.height == 120
    assert photo.bytes_original == len(storage.files[photo.original_path])
    assert len(storage.saved) == 3
    assert {key.split("/", 1)[0] for key, _, _ in storage.saved} == {
        "originals",
        "processed",
        "thumbs",
    }

    original = Image.open(BytesIO(storage.files[photo.original_path]))
    processed = Image.open(BytesIO(storage.files[photo.processed_path]))
    thumb = Image.open(BytesIO(storage.files[photo.thumb_path]))

    assert original.size == (60, 120)
    assert original.getexif().get(274) is None
    assert original.getexif().get(34853) is None
    assert max(processed.size) <= 2000
    assert max(thumb.size) <= 400


@pytest.mark.django_db
def test_library_gps_exif_is_stripped_before_storage_and_ai_send_path():
    category = ProductCategory.objects.create(name="Library", slug="library", sku_prefix="LIB")
    item = InventoryItem.objects.create(title="GPS library image", category=category)
    storage = RecordingStorage()
    upload = gps_tagged_library_jpeg()
    assert Image.open(BytesIO(upload.getvalue())).getexif().get(34853) is not None

    photo = MediaService(storage=storage).process_upload(
        item,
        upload,
        PhotoAsset.Role.FRONT,
    )

    for key in [photo.original_path, photo.processed_path, photo.thumb_path]:
        stored = Image.open(BytesIO(storage.files[key]))
        assert stored.getexif().get(34853) is None

    prepared_from_raw = strip_exif_for_ai(
        gps_tagged_library_jpeg().getvalue(),
        photo_id="raw-library",
    )
    prepared_from_storage = strip_exif_for_ai(
        storage.open(photo.original_path),
        photo_id=str(photo.id),
    )
    for prepared in [prepared_from_raw, prepared_from_storage]:
        prepared_image = Image.open(BytesIO(prepared.data))
        assert prepared.exif_stripped is True
        assert prepared_image.getexif().get(34853) is None


@pytest.mark.django_db
def test_first_photo_only_becomes_main():
    category = ProductCategory.objects.create(name="Main", slug="main", sku_prefix="M")
    item = InventoryItem.objects.create(title="Main order", category=category)
    storage = RecordingStorage()
    service = MediaService(storage=storage)

    first = service.process_upload(item, oriented_jpeg_with_exif(), PhotoAsset.Role.FRONT)
    second = service.process_upload(item, oriented_jpeg_with_exif(), PhotoAsset.Role.BACK)

    assert first.is_main is True
    assert second.is_main is False
    assert second.order_index == 1
