from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps

from apps.intelligence.models import FieldSuggestion, ImageFingerprint
from apps.photos.models import PhotoAsset
from integrations.storage import LocalFileStorageAdapter


NEAR_DUPLICATE_THRESHOLD = 6


def average_hash(image: Image.Image, size: int = 8) -> str:
    prepared = ImageOps.exif_transpose(image).convert("L").resize((size, size))
    if hasattr(prepared, "get_flattened_data"):
        pixels = list(prepared.get_flattened_data())
    else:
        pixels = list(prepared.getdata())
    mean = sum(pixels) / len(pixels)
    bits = "".join("1" if pixel >= mean else "0" for pixel in pixels)
    return f"{int(bits, 2):0{size * size // 4}x}"


def hamming_distance(left: str, right: str) -> int:
    return bin(int(left, 16) ^ int(right, 16)).count("1")


def fingerprint_and_flag(photo: PhotoAsset, *, image: Image.Image | None = None, storage=None) -> ImageFingerprint:
    storage = storage or LocalFileStorageAdapter()
    if image is None:
        key = photo.processed_path or photo.original_path
        image = Image.open(BytesIO(storage.open(key)))
    perceptual_hash = average_hash(image)

    existing = list(
        ImageFingerprint.objects.select_related("photo", "item")
        .exclude(photo=photo)
        .all()
    )
    fingerprint, _ = ImageFingerprint.objects.update_or_create(
        photo=photo,
        defaults={
            "item": photo.item,
            "perceptual_hash": perceptual_hash,
        },
    )
    for candidate in existing:
        distance = hamming_distance(perceptual_hash, candidate.perceptual_hash)
        if distance <= NEAR_DUPLICATE_THRESHOLD:
            stage_duplicate_candidate(photo, candidate, distance)
    return fingerprint


def scan_item_photos(item, *, storage=None) -> list[FieldSuggestion]:
    before = set(FieldSuggestion.objects.filter(item=item).values_list("id", flat=True))
    for photo in item.photos.order_by("created_at"):
        fingerprint_and_flag(photo, storage=storage)
    return list(FieldSuggestion.objects.filter(item=item).exclude(id__in=before))


def stage_duplicate_candidate(
    photo: PhotoAsset,
    matched: ImageFingerprint,
    distance: int,
) -> FieldSuggestion:
    evidence = (
        f"Near-duplicate image candidate: this photo is visually close to "
        f"{matched.item.sku} ({matched.item.title or 'Untitled item'}); hash distance {distance}."
    )
    existing = FieldSuggestion.objects.filter(
        item=photo.item,
        photo=photo,
        source=FieldSuggestion.Source.DUPLICATE,
        field="duplicate_candidate",
        status=FieldSuggestion.Status.PENDING,
        evidence=evidence,
    ).first()
    if existing:
        return existing
    return FieldSuggestion.objects.create(
        item=photo.item,
        photo=photo,
        field="duplicate_candidate",
        proposed_value={
            "matched_item": str(matched.item_id),
            "matched_photo": str(matched.photo_id),
            "matched_sku": matched.item.sku,
            "distance": distance,
        },
        source=FieldSuggestion.Source.DUPLICATE,
        confidence_band=FieldSuggestion.ConfidenceBand.CANDIDATE,
        evidence=evidence,
    )
