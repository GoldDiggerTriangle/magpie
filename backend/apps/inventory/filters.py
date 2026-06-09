import django_filters
from django.db.models import Count

from apps.inventory.models import InventoryItem


class InventoryItemFilter(django_filters.FilterSet):
    has_photos = django_filters.BooleanFilter(method="filter_has_photos")
    min_value = django_filters.NumberFilter(field_name="estimated_value", lookup_expr="gte")
    max_value = django_filters.NumberFilter(field_name="estimated_value", lookup_expr="lte")

    class Meta:
        model = InventoryItem
        fields = ["status", "category", "condition", "location"]

    def filter_has_photos(self, queryset, name, value):
        queryset = queryset.annotate(photo_count=Count("photos"))
        if value:
            return queryset.filter(photo_count__gt=0)
        return queryset.filter(photo_count=0)
