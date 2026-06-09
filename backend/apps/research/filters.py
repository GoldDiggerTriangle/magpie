import django_filters

from apps.research.models import Comparable, ResearchRecord


class ComparableFilter(django_filters.FilterSet):
    class Meta:
        model = Comparable
        fields = ["item", "kind"]


class ResearchRecordFilter(django_filters.FilterSet):
    class Meta:
        model = ResearchRecord
        fields = ["item"]

