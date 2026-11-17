"""Public workflow errors contain whitelisted metadata, never provider payloads."""
from apps.ebay.adapters import EbayHttpError
from apps.ebay.diagnostics import public_diagnostic, safe_exception


class WorkflowError(Exception):
    def __init__(self, key, message, *, status=409, checks=None, diagnostic=None):
        super().__init__(message)
        self.key, self.message, self.status = key, message, status
        self.checks = checks or []
        self.diagnostic = diagnostic

    def payload(self):
        return {"key": self.key, "detail": self.message, "checks": self.checks,
            **({"diagnostic": self.diagnostic} if self.diagnostic else {})}


def provider_error(exc, operation):
    status = exc.http_status if isinstance(exc, EbayHttpError) else None
    codes = list(exc.error_ids) if isinstance(exc, EbayHttpError) else []
    definite = status is not None and 400 <= status < 500 and status not in {408, 409, 425, 429}
    diagnosis = public_diagnostic(safe_exception(exc, operation))
    # Diagnosis is display-only. This established Phase 5 predicate alone determines outcome certainty.
    message = " ".join(i["message"] for i in diagnosis["issues"])
    if not definite: message += " Outcome is unknown. Do not retry publishing; reconcile the offer."
    return {"operation": operation, "http_status": status, "error_ids": codes, "message": message,
            "kind": "definite_failure" if definite else "unknown_outcome", "diagnostic": diagnosis}
