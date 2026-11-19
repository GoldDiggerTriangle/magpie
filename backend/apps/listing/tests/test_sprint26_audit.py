from datetime import date
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.catalog.models import ProductCategory
from apps.inventory.models import InventoryItem
from apps.listing.models import ListingDraft
from apps.sales.models import SaleRecord


@pytest.mark.django_db
def test_zero_stock_draft_creation_current_backend_contract(django_user_model):
    """Audit only: Sprint 26 changes the entry, not this existing backend behaviour."""
    category = ProductCategory.objects.create(name="Audit gold", slug="audit-gold", sku_prefix="AUD", profile_key="gold")
    item = InventoryItem.objects.create(title="Synthetic sold-out item", category=category, quantity_total=1, status="sold")
    SaleRecord.objects.create(item=item, sale_date=date(2026, 11, 19), quantity=1, sale_price="1.00")
    assert item.quantity_remaining == 0
    client = APIClient()
    client.force_authenticate(user=django_user_model.objects.create_user(username="zero-stock-audit"))
    with patch("apps.listing.views.refresh_editor_metadata") as live_metadata:
        response = client.post(f"/api/items/{item.pk}/listing-drafts/", {}, format="json")
    assert response.status_code == 201
    draft = ListingDraft.objects.get(pk=response.data["id"])
    assert draft.quantity == 0
    assert draft.status == "draft"
    assert not draft.channel_data.get("offer_id")
    assert not draft.channel_data.get("listing_id")
    live_metadata.assert_not_called()
