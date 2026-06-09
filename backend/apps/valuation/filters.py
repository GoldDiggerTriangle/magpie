import django_filters

from apps.valuation.models import FeeSchedule, ValuationReport


class FeeScheduleFilter(django_filters.FilterSet):
    class Meta:
        model = FeeSchedule
        fields = ["is_active"]


class ValuationReportFilter(django_filters.FilterSet):
    class Meta:
        model = ValuationReport
        fields = ["item", "strategy", "is_current"]

