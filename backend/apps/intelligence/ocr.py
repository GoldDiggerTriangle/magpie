from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from django.conf import settings

from apps.intelligence.models import FieldSuggestion
from apps.inventory.models import InventoryItem
from apps.photos.models import PhotoAsset
from integrations.storage import LocalFileStorageAdapter


class OcrUnavailable(Exception):
    pass


@dataclass(frozen=True)
class OcrResult:
    text: str
    evidence: str = ""


class OcrAdapter(Protocol):
    def recognize(self, photo: PhotoAsset) -> OcrResult: ...


class LocalTesseractOcrAdapter:
    def __init__(self, binary: str | None = None, storage=None):
        self.binary = binary or shutil.which("tesseract")
        self.storage = storage or LocalFileStorageAdapter()

    @property
    def available(self) -> bool:
        return bool(self.binary)

    def recognize(self, photo: PhotoAsset) -> OcrResult:
        if not self.binary:
            raise OcrUnavailable("Local Tesseract is not installed or not on PATH.")
        key = photo.processed_path or photo.original_path
        if not key:
            return OcrResult(text="", evidence="No image path available.")
        image_bytes = self.storage.open(key)
        with tempfile.NamedTemporaryFile(
            dir=settings.BASE_DIR,
            suffix=".jpg",
            delete=False,
        ) as handle:
            handle.write(image_bytes)
            image_path = Path(handle.name)
        try:
            result = subprocess.run(
                [self.binary, str(image_path), "stdout", "--psm", "6"],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
        finally:
            image_path.unlink(missing_ok=True)
        if result.returncode != 0:
            raise OcrUnavailable("Local Tesseract could not read this image.")
        return OcrResult(text=result.stdout.strip(), evidence="Local Tesseract OCR")


class FakeOcrAdapter:
    def __init__(self, text: str):
        self.text = text

    @property
    def available(self) -> bool:
        return True

    def recognize(self, photo: PhotoAsset) -> OcrResult:
        return OcrResult(text=self.text, evidence=f"Fake OCR fixture for {photo.id}")


def run_ocr_for_item(
    item: InventoryItem,
    *,
    adapter: OcrAdapter | None = None,
) -> dict:
    adapter = adapter or LocalTesseractOcrAdapter()
    available = getattr(adapter, "available", True)
    if not available:
        return {
            "available": False,
            "detail": "OCR unavailable. Install local Tesseract to use OCR on this machine.",
            "suggestions": [],
        }

    suggestions = []
    for photo in item.photos.order_by("order_index", "created_at"):
        try:
            result = adapter.recognize(photo)
        except OcrUnavailable as exc:
            return {"available": False, "detail": str(exc), "suggestions": []}
        suggestions.extend(stage_ocr_suggestions(item, photo, result.text, result.evidence))

    return {
        "available": True,
        "detail": "OCR completed." if item.photos.exists() else "No photos available for OCR.",
        "suggestions": suggestions,
    }


def stage_ocr_suggestions(
    item: InventoryItem,
    photo: PhotoAsset | None,
    text: str,
    evidence_prefix: str = "OCR text",
) -> list[FieldSuggestion]:
    text = " ".join((text or "").split())
    if not text:
        return []
    suggestions = []
    for field, value, band, evidence in map_text_to_suggestions(item, text):
        suggestion = FieldSuggestion.objects.create(
            item=item,
            photo=photo,
            field=field,
            proposed_value=value,
            source=FieldSuggestion.Source.OCR,
            confidence_band=band,
            evidence=f"{evidence_prefix}: {evidence}",
        )
        suggestions.append(suggestion)
    return suggestions


def map_text_to_suggestions(item: InventoryItem, text: str) -> list[tuple[str, str, str, str]]:
    profile = item.category.profile_key if item.category_id and item.category else ""
    suggestions: list[tuple[str, str, str, str]] = []

    if profile in {"stamps", "coins"}:
        year = first_year(text)
        if year:
            suggestions.append(
                ("attributes.year", year, FieldSuggestion.ConfidenceBand.MEDIUM, f"Recognised year {year}")
            )
        denomination = first_denomination(text)
        if denomination:
            suggestions.append(
                (
                    "attributes.denomination",
                    denomination,
                    FieldSuggestion.ConfidenceBand.MEDIUM,
                    f"Recognised denomination {denomination}",
                )
            )

    if profile == "phones":
        brand = first_phone_brand(text)
        if brand:
            suggestions.append(
                ("attributes.brand", brand, FieldSuggestion.ConfidenceBand.MEDIUM, f"Recognised brand {brand}")
            )
        model = labelled_value(text, "model")
        if model:
            suggestions.append(
                ("attributes.model", model, FieldSuggestion.ConfidenceBand.MEDIUM, f"Recognised model {model}")
            )
        serial = labelled_value(text, "serial")
        if serial:
            suggestions.append(
                ("attributes.serial_no", serial, FieldSuggestion.ConfidenceBand.HIGH, f"Recognised serial {serial}")
            )

    if profile == "gold":
        metal = first_metal(text)
        if metal:
            suggestions.append(
                ("attributes.metal", metal, FieldSuggestion.ConfidenceBand.MEDIUM, f"Recognised metal {metal}")
            )
        karat = first_karat(text)
        if karat:
            suggestions.append(
                ("attributes.karat", karat, FieldSuggestion.ConfidenceBand.MEDIUM, f"Recognised karat {karat}")
            )

    if not suggestions:
        suggestions.append(
            (
                "notes",
                text[:240],
                FieldSuggestion.ConfidenceBand.LOW,
                "Recognised text retained as a lead",
            )
        )
    return suggestions


def first_year(text: str) -> str:
    for match in re.finditer(r"\b(1[89]\d{2}|20\d{2})\b", text):
        year = int(match.group(1))
        if 1840 <= year <= 2100:
            return str(year)
    return ""


def first_denomination(text: str) -> str:
    match = re.search(
        r"\b(\d+(?:\.\d+)?\s?(?:d|c|p|¢|cent|cents|pence|shilling|shillings|dollar|dollars))\b",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


def labelled_value(text: str, label: str) -> str:
    match = re.search(rf"\b{label}\s*(?:no\.?|number|#|:)?\s*([A-Z0-9][A-Z0-9\-_/]{{2,}})", text, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def first_phone_brand(text: str) -> str:
    brands = ["Apple", "Samsung", "Google", "Nokia", "Motorola", "Sony", "Huawei", "Oppo"]
    for brand in brands:
        if re.search(rf"\b{re.escape(brand)}\b", text, flags=re.IGNORECASE):
            return brand
    return ""


def first_metal(text: str) -> str:
    for metal in ["gold", "silver", "platinum", "palladium"]:
        if re.search(rf"\b{metal}\b", text, flags=re.IGNORECASE):
            return metal
    return ""


def first_karat(text: str) -> str:
    match = re.search(r"\b(9|10|14|18|22|24)\s?(?:k|kt|ct|karat)\b", text, flags=re.IGNORECASE)
    return match.group(1) if match else ""
