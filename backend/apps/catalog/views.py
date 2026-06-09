from rest_framework.viewsets import ModelViewSet

from apps.catalog.models import ProductCategory
from apps.catalog.serializers import ProductCategorySerializer


class ProductCategoryViewSet(ModelViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    search_fields = ["name", "slug", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
