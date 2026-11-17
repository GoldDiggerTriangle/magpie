"""Provider payloads stop here. Only bounded, allowlisted facts may leave this module."""
from datetime import datetime
import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.utils import timezone


OPERATIONS = {
    "oauth.refresh": ("OAuth renewal", "seller"),
    "oauth.exchange": ("Seller connection", "seller"),
    "oauth.application": ("Application authorisation", "application"),
    "inventory.items": ("Inventory", "seller"),
    "inventory.item": ("Inventory", "seller"),
    "inventory.replace": ("Inventory", "seller"),
    "inventory.locations": ("Inventory", "seller"),
    "inventory.location": ("Inventory", "seller"),
    "inventory.location_create": ("Inventory", "seller"),
    "inventory.offers": ("Inventory", "seller"),
    "inventory.offer": ("Inventory", "seller"),
    "inventory.create": ("Inventory", "seller"),
    "inventory.update": ("Inventory", "seller"),
    "inventory.publish": ("Inventory", "seller"),
    "inventory.remove": ("Inventory", "seller"),
    "inventory.withdraw": ("Inventory", "seller"),
    "inventory.fees": ("Inventory", "seller"),
    "account.payment": ("Account", "seller"),
    "account.fulfillment": ("Account", "seller"),
    "account.return": ("Account", "seller"),
    "account.programs": ("Account", "seller"),
    "account.identity": ("Account", "seller"),
    "fulfillment.orders": ("Fulfilment", "seller"),
    "finances.transactions": ("Finances", "seller"),
    "media.upload": ("Media/EPS", "seller"),
    "taxonomy.tree": ("Taxonomy", "application"),
    "taxonomy.suggestions": ("Taxonomy", "application"),
    "taxonomy.branch": ("Taxonomy", "application"),
    "taxonomy.aspects": ("Taxonomy", "application"),
    "metadata.conditions": ("Taxonomy", "application"),
    "metadata.durations": ("Taxonomy", "application"),
    "unknown": ("Unclassified operation", "seller"),
}
KINDS = {
    "access_expired", "renewal_temporary", "reconnect", "configuration", "permission",
    "missing_scope", "selling_limit", "restriction", "subscription", "validation",
    "missing_resource", "conflict", "rate_limit", "outage", "network", "malformed", "unknown",
}
DOMAINS = {"OAuth", "ACCESS", "ROUTING", "API_INVENTORY", "API_ACCOUNT", "API_FULFILLMENT",
           "API_FINANCES", "API_TAXONOMY", "API_METADATA", "API_MEDIA", "UNKNOWN"}
FIELDS = {"title", "price", "quantity", "category_id", "fulfillment_policy_id", "payment_policy_id",
          "return_policy_id", "merchant_location_key", "photos", "condition_id", "item_specifics",
          "description_html", "listing_duration", "listing_format"}
FIELD_NAMES = {"title": "title", "price": "price", "quantity": "quantity", "availableQuantity": "quantity",
    "categoryId": "category_id", "fulfillmentPolicyId": "fulfillment_policy_id", "paymentPolicyId": "payment_policy_id",
    "returnPolicyId": "return_policy_id", "merchantLocationKey": "merchant_location_key", "condition": "condition_id",
    "conditionId": "condition_id", "imageUrls": "photos", "aspects": "item_specifics", "listingDescription": "description_html",
    "listingDuration": "listing_duration", "format": "listing_format", **{f: f for f in FIELDS}}
INVENTORY_FIELDS = {25003: "price", 25004: "quantity", 25005: "category_id", 25007: "fulfillment_policy_id",
    25008: "payment_policy_id", 25009: "return_policy_id", 25012: "merchant_location_key", 25014: "photos",
    25015: "photos", 25021: "condition_id", 25022: "item_specifics", 25123: "return_policy_id", 25129: "item_specifics"}
