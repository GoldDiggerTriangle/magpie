from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import base64
import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from apps.ebay.constants import (
    DEFAULT_FAKE_ENVIRONMENT,
    EBAY_ENV_PRODUCTION,
    EBAY_ENV_SANDBOX,
    EBAY_ENVIRONMENTS,
    EBAY_SCOPES,
)


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    access_expires_at: datetime
    refresh_token: str | None
    refresh_expires_at: datetime | None


class EbayUnavailable(Exception):
    """Raised when eBay auth/account data cannot be fetched safely."""


class EbayAuthAdapter(Protocol):
    def build_consent_url(self, *, state: str) -> str:
        ...

    def exchange_code(self, *, code: str) -> TokenSet:
        ...

    def refresh(self, *, refresh_token: str) -> TokenSet:
        ...


class EbayAccountAdapter(Protocol):
    def get_identity(self, *, access_token: str) -> dict:
        ...

    def get_policy_optin_status(self, *, access_token: str) -> bool:
        ...

    def list_policies(self, *, access_token: str, kind: str) -> list[dict]:
        ...


class HttpEbayAuthAdapter:
    def __init__(self, *, environment: str | None = None, timeout_seconds: int | None = None):
        self.environment = _configured_environment(environment)
        self.timeout_seconds = timeout_seconds or settings.EBAY_HTTP_TIMEOUT_SECONDS

    def build_consent_url(self, *, state: str) -> str:
        _require_oauth_config()
        query = urlencode(
            {
                "client_id": settings.EBAY_CLIENT_ID,
                "redirect_uri": settings.EBAY_RU_NAME,
                "response_type": "code",
                "scope": " ".join(EBAY_SCOPES),
                "state": state,
            },
            quote_via=quote,
        )
        return f"{_auth_base(self.environment)}/oauth2/authorize?{query}"

    def exchange_code(self, *, code: str) -> TokenSet:
        _require_oauth_config()
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.EBAY_RU_NAME,
        }
        return self._token_request(payload)

    def refresh(self, *, refresh_token: str) -> TokenSet:
        _require_oauth_config()
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": " ".join(EBAY_SCOPES),
        }
        return self._token_request(payload)

    def _token_request(self, payload: dict[str, str]) -> TokenSet:
        body = urlencode(payload).encode("utf-8")
        credentials = f"{settings.EBAY_CLIENT_ID}:{settings.EBAY_CLIENT_SECRET}".encode("utf-8")
        request = Request(
            f"{_api_base(self.environment)}/identity/v1/oauth2/token",
            data=body,
            headers={
                "Authorization": f"Basic {base64.b64encode(credentials).decode('ascii')}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise EbayUnavailable(f"eBay token endpoint returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise EbayUnavailable("eBay token endpoint request failed.") from exc

        try:
            return _token_set_from_payload(data)
        except (KeyError, TypeError, ValueError) as exc:
            raise EbayUnavailable("eBay token endpoint response could not be parsed.") from exc


class HttpEbayAccountAdapter:
    def __init__(self, *, environment: str | None = None, timeout_seconds: int | None = None):
        self.environment = _configured_environment(environment)
        self.timeout_seconds = timeout_seconds or settings.EBAY_HTTP_TIMEOUT_SECONDS

    def get_identity(self, *, access_token: str) -> dict:
        payload = self._get("/commerce/identity/v1/user/", access_token=access_token)
        return {
            "user_id": str(payload.get("userId") or payload.get("user_id") or ""),
            "username": str(payload.get("username") or payload.get("userName") or ""),
        }

    def get_policy_optin_status(self, *, access_token: str) -> bool:
        payload = self._get(
            "/sell/account/v1/program/get_opted_in_programs",
            access_token=access_token,
        )
        programs = payload.get("programs") or payload.get("program") or payload
        if not isinstance(programs, list):
            return False
        return any(
            str(program.get("programType", "")).lower() == "seller_policies"
            for program in programs
            if isinstance(program, dict)
        )

    def list_policies(self, *, access_token: str, kind: str) -> list[dict]:
        kind = _normalize_policy_kind(kind)
        payload = self._get(
            f"/sell/account/v1/{kind}_policy?marketplace_id=EBAY_AU",
            access_token=access_token,
        )
        key = f"{kind}Policies"
        policies = payload.get(key) or payload.get("policies") or []
        if not isinstance(policies, list):
            raise EbayUnavailable("eBay policy response could not be parsed.")
        return policies

    def _get(self, path: str, *, access_token: str) -> dict:
        request = Request(
            f"{_api_base(self.environment)}{path}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise EbayUnavailable(f"eBay account endpoint returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise EbayUnavailable("eBay account endpoint request failed.") from exc


class FakeEbayAuthAdapter:
    def __init__(self, *, refresh_fails: bool = False, exchange_fails: bool = False):
        self.refresh_fails = refresh_fails
        self.exchange_fails = exchange_fails
        self.exchange_count = 0
        self.refresh_count = 0

    def build_consent_url(self, *, state: str) -> str:
        query = urlencode({"code": "fake-auth-code", "state": state})
        return f"https://signin.sandbox.ebay.test/consent?{query}"

    def exchange_code(self, *, code: str) -> TokenSet:
        self.exchange_count += 1
        if self.exchange_fails or code in {"", "invalid", "fail"}:
            raise EbayUnavailable("eBay authorization code exchange failed.")
        now = timezone.now()
        return TokenSet(
            access_token="fake-access-token",
            access_expires_at=now + timedelta(hours=2),
            refresh_token="fake-refresh-token",
            refresh_expires_at=now + timedelta(days=540),
        )

    def refresh(self, *, refresh_token: str) -> TokenSet:
        self.refresh_count += 1
        if self.refresh_fails or refresh_token == "fail-refresh":
            raise EbayUnavailable("eBay token refresh failed.")
        now = timezone.now()
        return TokenSet(
            access_token=f"fake-access-token-refreshed-{self.refresh_count}",
            access_expires_at=now + timedelta(hours=2),
            refresh_token=None,
            refresh_expires_at=None,
        )


class FakeEbayAccountAdapter:
    def __init__(self, *, policy_fails: bool = False):
        self.policy_fails = policy_fails

    def get_identity(self, *, access_token: str) -> dict:
        if not access_token:
            raise EbayUnavailable("Missing eBay access token.")
        return {"user_id": "fake-ebay-user-id", "username": "fake_sandbox_seller"}

    def get_policy_optin_status(self, *, access_token: str) -> bool:
        if self.policy_fails:
            raise EbayUnavailable("eBay policy opt-in status failed.")
        return True

    def list_policies(self, *, access_token: str, kind: str) -> list[dict]:
        if self.policy_fails:
            raise EbayUnavailable("eBay policy list failed.")
        kind = _normalize_policy_kind(kind)
        return [
            {
                f"{kind}PolicyId": f"fake-{kind}-policy",
                "name": f"Fake {kind.title()} Policy",
                "marketplaceId": "EBAY_AU",
            }
        ]


def get_ebay_auth_adapter() -> EbayAuthAdapter:
    if not settings.EBAY_ENV:
        return FakeEbayAuthAdapter()
    return HttpEbayAuthAdapter()


def get_ebay_account_adapter() -> EbayAccountAdapter:
    if not settings.EBAY_ENV:
        return FakeEbayAccountAdapter()
    return HttpEbayAccountAdapter()


def effective_environment() -> str:
    env = str(settings.EBAY_ENV or "").strip().lower()
    if not env:
        return DEFAULT_FAKE_ENVIRONMENT
    if env not in EBAY_ENVIRONMENTS:
        raise EbayUnavailable("EBAY_ENV must be sandbox or production.")
    return env


def is_configured() -> bool:
    return str(settings.EBAY_ENV or "").strip().lower() in EBAY_ENVIRONMENTS


def _configured_environment(environment: str | None) -> str:
    env = str(environment or settings.EBAY_ENV or "").strip().lower()
    if env not in EBAY_ENVIRONMENTS:
        raise EbayUnavailable("EBAY_ENV must be sandbox or production.")
    return env


def _require_oauth_config() -> None:
    missing = [
        name
        for name in ["EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET", "EBAY_RU_NAME"]
        if not getattr(settings, name, "")
    ]
    if missing:
        raise EbayUnavailable(f"{', '.join(missing)} must be configured for eBay OAuth.")


def _auth_base(environment: str) -> str:
    if environment == EBAY_ENV_SANDBOX:
        return "https://auth.sandbox.ebay.com"
    if environment == EBAY_ENV_PRODUCTION:
        return "https://auth.ebay.com"
    raise EbayUnavailable("EBAY_ENV must be sandbox or production.")


def _api_base(environment: str) -> str:
    if environment == EBAY_ENV_SANDBOX:
        return "https://api.sandbox.ebay.com"
    if environment == EBAY_ENV_PRODUCTION:
        return "https://api.ebay.com"
    raise EbayUnavailable("EBAY_ENV must be sandbox or production.")


def _token_set_from_payload(data: dict) -> TokenSet:
    now = timezone.now()
    access_expires_in = int(data["expires_in"])
    refresh_expires_in = data.get("refresh_token_expires_in")
    refresh_token = data.get("refresh_token")
    return TokenSet(
        access_token=str(data["access_token"]),
        access_expires_at=now + timedelta(seconds=access_expires_in),
        refresh_token=str(refresh_token) if refresh_token else None,
        refresh_expires_at=(
            now + timedelta(seconds=int(refresh_expires_in))
            if refresh_expires_in is not None
            else None
        ),
    )


def _normalize_policy_kind(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    if normalized not in {"payment", "fulfillment", "return"}:
        raise EbayUnavailable(f"Unsupported eBay policy kind: {kind}")
    return normalized
