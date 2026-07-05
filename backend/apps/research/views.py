from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.inventory.models import InventoryItem
from apps.research.filters import ComparableFilter, ResearchRecordFilter
from apps.research.descriptor_lookup import descriptor_lookup_payload, parse_terms
from apps.research.links import research_links
from apps.research.models import Comparable, ResearchRecord
from apps.research.pricing_evidence import pricing_evidence_payload
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


class PricingEvidenceView(APIView):
    def get(self, request, item_id):
        item = get_object_or_404(
            InventoryItem.objects.select_related("category").prefetch_related("comparables"),
            pk=item_id,
        )
        return Response(pricing_evidence_payload(item))


class DescriptorEvidenceLookupView(APIView):
    def get(self, request):
        return Response(
            descriptor_lookup_payload(
                category_id=request.query_params.get("category"),
                terms=request.query_params.get("terms", ""),
                attributes=query_attributes(request),
            )
        )


class DescriptorComparableCaptureView(APIView):
    def post(self, request):
        payload = request.data
        price = payload.get("price")
        if price in {None, ""}:
            return Response(
                {"detail": "Captured evidence needs a human-entered price."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        source = (payload.get("source") or "").strip()
        if not source:
            return Response(
                {"detail": "Captured evidence needs a source label."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        category_id = payload.get("category") or None
        terms = parse_terms(payload.get("terms") or "")
        attributes = payload.get("attributes") if isinstance(payload.get("attributes"), dict) else {}
        comparable_data = {
            "item": payload.get("item") or None,
            "descriptor_category": category_id,
            "descriptor_terms": terms,
            "descriptor_attributes": attributes,
            "kind": Comparable.Kind.SOLD,
            "source": source,
            "source_tag": payload.get("source_tag") or "manual",
            "title": payload.get("title") or "Captured descriptor comparable",
            "price": price,
            "price_basis": payload.get("price_basis") or Comparable.PriceBasis.UNKNOWN,
            "shipping": payload.get("shipping") or None,
            "currency": payload.get("currency") or "AUD",
            "condition": payload.get("condition") or "",
            "grade": payload.get("grade") or "",
            "sale_format": payload.get("sale_format") or Comparable.SaleFormat.UNKNOWN,
            "match_scope": payload.get("match_scope") or Comparable.MatchScope.SIMILAR,
            "match_reason": payload.get("match_reason") or "user-captured from descriptor lookup",
            "url": payload.get("url") or "",
            "observed_on": payload.get("observed_on") or None,
            "notes": payload.get("notes") or "",
        }
        serializer = ComparableSerializer(data=comparable_data)
        serializer.is_valid(raise_exception=True)
        comparable = serializer.save()
        return Response(
            {
                "comparable": ComparableSerializer(comparable).data,
                "lookup": descriptor_lookup_payload(
                    category_id=category_id,
                    terms=terms,
                    attributes=attributes,
                ),
            },
            status=status.HTTP_201_CREATED,
        )


def query_attributes(request) -> dict:
    attributes = {}
    for key, value in request.query_params.items():
        if key.startswith("attr_") and value:
            attributes[key.removeprefix("attr_")] = value
    return attributes
