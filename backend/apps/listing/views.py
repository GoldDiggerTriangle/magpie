from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as ApiValidationError
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.inventory.models import InventoryItem
from apps.ebay import aspects as ebay_aspects
from apps.ebay import publishing as ebay_publishing
from apps.ebay import staging as ebay_staging
from integrations.ebay import EbayUnavailable
from apps.listing.channel_listings import (
    CHANNEL_LABELS,
    item_listing_state,
    seed_ebay_channel_listings,
    take_down_checklist_items,
)
from apps.listing.copy_packs import render_copy_pack
from apps.listing.canonical import get_or_create_canonical_draft, plan_group
from apps.listing.export import build_export_bundle
from apps.listing.generators import generated_meta, generator_for
from apps.listing.context import safe_context
from apps.listing.editor import description_default, editor_context
from apps.listing.editor_metadata import refresh_editor_metadata
from apps.listing.models import ChannelListing, ListingBoilerplate, ListingDraft
from apps.listing.readiness import check_readiness
from apps.listing.serializers import (
    ChannelListingSerializer,
    ListingBoilerplateSerializer,
    ListingDraftSerializer,
)
from apps.listing.specifics import build_specifics, build_specifics_from_context


class ListingBoilerplateViewSet(ReadOnlyModelViewSet):
    queryset = ListingBoilerplate.objects.all()
    serializer_class = ListingBoilerplateSerializer
    search_fields = ["name", "notes"]
    ordering_fields = ["channel", "name"]
    ordering = ["channel", "name"]


class ItemCopyPackView(APIView):
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        item = get_object_or_404(
            InventoryItem.objects.select_related("category").prefetch_related("listing_drafts"),
            pk=kwargs["item_id"],
        )
        payload = render_copy_pack(
            item,
            channel=request.query_params.get("channel") or "generic",
            evidence_price=request.query_params.get("evidence_price"),
            evidence_label=request.query_params.get("evidence_label") or "",
        )
        return Response(payload)