MESSAGES = {
    "access_expired": "Access authorisation was rejected. Automatic renewal is attempted first for read-only calls.",
    "renewal_temporary": "Renewal failed - check connection. Seller reconnection is not yet indicated.",
    "reconnect": "Seller authorisation is no longer usable. Reconnect eBay.",
    "configuration": "Application credentials or local configuration need attention. Check EBAY_ENV, EBAY_CLIENT_ID, EBAY_CLIENT_SECRET, EBAY_RU_NAME and MAGPIE_TOKEN_ENCRYPTION_KEY locally. Reconnecting the seller will not fix this.",
    "permission": "eBay permission denied for {operation} - cause not confirmed.",
    "missing_scope": "eBay explicitly reported insufficient scope for {operation}. Review the requested permissions in Settings.",
    "selling_limit": "eBay reports a selling limit. Review the account's selling limits on eBay.",
    "restriction": "eBay reports an account or listing restriction. Check eBay account messages and restrictions.",
    "subscription": "eBay explicitly reports a subscription requirement. Review the requirement on the eBay account.",
    "validation": "eBay rejected {field}. Review this field in the listing editor.",
    "missing_resource": "The resource for {operation} was not found. Confirm its recorded identity and state.",
    "conflict": "eBay reports a state conflict for {operation}. Check the existing result before another action.",
    "rate_limit": "eBay rate limit reached. Wait before another check; this does not permit retrying a write.",
    "outage": "eBay service failure for {operation}. Keep local work going; a write outcome may still be unknown.",
    "network": "Network response was not confirmed for {operation}. A timeout does not cancel a write.",
    "malformed": "Unexpected or malformed response for {operation}. The result is not verified.",
    "unknown": "Unclassified eBay response for {operation}. Copy the sanitised diagnostics; cause not confirmed.",
}


def operation_for(url, method):
    path = urlsplit(url).path
    if "/sell/inventory/" in path:
        tail = path.split("/v1/", 1)[-1].strip("/")
        if tail.startswith("inventory_item"):
            return "inventory.replace" if method == "PUT" else "inventory.item" if "/" in tail else "inventory.items"
        if tail.startswith("location"):
            return "inventory.location_create" if method == "POST" else "inventory.location" if "/" in tail else "inventory.locations"
        if tail == "offer/get_listing_fees": return "inventory.fees"
        if tail.endswith("/publish"): return "inventory.publish"
        if tail.endswith("/withdraw"): return "inventory.withdraw"
        return {"POST": "inventory.create", "PUT": "inventory.update", "DELETE": "inventory.remove"}.get(method,
            "inventory.offers" if tail == "offer" else "inventory.offer")
    for marker, operation in [("payment_policy", "account.payment"), ("fulfillment_policy", "account.fulfillment"),
        ("return_policy", "account.return"), ("get_opted_in_programs", "account.programs"), ("/identity/v1/user", "account.identity"),
        ("/fulfillment/", "fulfillment.orders"), ("/finances/", "finances.transactions"), ("/media/", "media.upload"),
        ("get_default_category_tree_id", "taxonomy.tree"), ("get_category_suggestions", "taxonomy.suggestions"),
        ("get_category_subtree", "taxonomy.branch"), ("get_item_aspects_for_category", "taxonomy.aspects"),
        ("get_item_condition_policies", "metadata.conditions"), ("get_listing_type_policies", "metadata.durations")]:
        if marker in path: return operation
    return "unknown"


def diagnostic(operation, *, status=None, payload=None, failure=None):
    operation = {"publishOffer": "inventory.publish", "createOffer": "inventory.create", "stageOffer": "inventory.update"}.get(operation, operation)
    operation = operation if operation in OPERATIONS else "unknown"
    payload = payload if isinstance(payload, dict) else {}
    errors = payload.get("errors", [])
    warnings = payload.get("warnings", [])
    issues = []
    for severity, rows in [("error", errors), ("warning", warnings)]:
        if not isinstance(rows, list): continue
        for row in rows[:20]:
            if isinstance(row, dict): issues.append(_issue(operation, status, row, severity))
    oauth = payload.get("error")
    if operation.startswith("oauth.") and isinstance(oauth, str) and oauth:
        kind = "configuration" if oauth in {"invalid_client", "unauthorized_client", "invalid_scope", "unsupported_grant_type"} else (
            "reconnect" if oauth == "invalid_grant" and operation == "oauth.refresh" else "configuration" if oauth == "invalid_grant" else "renewal_temporary")
        issues.insert(0, {"kind": kind, "error_id": None, "domain": "OAuth", "category": "REQUEST", "field": None, "severity": "error"})
    if not issues or failure:
        kind = failure or ("permission" if status == 403 else "access_expired" if status == 401 else "missing_resource" if status == 404
            else "conflict" if status == 409 else "rate_limit" if status == 429 else "outage" if status and status >= 500 else "unknown")
        if operation == "oauth.refresh" and kind in {"network", "outage", "unknown", "malformed"}: kind = "renewal_temporary"
        issues.append({"kind": kind, "error_id": None, "domain": "UNKNOWN", "category": "UNKNOWN", "field": None, "severity": "error"})
    value = {"operation": operation, "time": timezone.now().isoformat(), "http_status": status, "issues": issues}
    validate_diagnostic(value)
    return value


