from django.contrib import admin

from apps.intelligence.models import (
    AICredential,
    AIReferenceLink,
    AIResearchCall,
    AIResearchSearchTerm,
    FieldSuggestion,
    ImageFingerprint,
)


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


@admin.register(AICredential)
class AICredentialAdmin(admin.ModelAdmin):
    list_display = ("provider", "model_id", "is_active", "monthly_budget_cap_usd", "connected_at")
    readonly_fields = ("created_at", "updated_at", "connected_at")
    search_fields = ("provider", "model_id")


@admin.register(AIResearchCall)
class AIResearchCallAdmin(admin.ModelAdmin):
    list_display = ("item", "phase", "status", "provider", "model_id", "estimated_cost_usd", "created_at")
    list_filter = ("phase", "status", "provider")
    search_fields = ("item__sku", "item__title", "provider", "model_id")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AIResearchSearchTerm)
class AIResearchSearchTermAdmin(admin.ModelAdmin):
    list_display = ("item", "phrase", "is_active", "created_at")
    search_fields = ("item__sku", "item__title", "phrase", "source_basis")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AIReferenceLink)
class AIReferenceLinkAdmin(admin.ModelAdmin):
    list_display = ("item", "label", "url", "created_at")
    search_fields = ("item__sku", "item__title", "label", "url", "source_basis")
    readonly_fields = ("created_at", "updated_at")
