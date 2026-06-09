from django.contrib import admin

from apps.catalog.models import ProductCategory


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sku_prefix", "parent", "profile_key")
    list_filter = ("sku_prefix", "profile_key")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug", "description")
    readonly_fields = ("id", "created_at", "updated_at")
