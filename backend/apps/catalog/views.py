from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.catalog.models import ProductCategory
from apps.catalog.denominations import apply_denomination_suggestions
from apps.catalog.profiles import get_schema
from apps.catalog.serializers import ProductCategorySerializer


class ProductCategoryViewSet(ModelViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    search_fields = ["name", "slug", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    @action(detail=True, methods=["get"], url_path="schema")
    def schema(self, request, pk=None):
        category = self.get_object()
        schema = get_schema(category.profile_key)
        return Response(
            {
                "profile_key": schema.profile_key,
                "fields": apply_denomination_suggestions(
                    schema.fields(),
                    category.profile_key,
                ),
            }
        )
