from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
    EBAY_MARKETPLACE_ID,
    EBAY_SCOPES,
)
from apps.ebay.diagnostics import diagnostic, operation_for, public_diagnostic


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    access_expires_at: datetime
    refresh_token: str | None
    refresh_expires_at: datetime | None


class EbayUnavailable(Exception):
    """Raised when eBay auth/account data cannot be fetched safely."""

    def __init__(self, message="eBay response unavailable.", *, diagnostic=None):
        self.diagnostic = diagnostic
        if diagnostic:
            message = " ".join(i["message"] for i in public_diagnostic(diagnostic)["issues"])
        super().__init__(message)


class EbayHttpError(EbayUnavailable):
    def __init__(self, message: str, *, http_status: int, error_ids: tuple[int, ...], diagnostic=None):
        super().__init__(message, diagnostic=diagnostic)
        self.http_status = http_status
        self.error_ids = error_ids


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
    def get_inventory_item(self, *, access_token, sku) -> dict:
        ...

    def get_location(self, *, access_token, merchant_location_key) -> dict:
        ...

    def get_listing_fees(self, *, access_token, offer_id) -> dict:
        ...

    def delete_offer(self, *, access_token, offer_id) -> None:
        ...

    def upsert_inventory_item(self, *, access_token, sku, payload) -> None:
        ...

    def create_offer(self, *, access_token, payload) -> str:
        ...

    def update_offer(self, *, access_token, offer_id, payload) -> None:
        ...

    def get_offers(self, *, access_token, sku, marketplace_id, format) -> list[dict]:
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

    def category_details(self, *, category_id: str) -> dict:
        ...

    def category_children(self, *, category_id: str) -> dict:
        ...

    def item_aspects(self, *, category_id: str) -> list[dict]:
        ...

    def item_condition_policy(self, *, category_id: str) -> dict:
        ...

    def listing_type_policy(self, *, category_id: str) -> dict:
        ...


class EbayOrderAdapter(Protocol):
    def list_orders(self, *, access_token: str, start, end) -> list[dict]:
        ...


class EbayFinancesAdapter(Protocol):
    def list_transactions(self, *, access_token: str, start, end) -> list[dict]:
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
        operation = {"refresh_token": "oauth.refresh", "authorization_code": "oauth.exchange", "client_credentials": "oauth.application"}[payload["grant_type"]]
        data = _perform_request(request, operation=operation, timeout_seconds=self.timeout_seconds)
        try:
            return _token_set_from_payload(data)
        except (KeyError, TypeError, ValueError):
            raise _malformed(operation) from None


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
            raise _malformed(f"account.{kind}")
        return policies

    def _get(self, path: str, *, access_token: str, base_url: str | None = None) -> dict:
        return _request_json(f"{base_url or _api_base(self.environment)}{path}", access_token=access_token,
            method="GET", timeout_seconds=self.timeout_seconds, service_name="eBay account endpoint")


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
            raise _malformed("media.upload")
        return str(image_url)


