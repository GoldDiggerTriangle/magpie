from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Q, Sum
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventory.models import InventoryItem


class DashboardSummaryView(APIView):
    def get(self, request):
        queryset = InventoryItem.objects.all()
        total_value = queryset.aggregate(total=Sum("estimated_value"))["total"] or Decimal("0")
        by_status = dict(queryset.values_list("status").annotate(count=Count("id")))
        missing_photos = queryset.annotate(photo_count=Count("photos")).filter(
            photo_count=0
        ).count()
        high_value_unlisted = queryset.filter(
            estimated_value__gte=settings.HIGH_VALUE_THRESHOLD
        ).exclude(
            status__in=[
                InventoryItem.Status.LISTED,
                InventoryItem.Status.SOLD,
                InventoryItem.Status.ARCHIVED,
            ]
        ).count()

        return Response(
            {
                "total_items": queryset.count(),
                "total_estimated_value": str(total_value),
                "currency": "AUD",
                "by_status": by_status,
                "missing_photos": missing_photos,
                "high_value_unlisted": high_value_unlisted,
            }
        )
