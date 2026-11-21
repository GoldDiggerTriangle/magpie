from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.inventory.models import InventoryItem
from apps.listing.channel_listings import take_down_items_queryset
from apps.listing.models import ChannelListing
from apps.sales.models import SaleRecord


pytestmark = pytest.mark.django_db


@pytest.fixture
def api(django_user_model):
    client = APIClient()
    client.force_authenticate(django_user_model.objects.create_user(username="listing-presence"))
    return client


@pytest.mark.parametrize("quantity_total", [1, 3], ids=["sold-out", "partial-stock"])
@pytest.mark.parametrize(
    "active_count,ended_count",
    [(0, 0), (0, 2), (1, 0), (2, 2)],
    ids=["never-listed", "ended-only", "active", "mixed-multiple"],
)
def test_home_and_board_require_an_existing_unended_listing(api, quantity_total, active_count, ended_count):
    stock = InventoryItem.objects.create(
        title="Listing presence regression", quantity_total=quantity_total, acquisition_cost=Decimal("3.00")
    )
    SaleRecord.objects.create(
        item=stock, sale_date=timezone.localdate(), quantity=1, sale_price=Decimal("5.00")
    )
    for index in range(active_count + ended_count):
        ChannelListing.objects.create(
            item=stock,
            channel=ChannelListing.Channel.FACEBOOK_MARKETPLACE,
            ended_at=timezone.now() - timedelta(days=1) if index >= active_count else None,
        )

    expected_ids = [str(stock.pk)] if active_count else []
    assert [str(row.pk) for row in take_down_items_queryset()] == expected_ids

    response = api.get("/api/channel-listings/board/")
    assert response.status_code == 200
    board = response.data
    expected_take_down = expected_ids if quantity_total == 1 else []
    expected_partial = expected_ids if quantity_total > 1 else []
    assert [row["item"] for row in board["take_down_checklist"]] == expected_take_down
    assert [row["item"] for row in board["partial_quantity"]] == expected_partial
    assert sum(group["count"] for group in board["groups"]) == active_count
    for row in board["take_down_checklist"] + board["partial_quantity"]:
        assert len(row["active_listings"]) == active_count

    response = api.get("/api/analytics/summary/", {"range": "this_month"})
    assert response.status_code == 200
    summary = response.data
    expected_count = len(expected_take_down)
    assert summary["action_counts"]["take_down_checklists"] == expected_count
    assert [row for row in summary["alerts"] if row["id"] == "take-down"] == (
        [{"id": "take-down", "count": 1, "label": "Sold-out listings to take down", "href": "/listings"}]
        if expected_count else []
    )