class HttpEbayInventoryAdapter:
    def __init__(self, *, environment: str | None = None, timeout_seconds: int | None = None):
        self.environment = _configured_environment(environment)
        self.timeout_seconds = timeout_seconds or settings.EBAY_HTTP_TIMEOUT_SECONDS

    def get_inventory_item(self, *, access_token, sku) -> dict:
        return _request_json(f"{_api_base(self.environment)}/sell/inventory/v1/inventory_item/{quote(str(sku), safe='')}", access_token=access_token, method="GET", timeout_seconds=self.timeout_seconds, service_name="eBay inventory read")

    def get_location(self, *, access_token, merchant_location_key) -> dict:
        return _request_json(f"{_api_base(self.environment)}/sell/inventory/v1/location/{quote(str(merchant_location_key), safe='')}", access_token=access_token, method="GET", timeout_seconds=self.timeout_seconds, service_name="eBay location read")

    def get_listing_fees(self, *, access_token, offer_id) -> dict:
        # eBay's fee lookup is a read operation with a POST-shaped request.
        return _request_json(f"{_api_base(self.environment)}/sell/inventory/v1/offer/get_listing_fees", access_token=access_token, method="POST", data=json.dumps({"offers": [{"offerId": str(offer_id)}]}).encode(), headers=_inventory_headers(), timeout_seconds=self.timeout_seconds, service_name="eBay fee lookup")

    def delete_offer(self, *, access_token, offer_id) -> None:
        _request_json(f"{_api_base(self.environment)}/sell/inventory/v1/offer/{quote(str(offer_id), safe='')}", access_token=access_token, method="DELETE", headers=_inventory_headers(), timeout_seconds=self.timeout_seconds, service_name="eBay unpublished offer removal", allow_empty=True)

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
            raise _malformed("inventory.create")
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

    def get_offers(self, *, access_token, sku, marketplace_id, format) -> list[dict]:
        query = urlencode(
            {
                "sku": str(sku),
                "marketplace_id": str(marketplace_id),
                "format": str(format),
            },
            quote_via=quote,
        )
        try:
            response = _request_json(
                f"{_api_base(self.environment)}/sell/inventory/v1/offer?{query}",
                access_token=access_token,
                method="GET",
                headers={"Accept": "application/json"},
                timeout_seconds=self.timeout_seconds,
                service_name="eBay inventory endpoint",
            )
        except EbayHttpError as exc:
            if exc.http_status == 404 and exc.error_ids == (25713,):
                return []
            raise
        offers = response.get("offers") or []
        if not isinstance(offers, list):
            raise _malformed("inventory.offers")
        return [offer for offer in offers if isinstance(offer, dict)]

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
            timeout_seconds=min(self.timeout_seconds, 60),
            service_name="eBay inventory endpoint",
        )
        listing_id = response.get("listingId") or response.get("listing_id")
        if not listing_id:
            raise _malformed("inventory.publish")
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
            raise _malformed("taxonomy.tree")
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
            raise _malformed("taxonomy.suggestions")
        normalized = []
        for entry in suggestions:
            if not isinstance(entry, dict):
                continue
            suggestion = _normalize_category_suggestion(entry, tree_id=tree_id)
            if not suggestion["category_id"]:
                continue
            if suggestion["is_leaf"] is None:
                try:
                    details = self._category_details(
                        category_id=suggestion["category_id"],
                        tree_id=tree_id,
                    )
                except EbayUnavailable as exc:
                    suggestion["validation_error"] = str(exc)
                else:
                    suggestion["is_leaf"] = details["is_leaf"]
                    suggestion["child_count"] = details["child_count"]
                    if not suggestion["category_name"]:
                        suggestion["category_name"] = details["category_name"]
                        suggestion["name"] = details["category_name"]
                    if len(suggestion["category_path"]) <= 1 and details["category_path"]:
                        suggestion["category_path"] = details["category_path"]
            normalized.append(suggestion)
        return normalized

    def category_details(self, *, category_id: str) -> dict:
        tree_id = self.default_tree_id(marketplace="EBAY_AU")
        return self._category_details(category_id=category_id, tree_id=tree_id)

    def category_children(self, *, category_id: str) -> dict:
        if not category_id.isdecimal() or int(category_id) <= 0:
            raise EbayUnavailable("Choose a non-root category branch.")
        tree_id = self.default_tree_id(marketplace="EBAY_AU")
        response = _request_json(
            f"{_api_base(self.environment)}/commerce/taxonomy/v1/category_tree/{quote(tree_id, safe='')}/get_category_subtree?category_id={quote(category_id, safe='')}",
            access_token=self.access_token, method="GET", headers={"Accept": "application/json"},
            timeout_seconds=self.timeout_seconds, service_name="eBay taxonomy branch endpoint",
        )
        node = response.get("categorySubtreeNode")
        if not isinstance(node, dict) or str((node.get("category") or {}).get("categoryId")) != category_id:
            raise EbayUnavailable("eBay did not return the requested category branch.")
        # eBay returns descendants too: discard those, never recurse or mirror.
        children = []
        for child in node.get("childCategoryTreeNodes") or []:
            if isinstance(child, dict):
                row = _normalize_category_node(child, tree_id=tree_id)
                row["is_leaf"] = _leaf_value(child)
                children.append(row)
        parent = _normalize_category_node(node, tree_id=tree_id)
        parent["is_leaf"] = _leaf_value(node)
        return {"marketplace": "EBAY_AU", "category_tree_id": tree_id,
                "category": parent,
                "children": children}

    def _category_details(self, *, category_id: str, tree_id: str) -> dict:
        response = _request_json(
            f"{_api_base(self.environment)}/commerce/taxonomy/v1/category_tree/{quote(tree_id, safe='')}/get_category_subtree?category_id={quote(category_id, safe='')}",
            access_token=self.access_token,
            method="GET",
            headers={"Accept": "application/json"},
            timeout_seconds=self.timeout_seconds,
            service_name="eBay taxonomy endpoint",
        )
        node = response.get("categorySubtreeNode") or response.get("category_subtree_node")
        if not isinstance(node, dict):
            raise EbayUnavailable("eBay taxonomy category response could not be parsed.")
        details = _normalize_category_node(node, tree_id=tree_id)
        if not details["category_id"]:
            raise EbayUnavailable("eBay taxonomy category response could not be parsed.")
        return details

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
            raise _malformed("taxonomy.aspects")
        return [_normalize_aspect(aspect) for aspect in aspects if isinstance(aspect, dict)]

    def item_condition_policy(self, *, category_id: str) -> dict:
        response = _request_json(
            f"{_api_base(self.environment)}/sell/metadata/v1/marketplace/EBAY_AU/get_item_condition_policies"
            f"?filter={quote('categoryIds:{' + str(category_id) + '}', safe='')}",
            access_token=self.access_token,
            method="GET",
            headers={"Accept": "application/json"},
            timeout_seconds=self.timeout_seconds,
            service_name="eBay condition metadata endpoint",
        )
        policies = response.get("itemConditionPolicies")
        if not isinstance(policies, list):
            raise EbayUnavailable("eBay condition policy response could not be parsed.")
        matches = [
            row
            for row in policies
            if isinstance(row, dict) and str(row.get("categoryId")) == str(category_id)
        ]
        if len(matches) != 1:
            raise EbayUnavailable("eBay did not return a unique condition policy for this category.")
        policy = matches[0]
        required = policy.get("itemConditionRequired")
        conditions = policy.get("itemConditions", [] if required is False else None)
        if not isinstance(required, bool) or not isinstance(conditions, list):
            raise EbayUnavailable("eBay condition policy response could not be parsed.")
        return {"category_id": str(category_id), "required": required, "conditions": conditions}


    def listing_type_policy(self, *, category_id: str) -> dict:
        response = _request_json(
            f"{_api_base(self.environment)}/sell/metadata/v1/marketplace/EBAY_AU/get_listing_type_policies"
            f"?filter={quote('categoryIds:{' + str(category_id) + '}', safe='')}",
            access_token=self.access_token, method="GET",
            headers={"Accept": "application/json"}, timeout_seconds=self.timeout_seconds,
            service_name="eBay listing-duration metadata endpoint",
        )
        rows = response.get("listingTypePolicies")
        matches = [row for row in rows if isinstance(row, dict) and str(row.get("categoryId")) == str(category_id)] if isinstance(rows, list) else []
        if len(matches) != 1 or not isinstance(matches[0].get("listingDurations"), list):
            raise EbayUnavailable("eBay did not return a unique listing-duration policy for this category.")
        return {"category_id": str(category_id), "formats": {
            row["listingType"]: row["durationValues"] for row in matches[0]["listingDurations"]
            if isinstance(row, dict) and row.get("listingType") in {"AUCTION", "FIXED_PRICE_ITEM"}
            and isinstance(row.get("durationValues"), list)
        }}