def _issue(operation, status, row, severity):
    eid = row.get("errorId")
    eid = eid if type(eid) is int and 0 <= eid <= 2**31 - 1 else None
    domain = row.get("domain") if isinstance(row.get("domain"), str) and row.get("domain") in DOMAINS else "UNKNOWN"
    category = str(row.get("category", "")).upper()
    category = category if category in {"REQUEST", "BUSINESS", "APPLICATION"} else "UNKNOWN"
    field = None
    parameters = row.get("parameters") if isinstance(row.get("parameters"), list) else []
    for parameter in parameters[:20]:
        if not isinstance(parameter, dict): continue
        name, value = parameter.get("name"), parameter.get("value")
        field = (FIELD_NAMES.get(name) if isinstance(name, str) else None) or field
        if name == "fieldName" and isinstance(value, str): field = FIELD_NAMES.get(value) or field
    refs = row.get("inputRefIds") if isinstance(row.get("inputRefIds"), list) else []
    for ref in refs[:20]:
        if isinstance(ref, str):
            for token in re.split(r"[.$\[\]]+", ref): field = FIELD_NAMES.get(token) or field
    kind = "permission" if status == 403 else "access_expired" if status == 401 else "unknown"
    if domain == "OAuth" and eid == 1001: kind = "access_expired"
    elif status == 429 or (domain == "ACCESS" and eid == 2001): kind = "rate_limit"
    elif status == 409: kind = "conflict"
    elif status == 404: kind = "missing_resource"
    elif status and status >= 500: kind = "outage"
    elif operation.startswith("inventory.") and domain == "API_INVENTORY":
        if eid in INVENTORY_FIELDS: kind, field = "validation", INVENTORY_FIELDS[eid]
        elif eid == 25026: kind = "selling_limit"
        elif eid in {25096, 25097, 25098}: kind = "restriction"
        elif eid in {25701, 25702, 25710, 25713}: kind = "missing_resource"
        elif eid in {25016, 25017, 25022, 25601} and field: kind = "validation"
    if category in {"REQUEST", "BUSINESS"} and domain != "UNKNOWN":
        # Text is used only as evidence for a closed classification, never retained.
        message = str(row.get("message", "")).lower()
        if re.search(r"(?:requires?|must have|need).{0,45}(?:store |shop )?subscription", message): kind = "subscription"
        elif re.search(r"(?:seller|account).{0,30}(?:restricted|suspended)", message): kind = "restriction"
        elif status == 403 and "insufficient scope" in message: kind = "missing_scope"
        elif field and kind == "unknown": kind = "validation"
    return {"kind": kind, "error_id": eid, "domain": domain, "category": category, "field": field, "severity": severity}


def validate_diagnostic(value):
    fail = lambda: ValidationError("Diagnostic contains non-allowlisted data.")
    if not isinstance(value, dict) or set(value) != {"operation", "time", "http_status", "issues"}: raise fail()
    if value["operation"] not in OPERATIONS: raise fail()
    valid_time(value["time"])
    if value["http_status"] is not None and (type(value["http_status"]) is not int or not 100 <= value["http_status"] <= 599): raise fail()
    if not isinstance(value["issues"], list) or not 1 <= len(value["issues"]) <= 40: raise fail()
    for issue in value["issues"]:
        if not isinstance(issue, dict) or set(issue) != {"kind", "error_id", "domain", "category", "field", "severity"}: raise fail()
        if issue["kind"] not in KINDS or issue["domain"] not in DOMAINS or issue["category"] not in {"REQUEST", "BUSINESS", "APPLICATION", "UNKNOWN"}: raise fail()
        if issue["severity"] not in {"error", "warning"} or issue["field"] not in FIELDS | {None}: raise fail()
        if issue["error_id"] is not None and (type(issue["error_id"]) is not int or not 0 <= issue["error_id"] <= 2**31 - 1): raise fail()


def valid_time(value):
    try:
        if not isinstance(value, str) or len(value) > 40 or datetime.fromisoformat(value).tzinfo is None: raise ValueError
    except (ValueError, TypeError): raise ValidationError("Invalid diagnostic timestamp.") from None


def public_diagnostic(value):
    validate_diagnostic(value)
    return {**value, "issues": [{**issue, "message": MESSAGES[issue["kind"]].format(
        operation=value["operation"], field=(issue["field"] or "the reported field").replace("_", " "))} for issue in value["issues"]]}


def safe_exception(exc, operation="unknown"):
    value = getattr(exc, "diagnostic", None)
    try:
        if value: validate_diagnostic(value); return value
    except (ValidationError, TypeError, ValueError): pass
    from django.core.exceptions import ImproperlyConfigured
    return diagnostic(operation, status=getattr(exc, "http_status", None),
        failure="configuration" if isinstance(exc, ImproperlyConfigured) else None)


def safe_message(exc, operation="unknown"):
    return " ".join(row["message"] for row in public_diagnostic(safe_exception(exc, operation))["issues"])
