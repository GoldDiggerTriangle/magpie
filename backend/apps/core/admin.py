from django.contrib import admin

from apps.core.models import SkuSequence


@admin.register(SkuSequence)
class SkuSequenceAdmin(admin.ModelAdmin):
    list_display = ("prefix", "last_value")
    search_fields = ("prefix",)
