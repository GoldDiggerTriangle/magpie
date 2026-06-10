from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.inventory.models import InventoryItem
from apps.valuation.filters import FeeScheduleFilter, ValuationReportFilter
from apps.valuation.models import FeeSchedule, Metal, ValuationReport
from apps.valuation.serializers import FeeScheduleSerializer, ValuationReportSerializer
from apps.valuation.services import (
    active_fee_schedule,
    calculate_profit,
    get_spot,
    serialize_spot_quote,
    set_current,
    true_cost_for_item,
)
from integrations.metals import MetalsUnavailable


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

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
        except MetalsUnavailable as exc:
            return Response(
                {
                    "needs_manual_spot": True,
                    "detail": str(exc),
                    "fallback_strategy": ValuationReport.Strategy.COMMODITY_MANUAL,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except DRFValidationError as exc:
            response_status = (
                status.HTTP_422_UNPROCESSABLE_ENTITY
                if self._is_live_input_error(request, exc.detail)
                else status.HTTP_400_BAD_REQUEST
            )
            return Response(exc.detail, status=response_status)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def _is_live_input_error(self, request, detail) -> bool:
        return (
            request.data.get("strategy") == ValuationReport.Strategy.COMMODITY_LIVE
            and isinstance(detail, dict)
            and "inputs" in detail
        )


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


class MetalsSpotView(APIView):
    def get(self, request):
        metal = str(request.query_params.get("metal") or Metal.GOLD).strip().lower()
        currency = str(request.query_params.get("currency") or "AUD").strip().upper()
        refresh = str(request.query_params.get("refresh", "")).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        if metal not in Metal.values:
            return Response(
                {"metal": [f"Unsupported metal: {metal}"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(currency) != 3:
            return Response(
                {"currency": ["Currency must be a three-letter ISO code."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            quote = get_spot(metal, currency, force_refresh=refresh)
        except MetalsUnavailable as exc:
            return Response(
                {
                    "needs_manual_spot": True,
                    "detail": str(exc),
                    "fallback_strategy": ValuationReport.Strategy.COMMODITY_MANUAL,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(serialize_spot_quote(quote))
