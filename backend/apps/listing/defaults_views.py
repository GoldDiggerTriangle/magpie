from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

import integrations.ebay as ebay
from apps.catalog.models import ProductCategory
from apps.ebay.services import get_app_access_token
from apps.listing.defaults import DEFAULT_FIELDS, FIELD_LABELS, defaults_metadata, defaults_row, evaluate_defaults, normalize_values, revision
from apps.listing.editor_metadata import MARKETPLACE, fetch_editor_metadata, mapping
from apps.listing.models import CategoryListingDefaults


def payload(category, *, category_id=None):
    row = defaults_row(category)
    values = deepcopy(row.values if row else {})
    selected = {**values, **({"category_id": category_id} if category_id is not None else {})}
    metadata, _ = defaults_metadata(selected, row.metadata if row else {})
    _, checks = evaluate_defaults(values, metadata)
    return {"category": str(category.pk), "category_name": category.name, "values": values,
            "revision": revision(values), "updated_at": row.updated_at.isoformat() if row else None,
            "editor": {"metadata": metadata, "sources": {key: f"Human-set {category.name} defaults" for key in values},
                       "checks": [], "price_options": [], "price_source": None, "read_only": False, "staged_local_changes": False},
            "validation": checks}


class CategoryListingDefaultsViewSet(ViewSet):
    http_method_names = ["get", "put", "post", "head", "options"]

    def category(self, pk):
        return get_object_or_404(ProductCategory, pk=pk)

    def list(self, request):
        saved = {str(row.category_id): row for row in CategoryListingDefaults.objects.filter(environment=ebay.effective_environment(), marketplace=MARKETPLACE)}
        return Response({"categories": [{"id": str(row.pk), "name": row.name, "configured": bool(saved.get(str(row.pk)) and saved[str(row.pk)].values)} for row in ProductCategory.objects.all()]})

    def retrieve(self, request, pk=None):
        return Response(payload(self.category(pk), category_id=request.query_params.get("category_id")))

    def values_request(self, request, *, save=False):
        allowed = {"values", "expected_revision"} if save else {"values"}
        if not isinstance(request.data, dict) or set(request.data) - allowed or "values" not in request.data:
            raise ValidationError("Provide only values and, when saving, expected_revision.")
        return normalize_values(request.data["values"])

    @action(detail=True, methods=["post"])
    def preview(self, request, pk=None):
        category = self.category(pk)
        try:
            values = self.values_request(request)
        except ValidationError as exc:
            return Response({"detail": exc.messages}, status=400)
        current = payload(category)
        old = current["values"]
        changes = [{"field": key, "label": FIELD_LABELS[key], "before": old.get(key, ""), "after": values.get(key, ""),
                    "clears": bool(old.get(key) and not values.get(key))} for key in DEFAULT_FIELDS if old.get(key, "") != values.get(key, "")]
        return Response({"values": values, "changes": changes, "expected_revision": current["revision"], "category_name": category.name})

    def update(self, request, pk=None):
        category = self.category(pk)
        try:
            values = self.values_request(request, save=True)
        except ValidationError as exc:
            return Response({"detail": exc.messages}, status=400)
        with transaction.atomic():
            # Serialize even first creation. No drafts are read for update or rewritten.
            ProductCategory.objects.select_for_update().get(pk=category.pk)
            row = defaults_row(category)
            old = row.values if row else {}
            if request.data.get("expected_revision") != revision(old):
                return Response({"detail": "Defaults changed elsewhere. Preview again before saving."}, status=409)
            if row:
                claimed = CategoryListingDefaults.objects.filter(pk=row.pk, updated_at=row.updated_at).update(values=values, updated_at=timezone.now())
                if not claimed:
                    return Response({"detail": "Defaults changed elsewhere. Preview again."}, status=409)
            else:
                _, created = CategoryListingDefaults.objects.get_or_create(category=category, environment=ebay.effective_environment(), marketplace=MARKETPLACE, defaults={"values": values})
                if not created:
                    return Response({"detail": "Defaults changed elsewhere. Preview again before saving."}, status=409)
        return Response(payload(category))

    @action(detail=True, methods=["post"], url_path="refresh-metadata")
    def refresh_metadata(self, request, pk=None):
        category = self.category(pk)
        if not isinstance(request.data, dict) or set(request.data) - {"category_id", "query"}:
            return Response({"detail": "Only category ID and search are accepted."}, status=400)
        category_id, query = request.data.get("category_id", ""), request.data.get("query", "")
        if not isinstance(category_id, str) or len(category_id) > 30 or (category_id and not category_id.isdecimal()) or not isinstance(query, str) or len(query) > 200:
            return Response({"detail": "Provide a valid category ID or search."}, status=400)
        try:
            snapshot, search = fetch_editor_metadata(category_id=category_id, query=query, actor=request.user, allow_nonleaf=True)
        except (ValidationError, ebay.EbayUnavailable):
            return Response({"detail": "Metadata refresh failed; saved snapshots and defaults remain unchanged."}, status=503)
        with transaction.atomic():
            ProductCategory.objects.select_for_update().get(pk=category.pk)
            row, _ = CategoryListingDefaults.objects.get_or_create(category=category, environment=ebay.effective_environment())
            cached = deepcopy(mapping(row.metadata))
            if snapshot:
                categories = cached.setdefault("categories", {})
                categories.pop(category_id, None)
                categories[category_id] = snapshot
                cached["categories"] = dict(list(categories.items())[-8:])
            if search:
                cached["search"] = search
            row.metadata = cached
            row.save(update_fields=["metadata", "updated_at"])
        return Response(payload(category, category_id=category_id))

    @action(detail=True, methods=["get"], url_path="category-children")
    def category_children(self, request, pk=None):
        self.category(pk)
        category_id = request.query_params.get("category_id", "")
        if len(category_id) > 30 or not category_id.isdecimal() or int(category_id) <= 0:
            return Response({"detail": "Choose a non-root category ID."}, status=400)
        try:
            branch = ebay.get_ebay_taxonomy_adapter(access_token=get_app_access_token()).category_children(category_id=category_id)
        except ebay.EbayUnavailable:
            return Response({"detail": "Category browse unavailable; retry metadata refresh."}, status=503)
        return Response({**branch, "fetched_at": timezone.now().isoformat(), "provenance": "eBay AU Taxonomy subtree GET; immediate children only"})
