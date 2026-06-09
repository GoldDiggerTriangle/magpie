from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.acquisitions.views import AcquisitionRecordViewSet
from apps.catalog.views import ProductCategoryViewSet
from apps.dashboard.views import DashboardSummaryView
from apps.inventory.views import InventoryItemViewSet
from apps.locations.views import StorageLocationViewSet
from apps.photos.views import PhotoAssetViewSet

router = DefaultRouter()
router.register("items", InventoryItemViewSet, basename="item")
router.register("photos", PhotoAssetViewSet, basename="photo")
router.register("categories", ProductCategoryViewSet, basename="category")
router.register("locations", StorageLocationViewSet, basename="location")
router.register("acquisitions", AcquisitionRecordViewSet, basename="acquisition")

urlpatterns = [
    path(
        "items/export.csv",
        InventoryItemViewSet.as_view({"get": "export_csv"}),
        name="item-export-csv",
    ),
    path("", include(router.urls)),
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
]
