from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework import mixins

from apps.inventory.models import InventoryItem
from apps.sales.models import SaleRecord
from apps.sales.serializers import SaleRecordSerializer


class SaleRecordViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    serializer_class = SaleRecordSerializer
    queryset = (
        SaleRecord.objects.select_related("item", "listing_draft", "corrected_from")
        .prefetch_related("corrections")
        .all()
    )
    ordering_fields = ["sale_date", "created_at", "sale_price", "quantity"]
    ordering = ["-sale_date", "-created_at"]
    search_fields = ["item__sku", "item__title", "notes"]

    def get_queryset(self):
        queryset = super().get_queryset()
        item_id = self.request.query_params.get("item")
        if item_id:
            queryset = queryset.filter(item_id=item_id)
        return queryset

    @action(detail=True, methods=["post"])
    def correct(self, request, pk=None):
        corrected = self.get_object()
        serializer = self.get_serializer(
            data={**request.data, "item": str(corrected.item_id)},
            context={**self.get_serializer_context(), "corrected_from": corrected},
        )
        serializer.is_valid(raise_exception=True)
        sale = serializer.save()
        return Response(
            self.get_serializer(sale).data,
            status=status.HTTP_201_CREATED,
        )


class ItemSaleRecordListCreateView(ListCreateAPIView):
    serializer_class = SaleRecordSerializer

    def get_queryset(self):
        return (
            SaleRecord.objects.select_related("item", "listing_draft", "corrected_from")
            .prefetch_related("corrections")
            .filter(item_id=self.kwargs["item_id"])
            .order_by("-sale_date", "-created_at")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["item"] = InventoryItem.objects.get(pk=self.kwargs["item_id"])
        return context
