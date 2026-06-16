from django.contrib import admin

from apps.photos.models import PhotoAsset, PhotoDerivative


@admin.register(PhotoAsset)
class PhotoAssetAdmin(admin.ModelAdmin):
    list_display = (
        "item",
        "role",
        "is_main",
        "order_index",
        "width",
        "height",
        "exif_stripped",
        "fixup_status",
        "created_at",
    )
    list_filter = ("role", "is_main", "exif_stripped", "fixup_status")
    search_fields = ("item__sku", "item__title", "original_path", "processed_path", "thumb_path")
    readonly_fields = ("id", "created_at", "updated_at")
    autocomplete_fields = ("item", "active_derivative")


@admin.register(PhotoDerivative)
class PhotoDerivativeAdmin(admin.ModelAdmin):
    list_display = ("photo", "source", "status", "background_mode", "created_at")
    list_filter = ("source", "status", "background_mode")
    search_fields = (
        "photo__item__sku",
        "photo__item__title",
        "fixed_path",
        "source_path",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    autocomplete_fields = ("photo",)
