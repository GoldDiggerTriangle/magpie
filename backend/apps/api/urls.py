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
from apps.intelligence.views import (
    AICredentialView,
    AIStatusView,
    FieldSuggestionViewSet,
    ItemAIIdentifyView,
    ItemAIPriceAssistView,
    ItemAIReferencesView,
    ItemDuplicateScanView,
    ItemOcrRunView,
    ItemSoldSearchView,
)
from apps.listing.views import (
    ItemListingDraftListCreateView,
    ListingBoilerplateViewSet,
    ListingDraftViewSet,
)
from apps.locations.views import StorageLocationViewSet
from apps.photos.views import PhotoAssetViewSet
from apps.profit.views import (
    BuyCalculatorCalculateView,
    BuyCalculatorEvidenceView,
    EbayFeePreviewView,
    ProfitSettingView,
)
from apps.research.views import (
    ComparableViewSet,
    PricingEvidenceView,
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
router.register("field-suggestions", FieldSuggestionViewSet, basename="field-suggestion")
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
        "items/<uuid:item_id>/sold-searches/",
        ItemSoldSearchView.as_view(),
        name="item-sold-searches",
    ),
    path(
        "items/<uuid:item_id>/ocr/",
        ItemOcrRunView.as_view(),
        name="item-ocr",
    ),
    path(
        "items/<uuid:item_id>/duplicate-scan/",
        ItemDuplicateScanView.as_view(),
        name="item-duplicate-scan",
    ),
    path("ai/status/", AIStatusView.as_view(), name="ai-status"),
    path("ai/credential/", AICredentialView.as_view(), name="ai-credential"),
    path(
        "items/<uuid:item_id>/ai/identify/",
        ItemAIIdentifyView.as_view(),
        name="item-ai-identify",
    ),
    path(
        "items/<uuid:item_id>/ai/price-assist/",
        ItemAIPriceAssistView.as_view(),
        name="item-ai-price-assist",
    ),
    path(
        "items/<uuid:item_id>/ai/references/",
        ItemAIReferencesView.as_view(),
        name="item-ai-references",
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
    path(
        "items/<uuid:item_id>/pricing-evidence/",
        PricingEvidenceView.as_view(),
        name="item-pricing-evidence",
    ),
    path("metals/spot/", MetalsSpotView.as_view(), name="metals-spot"),
    path("profit/settings/", ProfitSettingView.as_view(), name="profit-settings"),
    path("profit/fees/preview/", EbayFeePreviewView.as_view(), name="profit-fees-preview"),
    path("buy-calculator/evidence/", BuyCalculatorEvidenceView.as_view(), name="buy-calculator-evidence"),
    path("buy-calculator/calculate/", BuyCalculatorCalculateView.as_view(), name="buy-calculator-calculate"),
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
