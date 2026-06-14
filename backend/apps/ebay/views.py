from django.core.exceptions import ImproperlyConfigured, ValidationError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.ebay import EbayUnavailable
from apps.ebay.serializers import (
    CategoryAspectsQuerySerializer,
    CategorySuggestionsQuerySerializer,
    ConnectCompleteSerializer,
    EbayOrderDuplicateCandidateSerializer,
    EbayOrderDuplicateResolveSerializer,
    EbayOrderStagingResolveSerializer,
    EbayOrderStagingSerializer,
    EbayOrderSyncSerializer,
    MerchantLocationCreateSerializer,
    MerchantLocationSerializer,
)
from apps.ebay import aspects
from apps.ebay import order_sync
from apps.ebay import services
from apps.ebay.models import EbayOrderDuplicateCandidate, EbayOrderStaging
from apps.sales.serializers import SaleRecordSerializer


class EbayConnectStartView(APIView):
    def post(self, request):
        try:
            return Response(services.start_connect(actor=request.user))
        except ImproperlyConfigured as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except EbayUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class EbayConnectCompleteView(APIView):
    def post(self, request):
        serializer = ConnectCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            summary = services.complete_connect(
                pasted_url=serializer.validated_data.get("pasted_url"),
                code=serializer.validated_data.get("code"),
                state=serializer.validated_data.get("state"),
                actor=request.user,
            )
        except ValidationError as exc:
            return Response({"detail": exc.message}, status=status.HTTP_400_BAD_REQUEST)
        except (ImproperlyConfigured, EbayUnavailable) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(
            {
                "environment": summary.environment,
                "ebay_user_id": summary.ebay_user_id,
                "ebay_username": summary.ebay_username,
                "scopes": summary.scopes,
                "access_token_expires_at": summary.access_token_expires_at,
                "refresh_token_expires_at": summary.refresh_token_expires_at,
            }
        )


class EbayDisconnectView(APIView):
    def post(self, request):
        services.disconnect(actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EbayStatusView(APIView):
    def get(self, request):
        return Response(services.status_summary())


class EbayRefreshPoliciesView(APIView):
    def post(self, request):
        try:
            services.refresh_account_snapshot(actor=request.user)
        except (ImproperlyConfigured, EbayUnavailable) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(services.status_summary())


class EbayCategorySuggestionsView(APIView):
    def get(self, request):
        serializer = CategorySuggestionsQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(
                aspects.suggest_categories(
                    q=serializer.validated_data["q"],
                    actor=request.user,
                )
            )
        except (ImproperlyConfigured, EbayUnavailable) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class EbayCategoryAspectsView(APIView):
    def get(self, request):
        serializer = CategoryAspectsQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(
                aspects.get_category_aspects(
                    category_id=serializer.validated_data["category_id"],
                    actor=request.user,
                )
            )
        except (ImproperlyConfigured, EbayUnavailable) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class EbayMerchantLocationView(APIView):
    def get(self, request):
        location = services.current_merchant_location()
        if location is None:
            return Response({"configured": False, "location": None})
        return Response(
            {
                "configured": True,
                "location": MerchantLocationSerializer(location).data,
            }
        )

    def post(self, request):
        serializer = MerchantLocationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            location = services.create_merchant_location(
                actor=request.user,
                **serializer.validated_data,
            )
        except (ImproperlyConfigured, EbayUnavailable) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(
            {
                "configured": True,
                "location": MerchantLocationSerializer(location).data,
            },
            status=status.HTTP_201_CREATED,
        )


class EbayOrderSyncView(APIView):
    def post(self, request):
        serializer = EbayOrderSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(
                order_sync.sync_orders(actor=request.user, **serializer.validated_data)
            )
        except (ImproperlyConfigured, EbayUnavailable) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class EbayOrderStagingViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = EbayOrderStagingSerializer
    queryset = EbayOrderStaging.objects.select_related("resolved_sale").all()
    ordering = ["-sale_date", "-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        staging = self.get_object()
        serializer = EbayOrderStagingResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action_name = serializer.validated_data["action"]
        item = serializer.validated_data.get("item")
        try:
            sale = order_sync.resolve_staging(
                staging,
                action=action_name,
                actor=request.user,
                item=item,
                item_data=serializer.item_data,
                cost_basis_override=serializer.validated_data.get("cost_basis_override"),
                notes=serializer.validated_data.get("notes", ""),
            )
        except DRFValidationError as exc:
            payload = _staging_resolution_error_payload(
                exc,
                staging=staging,
                action=action_name,
                item=item,
            )
            if payload:
                return Response(payload, status=status.HTTP_400_BAD_REQUEST)
            raise
        return Response(SaleRecordSerializer(sale).data, status=status.HTTP_201_CREATED)


class EbayOrderDuplicateCandidateViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = EbayOrderDuplicateCandidateSerializer
    queryset = (
        EbayOrderDuplicateCandidate.objects.select_related("item", "manual_sale")
        .all()
    )
    ordering = ["-sale_date", "-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        candidate = self.get_object()
        serializer = EbayOrderDuplicateResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resolved = order_sync.resolve_duplicate_candidate(
            candidate,
            action=serializer.validated_data["action"],
            actor=request.user,
        )
        return Response(self.get_serializer(resolved).data)


def _staging_resolution_error_payload(
    exc: DRFValidationError,
    *,
    staging: EbayOrderStaging,
    action: str,
    item,
) -> dict | None:
    if action != "link" or item is None or not _has_quantity_error(exc):
        return None
    item.refresh_from_db()
    sold = item.quantity_sold
    total = item.quantity_total
    remaining = item.quantity_remaining
    if remaining <= 0:
        detail = (
            f"Can\u2019t link \u2014 {item.sku} has no remaining quantity "
            f"({sold} of {total} already sold). Increase that item\u2019s quantity, "
            "choose a different item, or mark this order external."
        )
    else:
        detail = (
            f"Can\u2019t link \u2014 {item.sku} only has {remaining} remaining "
            f"({sold} of {total} already sold), but this order needs {staging.quantity}. "
            "Increase that item\u2019s quantity, choose a different item, or mark this order external."
        )
    return {
        "detail": detail,
        "code": "quantity_remaining_exceeded",
        "item": str(item.id),
        "sku": item.sku,
        "quantity_total": total,
        "quantity_sold": sold,
        "quantity_remaining": remaining,
        "field_errors": exc.detail,
    }


def _has_quantity_error(exc: DRFValidationError) -> bool:
    detail = exc.detail
    if isinstance(detail, dict):
        return "quantity" in detail
    return False