class HttpEbayOrderAdapter:
    def __init__(self, *, environment: str | None = None, timeout_seconds: int | None = None):
        self.environment = _configured_environment(environment)
        self.timeout_seconds = timeout_seconds or settings.EBAY_HTTP_TIMEOUT_SECONDS

    def list_orders(self, *, access_token: str, start, end) -> list[dict]:
        orders: list[dict] = []
        offset = 0
        limit = 100
        while True:
            query = urlencode(
                {
                    "filter": (
                        f"creationdate:[{_ebay_datetime(start)}..{_ebay_datetime(end)}]"
                    ),
                    "limit": str(limit),
                    "offset": str(offset),
                },
                quote_via=quote,
            )
            response = _request_json(
                f"{_api_base(self.environment)}/sell/fulfillment/v1/order?{query}",
                access_token=access_token,
                method="GET",
                headers={"Accept": "application/json"},
                timeout_seconds=self.timeout_seconds,
                service_name="eBay fulfillment order endpoint",
            )
            batch = response.get("orders") or []
            if not isinstance(batch, list):
                raise _malformed("fulfillment.orders")
            orders.extend([order for order in batch if isinstance(order, dict)])
            total = int(response.get("total") or len(orders))
            if len(orders) >= total or not batch:
                return orders
            offset += limit


