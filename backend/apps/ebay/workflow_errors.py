"""Public workflow errors contain whitelisted metadata, never provider payloads."""
from apps.ebay.adapters import EbayHttpError


class WorkflowError(Exception):
    def __init__(self, key, message, *, status=409, checks=None):
        super().__init__(message)
        self.key, self.message, self.status = key, message, status
        self.checks = checks or []

    def payload(self):
        return {"key": self.key, "detail": self.message, "checks": self.checks}


def provider_error(exc, operation):
    status = exc.http_status if isinstance(exc, EbayHttpError) else None
    codes = list(exc.error_ids) if isinstance(exc, EbayHttpError) else []
    definite = status is not None and 400 <= status < 500 and status not in {408, 409, 425, 429}
    message = ("eBay permission denied; check the account connection and permissions." if status in {401, 403}
               else "eBay rejected the request; review the listing fields and error codes." if definite
               else "eBay outcome is unknown. Do not retry publishing; reconcile the offer.")
    return {"operation": operation, "http_status": status, "error_ids": codes, "message": message,
            "kind": "definite_failure" if definite else "unknown_outcome"}
