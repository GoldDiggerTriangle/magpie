"""Model-level privacy boundary, also used by conditional/bulk writes."""
from django.core.exceptions import ValidationError

from apps.ebay.diagnostics import OPERATIONS, validate_diagnostic, valid_time


def validate_operations(value):
    if not isinstance(value, dict) or len(value) > len(OPERATIONS):
        raise ValidationError("Invalid health operation registry.")
    for operation, entry in value.items():
        if operation not in OPERATIONS or not isinstance(entry, dict) or set(entry) != {"last_success", "current_failure", "warnings"}:
            raise ValidationError("Health data is not allowlisted.")
        success = entry["last_success"]
        if success is not None:
            if not isinstance(success, dict) or set(success) != {"sequence", "time", "http_status", "count"}:
                raise ValidationError("Invalid health success record.")
            _sequence(success["sequence"])
            valid_time(success["time"])
            if type(success["http_status"]) is not int or not 200 <= success["http_status"] <= 299:
                raise ValidationError("Invalid health success status.")
            if success["count"] is not None and (type(success["count"]) is not int or not 0 <= success["count"] <= 10**12):
                raise ValidationError("Invalid health record count.")
        failure = entry["current_failure"]
        if failure is not None:
            if not isinstance(failure, dict) or set(failure) != {"sequence", "diagnostic"}:
                raise ValidationError("Invalid health failure record.")
            _sequence(failure["sequence"])
            validate_diagnostic(failure["diagnostic"])
            if failure["diagnostic"]["operation"] != operation:
                raise ValidationError("Diagnostic operation mismatch.")
        if entry["warnings"] is not None:
            validate_diagnostic(entry["warnings"])
            if entry["warnings"]["operation"] != operation or any(i["severity"] != "warning" for i in entry["warnings"]["issues"]):
                raise ValidationError("Invalid health warnings.")


def _sequence(value):
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise ValidationError("Invalid health attempt sequence.")