class HttpEbayFinancesAdapter:
    def __init__(self, *, environment: str | None = None, timeout_seconds: int | None = None):
        self.environment = _configured_environment(environment)
        self.timeout_seconds = timeout_seconds or settings.EBAY_HTTP_TIMEOUT_SECONDS

    def list_transactions(self, *, access_token: str, start, end) -> list[dict]:
        transactions: list[dict] = []
        offset = 0
        limit = 100
        while True:
            query = urlencode(
                {
                    "filter": (
                        f"transactionDate:[{_ebay_datetime(start)}..{_ebay_datetime(end)}]"
                    ),
                    "limit": str(limit),
                    "offset": str(offset),
                },
                quote_via=quote,
            )
            response = _request_json(
                f"{_finances_base(self.environment)}/sell/finances/v1/transaction?{query}",
                access_token=access_token,
                method="GET",
                headers={
                    "Accept": "application/json",
                    "X-EBAY-C-MARKETPLACE-ID": EBAY_MARKETPLACE_ID,
                },
                timeout_seconds=self.timeout_seconds,
                service_name="eBay finances transaction endpoint",
            )
            batch = response.get("transactions") or []
            if not isinstance(batch, list):
                raise _malformed("finances.transactions")
            transactions.extend([row for row in batch if isinstance(row, dict)])
            total = int(response.get("total") or len(transactions))
            if len(transactions) >= total or not batch:
                return transactions
            offset += limit


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
    create_count = 0
    update_count = 0
    withdraw_count = 0
    publish_count = 0

    def get_inventory_item(self, *, access_token, sku) -> dict:
        if str(sku) not in self.inventory_items:
            raise EbayHttpError("Fake inventory not found", http_status=404, error_ids=())
        return {"sku": str(sku), **self.inventory_items[str(sku)]}

    def get_location(self, *, access_token, merchant_location_key) -> dict:
        if str(merchant_location_key) not in self.locations:
            raise EbayHttpError("Fake location not found", http_status=404, error_ids=())
        return {"merchantLocationKey": str(merchant_location_key), **self.locations[str(merchant_location_key)]}

    def get_listing_fees(self, *, access_token, offer_id) -> dict:
        return {"feeSummaries": [{"marketplaceId": "EBAY_AU", "fees": [{"feeType": "InsertionFee", "amount": {"currency": "AUD", "value": "0.06"}}]}]}

    def delete_offer(self, *, access_token, offer_id) -> None:
        if offer_id not in self.offers:
            raise EbayHttpError("Fake offer not found", http_status=404, error_ids=())
        if self.offers[offer_id].get("status") == "PUBLISHED":
            raise EbayHttpError("Published fake offer protected", http_status=409, error_ids=())
        type(self).withdraw_count += 1
        del self.offers[offer_id]

    def upsert_inventory_item(self, *, access_token, sku, payload) -> None:
        if not access_token:
            raise EbayUnavailable("Missing eBay access token.")
        self.inventory_items[str(sku)] = payload

    def create_offer(self, *, access_token, payload) -> str:
        if not access_token:
            raise EbayUnavailable("Missing eBay access token.")
        for offer_id, offer in self.offers.items():
            if (
                str(offer.get("sku")) == str(payload.get("sku"))
                and str(offer.get("marketplaceId")) == str(payload.get("marketplaceId"))
                and str(offer.get("format")) == str(payload.get("format"))
            ):
                raise EbayUnavailable(
                    json.dumps(
                        {
                            "errors": [
                                {
                                    "errorId": 25002,
                                    "message": "A user error has occurred. Offer entity already exists.",
                                    "parameters": [{"name": "offerId", "value": offer_id}],
                                }
                            ]
                        }
                    )
                )
        type(self).create_count += 1
        type(self).offer_counter += 1
        offer_id = f"fake-offer-{type(self).offer_counter}"
        self.offers[offer_id] = {"offerId": offer_id, **payload, "status": "UNPUBLISHED"}
        return offer_id

    def update_offer(self, *, access_token, offer_id, payload) -> None:
        if offer_id not in self.offers:
            raise EbayUnavailable("Fake offer could not be found.")
        type(self).update_count += 1
        self.offers[offer_id].update(payload)
        self.offers[offer_id]["offerId"] = offer_id
        self.offers[offer_id]["status"] = "UNPUBLISHED"

    def get_offers(self, *, access_token, sku, marketplace_id, format) -> list[dict]:
        if not access_token:
            raise EbayUnavailable("Missing eBay access token.")
        return [
            dict(offer)
            for offer in self.offers.values()
            if str(offer.get("sku")) == str(sku)
            and str(offer.get("marketplaceId")) == str(marketplace_id)
            and str(offer.get("format")) == str(format)
        ]

    def withdraw_offer(self, *, access_token, offer_id) -> None:
        if offer_id not in self.offers:
            raise EbayUnavailable("Fake offer could not be found.")
        type(self).withdraw_count += 1
        self.offers[offer_id]["status"] = "UNPUBLISHED"
        self.offers[offer_id].pop("listing", None)

    def publish_offer(self, *, access_token, offer_id) -> str:
        type(self).publish_count += 1
        if self.publish_should_fail:
            raise EbayHttpError(
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
                ), http_status=400, error_ids=(25002,)
            )
        if offer_id not in self.offers:
            raise EbayUnavailable("Fake offer could not be found.")
        listing_id = f"fake-listing-{offer_id}"
        self.offers[offer_id]["status"] = "PUBLISHED"
        self.offers[offer_id]["listingId"] = listing_id
        return listing_id

    def get_offer(self, *, access_token, offer_id) -> dict:
        if offer_id not in self.offers:
            raise EbayHttpError("Fake offer could not be found.", http_status=404, error_ids=())
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
                "category_name": "Stamps",
                "name": "Stamps",
                "category_path": ["Stamps"],
                "is_leaf": False,
                "child_count": 3,
                "source": "fake",
            },
            {
                "category_id": "105848",
                "category_tree_id": "15",
                "category_name": "Australian Stamps",
                "name": "Australian Stamps",
                "category_path": ["Stamps", "Australia", "Australian Stamps"],
                "is_leaf": True,
                "child_count": 0,
                "source": "fake",
            }
        ]

    def category_details(self, *, category_id: str) -> dict:
        if str(category_id) == "260":
            return {
                "category_id": "260",
                "category_tree_id": "15",
                "category_name": "Stamps",
                "name": "Stamps",
                "category_path": ["Stamps"],
                "is_leaf": False,
                "child_count": 3,
                "source": "fake",
            }
        return {
            "category_id": str(category_id),
            "category_tree_id": "15",
            "category_name": "Australian Stamps",
            "name": "Australian Stamps",
            "category_path": ["Stamps", "Australia", "Australian Stamps"],
            "is_leaf": True,
            "child_count": 0,
            "source": "fake",
        }

    def item_aspects(self, *, category_id: str) -> list[dict]:
        if str(category_id) == "260":
            raise EbayUnavailable("The specified category ID must be a leaf category.")
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

    def item_condition_policy(self, *, category_id: str) -> dict:
        return {
            "category_id": str(category_id),
            "required": True,
            "conditions": [{"conditionId": "3000", "conditionDescription": "Used"}],
        }

    def category_children(self, *, category_id: str) -> dict:
        parent = {"category_id": category_id, "category_name": "Stamps", "category_tree_id": "15", "is_leaf": False}
        child = {"category_id": "105848", "category_name": "Australian Stamps", "category_tree_id": "15", "is_leaf": True}
        return {"marketplace": "EBAY_AU", "category_tree_id": "15", "category": parent, "children": [child]}


    def listing_type_policy(self, *, category_id: str) -> dict:
        return {"category_id": str(category_id), "formats": {
            "FIXED_PRICE_ITEM": ["GTC"], "AUCTION": ["DAYS_3", "DAYS_5", "DAYS_7", "DAYS_10"],
        }}


