EBAY_ENV_SANDBOX = "sandbox"
EBAY_ENV_PRODUCTION = "production"
EBAY_ENVIRONMENTS = {EBAY_ENV_SANDBOX, EBAY_ENV_PRODUCTION}
DEFAULT_FAKE_ENVIRONMENT = EBAY_ENV_SANDBOX

_SCOPE_HOST = "api." + "ebay.com"
_SCOPE_BASE = f"https://{_SCOPE_HOST}/oauth/api_scope"
EBAY_SCOPES = [
    f"{_SCOPE_BASE}/sell.inventory",
    f"{_SCOPE_BASE}/sell.account.readonly",
    f"{_SCOPE_BASE}/sell.fulfillment.readonly",
    f"{_SCOPE_BASE}/sell.finances",
]
EBAY_APP_SCOPE = _SCOPE_BASE
EBAY_MARKETPLACE_ID = "EBAY_AU"

OAUTH_STATE_TTL_MINUTES = 10

AUDIT_CONNECT_STARTED = "ebay.connect.started"
AUDIT_CONNECT_COMPLETED = "ebay.connect.completed"
AUDIT_CONNECT_FAILED = "ebay.connect.failed"
AUDIT_DISCONNECT_COMPLETED = "ebay.disconnect.completed"
AUDIT_TOKEN_REFRESH_COMPLETED = "ebay.token.refresh.completed"
AUDIT_TOKEN_REFRESH_FAILED = "ebay.token.refresh.failed"
AUDIT_POLICY_REFRESH_COMPLETED = "ebay.policy_refresh.completed"
AUDIT_POLICY_REFRESH_FAILED = "ebay.policy_refresh.failed"
AUDIT_MEDIA_UPLOADED = "ebay.media.uploaded"
AUDIT_INVENTORY_ITEM_UPSERTED = "ebay.inventory_item.upserted"
AUDIT_OFFER_CREATED = "ebay.offer.created"
AUDIT_OFFER_UPDATED = "ebay.offer.updated"
AUDIT_OFFER_WITHDRAWN = "ebay.offer.withdrawn"
AUDIT_PUBLISH_ATTEMPTED = "ebay.publish.attempted"
AUDIT_PUBLISH_SUCCEEDED = "ebay.publish.succeeded"
AUDIT_PUBLISH_FAILED = "ebay.publish.failed"
AUDIT_TAXONOMY_CATEGORY_SUGGESTED = "ebay.taxonomy.category_suggested"
AUDIT_TAXONOMY_ASPECTS_FETCHED = "ebay.taxonomy.aspects_fetched"
AUDIT_TAXONOMY_ASPECTS_OVERRIDE = "ebay.taxonomy.aspects_override"
AUDIT_LOCATION_CREATED = "ebay.location.created"
AUDIT_LOCATION_REFRESH_FAILED = "ebay.location.refresh_failed"
AUDIT_ORDER_SYNC_STARTED = "ebay.order.sync.started"
AUDIT_ORDER_SYNC_COMPLETED = "ebay.order.sync.completed"
AUDIT_ORDER_SYNC_FAILED = "ebay.order.sync.failed"
AUDIT_ORDER_STAGING_RESOLVED = "ebay.order_staging.resolved"
AUDIT_ORDER_DUPLICATE_FLAGGED = "ebay.order.duplicate_flagged"

CONDITION_MAP = {
    "new": {"condition_id": "1000", "condition": "NEW"},
    "like_new": {"condition_id": "2750", "condition": "LIKE_NEW"},
    "very_good": {"condition_id": "4000", "condition": "USED_VERY_GOOD"},
    "good": {"condition_id": "5000", "condition": "USED_GOOD"},
    "acceptable": {"condition_id": "6000", "condition": "USED_ACCEPTABLE"},
    "for_parts": {"condition_id": "7000", "condition": "FOR_PARTS_OR_NOT_WORKING"},
    "ungraded": {"condition_id": "3000", "condition": "USED_EXCELLENT"},
}

CHANNEL_DATA_KEYS = {
    "category_id",
    "category_tree_id",
    "category_name",
    "condition_id",
    "merchant_location_key",
    "payment_policy_id",
    "fulfillment_policy_id",
    "return_policy_id",
    "eps_image_urls",
    "inventory_item_sku",
    "offer_id",
    "listing_id",
    "staged_at",
    "published_at",
    "last_ebay_error",
    "last_payload_snapshot",
    "last_offer_snapshot",
}
