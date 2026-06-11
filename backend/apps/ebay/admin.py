from django.contrib import admin

from apps.ebay.models import EbayAccountSnapshot, EbayCredential, OAuthState


@admin.register(EbayCredential)
class EbayCredentialAdmin(admin.ModelAdmin):
    list_display = [
        "environment",
        "ebay_username",
        "ebay_user_id",
        "connected_at",
        "access_token_expires_at",
        "refresh_token_expires_at",
    ]
    list_filter = ["environment", "connected_at"]
    search_fields = ["ebay_username", "ebay_user_id"]
    readonly_fields = [
        "owner",
        "environment",
        "ebay_user_id",
        "ebay_username",
        "scopes",
        "redacted_refresh_token",
        "redacted_access_token",
        "refresh_token_expires_at",
        "access_token_expires_at",
        "connected_at",
        "last_refresh_at",
        "last_refresh_error",
        "created_at",
        "updated_at",
    ]
    fields = readonly_fields

    def get_queryset(self, request):
        return super().get_queryset(request).defer("refresh_token", "access_token")

    @admin.display(description="refresh token")
    def redacted_refresh_token(self, obj):
        return "***" if obj and getattr(obj, "pk", True) else ""

    @admin.display(description="access token")
    def redacted_access_token(self, obj):
        return "***" if obj and getattr(obj, "pk", True) else ""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(OAuthState)
class OAuthStateAdmin(admin.ModelAdmin):
    list_display = ["id", "expires_at", "consumed_at", "created_at"]
    readonly_fields = ["state", "expires_at", "consumed_at", "created_at", "updated_at"]
    search_fields = ["state"]


@admin.register(EbayAccountSnapshot)
class EbayAccountSnapshotAdmin(admin.ModelAdmin):
    list_display = ["environment", "business_policies_opted_in", "fetched_at"]
    readonly_fields = [
        "environment",
        "business_policies_opted_in",
        "payment_policies",
        "fulfillment_policies",
        "return_policies",
        "fetched_at",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