class FakeEbayOrderAdapter:
    orders: list[dict] = []
    call_count = 0
    last_start = None
    last_end = None

    def list_orders(self, *, access_token: str, start, end) -> list[dict]:
        if not access_token:
            raise EbayUnavailable("Missing eBay access token.")
        type(self).call_count += 1
        type(self).last_start = start
        type(self).last_end = end
        return [dict(order) for order in type(self).orders]


class FakeEbayFinancesAdapter:
    transactions: list[dict] = []
    call_count = 0
    last_start = None
    last_end = None

    def list_transactions(self, *, access_token: str, start, end) -> list[dict]:
        if not access_token:
            raise EbayUnavailable("Missing eBay access token.")
        type(self).call_count += 1
        type(self).last_start = start
        type(self).last_end = end
        return [dict(transaction) for transaction in type(self).transactions]


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


def get_ebay_order_adapter() -> EbayOrderAdapter:
    if not settings.EBAY_ENV:
        return FakeEbayOrderAdapter()
    return HttpEbayOrderAdapter()


def get_ebay_finances_adapter() -> EbayFinancesAdapter:
    if not settings.EBAY_ENV:
        return FakeEbayFinancesAdapter()
    return HttpEbayFinancesAdapter()


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
        raise EbayUnavailable(diagnostic=diagnostic("oauth.application", failure="configuration"))


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


