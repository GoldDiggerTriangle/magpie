from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date
from io import StringIO
from threading import Event, current_thread
from unittest.mock import patch

import pytest
from django.core.management import call_command, CommandError
from django.db import connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.query import QuerySet
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.catalog.models import ProductCategory
from apps.inventory.models import InventoryItem
from apps.listing.creation_stock import DraftStockError, SoldOut
from apps.listing.models import ListingDraft, ListingBoilerplate
from apps.sales.models import SaleRecord
from apps.sales.services import create_sale_record


@pytest.fixture
def owned(db):
    category = ProductCategory.objects.create(name="Stock guard", slug="stock-guard", sku_prefix="SG")
    return InventoryItem.objects.create(title="Own stock", category=category, quantity_total=1)


@pytest.fixture
def api(django_user_model):
    client = APIClient()
    client.force_authenticate(django_user_model.objects.create_user(username="draft-guard"))
    return client


def sell(item, quantity=1, **kwargs):
    return SaleRecord.objects.using(item._state.db).create(item=item, quantity=quantity, sale_price="1.00", sale_date=date(2026, 11, 20), **kwargs)


def open_draft(api, item):
    return api.post(f"/api/items/{item.pk}/listing-drafts/", {}, format="json")


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["draft", "ready", "exported", "staged", "publish_failed", "future_status"])
def test_zero_stock_reuses_eligible_active_unchanged(api, owned, status):
    draft = ListingDraft.objects.create(item=owned, status=status, title="Retained human title")
    sell(owned)
    before = ListingDraft.objects.values().get(pk=draft.pk)
    revision = InventoryItem.objects.get(pk=owned.pk).stock_revision
    response = open_draft(api, owned)
    assert response.status_code == 200 and response.data["id"] == str(draft.pk)
    assert ListingDraft.objects.values().get(pk=draft.pk) == before
    assert InventoryItem.objects.get(pk=owned.pk).stock_revision == revision


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["publishing", "publish_unknown"])
def test_unresolved_outcome_precedes_zero_stock(api, owned, status):
    draft = ListingDraft.objects.create(item=owned, status=status)
    sell(owned)
    response = open_draft(api, owned)
    assert response.status_code == 400
    assert "publish outcome" in str(response.data)
    assert "sold_out" not in str(response.data)
    assert ListingDraft.objects.get(pk=draft.pk).status == status


@pytest.mark.django_db
def test_zero_stock_blocks_relist_without_touching_history_or_audit(api, owned):
    draft = ListingDraft.objects.create(item=owned, status="published", channel_data={"listing_id": "historic"})
    sell(owned)
    before = list(ListingDraft.objects.values()); audits = AuditLog.objects.count()
    response = open_draft(api, owned)
    assert response.status_code == 409 and response.data["code"] == "sold_out"
    assert list(ListingDraft.objects.values()) == before
    assert AuditLog.objects.count() == audits
    assert ListingDraft.objects.get(pk=draft.pk).channel_data["listing_id"] == "historic"


@pytest.mark.django_db
def test_partial_stock_and_restock_use_counts_not_sold_status(api, owned):
    sell(owned)
    assert open_draft(api, owned).status_code == 409
    owned.quantity_total = 3; owned.status = "sold"; owned.save()
    response = open_draft(api, owned)
    assert response.status_code == 201 and response.data["quantity"] == 2


@pytest.mark.django_db
def test_creation_fence_preserves_inventory_values(api, owned):
    before = InventoryItem.objects.values().get(pk=owned.pk)
    assert open_draft(api, owned).status_code == 201
    assert InventoryItem.objects.values().get(pk=owned.pk) == before


@pytest.mark.django_db
def test_superseded_sale_is_excluded(api, owned):
    owned.quantity_total = 2; owned.save()
    original = sell(owned, 2)
    sell(owned, 1, corrected_from=original)
    response = open_draft(api, owned)
    assert response.status_code == 201 and response.data["quantity"] == 1


@pytest.mark.django_db
def test_zero_stock_edits_and_archive_remain_available(api, owned):
    draft = ListingDraft.objects.create(item=owned)
    sell(owned)
    response = api.patch(f"/api/listing-drafts/{draft.pk}/", {"title": "Still editable locally"}, format="json")
    assert response.status_code == 200
    response = api.post(f"/api/listing-drafts/{draft.pk}/archive/", {}, format="json")
    assert response.status_code == 200
    assert ListingDraft.objects.get(pk=draft.pk).status == "archived"


@pytest.mark.django_db
def test_channel_into_ebay_counts_as_new_creation(api, owned):
    draft = ListingDraft.objects.create(item=owned, channel="generic")
    sell(owned)
    before = ListingDraft.objects.values().get(pk=draft.pk)
    response = api.patch(f"/api/listing-drafts/{draft.pk}/", {"channel": "ebay_au"}, format="json")
    assert response.status_code == 409 and response.data["code"] == "sold_out"
    assert ListingDraft.objects.values().get(pk=draft.pk) == before
    assert api.patch(f"/api/listing-drafts/{draft.pk}/", {"title": "Other channel edit"}, format="json").status_code == 200


