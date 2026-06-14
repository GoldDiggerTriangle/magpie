from django.contrib import admin

from apps.intelligence.models import FieldSuggestion, ImageFingerprint


@admin.register(FieldSuggestion)
class FieldSuggestionAdmin(admin.ModelAdmin):
    list_display = ("item", "field", "source", "confidence_band", "status", "created_at")
    list_filter = ("source", "confidence_band", "status")
    search_fields = ("item__sku", "item__title", "field", "evidence")
    readonly_fields = ("created_at", "updated_at", "resolved_at")


@admin.register(ImageFingerprint)
class ImageFingerprintAdmin(admin.ModelAdmin):
    list_display = ("photo", "item", "algorithm", "perceptual_hash", "created_at")
    search_fields = ("item__sku", "item__title", "perceptual_hash")
    readonly_fields = ("created_at", "updated_at")
