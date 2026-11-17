from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO, StringIO
import json
from copy import deepcopy
from threading import Barrier
from urllib.error import HTTPError, URLError

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import close_old_connections, connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from rest_framework.test import APIClient

from apps.ebay import adapters, connection_health as health, services
from apps.ebay.diagnostics import diagnostic, public_diagnostic
from apps.ebay.models import EbayConnectionHealth, EbayCredential
from apps.ebay.workflow_errors import provider_error

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def config(settings):
    settings.EBAY_ENV = ""
    settings.MAGPIE_TOKEN_ENCRYPTION_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="


@pytest.fixture
def credential():
    return EbayCredential.objects.create(environment="sandbox", refresh_token="synthetic-refresh", access_token="synthetic-access",
        access_token_expires_at=timezone.now() + timedelta(hours=1), refresh_token_expires_at=timezone.now() + timedelta(days=60))


def row(error_id=25003, domain="API_INVENTORY", **kwargs):
    return {"errorId": error_id, "domain": domain, "category": "REQUEST", **kwargs}


@pytest.mark.parametrize("operation,status,payload,failure,expected,field", [
    ("inventory.publish", 403, {"errors": [row(1100, "OAuth")]}, None, "permission", None),
    ("inventory.publish", 403, {"errors": [row(1100, "OAuth", message="Insufficient scope for this operation")]}, None, "missing_scope", None),
    ("inventory.publish", 401, {"errors": [row(1001, "OAuth")]}, None, "access_expired", None),
    ("oauth.refresh", 400, {"error": "invalid_grant"}, None, "reconnect", None),
    ("oauth.refresh", 401, {"error": "invalid_client"}, None, "configuration", None),
    ("oauth.refresh", 503, {}, None, "renewal_temporary", None),
    ("oauth.refresh", None, {}, "network", "renewal_temporary", None),
    ("inventory.publish", 400, {"errors": [row(25026)]}, None, "selling_limit", None),
    ("inventory.publish", 400, {"errors": [row(25097)]}, None, "restriction", None),
    ("inventory.publish", 403, {"errors": [row(99999, message="This operation requires a store subscription")]}, None, "subscription", None),
    ("inventory.publish", 400, {"errors": [row(25003)]}, None, "validation", "price"),
    ("account.payment", 400, {"errors": [row(25003)]}, None, "unknown", None),
    ("inventory.publish", 400, {"errors": [row(25016, parameters=[{"name": "fieldName", "value": "title"}])]}, None, "validation", "title"),
    ("inventory.offer", 404, {}, None, "missing_resource", None),
    ("inventory.update", 409, {}, None, "conflict", None),
    ("account.payment", 429, {}, None, "rate_limit", None),
    ("finances.transactions", 502, {}, None, "outage", None),
    ("inventory.publish", None, {}, "network", "network", None),
    ("inventory.publish", 200, {}, "malformed", "malformed", None),
    ("inventory.publish", 400, {"errors": [row(99999)]}, None, "unknown", None),
])
def test_operation_aware_classes(operation, status, payload, failure, expected, field):
    value = diagnostic(operation, status=status, payload=payload, failure=failure)
    assert value["issues"][0]["kind"] == expected
    assert value["issues"][0]["field"] == field
    if expected == "permission": assert "cause not confirmed" in public_diagnostic(value)["issues"][0]["message"]


def test_multiple_errors_warnings_and_secret_text_are_allowlisted():
    value = diagnostic("inventory.publish", status=400, payload={"errors": [
        row(25003, message="SYNTHETIC_DO_NOT_STORE", longMessage="Bearer SYNTHETIC_DO_NOT_STORE", parameters=[{"name": "price", "value": "SYNTHETIC_DO_NOT_STORE"}]),
        row(25004)], "warnings": [row(25402)], "headers": {"Authorization": "SYNTHETIC_DO_NOT_STORE"}})
    assert len(value["issues"]) == 3
    assert "SYNTHETIC_DO_NOT_STORE" not in json.dumps(value)
    assert "raw" not in json.dumps(value) and "headers" not in json.dumps(value)


@pytest.mark.parametrize("path", ["save", "update", "bulk_create", "bulk_update"])
def test_model_privacy_boundary_rejects_secret_bearing_diagnostics(path):
    entry = {"last_success": None, "current_failure": {"sequence": 1,
        "diagnostic": {**diagnostic("inventory.publish", status=403), "message": "SYNTHETIC_DO_NOT_STORE"}}, "warnings": None}
    instance = EbayConnectionHealth(environment="sandbox", principal="seller", operations={"inventory.publish": entry})
    with pytest.raises(ValidationError):
        if path == "save": instance.save()
        elif path == "update": EbayConnectionHealth.objects.all().update(operations=instance.operations)
        elif path == "bulk_create": EbayConnectionHealth.objects.bulk_create([instance])
        else: EbayConnectionHealth.objects.bulk_update([instance], ["operations"])
    assert EbayConnectionHealth.objects.count() == 0