def _finances_base(environment: str) -> str:
    if environment == EBAY_ENV_SANDBOX:
        return "https://apiz.sandbox.ebay.com"
    if environment == EBAY_ENV_PRODUCTION:
        return "https://apiz.ebay.com"
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
    from apps.ebay.diagnostics import OPERATIONS
    from apps.ebay import services
    operation = operation_for(url, method)
    for attempt in range(2):
        request = Request(url, data=data, headers={"Authorization": f"Bearer {access_token}", **(headers or {})}, method=method)
        try:
            return _perform_request(request, operation=operation, timeout_seconds=timeout_seconds, allow_empty=allow_empty)
        except EbayHttpError as exc:
            rejected_access = exc.http_status == 401 and any(i["kind"] == "access_expired" for i in exc.diagnostic["issues"])
            # A read may renew once. Never replay a write or override Phase 5's recovery rules.
            if attempt or method != "GET" or not rejected_access: raise
            access_token = services.get_app_access_token(force_refresh=True) if OPERATIONS[operation][1] == "application" else services.get_access_token(force_refresh=True)
    raise AssertionError("Unreachable renewal path")


def _perform_request(request, *, operation, timeout_seconds, allow_empty=False):
    from apps.ebay.connection_health import observe_begin, observe_finish
    ticket = observe_begin(operation)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
            status = getattr(response, "status", 200)
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        if not isinstance(payload, dict) or (not raw and not allow_empty):
            raise ValueError("malformed")
        if any(key in payload and not isinstance(payload[key], list) for key in ("errors", "warnings")):
            raise ValueError("malformed diagnostics")
        if payload.get("errors"):
            value = diagnostic(operation, status=status, payload=payload)
            observe_finish(ticket, failure=value)
            error = EbayHttpError("eBay structured rejection.", http_status=status,
                error_ids=tuple(i["error_id"] for i in value["issues"] if i["error_id"] is not None), diagnostic=value)
        else:
            warning = diagnostic(operation, status=status, payload={"warnings": payload["warnings"]}) if payload.get("warnings") else None
            count = next((len(payload[key]) for key in ("inventoryItems", "paymentPolicies", "fulfillmentPolicies", "returnPolicies", "orders", "transactions", "locations") if isinstance(payload.get(key), list)), None)
            observe_finish(ticket, status=status, warnings=warning, count=count)
            return payload
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8", errors="replace"))
        except (ValueError, UnicodeError): payload = {}
        value = diagnostic(operation, status=exc.code, payload=payload)
        # The existing no-offers sentinel is not a broken connection.
        no_offers = operation == "inventory.offers" and exc.code == 404 and [i["error_id"] for i in value["issues"]] == [25713]
        if not no_offers: observe_finish(ticket, failure=value)
        error = EbayHttpError("eBay rejected the operation.", http_status=exc.code,
            error_ids=tuple(i["error_id"] for i in value["issues"] if i["error_id"] is not None), diagnostic=value)
    except (URLError, TimeoutError, OSError):
        value = diagnostic(operation, failure="network")
        observe_finish(ticket, failure=value)
        error = EbayUnavailable(diagnostic=value)
    except (ValueError, TypeError, UnicodeError):
        value = diagnostic(operation, failure="malformed")
        observe_finish(ticket, failure=value)
        error = EbayUnavailable(diagnostic=value)
    # Raise outside the handler: even a suppressed __context__ would retain HTTPError headers/body.
    request = response = payload = raw = None
    raise error from None


