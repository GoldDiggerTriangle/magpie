from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.api.views import HealthCheckView
from apps.audit.views import AuditLogViewSet
from apps.acquisitions.views import AcquisitionRecordViewSet
from apps.catalog.views import ProductCategoryViewSet
from apps.dashboard.views import (
    AnalyticsAgingView,
    AnalyticsByCategoryView,
    AnalyticsEstimateVsActualView,
    AnalyticsListingOpportunitiesView,
    AnalyticsPnlView,
    AnalyticsSummaryView,
    DashboardPreferenceView,
    DashboardSummaryView,
)
from apps.ebay.views import (
    EbayCategoryAspectsView,
    EbayCategorySuggestionsView,
    EbayConnectCompleteView,
    EbayConnectStartView,
    EbayDisconnectView,
    EbayOrderDuplicateCandidateViewSet,
    EbayOrderStagingViewSet,
    EbayOrderSyncView,
    EbayMerchantLocationView,
    EbayRefreshPoliciesView,
    EbayStatusView,
)
from apps.inventory.views import InventoryItemViewSet
from apps.listing.views import (
    ItemListingDraftListCreateView,
    ListingBoilerplateViewSet,
    ListingDraftViewSet,
)
from apps.locations.views import StorageLocationViewSet
from apps.photos.views import PhotoAssetViewSet
from apps.research.views import (
    ComparableViewSet,
    ResearchLinksView,
    ResearchRecordViewSet,
)
from apps.sales.views import ItemSaleRecordListCreateView, SaleRecordViewSet
from apps.valuation.views import (
    FeeScheduleViewSet,
    ItemValuationReportListCreateView,
    MetalsSpotView,
    ValuationReportViewSet,
)

router = DefaultRouter()
router.register("items", InventoryItemViewSet, basename="item")
router.register("photos", PhotoAssetViewSet, basename="photo")
router.register("categories", ProductCategoryViewSet, basename="category")
router.register("locations", StorageLocationViewSet, basename="location")
router.register("acquisitions", AcquisitionRecordViewSet, basename="acquisition")
router.register("comparables", ComparableViewSet, basename="comparable")
router.register("research-records", ResearchRecordViewSet, basename="research-record")
router.register("fee-schedules", FeeScheduleViewSet, basename="fee-schedule")
router.register("listing-drafts", ListingDraftViewSet, basename="listing-draft")
router.register(
    "listing-boilerplates",
    ListingBoilerplateViewSet,
    basename="listing-boilerplate",
)
router.register("sales", SaleRecordViewSet, basename="sale")
router.register("ebay/order-staging", EbayOrderStagingViewSet, basename="ebay-order-staging")
router.register(
    "ebay/order-duplicates",
    EbayOrderDuplicateCandidateViewSet,
    basename="ebay-order-duplicate",
)
router.register("audit-log", AuditLogViewSet, basename="audit-log")

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path(
        "items/<uuid:item_id>/valuation-reports/",
        ItemValuationReportListCreateView.as_view(),
        name="item-valuation-reports",
    ),
    path(
        "items/<uuid:item_id>/listing-drafts/",
        ItemListingDraftListCreateView.as_view(),
        name="item-listing-drafts",
    ),
    path(
        "items/<uuid:item_id>/sales/",
        ItemSaleRecordListCreateView.as_view(),
        name="item-sales",
    ),
    path(
        "valuation-reports/<uuid:pk>/",
        ValuationReportViewSet.as_view(
            {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
        ),
        name="valuation-report-detail",
    ),
    path(
        "valuation-reports/<uuid:pk>/set-current/",
        ValuationReportViewSet.as_view({"post": "set_current"}),
        name="valuation-report-set-current",
    ),
    path(
        "valuation-reports/<uuid:pk>/profit/",
        ValuationReportViewSet.as_view({"get": "profit"}),
        name="valuation-report-profit",
    ),
    path(
        "items/<uuid:item_id>/research-links/",
        ResearchLinksView.as_view(),
        name="item-research-links",
    ),
    path("metals/spot/", MetalsSpotView.as_view(), name="metals-spot"),
    path("ebay/connect/start/", EbayConnectStartView.as_view(), name="ebay-connect-start"),
    path(
        "ebay/connect/complete/",
        EbayConnectCompleteView.as_view(),
        name="ebay-connect-complete",
    ),
    path("ebay/disconnect/", EbayDisconnectView.as_view(), name="ebay-disconnect"),
    path("ebay/status/", EbayStatusView.as_view(), name="ebay-status"),
    path("ebay/orders/sync/", EbayOrderSyncView.as_view(), name="ebay-orders-sync"),
    path(
        "ebay/refresh-policies/",
        EbayRefreshPoliciesView.as_view(),
        name="ebay-refresh-policies",
    ),
    path(
        "ebay/category-suggestions/",
        EbayCategorySuggestionsView.as_view(),
        name="ebay-category-suggestions",
    ),
    path(
        "ebay/category-aspects/",
        EbayCategoryAspectsView.as_view(),
        name="ebay-category-aspects",
    ),
    path(
        "ebay/merchant-location/",
        EbayMerchantLocationView.as_view(),
        name="ebay-merchant-location",
    ),
    path(
        "items/export.csv",
        InventoryItemViewSet.as_view({"get": "export_csv"}),
        name="item-export-csv",
    ),
    path("", include(router.urls)),
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("dashboard/preferences/", DashboardPreferenceView.as_view(), name="dashboard-preferences"),
    path("analytics/summary/", AnalyticsSummaryView.as_view(), name="analytics-summary"),
    path("analytics/pnl/", AnalyticsPnlView.as_view(), name="analytics-pnl"),
    path("analytics/by-category/", AnalyticsByCategoryView.as_view(), name="analytics-by-category"),
    path(
        "analytics/estimate-vs-actual/",
        AnalyticsEstimateVsActualView.as_view(),
        name="analytics-estimate-vs-actual",
    ),
    path("analytics/aging/", AnalyticsAgingView.as_view(), name="analytics-aging"),
    path(
        "analytics/listing-opportunities/",
        AnalyticsListingOpportunitiesView.as_view(),
        name="analytics-listing-opportunities",
    ),
]