def test_unrelated_success_and_late_responses_cannot_clear_current_failure():
    old = health.begin("inventory.publish")
    newest = health.begin("inventory.publish")
    health.finish(newest, failure=diagnostic("inventory.publish", status=403))
    health.finish(old, status=200)
    health.finish(health.begin("taxonomy.tree"), status=200)
    data = health.summary()
    assert data["alerts"][0]["operation"] == "inventory.publish"
    entry = EbayConnectionHealth.objects.get(principal="seller").operations["inventory.publish"]
    assert entry["last_success"] and entry["current_failure"]
    health.finish(health.begin("inventory.publish"), status=200)
    assert not health.summary()["alerts"]


def test_reconnect_fences_old_results_and_preserves_application_health():
    ticket = health.begin("inventory.items")
    health.finish(health.begin("taxonomy.tree"), status=200)
    health.reset_seller()
    health.finish(ticket, failure=diagnostic("inventory.items", status=403))
    assert not health.summary()["alerts"]
    assert EbayConnectionHealth.objects.get(principal="seller").operations == {}
    assert "taxonomy.tree" in EbayConnectionHealth.objects.get(principal="application").operations


def test_health_get_is_transient_no_network_no_token_decryption(credential, django_user_model, monkeypatch):
    client = APIClient(); client.force_authenticate(django_user_model.objects.create_user(username="health-read"))
    monkeypatch.setattr(adapters, "urlopen", lambda *a, **k: pytest.fail("No call on load"))
    monkeypatch.setattr(services, "get_access_token", lambda **k: pytest.fail("No renewal on load"))
    monkeypatch.setattr("apps.ebay.fields.EncryptedTextField.from_db_value", lambda *a, **k: pytest.fail("No credential decryption on load"))
    before = EbayConnectionHealth.objects.count()
    response = client.get("/api/ebay/connection-health/")
    assert response.status_code == 200
    assert response.data["checks"]["seller"]["completed_at"] is None
    assert response.data["scopes"]["grant_status"] == "not_independently_verified"
    assert not response.data["scopes"]["requested"]
    assert EbayConnectionHealth.objects.count() == before == 0
    assert "synthetic" not in json.dumps(response.data, default=str)


def test_manual_checks_are_throttled_and_never_write_listings(credential, monkeypatch):
    calls = []
    monkeypatch.setattr(adapters, "read_connection_probe", lambda api, **kwargs: calls.append(api) or 0)
    monkeypatch.setattr(adapters.HttpEbayInventoryAdapter, "publish_offer", lambda **k: pytest.fail("No write"))
    first = health.check_connection()
    assert not first["throttled"] and first["health"]["checks"]["seller"]["completed_at"]
    assert calls == ["Inventory", "Account", "Fulfilment", "Finances", "Taxonomy"]
    assert health.check_connection()["throttled"]
    assert len(calls) == 5
    assert "media.upload" not in [r["operation"] for r in health.summary()["operations"]]


def test_expired_access_renews_first_without_reconnect_banner(credential):
    credential.access_token_expires_at = timezone.now() - timedelta(minutes=5)
    credential.save(update_fields=["access_token_expires_at"])
    assert services.get_access_token() != "synthetic-access"
    assert not health.summary()["alerts"]
    credential.refresh_from_db()
    assert credential.last_refresh_at and credential.access_token_expires_at > timezone.now()


@pytest.mark.parametrize("status,payload,kind", [(503, {}, "renewal_temporary"), (400, {"error": "invalid_grant"}, "reconnect"), (401, {"error": "invalid_client"}, "configuration")])
def test_renewal_failures_remain_distinct(credential, monkeypatch, status, payload, kind):
    credential.access_token_expires_at = timezone.now() - timedelta(minutes=5); credential.save()
    class Broken:
        def refresh(self, **kwargs):
            raise adapters.EbayHttpError("DO_NOT_STORE", http_status=status, error_ids=(), diagnostic=diagnostic("oauth.refresh", status=status, payload=payload))
    monkeypatch.setattr("integrations.ebay.get_ebay_auth_adapter", lambda: Broken())
    with pytest.raises(adapters.EbayUnavailable): services.get_access_token()
    assert health.summary()["alerts"][0]["issues"][0]["kind"] == kind
    credential.refresh_from_db()
    assert "DO_NOT_STORE" not in credential.last_refresh_error


def test_access_rejection_renews_get_once_but_never_replays_write(credential, monkeypatch):
    calls = []
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return b'{"inventoryItems": []}'
    def send(request, **kwargs):
        calls.append(request.method)
        if len(calls) == 1:
            raise HTTPError(request.full_url, 401, "Denied", {}, BytesIO(json.dumps({"errors": [row(1001, "OAuth")]}).encode()))
        return Response()
    monkeypatch.setattr(adapters, "urlopen", send)
    kwargs = dict(access_token="synthetic-access", timeout_seconds=1, service_name="test")
    adapters._request_json("https://api.ebay.com/sell/inventory/v1/inventory_item", method="GET", **kwargs)
    assert calls == ["GET", "GET"] and not health.summary()["alerts"]
    calls.clear()
    with pytest.raises(adapters.EbayHttpError): adapters._request_json("https://api.ebay.com/sell/inventory/v1/offer/1/publish", method="POST", **kwargs)
    assert calls == ["POST"]