@pytest.mark.django_db
def test_direct_and_bulk_paths_cannot_bypass(owned):
    draft = ListingDraft.objects.create(item=owned, channel="generic")
    sell(owned)
    for action in [lambda: ListingDraft.objects.create(item=owned),
                   lambda: ListingDraft.objects.bulk_create([ListingDraft(item=owned)]),
                   lambda: ListingDraft.objects.filter(pk=draft.pk).update(channel="ebay_au")]:
        with pytest.raises(SoldOut):
            action()
    draft.channel = "ebay_au"
    with pytest.raises(SoldOut):
        ListingDraft.objects.bulk_update([draft], ["channel"])
    assert ListingDraft.objects.filter(item=owned).count() == 1


@pytest.mark.django_db
def test_admin_add_reports_sold_out_in_form(client, django_user_model, owned):
    client.force_login(django_user_model.objects.create_superuser(username="guard-admin", password="test-only"))
    sell(owned)
    response = client.post(reverse("admin:listing_listingdraft_add"), {
        "item": str(owned.pk), "channel": "ebay_au", "status": "draft", "quantity": "1",
        "listing_format": "fixed", "currency": "AUD", "channel_data": "{}", "item_specifics": "[]", "photo_ids": "[]", "publish_error": "{}", "_save": "Save",
    })
    assert response.status_code == 200
    assert "Sold out" in str(response.context["adminform"].form.errors)
    assert not ListingDraft.objects.filter(item=owned).exists()


@pytest.mark.django_db
def test_seed_command_refuses_and_rolls_back(owned):
    sell(owned)
    from apps.core.management.commands.seed import Command
    with patch.object(Command, "seed_categories", return_value={}), patch.object(Command, "seed_locations", return_value={}), patch.object(Command, "seed_items", return_value=({"Seed/example phone - Samsung Galaxy S21": owned}, 0)), patch.object(Command, "seed_fee_schedule"), patch.object(Command, "seed_research_and_valuations"):
        with pytest.raises(CommandError, match="Sold out"):
            call_command("seed", stdout=StringIO())
    assert not ListingDraft.objects.filter(item=owned).exists()
    assert not ListingBoilerplate.objects.exists()


@pytest.fixture
def stock_database(tmp_path, django_db_blocker):
    alias = "default"
    if connections[alias].vendor == "sqlite":
        alias = "draft_stock_file"
        config = deepcopy(connections["default"].settings_dict)
        config.update(NAME=str(tmp_path / "draft-stock.sqlite3"), OPTIONS={"timeout": 10})
        connections.databases[alias] = config
        with django_db_blocker.unblock():
            executor = MigrationExecutor(connections[alias]); executor.migrate(executor.loader.graph.leaf_nodes())
            with connections[alias].cursor() as cursor:
                cursor.execute("PRAGMA journal_mode=WAL")
    try:
        with django_db_blocker.unblock():
            category = ProductCategory.objects.using(alias).create(name="Race stock", slug="race-stock", sku_prefix="RS")
            item = InventoryItem.objects.using(alias).create(title="Own race stock", category=category, sku="RS-00001")
            yield alias, item
    finally:
        if alias != "default":
            connections[alias].close(); del connections[alias]; del connections.databases[alias]


@pytest.mark.django_db(transaction=True)
def test_sale_wins_after_creation_read_no_stale_draft(stock_database, monkeypatch):
    alias, item = stock_database
    read = Event(); sold = Event(); update = QuerySet.update
    def intercepted(query, **kwargs):
        if query.model is InventoryItem and current_thread().name.startswith("creator") and "stock_revision" in kwargs:
            read.set(); assert sold.wait(10)
        return update(query, **kwargs)
    monkeypatch.setattr(QuerySet, "update", intercepted)
    def create():
        try:
            with pytest.raises(DraftStockError):
                ListingDraft.objects.using(alias).create(item=item)
        finally:
            connections[alias].close()
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="creator") as pool:
        future = pool.submit(create); assert read.wait(10)
        create_sale_record(data={"item": item, "quantity": 1, "sale_price": "1.00", "sale_date": date(2026, 11, 20)})
        sold.set(); future.result(timeout=15)
    assert InventoryItem.objects.using(alias).get(pk=item.pk).quantity_remaining == 0
    assert not ListingDraft.objects.using(alias).filter(item=item).exists()
    assert SaleRecord.objects.using(alias).filter(item=item).count() == 1


@pytest.mark.django_db(transaction=True)
def test_creation_wins_fence_then_sale_serializes(stock_database, monkeypatch):
    alias, item = stock_database
    fenced = Event(); sale_started = Event()
    from apps.listing import creation_stock
    check = creation_stock.require_remaining_stock
    def checked(fresh):
        check(fresh)
        fenced.set(); assert sale_started.wait(10)
    monkeypatch.setattr(creation_stock, "require_remaining_stock", checked)
    def create():
        try:
            return ListingDraft.objects.using(alias).create(item=item).pk
        finally:
            connections[alias].close()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(create); assert fenced.wait(10)
        sale_started.set()
        sale = create_sale_record(data={"item": item, "quantity": 1, "sale_price": "1.00", "sale_date": date(2026, 11, 20)})
        draft_id = future.result(timeout=15)
    draft = ListingDraft.objects.using(alias).get(pk=draft_id)
    assert draft.created_at <= sale.created_at
    assert InventoryItem.objects.using(alias).get(pk=item.pk).quantity_remaining == 0
    assert ListingDraft.objects.using(alias).filter(item=item).count() == 1