class ChannelListingViewSet(ModelViewSet):
    serializer_class = ChannelListingSerializer
    queryset = (
        ChannelListing.objects.select_related("item", "item__category", "source_listing_draft")
        .prefetch_related("item__sales", "item__channel_listings")
        .all()
    )
    ordering_fields = ["listed_at", "ended_at", "channel"]
    ordering = ["channel", "-listed_at"]
    search_fields = ["item__sku", "item__title", "note", "url"]

    def get_queryset(self):
        queryset = super().get_queryset()
        active = self.request.query_params.get("active")
        channel = self.request.query_params.get("channel")
        item_id = self.request.query_params.get("item")
        if active == "true":
            queryset = queryset.filter(ended_at__isnull=True)
        elif active == "false":
            queryset = queryset.filter(ended_at__isnull=False)
        if channel:
            queryset = queryset.filter(channel=channel)
        if item_id:
            queryset = queryset.filter(item_id=item_id)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["now"] = timezone.now()
        return context

    @action(detail=True, methods=["post"], url_path="mark-ended")
    def mark_ended(self, request, pk=None):
        listing = self.get_object()
        if listing.ended_at is None:
            listing.ended_at = timezone.now()
            listing.save(update_fields=["ended_at", "updated_at"])
        return Response(self.get_serializer(listing).data)

    @action(detail=False, methods=["post"], url_path="seed-ebay")
    def seed_ebay(self, request):
        result = seed_ebay_channel_listings()
        return Response(
            {
                "seeded": result.seeded,
                "existing": result.existing,
                "skipped_ambiguous": result.skipped_ambiguous,
                "skipped_missing_date": result.skipped_missing_date,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="board")
    def board(self, request):
        listings = list(
            self.filter_queryset(self.get_queryset().filter(ended_at__isnull=True))
            .order_by("channel", "listed_at")
        )
        serializer = self.get_serializer(listings, many=True)
        groups = []
        by_channel = {}
        for row in serializer.data:
            by_channel.setdefault(row["channel"], []).append(row)
        for channel, rows in sorted(by_channel.items(), key=lambda item: CHANNEL_LABELS.get(item[0], item[0])):
            groups.append(
                {
                    "channel": channel,
                    "channel_label": CHANNEL_LABELS.get(channel, channel),
                    "count": len(rows),
                    "listings": rows,
                }
            )
        checklist_items = [
            _serialize_item_listing_state(item, context=self.get_serializer_context())
            for item in take_down_checklist_items()
        ]
        partial_items = [
            _serialize_item_listing_state(item, context=self.get_serializer_context())
            for item in InventoryItem.objects.prefetch_related("channel_listings", "sales")
            .filter(channel_listings__ended_at__isnull=True)
            .distinct()
            if item.quantity_sold > 0 and item.quantity_remaining > 0
        ]
        return Response(
            {
                "groups": groups,
                "take_down_checklist": checklist_items,
                "partial_quantity": partial_items,
                "empty": not groups,
            }
        )


class ItemListingDraftListCreateView(ListCreateAPIView):
    serializer_class = ListingDraftSerializer
    ordering = None

    def get_item(self):
        return get_object_or_404(
            InventoryItem.objects.select_related("category").prefetch_related(
                "photos",
                "valuation_reports",
            ),
            pk=self.kwargs["item_id"],
        )

    def get_queryset(self):
        queryset = (
            ListingDraft.objects.select_related("item", "item__category", "boilerplate")
            .filter(item=self.get_item())
            .prefetch_related("item__photos", "item__valuation_reports")
        )
        ebay_drafts = list(queryset.filter(channel="ebay_au"))
        group = plan_group(ebay_drafts) if ebay_drafts else None
        if group and group["keeper"]:
            return queryset.annotate(
                canonical_order=Case(
                    When(pk=group["keeper"]["draft_id"], then=Value(0)),
                    default=Value(1), output_field=IntegerField(),
                )
            ).order_by("canonical_order", "-created_at")
        return queryset

    def create(self, request, *args, **kwargs):
        item = self.get_item()
        channel = request.data.get("channel", "ebay_au")
        if not isinstance(channel, str) or not channel.strip() or len(channel) > 30:
            return Response({"channel": "Provide a channel name of at most 30 characters."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            draft, created = get_or_create_canonical_draft(
                item, channel=channel,
                create_new=lambda: create_generated_draft(item, channel=channel),
            )
        except ValidationError as exc:
            return Response(_validation_payload(exc), status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(draft)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ListingDraftViewSet(ModelViewSet):
    queryset = (
        ListingDraft.objects.select_related("item", "item__category", "boilerplate")
        .prefetch_related("item__photos", "item__valuation_reports")
        .all()
    )
    serializer_class = ListingDraftSerializer
    http_method_names = ["get", "patch", "delete", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        return Response({"detail": "Create or open drafts through the item's listing-drafts endpoint."}, status=status.HTTP_400_BAD_REQUEST)

    def mutable_draft(self):
        draft = self.get_object()
        try:
            draft.assert_editable()
        except ValidationError as exc:
            raise ApiValidationError(_validation_payload(exc)) from None
        return draft

    def perform_destroy(self, instance):
        try:
            instance.assert_editable()
            raise ApiValidationError({"detail": "Hard deletion is disabled. Archive the draft to retain its history."})
        except ValidationError as exc:
            raise ApiValidationError(_validation_payload(exc)) from None

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        from copy import deepcopy
        from apps.audit.services import record
        from apps.listing.canonical import completeness_components
        with transaction.atomic():
            draft = self.mutable_draft()
            if str((draft.channel_data or {}).get("offer_id") or "").strip():
                return Response({"detail": "This draft holds a staged offer. Withdraw it before archiving (Phase 5)."}, status=400)
            prior = draft.status
            score = sum(completeness_components(draft).values())
            data = deepcopy(draft.channel_data or {})
            data["archived_at"] = timezone.now().isoformat()
            claimed = ListingDraft.objects.filter(pk=draft.pk, updated_at=draft.updated_at).update(status=ListingDraft.Status.ARCHIVED, channel_data=data, updated_at=timezone.now())
            if not claimed:
                return Response({"detail": "Draft changed elsewhere. Reload before archiving."}, status=409)
            record(actor=request.user, action="listing.draft.archived", target_type="listing_draft", target_id=str(draft.pk), payload={"pre_archive_status": prior, "offer_id": None, "score": score})
            draft.refresh_from_db()
        return Response(self.get_serializer(draft).data)

    @action(detail=True, methods=["get"], url_path="editor")
    def editor(self, request, pk=None):
        return Response(editor_context(self.get_object(), category_id=request.query_params.get("category_id")))

    @action(detail=True, methods=["get"], url_path="category-children")
    def category_children(self, request, pk=None):
        from apps.ebay.services import get_app_access_token
        import integrations.ebay as ebay
        self.mutable_draft()
        category_id = request.query_params.get("category_id", "")
        if len(category_id) > 30 or not category_id.isdecimal() or int(category_id) <= 0:
            return Response({"detail": "Choose a non-root category ID to browse."}, status=400)
        try:
            result = ebay.get_ebay_taxonomy_adapter(access_token=get_app_access_token()).category_children(category_id=category_id)
        except EbayUnavailable:
            return Response({"detail": "Category browse unavailable. Keep the current mapping and retry the metadata connection."}, status=503)
        return Response({**result, "fetched_at": timezone.now().isoformat(), "provenance": "eBay AU Taxonomy subtree GET; immediate children only"})

    @action(detail=True, methods=["post"], url_path="refresh-metadata")
    def refresh_metadata(self, request, pk=None):
        draft = self.mutable_draft()
        query = request.data.get("query", "")
        category_id = request.data.get("category_id", (draft.channel_data or {}).get("category_id", ""))
        if not isinstance(query, str) or len(query) > 200 or not isinstance(category_id, str) or (category_id and not category_id.isdecimal()):
            return Response({"detail": "Provide a category ID and/or a search of at most 200 characters."}, status=400)
        try:
            updated = refresh_editor_metadata(draft, query=query, category_id=category_id, actor=request.user)
        except ValidationError as exc:
            return Response(_validation_payload(exc), status=400)
        except EbayUnavailable:
            return Response({"detail": "eBay metadata refresh failed. Saved snapshots are unchanged; check the connection in Settings and retry."}, status=503)
        return Response({"draft": self.get_serializer(updated).data, "editor": editor_context(updated, category_id=category_id)})

    @action(detail=True, methods=["post"], url_path="generate")
    def generate(self, request, pk=None):
        draft = self.mutable_draft()
        fields = request.data.get("fields") or []
        if not isinstance(fields, list) or not fields:
            return Response(
                {"fields": "Provide a non-empty list of fields to regenerate."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        normalized = {"description" if field == "description_html" else field for field in fields}
        allowed = {"title", "description", "specifics"}
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
        if not draft.is_read_only:
            draft.assert_editable()
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
        draft = self.mutable_draft()
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
        draft = self.mutable_draft()
        try:
            withdrawn = ebay_staging.withdraw_staged(draft, actor=request.user)
        except ValidationError as exc:
            return Response(_validation_payload(exc), status=status.HTTP_400_BAD_REQUEST)
        except EbayUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(self.get_serializer(withdrawn).data)

    @action(detail=True, methods=["get"], url_path="aspects-check")
    def aspects_check(self, request, pk=None):
        draft = self.mutable_draft()
        try:
            return Response(ebay_aspects.check_aspects(draft, actor=request.user))
        except EbayUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=True, methods=["get"], url_path="staged-review")
    def staged_review(self, request, pk=None):
        draft = self.mutable_draft()
        try:
            return Response(ebay_publishing.staged_review(draft, actor=request.user))
        except ValidationError as exc:
            return Response(_validation_payload(exc), status=status.HTTP_400_BAD_REQUEST)
        except EbayUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        draft = self.mutable_draft()
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


def create_generated_draft(item, *, channel="ebay_au") -> ListingDraft:
    ctx = safe_context(item)
    generator = generator_for(item)
    specifics = build_specifics_from_context(ctx)
    boilerplate = (
        ListingBoilerplate.objects.filter(channel="ebay_au", is_active=True)
        .order_by("name")
        .first()
    )
    meta = {
        "title": generated_meta(generator.profile_key),
        "description": generated_meta(generator.profile_key),
    }
    price = None
    currency = item.currency or "AUD"
    title = item.title
    description = description_default(item)
    meta["editor_sources"] = {"title": "Item title", "description_html": "eBay copy-pack template", "item_specifics": "Allowlisted item fields", "photo_ids": "Item's own photos", "quantity": "Draft default (confirm remaining stock)"}
    photo_ids = [
        str(photo.id)
        for photo in item.photos.order_by("order_index", "created_at")
    ]
    return ListingDraft.objects.create(
        item=item,
        channel=channel,
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

    draft.generated_meta = meta


def _validation_payload(exc: ValidationError) -> dict:
    if hasattr(exc, "message_dict"):
        return exc.message_dict
    return {"detail": "; ".join(exc.messages)}


def _serialize_item_listing_state(item: InventoryItem, *, context: dict) -> dict:
    state = item_listing_state(item)
    serializer = ChannelListingSerializer(
        state["active_listings"],
        many=True,
        context=context,
    )
    return {
        "item": str(item.id),
        "sku": item.sku,
        "title": item.title,
        "state": state["state"],
        "message": state["message"],
        "quantity_sold": state["quantity_sold"],
        "quantity_remaining": state["quantity_remaining"],
        "quantity_total": state["quantity_total"],
        "active_listings": serializer.data,
    }
