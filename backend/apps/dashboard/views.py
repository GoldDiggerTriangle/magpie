from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Q, Sum
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dashboard.analytics import (
    build_aging,
    build_by_category,
    build_estimate_vs_actual,
    build_listing_opportunities,
    build_pnl,
    build_summary,
    parse_filters,
)
from apps.dashboard.models import DashboardPreference
from apps.dashboard.serializers import (
    DashboardPreferenceSerializer,
    default_preference_payload,
)
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


class AnalyticsSummaryView(APIView):
    def get(self, request):
        return Response(build_summary(parse_filters(request.query_params)))


class AnalyticsPnlView(APIView):
    def get(self, request):
        return Response(build_pnl(parse_filters(request.query_params)))


class AnalyticsByCategoryView(APIView):
    def get(self, request):
        return Response(build_by_category(parse_filters(request.query_params)))


class AnalyticsEstimateVsActualView(APIView):
    def get(self, request):
        return Response(build_estimate_vs_actual(parse_filters(request.query_params)))


class AnalyticsAgingView(APIView):
    def get(self, request):
        return Response(build_aging(parse_filters(request.query_params)))


class AnalyticsListingOpportunitiesView(APIView):
    def get(self, request):
        return Response(build_listing_opportunities(parse_filters(request.query_params)))


class DashboardPreferenceView(APIView):
    def get(self, request):
        preference = DashboardPreference.objects.order_by("-updated_at").first()
        if preference is None:
            return Response(default_preference_payload())
        return Response(DashboardPreferenceSerializer(preference).data)

    def put(self, request):
        preference = DashboardPreference.objects.order_by("-updated_at").first()
        serializer = DashboardPreferenceSerializer(
            preference,
            data=request.data,
            partial=False,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