def _malformed(operation):
    from apps.ebay.connection_health import observe_begin, observe_finish
    value = diagnostic(operation, failure="malformed")
    observe_finish(observe_begin(operation), failure=value)
    return EbayUnavailable(diagnostic=value)


def read_connection_probe(api, *, access_token):
    if not settings.EBAY_ENV:
        return 0  # deterministic offline probe; never opens a network connection
    env = effective_environment()
    base = _api_base(env)
    paths = {"Inventory": "/sell/inventory/v1/inventory_item?limit=1",
        "Account": "/sell/account/v1/payment_policy?marketplace_id=EBAY_AU",
        "Fulfilment": "/sell/fulfillment/v1/order?limit=1",
        "Finances": "/sell/finances/v1/transaction?limit=1",
        "Taxonomy": "/commerce/taxonomy/v1/get_default_category_tree_id?marketplace_id=EBAY_AU"}
    base = _finances_base(env) if api == "Finances" else base
    result = _request_json(base + paths[api], access_token=access_token, method="GET",
        headers={"Accept": "application/json", **({"X-EBAY-C-MARKETPLACE-ID": EBAY_MARKETPLACE_ID} if api == "Finances" else {})},
        timeout_seconds=min(settings.EBAY_HTTP_TIMEOUT_SECONDS, 15), service_name="eBay connection check")
    keys = {"Inventory": "inventoryItems", "Account": "paymentPolicies", "Fulfilment": "orders", "Finances": "transactions"}
    if api == "Taxonomy":
        if not result.get("categoryTreeId"): raise EbayUnavailable(diagnostic=diagnostic("taxonomy.tree", failure="malformed"))
        return 1
    rows = result.get(keys[api], [])
    if not isinstance(rows, list): raise EbayUnavailable(diagnostic=diagnostic(operation_for(base + paths[api], "GET"), failure="malformed"))
    return len(rows)


