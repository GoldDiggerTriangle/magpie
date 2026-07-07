from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings

from apps.research.models import Comparable


class ComparableCaptureOcrUnavailable(Exception):
    pass


@dataclass(frozen=True)
class ComparableCaptureResult:
    draft: dict
    detail: str
    parsed_from: list[str]
    warnings: list[str]
    ocr_available: bool

    @property
    def available(self) -> bool:
        return bool(
            self.draft.get("url")
            or self.draft.get("title")
            or self.draft.get("price")
            or self.draft.get("shipping")
            or self.draft.get("observed_on")
        )


MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def blank_comparable_draft() -> dict:
    return {
        "title": "",
        "price": "",
        "price_basis": Comparable.PriceBasis.UNKNOWN,
        "shipping": "",
        "source": "",
        "source_tag": "manual",
        "url": "",
        "observed_on": "",
        "condition": "",
        "grade": "",
        "sale_format": Comparable.SaleFormat.UNKNOWN,
        "match_scope": Comparable.MatchScope.EXACT,
        "match_reason": "",
    }


def ocr_uploaded_screenshot(uploaded, *, binary: str | None = None) -> str:
    tesseract = binary or shutil.which("tesseract")
    if not tesseract:
        raise ComparableCaptureOcrUnavailable(
            "Screenshot OCR is unavailable on this machine. Install local Tesseract, or type the sold result into the capture form."
        )
    suffix = Path(uploaded.name or "screenshot.png").suffix or ".png"
    with tempfile.NamedTemporaryFile(
        dir=settings.BASE_DIR,
        suffix=suffix,
        delete=False,
    ) as handle:
        for chunk in uploaded.chunks():
            handle.write(chunk)
        image_path = Path(handle.name)

    try:
        result = subprocess.run(
            [tesseract, str(image_path), "stdout", "--psm", "6"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    finally:
        image_path.unlink(missing_ok=True)

    if result.returncode != 0:
        raise ComparableCaptureOcrUnavailable("Local OCR could not read this screenshot.")
    return result.stdout.strip()


def comparable_capture_draft(*, url: str = "", ocr_text: str = "", ocr_available: bool = True) -> ComparableCaptureResult:
    draft = blank_comparable_draft()
    warnings: list[str] = []
    parsed_from: list[str] = []
    url = (url or "").strip()
    text = normalise_text(ocr_text)

    if url:
        parsed_from.append("link")
        draft["url"] = url
        source, tag = source_from_url(url)
        draft["source"] = source
        draft["source_tag"] = tag
        draft["match_reason"] = "user-selected marketplace evidence; review exactness"

    if text:
        parsed_from.append("screenshot")
        apply_ocr_text_to_draft(draft, text)
        if not draft["source"]:
            draft["source"] = "Screenshot capture"
        if draft["source_tag"] == "manual" and looks_like_ebay(text):
            draft["source_tag"] = "ebay_sold"
            draft["source"] = "eBay sold"

    if not ocr_available:
        warnings.append("Screenshot OCR was unavailable; link values were not fetched or inferred.")

    if url and not text and not draft["price"]:
        detail = "Link recorded. Magpie did not fetch the marketplace page; add a screenshot or type the sold price before saving evidence."
    elif draft["price"]:
        detail = "Capture form filled from your screenshot. Review it, then press Add to grid to save evidence."
    elif text:
        detail = "Screenshot read, but no sold price was found. Review the capture form and type the missing values."
    else:
        detail = "Add an evidence link or screenshot to fill the capture form."

    return ComparableCaptureResult(
        draft=draft,
        detail=detail,
        parsed_from=parsed_from,
        warnings=warnings,
        ocr_available=ocr_available,
    )


def apply_ocr_text_to_draft(draft: dict, text: str) -> None:
    sold_match = re.search(r"\bSOLD\s+(\d{1,2})\s+([A-Z]{3})\s+(\d{4})\b", text, flags=re.IGNORECASE)
    search_start = 0
    if sold_match:
        observed = parse_sold_date(sold_match)
        if observed:
            draft["observed_on"] = observed.isoformat()
        search_start = sold_match.end()

    price_match = first_buyer_visible_price(text[search_start:])
    if price_match:
        draft["price"] = money_string(price_match.group(1))
        draft["price_basis"] = Comparable.PriceBasis.BUYER_VISIBLE
        title = text[search_start : search_start + price_match.start()]
        title = clean_title(title)
        if title:
            draft["title"] = title[:300]

    shipping = first_shipping(text)
    if shipping:
        draft["shipping"] = money_string(shipping)

    lowered = text.lower()
    if "best offer" in lowered or "buy it now" in lowered:
        draft["sale_format"] = Comparable.SaleFormat.FIXED_PRICE
    elif "auction" in lowered:
        draft["sale_format"] = Comparable.SaleFormat.AUCTION

    if draft["source_tag"] == "manual" and looks_like_ebay(text):
        draft["source"] = "eBay sold"
        draft["source_tag"] = "ebay_sold"
    if not draft["match_reason"]:
        draft["match_reason"] = "user-selected sold-result screenshot; review exactness"


def source_from_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "ebay." in host or host == "ebay.io":
        return "eBay sold", "ebay_sold"
    if "facebook." in host:
        return "Facebook Marketplace", "facebook_marketplace"
    if "worthpoint." in host:
        return "WorthPoint", "price_guide"
    return "User evidence link", "manual"


def normalise_text(value: str) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def looks_like_ebay(text: str) -> bool:
    lowered = text.lower()
    return "sold" in lowered and ("au $" in lowered or "ebay" in lowered or "sell one like this" in lowered)


def parse_sold_date(match: re.Match[str]) -> date | None:
    day = int(match.group(1))
    month = MONTHS.get(match.group(2).upper())
    year = int(match.group(3))
    if not month:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def first_buyer_visible_price(text: str) -> re.Match[str] | None:
    return re.search(
        r"(?<!\+)\bAU\s*\$?\s*([0-9][0-9,]*(?:\.\d{2})?)",
        text,
        flags=re.IGNORECASE,
    )


def first_shipping(text: str) -> str:
    match = re.search(
        r"\+\s*AU\s*\$?\s*([0-9][0-9,]*(?:\.\d{2})?)\s+(?:delivery|postage|shipping)",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else ""


def money_string(value: str) -> str:
    try:
        amount = Decimal(value.replace(",", ""))
    except (InvalidOperation, AttributeError):
        return ""
    return f"{amount:.2f}"


def clean_title(value: str) -> str:
    value = re.sub(r"\bor Best Offer\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\bSell one like this\b", "", value, flags=re.IGNORECASE)
    return normalise_text(value).strip(" -:|")
