"""Local crash recovery at service startup, never during management commands."""
import logging

from django.db import DatabaseError


def recover_interrupted_publishes():
    from apps.ebay.publish_state import recover_stale
    try:
        recover_stale()
    except DatabaseError:
        # Deployment may start before an approved additive migration is applied.
        # Never log database exceptions: drivers can include connection values.
        logging.getLogger(__name__).warning("Publish recovery unavailable; check database migrations.")
