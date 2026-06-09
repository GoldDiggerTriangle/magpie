from django.contrib import admin

from apps.photos.models import PhotoAsset


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
        "created_at",
    )
    list_filter = ("role", "is_main", "exif_stripped")
    search_fields = ("item__sku", "item__title", "original_path", "processed_path", "thumb_path")
    readonly_fields = ("id", "created_at", "updated_at")
    autocomplete_fields = ("item",)
