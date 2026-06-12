from django.db import transaction
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.inventory.models import InventoryItem
from apps.ebay import aspects as ebay_aspects
from apps.ebay import publishing as ebay_publishing
from apps.ebay import staging as ebay_staging
from integrations.ebay import EbayUnavailable
from apps.listing.export import build_export_bundle
from apps.listing.generators import generated_meta, generator_for
from apps.listing.context import safe_context
from apps.listing.models import ListingBoilerplate, ListingDraft
from apps.listing.readiness import check_readiness
from apps.listing.serializers import (
    ListingBoilerplateSerializer,
    ListingDraftSerializer,
)
from apps.listing.specifics import build_specifics, build_specifics_from_context
from apps.valuation.models import ValuationReport


class ListingBoilerplateViewSet(ReadOnlyModelViewSet):
    queryset = ListingBoilerplate.objects.all()
    serializer_class = ListingBoilerplateSerializer
    search_fields = ["name", "notes"]
    ordering_fields = ["channel", "name"]
    ordering = ["channel", "name"]


class ItemListingDraftListCreateView(ListCreateAPIView):
    serializer_class = ListingDraftSerializer
    ordering = ["-created_at"]

    def get_item(self):
        return get_object_or_404(
            InventoryItem.objects.select_related("category").prefetch_related(
                "photos",
                "valuation_reports",
            ),
            pk=self.kwargs["item_id"],
        )

    def get_queryset(self):
        return (
            ListingDraft.objects.select_related("item", "item__category", "boilerplate")
            .filter(item=self.get_item())
            .prefetch_related("item__photos", "item__valuation_reports")
        )

    def create(self, request, *args, **kwargs):
        item = self.get_item()
        with transaction.atomic():
            draft = create_generated_draft(item)
        serializer = self.get_serializer(draft)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ListingDraftViewSet(ModelViewSet):
    queryset = (
        ListingDraft.objects.select_related("item", "item__category", "boilerplate")
        .prefetch_related("item__photos", "item__valuation_reports")
        .all()
    )
    serializer_class = ListingDraftSerializer
    http_method_names = ["get", "patch", "delete", "post", "head", "options"]

    @action(detail=True, methods=["post"], url_path="generate")
    def generate(self, request, pk=None):
        draft = self.get_object()
        fields = request.data.get("fields") or []
        if not isinstance(fields, list) or not fields:
            return Response(
                {"fields": "Provide a non-empty list of fields to regenerate."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        normalized = {"description" if field == "description_html" else field for field in fields}
        allowed = {"title", "description", "specifics", "price"}
        unknown = sorted(normalized - allowed)
        if unknown:
            return Response(
                {"fields": f"Unsupported field(s): {', '.join(unknown)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        confirm_overwrite = bool(request.data.get("confirm_overwrite"))
        protected = []
        if "title" in normalized and draft.title_edited and draft.title.strip():
            protected.append("title")
        if (
            "description" in normalized
            and draft.description_edited
            and draft.description_html.strip()
        ):
            protected.append("description")
        if protected and not confirm_overwrite:
            return Response(
                {
                    "confirm_overwrite": "Required to overwrite edited generated fields.",
                    "protected_fields": protected,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            regenerate_fields(draft, normalized)
            draft.save()

        serializer = self.get_serializer(draft)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="readiness")
    def readiness(self, request, pk=None):
        draft = self.get_object()
        return Response([check.as_dict() for check in check_readiness(draft)])

    @action(detail=True, methods=["get"], url_path="export")
    def export(self, request, pk=None):
        draft = self.get_object()
        draft.status = ListingDraft.Status.EXPORTED
        draft.exported_at = timezone.now()
        draft.save(update_fields=["status", "exported_at", "updated_at"])
        payload, _meta = build_export_bundle(draft)
        response = HttpResponse(payload, content_type="application/zip")
        response["Content-Disposition"] = (
            f'attachment; filename="listing-{draft.item.sku}.zip"'
        )
        return response

    @action(detail=True, methods=["post"], url_path="stage")
    def stage(self, request, pk=None):
        draft = self.get_object()
        try:
            staged = ebay_staging.stage_draft(
                draft,
                override_missing_aspects=bool(request.data.get("override_missing_aspects")),
                override_reason=str(request.data.get("override_reason") or ""),
                actor=request.user,
            )
        except ValidationError as exc:
            return Response(_validation_payload(exc), status=status.HTTP_400_BAD_REQUEST)
        except EbayUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(self.get_serializer(staged).data)

    @action(detail=True, methods=["post"], url_path="withdraw")
    def withdraw(self, request, pk=None):
        draft = self.get_object()
        try:
            withdrawn = ebay_staging.withdraw_staged(draft, actor=request.user)
        except ValidationError as exc:
            return Response(_validation_payload(exc), status=status.HTTP_400_BAD_REQUEST)
        except EbayUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(self.get_serializer(withdrawn).data)

    @action(detail=True, methods=["get"], url_path="aspects-check")
    def aspects_check(self, request, pk=None):
        draft = self.get_object()
        try:
            return Response(ebay_aspects.check_aspects(draft, actor=request.user))
        except EbayUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=True, methods=["get"], url_path="staged-review")
    def staged_review(self, request, pk=None):
        draft = self.get_object()
        try:
            return Response(ebay_publishing.staged_review(draft, actor=request.user))
        except ValidationError as exc:
            return Response(_validation_payload(exc), status=status.HTTP_400_BAD_REQUEST)
        except EbayUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        draft = self.get_object()
        try:
            published = ebay_publishing.publish_draft(
                draft,
                confirm_sku=str(request.data.get("confirm_sku") or ""),
                actor=request.user,
            )
        except ValidationError as exc:
            return Response(_validation_payload(exc), status=status.HTTP_400_BAD_REQUEST)
        except EbayUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(self.get_serializer(published).data)


def create_generated_draft(item) -> ListingDraft:
    ctx = safe_context(item)
    generator = generator_for(item)
    specifics = build_specifics_from_context(ctx)
    boilerplate = (
        ListingBoilerplate.objects.filter(channel="ebay_au", is_active=True)
        .order_by("name")
        .first()
    )
    current_report = current_valuation(item)
    meta = {
        "title": generated_meta(generator.profile_key),
        "description": generated_meta(generator.profile_key),
    }
    price = None
    currency = item.currency or "AUD"
    if current_report and current_report.suggested_price is not None:
        price = current_report.suggested_price
        currency = current_report.currency
        meta["price_source"] = {
            "valuation_report_id": str(current_report.id),
            "price_point": "suggested",
            "value": str(current_report.suggested_price),
            "captured_at": timezone.now().isoformat(),
        }

    title = generator.title(ctx)
    description = generator.description_html(
        ctx,
        specifics=specifics,
        boilerplate_html=boilerplate.body_html if boilerplate else "",
        sku_footer="",
    )
    photo_ids = [
        str(photo.id)
        for photo in item.photos.order_by("order_index", "created_at")
    ]
    return ListingDraft.objects.create(
        item=item,
        title=title,
        description_html=description,
        item_specifics=specifics,
        photo_ids=photo_ids,
        boilerplate=boilerplate,
        price=price,
        currency=currency,
        generated_meta=meta,
    )


def regenerate_fields(draft, fields: set[str]) -> None:
    ctx = safe_context(draft.item)
    generator = generator_for(draft.item)
    meta = dict(draft.generated_meta or {})

    if "specifics" in fields:
        draft.item_specifics = build_specifics(draft.item)

    if "title" in fields:
        draft.title = generator.title(ctx)
        draft.title_edited = False
        meta["title"] = generated_meta(generator.profile_key)

    if "description" in fields:
        specifics = draft.item_specifics or build_specifics_from_context(ctx)
        draft.description_html = generator.description_html(
            ctx,
            specifics=specifics,
            boilerplate_html=draft.boilerplate.body_html if draft.boilerplate else "",
            sku_footer=draft.item.sku if draft.include_sku_footer else "",
        )
        draft.description_edited = False
        meta["description"] = generated_meta(generator.profile_key)

    if "price" in fields:
        report = current_valuation(draft.item)
        if report and report.suggested_price is not None:
            draft.price = report.suggested_price
            draft.currency = report.currency
            meta["price_source"] = {
                "valuation_report_id": str(report.id),
                "price_point": "suggested",
                "value": str(report.suggested_price),
                "captured_at": timezone.now().isoformat(),
            }
        else:
            draft.price = None
            meta.pop("price_source", None)

    draft.generated_meta = meta


def current_valuation(item):
    return ValuationReport.objects.filter(item=item, is_current=True).first()


def _validation_payload(exc: ValidationError) -> dict:
    if hasattr(exc, "message_dict"):
        return exc.message_dict
    return {"detail": "; ".join(exc.messages)}
