from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import base64
import json
import uuid
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from apps.ebay.constants import (
    DEFAULT_FAKE_ENVIRONMENT,
    EBAY_APP_SCOPE,
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

    def client_credentials(self, *, scope: str = EBAY_APP_SCOPE) -> TokenSet:
        ...


class EbayAccountAdapter(Protocol):
    def get_identity(self, *, access_token: str) -> dict:
        ...

    def get_policy_optin_status(self, *, access_token: str) -> bool:
        ...

    def list_policies(self, *, access_token: str, kind: str) -> list[dict]:
        ...


class EbayMediaAdapter(Protocol):
    def upload_image(self, *, access_token: str, file) -> str:
        ...


class EbayInventoryAdapter(Protocol):
    def upsert_inventory_item(self, *, access_token, sku, payload) -> None:
        ...

    def create_offer(self, *, access_token, payload) -> str:
        ...

    def update_offer(self, *, access_token, offer_id, payload) -> None:
        ...

    def withdraw_offer(self, *, access_token, offer_id) -> None:
        ...

    def publish_offer(self, *, access_token, offer_id) -> str:
        ...

    def get_offer(self, *, access_token, offer_id) -> dict:
        ...

    def create_inventory_location(self, *, access_token, merchant_location_key, payload) -> None:
        ...


class EbayTaxonomyAdapter(Protocol):
    def default_tree_id(self, *, marketplace: str) -> str:
        ...

    def suggest_categories(self, *, q: str) -> list[dict]:
        ...

    def item_aspects(self, *, category_id: str) -> list[dict]:
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

    def client_credentials(self, *, scope: str = EBAY_APP_SCOPE) -> TokenSet:
        _require_oauth_config()
        payload = {
            "grant_type": "client_credentials",
            "scope": scope,
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
        payload = self._get(
            "/commerce/identity/v1/user/",
            access_token=access_token,
            base_url=_identity_base(self.environment),
        )
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
            _is_business_policies_program(program)
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

    def _get(self, path: str, *, access_token: str, base_url: str | None = None) -> dict:
        request = Request(
            f"{base_url or _api_base(self.environment)}{path}",
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


class HttpEbayMediaAdapter:
    def __init__(self, *, environment: str | None = None, timeout_seconds: int | None = None):
        self.environment = _configured_environment(environment)
        self.timeout_seconds = timeout_seconds or settings.EBAY_HTTP_TIMEOUT_SECONDS

    def upload_image(self, *, access_token: str, file) -> str:
        boundary = f"magpie-{uuid.uuid4().hex}"
        filename = getattr(file, "name", "image.jpg")
        data = file.read()
        body = b"".join(
            [
                f"--{boundary}\r\n".encode(),
                (
                    'Content-Disposition: form-data; name="image"; '
                    f'filename="{filename}"\r\n'
                ).encode(),
                b"Content-Type: image/jpeg\r\n\r\n",
                data,
                b"\r\n",
                f"--{boundary}--\r\n".encode(),
            ]
        )
        response = _request_json(
            f"{_media_base(self.environment)}/commerce/media/v1_beta/image/create_image_from_file",
            access_token=access_token,
            data=body,
            method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            timeout_seconds=self.timeout_seconds,
            service_name="eBay media endpoint",
        )
        image_url = response.get("imageUrl")
        if not image_url:
            raise EbayUnavailable("eBay media response could not be parsed.")
        return str(image_url)


class HttpEbayInventoryAdapter:
    def __init__(self, *, environment: str | None = None, timeout_seconds: int | None = None):
        self.environment = _configured_environment(environment)
        self.timeout_seconds = timeout_seconds or settings.EBAY_HTTP_TIMEOUT_SECONDS

    def upsert_inventory_item(self, *, access_token, sku, payload) -> None:
        _request_json(
            f"{_api_base(self.environment)}/sell/inventory/v1/inventory_item/{quote(str(sku), safe='')}",
            access_token=access_token,
            data=json.dumps(payload).encode("utf-8"),
            method="PUT",
            headers=_inventory_headers(),
            timeout_seconds=self.timeout_seconds,
            service_name="eBay inventory endpoint",
            allow_empty=True,
        )

    def create_offer(self, *, access_token, payload) -> str:
        response = _request_json(
            f"{_api_base(self.environment)}/sell/inventory/v1/offer",
            access_token=access_token,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers=_inventory_headers(),
            timeout_seconds=self.timeout_seconds,
            service_name="eBay inventory endpoint",
        )
        offer_id = response.get("offerId") or response.get("offer_id")
        if not offer_id:
            raise EbayUnavailable("eBay offer response could not be parsed.")
        return str(offer_id)

    def update_offer(self, *, access_token, offer_id, payload) -> None:
        _request_json(
            f"{_api_base(self.environment)}/sell/inventory/v1/offer/{quote(str(offer_id), safe='')}",
            access_token=access_token,
            data=json.dumps(payload).encode("utf-8"),
            method="PUT",
            headers=_inventory_headers(),
            timeout_seconds=self.timeout_seconds,
            service_name="eBay inventory endpoint",
            allow_empty=True,
        )

    def withdraw_offer(self, *, access_token, offer_id) -> None:
        _request_json(
            f"{_api_base(self.environment)}/sell/inventory/v1/offer/{quote(str(offer_id), safe='')}/withdraw",
            access_token=access_token,
            data=b"",
            method="POST",
            headers=_inventory_headers(),
            timeout_seconds=self.timeout_seconds,
            service_name="eBay inventory endpoint",
            allow_empty=True,
        )

    def publish_offer(self, *, access_token, offer_id) -> str:
        response = _request_json(
            f"{_api_base(self.environment)}/sell/inventory/v1/offer/{quote(str(offer_id), safe='')}/publish",
            access_token=access_token,
            data=b"",
            method="POST",
            headers=_inventory_headers(),
            timeout_seconds=self.timeout_seconds,
            service_name="eBay inventory endpoint",
        )
        listing_id = response.get("listingId") or response.get("listing_id")
        if not listing_id:
            raise EbayUnavailable("eBay publish response could not be parsed.")
        return str(listing_id)

    def get_offer(self, *, access_token, offer_id) -> dict:
        return _request_json(
            f"{_api_base(self.environment)}/sell/inventory/v1/offer/{quote(str(offer_id), safe='')}",
            access_token=access_token,
            method="GET",
            headers={"Accept": "application/json"},
            timeout_seconds=self.timeout_seconds,
            service_name="eBay inventory endpoint",
        )

    def create_inventory_location(self, *, access_token, merchant_location_key, payload) -> None:
        _request_json(
            f"{_api_base(self.environment)}/sell/inventory/v1/location/{quote(str(merchant_location_key), safe='')}",
            access_token=access_token,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers=_inventory_headers(),
            timeout_seconds=self.timeout_seconds,
            service_name="eBay inventory endpoint",
            allow_empty=True,
        )


class HttpEbayTaxonomyAdapter:
    def __init__(
        self,
        *,
        access_token: str,
        environment: str | None = None,
        timeout_seconds: int | None = None,
    ):
        self.environment = _configured_environment(environment)
        self.access_token = access_token
        self.timeout_seconds = timeout_seconds or settings.EBAY_HTTP_TIMEOUT_SECONDS

    def default_tree_id(self, *, marketplace: str) -> str:
        response = _request_json(
            f"{_api_base(self.environment)}/commerce/taxonomy/v1/get_default_category_tree_id?marketplace_id={quote(marketplace, safe='')}",
            access_token=self.access_token,
            method="GET",
            headers={"Accept": "application/json"},
            timeout_seconds=self.timeout_seconds,
            service_name="eBay taxonomy endpoint",
        )
        tree_id = response.get("categoryTreeId") or response.get("category_tree_id")
        if not tree_id:
            raise EbayUnavailable("eBay taxonomy tree response could not be parsed.")
        return str(tree_id)

    def suggest_categories(self, *, q: str) -> list[dict]:
        tree_id = self.default_tree_id(marketplace="EBAY_AU")
        response = _request_json(
            f"{_api_base(self.environment)}/commerce/taxonomy/v1/category_tree/{quote(tree_id, safe='')}/get_category_suggestions?q={quote(q)}",
            access_token=self.access_token,
            method="GET",
            headers={"Accept": "application/json"},
            timeout_seconds=self.timeout_seconds,
            service_name="eBay taxonomy endpoint",
        )
        suggestions = response.get("categorySuggestions") or response.get("category_suggestions") or []
        if not isinstance(suggestions, list):
            raise EbayUnavailable("eBay taxonomy suggestions response could not be parsed.")
        normalized = []
        for entry in suggestions:
            category = entry.get("category") if isinstance(entry, dict) else {}
            if not isinstance(category, dict):
                continue
            normalized.append(
                {
                    "category_id": str(category.get("categoryId") or ""),
                    "category_name": str(category.get("categoryName") or ""),
                    "category_tree_id": tree_id,
                    "source": "ebay",
                }
            )
        return normalized

    def item_aspects(self, *, category_id: str) -> list[dict]:
        tree_id = self.default_tree_id(marketplace="EBAY_AU")
        response = _request_json(
            f"{_api_base(self.environment)}/commerce/taxonomy/v1/category_tree/{quote(tree_id, safe='')}/get_item_aspects_for_category?category_id={quote(category_id, safe='')}",
            access_token=self.access_token,
            method="GET",
            headers={"Accept": "application/json"},
            timeout_seconds=self.timeout_seconds,
            service_name="eBay taxonomy endpoint",
        )
        aspects = response.get("aspects") or []
        if not isinstance(aspects, list):
            raise EbayUnavailable("eBay taxonomy aspects response could not be parsed.")
        return [_normalize_aspect(aspect) for aspect in aspects if isinstance(aspect, dict)]


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

    def client_credentials(self, *, scope: str = EBAY_APP_SCOPE) -> TokenSet:
        now = timezone.now()
        return TokenSet(
            access_token=f"fake-app-token-{scope.rsplit('/', 1)[-1]}",
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


class FakeEbayMediaAdapter:
    upload_count = 0

    def upload_image(self, *, access_token: str, file) -> str:
        if not access_token:
            raise EbayUnavailable("Missing eBay access token.")
        type(self).upload_count += 1
        return f"fake-eps://{type(self).upload_count}.jpg"


class FakeEbayInventoryAdapter:
    offers: dict[str, dict] = {}
    inventory_items: dict[str, dict] = {}
    locations: dict[str, dict] = {}
    publish_should_fail = False
    offer_counter = 0

    def upsert_inventory_item(self, *, access_token, sku, payload) -> None:
        if not access_token:
            raise EbayUnavailable("Missing eBay access token.")
        self.inventory_items[str(sku)] = payload

    def create_offer(self, *, access_token, payload) -> str:
        if not access_token:
            raise EbayUnavailable("Missing eBay access token.")
        type(self).offer_counter += 1
        offer_id = f"fake-offer-{type(self).offer_counter}"
        self.offers[offer_id] = {"offerId": offer_id, **payload, "status": "UNPUBLISHED"}
        return offer_id

    def update_offer(self, *, access_token, offer_id, payload) -> None:
        if offer_id not in self.offers:
            raise EbayUnavailable("Fake offer could not be found.")
        self.offers[offer_id].update(payload)
        self.offers[offer_id]["offerId"] = offer_id

    def withdraw_offer(self, *, access_token, offer_id) -> None:
        if offer_id not in self.offers:
            raise EbayUnavailable("Fake offer could not be found.")
        self.offers[offer_id]["status"] = "WITHDRAWN"

    def publish_offer(self, *, access_token, offer_id) -> str:
        if self.publish_should_fail:
            raise EbayUnavailable(
                json.dumps(
                    {
                        "errors": [
                            {
                                "errorId": 25002,
                                "message": "Fake publish failure.",
                                "longMessage": "Fake eBay publish validation failure.",
                            }
                        ]
                    }
                )
            )
        if offer_id not in self.offers:
            raise EbayUnavailable("Fake offer could not be found.")
        listing_id = f"fake-listing-{offer_id}"
        self.offers[offer_id]["status"] = "PUBLISHED"
        self.offers[offer_id]["listingId"] = listing_id
        return listing_id

    def get_offer(self, *, access_token, offer_id) -> dict:
        if offer_id not in self.offers:
            raise EbayUnavailable("Fake offer could not be found.")
        return dict(self.offers[offer_id])

    def create_inventory_location(self, *, access_token, merchant_location_key, payload) -> None:
        if not access_token:
            raise EbayUnavailable("Missing eBay access token.")
        self.locations[str(merchant_location_key)] = payload


class FakeEbayTaxonomyAdapter:
    def __init__(self, *, environment: str | None = None, access_token: str | None = None):
        self.environment = environment or effective_environment()
        self.access_token = access_token or "fake-app-token"

    def default_tree_id(self, *, marketplace: str) -> str:
        return "15" if marketplace == "EBAY_AU" else "0"

    def suggest_categories(self, *, q: str) -> list[dict]:
        if self.environment == EBAY_ENV_SANDBOX:
            raise EbayUnavailable("eBay taxonomy suggestions are unsupported in sandbox.")
        return [
            {
                "category_id": "260",
                "category_tree_id": "15",
                "category_name": f"Stamps > {q.title()}",
                "source": "fake",
            }
        ]

    def item_aspects(self, *, category_id: str) -> list[dict]:
        return [
            {
                "name": "Brand",
                "required": True,
                "type": "STRING",
                "values": [],
            },
            {
                "name": "Country/Region of Manufacture",
                "required": True,
                "type": "STRING",
                "values": ["Australia"],
            },
            {
                "name": "Year of Issue",
                "required": False,
                "type": "STRING",
                "values": [],
            },
        ]


def get_ebay_auth_adapter() -> EbayAuthAdapter:
    if not settings.EBAY_ENV:
        return FakeEbayAuthAdapter()
    return HttpEbayAuthAdapter()


def get_ebay_account_adapter() -> EbayAccountAdapter:
    if not settings.EBAY_ENV:
        return FakeEbayAccountAdapter()
    return HttpEbayAccountAdapter()


def get_ebay_media_adapter() -> EbayMediaAdapter:
    if not settings.EBAY_ENV:
        return FakeEbayMediaAdapter()
    return HttpEbayMediaAdapter()


def get_ebay_inventory_adapter() -> EbayInventoryAdapter:
    if not settings.EBAY_ENV:
        return FakeEbayInventoryAdapter()
    return HttpEbayInventoryAdapter()


def get_ebay_taxonomy_adapter(*, access_token: str | None = None) -> EbayTaxonomyAdapter:
    if not settings.EBAY_ENV:
        return FakeEbayTaxonomyAdapter(access_token=access_token)
    if not access_token:
        raise EbayUnavailable("eBay taxonomy app token is required.")
    return HttpEbayTaxonomyAdapter(access_token=access_token)


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


def _media_base(environment: str) -> str:
    if environment == EBAY_ENV_SANDBOX:
        return "https://apim.sandbox.ebay.com"
    if environment == EBAY_ENV_PRODUCTION:
        return "https://apim.ebay.com"
    raise EbayUnavailable("EBAY_ENV must be sandbox or production.")


def _identity_base(environment: str) -> str:
    if environment == EBAY_ENV_SANDBOX:
        return "https://apiz.sandbox.ebay.com"
    if environment == EBAY_ENV_PRODUCTION:
        return "https://apiz.ebay.com"
    raise EbayUnavailable("EBAY_ENV must be sandbox or production.")


def _inventory_headers() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Content-Language": "en-AU",
    }


def _request_json(
    url: str,
    *,
    access_token: str,
    method: str,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout_seconds: int,
    service_name: str,
    allow_empty: bool = False,
) -> dict:
    request_headers = {
        "Authorization": f"Bearer {access_token}",
        **(headers or {}),
    }
    request = Request(url, data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
            if not raw:
                return {} if allow_empty else {}
            return json.loads(raw.decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if detail:
            raise EbayUnavailable(f"{service_name} returned HTTP {exc.code}: {detail[:1000]}") from exc
        raise EbayUnavailable(f"{service_name} returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise EbayUnavailable(f"{service_name} request failed.") from exc


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


def _is_business_policies_program(program: dict) -> bool:
    program_type = str(program.get("programType", "")).strip().upper()
    return program_type in {"SELLING_POLICY_MANAGEMENT", "SELLER_POLICIES"}


def _normalize_aspect(aspect: dict) -> dict:
    constraint = aspect.get("aspectConstraint") or {}
    values = aspect.get("aspectValues") or []
    return {
        "name": str(aspect.get("localizedAspectName") or aspect.get("name") or ""),
        "required": str(constraint.get("aspectRequired", "")).lower() == "true"
        or constraint.get("aspectRequired") is True,
        "type": str(constraint.get("aspectDataType") or aspect.get("type") or "STRING"),
        "values": [
            str(value.get("localizedValue") or value.get("value") or "")
            for value in values
            if isinstance(value, dict)
        ],
    }
