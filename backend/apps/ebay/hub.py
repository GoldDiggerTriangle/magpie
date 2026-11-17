"""Owned eBay records only. Opening the hub never refreshes tokens or reconciles."""
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ebay.models import EbayOrderDuplicateCandidate, EbayOrderStaging, EbayOrderSyncState
from apps.ebay.services import status_summary
from apps.listing.models import ChannelListing, ListingDraft


class EbayHubView(APIView):
    def get(self, request):
        status = status_summary()
        environment = status["environment"]
        sync = EbayOrderSyncState.objects.filter(environment=environment).first()
        snapshot = status["snapshot"] or {}
        drafts = []
        for row in ListingDraft.objects.filter(channel="ebay_au").select_related("item").order_by("-updated_at", "id"):
            data = row.channel_data or {}
            drafts.append({
                "id": str(row.pk), "item_id": str(row.item_id), "sku": row.item.sku,
                "title": row.title, "status": row.status, "updated_at": row.updated_at,
                "offer_id": str(data.get("offer_id") or ""),
                "listing_id": str(data.get("listing_id") or ""),
                "publish_started_at": row.publish_started_at,
                "has_publish_error": bool(row.publish_error),
            })
        listings = [{
            "id": str(row.pk), "item_id": str(row.item_id), "sku": row.item.sku,
            "title": row.item.title, "draft_id": str(row.source_listing_draft_id or ""),
            "listing_id": row.external_listing_id, "url": row.url, "listed_at": row.listed_at,
        } for row in ChannelListing.objects.filter(channel="ebay", ended_at__isnull=True).select_related("item")]
        return Response({
            "as_of": timezone.now(), "provenance": "Owned local records; not a live eBay check",
            "drafts": drafts, "listings": listings,
            "connection": {
                "configured": status["configured"], "connected": status["connected"],
                "environment": environment, "requires_reconsent": status["requires_reconsent"],
                "access_token_expires_at": status["access_token_expires_at"],
                "has_refresh_error": bool(status["last_refresh_error"]),
                "policies_fetched_at": snapshot.get("fetched_at"),
            },
            "orders": {
                "last_synced_at": sync.last_synced_at if sync else None,
                "pending": EbayOrderStaging.objects.filter(environment=environment, status="pending").count(),
                "duplicates": EbayOrderDuplicateCandidate.objects.filter(environment=environment, status="pending").count(),
            },
        })
