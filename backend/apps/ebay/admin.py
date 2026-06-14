from django.contrib import admin

from apps.ebay.models import (
    EbayAccountSnapshot,
    EbayAppToken,
    EbayCredential,
    EbayOrderDuplicateCandidate,
    EbayOrderStaging,
    EbayOrderSyncState,
    MerchantLocation,
    OAuthState,
)


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


@admin.register(EbayOrderSyncState)
class EbayOrderSyncStateAdmin(admin.ModelAdmin):
    list_display = ["environment", "last_synced_at", "lookback_days", "updated_at"]
    readonly_fields = ["environment", "last_synced_at", "lookback_days", "created_at", "updated_at"]


@admin.register(EbayOrderStaging)
class EbayOrderStagingAdmin(admin.ModelAdmin):
    list_display = [
        "environment",
        "ebay_order_id",
        "ebay_line_item_id",
        "sku",
        "quantity",
        "line_price",
        "fee_status",
        "status",
        "sale_date",
    ]
    list_filter = ["environment", "status", "fee_status", "sale_date"]
    search_fields = ["ebay_order_id", "ebay_line_item_id", "sku", "notes"]
    readonly_fields = ["raw", "finance_snapshot", "created_at", "updated_at"]


@admin.register(EbayOrderDuplicateCandidate)
class EbayOrderDuplicateCandidateAdmin(admin.ModelAdmin):
    list_display = [
        "environment",
        "ebay_order_id",
        "ebay_line_item_id",
        "sku",
        "item",
        "manual_sale",
        "status",
        "sale_date",
    ]
    list_filter = ["environment", "status", "sale_date"]
    search_fields = ["ebay_order_id", "ebay_line_item_id", "sku", "item__sku", "notes"]
    readonly_fields = ["raw", "created_at", "updated_at"]


@admin.register(EbayAppToken)
class EbayAppTokenAdmin(admin.ModelAdmin):
    list_display = ["environment", "expires_at", "created_at"]
    readonly_fields = [
        "environment",
        "redacted_access_token",
        "expires_at",
        "created_at",
        "updated_at",
    ]
    fields = readonly_fields

    def get_queryset(self, request):
        return super().get_queryset(request).defer("access_token")

    @admin.display(description="access token")
    def redacted_access_token(self, obj):
        return "***" if obj and getattr(obj, "pk", True) else ""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MerchantLocation)
class MerchantLocationAdmin(admin.ModelAdmin):
    list_display = [
        "environment",
        "merchant_location_key",
        "name",
        "country",
        "postal_code",
        "created_on_ebay",
        "fetched_at",
    ]
    readonly_fields = [
        "environment",
        "merchant_location_key",
        "name",
        "country",
        "postal_code",
        "city",
        "state",
        "created_on_ebay",
        "fetched_at",
        "created_at",
        "updated_at",
    ]
