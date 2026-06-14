from io import BytesIO
from urllib.parse import parse_qs, urlparse

import pytest
from PIL import Image, ImageDraw
from rest_framework.test import APIClient

from apps.catalog.models import ProductCategory
from apps.intelligence.images import hamming_distance
from apps.intelligence.models import FieldSuggestion, ImageFingerprint
from apps.intelligence.ocr import FakeOcrAdapter, run_ocr_for_item
from apps.intelligence.sold_search import build_sold_search_links
from apps.inventory.models import InventoryItem
from apps.photos.models import PhotoAsset
from apps.photos.services import MediaService
from apps.valuation.models import ValuationReport


class RecordingStorage:
    def __init__(self):
        self.files = {}

    def save(self, key: str, data: bytes, content_type: str = "image/jpeg") -> str:
        self.files[key] = data
        return key

    def open(self, key: str) -> bytes:
        return self.files[key]

    def delete(self, key: str) -> None:
        self.files.pop(key, None)

    def url(self, key: str) -> str:
        return f"/media/{key}"


class UnavailableOcr:
    available = False

    def recognize(self, photo):
        raise AssertionError("recognize should not be called when unavailable")


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="sprint13", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def stamp_category():
    return ProductCategory.objects.create(
        name="Stamps",
        slug="sprint13-stamps",
        sku_prefix="STM",
        profile_key="stamps",
    )


@pytest.fixture
def phone_category():
    return ProductCategory.objects.create(
        name="Phones",
        slug="sprint13-phones",
        sku_prefix="PHO",
        profile_key="phones",
    )


def upload_image(name="item.jpg", *, variant="bridge") -> BytesIO:
    image = Image.new("RGB", (240, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 220, 160), outline="black", width=4)
    draw.line((30, 120, 210, 40), fill="navy", width=6)
    draw.text((40, 70), variant, fill="black")
    output = BytesIO()
    image.save(output, format="JPEG")
    output.seek(0)
    output.name = name
    return output


@pytest.mark.django_db
def test_sold_search_urls_are_local_builds_with_ebay_sold_filters(stamp_category):
    item = InventoryItem.objects.create(
        title="Australia 1932 Harbour Bridge 2d",
        category=stamp_category,
        attributes={"country": "Australia", "year": 1932, "denomination": "2d"},
        estimated_value="25.00",
    )
    ValuationReport.objects.create(item=item, is_current=True, suggested_price="30.00")

    links = build_sold_search_links(item)
    by_id = {link.id: link for link in links}

    assert {"broad", "exact", "auction", "fixed_price", "price_bounded", "category"} <= set(by_id)
    auction_params = parse_qs(urlparse(by_id["auction"].url).query)
    assert by_id["auction"].url.startswith("https://www.ebay.com.au/sch/i.html?")
    assert auction_params["_nkw"] == ["Australia 1932 2d"]
    assert auction_params["LH_Sold"] == ["1"]
    assert auction_params["LH_Complete"] == ["1"]
    assert auction_params["LH_Auction"] == ["1"]

    fixed_params = parse_qs(urlparse(by_id["fixed_price"].url).query)
    assert fixed_params["LH_BIN"] == ["1"]

    price_params = parse_qs(urlparse(by_id["price_bounded"].url).query)
    assert price_params["_udlo"] == ["21.00"]
    assert price_params["_udhi"] == ["39.00"]

    import apps.intelligence.sold_search as sold_search

    source = sold_search.__loader__.get_source(sold_search.__name__)
    assert "requests" not in source
    assert "httpx" not in source
    assert "urlopen" not in source


@pytest.mark.django_db
def test_ocr_stages_suggestions_and_never_persists_without_review(stamp_category):
    item = InventoryItem.objects.create(title="OCR target", category=stamp_category)
    photo = PhotoAsset.objects.create(item=item, original_path="originals/ocr.jpg")

    result = run_ocr_for_item(
        item,
        adapter=FakeOcrAdapter("Australia 1932 2d Harbour Bridge"),
    )

    item.refresh_from_db()
    assert result["available"] is True
    assert FieldSuggestion.objects.filter(item=item, source=FieldSuggestion.Source.OCR).count() == 2
    assert item.attributes == {}
    assert all(suggestion.photo_id == photo.id for suggestion in result["suggestions"])