def _ebay_datetime(value) -> str:
    if timezone.is_naive(value):
        value = timezone.make_aware(value, UTC)
    value = value.astimezone(UTC).replace(microsecond=0)
    return value.strftime("%Y-%m-%dT%H:%M:%S.000Z")


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
        "mode": str(constraint.get("aspectMode") or "FREE_TEXT"),
        "values": [
            str(value.get("localizedValue") or value.get("value") or "")
            for value in values
            if isinstance(value, dict)
        ],
    }


def _normalize_category_suggestion(entry: dict, *, tree_id: str) -> dict:
    category = entry.get("category") if isinstance(entry.get("category"), dict) else {}
    category_id = str(category.get("categoryId") or category.get("category_id") or "")
    category_name = str(category.get("categoryName") or category.get("category_name") or "")
    category_path = _category_path_from_suggestion(entry, category_name)
    is_leaf = _leaf_value(entry)
    return {
        "category_id": category_id,
        "category_tree_id": tree_id,
        "category_name": category_name,
        "name": category_name,
        "category_path": category_path,
        "ancestors": [{"category_id": str(row.get("categoryId") or ""), "category_name": str(row.get("categoryName") or "")} for row in sorted(entry.get("categoryTreeNodeAncestors") or [], key=_category_node_level) if isinstance(row, dict) and row.get("categoryId") and row.get("categoryName")],
        "is_leaf": is_leaf,
        "child_count": None,
        "source": "ebay",
    }


def _normalize_category_node(node: dict, *, tree_id: str) -> dict:
    category = node.get("category") if isinstance(node.get("category"), dict) else {}
    children = node.get("childCategoryTreeNodes") or node.get("child_category_tree_nodes") or []
    if not isinstance(children, list):
        children = []
    category_id = str(category.get("categoryId") or category.get("category_id") or "")
    category_name = str(category.get("categoryName") or category.get("category_name") or "")
    is_leaf = _leaf_value(node)
    if is_leaf is None:
        is_leaf = False if children else True
    return {
        "category_id": category_id,
        "category_tree_id": tree_id,
        "category_name": category_name,
        "name": category_name,
        "category_path": [category_name] if category_name else [],
        "is_leaf": is_leaf,
        "child_count": len(children),
        "source": "ebay",
    }


def _category_path_from_suggestion(entry: dict, category_name: str) -> list[str]:
    ancestors = entry.get("categoryTreeNodeAncestors") or entry.get("category_tree_node_ancestors") or []
    names: list[str] = []
    if isinstance(ancestors, list):
        sorted_ancestors = sorted(ancestors, key=_category_node_level)
        for ancestor in sorted_ancestors:
            if not isinstance(ancestor, dict):
                continue
            category = ancestor.get("category") if isinstance(ancestor.get("category"), dict) else {}
            name = str(category.get("categoryName") or category.get("category_name") or "").strip()
            if name and name not in names:
                names.append(name)
    if category_name and category_name not in names:
        names.append(category_name)
    return names


def _category_node_level(node: dict) -> int:
    try:
        return int(node.get("categoryTreeNodeLevel") or node.get("category_tree_node_level") or 0)
    except (TypeError, ValueError):
        return 0


def _leaf_value(entry: dict) -> bool | None:
    raw = entry.get("leafCategoryTreeNode")
    if raw is None and isinstance(entry.get("categoryTreeNode"), dict):
        raw = entry["categoryTreeNode"].get("leafCategoryTreeNode")
    if raw is None:
        raw = entry.get("leaf_category_tree_node")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    return None
