import csv

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Max
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.inventory.filters import InventoryItemFilter
from apps.inventory.models import InventoryItem
from apps.inventory.serializers import (
    InventoryItemDetailSerializer,
    InventoryItemListSerializer,
)
from apps.photos.models import PhotoAsset
from apps.photos.serializers import PhotoAssetSerializer
from apps.photos.fixup import PhotoFixupService
from apps.photos.services import MediaService
from apps.sales.services import recompute_item_sale_status


class InventoryItemViewSet(ModelViewSet):
    queryset = (
        InventoryItem.objects.select_related("category", "location", "acquisition", "owner")
        .prefetch_related("photos", "comparables", "valuation_reports")
        .all()
    )
    filterset_class = InventoryItemFilter
    search_fields = ["title", "sku", "notes"]
    ordering_fields = ["created_at", "estimated_value", "title"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return InventoryItemListSerializer
        return InventoryItemDetailSerializer

    def perform_update(self, serializer):
        item = serializer.save()
        recompute_item_sale_status(item)

    @action(detail=True, methods=["post"], url_path="photos")
    def upload_photo(self, request, pk=None):
        item = self.get_object()
        image = request.FILES.get("image")
        if image is None:
            return Response(
                {"image": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        role = request.data.get("role") or PhotoAsset.Role.OTHER
        if role not in PhotoAsset.Role.values:
            return Response(
                {"role": ["Invalid photo role."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            photo = MediaService().process_upload(item, image, role)
        except DjangoValidationError as exc:
            return Response(
                {"image": exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            PhotoAssetSerializer(photo, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="photos/reorder")
    def reorder_photos(self, request, pk=None):
        item = self.get_object()
        order = request.data.get("order")
        if not isinstance(order, list):
            return Response(
                {"order": ["Expected a list of photo IDs."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        photos = {str(photo.id): photo for photo in item.photos.all()}
        if set(order) != set(photos.keys()):
            return Response(
                {"order": ["Order must include each item photo exactly once."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for index, photo_id in enumerate(order):
                PhotoAsset.objects.filter(pk=photos[photo_id].pk).update(order_index=index)

        serializer = PhotoAssetSerializer(
            item.photos.order_by("order_index", "created_at"),
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="photos/fixup")
    def fixup_photos(self, request, pk=None):
        item = self.get_object()
        PhotoFixupService().generate_for_item(item)
        serializer = PhotoAssetSerializer(
            item.photos.select_related("active_derivative").prefetch_related("derivatives").order_by(
                "order_index",
                "created_at",
            ),
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="export.csv")
    def export_csv(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="inventory-items.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "id",
                "sku",
                "title",
                "category",
                "status",
                "condition",
                "location",
                "acquisition_cost",
                "refurb_cost",
                "inbound_shipping_cost",
                "est_outbound_shipping",
                "est_packaging_cost",
                "estimated_value",
                "min_price",
                "target_price",
                "currency",
                "photo_count",
                "created_at",
                "updated_at",
            ]
        )

        queryset = (
            self.filter_queryset(self.get_queryset())
            .annotate(photo_count=Count("photos"))
            .order_by("sku")
        )
        for item in queryset:
            writer.writerow(
                [
                    item.id,
                    item.sku,
                    item.title,
                    item.category.name if item.category else "",
                    item.status,
                    item.condition,
                    item.location.label if item.location else "",
                    item.acquisition_cost,
                    item.refurb_cost,
                    item.inbound_shipping_cost,
                    item.est_outbound_shipping,
                    item.est_packaging_cost,
                    item.estimated_value,
                    item.min_price,
                    item.target_price,
                    item.currency,
                    item.photo_count,
                    item.created_at,
                    item.updated_at,
                ]
            )
        return response