@pytest.mark.django_db
def test_ocr_unavailable_is_graceful(stamp_category):
    item = InventoryItem.objects.create(title="OCR target", category=stamp_category)
    PhotoAsset.objects.create(item=item, original_path="originals/ocr.jpg")

    result = run_ocr_for_item(item, adapter=UnavailableOcr())

    assert result["available"] is False
    assert "OCR unavailable" in result["detail"]
    assert result["suggestions"] == []


@pytest.mark.django_db
def test_approve_edit_reject_are_the_only_item_write_paths(api_client, stamp_category):
    item = InventoryItem.objects.create(title="Review target", category=stamp_category)
    approve = FieldSuggestion.objects.create(
        item=item,
        field="attributes.year",
        proposed_value="1932",
        source=FieldSuggestion.Source.OCR,
        confidence_band=FieldSuggestion.ConfidenceBand.MEDIUM,
        evidence="OCR text: 1932",
    )
    edit = FieldSuggestion.objects.create(
        item=item,
        field="attributes.denomination",
        proposed_value="1d",
        source=FieldSuggestion.Source.OCR,
        confidence_band=FieldSuggestion.ConfidenceBand.MEDIUM,
        evidence="OCR text: 1d",
    )
    reject = FieldSuggestion.objects.create(
        item=item,
        field="attributes.country",
        proposed_value="Australia",
        source=FieldSuggestion.Source.OCR,
        confidence_band=FieldSuggestion.ConfidenceBand.LOW,
        evidence="OCR text: Australia",
    )

    item.refresh_from_db()
    assert item.attributes == {}

    approve_response = api_client.post(f"/api/field-suggestions/{approve.id}/approve/")
    assert approve_response.status_code == 200, approve_response.data
    item.refresh_from_db()
    assert item.attributes["year"] == 1932

    edit_response = api_client.post(
        f"/api/field-suggestions/{edit.id}/edit/",
        {"value": "2d"},
        format="json",
    )
    assert edit_response.status_code == 200, edit_response.data
    item.refresh_from_db()
    assert item.attributes["denomination"] == "2d"

    before_reject = dict(item.attributes)
    reject_response = api_client.post(f"/api/field-suggestions/{reject.id}/reject/")
    assert reject_response.status_code == 200, reject_response.data
    item.refresh_from_db()
    assert item.attributes == before_reject


@pytest.mark.django_db
def test_duplicate_image_detection_flags_review_candidates_without_auto_merge(stamp_category):
    storage = RecordingStorage()
    first = InventoryItem.objects.create(title="Known item", category=stamp_category)
    second = InventoryItem.objects.create(title="Possible duplicate", category=stamp_category)

    first_photo = MediaService(storage=storage).process_upload(
        first,
        upload_image("first.jpg", variant="bridge"),
        PhotoAsset.Role.FRONT,
    )
    second_photo = MediaService(storage=storage).process_upload(
        second,
        upload_image("second.jpg", variant="bridge"),
        PhotoAsset.Role.FRONT,
    )

    assert ImageFingerprint.objects.count() == 2
    hashes = list(ImageFingerprint.objects.order_by("created_at").values_list("perceptual_hash", flat=True))
    assert hamming_distance(hashes[0], hashes[1]) == 0

    candidate = FieldSuggestion.objects.get(
        item=second,
        photo=second_photo,
        source=FieldSuggestion.Source.DUPLICATE,
        field="duplicate_candidate",
    )
    assert candidate.confidence_band == FieldSuggestion.ConfidenceBand.CANDIDATE
    assert candidate.status == FieldSuggestion.Status.PENDING
    assert candidate.proposed_value["matched_item"] == str(first.id)

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.id != second.id
    assert first.title == "Known item"
    assert second.title == "Possible duplicate"
    assert first_photo.item_id == first.id
    assert second_photo.item_id == second.id