@pytest.mark.parametrize("body", [b'{"message":"DO_NOT_STORE"}', b'<html>DO_NOT_STORE</html>'])
def test_transport_does_not_retain_raw_bodies_headers_or_exception_cause(monkeypatch, body):
    def send(request, **kwargs): raise HTTPError(request.full_url, 403, "DO_NOT_STORE", {"Authorization": "DO_NOT_STORE"}, BytesIO(body))
    monkeypatch.setattr(adapters, "urlopen", send)
    with pytest.raises(adapters.EbayHttpError) as result:
        adapters._request_json("https://api.ebay.com/sell/inventory/v1/offer/1/publish", access_token="synthetic", method="POST", timeout_seconds=1, service_name="test")
    assert "DO_NOT_STORE" not in str(result.value) + json.dumps(result.value.__dict__)
    assert result.value.__suppress_context__
    assert result.value.__context__ is None
    assert "DO_NOT_STORE" not in json.dumps(EbayConnectionHealth.objects.get(principal="seller").operations)


def test_diagnosis_does_not_change_phase5_uncertain_outcome():
    failure = adapters.EbayHttpError("do not expose", http_status=409, error_ids=(25003,), diagnostic=diagnostic("inventory.publish", status=409, payload={"errors": [row(25003)]}))
    assert provider_error(failure, "publishOffer")["kind"] == "unknown_outcome"
    assert provider_error(TimeoutError(), "publishOffer")["kind"] == "unknown_outcome"


def test_finances_probe_preserves_existing_apiz_marketplace_header(settings, monkeypatch):
    settings.EBAY_ENV = "production"
    captured = []
    monkeypatch.setattr(adapters, "_request_json", lambda url, **kwargs: captured.append((url, kwargs)) or {"transactions": []})
    assert adapters.read_connection_probe("Finances", access_token="synthetic") == 0
    assert captured[0][0] == "https://apiz.ebay.com/sell/finances/v1/transaction?limit=1"
    assert captured[0][1]["method"] == "GET"
    assert captured[0][1]["headers"]["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_AU"


@pytest.mark.parametrize("body", [b'[]', b'{"warnings":"DO_NOT_STORE"}', b'{"errors":{"body":"DO_NOT_STORE"}}'])
def test_malformed_response_never_becomes_healthy_or_exposes_body(monkeypatch, body):
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return body
    monkeypatch.setattr(adapters, "urlopen", lambda *a, **k: Response())
    with pytest.raises(adapters.EbayUnavailable) as result:
        adapters._request_json("https://api.ebay.com/sell/inventory/v1/offer/1/publish", access_token="synthetic", method="POST", timeout_seconds=1, service_name="test")
    assert result.value.diagnostic["issues"][0]["kind"] == "malformed"
    entry = EbayConnectionHealth.objects.get(principal="seller").operations["inventory.publish"]
    assert entry["last_success"] is None and entry["current_failure"]
    assert "DO_NOT_STORE" not in str(result.value)


@pytest.mark.django_db(transaction=True)
def test_migration_sql_creates_only_new_table_and_model_constraint():
    sql = StringIO(); call_command("sqlmigrate", "ebay", "0004", stdout=sql)
    text = sql.getvalue()
    assert "CREATE TABLE" in text and "ebay_ebayconnectionhealth" in text
    assert not any(word in text.upper() for word in ("ALTER TABLE", "DROP TABLE", "INSERT INTO", "UPDATE ", "DELETE FROM"))
    assert "one_connection_health_per_principal" in text


@pytest.mark.django_db(transaction=True)
def test_concurrent_health_results_are_fenced_on_file_sqlite_and_postgres(tmp_path, django_db_blocker):
    with django_db_blocker.unblock():
        alias = "default"
        if connection.vendor == "sqlite":
            alias = "health_file"
            config = deepcopy(connections["default"].settings_dict)
            config.update(NAME=str(tmp_path / "health.sqlite3"), OPTIONS={"timeout": 10})
            connections.databases[alias] = config
            executor = MigrationExecutor(connections[alias]); executor.migrate(executor.loader.graph.leaf_nodes())
        old, new = health.begin("inventory.items", using=alias), health.begin("inventory.items", using=alias)
        barrier = Barrier(2)
        def worker(ticket, failed):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                health.finish(ticket, failure=diagnostic("inventory.items", status=403) if failed else None, status=200)
            finally: connections[alias].close()
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(worker, new, True), pool.submit(worker, old, False)]
                for future in futures: future.result()
            entry = EbayConnectionHealth.objects.using(alias).get(principal="seller").operations["inventory.items"]
            assert entry["current_failure"]["diagnostic"]["http_status"] == 403
            assert entry["last_success"]
        finally:
            if alias != "default":
                connections[alias].close(); del connections[alias]; del connections.databases[alias]
