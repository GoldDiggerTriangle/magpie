from io import BytesIO
import uuid

from django.core.exceptions import ValidationError
from django.db.models import Max
from PIL import Image, ImageOps, UnidentifiedImageError

from apps.photos.models import PhotoAsset
from integrations.storage import LocalFileStorageAdapter


class MediaService:
    def __init__(self, storage=None):
        self.storage = storage or LocalFileStorageAdapter()

    def process_upload(self, item, django_file, role=PhotoAsset.Role.OTHER) -> PhotoAsset:
        try:
            image = Image.open(django_file)
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise ValidationError("Uploaded file is not a valid image.") from exc

        image_id = uuid.uuid4().hex
        item_id = str(item.id)

        original_bytes = self.render_jpeg(image, quality=92)
        processed = self.copy_with_longest_side(image, 2000)
        processed_bytes = self.render_jpeg(processed, quality=85)
        thumb = self.copy_with_longest_side(image, 400)
        thumb_bytes = self.render_jpeg(thumb, quality=80)

        original_key = f"originals/{item_id}/{image_id}.jpg"
        processed_key = f"processed/{item_id}/{image_id}.jpg"
        thumb_key = f"thumbs/{item_id}/{image_id}.jpg"

        self.storage.save(original_key, original_bytes, content_type="image/jpeg")
        self.storage.save(processed_key, processed_bytes, content_type="image/jpeg")
        self.storage.save(thumb_key, thumb_bytes, content_type="image/jpeg")

        max_order = item.photos.aggregate(max_order=Max("order_index"))["max_order"]
        order_index = 0 if max_order is None else max_order + 1
        is_main = not item.photos.exists()

        return PhotoAsset.objects.create(
            item=item,
            role=role or PhotoAsset.Role.OTHER,
            is_main=is_main,
            order_index=order_index,
            original_path=original_key,
            processed_path=processed_key,
            thumb_path=thumb_key,
            width=image.width,
            height=image.height,
            bytes_original=len(original_bytes),
            exif_stripped=True,
        )

    def render_jpeg(self, image: Image.Image, quality: int) -> bytes:
        output = BytesIO()
        image.save(output, format="JPEG", quality=quality, optimize=True)
        return output.getvalue()

    def copy_with_longest_side(self, image: Image.Image, max_side: int) -> Image.Image:
        copy = image.copy()
        copy.thumbnail((max_side, max_side))
        return copy
