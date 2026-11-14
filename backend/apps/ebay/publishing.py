"""Public entry points for the single reviewed publishing pipeline."""
from apps.ebay.publish_state import publish_draft, reconcile_draft
from apps.ebay.review import prepare_review, review_payload


def staged_review(draft, *, actor=None):
    return review_payload(prepare_review(draft, actor=actor))
