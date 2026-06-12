from __future__ import annotations

from datetime import timedelta
from io import StringIO
import inspect
import json
import threading
import time
from urllib.parse import parse_qs, urlparse
import zipfile

import pytest
from cryptography.fernet import Fernet
from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

import integrations.ebay as ebay_integration
from apps.audit.models import AuditLog
from apps.audit.services import record
from apps.ebay.constants import (
    AUDIT_CONNECT_COMPLETED,
    AUDIT_CONNECT_FAILED,
    AUDIT_CONNECT_STARTED,
    AUDIT_DISCONNECT_COMPLETED,
    AUDIT_POLICY_REFRESH_COMPLETED,
    AUDIT_TOKEN_REFRESH_COMPLETED,
    AUDIT_TOKEN_REFRESH_FAILED,
    EBAY_SCOPES,
)
from apps.ebay.fields import can_decrypt
from apps.ebay.models import EbayAccountSnapshot, EbayCredential, OAuthState
from apps.ebay.services import (
    complete_connect,
    get_access_token,
    refresh_account_snapshot,
)


TEST_FERNET_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="


@pytest.fixture(autouse=True)
def ebay_settings(settings):
    settings.EBAY_ENV = ""
    settings.EBAY_CLIENT_ID = ""
    settings.EBAY_CLIENT_SECRET = ""
    settings.EBAY_RU_NAME = ""
    settings.MAGPIE_TOKEN_ENCRYPTION_KEY = TEST_FERNET_KEY


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="sprint6", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def raw_token_columns(credential_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            select refresh_token, access_token
            from ebay_ebaycredential
            where id = %s
            """,
            [credential_id.hex if connection.vendor == "sqlite" else str(credential_id)],
        )
        return cursor.fetchone()


@pytest.mark.django_db
def test_encrypted_field_round_trip_ciphertext_and_missing_key(settings):
    credential = EbayCredential.objects.create(
        environment="sandbox",
        ebay_user_id="user-1",
        ebay_username="seller",
        scopes=EBAY_SCOPES,
        refresh_token="plain-refresh-token",
        access_token="plain-access-token",
        access_token_expires_at=timezone.now() + timedelta(hours=1),
    )

    raw_refresh, raw_access = raw_token_columns(credential.id)
    assert "plain-refresh-token" not in raw_refresh
    assert "plain-access-token" not in raw_access
    assert can_decrypt(raw_refresh)
    assert can_decrypt(raw_access)
    assert Fernet(TEST_FERNET_KEY.encode()).decrypt(raw_refresh.encode()).decode() == "plain-refresh-token"

    credential.refresh_from_db()
    assert credential.refresh_token == "plain-refresh-token"
    assert credential.access_token == "plain-access-token"

    settings.MAGPIE_TOKEN_ENCRYPTION_KEY = ""
    with pytest.raises(ImproperlyConfigured, match="MAGPIE_TOKEN_ENCRYPTION_KEY"):
        EbayCredential.objects.create(
            environment="production",
            refresh_token="cannot-store",
        )


@pytest.mark.django_db
def test_connect_start_missing_key_hard_fails(api_client, settings):
    settings.MAGPIE_TOKEN_ENCRYPTION_KEY = ""

    response = api_client.post("/api/ebay/connect/start/", {}, format="json")

    assert response.status_code == 503
    assert "MAGPIE_TOKEN_ENCRYPTION_KEY" in response.data["detail"]
    assert OAuthState.objects.count() == 0


def test_http_consent_url_uses_sandbox_and_percent_encoded_scope(settings):
    settings.EBAY_ENV = "sandbox"
    settings.EBAY_CLIENT_ID = "sandbox-client-id-123456"
    settings.EBAY_CLIENT_SECRET = "sandbox-client-secret"
    settings.EBAY_RU_NAME = "sandbox-runame"

    url = ebay_integration.HttpEbayAuthAdapter().build_consent_url(state="state-value")
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    raw_scope = parsed.query.split("scope=", 1)[1].split("&", 1)[0]

    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://auth.sandbox.ebay.com/oauth2/authorize"
    assert query["redirect_uri"] == ["sandbox-runame"]
    assert query["response_type"] == ["code"]
    assert query["scope"] == [" ".join(EBAY_SCOPES)]
    assert "%20" in raw_scope
    assert "+" not in raw_scope


def test_http_consent_url_uses_current_runame_setting(settings):
    settings.EBAY_ENV = "sandbox"
    settings.EBAY_CLIENT_ID = "sandbox-client-id-123456"
    settings.EBAY_CLIENT_SECRET = "sandbox-client-secret"
    adapter = ebay_integration.HttpEbayAuthAdapter()

    settings.EBAY_RU_NAME = "first-runame"
    first_url = adapter.build_consent_url(state="state-one")
    first_query = parse_qs(urlparse(first_url).query)

    settings.EBAY_RU_NAME = "second-runame"
    second_url = adapter.build_consent_url(state="state-two")
    second_query = parse_qs(urlparse(second_url).query)

    assert first_query["redirect_uri"] == ["first-runame"]
    assert second_query["redirect_uri"] == ["second-runame"]


def test_http_identity_endpoint_uses_apiz_host(settings, monkeypatch):
    settings.EBAY_ENV = "production"
    settings.EBAY_CLIENT_ID = "production-client-id"
    settings.EBAY_CLIENT_SECRET = "production-client-secret"
    settings.EBAY_RU_NAME = "production-runame"
    called_urls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"userId": "user-1", "username": "seller"}'

    def fake_urlopen(request, timeout):
        called_urls.append(request.full_url)
        return FakeResponse()

    monkeypatch.setattr(ebay_integration, "urlopen", fake_urlopen)

    identity = ebay_integration.HttpEbayAccountAdapter().get_identity(access_token="access-token")

    assert identity == {"user_id": "user-1", "username": "seller"}
    assert called_urls == ["https://apiz.ebay.com/commerce/identity/v1/user/"]


def test_http_policy_optin_accepts_official_business_policy_program(settings, monkeypatch):
    settings.EBAY_ENV = "production"
    settings.EBAY_CLIENT_ID = "production-client-id"
    settings.EBAY_CLIENT_SECRET = "production-client-secret"
    settings.EBAY_RU_NAME = "production-runame"
    adapter = ebay_integration.HttpEbayAccountAdapter()

    monkeypatch.setattr(
        adapter,
        "_get",
        lambda path, access_token: {
            "programs": [{"programType": "SELLING_POLICY_MANAGEMENT"}]
        },
    )

    assert adapter.get_policy_optin_status(access_token="access-token") is True


def test_inspect_ebay_oauth_command_prints_safe_fields(settings):
    settings.EBAY_ENV = "sandbox"
    settings.EBAY_CLIENT_ID = "sandbox-client-id-123456"
    settings.EBAY_CLIENT_SECRET = "sandbox-client-secret"
    settings.EBAY_RU_NAME = "sandbox-runame"
    out = StringIO()

    call_command("inspect_ebay_oauth", stdout=out)

    text = out.getvalue()
    assert "environment=sandbox" in text
    assert "authorize_base=https://auth.sandbox.ebay.com/oauth2/authorize" in text
    assert "token_endpoint=https://api.sandbox.ebay.com/identity/v1/oauth2/token" in text
    assert "client_id_suffix=123456" in text
    assert "redirect_uri=sandbox-runame" in text
    assert "scope=https://api.ebay.com/oauth/api_scope/sell.inventory" in text
    assert "scope=https://api.ebay.com/oauth/api_scope/sell.account.readonly" in text
    assert "scope_separator_encoding=%20" in text
    assert "state_length=26" in text
    assert settings.EBAY_CLIENT_ID not in text
    assert settings.EBAY_CLIENT_SECRET not in text
    assert "debug-state-for-inspection" not in text


@pytest.mark.django_db
def test_fake_connect_status_policy_refresh_disconnect_and_secret_free_audit(api_client):
    start = api_client.post("/api/ebay/connect/start/", {}, format="json")
    assert start.status_code == 200, start.data
    assert set(start.data) == {"consent_url"}
    state = OAuthState.objects.get()

    complete = api_client.post(
        "/api/ebay/connect/complete/",
        {"pasted_url": f"https://example.test/callback?code=auth-code-secret&state={state.state}"},
        format="json",
    )

    assert complete.status_code == 200, complete.data
    assert complete.data["environment"] == "sandbox"
    assert complete.data["ebay_username"] == ""
    assert "fake-access-token" not in json.dumps(complete.data, default=str)
    state.refresh_from_db()
    assert state.consumed_at is not None

    status = api_client.get("/api/ebay/status/")
    assert status.status_code == 200
    assert status.data["configured"] is False
    assert status.data["connected"] is True
    assert status.data["environment"] == "sandbox"
    assert "fake-access-token" not in json.dumps(status.data, default=str)

    policies = api_client.post("/api/ebay/refresh-policies/", {}, format="json")
    assert policies.status_code == 200, policies.data
    assert policies.data["snapshot"]["opted_in"] is True
    assert policies.data["snapshot"]["policy_counts"] == {
        "payment": 1,
        "fulfillment": 1,
        "return": 1,
    }

    disconnect = api_client.post("/api/ebay/disconnect/", {}, format="json")
    assert disconnect.status_code == 204
    assert EbayCredential.objects.count() == 0

    actions = set(AuditLog.objects.values_list("action", flat=True))
    assert {
        AUDIT_CONNECT_STARTED,
        AUDIT_CONNECT_COMPLETED,
        AUDIT_POLICY_REFRESH_COMPLETED,
        AUDIT_DISCONNECT_COMPLETED,
    } <= actions
    assert_audit_payloads_secret_free()


@pytest.mark.django_db
def test_connect_persists_credential_without_identity_lookup(api_client, monkeypatch):
    def fail_if_called():
        raise AssertionError("Identity lookup must not gate Sprint 6 connect")

    monkeypatch.setattr(ebay_integration, "get_ebay_account_adapter", fail_if_called)
    start = api_client.post("/api/ebay/connect/start/", {}, format="json")
    state = OAuthState.objects.get()

    complete = api_client.post(
        "/api/ebay/connect/complete/",
        {"code": "auth-code-secret", "state": state.state},
        format="json",
    )

    assert start.status_code == 200, start.data
    assert complete.status_code == 200, complete.data
    credential = EbayCredential.objects.get()
    assert credential.ebay_username == ""
    assert credential.ebay_user_id == ""


@pytest.mark.django_db
def test_unknown_expired_and_reused_states_are_rejected_and_audited(api_client):
    unknown = api_client.post(
        "/api/ebay/connect/complete/",
        {"code": "auth-code-secret", "state": "missing-state"},
        format="json",
    )
    assert unknown.status_code == 400

    expired_state = OAuthState.objects.create(expires_at=timezone.now() - timedelta(minutes=1))
    expired = api_client.post(
        "/api/ebay/connect/complete/",
        {"code": "auth-code-secret", "state": expired_state.state},
        format="json",
    )
    assert expired.status_code == 400

    state = OAuthState.objects.create()
    first = api_client.post(
        "/api/ebay/connect/complete/",
        {"code": "auth-code-secret", "state": state.state},
        format="json",
    )
    assert first.status_code == 200
    reused = api_client.post(
        "/api/ebay/connect/complete/",
        {"code": "another-auth-code", "state": state.state},
        format="json",
    )
    assert reused.status_code == 400

    failed = AuditLog.objects.filter(action=AUDIT_CONNECT_FAILED)
    assert failed.count() == 3
    assert_audit_payloads_secret_free()


@pytest.mark.django_db
def test_valid_state_is_consumed_when_exchange_fails(api_client):
    state = OAuthState.objects.create()

    response = api_client.post(
        "/api/ebay/connect/complete/",
        {"code": "invalid", "state": state.state},
        format="json",
    )

    assert response.status_code == 503
    state.refresh_from_db()
    assert state.consumed_at is not None
    retry = api_client.post(
        "/api/ebay/connect/complete/",
        {"code": "auth-code-secret", "state": state.state},
        format="json",
    )
    assert retry.status_code == 400
    assert EbayCredential.objects.count() == 0
    assert_audit_payloads_secret_free()


@pytest.mark.django_db
def test_status_unconfigured_without_credentials_reports_not_configured(api_client, settings):
    settings.MAGPIE_TOKEN_ENCRYPTION_KEY = ""

    response = api_client.get("/api/ebay/status/")

    assert response.status_code == 200
    assert response.data == {
        "configured": False,
        "environment": "",
        "connected": False,
        "ebay_username": "",
        "scopes": [],
        "access_token_expires_at": None,
        "refresh_token_expires_at": None,
        "last_refresh_error": "",
        "snapshot": {
            "opted_in": None,
            "policy_counts": {"payment": 0, "fulfillment": 0, "return": 0},
            "fetched_at": None,
        },
    }


@pytest.mark.django_db
def test_refresh_reuses_cached_token_and_failure_records_error(monkeypatch):
    expired = timezone.now() - timedelta(minutes=5)
    credential = EbayCredential.objects.create(
        environment="sandbox",
        ebay_user_id="user-1",
        ebay_username="seller",
        scopes=EBAY_SCOPES,
        refresh_token="fake-refresh-token",
        access_token="expired-access-token",
        access_token_expires_at=expired,
    )
    adapter = ebay_integration.FakeEbayAuthAdapter()
    monkeypatch.setattr(ebay_integration, "get_ebay_auth_adapter", lambda: adapter)

    first = get_access_token()
    second = get_access_token()

    assert first == second
    assert adapter.refresh_count == 1
    assert first.startswith("fake-access-token-refreshed")
    assert AuditLog.objects.filter(action=AUDIT_TOKEN_REFRESH_COMPLETED).count() == 1

    credential.refresh_from_db()
    credential.access_token_expires_at = expired
    credential.refresh_token = "fail-refresh"
    credential.save()
    with pytest.raises(ebay_integration.EbayUnavailable):
        get_access_token()
    credential.refresh_from_db()
    assert credential.last_refresh_error
    assert AuditLog.objects.filter(action=AUDIT_TOKEN_REFRESH_FAILED).count() == 1
    assert_audit_payloads_secret_free()


@pytest.mark.django_db(transaction=True)
def test_refresh_select_for_update_single_flight_on_postgresql(monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("select_for_update concurrency is verified in PostgreSQL CI")

    expired = timezone.now() - timedelta(minutes=5)
    EbayCredential.objects.create(
        environment="sandbox",
        refresh_token="fake-refresh-token",
        access_token="expired-access-token",
        access_token_expires_at=expired,
    )
    adapter = SlowCountingAuthAdapter()
    monkeypatch.setattr(ebay_integration, "get_ebay_auth_adapter", lambda: adapter)

    results: list[str] = []
    errors: list[Exception] = []

    def worker():
        try:
            results.append(get_access_token())
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert not errors
    assert len(results) == 2
    assert results[0] == results[1]
    assert adapter.refresh_count == 1


@pytest.mark.django_db
def test_audit_api_read_only_filters_and_sanitizes_payload(api_client):
    record(
        actor="system",
        action=AUDIT_CONNECT_COMPLETED,
        target_type="ebay_credential",
        payload={
            "environment": "sandbox",
            "token": "secret-token",
            "nested": {"auth_code": "secret-code", "safe": "kept"},
        },
    )
    record(actor="system", action="inventory.local", target_type="item")

    listed = api_client.get(
        "/api/audit-log/",
        {"action_prefix": "ebay.", "target_type": "ebay_credential"},
    )

    assert listed.status_code == 200
    assert listed.data["count"] == 1
    payload = listed.data["results"][0]["payload"]
    assert payload == {"environment": "sandbox", "nested": {"safe": "kept"}}
    assert api_client.post("/api/audit-log/", {}, format="json").status_code == 405
    audit_id = listed.data["results"][0]["id"]
    assert api_client.patch(f"/api/audit-log/{audit_id}/", {}, format="json").status_code == 405
    assert api_client.delete(f"/api/audit-log/{audit_id}/").status_code == 405


@pytest.mark.django_db(transaction=True)
def test_backup_json_restore_includes_audit_and_ebay_tables_with_ciphertext(tmp_path, monkeypatch):
    record(actor="system", action=AUDIT_CONNECT_COMPLETED, target_type="ebay_credential")
    credential = EbayCredential.objects.create(
        environment="sandbox",
        ebay_username="seller",
        scopes=EBAY_SCOPES,
        refresh_token="plain-refresh-token",
        access_token="plain-access-token",
        access_token_expires_at=timezone.now() + timedelta(hours=1),
    )
    EbayAccountSnapshot.objects.create(
        environment="sandbox",
        business_policies_opted_in=True,
        payment_policies=[{"id": "pay"}],
        fulfillment_policies=[],
        return_policies=[],
        fetched_at=timezone.now(),
    )

    import apps.core.management.commands.backup as backup_module

    monkeypatch.setattr(backup_module.shutil, "which", lambda name: None)
    call_command("backup", output_dir=str(tmp_path))
    backup_path = sorted(tmp_path.glob("backup-*.zip"))[-1]

    extract_dir = tmp_path / "restore"
    with zipfile.ZipFile(backup_path) as archive:
        db_json = archive.read("db.json").decode("utf-8")
        archive.extract("db.json", extract_dir)
        manifest = json.loads(archive.read("manifest.json"))

    assert manifest["row_counts"]["audit.auditlog"] == 1
    assert manifest["row_counts"]["ebay.ebaycredential"] == 1
    assert manifest["row_counts"]["ebay.ebayaccountsnapshot"] == 1
    assert "plain-refresh-token" not in db_json
    assert "plain-access-token" not in db_json
    raw_refresh, raw_access = raw_token_columns(credential.id)
    assert raw_refresh in db_json
    assert raw_access in db_json

    call_command("flush", interactive=False, verbosity=0)
    call_command("loaddata", str(extract_dir / "db.json"), verbosity=0)

    restored = EbayCredential.objects.get()
    assert restored.refresh_token == "plain-refresh-token"
    assert restored.access_token == "plain-access-token"
    assert AuditLog.objects.count() == 1
    assert EbayAccountSnapshot.objects.count() == 1


def test_ebay_app_has_no_http_imports_and_integration_has_no_listing_writes():
    import apps.ebay.models as ebay_models
    import apps.ebay.services as ebay_services
    import apps.ebay.views as ebay_views

    app_source = "\n".join(
        inspect.getsource(module)
        for module in [ebay_models, ebay_services, ebay_views]
    )
    for token in ["request" + "s", "http" + "x", "aio" + "http", "url" + "lib", "url" + "open"]:
        assert token not in app_source.lower()

    integration_source = inspect.getsource(ebay_integration)
    for token in ["create" + "offer", "publish" + "offer", "create" + "or" + "replace" + "inventory" + "item", "relist", "revise", "notification"]:
        assert token not in integration_source.lower()


def test_admin_redacts_tokens():
    model_admin = admin.site._registry[EbayCredential]

    assert "refresh_token" not in model_admin.fields
    assert "access_token" not in model_admin.fields
    assert model_admin.redacted_refresh_token(object()) == "***"
    assert model_admin.redacted_access_token(object()) == "***"


def test_local_dev_frontend_origin_is_csrf_trusted(settings):
    assert "http://localhost:5174" in settings.CSRF_TRUSTED_ORIGINS
    assert "http://127.0.0.1:5174" in settings.CSRF_TRUSTED_ORIGINS


class SlowCountingAuthAdapter:
    def __init__(self):
        self.refresh_count = 0
        self.lock = threading.Lock()

    def refresh(self, *, refresh_token: str):
        with self.lock:
            self.refresh_count += 1
        time.sleep(0.2)
        now = timezone.now()
        return ebay_integration.TokenSet(
            access_token="single-flight-access-token",
            access_expires_at=now + timedelta(hours=2),
            refresh_token=None,
            refresh_expires_at=None,
        )


def assert_audit_payloads_secret_free():
    payloads = json.dumps(list(AuditLog.objects.values_list("payload", flat=True))).lower()
    for secret in ["auth-code-secret", "another-auth-code", "secret-token", "secret-code"]:
        assert secret not in payloads
    for blocked_key in ["token", "code", "access_token", "refresh_token", "auth_code"]:
        assert blocked_key not in payloads
