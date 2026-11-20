from datetime import date
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.catalog.models import ProductCategory
from apps.inventory.models import InventoryItem
from apps.listing.models import ListingDraft
from apps.sales.models import SaleRecord


@pytest.mark.django_db
def test_zero_stock_draft_creation_refuses_new_ebay_draft(django_user_model):
    """Sprint 27 replaces the Sprint 26 audit's accepted-zero-stock contract."""
    category = ProductCategory.objects.create(name="Audit gold", slug="audit-gold", sku_prefix="AUD", profile_key="gold")
    item = InventoryItem.objects.create(title="Synthetic sold-out item", category=category, quantity_total=1, status="sold")
    SaleRecord.objects.create(item=item, sale_date=date(2026, 11, 19), quantity=1, sale_price="1.00")
    assert item.quantity_remaining == 0
    client = APIClient()
    client.force_authenticate(user=django_user_model.objects.create_user(username="zero-stock-audit"))
    with patch("apps.listing.views.refresh_editor_metadata") as live_metadata:
        response = client.post(f"/api/items/{item.pk}/listing-drafts/", {}, format="json")
    assert response.status_code == 409
    assert response.data == {"code": "sold_out", "detail": "Sold out \N{EM DASH} nothing to list."}
    assert not ListingDraft.objects.filter(item=item).exists()
    live_metadata.assert_not_called()
