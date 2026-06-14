from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.intelligence.images import scan_item_photos
from apps.intelligence.models import FieldSuggestion
from apps.intelligence.ocr import run_ocr_for_item
from apps.intelligence.serializers import (
    FieldSuggestionResolveSerializer,
    FieldSuggestionSerializer,
    OcrRunResultSerializer,
    SoldSearchLinkSerializer,
)
from apps.intelligence.sold_search import build_sold_search_links
from apps.intelligence.suggestions import SuggestionError, resolve_suggestion
from apps.inventory.models import InventoryItem


class FieldSuggestionViewSet(ReadOnlyModelViewSet):
    serializer_class = FieldSuggestionSerializer
    queryset = FieldSuggestion.objects.select_related("item", "photo").all()

    def get_queryset(self):
        queryset = super().get_queryset()
        item = self.request.query_params.get("item")
        status_filter = self.request.query_params.get("status")
        source = self.request.query_params.get("source")
        if item:
            queryset = queryset.filter(item_id=item)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if source:
            queryset = queryset.filter(source=source)
        return queryset

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._resolve(request, "approve")

    @action(detail=True, methods=["post"])
    def edit(self, request, pk=None):
        serializer = FieldSuggestionResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._resolve(request, "edit", serializer.validated_data.get("value"))

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._resolve(request, "reject")

    def _resolve(self, request, action: str, value=None):
        suggestion = self.get_object()
        try:
            resolved = resolve_suggestion(suggestion, action=action, value=value)
        except SuggestionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(resolved).data)


class ItemSoldSearchView(APIView):
    def get(self, request, item_id):
        item = get_object_or_404(InventoryItem.objects.select_related("category").prefetch_related(
            "valuation_reports"
        ), pk=item_id)
        serializer = SoldSearchLinkSerializer(build_sold_search_links(item), many=True)
        return Response({"links": serializer.data})


class ItemOcrRunView(APIView):
    def post(self, request, item_id):
        item = get_object_or_404(InventoryItem.objects.prefetch_related("photos").select_related(
            "category"
        ), pk=item_id)
        result = run_ocr_for_item(item)
        serializer = OcrRunResultSerializer(result, context={"request": request})
        return Response(serializer.data)


class ItemDuplicateScanView(APIView):
    def post(self, request, item_id):
        item = get_object_or_404(InventoryItem.objects.prefetch_related("photos"), pk=item_id)
        suggestions = scan_item_photos(item)
        serializer = FieldSuggestionSerializer(
            suggestions,
            many=True,
            context={"request": request},
        )
        return Response({"suggestions": serializer.data})
