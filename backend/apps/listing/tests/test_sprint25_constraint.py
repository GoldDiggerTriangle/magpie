from copy import deepcopy
from importlib import import_module
from io import StringIO
import json
from types import SimpleNamespace

import pytest
from django.core.management import call_command, CommandError
from django.db import connection, connections, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test.utils import CaptureQueriesContext

from apps.catalog.models import ProductCategory
from apps.inventory.models import InventoryItem
from apps.listing.canonical_check import CONSTRAINT_NAME
from apps.listing.draft_status import active_draft_filter, classify_draft_status
from apps.listing.models import ListingDraft


MIGRATION = import_module("apps.listing.migrations.0005_listingdraft_one_active")
BEFORE = ("listing", "0004_listingdraft_canonical_statuses")
AFTER = ("listing", "0005_listingdraft_one_active")
ACTIVE = [status for status in ListingDraft.Status.values if classify_draft_status(status) == "active"] + ["future_status"]


@pytest.fixture
def item(db):
    category = ProductCategory.objects.create(name="Constraint", slug="constraint", sku_prefix="UC")
    return InventoryItem.objects.create(title="Owned constraint item", category=category)


@pytest.mark.django_db
@pytest.mark.parametrize("status", ACTIVE)
def test_installed_constraint_covers_each_active_and_unknown_status(item, status):
    constraint = next(row for row in ListingDraft._meta.constraints if row.name == CONSTRAINT_NAME)
    installed = MIGRATION.Migration.operations[1].constraint
    assert constraint.condition == installed.condition == active_draft_filter()
    with connection.cursor() as cursor:
        info = connection.introspection.get_constraints(cursor, ListingDraft._meta.db_table)
    assert info[CONSTRAINT_NAME]["unique"] is True
    assert info[CONSTRAINT_NAME]["columns"] == ["item_id", "channel"]
    ListingDraft.objects.create(item=item, status=status, channel="first")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ListingDraft.objects.create(item=item, channel="first")
    ListingDraft.objects.create(item=item, channel="second")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ListingDraft.objects.create(item=item, channel="second", status=status)
    # Repeated terminal history is outside the constraint, even beside an active row.
    for terminal in ["published", "archived"]:
        for _ in range(2):
            ListingDraft.objects.create(item=item, channel="first", status=terminal)
    assert ListingDraft.objects.filter(item=item, channel="first").count() == 5


@pytest.mark.django_db
def test_precheck_is_read_only_and_does_not_install_or_repair(item):
    ListingDraft.objects.create(item=item)
    ListingDraft.objects.create(item=item, channel="generic")
    before = list(ListingDraft.objects.order_by("pk").values())
    out = StringIO()
    with CaptureQueriesContext(connection) as queries:
        call_command("check_canonical_drafts", stdout=out)
    report = json.loads(out.getvalue())
    assert report == {"violation_count": 0, "violations": [], "constraint_installed": True}
    assert list(ListingDraft.objects.order_by("pk").values()) == before
    assert all(query["sql"].lstrip().upper().startswith(("SELECT", "PRAGMA")) for query in queries)


@pytest.mark.django_db
def test_frozen_migration_precheck_names_seeded_violations_on_each_backend(item):
    # Emulate the before-B index state only inside this rolled-back test.
    constraint = next(row for row in ListingDraft._meta.constraints if row.name == CONSTRAINT_NAME)
    with connection.cursor() as cursor:
        cursor.execute(str(constraint.remove_sql(ListingDraft, connection.schema_editor())))
    ListingDraft.objects.create(item=item, status="ready")
    ListingDraft.objects.create(item=item, status="future_status")
    before = list(ListingDraft.objects.order_by("pk").values())
    historical_apps = MigrationExecutor(connection).loader.project_state([BEFORE]).apps
    with pytest.raises(RuntimeError, match=item.sku):
        MIGRATION.assert_no_active_duplicates(historical_apps, SimpleNamespace(connection=connection))
    out = StringIO()
    with pytest.raises(CommandError, match=item.sku):
        call_command("check_canonical_drafts", stdout=out)
    assert json.loads(out.getvalue())["violation_count"] == 1
    assert list(ListingDraft.objects.order_by("pk").values()) == before


@pytest.fixture
def sqlite_file(tmp_path, django_db_blocker):
    alias = "canonical_file"
    config = deepcopy(connections["default"].settings_dict)
    config.update(ENGINE="django.db.backends.sqlite3", NAME=str(tmp_path / "canonical.sqlite3"), OPTIONS={})
    connections.databases[alias] = config
    try:
        with django_db_blocker.unblock():
            db = connections[alias]
            executor = MigrationExecutor(db)
            executor.migrate([BEFORE])
            apps = executor.loader.project_state([BEFORE]).apps
            category = apps.get_model("catalog", "ProductCategory").objects.using(alias).create(name="File constraint", slug="file-constraint", sku_prefix="FC")
            item = apps.get_model("inventory", "InventoryItem").objects.using(alias).create(title="Own file item", category=category, sku="FC-00001")
            model = apps.get_model("listing", "ListingDraft")
            assert db.vendor == "sqlite" and db.settings_dict["NAME"] != ":memory:"
            assert (tmp_path / "canonical.sqlite3").is_file()
            yield db, item, model
    finally:
        connections[alias].close()
        del connections[alias]
        del connections.databases[alias]


def test_migration_b_seeded_violation_aborts_atomically_and_names_item(sqlite_file):
    db, item, model = sqlite_file
    alias = db.alias
    model.objects.using(alias).create(item=item, status="ready")
    model.objects.using(alias).create(item=item, status="future_status")
    before = list(model.objects.using(alias).order_by("pk").values())
    with pytest.raises(RuntimeError, match=r"FC-00001.*2 active drafts"):
        MigrationExecutor(db).migrate([AFTER])
    assert list(model.objects.using(alias).order_by("pk").values()) == before
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM django_migrations WHERE app='listing' AND name=%s", [AFTER[1]])
        assert cursor.fetchone()[0] == 0
        assert CONSTRAINT_NAME not in db.introspection.get_constraints(cursor, model._meta.db_table)
    out = StringIO()
    with pytest.raises(CommandError, match="FC-00001"):
        call_command("check_canonical_drafts", database=alias, stdout=out)
    report = json.loads(out.getvalue())
    assert report["violation_count"] == 1 and report["constraint_installed"] is False
    assert report["violations"][0]["sku"] == "FC-00001"
    assert report["violations"][0]["item_id"] == str(item.pk)


def test_file_backed_sqlite_installs_real_partial_index_and_rejects_every_active_status(sqlite_file):
    db, item, model = sqlite_file
    MigrationExecutor(db).migrate([AFTER])
    with db.cursor() as cursor:
        info = db.introspection.get_constraints(cursor, model._meta.db_table)
        assert info[CONSTRAINT_NAME]["unique"] is True
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name=%s", [CONSTRAINT_NAME])
        sql = cursor.fetchone()[0]
        assert "WHERE NOT" in sql and "archived" in sql and "published" in sql
    for index, status in enumerate(ACTIVE):
        channel = f"scope-{index}"
        model.objects.using(db.alias).create(item=item, channel=channel, status=status)
        with pytest.raises(IntegrityError):
            with transaction.atomic(using=db.alias):
                model.objects.using(db.alias).create(item=item, channel=channel, status="draft")
        for terminal in ["published", "archived"]:
            model.objects.using(db.alias).create(item=item, channel=channel, status=terminal)
    assert model.objects.using(db.alias).count() == len(ACTIVE) * 3
