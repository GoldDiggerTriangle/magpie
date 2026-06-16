from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import importlib.util
import math
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from PIL import Image, ImageEnhance, ImageOps, ImageStat, UnidentifiedImageError

from apps.photos.models import PhotoAsset, PhotoDerivative
from apps.photos.services import MediaService
from integrations.storage import LocalFileStorageAdapter


PHOTO_FIXUP_OPERATIONS = [
    "exif_orientation",
    "conservative_autocrop",
    "straighten_rotate",
    "gray_world_white_balance",
    "gentle_auto_levels",
    "local_background_cleanup",
]
PROHIBITED_PHOTO_FIXUP_STEPS = [
    "generative_fill",
    "retouch",
    "beautify",
    "scratch_removal",
    "wear_removal",
    "condition_smoothing",
    "shine_boost",
    "gloss_boost",
]


@dataclass(frozen=True)
class PipelineResult:
    image: Image.Image
    operations: list[dict]
    background_mode: str


class LocalPhotoFixupPipeline:
    """Conservative local-only photo cleanup for user-owned images."""

    pipeline_version = "sprint17-local-v1"

    def run(self, image: Image.Image, parameters: dict | None = None) -> PipelineResult:
        parameters = self._normalise_parameters(parameters or {})
        operations: list[dict] = []

        current = ImageOps.exif_transpose(image).convert("RGB")
        operations.append({"name": "exif_orientation", "mode": "local"})

        current = self._rotate(current, parameters["rotate_degrees"])
        operations.append(
            {
                "name": "straighten_rotate",
                "degrees": parameters["rotate_degrees"],
                "mode": "manual" if parameters["rotate_degrees"] else "conservative_noop",
            }
        )

        before_size = current.size
        current, crop_box = self._autocrop(current)
        operations.append(
            {
                "name": "conservative_autocrop",
                "before_size": before_size,
                "after_size": current.size,
                "crop_box": crop_box,
            }
        )

        current = self._copy_with_longest_side(current, 2000)
        current, white_balance = self._white_balance(current)
        operations.append({"name": "gray_world_white_balance", **white_balance})

        current = self._gentle_levels(
            current,
            exposure_delta=parameters["exposure_delta"],
            contrast_delta=parameters["contrast_delta"],
        )
        operations.append(
            {
                "name": "gentle_auto_levels",
                "exposure_delta": parameters["exposure_delta"],
                "contrast_delta": parameters["contrast_delta"],
            }
        )

        current, background_mode = self._background_cleanup(current)
        operations.append({"name": "local_background_cleanup", "mode": background_mode})

        return PipelineResult(
            image=current,
            operations=operations,
            background_mode=background_mode,
        )

    def _normalise_parameters(self, parameters: dict) -> dict:
        return {
            "rotate_degrees": self._clamp_float(parameters.get("rotate_degrees", 0), -12, 12),
            "exposure_delta": self._clamp_float(parameters.get("exposure_delta", 0), -0.25, 0.25),
            "contrast_delta": self._clamp_float(parameters.get("contrast_delta", 0), -0.2, 0.2),
        }

    def _clamp_float(self, value, low: float, high: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = 0.0
        if not math.isfinite(numeric):
            numeric = 0.0
        return max(low, min(high, numeric))

    def _rotate(self, image: Image.Image, degrees: float) -> Image.Image:
        if abs(degrees) < 0.05:
            return image
        return image.rotate(degrees, resample=Image.Resampling.BICUBIC, expand=True, fillcolor="white")

    def _autocrop(self, image: Image.Image) -> tuple[Image.Image, tuple[int, int, int, int] | None]:
        bbox = self._foreground_bbox(image)
        if bbox is None:
            return image, None
        left, top, right, bottom = bbox
        width, height = image.size
        if left <= 1 and top <= 1 and right >= width - 1 and bottom >= height - 1:
            return image, None
        cropped = image.crop((left, top, right, bottom))
        if cropped.width < width * 0.35 or cropped.height < height * 0.35:
            return image, None
        return cropped, (left, top, right, bottom)

    def _foreground_bbox(self, image: Image.Image) -> tuple[int, int, int, int] | None:
        sample = image.copy()
        sample.thumbnail((500, 500))
        scale_x = image.width / sample.width
        scale_y = image.height / sample.height
        bg = self._corner_average(sample)
        mask = bytearray()
        for red, green, blue in sample.getdata():
            distance = abs(red - bg[0]) + abs(green - bg[1]) + abs(blue - bg[2])
            mask.append(255 if distance > 42 else 0)
        bbox = Image.frombytes("L", sample.size, bytes(mask)).getbbox()
        if bbox is None:
            return None
        margin_x = max(8, int(image.width * 0.04))
        margin_y = max(8, int(image.height * 0.04))
        left = max(0, int(bbox[0] * scale_x) - margin_x)
        top = max(0, int(bbox[1] * scale_y) - margin_y)
        right = min(image.width, int(math.ceil(bbox[2] * scale_x)) + margin_x)
        bottom = min(image.height, int(math.ceil(bbox[3] * scale_y)) + margin_y)
        return left, top, right, bottom

    def _corner_average(self, image: Image.Image) -> tuple[int, int, int]:
        width, height = image.size
        size = max(4, min(width, height, 32))
        boxes = [
            (0, 0, size, size),
            (width - size, 0, width, size),
            (0, height - size, size, height),
            (width - size, height - size, width, height),
        ]
        totals = [0.0, 0.0, 0.0]
        count = 0
        for box in boxes:
            stat = ImageStat.Stat(image.crop(box))
            for index, mean in enumerate(stat.mean[:3]):
                totals[index] += mean
            count += 1
        return tuple(int(round(total / count)) for total in totals)

    def _copy_with_longest_side(self, image: Image.Image, max_side: int) -> Image.Image:
        copy = image.copy()
        copy.thumbnail((max_side, max_side))
        return copy

    def _white_balance(self, image: Image.Image) -> tuple[Image.Image, dict]:
        stat = ImageStat.Stat(image)
        means = stat.mean[:3]
        gray = sum(means) / 3
        scales = [max(0.92, min(1.08, gray / mean)) if mean else 1.0 for mean in means]
        channels = []
        for channel, scale in zip(image.split(), scales, strict=True):
            channels.append(channel.point(lambda value, s=scale: max(0, min(255, int(value * s)))))
        return Image.merge("RGB", channels), {
            "scales": [round(scale, 4) for scale in scales],
        }

    def _gentle_levels(
        self,
        image: Image.Image,
        *,
        exposure_delta: float,
        contrast_delta: float,
    ) -> Image.Image:
        current = ImageOps.autocontrast(image, cutoff=0.5)
        current = ImageEnhance.Brightness(current).enhance(1.0 + exposure_delta)
        current = ImageEnhance.Contrast(current).enhance(1.04 + contrast_delta)
        return current

    def _background_cleanup(self, image: Image.Image) -> tuple[Image.Image, str]:
        probe = LocalBackgroundModelProbe()
        if probe.available():
            return image, "offline_model_available_not_configured"
        bg = self._corner_average(image)
        cleaned = image.copy()
        pixels = []
        for red, green, blue in cleaned.getdata():
            distance = abs(red - bg[0]) + abs(green - bg[1]) + abs(blue - bg[2])
            bright = (red + green + blue) / 3
            if distance < 58 and bright > 150:
                pixels.append((255, 255, 255))
            else:
                pixels.append((red, green, blue))
        cleaned.putdata(pixels)
        return cleaned, "local_threshold_fallback"


class LocalBackgroundModelProbe:
    def available(self) -> bool:
        model_path = getattr(settings, "PHOTO_FIXUP_BACKGROUND_MODEL_PATH", "")
        return bool(
            model_path
            and importlib.util.find_spec("onnxruntime")
            and importlib.util.find_spec("rembg")
        )


class PhotoFixupService:
    condition_note = (
        "Local geometry, lighting, and background cleanup only. Original retained; "
        "no condition-altering operation is part of the pipeline."
    )

    def __init__(self, storage=None, pipeline: LocalPhotoFixupPipeline | None = None):
        self.storage = storage or LocalFileStorageAdapter()
        self.pipeline = pipeline or LocalPhotoFixupPipeline()
        self.media = MediaService(storage=self.storage)

    def generate(self, photo: PhotoAsset, parameters: dict | None = None, *, source=None) -> PhotoDerivative:
        try:
            image = Image.open(BytesIO(self.storage.open(photo.original_path)))
        except (FileNotFoundError, UnidentifiedImageError, OSError) as exc:
            raise ValidationError("Original photo is not available for local fix-up.") from exc

        result = self.pipeline.run(image, parameters or {})
        derivative_id = uuid.uuid4()
        item_id = str(photo.item_id)
        fixed_key = f"fixups/{item_id}/{derivative_id}.jpg"
        thumb_key = f"fixup-thumbs/{item_id}/{derivative_id}.jpg"
        fixed_bytes = self.media.render_jpeg(result.image, quality=88)
        thumb = self.media.copy_with_longest_side(result.image, 400)
        thumb_bytes = self.media.render_jpeg(thumb, quality=82)

        self.storage.save(fixed_key, fixed_bytes, content_type="image/jpeg")
        self.storage.save(thumb_key, thumb_bytes, content_type="image/jpeg")

        base_processed, base_thumb = self._base_display_paths(photo)
        with transaction.atomic():
            PhotoDerivative.objects.filter(
                photo=photo,
                status=PhotoDerivative.Status.PENDING_REVIEW,
            ).update(status=PhotoDerivative.Status.REJECTED)
            derivative = PhotoDerivative.objects.create(
                id=derivative_id,
                photo=photo,
                status=PhotoDerivative.Status.PENDING_REVIEW,
                source=source or PhotoDerivative.Source.LOCAL_FIXUP,
                fixed_path=fixed_key,
                thumb_path=thumb_key,
                source_path=photo.original_path,
                original_processed_path=base_processed,
                original_thumb_path=base_thumb,
                width=result.image.width,
                height=result.image.height,
                bytes_fixed=len(fixed_bytes),
                pipeline_version=self.pipeline.pipeline_version,
                operations=result.operations,
                parameters=self.pipeline._normalise_parameters(parameters or {}),
                background_mode=result.background_mode,
                condition_note=self.condition_note,
            )
            PhotoAsset.objects.filter(pk=photo.pk).update(
                fixup_status=PhotoAsset.FixupStatus.PENDING_REVIEW
            )
            photo.fixup_status = PhotoAsset.FixupStatus.PENDING_REVIEW
        return derivative

    def generate_for_item(self, item) -> list[PhotoDerivative]:
        return [self.generate(photo) for photo in item.photos.order_by("order_index", "created_at")]

    def tweak(self, derivative: PhotoDerivative, parameters: dict) -> PhotoDerivative:
        return self.generate(
            derivative.photo,
            parameters,
            source=PhotoDerivative.Source.LOCAL_TWEAK,
        )

    def approve(self, derivative: PhotoDerivative) -> PhotoAsset:
        with transaction.atomic():
            photo = PhotoAsset.objects.select_for_update().get(pk=derivative.photo_id)
            PhotoDerivative.objects.filter(
                photo=photo,
                status=PhotoDerivative.Status.APPROVED,
            ).exclude(pk=derivative.pk).update(status=PhotoDerivative.Status.REJECTED)
            derivative.status = PhotoDerivative.Status.APPROVED
            derivative.save(update_fields=["status", "updated_at"])
            photo.processed_path = derivative.fixed_path
            photo.thumb_path = derivative.thumb_path
            photo.active_derivative = derivative
            photo.fixup_status = PhotoAsset.FixupStatus.APPROVED
            photo.width = derivative.width
            photo.height = derivative.height
            photo.save(
                update_fields=[
                    "processed_path",
                    "thumb_path",
                    "active_derivative",
                    "fixup_status",
                    "width",
                    "height",
                    "updated_at",
                ]
            )
            return photo

    def reject(self, derivative: PhotoDerivative) -> PhotoAsset:
        with transaction.atomic():
            photo = PhotoAsset.objects.select_for_update().get(pk=derivative.photo_id)
            derivative.status = PhotoDerivative.Status.REJECTED
            derivative.save(update_fields=["status", "updated_at"])
            if photo.active_derivative_id:
                photo.fixup_status = PhotoAsset.FixupStatus.APPROVED
            else:
                photo.fixup_status = PhotoAsset.FixupStatus.REJECTED
            photo.save(update_fields=["fixup_status", "updated_at"])
            return photo

    def revert(self, photo: PhotoAsset) -> PhotoAsset:
        with transaction.atomic():
            locked = PhotoAsset.objects.select_for_update().get(pk=photo.pk)
            derivative = locked.active_derivative
            if derivative is None:
                locked.fixup_status = PhotoAsset.FixupStatus.NONE
                locked.save(update_fields=["fixup_status", "updated_at"])
                return locked
            locked.processed_path = derivative.original_processed_path or locked.original_path
            locked.thumb_path = derivative.original_thumb_path or derivative.original_processed_path or locked.original_path
            locked.active_derivative = None
            locked.fixup_status = PhotoAsset.FixupStatus.NONE
            locked.save(
                update_fields=[
                    "processed_path",
                    "thumb_path",
                    "active_derivative",
                    "fixup_status",
                    "updated_at",
                ]
            )
            derivative.status = PhotoDerivative.Status.REJECTED
            derivative.save(update_fields=["status", "updated_at"])
            return locked

    def _base_display_paths(self, photo: PhotoAsset) -> tuple[str, str]:
        active = photo.active_derivative
        if active:
            return (
                active.original_processed_path or photo.original_path,
                active.original_thumb_path or active.original_processed_path or photo.original_path,
            )
        return photo.processed_path or photo.original_path, photo.thumb_path or photo.processed_path or photo.original_path
