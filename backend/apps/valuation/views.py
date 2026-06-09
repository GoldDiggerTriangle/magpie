from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.inventory.models import InventoryItem
from apps.valuation.filters import FeeScheduleFilter, ValuationReportFilter
from apps.valuation.models import FeeSchedule, ValuationReport
from apps.valuation.serializers import FeeScheduleSerializer, ValuationReportSerializer
from apps.valuation.services import (
    active_fee_schedule,
    calculate_profit,
    set_current,
    true_cost_for_item,
)


class FeeScheduleViewSet(ReadOnlyModelViewSet):
    queryset = FeeSchedule.objects.all()
    serializer_class = FeeScheduleSerializer
    filterset_class = FeeScheduleFilter
    search_fields = ["name", "notes"]
    ordering_fields = ["effective_from", "name"]
    ordering = ["-effective_from"]


class ItemValuationReportListCreateView(ListCreateAPIView):
    serializer_class = ValuationReportSerializer
    filterset_class = ValuationReportFilter
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_item(self):
        return get_object_or_404(InventoryItem, pk=self.kwargs["item_id"])

    def get_queryset(self):
        return (
            ValuationReport.objects.select_related("item", "fee_schedule")
            .prefetch_related("comp_links__comparable")
            .filter(item=self.get_item())
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["item"] = self.get_item()
        return context

    def perform_create(self, serializer):
        serializer.save(item=self.get_item())


class ValuationReportViewSet(ModelViewSet):
    queryset = (
        ValuationReport.objects.select_related("item", "fee_schedule")
        .prefetch_related("comp_links__comparable")
        .all()
    )
    serializer_class = ValuationReportSerializer
    filterset_class = ValuationReportFilter
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def set_current(self, request, pk=None):
        report = self.get_object()
        report = set_current(report)
        serializer = self.get_serializer(report)
        return Response(serializer.data)

    def profit(self, request, pk=None):
        report = self.get_object()
        price = request.query_params.get("price")
        if price is None:
            return Response(
                {"price": ["This query parameter is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            sale_price = Decimal(str(price))
        except (InvalidOperation, ValueError):
            return Response(
                {"price": ["Enter a valid number."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        schedule = report.fee_schedule or active_fee_schedule()
        if schedule is None:
            return Response(
                {"fee_schedule": ["No active fee schedule is available."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        breakdown = calculate_profit(
            sale_price=sale_price,
            true_cost=true_cost_for_item(report.item),
            schedule=schedule,
            outbound_shipping=report.item.est_outbound_shipping,
            packaging=report.item.est_packaging_cost,
        )
        return Response(breakdown.as_serialized())
