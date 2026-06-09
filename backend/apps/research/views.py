from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.inventory.models import InventoryItem
from apps.research.filters import ComparableFilter, ResearchRecordFilter
from apps.research.links import research_links
from apps.research.models import Comparable, ResearchRecord
from apps.research.serializers import ComparableSerializer, ResearchRecordSerializer


class ComparableViewSet(ModelViewSet):
    queryset = Comparable.objects.select_related("item", "item__category").all()
    serializer_class = ComparableSerializer
    filterset_class = ComparableFilter
    search_fields = ["source", "title", "notes", "url"]
    ordering_fields = ["observed_on", "price", "created_at"]
    ordering = ["-observed_on", "-created_at"]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Comparable is linked to a valuation report and cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ResearchRecordViewSet(ModelViewSet):
    queryset = ResearchRecord.objects.select_related("item").all()
    serializer_class = ResearchRecordSerializer
    filterset_class = ResearchRecordFilter
    search_fields = ["source", "content"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]


class ResearchLinksView(APIView):
    def get(self, request, item_id):
        item = get_object_or_404(InventoryItem, pk=item_id)
        return Response({"item": str(item.id), "links": research_links(item)})
