from django.db.models import Q


DRAFT_STATUS_CLASSIFICATION = {
    "draft": "active",
    "ready": "active",
    "exported": "active",
    "staged": "active",
    "published": "terminal",
    "publish_failed": "active",
    "archived": "terminal",
    "publishing": "active",
    "publish_unknown": "active",
}
TERMINAL_DRAFT_STATUSES = frozenset(
    status for status, classification in DRAFT_STATUS_CLASSIFICATION.items()
    if classification == "terminal"
)
IN_FLIGHT_DRAFT_STATUSES = frozenset({"publishing", "publish_unknown"})


def classify_draft_status(status):
    return DRAFT_STATUS_CLASSIFICATION.get(status, "active")


def active_draft_filter():
    # Excluding terminal states also keeps unknown/future statuses active.
    # Migration B must use this same predicate after supervised resolution.
    return ~Q(status__in=sorted(TERMINAL_DRAFT_STATUSES))


def read_only_draft_filter():
    published_id = (
        Q(channel_data__listing_id__isnull=False)
        & ~Q(channel_data__listing_id="")
        & ~Q(channel_data__listing_id=None)
    )
    return Q(status__in=sorted(TERMINAL_DRAFT_STATUSES)) | published_id | Q(channel_listing__isnull=False)
